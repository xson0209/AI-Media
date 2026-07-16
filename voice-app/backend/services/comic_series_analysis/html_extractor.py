"""HTML parsing and content extraction for Comic Series Analysis (§4).

Parses fetched HTML with BeautifulSoup + lxml, selects the main content
region, strips noise (script/style/nav/ads/hidden), and produces ordered
text chunks plus ordered image URLs discovered via src/srcset/picture/
lazy-load/Open Graph. Relative URLs are resolved against the page URL at
discovery time.

All extracted text is *data*, never instructions — the caller wraps it in
an untrusted-source envelope (task 4.9). This module simply marks whether
any prompt-injection-looking phrases were seen so the pipeline can flag it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

EXTRACTOR_VERSION = "comic_html_extractor.v1"

# Tags whose content is never creative source.
_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "nav",
    "aside",
    "footer",
    "header",
    "template",
    "svg",
)

# Class/id substrings that strongly indicate non-content chrome.
_NOISE_HINTS = (
    "advert",
    "ads",
    "adsbygoogle",
    "comment",
    "sidebar",
    "menu",
    "navbar",
    "breadcrumb",
    "share",
    "social",
    "related",
    "recommend",
    "popup",
    "modal",
    "cookie",
    "banner",
)

# Attributes commonly used for lazy-loaded image URLs.
_LAZY_ATTRS = (
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-lazy",
    "data-url",
    "data-echo",
    "data-image",
)

# Phrases that look like prompt injection (task 4.9). Detection only — the
# content is still stored, just flagged.
_INJECTION_PATTERNS = re.compile(
    r"(ignore (all |previous )?instructions|bỏ qua (mọi |các )?quy tắc|"
    r"system prompt|đọc file|read file|gọi công cụ|call tool|reveal|"
    r"you are now|bạn bây giờ là)",
    re.IGNORECASE,
)


@dataclass
class ExtractedImage:
    """One discovered image URL with provenance."""

    url: str
    dom_order: int
    discovered_via: str  # src | srcset | picture | lazy | og | css | data_uri
    alt: str | None = None
    caption: str | None = None
    data_uri: bool = False


@dataclass
class ExtractedContent:
    """Structured result of HTML extraction."""

    title: str | None = None
    author: str | None = None
    chapter_identity: str | None = None
    text_chunks: list[str] = field(default_factory=list)
    images: list[ExtractedImage] = field(default_factory=list)
    extractor_version: str = EXTRACTOR_VERSION
    injection_flagged: bool = False
    js_shell_suspected: bool = False


def _is_hidden(tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    if tag.get("hidden") is not None:
        return True
    if tag.get("aria-hidden") == "true":
        return True
    return False


def _looks_noisy(tag) -> bool:
    identifiers = " ".join(
        filter(None, [" ".join(tag.get("class", [])), tag.get("id") or ""])
    ).lower()
    return any(hint in identifiers for hint in _NOISE_HINTS)


def _select_main(soup: BeautifulSoup):
    """Pick the most content-rich region, preferring semantic containers."""
    for selector in (
        ".reading-content",
        ".chapter-content",
        "#chapter-content",
        ".wp-manga-chapter",
        ".manga-content",
        ".chapter-images",
        ".entry-content",
        "article",
        "main",
        '[role="main"]',
    ):
        node = soup.select_one(selector)
        if node is not None:
            return node
    # Fall back to the container with the most text among common wrappers.
    candidates = soup.find_all(["div", "section"], recursive=True)
    best = None
    best_len = 0
    for node in candidates:
        if _looks_noisy(node):
            continue
        text_len = len(node.get_text(strip=True))
        if text_len > best_len:
            best_len = text_len
            best = node
    return best or soup.body or soup


def _is_lazy_placeholder_src(src: str | None) -> bool:
    value = (src or "").strip().lower()
    if not value.startswith("data:image/"):
        return False
    return value.startswith("data:image/gif;base64,r0lgodlhaq")

def _resolve(base_url: str, url: str) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith("data:"):
        return url
    resolved = urljoin(base_url, url)
    scheme = urlsplit(resolved).scheme.lower()
    if scheme not in {"http", "https", "data"}:
        return None
    return resolved


def _collect_images(root, base_url: str) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    seen: set[str] = set()
    order = 0

    def add(url: str | None, via: str, alt=None, caption=None):
        nonlocal order
        if not url or url in seen:
            return
        seen.add(url)
        images.append(
            ExtractedImage(
                url=url,
                dom_order=order,
                discovered_via=via,
                alt=alt,
                caption=caption,
                data_uri=url.startswith("data:"),
            )
        )
        order += 1

    for img in root.find_all("img"):
        alt = img.get("alt")
        # Prefer lazy attributes if src is a placeholder.
        lazy_found = False
        for attr in _LAZY_ATTRS:
            if img.get(attr):
                lazy_found = True
                add(_resolve(base_url, img.get(attr)), "lazy", alt=alt)
        if img.get("src"):
            src = img.get("src")
            if not (lazy_found and _is_lazy_placeholder_src(src)):
                add(_resolve(base_url, src), "src", alt=alt)
        srcset = img.get("srcset")
        if srcset:
            # Take the largest candidate (last entry commonly highest-res).
            for entry in srcset.split(","):
                url = entry.strip().split(" ")[0]
                add(_resolve(base_url, url), "srcset", alt=alt)

    for source in root.find_all("source"):
        srcset = source.get("srcset")
        if srcset:
            for entry in srcset.split(","):
                url = entry.strip().split(" ")[0]
                add(_resolve(base_url, url), "picture")

    return images


def _collect_og_images(soup: BeautifulSoup, base_url: str, existing: list[ExtractedImage]) -> None:
    order = len(existing)
    seen = {img.url for img in existing}
    for meta in soup.find_all("meta", property=re.compile(r"^og:image", re.I)):
        url = _resolve(base_url, meta.get("content"))
        if url and url not in seen:
            seen.add(url)
            existing.append(ExtractedImage(url=url, dom_order=order, discovered_via="og"))
            order += 1


def _extract_text_chunks(root) -> list[str]:
    chunks: list[str] = []
    for tag in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        if _is_hidden(tag) or _looks_noisy(tag):
            continue
        text = tag.get_text(" ", strip=True)
        if text and len(text) > 1:
            chunks.append(text)
    return chunks


def extract(html: str, base_url: str) -> ExtractedContent:
    """Extract ordered text and image URLs from an HTML document."""
    soup = BeautifulSoup(html, "lxml")

    # Strip noise tags globally before selecting main content.
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og_title = soup.find("meta", property=re.compile(r"^og:title", re.I))
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()

    author = None
    author_meta = soup.find("meta", attrs={"name": re.compile(r"author", re.I)})
    if author_meta and author_meta.get("content"):
        author = author_meta["content"].strip()

    main = _select_main(soup)
    text_chunks = _extract_text_chunks(main)
    images = _collect_images(main, base_url)
    if not images:
        _collect_og_images(soup, base_url, images)

    joined = "\n".join(text_chunks)
    injection_flagged = bool(_INJECTION_PATTERNS.search(joined))

    # JS-shell heuristic: almost no text and no images from a real body.
    js_shell_suspected = len(joined) < 200 and len(images) == 0

    return ExtractedContent(
        title=title,
        author=author,
        text_chunks=text_chunks,
        images=images,
        injection_flagged=injection_flagged,
        js_shell_suspected=js_shell_suspected,
    )


__all__ = ["EXTRACTOR_VERSION", "ExtractedContent", "ExtractedImage", "extract"]
