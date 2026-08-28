"""YouTube Data API resumable video uploader."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import httpx

from .base import PublishRequest, PublishResult, PublisherError, provider_http_error


TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def _expires_soon(secret: dict) -> bool:
    value = secret.get("expires_at")
    if value is None:
        return False
    try:
        if isinstance(value, (int, float)):
            expires = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        return (expires - datetime.now(timezone.utc)).total_seconds() < 90
    except (ValueError, TypeError, OSError):
        return True


async def ensure_access_token(
    secret: dict,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, dict | None]:
    access_token = str(secret.get("access_token") or "")
    if access_token and not _expires_soon(secret):
        return access_token, None
    refresh_token = str(secret.get("refresh_token") or "")
    client_id = str(secret.get("client_id") or "")
    client_secret = str(secret.get("client_secret") or "")
    if not (refresh_token and client_id and client_secret):
        if access_token:
            return access_token, None
        raise PublisherError(
            "YouTube credential không có access token hoặc refresh token hợp lệ.",
            error_code="YOUTUBE_AUTH_REQUIRED",
        )
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise provider_http_error("youtube", exc) from exc
    finally:
        if owns_client:
            await http.aclose()
    token = str(payload.get("access_token") or "")
    if not token:
        raise PublisherError("YouTube không trả access token.", error_code="YOUTUBE_TOKEN_RESPONSE_INVALID")
    updated = dict(secret)
    updated["access_token"] = token
    expires_in = int(payload.get("expires_in") or 3600)
    updated["expires_at"] = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + expires_in,
        tz=timezone.utc,
    ).isoformat()
    return token, updated


async def _file_stream(path, chunk_size: int = 4 * 1024 * 1024) -> AsyncIterator[bytes]:
    handle = path.open("rb")
    try:
        while True:
            chunk = await asyncio.to_thread(handle.read, chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        handle.close()


class YouTubePublisher:
    def __init__(self, *, client: httpx.AsyncClient | None = None):
        self.client = client

    @asynccontextmanager
    async def _client(self):
        if self.client is not None:
            yield self.client
            return
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, read=600.0)) as client:
            yield client

    async def publish(self, request: PublishRequest) -> PublishResult:
        request.checkpoint()
        async with self._client() as client:
            token, updated_secret = await ensure_access_token(request.secret, client)
            privacy = request.privacy or "private"
            status: dict[str, object] = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
            if request.scheduled_at is not None:
                scheduled = request.scheduled_at
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=timezone.utc)
                status["privacyStatus"] = "private"
                status["publishAt"] = scheduled.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            metadata = {
                "snippet": {
                    "title": request.title.strip() or request.asset_path.stem,
                    "description": request.description,
                    "tags": [tag.lstrip("#") for tag in request.tags if tag.strip()],
                    "categoryId": str(request.public_config.get("category_id") or "22"),
                },
                "status": status,
            }
            size = request.asset_path.stat().st_size
            upload_started = False
            try:
                init = await client.post(
                    UPLOAD_URL,
                    params={"uploadType": "resumable", "part": "snippet,status"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Length": str(size),
                        "X-Upload-Content-Type": request.mime_type,
                    },
                    json=metadata,
                )
                init.raise_for_status()
                upload_url = init.headers.get("Location")
                if not upload_url:
                    raise PublisherError(
                        "YouTube không trả resumable upload URL.",
                        error_code="YOUTUBE_UPLOAD_SESSION_INVALID",
                    )
                request.checkpoint()
                upload_started = True
                uploaded = await client.put(
                    upload_url,
                    headers={"Content-Type": request.mime_type, "Content-Length": str(size)},
                    content=_file_stream(request.asset_path),
                )
                uploaded.raise_for_status()
                payload = uploaded.json()
            except PublisherError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise provider_http_error("youtube", exc, ambiguous=upload_started) from exc
        video_id = str(payload.get("id") or "")
        if not video_id:
            raise PublisherError(
                "YouTube upload hoàn tất nhưng thiếu video id.",
                error_code="YOUTUBE_RESPONSE_INVALID",
                ambiguous=True,
            )
        return PublishResult(
            provider_post_id=video_id,
            provider_url=f"https://www.youtube.com/watch?v={video_id}",
            result={"privacy": status["privacyStatus"], "scheduled": request.scheduled_at is not None},
            updated_secret=updated_secret,
        )
