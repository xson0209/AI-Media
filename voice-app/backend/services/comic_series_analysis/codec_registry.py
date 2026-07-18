"""Image codec capability registry for Comic Series Analysis (§5).

Detects, at runtime, which image formats can actually be decoded/encoded on
this deployment — rather than branching on file extension. Each codec is
probed with a real fixture decode/encode so a missing native library
degrades to ``codec_unavailable`` instead of a late crash (tasks 5.1, 5.2a,
design §8).

Baseline (via Pillow): PNG, JPEG, WebP, GIF/APNG, TIFF, BMP.
HEIF adapter: HEIC/HEIF/MPO. AVIF adapter: AVIF. SVG adapter: sanitize +
rasterize with the bundled resvg wheel, falling back to CairoSVG.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger(__name__)

# Register optional Pillow plugins if present. Import failures are expected
# on deployments without the native libraries and must not crash.
try:  # HEIC/HEIF
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_IMPORTED = True
except Exception:  # pragma: no cover
    _HEIF_IMPORTED = False

try:  # AVIF (registers .avif with Pillow on import)
    import pillow_avif  # noqa: F401

    _AVIF_IMPORTED = True
except Exception:  # pragma: no cover
    _AVIF_IMPORTED = False


# The mandatory baseline the design requires for "full codec capability".
MANDATORY_FORMATS = (
    "png",
    "jpeg",
    "webp",
    "heif",
    "avif",
    "gif",
    "apng",
    "tiff",
    "bmp",
    "mpo",
    "svg",
)


@dataclass(frozen=True)
class CodecCapability:
    """Capability record for one format."""

    format: str
    can_decode: bool
    can_encode: bool
    supports_frames: bool = False
    supports_alpha: bool = False
    status: str = "ok"  # ok | codec_unavailable | degraded
    detail: str | None = None


def _probe_pillow_format(pil_format: str, size=(8, 8)) -> tuple[bool, bool]:
    """Encode then decode a tiny image to prove round-trip capability."""
    can_encode = False
    can_decode = False
    try:
        img = Image.new("RGB", size, (12, 34, 56))
        buf = io.BytesIO()
        img.save(buf, format=pil_format)
        can_encode = True
        buf.seek(0)
        reopened = Image.open(buf)
        reopened.load()
        can_decode = True
    except Exception as exc:
        logger.debug("Codec probe failed for %s: %s", pil_format, exc)
    return can_decode, can_encode


def _probe_svg() -> tuple[bool, bool]:
    """Probe the native-wheel resvg renderer, then the Cairo fallback."""
    fixture = '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"></svg>'
    try:
        import resvg_py

        png = resvg_py.svg_to_bytes(svg_string=fixture)
        return bool(png), False
    except Exception:
        pass
    try:
        import cairosvg  # noqa: F401
    except Exception:
        return False, False
    try:
        import cairosvg

        png = cairosvg.svg2png(
            bytestring=fixture.encode("utf-8")
        )
        return bool(png), False
    except Exception:
        return False, False


def _detect() -> dict[str, CodecCapability]:
    caps: dict[str, CodecCapability] = {}

    baseline = {
        "png": ("PNG", True, True),
        "jpeg": ("JPEG", False, False),
        "webp": ("WEBP", True, True),
        "gif": ("GIF", True, False),
        "tiff": ("TIFF", True, False),
        "bmp": ("BMP", False, False),
    }
    for fmt, (pil_fmt, frames, alpha) in baseline.items():
        can_dec, can_enc = _probe_pillow_format(pil_fmt)
        caps[fmt] = CodecCapability(
            format=fmt,
            can_decode=can_dec,
            can_encode=can_enc,
            supports_frames=frames,
            supports_alpha=alpha,
            status="ok" if can_dec else "codec_unavailable",
        )

    # APNG is decoded via PNG plugin; treat as frames-capable if PNG works.
    caps["apng"] = CodecCapability(
        "apng", caps["png"].can_decode, False, supports_frames=True, supports_alpha=True,
        status=caps["png"].status,
    )

    # HEIF/HEIC.
    if _HEIF_IMPORTED:
        can_dec, can_enc = _probe_pillow_format("HEIF")
        caps["heif"] = CodecCapability(
            "heif", can_dec, can_enc, supports_frames=True, supports_alpha=True,
            status="ok" if can_dec else "codec_unavailable",
        )
    else:
        caps["heif"] = CodecCapability("heif", False, False, status="codec_unavailable",
                                       detail="pillow-heif chưa cài")

    # MPO (multi-picture JPEG) — decode via Pillow's MPO plugin.
    caps["mpo"] = CodecCapability(
        "mpo", caps["jpeg"].can_decode, False, supports_frames=True,
        status=caps["jpeg"].status,
    )

    # AVIF.
    if _AVIF_IMPORTED:
        can_dec, can_enc = _probe_pillow_format("AVIF")
        caps["avif"] = CodecCapability(
            "avif", can_dec, can_enc, supports_frames=True, supports_alpha=True,
            status="ok" if can_dec else "codec_unavailable",
        )
    else:
        caps["avif"] = CodecCapability("avif", False, False, status="codec_unavailable",
                                       detail="pillow-avif-plugin chưa cài")

    # SVG.
    svg_dec, _ = _probe_svg()
    caps["svg"] = CodecCapability(
        "svg", svg_dec, False, status="ok" if svg_dec else "codec_unavailable",
        detail=None if svg_dec else "resvg-py/CairoSVG chưa khả dụng",
    )

    return caps


_CAPABILITIES: dict[str, CodecCapability] | None = None


def get_capabilities(*, refresh: bool = False) -> dict[str, CodecCapability]:
    """Return the detected codec capability map (cached)."""
    global _CAPABILITIES
    if _CAPABILITIES is None or refresh:
        _CAPABILITIES = _detect()
    return _CAPABILITIES


def capability_for(fmt: str) -> CodecCapability:
    """Capability for a specific format, or an unavailable placeholder."""
    caps = get_capabilities()
    return caps.get(
        fmt,
        CodecCapability(fmt, False, False, status="unsupported_image_format"),
    )


def is_full_capability_ready() -> bool:
    """True only if every mandatory baseline codec passes its probe (task 5.2a)."""
    caps = get_capabilities()
    return all(caps.get(fmt) and caps[fmt].can_decode for fmt in MANDATORY_FORMATS)


def missing_mandatory() -> list[str]:
    """List mandatory formats whose codec is unavailable."""
    caps = get_capabilities()
    return [fmt for fmt in MANDATORY_FORMATS if not (caps.get(fmt) and caps[fmt].can_decode)]


def capability_report() -> dict:
    """A JSON-safe report for health checks / observability (task 5.2a)."""
    caps = get_capabilities()
    return {
        "full_capability_ready": is_full_capability_ready(),
        "missing_mandatory": missing_mandatory(),
        "codecs": {
            fmt: {
                "can_decode": cap.can_decode,
                "can_encode": cap.can_encode,
                "supports_frames": cap.supports_frames,
                "status": cap.status,
                "detail": cap.detail,
            }
            for fmt, cap in sorted(caps.items())
        },
    }


__all__ = [
    "MANDATORY_FORMATS",
    "CodecCapability",
    "capability_for",
    "capability_report",
    "get_capabilities",
    "is_full_capability_ready",
    "missing_mandatory",
]
