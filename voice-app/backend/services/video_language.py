"""Shared language helpers for viewer-facing video/story content.

The application UI stays Vietnamese. These helpers describe the content
language for generated story/video output: narration, dialogue, subtitles,
on-screen text, CTA and voice generation.
"""

from __future__ import annotations

SUPPORTED_VIDEO_TARGET_LANGUAGES = {
    "ar",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fr",
    "he",
    "hi",
    "it",
    "ja",
    "ko",
    "ms",
    "nl",
    "no",
    "pl",
    "pt",
    "ru",
    "sv",
    "sw",
    "tr",
    "vi",
    "zh",
}
VIDEO_TARGET_LANGUAGE_PATTERN = "^(" + "|".join(sorted(SUPPORTED_VIDEO_TARGET_LANGUAGES)) + ")$"

_LABELS_VI = {
    "ar": "tiếng Ả Rập",
    "da": "tiếng Đan Mạch",
    "de": "tiếng Đức",
    "el": "tiếng Hy Lạp",
    "en": "tiếng Anh",
    "es": "tiếng Tây Ban Nha",
    "fi": "tiếng Phần Lan",
    "fr": "tiếng Pháp",
    "he": "tiếng Do Thái",
    "hi": "tiếng Hindi",
    "it": "tiếng Ý",
    "ja": "tiếng Nhật",
    "ko": "tiếng Hàn",
    "ms": "tiếng Mã Lai",
    "nl": "tiếng Hà Lan",
    "no": "tiếng Na Uy",
    "pl": "tiếng Ba Lan",
    "pt": "tiếng Bồ Đào Nha",
    "ru": "tiếng Nga",
    "sv": "tiếng Thụy Điển",
    "sw": "tiếng Swahili",
    "tr": "tiếng Thổ Nhĩ Kỳ",
    "vi": "tiếng Việt",
    "zh": "tiếng Trung",
}

_LABELS_EN = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "zh": "Chinese",
}


def normalize_video_language(value: str | None, *, default: str = "en") -> str:
    language = (value or "").strip().lower()
    if language in SUPPORTED_VIDEO_TARGET_LANGUAGES:
        return language
    fallback = (default or "").strip().lower()
    if fallback in SUPPORTED_VIDEO_TARGET_LANGUAGES or fallback == "":
        return fallback
    return "en"


def video_language_label(value: str | None) -> str:
    return _LABELS_VI[normalize_video_language(value)]


def video_language_english_name(value: str | None) -> str:
    return _LABELS_EN[normalize_video_language(value)]


def video_language_prompt_label(value: str | None) -> str:
    language = normalize_video_language(value)
    return f"{_LABELS_VI[language]} / {_LABELS_EN[language]}"


def narration_field_note(value: str | None) -> str:
    language = normalize_video_language(value)
    if language == "vi":
        return (
            "Trường english_narration là field tương thích cũ; hãy điền narration bằng tiếng Việt "
            "vì target_language của project là vi."
        )
    return (
        f"Trường english_narration là field tương thích cũ; hãy điền narration bằng {_LABELS_VI[language]} "
        f"vì target_language của project là {language}."
    )


def viewer_language_instruction(value: str | None) -> str:
    language = normalize_video_language(value)
    if language == "vi":
        return (
            "Video language: Vietnamese. All viewer-facing detailed_script, scene dialogue, "
            "shot narration, spoken voiceover, subtitles, on-screen text, CTA, and voice lines must be in Vietnamese. "
            "Do not write English narration for this project."
        )
    label = _LABELS_EN[language]
    return (
        f"Video language: {label}. All viewer-facing detailed_script, scene dialogue, "
        f"shot narration, spoken voiceover, subtitles, on-screen text, CTA, and voice lines must be in {label}. "
        "Vietnamese is allowed only in *_vi review/explanation fields for the app UI."
    )
