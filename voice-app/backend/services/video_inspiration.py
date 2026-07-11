"""Video inspiration workflow: source video -> transcript/visual notes -> new script."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config, models
from ..database import (
    VideoInspirationFrame as DBVideoInspirationFrame,
    VideoInspirationJob as DBVideoInspirationJob,
)
from . import (
    ai_planning,
    settings as settings_service,
    video_auto_runs,
    video_projects,
    video_rendering,
    video_storage,
)
from .transcribe import get_whisper_model

logger = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 700 * 1024 * 1024
MAX_VIDEO_DURATION_SECONDS = 30 * 60
MAX_FRAME_COUNT = 12
TRANSCRIPT_CHUNK_SECONDS = 25.0
TRANSCRIPT_SINGLE_PASS_MAX_SECONDS = 28.0
FFMPEG_TIMEOUT_SECONDS = 600
AI_TIMEOUT_SECONDS = 600
_STDERR_LIMIT = 1200
_AUDIO_ONLY_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
_SOCIAL_PLATFORMS = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "facebook.com": "facebook",
    "fb.watch": "facebook",
    "instagram.com": "instagram",
}
_SENSITIVE_QUERY_KEYS = {"token", "access_token", "auth", "key", "signature", "sig", "s", "fbclid"}

STEP_LABELS_VI = {
    "source_ready": "Đã nhận video",
    "downloading": "Đang lấy video từ link",
    "extract_audio": "Đang tách lời nói",
    "transcribe": "Đang chuyển lời nói thành chữ",
    "extract_frames": "Đang lấy hình ảnh đại diện",
    "visual_analysis": "Đang phân tích hình ảnh",
    "content_analysis": "Đang phân tích nội dung",
    "rewrite": "Đang viết kịch bản mới",
    "handoff": "Đang chuyển sang AI Video",
    "completed": "Hoàn tất",
    "failed": "Đã lỗi",
}

class VideoInspirationError(ValueError):
    """Raised when the video inspiration workflow cannot continue."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_INSPIRATION_ERROR", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code

def _now() -> datetime:
    return datetime.utcnow()

def _data_root() -> Path:
    path = config.get_data_dir() / "video_inspiration"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _job_dir(job_id: str) -> Path:
    path = _data_root() / job_id
    for child in ("source", "audio", "frames"):
        (path / child).mkdir(parents=True, exist_ok=True)
    return path

def _truncate(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    return text[:limit].rstrip()

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
    if value in {"vi", "en"}:
        return value
    raise VideoInspirationError("Ngôn ngữ kịch bản mới chỉ hỗ trợ tiếng Việt hoặc tiếng Anh.", error_code="VIDEO_INSPIRATION_LANGUAGE_INVALID")

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

def _job_response(row: DBVideoInspirationJob, db: Session) -> models.VideoInspirationJobResponse:
    response = models.VideoInspirationJobResponse.model_validate(row)
    response.frames = [models.VideoInspirationFrameResponse.model_validate(frame) for frame in _frames_for_job(row.id, db)]
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

def _transcript_audio_paths(path: Path) -> list[Path]:
    duration = _audio_duration_seconds(path)
    if duration is None or duration <= TRANSCRIPT_SINGLE_PASS_MAX_SECONDS:
        return [path]

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

    return chunks or [path]

async def _transcribe_audio(path: Path, *, model_size: str | None) -> tuple[str, str | None]:
    whisper = get_whisper_model()
    resolved_model = model_size or getattr(whisper, "model_size", None) or "turbo"
    load_async = getattr(whisper, "load_model_async", None)
    if callable(load_async):
        await load_async(resolved_model)
    parts = []
    for transcript_path in _transcript_audio_paths(path):
        text = await whisper.transcribe(str(transcript_path), None, resolved_model)
        if text and text.strip():
            parts.append(text.strip())
    return "\n".join(parts), resolved_model

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

def _clear_frames(row: DBVideoInspirationJob, db: Session) -> None:
    for frame in _frames_for_job(row.id, db):
        resolved = config.resolve_storage_path(frame.frame_path)
        if resolved and resolved.exists():
            resolved.unlink(missing_ok=True)
    db.query(DBVideoInspirationFrame).filter(DBVideoInspirationFrame.job_id == row.id).delete(synchronize_session=False)
    db.commit()

def _extract_frames(row: DBVideoInspirationJob, db: Session) -> list[DBVideoInspirationFrame]:
    source_path = _resolve_source(row)
    tools = _require_ffmpeg(ffprobe=False)
    metadata = _probe_video(source_path)
    timestamps = _frame_timestamps(metadata.get("duration_seconds"))
    _clear_frames(row, db)
    frame_dir = _job_dir(row.id) / "frames"
    rows: list[DBVideoInspirationFrame] = []
    for index, timestamp in enumerate(timestamps, start=1):
        frame_path = frame_dir / f"frame-{index:02d}-{int(timestamp * 1000):06d}ms.jpg"
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
            logger.warning("Failed to extract frame at %.2fs: %s", timestamp, _trim_stderr(result.stderr))
            continue
        frame = DBVideoInspirationFrame(
            id=str(uuid.uuid4()),
            job_id=row.id,
            frame_path=config.to_storage_path(frame_path),
            timestamp_seconds=timestamp,
            technical_metadata_json={
                "source_duration_seconds": metadata.get("duration_seconds"),
                "source_width": metadata.get("width"),
                "source_height": metadata.get("height"),
            },
            created_at=_now(),
        )
        db.add(frame)
        rows.append(frame)
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
    raw = ai_planning.run_codex_exec(settings, prompt, output_schema=schema, timeout_seconds=timeout_seconds)
    try:
        return _json_from_ai(raw)
    except json.JSONDecodeError as exc:
        raise VideoInspirationError(
            "AI trả về kết quả không đúng cấu trúc. Hãy thử chạy lại bước này.",
            error_code="VIDEO_INSPIRATION_AI_INVALID_JSON",
        ) from exc

VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary_vi": {"type": "string"},
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
    "required": ["summary_vi", "frames", "limitations_vi"],
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
        "notes_vi",
    ],
}

REWRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "big_idea": {"type": "string"},
        "hook": {"type": "string"},
        "script": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "narration": {"type": "string"},
                    "visual_suggestion": {"type": "string"},
                },
                "required": ["title", "narration", "visual_suggestion"],
            },
        },
        "visual_suggestions": {"type": "array", "items": {"type": "string"}},
        "originality_note": {"type": "string"},
    },
    "required": ["title", "big_idea", "hook", "script", "segments", "visual_suggestions", "originality_note"],
}

def _visual_analysis_prompt(frames: list[DBVideoInspirationFrame]) -> str:
    frame_lines = "\n".join(
        f"- {frame.timestamp_seconds:.2f}s: {config.resolve_storage_path(frame.frame_path)}"
        for frame in frames
    )
    return f"""
Bạn là bộ phân tích hình ảnh video. Chỉ phân tích dựa trên các file ảnh frame dưới đây, không dùng transcript và không đoán khi không nhìn được ảnh.

Frame cần xem:
{frame_lines}

Yêu cầu:
- Trả tiếng Việt.
- Mô tả bối cảnh/chủ thể, nhân vật nếu thấy rõ, mood, màu sắc, ánh sáng, camera/framing và khoảnh khắc đáng chú ý.
- Nếu môi trường không cho bạn xem ảnh, phải nói rõ trong limitations_vi và không bịa nội dung hình ảnh.
- Chỉ trả JSON đúng schema.
""".strip()

def _analysis_prompt(row: DBVideoInspirationJob) -> str:
    return f"""
Bạn là biên tập viên video kiêm strategist nội dung. Hãy phân tích video gốc bằng tiếng Việt trước khi viết lại.

Transcript đã nhận:
{_truncate(row.transcript_text, 50000)}

Tóm tắt hình ảnh:
{_truncate(row.visual_summary, 20000)}

Định hướng phát triển thêm từ người dùng:
{_truncate(row.user_direction, 20000) or "Không có"}

Yêu cầu:
- Phân tích ý chính, hook, cấu trúc, nhân vật/bối cảnh, nhịp dựng, điểm mạnh/yếu và cơ hội viết mới.
- Nếu có định hướng từ người dùng, hãy chỉ ra cơ hội phát triển phù hợp với định hướng đó nhưng không bóp méo nội dung video gốc.
- Nếu thiếu hình ảnh hoặc transcript thì ghi rõ phần thiếu, không nói như đã xem đầy đủ.
- Chỉ trả JSON đúng schema.
""".strip()

def _rewrite_prompt(row: DBVideoInspirationJob) -> str:
    language_label = "tiếng Việt" if row.target_language == "vi" else "English"
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

def _apply_visual_payload(row: DBVideoInspirationJob, frames: list[DBVideoInspirationFrame], payload: dict[str, Any], db: Session) -> None:
    by_timestamp = {
        round(float(item.get("timestamp_seconds", 0)), 2): item.get("description_vi", "")
        for item in payload.get("frames", [])
        if isinstance(item, dict)
    }
    for frame in frames:
        frame.description_vi = _truncate(by_timestamp.get(round(float(frame.timestamp_seconds), 2), ""), 12000)
    summary = payload.get("summary_vi") or ""
    limitations = payload.get("limitations_vi") or ""
    row.visual_summary = "\n\n".join(part for part in (summary.strip(), limitations.strip()) if part)
    db.commit()

async def analyze_job(
    job_id: str,
    data: models.VideoInspirationAnalyzeRequest,
    db: Session,
) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    try:
        _set_job_state(row, db, status="analyzing", step="extract_audio", progress=0.16)
        audio_path = _extract_audio(row)
        db.commit()

        _set_job_state(row, db, step="transcribe", progress=0.30)
        transcript, model_size = await _transcribe_audio(audio_path, model_size=data.stt_model)
        row.transcript_text = transcript
        row.transcript_language = None
        row.transcript_status = "empty" if not transcript.strip() else "completed"
        row.analysis_json = None
        row.rewritten_script = None
        row.updated_at = _now()
        db.commit()

        _set_job_state(row, db, step="extract_frames", progress=0.48)
        frames = _extract_frames(row, db)

        _set_job_state(row, db, step="visual_analysis", progress=0.62)
        ready, message, error_code = _provider_ready(db)
        if not ready:
            if not data.allow_audio_only:
                raise VideoInspirationError(
                    f"Chưa phân tích được hình ảnh: {message}",
                    error_code=error_code or "VIDEO_INSPIRATION_VISION_PROVIDER_REQUIRED",
                )
            row.visual_summary = "Chưa phân tích hình ảnh vì công cụ AI/vision chưa sẵn sàng. Phần sau chỉ dựa trên transcript và frame đã trích."
        elif frames:
            visual_payload = _run_structured_ai(db, _visual_analysis_prompt(frames), VISUAL_SCHEMA)
            _apply_visual_payload(row, frames, visual_payload, db)
        else:
            row.visual_summary = "Không trích được frame đại diện từ video."
            db.commit()

        _set_job_state(row, db, step="content_analysis", progress=0.78)
        ready, message, error_code = _provider_ready(db)
        if not ready:
            raise VideoInspirationError(
                f"Chưa phân tích được nội dung: {message}",
                error_code=error_code or "VIDEO_INSPIRATION_AI_PROVIDER_REQUIRED",
            )
        row.analysis_json = _run_structured_ai(db, _analysis_prompt(row), ANALYSIS_SCHEMA)
        row.status = "analyzed"
        row.current_step = "completed"
        row.progress = 0.88
        row.failure_reason = None
        row.error_code = None
        row.updated_at = _now()
        db.commit()
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
    row.rewritten_script = None
    row.status = "transcript_edited"
    row.current_step = "source_ready"
    row.progress = max(float(row.progress or 0.0), 0.45)
    row.failure_reason = None
    row.error_code = None
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

def rewrite_job(job_id: str, data: models.VideoInspirationRewriteRequest, db: Session) -> models.VideoInspirationJobResponse | None:
    row = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if row is None:
        return None
    try:
        if data.target_language:
            row.target_language = _validate_target_language(data.target_language)
        if data.user_direction is not None:
            row.user_direction = _clean_user_direction(data.user_direction)
        if not row.analysis_json:
            raise VideoInspirationError("Cần phân tích video trước khi viết kịch bản mới.", error_code="VIDEO_INSPIRATION_ANALYSIS_REQUIRED")
        ready, message, error_code = _provider_ready(db)
        if not ready:
            raise VideoInspirationError(
                f"Chưa viết được kịch bản mới: {message}",
                error_code=error_code or "VIDEO_INSPIRATION_AI_PROVIDER_REQUIRED",
            )
        _set_job_state(row, db, status="rewriting", step="rewrite", progress=0.92)
        payload = _run_structured_ai(db, _rewrite_prompt(row), REWRITE_SCHEMA)
        segments = payload.get("segments") or []
        segment_text = "\n\n".join(
            f"{index}. {item.get('title', '').strip()}\nNarration: {item.get('narration', '').strip()}\nGợi ý hình ảnh: {item.get('visual_suggestion', '').strip()}"
            for index, item in enumerate(segments, start=1)
            if isinstance(item, dict)
        )
        script = (payload.get("script") or "").strip()
        if segment_text:
            script = f"{script}\n\nCấu trúc đoạn/cảnh:\n{segment_text}".strip()
        if payload.get("originality_note"):
            script = f"{script}\n\nGhi chú:\n{payload['originality_note']}".strip()
        row.rewritten_script = script
        row.script_title = _truncate(payload.get("title"), 160)
        row.big_idea = _truncate(payload.get("big_idea"), 20000)
        row.hook = _truncate(payload.get("hook"), 12000)
        row.analysis_json = {**(row.analysis_json or {}), "rewrite": payload}
        row.status = "rewritten"
        row.current_step = "completed"
        row.progress = 1.0
        row.failure_reason = None
        row.error_code = None
        row.updated_at = _now()
        db.commit()
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
    db.commit()
    return _job_response(row, db)

def _source_block(block_type: str, content: str) -> models.VideoSourceBlockDraft | None:
    text = _truncate(content, 30000)
    if not text:
        return None
    return models.VideoSourceBlockDraft(block_type=block_type, content=text)

def _project_source_blocks(row: DBVideoInspirationJob) -> list[models.VideoSourceBlockDraft]:
    analysis_text = json.dumps(row.analysis_json or {}, ensure_ascii=False, indent=2)
    blocks = [
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
        raise VideoInspirationError("Cần có kịch bản mới trước khi chuyển sang AI Video.", error_code="VIDEO_INSPIRATION_SCRIPT_REQUIRED")
    try:
        _set_job_state(row, db, status="handoff", step="handoff", progress=1.0)
        project = video_projects.create_project(
            models.VideoProjectCreate(
                title=row.script_title or "Video từ cảm hứng",
                topic=_truncate(row.big_idea or row.rewritten_script, 4000) or "Phát triển video từ kịch bản cảm hứng",
                language="vi",
                target_language=row.target_language,
                phase="phase2",
                visual_style=_truncate(
                    "\n\n".join(part for part in (row.user_direction, row.visual_summary) if part),
                    2000,
                ) or None,
                voice_profile_id=data.voice_profile_id or None,
                source_blocks=_project_source_blocks(row),
                video_purpose="custom",
                dialogue_mode="voiceover",
                narration_density="balanced",
            ),
            db,
        )
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
