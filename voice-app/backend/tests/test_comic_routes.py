"""Route wiring + API smoke tests for Comic Series Analysis (tasks 1.1, 7.5, 7.6)."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import config, database
from backend.app import create_app
from backend.database import session as database_session


@pytest.fixture
def client(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c
    database_session.engine.dispose()


def _png_bytes(color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), color).save(buf, format="PNG")
    return buf.getvalue()


def test_routes_registered():
    app = create_app()
    paths = set(app.openapi()["paths"])
    assert "/comic-series-analysis/jobs" in paths
    assert "/comic-series-analysis/jobs/from-url" in paths
    assert "/comic-series-analysis/jobs/from-upload" in paths
    assert "/comic-series-analysis/capabilities" in paths
    # No direct AI-video handoff endpoint exists under this prefix.
    comic_paths = [p for p in paths if p.startswith("/comic-series-analysis")]
    assert not any("ai-video" in p for p in comic_paths)


def test_capabilities_endpoint(client):
    resp = client.get("/comic-series-analysis/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["feature_enabled"] is True
    assert "codecs" in body


def test_create_upload_job_and_list(client):
    files = [
        ("files", ("a.png", _png_bytes((1, 2, 3)), "image/png")),
        ("files", ("b.png", _png_bytes((9, 9, 9)), "image/png")),
    ]
    resp = client.post(
        "/comic-series-analysis/jobs/from-upload",
        files=files,
        data={"reading_mode": "vertical"},
    )
    assert resp.status_code == 200, resp.text
    job = resp.json()
    assert job["run_status"] == "source_ready"
    assert job["result_completeness"] == "complete"
    job_id = job["id"]

    # List is lightweight.
    listing = client.get("/comic-series-analysis/jobs").json()
    assert listing["total"] >= 1

    # Pages are paginated.
    pages = client.get(f"/comic-series-analysis/jobs/{job_id}/pages").json()
    assert pages["total"] == 2
    assert len(pages["items"]) == 2


def test_analyze_package_and_rewrite_flow(client, monkeypatch):
    from backend.services.comic_series_analysis import rewrite, vision_adapters

    vision_adapters.set_vision_adapter(vision_adapters.NullVisionAdapter())
    files = [("files", ("chapter.png", _png_bytes(), "image/png"))]
    job_id = client.post("/comic-series-analysis/jobs/from-upload", files=files).json()["id"]

    analyzed = client.post(f"/comic-series-analysis/jobs/{job_id}/analyze")
    assert analyzed.status_code == 202, analyzed.text
    assert analyzed.json()["analysis_revision"] == 1

    package = client.get(f"/comic-series-analysis/jobs/{job_id}/analysis-package")
    assert package.status_code == 200
    assert package.json()["analysis_revision"] == 1
    assert len(package.json()["panels"]) == 1

    optimized = {
        "title": "Cuộc hẹn dưới mưa",
        "synopsis": "Ari gặp lại Kai.",
        "hook": "Cánh cửa quán cà phê mở ra.",
        "full_story": "Ari bước vào quán và nhìn thấy Kai.",
        "plot_beats": ["Ari đến", "Ari gặp Kai"],
        "character_arcs": ["Ari đối diện ký ức"],
        "scene_outline": ["Quán cà phê trong mưa"],
    }
    captured: dict[str, object] = {}

    def fake_run_codex(settings, prompt, *_args, **_kwargs):
        captured["reasoning_effort"] = getattr(settings, "model_reasoning_effort", None)
        captured["prompt_chars"] = len(prompt)
        return json.dumps(optimized)

    monkeypatch.setattr(rewrite.ai_planning, "run_codex_exec", fake_run_codex)
    rewritten = client.post(f"/comic-series-analysis/jobs/{job_id}/rewrite")

    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["optimized_script"]["full_story"] == optimized["full_story"]
    assert captured["reasoning_effort"] == "high"
    assert captured["prompt_chars"] < 12_000

def test_rewrite_timeout_uses_evidence_grounded_fallback(client, monkeypatch):
    from backend.services.comic_series_analysis import rewrite, vision_adapters

    vision_adapters.set_vision_adapter(vision_adapters.NullVisionAdapter())
    files = [("files", ("chapter.png", _png_bytes(), "image/png"))]
    job_id = client.post("/comic-series-analysis/jobs/from-upload", files=files).json()["id"]

    analyzed = client.post(f"/comic-series-analysis/jobs/{job_id}/analyze")
    assert analyzed.status_code == 202, analyzed.text

    def timeout_run_codex(*_args, **_kwargs):
        raise rewrite.ai_planning.AIPlanningError(
            "Codex exec timed out after 180 seconds.",
            error_code="CODEX_EXEC_TIMEOUT",
        )

    monkeypatch.setattr(rewrite.ai_planning, "run_codex_exec", timeout_run_codex)
    rewritten = client.post(f"/comic-series-analysis/jobs/{job_id}/rewrite")

    assert rewritten.status_code == 200, rewritten.text
    optimized = rewritten.json()["optimized_script"]
    assert optimized["full_story"].strip()
    assert optimized["plot_beats"]
    assert optimized["scene_outline"]

def test_asset_original_preview_and_export_are_served_from_canonical_paths(client):
    files = [("files", ("a.png", _png_bytes(), "image/png"))]
    job_id = client.post("/comic-series-analysis/jobs/from-upload", files=files).json()["id"]
    pages = client.get(f"/comic-series-analysis/jobs/{job_id}/pages").json()
    asset_id = pages["items"][0]["asset_id"]

    original = client.get(f"/comic-series-analysis/assets/{asset_id}/original")
    assert original.status_code == 200
    assert original.headers["content-type"].startswith("image/png")
    assert "comic-" in original.headers["content-disposition"]

    preview = client.get(f"/comic-series-analysis/assets/{asset_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/webp")

    exported = client.post(f"/comic-series-analysis/assets/{asset_id}/exports?format=png")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("image/png")
    assert "comic-" in exported.headers["content-disposition"]

    invalid = client.post(f"/comic-series-analysis/assets/{asset_id}/exports?format=../../secret")
    assert invalid.status_code == 422


def test_create_url_job_draft(client):
    resp = client.post(
        "/comic-series-analysis/jobs/from-url",
        json={"url": "https://example.com/ch1", "reading_mode": "auto"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["run_status"] == "draft"


def test_url_ingestion_handles_direct_image_and_unsupported_content(client, monkeypatch):
    from backend.database import ComicSourceAsset, ComicSourcePage
    from backend.services.comic_series_analysis import fetcher, service

    session = database_session.SessionLocal()
    try:
        image_job = service.create_url_job(
            session,
            url="https://cdn.example.com/chapter.png",
            rights_attested=True,
        )

        def image_fetch(raw_url, **_kwargs):
            return fetcher.FetchResult(
                final_url=raw_url,
                status_code=200,
                content_kind="image",
                content=_png_bytes(),
                declared_content_type="image/png",
                detected_format="png",
            )

        monkeypatch.setattr(service.fetcher, "fetch", image_fetch)
        outcome = service.run_url_ingestion(session, image_job, "https://cdn.example.com/chapter.png")
        session.refresh(image_job)
        assert outcome.result_completeness == "complete"
        assert image_job.run_status == "source_ready"
        assert session.query(ComicSourcePage).filter_by(job_id=image_job.id, page_kind="image").count() == 1
        assert session.query(ComicSourceAsset).filter_by(job_id=image_job.id, provenance="web").count() == 1

        unsupported_job = service.create_url_job(
            session,
            url="https://docs.example.com/chapter.pdf",
            rights_attested=True,
        )

        def unsupported_fetch(raw_url, **_kwargs):
            return fetcher.FetchResult(
                final_url=raw_url,
                status_code=200,
                content_kind="unsupported",
                content=b"%PDF",
                declared_content_type="application/pdf",
            )

        monkeypatch.setattr(service.fetcher, "fetch", unsupported_fetch)
        outcome = service.run_url_ingestion(session, unsupported_job, "https://docs.example.com/chapter.pdf")
        session.refresh(unsupported_job)
        assert outcome.outcome_code == "unsupported_content"
        assert unsupported_job.run_status == "failed"
        assert unsupported_job.error_code == "COMIC_UNSUPPORTED_CONTENT"
    finally:
        session.close()

def test_url_job_rejects_private_host(client):
    resp = client.post(
        "/comic-series-analysis/jobs/from-url",
        json={"url": "http://127.0.0.1/secret"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "COMIC_URL_BLOCKED"


def test_canon_mode_requires_rights(client):
    resp = client.post(
        "/comic-series-analysis/jobs/from-url",
        json={"url": "https://example.com/ch1", "development_mode": "bam_canon_va_phat_trien_tiep"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "COMIC_RIGHTS_REQUIRED"


def test_delete_job(client):
    from backend.database import ComicAnalysisJob, ComicSourceAsset, ComicSourceDocument, ComicSourcePage

    files = [("files", ("a.png", _png_bytes(), "image/png"))]
    job_id = client.post("/comic-series-analysis/jobs/from-upload", files=files).json()["id"]
    session = database_session.SessionLocal()
    try:
        assert session.query(ComicAnalysisJob).filter_by(id=job_id).count() == 1
        assert session.query(ComicSourceDocument).filter_by(job_id=job_id).count() == 1
        assert session.query(ComicSourcePage).filter_by(job_id=job_id).count() == 1
        assert session.query(ComicSourceAsset).filter_by(job_id=job_id).count() == 1
    finally:
        session.close()

    resp = client.delete(f"/comic-series-analysis/jobs/{job_id}")
    assert resp.status_code == 200
    assert client.get(f"/comic-series-analysis/jobs/{job_id}").status_code == 404
    session = database_session.SessionLocal()
    try:
        assert session.query(ComicAnalysisJob).filter_by(id=job_id).count() == 0
        assert session.query(ComicSourceDocument).filter_by(job_id=job_id).count() == 0
        assert session.query(ComicSourcePage).filter_by(job_id=job_id).count() == 0
        assert session.query(ComicSourceAsset).filter_by(job_id=job_id).count() == 0
    finally:
        session.close()
