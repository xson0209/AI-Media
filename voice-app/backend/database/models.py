"""ORM model definitions for the voicebox SQLite database."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

from ..utils.capture_chords import (
    default_push_to_talk_chord,
    default_toggle_to_talk_chord,
)

Base = declarative_base()


class VoiceProfile(Base):
    """Voice profile.

    voice_type discriminates three flavours:
      - "cloned"   — traditional reference-audio profiles (all cloning engines)
      - "preset"   — engine-specific pre-built voice (e.g. Kokoro voices)
      - "designed"  — text-described voice (e.g. Qwen CustomVoice, future)
    """

    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    language = Column(String, default="en")
    avatar_path = Column(String, nullable=True)
    effects_chain = Column(Text, nullable=True)

    # Voice type system — added v0.3.x
    voice_type = Column(String, default="cloned")  # "cloned" | "preset" | "designed"
    preset_engine = Column(String, nullable=True)   # e.g. "kokoro" — only for preset
    preset_voice_id = Column(String, nullable=True)  # e.g. "am_adam" — only for preset
    design_prompt = Column(Text, nullable=True)      # text description — only for designed
    default_engine = Column(String, nullable=True)   # auto-selected engine, locked for preset
    # Free-form character prompt used by the compose button and the
    # personality-rewrite path on /generate. Describes *what* this voice
    # says and how, orthogonal to how it sounds (handled by the preset /
    # cloning metadata above).
    personality = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProfileSample(Base):
    """Audio sample attached to a voice profile."""

    __tablename__ = "profile_samples"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    audio_path = Column(String, nullable=False)
    reference_text = Column(Text, nullable=False)


class Generation(Base):
    """A single TTS generation."""

    __tablename__ = "generations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    text = Column(Text, nullable=False)
    language = Column(String, default="en")
    audio_path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    seed = Column(Integer)
    instruct = Column(Text)
    engine = Column(String, default="qwen")
    model_size = Column(String, nullable=True)
    status = Column(String, default="completed")
    error = Column(Text, nullable=True)
    is_favorited = Column(Boolean, default=False)
    # Origin of this generation — "manual" for plain /generate calls,
    # "personality_speak" for rows whose text was rewritten through the
    # profile's personality LLM before TTS. Future sources (bulk import,
    # agent replies, etc.) can extend this.
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)


class Story(Base):
    """A story that sequences multiple generations."""

    __tablename__ = "stories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StoryItem(Base):
    """Links a generation to a story at a specific timecode."""

    __tablename__ = "story_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    generation_id = Column(String, ForeignKey("generations.id"), nullable=False)
    version_id = Column(String, ForeignKey("generation_versions.id"), nullable=True)
    start_time_ms = Column(Integer, nullable=False, default=0)
    track = Column(Integer, nullable=False, default=0)
    trim_start_ms = Column(Integer, nullable=False, default=0)
    trim_end_ms = Column(Integer, nullable=False, default=0)
    volume = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    """Audio studio project (JSON blob)."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GenerationVersion(Base):
    """A version of a generation's audio (original, processed, alternate takes)."""

    __tablename__ = "generation_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    generation_id = Column(String, ForeignKey("generations.id"), nullable=False)
    label = Column(String, nullable=False)
    audio_path = Column(String, nullable=False)
    effects_chain = Column(Text, nullable=True)
    source_version_id = Column(String, ForeignKey("generation_versions.id"), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EffectPreset(Base):
    """Saved effect chain preset."""

    __tablename__ = "effect_presets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    effects_chain = Column(Text, nullable=False)
    is_builtin = Column(Boolean, default=False)
    sort_order = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)


class AudioChannel(Base):
    """Audio output channel (bus)."""

    __tablename__ = "audio_channels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChannelDeviceMapping(Base):
    """Mapping between a channel and an OS audio device."""

    __tablename__ = "channel_device_mappings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id = Column(String, ForeignKey("audio_channels.id"), nullable=False)
    device_id = Column(String, nullable=False)


class ProfileChannelMapping(Base):
    """Many-to-many mapping between voice profiles and audio channels."""

    __tablename__ = "profile_channel_mappings"

    profile_id = Column(String, ForeignKey("profiles.id"), primary_key=True)
    channel_id = Column(String, ForeignKey("audio_channels.id"), primary_key=True)


class CaptureSettings(Base):
    """Singleton row holding user defaults for the capture/refine flow.

    Kept server-side so every window, CLI client, and API consumer reads the
    same preferences. The ``id`` column is always 1.
    """

    __tablename__ = "capture_settings"

    id = Column(Integer, primary_key=True, default=1)
    stt_model = Column(String, nullable=False, default="turbo")
    language = Column(String, nullable=False, default="auto")
    auto_refine = Column(Boolean, nullable=False, default=True)
    llm_model = Column(String, nullable=False, default="0.6B")
    smart_cleanup = Column(Boolean, nullable=False, default=True)
    self_correction = Column(Boolean, nullable=False, default=True)
    preserve_technical = Column(Boolean, nullable=False, default=True)
    allow_auto_paste = Column(Boolean, nullable=False, default=True)
    default_playback_voice_id = Column(String, nullable=True)
    # Default OFF — opting in is what triggers the macOS Input Monitoring TCC
    # prompt. We deliberately don't spawn the global keyboard tap until the
    # user flips this on so a fresh-install user doesn't see a scary
    # "Voicebox would like to receive keystrokes from any application" dialog
    # before they've even opened the Captures tab.
    hotkey_enabled = Column(Boolean, nullable=False, default=False)
    # Lists of keytap key names (e.g. "MetaRight", "ControlRight"). Right-hand
    # modifiers by default so they don't collide with left-hand shortcuts.
    chord_push_to_talk_keys = Column(
        JSON, nullable=False, default=default_push_to_talk_chord
    )
    chord_toggle_to_talk_keys = Column(
        JSON, nullable=False, default=default_toggle_to_talk_chord
    )
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GenerationSettings(Base):
    """Singleton row for long-form TTS generation preferences."""

    __tablename__ = "generation_settings"

    id = Column(Integer, primary_key=True, default=1)
    max_chunk_chars = Column(Integer, nullable=False, default=800)
    crossfade_ms = Column(Integer, nullable=False, default=50)
    normalize_audio = Column(Boolean, nullable=False, default=True)
    autoplay_on_generate = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIPlanningSettings(Base):
    """Singleton row for AI Video Assistant planning provider settings."""

    __tablename__ = "ai_planning_settings"

    id = Column(Integer, primary_key=True, default=1)
    provider = Column(String, nullable=False, default="codex-cli")
    codex_path = Column(String, nullable=True)
    model = Column(String, nullable=True)
    timeout_seconds = Column(Integer, nullable=False, default=60)
    output_schema_path = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoSeries(Base):
    """Optional parent context for AI Video episode projects."""

    __tablename__ = "video_series"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    character_bible = Column(Text, nullable=True)
    world_bible = Column(Text, nullable=True)
    style_bible = Column(Text, nullable=True)
    continuity_rules = Column(Text, nullable=True)
    negative_rules = Column(Text, nullable=True)
    previous_episode_summary = Column(Text, nullable=True)
    latest_episode_number = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoProject(Base):
    """AI Video Assistant project state."""

    __tablename__ = "video_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    episode_number = Column(Integer, nullable=True)
    episode_title = Column(String, nullable=True)
    title = Column(String, nullable=False)
    topic = Column(Text, nullable=False)
    language = Column(String, nullable=False, default="vi")
    target_duration_seconds = Column(Integer, nullable=True)
    aspect_ratio = Column(String, nullable=False, default="9:16")
    visual_style = Column(Text, nullable=True)
    voice_profile_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    status = Column(String, nullable=False, default="draft")
    creative_brief = Column(Text, nullable=True)
    script_text = Column(Text, nullable=True)
    style_bible = Column(Text, nullable=True)
    character_bible = Column(Text, nullable=True)
    script_approved = Column(Boolean, nullable=False, default=False)
    phase = Column(String, nullable=False, default="phase1")
    target_language = Column(String, nullable=False, default="en")
    video_purpose = Column(String, nullable=False, default="custom")
    dialogue_mode = Column(String, nullable=False, default="voiceover")
    narration_density = Column(String, nullable=False, default="balanced")
    call_to_action_style = Column(String, nullable=True)
    default_shot_duration_seconds = Column(Integer, nullable=True)
    prompt_segment_count = Column(Integer, nullable=True)
    prompt_segment_duration_seconds = Column(Integer, nullable=True)
    micro_scenes_per_prompt = Column(Integer, nullable=True)
    input_synthesis = Column(Text, nullable=True)
    story_strategy = Column(Text, nullable=True)
    continuity_bible = Column(Text, nullable=True)
    detailed_script = Column(Text, nullable=True)
    retention_plan_json = Column(JSON, nullable=True)
    sound_design_plan_json = Column(JSON, nullable=True)
    story_approved = Column(Boolean, nullable=False, default=False)
    planning_status = Column(String, nullable=False, default="draft")
    planning_error = Column(Text, nullable=True)
    last_request_id = Column(String, nullable=True)
    package_stale = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoAutoRun(Base):
    """Persisted orchestration run for AI Video material generation."""

    __tablename__ = "video_auto_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    mode = Column(String, nullable=False, default="review_gated")
    status = Column(String, nullable=False, default="queued")
    current_step = Column(String, nullable=False, default="validate")
    review_stage = Column(String, nullable=True)
    progress = Column(Float, nullable=False, default=0.0)
    create_package = Column(Boolean, nullable=False, default=False)
    force = Column(Boolean, nullable=False, default=False)
    step_results_json = Column(JSON, nullable=True)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoProviderSession(Base):
    """Local browser-provider connection metadata for AI Video clip generation."""

    __tablename__ = "video_provider_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String, nullable=False, default="veo")
    provider_tool = Column(String, nullable=True, default="veo3_flow")
    status = Column(String, nullable=False, default="not_configured")
    is_default = Column(Boolean, nullable=False, default=True)
    chrome_profile_path = Column(String, nullable=False)
    connection_label = Column(String, nullable=True)
    verified_account_hint = Column(String, nullable=True)
    account_identifier_hash = Column(String, nullable=True)
    identity_status = Column(String, nullable=False, default="unknown")
    identity_verified_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoClipGenerationJob(Base):
    """Provider clip generation job for an AI Video project."""

    __tablename__ = "video_clip_generation_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    provider = Column(String, nullable=False, default="veo")
    session_id = Column(String, ForeignKey("video_provider_sessions.id"), nullable=False)
    status = Column(String, nullable=False, default="queued")
    current_step = Column(String, nullable=False, default="validate")
    progress = Column(Float, nullable=False, default=0.0)
    force = Column(Boolean, nullable=False, default=False)
    auto_render = Column(Boolean, nullable=False, default=False)
    credit_approval_policy = Column(String, nullable=False, default="approve_dont_ask_again")
    max_credit_per_job = Column(Integer, nullable=True)
    credit_spent_estimate = Column(Integer, nullable=False, default=0)
    render_job_id = Column(String, ForeignKey("video_render_jobs.id"), nullable=True)
    download_dir = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    step_results_json = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoClipGenerationItem(Base):
    """One provider-generation item mapped to a concrete project shot."""

    __tablename__ = "video_clip_generation_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_clip_generation_jobs.id"), nullable=False)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    shot_id = Column(String, ForeignKey("video_shots.id"), nullable=False)
    shot_order = Column(Integer, nullable=False, default=0)
    prompt_id = Column(String, ForeignKey("video_shot_prompts.id"), nullable=True)
    status = Column(String, nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    credit_cost = Column(Integer, nullable=True)
    provider_duration_seconds = Column(Float, nullable=True)
    provider_asset_id = Column(String, nullable=True)
    provider_project_ref_hash = Column(String, nullable=True)
    download_correlation_id = Column(String, nullable=True)
    download_url_hash = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    downloaded_file_path = Column(String, nullable=True)
    clip_id = Column(String, ForeignKey("video_shot_clips.id"), nullable=True)
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoSourceBlock(Base):
    """Structured input block for AI Video phase 2 planning."""

    __tablename__ = "video_source_blocks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    block_type = Column(String, nullable=False, default="idea")
    sort_order = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoScene(Base):
    """A scene in an AI Video Assistant project."""

    __tablename__ = "video_scenes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    scene_order = Column(Integer, nullable=False, default=0)
    title = Column(String, nullable=True)
    dialogue = Column(Text, nullable=False, default="")
    visual_description = Column(Text, nullable=True)
    target_duration_seconds = Column(Integer, nullable=True)
    approved = Column(Boolean, nullable=False, default=False)
    no_narration = Column(Boolean, nullable=False, default=False)
    prompt_status = Column(String, nullable=False, default="missing")
    voice_status = Column(String, nullable=False, default="missing")
    subtitle_status = Column(String, nullable=False, default="stale")
    generation_id = Column(String, ForeignKey("generations.id"), nullable=True)
    audio_path = Column(String, nullable=True)
    audio_duration = Column(Float, nullable=True)
    voice_failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoScenePrompt(Base):
    """Prompt artifact for a scene."""

    __tablename__ = "video_scene_prompts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    scene_id = Column(String, ForeignKey("video_scenes.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    main_prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    aspect_ratio = Column(String, nullable=True)
    style_notes = Column(Text, nullable=True)
    character_notes = Column(Text, nullable=True)
    prompt_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoShot(Base):
    """Short renderable shot in AI Video phase 2."""

    __tablename__ = "video_shots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    scene_id = Column(String, ForeignKey("video_scenes.id"), nullable=True)
    shot_order = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=True)
    vietnamese_description = Column(Text, nullable=True)
    english_narration = Column(Text, nullable=True)
    primary_action = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    shot_type = Column(String, nullable=True)
    camera_angle = Column(String, nullable=True)
    framing = Column(String, nullable=True)
    composition = Column(Text, nullable=True)
    camera_motion = Column(String, nullable=True)
    subject_motion = Column(Text, nullable=True)
    environment_motion = Column(Text, nullable=True)
    transition_to_next = Column(Text, nullable=True)
    retention_json = Column(JSON, nullable=True)
    transition_json = Column(JSON, nullable=True)
    sound_design_json = Column(JSON, nullable=True)
    micro_scenes_json = Column(JSON, nullable=True)
    retainability_quality_check = Column(JSON, nullable=True)
    locked = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="draft")
    prompt_status = Column(String, nullable=False, default="missing")
    voice_status = Column(String, nullable=False, default="missing")
    subtitle_status = Column(String, nullable=False, default="stale")
    generation_id = Column(String, ForeignKey("generations.id"), nullable=True)
    audio_path = Column(String, nullable=True)
    audio_duration = Column(Float, nullable=True)
    voice_failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def micro_scenes(self):
        return self.micro_scenes_json or []

    @micro_scenes.setter
    def micro_scenes(self, value):
        self.micro_scenes_json = value

class VideoShotPrompt(Base):
    """Structured video prompt artifact for a phase 2 shot."""

    __tablename__ = "video_shot_prompts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    scene_id = Column(String, ForeignKey("video_scenes.id"), nullable=True)
    shot_id = Column(String, ForeignKey("video_shots.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    prompt = Column(Text, nullable=False)
    prompt_explanation_vi = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    aspect_ratio = Column(String, nullable=True)
    camera_motion = Column(String, nullable=True)
    subject_motion = Column(Text, nullable=True)
    environment_motion = Column(Text, nullable=True)
    start_frame = Column(Text, nullable=True)
    end_frame = Column(Text, nullable=True)
    lighting = Column(Text, nullable=True)
    mood = Column(Text, nullable=True)
    style_notes = Column(Text, nullable=True)
    continuity_notes = Column(Text, nullable=True)
    retention_notes = Column(Text, nullable=True)
    transition_notes = Column(Text, nullable=True)
    sound_design_notes = Column(Text, nullable=True)
    quality_status = Column(String, nullable=False, default="unchecked")
    quality_check = Column(JSON, nullable=True)
    prompt_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoShotClip(Base):
    """Uploaded or provider-returned video clip attached to one AI Video shot."""

    __tablename__ = "video_shot_clips"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    shot_id = Column(String, ForeignKey("video_shots.id"), nullable=False)
    source = Column(String, nullable=False, default="upload")
    status = Column(String, nullable=False, default="pending")
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(String, nullable=True)
    has_audio = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    failure_reason = Column(Text, nullable=True)
    provider = Column(String, nullable=True)
    provider_asset_id = Column(String, nullable=True)
    provider_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoRenderJob(Base):
    """Background MP4 render job for an AI Video project."""

    __tablename__ = "video_render_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    status = Column(String, nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    current_step = Column(String, nullable=True)
    settings_json = Column(Text, nullable=True)
    readiness_json = Column(Text, nullable=True)
    timeline_manifest_path = Column(String, nullable=True)
    output_path = Column(String, nullable=True)
    subtitle_ass_path = Column(String, nullable=True)
    stale = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    technical_details = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoDebugEvent(Base):
    """Redacted local debug event for AI Video phase 2."""

    __tablename__ = "video_debug_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, nullable=False)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    scene_id = Column(String, ForeignKey("video_scenes.id"), nullable=True)
    shot_id = Column(String, ForeignKey("video_shots.id"), nullable=True)
    step_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="info")
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    duration_ms = Column(Float, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String, nullable=True)
    exception_class = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    technical_details = Column(Text, nullable=True)
    validation_errors = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoSceneAsset(Base):
    """Optional preview asset attached to a scene."""

    __tablename__ = "video_scene_assets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    scene_id = Column(String, ForeignKey("video_scenes.id"), nullable=False)
    asset_type = Column(String, nullable=False, default="preview_image")
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoSubtitle(Base):
    """Subtitle artifact generated for a video project."""

    __tablename__ = "video_subtitles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    status = Column(String, nullable=False, default="missing")
    subtitle_path = Column(String, nullable=True)
    format = Column(String, nullable=False, default="srt")
    cues_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoPackageExport(Base):
    """ZIP package export for Premiere-ready materials."""

    __tablename__ = "video_package_exports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    manifest_path = Column(String, nullable=True)
    zip_path = Column(String, nullable=True)
    stale = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MCPClientBinding(Base):
    """Per-MCP-client settings (voice profile, engine, personality default).

    Lets users bind distinct voices to distinct agents — e.g. Claude Code
    speaks in "Morgan," Cursor in "Scarlett." The MCP client identifies
    itself via the ``X-Voicebox-Client-Id`` HTTP header; direct-HTTP
    clients set it in their MCP config's ``headers`` block, the stdio
    shim forwards it from the ``VOICEBOX_CLIENT_ID`` env var.
    """

    __tablename__ = "mcp_client_bindings"

    client_id = Column(String, primary_key=True)
    label = Column(String, nullable=True)  # display name
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    default_engine = Column(String, nullable=True)
    # When true, voicebox.speak routes through the profile's personality LLM
    # (rewrite) before TTS by default. Callers can still override per call.
    default_personality = Column(Boolean, nullable=False, default=False)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Capture(Base):
    """A single voice input capture (dictation, recording, or uploaded file).

    Stores the original audio alongside the raw transcript and, optionally, a
    refined version produced by the LLM. Refinement flags are serialized as
    JSON so we can reproduce the prompt that generated the refined text.
    """

    __tablename__ = "captures"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    audio_path = Column(String, nullable=False)
    source = Column(String, nullable=False, default="file")  # dictation | recording | file
    language = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    transcript_raw = Column(Text, nullable=False, default="")
    transcript_refined = Column(Text, nullable=True)
    stt_model = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    refinement_flags = Column(Text, nullable=True)  # JSON blob
    created_at = Column(DateTime, default=datetime.utcnow)
