"""Series reference assets, version history, dependency snapshots, and targeted stale events."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    ArtifactDependencySnapshot as DBArtifactDependencySnapshot,
    ArtifactStaleEvent as DBArtifactStaleEvent,
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    SeriesReferenceAsset as DBSeriesReferenceAsset,
    SeriesVersionRecord as DBSeriesVersionRecord,
    StoryAdaptation as DBStoryAdaptation,
    VideoSeries as DBVideoSeries,
)
from . import video_storage

REFERENCE_ENTITY_TYPES = {"character", "location"}
CHARACTER_REFERENCE_ROLES = {"face_front", "face_side", "full_body", "signature_outfit", "expression", "other"}
LOCATION_REFERENCE_ROLES = {"wide_view", "entrance", "interior", "landmark_detail", "lighting_reference", "other"}
SUPPORTED_REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_REFERENCE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MAX_REFERENCE_IMAGE_BYTES = 25 * 1024 * 1024
MIN_REFERENCE_DIMENSION = 64
MAX_REFERENCE_DIMENSION = 8192
THUMBNAIL_MAX_SIZE = (512, 512)

SENSITIVE_METADATA_KEYS = {
    "cookie",
    "cookies",
    "token",
    "access_token",
    "refresh_token",
    "credential",
    "credentials",
    "password",
    "secret",
    "chrome_profile_path",
    "browser_profile_path",
    "profile_path",
}

SCOPE_AFFECTS: dict[str, set[str]] = {
    "visual_identity": {"visual_identity", "reference_image"},
    "reference_image": {"reference_image", "visual_identity"},
    "story_state": {"story_state"},
    "camera_style": {"camera_style", "style"},
    "style": {"style", "camera_style"},
    "dialogue": {"dialogue", "narration", "timing"},
    "narration": {"dialogue", "narration", "timing"},
    "language": {"language", "dialogue", "narration"},
    "timing": {"timing", "narration"},
    "voice_profile": {"voice_profile"},
    "package": {"package"},
}

class SeriesReferenceError(ValueError):
    """Raised when a reference/version/dependency operation is invalid."""

def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _safe_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_METADATA_KEYS or any(part in normalized for part in ("cookie", "token", "credential", "password", "secret")):
                continue
            result[str(key)] = _safe_metadata(item) if isinstance(item, (dict, list)) else item
        return result
    if isinstance(value, list):
        return {"items": [_safe_metadata(item) if isinstance(item, (dict, list)) else item for item in value]}
    return {}

def _snapshot_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return _safe_metadata(value)
    if hasattr(value, "__table__"):
        data: dict[str, Any] = {}
        for column in value.__table__.columns:
            item = getattr(value, column.name)
            if isinstance(item, datetime):
                data[column.name] = item.isoformat()
            else:
                data[column.name] = item
        return _safe_metadata(data)
    return {}

def _require_series(series_id: str, db: Session) -> DBVideoSeries:
    row = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if row is None:
        raise SeriesReferenceError("Không tìm thấy series.")
    return row

def _normalize_text(value: object | None) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "á": "a", "à": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ắ": "a", "ằ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ấ": "a", "ầ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "đ": "d",
        "é": "e", "è": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ế": "e", "ề": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "í": "i", "ì": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ó": "o", "ò": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ố": "o", "ồ": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ớ": "o", "ờ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ú": "u", "ù": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ứ": "u", "ừ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ý": "y", "ỳ": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
    }
    for source, dest in replacements.items():
        text = text.replace(source, dest)
    return " ".join(text.split())

def _role_allowed(entity_type: str, reference_role: str) -> bool:
    if entity_type == "character":
        return reference_role in CHARACTER_REFERENCE_ROLES
    if entity_type == "location":
        return reference_role in LOCATION_REFERENCE_ROLES
    return False

def _validate_reference_target(series_id: str, entity_type: str, entity_id: str, reference_role: str, db: Session) -> None:
    if entity_type not in REFERENCE_ENTITY_TYPES:
        raise SeriesReferenceError("Loại thực thể ảnh tham chiếu không hợp lệ.")
    if not entity_id.strip():
        raise SeriesReferenceError("Thiếu mã thực thể cho ảnh tham chiếu.")
    if not _role_allowed(entity_type, reference_role):
        raise SeriesReferenceError("Vai trò ảnh tham chiếu không hợp lệ cho thực thể này.")
    if entity_type == "character":
        exists = (
            db.query(DBSeriesCharacterProfile.id)
            .filter(DBSeriesCharacterProfile.series_id == series_id, DBSeriesCharacterProfile.id == entity_id)
            .first()
        )
        if exists is None:
            raise SeriesReferenceError("Không tìm thấy Hồ sơ nhân vật để gắn ảnh tham chiếu.")

def _reference_entity_dir(series_id: str, entity_type: str, entity_id: str) -> Path:
    safe_entity = video_storage.sanitize_download_filename(entity_id, fallback="entity", max_length=100)
    path = video_storage.get_series_dir(series_id) / "reference_assets" / entity_type / safe_entity
    path.mkdir(parents=True, exist_ok=True)
    return path

def _image_metadata(data: bytes) -> tuple[str, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            image_format = image.format or ""
            width, height = image.size
    except Exception as exc:
        raise SeriesReferenceError("File upload không phải ảnh hợp lệ.") from exc
    if image_format not in SUPPORTED_REFERENCE_FORMATS:
        raise SeriesReferenceError("Định dạng ảnh không được hỗ trợ. Chỉ nhận PNG, JPG, JPEG hoặc WEBP.")
    if width < MIN_REFERENCE_DIMENSION or height < MIN_REFERENCE_DIMENSION:
        raise SeriesReferenceError("Ảnh tham chiếu quá nhỏ. Cần tối thiểu 64x64 px.")
    if width > MAX_REFERENCE_DIMENSION or height > MAX_REFERENCE_DIMENSION:
        raise SeriesReferenceError("Ảnh tham chiếu quá lớn. Cạnh tối đa hiện tại là 8192 px.")
    return SUPPORTED_REFERENCE_FORMATS[image_format], width, height

def _write_thumbnail(data: bytes, target: Path) -> None:
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.thumbnail(THUMBNAIL_MAX_SIZE, Image.Resampling.LANCZOS)
        image.save(target, format="PNG", optimize=True)

def _reference_response(row: DBSeriesReferenceAsset, db: Session) -> models.SeriesReferenceAssetResponse:
    usage_count = (
        db.query(func.count(DBArtifactDependencySnapshot.id))
        .filter(
            DBArtifactDependencySnapshot.series_id == row.series_id,
            DBArtifactDependencySnapshot.dependency_type == "reference_asset",
            DBArtifactDependencySnapshot.dependency_id == row.id,
        )
        .scalar()
        or 0
    )
    return models.SeriesReferenceAssetResponse(
        id=row.id,
        series_id=row.series_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        reference_role=row.reference_role,
        label=row.label,
        asset_path=row.asset_path,
        thumbnail_path=row.thumbnail_path,
        provider_asset_id=row.provider_asset_id,
        original_filename=row.original_filename,
        mime_type=row.mime_type,
        width=row.width,
        height=row.height,
        file_size_bytes=row.file_size_bytes,
        checksum=row.checksum,
        source_type=row.source_type,
        approval_status=row.approval_status,
        revision=int(row.revision or 1),
        active=bool(row.active),
        metadata=_safe_metadata(row.metadata_json or {}),
        usage_count=int(usage_count),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

def _version_response(row: DBSeriesVersionRecord) -> models.SeriesVersionRecordResponse:
    return models.SeriesVersionRecordResponse(
        id=row.id,
        series_id=row.series_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        revision=int(row.revision or 1),
        snapshot=_safe_metadata(row.snapshot_json or {}),
        changed_by=row.changed_by,
        change_source=row.change_source,
        change_reason=row.change_reason,
        created_at=row.created_at,
    )

def record_version(
    db: Session,
    *,
    series_id: str,
    entity_type: str,
    entity_id: str,
    revision: int,
    snapshot: dict[str, Any],
    changed_by: str | None = None,
    change_source: str | None = "system",
    change_reason: str | None = None,
) -> DBSeriesVersionRecord:
    row = DBSeriesVersionRecord(
        id=str(uuid.uuid4()),
        series_id=series_id,
        entity_type=entity_type,
        entity_id=entity_id,
        revision=int(revision or 1),
        snapshot_json=_safe_metadata(snapshot),
        changed_by=changed_by,
        change_source=change_source,
        change_reason=change_reason,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    return row

def upload_reference_asset(
    series_id: str,
    *,
    entity_type: str,
    entity_id: str,
    reference_role: str,
    filename: str,
    data: bytes,
    db: Session,
    content_type: str | None = None,
    label: str | None = None,
    source_type: str | None = "upload",
    provider_asset_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.SeriesReferenceAssetResponse:
    _require_series(series_id, db)
    _validate_reference_target(series_id, entity_type, entity_id, reference_role, db)
    if not data:
        raise SeriesReferenceError("File ảnh tham chiếu đang trống.")
    if len(data) > MAX_REFERENCE_IMAGE_BYTES:
        raise SeriesReferenceError("Ảnh tham chiếu quá lớn. Giới hạn hiện tại là 25MB.")
    ext = Path(filename or "reference.png").suffix.lower() or ".png"
    if ext not in SUPPORTED_REFERENCE_EXTENSIONS:
        raise SeriesReferenceError("Tên file hoặc định dạng ảnh không được hỗ trợ. Chỉ nhận PNG, JPG, JPEG hoặc WEBP.")
    mime_type, width, height = _image_metadata(data)
    if content_type and not content_type.startswith("image/"):
        raise SeriesReferenceError("Loại file upload không phải ảnh.")

    now = datetime.utcnow()
    asset_id = str(uuid.uuid4())
    safe_original = video_storage.sanitize_download_filename(filename or "reference-image")
    target_dir = _reference_entity_dir(series_id, entity_type, entity_id)
    target = target_dir / f"{asset_id}{ext}"
    thumbnail = target_dir / f"{asset_id}-thumbnail.png"
    target.write_bytes(data)
    _write_thumbnail(data, thumbnail)
    row = DBSeriesReferenceAsset(
        id=asset_id,
        series_id=series_id,
        entity_type=entity_type,
        entity_id=entity_id,
        reference_role=reference_role,
        label=(label or "").strip() or safe_original,
        asset_path=video_storage.to_artifact_storage_path(target),
        thumbnail_path=video_storage.to_artifact_storage_path(thumbnail),
        provider_asset_id=provider_asset_id,
        original_filename=safe_original,
        mime_type=mime_type,
        width=width,
        height=height,
        file_size_bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
        source_type=source_type,
        approval_status="pending_approval",
        revision=1,
        active=False,
        metadata_json=_safe_metadata(metadata or {}),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    record_version(
        db,
        series_id=series_id,
        entity_type="reference_asset",
        entity_id=row.id,
        revision=1,
        snapshot=_snapshot_json(row),
        change_source=source_type or "upload",
        change_reason="Tải ảnh tham chiếu, chờ duyệt trước khi dùng trong prompt.",
    )
    db.commit()
    db.refresh(row)
    return _reference_response(row, db)

def list_reference_assets(
    series_id: str,
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    approval_status: str | None = None,
    active: bool | None = None,
) -> models.SeriesReferenceAssetListResponse:
    _require_series(series_id, db)
    query = db.query(DBSeriesReferenceAsset).filter(DBSeriesReferenceAsset.series_id == series_id)
    if entity_type:
        query = query.filter(DBSeriesReferenceAsset.entity_type == entity_type)
    if entity_id:
        query = query.filter(DBSeriesReferenceAsset.entity_id == entity_id)
    if approval_status:
        query = query.filter(DBSeriesReferenceAsset.approval_status == approval_status)
    if active is not None:
        query = query.filter(DBSeriesReferenceAsset.active.is_(active))
    rows = query.order_by(DBSeriesReferenceAsset.updated_at.desc(), DBSeriesReferenceAsset.created_at.desc()).all()
    return models.SeriesReferenceAssetListResponse(items=[_reference_response(row, db) for row in rows], total=len(rows))

def update_reference_asset_status(
    series_id: str,
    asset_id: str,
    data: models.SeriesReferenceAssetStatusRequest,
    db: Session,
) -> models.SeriesReferenceAssetResponse | None:
    row = (
        db.query(DBSeriesReferenceAsset)
        .filter(DBSeriesReferenceAsset.series_id == series_id, DBSeriesReferenceAsset.id == asset_id)
        .first()
    )
    if row is None:
        return None
    old_revision = int(row.revision or 1)
    changed = False
    if data.approval_status is not None and data.approval_status != row.approval_status:
        row.approval_status = data.approval_status
        changed = True
    if data.active is not None:
        if data.active and row.approval_status != "approved":
            raise SeriesReferenceError("Chỉ ảnh đã duyệt mới được kích hoạt để đưa vào prompt.")
        if bool(data.active) != bool(row.active):
            row.active = bool(data.active)
            changed = True
    if row.approval_status in {"rejected", "archived"} and row.active:
        row.active = False
        changed = True
    if changed:
        row.revision = old_revision + 1
        row.updated_at = datetime.utcnow()
        record_version(
            db,
            series_id=series_id,
            entity_type="reference_asset",
            entity_id=row.id,
            revision=int(row.revision or 1),
            snapshot=_snapshot_json(row),
            changed_by=data.changed_by,
            change_source="reference_asset_status",
            change_reason=data.reason or "Cập nhật trạng thái ảnh tham chiếu.",
        )
        mark_dependency_stale(
            series_id,
            dependency_type="reference_asset",
            dependency_id=row.id,
            changed_scope="reference_image",
            db=db,
            old_revision=old_revision,
            new_revision=int(row.revision or 1),
            reason_vi=data.reason or "Ảnh tham chiếu đã đổi trạng thái hoặc phiên bản.",
            commit=False,
        )
    db.commit()
    db.refresh(row)
    return _reference_response(row, db)

def delete_reference_asset(series_id: str, asset_id: str, db: Session) -> dict[str, Any] | None:
    row = (
        db.query(DBSeriesReferenceAsset)
        .filter(DBSeriesReferenceAsset.series_id == series_id, DBSeriesReferenceAsset.id == asset_id)
        .first()
    )
    if row is None:
        return None
    dependency_count = (
        db.query(func.count(DBArtifactDependencySnapshot.id))
        .filter(
            DBArtifactDependencySnapshot.series_id == series_id,
            DBArtifactDependencySnapshot.dependency_type == "reference_asset",
            DBArtifactDependencySnapshot.dependency_id == asset_id,
        )
        .scalar()
        or 0
    )
    if dependency_count:
        old_revision = int(row.revision or 1)
        row.active = False
        row.approval_status = "archived"
        row.revision = old_revision + 1
        row.updated_at = datetime.utcnow()
        record_version(
            db,
            series_id=series_id,
            entity_type="reference_asset",
            entity_id=row.id,
            revision=int(row.revision or 1),
            snapshot=_snapshot_json(row),
            change_source="reference_asset_safe_delete",
            change_reason="Không xóa file vì artifact cũ đang tham chiếu; đã lưu archive an toàn.",
        )
        mark_dependency_stale(
            series_id,
            dependency_type="reference_asset",
            dependency_id=row.id,
            changed_scope="reference_image",
            db=db,
            old_revision=old_revision,
            new_revision=int(row.revision or 1),
            reason_vi="Ảnh tham chiếu đang dùng đã bị vô hiệu hóa.",
            commit=False,
        )
        db.commit()
        return {"deleted": False, "archived": True, "dependency_count": int(dependency_count)}
    video_storage.remove_artifact_file(row.asset_path)
    video_storage.remove_artifact_file(row.thumbnail_path)
    db.delete(row)
    db.commit()
    return {"deleted": True, "archived": False, "dependency_count": 0}

def _asset_prompt_metadata(row: DBSeriesReferenceAsset) -> dict[str, Any]:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "reference_role": row.reference_role,
        "label": row.label,
        "revision": int(row.revision or 1),
        "mime_type": row.mime_type,
        "width": row.width,
        "height": row.height,
        "checksum": row.checksum,
        "asset_path": row.asset_path,
        "thumbnail_path": row.thumbnail_path,
        "provider_asset_id": row.provider_asset_id,
    }

def approved_reference_assets_for_prompt(
    series_id: str,
    db: Session,
    *,
    prompt_text: str | None = None,
    entity_refs: list[str | dict[str, Any]] | None = None,
) -> list[DBSeriesReferenceAsset]:
    _require_series(series_id, db)
    rows = (
        db.query(DBSeriesReferenceAsset)
        .filter(
            DBSeriesReferenceAsset.series_id == series_id,
            DBSeriesReferenceAsset.approval_status == "approved",
            DBSeriesReferenceAsset.active.is_(True),
        )
        .order_by(DBSeriesReferenceAsset.entity_type.asc(), DBSeriesReferenceAsset.reference_role.asc(), DBSeriesReferenceAsset.created_at.asc())
        .all()
    )
    if not rows:
        return []
    explicit_ids: set[str] = set()
    for ref in entity_refs or []:
        if isinstance(ref, str) and ref.strip():
            explicit_ids.add(ref.strip())
        elif isinstance(ref, dict):
            for key in ("id", "entity_id", "profile_id", "location_id"):
                value = ref.get(key)
                if isinstance(value, str) and value.strip():
                    explicit_ids.add(value.strip())
    if explicit_ids:
        return [row for row in rows if row.entity_id in explicit_ids or row.id in explicit_ids]

    text = _normalize_text(prompt_text)
    if not text:
        return rows
    matched_entity_ids: set[str] = set()
    profiles = db.query(DBSeriesCharacterProfile).filter(DBSeriesCharacterProfile.series_id == series_id).all()
    for profile in profiles:
        names = [profile.id, profile.name, profile.role]
        if any(_normalize_text(name) and _normalize_text(name) in text for name in names):
            matched_entity_ids.add(profile.id)
    for row in rows:
        candidates = [row.entity_id, row.label, row.reference_role]
        if row.entity_type == "location" and any(_normalize_text(item) and _normalize_text(item) in text for item in candidates):
            matched_entity_ids.add(row.entity_id)
    selected = [row for row in rows if row.entity_id in matched_entity_ids]
    return selected

def build_reference_provider_report(
    references: list[DBSeriesReferenceAsset],
    *,
    provider: str = "provider-neutral",
    provider_supports_references: bool = False,
) -> models.SeriesReferenceProviderReport:
    safe_refs = [_asset_prompt_metadata(row) for row in references]
    if provider_supports_references:
        return models.SeriesReferenceProviderReport(
            provider=provider,
            provider_supports_references=True,
            sent=safe_refs,
            skipped=[],
            fallback_text=None,
        )
    fallback_parts = [
        f"{item['label'] or item['id']} ({item['entity_type']}:{item['entity_id']}, {item['reference_role']}, rev {item['revision']})"
        for item in safe_refs
    ]
    return models.SeriesReferenceProviderReport(
        provider=provider,
        provider_supports_references=False,
        sent=[],
        skipped=[{**item, "reason_vi": "Provider hiện tại chưa hỗ trợ gửi ảnh tham chiếu trực tiếp."} for item in safe_refs],
        fallback_text="; ".join(fallback_parts) if fallback_parts else None,
    )

def build_reference_prompt_package(
    series_id: str,
    db: Session,
    *,
    prompt_text: str | None = None,
    entity_refs: list[str | dict[str, Any]] | None = None,
    provider: str = "provider-neutral",
    provider_supports_references: bool = False,
) -> dict[str, Any]:
    references = approved_reference_assets_for_prompt(series_id, db, prompt_text=prompt_text, entity_refs=entity_refs)
    report = build_reference_provider_report(
        references,
        provider=provider,
        provider_supports_references=provider_supports_references,
    )
    return {
        "reference_assets": [_asset_prompt_metadata(row) for row in references],
        "reference_asset_ids": [row.id for row in references],
        "provider_report": report.model_dump(mode="json"),
    }

def _dependency_response(row: DBArtifactDependencySnapshot) -> models.ArtifactDependencySnapshotResponse:
    return models.ArtifactDependencySnapshotResponse(
        id=row.id,
        series_id=row.series_id,
        artifact_type=row.artifact_type,
        artifact_id=row.artifact_id,
        artifact_revision=int(row.artifact_revision or 1),
        dependency_type=row.dependency_type,
        dependency_id=row.dependency_id,
        dependency_revision=int(row.dependency_revision or 1),
        dependency_scope=row.dependency_scope,
        metadata=_safe_metadata(row.metadata_json or {}),
        created_at=row.created_at,
    )

def record_dependency_snapshots(
    series_id: str,
    data: models.ArtifactDependencyRecordRequest,
    db: Session,
    *,
    commit: bool = True,
) -> list[models.ArtifactDependencySnapshotResponse]:
    _require_series(series_id, db)
    db.query(DBArtifactDependencySnapshot).filter(
        DBArtifactDependencySnapshot.series_id == series_id,
        DBArtifactDependencySnapshot.artifact_type == data.artifact_type,
        DBArtifactDependencySnapshot.artifact_id == data.artifact_id,
    ).delete(synchronize_session=False)
    rows: list[DBArtifactDependencySnapshot] = []
    now = datetime.utcnow()
    for dep in data.dependencies:
        row = DBArtifactDependencySnapshot(
            id=str(uuid.uuid4()),
            series_id=series_id,
            artifact_type=data.artifact_type,
            artifact_id=data.artifact_id,
            artifact_revision=data.artifact_revision,
            dependency_type=dep.dependency_type,
            dependency_id=dep.dependency_id,
            dependency_revision=dep.dependency_revision,
            dependency_scope=dep.dependency_scope,
            metadata_json=_safe_metadata(dep.metadata),
            created_at=now,
        )
        db.add(row)
        rows.append(row)
    if commit:
        db.commit()
        for row in rows:
            db.refresh(row)
    return [_dependency_response(row) for row in rows]

def dependencies_for_artifact(
    series_id: str,
    artifact_type: str,
    artifact_id: str,
    db: Session,
) -> list[models.ArtifactDependencySnapshotResponse]:
    _require_series(series_id, db)
    rows = (
        db.query(DBArtifactDependencySnapshot)
        .filter(
            DBArtifactDependencySnapshot.series_id == series_id,
            DBArtifactDependencySnapshot.artifact_type == artifact_type,
            DBArtifactDependencySnapshot.artifact_id == artifact_id,
        )
        .order_by(DBArtifactDependencySnapshot.created_at.asc())
        .all()
    )
    return [_dependency_response(row) for row in rows]

def _scope_matches(changed_scope: str, dependency_scope: str) -> bool:
    allowed = SCOPE_AFFECTS.get(changed_scope, {changed_scope})
    return dependency_scope in allowed or changed_scope == dependency_scope

def _stale_event_response(row: DBArtifactStaleEvent) -> models.ArtifactStaleEventResponse:
    return models.ArtifactStaleEventResponse(
        id=row.id,
        series_id=row.series_id,
        artifact_type=row.artifact_type,
        artifact_id=row.artifact_id,
        artifact_revision=int(row.artifact_revision or 1),
        dependency_type=row.dependency_type,
        dependency_id=row.dependency_id,
        old_revision=row.old_revision,
        new_revision=row.new_revision,
        changed_scope=row.changed_scope,
        dependency_scope=row.dependency_scope,
        reason_vi=row.reason_vi,
        propagation_rule=row.propagation_rule,
        status=row.status,
        metadata=_safe_metadata(row.metadata_json or {}),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )

def _apply_story_panel_stale(snapshot: DBArtifactDependencySnapshot, reason_vi: str, db: Session) -> None:
    metadata = _json_dict(snapshot.metadata_json)
    adaptation_id = metadata.get("adaptation_id")
    panel_order = metadata.get("panel_order")
    if not adaptation_id or panel_order is None:
        return
    row = db.query(DBStoryAdaptation).filter(DBStoryAdaptation.id == str(adaptation_id)).first()
    if row is None or not isinstance(row.payload_json, dict):
        return
    payload = dict(row.payload_json)
    panels = [dict(panel) for panel in payload.get("panels", []) if isinstance(panel, dict)]
    changed = False
    for panel in panels:
        if int(panel.get("order") or 0) == int(panel_order):
            panel["stale"] = True
            panel["stale_reason_vi"] = reason_vi
            panel["prompt_status"] = "stale"
            panel["render_status"] = "not_requested"
            changed = True
    if changed:
        payload["panels"] = panels
        row.payload_json = payload
        row.status = "stale"
        row.revision = int(row.revision or 1) + 1
        row.updated_at = datetime.utcnow()

def _apply_artifact_stale(snapshot: DBArtifactDependencySnapshot, reason_vi: str, db: Session) -> None:
    if snapshot.artifact_type == "story_panel":
        _apply_story_panel_stale(snapshot, reason_vi, db)
        return
    from ..features.ai_video import artifact_state

    artifact_state.apply_dependency_stale(snapshot, reason_vi, db)


def mark_dependency_stale(
    series_id: str,
    *,
    dependency_type: str,
    dependency_id: str,
    changed_scope: str,
    db: Session,
    old_revision: int | None = None,
    new_revision: int | None = None,
    reason_vi: str | None = None,
    commit: bool = True,
) -> models.ArtifactStaleEventListResponse:
    _require_series(series_id, db)
    snapshots = (
        db.query(DBArtifactDependencySnapshot)
        .filter(
            DBArtifactDependencySnapshot.series_id == series_id,
            DBArtifactDependencySnapshot.dependency_type == dependency_type,
            DBArtifactDependencySnapshot.dependency_id == dependency_id,
        )
        .all()
    )
    rows: list[DBArtifactStaleEvent] = []
    now = datetime.utcnow()
    reason = reason_vi or "Dữ liệu nguồn đã thay đổi nên artifact cần tạo lại đúng phạm vi."
    for snapshot in snapshots:
        if not _scope_matches(changed_scope, snapshot.dependency_scope):
            continue
        duplicate = (
            db.query(DBArtifactStaleEvent.id)
            .filter(
                DBArtifactStaleEvent.series_id == series_id,
                DBArtifactStaleEvent.artifact_type == snapshot.artifact_type,
                DBArtifactStaleEvent.artifact_id == snapshot.artifact_id,
                DBArtifactStaleEvent.dependency_type == dependency_type,
                DBArtifactStaleEvent.dependency_id == dependency_id,
                DBArtifactStaleEvent.changed_scope == changed_scope,
                DBArtifactStaleEvent.status == "active",
            )
            .first()
        )
        if duplicate is not None:
            from ..features.ai_video import artifact_state

            artifact_state.apply_dependency_stale(snapshot, reason, db, replay=True)
            continue
        event = DBArtifactStaleEvent(
            id=str(uuid.uuid4()),
            series_id=series_id,
            artifact_type=snapshot.artifact_type,
            artifact_id=snapshot.artifact_id,
            artifact_revision=int(snapshot.artifact_revision or 1),
            dependency_type=dependency_type,
            dependency_id=dependency_id,
            old_revision=old_revision if old_revision is not None else int(snapshot.dependency_revision or 1),
            new_revision=new_revision,
            changed_scope=changed_scope,
            dependency_scope=snapshot.dependency_scope,
            reason_vi=reason,
            propagation_rule=f"{changed_scope}->{snapshot.dependency_scope}",
            status="active",
            metadata_json=_safe_metadata(snapshot.metadata_json or {}),
            created_at=now,
        )
        db.add(event)
        rows.append(event)
        _apply_artifact_stale(snapshot, reason, db)
    if commit:
        db.commit()
        for row in rows:
            db.refresh(row)
    return models.ArtifactStaleEventListResponse(items=[_stale_event_response(row) for row in rows], total=len(rows))

def list_stale_events(
    series_id: str,
    db: Session,
    *,
    status: str | None = "active",
    artifact_type: str | None = None,
    limit: int = 100,
) -> models.ArtifactStaleEventListResponse:
    _require_series(series_id, db)
    query = db.query(DBArtifactStaleEvent).filter(DBArtifactStaleEvent.series_id == series_id)
    if status:
        query = query.filter(DBArtifactStaleEvent.status == status)
    if artifact_type:
        query = query.filter(DBArtifactStaleEvent.artifact_type == artifact_type)
    rows = query.order_by(DBArtifactStaleEvent.created_at.desc()).limit(limit).all()
    return models.ArtifactStaleEventListResponse(items=[_stale_event_response(row) for row in rows], total=len(rows))

def request_targeted_regeneration(
    series_id: str,
    data: models.ArtifactTargetedRegenerationRequest,
    db: Session,
) -> models.ArtifactTargetedRegenerationResponse:
    _require_series(series_id, db)
    query = db.query(DBArtifactStaleEvent).filter(DBArtifactStaleEvent.series_id == series_id, DBArtifactStaleEvent.status == "active")
    if data.event_ids:
        query = query.filter(DBArtifactStaleEvent.id.in_(data.event_ids))
    if data.artifact_type:
        query = query.filter(DBArtifactStaleEvent.artifact_type == data.artifact_type)
    if data.artifact_id:
        query = query.filter(DBArtifactStaleEvent.artifact_id == data.artifact_id)
    rows = query.all()
    now = datetime.utcnow()
    artifacts: list[dict[str, Any]] = []
    for row in rows:
        row.status = "regenerate_requested"
        row.resolved_at = now
        artifacts.append(
            {
                "artifact_type": row.artifact_type,
                "artifact_id": row.artifact_id,
                "reason_vi": row.reason_vi,
                "changed_scope": row.changed_scope,
            }
        )
    db.commit()
    return models.ArtifactTargetedRegenerationResponse(
        requested=len(rows),
        artifacts=artifacts,
        message=f"Đã ghi yêu cầu tạo lại đúng phạm vi cho {len(rows)} artifact.",
    )

def _diff_values(before: Any, after: Any) -> bool:
    return json.dumps(before, ensure_ascii=False, sort_keys=True, default=str) != json.dumps(after, ensure_ascii=False, sort_keys=True, default=str)

def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    text = " ".join(text.split())
    return text[:160] + ("..." if len(text) > 160 else "")

def version_history(
    series_id: str,
    entity_type: str,
    entity_id: str,
    db: Session,
) -> models.SeriesVersionHistoryResponse:
    _require_series(series_id, db)
    rows = (
        db.query(DBSeriesVersionRecord)
        .filter(
            DBSeriesVersionRecord.series_id == series_id,
            DBSeriesVersionRecord.entity_type == entity_type,
            DBSeriesVersionRecord.entity_id == entity_id,
        )
        .order_by(DBSeriesVersionRecord.revision.asc(), DBSeriesVersionRecord.created_at.asc())
        .all()
    )
    diff_vi: list[str] = []
    if len(rows) >= 2:
        before = _safe_metadata(rows[-2].snapshot_json or {})
        after = _safe_metadata(rows[-1].snapshot_json or {})
        keys = sorted(set(before) | set(after))
        for key in keys:
            if _diff_values(before.get(key), after.get(key)):
                diff_vi.append(f"{key}: đổi từ `{_short(before.get(key))}` sang `{_short(after.get(key))}`.")
    return models.SeriesVersionHistoryResponse(
        items=[_version_response(row) for row in rows],
        total=len(rows),
        diff_vi=diff_vi,
    )
