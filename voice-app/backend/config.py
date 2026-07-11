"""Compatibility wrapper for backend runtime configuration.

New code should import from ``backend.core.config``.  Existing modules can
continue importing ``backend.config`` while the backend is split into layers.
"""

from .core import config as _core_config
from .core.config import *  # noqa: F403

__all__ = _core_config.__all__
