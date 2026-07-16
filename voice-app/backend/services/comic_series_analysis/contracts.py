"""Stable public contracts for Comic Series Analysis.

This module is the single source of truth for schema versions, job/run
states, progress steps, error codes (stable Vietnamese messages),
development modes, confidence normalization and the approval manifest
classification. Everything else in the feature imports from here so the
contract stays versioned and consistent across backend and frontend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# --------------------------------------------------------------------------
# Schema versions (task 1.4)
# --------------------------------------------------------------------------

SOURCE_PACKAGE_SCHEMA_VERSION = "comic_source_package.v1"
ANALYSIS_PACKAGE_SCHEMA_VERSION = "comic_analysis_package.v1"
HANDOFF_MAPPING_SCHEMA_VERSION = "comic_series_handoff.v1"
APPROVAL_MANIFEST_SCHEMA_VERSION = "comic_approval_manifest.v1"

# Confidence method/threshold config version (task 1.13)
CONFIDENCE_CONFIG_VERSION = "comic_confidence.v1"


# --------------------------------------------------------------------------
# Job lifecycle (task 1.5, design §21)
# --------------------------------------------------------------------------

RunStatus = Literal[
    "draft",
    "queued",
    "running",
    "source_ready",
    "ready_for_review",
    "approved",
    "failed",
    "cancelled",
    "interrupted",
]

RUN_STATUSES: tuple[str, ...] = (
    "draft",
    "queued",
    "running",
    "source_ready",
    "ready_for_review",
    "approved",
    "failed",
    "cancelled",
    "interrupted",
)

# Terminal run states — no further automatic transition.
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset({"approved", "failed", "cancelled"})

# Active run states — a runtime task is expected to exist.
ACTIVE_RUN_STATUSES: frozenset[str] = frozenset({"queued", "running"})


ResultCompleteness = Literal["complete", "partial", "unavailable"]

RESULT_COMPLETENESS: tuple[str, ...] = ("complete", "partial", "unavailable")


CurrentStep = Literal[
    "validate_source",
    "fetch_html",
    "render_browser",
    "extract_content",
    "download_assets",
    "normalize_images",
    "ocr",
    "panel_analysis",
    "character_analysis",
    "story_analysis",
    "build_review",
]

# Ordered pipeline steps used for progress and retry checkpointing.
PIPELINE_STEPS: tuple[str, ...] = (
    "validate_source",
    "fetch_html",
    "render_browser",
    "extract_content",
    "download_assets",
    "normalize_images",
    "ocr",
    "panel_analysis",
    "character_analysis",
    "story_analysis",
    "build_review",
)


# Source revision lifecycle (task 2.15, design §10)
SourceLifecycle = Literal["collecting", "finalized"]
SOURCE_LIFECYCLES: tuple[str, ...] = ("collecting", "finalized")


# Handoff status (design §19)
HandoffStatus = Literal["previewed", "committing", "committed", "failed", "rolled_back"]
HANDOFF_STATUSES: tuple[str, ...] = (
    "previewed",
    "committing",
    "committed",
    "failed",
    "rolled_back",
)

# Per-item handoff classification (design §18)
HandoffItemDecision = Literal["create", "update", "merge", "skip", "duplicate", "conflict"]
HANDOFF_ITEM_DECISIONS: tuple[str, ...] = (
    "create",
    "update",
    "merge",
    "skip",
    "duplicate",
    "conflict",
)


# --------------------------------------------------------------------------
# Development modes and rights (task 1.7, 1.10, design §17)
# --------------------------------------------------------------------------

DevelopmentMode = Literal["lay_cam_hung_va_viet_moi", "bam_canon_va_phat_trien_tiep"]
DEVELOPMENT_MODES: tuple[str, ...] = (
    "lay_cam_hung_va_viet_moi",
    "bam_canon_va_phat_trien_tiep",
)
# External web sources default to "write new" unless the user attests rights
# to develop the canon further.
DEFAULT_DEVELOPMENT_MODE: str = "lay_cam_hung_va_viet_moi"


# --------------------------------------------------------------------------
# Provenance of an asset / chunk occurrence (task 7.4a)
# --------------------------------------------------------------------------

Provenance = Literal["web", "upload", "manual_text"]
PROVENANCES: tuple[str, ...] = ("web", "upload", "manual_text")


# --------------------------------------------------------------------------
# Approval manifest item classification (task 1.12, design §14)
# --------------------------------------------------------------------------

ApprovalItemState = Literal["accepted", "excluded", "unreviewed"]
APPROVAL_ITEM_STATES: tuple[str, ...] = ("accepted", "excluded", "unreviewed")

# Provenance/source of an editable value (task 1.13 / spec).
EditSource = Literal["observed", "inferred", "user_edited"]
EDIT_SOURCES: tuple[str, ...] = ("observed", "inferred", "user_edited")


# --------------------------------------------------------------------------
# Reading modes (spec: phan-tich-truyen-tranh-da-phuong-thuc)
# --------------------------------------------------------------------------

ReadingMode = Literal["auto", "vertical", "page_ltr", "page_rtl"]
READING_MODES: tuple[str, ...] = ("auto", "vertical", "page_ltr", "page_rtl")


# --------------------------------------------------------------------------
# Stale representation on dependent creative artifacts (task 1.11, design §16)
# --------------------------------------------------------------------------
# Candidates: generation_status = "stale" AND evaluation_status = "stale",
#   and selected is cleared.
# Master Story (StoryEpisode.master_story_json): approval_status = "stale",
#   approved_at cleared.
# Adaptations (StoryAdaptation): status = "stale".
STALE_STATUS = "stale"


# --------------------------------------------------------------------------
# Confidence normalization (task 1.13, design §12)
# --------------------------------------------------------------------------

# Threshold mapping label boundaries. Values are the *lower* inclusive bound.
CONFIDENCE_LABEL_THRESHOLDS: dict[str, float] = {
    "cao": 0.75,
    "vua": 0.45,
    "thap": 0.0,
}


def normalize_confidence(value: object) -> float | None:
    """Coerce a confidence value into ``[0, 1]`` or ``None``.

    Anything non-numeric, NaN or out of range collapses to ``None`` so that
    downstream code never has to guess whether ``0`` meant "zero confidence"
    or "missing".
    """
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:  # NaN
        return None
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def confidence_label(value: object) -> str | None:
    """Map a normalized confidence to a stable Vietnamese label.

    Returns ``None`` when confidence is missing so the UI can show
    "không rõ" rather than implying a low-confidence result.
    """
    normalized = normalize_confidence(value)
    if normalized is None:
        return None
    if normalized >= CONFIDENCE_LABEL_THRESHOLDS["cao"]:
        return "cao"
    if normalized >= CONFIDENCE_LABEL_THRESHOLDS["vua"]:
        return "vua"
    return "thap"


# --------------------------------------------------------------------------
# Error codes with stable Vietnamese messages (task 1.5)
# --------------------------------------------------------------------------

ERROR_MESSAGES: dict[str, str] = {
    # Generic / lifecycle
    "COMIC_ANALYSIS_NOT_FOUND": "Không tìm thấy job phân tích truyện tranh.",
    "COMIC_ANALYSIS_DISABLED": "Tính năng phân tích truyện tranh đang tắt.",
    "COMIC_ANALYSIS_INVALID_STATE": "Job đang ở trạng thái không cho phép thao tác này.",
    "COMIC_ANALYSIS_ALREADY_RUNNING": "Job đang chạy hoặc đã có tiến trình xử lý.",
    "COMIC_ANALYSIS_STALE_REVISION": "Nội dung đã thay đổi; hãy tải lại và thử lại.",
    # URL / fetch
    "COMIC_URL_INVALID": "URL không hợp lệ; chỉ chấp nhận http hoặc https công khai.",
    "COMIC_URL_BLOCKED": "URL trỏ tới địa chỉ không công khai và đã bị chặn.",
    "COMIC_URL_HAS_USERINFO": "URL không được chứa thông tin đăng nhập.",
    "COMIC_URL_PORT_BLOCKED": "Cổng của URL không được chính sách cho phép.",
    "COMIC_URL_REDIRECT_BLOCKED": "Chuỗi chuyển hướng dẫn tới đích không an toàn.",
    "COMIC_URL_TOO_MANY_REDIRECTS": "Quá nhiều lần chuyển hướng.",
    "COMIC_FETCH_TIMEOUT": "Hết thời gian chờ khi tải nguồn.",
    "COMIC_FETCH_TOO_LARGE": "Nội dung tải về vượt quá giới hạn cho phép.",
    "COMIC_ACCESS_DENIED": "Máy chủ nguồn từ chối truy cập.",
    "COMIC_AUTHENTICATION_REQUIRED": "Nguồn yêu cầu đăng nhập; hãy dán nội dung hoặc upload ảnh.",
    "COMIC_CAPTCHA_REQUIRED": "Nguồn yêu cầu xác minh CAPTCHA; hãy dán nội dung hoặc upload ảnh.",
    "COMIC_NEEDS_UPLOAD": "Không thể tự động tải nguồn; hãy upload ảnh hoặc dán nội dung.",
    "COMIC_UNSUPPORTED_CONTENT": "Loại nội dung này chưa được hỗ trợ.",
    "COMIC_ROBOTS_DISALLOWED": "Chính sách nguồn không cho phép tải tự động.",
    # Images / codec
    "COMIC_CODEC_UNAVAILABLE": "Định dạng ảnh này chưa có codec khả dụng.",
    "COMIC_UNSUPPORTED_IMAGE_FORMAT": "Định dạng ảnh không được hỗ trợ.",
    "COMIC_IMAGE_CORRUPT": "File ảnh bị hỏng hoặc không phải ảnh hợp lệ.",
    "COMIC_IMAGE_TOO_LARGE": "Ảnh vượt quá giới hạn kích thước cho phép.",
    "COMIC_DECOMPRESSION_BOMB": "Ảnh có dấu hiệu decompression bomb và đã bị từ chối.",
    "COMIC_ASSET_NOT_FOUND": "Không tìm thấy asset ảnh.",
    "COMIC_ASSET_FILE_MISSING": "File asset không còn tồn tại.",
    # Vision / OCR
    "COMIC_VISION_UNAVAILABLE": "Model vision không khả dụng để đọc ảnh.",
    "COMIC_VISION_ATTACH_FAILED": "Không thể đính kèm ảnh cho model vision.",
    "COMIC_ANALYSIS_INVALID_OUTPUT": "Kết quả phân tích AI không đúng định dạng.",
    # Review / approval
    "COMIC_REVISION_NOT_APPROVED": "Revision phân tích chưa được duyệt.",
    "COMIC_APPROVAL_STALE": "Bản duyệt đã cũ; hãy review và duyệt lại.",
    "COMIC_ITEM_UNREVIEWED": "Còn item chưa được review.",
    "COMIC_REVISION_CONFLICT": "Có người khác đã chỉnh sửa; hãy tải lại phiên bản mới nhất.",
    # Handoff
    "COMIC_HANDOFF_PREVIEW_STALE": "Preview đã cũ; hãy tạo preview mới.",
    "COMIC_HANDOFF_TARGET_INVALID": "Series đích không hợp lệ cho luồng này.",
    "COMIC_HANDOFF_TARGET_VIDEO_ONLY": "Series chỉ dành cho video không thể nhận nguồn truyện tranh.",
    "COMIC_HANDOFF_IDEMPOTENCY_CONFLICT": "Idempotency key đã dùng với payload khác.",
    "COMIC_HANDOFF_CONFLICT_UNRESOLVED": "Còn xung đột chưa được giải quyết.",
    "COMIC_HANDOFF_COMMIT_FAILED": "Commit handoff thất bại; không có Series/Episode nào được tạo dở.",
    # Rights / development mode
    "COMIC_RIGHTS_REQUIRED": "Chế độ bám canon cần xác nhận quyền sử dụng nguồn.",
}


DEFAULT_ERROR_MESSAGE = "Đã xảy ra lỗi khi phân tích truyện tranh."


def error_message(error_code: str) -> str:
    """Return the stable Vietnamese message for an error code."""
    return ERROR_MESSAGES.get(error_code, DEFAULT_ERROR_MESSAGE)


class ComicAnalysisError(Exception):
    """Domain error carrying a stable error code and HTTP status.

    Mirrors the ``VideoInspirationError`` shape so routes can translate it
    into an ``HTTPException`` with ``{"message", "error_code"}`` detail.
    """

    def __init__(
        self,
        error_code: str,
        message: str | None = None,
        *,
        status_code: int = 400,
    ) -> None:
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message or error_message(error_code))


@dataclass(frozen=True)
class Outcome:
    """Best-effort outcome of a fetch/ingest step (design §4).

    ``run_status`` describes the job lifecycle, ``result_completeness``
    describes how much was retrieved, and ``outcome_code`` carries the
    specific reason (e.g. ``authentication_required``) without conflating
    the three axes.
    """

    result_completeness: str = "complete"
    outcome_code: str | None = None
    detail_vi: str | None = None
