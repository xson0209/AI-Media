"""
Generation queue with bounded TTS concurrency.
"""

import asyncio
import os
import traceback
from dataclasses import dataclass
from typing import Coroutine, Literal

# Keep references to fire-and-forget background tasks to prevent GC
_background_tasks: set = set()


@dataclass
class GenerationJob:
    """Queued generation work plus the generation ID it belongs to."""

    generation_id: str
    coro: Coroutine


DEFAULT_GENERATION_CONCURRENCY = 2
MAX_GENERATION_CONCURRENCY = 4

# Generation queue — limits concurrent TTS inference to avoid GPU contention
_generation_queue: asyncio.Queue = None  # type: ignore  # initialized at startup
_generation_worker_tasks: list[asyncio.Task] = []
_queued_generation_ids: set[str] = set()
_running_generation_tasks: dict[str, asyncio.Task] = {}
_cancelled_generation_ids: set[str] = set()
_generation_max_concurrency = DEFAULT_GENERATION_CONCURRENCY


def create_background_task(coro) -> asyncio.Task:
    """Create a background task and prevent it from being garbage collected."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def get_generation_max_concurrency() -> int:
    """Return configured generation concurrency, clamped to a small safe range."""
    raw = os.environ.get("VOICEBOX_GENERATION_CONCURRENCY")
    if raw is None or not raw.strip():
        return DEFAULT_GENERATION_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_GENERATION_CONCURRENCY
    return max(1, min(MAX_GENERATION_CONCURRENCY, value))

async def _generation_worker():
    """Worker that processes generation tasks from the shared queue."""
    while True:
        job = await _generation_queue.get()
        try:
            if job.generation_id in _cancelled_generation_ids:
                _cancelled_generation_ids.discard(job.generation_id)
                job.coro.close()
                continue

            task = asyncio.create_task(job.coro)
            _running_generation_tasks[job.generation_id] = task
            _queued_generation_ids.discard(job.generation_id)
            try:
                await task
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise
        except Exception:
            traceback.print_exc()
            await _force_fail_if_active(
                job.generation_id,
                "Worker exited without writing terminal status",
            )
        finally:
            _running_generation_tasks.pop(job.generation_id, None)
            _queued_generation_ids.discard(job.generation_id)
            _generation_queue.task_done()


async def _force_fail_if_active(generation_id: str, error: str) -> None:
    """Best-effort recovery — flip an active row to failed if the worker
    bailed before writing a terminal status. Catches the case where the gen
    coroutine's own status-write raised (e.g. SQLite lock contention)."""
    try:
        from ..database import Generation as DBGeneration, get_db
        from . import history

        db = next(get_db())
        try:
            gen = db.query(DBGeneration).filter_by(id=generation_id).first()
            if gen is None:
                return
            if (gen.status or "completed") not in ("loading_model", "generating"):
                return
            await history.update_generation_status(
                generation_id=generation_id,
                status="failed",
                db=db,
                error=error,
            )
        finally:
            db.close()
    except Exception:
        traceback.print_exc()


def enqueue_generation(generation_id: str, coro):
    """Add a generation coroutine to the bounded-concurrency queue."""
    if _generation_queue is None:
        raise RuntimeError("Generation queue has not been initialized")

    _queued_generation_ids.add(generation_id)
    _generation_queue.put_nowait(GenerationJob(generation_id=generation_id, coro=coro))


def cancel_generation(generation_id: str) -> Literal["queued", "running"] | None:
    """Cancel a queued or running generation if it is still active."""
    running_task = _running_generation_tasks.get(generation_id)
    if running_task is not None:
        running_task.cancel()
        return "running"

    if generation_id in _queued_generation_ids:
        _queued_generation_ids.discard(generation_id)
        _cancelled_generation_ids.add(generation_id)
        return "queued"

    return None


def get_generation_queue_snapshot() -> dict:
    """Return queue state for resource cleanup guards and diagnostics."""
    return {
        "available": _generation_queue is not None,
        "max_concurrency": _generation_max_concurrency,
        "queued": len(_queued_generation_ids),
        "running": len(_running_generation_tasks),
        "queued_ids": sorted(_queued_generation_ids),
        "running_ids": sorted(_running_generation_tasks.keys()),
    }

def init_queue(force: bool = False, max_concurrency: int | None = None):
    """Initialize the generation queue and start worker tasks.

    Must be called once during application startup (inside a running event loop).
    """
    global _generation_queue, _generation_worker_tasks, _generation_max_concurrency
    global _queued_generation_ids, _running_generation_tasks, _cancelled_generation_ids

    active_workers = [task for task in _generation_worker_tasks if not task.done()]
    if active_workers:
        if not force:
            return
        for task in active_workers:
            task.cancel()
        for task in list(_running_generation_tasks.values()):
            task.cancel()

    configured_concurrency = max_concurrency if max_concurrency is not None else get_generation_max_concurrency()
    _generation_max_concurrency = max(1, min(MAX_GENERATION_CONCURRENCY, int(configured_concurrency)))
    _generation_queue = asyncio.Queue()
    _queued_generation_ids = set()
    _running_generation_tasks = {}
    _cancelled_generation_ids = set()
    _generation_worker_tasks = [
        create_background_task(_generation_worker())
        for _ in range(_generation_max_concurrency)
    ]
