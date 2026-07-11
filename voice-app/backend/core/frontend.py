"""Static frontend mounting for Docker/web deployments."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def mount_frontend(application: FastAPI) -> None:
    """Serve the built web frontend when present.

    In development or API-only mode the frontend build directory is absent and
    this function is intentionally a no-op.
    """
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if not frontend_dir.is_dir():
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets_dir = frontend_dir / "assets"
    if assets_dir.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="frontend-assets",
        )

    @application.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = (frontend_dir / full_path).resolve()
        if full_path and file_path.is_file() and file_path.is_relative_to(frontend_dir):
            return FileResponse(file_path)
        return FileResponse(frontend_dir / "index.html", media_type="text/html")

    logger.info("Frontend: serving SPA from %s", frontend_dir)
