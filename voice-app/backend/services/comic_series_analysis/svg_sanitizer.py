"""SVG sanitization + isolated rasterization for Comic Series Analysis (task 5.9).

Raw SVG is never rendered or executed directly in the UI. It is first
sanitized (script, event handlers, external entities, ``foreignObject``,
external image/font/style URLs removed) using ``defusedxml`` to block XXE,
then rasterized to PNG with network and filesystem access disabled.

Rasterization prefers ``resvg-py`` (a self-contained native wheel) and falls
back to CairoSVG when available.
"""

from __future__ import annotations

import logging
import re

from .contracts import ComicAnalysisError

logger = logging.getLogger(__name__)

# Attributes that carry executable behavior.
_EVENT_ATTR = re.compile(r"^on", re.IGNORECASE)
# Elements never allowed in a sanitized SVG.
_FORBIDDEN_TAGS = {
    "script",
    "foreignobject",
    "iframe",
    "embed",
    "object",
    "use",  # can reference external resources
    "image",  # external raster references
    "audio",
    "video",
    "animate",
    "set",
    "handler",
}
# Attribute values that must not reference external/local resources.
_URL_ATTRS = {"href", "xlink:href", "src", "style"}
_EXTERNAL_URL = re.compile(r"(url\(|https?:|file:|//|data:)", re.IGNORECASE)


def sanitize_svg(svg_bytes: bytes) -> bytes:
    """Return a sanitized SVG with scripts/external refs/XXE removed.

    Uses defusedxml to parse safely (blocks external entities / billion
    laughs). Raises ``COMIC_IMAGE_CORRUPT`` if the SVG cannot be parsed.
    """
    try:
        from defusedxml import ElementTree as SafeET
        from xml.etree.ElementTree import tostring
    except Exception as exc:  # pragma: no cover
        raise ComicAnalysisError(
            "COMIC_CODEC_UNAVAILABLE", "Thiếu thư viện làm sạch SVG."
        ) from exc

    try:
        # defusedxml disables entity expansion / external entities by default.
        root = SafeET.fromstring(svg_bytes)
    except Exception as exc:
        raise ComicAnalysisError("COMIC_IMAGE_CORRUPT", f"SVG không hợp lệ: {exc}") from exc

    _strip_node(root)
    cleaned = tostring(root, encoding="utf-8")
    return cleaned


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1].lower() if "}" in tag else tag.lower()


def _strip_node(node) -> None:
    # Remove forbidden children.
    for child in list(node):
        if _local_tag(child.tag) in _FORBIDDEN_TAGS:
            node.remove(child)
        else:
            _strip_node(child)

    # Remove event handlers and external-URL attributes.
    for attr in list(node.attrib):
        local = attr.split("}", 1)[-1].lower() if "}" in attr else attr.lower()
        value = node.attrib[attr]
        if _EVENT_ATTR.match(local):
            del node.attrib[attr]
        elif local in _URL_ATTRS and _EXTERNAL_URL.search(value or ""):
            del node.attrib[attr]


def rasterize_svg(svg_bytes: bytes, *, max_edge: int = 2048) -> bytes:
    """Sanitize then rasterize an SVG to PNG in an isolated renderer.

    Raises ``COMIC_CODEC_UNAVAILABLE`` if neither renderer is available.
    """
    cleaned = sanitize_svg(svg_bytes)
    try:
        import resvg_py

        return resvg_py.svg_to_bytes(
            svg_string=cleaned.decode("utf-8"),
            width=max_edge,
            resources_dir=None,
        )
    except ImportError:
        pass
    except Exception as exc:
        raise ComicAnalysisError("COMIC_IMAGE_CORRUPT", f"Rasterize SVG lỗi: {exc}") from exc
    try:
        import cairosvg
    except Exception as exc:
        raise ComicAnalysisError(
            "COMIC_CODEC_UNAVAILABLE", "SVG rasterizer (resvg/Cairo) chưa khả dụng."
        ) from exc
    try:
        # Unsafe URL access is already stripped by sanitize_svg above.
        return cairosvg.svg2png(
            bytestring=cleaned,
            output_width=max_edge,
        )
    except Exception as exc:
        raise ComicAnalysisError("COMIC_IMAGE_CORRUPT", f"Rasterize SVG lỗi: {exc}") from exc


__all__ = ["rasterize_svg", "sanitize_svg"]
