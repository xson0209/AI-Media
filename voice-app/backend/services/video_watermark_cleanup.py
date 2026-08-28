"""Isolated visible AI watermark cleanup and derivative caching for video clips."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import video_storage

WATERMARK_ROOT_ENV = "VOICEBOX_WATERMARK_ROOT"
WATERMARK_PYTHON_ENV = "VOICEBOX_WATERMARK_PYTHON"
WATERMARK_WORKER_SCRIPT_ENV = "VOICEBOX_WATERMARK_WORKER_SCRIPT"
WATERMARK_TIMEOUT_ENV = "VOICEBOX_WATERMARK_TIMEOUT_SECONDS"
WORKER_PROTOCOL_VERSION = "voicebox-watermark-worker-v1"
WATERMARK_CACHE_VERSION = "watermark-cache-v1"
DEFAULT_TIMEOUT_SECONDS = 1200
RUNTIME_CHECK_TIMEOUT_SECONDS = 30
_STDERR_LIMIT = 4000
_SUPPORTED_PROVIDERS = {"sora", "veo", "seedance", "dola", "hailuo", "kling"}
# Region-fill backends exposed to users, in stable probe order. `lama` is out of
# scope for Voicebox (~4.7 GB RAM).
SUPPORTED_CLEANUP_BACKENDS = ("cv2", "migan")


class VideoWatermarkCleanupError(ValueError):
    """Raised when requested watermark cleanup cannot complete safely."""

    def __init__(self, message: str, *, error_code: str = "VIDEO_RENDER_WATERMARK_FAILED"):
        super().__init__(message)
        self.error_code = error_code


MODEL_CACHE_CACHED = "cached"
MODEL_CACHE_NOT_CACHED = "not_cached"
MODEL_CACHE_UNKNOWN = "unknown"
_MODEL_CACHE_STATES = {MODEL_CACHE_CACHED, MODEL_CACHE_NOT_CACHED, MODEL_CACHE_UNKNOWN}
MIGAN_MODEL_DOWNLOAD_MB = 28


@dataclass(frozen=True)
class WatermarkRuntimeStatus:
    ready: bool
    package_root: Path | None
    python: str | None
    worker_script: Path | None
    revision: str | None = None
    package_version: str | None = None
    failure_reason: str | None = None
    error_code: str | None = None
    # Only set for model-backed backends (migan). None means "not applicable",
    # which is how cv2 always reports.
    model_cache: str | None = None


def _voicebox_root() -> Path:
    return Path(__file__).resolve().parents[2]


def configured_package_root() -> Path:
    configured = os.environ.get(WATERMARK_ROOT_ENV)
    if configured:
        return Path(configured).expanduser()
    return _voicebox_root().parent / "remove watermark"


def configured_worker_script() -> Path:
    configured = os.environ.get(WATERMARK_WORKER_SCRIPT_ENV)
    if configured:
        return Path(configured).expanduser()
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return bundle_root / "backend" / "workers" / "video_watermark_worker.py"
    return _voicebox_root() / "backend" / "workers" / "video_watermark_worker.py"


def _configured_python(package_root: Path) -> str | None:
    configured = os.environ.get(WATERMARK_PYTHON_ENV)
    candidates: list[str | None] = []
    if configured:
        configured_path = Path(configured).expanduser()
        candidates.append(str(configured_path))
        if configured_path.name == configured:
            candidates.append(shutil.which(configured))
    if os.name == "nt":
        candidates.append(str(package_root / ".venv" / "Scripts" / "python.exe"))
    else:
        candidates.append(str(package_root / ".venv" / "bin" / "python"))
    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)
    candidates.extend([shutil.which("python3"), shutil.which("python")])
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return str(path)
    return None


def _package_revision(package_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(package_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
        revision = result.stdout.strip()
        if result.returncode == 0 and revision:
            return revision
    except (OSError, subprocess.SubprocessError):
        pass
    pyproject = package_root / "pyproject.toml"
    if pyproject.exists():
        stat = pyproject.stat()
        return f"unversioned-{stat.st_size}-{stat.st_mtime_ns}"
    return "unknown"


def _worker_environment(
    *,
    package_root: Path,
    revision: str,
    ffmpeg: str | None,
    ffprobe: str | None,
) -> dict[str, str]:
    env = dict(os.environ)
    python_paths = [str(package_root / "src"), str(_voicebox_root())]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    tool_dirs: list[str] = []
    for tool in (ffmpeg, ffprobe):
        if not tool:
            continue
        parent = str(Path(tool).expanduser().resolve().parent)
        if parent not in tool_dirs:
            tool_dirs.append(parent)
    if env.get("PATH"):
        tool_dirs.append(env["PATH"])
    env["PATH"] = os.pathsep.join(tool_dirs)
    env["PYTHONIOENCODING"] = "utf-8"
    if ffmpeg:
        env["VOICEBOX_WATERMARK_FFMPEG"] = str(Path(ffmpeg).expanduser().resolve())
    if ffprobe:
        env["VOICEBOX_WATERMARK_FFPROBE"] = str(Path(ffprobe).expanduser().resolve())
    env["VOICEBOX_WATERMARK_REVISION"] = revision
    return env


def _parse_worker_payload(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise VideoWatermarkCleanupError(
        "Watermark worker không trả JSON hợp lệ.",
        error_code="VIDEO_RENDER_WATERMARK_PROTOCOL_INVALID",
    )


def _run_worker(
    *,
    python: str,
    worker_script: Path,
    package_root: Path,
    revision: str,
    ffmpeg: str | None,
    ffprobe: str | None,
    args: list[str] | None = None,
    request: dict[str, Any] | None = None,
    timeout: int,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    command = [python, str(worker_script), *(args or [])]
    env = _worker_environment(
        package_root=package_root,
        revision=revision,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request, ensure_ascii=False) if request is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(package_root),
            env=env,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoWatermarkCleanupError(
            "Watermark worker chạy quá thời gian cho phép.",
            error_code="VIDEO_RENDER_WATERMARK_TIMEOUT",
        ) from exc
    except OSError as exc:
        raise VideoWatermarkCleanupError(
            f"Không khởi động được watermark worker: {exc}",
            error_code="VIDEO_RENDER_WATERMARK_WORKER_START_FAILED",
        ) from exc
    return completed, _parse_worker_payload(completed.stdout)


def get_runtime_status(
    *,
    backend: str,
    ffmpeg: str | None,
    ffprobe: str | None,
) -> WatermarkRuntimeStatus:
    package_root = configured_package_root()
    worker_script = configured_worker_script()
    python = _configured_python(package_root)
    if not package_root.exists() or not (package_root / "src" / "remove_ai_watermarks").exists():
        return WatermarkRuntimeStatus(
            ready=False,
            package_root=package_root,
            python=python,
            worker_script=worker_script,
            failure_reason="Chưa tìm thấy source remove-ai-watermarks. Hãy cấu hình VOICEBOX_WATERMARK_ROOT.",
            error_code="VIDEO_RENDER_WATERMARK_ROOT_MISSING",
        )
    if python is None:
        return WatermarkRuntimeStatus(
            ready=False,
            package_root=package_root,
            python=None,
            worker_script=worker_script,
            failure_reason="Chưa tìm thấy Python cho watermark worker. Hãy chạy script setup hoặc cấu hình VOICEBOX_WATERMARK_PYTHON.",
            error_code="VIDEO_RENDER_WATERMARK_PYTHON_MISSING",
        )
    if not worker_script.exists():
        return WatermarkRuntimeStatus(
            ready=False,
            package_root=package_root,
            python=python,
            worker_script=worker_script,
            failure_reason="Không tìm thấy watermark worker script trong bản cài Voicebox.",
            error_code="VIDEO_RENDER_WATERMARK_SCRIPT_MISSING",
        )
    revision = _package_revision(package_root)
    try:
        completed, payload = _run_worker(
            python=python,
            worker_script=worker_script,
            package_root=package_root,
            revision=revision,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            args=["--check", "--backend", backend],
            timeout=RUNTIME_CHECK_TIMEOUT_SECONDS,
        )
    except VideoWatermarkCleanupError as exc:
        return WatermarkRuntimeStatus(
            ready=False,
            package_root=package_root,
            python=python,
            worker_script=worker_script,
            revision=revision,
            failure_reason=str(exc),
            error_code=exc.error_code,
        )
    ready = completed.returncode == 0 and payload.get("ready") is True and payload.get("ok") is True
    raw_model_cache = payload.get("model_cache")
    model_cache = str(raw_model_cache) if raw_model_cache in _MODEL_CACHE_STATES else None
    return WatermarkRuntimeStatus(
        ready=ready,
        package_root=package_root,
        python=python,
        worker_script=worker_script,
        revision=str(payload.get("revision") or revision),
        package_version=str(payload.get("package_version")) if payload.get("package_version") else None,
        failure_reason=None if ready else str(payload.get("message") or "Watermark worker chưa sẵn sàng."),
        error_code=None if ready else str(payload.get("error_code") or "VIDEO_RENDER_WATERMARK_WORKER_NOT_READY"),
        model_cache=model_cache,
    )


def _source_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def watermark_cache_key(
    *,
    input_path: Path,
    mark: str,
    backend: str,
    temporal_consistency: bool,
    runtime: WatermarkRuntimeStatus,
) -> str:
    payload = {
        "version": WATERMARK_CACHE_VERSION,
        "protocol": WORKER_PROTOCOL_VERSION,
        "source": _source_identity(input_path),
        "mark": mark,
        "backend": backend,
        "temporal_consistency": temporal_consistency,
        "package_root": str(runtime.package_root.resolve()) if runtime.package_root else None,
        "revision": runtime.revision,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_dir(project_id: str) -> Path:
    path = video_storage.get_project_subdir(project_id, "render_cache") / "watermark"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_cache_report(report_path: Path, output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists() or output_path.stat().st_size <= 0 or not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("ok") is True else None


def _timeout_seconds() -> int:
    raw = os.environ.get(WATERMARK_TIMEOUT_ENV)
    try:
        parsed = int(raw) if raw else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return max(60, min(parsed, 7200))


def mark_for_provider(provider: str | None) -> str:
    normalized = str(provider or "").strip().lower()
    return normalized if normalized in _SUPPORTED_PROVIDERS else "auto"


def _cached_mark_for_clip(*, project_id: str, shot_id: str, input_path: Path) -> str | None:
    """Read back the mark a previous cleanup of this same clip already observed.

    Every cache report carries the `visible_mark` the worker actually found, so a clip
    cleaned once already tells us which provider mark it holds. Reports are matched on
    the source filename first because that pins the exact file; `shot_id` is accepted as
    a weaker match for clips whose cache was written before the filename was recorded.
    """
    cache_root = video_storage.get_project_subdir(project_id, "render_cache") / "watermark"
    if not cache_root.exists():
        return None
    newest: tuple[int, str] | None = None
    for report_path in sorted(cache_root.glob("*.json")):
        if report_path.name.endswith(".tmp.json"):
            continue
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            mtime_ns = report_path.stat().st_mtime_ns
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            continue
        if payload.get("source_filename") != input_path.name and payload.get("shot_id") != shot_id:
            continue
        mark = str(payload.get("visible_mark") or "").strip().lower()
        if mark not in _SUPPORTED_PROVIDERS:
            continue
        if newest is None or mtime_ns > newest[0]:
            newest = (mtime_ns, mark)
    return newest[1] if newest else None


def resolve_clip_mark(
    *,
    project_id: str,
    shot_id: str,
    input_path: Path,
    provider: str | None,
) -> str:
    """Pick the narrowest mark to scan for, ordered by how much each source is trusted.

    `auto` makes the worker run every supported detector on every frame — measured at
    37,6 giây/clip against 8,7 giây/clip for a single known mark on the same clip. So the
    provider stored on the clip wins, then whatever a previous cleanup of the same clip
    recorded, and only a clip with neither falls back to the full scan.
    """
    mark = mark_for_provider(provider)
    if mark != "auto":
        return mark
    return _cached_mark_for_clip(project_id=project_id, shot_id=shot_id, input_path=input_path) or "auto"


def cleanup_clip_with_cache(
    *,
    project_id: str,
    shot_id: str,
    input_path: Path,
    provider: str | None,
    backend: str,
    runtime: WatermarkRuntimeStatus,
    ffmpeg: str | None,
    ffprobe: str | None,
    temporal_consistency: bool = True,
) -> tuple[Path, dict[str, Any]]:
    if not runtime.ready or runtime.package_root is None or runtime.python is None or runtime.worker_script is None:
        raise VideoWatermarkCleanupError(
            runtime.failure_reason or "Watermark worker chưa sẵn sàng.",
            error_code=runtime.error_code or "VIDEO_RENDER_WATERMARK_WORKER_NOT_READY",
        )
    mark = resolve_clip_mark(
        project_id=project_id,
        shot_id=shot_id,
        input_path=input_path,
        provider=provider,
    )
    cache_key = watermark_cache_key(
        input_path=input_path,
        mark=mark,
        backend=backend,
        temporal_consistency=temporal_consistency,
        runtime=runtime,
    )
    suffix = input_path.suffix.lower() or ".mp4"
    cache_root = _cache_dir(project_id)
    output_path = cache_root / f"{cache_key}{suffix}"
    report_path = cache_root / f"{cache_key}.json"
    cached = _load_cache_report(report_path, output_path)
    if cached is not None:
        result = dict(cached)
        result.update({"cache_hit": True, "cache_key": cache_key, "shot_id": shot_id})
        return output_path, result

    temp_token = uuid.uuid4().hex[:12]
    temp_output = cache_root / f"{cache_key[:16]}.{temp_token}.tmp{suffix}"
    temp_report = cache_root / f"{cache_key[:16]}.{temp_token}.tmp.json"
    request = {
        "operation": "video_all",
        "source_path": str(input_path),
        "output_path": str(temp_output),
        "mark": mark,
        "backend": backend,
        "temporal_consistency": temporal_consistency,
        "include_invisible": False,
    }
    try:
        completed, payload = _run_worker(
            python=runtime.python,
            worker_script=runtime.worker_script,
            package_root=runtime.package_root,
            revision=runtime.revision or "unknown",
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            request=request,
            timeout=_timeout_seconds(),
        )
        if completed.returncode != 0 or payload.get("ok") is not True:
            message = str(payload.get("message") or completed.stderr or "Watermark worker thất bại.")
            raise VideoWatermarkCleanupError(
                message[:_STDERR_LIMIT],
                error_code=str(payload.get("error_code") or "VIDEO_RENDER_WATERMARK_WORKER_FAILED"),
            )
        if not temp_output.exists() or temp_output.stat().st_size <= 0:
            raise VideoWatermarkCleanupError(
                "Watermark worker không tạo output video hợp lệ.",
                error_code="VIDEO_RENDER_WATERMARK_OUTPUT_MISSING",
            )
        result = {
            **payload,
            "ok": True,
            "output_path": str(output_path),
            "cache_hit": False,
            "cache_key": cache_key,
            "shot_id": shot_id,
            "provider": provider,
            "requested_mark": mark,
            "backend": backend,
            "runtime_revision": runtime.revision,
            "runtime_package_version": runtime.package_version,
            "source_filename": input_path.name,
            "output_filename": output_path.name,
        }
        temp_report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_output.replace(output_path)
        temp_report.replace(report_path)
        return output_path, result
    finally:
        temp_output.unlink(missing_ok=True)
        temp_report.unlink(missing_ok=True)
