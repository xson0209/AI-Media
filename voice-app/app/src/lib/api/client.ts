import { runClipBatchUpload } from '@/lib/clipBatchUpload';
import type { LanguageCode } from '@/lib/constants/languages';
import { clipAudioChoiceFromSettings } from '@/lib/renderSettingsStore';
import { useServerStore } from '@/stores/serverStore';
import type {
  ActiveTasksResponse,
  AutomationAssetResponse,
  AutomationConnectionCreate,
  AutomationConnectionResponse,
  AutomationConnectionUpdate,
  AutomationHubStatusResponse,
  AutomationPublishJobCreate,
  AutomationPublishJobResponse,
  AutomationSidecarStatus,
  ArtifactDependencyRecordRequest,
  ArtifactDependencySnapshotResponse,
  ArtifactStaleEventListResponse,
  ArtifactStaleMarkRequest,
  ArtifactTargetedRegenerationRequest,
  ArtifactTargetedRegenerationResponse,
  AIPlanningSettings,
  AIPlanningSettingsUpdate,
  AIPlanningTestResponse,
  AIPlanningProviderCheckResponse,
  ApplyEffectsRequest,
  AvailableEffectsResponse,
  CaptureCreateResponse,
  CharacterProposalDecisionRequest,
  CharacterProposalDecisionResponse,
  ComicCapabilitiesResponse,
  ComicHandoffPreview,
  ComicHandoffResult,
  ComicJobDetail,
  ComicAnalysisPackage,
  ComicJobListResponse,
  ComicUrlJobRequest,
  CaptureListResponse,
  CaptureReadinessResponse,
  CaptureRefineRequest,
  CaptureResponse,
  CaptureRetranscribeRequest,
  CaptureSettings,
  CaptureSettingsUpdate,
  CaptureSource,
  CudaStatus,
  DownloadedBlob,
  EffectConfig,
  EffectPresetCreate,
  EffectPresetResponse,
  GenerationRequest,
  GenerationResponse,
  GenerationSettings,
  GenerationSettingsUpdate,
  GenerationVersionResponse,
  HealthResponse,
  HistoryListResponse,
  HistoryQuery,
  HistoryResponse,
  MCPClientBinding,
  MCPClientBindingListResponse,
  MCPClientBindingUpsert,
  ModelDownloadRequest,
  ModelStatusListResponse,
  PersonalityTextResponse,
  RenderCacheClearResponse,
  PresetVoice,
  ProfileSampleResponse,
  PlatformRetentionDatasetCreateRequest,
  PlatformRetentionDatasetListResponse,
  PlatformRetentionDatasetResponse,
  ProductVideoProjectCreate,
  ProductVideoProjectDetailResponse,
  ProductVideoProjectResponse,
  ProductVideoProjectUpdate,
  ProductVideoPromptPackResponse,
  ProductVideoShotResponse,
  ResourceCleanupRequest,
  ResourceCleanupResponse,
  ResourceStatusResponse,
  ResearchChatResponse,
  ResearchChatAction,
  ResearchChatPromotionResponse,
  ResearchChatThreadResponse,
  ResearchHandoffResponse,
  ResearchIdeaResponse,
  ResearchProjectCreate,
  ResearchProjectResponse,
  ResearchRecommendationResponse,
  ResearchRunResponse,
  ResearchScoreResponse,
  ResearchScriptResponse,
  ResearchSourceResponse,
  RoxyProfileListResponse,
  RoxyWorkspaceListResponse,
  SeriesCharacterProfileCreate,
  SeriesCharacterProfileResponse,
  SeriesCharacterProfileSuggestionResponse,
  SeriesCharacterProfileUpdate,
  SeriesCanonCheckRequest,
  SeriesCanonCheckResponse,
  SeriesContextCompileRequest,
  SeriesContextCompileResponse,
  SeriesContextTraceListResponse,
  SeriesCurrentStateCreate,
  SeriesCurrentStateListResponse,
  SeriesCurrentStateResponse,
  SeriesCurrentStateStatusRequest,
  SeriesCurrentStateUpdate,
  SeriesMemoryCardCreate,
  SeriesMemoryCardListResponse,
  SeriesMemoryCardResponse,
  SeriesMemoryCardStatusRequest,
  SeriesMemoryCardUpdate,
  SeriesMemorySuggestionRequest,
  SeriesMemorySuggestionResponse,
  SeriesReferenceAssetListResponse,
  SeriesReferenceAssetResponse,
  SeriesReferenceAssetStatusRequest,
  SeriesVersionHistoryResponse,
  SeriesStateProposalRequest,
  StoryCreate,
  StoryAdaptationResponse,
  StoryApprovalRequest,
  StoryCandidateSelectionRequest,
  StoryCandidateSynthesisRequest,
  StoryDetailResponse,
  StoryEpisodeCreate,
  StoryEpisodeResponse,
  StoryEpisodeUpdate,
  StoryImageRenderJobUpdateRequest,
  StoryImageRenderRequest,
  StoryItemBatchUpdate,
  StoryItemCreate,
  StoryItemDetail,
  StoryItemMove,
  StoryItemReorder,
  StoryItemSplit,
  StoryItemTrim,
  StoryItemVersionUpdate,
  StoryItemVolumeUpdate,
  StoryPanelPromptApprovalRequest,
  StoryPanelPromptUpdateRequest,
  StoryPromptRepairRequest,
  StoryResponse,
  StorySuggestionApprovalRequest,
  StorySuggestionResponse,
  StoryVideoHandoffRequest,
  SystemResourcesResponse,
  TadaVietnameseStatusResponse,
  TranscriptionResponse,
  VideoAutoRunContinueRequest,
  VideoAutoRunResponse,
  VideoAutoRunRetryRequest,
  VideoAutoRunStartRequest,
  VideoClipGenerationCreditApprovalRequest,
  VideoClipGenerationJobResponse,
  VideoClipGenerationJobStartRequest,
  VideoClipGenerationResumeRequest,
  VideoClipGenerationRetryRequest,
  VideoEpisodeCreate,
  VideoGeneratedDataResetResponse,
  VideoInspirationAnalyzeRequest,
  VideoInspirationVariantGenerateRequest,
  VideoInspirationVariantScoreRequest,
  VideoInspirationVariantSynthesisRequest,
  VideoInspirationVariantSelectRequest,
  VideoInspirationCreateProjectRequest,
  VideoInspirationDirectionUpdate,
  VideoInspirationHandoffListResponse,
  VideoInspirationHandoffResponse,
  VideoInspirationJobResponse,
  VideoInspirationListResponse,
  VideoInspirationRewriteRequest,
  VideoInspirationScriptUpdate,
  VideoInspirationStructuredHandoffResponse,
  VideoInspirationTargetLanguage,
  VideoInspirationTextEventUpdate,
  VideoInspirationTranscriptSegmentUpdate,
  VideoInspirationTranscriptUpdate,
  VideoInspirationUrlRequest,
  VideoPackageExportResponse,
  VideoPackageReadinessResponse,
  VideoPublishingMetadataGenerateRequest,
  VideoPublishingMetadataResponse,
  VideoProviderProjectBindingResponse,
  VideoProviderSessionLabelUpdate,
  VideoProviderSessionOpenRequest,
  VideoProviderSessionResponse,
  VideoProjectCreate,
  VideoProjectContextCompileRequest,
  VideoProjectContextSnapshotListResponse,
  VideoProjectContextSnapshotResponse,
  VideoProjectCharacterFlowResponse,
  VideoProjectDetailResponse,
  VideoProjectMemoryListResponse,
  VideoProjectLocalizeRequest,
  VideoQualityOverrideRequest,
  VideoQualityReportListResponse,
  VideoQualityReportResponse,
  VideoQualityRunRequest,
  VideoProjectResponse,
  VideoProjectStatusResponse,
  VideoProjectTargetTimelineResponse,
  VideoProjectUpdate,
  VideoShotUpdate,
  NewsSpeechMode,
  VideoPromptContentResponse,
  VideoRenderJobResponse,
  VideoRenderReadinessResponse,
  VideoRenderSettings,
  VideoRenderSfxAssetResponse,
  VideoSceneAssetResponse,
  VideoSceneNarrationRequest,
  VideoSceneResponse,
  VideoSceneVoiceStatusResponse,
  VideoSeriesCreate,
  VideoSeriesResponse,
  VideoSeriesUpdate,
  VideoShotClipBatchEntry,
  VideoShotClipBatchResult,
  VideoShotClipResponse,
  VideoShotPromptPackResponse,
  VideoShotResponse,
  VideoShotVoiceStatusResponse,
  VideoSourceBlockCreate,
  VideoSourceBlockResponse,
  VideoSourceBlockUpdate,
  VideoSubtitleResponse,
  VoiceProfileCreate,
  VoiceProfileResponse,
  WhisperModelSize,
} from './types';

export interface AudioTrimOptions {
  trimStartSeconds: number;
  trimDurationSeconds: number;
}

function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: Record<string, unknown>) => e.msg || e.message || JSON.stringify(e))
      .join('; ');
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.message === 'string') return obj.message;
    return JSON.stringify(detail);
  }
  return fallback;
}

function filenameFromDisposition(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
  return asciiMatch?.[1] || fallback;
}

class ApiClient {
  private getBaseUrl(): string {
    const serverUrl = useServerStore.getState().serverUrl;
    return serverUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.getBaseUrl()}${endpoint}`;
    const headers = new Headers(options?.headers);
    if (!(options?.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  private async download(endpoint: string, fallbackFilename: string): Promise<DownloadedBlob> {
    const response = await fetch(`${this.getBaseUrl()}${endpoint}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(
        response.headers.get('Content-Disposition'),
        fallbackFilename,
      ),
    };
  }

  // Health
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async getSystemResources(): Promise<SystemResourcesResponse> {
    return this.request<SystemResourcesResponse>('/health/system');
  }

  // Profiles
  async createProfile(data: VoiceProfileCreate): Promise<VoiceProfileResponse> {
    return this.request<VoiceProfileResponse>('/profiles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listProfiles(): Promise<VoiceProfileResponse[]> {
    return this.request<VoiceProfileResponse[]>('/profiles');
  }

  async getProfile(profileId: string): Promise<VoiceProfileResponse> {
    return this.request<VoiceProfileResponse>(`/profiles/${profileId}`);
  }

  async listPresetVoices(engine: string): Promise<{ engine: string; voices: PresetVoice[] }> {
    return this.request<{ engine: string; voices: PresetVoice[] }>(`/profiles/presets/${engine}`);
  }

  async updateProfile(profileId: string, data: VoiceProfileCreate): Promise<VoiceProfileResponse> {
    return this.request<VoiceProfileResponse>(`/profiles/${profileId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteProfile(profileId: string): Promise<void> {
    await this.request<void>(`/profiles/${profileId}`, {
      method: 'DELETE',
    });
  }

  // ── Personality-driven text generation ─────────────────────────────
  // Compose produces a fresh in-character utterance the UI drops into
  // the generate textarea. Rewrite now happens server-side inside
  // `/generate` when `personality: true` is passed in the request body.

  async composeWithPersonality(profileId: string): Promise<PersonalityTextResponse> {
    return this.request<PersonalityTextResponse>(`/profiles/${profileId}/compose`, {
      method: 'POST',
    });
  }

  async addProfileSample(
    profileId: string,
    file: File,
    referenceText: string,
    trimOptions?: AudioTrimOptions,
  ): Promise<ProfileSampleResponse> {
    const url = `${this.getBaseUrl()}/profiles/${profileId}/samples`;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('reference_text', referenceText);
    if (trimOptions) {
      formData.append('trim_start_seconds', String(trimOptions.trimStartSeconds));
      formData.append('trim_duration_seconds', String(trimOptions.trimDurationSeconds));
    }

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  async listProfileSamples(profileId: string): Promise<ProfileSampleResponse[]> {
    return this.request<ProfileSampleResponse[]>(`/profiles/${profileId}/samples`);
  }

  async deleteProfileSample(sampleId: string): Promise<void> {
    await this.request<void>(`/profiles/samples/${sampleId}`, {
      method: 'DELETE',
    });
  }

  async updateProfileSample(
    sampleId: string,
    referenceText: string,
  ): Promise<ProfileSampleResponse> {
    return this.request<ProfileSampleResponse>(`/profiles/samples/${sampleId}`, {
      method: 'PUT',
      body: JSON.stringify({ reference_text: referenceText }),
    });
  }

  async exportProfile(profileId: string): Promise<Blob> {
    const url = `${this.getBaseUrl()}/profiles/${profileId}/export`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.blob();
  }

  async importProfile(file: File): Promise<VoiceProfileResponse> {
    const url = `${this.getBaseUrl()}/profiles/import`;
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  async uploadAvatar(profileId: string, file: File): Promise<VoiceProfileResponse> {
    const url = `${this.getBaseUrl()}/profiles/${profileId}/avatar`;
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  async deleteAvatar(profileId: string): Promise<void> {
    await this.request<void>(`/profiles/${profileId}/avatar`, {
      method: 'DELETE',
    });
  }

  // Generation
  async generateSpeech(data: GenerationRequest): Promise<GenerationResponse> {
    return this.request<GenerationResponse>('/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async retryGeneration(generationId: string): Promise<GenerationResponse> {
    return this.request<GenerationResponse>(`/generate/${generationId}/retry`, {
      method: 'POST',
    });
  }

  async cancelGeneration(generationId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/generate/${generationId}/cancel`, {
      method: 'POST',
    });
  }

  async regenerateGeneration(generationId: string): Promise<GenerationResponse> {
    return this.request<GenerationResponse>(`/generate/${generationId}/regenerate`, {
      method: 'POST',
    });
  }

  async importAudio(file: File): Promise<GenerationResponse> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${this.getBaseUrl()}/generate/import`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async toggleFavorite(generationId: string): Promise<{ is_favorited: boolean }> {
    return this.request<{ is_favorited: boolean }>(`/history/${generationId}/favorite`, {
      method: 'POST',
    });
  }

  // History
  async listHistory(query?: HistoryQuery): Promise<HistoryListResponse> {
    const params = new URLSearchParams();
    if (query?.profile_id) params.append('profile_id', query.profile_id);
    if (query?.search) params.append('search', query.search);
    if (query?.limit) params.append('limit', query.limit.toString());
    if (query?.offset) params.append('offset', query.offset.toString());

    const queryString = params.toString();
    const endpoint = queryString ? `/history?${queryString}` : '/history';

    return this.request<HistoryListResponse>(endpoint);
  }

  async getGeneration(generationId: string): Promise<HistoryResponse> {
    return this.request<HistoryResponse>(`/history/${generationId}`);
  }

  async deleteGeneration(generationId: string): Promise<void> {
    await this.request<void>(`/history/${generationId}`, {
      method: 'DELETE',
    });
  }

  async clearFailedGenerations(): Promise<{ deleted: number }> {
    return this.request<{ deleted: number }>(`/history/failed`, {
      method: 'DELETE',
    });
  }

  async exportGeneration(generationId: string): Promise<Blob> {
    const url = `${this.getBaseUrl()}/history/${generationId}/export`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.blob();
  }

  async exportGenerationAudio(generationId: string): Promise<Blob> {
    const url = `${this.getBaseUrl()}/history/${generationId}/export-audio`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.blob();
  }

  async importGeneration(file: File): Promise<{
    id: string;
    profile_id: string;
    profile_name: string;
    text: string;
    message: string;
  }> {
    const url = `${this.getBaseUrl()}/history/import`;
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  // Generation status SSE
  getGenerationStatusUrl(generationId: string): string {
    return `${this.getBaseUrl()}/generate/${generationId}/status`;
  }

  // Audio
  getAudioUrl(audioId: string): string {
    return `${this.getBaseUrl()}/audio/${audioId}`;
  }

  getSampleUrl(sampleId: string): string {
    return `${this.getBaseUrl()}/samples/${sampleId}`;
  }

  // Transcription
  async transcribeAudio(
    file: File,
    language?: LanguageCode,
    model?: WhisperModelSize,
    trimOptions?: AudioTrimOptions,
  ): Promise<TranscriptionResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (language) {
      formData.append('language', language);
    }
    if (model) {
      formData.append('model', model);
    }
    if (trimOptions) {
      formData.append('trim_start_seconds', String(trimOptions.trimStartSeconds));
      formData.append('trim_duration_seconds', String(trimOptions.trimDurationSeconds));
    }

    const url = `${this.getBaseUrl()}/transcribe`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.json();
  }

  // Video Inspiration
  async listVideoInspirationJobs(limit = 20, offset = 0): Promise<VideoInspirationListResponse> {
    return this.request<VideoInspirationListResponse>(
      `/video-inspiration/jobs?limit=${limit}&offset=${offset}`,
    );
  }

  async getVideoInspirationJob(jobId: string): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}`);
  }

  getVideoInspirationFrameUrl(frameId: string): string {
    return `${this.getBaseUrl()}/video-inspiration/frames/${frameId}`;
  }

  async uploadVideoInspirationJob(
    file: File,
    targetLanguage: VideoInspirationTargetLanguage,
    userDirection?: string | null,
  ): Promise<VideoInspirationJobResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_language', targetLanguage);
    const direction = userDirection?.trim();
    if (direction) {
      formData.append('user_direction', direction);
    }
    const response = await fetch(`${this.getBaseUrl()}/video-inspiration/jobs/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  async createVideoInspirationJobFromUrl(
    data: VideoInspirationUrlRequest,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>('/video-inspiration/jobs/from-url', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async analyzeVideoInspirationJob(
    jobId: string,
    data: VideoInspirationAnalyzeRequest,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/analyze`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async deepResearchVideoInspirationJob(
    jobId: string,
    data: VideoInspirationAnalyzeRequest = {},
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/deep-research`,
      { method: 'POST', body: JSON.stringify({ ...data, analysis_mode: 'high_quality', handoff_to_ai_video: true }) },
    );
  }

  async generateVideoInspirationVariants(
    jobId: string,
    data: VideoInspirationVariantGenerateRequest = {},
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}/variants/candidates`, {
      method: 'POST', body: JSON.stringify(data),
    });
  }

  async scoreVideoInspirationVariants(
    jobId: string,
    data: VideoInspirationVariantScoreRequest = {},
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}/variants/score`, {
      method: 'POST', body: JSON.stringify(data),
    });
  }

  async synthesizeVideoInspirationVariants(
    jobId: string,
    data: VideoInspirationVariantSynthesisRequest = {},
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}/variants/synthesize`, {
      method: 'POST', body: JSON.stringify(data),
    });
  }

  async selectVideoInspirationVariant(
    jobId: string,
    data: VideoInspirationVariantSelectRequest,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}/variants/select`, {
      method: 'POST', body: JSON.stringify(data),
    });
  }

  async updateVideoInspirationTranscript(
    jobId: string,
    data: VideoInspirationTranscriptUpdate,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/transcript`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async updateVideoInspirationTranscriptSegment(
    jobId: string,
    segmentId: string,
    data: VideoInspirationTranscriptSegmentUpdate,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/transcript-segments/${segmentId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async updateVideoInspirationTextEvent(
    jobId: string,
    eventId: string,
    data: VideoInspirationTextEventUpdate,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/on-screen-text/${eventId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async getVideoInspirationAnalysisPackage(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      `/video-inspiration/jobs/${jobId}/analysis-package`,
    );
  }

  async updateVideoInspirationDirection(
    jobId: string,
    data: VideoInspirationDirectionUpdate,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/direction`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async rewriteVideoInspirationJob(
    jobId: string,
    data: VideoInspirationRewriteRequest,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(`/video-inspiration/jobs/${jobId}/rewrite`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async cancelVideoInspirationJob(jobId: string): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/cancel`,
      { method: 'POST' },
    );
  }

  async retryVideoInspirationJob(jobId: string): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/retry`,
      { method: 'POST' },
    );
  }

  async updateVideoInspirationScript(
    jobId: string,
    data: VideoInspirationScriptUpdate,
  ): Promise<VideoInspirationJobResponse> {
    return this.request<VideoInspirationJobResponse>(
      `/video-inspiration/jobs/${jobId}/script`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async createAIVideoProjectFromInspiration(
    jobId: string,
    data: VideoInspirationCreateProjectRequest,
  ): Promise<VideoInspirationHandoffResponse> {
    return this.request<VideoInspirationHandoffResponse>(
      `/video-inspiration/jobs/${jobId}/create-ai-video-project`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async createVideoInspirationHandoff(
    jobId: string,
  ): Promise<VideoInspirationStructuredHandoffResponse> {
    return this.request<VideoInspirationStructuredHandoffResponse>(
      `/video-inspiration/jobs/${jobId}/handoffs`,
      { method: 'POST' },
    );
  }

  async listVideoInspirationHandoffs(
    jobId: string,
  ): Promise<VideoInspirationHandoffListResponse> {
    return this.request<VideoInspirationHandoffListResponse>(
      `/video-inspiration/jobs/${jobId}/handoffs`,
    );
  }

  // Captures
  async listCaptures(limit = 50, offset = 0): Promise<CaptureListResponse> {
    return this.request<CaptureListResponse>(`/captures?limit=${limit}&offset=${offset}`);
  }

  async getCapture(captureId: string): Promise<CaptureResponse> {
    return this.request<CaptureResponse>(`/captures/${captureId}`);
  }

  async createCapture(
    file: File,
    options?: {
      source?: CaptureSource;
      language?: LanguageCode;
      sttModel?: WhisperModelSize;
    },
  ): Promise<CaptureCreateResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', options?.source ?? 'file');
    if (options?.language) formData.append('language', options.language);
    if (options?.sttModel) formData.append('stt_model', options.sttModel);

    const url = `${this.getBaseUrl()}/captures`;
    const response = await fetch(url, { method: 'POST', body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  async deleteCapture(captureId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/captures/${captureId}`, {
      method: 'DELETE',
    });
  }

  async refineCapture(captureId: string, body: CaptureRefineRequest): Promise<CaptureResponse> {
    return this.request<CaptureResponse>(`/captures/${captureId}/refine`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async retranscribeCapture(
    captureId: string,
    body: CaptureRetranscribeRequest,
  ): Promise<CaptureResponse> {
    return this.request<CaptureResponse>(`/captures/${captureId}/retranscribe`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  getCaptureAudioUrl(captureId: string): string {
    return `${this.getBaseUrl()}/captures/${captureId}/audio`;
  }

  // Settings
  async getCaptureSettings(): Promise<CaptureSettings> {
    return this.request<CaptureSettings>('/settings/captures');
  }

  async getCaptureReadiness(): Promise<CaptureReadinessResponse> {
    return this.request<CaptureReadinessResponse>('/capture/readiness');
  }

  async updateCaptureSettings(patch: CaptureSettingsUpdate): Promise<CaptureSettings> {
    return this.request<CaptureSettings>('/settings/captures', {
      method: 'PUT',
      body: JSON.stringify(patch),
    });
  }

  async getGenerationSettings(): Promise<GenerationSettings> {
    return this.request<GenerationSettings>('/settings/generation');
  }

  async updateGenerationSettings(patch: GenerationSettingsUpdate): Promise<GenerationSettings> {
    return this.request<GenerationSettings>('/settings/generation', {
      method: 'PUT',
      body: JSON.stringify(patch),
    });
  }

  async getAIPlanningSettings(): Promise<AIPlanningSettings> {
    return this.request<AIPlanningSettings>('/settings/ai-planning');
  }

  async updateAIPlanningSettings(patch: AIPlanningSettingsUpdate): Promise<AIPlanningSettings> {
    return this.request<AIPlanningSettings>('/settings/ai-planning', {
      method: 'PUT',
      body: JSON.stringify(patch),
    });
  }

  async testAIPlanningSettings(): Promise<AIPlanningTestResponse> {
    return this.request<AIPlanningTestResponse>('/settings/ai-planning/test', {
      method: 'POST',
    });
  }

  // MCP bindings — per-MCP-client voice/engine/personality mapping.
  async listMCPBindings(): Promise<MCPClientBindingListResponse> {
    return this.request<MCPClientBindingListResponse>('/mcp/bindings');
  }

  async upsertMCPBinding(data: MCPClientBindingUpsert): Promise<MCPClientBinding> {
    return this.request<MCPClientBinding>('/mcp/bindings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteMCPBinding(clientId: string): Promise<{ deleted: string }> {
    return this.request<{ deleted: string }>(`/mcp/bindings/${encodeURIComponent(clientId)}`, {
      method: 'DELETE',
    });
  }

  // AI Video Assistant
  async checkAIPlanningProvider(checkExec = false): Promise<AIPlanningProviderCheckResponse> {
    const suffix = checkExec ? '?check_exec=true' : '';
    return this.request<AIPlanningProviderCheckResponse>(`/ai-video/planning/check${suffix}`);
  }

  async listVideoProjects(): Promise<VideoProjectResponse[]> {
    return this.request<VideoProjectResponse[]>('/ai-video/projects');
  }

  async listNewsVideoProjects(): Promise<VideoProjectResponse[]> {
    return this.request<VideoProjectResponse[]>('/news-video/projects');
  }

  async createNewsVideoProject(data: VideoProjectCreate): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>('/news-video/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getNewsVideoProject(projectId: string): Promise<VideoProjectDetailResponse> {
    return this.request<VideoProjectDetailResponse>(`/news-video/projects/${projectId}`);
  }

  async updateNewsVideoProject(projectId: string, data: Partial<VideoProjectUpdate> & { speech_mode?: NewsSpeechMode }): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>(`/news-video/projects/${projectId}`, { method: 'PATCH', body: JSON.stringify(data) });
  }

  async updateNewsVideoShot(projectId: string, shotId: string, data: Partial<VideoShotUpdate> & { speech_mode?: NewsSpeechMode }): Promise<VideoShotResponse> {
    return this.request<VideoShotResponse>(`/news-video/projects/${projectId}/shots/${shotId}`, { method: 'PATCH', body: JSON.stringify(data) });
  }

  async planNewsVideoProject(projectId: string): Promise<VideoShotResponse[]> {
    return this.request<VideoShotResponse[]>(`/news-video/projects/${projectId}/plan`, { method: 'POST' });
  }

  async generateNewsVideoPrompts(projectId: string): Promise<VideoShotPromptPackResponse> {
    return this.request<VideoShotPromptPackResponse>(`/news-video/projects/${projectId}/prompts`, { method: 'POST' });
  }

  async getNewsVideoPrompt(projectId: string, shotId: string): Promise<VideoPromptContentResponse> {
    return this.request<VideoPromptContentResponse>(`/news-video/projects/${projectId}/shots/${shotId}/prompt`);
  }

  async downloadNewsVideoPromptPack(projectId: string): Promise<DownloadedBlob> {
    return this.download(`/news-video/projects/${projectId}/prompt-pack`, `news-video-prompts-${projectId}.txt`);
  }

  async getVideoProjectCharacterFlow(projectId: string): Promise<VideoProjectCharacterFlowResponse> {
    return this.request<VideoProjectCharacterFlowResponse>(
      `/ai-video/projects/${projectId}/character-flow`,
    );
  }

  async decideVideoProjectCharacterProposal(
    projectId: string,
    proposalId: string,
    data: CharacterProposalDecisionRequest,
  ): Promise<CharacterProposalDecisionResponse> {
    return this.request<CharacterProposalDecisionResponse>(
      `/ai-video/projects/${projectId}/character-proposals/${proposalId}/decision`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listVideoSeries(): Promise<VideoSeriesResponse[]> {
    return this.request<VideoSeriesResponse[]>('/ai-video/series');
  }

  async createVideoSeries(data: VideoSeriesCreate): Promise<VideoSeriesResponse> {
    return this.request<VideoSeriesResponse>('/ai-video/series', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateVideoSeries(seriesId: string, data: VideoSeriesUpdate): Promise<VideoSeriesResponse> {
    return this.request<VideoSeriesResponse>(`/ai-video/series/${seriesId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async listSeriesCharacterProfiles(seriesId: string): Promise<SeriesCharacterProfileResponse[]> {
    return this.request<SeriesCharacterProfileResponse[]>(
      `/ai-video/series/${seriesId}/character-profiles`,
    );
  }

  async createSeriesCharacterProfile(
    seriesId: string,
    data: SeriesCharacterProfileCreate,
  ): Promise<SeriesCharacterProfileResponse> {
    return this.request<SeriesCharacterProfileResponse>(
      `/ai-video/series/${seriesId}/character-profiles`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async updateSeriesCharacterProfile(
    seriesId: string,
    profileId: string,
    data: SeriesCharacterProfileUpdate,
  ): Promise<SeriesCharacterProfileResponse> {
    return this.request<SeriesCharacterProfileResponse>(
      `/ai-video/series/${seriesId}/character-profiles/${profileId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteSeriesCharacterProfile(seriesId: string, profileId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(
      `/ai-video/series/${seriesId}/character-profiles/${profileId}`,
      {
        method: 'DELETE',
      },
    );
  }

  async listSeriesReferenceAssets(
    seriesId: string,
    query: {
      entity_type?: string | null;
      entity_id?: string | null;
      approval_status?: string | null;
      active?: boolean | null;
    } = {},
  ): Promise<SeriesReferenceAssetListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<SeriesReferenceAssetListResponse>(
      `/ai-video/series/${seriesId}/reference-assets${suffix}`,
    );
  }

  async uploadSeriesReferenceAsset(
    seriesId: string,
    data: {
      file: File;
      entity_type: string;
      entity_id: string;
      reference_role: string;
      label?: string | null;
      source_type?: string | null;
    },
  ): Promise<SeriesReferenceAssetResponse> {
    const formData = new FormData();
    formData.append('file', data.file);
    formData.append('entity_type', data.entity_type);
    formData.append('entity_id', data.entity_id);
    formData.append('reference_role', data.reference_role);
    if (data.label) formData.append('label', data.label);
    if (data.source_type) formData.append('source_type', data.source_type);
    return this.request<SeriesReferenceAssetResponse>(
      `/ai-video/series/${seriesId}/reference-assets`,
      {
        method: 'POST',
        body: formData,
      },
    );
  }

  async updateSeriesReferenceAssetStatus(
    seriesId: string,
    assetId: string,
    data: SeriesReferenceAssetStatusRequest,
  ): Promise<SeriesReferenceAssetResponse> {
    return this.request<SeriesReferenceAssetResponse>(
      `/ai-video/series/${seriesId}/reference-assets/${assetId}/status`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteSeriesReferenceAsset(
    seriesId: string,
    assetId: string,
  ): Promise<{ deleted: boolean; archived: boolean; dependency_count: number }> {
    return this.request<{ deleted: boolean; archived: boolean; dependency_count: number }>(
      `/ai-video/series/${seriesId}/reference-assets/${assetId}`,
      {
        method: 'DELETE',
      },
    );
  }

  async getSeriesVersionHistory(
    seriesId: string,
    entityType: string,
    entityId: string,
  ): Promise<SeriesVersionHistoryResponse> {
    return this.request<SeriesVersionHistoryResponse>(
      `/ai-video/series/${seriesId}/versions/${entityType}/${entityId}`,
    );
  }

  async recordSeriesArtifactDependencies(
    seriesId: string,
    data: ArtifactDependencyRecordRequest,
  ): Promise<ArtifactDependencySnapshotResponse[]> {
    return this.request<ArtifactDependencySnapshotResponse[]>(
      `/ai-video/series/${seriesId}/dependencies`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listSeriesArtifactDependencies(
    seriesId: string,
    artifactType: string,
    artifactId: string,
  ): Promise<ArtifactDependencySnapshotResponse[]> {
    return this.request<ArtifactDependencySnapshotResponse[]>(
      `/ai-video/series/${seriesId}/dependencies/${artifactType}/${artifactId}`,
    );
  }

  async listSeriesStaleEvents(
    seriesId: string,
    query: { status?: string | null; artifact_type?: string | null; limit?: number | null } = {},
  ): Promise<ArtifactStaleEventListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<ArtifactStaleEventListResponse>(
      `/ai-video/series/${seriesId}/stale-events${suffix}`,
    );
  }

  async markSeriesDependencyStale(
    seriesId: string,
    data: ArtifactStaleMarkRequest,
  ): Promise<ArtifactStaleEventListResponse> {
    return this.request<ArtifactStaleEventListResponse>(
      `/ai-video/series/${seriesId}/stale-events/mark`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async requestSeriesTargetedRegeneration(
    seriesId: string,
    data: ArtifactTargetedRegenerationRequest,
  ): Promise<ArtifactTargetedRegenerationResponse> {
    return this.request<ArtifactTargetedRegenerationResponse>(
      `/ai-video/series/${seriesId}/stale-events/regenerate`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async suggestSeriesCharacterProfiles(
    seriesId: string,
  ): Promise<SeriesCharacterProfileSuggestionResponse> {
    return this.request<SeriesCharacterProfileSuggestionResponse>(
      `/ai-video/series/${seriesId}/character-profile-suggestions`,
      {
        method: 'POST',
      },
    );
  }

  async listSeriesMemoryCards(
    seriesId: string,
    query: {
      card_type?: string | null;
      status?: string | null;
      episode_number?: number | null;
      entity_ref?: string | null;
      tag?: string | null;
      min_importance?: number | null;
    } = {},
  ): Promise<SeriesMemoryCardListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<SeriesMemoryCardListResponse>(
      `/ai-video/series/${seriesId}/memory-cards${suffix}`,
    );
  }

  async createSeriesMemoryCard(
    seriesId: string,
    data: SeriesMemoryCardCreate,
  ): Promise<SeriesMemoryCardResponse> {
    return this.request<SeriesMemoryCardResponse>(`/ai-video/series/${seriesId}/memory-cards`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async suggestSeriesMemoryCards(
    seriesId: string,
    data: SeriesMemorySuggestionRequest = {},
  ): Promise<SeriesMemorySuggestionResponse> {
    return this.request<SeriesMemorySuggestionResponse>(
      `/ai-video/series/${seriesId}/memory-cards/suggestions`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async updateSeriesMemoryCard(
    seriesId: string,
    cardId: string,
    data: SeriesMemoryCardUpdate,
  ): Promise<SeriesMemoryCardResponse> {
    return this.request<SeriesMemoryCardResponse>(
      `/ai-video/series/${seriesId}/memory-cards/${cardId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async setSeriesMemoryCardStatus(
    seriesId: string,
    cardId: string,
    data: SeriesMemoryCardStatusRequest,
  ): Promise<SeriesMemoryCardResponse> {
    return this.request<SeriesMemoryCardResponse>(
      `/ai-video/series/${seriesId}/memory-cards/${cardId}/status`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteSeriesMemoryCard(seriesId: string, cardId: string): Promise<{ deleted: boolean }> {
    return this.request<{ deleted: boolean }>(
      `/ai-video/series/${seriesId}/memory-cards/${cardId}`,
      {
        method: 'DELETE',
      },
    );
  }

  async listSeriesCurrentStates(seriesId: string): Promise<SeriesCurrentStateListResponse> {
    return this.request<SeriesCurrentStateListResponse>(
      `/ai-video/series/${seriesId}/current-states`,
    );
  }

  async createSeriesCurrentState(
    seriesId: string,
    data: SeriesCurrentStateCreate,
  ): Promise<SeriesCurrentStateResponse> {
    return this.request<SeriesCurrentStateResponse>(
      `/ai-video/series/${seriesId}/current-states`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async proposeSeriesCurrentState(
    seriesId: string,
    data: SeriesStateProposalRequest,
  ): Promise<SeriesCurrentStateResponse> {
    return this.request<SeriesCurrentStateResponse>(
      `/ai-video/series/${seriesId}/current-states/propose`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async updateSeriesCurrentState(
    seriesId: string,
    stateId: string,
    data: SeriesCurrentStateUpdate,
  ): Promise<SeriesCurrentStateResponse> {
    return this.request<SeriesCurrentStateResponse>(
      `/ai-video/series/${seriesId}/current-states/${stateId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async setSeriesCurrentStateStatus(
    seriesId: string,
    stateId: string,
    data: SeriesCurrentStateStatusRequest,
  ): Promise<SeriesCurrentStateResponse> {
    return this.request<SeriesCurrentStateResponse>(
      `/ai-video/series/${seriesId}/current-states/${stateId}/status`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async compileSeriesContext(
    seriesId: string,
    data: SeriesContextCompileRequest,
  ): Promise<SeriesContextCompileResponse> {
    return this.request<SeriesContextCompileResponse>(
      `/ai-video/series/${seriesId}/context/compile`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listSeriesContextTraces(
    seriesId: string,
    query: {
      task_type?: string | null;
      project_id?: string | null;
      story_episode_id?: string | null;
      limit?: number | null;
    } = {},
  ): Promise<SeriesContextTraceListResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<SeriesContextTraceListResponse>(
      `/ai-video/series/${seriesId}/context/traces${suffix}`,
    );
  }

  async checkSeriesCanon(
    seriesId: string,
    data: SeriesCanonCheckRequest,
  ): Promise<SeriesCanonCheckResponse> {
    return this.request<SeriesCanonCheckResponse>(`/ai-video/series/${seriesId}/canon-check`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listSeriesCanonChecks(
    seriesId: string,
    query: {
      project_id?: string | null;
      story_episode_id?: string | null;
      limit?: number | null;
    } = {},
  ): Promise<SeriesCanonCheckResponse[]> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<SeriesCanonCheckResponse[]>(
      `/ai-video/series/${seriesId}/canon-checks${suffix}`,
    );
  }

  async listStoryStudioSeries(): Promise<VideoSeriesResponse[]> {
    return this.request<VideoSeriesResponse[]>('/story-studio/series');
  }

  async listStoryEpisodes(seriesId: string): Promise<StoryEpisodeResponse[]> {
    return this.request<StoryEpisodeResponse[]>(`/story-studio/series/${seriesId}/episodes`);
  }

  async createStoryEpisode(
    seriesId: string,
    data: StoryEpisodeCreate,
  ): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(`/story-studio/series/${seriesId}/episodes`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStoryEpisode(episodeId: string): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(`/story-studio/episodes/${episodeId}`);
  }

  async updateStoryEpisode(
    episodeId: string,
    data: StoryEpisodeUpdate,
  ): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(`/story-studio/episodes/${episodeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async generateStoryCandidates(episodeId: string): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(`/story-studio/episodes/${episodeId}/candidates`, {
      method: 'POST',
    });
  }

  async scoreStoryCandidates(episodeId: string): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(
      `/story-studio/episodes/${episodeId}/candidates/score`,
      {
        method: 'POST',
      },
    );
  }

  async selectStoryMaster(
    episodeId: string,
    data: StoryCandidateSelectionRequest,
  ): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(`/story-studio/episodes/${episodeId}/master-story`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async synthesizeStoryMaster(
    episodeId: string,
    data: StoryCandidateSynthesisRequest,
  ): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(
      `/story-studio/episodes/${episodeId}/master-story/synthesize`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async approveStoryMaster(
    episodeId: string,
    data: StoryApprovalRequest,
  ): Promise<StoryEpisodeResponse> {
    return this.request<StoryEpisodeResponse>(
      `/story-studio/episodes/${episodeId}/master-story/approval`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async createStoryImageAdaptation(episodeId: string): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation`,
      {
        method: 'POST',
      },
    );
  }

  async approveStoryImagePrompts(
    episodeId: string,
    data: StoryPanelPromptApprovalRequest,
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation/prompts/approval`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async updateStoryImagePanel(
    episodeId: string,
    data: StoryPanelPromptUpdateRequest,
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation/panel`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async repairStoryImagePanel(
    episodeId: string,
    data: StoryPromptRepairRequest,
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation/panel/repair`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async requestStoryImageRender(
    episodeId: string,
    data: StoryImageRenderRequest = {},
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation/render`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async updateStoryImageRenderJob(
    episodeId: string,
    renderJobId: string,
    data: StoryImageRenderJobUpdateRequest,
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/image-adaptation/render/jobs/${renderJobId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async exportStoryImagePrompts(episodeId: string): Promise<string> {
    const response = await fetch(
      `${this.getBaseUrl()}/story-studio/episodes/${episodeId}/image-adaptation/prompts/export`,
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.text();
  }

  async createStoryVideoAdaptation(
    episodeId: string,
    data: StoryVideoHandoffRequest = { open_existing: true },
  ): Promise<StoryAdaptationResponse> {
    return this.request<StoryAdaptationResponse>(
      `/story-studio/episodes/${episodeId}/video-adaptation`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async suggestStoryUpdates(episodeId: string): Promise<StorySuggestionResponse> {
    return this.request<StorySuggestionResponse>(`/story-studio/episodes/${episodeId}/suggestions`, {
      method: 'POST',
    });
  }

  async approveStoryUpdates(
    episodeId: string,
    data: StorySuggestionApprovalRequest,
  ): Promise<StorySuggestionResponse> {
    return this.request<StorySuggestionResponse>(
      `/story-studio/episodes/${episodeId}/suggestions/approval`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteVideoSeries(
    seriesId: string,
    options: { deleteEpisodes?: boolean; confirmDeleteEpisodes?: boolean } = {},
  ): Promise<{ message: string }> {
    const params = new URLSearchParams();
    if (options.deleteEpisodes) params.set('delete_episodes', 'true');
    if (options.confirmDeleteEpisodes) params.set('confirm_delete_episodes', 'true');
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return this.request<{ message: string }>(`/ai-video/series/${seriesId}${suffix}`, {
      method: 'DELETE',
    });
  }

  async createVideoSeriesEpisode(
    seriesId: string,
    data: VideoEpisodeCreate,
  ): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>(`/ai-video/series/${seriesId}/episodes`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createVideoProject(data: VideoProjectCreate): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>('/ai-video/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getVideoProject(projectId: string): Promise<VideoProjectDetailResponse> {
    return this.request<VideoProjectDetailResponse>(`/ai-video/projects/${projectId}`);
  }

  async getVideoProjectMemory(projectId: string): Promise<VideoProjectMemoryListResponse> {
    return this.request<VideoProjectMemoryListResponse>(`/ai-video/projects/${projectId}/memory`);
  }

  async getVideoProjectTargetTimeline(
    projectId: string,
  ): Promise<VideoProjectTargetTimelineResponse> {
    return this.request<VideoProjectTargetTimelineResponse>(
      `/ai-video/projects/${projectId}/target-timeline`,
    );
  }

  async compileVideoProjectContext(
    projectId: string,
    data: VideoProjectContextCompileRequest,
  ): Promise<VideoProjectContextSnapshotResponse> {
    return this.request<VideoProjectContextSnapshotResponse>(
      `/ai-video/projects/${projectId}/context/compile`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listVideoProjectContextSnapshots(
    projectId: string,
    limit = 20,
  ): Promise<VideoProjectContextSnapshotListResponse> {
    return this.request<VideoProjectContextSnapshotListResponse>(
      `/ai-video/projects/${projectId}/context/snapshots?limit=${limit}`,
    );
  }

  async runVideoProjectQualityReport(
    projectId: string,
    data: VideoQualityRunRequest = {},
  ): Promise<VideoQualityReportResponse> {
    return this.request<VideoQualityReportResponse>(
      `/ai-video/projects/${projectId}/quality/reports`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async getLatestVideoProjectQualityReport(
    projectId: string,
  ): Promise<VideoQualityReportResponse | null> {
    return this.request<VideoQualityReportResponse | null>(
      `/ai-video/projects/${projectId}/quality/reports/latest`,
    );
  }

  async listVideoProjectQualityReports(
    projectId: string,
    limit = 20,
  ): Promise<VideoQualityReportListResponse> {
    return this.request<VideoQualityReportListResponse>(
      `/ai-video/projects/${projectId}/quality/reports?limit=${limit}`,
    );
  }

  async overrideVideoQualityReport(
    reportId: string,
    data: VideoQualityOverrideRequest,
  ): Promise<VideoQualityReportResponse> {
    return this.request<VideoQualityReportResponse>(
      `/ai-video/quality/reports/${reportId}/override`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async createVideoProjectRetentionDataset(
    projectId: string,
    data: PlatformRetentionDatasetCreateRequest,
  ): Promise<PlatformRetentionDatasetResponse> {
    return this.request<PlatformRetentionDatasetResponse>(
      `/ai-video/projects/${projectId}/retention-datasets`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listVideoProjectRetentionDatasets(
    projectId: string,
    limit = 20,
  ): Promise<PlatformRetentionDatasetListResponse> {
    return this.request<PlatformRetentionDatasetListResponse>(
      `/ai-video/projects/${projectId}/retention-datasets?limit=${limit}`,
    );
  }

  async updateVideoProject(
    projectId: string,
    data: VideoProjectUpdate,
  ): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>(`/ai-video/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async localizeVideoProject(
    projectId: string,
    data: VideoProjectLocalizeRequest,
  ): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>(`/ai-video/projects/${projectId}/localize`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteVideoProject(projectId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/ai-video/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  async resetVideoProjectGeneratedData(
    projectId: string,
  ): Promise<VideoGeneratedDataResetResponse> {
    return this.request<VideoGeneratedDataResetResponse>(
      `/ai-video/projects/${projectId}/reset-generated-data`,
      {
        method: 'POST',
      },
    );
  }

  async updateVideoSeriesSummaryFromProject(
    projectId: string,
    summary?: string,
  ): Promise<VideoSeriesResponse> {
    return this.request<VideoSeriesResponse>(`/ai-video/projects/${projectId}/series-summary`, {
      method: 'POST',
      body: JSON.stringify({ summary: summary || null }),
    });
  }

  async getVideoProjectStatus(projectId: string): Promise<VideoProjectStatusResponse> {
    return this.request<VideoProjectStatusResponse>(`/ai-video/projects/${projectId}/status`);
  }

  async getVideoPublishingMetadata(projectId: string): Promise<VideoPublishingMetadataResponse> {
    return this.request<VideoPublishingMetadataResponse>(
      `/ai-video/projects/${projectId}/publishing-metadata`,
    );
  }

  async generateVideoPublishingMetadata(
    projectId: string,
    data: VideoPublishingMetadataGenerateRequest = {},
  ): Promise<VideoPublishingMetadataResponse> {
    return this.request<VideoPublishingMetadataResponse>(
      `/ai-video/projects/${projectId}/publishing-metadata`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async startVideoAutoRun(
    projectId: string,
    data: VideoAutoRunStartRequest,
  ): Promise<VideoAutoRunResponse> {
    return this.request<VideoAutoRunResponse>(`/ai-video/projects/${projectId}/auto-runs`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getLatestVideoAutoRun(projectId: string): Promise<VideoAutoRunResponse | null> {
    return this.request<VideoAutoRunResponse | null>(
      `/ai-video/projects/${projectId}/auto-runs/latest`,
    );
  }

  async getVideoAutoRun(projectId: string, runId: string): Promise<VideoAutoRunResponse> {
    return this.request<VideoAutoRunResponse>(`/ai-video/projects/${projectId}/auto-runs/${runId}`);
  }

  async continueVideoAutoRun(
    projectId: string,
    runId: string,
    data: VideoAutoRunContinueRequest = { approved: true },
  ): Promise<VideoAutoRunResponse> {
    return this.request<VideoAutoRunResponse>(
      `/ai-video/projects/${projectId}/auto-runs/${runId}/continue`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async cancelVideoAutoRun(projectId: string, runId: string): Promise<VideoAutoRunResponse> {
    return this.request<VideoAutoRunResponse>(
      `/ai-video/projects/${projectId}/auto-runs/${runId}/cancel`,
      {
        method: 'POST',
      },
    );
  }

  async retryVideoAutoRun(
    projectId: string,
    runId: string,
    data: VideoAutoRunRetryRequest = {},
  ): Promise<VideoAutoRunResponse> {
    return this.request<VideoAutoRunResponse>(
      `/ai-video/projects/${projectId}/auto-runs/${runId}/retry`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async getDefaultVeoProviderSession(): Promise<VideoProviderSessionResponse | null> {
    return this.request<VideoProviderSessionResponse | null>('/ai-video/provider-sessions/veo/default');
  }

  async openVeoProviderLogin(
    data: VideoProviderSessionOpenRequest = { provider: 'veo' },
  ): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>('/ai-video/provider-sessions/veo/open-login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async checkVeoProviderSession(): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>('/ai-video/provider-sessions/veo/check', {
      method: 'POST',
    });
  }

  async updateVeoProviderSessionLabel(
    sessionId: string,
    data: VideoProviderSessionLabelUpdate,
  ): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>(
      `/ai-video/provider-sessions/${sessionId}/label`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async confirmVeoProviderSessionIdentity(sessionId: string): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>(
      `/ai-video/provider-sessions/${sessionId}/confirm-identity`,
      { method: 'POST' },
    );
  }

  async invalidateVeoProviderSession(sessionId: string): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>(
      `/ai-video/provider-sessions/${sessionId}/invalidate`,
      { method: 'POST' },
    );
  }

  async changeVeoProviderAccount(sessionId: string): Promise<VideoProviderSessionResponse> {
    return this.request<VideoProviderSessionResponse>(
      `/ai-video/provider-sessions/${sessionId}/change-account`,
      { method: 'POST' },
    );
  }

  async startVideoClipGenerationJob(
    projectId: string,
    data: VideoClipGenerationJobStartRequest,
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async getLatestVideoClipGenerationJob(
    projectId: string,
  ): Promise<VideoClipGenerationJobResponse | null> {
    return this.request<VideoClipGenerationJobResponse | null>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/latest`,
    );
  }

  async getVideoClipGenerationJob(
    projectId: string,
    jobId: string,
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/${jobId}`,
    );
  }

  async getVideoProviderProjectBinding(
    projectId: string,
  ): Promise<VideoProviderProjectBindingResponse | null> {
    return this.request<VideoProviderProjectBindingResponse | null>(
      `/ai-video/projects/${projectId}/provider-flow/binding`,
    );
  }

  async openVideoProviderProjectBinding(
    projectId: string,
  ): Promise<VideoProviderProjectBindingResponse> {
    return this.request<VideoProviderProjectBindingResponse>(
      `/ai-video/projects/${projectId}/provider-flow/open`,
      { method: 'POST' },
    );
  }

  async retryVideoClipGenerationJob(
    projectId: string,
    jobId: string,
    data: VideoClipGenerationRetryRequest = {},
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/${jobId}/retry`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async resumeVideoClipGenerationJob(
    projectId: string,
    jobId: string,
    data: VideoClipGenerationResumeRequest = {},
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/${jobId}/resume`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async cancelVideoClipGenerationJob(
    projectId: string,
    jobId: string,
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/${jobId}/cancel`,
      { method: 'POST' },
    );
  }

  async approveVideoClipGenerationCredit(
    projectId: string,
    jobId: string,
    itemId: string,
    data: VideoClipGenerationCreditApprovalRequest = { approve: true },
  ): Promise<VideoClipGenerationJobResponse> {
    return this.request<VideoClipGenerationJobResponse>(
      `/ai-video/projects/${projectId}/clip-generation/jobs/${jobId}/items/${itemId}/credit`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async listVideoSourceBlocks(projectId: string): Promise<VideoSourceBlockResponse[]> {
    return this.request<VideoSourceBlockResponse[]>(
      `/ai-video/projects/${projectId}/source-blocks`,
    );
  }

  async createVideoSourceBlock(
    projectId: string,
    data: VideoSourceBlockCreate,
  ): Promise<VideoSourceBlockResponse> {
    return this.request<VideoSourceBlockResponse>(`/ai-video/projects/${projectId}/source-blocks`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateVideoSourceBlock(
    projectId: string,
    blockId: string,
    data: VideoSourceBlockUpdate,
  ): Promise<VideoSourceBlockResponse> {
    return this.request<VideoSourceBlockResponse>(
      `/ai-video/projects/${projectId}/source-blocks/${blockId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteVideoSourceBlock(
    projectId: string,
    blockId: string,
    confirmDeleteLast = false,
  ): Promise<{ message: string }> {
    const suffix = confirmDeleteLast ? '?confirm_delete_last=true' : '';
    return this.request<{ message: string }>(
      `/ai-video/projects/${projectId}/source-blocks/${blockId}${suffix}`,
      {
        method: 'DELETE',
      },
    );
  }

  async developVideoStory(projectId: string, force = false): Promise<VideoProjectDetailResponse> {
    return this.request<VideoProjectDetailResponse>(`/ai-video/projects/${projectId}/story`, {
      method: 'POST',
      body: JSON.stringify({ force }),
    });
  }

  async approveVideoStory(projectId: string, approved: boolean): Promise<VideoProjectResponse> {
    return this.request<VideoProjectResponse>(`/ai-video/projects/${projectId}/story/approval`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    });
  }

  async generateVideoShots(projectId: string): Promise<VideoShotResponse[]> {
    return this.request<VideoShotResponse[]>(`/ai-video/projects/${projectId}/shots`, {
      method: 'POST',
    });
  }

  async updateVideoShot(
    projectId: string,
    shotId: string,
    data: Partial<VideoShotResponse>,
  ): Promise<VideoShotResponse> {
    return this.request<VideoShotResponse>(`/ai-video/projects/${projectId}/shots/${shotId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async lockVideoShot(
    projectId: string,
    shotId: string,
    locked: boolean,
  ): Promise<VideoShotResponse> {
    return this.request<VideoShotResponse>(`/ai-video/projects/${projectId}/shots/${shotId}/lock`, {
      method: 'POST',
      body: JSON.stringify({ locked }),
    });
  }

  async regenerateVideoShot(projectId: string, shotId: string): Promise<VideoShotResponse> {
    return this.request<VideoShotResponse>(
      `/ai-video/projects/${projectId}/shots/${shotId}/regenerate`,
      {
        method: 'POST',
      },
    );
  }

  async generateVideoProjectPlan(projectId: string): Promise<VideoProjectDetailResponse> {
    return this.request<VideoProjectDetailResponse>(`/ai-video/projects/${projectId}/plan`, {
      method: 'POST',
    });
  }

  async approveVideoScene(
    projectId: string,
    sceneId: string,
    approved: boolean,
  ): Promise<VideoSceneResponse> {
    return this.request<VideoSceneResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/approval`,
      {
        method: 'POST',
        body: JSON.stringify({ approved }),
      },
    );
  }

  async regenerateVideoScene(projectId: string, sceneId: string): Promise<VideoSceneResponse> {
    return this.request<VideoSceneResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/regenerate`,
      { method: 'POST' },
    );
  }

  async setVideoSceneNoNarration(
    projectId: string,
    sceneId: string,
    noNarration: boolean,
  ): Promise<VideoSceneResponse> {
    return this.request<VideoSceneResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/no-narration`,
      {
        method: 'POST',
        body: JSON.stringify({ no_narration: noNarration }),
      },
    );
  }

  async generateVideoPromptPack(
    projectId: string,
  ): Promise<VideoShotPromptPackResponse | { project_id: string }> {
    return this.request<VideoShotPromptPackResponse | { project_id: string }>(
      `/ai-video/projects/${projectId}/prompts`,
      {
        method: 'POST',
      },
    );
  }

  async getVideoShotPrompt(projectId: string, shotId: string): Promise<VideoPromptContentResponse> {
    return this.request<VideoPromptContentResponse>(
      `/ai-video/projects/${projectId}/shots/${shotId}/prompt`,
    );
  }

  async downloadVideoShotPrompt(projectId: string, shotId: string): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/shots/${shotId}/prompt/download`,
      'Prompt video.txt',
    );
  }

  async getVideoShotClip(projectId: string, shotId: string): Promise<VideoShotClipResponse | null> {
    return this.request<VideoShotClipResponse | null>(
      `/ai-video/projects/${projectId}/shots/${shotId}/clip`,
    );
  }

  getVideoShotClipDownloadUrl(projectId: string, shotId: string): string {
    return `${this.getBaseUrl()}/ai-video/projects/${projectId}/shots/${shotId}/clip/download`;
  }

  async downloadVideoShotClip(
    projectId: string,
    shotId: string,
    fallbackFilename = 'clip.mp4',
  ): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/shots/${shotId}/clip/download`,
      fallbackFilename,
    );
  }

  async uploadVideoShotClip(
    projectId: string,
    shotId: string,
    file: File,
    provider?: string,
  ): Promise<VideoShotClipResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (provider) formData.append('provider', provider);
    const response = await fetch(
      `${this.getBaseUrl()}/ai-video/projects/${projectId}/shots/${shotId}/clip`,
      {
        method: 'POST',
        body: formData,
      },
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  /**
   * Uploads one clip per matched entry, a few at a time. Each file gets its own request so
   * the existing per-file validation applies unchanged and one rejected file never discards
   * the others -- a partially loaded batch is still useful.
   */
  async uploadVideoShotClipBatch(
    projectId: string,
    entries: VideoShotClipBatchEntry[],
    options?: {
      provider?: string;
      concurrency?: number;
      onProgress?: (done: number, total: number) => void;
    },
  ): Promise<VideoShotClipBatchResult> {
    return runClipBatchUpload(
      entries,
      (entry) => this.uploadVideoShotClip(projectId, entry.shotId, entry.file, options?.provider),
      { concurrency: options?.concurrency, onProgress: options?.onProgress },
    );
  }

  async deleteVideoShotClip(projectId: string, shotId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(
      `/ai-video/projects/${projectId}/shots/${shotId}/clip`,
      {
        method: 'DELETE',
      },
    );
  }

  async getVideoScenePrompt(
    projectId: string,
    sceneId: string,
  ): Promise<VideoPromptContentResponse> {
    return this.request<VideoPromptContentResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/prompt`,
    );
  }

  async downloadVideoScenePrompt(projectId: string, sceneId: string): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/prompt/download`,
      'Prompt ảnh.txt',
    );
  }

  async uploadVideoPreviewImage(
    projectId: string,
    sceneId: string,
    file: File,
  ): Promise<VideoSceneAssetResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(
      `${this.getBaseUrl()}/ai-video/projects/${projectId}/scenes/${sceneId}/preview-image`,
      { method: 'POST', body: formData },
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  async createVideoSceneVoice(
    projectId: string,
    sceneId: string,
    data: VideoSceneNarrationRequest,
  ): Promise<VideoSceneVoiceStatusResponse> {
    return this.request<VideoSceneVoiceStatusResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/voice`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  }

  async getVideoSceneVoiceStatus(
    projectId: string,
    sceneId: string,
  ): Promise<VideoSceneVoiceStatusResponse> {
    return this.request<VideoSceneVoiceStatusResponse>(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/voice/status`,
    );
  }

  async downloadVideoSceneVoice(projectId: string, sceneId: string): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/scenes/${sceneId}/voice/download`,
      'Giọng đọc.wav',
    );
  }

  getVideoSceneVoiceUrl(projectId: string, sceneId: string): string {
    return `${this.getBaseUrl()}/ai-video/projects/${projectId}/scenes/${sceneId}/voice/download`;
  }

  async createVideoShotVoice(
    projectId: string,
    shotId: string,
    data: VideoSceneNarrationRequest,
  ): Promise<VideoShotVoiceStatusResponse> {
    return this.request<VideoShotVoiceStatusResponse>(
      `/ai-video/projects/${projectId}/shots/${shotId}/voice`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  }

  async getVideoShotVoiceStatus(
    projectId: string,
    shotId: string,
  ): Promise<VideoShotVoiceStatusResponse> {
    return this.request<VideoShotVoiceStatusResponse>(
      `/ai-video/projects/${projectId}/shots/${shotId}/voice/status`,
    );
  }

  async downloadVideoShotVoice(projectId: string, shotId: string): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/shots/${shotId}/voice/download`,
      'Giọng đọc.wav',
    );
  }

  getVideoShotVoiceUrl(projectId: string, shotId: string): string {
    return `${this.getBaseUrl()}/ai-video/projects/${projectId}/shots/${shotId}/voice/download`;
  }

  async generateVideoSubtitle(projectId: string): Promise<VideoSubtitleResponse> {
    return this.request<VideoSubtitleResponse>(`/ai-video/projects/${projectId}/subtitle`, {
      method: 'POST',
    });
  }

  async downloadVideoSubtitle(projectId: string): Promise<DownloadedBlob> {
    return this.download(`/ai-video/projects/${projectId}/subtitle/download`, 'Phụ đề.srt');
  }

  async getVideoRenderReadiness(
    projectId: string,
    settings: VideoRenderSettings,
  ): Promise<VideoRenderReadinessResponse> {
    const params = new URLSearchParams({
      resolution: settings.resolution,
      fps: String(settings.fps),
      fit_mode: settings.fit_mode,
      duration_mode: settings.duration_mode,
      subtitle_mode: settings.subtitle_mode,
      mute_clip_audio: String(settings.mute_clip_audio),
      clip_audio_mode: clipAudioChoiceFromSettings(settings),
      enhanced_render: String(settings.enhanced_render ?? false),
      enhanced_audio: String(settings.enhanced_audio ?? true),
      ai_review: String(settings.ai_review ?? true),
      max_fix_attempts: String(settings.max_fix_attempts ?? 1),
      watermark_cleanup: String(settings.watermark_cleanup ?? false),
      watermark_backend: settings.watermark_backend ?? 'cv2',
    });
    return this.request<VideoRenderReadinessResponse>(
      `/ai-video/projects/${projectId}/render/readiness?${params.toString()}`,
    );
  }

  async listVideoRenderSfxAssets(projectId: string): Promise<VideoRenderSfxAssetResponse[]> {
    return this.request<VideoRenderSfxAssetResponse[]>(
      `/ai-video/projects/${projectId}/render/sfx-assets`,
    );
  }

  async uploadVideoRenderSfxAsset(
    projectId: string,
    file: File,
  ): Promise<VideoRenderSfxAssetResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(
      `${this.getBaseUrl()}/ai-video/projects/${projectId}/render/sfx-assets`,
      {
        method: 'POST',
        body: formData,
      },
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  async deleteVideoRenderSfxAsset(projectId: string, assetId: string): Promise<{ deleted: boolean }> {
    return this.request<{ deleted: boolean }>(
      `/ai-video/projects/${projectId}/render/sfx-assets/${assetId}`,
      { method: 'DELETE' },
    );
  }

  async listVideoRenderJobs(projectId: string): Promise<VideoRenderJobResponse[]> {
    return this.request<VideoRenderJobResponse[]>(`/ai-video/projects/${projectId}/render/jobs`);
  }

  async getLatestVideoRenderJob(projectId: string): Promise<VideoRenderJobResponse | null> {
    return this.request<VideoRenderJobResponse | null>(
      `/ai-video/projects/${projectId}/render/jobs/latest`,
    );
  }

  async getVideoRenderJob(projectId: string, jobId: string): Promise<VideoRenderJobResponse> {
    return this.request<VideoRenderJobResponse>(
      `/ai-video/projects/${projectId}/render/jobs/${jobId}`,
    );
  }

  async createVideoRenderJob(
    projectId: string,
    settings: VideoRenderSettings,
  ): Promise<VideoRenderJobResponse> {
    return this.request<VideoRenderJobResponse>(`/ai-video/projects/${projectId}/render/jobs`, {
      method: 'POST',
      body: JSON.stringify({ settings }),
    });
  }

  async downloadVideoRenderJob(projectId: string, jobId: string): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/render/jobs/${jobId}/download`,
      'Video hoàn chỉnh.mp4',
    );
  }

  getVideoRenderJobDownloadUrl(projectId: string, jobId: string): string {
    return `${this.getBaseUrl()}/ai-video/projects/${projectId}/render/jobs/${jobId}/download`;
  }

  async downloadVideoRenderEnhancedArtifact(
    projectId: string,
    jobId: string,
    artifactKey: string,
  ): Promise<DownloadedBlob> {
    return this.download(
      `/ai-video/projects/${projectId}/render/jobs/${jobId}/enhanced-artifacts/${encodeURIComponent(artifactKey)}`,
      'Báo cáo enhanced render.md',
    );
  }

  async getVideoPackageReadiness(projectId: string): Promise<VideoPackageReadinessResponse> {
    return this.request<VideoPackageReadinessResponse>(
      `/ai-video/projects/${projectId}/package/readiness`,
    );
  }

  async createVideoPackage(projectId: string): Promise<VideoPackageExportResponse> {
    return this.request<VideoPackageExportResponse>(`/ai-video/projects/${projectId}/package`, {
      method: 'POST',
    });
  }

  async downloadVideoPackage(projectId: string): Promise<DownloadedBlob> {
    return this.download(`/ai-video/projects/${projectId}/package/download`, 'Bộ nguyên liệu.zip');
  }

  async getVideoProjectDebug(projectId: string): Promise<unknown> {
    return this.request<unknown>(`/ai-video/projects/${projectId}/debug`);
  }

  getVideoPreviewImageUrl(assetId: string): string {
    return `${this.getBaseUrl()}/ai-video/preview-images/${assetId}`;
  }

  // Model Management
  async getModelStatus(): Promise<ModelStatusListResponse> {
    return this.request<ModelStatusListResponse>('/models/status');
  }

  async getTadaVietnameseStatus(): Promise<TadaVietnameseStatusResponse> {
    return this.request<TadaVietnameseStatusResponse>('/models/tada-vietnamese-status');
  }

  async getModelsCacheDir(): Promise<{ path: string }> {
    return this.request<{ path: string }>('/models/cache-dir');
  }

  async migrateModels(
    destination: string,
  ): Promise<{ source: string; destination: string; moved: number; errors: string[] }> {
    return this.request('/models/migrate', {
      method: 'POST',
      body: JSON.stringify({ destination }),
    });
  }

  getMigrationProgressUrl(): string {
    return `${this.getBaseUrl()}/models/migrate/progress`;
  }

  async triggerModelDownload(modelName: string): Promise<{ message: string }> {
    console.log(
      '[API] triggerModelDownload called for:',
      modelName,
      'at',
      new Date().toISOString(),
    );
    const result = await this.request<{ message: string }>('/models/download', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName } as ModelDownloadRequest),
    });
    console.log('[API] triggerModelDownload response:', result);
    return result;
  }

  async deleteModel(modelName: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/models/${modelName}`, {
      method: 'DELETE',
    });
  }

  async unloadModel(modelName: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/models/${modelName}/unload`, {
      method: 'POST',
    });
  }

  async getResourceStatus(): Promise<ResourceStatusResponse> {
    return this.request<ResourceStatusResponse>('/resources/status');
  }

  async cleanupResources(request: ResourceCleanupRequest = {}): Promise<ResourceCleanupResponse> {
    return this.request<ResourceCleanupResponse>('/resources/cleanup', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async clearRenderCache(projectId?: string | null): Promise<RenderCacheClearResponse> {
    return this.request<RenderCacheClearResponse>('/resources/render-cache/clear', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId ?? null }),
    });
  }

  async cancelDownload(modelName: string): Promise<{ message: string }> {
    return this.request<{ message: string }>('/models/download/cancel', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName } as ModelDownloadRequest),
    });
  }

  // Task Management
  async getActiveTasks(): Promise<ActiveTasksResponse> {
    return this.request<ActiveTasksResponse>('/tasks/active');
  }

  async clearAllTasks(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/tasks/clear', { method: 'POST' });
  }

  // Audio Channels
  async listChannels(): Promise<
    Array<{
      id: string;
      name: string;
      is_default: boolean;
      device_ids: string[];
      created_at: string;
    }>
  > {
    return this.request('/channels');
  }

  async createChannel(data: { name: string; device_ids: string[] }): Promise<{
    id: string;
    name: string;
    is_default: boolean;
    device_ids: string[];
    created_at: string;
  }> {
    return this.request('/channels', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateChannel(
    channelId: string,
    data: {
      name?: string;
      device_ids?: string[];
    },
  ): Promise<{
    id: string;
    name: string;
    is_default: boolean;
    device_ids: string[];
    created_at: string;
  }> {
    return this.request(`/channels/${channelId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteChannel(channelId: string): Promise<{ message: string }> {
    return this.request(`/channels/${channelId}`, {
      method: 'DELETE',
    });
  }

  async getChannelVoices(channelId: string): Promise<{ profile_ids: string[] }> {
    return this.request(`/channels/${channelId}/voices`);
  }

  async setChannelVoices(channelId: string, profileIds: string[]): Promise<{ message: string }> {
    return this.request(`/channels/${channelId}/voices`, {
      method: 'PUT',
      body: JSON.stringify({ profile_ids: profileIds }),
    });
  }

  async getProfileChannels(profileId: string): Promise<{ channel_ids: string[] }> {
    return this.request(`/profiles/${profileId}/channels`);
  }

  async setProfileChannels(profileId: string, channelIds: string[]): Promise<{ message: string }> {
    return this.request(`/profiles/${profileId}/channels`, {
      method: 'PUT',
      body: JSON.stringify({ channel_ids: channelIds }),
    });
  }

  // CUDA Backend Management
  async getCudaStatus(): Promise<CudaStatus> {
    return this.request<CudaStatus>('/backend/cuda-status');
  }

  async downloadCudaBackend(): Promise<{ message: string; progress_key: string }> {
    return this.request<{ message: string; progress_key: string }>('/backend/download-cuda', {
      method: 'POST',
    });
  }

  async deleteCudaBackend(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/backend/cuda', {
      method: 'DELETE',
    });
  }

  // Stories
  async listStories(): Promise<StoryResponse[]> {
    return this.request<StoryResponse[]>('/stories');
  }

  async createStory(data: StoryCreate): Promise<StoryResponse> {
    return this.request<StoryResponse>('/stories', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStory(storyId: string): Promise<StoryDetailResponse> {
    return this.request<StoryDetailResponse>(`/stories/${storyId}`);
  }

  async updateStory(storyId: string, data: StoryCreate): Promise<StoryResponse> {
    return this.request<StoryResponse>(`/stories/${storyId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteStory(storyId: string): Promise<void> {
    await this.request<void>(`/stories/${storyId}`, {
      method: 'DELETE',
    });
  }

  async addStoryItem(storyId: string, data: StoryItemCreate): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async removeStoryItem(storyId: string, itemId: string): Promise<void> {
    await this.request<void>(`/stories/${storyId}/items/${itemId}`, {
      method: 'DELETE',
    });
  }

  async updateStoryItemTimes(storyId: string, data: StoryItemBatchUpdate): Promise<void> {
    await this.request<void>(`/stories/${storyId}/items/times`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async reorderStoryItems(storyId: string, data: StoryItemReorder): Promise<StoryItemDetail[]> {
    return this.request<StoryItemDetail[]>(`/stories/${storyId}/items/reorder`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async moveStoryItem(
    storyId: string,
    itemId: string,
    data: StoryItemMove,
  ): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items/${itemId}/move`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async trimStoryItem(
    storyId: string,
    itemId: string,
    data: StoryItemTrim,
  ): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items/${itemId}/trim`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async updateStoryItemVolume(
    storyId: string,
    itemId: string,
    data: StoryItemVolumeUpdate,
  ): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items/${itemId}/volume`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async splitStoryItem(
    storyId: string,
    itemId: string,
    data: StoryItemSplit,
  ): Promise<StoryItemDetail[]> {
    return this.request<StoryItemDetail[]>(`/stories/${storyId}/items/${itemId}/split`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async duplicateStoryItem(storyId: string, itemId: string): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items/${itemId}/duplicate`, {
      method: 'POST',
    });
  }

  async setStoryItemVersion(
    storyId: string,
    itemId: string,
    data: StoryItemVersionUpdate,
  ): Promise<StoryItemDetail> {
    return this.request<StoryItemDetail>(`/stories/${storyId}/items/${itemId}/version`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async exportStoryAudio(storyId: string): Promise<Blob> {
    const url = `${this.getBaseUrl()}/stories/${storyId}/export-audio`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.blob();
  }

  // Effects & Versions
  async getAvailableEffects(): Promise<AvailableEffectsResponse> {
    return this.request<AvailableEffectsResponse>('/effects/available');
  }

  async listEffectPresets(): Promise<EffectPresetResponse[]> {
    return this.request<EffectPresetResponse[]>('/effects/presets');
  }

  async createEffectPreset(data: EffectPresetCreate): Promise<EffectPresetResponse> {
    return this.request<EffectPresetResponse>('/effects/presets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateEffectPreset(
    presetId: string,
    data: { name?: string; description?: string; effects_chain?: EffectConfig[] },
  ): Promise<EffectPresetResponse> {
    return this.request<EffectPresetResponse>(`/effects/presets/${presetId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteEffectPreset(presetId: string): Promise<void> {
    await this.request<void>(`/effects/presets/${presetId}`, {
      method: 'DELETE',
    });
  }

  async listGenerationVersions(generationId: string): Promise<GenerationVersionResponse[]> {
    return this.request<GenerationVersionResponse[]>(`/generations/${generationId}/versions`);
  }

  async applyEffectsToGeneration(
    generationId: string,
    data: ApplyEffectsRequest,
  ): Promise<GenerationVersionResponse> {
    return this.request<GenerationVersionResponse>(
      `/generations/${generationId}/versions/apply-effects`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
    );
  }

  async setDefaultVersion(
    generationId: string,
    versionId: string,
  ): Promise<GenerationVersionResponse> {
    return this.request<GenerationVersionResponse>(
      `/generations/${generationId}/versions/${versionId}/set-default`,
      { method: 'PUT' },
    );
  }

  async deleteGenerationVersion(generationId: string, versionId: string): Promise<void> {
    await this.request<void>(`/generations/${generationId}/versions/${versionId}`, {
      method: 'DELETE',
    });
  }

  getVersionAudioUrl(versionId: string): string {
    return `${this.getBaseUrl()}/audio/version/${versionId}`;
  }

  async updateProfileEffects(
    profileId: string,
    effectsChain: EffectConfig[] | null,
  ): Promise<VoiceProfileResponse> {
    return this.request<VoiceProfileResponse>(`/profiles/${profileId}/effects`, {
      method: 'PUT',
      body: JSON.stringify({ effects_chain: effectsChain }),
    });
  }

  async previewEffects(generationId: string, effectsChain: EffectConfig[]): Promise<Blob> {
    const url = `${this.getBaseUrl()}/effects/preview/${generationId}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ effects_chain: effectsChain }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }

    return response.blob();
  }

  // --- Comic Series Analysis (change 13) ---------------------------------

  async getComicCapabilities(): Promise<ComicCapabilitiesResponse> {
    return this.request<ComicCapabilitiesResponse>('/comic-series-analysis/capabilities');
  }

  async listComicJobs(limit = 20, offset = 0): Promise<ComicJobListResponse> {
    return this.request<ComicJobListResponse>(
      `/comic-series-analysis/jobs?limit=${limit}&offset=${offset}`,
    );
  }

  async getComicJob(jobId: string): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>(`/comic-series-analysis/jobs/${jobId}`);
  }

  async createComicUrlJob(payload: ComicUrlJobRequest): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>('/comic-series-analysis/jobs/from-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  async createComicUploadJob(
    files: File[],
    options: { reading_mode?: string; development_mode?: string; rights_attested?: boolean; title?: string } = {},
  ): Promise<ComicJobDetail> {
    const form = new FormData();
    for (const file of files) form.append('files', file);
    if (options.reading_mode) form.append('reading_mode', options.reading_mode);
    if (options.development_mode) form.append('development_mode', options.development_mode);
    if (options.rights_attested !== undefined) form.append('rights_attested', String(options.rights_attested));
    if (options.title) form.append('title', options.title);
    const url = `${this.getBaseUrl()}/comic-series-analysis/jobs/from-upload`;
    const response = await fetch(url, { method: 'POST', body: form });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(formatErrorDetail(error.detail, `HTTP error! status: ${response.status}`));
    }
    return response.json();
  }

  async runComicJob(jobId: string): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>(`/comic-series-analysis/jobs/${jobId}/run`, { method: 'POST' });
  }

  async analyzeComicJob(jobId: string): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>(`/comic-series-analysis/jobs/${jobId}/analyze`, { method: 'POST' });
  }

  async getComicAnalysisPackage(jobId: string): Promise<ComicAnalysisPackage> {
    return this.request<ComicAnalysisPackage>(`/comic-series-analysis/jobs/${jobId}/analysis-package`);
  }

  async rewriteComicStory(jobId: string): Promise<ComicAnalysisPackage> {
    return this.request<ComicAnalysisPackage>(`/comic-series-analysis/jobs/${jobId}/rewrite`, { method: 'POST' });
  }

  async approveComicJob(jobId: string, payload: Record<string, unknown>): Promise<{ approved: boolean; manifest_id: string }> {
    return this.request<{ approved: boolean; manifest_id: string }>(`/comic-series-analysis/jobs/${jobId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  getComicAssetPreviewUrl(assetId: string): string {
    return `${this.getBaseUrl()}/comic-series-analysis/assets/${assetId}/preview`;
  }

  async cancelComicJob(jobId: string): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>(`/comic-series-analysis/jobs/${jobId}/cancel`, { method: 'POST' });
  }

  async retryComicJob(jobId: string): Promise<ComicJobDetail> {
    return this.request<ComicJobDetail>(`/comic-series-analysis/jobs/${jobId}/retry`, { method: 'POST' });
  }

  async deleteComicJob(jobId: string): Promise<void> {
    await this.request<void>(`/comic-series-analysis/jobs/${jobId}`, { method: 'DELETE' });
  }

  async previewComicHandoff(jobId: string, payload: Record<string, unknown>): Promise<ComicHandoffPreview> {
    return this.request<ComicHandoffPreview>(`/comic-series-analysis/jobs/${jobId}/series-handoff/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  async commitComicHandoff(jobId: string, payload: Record<string, unknown>): Promise<ComicHandoffResult> {
    return this.request<ComicHandoffResult>(`/comic-series-analysis/jobs/${jobId}/series-handoff/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  // --- Research Workspace -------------------------------------------------

  async listResearchProjects(status?: string): Promise<ResearchProjectResponse[]> {
    return this.request<ResearchProjectResponse[]>(`/research/projects${status ? `?status=${encodeURIComponent(status)}` : ''}`);
  }

  async createResearchProject(data: ResearchProjectCreate): Promise<ResearchProjectResponse> {
    return this.request<ResearchProjectResponse>('/research/projects', { method: 'POST', body: JSON.stringify(data) });
  }

  async getResearchMemory(projectId: string): Promise<string> {
    const response = await fetch(`${this.getBaseUrl()}/research/projects/${projectId}/memory`);
    if (!response.ok) throw new Error(`Không đọc được memory nghiên cứu (${response.status}).`);
    return response.text();
  }

  async listResearchSources(projectId: string): Promise<ResearchSourceResponse[]> {
    return this.request<ResearchSourceResponse[]>(`/research/projects/${projectId}/sources`);
  }

  async getResearchSource(projectId: string, sourceId: string): Promise<ResearchSourceResponse> {
    return this.request<ResearchSourceResponse>(`/research/projects/${projectId}/sources/${sourceId}`);
  }

  async addResearchTextSource(projectId: string, data: { source_type: string; title?: string; content?: string; input_url?: string }): Promise<ResearchSourceResponse> {
    return this.request<ResearchSourceResponse>(`/research/projects/${projectId}/sources`, { method: 'POST', body: JSON.stringify(data) });
  }

  async linkResearchSeriesMemory(
    projectId: string,
    data: { series_id: string; episode_number?: number; max_chars?: number },
  ): Promise<ResearchSourceResponse> {
    return this.request<ResearchSourceResponse>(`/research/projects/${projectId}/sources/series-memory`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async uploadResearchSource(projectId: string, sourceType: string, file: File, title?: string): Promise<ResearchSourceResponse> {
    const form = new FormData();
    form.append('source_type', sourceType);
    if (title) form.append('title', title);
    form.append('file', file);
    return this.request<ResearchSourceResponse>(`/research/projects/${projectId}/sources/upload`, { method: 'POST', body: form });
  }

  async retryResearchSource(projectId: string, sourceId: string): Promise<ResearchSourceResponse> {
    return this.request<ResearchSourceResponse>(`/research/projects/${projectId}/sources/${sourceId}/retry`, {
      method: 'POST',
      body: JSON.stringify({ resolve_dns: true }),
    });
  }

  async approveResearchSource(projectId: string, sourceId: string, title?: string): Promise<ResearchIdeaResponse> {
    return this.request<ResearchIdeaResponse>(`/research/projects/${projectId}/sources/${sourceId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ title, observation_indexes: [] }),
    });
  }

  async listResearchRuns(projectId: string): Promise<ResearchRunResponse[]> {
    return this.request<ResearchRunResponse[]>(`/research/projects/${projectId}/runs`);
  }

  async createResearchRun(projectId: string, data: { mode: 'research' | 'creative' | 'both'; brief?: string; source_ids?: string[]; related_project_ids?: string[]; run_ai?: boolean }): Promise<ResearchRunResponse> {
    return this.request<ResearchRunResponse>(`/research/projects/${projectId}/runs`, { method: 'POST', body: JSON.stringify(data) });
  }

  async getResearchRun(projectId: string, runId: string): Promise<ResearchRunResponse> {
    return this.request<ResearchRunResponse>(`/research/projects/${projectId}/runs/${runId}`);
  }

  async retryResearchRun(projectId: string, runId: string, runAi = true): Promise<ResearchRunResponse> {
    return this.request<ResearchRunResponse>(`/research/projects/${projectId}/runs/${runId}/retry`, {
      method: 'POST',
      body: JSON.stringify({ run_ai: runAi }),
    });
  }

  async mergeResearchRun(projectId: string, runId: string): Promise<ResearchRunResponse> {
    return this.request<ResearchRunResponse>(`/research/projects/${projectId}/runs/${runId}/merge`, {
      method: 'POST',
      body: JSON.stringify({ materialize_options: true }),
    });
  }

  async cancelResearchRun(projectId: string, runId: string): Promise<ResearchRunResponse> {
    return this.request<ResearchRunResponse>(`/research/projects/${projectId}/runs/${runId}/cancel`, { method: 'POST' });
  }

  async listResearchIdeas(projectId: string): Promise<ResearchIdeaResponse[]> {
    return this.request<ResearchIdeaResponse[]>(`/research/projects/${projectId}/ideas`);
  }

  async createResearchIdea(projectId: string, data: { title: string; summary?: string; content?: Record<string, unknown>; run_id?: string }): Promise<ResearchIdeaResponse> {
    return this.request<ResearchIdeaResponse>(`/research/projects/${projectId}/ideas`, { method: 'POST', body: JSON.stringify(data) });
  }

  async setResearchIdeaStatus(projectId: string, ideaId: string, status: string): Promise<ResearchIdeaResponse> {
    return this.request<ResearchIdeaResponse>(`/research/projects/${projectId}/ideas/${ideaId}/status`, { method: 'POST', body: JSON.stringify({ status }) });
  }

  async listResearchScripts(projectId: string): Promise<ResearchScriptResponse[]> {
    return this.request<ResearchScriptResponse[]>(`/research/projects/${projectId}/scripts`);
  }

  async createResearchScript(projectId: string, data: { title: string; content?: string; content_json?: Record<string, unknown>; idea_id?: string; target_format?: string }): Promise<ResearchScriptResponse> {
    return this.request<ResearchScriptResponse>(`/research/projects/${projectId}/scripts`, { method: 'POST', body: JSON.stringify(data) });
  }

  async setResearchScriptStatus(projectId: string, scriptId: string, status: string): Promise<ResearchScriptResponse> {
    return this.request<ResearchScriptResponse>(`/research/projects/${projectId}/scripts/${scriptId}/status`, { method: 'POST', body: JSON.stringify({ status }) });
  }

  async listResearchScores(projectId: string): Promise<ResearchScoreResponse[]> {
    return this.request<ResearchScoreResponse[]>(`/research/projects/${projectId}/scores`);
  }

  async scoreResearchContent(projectId: string, data: { target_type: 'idea' | 'script'; target_id: string; components?: Record<string, number>; explanations?: Record<string, string>; evidence_refs?: unknown[]; limitations?: unknown[]; constraint_violations?: string[]; run_ai?: boolean }): Promise<ResearchScoreResponse> {
    return this.request<ResearchScoreResponse>(`/research/projects/${projectId}/scores`, { method: 'POST', body: JSON.stringify(data) });
  }

  async getResearchRecommendation(projectId: string): Promise<ResearchRecommendationResponse> {
    return this.request<ResearchRecommendationResponse>(`/research/projects/${projectId}/recommendation`);
  }

  async overrideResearchScore(projectId: string, scoreId: string, data: { status?: 'recommended' | 'alternative' | 'blocked' | null; reason?: string | null }): Promise<ResearchScoreResponse> {
    return this.request<ResearchScoreResponse>(`/research/projects/${projectId}/scores/${scoreId}/override`, { method: 'POST', body: JSON.stringify(data) });
  }

  async researchChat(projectId: string, data: { message: string; mode?: 'research' | 'creative' | 'both'; selected_project_ids?: string[]; action?: ResearchChatAction; thread_id?: string; branch_name?: string; parent_message_id?: string; run_ai?: boolean }): Promise<ResearchChatResponse> {
    return this.request<ResearchChatResponse>(`/research/projects/${projectId}/chat`, { method: 'POST', body: JSON.stringify(data) });
  }

  async listResearchChatThreads(projectId: string): Promise<ResearchChatThreadResponse[]> {
    return this.request<ResearchChatThreadResponse[]>(`/research/projects/${projectId}/chat/threads`);
  }

  async approveResearchChatMessage(projectId: string, messageId: string, promotionType: 'idea' | 'script' | 'memory_card', title?: string): Promise<ResearchChatPromotionResponse> {
    return this.request<ResearchChatPromotionResponse>(`/research/projects/${projectId}/chat/messages/${messageId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ promotion_type: promotionType, title, accept: true }),
    });
  }

  async rejectResearchChatMessage(projectId: string, messageId: string): Promise<void> {
    await this.request(`/research/projects/${projectId}/chat/messages/${messageId}/status`, {
      method: 'POST',
      body: JSON.stringify({ status: 'rejected' }),
    });
  }

  async handoffResearchToAIVideo(projectId: string, data: { accepted_idea_ids?: string[]; accepted_script_ids?: string[]; selected_target_id?: string; selection_source?: 'user_override' | 'ai' | 'none'; title?: string; target_language?: string; target_duration_seconds?: number; aspect_ratio?: '9:16' | '16:9' | '1:1'; idempotency_key?: string }): Promise<ResearchHandoffResponse> {
    return this.request<ResearchHandoffResponse>(`/research/projects/${projectId}/handoffs/ai-video`, { method: 'POST', body: JSON.stringify(data) });
  }

  // --- Automation Hub ----------------------------------------------------

  async getAutomationHubStatus(): Promise<AutomationHubStatusResponse> {
    return this.request<AutomationHubStatusResponse>('/automation-hub/status');
  }

  async listAutomationConnections(): Promise<AutomationConnectionResponse[]> {
    return this.request<AutomationConnectionResponse[]>('/automation-hub/connections');
  }

  async createAutomationConnection(data: AutomationConnectionCreate): Promise<AutomationConnectionResponse> {
    return this.request<AutomationConnectionResponse>('/automation-hub/connections', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAutomationConnection(
    connectionId: string,
    data: AutomationConnectionUpdate,
  ): Promise<AutomationConnectionResponse> {
    return this.request<AutomationConnectionResponse>(`/automation-hub/connections/${connectionId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async checkAutomationConnection(connectionId: string): Promise<AutomationConnectionResponse> {
    return this.request<AutomationConnectionResponse>(`/automation-hub/connections/${connectionId}/check`, {
      method: 'POST',
    });
  }

  async deleteAutomationConnection(connectionId: string): Promise<void> {
    await this.request(`/automation-hub/connections/${connectionId}`, { method: 'DELETE' });
  }

  async getRoxyHealth(connectionId: string): Promise<{ ok: boolean; data?: Record<string, unknown> }> {
    return this.request(`/automation-hub/roxy/health?connection_id=${encodeURIComponent(connectionId)}`);
  }

  async listRoxyWorkspaces(connectionId: string): Promise<RoxyWorkspaceListResponse> {
    return this.request<RoxyWorkspaceListResponse>(
      `/automation-hub/roxy/workspaces?connection_id=${encodeURIComponent(connectionId)}`,
    );
  }

  async listRoxyProfiles(connectionId: string, workspaceId: number): Promise<RoxyProfileListResponse> {
    return this.request<RoxyProfileListResponse>(
      `/automation-hub/roxy/profiles?connection_id=${encodeURIComponent(connectionId)}&workspace_id=${workspaceId}`,
    );
  }

  async openRoxyProfile(data: {
    connection_id: string;
    workspace_id: number;
    dir_id: string;
    force_open?: boolean;
    args?: string[];
  }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/automation-hub/roxy/profiles/open', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async closeRoxyProfiles(data: { connection_id: string; dir_ids: string[] }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/automation-hub/roxy/profiles/close', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAutomationSidecarStatus(): Promise<AutomationSidecarStatus> {
    return this.request<AutomationSidecarStatus>('/automation-hub/sidecar/status');
  }

  async startAutomationSidecar(): Promise<AutomationSidecarStatus> {
    return this.request<AutomationSidecarStatus>('/automation-hub/sidecar/start', { method: 'POST' });
  }

  async stopAutomationSidecar(): Promise<AutomationSidecarStatus> {
    return this.request<AutomationSidecarStatus>('/automation-hub/sidecar/stop', { method: 'POST' });
  }

  async listAutomationAssets(): Promise<AutomationAssetResponse[]> {
    return this.request<AutomationAssetResponse[]>('/automation-hub/assets');
  }

  async uploadAutomationAsset(file: File): Promise<AutomationAssetResponse> {
    const form = new FormData();
    form.append('file', file);
    return this.request<AutomationAssetResponse>('/automation-hub/assets/upload', {
      method: 'POST',
      body: form,
    });
  }

  async importAutomationRenderAsset(renderJobId: string): Promise<AutomationAssetResponse> {
    return this.request<AutomationAssetResponse>('/automation-hub/assets/import-render', {
      method: 'POST',
      body: JSON.stringify({ render_job_id: renderJobId }),
    });
  }

  async deleteAutomationAsset(assetId: string): Promise<void> {
    await this.request(`/automation-hub/assets/${assetId}`, { method: 'DELETE' });
  }

  async listAutomationPublishJobs(): Promise<AutomationPublishJobResponse[]> {
    return this.request<AutomationPublishJobResponse[]>('/automation-hub/jobs');
  }

  async createAutomationPublishJob(data: AutomationPublishJobCreate): Promise<AutomationPublishJobResponse> {
    return this.request<AutomationPublishJobResponse>('/automation-hub/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAutomationPublishJob(jobId: string): Promise<AutomationPublishJobResponse> {
    return this.request<AutomationPublishJobResponse>(`/automation-hub/jobs/${jobId}`);
  }

  async cancelAutomationPublishJob(jobId: string): Promise<AutomationPublishJobResponse> {
    return this.request<AutomationPublishJobResponse>(`/automation-hub/jobs/${jobId}/cancel`, { method: 'POST' });
  }

  async retryAutomationPublishJob(jobId: string): Promise<AutomationPublishJobResponse> {
    return this.request<AutomationPublishJobResponse>(`/automation-hub/jobs/${jobId}/retry`, { method: 'POST' });
  }

  // ── Product Video (prompt-only flow) ────────────────────────────────
  // This flow deliberately stops at the prompt pack: no clip generation, no
  // TTS, no render. See openspec ngay-23-08-luong-product-video-sinh-prompt.

  async listProductVideoProjects(): Promise<ProductVideoProjectResponse[]> {
    return this.request<ProductVideoProjectResponse[]>('/product-video/projects');
  }

  async createProductVideoProject(
    data: ProductVideoProjectCreate,
  ): Promise<ProductVideoProjectDetailResponse> {
    return this.request<ProductVideoProjectDetailResponse>('/product-video/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getProductVideoProject(projectId: string): Promise<ProductVideoProjectDetailResponse> {
    return this.request<ProductVideoProjectDetailResponse>(
      `/product-video/projects/${projectId}`,
    );
  }

  async updateProductVideoProject(
    projectId: string,
    data: ProductVideoProjectUpdate,
  ): Promise<ProductVideoProjectDetailResponse> {
    return this.request<ProductVideoProjectDetailResponse>(
      `/product-video/projects/${projectId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  async deleteProductVideoProject(projectId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/product-video/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  async planProductVideoShots(projectId: string): Promise<ProductVideoShotResponse[]> {
    return this.request<ProductVideoShotResponse[]>(
      `/product-video/projects/${projectId}/shots`,
      { method: 'POST' },
    );
  }

  async generateProductVideoPrompts(
    projectId: string,
  ): Promise<ProductVideoPromptPackResponse> {
    return this.request<ProductVideoPromptPackResponse>(
      `/product-video/projects/${projectId}/prompts`,
      { method: 'POST' },
    );
  }

  async downloadProductVideoPromptPack(projectId: string): Promise<DownloadedBlob> {
    return this.download(
      `/product-video/projects/${projectId}/prompt-pack`,
      `product-video-prompts-${projectId}.txt`,
    );
  }
}

export const apiClient = new ApiClient();
