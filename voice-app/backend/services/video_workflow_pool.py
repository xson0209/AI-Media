"""In-process coordinator for long-running AI media workflows.

The desktop application runs one backend process, so an asyncio-aware FIFO
coordinator is sufficient to keep at most three AI Video / Video Inspiration
workflows active while still letting HTTP polling remain responsive.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Callable

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 3
MAX_CONCURRENCY = 3
CONCURRENCY_ENV = "VOICEBOX_MEDIA_WORKFLOW_CONCURRENCY"


class WorkflowPoolError(RuntimeError):
    """Base error for workflow coordination."""


class WorkflowAlreadyActiveError(WorkflowPoolError):
    """Raised when the same project/job is already queued or running."""

    def __init__(self, work_key: str):
        super().__init__("Dự án này đã được xếp lịch hoặc đang xử lý. Vui lòng theo dõi tiến độ hiện tại.")
        self.work_key = work_key


@dataclass(frozen=True)
class WorkflowPoolEvent:
    work_key: str
    workflow_type: str
    operation_name: str
    max_concurrency: int
    running: int
    queued: int
    wait_ms: float | None = None


@dataclass
class _Waiter:
    work_key: str
    workflow_type: str
    operation_name: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[None]
    queued_at: float


_state_lock = threading.RLock()
_running: dict[str, dict[str, object]] = {}
_waiting: deque[_Waiter] = deque()


def get_max_concurrency() -> int:
    """Return a configurable lower limit while preserving the hard cap of 3."""
    raw = os.environ.get(CONCURRENCY_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_CONCURRENCY
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MAX_CONCURRENCY
    if parsed < 1:
        return DEFAULT_MAX_CONCURRENCY
    return min(parsed, MAX_CONCURRENCY)


def _event(
    *,
    work_key: str,
    workflow_type: str,
    operation_name: str,
    wait_ms: float | None = None,
) -> WorkflowPoolEvent:
    return WorkflowPoolEvent(
        work_key=work_key,
        workflow_type=workflow_type,
        operation_name=operation_name,
        max_concurrency=get_max_concurrency(),
        running=len(_running),
        queued=len(_waiting),
        wait_ms=wait_ms,
    )


def snapshot() -> dict[str, object]:
    """Return resource counters and safe keys for API/UI diagnostics."""
    with _state_lock:
        return {
            "available": True,
            "max_concurrency": get_max_concurrency(),
            "running": len(_running),
            "queued": len(_waiting),
            "running_keys": sorted(_running),
            "queued_keys": [item.work_key for item in _waiting],
        }


def is_active(work_key: str) -> bool:
    with _state_lock:
        return work_key in _running or any(item.work_key == work_key for item in _waiting)


def _wake_next_locked() -> None:
    limit = get_max_concurrency()
    while len(_running) < limit and _waiting:
        waiter = _waiting.popleft()
        if waiter.future.done():
            continue
        _running[waiter.work_key] = {
            "workflow_type": waiter.workflow_type,
            "operation_name": waiter.operation_name,
            "started_at": time.time(),
        }

        def _wake(future: asyncio.Future[None] = waiter.future) -> None:
            if not future.done():
                future.set_result(None)

        waiter.loop.call_soon_threadsafe(_wake)


def _remove_waiter_locked(work_key: str) -> bool:
    removed = False
    retained: deque[_Waiter] = deque()
    while _waiting:
        waiter = _waiting.popleft()
        if waiter.work_key == work_key:
            removed = True

            def _cancel(future: asyncio.Future[None] = waiter.future) -> None:
                if not future.done():
                    future.cancel()

            waiter.loop.call_soon_threadsafe(_cancel)
            continue
        retained.append(waiter)
    _waiting.extend(retained)
    return removed


def cancel_waiting(work_key: str) -> bool:
    """Cancel a workflow that has not acquired one of the three slots yet."""
    with _state_lock:
        removed = _remove_waiter_locked(work_key)
        if removed:
            _wake_next_locked()
        return removed


def _release_or_unregister(work_key: str) -> None:
    with _state_lock:
        _running.pop(work_key, None)
        _remove_waiter_locked(work_key)
        _wake_next_locked()


@asynccontextmanager
async def workflow_slot(
    *,
    work_key: str,
    workflow_type: str,
    operation_name: str,
    on_wait: Callable[[WorkflowPoolEvent], None] | None = None,
    on_acquired: Callable[[WorkflowPoolEvent], None] | None = None,
) -> AsyncIterator[WorkflowPoolEvent]:
    """Acquire one FIFO workflow slot and release it in every exit path."""
    normalized_key = (work_key or "").strip()
    if not normalized_key:
        raise WorkflowPoolError("Thiếu mã dự án để xếp lịch xử lý.")

    loop = asyncio.get_running_loop()
    queued_at = time.perf_counter()
    waiter: _Waiter | None = None
    acquired_immediately = False

    with _state_lock:
        if normalized_key in _running or any(item.work_key == normalized_key for item in _waiting):
            raise WorkflowAlreadyActiveError(normalized_key)
        if len(_running) < get_max_concurrency() and not _waiting:
            _running[normalized_key] = {
                "workflow_type": workflow_type,
                "operation_name": operation_name,
                "started_at": time.time(),
            }
            acquired_immediately = True
        else:
            waiter = _Waiter(
                work_key=normalized_key,
                workflow_type=workflow_type,
                operation_name=operation_name,
                loop=loop,
                future=loop.create_future(),
                queued_at=time.time(),
            )
            _waiting.append(waiter)
            waiting_event = _event(
                work_key=normalized_key,
                workflow_type=workflow_type,
                operation_name=operation_name,
            )

    if waiter is not None and on_wait is not None:
        try:
            on_wait(waiting_event)
        except Exception:
            logger.exception("Workflow wait callback failed", extra={"work_key": normalized_key})
    if waiter is not None:
        logger.info(
            "AI media workflow is waiting for a slot",
            extra={"workflow_pool": event_as_dict(waiting_event)},
        )

    yielded = False
    try:
        if waiter is not None:
            await waiter.future
        wait_ms = round((time.perf_counter() - queued_at) * 1000, 2)
        with _state_lock:
            acquired_event = _event(
                work_key=normalized_key,
                workflow_type=workflow_type,
                operation_name=operation_name,
                wait_ms=wait_ms,
            )
        if on_acquired is not None:
            try:
                on_acquired(acquired_event)
            except Exception:
                logger.exception("Workflow acquired callback failed", extra={"work_key": normalized_key})
        logger.info(
            "AI media workflow acquired a slot",
            extra={"workflow_pool": event_as_dict(acquired_event)},
        )
        yielded = True
        yield acquired_event
    finally:
        # This also handles cancellation racing with a waiter being promoted.
        if yielded or acquired_immediately or waiter is not None:
            _release_or_unregister(normalized_key)
            released = snapshot()
            logger.info(
                "AI media workflow released its slot",
                extra={
                    "workflow_pool": {
                        "work_key": normalized_key,
                        "workflow_type": workflow_type,
                        "operation_name": operation_name,
                        "max_concurrency": released["max_concurrency"],
                        "running": released["running"],
                        "queued": released["queued"],
                    }
                },
            )


def reset_for_tests() -> None:
    """Reset all in-memory workflow state. Intended for tests only."""
    with _state_lock:
        for waiter in list(_waiting):
            if not waiter.future.done():
                waiter.loop.call_soon_threadsafe(waiter.future.cancel)
        _waiting.clear()
        _running.clear()


def event_as_dict(event: WorkflowPoolEvent) -> dict[str, object]:
    return asdict(event)
