"""Facebook Page resumable video uploader."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timezone

import httpx

from ..config import get_config
from .base import PublishRequest, PublishResult, PublisherError, provider_http_error


class FacebookPublisher:
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
        page_id = str(request.public_config.get("page_id") or "").strip()
        token = str(request.secret.get("page_access_token") or "").strip()
        if not page_id:
            raise PublisherError("Facebook chỉ hỗ trợ Page và cần page_id.", error_code="FACEBOOK_PAGE_ID_REQUIRED")
        if not token:
            raise PublisherError("Thiếu Facebook Page access token.", error_code="FACEBOOK_PAGE_TOKEN_REQUIRED")
        graph_version = str(request.public_config.get("graph_version") or get_config().graph_api_version)
        endpoint = f"https://graph-video.facebook.com/{graph_version}/{page_id}/videos"
        size = request.asset_path.stat().st_size
        video_id = ""
        async with self._client() as client:
            try:
                request.checkpoint()
                start = await client.post(
                    endpoint,
                    data={"upload_phase": "start", "file_size": str(size), "access_token": token},
                )
                start.raise_for_status()
                start_payload = start.json()
                session_id = str(start_payload.get("upload_session_id") or "")
                video_id = str(start_payload.get("video_id") or "")
                start_offset = int(start_payload.get("start_offset") or 0)
                end_offset = int(start_payload.get("end_offset") or 0)
                if not session_id:
                    raise PublisherError(
                        "Facebook không tạo được resumable upload session.",
                        error_code="FACEBOOK_UPLOAD_SESSION_INVALID",
                    )
                with request.asset_path.open("rb") as handle:
                    while start_offset < size:
                        request.checkpoint()
                        handle.seek(start_offset)
                        wanted = max(1, end_offset - start_offset) if end_offset > start_offset else 4 * 1024 * 1024
                        chunk = handle.read(min(wanted, 8 * 1024 * 1024))
                        if not chunk:
                            break
                        transfer = await client.post(
                            endpoint,
                            data={
                                "upload_phase": "transfer",
                                "upload_session_id": session_id,
                                "start_offset": str(start_offset),
                                "access_token": token,
                            },
                            files={"video_file_chunk": ("chunk.bin", chunk, "application/octet-stream")},
                        )
                        transfer.raise_for_status()
                        transfer_payload = transfer.json()
                        next_start = int(transfer_payload.get("start_offset") or (start_offset + len(chunk)))
                        end_offset = int(transfer_payload.get("end_offset") or next_start)
                        if next_start <= start_offset:
                            raise PublisherError(
                                "Facebook không tiến triển offset upload.",
                                error_code="FACEBOOK_UPLOAD_OFFSET_INVALID",
                            )
                        start_offset = next_start
                request.checkpoint()
                finish_data = {
                    "upload_phase": "finish",
                    "upload_session_id": session_id,
                    "title": request.title,
                    "description": request.description,
                    "access_token": token,
                }
                if request.scheduled_at is not None:
                    scheduled = request.scheduled_at
                    if scheduled.tzinfo is None:
                        scheduled = scheduled.replace(tzinfo=timezone.utc)
                    finish_data.update(
                        {
                            "published": "false",
                            "scheduled_publish_time": str(int(scheduled.timestamp())),
                        }
                    )
                finish = await client.post(endpoint, data=finish_data)
                finish.raise_for_status()
                finish_payload = finish.json()
            except PublisherError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise provider_http_error("facebook", exc, ambiguous=bool(video_id)) from exc
        if not video_id:
            video_id = str(finish_payload.get("video_id") or finish_payload.get("id") or "")
        if not video_id:
            raise PublisherError(
                "Facebook upload hoàn tất nhưng thiếu video id.",
                error_code="FACEBOOK_RESPONSE_INVALID",
                ambiguous=True,
            )
        return PublishResult(
            provider_post_id=video_id,
            provider_url=f"https://www.facebook.com/{video_id}",
            result={"scheduled": request.scheduled_at is not None, "success": bool(finish_payload.get("success", True))},
        )
