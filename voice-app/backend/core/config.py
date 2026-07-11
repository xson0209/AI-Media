"""Runtime configuration for the backend process.

This module is the single source for local ports, CORS origins, storage
directories, and model/cache locations.  ``backend.config`` re-exports the
path helpers for compatibility with older imports.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 17493
DEFAULT_FRONTEND_HOST = "localhost"
DEFAULT_FRONTEND_PORT = 5173

ENV_BACKEND_HOST = "VOICEBOX_BACKEND_HOST"
ENV_BACKEND_PORT = "VOICEBOX_BACKEND_PORT"
ENV_LEGACY_BACKEND_PORT = "VOICEBOX_PORT"
ENV_FRONTEND_HOST = "VOICEBOX_FRONTEND_HOST"
ENV_FRONTEND_PORT = "VOICEBOX_FRONTEND_PORT"
ENV_PUBLIC_BACKEND_URL = "VOICEBOX_PUBLIC_BACKEND_URL"
ENV_CORS_ORIGINS = "VOICEBOX_CORS_ORIGINS"
ENV_DATA_DIR = "VOICEBOX_DATA_DIR"
ENV_MODELS_DIR = "VOICEBOX_MODELS_DIR"
ENV_CACHE_DIR = "VOICEBOX_CACHE_DIR"


def _parse_int(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        logger.warning("Invalid integer config value %r; using %s", value, default)
        return default
    if parsed <= 0 or parsed > 65535:
        logger.warning("Invalid port config value %r; using %s", value, default)
        return default
    return parsed


def _first_env(environ: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = environ.get(name)
        if value:
            return value
    return None


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _resolve_path(value: str | None, default: Path) -> Path:
    return Path(value).expanduser().resolve() if value else default.resolve()


def _feature_flags(environ: Mapping[str, str]) -> Mapping[str, str]:
    prefix = "VOICEBOX_FEATURE_"
    flags = {key.removeprefix(prefix).lower(): value for key, value in environ.items() if key.startswith(prefix)}
    return MappingProxyType(flags)


@dataclass(frozen=True)
class RuntimeConfig:
    backend_host: str
    backend_port: int
    frontend_host: str
    frontend_port: int
    public_backend_url: str | None
    cors_origins: tuple[str, ...]
    data_dir: Path
    models_dir: Path
    cache_dir: Path
    feature_flags: Mapping[str, str]

    @property
    def backend_url(self) -> str:
        if self.public_backend_url:
            return self.public_backend_url.rstrip("/")
        host = "127.0.0.1" if self.backend_host in {"0.0.0.0", "::"} else self.backend_host
        return f"http://{host}:{self.backend_port}"

    @property
    def frontend_dev_origins(self) -> tuple[str, str]:
        return (
            f"http://localhost:{self.frontend_port}",
            f"http://127.0.0.1:{self.frontend_port}",
        )

    @property
    def backend_local_origins(self) -> tuple[str, str]:
        return (
            f"http://localhost:{self.backend_port}",
            f"http://127.0.0.1:{self.backend_port}",
        )


_data_dir = _resolve_path(os.environ.get(ENV_DATA_DIR), Path("data"))


def build_cors_origins(
    *,
    backend_port: int = DEFAULT_BACKEND_PORT,
    frontend_port: int = DEFAULT_FRONTEND_PORT,
    extra_origins: str | None = None,
) -> tuple[str, ...]:
    """Build the local-first CORS allowlist."""
    origins = [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
        f"http://localhost:{backend_port}",
        f"http://127.0.0.1:{backend_port}",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
    ]
    origins.extend(_split_csv(extra_origins))
    return tuple(dict.fromkeys(origins))


def load_runtime_config(environ: Mapping[str, str] | None = None) -> RuntimeConfig:
    """Load runtime configuration from environment variables and current state."""
    env = environ or os.environ
    backend_port = _parse_int(
        _first_env(env, ENV_BACKEND_PORT, ENV_LEGACY_BACKEND_PORT),
        DEFAULT_BACKEND_PORT,
    )
    frontend_port = _parse_int(env.get(ENV_FRONTEND_PORT), DEFAULT_FRONTEND_PORT)
    data_dir = _resolve_path(env.get(ENV_DATA_DIR), _data_dir)
    models_dir = _resolve_path(env.get(ENV_MODELS_DIR), data_dir / "models")
    cache_dir = _resolve_path(env.get(ENV_CACHE_DIR), data_dir / "cache")
    return RuntimeConfig(
        backend_host=env.get(ENV_BACKEND_HOST, DEFAULT_BACKEND_HOST),
        backend_port=backend_port,
        frontend_host=env.get(ENV_FRONTEND_HOST, DEFAULT_FRONTEND_HOST),
        frontend_port=frontend_port,
        public_backend_url=env.get(ENV_PUBLIC_BACKEND_URL) or None,
        cors_origins=build_cors_origins(
            backend_port=backend_port,
            frontend_port=frontend_port,
            extra_origins=env.get(ENV_CORS_ORIGINS),
        ),
        data_dir=data_dir,
        models_dir=models_dir,
        cache_dir=cache_dir,
        feature_flags=_feature_flags(env),
    )


def get_runtime_config() -> RuntimeConfig:
    return load_runtime_config()


def configure_model_cache() -> None:
    """Apply the configured HuggingFace model cache early in process startup."""
    models_dir = os.environ.get(ENV_MODELS_DIR)
    if not models_dir:
        return
    os.environ["HF_HUB_CACHE"] = str(Path(models_dir).expanduser().resolve())
    logger.info("Model download path set to: %s", os.environ["HF_HUB_CACHE"])


configure_model_cache()


def _path_relative_to_any_data_dir(path: Path) -> Path | None:
    parts = path.parts
    for idx, part in enumerate(parts):
        if part != "data":
            continue

        tail = parts[idx + 1 :]
        if tail:
            return Path(*tail)
        return Path()

    return None


def set_data_dir(path: str | Path) -> None:
    """Set the data directory path for this process."""
    global _data_dir
    _data_dir = Path(path).expanduser().resolve()
    _data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Data directory set to: %s", _data_dir)


def get_data_dir() -> Path:
    """Get the configured data directory."""
    return _data_dir


def to_storage_path(path: str | Path) -> str:
    """Convert a filesystem path to a DB-safe path relative to the data dir."""
    resolved_path = Path(path).resolve()

    relative_to_any_data_dir = _path_relative_to_any_data_dir(resolved_path)
    if relative_to_any_data_dir is not None:
        return str(relative_to_any_data_dir)

    try:
        return str(resolved_path.relative_to(_data_dir))
    except ValueError:
        return str(resolved_path)


def resolve_storage_path(path: str | Path | None) -> Path | None:
    """Resolve a DB-stored path against the configured data dir."""
    if path is None:
        return None

    stored_path = Path(path)
    if stored_path.is_absolute():
        rebased_path = _path_relative_to_any_data_dir(stored_path)
        if rebased_path is not None:
            candidate = (_data_dir / rebased_path).resolve()
            if candidate.exists() or not stored_path.exists():
                return candidate

        return stored_path

    if stored_path.parts and stored_path.parts[0] == "data":
        stored_path = Path(*stored_path.parts[1:]) if len(stored_path.parts) > 1 else Path()

    return (_data_dir / stored_path).resolve()


def get_db_path() -> Path:
    """Get database file path."""
    return _data_dir / "voicebox.db"


def get_profiles_dir() -> Path:
    """Get profiles directory path."""
    path = _data_dir / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_generations_dir() -> Path:
    """Get generations directory path."""
    path = _data_dir / "generations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_captures_dir() -> Path:
    """Get captures directory path."""
    path = _data_dir / "captures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    """Get cache directory path."""
    path = get_runtime_config().cache_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    """Get models directory path."""
    path = get_runtime_config().models_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "DEFAULT_BACKEND_HOST",
    "DEFAULT_BACKEND_PORT",
    "DEFAULT_FRONTEND_HOST",
    "DEFAULT_FRONTEND_PORT",
    "ENV_BACKEND_HOST",
    "ENV_BACKEND_PORT",
    "ENV_CACHE_DIR",
    "ENV_CORS_ORIGINS",
    "ENV_DATA_DIR",
    "ENV_FRONTEND_HOST",
    "ENV_FRONTEND_PORT",
    "ENV_LEGACY_BACKEND_PORT",
    "ENV_MODELS_DIR",
    "ENV_PUBLIC_BACKEND_URL",
    "RuntimeConfig",
    "build_cors_origins",
    "configure_model_cache",
    "get_cache_dir",
    "get_captures_dir",
    "get_data_dir",
    "get_db_path",
    "get_generations_dir",
    "get_models_dir",
    "get_profiles_dir",
    "get_runtime_config",
    "load_runtime_config",
    "resolve_storage_path",
    "set_data_dir",
    "to_storage_path",
]
