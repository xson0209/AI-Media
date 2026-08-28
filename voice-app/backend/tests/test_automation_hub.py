from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from starlette.datastructures import Headers, UploadFile

from backend import config, database
from backend.app import create_app
from backend.database import (
    AutomationAsset,
    AutomationConnection,
    AutomationPublishAttempt,
    AutomationPublishJob,
    VideoProject,
    VideoRenderJob,
    get_db,
)
from backend.database import session as database_session
from backend.services.automation_hub import assets, connections, jobs, roxy, security, sidecar, storage
from backend.services.automation_hub.publishers.base import PublishRequest, PublishResult, PublisherError
from backend.services.automation_hub.publishers.facebook import FacebookPublisher
from backend.services.automation_hub.publishers.tiktok import TikTokPublisher
from backend.services.automation_hub.publishers.youtube import YouTubePublisher
from backend.services.automation_hub.schemas import (
    AutomationConnectionCreate,
    AutomationConnectionUpdate,
    AutomationPublishJobCreate,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    previous_data_dir = config.get_data_dir()
    config.set_data_dir(tmp_path)
    for name in (
        "VOICEBOX_AUTOMATION_SECRET_KEY",
        "VOICEBOX_FEATURE_AUTOMATION_HUB",
        "VOICEBOX_FEATURE_AUTOMATION_HUB_TIKTOK_DIRECT_POST",
        "VOICEBOX_AUTOMATION_MAX_UPLOAD_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if database_session.engine is not None:
            database_session.engine.dispose()
        config.set_data_dir(previous_data_dir)


def _upload(filename: str, content: bytes, content_type: str = "video/mp4") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _seed_asset_and_connection(
    db,
    *,
    platform: str = "youtube",
    secret: dict | None = None,
    public_config: dict | None = None,
) -> tuple[AutomationAsset, AutomationConnection]:
    asset_id = f"asset-{platform}"
    asset_dir = storage.assets_dir() / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_path = asset_dir / "video.mp4"
    asset_bytes = b"automation-hub-video"
    asset_path.write_bytes(asset_bytes)
    asset = AutomationAsset(
        id=asset_id,
        source_type="upload",
        stored_path=config.to_storage_path(asset_path),
        filename=asset_path.name,
        mime_type="video/mp4",
        size_bytes=len(asset_bytes),
        sha256=hashlib.sha256(asset_bytes).hexdigest(),
    )
    default_secrets = {
        "youtube": {"access_token": "youtube-secret"},
        "facebook": {"page_access_token": "facebook-secret"},
        "tiktok": {"access_token": "tiktok-secret"},
    }
    default_public = {
        "youtube": {},
        "facebook": {"page_id": "page-123"},
        "tiktok": {},
    }
    ciphertext, fingerprint = security.encrypt_secret(secret or default_secrets[platform])
    connection = AutomationConnection(
        id=f"connection-{platform}",
        kind="publisher",
        platform=platform,
        label=f"{platform} test",
        status="ready",
        public_config_json=public_config if public_config is not None else default_public[platform],
        secret_ciphertext=ciphertext,
        secret_fingerprint=fingerprint,
        scopes_json=[],
    )
    db.add_all([asset, connection])
    db.commit()
    return asset, connection


def _job_payload(asset: AutomationAsset, connection: AutomationConnection, *, key: str) -> AutomationPublishJobCreate:
    return AutomationPublishJobCreate(
        asset_id=asset.id,
        connection_id=connection.id,
        platform=connection.platform,
        publish_mode="draft" if connection.platform == "tiktok" else "standard",
        title="Video test",
        description="Mô tả test",
        tags=["test", "automation"],
        privacy="private",
        idempotency_key=key,
    )


def _publish_request(
    path: Path,
    *,
    platform: str,
    scheduled_at: datetime | None = None,
    publish_mode: str = "standard",
    secret: dict | None = None,
) -> PublishRequest:
    secrets = {
        "youtube": {"access_token": "youtube-token"},
        "facebook": {"page_access_token": "facebook-token"},
        "tiktok": {"access_token": "tiktok-token"},
    }
    public_configs = {
        "youtube": {"category_id": "22"},
        "facebook": {"page_id": "page-123", "graph_version": "v23.0"},
        "tiktok": {},
    }
    return PublishRequest(
        job_id="job-1",
        asset_path=path,
        mime_type="video/mp4",
        title="Tiêu đề",
        description="Mô tả",
        tags=["tag-one", "#tag-two"],
        privacy="private",
        scheduled_at=scheduled_at,
        publish_mode=publish_mode,
        public_config=public_configs[platform],
        secret=secret if secret is not None else secrets[platform],
    )


def test_migration_creates_automation_tables_indexes_and_unique_idempotency(db):
    inspector = inspect(database_session.engine)
    assert {
        "automation_connections",
        "automation_assets",
        "automation_publish_jobs",
        "automation_publish_attempts",
    }.issubset(set(inspector.get_table_names()))

    job_indexes = {item["name"] for item in inspector.get_indexes("automation_publish_jobs")}
    assert "idx_automation_publish_jobs_status_schedule" in job_indexes
    assert "idx_automation_publish_jobs_connection" in job_indexes
    unique_columns = {
        tuple(item.get("column_names") or [])
        for item in inspector.get_unique_constraints("automation_publish_jobs")
    }
    assert ("idempotency_key",) in unique_columns


def test_connection_secret_is_encrypted_redacted_and_preserved_on_public_update(db, monkeypatch):
    monkeypatch.setenv("VOICEBOX_AUTOMATION_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    raw_secret = "never-return-this-token"
    response = connections.create_connection(
        AutomationConnectionCreate(
            kind="publisher",
            platform="youtube",
            label="Kênh YouTube",
            public_config={"channel_label": "Demo"},
            secret={"access_token": raw_secret},
            scopes=["youtube.upload"],
        ),
        db,
    )
    row = db.query(AutomationConnection).filter(AutomationConnection.id == response.id).one()
    original_ciphertext = row.secret_ciphertext

    assert raw_secret not in row.secret_ciphertext
    assert raw_secret not in response.model_dump_json()
    assert response.has_secret is True
    assert response.secret_fingerprint == row.secret_fingerprint

    updated = connections.update_connection(
        row.id,
        AutomationConnectionUpdate(label="Kênh YouTube mới", public_config={"channel_label": "Mới"}),
        db,
    )
    db.refresh(row)
    assert updated is not None
    assert updated.label == "Kênh YouTube mới"
    assert row.secret_ciphertext == original_ciphertext
    assert security.decrypt_secret(row.secret_ciphertext)["access_token"] == raw_secret


def test_connection_key_loss_marks_connection_needs_auth(db, monkeypatch):
    monkeypatch.setenv("VOICEBOX_AUTOMATION_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    response = connections.create_connection(
        AutomationConnectionCreate(
            kind="publisher",
            platform="tiktok",
            label="TikTok",
            secret={"access_token": "secret-token"},
        ),
        db,
    )
    monkeypatch.setenv("VOICEBOX_AUTOMATION_SECRET_KEY", Fernet.generate_key().decode("ascii"))

    with pytest.raises(security.SecretStoreError):
        connections.update_connection(
            response.id,
            AutomationConnectionUpdate(label="TikTok đổi tên"),
            db,
        )

    row = db.query(AutomationConnection).filter(AutomationConnection.id == response.id).one()
    db.refresh(row)
    assert row.status == "needs_auth"
    assert "secret-token" not in (row.failure_reason or "")


@pytest.mark.asyncio
async def test_roxy_mock_transport_covers_contract_and_never_exposes_token(monkeypatch):
    api_key = "roxy-key-that-must-stay-secret"
    requests: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["token"] == api_key
        requests.append((request.method, request.url.path))
        path = request.url.path
        if path == "/health":
            data = {"desktop": "ready"}
        elif path == "/browser/workspace":
            data = {"rows": [{"id": 1, "name": "Workspace"}], "total": 1}
        elif path == "/browser/list_v3":
            data = {"rows": [{"dirId": "profile-1", "windowName": "Profile"}], "total": 1}
        elif path == "/browser/open":
            data = {"dirId": "profile-1", "ws": "ws://127.0.0.1/devtools", "token": api_key}
        elif path == "/browser/close":
            data = {"ok": True}
        elif path == "/browser/connection_info":
            data = [{"dirId": "profile-1", "http": "http://127.0.0.1:9222", "cookie": "private"}]
        else:
            return httpx.Response(404, json={"code": 404})
        return httpx.Response(200, json={"code": 0, "data": data})

    client = roxy.RoxyLocalApiClient(api_key=api_key, transport=httpx.MockTransport(handler))
    assert (await client.health())["ok"] is True
    assert (await client.workspaces())["total"] == 1
    assert (await client.profiles(1))["rows"][0]["dirId"] == "profile-1"
    opened = await client.open_profile(1, "profile-1")
    assert opened["ws"].startswith("ws://")
    assert api_key not in json.dumps(opened)
    assert "token" not in opened
    assert (await client.close_profiles(["profile-1"]))["results"][0]["closed"] is True
    info = await client.connection_info(["profile-1"])
    assert "cookie" not in info[0]
    assert {path for _, path in requests} == {
        "/health",
        "/browser/workspace",
        "/browser/list_v3",
        "/browser/open",
        "/browser/close",
        "/browser/connection_info",
    }

    async def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 401, "msg": f"invalid token {api_key}"})

    rejected_client = roxy.RoxyLocalApiClient(api_key=api_key, transport=httpx.MockTransport(rejected))
    with pytest.raises(roxy.RoxyApiError) as exc_info:
        await rejected_client.health()
    assert api_key not in str(exc_info.value)


@pytest.mark.asyncio
async def test_asset_upload_sanitizes_path_hashes_and_snapshots_content(db):
    content = b"immutable-upload-content"
    response = await assets.create_from_upload(_upload("../unsafe/video.mp4", content), db)
    row = db.query(AutomationAsset).filter(AutomationAsset.id == response.id).one()
    resolved = assets.resolve_asset_path(row)

    assert response.filename == "video.mp4"
    assert response.sha256 == hashlib.sha256(content).hexdigest()
    assert response.size_bytes == len(content)
    assert resolved.read_bytes() == content
    assert storage.assets_dir().resolve() in resolved.resolve().parents


@pytest.mark.asyncio
async def test_asset_rejects_unsupported_empty_and_oversized_uploads(db, monkeypatch):
    with pytest.raises(assets.AssetError) as unsupported:
        await assets.create_from_upload(_upload("payload.txt", b"not-video", "text/plain"), db)
    assert unsupported.value.error_code == "AUTOMATION_ASSET_TYPE_UNSUPPORTED"

    with pytest.raises(assets.AssetError) as empty:
        await assets.create_from_upload(_upload("empty.mp4", b""), db)
    assert empty.value.error_code == "AUTOMATION_ASSET_EMPTY"

    monkeypatch.setenv("VOICEBOX_AUTOMATION_MAX_UPLOAD_BYTES", "1024")
    with pytest.raises(assets.AssetError) as oversized:
        await assets.create_from_upload(_upload("large.mp4", b"x" * 1025), db)
    assert oversized.value.error_code == "AUTOMATION_ASSET_TOO_LARGE"


def test_import_render_creates_snapshot_independent_from_source(db):
    source = config.get_data_dir() / "render-output.mp4"
    source.write_bytes(b"original-render")
    project = VideoProject(title="Project", topic="Topic")
    db.add(project)
    db.flush()
    render = VideoRenderJob(
        project_id=project.id,
        status="completed",
        progress=1.0,
        output_path=config.to_storage_path(source),
    )
    db.add(render)
    db.commit()

    response = assets.import_render_output(render.id, db)
    row = db.query(AutomationAsset).filter(AutomationAsset.id == response.id).one()
    snapshot = assets.resolve_asset_path(row)
    source.write_bytes(b"source-changed-after-import")

    assert snapshot.read_bytes() == b"original-render"
    assert row.source_ref == render.id
    db.refresh(render)
    assert render.status == "completed"


@pytest.mark.asyncio
async def test_youtube_resumable_upload_and_native_schedule(tmp_path):
    path = tmp_path / "youtube.mp4"
    video = b"youtube-video-bytes"
    path.write_bytes(video)
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured["metadata"] = json.loads((await request.aread()).decode("utf-8"))
            captured["init_headers"] = dict(request.headers)
            return httpx.Response(200, headers={"Location": "https://upload.youtube.test/session"})
        captured["upload_headers"] = dict(request.headers)
        captured["upload_body"] = await request.aread()
        return httpx.Response(200, json={"id": "youtube-video-id"})

    scheduled = datetime.now(timezone.utc) + timedelta(days=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await YouTubePublisher(client=client).publish(
            _publish_request(path, platform="youtube", scheduled_at=scheduled)
        )

    metadata = captured["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["status"]["privacyStatus"] == "private"
    assert metadata["status"]["publishAt"].endswith("Z")
    assert captured["upload_body"] == video
    assert captured["upload_headers"]["content-length"] == str(len(video))
    assert result.provider_post_id == "youtube-video-id"
    assert result.result["scheduled"] is True


@pytest.mark.asyncio
async def test_youtube_refreshes_expired_token_before_resumable_upload(tmp_path):
    path = tmp_path / "youtube-refresh.mp4"
    path.write_bytes(b"youtube-refresh-video")
    authorization_headers: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://oauth2.googleapis.com/token":
            return httpx.Response(200, json={"access_token": "refreshed-token", "expires_in": 3600})
        if request.method == "POST":
            authorization_headers.append(request.headers["authorization"])
            return httpx.Response(200, headers={"Location": "https://upload.youtube.test/refreshed-session"})
        return httpx.Response(200, json={"id": "youtube-refreshed-id"})

    expired_secret = {
        "access_token": "expired-token",
        "expires_at": "2000-01-01T00:00:00Z",
        "refresh_token": "refresh-token",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await YouTubePublisher(client=client).publish(
            _publish_request(path, platform="youtube", secret=expired_secret)
        )

    assert authorization_headers == ["Bearer refreshed-token"]
    assert result.provider_post_id == "youtube-refreshed-id"
    assert result.updated_secret is not None
    assert result.updated_secret["access_token"] == "refreshed-token"
    assert result.updated_secret["refresh_token"] == "refresh-token"


@pytest.mark.asyncio
async def test_youtube_init_failure_is_retryable_without_ambiguous_outcome(tmp_path):
    path = tmp_path / "youtube.mp4"
    path.write_bytes(b"video")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PublisherError) as exc_info:
            await YouTubePublisher(client=client).publish(_publish_request(path, platform="youtube"))
    assert exc_info.value.retryable is True
    assert exc_info.value.ambiguous is False


@pytest.mark.asyncio
async def test_facebook_page_resumable_upload_uses_video_host_and_schedule(tmp_path):
    path = tmp_path / "facebook.mp4"
    video = b"facebook-video"
    path.write_bytes(video)
    calls: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        calls.append({"url": str(request.url), "body": body})
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "upload_session_id": "session-1",
                    "video_id": "facebook-video-id",
                    "start_offset": "0",
                    "end_offset": str(len(video)),
                },
            )
        if len(calls) == 2:
            return httpx.Response(
                200,
                json={"start_offset": str(len(video)), "end_offset": str(len(video))},
            )
        return httpx.Response(200, json={"success": True, "video_id": "facebook-video-id"})

    scheduled = datetime.now(timezone.utc) + timedelta(days=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FacebookPublisher(client=client).publish(
            _publish_request(path, platform="facebook", scheduled_at=scheduled)
        )

    assert len(calls) == 3
    assert calls[0]["url"].startswith("https://graph-video.facebook.com/v23.0/page-123/videos")
    finish_body = calls[2]["body"].decode("utf-8")
    assert "published=false" in finish_body
    assert "scheduled_publish_time=" in finish_body
    assert result.provider_post_id == "facebook-video-id"
    assert result.result["scheduled"] is True


@pytest.mark.asyncio
async def test_tiktok_draft_init_and_small_file_content_range(tmp_path):
    path = tmp_path / "tiktok.mp4"
    video = b"tiktok-small-video"
    path.write_bytes(video)
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured["init"] = json.loads((await request.aread()).decode("utf-8"))
            return httpx.Response(
                200,
                json={"data": {"upload_url": "https://upload.tiktok.test/video", "publish_id": "publish-1"}},
            )
        captured["range"] = request.headers["content-range"]
        captured["length"] = request.headers["content-length"]
        captured["body"] = await request.aread()
        return httpx.Response(201)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TikTokPublisher(client=client).publish(
            _publish_request(path, platform="tiktok", publish_mode="draft")
        )

    source_info = captured["init"]["source_info"]
    assert source_info["video_size"] == len(video)
    assert source_info["chunk_size"] == len(video)
    assert source_info["total_chunk_count"] == 1
    assert captured["range"] == f"bytes 0-{len(video) - 1}/{len(video)}"
    assert captured["length"] == str(len(video))
    assert captured["body"] == video
    assert result.provider_post_id == "publish-1"
    assert result.result["mode"] == "draft"


@pytest.mark.asyncio
async def test_tiktok_direct_post_guard_rejects_before_network(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEBOX_FEATURE_AUTOMATION_HUB_TIKTOK_DIRECT_POST", raising=False)
    path = tmp_path / "tiktok.mp4"
    path.write_bytes(b"video")
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PublisherError) as exc_info:
            await TikTokPublisher(client=client).publish(
                _publish_request(path, platform="tiktok", publish_mode="direct")
            )
    assert exc_info.value.error_code == "TIKTOK_DIRECT_POST_DISABLED"
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "status_code", "publisher_type", "expected_error_code", "secret_value"),
    [
        ("youtube", 401, YouTubePublisher, "YOUTUBE_HTTP_401", "youtube-token"),
        ("facebook", 403, FacebookPublisher, "FACEBOOK_HTTP_403", "facebook-token"),
        ("tiktok", 401, TikTokPublisher, "TIKTOK_HTTP_401", "tiktok-token"),
    ],
)
async def test_publishers_redact_provider_auth_and_scope_failures(
    tmp_path,
    platform,
    status_code,
    publisher_type,
    expected_error_code,
    secret_value,
):
    path = tmp_path / f"{platform}-auth-error.mp4"
    path.write_bytes(b"video")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": f"invalid credential {secret_value}"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PublisherError) as exc_info:
            await publisher_type(client=client).publish(_publish_request(path, platform=platform))

    error = exc_info.value
    assert error.error_code == expected_error_code
    assert error.retryable is False
    assert error.ambiguous is False
    assert error.response_meta == {"http_status": status_code}
    assert secret_value not in str(error)


@pytest.mark.asyncio
async def test_sidecar_start_reuses_external_healthy_runtime_without_spawning(monkeypatch):
    monkeypatch.setattr(
        sidecar,
        "health",
        lambda: _async_value({"ready": True, "url": "http://127.0.0.1:3333/health"}),
    )

    def fail_spawn(*args, **kwargs):
        raise AssertionError("A healthy external sidecar must not be spawned again")

    monkeypatch.setattr(sidecar.subprocess, "Popen", fail_spawn)
    status = await sidecar.start()
    assert status["ready"] is True
    assert status["managed"] is False


async def _async_value(value):
    return value


def test_job_idempotency_cancel_retry_and_duplicate_guard(db):
    asset, connection = _seed_asset_and_connection(db)
    payload = _job_payload(asset, connection, key="idempotency-job-0001")
    first = jobs.create_job(payload, db)
    second = jobs.create_job(payload, db)

    assert first.id == second.id
    assert db.query(AutomationPublishJob).count() == 1

    cancelled = jobs.cancel_job(first.id, db)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    retried = jobs.retry_job(first.id, db)
    assert retried is not None
    assert retried.status == "queued"

    row = jobs.get_job(first.id, db)
    row.status = "failed"
    row.provider_post_id = "already-created"
    db.commit()
    with pytest.raises(jobs.JobError) as exc_info:
        jobs.retry_job(first.id, db)
    assert exc_info.value.error_code == "AUTOMATION_DUPLICATE_GUARD"


def test_retry_preserves_future_tiktok_schedule_without_enqueueing(db, monkeypatch):
    asset, connection = _seed_asset_and_connection(db, platform="tiktok")
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    payload = AutomationPublishJobCreate(
        asset_id=asset.id,
        connection_id=connection.id,
        platform="tiktok",
        publish_mode="draft",
        title="Scheduled TikTok retry",
        description="",
        tags=[],
        privacy="private",
        scheduled_at=scheduled_at,
        idempotency_key="scheduled-tiktok-retry",
    )
    created = jobs.create_job(payload, db)
    assert created.status == "scheduled"
    cancelled = jobs.cancel_job(created.id, db)
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    enqueued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue_job", enqueued.append)
    retried = jobs.retry_job(created.id, db)

    assert retried is not None
    assert retried.status == "scheduled"
    assert retried.scheduled_at == scheduled_at.replace(tzinfo=None)
    assert enqueued == []


def test_startup_recovery_marks_active_jobs_interrupted_without_requeue(db):
    asset, connection = _seed_asset_and_connection(db)
    response = jobs.create_job(_job_payload(asset, connection, key="idempotency-job-recovery"), db)
    row = jobs.get_job(response.id, db)
    row.status = "uploading"
    row.provider_post_id = "provider-may-have-created-this"
    db.commit()

    assert jobs.sync_stale_running_jobs(db) == 1
    db.refresh(row)
    assert row.status == "interrupted"
    assert row.error_code == "AUTOMATION_JOB_INTERRUPTED"
    assert row.provider_post_id == "provider-may-have-created-this"


def test_persisted_ready_jobs_are_enqueued_fifo(db, monkeypatch):
    asset, connection = _seed_asset_and_connection(db)
    older = AutomationPublishJob(
        asset_id=asset.id,
        connection_id=connection.id,
        platform="youtube",
        publish_mode="standard",
        status="queued",
        title="Older",
        description="",
        idempotency_key="fifo-older-job",
        created_at=datetime.utcnow() - timedelta(minutes=1),
    )
    newer = AutomationPublishJob(
        asset_id=asset.id,
        connection_id=connection.id,
        platform="youtube",
        publish_mode="standard",
        status="queued",
        title="Newer",
        description="",
        idempotency_key="fifo-newer-job",
        created_at=datetime.utcnow(),
    )
    db.add_all([newer, older])
    db.commit()
    captured: list[str] = []
    monkeypatch.setattr(jobs, "enqueue_job", captured.append)

    jobs._enqueue_persisted_ready_jobs()

    assert captured == [older.id, newer.id]


def test_worker_initializes_bounded_configured_concurrency(monkeypatch):
    class FakeTask:
        def done(self):
            return False

        def cancel(self):
            return None

    captured: list[str] = []

    def capture_background_task(coroutine):
        captured.append(coroutine.cr_code.co_name)
        coroutine.close()
        return FakeTask()

    monkeypatch.setenv("VOICEBOX_AUTOMATION_PUBLISHING_CONCURRENCY", "3")
    monkeypatch.setattr(jobs, "_queue", None)
    monkeypatch.setattr(jobs, "_worker_tasks", [])
    monkeypatch.setattr(jobs, "_poller_task", None)
    monkeypatch.setattr(jobs, "create_background_task", capture_background_task)
    monkeypatch.setattr(jobs, "_enqueue_persisted_ready_jobs", lambda: None)

    jobs.init_worker(force=True)

    assert captured == ["_worker_loop", "_worker_loop", "_worker_loop", "_scheduled_poller"]
    assert jobs.worker_snapshot()["max_concurrency"] == 3


@pytest.mark.asyncio
async def test_job_worker_retries_safe_failure_and_records_attempts(db, monkeypatch):
    asset, connection = _seed_asset_and_connection(db)
    response = jobs.create_job(_job_payload(asset, connection, key="retry-safe-failure"), db)

    class RetryThenSucceed:
        def __init__(self):
            self.calls = 0

        async def publish(self, request: PublishRequest) -> PublishResult:
            self.calls += 1
            if self.calls == 1:
                raise PublisherError(
                    "Lỗi mạng an toàn để retry.",
                    error_code="TEST_RETRYABLE",
                    retryable=True,
                )
            return PublishResult(provider_post_id="provider-success", provider_url="https://example.test/post")

    publisher = RetryThenSucceed()
    monkeypatch.setattr(jobs, "get_publisher", lambda platform: publisher)
    await jobs._process_job(response.id)

    db.expire_all()
    row = jobs.get_job(response.id, db)
    attempts = (
        db.query(AutomationPublishAttempt)
        .filter(AutomationPublishAttempt.job_id == response.id)
        .order_by(AutomationPublishAttempt.attempt_number.asc())
        .all()
    )
    assert publisher.calls == 2
    assert row.status == "completed"
    assert row.provider_post_id == "provider-success"
    assert [attempt.status for attempt in attempts] == ["failed", "completed"]


@pytest.mark.asyncio
async def test_job_worker_does_not_retry_ambiguous_failure(db, monkeypatch):
    asset, connection = _seed_asset_and_connection(db)
    response = jobs.create_job(_job_payload(asset, connection, key="retry-ambiguous-failure"), db)

    class AmbiguousFailure:
        def __init__(self):
            self.calls = 0

        async def publish(self, request: PublishRequest) -> PublishResult:
            self.calls += 1
            raise PublisherError(
                "Provider có thể đã nhận video.",
                error_code="TEST_AMBIGUOUS",
                retryable=True,
                ambiguous=True,
            )

    publisher = AmbiguousFailure()
    monkeypatch.setattr(jobs, "get_publisher", lambda platform: publisher)
    await jobs._process_job(response.id)

    db.expire_all()
    row = jobs.get_job(response.id, db)
    assert publisher.calls == 1
    assert row.status == "interrupted"
    assert row.attempt_count == 1
    assert db.query(AutomationPublishAttempt).filter(AutomationPublishAttempt.job_id == response.id).count() == 1


def test_api_feature_guard_and_connection_response_redaction(db, monkeypatch):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    raw_secret = "api-response-must-not-contain-this"
    payload = {
        "kind": "publisher",
        "platform": "youtube",
        "label": "YouTube API",
        "public_config": {"channel_label": "Demo"},
        "secret": {"access_token": raw_secret},
        "scopes": ["youtube.upload"],
    }
    try:
        blocked = client.post("/automation-hub/connections", json=payload)
        assert blocked.status_code == 503
        assert blocked.json()["detail"]["error_code"] == "AUTOMATION_HUB_DISABLED"
        assert db.query(AutomationConnection).count() == 0

        monkeypatch.setenv("VOICEBOX_FEATURE_AUTOMATION_HUB", "true")
        created = client.post("/automation-hub/connections", json=payload)
        assert created.status_code == 200
        body = created.json()
        serialized = json.dumps(body)
        assert body["has_secret"] is True
        assert "secret" not in body
        assert "secret_ciphertext" not in body
        assert raw_secret not in serialized
        assert "/automation-hub/jobs" in app.openapi()["paths"]

        asset, connection = _seed_asset_and_connection(db)
        job_payload = _job_payload(asset, connection, key="api-job-crud-0001").model_dump(mode="json")
        created_job = client.post("/automation-hub/jobs", json=job_payload)
        assert created_job.status_code == 200
        job_body = created_job.json()
        job_id = job_body["id"]
        assert job_body["status"] == "queued"
        assert raw_secret not in json.dumps(job_body)
        assert "secret_ciphertext" not in json.dumps(job_body)

        listed_jobs = client.get("/automation-hub/jobs")
        assert listed_jobs.status_code == 200
        assert any(item["id"] == job_id for item in listed_jobs.json())
        fetched_job = client.get(f"/automation-hub/jobs/{job_id}")
        assert fetched_job.status_code == 200
        assert fetched_job.json()["id"] == job_id

        cancelled_job = client.post(f"/automation-hub/jobs/{job_id}/cancel")
        assert cancelled_job.status_code == 200
        assert cancelled_job.json()["status"] == "cancelled"
        retried_job = client.post(f"/automation-hub/jobs/{job_id}/retry")
        assert retried_job.status_code == 200
        assert retried_job.json()["status"] == "queued"
        cancelled_again = client.post(f"/automation-hub/jobs/{job_id}/cancel")
        assert cancelled_again.status_code == 200
        deleted_job = client.delete(f"/automation-hub/jobs/{job_id}")
        assert deleted_job.status_code == 200
        assert deleted_job.json() == {"deleted": True}
    finally:
        client.close()
        app.dependency_overrides.clear()
