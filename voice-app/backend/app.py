"""FastAPI application factory and middleware wiring."""

import logging
import os
from contextlib import asynccontextmanager

# AMD GPU environment variables must be set before torch import
if not os.environ.get("HSA_OVERRIDE_GFX_VERSION"):
    os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
if not os.environ.get("MIOPEN_LOG_LEVEL"):
    os.environ["MIOPEN_LOG_LEVEL"] = "4"

from urllib.parse import quote

from fastapi import FastAPI

from . import __version__
from .core.cors import configure_cors
from .core.frontend import mount_frontend
from .core.lifecycle import run_shutdown, run_startup
from .core.logging import configure_logging
from .routes import register_routers

configure_logging()

logger = logging.getLogger(__name__)


def safe_content_disposition(disposition_type: str, filename: str) -> str:
    """Build a Content-Disposition header safe for non-ASCII filenames.

    Uses RFC 5987 ``filename*`` parameter so browsers can decode UTF-8
    filenames while the ``filename`` fallback stays ASCII-only.
    """
    ascii_name = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in " -_.")).strip() or "download"
    utf8_name = quote(filename, safe="")
    return f"{disposition_type}; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from .mcp_server.context import ClientIdMiddleware
    from .mcp_server.server import build_mcp_server, compose_lifespan

    # Build the MCP app up-front so we can wire its lifespan into FastAPI's —
    # FastMCP's Streamable HTTP transport only works if its session manager
    # runs inside the parent ASGI lifespan.
    mcp = build_mcp_server()
    mcp_app = mcp.http_app(path="/", transport="http")

    @asynccontextmanager
    async def voicebox_lifespan(app: FastAPI):
        await run_startup(app)
        try:
            yield
        finally:
            # Paired with run_startup via try/finally: runs whether or
            # not the nested MCP lifespan entered cleanly, so a partial
            # startup still unloads whatever models were loaded.
            await run_shutdown()

    # compose_lifespan enters factories in order (voicebox startup →
    # MCP startup) and exits in LIFO (MCP teardown first → models
    # unload last). That ordering matters on shutdown: FastMCP's
    # __aexit__ cancels in-flight session tasks, and we want that to
    # happen *before* _run_shutdown yanks the TTS / Whisper / LLM
    # models out from under any MCP request that was still generating.
    lifespan = compose_lifespan(voicebox_lifespan, mcp_app.router.lifespan_context)

    application = FastAPI(
        title="voicebox API",
        description="Production-quality Qwen3-TTS voice cloning API",
        version=__version__,
        lifespan=lifespan,
    )

    configure_cors(application)
    application.add_middleware(ClientIdMiddleware)
    register_routers(application)
    application.mount("/mcp", mcp_app)
    logger.info("MCP: mounted at /mcp")
    mount_frontend(application)

    return application


app = create_app()
