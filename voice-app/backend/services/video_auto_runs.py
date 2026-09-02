"""Auto-run orchestration for AI Video material generation."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import models
from ..database import (
    VideoAutoRun as DBVideoAutoRun,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoPackageExport as DBVideoPackageExport,
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
    VideoSubtitle as DBVideoSubtitle,
    get_db,
)
from . import (
    ai_planning,
    settings as settings_service,
    video_clip_generation,
    video_observability,
    video_phase2,
    video_planning_pool,
    video_publishing_metadata,
    video_rendering,
    video_series_characters,
    video_speech,
    video_storage,
    video_subtitles,
    video_voice,
    video_workflow_pool,
)
from .task_queue import create_background_task

ACTIVE_STATUSES = {
    "queued",
    "waiting_workflow",
    "running",
    "waiting_planning",
    "waiting_voice",
    "waiting_clips",
    "waiting_render",
    "needs_review",
    "needs_input",
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
MATERIAL_TARGET_FULL = "full_materials"
MATERIAL_TARGET_PROMPTS_ONLY = "prompts_only"
MATERIAL_TARGET_PUBLISHING_KIT = "publishing_kit"
MATERIAL_TARGET_VIDEO_CLIPS = "video_clips"
MATERIAL_TARGETS = {MATERIAL_TARGET_FULL, MATERIAL_TARGET_PROMPTS_ONLY, MATERIAL_TARGET_PUBLISHING_KIT, MATERIAL_TARGET_VIDEO_CLIPS}
VOICE_BUSY_STATUSES = {"queued", "generating", "loading_model"}
VOICE_RETRYABLE_STATUSES = {"missing", "stale", "failed", "cancelled"}
VOICE_ENQUEUE_BATCH_SIZE = 2
INTERRUPTED_VOICE_FAILURE_MARKERS = (
    "server was shut down during generation",
)
POLL_SECONDS = 2.0
MAX_WAIT_SECONDS = 2 * 60 * 60

STEP_ORDER = [
    "validate",
    "develop_story",
    "waiting_planning",
    "review_character_proposals",
    "review_story",
    "generate_shots",
    "generate_prompts",
    "generate_publishing_metadata",
    "review_prompts",
    "generate_clips",
    "waiting_clips",
    "generate_voice",
    "waiting_voice",
    "generate_subtitle",
    "generate_render",
    "waiting_render",
    "completed",
]
STEP_PROGRESS = {
    "validate": 0.05,
    "develop_story": 0.18,
    "waiting_planning": 0.18,
    "review_character_proposals": 0.24,
    "review_story": 0.28,
    "generate_shots": 0.40,
    "generate_prompts": 0.53,
    "generate_publishing_metadata": 0.59,
    "review_prompts": 0.64,
    "generate_clips": 0.66,
    "waiting_clips": 0.74,
    "generate_voice": 0.80,
    "waiting_voice": 0.86,
    "generate_subtitle": 0.92,
    "generate_render": 0.96,
    "waiting_render": 0.98,
    "completed": 1.0,
}
TRANSIENT_STEPS = {"waiting_planning"}
FULL_MATERIALS_SKIPPED_STEPS = {"generate_clips", "waiting_clips", "generate_render", "waiting_render"}
PROMPTS_ONLY_SKIPPED_STEPS = {"generate_publishing_metadata", "generate_clips", "waiting_clips", "generate_voice", "waiting_voice", "generate_subtitle", "generate_render", "waiting_render"}
PUBLISHING_KIT_SKIPPED_STEPS = {"generate_clips", "waiting_clips", "generate_voice", "waiting_voice", "generate_subtitle", "generate_render", "waiting_render"}
VIDEO_CLIPS_SKIPPED_STEPS: set[str] = set()

class VideoAutoRunError(ValueError):
    """Raised when an auto-run cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_AUTO_RUN_ERROR"):
        super().__init__(message)
        self.error_code = error_code

class VideoAutoRunNeedsInputError(VideoAutoRunError):
    """Raised when user input is required before auto-run can continue."""

def _results(row: DBVideoAutoRun) -> dict[str, Any]:
    value = row.step_results_json if isinstance(row.step_results_json, dict) else {}
    value.setdefault("reviewed", {})
    value.setdefault("completed_steps", [])
    value.setdefault("events", [])
    return value

def _save_results(row: DBVideoAutoRun, results: dict[str, Any]) -> None:
    row.step_results_json = results
    flag_modified(row, "step_results_json")

def _material_target(row: DBVideoAutoRun) -> str:
    target = _results(row).get("material_target")
    return target if target in MATERIAL_TARGETS else MATERIAL_TARGET_FULL

def _step_order(row: DBVideoAutoRun) -> list[str]:
    if _material_target(row) == MATERIAL_TARGET_PROMPTS_ONLY:
        return [step for step in STEP_ORDER if step not in PROMPTS_ONLY_SKIPPED_STEPS]
    if _material_target(row) == MATERIAL_TARGET_PUBLISHING_KIT:
        return [step for step in STEP_ORDER if step not in PUBLISHING_KIT_SKIPPED_STEPS]
    if _material_target(row) == MATERIAL_TARGET_VIDEO_CLIPS:
        return [step for step in STEP_ORDER if step not in VIDEO_CLIPS_SKIPPED_STEPS]
    return [step for step in STEP_ORDER if step not in FULL_MATERIALS_SKIPPED_STEPS]

def _mark_completed(row: DBVideoAutoRun, step: str, **details: Any) -> None:
    results = _results(row)
    completed = list(dict.fromkeys([*results.get("completed_steps", []), step]))
    results["completed_steps"] = completed
    if details:
        results.setdefault("step_details", {})[step] = _redacted_details(details)
    _save_results(row, results)

def _step_completed(row: DBVideoAutoRun, step: str) -> bool:
    return step in set(_results(row).get("completed_steps", []))

def _force_pending(row: DBVideoAutoRun, step: str) -> bool:
    return bool(row.force) and not _step_completed(row, step)

def _mark_reviewed(row: DBVideoAutoRun, stage: str, *, auto_approved: bool = False) -> None:
    results = _results(row)
    if results["reviewed"].get(stage):
        _save_results(row, results)
        return
    results["reviewed"][stage] = True
    results.setdefault("review_events", []).append(
        {"stage": stage, "auto_approved": auto_approved, "reviewed_at": datetime.utcnow().isoformat()}
    )
    _save_results(row, results)

def _record_voice_failures(row: DBVideoAutoRun, shots: list[DBVideoShot]) -> None:
    results = _results(row)
    results["voice_failed_shots"] = [
        {
            "shot_id": shot.id,
            "shot_order": shot.shot_order,
            "voice_status": shot.voice_status,
            "failure_reason": _redacted_text(shot.voice_failure_reason),
        }
        for shot in shots
    ]
    _save_results(row, results)

def _clear_voice_failures(row: DBVideoAutoRun) -> None:
    results = _results(row)
    if "voice_failed_shots" not in results:
        return
    results.pop("voice_failed_shots", None)
    _save_results(row, results)

def _is_interrupted_voice_failure(shot: DBVideoShot) -> bool:
    if shot.voice_status != "failed":
        return False
    reason = (shot.voice_failure_reason or "").casefold()
    return any(marker in reason for marker in INTERRUPTED_VOICE_FAILURE_MARKERS)

def _redacted_details(details: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in details.items():
        if isinstance(value, str) and len(value) > 160:
            safe[key] = f"{value[:160]}...[truncated]"
        else:
            safe[key] = value
    return safe

def _redacted_text(value: str | None, max_length: int = 160) -> str | None:
    if value is None:
        return None
    return f"{value[:max_length]}...[truncated]" if len(value) > max_length else value

def _set_step(row: DBVideoAutoRun, db: Session, step: str, *, status: str = "running", review_stage: str | None = None) -> None:
    now = datetime.utcnow()
    previous_step = row.current_step
    row.status = status
    row.current_step = step
    row.review_stage = review_stage
    if status != "waiting_planning":
        row.progress = STEP_PROGRESS.get(step, row.progress or 0.0)
    row.started_at = row.started_at or now
    row.updated_at = now
    db.commit()
    if previous_step != step or status in {"needs_review", "needs_input", "failed", "completed", "cancelled"}:
        _log(row, db, step_name=f"auto_run_{step}", status=status, message=_status_message(step, status), details={"review_stage": review_stage})

def _auto_run_planning_callbacks(row: DBVideoAutoRun, db: Session, step: str):
    def on_wait(event: video_planning_pool.PlanningPoolEvent) -> None:
        results = _results(row)
        results["waiting_planning"] = _redacted_details(
            {
                "step": step,
                "wait_started_at": datetime.utcnow().isoformat(),
                "max_concurrency": event.max_concurrency,
                "active_count": event.active_count,
                "waiting_count": event.waiting_count,
            }
        )
        _save_results(row, results)
        _set_step(row, db, "waiting_planning", status="waiting_planning")

    def on_acquired(event: video_planning_pool.PlanningPoolEvent) -> None:
        results = _results(row)
        waiting = dict(results.pop("waiting_planning", {}) or {})
        if waiting:
            waiting.update(
                {
                    "step": step,
                    "wait_ms": event.wait_ms,
                    "max_concurrency": event.max_concurrency,
                    "active_count": event.active_count,
                    "waiting_count": event.waiting_count,
                    "slot_acquired_at": datetime.utcnow().isoformat(),
                }
            )
            results["last_planning_wait"] = _redacted_details(waiting)
        _save_results(row, results)
        _set_step(row, db, step, status="running")

    return video_planning_pool.planning_wait_callbacks(on_wait=on_wait, on_acquired=on_acquired)

def _wait_for_project_planning(row: DBVideoAutoRun, db: Session, step: str) -> dict[str, Any] | None:
    active_info = video_planning_pool.active_project_info(row.project_id)
    if active_info is None:
        return None
    results = _results(row)
    results["waiting_planning"] = _redacted_details(
        {
            "step": step,
            "wait_started_at": datetime.utcnow().isoformat(),
            "active_project_step": active_info.get("step_name"),
            "active_project_state": active_info.get("state"),
        }
    )
    _save_results(row, results)
    _set_step(row, db, "waiting_planning", status="waiting_planning")
    return {"action": "wait_planning"}

def _status_message(step: str, status: str) -> str:
    if status == "waiting_planning":
        return "Auto-run đang chờ slot Codex planning."
    if status == "waiting_clips":
        return "Auto-run đang chờ Veo tạo và tải clip về project."
    if status == "waiting_render":
        return "Auto-run đang chờ render MP4 hoàn tất."
    if status == "needs_review":
        return "Auto-run đang chờ người dùng duyệt."
    if status == "needs_input":
        return "Auto-run cần bổ sung thông tin trước khi tiếp tục."
    if status == "completed":
        return "Auto-run đã hoàn tất nguyên liệu video."
    if status == "failed":
        return "Auto-run thất bại."
    return f"Auto-run đang xử lý bước {step}."

def _log(
    row: DBVideoAutoRun,
    db: Session,
    *,
    step_name: str,
    status: str,
    message: str,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    safe_details = {"auto_run_id": row.id, **(details or {})}
    duration_ms = None
    if row.started_at is not None:
        duration_ms = round((datetime.utcnow() - row.started_at).total_seconds() * 1000, 2)
    video_observability.log_event(
        db,
        step_name=step_name,
        status="failure" if status == "failed" else status,
        project_id=row.project_id,
        duration_ms=duration_ms,
        error_code=error_code,
        message=message,
        technical_details=safe_details,
    )

def _active_run(project_id: str, db: Session) -> DBVideoAutoRun | None:
    return (
        db.query(DBVideoAutoRun)
        .filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.status.in_(ACTIVE_STATUSES))
        .order_by(DBVideoAutoRun.created_at.desc())
        .first()
    )

def start_auto_run_record(
    project_id: str,
    data: models.VideoAutoRunStartRequest,
    db: Session,
) -> models.VideoAutoRunResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    active = _active_run(project_id, db)
    if active is not None:
        return auto_run_response(active, db)
    now = datetime.utcnow()
    row = DBVideoAutoRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        mode=data.mode,
        status="queued",
        current_step="validate",
        progress=0.0,
        create_package=False,
        force=data.force,
        step_results_json={
            "reviewed": {},
            "completed_steps": [],
            "events": [],
            "material_target": data.material_target,
        },
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    create_background_task(_run_auto_run(row.id))
    return auto_run_response(row, db)

async def start_auto_run(
    project_id: str,
    data: models.VideoAutoRunStartRequest,
    db: Session,
) -> models.VideoAutoRunResponse | None:
    return start_auto_run_record(project_id, data, db)

def get_latest_auto_run(project_id: str, db: Session) -> models.VideoAutoRunResponse | None:
    row = (
        db.query(DBVideoAutoRun)
        .filter(DBVideoAutoRun.project_id == project_id)
        .order_by(DBVideoAutoRun.created_at.desc())
        .first()
    )
    return auto_run_response(row, db) if row else None

def get_auto_run(project_id: str, run_id: str, db: Session) -> models.VideoAutoRunResponse | None:
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.id == run_id).first()
    return auto_run_response(row, db) if row else None

async def continue_auto_run(
    project_id: str,
    run_id: str,
    data: models.VideoAutoRunContinueRequest,
    db: Session,
) -> models.VideoAutoRunResponse | None:
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.id == run_id).first()
    if row is None:
        return None
    if row.status not in {"needs_review", "needs_input"}:
        raise VideoAutoRunError("Auto-run hiện không ở trạng thái cần tiếp tục.", error_code="VIDEO_AUTO_RUN_INVALID_STATE")
    results = _results(row)
    if row.status == "needs_review" and row.review_stage:
        if row.review_stage == video_series_characters.REVIEW_STAGE:
            if not data.approved:
                results["reviewed"][row.review_stage] = False
                results.setdefault("review_events", []).append(
                    {"stage": row.review_stage, "approved": False, "reviewed_at": datetime.utcnow().isoformat()}
                )
                row.status = "cancelled"
                row.completed_at = datetime.utcnow()
                row.failure_reason = "Người dùng hủy auto-run tại bước duyệt nhân vật mới."
                _save_results(row, results)
                db.commit()
                return auto_run_response(row, db)
            project = _require_project(row, db)
            pending = video_series_characters.pending_required_proposals(project)
            if pending:
                raise VideoAutoRunError(
                    f"Còn {len(pending)} nhân vật mới cần quyết định trước khi chạy tiếp.",
                    error_code="AI_VIDEO_CHARACTER_PROPOSALS_PENDING",
                )
            results["reviewed"][row.review_stage] = True
            results.setdefault("review_events", []).append(
                {"stage": row.review_stage, "approved": True, "reviewed_at": datetime.utcnow().isoformat()}
            )
            flow = video_series_characters.project_character_flow(project)
            row.current_step = str(flow.get("resume_step") or "review_story")
            row.status = "waiting_workflow"
            row.review_stage = None
            row.failure_reason = None
            row.error_code = None
            row.updated_at = datetime.utcnow()
            _save_results(row, results)
            db.commit()
            create_background_task(_run_auto_run(row.id))
            return auto_run_response(row, db)
        results["reviewed"][row.review_stage] = bool(data.approved)
        results.setdefault("review_events", []).append(
            {"stage": row.review_stage, "approved": bool(data.approved), "reviewed_at": datetime.utcnow().isoformat()}
        )
        if not data.approved:
            row.status = "cancelled"
            row.completed_at = datetime.utcnow()
            row.failure_reason = "Người dùng không duyệt bước auto-run hiện tại."
            _save_results(row, results)
            db.commit()
            return auto_run_response(row, db)
        if row.review_stage == "story":
            row.current_step = "generate_shots"
        target = _material_target(row)
        if target in {MATERIAL_TARGET_PROMPTS_ONLY, MATERIAL_TARGET_PUBLISHING_KIT}:
            row.current_step = "completed"
        elif target == MATERIAL_TARGET_VIDEO_CLIPS:
            row.current_step = "generate_clips"
        else:
            row.current_step = "generate_voice"
    row.status = "waiting_workflow"
    row.review_stage = None
    row.failure_reason = None
    row.error_code = None
    row.updated_at = datetime.utcnow()
    results.pop("voice_failed_shots", None)
    _save_results(row, results)
    db.commit()
    create_background_task(_run_auto_run(row.id))
    return auto_run_response(row, db)

async def retry_auto_run(
    project_id: str,
    run_id: str,
    data: models.VideoAutoRunRetryRequest,
    db: Session,
) -> models.VideoAutoRunResponse | None:
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.id == run_id).first()
    if row is None:
        return None
    if row.status not in {"failed", "needs_input"}:
        raise VideoAutoRunError("Chỉ retry auto-run đang lỗi hoặc cần bổ sung thông tin.", error_code="VIDEO_AUTO_RUN_INVALID_STATE")
    active = _active_run(project_id, db)
    if active is not None and active.id != row.id:
        raise VideoAutoRunError("Project đang có auto-run khác còn active.", error_code="VIDEO_AUTO_RUN_ACTIVE_EXISTS")
    row.status = "waiting_workflow"
    row.force = bool(data.force)
    row.create_package = False
    row.review_stage = None
    row.failure_reason = None
    row.error_code = None
    row.updated_at = datetime.utcnow()
    _clear_voice_failures(row)
    db.commit()
    create_background_task(_run_auto_run(row.id))
    return auto_run_response(row, db)

def cancel_auto_run(project_id: str, run_id: str, db: Session) -> models.VideoAutoRunResponse | None:
    row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.project_id == project_id, DBVideoAutoRun.id == run_id).first()
    if row is None:
        return None
    if row.status in TERMINAL_STATUSES:
        return auto_run_response(row, db)
    now = datetime.utcnow()
    row.status = "cancelled"
    row.failure_reason = "Người dùng đã hủy auto-run."
    row.completed_at = now
    row.updated_at = now
    db.commit()
    video_workflow_pool.cancel_waiting(f"ai-video:{project_id}")
    try:
        video_voice.cancel_project_voice_generations(project_id, db)
    except Exception:
        # The auto-run itself is already cancelled. Voice cleanup is
        # best-effort so a secondary database/worker race cannot undo it.
        pass
    _log(row, db, step_name="auto_run_cancelled", status="cancelled", message="Người dùng đã hủy auto-run.")
    return auto_run_response(row, db)

def sync_stale_running_runs(db: Session) -> int:
    """Mark interrupted in-flight runs after a process restart.

    Queued runs are intentionally excluded here.  A queued run has not started
    any work yet and can be safely handed back to the dispatcher below.  The
    previous implementation marked queued rows as failed, leaving no task to
    execute them after a restart.
    """
    now = datetime.utcnow()
    result = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.status.in_(["waiting_workflow", "running", "waiting_planning", "waiting_voice", "waiting_clips", "waiting_render"])).update(
        {
            "status": "failed",
            "failure_reason": "Auto-run bị gián đoạn khi ứng dụng đóng.",
            "error_code": "VIDEO_AUTO_RUN_INTERRUPTED",
            "completed_at": now,
            "updated_at": now,
        },
        synchronize_session=False,
    )
    if result:
        db.commit()
    return int(result or 0)


def resume_queued_auto_runs(db: Session) -> int:
    """Re-dispatch queued runs left behind by a backend restart.

    The workflow pool is in-memory, so queued rows outlive their original
    background task.  Recreating the task from the durable row makes startup
    recovery idempotent; ``_workflow_acquired`` re-checks the row before any
    step is executed and terminal rows are ignored.
    """
    rows = (
        db.query(DBVideoAutoRun)
        .filter(DBVideoAutoRun.status.in_(["queued", "waiting_workflow"]))
        .order_by(DBVideoAutoRun.created_at.asc())
        .all()
    )
    for row in rows:
        create_background_task(_run_auto_run(row.id))
    return len(rows)

def resume_interrupted_auto_run_after_clip_job(job_id: str, db: Session) -> str | None:
    job = db.query(DBVideoClipGenerationJob).filter(DBVideoClipGenerationJob.id == job_id).first()
    if job is None or job.status != "completed":
        return None
    candidates = (
        db.query(DBVideoAutoRun)
        .filter(
            DBVideoAutoRun.project_id == job.project_id,
            DBVideoAutoRun.status == "failed",
            DBVideoAutoRun.current_step == "waiting_clips",
            DBVideoAutoRun.error_code == "VIDEO_AUTO_RUN_INTERRUPTED",
        )
        .order_by(DBVideoAutoRun.updated_at.desc(), DBVideoAutoRun.created_at.desc())
        .all()
    )
    for row in candidates:
        if _results(row).get("clip_generation_job_id") != job.id:
            continue
        if not _all_provider_clips_ready(row.project_id, db):
            return None
        row.status = "running"
        row.failure_reason = None
        row.error_code = None
        row.completed_at = None
        row.updated_at = datetime.utcnow()
        _remember_clip_job(row, job)
        db.commit()
        _log(
            row,
            db,
            step_name="auto_run_resume_after_clip_job",
            status="running",
            message="Auto-run tiếp tục sau khi job Veo đã tải clip về project.",
            details={"clip_generation_job_id": job.id},
        )
        create_background_task(_run_auto_run(row.id))
        return row.id
    return None

def _workflow_context(run_id: str) -> tuple[str, str] | None:
    db = next(get_db())
    try:
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
        if row is None or row.status in TERMINAL_STATUSES or row.status in {"needs_review", "needs_input"}:
            return None
        return row.project_id, row.current_step or "validate"
    finally:
        db.close()


def _workflow_acquired(run_id: str) -> bool:
    db = next(get_db())
    try:
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
        if row is None or row.status in TERMINAL_STATUSES or row.status in {"needs_review", "needs_input"}:
            return False
        if row.status == "waiting_workflow":
            row.status = "running"
            row.updated_at = datetime.utcnow()
            db.commit()
        return True
    finally:
        db.close()


async def _run_auto_run(run_id: str) -> None:
    context = await asyncio.to_thread(_workflow_context, run_id)
    if context is None:
        return
    project_id, operation_name = context
    try:
        async with video_workflow_pool.workflow_slot(
            work_key=f"ai-video:{project_id}",
            workflow_type="ai_video",
            operation_name=operation_name,
        ):
            if not await asyncio.to_thread(_workflow_acquired, run_id):
                return
            await _run_auto_run_in_slot(run_id)
    except video_workflow_pool.WorkflowAlreadyActiveError:
        # A near-simultaneous request may create a duplicate fire-and-forget
        # task. The original task remains the single owner for this project.
        return
    except asyncio.CancelledError:
        # The cancel endpoint has already persisted the terminal state.
        return


async def _run_auto_run_in_slot(run_id: str) -> None:
    started = time.monotonic()
    while True:
        action = await asyncio.to_thread(_advance_auto_run_sync, run_id)
        kind = action.get("action")
        if kind == "enqueue_voice":
            await _enqueue_voice(run_id, action.get("shot_ids", []))
            await asyncio.sleep(0.1)
            continue
        if kind == "wait_planning":
            if time.monotonic() - started > MAX_WAIT_SECONDS:
                await asyncio.to_thread(_fail_run_by_id, run_id, "Chờ AI planning quá lâu.", "VIDEO_AUTO_RUN_PLANNING_TIMEOUT")
                return
            await asyncio.sleep(POLL_SECONDS)
            continue
        if kind == "wait_voice":
            if time.monotonic() - started > MAX_WAIT_SECONDS:
                await asyncio.to_thread(_fail_run_by_id, run_id, "Chờ tạo voice quá lâu.", "VIDEO_AUTO_RUN_VOICE_TIMEOUT")
                return
            await asyncio.sleep(POLL_SECONDS)
            continue
        if kind == "run_clip_job":
            await video_clip_generation._run_job(action["job_id"])
            continue
        if kind == "wait_clips":
            if time.monotonic() - started > MAX_WAIT_SECONDS:
                await asyncio.to_thread(_fail_run_by_id, run_id, "Chờ Veo tạo và tải clip quá lâu.", "VIDEO_AUTO_RUN_CLIP_TIMEOUT")
                return
            await asyncio.sleep(POLL_SECONDS)
            continue
        if kind == "run_render_job":
            await video_rendering._run_render_job(action["job_id"])
            continue
        if kind == "wait_render":
            if time.monotonic() - started > MAX_WAIT_SECONDS:
                await asyncio.to_thread(_fail_run_by_id, run_id, "Chờ render MP4 quá lâu.", "VIDEO_AUTO_RUN_RENDER_TIMEOUT")
                return
            await asyncio.sleep(POLL_SECONDS)
            continue
        return

def _advance_auto_run_sync(run_id: str) -> dict[str, Any]:
    db = next(get_db())
    try:
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
        if row is None or row.status in TERMINAL_STATUSES or row.status in {"needs_review", "needs_input"}:
            return {"action": "stop"}
        try:
            return _advance_steps(row, db)
        except VideoAutoRunNeedsInputError as exc:
            _needs_input(row, db, str(exc), exc.error_code)
            return {"action": "stop"}
        except Exception as exc:
            # Phase 2 may have staged deletes/inserts before a serialization or
            # provider error. Never commit those partial changes together with
            # the auto-run failure state.
            db.rollback()
            row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
            if row is None:
                return {"action": "stop"}
            _fail_run(row, db, exc)
            return {"action": "stop"}
    finally:
        db.close()

def _advance_steps(row: DBVideoAutoRun, db: Session) -> dict[str, Any]:
    if row.create_package:
        row.create_package = False
        db.commit()
    if row.status == "queued":
        _set_step(row, db, "validate")
    project = _require_project(row, db)
    _validate_project_inputs(project, db)
    _mark_completed(row, "validate")

    if _needs_story(project, row):
        _ensure_planning_ready(db)
        wait_action = _wait_for_project_planning(row, db, "develop_story")
        if wait_action is not None:
            return wait_action
        _set_step(row, db, "develop_story")
        with _auto_run_planning_callbacks(row, db, "develop_story"):
            video_phase2.develop_story(project.id, db, force=bool(row.force))
        db.refresh(project)
        _mark_completed(row, "develop_story")

    if video_series_characters.has_pending_required_proposals(project):
        flow = video_series_characters.project_character_flow(project)
        results = _results(row)
        results["character_flow"] = {
            "pending_required_count": len(video_series_characters.pending_required_proposals(project)),
            "resume_step": flow.get("resume_step") or video_series_characters.DEFAULT_RESUME_STEP,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save_results(row, results)
        _set_step(
            row,
            db,
            video_series_characters.REVIEW_STEP,
            status="needs_review",
            review_stage=video_series_characters.REVIEW_STAGE,
        )
        return {"action": "stop"}

    if row.mode == "review_gated" and not _reviewed(row, "story"):
        _set_step(row, db, "review_story", status="needs_review", review_stage="story")
        return {"action": "stop"}
    if row.mode == "full_auto":
        _mark_reviewed(row, "story", auto_approved=True)
    if not project.story_approved:
        video_phase2.approve_story(project.id, True, db)
        db.refresh(project)
    _mark_completed(row, "review_story")

    if _needs_shots(project.id, db, row):
        _ensure_planning_ready(db)
        wait_action = _wait_for_project_planning(row, db, "generate_shots")
        if wait_action is not None:
            return wait_action
        _set_step(row, db, "generate_shots")
        with _auto_run_planning_callbacks(row, db, "generate_shots"):
            video_phase2.generate_shots(project.id, db)
        _mark_completed(row, "generate_shots")

    if _needs_prompts(project.id, db, row):
        _ensure_planning_ready(db)
        wait_action = _wait_for_project_planning(row, db, "generate_prompts")
        if wait_action is not None:
            return wait_action
        _set_step(row, db, "generate_prompts")
        with _auto_run_planning_callbacks(row, db, "generate_prompts"):
            video_phase2.generate_video_prompt_pack(project.id, db)
        _mark_completed(row, "generate_prompts")

    if _metadata_required(row):
        if _needs_publishing_metadata(project.id, db, row):
            _ensure_planning_ready(db)
            wait_action = _wait_for_project_planning(row, db, "generate_publishing_metadata")
            if wait_action is not None:
                return wait_action
            _set_step(row, db, "generate_publishing_metadata")
            with _auto_run_planning_callbacks(row, db, "generate_publishing_metadata"):
                video_publishing_metadata.generate_publishing_metadata(
                    project.id,
                    models.VideoPublishingMetadataGenerateRequest(platform="all", force=bool(row.force)),
                    db,
                )
            metadata_summary = video_publishing_metadata.metadata_status_summary(project.id, db)
            _mark_completed(
                row,
                "generate_publishing_metadata",
                status=metadata_summary.get("status"),
                revision=metadata_summary.get("revision"),
                platforms_ready=metadata_summary.get("platforms_ready"),
            )
        elif not _step_completed(row, "generate_publishing_metadata"):
            metadata_summary = video_publishing_metadata.metadata_status_summary(project.id, db)
            _mark_completed(
                row,
                "generate_publishing_metadata",
                skipped=True,
                status=metadata_summary.get("status"),
                revision=metadata_summary.get("revision"),
                platforms_ready=metadata_summary.get("platforms_ready"),
            )

    if row.mode == "review_gated" and not _reviewed(row, "prompts"):
        _set_step(row, db, "review_prompts", status="needs_review", review_stage="prompts")
        return {"action": "stop"}
    if row.mode == "full_auto":
        _mark_reviewed(row, "prompts", auto_approved=True)
    _approve_prompt_review(project.id, db, auto_approved=row.mode == "full_auto")
    _mark_completed(row, "review_prompts")

    if _material_target(row) == MATERIAL_TARGET_PROMPTS_ONLY:
        _complete_run(
            row,
            db,
            project,
            message="Auto-run đã tạo xong prompt video. Bạn có thể upload ảnh và để AI tạo thoại từ prompt.",
        )
        return {"action": "stop"}

    if _material_target(row) == MATERIAL_TARGET_PUBLISHING_KIT:
        _complete_run(
            row,
            db,
            project,
            message="Auto-run đã tạo xong prompt video và bộ nội dung đăng.",
        )
        return {"action": "stop"}

    if _material_target(row) == MATERIAL_TARGET_VIDEO_CLIPS:
        clip_action = _clip_action(row, project, db)
        if clip_action is not None:
            return clip_action
        _mark_completed(row, "generate_clips")
        _mark_completed(row, "waiting_clips")

    voice_action = _voice_action(row, project, db)
    if voice_action is not None:
        return voice_action
    _clear_voice_failures(row)
    _mark_completed(row, "generate_voice")
    _mark_completed(row, "waiting_voice")

    if _needs_subtitle(project.id, db, row):
        _set_step(row, db, "generate_subtitle")
        video_subtitles.generate_subtitle(project.id, db)
        _mark_completed(row, "generate_subtitle")

    if _material_target(row) == MATERIAL_TARGET_VIDEO_CLIPS:
        render_action = _render_action(row, project, db)
        if render_action is not None:
            return render_action
        _mark_completed(row, "generate_render")
        _mark_completed(row, "waiting_render")
        _complete_run(row, db, project, message="Auto-run đã tạo prompt, tải clip Veo, tạo voice/SRT và render xong MP4.")
        return {"action": "stop"}

    _complete_run(row, db, project, message="Auto-run đã tạo xong nguyên liệu.")
    return {"action": "stop"}

def _complete_run(row: DBVideoAutoRun, db: Session, project: DBVideoProject, *, message: str) -> None:
    now = datetime.utcnow()
    row.status = "completed"
    row.current_step = "completed"
    row.progress = 1.0
    row.review_stage = None
    row.completed_at = now
    row.updated_at = now
    _mark_completed(row, "completed")
    db.commit()
    _log(
        row,
        db,
        step_name="auto_run_completed",
        status="completed",
        message=message,
        details=_summary(project.id, db, material_target=_material_target(row)).model_dump(),
    )

def _require_project(row: DBVideoAutoRun, db: Session) -> DBVideoProject:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == row.project_id).first()
    if project is None:
        raise VideoAutoRunError("Không tìm thấy dự án video.", error_code="VIDEO_PROJECT_NOT_FOUND")
    return project

def _validate_project_inputs(project: DBVideoProject, db: Session) -> None:
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoAutoRunNeedsInputError("Auto tạo nguyên liệu chỉ hỗ trợ dự án AI Video phase 2.", error_code="VIDEO_AUTO_RUN_PHASE_UNSUPPORTED")
    source_count = (
        db.query(func.count(DBVideoSourceBlock.id))
        .filter(DBVideoSourceBlock.project_id == project.id, func.trim(DBVideoSourceBlock.content) != "")
        .scalar()
        or 0
    )
    if source_count == 0 and not (project.topic or "").strip():
        raise VideoAutoRunNeedsInputError("Cần nhập yêu cầu hoặc nguồn nội dung trước khi chạy auto.", error_code="VIDEO_AUTO_RUN_SOURCE_REQUIRED")
    if (
        project.prompt_segment_count
        and project.prompt_segment_duration_seconds
        and project.micro_scenes_per_prompt
        and project.prompt_segment_duration_seconds / max(1, project.micro_scenes_per_prompt) < 1.5
    ):
        raise VideoAutoRunNeedsInputError("Mỗi cảnh nhỏ cần tối thiểu khoảng 1.5 giây.", error_code="VIDEO_AUTO_RUN_PROMPT_CONFIG_INVALID")

def _ensure_planning_ready(db: Session) -> None:
    settings = settings_service.get_ai_planning_settings(db)
    check = ai_planning.check_provider(settings, check_exec=False)
    if not check.ready:
        raise VideoAutoRunNeedsInputError(check.message, error_code=check.error_code or "AI_PLANNING_PROVIDER_NOT_READY")

def _needs_story(project: DBVideoProject, row: DBVideoAutoRun) -> bool:
    if _force_pending(row, "develop_story"):
        return True
    if not (project.story_strategy or project.detailed_script):
        return True
    return getattr(project, "planning_status", "draft") in {"draft", "stale"}

def _needs_shots(project_id: str, db: Session, row: DBVideoAutoRun) -> bool:
    if _force_pending(row, "generate_shots"):
        return True
    shots = _ordered_shots(project_id, db)
    return not shots or any(shot.status == "stale" for shot in shots)

def _needs_prompts(project_id: str, db: Session, row: DBVideoAutoRun) -> bool:
    shots = _ordered_shots(project_id, db)
    if not shots:
        return True
    if _force_pending(row, "generate_prompts"):
        return True
    prompt_shot_ids = {
        item[0]
        for item in db.query(DBVideoShotPrompt.shot_id)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.quality_status == "passed")
        .all()
    }
    return any(shot.id not in prompt_shot_ids or shot.prompt_status in {"missing", "stale"} for shot in shots)

def _metadata_required(row: DBVideoAutoRun) -> bool:
    return _material_target(row) in {
        MATERIAL_TARGET_FULL,
        MATERIAL_TARGET_PUBLISHING_KIT,
        MATERIAL_TARGET_VIDEO_CLIPS,
    }

def _needs_publishing_metadata(project_id: str, db: Session, row: DBVideoAutoRun) -> bool:
    if not _metadata_required(row):
        return False
    if _force_pending(row, "generate_publishing_metadata"):
        return True
    summary = video_publishing_metadata.metadata_status_summary(project_id, db)
    return not bool(summary.get("ready"))

def _approve_prompt_review(project_id: str, db: Session, *, auto_approved: bool) -> None:
    now = datetime.utcnow()
    changed = False
    for shot in _ordered_shots(project_id, db):
        if shot.prompt_status != "needs_review":
            continue
        prompt = (
            db.query(DBVideoShotPrompt)
            .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.shot_id == shot.id)
            .order_by(DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
            .first()
        )
        if prompt is None:
            continue
        quality_check = dict(prompt.quality_check or {})
        quality_check["auto_run_review_override"] = "full_auto" if auto_approved else "review_gated"
        prompt.quality_check = quality_check
        prompt.quality_status = "passed"
        shot.prompt_status = "completed"
        shot.updated_at = now
        changed = True
    if changed:
        db.commit()

def _reviewed(row: DBVideoAutoRun, stage: str) -> bool:
    if row.mode == "full_auto":
        _mark_reviewed(row, stage, auto_approved=True)
        return True
    return bool(_results(row).get("reviewed", {}).get(stage))

def _latest_clip_job(project_id: str, db: Session) -> DBVideoClipGenerationJob | None:
    return (
        db.query(DBVideoClipGenerationJob)
        .filter(DBVideoClipGenerationJob.project_id == project_id, DBVideoClipGenerationJob.provider == "veo")
        .order_by(DBVideoClipGenerationJob.created_at.desc())
        .first()
    )

def _ready_provider_clip_count(project_id: str, db: Session) -> int:
    count = 0
    for shot in _ordered_shots(project_id, db):
        clip = (
            db.query(DBVideoShotClip)
            .filter(
                DBVideoShotClip.project_id == project_id,
                DBVideoShotClip.shot_id == shot.id,
                DBVideoShotClip.is_active.is_(True),
                DBVideoShotClip.source == "provider",
                DBVideoShotClip.provider == "veo",
                DBVideoShotClip.status == "ready",
            )
            .order_by(DBVideoShotClip.created_at.desc())
            .first()
        )
        if clip is None:
            continue
        path = video_storage.resolve_artifact_storage_path(clip.file_path)
        if path is not None and path.exists() and path.is_file():
            count += 1
    return count

def _all_provider_clips_ready(project_id: str, db: Session) -> bool:
    shots = _ordered_shots(project_id, db)
    return bool(shots) and _ready_provider_clip_count(project_id, db) == len(shots)

def _remember_clip_job(row: DBVideoAutoRun, job: models.VideoClipGenerationJobResponse | DBVideoClipGenerationJob) -> None:
    results = _results(row)
    results["clip_generation_job_id"] = job.id
    results["clip_generation_status"] = job.status
    _save_results(row, results)

def _clip_action(row: DBVideoAutoRun, project: DBVideoProject, db: Session) -> dict[str, Any] | None:
    if _all_provider_clips_ready(project.id, db):
        return None
    job = _latest_clip_job(project.id, db)
    if job is not None:
        _remember_clip_job(row, job)
        db.commit()
        if job.status in {"queued", "running"}:
            _set_step(row, db, "waiting_clips", status="waiting_clips")
            return {"action": "wait_clips"}
        if job.status in {"needs_login", "needs_user_action", "needs_credit_approval"}:
            raise VideoAutoRunNeedsInputError(
                job.failure_reason or "Job Veo cần bạn xử lý phiên đăng nhập, tài khoản hoặc credit trước khi tiếp tục.",
                error_code=job.error_code or "VIDEO_AUTO_RUN_CLIP_NEEDS_INPUT",
            )
        if job.status in {"failed", "cancelled"}:
            raise VideoAutoRunError(
                job.failure_reason or "Job Veo chưa tải đủ clip về project.",
                error_code=job.error_code or "VIDEO_AUTO_RUN_CLIP_FAILED",
            )
    _set_step(row, db, "generate_clips")
    try:
        response = video_clip_generation.start_job_for_auto_run(
            project.id,
            models.VideoClipGenerationJobStartRequest(
                force=bool(row.force),
                auto_render=False,
                credit_approval_policy="approve_dont_ask_again",
            ),
            db,
            auto_run_id=row.id,
        )
    except video_clip_generation.VideoClipGenerationError as exc:
        raise VideoAutoRunNeedsInputError(str(exc), error_code=exc.error_code) from exc
    if response is None:
        raise VideoAutoRunError("Không tìm thấy dự án để tạo clip Veo.", error_code="VIDEO_PROJECT_NOT_FOUND")
    _remember_clip_job(row, response)
    _set_step(row, db, "waiting_clips", status="waiting_clips")
    return {"action": "run_clip_job", "job_id": response.id}

def _latest_render_job(project_id: str, db: Session) -> DBVideoRenderJob | None:
    return video_rendering.latest_render_job(project_id, db)

def _remember_render_job(row: DBVideoAutoRun, job: models.VideoRenderJobResponse | DBVideoRenderJob) -> None:
    results = _results(row)
    results["render_job_id"] = job.id
    results["render_job_status"] = job.status
    if getattr(job, "output_path", None):
        results["render_output_path"] = job.output_path
    _save_results(row, results)

def _render_action(row: DBVideoAutoRun, project: DBVideoProject, db: Session) -> dict[str, Any] | None:
    job = _latest_render_job(project.id, db)
    if job is not None:
        _remember_render_job(row, job)
        db.commit()
        if job.status == "completed" and job.output_path:
            return None
        if job.status in {"queued", "running"}:
            _set_step(row, db, "waiting_render", status="waiting_render")
            return {"action": "wait_render"}
        if job.status in {"failed", "cancelled"}:
            raise VideoAutoRunError(
                job.failure_reason or "Render MP4 chưa hoàn tất.",
                error_code=job.error_code or "VIDEO_AUTO_RUN_RENDER_FAILED",
            )
    # An auto run cannot see the UI, so it reuses the settings of the project's most
    # recent render instead of always building with defaults.
    settings = video_rendering.render_settings_for_project(project.id, db)
    readiness = video_rendering.get_render_readiness(project.id, db, settings)
    if readiness is None:
        raise VideoAutoRunError("Không tìm thấy dự án để render MP4.", error_code="VIDEO_PROJECT_NOT_FOUND")
    if not readiness.ready:
        reason = "; ".join(readiness.missing_reasons) or "Project chưa đủ điều kiện render MP4."
        raise VideoAutoRunError(reason, error_code="VIDEO_AUTO_RUN_RENDER_NOT_READY")
    _set_step(row, db, "generate_render")
    try:
        response = video_rendering.create_render_job_for_auto_run(
            project.id,
            models.VideoRenderJobCreateRequest(settings=settings),
            db,
        )
    except video_rendering.VideoRenderError as exc:
        raise VideoAutoRunError(str(exc), error_code=exc.error_code) from exc
    if response is None:
        raise VideoAutoRunError("Không tìm thấy dự án để render MP4.", error_code="VIDEO_PROJECT_NOT_FOUND")
    _remember_render_job(row, response)
    _set_step(row, db, "waiting_render", status="waiting_render")
    return {"action": "run_render_job", "job_id": response.id}

def _voice_action(row: DBVideoAutoRun, project: DBVideoProject, db: Session) -> dict[str, Any] | None:
    if video_speech.uses_veo_native_speech(project):
        return None
    _sync_busy_shot_voice_statuses(project.id, db)
    shots = [shot for shot in _ordered_shots(project.id, db) if (shot.english_narration or "").strip()]
    if not shots:
        return None
    failed = [shot for shot in shots if shot.voice_status == "failed"]
    retrying_voice = row.current_step == "generate_voice"
    blocked_failed = [shot for shot in failed if not _is_interrupted_voice_failure(shot)]
    if blocked_failed and not retrying_voice:
        _record_voice_failures(row, blocked_failed)
        db.commit()
        labels = ", ".join(str(shot.shot_order) for shot in blocked_failed)
        raise VideoAutoRunError(f"Một số segment tạo voice thất bại: {labels}.", error_code="VIDEO_AUTO_RUN_VOICE_FAILED")
    busy = [shot for shot in shots if shot.voice_status in VOICE_BUSY_STATUSES]
    if busy:
        _set_step(row, db, "waiting_voice", status="waiting_voice")
        return {"action": "wait_voice"}
    missing = [
        shot
        for shot in shots
        if shot.voice_status in VOICE_RETRYABLE_STATUSES or not shot.audio_path or not shot.audio_duration
    ]
    if missing:
        if not project.voice_profile_id:
            raise VideoAutoRunNeedsInputError("Chưa chọn voice profile cho dự án video.", error_code="VIDEO_AUTO_RUN_VOICE_PROFILE_REQUIRED")
        _set_step(row, db, "generate_voice")
        return {"action": "enqueue_voice", "shot_ids": [shot.id for shot in missing[:VOICE_ENQUEUE_BATCH_SIZE]]}
    return None

def _sync_busy_shot_voice_statuses(project_id: str, db: Session) -> None:
    busy_ids = [
        item[0]
        for item in db.query(DBVideoShot.id)
        .filter(
            DBVideoShot.project_id == project_id,
            DBVideoShot.generation_id.isnot(None),
            DBVideoShot.voice_status.in_(VOICE_BUSY_STATUSES),
        )
        .all()
    ]
    for shot_id in busy_ids:
        video_voice.sync_shot_voice_status(project_id, shot_id, db)

async def _enqueue_voice(run_id: str, shot_ids: list[str]) -> None:
    db = next(get_db())
    try:
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
        if row is None or row.status in TERMINAL_STATUSES or row.status == "cancelled":
            return
        project = db.query(DBVideoProject).filter(DBVideoProject.id == row.project_id).first()
        if project is None:
            return
        for shot_id in shot_ids:
            db.refresh(row)
            if row.status in TERMINAL_STATUSES or row.status == "cancelled":
                return
            shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id, DBVideoShot.id == shot_id).first()
            if shot is None or not (shot.english_narration or "").strip():
                continue
            if shot.voice_status in VOICE_BUSY_STATUSES:
                continue
            await video_voice.create_shot_narration(
                project.id,
                shot.id,
                models.VideoSceneNarrationRequest(
                    profile_id=project.voice_profile_id,
                    language=project.target_language,
                    force=shot.voice_status in {"failed", "stale"},
                ),
                db,
            )
        db.refresh(row)
        if row.status in TERMINAL_STATUSES or row.status == "cancelled":
            return
        row.status = "waiting_voice"
        row.current_step = "waiting_voice"
        row.progress = STEP_PROGRESS["waiting_voice"]
        row.updated_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        if row is not None:
            _fail_run(row, db, exc)
    finally:
        db.close()

def _needs_subtitle(project_id: str, db: Session, row: DBVideoAutoRun) -> bool:
    if _force_pending(row, "generate_subtitle"):
        return True
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    if subtitle is None or subtitle.status != "completed":
        return True
    shots = [shot for shot in _ordered_shots(project_id, db) if (shot.english_narration or "").strip()]
    return any(shot.subtitle_status != "completed" for shot in shots)

def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc()).all()

def _needs_input(row: DBVideoAutoRun, db: Session, message: str, error_code: str) -> None:
    row.status = "needs_input"
    row.failure_reason = message
    row.error_code = error_code
    row.updated_at = datetime.utcnow()
    db.commit()
    _log(row, db, step_name="auto_run_needs_input", status="needs_input", message=message, error_code=error_code)

def _fail_run(row: DBVideoAutoRun, db: Session, exc: BaseException) -> None:
    error_code = getattr(exc, "error_code", "VIDEO_AUTO_RUN_FAILED")
    row.status = "failed"
    row.failure_reason = str(exc)
    row.error_code = error_code
    row.completed_at = datetime.utcnow()
    row.updated_at = row.completed_at
    db.commit()
    _log(row, db, step_name="auto_run_failed", status="failed", message=str(exc), error_code=error_code, details={"current_step": row.current_step})

def _fail_run_by_id(run_id: str, message: str, error_code: str) -> None:
    db = next(get_db())
    try:
        row = db.query(DBVideoAutoRun).filter(DBVideoAutoRun.id == run_id).first()
        if row is not None and row.status not in TERMINAL_STATUSES:
            _fail_run(row, db, VideoAutoRunError(message, error_code=error_code))
    finally:
        db.close()

def _summary(
    project_id: str,
    db: Session,
    *,
    material_target: str = MATERIAL_TARGET_FULL,
) -> models.VideoAutoRunSummary:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shots = _ordered_shots(project_id, db)
    prompt_shot_ids = {
        item[0]
        for item in db.query(DBVideoShotPrompt.shot_id)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.quality_status == "passed")
        .all()
    }
    narrated = [shot for shot in shots if (shot.english_narration or "").strip()]
    if video_speech.uses_veo_native_speech(project):
        clips = video_rendering.active_clips_for_project(project_id, db)
        voice_completed = [
            shot
            for shot in narrated
            if (clip := clips.get(shot.id)) is not None
            and clip.status == "ready"
            and clip.has_audio
            and clip.duration_seconds
        ]
    else:
        voice_completed = [shot for shot in narrated if shot.voice_status == "completed" and shot.audio_path and shot.audio_duration]
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    package = db.query(DBVideoPackageExport).filter(DBVideoPackageExport.project_id == project_id).order_by(DBVideoPackageExport.created_at.desc()).first()
    prompt_completed = [shot for shot in shots if shot.id in prompt_shot_ids and shot.prompt_status == "completed"]
    subtitle_status = subtitle.status if subtitle else "missing"
    prompt_ready = bool(shots) and len(prompt_completed) == len(shots)
    clip_completed_count = _ready_provider_clip_count(project_id, db)
    clip_job = _latest_clip_job(project_id, db)
    clip_job_completed = bool(clip_job and clip_job.status == "completed")
    render_job = _latest_render_job(project_id, db)
    metadata_summary = video_publishing_metadata.metadata_status_summary(project_id, db)
    metadata_ready = bool(metadata_summary.get("ready"))
    if material_target == MATERIAL_TARGET_PROMPTS_ONLY:
        core_ready = prompt_ready
    elif material_target == MATERIAL_TARGET_PUBLISHING_KIT:
        core_ready = prompt_ready and metadata_ready
    elif material_target == MATERIAL_TARGET_VIDEO_CLIPS:
        core_ready = (
            prompt_ready
            and metadata_ready
            and bool(shots)
            and clip_completed_count == len(shots)
            and bool(render_job and render_job.status == "completed" and render_job.output_path)
        )
    else:
        core_ready = prompt_ready and metadata_ready and len(voice_completed) == len(narrated) and subtitle_status == "completed"
    return models.VideoAutoRunSummary(
        shot_count=len(shots),
        prompt_completed_count=len(prompt_completed),
        prompt_required_count=len(shots),
        voice_completed_count=len(voice_completed),
        voice_required_count=len(narrated),
        clip_completed_count=clip_completed_count,
        clip_required_count=len(shots),
        clip_generation_job_id=clip_job.id if clip_job else None,
        clip_generation_status=clip_job.status if clip_job else None,
        clip_generation_error_code=None if clip_job_completed else (clip_job.error_code if clip_job else None),
        clip_generation_failure_reason=None if clip_job_completed else (clip_job.failure_reason if clip_job else None),
        render_job_id=render_job.id if render_job else None,
        render_job_status=render_job.status if render_job else None,
        render_job_error_code=render_job.error_code if render_job else None,
        render_job_failure_reason=render_job.failure_reason if render_job else None,
        render_output_path=render_job.output_path if render_job else None,
        publishing_metadata_status=str(metadata_summary.get("status") or "missing"),
        publishing_metadata_ready=metadata_ready,
        publishing_metadata_stale=bool(metadata_summary.get("stale")),
        publishing_metadata_revision=metadata_summary.get("revision"),
        publishing_metadata_platforms_ready=int(metadata_summary.get("platforms_ready") or 0),
        subtitle_status=subtitle_status,
        package_status=package.status if package else None,
        package_id=package.id if package else None,
        core_ready=core_ready,
        package_ready=bool(package and package.status == "completed" and not package.stale),
    )

def auto_run_response(row: DBVideoAutoRun, db: Session) -> models.VideoAutoRunResponse:
    results = _results(row)
    material_target = _material_target(row)
    completed_steps = list(dict.fromkeys(results.get("completed_steps", [])))
    pending_steps = (
        []
        if row.status == "completed"
        else [step for step in _step_order(row) if step not in completed_steps and step not in TRANSIENT_STEPS]
    )
    return models.VideoAutoRunResponse(
        id=row.id,
        project_id=row.project_id,
        mode=row.mode,
        material_target=material_target,
        status=row.status,
        current_step=row.current_step,
        review_stage=row.review_stage,
        progress=float(row.progress or 0.0),
        force=bool(row.force),
        step_results_json=results,
        completed_steps=completed_steps,
        pending_steps=pending_steps,
        failure_reason=row.failure_reason,
        error_code=row.error_code,
        summary=_summary(row.project_id, db, material_target=material_target),
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
