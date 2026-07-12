import type { LanguageCode } from '@/lib/constants/languages';
import { useServerStore } from '@/stores/serverStore';
import type {
  ActiveTasksResponse,
  AIPlanningProviderCheckResponse,
  ApplyEffectsRequest,
  AvailableEffectsResponse,
  CaptureCreateResponse,
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
  ResourceCleanupRequest,
  ResourceCleanupResponse,
  ResourceStatusResponse,
  StoryCreate,
  StoryDetailResponse,
  StoryItemBatchUpdate,
  StoryItemCreate,
  StoryItemDetail,
  StoryItemMove,
  StoryItemReorder,
  StoryItemSplit,
  StoryItemTrim,
  StoryItemVersionUpdate,
  StoryItemVolumeUpdate,
  StoryResponse,
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
  VideoInspirationCreateProjectRequest,
  VideoInspirationDirectionUpdate,
  VideoInspirationHandoffResponse,
  VideoInspirationJobResponse,
  VideoInspirationListResponse,
  VideoInspirationRewriteRequest,
  VideoInspirationScriptUpdate,
  VideoInspirationTargetLanguage,
  VideoInspirationTranscriptUpdate,
  VideoInspirationUrlRequest,
  VideoPackageExportResponse,
  VideoPackageReadinessResponse,
  VideoProviderSessionLabelUpdate,
  VideoProviderSessionOpenRequest,
  VideoProviderSessionResponse,
  VideoProjectCreate,
  VideoProjectDetailResponse,
  VideoProjectLocalizeRequest,
  VideoProjectResponse,
  VideoProjectStatusResponse,
  VideoProjectUpdate,
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
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
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

  async uploadVideoShotClip(
    projectId: string,
    shotId: string,
    file: File,
  ): Promise<VideoShotClipResponse> {
    const formData = new FormData();
    formData.append('file', file);
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
      enhanced_render: String(settings.enhanced_render ?? false),
      enhanced_audio: String(settings.enhanced_audio ?? true),
      ai_review: String(settings.ai_review ?? true),
      max_fix_attempts: String(settings.max_fix_attempts ?? 1),
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
}

export const apiClient = new ApiClient();
