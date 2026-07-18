import asyncio

import pytest

from backend.services import video_workflow_pool
from backend.services import video_auto_runs


async def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out while waiting for workflow pool state")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_three_workflows_run_and_fourth_waits_fifo(monkeypatch):
    monkeypatch.delenv(video_workflow_pool.CONCURRENCY_ENV, raising=False)
    video_workflow_pool.reset_for_tests()
    entered: list[str] = []
    releases = {f"work-{index}": asyncio.Event() for index in range(4)}

    async def worker(work_key: str) -> None:
        async with video_workflow_pool.workflow_slot(
            work_key=work_key,
            workflow_type="test",
            operation_name="run",
        ):
            entered.append(work_key)
            await releases[work_key].wait()

    tasks = [asyncio.create_task(worker(f"work-{index}")) for index in range(3)]
    try:
        await _wait_until(lambda: video_workflow_pool.snapshot()["running"] == 3)
        fourth = asyncio.create_task(worker("work-3"))
        tasks.append(fourth)
        await _wait_until(lambda: video_workflow_pool.snapshot()["queued"] == 1)
        assert entered == ["work-0", "work-1", "work-2"]

        releases["work-0"].set()
        await _wait_until(lambda: "work-3" in entered)
        assert entered == ["work-0", "work-1", "work-2", "work-3"]
    finally:
        for event in releases.values():
            event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        video_workflow_pool.reset_for_tests()


@pytest.mark.asyncio
async def test_duplicate_work_key_is_rejected():
    video_workflow_pool.reset_for_tests()
    async with video_workflow_pool.workflow_slot(
        work_key="ai-video:one",
        workflow_type="ai_video",
        operation_name="auto_run",
    ):
        with pytest.raises(video_workflow_pool.WorkflowAlreadyActiveError):
            async with video_workflow_pool.workflow_slot(
                work_key="ai-video:one",
                workflow_type="ai_video",
                operation_name="auto_run",
            ):
                raise AssertionError("duplicate workflow must not enter")
    assert video_workflow_pool.snapshot()["running"] == 0


@pytest.mark.asyncio
async def test_cancel_waiting_workflow_removes_it_immediately(monkeypatch):
    monkeypatch.setenv(video_workflow_pool.CONCURRENCY_ENV, "1")
    video_workflow_pool.reset_for_tests()
    release = asyncio.Event()

    async def first() -> None:
        async with video_workflow_pool.workflow_slot(
            work_key="ai-video:first",
            workflow_type="ai_video",
            operation_name="auto_run",
        ):
            await release.wait()

    async def second() -> None:
        async with video_workflow_pool.workflow_slot(
            work_key="video-inspiration:second",
            workflow_type="video_inspiration",
            operation_name="analyze",
        ):
            raise AssertionError("cancelled queued workflow must not enter")

    first_task = asyncio.create_task(first())
    second_task: asyncio.Task | None = None
    try:
        await _wait_until(lambda: video_workflow_pool.snapshot()["running"] == 1)
        second_task = asyncio.create_task(second())
        await _wait_until(lambda: video_workflow_pool.snapshot()["queued"] == 1)
        assert video_workflow_pool.cancel_waiting("video-inspiration:second") is True
        await _wait_until(lambda: video_workflow_pool.snapshot()["queued"] == 0)
        result = await asyncio.gather(second_task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
    finally:
        release.set()
        await asyncio.gather(first_task, return_exceptions=True)
        if second_task is not None and not second_task.done():
            second_task.cancel()
            await asyncio.gather(second_task, return_exceptions=True)
        video_workflow_pool.reset_for_tests()


def test_workflow_concurrency_cannot_exceed_three(monkeypatch):
    monkeypatch.setenv(video_workflow_pool.CONCURRENCY_ENV, "99")
    assert video_workflow_pool.get_max_concurrency() == 3


@pytest.mark.asyncio
async def test_ai_video_auto_run_uses_shared_three_workflow_limit(monkeypatch):
    monkeypatch.delenv(video_workflow_pool.CONCURRENCY_ENV, raising=False)
    video_workflow_pool.reset_for_tests()
    entered: list[str] = []
    release = asyncio.Event()

    monkeypatch.setattr(video_auto_runs, "_workflow_context", lambda run_id: (run_id, "auto_run"))
    monkeypatch.setattr(video_auto_runs, "_workflow_acquired", lambda run_id: True)

    async def fake_run_in_slot(run_id: str) -> None:
        entered.append(run_id)
        await release.wait()

    monkeypatch.setattr(video_auto_runs, "_run_auto_run_in_slot", fake_run_in_slot)
    tasks = [asyncio.create_task(video_auto_runs._run_auto_run(f"project-{index}")) for index in range(4)]
    try:
        await _wait_until(lambda: video_workflow_pool.snapshot()["running"] == 3)
        await _wait_until(lambda: video_workflow_pool.snapshot()["queued"] == 1)
        await _wait_until(lambda: len(entered) == 3)
        assert entered == ["project-0", "project-1", "project-2"]
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        video_workflow_pool.reset_for_tests()


@pytest.mark.asyncio
async def test_two_ai_video_and_one_video_inspiration_share_the_same_pool(monkeypatch):
    monkeypatch.delenv(video_workflow_pool.CONCURRENCY_ENV, raising=False)
    video_workflow_pool.reset_for_tests()
    release = asyncio.Event()
    entered: set[str] = set()

    monkeypatch.setattr(video_auto_runs, "_workflow_context", lambda run_id: (run_id, "auto_run"))
    monkeypatch.setattr(video_auto_runs, "_workflow_acquired", lambda run_id: True)

    async def fake_ai_run(run_id: str) -> None:
        entered.add(f"ai-video:{run_id}")
        await release.wait()

    async def inspiration_run() -> None:
        async with video_workflow_pool.workflow_slot(
            work_key="video-inspiration:job-1",
            workflow_type="video_inspiration",
            operation_name="analyze",
        ):
            entered.add("video-inspiration:job-1")
            await release.wait()

    monkeypatch.setattr(video_auto_runs, "_run_auto_run_in_slot", fake_ai_run)
    tasks = [
        asyncio.create_task(video_auto_runs._run_auto_run("project-a")),
        asyncio.create_task(video_auto_runs._run_auto_run("project-b")),
        asyncio.create_task(inspiration_run()),
    ]
    try:
        await _wait_until(lambda: video_workflow_pool.snapshot()["running"] == 3)
        await _wait_until(lambda: len(entered) == 3)
        assert entered == {
            "ai-video:project-a",
            "ai-video:project-b",
            "video-inspiration:job-1",
        }
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        video_workflow_pool.reset_for_tests()
