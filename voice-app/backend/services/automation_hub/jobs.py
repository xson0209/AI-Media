"""Persistent, isolated publishing queue and scheduler."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ... import config as app_config
from ...database import (
    AutomationAsset,
    AutomationConnection,
    AutomationPublishAttempt,
    AutomationPublishJob,
    get_db,
)
from ..task_queue import create_background_task
from . import assets, security
from .config import get_config
from .publishers import PublishRequest, PublisherError, get_publisher
from .publishers.base import PublishCancelled
from .schemas import (
    AutomationPublishAttemptResponse,
    AutomationPublishJobCreate,
    AutomationPublishJobResponse,
)


ACTIVE_STATUSES = {"preparing", "uploading", "finalizing"}
TERMINAL_STATUSES = {"completed", "failed", "interrupted", "cancelled"}
RETRYABLE_STATUSES = {"failed", "interrupted", "cancelled"}

_queue: asyncio.Queue[str] | None = None
_worker_tasks: list[asyncio.Task] = []
_poller_task: asyncio.Task | None = None
_queued_ids: set[str] = set()
_running_ids: set[str] = set()
_cancel_requested: set[str] = set()
_state_lock = threading.RLock()


class JobError(RuntimeError):
    def __init__(self, message: str, error_code: str = "AUTOMATION_JOB_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _attempt_response(row: AutomationPublishAttempt) -> AutomationPublishAttemptResponse:
    return AutomationPublishAttemptResponse(
        id=row.id,
        attempt_number=row.attempt_number,
        status=row.status,
        request_meta=dict(row.request_meta_json or {}),
        response_meta=dict(row.response_meta_json or {}),
        error_code=row.error_code,
        failure_reason=row.failure_reason,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def to_response(row: AutomationPublishJob, db: Session, *, include_attempts: bool = True) -> AutomationPublishJobResponse:
    attempts = []
    if include_attempts:
        attempts = [
            _attempt_response(attempt)
            for attempt in (
                db.query(AutomationPublishAttempt)
                .filter(AutomationPublishAttempt.job_id == row.id)
                .order_by(AutomationPublishAttempt.attempt_number.asc())
                .all()
            )
        ]
    return AutomationPublishJobResponse(
        id=row.id,
        asset_id=row.asset_id,
        connection_id=row.connection_id,
        platform=row.platform,
        publish_mode=row.publish_mode,
        status=row.status,
        title=row.title or "",
        description=row.description or "",
        tags=list(row.tags_json or []),
        privacy=row.privacy,
        scheduled_at=row.scheduled_at,
        idempotency_key=row.idempotency_key,
        attempt_count=row.attempt_count,
        cancel_requested=bool(row.cancel_requested),
        provider_post_id=row.provider_post_id,
        provider_url=row.provider_url,
        result=dict(row.result_json or {}),
        error_code=row.error_code,
        failure_reason=row.failure_reason,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        attempts=attempts,
    )


def list_jobs(db: Session, *, limit: int = 100) -> list[AutomationPublishJobResponse]:
    rows = (
        db.query(AutomationPublishJob)
        .order_by(AutomationPublishJob.created_at.desc())
        .limit(max(1, min(500, limit)))
        .all()
    )
    return [to_response(row, db, include_attempts=False) for row in rows]


def get_job(job_id: str, db: Session) -> AutomationPublishJob | None:
    return db.query(AutomationPublishJob).filter(AutomationPublishJob.id == job_id).first()


def create_job(data: AutomationPublishJobCreate, db: Session) -> AutomationPublishJobResponse:
    existing = (
        db.query(AutomationPublishJob)
        .filter(AutomationPublishJob.idempotency_key == data.idempotency_key)
        .first()
    )
    if existing is not None:
        return to_response(existing, db)
    asset = db.query(AutomationAsset).filter(AutomationAsset.id == data.asset_id).first()
    if asset is None:
        raise JobError("Không tìm thấy Automation Hub asset.", "AUTOMATION_ASSET_NOT_FOUND")
    connection = (
        db.query(AutomationConnection)
        .filter(AutomationConnection.id == data.connection_id)
        .first()
    )
    if connection is None:
        raise JobError("Không tìm thấy publishing connection.", "AUTOMATION_CONNECTION_NOT_FOUND")
    if connection.platform != data.platform or connection.kind != "publisher":
        raise JobError("Connection không khớp nền tảng publishing.", "AUTOMATION_CONNECTION_PLATFORM_MISMATCH")
    if connection.status != "ready":
        raise JobError("Hãy kiểm tra connection thành công trước khi tạo job.", "AUTOMATION_CONNECTION_NOT_READY")
    scheduled_at = _utc_naive(data.scheduled_at)
    if data.platform == "tiktok" and data.publish_mode == "direct" and not get_config().direct_post_enabled:
        raise JobError(
            "TikTok Direct Post đang tắt hoặc chưa được audit. Hãy dùng Draft.",
            "TIKTOK_DIRECT_POST_DISABLED",
        )
    status = "scheduled" if data.platform == "tiktok" and scheduled_at and scheduled_at > datetime.utcnow() else "queued"
    row = AutomationPublishJob(
        asset_id=data.asset_id,
        connection_id=data.connection_id,
        platform=data.platform,
        publish_mode=data.publish_mode,
        status=status,
        title=data.title.strip(),
        description=data.description,
        tags_json=list(dict.fromkeys(tag.strip() for tag in data.tags if tag.strip())),
        privacy=data.privacy,
        scheduled_at=scheduled_at,
        idempotency_key=data.idempotency_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if status == "queued":
        enqueue_job(row.id)
    return to_response(row, db)


def cancel_job(job_id: str, db: Session) -> AutomationPublishJobResponse | None:
    row = get_job(job_id, db)
    if row is None:
        return None
    if row.status in TERMINAL_STATUSES:
        return to_response(row, db)
    row.cancel_requested = True
    if row.status in {"queued", "scheduled"}:
        row.status = "cancelled"
        row.completed_at = datetime.utcnow()
        with _state_lock:
            _queued_ids.discard(row.id)
    else:
        with _state_lock:
            _cancel_requested.add(row.id)
    db.commit()
    db.refresh(row)
    return to_response(row, db)


def retry_job(job_id: str, db: Session) -> AutomationPublishJobResponse | None:
    row = get_job(job_id, db)
    if row is None:
        return None
    if row.provider_post_id:
        raise JobError(
            "Job đã có provider post id nên không được upload lại để tránh đăng trùng.",
            "AUTOMATION_DUPLICATE_GUARD",
        )
    if row.status not in RETRYABLE_STATUSES:
        raise JobError("Chỉ job lỗi, interrupted hoặc cancelled mới được retry.", "AUTOMATION_JOB_NOT_RETRYABLE")
    scheduled_at = _utc_naive(row.scheduled_at)
    status = (
        "scheduled"
        if row.platform == "tiktok" and scheduled_at is not None and scheduled_at > datetime.utcnow()
        else "queued"
    )
    row.status = status
    row.cancel_requested = False
    row.error_code = None
    row.failure_reason = None
    row.completed_at = None
    with _state_lock:
        _cancel_requested.discard(row.id)
    db.commit()
    db.refresh(row)
    if status == "queued":
        enqueue_job(row.id)
    return to_response(row, db)


def delete_job(job_id: str, db: Session) -> bool:
    row = get_job(job_id, db)
    if row is None:
        return False
    if row.status not in TERMINAL_STATUSES:
        raise JobError("Không thể xóa publishing job đang hoạt động.", "AUTOMATION_JOB_ACTIVE")
    db.query(AutomationPublishAttempt).filter(AutomationPublishAttempt.job_id == job_id).delete()
    db.delete(row)
    db.commit()
    return True


def enqueue_job(job_id: str) -> None:
    queue = _queue
    if queue is None:
        return
    with _state_lock:
        if job_id in _queued_ids or job_id in _running_ids:
            return
        _queued_ids.add(job_id)
    queue.put_nowait(job_id)


def worker_snapshot() -> dict[str, Any]:
    with _state_lock:
        return {
            "available": _queue is not None,
            "max_concurrency": get_config().publishing_concurrency,
            "queued": len(_queued_ids),
            "running": len(_running_ids),
            "queued_ids": sorted(_queued_ids),
            "running_ids": sorted(_running_ids),
        }


def init_worker(force: bool = False) -> None:
    global _queue, _worker_tasks, _poller_task
    active = [task for task in _worker_tasks if not task.done()]
    if active and not force:
        return
    if force:
        for task in active:
            task.cancel()
        if _poller_task is not None and not _poller_task.done():
            _poller_task.cancel()
    _queue = asyncio.Queue()
    with _state_lock:
        _queued_ids.clear()
        _running_ids.clear()
        _cancel_requested.clear()
    _worker_tasks = [create_background_task(_worker_loop()) for _ in range(get_config().publishing_concurrency)]
    _poller_task = create_background_task(_scheduled_poller())
    _enqueue_persisted_ready_jobs()


def _new_db() -> Session:
    generator = get_db()
    return next(generator)


def _enqueue_persisted_ready_jobs() -> None:
    db = _new_db()
    try:
        rows = (
            db.query(AutomationPublishJob)
            .filter(AutomationPublishJob.status == "queued")
            .order_by(AutomationPublishJob.created_at.asc())
            .all()
        )
        for row in rows:
            enqueue_job(row.id)
    finally:
        db.close()


async def _scheduled_poller() -> None:
    while True:
        try:
            await asyncio.sleep(1.0)
            db = _new_db()
            try:
                rows = (
                    db.query(AutomationPublishJob)
                    .filter(
                        AutomationPublishJob.status == "scheduled",
                        AutomationPublishJob.scheduled_at <= datetime.utcnow(),
                    )
                    .order_by(AutomationPublishJob.created_at.asc())
                    .all()
                )
                ids = []
                for row in rows:
                    row.status = "queued"
                    ids.append(row.id)
                if ids:
                    db.commit()
                for job_id in ids:
                    enqueue_job(job_id)
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(2.0)


async def _worker_loop() -> None:
    while True:
        queue = _queue
        if queue is None:
            await asyncio.sleep(0.1)
            continue
        job_id = await queue.get()
        with _state_lock:
            _queued_ids.discard(job_id)
            _running_ids.add(job_id)
        try:
            await _process_job(job_id)
        except asyncio.CancelledError:
            raise
        finally:
            with _state_lock:
                _running_ids.discard(job_id)
                _cancel_requested.discard(job_id)
            queue.task_done()


def _is_cancelled(job_id: str) -> bool:
    with _state_lock:
        return job_id in _cancel_requested


async def _process_job(job_id: str) -> None:
    cfg = get_config()
    for loop_attempt in range(1, cfg.retry_attempts + 1):
        db = _new_db()
        try:
            row = get_job(job_id, db)
            if row is None or row.status in TERMINAL_STATUSES or row.cancel_requested:
                return
            asset = db.query(AutomationAsset).filter(AutomationAsset.id == row.asset_id).first()
            connection = (
                db.query(AutomationConnection)
                .filter(AutomationConnection.id == row.connection_id)
                .first()
            )
            if asset is None or connection is None:
                row.status = "failed"
                row.error_code = "AUTOMATION_DEPENDENCY_MISSING"
                row.failure_reason = "Asset hoặc connection của job không còn tồn tại."
                row.completed_at = datetime.utcnow()
                db.commit()
                return
            try:
                secret = security.decrypt_secret(connection.secret_ciphertext)
                asset_path = assets.resolve_asset_path(asset)
            except (security.SecretStoreError, assets.AssetError) as exc:
                row.status = "failed"
                row.error_code = getattr(exc, "error_code", "AUTOMATION_PREPARE_FAILED")
                row.failure_reason = str(exc)
                row.completed_at = datetime.utcnow()
                db.commit()
                return
            row.status = "preparing"
            row.started_at = row.started_at or datetime.utcnow()
            row.attempt_count = int(row.attempt_count or 0) + 1
            attempt_number = row.attempt_count
            attempt = AutomationPublishAttempt(
                job_id=row.id,
                attempt_number=attempt_number,
                status="running",
                request_meta_json={
                    "platform": row.platform,
                    "publish_mode": row.publish_mode,
                    "asset_sha256": asset.sha256,
                    "size_bytes": asset.size_bytes,
                    "scheduled": row.scheduled_at is not None,
                },
                started_at=datetime.utcnow(),
            )
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            job_data = {
                "platform": row.platform,
                "publish_mode": row.publish_mode,
                "title": row.title or "",
                "description": row.description or "",
                "tags": list(row.tags_json or []),
                "privacy": row.privacy,
                "scheduled_at": row.scheduled_at,
                "public_config": dict(connection.public_config_json or {}),
                "mime_type": asset.mime_type,
                "connection_id": connection.id,
                "attempt_id": attempt.id,
                "asset_path": asset_path,
                "secret": secret,
            }
            row.status = "uploading"
            db.commit()
        finally:
            db.close()

        request = PublishRequest(
            job_id=job_id,
            asset_path=job_data["asset_path"],
            mime_type=job_data["mime_type"],
            title=job_data["title"],
            description=job_data["description"],
            tags=job_data["tags"],
            privacy=job_data["privacy"],
            scheduled_at=job_data["scheduled_at"],
            publish_mode=job_data["publish_mode"],
            public_config=job_data["public_config"],
            secret=job_data["secret"],
            is_cancelled=lambda: _is_cancelled(job_id),
        )
        try:
            result = await get_publisher(job_data["platform"]).publish(request)
            db = _new_db()
            try:
                row = get_job(job_id, db)
                attempt = (
                    db.query(AutomationPublishAttempt)
                    .filter(AutomationPublishAttempt.id == job_data["attempt_id"])
                    .first()
                )
                connection = (
                    db.query(AutomationConnection)
                    .filter(AutomationConnection.id == job_data["connection_id"])
                    .first()
                )
                if row is None:
                    return
                row.status = "finalizing"
                row.provider_post_id = result.provider_post_id
                row.provider_url = result.provider_url
                row.result_json = dict(result.result or {})
                if result.updated_secret is not None and connection is not None:
                    connection.secret_ciphertext, connection.secret_fingerprint = security.encrypt_secret(
                        result.updated_secret
                    )
                if attempt is not None:
                    attempt.status = "completed"
                    attempt.response_meta_json = {
                        "provider_post_id": result.provider_post_id,
                        "has_provider_url": bool(result.provider_url),
                    }
                    attempt.completed_at = datetime.utcnow()
                row.status = "completed"
                row.error_code = None
                row.failure_reason = None
                row.completed_at = datetime.utcnow()
                db.commit()
            finally:
                db.close()
            return
        except PublishCancelled as exc:
            _finish_failure(job_id, job_data["attempt_id"], exc, status="cancelled")
            return
        except PublisherError as exc:
            _finish_attempt_failure(job_id, job_data["attempt_id"], exc)
            if exc.retryable and not exc.ambiguous and loop_attempt < cfg.retry_attempts and not _is_cancelled(job_id):
                await asyncio.sleep(float(loop_attempt))
                continue
            _finish_job_failure(job_id, exc, status="interrupted" if exc.ambiguous else "failed")
            return
        except Exception:
            exc = PublisherError(
                "Publishing adapter gặp lỗi không xác định.",
                error_code="AUTOMATION_PUBLISH_UNEXPECTED",
            )
            _finish_failure(job_id, job_data["attempt_id"], exc, status="failed")
            return


def _finish_attempt_failure(job_id: str, attempt_id: str, exc: PublisherError) -> None:
    db = _new_db()
    try:
        attempt = db.query(AutomationPublishAttempt).filter(AutomationPublishAttempt.id == attempt_id).first()
        if attempt is not None:
            attempt.status = "failed"
            attempt.error_code = exc.error_code
            attempt.failure_reason = str(exc)
            attempt.response_meta_json = dict(exc.response_meta or {})
            attempt.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def _finish_job_failure(job_id: str, exc: PublisherError, *, status: str) -> None:
    db = _new_db()
    try:
        row = get_job(job_id, db)
        if row is not None:
            row.status = status
            row.error_code = exc.error_code
            row.failure_reason = str(exc)
            row.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def _finish_failure(job_id: str, attempt_id: str, exc: PublisherError, *, status: str) -> None:
    _finish_attempt_failure(job_id, attempt_id, exc)
    _finish_job_failure(job_id, exc, status=status)


def sync_stale_running_jobs(db: Session) -> int:
    rows = db.query(AutomationPublishJob).filter(AutomationPublishJob.status.in_(ACTIVE_STATUSES)).all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "interrupted"
        row.error_code = "AUTOMATION_JOB_INTERRUPTED"
        row.failure_reason = (
            "Backend đã dừng trong lúc upload. Không tự retry vì provider có thể đã nhận video; hãy kiểm tra trước."
        )
        row.completed_at = now
    if rows:
        db.commit()
    return len(rows)
