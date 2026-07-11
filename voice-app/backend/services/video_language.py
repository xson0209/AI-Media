"""Shared language helpers for AI Video projects."""

from __future__ import annotations

SUPPORTED_VIDEO_TARGET_LANGUAGES = {"en", "vi"}
VIDEO_TARGET_LANGUAGE_PATTERN = "^(en|vi)$"

_LABELS_VI = {
    "en": "tiếng Anh",
    "vi": "tiếng Việt",
}

_LABELS_EN = {
    "en": "English",
    "vi": "Vietnamese",
}


def normalize_video_language(value: str | None, *, default: str = "en") -> str:
    language = (value or default or "en").strip().lower()
    return language if language in SUPPORTED_VIDEO_TARGET_LANGUAGES else default


def video_language_label(value: str | None) -> str:
    return _LABELS_VI[normalize_video_language(value)]


def video_language_english_name(value: str | None) -> str:
    return _LABELS_EN[normalize_video_language(value)]


def narration_field_note(value: str | None) -> str:
    language = normalize_video_language(value)
    if language == "vi":
        return (
            "Trường english_narration là field tương thích cũ; hãy điền narration bằng tiếng Việt "
            "vì target_language của project là vi."
        )
    return (
        "Trường english_narration là field tương thích cũ; hãy điền narration bằng tiếng Anh "
        "vì target_language của project là en."
    )


def viewer_language_instruction(value: str | None) -> str:
    language = normalize_video_language(value)
    if language == "vi":
        return (
            "Video language: Vietnamese. All viewer-facing detailed_script, scene dialogue, "
            "shot narration, spoken voiceover, subtitles, and any on-screen text must be in Vietnamese. "
            "Do not write English narration for this project."
        )
    return (
        "Video language: English. All viewer-facing detailed_script, scene dialogue, "
        "shot narration, spoken voiceover, subtitles, and any on-screen text must be in English."
    )
