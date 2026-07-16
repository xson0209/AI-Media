"""Backend startup and shutdown lifecycle."""

from __future__ import annotations

import asyncio
import logging
import platform
import sys
from pathlib import Path

import torch
from fastapi import FastAPI

from .. import __version__, config, database
from ..database import get_db
from ..services import llm, transcribe, tts
from ..services.task_queue import create_background_task, init_queue
from ..utils.platform_detect import get_backend_type
from ..utils.progress import get_progress_manager
from .asyncio_windows import install_proactor_connection_reset_suppression

logger = logging.getLogger(__name__)


def get_gpu_status() -> str:
    """Return a human-readable string describing GPU availability."""
    backend_type = get_backend_type()
    if torch.cuda.is_available():
        from ..backends.base import check_cuda_compatibility

        device_name = torch.cuda.get_device_name(0)
        compatible, _warning = check_cuda_compatibility()
        is_rocm = hasattr(torch.version, "hip") and torch.version.hip is not None
        if is_rocm:
            label = f"ROCm ({device_name})"
        else:
            label = f"CUDA ({device_name})"
        if not compatible:
            label += " [UNSUPPORTED - see logs]"
        return label
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "MPS (Apple Silicon)"
    if backend_type == "mlx":
        return "Metal (Apple Silicon via MLX)"

    try:
        import intel_extension_for_pytorch  # noqa: F401

        if hasattr(torch, "xpu") and torch.xpu.is_available():
            try:
                xpu_name = torch.xpu.get_device_name(0)
            except Exception:
                xpu_name = "Intel GPU"
            return f"XPU ({xpu_name})"
    except ImportError:
        pass

    return "None (CPU only)"


async def run_startup(application: FastAPI) -> None:
    """Database init, warnings, model-cache prep. Runs on lifespan entry."""
    try:
        install_proactor_connection_reset_suppression(asyncio.get_running_loop())
    except Exception as e:
        logger.warning("Could not install asyncio Windows compatibility handler: %s", e)

    logger.info("Voicebox v%s starting up", __version__)
    logger.info(
        "Python %s on %s %s (%s)",
        sys.version.split()[0],
        platform.system(),
        platform.release(),
        platform.machine(),
    )

    database.init_db()

    from ..database.session import _db_path

    logger.info("Database: %s", _db_path)
    logger.info("Data directory: %s", config.get_data_dir())

    init_queue()

    from sqlalchemy import text as sa_text

    db = next(get_db())
    try:
        result = db.execute(
            sa_text(
                "UPDATE generations SET status = 'failed', "
                "error = 'Server was shut down during generation' "
                "WHERE status IN ('queued', 'generating', 'loading_model')"
            )
        )
        if result.rowcount > 0:
            logger.info("Marked %d stale generation(s) as failed", result.rowcount)

        from ..services import video_auto_runs, video_clip_generation, video_inspiration_runs, video_rendering

        stale_render_count = video_rendering.sync_stale_running_jobs(db)
        if stale_render_count > 0:
            logger.info("Marked %d stale video render job(s) as failed", stale_render_count)

        stale_auto_run_count = video_auto_runs.sync_stale_running_runs(db)
        if stale_auto_run_count > 0:
            logger.info("Marked %d stale AI Video auto-run(s) as failed", stale_auto_run_count)

        stale_clip_generation_count = video_clip_generation.sync_stale_running_jobs(db)
        if stale_clip_generation_count > 0:
            logger.info("Marked %d stale AI Video clip generation job(s) as failed", stale_clip_generation_count)

        stale_inspiration_count = video_inspiration_runs.sync_interrupted_jobs(db)
        if stale_inspiration_count > 0:
            logger.info("Marked %d interrupted Video Inspiration job(s) as failed", stale_inspiration_count)

        try:
            from ..services.comic_series_analysis import runner as comic_runner

            stale_comic_count = comic_runner.recover_interrupted_jobs(db)
            if stale_comic_count > 0:
                logger.info("Recovered %d interrupted Comic Analysis job(s)", stale_comic_count)
        except Exception as comic_exc:
            logger.warning("Could not recover Comic Analysis jobs: %s", comic_exc)

        from ..database import Generation as DBGeneration, VoiceProfile as DBVoiceProfile

        profile_count = db.query(DBVoiceProfile).count()
        generation_count = db.query(DBGeneration).count()
        logger.info("Profiles: %d, Generations: %d", profile_count, generation_count)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Could not clean up stale generations: %s", e)
    finally:
        db.close()

    backend_type = get_backend_type()
    logger.info("Backend: %s", backend_type.upper())
    logger.info("GPU: %s", get_gpu_status())

    from ..backends.base import check_cuda_compatibility

    _compatible, _cuda_warning = check_cuda_compatibility()
    if not _compatible:
        logger.warning("GPU COMPATIBILITY: %s", _cuda_warning)

    from ..services.cuda import check_and_update_cuda_binary

    create_background_task(check_and_update_cuda_binary())
    try:
        from ..services.resource_manager import get_resource_manager

        get_resource_manager().apply_mlx_cache_limit()
        create_background_task(get_resource_manager().periodic_cleanup())
    except Exception as e:
        logger.warning("Could not initialize resource manager cleanup: %s", e)

    try:
        progress_manager = get_progress_manager()
        progress_manager._set_main_loop(asyncio.get_running_loop())
    except Exception as e:
        logger.warning("Could not initialize progress manager event loop: %s", e)

    try:
        from huggingface_hub import constants as hf_constants

        cache_dir = Path(hf_constants.HF_HUB_CACHE)
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Model cache: %s", cache_dir)
    except Exception as e:
        logger.warning("Could not create HuggingFace cache directory: %s", e)

    logger.info("Ready")


async def run_shutdown() -> None:
    """Unload models on lifespan exit."""
    logger.info("Voicebox server shutting down...")
    try:
        tts.unload_tts_model()
    except Exception:
        logger.exception("Failed to unload TTS model")
    try:
        transcribe.unload_whisper_model()
    except Exception:
        logger.exception("Failed to unload Whisper model")
    try:
        llm.unload_llm_model()
    except Exception:
        logger.exception("Failed to unload LLM model")
