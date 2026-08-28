"""Isolated JSON worker for visible AI video-mark cleanup.

This module intentionally imports the optional remove-ai-watermarks runtime only
inside command handlers so Voicebox's main backend does not inherit its native
dependencies. It can be executed by a separately configured Python interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, is_dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "voicebox-watermark-worker-v1"
SUPPORTED_BACKENDS = {"cv2", "migan"}
SUPPORTED_MARKS = {"auto", "sora", "veo", "seedance", "dola", "hailuo", "kling"}
FFMPEG_PATH_ENV = "VOICEBOX_WATERMARK_FFMPEG"
FFPROBE_PATH_ENV = "VOICEBOX_WATERMARK_FFPROBE"

# Declared locally on purpose: importing region_eraser during --check would pull
# the heavy inpainting dependency chain into a cheap diagnostic call. Keep these
# in sync with remove_ai_watermarks.region_eraser.
MIGAN_MODEL_REPO = "andraniksargsyan/migan"
MIGAN_MODEL_FILE = "migan.onnx"

MODEL_CACHE_CACHED = "cached"
MODEL_CACHE_NOT_CACHED = "not_cached"
MODEL_CACHE_UNKNOWN = "unknown"

SETUP_COMMAND_HINT = "powershell -ExecutionPolicy Bypass -File .\\scripts\\setup-watermark-worker.ps1"


def _setup_command(backend: str) -> str:
    """Setup command a user must run to provision the worker for `backend`."""

    if backend == "migan":
        return f"{SETUP_COMMAND_HINT} -Backend migan"
    return SETUP_COMMAND_HINT


def _migan_model_cache_state() -> str:
    """Report whether the MI-GAN ONNX model is already in the local HF cache.

    Looks the model up in the local cache only and never downloads it: readiness
    must stay fast and free of network side effects. Unexpected failures degrade
    to "unknown" rather than reporting the backend as not ready.
    """

    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(repo_id=MIGAN_MODEL_REPO, filename=MIGAN_MODEL_FILE)
        return MODEL_CACHE_CACHED if isinstance(cached, str) and Path(cached).is_file() else MODEL_CACHE_NOT_CACHED
    except Exception:
        return MODEL_CACHE_UNKNOWN


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="strict")


def _tool_alias_directory(tool_path: str, canonical_name: str) -> Path | None:
    source = Path(tool_path).expanduser()
    if not source.exists() or not source.is_file():
        return None
    canonical_filename = f"{canonical_name}.exe" if os.name == "nt" else canonical_name
    if source.name.casefold() == canonical_filename.casefold():
        return source.parent
    stat = source.stat()
    identity = f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    digest = hashlib.sha256(identity).hexdigest()[:12]
    alias_dir = source.parent / f".voicebox-watermark-tools-{digest}"
    alias_dir.mkdir(parents=True, exist_ok=True)
    alias = alias_dir / canonical_filename
    if not alias.exists():
        try:
            alias.symlink_to(source)
        except OSError:
            try:
                os.link(source, alias)
            except OSError:
                shutil.copy2(source, alias)
    if os.name != "nt":
        alias.chmod(alias.stat().st_mode | 0o111)
    return alias_dir


def _configure_tool_aliases() -> None:
    alias_dirs: list[str] = []
    for env_name, canonical_name in ((FFMPEG_PATH_ENV, "ffmpeg"), (FFPROBE_PATH_ENV, "ffprobe")):
        configured = os.environ.get(env_name)
        if not configured:
            continue
        alias_dir = _tool_alias_directory(configured, canonical_name)
        if alias_dir is not None and str(alias_dir) not in alias_dirs:
            alias_dirs.append(str(alias_dir))
    if alias_dirs:
        existing_path = os.environ.get("PATH")
        if existing_path:
            alias_dirs.append(existing_path)
        os.environ["PATH"] = os.pathsep.join(alias_dirs)


def _package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def check_runtime(backend: str) -> dict[str, Any]:
    if backend not in SUPPORTED_BACKENDS:
        return {
            "ok": False,
            "ready": False,
            "protocol_version": PROTOCOL_VERSION,
            "error_code": "WATERMARK_WORKER_BACKEND_UNSUPPORTED",
            "message": "Backend watermark chỉ hỗ trợ cv2 hoặc migan.",
        }
    try:
        import av  # noqa: F401
        import cv2  # noqa: F401
        import remove_ai_watermarks as raiw
    except Exception as exc:
        setup_command = _setup_command(backend)
        return {
            "ok": False,
            "ready": False,
            "protocol_version": PROTOCOL_VERSION,
            "error_code": "WATERMARK_WORKER_DEPENDENCY_MISSING",
            "message": (
                f"Thiếu dependency video watermark: {exc}. "
                f"Python đang chạy worker: {sys.executable}. "
                f"Chạy lệnh setup từ thư mục Voicebox: {setup_command}"
            ),
            "exception_type": type(exc).__name__,
            "python": sys.executable,
            "setup_command": setup_command,
            "backend": backend,
        }

    if not hasattr(raiw, "remove_video_all"):
        return {
            "ok": False,
            "ready": False,
            "protocol_version": PROTOCOL_VERSION,
            "error_code": "WATERMARK_WORKER_VIDEO_API_MISSING",
            "message": "Revision remove-ai-watermarks hiện tại chưa có video API remove_video_all.",
        }
    model_cache: str | None = None
    if backend == "migan":
        try:
            import huggingface_hub  # noqa: F401
            import onnxruntime  # noqa: F401
        except Exception as exc:
            setup_command = _setup_command("migan")
            return {
                "ok": False,
                "ready": False,
                "protocol_version": PROTOCOL_VERSION,
                "error_code": "WATERMARK_WORKER_MIGAN_MISSING",
                "message": (
                    f"Backend MI-GAN chưa sẵn sàng: {exc}. "
                    f"Python đang chạy worker: {sys.executable}. "
                    f"Chạy lệnh setup từ thư mục Voicebox: {setup_command}"
                ),
                "exception_type": type(exc).__name__,
                "python": sys.executable,
                "setup_command": setup_command,
                "backend": "migan",
            }
        model_cache = _migan_model_cache_state()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            "ok": False,
            "ready": False,
            "protocol_version": PROTOCOL_VERSION,
            "error_code": "WATERMARK_WORKER_FFMPEG_MISSING",
            "message": "Watermark worker chưa tìm thấy FFmpeg trên PATH.",
        }
    payload: dict[str, Any] = {
        "ok": True,
        "ready": True,
        "protocol_version": PROTOCOL_VERSION,
        "package_version": getattr(raiw, "__version__", None) or _package_version("remove-ai-watermarks"),
        "revision": os.environ.get("VOICEBOX_WATERMARK_REVISION"),
        "python": sys.executable,
        "ffmpeg": ffmpeg,
        "ffprobe": shutil.which("ffprobe"),
        "backend": backend,
    }
    # cv2 inpainting uses no model, so it reports no model cache state at all.
    if model_cache is not None:
        payload["model_cache"] = model_cache
    return payload


def run_cleanup(request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation") or "")
    if operation != "video_all":
        raise ValueError("Worker chỉ hỗ trợ operation=video_all.")
    if request.get("include_invisible") not in {None, False}:
        raise ValueError("Invisible/SynthID cleanup không được hỗ trợ trong Voicebox MVP.")
    backend = str(request.get("backend") or "cv2")
    mark = str(request.get("mark") or "auto")
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError("Backend watermark chỉ hỗ trợ cv2 hoặc migan.")
    if mark not in SUPPORTED_MARKS:
        raise ValueError("Visible video mark không nằm trong registry được hỗ trợ.")

    source = Path(str(request.get("source_path") or ""))
    output = Path(str(request.get("output_path") or ""))
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Không tìm thấy source clip: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("Worker output phải khác source clip.")
    output.parent.mkdir(parents=True, exist_ok=True)

    import remove_ai_watermarks as raiw

    result = raiw.remove_video_all(
        source,
        output,
        mark=mark,
        backend=backend,
        temporal_consistency=bool(request.get("temporal_consistency", True)),
        include_invisible=False,
    )
    raw_result = asdict(result) if is_dataclass(result) else dict(vars(result))
    visible_mark = raw_result.get("visible_mark")
    detected_metadata = raw_result.get("detected_metadata") or {}
    return {
        "ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "status": "removed" if visible_mark or detected_metadata else "no_supported_mark",
        "output_path": str(output),
        "visible_mark": visible_mark,
        "total_frames": raw_result.get("total_frames"),
        "visible_detected_frames": raw_result.get("visible_detected_frames"),
        "visible_removed_frames": raw_result.get("visible_removed_frames"),
        "detected_metadata": detected_metadata,
        "remaining_metadata": raw_result.get("remaining_metadata") or {},
        "invisible_removed": False,
        "backend": backend,
        "requested_mark": mark,
        "revision": os.environ.get("VOICEBOX_WATERMARK_REVISION"),
    }


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("Worker không nhận được JSON request.")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Worker request phải là JSON object.")
    return payload


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    _configure_tool_aliases()
    parser = argparse.ArgumentParser(description="Voicebox isolated video watermark worker")
    parser.add_argument("--check", action="store_true", help="Check optional video watermark runtime")
    parser.add_argument("--backend", choices=sorted(SUPPORTED_BACKENDS), default="cv2")
    args = parser.parse_args(argv)
    if args.check:
        payload = check_runtime(args.backend)
        _emit(payload)
        return 0 if payload.get("ready") else 1
    try:
        _emit(run_cleanup(_read_request()))
        return 0
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "protocol_version": PROTOCOL_VERSION,
                "error_code": "WATERMARK_WORKER_FAILED",
                "message": str(exc),
                "exception_type": type(exc).__name__,
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
