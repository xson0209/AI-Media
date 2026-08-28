"""Canonical contracts shared by platform publishers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx


class PublisherError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        retryable: bool = False,
        ambiguous: bool = False,
        response_meta: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.response_meta = response_meta or {}


class PublishCancelled(PublisherError):
    def __init__(self):
        super().__init__(
            "Publishing job đã được hủy.",
            error_code="AUTOMATION_PUBLISH_CANCELLED",
            retryable=False,
        )


@dataclass(frozen=True)
class PublishRequest:
    job_id: str
    asset_path: Path
    mime_type: str
    title: str
    description: str
    tags: list[str]
    privacy: str | None
    scheduled_at: datetime | None
    publish_mode: str
    public_config: dict[str, Any]
    secret: dict[str, Any]
    is_cancelled: Callable[[], bool] = field(default=lambda: False)

    def checkpoint(self) -> None:
        if self.is_cancelled():
            raise PublishCancelled()


@dataclass(frozen=True)
class PublishResult:
    provider_post_id: str
    provider_url: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    updated_secret: dict[str, Any] | None = None


class Publisher(Protocol):
    async def publish(self, request: PublishRequest) -> PublishResult: ...


def provider_http_error(platform: str, exc: Exception, *, ambiguous: bool = False) -> PublisherError:
    if isinstance(exc, httpx.TimeoutException):
        return PublisherError(
            f"{platform} không phản hồi trong thời gian cho phép.",
            error_code=f"{platform.upper()}_TIMEOUT",
            retryable=not ambiguous,
            ambiguous=ambiguous,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return PublisherError(
            f"{platform} từ chối request (HTTP {status}). Hãy kiểm tra token, scope và metadata.",
            error_code=f"{platform.upper()}_HTTP_{status}",
            retryable=status == 429 or status >= 500,
            ambiguous=ambiguous,
            response_meta={"http_status": status},
        )
    return PublisherError(
        f"Không kết nối được {platform}.",
        error_code=f"{platform.upper()}_NETWORK_ERROR",
        retryable=not ambiguous,
        ambiguous=ambiguous,
    )


def get_publisher(platform: str, *, client: httpx.AsyncClient | None = None) -> Publisher:
    if platform == "youtube":
        from .youtube import YouTubePublisher

        return YouTubePublisher(client=client)
    if platform == "facebook":
        from .facebook import FacebookPublisher

        return FacebookPublisher(client=client)
    if platform == "tiktok":
        from .tiktok import TikTokPublisher

        return TikTokPublisher(client=client)
    raise PublisherError(
        "Nền tảng publishing chưa được hỗ trợ.",
        error_code="AUTOMATION_PLATFORM_UNSUPPORTED",
    )
