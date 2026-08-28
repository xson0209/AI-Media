"""Shared speech-source and Veo-native Vietnamese dialogue helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..database import (
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    VideoProject as DBVideoProject,
    VideoShot as DBVideoShot,
)
from . import video_series_characters

VEO_NATIVE_LANGUAGE = "vi"
SPEECH_SOURCE_VEO_NATIVE = "veo_native"
SPEECH_SOURCE_PROJECT_AUDIO = "project_audio"
SPEECH_SOURCE_NONE = "none"

# News Video UI modes. Legacy projects continue to use the two canonical sources.
NEWS_SPEECH_MODES = {
    "veo_narration",
    "veo_dialogue",
    "voicebox_co_context",
    "voicebox_khong_context",
    "none",
}


def _text(value: Any, *, max_length: int = 6000) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_length]


def speech_source_for_language(target_language: str | None) -> str:
    """Resolve the one effective speech source without silently changing other languages."""
    language = _text(target_language, max_length=20).lower()
    return SPEECH_SOURCE_VEO_NATIVE if language == VEO_NATIVE_LANGUAGE else SPEECH_SOURCE_PROJECT_AUDIO


def speech_mode_for(project: DBVideoProject | None, shot: DBVideoShot | None = None) -> str | None:
    """Resolve explicit News speech mode; NULL keeps legacy behavior."""
    shot_mode = getattr(shot, "speech_source_override", None) if shot is not None else None
    project_mode = getattr(project, "speech_source", None) if project is not None else None
    for value in (shot_mode, project_mode):
        mode = _text(value, max_length=80).lower()
        if mode in NEWS_SPEECH_MODES:
            return mode
    return None


def effective_speech_source(project: DBVideoProject | None, shot: DBVideoShot | None = None) -> str:
    mode = speech_mode_for(project, shot)
    if mode in {"veo_narration", "veo_dialogue"}:
        return SPEECH_SOURCE_VEO_NATIVE
    if mode in {"voicebox_co_context", "voicebox_khong_context", "none"}:
        return SPEECH_SOURCE_PROJECT_AUDIO
    language = getattr(project, "target_language", None) if project is not None else project
    return speech_source_for_language(language)


def uses_veo_native_speech(project_or_language: DBVideoProject | str | None, shot: DBVideoShot | None = None) -> bool:
    if isinstance(project_or_language, str) or project_or_language is None:
        language = project_or_language
        project = None
    else:
        project = project_or_language
        language = getattr(project_or_language, "target_language", None)
    mode = speech_mode_for(project, shot)
    if mode is not None:
        return mode in {"veo_narration", "veo_dialogue"}
    return speech_source_for_language(language) == SPEECH_SOURCE_VEO_NATIVE


def _visible_characters(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("visible_characters")
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _first_visible_character(visible_characters: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in visible_characters if _text(item.get("name") or item.get("character_name"), max_length=160)), None)


def normalize_speech_cues(
    raw_cues: Any,
    *,
    narration: str | None,
    dialogue_mode: str | None,
    visible_characters: Any = None,
    shot_context: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize planner/user speech cues and preserve narration through a safe fallback."""
    visible = _visible_characters(visible_characters)
    first_visible = _first_visible_character(visible)
    normalized: list[dict[str, Any]] = []
    values = raw_cues if isinstance(raw_cues, list) else []
    for raw in values[:20]:
        if not isinstance(raw, dict):
            continue
        text = _text(raw.get("text") or raw.get("dialogue") or raw.get("line") or raw.get("narration"), max_length=20000)
        if not text:
            continue
        profile_id = _text(
            raw.get("character_profile_id") or raw.get("profile_id") or raw.get("series_character_profile_id"),
            max_length=160,
        ) or None
        speaker_name = _text(raw.get("speaker_name") or raw.get("speaker") or raw.get("character_name"), max_length=160)
        if not speaker_name and first_visible and dialogue_mode != "voiceover":
            speaker_name = _text(first_visible.get("name") or first_visible.get("character_name"), max_length=160)
            profile_id = profile_id or _text(
                first_visible.get("character_profile_id") or first_visible.get("profile_id"), max_length=160
            ) or None
        speaker_name = speaker_name or "Narrator"
        default_role = "offscreen_narrator" if dialogue_mode == "voiceover" or speaker_name == "Narrator" else "visible_character"
        speaker_role = _text(raw.get("speaker_role") or raw.get("role"), max_length=80) or default_role
        if speaker_role not in {"visible_character", "offscreen_narrator", "episode_guest", "unknown"}:
            speaker_role = default_role
        start_seconds = raw.get("start_seconds")
        end_seconds = raw.get("end_seconds")
        normalized.append(
            {
                "speaker_name": speaker_name,
                "character_profile_id": profile_id,
                "speaker_role": speaker_role,
                "text": text,
                "voice_description": _text(
                    raw.get("voice_description") or raw.get("voice") or raw.get("speech_style"), max_length=4000
                )
                or None,
                "delivery": _text(raw.get("delivery") or raw.get("delivery_style") or raw.get("pacing"), max_length=4000)
                or None,
                "emotion": _text(raw.get("emotion") or raw.get("emotional_tone"), max_length=2000) or None,
                "context": _text(raw.get("context") or raw.get("scene_context") or shot_context, max_length=6000) or None,
                "pronunciation_notes": _text(raw.get("pronunciation_notes") or raw.get("pronunciation"), max_length=4000) or None,
                "start_seconds": float(start_seconds) if isinstance(start_seconds, (int, float)) and start_seconds >= 0 else None,
                "end_seconds": float(end_seconds) if isinstance(end_seconds, (int, float)) and end_seconds >= 0 else None,
                "lip_sync_required": bool(raw.get("lip_sync_required", speaker_role == "visible_character")),
            }
        )
    if normalized:
        return normalized

    fallback_text = _text(narration, max_length=20000)
    if not fallback_text:
        return []
    speaker_name = "Narrator"
    profile_id: str | None = None
    speaker_role = "offscreen_narrator"
    if dialogue_mode != "voiceover" and first_visible:
        speaker_name = _text(first_visible.get("name") or first_visible.get("character_name"), max_length=160) or "Character"
        profile_id = _text(first_visible.get("character_profile_id") or first_visible.get("profile_id"), max_length=160) or None
        speaker_role = "visible_character"
    return [
        {
            "speaker_name": speaker_name,
            "character_profile_id": profile_id,
            "speaker_role": speaker_role,
            "text": fallback_text,
            "voice_description": None,
            "delivery": None,
            "emotion": _text(first_visible.get("expression") if first_visible else None, max_length=2000) or None,
            "pronunciation_notes": None,
            "context": _text(shot_context, max_length=6000) or None,
            "start_seconds": None,
            "end_seconds": None,
            "lip_sync_required": speaker_role == "visible_character",
        }
    ]


def speech_cues_for_shot(shot: DBVideoShot, project: DBVideoProject | None = None) -> list[dict[str, Any]]:
    return normalize_speech_cues(
        getattr(shot, "speech_cues_json", None),
        narration=getattr(shot, "english_narration", None),
        dialogue_mode=getattr(project, "dialogue_mode", None) if project is not None else None,
        visible_characters=getattr(shot, "retention_json", None),
        shot_context="; ".join(
            part
            for part in [
                _text(getattr(shot, "vietnamese_description", None)),
                _text(getattr(shot, "primary_action", None)),
                _text(getattr(shot, "environment_motion", None)),
            ]
            if part
        ),
    )


def spoken_text_for_shot(shot: DBVideoShot, project: DBVideoProject | None = None) -> str:
    lines = [_text(item.get("text"), max_length=20000) for item in speech_cues_for_shot(shot, project)]
    text = " ".join(line for line in lines if line).strip()
    return text or _text(getattr(shot, "english_narration", None), max_length=20000)


def _profile_maps(project: DBVideoProject, db: Session) -> tuple[dict[str, DBSeriesCharacterProfile], dict[str, DBSeriesCharacterProfile]]:
    if not project.series_id:
        return {}, {}
    rows = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == project.series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    return {row.id: row for row in rows}, {row.name.casefold(): row for row in rows if row.name}


def _guest_maps(project: DBVideoProject) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    flow = video_series_characters.project_character_flow(project)
    guests = [item for item in flow.get("episode_only_guests", []) if isinstance(item, dict)]
    by_id = {_text(item.get("guest_id"), max_length=160): item for item in guests if _text(item.get("guest_id"), max_length=160)}
    by_name = {
        _text(item.get("name"), max_length=160).casefold(): item
        for item in guests
        if _text(item.get("name"), max_length=160)
    }
    return by_id, by_name


def build_veo_native_speech_section(project: DBVideoProject, shot: DBVideoShot, db: Session) -> str:
    """Build an append-only provider section; the existing visual prompt remains untouched."""
    if not uses_veo_native_speech(project):
        return ""
    cues = speech_cues_for_shot(shot, project)
    if not cues:
        return ""
    profiles_by_id, profiles_by_name = _profile_maps(project, db)
    guests_by_id, guests_by_name = _guest_maps(project)
    visible = _visible_characters(getattr(shot, "retention_json", None))
    visible_by_name = {
        _text(item.get("name") or item.get("character_name"), max_length=160).casefold(): item
        for item in visible
        if _text(item.get("name") or item.get("character_name"), max_length=160)
    }
    lines = [
        "Vietnamese spoken dialogue — generate this as audible audio inside the Veo clip:",
        "Use natural Vietnamese pronunciation and keep each named character's voice identity consistent throughout this clip.",
    ]
    for index, cue in enumerate(cues, start=1):
        speaker_name = _text(cue.get("speaker_name"), max_length=160) or "Narrator"
        profile_id = _text(cue.get("character_profile_id"), max_length=160)
        profile = profiles_by_id.get(profile_id) or profiles_by_name.get(speaker_name.casefold())
        guest = guests_by_id.get(profile_id) or guests_by_name.get(speaker_name.casefold())
        visible_context = visible_by_name.get(speaker_name.casefold(), {})
        canonical_voice = _text(cue.get("voice_description"), max_length=4000)
        if not canonical_voice and profile is not None:
            canonical_voice = _text(profile.speech_style, max_length=4000)
        if not canonical_voice and guest is not None:
            canonical_voice = _text(guest.get("speech_style"), max_length=4000)
        if not canonical_voice:
            canonical_voice = (
                "a stable natural Vietnamese cinematic voice, clear articulation, consistent timbre and age across the whole clip"
            )
        personality = _text(profile.personality if profile is not None else guest.get("personality") if guest else None, max_length=2000)
        role = _text(profile.role if profile is not None else guest.get("episode_role") if guest else cue.get("speaker_role"), max_length=500)
        emotion = _text(cue.get("emotion") or visible_context.get("expression") or visible_context.get("emotion"), max_length=2000)
        delivery = _text(cue.get("delivery"), max_length=4000)
        context = _text(
            cue.get("context")
            or "; ".join(
                part
                for part in [
                    _text(getattr(shot, "vietnamese_description", None)),
                    _text(getattr(shot, "primary_action", None)),
                    _text(visible_context.get("action")),
                    _text(visible_context.get("interaction")),
                ]
                if part
            ),
            max_length=6000,
        )
        lines.extend(
            [
                f"Speaker {index}: {speaker_name}",
                f"- Character role: {role or cue.get('speaker_role') or 'speaker'}",
                f"- Canonical voice: {canonical_voice}",
                f"- Personality affecting delivery: {personality or 'follow the established character personality and remain consistent'}",
                f"- Current emotion: {emotion or 'natural emotion matching the scene'}",
                f"- Delivery and pacing: {delivery or 'clear Vietnamese speech paced to fit this clip without rushing or truncation'}",
                f"- Pronunciation notes: {_text(cue.get('pronunciation_notes'), max_length=4000) or 'none'}",
                f"- Scene context: {context or 'follow the visual action and emotional state already described in the visual prompt'}",
                f"- Lip sync: {'required for the visible speaker' if cue.get('lip_sync_required') else 'not required; use a natural off-screen voice if the speaker is not visible'}",
                f'- Speak exactly once in Vietnamese: "{_text(cue.get("text"), max_length=20000)}"',
            ]
        )
    lines.extend(
        [
            "Audio restrictions:",
            "- No English speech, no paraphrase, no translated replacement, no extra narrator, and no additional spoken words.",
            "- Do not swap voices between characters and do not change a character's voice timbre during the clip.",
            "- Generate audible Vietnamese dialogue and natural scene ambience, but do not generate subtitles, captions, text overlays, letters, words, UI text, logos, or watermarks.",
        ]
    )
    return "\n".join(lines).strip()


def build_provider_audio_contract(
    project: DBVideoProject,
    shot: DBVideoShot,
    db: Session | None = None,
) -> str:
    """Return deterministic audio instructions for manual/provider prompt consumers."""
    mode = speech_mode_for(project, shot)
    if mode in {"veo_narration", "veo_dialogue"}:
        if db is not None:
            return build_veo_native_speech_section(project, shot, db)
        cues = speech_cues_for_shot(shot, project)
        kind = "off-screen Vietnamese narration" if mode == "veo_narration" else "visible Vietnamese dialogue with accurate lip-sync"
        lines = ["AUDIO CONTRACT — VEO NATIVE:", f"Generate {kind} inside the clip.", "Speak each line exactly once; no paraphrase, translation, extra words, subtitles, logos, or watermarks."]
        lines.extend(f'Speaker {cue.get("speaker_name", "Narrator")}: "{cue.get("text", "")}"' for cue in cues)
        return "\n".join(lines)
    if mode == "voicebox_co_context":
        context = spoken_text_for_shot(shot, project)
        return (
            "ÂM THANH — TTS VOICEBOX HẬU KỲ:\n"
            f"Nội dung lời chỉ là ngữ cảnh nhịp hình, không được phát thành tiếng: {context}\n"
            "CẤM spoken words, narration, dialogue, voiceover, lip-sync, subtitle, chữ, logo và watermark. "
            "Voicebox sẽ tạo lời đọc sau khi clip được upload."
        )
    if mode in {"voicebox_khong_context", "none"}:
        return (
            "ÂM THANH — KHÔNG LỜI:\n"
            "CẤM mọi spoken words, narration, dialogue, voiceover và lip-sync. "
            "Chỉ ambience/SFX không lời nếu policy cho phép; không tạo subtitle, chữ, logo hoặc watermark."
        )
    return ""

def build_provider_prompt(visual: str, speech_mode: str | None, cues: list[dict[str, Any]] | None = None, negative: str | None = None, continuity: str | None = None) -> dict[str, Any]:
    """Compose deterministic Veo-ready content at read time."""
    import hashlib
    mode = _text(speech_mode, max_length=80).lower() or "none"
    if mode not in NEWS_SPEECH_MODES:
        mode = "none"
    cue_lines = [f'Speaker {c.get("speaker_name", "Narrator")}: "{_text(c.get("text"), max_length=20000)}"' for c in (cues or []) if _text(c.get("text"))]
    if mode == "veo_narration":
        audio = "AUDIO CONTRACT — VEO NATIVE NARRATION: Speak exact lines once as off-screen Vietnamese narration. No paraphrase, extra words, subtitles, or text overlays.\n" + "\n".join(cue_lines)
    elif mode == "veo_dialogue":
        audio = "AUDIO CONTRACT — VEO NATIVE DIALOGUE: Visible speaker, stable identity/wardrobe, exact Vietnamese lines with lip-sync; never swap speaker or paraphrase.\n" + "\n".join(cue_lines)
    elif mode == "voicebox_co_context":
        audio = "AUDIO CONTRACT — VOICEBOX: Lines are timing context only. Veo must be silent: no spoken words, narration, dialogue, voiceover, or lip-sync. Voicebox adds TTS after upload.\n" + "\n".join(cue_lines)
    else:
        audio = "AUDIO CONTRACT — SILENT CLIP: No speech, narration, dialogue, voiceover, or lip-sync; ambience/SFX only if allowed."
    negative_text = _text(negative, max_length=12000) or "subtitles, captions, text overlays, logos, watermarks, extra speakers, paraphrased dialogue"
    provider = "\n\n".join(part for part in [_text(visual, max_length=20000), f"Continuity: {_text(continuity)}" if _text(continuity) else "", audio, "NEGATIVE PROMPT:\n" + negative_text] if part)
    return {"provider_prompt": provider, "negative_prompt": negative_text, "audio_contract": audio, "input_fingerprint": hashlib.sha256(provider.encode("utf-8")).hexdigest()}
