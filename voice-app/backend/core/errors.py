"""Shared backend error types."""

from __future__ import annotations


class BackendError(Exception):
    """Base class for internal backend errors that can be mapped at API edges."""


class ConfigurationError(BackendError):
    """Raised when runtime configuration is invalid for the requested action."""
