"""Compatibility import for the AI Video render module.

Both paths resolve to the same module, including private helpers and runtime
state, so existing callers and dependency patches retain their behavior.
"""

import sys

from ..features.ai_video import render as _implementation

sys.modules[__name__] = _implementation
