"""Safe logging / diagnostics for Comic Series Analysis (task 11.5, §25).

Logs must never leak credentials, sensitive query params, cookies, long
source text or binary image bytes. This module provides redaction helpers
and a structured event logger that only emits counts, byte sizes, formats,
durations, step names, error codes and shortened checksums.
"""

from __future__ import annotations

import logging

from .url_security import redact_url

logger = logging.getLogger("comic_series_analysis")

_MAX_TEXT_PREVIEW = 80


def short_checksum(checksum: str | None) -> str | None:
    """Return a shortened checksum safe for logs."""
    if not checksum:
        return None
    return checksum[:12]


def redact_text(value: str | None) -> str | None:
    """Never log full source text — only a length + short preview."""
    if value is None:
        return None
    preview = value[:_MAX_TEXT_PREVIEW].replace("\n", " ")
    return f"len={len(value)} preview={preview!r}"


def safe_event(event: str, **fields) -> dict:
    """Build a redacted structured log payload.

    URLs are redacted; anything named like a secret is dropped; text is
    summarized; bytes objects become sizes.
    """
    safe: dict[str, object] = {"event": event}
    for key, value in fields.items():
        lowered = key.lower()
        if any(s in lowered for s in ("cookie", "token", "authorization", "secret", "password", "prompt")):
            continue  # never log these
        if lowered.endswith("url") and isinstance(value, str):
            safe[key] = redact_url(value)
        elif lowered.endswith("checksum") and isinstance(value, str):
            safe[key] = short_checksum(value)
        elif isinstance(value, (bytes, bytearray)):
            safe[key] = f"bytes={len(value)}"
        elif key in ("text", "html", "source", "content") and isinstance(value, str):
            safe[key] = redact_text(value)
        else:
            safe[key] = value
    return safe


def log_event(event: str, *, level: int = logging.INFO, **fields) -> None:
    """Emit a redacted structured event to the comic logger."""
    payload = safe_event(event, **fields)
    logger.log(level, "comic_event %s", payload)


__all__ = ["log_event", "redact_text", "safe_event", "short_checksum"]
