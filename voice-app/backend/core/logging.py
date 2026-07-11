"""Logging setup for the backend process."""

from __future__ import annotations

import logging
import sys
from typing import ClassVar


class ColoredFormatter(logging.Formatter):
    """Formatter that keeps backend logs close to uvicorn's color style."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging() -> None:
    """Configure root logging once for direct backend startup."""
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ColoredFormatter("%(levelname)s:     %(message)s"))
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
    )
