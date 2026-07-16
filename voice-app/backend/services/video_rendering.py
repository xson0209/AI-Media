"""Timeline MP4 rendering for AI Video Assistant phase 2."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import unicodedata
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..database import (
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSubtitle as DBVideoSubtitle,
    get_db,
)
from . import video_observability, video_series_memory, video_storage
from .task_queue import create_background_task

MAX_CLIP_SIZE_BYTES = 700 * 1024 * 1024
MAX_CLIP_DURATION_SECONDS = 120.0
MAX_SFX_SIZE_BYTES = 80 * 1024 * 1024
MAX_SFX_DURATION_SECONDS = 120.0
CLIP_DURATION_WARNING_RATIO = 0.35
_STDERR_LIMIT = 4000
_NORMALIZE_CACHE_VERSION = "normalize-v1"
RENDER_CACHE_MAX_MB_ENV = "VOICEBOX_RENDER_CACHE_MAX_MB"
RENDER_CACHE_MAX_AGE_DAYS_ENV = "VOICEBOX_RENDER_CACHE_MAX_AGE_DAYS"
_render_lock = asyncio.Lock()
_SFX_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
_ENHANCED_ARTIFACTS = (
    ("script_retention", 1, "Kịch bản và nhịp giữ chân", ".md"),
    ("shot_transitions", 2, "Shot list và chuyển cảnh", ".csv"),
    ("video_prompts_effects", 3, "Prompt video và chỉ dẫn hiệu ứng", ".md"),
    ("sfx_mixing_notes", 4, "Âm thanh SFX và mixing notes", ".md"),
    ("ai_review_report", 5, "Báo cáo AI review sau render", ".md"),
    ("timeline_manifest", 6, "Timeline manifest dựng MP4", ".json"),
)
_EDGE_FADE_TRANSITIONS = {"crossfade", "dip_to_black", "dip_to_white", "flash"}
_SAFE_HARD_CUT_TRANSITIONS = {"hard_cut", "match_cut"}


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


@dataclass(frozen=True)
class AudioMetadata:
    duration_seconds: float | None
    codec: str | None

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
    if binary == "ffmpeg":
        candidates.append(_imageio_ffmpeg_candidate())
    for prefix in ("/opt/homebrew", "/usr/local"):
        candidates.append(f"{prefix}/opt/ffmpeg-full/bin/{binary}")
    return [candidate for candidate in candidates if candidate]

def _imageio_ffmpeg_candidate() -> str | None:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception:
        return None
    try:
        candidate = get_ffmpeg_exe()
    except Exception:
        return None
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    return str(path) if path.exists() else None

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
    selected_path = Path(selected_tool)
    candidates = [selected_path.with_name(sibling_binary)]
    if selected_path.suffix:
        candidates.insert(0, selected_path.with_name(f"{sibling_binary}{selected_path.suffix}"))
    if os.name == "nt":
        candidates.append(selected_path.with_name(f"{sibling_binary}.exe"))
    return _first_existing_tool([str(candidate) for candidate in candidates])

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


def _duration_from_ffmpeg_text(text: str) -> float | None:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

def _ffmpeg_probe_text(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return "\n".join(part for part in (result.stderr, result.stdout) if part)

def _probe_clip_with_ffmpeg(path: Path, ffmpeg: str) -> ClipMetadata:
    text = _ffmpeg_probe_text(path, ffmpeg)
    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    if not video_line:
        raise VideoRenderError(
            "Không đọc được metadata video. Hãy kiểm tra lại file clip.",
            error_code="VIDEO_RENDER_CLIP_INVALID",
        ) from RuntimeError(_truncate_stderr(text) or "ffmpeg probe failed")
    size_match = re.search(r"(?<![\w])(\d{2,5})x(\d{2,5})(?![\w])", video_line)
    codec_match = re.search(r"Video:\s*([^,\s]+)", video_line)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", video_line)
    return ClipMetadata(
        duration_seconds=_duration_from_ffmpeg_text(text),
        width=int(size_match.group(1)) if size_match else None,
        height=int(size_match.group(2)) if size_match else None,
        fps=float(fps_match.group(1)) if fps_match else None,
        codec=codec_match.group(1) if codec_match else None,
        has_audio=any("Audio:" in line for line in text.splitlines()),
    )

def probe_clip(path: Path, *, ffprobe_path: str | None = None, ffmpeg_path: str | None = None) -> ClipMetadata:
    """Read clip metadata via ffprobe, falling back to ffmpeg's input banner."""
    ffprobe = ffprobe_path
    ffmpeg = ffmpeg_path
    if ffprobe is None:
        tools = detect_tools()
        ffprobe = tools.ffprobe
        ffmpeg = ffmpeg or tools.ffmpeg
    if not ffprobe:
        if ffmpeg:
            return _probe_clip_with_ffmpeg(path, ffmpeg)
        raise VideoRenderError(
            "Chưa tìm thấy FFprobe hoặc FFmpeg. Hãy cài FFmpeg hoặc cấu hình đường dẫn FFmpeg trước khi upload clip.",
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

def _probe_audio_with_ffmpeg(path: Path, ffmpeg: str) -> AudioMetadata:
    text = _ffmpeg_probe_text(path, ffmpeg)
    audio_line = next((line for line in text.splitlines() if "Audio:" in line), "")
    if not audio_line:
        raise VideoRenderError(
            "Không đọc được metadata audio. Hãy kiểm tra lại file SFX/BGM.",
            error_code="VIDEO_RENDER_SFX_INVALID",
        ) from RuntimeError(_truncate_stderr(text) or "ffmpeg probe failed")
    codec_match = re.search(r"Audio:\s*([^,\s]+)", audio_line)
    return AudioMetadata(duration_seconds=_duration_from_ffmpeg_text(text), codec=codec_match.group(1) if codec_match else None)

def probe_audio_asset(path: Path, *, ffprobe_path: str | None = None, ffmpeg_path: str | None = None) -> AudioMetadata:
    """Read SFX/BGM audio metadata via ffprobe, falling back to ffmpeg's input banner."""
    ffprobe = ffprobe_path
    ffmpeg = ffmpeg_path
    if ffprobe is None:
        tools = detect_tools()
        ffprobe = tools.ffprobe
        ffmpeg = ffmpeg or tools.ffmpeg
    if not ffprobe:
        if ffmpeg:
            return _probe_audio_with_ffmpeg(path, ffmpeg)
        raise VideoRenderError(
            "Chưa tìm thấy FFprobe để kiểm tra asset âm thanh.",
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
            "Không đọc được metadata audio. Hãy kiểm tra lại file SFX/BGM.",
            error_code="VIDEO_RENDER_SFX_INVALID",
        ) from RuntimeError(_truncate_stderr(result.stderr) or "ffprobe failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoRenderError("Metadata audio không hợp lệ.", error_code="VIDEO_RENDER_SFX_INVALID") from exc

    streams = payload.get("streams") or []
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not audio_stream:
        raise VideoRenderError("File SFX/BGM không có audio stream hợp lệ.", error_code="VIDEO_RENDER_SFX_INVALID")
    duration = _float_or_none(audio_stream.get("duration")) or _float_or_none((payload.get("format") or {}).get("duration"))
    return AudioMetadata(duration_seconds=duration, codec=audio_stream.get("codec_name"))


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


def get_active_clip_download(project_id: str, shot_id: str, db: Session) -> tuple[str, Path, str] | None:
    clip = (
        db.query(DBVideoShotClip)
        .filter(DBVideoShotClip.project_id == project_id, DBVideoShotClip.shot_id == shot_id, DBVideoShotClip.is_active.is_(True))
        .order_by(DBVideoShotClip.created_at.desc())
        .first()
    )
    if clip is None:
        return None
    if clip.status != "ready":
        return None
    path = video_storage.resolve_artifact_storage_path(clip.file_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    filename = video_storage.sanitize_download_filename(
        clip.original_filename or path.name,
        fallback=f"clip-{shot_id}{path.suffix or '.mp4'}",
    )
    media_type = clip.mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return filename, path, media_type


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


def _normalize_alias_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.lower().replace("_", " ").replace("-", " ")

def _infer_sfx_aliases(filename: str | None, extra_text: str | None = None) -> list[str]:
    text = _normalize_alias_text(f"{filename or ''} {extra_text or ''}")
    aliases: list[str] = []
    checks = [
        ("glass_break", ("glass", "kinh", "vo", "broken", "break", "shatter")),
        ("broken_glass", ("glass", "kinh", "broken", "shatter")),
        ("whoosh", ("whoosh", "swoosh", "whip", "vuot", "gio")),
        ("impact", ("impact", "hit", "slam", "boom", "dap", "va cham")),
        ("riser", ("riser", "rise", "build", "swell", "cao trao")),
        ("silence_drop", ("silence", "drop", "pause", "im lang", "lang")),
        ("bgm", ("bgm", "music", "nhac", "beat", "bed")),
    ]
    for alias, keywords in checks:
        if any(keyword in text for keyword in keywords):
            aliases.append(alias)
    if not aliases and filename:
        stem = Path(filename).stem.strip().lower().replace(" ", "_")
        if stem:
            aliases.append(stem[:64])
    return list(dict.fromkeys(aliases))

def _sfx_sidecar_path(asset_path: Path) -> Path:
    return asset_path.with_suffix(f"{asset_path.suffix}.json")

def _sfx_payload_to_response(payload: dict[str, Any]) -> models.VideoRenderSfxAssetResponse:
    return models.VideoRenderSfxAssetResponse(
        asset_id=str(payload.get("asset_id") or ""),
        filename=str(payload.get("filename") or payload.get("asset_id") or "sfx"),
        file_path=str(payload.get("file_path") or ""),
        mime_type=payload.get("mime_type"),
        size_bytes=payload.get("size_bytes"),
        duration_seconds=payload.get("duration_seconds"),
        cue_aliases=list(payload.get("cue_aliases") or []),
        status=str(payload.get("status") or "ready"),
        failure_reason=payload.get("failure_reason"),
    )

def list_render_sfx_assets(project_id: str, db: Session) -> list[models.VideoRenderSfxAssetResponse] | None:
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        return None
    asset_dir = video_storage.get_project_subdir(project_id, "sfx_assets")
    assets: list[models.VideoRenderSfxAssetResponse] = []
    for sidecar in sorted(asset_dir.glob("*.json")):
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        response = _sfx_payload_to_response(payload)
        asset_path = video_storage.resolve_artifact_storage_path(response.file_path)
        if asset_path is None or not asset_path.exists():
            response.status = "missing"
            response.failure_reason = "File asset không còn tồn tại."
        assets.append(response)
    return assets

def upload_render_sfx_asset(
    project_id: str,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    db: Session,
) -> models.VideoRenderSfxAssetResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if getattr(project, "phase", "phase1") != "phase2":
        raise VideoRenderError("Chỉ project AI Video phase 2 mới hỗ trợ asset SFX/BGM.", error_code="VIDEO_RENDER_PHASE_REQUIRED")
    if not data:
        raise VideoRenderError("File SFX/BGM rỗng.", error_code="VIDEO_RENDER_SFX_EMPTY")
    if len(data) > MAX_SFX_SIZE_BYTES:
        raise VideoRenderError("File SFX/BGM quá lớn. Hãy dùng asset ngắn hơn hoặc nén file trước khi upload.", error_code="VIDEO_RENDER_SFX_TOO_LARGE")

    suffix = Path(filename or "sfx.wav").suffix.lower() or mimetypes.guess_extension(content_type or "") or ".wav"
    if suffix not in _SFX_AUDIO_SUFFIXES:
        raise VideoRenderError("Định dạng SFX/BGM chưa được hỗ trợ. Hãy dùng WAV, MP3, M4A, AAC, OGG hoặc FLAC.", error_code="VIDEO_RENDER_SFX_UNSUPPORTED")

    asset_id = str(uuid.uuid4())
    asset_dir = video_storage.get_project_subdir(project_id, "sfx_assets")
    asset_path = asset_dir / f"sfx-{asset_id}{suffix}"
    asset_path.write_bytes(data)
    payload: dict[str, Any] = {
        "asset_id": asset_id,
        "filename": video_storage.sanitize_download_filename(filename or f"sfx{suffix}"),
        "file_path": video_storage.to_artifact_storage_path(asset_path),
        "mime_type": content_type or mimetypes.guess_type(filename or "")[0],
        "size_bytes": len(data),
        "cue_aliases": _infer_sfx_aliases(filename),
        "status": "ready",
        "failure_reason": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        metadata = probe_audio_asset(asset_path)
        if metadata.duration_seconds and metadata.duration_seconds > MAX_SFX_DURATION_SECONDS:
            raise VideoRenderError("Asset SFX/BGM quá dài cho workflow dựng nhanh.", error_code="VIDEO_RENDER_SFX_TOO_LONG")
        payload["duration_seconds"] = metadata.duration_seconds
        payload["codec"] = metadata.codec
    except VideoRenderError as exc:
        payload["status"] = "failed"
        payload["failure_reason"] = str(exc)
    _sfx_sidecar_path(asset_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _mark_render_outputs_stale(project_id, db)
    db.commit()
    return _sfx_payload_to_response(payload)

def delete_render_sfx_asset(project_id: str, asset_id: str, db: Session) -> bool | None:
    project_exists = db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first()
    if project_exists is None:
        return None
    assets = list_render_sfx_assets(project_id, db) or []
    asset = next((item for item in assets if item.asset_id == asset_id), None)
    if asset is None:
        return False
    path = video_storage.resolve_artifact_storage_path(asset.file_path)
    if path is not None:
        sidecar = _sfx_sidecar_path(path)
        if sidecar.exists():
            sidecar.unlink()
        video_storage.remove_artifact_file(path)
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


def _timeline_total_duration(timeline: list[models.VideoRenderTimelineShot]) -> float:
    return round(max((item.end_seconds for item in timeline), default=0.0), 3)

def _asset_alias_index(assets: list[models.VideoRenderSfxAssetResponse]) -> dict[str, models.VideoRenderSfxAssetResponse]:
    index: dict[str, models.VideoRenderSfxAssetResponse] = {}
    for asset in assets:
        if asset.status != "ready":
            continue
        for alias in asset.cue_aliases or []:
            normalized = _normalize_sfx_alias(alias, alias)
            index.setdefault(normalized, asset)
            if normalized in {"glass_break", "broken_glass"}:
                index.setdefault("glass_break", asset)
                index.setdefault("broken_glass", asset)
    return index

def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

def _nested_transition(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("transition_pack")
    return nested if isinstance(nested, dict) else value

def _normalize_transition_alias(value: Any, continuity_risk: str | None = None) -> str:
    text = _normalize_alias_text(str(value or ""))
    risk = _normalize_alias_text(continuity_risk)
    if any(token in risk for token in ("high", "cao", "risk cao", "nhay cam")):
        return "match_cut"
    if "white" in text or "trang" in text:
        return "dip_to_white" if "dip" in text or "fade" in text else "flash"
    if "black" in text or "den" in text:
        return "dip_to_black"
    if "cross" in text or "fade" in text:
        return "crossfade"
    if "match" in text:
        return "match_cut"
    if "whip" in text or "pan" in text:
        return "whip_pan"
    if "glitch" in text:
        return "glitch"
    if "flash" in text:
        return "flash"
    if "zoom" in text or "punch" in text:
        return "punch_zoom"
    return "hard_cut"

def _transition_render_mode(alias: str) -> tuple[str, bool, str | None]:
    if alias in _SAFE_HARD_CUT_TRANSITIONS:
        return "hard_cut", True, None
    if alias in _EDGE_FADE_TRANSITIONS:
        return "edge_fade", True, None
    return "hard_cut", False, f"Transition `{alias}` chưa có filter an toàn trong runtime này nên fallback về hard cut."

def _normalize_sfx_alias(cue_type: Any, label: Any = None) -> str:
    text = f"{cue_type or ''} {label or ''}"
    aliases = _infer_sfx_aliases(text)
    priority = ["glass_break", "broken_glass", "whoosh", "impact", "riser", "silence_drop", "bgm"]
    for alias in priority:
        if alias in aliases:
            return "glass_break" if alias == "broken_glass" else alias
    clean = _normalize_alias_text(str(cue_type or label or "sfx")).strip().replace(" ", "_")
    return clean[:64] or "sfx"

def _cue_start_seconds(item: models.VideoRenderTimelineShot, cue: dict[str, Any], alias: str, total_duration: float) -> float:
    text = _normalize_alias_text(" ".join(str(cue.get(key) or "") for key in ("timing", "purpose", "cue_label")))
    if "start" in text or "hook" in text or "mo dau" in text:
        start = item.start_seconds + 0.15
    elif "before" in text or "truoc" in text or alias == "riser":
        start = item.end_seconds - min(0.7, max(0.15, item.duration_seconds * 0.35))
    elif "transition" in text or "cut" in text or "reveal" in text or "payoff" in text:
        start = item.end_seconds - 0.18
    else:
        start = item.start_seconds + min(item.duration_seconds * 0.5, max(0.15, item.duration_seconds - 0.15))
    return round(max(0.0, min(start, max(0.0, total_duration - 0.05))), 3)

def _sound_cues_for_item(item: models.VideoRenderTimelineShot) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    sound = item.sound_design or {}
    if isinstance(sound, dict):
        raw_cues = sound.get("sound_cues")
        if isinstance(raw_cues, list):
            for raw in raw_cues:
                if isinstance(raw, dict):
                    cues.append(dict(raw))
                elif raw:
                    cues.append({"cue_type": str(raw)})
        raw_drops = sound.get("silence_drops")
        if isinstance(raw_drops, list):
            for drop in raw_drops:
                cues.append({"cue_type": "silence_drop", "timing": str(drop), "purpose": "pattern interrupt"})
        elif isinstance(raw_drops, str) and raw_drops.strip():
            cues.append({"cue_type": "silence_drop", "timing": raw_drops, "purpose": "pattern interrupt"})
    transition = _nested_transition(item.transition)
    transition_sfx = _first_text(transition.get("transition_sfx"), transition.get("sfx"), transition.get("sound_effect"))
    if transition_sfx:
        cues.append({"cue_type": transition_sfx, "timing": "on transition", "purpose": "accent transition"})
    return cues

def _sfx_duration(alias: str, asset: models.VideoRenderSfxAssetResponse | None) -> float:
    if asset and asset.duration_seconds:
        return round(max(0.08, min(float(asset.duration_seconds), 4.0)), 3)
    defaults = {
        "glass_break": 0.9,
        "whoosh": 0.45,
        "impact": 0.55,
        "riser": 0.9,
        "silence_drop": 0.35,
        "bgm": 0.0,
    }
    return defaults.get(alias, 0.6)

def _missing_sfx_message(alias: str) -> str:
    labels = {
        "glass_break": "tiếng kính vỡ",
        "whoosh": "whoosh chuyển cảnh",
        "impact": "impact",
        "riser": "riser",
        "silence_drop": "silence drop",
        "bgm": "nhạc nền",
    }
    label = labels.get(alias, alias)
    return f"Thiếu asset {label}; MP4 không được báo là đã có SFX thật cho cue này."

def build_enhanced_render_plan(
    project: DBVideoProject,
    timeline: list[models.VideoRenderTimelineShot],
    shots_by_id: dict[str, DBVideoShot],
    assets: list[models.VideoRenderSfxAssetResponse],
    settings: models.VideoRenderSettings,
) -> dict[str, Any]:
    total_duration = _timeline_total_duration(timeline)
    asset_index = _asset_alias_index(assets)
    transitions: list[models.VideoEnhancedTransitionAction] = []
    sfx_actions: list[models.VideoEnhancedSfxAction] = []
    retention_actions: list[models.VideoEnhancedRetentionAction] = []
    fallbacks: list[models.VideoEnhancedRenderFallback] = []
    warnings: list[str] = []

    creative_count = 0
    for index, item in enumerate(timeline):
        transition = _nested_transition(item.transition)
        if item.retention or transition or item.sound_design or item.retainability_quality_check:
            creative_count += 1
        retention = item.retention or {}
        if isinstance(retention, dict) and retention:
            beat_curve = retention.get("beat_curve")
            beat = beat_curve[0] if isinstance(beat_curve, list) and beat_curve and isinstance(beat_curve[0], dict) else {}
            retention_actions.append(
                models.VideoEnhancedRetentionAction(
                    shot_id=item.shot_id,
                    shot_order=item.shot_order,
                    role=_first_text(retention.get("retention_role"), retention.get("role"), beat.get("purpose")),
                    hook=_first_text(retention.get("hook_0_2s"), retention.get("viewer_question"), retention.get("open_loop")),
                    pattern_interrupt=_first_text(retention.get("pattern_interrupt"), beat.get("pattern_interrupt"), retention.get("visual_surprise")),
                    payoff=_first_text(retention.get("payoff_plan"), retention.get("payoff")),
                    note_vi=_first_text(retention.get("review_vi"), retention.get("cut_reason")),
                )
            )

        if index < len(timeline) - 1:
            original_transition = _first_text(transition.get("transition_type"), transition.get("type"), transition.get("name"))
            continuity_risk = _first_text(transition.get("continuity_risk"), transition.get("risk"))
            alias = _normalize_transition_alias(original_transition, continuity_risk)
            render_mode, rendered, fallback_reason = _transition_render_mode(alias)
            duration = 0.22 if alias in {"flash", "hard_cut", "match_cut"} else 0.35
            action = models.VideoEnhancedTransitionAction(
                from_shot_id=item.shot_id,
                to_shot_id=timeline[index + 1].shot_id,
                transition_alias=alias,
                original_transition=original_transition,
                at_seconds=round(item.end_seconds, 3),
                duration_seconds=duration,
                render_mode=render_mode,
                rendered=rendered,
                continuity_risk=continuity_risk,
                fallback_reason=fallback_reason,
            )
            transitions.append(action)
            if fallback_reason:
                fallbacks.append(models.VideoEnhancedRenderFallback(kind="transition", shot_id=item.shot_id, message_vi=fallback_reason))

        for cue in _sound_cues_for_item(item):
            cue_label = _first_text(cue.get("cue_label"), cue.get("cue_type"), cue.get("purpose"))
            alias = _normalize_sfx_alias(cue.get("cue_type"), cue_label)
            if alias == "bgm":
                continue
            start_seconds = _cue_start_seconds(item, cue, alias, total_duration)
            if alias == "silence_drop":
                message = "Silence drop chỉ được ghi vào plan; hệ thống không cắt voice tự động để tránh mất lời thoại."
                action = models.VideoEnhancedSfxAction(
                    shot_id=item.shot_id,
                    cue_alias=alias,
                    cue_label=cue_label,
                    start_seconds=start_seconds,
                    duration_seconds=_sfx_duration(alias, None),
                    volume=0.0,
                    duck_under_voice=item.has_narration,
                    rendered=False,
                    fallback_reason=message,
                )
                sfx_actions.append(action)
                fallbacks.append(models.VideoEnhancedRenderFallback(kind="sfx", shot_id=item.shot_id, cue_alias=alias, message_vi=message))
                continue
            asset = asset_index.get(alias)
            duration = _sfx_duration(alias, asset)
            action = models.VideoEnhancedSfxAction(
                shot_id=item.shot_id,
                cue_alias=alias,
                cue_label=cue_label,
                start_seconds=start_seconds,
                duration_seconds=duration,
                volume=0.36 if item.has_narration else 0.55,
                fade_in_seconds=0.02,
                fade_out_seconds=min(0.18, max(0.04, duration * 0.25)),
                duck_under_voice=item.has_narration,
                asset_id=asset.asset_id if asset else None,
                asset_filename=asset.filename if asset else None,
                asset_path=asset.file_path if asset else None,
                rendered=asset is not None,
                fallback_reason=None if asset else _missing_sfx_message(alias),
            )
            sfx_actions.append(action)
            if asset is None:
                fallbacks.append(models.VideoEnhancedRenderFallback(kind="sfx", shot_id=item.shot_id, cue_alias=alias, message_vi=action.fallback_reason or _missing_sfx_message(alias)))

    bgm_asset = asset_index.get("bgm")
    bgm_action = None
    project_sound = project.sound_design_plan_json if isinstance(project.sound_design_plan_json, dict) else {}
    has_bgm_direction = bool(_first_text(project_sound.get("music_mood"), project_sound.get("ambience_bed"), project_sound.get("energy_curve")))
    if bgm_asset:
        bgm_action = models.VideoEnhancedBgmAction(
            asset_id=bgm_asset.asset_id,
            asset_filename=bgm_asset.filename,
            asset_path=bgm_asset.file_path,
            start_seconds=0.0,
            duration_seconds=total_duration,
            volume=0.12,
            rendered=True,
        )
    elif has_bgm_direction:
        message = "Có chỉ dẫn nhạc nền/ambience nhưng chưa có asset BGM thật để mix."
        bgm_action = models.VideoEnhancedBgmAction(duration_seconds=total_duration, rendered=False, fallback_reason=message)
        fallbacks.append(models.VideoEnhancedRenderFallback(kind="bgm", message_vi=message))

    if creative_count == 0:
        fallbacks.append(models.VideoEnhancedRenderFallback(kind="creative_direction", message_vi="Project chưa có đủ retention/transition/sound metadata để tự thêm hiệu ứng giữ chân nâng cao."))
    if not settings.enhanced_render:
        warnings.append("Enhanced render đang tắt; plan chỉ dùng để preview/debug.")
    rendered_sfx_count = sum(1 for action in sfx_actions if action.rendered)
    if sfx_actions and rendered_sfx_count == 0:
        warnings.append("Có cue SFX nhưng chưa cue nào có asset thật để mix.")

    plan = models.VideoEnhancedRenderPlan(
        project_id=project.id,
        project_title=project.title,
        total_duration_seconds=total_duration,
        settings=settings.model_dump(),
        transition_actions=transitions,
        sfx_actions=sfx_actions,
        bgm_action=bgm_action,
        retention_actions=retention_actions,
        fallbacks=fallbacks,
        warnings=warnings,
    )
    return plan.model_dump()

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
    if has_sound_metadata and settings.enhanced_render and settings.enhanced_audio:
        ready_assets = [asset for asset in (list_render_sfx_assets(project_id, db) or []) if asset.status == "ready"]
        if ready_assets:
            warnings.append(
                models.VideoRenderWarning(
                    code="VIDEO_RENDER_ENHANCED_AUDIO_ASSETS_READY",
                    message=f"Enhanced audio bật: hệ thống sẽ thử map và mix {len(ready_assets)} asset SFX/BGM thật vào MP4.",
                )
            )
        else:
            warnings.append(
                models.VideoRenderWarning(
                    code="VIDEO_RENDER_SFX_ASSET_MISSING",
                    message="Enhanced audio bật nhưng project chưa có asset SFX/BGM thật; report sẽ ghi fallback rõ ràng cho các cue thiếu asset.",
                )
            )
    elif has_sound_metadata:
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

    tmp_path = cache_path.with_name(f"{cache_key[:16]}.{uuid.uuid4().hex[:12]}.tmp.mp4")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
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

def build_transition_edge_effect_command(
    *,
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    duration_seconds: float,
    fade_in_seconds: float = 0.0,
    fade_out_seconds: float = 0.0,
    color: str = "black",
) -> list[str]:
    filters: list[str] = []
    if fade_in_seconds > 0:
        filters.append(f"fade=t=in:st=0:d={fade_in_seconds:.3f}:color={color}")
    if fade_out_seconds > 0:
        start = max(0.0, duration_seconds - fade_out_seconds)
        filters.append(f"fade=t=out:st={start:.3f}:d={fade_out_seconds:.3f}:color={color}")
    return [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        ",".join(filters) if filters else "null",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

def _transition_edge_specs(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for action in plan.get("transition_actions") or []:
        if not action.get("rendered") or action.get("render_mode") != "edge_fade":
            continue
        duration = max(0.08, min(float(action.get("duration_seconds") or 0.22), 0.6))
        alias = str(action.get("transition_alias") or "")
        color = "white" if alias in {"dip_to_white", "flash"} else "black"
        from_shot_id = action.get("from_shot_id")
        to_shot_id = action.get("to_shot_id")
        if from_shot_id:
            spec = specs.setdefault(str(from_shot_id), {"fade_in": 0.0, "fade_out": 0.0, "color": color})
            spec["fade_out"] = max(float(spec.get("fade_out") or 0.0), duration)
            spec["color"] = color
        if to_shot_id:
            spec = specs.setdefault(str(to_shot_id), {"fade_in": 0.0, "fade_out": 0.0, "color": color})
            spec["fade_in"] = max(float(spec.get("fade_in") or 0.0), duration)
            spec["color"] = color
    return specs

def _apply_enhanced_video_effects(
    ffmpeg: str,
    normalized_paths: list[Path],
    timeline: list[models.VideoRenderTimelineShot],
    plan: dict[str, Any],
    output_dir: Path,
) -> list[Path]:
    specs = _transition_edge_specs(plan)
    if not specs:
        return normalized_paths
    enhanced_paths: list[Path] = []
    for index, (input_path, item) in enumerate(zip(normalized_paths, timeline, strict=True), start=1):
        spec = specs.get(item.shot_id)
        if not spec:
            enhanced_paths.append(input_path)
            continue
        out_path = output_dir / f"video-effect-{index:03d}.mp4"
        cmd = build_transition_edge_effect_command(
            ffmpeg=ffmpeg,
            input_path=input_path,
            output_path=out_path,
            duration_seconds=item.duration_seconds,
            fade_in_seconds=float(spec.get("fade_in") or 0.0),
            fade_out_seconds=float(spec.get("fade_out") or 0.0),
            color=str(spec.get("color") or "black"),
        )
        _run_command(cmd, timeout=600)
        enhanced_paths.append(out_path)
    return enhanced_paths

def _resolved_action_path(action: dict[str, Any]) -> Path | None:
    raw_path = action.get("asset_path")
    path = video_storage.resolve_artifact_storage_path(raw_path)
    return path if path is not None and path.exists() else None

def _renderable_audio_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for action in plan.get("sfx_actions") or []:
        if action.get("rendered") and _resolved_action_path(action) is not None:
            actions.append(action)
    bgm = plan.get("bgm_action")
    if isinstance(bgm, dict) and bgm.get("rendered") and _resolved_action_path(bgm) is not None:
        actions.append({**bgm, "cue_alias": "bgm", "fade_in_seconds": 0.5, "fade_out_seconds": 0.8})
    return actions

def build_enhanced_audio_mix_command(
    *,
    ffmpeg: str,
    base_audio_path: Path,
    sfx_actions: list[dict[str, Any]],
    output_path: Path,
    total_duration_seconds: float,
) -> list[str]:
    cmd = [ffmpeg, "-y", "-i", str(base_audio_path)]
    resolved_paths: list[Path] = []
    for action in sfx_actions:
        path = _resolved_action_path(action)
        if path is None:
            continue
        resolved_paths.append(path)
        cmd.extend(["-i", str(path)])
    if not resolved_paths:
        raise VideoRenderError("Không có asset SFX/BGM hợp lệ để mix.", error_code="VIDEO_RENDER_SFX_ASSET_MISSING")

    filters = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo[base]"]
    mix_inputs = ["[base]"]
    for index, action in enumerate(sfx_actions[: len(resolved_paths)], start=1):
        duration = max(0.08, min(float(action.get("duration_seconds") or total_duration_seconds), total_duration_seconds))
        start_seconds = max(0.0, min(float(action.get("start_seconds") or 0.0), max(0.0, total_duration_seconds - 0.01)))
        delay_ms = int(round(start_seconds * 1000))
        fade_in = max(0.0, min(float(action.get("fade_in_seconds") or 0.0), duration / 2))
        fade_out = max(0.0, min(float(action.get("fade_out_seconds") or 0.0), duration / 2))
        fade_out_start = max(0.0, duration - fade_out)
        volume = max(0.0, min(float(action.get("volume") or 0.0), 0.85))
        filters.append(
            f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f},"
            f"volume={volume:.3f},adelay={delay_ms}|{delay_ms}[sfx{index}]"
        )
        mix_inputs.append(f"[sfx{index}]")
    filters.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0,"
        f"atrim=duration={total_duration_seconds:.3f}[mixed]"
    )
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "[mixed]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(output_path)])
    return cmd

def _mix_enhanced_audio(
    ffmpeg: str,
    base_audio_path: Path,
    plan: dict[str, Any],
    output_path: Path,
) -> Path:
    actions = _renderable_audio_actions(plan)
    if not actions:
        return base_audio_path
    cmd = build_enhanced_audio_mix_command(
        ffmpeg=ffmpeg,
        base_audio_path=base_audio_path,
        sfx_actions=actions,
        output_path=output_path,
        total_duration_seconds=float(plan.get("total_duration_seconds") or 0.0),
    )
    _run_command(cmd, timeout=600)
    plan.setdefault("audio_mix", {})["rendered_action_count"] = len(actions)
    return output_path

def _latest_shot_prompts(project_id: str, db: Session) -> dict[str, DBVideoShotPrompt]:
    rows = (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id)
        .order_by(DBVideoShotPrompt.shot_id.asc(), DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
        .all()
    )
    prompts: dict[str, DBVideoShotPrompt] = {}
    for row in rows:
        prompts.setdefault(row.shot_id, row)
    return prompts

def _enhanced_artifact_path(base_dir: Path, kind: str) -> Path:
    item = next((entry for entry in _ENHANCED_ARTIFACTS if entry[0] == kind), None)
    if item is None:
        raise ValueError(f"Unknown enhanced render artifact kind: {kind}")
    _, index, title, suffix = item
    return base_dir / video_storage.enhanced_render_artifact_filename(index, title, suffix)

def _format_seconds(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 0.0
    return f"{seconds:.2f}s"

def _render_script_retention_markdown(
    project: DBVideoProject,
    timeline: list[models.VideoRenderTimelineShot],
    plan: dict[str, Any],
) -> str:
    lines = [
        f"# Kịch bản và nhịp giữ chân - {project.title}",
        "",
        f"- Tổng thời lượng timeline: {_format_seconds(plan.get('total_duration_seconds'))}",
        f"- Số shot: {len(timeline)}",
        "",
        "## Kịch bản",
        (project.detailed_script or project.input_synthesis or project.topic or "Chưa có kịch bản chi tiết.").strip(),
        "",
        "## Nhịp giữ chân theo shot",
    ]
    retention_by_shot = {item.get("shot_id"): item for item in plan.get("retention_actions") or []}
    for item in timeline:
        retention = retention_by_shot.get(item.shot_id) or {}
        lines.extend(
            [
                "",
                f"### Shot {item.shot_order:02d} ({_format_seconds(item.start_seconds)} - {_format_seconds(item.end_seconds)})",
                f"- Vai trò: {retention.get('role') or 'Chưa có'}",
                f"- Hook/open loop: {retention.get('hook') or 'Chưa có'}",
                f"- Pattern interrupt: {retention.get('pattern_interrupt') or 'Chưa có'}",
                f"- Payoff: {retention.get('payoff') or 'Chưa có'}",
            ]
        )
    return "\n".join(lines) + "\n"

def _render_shot_transition_csv(timeline: list[models.VideoRenderTimelineShot], plan: dict[str, Any]) -> str:
    transitions_by_shot = {item.get("from_shot_id"): item for item in plan.get("transition_actions") or []}
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "shot_order",
            "shot_id",
            "start_seconds",
            "end_seconds",
            "duration_seconds",
            "transition_alias",
            "render_mode",
            "rendered",
            "continuity_risk",
            "fallback_reason",
        ],
    )
    writer.writeheader()
    for item in timeline:
        transition = transitions_by_shot.get(item.shot_id) or {}
        writer.writerow(
            {
                "shot_order": item.shot_order,
                "shot_id": item.shot_id,
                "start_seconds": f"{item.start_seconds:.3f}",
                "end_seconds": f"{item.end_seconds:.3f}",
                "duration_seconds": f"{item.duration_seconds:.3f}",
                "transition_alias": transition.get("transition_alias") or "",
                "render_mode": transition.get("render_mode") or "",
                "rendered": transition.get("rendered") if transition else "",
                "continuity_risk": transition.get("continuity_risk") or "",
                "fallback_reason": transition.get("fallback_reason") or "",
            }
        )
    return output.getvalue()

def _render_video_prompts_markdown(project_id: str, timeline: list[models.VideoRenderTimelineShot], plan: dict[str, Any], db: Session) -> str:
    prompts = _latest_shot_prompts(project_id, db)
    transitions_by_shot = {item.get("from_shot_id"): item for item in plan.get("transition_actions") or []}
    lines = [
        "# Prompt video và chỉ dẫn hiệu ứng",
        "",
        "File này gom prompt video mới nhất theo shot kèm transition/effect đã được plan hóa.",
    ]
    for item in timeline:
        prompt = prompts.get(item.shot_id)
        transition = transitions_by_shot.get(item.shot_id) or {}
        lines.extend(
            [
                "",
                f"## Shot {item.shot_order:02d}",
                f"- Thời gian: {_format_seconds(item.start_seconds)} - {_format_seconds(item.end_seconds)}",
                f"- Transition/effect: {transition.get('transition_alias') or 'hard_cut'} ({transition.get('render_mode') or 'hard_cut'})",
                f"- Fallback: {transition.get('fallback_reason') or 'Không'}",
                "",
                "### Prompt",
                (prompt.prompt if prompt else "Chưa có prompt video cho shot này.").strip(),
            ]
        )
        if prompt and prompt.retention_notes:
            lines.extend(["", f"- Retention notes: {prompt.retention_notes}"])
        if prompt and prompt.transition_notes:
            lines.append(f"- Transition notes: {prompt.transition_notes}")
        if prompt and prompt.sound_design_notes:
            lines.append(f"- Sound design notes: {prompt.sound_design_notes}")
    return "\n".join(lines) + "\n"

def _render_sfx_mixing_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Âm thanh SFX và mixing notes",
        "",
        "Voice được ưu tiên rõ hơn SFX/BGM. Cue chỉ được ghi là đã render thật khi có asset audio hợp lệ.",
        "",
        "## SFX actions",
    ]
    for action in plan.get("sfx_actions") or []:
        rendered = "đã mix asset thật" if action.get("rendered") else "fallback/chưa mix"
        lines.extend(
            [
                "",
                f"- `{action.get('cue_alias')}` tại {_format_seconds(action.get('start_seconds'))}: {rendered}",
                f"  - Asset: {action.get('asset_filename') or 'chưa có'}",
                f"  - Volume: {action.get('volume')}",
                f"  - Duck voice: {'có' if action.get('duck_under_voice') else 'không'}",
                f"  - Ghi chú: {action.get('fallback_reason') or 'OK'}",
            ]
        )
    bgm = plan.get("bgm_action") if isinstance(plan.get("bgm_action"), dict) else None
    lines.extend(["", "## BGM"])
    if bgm:
        lines.append(f"- Asset: {bgm.get('asset_filename') or 'chưa có'}")
        lines.append(f"- Trạng thái: {'đã mix' if bgm.get('rendered') else 'fallback/chưa mix'}")
        lines.append(f"- Ghi chú: {bgm.get('fallback_reason') or 'OK'}")
    else:
        lines.append("- Chưa có BGM action.")
    lines.extend(["", "## Fallback"])
    fallbacks = plan.get("fallbacks") or []
    if fallbacks:
        for fallback in fallbacks:
            lines.append(f"- {fallback.get('message_vi')}")
    else:
        lines.append("- Không có fallback.")
    return "\n".join(lines) + "\n"

def _probe_output_summary(path: Path, ffprobe: str | None) -> dict[str, Any]:
    if not ffprobe or not path.exists():
        return {"available": False, "reason": "Không có FFprobe hoặc file output chưa tồn tại."}
    result = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return {"available": False, "reason": _truncate_stderr(result.stderr) or "FFprobe không đọc được output."}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": False, "reason": "FFprobe trả metadata không hợp lệ."}
    streams = payload.get("streams") or []
    return {
        "available": True,
        "duration_seconds": _float_or_none((payload.get("format") or {}).get("duration")),
        "video_streams": sum(1 for stream in streams if stream.get("codec_type") == "video"),
        "audio_streams": sum(1 for stream in streams if stream.get("codec_type") == "audio"),
    }

def _build_render_review(
    plan: dict[str, Any],
    settings: models.VideoRenderSettings,
    output_summary: dict[str, Any],
) -> dict[str, Any]:
    if not settings.ai_review:
        return {
            "status": "skipped",
            "passed": None,
            "source": "not_run",
            "findings": ["Người dùng đã tắt AI review cho render này."],
            "fixable_actions": [],
            "requires_user_action": [],
            "review_vi": "Chưa chạy AI review sau render vì setting ai_review đang tắt.",
            "max_fix_attempts": settings.max_fix_attempts,
            "fix_attempt_count": 0,
        }

    findings: list[str] = []
    fixable_actions: list[str] = []
    requires_user_action: list[str] = []
    for fallback in plan.get("fallbacks") or []:
        message = str(fallback.get("message_vi") or "")
        findings.append(message)
        if fallback.get("kind") in {"sfx", "bgm"}:
            requires_user_action.append(message)
        elif fallback.get("kind") == "transition":
            fixable_actions.append("Đã fallback transition về hard cut an toàn trong plan.")
    if not output_summary.get("available"):
        findings.append(f"Chỉ review được manifest/plan; metadata output chưa đầy đủ: {output_summary.get('reason')}")
    else:
        if int(output_summary.get("audio_streams") or 0) < 1:
            findings.append("Output không có audio stream theo FFprobe.")
            fixable_actions.append("Kiểm tra lại bước mux audio và render lại.")
        if int(output_summary.get("video_streams") or 0) < 1:
            findings.append("Output không có video stream theo FFprobe.")
            requires_user_action.append("Cần kiểm tra lại clip source hoặc FFmpeg runtime.")
    rendered_sfx_count = sum(1 for action in plan.get("sfx_actions") or [] if action.get("rendered"))
    if rendered_sfx_count:
        findings.append(f"Đã có {rendered_sfx_count} cue SFX/BGM có asset thật trong plan mix.")
    findings.append("Phạm vi review: dựa trên manifest, enhanced plan và metadata FFprobe; chưa khẳng định đã nghe/xem chi tiết từng frame nếu không có frame/audio analysis đầy đủ.")

    status = "passed"
    passed = True
    if requires_user_action:
        status = "needs_user_action"
        passed = False
    elif findings or fixable_actions:
        status = "warning"
    return {
        "status": status,
        "passed": passed,
        "source": "metadata_rule_review",
        "findings": findings,
        "fixable_actions": fixable_actions,
        "requires_user_action": requires_user_action,
        "review_vi": "Review tự động đã hoàn tất với phạm vi metadata/manifest. Xem findings để biết cue nào đã mix thật và cue nào cần asset/fallback.",
        "max_fix_attempts": settings.max_fix_attempts,
        "fix_attempt_count": 0,
    }

def _render_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Báo cáo AI review sau render",
        "",
        f"- Trạng thái: {review.get('status')}",
        f"- Nguồn phân tích: {review.get('source')}",
        f"- Auto-fix đã dùng: {review.get('fix_attempt_count', 0)}/{review.get('max_fix_attempts', 0)}",
        "",
        "## Kết luận",
        str(review.get("review_vi") or ""),
        "",
        "## Findings",
    ]
    findings = review.get("findings") or []
    lines.extend([f"- {item}" for item in findings] or ["- Không có finding."])
    lines.extend(["", "## Fixable actions"])
    fixable = review.get("fixable_actions") or []
    lines.extend([f"- {item}" for item in fixable] or ["- Không có action tự sửa."])
    lines.extend(["", "## Cần người dùng xử lý"])
    required = review.get("requires_user_action") or []
    lines.extend([f"- {item}" for item in required] or ["- Không có yêu cầu thêm."])
    return "\n".join(lines) + "\n"

def _write_enhanced_render_artifacts(
    *,
    project: DBVideoProject,
    job: DBVideoRenderJob,
    timeline: list[models.VideoRenderTimelineShot],
    plan: dict[str, Any],
    manifest_payload: dict[str, Any],
    review: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    base_dir = video_storage.get_project_subdir(project.id, "render_enhanced") / job.id
    base_dir.mkdir(parents=True, exist_ok=True)
    plan_path = base_dir / "enhanced-render-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    content_by_kind = {
        "script_retention": _render_script_retention_markdown(project, timeline, plan),
        "shot_transitions": _render_shot_transition_csv(timeline, plan),
        "video_prompts_effects": _render_video_prompts_markdown(project.id, timeline, plan, db),
        "sfx_mixing_notes": _render_sfx_mixing_markdown(plan),
        "ai_review_report": _render_review_markdown(review),
        "timeline_manifest": json.dumps({**manifest_payload, "enhanced_render_plan": plan, "review": review}, ensure_ascii=False, indent=2),
    }
    items: list[dict[str, Any]] = []
    for kind, _, _, _ in _ENHANCED_ARTIFACTS:
        path = _enhanced_artifact_path(base_dir, kind)
        path.write_text(content_by_kind[kind], encoding="utf-8", newline="" if path.suffix == ".csv" else None)
        items.append({"kind": kind, "filename": path.name, "path": video_storage.to_artifact_storage_path(path)})
    return {
        "enhanced_plan": video_storage.to_artifact_storage_path(plan_path),
        "items": items,
    }

def _render_job_steps(job: DBVideoRenderJob, db: Session) -> None:
    settings = models.VideoRenderSettings.model_validate_json(job.settings_json or "{}")
    tools = detect_tools()
    if not tools.ffmpeg_ready:
        raise VideoRenderError("Chưa tìm thấy FFmpeg.", error_code="VIDEO_RENDER_FFMPEG_MISSING")
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
    enhanced_plan: dict[str, Any] | None = None
    if settings.enhanced_render:
        sfx_assets = list_render_sfx_assets(project.id, db) or []
        enhanced_plan = build_enhanced_render_plan(project, timeline, shots_by_id, sfx_assets, settings)
        _update_job(job, db, progress=0.08, current_step="Đang lập enhanced render plan")
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
    video_paths_for_concat = normalized_paths
    if enhanced_plan is not None:
        try:
            video_paths_for_concat = _apply_enhanced_video_effects(tools.ffmpeg or "ffmpeg", normalized_paths, timeline, enhanced_plan, intermediate_dir)
            _update_job(job, db, progress=0.58, current_step="Đang áp dụng hiệu ứng chuyển cảnh an toàn")
        except VideoRenderError as exc:
            enhanced_plan.setdefault("fallbacks", []).append(
                {
                    "kind": "transition",
                    "message_vi": f"Không render được hiệu ứng chuyển cảnh nâng cao nên fallback về ghép cơ bản: {exc}",
                }
            )
            enhanced_plan.setdefault("warnings", []).append("Transition effect fallback về ghép cơ bản.")
            video_paths_for_concat = normalized_paths
    _concat_media(tools.ffmpeg or "ffmpeg", video_paths_for_concat, video_concat, stream_copy=True)
    _update_job(job, db, progress=0.6, current_step="Đang ghép video")

    audio_segments = _build_audio_segments(tools.ffmpeg or "ffmpeg", timeline, shots_by_id, intermediate_dir)
    audio_concat = intermediate_dir / "audio.wav"
    _concat_media(tools.ffmpeg or "ffmpeg", audio_segments, audio_concat, stream_copy=False, audio=True)
    audio_for_mux = audio_concat
    if enhanced_plan is not None and settings.enhanced_audio:
        try:
            audio_for_mux = _mix_enhanced_audio(
                tools.ffmpeg or "ffmpeg",
                audio_concat,
                enhanced_plan,
                intermediate_dir / "audio-enhanced.wav",
            )
            if audio_for_mux != audio_concat:
                _update_job(job, db, progress=0.73, current_step="Đang mix SFX/BGM thật")
        except VideoRenderError as exc:
            enhanced_plan.setdefault("fallbacks", []).append(
                {
                    "kind": "audio_mix",
                    "message_vi": f"Không mix được SFX/BGM thật nên giữ audio voice cơ bản: {exc}",
                }
            )
            enhanced_plan.setdefault("warnings", []).append("Audio mix fallback về voice cơ bản.")
            audio_for_mux = audio_concat
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
        audio_path=audio_for_mux,
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
    if enhanced_plan is not None:
        output_summary = _probe_output_summary(output_path, tools.ffprobe)
        review = _build_render_review(enhanced_plan, settings, output_summary)
        artifacts = _write_enhanced_render_artifacts(
            project=project,
            job=job,
            timeline=timeline,
            plan=enhanced_plan,
            manifest_payload=manifest_payload,
            review=review,
            db=db,
        )
        job.enhanced_plan_path = artifacts.get("enhanced_plan")
        job.enhanced_artifacts_json = artifacts
        review_item = next((item for item in artifacts.get("items", []) if item.get("kind") == "ai_review_report"), None)
        job.review_report_path = review_item.get("path") if review_item else None
        job.review_status = review.get("status")
        job.fix_attempt_count = int(review.get("fix_attempt_count") or 0)
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

def get_enhanced_render_artifact_download(project_id: str, job_id: str, artifact_key: str, db: Session) -> tuple[str, Path] | None:
    job = db.query(DBVideoRenderJob).filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.id == job_id).first()
    if job is None or not job.enhanced_artifacts_json:
        return None
    artifacts = job.enhanced_artifacts_json if isinstance(job.enhanced_artifacts_json, dict) else {}
    for item in artifacts.get("items") or []:
        filename = str(item.get("filename") or "")
        kind = str(item.get("kind") or "")
        if artifact_key not in {filename, kind}:
            continue
        path = video_storage.resolve_artifact_storage_path(item.get("path"))
        if path is None or not path.exists():
            return None
        return filename, path
    if artifact_key == "enhanced_plan":
        path = video_storage.resolve_artifact_storage_path(artifacts.get("enhanced_plan"))
        if path is not None and path.exists():
            return "enhanced-render-plan.json", path
    return None
