"""Local RAM/GPU resource management for AI Video workflows."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..database import (
    VideoAutoRun as DBVideoAutoRun,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoRenderJob as DBVideoRenderJob,
    get_db,
)
from ..utils.platform_detect import get_backend_type
from ..utils.tasks import get_task_manager

logger = logging.getLogger(__name__)

RESOURCE_IDLE_UNLOAD_SECONDS_ENV = "VOICEBOX_RESOURCE_IDLE_UNLOAD_SECONDS"
RESOURCE_CLEANUP_INTERVAL_SECONDS_ENV = "VOICEBOX_RESOURCE_CLEANUP_INTERVAL_SECONDS"
RESOURCE_MAX_HEAVY_MODELS_ENV = "VOICEBOX_RESOURCE_MAX_HEAVY_MODELS"
RESOURCE_HEAVY_MODEL_MB_ENV = "VOICEBOX_RESOURCE_HEAVY_MODEL_MB"
RESOURCE_MEMORY_WARNING_PERCENT_ENV = "VOICEBOX_RESOURCE_MEMORY_WARNING_PERCENT"
RESOURCE_MEMORY_CRITICAL_PERCENT_ENV = "VOICEBOX_RESOURCE_MEMORY_CRITICAL_PERCENT"
MLX_CACHE_LIMIT_MB_ENV = "VOICEBOX_MLX_CACHE_LIMIT_MB"
MLX_CLEANUP_CACHE_MB_ENV = "VOICEBOX_MLX_CLEANUP_CACHE_MB"


@dataclass
class ModelRuntimeState:
    key: str
    kind: str
    engine: str
    model_size: str | None = None
    display_name: str | None = None
    backend_type: str | None = None
    size_mb: float | None = None
    heavy: bool = False
    loaded: bool = False
    loading: bool = False
    loaded_at: datetime | None = None
    last_used_at: datetime | None = None
    last_unloaded_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        now = datetime.utcnow()
        idle_seconds = None
        if self.loaded and self.last_used_at is not None:
            idle_seconds = max(0.0, (now - self.last_used_at).total_seconds())
        return {
            "key": self.key,
            "kind": self.kind,
            "engine": self.engine,
            "model_size": self.model_size,
            "display_name": self.display_name,
            "backend_type": self.backend_type,
            "size_mb": self.size_mb,
            "heavy": self.heavy,
            "loaded": self.loaded,
            "loading": self.loading,
            "loaded_at": self.loaded_at,
            "last_used_at": self.last_used_at,
            "last_unloaded_at": self.last_unloaded_at,
            "idle_seconds": idle_seconds,
        }


@dataclass
class CleanupAction:
    action: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


class ResourceManager:
    """Tracks local model/cache usage and performs conservative cleanup."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._models: dict[str, ModelRuntimeState] = {}
        self._cleanup_events: list[dict[str, Any]] = []
        self._mlx_limit_applied_mb: int | None = None

    def policy(self) -> dict[str, Any]:
        return {
            "idle_unload_seconds": _int_env(RESOURCE_IDLE_UNLOAD_SECONDS_ENV, 600),
            "cleanup_interval_seconds": _int_env(RESOURCE_CLEANUP_INTERVAL_SECONDS_ENV, 60),
            "max_loaded_heavy_models": _int_env(RESOURCE_MAX_HEAVY_MODELS_ENV, 1),
            "heavy_model_threshold_mb": _float_env(RESOURCE_HEAVY_MODEL_MB_ENV, 1000.0),
            "memory_warning_percent": _float_env(RESOURCE_MEMORY_WARNING_PERCENT_ENV, 75.0),
            "memory_critical_percent": _float_env(RESOURCE_MEMORY_CRITICAL_PERCENT_ENV, 85.0),
            "mlx_cache_limit_mb": _optional_int_env(MLX_CACHE_LIMIT_MB_ENV),
            "mlx_cleanup_cache_mb": _int_env(MLX_CLEANUP_CACHE_MB_ENV, 512),
        }

    def model_key(self, kind: str, engine: str, model_size: str | None = None) -> str:
        return f"{kind}:{engine}:{model_size or 'default'}"

    def prepare_model_load(
        self,
        *,
        kind: str,
        engine: str,
        model_size: str | None = None,
        backend_type: str | None = None,
    ) -> None:
        """Mark a model as loading and enforce conservative heavy-model policy."""
        state = self._ensure_model_state(
            kind=kind,
            engine=engine,
            model_size=model_size,
            backend_type=backend_type,
        )
        with self._lock:
            state.loading = True
            state.last_used_at = datetime.utcnow()
        self.apply_mlx_cache_limit()
        self.unload_idle_models()
        self.enforce_heavy_model_limit(next_model_key=state.key)

    def record_model_used(
        self,
        *,
        kind: str,
        engine: str,
        model_size: str | None = None,
        backend_type: str | None = None,
    ) -> None:
        state = self._ensure_model_state(
            kind=kind,
            engine=engine,
            model_size=model_size,
            backend_type=backend_type,
        )
        now = datetime.utcnow()
        with self._lock:
            state.loaded = True
            state.loading = False
            state.loaded_at = state.loaded_at or now
            state.last_used_at = now

    def record_model_unloaded(
        self,
        *,
        kind: str,
        engine: str,
        model_size: str | None = None,
    ) -> None:
        key = self.model_key(kind, engine, model_size)
        with self._lock:
            state = self._models.get(key)
            if state is None:
                return
            state.loaded = False
            state.loading = False
            state.loaded_at = None
            state.last_unloaded_at = datetime.utcnow()

    def status(self, db: Session | None = None) -> dict[str, Any]:
        memory = memory_pressure_snapshot(self.policy())
        queue = generation_queue_snapshot()
        workflow_pool = workflow_pool_snapshot()
        planning_pool = planning_pool_snapshot()
        stt_pool = stt_pool_snapshot()
        active = active_job_snapshot(db)
        voice_cache = voice_prompt_cache_snapshot()
        render_cache = render_cache_snapshot()
        mlx = mlx_memory_snapshot()
        with self._lock:
            models = [state.as_dict() for state in self._models.values()]
            recent_events = list(self._cleanup_events[-20:])
        return {
            "sampled_at": datetime.utcnow(),
            "policy": self.policy(),
            "memory": memory,
            "generation_queue": queue,
            "workflow_pool": workflow_pool,
            "planning_pool": planning_pool,
            "stt_pool": stt_pool,
            "active_jobs": active,
            "models": sorted(models, key=lambda item: item.get("key") or ""),
            "voice_prompt_cache": voice_cache,
            "render_cache": render_cache,
            "mlx": mlx,
            "recent_events": recent_events,
        }

    def cleanup(
        self,
        *,
        db: Session | None = None,
        unload_idle_models: bool = True,
        clear_voice_prompt_memory: bool = True,
        clear_mlx_cache: bool = True,
        clear_render_cache: bool = False,
        render_cache_project_id: str | None = None,
    ) -> list[CleanupAction]:
        actions: list[CleanupAction] = []

        if clear_voice_prompt_memory:
            try:
                from ..utils.cache import clear_voice_prompt_memory_cache

                result = clear_voice_prompt_memory_cache()
                actions.append(
                    CleanupAction(
                        action="clear_voice_prompt_memory",
                        status="completed",
                        message="Đã xóa voice prompt memory cache.",
                        details=result,
                    )
                )
            except Exception as exc:
                logger.exception("Failed to clear voice prompt memory cache")
                actions.append(
                    CleanupAction(
                        action="clear_voice_prompt_memory",
                        status="failed",
                        message="Không xóa được voice prompt memory cache.",
                        details={"error": str(exc)},
                    )
                )

        if unload_idle_models:
            actions.extend(self.unload_idle_models(db=db, force_all_idle=True))

        if clear_mlx_cache:
            actions.append(self.clear_mlx_cache_if_safe(db=db, force=True))

        if clear_render_cache:
            try:
                from . import video_rendering

                result = video_rendering.clear_render_intermediate_cache(
                    project_id=render_cache_project_id,
                    db=db,
                )
                actions.append(
                    CleanupAction(
                        action="clear_render_cache",
                        status="completed",
                        message="Đã dọn render intermediate cache.",
                        details=result,
                    )
                )
            except Exception as exc:
                logger.exception("Failed to clear render cache")
                actions.append(
                    CleanupAction(
                        action="clear_render_cache",
                        status="failed",
                        message="Không dọn được render intermediate cache.",
                        details={"error": str(exc)},
                    )
                )

        self._remember_events(actions)
        return actions

    def unload_idle_models(
        self,
        *,
        db: Session | None = None,
        force_all_idle: bool = False,
    ) -> list[CleanupAction]:
        actions: list[CleanupAction] = []
        if has_active_resource_work(db):
            actions.append(
                CleanupAction(
                    action="unload_idle_models",
                    status="kept_active",
                    message="Đang có job active nên chưa unload model.",
                    details=active_resource_snapshot(db),
                )
            )
            return actions

        now = datetime.utcnow()
        idle_seconds = self.policy()["idle_unload_seconds"]
        with self._lock:
            candidates = [
                state
                for state in self._models.values()
                if state.loaded
                and not state.loading
                and (
                    force_all_idle
                    or (
                        state.last_used_at is not None
                        and (now - state.last_used_at).total_seconds() >= idle_seconds
                    )
                )
            ]
        for state in sorted(candidates, key=lambda item: item.last_used_at or datetime.min):
            actions.append(self._unload_state(state, reason="idle_timeout" if not force_all_idle else "manual_cleanup"))
        if not candidates:
            actions.append(
                CleanupAction(
                    action="unload_idle_models",
                    status="skipped",
                    message="Không có model idle nào cần unload.",
                )
            )
        self._remember_events(actions)
        return actions

    def enforce_heavy_model_limit(self, *, next_model_key: str | None = None) -> list[CleanupAction]:
        actions: list[CleanupAction] = []
        if has_active_resource_work():
            return actions
        max_loaded = int(self.policy()["max_loaded_heavy_models"])
        if max_loaded < 1:
            return actions
        with self._lock:
            heavy = [
                state
                for state in self._models.values()
                if state.loaded and state.heavy and not state.loading and state.key != next_model_key
            ]
        target_loaded = max(0, max_loaded - (1 if next_model_key else 0))
        if len(heavy) <= target_loaded:
            return actions
        for state in sorted(heavy, key=lambda item: item.last_used_at or datetime.min):
            if len(heavy) <= target_loaded:
                break
            actions.append(self._unload_state(state, reason="heavy_model_limit"))
            heavy.remove(state)
        self._remember_events(actions)
        return actions

    def apply_mlx_cache_limit(self) -> CleanupAction | None:
        limit_mb = self.policy().get("mlx_cache_limit_mb")
        if not limit_mb:
            return None
        if self._mlx_limit_applied_mb == limit_mb:
            return None
        try:
            import mlx.core as mx  # type: ignore

            if not hasattr(mx, "set_cache_limit"):
                return None
            mx.set_cache_limit(int(limit_mb) * 1024 * 1024)
            self._mlx_limit_applied_mb = int(limit_mb)
            action = CleanupAction(
                action="set_mlx_cache_limit",
                status="completed",
                message="Đã áp dụng giới hạn MLX cache.",
                details={"limit_mb": int(limit_mb)},
            )
            self._remember_events([action])
            return action
        except Exception as exc:
            logger.debug("MLX cache limit not applied: %s", exc)
            return None

    def clear_mlx_cache_if_safe(self, *, db: Session | None = None, force: bool = False) -> CleanupAction:
        snapshot = mlx_memory_snapshot()
        if not snapshot.get("available"):
            return CleanupAction(
                action="clear_mlx_cache",
                status="skipped",
                message="MLX không khả dụng trong runtime hiện tại.",
            )
        loading_keys = self.loading_model_keys()
        if loading_keys:
            return CleanupAction(
                action="clear_mlx_cache",
                status="kept_active",
                message="Đang load model nên chưa clear MLX cache.",
                details={"loading_models": loading_keys},
            )
        if has_active_resource_work(db):
            return CleanupAction(
                action="clear_mlx_cache",
                status="kept_active",
                message="Đang có job active nên chưa clear MLX cache.",
                details=active_resource_snapshot(db),
            )
        cache_mb = float(snapshot.get("cache_mb") or 0)
        threshold_mb = float(self.policy()["mlx_cleanup_cache_mb"])
        if not force and cache_mb < threshold_mb:
            return CleanupAction(
                action="clear_mlx_cache",
                status="skipped",
                message="MLX cache chưa vượt ngưỡng cleanup.",
                details={"cache_mb": cache_mb, "threshold_mb": threshold_mb},
            )
        try:
            import mlx.core as mx  # type: ignore

            mx.clear_cache()
            action = CleanupAction(
                action="clear_mlx_cache",
                status="completed",
                message="Đã clear MLX cache.",
                details={"before_cache_mb": cache_mb},
            )
            self._remember_events([action])
            return action
        except Exception as exc:
            logger.exception("Failed to clear MLX cache")
            return CleanupAction(
                action="clear_mlx_cache",
                status="failed",
                message="Không clear được MLX cache.",
                details={"error": str(exc)},
            )

    async def periodic_cleanup(self) -> None:
        while True:
            await asyncio.sleep(max(5, int(self.policy()["cleanup_interval_seconds"])))
            try:
                self.apply_mlx_cache_limit()
                self.unload_idle_models()
                memory = memory_pressure_snapshot(self.policy())
                critical = memory.get("status") == "critical"
                if critical:
                    self.clear_mlx_cache_if_safe()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Periodic resource cleanup failed")

    def _ensure_model_state(
        self,
        *,
        kind: str,
        engine: str,
        model_size: str | None,
        backend_type: str | None,
    ) -> ModelRuntimeState:
        key = self.model_key(kind, engine, model_size)
        metadata = model_metadata(kind=kind, engine=engine, model_size=model_size)
        with self._lock:
            state = self._models.get(key)
            if state is None:
                state = ModelRuntimeState(
                    key=key,
                    kind=kind,
                    engine=engine,
                    model_size=model_size,
                )
                self._models[key] = state
            state.backend_type = backend_type or state.backend_type or get_backend_type()
            state.display_name = metadata.get("display_name") or state.display_name
            state.size_mb = metadata.get("size_mb") if metadata.get("size_mb") is not None else state.size_mb
            threshold = float(self.policy()["heavy_model_threshold_mb"])
            state.heavy = bool((state.size_mb or 0) >= threshold)
            return state

    def _unload_state(self, state: ModelRuntimeState, *, reason: str) -> CleanupAction:
        config = model_config_for_state(state)
        if config is None:
            return CleanupAction(
                action="unload_model",
                status="skipped",
                message="Không tìm thấy config để unload model.",
                details={"model_key": state.key, "reason": reason},
            )
        try:
            from ..backends import unload_model_by_config

            was_loaded = unload_model_by_config(config)
            self.record_model_unloaded(kind=state.kind, engine=state.engine, model_size=state.model_size)
            return CleanupAction(
                action="unload_model",
                status="completed" if was_loaded else "skipped",
                message="Đã unload model idle." if was_loaded else "Model đã không còn loaded.",
                details={"model_key": state.key, "reason": reason},
            )
        except Exception as exc:
            logger.exception("Failed to unload model %s", state.key)
            return CleanupAction(
                action="unload_model",
                status="failed",
                message="Không unload được model.",
                details={"model_key": state.key, "reason": reason, "error": str(exc)},
            )

    def _remember_events(self, actions: list[CleanupAction]) -> None:
        if not actions:
            return
        now = datetime.utcnow().isoformat()
        with self._lock:
            for action in actions:
                self._cleanup_events.append({"at": now, **action.as_dict()})
            self._cleanup_events = self._cleanup_events[-50:]

    def loading_model_keys(self) -> list[str]:
        with self._lock:
            return sorted(state.key for state in self._models.values() if state.loading)


_manager = ResourceManager()


def get_resource_manager() -> ResourceManager:
    return _manager


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _optional_int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, str(default))))
    except ValueError:
        return default


def model_metadata(*, kind: str, engine: str, model_size: str | None) -> dict[str, Any]:
    config = model_config_lookup(kind=kind, engine=engine, model_size=model_size)
    if config is None:
        return {}
    return {
        "display_name": config.display_name,
        "size_mb": float(config.size_mb or 0),
        "model_name": config.model_name,
    }


def model_config_lookup(*, kind: str, engine: str, model_size: str | None):
    try:
        from ..backends import get_all_model_configs

        configs = get_all_model_configs()
    except Exception:
        return None
    for config in configs:
        if kind == "stt" and config.engine != "whisper":
            continue
        if kind == "llm" and config.engine != "qwen_llm":
            continue
        if kind == "tts" and config.engine != engine:
            continue
        if kind in {"stt", "llm"} and config.engine != engine:
            continue
        if (config.model_size or None) == (model_size or "default"):
            return config
        if model_size is None and config.engine == engine:
            return config
    return None


def model_config_for_state(state: ModelRuntimeState):
    return model_config_lookup(kind=state.kind, engine=state.engine, model_size=state.model_size)


def generation_queue_snapshot() -> dict[str, Any]:
    try:
        from .task_queue import get_generation_queue_snapshot

        return get_generation_queue_snapshot()
    except Exception:
        return {"queued": 0, "running": 0, "available": False}


def workflow_pool_snapshot() -> dict[str, Any]:
    try:
        from .video_workflow_pool import snapshot

        return snapshot()
    except Exception:
        return {"queued": 0, "running": 0, "max_concurrency": 3, "available": False}


def planning_pool_snapshot() -> dict[str, Any]:
    try:
        from .video_planning_pool import resource_snapshot

        return resource_snapshot()
    except Exception:
        return {"queued": 0, "running": 0, "max_concurrency": 3, "available": False}


def stt_pool_snapshot() -> dict[str, Any]:
    try:
        from .video_inspiration_runs import get_stt_pool_snapshot

        return get_stt_pool_snapshot()
    except Exception:
        return {"queued": 0, "running": 0, "max_concurrency": 1, "available": False}


def has_active_generation_work() -> bool:
    queue = generation_queue_snapshot()
    if int(queue.get("queued") or 0) or int(queue.get("running") or 0):
        return True
    try:
        return bool(get_task_manager().get_active_generations())
    except Exception:
        return False

def active_resource_snapshot(db: Session | None = None) -> dict[str, Any]:
    return {
        "generation_queue": generation_queue_snapshot(),
        "workflow_pool": workflow_pool_snapshot(),
        "planning_pool": planning_pool_snapshot(),
        "stt_pool": stt_pool_snapshot(),
        "active_jobs": active_job_snapshot(db),
    }

def has_active_resource_work(db: Session | None = None) -> bool:
    if has_active_generation_work():
        return True
    for pool in (workflow_pool_snapshot(), planning_pool_snapshot(), stt_pool_snapshot()):
        if int(pool.get("queued") or 0) or int(pool.get("running") or 0):
            return True
    active = active_job_snapshot(db)
    return bool(
        int(active.get("generation_count") or 0)
        or int(active.get("render_count") or 0)
        or int(active.get("auto_run_count") or 0)
        or int(active.get("video_inspiration_count") or 0)
    )


def active_job_snapshot(db: Session | None = None) -> dict[str, Any]:
    active_generations = []
    try:
        active_generations = [
            {
                "task_id": task.task_id,
                "profile_id": task.profile_id,
                "text_preview": task.text_preview,
                "started_at": task.started_at,
            }
            for task in get_task_manager().get_active_generations()
        ]
    except Exception:
        active_generations = []

    render_count = 0
    auto_run_count = 0
    video_inspiration_count = 0
    close_db = False
    if db is None:
        try:
            db = next(get_db())
            close_db = True
        except Exception:
            db = None
    if db is not None:
        try:
            render_count = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.status.in_(["queued", "running"])).count()
            auto_run_count = db.query(DBVideoAutoRun).filter(
                DBVideoAutoRun.status.in_(["queued", "waiting_workflow", "running", "waiting_planning", "waiting_voice"])
            ).count()
            video_inspiration_count = db.query(DBVideoInspirationJob).filter(
                DBVideoInspirationJob.status.in_(["analyzing", "rewriting", "handoff"])
            ).count()
        except Exception:
            render_count = 0
            auto_run_count = 0
            video_inspiration_count = 0
        finally:
            if close_db:
                db.close()
    return {
        "generations": active_generations,
        "generation_count": len(active_generations),
        "render_count": int(render_count or 0),
        "auto_run_count": int(auto_run_count or 0),
        "video_inspiration_count": int(video_inspiration_count or 0),
    }


def voice_prompt_cache_snapshot() -> dict[str, Any]:
    try:
        from ..utils.cache import get_voice_prompt_cache_stats

        return get_voice_prompt_cache_stats()
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def render_cache_snapshot() -> dict[str, Any]:
    try:
        from . import video_rendering

        return video_rendering.get_render_intermediate_cache_stats()
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def mlx_memory_snapshot() -> dict[str, Any]:
    try:
        import mlx.core as mx  # type: ignore

        cache = _maybe_call(mx, "get_cache_memory")
        active = None
        metal = getattr(mx, "metal", None)
        if metal is not None:
            active = _maybe_call(metal, "get_active_memory")
        return {
            "available": True,
            "cache_bytes": cache,
            "cache_mb": _bytes_to_mb(cache),
            "active_bytes": active,
            "active_mb": _bytes_to_mb(active),
        }
    except Exception:
        return {"available": False}


def _maybe_call(obj: Any, name: str) -> int | None:
    fn = getattr(obj, name, None)
    if not callable(fn):
        return None
    try:
        value = fn()
    except Exception:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bytes_to_mb(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024 / 1024, 1)


def memory_pressure_snapshot(policy: dict[str, Any]) -> dict[str, Any]:
    stats = _memory_stats()
    if stats is None:
        return {"status": "unknown", "percent": None}
    used, total, percent = stats
    warning = float(policy.get("memory_warning_percent") or 75.0)
    critical = float(policy.get("memory_critical_percent") or 85.0)
    if percent >= critical:
        status = "critical"
    elif percent >= warning:
        status = "warning"
    else:
        status = "normal"
    return {
        "status": status,
        "percent": round(percent, 1),
        "used_mb": round(used / 1024 / 1024, 1),
        "total_mb": round(total / 1024 / 1024, 1),
    }


def _memory_stats() -> tuple[float, float, float] | None:
    if platform.system() == "Darwin":
        return _mac_memory_stats()
    if platform.system() == "Linux":
        return _linux_memory_stats()
    return None


def _run_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=1.5)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout


def _mac_memory_stats() -> tuple[float, float, float] | None:
    total_output = _run_command(["sysctl", "-n", "hw.memsize"])
    vm_output = _run_command(["vm_stat"])
    page_output = _run_command(["pagesize"])
    if not total_output or not vm_output:
        return None
    try:
        total = float(total_output.strip())
        page_size = float(page_output.strip()) if page_output else 4096.0
    except ValueError:
        return None
    pages: dict[str, float] = {}
    for line in vm_output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        try:
            pages[key.strip()] = float(value.strip().rstrip("."))
        except ValueError:
            continue
    free_pages = pages.get("Pages free", 0.0) + pages.get("Pages speculative", 0.0)
    inactive_pages = pages.get("Pages inactive", 0.0)
    compressed_pages = pages.get("Pages occupied by compressor", 0.0)
    available = max(0.0, (free_pages + inactive_pages - compressed_pages) * page_size)
    used = max(0.0, min(total, total - available))
    percent = (used / total) * 100 if total else 0.0
    return used, total, percent


def _linux_memory_stats() -> tuple[float, float, float] | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    values: dict[str, float] = {}
    try:
        for line in meminfo.read_text().splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = float(raw_value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    used = max(0.0, total - available)
    percent = (used / total) * 100 if total else 0.0
    return used, total, percent
