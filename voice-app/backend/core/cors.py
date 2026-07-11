"""CORS configuration for the FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import RuntimeConfig, get_runtime_config


def configure_cors(application: FastAPI, settings: RuntimeConfig | None = None) -> None:
    """Install CORS middleware using the shared runtime configuration."""
    runtime_config = settings or get_runtime_config()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
