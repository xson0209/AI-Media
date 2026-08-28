"""Lifecycle helper for the optional Roxy Playwright MCP HTTP sidecar."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

import httpx

from . import storage
from .config import get_config


_lock = threading.RLock()
_process: subprocess.Popen | None = None
_stdout_handle = None
_stderr_handle = None


class SidecarError(RuntimeError):
    def __init__(self, message: str, error_code: str = "ROXY_SIDECAR_ERROR"):
        super().__init__(message)
        self.error_code = error_code


async def health() -> dict[str, Any]:
    cfg = get_config()
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(cfg.sidecar_health_url)
            response.raise_for_status()
            payload = response.json()
        return {"ready": bool(payload.get("ok", True)), "url": cfg.sidecar_health_url}
    except (httpx.HTTPError, ValueError):
        return {"ready": False, "url": cfg.sidecar_health_url}


def _process_status() -> dict[str, Any]:
    with _lock:
        process = _process
        running = process is not None and process.poll() is None
        return {"managed": process is not None, "running": running, "pid": process.pid if running else None}


async def status() -> dict[str, Any]:
    return {**_process_status(), **await health(), "browser_connected": False}


async def start() -> dict[str, Any]:
    global _process, _stdout_handle, _stderr_handle
    current_health = await health()
    if current_health["ready"]:
        return {**_process_status(), **current_health, "browser_connected": False}
    cfg = get_config()
    with _lock:
        already_running = _process is not None and _process.poll() is None
        if not already_running:
            entry = cfg.sidecar_entry_path.resolve()
            if not entry.is_file() or entry.suffix.lower() not in {".js", ".mjs", ".cjs"}:
                raise SidecarError(
                    "Không tìm thấy entry đã build của roxybrowser-playwright-mcp. Hãy chạy script setup trước.",
                    "ROXY_SIDECAR_ENTRY_MISSING",
                )
            node = shutil.which("node")
            if not node:
                raise SidecarError("Không tìm thấy Node.js trong PATH.", "ROXY_SIDECAR_NODE_MISSING")
            runtime = storage.runtime_dir()
            artifacts = storage.sidecar_artifacts_dir()
            stdout_path = runtime / "roxy-playwright.out.log"
            stderr_path = runtime / "roxy-playwright.err.log"
            _stdout_handle = stdout_path.open("ab")
            _stderr_handle = stderr_path.open("ab")
            command = [
                node,
                str(entry),
                "--transport",
                "http",
                "--host",
                cfg.sidecar_host,
                "--port",
                str(cfg.sidecar_port),
                "--path",
                "/mcp",
                "--artifacts-dir",
                str(artifacts),
                "--downloads-dir",
                str(artifacts / "downloads"),
                "--screenshots-dir",
                str(artifacts / "screenshots"),
                "--snapshots-dir",
                str(artifacts / "snapshots"),
                "--temp-dir",
                str(runtime / "temp"),
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            _process = subprocess.Popen(
                command,
                cwd=str(entry.parent),
                stdin=subprocess.DEVNULL,
                stdout=_stdout_handle,
                stderr=_stderr_handle,
                shell=False,
                creationflags=creationflags,
            )
    if already_running:
        return await status()
    for _ in range(20):
        await asyncio.sleep(0.25)
        current = await health()
        if current["ready"]:
            break
        if _process is not None and _process.poll() is not None:
            raise SidecarError("Playwright MCP sidecar đã thoát khi khởi động.", "ROXY_SIDECAR_START_FAILED")
    return await status()


async def stop() -> dict[str, Any]:
    global _process, _stdout_handle, _stderr_handle
    with _lock:
        process = _process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        _process = None
        for handle in (_stdout_handle, _stderr_handle):
            if handle is not None:
                handle.close()
        _stdout_handle = None
        _stderr_handle = None
    return await status()
