"""Flow/Veo project binding helpers for AI Video clip generation."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProviderProjectBinding as DBVideoProviderProjectBinding,
    VideoProject as DBVideoProject,
    VideoSeries as DBVideoSeries,
)
from . import chrome_cdp, video_provider_sessions

PROVIDER = "veo"
PROVIDER_TOOL = video_provider_sessions.DEFAULT_PROVIDER_TOOL
ACTIVE_STATUS = "active"
NEEDS_CHECK_STATUS = "needs_check"
INVALID_STATUS = "invalid"
ROTATED_STATUS = "rotated"
FLOW_MODEL_SELECTION_MODE = "use_current_flow_selection"
FLOW_ALLOW_AUTOMATIC_MODEL_CHANGE = False


class VideoProviderProjectBindingError(ValueError):
    """Raised when an operation needs a Flow project binding but cannot get one."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_PROVIDER_PROJECT_BINDING_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def now() -> datetime:
    return datetime.utcnow()


def safe_provider_project_url(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if parsed.scheme.lower() != "https" or host != "labs.google":
        return None
    if "/tools/flow/project/" not in path:
        return None
    return text


def provider_project_ref_hash(provider_project_url: str) -> str:
    return chrome_cdp.sha256_short(provider_project_url, length=24)


def scope_for_project(project: DBVideoProject) -> tuple[str, str]:
    if project.series_id:
        return "series", project.series_id
    return "project", project.id


def _scope_filter(query, project: DBVideoProject):
    scope, scope_id = scope_for_project(project)
    if scope == "series":
        return query.filter(
            DBVideoProviderProjectBinding.series_id == scope_id,
            DBVideoProviderProjectBinding.project_id.is_(None),
        )
    return query.filter(
        DBVideoProviderProjectBinding.project_id == scope_id,
        DBVideoProviderProjectBinding.series_id.is_(None),
    )


def active_binding_for_project(project: DBVideoProject, db: Session) -> DBVideoProviderProjectBinding | None:
    query = db.query(DBVideoProviderProjectBinding).filter(
        DBVideoProviderProjectBinding.provider == PROVIDER,
        DBVideoProviderProjectBinding.provider_tool == PROVIDER_TOOL,
        DBVideoProviderProjectBinding.status.in_([ACTIVE_STATUS, NEEDS_CHECK_STATUS]),
    )
    return _scope_filter(query, project).order_by(DBVideoProviderProjectBinding.updated_at.desc()).first()


def binding_for_project_response(project: DBVideoProject, db: Session) -> models.VideoProviderProjectBindingResponse | None:
    binding = active_binding_for_project(project, db)
    return binding_response(binding, project=project) if binding else None


def active_binding_for_series(series_id: str, db: Session) -> DBVideoProviderProjectBinding | None:
    return (
        db.query(DBVideoProviderProjectBinding)
        .filter(
            DBVideoProviderProjectBinding.series_id == series_id,
            DBVideoProviderProjectBinding.project_id.is_(None),
            DBVideoProviderProjectBinding.provider == PROVIDER,
            DBVideoProviderProjectBinding.provider_tool == PROVIDER_TOOL,
            DBVideoProviderProjectBinding.status.in_([ACTIVE_STATUS, NEEDS_CHECK_STATUS]),
        )
        .order_by(DBVideoProviderProjectBinding.updated_at.desc())
        .first()
    )

def binding_for_series_response(series: DBVideoSeries, db: Session) -> models.VideoProviderProjectBindingResponse | None:
    binding = active_binding_for_series(series.id, db)
    return binding_response(binding) if binding else None

def binding_response(
    binding: DBVideoProviderProjectBinding,
    *,
    project: DBVideoProject | None = None,
) -> models.VideoProviderProjectBindingResponse:
    scope = "series" if binding.series_id else "project"
    scope_id = binding.series_id or binding.project_id or ""
    series_id = binding.series_id or getattr(project, "series_id", None)
    return models.VideoProviderProjectBindingResponse(
        id=binding.id,
        scope=scope,
        scope_id=scope_id,
        project_id=binding.project_id,
        series_id=series_id,
        provider=binding.provider,
        provider_tool=binding.provider_tool,
        provider_project_ref_hash=binding.provider_project_ref_hash,
        status=binding.status,
        last_checked_at=binding.last_checked_at,
        last_success_at=binding.last_success_at,
        failure_reason=binding.failure_reason,
        observed_model_label=binding.observed_model_label,
        observed_model_cost_label=binding.observed_model_cost_label,
        model_selection_mode=FLOW_MODEL_SELECTION_MODE,
        allow_automatic_model_change=FLOW_ALLOW_AUTOMATIC_MODEL_CHANGE,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def upsert_binding_for_project(
    project: DBVideoProject,
    db: Session,
    *,
    provider_project_url: str,
    provider_project_ref_hash_value: str | None = None,
    observed_model_label: str | None = None,
    observed_model_cost_label: str | None = None,
) -> DBVideoProviderProjectBinding | None:
    safe_url = safe_provider_project_url(provider_project_url)
    if not safe_url:
        return None
    ref_hash = provider_project_ref_hash_value or provider_project_ref_hash(safe_url)
    timestamp = now()
    binding = active_binding_for_project(project, db)
    if binding and binding.provider_project_ref_hash != ref_hash:
        binding.failure_reason = "Flow trả URL khác binding hiện tại. Voicebox giữ binding cũ và yêu cầu kiểm tra trước khi rotate."
        binding.last_checked_at = timestamp
        binding.updated_at = timestamp
        db.commit()
        db.refresh(binding)
        return binding
    if binding is None:
        scope, scope_id = scope_for_project(project)
        binding = DBVideoProviderProjectBinding(
            project_id=scope_id if scope == "project" else None,
            series_id=scope_id if scope == "series" else None,
            provider=PROVIDER,
            provider_tool=PROVIDER_TOOL,
            provider_project_url=safe_url,
            provider_project_ref_hash=ref_hash,
            status=ACTIVE_STATUS,
            last_checked_at=timestamp,
            last_success_at=timestamp,
            observed_model_label=observed_model_label,
            observed_model_cost_label=observed_model_cost_label,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(binding)
    else:
        binding.provider_project_url = safe_url
        binding.provider_project_ref_hash = ref_hash
        binding.status = ACTIVE_STATUS
        binding.failure_reason = None
        binding.last_checked_at = timestamp
        binding.last_success_at = timestamp
        binding.updated_at = timestamp
        if observed_model_label:
            binding.observed_model_label = observed_model_label
        if observed_model_cost_label:
            binding.observed_model_cost_label = observed_model_cost_label
    db.commit()
    db.refresh(binding)
    return binding


def mark_binding_invalid(
    binding: DBVideoProviderProjectBinding,
    db: Session,
    *,
    reason: str,
    status: str = INVALID_STATUS,
) -> None:
    binding.status = status
    binding.failure_reason = reason
    binding.last_checked_at = now()
    binding.updated_at = binding.last_checked_at
    db.commit()


def mark_binding_needs_check(
    binding: DBVideoProviderProjectBinding,
    db: Session,
    *,
    reason: str,
) -> None:
    binding.status = NEEDS_CHECK_STATUS
    binding.failure_reason = reason
    binding.last_checked_at = now()
    binding.updated_at = binding.last_checked_at
    db.commit()


def update_model_observation(
    binding: DBVideoProviderProjectBinding | None,
    db: Session,
    *,
    observed_model_label: str | None,
    observed_model_cost_label: str | None,
) -> None:
    if binding is None:
        return
    changed = False
    if observed_model_label and binding.observed_model_label != observed_model_label:
        binding.observed_model_label = observed_model_label
        changed = True
    if observed_model_cost_label and binding.observed_model_cost_label != observed_model_cost_label:
        binding.observed_model_cost_label = observed_model_cost_label
        changed = True
    if changed:
        binding.updated_at = now()
        db.commit()


def get_project_binding(project_id: str, db: Session) -> models.VideoProviderProjectBindingResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    return binding_for_project_response(project, db)


def open_project_binding(project_id: str, db: Session) -> models.VideoProviderProjectBindingResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    binding = active_binding_for_project(project, db)
    if binding is None:
        return None
    session = video_provider_sessions.get_default_session(db, provider=PROVIDER, create=False)
    if session is None or session.status != "ready":
        raise VideoProviderProjectBindingError(
            "Phiên Veo/Chrome chưa sẵn sàng để mở Flow project. Hãy đăng nhập hoặc kiểm tra phiên trước.",
            error_code="VIDEO_PROVIDER_SESSION_NOT_READY",
        )
    runtime = video_provider_sessions.launch_chrome(
        provider=PROVIDER,
        url=binding.provider_project_url,
    )
    chrome_cdp.open_target(runtime.port, binding.provider_project_url)
    return binding_response(binding, project=project)
