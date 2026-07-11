"""Purpose and dialogue presets for AI Video projects."""

from __future__ import annotations

from dataclasses import dataclass

from . import video_language

VIDEO_PURPOSE_CUSTOM = "custom"
VIDEO_PURPOSE_VALUES = {
    VIDEO_PURPOSE_CUSTOM,
    "vietnam_market",
    "global_short",
    "educational_explainer",
    "sales_ad",
    "localized_variant",
}
VIDEO_PURPOSE_PATTERN = "^(custom|vietnam_market|global_short|educational_explainer|sales_ad|localized_variant)$"

DIALOGUE_MODE_VALUES = {"voiceover", "character_lines", "mixed"}
DIALOGUE_MODE_PATTERN = "^(voiceover|character_lines|mixed)$"

NARRATION_DENSITY_VALUES = {"light", "balanced", "dense"}
NARRATION_DENSITY_PATTERN = "^(light|balanced|dense)$"

CTA_STYLE_PATTERN = "^(none|soft|direct|urgent)$"


@dataclass(frozen=True)
class VideoPurposePreset:
    value: str
    label_vi: str
    description_vi: str
    recommended_target_language: str
    dialogue_mode: str
    narration_density: str
    subtitle_expectation: str
    tone_guidance: str
    call_to_action_style: str | None = None


VIDEO_PURPOSE_PRESETS: dict[str, VideoPurposePreset] = {
    VIDEO_PURPOSE_CUSTOM: VideoPurposePreset(
        value=VIDEO_PURPOSE_CUSTOM,
        label_vi="Tuy chinh",
        description_vi="Nguoi dung tu chon ngon ngu, voice va cach viet loi thoai.",
        recommended_target_language="en",
        dialogue_mode="voiceover",
        narration_density="balanced",
        subtitle_expectation="subtitle follows target_language",
        tone_guidance="Follow the user's source blocks and visual style without forcing a preset use case.",
        call_to_action_style="none",
    ),
    "vietnam_market": VideoPurposePreset(
        value="vietnam_market",
        label_vi="Thi truong Viet Nam",
        description_vi="Toi uu cho nguoi xem Viet Nam voi loi ke/chuyen thoai tieng Viet tu nhien.",
        recommended_target_language="vi",
        dialogue_mode="voiceover",
        narration_density="balanced",
        subtitle_expectation="Vietnamese subtitle matching Vietnamese voiceover",
        tone_guidance="Use natural Vietnamese phrasing, local context, clear emotional beats, and avoid stiff translated wording.",
        call_to_action_style="soft",
    ),
    "global_short": VideoPurposePreset(
        value="global_short",
        label_vi="Global / English short",
        description_vi="Toi uu cho short quoc te bang tieng Anh, hook nhanh va de hieu.",
        recommended_target_language="en",
        dialogue_mode="voiceover",
        narration_density="balanced",
        subtitle_expectation="English subtitle matching English voiceover",
        tone_guidance="Use concise international English, fast hook, visual clarity, and short punchy lines.",
        call_to_action_style="soft",
    ),
    "educational_explainer": VideoPurposePreset(
        value="educational_explainer",
        label_vi="Giai thich / giao duc",
        description_vi="Uu tien loi thoai ro nghia, du ngu canh va nhip de nghe.",
        recommended_target_language="vi",
        dialogue_mode="voiceover",
        narration_density="dense",
        subtitle_expectation="subtitle should preserve explanatory clarity",
        tone_guidance="Explain one idea at a time, use concrete examples, avoid jargon unless it is immediately clarified.",
        call_to_action_style="none",
    ),
    "sales_ad": VideoPurposePreset(
        value="sales_ad",
        label_vi="Quang cao / ban hang",
        description_vi="Uu tien hook, loi ich, bang chung nhanh va CTA ro.",
        recommended_target_language="vi",
        dialogue_mode="voiceover",
        narration_density="light",
        subtitle_expectation="subtitle should be concise and CTA-friendly",
        tone_guidance="Lead with a pain point or promise, show concrete benefit, keep claims specific, and end with a clear CTA.",
        call_to_action_style="direct",
    ),
    "localized_variant": VideoPurposePreset(
        value="localized_variant",
        label_vi="Ban localize",
        description_vi="Tao bien the rieng cho audience/ngon ngu moi tu cung source.",
        recommended_target_language="en",
        dialogue_mode="voiceover",
        narration_density="balanced",
        subtitle_expectation="subtitle follows the localized target language",
        tone_guidance="Keep the original idea and continuity, but rewrite idioms and examples naturally for the new audience.",
        call_to_action_style="soft",
    ),
}

VIDEO_PURPOSE_VALUE_ALIASES = {
    "vietnam": "vietnam_market",
    "vietnamese": "vietnam_market",
    "vietnamese_market": "vietnam_market",
    "viet_nam": "vietnam_market",
    "global": "global_short",
    "english_short": "global_short",
    "international_short": "global_short",
    "educational": "educational_explainer",
    "education": "educational_explainer",
    "explainer": "educational_explainer",
    "sales": "sales_ad",
    "ad": "sales_ad",
    "advertisement": "sales_ad",
    "localized": "localized_variant",
    "localised_variant": "localized_variant",
}

DIALOGUE_MODE_VALUE_ALIASES = {
    "voice_over": "voiceover",
    "narration": "voiceover",
    "narrator": "voiceover",
    "character_dialogue": "character_lines",
    "character_line": "character_lines",
    "dialogue": "character_lines",
    "hybrid": "mixed",
}

NARRATION_DENSITY_VALUE_ALIASES = {
    "short": "light",
    "low": "light",
    "medium": "balanced",
    "normal": "balanced",
    "heavy": "dense",
    "high": "dense",
}

def _token(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")

PURPOSE_FIELD_ALIASES = ("video_purpose", "purpose", "project_purpose", "audience_purpose", "use_case")
DIALOGUE_MODE_FIELD_ALIASES = ("dialogue_mode", "voice_mode", "speech_mode", "narration_mode")
NARRATION_DENSITY_FIELD_ALIASES = ("narration_density", "voiceover_density", "speech_density", "talk_density")
CTA_STYLE_FIELD_ALIASES = ("call_to_action_style", "cta_style", "cta", "sales_cta")
NARRATION_TEXT_FIELD_ALIASES = (
    "english_narration",
    "narration",
    "voiceover",
    "voice_over",
    "voiceover_text",
    "voice_over_text",
    "narration_text",
    "spoken_narration",
    "dialogue",
)


def normalize_video_purpose(value: str | None, *, default: str = VIDEO_PURPOSE_CUSTOM) -> str:
    purpose = _token(value or default or VIDEO_PURPOSE_CUSTOM)
    purpose = VIDEO_PURPOSE_VALUE_ALIASES.get(purpose, purpose)
    return purpose if purpose in VIDEO_PURPOSE_VALUES else default


def purpose_preset(value: str | None) -> VideoPurposePreset:
    return VIDEO_PURPOSE_PRESETS[normalize_video_purpose(value)]


def normalize_dialogue_mode(value: str | None, *, purpose: str | None = None, default: str | None = None) -> str:
    fallback = default or purpose_preset(purpose).dialogue_mode
    mode = _token(value or fallback or "voiceover")
    mode = DIALOGUE_MODE_VALUE_ALIASES.get(mode, mode)
    return mode if mode in DIALOGUE_MODE_VALUES else fallback


def normalize_narration_density(value: str | None, *, purpose: str | None = None, default: str | None = None) -> str:
    fallback = default or purpose_preset(purpose).narration_density
    density = _token(value or fallback or "balanced")
    density = NARRATION_DENSITY_VALUE_ALIASES.get(density, density)
    return density if density in NARRATION_DENSITY_VALUES else fallback


def normalize_call_to_action_style(value: str | None, *, purpose: str | None = None) -> str | None:
    fallback = purpose_preset(purpose).call_to_action_style
    style = _token(value or fallback or "")
    if not style or style == "none":
        return None
    if style in {"soft", "direct", "urgent"}:
        return style
    return None if fallback in {None, "none"} else fallback


def resolve_purpose_settings(
    *,
    video_purpose: str | None,
    target_language: str | None = None,
    dialogue_mode: str | None = None,
    narration_density: str | None = None,
    call_to_action_style: str | None = None,
) -> dict[str, str | None]:
    purpose = normalize_video_purpose(video_purpose)
    preset = purpose_preset(purpose)
    language = video_language.normalize_video_language(target_language or preset.recommended_target_language)
    return {
        "video_purpose": purpose,
        "target_language": language,
        "dialogue_mode": normalize_dialogue_mode(dialogue_mode, purpose=purpose),
        "narration_density": normalize_narration_density(narration_density, purpose=purpose),
        "call_to_action_style": normalize_call_to_action_style(call_to_action_style, purpose=purpose),
    }


def purpose_context_lines(
    *,
    video_purpose: str | None,
    target_language: str | None,
    dialogue_mode: str | None,
    narration_density: str | None,
    call_to_action_style: str | None,
) -> list[str]:
    settings = resolve_purpose_settings(
        video_purpose=video_purpose,
        target_language=target_language,
        dialogue_mode=dialogue_mode,
        narration_density=narration_density,
        call_to_action_style=call_to_action_style,
    )
    preset = purpose_preset(str(settings["video_purpose"]))
    lines = [
        f"Video purpose: {settings['video_purpose']} - {preset.label_vi}",
        f"Purpose description: {preset.description_vi}",
        f"Dialogue mode: {settings['dialogue_mode']}",
        f"Narration density: {settings['narration_density']}",
        f"Subtitle expectation: {preset.subtitle_expectation}",
        f"Tone guidance: {preset.tone_guidance}",
    ]
    if settings.get("call_to_action_style"):
        lines.append(f"Call to action style: {settings['call_to_action_style']}")
    lines.append(
        "Purpose guidance must never override target_language for viewer-facing speech, subtitles, or on-screen text."
    )
    return lines
