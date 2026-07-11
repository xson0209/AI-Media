"""Local structured logging for AI Video phase 2."""

from __future__ import annotations

import json
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy.orm import Session

from ..database import VideoDebugEvent as DBVideoDebugEvent, VideoProject as DBVideoProject
from . import video_errors, video_storage

_MAX_TEXT = 1200
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|bearer|authorization|password|cookie)\s*[:=]\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[^\s,;]+")

def _redact_value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [_redact_value(item) for item in value[:40]]
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("token", "secret", "api_key", "apikey", "authorization", "password", "cookie")):
                safe[str(key)] = "[redacted]"
            else:
                safe[str(key)] = _redact_value(item)
        return safe
    text = str(value)
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _BEARER_PATTERN.sub("bearer [redacted]", text)
    if len(text) > _MAX_TEXT:
        return f"{text[:_MAX_TEXT]}...[truncated]"
    return text

def redacted_json(data: Any) -> str | None:
    if data is None:
        return None
    return json.dumps(_redact_value(data), ensure_ascii=False, default=str)

def _log_file(project_id: str, db: Session) -> str | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    path = video_storage.get_project_subdir(project_id, "logs") / video_storage.debug_log_filename(project.title)
    return video_storage.to_artifact_storage_path(path)

def log_event(
    db: Session,
    *,
    step_name: str,
    status: str = "info",
    message: str | None = None,
    project_id: str | None = None,
    scene_id: str | None = None,
    shot_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    duration_ms: float | None = None,
    retry_count: int = 0,
    error_code: str | None = None,
    exc: BaseException | None = None,
    technical_details: Any | None = None,
    validation_errors: Any | None = None,
    request_id: str | None = None,
) -> DBVideoDebugEvent:
    request_id = request_id or video_errors.current_request_id()
    row = DBVideoDebugEvent(
        id=str(uuid.uuid4()),
        request_id=request_id,
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        step_name=step_name,
        status=status,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        retry_count=retry_count,
        error_code=error_code,
        exception_class=exc.__class__.__name__ if exc else None,
        message=_redact_value(message),
        technical_details=redacted_json(technical_details),
        validation_errors=_redact_value(validation_errors),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    if project_id:
        project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
        if project is not None:
            project.last_request_id = request_id
    db.commit()
    db.refresh(row)

    if project_id:
        path_value = _log_file(project_id, db)
        path = video_storage.resolve_artifact_storage_path(path_value)
        if path is not None:
            payload = {
                "id": row.id,
                "request_id": row.request_id,
                "project_id": row.project_id,
                "scene_id": row.scene_id,
                "shot_id": row.shot_id,
                "step_name": row.step_name,
                "status": row.status,
                "provider": row.provider,
                "model": row.model,
                "duration_ms": row.duration_ms,
                "retry_count": row.retry_count,
                "error_code": row.error_code,
                "exception_class": row.exception_class,
                "message": row.message,
                "technical_details": row.technical_details,
                "validation_errors": row.validation_errors,
                "created_at": row.created_at.isoformat(),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    video_errors.log_step(
        message or step_name,
        level=20 if status not in {"warning", "failure"} else 30,
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        step_name=step_name,
        status=status,
        error_code=error_code,
    )
    return row

@contextmanager
def log_timed_step(
    db: Session,
    *,
    step_name: str,
    project_id: str | None = None,
    scene_id: str | None = None,
    shot_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Iterator[None]:
    started = time.perf_counter()
    log_event(
        db,
        step_name=step_name,
        status="start",
        message=f"Bắt đầu {step_name}",
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        provider=provider,
        model=model,
    )
    try:
        yield
    except Exception as exc:
        log_event(
            db,
            step_name=step_name,
            status="failure",
            message=str(exc),
            project_id=project_id,
            scene_id=scene_id,
            shot_id=shot_id,
            provider=provider,
            model=model,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            exc=exc,
        )
        raise
    else:
        log_event(
            db,
            step_name=step_name,
            status="success",
            message=f"Hoàn tất {step_name}",
            project_id=project_id,
            scene_id=scene_id,
            shot_id=shot_id,
            provider=provider,
            model=model,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

def latest_events(project_id: str, db: Session, *, limit: int = 40) -> list[DBVideoDebugEvent]:
    return (
        db.query(DBVideoDebugEvent)
        .filter(DBVideoDebugEvent.project_id == project_id)
        .order_by(DBVideoDebugEvent.created_at.desc())
        .limit(limit)
        .all()
    )

def latest_log_path(project_id: str, db: Session) -> str | None:
    return _log_file(project_id, db)
