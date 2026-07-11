"""Concurrency guard for Codex-backed AI Video planning work."""

from __future__ import annotations

import os
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from sqlalchemy.orm import Session

from . import ai_planning, video_observability

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 3
MAX_CONFIGURED_CONCURRENCY = 8
CONCURRENCY_ENV = "VOICEBOX_CODEX_PLANNING_CONCURRENCY"


class VideoPlanningPoolError(ai_planning.AIPlanningError):
    """Raised when a Codex planning job cannot enter the planning pool."""


class ProjectPlanningActiveError(VideoPlanningPoolError):
    """Raised when the same project already has an active planning job."""

    def __init__(self, project_id: str, step_name: str, *, active_step_name: str | None = None):
        active_label = f" ({active_step_name})" if active_step_name else ""
        super().__init__(
            f"Dự án này đang có bước AI planning khác{active_label} đang chạy. Hãy chờ bước hiện tại hoàn tất rồi thử lại.",
            error_code="AI_VIDEO_PLANNING_PROJECT_ACTIVE",
        )
        self.project_id = project_id
        self.step_name = step_name
        self.active_step_name = active_step_name


@dataclass(frozen=True)
class PlanningPoolEvent:
    project_id: str
    step_name: str
    max_concurrency: int
    active_count: int
    waiting_count: int
    wait_ms: float | None = None


@dataclass(frozen=True)
class _PlanningCallbacks:
    on_wait: Callable[[PlanningPoolEvent], None] | None = None
    on_acquired: Callable[[PlanningPoolEvent], None] | None = None


_state_lock = threading.RLock()
_semaphore: threading.BoundedSemaphore | None = None
_semaphore_limit: int | None = None
_active_projects: dict[str, dict[str, Any]] = {}
_active_count = 0
_waiting_count = 0
_callback_state = threading.local()


def get_max_concurrency() -> int:
    """Return the configured planning concurrency, falling back safely to 2."""
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
    """Return a best-effort snapshot for tests/debugging."""
    with _state_lock:
        return PlanningPoolEvent(
            project_id="",
            step_name="snapshot",
            max_concurrency=get_max_concurrency(),
            active_count=_active_count,
            waiting_count=_waiting_count,
        )


def active_project_info(project_id: str) -> dict[str, Any] | None:
    """Return active/waiting planning info for one project, if any."""
    with _state_lock:
        info = _active_projects.get(project_id)
        return dict(info) if info else None


def is_project_active(project_id: str) -> bool:
    """Whether a project currently owns or waits on a planning slot."""
    return active_project_info(project_id) is not None


def reset_for_tests() -> None:
    """Reset in-memory state. Intended for tests only."""
    global _semaphore, _semaphore_limit, _active_count, _waiting_count
    with _state_lock:
        _semaphore = None
        _semaphore_limit = None
        _active_projects.clear()
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
        if isinstance(value, str):
            safe[key] = f"{value[:160]}...[truncated]" if len(value) > 160 else value
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [str(item)[:80] for item in value[:20]]
        elif isinstance(value, dict):
            safe[key] = {str(item_key)[:80]: str(item_value)[:120] for item_key, item_value in list(value.items())[:20]}
        else:
            safe[key] = str(value)[:120]
    return safe

def _event_details(details: dict[str, Any] | None, event: PlanningPoolEvent | None = None, **extra: Any) -> dict[str, Any]:
    payload = _safe_details(details)
    if event is not None:
        payload.update(event.__dict__)
    payload.update(_safe_details(extra))
    return payload


def _log_event(
    db: Session,
    *,
    event_name: str,
    status: str,
    project_id: str,
    step_name: str,
    provider: str | None,
    model: str | None,
    message: str,
    error_code: str | None = None,
    duration_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    video_observability.log_event(
        db,
        step_name=event_name,
        status=status,
        project_id=project_id,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        error_code=error_code,
        message=message,
        technical_details=_safe_details(details),
    )

def _log_event_safely(db: Session, **kwargs: Any) -> None:
    try:
        _log_event(db, **kwargs)
    except Exception:
        logger.exception(
            "Failed to write AI Video planning pool debug event",
            extra={
                "project_id": kwargs.get("project_id"),
                "step_name": kwargs.get("step_name"),
                "event_name": kwargs.get("event_name"),
                "status": kwargs.get("status"),
                "error_code": kwargs.get("error_code"),
            },
        )

def _run_callback_safely(
    db: Session,
    callback: Callable[[PlanningPoolEvent], None] | None,
    event: PlanningPoolEvent,
    *,
    provider: str | None,
    model: str | None,
    callback_name: str,
    details: dict[str, Any] | None,
) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception as exc:
        _log_event_safely(
            db,
            event_name="codex_planning_callback_error",
            status="failure",
            project_id=event.project_id,
            step_name=event.step_name,
            provider=provider,
            model=model,
            error_code="CODEX_PLANNING_CALLBACK_FAILED",
            message=f"Callback {callback_name} của Codex planning pool bị lỗi.",
            details=_event_details(details, event, callback_name=callback_name, error_class=exc.__class__.__name__),
        )
        logger.exception(
            "AI Video planning pool callback failed",
            extra={
                "project_id": event.project_id,
                "step_name": event.step_name,
                "callback_name": callback_name,
            },
        )


@contextmanager
def planning_slot(
    db: Session,
    *,
    project_id: str,
    step_name: str,
    provider: str | None = None,
    model: str | None = None,
    details: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Acquire a global Codex planning slot and a per-project planning lock."""
    global _active_count, _waiting_count
    started_wait = time.perf_counter()
    acquired = False
    registered = False
    release_status = "failure"
    release_message = "Codex planning đã release slot sau lỗi chưa xác định."
    release_error_code = "CODEX_PLANNING_FAILED"
    max_concurrency: int
    semaphore: threading.BoundedSemaphore
    callbacks = _current_callbacks()

    with _state_lock:
        semaphore = _ensure_semaphore_locked()
        max_concurrency = _semaphore_limit or get_max_concurrency()
        if project_id in _active_projects:
            active_info = dict(_active_projects.get(project_id) or {})
            active_step_name = active_info.get("step_name")
            duplicate_event = PlanningPoolEvent(
                project_id=project_id,
                step_name=step_name,
                max_concurrency=max_concurrency,
                active_count=_active_count,
                waiting_count=_waiting_count,
            )
            duplicate_error = ProjectPlanningActiveError(project_id, step_name, active_step_name=active_step_name)
            _log_event_safely(
                db,
                event_name="codex_planning_rejected",
                status="failure",
                project_id=project_id,
                step_name=step_name,
                provider=provider,
                model=model,
                error_code=duplicate_error.error_code,
                message=str(duplicate_error),
                details=_event_details(details, duplicate_event, active_project=active_info),
            )
            raise duplicate_error
        _active_projects[project_id] = {"step_name": step_name, "state": "waiting", "started_at": time.time()}
        registered = True
        _waiting_count += 1

    try:
        acquired = semaphore.acquire(blocking=False)
        if not acquired:
            with _state_lock:
                wait_event = PlanningPoolEvent(
                    project_id=project_id,
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
                step_name=step_name,
                provider=provider,
                model=model,
                message="Codex planning đang chờ slot trống.",
                details=_event_details(details, wait_event),
            )
            _run_callback_safely(
                db,
                callbacks.on_wait,
                wait_event,
                provider=provider,
                model=model,
                callback_name="on_wait",
                details=details,
            )
            semaphore.acquire()
        acquired = True
        wait_ms = round((time.perf_counter() - started_wait) * 1000, 2)
        with _state_lock:
            _waiting_count = max(0, _waiting_count - 1)
            _active_count += 1
            _active_projects[project_id] = {"step_name": step_name, "state": "running", "started_at": time.time()}
            acquired_event = PlanningPoolEvent(
                project_id=project_id,
                step_name=step_name,
                max_concurrency=max_concurrency,
                active_count=_active_count,
                waiting_count=_waiting_count,
                wait_ms=wait_ms,
            )
        _run_callback_safely(
            db,
            callbacks.on_acquired,
            acquired_event,
            provider=provider,
            model=model,
            callback_name="on_acquired",
            details=details,
        )
        _log_event_safely(
            db,
            event_name="codex_planning_acquired",
            status="start",
            project_id=project_id,
            step_name=step_name,
            provider=provider,
            model=model,
            duration_ms=wait_ms,
            message="Codex planning đã lấy slot.",
            details=_event_details(details, acquired_event),
        )
        yield
        _log_event_safely(
            db,
            event_name="codex_planning_completed",
            status="success",
            project_id=project_id,
            step_name=step_name,
            provider=provider,
            model=model,
            message="Codex planning hoàn tất.",
            details=_event_details(details, acquired_event),
        )
        release_status = "success"
        release_message = "Codex planning đã release slot."
        release_error_code = None
    except Exception as exc:
        release_status = "failure"
        release_message = "Codex planning lỗi và đã release slot."
        release_error_code = getattr(exc, "error_code", "CODEX_PLANNING_FAILED")
        if acquired:
            _log_event_safely(
                db,
                event_name="codex_planning_error",
                status="failure",
                project_id=project_id,
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
                _active_projects.pop(project_id, None)
                if acquired:
                    _active_count = max(0, _active_count - 1)
                else:
                    _waiting_count = max(0, _waiting_count - 1)
                released_event = PlanningPoolEvent(
                    project_id=project_id,
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
                    step_name=step_name,
                    provider=provider,
                    model=model,
                    error_code=release_error_code,
                    message=release_message,
                    details=_event_details(details, released_event),
                )
