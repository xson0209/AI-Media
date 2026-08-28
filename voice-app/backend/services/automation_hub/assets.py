"""Immutable video asset snapshots for publishing jobs."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ... import config as app_config
from ...database import AutomationAsset, AutomationPublishJob, VideoRenderJob
from . import storage
from .config import get_config
from .schemas import AutomationAssetResponse


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
ACTIVE_JOB_STATUSES = {"queued", "scheduled", "preparing", "uploading", "finalizing"}


class AssetError(RuntimeError):
    def __init__(self, message: str, error_code: str = "AUTOMATION_ASSET_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _safe_filename(value: str | None) -> str:
    name = Path(value or "video.mp4").name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .") or "video.mp4"
    return stem[:180]


def to_response(row: AutomationAsset) -> AutomationAssetResponse:
    return AutomationAssetResponse(
        id=row.id,
        source_type=row.source_type,
        source_ref=row.source_ref,
        filename=row.filename,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=row.created_at,
    )


def list_assets(db: Session) -> list[AutomationAssetResponse]:
    return [to_response(row) for row in db.query(AutomationAsset).order_by(AutomationAsset.created_at.desc()).all()]


def get_asset(asset_id: str, db: Session) -> AutomationAsset | None:
    return db.query(AutomationAsset).filter(AutomationAsset.id == asset_id).first()


async def create_from_upload(upload: UploadFile, db: Session) -> AutomationAssetResponse:
    filename = _safe_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AssetError("Định dạng video chưa được hỗ trợ.", "AUTOMATION_ASSET_TYPE_UNSUPPORTED")
    asset_id = str(uuid.uuid4())
    target_dir = storage.assets_dir() / asset_id
    target_dir.mkdir(parents=False, exist_ok=False)
    target_path = target_dir / filename
    digest = hashlib.sha256()
    size = 0
    try:
        with target_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > get_config().max_upload_bytes:
                    raise AssetError("File video vượt giới hạn Automation Hub.", "AUTOMATION_ASSET_TOO_LARGE")
                digest.update(chunk)
                handle.write(chunk)
        if size <= 0:
            raise AssetError("File video rỗng.", "AUTOMATION_ASSET_EMPTY")
        row = AutomationAsset(
            id=asset_id,
            source_type="upload",
            stored_path=app_config.to_storage_path(target_path),
            filename=filename,
            mime_type=upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            size_bytes=size,
            sha256=digest.hexdigest(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_response(row)
    except Exception:
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        raise
    finally:
        await upload.close()


def import_render_output(render_job_id: str, db: Session) -> AutomationAssetResponse:
    render = db.query(VideoRenderJob).filter(VideoRenderJob.id == render_job_id).first()
    if render is None or not render.output_path or render.status != "completed":
        raise AssetError("Render output chưa sẵn sàng để import.", "AUTOMATION_RENDER_OUTPUT_NOT_READY")
    source = app_config.resolve_storage_path(render.output_path)
    if source is None or not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise AssetError("Không tìm thấy file video render hợp lệ.", "AUTOMATION_RENDER_FILE_MISSING")
    if source.stat().st_size > get_config().max_upload_bytes:
        raise AssetError("File video vượt giới hạn Automation Hub.", "AUTOMATION_ASSET_TOO_LARGE")
    asset_id = str(uuid.uuid4())
    filename = _safe_filename(source.name)
    target_dir = storage.assets_dir() / asset_id
    target_dir.mkdir(parents=False, exist_ok=False)
    target = target_dir / filename
    try:
        shutil.copy2(source, target)
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        row = AutomationAsset(
            id=asset_id,
            source_type="render_output",
            source_ref=render_job_id,
            stored_path=app_config.to_storage_path(target),
            filename=filename,
            mime_type=mimetypes.guess_type(filename)[0] or "video/mp4",
            size_bytes=target.stat().st_size,
            sha256=digest.hexdigest(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_response(row)
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise


def resolve_asset_path(row: AutomationAsset) -> Path:
    path = app_config.resolve_storage_path(row.stored_path)
    if path is None:
        raise AssetError("Asset không có đường dẫn hợp lệ.", "AUTOMATION_ASSET_PATH_INVALID")
    path = storage.ensure_within_root(path, storage.assets_dir())
    if not path.is_file():
        raise AssetError("File asset không còn tồn tại.", "AUTOMATION_ASSET_FILE_MISSING")
    return path


def delete_asset(asset_id: str, db: Session) -> bool:
    row = get_asset(asset_id, db)
    if row is None:
        return False
    active = (
        db.query(AutomationPublishJob)
        .filter(AutomationPublishJob.asset_id == asset_id, AutomationPublishJob.status.in_(ACTIVE_JOB_STATUSES))
        .first()
    )
    if active is not None:
        raise AssetError("Không thể xóa asset đang được publishing job sử dụng.", "AUTOMATION_ASSET_IN_USE")
    path = app_config.resolve_storage_path(row.stored_path)
    db.delete(row)
    db.commit()
    if path is not None:
        try:
            asset_root = storage.ensure_within_root(path.parent, storage.assets_dir())
            assets_root = storage.assets_dir().resolve()
            if asset_root != assets_root:
                shutil.rmtree(asset_root, ignore_errors=True)
        except ValueError:
            pass
    return True
