"""Bounded Codex repair policy for Veo provider technical failures."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..database import (
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoClipGenerationJob as DBVideoClipGenerationJob,
    VideoCodexRepairAttempt as DBVideoCodexRepairAttempt,
)

ALLOWLIST_ERROR_CODES = {
    "VIDEO_PROVIDER_UI_CHANGED",
    "VIDEO_PROVIDER_DOWNLOAD_UNAVAILABLE",
    "VIDEO_DOWNLOAD_AMBIGUOUS",
    "VIDEO_DOWNLOAD_DIRECT_FAILED",
    "VIDEO_DOWNLOAD_STALLED",
    "VIDEO_DOWNLOAD_TIMEOUT",
    "VIDEO_DOWNLOAD_INVALID_FILE",
    "VIDEO_RENDER_CLIP_INVALID",
}

DENYLIST_ERROR_CODES = {
    "VIDEO_PROVIDER_PROJECT_NEEDS_LOGIN",
    "VIDEO_PROVIDER_SESSION_NOT_READY",
    "VIDEO_PROVIDER_CHROME_MISSING",
    "VIDEO_PROVIDER_PROFILE_LOCKED",
    "VIDEO_PROVIDER_FLOW_APP_ERROR",
    "VIDEO_PROVIDER_PROJECT_NOT_READY",
    "VIDEO_PROVIDER_PROJECT_INVALID",
    "VIDEO_PROVIDER_GENERATION_FAILED",
    "VIDEO_PROVIDER_CREDIT_LIMIT_EXCEEDED",
    "VIDEO_PROVIDER_NEEDS_CREDIT_APPROVAL",
    "VIDEO_PROVIDER_MODEL_QUOTA_EXHAUSTED",
    "VIDEO_PROVIDER_MODEL_UNAVAILABLE",
    "VIDEO_PROVIDER_BILLING_REQUIRED",
    "VIDEO_PROVIDER_PAYMENT_REQUIRED",
    "VIDEO_PROVIDER_QUOTA_OR_POLICY",
    "VIDEO_PROVIDER_POLICY_PUBLIC_FIGURE",
    "VIDEO_PROVIDER_POLICY_BLOCKED",
}

FILE_ALLOWLIST = (
    "backend/services/video_veo_chrome.py",
    "backend/services/video_clip_generation.py",
    "backend/tests/test_video_veo_chrome.py",
    "backend/tests/test_video_clip_generation.py",
)

REQUIRED_TESTS = (
    "backend/tests/test_video_veo_chrome.py",
    "backend/tests/test_video_clip_generation.py",
)

MAX_REPAIR_ATTEMPTS_PER_ERROR = 2
REPAIR_AUTORUN_ENV = "VOICEBOX_CODEX_REPAIR_AUTORUN"


def is_denylisted(error_code: str | None) -> bool:
    return str(error_code or "") in DENYLIST_ERROR_CODES


def is_allowlisted(error_code: str | None) -> bool:
    code = str(error_code or "")
    return code in ALLOWLIST_ERROR_CODES and code not in DENYLIST_ERROR_CODES


def _now() -> datetime:
    return datetime.utcnow()


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _redacted_error_text(value: object, *, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    for marker in ("cookie", "token", "authorization", "credential", "password"):
        text = text.replace(marker, "[redacted]")
        text = text.replace(marker.upper(), "[REDACTED]")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "...[truncated]"


def _attempt_count(job: DBVideoClipGenerationJob, item: DBVideoClipGenerationItem | None, error_code: str, db: Session) -> int:
    query = db.query(DBVideoCodexRepairAttempt).filter(
        DBVideoCodexRepairAttempt.job_id == job.id,
        DBVideoCodexRepairAttempt.error_code == error_code,
    )
    if item is not None:
        query = query.filter(DBVideoCodexRepairAttempt.item_id == item.id)
    return int(query.count() or 0)


def create_repair_attempt(
    job: DBVideoClipGenerationJob,
    item: DBVideoClipGenerationItem | None,
    error: BaseException,
    db: Session,
    *,
    step_name: str | None = None,
) -> DBVideoCodexRepairAttempt | None:
    error_code = str(getattr(error, "error_code", "") or "VIDEO_PROVIDER_ERROR")
    if not bool(getattr(job, "enable_codex_repair", False)):
        return None
    if not is_allowlisted(error_code):
        return None
    timestamp = _now()
    attempts = _attempt_count(job, item, error_code, db)
    if attempts >= MAX_REPAIR_ATTEMPTS_PER_ERROR:
        job.repair_status = "limit_reached"
        job.repair_report_json = {
            "message_vi": "Đã hết số lần Codex auto-repair cho lỗi này. Cần xử lý thủ công.",
            "error_code": error_code,
            "max_attempts": MAX_REPAIR_ATTEMPTS_PER_ERROR,
        }
        job.updated_at = timestamp
        db.commit()
        return None

    autorun_enabled = os.environ.get(REPAIR_AUTORUN_ENV) == "1"
    status = "queued" if autorun_enabled else "approval_required"
    failure_reason = None if autorun_enabled else (
        "Codex repair đã được pause an toàn. Bật VOICEBOX_CODEX_REPAIR_AUTORUN=1 nếu muốn backend tự chạy runner sửa code."
    )
    attempt = DBVideoCodexRepairAttempt(
        job_id=job.id,
        item_id=item.id if item else None,
        project_id=job.project_id,
        status=status,
        error_code=error_code,
        step_name=step_name or job.current_step,
        repair_context_json={
            "job_id": job.id,
            "item_id": item.id if item else None,
            "project_id": job.project_id,
            "shot_id": item.shot_id if item else None,
            "shot_order": item.shot_order if item else None,
            "error_code": error_code,
            "message_vi": _redacted_error_text(error),
            "details": _redacted_details(getattr(error, "details", None)),
            "repo_root": _repo_root(),
            "file_allowlist": list(FILE_ALLOWLIST),
            "required_tests": list(REQUIRED_TESTS),
        },
        files_changed_json={"allowed_files": list(FILE_ALLOWLIST), "changed_files": []},
        tests_run_json={"required_tests": list(REQUIRED_TESTS), "commands": []},
        test_result=None,
        failure_reason=failure_reason,
        requires_approval=not autorun_enabled,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(attempt)
    job.repair_status = status
    job.repair_attempt_count = int(job.repair_attempt_count or 0) + 1
    job.repair_report_json = {
        "message_vi": (
            "Codex đang được xếp hàng để sửa lỗi kỹ thuật app."
            if autorun_enabled
            else "Job đã pause để lưu context Codex repair; cần bật runner trước khi tự sửa code."
        ),
        "error_code": error_code,
        "attempt_id": attempt.id,
        "file_allowlist": list(FILE_ALLOWLIST),
        "required_tests": list(REQUIRED_TESTS),
    }
    job.updated_at = timestamp
    db.commit()
    db.refresh(attempt)
    return attempt


def _redacted_details(details: Any) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in details.items():
        lowered = str(key).lower()
        if any(secret in lowered for secret in ("cookie", "token", "authorization", "credential", "password")):
            safe[key] = "[redacted]"
        elif isinstance(value, str):
            safe[key] = _redacted_error_text(value, max_chars=300)
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        else:
            safe[key] = _redacted_error_text(value, max_chars=300)
    return safe
