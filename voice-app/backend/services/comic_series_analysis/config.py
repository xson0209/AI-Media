"""Typed configuration and storage layout for Comic Series Analysis.

All operational limits (timeouts, redirect caps, byte/pixel budgets,
image/page counts, concurrency, scroll rounds) live here as a single typed
config so they can be tuned without hunting through the pipeline, and so
tests can assert against explicit policy rather than magic numbers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ... import config as _core_config

# Feature flag (task 11.8): default ON; set VOICEBOX_FEATURE_COMIC_ANALYSIS=0
# to disable the route, menu and runner while keeping already-handed-off
# Series/Episodes fully usable.
_FEATURE_FLAG_KEY = "comic_analysis"


def is_feature_enabled() -> bool:
    """Whether the Comic Series Analysis feature is enabled."""
    flags = _core_config.get_runtime_config().feature_flags
    raw = flags.get(_FEATURE_FLAG_KEY)
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}


@dataclass(frozen=True)
class NetworkPolicy:
    """SSRF and network resource policy (tasks 1.6, 3.4, 3.10, 3.11)."""

    # Only these schemes are ever fetched.
    allowed_schemes: tuple[str, ...] = ("http", "https")
    # Ports allowed for outbound fetches. Empty tuple means "default only".
    allowed_ports: tuple[int, ...] = (80, 443, 8080, 8443)
    # Per-phase timeouts in seconds.
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    total_timeout_seconds: float = 120.0
    # Redirect handling.
    max_redirects: int = 5
    # Byte budgets (post-decompression).
    max_html_bytes: int = 8 * 1024 * 1024
    max_image_bytes: int = 40 * 1024 * 1024
    max_total_bytes: int = 512 * 1024 * 1024
    # Data-URI images inlined in HTML.
    max_data_uri_bytes: int = 8 * 1024 * 1024
    # Never trust ambient proxy/credential env for outbound fetches.
    trust_env: bool = False


@dataclass(frozen=True)
class IngestPolicy:
    """Per-job ingestion budgets (tasks 1.6, 3.10, 4.8)."""

    max_pages: int = 50
    max_images: int = 400
    max_upload_images: int = 400
    retry_limit: int = 3
    fetch_concurrency: int = 4
    # Browser fallback scroll limits.
    browser_max_scroll_rounds: int = 30
    browser_max_scroll_height_px: int = 200_000
    browser_max_scroll_seconds: float = 60.0
    browser_max_new_assets: int = 400
    # Coverage threshold below which static-first will consider browser fallback.
    min_text_chars_for_static: int = 400
    min_images_for_static: int = 1
    # Whether to honor configured robots/policy disallow rules.
    respect_robots: bool = True


@dataclass(frozen=True)
class ImagePolicy:
    """Image decode / normalization / tiling limits (tasks 1.6, 5.4, 5.7)."""

    max_pixels: int = 60_000_000  # decompression-bomb guard for a single decode
    max_frames: int = 40  # animated/multi-page frame extraction cap
    max_pages: int = 40
    # Webtoon tiling.
    tile_height_px: int = 2000
    tile_overlap_px: int = 200
    tile_trigger_height_px: int = 4000
    tile_trigger_ratio: float = 3.0  # height/width ratio that triggers tiling
    preview_max_edge_px: int = 1600
    analysis_max_edge_px: int = 4096


@dataclass(frozen=True)
class VisionPolicy:
    """AI vision/OCR batching limits (tasks 1.6, 6.10)."""

    workflow_type: str = "comic_series_analysis"
    max_attachments_per_request: int = 4
    max_batches_per_job: int = 200
    analysis_char_budget: int = 24_000


@dataclass(frozen=True)
class ComicAnalysisConfig:
    """Aggregate typed configuration for the feature."""

    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    ingest: IngestPolicy = field(default_factory=IngestPolicy)
    image: ImagePolicy = field(default_factory=ImagePolicy)
    vision: VisionPolicy = field(default_factory=VisionPolicy)
    # source_input compatibility projection limit (design §15).
    source_input_projection_limit: int = 50_000


_CONFIG = ComicAnalysisConfig()


def get_config() -> ComicAnalysisConfig:
    """Return the active typed configuration."""
    return _CONFIG


# --------------------------------------------------------------------------
# Storage layout (task 11.1) — a dedicated root, never mixed with video.
# --------------------------------------------------------------------------

_STORAGE_SUBDIRS = (
    "originals",
    "analysis",
    "previews",
    "tiles",
    "exports",
    "snapshots",
    "staging",
)


def get_storage_root() -> Path:
    """Root directory for all Comic Analysis artifacts."""
    path = _core_config.get_data_dir() / "comic_series_analysis"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_storage_subdir(name: str) -> Path:
    """Return (and create) a named subdirectory under the storage root."""
    if name not in _STORAGE_SUBDIRS:
        raise ValueError(f"Unknown comic storage subdir: {name!r}")
    path = get_storage_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "ComicAnalysisConfig",
    "IngestPolicy",
    "ImagePolicy",
    "NetworkPolicy",
    "VisionPolicy",
    "get_config",
    "get_storage_root",
    "get_storage_subdir",
    "is_feature_enabled",
]
