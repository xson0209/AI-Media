"""Runtime configuration for the isolated Automation Hub."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ... import config as app_config


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError:
        return default


def _loopback_url(value: str, default: str) -> str:
    candidate = (value or default).rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return default.rstrip("/")
    return candidate


@dataclass(frozen=True)
class AutomationHubConfig:
    enabled: bool
    direct_post_enabled: bool
    publishing_concurrency: int
    max_upload_bytes: int
    retry_attempts: int
    roxy_api_host: str
    roxy_timeout_seconds: float
    sidecar_health_url: str
    sidecar_entry_path: Path
    sidecar_host: str
    sidecar_port: int
    graph_api_version: str
    data_root: Path


def get_config() -> AutomationHubConfig:
    data_root = (app_config.get_data_dir() / "automation_hub").resolve()
    default_entry = data_root / "roxybrowserlabs" / "roxybrowser-playwright-mcp" / "dist" / "bin" / "roxybrowser-mcp.js"
    entry_raw = os.environ.get("VOICEBOX_ROXY_PLAYWRIGHT_ENTRY")
    entry = Path(entry_raw).expanduser().resolve() if entry_raw else default_entry
    port = _int_env("VOICEBOX_ROXY_PLAYWRIGHT_PORT", 3333, minimum=1, maximum=65535)
    host = os.environ.get("VOICEBOX_ROXY_PLAYWRIGHT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host not in {"127.0.0.1", "localhost", "::1"}:
        host = "127.0.0.1"
    default_health = f"http://127.0.0.1:{port}/health"
    return AutomationHubConfig(
        enabled=app_config.is_feature_enabled("automation_hub", default=False),
        direct_post_enabled=app_config.is_feature_enabled("automation_hub_tiktok_direct_post", default=False),
        publishing_concurrency=_int_env("VOICEBOX_AUTOMATION_PUBLISHING_CONCURRENCY", 1, minimum=1, maximum=3),
        max_upload_bytes=_int_env(
            "VOICEBOX_AUTOMATION_MAX_UPLOAD_BYTES",
            8 * 1024 * 1024 * 1024,
            minimum=1024,
            maximum=64 * 1024 * 1024 * 1024,
        ),
        retry_attempts=_int_env("VOICEBOX_AUTOMATION_RETRY_ATTEMPTS", 2, minimum=1, maximum=4),
        roxy_api_host=_loopback_url(
            os.environ.get("VOICEBOX_ROXY_API_HOST", ""),
            "http://127.0.0.1:50000",
        ),
        roxy_timeout_seconds=float(_int_env("VOICEBOX_ROXY_TIMEOUT_SECONDS", 30, minimum=3, maximum=120)),
        sidecar_health_url=_loopback_url(
            os.environ.get("VOICEBOX_ROXY_PLAYWRIGHT_HEALTH_URL", ""),
            default_health,
        ),
        sidecar_entry_path=entry,
        sidecar_host=host,
        sidecar_port=port,
        graph_api_version=os.environ.get("VOICEBOX_META_GRAPH_API_VERSION", "v23.0").strip() or "v23.0",
        data_root=data_root,
    )


def require_enabled() -> AutomationHubConfig:
    cfg = get_config()
    if not cfg.enabled:
        raise AutomationHubDisabledError(
            "Automation Hub đang tắt. Hãy đặt VOICEBOX_FEATURE_AUTOMATION_HUB=true rồi khởi động lại backend."
        )
    return cfg


class AutomationHubDisabledError(RuntimeError):
    error_code = "AUTOMATION_HUB_DISABLED"
