"""AI Video Assistant project persistence and status helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    Generation as DBGeneration,
    VideoDebugEvent as DBVideoDebugEvent,
    VideoAutoRun as DBVideoAutoRun,
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoPackageExport as DBVideoPackageExport,
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoScene as DBVideoScene,
    VideoSceneAsset as DBVideoSceneAsset,
    VideoScenePrompt as DBVideoScenePrompt,
    VideoSeries as DBVideoSeries,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
    VideoSubtitle as DBVideoSubtitle,
)
from . import (
    video_clip_generation,
    video_language,
    video_observability,
    video_provider_storage,
    video_purpose,
    video_rendering,
    video_series_memory,
    video_state,
    video_storage,
)

PROMPT_SEGMENT_MIN_SECONDS_PER_MICRO_SCENE = 1.5
PROJECT_OPERATION_ACTIVE_CODE = "AI_VIDEO_PROJECT_OPERATION_ACTIVE"
VOICE_BUSY_STATUSES = {"queued", "generating", "loading_model"}
RENDER_BUSY_STATUSES = {"queued", "running"}

class VideoProjectOperationError(ValueError):
    """Raised when a destructive project operation cannot safely run."""

    def __init__(self, message: str, *, error_code: str = "AI_VIDEO_PROJECT_OPERATION_FAILED"):
        super().__init__(message)
        self.error_code = error_code


def _default_title(topic: str) -> str:
    first_line = (topic or "").strip().splitlines()[0:1]
    title = first_line[0] if first_line else "Dự án video"
    return title[:120]

def _scene_count(project_id: str, db: Session) -> int:
    return db.query(func.count(DBVideoScene.id)).filter(DBVideoScene.project_id == project_id).scalar() or 0

def _shot_count(project_id: str, db: Session) -> int:
    return db.query(func.count(DBVideoShot.id)).filter(DBVideoShot.project_id == project_id).scalar() or 0

def _series_episode_count(series_id: str, db: Session) -> int:
    return db.query(func.count(DBVideoProject.id)).filter(DBVideoProject.series_id == series_id).scalar() or 0

def _series_response(series: DBVideoSeries, db: Session) -> models.VideoSeriesResponse:
    response = models.VideoSeriesResponse.model_validate(series)
    response.episode_count = _series_episode_count(series.id, db)
    return response

def _project_response(project: DBVideoProject, db: Session) -> models.VideoProjectResponse:
    from . import video_auto_runs

    response = models.VideoProjectResponse.model_validate(project)
    response.scene_count = _scene_count(project.id, db)
    response.shot_count = _shot_count(project.id, db)
    active_run = (
        db.query(video_auto_runs.DBVideoAutoRun)
        .filter(
            video_auto_runs.DBVideoAutoRun.project_id == project.id,
            video_auto_runs.DBVideoAutoRun.status.in_(video_auto_runs.ACTIVE_STATUSES),
        )
        .order_by(video_auto_runs.DBVideoAutoRun.created_at.desc())
        .first()
    )
    if active_run is not None:
        response.active_run_status = active_run.status
        response.active_run_step = active_run.current_step
        response.active_run_progress = float(active_run.progress or 0.0)
    else:
        latest_run = (
            db.query(video_auto_runs.DBVideoAutoRun)
            .filter(video_auto_runs.DBVideoAutoRun.project_id == project.id)
            .order_by(video_auto_runs.DBVideoAutoRun.updated_at.desc())
            .first()
        )
        if latest_run is not None and latest_run.status == "failed":
            response.active_run_status = latest_run.status
            response.active_run_step = latest_run.current_step
            response.active_run_progress = float(latest_run.progress or 0.0)
    if project.series_id:
        series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
        response.series_title = series.title if series else None
    return response

def _validate_series_exists(series_id: str | None, db: Session) -> DBVideoSeries | None:
    if not series_id:
        return None
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        raise ValueError("Không tìm thấy series AI Video.")
    return series

def _validate_project_operation_available(project_id: str, db: Session, *, operation: str) -> None:
    from . import video_auto_runs, video_planning_pool

    active_run = (
        db.query(video_auto_runs.DBVideoAutoRun)
        .filter(
            video_auto_runs.DBVideoAutoRun.project_id == project_id,
            video_auto_runs.DBVideoAutoRun.status.in_(video_auto_runs.ACTIVE_STATUSES),
        )
        .order_by(video_auto_runs.DBVideoAutoRun.created_at.desc())
        .first()
    )
    if active_run is not None:
        raise VideoProjectOperationError(
            "Dự án đang auto-run. Hãy huỷ hoặc chờ auto-run hoàn tất trước khi xoá dữ liệu.",
            error_code=PROJECT_OPERATION_ACTIVE_CODE,
        )
    planning_info = video_planning_pool.active_project_info(project_id)
    if planning_info is not None:
        raise VideoProjectOperationError(
            "Dự án đang chạy AI planning. Hãy chờ bước hiện tại hoàn tất trước khi xoá dữ liệu.",
            error_code=PROJECT_OPERATION_ACTIVE_CODE,
        )
    busy_scene = db.query(DBVideoScene.id).filter(
        DBVideoScene.project_id == project_id,
        DBVideoScene.voice_status.in_(VOICE_BUSY_STATUSES),
    ).first()
    busy_shot = db.query(DBVideoShot.id).filter(
        DBVideoShot.project_id == project_id,
        DBVideoShot.voice_status.in_(VOICE_BUSY_STATUSES),
    ).first()
    if busy_scene is not None or busy_shot is not None:
        raise VideoProjectOperationError(
            "Dự án đang tạo voice. Hãy dừng hoặc chờ voice hoàn tất trước khi xoá dữ liệu.",
            error_code=PROJECT_OPERATION_ACTIVE_CODE,
        )
    busy_render = db.query(DBVideoRenderJob.id).filter(
        DBVideoRenderJob.project_id == project_id,
        DBVideoRenderJob.status.in_(RENDER_BUSY_STATUSES),
    ).first()
    if busy_render is not None:
        raise VideoProjectOperationError(
            "Dự án đang render MP4. Hãy chờ render hoàn tất trước khi xoá dữ liệu.",
            error_code=PROJECT_OPERATION_ACTIVE_CODE,
        )
    busy_clip_generation = db.query(DBVideoClipGenerationJob.id).filter(
        DBVideoClipGenerationJob.project_id == project_id,
        DBVideoClipGenerationJob.status.in_(video_clip_generation.ACTIVE_STATUSES),
    ).first()
    if busy_clip_generation is not None:
        raise VideoProjectOperationError(
            "Dự án đang tạo clip bằng Veo. Hãy huỷ hoặc chờ job hoàn tất trước khi xoá dữ liệu.",
            error_code=PROJECT_OPERATION_ACTIVE_CODE,
        )

def _log_project_operation(
    db: Session,
    *,
    project_id: str,
    operation: str,
    status: str,
    message: str,
    counts: dict[str, int] | None = None,
    error_code: str | None = None,
    exc: BaseException | None = None,
) -> None:
    video_observability.log_event(
        db,
        step_name=f"project_{operation}",
        status=status,
        project_id=project_id,
        error_code=error_code,
        exc=exc,
        message=message,
        technical_details={"operation": operation, "counts": counts or {}},
    )

def _configured_prompt_segment_values(data: dict) -> tuple[int, int, int] | None:
    keys = ("prompt_segment_count", "prompt_segment_duration_seconds", "micro_scenes_per_prompt")
    values = {key: data.get(key) for key in keys}
    provided = [key for key, value in values.items() if value is not None]
    if not provided:
        return None
    if len(provided) != len(keys):
        missing = ", ".join(key for key in keys if values[key] is None)
        raise ValueError(f"Thiếu cấu hình prompt segment: {missing}.")
    count = int(values["prompt_segment_count"])
    duration = int(values["prompt_segment_duration_seconds"])
    micro_count = int(values["micro_scenes_per_prompt"])
    total_duration = count * duration
    if total_duration > 7200:
        raise ValueError("Tổng thời lượng video không được vượt quá 7200 giây.")
    if duration / max(1, micro_count) < PROMPT_SEGMENT_MIN_SECONDS_PER_MICRO_SCENE:
        raise ValueError("Mỗi cảnh nhỏ cần tối thiểu khoảng 1.5 giây. Hãy giảm số cảnh nhỏ hoặc tăng thời gian mỗi prompt.")
    return count, duration, micro_count

def _project_config_dict(project: DBVideoProject) -> dict[str, int | None]:
    return {
        "prompt_segment_count": project.prompt_segment_count,
        "prompt_segment_duration_seconds": project.prompt_segment_duration_seconds,
        "micro_scenes_per_prompt": project.micro_scenes_per_prompt,
    }

def _derive_target_duration_from_config(data: dict) -> int | None:
    values = _configured_prompt_segment_values(data)
    if values is None:
        return None
    count, duration, _micro_count = values
    return count * duration

def _stale_dialogue_dependent_artifacts(project: DBVideoProject, db: Session) -> None:
    """Mark generated material stale after purpose or dialogue contract changes."""
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project.id).update(
        {"prompt_status": "stale", "voice_status": "stale", "subtitle_status": "stale"},
        synchronize_session=False,
    )
    for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all():
        shot.status = "stale"
        shot.prompt_status = "stale"
        shot.subtitle_status = "stale"
        if (shot.english_narration or "").strip():
            shot.voice_status = "stale"
    db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project.id).update(
        {"status": "stale"},
        synchronize_session=False,
    )
    video_rendering.mark_render_outputs_stale(project.id, db)
    video_state.mark_package_stale(project, db)

def _ordered_scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )

def _sync_voice_statuses(project_id: str, db: Session) -> None:
    """Refresh linked generation status before returning AI Video project state."""
    from . import video_voice

    busy_states = {"generating", "loading_model", "queued"}
    scene_ids = [
        row[0]
        for row in db.query(DBVideoScene.id)
        .filter(
            DBVideoScene.project_id == project_id,
            DBVideoScene.generation_id.isnot(None),
            DBVideoScene.voice_status.in_(busy_states),
        )
        .all()
    ]
    for scene_id in scene_ids:
        video_voice.sync_scene_voice_status(project_id, scene_id, db)

    shot_ids = [
        row[0]
        for row in db.query(DBVideoShot.id)
        .filter(
            DBVideoShot.project_id == project_id,
            DBVideoShot.generation_id.isnot(None),
            DBVideoShot.voice_status.in_(busy_states),
        )
        .all()
    ]
    for shot_id in shot_ids:
        video_voice.sync_shot_voice_status(project_id, shot_id, db)

def _detail_response(project: DBVideoProject, db: Session) -> models.VideoProjectDetailResponse:
    _sync_voice_statuses(project.id, db)
    data = models.VideoProjectDetailResponse.model_validate(project)
    data.scene_count = _scene_count(project.id, db)
    data.shot_count = _shot_count(project.id, db)
    data.source_blocks = [
        models.VideoSourceBlockResponse.model_validate(row)
        for row in db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project.id)
        .order_by(DBVideoSourceBlock.sort_order.asc(), DBVideoSourceBlock.created_at.asc())
        .all()
    ]
    data.scenes = [models.VideoSceneResponse.model_validate(scene) for scene in _ordered_scenes(project.id, db)]
    data.shots = [
        models.VideoShotResponse.model_validate(row)
        for row in db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project.id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    ]
    return data

def create_project(data: models.VideoProjectCreate, db: Session) -> models.VideoProjectResponse:
    now = datetime.utcnow()
    create_data = data.model_dump()
    series = _validate_series_exists(data.series_id, db)
    derived_target_duration = _derive_target_duration_from_config(create_data)
    explicit_target_language = data.target_language if "target_language" in data.model_fields_set else None
    purpose_settings = video_purpose.resolve_purpose_settings(
        video_purpose=data.video_purpose,
        target_language=explicit_target_language,
        dialogue_mode=data.dialogue_mode,
        narration_density=data.narration_density,
        call_to_action_style=data.call_to_action_style,
    )
    project = DBVideoProject(
        id=str(uuid.uuid4()),
        series_id=series.id if series else None,
        episode_number=data.episode_number,
        episode_title=data.episode_title,
        title=data.title or _default_title(data.topic),
        topic=data.topic,
        language=data.language,
        target_language=purpose_settings["target_language"],
        video_purpose=purpose_settings["video_purpose"],
        dialogue_mode=purpose_settings["dialogue_mode"],
        narration_density=purpose_settings["narration_density"],
        call_to_action_style=purpose_settings["call_to_action_style"],
        target_duration_seconds=derived_target_duration if derived_target_duration is not None else data.target_duration_seconds,
        aspect_ratio=data.aspect_ratio,
        visual_style=data.visual_style,
        voice_profile_id=data.voice_profile_id,
        phase=data.phase,
        default_shot_duration_seconds=data.default_shot_duration_seconds,
        prompt_segment_count=data.prompt_segment_count,
        prompt_segment_duration_seconds=data.prompt_segment_duration_seconds,
        micro_scenes_per_prompt=data.micro_scenes_per_prompt,
        planning_status="draft",
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    source_blocks = data.source_blocks or [models.VideoSourceBlockDraft(block_type="idea", content=data.topic)]
    for index, block in enumerate(source_blocks, start=1):
        db.add(
            DBVideoSourceBlock(
                id=str(uuid.uuid4()),
                project_id=project.id,
                block_type=block.block_type,
                sort_order=index,
                content=block.content,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    db.refresh(project)
    video_storage.get_project_dir(project.id)
    if project.series_id:
        video_series_memory.sync_series_memory_file(project.series_id, db)
    return _project_response(project, db)

def list_projects(db: Session) -> list[models.VideoProjectResponse]:
    rows = db.query(DBVideoProject).order_by(DBVideoProject.updated_at.desc()).all()
    return [_project_response(project, db) for project in rows]

def get_project(project_id: str, db: Session) -> models.VideoProjectDetailResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    return _detail_response(project, db)

def list_series(db: Session) -> list[models.VideoSeriesResponse]:
    rows = db.query(DBVideoSeries).order_by(DBVideoSeries.updated_at.desc(), DBVideoSeries.created_at.desc()).all()
    return [_series_response(row, db) for row in rows]

def get_series(series_id: str, db: Session) -> models.VideoSeriesResponse | None:
    row = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    return _series_response(row, db) if row else None

def create_series(data: models.VideoSeriesCreate, db: Session) -> models.VideoSeriesResponse:
    now = datetime.utcnow()
    row = DBVideoSeries(
        id=str(uuid.uuid4()),
        title=data.title.strip(),
        character_bible=data.character_bible,
        world_bible=data.world_bible,
        style_bible=data.style_bible,
        continuity_rules=data.continuity_rules,
        negative_rules=data.negative_rules,
        previous_episode_summary=data.previous_episode_summary,
        latest_episode_number=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    video_series_memory.sync_series_memory_file(row.id, db)
    return _series_response(row, db)

def update_series(series_id: str, patch: models.VideoSeriesUpdate, db: Session) -> models.VideoSeriesResponse | None:
    row = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if row is None:
        return None
    data = patch.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value.strip() if key == "title" and isinstance(value, str) else value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    video_series_memory.sync_series_memory_file(row.id, db)
    return _series_response(row, db)

def _latest_episode_project(series_id: str, db: Session) -> DBVideoProject | None:
    return (
        db.query(DBVideoProject)
        .filter(DBVideoProject.series_id == series_id)
        .order_by(DBVideoProject.episode_number.desc().nullslast(), DBVideoProject.created_at.desc())
        .first()
    )

def next_episode_number(series_id: str, db: Session) -> int:
    series = _validate_series_exists(series_id, db)
    max_project_episode = db.query(func.max(DBVideoProject.episode_number)).filter(DBVideoProject.series_id == series_id).scalar() or 0
    return max(int(series.latest_episode_number or 0), int(max_project_episode or 0)) + 1

def create_episode(series_id: str, data: models.VideoEpisodeCreate, db: Session) -> models.VideoProjectResponse | None:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        return None
    latest = _latest_episode_project(series_id, db) if data.reuse_latest_config else None
    episode_number = data.episode_number or next_episode_number(series_id, db)
    duplicate = db.query(DBVideoProject.id).filter(
        DBVideoProject.series_id == series_id,
        DBVideoProject.episode_number == episode_number,
    ).first()
    if duplicate is not None:
        raise ValueError(f"Series đã có tập số {episode_number}. Hãy chọn số tập khác.")
    episode_title = data.episode_title or f"Tập {episode_number:02d}"
    project_title = data.title or f"{series.title} - {episode_title}"
    inherit_purpose_config = latest is not None and data.video_purpose is None
    project_kwargs = {
        "topic": data.topic,
        "title": project_title,
        "series_id": series_id,
        "episode_number": episode_number,
        "episode_title": episode_title,
        "language": data.language,
        "video_purpose": data.video_purpose or (latest.video_purpose if inherit_purpose_config else video_purpose.VIDEO_PURPOSE_CUSTOM),
        "dialogue_mode": data.dialogue_mode if data.dialogue_mode is not None else (latest.dialogue_mode if inherit_purpose_config else None),
        "narration_density": data.narration_density if data.narration_density is not None else (latest.narration_density if inherit_purpose_config else None),
        "call_to_action_style": data.call_to_action_style if data.call_to_action_style is not None else (latest.call_to_action_style if inherit_purpose_config else None),
        "target_duration_seconds": data.target_duration_seconds if data.target_duration_seconds is not None else (latest.target_duration_seconds if latest else None),
        "aspect_ratio": data.aspect_ratio or (latest.aspect_ratio if latest else "9:16"),
        "visual_style": data.visual_style if data.visual_style is not None else (latest.visual_style if latest else None),
        "voice_profile_id": data.voice_profile_id if data.voice_profile_id is not None else (latest.voice_profile_id if latest else None),
        "phase": data.phase,
        "default_shot_duration_seconds": data.default_shot_duration_seconds if data.default_shot_duration_seconds is not None else (latest.default_shot_duration_seconds if latest else None),
        "prompt_segment_count": data.prompt_segment_count if data.prompt_segment_count is not None else (latest.prompt_segment_count if latest else None),
        "prompt_segment_duration_seconds": data.prompt_segment_duration_seconds if data.prompt_segment_duration_seconds is not None else (latest.prompt_segment_duration_seconds if latest else None),
        "micro_scenes_per_prompt": data.micro_scenes_per_prompt if data.micro_scenes_per_prompt is not None else (latest.micro_scenes_per_prompt if latest else None),
        "source_blocks": data.source_blocks,
    }
    target_language = data.target_language if data.target_language is not None else (latest.target_language if inherit_purpose_config else None)
    if target_language is not None:
        project_kwargs["target_language"] = target_language
    project_data = models.VideoProjectCreate(**project_kwargs)
    project = create_project(project_data, db)
    series.latest_episode_number = max(int(series.latest_episode_number or 0), episode_number)
    series.updated_at = datetime.utcnow()
    db.commit()
    video_series_memory.sync_series_memory_file(series_id, db)
    return project

def localize_project(
    project_id: str,
    data: models.VideoProjectLocalizeRequest,
    db: Session,
) -> models.VideoProjectResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    target_language = video_language.normalize_video_language(data.target_language)
    language_label = video_language.video_language_label(target_language)
    source_blocks = [
        models.VideoSourceBlockDraft(block_type=row.block_type, content=row.content)
        for row in db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project_id)
        .order_by(DBVideoSourceBlock.sort_order.asc(), DBVideoSourceBlock.created_at.asc())
        .all()
    ]
    if not source_blocks:
        source_blocks = [models.VideoSourceBlockDraft(block_type="idea", content=project.topic)]
    create_data = models.VideoProjectCreate(
        topic=project.topic,
        title=data.title or f"{project.title} - {language_label}",
        language=project.language,
        target_language=target_language,
        video_purpose=data.video_purpose,
        dialogue_mode=data.dialogue_mode,
        narration_density=data.narration_density,
        call_to_action_style=data.call_to_action_style,
        target_duration_seconds=project.target_duration_seconds,
        aspect_ratio=project.aspect_ratio,
        visual_style=project.visual_style,
        voice_profile_id=data.voice_profile_id if data.voice_profile_id is not None else project.voice_profile_id,
        phase=project.phase,
        default_shot_duration_seconds=project.default_shot_duration_seconds,
        prompt_segment_count=project.prompt_segment_count,
        prompt_segment_duration_seconds=project.prompt_segment_duration_seconds,
        micro_scenes_per_prompt=project.micro_scenes_per_prompt,
        source_blocks=source_blocks,
    )
    localized = create_project(create_data, db)
    localized_row = db.query(DBVideoProject).filter(DBVideoProject.id == localized.id).first()
    if localized_row is not None:
        localized_row.continuity_bible = project.continuity_bible
        localized_row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(localized_row)
        localized = _project_response(localized_row, db)
    return localized

def delete_series(series_id: str, db: Session, *, delete_episodes: bool = False, confirm_delete_episodes: bool = False) -> bool:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        return False
    episode_ids = [row[0] for row in db.query(DBVideoProject.id).filter(DBVideoProject.series_id == series_id).all()]
    if delete_episodes:
        if not confirm_delete_episodes:
            raise VideoProjectOperationError(
                "Cần confirm_delete_episodes=true để xoá series kèm toàn bộ tập.",
                error_code="AI_VIDEO_SERIES_DELETE_CONFIRM_REQUIRED",
            )
        for project_id in episode_ids:
            _validate_project_operation_available(project_id, db, operation="delete_series_episode")
        for project_id in episode_ids:
            delete_project(project_id, db, check_active=False)
    else:
        now = datetime.utcnow()
        db.query(DBVideoProject).filter(DBVideoProject.series_id == series_id).update(
            {"series_id": None, "episode_number": None, "episode_title": None, "updated_at": now},
            synchronize_session=False,
        )
    db.delete(series)
    db.commit()
    video_storage.remove_series_artifacts(series_id)
    return True

def update_series_summary_from_project(
    project_id: str,
    data: models.VideoSeriesSummaryUpdateRequest,
    db: Session,
) -> models.VideoSeriesResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if not project.series_id:
        raise ValueError("Project này là project lẻ, không có series để cập nhật summary.")
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
    if series is None:
        raise ValueError("Không tìm thấy series AI Video của project này.")
    summary = (data.summary or project.detailed_script or project.story_strategy or project.script_text or "").strip()
    if not summary:
        raise ValueError("Chưa có summary hợp lệ để cập nhật Series Bible.")
    series.previous_episode_summary = summary[:50000]
    if project.episode_number:
        series.latest_episode_number = max(int(series.latest_episode_number or 0), int(project.episode_number))
    series.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(series)
    video_series_memory.sync_series_memory_file(series.id, db)
    video_observability.log_event(
        db,
        step_name="series_summary_update",
        status="success",
        project_id=project_id,
        message="Đã cập nhật previous episode summary cho series bằng action explicit.",
        technical_details={
            "series_id": series.id,
            "episode_number": project.episode_number,
            "summary_chars": len(summary),
            "truncated": len(summary) > 50000,
        },
    )
    return _series_response(series, db)

def update_project(
    project_id: str,
    patch: models.VideoProjectUpdate,
    db: Session,
) -> models.VideoProjectResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    previous_series_id = project.series_id
    data = patch.model_dump(exclude_unset=True)
    incoming_keys = set(data)
    if "series_id" in data and data["series_id"]:
        _validate_series_exists(data["series_id"], db)
    purpose_contract_keys = {"video_purpose", "dialogue_mode", "narration_density", "call_to_action_style"}
    if "target_language" in data or incoming_keys & purpose_contract_keys:
        if "target_language" in data:
            data["target_language"] = video_language.normalize_video_language(data["target_language"])
        current_purpose = video_purpose.normalize_video_purpose(getattr(project, "video_purpose", None))
        purpose_for_resolution = data.get("video_purpose", current_purpose)
        target_language_for_resolution = data.get("target_language", video_language.normalize_video_language(project.target_language))
        reset_to_preset = "video_purpose" in data
        purpose_settings = video_purpose.resolve_purpose_settings(
            video_purpose=purpose_for_resolution,
            target_language=target_language_for_resolution,
            dialogue_mode=data["dialogue_mode"] if "dialogue_mode" in data else (None if reset_to_preset else getattr(project, "dialogue_mode", None)),
            narration_density=data["narration_density"] if "narration_density" in data else (None if reset_to_preset else getattr(project, "narration_density", None)),
            call_to_action_style=data["call_to_action_style"] if "call_to_action_style" in data else (None if reset_to_preset else getattr(project, "call_to_action_style", None)),
        )
        if not reset_to_preset and "call_to_action_style" not in data:
            purpose_settings["call_to_action_style"] = getattr(project, "call_to_action_style", None)
        data.update(
            {
                "target_language": purpose_settings["target_language"],
                "video_purpose": purpose_settings["video_purpose"],
                "dialogue_mode": purpose_settings["dialogue_mode"],
                "narration_density": purpose_settings["narration_density"],
                "call_to_action_style": purpose_settings["call_to_action_style"],
            }
        )
    target_language_changed = "target_language" in data and data["target_language"] != video_language.normalize_video_language(project.target_language)
    purpose_contract_changed = any(
        key in data and data[key] != getattr(project, key, None)
        for key in purpose_contract_keys
    )
    prompt_config_keys = {"prompt_segment_count", "prompt_segment_duration_seconds", "micro_scenes_per_prompt"}
    prompt_config_changed = any(key in incoming_keys for key in prompt_config_keys)
    prompt_config_only_changed = prompt_config_changed and incoming_keys <= prompt_config_keys
    if prompt_config_changed:
        combined_config = {**_project_config_dict(project), **{key: data.get(key) for key in _project_config_dict(project) if key in data}}
        derived_target_duration = _derive_target_duration_from_config(combined_config)
        data["target_duration_seconds"] = derived_target_duration
    for key, value in data.items():
        setattr(project, key, value)
    if "voice_profile_id" in data:
        db.query(DBVideoScene).filter(
            DBVideoScene.project_id == project_id,
            DBVideoScene.no_narration.is_(False),
        ).update(
            {"voice_status": "stale", "subtitle_status": "stale"},
            synchronize_session=False,
        )
        for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).all():
            if (shot.english_narration or "").strip():
                shot.voice_status = "stale"
                shot.subtitle_status = "stale"
    content_changed = any(
        key in data
        for key in {
            "topic",
            "target_language",
            "target_duration_seconds",
            "visual_style",
            "default_shot_duration_seconds",
            "prompt_segment_count",
            "prompt_segment_duration_seconds",
            "micro_scenes_per_prompt",
            "continuity_bible",
            "series_id",
            "episode_number",
            "episode_title",
        }
    ) or purpose_contract_changed
    if target_language_changed:
        db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).update(
            {"prompt_status": "stale", "subtitle_status": "stale"},
            synchronize_session=False,
        )
        for scene in db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).all():
            if (scene.dialogue or "").strip() and not scene.no_narration:
                scene.voice_status = "stale"
                scene.subtitle_status = "stale"
        for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).all():
            shot.status = "stale"
            shot.prompt_status = "stale"
            shot.subtitle_status = "stale"
            if (shot.english_narration or "").strip():
                shot.voice_status = "stale"
        db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).update(
            {"status": "stale"},
            synchronize_session=False,
        )
    if purpose_contract_changed:
        _stale_dialogue_dependent_artifacts(project, db)
    if content_changed or "voice_profile_id" in data:
        if content_changed and not prompt_config_only_changed:
            project.story_approved = False
            project.script_approved = False
            project.retention_plan_json = None
            project.sound_design_plan_json = None
        project.planning_status = "stale"
        if not target_language_changed:
            if prompt_config_changed:
                for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).all():
                    shot.status = "stale"
                    shot.prompt_status = "stale"
                    shot.subtitle_status = "stale"
                    if (shot.english_narration or "").strip():
                        shot.voice_status = "stale"
                db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).update(
                    {"status": "stale"},
                    synchronize_session=False,
                )
            else:
                db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.locked.is_(False)).update(
                    {"status": "stale", "prompt_status": "stale", "subtitle_status": "stale"},
                    synchronize_session=False,
                )
        video_rendering.mark_render_outputs_stale(project_id, db)
        video_state.mark_package_stale(project, db)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    for series_id in {previous_series_id, project.series_id}:
        if series_id:
            video_series_memory.sync_series_memory_file(series_id, db)
    return _project_response(project, db)

def _remove_generation_files(generation_ids: list[str], db: Session) -> None:
    if not generation_ids:
        return
    rows = db.query(DBGeneration).filter(DBGeneration.id.in_(generation_ids)).all()
    for row in rows:
        video_storage.remove_artifact_file(row.audio_path)
        row.audio_path = None
        row.duration = None
        row.status = "failed"
        row.error = "AI Video generated data was reset or deleted."

def reset_generated_data(project_id: str, db: Session) -> models.VideoGeneratedDataResetResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    _validate_project_operation_available(project_id, db, operation="reset_generated_data")
    series_id = project.series_id

    scene_generation_ids = [row[0] for row in db.query(DBVideoScene.generation_id).filter(DBVideoScene.project_id == project_id, DBVideoScene.generation_id.isnot(None)).all()]
    shot_generation_ids = [row[0] for row in db.query(DBVideoShot.generation_id).filter(DBVideoShot.project_id == project_id, DBVideoShot.generation_id.isnot(None)).all()]
    for audio_path in [row[0] for row in db.query(DBVideoScene.audio_path).filter(DBVideoScene.project_id == project_id, DBVideoScene.audio_path.isnot(None)).all()]:
        video_storage.remove_artifact_file(audio_path)
    for audio_path in [row[0] for row in db.query(DBVideoShot.audio_path).filter(DBVideoShot.project_id == project_id, DBVideoShot.audio_path.isnot(None)).all()]:
        video_storage.remove_artifact_file(audio_path)

    counts = {
        "package_exports": db.query(func.count(DBVideoPackageExport.id)).filter(DBVideoPackageExport.project_id == project_id).scalar() or 0,
        "clip_generation_jobs": db.query(func.count(DBVideoClipGenerationJob.id)).filter(DBVideoClipGenerationJob.project_id == project_id).scalar() or 0,
        "render_jobs": db.query(func.count(DBVideoRenderJob.id)).filter(DBVideoRenderJob.project_id == project_id).scalar() or 0,
        "debug_events": db.query(func.count(DBVideoDebugEvent.id)).filter(DBVideoDebugEvent.project_id == project_id).scalar() or 0,
        "subtitles": db.query(func.count(DBVideoSubtitle.id)).filter(DBVideoSubtitle.project_id == project_id).scalar() or 0,
        "scene_assets": db.query(func.count(DBVideoSceneAsset.id)).filter(DBVideoSceneAsset.project_id == project_id).scalar() or 0,
        "shot_prompts": db.query(func.count(DBVideoShotPrompt.id)).filter(DBVideoShotPrompt.project_id == project_id).scalar() or 0,
        "shot_clips": db.query(func.count(DBVideoShotClip.id)).filter(DBVideoShotClip.project_id == project_id).scalar() or 0,
        "shots": db.query(func.count(DBVideoShot.id)).filter(DBVideoShot.project_id == project_id).scalar() or 0,
        "scene_prompts": db.query(func.count(DBVideoScenePrompt.id)).filter(DBVideoScenePrompt.project_id == project_id).scalar() or 0,
        "scenes": db.query(func.count(DBVideoScene.id)).filter(DBVideoScene.project_id == project_id).scalar() or 0,
    }

    _remove_generation_files(list(dict.fromkeys(scene_generation_ids + shot_generation_ids)), db)
    db.query(DBVideoClipGenerationItem).filter(DBVideoClipGenerationItem.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoDebugEvent).filter(DBVideoDebugEvent.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoSceneAsset).filter(DBVideoSceneAsset.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoShotClip).filter(DBVideoShotClip.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id).delete(synchronize_session=False)

    project.creative_brief = None
    project.script_text = None
    project.style_bible = None
    project.character_bible = None
    project.input_synthesis = None
    project.story_strategy = None
    project.continuity_bible = None
    project.detailed_script = None
    project.retention_plan_json = None
    project.sound_design_plan_json = None
    project.story_approved = False
    project.script_approved = False
    project.planning_status = "draft"
    project.planning_error = None
    project.status = "draft"
    project.package_stale = False
    project.updated_at = datetime.utcnow()
    db.commit()
    video_provider_storage.cleanup_project_downloads(project_id)
    video_storage.remove_project_artifacts(project_id)
    video_storage.get_project_dir(project_id)
    if series_id:
        video_series_memory.sync_series_memory_file(series_id, db)
    _log_project_operation(
        db,
        project_id=project_id,
        operation="reset_generated_data",
        status="success",
        message="Đã xoá dữ liệu đã tạo và giữ lại project, nguồn nhập, cấu hình và liên kết series.",
        counts=counts,
    )
    return models.VideoGeneratedDataResetResponse(
        project_id=project_id,
        message="Đã xoá dữ liệu đã tạo. Nguồn nhập, cấu hình và series vẫn được giữ.",
        deleted_counts=counts,
    )

def delete_project(project_id: str, db: Session, *, check_active: bool = True) -> bool:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return False
    if check_active:
        _validate_project_operation_available(project_id, db, operation="delete_project")
    series_id = project.series_id

    counts = {
        "source_blocks": db.query(func.count(DBVideoSourceBlock.id)).filter(DBVideoSourceBlock.project_id == project_id).scalar() or 0,
        "scenes": db.query(func.count(DBVideoScene.id)).filter(DBVideoScene.project_id == project_id).scalar() or 0,
        "shots": db.query(func.count(DBVideoShot.id)).filter(DBVideoShot.project_id == project_id).scalar() or 0,
        "shot_prompts": db.query(func.count(DBVideoShotPrompt.id)).filter(DBVideoShotPrompt.project_id == project_id).scalar() or 0,
        "clip_generation_jobs": db.query(func.count(DBVideoClipGenerationJob.id)).filter(DBVideoClipGenerationJob.project_id == project_id).scalar() or 0,
        "render_jobs": db.query(func.count(DBVideoRenderJob.id)).filter(DBVideoRenderJob.project_id == project_id).scalar() or 0,
    }
    _log_project_operation(
        db,
        project_id=project_id,
        operation="delete_project",
        status="success",
        message="Đang xoá project AI Video và artifacts liên quan.",
        counts=counts,
    )

    db.query(DBVideoClipGenerationItem).filter(DBVideoClipGenerationItem.project_id == project_id).delete()
    db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id).delete()
    db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project_id).delete()
    render_jobs = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id).all()
    for render_job in render_jobs:
        video_storage.remove_artifact_file(render_job.timeline_manifest_path)
        video_storage.remove_artifact_file(render_job.output_path)
        video_storage.remove_artifact_file(render_job.subtitle_ass_path)
    db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id).delete()
    db.query(DBVideoDebugEvent).filter(DBVideoDebugEvent.project_id == project_id).delete()
    db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).delete()
    db.query(DBVideoSceneAsset).filter(DBVideoSceneAsset.project_id == project_id).delete()
    shot_prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project_id).all()
    for shot_prompt in shot_prompts:
        video_storage.remove_artifact_file(shot_prompt.prompt_path)
    db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project_id).delete()
    shot_clips = db.query(DBVideoShotClip).filter(DBVideoShotClip.project_id == project_id).all()
    for shot_clip in shot_clips:
        video_storage.remove_artifact_file(shot_clip.file_path)
    db.query(DBVideoShotClip).filter(DBVideoShotClip.project_id == project_id).delete()
    db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).delete()
    db.query(DBVideoSourceBlock).filter(DBVideoSourceBlock.project_id == project_id).delete()
    db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.project_id == project_id).delete()
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).delete()
    db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id).delete()
    db.delete(project)
    db.commit()
    video_provider_storage.cleanup_project_downloads(project_id)
    video_storage.remove_project_artifacts(project_id)
    if series_id and db.query(DBVideoSeries.id).filter(DBVideoSeries.id == series_id).first():
        video_series_memory.sync_series_memory_file(series_id, db)
    return True

def replace_scenes(
    project_id: str,
    data: models.VideoScenesReplaceRequest,
    db: Session,
) -> list[models.VideoSceneResponse] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None

    old_scenes = db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).all()
    old_scene_ids = [scene.id for scene in old_scenes]
    if old_scene_ids:
        old_shots = db.query(DBVideoShot).filter(DBVideoShot.scene_id.in_(old_scene_ids)).all()
        old_shot_ids = [shot.id for shot in old_shots]
        if old_shot_ids:
            old_shot_prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(old_shot_ids)).all()
            for old_prompt in old_shot_prompts:
                video_storage.remove_artifact_file(old_prompt.prompt_path)
            db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(old_shot_ids)).delete(synchronize_session=False)
            old_shot_clips = db.query(DBVideoShotClip).filter(DBVideoShotClip.shot_id.in_(old_shot_ids)).all()
            for old_clip in old_shot_clips:
                video_storage.remove_artifact_file(old_clip.file_path)
            db.query(DBVideoShotClip).filter(DBVideoShotClip.shot_id.in_(old_shot_ids)).delete(synchronize_session=False)
            db.query(DBVideoShot).filter(DBVideoShot.id.in_(old_shot_ids)).delete(synchronize_session=False)
        old_assets = db.query(DBVideoSceneAsset).filter(DBVideoSceneAsset.scene_id.in_(old_scene_ids)).all()
        for old_asset in old_assets:
            video_storage.remove_artifact_file(old_asset.file_path)
        old_prompts = db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id.in_(old_scene_ids)).all()
        for old_prompt in old_prompts:
            video_storage.remove_artifact_file(old_prompt.prompt_path)
        db.query(DBVideoSceneAsset).filter(DBVideoSceneAsset.scene_id.in_(old_scene_ids)).delete(synchronize_session=False)
        db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id.in_(old_scene_ids)).delete(synchronize_session=False)
    subtitles = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).all()
    for subtitle in subtitles:
        video_storage.remove_artifact_file(subtitle.subtitle_path)
    db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).delete()

    now = datetime.utcnow()
    rows: list[DBVideoScene] = []
    for index, scene in enumerate(data.scenes, start=1):
        row = DBVideoScene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_order=index,
            title=scene.title,
            dialogue=scene.dialogue,
            visual_description=scene.visual_description,
            target_duration_seconds=scene.target_duration_seconds,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows.append(row)

    project.script_approved = False
    project.story_approved = False
    project.retention_plan_json = None
    project.sound_design_plan_json = None
    project.planning_status = "script_ready"
    video_rendering.mark_render_outputs_stale(project_id, db)
    video_state.mark_package_stale(project, db)
    project.status = "script_ready"
    project.updated_at = now
    db.commit()
    for row in rows:
        db.refresh(row)
    return [models.VideoSceneResponse.model_validate(row) for row in rows]

def update_scene(
    project_id: str,
    scene_id: str,
    patch: models.VideoSceneUpdate,
    db: Session,
) -> models.VideoSceneResponse | None:
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if scene is None:
        return None
    data = patch.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(scene, key, value)
    if any(key in data for key in {"dialogue", "visual_description"}):
        scene.prompt_status = "stale"
        scene.voice_status = "stale"
        scene.subtitle_status = "stale"
        project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
        if project is not None:
            video_rendering.mark_render_outputs_stale(project_id, db)
            video_state.mark_package_stale(project, db)
    scene.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return models.VideoSceneResponse.model_validate(scene)

def set_script_approved(
    project_id: str,
    approved: bool,
    db: Session,
) -> models.VideoProjectResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    project.script_approved = approved
    project.status = "script_approved" if approved else "script_ready"
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return _project_response(project, db)

def set_scene_approved(
    project_id: str,
    scene_id: str,
    approved: bool,
    db: Session,
) -> models.VideoSceneResponse | None:
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if scene is None:
        return None
    scene.approved = approved
    scene.updated_at = datetime.utcnow()
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is not None:
        video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(scene)
    return models.VideoSceneResponse.model_validate(scene)

def set_scene_no_narration(
    project_id: str,
    scene_id: str,
    no_narration: bool,
    db: Session,
) -> models.VideoSceneResponse | None:
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if scene is None:
        return None
    scene.no_narration = no_narration
    if no_narration:
        scene.voice_status = "skipped"
        scene.generation_id = None
        scene.audio_path = None
        scene.audio_duration = None
        scene.voice_failure_reason = None
    elif scene.voice_status == "skipped":
        scene.voice_status = "missing"
    scene.subtitle_status = "stale"
    scene.updated_at = datetime.utcnow()
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is not None:
        video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(scene)
    return models.VideoSceneResponse.model_validate(scene)

def get_project_status(project_id: str, db: Session) -> models.VideoProjectStatusResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    from . import video_planning_pool

    planning_info = video_planning_pool.active_project_info(project_id)
    _sync_voice_statuses(project_id, db)
    scenes = _ordered_scenes(project_id, db)
    approved_scenes = [scene for scene in scenes if scene.approved]
    scene_ids = [scene.id for scene in approved_scenes]
    prompt_scene_ids = {
        row[0]
        for row in db.query(DBVideoScenePrompt.scene_id)
        .filter(DBVideoScenePrompt.project_id == project_id)
        .all()
    }
    shot_rows = (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc())
        .all()
    )
    completed_prompt_shot_ids = {
        row[0]
        for row in db.query(DBVideoShotPrompt.shot_id)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.quality_status == "passed")
        .all()
    }
    missing_video_prompt_shot_ids = [
        shot.id for shot in shot_rows if shot.id not in completed_prompt_shot_ids or shot.prompt_status in {"missing", "needs_review", "stale"}
    ]
    stale_prompt_shot_ids = [shot.id for shot in shot_rows if shot.prompt_status == "stale"]
    missing_prompt = [scene.id for scene in approved_scenes if scene.id not in prompt_scene_ids]
    if shot_rows:
        missing_prompt = []
    if shot_rows:
        missing_voice = []
        missing_voice_shot_ids = [
            shot.id
            for shot in shot_rows
            if (shot.english_narration or "").strip()
            and (shot.voice_status != "completed" or not shot.audio_path or not shot.audio_duration)
        ]
    else:
        missing_voice = [
            scene.id
            for scene in approved_scenes
            if scene.voice_status != "completed" and scene.dialogue.strip() and not scene.no_narration
        ]
        missing_voice_shot_ids = []
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    missing_subtitle = subtitle is None or subtitle.status != "completed"
    missing_scene_ids = sorted(set(missing_prompt + missing_voice))
    has_script_items = bool(scene_ids or shot_rows)
    return models.VideoProjectStatusResponse(
        project_id=project_id,
        planning_active=planning_info is not None,
        planning_active_step=str(planning_info.get("step_name")) if planning_info else None,
        missing_script=not has_script_items,
        missing_prompt=bool(missing_prompt),
        missing_voice=bool(missing_voice or missing_voice_shot_ids),
        missing_subtitle=missing_subtitle,
        package_stale=bool(project.package_stale),
        package_ready=has_script_items
        and not missing_prompt
        and not missing_video_prompt_shot_ids
        and not missing_voice
        and not missing_voice_shot_ids
        and not missing_subtitle,
        missing_scene_ids=missing_scene_ids,
        story_approved=bool(project.story_approved),
        missing_source_blocks=(
            db.query(func.count(DBVideoSourceBlock.id)).filter(DBVideoSourceBlock.project_id == project_id).scalar() or 0
        ) == 0,
        missing_shots=bool(project.phase == "phase2" and not shot_rows),
        missing_video_prompt_shot_ids=missing_video_prompt_shot_ids,
        stale_prompt_shot_ids=stale_prompt_shot_ids,
        missing_voice_shot_ids=missing_voice_shot_ids,
    )
