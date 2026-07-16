"""Background execution and resource gates for Video Inspiration jobs."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import weakref
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, TypeVar

from sqlalchemy.orm import Session

from .. import models
from ..database import VideoInspirationJob as DBVideoInspirationJob, get_db
from . import video_inspiration, video_workflow_pool
from .task_queue import create_background_task

logger = logging.getLogger(__name__)

VideoInspirationOperation = Literal["analyze", "rewrite"]

STT_CONCURRENCY_ENV = "VOICEBOX_VIDEO_INSPIRATION_STT_CONCURRENCY"
DEFAULT_STT_CONCURRENCY = 1
MAX_STT_CONCURRENCY = 1

_T = TypeVar("_T")


@dataclass
class _RunHandle:
    job_id: str
    operation: VideoInspirationOperation
    cancel_event: threading.Event
    task: asyncio.Task | None = None


_run_lock = threading.RLock()
_active_runs: dict[str, _RunHandle] = {}
_stt_lock = threading.RLock()
_stt_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)
_stt_running_keys: set[str] = set()
_stt_queued_keys: list[str] = []


def get_stt_max_concurrency() -> int:
    """Return the bounded number of concurrent Video Inspiration STT jobs."""
    raw = os.environ.get(STT_CONCURRENCY_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_STT_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_STT_CONCURRENCY
    return max(1, min(MAX_STT_CONCURRENCY, value))


def _stt_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    with _stt_lock:
        semaphore = _stt_semaphores.get(loop)
        if semaphore is None:
            semaphore = asyncio.Semaphore(get_stt_max_concurrency())
            _stt_semaphores[loop] = semaphore
        return semaphore


async def run_with_stt_slot(
    factory: Callable[[], Awaitable[_T]],
    *,
    work_key: str | None = None,
) -> _T:
    """Run one STT operation through the process-wide, per-loop STT gate."""
    key = (work_key or f"video-inspiration-stt:{id(factory)}").strip()
    semaphore = _stt_semaphore()
    with _stt_lock:
        _stt_queued_keys.append(key)
    acquired = False
    try:
        await semaphore.acquire()
        acquired = True
        with _stt_lock:
            if key in _stt_queued_keys:
                _stt_queued_keys.remove(key)
            _stt_running_keys.add(key)
        return await factory()
    finally:
        with _stt_lock:
            if key in _stt_queued_keys:
                _stt_queued_keys.remove(key)
            _stt_running_keys.discard(key)
        if acquired:
            semaphore.release()


def get_stt_pool_snapshot() -> dict[str, object]:
    """Return safe STT counters for resource status and Vietnamese queue UI."""
    with _stt_lock:
        return {
            "available": True,
            "max_concurrency": get_stt_max_concurrency(),
            "running": len(_stt_running_keys),
            "queued": len(_stt_queued_keys),
            "running_keys": sorted(_stt_running_keys),
            "queued_keys": list(_stt_queued_keys),
        }


def _row(job_id: str, db: Session) -> DBVideoInspirationJob | None:
    return db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()


def _active_error(job_id: str, operation: VideoInspirationOperation) -> video_inspiration.VideoInspirationError:
    label = "phân tích video" if operation == "analyze" else "viết kịch bản tối ưu"
    return video_inspiration.VideoInspirationError(
        f"Job này đang chạy tác vụ {label}. Hãy chờ tác vụ hiện tại hoàn tất hoặc bấm hủy trước khi chạy lại.",
        error_code="VIDEO_INSPIRATION_JOB_ACTIVE",
        status_code=409,
    )


def _mark_interrupted(row: DBVideoInspirationJob, db: Session) -> None:
    video_inspiration._set_job_state(
        row,
        db,
        status="failed",
        step="interrupted",
        progress=float(row.progress or 0.0),
        failure_reason="Tác vụ Video Inspiration bị gián đoạn khi backend dừng hoặc khởi động lại. Hãy bấm chạy lại để tiếp tục.",
        error_code="VIDEO_INSPIRATION_INTERRUPTED",
    )


def _mark_cancelled(row: DBVideoInspirationJob, db: Session) -> None:
    video_inspiration._set_job_state(
        row,
        db,
        status="cancelled",
        step="cancelled",
        progress=float(row.progress or 0.0),
        failure_reason="Đã hủy tác vụ Video Inspiration theo yêu cầu.",
        error_code="VIDEO_INSPIRATION_CANCELLED",
    )


def _prepare_schedule(
    job_id: str,
    operation: VideoInspirationOperation,
    db: Session,
) -> tuple[DBVideoInspirationJob, _RunHandle]:
    row = _row(job_id, db)
    if row is None:
        raise video_inspiration.VideoInspirationError(
            "Không tìm thấy job video cảm hứng.",
            error_code="VIDEO_INSPIRATION_NOT_FOUND",
            status_code=404,
        )

    with _run_lock:
        existing = _active_runs.get(job_id)
        if existing is not None:
            raise _active_error(job_id, existing.operation)

        if row.status in video_inspiration.ACTIVE_JOB_STATUSES:
            if video_inspiration._active_job_stale(row):
                _mark_interrupted(row, db)
            else:
                current_operation: VideoInspirationOperation = (
                    "rewrite" if row.status == "rewriting" else "analyze"
                )
                raise _active_error(job_id, current_operation)

        if operation == "analyze":
            video_inspiration._resolve_source(row)
        elif not row.analysis_json:
            raise video_inspiration.VideoInspirationError(
                "Cần phân tích video trước khi viết kịch bản tối ưu.",
                error_code="VIDEO_INSPIRATION_ANALYSIS_REQUIRED",
            )

        handle = _RunHandle(
            job_id=job_id,
            operation=operation,
            cancel_event=threading.Event(),
        )
        _active_runs[job_id] = handle

    return row, handle


def _schedule_state(row: DBVideoInspirationJob, operation: VideoInspirationOperation, db: Session) -> None:
    if operation == "analyze":
        video_inspiration._set_job_state(
            row,
            db,
            status="analyzing",
            step="queued_analysis",
            progress=max(0.10, min(float(row.progress or 0.0), 0.15)),
        )
    else:
        video_inspiration._set_job_state(
            row,
            db,
            status="rewriting",
            step="queued_rewrite",
            progress=max(float(row.progress or 0.0), 0.90),
        )


def schedule_analyze(
    job_id: str,
    data: models.VideoInspirationAnalyzeRequest,
    db: Session,
) -> models.VideoInspirationJobResponse:
    """Schedule analysis and return the queued job without waiting for media/AI work."""
    row, handle = _prepare_schedule(job_id, "analyze", db)
    try:
        _schedule_state(row, "analyze", db)
        payload = data.model_dump()
        handle.task = create_background_task(_run_analyze(handle, payload))
    except BaseException:
        with _run_lock:
            if _active_runs.get(job_id) is handle:
                _active_runs.pop(job_id, None)
        raise
    response = video_inspiration.get_job(job_id, db)
    assert response is not None
    return response


def schedule_rewrite(
    job_id: str,
    data: models.VideoInspirationRewriteRequest,
    db: Session,
) -> models.VideoInspirationJobResponse:
    """Schedule rewrite and return the queued job without waiting for Codex."""
    row, handle = _prepare_schedule(job_id, "rewrite", db)
    try:
        _schedule_state(row, "rewrite", db)
        payload = data.model_dump()
        handle.task = create_background_task(_run_rewrite(handle, payload))
    except BaseException:
        with _run_lock:
            if _active_runs.get(job_id) is handle:
                _active_runs.pop(job_id, None)
        raise
    response = video_inspiration.get_job(job_id, db)
    assert response is not None
    return response


async def _run_analyze(handle: _RunHandle, payload: dict) -> None:
    try:
        async with video_workflow_pool.workflow_slot(
            work_key=f"video-inspiration:{handle.job_id}",
            workflow_type="video_inspiration",
            operation_name="analyze",
        ):
            db_iter = get_db()
            db = next(db_iter)
            try:
                data = models.VideoInspirationAnalyzeRequest(**payload)

                async def stt_runner(factory: Callable[[], Awaitable[_T]]) -> _T:
                    return await run_with_stt_slot(
                        factory,
                        work_key=f"video-inspiration:{handle.job_id}",
                    )

                await video_inspiration.analyze_job(
                    handle.job_id,
                    data,
                    db,
                    cancel_requested=handle.cancel_event.is_set,
                    stt_runner=stt_runner,
                )
                if handle.cancel_event.is_set():
                    row = _row(handle.job_id, db)
                    if row is not None:
                        _mark_cancelled(row, db)
            finally:
                db_iter.close()
    except asyncio.CancelledError:
        _mark_cancelled_by_id(handle.job_id)
        raise
    except Exception as exc:
        logger.exception("Video Inspiration analysis background task failed", extra={"job_id": handle.job_id})
        _mark_failed_by_id(handle.job_id, exc)
    finally:
        _release_handle(handle)


def _run_rewrite_sync(handle: _RunHandle, payload: dict) -> None:
    db_iter = get_db()
    db = next(db_iter)
    try:
        data = models.VideoInspirationRewriteRequest(**payload)
        video_inspiration.rewrite_job(
            handle.job_id,
            data,
            db,
            cancel_requested=handle.cancel_event.is_set,
        )
        if handle.cancel_event.is_set():
            row = _row(handle.job_id, db)
            if row is not None:
                _mark_cancelled(row, db)
    finally:
        db_iter.close()


async def _run_rewrite(handle: _RunHandle, payload: dict) -> None:
    try:
        async with video_workflow_pool.workflow_slot(
            work_key=f"video-inspiration:{handle.job_id}",
            workflow_type="video_inspiration",
            operation_name="rewrite",
        ):
            await asyncio.to_thread(_run_rewrite_sync, handle, payload)
    except asyncio.CancelledError:
        handle.cancel_event.set()
        _mark_cancelled_by_id(handle.job_id)
        raise
    except Exception as exc:
        logger.exception("Video Inspiration rewrite background task failed", extra={"job_id": handle.job_id})
        _mark_failed_by_id(handle.job_id, exc)
    finally:
        _release_handle(handle)


def _release_handle(handle: _RunHandle) -> None:
    with _run_lock:
        if _active_runs.get(handle.job_id) is handle:
            _active_runs.pop(handle.job_id, None)


def _mark_cancelled_by_id(job_id: str) -> None:
    db_iter = get_db()
    db = next(db_iter)
    try:
        row = _row(job_id, db)
        if row is not None:
            _mark_cancelled(row, db)
    finally:
        db_iter.close()


def _mark_failed_by_id(job_id: str, exc: BaseException) -> None:
    db_iter = get_db()
    db = next(db_iter)
    try:
        row = _row(job_id, db)
        if row is not None and row.status in video_inspiration.ACTIVE_JOB_STATUSES:
            video_inspiration._fail_job(row, db, exc)
    finally:
        db_iter.close()


def cancel_job(job_id: str, db: Session) -> models.VideoInspirationJobResponse | None:
    """Request cooperative cancellation and expose a terminal Vietnamese status immediately."""
    row = _row(job_id, db)
    if row is None:
        return None
    with _run_lock:
        handle = _active_runs.get(job_id)
        if handle is not None:
            handle.cancel_event.set()
    video_workflow_pool.cancel_waiting(f"video-inspiration:{job_id}")
    if handle is not None or row.status in video_inspiration.ACTIVE_JOB_STATUSES:
        _mark_cancelled(row, db)
    return video_inspiration.get_job(job_id, db)


def retry_job(
    job_id: str,
    db: Session,
    *,
    operation: VideoInspirationOperation | None = None,
) -> models.VideoInspirationJobResponse | None:
    """Retry the requested stage, or infer rewrite only when analysis already exists."""
    row = _row(job_id, db)
    if row is None:
        return None
    selected = operation or ("rewrite" if row.analysis_json else "analyze")
    if selected == "rewrite":
        return schedule_rewrite(
            job_id,
            models.VideoInspirationRewriteRequest(
                target_language=row.target_language,
                user_direction=row.user_direction,
            ),
            db,
        )
    return schedule_analyze(
        job_id,
        models.VideoInspirationAnalyzeRequest(
            analysis_mode=row.analysis_mode or "quick",
        ),
        db,
    )


def sync_interrupted_jobs(db: Session) -> int:
    """Mark jobs left active by a previous backend process as retryable failures."""
    rows = (
        db.query(DBVideoInspirationJob)
        .filter(DBVideoInspirationJob.status.in_(video_inspiration.ACTIVE_JOB_STATUSES))
        .all()
    )
    for row in rows:
        _mark_interrupted(row, db)
    return len(rows)


def active_snapshot() -> dict[str, dict[str, str]]:
    with _run_lock:
        return {
            job_id: {"operation": handle.operation}
            for job_id, handle in _active_runs.items()
        }


def reset_for_tests() -> None:
    """Clear in-memory runner/gate state. Intended for focused tests only."""
    with _run_lock:
        handles = list(_active_runs.values())
        _active_runs.clear()
    for handle in handles:
        handle.cancel_event.set()
        if handle.task is not None and not handle.task.done():
            handle.task.cancel()
    with _stt_lock:
        _stt_semaphores.clear()
        _stt_running_keys.clear()
        _stt_queued_keys.clear()
