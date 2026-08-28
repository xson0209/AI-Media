"""Runner + service tests (tasks 7.4, 7.9, 12.8)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend import config, database
from backend.database import session as database_session
from backend.services.comic_series_analysis import runner, schemas, service
from backend.services.comic_series_analysis.contracts import ComicAnalysisError


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database_session.engine.dispose()


def _png(color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), color).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_job_preserves_order_and_provenance(db):
    job = service.create_upload_job(
        db, images=[("a.png", _png((1, 2, 3))), ("b.png", _png((4, 5, 6)))]
    )
    from backend.database import ComicSourcePage
    pages = (
        db.query(ComicSourcePage)
        .filter_by(job_id=job.id)
        .order_by(ComicSourcePage.page_order)
        .all()
    )
    assert [p.page_order for p in pages] == [0, 1]
    assert all(p.provenance == "upload" for p in pages)


def test_bad_upload_file_no_orphan(db):
    # One valid, one invalid (not an image).
    job = service.create_upload_job(
        db, images=[("ok.png", _png()), ("bad.txt", b"not an image at all")]
    )
    from backend.database import ComicSourceAsset
    assets = db.query(ComicSourceAsset).filter_by(job_id=job.id).all()
    # Both recorded, but the bad one has no original_path (no orphan blob).
    bad = [a for a in assets if a.codec_status == "unsupported_image_format"]
    assert len(bad) == 1
    assert bad[0].original_path is None


def test_delete_job_cleans_children(db):
    job = service.create_upload_job(db, images=[("a.png", _png())])
    from backend.database import ComicSourceAsset, ComicSourcePage, ComicSourceDocument
    assert db.query(ComicSourceAsset).filter_by(job_id=job.id).count() >= 1
    assert service.delete_job(db, job.id) is True
    assert service.get_job(db, job.id) is None
    assert db.query(ComicSourceAsset).filter_by(job_id=job.id).count() == 0
    assert db.query(ComicSourcePage).filter_by(job_id=job.id).count() == 0
    assert db.query(ComicSourceDocument).filter_by(job_id=job.id).count() == 0


def test_delete_job_cleans_analysis_review_and_handoff_rows(db):
    from backend.database import (
        ComicApprovalManifest,
        ComicDetectedCharacter,
        ComicDetectedLocation,
        ComicPanel,
        ComicPlotAnalysis,
        ComicSeriesHandoff,
        ComicSeriesHandoffItem,
        ComicSourcePage,
        ComicSourceVersionRecord,
        ComicSpeechBubble,
    )

    job = service.create_upload_job(db, images=[("analyzed.png", _png())])
    page = db.query(ComicSourcePage).filter_by(job_id=job.id).one()
    manifest = ComicApprovalManifest(
        job_id=job.id,
        analysis_revision=1,
        manifest_hash="manifest-hash",
    )
    panel = ComicPanel(
        job_id=job.id,
        analysis_revision=1,
        page_id=page.id,
        asset_id=page.asset_id,
    )
    character = ComicDetectedCharacter(
        job_id=job.id,
        analysis_revision=1,
        display_name="Ari",
    )
    location = ComicDetectedLocation(
        job_id=job.id,
        analysis_revision=1,
        name="Quan ca phe",
    )
    plot = ComicPlotAnalysis(
        job_id=job.id,
        analysis_revision=1,
        synopsis="Ari gap Kai.",
    )
    db.add_all([manifest, panel, character, location, plot])
    db.flush()

    bubble = ComicSpeechBubble(
        job_id=job.id,
        analysis_revision=1,
        panel_id=panel.id,
        speaker_character_id=character.id,
        raw_text="Xin chao",
    )
    handoff = ComicSeriesHandoff(
        job_id=job.id,
        analysis_revision=1,
        approval_manifest_id=manifest.id,
    )
    db.add_all([bubble, handoff])
    db.flush()

    handoff_item = ComicSeriesHandoffItem(
        handoff_id=handoff.id,
        item_type="character",
        source_ref_id=character.id,
    )
    version_record = ComicSourceVersionRecord(
        job_id=job.id,
        handoff_id=handoff.id,
        analysis_revision=1,
        target_type="profile",
        target_id="profile-1",
    )
    db.add_all([handoff_item, version_record])
    job.analysis_revision = 1
    job.approval_manifest_id = manifest.id
    job.run_status = "ready_for_review"
    db.commit()
    job_id = job.id
    handoff_id = handoff.id

    assert service.delete_job(db, job_id) is True
    for model in (
        ComicApprovalManifest,
        ComicDetectedCharacter,
        ComicDetectedLocation,
        ComicPanel,
        ComicPlotAnalysis,
        ComicSeriesHandoff,
        ComicSourceVersionRecord,
        ComicSpeechBubble,
    ):
        assert db.query(model).filter_by(job_id=job_id).count() == 0
    assert db.query(ComicSeriesHandoffItem).filter_by(handoff_id=handoff_id).count() == 0


@pytest.mark.parametrize("run_status", ["queued", "running"])
def test_delete_job_rejects_active_run(db, run_status):
    job = service.create_url_job(db, url="https://example.com/chapter")
    job.run_status = run_status
    db.commit()

    with pytest.raises(ComicAnalysisError) as exc:
        service.delete_job(db, job.id)

    assert exc.value.status_code == 409
    assert exc.value.error_code == "COMIC_ANALYSIS_INVALID_STATE"
    assert service.get_job(db, job.id) is not None


def test_recover_interrupted_jobs(db):
    from backend.database import ComicAnalysisJob
    running = ComicAnalysisJob(source_type="url", source_url="http://x/y", run_status="running")
    queued = ComicAnalysisJob(source_type="url", source_url="http://x/z", run_status="queued")
    done = ComicAnalysisJob(source_type="url", source_url="http://x/w", run_status="ready_for_review")
    db.add_all([running, queued, done])
    db.commit()

    count = runner.recover_interrupted_jobs()
    assert count == 2
    db.expire_all()
    assert db.query(ComicAnalysisJob).filter_by(id=running.id).first().run_status == "interrupted"
    assert db.query(ComicAnalysisJob).filter_by(id=queued.id).first().run_status == "interrupted"
    assert db.query(ComicAnalysisJob).filter_by(id=done.id).first().run_status == "ready_for_review"


def test_recover_interrupted_jobs_reuses_lifecycle_session(db, monkeypatch):
    from backend.database import ComicAnalysisJob

    running = ComicAnalysisJob(source_type="url", source_url="http://x/y", run_status="running")
    db.add(running)
    db.commit()

    def fail_if_second_session_is_opened():
        raise AssertionError("startup recovery must reuse the lifecycle DB session")

    monkeypatch.setattr(database_session, "SessionLocal", fail_if_second_session_is_opened)

    count = runner.recover_interrupted_jobs(db)

    assert count == 1
    assert running.run_status == "interrupted"
    assert running.error_code == "COMIC_ANALYSIS_INVALID_STATE"


def test_rights_required_for_canon_mode(db):
    with pytest.raises(ComicAnalysisError) as exc:
        service.create_url_job(
            db, url="https://example.com/ch1",
            development_mode="bam_canon_va_phat_trien_tiep", rights_attested=False,
        )
    assert exc.value.error_code == "COMIC_RIGHTS_REQUIRED"


def test_url_job_defaults_to_write_new(db):
    job = service.create_url_job(db, url="https://example.com/ch1")
    assert job.development_mode == "lay_cam_hung_va_viet_moi"
    assert job.run_status == "draft"
    # The stored URL is redacted; raw URL kept transiently for the run.
    assert getattr(job, "_raw_url", None) == "https://example.com/ch1"

def test_schedule_run_recovers_stored_public_url_after_create_request(db, monkeypatch):
    job = service.create_url_job(db, url="https://example.com/ch1?page=2")
    job_id = job.id
    db.expunge_all()
    captured: dict[str, object] = {}

    def fake_run_job_task(scheduled_job_id, raw_url):
        captured["job_id"] = scheduled_job_id
        captured["raw_url"] = raw_url
        return object()

    monkeypatch.setattr(runner, "_run_job_task", fake_run_job_task)
    monkeypatch.setattr(runner.task_queue, "create_background_task", lambda task: captured.setdefault("task", task))

    queued = runner.schedule_run(db, job_id)

    assert queued.run_status == "queued"
    assert captured["job_id"] == job_id
    assert captured["raw_url"] == "https://example.com/ch1?page=2"

def test_job_summary_includes_vietnamese_error_message(db):
    job = service.create_url_job(db, url="https://example.com/ch1")
    job.error_code = "COMIC_NEEDS_UPLOAD"
    db.commit()

    summary = schemas.job_summary(job)

    assert summary.error_message == "Không thể tự động tải nguồn; hãy upload ảnh hoặc dán nội dung."
