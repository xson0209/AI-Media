"""
Generation queue with bounded TTS concurrency.
"""

import asyncio
import os
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Coroutine, Literal

# Keep references to fire-and-forget background tasks to prevent GC
_background_tasks: set = set()


@dataclass
class GenerationJob:
    """Queued generation work plus the generation ID it belongs to."""

    generation_id: str
    coro: Coroutine


DEFAULT_GENERATION_CONCURRENCY = 1
# TTS backends share process-wide model/GPU state. Keep this as a hard safety
# limit, even when an environment variable or test override requests more.
# Running two Qwen clone inferences against the same loaded model can starve or
# wedge small local GPUs, leaving AI Video auto-runs stuck at waiting_voice.
MAX_GENERATION_CONCURRENCY = 1

# Generation queue — limits concurrent TTS inference to avoid GPU contention
_generation_queue: asyncio.Queue = None  # type: ignore  # initialized at startup
_generation_worker_tasks: list[asyncio.Task] = []
_queued_generation_ids: set[str] = set()
_running_generation_tasks: dict[str, asyncio.Task] = {}
_cancelled_generation_ids: set[str] = set()
_generation_max_concurrency = DEFAULT_GENERATION_CONCURRENCY
_generation_inference_semaphore: asyncio.Semaphore | None = None
_generation_inference_running = 0


def create_background_task(coro) -> asyncio.Task:
    """Create a background task and prevent it from being garbage collected."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def get_generation_max_concurrency() -> int:
    """Return configured generation concurrency, hard-capped for process safety."""
    raw = os.environ.get("VOICEBOX_GENERATION_CONCURRENCY")
    if raw is None or not raw.strip():
        return DEFAULT_GENERATION_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_GENERATION_CONCURRENCY
    return max(1, min(MAX_GENERATION_CONCURRENCY, value))


@asynccontextmanager
async def generation_inference_slot() -> AsyncIterator[None]:
    """Acquire one process-wide TTS inference slot.

    Queue workers and direct streaming generation share this gate so their
    combined inference count can never exceed the configured hard cap.
    """
    global _generation_inference_running

    semaphore = _generation_inference_semaphore
    if semaphore is None:
        raise RuntimeError("Generation inference gate has not been initialized")

    await semaphore.acquire()
    _generation_inference_running += 1
    try:
        yield
    finally:
        _generation_inference_running = max(0, _generation_inference_running - 1)
        semaphore.release()


async def _generation_worker():
    """Worker that processes generation tasks from the shared queue."""
    while True:
        queue = _generation_queue
        job = await queue.get()
        task: asyncio.Task | None = None
        try:
            if job.generation_id in _cancelled_generation_ids:
                _cancelled_generation_ids.discard(job.generation_id)
                job.coro.close()
                continue

            async with generation_inference_slot():
                # The job may have been cancelled while this worker was
                # waiting for a slot held by another worker or /generate/stream.
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
                    worker_task = asyncio.current_task()
                    if worker_task is not None and worker_task.cancelling():
                        raise
        except asyncio.CancelledError:
            if task is None:
                job.coro.close()
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
            queue.task_done()


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
            if (gen.status or "completed") not in ("queued", "loading_model", "generating"):
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
        # Includes direct /generate/stream inference, which has no generation
        # id and therefore does not appear in running_ids.
        "running": _generation_inference_running,
        "queued_ids": sorted(_queued_generation_ids),
        "running_ids": sorted(_running_generation_tasks.keys()),
    }


def init_queue(force: bool = False, max_concurrency: int | None = None):
    """Initialize the generation queue and start worker tasks.

    Must be called once during application startup (inside a running event loop).
    """
    global _generation_queue, _generation_worker_tasks, _generation_max_concurrency
    global _queued_generation_ids, _running_generation_tasks, _cancelled_generation_ids
    global _generation_inference_semaphore, _generation_inference_running

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
    _generation_inference_semaphore = asyncio.Semaphore(_generation_max_concurrency)
    _generation_inference_running = 0
    _queued_generation_ids = set()
    _running_generation_tasks = {}
    _cancelled_generation_ids = set()
    _generation_worker_tasks = [
        create_background_task(_generation_worker())
        for _ in range(_generation_max_concurrency)
    ]
