"""Background runner for Comic Series Analysis (§7).

Schedules the ingestion pipeline on a dedicated background task with its own
DB session (never reusing the request session across threads/tasks, task
7.1), coordinated through the shared workflow pool under a comic-specific
work key ``comic-series-analysis:<job_id>`` (task 7.2). Provides cancel,
retry and startup recovery for interrupted jobs (task 7.9).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ...database import ComicAnalysisJob as DBJob, session as db_session
from ...services import task_queue, video_workflow_pool
from . import config as comic_config
from . import service, url_security
from .contracts import ACTIVE_RUN_STATUSES, ComicAnalysisError

logger = logging.getLogger(__name__)

WORKFLOW_TYPE = "comic_series_analysis"

# Cooperative cancellation: job ids the user asked to cancel.
_cancel_requested: set[str] = set()


def work_key(job_id: str) -> str:
    return f"comic-series-analysis:{job_id}"


def _stored_runnable_url(job: DBJob) -> str | None:
    """Recover a public URL persisted for a later run request."""
    stored_url = (job.source_url or "").strip()
    if not stored_url or "<redacted>" in stored_url:
        return None
    try:
        url_security.validate_url(stored_url)
    except ComicAnalysisError:
        return None
    return stored_url

def request_cancel(db: Session, job_id: str) -> DBJob | None:
    """Cooperatively cancel a job; stops before the next heavy step."""
    job = service.get_job(db, job_id)
    if job is None:
        return None
    _cancel_requested.add(job_id)
    if job.run_status in ("draft", "queued"):
        job.run_status = "cancelled"
        db.commit()
        db.refresh(job)
    return job


def is_cancelled(job_id: str) -> bool:
    return job_id in _cancel_requested


def schedule_run(db: Session, job_id: str) -> DBJob:
    """Queue a job's ingestion run and return immediately (HTTP 202, task 7.5)."""
    if not comic_config.is_feature_enabled():
        raise ComicAnalysisError("COMIC_ANALYSIS_DISABLED", status_code=403)
    job = service.get_job(db, job_id)
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)
    if job.run_status in ACTIVE_RUN_STATUSES:
        raise ComicAnalysisError("COMIC_ANALYSIS_ALREADY_RUNNING", status_code=409)
    if job.source_type != "url":
        # Upload jobs are ingested synchronously at creation; nothing to run.
        raise ComicAnalysisError("COMIC_ANALYSIS_INVALID_STATE", "Job này không cần chạy fetch.")

    raw_url = getattr(job, "_raw_url", None) or _stored_runnable_url(job)
    job.run_status = "queued"
    job.current_step = "validate_source"
    job.progress = 0.0
    job.error_code = None
    job.outcome_code = None
    _cancel_requested.discard(job_id)
    db.commit()
    db.refresh(job)

    task_queue.create_background_task(_run_job_task(job_id, raw_url))
    return job


async def _run_job_task(job_id: str, raw_url: str | None) -> None:
    """Background entrypoint: own DB session, own work-key slot."""
    try:
        async with video_workflow_pool.workflow_slot(
            work_key=work_key(job_id),
            workflow_type=WORKFLOW_TYPE,
            operation_name="ingest",
        ):
            _execute_run(job_id, raw_url)
    except video_workflow_pool.WorkflowAlreadyActiveError:
        logger.info("Comic job %s already active; skipping duplicate run", job_id)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Comic job %s run failed", job_id)
        _mark_failed(job_id, "COMIC_NEEDS_UPLOAD")


def _execute_run(job_id: str, raw_url: str | None) -> None:
    db = db_session.SessionLocal()
    try:
        job = service.get_job(db, job_id)
        if job is None:
            return
        if is_cancelled(job_id):
            job.run_status = "cancelled"
            db.commit()
            return
        raw_url = raw_url or _stored_runnable_url(job)
        if not raw_url:
            # Recover the raw URL is impossible from a redacted DB value; the
            # run must have the original. If missing, mark needs-upload.
            _mark_failed(job_id, "COMIC_NEEDS_UPLOAD", db=db)
            return
        try:
            service.run_url_ingestion(db, job, raw_url)
        except ComicAnalysisError as exc:
            job = service.get_job(db, job_id)
            if job is not None:
                job.run_status = "failed"
                job.error_code = exc.error_code
                job.result_completeness = "unavailable"
                db.commit()
    finally:
        _cancel_requested.discard(job_id)
        db.close()


def _mark_failed(job_id: str, error_code: str, *, db: Session | None = None) -> None:
    owns = db is None
    session = db or db_session.SessionLocal()
    try:
        job = service.get_job(session, job_id)
        if job is not None:
            job.run_status = "failed"
            job.error_code = error_code
            job.result_completeness = "unavailable"
            session.commit()
    finally:
        if owns:
            session.close()


def recover_interrupted_jobs(db: Session | None = None) -> int:
    """On startup, mark active jobs with no runtime task as interrupted (task 7.9).

    Called during app lifecycle. A queued/running job in the DB after a
    restart cannot have a live task, so it becomes ``interrupted`` (retryable)
    rather than being assumed alive.
    """
    if db_session.SessionLocal is None:
        return 0
    owns_session = db is None
    db = db or db_session.SessionLocal()
    count = 0
    try:
        stale = (
            db.query(DBJob)
            .filter(DBJob.run_status.in_(tuple(ACTIVE_RUN_STATUSES)))
            .all()
        )
        for job in stale:
            job.run_status = "interrupted"
            job.error_code = "COMIC_ANALYSIS_INVALID_STATE"
            count += 1
        if count and owns_session:
            db.commit()
            logger.info("Recovered %d interrupted comic jobs", count)
    finally:
        if owns_session:
            db.close()
    return count


def retry_job(db: Session, job_id: str) -> DBJob:
    """Retry a failed/interrupted/partial job (reuses valid artifacts, task 7.12)."""
    job = service.get_job(db, job_id)
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)
    if job.run_status in ACTIVE_RUN_STATUSES:
        raise ComicAnalysisError("COMIC_ANALYSIS_ALREADY_RUNNING", status_code=409)
    return schedule_run(db, job_id)


__all__ = [
    "WORKFLOW_TYPE",
    "recover_interrupted_jobs",
    "request_cancel",
    "retry_job",
    "schedule_run",
    "work_key",
]
