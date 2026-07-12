// API Types matching backend Pydantic models
import type { LanguageCode } from '@/lib/constants/languages';

export type VoiceType = 'cloned' | 'preset' | 'designed';
export type VideoLanguage = 'en' | 'vi';
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

export interface AIPlanningProviderCheckResponse {
  ready: boolean;
  provider: string;
  message: string;
  codex_path?: string | null;
  version?: string | null;
  request_id?: string | null;
  error_code?: string | null;
}

export interface VideoProjectCreate {
  topic: string;
  title?: string | null;
  series_id?: string | null;
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

export interface VideoSeriesCreate {
  title: string;
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
  character_bible?: string | null;
  world_bible?: string | null;
  style_bible?: string | null;
  continuity_rules?: string | null;
  negative_rules?: string | null;
  previous_episode_summary?: string | null;
  latest_episode_number: number;
  episode_count: number;
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

export type VideoClipGenerationStatus =
  | 'queued'
  | 'running'
  | 'needs_login'
  | 'needs_user_action'
  | 'needs_credit_approval'
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
  needs_credit_approval_items: number;
  credit_spent_estimate: number;
  render_ready: boolean;
  render_missing_reasons: string[];
}

export interface VideoClipGenerationJobStartRequest {
  session_id?: string | null;
  force?: boolean;
  auto_render?: boolean;
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
  credit_approval_policy: 'approve_dont_ask_again' | 'manual_per_item' | string;
  max_credit_per_job?: number | null;
  credit_spent_estimate: number;
  render_job_id?: string | null;
  failure_reason?: string | null;
  error_code?: string | null;
  step_results_json?: Record<string, unknown> | null;
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
  created_at: string;
  updated_at: string;
}

export type VideoAutoRunMode = 'review_gated' | 'full_auto';
export type VideoAutoRunMaterialTarget = 'full_materials' | 'prompts_only' | 'video_clips';
export type VideoAutoRunStatus =
  | 'queued'
  | 'running'
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
  | 'develop_story'
  | 'waiting_planning'
  | 'review_story'
  | 'generate_shots'
  | 'generate_prompts'
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

export type VideoInspirationTargetLanguage = 'vi' | 'en';

export interface VideoInspirationFrameResponse {
  id: string;
  job_id: string;
  frame_path: string;
  timestamp_seconds: number;
  description_vi?: string | null;
  technical_metadata_json?: Record<string, unknown> | null;
  created_at: string;
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
  frames: VideoInspirationFrameResponse[];
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
}

export interface VideoInspirationTranscriptUpdate {
  transcript_text: string;
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
    queued_ids: string[];
    running_ids: string[];
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
