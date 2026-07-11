"""Codex-backed planning and prompt generation for AI Video Assistant."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoScenePrompt as DBVideoScenePrompt,
)
from . import ai_planning, settings as settings_service, video_errors, video_planning_pool, video_state, video_storage

logger = logging.getLogger(__name__)

class ScenePlan(BaseModel):
    title: str = Field(default="", max_length=160)
    dialogue: str = Field(default="", max_length=20000)
    visual_description: str = Field(default="", max_length=4000)
    target_duration_seconds: int | None = Field(default=None, ge=1, le=3600)

class ProjectPlan(BaseModel):
    creative_brief: str = Field(default="", max_length=12000)
    script_text: str = Field(default="", max_length=50000)
    style_bible: str = Field(default="", max_length=12000)
    character_bible: str = Field(default="", max_length=12000)
    scenes: list[ScenePlan] = Field(..., min_length=1, max_length=200)

class ScenePromptPlan(BaseModel):
    scene_order: int = Field(..., ge=1)
    main_prompt: str = Field(..., min_length=1, max_length=12000)
    negative_prompt: str = Field(default="", max_length=4000)
    style_notes: str = Field(default="", max_length=4000)
    character_notes: str = Field(default="", max_length=4000)

class PromptPackPlan(BaseModel):
    style_bible: str = Field(default="", max_length=12000)
    character_bible: str = Field(default="", max_length=12000)
    prompts: list[ScenePromptPlan] = Field(..., min_length=1, max_length=200)

PROJECT_PLAN_SCHEMA = ProjectPlan.model_json_schema()
SCENE_PLAN_SCHEMA = ScenePlan.model_json_schema()
PROMPT_PACK_SCHEMA = PromptPackPlan.model_json_schema()

class VideoPlanningValidationError(ValueError):
    """Raised when Codex output is not valid planning JSON."""

def _load_json_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise VideoPlanningValidationError("Codex output is not JSON.") from None
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise VideoPlanningValidationError("Codex output contains invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise VideoPlanningValidationError("Codex output must be a JSON object.")
    return parsed

def _project_context(project: DBVideoProject) -> str:
    return (
        f"Tên dự án: {project.title}\n"
        f"Chủ đề: {project.topic}\n"
        f"Ngôn ngữ: {project.language}\n"
        f"Thời lượng mục tiêu: {project.target_duration_seconds or 'tự chọn'} giây\n"
        f"Tỷ lệ khung hình: {project.aspect_ratio}\n"
        f"Phong cách ảnh: {project.visual_style or 'tự đề xuất'}\n"
    )

def _language_instruction(language: str) -> str:
    if language.lower().startswith("vi"):
        return "Viết toàn bộ nội dung người dùng đọc bằng tiếng Việt tự nhiên, dễ hiểu cho người không rành kỹ thuật."
    return f"Write user-facing script content in language code `{language}`."

def _run_structured_codex(
    db: Session,
    project_id: str,
    step_name: str,
    prompt: str,
    schema: dict,
) -> dict:
    settings = settings_service.get_ai_planning_settings(db)
    schema_properties = schema.get("properties") if isinstance(schema, dict) else None
    schema_keys = sorted(str(key) for key in schema_properties)[:20] if isinstance(schema_properties, dict) else []
    log_details = {
        "prompt_chars": len(prompt),
        "schema_keys": schema_keys,
        "timeout_seconds": settings.timeout_seconds,
    }
    try:
        with video_planning_pool.planning_slot(
            db,
            project_id=project_id,
            step_name=step_name,
            provider=settings.provider,
            model=settings.model,
            details=log_details,
        ):
            raw = ai_planning.run_codex_exec(settings, prompt, output_schema=schema)
            try:
                return _load_json_object(raw)
            except VideoPlanningValidationError as exc:
                video_errors.log_error(
                    "Codex planning output failed JSON validation",
                    exc=exc,
                    project_id=project_id,
                    step_name="planning_output_validation",
                    output_chars=len(raw or ""),
                )
                raise
    except ai_planning.AIPlanningError:
        raise
    except VideoPlanningValidationError:
        raise
    except Exception as exc:
        logger.exception("Unexpected Codex planning failure")
        raise ai_planning.AIPlanningError(
            "Codex CLI gặp lỗi khi tạo nội dung.",
            error_code="CODEX_PLANNING_FAILED",
        ) from exc

def generate_project_plan(project_id: str, db: Session) -> models.VideoProjectDetailResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None

    prompt = f"""
Bạn là AI Video Assistant trong app Voicebox. Nhiệm vụ: từ ý tưởng ngắn, tạo kịch bản video có cấu trúc để người dùng mang vào Premiere.

{_project_context(project)}

Yêu cầu:
- {_language_instruction(project.language)}
- Chia thành các scene rõ ràng.
- Mỗi scene có dialogue để Voicebox đọc, visual_description để tạo prompt ảnh, và target_duration_seconds.
- Không tạo hướng dẫn kỹ thuật dài dòng cho người dùng.
- Trả về đúng JSON theo schema, không thêm markdown.
""".strip()

    try:
        plan = ProjectPlan.model_validate(_run_structured_codex(db, project_id, "project_plan", prompt, PROJECT_PLAN_SCHEMA))
    except ValidationError as exc:
        logger.warning("Invalid project plan from Codex", extra={"project_id": project_id, "errors": exc.errors()})
        video_errors.log_error(
            "Invalid project plan from Codex",
            exc=exc,
            project_id=project_id,
            validation_errors=exc.errors(),
            step_name="project_plan_validation",
        )
        raise VideoPlanningValidationError("Codex trả về kịch bản không đúng cấu trúc.") from exc

    now = datetime.utcnow()
    project.creative_brief = plan.creative_brief
    project.script_text = plan.script_text
    project.style_bible = plan.style_bible
    project.character_bible = plan.character_bible
    project.script_approved = False
    video_state.mark_package_stale(project, db)
    project.status = "script_ready"
    project.updated_at = now

    old_scenes = db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).all()
    old_scene_ids = [scene.id for scene in old_scenes]
    if old_scene_ids:
        old_prompts = db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id.in_(old_scene_ids)).all()
        for old_prompt in old_prompts:
            video_storage.remove_artifact_file(old_prompt.prompt_path)
        db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id.in_(old_scene_ids)).delete(synchronize_session=False)
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).delete()

    for index, scene in enumerate(plan.scenes, start=1):
        db.add(
            DBVideoScene(
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
        )

    db.commit()
    db.refresh(project)
    from . import video_projects

    return video_projects.get_project(project_id, db)

def regenerate_scene(project_id: str, scene_id: str, db: Session) -> models.VideoSceneResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if project is None or scene is None:
        return None

    prompt = f"""
Bạn là AI Video Assistant trong app Voicebox. Hãy viết lại một scene duy nhất, giữ đúng mục tiêu của project.

{_project_context(project)}

Scene hiện tại:
- Thứ tự: {scene.scene_order}
- Tiêu đề: {scene.title or ''}
- Lời thoại: {scene.dialogue}
- Mô tả hình ảnh: {scene.visual_description or ''}

Yêu cầu:
- {_language_instruction(project.language)}
- Chỉ trả JSON cho scene này theo schema.
- Không đổi thứ tự scene.
""".strip()

    try:
        plan = ScenePlan.model_validate(_run_structured_codex(db, project_id, "scene_regenerate", prompt, SCENE_PLAN_SCHEMA))
    except ValidationError as exc:
        logger.warning("Invalid regenerated scene from Codex", extra={"project_id": project_id, "scene_id": scene_id})
        video_errors.log_error(
            "Invalid regenerated scene from Codex",
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            validation_errors=exc.errors(),
            step_name="scene_regenerate_validation",
        )
        raise VideoPlanningValidationError("Codex trả về scene không đúng cấu trúc.") from exc

    scene.title = plan.title
    scene.dialogue = plan.dialogue
    scene.visual_description = plan.visual_description
    scene.target_duration_seconds = plan.target_duration_seconds
    scene.prompt_status = "stale"
    scene.voice_status = "stale" if plan.dialogue.strip() and not scene.no_narration else scene.voice_status
    scene.subtitle_status = "stale"
    scene.updated_at = datetime.utcnow()
    video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(scene)
    return models.VideoSceneResponse.model_validate(scene)

def _prompt_text(prompt: ScenePromptPlan, project: DBVideoProject) -> str:
    parts = [
        prompt.main_prompt.strip(),
        "",
        f"Aspect ratio: {project.aspect_ratio}",
    ]
    if prompt.negative_prompt.strip():
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.style_notes.strip():
        parts.extend(["", "Style notes:", prompt.style_notes.strip()])
    if prompt.character_notes.strip():
        parts.extend(["", "Character consistency:", prompt.character_notes.strip()])
    return "\n".join(parts).strip() + "\n"

def generate_prompt_pack(project_id: str, db: Session) -> models.VideoPromptPackResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    scenes = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.approved.is_(True))
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )
    if not scenes:
        raise VideoPlanningValidationError("Cần duyệt ít nhất một scene trước khi tạo prompt ảnh.")

    scene_lines = "\n".join(
        f"Scene {scene.scene_order}: title={scene.title or ''}; dialogue={scene.dialogue}; visual={scene.visual_description or ''}"
        for scene in scenes
    )
    prompt = f"""
Bạn là chuyên gia prompt ảnh cho video dựng trong Premiere. Tạo prompt ảnh nhất quán cho từng scene đã duyệt.

{_project_context(project)}

Style bible hiện có: {project.style_bible or 'chưa có'}
Character bible hiện có: {project.character_bible or 'chưa có'}

Scene đã duyệt:
{scene_lines}

Yêu cầu:
- Prompt nên viết bằng tiếng Anh để dùng tốt với GPT Image, Flux, SDXL hoặc Midjourney.
- Giữ nhất quán nhân vật, bối cảnh, ánh sáng, màu sắc và phong cách giữa các scene.
- Mỗi prompt phải có scene_order khớp scene gốc.
- Trả về đúng JSON theo schema, không thêm markdown.
""".strip()

    try:
        pack = PromptPackPlan.model_validate(_run_structured_codex(db, project_id, "prompt_pack", prompt, PROMPT_PACK_SCHEMA))
    except ValidationError as exc:
        logger.warning("Invalid prompt pack from Codex", extra={"project_id": project_id, "errors": exc.errors()})
        video_errors.log_error(
            "Invalid prompt pack from Codex",
            exc=exc,
            project_id=project_id,
            validation_errors=exc.errors(),
            step_name="prompt_pack_validation",
        )
        raise VideoPlanningValidationError("Codex trả về prompt ảnh không đúng cấu trúc.") from exc

    now = datetime.utcnow()
    project.style_bible = pack.style_bible or project.style_bible
    project.character_bible = pack.character_bible or project.character_bible
    video_state.mark_package_stale(project, db)

    scenes_by_order = {scene.scene_order: scene for scene in scenes}
    created: list[DBVideoScenePrompt] = []
    prompt_dir = video_storage.get_project_subdir(project_id, "prompts")
    for item in pack.prompts:
        scene = scenes_by_order.get(item.scene_order)
        if scene is None:
            continue
        version = (
            db.query(func.max(DBVideoScenePrompt.version))
            .filter(DBVideoScenePrompt.scene_id == scene.id)
            .scalar()
            or 0
        ) + 1
        previous_prompts = db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id == scene.id).all()
        for previous_prompt in previous_prompts:
            video_storage.remove_artifact_file(previous_prompt.prompt_path)
        db.query(DBVideoScenePrompt).filter(DBVideoScenePrompt.scene_id == scene.id).delete(synchronize_session=False)
        row = DBVideoScenePrompt(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=scene.id,
            version=version,
            main_prompt=item.main_prompt,
            negative_prompt=item.negative_prompt,
            aspect_ratio=project.aspect_ratio,
            style_notes=item.style_notes,
            character_notes=item.character_notes,
            created_at=now,
        )
        prompt_path = prompt_dir / f"scene-{scene.scene_order:02d}-prompt-{row.id}.txt"
        prompt_path.write_text(_prompt_text(item, project), encoding="utf-8")
        row.prompt_path = video_storage.to_artifact_storage_path(prompt_path)
        scene.prompt_status = "completed"
        scene.updated_at = now
        db.add(row)
        created.append(row)

    db.commit()
    for row in created:
        db.refresh(row)
    return models.VideoPromptPackResponse(
        project_id=project_id,
        prompts=[models.VideoScenePromptResponse.model_validate(row) for row in created],
    )
