from __future__ import annotations

import io

import pytest
from PIL import Image

from backend import config, models
from backend.database import init_db
from backend.database import session as database_session
from backend.services import series_references, video_projects

@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()

def _png_bytes(color: tuple[int, int, int] = (40, 120, 200), size: tuple[int, int] = (128, 128)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()

def _series(db):
    return video_projects.create_series(
        models.VideoSeriesCreate(title="Reference Series", series_mode="hybrid", style_bible="cinematic watercolor"),
        db,
    )

def _profile(series_id: str, db, name: str = "Lan"):
    return video_projects.create_character_profile(
        series_id,
        models.SeriesCharacterProfileCreate(
            name=name,
            face_description=f"{name} co khuon mat tron",
            hair_description="toc den ngang vai",
            signature_outfit="ao khoac xanh",
        ),
        db,
    )

def test_reference_upload_requires_approval_and_provider_reports_fallback(db):
    series = _series(db)
    profile = _profile(series.id, db, "Lan")

    asset = series_references.upload_reference_asset(
        series.id,
        entity_type="character",
        entity_id=profile.id,
        reference_role="face_front",
        filename="lan.png",
        content_type="image/png",
        data=_png_bytes(),
        label="Lan chinh dien",
        db=db,
    )

    assert asset.approval_status == "pending_approval"
    assert asset.active is False
    assert asset.revision == 1
    assert asset.thumbnail_path

    package = series_references.build_reference_prompt_package(
        series.id,
        db,
        prompt_text="Lan buoc vao quan ca phe",
        provider="manual-provider",
        provider_supports_references=False,
    )
    assert package["reference_asset_ids"] == []

    approved = series_references.update_reference_asset_status(
        series.id,
        asset.id,
        models.SeriesReferenceAssetStatusRequest(
            approval_status="approved",
            active=True,
            reason="Duyet de dung lam chuan khuon mat",
        ),
        db,
    )

    assert approved is not None
    assert approved.approval_status == "approved"
    assert approved.active is True
    assert approved.revision == 2

    package = series_references.build_reference_prompt_package(
        series.id,
        db,
        prompt_text="Lan buoc vao quan ca phe",
        provider="manual-provider",
        provider_supports_references=False,
    )
    assert package["reference_asset_ids"] == [asset.id]
    assert package["provider_report"]["sent"] == []
    assert package["provider_report"]["skipped"][0]["id"] == asset.id
    assert "chưa hỗ trợ" in package["provider_report"]["skipped"][0]["reason_vi"]

def test_reference_upload_rejects_invalid_file_before_saving(db):
    series = _series(db)
    profile = _profile(series.id, db, "Lan")

    with pytest.raises(series_references.SeriesReferenceError, match="không phải ảnh|không được hỗ trợ"):
        series_references.upload_reference_asset(
            series.id,
            entity_type="character",
            entity_id=profile.id,
            reference_role="face_front",
            filename="lan.txt",
            content_type="text/plain",
            data=b"not an image",
            db=db,
        )

    listed = series_references.list_reference_assets(series.id, db)
    assert listed.total == 0

def test_character_revision_marks_only_dependent_artifact_stale(db):
    series = _series(db)
    lan = _profile(series.id, db, "Lan")
    mai = _profile(series.id, db, "Mai")

    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="story_panel",
            artifact_id="panel-lan",
            artifact_revision=1,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="character_profile",
                    dependency_id=lan.id,
                    dependency_revision=lan.revision,
                    dependency_scope="visual_identity",
                )
            ],
        ),
        db,
    )
    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="story_panel",
            artifact_id="panel-mai",
            artifact_revision=1,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="character_profile",
                    dependency_id=mai.id,
                    dependency_revision=mai.revision,
                    dependency_scope="visual_identity",
                )
            ],
        ),
        db,
    )

    updated = video_projects.update_character_profile(
        series.id,
        lan.id,
        models.SeriesCharacterProfileUpdate(hair_description="toc bac ngan"),
        db,
    )

    assert updated is not None
    assert updated.revision == lan.revision + 1
    events = series_references.list_stale_events(series.id, db)
    assert events.total == 1
    assert events.items[0].artifact_id == "panel-lan"
    assert events.items[0].dependency_id == lan.id

    request = series_references.request_targeted_regeneration(
        series.id,
        models.ArtifactTargetedRegenerationRequest(event_ids=[events.items[0].id]),
        db,
    )
    assert request.requested == 1
    assert request.artifacts[0]["artifact_id"] == "panel-lan"

def test_style_change_stales_visual_prompt_but_not_voice(db):
    series = _series(db)
    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="video_prompt",
            artifact_id="prompt-1",
            artifact_revision=1,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="series_style",
                    dependency_id=series.id,
                    dependency_revision=series.revision,
                    dependency_scope="camera_style",
                )
            ],
        ),
        db,
    )
    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="scene_voice",
            artifact_id="voice-1",
            artifact_revision=1,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="series_style",
                    dependency_id=series.id,
                    dependency_revision=series.revision,
                    dependency_scope="voice_profile",
                )
            ],
        ),
        db,
    )

    updated = video_projects.update_series(
        series.id,
        models.VideoSeriesUpdate(style_bible="noir lighting, static camera"),
        db,
    )

    assert updated is not None
    events = series_references.list_stale_events(series.id, db)
    assert events.total == 1
    assert events.items[0].artifact_type == "video_prompt"
    assert events.items[0].artifact_id == "prompt-1"

def test_version_history_diff_and_safe_delete_archive_reference(db):
    series = _series(db)
    profile = _profile(series.id, db, "Lan")
    asset = series_references.upload_reference_asset(
        series.id,
        entity_type="character",
        entity_id=profile.id,
        reference_role="full_body",
        filename="lan.png",
        content_type="image/png",
        data=_png_bytes((200, 80, 60)),
        db=db,
    )
    asset = series_references.update_reference_asset_status(
        series.id,
        asset.id,
        models.SeriesReferenceAssetStatusRequest(approval_status="approved", active=True),
        db,
    )
    assert asset is not None
    series_references.record_dependency_snapshots(
        series.id,
        models.ArtifactDependencyRecordRequest(
            artifact_type="story_panel",
            artifact_id="panel-uses-reference",
            artifact_revision=1,
            dependencies=[
                models.ArtifactDependencyInput(
                    dependency_type="reference_asset",
                    dependency_id=asset.id,
                    dependency_revision=asset.revision,
                    dependency_scope="reference_image",
                )
            ],
        ),
        db,
    )

    deleted = series_references.delete_reference_asset(series.id, asset.id, db)

    assert deleted == {"deleted": False, "archived": True, "dependency_count": 1}
    history = series_references.version_history(series.id, "reference_asset", asset.id, db)
    assert history.total == 3
    assert any("approval_status" in line or "active" in line for line in history.diff_vi)
    events = series_references.list_stale_events(series.id, db)
    assert events.total == 1
    assert events.items[0].artifact_id == "panel-uses-reference"
