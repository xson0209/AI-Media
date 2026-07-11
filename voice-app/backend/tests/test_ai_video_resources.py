import os
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import torch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes import resources
from backend.services import resource_manager, video_rendering
from backend.services.resource_manager import ModelRuntimeState, ResourceManager
from backend.utils import cache as voice_cache


def _status_payload() -> dict:
    return {
        "sampled_at": datetime.utcnow(),
        "policy": {"idle_unload_seconds": 600},
        "memory": {"status": "normal", "percent": None},
        "generation_queue": {
            "available": True,
            "queued": 0,
            "running": 0,
            "queued_ids": [],
            "running_ids": [],
        },
        "active_jobs": {
            "generations": [],
            "generation_count": 0,
            "render_count": 0,
            "auto_run_count": 0,
        },
        "models": [],
        "voice_prompt_cache": {"available": True, "entries": 0, "size_mb": 0},
        "render_cache": {"available": True, "files": 0, "size_mb": 0},
        "mlx": {"available": False},
        "recent_events": [],
    }


def _loaded_state(
    key: str,
    *,
    kind: str = "tts",
    engine: str = "qwen",
    model_size: str = "1.7B",
    last_used_at: datetime | None = None,
    heavy: bool = False,
) -> ModelRuntimeState:
    used_at = last_used_at or datetime.utcnow()
    return ModelRuntimeState(
        key=key,
        kind=kind,
        engine=engine,
        model_size=model_size,
        loaded=True,
        loaded_at=used_at,
        last_used_at=used_at,
        heavy=heavy,
        size_mb=3500 if heavy else 500,
    )


def test_resource_manager_unloads_idle_model(monkeypatch):
    manager = ResourceManager()
    state = _loaded_state(
        "tts:qwen:1.7B",
        last_used_at=datetime.utcnow() - timedelta(seconds=30),
    )
    manager._models[state.key] = state

    monkeypatch.setenv(resource_manager.RESOURCE_IDLE_UNLOAD_SECONDS_ENV, "1")
    monkeypatch.setattr(resource_manager, "has_active_resource_work", lambda db=None: False)
    monkeypatch.setattr(resource_manager, "model_config_for_state", lambda _state: object())

    import backend.backends as backends

    monkeypatch.setattr(backends, "unload_model_by_config", lambda _config: True)

    actions = manager.unload_idle_models()

    assert actions[0].status == "completed"
    assert actions[0].details["reason"] == "idle_timeout"
    assert state.loaded is False


def test_resource_manager_keeps_models_when_jobs_are_active(monkeypatch):
    manager = ResourceManager()
    state = _loaded_state(
        "tts:qwen:1.7B",
        last_used_at=datetime.utcnow() - timedelta(seconds=30),
    )
    manager._models[state.key] = state

    monkeypatch.setenv(resource_manager.RESOURCE_IDLE_UNLOAD_SECONDS_ENV, "1")
    monkeypatch.setattr(resource_manager, "has_active_resource_work", lambda db=None: True)
    monkeypatch.setattr(
        resource_manager,
        "active_resource_snapshot",
        lambda db=None: {
            "generation_queue": {"queued": 0, "running": 0},
            "active_jobs": {"render_count": 1, "auto_run_count": 0, "generation_count": 0},
        },
    )

    actions = manager.unload_idle_models()

    assert actions[0].status == "kept_active"
    assert "đang có job active" in actions[0].message.lower()
    assert state.loaded is True


def test_resource_manager_heavy_model_limit_unloads_lru_idle_model(monkeypatch):
    manager = ResourceManager()
    oldest = _loaded_state(
        "tts:qwen:1.7B",
        last_used_at=datetime.utcnow() - timedelta(minutes=10),
        heavy=True,
    )
    newest = _loaded_state(
        "tts:tada:3B",
        engine="tada",
        model_size="3B",
        last_used_at=datetime.utcnow() - timedelta(minutes=1),
        heavy=True,
    )
    manager._models[oldest.key] = oldest
    manager._models[newest.key] = newest

    monkeypatch.setenv(resource_manager.RESOURCE_MAX_HEAVY_MODELS_ENV, "1")
    monkeypatch.setattr(resource_manager, "has_active_resource_work", lambda db=None: False)
    monkeypatch.setattr(resource_manager, "model_config_for_state", lambda _state: object())

    import backend.backends as backends

    unloaded: list[str] = []
    monkeypatch.setattr(backends, "unload_model_by_config", lambda _config: unloaded.append("yes") or True)

    actions = manager.enforce_heavy_model_limit()

    assert actions[0].status == "completed"
    assert actions[0].details["model_key"] == oldest.key
    assert unloaded == ["yes"]
    assert oldest.loaded is False
    assert newest.loaded is True


def test_mlx_cleanup_uses_optional_api_only_when_idle(monkeypatch):
    manager = ResourceManager()
    calls: list[str] = []

    mlx_package = types.ModuleType("mlx")
    mlx_core = types.ModuleType("mlx.core")
    mlx_core.get_cache_memory = lambda: 700 * 1024 * 1024
    mlx_core.clear_cache = lambda: calls.append("clear")
    mlx_core.metal = types.SimpleNamespace(get_active_memory=lambda: 123 * 1024 * 1024)
    mlx_package.core = mlx_core
    monkeypatch.setitem(sys.modules, "mlx", mlx_package)
    monkeypatch.setitem(sys.modules, "mlx.core", mlx_core)
    monkeypatch.setenv(resource_manager.MLX_CLEANUP_CACHE_MB_ENV, "512")

    monkeypatch.setattr(resource_manager, "has_active_resource_work", lambda db=None: True)
    active_action = manager.clear_mlx_cache_if_safe()
    assert active_action.status == "kept_active"
    assert calls == []

    monkeypatch.setattr(resource_manager, "has_active_resource_work", lambda db=None: False)
    loading_state = _loaded_state("tts:qwen:1.7B")
    loading_state.loading = True
    manager._models[loading_state.key] = loading_state
    loading_action = manager.clear_mlx_cache_if_safe()
    assert loading_action.status == "kept_active"
    assert loading_action.details["loading_models"] == [loading_state.key]
    assert calls == []

    loading_state.loading = False
    idle_action = manager.clear_mlx_cache_if_safe()
    assert idle_action.status == "completed"
    assert calls == ["clear"]


def test_voice_prompt_cache_lru_eviction_keeps_disk_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_cache.config, "get_cache_dir", lambda: tmp_path)
    monkeypatch.setenv(voice_cache.VOICE_PROMPT_MEMORY_MAX_ENTRIES_ENV, "1")
    voice_cache.clear_voice_prompt_cache()
    voice_cache._cache_stats.update(
        {
            "hits_memory": 0,
            "hits_disk": 0,
            "misses": 0,
            "evictions": 0,
        }
    )

    voice_cache.cache_voice_prompt("a", torch.tensor([1.0]))
    voice_cache.cache_voice_prompt("b", torch.tensor([2.0]))

    assert (tmp_path / "a.prompt").exists()
    assert voice_cache.get_voice_prompt_cache_stats()["entries"] == 1

    restored = voice_cache.get_cached_voice_prompt("a")

    assert torch.equal(restored, torch.tensor([1.0]))
    stats = voice_cache.get_voice_prompt_cache_stats()
    assert stats["hits_disk"] == 1
    assert stats["entries"] == 1

    result = voice_cache.clear_voice_prompt_memory_cache()
    assert result["entries_cleared"] == 1
    assert (tmp_path / "a.prompt").exists()


def test_render_cache_hits_same_clip_and_misses_changed_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(video_rendering.video_storage.config, "get_data_dir", lambda: tmp_path)
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"clip-v1")
    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], *, timeout: int = 600):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"normalized")

    monkeypatch.setattr(video_rendering, "_run_command", fake_run_command)

    first_path, first_hit = video_rendering._normalize_clip_with_cache(
        project_id="project-1",
        ffmpeg="ffmpeg",
        input_path=input_path,
        target_duration=2.0,
        clip_duration=1.5,
        width=720,
        height=1280,
        fps=30,
        fit_mode="crop",
        background_color="#000000",
        freeze_short_clip=True,
    )
    second_path, second_hit = video_rendering._normalize_clip_with_cache(
        project_id="project-1",
        ffmpeg="ffmpeg",
        input_path=input_path,
        target_duration=2.0,
        clip_duration=1.5,
        width=720,
        height=1280,
        fps=30,
        fit_mode="crop",
        background_color="#000000",
        freeze_short_clip=True,
    )
    changed_path, changed_hit = video_rendering._normalize_clip_with_cache(
        project_id="project-1",
        ffmpeg="ffmpeg",
        input_path=input_path,
        target_duration=2.0,
        clip_duration=1.5,
        width=1080,
        height=1920,
        fps=30,
        fit_mode="crop",
        background_color="#000000",
        freeze_short_clip=True,
    )

    assert first_hit is False
    assert second_hit is True
    assert changed_hit is False
    assert first_path == second_path
    assert changed_path != first_path
    assert len(calls) == 2


def test_render_cache_prune_uses_age_and_quota(monkeypatch, tmp_path):
    monkeypatch.setattr(video_rendering.video_storage.config, "get_data_dir", lambda: tmp_path)
    cache_dir = video_rendering.video_storage.get_project_subdir("project-1", "render_cache")
    old_file = cache_dir / "old.mp4"
    newest_file = cache_dir / "newest.mp4"
    older_file = cache_dir / "older.mp4"
    old_file.write_bytes(b"x" * 10)
    newest_file.write_bytes(b"x" * 800_000)
    older_file.write_bytes(b"x" * 800_000)

    old_time = (datetime.utcnow() - timedelta(days=20)).timestamp()
    older_time = (datetime.utcnow() - timedelta(hours=2)).timestamp()
    newest_time = datetime.utcnow().timestamp()
    os.utime(old_file, (old_time, old_time))
    os.utime(older_file, (older_time, older_time))
    os.utime(newest_file, (newest_time, newest_time))

    result = video_rendering.prune_render_intermediate_cache(
        project_id="project-1",
        max_age_days=14,
        max_mb=1,
    )

    assert result["deleted_by_age"] == 1
    assert result["deleted_by_quota"] == 1
    assert not old_file.exists()
    assert not older_file.exists()
    assert newest_file.exists()


def test_resource_status_and_cleanup_api(monkeypatch):
    class DummyManager:
        def status(self, db=None):
            return _status_payload()

        def cleanup(self, **kwargs):
            return [
                resource_manager.CleanupAction(
                    action="clear_voice_prompt_memory",
                    status="completed",
                    message="done",
                )
            ]

    app = FastAPI()
    app.dependency_overrides[resources.get_db] = lambda: None
    app.include_router(resources.router)
    monkeypatch.setattr(resources, "get_resource_manager", lambda: DummyManager())

    client = TestClient(app)

    status_response = client.get("/resources/status")
    cleanup_response = client.post("/resources/cleanup", json={})

    assert status_response.status_code == 200
    assert status_response.json()["models"] == []
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["actions"][0]["status"] == "completed"
