"""AI Video schema bridge.

The public Pydantic models still live in ``backend.models`` during the first
refactor pass.  This module gives feature code a stable domain import path
without changing response JSON.
"""

from ... import models as _models

__all__ = [name for name in dir(_models) if name.startswith(("Video", "AI"))]

globals().update({name: getattr(_models, name) for name in __all__})
