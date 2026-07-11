"""
LLM inference module - delegates to backend abstraction layer.
"""

from ..backends import get_llm_backend, LLMBackend


def get_llm_model() -> LLMBackend:
    """Get LLM backend instance (MLX or PyTorch based on platform)."""
    return get_llm_backend()


def unload_llm_model() -> None:
    """Unload LLM model to free memory."""
    backend = get_llm_backend()
    model_size = getattr(backend, "_current_model_size", None) or getattr(backend, "model_size", None)
    backend.unload_model()
    try:
        from .resource_manager import get_resource_manager

        get_resource_manager().record_model_unloaded(kind="llm", engine="qwen_llm", model_size=model_size)
    except Exception:
        pass
