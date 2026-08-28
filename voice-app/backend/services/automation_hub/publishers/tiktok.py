"""TikTok Content Posting API uploader (Draft by default)."""

from __future__ import annotations

import math
from contextlib import asynccontextmanager

import httpx

from ..config import get_config
from .base import PublishRequest, PublishResult, PublisherError, provider_http_error


DRAFT_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
DIRECT_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


class TikTokPublisher:
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
        token = str(request.secret.get("access_token") or "").strip()
        if not token:
            raise PublisherError("Thiếu TikTok access token.", error_code="TIKTOK_ACCESS_TOKEN_REQUIRED")
        direct = request.publish_mode == "direct"
        if direct and not get_config().direct_post_enabled:
            raise PublisherError(
                "TikTok Direct Post đang tắt hoặc ứng dụng chưa được audit. Hãy dùng Draft.",
                error_code="TIKTOK_DIRECT_POST_DISABLED",
            )
        size = request.asset_path.stat().st_size
        chunk_size = size if size < 5 * 1024 * 1024 else min(size, 64 * 1024 * 1024)
        total_chunks = max(1, math.ceil(size / chunk_size))
        body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }
        endpoint = DRAFT_INIT_URL
        if direct:
            endpoint = DIRECT_INIT_URL
            body["post_info"] = {
                "title": request.title or request.description[:150],
                "privacy_level": request.privacy or "SELF_ONLY",
                "disable_duet": bool(request.public_config.get("disable_duet", False)),
                "disable_comment": bool(request.public_config.get("disable_comment", False)),
                "disable_stitch": bool(request.public_config.get("disable_stitch", False)),
                "video_cover_timestamp_ms": int(request.public_config.get("video_cover_timestamp_ms") or 1000),
            }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
        async with self._client() as client:
            try:
                request.checkpoint()
                initialized = await client.post(endpoint, headers=headers, json=body)
                initialized.raise_for_status()
                payload = initialized.json()
                data = payload.get("data") or {}
                upload_url = str(data.get("upload_url") or "")
                publish_id = str(data.get("publish_id") or "")
                if not upload_url or not publish_id:
                    raise PublisherError(
                        "TikTok không trả upload_url hoặc publish_id.",
                        error_code="TIKTOK_INIT_RESPONSE_INVALID",
                    )
                with request.asset_path.open("rb") as handle:
                    offset = 0
                    while offset < size:
                        request.checkpoint()
                        chunk = handle.read(chunk_size)
                        if not chunk:
                            break
                        end = offset + len(chunk) - 1
                        uploaded = await client.put(
                            upload_url,
                            headers={
                                "Content-Type": request.mime_type,
                                "Content-Length": str(len(chunk)),
                                "Content-Range": f"bytes {offset}-{end}/{size}",
                            },
                            content=chunk,
                        )
                        uploaded.raise_for_status()
                        offset = end + 1
            except PublisherError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise provider_http_error("tiktok", exc, ambiguous="publish_id" in locals()) from exc
        return PublishResult(
            provider_post_id=publish_id,
            provider_url=None,
            result={"mode": "direct" if direct else "draft", "total_chunks": total_chunks},
        )
