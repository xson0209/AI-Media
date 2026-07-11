"""Local Qwen3-TTS 1.7B-only policy plus Vietnamese experiment gate.

Qwen3-TTS does not list Vietnamese as an official language. This module keeps
the exception narrow: only the base Qwen 1.7B engine is enabled, and Vietnamese
requires a Vietnamese voice profile.
"""

from __future__ import annotations

from typing import Any

QWEN_ENGINE = "qwen"
QWEN_VIETNAMESE_MODEL_SIZE = "1.7B"
VIETNAMESE_LANGUAGE = "vi"

def _profile_language(profile: Any) -> str:
    return (getattr(profile, "language", None) or "").strip().lower()

def resolve_engine(
    *,
    profile: Any,
    engine: str | None,
    language: str | None,
) -> str:
    return QWEN_ENGINE

def normalize_model_size(
    *,
    engine: str | None,
    language: str | None,
    model_size: str | None,
) -> str | None:
    if engine == QWEN_ENGINE:
        return QWEN_VIETNAMESE_MODEL_SIZE
    return model_size


def is_qwen_vietnamese_request(
    *,
    engine: str | None,
    model_size: str | None,
    language: str | None,
) -> bool:
    return engine == QWEN_ENGINE and language == VIETNAMESE_LANGUAGE


def should_allow_profile_bypass(
    *,
    profile: Any,
    engine: str | None,
    model_size: str | None,
    language: str | None,
) -> bool:
    profile_language = (getattr(profile, "language", None) or "").strip().lower()
    return (
        is_qwen_vietnamese_request(engine=engine, model_size=model_size, language=language)
        and model_size == QWEN_VIETNAMESE_MODEL_SIZE
        and profile_language == VIETNAMESE_LANGUAGE
    )


def ensure_qwen_vietnamese_allowed(
    *,
    profile: Any,
    engine: str | None,
    model_size: str | None,
    language: str | None,
) -> None:
    """Reject unsupported Qwen Vietnamese combinations."""
    if engine != QWEN_ENGINE:
        raise ValueError("This local test build only enables Qwen TTS 1.7B.")
    if model_size != QWEN_VIETNAMESE_MODEL_SIZE:
        raise ValueError("This local test build only enables Qwen TTS 1.7B.")
    if language != VIETNAMESE_LANGUAGE:
        return
    if not should_allow_profile_bypass(
        profile=profile,
        engine=engine,
        model_size=model_size,
        language=language,
    ):
        raise ValueError("Vietnamese Qwen generation requires a Vietnamese voice profile.")
