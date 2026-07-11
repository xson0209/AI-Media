"""HTTP response helpers shared by routes and the app factory."""

from __future__ import annotations

from urllib.parse import quote


def safe_content_disposition(disposition_type: str, filename: str) -> str:
    """Build a Content-Disposition header safe for non-ASCII filenames."""
    ascii_name = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in " -_.")).strip() or "download"
    utf8_name = quote(filename, safe="")
    return f"{disposition_type}; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
