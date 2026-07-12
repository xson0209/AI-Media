"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional, List
from datetime import datetime

from .utils.capture_chords import (
    default_push_to_talk_chord,
    default_toggle_to_talk_chord,
)
from .services import video_purpose as video_purpose_service

_VIDEO_VISUAL_STYLE_MAX_LENGTH = 2000


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
    timeout_seconds: int = Field(default=60, ge=5, le=600)
    output_schema_path: Optional[str] = None

    class Config:
        from_attributes = True

class AIPlanningSettingsUpdate(BaseModel):
    """Partial update for AI planning provider settings."""

    provider: Optional[str] = Field(default=None, min_length=1, max_length=50)
    codex_path: Optional[str] = Field(default=None, max_length=1000)
    model: Optional[str] = Field(default=None, max_length=100)
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

class VideoShotUpdate(BaseModel):
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
    retention_json: Optional[dict[str, Any]] = None
    transition_json: Optional[dict[str, Any]] = None
    sound_design_json: Optional[dict[str, Any]] = None
    micro_scenes: Optional[List[VideoShotMicroScene]] = Field(default=None, max_length=20)
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
    fps: int = Field(default=30, ge=12, le=60)
    fit_mode: str = Field(default="crop", pattern="^(crop|pad)$")
    duration_mode: str = Field(default="freeze", pattern="^(freeze|trim_only)$")
    subtitle_mode: str = Field(default="burn_in", pattern="^(burn_in|sidecar|none)$")
    mute_clip_audio: bool = True
    background_color: str = Field(default="#111827", max_length=20)
    force: bool = False
    enhanced_render: bool = False
    enhanced_audio: bool = True
    ai_review: bool = True
    max_fix_attempts: int = Field(default=1, ge=0, le=2)

class VideoRenderWarning(BaseModel):
    shot_id: Optional[str] = None
    code: str
    message: str

class VideoRenderReadinessResponse(BaseModel):
    """Checklist before creating an MP4 render job."""

    project_id: str
    ready: bool
    ffmpeg_ready: bool = False
    ffprobe_ready: bool = False
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
    needs_credit_approval_items: int = 0
    credit_spent_estimate: int = 0
    render_ready: bool = False
    render_missing_reasons: List[str] = Field(default_factory=list)

class VideoClipGenerationJobStartRequest(BaseModel):
    session_id: Optional[str] = None
    force: bool = False
    auto_render: bool = False
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
    credit_approval_policy: str = "approve_dont_ask_again"
    max_credit_per_job: Optional[int] = None
    credit_spent_estimate: int = 0
    render_job_id: Optional[str] = None
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    step_results_json: Optional[dict[str, Any]] = None
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

class VideoSeriesCreate(BaseModel):
    """Request model for creating an optional AI Video series."""

    title: str = Field(..., min_length=1, max_length=160)
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
    character_bible: Optional[str] = None
    world_bible: Optional[str] = None
    style_bible: Optional[str] = None
    continuity_rules: Optional[str] = None
    negative_rules: Optional[str] = None
    previous_episode_summary: Optional[str] = None
    latest_episode_number: int = 0
    episode_count: int = 0
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
    language: str = Field(default="vi", max_length=20)
    target_language: Optional[str] = Field(default=None, pattern="^(en|vi)$")
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
    title: Optional[str] = Field(default=None, max_length=160)
    series_id: Optional[str] = None
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    episode_title: Optional[str] = Field(default=None, max_length=160)
    language: str = Field(default="vi", max_length=20)
    target_language: str = Field(default="en", pattern="^(en|vi)$")
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
    episode_number: Optional[int] = Field(default=None, ge=1, le=10000)
    episode_title: Optional[str] = Field(default=None, max_length=160)
    language: Optional[str] = Field(default=None, max_length=20)
    target_language: Optional[str] = Field(default=None, pattern="^(en|vi)$")
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
    episode_number: Optional[int] = None
    episode_title: Optional[str] = None
    series_title: Optional[str] = None
    title: str
    topic: str
    language: str
    target_language: str = "en"
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
    package_stale: bool
    scene_count: int = 0
    shot_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoProjectLocalizeRequest(BaseModel):
    """Create a separate localized copy of an AI Video project."""

    target_language: str = Field(..., pattern="^(en|vi)$")
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
    created_at: datetime
    updated_at: datetime


class VideoPackageReadinessResponse(BaseModel):
    """Checklist used before creating a Premiere materials package."""

    project_id: str
    language: str = "en"
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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoAutoRunStartRequest(BaseModel):
    """Start an AI Video material auto-run."""

    mode: str = Field(default="review_gated", pattern="^(review_gated|full_auto)$")
    material_target: str = Field(default="full_materials", pattern="^(full_materials|prompts_only|video_clips)$")
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
    frame_path: str
    timestamp_seconds: float
    description_vi: Optional[str] = None
    technical_metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime

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
    frames: List[VideoInspirationFrameResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoInspirationListResponse(BaseModel):
    items: List[VideoInspirationJobResponse]
    total: int

class VideoInspirationUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=4000)
    target_language: str = Field(default="vi", pattern="^(vi|en)$")
    user_direction: Optional[str] = Field(default=None, max_length=20000)
    use_browser_cookies: bool = False

class VideoInspirationAnalyzeRequest(BaseModel):
    allow_audio_only: bool = False
    stt_model: Optional[str] = Field(default=None, pattern="^(base|small|medium|large|turbo)$")

class VideoInspirationTranscriptUpdate(BaseModel):
    transcript_text: str = Field(..., max_length=120000)

class VideoInspirationDirectionUpdate(BaseModel):
    user_direction: Optional[str] = Field(default=None, max_length=20000)

class VideoInspirationRewriteRequest(BaseModel):
    target_language: Optional[str] = Field(default=None, pattern="^(vi|en)$")
    user_direction: Optional[str] = Field(default=None, max_length=20000)

class VideoInspirationScriptUpdate(BaseModel):
    rewritten_script: str = Field(..., min_length=1, max_length=160000)
    script_title: Optional[str] = Field(default=None, max_length=160)
    big_idea: Optional[str] = Field(default=None, max_length=20000)
    hook: Optional[str] = Field(default=None, max_length=12000)

class VideoInspirationCreateProjectRequest(BaseModel):
    start_full_materials: bool = False
    mode: str = Field(default="full_auto", pattern="^(review_gated|full_auto)$")
    voice_profile_id: Optional[str] = None

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
    queued: int = 0
    running: int = 0
    queued_ids: List[str] = Field(default_factory=list)
    running_ids: List[str] = Field(default_factory=list)

class ResourceActiveJobsStatus(BaseModel):
    """Active job counts relevant to resource cleanup."""

    generations: List[dict[str, Any]] = Field(default_factory=list)
    generation_count: int = 0
    render_count: int = 0
    auto_run_count: int = 0

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
