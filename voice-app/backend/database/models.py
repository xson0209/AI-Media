"""ORM model definitions for the voicebox SQLite database."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text
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
    model_reasoning_effort = Column(String, nullable=True)
    # Shared provider/model for every content-research and content-development flow.
    # Kept separate from the legacy AI-planning provider fields so existing
    # Codex planning settings remain backwards compatible.
    content_provider = Column(String, nullable=False, default="codex")
    content_model = Column(String, nullable=True)
    timeout_seconds = Column(Integer, nullable=False, default=600)
    output_schema_path = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoSeries(Base):
    """Optional parent context for AI Video episode projects."""

    __tablename__ = "video_series"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    series_mode = Column(String, nullable=False, default="video_story_only")
    character_bible = Column(Text, nullable=True)
    world_bible = Column(Text, nullable=True)
    style_bible = Column(Text, nullable=True)
    continuity_rules = Column(Text, nullable=True)
    negative_rules = Column(Text, nullable=True)
    previous_episode_summary = Column(Text, nullable=True)
    latest_episode_number = Column(Integer, nullable=False, default=0)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeriesCharacterProfile(Base):
    """Structured character profile shared by Story Studio and AI Video."""

    __tablename__ = "series_character_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    face_description = Column(Text, nullable=True)
    hair_description = Column(Text, nullable=True)
    body_description = Column(Text, nullable=True)
    signature_outfit = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    speech_style = Column(Text, nullable=True)
    fixed_traits = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeriesMemoryCard(Base):
    """Small approved or draft memory unit for selecting relevant series context."""

    __tablename__ = "series_memory_cards"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    card_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content_json = Column(JSON, nullable=False, default=dict)
    tags_json = Column(JSON, nullable=True)
    entity_refs_json = Column(JSON, nullable=True)
    importance = Column(Float, nullable=False, default=0.5)
    status = Column(String, nullable=False, default="draft")
    effective_from_episode = Column(Integer, nullable=True)
    effective_to_episode = Column(Integer, nullable=True)
    source_type = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeriesCurrentState(Base):
    """Versioned snapshot of the approved current state of a series."""

    __tablename__ = "series_current_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    based_on_episode_number = Column(Integer, nullable=False, default=0)
    character_states_json = Column(JSON, nullable=True)
    relationship_states_json = Column(JSON, nullable=True)
    location_states_json = Column(JSON, nullable=True)
    prop_states_json = Column(JSON, nullable=True)
    open_threads_json = Column(JSON, nullable=True)
    unresolved_conflicts_json = Column(JSON, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    approval_status = Column(String, nullable=False, default="draft")
    source_type = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    previous_state_id = Column(String, ForeignKey("series_current_states.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeriesContextTrace(Base):
    """Safe audit trace for one compiled context package."""

    __tablename__ = "series_context_traces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=True)
    task_type = Column(String, nullable=False)
    target_ref_type = Column(String, nullable=True)
    target_ref_id = Column(String, nullable=True)
    selected_cards_json = Column(JSON, nullable=True)
    selected_character_profiles_json = Column(JSON, nullable=True)
    group_budget_json = Column(JSON, nullable=True)
    missing_required_json = Column(JSON, nullable=True)
    truncated_groups_json = Column(JSON, nullable=True)
    context_stats_json = Column(JSON, nullable=True)
    reasons_json = Column(JSON, nullable=True)
    context_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SeriesCanonCheck(Base):
    """Canon check result for image or video prompts, including overrides."""

    __tablename__ = "series_canon_checks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=True)
    prompt_kind = Column(String, nullable=False)
    prompt_ref_id = Column(String, nullable=True)
    passed = Column(Boolean, nullable=False, default=True)
    blocking_conflicts_json = Column(JSON, nullable=True)
    warnings_json = Column(JSON, nullable=True)
    evidence_card_ids_json = Column(JSON, nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_by = Column(String, nullable=True)
    overridden_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SeriesReferenceAsset(Base):
    """Approved or draft visual reference asset for a series entity."""

    __tablename__ = "series_reference_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    reference_role = Column(String, nullable=False)
    label = Column(String, nullable=True)
    asset_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    provider_asset_id = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    checksum = Column(String, nullable=False)
    source_type = Column(String, nullable=True)
    approval_status = Column(String, nullable=False, default="pending_approval")
    revision = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SeriesVersionRecord(Base):
    """Immutable version snapshot for series canon and user-approved data."""

    __tablename__ = "series_version_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    changed_by = Column(String, nullable=True)
    change_source = Column(String, nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ArtifactDependencySnapshot(Base):
    """Dependency edge from an artifact to the exact source revision it used."""

    __tablename__ = "artifact_dependency_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    artifact_type = Column(String, nullable=False)
    artifact_id = Column(String, nullable=False)
    artifact_revision = Column(Integer, nullable=False, default=1)
    dependency_type = Column(String, nullable=False)
    dependency_id = Column(String, nullable=False)
    dependency_revision = Column(Integer, nullable=False, default=1)
    dependency_scope = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ArtifactStaleEvent(Base):
    """Targeted stale marker created from dependency revision changes."""

    __tablename__ = "artifact_stale_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    artifact_type = Column(String, nullable=False)
    artifact_id = Column(String, nullable=False)
    artifact_revision = Column(Integer, nullable=False, default=1)
    dependency_type = Column(String, nullable=False)
    dependency_id = Column(String, nullable=False)
    old_revision = Column(Integer, nullable=True)
    new_revision = Column(Integer, nullable=True)
    changed_scope = Column(String, nullable=False)
    dependency_scope = Column(String, nullable=False)
    reason_vi = Column(Text, nullable=False)
    propagation_rule = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class StoryEpisode(Base):
    """Master story episode prepared in Story Studio before rendering outputs."""

    __tablename__ = "story_episodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    output_intent = Column(String, nullable=False, default="truyen_anh")
    market_profile = Column(String, nullable=False, default="viet_nam")
    language_profile = Column(String, nullable=False, default="vi")
    source_input = Column(Text, nullable=True)
    source_digest = Column(Text, nullable=True)
    # Comic Series Analysis (change 13): the canonical structured source.
    current_source_document_id = Column(
        String, ForeignKey("story_episode_source_documents.id"), nullable=True
    )
    development_mode = Column(String, nullable=True)  # NULL for legacy/manual episodes
    rights_attestation_revision = Column(Integer, nullable=True)
    master_story_approval_status = Column(String, nullable=True)  # includes "stale"
    master_story_approved_at = Column(DateTime, nullable=True)
    output_settings_json = Column(JSON, nullable=True)
    master_story_json = Column(JSON, nullable=True)
    selection_reason = Column(Text, nullable=True)
    approval_status = Column(String, nullable=False, default="draft")
    approved_at = Column(DateTime, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StoryScenarioCandidate(Base):
    """One generated direction for a Story Studio episode."""

    __tablename__ = "story_scenario_candidates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=False)
    strategy_type = Column(String, nullable=False)
    script_json = Column(JSON, nullable=False)
    score_json = Column(JSON, nullable=True)
    strengths = Column(Text, nullable=True)
    risks = Column(Text, nullable=True)
    context_snapshot_id = Column(String, nullable=True)
    model_label = Column(String, nullable=True)
    generation_attempt = Column(Integer, nullable=False, default=1)
    generation_status = Column(String, nullable=False, default="completed")
    generation_metadata_json = Column(JSON, nullable=True)
    evaluation_status = Column(String, nullable=False, default="pending")
    evaluation_json = Column(JSON, nullable=True)
    selected = Column(Boolean, nullable=False, default=False)
    # Comic source dependency (change 13, task 2.14): the exact source doc/mode
    # revision this candidate was generated from, so it can be staled precisely.
    source_document_id = Column(String, nullable=True)
    source_document_revision = Column(Integer, nullable=True)
    development_mode = Column(String, nullable=True)
    dependency_fingerprint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StoryAdaptation(Base):
    """Rendered-product handoff for image story or video story outputs."""

    __tablename__ = "story_adaptations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=False)
    kind = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    payload_json = Column(JSON, nullable=True)
    linked_video_project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoProject(Base):
    """AI Video Assistant project state."""

    __tablename__ = "video_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=True)
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
    # Lifecycle management is separate from production status. Archived
    # projects remain recoverable and keep their generated artifacts.
    archived_at = Column(DateTime, nullable=True)
    creative_brief = Column(Text, nullable=True)
    script_text = Column(Text, nullable=True)
    style_bible = Column(Text, nullable=True)
    character_bible = Column(Text, nullable=True)
    script_approved = Column(Boolean, nullable=False, default=False)
    phase = Column(String, nullable=False, default="phase1")
    target_language = Column(String, nullable=False, default="en")
    # Explicit News Video speech mode; NULL preserves legacy language fallback.
    speech_source = Column(String, nullable=True)
    video_purpose = Column(String, nullable=False, default="custom")
    # Structured Content Profile (v1). Nullable on disk so older SQLite files
    # can be upgraded without rewriting historical projects; API responses
    # resolve null legacy values from video_purpose at read time.
    content_profile_version = Column(Integer, nullable=True, default=1)
    content_objective = Column(String, nullable=True)
    content_genre = Column(String, nullable=True)
    audience_age_band = Column(String, nullable=True)
    format_profile = Column(String, nullable=True)
    distribution_platform = Column(String, nullable=True)
    interaction_mode = Column(String, nullable=True)
    safety_policy = Column(String, nullable=True)
    made_for_kids = Column(Boolean, nullable=True)
    learning_objective = Column(Text, nullable=True)
    dialogue_mode = Column(String, nullable=False, default="voiceover")
    narration_density = Column(String, nullable=False, default="balanced")
    call_to_action_style = Column(String, nullable=True)
    cta_action = Column(String, nullable=True)
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

class NewsVideoWorkflow(Base):
    """News-specific metadata; presence of this row discriminates News projects."""
    __tablename__ = "news_video_workflows"
    project_id = Column(String, ForeignKey("video_projects.id"), primary_key=True)
    visual_format = Column(String, nullable=False, default="9:16")
    source_note = Column(Text, nullable=True)
    default_speech_source = Column(String, nullable=True)
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

class VideoPublishingMetadata(Base):
    """Project-level publishing copy for YouTube, TikTok and Facebook."""

    __tablename__ = "video_publishing_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="missing")
    target_language = Column(String, nullable=False, default="en")
    platforms_json = Column(JSON, nullable=False, default=dict)
    input_fingerprint = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    stale = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
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

class VideoProviderProjectBinding(Base):
    """Internal Flow/Veo project URL binding for one project or one series."""

    __tablename__ = "video_provider_project_bindings"
    __table_args__ = (
        CheckConstraint(
            "(project_id IS NOT NULL AND series_id IS NULL) OR (project_id IS NULL AND series_id IS NOT NULL)",
            name="ck_video_provider_binding_exact_scope",
        ),
        CheckConstraint(
            "status IN ('active', 'needs_check', 'invalid', 'rotated')",
            name="ck_video_provider_binding_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    provider = Column(String, nullable=False, default="veo")
    provider_tool = Column(String, nullable=False, default="veo3_flow")
    provider_project_url = Column(Text, nullable=False)
    provider_project_ref_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    last_checked_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    observed_model_label = Column(String, nullable=True)
    observed_model_cost_label = Column(String, nullable=True)
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
    enable_codex_repair = Column(Boolean, nullable=False, default=False)
    credit_approval_policy = Column(String, nullable=False, default="approve_dont_ask_again")
    max_credit_per_job = Column(Integer, nullable=True)
    credit_spent_estimate = Column(Integer, nullable=False, default=0)
    render_job_id = Column(String, ForeignKey("video_render_jobs.id"), nullable=True)
    download_dir = Column(String, nullable=True)
    repair_status = Column(String, nullable=True)
    repair_attempt_count = Column(Integer, nullable=False, default=0)
    repair_report_json = Column(JSON, nullable=True)
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
    observed_model_label = Column(String, nullable=True)
    observed_model_cost_label = Column(String, nullable=True)
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

class VideoCodexRepairAttempt(Base):
    """Audit row for a bounded Codex repair attempt on a provider job."""

    __tablename__ = "video_codex_repair_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_clip_generation_jobs.id"), nullable=False)
    item_id = Column(String, ForeignKey("video_clip_generation_items.id"), nullable=True)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    status = Column(String, nullable=False, default="queued")
    error_code = Column(String, nullable=False)
    step_name = Column(String, nullable=True)
    repair_context_json = Column(JSON, nullable=True)
    files_changed_json = Column(JSON, nullable=True)
    tests_run_json = Column(JSON, nullable=True)
    test_result = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    requires_approval = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

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
    revision = Column(Integer, nullable=False, default=1)
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
    speech_cues_json = Column(JSON, nullable=True)
    # Per-shot News Video override; NULL inherits project/legacy resolver.
    speech_source_override = Column(String, nullable=True)
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
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def micro_scenes(self):
        return self.micro_scenes_json or []

    @micro_scenes.setter
    def micro_scenes(self, value):
        self.micro_scenes_json = value

    @property
    def speech_cues(self):
        return self.speech_cues_json or []

    @speech_cues.setter
    def speech_cues(self, value):
        self.speech_cues_json = value

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
    quality_threshold = Column(Float, nullable=False, default=85.0)
    parent_prompt_id = Column(String, ForeignKey("video_shot_prompts.id"), nullable=True)
    repair_attempt = Column(Integer, nullable=False, default=0)
    repair_status = Column(String, nullable=False, default="none")
    repair_changes_json = Column(JSON, nullable=True)
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
    enhanced_plan_path = Column(String, nullable=True)
    review_report_path = Column(String, nullable=True)
    enhanced_artifacts_json = Column(JSON, nullable=True)
    review_status = Column(String, nullable=True)
    fix_attempt_count = Column(Integer, nullable=False, default=0)
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
    revision = Column(Integer, nullable=False, default=1)
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
    revision = Column(Integer, nullable=False, default=1)
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

class VideoInspirationJob(Base):
    """Workflow state for turning an existing video into a new script."""

    __tablename__ = "video_inspiration_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False, default="upload")
    source_url = Column(Text, nullable=True)
    original_filename = Column(String, nullable=True)
    source_platform = Column(String, nullable=False, default="unknown")
    source_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    source_duration_seconds = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="uploaded")
    current_step = Column(String, nullable=False, default="source_ready")
    progress = Column(Float, nullable=False, default=0.0)
    target_language = Column(String, nullable=False, default="vi")
    rewrite_mode = Column(String, nullable=False, default="bold_remix")
    user_direction = Column(Text, nullable=True)
    transcript_text = Column(Text, nullable=True)
    transcript_language = Column(String, nullable=True)
    transcript_status = Column(String, nullable=False, default="pending")
    analysis_schema_version = Column(String, nullable=False, default="video_analysis_package.v1")
    analysis_mode = Column(String, nullable=False, default="quick")
    analysis_package_json = Column(JSON, nullable=True)
    analysis_package_path = Column(String, nullable=True)
    coverage_metrics_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    retention_source = Column(String, nullable=False, default="predicted_from_content")
    analysis_completeness = Column(String, nullable=False, default="not_started")
    visual_summary = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=True)
    rewritten_script = Column(Text, nullable=True)
    script_title = Column(String, nullable=True)
    big_idea = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    created_video_project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    latest_auto_run_id = Column(String, ForeignKey("video_auto_runs.id"), nullable=True)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoInspirationFrame(Base):
    """Sampled frame extracted from a source video for visual analysis."""

    __tablename__ = "video_inspiration_frames"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    shot_id = Column(String, ForeignKey("video_inspiration_shots.id"), nullable=True)
    shot_order = Column(Integer, nullable=True)
    frame_role = Column(String, nullable=False, default="keyframe")
    frame_path = Column(String, nullable=False)
    timestamp_seconds = Column(Float, nullable=False, default=0.0)
    description_vi = Column(Text, nullable=True)
    technical_metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoInspirationShot(Base):
    """Detected source-video shot with keyframes and per-shot observations."""

    __tablename__ = "video_inspiration_shots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    shot_order = Column(Integer, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    keyframe_ids_json = Column(JSON, nullable=True)
    visual_description_vi = Column(Text, nullable=True)
    subjects_json = Column(JSON, nullable=True)
    setting_json = Column(JSON, nullable=True)
    camera_json = Column(JSON, nullable=True)
    subject_motion_json = Column(JSON, nullable=True)
    transition_in = Column(String, nullable=True)
    transition_out = Column(String, nullable=True)
    on_screen_text_json = Column(JSON, nullable=True)
    confidence_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoInspirationTranscriptSegment(Base):
    """Transcript segment with timing precision and edit provenance."""

    __tablename__ = "video_inspiration_transcript_segments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    segment_order = Column(Integer, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    text = Column(Text, nullable=False, default="")
    raw_text = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    speaker_label = Column(String, nullable=True)
    source = Column(String, nullable=False, default="stt_raw")
    timestamp_precision = Column(String, nullable=False, default="chunk")
    confidence = Column(Float, nullable=True)
    shot_ids_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoInspirationAudioEvent(Base):
    """Observed or inferred audio timeline event independent from transcript."""

    __tablename__ = "video_inspiration_audio_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    event_order = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    description_vi = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    technical_metadata_json = Column(JSON, nullable=True)
    shot_ids_json = Column(JSON, nullable=True)
    transcript_segment_ids_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoInspirationTextEvent(Base):
    """OCR or vision text event shown on screen."""

    __tablename__ = "video_inspiration_text_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    shot_id = Column(String, ForeignKey("video_inspiration_shots.id"), nullable=True)
    event_order = Column(Integer, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    text = Column(Text, nullable=False, default="")
    language = Column(String, nullable=True)
    role = Column(String, nullable=False, default="unknown")
    region_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="vision")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoInspirationRetentionBeat(Base):
    """Predicted content-retention beat with timestamped evidence."""

    __tablename__ = "video_inspiration_retention_beats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    beat_order = Column(Integer, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    role = Column(String, nullable=False, default="development")
    viewer_question_before = Column(Text, nullable=True)
    content_promise = Column(Text, nullable=True)
    new_information = Column(Text, nullable=True)
    emotional_or_stakes_change = Column(Text, nullable=True)
    question_answered = Column(Text, nullable=True)
    new_open_loop = Column(Text, nullable=True)
    micro_payoff = Column(Text, nullable=True)
    why_continue = Column(Text, nullable=True)
    drop_off_risks_json = Column(JSON, nullable=True)
    evidence_refs_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoInspirationHandoff(Base):
    """Durable structured handoff from Video Inspiration to AI Video."""

    __tablename__ = "video_inspiration_handoffs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=False)
    analysis_package_path = Column(String, nullable=True)
    analysis_package_revision = Column(String, nullable=False, default="video_analysis_package.v1")
    schema_version = Column(String, nullable=False, default="video_inspiration_handoff.v1")
    status = Column(String, nullable=False, default="draft")
    target_language = Column(String, nullable=False, default="vi")
    approved_script_revision = Column(Integer, nullable=False, default=1)
    payload_json = Column(JSON, nullable=False, default=dict)
    source_blocks_json = Column(JSON, nullable=True)
    created_project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

class VideoProjectMemoryCard(Base):
    """Approved project-scope memory card for standalone and series projects."""

    __tablename__ = "video_project_memory_cards"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    memory_scope = Column(String, nullable=False, default="project")
    card_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content_json = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="approved")
    source_type = Column(String, nullable=False, default="handoff")
    source_ref_id = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

class VideoProjectTargetTimelineBeat(Base):
    """Target timeline beat restructured for the new AI Video project."""

    __tablename__ = "video_project_target_timeline_beats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    handoff_id = Column(String, ForeignKey("video_inspiration_handoffs.id"), nullable=True)
    beat_order = Column(Integer, nullable=False)
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    role = Column(String, nullable=False, default="development")
    content = Column(Text, nullable=True)
    viewer_question = Column(Text, nullable=True)
    new_information = Column(Text, nullable=True)
    micro_payoff = Column(Text, nullable=True)
    visual_direction = Column(Text, nullable=True)
    audio_direction = Column(Text, nullable=True)
    evidence_refs_json = Column(JSON, nullable=True)
    source_lesson_refs_json = Column(JSON, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VideoProjectContextSnapshot(Base):
    """Compiled task-specific context used by AI Video generation steps."""

    __tablename__ = "video_project_context_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    task_type = Column(String, nullable=False)
    artifact_type = Column(String, nullable=True)
    artifact_id = Column(String, nullable=True)
    context_json = Column(JSON, nullable=False, default=dict)
    source_refs_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoQualityReport(Base):
    """End-to-end quality gate report for AI Video and Video Inspiration artifacts."""

    __tablename__ = "video_quality_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=True)
    scope = Column(String, nullable=False, default="project")
    status = Column(String, nullable=False, default="not_checked")
    overall_status = Column(String, nullable=False, default="not_checked")
    content_score = Column(Float, nullable=False, default=0.0)
    presentation_score = Column(Float, nullable=False, default=0.0)
    total_score = Column(Float, nullable=False, default=0.0)
    rubric_json = Column(JSON, nullable=False, default=dict)
    sections_json = Column(JSON, nullable=False, default=dict)
    blocking_errors_json = Column(JSON, nullable=True)
    warnings_json = Column(JSON, nullable=True)
    recommended_actions_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    dependencies_json = Column(JSON, nullable=True)
    override_history_json = Column(JSON, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PlatformRetentionDataset(Base):
    """Optional imported real platform retention data normalized for timeline comparison."""

    __tablename__ = "platform_retention_datasets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=True)
    job_id = Column(String, ForeignKey("video_inspiration_jobs.id"), nullable=True)
    platform = Column(String, nullable=False, default="manual")
    video_duration_seconds = Column(Float, nullable=False, default=0.0)
    data_points_json = Column(JSON, nullable=False, default=list)
    normalized_points_json = Column(JSON, nullable=False, default=list)
    average_watch_time = Column(Float, nullable=True)
    completion_rate = Column(Float, nullable=True)
    rewatch_rate = Column(Float, nullable=True)
    cta_click_rate = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    source_type = Column(String, nullable=False, default="manual")
    linked_findings_json = Column(JSON, nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================================================
# Comic Series Analysis (change 13) — independent from Video Inspiration.
# No foreign key to video_inspiration_jobs. Only intersects Series/Episode.
# ==========================================================================

class ComicAnalysisJob(Base):
    """Workflow state for ingesting and analyzing a comic source."""

    __tablename__ = "comic_analysis_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False, default="url")  # url | upload | mixed
    source_url = Column(Text, nullable=True)  # redacted, stored URL
    title = Column(String, nullable=True)
    reading_mode = Column(String, nullable=False, default="auto")
    development_mode = Column(String, nullable=False, default="lay_cam_hung_va_viet_moi")
    rights_attested_at = Column(DateTime, nullable=True)
    rights_attestation_revision = Column(Integer, nullable=False, default=0)
    # Lifecycle (contracts.RunStatus) separate from completeness.
    run_status = Column(String, nullable=False, default="draft")
    result_completeness = Column(String, nullable=False, default="unavailable")
    current_step = Column(String, nullable=False, default="validate_source")
    progress = Column(Float, nullable=False, default=0.0)
    step_state_json = Column(JSON, nullable=True)  # per-step checkpoint/coverage/error
    source_package_schema_version = Column(
        String, nullable=False, default="comic_source_package.v1"
    )
    analysis_schema_version = Column(
        String, nullable=False, default="comic_analysis_package.v1"
    )
    current_source_document_id = Column(
        String, ForeignKey("comic_source_documents.id"), nullable=True
    )
    analysis_revision = Column(Integer, nullable=False, default=0)
    coverage_metrics_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    analysis_package_json = Column(JSON, nullable=True)
    analysis_package_path = Column(String, nullable=True)
    approval_manifest_id = Column(String, nullable=True)
    outcome_code = Column(String, nullable=True)  # authentication_required, etc.
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    active_operation_id = Column(String, nullable=True)  # guards concurrent runs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicSourceDocument(Base):
    """Immutable-after-finalize snapshot of one ingested comic source revision."""

    __tablename__ = "comic_source_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    previous_revision_id = Column(
        String, ForeignKey("comic_source_documents.id"), nullable=True
    )
    lifecycle = Column(String, nullable=False, default="collecting")  # collecting|finalized
    requested_url = Column(Text, nullable=True)
    canonical_url = Column(Text, nullable=True)
    final_url = Column(Text, nullable=True)  # after redirects, redacted
    retrieval_mode = Column(String, nullable=True)  # static | browser | upload | manual_text
    http_status = Column(Integer, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    extractor_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)  # over ordered text+asset manifest
    asset_manifest_json = Column(JSON, nullable=True)  # ordered checksums
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    chapter_identity = Column(String, nullable=True)
    coverage_metrics_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    raw_html_quarantine_path = Column(String, nullable=True)  # isolated, not creative
    finalized_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicSourcePage(Base):
    """One page/text-chunk position within a source document, in reading order."""

    __tablename__ = "comic_source_pages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("comic_source_documents.id"), nullable=False)
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    page_order = Column(Integer, nullable=False, default=0)
    page_kind = Column(String, nullable=False, default="image")  # image | text | mixed
    asset_id = Column(String, ForeignKey("comic_source_assets.id"), nullable=True)
    extracted_text = Column(Text, nullable=True)  # cleaned HTML text chunk
    evidence_id = Column(String, nullable=True)  # stable evidence anchor
    provenance = Column(String, nullable=False, default="web")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ComicSourceAsset(Base):
    """An original image byte-blob plus its provenance and derivative links."""

    __tablename__ = "comic_source_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("comic_source_documents.id"), nullable=False)
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    asset_order = Column(Integer, nullable=False, default=0)
    original_path = Column(String, nullable=True)
    source_url = Column(Text, nullable=True)  # redacted
    referrer = Column(Text, nullable=True)
    detected_format = Column(String, nullable=True)  # from magic bytes
    sniffed_mime_type = Column(String, nullable=True)
    byte_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    frame_count = Column(Integer, nullable=False, default=1)
    page_count = Column(Integer, nullable=False, default=1)
    checksum = Column(String, nullable=True)  # sha256 of original bytes
    decoded_pixel_hash = Column(String, nullable=True)  # post-orientation/colorspace
    codec_status = Column(String, nullable=False, default="pending")  # ok|codec_unavailable|...
    provenance = Column(String, nullable=False, default="web")
    occurrences_json = Column(JSON, nullable=True)  # list of DOM positions/URLs
    derivatives_json = Column(JSON, nullable=True)  # analysis/preview/tile/export paths
    transform_version = Column(String, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicPanel(Base):
    """A detected panel with reading order, bounding box and confidence."""

    __tablename__ = "comic_panels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    page_id = Column(String, ForeignKey("comic_source_pages.id"), nullable=True)
    asset_id = Column(String, ForeignKey("comic_source_assets.id"), nullable=True)
    tile_id = Column(String, nullable=True)
    reading_order = Column(Integer, nullable=False, default=0)
    bounding_box_json = Column(JSON, nullable=True)  # {x, y, w, h} in source coords
    visual_description = Column(Text, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    edit_source = Column(String, nullable=False, default="observed")
    needs_review = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicSpeechBubble(Base):
    """OCR/dialogue region: raw, AI-normalized and user-edited text kept apart."""

    __tablename__ = "comic_speech_bubbles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    panel_id = Column(String, ForeignKey("comic_panels.id"), nullable=True)
    reading_order = Column(Integer, nullable=False, default=0)
    bubble_type = Column(String, nullable=False, default="unknown")  # dialogue|narration|sfx|unknown
    bounding_box_json = Column(JSON, nullable=True)
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    approved_text = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    speaker_character_id = Column(String, nullable=True)
    speaker_confidence = Column(Float, nullable=True)
    speaker_evidence_ids_json = Column(JSON, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)
    edit_source = Column(String, nullable=False, default="observed")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicDetectedCharacter(Base):
    """A clustered character candidate with multi-evidence attributes."""

    __tablename__ = "comic_detected_characters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    display_name = Column(String, nullable=True)
    aliases_json = Column(JSON, nullable=True)
    role = Column(String, nullable=True)
    face_description = Column(Text, nullable=True)
    hair_description = Column(Text, nullable=True)
    body_description = Column(Text, nullable=True)
    outfit_description = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    speech_style = Column(Text, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)  # panels/bubbles/assets
    reference_asset_ids_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    possible_duplicate_of_json = Column(JSON, nullable=True)
    edit_source = Column(String, nullable=False, default="inferred")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicDetectedLocation(Base):
    """A detected location / world-rule candidate."""

    __tablename__ = "comic_detected_locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    world_rules = Column(Text, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    edit_source = Column(String, nullable=False, default="inferred")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicPlotAnalysis(Base):
    """Structured plot / canon / development analysis for one revision."""

    __tablename__ = "comic_plot_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    synopsis = Column(Text, nullable=True)
    plot_beats_json = Column(JSON, nullable=True)  # opening/conflict/climax/ending
    relationships_json = Column(JSON, nullable=True)
    end_state_json = Column(JSON, nullable=True)
    canon_candidates_json = Column(JSON, nullable=True)  # each w/ evidence+confidence
    development_options_json = Column(JSON, nullable=True)  # drafts only
    uncertainties_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    originality_check_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicApprovalManifest(Base):
    """Immutable manifest of accepted/excluded/unreviewed items for a revision."""

    __tablename__ = "comic_approval_manifests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    schema_version = Column(String, nullable=False, default="comic_approval_manifest.v1")
    manifest_hash = Column(String, nullable=False)
    accepted_items_json = Column(JSON, nullable=False, default=list)
    excluded_items_json = Column(JSON, nullable=False, default=list)
    unreviewed_items_json = Column(JSON, nullable=False, default=list)
    accepted_limitations_json = Column(JSON, nullable=True)
    requested_development_mode = Column(String, nullable=False, default="lay_cam_hung_va_viet_moi")
    rights_attestation_revision = Column(Integer, nullable=False, default=0)
    source_document_revision = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)  # invalidated on new revision
    created_at = Column(DateTime, default=datetime.utcnow)


class ComicSeriesHandoff(Base):
    """A preview/commit of one comic analysis revision into a Series."""

    __tablename__ = "comic_series_handoffs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comic_analysis_jobs.id"), nullable=False)
    analysis_revision = Column(Integer, nullable=False, default=1)
    approval_manifest_id = Column(
        String, ForeignKey("comic_approval_manifests.id"), nullable=True
    )
    approval_manifest_hash = Column(String, nullable=True)
    rights_attestation_revision = Column(Integer, nullable=False, default=0)
    development_mode = Column(String, nullable=False, default="lay_cam_hung_va_viet_moi")
    target_kind = Column(String, nullable=False, default="new_series")  # new_series|existing_series
    target_series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    target_series_mode = Column(String, nullable=True)  # image_story_only | hybrid
    target_series_title = Column(String, nullable=True)
    episode_number = Column(Integer, nullable=True)
    episode_title = Column(String, nullable=True)
    output_intent = Column(String, nullable=False, default="truyen_anh")
    target_dependency_fingerprint = Column(String, nullable=True)
    preview_fingerprint = Column(String, nullable=True)
    mapping_schema_version = Column(String, nullable=False, default="comic_series_handoff.v1")
    item_decisions_json = Column(JSON, nullable=True)
    conflict_resolutions_json = Column(JSON, nullable=True)
    ai_matching_json = Column(JSON, nullable=True)  # persisted/versioned matching input
    idempotency_key = Column(String, nullable=True)
    operation_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="previewed")  # HandoffStatus
    created_series_id = Column(String, ForeignKey("video_series.id"), nullable=True)
    created_story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=True)
    created_source_document_id = Column(String, nullable=True)
    staging_manifest_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    failure_reason = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComicSeriesHandoffItem(Base):
    """One create/update/merge/skip item within a handoff, with its decision."""

    __tablename__ = "comic_series_handoff_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    handoff_id = Column(String, ForeignKey("comic_series_handoffs.id"), nullable=False)
    item_type = Column(String, nullable=False)  # episode|character|location|canon|memory|reference|...
    source_ref_id = Column(String, nullable=True)  # comic entity id
    decision = Column(String, nullable=False, default="create")  # HandoffItemDecision
    target_ref_type = Column(String, nullable=True)
    target_ref_id = Column(String, nullable=True)
    expected_target_revision = Column(Integer, nullable=True)
    field_decisions_json = Column(JSON, nullable=True)  # field-level resolutions
    match_confidence = Column(Float, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)
    created_target_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="previewed")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StoryEpisodeSourceDocument(Base):
    """Canonical, full-content source of a Story Episode created from a comic.

    Holds raw-extracted, AI-normalized and approved content; the source of
    truth that replaces the 50k-char ``source_input`` projection.
    """

    __tablename__ = "story_episode_source_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    previous_revision_id = Column(
        String, ForeignKey("story_episode_source_documents.id"), nullable=True
    )
    approval_status = Column(String, nullable=False, default="approved")  # approved|superseded|stale
    schema_version = Column(String, nullable=False, default="comic_source_package.v1")
    source_kind = Column(String, nullable=False, default="comic_analysis")
    comic_job_id = Column(String, nullable=True)  # provenance (no FK to keep boundary loose)
    comic_analysis_revision = Column(Integer, nullable=True)
    comic_source_revision = Column(Integer, nullable=True)
    handoff_id = Column(String, nullable=True)
    title = Column(String, nullable=True)
    synopsis = Column(Text, nullable=True)
    plot_structure_json = Column(JSON, nullable=True)
    raw_extracted_text = Column(Text, nullable=True)
    ai_normalized_text = Column(Text, nullable=True)
    approved_text = Column(Text, nullable=True)
    coverage_metrics_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True)
    provenance_json = Column(JSON, nullable=True)  # urls, hashes, fetched_at, revisions
    content_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StoryEpisodeSourceChunk(Base):
    """An ordered, evidence-linked chunk of a Story Episode source document."""

    __tablename__ = "story_episode_source_chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String, ForeignKey("story_episode_source_documents.id"), nullable=False
    )
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=False)
    chunk_order = Column(Integer, nullable=False, default=0)
    chunk_type = Column(String, nullable=False, default="text")  # text|dialogue|narration|panel|visual
    approved_text = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    ai_text = Column(Text, nullable=True)
    page_refs_json = Column(JSON, nullable=True)
    panel_refs_json = Column(JSON, nullable=True)
    bubble_refs_json = Column(JSON, nullable=True)
    speaker_ref = Column(String, nullable=True)
    evidence_ids_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    source_revision = Column(Integer, nullable=True)
    approval_state = Column(String, nullable=False, default="accepted")  # accepted|unreviewed
    created_at = Column(DateTime, default=datetime.utcnow)


class StoryEpisodeSourceAsset(Base):
    """Immutable link from a Story Episode source doc to a comic source asset."""

    __tablename__ = "story_episode_source_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String, ForeignKey("story_episode_source_documents.id"), nullable=False
    )
    story_episode_id = Column(String, ForeignKey("story_episodes.id"), nullable=False)
    asset_order = Column(Integer, nullable=False, default=0)
    comic_source_asset_id = Column(String, nullable=True)
    original_path = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    source_revision = Column(Integer, nullable=True)
    occurrences_json = Column(JSON, nullable=True)  # page/panel occurrences
    evidence_mapping_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ComicSourceVersionRecord(Base):
    """Maps target Series/Episode/Profile/etc. back to analysis+handoff+evidence."""

    __tablename__ = "comic_source_version_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, nullable=True)
    handoff_id = Column(String, nullable=True)
    analysis_revision = Column(Integer, nullable=True)
    source_document_revision = Column(Integer, nullable=True)
    target_type = Column(String, nullable=False)  # series|episode|profile|memory|reference
    target_id = Column(String, nullable=False)
    evidence_ids_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResearchProject(Base):
    """Persistent research workspace; DB is the source of truth."""

    __tablename__ = "research_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    brief = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")
    revision = Column(Integer, nullable=False, default=1)
    memory_path = Column(String, nullable=True)
    manifest_path = Column(String, nullable=True)
    tags_json = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchSource(Base):
    """One immutable input and its normalized research package."""

    __tablename__ = "research_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    source_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    input_url = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued")
    revision = Column(Integer, nullable=False, default=1)
    source_package_path = Column(String, nullable=True)
    summary_path = Column(String, nullable=True)
    artifact_dir = Column(String, nullable=True)
    source_hash = Column(String, nullable=True)
    result_json = Column(JSON, nullable=True)
    limitations_json = Column(JSON, nullable=True, default=list)
    provenance_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchRun(Base):
    """A research/creative attempt or an explicit merge run."""

    __tablename__ = "research_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    mode = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    brief_path = Column(String, nullable=True)
    research_result_path = Column(String, nullable=True)
    creative_result_path = Column(String, nullable=True)
    merged_result_path = Column(String, nullable=True)
    output_json = Column(JSON, nullable=True)
    provider_metadata_json = Column(JSON, nullable=True)
    cost_json = Column(JSON, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchIdea(Base):
    """Candidate or accepted content option."""

    __tablename__ = "research_ideas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    run_id = Column(String, ForeignKey("research_runs.id"), nullable=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="candidate")
    idea_path = Column(String, nullable=True)
    source_provider = Column(String, nullable=True)
    content_json = Column(JSON, nullable=True, default=dict)
    dependency_fingerprint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchScript(Base):
    """Draft or accepted script seed linked to an idea."""

    __tablename__ = "research_scripts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    idea_id = Column(String, ForeignKey("research_ideas.id"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    script_path = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    content_json = Column(JSON, nullable=True, default=dict)
    target_format = Column(String, nullable=True, default="series_3_minute")
    dependency_fingerprint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchScore(Base):
    """Versioned rubric score and recommendation for an idea or script."""

    __tablename__ = "research_scores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    rubric_version = Column(String, nullable=False, default="research-score.v1")
    components_json = Column(JSON, nullable=False, default=dict)
    total_score = Column(Float, nullable=False, default=0.0)
    recommendation_status = Column(String, nullable=False, default="alternative")
    recommendation_reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    tie_group = Column(Integer, nullable=True)
    completeness_status = Column(String, nullable=False, default="incomplete")
    stale_reason = Column(Text, nullable=True)
    improvement_actions_json = Column(JSON, nullable=True, default=list)
    tradeoffs_json = Column(JSON, nullable=True, default=dict)
    safety_gate_json = Column(JSON, nullable=True, default=dict)
    provider_metadata_json = Column(JSON, nullable=True, default=dict)
    cost_json = Column(JSON, nullable=True, default=dict)
    evidence_refs_json = Column(JSON, nullable=True, default=list)
    limitations_json = Column(JSON, nullable=True, default=list)
    dependency_fingerprint = Column(String, nullable=True)
    user_override_status = Column(String, nullable=True)
    user_override_reason = Column(Text, nullable=True)
    user_override_revision = Column(Integer, nullable=False, default=0)
    user_override_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchChatThread(Base):
    """A persistent content-development conversation."""

    __tablename__ = "research_chat_threads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    title = Column(String, nullable=True)
    selected_project_ids_json = Column(JSON, nullable=True, default=list)
    branch_name = Column(String, nullable=True, default="canon")
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchChatMessage(Base):
    """One user or AI draft message; accepted actions are explicit."""

    __tablename__ = "research_chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, ForeignKey("research_chat_threads.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String, nullable=False, default="draft")
    status = Column(String, nullable=False, default="draft")
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResearchHandoff(Base):
    """Immutable approved handoff from research into an AI Video project."""

    __tablename__ = "research_handoffs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="previewed")
    idempotency_key = Column(String, nullable=True, unique=True)
    dependency_fingerprint = Column(String, nullable=True)
    accepted_idea_ids_json = Column(JSON, nullable=True, default=list)
    accepted_script_ids_json = Column(JSON, nullable=True, default=list)
    payload_json = Column(JSON, nullable=False, default=dict)
    handoff_path = Column(String, nullable=True)
    target_ai_video_project_id = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutomationConnection(Base):
    """Encrypted connection metadata for Automation Hub integrations."""

    __tablename__ = "automation_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = Column(String, nullable=False, default="publisher")
    platform = Column(String, nullable=False)
    label = Column(String, nullable=False)
    status = Column(String, nullable=False, default="not_configured")
    public_config_json = Column(JSON, nullable=False, default=dict)
    secret_ciphertext = Column(Text, nullable=True)
    secret_fingerprint = Column(String, nullable=True)
    scopes_json = Column(JSON, nullable=True, default=list)
    last_checked_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutomationAsset(Base):
    """Immutable video snapshot used by Automation Hub publishing jobs."""

    __tablename__ = "automation_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False, default="upload")
    source_ref = Column(String, nullable=True)
    stored_path = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False, default="video/mp4")
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AutomationPublishJob(Base):
    """Independent social publishing job owned by Automation Hub."""

    __tablename__ = "automation_publish_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String, ForeignKey("automation_assets.id"), nullable=False)
    connection_id = Column(String, ForeignKey("automation_connections.id"), nullable=False)
    platform = Column(String, nullable=False)
    publish_mode = Column(String, nullable=False, default="standard")
    status = Column(String, nullable=False, default="queued")
    title = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    tags_json = Column(JSON, nullable=True, default=list)
    privacy = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String, nullable=False, unique=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    provider_post_id = Column(String, nullable=True)
    provider_url = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutomationPublishAttempt(Base):
    """Redacted audit record for one provider upload attempt."""

    __tablename__ = "automation_publish_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("automation_publish_jobs.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="running")
    request_meta_json = Column(JSON, nullable=True, default=dict)
    response_meta_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductVideoProject(Base):
    """Product-selling video project with a prompt-only planning boundary.

    ``render_project_id`` points at an internal phase-2 AI Video bridge used
    only after the user uploads clips and explicitly starts an MP4 render.
    Product Video never creates provider-generation or TTS jobs automatically.
    """

    __tablename__ = "product_video_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    topic = Column(Text, nullable=False)
    target_language = Column(String, nullable=False, default="vi")
    aspect_ratio = Column(String, nullable=False, default="9:16")
    visual_style = Column(Text, nullable=True)
    visual_style_preset = Column(String, nullable=True)
    video_purpose = Column(String, nullable=False, default="sales_ad")
    dialogue_mode = Column(String, nullable=False, default="voiceover")
    narration_density = Column(String, nullable=False, default="light")
    call_to_action_style = Column(String, nullable=True)
    # These mirror AI Video's creation controls. They govern only Product
    # Video planning/prompt stages; provider/TTS/render work remains explicit.
    creation_mode = Column(String, nullable=False, default="quick")
    automation_mode = Column(String, nullable=False, default="full_auto")
    output_target = Column(String, nullable=False, default="render_ready")
    target_duration_seconds = Column(Integer, nullable=False, default=30)
    prompt_segment_count = Column(Integer, nullable=True)
    prompt_segment_duration_seconds = Column(Integer, nullable=True)
    micro_scenes_per_prompt = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="draft")
    planning_status = Column(String, nullable=False, default="draft")
    planning_error = Column(Text, nullable=True)
    hook_text = Column(Text, nullable=True)
    retention_plan_json = Column(JSON, nullable=True)
    sound_design_plan_json = Column(JSON, nullable=True)
    render_project_id = Column(String, ForeignKey("video_projects.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductVideoShot(Base):
    """One planned Flow clip of a product video project."""

    __tablename__ = "product_video_shots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("product_video_projects.id"), nullable=False)
    shot_order = Column(Integer, nullable=False, default=1)
    shot_type = Column(String, nullable=True)
    framing = Column(String, nullable=True)
    camera_angle = Column(String, nullable=True)
    composition = Column(Text, nullable=True)
    camera_motion = Column(Text, nullable=True)
    subject_motion = Column(Text, nullable=True)
    environment_motion = Column(Text, nullable=True)
    lighting = Column(Text, nullable=True)
    mood = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    beat_role = Column(String, nullable=True)
    narration_text = Column(Text, nullable=True)
    retention_notes = Column(Text, nullable=True)
    transition_notes = Column(Text, nullable=True)
    sound_design_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductVideoShotPrompt(Base):
    """Rendered Flow prompt text for one product video shot."""

    __tablename__ = "product_video_shot_prompts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("product_video_projects.id"), nullable=False)
    shot_id = Column(String, ForeignKey("product_video_shots.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    prompt_explanation_vi = Column(Text, nullable=True)
    aspect_ratio = Column(String, nullable=False, default="9:16")
    created_at = Column(DateTime, default=datetime.utcnow)
