"""Timeline MP4 rendering for AI Video Assistant phase 2."""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import shlex
import shutil
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoSubtitle as DBVideoSubtitle,
    get_db,
)
from . import video_observability, video_series_memory, video_storage
from .task_queue import create_background_task

MAX_CLIP_SIZE_BYTES = 700 * 1024 * 1024
MAX_CLIP_DURATION_SECONDS = 120.0
CLIP_DURATION_WARNING_RATIO = 0.35
_STDERR_LIMIT = 4000
_NORMALIZE_CACHE_VERSION = "normalize-v1"
RENDER_CACHE_MAX_MB_ENV = "VOICEBOX_RENDER_CACHE_MAX_MB"
RENDER_CACHE_MAX_AGE_DAYS_ENV = "VOICEBOX_RENDER_CACHE_MAX_AGE_DAYS"
_render_lock = asyncio.Lock()


class VideoRenderError(ValueError):
    """Raised when video timeline rendering cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_RENDER_ERROR"):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class FFmpegTools:
    ffmpeg: str | None
    ffprobe: str | None

    @property
    def ffmpeg_ready(self) -> bool:
        return bool(self.ffmpeg)

    @property
    def ffprobe_ready(self) -> bool:
        return bool(self.ffprobe)


@dataclass(frozen=True)
class ClipMetadata:
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    codec: str | None
    has_audio: bool


def detect_tools() -> FFmpegTools:
    """Find FFmpeg and FFprobe from runtime env overrides, PATH, or ffmpeg-full."""
    configured_ffmpeg = _tool_from_env("VOICEBOX_FFMPEG_PATH")
    configured_ffprobe = _tool_from_env("VOICEBOX_FFPROBE_PATH")
    ffmpeg = configured_ffmpeg or _select_preferred_ffmpeg(_default_tool_candidates("ffmpeg"))
    ffprobe = configured_ffprobe or _matching_sibling_tool(ffmpeg, "ffprobe") or _first_existing_tool(_default_tool_candidates("ffprobe"))
    return FFmpegTools(ffmpeg=ffmpeg, ffprobe=ffprobe)

def _tool_from_env(env_name: str) -> str | None:
    configured = os.environ.get(env_name)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return str(candidate)
    return None

def _default_tool_candidates(binary: str) -> list[str]:
    candidates = [shutil.which(binary)]
    for prefix in ("/opt/homebrew", "/usr/local"):
        candidates.append(f"{prefix}/opt/ffmpeg-full/bin/{binary}")
    return [candidate for candidate in candidates if candidate]

def _first_existing_tool(candidates: list[str]) -> str | None:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)
    return None

def _select_preferred_ffmpeg(candidates: list[str]) -> str | None:
    existing: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        path = str(Path(candidate).expanduser())
        if path in seen or not Path(path).exists():
            continue
        seen.add(path)
        existing.append(path)
    for candidate in existing:
        if _select_subtitle_filter(candidate):
            return candidate
    return existing[0] if existing else None

def _matching_sibling_tool(selected_tool: str | None, sibling_binary: str) -> str | None:
    if not selected_tool:
        return None
    sibling = Path(selected_tool).with_name(sibling_binary)
    return str(sibling) if sibling.exists() else None

@lru_cache(maxsize=8)
def _ffmpeg_filter_names(ffmpeg: str) -> frozenset[str]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        return frozenset()
    names: set[str] = set()
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] and parts[0][0] in ".TSC":
            names.add(parts[1])
    return frozenset(names)

def _select_subtitle_filter(ffmpeg: str) -> str | None:
    names = _ffmpeg_filter_names(ffmpeg)
    if "subtitles" in names:
        return "subtitles"
    if "ass" in names:
        return "ass"
    return None


def _truncate_stderr(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) <= _STDERR_LIMIT:
        return text
    return text[-_STDERR_LIMIT:]


def _run_command(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        command = " ".join(shlex.quote(arg) for arg in args[:8])
        raise VideoRenderError(
            "FFmpeg xử lý video thất bại.",
            error_code="VIDEO_RENDER_FFMPEG_FAILED",
        ) from RuntimeError(f"{command}\n{_truncate_stderr(result.stderr)}")
    return result


def probe_clip(path: Path, *, ffprobe_path: str | None = None) -> ClipMetadata:
    """Read clip metadata via ffprobe."""
    ffprobe = ffprobe_path or detect_tools().ffprobe
    if not ffprobe:
        raise VideoRenderError(
            "Chưa tìm thấy FFprobe. Hãy cài FFmpeg hoặc cấu hình đường dẫn FFmpeg trước khi upload clip.",
            error_code="VIDEO_RENDER_FFPROBE_MISSING",
        )
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise VideoRenderError(
            "Không đọc được metadata video. Hãy kiểm tra lại file clip.",
            error_code="VIDEO_RENDER_CLIP_INVALID",
        ) from RuntimeError(_truncate_stderr(result.stderr) or "ffprobe failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoRenderError("Metadata video không hợp lệ.", error_code="VIDEO_RENDER_CLIP_INVALID") from exc

    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise VideoRenderError("File upload không có video stream hợp lệ.", error_code="VIDEO_RENDER_CLIP_INVALID")
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = _float_or_none(video_stream.get("duration")) or _float_or_none((payload.get("format") or {}).get("duration"))
    fps = _fps_from_stream(video_stream)
    return ClipMetadata(
        duration_seconds=duration,
        width=_int_or_none(video_stream.get("width")),
        height=_int_or_none(video_stream.get("height")),
        fps=fps,
        codec=video_stream.get("codec_name"),
        has_audio=audio_stream is not None,
    )


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _fps_from_stream(stream: dict[str, Any]) -> float | None:
    raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not raw or raw == "0/0":
        return None
    if isinstance(raw, str) and "/" in raw:
        numerator, denominator = raw.split("/", 1)
        try:
            den = float(denominator)
            return float(numerator) / den if den else None
        except ValueError:
            return None
    return _float_or_none(raw)


def _clip_response(row: DBVideoShotClip) -> models.VideoShotClipResponse:
    return models.VideoShotClipResponse.model_validate(row)


def _job_response(row: DBVideoRenderJob) -> models.VideoRenderJobResponse:
    return models.VideoRenderJobResponse.model_validate(row)


def _get_project_shot(project_id: str, shot_id: str, db: Session) -> tuple[DBVideoProject, DBVideoShot] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if project is None or shot is None:
        return None
    return project, shot


def get_active_clip(project_id: str, shot_id: str, db: Session) -> models.VideoShotClipResponse | None:
    clip = (
        db.query(DBVideoShotClip)
        .filter(DBVideoShotClip.project_id == project_id, DBVideoShotClip.shot_id == shot_id, DBVideoShotClip.is_active.is_(True))
        .order_by(DBVideoShotClip.created_at.desc())
        .first()
    )
    return _clip_response(clip) if clip else None


def _mark_render_outputs_stale(project_id: str, db: Session) -> None:
    db.query(DBVideoRenderJob).filter(
        DBVideoRenderJob.project_id == project_id,
        DBVideoRenderJob.status == "completed",
        DBVideoRenderJob.stale.is_(False),
    ).update({"stale": True, "updated_at": datetime.utcnow()}, synchronize_session=False)


def mark_render_outputs_stale(project_id: str, db: Session) -> None:
    """Mark completed render outputs as stale after timeline inputs change."""
    _mark_render_outputs_stale(project_id, db)


def upload_shot_clip(
    project_id: str,
    shot_id: str,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    db: Session,
) -> models.VideoShotClipResponse | None:
    result = _get_project_shot(project_id, shot_id, db)
    if result is None:
        return None
    project, shot = result
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoRenderError("Chỉ project AI Video phase 2 mới hỗ trợ dựng nhanh MP4.", error_code="VIDEO_RENDER_PHASE_REQUIRED")
    if not data:
        raise VideoRenderError("File clip rỗng.", error_code="VIDEO_RENDER_CLIP_EMPTY")
    if len(data) > MAX_CLIP_SIZE_BYTES:
        raise VideoRenderError("File clip quá lớn. Hãy dùng clip ngắn hơn hoặc nén file trước khi upload.", error_code="VIDEO_RENDER_CLIP_TOO_LARGE")

    now = datetime.utcnow()
    suffix = Path(filename or "clip.mp4").suffix.lower() or mimetypes.guess_extension(content_type or "") or ".mp4"
    if suffix not in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
        raise VideoRenderError("Định dạng clip chưa được hỗ trợ. Hãy dùng MP4, MOV, WEBM hoặc MKV.", error_code="VIDEO_RENDER_CLIP_UNSUPPORTED")
    clip_id = str(uuid.uuid4())
    clip_dir = video_storage.get_project_subdir(project_id, "shot_clips")
    path = clip_dir / f"clip-{shot.shot_order:03d}-{clip_id}{suffix}"
    path.write_bytes(data)

    db.query(DBVideoShotClip).filter(
        DBVideoShotClip.project_id == project_id,
        DBVideoShotClip.shot_id == shot_id,
        DBVideoShotClip.is_active.is_(True),
    ).update({"is_active": False, "updated_at": now}, synchronize_session=False)

    row = DBVideoShotClip(
        id=clip_id,
        project_id=project_id,
        shot_id=shot_id,
        source="upload",
        status="pending",
        file_path=video_storage.to_artifact_storage_path(path),
        original_filename=filename,
        mime_type=content_type,
        size_bytes=len(data),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        metadata = probe_clip(path)
        if metadata.duration_seconds and metadata.duration_seconds > MAX_CLIP_DURATION_SECONDS:
            raise VideoRenderError("Clip quá dài cho luồng dựng nhanh. Hãy upload clip ngắn hơn.", error_code="VIDEO_RENDER_CLIP_TOO_LONG")
        row.duration_seconds = metadata.duration_seconds
        row.width = metadata.width
        row.height = metadata.height
        row.fps = metadata.fps
        row.codec = metadata.codec
        row.has_audio = metadata.has_audio
        row.status = "ready"
        row.failure_reason = None
    except VideoRenderError as exc:
        row.status = "failed"
        row.failure_reason = str(exc)
    _mark_render_outputs_stale(project_id, db)
    db.commit()
    db.refresh(row)
    return _clip_response(row)


def import_provider_clip(
    project_id: str,
    shot_id: str,
    *,
    source_path: Path,
    original_filename: str | None,
    provider: str,
    provider_asset_id: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
    db: Session,
) -> models.VideoShotClipResponse | None:
    result = _get_project_shot(project_id, shot_id, db)
    if result is None:
        return None
    project, shot = result
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoRenderError("Chỉ project AI Video phase 2 mới hỗ trợ import clip provider.", error_code="VIDEO_RENDER_PHASE_REQUIRED")
    if not source_path.exists() or not source_path.is_file():
        raise VideoRenderError("File clip provider không còn tồn tại.", error_code="VIDEO_PROVIDER_CLIP_FILE_NOT_FOUND")
    size_bytes = source_path.stat().st_size
    if size_bytes <= 0:
        raise VideoRenderError("File clip provider rỗng.", error_code="VIDEO_RENDER_CLIP_EMPTY")
    if size_bytes > MAX_CLIP_SIZE_BYTES:
        raise VideoRenderError("File clip provider quá lớn.", error_code="VIDEO_RENDER_CLIP_TOO_LARGE")

    suffix = source_path.suffix.lower() or mimetypes.guess_extension(mimetypes.guess_type(original_filename or "")[0] or "") or ".mp4"
    if suffix not in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
        raise VideoRenderError("Định dạng clip provider chưa được hỗ trợ.", error_code="VIDEO_RENDER_CLIP_UNSUPPORTED")
    now = datetime.utcnow()
    clip_id = str(uuid.uuid4())
    clip_dir = video_storage.get_project_subdir(project_id, "shot_clips")
    dest_path = clip_dir / f"clip-{shot.shot_order:03d}-{clip_id}{suffix}"
    shutil.copy2(source_path, dest_path)

    db.query(DBVideoShotClip).filter(
        DBVideoShotClip.project_id == project_id,
        DBVideoShotClip.shot_id == shot_id,
        DBVideoShotClip.is_active.is_(True),
    ).update({"is_active": False, "updated_at": now}, synchronize_session=False)

    row = DBVideoShotClip(
        id=clip_id,
        project_id=project_id,
        shot_id=shot_id,
        source="provider",
        status="pending",
        file_path=video_storage.to_artifact_storage_path(dest_path),
        original_filename=video_storage.sanitize_download_filename(
            original_filename or source_path.name,
            fallback=f"veo-{shot.shot_order:03d}{suffix}",
        ),
        mime_type=mimetypes.guess_type(dest_path.name)[0],
        size_bytes=size_bytes,
        is_active=True,
        provider=provider,
        provider_asset_id=provider_asset_id,
        provider_metadata=provider_metadata or {},
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        metadata = probe_clip(dest_path)
        if metadata.duration_seconds and metadata.duration_seconds > MAX_CLIP_DURATION_SECONDS:
            raise VideoRenderError("Clip provider quá dài cho luồng dựng nhanh.", error_code="VIDEO_RENDER_CLIP_TOO_LONG")
        row.duration_seconds = metadata.duration_seconds
        row.width = metadata.width
        row.height = metadata.height
        row.fps = metadata.fps
        row.codec = metadata.codec
        row.has_audio = metadata.has_audio
        row.status = "ready"
        row.failure_reason = None
    except VideoRenderError as exc:
        row.status = "failed"
        row.failure_reason = str(exc)
    _mark_render_outputs_stale(project_id, db)
    db.commit()
    db.refresh(row)
    return _clip_response(row)

def delete_shot_clip(project_id: str, shot_id: str, db: Session) -> bool | None:
    result = _get_project_shot(project_id, shot_id, db)
    if result is None:
        return None
    clip = (
        db.query(DBVideoShotClip)
        .filter(DBVideoShotClip.project_id == project_id, DBVideoShotClip.shot_id == shot_id, DBVideoShotClip.is_active.is_(True))
        .order_by(DBVideoShotClip.created_at.desc())
        .first()
    )
    if clip is None:
        return False
    clip.is_active = False
    clip.updated_at = datetime.utcnow()
    video_storage.remove_artifact_file(clip.file_path)
    _mark_render_outputs_stale(project_id, db)
    db.commit()
    return True


def _ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc()).all()


def _active_clips(project_id: str, db: Session) -> dict[str, DBVideoShotClip]:
    rows = (
        db.query(DBVideoShotClip)
        .filter(DBVideoShotClip.project_id == project_id, DBVideoShotClip.is_active.is_(True))
        .order_by(DBVideoShotClip.created_at.desc())
        .all()
    )
    clips: dict[str, DBVideoShotClip] = {}
    for row in rows:
        clips.setdefault(row.shot_id, row)
    return clips


def shot_requires_narration(shot: DBVideoShot) -> bool:
    return bool((shot.english_narration or "").strip())


def resolve_shot_duration(shot: DBVideoShot) -> float | None:
    if shot_requires_narration(shot):
        return float(shot.audio_duration) if shot.audio_duration and shot.audio_duration > 0 else None
    return float(shot.duration_seconds) if shot.duration_seconds and shot.duration_seconds > 0 else None


def build_timeline_manifest(project_id: str, db: Session) -> list[models.VideoRenderTimelineShot]:
    shots = _ordered_shots(project_id, db)
    clips = _active_clips(project_id, db)
    cursor = 0.0
    timeline: list[models.VideoRenderTimelineShot] = []
    for shot in shots:
        duration = resolve_shot_duration(shot)
        if duration is None:
            continue
        clip = clips.get(shot.id)
        start = cursor
        end = start + duration
        timeline.append(
            models.VideoRenderTimelineShot(
                shot_id=shot.id,
                shot_order=shot.shot_order,
                scene_id=shot.scene_id,
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                duration_seconds=round(duration, 3),
                clip_id=clip.id if clip else None,
                clip_duration_seconds=clip.duration_seconds if clip else None,
                has_narration=shot_requires_narration(shot),
                retention=shot.retention_json,
                transition=shot.transition_json,
                sound_design=shot.sound_design_json,
                retainability_quality_check=shot.retainability_quality_check,
            )
        )
        cursor = end
    return timeline


def get_render_readiness(
    project_id: str,
    db: Session,
    settings: models.VideoRenderSettings | None = None,
) -> models.VideoRenderReadinessResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    settings = settings or models.VideoRenderSettings()
    tools = detect_tools()
    shots = _ordered_shots(project_id, db)
    clips = _active_clips(project_id, db)
    missing_clip: list[str] = []
    invalid_clip: list[str] = []
    missing_voice: list[str] = []
    missing_timer: list[str] = []
    warnings: list[models.VideoRenderWarning] = []
    has_sound_metadata = any(bool(getattr(shot, "sound_design_json", None)) for shot in shots)
    if has_sound_metadata:
        warnings.append(
            models.VideoRenderWarning(
                code="VIDEO_RENDER_SOUND_DESIGN_METADATA_ONLY",
                message="Sound design/SFX/BGM hiện là chỉ dẫn dựng; MP4 render hiện tại chưa tự mix asset SFX/BGM thật.",
            )
        )

    for shot in shots:
        duration = resolve_shot_duration(shot)
        if shot_requires_narration(shot) and (shot.voice_status != "completed" or not shot.audio_path or not shot.audio_duration):
            missing_voice.append(shot.id)
        if duration is None:
            missing_timer.append(shot.id)
        clip = clips.get(shot.id)
        if clip is None:
            missing_clip.append(shot.id)
        elif clip.status != "ready":
            invalid_clip.append(shot.id)
        elif duration and clip.duration_seconds:
            diff_ratio = abs(clip.duration_seconds - duration) / max(duration, 0.001)
            if diff_ratio >= CLIP_DURATION_WARNING_RATIO:
                warnings.append(
                    models.VideoRenderWarning(
                        shot_id=shot.id,
                        code="VIDEO_RENDER_CLIP_DURATION_MISMATCH",
                        message=f"Shot {shot.shot_order:02d} có clip lệch thời lượng nhiều so với voice/timer.",
                    )
                )

    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id, DBVideoSubtitle.status == "completed").first()
    missing_subtitle = settings.subtitle_mode == "burn_in" and subtitle is None
    latest_job = latest_render_job(project_id, db)
    stale_output = bool(latest_job and latest_job.stale)
    reasons: list[str] = []
    if not shots:
        reasons.append("Project chưa có shot để dựng video.")
    if not tools.ffmpeg_ready:
        reasons.append("Chưa tìm thấy FFmpeg.")
    if not tools.ffprobe_ready:
        reasons.append("Chưa tìm thấy FFprobe.")
    subtitle_filter_ready = settings.subtitle_mode != "burn_in" or bool(tools.ffmpeg and _select_subtitle_filter(tools.ffmpeg))
    if settings.subtitle_mode == "burn_in" and tools.ffmpeg_ready and not subtitle_filter_ready:
        reasons.append("FFmpeg hiện tại chưa có filter burn-in phụ đề. Hãy dùng SRT rời hoặc cài FFmpeg có libass.")
    if missing_clip:
        reasons.append("Thiếu video clip cho một số shot.")
    if invalid_clip:
        reasons.append("Một số clip chưa đọc được hoặc chưa hợp lệ.")
    if missing_voice:
        reasons.append("Thiếu giọng đọc hoàn tất cho một số shot có narration.")
    if missing_timer:
        reasons.append("Một số shot thiếu thời lượng render.")
    if missing_subtitle:
        reasons.append("Chưa có phụ đề hoàn tất để burn vào video.")

    return models.VideoRenderReadinessResponse(
        project_id=project_id,
        ready=bool(shots)
        and tools.ffmpeg_ready
        and tools.ffprobe_ready
        and subtitle_filter_ready
        and not missing_clip
        and not invalid_clip
        and not missing_voice
        and not missing_timer
        and not missing_subtitle,
        ffmpeg_ready=tools.ffmpeg_ready,
        ffprobe_ready=tools.ffprobe_ready,
        missing_clip_shot_ids=missing_clip,
        invalid_clip_shot_ids=invalid_clip,
        missing_voice_shot_ids=missing_voice,
        missing_timer_shot_ids=missing_timer,
        missing_subtitle=missing_subtitle,
        stale_output=stale_output,
        missing_reasons=reasons,
        warnings=warnings,
    )


def latest_render_job(project_id: str, db: Session) -> DBVideoRenderJob | None:
    return db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id).order_by(DBVideoRenderJob.created_at.desc()).first()


def list_render_jobs(project_id: str, db: Session) -> list[models.VideoRenderJobResponse]:
    rows = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id).order_by(DBVideoRenderJob.created_at.desc()).all()
    return [_job_response(row) for row in rows]


def get_render_job(project_id: str, job_id: str, db: Session) -> models.VideoRenderJobResponse | None:
    row = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.id == job_id).first()
    return _job_response(row) if row else None


def get_latest_render_job(project_id: str, db: Session) -> models.VideoRenderJobResponse | None:
    row = latest_render_job(project_id, db)
    return _job_response(row) if row else None


def _create_render_job_sync(
    project_id: str,
    data: models.VideoRenderJobCreateRequest,
    db: Session,
    *,
    schedule_background: bool,
) -> models.VideoRenderJobResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    readiness = get_render_readiness(project_id, db, data.settings)
    if readiness is None:
        return None
    if not readiness.ready and not data.settings.force:
        reason = "; ".join(readiness.missing_reasons) or "Project chưa đủ điều kiện dựng MP4."
        raise VideoRenderError(reason, error_code="VIDEO_RENDER_NOT_READY")
    now = datetime.utcnow()
    db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.status == "completed").update(
        {"stale": True, "updated_at": now}, synchronize_session=False
    )
    row = DBVideoRenderJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        status="queued",
        progress=0.0,
        current_step="Đang chờ dựng video",
        settings_json=data.settings.model_dump_json(),
        readiness_json=readiness.model_dump_json(),
        stale=False,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if schedule_background:
        create_background_task(_run_render_job(row.id))
    return _job_response(row)


async def create_render_job(
    project_id: str,
    data: models.VideoRenderJobCreateRequest,
    db: Session,
) -> models.VideoRenderJobResponse | None:
    return _create_render_job_sync(project_id, data, db, schedule_background=True)


def create_render_job_for_auto_run(
    project_id: str,
    data: models.VideoRenderJobCreateRequest,
    db: Session,
) -> models.VideoRenderJobResponse | None:
    return _create_render_job_sync(project_id, data, db, schedule_background=False)


async def _run_render_job(job_id: str) -> None:
    async with _render_lock:
        await asyncio.to_thread(_run_render_job_sync, job_id)


def sync_stale_running_jobs(db: Session) -> int:
    now = datetime.utcnow()
    result = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.status.in_(["queued", "running"])).update(
        {
            "status": "failed",
            "failure_reason": "Render bị gián đoạn khi ứng dụng đóng.",
            "error_code": "VIDEO_RENDER_INTERRUPTED",
            "updated_at": now,
            "completed_at": now,
        },
        synchronize_session=False,
    )
    if result:
        db.commit()
    return int(result or 0)


def _run_render_job_sync(job_id: str) -> None:
    db = next(get_db())
    try:
        job = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.id == job_id).first()
        if job is None:
            return
        try:
            _render_job_steps(job, db)
        except Exception as exc:
            _fail_job(job, db, exc)
    finally:
        db.close()


def _normalized_clip_cache_dir(project_id: str) -> Path:
    path = video_storage.get_project_subdir(project_id, "render_cache") / "normalized"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _source_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }

def _normalized_clip_cache_key(
    *,
    input_path: Path,
    target_duration: float,
    clip_duration: float | None,
    width: int,
    height: int,
    fps: int,
    fit_mode: str,
    background_color: str,
    freeze_short_clip: bool,
) -> str:
    payload = {
        "version": _NORMALIZE_CACHE_VERSION,
        "source": _source_identity(input_path),
        "target_duration": round(float(target_duration), 3),
        "clip_duration": round(float(clip_duration), 3) if clip_duration is not None else None,
        "width": width,
        "height": height,
        "fps": fps,
        "fit_mode": fit_mode,
        "background_color": background_color,
        "freeze_short_clip": freeze_short_clip,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _normalize_clip_with_cache(
    *,
    project_id: str,
    ffmpeg: str,
    input_path: Path,
    target_duration: float,
    clip_duration: float | None,
    width: int,
    height: int,
    fps: int,
    fit_mode: str,
    background_color: str,
    freeze_short_clip: bool,
) -> tuple[Path, bool]:
    cache_key = _normalized_clip_cache_key(
        input_path=input_path,
        target_duration=target_duration,
        clip_duration=clip_duration,
        width=width,
        height=height,
        fps=fps,
        fit_mode=fit_mode,
        background_color=background_color,
        freeze_short_clip=freeze_short_clip,
    )
    cache_path = _normalized_clip_cache_dir(project_id) / f"{cache_key}.mp4"
    if cache_path.exists():
        return cache_path, True

    tmp_path = cache_path.with_suffix(f".{uuid.uuid4().hex}.tmp.mp4")
    cmd = build_normalize_clip_command(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=tmp_path,
        target_duration=target_duration,
        clip_duration=clip_duration,
        width=width,
        height=height,
        fps=fps,
        fit_mode=fit_mode,
        background_color=background_color,
        freeze_short_clip=freeze_short_clip,
    )
    try:
        _run_command(cmd, timeout=600)
        tmp_path.replace(cache_path)
        with suppress(Exception):
            prune_render_intermediate_cache(project_id=project_id)
    finally:
        tmp_path.unlink(missing_ok=True)
    return cache_path, False

def _render_job_steps(job: DBVideoRenderJob, db: Session) -> None:
    settings = models.VideoRenderSettings.model_validate_json(job.settings_json or "{}")
    tools = detect_tools()
    if not tools.ffmpeg_ready or not tools.ffprobe_ready:
        raise VideoRenderError("Chưa tìm thấy FFmpeg hoặc FFprobe.", error_code="VIDEO_RENDER_FFMPEG_MISSING")
    project = db.query(DBVideoProject).filter(DBVideoProject.id == job.project_id).first()
    if project is None:
        raise VideoRenderError("Không tìm thấy dự án video.", error_code="VIDEO_PROJECT_NOT_FOUND")
    readiness = get_render_readiness(project.id, db, settings)
    if readiness is None or (not readiness.ready and not settings.force):
        reason = "; ".join(readiness.missing_reasons if readiness else []) or "Project chưa đủ điều kiện dựng MP4."
        raise VideoRenderError(reason, error_code="VIDEO_RENDER_NOT_READY")
    shots = _ordered_shots(project.id, db)
    clips = _active_clips(project.id, db)
    timeline = build_timeline_manifest(project.id, db)
    if not timeline:
        raise VideoRenderError("Project chưa có timeline hợp lệ để render.", error_code="VIDEO_RENDER_EMPTY_TIMELINE")

    output_dir = video_storage.get_project_subdir(project.id, "render_outputs") / job.id
    intermediate_dir = video_storage.get_project_subdir(project.id, "render_intermediates") / job.id
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "timeline-manifest.json"
    manifest_payload = {
        "project_id": project.id,
        "project_title": project.title,
        "settings": settings.model_dump(),
        "sound_design_note": "SFX/BGM trong manifest là chỉ dẫn dựng nếu chưa có audio asset thật được mix vào MP4.",
        "timeline": [item.model_dump() for item in timeline],
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    job.timeline_manifest_path = video_storage.to_artifact_storage_path(manifest_path)
    _update_job(job, db, status="running", progress=0.05, current_step="Đang chuẩn bị timeline", started=True)

    resolution = _resolve_resolution(project.aspect_ratio, settings.resolution)
    normalized_paths: list[Path] = []
    render_cache_summary = {"normalized_hits": 0, "normalized_misses": 0}
    shots_by_id = {shot.id: shot for shot in shots}
    for index, item in enumerate(timeline, start=1):
        shot = shots_by_id[item.shot_id]
        clip = clips.get(shot.id)
        if clip is None:
            raise VideoRenderError("Thiếu clip video cho timeline.", error_code="VIDEO_RENDER_CLIP_MISSING")
        clip_path = video_storage.resolve_artifact_storage_path(clip.file_path)
        if clip_path is None or not clip_path.exists():
            raise VideoRenderError("File clip video không còn tồn tại.", error_code="VIDEO_RENDER_CLIP_FILE_MISSING")
        normalized_path, cache_hit = _normalize_clip_with_cache(
            project_id=project.id,
            ffmpeg=tools.ffmpeg or "ffmpeg",
            input_path=clip_path,
            target_duration=item.duration_seconds,
            clip_duration=clip.duration_seconds,
            width=resolution[0],
            height=resolution[1],
            fps=settings.fps,
            fit_mode=settings.fit_mode,
            background_color=settings.background_color,
            freeze_short_clip=settings.duration_mode == "freeze",
        )
        if cache_hit:
            render_cache_summary["normalized_hits"] += 1
        else:
            render_cache_summary["normalized_misses"] += 1
        normalized_paths.append(normalized_path)
        _update_job(job, db, progress=0.1 + (0.45 * index / max(1, len(timeline))), current_step=f"Đang chuẩn hóa clip {index}/{len(timeline)}")

    video_concat = intermediate_dir / "video-concat.mp4"
    _concat_media(tools.ffmpeg or "ffmpeg", normalized_paths, video_concat, stream_copy=True)
    _update_job(job, db, progress=0.6, current_step="Đang ghép video")

    audio_segments = _build_audio_segments(tools.ffmpeg or "ffmpeg", timeline, shots_by_id, intermediate_dir)
    audio_concat = intermediate_dir / "audio.wav"
    _concat_media(tools.ffmpeg or "ffmpeg", audio_segments, audio_concat, stream_copy=False, audio=True)
    _update_job(job, db, progress=0.75, current_step="Đang ghép voice")
    (output_dir / "render-cache-summary.json").write_text(
        json.dumps(render_cache_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    subtitle_ass_path: Path | None = None
    subtitle_filter: str | None = None
    if settings.subtitle_mode == "burn_in":
        subtitle_filter = _select_subtitle_filter(tools.ffmpeg or "ffmpeg")
        if subtitle_filter is None:
            raise VideoRenderError(
                "FFmpeg hiện tại chưa hỗ trợ burn-in phụ đề. Hãy thử chế độ SRT rời hoặc cài FFmpeg có libass.",
                error_code="VIDEO_RENDER_SUBTITLE_FILTER_MISSING",
            )
        subtitle_ass_path = intermediate_dir / "subtitles.ass"
        _write_ass_subtitle(project.id, subtitle_ass_path, db, resolution)
        job.subtitle_ass_path = video_storage.to_artifact_storage_path(subtitle_ass_path)

    output_path = output_dir / "final.mp4"
    final_cmd = build_final_mux_command(
        ffmpeg=tools.ffmpeg or "ffmpeg",
        video_path=video_concat,
        audio_path=audio_concat,
        output_path=output_path,
        subtitle_ass_path=subtitle_ass_path,
        subtitle_filter=subtitle_filter or "subtitles",
    )
    try:
        _run_command(final_cmd, timeout=1200)
    except VideoRenderError as exc:
        if settings.subtitle_mode == "burn_in":
            raise VideoRenderError(
                "Không burn được phụ đề vào video. Hãy thử chế độ SRT rời hoặc kiểm tra FFmpeg có libass.",
                error_code="VIDEO_RENDER_SUBTITLE_BURN_IN_FAILED",
            ) from (exc.__cause__ or exc)
        raise
    job.status = "completed"
    job.progress = 1.0
    job.current_step = "Đã dựng xong MP4"
    job.output_path = video_storage.to_artifact_storage_path(output_path)
    job.failure_reason = None
    job.error_code = None
    job.completed_at = datetime.utcnow()
    job.updated_at = job.completed_at
    db.commit()
    try:
        video_series_memory.record_rendered_episode(project.id, db)
    except Exception as exc:
        db.rollback()
        video_observability.log_event(
            db,
            step_name="series_memory_update",
            status="warning",
            project_id=project.id,
            error_code="AI_VIDEO_SERIES_MEMORY_UPDATE_FAILED",
            exc=exc,
            message="Render đã hoàn tất nhưng không cập nhật được file series-memory.md.",
            technical_details={"series_id": project.series_id, "render_job_id": job.id},
        )


def _fail_job(job: DBVideoRenderJob, db: Session, exc: Exception) -> None:
    now = datetime.utcnow()
    job.status = "failed"
    job.progress = min(float(job.progress or 0), 0.99)
    job.current_step = "Dựng MP4 thất bại"
    job.failure_reason = str(exc) or "Không dựng được MP4."
    job.error_code = exc.error_code if isinstance(exc, VideoRenderError) else "VIDEO_RENDER_FAILED"
    cause = getattr(exc, "__cause__", None)
    job.technical_details = _truncate_stderr(str(cause)) if cause else None
    job.completed_at = now
    job.updated_at = now
    db.commit()


def _update_job(
    job: DBVideoRenderJob,
    db: Session,
    *,
    status: str | None = None,
    progress: float | None = None,
    current_step: str | None = None,
    started: bool = False,
) -> None:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = max(0.0, min(1.0, progress))
    if current_step is not None:
        job.current_step = current_step
    if started and job.started_at is None:
        job.started_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    db.commit()


def _resolve_resolution(aspect_ratio: str, preset: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return (1280, 720) if preset == "720p" else (1920, 1080)
    if aspect_ratio == "1:1":
        return (720, 720) if preset == "720p" else (1080, 1080)
    return (720, 1280) if preset == "720p" else (1080, 1920)


def build_normalize_clip_command(
    *,
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    target_duration: float,
    clip_duration: float | None,
    width: int,
    height: int,
    fps: int,
    fit_mode: str,
    background_color: str,
    freeze_short_clip: bool = True,
) -> list[str]:
    shortage = max(0.0, target_duration - float(clip_duration or 0))
    if fit_mode == "pad":
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={background_color}"
    else:
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    filters = [
        scale_filter,
        f"fps={fps}",
        "format=yuv420p",
        "setsar=1",
    ]
    if shortage > 0 and freeze_short_clip:
        filters.append(f"tpad=stop_mode=clone:stop_duration={shortage:.3f}")
    filters.extend([f"trim=duration={target_duration:.3f}", "setpts=PTS-STARTPTS"])
    return [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-an",
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _concat_media(ffmpeg: str, inputs: list[Path], output_path: Path, *, stream_copy: bool, audio: bool = False) -> None:
    list_path = output_path.with_suffix(".txt")
    list_path.write_text("".join(f"file '{_escape_concat_path(path)}'\n" for path in inputs), encoding="utf-8")
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    if stream_copy:
        cmd.extend(["-c", "copy"])
    elif audio:
        cmd.extend(["-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le"])
    cmd.append(str(output_path))
    _run_command(cmd, timeout=900)


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def get_render_intermediate_cache_stats() -> dict[str, Any]:
    """Return global AI Video render cache size."""
    root = video_storage.get_video_projects_dir()
    files = 0
    total_bytes = 0
    for path in root.glob("*/render_cache/**/*"):
        if not path.is_file():
            continue
        files += 1
        with suppress(OSError):
            total_bytes += path.stat().st_size
    return {
        "available": True,
        "files": files,
        "bytes": total_bytes,
        "size_mb": round(total_bytes / 1024 / 1024, 2),
        "max_mb": _render_cache_max_mb(),
        "max_age_days": _render_cache_max_age_days(),
    }

def _render_cache_max_mb() -> int:
    try:
        return max(0, int(os.environ.get(RENDER_CACHE_MAX_MB_ENV, "4096")))
    except ValueError:
        return 4096

def _render_cache_max_age_days() -> int:
    try:
        return max(0, int(os.environ.get(RENDER_CACHE_MAX_AGE_DAYS_ENV, "14")))
    except ValueError:
        return 14

def _render_cache_roots(project_id: str | None) -> list[Path]:
    if project_id:
        return [video_storage.get_project_subdir(project_id, "render_cache")]
    projects_root = video_storage.get_video_projects_dir()
    return [path / "render_cache" for path in projects_root.iterdir() if (path / "render_cache").exists()]

def _remove_empty_cache_dirs(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if not path.is_dir():
            continue
        with suppress(OSError):
            path.rmdir()

def prune_render_intermediate_cache(
    project_id: str | None = None,
    *,
    max_age_days: int | None = None,
    max_mb: int | None = None,
) -> dict[str, Any]:
    """Prune persistent render cache by configured age and quota."""
    roots = _render_cache_roots(project_id)
    age_days = _render_cache_max_age_days() if max_age_days is None else max(0, int(max_age_days))
    quota_mb = _render_cache_max_mb() if max_mb is None else max(0, int(max_mb))
    quota_bytes = quota_mb * 1024 * 1024 if quota_mb > 0 else None
    cutoff = datetime.utcnow().timestamp() - (age_days * 86400) if age_days > 0 else None

    files: list[tuple[Path, int, float]] = []
    files_deleted = 0
    bytes_deleted = 0
    deleted_by_age = 0

    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if cutoff is not None and stat.st_mtime < cutoff:
                try:
                    path.unlink()
                    files_deleted += 1
                    bytes_deleted += stat.st_size
                    deleted_by_age += 1
                except OSError:
                    pass
                continue
            files.append((path, stat.st_size, stat.st_mtime))

    total_bytes = sum(size for _path, size, _mtime in files)
    deleted_by_quota = 0
    if quota_bytes is not None and total_bytes > quota_bytes:
        for path, size, _mtime in sorted(files, key=lambda item: item[2]):
            if total_bytes <= quota_bytes:
                break
            try:
                path.unlink()
            except OSError:
                continue
            total_bytes -= size
            files_deleted += 1
            bytes_deleted += size
            deleted_by_quota += 1

    for root in roots:
        if root.exists():
            _remove_empty_cache_dirs(root)

    return {
        "files_deleted": files_deleted,
        "bytes_deleted": bytes_deleted,
        "project_id": project_id,
        "max_age_days": age_days,
        "max_mb": quota_mb,
        "deleted_by_age": deleted_by_age,
        "deleted_by_quota": deleted_by_quota,
    }

def clear_render_intermediate_cache(project_id: str | None = None, db: Session | None = None) -> dict[str, Any]:
    """Clear persistent render intermediate cache globally or for one project."""
    roots = _render_cache_roots(project_id)

    files_deleted = 0
    bytes_deleted = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                try:
                    bytes_deleted += path.stat().st_size
                    path.unlink()
                    files_deleted += 1
                except OSError:
                    pass
            elif path.is_dir():
                with suppress(OSError):
                    path.rmdir()
        root.mkdir(parents=True, exist_ok=True)
    return {
        "files_deleted": files_deleted,
        "bytes_deleted": bytes_deleted,
        "project_id": project_id,
    }

def _build_audio_segments(ffmpeg: str, timeline: list[models.VideoRenderTimelineShot], shots_by_id: dict[str, DBVideoShot], output_dir: Path) -> list[Path]:
    segments: list[Path] = []
    for index, item in enumerate(timeline, start=1):
        shot = shots_by_id[item.shot_id]
        out_path = output_dir / f"audio-{index:03d}.wav"
        audio_path = video_storage.resolve_artifact_storage_path(shot.audio_path)
        if item.has_narration and audio_path is not None and audio_path.exists():
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(audio_path),
                "-af",
                f"apad,atrim=duration={item.duration_seconds:.3f}",
                "-ac",
                "2",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                str(out_path),
            ]
        else:
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t",
                f"{item.duration_seconds:.3f}",
                "-c:a",
                "pcm_s16le",
                str(out_path),
            ]
        _run_command(cmd, timeout=300)
        segments.append(out_path)
    return segments


def _write_ass_subtitle(project_id: str, path: Path, db: Session, resolution: tuple[int, int]) -> None:
    subtitle = db.query(DBVideoSubtitle).filter(DBVideoSubtitle.project_id == project_id, DBVideoSubtitle.status == "completed").first()
    if subtitle is None or not subtitle.cues_json:
        raise VideoRenderError("Chưa có phụ đề hoàn tất để burn vào video.", error_code="VIDEO_RENDER_SUBTITLE_MISSING")
    cues = json.loads(subtitle.cues_json)
    style = _ass_caption_style(resolution)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {resolution[0]}",
        f"PlayResY: {resolution[1]}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{style['font_name']},{style['font_size']},{style['primary']},{style['secondary']},{style['outline_colour']},{style['back_colour']},-1,0,0,0,100,100,0.2,0,1,{style['outline']},{style['shadow']},2,{style['margin_h']},{style['margin_h']},{style['margin_v']},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        text = _ass_karaoke_text(cue, max_line_chars=int(style["max_line_chars"]))
        lines.append(f"Dialogue: 0,{_ass_ts(float(cue.get('start_seconds') or 0))},{_ass_ts(float(cue.get('end_seconds') or 0))},Default,,0,0,0,,{{\\fad(110,110)\\blur0.35}}{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ass_caption_style(resolution: tuple[int, int]) -> dict[str, str | int]:
    width, height = resolution
    short_edge = min(width, height)
    vertical = height > width
    square = width == height
    if vertical:
        font_size = round(width * 0.045)
        margin_v = round(height * 0.075)
        margin_h = round(width * 0.08)
        max_line_chars = 30
    elif square:
        font_size = round(short_edge * 0.047)
        margin_v = round(height * 0.08)
        margin_h = round(width * 0.08)
        max_line_chars = 38
    else:
        font_size = round(short_edge * 0.052)
        margin_v = round(height * 0.074)
        margin_h = round(width * 0.07)
        max_line_chars = 52
    outline = max(4, round(font_size * 0.12))
    shadow = max(1, round(font_size * 0.035))
    return {
        "font_name": "Arial",
        "font_size": font_size,
        "primary": "&H0007D7F7",
        "secondary": "&H00FCFAF8",
        "outline_colour": "&HA0271811",
        "back_colour": "&H8F171411",
        "outline": outline,
        "shadow": shadow,
        "margin_h": margin_h,
        "margin_v": margin_v,
        "max_line_chars": max_line_chars,
    }

def _ass_karaoke_text(cue: dict[str, Any], *, max_line_chars: int | None = None) -> str:
    raw_text = str(cue.get("text") or "")
    words = raw_text.split()
    if not words:
        return ""
    start = float(cue.get("start_seconds") or 0)
    end = float(cue.get("end_seconds") or start)
    total_cs = max(1, round(max(0.01, end - start) * 100))
    durations = _karaoke_word_durations(words, total_cs)
    parts = []
    line_len = 0
    for index, (word, duration) in enumerate(zip(words, durations, strict=True)):
        if not index:
            spacer = ""
            line_len = len(word)
        elif max_line_chars and line_len and line_len + 1 + len(word) > max_line_chars:
            spacer = r"\N"
            line_len = len(word)
        else:
            spacer = r"\h"
            line_len += 1 + len(word)
        parts.append(f"{spacer}{{\\k{duration}}}{_ass_escape(word)}")
    return "".join(parts)

def _karaoke_word_durations(words: list[str], total_cs: int) -> list[int]:
    weights = [max(1, len(word.strip())) for word in words]
    total_weight = sum(weights)
    durations = [max(1, round(total_cs * weight / total_weight)) for weight in weights]
    drift = total_cs - sum(durations)
    index = 0
    while drift:
        step = 1 if drift > 0 else -1
        if durations[index] + step >= 1:
            durations[index] += step
            drift -= step
        index = (index + 1) % len(durations)
    return durations

def _ass_escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", r"\N")


def _ass_ts(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    hours = total_cs // 360000
    total_cs %= 360000
    minutes = total_cs // 6000
    total_cs %= 6000
    secs = total_cs // 100
    centis = total_cs % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def build_final_mux_command(
    *,
    ffmpeg: str,
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    subtitle_ass_path: Path | None = None,
    subtitle_filter: str = "subtitles",
) -> list[str]:
    cmd = [ffmpeg, "-y", "-i", str(video_path), "-i", str(audio_path)]
    if subtitle_ass_path is not None:
        cmd.extend(["-vf", f"{subtitle_filter}=filename='{_filter_path(subtitle_ass_path)}'", "-c:v", "libx264", "-preset", "veryfast"])
    else:
        cmd.extend(["-c:v", "copy"])
    cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(output_path)])
    return cmd


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def get_render_download(project_id: str, job_id: str, db: Session) -> tuple[str, Path] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    job = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.id == job_id).first()
    if project is None or job is None or job.status != "completed" or not job.output_path:
        return None
    path = video_storage.resolve_artifact_storage_path(job.output_path)
    if path is None or not path.exists():
        return None
    return video_storage.render_output_filename(project.title), path
