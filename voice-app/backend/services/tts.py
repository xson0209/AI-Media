"""
TTS inference module - delegates to backend abstraction layer.
"""

from typing import Optional
import numpy as np
import io
import soundfile as sf

from ..backends import get_tts_backend, TTSBackend


def get_tts_model() -> TTSBackend:
    """
    Get TTS backend instance (MLX or PyTorch based on platform).
    
    Returns:
        TTS backend instance
    """
    return get_tts_backend()


def unload_tts_model():
    """Unload TTS model to free memory."""
    backend = get_tts_backend()
    model_size = getattr(backend, "_current_model_size", None) or getattr(backend, "model_size", None)
    backend.unload_model()
    try:
        from .resource_manager import get_resource_manager

        get_resource_manager().record_model_unloaded(kind="tts", engine="qwen", model_size=model_size)
    except Exception:
        pass


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert audio array to WAV bytes."""
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    buffer.seek(0)
    return buffer.read()
