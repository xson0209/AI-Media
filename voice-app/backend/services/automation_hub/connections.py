"""Connection persistence and provider health checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ...database import AutomationConnection, AutomationPublishJob
from . import security
from .config import get_config
from .roxy import RoxyApiError
from .schemas import AutomationConnectionCreate, AutomationConnectionResponse, AutomationConnectionUpdate


ACTIVE_JOB_STATUSES = {"queued", "scheduled", "preparing", "uploading", "finalizing"}
SUPPORTED_PLATFORMS = {"roxy", "youtube", "facebook", "tiktok"}


class ConnectionError(RuntimeError):
    def __init__(self, message: str, error_code: str = "AUTOMATION_CONNECTION_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _validate(kind: str, platform: str, public_config: dict[str, Any], secret: dict[str, Any]) -> None:
    if platform not in SUPPORTED_PLATFORMS:
        raise ConnectionError("Nền tảng chưa được hỗ trợ.", "AUTOMATION_PLATFORM_UNSUPPORTED")
    if platform == "roxy":
        if kind != "roxy":
            raise ConnectionError("RoxyBrowser phải dùng connection kind = roxy.", "AUTOMATION_CONNECTION_KIND_INVALID")
        if not str(secret.get("api_key") or "").strip():
            raise ConnectionError("Thiếu RoxyBrowser API key.", "ROXY_API_KEY_REQUIRED")
        return
    if kind != "publisher":
        raise ConnectionError("Connection xuất bản phải dùng kind = publisher.", "AUTOMATION_CONNECTION_KIND_INVALID")
    if platform == "youtube":
        if not secret.get("access_token") and not (
            secret.get("refresh_token") and secret.get("client_id") and secret.get("client_secret")
        ):
            raise ConnectionError(
                "YouTube cần access token hoặc bộ refresh token/client id/client secret.",
                "YOUTUBE_CREDENTIAL_REQUIRED",
            )
    elif platform == "facebook":
        if not str(public_config.get("page_id") or "").strip():
            raise ConnectionError("Facebook chỉ hỗ trợ Page và cần page_id.", "FACEBOOK_PAGE_ID_REQUIRED")
        if not str(secret.get("page_access_token") or "").strip():
            raise ConnectionError("Thiếu Facebook Page access token.", "FACEBOOK_PAGE_TOKEN_REQUIRED")
    elif platform == "tiktok" and not str(secret.get("access_token") or "").strip():
        raise ConnectionError("Thiếu TikTok access token.", "TIKTOK_ACCESS_TOKEN_REQUIRED")


def to_response(row: AutomationConnection) -> AutomationConnectionResponse:
    return AutomationConnectionResponse(
        id=row.id,
        kind=row.kind,
        platform=row.platform,
        label=row.label,
        status=row.status,
        public_config=dict(row.public_config_json or {}),
        has_secret=bool(row.secret_ciphertext),
        secret_fingerprint=row.secret_fingerprint,
        scopes=list(row.scopes_json or []),
        last_checked_at=row.last_checked_at,
        failure_reason=row.failure_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_connections(db: Session) -> list[AutomationConnectionResponse]:
    rows = db.query(AutomationConnection).order_by(AutomationConnection.created_at.desc()).all()
    return [to_response(row) for row in rows]


def get_connection(connection_id: str, db: Session) -> AutomationConnection | None:
    return db.query(AutomationConnection).filter(AutomationConnection.id == connection_id).first()


def create_connection(data: AutomationConnectionCreate, db: Session) -> AutomationConnectionResponse:
    public_config = dict(data.public_config or {})
    secret = dict(data.secret or {})
    _validate(data.kind, data.platform, public_config, secret)
    ciphertext, fingerprint = security.encrypt_secret(secret)
    row = AutomationConnection(
        kind=data.kind,
        platform=data.platform,
        label=data.label.strip(),
        status="not_checked",
        public_config_json=public_config,
        secret_ciphertext=ciphertext,
        secret_fingerprint=fingerprint,
        scopes_json=list(dict.fromkeys(item.strip() for item in data.scopes if item.strip())),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return to_response(row)


def update_connection(
    connection_id: str,
    data: AutomationConnectionUpdate,
    db: Session,
) -> AutomationConnectionResponse | None:
    row = get_connection(connection_id, db)
    if row is None:
        return None
    public_config = dict(data.public_config) if data.public_config is not None else dict(row.public_config_json or {})
    if data.secret is not None:
        secret = dict(data.secret)
        _validate(row.kind, row.platform, public_config, secret)
        row.secret_ciphertext, row.secret_fingerprint = security.encrypt_secret(secret)
    else:
        try:
            secret = security.decrypt_secret(row.secret_ciphertext)
        except security.SecretStoreError as exc:
            row.status = "needs_auth"
            row.failure_reason = str(exc)
            db.commit()
            raise
        _validate(row.kind, row.platform, public_config, secret)
    if data.label is not None:
        row.label = data.label.strip()
    row.public_config_json = public_config
    if data.scopes is not None:
        row.scopes_json = list(dict.fromkeys(item.strip() for item in data.scopes if item.strip()))
    row.status = "not_checked"
    row.failure_reason = None
    db.commit()
    db.refresh(row)
    return to_response(row)


def delete_connection(connection_id: str, db: Session) -> bool:
    row = get_connection(connection_id, db)
    if row is None:
        return False
    active = (
        db.query(AutomationPublishJob)
        .filter(
            AutomationPublishJob.connection_id == connection_id,
            AutomationPublishJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .first()
    )
    if active is not None:
        raise ConnectionError(
            "Không thể xóa connection đang được publishing job sử dụng.",
            "AUTOMATION_CONNECTION_IN_USE",
        )
    db.delete(row)
    db.commit()
    return True


async def check_connection(connection_id: str, db: Session) -> AutomationConnectionResponse | None:
    row = get_connection(connection_id, db)
    if row is None:
        return None
    try:
        secret = security.decrypt_secret(row.secret_ciphertext)
        public = dict(row.public_config_json or {})
        timeout = httpx.Timeout(30.0)
        if row.platform == "roxy":
            from .roxy import RoxyLocalApiClient

            client = RoxyLocalApiClient(
                api_key=str(secret.get("api_key") or ""),
                api_host=str(public.get("api_host") or get_config().roxy_api_host),
            )
            await client.health()
        elif row.platform == "youtube":
            from .publishers.youtube import ensure_access_token

            token, refreshed_secret = await ensure_access_token(secret)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "id,snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
            if refreshed_secret is not None:
                row.secret_ciphertext, row.secret_fingerprint = security.encrypt_secret(refreshed_secret)
        elif row.platform == "facebook":
            page_id = str(public.get("page_id") or "")
            graph_version = str(public.get("graph_version") or get_config().graph_api_version)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"https://graph.facebook.com/{graph_version}/{page_id}",
                    params={"fields": "id,name", "access_token": secret.get("page_access_token")},
                )
                response.raise_for_status()
        elif row.platform == "tiktok":
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    "https://open.tiktokapis.com/v2/user/info/",
                    params={"fields": "open_id,display_name"},
                    headers={"Authorization": f"Bearer {secret.get('access_token')}"},
                )
                response.raise_for_status()
        else:
            raise ConnectionError("Nền tảng chưa được hỗ trợ.", "AUTOMATION_PLATFORM_UNSUPPORTED")
        row.status = "ready"
        row.failure_reason = None
    except (security.SecretStoreError, ConnectionError, RoxyApiError) as exc:
        row.status = "needs_auth"
        row.failure_reason = str(exc)
    except (httpx.HTTPError, ValueError) as exc:
        row.status = "needs_auth"
        row.failure_reason = f"Không kiểm tra được connection {row.label}. Hãy kiểm tra token, scope và cấu hình."
    row.last_checked_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return to_response(row)
