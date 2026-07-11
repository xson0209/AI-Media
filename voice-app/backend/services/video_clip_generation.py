"""Orchestration for generating AI Video shot clips through Veo/Chrome."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import models
from ..database import (
    VideoAutoRun as DBVideoAutoRun,
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoProject as DBVideoProject,
    VideoProviderSession as DBVideoProviderSession,
    VideoRenderJob as DBVideoRenderJob,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    get_db,
)
from . import (
    video_observability,
    video_provider_sessions,
    video_provider_storage,
    video_rendering,
    video_storage,
    video_veo_chrome,
)
from .task_queue import create_background_task

ACTIVE_STATUSES = {"queued", "running", "needs_login", "needs_user_action", "needs_credit_approval"}
TERMINAL_STATUSES = {"completed", "completed_with_render_blocked", "failed", "cancelled"}
RENDER_BUSY_STATUSES = {"queued", "running"}
ITEM_ACTIVE_STATUSES = {
    "opening_provider",
    "submitting_prompt",
    "resolving_followup",
    "credit_policy_check",
    "approving_credit",
    "waiting_generation",
    "downloading",
    "importing",
}
ITEM_RETRYABLE_STATUSES = {"pending", "failed", "needs_login", "needs_user_action", "needs_credit_approval"}
MAX_ATTEMPTS = 2
PROVIDER_PROJECT_URL_RESULT_KEY = "provider_project_url"
PROVIDER_PROJECT_HASH_RESULT_KEY = "provider_project_ref_hash"
ITEM_STATUS_MESSAGES = {
    "opening_provider": "Đang mở Veo",
    "submitting_prompt": "Đang gửi prompt",
    "resolving_followup": "Đang xử lý câu hỏi duration",
    "credit_policy_check": "Đang kiểm tra chính sách credit",
    "approving_credit": "Đang phê duyệt credit",
    "waiting_generation": "Đang chờ Veo tạo clip",
    "downloading": "Đang tải clip",
    "importing": "Đang import clip",
}
PUBLIC_FIGURE_PROVIDER_REPLACEMENTS = (
    (re.compile(r"\b(?:lionel\s+)?messi\b", re.IGNORECASE), "an Argentina football supporter"),
    (re.compile(r"\bleo\s+messi\b", re.IGNORECASE), "an Argentina football supporter"),
    (re.compile(r"\bcristiano\s+ronaldo\b|\bronald[o0]\b|\bcr7\b", re.IGNORECASE), "a football supporter"),
    (re.compile(r"\bneymar(?:\s+jr\.?)?\b", re.IGNORECASE), "a football supporter"),
    (re.compile(r"\bmbapp[eé]\b|\bkylian\s+mbapp[eé]\b", re.IGNORECASE), "a football supporter"),
)
PUBLIC_FIGURE_CONTEXT_REPLACEMENTS = (
    (re.compile(r"\bpublic figures?\b", re.IGNORECASE), "named people"),
    (re.compile(r"\bcelebrit(?:y|ies)\b", re.IGNORECASE), "named people"),
    (re.compile(r"\breal[-\s]?football[-\s]?players?\b", re.IGNORECASE), "named athletes"),
    (re.compile(r"\breal[-\s]?players?\b", re.IGNORECASE), "named athletes"),
    (re.compile(r"\bplayer likeness(?:es)?\b", re.IGNORECASE), "portrait likenesses"),
    (re.compile(r"\bworld cup(?:\s+\d{4})?\b", re.IGNORECASE), "fictional tournament"),
    (re.compile(r"\b(?:shirt|jersey|scarf|banner|flag|sign|poster|label)\s+(?:number\s+)?10\b", re.IGNORECASE), "blue-and-white supporter gear"),
    (re.compile(r"\bnumber\s+10\b", re.IGNORECASE), "blue-and-white supporter gear"),
    (re.compile(r"\bnumber[-\s]?ten\b", re.IGNORECASE), "blue-and-white supporter"),
    (re.compile(r"\bgoat\b", re.IGNORECASE), "champion"),
    (re.compile(r"cầu thủ thật", re.IGNORECASE), "người có tên"),
    (re.compile(r"người nổi tiếng", re.IGNORECASE), "người có tên"),
)

class VideoClipGenerationError(ValueError):
    """Raised when a clip generation job cannot start or continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_CLIP_GENERATION_ERROR"):
        super().__init__(message)
        self.error_code = error_code

def _now() -> datetime:
    return datetime.utcnow()

def provider_safe_prompt_for_veo(prompt: str) -> tuple[str, bool]:
    """Remove public-figure cues before sending a project prompt to Veo/Flow."""
    safe = prompt
    for pattern, replacement in PUBLIC_FIGURE_PROVIDER_REPLACEMENTS:
        safe = pattern.sub(replacement, safe)
    for pattern, replacement in PUBLIC_FIGURE_CONTEXT_REPLACEMENTS:
        safe = pattern.sub(replacement, safe)
    changed = safe != prompt
    if changed:
        safe = (
            safe.strip()
            + "\n\nUse only fictional simple stick-figure or generic football supporters. "
            "No realistic faces, logos, jersey numbers, or real people."
        )
    return safe, changed

def _active_job(project_id: str, db: Session, *, provider: str = "veo") -> DBVideoClipGenerationJob | None:
    return (
        db.query(DBVideoClipGenerationJob)
        .filter(
            DBVideoClipGenerationJob.project_id == project_id,
            DBVideoClipGenerationJob.provider == provider,
            DBVideoClipGenerationJob.status.in_(ACTIVE_STATUSES),
        )
        .order_by(DBVideoClipGenerationJob.created_at.desc())
        .first()
    )

def has_active_job(project_id: str, db: Session) -> bool:
    return _active_job(project_id, db) is not None

def _ensure_project_can_start_clip_generation(
    project_id: str,
    db: Session,
    *,
    allow_active_auto_run_id: str | None = None,
) -> None:
    from . import video_auto_runs, video_planning_pool

    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is not None and project.series_id:
        active_series_job = (
            db.query(DBVideoClipGenerationJob.id)
            .join(DBVideoProject, DBVideoProject.id == DBVideoClipGenerationJob.project_id)
            .filter(
                DBVideoProject.series_id == project.series_id,
                DBVideoClipGenerationJob.project_id != project_id,
                DBVideoClipGenerationJob.provider == "veo",
                DBVideoClipGenerationJob.status.in_(ACTIVE_STATUSES),
            )
            .first()
        )
        if active_series_job is not None:
            raise VideoClipGenerationError(
                "Series đang có job Veo khác chạy cùng Flow project. Hãy chờ job đó hoàn tất trước khi tạo clip episode tiếp theo.",
                error_code="VIDEO_CLIP_SERIES_BUSY_VEO_JOB",
            )

    active_auto_run = (
        db.query(DBVideoAutoRun.id)
        .filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.status.in_(video_auto_runs.ACTIVE_STATUSES))
        .first()
    )
    if active_auto_run is not None and active_auto_run[0] != allow_active_auto_run_id:
        raise VideoClipGenerationError(
            "Dự án đang auto-run. Hãy hủy hoặc chờ auto-run hoàn tất trước khi tạo clip bằng Veo.",
            error_code="VIDEO_CLIP_PROJECT_BUSY_AUTO_RUN",
        )
    if video_planning_pool.active_project_info(project_id) is not None:
        raise VideoClipGenerationError(
            "Dự án đang chạy AI planning. Hãy chờ bước hiện tại hoàn tất trước khi tạo clip bằng Veo.",
            error_code="VIDEO_CLIP_PROJECT_BUSY_PLANNING",
        )
    active_render = (
        db.query(DBVideoRenderJob.id)
        .filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.status.in_(RENDER_BUSY_STATUSES))
        .first()
    )
    if active_render is not None:
        raise VideoClipGenerationError(
            "Dự án đang render MP4. Hãy chờ render hoàn tất trước khi tạo clip bằng Veo.",
            error_code="VIDEO_CLIP_PROJECT_BUSY_RENDER",
        )

def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )

def _latest_prompt(project_id: str, shot_id: str, db: Session) -> DBVideoShotPrompt | None:
    return (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.shot_id == shot_id)
        .order_by(DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
        .first()
    )

def _prompt_ready(shot: DBVideoShot, prompt: DBVideoShotPrompt | None) -> bool:
    return (
        prompt is not None
        and shot.prompt_status == "completed"
        and getattr(prompt, "quality_status", None) in {"passed", "completed"}
    )

def _active_provider_clip(project_id: str, shot_id: str, db: Session) -> DBVideoShotClip | None:
    clip = (
        db.query(DBVideoShotClip)
        .filter(
            DBVideoShotClip.project_id == project_id,
            DBVideoShotClip.shot_id == shot_id,
            DBVideoShotClip.is_active.is_(True),
            DBVideoShotClip.source == "provider",
            DBVideoShotClip.provider == "veo",
            DBVideoShotClip.status == "ready",
        )
        .order_by(DBVideoShotClip.created_at.desc())
        .first()
    )
    if clip is None:
        return None
    path = video_storage.resolve_artifact_storage_path(clip.file_path)
    return clip if path is not None and path.exists() and path.is_file() else None

def _results(row: DBVideoClipGenerationJob) -> dict[str, Any]:
    value = row.step_results_json if isinstance(row.step_results_json, dict) else {}
    value.setdefault("events", [])
    return value

def _save_results(row: DBVideoClipGenerationJob, value: dict[str, Any]) -> None:
    row.step_results_json = value
    flag_modified(row, "step_results_json")

def _safe_provider_project_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "labs.google" not in lowered or "/tools/flow/project/" not in lowered:
        return None
    return text

def _provider_project_url_from_results(row: DBVideoClipGenerationJob) -> str | None:
    return _safe_provider_project_url(_results(row).get(PROVIDER_PROJECT_URL_RESULT_KEY))

def _find_reusable_provider_project_url(project: DBVideoProject, db: Session) -> str | None:
    rows = (
        db.query(DBVideoClipGenerationJob)
        .filter(DBVideoClipGenerationJob.project_id == project.id, DBVideoClipGenerationJob.provider == "veo")
        .order_by(DBVideoClipGenerationJob.updated_at.desc(), DBVideoClipGenerationJob.created_at.desc())
        .limit(20)
        .all()
    )
    for row in rows:
        url = _provider_project_url_from_results(row)
        if url:
            return url
    return None

def _save_provider_project_url(
    job: DBVideoClipGenerationJob,
    db: Session,
    provider_project_url: str,
    provider_project_ref_hash: str | None,
) -> None:
    safe_url = _safe_provider_project_url(provider_project_url)
    if not safe_url:
        return
    results = _results(job)
    results[PROVIDER_PROJECT_URL_RESULT_KEY] = safe_url
    if provider_project_ref_hash:
        results[PROVIDER_PROJECT_HASH_RESULT_KEY] = provider_project_ref_hash
    _save_results(job, results)
    db.commit()

def _record_event(row: DBVideoClipGenerationJob, event: dict[str, Any]) -> None:
    results = _results(row)
    safe = dict(event)
    if "prompt" in safe:
        prompt = str(safe.pop("prompt") or "")
        safe["prompt_preview"] = f"{prompt[:120]}...[truncated]" if len(prompt) > 120 else prompt
    safe["at"] = _now().isoformat()
    results.setdefault("events", []).append(safe)
    results["events"] = results["events"][-80:]
    _save_results(row, results)

def _set_job(
    row: DBVideoClipGenerationJob,
    db: Session,
    *,
    status: str | None = None,
    current_step: str | None = None,
    progress: float | None = None,
    failure_reason: str | None = None,
    error_code: str | None = None,
    completed: bool = False,
) -> None:
    now = _now()
    if status is not None:
        row.status = status
    if current_step is not None:
        row.current_step = current_step
    if progress is not None:
        row.progress = progress
    if failure_reason is not None:
        row.failure_reason = failure_reason
    if error_code is not None:
        row.error_code = error_code
    row.started_at = row.started_at or now
    row.updated_at = now
    if completed:
        row.completed_at = now
    db.commit()

def _set_item(
    item: DBVideoClipGenerationItem,
    db: Session,
    *,
    status: str,
    failure_reason: str | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    now = _now()
    item.status = status
    item.updated_at = now
    if started:
        item.started_at = item.started_at or now
    if completed:
        item.completed_at = now
    if failure_reason is not None:
        item.failure_reason = failure_reason
    db.commit()

def _item_summary(items: list[DBVideoClipGenerationItem], readiness: models.VideoRenderReadinessResponse | None) -> models.VideoClipGenerationSummary:
    counts = {status: 0 for status in ["pending", "completed", "skipped", "failed", "needs_login", "needs_credit_approval"]}
    active = 0
    credit_spent = 0
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
        if item.status in ITEM_ACTIVE_STATUSES:
            active += 1
        credit_spent += int(item.credit_cost or 0)
    return models.VideoClipGenerationSummary(
        total_items=len(items),
        pending_items=counts["pending"],
        active_items=active,
        completed_items=counts["completed"],
        skipped_items=counts["skipped"],
        failed_items=counts["failed"],
        needs_login_items=counts["needs_login"],
        needs_credit_approval_items=counts["needs_credit_approval"],
        credit_spent_estimate=credit_spent,
        render_ready=bool(readiness and readiness.ready),
        render_missing_reasons=list(readiness.missing_reasons if readiness else []),
    )

def job_response(row: DBVideoClipGenerationJob, db: Session) -> models.VideoClipGenerationJobResponse:
    items = (
        db.query(DBVideoClipGenerationItem)
        .filter(DBVideoClipGenerationItem.job_id == row.id)
        .order_by(DBVideoClipGenerationItem.shot_order.asc(), DBVideoClipGenerationItem.created_at.asc())
        .all()
    )
    readiness = video_rendering.get_render_readiness(row.project_id, db)
    response = models.VideoClipGenerationJobResponse.model_validate(row)
    if row.status == "completed":
        response.failure_reason = None
        response.error_code = None
    response.items = [models.VideoClipGenerationItemResponse.model_validate(item) for item in items]
    if row.status == "completed":
        for item in response.items:
            if item.status == "completed":
                item.failure_reason = None
    response.summary = _item_summary(items, readiness)
    return response

def get_latest_job(project_id: str, db: Session) -> models.VideoClipGenerationJobResponse | None:
    row = (
        db.query(DBVideoClipGenerationJob)
        .filter(DBVideoClipGenerationJob.project_id == project_id)
        .order_by(DBVideoClipGenerationJob.created_at.desc())
        .first()
    )
    return job_response(row, db) if row else None

def get_job(project_id: str, job_id: str, db: Session) -> models.VideoClipGenerationJobResponse | None:
    row = (
        db.query(DBVideoClipGenerationJob)
        .filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.id == job_id)
        .first()
    )
    return job_response(row, db) if row else None

def _session_for_start(data: models.VideoClipGenerationJobStartRequest, db: Session) -> DBVideoProviderSession:
    if data.session_id:
        session = db.query(DBVideoProviderSession).filter(DBVideoProviderSession.id == data.session_id).first()
    else:
        session = video_provider_sessions.get_default_session(db, create=False)
    if session is None:
        raise VideoClipGenerationError(
            "Chưa cấu hình phiên Veo3/Chrome. Hãy bấm Đăng nhập Google kết nối Veo3 trước.",
            error_code="VIDEO_PROVIDER_SESSION_NOT_CONFIGURED",
        )
    if data.confirm_identity and session.status == "ready":
        video_provider_sessions.confirm_identity(session.id, db)
        db.refresh(session)
    if session.status != "ready":
        raise VideoClipGenerationError(
            "Phiên Veo3/Chrome chưa sẵn sàng. Hãy kiểm tra phiên hoặc đăng nhập lại.",
            error_code="VIDEO_PROVIDER_SESSION_NOT_READY",
        )
    if session.identity_status in video_provider_sessions.IDENTITY_BLOCKING_STATUSES:
        raise VideoClipGenerationError(
            "Cần đặt nhãn/xác nhận tài khoản Veo3 đang kết nối trước khi chạy tự động.",
            error_code="VIDEO_PROVIDER_IDENTITY_UNCONFIRMED",
        )
    return session

def _start_job_sync(
    project_id: str,
    data: models.VideoClipGenerationJobStartRequest,
    db: Session,
    *,
    schedule_background: bool,
    allow_active_auto_run_id: str | None = None,
) -> models.VideoClipGenerationJobResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoClipGenerationError("Chỉ project phase 2 mới tạo clip bằng Veo.", error_code="VIDEO_CLIP_PHASE_REQUIRED")
    _ensure_project_can_start_clip_generation(
        project_id,
        db,
        allow_active_auto_run_id=allow_active_auto_run_id,
    )
    active = _active_job(project_id, db)
    if active is not None:
        return job_response(active, db)
    session = _session_for_start(data, db)
    shots = _ordered_shots(project_id, db)
    if not shots:
        raise VideoClipGenerationError("Project chưa có shot để tạo clip.", error_code="VIDEO_CLIP_NO_SHOTS")

    prompts_by_shot = {shot.id: _latest_prompt(project_id, shot.id, db) for shot in shots}
    missing = [shot for shot in shots if not _prompt_ready(shot, prompts_by_shot.get(shot.id))]
    if missing:
        labels = ", ".join(f"Segment {shot.shot_order:02d}" for shot in missing[:8])
        raise VideoClipGenerationError(
            f"Thiếu prompt video đạt chất lượng cho: {labels}. Hãy tạo prompt video trước.",
            error_code="VIDEO_CLIP_PROMPT_MISSING",
        )

    now = _now()
    job_id = str(uuid.uuid4())
    download_dir = video_provider_storage.get_job_download_dir(project_id, job_id)
    step_results = {"events": [], "credit_approval_policy": data.credit_approval_policy}
    reusable_provider_project_url = _find_reusable_provider_project_url(project, db)
    if reusable_provider_project_url:
        step_results[PROVIDER_PROJECT_URL_RESULT_KEY] = reusable_provider_project_url
    job = DBVideoClipGenerationJob(
        id=job_id,
        project_id=project_id,
        provider="veo",
        session_id=session.id,
        status="queued",
        current_step="validate",
        progress=0.0,
        force=data.force,
        auto_render=data.auto_render,
        credit_approval_policy=data.credit_approval_policy,
        max_credit_per_job=data.max_credit_per_job,
        credit_spent_estimate=0,
        download_dir=video_provider_storage.to_storage_path(download_dir),
        step_results_json=step_results,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()
    for shot in shots:
        prompt = prompts_by_shot[shot.id]
        clip = _active_provider_clip(project_id, shot.id, db)
        status = "skipped" if clip is not None and not data.force else "pending"
        db.add(
            DBVideoClipGenerationItem(
                id=str(uuid.uuid4()),
                job_id=job.id,
                project_id=project_id,
                shot_id=shot.id,
                shot_order=shot.shot_order,
                prompt_id=prompt.id if prompt else None,
                status=status,
                attempt_count=0,
                clip_id=clip.id if clip is not None and not data.force else None,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    db.refresh(job)
    if schedule_background:
        create_background_task(_run_job(job.id))
    return job_response(job, db)

async def start_job(
    project_id: str,
    data: models.VideoClipGenerationJobStartRequest,
    db: Session,
) -> models.VideoClipGenerationJobResponse | None:
    return _start_job_sync(project_id, data, db, schedule_background=True)

def start_job_for_auto_run(
    project_id: str,
    data: models.VideoClipGenerationJobStartRequest,
    db: Session,
    *,
    auto_run_id: str,
) -> models.VideoClipGenerationJobResponse | None:
    return _start_job_sync(
        project_id,
        data,
        db,
        schedule_background=False,
        allow_active_auto_run_id=auto_run_id,
    )

async def retry_job(
    project_id: str,
    job_id: str,
    data: models.VideoClipGenerationRetryRequest,
    db: Session,
) -> models.VideoClipGenerationJobResponse | None:
    row = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.id == job_id).first()
    if row is None:
        return None
    _ensure_project_can_start_clip_generation(project_id, db)
    if row.status not in {"failed", "needs_login", "needs_user_action", "needs_credit_approval", "completed_with_render_blocked"}:
        raise VideoClipGenerationError("Job hiện không ở trạng thái có thể retry.", error_code="VIDEO_CLIP_JOB_INVALID_STATE")
    active = _active_job(project_id, db)
    if active is not None and active.id != row.id:
        raise VideoClipGenerationError("Project đang có job Veo khác còn active.", error_code="VIDEO_CLIP_ACTIVE_JOB_EXISTS")
    now = _now()
    row.status = "queued"
    row.current_step = "retry"
    row.force = bool(data.force or row.force)
    row.failure_reason = None
    row.error_code = None
    row.completed_at = None
    row.updated_at = now
    retryable_reset_statuses = {"failed", "needs_login", "needs_user_action", "needs_credit_approval", *ITEM_ACTIVE_STATUSES}
    for item in db.query(DBVideoClipGenerationItem).filter(DBVideoClipGenerationItem.job_id == row.id).all():
        if item.status in retryable_reset_statuses:
            item.status = "pending"
            item.failure_reason = None
            item.updated_at = now
    db.commit()
    create_background_task(_run_job(row.id))
    return job_response(row, db)

async def resume_job(
    project_id: str,
    job_id: str,
    data: models.VideoClipGenerationResumeRequest,
    db: Session,
) -> models.VideoClipGenerationJobResponse | None:
    row = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.id == job_id).first()
    if row is None:
        return None
    _ensure_project_can_start_clip_generation(project_id, db)
    if row.status not in {"needs_login", "needs_user_action", "needs_credit_approval", "failed"}:
        raise VideoClipGenerationError("Job hiện không cần resume.", error_code="VIDEO_CLIP_JOB_INVALID_STATE")
    session = db.query(DBVideoProviderSession).filter(DBVideoProviderSession.id == row.session_id).first()
    if session is None or session.status != "ready":
        raise VideoClipGenerationError("Phiên Veo chưa ready để resume.", error_code="VIDEO_PROVIDER_SESSION_NOT_READY")
    if data.confirm_identity:
        video_provider_sessions.confirm_identity(session.id, db)
        db.refresh(session)
    if session.identity_status in video_provider_sessions.IDENTITY_BLOCKING_STATUSES:
        raise VideoClipGenerationError("Cần xác nhận tài khoản Veo trước khi resume.", error_code="VIDEO_PROVIDER_IDENTITY_UNCONFIRMED")
    row.status = "queued"
    row.current_step = "resume"
    row.failure_reason = None
    row.error_code = None
    row.completed_at = None
    row.updated_at = _now()
    for item in db.query(DBVideoClipGenerationItem).filter(DBVideoClipGenerationItem.job_id == row.id).all():
        if item.status in {"failed", "needs_login", "needs_user_action", "needs_credit_approval", *ITEM_ACTIVE_STATUSES}:
            item.status = "pending"
            item.failure_reason = None
            item.updated_at = row.updated_at
    db.commit()
    create_background_task(_run_job(row.id))
    return job_response(row, db)

def cancel_job(project_id: str, job_id: str, db: Session) -> models.VideoClipGenerationJobResponse | None:
    row = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.id == job_id).first()
    if row is None:
        return None
    if row.status in TERMINAL_STATUSES:
        return job_response(row, db)
    now = _now()
    row.status = "cancelled"
    row.current_step = "cancelled"
    row.failure_reason = "Người dùng đã hủy job tạo clip Veo."
    row.completed_at = now
    row.updated_at = now
    db.query(DBVideoClipGenerationItem).filter(
        DBVideoClipGenerationItem.job_id == row.id,
        DBVideoClipGenerationItem.status.in_(["pending", *ITEM_ACTIVE_STATUSES]),
    ).update({"status": "cancelled", "failure_reason": row.failure_reason, "updated_at": now}, synchronize_session=False)
    db.commit()
    return job_response(row, db)

def approve_credit(
    project_id: str,
    job_id: str,
    item_id: str,
    data: models.VideoClipGenerationCreditApprovalRequest,
    db: Session,
) -> models.VideoClipGenerationJobResponse | None:
    row = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.id == job_id).first()
    if row is None:
        return None
    _ensure_project_can_start_clip_generation(project_id, db)
    item = db.query(DBVideoClipGenerationItem).filter(DBVideoClipGenerationItem.job_id == row.id, DBVideoClipGenerationItem.id == item_id).first()
    if item is None:
        raise VideoClipGenerationError("Không tìm thấy item credit cần phê duyệt.", error_code="VIDEO_CLIP_ITEM_NOT_FOUND")
    if not data.approve:
        item.status = "cancelled"
        item.failure_reason = "Người dùng từ chối phê duyệt credit."
        row.status = "failed"
        row.failure_reason = item.failure_reason
        row.error_code = "VIDEO_PROVIDER_CREDIT_REJECTED"
    else:
        item.status = "pending"
        item.failure_reason = None
        row.status = "queued"
        row.failure_reason = None
        row.error_code = None
    now = _now()
    item.updated_at = now
    row.updated_at = now
    db.commit()
    if data.approve:
        create_background_task(_run_job(row.id))
    return job_response(row, db)

async def _run_job(job_id: str) -> None:
    action = await asyncio.to_thread(_run_job_sync, job_id)
    await asyncio.to_thread(_resume_linked_auto_run_after_job_completion, job_id)
    if action.get("auto_render"):
        await _handoff_render(job_id)

def _resume_linked_auto_run_after_job_completion(job_id: str) -> None:
    db = next(get_db())
    try:
        from . import video_auto_runs

        video_auto_runs.resume_interrupted_auto_run_after_clip_job(job_id, db)
    finally:
        db.close()

async def _handoff_render(job_id: str) -> None:
    db = next(get_db())
    try:
        job = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.id == job_id).first()
        if job is None or job.status not in {"completed", "completed_with_render_blocked"}:
            return
        readiness = video_rendering.get_render_readiness(job.project_id, db)
        if readiness is None or not readiness.ready:
            job.status = "completed_with_render_blocked"
            job.current_step = "render_blocked"
            job.failure_reason = "; ".join(readiness.missing_reasons if readiness else []) or "Chưa đủ điều kiện render MP4."
            job.updated_at = _now()
            db.commit()
            return
        render = await video_rendering.create_render_job(job.project_id, models.VideoRenderJobCreateRequest(), db)
        if render is not None:
            job.render_job_id = render.id
            job.current_step = "auto_render_started"
            job.updated_at = _now()
            db.commit()
    finally:
        db.close()

def _run_job_sync(job_id: str) -> dict[str, Any]:
    db = next(get_db())
    try:
        job = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.id == job_id).first()
        if job is None or job.status in TERMINAL_STATUSES:
            return {"action": "stop"}
        items = (
            db.query(DBVideoClipGenerationItem)
            .filter(DBVideoClipGenerationItem.job_id == job.id)
            .order_by(DBVideoClipGenerationItem.shot_order.asc(), DBVideoClipGenerationItem.created_at.asc())
            .all()
        )
        runnable = [item for item in items if item.status in ITEM_RETRYABLE_STATUSES]
        total = len([item for item in items if item.status != "skipped"]) or 1
        if not runnable:
            job.failure_reason = None
            job.error_code = None
            _set_job(job, db, status="completed", current_step="completed", progress=1.0, completed=True)
            return {"auto_render": bool(job.auto_render)}
        _set_job(job, db, status="running", current_step="opening_provider", progress=0.05)
        for item in runnable:
            db.refresh(job)
            if job.status == "cancelled":
                return {"action": "cancelled"}
            if item.attempt_count >= MAX_ATTEMPTS:
                _set_item(item, db, status="failed", failure_reason="Item đã vượt số lần thử tối đa.", completed=True)
                continue
            prompt = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.id == item.prompt_id).first()
            shot = db.query(DBVideoShot).filter(DBVideoShot.id == item.shot_id).first()
            if prompt is None or shot is None:
                _set_item(item, db, status="failed", failure_reason="Không tìm thấy prompt hoặc shot của item.", completed=True)
                continue
            item.attempt_count = int(item.attempt_count or 0) + 1
            _set_item(item, db, status="opening_provider", started=True)
            _set_job(job, db, status="running", current_step=f"Đang mở Veo cho Segment {item.shot_order:02d}", progress=_progress(items, item))
            context = video_veo_chrome.make_download_context(
                project_id=job.project_id,
                job_id=job.id,
                item_id=item.id,
                shot_id=item.shot_id,
                shot_order=item.shot_order,
                prompt_id=item.prompt_id,
            )
            item.download_correlation_id = context.download_correlation_id
            item.downloaded_file_path = video_provider_storage.to_storage_path(context.expected_download_dir)
            db.commit()
            def update_item_status(status: str, message: str | None = None) -> None:
                if status not in ITEM_ACTIVE_STATUSES:
                    return
                label = message or ITEM_STATUS_MESSAGES.get(status, status)
                _set_item(item, db, status=status)
                _set_job(job, db, status="running", current_step=f"{label} - Segment {item.shot_order:02d}", progress=_progress(items, item))

            try:
                _set_item(item, db, status="submitting_prompt")
                _set_job(job, db, current_step=f"Đang gửi prompt Segment {item.shot_order:02d}")
                provider_project_url = _provider_project_url_from_results(job)
                provider_prompt, provider_prompt_sanitized = provider_safe_prompt_for_veo(prompt.prompt)
                def remember_provider_project(provider_project_url: str, provider_project_ref_hash: str | None = None) -> None:
                    _save_provider_project_url(job, db, provider_project_url, provider_project_ref_hash)

                result = video_veo_chrome.submit_prompt_and_download(
                    prompt=provider_prompt,
                    requested_duration_seconds=prompt.duration_seconds or shot.duration_seconds,
                    download_context=context,
                    credit_approval_policy=job.credit_approval_policy,
                    provider_project_url=provider_project_url,
                    max_credit_per_job=job.max_credit_per_job,
                    credit_spent_estimate=job.credit_spent_estimate,
                    on_status=update_item_status,
                    on_provider_project=remember_provider_project,
                )
                _set_item(item, db, status="importing")
                item.credit_cost = result.credit_cost
                item.provider_duration_seconds = result.provider_duration_seconds
                item.provider_asset_id = result.provider_asset_id
                item.provider_project_ref_hash = result.provider_project_ref_hash
                item.download_url_hash = result.download_url_hash
                item.original_filename = result.original_filename
                item.downloaded_file_path = video_provider_storage.to_storage_path(result.downloaded_file_path)
                job.credit_spent_estimate = int(job.credit_spent_estimate or 0) + int(result.credit_cost or 0)
                if result.provider_project_url:
                    _save_provider_project_url(job, db, result.provider_project_url, result.provider_project_ref_hash)
                clip = video_rendering.import_provider_clip(
                    job.project_id,
                    item.shot_id,
                    source_path=result.downloaded_file_path,
                    original_filename=result.original_filename,
                    provider="veo",
                    provider_asset_id=result.provider_asset_id,
                    provider_metadata={
                        **(result.metadata or {}),
                        "job_id": job.id,
                        "item_id": item.id,
                        "shot_order": item.shot_order,
                        "attempt_count": item.attempt_count,
                        "provider_prompt_sanitized": provider_prompt_sanitized,
                        "provider_project_ref_hash": result.provider_project_ref_hash,
                        "download_url_hash": result.download_url_hash,
                    },
                    db=db,
                )
                if clip is None:
                    raise VideoClipGenerationError("Không tìm thấy shot để import clip.", error_code="VIDEO_SHOT_NOT_FOUND")
                item.clip_id = clip.id
                if clip.status != "ready":
                    raise VideoClipGenerationError(clip.failure_reason or "Clip provider không hợp lệ.", error_code="VIDEO_RENDER_CLIP_INVALID")
                item.failure_reason = None
                _set_item(item, db, status="completed", completed=True)
                _record_event(job, {"step": "item_completed", "item_id": item.id, "shot_id": item.shot_id, "shot_order": item.shot_order})
            except video_veo_chrome.VeoChromeError as exc:
                _handle_provider_error(job, item, exc, db)
                return {"action": "provider_error"}
            except video_provider_sessions.VideoProviderSessionError as exc:
                _set_item(item, db, status="needs_login", failure_reason=str(exc))
                _set_job(job, db, status="needs_login", current_step="needs_login", failure_reason=str(exc), error_code=exc.error_code)
                return {"action": "provider_session_error"}
            except Exception as exc:
                _fail_item_and_job(job, item, str(exc), getattr(exc, "error_code", "VIDEO_CLIP_ITEM_FAILED"), db)
                return {"action": "failed"}
        db.refresh(job)
        remaining = db.query(DBVideoClipGenerationItem.id).filter(
            DBVideoClipGenerationItem.job_id == job.id,
            DBVideoClipGenerationItem.status.in_(["pending", *ITEM_ACTIVE_STATUSES, "failed", "needs_login", "needs_user_action", "needs_credit_approval"]),
        ).first()
        if remaining is None:
            job.failure_reason = None
            job.error_code = None
            _set_job(job, db, status="completed", current_step="completed", progress=1.0, completed=True)
            return {"auto_render": bool(job.auto_render)}
        _set_job(job, db, status="failed", current_step="failed", failure_reason="Một số item Veo chưa hoàn tất.", error_code="VIDEO_CLIP_ITEMS_INCOMPLETE", completed=True)
        return {"action": "incomplete"}
    finally:
        db.close()

def _progress(items: list[DBVideoClipGenerationItem], current: DBVideoClipGenerationItem) -> float:
    runnable = [item for item in items if item.status != "skipped"]
    if not runnable:
        return 1.0
    index = max(0, [item.id for item in runnable].index(current.id))
    return min(0.95, index / max(1, len(runnable)) + 0.05)

def _handle_provider_error(job: DBVideoClipGenerationJob, item: DBVideoClipGenerationItem, exc: video_veo_chrome.VeoChromeError, db: Session) -> None:
    if exc.error_code in {"VIDEO_PROVIDER_NEEDS_CREDIT_APPROVAL", "VIDEO_PROVIDER_CREDIT_LIMIT_EXCEEDED"}:
        item.credit_cost = exc.details.get("credit_cost") if isinstance(exc.details, dict) else item.credit_cost
        _set_item(item, db, status="needs_credit_approval", failure_reason=str(exc))
        _set_job(job, db, status="needs_credit_approval", current_step="needs_credit_approval", failure_reason=str(exc), error_code=exc.error_code)
        return
    if exc.error_code in {"VIDEO_PROVIDER_SESSION_NOT_READY", "VIDEO_PROVIDER_CHROME_MISSING", "VIDEO_PROVIDER_PROFILE_LOCKED"}:
        _set_item(item, db, status="needs_login", failure_reason=str(exc))
        _set_job(job, db, status="needs_login", current_step="needs_login", failure_reason=str(exc), error_code=exc.error_code)
        return
    _fail_item_and_job(job, item, str(exc), exc.error_code, db)

def _fail_item_and_job(
    job: DBVideoClipGenerationJob,
    item: DBVideoClipGenerationItem,
    reason: str,
    error_code: str,
    db: Session,
) -> None:
    _set_item(item, db, status="failed", failure_reason=reason, completed=True)
    _set_job(job, db, status="failed", current_step="failed", failure_reason=reason, error_code=error_code, completed=True)
    video_observability.log_event(
        db,
        step_name="veo_clip_generation",
        status="failure",
        project_id=job.project_id,
        shot_id=item.shot_id,
        provider="veo",
        error_code=error_code,
        message=reason,
        technical_details={"job_id": job.id, "item_id": item.id, "shot_order": item.shot_order},
    )

def sync_stale_running_jobs(db: Session) -> int:
    now = _now()
    result = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.status.in_(["queued", "running"])).update(
        {
            "status": "failed",
            "failure_reason": "Job tạo clip Veo bị gián đoạn khi ứng dụng đóng.",
            "error_code": "VIDEO_CLIP_GENERATION_INTERRUPTED",
            "completed_at": now,
            "updated_at": now,
        },
        synchronize_session=False,
    )
    if result:
        db.commit()
    return int(result or 0)
