"""
STT (Speech-to-Text) module - delegates to backend abstraction layer.
"""

from typing import Optional
from ..backends import get_stt_backend, STTBackend


def get_whisper_model() -> STTBackend:
    """
    Get STT backend instance (MLX or PyTorch based on platform).
    
    Returns:
        STT backend instance
    """
    return get_stt_backend()


def unload_whisper_model():
    """Unload Whisper model to free memory."""
    backend = get_stt_backend()
    model_size = getattr(backend, "model_size", None)
    backend.unload_model()
    try:
        from .resource_manager import get_resource_manager

        get_resource_manager().record_model_unloaded(kind="stt", engine="whisper", model_size=model_size)
    except Exception:
        pass
