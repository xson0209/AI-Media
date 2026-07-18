"""Streaming, SSRF-safe HTTP fetcher for Comic Series Analysis.

Wraps ``httpx`` with:
  - ``trust_env=False`` and no ambient proxy/credentials (task 3.4).
  - Manual, per-hop redirect validation so every redirect target is
    re-checked against the SSRF policy (task 3.2).
  - Per-phase timeouts, a finite redirect cap and a post-decompression byte
    budget (tasks 3.4, 3.10).
  - Content classification into HTML / direct-image / unsupported using both
    the declared Content-Type and magic bytes (task 3.5).

Access-control-aware: authentication / CAPTCHA / access-denied responses are
surfaced as outcome codes, never bypassed (task 3.7).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from . import url_security
from .config import NetworkPolicy, get_config
from .contracts import ComicAnalysisError

logger = logging.getLogger(__name__)

# Magic-byte signatures for the image formats we recognize (task 3.5, 5.4).
_IMAGE_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
)


def sniff_image_format(head: bytes) -> str | None:
    """Return a detected image format from magic bytes, or None."""
    for signature, name in _IMAGE_MAGIC:
        if head.startswith(signature):
            return name
    # RIFF/WEBP: "RIFF"...."WEBP"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    # HEIF/AVIF: "....ftyp" then a brand.
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"heim", b"heis", b"mif1", b"msf1"):
            return "heif"
        if brand in (b"avif", b"avis"):
            return "avif"
    # SVG (text) — starts with "<?xml" or "<svg" possibly after BOM/whitespace.
    stripped = head.lstrip()[:6].lower()
    if stripped.startswith(b"<svg") or stripped.startswith(b"<?xml"):
        return "svg"
    return None


ContentKind = str  # "html" | "image" | "unsupported"


@dataclass
class FetchResult:
    """The outcome of one fetch."""

    final_url: str
    status_code: int
    content_kind: ContentKind
    content: bytes
    declared_content_type: str | None = None
    detected_format: str | None = None
    truncated: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    outcome_code: str | None = None


def _classify(content_type: str | None, head: bytes) -> tuple[ContentKind, str | None]:
    detected = sniff_image_format(head)
    if detected is not None:
        return "image", detected
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype in {"text/html", "application/xhtml+xml"} or head.lstrip()[:1] == b"<":
        return "html", None
    if ctype.startswith("image/"):
        # Declared image but unknown magic — treat as unsupported image.
        return "unsupported", None
    return "unsupported", None


def _outcome_for_status(status: int) -> str | None:
    if status in (401,):
        return "authentication_required"
    if status in (403,):
        return "access_denied"
    if status in (407,):
        return "authentication_required"
    if status == 429:
        return "access_denied"
    return None


def _new_client(policy: NetworkPolicy) -> httpx.Client:
    timeout = httpx.Timeout(
        connect=policy.connect_timeout_seconds,
        read=policy.read_timeout_seconds,
        write=policy.read_timeout_seconds,
        pool=policy.connect_timeout_seconds,
    )
    return httpx.Client(
        trust_env=policy.trust_env,
        follow_redirects=False,  # we validate each hop ourselves
        timeout=timeout,
        headers={"User-Agent": "ComicSeriesAnalysis/1.0 (+best-effort)"},
    )


def fetch(
    raw_url: str,
    *,
    kind: str = "any",
    policy: NetworkPolicy | None = None,
    max_bytes: int | None = None,
    client: httpx.Client | None = None,
) -> FetchResult:
    """Fetch a URL with full SSRF validation and manual redirect handling.

    ``kind`` may be ``"html"``, ``"image"`` or ``"any"`` to bound the byte
    budget. Raises :class:`ComicAnalysisError` on policy violations, timeouts
    or over-budget content; sets ``outcome_code`` for auth/captcha/denied.
    """
    policy = policy or get_config().network
    if max_bytes is None:
        max_bytes = policy.max_image_bytes if kind == "image" else policy.max_html_bytes

    owns_client = client is None
    http = client or _new_client(policy)
    redirect_chain: list[str] = []
    current = raw_url
    try:
        for _hop in range(policy.max_redirects + 1):
            url_security.validate_and_resolve(current, policy=policy)
            try:
                with http.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ComicAnalysisError(
                                "COMIC_URL_REDIRECT_BLOCKED", "Redirect thiếu Location."
                            )
                        current = str(response.url.join(location))
                        redirect_chain.append(url_security.redact_url(current))
                        continue

                    outcome = _outcome_for_status(response.status_code)
                    if outcome is not None:
                        return FetchResult(
                            final_url=url_security.redact_url(str(response.url)),
                            status_code=response.status_code,
                            content_kind="unsupported",
                            content=b"",
                            declared_content_type=response.headers.get("content-type"),
                            redirect_chain=redirect_chain,
                            outcome_code=outcome,
                        )

                    # Stream with a hard byte budget (post-decompression).
                    chunks: list[bytes] = []
                    total = 0
                    truncated = False
                    for chunk in response.iter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            truncated = True
                            break
                    body = b"".join(chunks)
                    if truncated:
                        raise ComicAnalysisError(
                            "COMIC_FETCH_TOO_LARGE",
                            f"Nội dung vượt {max_bytes} byte.",
                        )
                    content_type = response.headers.get("content-type")
                    content_kind, detected = _classify(content_type, body[:64])
                    return FetchResult(
                        final_url=url_security.redact_url(str(response.url)),
                        status_code=response.status_code,
                        content_kind=content_kind,
                        content=body,
                        declared_content_type=content_type,
                        detected_format=detected,
                        truncated=False,
                        redirect_chain=redirect_chain,
                    )
            except httpx.TimeoutException as exc:
                raise ComicAnalysisError("COMIC_FETCH_TIMEOUT", "Hết thời gian chờ.") from exc
            except httpx.HTTPError as exc:
                raise ComicAnalysisError(
                    "COMIC_NEEDS_UPLOAD", f"Không tải được nguồn: {exc}"
                ) from exc

        raise ComicAnalysisError("COMIC_URL_TOO_MANY_REDIRECTS", "Quá nhiều lần chuyển hướng.")
    finally:
        if owns_client:
            http.close()


__all__ = ["FetchResult", "fetch", "sniff_image_format"]
