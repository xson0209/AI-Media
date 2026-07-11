"""Transcription endpoints."""

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import models
from ..services import transcribe
from ..services.task_queue import create_background_task
from ..utils.tasks import get_task_manager

router = APIRouter()

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB


@router.post("/transcribe", response_model=models.TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    model: str | None = Form(None),
    trim_start_seconds: float | None = Form(None),
    trim_duration_seconds: float | None = Form(None),
):
    """Transcribe audio file to text."""
    allowed_audio_exts = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm", ".opus"}
    uploaded_ext = Path(file.filename or "").suffix.lower()
    file_suffix = uploaded_ext if uploaded_ext in allowed_audio_exts else ".wav"

    with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            tmp.write(chunk)
        tmp_path = tmp.name
    transcribe_path = tmp_path
    segment_path: str | None = None

    try:
        from ..utils.audio import (
            MAX_REFERENCE_AUDIO_DURATION_SECONDS,
            load_audio,
            load_audio_segment,
            save_audio,
        )
        from ..backends import WHISPER_HF_REPOS

        has_trim_start = trim_start_seconds is not None
        has_trim_duration = trim_duration_seconds is not None
        if has_trim_start != has_trim_duration:
            raise HTTPException(
                status_code=400,
                detail="Audio segment start and duration are required together",
            )

        if has_trim_start and has_trim_duration:
            assert trim_start_seconds is not None
            assert trim_duration_seconds is not None
            if trim_duration_seconds > MAX_REFERENCE_AUDIO_DURATION_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Audio segment too long (maximum {MAX_REFERENCE_AUDIO_DURATION_SECONDS} seconds)",
                )
            audio, sr = await asyncio.to_thread(
                load_audio_segment,
                tmp_path,
                offset=trim_start_seconds,
                duration=trim_duration_seconds,
            )
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as segment_tmp:
                segment_path = segment_tmp.name
            await asyncio.to_thread(save_audio, audio, segment_path, sr)
            transcribe_path = segment_path
        else:
            audio, sr = await asyncio.to_thread(load_audio, tmp_path)
        duration = len(audio) / sr

        whisper_model = transcribe.get_whisper_model()
        model_size = model if model else whisper_model.model_size

        valid_sizes = list(WHISPER_HF_REPOS.keys())
        if model_size not in valid_sizes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model size '{model_size}'. Must be one of: {', '.join(valid_sizes)}",
            )

        already_loaded = whisper_model.is_loaded() and whisper_model.model_size == model_size
        if not already_loaded and not whisper_model._is_model_cached(model_size):
            progress_model_name = f"whisper-{model_size}"
            task_manager = get_task_manager()

            async def download_whisper_background():
                try:
                    from ..services.resource_manager import get_resource_manager
                    from ..utils.platform_detect import get_backend_type

                    manager = get_resource_manager()
                    manager.prepare_model_load(kind="stt", engine="whisper", model_size=model_size, backend_type=get_backend_type())
                    await whisper_model.load_model_async(model_size)
                    manager.record_model_used(kind="stt", engine="whisper", model_size=model_size, backend_type=get_backend_type())
                    task_manager.complete_download(progress_model_name)
                except Exception as e:
                    task_manager.error_download(progress_model_name, str(e))

            task_manager.start_download(progress_model_name)
            create_background_task(download_whisper_background())

            raise HTTPException(
                status_code=202,
                detail={
                    "message": f"Whisper model {model_size} is being downloaded. Please wait and try again.",
                    "model_name": progress_model_name,
                    "downloading": True,
                },
            )

        from ..services.resource_manager import get_resource_manager
        from ..utils.platform_detect import get_backend_type

        manager = get_resource_manager()
        manager.prepare_model_load(kind="stt", engine="whisper", model_size=model_size, backend_type=get_backend_type())
        await whisper_model.load_model_async(model_size)
        manager.record_model_used(kind="stt", engine="whisper", model_size=model_size, backend_type=get_backend_type())
        text = await whisper_model.transcribe(transcribe_path, language, model_size)
        manager.record_model_used(kind="stt", engine="whisper", model_size=model_size, backend_type=get_backend_type())

        return models.TranscriptionResponse(
            text=text,
            duration=duration,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if segment_path is not None:
            Path(segment_path).unlink(missing_ok=True)
