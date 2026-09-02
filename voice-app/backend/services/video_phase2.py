"""Phase 2 Script-to-Video-Prompt workflow for AI Video Assistant."""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import (
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    VideoProject as DBVideoProject,
    VideoScene as DBVideoScene,
    VideoSeries as DBVideoSeries,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSourceBlock as DBVideoSourceBlock,
)
from . import (
    ai_planning,
    series_brain,
    series_references,
    settings as settings_service,
    video_language,
    video_observability,
    video_planning_pool,
    video_purpose as video_purpose_service,
    video_rendering,
    video_series_memory,
    video_series_characters,
    video_speech,
    video_state,
    video_storage,
)
from .video_planning import VideoPlanningValidationError, _load_json_object

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
VIDEO_PROMPT_BATCH_SIZE = 5
VIDEO_PROMPT_BATCH_MAX_ATTEMPTS = 2
PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS = 600
PHASE2_MAX_CODEX_TIMEOUT_SECONDS = 600
VIDEO_PROMPT_SEGMENT_SECONDS = 8
DEFAULT_MICRO_SCENES_PER_PROMPT = 4
NARRATION_MIN_WORDS_PER_SECOND = 2.1
NARRATION_TARGET_WORDS_PER_SECOND = 2.7
NARRATION_MAX_WORDS_PER_SECOND = 3.4
SHOT_VARIATION_FIELDS = ("camera_angle", "framing", "composition", "camera_motion")
VIDEO_PROMPT_LIST_KEYS = (
    "prompts",
    "video_prompts",
    "shot_prompts",
    "shots",
    "segments",
    "prompt_segments",
    "video_segments",
    "segment_prompts",
    "video_prompt_segments",
    "prompt_breakdown",
    "clip_prompts",
    "clips",
)

@dataclass(frozen=True)
class PromptSegmentConfig:
    segment_count: int | None
    prompt_duration_seconds: int
    micro_scenes_per_prompt: int
    target_duration_seconds: int | None
    explicit: bool

def _format_seconds(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")

def _resolve_prompt_segment_config(project: DBVideoProject) -> PromptSegmentConfig:
    configured_values = (
        getattr(project, "prompt_segment_count", None),
        getattr(project, "prompt_segment_duration_seconds", None),
        getattr(project, "micro_scenes_per_prompt", None),
    )
    if all(value is not None and int(value) > 0 for value in configured_values):
        count = int(configured_values[0] or 0)
        duration = int(configured_values[1] or VIDEO_PROMPT_SEGMENT_SECONDS)
        micro_count = int(configured_values[2] or DEFAULT_MICRO_SCENES_PER_PROMPT)
        return PromptSegmentConfig(
            segment_count=count,
            prompt_duration_seconds=duration,
            micro_scenes_per_prompt=micro_count,
            target_duration_seconds=count * duration,
            explicit=True,
        )
    target_duration = getattr(project, "target_duration_seconds", None)
    if target_duration and target_duration > 0:
        return PromptSegmentConfig(
            segment_count=max(1, math.ceil(target_duration / VIDEO_PROMPT_SEGMENT_SECONDS)),
            prompt_duration_seconds=VIDEO_PROMPT_SEGMENT_SECONDS,
            micro_scenes_per_prompt=DEFAULT_MICRO_SCENES_PER_PROMPT,
            target_duration_seconds=int(target_duration),
            explicit=False,
        )
    return PromptSegmentConfig(
        segment_count=None,
        prompt_duration_seconds=VIDEO_PROMPT_SEGMENT_SECONDS,
        micro_scenes_per_prompt=DEFAULT_MICRO_SCENES_PER_PROMPT,
        target_duration_seconds=None,
        explicit=False,
    )

def _micro_scene_ranges(duration_seconds: float | int, micro_scene_count: int) -> list[tuple[float, float]]:
    duration = max(0.1, float(duration_seconds or VIDEO_PROMPT_SEGMENT_SECONDS))
    count = max(1, int(micro_scene_count or DEFAULT_MICRO_SCENES_PER_PROMPT))
    step = duration / count
    ranges: list[tuple[float, float]] = []
    for index in range(count):
        start = round(index * step, 2)
        end = round(duration if index == count - 1 else (index + 1) * step, 2)
        ranges.append((start, end))
    return ranges

def _micro_scene_range_label(start: float | int, end: float | int) -> str:
    return f"{_format_seconds(start)}-{_format_seconds(end)}s"

def _default_retention_payload(*, fallback: str = "") -> dict[str, object]:
    review = fallback.strip() or "Mở video bằng một hình ảnh hoặc câu hỏi gây tò mò, đổi nhịp đều đặn và kết bằng payoff rõ ràng."
    return {
        "review_vi": review,
        "hook_0_2s": "Mở bằng hình ảnh hoặc câu đầu tiên đủ mạnh trong 0-2 giây để người xem dừng lại.",
        "viewer_question": "Điều gì sẽ xảy ra tiếp theo?",
        "curiosity_gap": "Giữ một thông tin hoặc kết quả chưa tiết lộ cho tới payoff.",
        "beat_curve": [
            {
                "start_seconds": 0,
                "end_seconds": 2,
                "purpose": "cold open",
                "viewer_reason": "tạo tò mò ngay lập tức",
                "pattern_interrupt": "đổi hình/camera sớm nếu cảnh đứng yên",
                "visual_surprise": "một chi tiết thị giác bất ngờ nhưng đúng continuity",
            }
        ],
        "pattern_interrupts": ["Đổi cỡ cảnh, góc máy, chuyển động hoặc âm thanh trước khi đoạn bị tĩnh."],
        "payoff_plan": "Kết thúc bằng hình ảnh, câu nói hoặc khoảnh khắc giải quyết curiosity gap.",
        "dropoff_risks": ["Đoạn quá tĩnh", "Narration dày nhưng visual không đổi", "Thiếu payoff rõ"],
    }

def _default_transition_payload(*, final: bool = False, fallback: str = "") -> dict[str, object]:
    if final:
        return {
            "transition_type": "final hold",
            "trigger": "payoff frame or final narration beat",
            "timing": "last 1-2 seconds",
            "edit_reason": "let the viewer register the payoff before the video ends",
            "transition_sfx": "soft impact or clean music resolve",
            "continuity_risk": "low; keep the same character, style, and story state",
        }
    return {
        "transition_type": "motivated cut",
        "trigger": fallback.strip() or "visual action, narration beat, or sound cue",
        "timing": "end of the shot or segment",
        "edit_reason": "move viewer attention to the next beat without breaking continuity",
        "transition_sfx": "subtle whoosh, riser, or impact hit under the cut",
        "continuity_risk": "low if character identity, wardrobe, setting, and style stay consistent",
    }

def _default_sound_payload(*, has_narration: bool = True, fallback: str = "") -> dict[str, object]:
    cue = fallback.strip() or "subtle whoosh or impact hit on the edit point"
    return {
        "review_vi": "Nhạc nền điện ảnh hỗ trợ nhịp kể, tăng năng lượng ở đoạn reveal/payoff, SFX ngắn dùng để nhấn chuyển cảnh và luôn giữ giọng đọc rõ.",
        "music_mood": "cinematic, controlled, supportive of the narration",
        "energy_curve": "start restrained, build through the reveal, resolve at payoff",
        "ambience_bed": "light ambience matching the setting without distracting from voice",
        "sound_cues": [
            {
                "cue_type": "transition accent",
                "timing": "near the cut or reveal",
                "purpose": cue,
                "mix_note": "keep short and below the voice",
            }
        ],
        "silence_drops": ["Use a brief silence drop before a reveal only if it strengthens the beat."],
        "mixing_notes": "Voice must stay clear above music and SFX." if has_narration else "Use ambience and short SFX to carry rhythm because this shot has no narration.",
    }

class RetentionBeatPlan(BaseModel):
    start_seconds: float | None = Field(default=None, ge=0, le=7200)
    end_seconds: float | None = Field(default=None, ge=0, le=7200)
    purpose: str = Field(default="", max_length=4000)
    viewer_reason: str = Field(default="", max_length=4000)
    pattern_interrupt: str = Field(default="", max_length=4000)
    visual_surprise: str = Field(default="", max_length=4000)

class RetentionDirectionPlan(BaseModel):
    review_vi: str = Field(default="", max_length=20000)
    hook_0_2s: str = Field(default="", max_length=4000)
    viewer_question: str = Field(default="", max_length=4000)
    curiosity_gap: str = Field(default="", max_length=4000)
    beat_curve: list[RetentionBeatPlan] = Field(default_factory=list, max_length=80)
    pattern_interrupts: list[str] = Field(default_factory=list, max_length=80)
    payoff_plan: str = Field(default="", max_length=4000)
    dropoff_risks: list[str] = Field(default_factory=list, max_length=80)

class TransitionPackPlan(BaseModel):
    transition_type: str = Field(default="", max_length=160)
    trigger: str = Field(default="", max_length=4000)
    timing: str = Field(default="", max_length=1000)
    edit_reason: str = Field(default="", max_length=4000)
    transition_sfx: str = Field(default="", max_length=1000)
    continuity_risk: str = Field(default="", max_length=4000)

class SoundCuePlan(BaseModel):
    cue_type: str = Field(default="", max_length=160)
    timing: str = Field(default="", max_length=1000)
    purpose: str = Field(default="", max_length=4000)
    mix_note: str = Field(default="", max_length=4000)

class SoundDesignPlan(BaseModel):
    music_mood: str = Field(default="", max_length=4000)
    energy_curve: str = Field(default="", max_length=4000)
    ambience_bed: str = Field(default="", max_length=4000)
    sound_cues: list[SoundCuePlan] = Field(default_factory=list, max_length=120)
    silence_drops: list[str] = Field(default_factory=list, max_length=80)
    mixing_notes: str = Field(default="", max_length=4000)

class ProjectSoundDesignPlan(SoundDesignPlan):
    review_vi: str = Field(
        default="",
        max_length=20000,
        description="Vietnamese review text for the UI only. Do not copy this into generation prompts.",
    )

class CharacterReferencePlan(BaseModel):
    """Structured character reference used by strict provider schemas."""
    name: str = Field(default="", max_length=160)
    character_profile_id: str | None = Field(default=None, max_length=160)
    guest_id: str | None = Field(default=None, max_length=160)
    role: str = Field(default="", max_length=400)
    appearance: str = Field(default="", max_length=4000)
    position: str = Field(default="", max_length=1000)
    action: str = Field(default="", max_length=4000)
    expression: str = Field(default="", max_length=2000)
    interaction: str = Field(default="", max_length=4000)


def _json_safe(value: Any) -> Any:
    """Convert nested Pydantic models to values accepted by JSON/JSON columns."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value

class PromptQualityCheckPlan(BaseModel):
    """Fixed contract for prompt QA; values remain JSON compatible."""
    passed: bool = False
    missing_fields: list[str] = Field(default_factory=list, max_length=80)
    warnings: list[str] = Field(default_factory=list, max_length=80)
    score: float | None = Field(default=None, ge=0, le=1)
    notes: str = Field(default="", max_length=6000)


SEGMENT_CAMERA_VARIATION_PROFILES = (
    {
        "shot_type": "opening segment",
        "camera_angle": "low three-quarter angle",
        "framing": "wide establishing frame into medium subject frame",
        "composition": "foreground subject leads into layered background depth",
        "camera_motion": "slow forward push-in with a gentle lateral drift",
    },
    {
        "shot_type": "build-up segment",
        "camera_angle": "eye-level side angle",
        "framing": "medium two-plane frame with foreground detail",
        "composition": "subject offset on the left third with story detail on the right",
        "camera_motion": "smooth side track that settles into a locked hold",
    },
    {
        "shot_type": "detail segment",
        "camera_angle": "high detail angle",
        "framing": "tight insert frame opening to close-up reaction",
        "composition": "important object fills the foreground before revealing the subject",
        "camera_motion": "controlled tilt down then short rack-focus move",
    },
    {
        "shot_type": "climax segment",
        "camera_angle": "low hero angle",
        "framing": "dynamic close-up widening into action frame",
        "composition": "diagonal action line pulls from lower foreground to upper background",
        "camera_motion": "fast tracking move that lands on a stable final frame",
    },
    {
        "shot_type": "payoff segment",
        "camera_angle": "over-the-shoulder angle",
        "framing": "shoulder foreground with subject and result framed beyond",
        "composition": "foreground silhouette frames the emotional payoff in the center",
        "camera_motion": "subtle handheld drift into a gentle push-in",
    },
)

class StoryScenePlan(BaseModel):
    title: str = Field(default="", max_length=160)
    vietnamese_description: str = Field(default="", max_length=12000)
    # Backward-compatible storage/API field. The value is narration text in the selected project video language.
    english_narration: str = Field(
        default="",
        max_length=20000,
        description="Longer scene voiceover text in the selected video language, not a short tagline.",
    )
    character_appearance: str = Field(..., min_length=1, max_length=4000)
    wardrobe_and_sandals: str = Field(..., min_length=1, max_length=4000)
    subject_motion_by_duration: str = Field(..., min_length=1, max_length=4000)
    setting_and_lighting: str = Field(..., min_length=1, max_length=4000)
    detailed_mood: str = Field(..., min_length=1, max_length=4000)
    target_duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    related_characters: list[CharacterReferencePlan] = Field(default_factory=list, max_length=30)

class StoryDevelopmentPlan(BaseModel):
    video_purpose: str | None = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: str | None = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: str | None = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: str | None = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    input_synthesis: str = Field(default="", max_length=50000)
    story_strategy_vi: str = Field(default="", max_length=50000)
    story_strategy: str = Field(default="", max_length=50000)
    continuity_bible_vi: str = Field(default="", max_length=50000)
    continuity_bible: str = Field(default="", max_length=50000)
    detailed_script_vi: str = Field(default="", max_length=80000)
    detailed_script: str = Field(default="", max_length=80000)
    retention_plan: RetentionDirectionPlan = Field(default_factory=RetentionDirectionPlan)
    sound_design_plan: ProjectSoundDesignPlan = Field(default_factory=ProjectSoundDesignPlan)
    episode_cast: list[models.EpisodeCastMember] = Field(default_factory=list, max_length=50)
    episode_only_guests: list[models.EpisodeOnlyGuest] = Field(default_factory=list, max_length=50)
    new_character_proposals: list[models.NewCharacterProposal] = Field(default_factory=list, max_length=50)
    scenes: list[StoryScenePlan] = Field(default_factory=list, min_length=1, max_length=120)

class MicroScenePlan(BaseModel):
    order: int = Field(..., ge=1, le=20)
    start_seconds: float = Field(..., ge=0, le=7200)
    end_seconds: float = Field(..., ge=0, le=7200)
    description_vi: str = Field(default="", max_length=4000)
    visual_action: str = Field(default="", max_length=4000)
    camera_note: str = Field(default="", max_length=4000)
    continuity_note: str = Field(default="", max_length=4000)
    visible_characters: list[CharacterReferencePlan] = Field(default_factory=list, max_length=20)

class ShotPlan(BaseModel):
    scene_order: int = Field(..., ge=1)
    shot_order: int = Field(..., ge=1)
    duration_seconds: float | None = Field(default=None, ge=0.5, le=30)
    vietnamese_description: str = Field(
        default="",
        max_length=12000,
        description="Vietnamese review text. In prompt segment mode, include the configured timestamped micro-scenes.",
    )
    # Backward-compatible storage/API field. The value is narration text in the selected project video language.
    english_narration: str = Field(
        default="",
        max_length=20000,
        description="Longer voiceover text in the selected video language, sized to cover most of the shot or segment duration.",
    )
    primary_action: str = Field(default="", max_length=4000)
    purpose: str = Field(default="", max_length=4000)
    shot_type: str = Field(default="", max_length=120)
    camera_angle: str = Field(default="", max_length=160)
    framing: str = Field(default="", max_length=160)
    composition: str = Field(default="", max_length=4000)
    camera_motion: str = Field(default="", max_length=160)
    subject_motion: str = Field(default="", max_length=4000)
    environment_motion: str = Field(default="", max_length=4000)
    transition_to_next: str = Field(default="", max_length=4000)
    retention_role: str = Field(default="", max_length=160)
    open_loop: str = Field(default="", max_length=4000)
    visual_surprise: str = Field(default="", max_length=4000)
    cut_reason: str = Field(default="", max_length=4000)
    visible_characters: list[CharacterReferencePlan] = Field(default_factory=list, max_length=30)
    speech_cues: list[models.VideoShotSpeechCue] = Field(default_factory=list, max_length=20)
    transition_pack: TransitionPackPlan = Field(default_factory=TransitionPackPlan)
    sound_design: SoundDesignPlan = Field(default_factory=SoundDesignPlan)
    micro_scenes: list[MicroScenePlan] = Field(default_factory=list, max_length=20)

class ShotBreakdownPlan(BaseModel):
    video_purpose: str | None = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: str | None = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: str | None = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: str | None = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    shots: list[ShotPlan] = Field(..., min_length=1, max_length=400)

class VideoPromptPlan(BaseModel):
    shot_order: int = Field(..., ge=1)
    prompt: str = Field(..., min_length=1, max_length=20000)
    prompt_explanation_vi: str = Field(
        default="",
        max_length=12000,
        description="Vietnamese review text that explains the video prompt for the user. Not copied into the generation prompt by default.",
    )
    negative_prompt: str = Field(default="", max_length=6000)
    duration_seconds: float | None = Field(default=None, ge=0.5, le=30)
    aspect_ratio: str = Field(default="9:16", max_length=20)
    shot_type: str = Field(default="", max_length=120)
    camera_angle: str = Field(default="", max_length=160)
    framing: str = Field(default="", max_length=160)
    composition: str = Field(default="", max_length=4000)
    camera_motion: str = Field(default="", max_length=160)
    subject_motion: str = Field(default="", max_length=4000)
    environment_motion: str = Field(default="", max_length=4000)
    start_frame: str = Field(default="", max_length=4000)
    end_frame: str = Field(default="", max_length=4000)
    lighting: str = Field(default="", max_length=4000)
    mood: str = Field(default="", max_length=4000)
    continuity_notes: str = Field(default="", max_length=6000)
    retention_notes: str = Field(..., min_length=1, max_length=6000)
    transition_notes: str = Field(..., min_length=1, max_length=6000)
    sound_design_notes: str = Field(..., min_length=1, max_length=6000)
    quality_check: PromptQualityCheckPlan = Field(default_factory=PromptQualityCheckPlan)

class VideoPromptPackPlan(BaseModel):
    video_purpose: str | None = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: str | None = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: str | None = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: str | None = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    prompts: list[VideoPromptPlan] = Field(..., min_length=1, max_length=400)

STORY_DEVELOPMENT_SCHEMA = StoryDevelopmentPlan.model_json_schema()
SHOT_BREAKDOWN_SCHEMA = ShotBreakdownPlan.model_json_schema()
VIDEO_PROMPT_PACK_SCHEMA = VideoPromptPackPlan.model_json_schema()

VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS = {
    "retention_notes": "State the shot's retention role and the reason viewers keep watching.",
    "transition_notes": "Describe the motivated edit into the next beat or final hold.",
    "sound_design_notes": "Describe music/SFX as editor guidance; keep voice clear above audio cues.",
}

VIDEO_PROMPT_CREATIVE_NOTE_ALIASES = {
    "retention_notes": ("retention_notes", "retention", "retention_role", "viewer_retention"),
    "transition_notes": ("transition_notes", "transition_pack", "transition", "edit_transition"),
    "sound_design_notes": ("sound_design_notes", "sound_design", "sfx", "sound_cues", "audio_notes"),
}

VIDEO_PROMPT_SHOT_CREATIVE_FIELDS = {
    "retention_notes": "retention_json",
    "transition_notes": "transition_json",
    "sound_design_notes": "sound_design_json",
}

def _humanize_key(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()

def _planning_value_to_text(value, *, level: int = 0) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            item_text = _planning_value_to_text(item, level=level + 1)
            if not item_text:
                continue
            if "\n" in item_text:
                lines.append("- " + item_text.replace("\n", "\n  "))
            else:
                lines.append(f"- {item_text}")
        return "\n".join(lines)
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            item_text = _planning_value_to_text(item, level=level + 1)
            if not item_text:
                continue
            label = _humanize_key(str(key))
            if isinstance(item, (dict, list)):
                lines.append(f"{label}:\n{item_text}")
            else:
                lines.append(f"{label}: {item_text}")
        return "\n\n".join(lines)
    return json.dumps(value, ensure_ascii=False, default=str)

def _normalize_story_scene_payload(scene) -> dict:
    if not isinstance(scene, dict):
        return {"vietnamese_description": _planning_value_to_text(scene)}
    _reject_alias_conflicts(scene, {"english_narration": video_purpose_service.NARRATION_TEXT_FIELD_ALIASES})
    normalized = dict(scene)
    alias_groups = {
        "english_narration": video_purpose_service.NARRATION_TEXT_FIELD_ALIASES,
        "character_appearance": (
            "character_appearance",
            "character_look",
            "appearance",
            "physical_appearance",
            "nhan_vat",
        ),
        "wardrobe_and_sandals": (
            "wardrobe_and_sandals",
            "outfit_and_sandals",
            "clothing_and_sandals",
            "wardrobe",
            "outfit",
            "costume",
        ),
        "subject_motion_by_duration": (
            "subject_motion_by_duration",
            "subject_motion_3s",
            "subject_motion",
            "subject_motion_by_shot_duration",
            "timed_subject_motion",
            "three_second_action",
            "action_3s",
            "movement_3s",
        ),
        "setting_and_lighting": (
            "setting_and_lighting",
            "background_and_lighting",
            "environment_and_lighting",
            "setting",
            "lighting",
        ),
        "detailed_mood": (
            "detailed_mood",
            "mood",
            "emotion",
            "emotional_tone",
            "tone",
        ),
    }
    for target, aliases in alias_groups.items():
        if target not in normalized or normalized[target] is None:
            value = _first_present(normalized, *aliases)
            if value is not None:
                normalized[target] = value
    for field in (
        "title",
        "vietnamese_description",
        "english_narration",
        "character_appearance",
        "wardrobe_and_sandals",
        "subject_motion_by_duration",
        "setting_and_lighting",
        "detailed_mood",
    ):
        if field in normalized:
            normalized[field] = _planning_value_to_text(normalized[field])
    related = _first_present(normalized, "related_characters", "characters", "scene_characters")
    if isinstance(related, list):
        normalized["related_characters"] = [item if isinstance(item, dict) else {"name": _planning_value_to_text(item)} for item in related]
    return normalized

def _story_scene_visual_description(scene: StoryScenePlan) -> str:
    lines = [scene.vietnamese_description.strip()]
    if scene.related_characters:
        lines.append(
            f"Related characters: {json.dumps(_json_safe(scene.related_characters), ensure_ascii=False)}",
        )
    details = [
        ("Character appearance", scene.character_appearance),
        ("Wardrobe and sandals", scene.wardrobe_and_sandals),
        ("Subject motion by shot duration", scene.subject_motion_by_duration),
        ("Setting and lighting", scene.setting_and_lighting),
        ("Detailed emotion/mood", scene.detailed_mood),
    ]
    for label, value in details:
        text = (value or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(line for line in lines if line).strip()

def _normalize_story_development_payload(payload: dict) -> dict:
    payload = _normalize_purpose_metadata_payload(payload)
    _reject_alias_conflicts(
        payload,
        {
            "retention_plan": ("retention_plan", "retention_map", "retention_direction", "viewer_retention"),
            "sound_design_plan": ("sound_design_plan", "sound_design", "audio_plan", "sfx_plan"),
            "scenes": ("scenes", "chapters", "sections"),
        },
    )
    normalized = dict(payload)
    for field in (
        "input_synthesis",
        "story_strategy_vi",
        "story_strategy",
        "continuity_bible_vi",
        "continuity_bible",
        "detailed_script_vi",
        "detailed_script",
    ):
        if field in normalized:
            normalized[field] = _planning_value_to_text(normalized[field])
    normalized["retention_plan"] = _normalize_retention_payload(
        _first_present(normalized, "retention_plan", "retention_map", "retention_direction", "viewer_retention"),
        fallback=_planning_value_to_text(_first_present(normalized, "story_strategy_vi", "story_strategy", "detailed_script_vi")),
    )
    normalized["sound_design_plan"] = _normalize_sound_payload(
        _first_present(normalized, "sound_design_plan", "sound_design", "audio_plan", "sfx_plan"),
        has_narration=True,
        fallback=_planning_value_to_text(_first_present(normalized, "story_strategy_vi", "story_strategy")),
    )
    for target, aliases in {
        "episode_cast": ("episode_cast", "cast", "selected_characters"),
        "episode_only_guests": ("episode_only_guests", "episode_guests", "guest_characters"),
        "new_character_proposals": ("new_character_proposals", "character_proposals", "proposed_characters"),
    }.items():
        value = _first_present(normalized, *aliases)
        if isinstance(value, list):
            normalized[target] = [item if isinstance(item, dict) else {"name": _planning_value_to_text(item)} for item in value]
        else:
            normalized[target] = []
    scenes = normalized.get("scenes")
    if isinstance(scenes, list):
        normalized["scenes"] = [_normalize_story_scene_payload(scene) for scene in scenes]
    return normalized

def _bilingual_planning_text(vietnamese_text: str | None, reference_text: str | None, *, reference_label: str) -> str:
    vietnamese = (vietnamese_text or "").strip()
    reference = (reference_text or "").strip()
    if vietnamese and reference:
        return f"Bản tiếng Việt:\n{vietnamese}\n\n{reference_label}:\n{reference}"
    if vietnamese:
        return f"Bản tiếng Việt:\n{vietnamese}"
    return reference

def _video_language_reference_label(project: DBVideoProject) -> str:
    return f"Bản {video_language.video_language_label(project.target_language)} dùng cho video"

def _payload_type_summary(payload: dict) -> dict[str, str]:
    return {str(key): value.__class__.__name__ for key, value in payload.items()}

def _canonical_mapping_value(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)

def _raise_mapping_error(message: str, *, error_code: str, validation_errors: list[dict[str, object]]) -> None:
    exc = VideoPlanningValidationError(message)
    exc.error_code = error_code
    exc.validation_errors = validation_errors
    raise exc

def _reject_alias_conflict(payload: dict, canonical_field: str, aliases: tuple[str, ...]) -> None:
    if not isinstance(payload, dict):
        return
    present = [(key, payload[key]) for key in aliases if key in payload and _has_planning_content(payload[key])]
    if len(present) <= 1:
        return
    values = {_canonical_mapping_value(value) for _, value in present}
    if len(values) <= 1:
        return
    keys = [key for key, _ in present]
    _raise_mapping_error(
        f"AI trả về nhiều alias mâu thuẫn cho field `{canonical_field}`: {', '.join(keys)}.",
        error_code="AI_VIDEO_MAPPING_ALIAS_CONFLICT",
        validation_errors=[
            {
                "loc": canonical_field,
                "msg": "Alias conflict",
                "keys": keys,
                "type_summary": {key: value.__class__.__name__ for key, value in present},
            }
        ],
    )

def _reject_alias_conflicts(payload: dict, alias_map: dict[str, tuple[str, ...]]) -> None:
    for canonical_field, aliases in alias_map.items():
        _reject_alias_conflict(payload, canonical_field, aliases)

def _first_present(payload: dict, *keys: str):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None

def _has_planning_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float, bool)):
        return True
    if isinstance(value, list):
        return any(_has_planning_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_planning_content(item) for item in value.values())
    return bool(_planning_value_to_text(value))

def _has_alias_content(payload: dict, *keys: str) -> bool:
    return _has_planning_content(_first_present(payload, *keys))

def _normalize_purpose_metadata_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    _reject_alias_conflicts(
        payload,
        {
            "video_purpose": video_purpose_service.PURPOSE_FIELD_ALIASES,
            "dialogue_mode": video_purpose_service.DIALOGUE_MODE_FIELD_ALIASES,
            "narration_density": video_purpose_service.NARRATION_DENSITY_FIELD_ALIASES,
            "call_to_action_style": video_purpose_service.CTA_STYLE_FIELD_ALIASES,
        },
    )
    normalized = dict(payload)
    purpose_value = _first_present(normalized, *video_purpose_service.PURPOSE_FIELD_ALIASES)
    if purpose_value is not None:
        normalized["video_purpose"] = video_purpose_service.normalize_video_purpose(_planning_value_to_text(purpose_value))
    dialogue_value = _first_present(normalized, *video_purpose_service.DIALOGUE_MODE_FIELD_ALIASES)
    if dialogue_value is not None:
        normalized["dialogue_mode"] = video_purpose_service.normalize_dialogue_mode(
            _planning_value_to_text(dialogue_value),
            purpose=normalized.get("video_purpose"),
        )
    density_value = _first_present(normalized, *video_purpose_service.NARRATION_DENSITY_FIELD_ALIASES)
    if density_value is not None:
        normalized["narration_density"] = video_purpose_service.normalize_narration_density(
            _planning_value_to_text(density_value),
            purpose=normalized.get("video_purpose"),
        )
    cta_value = _first_present(normalized, *video_purpose_service.CTA_STYLE_FIELD_ALIASES)
    if cta_value is not None:
        normalized["call_to_action_style"] = video_purpose_service.normalize_call_to_action_style(
            _planning_value_to_text(cta_value),
            purpose=normalized.get("video_purpose"),
        )
    return normalized

def _is_video_prompt_creative_default(field: str, value: str | None) -> bool:
    return (value or "").strip() == VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS.get(field, "")

def _has_video_prompt_creative_note(
    raw_item: dict,
    item: VideoPromptPlan,
    shot: DBVideoShot | None,
    field: str,
) -> bool:
    if _has_alias_content(raw_item, *VIDEO_PROMPT_CREATIVE_NOTE_ALIASES[field]):
        return True
    item_value = _planning_value_to_text(getattr(item, field, ""))
    if item_value:
        return True
    shot_field = VIDEO_PROMPT_SHOT_CREATIVE_FIELDS[field]
    return bool(shot is not None and _has_planning_content(getattr(shot, shot_field, None)))

def _missing_alias_fields(payload, field_aliases: dict[str, tuple[str, ...]], *, prefix: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{prefix}.{field}" for field in field_aliases]
    return [f"{prefix}.{field}" for field, aliases in field_aliases.items() if not _has_alias_content(payload, *aliases)]

def _raise_missing_required_output(label: str, missing: list[str]) -> None:
    unique_missing = list(dict.fromkeys(missing))
    if not unique_missing:
        return
    exc = VideoPlanningValidationError(
        f"AI trả về {label} thiếu field bắt buộc: {', '.join(unique_missing)}."
    )
    exc.error_code = "AI_VIDEO_MAPPING_REQUIRED_FIELD_MISSING"
    exc.validation_errors = [{"loc": field, "msg": "Thiếu field bắt buộc"} for field in unique_missing]
    raise exc

def _validation_errors_from_exception(exc: BaseException) -> object:
    return getattr(exc, "validation_errors", [{"msg": str(exc)}])

RETENTION_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "hook_0_2s": ("hook_0_2s", "hook", "cold_open", "first_two_seconds_hook", "retention_hook"),
    "viewer_question": ("viewer_question", "audience_question", "question", "open_question"),
    "curiosity_gap": ("curiosity_gap", "open_loop", "mystery", "retention_gap"),
    "beat_curve": ("beat_curve", "retention_beats", "beats", "timeline_beats", "retention_timeline"),
    "pattern_interrupts": ("pattern_interrupts", "interrupts", "visual_interrupts", "rhythm_changes"),
    "payoff_plan": ("payoff_plan", "payoff", "ending_payoff", "resolution"),
    "dropoff_risks": ("dropoff_risks", "drop_off_risks", "retention_risks", "risks"),
}

TRANSITION_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "transition_type": ("transition_type", "type", "transition", "edit_transition"),
    "trigger": ("trigger", "transition_trigger", "cut_trigger"),
    "timing": ("timing", "time", "cut_timing"),
    "edit_reason": ("edit_reason", "cut_reason", "reason", "purpose"),
    "transition_sfx": ("transition_sfx", "sfx", "sound_effect", "sound_cue"),
    "continuity_risk": ("continuity_risk", "risk", "continuity_note"),
}

SOUND_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "music_mood": ("music_mood", "music", "background_music_mood", "bgm_mood"),
    "energy_curve": ("energy_curve", "music_energy_curve", "audio_energy_curve"),
    "ambience_bed": ("ambience_bed", "ambience", "room_tone", "ambient_sound"),
    "sound_cues": ("sound_cues", "sfx_cues", "sfx", "sound_effects", "audio_cues"),
    "silence_drops": ("silence_drops", "silence_drop", "dramatic_silence"),
    "mixing_notes": ("mixing_notes", "mix_notes", "mixing", "voice_mix_note"),
}
SHOT_SOUND_FALLBACK_FIELDS = frozenset({"silence_drops"})

SERIES_BIBLE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "character_bible": ("character_bible", "characters", "character_profile", "main_character", "nhan_vat"),
    "world_bible": ("world_bible", "world", "setting", "setting_bible", "boi_canh"),
    "style_bible": ("style_bible", "style", "visual_style", "art_direction"),
    "continuity_rules": ("continuity_rules", "continuity", "rules", "canon_rules"),
    "negative_rules": ("negative_rules", "negative_prompt", "donts", "avoid"),
    "previous_episode_summary": ("previous_episode_summary", "latest_summary", "series_summary", "recap"),
}

def normalize_series_bible_payload(payload: dict, *, has_character_profiles: bool = False) -> dict[str, str]:
    """Normalize Codex-created Series Bible payload with strict alias conflict checks."""
    if not isinstance(payload, dict):
        _raise_mapping_error(
            "AI trả về Series Bible không phải object JSON.",
            error_code="AI_VIDEO_MAPPING_TYPE_INVALID",
            validation_errors=[{"loc": "series_bible", "msg": "Expected object", "actual_type": payload.__class__.__name__}],
        )
    _reject_alias_conflicts(payload, SERIES_BIBLE_FIELD_ALIASES)
    normalized = {
        field: _planning_value_to_text(_first_present(payload, *aliases))
        for field, aliases in SERIES_BIBLE_FIELD_ALIASES.items()
    }
    missing_core = [field for field in ("world_bible", "style_bible") if not normalized[field].strip()]
    if not normalized["character_bible"].strip() and not has_character_profiles:
        missing_core.insert(0, "character_bible")
    if missing_core:
        _raise_mapping_error(
            "AI trả về Series Bible thiếu nhân vật, bối cảnh hoặc style cốt lõi.",
            error_code="AI_VIDEO_MAPPING_REQUIRED_FIELD_MISSING",
            validation_errors=[{"loc": f"series_bible.{field}", "msg": "Thiếu field cốt lõi"} for field in missing_core],
        )
    return normalized

def _missing_retention_output(value, *, prefix: str) -> list[str]:
    return _missing_alias_fields(value, RETENTION_FIELD_ALIASES, prefix=prefix)

def _missing_transition_output(value, *, prefix: str) -> list[str]:
    return _missing_alias_fields(value, TRANSITION_FIELD_ALIASES, prefix=prefix)

def _missing_sound_output(value, *, prefix: str, fallback_fields: frozenset[str] = frozenset()) -> list[str]:
    missing = _missing_alias_fields(value, SOUND_FIELD_ALIASES, prefix=prefix)
    if not fallback_fields or not isinstance(value, dict):
        return missing
    return [field for field in missing if field.rsplit(".", 1)[-1] not in fallback_fields]

def _fallback_sound_output_fields(
    value,
    *,
    prefix: str,
    fallback_fields: frozenset[str] = SHOT_SOUND_FALLBACK_FIELDS,
) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [
        f"{prefix}.{field}"
        for field, aliases in SOUND_FIELD_ALIASES.items()
        if field in fallback_fields and not _has_alias_content(value, *aliases)
    ]

def _raw_items_from_payload(payload: dict | None, *keys: str) -> list:
    if not isinstance(payload, dict):
        return []
    items = _first_present(payload, *keys)
    if isinstance(items, list):
        return items
    scenes = _first_present(payload, "scenes", "chapters", "sections")
    flattened: list = []
    if isinstance(scenes, list):
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            scene_items = _first_present(scene, *keys)
            if isinstance(scene_items, list):
                flattened.extend(scene_items)
    return flattened

def _validate_story_creative_output(raw_plan: dict, plan: StoryDevelopmentPlan, project: DBVideoProject) -> dict[str, object]:
    missing: list[str] = []
    retention_raw = _first_present(raw_plan, "retention_plan", "retention_map", "retention_direction", "viewer_retention")
    sound_raw = _first_present(raw_plan, "sound_design_plan", "sound_design", "audio_plan", "sfx_plan")
    missing.extend(_missing_retention_output(retention_raw, prefix="retention_plan"))
    missing.extend(_missing_sound_output(sound_raw, prefix="sound_design_plan"))
    retention_quality = _retention_quality_check(plan.retention_plan, project)
    missing.extend(f"retention_plan.{field}" for field in retention_quality.get("missing_fields", []))
    if "beat_exceeds_target_duration" in retention_quality.get("warnings", []):
        missing.append("retention_plan.beat_curve.end_seconds")
    _raise_missing_required_output("creative direction", missing)
    return retention_quality

def _shot_raw_sound_payload(raw_shot: dict):
    sound = _first_present(raw_shot, "sound_design", "sound_design_plan", "audio_plan")
    if sound is not None:
        return sound
    if any(key in raw_shot for key in ("music_mood", "music", "background_music_mood", "energy_curve", "audio_energy_curve", "ambience_bed", "ambience", "sfx", "sound_cues", "silence_drops", "mixing_notes", "mix_notes")):
        return raw_shot
    return None

def _validate_shot_creative_output(raw_plan: dict, plan: ShotBreakdownPlan) -> None:
    raw_shots = _raw_items_from_payload(raw_plan, "shots", "segments", "prompt_segments", "video_segments", "segment_breakdown")
    missing: list[str] = []
    if len(raw_shots) != len(plan.shots):
        missing.append("shots")
    for index, shot in enumerate(plan.shots, start=1):
        raw_shot = raw_shots[index - 1] if index - 1 < len(raw_shots) and isinstance(raw_shots[index - 1], dict) else {}
        prefix = f"shots[{index}]"
        if not _has_alias_content(raw_shot, "retention_role", "segment_role", "beat_role", "role"):
            missing.append(f"{prefix}.retention_role")
        if not _has_alias_content(raw_shot, "open_loop", "curiosity_gap", "viewer_question"):
            missing.append(f"{prefix}.open_loop")
        if not _has_alias_content(raw_shot, "visual_surprise", "pattern_interrupt", "surprise", "visual_hook"):
            missing.append(f"{prefix}.visual_surprise")
        if not _has_alias_content(raw_shot, "cut_reason", "edit_reason", "reason_to_cut"):
            missing.append(f"{prefix}.cut_reason")
        transition_raw = _first_present(raw_shot, "transition_pack", "transition", "edit_transition", "next_transition")
        missing.extend(_missing_transition_output(transition_raw, prefix=f"{prefix}.transition_pack"))
        missing.extend(
            _missing_sound_output(
                _shot_raw_sound_payload(raw_shot),
                prefix=f"{prefix}.sound_design",
                fallback_fields=SHOT_SOUND_FALLBACK_FIELDS,
            )
        )
        quality = _shot_retainability_quality(shot, is_first=index == 1, is_final=index == len(plan.shots))
        missing.extend(f"{prefix}.{field}" for field in quality.get("missing_fields", []))
    _raise_missing_required_output("shot breakdown", missing)

def _shot_sound_fallback_fields(raw_plan: dict | None) -> list[str]:
    raw_shots = _raw_items_from_payload(raw_plan or {}, "shots", "segments", "prompt_segments", "video_segments", "segment_breakdown")
    fields: list[str] = []
    for index, raw_shot in enumerate(raw_shots, start=1):
        if not isinstance(raw_shot, dict):
            continue
        fields.extend(
            _fallback_sound_output_fields(
                _shot_raw_sound_payload(raw_shot),
                prefix=f"shots[{index}].sound_design",
            )
        )
    return fields

def _validate_shot_order_output(
    plan: ShotBreakdownPlan,
    *,
    valid_scene_orders: set[int],
    expected_count: int | None,
    first_shot_order: int,
) -> None:
    actual_orders = [shot.shot_order for shot in plan.shots]
    duplicate_orders = sorted({order for order in actual_orders if actual_orders.count(order) > 1})
    missing: list[str] = []
    if expected_count is not None and len(plan.shots) != expected_count:
        _raise_mapping_error(
            f"AI phải tạo đúng {expected_count} shot/segment, hiện nhận {len(plan.shots)}.",
            error_code="AI_VIDEO_MAPPING_COUNT_MISMATCH",
            validation_errors=[{"loc": "shots", "msg": "Count mismatch", "expected": expected_count, "actual": len(plan.shots)}],
        )
    expected_orders = list(range(first_shot_order, first_shot_order + len(plan.shots)))
    local_orders = list(range(1, len(plan.shots) + 1))
    if actual_orders not in (expected_orders, local_orders):
        _raise_mapping_error(
            "AI trả về shot_order không đúng thứ tự liên tục.",
            error_code="AI_VIDEO_MAPPING_ORDER_MISMATCH",
            validation_errors=[{"loc": "shots.shot_order", "msg": "Order mismatch", "expected": expected_orders, "actual": actual_orders}],
        )
    if duplicate_orders:
        missing.append(f"duplicate shot_order: {duplicate_orders}")
    invalid_scenes = sorted({shot.scene_order for shot in plan.shots if shot.scene_order not in valid_scene_orders})
    if invalid_scenes:
        missing.append(f"scene_order không tồn tại: {invalid_scenes}")
    if missing:
        _raise_mapping_error(
            "AI trả về shot breakdown sai scene/order.",
            error_code="AI_VIDEO_MAPPING_ORDER_MISMATCH",
            validation_errors=[{"loc": "shots", "msg": item} for item in missing],
        )

def _validate_prompt_pack_output(raw_pack: dict, pack: VideoPromptPackPlan, shots: list[DBVideoShot], project: DBVideoProject) -> dict[int, dict[str, object]]:
    raw_prompts = _raw_items_from_payload(raw_pack, *VIDEO_PROMPT_LIST_KEYS)
    global_negative_prompt = _first_present(raw_pack, "negative_prompt_global", "global_negative_prompt", "negative_prompt")
    global_continuity = _first_present(
        raw_pack,
        "global_continuity",
        "global_continuity_bible",
        "continuity_bible",
        "continuity_notes",
    )
    shots_by_order = {shot.shot_order: shot for shot in shots}
    missing: list[str] = []
    quality_by_order: dict[int, dict[str, object]] = {}
    expected_orders = [shot.shot_order for shot in shots]
    actual_orders = [item.shot_order for item in pack.prompts]
    duplicate_orders = sorted({order for order in actual_orders if actual_orders.count(order) > 1})
    if len(pack.prompts) != len(shots):
        _raise_mapping_error(
            f"AI phải tạo đúng {len(shots)} prompt, hiện nhận {len(pack.prompts)}.",
            error_code="AI_VIDEO_MAPPING_COUNT_MISMATCH",
            validation_errors=[{"loc": "prompts", "msg": "Count mismatch", "expected": len(shots), "actual": len(pack.prompts)}],
        )
    if duplicate_orders or actual_orders != expected_orders:
        _raise_mapping_error(
            "AI trả về prompt pack sai shot_order hoặc sai thứ tự.",
            error_code="AI_VIDEO_MAPPING_ORDER_MISMATCH",
            validation_errors=[
                {
                    "loc": "prompts.shot_order",
                    "msg": "Order mismatch" if not duplicate_orders else "Duplicate order",
                    "expected": expected_orders,
                    "actual": actual_orders,
                    "duplicates": duplicate_orders,
                }
            ],
        )
    if len(raw_prompts) != len(pack.prompts):
        missing.append("prompts")
    for index, item in enumerate(pack.prompts, start=1):
        raw_item = raw_prompts[index - 1] if index - 1 < len(raw_prompts) and isinstance(raw_prompts[index - 1], dict) else {}
        prefix = f"prompts[{index}]"
        shot = shots_by_order.get(item.shot_order)
        if not _has_alias_content(raw_item, "prompt", "video_prompt", "main_prompt", "main_video_prompt", "prompt_text", "generation_prompt", "video_generation_prompt", "segment_prompt", "segment_video_prompt", "clip_prompt", "full_prompt", "positive_prompt", "detailed_prompt", "detailed_video_prompt", "veo_prompt", "prompt_body", "text"):
            missing.append(f"{prefix}.prompt")
        if not _has_alias_content(raw_item, "prompt_explanation_vi", "prompt_review_vi", "prompt_translation_vi", "vietnamese_prompt_explanation", "vietnamese_explanation", "explanation_vi", "review_vi", "translation_vi", "user_explanation_vi", "ban_giai_thich_tieng_viet", "vi_description", "vietnamese_description", "description_vi", "description_vietnamese", "segment_description_vi", "review_description_vi"):
            missing.append(f"{prefix}.prompt_explanation_vi")
        if not _has_alias_content(raw_item, "negative_prompt", "negative", "negative_prompt_text", "avoid", "avoid_prompt") and not _has_planning_content(global_negative_prompt):
            missing.append(f"{prefix}.negative_prompt")
        if (
            not _has_alias_content(
                raw_item,
                "continuity_notes",
                "continuity",
                "consistency_notes",
                "segment_continuity",
                "visual_continuity",
                "continuity_bible",
                "global_continuity",
            )
            and not _has_planning_content(global_continuity)
            and not _has_planning_content(item.continuity_notes)
        ):
            missing.append(f"{prefix}.continuity_notes")
        for field in VIDEO_PROMPT_CREATIVE_NOTE_ALIASES:
            if not _has_video_prompt_creative_note(raw_item, item, shot, field):
                missing.append(f"{prefix}.{field}")
        duration_seconds = _clamp_shot_duration(item.duration_seconds or (shot.duration_seconds if shot else None), project, shot_order=item.shot_order)
        quality = _quality_check(item, duration_seconds=duration_seconds)
        quality_by_order[item.shot_order] = quality
        if not quality["passed"]:
            missing.extend(f"{prefix}.{field}" for field in quality.get("missing_fields", []))
    _raise_missing_required_output("prompt video", missing)
    return quality_by_order

def _normalize_retention_payload(value, *, fallback: str = "") -> dict[str, object]:
    if not isinstance(value, dict):
        text = _planning_value_to_text(value) or fallback
        return _default_retention_payload(fallback=text)
    _reject_alias_conflicts(value, RETENTION_FIELD_ALIASES)
    normalized = dict(value)
    aliases = {
        "review_vi": ("review_vi", "vietnamese_review", "description_vi", "retention_review_vi"),
        "hook_0_2s": ("hook_0_2s", "hook", "cold_open", "first_two_seconds_hook", "retention_hook"),
        "viewer_question": ("viewer_question", "audience_question", "question", "open_question"),
        "curiosity_gap": ("curiosity_gap", "open_loop", "mystery", "retention_gap"),
        "beat_curve": ("beat_curve", "retention_beats", "beats", "timeline_beats", "retention_timeline"),
        "pattern_interrupts": ("pattern_interrupts", "interrupts", "visual_interrupts", "rhythm_changes"),
        "payoff_plan": ("payoff_plan", "payoff", "ending_payoff", "resolution"),
        "dropoff_risks": ("dropoff_risks", "drop_off_risks", "retention_risks", "risks"),
    }
    default_payload = _default_retention_payload(fallback=fallback)
    for target, keys in aliases.items():
        value_for_target = _first_present(normalized, *keys)
        if value_for_target is None:
            normalized[target] = default_payload[target]
        elif target in {"beat_curve"} and isinstance(value_for_target, list):
            beats: list[dict[str, object]] = []
            for beat in value_for_target:
                if isinstance(beat, dict):
                    beats.append(
                        {
                            "start_seconds": _number_or_default(_first_present(beat, "start_seconds", "start", "from"), None),
                            "end_seconds": _number_or_default(_first_present(beat, "end_seconds", "end", "to"), None),
                            "purpose": _planning_value_to_text(_first_present(beat, "purpose", "role", "beat", "goal")),
                            "viewer_reason": _planning_value_to_text(_first_present(beat, "viewer_reason", "why_watch", "retention_reason")),
                            "pattern_interrupt": _planning_value_to_text(_first_present(beat, "pattern_interrupt", "interrupt", "rhythm_change")),
                            "visual_surprise": _planning_value_to_text(_first_present(beat, "visual_surprise", "surprise", "visual_hook")),
                        }
                    )
                else:
                    beats.append({"purpose": _planning_value_to_text(beat)})
            normalized[target] = beats or default_payload[target]
        elif target in {"pattern_interrupts", "dropoff_risks"}:
            if isinstance(value_for_target, list):
                normalized[target] = [_planning_value_to_text(item) for item in value_for_target if _planning_value_to_text(item)] or default_payload[target]
            else:
                text = _planning_value_to_text(value_for_target)
                normalized[target] = [text] if text else default_payload[target]
        else:
            normalized[target] = _planning_value_to_text(value_for_target) or default_payload[target]
    return normalized

def _normalize_transition_payload(value, *, final: bool = False, fallback: str = "") -> dict[str, object]:
    if not isinstance(value, dict):
        return _default_transition_payload(final=final, fallback=_planning_value_to_text(value) or fallback)
    _reject_alias_conflicts(value, TRANSITION_FIELD_ALIASES)
    normalized = dict(value)
    aliases = {
        "transition_type": ("transition_type", "type", "transition", "edit_transition"),
        "trigger": ("trigger", "transition_trigger", "cut_trigger"),
        "timing": ("timing", "time", "cut_timing"),
        "edit_reason": ("edit_reason", "cut_reason", "reason", "purpose"),
        "transition_sfx": ("transition_sfx", "sfx", "sound_effect", "sound_cue"),
        "continuity_risk": ("continuity_risk", "risk", "continuity_note"),
    }
    default_payload = _default_transition_payload(final=final, fallback=fallback)
    for target, keys in aliases.items():
        raw = _first_present(normalized, *keys)
        normalized[target] = _planning_value_to_text(raw) or default_payload[target]
    return normalized

def _normalize_sound_payload(value, *, has_narration: bool = True, fallback: str = "") -> dict[str, object]:
    def normalize_cues(raw) -> list[dict[str, str]]:
        cues: list[dict[str, str]] = []
        raw_cues = raw if isinstance(raw, list) else ([raw] if raw is not None else [])
        for cue in raw_cues:
            if isinstance(cue, dict):
                cues.append(
                    {
                        "cue_type": _planning_value_to_text(_first_present(cue, "cue_type", "type", "sfx", "sound")),
                        "timing": _planning_value_to_text(_first_present(cue, "timing", "time", "at")),
                        "purpose": _planning_value_to_text(_first_present(cue, "purpose", "reason", "effect")),
                        "mix_note": _planning_value_to_text(_first_present(cue, "mix_note", "mixing", "volume_note")),
                    }
                )
            else:
                text = _planning_value_to_text(cue)
                if text:
                    cues.append({"cue_type": text, "timing": "near the edit point", "purpose": text, "mix_note": "keep below voice"})
        return cues

    if isinstance(value, list):
        default_payload = _default_sound_payload(has_narration=has_narration, fallback=fallback)
        default_payload["sound_cues"] = normalize_cues(value) or default_payload["sound_cues"]
        return default_payload
    if not isinstance(value, dict):
        return _default_sound_payload(has_narration=has_narration, fallback=_planning_value_to_text(value) or fallback)
    _reject_alias_conflicts(value, SOUND_FIELD_ALIASES)
    normalized = dict(value)
    aliases = {
        "review_vi": ("review_vi", "vietnamese_review", "description_vi", "sound_review_vi", "audio_review_vi"),
        "music_mood": ("music_mood", "music", "background_music_mood", "bgm_mood"),
        "energy_curve": ("energy_curve", "music_energy_curve", "audio_energy_curve"),
        "ambience_bed": ("ambience_bed", "ambience", "room_tone", "ambient_sound"),
        "sound_cues": ("sound_cues", "sfx_cues", "sfx", "sound_effects", "audio_cues"),
        "silence_drops": ("silence_drops", "silence_drop", "dramatic_silence"),
        "mixing_notes": ("mixing_notes", "mix_notes", "mixing", "voice_mix_note"),
    }
    default_payload = _default_sound_payload(has_narration=has_narration, fallback=fallback)
    for target, keys in aliases.items():
        raw = _first_present(normalized, *keys)
        if target == "sound_cues":
            cues = normalize_cues(raw)
            normalized[target] = cues or default_payload[target]
        elif target == "silence_drops":
            if isinstance(raw, list):
                normalized[target] = [_planning_value_to_text(item) for item in raw if _planning_value_to_text(item)] or default_payload[target]
            else:
                text = _planning_value_to_text(raw)
                normalized[target] = [text] if text else default_payload[target]
        else:
            normalized[target] = _planning_value_to_text(raw) or default_payload[target]
    return normalized

def _number_or_default(value, default: int | float | None) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match:
            parsed = float(match.group(0))
            return int(parsed) if parsed.is_integer() else parsed
    return default

def _normalize_micro_scene_payload(item, *, index: int) -> dict:
    if not isinstance(item, dict):
        text = _planning_value_to_text(item)
        return {
            "order": index,
            "start_seconds": 0,
            "end_seconds": 0,
            "description_vi": text,
            "visual_action": text,
            "camera_note": "",
            "continuity_note": "",
            "visible_characters": [],
        }
    description = _planning_value_to_text(
        _first_present(item, "description_vi", "vietnamese_description", "segment_description_vi", "description", "summary", "beat")
    )
    visual_action = _planning_value_to_text(
        _first_present(item, "visual_action", "action", "primary_action", "subject_action", "subject_motion", "visual")
    ) or description
    visible = _first_present(item, "visible_characters", "characters", "foreground_characters")
    return {
        "order": int(_number_or_default(_first_present(item, "order", "index", "scene_order", "beat_order", "micro_scene_order"), index) or index),
        "start_seconds": float(_number_or_default(_first_present(item, "start_seconds", "start", "from_seconds", "from"), 0) or 0),
        "end_seconds": float(_number_or_default(_first_present(item, "end_seconds", "end", "to_seconds", "to"), 0) or 0),
        "description_vi": description,
        "visual_action": visual_action,
        "camera_note": _planning_value_to_text(_first_present(item, "camera_note", "camera", "camera_motion", "camera_movement")),
        "continuity_note": _planning_value_to_text(_first_present(item, "continuity_note", "continuity", "continuity_notes")),
        "visible_characters": [
            value if isinstance(value, dict) else {"name": _planning_value_to_text(value)}
            for value in (visible if isinstance(visible, list) else [])
        ],
    }

def _parse_timeline_micro_scenes(text: str) -> list[dict]:
    source = (text or "").strip()
    if not source:
        return []
    pattern = re.compile(
        r"(?P<start>\d+(?:\.\d+)?)\s*(?:-|\u2013|to)\s*(?P<end>\d+(?:\.\d+)?)\s*s",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(source))
    if not matches:
        return []
    scenes: list[dict] = []
    for index, match in enumerate(matches, start=1):
        next_start = matches[index].start() if index < len(matches) else len(source)
        description = source[match.end():next_start].strip(" :;,.\n\t")
        scenes.append(
            {
                "order": index,
                "start_seconds": float(match.group("start")),
                "end_seconds": float(match.group("end")),
                "description_vi": description,
                "visual_action": description,
                "camera_note": "",
                "continuity_note": "",
                "visible_characters": [],
            }
        )
    return scenes

def _normalize_micro_scenes_from_shot(shot: dict) -> list[dict]:
    raw_micro_scenes = _first_present(shot, "micro_scenes", "microScenes", "micro_scene_timeline", "timeline_beats")
    if raw_micro_scenes is None:
        raw_micro_scenes = _first_present(shot, "beats", "timeline")
    if raw_micro_scenes is None and isinstance(shot.get("scenes"), list):
        raw_micro_scenes = shot.get("scenes")
    if isinstance(raw_micro_scenes, list):
        return [_normalize_micro_scene_payload(item, index=index) for index, item in enumerate(raw_micro_scenes, start=1)]
    text = _planning_value_to_text(
        raw_micro_scenes
        if raw_micro_scenes is not None
        else _first_present(shot, "vietnamese_description", "segment_description_vi", "subject_motion", "description")
    )
    return _parse_timeline_micro_scenes(text)

def _normalize_shot_payload(shot, *, index: int, dialogue_mode: str | None = None) -> dict:
    if not isinstance(shot, dict):
        return {
            "scene_order": 1,
            "shot_order": index,
            "vietnamese_description": _planning_value_to_text(shot),
        }
    _reject_alias_conflicts(
        shot,
        {
            "shot_order": ("shot_order", "shot_number", "shot", "shotIndex", "segment_order", "segment_number", "segment", "segmentIndex", "order"),
            "primary_action": ("primary_action", "main_action", "action", "subject_action", "segment_action"),
            "english_narration": video_purpose_service.NARRATION_TEXT_FIELD_ALIASES,
        },
    )
    visual_prompt = _planning_value_to_text(_first_present(shot, "visual_prompt", "prompt", "image_prompt"))
    framing = _planning_value_to_text(_first_present(shot, "framing", "frame", "composition_description"))
    primary_action = _planning_value_to_text(
        _first_present(shot, "primary_action", "main_action", "action", "subject_action", "segment_action")
    )
    composition = _planning_value_to_text(_first_present(shot, "composition", "visual_composition"))
    if not composition and visual_prompt:
        composition = visual_prompt
    visible_characters = _first_present(shot, "visible_characters", "foreground_characters", "characters_in_frame")
    normalized_visible_characters = [
        item if isinstance(item, dict) else {"name": _planning_value_to_text(item)}
        for item in (visible_characters if isinstance(visible_characters, list) else [])
    ]
    narration = _planning_value_to_text(
        _first_present(shot, *video_purpose_service.NARRATION_TEXT_FIELD_ALIASES)
    )
    vietnamese_description = _planning_value_to_text(
        _first_present(
            shot,
            "vietnamese_description",
            "description_vi",
            "description_vietnamese",
            "user_description",
            "summary_vi",
            "vietnamese_summary",
            "segment_description_vi",
            "segment_description",
            "review_description_vi",
            "micro_scenes",
            "micro_scene_timeline",
            "timeline",
            "beats",
        )
    )
    environment_motion = _planning_value_to_text(
        _first_present(shot, "environment_motion", "background_motion", "environment_movement")
    )
    speech_cues = video_speech.normalize_speech_cues(
        _first_present(shot, "speech_cues", "dialogue_lines", "voice_lines", "spoken_lines"),
        narration=narration,
        dialogue_mode=dialogue_mode,
        visible_characters=normalized_visible_characters,
        shot_context="; ".join(part for part in (vietnamese_description, primary_action, environment_motion) if part),
    )

    return {
        "scene_order": int(_number_or_default(_first_present(shot, "scene_order", "scene_number", "scene", "sceneIndex", "parent_scene_order"), 1)),
        "shot_order": int(
            _number_or_default(
                _first_present(shot, "shot_order", "shot_number", "shot", "shotIndex", "segment_order", "segment_number", "segment", "segmentIndex", "order"),
                index,
            )
        ),
        "duration_seconds": _number_or_default(
            _first_present(shot, "duration_seconds", "duration", "seconds", "usable_duration_seconds", "timeline_duration_seconds", "segment_duration_seconds"),
            None,
        ),
        "vietnamese_description": vietnamese_description,
        "english_narration": narration,
        "primary_action": primary_action or visual_prompt,
        "purpose": _planning_value_to_text(_first_present(shot, "purpose", "goal", "story_purpose", "segment_purpose", "objective")),
        "shot_type": _planning_value_to_text(_first_present(shot, "shot_type", "type", "camera_shot", "segment_type")),
        "camera_angle": _planning_value_to_text(_first_present(shot, "camera_angle", "angle")),
        "framing": framing,
        "composition": composition,
        "camera_motion": _planning_value_to_text(_first_present(shot, "camera_motion", "camera_movement", "movement")),
        "subject_motion": _planning_value_to_text(_first_present(shot, "subject_motion", "character_motion", "subject_movement")),
        "environment_motion": environment_motion,
        "transition_to_next": _planning_value_to_text(
            _first_present(shot, "transition_to_next", "transition", "next_transition")
        ),
        "retention_role": _planning_value_to_text(_first_present(shot, "retention_role", "segment_role", "beat_role", "role")),
        "open_loop": _planning_value_to_text(_first_present(shot, "open_loop", "curiosity_gap", "viewer_question")),
        "visual_surprise": _planning_value_to_text(_first_present(shot, "visual_surprise", "pattern_interrupt", "surprise", "visual_hook")),
        "cut_reason": _planning_value_to_text(_first_present(shot, "cut_reason", "edit_reason", "reason_to_cut")),
        "visible_characters": normalized_visible_characters,
        "speech_cues": speech_cues,
        "transition_pack": _normalize_transition_payload(
            _first_present(shot, "transition_pack", "transition", "edit_transition", "next_transition"),
            final=False,
            fallback=_planning_value_to_text(_first_present(shot, "transition_to_next", "transition", "next_transition")),
        ),
        "sound_design": _normalize_sound_payload(
            _first_present(shot, "sound_design", "sound_design_plan", "audio_plan", "sfx", "sound_cues"),
            has_narration=bool(_planning_value_to_text(_first_present(shot, *video_purpose_service.NARRATION_TEXT_FIELD_ALIASES))),
            fallback=_planning_value_to_text(_first_present(shot, "transition_to_next", "transition", "next_transition")),
        ),
        "micro_scenes": _normalize_micro_scenes_from_shot(shot),
    }

def _normalize_shot_breakdown_payload(payload: dict, *, dialogue_mode: str | None = None) -> dict:
    payload = _normalize_purpose_metadata_payload(payload)
    effective_dialogue_mode = dialogue_mode or _planning_value_to_text(payload.get("dialogue_mode")) or None
    _reject_alias_conflict(payload, "shots", ("shots", "segments", "prompt_segments", "video_segments", "segment_breakdown"))
    shots = _first_present(payload, "shots", "segments", "prompt_segments", "video_segments", "segment_breakdown")
    if not isinstance(shots, list):
        scenes = payload.get("scenes")
        if isinstance(scenes, list):
            flattened: list[dict] = []
            for scene_index, scene in enumerate(scenes, start=1):
                if not isinstance(scene, dict):
                    continue
                scene_shots = _first_present(scene, "shots", "segments", "prompt_segments", "video_segments")
                if not isinstance(scene_shots, list):
                    continue
                for shot in scene_shots:
                    shot_payload = dict(shot) if isinstance(shot, dict) else {"vietnamese_description": shot}
                    shot_payload.setdefault("scene_order", scene.get("scene_order") or scene.get("scene_number") or scene_index)
                    flattened.append(shot_payload)
            shots = flattened
        else:
            shots = []
    normalized = dict(payload)
    normalized_shots: list[dict] = []
    for index, shot in enumerate(shots, start=1):
        normalized_shot = _normalize_shot_payload(shot, index=index, dialogue_mode=effective_dialogue_mode)
        # Shot breakdown rows are persisted in list order below. Treat list order as
        # canonical so local scene indexes, zero-based indexes, or offset indexes
        # from the AI do not fail mapping before the backend assigns DB order.
        normalized_shot["shot_order"] = index
        normalized_shots.append(normalized_shot)
    normalized["shots"] = normalized_shots
    return normalized

def _extract_labeled_fragment(text: str, *labels: str) -> str:
    if not text:
        return ""
    label_pattern = "|".join(re.escape(label) for label in labels)
    known_labels = [
        "Subject and action",
        "Shot type",
        "Camera angle",
        "Framing",
        "Composition",
        "Camera movement",
        "Subject motion",
        "Environment motion",
        "Lighting",
        "Mood",
        "Start frame",
        "End frame",
        "Continuity notes",
    ]
    stop_pattern = "|".join(re.escape(label) for label in known_labels)
    match = re.search(
        rf"(?:{label_pattern})\s*:\s*(.*?)(?=(?:{stop_pattern})\s*:|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip(" .\n\t")

def _fallback_prompt_explanation_vi(prompt: str, fallback_detail: str = "") -> str:
    source = (fallback_detail or prompt or "").strip()
    if not source:
        return "Prompt này tạo một đoạn video theo thông tin segment đã duyệt, giữ đúng nhân vật, hành động, camera, ánh sáng, mood và continuity."
    source = re.sub(r"\s+", " ", source)[:900]
    return f"Prompt này yêu cầu tạo video theo nội dung sau để người dùng dễ duyệt: {source}"

def _bounded_prompt_field(value: str, max_length: int, fallback: str = "") -> str:
    text = (value or fallback or "").strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip(" ,.;:\n\t")

_VIDEO_RENDER_TEXT_CUE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\s*,?\s*(?:and\s+)?leave (?:a\s+)?clean (?:space\s+(?:at|in)\s+the\s+)?(?:lower[-\s]?frame|lower|caption|subtitle)[^.]*subtitles?[^.]*\.",
            re.IGNORECASE,
        ),
        ".",
    ),
    (
        re.compile(
            r"\s*,?\s*with (?:a\s+)?clean (?:space\s+(?:at|in)\s+the\s+)?(?:lower[-\s]?frame|lower|caption|subtitle)[^.]*subtitles?[^.]*\.",
            re.IGNORECASE,
        ),
        ".",
    ),
    (
        re.compile(
            r"\bLeave clean lower space for yellow karaoke subtitles added later; do not burn subtitles into the generated video\.",
            re.IGNORECASE,
        ),
        "Keep the lower frame visually uncluttered; do not render subtitles, captions, karaoke lyrics, or text overlays.",
    ),
    (
        re.compile(
            r"\bViewer-facing narration, speech, subtitle area, and any on-screen text must be natural [^.]*\.",
            re.IGNORECASE,
        ),
        "Narration and subtitles are handled after video generation; do not render readable text in the video.",
    ),
    (
        re.compile(r"\byellow\s+karaoke\s+subtitle[s]?\s+added\s+(?:during|in|at)\s+render\b", re.IGNORECASE),
        "post-render subtitle track",
    ),
)

_VIDEO_RENDER_3D_PROMPT_RULE = (
    "Visual style rule: generate high-quality stylized 3D cinematic animation with dimensional characters, "
    "volumetric lighting, depth, textured materials, parallax, and real camera movement; if the source is manga, "
    "webtoon, illustration, image, or another 2D reference, translate it into a 3D animated video look, not a "
    "flat/static image."
)

_VIDEO_RENDER_3D_NEGATIVE_RULE = (
    "no 2D illustration, no flat drawing, no flat comic panel, no static image, no image prompt, "
    "no storyboard frame, no line-art-only render"
)

def _render_safe_video_prompt_text(prompt: str) -> str:
    safe = str(prompt or "").strip()
    if not safe:
        return ""
    for pattern, replacement in _VIDEO_RENDER_TEXT_CUE_REPLACEMENTS:
        safe = pattern.sub(replacement, safe)
    safe = re.sub(r"[ \t]+([.,;:])", r"\1", safe)
    safe = re.sub(r"(?:\.\s*){2,}", ". ", safe)
    safe = re.sub(r"\s+", " ", safe).strip()
    text_block_rule = "Do not render subtitles, captions, karaoke lyrics, text overlays, letters, words, UI text, logos, or watermarks in the video."
    if text_block_rule.casefold() not in safe.casefold():
        safe = f"{safe} {text_block_rule}".strip()
    if _VIDEO_RENDER_3D_PROMPT_RULE.casefold() not in safe.casefold():
        safe = f"{safe} {_VIDEO_RENDER_3D_PROMPT_RULE}".strip()
    return safe

def _render_safe_video_negative_prompt_text(negative_prompt: str) -> str:
    base = _bounded_prompt_field(negative_prompt, 6000)
    required_parts = [
        "no subtitles, no captions, no text overlays, no letters, no words, no UI text",
        _VIDEO_RENDER_3D_NEGATIVE_RULE,
    ]
    parts = [base] if base else []
    for required in required_parts:
        if required.casefold() not in base.casefold():
            parts.append(required)
    return _bounded_prompt_field(", ".join(part for part in parts if part), 6000)

def _normalize_video_prompt_payload(item, *, index: int, global_negative_prompt: str = "", global_continuity: str = "") -> dict:
    if not isinstance(item, dict):
        prompt = _planning_value_to_text(item)
        return {
            "shot_order": index,
            "prompt": _bounded_prompt_field(_render_safe_video_prompt_text(prompt), 20000),
            "prompt_explanation_vi": _fallback_prompt_explanation_vi(prompt),
            "negative_prompt": _render_safe_video_negative_prompt_text(global_negative_prompt),
            "continuity_notes": global_continuity,
            "retention_notes": VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["retention_notes"],
            "transition_notes": VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["transition_notes"],
            "sound_design_notes": VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["sound_design_notes"],
        }
    _reject_alias_conflicts(
        item,
        {
            "prompt": (
                "prompt",
                "video_prompt",
                "main_prompt",
                "main_video_prompt",
                "prompt_text",
                "generation_prompt",
                "video_generation_prompt",
                "segment_prompt",
                "segment_video_prompt",
                "clip_prompt",
                "full_prompt",
                "positive_prompt",
                "detailed_prompt",
                "detailed_video_prompt",
                "veo_prompt",
                "prompt_body",
                "text",
            ),
            "shot_order": ("shot_order", "shot_number", "shot", "shotIndex", "segment_order", "segment_number", "segment", "segmentIndex", "order"),
            "continuity_notes": ("continuity_notes", "continuity", "consistency_notes", "segment_continuity", "visual_continuity", "continuity_bible", "global_continuity"),
        },
    )
    prompt = _planning_value_to_text(
        _first_present(
            item,
            "prompt",
            "video_prompt",
            "main_prompt",
            "main_video_prompt",
            "prompt_text",
            "generation_prompt",
            "video_generation_prompt",
            "segment_prompt",
            "segment_video_prompt",
            "clip_prompt",
            "full_prompt",
            "positive_prompt",
            "detailed_prompt",
            "detailed_video_prompt",
            "veo_prompt",
            "prompt_body",
            "text",
        )
    ) or _planning_value_to_text(
        _first_present(item, "segment_description", "description", "visual_description", "scene_description")
    )
    negative_prompt = _planning_value_to_text(
        _first_present(item, "negative_prompt", "negative", "negative_prompt_text", "avoid", "avoid_prompt")
    ) or global_negative_prompt
    prompt_explanation_vi = _planning_value_to_text(
        _first_present(
            item,
            "prompt_explanation_vi",
            "prompt_review_vi",
            "prompt_translation_vi",
            "vietnamese_prompt_explanation",
            "vietnamese_explanation",
            "explanation_vi",
            "review_vi",
            "translation_vi",
            "user_explanation_vi",
            "ban_giai_thich_tieng_viet",
            "vi_description",
            "vietnamese_description",
            "description_vi",
            "description_vietnamese",
            "segment_description_vi",
            "review_description_vi",
        )
    )
    continuity_notes = _planning_value_to_text(
        _first_present(
            item,
            "continuity_notes",
            "continuity",
            "consistency_notes",
            "segment_continuity",
            "visual_continuity",
            "continuity_bible",
            "global_continuity",
        )
    ) or global_continuity

    shot_type = _planning_value_to_text(_first_present(item, "shot_type", "type", "segment_type", "clip_type")) or _extract_labeled_fragment(prompt, "Shot type")
    camera_angle = _planning_value_to_text(_first_present(item, "camera_angle", "angle")) or _extract_labeled_fragment(prompt, "Camera angle")
    framing = _planning_value_to_text(_first_present(item, "framing", "frame")) or _extract_labeled_fragment(prompt, "Framing")
    composition = _planning_value_to_text(_first_present(item, "composition", "visual_composition", "visual_layout")) or _extract_labeled_fragment(prompt, "Composition")
    camera_motion = _planning_value_to_text(_first_present(item, "camera_motion", "camera_movement", "camera_move", "movement")) or _extract_labeled_fragment(prompt, "Camera movement")
    subject_motion = _planning_value_to_text(_first_present(item, "subject_motion", "subject_movement", "character_motion")) or _extract_labeled_fragment(prompt, "Subject motion")
    environment_motion = _planning_value_to_text(_first_present(item, "environment_motion", "environment_movement", "background_motion")) or _extract_labeled_fragment(prompt, "Environment motion")
    start_frame = _planning_value_to_text(_first_present(item, "start_frame", "first_frame", "opening_frame", "initial_frame", "start_frame_description")) or _extract_labeled_fragment(prompt, "Start frame")
    end_frame = _planning_value_to_text(_first_present(item, "end_frame", "last_frame", "final_frame", "ending_frame", "end_frame_description")) or _extract_labeled_fragment(prompt, "End frame")
    lighting = _planning_value_to_text(_first_present(item, "lighting", "light")) or _extract_labeled_fragment(prompt, "Lighting")
    mood = _planning_value_to_text(_first_present(item, "mood", "tone")) or _extract_labeled_fragment(prompt, "Mood")

    fallback_detail = prompt[:600] if prompt else "See the main prompt for this shot."
    prompt_explanation_vi = prompt_explanation_vi or _fallback_prompt_explanation_vi(prompt, fallback_detail)
    return {
        "shot_order": int(_number_or_default(_first_present(item, "shot_order", "shot_number", "shot", "shotIndex", "segment_order", "segment_number", "segment", "segmentIndex", "order"), index)),
        "prompt": _bounded_prompt_field(_render_safe_video_prompt_text(prompt or fallback_detail), 20000),
        "prompt_explanation_vi": _bounded_prompt_field(prompt_explanation_vi, 12000),
        "negative_prompt": _render_safe_video_negative_prompt_text(negative_prompt),
        "duration_seconds": _number_or_default(_first_present(item, "duration_seconds", "duration", "seconds", "segment_duration_seconds", "clip_duration_seconds", "usable_duration_seconds", "timeline_duration_seconds"), None),
        "aspect_ratio": _bounded_prompt_field(_planning_value_to_text(_first_present(item, "aspect_ratio", "ratio")), 20, "9:16"),
        "shot_type": _bounded_prompt_field(shot_type, 120, "video shot"),
        "camera_angle": _bounded_prompt_field(camera_angle, 160, "cinematic angle"),
        "framing": _bounded_prompt_field(framing, 160, "Vertical cinematic frame centered on the main subject."),
        "composition": _bounded_prompt_field(composition, 4000, fallback_detail),
        "camera_motion": _bounded_prompt_field(camera_motion, 160, "subtle cinematic camera movement"),
        "subject_motion": _bounded_prompt_field(subject_motion or _extract_labeled_fragment(prompt, "Subject and action"), 4000, fallback_detail),
        "environment_motion": _bounded_prompt_field(environment_motion, 4000, "subtle environmental motion matching the scene"),
        "start_frame": _bounded_prompt_field(start_frame, 4000, "Start from the opening visual described in the main prompt."),
        "end_frame": _bounded_prompt_field(end_frame, 4000, "End on the final visual beat described in the main prompt."),
        "lighting": _bounded_prompt_field(lighting, 4000, "cinematic natural light"),
        "mood": _bounded_prompt_field(mood, 4000, "cinematic and emotionally clear"),
        "continuity_notes": _bounded_prompt_field(continuity_notes, 6000, "Keep character identity, proportions, environment, and visual style consistent."),
        "retention_notes": _bounded_prompt_field(
            _planning_value_to_text(_first_present(item, *VIDEO_PROMPT_CREATIVE_NOTE_ALIASES["retention_notes"])),
            6000,
            VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["retention_notes"],
        ),
        "transition_notes": _bounded_prompt_field(
            _planning_value_to_text(_first_present(item, *VIDEO_PROMPT_CREATIVE_NOTE_ALIASES["transition_notes"])),
            6000,
            VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["transition_notes"],
        ),
        "sound_design_notes": _bounded_prompt_field(
            _planning_value_to_text(_first_present(item, *VIDEO_PROMPT_CREATIVE_NOTE_ALIASES["sound_design_notes"])),
            6000,
            VIDEO_PROMPT_CREATIVE_NOTE_DEFAULTS["sound_design_notes"],
        ),
    }

def _normalize_video_prompt_pack_payload(payload: dict, project: DBVideoProject | None = None) -> dict:
    payload = _normalize_purpose_metadata_payload(payload)
    _reject_alias_conflict(payload, "prompts", VIDEO_PROMPT_LIST_KEYS)
    _reject_alias_conflicts(
        payload,
        {
            "global_negative_prompt": ("negative_prompt_global", "global_negative_prompt", "negative_prompt"),
            "global_continuity": ("global_continuity", "global_continuity_bible", "continuity_bible", "continuity_notes"),
        },
    )
    global_negative_prompt = _planning_value_to_text(
        _first_present(payload, "negative_prompt_global", "global_negative_prompt", "negative_prompt")
    )
    global_continuity = _planning_value_to_text(
        _first_present(
            payload,
            "global_continuity",
            "global_continuity_bible",
            "continuity_bible",
            "continuity_notes",
        )
    ) or _planning_value_to_text(
        getattr(project, "continuity_bible", None)
    )
    prompts = _first_present(payload, *VIDEO_PROMPT_LIST_KEYS)
    if not isinstance(prompts, list):
        scenes = _first_present(payload, "scenes", "chapters", "sections")
        if isinstance(scenes, list):
            flattened: list[dict] = []
            for scene_index, scene in enumerate(scenes, start=1):
                if not isinstance(scene, dict):
                    continue
                scene_prompts = _first_present(scene, *VIDEO_PROMPT_LIST_KEYS)
                if not isinstance(scene_prompts, list):
                    continue
                for item in scene_prompts:
                    prompt_payload = dict(item) if isinstance(item, dict) else {"prompt": item}
                    prompt_payload.setdefault("scene_order", scene.get("scene_order") or scene.get("scene_number") or scene_index)
                    flattened.append(prompt_payload)
            prompts = flattened
        else:
            prompts = []
    normalized = dict(payload)
    normalized["prompts"] = [
            _normalize_video_prompt_payload(
                item,
                index=index,
                global_negative_prompt=global_negative_prompt,
                global_continuity=global_continuity,
            )
            for index, item in enumerate(prompts, start=1)
        ]
    return normalized

def _source_response(row: DBVideoSourceBlock) -> models.VideoSourceBlockResponse:
    return models.VideoSourceBlockResponse.model_validate(row)

def _shot_response(row: DBVideoShot) -> models.VideoShotResponse:
    return models.VideoShotResponse.model_validate(row)

def _ordered_source_blocks(project_id: str, db: Session) -> list[DBVideoSourceBlock]:
    return (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project_id)
        .order_by(DBVideoSourceBlock.sort_order.asc(), DBVideoSourceBlock.created_at.asc())
        .all()
    )

def ordered_shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc(), DBVideoShot.created_at.asc())
        .all()
    )

def _delete_shots_with_artifacts(project_id: str, shot_ids: list[str], db: Session) -> None:
    if not shot_ids:
        return
    old_prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(shot_ids)).all()
    for old_prompt in old_prompts:
        video_storage.remove_artifact_file(old_prompt.prompt_path)
    db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(shot_ids)).delete(synchronize_session=False)
    old_clips = db.query(DBVideoShotClip).filter(DBVideoShotClip.shot_id.in_(shot_ids)).all()
    for old_clip in old_clips:
        video_storage.remove_artifact_file(old_clip.file_path)
    db.query(DBVideoShotClip).filter(DBVideoShotClip.shot_id.in_(shot_ids)).delete(synchronize_session=False)
    db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id.in_(shot_ids)).delete(synchronize_session=False)

def _ordered_scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )

def _next_source_order(project_id: str, db: Session) -> int:
    return (db.query(func.max(DBVideoSourceBlock.sort_order)).filter(DBVideoSourceBlock.project_id == project_id).scalar() or 0) + 1

def _phase2_stale(project: DBVideoProject, db: Session) -> None:
    from . import video_publishing_metadata

    project.story_approved = False
    project.script_approved = False
    project.planning_status = "stale"
    project.planning_error = None
    project.retention_plan_json = None
    project.sound_design_plan_json = None
    for shot in ordered_shots(project.id, db):
        if not shot.locked:
            shot.status = "stale"
            shot.prompt_status = "stale"
            shot.subtitle_status = "stale"
            shot.updated_at = datetime.utcnow()
    video_rendering.mark_render_outputs_stale(project.id, db)
    video_state.mark_package_stale(project, db)
    video_publishing_metadata.mark_publishing_metadata_stale(
        project.id,
        db,
        reason="Nguồn nội dung hoặc dữ liệu phase 2 đã thay đổi.",
    )

def create_default_source_block(project: DBVideoProject, db: Session) -> DBVideoSourceBlock:
    row = DBVideoSourceBlock(
        id=str(uuid.uuid4()),
        project_id=project.id,
        block_type="idea",
        sort_order=1,
        content=project.topic,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    return row

def list_source_blocks(project_id: str, db: Session) -> list[models.VideoSourceBlockResponse] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    return [_source_response(row) for row in _ordered_source_blocks(project_id, db)]

def create_source_block(project_id: str, data: models.VideoSourceBlockCreate, db: Session) -> models.VideoSourceBlockResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    now = datetime.utcnow()
    row = DBVideoSourceBlock(
        id=str(uuid.uuid4()),
        project_id=project_id,
        block_type=data.block_type,
        sort_order=data.sort_order if data.sort_order is not None else _next_source_order(project_id, db),
        content=data.content,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _phase2_stale(project, db)
    db.commit()
    db.refresh(row)
    video_observability.log_event(db, step_name="source_block_create", status="success", project_id=project_id, message="Đã thêm source block")
    return _source_response(row)

def update_source_block(project_id: str, block_id: str, data: models.VideoSourceBlockUpdate, db: Session) -> models.VideoSourceBlockResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    row = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project_id, DBVideoSourceBlock.id == block_id)
        .first()
    )
    if project is None or row is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    _phase2_stale(project, db)
    db.commit()
    db.refresh(row)
    video_observability.log_event(db, step_name="source_block_update", status="success", project_id=project_id, message="Đã cập nhật source block")
    return _source_response(row)

def delete_source_block(project_id: str, block_id: str, db: Session, *, confirm_delete_last: bool = False) -> bool | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    row = (
        db.query(DBVideoSourceBlock)
        .filter(DBVideoSourceBlock.project_id == project_id, DBVideoSourceBlock.id == block_id)
        .first()
    )
    if project is None:
        return None
    if row is None:
        return False
    before_blocks = _ordered_source_blocks(project_id, db)
    if len(before_blocks) <= 1 and not confirm_delete_last:
        raise ValueError("Đây là nguồn nội dung cuối cùng. Hãy xác nhận nếu vẫn muốn xoá để project không còn input.")
    db.delete(row)
    remaining = [block for block in before_blocks if block.id != block_id]
    for index, block in enumerate(remaining, start=1):
        block.sort_order = index
        block.updated_at = datetime.utcnow()
    _phase2_stale(project, db)
    db.commit()
    video_observability.log_event(
        db,
        step_name="source_block_delete",
        status="success",
        project_id=project_id,
        message="Đã xóa source block và đánh dấu dữ liệu planning cần tạo lại.",
        technical_details={
            "deleted_block_id": block_id,
            "remaining_block_ids": [block.id for block in remaining],
            "remaining_count": len(remaining),
        },
    )
    return True

def reorder_source_blocks(project_id: str, data: models.VideoSourceBlockReorderRequest, db: Session) -> list[models.VideoSourceBlockResponse] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    rows = {row.id: row for row in _ordered_source_blocks(project_id, db)}
    for index, block_id in enumerate(data.block_ids, start=1):
        if block_id in rows:
            rows[block_id].sort_order = index
            rows[block_id].updated_at = datetime.utcnow()
    _phase2_stale(project, db)
    db.commit()
    return [_source_response(row) for row in _ordered_source_blocks(project_id, db)]

def _normalized_source_blocks(project: DBVideoProject, db: Session) -> list[dict[str, object]]:
    blocks = _ordered_source_blocks(project.id, db)
    if not blocks:
        blocks = [create_default_source_block(project, db)]
        db.commit()
    normalized: list[dict[str, object]] = []
    truncated: list[str] = []
    for block in blocks:
        content = (block.content or "").strip()
        if not content:
            continue
        if len(content) > 12000:
            content = content[:12000].rstrip(" ,.;:\n\t") + "...[truncated]"
            truncated.append(block.id)
        normalized.append(
            {
                "id": block.id,
                "sort_order": int(block.sort_order or len(normalized) + 1),
                "block_type": (block.block_type or "idea").strip() or "idea",
                "content": content,
            }
        )
    if truncated:
        video_observability.log_event(
            db,
            step_name="source_context",
            status="info",
            project_id=project.id,
            error_code="AI_VIDEO_SOURCE_CONTEXT_TRUNCATED",
            message="Source block dài đã được truncate an toàn trước khi gửi Codex.",
            technical_details={"truncated_block_ids": truncated},
        )
    if not normalized:
        normalized.append(
            {
                "id": None,
                "sort_order": 1,
                "block_type": "idea",
                "content": (project.topic or "").strip() or project.title,
            }
        )
    return normalized

def _source_context(project: DBVideoProject, db: Session) -> str:
    lines = []
    for block in _normalized_source_blocks(project, db):
        lines.append(f"[{block['sort_order']}] {block['block_type']}:\n{block['content']}")
    return "\n\n".join(lines)

def _phase2_should_use_provider_fallback(exc: Exception) -> bool:
    if getattr(exc, "error_code", None) in {
        "CODEX_EXEC_TIMEOUT",
        "CODEX_PROVIDER_TEMPORARY_UNAVAILABLE",
    }:
        return True
    text = "\n".join(
        part
        for part in (
            str(exc),
            getattr(exc, "provider_detail", None),
        )
        if part
    ).lower()
    return any(
        marker in text
        for marker in (
            "timed out",
            "timeout",
            "time out",
            "overloaded",
            "unavailable",
            "temporarily unavailable",
            "rate limit",
            "connection",
            "network",
            "502",
            "503",
            "504",
            "gateway",
        )
    )

def _fallback_source_snippets(project: DBVideoProject, db: Session, *, limit: int = 12) -> list[str]:
    values: list[str] = [
        project.topic or "",
        project.detailed_script or "",
        project.script_text or "",
        project.creative_brief or "",
    ]
    values.extend(block.content or "" for block in _ordered_source_blocks(project.id, db))
    snippets: list[str] = []
    seen: set[str] = set()
    provenance_markers = ("provenance", "video inspiration job id", "link nguồn", "source link", "đường dẫn file nguồn", "source file path", "gói phân tích", "analysis package", "checksum", "artifact", "job id", "http://", "https://", "s3://", "video_inspiration/", ".json", ".mp4")
    for value in values:
        for part in re.split(r"(?=Panel\s+\d+:)|\n\s*\n+|\n-", value or "", flags=re.IGNORECASE):
            text = re.sub(r"\s+", " ", part).strip(" -\t\r\n")
            if not text or len(text) < 35:
                continue
            lowered = text.lower()
            if lowered.startswith("language lock") or lowered.startswith("negative prompt") or any(marker in lowered for marker in provenance_markers):
                continue
            text = text[:520].rstrip(" ,.;:") + ("..." if len(text) > 520 else "")
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            snippets.append(text)
            if len(snippets) >= limit:
                return snippets
    fallback = (project.topic or project.title or "Nguồn video đã handoff").strip()
    if snippets:
        return snippets
    if any(marker in fallback.lower() for marker in provenance_markers):
        fallback = "Approved video concept"
    return [fallback]

def _production_narration_valid(text: str | None, *, target_language: str | None = None) -> bool:
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if not value or len(value) < 3:
        return False
    lowered = value.lower()
    markers = ("provenance", "video inspiration job id", "link nguồn", "đường dẫn file nguồn", "gói phân tích", "http://", "https://", "video_inspiration/", "job id", "checksum")
    if any(marker in lowered for marker in markers):
        return False
    if video_language.normalize_video_language(target_language) == "en" and re.search(r"[à-ỹđ]", lowered):
        return False
    return True

def _fallback_story_development_payload(project: DBVideoProject, db: Session, *, fallback_reason: str) -> dict[str, Any]:
    snippets = _fallback_source_snippets(project, db, limit=8)
    scene_titles = [
        "Hook từ nguồn",
        "Xung đột chính",
        "Bước ngoặt",
        "Cao trào",
        "Payoff và hướng tiếp theo",
    ]
    scenes: list[dict[str, Any]] = []
    default_duration = int(project.default_shot_duration_seconds or 5)
    style_label = (project.visual_style or "phong cách hình ảnh đã duyệt").strip()
    for index, title in enumerate(scene_titles, start=1):
        source = snippets[(index - 1) % len(snippets)]
        scenes.append(
            {
                "title": title,
                "vietnamese_description": (
                    f"{title}: chuyển ý nguồn thành một cảnh video dọc 9:16. Trọng tâm nguồn: {source}"
                ),
                "english_narration": (
                    f"{source} Nhịp kể giữ đúng nội dung nguồn, tăng dần xung đột và dẫn tới một payoff rõ ràng."
                ),
                "character_appearance": "Kế thừa đúng nhân vật, hình dáng, nhận diện và biểu cảm đã mô tả trong nguồn; không tự thêm nhân vật hoặc canon mới.",
                "wardrobe_and_sandals": "Giữ nguyên trang phục và footwear theo nguồn; nếu nguồn không nêu hoặc khung hình không thấy thì không tự bịa chi tiết.",
                "subject_motion_by_duration": f"Trong khoảng {default_duration}s, nhân vật thực hiện đúng một hành động chính nhìn thấy rõ, bám nội dung nguồn của cảnh.",
                "setting_and_lighting": f"Bám đúng bối cảnh, thời điểm và ánh sáng trong nguồn; thể hiện nhất quán theo {style_label}.",
                "detailed_mood": "Giữ đúng cảm xúc của đoạn nguồn, tăng nhịp hợp lý từ hook qua xung đột đến payoff.",
                "target_duration_seconds": default_duration,
            }
        )
    for scene in scenes:
        current = scene.get("english_narration")
        if not _production_narration_valid(current, target_language=project.target_language):
            scene["english_narration"] = (
                "The approved source detail unfolds into a clear visual beat, builds tension through the character's decision, and lands on a concrete payoff."
                if video_language.normalize_video_language(project.target_language) == "en"
                else "Cảnh đã duyệt phát triển thành một nhịp hình ảnh rõ ràng, tăng dần xung đột qua quyết định của nhân vật và kết thúc bằng một payoff cụ thể."
            )
    synthesis = (
        f"Fallback phase2 do provider lỗi/chậm: {fallback_reason[:260]}. "
        f"Video bám nguồn handoff của project '{project.title}', ngôn ngữ {project.target_language} và {style_label}."
    )
    strategy = (
        "Mở bằng chi tiết mạnh nhất trong nguồn, phát triển xung đột theo thứ tự nhân quả, tạo bước ngoặt rõ, "
        "đưa tới cao trào và kết bằng payoff hoặc open loop có căn cứ trong nội dung đã duyệt."
    )
    continuity = (
        f"Giữ nguyên nhân vật, trang phục, đạo cụ, bối cảnh, bảng màu, {style_label} và trạng thái câu chuyện từ nguồn. "
        "Không thêm nhân vật có tên, quan hệ, địa danh hoặc canon mới ngoài nội dung đã duyệt."
    )
    detailed_script = "\n\n".join(f"Cảnh {idx}: {scene['vietnamese_description']}" for idx, scene in enumerate(scenes, start=1))
    return {
        "video_purpose": project.video_purpose or "global_short",
        "dialogue_mode": project.dialogue_mode or "character_lines",
        "narration_density": project.narration_density or "dense",
        "call_to_action_style": project.call_to_action_style or "direct",
        "input_synthesis": synthesis,
        "story_strategy_vi": strategy,
        "story_strategy": strategy,
        "continuity_bible_vi": continuity,
        "continuity_bible": continuity,
        "detailed_script_vi": detailed_script,
        "detailed_script": detailed_script,
        "retention_plan": _default_retention_payload(
            fallback="0-2s mở bằng chi tiết mạnh nhất trong nguồn; giữa video giữ một câu hỏi chưa giải đáp; cuối video trả payoff và mở hướng tiếp theo từ chính nội dung đã duyệt."
        ),
        "sound_design_plan": _default_sound_payload(
            has_narration=True,
            fallback="ambience đúng bối cảnh, một nhịp impact cho bước ngoặt và cao trào âm nhạc vừa đủ dưới narration",
        ),
        "scenes": scenes,
    }

def _fallback_shot_breakdown_payload(
    project: DBVideoProject,
    scenes: list[DBVideoScene],
    *,
    fallback_reason: str,
    segment_count: int | None = None,
    first_shot_order: int = 1,
) -> dict[str, Any]:
    rows = scenes or []
    if not rows:
        rows = [
            DBVideoScene(
                id="fallback-scene",
                project_id=project.id,
                scene_order=1,
                title="Fallback scene",
                dialogue=project.topic or project.title,
                visual_description=project.topic or project.title,
                target_duration_seconds=project.default_shot_duration_seconds or 5,
            )
        ]
    if segment_count is None:
        selected_scenes = rows[:8]
    else:
        requested_count = max(0, int(segment_count))
        configured_total = _resolve_prompt_segment_config(project).segment_count
        total_segment_count = configured_total or (first_shot_order - 1 + requested_count)
        selected_scenes = []
        for shot_order in range(first_shot_order, first_shot_order + requested_count):
            if len(rows) == 1 or total_segment_count <= 1:
                scene_index = 0
            else:
                scene_index = round(
                    (shot_order - 1) * (len(rows) - 1) / (total_segment_count - 1)
                )
            selected_scenes.append(rows[min(len(rows) - 1, max(0, scene_index))])

    shots: list[dict[str, Any]] = []
    micro_count = int(project.micro_scenes_per_prompt or DEFAULT_MICRO_SCENES_PER_PROMPT)
    project_label = (project.title or project.topic or "dự án video").strip()
    style_label = (project.visual_style or "phong cách hình ảnh đã duyệt").strip()
    for offset, scene in enumerate(selected_scenes):
        shot_order = first_shot_order + offset
        profile = SEGMENT_CAMERA_VARIATION_PROFILES[(shot_order - 1) % len(SEGMENT_CAMERA_VARIATION_PROFILES)]
        duration = _clamp_shot_duration(
            scene.target_duration_seconds,
            project,
            shot_order=shot_order,
        )
        ranges = _micro_scene_ranges(duration, micro_count)
        base = (scene.visual_description or scene.dialogue or scene.title or project.topic or project.title or "").strip()
        micro_scenes = [
            {
                "order": micro_index,
                "start_seconds": start,
                "end_seconds": end,
                "description_vi": f"{_micro_scene_range_label(start, end)}: {base[:260]}",
                "visual_action": f"Nhân vật giữ hành động chính của cảnh {scene.scene_order or shot_order}, biểu cảm rõ, chuyển động nhỏ nhưng đọc được.",
                "camera_note": profile["camera_motion"],
                "continuity_note": f"Giữ cùng nhân vật, trang phục, {style_label} và trạng thái câu chuyện.",
                "visible_characters": [],
            }
            for micro_index, (start, end) in enumerate(ranges, start=1)
        ]
        shots.append(
            {
                "scene_order": int(scene.scene_order or shot_order),
                "shot_order": shot_order,
                "duration_seconds": duration,
                "vietnamese_description": f"Segment {shot_order}: {base}",
                "english_narration": scene.dialogue or base,
                "primary_action": "Nhân vật thực hiện một hành động chính rõ ràng theo scene đã duyệt, với phản ứng và chuyển động dễ đọc.",
                "purpose": "Chuyển scene đã duyệt thành nhịp video dọc có hook, cảm xúc và payoff.",
                "shot_type": profile["shot_type"],
                "camera_angle": profile["camera_angle"],
                "framing": profile["framing"],
                "composition": profile["composition"],
                "camera_motion": profile["camera_motion"],
                "subject_motion": "Subtle readable motion consistent with the approved scene: blink, turn, step, gesture, react, then settle.",
                "environment_motion": "Subtle environmental motion consistent with the approved setting, with controlled depth and light drift.",
                "transition_to_next": "Motivated cut on the final look or narration beat.",
                "retention_role": "Open loop hoặc payoff nhỏ để giữ người xem.",
                "open_loop": f"Điều gì sẽ xảy ra tiếp theo trong {project_label}?",
                "visual_surprise": "Một thay đổi hình ảnh hoặc phản ứng bất ngờ được lấy trực tiếp từ scene đã duyệt.",
                "cut_reason": "Cắt khi cảm xúc hoặc thông tin mới đạt đỉnh.",
                "visible_characters": [],
                "transition_pack": _default_transition_payload(final=offset == len(selected_scenes) - 1),
                "sound_design": _default_sound_payload(has_narration=bool(scene.dialogue or base)),
                "micro_scenes": micro_scenes,
            }
        )
    return {
        "video_purpose": project.video_purpose or "global_short",
        "dialogue_mode": project.dialogue_mode or "character_lines",
        "narration_density": project.narration_density or "dense",
        "call_to_action_style": project.call_to_action_style or "direct",
        "shots": [
            ({**shot, "english_narration": "", "speech_cues": []}
             if not _production_narration_valid(shot.get("english_narration"), target_language=project.target_language)
             else shot)
            for shot in shots
        ],
    }

def _fallback_video_prompt_pack_payload(
    project: DBVideoProject,
    shots: list[DBVideoShot],
    *,
    fallback_reason: str,
) -> dict[str, Any]:
    prompts: list[dict[str, Any]] = []
    style_label = (project.visual_style or "the approved project visual style").strip()
    for shot in shots:
        duration = _clamp_shot_duration(shot.duration_seconds, project, shot_order=shot.shot_order)
        micro_text = _micro_scene_timeline_text(shot.micro_scenes_json or [])
        character_text = video_series_characters.fallback_prompt_character_text(project)
        speech_cues = shot.speech_cues_json if isinstance(shot.speech_cues_json, list) else []
        speech_text = json.dumps(speech_cues, ensure_ascii=False) if speech_cues else (shot.english_narration or "")
        sound_text = json.dumps(shot.sound_design_json or {}, ensure_ascii=False)
        prompt = (
            f"Create a {duration:g}-second {project.aspect_ratio} high-quality cinematic animation video in this visual style: {style_label}. "
            f"Shot {shot.shot_order}: {shot.vietnamese_description}. "
            f"{character_text} "
            f"Action: {shot.primary_action}. Camera: {shot.camera_angle}, {shot.framing}, {shot.camera_motion}. "
            f"Composition: {shot.composition}. Subject motion: {shot.subject_motion}. Environment motion: {shot.environment_motion}. "
            f"Lighting and mood: preserve the approved scene setting, palette, atmosphere, and emotional tone; use controlled cinematic contrast, clear depth, and parallax. "
            f"Micro-scene timeline: {micro_text}. "
            f"DIALOGUE / SPEECH (target language {video_language.video_language_label(project.target_language)}): {speech_text}. "
            "Preserve exact dialogue text, speaker, delivery, emotion, context, and lip_sync_required; distinguish visible on-screen speech from off-screen voice-over. "
            f"SOUND DESIGN: {sound_text}. Include ambience, music mood/energy, timed SFX, beat timing, and mixing notes. "
            "For Veo 3 native-audio rendering, render this dialogue and sound design inside the clip itself; do not replace it with invented language. "
            "Do not render subtitles, captions, karaoke lyrics, text overlays, letters, words, UI text, logos, or watermarks in the video."
        )
        negative_prompt = (
            "No watermark, no logo, no random text, no burned-in subtitles, no distorted face, no bad hands, "
            "no extra characters, no photorealistic live-action, no flicker, no 2D illustration, no flat drawing, "
            "no flat comic panel, no static image, no image prompt, no storyboard frame, no line-art-only render."
        )
        if project.series_id:
            negative_prompt = (
                "No watermark, no logo, no random text, no burned-in subtitles, no distorted face, no bad hands, "
                "no extra characters, no duplicate character, no identity swap, no unintended named character, no wrong face, "
                "no wrong hairstyle, no wrong signature outfit, no extra foreground character outside the approved cast, "
                "no photorealistic live-action, no flicker, no 2D illustration, no flat drawing, no flat comic panel, "
                "no static image, no image prompt, no storyboard frame, no line-art-only render."
            )
        prompts.append(
            {
                "shot_order": shot.shot_order,
                "prompt": prompt,
                "prompt_explanation_vi": (
                    f"Fallback prompt video cho shot {shot.shot_order}: chuyển segment thành clip {duration:g}s, giữ {style_label}, "
                    "nhân vật, trang phục, bối cảnh và trạng thái câu chuyện đã duyệt; voice và phụ đề được tạo ở bước sau."
                ),
                "negative_prompt": negative_prompt,
                "duration_seconds": duration,
                "aspect_ratio": project.aspect_ratio or "9:16",
                "shot_type": shot.shot_type or "cinematic segment",
                "camera_angle": shot.camera_angle or "eye-level cinematic angle",
                "framing": shot.framing or "vertical medium shot",
                "composition": shot.composition or "subject framed clearly with an uncluttered lower frame",
                "camera_motion": shot.camera_motion or "slow push-in",
                "subject_motion": shot.subject_motion or shot.primary_action or "subtle emotional reaction",
                "environment_motion": shot.environment_motion or "soft ambient movement",
                "start_frame": "Start on a clean frame that establishes the approved setting, characters, and current story beat.",
                "end_frame": "End on an emotional hold or motivated transition into the next segment.",
                "lighting": "cinematic lighting consistent with the approved shot description, controlled contrast, and readable subject separation",
                "mood": "match the approved shot emotion and current story state without adding a different genre or canon",
                "continuity_notes": video_series_characters.segment_continuity_rule(project),
                "retention_notes": _planning_value_to_text(shot.retention_json) or "Maintain the approved open loop and pay it off through visible action from the source.",
                "transition_notes": _planning_value_to_text(shot.transition_json) or shot.transition_to_next or "Motivated cut to the next emotional beat.",
                "sound_design_notes": _planning_value_to_text(shot.sound_design_json) or "Use subtle cinematic music and short transition SFX under clear narration in the approved target language.",
            }
        )
    return {
        "video_purpose": project.video_purpose or "global_short",
        "dialogue_mode": project.dialogue_mode or "character_lines",
        "narration_density": project.narration_density or "dense",
        "call_to_action_style": project.call_to_action_style or "direct",
        "global_negative_prompt": "No watermark, no logo, no random text, no burned-in subtitles, no distorted faces, no 2D illustration, no flat drawing, no flat comic panel, no static image, no image prompt, no storyboard frame, no line-art-only render.",
        "global_continuity": (
            f"{style_label}. Keep the same approved character identities, proportions, wardrobe logic, props, locations, "
            "color palette, and story state across all segments. Do not invent named characters or canon details."
        ),
        "prompts": prompts,
    }

def _target_prompt_segment_count(project: DBVideoProject) -> int | None:
    return _resolve_prompt_segment_config(project).segment_count

def _usable_segment_duration(project: DBVideoProject, segment_order: int) -> float:
    config = _resolve_prompt_segment_config(project)
    prompt_duration = float(config.prompt_duration_seconds)
    if not config.target_duration_seconds or config.target_duration_seconds <= 0:
        return prompt_duration
    elapsed = max(0, segment_order - 1) * prompt_duration
    remaining = config.target_duration_seconds - elapsed
    if remaining <= 0:
        return prompt_duration
    return float(min(prompt_duration, remaining))

def _segment_timeline_label(project: DBVideoProject, segment_order: int) -> str:
    config = _resolve_prompt_segment_config(project)
    prompt_duration = config.prompt_duration_seconds
    start = max(0, segment_order - 1) * prompt_duration
    if config.target_duration_seconds and config.target_duration_seconds > 0:
        end = min(config.target_duration_seconds, start + prompt_duration)
    else:
        end = start + prompt_duration
    return _micro_scene_range_label(start, end)

def _narration_word_range(duration_seconds: float | int | None, *, segment_mode: bool) -> tuple[int, int, int]:
    duration = max(1.0, float(duration_seconds or VIDEO_PROMPT_SEGMENT_SECONDS))
    floor = 12 if segment_mode else 6
    minimum = max(floor, math.ceil(duration * NARRATION_MIN_WORDS_PER_SECOND))
    target = max(minimum + 2, math.ceil(duration * NARRATION_TARGET_WORDS_PER_SECOND))
    maximum = max(target + 4, math.ceil(duration * NARRATION_MAX_WORDS_PER_SECOND))
    return minimum, target, maximum

def _narration_length_instruction(project: DBVideoProject, *, duration_seconds: float | int | None = None, shot_order: int | None = None) -> str:
    segment_count = _target_prompt_segment_count(project)
    if segment_count is not None:
        config = _resolve_prompt_segment_config(project)
        full_min, full_target, full_max = _narration_word_range(config.prompt_duration_seconds, segment_mode=True)
        if shot_order is not None:
            usable_duration = duration_seconds or _usable_segment_duration(project, shot_order)
            min_words, target_words, max_words = _narration_word_range(usable_duration, segment_mode=True)
            return (
                f"english_narration phải là voiceover dài hơn cho segment này, khoảng {min_words}-{max_words} từ "
                f"(mục tiêu {target_words} từ) cho {usable_duration:g}s timeline; không viết một câu cụt 3-8 từ."
            )
        final_duration = _usable_segment_duration(project, segment_count)
        final_note = ""
        if final_duration < config.prompt_duration_seconds:
            final_min, final_target, final_max = _narration_word_range(final_duration, segment_mode=True)
            final_note = f" Segment cuối {final_duration:g}s dùng khoảng {final_min}-{final_max} từ, mục tiêu {final_target} từ."
        return (
            f"english_narration phải là voiceover dài hơn, đủ phủ phần lớn mỗi segment: "
            f"segment {config.prompt_duration_seconds}s đầy đủ dùng khoảng {full_min}-{full_max} từ, mục tiêu {full_target} từ. "
            f"Không viết tagline/câu cụt 3-8 từ; viết 1-2 câu tự nhiên có cảm xúc và thông tin mới.{final_note}"
        )
    min_words, target_words, max_words = _narration_word_range(duration_seconds or project.default_shot_duration_seconds or 3, segment_mode=False)
    return (
        f"english_narration phải dài hơn một câu ngắn, khoảng {min_words}-{max_words} từ "
        f"(mục tiêu {target_words} từ) theo thời lượng shot; không viết tagline/câu cụt 3-8 từ."
    )

def _shot_duration_preference(project: DBVideoProject) -> str:
    config = _resolve_prompt_segment_config(project)
    if config.segment_count is not None:
        source = "theo cấu hình người dùng" if config.explicit else "legacy từ thời lượng mục tiêu"
        return (
            f"Prompt segment mode ({source}): tạo đúng {config.segment_count} prompt segment; "
            f"mỗi prompt tạo clip {config.prompt_duration_seconds} giây, mỗi prompt có {config.micro_scenes_per_prompt} cảnh nhỏ; "
            "segment cuối có thể trim theo thời lượng mục tiêu nếu là project legacy"
        )
    if project.default_shot_duration_seconds is None:
        return "Auto: AI tự chọn thời lượng từng shot theo nhịp nội dung, trong khoảng 1-5 giây"
    return f"ưu tiên khoảng {project.default_shot_duration_seconds} giây cho mỗi shot, vẫn cho phép 1-5 giây"

def _clamp_shot_duration(value: float | int | None, project: DBVideoProject, *, shot_order: int | None = None) -> float:
    if _target_prompt_segment_count(project) is not None and shot_order is not None:
        return _usable_segment_duration(project, shot_order)
    fallback = project.default_shot_duration_seconds or 3
    duration = value if value is not None else fallback
    return min(5, max(1, float(duration)))

def _micro_scene_fallback_text(shot: ShotPlan) -> str:
    return _planning_value_to_text(
        {
            "description_vi": shot.vietnamese_description,
            "visual_action": shot.primary_action or shot.subject_motion,
            "camera_note": shot.camera_motion or shot.camera_angle or shot.framing,
            "continuity_note": shot.transition_to_next,
        }
    )

def _fit_micro_scenes_to_config(shot: ShotPlan, project: DBVideoProject, *, shot_order: int) -> None:
    config = _resolve_prompt_segment_config(project)
    if config.segment_count is None:
        return
    duration = _usable_segment_duration(project, shot_order)
    shot.duration_seconds = duration
    desired_count = config.micro_scenes_per_prompt
    existing = [scene for scene in shot.micro_scenes if (scene.description_vi or scene.visual_action or scene.camera_note)]
    if len(existing) != desired_count:
        existing = []
    ranges = _micro_scene_ranges(duration, desired_count)
    fallback_text = _micro_scene_fallback_text(shot)
    fitted: list[MicroScenePlan] = []
    for index, (start, end) in enumerate(ranges, start=1):
        source = existing[index - 1] if index - 1 < len(existing) else None
        description = (source.description_vi if source else "") or fallback_text
        visual_action = (source.visual_action if source else "") or shot.primary_action or shot.subject_motion or description
        camera_note = (source.camera_note if source else "") or shot.camera_motion or shot.camera_angle or shot.framing or ""
        fitted.append(
            MicroScenePlan(
                order=index,
                start_seconds=start,
                end_seconds=end,
                description_vi=description,
                visual_action=visual_action,
                camera_note=camera_note,
                continuity_note=(source.continuity_note if source else "") or shot.transition_to_next or "",
            )
        )
    shot.micro_scenes = fitted

def _micro_scene_lines(micro_scenes: list[MicroScenePlan] | list[dict] | None) -> list[str]:
    lines: list[str] = []
    for item in micro_scenes or []:
        if isinstance(item, MicroScenePlan):
            payload = item.model_dump()
        elif isinstance(item, dict):
            payload = item
        else:
            continue
        label = _micro_scene_range_label(payload.get("start_seconds") or 0, payload.get("end_seconds") or 0)
        description = _planning_value_to_text(
            payload.get("description_vi") or payload.get("visual_action") or payload.get("camera_note")
        )
        camera = _planning_value_to_text(payload.get("camera_note"))
        continuity = _planning_value_to_text(payload.get("continuity_note"))
        detail = description
        if camera:
            detail = f"{detail}; camera: {camera}" if detail else f"camera: {camera}"
        if continuity:
            detail = f"{detail}; continuity: {continuity}" if detail else f"continuity: {continuity}"
        lines.append(f"{label}: {detail}".strip())
    return lines

def _micro_scene_timeline_text(micro_scenes: list[MicroScenePlan] | list[dict] | None) -> str:
    return "\n".join(_micro_scene_lines(micro_scenes))

def _series_field_text(value: str | None, *, limit: int, field_name: str, truncated: list[str]) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    truncated.append(field_name)
    return text[:limit].rstrip(" ,.;:\n\t") + "...[truncated]"

def _series_character_profiles_text(series_id: str, db: Session, *, limit: int, truncated: list[str]) -> str:
    rows = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    parts: list[str] = []
    for row in rows:
        fields = [
            f"- {row.name} ({(row.role or 'vai trò chưa rõ').strip()})",
            f"  Face: {(row.face_description or '').strip()}",
            f"  Hair: {(row.hair_description or '').strip()}",
            f"  Body: {(row.body_description or '').strip()}",
            f"  Outfit: {(row.signature_outfit or '').strip()}",
            f"  Personality: {(row.personality or '').strip()}",
            f"  Speech: {(row.speech_style or '').strip()}",
            f"  Fixed traits: {(row.fixed_traits or '').strip()}",
            f"  Notes: {(row.additional_notes or '').strip()}",
        ]
        parts.append("\n".join(field for field in fields if not field.endswith(": ")))
    text = "\n\n".join(parts).strip()
    if len(text) <= limit:
        return text
    truncated.append("character_profiles")
    return text[:limit].rstrip(" ,.;:\n\t") + "...[truncated]"

def _series_context(project: DBVideoProject, db: Session) -> str:
    series_id = getattr(project, "series_id", None)
    if not series_id:
        return ""
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        video_observability.log_event(
            db,
            step_name="series_context",
            status="warning",
            project_id=project.id,
            error_code="AI_VIDEO_SERIES_NOT_FOUND",
            message="Project có series_id nhưng không tìm thấy Series Bible.",
            technical_details={"series_id": series_id},
        )
        return ""
    try:
        compiled = series_brain.compile_prompt_context(
            series.id,
            db,
            task_type="video_story_development",
            episode_number=getattr(project, "episode_number", None),
            project_id=project.id,
            user_input=getattr(project, "topic", None),
            current_payload={
                "project_title": project.title,
                "episode_title": getattr(project, "episode_title", None),
                "source_topic": project.topic,
                "story_strategy": project.story_strategy,
                "continuity_bible": project.continuity_bible,
                "detailed_script": project.detailed_script,
            },
            max_chars=video_series_memory.MAX_MEMORY_CONTEXT_CHARS,
            persist_trace=True,
        )
        if compiled.missing_required or compiled.truncated_groups:
            video_observability.log_event(
                db,
                step_name="series_context",
                status="warning" if compiled.missing_required else "info",
                project_id=project.id,
                error_code="AI_VIDEO_SERIES_CONTEXT_INCOMPLETE" if compiled.missing_required else "AI_VIDEO_SERIES_CONTEXT_TRUNCATED",
                message="Series context duoc bien dich theo nhiem vu va co trace an toan.",
                technical_details={
                    "series_id": series.id,
                    "trace_id": compiled.trace_id,
                    "missing_required": compiled.missing_required,
                    "truncated_groups": compiled.truncated_groups,
                    "context_stats": compiled.context_stats,
                },
            )
        trace_line = f"Series context trace: `{compiled.trace_id}`" if compiled.trace_id else "Series context trace: not persisted"
        return "\n".join(
            [
                "Series context:",
                trace_line,
                "- Series memory file (`series-memory.md`): replaced by Series Brain compiled context.",
                "- Episode Index: retained in the rendered Markdown memory file; task context below is compiled by Series Brain.",
                compiled.context_text,
            ]
        )
    except Exception as exc:
        video_observability.log_event(
            db,
            step_name="series_context",
            status="warning",
            project_id=project.id,
            error_code="AI_VIDEO_SERIES_CONTEXT_COMPILE_FAILED",
            exc=exc,
            message="Khong bien dich duoc Series Brain context; fallback ve Series Bible cu.",
            technical_details={"series_id": series.id},
        )
    truncated: list[str] = []
    memory_text = ""
    try:
        memory_text, memory_truncated = video_series_memory.read_series_memory_for_prompt(series.id, db)
        if memory_truncated:
            truncated.append("series_memory_file")
    except Exception as exc:
        video_observability.log_event(
            db,
            step_name="series_context",
            status="warning",
            project_id=project.id,
            error_code="AI_VIDEO_SERIES_MEMORY_READ_FAILED",
            exc=exc,
            message="Không đọc được file series-memory.md; fallback về Series Bible trong database.",
            technical_details={"series_id": series.id},
        )
    profile_text = _series_character_profiles_text(series.id, db, limit=8000, truncated=truncated)
    missing_core = [
        key
        for key, value in {
            "world_bible": series.world_bible,
            "style_bible": series.style_bible,
        }.items()
        if not (value or "").strip()
    ]
    if not (series.character_bible or "").strip() and not profile_text:
        missing_core.insert(0, "character_profiles_or_character_bible")
    if missing_core or truncated:
        video_observability.log_event(
            db,
            step_name="series_context",
            status="warning" if missing_core else "info",
            project_id=project.id,
            error_code="AI_VIDEO_SERIES_CONTEXT_INCOMPLETE" if missing_core else "AI_VIDEO_SERIES_CONTEXT_TRUNCATED",
            message="Series context thiếu trường cốt lõi hoặc đã được truncate an toàn.",
            technical_details={
                "series_id": series.id,
                "missing_core_fields": missing_core,
                "truncated_fields": truncated,
                "episode_number": getattr(project, "episode_number", None),
            },
        )
    lines = [
        "Series context:",
        f"- Series title: {series.title}",
        f"- Episode: {getattr(project, 'episode_number', None) or 'unspecified'} - {getattr(project, 'episode_title', None) or project.title}",
    ]
    if memory_text:
        lines.append(f"- Series memory file (`series-memory.md`):\n{memory_text}")
    else:
        fields = {
            "Structured character profiles": profile_text,
            "Character bible": _series_field_text(series.character_bible, limit=8000, field_name="character_bible", truncated=truncated),
            "World bible": _series_field_text(series.world_bible, limit=8000, field_name="world_bible", truncated=truncated),
            "Style bible": _series_field_text(series.style_bible, limit=8000, field_name="style_bible", truncated=truncated),
            "Continuity rules": _series_field_text(series.continuity_rules, limit=8000, field_name="continuity_rules", truncated=truncated),
            "Negative rules": _series_field_text(series.negative_rules, limit=6000, field_name="negative_rules", truncated=truncated),
            "Previous episode summary": _series_field_text(series.previous_episode_summary, limit=4000, field_name="previous_episode_summary", truncated=truncated),
        }
        for label, value in fields.items():
            if value:
                lines.append(f"- {label}:\n{value}")
    lines.append(
        "- Non-negotiables: keep the same character identity, same world, same visual style, and same story continuity unless the user explicitly changes the Series Bible."
    )
    return "\n".join(lines)

def normalize_phase2_codex_context(project: DBVideoProject, db: Session) -> dict[str, object]:
    target_language = video_language.normalize_video_language(getattr(project, "target_language", None))
    settings = video_purpose_service.resolve_purpose_settings(
        video_purpose=getattr(project, "video_purpose", None),
        target_language=target_language,
        dialogue_mode=getattr(project, "dialogue_mode", None),
        narration_density=getattr(project, "narration_density", None),
        call_to_action_style=getattr(project, "call_to_action_style", None),
    )
    segment_config = _resolve_prompt_segment_config(project)
    source_blocks = _normalized_source_blocks(project, db)
    source_context = "\n\n".join(
        f"[{block['sort_order']}] {block['block_type']}:\n{block['content']}" for block in source_blocks
    )
    return {
        "project_id": project.id,
        "title": project.title,
        "topic": project.topic,
        "target_language": target_language,
        "target_language_label": video_language.video_language_label(target_language),
        "viewer_language_instruction": video_language.viewer_language_instruction(target_language),
        "narration_field_note": video_language.narration_field_note(target_language),
        "video_purpose": settings["video_purpose"],
        "dialogue_mode": settings["dialogue_mode"],
        "narration_density": settings["narration_density"],
        "call_to_action_style": settings["call_to_action_style"],
        "purpose_context_lines": video_purpose_service.purpose_context_lines(
            video_purpose=str(settings["video_purpose"]),
            target_language=target_language,
            dialogue_mode=str(settings["dialogue_mode"]),
            narration_density=str(settings["narration_density"]),
            call_to_action_style=settings["call_to_action_style"],
        ),
        "source_blocks": source_blocks,
        "source_context": source_context,
        "series_context": _series_context(project, db),
        "prompt_segment_config": {
            "segment_count": segment_config.segment_count,
            "prompt_duration_seconds": segment_config.prompt_duration_seconds,
            "micro_scenes_per_prompt": segment_config.micro_scenes_per_prompt,
            "target_duration_seconds": segment_config.target_duration_seconds,
            "explicit": segment_config.explicit,
        },
    }

def _purpose_generation_instructions(project: DBVideoProject) -> str:
    settings = video_purpose_service.resolve_purpose_settings(
        video_purpose=getattr(project, "video_purpose", None),
        target_language=getattr(project, "target_language", None),
        dialogue_mode=getattr(project, "dialogue_mode", None),
        narration_density=getattr(project, "narration_density", None),
        call_to_action_style=getattr(project, "call_to_action_style", None),
    )
    purpose = str(settings["video_purpose"])
    dialogue_mode = str(settings["dialogue_mode"])
    density = str(settings["narration_density"])
    target_language = video_language.normalize_video_language(getattr(project, "target_language", None))
    lines = [
        f"Áp dụng video_purpose={purpose}, dialogue_mode={dialogue_mode}, narration_density={density}.",
        "target_language luôn là nguồn sự thật cho speech, narration, subtitle và on-screen text người xem đọc.",
    ]
    if target_language == "en":
        lines.append(
            "English language lock: every viewer-facing field must be written in natural English. "
            "Do not copy Vietnamese dialogue, narration, subtitles, on-screen text, or CTA into production fields. "
            "If the source block or analysis notes are Vietnamese, translate/rewrite them for production output and keep the Vietnamese text only in review/explanation fields."
        )
    else:
        lines.append(
            "Vietnamese language lock: every viewer-facing field must be written in natural Vietnamese. "
            "Do not mix English source wording into narration/dialogue/subtitle/on-screen text unless it is technical camera/visual direction."
        )
    if purpose == "educational_explainer":
        lines.append("Với educational_explainer, thoại/narration phải rõ nghĩa, dễ nghe, đủ ngữ cảnh, giải thích từng ý bằng ví dụ cụ thể.")
    if purpose == "sales_ad":
        cta = settings.get("call_to_action_style") or "direct"
        lines.append(f"Với sales_ad, mở bằng hook, nêu lợi ích chính, giữ nhịp cô đọng và kết bằng CTA kiểu {cta}.")
    if dialogue_mode == "voiceover":
        lines.append("Với dialogue_mode=voiceover, ưu tiên narrator/voiceover; không bắt buộc tạo câu thoại nhân vật riêng.")
    elif dialogue_mode == "character_lines":
        lines.append("Với dialogue_mode=character_lines, viết câu thoại tự nhiên cho nhân vật/người nói nhưng vẫn nằm trong một voice track hiện có.")
    else:
        lines.append("Với dialogue_mode=mixed, kết hợp voiceover ngắn và câu thoại tự nhiên khi giúp câu chuyện rõ hơn.")
    if density == "light":
        lines.append("Narration density light: câu ngắn, ít chữ, chừa nhiều không gian cho visual.")
    elif density == "dense":
        lines.append("Narration density dense: đủ thông tin và ngữ cảnh, nhưng vẫn tự nhiên theo nhịp video.")
    else:
        lines.append("Narration density balanced: cân bằng giữa thông tin, cảm xúc và nhịp dựng.")
    return "\n- ".join(lines)

def _project_context(project: DBVideoProject, db: Session) -> str:
    context = normalize_phase2_codex_context(project, db)
    target_language = str(context["target_language"])
    series_context = str(context["series_context"] or "")
    parts = [
        f"Tên dự án: {project.title}\n"
        f"Topic ngắn: {project.topic}\n"
        f"Ngôn ngữ UI và phần giải thích cho người dùng: tiếng Việt\n"
        f"Ngôn ngữ video người xem nghe/đọc: {context['target_language_label']} ({target_language})\n"
        f"Chỉ dẫn ngôn ngữ video: {context['viewer_language_instruction']}\n"
        f"Mục đích video: {context['video_purpose']}\n"
        f"Dialogue mode: {context['dialogue_mode']}\n"
        f"Narration density: {context['narration_density']}\n"
        f"CTA style: {context['call_to_action_style'] or 'none'}\n"
        "Purpose/preset guidance:\n- " + "\n- ".join(str(line) for line in context["purpose_context_lines"]) + "\n"
        f"Thời lượng mục tiêu: {project.target_duration_seconds or 'tự chọn'} giây\n"
        f"Tỷ lệ khung hình: {project.aspect_ratio}\n"
        f"Kế hoạch shot/prompt: {_shot_duration_preference(project)}\n"
        f"Phong cách video: {project.visual_style or 'tự đề xuất'}"
    ]
    if series_context:
        parts.append(series_context)
    parts.append(f"Nguồn nội dung:\n{context['source_context']}")
    return "\n\n".join(parts)

def _phase2_codex_timeout(settings) -> int:
    try:
        phase2_floor = int(os.environ.get("VOICEBOX_PHASE2_CODEX_TIMEOUT", str(PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS)))
    except ValueError:
        phase2_floor = PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS
    phase2_floor = max(PHASE2_DEFAULT_CODEX_TIMEOUT_SECONDS, phase2_floor)
    configured = settings.timeout_seconds or 60
    return max(5, min(max(configured, phase2_floor), PHASE2_MAX_CODEX_TIMEOUT_SECONDS))

def _run_structured_codex(
    db: Session,
    project: DBVideoProject,
    prompt: str,
    schema: dict,
    *,
    step_name: str,
    max_attempts: int | None = None,
    technical_context: dict[str, object] | None = None,
) -> dict:
    settings = settings_service.get_ai_planning_settings(db)
    timeout_seconds = _phase2_codex_timeout(settings)
    attempt_limit = max(1, int(max_attempts or MAX_RETRIES))
    schema_properties = schema.get("properties") if isinstance(schema, dict) else None
    schema_keys = sorted(str(key) for key in schema_properties)[:20] if isinstance(schema_properties, dict) else []
    log_details = {
        "timeout_seconds": timeout_seconds,
        "prompt_chars": len(prompt),
        "schema_keys": schema_keys,
        "max_attempts": attempt_limit,
        "max_retries": attempt_limit,
        **(technical_context or {}),
    }
    last_error: BaseException | None = None
    with video_planning_pool.planning_slot(
        db,
        project_id=project.id,
        step_name=step_name,
        provider=settings.provider,
        model=settings.model,
        details=log_details,
    ):
        for attempt in range(1, attempt_limit + 1):
            started = time.perf_counter()
            try:
                video_observability.log_event(
                    db,
                    step_name=step_name,
                    status="start",
                    project_id=project.id,
                    provider=settings.provider,
                    model=settings.model,
                    retry_count=attempt - 1,
                    message=f"Bắt đầu {step_name}",
                    technical_details={**log_details, "attempt": attempt},
                )
                raw = ai_planning.run_codex_exec(settings, prompt, output_schema=schema, timeout_seconds=timeout_seconds)
                parsed = _load_json_object(raw)
                video_observability.log_event(
                    db,
                    step_name=step_name,
                    status="success",
                    project_id=project.id,
                    provider=settings.provider,
                    model=settings.model,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    retry_count=attempt - 1,
                    message=f"Hoàn tất {step_name}",
                    technical_details={**log_details, "attempt": attempt, "output_chars": len(raw or "")},
                )
                return parsed
            except (ai_planning.AIPlanningError, VideoPlanningValidationError) as exc:
                last_error = exc
                error_code = getattr(exc, "error_code", "VIDEO_PLANNING_INVALID_OUTPUT")
                should_retry = attempt < attempt_limit and error_code not in {
                    "CODEX_EXEC_TIMEOUT",
                    "CODEX_PROVIDER_REJECTED",
                }
                video_observability.log_event(
                    db,
                    step_name=step_name,
                    status="warning" if should_retry else "failure",
                    project_id=project.id,
                    provider=settings.provider,
                    model=settings.model,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    retry_count=attempt,
                    error_code=error_code,
                    exc=exc,
                    message=str(exc),
                    technical_details={
                        **log_details,
                        "attempt": attempt,
                        "will_retry": should_retry,
                        "error_class": exc.__class__.__name__,
                    },
                )
                if not should_retry:
                    if isinstance(exc, ai_planning.AIPlanningError):
                        raise exc
                    break
                time.sleep(RETRY_DELAY_SECONDS)
        if isinstance(last_error, ai_planning.AIPlanningError):
            raise last_error
        raise VideoPlanningValidationError("AI trả về dữ liệu không đúng định dạng. Thử lại.") from last_error

def develop_story(project_id: str, db: Session, *, force: bool = False) -> models.VideoProjectDetailResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if project.story_approved and not force:
        from . import video_projects

        return video_projects.get_project(project_id, db)

    prompt = f"""
Bạn là Script-to-Video-Prompt Studio trong Voicebox. Người dùng có thể nhập nguồn nội dung bằng tiếng Việt, tiếng Anh hoặc lẫn cả hai. Video cuối phải dùng ngôn ngữ video đã chọn.

{_project_context(project, db)}

{video_series_characters.story_development_instructions(project, db)}

Hãy phát triển nội dung thành story strategy hấp dẫn và kịch bản chi tiết.
Yêu cầu bắt buộc:
- {video_language.viewer_language_instruction(project.target_language)}
- {video_language.narration_field_note(project.target_language)}
- {_purpose_generation_instructions(project)}
- story_strategy_vi, continuity_bible_vi và detailed_script_vi bắt buộc viết bằng tiếng Việt tự nhiên, đủ rõ để người dùng Việt đọc, hiểu, duyệt và chỉnh mà không cần hiểu tiếng Anh.
- story_strategy, continuity_bible và detailed_script là bản dùng cho sản xuất theo ngôn ngữ video đã chọn; nếu video là tiếng Anh thì viết các field này bằng tiếng Anh.
- Không được bỏ trống bản tiếng Việt. Mỗi bản tiếng Việt phải giải thích cùng nội dung với bản sản xuất, không chỉ tóm tắt một dòng.
- english_narration của mỗi scene phải là voiceover đủ dài để tạo giọng đọc tự nhiên: thường 2-3 câu ngắn hoặc khoảng 18-35 từ tùy target_duration_seconds; không viết một tagline/câu cụt vài từ.
- Giữ ý chính, điều bắt buộc và điều cần tránh của người dùng.
- Tạo hook, xung đột/vấn đề chính, emotional arc, các điểm thú vị, cao trào nhỏ và payoff.
- Tạo retention_plan có cấu trúc: hook_0_2s, viewer_question, curiosity_gap, beat_curve theo timeline, pattern_interrupts, payoff_plan và dropoff_risks.
- Tạo sound_design_plan toàn project: review_vi viết bằng tiếng Việt tự nhiên cho UI duyệt, cùng music_mood, energy_curve, ambience_bed, sound_cues, silence_drops và mixing_notes cho chỉ dẫn dựng; không được nói MP4 đã có SFX/BGM thật.
- Tạo continuity bible để giữ nhân vật, trang phục, đạo cụ, bối cảnh, tone màu, mood và camera style nhất quán từ đầu đến cuối.
- vietnamese_description phải bằng tiếng Việt để người dùng hiểu.
- Mỗi scene bắt buộc có 5 trường chi tiết để truyền xuống shot/prompt video; có thể dùng thuật ngữ kỹ thuật tiếng Anh cho camera/visual nếu hữu ích, nhưng không được đổi ngôn ngữ narration của video:
  1. character_appearance: nhân vật trông như thế nào, gồm tóc, kính, dáng người, biểu cảm, đặc điểm nhận diện.
  2. wardrobe_and_sandals: trang phục và sandals/footwear thật cụ thể, gồm màu sắc, kiểu dáng, chất liệu, lace/bow/strap nếu có; nếu không thấy sandals thì ghi rõ footwear/sandals not visible.
  3. subject_motion_by_duration: hành động chính của subject theo thời lượng mỗi shot mà user đã nhập/chọn ({_shot_duration_preference(project)}); chỉ một hành động rõ, quay được bằng video AI.
  4. setting_and_lighting: bối cảnh, thời điểm, nguồn sáng, hướng sáng, màu ánh sáng, contrast và atmosphere.
  5. detailed_mood: cảm xúc/mood chi tiết, biểu cảm, năng lượng, nhịp cảm xúc của cảnh.
- Chia thành scene lớn; chưa tạo shot ở bước này.
- Không dùng tool/command, không đọc file trong project, không giải thích quá trình; schema đã được truyền qua output_schema.
- Chỉ trả về đúng JSON theo schema, không thêm markdown.
""".strip()
    raw_plan: dict | None = None
    normalized_plan: dict | None = None
    try:
        raw_plan = _run_structured_codex(db, project, prompt, STORY_DEVELOPMENT_SCHEMA, step_name="story_development")
        normalized_plan = _normalize_story_development_payload(raw_plan)
        plan = StoryDevelopmentPlan.model_validate(normalized_plan)
        retention_quality = _validate_story_creative_output(raw_plan, plan, project)
    except ai_planning.AIPlanningError as exc:
        if not _phase2_should_use_provider_fallback(exc):
            raise
        raw_plan = _fallback_story_development_payload(project, db, fallback_reason=str(exc))
        normalized_plan = _normalize_story_development_payload(raw_plan)
        plan = StoryDevelopmentPlan.model_validate(normalized_plan)
        retention_quality = {
            "passed": True,
            "missing_fields": [],
            "fallback_used": True,
            "fallback_reason": str(exc)[:1000],
        }
        video_observability.log_event(
            db,
            step_name="story_development_fallback",
            status="warning",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "CODEX_EXEC_TIMEOUT"),
            exc=exc,
            message="Provider story development lỗi/chậm; dùng fallback nội bộ từ source blocks.",
        )
    except ValidationError as exc:
        video_observability.log_event(
            db,
            step_name="story_development_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_STORY_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_plan or {}),
                "normalized_field_types": _payload_type_summary(normalized_plan or {}),
            },
            validation_errors=exc.errors(),
            message="AI trả về kịch bản không đúng cấu trúc.",
        )
        raise VideoPlanningValidationError("AI trả về kịch bản không đúng cấu trúc.") from exc
    except VideoPlanningValidationError as exc:
        video_observability.log_event(
            db,
            step_name="story_development_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_STORY_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_plan or {}),
                "normalized_field_types": _payload_type_summary(normalized_plan or {}),
            },
            validation_errors=_validation_errors_from_exception(exc),
            message=str(exc),
        )
        raise

    now = datetime.utcnow()
    old_shots = ordered_shots(project_id, db)
    old_shot_ids = [shot.id for shot in old_shots]
    if old_shot_ids:
        old_prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(old_shot_ids)).all()
        for old_prompt in old_prompts:
            video_storage.remove_artifact_file(old_prompt.prompt_path)
        db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id.in_(old_shot_ids)).delete(synchronize_session=False)
        db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id).delete(synchronize_session=False)
    db.query(DBVideoScene).filter(DBVideoScene.project_id == project_id).delete(synchronize_session=False)

    reference_label = _video_language_reference_label(project)
    story_strategy = _bilingual_planning_text(plan.story_strategy_vi, plan.story_strategy, reference_label=reference_label)
    continuity_bible = _bilingual_planning_text(plan.continuity_bible_vi, plan.continuity_bible, reference_label=reference_label)
    detailed_script = _bilingual_planning_text(plan.detailed_script_vi, plan.detailed_script, reference_label=reference_label)
    retention_payload = {
        **plan.retention_plan.model_dump(),
        "quality_check": retention_quality,
    }
    character_flow = video_series_characters.build_story_character_flow(project, db, normalized_plan or {})
    if character_flow is not None:
        retention_payload[video_series_characters.CHARACTER_FLOW_KEY] = character_flow

    project.phase = "phase2"
    project.input_synthesis = plan.input_synthesis
    project.story_strategy = story_strategy
    project.continuity_bible = continuity_bible
    project.detailed_script = detailed_script
    project.retention_plan_json = retention_payload
    project.sound_design_plan_json = plan.sound_design_plan.model_dump()
    project.creative_brief = story_strategy
    project.script_text = detailed_script
    project.style_bible = continuity_bible
    project.story_approved = False
    project.script_approved = False
    project.planning_status = "story_ready"
    project.planning_error = None
    project.status = "story_ready"
    project.updated_at = now
    video_state.mark_package_stale(project, db)

    for index, scene in enumerate(plan.scenes, start=1):
        db.add(
            DBVideoScene(
                id=str(uuid.uuid4()),
                project_id=project_id,
                scene_order=index,
                title=scene.title,
                dialogue=scene.english_narration,
                visual_description=_story_scene_visual_description(scene),
                target_duration_seconds=scene.target_duration_seconds,
                approved=True,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    from . import video_projects

    return video_projects.get_project(project_id, db)

def approve_story(project_id: str, approved: bool, db: Session) -> models.VideoProjectResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    project.story_approved = approved
    project.script_approved = approved
    project.status = "story_approved" if approved else "story_ready"
    project.planning_status = project.status
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    from . import video_projects

    return video_projects._project_response(project, db)

def _variation_scene_key(shot: DBVideoShot | ShotPlan) -> str:
    return str(getattr(shot, "scene_id", None) or getattr(shot, "scene_order", "project"))

def _group_shots_for_variation(shots: list[DBVideoShot] | list[ShotPlan]) -> dict[str, list]:
    by_scene: dict[str, list] = {}
    for shot in shots:
        by_scene.setdefault(_variation_scene_key(shot), []).append(shot)
    return by_scene

def _variation_field_count(scene_shots: list) -> int:
    varied_fields = 0
    for field in SHOT_VARIATION_FIELDS:
        values = {(getattr(shot, field, "") or "").strip().lower() for shot in scene_shots}
        if len([value for value in values if value]) >= 2:
            varied_fields += 1
    return varied_fields

def _enrich_segment_shot_variation(shots: list[ShotPlan]) -> bool:
    changed = False
    for scene_shots in _group_shots_for_variation(shots).values():
        if len(scene_shots) <= 1 or _variation_field_count(scene_shots) >= 2:
            continue
        ordered_scene_shots = sorted(scene_shots, key=lambda shot: getattr(shot, "shot_order", 0) or 0)
        for index, shot in enumerate(ordered_scene_shots):
            profile = SEGMENT_CAMERA_VARIATION_PROFILES[index % len(SEGMENT_CAMERA_VARIATION_PROFILES)]
            shot.camera_angle = profile["camera_angle"]
            shot.framing = profile["framing"]
            shot.camera_motion = profile["camera_motion"]
            if not (shot.shot_type or "").strip():
                shot.shot_type = profile["shot_type"]
            current_composition = (shot.composition or "").strip()
            segment_composition = profile["composition"]
            shot.composition = (
                f"{current_composition}; {segment_composition}" if current_composition else segment_composition
            )[:4000]
            changed = True
    return changed

def validate_shot_variation(shots: list[DBVideoShot] | list[ShotPlan]) -> bool:
    by_scene = _group_shots_for_variation(shots)
    for scene_shots in by_scene.values():
        if len(scene_shots) <= 1:
            continue
        if _variation_field_count(scene_shots) < 2:
            return False
    return True

def _shot_retention_metadata(shot: ShotPlan) -> dict[str, Any]:
    return {
        "retention_role": shot.retention_role or "story beat",
        "open_loop": shot.open_loop or "Keep the viewer waiting for the next visual or narrative payoff.",
        "visual_surprise": shot.visual_surprise or "Use a visual change before the shot feels static.",
        "cut_reason": shot.cut_reason or "Cut on action, emotion, narration, or sound cue.",
        "visible_characters": _json_safe(shot.visible_characters),
    }

def _model_dump(value: BaseModel | dict | None) -> dict:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}

def _shot_retainability_quality(shot: ShotPlan | DBVideoShot, *, is_first: bool = False, is_final: bool = False) -> dict[str, object]:
    retention = (
        _model_dump(getattr(shot, "retention_json", None))
        if isinstance(shot, DBVideoShot)
        else {
            "retention_role": shot.retention_role,
            "open_loop": shot.open_loop,
            "visual_surprise": shot.visual_surprise,
            "cut_reason": shot.cut_reason,
        }
    )
    transition = _model_dump(getattr(shot, "transition_json", None)) if isinstance(shot, DBVideoShot) else _model_dump(shot.transition_pack)
    sound = _model_dump(getattr(shot, "sound_design_json", None)) if isinstance(shot, DBVideoShot) else _model_dump(shot.sound_design)
    narration = (getattr(shot, "english_narration", "") or "").strip()
    duration = float(getattr(shot, "duration_seconds", 0) or 0)
    missing: list[str] = []
    warnings: list[str] = []
    if is_first and not (retention.get("visual_surprise") or retention.get("open_loop")):
        missing.append("hook_0_2s")
    if not retention.get("retention_role"):
        missing.append("retention_role")
    if not transition.get("transition_type"):
        missing.append("transition_type" if not is_final else "final_hold")
    if not transition.get("edit_reason"):
        missing.append("cut_reason")
    sound_cues = sound.get("sound_cues") if isinstance(sound, dict) else []
    if not sound_cues:
        missing.append("sound_cues")
    if narration and not sound.get("mixing_notes"):
        missing.append("mixing_notes")
        warnings.append("audio_clutter_risk")
    if duration >= 8 and not retention.get("visual_surprise") and not sound_cues:
        warnings.append("long_static_span_risk")
    return {
        "passed": not missing,
        "missing_fields": missing,
        "warnings": warnings,
        "weak_hook_risk": "hook_0_2s" in missing,
        "audio_clutter_risk": "audio_clutter_risk" in warnings,
        "long_static_span_risk": "long_static_span_risk" in warnings,
    }

def _finalize_shot_creative_direction(shots: list[ShotPlan]) -> None:
    for index, shot in enumerate(shots):
        final = index == len(shots) - 1
        if not (shot.transition_pack.transition_type or "").strip() or final:
            shot.transition_pack = TransitionPackPlan.model_validate(
                _normalize_transition_payload(
                    shot.transition_pack.model_dump() if (shot.transition_pack.transition_type or "").strip() and not final else shot.transition_to_next,
                    final=final,
                    fallback=shot.transition_to_next,
                )
            )
        if not (shot.retention_role or "").strip():
            roles = ["cold open", "setup", "build-up", "pattern interrupt", "climax", "payoff"]
            shot.retention_role = roles[min(index, len(roles) - 1)]
        if not (shot.visual_surprise or "").strip():
            shot.visual_surprise = "Change camera scale, motion, or visual detail before the segment feels static."
        if not (shot.cut_reason or "").strip():
            shot.cut_reason = shot.transition_pack.edit_reason or "Cut on action, emotion, narration, or sound cue."
        if not shot.sound_design.sound_cues:
            shot.sound_design = SoundDesignPlan.model_validate(
                _normalize_sound_payload(None, has_narration=bool((shot.english_narration or "").strip()), fallback=shot.transition_pack.transition_sfx)
            )

def _retention_quality_check(plan: RetentionDirectionPlan, project: DBVideoProject) -> dict[str, object]:
    missing: list[str] = []
    warnings: list[str] = []
    if not plan.hook_0_2s.strip():
        missing.append("hook_0_2s")
    if not plan.viewer_question.strip():
        missing.append("viewer_question")
    if not plan.curiosity_gap.strip():
        missing.append("curiosity_gap")
    if not plan.beat_curve:
        missing.append("beat_curve")
    if not plan.pattern_interrupts:
        missing.append("pattern_interrupts")
    if not plan.payoff_plan.strip():
        missing.append("payoff_plan")
    if not plan.dropoff_risks:
        missing.append("dropoff_risks")
    if project.target_duration_seconds:
        for beat in plan.beat_curve:
            if beat.end_seconds and beat.end_seconds > project.target_duration_seconds:
                warnings.append("beat_exceeds_target_duration")
    return {"passed": not missing, "missing_fields": missing, "warnings": warnings}

def _validate_shot_micro_scene_output(plan: ShotBreakdownPlan, project: DBVideoProject) -> None:
    config = _resolve_prompt_segment_config(project)
    if config.segment_count is None:
        return
    missing: list[str] = []
    for shot_index, shot in enumerate(plan.shots, start=1):
        if len(shot.micro_scenes) != config.micro_scenes_per_prompt:
            missing.append(f"shots[{shot_index}].micro_scenes")
            continue
        for micro_scene in shot.micro_scenes:
            if micro_scene.end_seconds <= micro_scene.start_seconds:
                missing.append(f"shots[{shot_index}].micro_scenes[{micro_scene.order}].time_range")
            if not (micro_scene.description_vi or micro_scene.visual_action).strip():
                missing.append(f"shots[{shot_index}].micro_scenes[{micro_scene.order}].visual_action")
    _raise_missing_required_output("micro-scenes", missing)

def generate_shots(project_id: str, db: Session) -> list[models.VideoShotResponse] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if not project.story_approved:
        raise VideoPlanningValidationError("Cần duyệt kịch bản trước khi tạo shot.")
    scenes = _ordered_scenes(project_id, db)
    scene_lines = "\n".join(
        f"Scene {scene.scene_order}: {scene.title or ''}\nMô tả cho người dùng: {scene.visual_description or ''}\nNarration theo ngôn ngữ video: {scene.dialogue or ''}\nTarget duration: {scene.target_duration_seconds or 'auto'}s"
        for scene in scenes
    )
    target_segment_count = _target_prompt_segment_count(project)
    segment_config = _resolve_prompt_segment_config(project)
    locked_segment_count = db.query(func.count(DBVideoShot.id)).filter(
        DBVideoShot.project_id == project_id,
        DBVideoShot.locked.is_(True),
    ).scalar() or 0
    if target_segment_count is not None and locked_segment_count > target_segment_count:
        raise VideoPlanningValidationError(
            f"Project đang có {locked_segment_count} segment đã khóa, vượt cấu hình {target_segment_count} prompt. Hãy mở khóa segment dư rồi tạo lại."
        )
    segments_to_generate = (
        max(0, target_segment_count - locked_segment_count) if target_segment_count is not None else None
    )
    if segments_to_generate == 0:
        old_unlocked_ids = [shot.id for shot in ordered_shots(project_id, db) if not shot.locked]
        if old_unlocked_ids:
            _delete_shots_with_artifacts(project_id, old_unlocked_ids, db)
            video_rendering.mark_render_outputs_stale(project_id, db)
            video_state.mark_package_stale(project, db)
            db.commit()
        return [_shot_response(row) for row in ordered_shots(project_id, db)]
    segment_instruction = (
        f"- Tạo đúng {segments_to_generate} prompt segment mới vì video mục tiêu dài {segment_config.target_duration_seconds or project.target_duration_seconds} giây.\n"
        f"- Toàn video có {target_segment_count} segment; {locked_segment_count} segment đầu có thể đã khóa, các segment mới vẫn phải nối tiếp đúng thứ tự Segment X of {target_segment_count}.\n"
        f"- Mỗi segment tương ứng đúng 1 prompt tạo video {segment_config.prompt_duration_seconds} giây.\n"
        f"- Mỗi segment phải có đúng {segment_config.micro_scenes_per_prompt} micro_scenes có cấu trúc.\n"
        f"- duration_seconds là thời lượng dùng khi ghép timeline: {segment_config.prompt_duration_seconds} giây cho segment đầy đủ, "
        f"segment cuối dùng phần dư nếu thời lượng không chia hết cho {segment_config.prompt_duration_seconds}.\n"
        f"- Bên trong mỗi segment phải có đúng {segment_config.micro_scenes_per_prompt} cảnh nhỏ theo timeline rõ ràng; vẫn phải là một prompt liền mạch."
        if target_segment_count is not None
        else "- Nếu chưa có thời lượng mục tiêu, tự chọn số shot theo nội dung; mỗi shot vẫn nằm trong 1-5 giây."
    )
    micro_scene_example = _micro_scene_timeline_text(
        [
            {
                "start_seconds": start,
                "end_seconds": end,
                "description_vi": "mô tả cảnh nhỏ bằng tiếng Việt",
                "visual_action": "visual action",
                "camera_note": "camera note",
                "continuity_note": "continuity note",
            }
            for start, end in _micro_scene_ranges(segment_config.prompt_duration_seconds, segment_config.micro_scenes_per_prompt)
        ]
    )
    prompt = f"""
Bạn là editor điện ảnh tạo shot breakdown cho video AI.

{_project_context(project, db)}

{video_series_characters.shot_breakdown_instructions(project)}

Story strategy:\n{project.story_strategy or ''}

Continuity bible:\n{project.continuity_bible or ''}

Retention map:\n{json.dumps(project.retention_plan_json or {}, ensure_ascii=False)}

Sound design plan:\n{json.dumps(project.sound_design_plan_json or {}, ensure_ascii=False)}

Detailed script:\n{project.detailed_script or project.script_text or ''}

Scenes đã duyệt:\n{scene_lines}

Yêu cầu bắt buộc:
- {video_language.viewer_language_instruction(project.target_language)}
- {video_language.narration_field_note(project.target_language)}
- {_purpose_generation_instructions(project)}
- {_shot_duration_preference(project)}.
{segment_instruction}
- Với mode prompt segment, không tạo các shot rời thành câu chuyện riêng; mỗi segment phải nối tiếp segment trước/sau.
- Với mode prompt segment, mỗi segment có một mục tiêu rõ: hook, build-up, obstacle, climax, payoff hoặc transition.
- Scene dài phải tách thành nhiều prompt segment hoặc shot đủ nhịp; không để scene chỉ có một góc quay nếu có nhiều ý hình ảnh.
- Mỗi shot/segment chỉ có một hành động chính nhìn thấy rõ. Không gom nhiều hành động chính như hất tay + nhân vật rơi + hồi tưởng + chuyển cảnh mới vào cùng một shot.
- Nếu một scene có nhiều hành động chính, phải tách thành nhiều shot/segment nhỏ theo thứ tự thời gian; chỉ giữ lại các micro-scenes phụ trợ cho cùng một hành động chính trong một segment.
- Thời lượng shot/segment phải khớp với nội dung: shot ngắn 3-5 giây chỉ đủ một hành động chính; prompt segment dài hơn có thể có micro-scenes nhưng không đổi sang hành động chính khác.
- Với mode prompt segment, vietnamese_description phải là bản tiếng Việt để duyệt: mô tả đủ {segment_config.micro_scenes_per_prompt} cảnh nhỏ kèm mốc thời gian trong segment.
- Trả micro_scenes theo contract chuẩn: order, start_seconds, end_seconds, description_vi, visual_action, camera_note, continuity_note.
- Timeline micro_scenes phải phủ đúng 0-{segment_config.prompt_duration_seconds}s của từng prompt. Gợi ý range cho mỗi segment:\n{micro_scene_example}
- Nếu english_narration/narration của segment dùng tiếng Anh hoặc ngôn ngữ khác tiếng Việt, vietnamese_description phải giải thích nội dung narration đó bằng tiếng Việt để người dùng hiểu đoạn voice đang nói gì.
- vietnamese_description cũng phải nêu hành động chính, camera/chuyển cảnh, mood và continuity để người dùng Việt hiểu segment đang làm gì mà không cần đọc prompt tiếng Anh.
- Thay đổi shot type, camera angle, framing, composition và camera movement liên tục để nhịp dựng nhanh, không nhàm chán.
- Mỗi shot/segment phải có retention_role, open_loop, visual_surprise và cut_reason để giải thích cách giữ chân người xem.
- Mỗi shot/segment phải có transition_pack gồm transition_type, trigger, timing, edit_reason, transition_sfx và continuity_risk; shot cuối dùng final hold/payoff thay vì chuyển sang shot tiếp theo.
- Mỗi shot/segment phải có sound_design gồm music_mood, energy_curve, ambience_bed, sound_cues, silence_drops và mixing_notes; SFX/BGM là chỉ dẫn dựng nếu chưa có asset audio thật.
- Mỗi shot phải kế thừa và cụ thể hóa 5 chi tiết trong scene: character appearance, wardrobe and sandals, subject motion căn theo duration_seconds thật của shot, setting and lighting, detailed mood.
- Tạo transition_to_next rõ ràng, phù hợp continuity bible.
- vietnamese_description giải thích cho người dùng Việt; english_narration chứa narration theo ngôn ngữ video đã chọn.
- Mỗi shot có lời nói phải trả `speech_cues`: từng câu thoại chính xác, speaker_name, character_profile_id nếu có, speaker_role, voice_description, delivery, emotion, context và lip_sync_required.
- `speech_cues[].text` phải đúng ngôn ngữ video đã chọn và không được diễn giải hoặc dịch khác với câu nhân vật sẽ nói.
- Với nhân vật thuộc series, voice_description phải kế thừa canonical speech_style/giọng nói và personality; delivery/emotion/context chỉ mô tả trạng thái tạm thời của đúng shot.
- Nếu người nói hiện trong khung hình, đặt lip_sync_required=true và mô tả hành động/bối cảnh lúc nói; nếu là voice-over ngoài hình, đặt speaker_role=offscreen_narrator và lip_sync_required=false.
{('- Vì ngôn ngữ video là tiếng Việt, các speech_cues này sẽ được nối vào prompt Veo 3 để clip tự render giọng Việt; phải có câu thoại tiếng Việt chính xác và đủ mô tả giọng cho mọi shot có lời.' if video_speech.uses_veo_native_speech(project) else '- Audio của ngôn ngữ này vẫn dùng pipeline voice/TTS hiện tại của dự án; speech_cues chỉ là metadata nội dung và không cho Veo tự tạo lời nói.')}
- {_narration_length_instruction(project)}
- Không dùng tool/command, không đọc file trong project, không giải thích quá trình; schema đã được truyền qua output_schema.
- Chỉ trả về đúng JSON theo schema, không thêm markdown.
    """.strip()
    raw_plan: dict | None = None
    normalized_plan: dict | None = None
    sound_fallback_fields: list[str] = []
    try:
        raw_plan = _run_structured_codex(db, project, prompt, SHOT_BREAKDOWN_SCHEMA, step_name="shot_breakdown")
        normalized_plan = _normalize_shot_breakdown_payload(raw_plan, dialogue_mode=project.dialogue_mode)
        plan = ShotBreakdownPlan.model_validate(normalized_plan)
        _validate_shot_order_output(
            plan,
            valid_scene_orders={scene.scene_order for scene in scenes} or {1},
            expected_count=segments_to_generate,
            first_shot_order=1 + locked_segment_count,
        )
        for index, shot in enumerate(plan.shots, start=1 + locked_segment_count):
            _fit_micro_scenes_to_config(shot, project, shot_order=index)
        _finalize_shot_creative_direction(plan.shots)
        sound_fallback_fields = _shot_sound_fallback_fields(raw_plan)
        _validate_shot_creative_output(raw_plan, plan)
        _validate_shot_micro_scene_output(plan, project)
    except ai_planning.AIPlanningError as exc:
        if not _phase2_should_use_provider_fallback(exc):
            raise
        raw_plan = _fallback_shot_breakdown_payload(
            project,
            scenes,
            fallback_reason=str(exc),
            segment_count=segments_to_generate,
            first_shot_order=1 + locked_segment_count,
        )
        normalized_plan = _normalize_shot_breakdown_payload(raw_plan, dialogue_mode=project.dialogue_mode)
        plan = ShotBreakdownPlan.model_validate(normalized_plan)
        _validate_shot_order_output(
            plan,
            valid_scene_orders={scene.scene_order for scene in scenes} or {1},
            expected_count=segments_to_generate,
            first_shot_order=1 + locked_segment_count,
        )
        for index, shot in enumerate(plan.shots, start=1 + locked_segment_count):
            _fit_micro_scenes_to_config(shot, project, shot_order=index)
        _finalize_shot_creative_direction(plan.shots)
        sound_fallback_fields = []
        _validate_shot_creative_output(raw_plan, plan)
        _validate_shot_micro_scene_output(plan, project)
        video_observability.log_event(
            db,
            step_name="shot_breakdown_fallback",
            status="warning",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "CODEX_EXEC_TIMEOUT"),
            exc=exc,
            message="Provider shot breakdown lỗi/chậm; dùng fallback nội bộ từ scenes đã duyệt.",
        )
    except ValidationError as exc:
        video_observability.log_event(
            db,
            step_name="shot_breakdown_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_SHOT_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_plan or {}),
                "normalized_field_types": _payload_type_summary(normalized_plan or {}),
                "raw_shot_count": len(raw_plan.get("shots", [])) if isinstance(raw_plan, dict) and isinstance(raw_plan.get("shots"), list) else 0,
                "normalized_shot_count": len(normalized_plan.get("shots", [])) if isinstance(normalized_plan, dict) and isinstance(normalized_plan.get("shots"), list) else 0,
            },
            validation_errors=exc.errors(),
            message="AI trả về shot không đúng cấu trúc.",
        )
        raise VideoPlanningValidationError("AI trả về shot không đúng cấu trúc.") from exc
    except VideoPlanningValidationError as exc:
        video_observability.log_event(
            db,
            step_name="shot_breakdown_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_SHOT_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_plan or {}),
                "normalized_field_types": _payload_type_summary(normalized_plan or {}),
                "raw_shot_count": len(_raw_items_from_payload(raw_plan or {}, "shots", "segments", "prompt_segments", "video_segments", "segment_breakdown")),
                "normalized_shot_count": len(normalized_plan.get("shots", [])) if isinstance(normalized_plan, dict) else 0,
            },
            validation_errors=_validation_errors_from_exception(exc),
            message=str(exc),
        )
        raise
    if not validate_shot_variation(plan.shots) and target_segment_count is not None:
        enriched = _enrich_segment_shot_variation(plan.shots)
        video_observability.log_event(
            db,
            step_name="shot_variation_validation",
            status="warning",
            project_id=project_id,
            error_code="VIDEO_SHOT_VARIATION_ENRICHED" if enriched else "VIDEO_SHOT_VARIATION_LOW_ALLOWED",
            technical_details={
                "target_segment_count": target_segment_count,
                "shot_count": len(plan.shots),
                "enriched": enriched,
                "valid_after_enrichment": validate_shot_variation(plan.shots),
            },
            message="Shot segment bị lặp metadata camera; backend đã tự bổ sung biến thể và tiếp tục.",
        )
    if not validate_shot_variation(plan.shots) and target_segment_count is None:
        video_observability.log_event(
            db,
            step_name="shot_variation_validation",
            status="failure",
            project_id=project_id,
            error_code="VIDEO_SHOT_VARIATION_TOO_LOW",
            message="Shot bị lặp góc máy hoặc bố cục quá nhiều.",
        )
        raise VideoPlanningValidationError("Shot bị lặp góc máy hoặc bố cục quá nhiều. Hãy tạo lại để có nhiều chuyển cảnh hơn.")

    scene_by_order = {scene.scene_order: scene for scene in scenes}
    now = datetime.utcnow()
    old_unlocked = [shot for shot in ordered_shots(project_id, db) if not shot.locked]
    old_ids = [shot.id for shot in old_unlocked]
    _delete_shots_with_artifacts(project_id, old_ids, db)

    rows: list[DBVideoShot] = []
    existing_locked_count = db.query(func.count(DBVideoShot.id)).filter(DBVideoShot.project_id == project_id).scalar() or 0
    for index, item in enumerate(plan.shots, start=1 + existing_locked_count):
        scene = scene_by_order.get(item.scene_order)
        quality = _shot_retainability_quality(item, is_first=index == 1, is_final=index == existing_locked_count + len(plan.shots))
        row = DBVideoShot(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=scene.id if scene else None,
            shot_order=index,
            duration_seconds=_clamp_shot_duration(item.duration_seconds, project, shot_order=index),
            vietnamese_description=item.vietnamese_description,
            english_narration=item.english_narration,
            primary_action=item.primary_action,
            purpose=item.purpose,
            shot_type=item.shot_type,
            camera_angle=item.camera_angle,
            framing=item.framing,
            composition=item.composition,
            camera_motion=item.camera_motion,
            subject_motion=item.subject_motion,
            environment_motion=item.environment_motion,
            transition_to_next=item.transition_to_next,
            retention_json=_shot_retention_metadata(item),
            transition_json=item.transition_pack.model_dump(),
            sound_design_json=item.sound_design.model_dump(),
            micro_scenes_json=[micro_scene.model_dump() for micro_scene in item.micro_scenes],
            speech_cues_json=[cue.model_dump() for cue in item.speech_cues],
            retainability_quality_check=quality,
            status="ready",
            prompt_status="missing",
            voice_status="missing" if item.english_narration.strip() else "skipped",
            subtitle_status="stale",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows.append(row)
    project.status = "shots_ready"
    project.planning_status = "shots_ready"
    video_rendering.mark_render_outputs_stale(project_id, db)
    video_state.mark_package_stale(project, db)
    from . import video_publishing_metadata

    video_publishing_metadata.mark_publishing_metadata_stale(
        project_id,
        db,
        reason="Danh sách segment hoặc narration đã thay đổi.",
    )
    db.commit()
    for row in rows:
        db.refresh(row)
    if sound_fallback_fields:
        video_observability.log_event(
            db,
            step_name="shot_breakdown_validation",
            status="warning",
            project_id=project_id,
            error_code="AI_VIDEO_MAPPING_FALLBACK_APPLIED",
            technical_details={"fallback_fields": sound_fallback_fields},
            validation_errors=[{"loc": field, "msg": "Đã dùng fallback an toàn"} for field in sound_fallback_fields],
            message="AI thiếu silence_drops trong sound_design; backend đã dùng fallback an toàn.",
        )
    return [_shot_response(row) for row in ordered_shots(project_id, db)]

def update_shot(project_id: str, shot_id: str, data: models.VideoShotUpdate, db: Session) -> models.VideoShotResponse | None:
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if shot is None:
        return None
    changed = data.model_dump(exclude_unset=True)
    for key, value in changed.items():
        if key == "micro_scenes":
            shot.micro_scenes_json = value or []
        elif key == "speech_cues":
            shot.speech_cues_json = [
                item.model_dump() if isinstance(item, BaseModel) else item
                for item in (value or [])
            ]
        else:
            setattr(shot, key, value)
    prompt_affecting_fields = {
        "english_narration",
        "duration_seconds",
        "vietnamese_description",
        "primary_action",
        "camera_angle",
        "framing",
        "composition",
        "camera_motion",
        "retention_json",
        "transition_json",
        "sound_design_json",
        "micro_scenes",
        "speech_cues",
        "speech_source_override",
        "retainability_quality_check",
    }
    if any(key in changed for key in prompt_affecting_fields):
        shot.prompt_status = "stale"
        if any(key in changed for key in {"english_narration", "duration_seconds", "speech_cues", "speech_source_override"}):
            shot.subtitle_status = "stale"
            from . import video_subtitles

            video_subtitles.mark_subtitle_stale(
                project_id,
                db,
                reason="Nội dung lời thoại hoặc timing segment đã thay đổi.",
            )
        if "english_narration" in changed:
            shot.voice_status = "missing" if (shot.english_narration or "").strip() else "skipped"
    shot.updated_at = datetime.utcnow()
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is not None:
        if video_speech.uses_veo_native_speech(project, shot) and any(
            key in changed for key in prompt_affecting_fields
        ):
            db.query(DBVideoShotClip).filter(
                DBVideoShotClip.project_id == project_id,
                DBVideoShotClip.shot_id == shot_id,
                DBVideoShotClip.is_active.is_(True),
                DBVideoShotClip.status == "ready",
            ).update(
                {"status": "stale", "updated_at": datetime.utcnow()},
                synchronize_session=False,
            )
        video_rendering.mark_render_outputs_stale(project_id, db)
        video_state.mark_package_stale(project, db)
        if any(key in changed for key in prompt_affecting_fields):
            from . import video_publishing_metadata

            video_publishing_metadata.mark_publishing_metadata_stale(
                project_id,
                db,
                reason="Segment hoặc prompt dependency đã được chỉnh sửa.",
            )
    db.commit()
    db.refresh(shot)
    return _shot_response(shot)

def set_shot_locked(project_id: str, shot_id: str, locked: bool, db: Session) -> models.VideoShotResponse | None:
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if shot is None:
        return None
    shot.locked = locked
    shot.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(shot)
    return _shot_response(shot)

def _quality_check(item: VideoPromptPlan, *, duration_seconds: float | None = None) -> dict[str, object]:
    required = [
        "prompt",
        "prompt_explanation_vi",
        "negative_prompt",
        "duration_seconds",
        "aspect_ratio",
        "shot_type",
        "camera_angle",
        "framing",
        "composition",
        "camera_motion",
        "subject_motion",
        "environment_motion",
        "continuity_notes",
        "retention_notes",
        "transition_notes",
        "sound_design_notes",
    ]
    missing = [
        field
        for field in required
        if not (duration_seconds if field == "duration_seconds" else getattr(item, field, None))
    ]
    return {"passed": not missing, "missing_fields": missing}

def speech_prompt_quality(project: DBVideoProject, shot: DBVideoShot, content: str) -> dict[str, object]:
    """Gate provider copy when an explicit speech cue is absent from content."""
    expected = video_speech.spoken_text_for_shot(shot, project)
    mode = video_speech.speech_mode_for(project, shot)
    required = mode in {"veo_narration", "veo_dialogue"} and bool(expected)
    present = not required or expected.casefold() in (content or "").casefold()
    return {"passed": present, "needs_review": required and not present, "reason_vi": None if present else f"Shot {getattr(shot, 'shot_order', '?')} có lời thoại nhưng prompt chưa chứa đúng câu thoại."}

def _segment_prompt_prefix(project: DBVideoProject, shot: DBVideoShot, *, duration_seconds: float) -> str:
    config = _resolve_prompt_segment_config(project)
    if config.segment_count is None:
        return ""
    timeline = _segment_timeline_label(project, shot.shot_order)
    final_hint = ""
    if duration_seconds < config.prompt_duration_seconds:
        final_hint = (
            f" The first {duration_seconds:g} seconds must contain the usable ending; "
            "any remaining generated time should be a clean hold or gentle extension for trimming."
        )
    micro_timeline = _micro_scene_timeline_text(shot.micro_scenes_json or [])
    return (
        f"Create a {config.prompt_duration_seconds}-second {project.aspect_ratio} high-quality stylized 3D cinematic animation video.\n"
        f"This is segment {shot.shot_order} of {config.segment_count} of a {config.target_duration_seconds or project.target_duration_seconds}-second video "
        f"covering timeline {timeline}.{final_hint}\n"
        "3D visual rule: use dimensional characters, depth, volumetric lighting, textured materials, parallax, "
        "and real camera movement; translate any manga, webtoon, illustration, image, or 2D reference into a 3D animated video look, "
        "not a flat/static image.\n"
        f"{video_series_characters.segment_continuity_rule(project)}\n"
        "Animation and text-safe rule: align visible action beats with the usable duration, use clear entry/hold/exit motion, "
        "and do not render subtitles, captions, karaoke lyrics, text overlays, letters, words, UI text, logos, or watermarks.\n"
        f"Segment structure: use exactly {config.micro_scenes_per_prompt} connected micro-scenes inside this one prompt, all serving one primary visual action.\n"
        f"Micro-scene timeline:\n{micro_timeline}"
    )

def _segment_aware_prompt_text(item: VideoPromptPlan, shot: DBVideoShot, project: DBVideoProject, *, duration_seconds: float) -> str:
    prompt = item.prompt.strip()
    prefix = _segment_prompt_prefix(project, shot, duration_seconds=duration_seconds)
    if not prefix:
        return prompt
    lowered = prompt.lower()
    has_segment = f"segment {shot.shot_order}" in lowered and "of" in lowered
    configured_duration = _resolve_prompt_segment_config(project).prompt_duration_seconds
    has_duration = f"{configured_duration}-second" in lowered or f"{configured_duration} second" in lowered or f"{configured_duration}s" in lowered
    if project.series_id:
        has_continuity = "approved episode cast" in lowered or "episode-only guests" in lowered
    else:
        has_continuity = "same character" in lowered or "same main character" in lowered
    if has_segment and has_duration and has_continuity:
        return prompt
    return f"{prefix}\n\n{prompt}".strip()

def _prompt_text(prompt: VideoPromptPlan, shot: DBVideoShot, project: DBVideoProject) -> str:
    duration_seconds = _clamp_shot_duration(prompt.duration_seconds or shot.duration_seconds, project, shot_order=shot.shot_order)
    prompt_text = _segment_aware_prompt_text(prompt, shot, project, duration_seconds=duration_seconds)
    segment_count = _target_prompt_segment_count(project)
    visible_characters = []
    if isinstance(shot.retention_json, dict) and isinstance(shot.retention_json.get("visible_characters"), list):
        visible_characters = shot.retention_json.get("visible_characters") or []
    parts = [
        prompt_text,
        "",
        f"Video language: {video_language.video_language_english_name(project.target_language)}",
        f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}",
        f"Shot type: {prompt.shot_type or shot.shot_type or ''}",
        f"Camera angle: {prompt.camera_angle or shot.camera_angle or ''}",
        f"Framing: {prompt.framing or shot.framing or ''}",
        f"Composition: {prompt.composition or shot.composition or ''}",
        f"Camera movement: {prompt.camera_motion or shot.camera_motion or ''}",
        f"Subject motion: {prompt.subject_motion or shot.subject_motion or ''}",
        f"Environment motion: {prompt.environment_motion or shot.environment_motion or ''}",
        f"Start frame: {prompt.start_frame}",
        f"End frame: {prompt.end_frame}",
        f"Lighting: {prompt.lighting}",
        f"Mood: {prompt.mood}",
        f"Continuity notes: {prompt.continuity_notes}",
        f"Visible characters: {json.dumps(visible_characters, ensure_ascii=False)}" if project.series_id and visible_characters else "",
        f"Retention notes: {prompt.retention_notes}",
        f"Transition notes: {prompt.transition_notes}",
        f"Sound design notes: {prompt.sound_design_notes}",
    ]
    if segment_count is not None:
        config = _resolve_prompt_segment_config(project)
        parts[3:3] = [
            f"Segment: {shot.shot_order} of {segment_count}",
            f"Video generation clip length: {config.prompt_duration_seconds} seconds",
            f"Usable timeline duration: {duration_seconds:g} seconds",
            f"Timeline position: {_segment_timeline_label(project, shot.shot_order)}",
            "Micro-scene timeline:\n" + (_micro_scene_timeline_text(shot.micro_scenes_json or []) or ""),
        ]
    else:
        parts[3:3] = [f"Duration: {duration_seconds} seconds"]
    if prompt.negative_prompt.strip():
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.prompt_explanation_vi.strip():
        parts.extend(["", "Bản giải thích tiếng Việt:", prompt.prompt_explanation_vi.strip()])
    # Compose the audio policy at read time so manual Veo copy/download and
    # provider automation share one deterministic contract.
    mode = video_speech.speech_mode_for(project, shot)
    if mode:
        contract = video_speech.build_provider_prompt(
            "", mode, video_speech.speech_cues_for_shot(shot, project),
            prompt.negative_prompt, prompt.continuity_notes,
        )
        parts.extend(["", contract["audio_contract"]])
    return "\n".join(part for part in parts if part is not None).strip() + "\n"


def _prompt_pack_batches(
    shots: list[DBVideoShot],
    *,
    batch_size: int = VIDEO_PROMPT_BATCH_SIZE,
) -> list[list[DBVideoShot]]:
    """Partition an already ordered shot list without changing its source order."""
    size = max(1, int(batch_size))
    return [shots[index : index + size] for index in range(0, len(shots), size)]


def _prompt_pack_batch_idempotency_key(project: DBVideoProject, batch: list[DBVideoShot]) -> str:
    """Return a stable key for this exact project/shot batch input."""
    batch_input = ",".join(
        f"{shot.id}:{int(getattr(shot, 'revision', 1) or 1)}:{shot.shot_order}"
        for shot in batch
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"voicebox:video-prompt-pack:{project.id}:{batch_input}"))


def _video_prompt_shot_lines(
    shots: list[DBVideoShot],
    project: DBVideoProject,
    *,
    target_segment_count: int | None,
    segment_config: PromptSegmentConfig,
) -> str:
    return "\n".join(
        (
            f"Segment {shot.shot_order} of {target_segment_count}: timeline={_segment_timeline_label(project, shot.shot_order)}; "
            f"prompt_clip_duration={segment_config.prompt_duration_seconds}s; usable_duration={shot.duration_seconds or _usable_segment_duration(project, shot.shot_order)}s; "
            f"micro_scenes={json.dumps(shot.micro_scenes_json or [], ensure_ascii=False)}; "
            f"vi={shot.vietnamese_description or ''}; narration={shot.english_narration or ''}; speech_cues={json.dumps(shot.speech_cues_json or [], ensure_ascii=False)}; action={shot.primary_action or ''}; "
            f"camera={shot.camera_angle or ''}, {shot.framing or ''}, {shot.camera_motion or ''}; transition={shot.transition_to_next or ''}; "
            f"retention={json.dumps(shot.retention_json or {}, ensure_ascii=False)}; transition_pack={json.dumps(shot.transition_json or {}, ensure_ascii=False)}; sound={json.dumps(shot.sound_design_json or {}, ensure_ascii=False)}"
            if target_segment_count is not None
            else f"Shot {shot.shot_order}: duration={shot.duration_seconds or 3}s; vi={shot.vietnamese_description or ''}; narration={shot.english_narration or ''}; speech_cues={json.dumps(shot.speech_cues_json or [], ensure_ascii=False)}; action={shot.primary_action or ''}; camera={shot.camera_angle or ''}, {shot.framing or ''}, {shot.camera_motion or ''}; transition={shot.transition_to_next or ''}; retention={json.dumps(shot.retention_json or {}, ensure_ascii=False)}; transition_pack={json.dumps(shot.transition_json or {}, ensure_ascii=False)}; sound={json.dumps(shot.sound_design_json or {}, ensure_ascii=False)}"
        )
        for shot in shots
    )


def generate_video_prompt_pack(project_id: str, db: Session) -> models.VideoShotPromptPackResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    shots = [shot for shot in ordered_shots(project_id, db) if not shot.locked or shot.prompt_status != "completed"]
    if not shots:
        shots = ordered_shots(project_id, db)
    if not shots:
        raise VideoPlanningValidationError("Cần tạo shot trước khi tạo prompt video.")
    target_segment_count = _target_prompt_segment_count(project)
    segment_config = _resolve_prompt_segment_config(project)
    shot_lines = _video_prompt_shot_lines(
        shots,
        project,
        target_segment_count=target_segment_count,
        segment_config=segment_config,
    )
    prompt_batches = _prompt_pack_batches(shots)
    batch_shot_token = "<<VOICEBOX_VIDEO_PROMPT_BATCH_SHOTS>>"
    batch_count_token = "<<VOICEBOX_VIDEO_PROMPT_BATCH_COUNT>>"
    segment_continuity_requirement = (
        "dùng đúng approved episode cast và episode-only guests của tập; không dùng rule một nhân vật chính duy nhất."
        if project.series_id
        else "giữ continuity: same character / same style / same outfit / same story state."
    )
    segment_prompt_requirements = (
        f"- Tạo đúng {batch_count_token} prompt cho các segment được liệt kê, mỗi prompt ứng với nhãn Segment X of {target_segment_count}; không tạo nhiều prompt nhỏ hơn.\n"
        f"- Mỗi main prompt phải bắt đầu hoặc nêu rõ: Create a {segment_config.prompt_duration_seconds}-second {project.aspect_ratio} high-quality stylized 3D cinematic animation video.\n"
        f"- Mỗi prompt phải nhắc `This is segment X of N` và {segment_continuity_requirement}\n"
        f"- Mỗi prompt phải có timeline rõ ràng với đúng {segment_config.micro_scenes_per_prompt} micro-scene liên tục trong một clip {segment_config.prompt_duration_seconds}s, khớp micro_scenes đã liệt kê.\n"
        "- Cuối mỗi prompt phải có transition sang segment tiếp theo; segment cuối giữ final composition hoặc CTA.\n"
        f"- Nếu segment cuối có usable_duration dưới {segment_config.prompt_duration_seconds}s, prompt vẫn tạo clip {segment_config.prompt_duration_seconds}s nhưng phần usable phải nằm ở đầu clip để render có thể trim phần dư."
        if target_segment_count is not None
        else "- Mỗi prompt ứng với một shot đã duyệt."
    )
    reference_package: dict[str, Any] = {"reference_assets": [], "reference_asset_ids": [], "provider_report": {}}
    reference_instruction = ""
    if project.series_id:
        reference_package = series_references.build_reference_prompt_package(
            project.series_id,
            db,
            prompt_text="\n".join([project.title, project.topic, project.continuity_bible or "", project.style_bible or "", shot_lines]),
            provider="video-prompt-provider",
            provider_supports_references=False,
        )
        if reference_package.get("reference_assets"):
            reference_lines = [
                f"- {item.get('label') or item.get('id')}: {item.get('entity_type')} {item.get('entity_id')}, role={item.get('reference_role')}, rev={item.get('revision')}"
                for item in reference_package.get("reference_assets", [])
                if isinstance(item, dict)
            ]
            reference_instruction = (
                "Visual references đã duyệt chỉ dùng để giữ identity/canon; khi viết prompt phải chuyển hóa thành "
                "stylized 3D cinematic animation, không biến thành prompt ảnh tĩnh hoặc flat 2D panel "
                "(provider-neutral, chỉ dùng ID/metadata an toàn):\n" + "\n".join(reference_lines)
            )
    prompt = f"""
Bạn là chuyên gia prompt tạo video AI. Tạo prompt video dạng dùng chung, không nhắc tên provider cụ thể, và không được mâu thuẫn với ngôn ngữ video đã chọn.

{_project_context(project, db)}

{video_series_characters.video_prompt_instructions(project)}

Continuity bible:\n{project.continuity_bible or project.style_bible or ''}

{reference_instruction}

Shot/segment cần tạo prompt:\n{batch_shot_token}

Yêu cầu bắt buộc:
- {video_language.viewer_language_instruction(project.target_language)}
- {_purpose_generation_instructions(project)}
- Prompt phải là prompt tạo video, không phải prompt ảnh.
- Không nhắc Runway, Kling, Veo, Pika, Luma hoặc provider cụ thể.
{segment_prompt_requirements}
- Tất cả prompt video phải ưu tiên high-quality stylized 3D/cinematic 3D animation: nhân vật có khối, chiều sâu, volumetric lighting, vật liệu có độ dày, parallax và camera movement thật.
- Nếu source là truyện tranh, webtoon, manga, ảnh, illustration hoặc reference 2D thì chỉ dùng làm căn cứ visual/canon và phải chuyển hóa thành 3D animated video look; không giữ dạng flat 2D illustration, comic panel, storyboard frame hoặc static image.
- Mỗi prompt có đủ duration, aspect ratio, subject/action, shot type, camera angle, framing, composition, camera movement, subject motion, environment motion, lighting, mood, start frame, end frame, continuity notes.
- Mỗi prompt có đủ duration, aspect ratio, subject/action, shot type, camera angle, framing, composition, camera movement, subject motion, environment motion, lighting, mood, start frame, end frame, continuity notes, retention_notes, transition_notes và sound_design_notes.
- Mỗi prompt/shot chỉ có một hành động chính. Không gom nhiều hành động chính như mở cửa + chạy + hồi tưởng + ngã trong cùng một shot; nếu nội dung có nhiều hành động chính thì phải tách ở bước shot/segment trước khi viết prompt.
- Thời lượng prompt phải khớp với lượng hành động: shot 3-5 giây chỉ mô tả một hành động nhìn thấy rõ; segment 10 giây có thể có micro-scenes nhưng tất cả vẫn phục vụ cùng một hành động chính.
- retention_notes phải nói rõ retention role, open loop, pattern interrupt hoặc visual surprise giúp giữ chân người xem.
- transition_notes phải nói rõ transition type, trigger, timing, edit reason, SFX và continuity risk.
- sound_design_notes phải là chỉ dẫn dựng âm thanh/SFX/BGM; nếu chưa có asset audio thật thì không được nói MP4 đã có SFX/BGM.
- Mỗi prompt phải mô tả animation cụ thể theo timeline: entry motion, hold beat, exit/transition motion, speed/rhythm, camera/object movement và điểm nhấn hình ảnh bám narration.
- Không yêu cầu công cụ tạo video render phụ đề/chữ trực tiếp. Nếu workflow có voice + SRT/subtitle, prompt render phải ghi rõ không render subtitles, captions, karaoke lyrics, text overlays, letters, words hoặc UI text trong video; voice và phụ đề được tạo ở bước sau.
- Prompt chính và các field riêng phải nói rõ: nhân vật trông như thế nào, trang phục và sandals/footwear cụ thể, subject motion căn theo duration_seconds thật của shot, bối cảnh + lighting, cảm xúc/mood chi tiết.
- `prompt` chỉ mô tả hình ảnh, hành động, máy quay, ánh sáng và continuity; CẤM viết câu thoại/narration vào field này. Lời nói chính xác chỉ nằm trong `speech_cues` để shared provider builder ghép theo speech_mode.
- prompt_explanation_vi bắt buộc viết bằng tiếng Việt tự nhiên để người dùng hiểu prompt đang yêu cầu gì: timeline, hình ảnh, hành động, camera, ánh sáng, mood, continuity và ngôn ngữ người xem nếu có.
- prompt_explanation_vi cũng phải giải thích retention purpose, chuyển cảnh và cue âm thanh/SFX của segment.
- Nếu prompt dùng tiếng Anh kỹ thuật cho camera/visual, vẫn phải chỉ dẫn rõ viewer-facing narration, speech, subtitle hoặc on-screen text dùng {video_language.video_language_label(project.target_language)}.
- Negative prompt tránh text overlay, subtitle sai, watermark, logo, distorted face, bad hands, flicker, unwanted camera shake, audio-caption mismatch hoặc extra people nếu không phù hợp.
- Với project series, negative prompt phải chặn duplicate character, identity swap, unintended named character, wrong face, wrong hairstyle, wrong signature outfit và extra foreground character ngoài cast.
- Negative prompt phải chặn thêm các lỗi 2D/static-image: no 2D illustration, no flat drawing, no flat comic panel, no static image, no image prompt, no storyboard frame, no line-art-only render.
- Không dùng tool/command, không đọc file trong project, không giải thích quá trình; schema đã được truyền qua output_schema.
- Chỉ trả về đúng JSON theo schema, không thêm markdown.
""".strip()
    raw_pack: dict | None = None
    normalized_pack: dict | None = None
    batch_raw_items: list[dict] = []
    batch_normalized_items: list[dict] = []
    try:
        for batch_index, batch_shots in enumerate(prompt_batches, start=1):
            batch_orders = [shot.shot_order for shot in batch_shots]
            batch_idempotency_key = _prompt_pack_batch_idempotency_key(project, batch_shots)
            batch_context = {
                "batch_index": batch_index,
                "batch_count": len(prompt_batches),
                "batch_start_order": batch_orders[0],
                "batch_end_order": batch_orders[-1],
                "batch_shot_orders": batch_orders,
                "batch_idempotency_key": batch_idempotency_key,
                "expected_prompt_count": len(batch_shots),
                "batch_max_attempts": VIDEO_PROMPT_BATCH_MAX_ATTEMPTS,
            }
            batch_shot_lines = _video_prompt_shot_lines(
                batch_shots,
                project,
                target_segment_count=target_segment_count,
                segment_config=segment_config,
            )
            batch_prompt = prompt.replace(batch_shot_token, batch_shot_lines).replace(
                batch_count_token,
                str(len(batch_shots)),
            )
            batch_context["batch_prompt_chars"] = len(batch_prompt)
            batch_context["batch_retry_count"] = 0

            batch_succeeded = False
            for batch_attempt in range(1, VIDEO_PROMPT_BATCH_MAX_ATTEMPTS + 1):
                raw_pack = None
                normalized_pack = None
                try:
                    raw_pack = _run_structured_codex(
                        db,
                        project,
                        batch_prompt,
                        VIDEO_PROMPT_PACK_SCHEMA,
                        step_name="video_prompt_generation",
                        max_attempts=1,
                        technical_context={**batch_context, "batch_attempt": batch_attempt},
                    )
                    normalized_pack = _normalize_video_prompt_pack_payload(raw_pack, project)
                    batch_pack = VideoPromptPackPlan.model_validate(normalized_pack)
                    _validate_prompt_pack_output(raw_pack, batch_pack, batch_shots, project)
                    raw_items = _raw_items_from_payload(raw_pack, *VIDEO_PROMPT_LIST_KEYS)
                    batch_raw_items.extend(item for item in raw_items if isinstance(item, dict))
                    batch_normalized_items.extend(
                        item for item in normalized_pack.get("prompts", []) if isinstance(item, dict)
                    )
                    video_observability.log_event(
                        db,
                        step_name="video_prompt_generation_batch",
                        status="success",
                        project_id=project_id,
                        retry_count=batch_attempt - 1,
                        technical_details={
                            **batch_context,
                            "batch_attempt": batch_attempt,
                            "batch_retry_count": batch_attempt - 1,
                            "output_prompt_count": len(batch_pack.prompts),
                        },
                        message=f"Hoàn tất batch prompt video {batch_index}/{len(prompt_batches)}.",
                    )
                    batch_succeeded = True
                    break
                except (ai_planning.AIPlanningError, ValidationError, VideoPlanningValidationError) as exc:
                    should_retry = batch_attempt < VIDEO_PROMPT_BATCH_MAX_ATTEMPTS
                    batch_context["batch_retry_count"] = batch_attempt if should_retry else batch_attempt - 1
                    video_observability.log_event(
                        db,
                        step_name="video_prompt_generation_batch_retry" if should_retry else "video_prompt_generation_batch_failure",
                        status="warning" if should_retry else "failure",
                        project_id=project_id,
                        retry_count=batch_attempt,
                        error_code=getattr(exc, "error_code", "VIDEO_PROMPT_INVALID_OUTPUT"),
                        exc=exc,
                        technical_details={
                            **batch_context,
                            "batch_attempt": batch_attempt,
                            "will_retry": should_retry,
                            "raw_field_types": _payload_type_summary(raw_pack or {}),
                            "normalized_field_types": _payload_type_summary(normalized_pack or {}),
                            "raw_prompt_count": len(_raw_items_from_payload(raw_pack or {}, *VIDEO_PROMPT_LIST_KEYS)),
                            "normalized_prompt_count": len(normalized_pack.get("prompts", [])) if isinstance(normalized_pack, dict) else 0,
                        },
                        validation_errors=(
                            exc.errors()
                            if isinstance(exc, ValidationError)
                            else _validation_errors_from_exception(exc)
                        ),
                        message=(
                            f"Batch prompt video {batch_index}/{len(prompt_batches)} lỗi; sẽ retry một lần."
                            if should_retry
                            else f"Batch prompt video {batch_index}/{len(prompt_batches)} thất bại sau một lần retry."
                        ),
                    )
                    if isinstance(exc, (ValidationError, VideoPlanningValidationError)):
                        video_observability.log_event(
                            db,
                            step_name="video_prompt_validation",
                            status="warning" if should_retry else "failure",
                            project_id=project_id,
                            retry_count=batch_attempt,
                            error_code=getattr(exc, "error_code", "VIDEO_PROMPT_INVALID_OUTPUT"),
                            exc=exc,
                            technical_details={**batch_context, "batch_attempt": batch_attempt, "will_retry": should_retry},
                            validation_errors=(
                                exc.errors()
                                if isinstance(exc, ValidationError)
                                else _validation_errors_from_exception(exc)
                            ),
                            message="Prompt pack mapping fail trong batch; chỉ retry batch hiện tại.",
                        )
                    if not should_retry:
                        raise
                    time.sleep(RETRY_DELAY_SECONDS)
            if not batch_succeeded:
                raise VideoPlanningValidationError(
                    f"Không thể tạo batch prompt video {batch_index}/{len(prompt_batches)}."
                )

        merged_raw = {
            "prompts": [
                {**raw_item, **normalized_item}
                for raw_item, normalized_item in zip(batch_raw_items, batch_normalized_items)
            ]
        }
        normalized_pack = {"prompts": batch_normalized_items}
        pack = VideoPromptPackPlan.model_validate(normalized_pack)
        quality_by_order = _validate_prompt_pack_output(merged_raw, pack, shots, project)
        raw_pack = merged_raw
    except ValidationError as exc:
        video_observability.log_event(
            db,
            step_name="video_prompt_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_PROMPT_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_pack or {}),
                "normalized_field_types": _payload_type_summary(normalized_pack or {}),
                "raw_prompt_count": len(_first_present(raw_pack or {}, *VIDEO_PROMPT_LIST_KEYS) or []),
                "normalized_prompt_count": len(normalized_pack.get("prompts", [])) if isinstance(normalized_pack, dict) else 0,
            },
            validation_errors=exc.errors(),
            message="AI trả về prompt video không đúng cấu trúc.",
        )
        raise VideoPlanningValidationError("AI trả về prompt video không đúng cấu trúc.") from exc
    except VideoPlanningValidationError as exc:
        video_observability.log_event(
            db,
            step_name="video_prompt_validation",
            status="failure",
            project_id=project_id,
            error_code=getattr(exc, "error_code", "VIDEO_PROMPT_INVALID_OUTPUT"),
            exc=exc,
            technical_details={
                "raw_field_types": _payload_type_summary(raw_pack or {}),
                "normalized_field_types": _payload_type_summary(normalized_pack or {}),
                "raw_prompt_count": len(_raw_items_from_payload(raw_pack or {}, *VIDEO_PROMPT_LIST_KEYS)),
                "normalized_prompt_count": len(normalized_pack.get("prompts", [])) if isinstance(normalized_pack, dict) else 0,
            },
            validation_errors=_validation_errors_from_exception(exc),
            message=str(exc),
        )
        raise

    shots_by_order = {shot.shot_order: shot for shot in shots}
    now = datetime.utcnow()
    prompt_dir = video_storage.get_project_subdir(project_id, "video_prompts")
    series_revision = 1
    if project.series_id:
        series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
        series_revision = int(getattr(series, "revision", 1) or 1)
    created: list[DBVideoShotPrompt] = []
    for item in pack.prompts:
        shot = shots_by_order.get(item.shot_order)
        if shot is None:
            continue
        previous_prompts = db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).all()
        for previous_prompt in previous_prompts:
            video_storage.remove_artifact_file(previous_prompt.prompt_path)
        db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.shot_id == shot.id).delete(synchronize_session=False)
        version = (db.query(func.max(DBVideoShotPrompt.version)).filter(DBVideoShotPrompt.shot_id == shot.id).scalar() or 0) + 1
        duration_seconds = _clamp_shot_duration(item.duration_seconds or shot.duration_seconds, project, shot_order=shot.shot_order)
        if _is_video_prompt_creative_default("retention_notes", item.retention_notes) and shot.retention_json:
            item.retention_notes = _planning_value_to_text(shot.retention_json)
        if _is_video_prompt_creative_default("transition_notes", item.transition_notes) and shot.transition_json:
            item.transition_notes = _planning_value_to_text(shot.transition_json)
        if _is_video_prompt_creative_default("sound_design_notes", item.sound_design_notes) and shot.sound_design_json:
            item.sound_design_notes = _planning_value_to_text(shot.sound_design_json)
        stored_prompt = _segment_aware_prompt_text(item, shot, project, duration_seconds=duration_seconds)
        quality = dict(quality_by_order.get(item.shot_order) or _quality_check(item, duration_seconds=duration_seconds))
        if project.series_id:
            try:
                canon_check = series_brain.check_canon(
                    project.series_id,
                    models.SeriesCanonCheckRequest(
                        prompt=stored_prompt,
                        prompt_kind="video_prompt",
                        prompt_ref_id=shot.id,
                        project_id=project_id,
                    ),
                    db,
                )
                quality["canon_check"] = canon_check.model_dump(mode="json")
                if not canon_check.passed:
                    quality["passed"] = False
                    missing = list(quality.get("missing_fields") or [])
                    missing.append("canon_conflicts")
                    quality["missing_fields"] = missing
            except Exception as exc:
                video_observability.log_event(
                    db,
                    step_name="video_prompt_canon_check",
                    status="warning",
                    project_id=project_id,
                    shot_id=shot.id,
                    error_code="SERIES_CANON_CHECK_FAILED",
                    exc=exc,
                    message="Khong kiem tra duoc canon cho prompt video; tiep tuc voi quality check hien co.",
                )
        if reference_package.get("reference_assets") or reference_package.get("provider_report"):
            quality["reference_assets"] = reference_package.get("reference_assets", [])
            quality["reference_asset_ids"] = reference_package.get("reference_asset_ids", [])
            quality["reference_provider_report"] = reference_package.get("provider_report", {})
        row = DBVideoShotPrompt(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=shot.scene_id,
            shot_id=shot.id,
            version=version,
            prompt=stored_prompt,
            prompt_explanation_vi=item.prompt_explanation_vi,
            negative_prompt=item.negative_prompt,
            duration_seconds=duration_seconds,
            aspect_ratio=item.aspect_ratio or project.aspect_ratio,
            camera_motion=item.camera_motion,
            subject_motion=item.subject_motion,
            environment_motion=item.environment_motion,
            start_frame=item.start_frame,
            end_frame=item.end_frame,
            lighting=item.lighting,
            mood=item.mood,
            style_notes=item.composition,
            continuity_notes=item.continuity_notes,
            retention_notes=item.retention_notes,
            transition_notes=item.transition_notes,
            sound_design_notes=item.sound_design_notes,
            quality_status="passed" if quality["passed"] else "failed",
            quality_check=quality,
            created_at=now,
        )
        scene = db.query(DBVideoScene).filter(DBVideoScene.id == shot.scene_id).first() if shot.scene_id else None
        prompt_path = prompt_dir / f"shot-{shot.shot_order:03d}-prompt-{row.id}.txt"
        prompt_path.write_text(_prompt_text(item, shot, project), encoding="utf-8")
        row.prompt_path = video_storage.to_artifact_storage_path(prompt_path)
        shot.prompt_status = "completed" if quality["passed"] else "needs_review"
        shot.updated_at = now
        if scene is not None:
            scene.prompt_status = "completed" if quality["passed"] else "stale"
            scene.updated_at = now
        db.add(row)
        if project.series_id:
            dependencies: list[models.ArtifactDependencyInput] = [
                models.ArtifactDependencyInput(
                    dependency_type="video_shot",
                    dependency_id=shot.id,
                    dependency_revision=int(getattr(shot, "revision", 1) or 1),
                    dependency_scope="story_state",
                    metadata={"shot_order": shot.shot_order, "scene_id": shot.scene_id},
                ),
                models.ArtifactDependencyInput(
                    dependency_type="series_style",
                    dependency_id=project.series_id,
                    dependency_revision=series_revision,
                    dependency_scope="camera_style",
                    metadata={"project_id": project.id},
                ),
                models.ArtifactDependencyInput(
                    dependency_type="series_bible",
                    dependency_id=project.series_id,
                    dependency_revision=series_revision,
                    dependency_scope="story_state",
                    metadata={"project_id": project.id},
                ),
            ]
            for reference in reference_package.get("reference_assets", []):
                if not isinstance(reference, dict) or not reference.get("id"):
                    continue
                dependencies.append(
                    models.ArtifactDependencyInput(
                        dependency_type="reference_asset",
                        dependency_id=str(reference.get("id")),
                        dependency_revision=int(reference.get("revision") or 1),
                        dependency_scope="reference_image",
                        metadata={
                            "label": reference.get("label"),
                            "entity_type": reference.get("entity_type"),
                            "entity_id": reference.get("entity_id"),
                            "reference_role": reference.get("reference_role"),
                            "shot_id": shot.id,
                            "shot_order": shot.shot_order,
                        },
                    )
                )
            series_references.record_dependency_snapshots(
                project.series_id,
                models.ArtifactDependencyRecordRequest(
                    artifact_type="video_prompt",
                    artifact_id=row.id,
                    artifact_revision=int(row.version or 1),
                    dependencies=dependencies,
                ),
                db,
                commit=False,
            )
        created.append(row)
    project.status = "prompts_ready"
    project.planning_status = "prompts_ready"
    video_state.mark_package_stale(project, db)
    from . import video_publishing_metadata

    video_publishing_metadata.mark_publishing_metadata_stale(
        project_id,
        db,
        reason="Prompt video cuối đã thay đổi.",
    )
    db.commit()
    for row in created:
        db.refresh(row)
    return models.VideoShotPromptPackResponse(
        project_id=project_id,
        prompts=[models.VideoShotPromptResponse.model_validate(row) for row in created],
    )

def _latest_shot_prompt(project_id: str, shot_id: str, db: Session) -> DBVideoShotPrompt | None:
    return (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id, DBVideoShotPrompt.shot_id == shot_id)
        .order_by(DBVideoShotPrompt.version.desc(), DBVideoShotPrompt.created_at.desc())
        .first()
    )

def _missing_prompt_explanation_text() -> str:
    return "Chưa có bản giải thích tiếng Việt riêng cho prompt này. Hãy tạo lại prompt video để có bản giải thích đầy đủ."

def _stored_prompt_download_text(prompt: DBVideoShotPrompt, shot: DBVideoShot, project: DBVideoProject) -> str:
    parts = [
        "# Prompt gốc để copy sang công cụ tạo video",
        "",
        (prompt.prompt or "").strip(),
        "",
        f"Video language: {video_language.video_language_english_name(project.target_language)}",
        f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}",
        f"Duration: {prompt.duration_seconds or shot.duration_seconds or ''} seconds",
        f"Camera movement: {prompt.camera_motion or shot.camera_motion or ''}",
        f"Subject motion: {prompt.subject_motion or shot.subject_motion or ''}",
        f"Environment motion: {prompt.environment_motion or shot.environment_motion or ''}",
        f"Start frame: {prompt.start_frame or ''}",
        f"End frame: {prompt.end_frame or ''}",
        f"Lighting: {prompt.lighting or ''}",
        f"Mood: {prompt.mood or ''}",
        f"Continuity notes: {prompt.continuity_notes or ''}",
    ]
    if prompt.negative_prompt:
        parts.extend(["", "Negative prompt:", prompt.negative_prompt.strip()])
    if prompt.retention_notes:
        parts.extend(["", "Retention:", prompt.retention_notes.strip()])
    if prompt.transition_notes:
        parts.extend(["", "Chuyển cảnh:", prompt.transition_notes.strip()])
    if prompt.sound_design_notes:
        parts.extend(["", "Âm thanh/SFX:", prompt.sound_design_notes.strip(), "Ghi chú: đây là chỉ dẫn dựng nếu chưa có asset SFX/BGM thật được mix vào MP4."])
    parts.extend([
        "",
        "Bản giải thích tiếng Việt:",
        (prompt.prompt_explanation_vi or "").strip() or _missing_prompt_explanation_text(),
    ])
    return "\n".join(part for part in parts if part is not None).strip() + "\n"


def _provider_ready_prompt_text(prompt: DBVideoShotPrompt, shot: DBVideoShot, project: DBVideoProject) -> str:
    """Compose the same Veo-ready contract used by the copy endpoint.

    Prompt downloads and prompt packs must not fall back to the legacy visual-only
    artifact: doing so would make a downloaded file silently lose the character
    dialogue selected in the News Video dropdown.
    """
    mode = video_speech.speech_mode_for(project, shot)
    if not mode:
        return _stored_prompt_download_text(prompt, shot, project)
    visual = "\n".join(
        part
        for part in (
            (prompt.prompt or "").strip(),
            f"Video language: {video_language.video_language_english_name(project.target_language)}",
            f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}",
            f"Duration: {prompt.duration_seconds or shot.duration_seconds or ''} seconds",
            f"Camera movement: {prompt.camera_motion or shot.camera_motion or ''}",
            f"Subject motion: {prompt.subject_motion or shot.subject_motion or ''}",
            f"Environment motion: {prompt.environment_motion or shot.environment_motion or ''}",
        )
        if part
    )
    contract = video_speech.build_provider_prompt(
        visual,
        mode,
        video_speech.speech_cues_for_shot(shot, project),
        prompt.negative_prompt,
        prompt.continuity_notes,
    )
    return contract["provider_prompt"].strip() + "\n"

def get_video_prompt_content(project_id: str, shot_id: str, db: Session) -> models.VideoPromptContentResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    prompt = _latest_shot_prompt(project_id, shot_id, db)
    if project is None or shot is None or prompt is None:
        return None
    scene = db.query(DBVideoScene).filter(DBVideoScene.id == shot.scene_id).first() if shot.scene_id else None
    content = _provider_ready_prompt_text(prompt, shot, project)
    return models.VideoPromptContentResponse(
        project_id=project_id,
        scene_id=shot.scene_id,
        shot_id=shot_id,
        prompt_id=prompt.id,
        filename=video_storage.video_prompt_filename(scene.scene_order if scene else None, shot.shot_order),
        content=content,
        prompt_explanation_vi=prompt.prompt_explanation_vi,
        negative_prompt=prompt.negative_prompt,
        retention_notes=prompt.retention_notes,
        transition_notes=prompt.transition_notes,
        sound_design_notes=prompt.sound_design_notes,
    )

def get_video_prompt_download(project_id: str, shot_id: str, db: Session) -> tuple[str, str] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    prompt = _latest_shot_prompt(project_id, shot_id, db)
    if project is None or shot is None or prompt is None:
        return None
    scene = db.query(DBVideoScene).filter(DBVideoScene.id == shot.scene_id).first() if shot.scene_id else None
    return (
        video_storage.video_prompt_filename(scene.scene_order if scene else None, shot.shot_order),
        _provider_ready_prompt_text(prompt, shot, project),
    )

def get_video_prompt_pack_download(project_id: str, db: Session) -> tuple[str, str] | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    sections: list[str] = []
    for shot in ordered_shots(project_id, db):
        prompt = _latest_shot_prompt(project_id, shot.id, db)
        if prompt is None:
            continue
        sections.append(f"# Shot {shot.shot_order:02d}\n\n{_provider_ready_prompt_text(prompt, shot, project).strip()}")
    if not sections:
        return None
    return video_storage.video_prompt_pack_filename(project.title), "\n\n---\n\n".join(sections).strip() + "\n"

def regenerate_shot(project_id: str, shot_id: str, db: Session) -> models.VideoShotResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    shot = db.query(DBVideoShot).filter(DBVideoShot.project_id == project_id, DBVideoShot.id == shot_id).first()
    if project is None or shot is None:
        return None
    if shot.locked:
        return _shot_response(shot)
    scene = db.query(DBVideoScene).filter(DBVideoScene.id == shot.scene_id).first() if shot.scene_id else None
    segment_config = _resolve_prompt_segment_config(project)
    regenerate_unit = f"prompt segment {segment_config.prompt_duration_seconds} giây" if segment_config.segment_count is not None else "shot ngắn 1-5 giây"
    prompt = f"""
Viết lại một {regenerate_unit}, giữ continuity và không đổi scene cha.

{_project_context(project, db)}

Continuity bible:\n{project.continuity_bible or ''}

Scene: {scene.title if scene else ''}\n{scene.visual_description if scene else ''}\n{scene.dialogue if scene else ''}

Shot hiện tại: {json.dumps(models.VideoShotResponse.model_validate(shot).model_dump(), ensure_ascii=False, default=str)}

Yêu cầu: không dùng tool/command, không đọc file trong project, không giải thích quá trình. Chỉ trả một object ShotPlan trong JSON schema dạng ShotBreakdownPlan với đúng 1 item trong `shots`.
Shot trả về phải có retention_role, open_loop, visual_surprise, cut_reason, transition_pack và sound_design đầy đủ.
{video_language.viewer_language_instruction(project.target_language)}
{video_language.narration_field_note(project.target_language)}
{_purpose_generation_instructions(project)}
{_narration_length_instruction(project, duration_seconds=shot.duration_seconds, shot_order=shot.shot_order)}
""".strip()
    raw_plan = _run_structured_codex(db, project, prompt, SHOT_BREAKDOWN_SCHEMA, step_name="shot_regenerate")
    plan = ShotBreakdownPlan.model_validate(
        _normalize_shot_breakdown_payload(raw_plan, dialogue_mode=project.dialogue_mode)
    )
    if not plan.shots:
        raise VideoPlanningValidationError("AI không trả về shot để cập nhật.")
    _finalize_shot_creative_direction(plan.shots)
    item = plan.shots[0]
    current_ordered_shots = ordered_shots(project_id, db)
    is_final_shot = bool(current_ordered_shots and current_ordered_shots[-1].id == shot.id)
    quality = _shot_retainability_quality(item, is_first=shot.shot_order == 1, is_final=is_final_shot)
    return update_shot(
        project_id,
        shot_id,
        models.VideoShotUpdate(
            duration_seconds=_clamp_shot_duration(item.duration_seconds, project, shot_order=shot.shot_order),
            vietnamese_description=item.vietnamese_description,
            english_narration=item.english_narration,
            primary_action=item.primary_action,
            purpose=item.purpose,
            shot_type=item.shot_type,
            camera_angle=item.camera_angle,
            framing=item.framing,
            composition=item.composition,
            camera_motion=item.camera_motion,
            subject_motion=item.subject_motion,
            environment_motion=item.environment_motion,
            transition_to_next=item.transition_to_next,
            retention_json=_shot_retention_metadata(item),
            transition_json=item.transition_pack.model_dump(),
            sound_design_json=item.sound_design.model_dump(),
            speech_cues=item.speech_cues,
            retainability_quality_check=quality,
        ),
        db,
    )
