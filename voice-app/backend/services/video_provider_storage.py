"""Local storage helpers for AI Video provider browser automation."""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import config
from . import video_storage

PROVIDER_STORAGE_DIR = "ai-video"
PROVIDER_PROFILE_DIR = "browser-profiles"
PROVIDER_DOWNLOAD_DIR = "provider-downloads"

def get_provider_root() -> Path:
    path = config.get_data_dir() / PROVIDER_STORAGE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_browser_profiles_root() -> Path:
    path = get_provider_root() / PROVIDER_PROFILE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_provider_downloads_root() -> Path:
    path = get_provider_root() / PROVIDER_DOWNLOAD_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path

def provider_profile_slug(provider: str = "veo") -> str:
    normalized = video_storage.sanitize_download_filename(provider, fallback="provider", max_length=40)
    if normalized.lower() in {"veo", "veo3", "flow", "veo3_flow"}:
        return "veo-chrome"
    return f"{normalized.lower()}-chrome"

def get_chrome_profile_dir(provider: str = "veo") -> Path:
    path = get_browser_profiles_root() / provider_profile_slug(provider)
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_job_download_dir(project_id: str, job_id: str) -> Path:
    path = get_provider_downloads_root() / project_id / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_item_download_dir(
    *,
    project_id: str,
    job_id: str,
    shot_order: int,
    shot_id: str,
    item_id: str,
) -> Path:
    safe_shot_id = video_storage.sanitize_download_filename(shot_id, fallback="shot", max_length=48)
    safe_item_id = video_storage.sanitize_download_filename(item_id, fallback="item", max_length=48)
    path = get_job_download_dir(project_id, job_id) / f"{shot_order:03d}-{safe_shot_id}-{safe_item_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path

def to_storage_path(path: str | Path) -> str:
    return config.to_storage_path(path)

def resolve_storage_path(path: str | Path | None) -> Path | None:
    return config.resolve_storage_path(path)

def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True

def cleanup_job_downloads(download_dir: str | Path | None) -> bool:
    if not download_dir:
        return False
    path = resolve_storage_path(download_dir)
    root = get_provider_downloads_root()
    if path is None or not path.exists() or not _is_under(path, root):
        return False
    shutil.rmtree(path)
    return True

def cleanup_project_downloads(project_id: str) -> bool:
    path = get_provider_downloads_root() / project_id
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True
