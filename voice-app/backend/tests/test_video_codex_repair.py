from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import (
    Base,
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoProject as DBVideoProject,
)
from backend.services import video_codex_repair, video_veo_chrome


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repair.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    return engine, session


def _job_and_item(db, *, enable_codex_repair: bool = True):
    project = DBVideoProject(
        title="Video",
        topic="Topic",
        phase="phase2",
        package_stale=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    job = DBVideoClipGenerationJob(
        project_id=project.id,
        session_id="session-1",
        status="running",
        current_step="waiting_generation",
        enable_codex_repair=enable_codex_repair,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    item = DBVideoClipGenerationItem(
        job_id=job.id,
        project_id=project.id,
        shot_id="shot-1",
        shot_order=1,
        status="waiting_generation",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return job, item


def test_codex_repair_allowlist_creates_redacted_attempt(tmp_path, monkeypatch):
    engine, db = _db(tmp_path)
    try:
        monkeypatch.delenv(video_codex_repair.REPAIR_AUTORUN_ENV, raising=False)
        job, item = _job_and_item(db)
        error = video_veo_chrome.VeoChromeError(
            "selector failed with cookie token and a very long DOM",
            error_code="VIDEO_PROVIDER_UI_CHANGED",
            details={"cookie": "secret", "download_correlation_id": "download-1"},
        )

        attempt = video_codex_repair.create_repair_attempt(job, item, error, db)

        assert attempt is not None
        assert attempt.status == "approval_required"
        assert attempt.requires_approval is True
        dumped = str(attempt.repair_context_json)
        assert "secret" not in dumped
        assert "download-1" in dumped
    finally:
        db.close()
        engine.dispose()


def test_codex_repair_denylist_and_unknown_do_not_create_attempt(tmp_path):
    engine, db = _db(tmp_path)
    try:
        job, item = _job_and_item(db)
        denied = video_veo_chrome.VeoChromeError("quota", error_code="VIDEO_PROVIDER_MODEL_QUOTA_EXHAUSTED")
        unknown = video_veo_chrome.VeoChromeError("unknown", error_code="VIDEO_PROVIDER_UNKNOWN")

        assert video_codex_repair.create_repair_attempt(job, item, denied, db) is None
        assert video_codex_repair.create_repair_attempt(job, item, unknown, db) is None
    finally:
        db.close()
        engine.dispose()
