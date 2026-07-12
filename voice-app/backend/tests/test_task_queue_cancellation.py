import asyncio

from backend.services import task_queue

def test_cancel_queued_generation_skips_execution():
    asyncio.run(_cancel_queued_generation_skips_execution())

async def _cancel_queued_generation_skips_execution():
    task_queue.init_queue(force=True, max_concurrency=1)

    running_started = asyncio.Event()
    release_running = asyncio.Event()
    queued_ran = asyncio.Event()

    async def running_job():
        running_started.set()
        await release_running.wait()

    async def queued_job():
        queued_ran.set()

    task_queue.enqueue_generation("gen-running", running_job())
    await asyncio.wait_for(running_started.wait(), timeout=1)

    task_queue.enqueue_generation("gen-queued", queued_job())
    assert task_queue.cancel_generation("gen-queued") == "queued"

    release_running.set()
    await asyncio.sleep(0.1)

    assert not queued_ran.is_set()

def test_cancel_running_generation_cancels_task():
    asyncio.run(_cancel_running_generation_cancels_task())

async def _cancel_running_generation_cancels_task():
    task_queue.init_queue(force=True, max_concurrency=1)

    running_started = asyncio.Event()
    running_cancelled = asyncio.Event()

    async def running_job():
        running_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            running_cancelled.set()
            raise

    task_queue.enqueue_generation("gen-running", running_job())
    await asyncio.wait_for(running_started.wait(), timeout=1)

    assert task_queue.cancel_generation("gen-running") == "running"
    await asyncio.wait_for(running_cancelled.wait(), timeout=1)

def test_generation_queue_runs_two_jobs_concurrently():
    asyncio.run(_generation_queue_runs_two_jobs_concurrently())

async def _generation_queue_runs_two_jobs_concurrently():
    task_queue.init_queue(force=True, max_concurrency=2)

    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release = asyncio.Event()

    async def job(started: asyncio.Event):
        started.set()
        await release.wait()

    task_queue.enqueue_generation("gen-first", job(first_started))
    task_queue.enqueue_generation("gen-second", job(second_started))

    await asyncio.wait_for(first_started.wait(), timeout=1)
    await asyncio.wait_for(second_started.wait(), timeout=1)
    snapshot = task_queue.get_generation_queue_snapshot()

    assert snapshot["max_concurrency"] == 2
    assert snapshot["running"] == 2

    release.set()
    await asyncio.sleep(0.1)
