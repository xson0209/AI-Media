"""Codec registry + image pipeline tests (tasks 5.x, 12.4, 12.5)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend.services.comic_series_analysis import codec_registry as cr
from backend.services.comic_series_analysis import image_pipeline as ip
from backend.services.comic_series_analysis import svg_sanitizer as svg
from backend.services.comic_series_analysis.contracts import ComicAnalysisError


def _encode(fmt: str, size=(16, 16), color=(10, 120, 200)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# --- Codec registry -------------------------------------------------------

def test_baseline_codecs_available():
    caps = cr.get_capabilities(refresh=True)
    for fmt in ("png", "jpeg", "webp", "gif", "tiff", "bmp", "heif", "avif"):
        assert caps[fmt].can_decode, f"{fmt} should decode"


def test_capability_report_shape():
    report = cr.capability_report()
    assert "full_capability_ready" in report
    assert "missing_mandatory" in report
    assert set(report["codecs"]) >= set(cr.MANDATORY_FORMATS)


def test_svg_codec_uses_packaged_renderer():
    capability = cr.get_capabilities(refresh=True)["svg"]
    assert capability.can_decode is True
    png = svg.rasterize_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="gold"/></svg>',
        max_edge=32,
    )
    assert ip.validate_image(png).detected_format == "png"


# --- Image validation across the format matrix ----------------------------

@pytest.mark.parametrize("fmt,detected", [
    ("PNG", "png"),
    ("JPEG", "jpeg"),
    ("WEBP", "webp"),
    ("GIF", "gif"),
    ("BMP", "bmp"),
    ("TIFF", "tiff"),
    ("HEIF", "heif"),
    ("AVIF", "avif"),
])
def test_validate_image_matrix(fmt, detected):
    data = _encode(fmt)
    v = ip.validate_image(data)
    assert v.detected_format == detected
    assert v.codec_status == "ok"
    assert v.error_code is None
    assert v.width == 16 and v.height == 16
    assert v.decoded_pixel_hash is not None


def test_validate_corrupt_file():
    v = ip.validate_image(b"\x89PNG\r\n\x1a\n" + b"garbage")
    assert v.error_code in {"COMIC_IMAGE_CORRUPT", "COMIC_DECOMPRESSION_BOMB"}


def test_validate_non_image():
    v = ip.validate_image(b"just some text, not an image")
    assert v.codec_status == "unsupported_image_format"
    assert v.error_code == "COMIC_UNSUPPORTED_IMAGE_FORMAT"


def test_decompression_bomb_guard(monkeypatch):
    from backend.services.comic_series_analysis.config import ImagePolicy
    tiny_policy = ImagePolicy(max_pixels=10)  # 16x16 exceeds this
    v = ip.validate_image(_encode("PNG"), policy=tiny_policy)
    assert v.error_code == "COMIC_DECOMPRESSION_BOMB"


def test_checksum_stable_and_original_preserved(tmp_path):
    data = _encode("PNG")
    checksum = ip.compute_checksum(data)
    path = ip.save_original(data, tmp_path, checksum, "png")
    assert path.read_bytes() == data  # byte-for-byte
    # Saving again is a no-op (dedup), content unchanged.
    path2 = ip.save_original(data, tmp_path, checksum, "png")
    assert path == path2
    assert path.read_bytes() == data


def test_make_derivatives_and_tiling(tmp_path):
    # A tall image to trigger tiling.
    img = Image.new("RGB", (400, 9000), (30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    checksum = ip.compute_checksum(data)
    result = ip.make_derivatives(
        data, checksum,
        analysis_dir=tmp_path / "analysis",
        preview_dir=tmp_path / "preview",
        tiles_dir=tmp_path / "tiles",
    )
    assert result.analysis_path and result.preview_path
    assert len(result.tiles) > 1
    # Tiles have increasing y coordinates and overlap.
    ys = [t.y for t in result.tiles]
    assert ys == sorted(ys)
    assert result.transform_version == ip.TRANSFORM_VERSION


def test_export_image_png_webp():
    data = _encode("PNG")
    png = ip.export_image(data, "png")
    assert ip.validate_image(png).detected_format == "png"
    webp = ip.export_image(data, "webp")
    assert ip.validate_image(webp).detected_format == "webp"


# --- SVG sanitization -----------------------------------------------------

def test_sanitize_svg_strips_script_and_handlers():
    dirty = (
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        b'<script>evil()</script>'
        b'<rect width="10" height="10" onclick="x()"/>'
        b'<image href="http://evil.com/x.png"/>'
        b'</svg>'
    )
    cleaned = svg.sanitize_svg(dirty)
    text = cleaned.decode("utf-8", "ignore").lower()
    assert "script" not in text
    assert "onload" not in text
    assert "onclick" not in text
    assert "evil.com" not in text


def test_sanitize_svg_blocks_xxe():
    xxe = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>'
    )
    # defusedxml should refuse entity expansion.
    with pytest.raises(ComicAnalysisError):
        svg.sanitize_svg(xxe)
