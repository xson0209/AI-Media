"""Prompt and preview-image helpers for AI Video Assistant."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoSceneAsset as DBVideoSceneAsset,
    VideoScenePrompt as DBVideoScenePrompt,
)
from . import video_errors, video_state, video_storage

SUPPORTED_PREVIEW_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PREVIEW_IMAGE_BYTES = 25 * 1024 * 1024

class VideoAssetError(ValueError):
    """Raised when an image/prompt asset operation cannot complete."""

def _scene_label(scene: DBVideoScene) -> str:
    return video_storage.scene_number(scene.scene_order)

def _latest_prompt(project_id: str, scene_id: str, db: Session) -> DBVideoScenePrompt | None:
    return (
        db.query(DBVideoScenePrompt)
        .filter(DBVideoScenePrompt.project_id == project_id, DBVideoScenePrompt.scene_id == scene_id)
        .order_by(DBVideoScenePrompt.version.desc(), DBVideoScenePrompt.created_at.desc())
        .first()
    )

def _prompt_content(prompt: DBVideoScenePrompt, project: DBVideoProject) -> str:
    parts = [prompt.main_prompt.strip(), "", f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}"]
    if prompt.negative_prompt:
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.style_notes:
        parts.extend(["", "Style notes:", prompt.style_notes.strip()])
    if prompt.character_notes:
        parts.extend(["", "Character consistency:", prompt.character_notes.strip()])
    return "\n".join(parts).strip() + "\n"

def get_prompt_content(
    project_id: str,
    scene_id: str,
    db: Session,
) -> models.VideoPromptContentResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    prompt = _latest_prompt(project_id, scene_id, db)
    if project is None or scene is None or prompt is None:
        return None
    content = _prompt_content(prompt, project)
    if prompt.prompt_path:
        path = video_storage.resolve_artifact_storage_path(prompt.prompt_path)
        if path and path.exists():
            content = path.read_text(encoding="utf-8")
    return models.VideoPromptContentResponse(
        project_id=project_id,
        scene_id=scene_id,
        prompt_id=prompt.id,
        filename=video_storage.prompt_filename(scene.scene_order),
        content=content,
    )

def get_prompt_download(project_id: str, scene_id: str, db: Session) -> tuple[str, str] | None:
    content = get_prompt_content(project_id, scene_id, db)
    if content is None:
        return None
    return content.filename, content.content

def get_prompt_pack_download(project_id: str, db: Session) -> tuple[str, str] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    scenes = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )
    sections: list[str] = []
    for scene in scenes:
        prompt = _latest_prompt(project_id, scene.id, db)
        if prompt is None:
            continue
        sections.append(f"# {_scene_label(scene)}\n\n{_prompt_content(prompt, project).strip()}")
    if not sections:
        return None
    filename = video_storage.prompt_pack_filename(project.title)
    return filename, "\n\n---\n\n".join(sections).strip() + "\n"

def upload_preview_image(
    project_id: str,
    scene_id: str,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    db: Session,
) -> models.VideoSceneAssetResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    scene = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id, DBVideoScene.id == scene_id)
        .first()
    )
    if project is None or scene is None:
        return None
    if len(data) > MAX_PREVIEW_IMAGE_BYTES:
        video_errors.log_error(
            "Preview image rejected because it is too large",
            project_id=project_id,
            scene_id=scene_id,
            sanitized_filename=video_storage.sanitize_download_filename(filename or "preview-image"),
            mime_type=content_type,
            file_size=len(data),
            reject_reason="too_large",
            step_name="preview_image_upload",
        )
        raise VideoAssetError("Ảnh preview quá lớn. Giới hạn hiện tại là 25MB.")
    ext = Path(filename or "preview.png").suffix.lower() or ".png"
    if ext not in SUPPORTED_PREVIEW_EXTENSIONS:
        video_errors.log_error(
            "Preview image rejected because extension is unsupported",
            project_id=project_id,
            scene_id=scene_id,
            sanitized_filename=video_storage.sanitize_download_filename(filename or "preview-image"),
            mime_type=content_type,
            file_size=len(data),
            reject_reason="unsupported_extension",
            step_name="preview_image_upload",
        )
        raise VideoAssetError("Định dạng ảnh không được hỗ trợ. Chỉ nhận PNG, JPG, JPEG hoặc WEBP.")

    asset_dir = video_storage.get_project_subdir(project_id, "preview_images")
    safe_original = video_storage.sanitize_download_filename(filename or "preview-image")
    target = asset_dir / f"scene-{scene.scene_order:02d}-preview-{uuid.uuid4()}{ext}"
    target.write_bytes(data)
    try:
        with Image.open(target) as image:
            image.verify()
    except Exception as exc:
        target.unlink(missing_ok=True)
        video_errors.log_error(
            "Preview image rejected because file verification failed",
            exc=exc,
            project_id=project_id,
            scene_id=scene_id,
            sanitized_filename=safe_original,
            mime_type=content_type,
            file_size=len(data),
            reject_reason="invalid_image",
            step_name="preview_image_upload",
        )
        raise VideoAssetError("File upload không phải ảnh hợp lệ.") from exc

    old_active_assets = (
        db.query(DBVideoSceneAsset)
        .filter(
            DBVideoSceneAsset.project_id == project_id,
            DBVideoSceneAsset.scene_id == scene_id,
            DBVideoSceneAsset.asset_type == "preview_image",
            DBVideoSceneAsset.is_active.is_(True),
        )
        .all()
    )
    db.query(DBVideoSceneAsset).filter(
        DBVideoSceneAsset.project_id == project_id,
        DBVideoSceneAsset.scene_id == scene_id,
        DBVideoSceneAsset.asset_type == "preview_image",
        DBVideoSceneAsset.is_active.is_(True),
    ).update({"is_active": False}, synchronize_session=False)

    guessed_type, _ = mimetypes.guess_type(target.name)
    row = DBVideoSceneAsset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        asset_type="preview_image",
        file_path=video_storage.to_artifact_storage_path(target),
        original_filename=safe_original,
        mime_type=content_type or guessed_type or "application/octet-stream",
        size_bytes=len(data),
        is_active=True,
    )
    db.add(row)
    video_state.mark_package_stale(project, db)
    db.commit()
    db.refresh(row)
    for old_asset in old_active_assets:
        video_storage.remove_artifact_file(old_asset.file_path)
    video_errors.log_step(
        "Preview image uploaded",
        project_id=project_id,
        scene_id=scene_id,
        asset_id=row.id,
        sanitized_filename=safe_original,
        mime_type=row.mime_type,
        file_size=row.size_bytes,
        step_name="preview_image_upload",
    )
    return models.VideoSceneAssetResponse.model_validate(row)

def get_preview_asset(asset_id: str, db: Session) -> DBVideoSceneAsset | None:
    return db.query(DBVideoSceneAsset).filter(DBVideoSceneAsset.id == asset_id).first()

def get_active_preview_asset(project_id: str, scene_id: str, db: Session) -> DBVideoSceneAsset | None:
    return (
        db.query(DBVideoSceneAsset)
        .filter(
            DBVideoSceneAsset.project_id == project_id,
            DBVideoSceneAsset.scene_id == scene_id,
            DBVideoSceneAsset.asset_type == "preview_image",
            DBVideoSceneAsset.is_active.is_(True),
        )
        .first()
    )

def resolve_asset_file(asset: DBVideoSceneAsset) -> Path | None:
    path = video_storage.resolve_artifact_storage_path(asset.file_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    return path
