"""Filesystem roots owned exclusively by Automation Hub."""

from __future__ import annotations

from pathlib import Path

from .config import get_config


def root_dir() -> Path:
    path = get_config().data_root
    path.mkdir(parents=True, exist_ok=True)
    return path


def assets_dir() -> Path:
    path = root_dir() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_dir() -> Path:
    path = root_dir() / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sidecar_artifacts_dir() -> Path:
    path = root_dir() / "playwright-artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def roxy_sources_dir() -> Path:
    path = root_dir() / "roxybrowserlabs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_within_root(path: Path, allowed_root: Path | None = None) -> Path:
    resolved = path.expanduser().resolve()
    root = (allowed_root or root_dir()).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Đường dẫn nằm ngoài vùng dữ liệu Automation Hub.") from exc
    return resolved
