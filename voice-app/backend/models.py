"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional, List
from datetime import datetime

from .utils.capture_chords import (
    default_push_to_talk_chord,
    default_toggle_to_talk_chord,
)
from .services import video_language, video_purpose as video_purpose_service

_VIDEO_VISUAL_STYLE_MAX_LENGTH = 2000
SERIES_MODE_PATTERN = "^(image_story_only|video_story_only|hybrid)$"
STORY_OUTPUT_INTENT_PATTERN = "^(truyen_anh|video_truyen|ca_hai)$"
STORY_APPROVAL_STATUS_PATTERN = "^(draft|pending_approval|approved|rejected)$"
STORY_ADAPTATION_KIND_PATTERN = "^(image_story|video_story)$"
STORY_ADAPTATION_STATUS_PATTERN = "^(draft|pending_approval|approved|waiting_provider|queued|rendering|completed|failed|stale)$"
STORY_PROMPT_STATUS_PATTERN = "^(draft|pending_approval|approved|stale)$"
STORY_RENDER_STATUS_PATTERN = "^(not_requested|waiting_provider|queued|rendering|completed|failed)$"
SERIES_MEMORY_CARD_TYPE_PATTERN = (
    "^(series_identity|character_context|relationship|location|prop|story_thread|canon_rule|"
    "visual_style|episode_summary|arc_summary|series_summary|reviewed_note)$"
)
SERIES_MEMORY_STATUS_PATTERN = "^(draft|pending_approval|approved|rejected|archived)$"
SERIES_STATE_STATUS_PATTERN = "^(draft|pending_approval|approved|rejected|archived)$"
SERIES_CONTEXT_TASK_PATTERN = (
    "^(story_candidate|master_story|image_panel_prompt|video_story_development|shot_breakdown|"
    "video_prompt|voice|subtitle)$"
)
SERIES_CANON_PROMPT_KIND_PATTERN = "^(image_panel_prompt|video_prompt|story_candidate|master_story|manual)$"
SERIES_REFERENCE_ENTITY_PATTERN = "^(character|location)$"
SERIES_REFERENCE_CHARACTER_ROLE_PATTERN = "^(face_front|face_side|full_body|signature_outfit|expression|other)$"
SERIES_REFERENCE_LOCATION_ROLE_PATTERN = "^(wide_view|entrance|interior|landmark_detail|lighting_reference|other)$"
SERIES_REFERENCE_ROLE_PATTERN = (
    "^(face_front|face_side|full_body|signature_outfit|expression|wide_view|entrance|"
    "interior|landmark_detail|lighting_reference|other)$"
)
SERIES_REFERENCE_STATUS_PATTERN = "^(pending_approval|approved|rejected|archived)$"
ARTIFACT_DEPENDENCY_SCOPE_PATTERN = (
    "^(visual_identity|story_state|dialogue|language|camera_style|reference_image|"
    "style|narration|voice_profile|timing|package)$"
)
VIDEO_QUALITY_STATUS_PATTERN = "^(not_checked|checking|passed|needs_review|blocked|stale)$"


def _truncate_string_field(value: Any, limit: int) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    return text[:limit].rstrip() if len(text) > limit else text


class _VisualStyleLimitedModel(BaseModel):
    @field_validator("visual_style", mode="before", check_fields=False)
    @classmethod
    def _limit_visual_style(cls, value: Any) -> Any:
        return _truncate_string_field(value, _VIDEO_VISUAL_STYLE_MAX_LENGTH)


class VoiceProfileCreate(BaseModel):
    """Request model for creating a voice profile."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    language: str = Field(
        default="en", pattern="^(zh|en|ja|ko|de|fr|ru|pt|es|it|he|ar|da|el|fi|hi|ms|nl|no|pl|sv|sw|tr|vi)$"
    )
    voice_type: Optional[str] = Field(default="cloned", pattern="^(cloned|preset|designed)$")
    preset_engine: Optional[str] = Field(None, max_length=50)
    preset_voice_id: Optional[str] = Field(None, max_length=100)
    design_prompt: Optional[str] = Field(None, max_length=2000)
    default_engine: Optional[str] = Field(None, max_length=50)
    personality: Optional[str] = Field(None, max_length=2000)


class VoiceProfileResponse(BaseModel):
    """Response model for voice profile."""

    id: str
    name: str
    description: Optional[str]
    language: str
    avatar_path: Optional[str] = None
    effects_chain: Optional[List["EffectConfig"]] = None
    voice_type: str = "cloned"
    preset_engine: Optional[str] = None
    preset_voice_id: Optional[str] = None
    design_prompt: Optional[str] = None
    default_engine: Optional[str] = None
    personality: Optional[str] = None
    generation_count: int = 0
    sample_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfileSampleCreate(BaseModel):
    """Request model for adding a sample to a profile."""

    reference_text: str = Field(..., min_length=1, max_length=1000)


class ProfileSampleUpdate(BaseModel):
    """Request model for updating a profile sample."""

    reference_text: str = Field(..., min_length=1, max_length=1000)


class ProfileSampleResponse(BaseModel):
    """Response model for profile sample."""

    id: str
    profile_id: str
    audio_path: str
    reference_text: str

    class Config:
        from_attributes = True


class GenerationRequest(BaseModel):
    """Request model for voice generation."""

    profile_id: str
    text: str = Field(..., min_length=1, max_length=50000)
    language: str = Field(default="en", pattern="^(zh|en|ja|ko|de|fr|ru|pt|es|it|he|ar|da|el|fi|hi|ms|nl|no|pl|sv|sw|tr|vi)$")
    seed: Optional[int] = Field(None, ge=0)
    model_size: Optional[str] = Field(default="1.7B", pattern="^(1\\.7B|0\\.6B|1B|3B)$")
    instruct: Optional[str] = Field(None, max_length=500)
    engine: Optional[str] = Field(default="qwen", pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$")
    personality: bool = Field(
        default=False,
        description="When true and the profile has a personality prompt, the input text is rewritten in-character before TTS.",
    )
    max_chunk_chars: int = Field(
        default=800, ge=100, le=5000, description="Max characters per chunk for long text splitting"
    )
    crossfade_ms: int = Field(
        default=50, ge=0, le=500, description="Crossfade duration in ms between chunks (0 for hard cut)"
    )
    normalize: bool = Field(default=True, description="Normalize output audio volume")
    effects_chain: Optional[List["EffectConfig"]] = Field(
        None, description="Effects chain to apply after generation (overrides profile default)"
    )


class GenerationResponse(BaseModel):
    """Response model for voice generation."""

    id: str
    profile_id: str
    text: str
    language: str
    audio_path: Optional[str] = None
    duration: Optional[float] = None
    seed: Optional[int] = None
    instruct: Optional[str] = None
    engine: Optional[str] = "qwen"
    model_size: Optional[str] = None
    status: str = "completed"
    error: Optional[str] = None
    is_favorited: bool = False
    source: str = "manual"
    created_at: datetime
    versions: Optional[List["GenerationVersionResponse"]] = None
    active_version_id: Optional[str] = None

    class Config:
        from_attributes = True


class HistoryQuery(BaseModel):
    """Query model for generation history."""

    profile_id: Optional[str] = None
    search: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class HistoryResponse(BaseModel):
    """Response model for history entry (includes profile name)."""

    id: str
    profile_id: str
    profile_name: str
    text: str
    language: str
    audio_path: Optional[str] = None
    duration: Optional[float] = None
    seed: Optional[int] = None
    instruct: Optional[str] = None
    engine: Optional[str] = "qwen"
    model_size: Optional[str] = None
    status: str = "completed"
    error: Optional[str] = None
    is_favorited: bool = False
    created_at: datetime
    versions: Optional[List["GenerationVersionResponse"]] = None
    active_version_id: Optional[str] = None

    class Config:
        from_attributes = True


class HistoryListResponse(BaseModel):
    """Response model for history list."""

    items: List[HistoryResponse]
    total: int


class TranscriptionRequest(BaseModel):
    """Request model for audio transcription."""

    language: Optional[str] = Field(None, pattern="^(en|zh|ja|ko|de|fr|ru|pt|es|it)$")
    model: Optional[str] = Field(None, pattern="^(base|small|medium|large|turbo)$")


class TranscriptionResponse(BaseModel):
    """Response model for transcription."""

    text: str
    duration: float


class RefinementFlagsModel(BaseModel):
    """Boolean toggles that drive the refinement prompt builder."""

    smart_cleanup: bool = True
    self_correction: bool = True
    preserve_technical: bool = True


class CaptureResponse(BaseModel):
    """Response model for a capture."""

    id: str
    audio_path: str
    source: str
    language: Optional[str] = None
    duration_ms: Optional[int] = None
    transcript_raw: str
    transcript_refined: Optional[str] = None
    stt_model: Optional[str] = None
    llm_model: Optional[str] = None
    refinement_flags: Optional[RefinementFlagsModel] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CaptureListResponse(BaseModel):
    """Response model for paginated capture list."""

    items: List[CaptureResponse]
    total: int


class CaptureCreateResponse(CaptureResponse):
    """
    Response model for ``POST /captures``.

    Adds ``auto_refine`` and ``allow_auto_paste`` — the server-side settings
    captured at the moment the capture was created. The client reads these to
    decide whether to chain a refinement request and whether to fire the
    synthetic-paste pipeline, so it doesn't need a synced local copy of the
    capture_settings table across sibling Tauri webviews.
    """

    auto_refine: bool
    allow_auto_paste: bool


class CaptureRefineRequest(BaseModel):
    """Request to refine a capture's transcript via the LLM."""

    flags: Optional[RefinementFlagsModel] = None
    model_size: Optional[str] = Field(default=None, pattern="^(0\\.6B|1\\.7B|4B)$")


class CaptureRetranscribeRequest(BaseModel):
    """Request to re-run STT on a capture's audio with a different model."""

    model: Optional[str] = Field(None, pattern="^(base|small|medium|large|turbo)$")
    language: Optional[str] = Field(None, pattern="^(en|zh|ja|ko|de|fr|ru|pt|es|it)$")


class CaptureSettingsResponse(BaseModel):
    """Server-persisted defaults for the capture / refine flow."""

    stt_model: str = Field(default="turbo", pattern="^(base|small|medium|large|turbo)$")
    language: str = Field(default="auto")
    auto_refine: bool = True
    llm_model: str = Field(default="0.6B", pattern="^(0\\.6B|1\\.7B|4B)$")
    smart_cleanup: bool = True
    self_correction: bool = True
    preserve_technical: bool = True
    allow_auto_paste: bool = True
    default_playback_voice_id: Optional[str] = None
    hotkey_enabled: bool = False
    chord_push_to_talk_keys: List[str] = Field(
        default_factory=default_push_to_talk_chord
    )
    chord_toggle_to_talk_keys: List[str] = Field(
        default_factory=default_toggle_to_talk_chord
    )

    class Config:
        from_attributes = True


class CaptureSettingsUpdate(BaseModel):
    """Partial update for capture settings — every field is optional."""

    stt_model: Optional[str] = Field(default=None, pattern="^(base|small|medium|large|turbo)$")
    language: Optional[str] = None
    auto_refine: Optional[bool] = None
    llm_model: Optional[str] = Field(default=None, pattern="^(0\\.6B|1\\.7B|4B)$")
    smart_cleanup: Optional[bool] = None
    self_correction: Optional[bool] = None
    preserve_technical: Optional[bool] = None
    allow_auto_paste: Optional[bool] = None
    default_playback_voice_id: Optional[str] = None
    hotkey_enabled: Optional[bool] = None
    chord_push_to_talk_keys: Optional[List[str]] = Field(default=None, min_length=1, max_length=6)
    chord_toggle_to_talk_keys: Optional[List[str]] = Field(default=None, min_length=1, max_length=6)


class GenerationSettingsResponse(BaseModel):
    """Server-persisted defaults for the generation flow."""

    max_chunk_chars: int = Field(default=800, ge=100, le=5000)
    crossfade_ms: int = Field(default=50, ge=0, le=500)
    normalize_audio: bool = True
    autoplay_on_generate: bool = True

    class Config:
        from_attributes = True


class GenerationSettingsUpdate(BaseModel):
    """Partial update for generation settings — every field is optional."""

    max_chunk_chars: Optional[int] = Field(default=None, ge=100, le=5000)
    crossfade_ms: Optional[int] = Field(default=None, ge=0, le=500)
    normalize_audio: Optional[bool] = None
    autoplay_on_generate: Optional[bool] = None

class AIPlanningSettingsResponse(BaseModel):
    """Server-persisted AI planning provider settings."""

    provider: str = "codex-cli"
    codex_path: Optional[str] = None
    model: Optional[str] = None
    model_reasoning_effort: Optional[str] = None
    timeout_seconds: int = Field(default=600, ge=5, le=600)
    output_schema_path: Optional[str] = None

    class Config:
        from_attributes = True

class AIPlanningSettingsUpdate(BaseModel):
    """Partial update for AI planning provider settings."""

    provider: Optional[str] = Field(default=None, min_length=1, max_length=50)
    codex_path: Optional[str] = Field(default=None, max_length=1000)
    model: Optional[str] = Field(default=None, max_length=100)
    model_reasoning_effort: Optional[str] = Field(
        default=None,
        pattern="^(low|medium|high|xhigh|max|ultra)$",
    )
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=600)
    output_schema_path: Optional[str] = Field(default=None, max_length=1000)

class AIPlanningProviderCheckResponse(BaseModel):
    """Readiness check result for the configured AI planning provider."""

    ready: bool
    provider: str
    message: str
    codex_path: Optional[str] = None
    version: Optional[str] = None
    request_id: Optional[str] = None
    error_code: Optional[str] = None
    requested_model: Optional[str] = None
    requested_reasoning_effort: Optional[str] = None
    effective_model: Optional[str] = None
    effective_reasoning_effort: Optional[str] = None
    model_source: Optional[str] = None
    model_verified: bool = False
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    fallback_error_code: Optional[str] = None

class AIPlanningTestResponse(BaseModel):
    """Live Codex test result for the configured AI planning provider."""

    ready: bool
    provider: str
    message: str
    prompt: str = "xin chào"
    output_text: Optional[str] = None
    request_id: Optional[str] = None
    error_code: Optional[str] = None
    requested_model: Optional[str] = None
    requested_reasoning_effort: Optional[str] = None
    effective_model: Optional[str] = None
    effective_reasoning_effort: Optional[str] = None
    model_source: Optional[str] = None
    model_verified: bool = False
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    fallback_error_code: Optional[str] = None

class VideoSourceBlockDraft(BaseModel):
    """Structured source content block for AI Video phase 2."""

    block_type: str = Field(default="idea", max_length=40)
    content: str = Field(..., min_length=1, max_length=30000)

class VideoSourceBlockCreate(VideoSourceBlockDraft):
    sort_order: Optional[int] = Field(default=None, ge=0)

class VideoSourceBlockUpdate(BaseModel):
    block_type: Optional[str] = Field(default=None, max_length=40)
    content: Optional[str] = Field(default=None, min_length=1, max_length=30000)
    sort_order: Optional[int] = Field(default=None, ge=0)

class VideoSourceBlockReorderRequest(BaseModel):
    block_ids: List[str] = Field(..., min_length=1, max_length=200)

class VideoSourceBlockResponse(BaseModel):
    id: str
    project_id: str
    block_type: str
    sort_order: int
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoStoryDevelopRequest(BaseModel):
    force: bool = False

class VideoStoryApprovalRequest(BaseModel):
    approved: bool = True

class VideoShotMicroScene(BaseModel):
    order: int = Field(..., ge=1, le=20)
    start_seconds: float = Field(..., ge=0, le=7200)
    end_seconds: float = Field(..., ge=0, le=7200)
    description_vi: str = Field(default="", max_length=4000)
    visual_action: str = Field(default="", max_length=4000)
    camera_note: str = Field(default="", max_length=4000)
    continuity_note: Optional[str] = Field(default=None, max_length=4000)
    visible_characters: List[dict[str, Any]] = Field(default_factory=list, max_length=20)


class VideoShotSpeechCue(BaseModel):
    """One exact spoken line and its character/scene delivery context."""

    speaker_name: str = Field(default="Narrator", max_length=160)
    character_profile_id: Optional[str] = Field(default=None, max_length=160)
    speaker_role: str = Field(
        default="offscreen_narrator",
        pattern="^(visible_character|offscreen_narrator|episode_guest|unknown)$",
    )
    text: str = Field(..., min_length=1, max_length=20000)
    voice_description: Optional[str] = Field(default=None, max_length=4000)
    delivery: Optional[str] = Field(default=None, max_length=4000)
    emotion: Optional[str] = Field(default=None, max_length=2000)
    context: Optional[str] = Field(default=None, max_length=6000)
    pronunciation_notes: Optional[str] = Field(default=None, max_length=4000)
    start_seconds: Optional[float] = Field(default=None, ge=0, le=7200)
    end_seconds: Optional[float] = Field(default=None, ge=0, le=7200)
    lip_sync_required: bool = False


class VideoShotDraft(BaseModel):
    scene_id: Optional[str] = None
    shot_order: int = Field(default=0, ge=0)
    duration_seconds: Optional[float] = Field(default=None, ge=0.5, le=30)
    vietnamese_description: Optional[str] = Field(default=None, max_length=12000)
    english_narration: Optional[str] = Field(default=None, max_length=20000)
    primary_action: Optional[str] = Field(default=None, max_length=4000)
    purpose: Optional[str] = Field(default=None, max_length=4000)
    shot_type: Optional[str] = Field(default=None, max_length=120)
    camera_angle: Optional[str] = Field(default=None, max_length=160)
    framing: Optional[str] = Field(default=None, max_length=160)
    composition: Optional[str] = Field(default=None, max_length=4000)
    camera_motion: Optional[str] = Field(default=None, max_length=160)
    subject_motion: Optional[str] = Field(default=None, max_length=4000)
    environment_motion: Optional[str] = Field(default=None, max_length=4000)
    transition_to_next: Optional[str] = Field(default=None, max_length=4000)
    micro_scenes: List[VideoShotMicroScene] = Field(default_factory=list, max_length=20)
    speech_cues: List[VideoShotSpeechCue] = Field(default_factory=list, max_length=20)

class VideoShotUpdate(BaseModel):
    duration_seconds: Optional[float] = Field(default=None, ge=0.5, le=30)
    speech_source_override: Optional[str] = Field(
        default=None,
        pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$",
    )
    speech_mode: Optional[str] = Field(default=None, pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$")
    vietnamese_description: Optional[str] = Field(default=None, max_length=12000)
    english_narration: Optional[str] = Field(default=None, max_length=20000)
    primary_action: Optional[str] = Field(default=None, max_length=4000)
    purpose: Optional[str] = Field(default=None, max_length=4000)
    shot_type: Optional[str] = Field(default=None, max_length=120)
    camera_angle: Optional[str] = Field(default=None, max_length=160)
    framing: Optional[str] = Field(default=None, max_length=160)
    composition: Optional[str] = Field(default=None, max_length=4000)
    camera_motion: Optional[str] = Field(default=None, max_length=160)
    subject_motion: Optional[str] = Field(default=None, max_length=4000)
    environment_motion: Optional[str] = Field(default=None, max_length=4000)
    transition_to_next: Optional[str] = Field(default=None, max_length=4000)
    retention_json: Optional[dict[str, Any]] = None
    transition_json: Optional[dict[str, Any]] = None
    sound_design_json: Optional[dict[str, Any]] = None
    micro_scenes: Optional[List[VideoShotMicroScene]] = Field(default=None, max_length=20)
    speech_cues: Optional[List[VideoShotSpeechCue]] = Field(default=None, max_length=20)
    retainability_quality_check: Optional[dict[str, Any]] = None

class VideoShotLockRequest(BaseModel):
    locked: bool = True

class VideoShotRegenerateRequest(BaseModel):
    scope: str = Field(default="shot", pattern="^(shot|scene|unlocked)$")

class VideoShotResponse(BaseModel):
    id: str
    project_id: str
    scene_id: Optional[str] = None
    shot_order: int
    duration_seconds: Optional[float] = None
    speech_source_override: Optional[str] = None
    vietnamese_description: Optional[str] = None
    english_narration: Optional[str] = None
    primary_action: Optional[str] = None
    purpose: Optional[str] = None
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    framing: Optional[str] = None
    composition: Optional[str] = None
    camera_motion: Optional[str] = None
    subject_motion: Optional[str] = None
    environment_motion: Optional[str] = None
    transition_to_next: Optional[str] = None
    retention_json: Optional[dict[str, Any]] = None
    transition_json: Optional[dict[str, Any]] = None
    sound_design_json: Optional[dict[str, Any]] = None
    micro_scenes: List[VideoShotMicroScene] = Field(default_factory=list)
    speech_cues: List[VideoShotSpeechCue] = Field(default_factory=list)
    retainability_quality_check: Optional[dict[str, Any]] = None
    locked: bool = False
    status: str
    prompt_status: str
    voice_status: str
    subtitle_status: str
    generation_id: Optional[str] = None
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None
    voice_failure_reason: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoPromptQualityCheck(BaseModel):
    passed: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class VideoShotPromptResponse(BaseModel):
    id: str
    project_id: str
    scene_id: Optional[str] = None
    shot_id: str
    version: int
    prompt: str
    prompt_explanation_vi: Optional[str] = None
    negative_prompt: Optional[str] = None
    duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    camera_motion: Optional[str] = None
    subject_motion: Optional[str] = None
    environment_motion: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    style_notes: Optional[str] = None
    continuity_notes: Optional[str] = None
    retention_notes: Optional[str] = None
    transition_notes: Optional[str] = None
    sound_design_notes: Optional[str] = None
    quality_status: str
    quality_check: Optional[dict[str, Any]] = None
    quality_threshold: float = 85.0
    parent_prompt_id: Optional[str] = None
    repair_attempt: int = 0
    repair_status: str = "none"
    repair_changes_json: Optional[dict[str, Any]] = None
    prompt_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoShotPromptPackResponse(BaseModel):
    project_id: str
    prompts: List[VideoShotPromptResponse] = Field(default_factory=list)

class VideoShotClipResponse(BaseModel):
    """Video clip attached to one AI Video phase-2 shot."""

    id: str
    project_id: str
    shot_id: str
    source: str = "upload"
    status: str
    file_path: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    has_audio: bool = False
    is_active: bool = True
    failure_reason: Optional[str] = None
    provider: Optional[str] = None
    provider_asset_id: Optional[str] = None
    provider_metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoRenderSettings(BaseModel):
    """User-selected settings for rendering the final MP4."""

    resolution: str = Field(default="auto", pattern="^(auto|720p|1080p)$")
    fps: int = Field(default=60, ge=12, le=60)
    fit_mode: str = Field(default="crop", pattern="^(crop|pad)$")
    duration_mode: str = Field(default="freeze", pattern="^(freeze|trim_only)$")
    subtitle_mode: str = Field(default="none", pattern="^(burn_in|sidecar|none)$")
    mute_clip_audio: bool = False
    # The three-level audio choice. Absent means "infer from mute_clip_audio": settings
    # written before this field existed live on in job rows and in the browser, and giving
    # this field a hard default would read a stored bed job as "drop" and silently strip the
    # original audio out of every later unattended render.
    clip_audio_mode: Optional[str] = Field(default=None, pattern="^(drop|bed|clip_only)$")
    background_color: str = Field(default="#111827", max_length=20)
    force: bool = False
    enhanced_render: bool = False
    enhanced_audio: bool = True
    ai_review: bool = True
    max_fix_attempts: int = Field(default=0, ge=0, le=2)
    watermark_cleanup: bool = True
    # cv2 is the default because it is ~27x faster than migan on the same clip while the
    # two outputs are visually indistinguishable (PSNR 50,7 dB / SSIM 0,9965). migan stays
    # selectable for clips whose logo sits on a background cv2 fills poorly.
    watermark_backend: str = Field(default="cv2", pattern="^(cv2|migan)$")

class VideoRenderWarning(BaseModel):
    shot_id: Optional[str] = None
    code: str
    message: str

class VideoRenderWatermarkBackendStatus(BaseModel):
    """Readiness of a single watermark region-fill backend."""

    backend: str
    ready: bool
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    revision: Optional[str] = None
    # "cached" | "not_cached" | "unknown"; None when the backend needs no model.
    model_cache: Optional[str] = None

class VideoRenderReadinessResponse(BaseModel):
    """Checklist before creating an MP4 render job."""

    project_id: str
    ready: bool
    ffmpeg_ready: bool = False
    ffprobe_ready: bool = False
    watermark_cleanup_ready: bool = True
    watermark_cleanup_revision: Optional[str] = None
    watermark_cleanup_failure_reason: Optional[str] = None
    # Per-backend readiness, populated only while watermark cleanup is enabled.
    watermark_backends: List[VideoRenderWatermarkBackendStatus] = Field(default_factory=list)
    missing_clip_shot_ids: List[str] = Field(default_factory=list)
    invalid_clip_shot_ids: List[str] = Field(default_factory=list)
    missing_voice_shot_ids: List[str] = Field(default_factory=list)
    missing_timer_shot_ids: List[str] = Field(default_factory=list)
    missing_subtitle: bool = False
    stale_output: bool = False
    missing_reasons: List[str] = Field(default_factory=list)
    warnings: List[VideoRenderWarning] = Field(default_factory=list)

class VideoRenderTimelineShot(BaseModel):
    shot_id: str
    shot_order: int
    scene_id: Optional[str] = None
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    clip_id: Optional[str] = None
    clip_duration_seconds: Optional[float] = None
    has_narration: bool = False
    effective_speech_source: Optional[str] = None
    retention: Optional[dict[str, Any]] = None
    transition: Optional[dict[str, Any]] = None
    sound_design: Optional[dict[str, Any]] = None
    retainability_quality_check: Optional[dict[str, Any]] = None

class VideoRenderSfxAssetResponse(BaseModel):
    """SFX/BGM audio asset available to enhanced render."""

    asset_id: str
    filename: str
    file_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    cue_aliases: List[str] = Field(default_factory=list)
    status: str = "ready"
    failure_reason: Optional[str] = None

class VideoEnhancedRenderArtifactResponse(BaseModel):
    filename: str
    path: Optional[str] = None
    kind: str

class VideoEnhancedRenderFallback(BaseModel):
    kind: str
    shot_id: Optional[str] = None
    cue_alias: Optional[str] = None
    message_vi: str

class VideoEnhancedTransitionAction(BaseModel):
    from_shot_id: str
    to_shot_id: Optional[str] = None
    transition_alias: str
    original_transition: Optional[str] = None
    at_seconds: float
    duration_seconds: float = 0.0
    render_mode: str = "hard_cut"
    rendered: bool = True
    continuity_risk: Optional[str] = None
    fallback_reason: Optional[str] = None

class VideoEnhancedSfxAction(BaseModel):
    shot_id: str
    cue_alias: str
    cue_label: Optional[str] = None
    start_seconds: float
    duration_seconds: float
    volume: float = Field(default=0.45, ge=0, le=1)
    fade_in_seconds: float = Field(default=0.02, ge=0, le=2)
    fade_out_seconds: float = Field(default=0.08, ge=0, le=2)
    duck_under_voice: bool = True
    asset_id: Optional[str] = None
    asset_filename: Optional[str] = None
    asset_path: Optional[str] = None
    rendered: bool = False
    fallback_reason: Optional[str] = None

class VideoEnhancedBgmAction(BaseModel):
    asset_id: Optional[str] = None
    asset_filename: Optional[str] = None
    asset_path: Optional[str] = None
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    volume: float = Field(default=0.12, ge=0, le=1)
    rendered: bool = False
    fallback_reason: Optional[str] = None

class VideoEnhancedRetentionAction(BaseModel):
    shot_id: str
    shot_order: int
    role: Optional[str] = None
    hook: Optional[str] = None
    pattern_interrupt: Optional[str] = None
    payoff: Optional[str] = None
    note_vi: Optional[str] = None

class VideoEnhancedRenderPlan(BaseModel):
    schema_version: str = "enhanced-render-plan-v1"
    project_id: str
    project_title: Optional[str] = None
    total_duration_seconds: float = 0.0
    settings: dict[str, Any] = Field(default_factory=dict)
    transition_actions: List[VideoEnhancedTransitionAction] = Field(default_factory=list)
    sfx_actions: List[VideoEnhancedSfxAction] = Field(default_factory=list)
    bgm_action: Optional[VideoEnhancedBgmAction] = None
    retention_actions: List[VideoEnhancedRetentionAction] = Field(default_factory=list)
    fallbacks: List[VideoEnhancedRenderFallback] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class VideoRenderJobCreateRequest(BaseModel):
    settings: VideoRenderSettings = Field(default_factory=VideoRenderSettings)

class VideoRenderJobResponse(BaseModel):
    """Background MP4 render job status."""

    id: str
    project_id: str
    status: str
    progress: float = 0.0
    current_step: Optional[str] = None
    settings_json: Optional[str] = None
    readiness_json: Optional[str] = None
    timeline_manifest_path: Optional[str] = None
    enhanced_plan_path: Optional[str] = None
    review_report_path: Optional[str] = None
    enhanced_artifacts_json: Optional[dict[str, Any]] = None
    review_status: Optional[str] = None
    fix_attempt_count: int = 0
    output_path: Optional[str] = None
    subtitle_ass_path: Optional[str] = None
    stale: bool = False
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    technical_details: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProviderSessionResponse(BaseModel):
    """Safe provider session metadata returned to AI Video UI."""

    id: str
    provider: str = "veo"
    provider_tool: Optional[str] = None
    status: str
    is_default: bool = True
    connection_label: Optional[str] = None
    verified_account_hint: Optional[str] = None
    identity_status: str = "unknown"
    identity_verified_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    chrome_profile_configured: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProviderSessionOpenRequest(BaseModel):
    provider: str = Field(default="veo", pattern="^(veo)$")
    change_account: bool = False

class VideoProviderSessionLabelUpdate(BaseModel):
    connection_label: str = Field(..., min_length=1, max_length=120)

class VideoProviderProjectBindingResponse(BaseModel):
    """Redacted Flow/Veo project binding metadata for UI and reports."""

    id: str
    scope: str
    scope_id: str
    project_id: Optional[str] = None
    series_id: Optional[str] = None
    provider: str = "veo"
    provider_tool: str = "veo3_flow"
    provider_project_ref_hash: str
    status: str
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    observed_model_label: Optional[str] = None
    observed_model_cost_label: Optional[str] = None
    model_selection_mode: str = "use_current_flow_selection"
    allow_automatic_model_change: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoCodexRepairAttemptResponse(BaseModel):
    """Redacted status for one bounded Codex repair attempt."""

    id: str
    job_id: str
    item_id: Optional[str] = None
    project_id: str
    status: str
    error_code: str
    step_name: Optional[str] = None
    repair_context_json: Optional[dict[str, Any]] = None
    files_changed_json: Optional[dict[str, Any]] = None
    tests_run_json: Optional[dict[str, Any]] = None
    test_result: Optional[str] = None
    failure_reason: Optional[str] = None
    requires_approval: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VideoClipGenerationItemResponse(BaseModel):
    id: str
    job_id: str
    project_id: str
    shot_id: str
    shot_order: int
    prompt_id: Optional[str] = None
    status: str
    attempt_count: int = 0
    credit_cost: Optional[int] = None
    provider_duration_seconds: Optional[float] = None
    provider_asset_id: Optional[str] = None
    provider_project_ref_hash: Optional[str] = None
    observed_model_label: Optional[str] = None
    observed_model_cost_label: Optional[str] = None
    download_correlation_id: Optional[str] = None
    download_url_hash: Optional[str] = None
    original_filename: Optional[str] = None
    downloaded_file_path: Optional[str] = None
    clip_id: Optional[str] = None
    failure_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoClipGenerationSummary(BaseModel):
    total_items: int = 0
    pending_items: int = 0
    active_items: int = 0
    completed_items: int = 0
    skipped_items: int = 0
    failed_items: int = 0
    needs_login_items: int = 0
    needs_user_action_items: int = 0
    needs_credit_approval_items: int = 0
    paused_for_repair_items: int = 0
    credit_spent_estimate: int = 0
    render_ready: bool = False
    render_missing_reasons: List[str] = Field(default_factory=list)

class VideoClipGenerationJobStartRequest(BaseModel):
    session_id: Optional[str] = None
    force: bool = False
    auto_render: bool = False
    enable_codex_repair: bool = False
    credit_approval_policy: str = Field(default="approve_dont_ask_again", pattern="^(approve_dont_ask_again|manual_per_item)$")
    max_credit_per_job: Optional[int] = Field(default=None, ge=1, le=1000)
    confirm_identity: bool = False

class VideoClipGenerationRetryRequest(BaseModel):
    force: bool = False

class VideoClipGenerationResumeRequest(BaseModel):
    confirm_identity: bool = False

class VideoClipGenerationCreditApprovalRequest(BaseModel):
    approve: bool = True

class VideoClipGenerationJobResponse(BaseModel):
    id: str
    project_id: str
    provider: str = "veo"
    session_id: str
    status: str
    current_step: str
    progress: float = 0.0
    force: bool = False
    auto_render: bool = False
    enable_codex_repair: bool = False
    credit_approval_policy: str = "approve_dont_ask_again"
    max_credit_per_job: Optional[int] = None
    credit_spent_estimate: int = 0
    render_job_id: Optional[str] = None
    repair_status: Optional[str] = None
    repair_attempt_count: int = 0
    repair_report_json: Optional[dict[str, Any]] = None
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    step_results_json: Optional[dict[str, Any]] = None
    provider_project_binding: Optional[VideoProviderProjectBindingResponse] = None
    repair_attempts: List[VideoCodexRepairAttemptResponse] = Field(default_factory=list)
    items: List[VideoClipGenerationItemResponse] = Field(default_factory=list)
    summary: VideoClipGenerationSummary = Field(default_factory=VideoClipGenerationSummary)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoDebugEventResponse(BaseModel):
    id: str
    request_id: str
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    shot_id: Optional[str] = None
    step_name: str
    status: str
    provider: Optional[str] = None
    model: Optional[str] = None
    duration_ms: Optional[float] = None
    retry_count: int = 0
    error_code: Optional[str] = None
    exception_class: Optional[str] = None
    message: Optional[str] = None
    technical_details: Optional[str] = None
    validation_errors: Optional[list[Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoDebugStatusResponse(BaseModel):
    project_id: str
    latest_request_id: Optional[str] = None
    log_path: Optional[str] = None
    artifact_status: dict[str, Any] = Field(default_factory=dict)
    latest_errors: List[VideoDebugEventResponse] = Field(default_factory=list)
    events: List[VideoDebugEventResponse] = Field(default_factory=list)

class VideoSceneDraft(BaseModel):
    """Scene data accepted when creating or replacing project scenes."""

    title: Optional[str] = Field(default=None, max_length=160)
    dialogue: str = Field(default="", max_length=20000)
    visual_description: Optional[str] = Field(default=None, max_length=4000)
    target_duration_seconds: Optional[int] = Field(default=None, ge=1, le=3600)

class SeriesCharacterProfileBase(BaseModel):
    """Shared structured character profile fields for one series."""

    name: str = Field(..., min_length=1, max_length=160)
    role: Optional[str] = Field(default=None, max_length=500)
    face_description: Optional[str] = Field(default=None, max_length=4000)
    hair_description: Optional[str] = Field(default=None, max_length=4000)
    body_description: Optional[str] = Field(default=None, max_length=4000)
    signature_outfit: Optional[str] = Field(default=None, max_length=4000)
    personality: Optional[str] = Field(default=None, max_length=4000)
    speech_style: Optional[str] = Field(default=None, max_length=4000)
    fixed_traits: Optional[str] = Field(default=None, max_length=4000)
    additional_notes: Optional[str] = Field(default=None, max_length=4000)
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)

class SeriesCharacterProfileCreate(SeriesCharacterProfileBase):
    """Create a shared character profile after user approval."""

class SeriesCharacterProfileUpdate(BaseModel):
    """Partial update for one shared character profile."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    role: Optional[str] = Field(default=None, max_length=500)
    face_description: Optional[str] = Field(default=None, max_length=4000)
    hair_description: Optional[str] = Field(default=None, max_length=4000)
    body_description: Optional[str] = Field(default=None, max_length=4000)
    signature_outfit: Optional[str] = Field(default=None, max_length=4000)
    personality: Optional[str] = Field(default=None, max_length=4000)
    speech_style: Optional[str] = Field(default=None, max_length=4000)
    fixed_traits: Optional[str] = Field(default=None, max_length=4000)
    additional_notes: Optional[str] = Field(default=None, max_length=4000)
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)

class SeriesCharacterProfileResponse(SeriesCharacterProfileBase):
    """Shared character profile returned to Story Studio and AI Video."""

    id: str
    series_id: str
    sort_order: int = 0
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EpisodeCastMember(BaseModel):
    """Project-level cast item selected from approved series character profiles."""

    character_profile_id: Optional[str] = None
    name: str = Field(default="", max_length=160)
    episode_role: Optional[str] = Field(default=None, max_length=500)
    importance: str = Field(default="supporting", max_length=80)
    reason_vi: Optional[str] = Field(default=None, max_length=2000)
    identity_lock: Optional[str] = Field(default=None, max_length=4000)
    visual_identity: Optional[str] = Field(default=None, max_length=4000)
    fixed_traits: Optional[str] = Field(default=None, max_length=4000)

class EpisodeOnlyGuest(BaseModel):
    """A reviewed character that may be used in one episode but is not series canon."""

    guest_id: str = Field(default="", max_length=120)
    proposal_id: Optional[str] = Field(default=None, max_length=120)
    name: str = Field(default="", max_length=160)
    episode_role: Optional[str] = Field(default=None, max_length=500)
    appearance: Optional[str] = Field(default=None, max_length=4000)
    personality: Optional[str] = Field(default=None, max_length=4000)
    speech_style: Optional[str] = Field(default=None, max_length=4000)
    reason_vi: Optional[str] = Field(default=None, max_length=2000)
    approved_at: Optional[str] = None

class NewCharacterProposal(BaseModel):
    """AI proposal for a new character. Canon writes require explicit user decision."""

    proposal_id: str = Field(default="", max_length=120)
    name: str = Field(default="", max_length=160)
    episode_role: Optional[str] = Field(default=None, max_length=500)
    reason_vi: Optional[str] = Field(default=None, max_length=4000)
    canon_impact: str = Field(default="unknown", max_length=120)
    reappears_likely: bool = False
    has_dialogue: bool = False
    foreground: bool = False
    affects_plot: bool = False
    background_extra: bool = False
    requires_review: bool = True
    face_description: Optional[str] = Field(default=None, max_length=4000)
    hair_description: Optional[str] = Field(default=None, max_length=4000)
    body_description: Optional[str] = Field(default=None, max_length=4000)
    signature_outfit: Optional[str] = Field(default=None, max_length=4000)
    personality: Optional[str] = Field(default=None, max_length=4000)
    speech_style: Optional[str] = Field(default=None, max_length=4000)
    fixed_traits: Optional[str] = Field(default=None, max_length=4000)
    additional_notes: Optional[str] = Field(default=None, max_length=4000)
    affected_artifacts: List[str] = Field(default_factory=list, max_length=20)
    status: str = Field(default="pending_review", max_length=80)
    decision: Optional[str] = Field(default=None, max_length=80)
    decided_at: Optional[str] = None
    decided_note_vi: Optional[str] = Field(default=None, max_length=2000)
    series_character_profile_id: Optional[str] = None

class VideoProjectCharacterFlowResponse(BaseModel):
    """Character-flow artifact stored on one AI Video project."""

    project_id: str
    series_id: Optional[str] = None
    episode_cast: List[EpisodeCastMember] = Field(default_factory=list)
    episode_only_guests: List[EpisodeOnlyGuest] = Field(default_factory=list)
    new_character_proposals: List[NewCharacterProposal] = Field(default_factory=list)
    pending_required_count: int = 0
    required_proposals_decided: bool = True
    resume_step: Optional[str] = None
    message: str = ""

class CharacterProposalDecisionRequest(BaseModel):
    """Decision for one AI-proposed character."""

    decision: str = Field(..., pattern="^(approve_as_series_character|keep_episode_only|reject)$")
    note_vi: Optional[str] = Field(default=None, max_length=2000)

class CharacterProposalDecisionResponse(BaseModel):
    """Updated project character flow after a proposal decision."""

    character_flow: VideoProjectCharacterFlowResponse
    created_character_profile: Optional[SeriesCharacterProfileResponse] = None
    auto_run_ready_to_continue: bool = False
    message: str

class SeriesCharacterProfileReorderRequest(BaseModel):
    """Persist a manual character profile order."""

    profile_ids: List[str] = Field(..., min_length=1, max_length=200)

class SeriesCharacterProfileSuggestionResponse(BaseModel):
    """Draft profile suggestion produced from legacy Character Bible text."""

    profiles: List[SeriesCharacterProfileCreate] = Field(default_factory=list)
    source: str = "character_bible"
    saved: bool = False
    message: str

class SeriesMemoryCardBase(BaseModel):
    """Editable structured memory unit for a long-running series."""

    card_type: str = Field(..., pattern=SERIES_MEMORY_CARD_TYPE_PATTERN)
    title: str = Field(..., min_length=1, max_length=240)
    content: dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, max_length=50)
    entity_refs: List[dict[str, Any]] = Field(default_factory=list, max_length=100)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    status: str = Field(default="draft", pattern=SERIES_MEMORY_STATUS_PATTERN)
    effective_from_episode: Optional[int] = Field(default=None, ge=1, le=10000)
    effective_to_episode: Optional[int] = Field(default=None, ge=1, le=10000)
    source_type: Optional[str] = Field(default=None, max_length=80)
    source_id: Optional[str] = Field(default=None, max_length=160)

class SeriesMemoryCardCreate(SeriesMemoryCardBase):
    """Create a draft or pending memory card."""

class SeriesMemoryCardUpdate(BaseModel):
    """Partial update for one memory card."""

    card_type: Optional[str] = Field(default=None, pattern=SERIES_MEMORY_CARD_TYPE_PATTERN)
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    content: Optional[dict[str, Any]] = None
    tags: Optional[List[str]] = Field(default=None, max_length=50)
    entity_refs: Optional[List[dict[str, Any]]] = Field(default=None, max_length=100)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: Optional[str] = Field(default=None, pattern=SERIES_MEMORY_STATUS_PATTERN)
    effective_from_episode: Optional[int] = Field(default=None, ge=1, le=10000)
    effective_to_episode: Optional[int] = Field(default=None, ge=1, le=10000)
    source_type: Optional[str] = Field(default=None, max_length=80)
    source_id: Optional[str] = Field(default=None, max_length=160)

class SeriesMemoryCardStatusRequest(BaseModel):
    """Approve, reject, archive, or move a card back to draft."""

    status: str = Field(..., pattern=SERIES_MEMORY_STATUS_PATTERN)

class SeriesMemoryCardResponse(SeriesMemoryCardBase):
    """Structured memory card returned by Series Brain APIs."""

    id: str
    series_id: str
    revision: int = 1
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class SeriesMemoryCardListResponse(BaseModel):
    items: List[SeriesMemoryCardResponse] = Field(default_factory=list)
    total: int = 0

class SeriesMemorySuggestionRequest(BaseModel):
    """Build draft cards from existing Bible/continuity fields."""

    include_legacy_bible: bool = True
    include_latest_summary: bool = True
    save_drafts: bool = False

class SeriesMemorySuggestionResponse(BaseModel):
    cards: List[SeriesMemoryCardCreate] = Field(default_factory=list)
    saved: bool = False
    message: str

class SeriesCurrentStateDraft(BaseModel):
    """Versioned state snapshot proposed or approved for a series."""

    based_on_episode_number: int = Field(default=0, ge=0, le=10000)
    character_states: dict[str, Any] = Field(default_factory=dict)
    relationship_states: dict[str, Any] = Field(default_factory=dict)
    location_states: dict[str, Any] = Field(default_factory=dict)
    prop_states: dict[str, Any] = Field(default_factory=dict)
    open_threads: List[dict[str, Any]] = Field(default_factory=list, max_length=500)
    unresolved_conflicts: List[dict[str, Any]] = Field(default_factory=list, max_length=500)
    approval_status: str = Field(default="draft", pattern=SERIES_STATE_STATUS_PATTERN)
    source_type: Optional[str] = Field(default=None, max_length=80)
    source_id: Optional[str] = Field(default=None, max_length=160)

class SeriesCurrentStateCreate(SeriesCurrentStateDraft):
    """Create a proposed or approved state version."""

class SeriesCurrentStateUpdate(BaseModel):
    based_on_episode_number: Optional[int] = Field(default=None, ge=0, le=10000)
    character_states: Optional[dict[str, Any]] = None
    relationship_states: Optional[dict[str, Any]] = None
    location_states: Optional[dict[str, Any]] = None
    prop_states: Optional[dict[str, Any]] = None
    open_threads: Optional[List[dict[str, Any]]] = Field(default=None, max_length=500)
    unresolved_conflicts: Optional[List[dict[str, Any]]] = Field(default=None, max_length=500)
    approval_status: Optional[str] = Field(default=None, pattern=SERIES_STATE_STATUS_PATTERN)

class SeriesCurrentStateStatusRequest(BaseModel):
    approval_status: str = Field(..., pattern=SERIES_STATE_STATUS_PATTERN)

class SeriesCurrentStateResponse(SeriesCurrentStateDraft):
    id: str
    series_id: str
    revision: int = 1
    previous_state_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class SeriesCurrentStateListResponse(BaseModel):
    items: List[SeriesCurrentStateResponse] = Field(default_factory=list)
    total: int = 0

class SeriesReferenceAssetStatusRequest(BaseModel):
    """Approve/reject/archive or activate/deactivate one reference asset."""

    approval_status: Optional[str] = Field(default=None, pattern=SERIES_REFERENCE_STATUS_PATTERN)
    active: Optional[bool] = None
    reason: Optional[str] = Field(default=None, max_length=1000)
    changed_by: Optional[str] = Field(default=None, max_length=160)

class SeriesReferenceAssetResponse(BaseModel):
    """Safe metadata for a character/location reference image."""

    id: str
    series_id: str
    entity_type: str
    entity_id: str
    reference_role: str
    label: Optional[str] = None
    asset_path: str
    thumbnail_path: Optional[str] = None
    provider_asset_id: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    checksum: str
    source_type: Optional[str] = None
    approval_status: str
    revision: int = 1
    active: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime

class SeriesReferenceAssetListResponse(BaseModel):
    items: List[SeriesReferenceAssetResponse] = Field(default_factory=list)
    total: int = 0

class SeriesReferenceProviderReport(BaseModel):
    provider: str = "provider-neutral"
    provider_supports_references: bool = False
    sent: List[dict[str, Any]] = Field(default_factory=list)
    skipped: List[dict[str, Any]] = Field(default_factory=list)
    fallback_text: Optional[str] = None

class ArtifactDependencyInput(BaseModel):
    dependency_type: str = Field(..., max_length=80)
    dependency_id: str = Field(..., max_length=160)
    dependency_revision: int = Field(default=1, ge=1)
    dependency_scope: str = Field(..., pattern=ARTIFACT_DEPENDENCY_SCOPE_PATTERN)
    metadata: dict[str, Any] = Field(default_factory=dict)

class ArtifactDependencySnapshotResponse(BaseModel):
    id: str
    series_id: str
    artifact_type: str
    artifact_id: str
    artifact_revision: int = 1
    dependency_type: str
    dependency_id: str
    dependency_revision: int = 1
    dependency_scope: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class ArtifactDependencyRecordRequest(BaseModel):
    artifact_type: str = Field(..., max_length=80)
    artifact_id: str = Field(..., max_length=180)
    artifact_revision: int = Field(default=1, ge=1)
    dependencies: List[ArtifactDependencyInput] = Field(default_factory=list, max_length=200)

class ArtifactStaleEventResponse(BaseModel):
    id: str
    series_id: str
    artifact_type: str
    artifact_id: str
    artifact_revision: int = 1
    dependency_type: str
    dependency_id: str
    old_revision: Optional[int] = None
    new_revision: Optional[int] = None
    changed_scope: str
    dependency_scope: str
    reason_vi: str
    propagation_rule: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    resolved_at: Optional[datetime] = None

class ArtifactStaleEventListResponse(BaseModel):
    items: List[ArtifactStaleEventResponse] = Field(default_factory=list)
    total: int = 0

class ArtifactStaleMarkRequest(BaseModel):
    dependency_type: str = Field(..., max_length=80)
    dependency_id: str = Field(..., max_length=160)
    old_revision: Optional[int] = Field(default=None, ge=1)
    new_revision: Optional[int] = Field(default=None, ge=1)
    changed_scope: str = Field(..., pattern=ARTIFACT_DEPENDENCY_SCOPE_PATTERN)
    reason_vi: Optional[str] = Field(default=None, max_length=2000)

class ArtifactTargetedRegenerationRequest(BaseModel):
    event_ids: Optional[List[str]] = Field(default=None, max_length=200)
    artifact_type: Optional[str] = Field(default=None, max_length=80)
    artifact_id: Optional[str] = Field(default=None, max_length=180)

class ArtifactTargetedRegenerationResponse(BaseModel):
    requested: int = 0
    artifacts: List[dict[str, Any]] = Field(default_factory=list)
    message: str

class SeriesVersionRecordResponse(BaseModel):
    id: str
    series_id: str
    entity_type: str
    entity_id: str
    revision: int = 1
    snapshot: dict[str, Any] = Field(default_factory=dict)
    changed_by: Optional[str] = None
    change_source: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: datetime

class SeriesVersionHistoryResponse(BaseModel):
    items: List[SeriesVersionRecordResponse] = Field(default_factory=list)
    total: int = 0
    diff_vi: List[str] = Field(default_factory=list)

class SeriesStateProposalRequest(BaseModel):
    source_type: str = Field(default="manual", max_length=80)
    source_id: Optional[str] = Field(default=None, max_length=160)
    based_on_episode_number: Optional[int] = Field(default=None, ge=0, le=10000)
    notes: Optional[str] = Field(default=None, max_length=12000)

class SeriesContextCompileRequest(BaseModel):
    task_type: str = Field(..., pattern=SERIES_CONTEXT_TASK_PATTERN)
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    project_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    target_ref_type: Optional[str] = Field(default=None, max_length=80)
    target_ref_id: Optional[str] = Field(default=None, max_length=160)
    user_input: Optional[str] = Field(default=None, max_length=50000)
    current_payload: dict[str, Any] = Field(default_factory=dict)
    entity_refs: List[str] = Field(default_factory=list, max_length=100)
    tags: List[str] = Field(default_factory=list, max_length=100)
    max_chars: int = Field(default=24000, ge=2000, le=100000)
    persist_trace: bool = True

class SeriesContextCompileResponse(BaseModel):
    trace_id: Optional[str] = None
    series_id: str
    task_type: str
    context_text: str
    selected_cards: List[dict[str, Any]] = Field(default_factory=list)
    selected_character_profiles: List[dict[str, Any]] = Field(default_factory=list)
    group_usage: List[dict[str, Any]] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    truncated_groups: List[str] = Field(default_factory=list)
    context_stats: dict[str, Any] = Field(default_factory=dict)

class SeriesContextTraceResponse(BaseModel):
    id: str
    series_id: str
    project_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    task_type: str
    target_ref_type: Optional[str] = None
    target_ref_id: Optional[str] = None
    selected_cards: List[dict[str, Any]] = Field(default_factory=list)
    selected_character_profiles: List[dict[str, Any]] = Field(default_factory=list)
    group_budget: List[dict[str, Any]] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    truncated_groups: List[str] = Field(default_factory=list)
    context_stats: dict[str, Any] = Field(default_factory=dict)
    reasons: List[dict[str, Any]] = Field(default_factory=list)
    context_preview: Optional[str] = None
    created_at: datetime

class SeriesContextTraceListResponse(BaseModel):
    items: List[SeriesContextTraceResponse] = Field(default_factory=list)
    total: int = 0

class SeriesCanonCheckRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=50000)
    prompt_kind: str = Field(default="manual", pattern=SERIES_CANON_PROMPT_KIND_PATTERN)
    prompt_ref_id: Optional[str] = Field(default=None, max_length=160)
    project_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    allow_override: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=4000)

class SeriesCanonCheckResponse(BaseModel):
    id: Optional[str] = None
    series_id: str
    prompt_kind: str
    prompt_ref_id: Optional[str] = None
    passed: bool
    blocking_conflicts: List[dict[str, Any]] = Field(default_factory=list)
    warnings: List[dict[str, Any]] = Field(default_factory=list)
    evidence_card_ids: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    override_reason: Optional[str] = None
    created_at: Optional[datetime] = None

class StoryImageOutputSettings(BaseModel):
    """Image-story production settings for one Story Studio episode."""

    panel_mode: str = Field(default="auto", pattern="^(auto|manual)$")
    panel_count: Optional[int] = Field(default=None, ge=1, le=200)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1|4:5)$")
    width: int = Field(default=720, ge=256, le=8192)
    height: int = Field(default=1280, ge=256, le=8192)

    @model_validator(mode="after")
    def _manual_count_required(self):
        if self.panel_mode == "manual" and not self.panel_count:
            raise ValueError("panel_count is required when image panel_mode is manual")
        return self

DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT = 6
DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS = 10
DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT = 4

class StoryVideoHandoffSettings(BaseModel):
    """Video handoff settings copied from Story Studio into AI Video."""

    handoff_only: bool = True
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1)$")
    target_language: str = Field(default="en", pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    video_purpose: str = Field(default="global_short", pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: str = Field(default="character_lines", pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: str = Field(default="dense", pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default="direct", pattern=video_purpose_service.CTA_STYLE_PATTERN)
    target_duration_seconds: Optional[int] = Field(default=None, ge=5, le=7200)
    default_shot_duration_seconds: Optional[int] = Field(default=None, ge=1, le=5)
    prompt_segment_count: Optional[int] = Field(default=DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT, ge=1, le=100)
    prompt_segment_duration_seconds: Optional[int] = Field(
        default=DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS,
        ge=3,
        le=30,
    )
    micro_scenes_per_prompt: Optional[int] = Field(default=DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT, ge=1, le=5)

class StoryEpisodeOutputSettings(BaseModel):
    """Normalized Story Studio episode production settings."""

    image: StoryImageOutputSettings = Field(default_factory=StoryImageOutputSettings)
    video: StoryVideoHandoffSettings = Field(default_factory=StoryVideoHandoffSettings)

class StoryEpisodeCreate(BaseModel):
    """Create a Story Studio episode inside an image/hybrid series."""

    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    title: Optional[str] = Field(default=None, max_length=160)
    output_intent: str = Field(default="truyen_anh", pattern=STORY_OUTPUT_INTENT_PATTERN)
    market_profile: str = Field(default="global_short", max_length=80)
    language_profile: str = Field(default="en", max_length=20)
    source_input: Optional[str] = Field(default=None, max_length=50000)
    output_settings: StoryEpisodeOutputSettings = Field(default_factory=StoryEpisodeOutputSettings)

class StoryEpisodeUpdate(BaseModel):
    """Partial update for Story Studio episode metadata or Master Story."""

    title: Optional[str] = Field(default=None, max_length=160)
    output_intent: Optional[str] = Field(default=None, pattern=STORY_OUTPUT_INTENT_PATTERN)
    market_profile: Optional[str] = Field(default=None, max_length=80)
    language_profile: Optional[str] = Field(default=None, max_length=20)
    source_input: Optional[str] = Field(default=None, max_length=50000)
    output_settings: Optional[StoryEpisodeOutputSettings] = None
    master_story_json: Optional[dict[str, Any]] = None
    selection_reason: Optional[str] = Field(default=None, max_length=4000)

class StoryScenarioCandidateResponse(BaseModel):
    """One Story Studio scenario direction."""

    id: str
    story_episode_id: str
    strategy_type: str
    script_json: dict[str, Any]
    score_json: Optional[dict[str, Any]] = None
    strengths: Optional[str] = None
    risks: Optional[str] = None
    context_snapshot_id: Optional[str] = None
    model_label: Optional[str] = None
    generation_attempt: int = 1
    generation_status: str = "completed"
    generation_metadata_json: Optional[dict[str, Any]] = None
    evaluation_status: str = "pending"
    evaluation_json: Optional[dict[str, Any]] = None
    selected: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StoryAdaptationResponse(BaseModel):
    """Image story or video story adaptation state."""

    id: str
    story_episode_id: str
    kind: str
    status: str
    payload_json: Optional[dict[str, Any]] = None
    linked_video_project_id: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StoryEpisodeSourceSummaryResponse(BaseModel):
    """Lightweight structured source summary for a Story Episode."""

    source_document_id: Optional[str] = None
    revision: Optional[int] = None
    source_kind: Optional[str] = None
    comic_job_id: Optional[str] = None
    comic_analysis_revision: Optional[int] = None
    chunk_count: int = 0
    page_count: int = 0
    panel_count: int = 0
    dialogue_count: int = 0
    coverage_metrics: Optional[dict[str, Any]] = None
    limitations: Optional[List[Any]] = None
    has_structured_source: bool = False

class StoryEpisodeResponse(BaseModel):
    """Story Studio episode with candidates and adaptations."""

    id: str
    series_id: str
    episode_number: int
    title: Optional[str] = None
    output_intent: str
    market_profile: str
    language_profile: str
    source_input: Optional[str] = None
    source_digest: Optional[str] = None
    current_source_document_id: Optional[str] = None
    source_summary: StoryEpisodeSourceSummaryResponse = Field(default_factory=StoryEpisodeSourceSummaryResponse)
    output_settings: StoryEpisodeOutputSettings = Field(default_factory=StoryEpisodeOutputSettings)
    master_story_json: Optional[dict[str, Any]] = None
    selection_reason: Optional[str] = None
    approval_status: str
    approved_at: Optional[datetime] = None
    revision: int = 1
    candidates: List[StoryScenarioCandidateResponse] = Field(default_factory=list)
    adaptations: List[StoryAdaptationResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StoryCandidateSelectionRequest(BaseModel):
    """Choose or synthesize a Master Story from generated candidates."""

    candidate_id: Optional[str] = None
    master_story_json: Optional[dict[str, Any]] = None
    selection_reason: Optional[str] = Field(default=None, max_length=4000)

class StoryCandidateSynthesisRequest(BaseModel):
    """Synthesize a Master Story from the strongest parts of generated candidates."""

    candidate_ids: Optional[List[str]] = Field(default=None, max_length=3)
    user_direction: Optional[str] = Field(default=None, max_length=4000)

class StoryApprovalRequest(BaseModel):
    """Approve or reject a Master Story."""

    approved: bool = True

class StoryPanelPromptApprovalRequest(BaseModel):
    """Approve or unapprove image prompts for selected panels."""

    panel_orders: Optional[List[int]] = Field(default=None, max_length=200)
    approved: bool = True
    canon_override_reason: Optional[str] = Field(default=None, max_length=4000)

class StoryPanelPromptUpdateRequest(BaseModel):
    """Edit a single panel prompt and reset approval when needed."""

    panel_order: int = Field(..., ge=1, le=10000)
    prompt: Optional[str] = Field(default=None, max_length=12000)
    negative_prompt: Optional[str] = Field(default=None, max_length=4000)
    caption_or_dialogue: Optional[str] = Field(default=None, max_length=4000)
    visual_description: Optional[str] = Field(default=None, max_length=4000)

class StoryPromptRepairRequest(BaseModel):
    """Run bounded auto-repair for one Story Studio panel prompt."""

    panel_order: int = Field(..., ge=1, le=10000)
    max_attempts: int = Field(default=2, ge=1, le=5)

class StoryImageRenderRequest(BaseModel):
    """Request image rendering for approved prompts."""

    panel_orders: Optional[List[int]] = Field(default=None, max_length=200)
    image_provider_configured: bool = False
    provider: str = Field(default="manual", max_length=80)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

class StoryImageRenderResult(BaseModel):
    """One panel result returned by an image provider adapter."""

    panel_order: int = Field(..., ge=1, le=10000)
    status: str = Field(default="completed", pattern="^(completed|failed)$")
    image_path: Optional[str] = Field(default=None, max_length=4000)
    image_url: Optional[str] = Field(default=None, max_length=4000)
    provider_asset_id: Optional[str] = Field(default=None, max_length=4000)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = Field(default=None, max_length=4000)

class StoryImageRenderJobUpdateRequest(BaseModel):
    """Update a Story Studio image render job from an adapter callback."""

    status: str = Field(..., pattern="^(queued|rendering|completed|failed)$")
    results: List[StoryImageRenderResult] = Field(default_factory=list, max_length=200)
    message: Optional[str] = Field(default=None, max_length=4000)

class StoryVideoHandoffRequest(BaseModel):
    """Create or reopen the linked AI Video project for a Story Episode."""

    open_existing: bool = True
    source_mode: str = Field(default="auto", pattern="^(auto|master_story|image_story_prompts)$")
    start_auto_run: bool = False
    material_target: str = Field(default="prompts_only", pattern="^(prompts_only|full_materials)$")

class StorySuggestionResponse(BaseModel):
    """Draft continuity or character updates that are not saved automatically."""

    suggestions: List[dict[str, Any]] = Field(default_factory=list)
    saved: bool = False
    message: str

class StorySuggestionApprovalRequest(BaseModel):
    """Approve or reject drafted continuity/profile updates before saving them."""

    approved: bool = True
    suggestions: List[dict[str, Any]] = Field(default_factory=list, max_length=200)

class VideoSeriesCreate(BaseModel):
    """Request model for creating an optional AI Video series."""

    title: str = Field(..., min_length=1, max_length=160)
    series_mode: str = Field(default="video_story_only", pattern=SERIES_MODE_PATTERN)
    character_bible: Optional[str] = Field(default=None, max_length=50000)
    world_bible: Optional[str] = Field(default=None, max_length=50000)
    style_bible: Optional[str] = Field(default=None, max_length=50000)
    continuity_rules: Optional[str] = Field(default=None, max_length=50000)
    negative_rules: Optional[str] = Field(default=None, max_length=50000)
    previous_episode_summary: Optional[str] = Field(default=None, max_length=50000)

class VideoSeriesUpdate(BaseModel):
    """Partial update for an AI Video series and its Series Bible."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    character_bible: Optional[str] = Field(default=None, max_length=50000)
    world_bible: Optional[str] = Field(default=None, max_length=50000)
    style_bible: Optional[str] = Field(default=None, max_length=50000)
    continuity_rules: Optional[str] = Field(default=None, max_length=50000)
    negative_rules: Optional[str] = Field(default=None, max_length=50000)
    previous_episode_summary: Optional[str] = Field(default=None, max_length=50000)
    latest_episode_number: Optional[int] = Field(default=None, ge=0, le=10000)

class VideoSeriesResponse(BaseModel):
    """Series summary including Bible fields for edit screens."""

    id: str
    title: str
    series_mode: str = "video_story_only"
    character_bible: Optional[str] = None
    world_bible: Optional[str] = None
    style_bible: Optional[str] = None
    continuity_rules: Optional[str] = None
    negative_rules: Optional[str] = None
    previous_episode_summary: Optional[str] = None
    latest_episode_number: int = 0
    revision: int = 1
    episode_count: int = 0
    story_episode_count: int = 0
    video_episode_count: int = 0
    character_profiles: List[SeriesCharacterProfileResponse] = Field(default_factory=list)
    provider_project_binding: Optional[VideoProviderProjectBindingResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoEpisodeCreate(_VisualStyleLimitedModel):
    """Create a new episode project from a series."""

    topic: str = Field(..., min_length=1, max_length=4000)
    episode_title: Optional[str] = Field(default=None, max_length=160)
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    title: Optional[str] = Field(default=None, max_length=160)
    language: str = Field(default="en", max_length=20)
    target_language: Optional[str] = Field(default=None, pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    speech_source: Optional[str] = Field(
        default=None,
        pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$",
    )
    video_purpose: Optional[str] = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    target_duration_seconds: Optional[int] = Field(default=None, ge=5, le=7200)
    aspect_ratio: Optional[str] = Field(default=None, pattern="^(9:16|16:9|1:1)$")
    visual_style: Optional[str] = Field(default=None, max_length=2000)
    voice_profile_id: Optional[str] = None
    phase: str = Field(default="phase2", pattern="^(phase1|phase2)$")
    default_shot_duration_seconds: Optional[int] = Field(default=None, ge=1, le=5)
    prompt_segment_count: Optional[int] = Field(default=None, ge=1, le=100)
    prompt_segment_duration_seconds: Optional[int] = Field(default=None, ge=3, le=30)
    micro_scenes_per_prompt: Optional[int] = Field(default=None, ge=1, le=5)
    source_blocks: List[VideoSourceBlockDraft] = Field(default_factory=list, max_length=40)
    reuse_latest_config: bool = True

class VideoGeneratedDataResetResponse(BaseModel):
    project_id: str
    message: str
    deleted_counts: dict[str, int] = Field(default_factory=dict)

class VideoSeriesSummaryUpdateRequest(BaseModel):
    summary: Optional[str] = Field(default=None, max_length=50000)

class VideoProjectCreate(_VisualStyleLimitedModel):
    """Request model for creating an AI Video Assistant project."""

    topic: str = Field(..., min_length=1, max_length=4000)
    source_note: Optional[str] = Field(default=None, max_length=10000)
    title: Optional[str] = Field(default=None, max_length=160)
    series_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    episode_title: Optional[str] = Field(default=None, max_length=160)
    language: str = Field(default="en", max_length=20)
    target_language: str = Field(default="en", pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    speech_source: Optional[str] = Field(
        default=None,
        pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$",
    )
    video_purpose: str = Field(default=video_purpose_service.VIDEO_PURPOSE_CUSTOM, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    target_duration_seconds: Optional[int] = Field(default=None, ge=5, le=7200)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1)$")
    visual_style: Optional[str] = Field(default=None, max_length=2000)
    voice_profile_id: Optional[str] = None
    phase: str = Field(default="phase1", pattern="^(phase1|phase2)$")
    default_shot_duration_seconds: Optional[int] = Field(default=3, ge=1, le=5)
    prompt_segment_count: Optional[int] = Field(default=None, ge=1, le=100)
    prompt_segment_duration_seconds: Optional[int] = Field(default=None, ge=3, le=30)
    micro_scenes_per_prompt: Optional[int] = Field(default=None, ge=1, le=5)
    source_blocks: List[VideoSourceBlockDraft] = Field(default_factory=list, max_length=40)

class VideoProjectUpdate(_VisualStyleLimitedModel):
    """Partial update for an AI Video Assistant project."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    topic: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    series_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    episode_title: Optional[str] = Field(default=None, max_length=160)
    language: Optional[str] = Field(default=None, max_length=20)
    target_language: Optional[str] = Field(default=None, pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    speech_source: Optional[str] = Field(default=None, pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$")
    speech_mode: Optional[str] = Field(default=None, pattern="^(veo_narration|veo_dialogue|voicebox_co_context|voicebox_khong_context|none)$")
    video_purpose: Optional[str] = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    target_duration_seconds: Optional[int] = Field(default=None, ge=5, le=7200)
    aspect_ratio: Optional[str] = Field(default=None, pattern="^(9:16|16:9|1:1)$")
    visual_style: Optional[str] = Field(default=None, max_length=2000)
    voice_profile_id: Optional[str] = None
    default_shot_duration_seconds: Optional[int] = Field(default=None, ge=1, le=5)
    prompt_segment_count: Optional[int] = Field(default=None, ge=1, le=100)
    prompt_segment_duration_seconds: Optional[int] = Field(default=None, ge=3, le=30)
    micro_scenes_per_prompt: Optional[int] = Field(default=None, ge=1, le=5)
    continuity_bible: Optional[str] = Field(default=None, max_length=50000)

class VideoProjectResponse(BaseModel):
    """List/detail summary for an AI Video Assistant project."""

    id: str
    series_id: Optional[str] = None
    story_episode_id: Optional[str] = None
    episode_number: Optional[int] = None
    episode_title: Optional[str] = None
    series_title: Optional[str] = None
    title: str
    topic: str
    language: str
    target_language: str = "en"
    speech_source: Optional[str] = None
    video_purpose: str = video_purpose_service.VIDEO_PURPOSE_CUSTOM
    dialogue_mode: str = "voiceover"
    narration_density: str = "balanced"
    call_to_action_style: Optional[str] = None
    target_duration_seconds: Optional[int] = None
    aspect_ratio: str
    visual_style: Optional[str] = None
    voice_profile_id: Optional[str] = None
    status: str
    script_approved: bool
    story_approved: bool = False
    phase: str = "phase1"
    default_shot_duration_seconds: Optional[int] = None
    prompt_segment_count: Optional[int] = None
    prompt_segment_duration_seconds: Optional[int] = None
    micro_scenes_per_prompt: Optional[int] = None
    planning_status: str = "draft"
    planning_error: Optional[str] = None
    last_request_id: Optional[str] = None
    active_run_status: Optional[str] = None
    active_run_step: Optional[str] = None
    active_run_progress: Optional[float] = None
    provider_project_binding: Optional[VideoProviderProjectBindingResponse] = None
    package_stale: bool
    scene_count: int = 0
    shot_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProjectLocalizeRequest(BaseModel):
    """Create a separate localized copy of an AI Video project."""

    target_language: str = Field(..., pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    video_purpose: str = Field(default="localized_variant", pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    title: Optional[str] = Field(default=None, max_length=160)
    voice_profile_id: Optional[str] = None

class VideoSceneResponse(BaseModel):
    """Response model for an AI Video Assistant scene."""

    id: str
    project_id: str
    scene_order: int
    title: Optional[str] = None
    dialogue: str
    visual_description: Optional[str] = None
    target_duration_seconds: Optional[int] = None
    approved: bool = False
    no_narration: bool = False
    prompt_status: str
    voice_status: str
    subtitle_status: str
    generation_id: Optional[str] = None
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None
    voice_failure_reason: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProjectDetailResponse(VideoProjectResponse):
    """Project detail with ordered scene rows and planning artifacts."""

    creative_brief: Optional[str] = None
    script_text: Optional[str] = None
    style_bible: Optional[str] = None
    character_bible: Optional[str] = None
    input_synthesis: Optional[str] = None
    story_strategy: Optional[str] = None
    continuity_bible: Optional[str] = None
    detailed_script: Optional[str] = None
    retention_plan_json: Optional[dict[str, Any]] = None
    sound_design_plan_json: Optional[dict[str, Any]] = None
    source_blocks: List[VideoSourceBlockResponse] = Field(default_factory=list)
    scenes: List[VideoSceneResponse] = Field(default_factory=list)
    shots: List[VideoShotResponse] = Field(default_factory=list)

class VideoSceneUpdate(BaseModel):
    """Partial update for one scene."""

    title: Optional[str] = Field(default=None, max_length=160)
    dialogue: Optional[str] = Field(default=None, max_length=20000)
    visual_description: Optional[str] = Field(default=None, max_length=4000)
    target_duration_seconds: Optional[int] = Field(default=None, ge=1, le=3600)

class VideoScenesReplaceRequest(BaseModel):
    """Replace all ordered scenes for a project."""

    scenes: List[VideoSceneDraft] = Field(..., min_length=1, max_length=200)

class VideoScriptApprovalRequest(BaseModel):
    """Approve or unapprove the current script/scene breakdown."""

    approved: bool = True

class VideoSceneApprovalRequest(BaseModel):
    """Approve or unapprove one scene for prompt/voice generation."""

    approved: bool = True

class VideoSceneNoNarrationRequest(BaseModel):
    """Mark whether a scene intentionally has no narration."""

    no_narration: bool = True

class VideoSceneNarrationRequest(BaseModel):
    """Create or retry narration for one AI Video scene using existing TTS settings."""

    profile_id: Optional[str] = None
    language: Optional[str] = Field(
        default=None,
        pattern="^(zh|en|ja|ko|de|fr|ru|pt|es|it|he|ar|da|el|fi|hi|ms|nl|no|pl|sv|sw|tr|vi)$",
    )
    seed: Optional[int] = Field(None, ge=0)
    model_size: Optional[str] = Field(default="1.7B", pattern="^(1\\.7B|0\\.6B|1B|3B)$")
    instruct: Optional[str] = Field(None, max_length=500)
    engine: Optional[str] = Field(default=None, pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$")
    normalize: bool = True
    max_chunk_chars: int = Field(default=800, ge=100, le=5000)
    crossfade_ms: int = Field(default=50, ge=0, le=500)
    force: bool = False

class VideoProjectStatusResponse(BaseModel):
    """Non-technical readiness flags for the AI Video Assistant wizard."""

    project_id: str
    planning_active: bool = False
    planning_active_step: Optional[str] = None
    missing_script: bool
    missing_prompt: bool
    missing_voice: bool
    missing_subtitle: bool
    package_stale: bool
    package_ready: bool
    missing_scene_ids: List[str] = Field(default_factory=list)
    story_approved: bool = False
    missing_source_blocks: bool = False
    missing_shots: bool = False
    missing_video_prompt_shot_ids: List[str] = Field(default_factory=list)
    stale_prompt_shot_ids: List[str] = Field(default_factory=list)
    missing_voice_shot_ids: List[str] = Field(default_factory=list)
    publishing_metadata_status: str = "missing"
    publishing_metadata_ready: bool = False
    publishing_metadata_stale: bool = False
    publishing_metadata_revision: Optional[int] = None

class VideoScenePromptResponse(BaseModel):
    """Prompt artifact returned for one scene."""

    id: str
    project_id: str
    scene_id: str
    version: int
    main_prompt: str
    negative_prompt: Optional[str] = None
    aspect_ratio: Optional[str] = None
    style_notes: Optional[str] = None
    character_notes: Optional[str] = None
    prompt_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoPromptPackResponse(BaseModel):
    """Prompt pack generated for approved scenes."""

    project_id: str
    prompts: List[VideoScenePromptResponse] = Field(default_factory=list)

class VideoPromptContentResponse(BaseModel):
    """Plain-text prompt content ready to copy."""

    project_id: str
    scene_id: Optional[str] = None
    shot_id: Optional[str] = None
    prompt_id: str
    filename: str
    content: str
    prompt_explanation_vi: Optional[str] = None
    negative_prompt: Optional[str] = None
    retention_notes: Optional[str] = None
    transition_notes: Optional[str] = None
    sound_design_notes: Optional[str] = None
    quality_status: Optional[str] = None
    quality_check: Optional[dict[str, Any]] = None
    quality_threshold: float = 85.0
    repair_attempt: int = 0
    repair_status: str = "none"
    repair_changes: dict[str, Any] = Field(default_factory=dict)

class VideoPublishingPlatformContent(BaseModel):
    """One platform-specific publishing copy bundle."""

    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=6000)
    hashtags: List[str] = Field(default_factory=list, max_length=30)
    thumbnail_prompt: str = Field(default="", max_length=6000)
    status: str = "missing"
    input_fingerprint: Optional[str] = None
    revision: int = 1

class VideoPublishingMetadataGenerateRequest(BaseModel):
    """Create or regenerate publishing metadata for one project."""

    platform: str = Field(default="all", pattern="^(all|youtube|tiktok|facebook)$")
    force: bool = False

class VideoPublishingMetadataResponse(BaseModel):
    """Project-level publishing copy for YouTube, TikTok and Facebook."""

    id: Optional[str] = None
    project_id: str
    status: str = "missing"
    target_language: str = "en"
    platforms: dict[str, VideoPublishingPlatformContent] = Field(default_factory=dict)
    input_fingerprint: Optional[str] = None
    revision: int = 0
    stale: bool = False
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    request_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class VideoSceneAssetResponse(BaseModel):
    """Preview image asset attached to a scene."""

    id: str
    project_id: str
    scene_id: str
    asset_type: str
    file_path: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AIVideoErrorResponse(BaseModel):
    """Friendly AI Video error returned to the wizard."""

    message: str
    error_code: str
    request_id: str


class VideoSceneVoiceStatusResponse(BaseModel):
    """Narration status for one AI Video scene."""

    project_id: str
    scene_id: str
    scene_order: int
    no_narration: bool = False
    voice_status: str
    generation_id: Optional[str] = None
    audio_path: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    failure_reason: Optional[str] = None

class VideoShotVoiceStatusResponse(BaseModel):
    """Narration status for one AI Video phase-2 shot."""

    project_id: str
    shot_id: str
    shot_order: int
    scene_id: Optional[str] = None
    voice_status: str
    generation_id: Optional[str] = None
    audio_path: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    failure_reason: Optional[str] = None


class VideoSubtitleCue(BaseModel):
    """One generated SRT subtitle cue."""

    index: int
    scene_id: Optional[str] = None
    scene_order: Optional[int] = None
    shot_id: Optional[str] = None
    shot_order: Optional[int] = None
    start_seconds: float
    end_seconds: float
    text: str


class VideoSubtitleResponse(BaseModel):
    """Subtitle artifact for a video project."""

    id: str
    project_id: str
    status: str
    subtitle_path: Optional[str] = None
    format: str = "srt"
    cues: List[VideoSubtitleCue] = Field(default_factory=list)
    revision: int = 1
    created_at: datetime
    updated_at: datetime


class VideoPackageReadinessResponse(BaseModel):
    """Checklist used before creating a Premiere materials package."""

    project_id: str
    language: str = "en"
    speech_source: str = "project_audio"
    video_purpose: str = video_purpose_service.VIDEO_PURPOSE_CUSTOM
    dialogue_mode: str = "voiceover"
    narration_density: str = "balanced"
    ready: bool
    missing_prompt_scene_ids: List[str] = Field(default_factory=list)
    missing_video_prompt_shot_ids: List[str] = Field(default_factory=list)
    missing_voice_scene_ids: List[str] = Field(default_factory=list)
    missing_voice_shot_ids: List[str] = Field(default_factory=list)
    missing_subtitle: bool = False
    missing_reasons: List[str] = Field(default_factory=list)


class VideoPackageManifestScene(BaseModel):
    """Human-readable manifest entry for one scene in the ZIP package."""

    scene_id: str
    scene_order: int
    title: Optional[str] = None
    prompt_filename: Optional[str] = None
    audio_filename: Optional[str] = None
    preview_image_filename: Optional[str] = None
    no_narration: bool = False


class VideoPackageManifestResponse(BaseModel):
    """Manifest content stored next to a generated ZIP package."""

    project_id: str
    project_title: str
    language: str
    speech_source: str = "project_audio"
    video_purpose: str = video_purpose_service.VIDEO_PURPOSE_CUSTOM
    dialogue_mode: str = "voiceover"
    narration_density: str = "balanced"
    call_to_action_style: Optional[str] = None
    aspect_ratio: str
    subtitle_filename: Optional[str] = None
    scenes: List[VideoPackageManifestScene] = Field(default_factory=list)


class VideoPackageExportResponse(BaseModel):
    """Persisted ZIP export status for Premiere materials."""

    id: str
    project_id: str
    status: str
    manifest_path: Optional[str] = None
    zip_path: Optional[str] = None
    stale: bool = False
    failure_reason: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoAutoRunStartRequest(BaseModel):
    """Start an AI Video material auto-run."""

    mode: str = Field(default="review_gated", pattern="^(review_gated|full_auto)$")
    material_target: str = Field(default="full_materials", pattern="^(full_materials|prompts_only|publishing_kit|video_clips)$")
    force: bool = False

class VideoAutoRunContinueRequest(BaseModel):
    """Continue an auto-run after review or missing input was handled."""

    approved: bool = True

class VideoAutoRunRetryRequest(BaseModel):
    """Retry a failed or needs-input auto-run without forcing unrelated artifacts."""

    force: bool = False

class VideoAutoRunSummary(BaseModel):
    """Safe material readiness summary for one auto-run."""

    shot_count: int = 0
    prompt_completed_count: int = 0
    prompt_required_count: int = 0
    voice_completed_count: int = 0
    voice_required_count: int = 0
    clip_completed_count: int = 0
    clip_required_count: int = 0
    clip_generation_job_id: Optional[str] = None
    clip_generation_status: Optional[str] = None
    clip_generation_error_code: Optional[str] = None
    clip_generation_failure_reason: Optional[str] = None
    render_job_id: Optional[str] = None
    render_job_status: Optional[str] = None
    render_job_error_code: Optional[str] = None
    render_job_failure_reason: Optional[str] = None
    render_output_path: Optional[str] = None
    publishing_metadata_status: str = "missing"
    publishing_metadata_ready: bool = False
    publishing_metadata_stale: bool = False
    publishing_metadata_revision: Optional[int] = None
    publishing_metadata_platforms_ready: int = 0
    subtitle_status: str = "missing"
    package_status: Optional[str] = None
    package_id: Optional[str] = None
    core_ready: bool = False
    package_ready: bool = False

class VideoAutoRunResponse(BaseModel):
    """Persisted AI Video material auto-run status."""

    id: str
    project_id: str
    mode: str
    material_target: str = "full_materials"
    status: str
    current_step: str
    review_stage: Optional[str] = None
    progress: float = 0.0
    force: bool = False
    step_results_json: Optional[dict[str, Any]] = None
    completed_steps: List[str] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    summary: VideoAutoRunSummary = Field(default_factory=VideoAutoRunSummary)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationFrameResponse(BaseModel):
    """Frame sampled from a video inspiration job."""

    id: str
    job_id: str
    shot_id: Optional[str] = None
    shot_order: Optional[int] = None
    frame_role: str = "keyframe"
    frame_path: str
    timestamp_seconds: float
    description_vi: Optional[str] = None
    technical_metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationShotResponse(BaseModel):
    id: str
    job_id: str
    shot_order: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    keyframe_ids_json: Optional[list[str]] = None
    visual_description_vi: Optional[str] = None
    subjects_json: Optional[dict[str, Any] | list[Any]] = None
    setting_json: Optional[dict[str, Any] | list[Any]] = None
    camera_json: Optional[dict[str, Any]] = None
    subject_motion_json: Optional[dict[str, Any] | list[Any]] = None
    transition_in: Optional[str] = None
    transition_out: Optional[str] = None
    on_screen_text_json: Optional[list[dict[str, Any]]] = None
    confidence_json: Optional[dict[str, Any]] = None
    limitations_json: Optional[list[str] | dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationTranscriptSegmentResponse(BaseModel):
    id: str
    job_id: str
    segment_order: int
    start_seconds: float
    end_seconds: float
    text: str
    raw_text: Optional[str] = None
    language: Optional[str] = None
    speaker_label: Optional[str] = None
    source: str = "stt_raw"
    timestamp_precision: str = "chunk"
    confidence: Optional[float] = None
    shot_ids_json: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationAudioEventResponse(BaseModel):
    id: str
    job_id: str
    event_order: int
    event_type: str
    start_seconds: float
    end_seconds: float
    description_vi: Optional[str] = None
    confidence: Optional[float] = None
    technical_metadata_json: Optional[dict[str, Any]] = None
    shot_ids_json: Optional[list[str]] = None
    transcript_segment_ids_json: Optional[list[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationTextEventResponse(BaseModel):
    id: str
    job_id: str
    shot_id: Optional[str] = None
    event_order: int
    start_seconds: float
    end_seconds: float
    text: str
    language: Optional[str] = None
    role: str = "unknown"
    region_json: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None
    source: str = "vision"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationRetentionBeatResponse(BaseModel):
    id: str
    job_id: str
    beat_order: int
    start_seconds: float
    end_seconds: float
    role: str
    viewer_question_before: Optional[str] = None
    content_promise: Optional[str] = None
    new_information: Optional[str] = None
    emotional_or_stakes_change: Optional[str] = None
    question_answered: Optional[str] = None
    new_open_loop: Optional[str] = None
    micro_payoff: Optional[str] = None
    why_continue: Optional[str] = None
    drop_off_risks_json: Optional[list[str] | dict[str, Any]] = None
    evidence_refs_json: Optional[list[dict[str, Any]] | list[str]] = None
    confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationJobResponse(BaseModel):
    """State and artifacts for the video inspiration workflow."""

    id: str
    source_type: str
    source_url: Optional[str] = None
    original_filename: Optional[str] = None
    source_platform: str = "unknown"
    source_path: Optional[str] = None
    audio_path: Optional[str] = None
    source_duration_seconds: Optional[float] = None
    status: str
    current_step: str
    progress: float = 0.0
    target_language: str = "vi"
    rewrite_mode: str = "bold_remix"
    user_direction: Optional[str] = None
    transcript_text: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_status: str = "pending"
    analysis_schema_version: str = "video_analysis_package.v1"
    analysis_mode: str = "quick"
    analysis_package_json: Optional[dict[str, Any]] = None
    analysis_package_path: Optional[str] = None
    coverage_metrics_json: Optional[dict[str, Any]] = None
    limitations_json: Optional[list[str] | dict[str, Any]] = None
    retention_source: str = "predicted_from_content"
    analysis_completeness: str = "not_started"
    visual_summary: Optional[str] = None
    analysis_json: Optional[dict[str, Any]] = None
    rewritten_script: Optional[str] = None
    script_title: Optional[str] = None
    big_idea: Optional[str] = None
    hook: Optional[str] = None
    created_video_project_id: Optional[str] = None
    latest_auto_run_id: Optional[str] = None
    ai_video_url: Optional[str] = None
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None
    frames: List[VideoInspirationFrameResponse] = Field(default_factory=list)
    shots: List[VideoInspirationShotResponse] = Field(default_factory=list)
    transcript_segments: List[VideoInspirationTranscriptSegmentResponse] = Field(default_factory=list)
    audio_events: List[VideoInspirationAudioEventResponse] = Field(default_factory=list)
    on_screen_text_events: List[VideoInspirationTextEventResponse] = Field(default_factory=list)
    content_retention_beats: List[VideoInspirationRetentionBeatResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationListResponse(BaseModel):
    items: List[VideoInspirationJobResponse]
    total: int

class VideoInspirationStructuredHandoffResponse(BaseModel):
    id: str
    job_id: str
    analysis_package_path: Optional[str] = None
    analysis_package_revision: str = "video_analysis_package.v1"
    schema_version: str = "video_inspiration_handoff.v1"
    status: str
    target_language: str = "vi"
    approved_script_revision: int = 1
    payload_json: dict[str, Any]
    source_blocks_json: Optional[list[dict[str, Any]]] = None
    created_project_id: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VideoInspirationHandoffListResponse(BaseModel):
    items: List[VideoInspirationStructuredHandoffResponse]
    total: int

class VideoInspirationUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=4000)
    target_language: str = Field(default="vi", pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    user_direction: Optional[str] = Field(default=None, max_length=20000)
    use_browser_cookies: bool = False

class VideoInspirationAnalyzeRequest(BaseModel):
    allow_audio_only: bool = False
    stt_model: Optional[str] = Field(default=None, pattern="^(base|small|medium|large|turbo)$")
    analysis_mode: str = Field(default="quick", pattern="^(quick|high_quality)$")
    handoff_to_ai_video: bool = False

class VideoInspirationTranscriptUpdate(BaseModel):
    transcript_text: str = Field(..., max_length=120000)

class VideoInspirationTranscriptSegmentUpdate(BaseModel):
    text: str = Field(..., max_length=20000)
    speaker_label: Optional[str] = Field(default=None, max_length=120)

class VideoInspirationTextEventUpdate(BaseModel):
    text: str = Field(..., max_length=4000)
    language: Optional[str] = Field(default=None, max_length=24)
    role: Optional[str] = Field(default=None, max_length=80)

class VideoProjectMemoryCardResponse(BaseModel):
    id: str
    project_id: str
    series_id: Optional[str] = None
    memory_scope: str = "project"
    card_type: str
    title: str
    content_json: dict[str, Any]
    status: str = "approved"
    source_type: str = "handoff"
    source_ref_id: Optional[str] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VideoProjectMemoryListResponse(BaseModel):
    items: List[VideoProjectMemoryCardResponse]
    total: int

class VideoProjectTargetTimelineBeatResponse(BaseModel):
    id: str
    project_id: str
    handoff_id: Optional[str] = None
    beat_order: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    role: str
    content: Optional[str] = None
    viewer_question: Optional[str] = None
    new_information: Optional[str] = None
    micro_payoff: Optional[str] = None
    visual_direction: Optional[str] = None
    audio_direction: Optional[str] = None
    evidence_refs_json: Optional[list[dict[str, Any]] | list[str]] = None
    source_lesson_refs_json: Optional[list[dict[str, Any]] | list[str]] = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProjectTargetTimelineResponse(BaseModel):
    items: List[VideoProjectTargetTimelineBeatResponse]
    total: int

class VideoProjectContextCompileRequest(BaseModel):
    task_type: str = Field(..., pattern="^(story|shot|prompt_image|prompt_video|voice|subtitle)$")
    artifact_type: Optional[str] = Field(default=None, max_length=80)
    artifact_id: Optional[str] = Field(default=None, max_length=120)

class VideoProjectContextSnapshotResponse(BaseModel):
    id: str
    project_id: str
    task_type: str
    artifact_type: Optional[str] = None
    artifact_id: Optional[str] = None
    context_json: dict[str, Any]
    source_refs_json: Optional[list[dict[str, Any]] | list[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VideoProjectContextSnapshotListResponse(BaseModel):
    items: List[VideoProjectContextSnapshotResponse]
    total: int

class VideoQualityRubricConfig(BaseModel):
    content_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    presentation_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    video_type: Optional[str] = Field(default=None, max_length=80)
    special_content_weight_confirmed: bool = False

    @model_validator(mode="after")
    def _validate_weights(self) -> "VideoQualityRubricConfig":
        total = self.content_weight + self.presentation_weight
        if not 0.99 <= total <= 1.01:
            raise ValueError("Tổng trọng số content và presentation phải bằng 1.0.")
        if self.content_weight < 0.60 and not self.special_content_weight_confirmed:
            raise ValueError("Trọng số nội dung không được dưới 60% nếu chưa xác nhận cấu hình đặc biệt.")
        return self

class VideoQualityRunRequest(BaseModel):
    force: bool = False
    rubric: Optional[VideoQualityRubricConfig] = None

class VideoQualityOverrideRequest(BaseModel):
    status: str = Field(..., pattern="^(passed|needs_review|blocked)$")
    reason: str = Field(..., min_length=8, max_length=4000)
    overridden_by: Optional[str] = Field(default=None, max_length=120)

class VideoQualityReportResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    scope: str = "project"
    status: str = Field(default="not_checked", pattern=VIDEO_QUALITY_STATUS_PATTERN)
    overall_status: str = Field(default="not_checked", pattern=VIDEO_QUALITY_STATUS_PATTERN)
    content_score: float = 0.0
    presentation_score: float = 0.0
    total_score: float = 0.0
    rubric_json: dict[str, Any] = Field(default_factory=dict)
    sections_json: dict[str, Any] = Field(default_factory=dict)
    blocking_errors_json: Optional[list[Any]] = None
    warnings_json: Optional[list[Any]] = None
    recommended_actions_json: Optional[list[Any]] = None
    evidence_json: Optional[dict[str, Any] | list[Any]] = None
    dependencies_json: Optional[dict[str, Any] | list[Any]] = None
    override_history_json: Optional[list[dict[str, Any]]] = None
    revision: int = 1
    checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoQualityReportListResponse(BaseModel):
    items: List[VideoQualityReportResponse]
    total: int

class PlatformRetentionDataPoint(BaseModel):
    timestamp_seconds: Optional[float] = Field(default=None, ge=0.0, le=7200.0)
    duration_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    retention_percent: Optional[float] = Field(default=None, ge=0.0, le=200.0)
    rewatch_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    label: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=2000)

class PlatformRetentionDatasetCreateRequest(BaseModel):
    platform: str = Field(default="manual", max_length=80)
    video_duration_seconds: float = Field(..., gt=0.0, le=7200.0)
    data_points: List[PlatformRetentionDataPoint] = Field(..., min_length=1, max_length=2000)
    average_watch_time: Optional[float] = Field(default=None, ge=0.0, le=7200.0)
    completion_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    rewatch_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    cta_click_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    conversion_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    source_type: str = Field(default="manual", pattern="^(manual|csv|json|platform_export)$")

class PlatformRetentionDatasetResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    platform: str
    video_duration_seconds: float
    data_points_json: list[dict[str, Any]]
    normalized_points_json: list[dict[str, Any]]
    average_watch_time: Optional[float] = None
    completion_rate: Optional[float] = None
    rewatch_rate: Optional[float] = None
    cta_click_rate: Optional[float] = None
    conversion_rate: Optional[float] = None
    source_type: str = "manual"
    linked_findings_json: Optional[list[dict[str, Any]]] = None
    imported_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class PlatformRetentionDatasetListResponse(BaseModel):
    items: List[PlatformRetentionDatasetResponse]
    total: int

class VideoInspirationDirectionUpdate(BaseModel):
    user_direction: Optional[str] = Field(default=None, max_length=20000)

class VideoInspirationRewriteRequest(BaseModel):
    target_language: Optional[str] = Field(default=None, pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    user_direction: Optional[str] = Field(default=None, max_length=20000)

class VideoInspirationVariantGenerateRequest(BaseModel):
    candidate_count: int = Field(default=2, ge=2, le=3)

class VideoInspirationVariantScoreRequest(BaseModel):
    variant_ids: List[str] = Field(default_factory=list, max_length=3)

class VideoInspirationVariantSynthesisRequest(BaseModel):
    variant_ids: List[str] = Field(default_factory=list, max_length=3)
    final_version_count: int = Field(default=1, ge=1, le=3)
    strategy: str = Field(default="balanced", pattern="^(balanced|hook|emotion|retention|visual)$")

class VideoInspirationVariantSelectRequest(BaseModel):
    variant_id: str = Field(..., min_length=1, max_length=120)

class VideoInspirationScriptUpdate(BaseModel):
    rewritten_script: str = Field(..., min_length=1, max_length=160000)
    script_title: Optional[str] = Field(default=None, max_length=160)
    big_idea: Optional[str] = Field(default=None, max_length=20000)
    hook: Optional[str] = Field(default=None, max_length=12000)

class VideoInspirationCreateProjectRequest(BaseModel):
    start_full_materials: bool = False
    mode: str = Field(default="full_auto", pattern="^(review_gated|full_auto)$")
    voice_profile_id: Optional[str] = None
    series_id: Optional[str] = None

class VideoInspirationHandoffResponse(BaseModel):
    job: VideoInspirationJobResponse
    project: VideoProjectResponse
    auto_run: Optional[VideoAutoRunResponse] = None
    ai_video_url: str

class MCPClientBindingResponse(BaseModel):
    """Per-MCP-client voice binding — what voice / engine the server should
    use when a given client_id calls voicebox.speak without args, plus an
    opt-in personality-rewrite default."""

    client_id: str
    label: Optional[str] = None
    profile_id: Optional[str] = None
    default_engine: Optional[str] = Field(
        None,
        pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$",
    )
    default_personality: bool = False
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MCPClientBindingUpsert(BaseModel):
    """Create or update a binding. Matched by ``client_id``."""

    client_id: str = Field(..., min_length=1, max_length=64)
    label: Optional[str] = Field(None, max_length=128)
    profile_id: Optional[str] = None
    default_engine: Optional[str] = Field(
        None,
        pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$",
    )
    default_personality: bool = False


class MCPClientBindingListResponse(BaseModel):
    items: List[MCPClientBindingResponse]


class SpeakRequest(BaseModel):
    """Body for POST /speak — non-MCP REST surface that mirrors voicebox.speak."""

    text: str = Field(..., min_length=1, max_length=10000)
    profile: Optional[str] = Field(
        None,
        description="Voice profile name or id. Falls back to per-client binding, then default.",
    )
    engine: Optional[str] = Field(
        None,
        pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$",
    )
    personality: Optional[bool] = Field(
        None,
        description="When true and the profile has a personality prompt, the input text is rewritten in-character before TTS. When null, the per-client binding's default_personality flag decides.",
    )
    language: Optional[str] = Field(
        None,
        pattern="^(zh|en|ja|ko|de|fr|ru|pt|es|it|he|ar|da|el|fi|hi|ms|nl|no|pl|sv|sw|tr)$",
    )


class LLMGenerateRequest(BaseModel):
    """Request model for LLM text generation."""

    prompt: str = Field(..., min_length=1, max_length=50000)
    system: Optional[str] = Field(None, max_length=4000)
    model_size: Optional[str] = Field(default="0.6B", pattern="^(0\\.6B|1\\.7B|4B)$")
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # Few-shot (user, assistant) pairs prepended as real chat turns.
    # Used by the refinement service to pin tricky rules (imperatives
    # staying imperatives, technical-term punctuation) that small models
    # lose when the examples live inline in the system prompt.
    examples: Optional[List[List[str]]] = Field(default=None, max_length=8)


class LLMGenerateResponse(BaseModel):
    """Response model for LLM text generation."""

    text: str
    model_size: str


# ── Profile personality endpoint ──────────────────────────────────────
# The sole standalone personality endpoint is ``/profiles/{id}/compose``,
# which produces a fresh in-character utterance the UI drops into the
# generate textarea. Rewrite is now reached via ``/generate`` with
# ``personality=true``.


class PersonalityTextResponse(BaseModel):
    """Response returned by the ``/profiles/{id}/compose`` endpoint."""

    text: str
    model_size: str


class ModelReadiness(BaseModel):
    """Per-model entry in the dictation readiness checklist.

    ``model_name`` is the canonical id used by ``POST /models/download`` so the
    frontend can wire a one-click "Download" button without a second lookup.
    ``size`` is the user's chosen variant (e.g. "turbo", "0.6B"); ``display_name``
    is what the checklist row should show ("Whisper Turbo").
    """

    ready: bool
    model_name: str
    display_name: str
    size: str
    size_mb: Optional[int] = None


class CaptureReadinessResponse(BaseModel):
    """Backend gates that must be green before the global hotkey will fire.

    The frontend combines this with its own TCC permission checks (input
    monitoring, accessibility) into the full dictation readiness checklist.
    Hotkey-enabled is the user's intent toggle and lives outside this struct.
    """

    stt: ModelReadiness
    llm: ModelReadiness


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    model_loaded: bool
    model_downloaded: Optional[bool] = None  # Whether model is cached/downloaded
    model_size: Optional[str] = None  # Current model size if loaded
    gpu_available: bool
    gpu_type: Optional[str] = None  # GPU type (CUDA, MPS, or None)
    vram_used_mb: Optional[float] = None
    backend_type: Optional[str] = None  # Backend type (mlx or pytorch)
    backend_variant: Optional[str] = None  # Binary variant (cpu or cuda)
    gpu_compatibility_warning: Optional[str] = None  # Warning if GPU arch unsupported


class SystemResourceMetric(BaseModel):
    """Single resource metric used by the system monitor panel."""

    percent: Optional[float] = None
    used: Optional[float] = None
    total: Optional[float] = None
    unit: Optional[str] = None
    label: Optional[str] = None
    status: str = "unknown"


class SystemResourcesResponse(BaseModel):
    """Live host resource usage for the local dashboard."""

    sampled_at: datetime
    cpu: SystemResourceMetric
    memory: SystemResourceMetric
    gpu: SystemResourceMetric
    thermal: SystemResourceMetric
    cpu_count: Optional[int] = None
    gpu_available: bool = False
    gpu_type: Optional[str] = None
    backend_type: Optional[str] = None
    backend_variant: Optional[str] = None


class ResourceModelState(BaseModel):
    """Loaded local model tracked by the resource manager."""

    key: str
    kind: str
    engine: str
    model_size: Optional[str] = None
    display_name: Optional[str] = None
    backend_type: Optional[str] = None
    size_mb: Optional[float] = None
    heavy: bool = False
    loaded: bool = False
    loading: bool = False
    loaded_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_unloaded_at: Optional[datetime] = None
    idle_seconds: Optional[float] = None

class ResourceMemoryStatus(BaseModel):
    """Host memory pressure summary."""

    status: str = "unknown"
    percent: Optional[float] = None
    used_mb: Optional[float] = None
    total_mb: Optional[float] = None

class ResourceCacheStatus(BaseModel):
    """Generic cache metric payload."""

    available: bool = True
    entries: Optional[int] = None
    bytes: Optional[int] = None
    size_mb: Optional[float] = None
    hits_memory: Optional[int] = None
    hits_disk: Optional[int] = None
    misses: Optional[int] = None
    evictions: Optional[int] = None
    files: Optional[int] = None
    disk_files: Optional[int] = None
    disk_bytes: Optional[int] = None
    disk_size_mb: Optional[float] = None
    max_entries: Optional[int] = None
    max_mb: Optional[float] = None
    max_age_days: Optional[int] = None
    ttl_seconds: Optional[int] = None
    error: Optional[str] = None

class ResourceMlxStatus(BaseModel):
    """MLX/Metal cache and active memory metrics."""

    available: bool = False
    cache_bytes: Optional[int] = None
    cache_mb: Optional[float] = None
    active_bytes: Optional[int] = None
    active_mb: Optional[float] = None

class ResourceGenerationQueueStatus(BaseModel):
    """Generation queue state used by cleanup guards."""

    available: bool = True
    max_concurrency: int = 2
    queued: int = 0
    running: int = 0
    queued_ids: List[str] = Field(default_factory=list)
    running_ids: List[str] = Field(default_factory=list)

class ResourceConcurrencyStatus(BaseModel):
    """Shared workflow/planning/STT pool state for the Vietnamese UI."""

    available: bool = True
    max_concurrency: int = 0
    queued: int = 0
    running: int = 0
    queued_keys: List[str] = Field(default_factory=list)
    running_keys: List[str] = Field(default_factory=list)

class ResourceActiveJobsStatus(BaseModel):
    """Active job counts relevant to resource cleanup."""

    generations: List[dict[str, Any]] = Field(default_factory=list)
    generation_count: int = 0
    render_count: int = 0
    auto_run_count: int = 0
    video_inspiration_count: int = 0

class ResourceCleanupAction(BaseModel):
    """One cleanup action result."""

    action: str
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

class ResourceStatusResponse(BaseModel):
    """Resource manager status for local AI Video workflows."""

    sampled_at: datetime
    policy: dict[str, Any] = Field(default_factory=dict)
    memory: ResourceMemoryStatus
    generation_queue: ResourceGenerationQueueStatus
    workflow_pool: ResourceConcurrencyStatus = Field(default_factory=lambda: ResourceConcurrencyStatus(max_concurrency=3))
    planning_pool: ResourceConcurrencyStatus = Field(default_factory=lambda: ResourceConcurrencyStatus(max_concurrency=3))
    stt_pool: ResourceConcurrencyStatus = Field(default_factory=lambda: ResourceConcurrencyStatus(max_concurrency=1))
    active_jobs: ResourceActiveJobsStatus
    models: List[ResourceModelState] = Field(default_factory=list)
    voice_prompt_cache: ResourceCacheStatus
    render_cache: ResourceCacheStatus
    mlx: ResourceMlxStatus
    recent_events: List[dict[str, Any]] = Field(default_factory=list)

class ResourceCleanupRequest(BaseModel):
    """Manual RAM/GPU cleanup request."""

    unload_idle_models: bool = True
    clear_voice_prompt_memory: bool = True
    clear_mlx_cache: bool = True
    clear_render_cache: bool = False
    render_cache_project_id: Optional[str] = None

class ResourceCleanupResponse(BaseModel):
    """Manual RAM/GPU cleanup result."""

    actions: List[ResourceCleanupAction] = Field(default_factory=list)
    status: ResourceStatusResponse

class RenderCacheClearRequest(BaseModel):
    """Clear render intermediate cache globally or for one AI Video project."""

    project_id: Optional[str] = None

class RenderCacheClearResponse(BaseModel):
    """Render intermediate cache clear result."""

    files_deleted: int = 0
    bytes_deleted: int = 0
    project_id: Optional[str] = None

class DirectoryCheck(BaseModel):
    """Health status for a single directory."""

    path: str
    exists: bool
    writable: bool
    error: Optional[str] = None


class FilesystemHealthResponse(BaseModel):
    """Response model for filesystem health check."""

    healthy: bool
    disk_free_mb: Optional[float] = None
    disk_total_mb: Optional[float] = None
    directories: List[DirectoryCheck]


class ModelStatus(BaseModel):
    """Response model for model status."""

    model_name: str
    display_name: str
    hf_repo_id: Optional[str] = None  # HuggingFace repository ID
    downloaded: bool
    downloading: bool = False  # True if download is in progress
    size_mb: Optional[float] = None
    loaded: bool = False


class ModelStatusListResponse(BaseModel):
    """Response model for model status list."""

    models: List[ModelStatus]


class TadaVietnameseStatusResponse(BaseModel):
    """Experimental Vietnamese gate status for TADA 3B."""

    accepted: bool
    local_bypass_enabled: bool = False
    status: str = "missing"
    language: str = "vi"
    model_size: str = "3B"
    aligner_strategy: str
    corpus_version: str
    run_id: Optional[str] = None
    notes: Optional[str] = None
    reviewer: Optional[str] = None


class ModelDownloadRequest(BaseModel):
    """Request model for triggering model download."""

    model_name: str


class ModelMigrateRequest(BaseModel):
    """Request model for migrating models to a new directory."""

    destination: str


class ActiveDownloadTask(BaseModel):
    """Response model for active download task."""

    model_name: str
    status: str
    started_at: datetime
    error: Optional[str] = None
    progress: Optional[float] = None  # 0-100 percentage
    current: Optional[int] = None  # bytes downloaded
    total: Optional[int] = None  # total bytes
    filename: Optional[str] = None  # current file being downloaded


class ActiveGenerationTask(BaseModel):
    """Response model for active generation task."""

    task_id: str
    profile_id: str
    text_preview: str
    started_at: datetime


class ActiveTasksResponse(BaseModel):
    """Response model for active tasks."""

    downloads: List[ActiveDownloadTask]
    generations: List[ActiveGenerationTask]


class AudioChannelCreate(BaseModel):
    """Request model for creating an audio channel."""

    name: str = Field(..., min_length=1, max_length=100)
    device_ids: List[str] = Field(default_factory=list)


class AudioChannelUpdate(BaseModel):
    """Request model for updating an audio channel."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    device_ids: Optional[List[str]] = None


class AudioChannelResponse(BaseModel):
    """Response model for audio channel."""

    id: str
    name: str
    is_default: bool
    device_ids: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ChannelVoiceAssignment(BaseModel):
    """Request model for assigning voices to a channel."""

    profile_ids: List[str]


class ProfileChannelAssignment(BaseModel):
    """Request model for assigning channels to a profile."""

    channel_ids: List[str]


class StoryCreate(BaseModel):
    """Request model for creating a story."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class StoryResponse(BaseModel):
    """Response model for story (list view)."""

    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    class Config:
        from_attributes = True


class StoryItemDetail(BaseModel):
    """Detail model for story item with generation info."""

    id: str
    story_id: str
    generation_id: str
    version_id: Optional[str] = None
    start_time_ms: int
    track: int = 0
    trim_start_ms: int = 0
    trim_end_ms: int = 0
    created_at: datetime
    # Generation details
    profile_id: str
    profile_name: str
    text: str
    language: str
    audio_path: str
    duration: float
    seed: Optional[int]
    instruct: Optional[str]
    engine: Optional[str] = None
    volume: float = 1.0
    generation_created_at: datetime
    # Versions available for this generation
    versions: Optional[List["GenerationVersionResponse"]] = None
    active_version_id: Optional[str] = None

    class Config:
        from_attributes = True


class StoryDetailResponse(BaseModel):
    """Response model for story with items."""

    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[StoryItemDetail] = []

    class Config:
        from_attributes = True


class StoryItemCreate(BaseModel):
    """Request model for adding a generation to a story."""

    generation_id: str
    start_time_ms: Optional[int] = None  # If not provided, will be calculated automatically
    track: Optional[int] = 0  # Track number (0 = main track)


class StoryItemUpdateTime(BaseModel):
    """Request model for updating a story item's timecode."""

    generation_id: str
    start_time_ms: int = Field(..., ge=0)


class StoryItemBatchUpdate(BaseModel):
    """Request model for batch updating story item timecodes."""

    updates: List[StoryItemUpdateTime]


class StoryItemReorder(BaseModel):
    """Request model for reordering story items."""

    generation_ids: List[str] = Field(..., min_length=1)


class StoryItemMove(BaseModel):
    """Request model for moving a story item (position and/or track)."""

    start_time_ms: int = Field(..., ge=0)
    track: int = 0


class StoryItemTrim(BaseModel):
    """Request model for trimming a story item."""

    trim_start_ms: int = Field(..., ge=0)
    trim_end_ms: int = Field(..., ge=0)


class StoryItemSplit(BaseModel):
    """Request model for splitting a story item."""

    split_time_ms: int = Field(..., ge=0)  # Time within the clip to split at (relative to clip start)


class StoryItemVersionUpdate(BaseModel):
    """Request model for setting a story item's pinned version."""

    version_id: Optional[str] = None  # null = use generation default


class StoryItemVolumeUpdate(BaseModel):
    """Request model for adjusting a story item's playback volume.

    Linear gain. ``1.0`` is the original level, ``0.0`` is silent. Capped
    above 1.0 so a too-aggressive boost can't blow out the mix or clip
    the export.
    """

    volume: float = Field(..., ge=0.0, le=2.0)


class EffectConfig(BaseModel):
    """A single effect in an effects chain."""

    type: str
    enabled: bool = True
    params: dict = Field(default_factory=dict)


class EffectsChain(BaseModel):
    """An ordered list of effects to apply."""

    effects: List[EffectConfig] = Field(default_factory=list)


class EffectPresetCreate(BaseModel):
    """Request model for creating an effect preset."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    effects_chain: List[EffectConfig]


class EffectPresetUpdate(BaseModel):
    """Request model for updating an effect preset."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    effects_chain: Optional[List[EffectConfig]] = None


class EffectPresetResponse(BaseModel):
    """Response model for effect preset."""

    id: str
    name: str
    description: Optional[str] = None
    effects_chain: List[EffectConfig]
    is_builtin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class GenerationVersionResponse(BaseModel):
    """Response model for a generation version."""

    id: str
    generation_id: str
    label: str
    audio_path: str
    effects_chain: Optional[List[EffectConfig]] = None
    source_version_id: Optional[str] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApplyEffectsRequest(BaseModel):
    """Request to apply effects to an existing generation."""

    effects_chain: List[EffectConfig]
    source_version_id: Optional[str] = Field(
        None, description="Version to use as source audio (defaults to clean/original)"
    )
    label: Optional[str] = Field(None, max_length=100, description="Label for this version (auto-generated if omitted)")
    set_as_default: bool = Field(default=True, description="Set this version as the default")


class ProfileEffectsUpdate(BaseModel):
    """Request to update the default effects chain on a profile."""

    effects_chain: Optional[List[EffectConfig]] = Field(None, description="Effects chain (null to remove)")


class AvailableEffectParam(BaseModel):
    """Description of a single effect parameter."""

    default: float
    min: float
    max: float
    step: float
    description: str


class AvailableEffect(BaseModel):
    """Description of an available effect type."""

    type: str
    label: str
    description: str
    params: dict  # param_name -> AvailableEffectParam


class AvailableEffectsResponse(BaseModel):
    """Response listing all available effect types."""

    effects: List[AvailableEffect]


# Research Workspace contracts. Kept separate from AI Video contracts so the
# new route can evolve without changing existing request/response behavior.
class ResearchProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    brief: Optional[str] = Field(None, max_length=20000)
    tags: List[str] = Field(default_factory=list, max_length=20)


class ResearchProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    brief: Optional[str] = Field(None, max_length=20000)
    tags: Optional[List[str]] = Field(None, max_length=20)
    status: Optional[str] = Field(None, pattern="^(draft|researching|ready_for_review|approved|archived)$")


class ResearchProjectResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    brief: Optional[str] = None
    status: str
    revision: int
    memory_path: Optional[str] = None
    manifest_path: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchContextRequest(BaseModel):
    project_ids: List[str] = Field(default_factory=list, max_length=10)
    max_chars: int = Field(default=60000, ge=1000, le=200000)
    per_project_chars: int = Field(default=12000, ge=500, le=50000)


class ResearchContextResponse(BaseModel):
    project_ids: List[str]
    context: str
    omitted_project_ids: List[str] = Field(default_factory=list)
    total_chars: int
    truncated: bool = False


class ResearchSourceResponse(BaseModel):
    id: str
    project_id: str
    source_type: str
    title: Optional[str] = None
    input_url: Optional[str] = None
    file_path: Optional[str] = None
    status: str
    revision: int
    source_package_path: Optional[str] = None
    summary_path: Optional[str] = None
    result: dict = Field(default_factory=dict)
    limitations: List[Any] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    error_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchSourceTextCreate(BaseModel):
    source_type: str = Field(..., pattern="^(text|docs_url|video_url|story_url)$")
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=100000)
    input_url: Optional[str] = Field(None, max_length=4000)


class ResearchSeriesMemorySourceCreate(BaseModel):
    series_id: str = Field(..., min_length=1, max_length=160)
    episode_number: Optional[int] = Field(None, ge=1, le=10000)
    max_chars: int = Field(default=40000, ge=2000, le=60000)


class ResearchSourceApproveRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    observation_indexes: List[int] = Field(default_factory=list, max_length=100)


class ResearchSourceRetryRequest(BaseModel):
    resolve_dns: bool = True


class ResearchRunCreate(BaseModel):
    mode: str = Field(..., pattern="^(research|creative|both)$")
    brief: Optional[str] = Field(None, max_length=20000)
    source_ids: List[str] = Field(default_factory=list, max_length=50)
    related_project_ids: List[str] = Field(default_factory=list, max_length=10)
    run_ai: bool = True


class ResearchRunRetryRequest(BaseModel):
    run_ai: bool = True


class ResearchRunMergeRequest(BaseModel):
    materialize_options: bool = True


class ResearchRunResponse(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    output: dict = Field(default_factory=dict)
    provider_metadata: dict = Field(default_factory=dict)
    cost: dict = Field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchIdeaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    summary: Optional[str] = Field(None, max_length=10000)
    content: dict = Field(default_factory=dict)
    run_id: Optional[str] = None
    source_provider: Optional[str] = Field(None, max_length=80)


class ResearchIdeaResponse(BaseModel):
    id: str
    project_id: str
    run_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    status: str
    content: dict = Field(default_factory=dict)
    source_provider: Optional[str] = None
    dependency_fingerprint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchScriptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: Optional[str] = Field(None, max_length=50000)
    content_json: dict = Field(default_factory=dict)
    idea_id: Optional[str] = None
    target_format: str = Field(default="series_3_minute", max_length=100)


class ResearchScriptResponse(BaseModel):
    id: str
    project_id: str
    idea_id: Optional[str] = None
    title: str
    status: str
    content: Optional[str] = None
    content_json: dict = Field(default_factory=dict)
    target_format: Optional[str] = None
    dependency_fingerprint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchScoreRequest(BaseModel):
    target_type: str = Field(..., pattern="^(idea|script)$")
    target_id: str = Field(..., min_length=1)
    components: Optional[dict[str, float]] = None
    explanations: dict[str, str] = Field(default_factory=dict)
    evidence_refs: List[Any] = Field(default_factory=list)
    limitations: List[Any] = Field(default_factory=list)
    constraint_violations: List[str] = Field(default_factory=list)
    run_ai: bool = True
    originality: Optional[float] = Field(None, ge=0, le=10)
    feasibility: Optional[float] = Field(None, ge=0, le=10)


class ResearchScoreResponse(BaseModel):
    id: str
    project_id: str
    target_type: str
    target_id: str
    rubric_version: str
    components: dict = Field(default_factory=dict)
    total_score: float
    recommendation_status: str
    recommendation_reason: Optional[str] = None
    confidence: Optional[float] = None
    rank: Optional[int] = None
    tie_group: Optional[int] = None
    completeness_status: str = "incomplete"
    stale_reason: Optional[str] = None
    improvement_actions: List[Any] = Field(default_factory=list)
    tradeoffs: dict = Field(default_factory=dict)
    safety_gate: dict = Field(default_factory=dict)
    provider_metadata: dict = Field(default_factory=dict)
    cost: dict = Field(default_factory=dict)
    evidence_refs: List[Any] = Field(default_factory=list)
    limitations: List[Any] = Field(default_factory=list)
    dependency_fingerprint: Optional[str] = None
    user_override_status: Optional[str] = None
    user_override_reason: Optional[str] = None
    user_override_revision: int = 0
    user_override_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchScoreOverrideRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(recommended|alternative|blocked)$")
    reason: Optional[str] = Field(None, max_length=2000)


class ResearchRecommendationResponse(BaseModel):
    project_id: str
    rubric_version: str
    ranked_scores: List[ResearchScoreResponse] = Field(default_factory=list)
    recommended_target_ids: List[str] = Field(default_factory=list)
    selected_target_id: Optional[str] = None
    selected_score_id: Optional[str] = None
    decision_source: str = "none"
    tie_groups: List[dict] = Field(default_factory=list)
    has_incomplete: bool = False
    has_stale: bool = False
    summary_reason: Optional[str] = None


class ResearchStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=40)


class ResearchChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    mode: str = Field(default="creative", pattern="^(research|creative|both)$")
    selected_project_ids: List[str] = Field(default_factory=list, max_length=10)
    action: str = Field(
        default="develop",
        pattern="^(develop|variant|next_episode|increase_drama|fix_logic|develop_character|script_seed)$",
    )
    thread_id: Optional[str] = None
    branch_name: Optional[str] = Field(None, max_length=120)
    parent_message_id: Optional[str] = None
    run_ai: bool = True


class ResearchChatResponse(BaseModel):
    thread_id: str
    user_message_id: str
    assistant_message_id: str
    draft: str
    suggestions: List[dict] = Field(default_factory=list)
    status: str = "draft"
    branch_name: str = "canon"
    continuity: dict = Field(default_factory=dict)
    context_project_ids: List[str] = Field(default_factory=list)


class ResearchChatMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    message_type: str
    status: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ResearchChatThreadResponse(BaseModel):
    id: str
    project_id: str
    title: Optional[str] = None
    selected_project_ids: List[str] = Field(default_factory=list)
    branch_name: str
    status: str
    messages: List[ResearchChatMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ResearchChatApprovalRequest(BaseModel):
    promotion_type: str = Field(..., pattern="^(idea|script|memory_card)$")
    title: Optional[str] = Field(None, max_length=300)
    accept: bool = True


class ResearchChatPromotionResponse(BaseModel):
    message_id: str
    promotion_type: str
    status: str
    project_revision: int
    idea: Optional[ResearchIdeaResponse] = None
    script: Optional[ResearchScriptResponse] = None


class ResearchChatMessageStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|rejected)$")


class ResearchHandoffCreate(BaseModel):
    accepted_idea_ids: List[str] = Field(default_factory=list, max_length=20)
    accepted_script_ids: List[str] = Field(default_factory=list, max_length=20)
    selected_target_id: Optional[str] = Field(None, max_length=100)
    selection_source: Optional[str] = Field(None, pattern="^(user_override|ai|none)$")
    title: Optional[str] = Field(None, max_length=200)
    target_language: str = Field(default="vi", pattern="^(vi|en)$")
    target_duration_seconds: Optional[int] = Field(None, ge=1, le=3600)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1)$")
    idempotency_key: Optional[str] = Field(None, max_length=200)


class ResearchHandoffResponse(BaseModel):
    id: str
    project_id: str
    revision: int
    status: str
    target_ai_video_project_id: Optional[str] = None
    deep_link: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


PRODUCT_VIDEO_ASPECT_RATIO_PATTERN = "^(9:16|16:9)$"
PRODUCT_VIDEO_MIN_DURATION_SECONDS = 15
PRODUCT_VIDEO_MAX_DURATION_SECONDS = 180
PRODUCT_VIDEO_CREATION_MODE_PATTERN = "^(quick|manual)$"
PRODUCT_VIDEO_AUTOMATION_MODE_PATTERN = "^(review_gated|full_auto)$"
PRODUCT_VIDEO_OUTPUT_TARGET_PATTERN = "^(render_ready|prompt_pack|shots_only)$"


class ProductVideoProjectCreate(_VisualStyleLimitedModel):
    """Request model for creating a product video prompt project."""

    topic: str = Field(..., min_length=1, max_length=4000)
    title: Optional[str] = Field(default=None, max_length=160)
    target_language: str = Field(default="vi", pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    video_purpose: str = Field(default="sales_ad", pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    creation_mode: str = Field(default="quick", pattern=PRODUCT_VIDEO_CREATION_MODE_PATTERN)
    automation_mode: str = Field(default="full_auto", pattern=PRODUCT_VIDEO_AUTOMATION_MODE_PATTERN)
    output_target: str = Field(default="render_ready", pattern=PRODUCT_VIDEO_OUTPUT_TARGET_PATTERN)
    aspect_ratio: str = Field(default="9:16", pattern=PRODUCT_VIDEO_ASPECT_RATIO_PATTERN)
    target_duration_seconds: int = Field(
        default=30,
        ge=PRODUCT_VIDEO_MIN_DURATION_SECONDS,
        le=PRODUCT_VIDEO_MAX_DURATION_SECONDS,
    )
    visual_style: Optional[str] = Field(default=None, max_length=_VIDEO_VISUAL_STYLE_MAX_LENGTH)
    # No pattern on purpose: the preset list changes often and lives in the frontend.
    visual_style_preset: Optional[str] = Field(default=None, max_length=40)
    prompt_segment_count: Optional[int] = Field(default=None, ge=1, le=60)
    prompt_segment_duration_seconds: Optional[int] = Field(default=None, ge=3, le=30)
    micro_scenes_per_prompt: Optional[int] = Field(default=None, ge=1, le=5)


class ProductVideoProjectUpdate(_VisualStyleLimitedModel):
    """Partial update for a product video prompt project."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    topic: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    target_language: Optional[str] = Field(default=None, pattern=video_language.VIDEO_TARGET_LANGUAGE_PATTERN)
    video_purpose: Optional[str] = Field(default=None, pattern=video_purpose_service.VIDEO_PURPOSE_PATTERN)
    dialogue_mode: Optional[str] = Field(default=None, pattern=video_purpose_service.DIALOGUE_MODE_PATTERN)
    narration_density: Optional[str] = Field(default=None, pattern=video_purpose_service.NARRATION_DENSITY_PATTERN)
    call_to_action_style: Optional[str] = Field(default=None, pattern=video_purpose_service.CTA_STYLE_PATTERN)
    creation_mode: Optional[str] = Field(default=None, pattern=PRODUCT_VIDEO_CREATION_MODE_PATTERN)
    automation_mode: Optional[str] = Field(default=None, pattern=PRODUCT_VIDEO_AUTOMATION_MODE_PATTERN)
    output_target: Optional[str] = Field(default=None, pattern=PRODUCT_VIDEO_OUTPUT_TARGET_PATTERN)
    aspect_ratio: Optional[str] = Field(default=None, pattern=PRODUCT_VIDEO_ASPECT_RATIO_PATTERN)
    target_duration_seconds: Optional[int] = Field(
        default=None,
        ge=PRODUCT_VIDEO_MIN_DURATION_SECONDS,
        le=PRODUCT_VIDEO_MAX_DURATION_SECONDS,
    )
    visual_style: Optional[str] = Field(default=None, max_length=_VIDEO_VISUAL_STYLE_MAX_LENGTH)
    visual_style_preset: Optional[str] = Field(default=None, max_length=40)
    prompt_segment_count: Optional[int] = Field(default=None, ge=1, le=60)
    prompt_segment_duration_seconds: Optional[int] = Field(default=None, ge=3, le=30)
    micro_scenes_per_prompt: Optional[int] = Field(default=None, ge=1, le=5)


class ProductVideoProjectResponse(BaseModel):
    """List/detail summary for a product video prompt project."""

    id: str
    title: str
    topic: str
    target_language: str
    aspect_ratio: str
    visual_style: Optional[str] = None
    visual_style_preset: Optional[str] = None
    video_purpose: str
    dialogue_mode: str
    narration_density: str
    call_to_action_style: Optional[str] = None
    creation_mode: str
    automation_mode: str
    output_target: str
    target_duration_seconds: int
    prompt_segment_count: Optional[int] = None
    prompt_segment_duration_seconds: Optional[int] = None
    micro_scenes_per_prompt: Optional[int] = None
    status: str
    planning_status: str
    planning_error: Optional[str] = None
    hook_text: Optional[str] = None
    # Derived because Veo snaps clip length to 4/6/8/10s, so the real duration
    # is a multiple of the clip length and rarely equals the requested value.
    derived_clip_count: int = 0
    derived_clip_duration_seconds: int = 0
    derived_duration_seconds: int = 0
    shot_count: int = 0
    prompt_count: int = 0
    render_project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductVideoShotResponse(BaseModel):
    """One planned Flow clip of a product video project."""

    id: str
    project_id: str
    shot_order: int
    shot_type: Optional[str] = None
    framing: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_motion: Optional[str] = None
    subject_motion: Optional[str] = None
    environment_motion: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    duration_seconds: Optional[int] = None
    beat_role: Optional[str] = None
    narration_text: Optional[str] = None
    retention_notes: Optional[str] = None
    transition_notes: Optional[str] = None
    sound_design_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductVideoPromptResponse(BaseModel):
    """Rendered Flow prompt for one product video shot."""

    id: str
    project_id: str
    shot_id: str
    shot_order: int = 1
    prompt: str
    negative_prompt: Optional[str] = None
    prompt_explanation_vi: Optional[str] = None
    aspect_ratio: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProductVideoPromptPackResponse(BaseModel):
    """Full prompt pack ready to paste into Google Flow."""

    project_id: str
    aspect_ratio: str
    target_language: str
    derived_clip_count: int = 0
    derived_clip_duration_seconds: int = 0
    derived_duration_seconds: int = 0
    hook_text: Optional[str] = None
    prompts: List[ProductVideoPromptResponse] = Field(default_factory=list)


class ProductVideoProjectDetailResponse(ProductVideoProjectResponse):
    """Project detail with its planned shots and generated prompts."""

    shots: List[ProductVideoShotResponse] = Field(default_factory=list)
    prompts: List[ProductVideoPromptResponse] = Field(default_factory=list)
    render_shots: List[VideoShotResponse] = Field(default_factory=list)
