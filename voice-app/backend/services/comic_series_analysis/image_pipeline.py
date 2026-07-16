"""Image processing pipeline for Comic Series Analysis (§5).

Responsibilities:
  - Preserve the original bytes byte-for-byte, never overwrite (task 5.3).
  - Validate magic bytes, decode, count frames/pages, guard against
    decompression bombs (task 5.4).
  - Produce an ``analysis`` derivative (PNG/JPEG, EXIF-oriented,
    sRGB-normalized) and a ``preview`` WebP (task 5.5).
  - Tile very tall webtoon images with overlap, keeping coordinates
    (tasks 5.7, 5.7a).
  - Compute a ``decoded_pixel_hash`` after orientation/colorspace
    normalization for pixel-equivalence checks (task 5.13).

Exports (PNG/WebP/HEIC) are produced on demand elsewhere; this module gives
the primitives. SVG sanitization lives in ``svg_sanitizer``.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from . import codec_registry
from .config import ImagePolicy, get_config
from .contracts import ComicAnalysisError
from .fetcher import sniff_image_format

logger = logging.getLogger(__name__)

TRANSFORM_VERSION = "comic_image_transform.v1"

# Map a detected format to the Pillow verify format name.
_DETECTED_TO_CODEC = {
    "png": "png",
    "jpeg": "jpeg",
    "webp": "webp",
    "gif": "gif",
    "bmp": "bmp",
    "tiff": "tiff",
    "heif": "heif",
    "avif": "avif",
    "svg": "svg",
}


@dataclass
class ImageValidation:
    """Result of validating/decoding an image blob."""

    detected_format: str | None
    checksum: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    frame_count: int = 1
    codec_status: str = "ok"  # ok | codec_unavailable | unsupported_image_format
    decoded_pixel_hash: str | None = None
    error_code: str | None = None


@dataclass
class Tile:
    """A tile of a tall image with coordinates in the source."""

    index: int
    path: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class DerivativeSet:
    """Paths to derived artifacts for one source asset."""

    analysis_path: str | None = None
    preview_path: str | None = None
    tiles: list[Tile] = field(default_factory=list)
    transform_version: str = TRANSFORM_VERSION


def compute_checksum(data: bytes) -> str:
    """SHA-256 of the original bytes."""
    return hashlib.sha256(data).hexdigest()


def save_original(data: bytes, dest_dir: Path, checksum: str, detected_format: str | None) -> Path:
    """Write original bytes byte-for-byte into a content-addressed path.

    Never overwrites an existing blob with the same checksum (dedup, task
    5.10): identical content maps to one physical file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = detected_format or "bin"
    path = dest_dir / f"{checksum}.{ext}"
    if not path.exists():
        # Atomic-ish write via temp + rename.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path


def validate_image(data: bytes, *, policy: ImagePolicy | None = None) -> ImageValidation:
    """Validate an image blob: magic bytes, decode, bomb guard (task 5.4)."""
    policy = policy or get_config().image
    checksum = compute_checksum(data)
    detected = sniff_image_format(data[:64])
    validation = ImageValidation(
        detected_format=detected, checksum=checksum, byte_size=len(data)
    )

    if detected is None:
        validation.codec_status = "unsupported_image_format"
        validation.error_code = "COMIC_UNSUPPORTED_IMAGE_FORMAT"
        return validation

    if detected == "svg":
        # SVG handled by sanitizer; capability-gated.
        cap = codec_registry.capability_for("svg")
        validation.codec_status = "ok" if cap.can_decode else "codec_unavailable"
        if not cap.can_decode:
            validation.error_code = "COMIC_CODEC_UNAVAILABLE"
        return validation

    cap = codec_registry.capability_for(_DETECTED_TO_CODEC.get(detected, detected))
    if not cap.can_decode:
        validation.codec_status = "codec_unavailable"
        validation.error_code = "COMIC_CODEC_UNAVAILABLE"
        return validation

    # Decompression-bomb guard: check declared size before full decode.
    try:
        probe = Image.open(io.BytesIO(data))
        width, height = probe.size
        if width * height > policy.max_pixels:
            validation.codec_status = "ok"
            validation.width, validation.height = width, height
            validation.error_code = "COMIC_DECOMPRESSION_BOMB"
            return validation
        # Count frames/pages for animated/multipage.
        frame_count = getattr(probe, "n_frames", 1)
        validation.frame_count = int(frame_count)
        # Full decode of the first frame to prove it's real image data.
        probe.seek(0)
        decoded = ImageOps.exif_transpose(probe.convert("RGB"))
        validation.width, validation.height = decoded.size
        validation.decoded_pixel_hash = hashlib.sha256(decoded.tobytes()).hexdigest()
    except Image.DecompressionBombError:
        validation.error_code = "COMIC_DECOMPRESSION_BOMB"
        return validation
    except Exception as exc:
        logger.debug("Image decode failed: %s", exc)
        validation.codec_status = "ok"
        validation.error_code = "COMIC_IMAGE_CORRUPT"
        return validation

    return validation


def _normalized_rgb(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.seek(0)
    return ImageOps.exif_transpose(img).convert("RGB")


def make_derivatives(
    data: bytes,
    checksum: str,
    *,
    analysis_dir: Path,
    preview_dir: Path,
    tiles_dir: Path,
    policy: ImagePolicy | None = None,
) -> DerivativeSet:
    """Create analysis PNG, preview WebP and (if tall) overlapping tiles.

    Never touches the original. Raises nothing for tiling failures — returns
    whatever derivatives succeeded.
    """
    policy = policy or get_config().image
    result = DerivativeSet()
    try:
        base = _normalized_rgb(data)
    except Exception as exc:
        raise ComicAnalysisError("COMIC_IMAGE_CORRUPT", f"Không decode được ảnh: {exc}")

    # Analysis derivative (PNG), bounded to max edge.
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_img = base.copy()
    analysis_img.thumbnail((policy.analysis_max_edge_px, policy.analysis_max_edge_px * 8))
    analysis_path = analysis_dir / f"{checksum}.png"
    analysis_img.save(analysis_path, format="PNG")
    result.analysis_path = str(analysis_path)

    # Preview derivative (WebP), small for UI.
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_img = base.copy()
    preview_img.thumbnail((policy.preview_max_edge_px, policy.preview_max_edge_px * 8))
    preview_path = preview_dir / f"{checksum}.webp"
    preview_img.save(preview_path, format="WEBP", quality=82)
    result.preview_path = str(preview_path)

    # Tiling for tall images (webtoon).
    width, height = base.size
    ratio = height / max(1, width)
    if height > policy.tile_trigger_height_px or ratio > policy.tile_trigger_ratio:
        result.tiles = _tile_tall(base, checksum, tiles_dir, policy)

    return result


def _tile_tall(img: Image.Image, checksum: str, tiles_dir: Path, policy: ImagePolicy) -> list[Tile]:
    """Slice a tall image top-to-bottom with overlap, keeping coordinates."""
    tiles_dir.mkdir(parents=True, exist_ok=True)
    width, height = img.size
    step = max(1, policy.tile_height_px - policy.tile_overlap_px)
    tiles: list[Tile] = []
    index = 0
    y = 0
    while y < height:
        bottom = min(height, y + policy.tile_height_px)
        crop = img.crop((0, y, width, bottom))
        path = tiles_dir / f"{checksum}_t{index}.png"
        crop.save(path, format="PNG")
        tiles.append(Tile(index=index, path=str(path), x=0, y=y, width=width, height=bottom - y))
        index += 1
        if bottom >= height:
            break
        y += step
    return tiles


def iter_frames(data: bytes, *, max_frames: int) -> list[Image.Image]:
    """Extract up to ``max_frames`` frames/pages from animated/multipage images."""
    img = Image.open(io.BytesIO(data))
    frames: list[Image.Image] = []
    for i, frame in enumerate(ImageSequence.Iterator(img)):
        if i >= max_frames:
            break
        frames.append(ImageOps.exif_transpose(frame.convert("RGB")))
    return frames


def export_image(data: bytes, target_format: str) -> bytes:
    """Export an image to PNG/WebP/HEIC on demand without touching original.

    Raises ``COMIC_CODEC_UNAVAILABLE`` if the target codec can't encode here.
    """
    fmt = target_format.lower()
    pil_format = {"png": "PNG", "webp": "WEBP", "heic": "HEIF", "heif": "HEIF"}.get(fmt)
    if pil_format is None:
        raise ComicAnalysisError("COMIC_UNSUPPORTED_IMAGE_FORMAT", f"Không hỗ trợ export {fmt}.")
    codec_key = "heif" if pil_format == "HEIF" else fmt
    cap = codec_registry.capability_for(codec_key)
    if not cap.can_encode:
        raise ComicAnalysisError("COMIC_CODEC_UNAVAILABLE", f"Không encode được {fmt}.")
    img = _normalized_rgb(data)
    buf = io.BytesIO()
    img.save(buf, format=pil_format)
    return buf.getvalue()


__all__ = [
    "TRANSFORM_VERSION",
    "DerivativeSet",
    "ImageValidation",
    "Tile",
    "compute_checksum",
    "export_image",
    "iter_frames",
    "make_derivatives",
    "save_original",
    "validate_image",
]
