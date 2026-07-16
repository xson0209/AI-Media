"""Concurrency guard for Codex-backed AI media planning work."""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from sqlalchemy.orm import Session

from . import ai_planning, video_observability

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 3
MAX_CONFIGURED_CONCURRENCY = 3
CONCURRENCY_ENV = "VOICEBOX_CODEX_PLANNING_CONCURRENCY"


class VideoPlanningPoolError(ai_planning.AIPlanningError):
    """Raised when a Codex planning job cannot enter the planning pool."""


class PlanningWorkActiveError(VideoPlanningPoolError):
    """Raised when the same workflow key already has active planning work."""

    def __init__(self, work_key: str, step_name: str, *, active_step_name: str | None = None):
        active_label = f" ({active_step_name})" if active_step_name else ""
        super().__init__(
            f"Công việc này đang có bước AI khác{active_label} chạy. Hãy chờ bước hiện tại hoàn tất rồi thử lại.",
            error_code="AI_MEDIA_PLANNING_WORK_ACTIVE",
        )
        self.work_key = work_key
        self.step_name = step_name
        self.active_step_name = active_step_name


class ProjectPlanningActiveError(PlanningWorkActiveError):
    """Backward-compatible error for duplicate AI Video project planning."""

    def __init__(self, project_id: str, step_name: str, *, active_step_name: str | None = None):
        super().__init__(project_id, step_name, active_step_name=active_step_name)
        active_label = f" ({active_step_name})" if active_step_name else ""
        self.args = (f"Dự án này đang có bước AI planning khác{active_label} đang chạy. Hãy chờ bước hiện tại hoàn tất rồi thử lại.",)
        self.error_code = "AI_VIDEO_PLANNING_PROJECT_ACTIVE"
        self.project_id = project_id


@dataclass(frozen=True)
class PlanningPoolEvent:
    project_id: str | None
    step_name: str
    max_concurrency: int
    active_count: int
    waiting_count: int
    wait_ms: float | None = None
    work_key: str = ""
    workflow_type: str = "ai_video"
    job_id: str | None = None


@dataclass(frozen=True)
class _PlanningCallbacks:
    on_wait: Callable[[PlanningPoolEvent], None] | None = None
    on_acquired: Callable[[PlanningPoolEvent], None] | None = None


_state_lock = threading.RLock()
_semaphore: threading.BoundedSemaphore | None = None
_semaphore_limit: int | None = None
_active_work: dict[str, dict[str, Any]] = {}
_active_count = 0
_waiting_count = 0
_callback_state = threading.local()


def get_max_concurrency() -> int:
    """Return configured planning concurrency, falling back safely to 3."""
    raw = os.environ.get(CONCURRENCY_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_CONCURRENCY
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MAX_CONCURRENCY
    if parsed < 1:
        return DEFAULT_MAX_CONCURRENCY
    return min(parsed, MAX_CONFIGURED_CONCURRENCY)


def _ensure_semaphore_locked() -> threading.BoundedSemaphore:
    global _semaphore, _semaphore_limit
    configured = get_max_concurrency()
    if _semaphore is None or (_semaphore_limit != configured and _active_count == 0 and _waiting_count == 0):
        _semaphore = threading.BoundedSemaphore(configured)
        _semaphore_limit = configured
    return _semaphore


def snapshot() -> PlanningPoolEvent:
    """Return a safe snapshot for resource status, tests and diagnostics."""
    with _state_lock:
        return PlanningPoolEvent(
            project_id=None,
            work_key="",
            workflow_type="all",
            step_name="snapshot",
            max_concurrency=get_max_concurrency(),
            active_count=_active_count,
            waiting_count=_waiting_count,
        )


def resource_snapshot() -> dict[str, Any]:
    with _state_lock:
        return {
            "available": True,
            "max_concurrency": get_max_concurrency(),
            "running": _active_count,
            "queued": _waiting_count,
            "running_keys": sorted(key for key, value in _active_work.items() if value.get("state") == "running"),
            "queued_keys": sorted(key for key, value in _active_work.items() if value.get("state") == "waiting"),
        }


def active_work_info(work_key: str) -> dict[str, Any] | None:
    with _state_lock:
        info = _active_work.get(work_key)
        return dict(info) if info else None


def active_project_info(project_id: str) -> dict[str, Any] | None:
    """Backward-compatible lookup for AI Video project callers."""
    return active_work_info(project_id)


def is_project_active(project_id: str) -> bool:
    return active_project_info(project_id) is not None


def reset_for_tests() -> None:
    global _semaphore, _semaphore_limit, _active_count, _waiting_count
    with _state_lock:
        _semaphore = None
        _semaphore_limit = None
        _active_work.clear()
        _active_count = 0
        _waiting_count = 0


@contextmanager
def planning_wait_callbacks(
    *,
    on_wait: Callable[[PlanningPoolEvent], None] | None = None,
    on_acquired: Callable[[PlanningPoolEvent], None] | None = None,
) -> Iterator[None]:
    """Install callbacks for the current thread while a planning step runs."""
    stack = list(getattr(_callback_state, "stack", []))
    stack.append(_PlanningCallbacks(on_wait=on_wait, on_acquired=on_acquired))
    _callback_state.stack = stack
    try:
        yield
    finally:
        stack = list(getattr(_callback_state, "stack", []))
        if stack:
            stack.pop()
        _callback_state.stack = stack


def _current_callbacks() -> _PlanningCallbacks:
    stack = getattr(_callback_state, "stack", [])
    return stack[-1] if stack else _PlanningCallbacks()


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (details or {}).items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in ("secret", "token", "api_key", "apikey", "password", "cookie")):
            safe[key] = "[redacted]"
        elif isinstance(value, str):
            safe[key] = f"{value[:160]}...[truncated]" if len(value) > 160 else value
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [str(item)[:80] for item in value[:20]]
        elif isinstance(value, dict):
            safe[key] = {str(k)[:80]: str(v)[:120] for k, v in list(value.items())[:20]}
        else:
            safe[key] = str(value)[:120]
    return safe


def _event_details(details: dict[str, Any] | None, event: PlanningPoolEvent | None = None, **extra: Any) -> dict[str, Any]:
    payload = _safe_details(details)
    if event is not None:
        payload.update(event.__dict__)
    payload.update(_safe_details(extra))
    return payload


def _log_event_safely(db: Session, **kwargs: Any) -> None:
    try:
        video_observability.log_event(
            db,
            step_name=kwargs["event_name"],
            status=kwargs["status"],
            project_id=kwargs.get("project_id"),
            provider=kwargs.get("provider"),
            model=kwargs.get("model"),
            duration_ms=kwargs.get("duration_ms"),
            error_code=kwargs.get("error_code"),
            message=kwargs.get("message"),
            technical_details=_safe_details(kwargs.get("details")),
        )
    except Exception:
        logger.exception(
            "Failed to write planning pool debug event",
            extra={"work_key": kwargs.get("work_key"), "step_name": kwargs.get("step_name")},
        )


def _run_callback_safely(
    callback: Callable[[PlanningPoolEvent], None] | None,
    event: PlanningPoolEvent,
) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        logger.exception("Planning pool callback failed", extra={"work_key": event.work_key})


@contextmanager
def planning_slot(
    db: Session,
    *,
    project_id: str | None = None,
    work_key: str | None = None,
    workflow_type: str = "ai_video",
    job_id: str | None = None,
    step_name: str,
    provider: str | None = None,
    model: str | None = None,
    details: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Acquire a global planning slot and a per-project/job planning lock."""
    global _active_count, _waiting_count

    resolved_key = (work_key or project_id or job_id or "").strip()
    if not resolved_key:
        raise VideoPlanningPoolError("Thiếu mã công việc để xếp lịch AI planning.", error_code="AI_MEDIA_PLANNING_WORK_KEY_REQUIRED")

    started_wait = time.perf_counter()
    acquired = False
    registered = False
    release_status = "failure"
    release_message = "AI planning đã trả slot sau lỗi chưa xác định."
    release_error_code: str | None = "CODEX_PLANNING_FAILED"
    callbacks = _current_callbacks()

    with _state_lock:
        semaphore = _ensure_semaphore_locked()
        max_concurrency = _semaphore_limit or get_max_concurrency()
        if resolved_key in _active_work:
            active_info = dict(_active_work.get(resolved_key) or {})
            active_step_name = active_info.get("step_name")
            duplicate_error: PlanningWorkActiveError
            if project_id is not None and work_key is None:
                duplicate_error = ProjectPlanningActiveError(project_id, step_name, active_step_name=active_step_name)
            else:
                duplicate_error = PlanningWorkActiveError(resolved_key, step_name, active_step_name=active_step_name)
            duplicate_event = PlanningPoolEvent(
                project_id=project_id,
                work_key=resolved_key,
                workflow_type=workflow_type,
                job_id=job_id,
                step_name=step_name,
                max_concurrency=max_concurrency,
                active_count=_active_count,
                waiting_count=_waiting_count,
            )
            _log_event_safely(
                db,
                event_name="codex_planning_rejected",
                status="failure",
                project_id=project_id,
                work_key=resolved_key,
                step_name=step_name,
                provider=provider,
                model=model,
                error_code=duplicate_error.error_code,
                message=str(duplicate_error),
                details=_event_details(details, duplicate_event, active_work=active_info),
            )
            raise duplicate_error
        _active_work[resolved_key] = {
            "step_name": step_name,
            "state": "waiting",
            "started_at": time.time(),
            "workflow_type": workflow_type,
            "project_id": project_id,
            "job_id": job_id,
        }
        registered = True
        _waiting_count += 1

    try:
        acquired = semaphore.acquire(blocking=False)
        if not acquired:
            with _state_lock:
                wait_event = PlanningPoolEvent(
                    project_id=project_id,
                    work_key=resolved_key,
                    workflow_type=workflow_type,
                    job_id=job_id,
                    step_name=step_name,
                    max_concurrency=max_concurrency,
                    active_count=_active_count,
                    waiting_count=_waiting_count,
                )
            _log_event_safely(
                db,
                event_name="codex_planning_waiting",
                status="waiting",
                project_id=project_id,
                work_key=resolved_key,
                step_name=step_name,
                provider=provider,
                model=model,
                message="AI planning đang chờ slot trống.",
                details=_event_details(details, wait_event),
            )
            _run_callback_safely(callbacks.on_wait, wait_event)
            semaphore.acquire()
        acquired = True
        wait_ms = round((time.perf_counter() - started_wait) * 1000, 2)
        with _state_lock:
            _waiting_count = max(0, _waiting_count - 1)
            _active_count += 1
            _active_work[resolved_key] = {
                "step_name": step_name,
                "state": "running",
                "started_at": time.time(),
                "workflow_type": workflow_type,
                "project_id": project_id,
                "job_id": job_id,
            }
            acquired_event = PlanningPoolEvent(
                project_id=project_id,
                work_key=resolved_key,
                workflow_type=workflow_type,
                job_id=job_id,
                step_name=step_name,
                max_concurrency=max_concurrency,
                active_count=_active_count,
                waiting_count=_waiting_count,
                wait_ms=wait_ms,
            )
        _run_callback_safely(callbacks.on_acquired, acquired_event)
        _log_event_safely(
            db,
            event_name="codex_planning_acquired",
            status="start",
            project_id=project_id,
            work_key=resolved_key,
            step_name=step_name,
            provider=provider,
            model=model,
            duration_ms=wait_ms,
            message="AI planning đã lấy slot.",
            details=_event_details(details, acquired_event),
        )
        yield
        _log_event_safely(
            db,
            event_name="codex_planning_completed",
            status="success",
            project_id=project_id,
            work_key=resolved_key,
            step_name=step_name,
            provider=provider,
            model=model,
            message="AI planning hoàn tất.",
            details=_event_details(details, acquired_event),
        )
        release_status = "success"
        release_message = "AI planning đã trả slot."
        release_error_code = None
    except Exception as exc:
        release_error_code = getattr(exc, "error_code", "CODEX_PLANNING_FAILED")
        if acquired:
            _log_event_safely(
                db,
                event_name="codex_planning_error",
                status="failure",
                project_id=project_id,
                work_key=resolved_key,
                step_name=step_name,
                provider=provider,
                model=model,
                error_code=release_error_code,
                message=str(exc),
                details=_event_details(details, None, error_class=exc.__class__.__name__),
            )
        raise
    finally:
        if acquired:
            semaphore.release()
        if registered:
            with _state_lock:
                _active_work.pop(resolved_key, None)
                if acquired:
                    _active_count = max(0, _active_count - 1)
                else:
                    _waiting_count = max(0, _waiting_count - 1)
                released_event = PlanningPoolEvent(
                    project_id=project_id,
                    work_key=resolved_key,
                    workflow_type=workflow_type,
                    job_id=job_id,
                    step_name=step_name,
                    max_concurrency=max_concurrency,
                    active_count=_active_count,
                    waiting_count=_waiting_count,
                )
            if acquired:
                _log_event_safely(
                    db,
                    event_name="codex_planning_released",
                    status=release_status,
                    project_id=project_id,
                    work_key=resolved_key,
                    step_name=step_name,
                    provider=provider,
                    model=model,
                    error_code=release_error_code,
                    message=release_message,
                    details=_event_details(details, released_event),
                )
