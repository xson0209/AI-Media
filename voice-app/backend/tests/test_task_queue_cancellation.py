import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

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

def test_generation_queue_serializes_tts_jobs():
    asyncio.run(_generation_queue_serializes_tts_jobs())

async def _generation_queue_serializes_tts_jobs():
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
    await asyncio.sleep(0.05)
    snapshot = task_queue.get_generation_queue_snapshot()

    assert snapshot["max_concurrency"] == 1
    assert snapshot["running"] == 1
    assert snapshot["running_ids"] == ["gen-first"]
    assert snapshot["queued_ids"] == ["gen-second"]
    assert not second_started.is_set()

    release.set()
    await asyncio.wait_for(second_started.wait(), timeout=1)
    await asyncio.sleep(0.05)


def test_generation_concurrency_is_hard_capped_at_one(monkeypatch):
    monkeypatch.setenv("VOICEBOX_GENERATION_CONCURRENCY", "99")

    assert task_queue.get_generation_max_concurrency() == 1
    asyncio.run(_generation_concurrency_is_hard_capped_at_one())


async def _generation_concurrency_is_hard_capped_at_one():
    task_queue.init_queue(force=True, max_concurrency=99)

    first_started = asyncio.Event()
    second_started = asyncio.Event()
    third_started = asyncio.Event()
    release = asyncio.Event()

    async def job(started: asyncio.Event):
        started.set()
        await release.wait()

    task_queue.enqueue_generation("gen-first", job(first_started))
    task_queue.enqueue_generation("gen-second", job(second_started))
    task_queue.enqueue_generation("gen-third", job(third_started))

    await asyncio.wait_for(first_started.wait(), timeout=1)
    await asyncio.sleep(0.05)

    snapshot = task_queue.get_generation_queue_snapshot()
    assert snapshot["max_concurrency"] == 1
    assert snapshot["running"] == 1
    assert snapshot["queued"] == 2
    assert not second_started.is_set()
    assert not third_started.is_set()

    release.set()
    await asyncio.wait_for(second_started.wait(), timeout=1)
    await asyncio.wait_for(third_started.wait(), timeout=1)
    await asyncio.sleep(0.05)


def test_stream_and_queue_share_the_same_inference_gate():
    asyncio.run(_stream_and_queue_share_the_same_inference_gate())


async def _stream_and_queue_share_the_same_inference_gate():
    task_queue.init_queue(force=True, max_concurrency=2)

    direct_started = asyncio.Event()
    release_direct = asyncio.Event()
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_jobs = asyncio.Event()

    async def direct_inference():
        async with task_queue.generation_inference_slot():
            direct_started.set()
            await release_direct.wait()

    async def queued_job(started: asyncio.Event):
        started.set()
        await release_jobs.wait()

    direct_task = asyncio.create_task(direct_inference())
    await asyncio.wait_for(direct_started.wait(), timeout=1)

    task_queue.enqueue_generation("gen-first", queued_job(first_started))
    task_queue.enqueue_generation("gen-second", queued_job(second_started))

    await asyncio.sleep(0.05)

    snapshot = task_queue.get_generation_queue_snapshot()
    assert snapshot["max_concurrency"] == 1
    assert snapshot["running"] == 1
    assert snapshot["running_ids"] == []
    assert snapshot["queued_ids"] == ["gen-first", "gen-second"]
    assert not first_started.is_set()
    assert not second_started.is_set()

    release_direct.set()
    await asyncio.wait_for(first_started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    assert not second_started.is_set()

    release_jobs.set()
    await asyncio.wait_for(second_started.wait(), timeout=1)

    await direct_task
    await asyncio.sleep(0.05)


def test_generate_stream_enters_the_shared_inference_gate(monkeypatch):
    asyncio.run(_generate_stream_enters_the_shared_inference_gate(monkeypatch))


async def _generate_stream_enters_the_shared_inference_gate(monkeypatch):
    import numpy as np

    from backend import backends, models
    from backend.routes import generations as generation_routes
    from backend.utils import chunked_tts

    gate_depth = 0
    calls: list[tuple[str, int]] = []

    @asynccontextmanager
    async def fake_inference_slot():
        nonlocal gate_depth
        gate_depth += 1
        calls.append(("gate_enter", gate_depth))
        try:
            yield
        finally:
            calls.append(("gate_exit", gate_depth))
            gate_depth -= 1

    async def fake_get_profile(profile_id, db):
        return SimpleNamespace(
            id=profile_id,
            default_engine="qwen",
            preset_engine=None,
            effects_chain=None,
        )

    async def fake_ready(*args, **kwargs):
        calls.append(("cache_ready", gate_depth))

    async def fake_load(*args, **kwargs):
        calls.append(("load_model", gate_depth))

    async def fake_voice_prompt(*args, **kwargs):
        calls.append(("voice_prompt", gate_depth))
        return {}

    async def fake_generate(*args, **kwargs):
        calls.append(("generate", gate_depth))
        return np.zeros(8, dtype=np.float32), 24000

    monkeypatch.setattr(generation_routes, "generation_inference_slot", fake_inference_slot)
    monkeypatch.setattr(generation_routes.profiles, "get_profile", fake_get_profile)
    monkeypatch.setattr(generation_routes.profiles, "validate_profile_engine", lambda *args, **kwargs: None)
    monkeypatch.setattr(generation_routes.profiles, "create_voice_prompt_for_profile", fake_voice_prompt)
    monkeypatch.setattr(generation_routes, "_validate_experimental_language_request", lambda *args, **kwargs: None)
    monkeypatch.setattr(generation_routes, "_allow_tada_vietnamese_profile_bypass", lambda *args, **kwargs: False)
    monkeypatch.setattr(backends, "ensure_model_cached_or_raise", fake_ready)
    monkeypatch.setattr(backends, "load_engine_model", fake_load)
    monkeypatch.setattr(backends, "get_tts_backend_for_engine", lambda engine: object())
    monkeypatch.setattr(backends, "engine_needs_trim", lambda engine: False)
    monkeypatch.setattr(chunked_tts, "generate_chunked", fake_generate)
    monkeypatch.setattr(generation_routes.tts, "audio_to_wav_bytes", lambda audio, sample_rate: b"RIFF-test")

    response = await generation_routes.stream_speech(
        models.GenerationRequest(
            profile_id="profile-1",
            text="Hello from the shared inference gate.",
            language="en",
            engine="qwen",
        ),
        db=object(),
    )

    assert response.media_type == "audio/wav"
    assert ("cache_ready", 0) in calls
    assert ("load_model", 1) in calls
    assert ("voice_prompt", 1) in calls
    assert ("generate", 1) in calls
    assert calls[-1] == ("gate_exit", 1)


def test_generate_audio_sync_waits_for_the_shared_inference_gate(monkeypatch):
    asyncio.run(_generate_audio_sync_waits_for_the_shared_inference_gate(monkeypatch))


async def _generate_audio_sync_waits_for_the_shared_inference_gate(monkeypatch):
    import numpy as np

    from backend import backends
    from backend.services import generation as generation_service
    from backend.services import qwen_vietnamese, tada_vietnamese, tts as tts_service
    from backend.utils import chunked_tts

    task_queue.init_queue(force=True, max_concurrency=1)
    holder_started = asyncio.Event()
    release_holder = asyncio.Event()
    calls: list[str] = []

    class FakeDB:
        def close(self):
            calls.append("db_close")

    async def hold_slot():
        async with task_queue.generation_inference_slot():
            holder_started.set()
            await release_holder.wait()

    async def fake_get_profile(profile_id, db):
        calls.append("profile")
        return SimpleNamespace(id=profile_id, language="en")

    async def fake_load(*args, **kwargs):
        calls.append("load")

    async def fake_voice_prompt(*args, **kwargs):
        calls.append("voice_prompt")
        return {}

    async def fake_generate(*args, **kwargs):
        calls.append("generate")
        return np.zeros(8, dtype=np.float32), 24000

    monkeypatch.setattr(generation_service, "get_db", lambda: iter([FakeDB()]))
    monkeypatch.setattr(generation_service.profiles, "get_profile", fake_get_profile)
    monkeypatch.setattr(generation_service.profiles, "create_voice_prompt_for_profile", fake_voice_prompt)
    monkeypatch.setattr(qwen_vietnamese, "ensure_qwen_vietnamese_allowed", lambda **kwargs: None)
    monkeypatch.setattr(tada_vietnamese, "ensure_tada_vietnamese_allowed", lambda **kwargs: None)
    monkeypatch.setattr(backends, "get_tts_backend_for_engine", lambda engine: object())
    monkeypatch.setattr(backends, "load_engine_model", fake_load)
    monkeypatch.setattr(backends, "engine_needs_trim", lambda engine: False)
    monkeypatch.setattr(chunked_tts, "generate_chunked", fake_generate)
    monkeypatch.setattr(tts_service, "audio_to_wav_bytes", lambda audio, sample_rate: b"RIFF-sync")

    holder_task = asyncio.create_task(hold_slot())
    await asyncio.wait_for(holder_started.wait(), timeout=1)
    generation_task = asyncio.create_task(
        generation_service.generate_audio_sync(
            profile_id="profile-1",
            text="Wait for the process-wide gate.",
            language="en",
            engine="qwen",
            model_size="1.7B",
        )
    )

    await asyncio.sleep(0.05)
    assert calls == []

    release_holder.set()
    result = await asyncio.wait_for(generation_task, timeout=1)
    await holder_task

    assert result == b"RIFF-sync"
    assert calls == ["profile", "load", "voice_prompt", "db_close", "generate"]
