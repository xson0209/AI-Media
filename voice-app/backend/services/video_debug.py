"""Safe debug summaries for AI Video Assistant."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..database import (
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoPackageExport as DBVideoPackageExport,
    VideoProject as DBVideoProject,
    VideoProviderSession as DBVideoProviderSession,
    VideoRenderJob as DBVideoRenderJob,
    VideoScene as DBVideoScene,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
    VideoSubtitle as DBVideoSubtitle,
)
from . import video_errors, video_language, video_observability, video_purpose

_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|bearer|authorization|password|cookie)\s*[:=]\s*([^\s,;]+)"
)
_BEARER_TEXT_PATTERN = re.compile(r"(?i)bearer\s+[^\s,;]+")

def _safe_debug_text(value: Any, *, max_length: int = 800) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = _SECRET_TEXT_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _BEARER_TEXT_PATTERN.sub("bearer [redacted]", text)
    if len(text) > max_length:
        return f"{text[:max_length]}...[truncated]"
    return text


def get_project_debug_details(project_id: str, db: Session) -> dict[str, Any] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    scenes = (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id).first()
    shots = (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc())
        .all()
    )
    source_count = db.query(DBVideoSourceBlock).filter(DBVideoSourceBlock.project_id == project_id).count()
    prompt_count = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project_id).count()
    clip_rows = db.query(DBVideoShotClip).filter(DBVideoShotClip.project_id == project_id, DBVideoShotClip.is_active.is_(True)).all()
    clips_by_shot = {clip.shot_id: clip for clip in clip_rows}
    events = video_observability.latest_events(project_id, db, limit=30)
    latest_errors = [event for event in events if event.status == "failure"][:10]
    package = (
        db.query(DBVideoPackageExport)
        .filter(DBVideoPackageExport.project_id == project_id)
        .order_by(DBVideoPackageExport.created_at.desc())
        .first()
    )
    render_job = (
        db.query(DBVideoRenderJob)
        .filter(DBVideoRenderJob.project_id == project_id)
        .order_by(DBVideoRenderJob.created_at.desc())
        .first()
    )
    clip_job = (
        db.query(DBVideoClipGenerationJob)
        .filter(DBVideoClipGenerationJob.project_id == project_id)
        .order_by(DBVideoClipGenerationJob.created_at.desc())
        .first()
    )
    clip_job_items = (
        db.query(DBVideoClipGenerationItem)
        .filter(DBVideoClipGenerationItem.job_id == clip_job.id)
        .order_by(DBVideoClipGenerationItem.shot_order.asc())
        .all()
        if clip_job is not None
        else []
    )
    provider_session = (
        db.query(DBVideoProviderSession)
        .filter(DBVideoProviderSession.provider == "veo", DBVideoProviderSession.is_default.is_(True))
        .order_by(DBVideoProviderSession.updated_at.desc())
        .first()
    )
    return {
        "request_id": video_errors.current_request_id(),
        "project": {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "phase": getattr(project, "phase", "phase1"),
            "target_language": video_language.normalize_video_language(getattr(project, "target_language", None)),
            "video_purpose": video_purpose.normalize_video_purpose(getattr(project, "video_purpose", None)),
            "dialogue_mode": video_purpose.normalize_dialogue_mode(getattr(project, "dialogue_mode", None), purpose=getattr(project, "video_purpose", None)),
            "narration_density": video_purpose.normalize_narration_density(getattr(project, "narration_density", None), purpose=getattr(project, "video_purpose", None)),
            "planning_status": getattr(project, "planning_status", "draft"),
            "story_approved": bool(getattr(project, "story_approved", False)),
            "last_request_id": getattr(project, "last_request_id", None),
            "package_stale": bool(project.package_stale),
            "script_approved": bool(project.script_approved),
            "has_retention_plan": bool(getattr(project, "retention_plan_json", None)),
            "has_sound_design_plan": bool(getattr(project, "sound_design_plan_json", None)),
        },
        "artifact_status": {
            "source_blocks": source_count,
            "scenes": len(scenes),
            "shots": len(shots),
            "video_prompts": prompt_count,
            "shot_clips": len(clip_rows),
            "clip_generation_status": clip_job.status if clip_job else "missing",
            "subtitle_status": subtitle.status if subtitle else "missing",
            "log_path": video_observability.latest_log_path(project_id, db),
        },
        "scenes": [
            {
                "id": scene.id,
                "order": scene.scene_order,
                "approved": bool(scene.approved),
                "no_narration": bool(scene.no_narration),
                "prompt_status": scene.prompt_status,
                "voice_status": scene.voice_status,
                "subtitle_status": scene.subtitle_status,
                "generation_id": scene.generation_id,
            }
            for scene in scenes
        ],
        "shots": [
            {
                "id": shot.id,
                "order": shot.shot_order,
                "scene_id": shot.scene_id,
                "locked": bool(shot.locked),
                "status": shot.status,
                "prompt_status": shot.prompt_status,
                "voice_status": shot.voice_status,
                "subtitle_status": shot.subtitle_status,
                "generation_id": shot.generation_id,
                "audio_path": shot.audio_path,
                "audio_duration": shot.audio_duration,
                "retention_role": (shot.retention_json or {}).get("retention_role") if isinstance(shot.retention_json, dict) else None,
                "transition_type": (shot.transition_json or {}).get("transition_type") if isinstance(shot.transition_json, dict) else None,
                "sound_cue_count": len((shot.sound_design_json or {}).get("sound_cues", [])) if isinstance(shot.sound_design_json, dict) else 0,
                "retainability_quality": shot.retainability_quality_check,
                "clip_status": clips_by_shot[shot.id].status if shot.id in clips_by_shot else "missing",
                "clip_duration": clips_by_shot[shot.id].duration_seconds if shot.id in clips_by_shot else None,
            }
            for shot in shots
        ],
        "subtitle": None
        if subtitle is None
        else {
            "id": subtitle.id,
            "status": subtitle.status,
            "format": subtitle.format,
        },
        "latest_package": None
        if package is None
        else {
            "id": package.id,
            "status": package.status,
            "stale": bool(package.stale),
            "failure_reason": _safe_debug_text(package.failure_reason),
        },
        "latest_render_job": None
        if render_job is None
        else {
            "id": render_job.id,
            "status": render_job.status,
            "progress": render_job.progress,
            "stale": bool(render_job.stale),
            "current_step": render_job.current_step,
            "failure_reason": _safe_debug_text(render_job.failure_reason),
            "output_path": render_job.output_path,
        },
        "provider_session": None
        if provider_session is None
        else {
            "id": provider_session.id,
            "provider": provider_session.provider,
            "provider_tool": provider_session.provider_tool,
            "status": provider_session.status,
            "connection_label": provider_session.connection_label,
            "verified_account_hint": provider_session.verified_account_hint,
            "identity_status": provider_session.identity_status,
            "identity_verified_at": provider_session.identity_verified_at.isoformat()
            if provider_session.identity_verified_at
            else None,
            "last_checked_at": provider_session.last_checked_at.isoformat() if provider_session.last_checked_at else None,
            "failure_reason": _safe_debug_text(provider_session.failure_reason),
        },
        "latest_clip_generation_job": None
        if clip_job is None
        else {
            "id": clip_job.id,
            "provider": clip_job.provider,
            "session_id": clip_job.session_id,
            "status": clip_job.status,
            "current_step": clip_job.current_step,
            "progress": clip_job.progress,
            "credit_approval_policy": clip_job.credit_approval_policy,
            "credit_spent_estimate": clip_job.credit_spent_estimate,
            "auto_render": bool(clip_job.auto_render),
            "render_job_id": clip_job.render_job_id,
            "failure_reason": _safe_debug_text(clip_job.failure_reason),
            "error_code": clip_job.error_code,
            "items": [
                {
                    "id": item.id,
                    "shot_id": item.shot_id,
                    "shot_order": item.shot_order,
                    "status": item.status,
                    "attempt_count": item.attempt_count,
                    "credit_cost": item.credit_cost,
                    "provider_duration_seconds": item.provider_duration_seconds,
                    "download_correlation_id": item.download_correlation_id,
                    "clip_id": item.clip_id,
                    "failure_reason": _safe_debug_text(item.failure_reason),
                }
                for item in clip_job_items
            ],
        },
        "latest_errors": [
            {
                "request_id": event.request_id,
                "step_name": event.step_name,
                "error_code": event.error_code,
                "message": _safe_debug_text(event.message),
                "technical_details": event.technical_details,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in latest_errors
        ],
        "events": [
            {
                "request_id": event.request_id,
                "step_name": event.step_name,
                "status": event.status,
                "duration_ms": event.duration_ms,
                "retry_count": event.retry_count,
                "error_code": event.error_code,
                "message": event.message,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
    }
