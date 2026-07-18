"""Video inspiration workflow: source video -> transcript/visual notes -> new script."""

from __future__ import annotations

import asyncio
from array import array
import importlib.util
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
import wave
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator, TypeVar
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config, models
from ..database import (
    VideoInspirationAudioEvent as DBVideoInspirationAudioEvent,
    VideoInspirationFrame as DBVideoInspirationFrame,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoInspirationRetentionBeat as DBVideoInspirationRetentionBeat,
    VideoInspirationShot as DBVideoInspirationShot,
    VideoInspirationTextEvent as DBVideoInspirationTextEvent,
    VideoInspirationTranscriptSegment as DBVideoInspirationTranscriptSegment,
    VideoProject as DBVideoProject,
)
from . import (
    ai_planning,
    settings as settings_service,
    video_auto_runs,
    video_language,
    video_project_memory,
    video_planning_pool,
    video_projects,
    video_rendering,
    video_storage,
)
from .transcribe import get_whisper_model

logger = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 700 * 1024 * 1024
MAX_VIDEO_DURATION_SECONDS = 30 * 60
MAX_FRAME_COUNT = 12
MAX_QUICK_KEYFRAMES = 14
MAX_HIGH_QUALITY_KEYFRAMES = 36
LONG_SHOT_SECONDS = 16.0
SHOT_SCENE_THRESHOLD_QUICK = 0.40
SHOT_SCENE_THRESHOLD_HIGH_QUALITY = 0.28
ANALYSIS_SCHEMA_VERSION = "video_analysis_package.v1"
TRANSCRIPT_CHUNK_SECONDS = 25.0
TRANSCRIPT_SINGLE_PASS_MAX_SECONDS = 28.0
FFMPEG_TIMEOUT_SECONDS = 600
AI_TIMEOUT_SECONDS = 600
ACTIVE_JOB_STALE_SECONDS = 15 * 60
ACTIVE_JOB_STALE_DELTA = timedelta(seconds=ACTIVE_JOB_STALE_SECONDS)
ACTIVE_JOB_STATUSES = {"analyzing", "rewriting", "handoff"}
_STDERR_LIMIT = 1200
_AUDIO_ONLY_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
_NO_SPEECH_TRANSCRIPT_LABELS = {
    "applause",
    "background music",
    "background noise",
    "instrumental",
    "laughter",
    "music",
    "music playing",
    "no speech",
    "noise",
    "silence",
    "sound effect",
    "sound effects",
}
_SOCIAL_PLATFORMS = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "facebook.com": "facebook",
    "fb.watch": "facebook",
    "instagram.com": "instagram",
}
_SENSITIVE_QUERY_KEYS = {"token", "access_token", "auth", "key", "signature", "sig", "s", "fbclid"}
_GENERIC_SOURCE_TITLE_STEMS = {
    "download",
    "source",
    "upload",
    "video",
    "file",
    "output",
    "clip",
    "untitled",
}

STEP_LABELS_VI = {
    "source_ready": "Đã nhận video",
    "downloading": "Đang lấy video từ link",
    "extract_audio": "Đang tách lời nói",
    "transcribe": "Đang chuyển lời nói thành chữ",
    "extract_frames": "Đang lấy hình ảnh đại diện",
    "visual_analysis": "Đang phân tích hình ảnh",
    "content_analysis": "Đang phân tích nội dung",
    "queued_analysis": "Đang chờ lượt phân tích video",
    "queued_rewrite": "Đang chờ lượt viết kịch bản",
    "rewrite": "Đang viết kịch bản tối ưu",
    "rewrite_brief": "Đang tạo brief kịch bản",
    "rewrite_candidates": "Đang tạo các bản nháp",
    "rewrite_review": "Đang chấm điểm bản nháp",
    "rewrite_synthesis": "Đang tổng hợp bản cuối",
    "handoff": "Đang chuyển sang AI Video",
    "completed": "Hoàn tất",
    "failed": "Đã lỗi",
    "cancelled": "Đã hủy",
    "interrupted": "Đã bị gián đoạn",
}

_AI_JOB_ID: ContextVar[str | None] = ContextVar("video_inspiration_ai_job_id", default=None)
_AI_STEP_NAME: ContextVar[str] = ContextVar("video_inspiration_ai_step_name", default="video_inspiration_ai")
_T = TypeVar("_T")

class VideoInspirationError(ValueError):
    """Raised when the video inspiration workflow cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_INSPIRATION_ERROR", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class VideoInspirationCancelledError(VideoInspirationError):
    """Raised at cooperative checkpoints after a background cancel request."""

    def __init__(self):
        super().__init__(
            "Đã hủy tác vụ Video Inspiration theo yêu cầu.",
            error_code="VIDEO_INSPIRATION_CANCELLED",
        )


def _ensure_not_cancelled(cancel_requested: Callable[[], bool] | None) -> None:
    if cancel_requested is not None and cancel_requested():
        raise VideoInspirationCancelledError()


@contextmanager
def _structured_ai_context(job_id: str, step_name: str) -> Iterator[None]:
    job_token = _AI_JOB_ID.set(job_id)
    step_token = _AI_STEP_NAME.set(step_name)
    try:
        yield
    finally:
        _AI_STEP_NAME.reset(step_token)
        _AI_JOB_ID.reset(job_token)

def _now() -> datetime:
    return datetime.utcnow()

def _data_root() -> Path:
    path = config.get_data_dir() / "video_inspiration"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _job_dir(job_id: str) -> Path:
    path = _data_root() / job_id
    for child in ("source", "audio", "frames", "analysis"):
        (path / child).mkdir(parents=True, exist_ok=True)
    return path

def _truncate(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    return text[:limit].rstrip()

def _title_candidate(value: Any, *, filename: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if filename:
        text = Path(text).stem
    text = re.sub(r"\.(?:aac|avi|flac|m4a|m4v|mkv|mov|mp3|mp4|ogg|opus|wav|webm)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .:-_")
    normalized = re.sub(r"\s*\(\d+\)$", "", text.lower()).strip()
    normalized = re.sub(r"\s+(?:aac|avi|flac|m4a|m4v|mkv|mov|mp3|mp4|ogg|opus|wav|webm)$", "", normalized).strip()
    normalized = re.sub(r"\s+\d+$", "", normalized).strip()
    if not text:
        return ""
    if text.lower() in _GENERIC_SOURCE_TITLE_STEMS or normalized in _GENERIC_SOURCE_TITLE_STEMS:
        return ""
    return _truncate(text, 120)

def _project_title_from_job(row: DBVideoInspirationJob) -> str:
    analysis = row.analysis_json or {}
    rewrite = analysis.get("rewrite") if isinstance(analysis.get("rewrite"), dict) else {}
    for value in (
        row.script_title,
        rewrite.get("title"),
        row.big_idea,
        rewrite.get("big_idea"),
        row.hook,
        analysis.get("main_idea_vi"),
        analysis.get("hook_vi"),
        row.user_direction,
        row.transcript_text,
    ):
        title = _title_candidate(value)
        if title:
            return title
    title = _title_candidate(row.original_filename, filename=True)
    if title and row.source_type != "url":
        return title
    platform = (row.source_platform or "").strip().lower()
    if platform and platform != "unknown":
        return f"Video cảm hứng từ {platform.title()}"
    return "Video từ cảm hứng"

def _safe_filename(value: str | None, *, fallback: str = "video") -> str:
    return video_storage.sanitize_download_filename(value or fallback, fallback=fallback)

def _trim_stderr(value: str | None) -> str:
    text = (value or "").strip()
    return text[-_STDERR_LIMIT:] if len(text) > _STDERR_LIMIT else text

def _redact_url(value: str) -> str:
    parsed = urlparse(value)
    query = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "[redacted]" if key.lower() in _SENSITIVE_QUERY_KEYS else item_value))
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

def _source_platform(value: str | None) -> str:
    if not value:
        return "upload"
    host = (urlparse(value).hostname or "").lower().removeprefix("www.")
    for suffix, platform in _SOCIAL_PLATFORMS.items():
        if host == suffix or host.endswith("." + suffix):
            return platform
    return "unknown"

def _validate_target_language(value: str | None) -> str:
    language = video_language.normalize_video_language(value, default="")
    if language:
        return language
    raise VideoInspirationError("Ngôn ngữ kịch bản mới không hợp lệ.", error_code="VIDEO_INSPIRATION_LANGUAGE_INVALID")

def _clean_user_direction(value: str | None) -> str | None:
    text = _truncate(value, 20000)
    return text or None

def _tools() -> video_rendering.FFmpegTools:
    return video_rendering.detect_tools()

def _require_ffmpeg(*, ffprobe: bool = False) -> video_rendering.FFmpegTools:
    tools = _tools()
    if not tools.ffmpeg_ready or (ffprobe and not tools.ffprobe_ready):
        missing = "FFmpeg/FFprobe" if ffprobe else "FFmpeg"
        raise VideoInspirationError(
            f"Thiếu {missing}. Hãy cấu hình FFmpeg trước khi phân tích video.",
            error_code="VIDEO_INSPIRATION_FFMPEG_REQUIRED",
        )
    return tools

def _run_command(command: list[str], *, timeout_seconds: int = FFMPEG_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )

def _yt_dlp_command() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return None

def _yt_dlp_ffmpeg_args() -> list[str]:
    tools = _tools()
    if not tools.ffmpeg:
        return []
    ffmpeg_path = Path(tools.ffmpeg)
    if not ffmpeg_path.is_absolute():
        return []
    return ["--ffmpeg-location", str(ffmpeg_path.parent)]

def _download_error_text(result: subprocess.CompletedProcess[str], source_url: str) -> str:
    text = "\n".join(part for part in (result.stderr, result.stdout) if part).strip()
    if source_url:
        text = text.replace(source_url, _redact_url(source_url))
    return _trim_stderr(text)

def _download_failure_error(result: subprocess.CompletedProcess[str], source_url: str) -> VideoInspirationError:
    detail = _download_error_text(result, source_url)
    lowered = detail.lower()
    if "could not find" in lowered and "browser" in lowered:
        return VideoInspirationError(
            "Không tìm thấy trình duyệt đã đăng nhập để lấy quyền xem link này. Hãy mở Chrome/Edge/Firefox, đăng nhập nền tảng đó, rồi thử lại hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_BROWSER_COOKIES_NOT_FOUND",
        )
    if "database is locked" in lowered or "could not copy chrome cookie database" in lowered:
        return VideoInspirationError(
            "Trình duyệt đang khóa dữ liệu đăng nhập nên app chưa dùng được phiên đăng nhập. Hãy đóng hẳn trình duyệt rồi thử lại, hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_BROWSER_COOKIES_LOCKED",
        )
    if any(part in lowered for part in ("sign in", "login", "log in", "private", "members-only")):
        return VideoInspirationError(
            "Link này đang bị nền tảng yêu cầu đăng nhập, xác minh hoặc không thật sự công khai. Hãy bật tùy chọn dùng phiên đăng nhập trình duyệt nếu đây là link anh có quyền xem, hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_LINK_REQUIRES_LOGIN",
        )
    if any(part in lowered for part in ("403", "forbidden", "blocked", "captcha", "bot")):
        return VideoInspirationError(
            "Nền tảng đang chặn tải tự động link này. Hãy thử copy link chia sẻ công khai mới, hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_LINK_BLOCKED",
        )
    if any(part in lowered for part in ("larger than max-filesize", "file is larger", "max-filesize")):
        return VideoInspirationError(
            "Video từ link này quá nặng. Bản đầu chỉ nhận video dưới 700MB, hãy dùng video ngắn hơn hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_LINK_TOO_LARGE",
        )
    if "unsupported url" in lowered:
        return VideoInspirationError(
            "Link này chưa thuộc dạng app đọc được. Hãy dùng link chia sẻ công khai từ YouTube, TikTok, Facebook hoặc Instagram.",
            error_code="VIDEO_INSPIRATION_PLATFORM_UNSUPPORTED",
        )
    if "ffmpeg" in lowered and any(part in lowered for part in ("not found", "not installed", "unable to")):
        return VideoInspirationError(
            "Thiếu FFmpeg để ghép hoặc chuyển video từ link. Hãy cấu hình FFmpeg rồi thử lại.",
            error_code="VIDEO_INSPIRATION_FFMPEG_REQUIRED",
        )
    if any(part in lowered for part in ("timed out", "timeout", "temporary failure", "connection")):
        return VideoInspirationError(
            "Mạng hoặc nền tảng phản hồi quá chậm nên chưa lấy được video. Hãy thử lại sau hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_LINK_NETWORK_FAILED",
        )
    if "unavailable" in lowered:
        return VideoInspirationError(
            "Video trong link này không còn khả dụng hoặc không mở công khai được. Hãy dùng link khác hoặc upload file .mp4.",
            error_code="VIDEO_INSPIRATION_LINK_UNAVAILABLE",
        )
    return VideoInspirationError(
        "Link này chưa tải được. Nền tảng có thể đang chặn tải tự động; hãy thử copy lại link chia sẻ công khai hoặc upload file .mp4.",
        error_code="VIDEO_INSPIRATION_LINK_DOWNLOAD_FAILED",
    )

def _remove_partial_downloads(source_dir: Path) -> None:
    for path in source_dir.glob("download.*"):
        if path.is_file():
            path.unlink(missing_ok=True)

def _browser_cookie_candidates() -> list[str]:
    candidates: list[str] = []
    local_app_data = Path(os.environ.get("LOCALAPPDATA") or "")
    app_data = Path(os.environ.get("APPDATA") or "")
    home = Path.home()
    browser_paths = [
        ("edge", local_app_data / "Microsoft" / "Edge" / "User Data"),
        ("chrome", local_app_data / "Google" / "Chrome" / "User Data"),
        ("brave", local_app_data / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("vivaldi", local_app_data / "Vivaldi" / "User Data"),
        ("opera", app_data / "Opera Software" / "Opera Stable"),
        ("firefox", app_data / "Mozilla" / "Firefox" / "Profiles"),
        ("chrome", home / ".config" / "google-chrome"),
        ("chromium", home / ".config" / "chromium"),
        ("edge", home / ".config" / "microsoft-edge"),
        ("firefox", home / ".mozilla" / "firefox"),
    ]
    for browser, path in browser_paths:
        if browser not in candidates and path.exists():
            candidates.append(browser)
    return candidates or ["edge", "chrome", "firefox"]

def _yt_dlp_download_attempts(
    downloader_command: list[str],
    output_template: Path,
    source_url: str,
    *,
    use_browser_cookies: bool = False,
) -> list[list[str]]:
    common = [
        *downloader_command,
        "--no-playlist",
        "--max-filesize",
        "700M",
        "--windows-filenames",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "--socket-timeout",
        "30",
        "--extractor-args",
        "youtube:player_client=android,ios,web,tv",
        *_yt_dlp_ffmpeg_args(),
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "--add-header",
        "Accept-Language: vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    ]
    def build(format_selector: str, extra: list[str] | None = None) -> list[str]:
        return [
            *common,
            *(extra or []),
            "--merge-output-format",
            "mp4",
            "-f",
            format_selector,
            "-o",
            str(output_template),
            source_url,
        ]

    def build_simple(format_selector: str, extra: list[str] | None = None) -> list[str]:
        return [
            *common,
            *(extra or []),
            "--merge-output-format",
            "mp4",
            "-f",
            format_selector,
            "-o",
            str(output_template),
            source_url,
        ]

    attempts = [
        build("bv*[height<=720]+ba/best[height<=720][ext=mp4]/best[ext=mp4]/best"),
        build_simple("best[height<=720]/best"),
    ]
    if use_browser_cookies:
        for browser in _browser_cookie_candidates():
            cookies = ["--cookies-from-browser", browser]
            attempts.extend(
                [
                    build("bv*[height<=720]+ba/best[height<=720][ext=mp4]/best[ext=mp4]/best", cookies),
                    build_simple("best[height<=720]/best", cookies),
                ],
            )
    return attempts

def _probe_video(path: Path) -> dict[str, Any]:
    tools = _require_ffmpeg(ffprobe=False)
    if not tools.ffprobe:
        return _probe_video_with_ffmpeg(path, tools.ffmpeg or "ffmpeg")
    result = _run_command(
        [
            tools.ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout_seconds=60,
    )
    if result.returncode != 0:
        raise VideoInspirationError(
            "Không đọc được thông tin video. File có thể bị lỗi hoặc không đúng định dạng.",
            error_code="VIDEO_INSPIRATION_PROBE_FAILED",
        )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoInspirationError(
            "Không đọc được thông tin video từ FFprobe.",
            error_code="VIDEO_INSPIRATION_PROBE_INVALID",
        ) from exc
    streams = payload.get("streams") if isinstance(payload, dict) else []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = _float_or_none((payload.get("format") or {}).get("duration")) or _float_or_none(video_stream.get("duration"))
    return {
        "duration_seconds": duration,
        "width": _int_or_none(video_stream.get("width")),
        "height": _int_or_none(video_stream.get("height")),
        "codec": video_stream.get("codec_name"),
        "has_audio": audio_stream is not None,
    }

def _probe_video_with_ffmpeg(path: Path, ffmpeg: str) -> dict[str, Any]:
    result = _run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
        ],
        timeout_seconds=60,
    )
    text = "\n".join(part for part in (result.stderr, result.stdout) if part)
    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    if not video_line:
        raise VideoInspirationError(
            "Không đọc được thông tin video. File có thể bị lỗi hoặc không đúng định dạng.",
            error_code="VIDEO_INSPIRATION_PROBE_FAILED",
        )
    duration = None
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    size_match = re.search(r"(?<![\w])(\d{2,5})x(\d{2,5})(?![\w])", video_line)
    codec_match = re.search(r"Video:\s*([^,\s]+)", video_line)
    return {
        "duration_seconds": duration,
        "width": int(size_match.group(1)) if size_match else None,
        "height": int(size_match.group(2)) if size_match else None,
        "codec": codec_match.group(1) if codec_match else None,
        "has_audio": "Audio:" in text,
    }

def _mux_downloaded_audio_video(video_path: Path, audio_path: Path) -> Path:
    tools = _require_ffmpeg(ffprobe=False)
    output_path = video_path.with_name("download.merged.mp4")
    attempts = [
        [
            tools.ffmpeg or "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        [
            tools.ffmpeg or "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
    ]
    last_result: subprocess.CompletedProcess[str] | None = None
    for command in attempts:
        output_path.unlink(missing_ok=True)
        result = _run_command(command)
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        last_result = result
    logger.warning(
        "Failed to merge downloaded split media video=%s audio=%s detail=%s",
        video_path.name,
        audio_path.name,
        _trim_stderr((last_result.stderr if last_result else "") or ""),
    )
    raise VideoInspirationError(
        "Không ghép được hình và tiếng sau khi tải link. Hãy thử lại hoặc upload file .mp4.",
        error_code="VIDEO_INSPIRATION_MEDIA_MERGE_FAILED",
    )

def _prepare_downloaded_source(source_dir: Path) -> tuple[Path, dict[str, Any]]:
    candidates = [path for path in source_dir.iterdir() if path.is_file()]
    if not candidates:
        raise VideoInspirationError("Không tìm thấy file video sau khi tải link.", error_code="VIDEO_INSPIRATION_LINK_NO_MEDIA")

    audio_candidates = sorted(
        [path for path in candidates if path.suffix.lower() in _AUDIO_ONLY_SUFFIXES],
        key=lambda item: item.stat().st_size,
        reverse=True,
    )
    video_candidates = sorted(
        [path for path in candidates if path.suffix.lower() not in _AUDIO_ONLY_SUFFIXES],
        key=lambda item: item.stat().st_size,
        reverse=True,
    )
    last_error: VideoInspirationError | None = None
    for video_path in video_candidates:
        try:
            metadata = _validate_video_file(video_path, size_bytes=video_path.stat().st_size)
        except VideoInspirationError as exc:
            last_error = exc
            continue
        if metadata.get("has_audio") or not audio_candidates:
            return video_path, metadata
        merged_path = _mux_downloaded_audio_video(video_path, audio_candidates[0])
        merged_metadata = _validate_video_file(merged_path, size_bytes=merged_path.stat().st_size)
        return merged_path, merged_metadata

    if last_error:
        raise last_error
    raise VideoInspirationError("Không tìm thấy file video sau khi tải link.", error_code="VIDEO_INSPIRATION_LINK_NO_MEDIA")

def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _validate_video_file(path: Path, *, size_bytes: int) -> dict[str, Any]:
    if size_bytes <= 0:
        raise VideoInspirationError("File video đang rỗng.", error_code="VIDEO_INSPIRATION_FILE_EMPTY")
    if size_bytes > MAX_VIDEO_BYTES:
        raise VideoInspirationError("Video quá nặng. Hãy chọn file dưới 700MB.", error_code="VIDEO_INSPIRATION_FILE_TOO_LARGE")
    metadata = _probe_video(path)
    duration = metadata.get("duration_seconds")
    if duration and duration > MAX_VIDEO_DURATION_SECONDS:
        raise VideoInspirationError("Video quá dài. Bản đầu chỉ nhận video tối đa 30 phút.", error_code="VIDEO_INSPIRATION_VIDEO_TOO_LONG")
    return metadata

def _set_job_state(
    row: DBVideoInspirationJob,
    db: Session,
    *,
    status: str | None = None,
    step: str | None = None,
    progress: float | None = None,
    failure_reason: str | None = None,
    error_code: str | None = None,
) -> None:
    if status is not None:
        row.status = status
    if step is not None:
        row.current_step = step
    if progress is not None:
        row.progress = max(0.0, min(1.0, float(progress)))
    row.failure_reason = failure_reason
    row.error_code = error_code
    row.updated_at = _now()
    db.commit()

def _fail_job(row: DBVideoInspirationJob, db: Session, exc: BaseException) -> None:
    _set_job_state(
        row,
        db,
        status="failed",
        step="failed",
        progress=row.progress or 0.0,
        failure_reason=str(exc),
        error_code=getattr(exc, "error_code", "VIDEO_INSPIRATION_FAILED"),
    )

def _frames_for_job(job_id: str, db: Session) -> list[DBVideoInspirationFrame]:
    return (
        db.query(DBVideoInspirationFrame)
        .filter(DBVideoInspirationFrame.job_id == job_id)
        .order_by(DBVideoInspirationFrame.timestamp_seconds.asc(), DBVideoInspirationFrame.created_at.asc())
        .all()
    )

def _shots_for_job(job_id: str, db: Session) -> list[DBVideoInspirationShot]:
    return (
        db.query(DBVideoInspirationShot)
        .filter(DBVideoInspirationShot.job_id == job_id)
        .order_by(DBVideoInspirationShot.shot_order.asc(), DBVideoInspirationShot.start_seconds.asc())
        .all()
    )

def _transcript_segments_for_job(job_id: str, db: Session) -> list[DBVideoInspirationTranscriptSegment]:
    return (
        db.query(DBVideoInspirationTranscriptSegment)
        .filter(DBVideoInspirationTranscriptSegment.job_id == job_id)
        .order_by(DBVideoInspirationTranscriptSegment.segment_order.asc(), DBVideoInspirationTranscriptSegment.start_seconds.asc())
        .all()
    )

def _audio_events_for_job(job_id: str, db: Session) -> list[DBVideoInspirationAudioEvent]:
    return (
        db.query(DBVideoInspirationAudioEvent)
        .filter(DBVideoInspirationAudioEvent.job_id == job_id)
        .order_by(DBVideoInspirationAudioEvent.event_order.asc(), DBVideoInspirationAudioEvent.start_seconds.asc())
        .all()
    )

def _text_events_for_job(job_id: str, db: Session) -> list[DBVideoInspirationTextEvent]:
    return (
        db.query(DBVideoInspirationTextEvent)
        .filter(DBVideoInspirationTextEvent.job_id == job_id)
        .order_by(DBVideoInspirationTextEvent.event_order.asc(), DBVideoInspirationTextEvent.start_seconds.asc())
        .all()
    )

def _retention_beats_for_job(job_id: str, db: Session) -> list[DBVideoInspirationRetentionBeat]:
    return (
        db.query(DBVideoInspirationRetentionBeat)
        .filter(DBVideoInspirationRetentionBeat.job_id == job_id)
        .order_by(DBVideoInspirationRetentionBeat.beat_order.asc(), DBVideoInspirationRetentionBeat.start_seconds.asc())
        .all()
    )

def _active_job_stale(row: DBVideoInspirationJob) -> bool:
    if row.status not in ACTIVE_JOB_STATUSES:
        return False
    last_update = row.updated_at or row.created_at
    if last_update is None:
        return False
    age = _now() - last_update
    return age > ACTIVE_JOB_STALE_DELTA

def _stale_reason(row: DBVideoInspirationJob) -> str:
    step = STEP_LABELS_VI.get(row.current_step, row.current_step or "bước đang chạy")
    minutes = ACTIVE_JOB_STALE_SECONDS // 60
    return (
        f"Job bị gián đoạn ở bước {step} và đã quá {minutes} phút không cập nhật. "
        "Bấm chạy lại phân tích để tiếp tục từ video nguồn."
    )

def _job_response(row: DBVideoInspirationJob, db: Session) -> models.VideoInspirationJobResponse:
    response = models.VideoInspirationJobResponse.model_validate(row)
    response.is_stale = _active_job_stale(row)
    response.stale_reason = _stale_reason(row) if response.is_stale else None
    response.frames = [models.VideoInspirationFrameResponse.model_validate(frame) for frame in _frames_for_job(row.id, db)]
    response.shots = [models.VideoInspirationShotResponse.model_validate(shot) for shot in _shots_for_job(row.id, db)]
    response.transcript_segments = [
        models.VideoInspirationTranscriptSegmentResponse.model_validate(segment)
        for segment in _transcript_segments_for_job(row.id, db)
    ]
    response.audio_events = [models.VideoInspirationAudioEventResponse.model_validate(event) for event in _audio_events_for_job(row.id, db)]
    response.on_screen_text_events = [
        models.VideoInspirationTextEventResponse.model_validate(event)
        for event in _text_events_for_job(row.id, db)
    ]
    response.content_retention_beats = [
        models.VideoInspirationRetentionBeatResponse.model_validate(beat)
        for beat in _retention_beats_for_job(row.id, db)
    ]
    response.ai_video_url = f"/ai-video?projectId={row.created_video_project_id}" if row.created_video_project_id else None
    return response

def get_job(job_id: str, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    return _job_response(row, db) if row else None

def list_jobs(db: Session, *, limit: int = 20, offset: int = 0) -> models.VideoInspirationListResponse:
    total = db.query(func.count(DBVideoInspirationJob.id)).scalar() or 0
    rows = (
        db.query(DBVideoInspirationJob)
        .order_by(DBVideoInspirationJob.updated_at.desc(), DBVideoInspirationJob.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return models.VideoInspirationListResponse(items=[_job_response(row, db) for row in rows], total=total)

def create_upload_job(
    *,
    data: bytes,
    filename: str,
    content_type: str | None,
    target_language: str,
    db: Session,
    user_direction: str | None = None,
) -> models.VideoInspirationJobResponse:
    language = _validate_target_language(target_language)
    suffix = Path(filename or "").suffix.lower()
    if suffix != ".mp4":
        raise VideoInspirationError("Hiện tại chỉ nhận file .mp4. Nếu là link mạng xã hội, hãy dùng ô dán link.", error_code="VIDEO_INSPIRATION_MP4_REQUIRED")
    if content_type and content_type not in {"application/octet-stream", "video/mp4"} and not content_type.startswith("video/"):
        raise VideoInspirationError("File tải lên không giống video MP4 hợp lệ.", error_code="VIDEO_INSPIRATION_MIME_INVALID")

    job_id = str(uuid.uuid4())
    source_dir = _job_dir(job_id) / "source"
    source_path = source_dir / f"{_safe_filename(Path(filename).stem, fallback='source')}.mp4"
    written = False
    try:
        source_path.write_bytes(data)
        written = True
        metadata = _validate_video_file(source_path, size_bytes=len(data))
        now = _now()
        row = DBVideoInspirationJob(
            id=job_id,
            source_type="upload",
            source_platform="upload",
            original_filename=filename,
            source_path=config.to_storage_path(source_path),
            source_duration_seconds=metadata.get("duration_seconds"),
            target_language=language,
            user_direction=_clean_user_direction(user_direction),
            status="uploaded",
            current_step="source_ready",
            progress=0.08,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _job_response(row, db)
    except Exception:
        if written:
            shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        raise

def create_url_job(
    *,
    url: str,
    target_language: str,
    db: Session,
    user_direction: str | None = None,
    use_browser_cookies: bool = False,
) -> models.VideoInspirationJobResponse:
    language = _validate_target_language(target_language)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VideoInspirationError("Link video không hợp lệ. Hãy dùng link http/https công khai.", error_code="VIDEO_INSPIRATION_URL_INVALID")

    platform = _source_platform(url)
    if platform == "unknown":
        raise VideoInspirationError(
            "Bản đầu chỉ thử lấy link công khai từ YouTube, TikTok, Facebook hoặc Instagram.",
            error_code="VIDEO_INSPIRATION_PLATFORM_UNSUPPORTED",
        )

    downloader_command = _yt_dlp_command()
    if not downloader_command:
        raise VideoInspirationError(
            "Máy này chưa có yt-dlp để lấy link mạng xã hội. Bạn có thể upload file .mp4 thay thế.",
            error_code="VIDEO_INSPIRATION_DOWNLOADER_MISSING",
        )

    job_id = str(uuid.uuid4())
    source_dir = _job_dir(job_id) / "source"
    output_template = source_dir / "download.%(ext)s"
    failed_result: subprocess.CompletedProcess[str] | None = None
    for command in _yt_dlp_download_attempts(
        downloader_command,
        output_template,
        url,
        use_browser_cookies=use_browser_cookies,
    ):
        _remove_partial_downloads(source_dir)
        result = _run_command(command, timeout_seconds=FFMPEG_TIMEOUT_SECONDS)
        if result.returncode == 0:
            failed_result = None
            break
        failed_result = result
        logger.info(
            "Video inspiration link download attempt failed platform=%s detail=%s",
            platform,
            _download_error_text(result, url),
        )
    if failed_result is not None:
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        raise _download_failure_error(failed_result, url)
    try:
        source_path, metadata = _prepare_downloaded_source(source_dir)
    except Exception:
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        raise

    now = _now()
    row = DBVideoInspirationJob(
        id=job_id,
        source_type="url",
        source_url=_redact_url(url),
        source_platform=platform,
        original_filename=source_path.name,
        source_path=config.to_storage_path(source_path),
        source_duration_seconds=metadata.get("duration_seconds"),
        target_language=language,
        user_direction=_clean_user_direction(user_direction),
        status="uploaded",
        current_step="source_ready",
        progress=0.08,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _job_response(row, db)

def _resolve_source(row: DBVideoInspirationJob) -> Path:
    source_path = config.resolve_storage_path(row.source_path)
    if source_path is None or not source_path.exists():
        raise VideoInspirationError("File video nguồn không còn tồn tại.", error_code="VIDEO_INSPIRATION_SOURCE_MISSING", status_code=404)
    return source_path

def _extract_audio(row: DBVideoInspirationJob) -> Path:
    source_path = _resolve_source(row)
    tools = _require_ffmpeg(ffprobe=False)
    audio_path = _job_dir(row.id) / "audio" / "speech.wav"
    result = _run_command(
        [
            tools.ffmpeg or "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(audio_path),
        ],
    )
    if result.returncode != 0 or not audio_path.exists():
        raise VideoInspirationError(
            "Không tách được âm thanh từ video. Video có thể không có audio hoặc FFmpeg đang lỗi.",
            error_code="VIDEO_INSPIRATION_AUDIO_EXTRACT_FAILED",
        )
    row.audio_path = config.to_storage_path(audio_path)
    return audio_path

def _audio_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as audio_file:
            frame_rate = audio_file.getframerate()
            if frame_rate <= 0:
                return None
            return audio_file.getnframes() / frame_rate
    except (EOFError, OSError, wave.Error):
        return None

def _format_ffmpeg_seconds(value: float) -> str:
    return f"{max(0.0, value):.3f}"

def _is_no_speech_transcript(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    normalized = re.sub(r"[^a-z]+", " ", text.lower()).strip()
    if not normalized:
        return True
    if normalized in _NO_SPEECH_TRANSCRIPT_LABELS:
        return True
    words = normalized.split()
    return bool(words) and set(words).issubset({"music"})

def _clean_transcribed_text(value: str | None) -> str:
    text = (value or "").strip()
    return "" if _is_no_speech_transcript(text) else text

def _extract_audio_transcript_chunk(source_path: Path, chunk_path: Path, *, start_seconds: float, duration_seconds: float) -> None:
    tools = _require_ffmpeg(ffprobe=False)
    result = _run_command(
        [
            tools.ffmpeg or "ffmpeg",
            "-y",
            "-ss",
            _format_ffmpeg_seconds(start_seconds),
            "-t",
            _format_ffmpeg_seconds(duration_seconds),
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(chunk_path),
        ],
    )
    if result.returncode != 0 or not chunk_path.exists() or chunk_path.stat().st_size <= 0:
        raise VideoInspirationError(
            "KhÃ´ng cáº¯t Ä‘Æ°á»£c audio dÃ i Ä‘á»ƒ chuyá»ƒn lá»i nÃ³i thÃ nh chá»¯.",
            error_code="VIDEO_INSPIRATION_AUDIO_CHUNK_FAILED",
        )

def _transcript_audio_windows(path: Path) -> list[tuple[Path, float, float | None, str]]:
    duration = _audio_duration_seconds(path)
    if duration is None or duration <= TRANSCRIPT_SINGLE_PASS_MAX_SECONDS:
        return [(path, 0.0, duration, "file")]

    chunk_dir = path.parent / "transcript_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for old_chunk in chunk_dir.glob("chunk-*.wav"):
        if old_chunk.is_file():
            old_chunk.unlink(missing_ok=True)

    chunks: list[Path] = []
    start = 0.0
    while start < duration:
        chunk_duration = min(TRANSCRIPT_CHUNK_SECONDS, duration - start)
        if chunk_duration <= 0.05:
            break
        chunk_path = chunk_dir / f"chunk-{len(chunks) + 1:03d}.wav"
        _extract_audio_transcript_chunk(
            path,
            chunk_path,
            start_seconds=start,
            duration_seconds=chunk_duration,
        )
        chunks.append(chunk_path)
        start += TRANSCRIPT_CHUNK_SECONDS

    if not chunks:
        return [(path, 0.0, duration, "file")]
    return [
        (
            chunk,
            float(index) * TRANSCRIPT_CHUNK_SECONDS,
            min(TRANSCRIPT_CHUNK_SECONDS, max(0.0, duration - float(index) * TRANSCRIPT_CHUNK_SECONDS)),
            "chunk",
        )
        for index, chunk in enumerate(chunks)
    ]

def _transcript_audio_paths(path: Path) -> list[Path]:
    return [item[0] for item in _transcript_audio_windows(path)]

def _transcription_segments_from_output(
    raw: Any,
    *,
    start_offset: float,
    fallback_duration: float | None,
    default_precision: str,
) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw_segments = raw.get("segments")
        language = raw.get("language")
        if isinstance(raw_segments, list):
            segments: list[dict[str, Any]] = []
            for item in raw_segments:
                if not isinstance(item, dict):
                    continue
                text = _clean_transcribed_text(str(item.get("text") or ""))
                if not text:
                    continue
                start = _float_or_none(item.get("start"))
                end = _float_or_none(item.get("end"))
                confidence = None
                no_speech_prob = _float_or_none(item.get("no_speech_prob"))
                if no_speech_prob is not None:
                    confidence = max(0.0, min(1.0, 1.0 - no_speech_prob))
                segments.append(
                    {
                        "start_seconds": round(start_offset + max(0.0, start or 0.0), 3),
                        "end_seconds": round(start_offset + max(start or 0.0, end or (fallback_duration or 0.0)), 3),
                        "text": text,
                        "raw_text": text,
                        "language": item.get("language") or language,
                        "speaker_label": item.get("speaker") or item.get("speaker_label"),
                        "timestamp_precision": "segment",
                        "confidence": confidence,
                        "source": "stt_raw",
                    }
                )
            if segments:
                return segments
        raw_text = raw.get("text")
    else:
        raw_text = raw
    text = _clean_transcribed_text(str(raw_text or ""))
    if not text:
        return []
    end_seconds = start_offset + (fallback_duration if fallback_duration is not None else 0.0)
    if end_seconds <= start_offset:
        end_seconds = start_offset
    return [
        {
            "start_seconds": round(start_offset, 3),
            "end_seconds": round(end_seconds, 3),
            "text": text,
            "raw_text": text,
            "language": None,
            "speaker_label": None,
            "timestamp_precision": default_precision,
            "confidence": None,
            "source": "stt_raw",
        }
    ]

async def _transcribe_audio_segments(
    path: Path,
    *,
    model_size: str | None,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    whisper = get_whisper_model()
    resolved_model = model_size or getattr(whisper, "model_size", None) or "turbo"
    load_async = getattr(whisper, "load_model_async", None)
    if callable(load_async):
        await load_async(resolved_model)
    segments: list[dict[str, Any]] = []
    for transcript_path, start_offset, duration, precision in _transcript_audio_windows(path):
        raw = await whisper.transcribe(str(transcript_path), None, resolved_model)
        segments.extend(
            _transcription_segments_from_output(
                raw,
                start_offset=start_offset,
                fallback_duration=duration,
                default_precision=precision,
            )
        )
    for index, segment in enumerate(segments, start=1):
        segment["segment_order"] = index
    return "\n".join(segment["text"] for segment in segments), resolved_model, segments

async def _transcribe_audio(path: Path, *, model_size: str | None) -> tuple[str, str | None]:
    text, resolved_model, _segments = await _transcribe_audio_segments(path, model_size=model_size)
    setattr(_transcribe_audio, "last_segments", _segments)
    return text, resolved_model

def _frame_timestamps(duration_seconds: float | None) -> list[float]:
    if not duration_seconds or duration_seconds <= 0:
        return [0.5]
    frame_count = min(MAX_FRAME_COUNT, max(3, int(duration_seconds // 20) + 1))
    if frame_count == 1:
        return [min(duration_seconds / 2, max(0.5, duration_seconds - 0.1))]
    start = min(1.0, max(0.0, duration_seconds * 0.05))
    end = max(start, duration_seconds * 0.95)
    step = (end - start) / max(1, frame_count - 1)
    return [round(min(duration_seconds - 0.1, start + index * step), 2) for index in range(frame_count)]

def _analysis_mode(value: str | None) -> str:
    return "high_quality" if value == "high_quality" else "quick"

def _shot_frame_budget(mode: str) -> int:
    return MAX_HIGH_QUALITY_KEYFRAMES if mode == "high_quality" else MAX_QUICK_KEYFRAMES

def _scene_threshold(mode: str) -> float:
    return SHOT_SCENE_THRESHOLD_HIGH_QUALITY if mode == "high_quality" else SHOT_SCENE_THRESHOLD_QUICK

def _parse_scene_times(stderr: str | None) -> list[float]:
    times: list[float] = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", stderr or ""):
        value = _float_or_none(match.group(1))
        if value is None or value <= 0:
            continue
        if not times or abs(value - times[-1]) > 0.35:
            times.append(round(value, 3))
    return times

def _detect_shot_ranges(source_path: Path, duration_seconds: float | None, *, mode: str) -> list[tuple[float, float]]:
    duration = float(duration_seconds or 0.0)
    if duration <= 0.05:
        return [(0.0, max(0.5, duration or 0.5))]
    tools = _require_ffmpeg(ffprobe=False)
    threshold = _scene_threshold(mode)
    result = _run_command(
        [
            tools.ffmpeg or "ffmpeg",
            "-hide_banner",
            "-i",
            str(source_path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        timeout_seconds=FFMPEG_TIMEOUT_SECONDS,
    )
    boundaries = [value for value in _parse_scene_times(result.stderr) if 0.25 < value < duration - 0.25]
    if result.returncode != 0:
        logger.info("Shot detection fell back to duration windows: %s", _trim_stderr(result.stderr))
        boundaries = []
    if not boundaries and duration > 45:
        window = 18.0 if mode == "high_quality" else 25.0
        boundaries = [round(value, 3) for value in _frange(window, duration, window)]
    points = [0.0, *boundaries, duration]
    ranges: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:]):
        if end - start < 0.2:
            continue
        ranges.append((round(start, 3), round(end, 3)))
    return ranges or [(0.0, duration)]

def _frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    value = start
    while value < stop:
        values.append(value)
        value += step
    return values

def _keyframe_timestamps_for_shot(start: float, end: float, *, remaining_budget: int, mode: str) -> list[float]:
    duration = max(0.0, end - start)
    if duration <= 0.05 or remaining_budget <= 0:
        return []
    epsilon = min(0.12, duration / 5)
    midpoint = start + duration / 2
    timestamps = [midpoint]
    if duration >= LONG_SHOT_SECONDS and remaining_budget >= 3:
        timestamps = [start + duration * 0.25, midpoint, start + duration * 0.75]
    elif mode == "high_quality" and duration >= 8.0 and remaining_budget >= 2:
        timestamps = [start + duration * 0.33, start + duration * 0.67]
    return [
        round(min(max(start + epsilon, value), max(start + epsilon, end - epsilon)), 3)
        for value in timestamps[:remaining_budget]
    ]

def _link_ids_by_overlap(
    ranges: list[tuple[str, float, float]],
    start_seconds: float,
    end_seconds: float,
) -> list[str]:
    links: list[str] = []
    for item_id, item_start, item_end in ranges:
        if max(float(item_start), start_seconds) <= min(float(item_end), end_seconds):
            links.append(item_id)
    return links

def _save_transcript_segments(
    row: DBVideoInspirationJob,
    segment_payloads: list[dict[str, Any]],
    db: Session,
) -> list[DBVideoInspirationTranscriptSegment]:
    db.query(DBVideoInspirationTranscriptSegment).filter(DBVideoInspirationTranscriptSegment.job_id == row.id).delete(synchronize_session=False)
    shot_ranges = [
        (shot.id, float(shot.start_seconds or 0.0), float(shot.end_seconds or 0.0))
        for shot in _shots_for_job(row.id, db)
    ]
    rows: list[DBVideoInspirationTranscriptSegment] = []
    for index, payload in enumerate(segment_payloads, start=1):
        text = _truncate(payload.get("text"), 20000)
        if not text:
            continue
        start_seconds = float(payload.get("start_seconds") or 0.0)
        end_seconds = float(payload.get("end_seconds") or start_seconds)
        segment = DBVideoInspirationTranscriptSegment(
            id=str(uuid.uuid4()),
            job_id=row.id,
            segment_order=int(payload.get("segment_order") or index),
            start_seconds=start_seconds,
            end_seconds=max(start_seconds, end_seconds),
            text=text,
            raw_text=_truncate(payload.get("raw_text"), 20000) or text,
            language=_truncate(payload.get("language"), 24) or row.transcript_language,
            speaker_label=_truncate(payload.get("speaker_label"), 120) or None,
            source=payload.get("source") or "stt_raw",
            timestamp_precision=payload.get("timestamp_precision") or "chunk",
            confidence=_float_or_none(payload.get("confidence")),
            shot_ids_json=_link_ids_by_overlap(shot_ranges, start_seconds, max(start_seconds, end_seconds)),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(segment)
        rows.append(segment)
    db.commit()
    for item in rows:
        db.refresh(item)
    return rows

def _save_user_transcript_edit(row: DBVideoInspirationJob, text: str, db: Session) -> None:
    db.query(DBVideoInspirationTranscriptSegment).filter(
        DBVideoInspirationTranscriptSegment.job_id == row.id,
        DBVideoInspirationTranscriptSegment.source == "user_edited",
    ).delete(synchronize_session=False)
    if not text.strip():
        db.commit()
        return
    shot_ranges = [
        (shot.id, float(shot.start_seconds or 0.0), float(shot.end_seconds or 0.0))
        for shot in _shots_for_job(row.id, db)
    ]
    duration = float(row.source_duration_seconds or 0.0)
    segment = DBVideoInspirationTranscriptSegment(
        id=str(uuid.uuid4()),
        job_id=row.id,
        segment_order=10_000,
        start_seconds=0.0,
        end_seconds=duration,
        text=text,
        raw_text=None,
        language=row.transcript_language,
        speaker_label=None,
        source="user_edited",
        timestamp_precision="file",
        confidence=None,
        shot_ids_json=_link_ids_by_overlap(shot_ranges, 0.0, duration),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(segment)
    db.commit()

def _wav_rms_windows(path: Path, *, window_seconds: float = 1.0) -> list[tuple[float, float, float]]:
    try:
        with wave.open(str(path), "rb") as audio_file:
            frame_rate = audio_file.getframerate()
            sample_width = audio_file.getsampwidth()
            channels = audio_file.getnchannels()
            if frame_rate <= 0 or sample_width != 2:
                return []
            frames_per_window = max(1, int(frame_rate * window_seconds))
            windows: list[tuple[float, float, float]] = []
            index = 0
            while True:
                raw = audio_file.readframes(frames_per_window)
                if not raw:
                    break
                samples = array("h")
                samples.frombytes(raw)
                if sys.byteorder == "big":
                    samples.byteswap()
                if channels > 1:
                    samples = array("h", samples[::channels])
                if not samples:
                    continue
                mean_square = sum(float(value) * float(value) for value in samples) / len(samples)
                rms = math.sqrt(mean_square) / 32768.0
                start = index * window_seconds
                end = start + (len(samples) / frame_rate)
                windows.append((round(start, 3), round(end, 3), round(rms, 6)))
                index += 1
            return windows
    except (EOFError, OSError, wave.Error):
        return []

def _contiguous_low_energy_ranges(windows: list[tuple[float, float, float]], *, threshold: float) -> list[tuple[float, float, float]]:
    ranges: list[tuple[float, float, float]] = []
    current_start: float | None = None
    current_end = 0.0
    values: list[float] = []
    for start, end, rms in windows:
        if rms <= threshold:
            if current_start is None:
                current_start = start
                values = []
            current_end = end
            values.append(rms)
        elif current_start is not None:
            if current_end - current_start >= 0.8:
                ranges.append((current_start, current_end, sum(values) / max(1, len(values))))
            current_start = None
            values = []
    if current_start is not None and current_end - current_start >= 0.8:
        ranges.append((current_start, current_end, sum(values) / max(1, len(values))))
    return ranges

def _save_audio_events(
    row: DBVideoInspirationJob,
    audio_path: Path,
    transcript_segments: list[DBVideoInspirationTranscriptSegment],
    db: Session,
) -> list[DBVideoInspirationAudioEvent]:
    db.query(DBVideoInspirationAudioEvent).filter(DBVideoInspirationAudioEvent.job_id == row.id).delete(synchronize_session=False)
    shot_ranges = [
        (shot.id, float(shot.start_seconds or 0.0), float(shot.end_seconds or 0.0))
        for shot in _shots_for_job(row.id, db)
    ]
    transcript_ranges = [
        (segment.id, float(segment.start_seconds or 0.0), float(segment.end_seconds or 0.0))
        for segment in transcript_segments
    ]
    windows = _wav_rms_windows(audio_path)
    events: list[DBVideoInspirationAudioEvent] = []

    def add_event(
        event_type: str,
        start_seconds: float,
        end_seconds: float,
        description_vi: str,
        *,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = DBVideoInspirationAudioEvent(
            id=str(uuid.uuid4()),
            job_id=row.id,
            event_order=len(events) + 1,
            event_type=event_type,
            start_seconds=round(max(0.0, start_seconds), 3),
            end_seconds=round(max(start_seconds, end_seconds), 3),
            description_vi=description_vi,
            confidence=max(0.0, min(1.0, confidence)),
            technical_metadata_json=metadata or {},
            shot_ids_json=_link_ids_by_overlap(shot_ranges, start_seconds, end_seconds),
            transcript_segment_ids_json=_link_ids_by_overlap(transcript_ranges, start_seconds, end_seconds),
            created_at=_now(),
        )
        db.add(event)
        events.append(event)

    for segment in transcript_segments:
        add_event(
            "speech",
            float(segment.start_seconds or 0.0),
            float(segment.end_seconds or 0.0),
            "Có lời nói trong transcript tại đoạn này.",
            confidence=segment.confidence if segment.confidence is not None else 0.72,
            metadata={"timestamp_precision": segment.timestamp_precision, "source": segment.source},
        )

    if windows:
        rms_values = [item[2] for item in windows]
        average_rms = sum(rms_values) / max(1, len(rms_values))
        low_threshold = max(0.006, min(0.025, average_rms * 0.35))
        for start, end, rms in _contiguous_low_energy_ranges(windows, threshold=low_threshold):
            add_event(
                "silence",
                start,
                end,
                "Khoảng âm lượng rất thấp hoặc im lặng.",
                confidence=0.78,
                metadata={"rms": rms, "threshold": low_threshold},
            )
        for previous, current in zip(windows, windows[1:]):
            delta = current[2] - previous[2]
            if abs(delta) >= max(0.04, average_rms * 1.4):
                add_event(
                    "energy_change",
                    current[0],
                    current[1],
                    "Mức năng lượng âm thanh thay đổi rõ.",
                    confidence=0.68,
                    metadata={"previous_rms": previous[2], "current_rms": current[2], "delta": delta},
                )
        if not transcript_segments and average_rms > low_threshold:
            add_event(
                "ambience",
                0.0,
                float(row.source_duration_seconds or windows[-1][1]),
                "Có âm thanh nền/nhạc/SFX nhưng không xác định tên hoặc nguồn âm thanh.",
                confidence=0.46,
                metadata={"average_rms": average_rms, "classification": "low_confidence_non_speech_audio"},
            )
        if transcript_segments and average_rms > 0.12:
            add_event(
                "possible_audio_clutter",
                0.0,
                float(row.source_duration_seconds or windows[-1][1]),
                "Âm lượng nền tổng thể cao; cần kiểm tra nguy cơ nhạc hoặc SFX che lời.",
                confidence=0.52,
                metadata={"average_rms": average_rms},
            )
    elif not transcript_segments:
        add_event(
            "ambience",
            0.0,
            float(row.source_duration_seconds or 0.0),
            "Không đọc được đặc trưng kỹ thuật âm thanh; chỉ biết video có audio đã tách.",
            confidence=0.2,
            metadata={"limitation": "wav_rms_unavailable"},
        )
    db.commit()
    for item in events:
        db.refresh(item)
    return events

def _clear_frames(row: DBVideoInspirationJob, db: Session) -> None:
    for frame in _frames_for_job(row.id, db):
        resolved = config.resolve_storage_path(frame.frame_path)
        if resolved and resolved.exists():
            resolved.unlink(missing_ok=True)
    db.query(DBVideoInspirationFrame).filter(DBVideoInspirationFrame.job_id == row.id).delete(synchronize_session=False)
    db.commit()

def _clear_timeline(row: DBVideoInspirationJob, db: Session, *, include_frames: bool = True) -> None:
    if include_frames:
        _clear_frames(row, db)
    db.query(DBVideoInspirationTextEvent).filter(DBVideoInspirationTextEvent.job_id == row.id).delete(synchronize_session=False)
    db.query(DBVideoInspirationRetentionBeat).filter(DBVideoInspirationRetentionBeat.job_id == row.id).delete(synchronize_session=False)
    db.query(DBVideoInspirationAudioEvent).filter(DBVideoInspirationAudioEvent.job_id == row.id).delete(synchronize_session=False)
    db.query(DBVideoInspirationTranscriptSegment).filter(DBVideoInspirationTranscriptSegment.job_id == row.id).delete(synchronize_session=False)
    db.query(DBVideoInspirationShot).filter(DBVideoInspirationShot.job_id == row.id).delete(synchronize_session=False)
    db.commit()

def _extract_frames(row: DBVideoInspirationJob, db: Session, *, mode: str | None = None) -> list[DBVideoInspirationFrame]:
    source_path = _resolve_source(row)
    tools = _require_ffmpeg(ffprobe=False)
    metadata = _probe_video(source_path)
    mode = _analysis_mode(mode or getattr(row, "analysis_mode", None))
    duration_seconds = metadata.get("duration_seconds") or row.source_duration_seconds
    shot_ranges = _detect_shot_ranges(source_path, duration_seconds, mode=mode)
    _clear_timeline(row, db, include_frames=True)
    frame_dir = _job_dir(row.id) / "frames"
    rows: list[DBVideoInspirationFrame] = []
    shots: list[DBVideoInspirationShot] = []
    now = _now()
    for order, (start, end) in enumerate(shot_ranges, start=1):
        shot = DBVideoInspirationShot(
            id=str(uuid.uuid4()),
            job_id=row.id,
            shot_order=order,
            start_seconds=start,
            end_seconds=end,
            duration_seconds=max(0.0, end - start),
            keyframe_ids_json=[],
            confidence_json={"shot_boundary": 0.82 if len(shot_ranges) > 1 else 0.58},
            limitations_json=[],
            created_at=now,
            updated_at=now,
        )
        db.add(shot)
        shots.append(shot)
    db.flush()

    max_budget = min(60, max(_shot_frame_budget(mode), len(shots)))
    remaining_budget = max_budget
    frame_index = 1
    for shot in shots:
        timestamps = _keyframe_timestamps_for_shot(
            float(shot.start_seconds or 0.0),
            float(shot.end_seconds or 0.0),
            remaining_budget=max(1, remaining_budget),
            mode=mode,
        )
        frame_ids: list[str] = []
        for timestamp in timestamps:
            if remaining_budget <= 0:
                break
            frame_path = frame_dir / f"shot-{shot.shot_order:03d}-frame-{frame_index:03d}-{int(timestamp * 1000):08d}ms.jpg"
            result = _run_command(
                [
                    tools.ffmpeg or "ffmpeg",
                    "-y",
                    "-ss",
                    str(timestamp),
                    "-i",
                    str(source_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(frame_path),
                ],
                timeout_seconds=90,
            )
            if result.returncode != 0 or not frame_path.exists():
                logger.warning("Failed to extract keyframe at %.2fs: %s", timestamp, _trim_stderr(result.stderr))
                continue
            frame = DBVideoInspirationFrame(
                id=str(uuid.uuid4()),
                job_id=row.id,
                shot_id=shot.id,
                shot_order=shot.shot_order,
                frame_role="keyframe",
                frame_path=config.to_storage_path(frame_path),
                timestamp_seconds=timestamp,
                technical_metadata_json={
                    "source_duration_seconds": duration_seconds,
                    "source_width": metadata.get("width"),
                    "source_height": metadata.get("height"),
                    "shot_id": shot.id,
                    "shot_order": shot.shot_order,
                    "shot_start_seconds": shot.start_seconds,
                    "shot_end_seconds": shot.end_seconds,
                },
                created_at=_now(),
            )
            db.add(frame)
            rows.append(frame)
            frame_ids.append(frame.id)
            frame_index += 1
            remaining_budget -= 1
        shot.keyframe_ids_json = frame_ids
        shot.updated_at = _now()
    if duration_seconds:
        row.source_duration_seconds = duration_seconds
    db.commit()
    for item in rows:
        db.refresh(item)
    return rows

def _provider_ready(db: Session) -> tuple[bool, str, str | None]:
    settings = settings_service.get_ai_planning_settings(db)
    check = ai_planning.check_provider(settings, check_exec=False)
    return bool(check.ready), check.message, check.error_code

def _json_from_ai(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

def _run_structured_ai(db: Session, prompt: str, schema: dict[str, Any], *, timeout_seconds: int = AI_TIMEOUT_SECONDS) -> dict[str, Any]:
    settings = settings_service.get_ai_planning_settings(db)
    job_id = _AI_JOB_ID.get()
    step_name = _AI_STEP_NAME.get()

    def run() -> str:
        return ai_planning.run_codex_exec(
            settings,
            prompt,
            output_schema=schema,
            timeout_seconds=timeout_seconds,
        )

    if job_id:
        with video_planning_pool.planning_slot(
            db,
            project_id=None,
            work_key=f"video-inspiration:{job_id}",
            workflow_type="video_inspiration",
            job_id=job_id,
            step_name=step_name,
            provider=settings.provider,
            model=settings.model,
            details={"prompt_chars": len(prompt), "schema_keys": sorted((schema.get("properties") or {}).keys())[:20]},
        ):
            raw = run()
    else:
        raw = run()
    try:
        return _json_from_ai(raw)
    except json.JSONDecodeError as exc:
        raise VideoInspirationError(
            "AI trả về kết quả không đúng cấu trúc. Hãy thử chạy lại bước này.",
            error_code="VIDEO_INSPIRATION_AI_INVALID_JSON",
        ) from exc


async def _run_structured_ai_in_thread(
    db: Session,
    prompt: str,
    schema: dict[str, Any],
    *,
    timeout_seconds: int = AI_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Keep blocking Codex subprocess execution off the server event loop."""
    return await asyncio.to_thread(
        _run_structured_ai,
        db,
        prompt,
        schema,
        timeout_seconds=timeout_seconds,
    )

VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary_vi": {"type": "string"},
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "shot_order": {"type": "number"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "visual_description_vi": {"type": "string"},
                    "subjects": {"type": "array", "items": {"type": "string"}},
                    "setting": {"type": "array", "items": {"type": "string"}},
                    "camera": {"type": "string"},
                    "subject_motion": {"type": "array", "items": {"type": "string"}},
                    "transition_in": {"type": "string"},
                    "transition_out": {"type": "string"},
                    "on_screen_text": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "text": {"type": "string"},
                                "role": {"type": "string"},
                                "language": {"type": "string"},
                                "region": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["text", "role", "language", "region", "confidence"],
                        },
                    },
                    "confidence": {"type": "number"},
                    "limitations": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "shot_order",
                    "start_seconds",
                    "end_seconds",
                    "visual_description_vi",
                    "subjects",
                    "setting",
                    "camera",
                    "subject_motion",
                    "transition_in",
                    "transition_out",
                    "on_screen_text",
                    "confidence",
                    "limitations",
                ],
            },
        },
        "frames": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "timestamp_seconds": {"type": "number"},
                    "description_vi": {"type": "string"},
                },
                "required": ["timestamp_seconds", "description_vi"],
            },
        },
        "limitations_vi": {"type": "string"},
    },
    "required": ["summary_vi", "shots", "frames", "limitations_vi"],
}

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "main_idea_vi": {"type": "string"},
        "hook_vi": {"type": "string"},
        "structure_vi": {"type": "string"},
        "characters_context_vi": {"type": "string"},
        "visual_rhythm_vi": {"type": "string"},
        "strengths_vi": {"type": "array", "items": {"type": "string"}},
        "weaknesses_vi": {"type": "array", "items": {"type": "string"}},
        "rewrite_opportunities_vi": {"type": "array", "items": {"type": "string"}},
        "content_retention_beats": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "order": {"type": "number"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "role": {"type": "string"},
                    "viewer_question_before": {"type": "string"},
                    "content_promise": {"type": "string"},
                    "new_information": {"type": "string"},
                    "emotional_or_stakes_change": {"type": "string"},
                    "question_answered": {"type": "string"},
                    "new_open_loop": {"type": "string"},
                    "micro_payoff": {"type": "string"},
                    "why_continue": {"type": "string"},
                    "drop_off_risks": {"type": "array", "items": {"type": "string"}},
                    "evidence_refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "type": {"type": "string"},
                                "id": {"type": "string"},
                            },
                            "required": ["type", "id"],
                        },
                    },
                    "confidence": {"type": "number"},
                },
                "required": [
                    "order",
                    "start_seconds",
                    "end_seconds",
                    "role",
                    "viewer_question_before",
                    "content_promise",
                    "new_information",
                    "emotional_or_stakes_change",
                    "question_answered",
                    "new_open_loop",
                    "micro_payoff",
                    "why_continue",
                    "drop_off_risks",
                    "evidence_refs",
                    "confidence",
                ],
            },
        },
        "hook_analysis": {"type": "string"},
        "story_structure": {"type": "string"},
        "visual_grammar": {"type": "string"},
        "audio_grammar": {"type": "string"},
        "originality_boundaries": {"type": "array", "items": {"type": "string"}},
        "coverage_notes": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "notes_vi": {"type": "string"},
    },
    "required": [
        "main_idea_vi",
        "hook_vi",
        "structure_vi",
        "characters_context_vi",
        "visual_rhythm_vi",
        "strengths_vi",
        "weaknesses_vi",
        "rewrite_opportunities_vi",
        "content_retention_beats",
        "hook_analysis",
        "story_structure",
        "visual_grammar",
        "audio_grammar",
        "originality_boundaries",
        "coverage_notes",
        "limitations",
        "notes_vi",
    ],
}

RETENTION_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "viewer_question": {"type": "string"},
        "curiosity_gap": {"type": "string"},
        "beat_curve": {"type": "array", "items": {"type": "string"}},
        "pattern_interrupts": {"type": "array", "items": {"type": "string"}},
        "payoff": {"type": "string"},
        "drop_off_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["viewer_question", "curiosity_gap", "beat_curve", "pattern_interrupts", "payoff", "drop_off_risks"],
}

SOUND_CUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "timing": {"type": "string"},
        "cue": {"type": "string"},
        "purpose": {"type": "string"},
    },
    "required": ["timing", "cue", "purpose"],
}

SOUND_DESIGN_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "music_mood": {"type": "string"},
        "ambience": {"type": "string"},
        "sfx_cues": {"type": "array", "items": SOUND_CUE_SCHEMA},
        "silence_drops": {"type": "array", "items": {"type": "string"}},
        "mixing_notes": {"type": "string"},
    },
    "required": ["music_mood", "ambience", "sfx_cues", "silence_drops", "mixing_notes"],
}

REWRITE_SEGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "narration": {"type": "string"},
        "visual_suggestion": {"type": "string"},
        "retention_role": {"type": "string"},
        "audio_cue": {"type": "string"},
    },
    "required": ["title", "narration", "visual_suggestion", "retention_role", "audio_cue"],
}

AI_VIDEO_SOURCE_BLOCKS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "idea": {"type": "string"},
        "rough_script": {"type": "string"},
        "character_notes": {"type": "string"},
        "style_notes": {"type": "string"},
        "must_have": {"type": "string"},
        "avoid": {"type": "string"},
    },
    "required": ["idea", "rough_script", "character_notes", "style_notes", "must_have", "avoid"],
}

REWRITE_PAYLOAD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "big_idea": {"type": "string"},
        "hook": {"type": "string"},
        "hook_3_5s": {"type": "string"},
        "viewer_question": {"type": "string"},
        "curiosity_gap": {"type": "string"},
        "script": {"type": "string"},
        "segments": {"type": "array", "items": REWRITE_SEGMENT_SCHEMA},
        "visual_suggestions": {"type": "array", "items": {"type": "string"}},
        "retention_plan": RETENTION_PLAN_SCHEMA,
        "sound_design_plan": SOUND_DESIGN_PLAN_SCHEMA,
        "audio_direction": {"type": "string"},
        "ai_video_source_blocks": AI_VIDEO_SOURCE_BLOCKS_SCHEMA,
        "originality_note": {"type": "string"},
    },
    "required": [
        "title",
        "big_idea",
        "hook",
        "hook_3_5s",
        "viewer_question",
        "curiosity_gap",
        "script",
        "segments",
        "visual_suggestions",
        "retention_plan",
        "sound_design_plan",
        "audio_direction",
        "ai_video_source_blocks",
        "originality_note",
    ],
}

CREATIVE_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "strategy_summary": {"type": "string"},
        "core_insight": {"type": "string"},
        "audience_promise": {"type": "string"},
        "visual_direction": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "candidate_angles": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["strategy_summary", "core_insight", "audience_promise", "visual_direction", "constraints", "candidate_angles"],
}

REWRITE_CANDIDATES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": REWRITE_PAYLOAD_SCHEMA,
        },
    },
    "required": ["candidates"],
}

REWRITE_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "candidate_index": {"type": "number"},
                    "score": {"type": "number"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "best_parts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["candidate_index", "score", "strengths", "weaknesses", "best_parts"],
            },
        },
        "synthesis_direction": {"type": "string"},
    },
    "required": ["reviews", "synthesis_direction"],
}

REWRITE_SCHEMA: dict[str, Any] = REWRITE_PAYLOAD_SCHEMA

def _visual_analysis_prompt(frames: list[DBVideoInspirationFrame]) -> str:
    frame_lines = "\n".join(
        f"- shot {frame.shot_order or '?'} @ {frame.timestamp_seconds:.2f}s: {config.resolve_storage_path(frame.frame_path)}"
        for frame in frames
    )
    return f"""
Bạn là bộ phân tích hình ảnh video theo shot. Chỉ phân tích dựa trên các file ảnh keyframe dưới đây, không dùng transcript và không đoán khi không nhìn được ảnh.

Keyframe cần xem:
{frame_lines}

Yêu cầu:
- Trả tiếng Việt.
- Nhóm theo shot_order. Mỗi shot phải có mô tả chủ thể, bối cảnh, ánh sáng/màu, bố cục, camera, chuyển động chủ thể, transition vào/ra nếu quan sát được.
- Trích chữ trên màn hình nếu thấy: text, vai trò nội dung (hook/title/evidence/cta/source_subtitle/unknown), ngôn ngữ, vùng tương đối và confidence.
- Nếu không đủ frame để khẳng định chuyển động camera/chủ thể, ghi confidence thấp hoặc limitations, không khẳng định chắc.
- Nếu môi trường không cho bạn xem ảnh, phải nói rõ trong limitations_vi và không bịa nội dung hình ảnh.
- Chỉ trả JSON đúng schema.
""".strip()

def _timeline_context_for_prompt(row: DBVideoInspirationJob, db: Session) -> str:
    shots = [
        {
            "id": shot.id,
            "shot_order": shot.shot_order,
            "start_seconds": shot.start_seconds,
            "end_seconds": shot.end_seconds,
            "duration_seconds": shot.duration_seconds,
            "visual_description_vi": shot.visual_description_vi,
            "camera": shot.camera_json,
            "subject_motion": shot.subject_motion_json,
            "on_screen_text": shot.on_screen_text_json,
        }
        for shot in _shots_for_job(row.id, db)
    ]
    transcript_segments = [
        {
            "id": segment.id,
            "segment_order": segment.segment_order,
            "start_seconds": segment.start_seconds,
            "end_seconds": segment.end_seconds,
            "text": segment.text,
            "source": segment.source,
            "timestamp_precision": segment.timestamp_precision,
            "shot_ids": segment.shot_ids_json,
        }
        for segment in _transcript_segments_for_job(row.id, db)
        if segment.source != "user_edited"
    ]
    audio_events = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "start_seconds": event.start_seconds,
            "end_seconds": event.end_seconds,
            "description_vi": event.description_vi,
            "confidence": event.confidence,
        }
        for event in _audio_events_for_job(row.id, db)
    ]
    text_events = [
        {
            "id": event.id,
            "shot_id": event.shot_id,
            "start_seconds": event.start_seconds,
            "end_seconds": event.end_seconds,
            "text": event.text,
            "role": event.role,
            "confidence": event.confidence,
        }
        for event in _text_events_for_job(row.id, db)
    ]
    return json.dumps(
        {
            "shots": shots,
            "transcript_segments": transcript_segments,
            "audio_events": audio_events,
            "on_screen_text_events": text_events,
            "retention_source": "predicted_from_content",
        },
        ensure_ascii=False,
        indent=2,
    )

def _analysis_prompt(row: DBVideoInspirationJob, db: Session) -> str:
    return f"""
Bạn là biên tập viên video kiêm strategist nội dung. Hãy phân tích video gốc bằng tiếng Việt trước khi viết lại.

Transcript đã nhận:
{_truncate(row.transcript_text, 50000)}

Tóm tắt hình ảnh:
{_truncate(row.visual_summary, 20000)}

Timeline đa phương thức đã trích xuất:
{_truncate(_timeline_context_for_prompt(row, db), 70000)}

Định hướng phát triển thêm từ người dùng:
{_truncate(row.user_direction, 20000) or "Không có"}

Yêu cầu:
- Phân tích ý chính, hook, cấu trúc, nhân vật/bối cảnh, nhịp dựng, điểm mạnh/yếu và cơ hội viết mới.
- Chia nội dung thành các beat retention theo timestamp. Tỷ trọng phân tích: 75% nội dung, 25% cách thể hiện.
- Mỗi beat phải nêu câu hỏi người xem đang giữ, thông tin mới, micro-payoff, vòng mở mới, rủi ro drop-off và evidence_refs tới shot/transcript/audio/text.
- Dùng nhãn retention_source = predicted_from_content trong ý nghĩa phân tích; không khẳng định đây là dữ liệu retention thực tế.
- Nếu có định hướng từ người dùng, hãy chỉ ra cơ hội phát triển phù hợp với định hướng đó nhưng không bóp méo nội dung video gốc.
- Nếu thiếu hình ảnh hoặc transcript thì ghi rõ phần thiếu, không nói như đã xem đầy đủ.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_prompt(row: DBVideoInspirationJob) -> str:
    language_label = video_language.video_language_prompt_label(row.target_language)
    return f"""
Bạn là biên kịch video ngắn. Hãy lấy cảm hứng từ video gốc nhưng viết mới mạnh tay, không paraphrase sát và không copy nguyên văn.

Ngôn ngữ kịch bản mới: {language_label}
Chế độ rewrite: bold_remix

Transcript gốc:
{_truncate(row.transcript_text, 50000)}

Phân tích tiếng Việt:
{json.dumps(row.analysis_json or {}, ensure_ascii=False)}

Tóm tắt hình ảnh:
{_truncate(row.visual_summary, 20000)}

Định hướng phát triển thêm từ người dùng:
{_truncate(row.user_direction, 20000) or "Không có"}

Yêu cầu:
- Có thể thay hook, cấu trúc, ví dụ, nhịp kể, payoff và cách mở.
- Giữ insight/cảm hứng chính, nhưng tạo thành kịch bản mới đủ khác.
- Nếu người dùng có định hướng riêng, phải bám theo định hướng đó khi chọn phong cách, nhân vật, bối cảnh, hình thức thể hiện và visual suggestions.
- Kết quả phải dễ đưa sang AI Video: có title, big idea, hook, script/narration chính, segments và visual suggestions.
- script và narration trong segments dùng đúng ngôn ngữ kịch bản mới.
- originality_note nhắc rõ đây là bản phát triển mới từ cảm hứng, không phải bản chép lại.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_context(row: DBVideoInspirationJob) -> str:
    language_label = video_language.video_language_prompt_label(row.target_language)
    analysis = {
        key: value
        for key, value in (row.analysis_json or {}).items()
        if key != "rewrite" and not key.startswith("rewrite_")
    }
    context = {
        "target_language": language_label,
        "rewrite_mode": row.rewrite_mode or "bold_remix",
        "transcript": _truncate(row.transcript_text, 50000),
        "analysis_vi": analysis,
        "visual_summary": _truncate(row.visual_summary, 20000),
        "user_direction": _truncate(row.user_direction, 20000) or "Không có",
    }
    return json.dumps(context, ensure_ascii=False, indent=2)

def _creative_brief_prompt(row: DBVideoInspirationJob) -> str:
    return f"""
Bạn là strategist nội dung video ngắn. Hãy tạo creative brief ngắn để chuẩn bị viết kịch bản tối ưu nhiều bước.

Dữ liệu đầu vào:
{_rewrite_context(row)}

Yêu cầu:
- Trả bằng tiếng Việt để người dùng dễ hiểu.
- Tóm tắt insight chính, lời hứa với người xem, hướng hình ảnh và các ràng buộc cần giữ.
- Đề xuất 2-3 hướng candidate khác nhau, ưu tiên hook 3-5 giây, retention và sound design.
- Không viết full script ở bước này.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_candidates_prompt(row: DBVideoInspirationJob, creative_brief: dict[str, Any]) -> str:
    language_label = video_language.video_language_prompt_label(row.target_language)
    return f"""
Bạn là biên kịch video ngắn. Hãy tạo đúng 2 bản nháp kịch bản khác hướng từ creative brief và dữ liệu gốc.

Ngôn ngữ script/narration của bản mới: {language_label}
Chế độ rewrite: bold_remix

Dữ liệu đầu vào:
{_rewrite_context(row)}

Creative brief:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

Yêu cầu cho mỗi candidate:
- Có đủ title, big_idea, hook, hook_3_5s, viewer_question, curiosity_gap, script, segments, visual_suggestions, retention_plan, sound_design_plan, audio_direction, ai_video_source_blocks và originality_note.
- hook_3_5s phải mô tả rõ 3-5 giây đầu: người xem thấy gì, nghe gì, câu hỏi/xung đột nào khiến họ ở lại.
- retention_plan phải có viewer question, curiosity gap, beat curve, pattern interrupt, payoff và rủi ro tụt retention.
- sound_design_plan chỉ là hướng dựng, chưa phải file âm thanh thật; phải có music mood, ambience, SFX cue, silence drop nếu phù hợp và mixing notes để voice không bị che.
- ai_video_source_blocks phải chia sẵn cho AI Video: idea, rough_script, character_notes, style_notes, must_have, avoid.
- Hai candidate phải khác hướng rõ ràng, không chỉ đổi câu chữ.
- Không copy sát transcript/video gốc.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_review_prompt(
    row: DBVideoInspirationJob,
    creative_brief: dict[str, Any],
    candidates: dict[str, Any],
) -> str:
    return f"""
Bạn là editor trưởng. Hãy chấm điểm các candidate bằng tiếng Việt trước khi tổng hợp bản cuối.

Ngữ cảnh:
{_rewrite_context(row)}

Creative brief:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

Candidates:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Rubric:
- Hook 3-5 giây đầu có giữ chân người xem không.
- Ý tưởng có rõ, khác video gốc và dễ dựng thành AI Video không.
- Retention có câu hỏi người xem, curiosity gap, beat curve, pattern interrupt và payoff không.
- Sound design/audio direction có giúp nhịp dựng, không che narration không.
- Có bám định hướng người dùng và đúng ngôn ngữ đầu ra không.

Yêu cầu:
- Chấm từng candidate, chỉ ra strengths, weaknesses và best_parts.
- synthesis_direction phải nói rõ nên lấy phần nào từ candidate nào để tạo bản cuối tốt nhất.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_synthesis_prompt(
    row: DBVideoInspirationJob,
    creative_brief: dict[str, Any],
    candidates: dict[str, Any],
    review: dict[str, Any],
) -> str:
    language_label = video_language.video_language_prompt_label(row.target_language)
    return f"""
Bạn là biên kịch kiêm producer AI Video. Hãy tổng hợp bản kịch bản tối ưu cuối cùng từ creative brief, candidates và review.

Ngôn ngữ script/narration cuối: {language_label}
Chế độ rewrite: bold_remix

Ngữ cảnh gốc:
{_rewrite_context(row)}

Creative brief:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

Candidates:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Review:
{json.dumps(review, ensure_ascii=False, indent=2)}

Yêu cầu bắt buộc:
- Trả đúng một bản cuối nhất quán, không trả nhiều lựa chọn.
- Bản cuối có thể lấy hook của candidate A, cấu trúc của candidate B và sound design của candidate khác, nhưng phải mượt và thống nhất.
- hook_3_5s không được chỉ là tiêu đề. Nó phải mô tả cụ thể 3-5 giây đầu: hành động/hình ảnh mở, âm thanh mở, câu hỏi hoặc xung đột giữ chân.
- script và narration trong segments phải dùng đúng ngôn ngữ script/narration cuối.
- retention_plan phải đủ để AI Video phát triển tiếp thành nhịp shot.
- sound_design_plan và audio_direction là chỉ dẫn dựng âm thanh, không nói như thể file MP4 đã có nhạc/SFX thật.
- ai_video_source_blocks phải điền sẵn idea, rough_script, character_notes, style_notes, must_have, avoid. Đưa retention, sound design, audio direction và hook 3-5s vào các block phù hợp.
- Dữ liệu dài để trong source blocks; visual style chỉ cần tóm tắt ngắn khi handoff.
- originality_note phải nói rõ đây là bản phát triển mới từ cảm hứng, không copy sát video gốc.
- Chỉ trả JSON đúng schema.
""".strip()

def _validate_candidate_payload(candidates: dict[str, Any]) -> None:
    items = candidates.get("candidates") if isinstance(candidates, dict) else None
    if not isinstance(items, list) or len(items) < 2:
        raise VideoInspirationError(
            "AI chưa tạo đủ ít nhất 2 bản nháp kịch bản để chấm điểm.",
            error_code="VIDEO_INSPIRATION_REWRITE_INCOMPLETE",
        )

def _has_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return value is not None

def _validate_optimized_rewrite_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise VideoInspirationError(
            "AI chưa trả đúng dữ liệu kịch bản tối ưu.",
            error_code="VIDEO_INSPIRATION_REWRITE_INCOMPLETE",
        )
    required_fields = [
        "title",
        "big_idea",
        "hook",
        "hook_3_5s",
        "viewer_question",
        "curiosity_gap",
        "script",
        "segments",
        "visual_suggestions",
        "retention_plan",
        "sound_design_plan",
        "audio_direction",
        "ai_video_source_blocks",
        "originality_note",
    ]
    missing = [field for field in required_fields if not _has_content(payload.get(field))]
    retention = payload.get("retention_plan") if isinstance(payload.get("retention_plan"), dict) else {}
    for field in ["viewer_question", "curiosity_gap", "beat_curve", "pattern_interrupts", "payoff", "drop_off_risks"]:
        if not _has_content(retention.get(field)):
            missing.append(f"retention_plan.{field}")
    sound = payload.get("sound_design_plan") if isinstance(payload.get("sound_design_plan"), dict) else {}
    for field in ["music_mood", "ambience", "sfx_cues", "silence_drops", "mixing_notes"]:
        if not _has_content(sound.get(field)):
            missing.append(f"sound_design_plan.{field}")
    source_blocks = payload.get("ai_video_source_blocks") if isinstance(payload.get("ai_video_source_blocks"), dict) else {}
    for field in ["idea", "rough_script", "character_notes", "style_notes", "must_have", "avoid"]:
        if not _has_content(source_blocks.get(field)):
            missing.append(f"ai_video_source_blocks.{field}")
    if missing:
        raise VideoInspirationError(
            "AI trả thiếu dữ liệu kịch bản tối ưu: " + ", ".join(sorted(set(missing))),
            error_code="VIDEO_INSPIRATION_REWRITE_INCOMPLETE",
        )

def _format_json_section(value: Any) -> str:
    if isinstance(value, list):
        lines = []
        for item in value:
            text = _format_json_section(item)
            if text:
                lines.append(text if text.startswith("- ") else f"- {text}")
        return "\n".join(lines)
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            text = _format_json_section(item)
            if not text:
                continue
            label = str(key).replace("_", " ")
            if "\n" in text:
                lines.append(f"{label}:\n{text}")
            else:
                lines.append(f"{label}: {text}")
        return "\n".join(lines)
    return str(value or "").strip()

def _format_optimized_script(payload: dict[str, Any]) -> str:
    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    segment_lines = []
    for index, item in enumerate(segments, start=1):
        if not isinstance(item, dict):
            continue
        segment_lines.append(
            "\n".join(
                part
                for part in [
                    f"{index}. {_truncate(item.get('title'), 400)}",
                    f"Narration: {_truncate(item.get('narration'), 4000)}",
                    f"Gợi ý hình ảnh: {_truncate(item.get('visual_suggestion'), 4000)}",
                    f"Nhịp giữ chân: {_truncate(item.get('retention_role'), 4000)}",
                    f"Âm thanh: {_truncate(item.get('audio_cue'), 4000)}",
                ]
                if part.split(": ", 1)[-1].strip()
            )
        )
    sections = [
        ("Tiêu đề", payload.get("title")),
        ("Big idea", payload.get("big_idea")),
        ("Hook 3-5 giây", payload.get("hook_3_5s") or payload.get("hook")),
        ("Câu hỏi giữ chân người xem", payload.get("viewer_question")),
        ("Khoảng tò mò", payload.get("curiosity_gap")),
        ("Kịch bản", payload.get("script")),
        ("Cấu trúc đoạn/cảnh", "\n\n".join(segment_lines)),
        ("Nhịp giữ chân", _format_json_section(payload.get("retention_plan"))),
        ("Âm thanh / sound design", _format_json_section(payload.get("sound_design_plan"))),
        ("Hướng âm thanh", payload.get("audio_direction")),
        ("Gợi ý hình ảnh", _format_json_section(payload.get("visual_suggestions"))),
        ("Ghi chú originality", payload.get("originality_note")),
    ]
    return "\n\n".join(
        f"{label}:\n{str(value).strip()}"
        for label, value in sections
        if str(value or "").strip()
    ).strip()

def _jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None
    return {"description": str(value)}

def _apply_visual_payload(row: DBVideoInspirationJob, frames: list[DBVideoInspirationFrame], payload: dict[str, Any], db: Session) -> None:
    by_timestamp = {
        round(float(item.get("timestamp_seconds", 0)), 2): item.get("description_vi", "")
        for item in payload.get("frames", [])
        if isinstance(item, dict)
    }
    for frame in frames:
        frame.description_vi = _truncate(by_timestamp.get(round(float(frame.timestamp_seconds), 2), ""), 12000)
    shots_by_order = {int(shot.shot_order): shot for shot in _shots_for_job(row.id, db)}
    db.query(DBVideoInspirationTextEvent).filter(DBVideoInspirationTextEvent.job_id == row.id).delete(synchronize_session=False)
    text_order = 1
    for item in payload.get("shots", []) if isinstance(payload.get("shots"), list) else []:
        if not isinstance(item, dict):
            continue
        order = _int_or_none(item.get("shot_order"))
        if order is None or order not in shots_by_order:
            continue
        shot = shots_by_order[order]
        shot.visual_description_vi = _truncate(item.get("visual_description_vi"), 12000)
        shot.subjects_json = _jsonish(item.get("subjects"))
        shot.setting_json = _jsonish(item.get("setting"))
        shot.camera_json = _jsonish(item.get("camera"))
        shot.subject_motion_json = _jsonish(item.get("subject_motion"))
        shot.transition_in = _truncate(item.get("transition_in"), 120)
        shot.transition_out = _truncate(item.get("transition_out"), 120)
        on_screen_text = item.get("on_screen_text") if isinstance(item.get("on_screen_text"), list) else []
        shot.on_screen_text_json = on_screen_text
        confidence = item.get("confidence")
        shot.confidence_json = confidence if isinstance(confidence, dict) else {"visual": _float_or_none(confidence)}
        limitations = item.get("limitations")
        shot.limitations_json = limitations if isinstance(limitations, list) else ([limitations] if limitations else [])
        shot.updated_at = _now()
        for text_item in on_screen_text:
            if not isinstance(text_item, dict):
                continue
            text_value = _truncate(text_item.get("text"), 4000)
            if not text_value:
                continue
            event = DBVideoInspirationTextEvent(
                id=str(uuid.uuid4()),
                job_id=row.id,
                shot_id=shot.id,
                event_order=text_order,
                start_seconds=float(shot.start_seconds or 0.0),
                end_seconds=float(shot.end_seconds or 0.0),
                text=text_value,
                language=_truncate(text_item.get("language"), 24) or None,
                role=_truncate(text_item.get("role"), 80) or "unknown",
                region_json=_jsonish(text_item.get("region")),
                confidence=_float_or_none(text_item.get("confidence")),
                source="vision",
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(event)
            text_order += 1
    summary = payload.get("summary_vi") or ""
    limitations = payload.get("limitations_vi") or ""
    row.visual_summary = "\n\n".join(part for part in (summary.strip(), limitations.strip()) if part)
    db.commit()

def _save_retention_beats(
    row: DBVideoInspirationJob,
    analysis_payload: dict[str, Any],
    db: Session,
) -> list[DBVideoInspirationRetentionBeat]:
    db.query(DBVideoInspirationRetentionBeat).filter(DBVideoInspirationRetentionBeat.job_id == row.id).delete(synchronize_session=False)
    payload_beats = analysis_payload.get("content_retention_beats")
    beats = payload_beats if isinstance(payload_beats, list) else []
    if not beats:
        transcript_segments = _transcript_segments_for_job(row.id, db)
        shots = _shots_for_job(row.id, db)
        if transcript_segments:
            beats = [
                {
                    "order": segment.segment_order,
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "role": "information",
                    "viewer_question_before": "Người xem chờ thông tin tiếp theo trong lời kể.",
                    "content_promise": "Tiếp tục mạch nội dung từ transcript.",
                    "new_information": segment.text,
                    "emotional_or_stakes_change": "",
                    "question_answered": "",
                    "new_open_loop": "",
                    "micro_payoff": "",
                    "why_continue": "Đoạn lời nói này đang cung cấp dữ liệu mới hoặc nối tiếp mạch lập luận.",
                    "drop_off_risks": [],
                    "evidence_refs": [{"type": "transcript_segment", "id": segment.id}],
                    "confidence": 0.42,
                }
                for segment in transcript_segments[:12]
            ]
        elif shots:
            beats = [
                {
                    "order": shot.shot_order,
                    "start_seconds": shot.start_seconds,
                    "end_seconds": shot.end_seconds,
                    "role": "visual_context",
                    "viewer_question_before": "Người xem dựa vào hình ảnh vì chưa có transcript.",
                    "content_promise": "",
                    "new_information": shot.visual_description_vi or "Shot hình ảnh chưa có mô tả chắc chắn.",
                    "emotional_or_stakes_change": "",
                    "question_answered": "",
                    "new_open_loop": "",
                    "micro_payoff": "",
                    "why_continue": "Beat này chỉ là dự đoán từ hình ảnh, confidence thấp hơn transcript.",
                    "drop_off_risks": ["Thiếu lời nói hoặc mô tả nội dung cụ thể."],
                    "evidence_refs": [{"type": "shot", "id": shot.id}],
                    "confidence": 0.28,
                }
                for shot in shots[:12]
            ]
    rows: list[DBVideoInspirationRetentionBeat] = []
    for index, item in enumerate(beats, start=1):
        if not isinstance(item, dict):
            continue
        start_seconds = float(item.get("start_seconds") or 0.0)
        end_seconds = float(item.get("end_seconds") or start_seconds)
        beat = DBVideoInspirationRetentionBeat(
            id=str(uuid.uuid4()),
            job_id=row.id,
            beat_order=int(item.get("order") or index),
            start_seconds=start_seconds,
            end_seconds=max(start_seconds, end_seconds),
            role=_truncate(item.get("role"), 80) or "development",
            viewer_question_before=_truncate(item.get("viewer_question_before"), 4000) or None,
            content_promise=_truncate(item.get("content_promise"), 4000) or None,
            new_information=_truncate(item.get("new_information"), 8000) or None,
            emotional_or_stakes_change=_truncate(item.get("emotional_or_stakes_change"), 4000) or None,
            question_answered=_truncate(item.get("question_answered"), 4000) or None,
            new_open_loop=_truncate(item.get("new_open_loop"), 4000) or None,
            micro_payoff=_truncate(item.get("micro_payoff"), 4000) or None,
            why_continue=_truncate(item.get("why_continue"), 4000) or None,
            drop_off_risks_json=item.get("drop_off_risks") if isinstance(item.get("drop_off_risks"), list) else [],
            evidence_refs_json=item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else [],
            confidence=_float_or_none(item.get("confidence")),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(beat)
        rows.append(beat)
    db.commit()
    for item in rows:
        db.refresh(item)
    return rows

def _interval_coverage(items: list[tuple[float, float]], duration_seconds: float) -> float:
    if duration_seconds <= 0 or not items:
        return 0.0
    merged: list[tuple[float, float]] = []
    for start, end in sorted((max(0.0, a), max(0.0, b)) for a, b in items if b > a):
        if not merged or start > merged[-1][1]:
            merged.append((start, min(duration_seconds, end)))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], min(duration_seconds, end)))
    covered = sum(max(0.0, end - start) for start, end in merged)
    return round(min(1.0, covered / duration_seconds), 4)

def _coverage_metrics(row: DBVideoInspirationJob, db: Session) -> tuple[dict[str, Any], list[str], str]:
    duration = float(row.source_duration_seconds or 0.0)
    shots = _shots_for_job(row.id, db)
    transcript_segments = [segment for segment in _transcript_segments_for_job(row.id, db) if segment.source != "user_edited"]
    audio_events = _audio_events_for_job(row.id, db)
    beats = _retention_beats_for_job(row.id, db)
    visual_described = [shot for shot in shots if (shot.visual_description_vi or "").strip()]
    metrics = {
        "duration_seconds": duration,
        "shot_count": len(shots),
        "keyframe_count": len(_frames_for_job(row.id, db)),
        "transcript_segment_count": len(transcript_segments),
        "audio_event_count": len(audio_events),
        "on_screen_text_event_count": len(_text_events_for_job(row.id, db)),
        "content_retention_beat_count": len(beats),
        "shot_coverage_ratio": _interval_coverage([(shot.start_seconds, shot.end_seconds) for shot in shots], duration),
        "visual_description_coverage_ratio": _interval_coverage(
            [(shot.start_seconds, shot.end_seconds) for shot in visual_described],
            duration,
        ),
        "transcript_coverage_ratio": _interval_coverage(
            [(segment.start_seconds, segment.end_seconds) for segment in transcript_segments],
            duration,
        ),
        "audio_event_coverage_ratio": _interval_coverage(
            [(event.start_seconds, event.end_seconds) for event in audio_events],
            duration,
        ),
        "retention_beat_coverage_ratio": _interval_coverage(
            [(beat.start_seconds, beat.end_seconds) for beat in beats],
            duration,
        ),
    }
    limitations: list[str] = []
    if not shots:
        limitations.append("Chưa phát hiện được shot timeline.")
    if metrics["visual_description_coverage_ratio"] < 0.75:
        limitations.append("Mô tả hình ảnh chưa phủ đủ thời lượng video.")
    if not transcript_segments:
        limitations.append("Transcript trống hoặc video không có lời nói nhận diện được.")
    if not audio_events:
        limitations.append("Chưa có timeline âm thanh độc lập.")
    if not beats:
        limitations.append("Chưa có beat retention dự đoán.")
    if metrics["shot_coverage_ratio"] >= 0.9 and metrics["visual_description_coverage_ratio"] >= 0.75 and audio_events and beats and transcript_segments:
        completeness = "full"
    elif shots or transcript_segments or audio_events or beats:
        completeness = "partial"
    else:
        completeness = "insufficient"
    metrics["completion_label_vi"] = {
        "full": "Đầy đủ",
        "partial": "Một phần",
        "insufficient": "Thiếu dữ liệu",
    }[completeness]
    return metrics, limitations, completeness

def _build_analysis_package(row: DBVideoInspirationJob, db: Session) -> dict[str, Any]:
    coverage, limitations, completeness = _coverage_metrics(row, db)
    analysis = row.analysis_json or {}
    package = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "job_id": row.id,
        "source_metadata": {
            "source_type": row.source_type,
            "source_platform": row.source_platform,
            "original_filename": row.original_filename,
            "duration_seconds": row.source_duration_seconds,
            "target_language": row.target_language,
            "analysis_mode": row.analysis_mode,
        },
        "shots": [
            {
                "id": shot.id,
                "order": shot.shot_order,
                "start_seconds": shot.start_seconds,
                "end_seconds": shot.end_seconds,
                "duration_seconds": shot.duration_seconds,
                "keyframe_ids": shot.keyframe_ids_json or [],
                "visual_description_vi": shot.visual_description_vi,
                "subjects": shot.subjects_json,
                "setting": shot.setting_json,
                "camera": shot.camera_json,
                "subject_motion": shot.subject_motion_json,
                "transition_in": shot.transition_in,
                "transition_out": shot.transition_out,
                "on_screen_text": shot.on_screen_text_json or [],
                "confidence": shot.confidence_json or {},
                "limitations": shot.limitations_json or [],
            }
            for shot in _shots_for_job(row.id, db)
        ],
        "transcript_segments": [
            {
                "id": segment.id,
                "order": segment.segment_order,
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "text": segment.text,
                "raw_text": segment.raw_text,
                "language": segment.language,
                "speaker_label": segment.speaker_label,
                "source": segment.source,
                "timestamp_precision": segment.timestamp_precision,
                "confidence": segment.confidence,
                "shot_ids": segment.shot_ids_json or [],
            }
            for segment in _transcript_segments_for_job(row.id, db)
        ],
        "audio_events": [
            {
                "id": event.id,
                "order": event.event_order,
                "event_type": event.event_type,
                "start_seconds": event.start_seconds,
                "end_seconds": event.end_seconds,
                "description_vi": event.description_vi,
                "confidence": event.confidence,
                "technical_metadata": event.technical_metadata_json or {},
                "shot_ids": event.shot_ids_json or [],
                "transcript_segment_ids": event.transcript_segment_ids_json or [],
            }
            for event in _audio_events_for_job(row.id, db)
        ],
        "on_screen_text_events": [
            {
                "id": event.id,
                "shot_id": event.shot_id,
                "start_seconds": event.start_seconds,
                "end_seconds": event.end_seconds,
                "text": event.text,
                "language": event.language,
                "role": event.role,
                "region": event.region_json,
                "confidence": event.confidence,
                "source": event.source,
            }
            for event in _text_events_for_job(row.id, db)
        ],
        "content_retention_beats": [
            {
                "id": beat.id,
                "order": beat.beat_order,
                "start_seconds": beat.start_seconds,
                "end_seconds": beat.end_seconds,
                "role": beat.role,
                "viewer_question_before": beat.viewer_question_before,
                "content_promise": beat.content_promise,
                "new_information": beat.new_information,
                "emotional_or_stakes_change": beat.emotional_or_stakes_change,
                "question_answered": beat.question_answered,
                "new_open_loop": beat.new_open_loop,
                "micro_payoff": beat.micro_payoff,
                "why_continue": beat.why_continue,
                "drop_off_risks": beat.drop_off_risks_json or [],
                "evidence_refs": beat.evidence_refs_json or [],
                "confidence": beat.confidence,
            }
            for beat in _retention_beats_for_job(row.id, db)
        ],
        "hook_analysis": analysis.get("hook_analysis") or analysis.get("hook_vi"),
        "story_structure": analysis.get("story_structure") or analysis.get("structure_vi"),
        "visual_grammar": analysis.get("visual_grammar") or analysis.get("visual_rhythm_vi"),
        "audio_grammar": analysis.get("audio_grammar"),
        "strengths": analysis.get("strengths_vi") or [],
        "weaknesses": analysis.get("weaknesses_vi") or [],
        "rewrite_opportunities": analysis.get("rewrite_opportunities_vi") or [],
        "originality_boundaries": analysis.get("originality_boundaries") or [],
        "limitations": [*limitations, *(_as_list(analysis.get("limitations")))],
        "coverage_metrics": coverage,
        "retention_source": "predicted_from_content",
        "analysis_completeness": completeness,
        "created_at": _now().isoformat(),
    }
    package_path = _job_dir(row.id) / "analysis" / "video-analysis-package-v1.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    row.analysis_schema_version = ANALYSIS_SCHEMA_VERSION
    row.analysis_package_json = package
    row.analysis_package_path = config.to_storage_path(package_path)
    row.coverage_metrics_json = coverage
    row.limitations_json = package["limitations"]
    row.retention_source = "predicted_from_content"
    row.analysis_completeness = completeness
    row.updated_at = _now()
    db.commit()
    return package

def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

async def analyze_job(
    job_id: str,
    data: models.VideoInspirationAnalyzeRequest,
    db: Session,
    *,
    cancel_requested: Callable[[], bool] | None = None,
    stt_runner: Callable[[Callable[[], Awaitable[Any]]], Awaitable[Any]] | None = None,
) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    try:
        _ensure_not_cancelled(cancel_requested)
        row.analysis_schema_version = ANALYSIS_SCHEMA_VERSION
        row.analysis_mode = _analysis_mode(data.analysis_mode)
        row.analysis_package_json = None
        row.analysis_package_path = None
        row.coverage_metrics_json = None
        row.limitations_json = None
        row.retention_source = "predicted_from_content"
        row.analysis_completeness = "not_started"
        db.commit()
        _set_job_state(row, db, status="analyzing", step="extract_audio", progress=0.16)
        audio_path = await asyncio.to_thread(_extract_audio, row)
        db.commit()
        _ensure_not_cancelled(cancel_requested)

        _set_job_state(row, db, step="transcribe", progress=0.30)
        setattr(_transcribe_audio, "last_segments", None)

        async def transcribe() -> tuple[str, str | None]:
            return await _transcribe_audio(audio_path, model_size=data.stt_model)

        if stt_runner is not None:
            transcript, model_size = await stt_runner(transcribe)
        else:
            transcript, model_size = await transcribe()
        _ensure_not_cancelled(cancel_requested)
        transcript_segments_payload = getattr(_transcribe_audio, "last_segments", None)
        if not transcript_segments_payload and transcript.strip():
            transcript_segments_payload = [
                {
                    "segment_order": 1,
                    "start_seconds": 0.0,
                    "end_seconds": float(row.source_duration_seconds or _audio_duration_seconds(audio_path) or 0.0),
                    "text": transcript,
                    "raw_text": transcript,
                    "timestamp_precision": "file",
                    "source": "stt_raw",
                }
            ]
        row.transcript_text = transcript
        row.transcript_language = None
        row.transcript_status = "empty" if not transcript.strip() else "completed"
        row.analysis_json = None
        row.rewritten_script = None
        row.updated_at = _now()
        db.commit()

        _set_job_state(row, db, step="extract_frames", progress=0.48)
        frames = await asyncio.to_thread(_extract_frames, row, db)
        _ensure_not_cancelled(cancel_requested)
        transcript_segments = _save_transcript_segments(row, transcript_segments_payload, db)
        _save_audio_events(row, audio_path, transcript_segments, db)

        _set_job_state(row, db, step="visual_analysis", progress=0.62)
        ready, message, error_code = await asyncio.to_thread(_provider_ready, db)
        if not ready:
            if not data.allow_audio_only:
                raise VideoInspirationError(
                    f"Chưa phân tích được hình ảnh: {message}",
                    error_code=error_code or "VIDEO_INSPIRATION_VISION_PROVIDER_REQUIRED",
            )
            row.visual_summary = "Chưa phân tích hình ảnh vì công cụ AI/vision chưa sẵn sàng. Phần sau chỉ dựa trên transcript và frame đã trích."
        elif frames:
            with _structured_ai_context(row.id, "video_inspiration_visual_analysis"):
                visual_payload = await _run_structured_ai_in_thread(
                    db,
                    _visual_analysis_prompt(frames),
                    VISUAL_SCHEMA,
                )
            _ensure_not_cancelled(cancel_requested)
            _apply_visual_payload(row, frames, visual_payload, db)
        else:
            row.visual_summary = "Không trích được frame đại diện từ video."
            db.commit()

        _set_job_state(row, db, step="content_analysis", progress=0.78)
        ready, message, error_code = await asyncio.to_thread(_provider_ready, db)
        if not ready:
            raise VideoInspirationError(
                f"Chưa phân tích được nội dung: {message}",
                error_code=error_code or "VIDEO_INSPIRATION_AI_PROVIDER_REQUIRED",
            )
        with _structured_ai_context(row.id, "video_inspiration_content_analysis"):
            row.analysis_json = await _run_structured_ai_in_thread(
                db,
                _analysis_prompt(row, db),
                ANALYSIS_SCHEMA,
            )
        _ensure_not_cancelled(cancel_requested)
        _save_retention_beats(row, row.analysis_json or {}, db)
        _build_analysis_package(row, db)
        row.status = "analyzed"
        row.current_step = "completed"
        row.progress = 0.88
        row.failure_reason = None
        row.error_code = None
        row.updated_at = _now()
        db.commit()
    except VideoInspirationCancelledError as exc:
        _set_job_state(
            row,
            db,
            status="cancelled",
            step="cancelled",
            progress=float(row.progress or 0.0),
            failure_reason=str(exc),
            error_code=exc.error_code,
        )
    except Exception as exc:
        _fail_job(row, db, exc)
        if isinstance(exc, VideoInspirationError):
            raise
        raise
    return _job_response(row, db)

def update_transcript(job_id: str, data: models.VideoInspirationTranscriptUpdate, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    row.transcript_text = data.transcript_text.strip()
    row.transcript_status = "empty" if not row.transcript_text else "completed"
    row.analysis_json = None
    row.analysis_package_json = None
    row.coverage_metrics_json = None
    row.limitations_json = None
    row.analysis_completeness = "not_started"
    row.rewritten_script = None
    row.status = "transcript_edited"
    row.current_step = "source_ready"
    row.progress = max(float(row.progress or 0.0), 0.45)
    row.failure_reason = None
    row.error_code = None
    row.updated_at = _now()
    _save_user_transcript_edit(row, row.transcript_text or "", db)
    db.commit()
    return _job_response(row, db)

def update_transcript_segment(
    job_id: str,
    segment_id: str,
    data: models.VideoInspirationTranscriptSegmentUpdate,
    db: Session,
) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    source_segment = (
        db.query(DBVideoInspirationTranscriptSegment)
        .filter(
            DBVideoInspirationTranscriptSegment.job_id == job_id,
            DBVideoInspirationTranscriptSegment.id == segment_id,
        )
        .first()
    )
    if source_segment is None:
        raise VideoInspirationError("Không tìm thấy transcript segment.", error_code="VIDEO_INSPIRATION_SEGMENT_NOT_FOUND", status_code=404)
    edited = DBVideoInspirationTranscriptSegment(
        id=str(uuid.uuid4()),
        job_id=job_id,
        segment_order=source_segment.segment_order,
        start_seconds=source_segment.start_seconds,
        end_seconds=source_segment.end_seconds,
        text=data.text.strip(),
        raw_text=source_segment.raw_text or source_segment.text,
        language=source_segment.language,
        speaker_label=(data.speaker_label or source_segment.speaker_label or "").strip() or None,
        source="user_edited",
        timestamp_precision=source_segment.timestamp_precision,
        confidence=None,
        shot_ids_json=source_segment.shot_ids_json,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(edited)
    row.transcript_text = "\n".join(
        segment.text
        for segment in _transcript_segments_for_job(job_id, db)
        if segment.id != source_segment.id and segment.source != "user_edited"
    ).strip()
    row.transcript_text = "\n".join(part for part in (row.transcript_text, edited.text) if part).strip()
    row.analysis_json = None
    row.analysis_package_json = None
    row.coverage_metrics_json = None
    row.limitations_json = None
    row.analysis_completeness = "not_started"
    row.status = "transcript_edited"
    row.updated_at = _now()
    db.commit()
    return _job_response(row, db)

def update_text_event(
    job_id: str,
    event_id: str,
    data: models.VideoInspirationTextEventUpdate,
    db: Session,
) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    event = (
        db.query(DBVideoInspirationTextEvent)
        .filter(DBVideoInspirationTextEvent.job_id == job_id, DBVideoInspirationTextEvent.id == event_id)
        .first()
    )
    if event is None:
        raise VideoInspirationError("Không tìm thấy chữ trên màn hình.", error_code="VIDEO_INSPIRATION_TEXT_EVENT_NOT_FOUND", status_code=404)
    event.text = data.text.strip()
    if data.language is not None:
        event.language = data.language.strip() or None
    if data.role is not None:
        event.role = data.role.strip() or "unknown"
    event.source = "user_edited"
    event.updated_at = _now()
    row.analysis_package_json = None
    row.coverage_metrics_json = None
    row.limitations_json = None
    row.analysis_completeness = "not_started"
    row.updated_at = _now()
    db.commit()
    return _job_response(row, db)

def update_direction(job_id: str, data: models.VideoInspirationDirectionUpdate, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    next_direction = _clean_user_direction(data.user_direction)
    changed = (row.user_direction or None) != next_direction
    row.user_direction = next_direction
    if changed:
        row.rewritten_script = None
        row.script_title = None
        row.big_idea = None
        row.hook = None
        row.status = "direction_edited"
        row.current_step = "completed" if row.analysis_json else "source_ready"
        row.progress = max(float(row.progress or 0.0), 0.08)
    row.failure_reason = None
    row.error_code = None
    row.updated_at = _now()
    db.commit()
    return _job_response(row, db)

def rewrite_job(
    job_id: str,
    data: models.VideoInspirationRewriteRequest,
    db: Session,
    *,
    cancel_requested: Callable[[], bool] | None = None,
) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    try:
        _ensure_not_cancelled(cancel_requested)
        if data.target_language:
            row.target_language = _validate_target_language(data.target_language)
        if data.user_direction is not None:
            row.user_direction = _clean_user_direction(data.user_direction)
        if not row.analysis_json:
            raise VideoInspirationError("Cần phân tích video trước khi viết kịch bản tối ưu.", error_code="VIDEO_INSPIRATION_ANALYSIS_REQUIRED")
        ready, message, error_code = _provider_ready(db)
        if not ready:
            raise VideoInspirationError(
                f"Chưa viết được kịch bản tối ưu: {message}",
                error_code=error_code or "VIDEO_INSPIRATION_AI_PROVIDER_REQUIRED",
            )
        _set_job_state(row, db, status="rewriting", step="rewrite_brief", progress=0.91)
        with _structured_ai_context(row.id, "video_inspiration_rewrite_brief"):
            creative_brief = _run_structured_ai(db, _creative_brief_prompt(row), CREATIVE_BRIEF_SCHEMA)
        _ensure_not_cancelled(cancel_requested)

        _set_job_state(row, db, status="rewriting", step="rewrite_candidates", progress=0.94)
        with _structured_ai_context(row.id, "video_inspiration_rewrite_candidates"):
            candidates = _run_structured_ai(
                db,
                _rewrite_candidates_prompt(row, creative_brief),
                REWRITE_CANDIDATES_SCHEMA,
            )
        _ensure_not_cancelled(cancel_requested)
        _validate_candidate_payload(candidates)

        _set_job_state(row, db, status="rewriting", step="rewrite_review", progress=0.97)
        with _structured_ai_context(row.id, "video_inspiration_rewrite_review"):
            review = _run_structured_ai(
                db,
                _rewrite_review_prompt(row, creative_brief, candidates),
                REWRITE_REVIEW_SCHEMA,
            )
        _ensure_not_cancelled(cancel_requested)

        _set_job_state(row, db, status="rewriting", step="rewrite_synthesis", progress=0.99)
        with _structured_ai_context(row.id, "video_inspiration_rewrite_synthesis"):
            payload = _run_structured_ai(
                db,
                _rewrite_synthesis_prompt(row, creative_brief, candidates, review),
                REWRITE_SCHEMA,
            )
        _ensure_not_cancelled(cancel_requested)
        _validate_optimized_rewrite_payload(payload)

        row.rewritten_script = _format_optimized_script(payload)
        row.script_title = _truncate(payload.get("title"), 160)
        row.big_idea = _truncate(payload.get("big_idea"), 20000)
        row.hook = _truncate(payload.get("hook_3_5s") or payload.get("hook"), 12000)
        row.analysis_json = {
            **(row.analysis_json or {}),
            "rewrite_creative_brief": creative_brief,
            "rewrite_candidates": candidates,
            "rewrite_review": review,
            "rewrite": payload,
        }
        row.status = "rewritten"
        row.current_step = "completed"
        row.progress = 1.0
        row.failure_reason = None
        row.error_code = None
        row.updated_at = _now()
        db.commit()
    except VideoInspirationCancelledError as exc:
        _set_job_state(
            row,
            db,
            status="cancelled",
            step="cancelled",
            progress=float(row.progress or 0.0),
            failure_reason=str(exc),
            error_code=exc.error_code,
        )
    except Exception as exc:
        _fail_job(row, db, exc)
        if isinstance(exc, VideoInspirationError):
            raise
        raise
    return _job_response(row, db)

def update_script(job_id: str, data: models.VideoInspirationScriptUpdate, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    previous_script = (row.rewritten_script or "").strip()
    row.rewritten_script = data.rewritten_script.strip()
    if data.script_title is not None:
        row.script_title = data.script_title.strip() or row.script_title
    if data.big_idea is not None:
        row.big_idea = data.big_idea.strip() or row.big_idea
    if data.hook is not None:
        row.hook = data.hook.strip() or row.hook
    row.status = "rewritten"
    row.current_step = "completed"
    row.progress = 1.0
    row.failure_reason = None
    row.error_code = None
    row.updated_at = _now()
    if previous_script and previous_script != row.rewritten_script:
        video_project_memory.mark_handoffs_stale_for_job(
            row.id,
            db,
            changed_scope="narration",
            reason_vi="Ká»‹ch báº£n Ä‘Ã­ch Ä‘Ã£ Ä‘á»•i; cáº§n táº¡o láº¡i voice, subtitle vÃ  package liÃªn quan.",
        )
    else:
        db.commit()
    return _job_response(row, db)

def _source_block(block_type: str, content: Any) -> models.VideoSourceBlockDraft | None:
    if not isinstance(content, str):
        content = _format_json_section(content)
    text = _truncate(content, 30000)
    if not text:
        return None
    return models.VideoSourceBlockDraft(block_type=block_type, content=text)

def _project_source_blocks(row: DBVideoInspirationJob) -> list[models.VideoSourceBlockDraft]:
    analysis_text = json.dumps(row.analysis_json or {}, ensure_ascii=False, indent=2)
    rewrite = (row.analysis_json or {}).get("rewrite") if isinstance(row.analysis_json, dict) else None
    rewrite_blocks = (
        rewrite.get("ai_video_source_blocks")
        if isinstance(rewrite, dict) and isinstance(rewrite.get("ai_video_source_blocks"), dict)
        else {}
    )
    blocks = [
        _source_block("idea", rewrite_blocks.get("idea", "")),
        _source_block("rough_script", rewrite_blocks.get("rough_script", "")),
        _source_block("character_notes", rewrite_blocks.get("character_notes", "")),
        _source_block("style_notes", rewrite_blocks.get("style_notes", "")),
        _source_block("must_have", rewrite_blocks.get("must_have", "")),
        _source_block("avoid", rewrite_blocks.get("avoid", "")),
        _source_block("script", row.rewritten_script or ""),
        _source_block("user_direction", row.user_direction or ""),
        _source_block("analysis", analysis_text),
        _source_block("visual_notes", row.visual_summary or ""),
        _source_block("transcript", row.transcript_text or ""),
    ]
    return [block for block in blocks if block is not None]

async def create_ai_video_project(
    job_id: str,
    data: models.VideoInspirationCreateProjectRequest,
    db: Session,
) -> models.VideoInspirationHandoffResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    if not (row.rewritten_script or "").strip():
        raise VideoInspirationError("Cần có kịch bản tối ưu trước khi chuyển sang AI Video.", error_code="VIDEO_INSPIRATION_SCRIPT_REQUIRED")
    if not row.analysis_package_json:
        raise VideoInspirationError("Cần có gói phân tích timeline trước khi chuyển sang AI Video.", error_code="VIDEO_INSPIRATION_ANALYSIS_PACKAGE_REQUIRED")
    try:
        _set_job_state(row, db, status="handoff", step="handoff", progress=1.0)
        handoff = video_project_memory.create_or_update_handoff(row, db, status="approved")
        handoff_source_blocks = video_project_memory.source_blocks_from_payload(handoff.payload_json)
        project = video_projects.create_project(
            models.VideoProjectCreate(
                title=_project_title_from_job(row),
                topic=_truncate(row.big_idea or row.rewritten_script, 4000) or "Phát triển video từ kịch bản cảm hứng",
                series_id=data.series_id or None,
                language="vi",
                target_language=row.target_language,
                phase="phase2",
                visual_style=_truncate(
                    "\n\n".join(part for part in (row.user_direction, row.visual_summary) if part),
                    2000,
                ) or None,
                voice_profile_id=data.voice_profile_id or None,
                source_blocks=handoff_source_blocks or _project_source_blocks(row),
                video_purpose="custom",
                dialogue_mode="voiceover",
                narration_density="balanced",
            ),
            db,
        )
        project_row = db.query(DBVideoProject).filter(DBVideoProject.id == project.id).first()
        if project_row is not None:
            video_project_memory.create_project_memory_from_handoff(project_row, handoff, db)
            video_project_memory.plan_target_timeline(project_row, handoff, db)
            video_project_memory.record_project_dependency(project_row.id, "video_inspiration_handoff", handoff.id, int(handoff.revision or 1), db)
            video_project_memory.mark_handoff_consumed(handoff, project_row.id, db)
        auto_run = None
        if data.start_full_materials:
            auto_run = await video_auto_runs.start_auto_run(
                project.id,
                models.VideoAutoRunStartRequest(
                    mode=data.mode,
                    material_target="full_materials",
                    force=False,
                ),
                db,
            )
        row.created_video_project_id = project.id
        row.latest_auto_run_id = auto_run.id if auto_run else None
        row.status = "ai_video_ready"
        row.current_step = "completed"
        row.progress = 1.0
        row.failure_reason = None
        row.error_code = None
        row.updated_at = _now()
        db.commit()
        db.refresh(row)
        return models.VideoInspirationHandoffResponse(
            job=_job_response(row, db),
            project=project,
            auto_run=auto_run,
            ai_video_url=f"/ai-video?projectId={project.id}",
        )
    except Exception as exc:
        _fail_job(row, db, exc)
        if isinstance(exc, VideoInspirationError):
            raise
        raise
