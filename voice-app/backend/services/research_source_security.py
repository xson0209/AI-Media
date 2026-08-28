"""Security and media validation for Research Workspace source ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import video_inspiration
from .comic_series_analysis import url_security
from .comic_series_analysis.contracts import ComicAnalysisError
from .comic_series_analysis.image_pipeline import validate_image


MAX_RESEARCH_IMAGE_BYTES = 40 * 1024 * 1024
MAX_RESEARCH_VIDEO_BYTES = video_inspiration.MAX_VIDEO_BYTES


class ResearchSourceValidationError(ValueError):
    def __init__(self, message: str, *, error_code: str, status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def validate_source_url(raw_url: str, *, resolve_dns: bool = False) -> dict[str, Any]:
    """Validate a public HTTP(S) URL and return redacted provenance."""

    try:
        validated = (
            url_security.validate_and_resolve(raw_url)
            if resolve_dns
            else url_security.validate_url(raw_url)
        )
    except ComicAnalysisError as exc:
        raise ResearchSourceValidationError(
            str(exc),
            error_code=f"RESEARCH_{exc.error_code}",
            status_code=exc.status_code,
        ) from exc
    return {
        "redacted_url": url_security.redact_url(raw_url),
        "scheme": validated.scheme,
        "host": validated.host,
        "port": validated.port,
        "ssrf_checked": True,
        "dns_checked": resolve_dns,
        "redirect_policy": "manual_per_hop_validation_required",
        "credentials_allowed": False,
    }


def validate_image_upload(
    data: bytes,
    *,
    filename: str,
    content_type: str | None,
) -> dict[str, Any]:
    if not data:
        raise ResearchSourceValidationError(
            "File ảnh đang rỗng.",
            error_code="RESEARCH_IMAGE_EMPTY",
        )
    if len(data) > MAX_RESEARCH_IMAGE_BYTES:
        raise ResearchSourceValidationError(
            "Ảnh quá nặng. Hãy chọn file dưới 40MB.",
            error_code="RESEARCH_IMAGE_TOO_LARGE",
        )
    if content_type and content_type != "application/octet-stream" and not content_type.startswith("image/"):
        raise ResearchSourceValidationError(
            "MIME khai báo không phải ảnh.",
            error_code="RESEARCH_IMAGE_MIME_INVALID",
        )
    validation = validate_image(data)
    if validation.detected_format == "svg":
        raise ResearchSourceValidationError(
            "Bản Research chỉ nhận ảnh raster; hãy upload PNG/JPEG/WebP đã rasterize.",
            error_code="RESEARCH_IMAGE_SVG_NOT_ALLOWED",
        )
    if validation.error_code:
        messages = {
            "COMIC_UNSUPPORTED_IMAGE_FORMAT": "Định dạng ảnh không được hỗ trợ hoặc magic bytes không hợp lệ.",
            "COMIC_CODEC_UNAVAILABLE": "Runtime chưa có codec để đọc định dạng ảnh này.",
            "COMIC_DECOMPRESSION_BOMB": "Ảnh vượt giới hạn pixel an toàn.",
            "COMIC_IMAGE_CORRUPT": "Ảnh bị lỗi hoặc không decode được.",
        }
        raise ResearchSourceValidationError(
            messages.get(validation.error_code, "Ảnh không hợp lệ."),
            error_code=f"RESEARCH_{validation.error_code}",
        )
    return {
        "kind": "image",
        "filename": Path(filename).name,
        "declared_mime": content_type,
        "detected_mime": f"image/{validation.detected_format}",
        "detected_format": validation.detected_format,
        "byte_size": validation.byte_size,
        "width": validation.width,
        "height": validation.height,
        "pixel_count": (validation.width or 0) * (validation.height or 0),
        "frame_count": validation.frame_count,
        "checksum": validation.checksum,
        "decoded_pixel_hash": validation.decoded_pixel_hash,
        "magic_bytes_checked": True,
        "decode_checked": True,
    }


def validate_video_upload(
    path: Path,
    *,
    data_head: bytes,
    size_bytes: int,
    filename: str,
    content_type: str | None,
) -> dict[str, Any]:
    if size_bytes <= 0:
        raise ResearchSourceValidationError(
            "File video đang rỗng.",
            error_code="RESEARCH_VIDEO_EMPTY",
        )
    if size_bytes > MAX_RESEARCH_VIDEO_BYTES:
        raise ResearchSourceValidationError(
            "Video quá nặng. Hãy chọn file dưới 700MB.",
            error_code="RESEARCH_VIDEO_TOO_LARGE",
        )
    if Path(filename).suffix.lower() != ".mp4":
        raise ResearchSourceValidationError(
            "Bản đầu chỉ nhận video MP4 để dùng chung pipeline Video Inspiration.",
            error_code="RESEARCH_VIDEO_MP4_REQUIRED",
        )
    if content_type and content_type not in {"application/octet-stream", "video/mp4"} and not content_type.startswith("video/"):
        raise ResearchSourceValidationError(
            "MIME khai báo không phải video.",
            error_code="RESEARCH_VIDEO_MIME_INVALID",
        )
    if len(data_head) < 12 or data_head[4:8] != b"ftyp":
        raise ResearchSourceValidationError(
            "Magic bytes không khớp container MP4.",
            error_code="RESEARCH_VIDEO_MAGIC_INVALID",
        )
    try:
        metadata = video_inspiration._validate_video_file(path, size_bytes=size_bytes)
    except video_inspiration.VideoInspirationError as exc:
        raise ResearchSourceValidationError(
            str(exc),
            error_code=f"RESEARCH_{exc.error_code}",
            status_code=exc.status_code,
        ) from exc
    return {
        "kind": "video",
        "filename": Path(filename).name,
        "declared_mime": content_type,
        "detected_mime": "video/mp4",
        "byte_size": size_bytes,
        "duration_seconds": metadata.get("duration_seconds"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "codec": metadata.get("codec"),
        "has_audio": metadata.get("has_audio"),
        "magic_bytes_checked": True,
        "probe_checked": True,
    }


__all__ = [
    "MAX_RESEARCH_IMAGE_BYTES",
    "MAX_RESEARCH_VIDEO_BYTES",
    "ResearchSourceValidationError",
    "validate_image_upload",
    "validate_source_url",
    "validate_video_upload",
]
