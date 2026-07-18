import asyncio
import threading
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import config, database, models
from backend.database import VideoInspirationJob as DBVideoInspirationJob
from backend.database import session as database_session
from backend.routes import video_inspiration as video_inspiration_routes
from backend.services import (
    video_inspiration,
    video_inspiration_runs,
    video_planning_pool,
    video_workflow_pool,
)


class _DummyTask:
    def done(self):
        return True

    def cancel(self):
        return None


@pytest.fixture
def db(tmp_path):
    config.set_data_dir(tmp_path)
    database.init_db()
    video_inspiration_runs.reset_for_tests()
    video_workflow_pool.reset_for_tests()
    video_planning_pool.reset_for_tests()
    session = database_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        video_inspiration_runs.reset_for_tests()
        video_workflow_pool.reset_for_tests()
        video_planning_pool.reset_for_tests()
        database_session.engine.dispose()


def _job(db, tmp_path, *, job_id="background-job", analysis=False):
    source = tmp_path / f"{job_id}.mp4"
    source.write_bytes(b"video")
    row = DBVideoInspirationJob(
        id=job_id,
        source_type="upload",
        source_platform="upload",
        source_path=config.to_storage_path(source),
        status="analyzed" if analysis else "uploaded",
        current_step="completed" if analysis else "source_ready",
        progress=0.88 if analysis else 0.08,
        target_language="vi",
        analysis_mode="quick",
        analysis_json={"main_idea_vi": "Ý chính"} if analysis else None,
        transcript_text="Transcript" if analysis else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return row


def _capture_background(monkeypatch):
    coroutines = []

    def fake_background(coro):
        coroutines.append(coro)
        coro.close()
        return _DummyTask()

    monkeypatch.setattr(video_inspiration_runs, "create_background_task", fake_background)
    return coroutines


def test_schedule_analyze_returns_queued_and_rejects_duplicate(db, tmp_path, monkeypatch):
    row = _job(db, tmp_path)
    captured = _capture_background(monkeypatch)

    response = video_inspiration_runs.schedule_analyze(
        row.id,
        models.VideoInspirationAnalyzeRequest(),
        db,
    )

    assert response.status == "analyzing"
    assert response.current_step == "queued_analysis"
    assert len(captured) == 1

    with pytest.raises(video_inspiration.VideoInspirationError) as exc_info:
        video_inspiration_runs.schedule_analyze(
            row.id,
            models.VideoInspirationAnalyzeRequest(),
            db,
        )

    assert exc_info.value.error_code == "VIDEO_INSPIRATION_JOB_ACTIVE"
    assert exc_info.value.status_code == 409


def test_analyze_and_rewrite_endpoints_return_202_after_scheduling(db, tmp_path, monkeypatch):
    analyze_row = _job(db, tmp_path, job_id="route-analyze")
    rewrite_row = _job(db, tmp_path, job_id="route-rewrite", analysis=True)
    captured = _capture_background(monkeypatch)
    app = FastAPI()
    app.dependency_overrides[video_inspiration_routes.get_db] = lambda: db
    app.include_router(video_inspiration_routes.router)

    with TestClient(app) as client:
        analyze_response = client.post(f"/video-inspiration/jobs/{analyze_row.id}/analyze", json={})
        rewrite_response = client.post(f"/video-inspiration/jobs/{rewrite_row.id}/rewrite", json={})

    assert analyze_response.status_code == 202
    assert analyze_response.json()["current_step"] == "queued_analysis"
    assert rewrite_response.status_code == 202
    assert rewrite_response.json()["current_step"] == "queued_rewrite"
    assert len(captured) == 2


def test_cancel_marks_active_job_terminal_immediately(db, tmp_path, monkeypatch):
    row = _job(db, tmp_path)
    _capture_background(monkeypatch)
    video_inspiration_runs.schedule_analyze(row.id, models.VideoInspirationAnalyzeRequest(), db)

    response = video_inspiration_runs.cancel_job(row.id, db)

    assert response is not None
    assert response.status == "cancelled"
    assert response.current_step == "cancelled"
    assert response.error_code == "VIDEO_INSPIRATION_CANCELLED"
    assert "Đã hủy" in (response.failure_reason or "")


def test_retry_infers_rewrite_when_analysis_exists(db, tmp_path, monkeypatch):
    row = _job(db, tmp_path, analysis=True)
    row.status = "failed"
    row.current_step = "failed"
    db.commit()
    _capture_background(monkeypatch)

    response = video_inspiration_runs.retry_job(row.id, db)

    assert response is not None
    assert response.status == "rewriting"
    assert response.current_step == "queued_rewrite"


def test_startup_recovery_marks_active_jobs_interrupted(db, tmp_path):
    row = _job(db, tmp_path)
    row.status = "analyzing"
    row.current_step = "content_analysis"
    db.commit()

    changed = video_inspiration_runs.sync_interrupted_jobs(db)

    db.refresh(row)
    assert changed == 1
    assert row.status == "failed"
    assert row.current_step == "interrupted"
    assert row.error_code == "VIDEO_INSPIRATION_INTERRUPTED"
    assert "khởi động lại" in (row.failure_reason or "")


def test_background_analyze_uses_a_fresh_database_session(db, tmp_path, monkeypatch):
    row = _job(db, tmp_path)
    request_session = db
    seen = {}

    async def fake_analyze(job_id, data, session, **kwargs):
        seen["fresh"] = session is not request_session
        worker_row = session.query(DBVideoInspirationJob).filter_by(id=job_id).one()
        worker_row.status = "analyzed"
        worker_row.current_step = "completed"
        session.commit()
        return video_inspiration.get_job(job_id, session)

    monkeypatch.setattr(video_inspiration, "analyze_job", fake_analyze)
    handle = video_inspiration_runs._RunHandle(
        job_id=row.id,
        operation="analyze",
        cancel_event=threading.Event(),
    )

    asyncio.run(video_inspiration_runs._run_analyze(handle, models.VideoInspirationAnalyzeRequest().model_dump()))

    db.expire_all()
    assert seen == {"fresh": True}
    assert db.query(DBVideoInspirationJob).filter_by(id=row.id).one().status == "analyzed"


def test_stt_gate_defaults_to_one_active_job(monkeypatch):
    monkeypatch.delenv(video_inspiration_runs.STT_CONCURRENCY_ENV, raising=False)
    video_inspiration_runs.reset_for_tests()

    async def scenario():
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release = asyncio.Event()
        running = 0
        peak = 0

        async def body(started):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            started.set()
            await release.wait()
            running -= 1

        first = asyncio.create_task(
            video_inspiration_runs.run_with_stt_slot(lambda: body(first_started))
        )
        await asyncio.wait_for(first_started.wait(), timeout=1)
        second = asyncio.create_task(
            video_inspiration_runs.run_with_stt_slot(lambda: body(second_started))
        )
        await asyncio.sleep(0.05)
        assert not second_started.is_set()
        release.set()
        await asyncio.gather(first, second)
        return peak

    assert asyncio.run(scenario()) == 1


def test_stt_concurrency_env_cannot_raise_hard_cap_above_one(monkeypatch):
    monkeypatch.setenv(video_inspiration_runs.STT_CONCURRENCY_ENV, "99")

    assert video_inspiration_runs.get_stt_max_concurrency() == 1
    assert video_inspiration_runs.get_stt_pool_snapshot()["max_concurrency"] == 1


def test_structured_codex_helper_runs_off_event_loop_thread(monkeypatch):
    event_loop_thread = threading.get_ident()
    worker_threads = []

    def fake_run(session, prompt, schema, *, timeout_seconds=600):
        worker_threads.append(threading.get_ident())
        return {"ok": True}

    monkeypatch.setattr(video_inspiration, "_run_structured_ai", fake_run)

    result = asyncio.run(
        video_inspiration._run_structured_ai_in_thread(
            object(),
            "prompt",
            {"type": "object"},
        )
    )

    assert result == {"ok": True}
    assert worker_threads and worker_threads[0] != event_loop_thread
