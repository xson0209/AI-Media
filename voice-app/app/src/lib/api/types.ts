// API Types matching backend Pydantic models
import type { LanguageCode } from '@/lib/constants/languages';

export type VoiceType = 'cloned' | 'preset' | 'designed';
export type VideoLanguage = LanguageCode;
export type VideoPurpose =
  | 'custom'
  | 'vietnam_market'
  | 'global_short'
  | 'educational_explainer'
  | 'sales_ad'
  | 'localized_variant';
export type DialogueMode = 'voiceover' | 'character_lines' | 'mixed';
export type NarrationDensity = 'light' | 'balanced' | 'dense';
export type CallToActionStyle = 'none' | 'soft' | 'direct' | 'urgent';

export interface VoiceProfileCreate {
  name: string;
  description?: string;
  language: LanguageCode;
  voice_type?: VoiceType;
  preset_engine?: string;
  preset_voice_id?: string;
  design_prompt?: string;
  default_engine?: string;
  /** Free-form character prompt used by compose and the `/generate` personality-rewrite path. */
  personality?: string;
}

export interface VoiceProfileResponse {
  id: string;
  name: string;
  description?: string;
  language: string;
  avatar_path?: string;
  effects_chain?: EffectConfig[];
  voice_type: VoiceType;
  preset_engine?: string;
  preset_voice_id?: string;
  design_prompt?: string;
  default_engine?: string;
  personality?: string | null;
  generation_count: number;
  sample_count: number;
  created_at: string;
  updated_at: string;
}

/** Response returned by /profiles/{id}/compose. */
export interface PersonalityTextResponse {
  text: string;
  model_size: string;
}

export interface PresetVoice {
  voice_id: string;
  name: string;
  gender: 'male' | 'female';
  language: string;
}

export interface ProfileSampleCreate {
  reference_text: string;
}

export interface ProfileSampleResponse {
  id: string;
  profile_id: string;
  audio_path: string;
  reference_text: string;
}

export interface EffectConfig {
  type: string;
  enabled: boolean;
  params: Record<string, number>;
}

export interface GenerationRequest {
  profile_id: string;
  text: string;
  language: LanguageCode;
  seed?: number;
  model_size?: '1.7B' | '0.6B' | '1B' | '3B';
  engine?:
    | 'qwen'
    | 'qwen_custom_voice'
    | 'luxtts'
    | 'chatterbox'
    | 'chatterbox_turbo'
    | 'tada'
    | 'kokoro';
  instruct?: string;
  /** When true and the profile has a personality prompt, input text is rewritten in-character before TTS. */
  personality?: boolean;
  max_chunk_chars?: number;
  crossfade_ms?: number;
  normalize?: boolean;
  effects_chain?: EffectConfig[];
}

export interface GenerationVersionResponse {
  id: string;
  generation_id: string;
  label: string;
  audio_path: string;
  effects_chain?: EffectConfig[];
  source_version_id?: string;
  is_default: boolean;
  created_at: string;
}

export interface GenerationResponse {
  id: string;
  profile_id: string;
  text: string;
  language: string;
  audio_path?: string;
  duration?: number;
  seed?: number;
  instruct?: string;
  engine?: string;
  model_size?: string;
  status: 'loading_model' | 'generating' | 'completed' | 'failed';
  error?: string;
  is_favorited?: boolean;
  created_at: string;
  versions?: GenerationVersionResponse[];
  active_version_id?: string;
}

export interface HistoryQuery {
  profile_id?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface HistoryResponse extends GenerationResponse {
  profile_name: string;
  versions?: GenerationVersionResponse[];
  active_version_id?: string;
}

export interface HistoryListResponse {
  items: HistoryResponse[];
  total: number;
}

export type WhisperModelSize = 'base' | 'small' | 'medium' | 'large' | 'turbo';

export type Qwen3ModelSize = '0.6B' | '1.7B' | '4B';

export type CaptureSource = 'dictation' | 'recording' | 'file';

/**
 * Snapshot of the accessibility-focused UI element at chord-start. Emitted
 * from Rust as part of the ``dictate:start`` payload so the frontend can
 * pass it back to ``paste_final_text`` once the final text is ready.
 */
export interface FocusSnapshot {
  pid: number;
  bundle_id: string | null;
  role: string | null;
}

export interface RefinementFlags {
  smart_cleanup: boolean;
  self_correction: boolean;
  preserve_technical: boolean;
}

export interface CaptureResponse {
  id: string;
  audio_path: string;
  source: CaptureSource;
  language?: string | null;
  duration_ms?: number | null;
  transcript_raw: string;
  transcript_refined?: string | null;
  stt_model?: string | null;
  llm_model?: string | null;
  refinement_flags?: RefinementFlags | null;
  created_at: string;
}

export interface CaptureListResponse {
  items: CaptureResponse[];
  total: number;
}

/**
 * Response of ``POST /captures``. Adds ``auto_refine`` and ``allow_auto_paste``
 * — the server's current settings captured at request time — so the client
 * can decide whether to chain a refine call and whether to fire the
 * synthetic-paste pipeline without relying on its own (possibly stale) copy
 * of capture_settings.
 */
export interface CaptureCreateResponse extends CaptureResponse {
  auto_refine: boolean;
  allow_auto_paste: boolean;
}

export interface CaptureRefineRequest {
  flags?: RefinementFlags;
  model_size?: Qwen3ModelSize;
}

export interface CaptureRetranscribeRequest {
  model?: WhisperModelSize;
  language?: LanguageCode;
}

export interface CaptureSettings {
  stt_model: WhisperModelSize;
  language: string;
  auto_refine: boolean;
  llm_model: Qwen3ModelSize;
  smart_cleanup: boolean;
  self_correction: boolean;
  preserve_technical: boolean;
  allow_auto_paste: boolean;
  default_playback_voice_id: string | null;
  /** Whether the global keyboard hotkey is armed. Off by default — turning
   *  this on triggers the macOS Input Monitoring TCC prompt. */
  hotkey_enabled: boolean;
  /** keytap key names. Defaults are platform-specific right-hand modifiers. */
  chord_push_to_talk_keys: string[];
  /** keytap key names. Toggle adds Space to the platform-specific PTT chord. */
  chord_toggle_to_talk_keys: string[];
}

export type CaptureSettingsUpdate = Partial<CaptureSettings>;

/**
 * One row in the dictation readiness checklist. ``model_name`` is the
 * canonical id understood by ``POST /models/download`` so the UI can wire a
 * one-click "Download" button without a second lookup.
 */
export interface ModelReadiness {
  ready: boolean;
  model_name: string;
  display_name: string;
  size: string;
  size_mb?: number | null;
}

/** Backend half of the dictation readiness check. The frontend combines this
 *  with TCC permission state into the full checklist used by useDictationReadiness. */
export interface CaptureReadinessResponse {
  stt: ModelReadiness;
  llm: ModelReadiness;
}

export interface GenerationSettings {
  max_chunk_chars: number;
  crossfade_ms: number;
  normalize_audio: boolean;
  autoplay_on_generate: boolean;
}

export type GenerationSettingsUpdate = Partial<GenerationSettings>;

export interface AIPlanningSettings {
  provider: string;
  codex_path?: string | null;
  model?: string | null;
  model_reasoning_effort?: string | null;
  timeout_seconds: number;
  output_schema_path?: string | null;
}

export type AIPlanningSettingsUpdate = Partial<AIPlanningSettings>;

export interface AIPlanningTestResponse {
  ready: boolean;
  provider: string;
  message: string;
  prompt: string;
  output_text?: string | null;
  request_id?: string | null;
  error_code?: string | null;
  requested_model?: string | null;
  requested_reasoning_effort?: string | null;
  effective_model?: string | null;
  effective_reasoning_effort?: string | null;
  model_source?: string | null;
  model_verified?: boolean;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  fallback_error_code?: string | null;
}

export interface AIPlanningProviderCheckResponse {
  ready: boolean;
  provider: string;
  message: string;
  codex_path?: string | null;
  version?: string | null;
  request_id?: string | null;
  error_code?: string | null;
  requested_model?: string | null;
  requested_reasoning_effort?: string | null;
  effective_model?: string | null;
  effective_reasoning_effort?: string | null;
  model_source?: string | null;
  model_verified?: boolean;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  fallback_error_code?: string | null;
}

export interface VideoProjectCreate {
  topic: string;
  title?: string | null;
  series_id?: string | null;
  story_episode_id?: string | null;
  episode_number?: number | null;
  episode_title?: string | null;
  language?: string;
  target_language?: VideoLanguage;
  video_purpose?: VideoPurpose;
  dialogue_mode?: DialogueMode | null;
  narration_density?: NarrationDensity | null;
  call_to_action_style?: CallToActionStyle | null;
  target_duration_seconds?: number | null;
  aspect_ratio?: '9:16' | '16:9' | '1:1';
  visual_style?: string | null;
  voice_profile_id?: string | null;
  phase?: 'phase1' | 'phase2';
  default_shot_duration_seconds?: number | null;
  prompt_segment_count?: number | null;
  prompt_segment_duration_seconds?: number | null;
  micro_scenes_per_prompt?: number | null;
  source_blocks?: VideoSourceBlockDraft[];
}

export interface VideoProjectUpdate {
  title?: string;
  topic?: string;
  series_id?: string | null;
  story_episode_id?: string | null;
  episode_number?: number | null;
  episode_title?: string | null;
  language?: string;
  target_language?: VideoLanguage;
  video_purpose?: VideoPurpose | null;
  dialogue_mode?: DialogueMode | null;
  narration_density?: NarrationDensity | null;
  call_to_action_style?: CallToActionStyle | null;
  target_duration_seconds?: number | null;
  aspect_ratio?: '9:16' | '16:9' | '1:1';
  visual_style?: string | null;
  voice_profile_id?: string | null;
  default_shot_duration_seconds?: number | null;
  prompt_segment_count?: number | null;
  prompt_segment_duration_seconds?: number | null;
  micro_scenes_per_prompt?: number | null;
  continuity_bible?: string | null;
}

export interface VideoSourceBlockDraft {
  block_type: string;
  content: string;
}

export interface VideoSourceBlockCreate extends VideoSourceBlockDraft {
  sort_order?: number | null;
}

export interface VideoSourceBlockUpdate {
  block_type?: string;
  content?: string;
  sort_order?: number;
}

export interface VideoSourceBlockResponse {
  id: string;
  project_id: string;
  block_type: string;
  sort_order: number;
  content: string;
  created_at: string;
  updated_at: string;
}

export type SeriesMode = 'image_story_only' | 'video_story_only' | 'hybrid';
export type StoryOutputIntent = 'truyen_anh' | 'video_truyen' | 'ca_hai';

export interface SeriesCharacterProfileCreate {
  name: string;
  role?: string | null;
  face_description?: string | null;
  hair_description?: string | null;
  body_description?: string | null;
  signature_outfit?: string | null;
  personality?: string | null;
  speech_style?: string | null;
  fixed_traits?: string | null;
  additional_notes?: string | null;
  sort_order?: number | null;
}

export interface SeriesCharacterProfileUpdate extends Partial<SeriesCharacterProfileCreate> {}

export interface SeriesCharacterProfileResponse extends SeriesCharacterProfileCreate {
  id: string;
  series_id: string;
  sort_order: number;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface SeriesCharacterProfileSuggestionResponse {
  profiles: SeriesCharacterProfileCreate[];
  source: string;
  saved: boolean;
  message: string;
}

export type SeriesMemoryCardType =
  | 'series_identity'
  | 'character_context'
  | 'relationship'
  | 'location'
  | 'prop'
  | 'story_thread'
  | 'canon_rule'
  | 'visual_style'
  | 'episode_summary'
  | 'arc_summary'
  | 'series_summary'
  | 'reviewed_note';

export type SeriesMemoryStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'archived';

export type SeriesContextTaskType =
  | 'story_candidate'
  | 'master_story'
  | 'image_panel_prompt'
  | 'video_story_development'
  | 'shot_breakdown'
  | 'video_prompt'
  | 'voice'
  | 'subtitle';

export type SeriesCanonPromptKind = 'image_panel_prompt' | 'video_prompt' | 'story_candidate' | 'master_story' | 'manual';

export interface SeriesMemoryCardCreate {
  card_type: SeriesMemoryCardType;
  title: string;
  content?: Record<string, unknown>;
  tags?: string[];
  entity_refs?: Array<Record<string, unknown>>;
  importance?: number;
  status?: SeriesMemoryStatus;
  effective_from_episode?: number | null;
  effective_to_episode?: number | null;
  source_type?: string | null;
  source_id?: string | null;
}

export interface SeriesMemoryCardUpdate extends Partial<SeriesMemoryCardCreate> {}

export interface SeriesMemoryCardStatusRequest {
  status: SeriesMemoryStatus;
}

export interface SeriesMemoryCardResponse extends Required<Pick<SeriesMemoryCardCreate, 'card_type' | 'title'>> {
  id: string;
  series_id: string;
  content: Record<string, unknown>;
  tags: string[];
  entity_refs: Array<Record<string, unknown>>;
  importance: number;
  status: SeriesMemoryStatus;
  effective_from_episode?: number | null;
  effective_to_episode?: number | null;
  source_type?: string | null;
  source_id?: string | null;
  revision: number;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SeriesMemoryCardListResponse {
  items: SeriesMemoryCardResponse[];
  total: number;
}

export interface SeriesMemorySuggestionRequest {
  include_legacy_bible?: boolean;
  include_latest_summary?: boolean;
  save_drafts?: boolean;
}

export interface SeriesMemorySuggestionResponse {
  cards: SeriesMemoryCardCreate[];
  saved: boolean;
  message: string;
}

export interface SeriesCurrentStateCreate {
  based_on_episode_number?: number;
  character_states?: Record<string, unknown>;
  relationship_states?: Record<string, unknown>;
  location_states?: Record<string, unknown>;
  prop_states?: Record<string, unknown>;
  open_threads?: Array<Record<string, unknown>>;
  unresolved_conflicts?: Array<Record<string, unknown>>;
  approval_status?: SeriesMemoryStatus;
  source_type?: string | null;
  source_id?: string | null;
}

export interface SeriesCurrentStateUpdate extends Partial<SeriesCurrentStateCreate> {}

export interface SeriesCurrentStateStatusRequest {
  approval_status: SeriesMemoryStatus;
}

export interface SeriesCurrentStateResponse {
  id: string;
  series_id: string;
  based_on_episode_number: number;
  character_states: Record<string, unknown>;
  relationship_states: Record<string, unknown>;
  location_states: Record<string, unknown>;
  prop_states: Record<string, unknown>;
  open_threads: Array<Record<string, unknown>>;
  unresolved_conflicts: Array<Record<string, unknown>>;
  approval_status: SeriesMemoryStatus;
  source_type?: string | null;
  source_id?: string | null;
  revision: number;
  previous_state_id?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SeriesCurrentStateListResponse {
  items: SeriesCurrentStateResponse[];
  total: number;
}

export type SeriesReferenceEntityType = 'character' | 'location';
export type SeriesReferenceApprovalStatus = 'pending_approval' | 'approved' | 'rejected' | 'archived';
export type SeriesReferenceRole =
  | 'face_front'
  | 'face_side'
  | 'full_body'
  | 'signature_outfit'
  | 'expression'
  | 'wide_view'
  | 'entrance'
  | 'interior'
  | 'landmark_detail'
  | 'lighting_reference'
  | 'other';

export interface SeriesReferenceAssetResponse {
  id: string;
  series_id: string;
  entity_type: SeriesReferenceEntityType | string;
  entity_id: string;
  reference_role: SeriesReferenceRole | string;
  label?: string | null;
  asset_path: string;
  thumbnail_path?: string | null;
  provider_asset_id?: string | null;
  original_filename?: string | null;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  file_size_bytes?: number | null;
  checksum: string;
  source_type?: string | null;
  approval_status: SeriesReferenceApprovalStatus | string;
  revision: number;
  active: boolean;
  metadata: Record<string, unknown>;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface SeriesReferenceAssetListResponse {
  items: SeriesReferenceAssetResponse[];
  total: number;
}

export interface SeriesReferenceAssetStatusRequest {
  approval_status?: SeriesReferenceApprovalStatus | null;
  active?: boolean | null;
  reason?: string | null;
  changed_by?: string | null;
}

export interface SeriesReferenceProviderReport {
  provider: string;
  provider_supports_references: boolean;
  sent: Array<Record<string, unknown>>;
  skipped: Array<Record<string, unknown>>;
  fallback_text?: string | null;
}

export interface ArtifactDependencyInput {
  dependency_type: string;
  dependency_id: string;
  dependency_revision?: number;
  dependency_scope:
    | 'visual_identity'
    | 'story_state'
    | 'dialogue'
    | 'language'
    | 'camera_style'
    | 'reference_image'
    | 'style'
    | 'narration'
    | 'voice_profile'
    | 'timing'
    | 'package'
    | string;
  metadata?: Record<string, unknown>;
}

export interface ArtifactDependencyRecordRequest {
  artifact_type: string;
  artifact_id: string;
  artifact_revision?: number;
  dependencies?: ArtifactDependencyInput[];
}

export interface ArtifactDependencySnapshotResponse {
  id: string;
  series_id: string;
  artifact_type: string;
  artifact_id: string;
  artifact_revision: number;
  dependency_type: string;
  dependency_id: string;
  dependency_revision: number;
  dependency_scope: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ArtifactStaleEventResponse {
  id: string;
  series_id: string;
  artifact_type: string;
  artifact_id: string;
  artifact_revision: number;
  dependency_type: string;
  dependency_id: string;
  old_revision?: number | null;
  new_revision?: number | null;
  changed_scope: string;
  dependency_scope: string;
  reason_vi: string;
  propagation_rule: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  resolved_at?: string | null;
}

export interface ArtifactStaleEventListResponse {
  items: ArtifactStaleEventResponse[];
  total: number;
}

export interface ArtifactStaleMarkRequest {
  dependency_type: string;
  dependency_id: string;
  old_revision?: number | null;
  new_revision?: number | null;
  changed_scope: string;
  reason_vi?: string | null;
}

export interface ArtifactTargetedRegenerationRequest {
  event_ids?: string[] | null;
  artifact_type?: string | null;
  artifact_id?: string | null;
}

export interface ArtifactTargetedRegenerationResponse {
  requested: number;
  artifacts: Array<Record<string, unknown>>;
  message: string;
}

export interface SeriesVersionRecordResponse {
  id: string;
  series_id: string;
  entity_type: string;
  entity_id: string;
  revision: number;
  snapshot: Record<string, unknown>;
  changed_by?: string | null;
  change_source?: string | null;
  change_reason?: string | null;
  created_at: string;
}

export interface SeriesVersionHistoryResponse {
  items: SeriesVersionRecordResponse[];
  total: number;
  diff_vi: string[];
}

export interface SeriesStateProposalRequest {
  source_type?: string;
  source_id?: string | null;
  based_on_episode_number?: number | null;
  notes?: string | null;
}

export interface SeriesContextCompileRequest {
  task_type: SeriesContextTaskType;
  episode_number?: number | null;
  project_id?: string | null;
  story_episode_id?: string | null;
  target_ref_type?: string | null;
  target_ref_id?: string | null;
  user_input?: string | null;
  current_payload?: Record<string, unknown>;
  entity_refs?: string[];
  tags?: string[];
  max_chars?: number;
  persist_trace?: boolean;
}

export interface SeriesContextCompileResponse {
  trace_id?: string | null;
  series_id: string;
  task_type: SeriesContextTaskType | string;
  context_text: string;
  selected_cards: Array<Record<string, unknown>>;
  selected_character_profiles: Array<Record<string, unknown>>;
  group_usage: Array<Record<string, unknown>>;
  missing_required: string[];
  truncated_groups: string[];
  context_stats: Record<string, unknown>;
}

export interface SeriesContextTraceResponse {
  id: string;
  series_id: string;
  project_id?: string | null;
  story_episode_id?: string | null;
  task_type: SeriesContextTaskType | string;
  target_ref_type?: string | null;
  target_ref_id?: string | null;
  selected_cards: Array<Record<string, unknown>>;
  selected_character_profiles: Array<Record<string, unknown>>;
  group_budget: Array<Record<string, unknown>>;
  missing_required: string[];
  truncated_groups: string[];
  context_stats: Record<string, unknown>;
  reasons: Array<Record<string, unknown>>;
  context_preview?: string | null;
  created_at: string;
}

export interface SeriesContextTraceListResponse {
  items: SeriesContextTraceResponse[];
  total: number;
}

export interface SeriesCanonCheckRequest {
  prompt: string;
  prompt_kind?: SeriesCanonPromptKind;
  prompt_ref_id?: string | null;
  project_id?: string | null;
  story_episode_id?: string | null;
  allow_override?: boolean;
  override_reason?: string | null;
}

export interface SeriesCanonCheckResponse {
  id?: string | null;
  series_id: string;
  prompt_kind: SeriesCanonPromptKind | string;
  prompt_ref_id?: string | null;
  passed: boolean;
  blocking_conflicts: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  evidence_card_ids: string[];
  suggestions: string[];
  override_reason?: string | null;
  created_at?: string | null;
}

export interface VideoSeriesCreate {
  title: string;
  series_mode?: SeriesMode;
  character_bible?: string | null;
  world_bible?: string | null;
  style_bible?: string | null;
  continuity_rules?: string | null;
  negative_rules?: string | null;
  previous_episode_summary?: string | null;
}

export interface VideoSeriesUpdate {
  title?: string;
  character_bible?: string | null;
  world_bible?: string | null;
  style_bible?: string | null;
  continuity_rules?: string | null;
  negative_rules?: string | null;
  previous_episode_summary?: string | null;
  latest_episode_number?: number | null;
}

export interface VideoSeriesResponse {
  id: string;
  title: string;
  series_mode: SeriesMode;
  character_bible?: string | null;
  world_bible?: string | null;
  style_bible?: string | null;
  continuity_rules?: string | null;
  negative_rules?: string | null;
  previous_episode_summary?: string | null;
  latest_episode_number: number;
  revision: number;
  episode_count: number;
  story_episode_count: number;
  video_episode_count: number;
  character_profiles: SeriesCharacterProfileResponse[];
  provider_project_binding?: VideoProviderProjectBindingResponse | null;
  created_at: string;
  updated_at: string;
}

export interface VideoEpisodeCreate {
  topic: string;
  episode_title?: string | null;
  episode_number?: number | null;
  title?: string | null;
  language?: string;
  target_language?: VideoLanguage | null;
  video_purpose?: VideoPurpose | null;
  dialogue_mode?: DialogueMode | null;
  narration_density?: NarrationDensity | null;
  call_to_action_style?: CallToActionStyle | null;
  target_duration_seconds?: number | null;
  aspect_ratio?: '9:16' | '16:9' | '1:1' | null;
  visual_style?: string | null;
  voice_profile_id?: string | null;
  phase?: 'phase1' | 'phase2';
  default_shot_duration_seconds?: number | null;
  prompt_segment_count?: number | null;
  prompt_segment_duration_seconds?: number | null;
  micro_scenes_per_prompt?: number | null;
  source_blocks?: VideoSourceBlockDraft[];
  reuse_latest_config?: boolean;
}

export interface StoryScenarioCandidateResponse {
  id: string;
  story_episode_id: string;
  strategy_type: string;
  script_json: Record<string, unknown>;
  score_json?: Record<string, unknown> | null;
  strengths?: string | null;
  risks?: string | null;
  context_snapshot_id?: string | null;
  model_label?: string | null;
  generation_attempt: number;
  generation_status: string;
  generation_metadata_json?: Record<string, unknown> | null;
  evaluation_status: string;
  evaluation_json?: Record<string, unknown> | null;
  selected: boolean;
  created_at: string;
  updated_at: string;
}

export interface StoryAdaptationResponse {
  id: string;
  story_episode_id: string;
  kind: 'image_story' | 'video_story';
  status: string;
  payload_json?: Record<string, unknown> | null;
  linked_video_project_id?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export type StoryVideoHandoffSourceMode = 'auto' | 'master_story' | 'image_story_prompts';

export interface StoryVideoHandoffRequest {
  open_existing?: boolean;
  source_mode?: StoryVideoHandoffSourceMode;
  start_auto_run?: boolean;
  material_target?: 'prompts_only' | 'full_materials';
}

export type StoryImagePanelMode = 'auto' | 'manual';
export type StoryImageAspectRatio = '9:16' | '16:9' | '1:1' | '4:5';
export type StoryVideoAspectRatio = '9:16' | '16:9' | '1:1';

export interface StoryImageOutputSettings {
  panel_mode: StoryImagePanelMode;
  panel_count?: number | null;
  aspect_ratio: StoryImageAspectRatio;
  width: number;
  height: number;
}

export interface StoryVideoHandoffSettings {
  handoff_only: boolean;
  aspect_ratio: StoryVideoAspectRatio;
  target_language: VideoLanguage;
  video_purpose: VideoPurpose;
  dialogue_mode: DialogueMode;
  narration_density: NarrationDensity;
  call_to_action_style?: CallToActionStyle | null;
  target_duration_seconds?: number | null;
  default_shot_duration_seconds?: number | null;
  prompt_segment_count?: number | null;
  prompt_segment_duration_seconds?: number | null;
  micro_scenes_per_prompt?: number | null;
}

export interface StoryEpisodeOutputSettings {
  image: StoryImageOutputSettings;
  video: StoryVideoHandoffSettings;
}

export interface StoryEpisodeSourceSummaryResponse {
  source_document_id?: string | null;
  revision?: number | null;
  source_kind?: string | null;
  comic_job_id?: string | null;
  comic_analysis_revision?: number | null;
  chunk_count: number;
  page_count: number;
  panel_count: number;
  dialogue_count: number;
  coverage_metrics?: Record<string, unknown> | null;
  limitations?: unknown[] | null;
  has_structured_source: boolean;
}

export interface StoryEpisodeResponse {
  id: string;
  series_id: string;
  episode_number: number;
  title?: string | null;
  output_intent: StoryOutputIntent;
  market_profile: string;
  language_profile: string;
  source_input?: string | null;
  source_digest?: string | null;
  current_source_document_id?: string | null;
  source_summary: StoryEpisodeSourceSummaryResponse;
  output_settings: StoryEpisodeOutputSettings;
  master_story_json?: Record<string, unknown> | null;
  selection_reason?: string | null;
  approval_status: string;
  approved_at?: string | null;
  revision: number;
  candidates: StoryScenarioCandidateResponse[];
  adaptations: StoryAdaptationResponse[];
  created_at: string;
  updated_at: string;
}

export interface StoryEpisodeCreate {
  episode_number?: number | null;
  title?: string | null;
  output_intent?: StoryOutputIntent;
  market_profile?: string;
  language_profile?: string;
  source_input?: string | null;
  output_settings?: StoryEpisodeOutputSettings;
}

export interface StoryEpisodeUpdate {
  title?: string | null;
  output_intent?: StoryOutputIntent;
  market_profile?: string;
  language_profile?: string;
  source_input?: string | null;
  output_settings?: StoryEpisodeOutputSettings | null;
  master_story_json?: Record<string, unknown> | null;
  selection_reason?: string | null;
}

export interface StoryCandidateSelectionRequest {
  candidate_id?: string | null;
  master_story_json?: Record<string, unknown> | null;
  selection_reason?: string | null;
}

export interface StoryCandidateSynthesisRequest {
  candidate_ids?: string[] | null;
  user_direction?: string | null;
}

export interface StoryApprovalRequest {
  approved: boolean;
}

export interface StoryPanelPromptApprovalRequest {
  panel_orders?: number[] | null;
  approved?: boolean;
  canon_override_reason?: string | null;
}

export interface StoryPanelPromptUpdateRequest {
  panel_order: number;
  prompt?: string | null;
  negative_prompt?: string | null;
  caption_or_dialogue?: string | null;
  visual_description?: string | null;
}

export interface StoryPromptRepairRequest {
  panel_order: number;
  max_attempts?: number;
}

export interface StoryImageRenderRequest {
  panel_orders?: number[] | null;
  image_provider_configured?: boolean;
  provider?: string;
  provider_metadata?: Record<string, unknown>;
}

export interface StoryImageRenderResult {
  panel_order: number;
  status?: 'completed' | 'failed';
  image_path?: string | null;
  image_url?: string | null;
  provider_asset_id?: string | null;
  provider_metadata?: Record<string, unknown>;
  failure_reason?: string | null;
}

export interface StoryImageRenderJobUpdateRequest {
  status: 'queued' | 'rendering' | 'completed' | 'failed';
  results?: StoryImageRenderResult[];
  message?: string | null;
}

export interface StorySuggestionResponse {
  suggestions: Array<Record<string, unknown>>;
  saved: boolean;
  message: string;
}

export interface StorySuggestionApprovalRequest {
  approved: boolean;
  suggestions?: Array<Record<string, unknown>>;
}

export interface VideoGeneratedDataResetResponse {
  project_id: string;
  message: string;
  deleted_counts: Record<string, number>;
}

export interface VideoProjectLocalizeRequest {
  target_language: VideoLanguage;
  video_purpose?: VideoPurpose;
  dialogue_mode?: DialogueMode | null;
  narration_density?: NarrationDensity | null;
  call_to_action_style?: CallToActionStyle | null;
  title?: string | null;
  voice_profile_id?: string | null;
}

export interface VideoProjectResponse {
  id: string;
  series_id?: string | null;
  story_episode_id?: string | null;
  episode_number?: number | null;
  episode_title?: string | null;
  series_title?: string | null;
  title: string;
  topic: string;
  language: string;
  target_language: VideoLanguage;
  video_purpose: VideoPurpose;
  dialogue_mode: DialogueMode;
  narration_density: NarrationDensity;
  call_to_action_style?: CallToActionStyle | null;
  target_duration_seconds?: number | null;
  aspect_ratio: string;
  visual_style?: string | null;
  voice_profile_id?: string | null;
  status: string;
  script_approved: boolean;
  story_approved: boolean;
  phase: 'phase1' | 'phase2';
  default_shot_duration_seconds?: number | null;
  prompt_segment_count?: number | null;
  prompt_segment_duration_seconds?: number | null;
  micro_scenes_per_prompt?: number | null;
  planning_status: string;
  planning_error?: string | null;
  last_request_id?: string | null;
  active_run_status?: VideoAutoRunStatus | null;
  active_run_step?: VideoAutoRunStep | null;
  active_run_progress?: number | null;
  provider_project_binding?: VideoProviderProjectBindingResponse | null;
  package_stale: boolean;
  scene_count: number;
  shot_count: number;
  created_at: string;
  updated_at: string;
}

export interface VideoSceneResponse {
  id: string;
  project_id: string;
  scene_order: number;
  title?: string | null;
  dialogue: string;
  visual_description?: string | null;
  target_duration_seconds?: number | null;
  approved: boolean;
  no_narration: boolean;
  prompt_status: string;
  voice_status: string;
  subtitle_status: string;
  generation_id?: string | null;
  audio_path?: string | null;
  audio_duration?: number | null;
  voice_failure_reason?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface VideoProjectDetailResponse extends VideoProjectResponse {
  creative_brief?: string | null;
  script_text?: string | null;
  style_bible?: string | null;
  character_bible?: string | null;
  input_synthesis?: string | null;
  story_strategy?: string | null;
  continuity_bible?: string | null;
  detailed_script?: string | null;
  retention_plan_json?: Record<string, unknown> | null;
  sound_design_plan_json?: Record<string, unknown> | null;
  source_blocks: VideoSourceBlockResponse[];
  scenes: VideoSceneResponse[];
  shots: VideoShotResponse[];
}

export interface VideoShotMicroScene {
  order: number;
  start_seconds: number;
  end_seconds: number;
  description_vi: string;
  visual_action: string;
  camera_note: string;
  continuity_note?: string | null;
}

export interface VideoShotResponse {
  id: string;
  project_id: string;
  scene_id?: string | null;
  shot_order: number;
  duration_seconds?: number | null;
  vietnamese_description?: string | null;
  english_narration?: string | null;
  primary_action?: string | null;
  purpose?: string | null;
  shot_type?: string | null;
  camera_angle?: string | null;
  framing?: string | null;
  composition?: string | null;
  camera_motion?: string | null;
  subject_motion?: string | null;
  environment_motion?: string | null;
  transition_to_next?: string | null;
  retention_json?: Record<string, unknown> | null;
  transition_json?: Record<string, unknown> | null;
  sound_design_json?: Record<string, unknown> | null;
  micro_scenes?: VideoShotMicroScene[] | null;
  retainability_quality_check?: Record<string, unknown> | null;
  locked: boolean;
  status: string;
  prompt_status: string;
  voice_status: string;
  subtitle_status: string;
  generation_id?: string | null;
  audio_path?: string | null;
  audio_duration?: number | null;
  voice_failure_reason?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface VideoShotPromptResponse {
  id: string;
  project_id: string;
  scene_id?: string | null;
  shot_id: string;
  version: number;
  prompt: string;
  prompt_explanation_vi?: string | null;
  negative_prompt?: string | null;
  duration_seconds?: number | null;
  aspect_ratio?: string | null;
  camera_motion?: string | null;
  subject_motion?: string | null;
  environment_motion?: string | null;
  start_frame?: string | null;
  end_frame?: string | null;
  lighting?: string | null;
  mood?: string | null;
  style_notes?: string | null;
  continuity_notes?: string | null;
  retention_notes?: string | null;
  transition_notes?: string | null;
  sound_design_notes?: string | null;
  quality_status: string;
  quality_check?: Record<string, unknown> | null;
  prompt_path?: string | null;
  created_at: string;
}

export interface VideoProjectStatusResponse {
  project_id: string;
  planning_active: boolean;
  planning_active_step?: string | null;
  missing_script: boolean;
  missing_prompt: boolean;
  missing_voice: boolean;
  missing_subtitle: boolean;
  package_stale: boolean;
  package_ready: boolean;
  missing_scene_ids: string[];
  story_approved: boolean;
  missing_source_blocks: boolean;
  missing_shots: boolean;
  missing_video_prompt_shot_ids: string[];
  stale_prompt_shot_ids: string[];
  missing_voice_shot_ids: string[];
  publishing_metadata_status: string;
  publishing_metadata_ready: boolean;
  publishing_metadata_stale: boolean;
  publishing_metadata_revision?: number | null;
}

export interface VideoPromptContentResponse {
  project_id: string;
  scene_id?: string | null;
  shot_id?: string | null;
  prompt_id: string;
  filename: string;
  content: string;
  prompt_explanation_vi?: string | null;
  negative_prompt?: string | null;
  retention_notes?: string | null;
  transition_notes?: string | null;
  sound_design_notes?: string | null;
}

export type VideoPublishingPlatform = 'youtube' | 'tiktok' | 'facebook';
export type VideoPublishingGeneratePlatform = 'all' | VideoPublishingPlatform;

export interface VideoPublishingPlatformContent {
  title: string;
  description: string;
  hashtags: string[];
  thumbnail_prompt: string;
  status: string;
  input_fingerprint?: string | null;
  revision: number;
}

export interface VideoPublishingMetadataGenerateRequest {
  platform?: VideoPublishingGeneratePlatform;
  force?: boolean;
}

export interface VideoPublishingMetadataResponse {
  id?: string | null;
  project_id: string;
  status: string;
  target_language: VideoLanguage;
  platforms: Partial<Record<VideoPublishingPlatform, VideoPublishingPlatformContent>>;
  input_fingerprint?: string | null;
  revision: number;
  stale: boolean;
  failure_reason?: string | null;
  error_code?: string | null;
  request_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface VideoSceneAssetResponse {
  id: string;
  project_id: string;
  scene_id: string;
  asset_type: string;
  file_path: string;
  original_filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  is_active: boolean;
  created_at: string;
}

export interface VideoSceneVoiceStatusResponse {
  project_id: string;
  scene_id: string;
  scene_order: number;
  no_narration: boolean;
  voice_status: string;
  generation_id?: string | null;
  audio_path?: string | null;
  audio_url?: string | null;
  audio_duration?: number | null;
  failure_reason?: string | null;
}

export interface VideoShotVoiceStatusResponse {
  project_id: string;
  shot_id: string;
  shot_order: number;
  scene_id?: string | null;
  voice_status: string;
  generation_id?: string | null;
  audio_path?: string | null;
  audio_url?: string | null;
  audio_duration?: number | null;
  failure_reason?: string | null;
}

export interface VideoSceneNarrationRequest {
  profile_id?: string | null;
  language?: LanguageCode;
  seed?: number | null;
  model_size?: '1.7B' | '0.6B' | '1B' | '3B';
  engine?: GenerationRequest['engine'];
  instruct?: string | null;
  normalize?: boolean;
  max_chunk_chars?: number;
  crossfade_ms?: number;
  force?: boolean;
}

export interface VideoSubtitleCue {
  index: number;
  scene_id?: string | null;
  scene_order?: number | null;
  shot_id?: string | null;
  shot_order?: number | null;
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface VideoSubtitleResponse {
  id: string;
  project_id: string;
  status: string;
  subtitle_path?: string | null;
  format: string;
  cues: VideoSubtitleCue[];
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface VideoPackageReadinessResponse {
  project_id: string;
  language: VideoLanguage;
  video_purpose: VideoPurpose;
  dialogue_mode: DialogueMode;
  narration_density: NarrationDensity;
  ready: boolean;
  missing_prompt_scene_ids: string[];
  missing_video_prompt_shot_ids: string[];
  missing_voice_scene_ids: string[];
  missing_voice_shot_ids: string[];
  missing_subtitle: boolean;
  missing_reasons: string[];
}

export interface VideoShotPromptPackResponse {
  project_id: string;
  prompts: VideoShotPromptResponse[];
}

export interface VideoShotClipResponse {
  id: string;
  project_id: string;
  shot_id: string;
  source: string;
  status: string;
  file_path: string;
  original_filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  duration_seconds?: number | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  codec?: string | null;
  has_audio: boolean;
  is_active: boolean;
  failure_reason?: string | null;
  provider?: string | null;
  provider_asset_id?: string | null;
  provider_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface VideoRenderSettings {
  resolution: 'auto' | '720p' | '1080p';
  fps: number;
  fit_mode: 'crop' | 'pad';
  duration_mode: 'freeze' | 'trim_only';
  subtitle_mode: 'burn_in' | 'sidecar' | 'none';
  mute_clip_audio: boolean;
  background_color?: string;
  force?: boolean;
  enhanced_render?: boolean;
  enhanced_audio?: boolean;
  ai_review?: boolean;
  max_fix_attempts?: number;
}

export interface VideoRenderWarning {
  shot_id?: string | null;
  code: string;
  message: string;
}

export interface VideoRenderReadinessResponse {
  project_id: string;
  ready: boolean;
  ffmpeg_ready: boolean;
  ffprobe_ready: boolean;
  missing_clip_shot_ids: string[];
  invalid_clip_shot_ids: string[];
  missing_voice_shot_ids: string[];
  missing_timer_shot_ids: string[];
  missing_subtitle: boolean;
  stale_output: boolean;
  missing_reasons: string[];
  warnings: VideoRenderWarning[];
}

export interface VideoRenderSfxAssetResponse {
  asset_id: string;
  filename: string;
  file_path: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  duration_seconds?: number | null;
  cue_aliases: string[];
  status: string;
  failure_reason?: string | null;
}

export interface VideoEnhancedRenderArtifactResponse {
  filename: string;
  path?: string | null;
  kind: string;
}

export interface VideoRenderJobResponse {
  id: string;
  project_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_step?: string | null;
  settings_json?: string | null;
  readiness_json?: string | null;
  timeline_manifest_path?: string | null;
  enhanced_plan_path?: string | null;
  review_report_path?: string | null;
  enhanced_artifacts_json?: {
    enhanced_plan?: string | null;
    items?: VideoEnhancedRenderArtifactResponse[];
  } | null;
  review_status?: string | null;
  fix_attempt_count?: number;
  output_path?: string | null;
  subtitle_ass_path?: string | null;
  stale: boolean;
  failure_reason?: string | null;
  error_code?: string | null;
  technical_details?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type VideoProviderSessionStatus =
  | 'not_configured'
  | 'needs_login'
  | 'checking'
  | 'ready'
  | 'invalid';
export type VideoProviderIdentityStatus = 'unknown' | 'detected' | 'confirmed' | 'mismatch' | 'needs_user_action';

export interface VideoProviderSessionResponse {
  id: string;
  provider: 'veo';
  provider_tool?: string | null;
  status: VideoProviderSessionStatus | string;
  is_default: boolean;
  connection_label?: string | null;
  verified_account_hint?: string | null;
  identity_status: VideoProviderIdentityStatus | string;
  identity_verified_at?: string | null;
  last_checked_at?: string | null;
  failure_reason?: string | null;
  chrome_profile_configured: boolean;
  created_at: string;
  updated_at: string;
}

export interface VideoProviderSessionOpenRequest {
  provider?: 'veo';
  change_account?: boolean;
}

export interface VideoProviderSessionLabelUpdate {
  connection_label: string;
}

export type VideoProviderProjectBindingStatus = 'active' | 'needs_check' | 'invalid' | 'rotated';

export interface VideoProviderProjectBindingResponse {
  id: string;
  scope: 'project' | 'series' | string;
  scope_id: string;
  project_id?: string | null;
  series_id?: string | null;
  provider: 'veo' | string;
  provider_tool: string;
  provider_project_ref_hash: string;
  status: VideoProviderProjectBindingStatus | string;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  failure_reason?: string | null;
  observed_model_label?: string | null;
  observed_model_cost_label?: string | null;
  model_selection_mode: 'use_current_flow_selection' | string;
  allow_automatic_model_change: boolean;
  created_at: string;
  updated_at: string;
}

export interface VideoCodexRepairAttemptResponse {
  id: string;
  job_id: string;
  item_id?: string | null;
  project_id: string;
  status: string;
  error_code: string;
  step_name?: string | null;
  repair_context_json?: Record<string, unknown> | null;
  files_changed_json?: Record<string, unknown> | null;
  tests_run_json?: Record<string, unknown> | null;
  test_result?: string | null;
  failure_reason?: string | null;
  requires_approval: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export type VideoClipGenerationStatus =
  | 'queued'
  | 'running'
  | 'needs_login'
  | 'needs_user_action'
  | 'needs_credit_approval'
  | 'paused_for_repair'
  | 'completed'
  | 'completed_with_render_blocked'
  | 'failed'
  | 'cancelled';

export type VideoClipGenerationItemStatus =
  | 'pending'
  | 'opening_provider'
  | 'submitting_prompt'
  | 'resolving_followup'
  | 'credit_policy_check'
  | 'approving_credit'
  | 'waiting_generation'
  | 'downloading'
  | 'importing'
  | 'completed'
  | 'skipped'
  | 'needs_credit_approval'
  | 'needs_login'
  | 'needs_user_action'
  | 'paused_for_repair'
  | 'failed'
  | 'cancelled';

export interface VideoClipGenerationItemResponse {
  id: string;
  job_id: string;
  project_id: string;
  shot_id: string;
  shot_order: number;
  prompt_id?: string | null;
  status: VideoClipGenerationItemStatus | string;
  attempt_count: number;
  credit_cost?: number | null;
  provider_duration_seconds?: number | null;
  provider_asset_id?: string | null;
  provider_project_ref_hash?: string | null;
  observed_model_label?: string | null;
  observed_model_cost_label?: string | null;
  download_correlation_id?: string | null;
  download_url_hash?: string | null;
  original_filename?: string | null;
  downloaded_file_path?: string | null;
  clip_id?: string | null;
  failure_reason?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoClipGenerationSummary {
  total_items: number;
  pending_items: number;
  active_items: number;
  completed_items: number;
  skipped_items: number;
  failed_items: number;
  needs_login_items: number;
  needs_user_action_items: number;
  needs_credit_approval_items: number;
  paused_for_repair_items: number;
  credit_spent_estimate: number;
  render_ready: boolean;
  render_missing_reasons: string[];
}

export interface VideoClipGenerationJobStartRequest {
  session_id?: string | null;
  force?: boolean;
  auto_render?: boolean;
  enable_codex_repair?: boolean;
  credit_approval_policy?: 'approve_dont_ask_again' | 'manual_per_item';
  max_credit_per_job?: number | null;
  confirm_identity?: boolean;
}

export interface VideoClipGenerationRetryRequest {
  force?: boolean;
}

export interface VideoClipGenerationResumeRequest {
  confirm_identity?: boolean;
}

export interface VideoClipGenerationCreditApprovalRequest {
  approve?: boolean;
}

export interface VideoClipGenerationJobResponse {
  id: string;
  project_id: string;
  provider: 'veo';
  session_id: string;
  status: VideoClipGenerationStatus | string;
  current_step: string;
  progress: number;
  force: boolean;
  auto_render: boolean;
  enable_codex_repair: boolean;
  credit_approval_policy: 'approve_dont_ask_again' | 'manual_per_item' | string;
  max_credit_per_job?: number | null;
  credit_spent_estimate: number;
  render_job_id?: string | null;
  repair_status?: string | null;
  repair_attempt_count: number;
  repair_report_json?: Record<string, unknown> | null;
  failure_reason?: string | null;
  error_code?: string | null;
  step_results_json?: Record<string, unknown> | null;
  provider_project_binding?: VideoProviderProjectBindingResponse | null;
  repair_attempts: VideoCodexRepairAttemptResponse[];
  items: VideoClipGenerationItemResponse[];
  summary: VideoClipGenerationSummary;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoPackageExportResponse {
  id: string;
  project_id: string;
  status: string;
  manifest_path?: string | null;
  zip_path?: string | null;
  stale: boolean;
  failure_reason?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export type VideoAutoRunMode = 'review_gated' | 'full_auto';
export type VideoAutoRunMaterialTarget =
  | 'full_materials'
  | 'prompts_only'
  | 'publishing_kit'
  | 'video_clips';
export type VideoAutoRunStatus =
  | 'queued'
  | 'running'
  | 'waiting_workflow'
  | 'waiting_planning'
  | 'waiting_voice'
  | 'waiting_clips'
  | 'waiting_render'
  | 'needs_review'
  | 'needs_input'
  | 'completed'
  | 'failed'
  | 'cancelled';
export type VideoAutoRunStep =
  | 'validate'
  | 'waiting_workflow'
  | 'develop_story'
  | 'waiting_planning'
  | 'review_story'
  | 'generate_shots'
  | 'generate_prompts'
  | 'generate_publishing_metadata'
  | 'review_prompts'
  | 'generate_clips'
  | 'waiting_clips'
  | 'generate_voice'
  | 'waiting_voice'
  | 'generate_subtitle'
  | 'generate_render'
  | 'waiting_render'
  | 'completed';
export type VideoAutoRunReviewStage = 'story' | 'prompts';

export interface VideoAutoRunStartRequest {
  mode?: VideoAutoRunMode;
  material_target?: VideoAutoRunMaterialTarget;
  force?: boolean;
}

export interface VideoAutoRunContinueRequest {
  approved?: boolean;
}

export interface VideoAutoRunRetryRequest {
  force?: boolean;
}

export interface VideoAutoRunSummary {
  shot_count: number;
  prompt_completed_count: number;
  prompt_required_count: number;
  voice_completed_count: number;
  voice_required_count: number;
  clip_completed_count: number;
  clip_required_count: number;
  clip_generation_job_id?: string | null;
  clip_generation_status?: string | null;
  clip_generation_error_code?: string | null;
  clip_generation_failure_reason?: string | null;
  render_job_id?: string | null;
  render_job_status?: string | null;
  render_job_error_code?: string | null;
  render_job_failure_reason?: string | null;
  render_output_path?: string | null;
  publishing_metadata_status: string;
  publishing_metadata_ready: boolean;
  publishing_metadata_stale: boolean;
  publishing_metadata_revision?: number | null;
  publishing_metadata_platforms_ready: number;
  subtitle_status: string;
  package_status?: string | null;
  package_id?: string | null;
  core_ready: boolean;
  package_ready: boolean;
}

export interface VideoAutoRunResponse {
  id: string;
  project_id: string;
  mode: VideoAutoRunMode;
  material_target: VideoAutoRunMaterialTarget;
  status: VideoAutoRunStatus;
  current_step: VideoAutoRunStep;
  review_stage?: VideoAutoRunReviewStage | null;
  progress: number;
  force: boolean;
  step_results_json?: Record<string, unknown> | null;
  completed_steps: VideoAutoRunStep[];
  pending_steps: VideoAutoRunStep[];
  failure_reason?: string | null;
  error_code?: string | null;
  summary: VideoAutoRunSummary;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type VideoInspirationTargetLanguage = LanguageCode;
export type VideoInspirationAnalysisMode = 'quick' | 'high_quality';

export interface VideoInspirationFrameResponse {
  id: string;
  job_id: string;
  shot_id?: string | null;
  shot_order?: number | null;
  frame_role: string;
  frame_path: string;
  timestamp_seconds: number;
  description_vi?: string | null;
  technical_metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface VideoInspirationShotResponse {
  id: string;
  job_id: string;
  shot_order: number;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  keyframe_ids_json?: string[] | null;
  visual_description_vi?: string | null;
  subjects_json?: Record<string, unknown> | unknown[] | null;
  setting_json?: Record<string, unknown> | unknown[] | null;
  camera_json?: Record<string, unknown> | null;
  subject_motion_json?: Record<string, unknown> | unknown[] | null;
  transition_in?: string | null;
  transition_out?: string | null;
  on_screen_text_json?: Array<Record<string, unknown>> | null;
  confidence_json?: Record<string, unknown> | null;
  limitations_json?: string[] | Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface VideoInspirationTranscriptSegmentResponse {
  id: string;
  job_id: string;
  segment_order: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  raw_text?: string | null;
  language?: string | null;
  speaker_label?: string | null;
  source: string;
  timestamp_precision: string;
  confidence?: number | null;
  shot_ids_json?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface VideoInspirationAudioEventResponse {
  id: string;
  job_id: string;
  event_order: number;
  event_type: string;
  start_seconds: number;
  end_seconds: number;
  description_vi?: string | null;
  confidence?: number | null;
  technical_metadata_json?: Record<string, unknown> | null;
  shot_ids_json?: string[] | null;
  transcript_segment_ids_json?: string[] | null;
  created_at: string;
}

export interface VideoInspirationTextEventResponse {
  id: string;
  job_id: string;
  shot_id?: string | null;
  event_order: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  language?: string | null;
  role: string;
  region_json?: Record<string, unknown> | null;
  confidence?: number | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface VideoInspirationRetentionBeatResponse {
  id: string;
  job_id: string;
  beat_order: number;
  start_seconds: number;
  end_seconds: number;
  role: string;
  viewer_question_before?: string | null;
  content_promise?: string | null;
  new_information?: string | null;
  emotional_or_stakes_change?: string | null;
  question_answered?: string | null;
  new_open_loop?: string | null;
  micro_payoff?: string | null;
  why_continue?: string | null;
  drop_off_risks_json?: string[] | Record<string, unknown> | null;
  evidence_refs_json?: Array<Record<string, unknown> | string> | null;
  confidence?: number | null;
  created_at: string;
  updated_at: string;
}

export interface VideoInspirationJobResponse {
  id: string;
  source_type: 'upload' | 'url' | string;
  source_url?: string | null;
  original_filename?: string | null;
  source_platform: string;
  source_path?: string | null;
  audio_path?: string | null;
  source_duration_seconds?: number | null;
  status: string;
  current_step: string;
  progress: number;
  target_language: VideoInspirationTargetLanguage;
  rewrite_mode: string;
  user_direction?: string | null;
  transcript_text?: string | null;
  transcript_language?: string | null;
  transcript_status: string;
  analysis_schema_version: string;
  analysis_mode: VideoInspirationAnalysisMode | string;
  analysis_package_json?: Record<string, unknown> | null;
  analysis_package_path?: string | null;
  coverage_metrics_json?: Record<string, unknown> | null;
  limitations_json?: string[] | Record<string, unknown> | null;
  retention_source: string;
  analysis_completeness: string;
  visual_summary?: string | null;
  analysis_json?: Record<string, unknown> | null;
  rewritten_script?: string | null;
  script_title?: string | null;
  big_idea?: string | null;
  hook?: string | null;
  created_video_project_id?: string | null;
  latest_auto_run_id?: string | null;
  ai_video_url?: string | null;
  failure_reason?: string | null;
  error_code?: string | null;
  is_stale?: boolean;
  stale_reason?: string | null;
  frames: VideoInspirationFrameResponse[];
  shots: VideoInspirationShotResponse[];
  transcript_segments: VideoInspirationTranscriptSegmentResponse[];
  audio_events: VideoInspirationAudioEventResponse[];
  on_screen_text_events: VideoInspirationTextEventResponse[];
  content_retention_beats: VideoInspirationRetentionBeatResponse[];
  created_at: string;
  updated_at: string;
}

export interface VideoInspirationListResponse {
  items: VideoInspirationJobResponse[];
  total: number;
}

export interface VideoInspirationUrlRequest {
  url: string;
  target_language: VideoInspirationTargetLanguage;
  user_direction?: string | null;
  use_browser_cookies?: boolean;
}

export interface VideoInspirationAnalyzeRequest {
  allow_audio_only?: boolean;
  stt_model?: WhisperModelSize | null;
  analysis_mode?: VideoInspirationAnalysisMode;
}

export interface VideoInspirationTranscriptUpdate {
  transcript_text: string;
}

export interface VideoInspirationTranscriptSegmentUpdate {
  text: string;
  speaker_label?: string | null;
}

export interface VideoInspirationTextEventUpdate {
  text: string;
  language?: string | null;
  role?: string | null;
}

export interface VideoInspirationDirectionUpdate {
  user_direction?: string | null;
}

export interface VideoInspirationRewriteRequest {
  target_language?: VideoInspirationTargetLanguage;
  user_direction?: string | null;
}

export interface VideoInspirationScriptUpdate {
  rewritten_script: string;
  script_title?: string | null;
  big_idea?: string | null;
  hook?: string | null;
}

export interface VideoInspirationCreateProjectRequest {
  start_full_materials?: boolean;
  mode?: VideoAutoRunMode;
  voice_profile_id?: string | null;
  series_id?: string | null;
}

export interface VideoInspirationStructuredHandoffResponse {
  id: string;
  job_id: string;
  analysis_package_path?: string | null;
  analysis_package_revision: string;
  schema_version: string;
  status: string;
  target_language: VideoInspirationTargetLanguage;
  approved_script_revision: number;
  payload_json: Record<string, unknown>;
  source_blocks_json?: Array<Record<string, unknown>> | null;
  created_project_id?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  approved_at?: string | null;
}

export interface VideoInspirationHandoffListResponse {
  items: VideoInspirationStructuredHandoffResponse[];
  total: number;
}

export interface VideoProjectMemoryCardResponse {
  id: string;
  project_id: string;
  series_id?: string | null;
  memory_scope: string;
  card_type: string;
  title: string;
  content_json: Record<string, unknown>;
  status: string;
  source_type: string;
  source_ref_id?: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  approved_at?: string | null;
}

export interface VideoProjectMemoryListResponse {
  items: VideoProjectMemoryCardResponse[];
  total: number;
}

export interface VideoProjectTargetTimelineBeatResponse {
  id: string;
  project_id: string;
  handoff_id?: string | null;
  beat_order: number;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  role: string;
  content?: string | null;
  viewer_question?: string | null;
  new_information?: string | null;
  micro_payoff?: string | null;
  visual_direction?: string | null;
  audio_direction?: string | null;
  evidence_refs_json?: Array<Record<string, unknown> | string> | null;
  source_lesson_refs_json?: Array<Record<string, unknown> | string> | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface VideoProjectTargetTimelineResponse {
  items: VideoProjectTargetTimelineBeatResponse[];
  total: number;
}

export type VideoProjectContextTaskType =
  | 'story'
  | 'shot'
  | 'prompt_image'
  | 'prompt_video'
  | 'voice'
  | 'subtitle';

export interface VideoProjectContextCompileRequest {
  task_type: VideoProjectContextTaskType;
  artifact_type?: string | null;
  artifact_id?: string | null;
}

export interface VideoProjectContextSnapshotResponse {
  id: string;
  project_id: string;
  task_type: VideoProjectContextTaskType;
  artifact_type?: string | null;
  artifact_id?: string | null;
  context_json: Record<string, unknown>;
  source_refs_json?: Array<Record<string, unknown> | string> | null;
  created_at: string;
}

export interface VideoProjectContextSnapshotListResponse {
  items: VideoProjectContextSnapshotResponse[];
  total: number;
}

export type VideoQualityStatus =
  | 'not_checked'
  | 'checking'
  | 'passed'
  | 'needs_review'
  | 'blocked'
  | 'stale';

export interface VideoQualityRubricConfig {
  content_weight?: number;
  presentation_weight?: number;
  video_type?: string | null;
  special_content_weight_confirmed?: boolean;
}

export interface VideoQualityRunRequest {
  force?: boolean;
  rubric?: VideoQualityRubricConfig | null;
}

export interface VideoQualityOverrideRequest {
  status: 'passed' | 'needs_review' | 'blocked';
  reason: string;
  overridden_by?: string | null;
}

export interface VideoQualitySectionResponse {
  status: VideoQualityStatus;
  score: number;
  summary_vi: string;
  evidence: unknown[];
  blocking_errors: unknown[];
  warnings: unknown[];
  recommended_actions: unknown[];
  criteria_scores: Record<string, unknown>;
  confidence: number;
}

export interface VideoQualityReportResponse {
  id: string;
  project_id?: string | null;
  job_id?: string | null;
  scope: string;
  status: VideoQualityStatus;
  overall_status: VideoQualityStatus;
  content_score: number;
  presentation_score: number;
  total_score: number;
  rubric_json: Record<string, unknown>;
  sections_json: Record<string, VideoQualitySectionResponse>;
  blocking_errors_json?: unknown[] | null;
  warnings_json?: unknown[] | null;
  recommended_actions_json?: unknown[] | null;
  evidence_json?: Record<string, unknown> | unknown[] | null;
  dependencies_json?: Record<string, unknown> | unknown[] | null;
  override_history_json?: Array<Record<string, unknown>> | null;
  revision: number;
  checked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoQualityReportListResponse {
  items: VideoQualityReportResponse[];
  total: number;
}

export interface PlatformRetentionDataPoint {
  timestamp_seconds?: number | null;
  duration_percent?: number | null;
  retention_percent?: number | null;
  rewatch_rate?: number | null;
  label?: string | null;
  note?: string | null;
}

export interface PlatformRetentionDatasetCreateRequest {
  platform?: string;
  video_duration_seconds: number;
  data_points: PlatformRetentionDataPoint[];
  average_watch_time?: number | null;
  completion_rate?: number | null;
  rewatch_rate?: number | null;
  cta_click_rate?: number | null;
  conversion_rate?: number | null;
  source_type?: 'manual' | 'csv' | 'json' | 'platform_export';
}

export interface PlatformRetentionDatasetResponse {
  id: string;
  project_id?: string | null;
  job_id?: string | null;
  platform: string;
  video_duration_seconds: number;
  data_points_json: Array<Record<string, unknown>>;
  normalized_points_json: Array<Record<string, unknown>>;
  average_watch_time?: number | null;
  completion_rate?: number | null;
  rewatch_rate?: number | null;
  cta_click_rate?: number | null;
  conversion_rate?: number | null;
  source_type: string;
  linked_findings_json?: Array<Record<string, unknown>> | null;
  imported_at: string;
  created_at: string;
}

export interface PlatformRetentionDatasetListResponse {
  items: PlatformRetentionDatasetResponse[];
  total: number;
}

export interface VideoInspirationHandoffResponse {
  job: VideoInspirationJobResponse;
  project: VideoProjectResponse;
  auto_run?: VideoAutoRunResponse | null;
  ai_video_url: string;
}

export interface DownloadedBlob {
  blob: Blob;
  filename: string;
}

export interface TranscriptionRequest {
  language?: LanguageCode;
  model?: WhisperModelSize;
}

export interface TranscriptionResponse {
  text: string;
  duration: number;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_downloaded?: boolean;
  model_size?: string;
  gpu_available: boolean;
  gpu_type?: string;
  vram_used_mb?: number;
  backend_type?: string;
  backend_variant?: string; // "cpu" or "cuda"
}

export interface SystemResourceMetric {
  percent?: number | null;
  used?: number | null;
  total?: number | null;
  unit?: string | null;
  label?: string | null;
  status: 'normal' | 'warning' | 'critical' | 'unknown';
}

export interface SystemResourcesResponse {
  sampled_at: string;
  cpu: SystemResourceMetric;
  memory: SystemResourceMetric;
  gpu: SystemResourceMetric;
  thermal: SystemResourceMetric;
  cpu_count?: number | null;
  gpu_available: boolean;
  gpu_type?: string | null;
  backend_type?: string | null;
  backend_variant?: string | null;
}

export interface ResourceModelState {
  key: string;
  kind: string;
  engine: string;
  model_size?: string | null;
  display_name?: string | null;
  backend_type?: string | null;
  size_mb?: number | null;
  heavy: boolean;
  loaded: boolean;
  loading: boolean;
  loaded_at?: string | null;
  last_used_at?: string | null;
  last_unloaded_at?: string | null;
  idle_seconds?: number | null;
}

export interface ResourceMemoryStatus {
  status: 'normal' | 'warning' | 'critical' | 'unknown';
  percent?: number | null;
  used_mb?: number | null;
  total_mb?: number | null;
}

export interface ResourceCacheStatus {
  available: boolean;
  entries?: number | null;
  bytes?: number | null;
  size_mb?: number | null;
  hits_memory?: number | null;
  hits_disk?: number | null;
  misses?: number | null;
  evictions?: number | null;
  files?: number | null;
  disk_files?: number | null;
  disk_bytes?: number | null;
  disk_size_mb?: number | null;
  max_entries?: number | null;
  max_mb?: number | null;
  max_age_days?: number | null;
  ttl_seconds?: number | null;
  error?: string | null;
}

export interface ResourceMlxStatus {
  available: boolean;
  cache_bytes?: number | null;
  cache_mb?: number | null;
  active_bytes?: number | null;
  active_mb?: number | null;
}

export interface ResourceCleanupAction {
  action: string;
  status: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ResourceStatusResponse {
  sampled_at: string;
  policy: Record<string, unknown>;
  memory: ResourceMemoryStatus;
  generation_queue: {
    available: boolean;
    queued: number;
    running: number;
    max_concurrency?: number | null;
    queued_ids: string[];
    running_ids: string[];
  };
  workflow_pool?: {
    available: boolean;
    max_concurrency: number;
    running: number;
    queued: number;
    running_keys: string[];
    queued_keys: string[];
  };
  planning_pool?: {
    available: boolean;
    max_concurrency: number;
    running: number;
    queued: number;
    running_keys: string[];
    queued_keys: string[];
  };
  stt_pool?: {
    available: boolean;
    max_concurrency: number;
    running: number;
    queued: number;
    running_keys: string[];
    queued_keys: string[];
  };
  active_jobs: {
    generations: Array<Record<string, unknown>>;
    generation_count: number;
    render_count: number;
    auto_run_count: number;
  };
  models: ResourceModelState[];
  voice_prompt_cache: ResourceCacheStatus;
  render_cache: ResourceCacheStatus;
  mlx: ResourceMlxStatus;
  recent_events: Array<Record<string, unknown>>;
}

export interface ResourceCleanupRequest {
  unload_idle_models?: boolean;
  clear_voice_prompt_memory?: boolean;
  clear_mlx_cache?: boolean;
  clear_render_cache?: boolean;
  render_cache_project_id?: string | null;
}

export interface ResourceCleanupResponse {
  actions: ResourceCleanupAction[];
  status: ResourceStatusResponse;
}

export interface RenderCacheClearResponse {
  files_deleted: number;
  bytes_deleted: number;
  project_id?: string | null;
}

export interface CudaDownloadProgress {
  model_name: string;
  current: number;
  total: number;
  progress: number;
  filename?: string;
  status: 'downloading' | 'extracting' | 'complete' | 'error';
  timestamp: string;
  error?: string;
}

export interface CudaStatus {
  available: boolean; // CUDA binary exists on disk
  active: boolean; // Currently running the CUDA binary
  binary_path?: string;
  downloading: boolean; // Download in progress
  download_progress?: CudaDownloadProgress;
}

export interface ModelProgress {
  model_name: string;
  current: number;
  total: number;
  progress: number;
  filename?: string;
  status: 'downloading' | 'extracting' | 'complete' | 'error';
  timestamp: string;
  error?: string;
}

export interface ModelStatus {
  model_name: string;
  display_name: string;
  hf_repo_id?: string; // HuggingFace repository ID
  downloaded: boolean;
  downloading: boolean; // True if download is in progress
  size_mb?: number;
  loaded: boolean;
}

export interface HuggingFaceModelInfo {
  id: string;
  author: string;
  lastModified: string;
  pipeline_tag?: string;
  library_name?: string;
  downloads: number;
  likes: number;
  tags: string[];
  cardData?: {
    license?: string;
    language?: string[];
    pipeline_tag?: string;
  };
}

export interface ModelStatusListResponse {
  models: ModelStatus[];
}

export interface TadaVietnameseStatusResponse {
  accepted: boolean;
  local_bypass_enabled: boolean;
  status: string;
  language: 'vi';
  model_size: '3B';
  aligner_strategy: string;
  corpus_version: string;
  run_id?: string | null;
  notes?: string | null;
  reviewer?: string | null;
}

export interface ModelDownloadRequest {
  model_name: string;
}

export interface ActiveDownloadTask {
  model_name: string;
  status: string;
  started_at: string;
  error?: string;
  progress?: number; // 0-100 percentage
  current?: number; // bytes downloaded
  total?: number; // total bytes
  filename?: string; // current file being downloaded
}

export interface ActiveGenerationTask {
  task_id: string;
  profile_id: string;
  text_preview: string;
  started_at: string;
}

export interface ActiveTasksResponse {
  downloads: ActiveDownloadTask[];
  generations: ActiveGenerationTask[];
}

export interface StoryCreate {
  name: string;
  description?: string;
}

export interface StoryResponse {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}

export interface StoryItemDetail {
  id: string;
  story_id: string;
  generation_id: string;
  version_id?: string;
  start_time_ms: number;
  track: number;
  trim_start_ms: number;
  trim_end_ms: number;
  created_at: string;
  profile_id: string;
  profile_name: string;
  text: string;
  language: string;
  audio_path: string;
  duration: number;
  seed?: number;
  instruct?: string;
  engine?: string;
  volume: number;
  generation_created_at: string;
  versions?: GenerationVersionResponse[];
  active_version_id?: string;
}

export interface StoryItemVolumeUpdate {
  volume: number;
}

export interface StoryItemVersionUpdate {
  version_id: string | null;
}

export interface StoryDetailResponse {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  items: StoryItemDetail[];
}

export interface StoryItemCreate {
  generation_id: string;
  start_time_ms?: number;
  track?: number;
}

export interface StoryItemUpdateTime {
  generation_id: string;
  start_time_ms: number;
}

export interface StoryItemBatchUpdate {
  updates: StoryItemUpdateTime[];
}

export interface StoryItemReorder {
  generation_ids: string[];
}

export interface StoryItemMove {
  start_time_ms: number;
  track: number;
}

export interface StoryItemTrim {
  trim_start_ms: number;
  trim_end_ms: number;
}

export interface StoryItemSplit {
  split_time_ms: number;
}

// Effects

export interface EffectPresetResponse {
  id: string;
  name: string;
  description?: string;
  effects_chain: EffectConfig[];
  is_builtin: boolean;
  created_at: string;
}

export interface EffectPresetCreate {
  name: string;
  description?: string;
  effects_chain: EffectConfig[];
}

export interface EffectPresetUpdate {
  name?: string;
  description?: string;
  effects_chain?: EffectConfig[];
}

export interface AvailableEffectParam {
  default: number;
  min: number;
  max: number;
  step: number;
  description: string;
}

export interface AvailableEffect {
  type: string;
  label: string;
  description: string;
  params: Record<string, AvailableEffectParam>;
}

export interface AvailableEffectsResponse {
  effects: AvailableEffect[];
}

export interface ApplyEffectsRequest {
  effects_chain: EffectConfig[];
  source_version_id?: string;
  label?: string;
  set_as_default?: boolean;
}

/* ─── MCP ─────────────────────────────────────────────────────────────── */

export interface MCPClientBinding {
  client_id: string;
  label: string | null;
  profile_id: string | null;
  default_engine: string | null;
  default_personality: boolean;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCPClientBindingUpsert {
  client_id: string;
  label?: string | null;
  profile_id?: string | null;
  default_engine?: string | null;
  default_personality?: boolean;
}

export interface MCPClientBindingListResponse {
  items: MCPClientBinding[];
}

// --- Comic Series Analysis (change 13) ---------------------------------

export interface ComicCapabilitiesResponse {
  feature_enabled: boolean;
  codecs: {
    full_capability_ready: boolean;
    missing_mandatory: string[];
    codecs: Record<string, { can_decode: boolean; can_encode: boolean; status: string; detail: string | null }>;
  };
}

export interface ComicJobSummary {
  id: string;
  source_type: string;
  title: string | null;
  run_status: string;
  result_completeness: string;
  current_step: string;
  progress: number;
  reading_mode: string;
  development_mode: string;
  outcome_code: string | null;
  error_code: string | null;
  error_message: string | null;
  current_source_document_id: string | null;
  analysis_revision: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ComicJobDetail extends ComicJobSummary {
  coverage_metrics: Record<string, unknown> | null;
  limitations: unknown[] | null;
  source_url: string | null;
}

export interface ComicJobListResponse {
  jobs: ComicJobSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ComicUrlJobRequest {
  url: string;
  reading_mode?: string;
  development_mode?: string;
  rights_attested?: boolean;
  title?: string;
}

export interface ComicHandoffPreview {
  handoff_id: string;
  status: string;
  preview_fingerprint: string;
  target_kind: string;
  target_series_mode: string;
  target_series_title?: string | null;
  output_intent?: StoryOutputIntent;
  output_settings?: StoryEpisodeOutputSettings | null;
  market_profile?: string;
  language_profile?: string;
  episode_number: number | null;
  item_decisions: Array<Record<string, unknown>>;
}

export interface ComicHandoffResult {
  series_id: string;
  story_episode_id: string;
  source_document_id: string;
  handoff_id: string;
  story_studio_url: string;
}

export interface ComicAnalysisPanel {
  id: string;
  asset_id?: string | null;
  reading_order: number;
  visual_description?: string | null;
  confidence?: number | null;
  evidence_ids?: string[] | null;
  needs_review?: boolean;
}

export interface ComicAnalysisDialogue {
  id: string;
  reading_order: number;
  bubble_type: string;
  text?: string | null;
  speaker_character_id?: string | null;
  confidence?: number | null;
  evidence_ids?: string[] | null;
}

export interface ComicAnalysisCharacter {
  id: string;
  name?: string | null;
  role?: string | null;
  face_description?: string | null;
  hair_description?: string | null;
  body_description?: string | null;
  outfit_description?: string | null;
  personality?: string | null;
  speech_style?: string | null;
  confidence?: number | null;
  evidence_ids?: string[] | null;
}

export interface ComicAnalysisLocation {
  id: string;
  name?: string | null;
  description?: string | null;
  world_rules?: string | null;
  confidence?: number | null;
  evidence_ids?: string[] | null;
}

export interface ComicOptimizedScript {
  title: string;
  synopsis: string;
  hook: string;
  full_story: string;
  plot_beats: string[];
  character_arcs: string[];
  scene_outline: string[];
}

export interface ComicAnalysisPackage {
  analysis_revision: number;
  panels: ComicAnalysisPanel[];
  dialogues: ComicAnalysisDialogue[];
  characters: ComicAnalysisCharacter[];
  locations: ComicAnalysisLocation[];
  plot: {
    synopsis?: string | null;
    plot_beats?: string[];
    relationships?: unknown[];
    end_state?: Record<string, unknown> | null;
    canon_candidates?: unknown[];
    uncertainties?: unknown[];
    limitations?: unknown[];
  };
  optimized_script?: ComicOptimizedScript | null;
  optimized_script_source?: string | null;
}
