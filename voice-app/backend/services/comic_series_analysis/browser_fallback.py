"""Isolated browser fallback for JS-rendered / lazy-loaded comic pages (§4).

Used only when static extraction is insufficient (task 4.5). The browser
runs in a throwaway context with no cookies, no stored profile, no
extensions and no filesystem access (task 4.6). Every request the page
generates is intercepted and passed through the same SSRF policy as static
fetch; private-network and dangerous-scheme requests are aborted (task 4.7).
Scrolling is bounded by rounds / height / time / new-asset count (task 4.8).

Playwright is imported lazily so a deployment without the browser binary
degrades to ``browser_unavailable`` instead of failing at import time.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from . import url_security
from .config import IngestPolicy, NetworkPolicy, get_config
from .contracts import ComicAnalysisError

logger = logging.getLogger(__name__)

_DANGEROUS_SCHEMES = ("file", "ftp", "chrome", "chrome-extension", "data", "blob", "ws", "wss")


def is_browser_available() -> bool:
    """Whether Playwright and a Chromium binary are usable."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


@dataclass
class BrowserRenderResult:
    """HTML plus observed image responses after browser render."""

    html: str
    final_url: str
    observed_image_urls: list[str] = field(default_factory=list)
    scroll_rounds: int = 0
    blocked_requests: int = 0


def _request_allowed(url: str, policy: NetworkPolicy) -> bool:
    """SSRF gate for a browser-generated request."""
    scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if scheme in _DANGEROUS_SCHEMES:
        return False
    if scheme not in policy.allowed_schemes:
        return False
    try:
        url_security.validate_and_resolve(url, policy=policy)
    except ComicAnalysisError:
        return False
    return True


def render(
    raw_url: str,
    *,
    network_policy: NetworkPolicy | None = None,
    ingest_policy: IngestPolicy | None = None,
) -> BrowserRenderResult:
    """Render a page in an isolated browser with bounded scrolling.

    Raises :class:`ComicAnalysisError` (``COMIC_NEEDS_UPLOAD``) if the browser
    runtime is unavailable so the caller can fall back to upload/paste.
    """
    net = network_policy or get_config().network
    ingest = ingest_policy or get_config().ingest

    # Validate the entry URL up front (same policy as static fetch).
    url_security.validate_and_resolve(raw_url, policy=net)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - import guard
        raise ComicAnalysisError(
            "COMIC_NEEDS_UPLOAD", "Trình duyệt không khả dụng; hãy upload ảnh."
        ) from exc

    observed_images: list[str] = []
    blocked = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                # Isolated, ephemeral context: no cookies/profile/downloads.
                context = browser.new_context(
                    accept_downloads=False,
                    java_script_enabled=True,
                    bypass_csp=False,
                )
                page = context.new_page()

                def _route(route):
                    nonlocal blocked
                    req_url = route.request.url
                    if not _request_allowed(req_url, net):
                        blocked += 1
                        route.abort()
                        return
                    route.continue_()

                page.route("**/*", _route)

                def _on_response(response):
                    ctype = (response.headers or {}).get("content-type", "")
                    if ctype.startswith("image/"):
                        observed_images.append(response.url)

                page.on("response", _on_response)

                page.goto(
                    raw_url,
                    timeout=int(net.total_timeout_seconds * 1000),
                    wait_until="domcontentloaded",
                )

                rounds = _bounded_scroll(page, ingest, observed_images)
                html = page.content()
                final_url = page.url
            finally:
                browser.close()
    except ComicAnalysisError:
        raise
    except Exception as exc:
        raise ComicAnalysisError(
            "COMIC_NEEDS_UPLOAD", f"Browser render lỗi: {exc}"
        ) from exc

    # Deduplicate observed image URLs, keep first-seen order.
    seen: set[str] = set()
    unique_images = []
    for url in observed_images:
        if url not in seen:
            seen.add(url)
            unique_images.append(url)

    return BrowserRenderResult(
        html=html,
        final_url=url_security.redact_url(final_url),
        observed_image_urls=unique_images,
        scroll_rounds=rounds,
        blocked_requests=blocked,
    )


def _bounded_scroll(page, ingest: IngestPolicy, observed_images: list[str]) -> int:
    """Scroll until the page stops growing or a limit is hit (task 4.8)."""
    start = time.monotonic()
    last_height = 0
    rounds = 0
    for _ in range(ingest.browser_max_scroll_rounds):
        if time.monotonic() - start > ingest.browser_max_scroll_seconds:
            break
        if len(observed_images) >= ingest.browser_max_new_assets:
            break
        height = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
        if height > ingest.browser_max_scroll_height_px:
            break
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)
        rounds += 1
        if height == last_height:
            break  # page stopped changing
        last_height = height
    return rounds


__all__ = ["BrowserRenderResult", "is_browser_available", "render"]
