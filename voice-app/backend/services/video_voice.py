"""AI Video scene narration using the existing Voicebox generation pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .. import config, models
from ..database import (
    Generation as DBGeneration,
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoShot as DBVideoShot,
)
from ..utils.tasks import get_task_manager
from . import (
    history,
    profiles,
    qwen_vietnamese,
    tada_vietnamese,
    video_errors,
    video_language,
    video_observability,
    video_rendering,
    video_state,
    video_storage,
)
from .generation import run_generation
from .task_queue import enqueue_generation


class VideoVoiceError(ValueError):
    """Raised when scene narration cannot be created."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_VOICE_ERROR"):
        super().__init__(message)
        self.error_code = error_code

ENGINE_LANGUAGE_SUPPORT: dict[str, set[str]] = {
    "qwen": {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"},
    "qwen_custom_voice": {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"},
    "luxtts": {"en"},
    "chatterbox": {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh"},
    "chatterbox_turbo": {"en"},
    "tada": {"en", "ar", "zh", "de", "es", "fr", "it", "ja", "pl", "pt"},
    "kokoro": {"en", "es", "fr", "hi", "it", "pt", "ja", "zh"},
}


def _resolve_generation_engine(
    data: models.VideoSceneNarrationRequest,
    profile,
    language: str,
) -> str:
    engine = data.engine or getattr(profile, "default_engine", None) or getattr(profile, "preset_engine", None)
    return qwen_vietnamese.resolve_engine(profile=profile, engine=engine, language=language)


def _language_for_project(project: DBVideoProject, data: models.VideoSceneNarrationRequest) -> str:
    if data.language:
        return data.language
    language = video_language.normalize_video_language(getattr(project, "target_language", None))
    supported = {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", "he", "ar", "da", "el", "fi", "hi", "ms", "nl", "no", "pl", "sv", "sw", "tr", "vi"}
    return language if language in supported else "en"

def _resolve_model_size(engine: str, data: models.VideoSceneNarrationRequest, language: str) -> str | None:
    from ..backends import engine_has_model_sizes

    if not engine_has_model_sizes(engine):
        return None

    model_size = tada_vietnamese.normalize_tada_model_size(
        engine=engine,
        language=language,
        model_size=data.model_size or "1.7B",
    )
    return qwen_vietnamese.normalize_model_size(
        engine=engine,
        language=language,
        model_size=model_size,
    )

def _ensure_language_allowed(profile, engine: str, model_size: str | None, language: str) -> bool:
    supported = ENGINE_LANGUAGE_SUPPORT.get(engine)
    try:
        qwen_vietnamese.ensure_qwen_vietnamese_allowed(
            profile=profile,
            engine=engine,
            model_size=model_size,
            language=language,
        )
    except ValueError as exc:
        raise VideoVoiceError(str(exc), error_code="VIDEO_VOICE_LANGUAGE_UNSUPPORTED") from exc
    allow_qwen_vi_bypass = qwen_vietnamese.should_allow_profile_bypass(
        profile=profile,
        engine=engine,
        model_size=model_size,
        language=language,
    )
    if supported is not None and language not in supported and not allow_qwen_vi_bypass:
        raise VideoVoiceError(
            f"Engine '{engine}' không hỗ trợ tạo voice cho ngôn ngữ video '{language}'. Hãy chọn engine/voice khác.",
            error_code="VIDEO_VOICE_LANGUAGE_UNSUPPORTED",
        )
    allow_tada_vi_bypass = tada_vietnamese.should_allow_profile_bypass(
        profile=profile,
        engine=engine,
        model_size=model_size,
        language=language,
    )
    try:
        tada_vietnamese.ensure_tada_vietnamese_allowed(
            engine=engine,
            model_size=model_size,
            language=language,
            allow_evaluation=allow_tada_vi_bypass,
        )
    except ValueError as exc:
        if language == "vi":
            raise VideoVoiceError(
                "Engine hoặc model đã chọn chưa sẵn sàng tạo voice tiếng Việt cho AI Video. "
                "Hãy chọn voice/engine hỗ trợ tiếng Việt hoặc hoàn tất bước đánh giá tiếng Việt trước.",
                error_code="VIDEO_VOICE_LANGUAGE_UNSUPPORTED",
            ) from exc
        raise VideoVoiceError(str(exc), error_code="VIDEO_VOICE_LANGUAGE_UNSUPPORTED") from exc
    return allow_tada_vi_bypass

def _ensure_profile_language_allowed(profile, language: str) -> None:
    profile_language = (getattr(profile, "language", None) or "").strip().lower()
    if profile_language and profile_language != language:
        raise VideoVoiceError(
            f"Voice profile đang là '{profile_language}' nhưng ngôn ngữ video là '{language}'. Hãy chọn voice profile đúng ngôn ngữ.",
            error_code="VIDEO_VOICE_PROFILE_LANGUAGE_MISMATCH",
        )


def _audio_url_from_generation(generation_id: str | None) -> str | None:
    if not generation_id:
        return None
    return f"/audio/{generation_id}"

def _audio_url(scene: DBVideoScene) -> str | None:
    return _audio_url_from_generation(scene.generation_id)

def _shot_audio_url(shot: DBVideoShot) -> str | None:
    return _audio_url_from_generation(shot.generation_id)


def _status_response(scene: DBVideoScene) -> models.VideoSceneVoiceStatusResponse:
    return models.VideoSceneVoiceStatusResponse(
        project_id=scene.project_id,
        scene_id=scene.id,
        scene_order=scene.scene_order,
        no_narration=bool(scene.no_narration),
        voice_status=scene.voice_status,
        generation_id=scene.generation_id,
        audio_path=scene.audio_path,
        audio_url=_audio_url(scene),
        audio_duration=scene.audio_duration,
        failure_reason=scene.voice_failure_reason,
    )

def _shot_status_response(shot: DBVideoShot) -> models.VideoShotVoiceStatusResponse:
    return models.VideoShotVoiceStatusResponse(
        project_id=shot.project_id,
        shot_id=shot.id,
        shot_order=shot.shot_order,
        scene_id=shot.scene_id,
        voice_status=shot.voice_status,
        generation_id=shot.generation_id,
        audio_path=shot.audio_path,
        audio_url=_shot_audio_url(shot),
        audio_duration=shot.audio_duration,
        failure_reason=shot.voice_failure_reason,
    )


def _get_scene(project_id: str, scene_id: str, db: Session) -> tuple[DBVideoProject, DBVideoScene] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if project is None or scene is None:
        return None
    return project, scene

def _get_shot(project_id: str, shot_id: str, db: Session) -> tuple[DBVideoProject, DBVideoShot] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shot = (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id)
        .first()
    )
    if project is None or shot is None:
        return None
    return project, shot

def _log_voice_failure(
    db: Session,
    *,
    project_id: str,
    message: str,
    error_code: str,
    scene_id: str | None = None,
    shot_id: str | None = None,
    details: dict | None = None,
) -> None:
    video_observability.log_event(
        db,
        step_name="voice_generation_validation",
        status="failure",
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        error_code=error_code,
        message=message,
        technical_details=details,
    )


def sync_scene_voice_status(project_id: str, scene_id: str, db: Session) -> models.VideoSceneVoiceStatusResponse | None:
    result = _get_scene(project_id, scene_id, db)
    if result is None:
        return None
    _project, scene = result
    if not scene.generation_id:
        return _status_response(scene)

    generation = db.query(DBGeneration).filter(DBGeneration.id == scene.generation_id).first()
    if generation is None:
        scene.voice_status = "failed"
        scene.voice_failure_reason = "Không tìm thấy generation đã liên kết với scene."
    elif generation.status == "completed":
        scene.voice_status = "completed"
        scene.audio_path = generation.audio_path
        scene.audio_duration = generation.duration
        scene.voice_failure_reason = None
    elif generation.status == "failed":
        scene.voice_status = "failed"
        scene.voice_failure_reason = generation.error or "Tạo giọng đọc thất bại."
    else:
        scene.voice_status = generation.status or "generating"
    scene.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return _status_response(scene)

def sync_shot_voice_status(project_id: str, shot_id: str, db: Session) -> models.VideoShotVoiceStatusResponse | None:
    result = _get_shot(project_id, shot_id, db)
    if result is None:
        return None
    _project, shot = result
    if not shot.generation_id:
        return _shot_status_response(shot)

    generation = db.query(DBGeneration).filter(DBGeneration.id == shot.generation_id).first()
    if generation is None:
        shot.voice_status = "failed"
        shot.voice_failure_reason = "Không tìm thấy generation đã liên kết với shot."
    elif generation.status == "completed":
        shot.voice_status = "completed"
        shot.audio_path = generation.audio_path
        shot.audio_duration = generation.duration
        shot.voice_failure_reason = None
    elif generation.status == "failed":
        shot.voice_status = "failed"
        shot.voice_failure_reason = generation.error or "Tạo giọng đọc cho shot thất bại."
    else:
        shot.voice_status = generation.status or "generating"
    shot.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(shot)
    return _shot_status_response(shot)


async def create_scene_narration(
    project_id: str,
    scene_id: str,
    data: models.VideoSceneNarrationRequest,
    db: Session,
) -> models.VideoSceneVoiceStatusResponse | None:
    result = _get_scene(project_id, scene_id, db)
    if result is None:
        return None
    project, scene = result

    if scene.no_narration:
        raise VideoVoiceError("Scene này đang được đánh dấu là cố ý không lời.", error_code="VIDEO_VOICE_SKIPPED_SCENE")
    if not (scene.dialogue or "").strip():
        raise VideoVoiceError("Scene này chưa có lời thoại để tạo giọng đọc.", error_code="VIDEO_VOICE_EMPTY_DIALOGUE")
    if scene.voice_status == "completed" and scene.generation_id and not data.force:
        return sync_scene_voice_status(project_id, scene_id, db)

    profile_id = data.profile_id or project.voice_profile_id
    if not profile_id:
        raise VideoVoiceError("Chưa chọn voice profile cho dự án video.", error_code="VIDEO_VOICE_PROFILE_REQUIRED")

    profile = await profiles.get_profile(profile_id, db)
    if not profile:
        raise VideoVoiceError("Không tìm thấy voice profile đã chọn.", error_code="VIDEO_VOICE_PROFILE_NOT_FOUND")

    language = _language_for_project(project, data)
    engine = _resolve_generation_engine(data, profile, language)
    try:
        profiles.validate_profile_engine(profile, engine)
    except ValueError as exc:
        raise VideoVoiceError(str(exc), error_code="VIDEO_VOICE_ENGINE_INVALID") from exc

    generation_id = str(uuid.uuid4())
    model_size = _resolve_model_size(engine, data, language)
    _ensure_profile_language_allowed(profile, language)
    allow_tada_vi_bypass = _ensure_language_allowed(profile, engine, model_size, language)
    text = scene.dialogue.strip()

    await history.create_generation(
        profile_id=profile_id,
        text=text,
        language=language,
        audio_path="",
        duration=0,
        seed=data.seed,
        db=db,
        instruct=data.instruct,
        generation_id=generation_id,
        status="generating",
        engine=engine,
        model_size=model_size,
        source="ai_video_scene",
    )

    scene.generation_id = generation_id
    scene.voice_status = "generating"
    scene.audio_path = None
    scene.audio_duration = None
    scene.voice_failure_reason = None
    scene.subtitle_status = "stale"
    scene.updated_at = datetime.utcnow()
    project.voice_profile_id = profile_id
    video_rendering.mark_render_outputs_stale(project_id, db)
    video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(scene)

    get_task_manager().start_generation(task_id=generation_id, profile_id=profile_id, text=text)
    enqueue_generation(
        generation_id,
        run_generation(
            generation_id=generation_id,
            profile_id=profile_id,
            text=text,
            language=language,
            engine=engine,
            model_size=model_size,
            seed=data.seed,
            normalize=data.normalize,
            effects_chain=None,
            instruct=data.instruct,
            mode="generate",
            max_chunk_chars=data.max_chunk_chars,
            crossfade_ms=data.crossfade_ms,
            allow_experimental_tada_vietnamese=allow_tada_vi_bypass,
        ),
    )
    video_errors.log_step(
        "Scene narration enqueued",
        project_id=project_id,
        scene_id=scene_id,
        voice_profile_id=profile_id,
        generation_id=generation_id,
        step_name="scene_voice_generation",
    )
    return _status_response(scene)

async def create_shot_narration(
    project_id: str,
    shot_id: str,
    data: models.VideoSceneNarrationRequest,
    db: Session,
) -> models.VideoShotVoiceStatusResponse | None:
    result = _get_shot(project_id, shot_id, db)
    if result is None:
        return None
    project, shot = result

    text = (shot.english_narration or "").strip()
    if not text:
        message = "Shot này chưa có narration để tạo giọng đọc."
        _log_voice_failure(
            db,
            project_id=project_id,
            shot_id=shot_id,
            message=message,
            error_code="VIDEO_VOICE_EMPTY_DIALOGUE",
            details={"shot_order": shot.shot_order, "field": "english_narration"},
        )
        raise VideoVoiceError(message, error_code="VIDEO_VOICE_EMPTY_DIALOGUE")
    if shot.voice_status == "completed" and shot.generation_id and not data.force:
        return sync_shot_voice_status(project_id, shot_id, db)

    profile_id = data.profile_id or project.voice_profile_id
    if not profile_id:
        message = "Chưa chọn voice profile cho dự án video."
        _log_voice_failure(
            db,
            project_id=project_id,
            shot_id=shot_id,
            message=message,
            error_code="VIDEO_VOICE_PROFILE_REQUIRED",
            details={"shot_order": shot.shot_order},
        )
        raise VideoVoiceError(message, error_code="VIDEO_VOICE_PROFILE_REQUIRED")

    profile = await profiles.get_profile(profile_id, db)
    if not profile:
        message = "Không tìm thấy voice profile đã chọn."
        _log_voice_failure(
            db,
            project_id=project_id,
            shot_id=shot_id,
            message=message,
            error_code="VIDEO_VOICE_PROFILE_NOT_FOUND",
            details={"shot_order": shot.shot_order, "voice_profile_id": profile_id},
        )
        raise VideoVoiceError(message, error_code="VIDEO_VOICE_PROFILE_NOT_FOUND")

    language = _language_for_project(project, data)
    engine = _resolve_generation_engine(data, profile, language)
    try:
        profiles.validate_profile_engine(profile, engine)
    except ValueError as exc:
        _log_voice_failure(
            db,
            project_id=project_id,
            shot_id=shot_id,
            message=str(exc),
            error_code="VIDEO_VOICE_ENGINE_INVALID",
            details={"shot_order": shot.shot_order, "voice_profile_id": profile_id, "engine": engine},
        )
        raise VideoVoiceError(str(exc), error_code="VIDEO_VOICE_ENGINE_INVALID") from exc

    generation_id = str(uuid.uuid4())
    model_size = _resolve_model_size(engine, data, language)
    try:
        _ensure_profile_language_allowed(profile, language)
        allow_tada_vi_bypass = _ensure_language_allowed(profile, engine, model_size, language)
    except VideoVoiceError as exc:
        _log_voice_failure(
            db,
            project_id=project_id,
            shot_id=shot_id,
            message=str(exc),
            error_code=exc.error_code,
            details={"shot_order": shot.shot_order, "voice_profile_id": profile_id, "engine": engine, "language": language},
        )
        raise

    await history.create_generation(
        profile_id=profile_id,
        text=text,
        language=language,
        audio_path="",
        duration=0,
        seed=data.seed,
        db=db,
        instruct=data.instruct,
        generation_id=generation_id,
        status="generating",
        engine=engine,
        model_size=model_size,
        source="ai_video_shot",
    )

    shot.generation_id = generation_id
    shot.voice_status = "generating"
    shot.audio_path = None
    shot.audio_duration = None
    shot.voice_failure_reason = None
    shot.subtitle_status = "stale"
    shot.updated_at = datetime.utcnow()
    project.voice_profile_id = profile_id
    video_rendering.mark_render_outputs_stale(project_id, db)
    video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(shot)

    get_task_manager().start_generation(task_id=generation_id, profile_id=profile_id, text=text)
    enqueue_generation(
        generation_id,
        run_generation(
            generation_id=generation_id,
            profile_id=profile_id,
            text=text,
            language=language,
            engine=engine,
            model_size=model_size,
            seed=data.seed,
            normalize=data.normalize,
            effects_chain=None,
            instruct=data.instruct,
            mode="generate",
            max_chunk_chars=data.max_chunk_chars,
            crossfade_ms=data.crossfade_ms,
            allow_experimental_tada_vietnamese=allow_tada_vi_bypass,
        ),
    )
    video_observability.log_event(
        db,
        step_name="shot_voice_generation",
        status="success",
        project_id=project_id,
        shot_id=shot_id,
        message="Đã đưa shot voice vào hàng đợi tạo audio.",
        technical_details={
            "shot_order": shot.shot_order,
            "voice_profile_id": profile_id,
            "generation_id": generation_id,
            "language": language,
            "engine": engine,
            "text_chars": len(text),
        },
    )
    return _shot_status_response(shot)


def get_scene_audio_download(project_id: str, scene_id: str, db: Session) -> tuple[str, Path] | None:
    status = sync_scene_voice_status(project_id, scene_id, db)
    if status is None or status.voice_status != "completed" or not status.audio_path:
        return None
    path = config.resolve_storage_path(status.audio_path)
    if path is None or not path.exists():
        return None
    return video_storage.voice_filename(status.scene_order, path.suffix or ".wav"), path

def get_shot_audio_download(project_id: str, shot_id: str, db: Session) -> tuple[str, Path] | None:
    status = sync_shot_voice_status(project_id, shot_id, db)
    if status is None or status.voice_status != "completed" or not status.audio_path:
        return None
    path = config.resolve_storage_path(status.audio_path)
    if path is None or not path.exists():
        return None

    scene_order: int | None = None
    if status.scene_id:
        scene = db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id, DBVideoScene.id == status.scene_id).first()
        scene_order = scene.scene_order if scene is not None else None
    return video_storage.shot_voice_filename(scene_order, status.shot_order, path.suffix or ".wav"), path
