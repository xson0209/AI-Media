import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouterState } from '@tanstack/react-router';
import {
  AlertTriangle,
  BookOpen,
  Brain,
  Check,
  Clapperboard,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  ListChecks,
  Loader2,
  Maximize2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRound,
  X,
  type LucideIcon,
} from 'lucide-react';
import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Button } from '@/components/ui/button';
import {
  SeriesCreateDialog,
  type SeriesCreateNextAction,
  type SeriesDraftInput,
  SeriesPickerDialog,
} from '@/components/SeriesDialogs/SeriesDialogs';
import { apiClient } from '@/lib/api/client';
import { ALL_LANGUAGES, LANGUAGE_OPTIONS } from '@/lib/constants/languages';
import type {
  SeriesCanonCheckResponse,
  SeriesCharacterProfileCreate,
  SeriesCurrentStateResponse,
  SeriesMemoryCardResponse,
  SeriesMemoryCardType,
  SeriesReferenceApprovalStatus,
  SeriesReferenceAssetResponse,
  SeriesMode,
  StoryAdaptationResponse,
  StoryEpisodeResponse,
  StoryEpisodeOutputSettings,
  StoryImageAspectRatio,
  StoryImagePanelMode,
  StoryOutputIntent,
  StoryVideoAspectRatio,
  StorySuggestionResponse,
  VideoLanguage,
  VideoPurpose,
  DialogueMode,
  NarrationDensity,
  CallToActionStyle,
  VideoSeriesResponse,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

type PanelPayload = {
  order: number;
  purpose?: string;
  caption_or_dialogue?: string;
  visual_description?: string;
  scene_context?: string;
  camera_angle?: string;
  composition_notes?: string;
  dialogue_note?: string;
  prompt?: string;
  render_prompt?: string;
  reader_prompt_vi?: string;
  prompt_explanation_vi?: string;
  negative_prompt?: string;
  prompt_status?: string;
  render_status?: string;
  asset?: {
    image_path?: string | null;
    image_url?: string | null;
    provider?: string | null;
    provider_asset_id?: string | null;
    provider_metadata?: Record<string, unknown>;
    render_job_id?: string | null;
    rendered_at?: string | null;
  } | null;
  failure_reason?: string | null;
  series_context_trace_id?: string | null;
  selected_memory_cards?: Array<Record<string, unknown>>;
  context_group_usage?: Array<Record<string, unknown>>;
  quality_check?: {
    passed?: boolean;
    score?: number;
    threshold?: number;
    criteria?: Record<string, number>;
    blocking_errors?: string[];
    warnings?: string[];
    evidence?: string[];
    suggestions?: string[];
  } | null;
  quality_status?: string | null;
  quality_threshold?: number | null;
  repair_attempt?: number | null;
  repair_status?: string | null;
  prompt_versions?: Array<Record<string, unknown>>;
  canon_check?: {
    passed?: boolean;
    blocking_conflicts?: Array<Record<string, unknown>>;
    warnings?: Array<Record<string, unknown>>;
    evidence_card_ids?: string[];
    suggestions?: string[];
    override_reason?: string | null;
  } | null;
};

type VideoRenderJobPayload = {
  id?: string;
  status?: string;
  progress?: number;
  current_step?: string | null;
  output_path?: string | null;
  stale?: boolean;
  failure_reason?: string | null;
};

const emptyProfile: SeriesCharacterProfileCreate = {
  name: '',
  role: '',
  face_description: '',
  hair_description: '',
  body_description: '',
  signature_outfit: '',
  personality: '',
  speech_style: '',
  fixed_traits: '',
  additional_notes: '',
};

const characterReferenceRoles = [
  'face_front',
  'face_side',
  'full_body',
  'signature_outfit',
  'expression',
  'other',
] as const;
const locationReferenceRoles = [
  'wide_view',
  'entrance',
  'interior',
  'landmark_detail',
  'lighting_reference',
  'other',
] as const;

const imageAspectSizes: Record<StoryImageAspectRatio, { width: number; height: number }> = {
  '9:16': { width: 720, height: 1280 },
  '16:9': { width: 1920, height: 1080 },
  '1:1': { width: 1080, height: 1080 },
  '4:5': { width: 1080, height: 1350 },
};

const storyVideoAspectOptions: StoryVideoAspectRatio[] = ['9:16', '16:9', '1:1'];
const storyImageAspectOptions = Object.keys(imageAspectSizes) as StoryImageAspectRatio[];
const DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT = 6;
const DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS = 10;
const DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT = 4;

function defaultEpisodeOutputSettings(): StoryEpisodeOutputSettings {
  return {
    image: {
      panel_mode: 'auto',
      panel_count: null,
      aspect_ratio: '9:16',
      width: 720,
      height: 1280,
    },
    video: {
      handoff_only: true,
      aspect_ratio: '9:16',
      target_language: 'en',
      video_purpose: 'global_short',
      dialogue_mode: 'character_lines',
      narration_density: 'dense',
      call_to_action_style: 'direct',
      target_duration_seconds: null,
      default_shot_duration_seconds: null,
      prompt_segment_count: DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT,
      prompt_segment_duration_seconds: DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS,
      micro_scenes_per_prompt: DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT,
    },
  };
}

function normalizeEpisodeOutputSettings(
  value: Partial<StoryEpisodeOutputSettings> | null | undefined,
): StoryEpisodeOutputSettings {
  const defaults = defaultEpisodeOutputSettings();
  return {
    image: {
      ...defaults.image,
      ...(value?.image ?? {}),
    },
    video: {
      ...defaults.video,
      ...(value?.video ?? {}),
    },
  };
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

function seriesModeLabel(mode: SeriesMode | null | undefined): string {
  if (mode === 'image_story_only') return 'Chuỗi truyện ảnh';
  if (mode === 'hybrid') return 'Chuỗi truyện + video';
  return 'Chuỗi video';
}

function intentLabel(intent: StoryOutputIntent | null | undefined): string {
  if (intent === 'video_truyen') return 'Video truyện';
  if (intent === 'ca_hai') return 'Cả truyện ảnh + video';
  return 'Truyện ảnh';
}

function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'draft':
      return 'Bản nháp';
    case 'pending_approval':
      return 'Chờ duyệt';
    case 'approved':
      return 'Đã duyệt';
    case 'rejected':
      return 'Đã từ chối';
    case 'archived':
      return 'Đã lưu trữ';
    case 'waiting_provider':
      return 'Chờ dịch vụ ảnh';
    case 'queued':
      return 'Đang xếp hàng';
    case 'rendering':
      return 'Đang dựng ảnh/video';
    case 'completed':
      return 'Hoàn tất';
    case 'failed':
      return 'Lỗi';
    case 'stale':
      return 'Cần tạo lại';
    case 'needs_review':
      return 'Cần rà soát';
    case 'repairing':
      return 'Đang sửa';
    case 'not_needed':
      return 'Không cần sửa';
    case 'not_requested':
      return 'Chưa render';
    default:
      return 'Chưa có trạng thái';
  }
}

function referenceRoleLabel(role: string | null | undefined): string {
  switch (role) {
    case 'face_front':
      return 'Mặt chính diện';
    case 'face_side':
      return 'Mặt góc nghiêng';
    case 'full_body':
      return 'Toàn thân';
    case 'signature_outfit':
      return 'Trang phục';
    case 'expression':
      return 'Biểu cảm';
    case 'wide_view':
      return 'Toàn cảnh';
    case 'entrance':
      return 'Lối vào';
    case 'interior':
      return 'Nội thất';
    case 'landmark_detail':
      return 'Chi tiết nhận diện';
    case 'lighting_reference':
      return 'Ánh sáng';
    default:
      return 'Khác';
  }
}

function referenceEntityLabel(
  asset: SeriesReferenceAssetResponse,
  profiles: Array<SeriesCharacterProfileCreate & { id?: string }>,
): string {
  if (asset.entity_type === 'character') {
    const profile = profiles.find((item) => 'id' in item && item.id === asset.entity_id);
    return profile?.name || 'Nhân vật';
  }
  return asset.entity_id;
}

function textValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(String).join('\n');
  if (value == null) return '';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function sourceKindLabel(value: string | null | undefined): string {
  if (value === 'comic_analysis') return 'Phân tích truyện tranh';
  if (value === 'manual') return 'Nguồn nhập tay';
  return value || 'Nguồn tập';
}

function compactLimitationLabel(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object') {
    const data = value as Record<string, unknown>;
    return String(data.message || data.description || data.code || JSON.stringify(data));
  }
  return String(value ?? '');
}

function optionalPositiveInt(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function panelModeLabel(value: StoryImagePanelMode): string {
  return value === 'manual' ? 'Chọn số ảnh' : 'Tự động';
}

function videoLanguageLabel(value: VideoLanguage): string {
  return ALL_LANGUAGES[value] ?? String(value);
}

function callToActionStyleLabel(value: CallToActionStyle): string {
  switch (value) {
    case 'soft':
      return 'Nhẹ nhàng';
    case 'direct':
      return 'Trực tiếp';
    case 'urgent':
      return 'Khẩn cấp';
    default:
      return 'Không dùng';
  }
}

function videoPurposeLabel(value: VideoPurpose): string {
  switch (value) {
    case 'vietnam_market':
      return 'Thị trường Việt';
    case 'global_short':
      return 'Short quốc tế';
    case 'educational_explainer':
      return 'Giải thích';
    case 'sales_ad':
      return 'Quảng cáo';
    case 'localized_variant':
      return 'Bản ngôn ngữ khác';
    default:
      return 'Tùy chỉnh';
  }
}

function dialogueModeLabel(value: DialogueMode): string {
  if (value === 'character_lines') return 'Thoại nhân vật';
  if (value === 'mixed') return 'Kể + thoại';
  return 'Thuyết minh';
}

function narrationDensityLabel(value: NarrationDensity): string {
  if (value === 'light') return 'Ít lời';
  if (value === 'dense') return 'Dày lời';
  return 'Cân bằng';
}

function formatSeconds(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
}

function videoDurationSummary(video: StoryEpisodeOutputSettings['video']): string {
  const promptCount = video.prompt_segment_count ?? null;
  const promptDuration = video.prompt_segment_duration_seconds ?? null;
  const microScenes = video.micro_scenes_per_prompt || DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT;
  if (promptCount && promptDuration) {
    const totalSeconds = promptCount * promptDuration;
    const secondsPerMicroScene = promptDuration / Math.max(1, microScenes);
    return `${promptCount} câu lệnh × ${promptDuration}s = khoảng ${totalSeconds}s. Mỗi câu lệnh có ${microScenes} cảnh nhỏ (~${formatSeconds(secondsPerMicroScene)}s/cảnh).`;
  }
  if (video.target_duration_seconds) {
    return `Video mục tiêu khoảng ${video.target_duration_seconds}s; hệ thống sẽ tự chia câu lệnh/cảnh theo nội dung truyện.`;
  }
  return 'Tự động: hệ thống tự chọn thời lượng theo nội dung. Nếu muốn kiểm soát Veo/Gemini, nhập Số câu lệnh video và Giây mỗi câu lệnh.';
}

function suggestionTypeLabel(value: unknown): string {
  if (value === 'continuity') return 'Nhất quán';
  if (value === 'character_profile' || value === 'character') return 'Hồ sơ nhân vật';
  if (value === 'review_note') return 'Ghi chú rà soát';
  return 'Đề xuất';
}

function memoryTypeLabel(value: SeriesMemoryCardType | string | null | undefined): string {
  switch (value) {
    case 'series_identity':
      return 'Danh tính';
    case 'character_context':
      return 'Nhân vật';
    case 'relationship':
      return 'Quan hệ';
    case 'location':
      return 'Địa điểm';
    case 'prop':
      return 'Đạo cụ';
    case 'story_thread':
      return 'Mạch truyện';
    case 'canon_rule':
      return 'Quy tắc gốc';
    case 'visual_style':
      return 'Phong cách';
    case 'episode_summary':
      return 'Tóm tắt tập';
    case 'arc_summary':
      return 'Tóm tắt chặng';
    case 'series_summary':
      return 'Tóm tắt series';
    case 'reviewed_note':
      return 'Ghi chú';
    default:
      return 'Thẻ nhớ';
  }
}

function renderProgressLabel(progress: number | undefined): string | null {
  if (typeof progress !== 'number' || Number.isNaN(progress)) return null;
  const normalized = progress <= 1 ? progress * 100 : progress;
  return `${Math.max(0, Math.min(100, Math.round(normalized)))}%`;
}

function recordText(record: Record<string, unknown> | undefined, key: string): string {
  const value = record?.[key];
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function listText(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => textValue(item)).filter(Boolean);
  }
  const text = textValue(value);
  return text ? [text] : [];
}

function hasBlockingCanon(panel: PanelPayload): boolean {
  return Boolean(panel.canon_check?.blocking_conflicts?.length);
}

function qualityCheck(panel: PanelPayload): NonNullable<PanelPayload['quality_check']> | undefined {
  return asRecord(panel.quality_check) as NonNullable<PanelPayload['quality_check']> | undefined;
}

function hasBlockingQuality(panel: PanelPayload): boolean {
  const quality = qualityCheck(panel);
  if (!quality || quality.passed) return false;
  const errors = listText(quality.blocking_errors);
  return errors.length === 0 || errors.some((error) => error !== 'canon_conflicts');
}

function qualityScoreLabel(panel: PanelPayload): string {
  const quality = qualityCheck(panel);
  if (!quality || typeof quality.score !== 'number') return 'chưa chấm';
  const threshold = typeof quality.threshold === 'number' ? quality.threshold : 85;
  return `${quality.score.toFixed(1)}/${threshold}`;
}

function latestPanelVersion(panel: PanelPayload): Record<string, unknown> | undefined {
  const versions = Array.isArray(panel.prompt_versions) ? panel.prompt_versions : [];
  return asRecord(versions[versions.length - 1]);
}

function candidateEvaluation(
  candidate: StoryEpisodeResponse['candidates'][number],
): Record<string, unknown> | undefined {
  return asRecord(candidate.evaluation_json);
}

function candidateErrorMessage(candidate: StoryEpisodeResponse['candidates'][number]): string {
  const metadata = asRecord(candidate.generation_metadata_json);
  return (
    textValue(candidate.script_json.error_message) ||
    textValue(metadata?.last_error) ||
    textValue(metadata?.fallback_reason) ||
    textValue(metadata?.evaluation_error)
  );
}

function briefJson(value: unknown): string {
  const text = textValue(value);
  return text.length > 280 ? `${text.slice(0, 280)}...` : text;
}

const STATE_COMPARE_FIELDS = [
  ['character_states', 'Nhân vật'],
  ['relationship_states', 'Quan hệ'],
  ['location_states', 'Địa điểm'],
  ['prop_states', 'Đạo cụ'],
  ['open_threads', 'Mạch truyện'],
  ['unresolved_conflicts', 'Xung đột'],
] as const;

function stateFingerprint(value: unknown): string {
  try {
    return JSON.stringify(value ?? null);
  } catch {
    return String(value ?? '');
  }
}

function stateValuePreview(value: unknown): string {
  if (Array.isArray(value)) {
    if (!value.length) return 'Chưa có';
    return value
      .slice(0, 3)
      .map((item) =>
        item && typeof item === 'object'
          ? recordText(item as Record<string, unknown>, 'title') || briefJson(item)
          : String(item),
      )
      .join(' | ');
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>);
    if (!keys.length) return 'Chưa có';
    return briefJson(value);
  }
  const text = briefJson(value);
  return text || 'Chưa có';
}

function stateDiffRows(
  state: SeriesCurrentStateResponse,
  previousState?: SeriesCurrentStateResponse | null,
) {
  return STATE_COMPARE_FIELDS.map(([key, label]) => {
    const oldValue = previousState?.[key];
    const newValue = state[key];
    return {
      key,
      label,
      changed: stateFingerprint(oldValue) !== stateFingerprint(newValue),
      oldValue: stateValuePreview(oldValue),
      newValue: stateValuePreview(newValue),
    };
  });
}

function panelsFrom(adaptation: StoryAdaptationResponse | undefined): PanelPayload[] {
  const panels = adaptation?.payload_json?.panels;
  return Array.isArray(panels) ? (panels as PanelPayload[]) : [];
}

async function writeClipboardText(value: string) {
  if (!value.trim()) throw new Error('Không có nội dung prompt để copy.');
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!ok) throw new Error('Clipboard rejected');
}

function panelPromptBlock(panel: PanelPayload): string {
  const lines = [`PANEL ${String(panel.order).padStart(2, '0')}`];
  if (panel.reader_prompt_vi || panel.prompt_explanation_vi) {
    lines.push(`BẢN ĐỌC CHO NGƯỜI DÙNG:\n${panel.reader_prompt_vi || panel.prompt_explanation_vi}`);
  }
  if (panel.caption_or_dialogue) lines.push(`Chữ/thoại trong ảnh: ${panel.caption_or_dialogue}`);
  if (panel.scene_context) lines.push(`Bối cảnh: ${panel.scene_context}`);
  if (panel.camera_angle) lines.push(`Góc máy: ${panel.camera_angle}`);
  if (panel.composition_notes) lines.push(`Bố cục: ${panel.composition_notes}`);
  if (panel.dialogue_note) lines.push(`Note thoại: ${panel.dialogue_note}`);
  if (panel.visual_description) lines.push(`Visual: ${panel.visual_description}`);
  if (panel.render_prompt || panel.prompt) {
    lines.push(`BẢN GỬI AI RENDER:\n${panel.render_prompt || panel.prompt}`);
  }
  if (panel.negative_prompt) lines.push(`NEGATIVE PROMPT:\n${panel.negative_prompt}`);
  return lines.join('\n\n');
}

function allPanelPromptsText(panels: PanelPayload[]): string {
  return panels.map(panelPromptBlock).join('\n\n---\n\n');
}

function payloadString(
  adaptation: StoryAdaptationResponse | undefined,
  key: string,
): string | null {
  const value = adaptation?.payload_json?.[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function payloadNumber(
  adaptation: StoryAdaptationResponse | undefined,
  key: string,
): number | null {
  const value = adaptation?.payload_json?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function handoffSourceLabel(value: string | null | undefined): string {
  if (value === 'image_story_prompts') return 'Câu lệnh truyện ảnh';
  if (value === 'master_story') return 'Truyện chính';
  return 'Chưa rõ nguồn';
}

function latestRenderJob(
  adaptation: StoryAdaptationResponse | undefined,
): VideoRenderJobPayload | null {
  const value = adaptation?.payload_json?.latest_render_job;
  return value && typeof value === 'object' ? (value as VideoRenderJobPayload) : null;
}

function totalScore(candidate: StoryEpisodeResponse['candidates'][number]): string {
  const score = candidate.score_json?.total;
  return typeof score === 'number' ? score.toFixed(1) : 'chưa chấm';
}

function firstStorySeries(series: VideoSeriesResponse[] | undefined): string {
  return series?.[0]?.id ?? '';
}

function useStoryEpisodeAction(
  action: () => Promise<StoryEpisodeResponse>,
  message: string,
  onSuccess: (episode: StoryEpisodeResponse, message: string) => void,
  onError: (error: unknown) => void,
) {
  return useMutation({
    mutationFn: action,
    onSuccess: (episode) => onSuccess(episode, message),
    onError,
  });
}

function useStoryAdaptationAction(
  action: () => Promise<StoryAdaptationResponse>,
  message: string,
  onSuccess: (
    adaptation: StoryAdaptationResponse,
    message: string,
    after?: (adaptation: StoryAdaptationResponse) => void,
  ) => void,
  onError: (error: unknown) => void,
  after?: (adaptation: StoryAdaptationResponse) => void,
) {
  return useMutation({
    mutationFn: action,
    onSuccess: (adaptation) => onSuccess(adaptation, message, after),
    onError,
  });
}

export function StoryStudio() {
  const queryClient = useQueryClient();
  const routeSearch = useRouterState({
    select: (state) => state.location.search as { seriesId?: unknown; episodeId?: unknown },
  });
  const searchSeriesId = typeof routeSearch.seriesId === 'string' ? routeSearch.seriesId : '';
  const searchEpisodeId = typeof routeSearch.episodeId === 'string' ? routeSearch.episodeId : '';
  const appliedDeepLinkRef = useRef<string | null>(null);
  const [selectedSeriesId, setSelectedSeriesId] = useState('');
  const [selectedEpisodeId, setSelectedEpisodeId] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [exportText, setExportText] = useState('');
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false);
  const [promptLibrarySnapshot, setPromptLibrarySnapshot] = useState<PanelPayload[] | null>(null);
  const [copiedPromptKey, setCopiedPromptKey] = useState<string | null>(null);
  const [seriesPickerOpen, setSeriesPickerOpen] = useState(false);
  const [seriesCreateDialogOpen, setSeriesCreateDialogOpen] = useState(false);
  const [autoRunStep, setAutoRunStep] = useState<string | null>(null);
  const [profileSuggestion, setProfileSuggestion] = useState<SeriesCharacterProfileCreate | null>(
    null,
  );
  const [storySuggestion, setStorySuggestion] = useState<StorySuggestionResponse | null>(null);
  const [canonOverrideReason, setCanonOverrideReason] = useState('');
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referenceDraft, setReferenceDraft] = useState({
    entity_type: 'character',
    entity_id: '',
    reference_role: 'face_front',
    label: '',
  });
  const [seriesDraft, setSeriesDraft] = useState({
    title: '',
    series_mode: 'image_story_only' as SeriesMode,
  });
  const [profileDraft, setProfileDraft] = useState<SeriesCharacterProfileCreate>(emptyProfile);
  const [episodeDraft, setEpisodeDraft] = useState({
    title: '',
    output_intent: 'truyen_anh' as StoryOutputIntent,
    market_profile: 'global_short',
    language_profile: 'en',
    source_input: '',
    output_settings: defaultEpisodeOutputSettings(),
  });

  useEffect(() => {
    if (!searchSeriesId && !searchEpisodeId) return;
    const deepLinkKey = `${searchSeriesId}\n${searchEpisodeId}`;
    if (appliedDeepLinkRef.current === deepLinkKey) return;
    appliedDeepLinkRef.current = deepLinkKey;
    if (searchSeriesId) {
      setSelectedSeriesId(searchSeriesId);
    }
    if (searchEpisodeId) {
      setSelectedEpisodeId(searchEpisodeId);
    }
    setProfileSuggestion(null);
    setStorySuggestion(null);
  }, [searchEpisodeId, searchSeriesId]);

  useEffect(() => {
    if (!promptLibraryOpen) {
      setPromptLibrarySnapshot(null);
    }
  }, [promptLibraryOpen]);

  const seriesQuery = useQuery({
    queryKey: ['story-studio', 'series'],
    queryFn: () => apiClient.listStoryStudioSeries(),
  });
  const selectedSeriesExists =
    !selectedSeriesId ||
    !seriesQuery.data ||
    seriesQuery.data.some((series) => series.id === selectedSeriesId);
  const effectiveSeriesId =
    selectedSeriesExists && selectedSeriesId
      ? selectedSeriesId
      : firstStorySeries(seriesQuery.data);
  const selectedSeries = useMemo(
    () => seriesQuery.data?.find((series) => series.id === effectiveSeriesId) ?? null,
    [effectiveSeriesId, seriesQuery.data],
  );
  const episodesQuery = useQuery({
    queryKey: ['story-studio', 'episodes', effectiveSeriesId],
    queryFn: () => apiClient.listStoryEpisodes(effectiveSeriesId),
    enabled: !!effectiveSeriesId,
  });
  const profilesQuery = useQuery({
    queryKey: ['ai-video', 'character-profiles', effectiveSeriesId],
    queryFn: () => apiClient.listSeriesCharacterProfiles(effectiveSeriesId),
    enabled: !!effectiveSeriesId,
  });
  const referenceAssetsQuery = useQuery({
    queryKey: ['ai-video', 'reference-assets', effectiveSeriesId],
    queryFn: () => apiClient.listSeriesReferenceAssets(effectiveSeriesId),
    enabled: !!effectiveSeriesId,
  });
  const staleEventsQuery = useQuery({
    queryKey: ['ai-video', 'stale-events', effectiveSeriesId],
    queryFn: () =>
      apiClient.listSeriesStaleEvents(effectiveSeriesId, { status: 'active', limit: 20 }),
    enabled: !!effectiveSeriesId,
  });
  const seriesVersionQuery = useQuery({
    queryKey: ['ai-video', 'versions', effectiveSeriesId, 'video_series'],
    queryFn: () =>
      apiClient.getSeriesVersionHistory(effectiveSeriesId, 'video_series', effectiveSeriesId),
    enabled: !!effectiveSeriesId,
  });
  const selectedEpisode = useMemo(
    () =>
      episodesQuery.data?.find((episode) => episode.id === selectedEpisodeId) ??
      episodesQuery.data?.[0] ??
      null,
    [episodesQuery.data, selectedEpisodeId],
  );
  const selectedEpisodeOutputSettings = useMemo(
    () => normalizeEpisodeOutputSettings(selectedEpisode?.output_settings),
    [selectedEpisode?.output_settings],
  );
  const selectedEpisodeSourceSummary = selectedEpisode?.source_summary ?? null;
  const selectedEpisodeSourceLimitations = useMemo(
    () =>
      (selectedEpisodeSourceSummary?.limitations ?? [])
        .map(compactLimitationLabel)
        .filter(Boolean)
        .slice(0, 2),
    [selectedEpisodeSourceSummary?.limitations],
  );
  const imageAdaptation = selectedEpisode?.adaptations.find((item) => item.kind === 'image_story');
  const videoAdaptation = selectedEpisode?.adaptations.find((item) => item.kind === 'video_story');
  const panels = panelsFrom(imageAdaptation);
  const hasPanelPromptSource = panels.some(
    (panel) => panel.prompt?.trim() || panel.visual_description?.trim(),
  );
  const promptLibraryPanels = promptLibrarySnapshot ?? panels;
  const fullPromptText = useMemo(() => allPanelPromptsText(panels), [panels]);
  const promptLibraryText = useMemo(
    () => allPanelPromptsText(promptLibraryPanels),
    [promptLibraryPanels],
  );
  const panelsWithBlockingCanon = panels.filter(hasBlockingCanon);
  const panelsWithBlockingQuality = panels.filter(hasBlockingQuality);
  const staleAdaptations =
    selectedEpisode?.adaptations.filter((item) => item.status === 'stale') ?? [];
  const videoRenderJob = latestRenderJob(videoAdaptation);
  const linkedVideoProjectId =
    videoAdaptation?.linked_video_project_id ??
    payloadString(videoAdaptation, 'linked_video_project_id');
  const videoHandoffSource =
    payloadString(videoAdaptation, 'handoff_source') ??
    payloadString(videoAdaptation, 'source_mode_resolved');
  const videoSourcePanelCount = payloadNumber(videoAdaptation, 'source_panel_count');
  const videoSourcePromptCount = payloadNumber(videoAdaptation, 'source_prompt_count');
  const videoAutoRunId = payloadString(videoAdaptation, 'auto_run_id');
  const videoAutoRunStatus = payloadString(videoAdaptation, 'auto_run_status');
  const videoAutoRunStep = payloadString(videoAdaptation, 'auto_run_step');
  const videoMp4Url =
    linkedVideoProjectId &&
    videoRenderJob?.id &&
    videoRenderJob.status === 'completed' &&
    !videoRenderJob.stale
      ? apiClient.getVideoRenderJobDownloadUrl(linkedVideoProjectId, videoRenderJob.id)
      : null;

  const invalidateStory = () => {
    queryClient.invalidateQueries({ queryKey: ['story-studio'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'character-profiles'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'reference-assets'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'stale-events'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'versions'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'series'] });
  };

  const selectStorySeries = (series: VideoSeriesResponse) => {
    setSelectedSeriesId(series.id);
    setSelectedEpisodeId('');
    setProfileSuggestion(null);
    setStorySuggestion(null);
    setSeriesPickerOpen(false);
    setNotice('Đã chọn series cho Story Studio.');
  };

  const createSeries = useMutation({
    mutationFn: (variables: {
      draft?: SeriesDraftInput;
      nextAction?: SeriesCreateNextAction;
    } = {}) => {
      const source = variables.draft ?? {
        title: seriesDraft.title,
        series_mode: seriesDraft.series_mode,
        character_bible: '',
        world_bible: '',
        style_bible: '',
        continuity_rules: '',
        negative_rules: '',
        previous_episode_summary: '',
      };
      if (!source.title.trim()) throw new Error('Tên series là bắt buộc.');
      return apiClient.createVideoSeries({
        title: source.title.trim(),
        series_mode: source.series_mode,
        character_bible: source.character_bible.trim() || null,
        world_bible: source.world_bible.trim() || null,
        style_bible: source.style_bible.trim() || null,
        continuity_rules: source.continuity_rules.trim() || null,
        negative_rules: source.negative_rules.trim() || null,
        previous_episode_summary: source.previous_episode_summary.trim() || null,
      });
    },
    onSuccess: (series, variables) => {
      setSelectedSeriesId(series.id);
      setSeriesDraft({ title: '', series_mode: 'image_story_only' });
      setSeriesCreateDialogOpen(false);
      setSeriesPickerOpen(false);
      if (variables?.nextAction === 'manage_characters') {
        setNotice('Đã tạo series. Bạn có thể thêm hồ sơ nhân vật ở panel bên phải.');
      } else {
        setNotice('Đã tạo series cho Story Studio.');
      }
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const createProfile = useMutation({
    mutationFn: () => {
      if (!effectiveSeriesId) throw new Error('Chọn series trước.');
      if (!profileDraft.name.trim()) throw new Error('Tên nhân vật là bắt buộc.');
      return apiClient.createSeriesCharacterProfile(effectiveSeriesId, {
        ...profileDraft,
        name: profileDraft.name.trim(),
      });
    },
    onSuccess: () => {
      setProfileDraft(emptyProfile);
      setNotice('Đã lưu Hồ sơ nhân vật dùng chung.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const suggestProfiles = useMutation({
    mutationFn: () => apiClient.suggestSeriesCharacterProfiles(effectiveSeriesId),
    onSuccess: (suggestion) => {
      setProfileSuggestion(suggestion.profiles[0] ?? null);
      setNotice(suggestion.message);
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const approveProfileSuggestion = useMutation({
    mutationFn: () => {
      if (!effectiveSeriesId) throw new Error('Chọn series trước.');
      if (!profileSuggestion?.name?.trim()) throw new Error('Gợi ý chưa có tên nhân vật hợp lệ.');
      return apiClient.createSeriesCharacterProfile(effectiveSeriesId, {
        ...profileSuggestion,
        name: profileSuggestion.name.trim(),
      });
    },
    onSuccess: () => {
      setProfileSuggestion(null);
      setNotice('Đã lưu Hồ sơ nhân vật sau khi duyệt gợi ý.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const uploadReferenceAsset = useMutation({
    mutationFn: () => {
      if (!effectiveSeriesId) throw new Error('Chọn series trước.');
      if (!referenceFile) throw new Error('Chọn file ảnh tham chiếu.');
      const entityId =
        referenceDraft.entity_type === 'character'
          ? referenceDraft.entity_id || profilesQuery.data?.[0]?.id || ''
          : referenceDraft.entity_id.trim();
      if (!entityId) throw new Error('Chọn nhân vật hoặc nhập mã địa điểm.');
      return apiClient.uploadSeriesReferenceAsset(effectiveSeriesId, {
        file: referenceFile,
        entity_type: referenceDraft.entity_type,
        entity_id: entityId,
        reference_role: referenceDraft.reference_role,
        label: referenceDraft.label.trim() || null,
        source_type: 'upload',
      });
    },
    onSuccess: () => {
      setReferenceFile(null);
      setReferenceDraft((current) => ({ ...current, label: '' }));
      setNotice('Đã tải ảnh tham chiếu. Ảnh đang chờ duyệt trước khi vào prompt.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const updateReferenceStatus = useMutation({
    mutationFn: ({
      asset,
      approval_status,
      active,
      reason,
    }: {
      asset: SeriesReferenceAssetResponse;
      approval_status?: SeriesReferenceApprovalStatus | null;
      active?: boolean | null;
      reason: string;
    }) =>
      apiClient.updateSeriesReferenceAssetStatus(effectiveSeriesId, asset.id, {
        approval_status,
        active,
        reason,
      }),
    onSuccess: () => {
      setNotice('Đã cập nhật trạng thái ảnh tham chiếu.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const deleteReferenceAsset = useMutation({
    mutationFn: (asset: SeriesReferenceAssetResponse) =>
      apiClient.deleteSeriesReferenceAsset(effectiveSeriesId, asset.id),
    onSuccess: (result) => {
      setNotice(
        result.archived
          ? 'Ảnh đang được artifact dùng nên đã lưu trữ an toàn.'
          : 'Đã xoá ảnh tham chiếu.',
      );
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const requestTargetedRegeneration = useMutation({
    mutationFn: () =>
      apiClient.requestSeriesTargetedRegeneration(effectiveSeriesId, {
        event_ids: staleEventsQuery.data?.items.map((event) => event.id) ?? [],
      }),
    onSuccess: (result) => {
      setNotice(result.message);
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const createEpisode = useMutation({
    mutationFn: () => {
      if (!effectiveSeriesId) throw new Error('Chọn series trước.');
      const outputSettings = episodeDraft.output_settings;
      const hasPromptSegmentSettings = Boolean(
        outputSettings.video.prompt_segment_count &&
          outputSettings.video.prompt_segment_duration_seconds,
      );
      return apiClient.createStoryEpisode(effectiveSeriesId, {
        title: episodeDraft.title.trim() || null,
        output_intent:
          selectedSeries?.series_mode === 'image_story_only'
            ? 'truyen_anh'
            : episodeDraft.output_intent,
        market_profile: episodeDraft.market_profile,
        language_profile: episodeDraft.language_profile,
        source_input: episodeDraft.source_input.trim() || null,
        output_settings: {
          image: {
            ...outputSettings.image,
            panel_count:
              outputSettings.image.panel_mode === 'manual'
                ? outputSettings.image.panel_count
                : null,
          },
          video: {
            ...outputSettings.video,
            call_to_action_style: outputSettings.video.call_to_action_style || null,
            target_duration_seconds: outputSettings.video.target_duration_seconds || null,
            default_shot_duration_seconds: outputSettings.video.default_shot_duration_seconds ?? null,
            prompt_segment_count: hasPromptSegmentSettings
              ? outputSettings.video.prompt_segment_count
              : null,
            prompt_segment_duration_seconds: hasPromptSegmentSettings
              ? outputSettings.video.prompt_segment_duration_seconds
              : null,
            micro_scenes_per_prompt: hasPromptSegmentSettings
              ? outputSettings.video.micro_scenes_per_prompt ||
                DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT
              : null,
          },
        },
      });
    },
    onSuccess: (episode) => {
      setSelectedEpisodeId(episode.id);
      setEpisodeDraft((current) => ({ ...current, title: '', source_input: '' }));
      setNotice('Đã tạo Story Episode.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const handleMutationError = (error: unknown) => {
    setNotice(getErrorMessage(error));
    invalidateStory();
  };
  const handleEpisodeActionSuccess = (episode: StoryEpisodeResponse, message: string) => {
    setSelectedEpisodeId(episode.id);
    setNotice(message);
    invalidateStory();
  };

  const generateCandidates = useStoryEpisodeAction(
    () => apiClient.generateStoryCandidates(selectedEpisode!.id),
    'Đã tạo đúng 3 hướng kịch bản.',
    handleEpisodeActionSuccess,
    handleMutationError,
  );
  const approveMaster = useStoryEpisodeAction(
    () => apiClient.approveStoryMaster(selectedEpisode!.id, { approved: true }),
    'Đã duyệt truyện chính.',
    handleEpisodeActionSuccess,
    handleMutationError,
  );

  const synthesizeMaster = useStoryEpisodeAction(
    () =>
      apiClient.synthesizeStoryMaster(selectedEpisode!.id, {
        candidate_ids: selectedEpisode!.candidates
          .filter((candidate) => candidate.generation_status === 'completed')
          .map((candidate) => candidate.id),
      }),
    'Đã tổng hợp phần tốt nhất thành truyện chính chờ duyệt.',
    handleEpisodeActionSuccess,
    handleMutationError,
  );

  const handleAdaptationActionSuccess = (
    adaptation: StoryAdaptationResponse,
    message: string,
    after?: (adaptation: StoryAdaptationResponse) => void,
  ) => {
    after?.(adaptation);
    setNotice(message);
    invalidateStory();
  };

  const createImage = useStoryAdaptationAction(
    () => apiClient.createStoryImageAdaptation(selectedEpisode!.id),
    'Đã tạo panel và prompt ảnh. Hãy duyệt prompt trước khi render.',
    handleAdaptationActionSuccess,
    handleMutationError,
  );
  const approvePrompts = useStoryAdaptationAction(
    () =>
      apiClient.approveStoryImagePrompts(selectedEpisode!.id, {
        approved: true,
        canon_override_reason: canonOverrideReason.trim() || null,
      }),
    'Đã duyệt prompt. Vì chưa có provider ảnh, trạng thái đang chờ provider.',
    handleAdaptationActionSuccess,
    handleMutationError,
  );
  const requestRender = useStoryAdaptationAction(
    () => apiClient.requestStoryImageRender(selectedEpisode!.id),
    'Chưa có image provider/API key. Prompt đã được giữ ở trạng thái chờ provider.',
    handleAdaptationActionSuccess,
    handleMutationError,
  );
  const createVideo = useStoryAdaptationAction(
    () =>
      apiClient.createStoryVideoAdaptation(selectedEpisode!.id, {
        open_existing: true,
        source_mode: 'master_story',
      }),
    'Đã handoff Master Story sang AI Video project.',
    handleAdaptationActionSuccess,
    handleMutationError,
  );
  const createVideoFromPrompts = useStoryAdaptationAction(
    () =>
      apiClient.createStoryVideoAdaptation(selectedEpisode!.id, {
        open_existing: true,
        source_mode: 'image_story_prompts',
        start_auto_run: true,
        material_target: 'prompts_only',
      }),
    'Đã tạo AI Video project từ prompt truyện và auto-run đến bước prompt video. Chưa render ảnh/video.',
    handleAdaptationActionSuccess,
    handleMutationError,
  );
  const suggestStoryUpdates = useMutation({
    mutationFn: () => apiClient.suggestStoryUpdates(selectedEpisode!.id),
    onSuccess: (suggestion) => {
      setStorySuggestion(suggestion);
      setNotice(suggestion.message);
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });
  const approveStoryUpdates = useMutation({
    mutationFn: () => {
      if (!storySuggestion) throw new Error('Chưa có đề xuất để duyệt.');
      return apiClient.approveStoryUpdates(selectedEpisode!.id, {
        approved: true,
        suggestions: storySuggestion.suggestions,
      });
    },
    onSuccess: (suggestion) => {
      setStorySuggestion(null);
      setNotice(suggestion.message);
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });
  const rejectStoryUpdates = useMutation({
    mutationFn: () =>
      apiClient.approveStoryUpdates(selectedEpisode!.id, {
        approved: false,
        suggestions: storySuggestion?.suggestions ?? [],
      }),
    onSuccess: (suggestion) => {
      setStorySuggestion(null);
      setNotice(suggestion.message);
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });
  const exportPrompts = useMutation({
    mutationFn: () => apiClient.exportStoryImagePrompts(selectedEpisode!.id),
    onSuccess: (text) => {
      setExportText(text);
      setNotice('Đã xuất câu lệnh ảnh ra khung bên dưới.');
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const copyPromptText = async (key: string, value: string) => {
    try {
      await writeClipboardText(value);
      setCopiedPromptKey(key);
      setNotice(
        key.startsWith('all-prompts') ? 'Đã sao chép toàn bộ câu lệnh ảnh.' : 'Đã sao chép câu lệnh ảnh.',
      );
    } catch (error) {
      setNotice(getErrorMessage(error));
    }
  };

  const autoRunToImagePrompts = useMutation({
    mutationFn: async () => {
      if (!selectedEpisode) throw new Error('Chọn Story Episode trước.');
      const episodeId = selectedEpisode.id;
      let episode: StoryEpisodeResponse = await apiClient.getStoryEpisode(episodeId);

      let completedCandidates = episode.candidates.filter(
        (candidate) => candidate.generation_status === 'completed',
      );
      if (completedCandidates.length < 3) {
        setAutoRunStep('Tạo 3 hướng kịch bản...');
        episode = await apiClient.generateStoryCandidates(episodeId);
        completedCandidates = episode.candidates.filter(
          (candidate) => candidate.generation_status === 'completed',
        );
      }

      if (completedCandidates.length < 3) {
        throw new Error(
          `Chưa đủ 3 bản nháp dùng được (${completedCandidates.length}/3). Kiểm tra lỗi bản nháp trước khi chạy tiếp.`,
        );
      }

      if (!episode.master_story_json) {
        setAutoRunStep('Tổng hợp truyện chính...');
        episode = await apiClient.synthesizeStoryMaster(episodeId, {
          candidate_ids: completedCandidates.map((candidate) => candidate.id),
        });
      }

      if (!episode.master_story_json) {
        throw new Error('Chưa tạo được truyện chính để duyệt.');
      }

      if (episode.approval_status !== 'approved') {
        setAutoRunStep('Duyệt truyện chính...');
        episode = await apiClient.approveStoryMaster(episodeId, { approved: true });
      }

      const existingImageAdaptation = episode.adaptations.find(
        (adaptation) => adaptation.kind === 'image_story',
      );
      const existingPanels = panelsFrom(existingImageAdaptation);
      if (existingImageAdaptation && existingPanels.length) {
        return { episodeId, panels: existingPanels, created: false };
      }

      setAutoRunStep('Tạo khung và câu lệnh ảnh...');
      const adaptation = await apiClient.createStoryImageAdaptation(episodeId);
      return { episodeId, panels: panelsFrom(adaptation), created: true };
    },
    onSuccess: ({ episodeId, panels: generatedPanels, created }) => {
      setSelectedEpisodeId(episodeId);
      setPromptLibrarySnapshot(generatedPanels);
      setPromptLibraryOpen(true);
      setNotice(
        created
          ? `Đã tự chạy đến bước câu lệnh ảnh (${generatedPanels.length} câu lệnh). Chưa dựng ảnh.`
          : `Tập này đã có ${generatedPanels.length} câu lệnh ảnh. Chưa dựng ảnh.`,
      );
      invalidateStory();
    },
    onError: handleMutationError,
    onSettled: () => setAutoRunStep(null),
  });

  const selectCandidate = useMutation({
    mutationFn: (candidateId: string) =>
      apiClient.selectStoryMaster(selectedEpisode!.id, {
        candidate_id: candidateId,
        selection_reason: 'Người dùng chọn bản nháp này làm truyện chính.',
      }),
    onSuccess: (episode) => {
      setSelectedEpisodeId(episode.id);
      setNotice('Đã lưu truyện chính, đang chờ duyệt.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const repairPanelPrompt = useMutation({
    mutationFn: (panelOrder: number) =>
      apiClient.repairStoryImagePanel(selectedEpisode!.id, {
        panel_order: panelOrder,
        max_attempts: 2,
      }),
    onSuccess: () => {
      setNotice('Đã tự sửa prompt và lưu lịch sử phiên bản. Prompt vẫn cần duyệt thủ công.');
      invalidateStory();
    },
    onError: (error) => setNotice(getErrorMessage(error)),
  });

  const busy =
    createSeries.isPending ||
    createProfile.isPending ||
    createEpisode.isPending ||
    generateCandidates.isPending ||
    synthesizeMaster.isPending ||
    selectCandidate.isPending ||
    autoRunToImagePrompts.isPending ||
    approveMaster.isPending ||
    createImage.isPending ||
    approvePrompts.isPending ||
    repairPanelPrompt.isPending ||
    requestRender.isPending ||
    createVideo.isPending ||
    createVideoFromPrompts.isPending ||
    suggestStoryUpdates.isPending ||
    approveStoryUpdates.isPending ||
    rejectStoryUpdates.isPending ||
    approveProfileSuggestion.isPending ||
    uploadReferenceAsset.isPending ||
    updateReferenceStatus.isPending ||
    deleteReferenceAsset.isPending ||
    requestTargetedRegeneration.isPending;

  const referenceRoleOptions =
    referenceDraft.entity_type === 'character' ? characterReferenceRoles : locationReferenceRoles;
  const seriesCount = seriesQuery.data?.length ?? 0;
  const episodeCount = episodesQuery.data?.length ?? 0;
  const profileCount = profilesQuery.data?.length ?? 0;
  const referenceItems = referenceAssetsQuery.data?.items ?? [];
  const referenceCount = referenceAssetsQuery.data?.total ?? referenceItems.length;
  const activeReferenceCount = referenceItems.filter(
    (asset) => asset.active && asset.approval_status === 'approved',
  ).length;
  const candidateRows = selectedEpisode?.candidates ?? [];
  const completedCandidateCount = candidateRows.filter(
    (candidate) => candidate.generation_status === 'completed',
  ).length;
  const scoredCandidateCount = candidateRows.filter(
    (candidate) => candidate.evaluation_status === 'completed',
  ).length;
  const failedCandidateCount = candidateRows.filter(
    (candidate) =>
      candidate.generation_status === 'failed' || candidate.evaluation_status === 'failed',
  ).length;
  const allCandidatesGenerated =
    candidateRows.length === 3 && completedCandidateCount === 3;
  const staleCount = staleEventsQuery.data?.total ?? 0;
  const workflowSteps = [
    {
      icon: BookOpen,
      label: 'Chuỗi',
      detail: selectedSeries?.title || 'Chọn hoặc tạo chuỗi',
      done: Boolean(effectiveSeriesId),
      active: !effectiveSeriesId,
    },
    {
      icon: UserRound,
      label: 'Nhân vật',
      detail: `${profileCount} hồ sơ · ${activeReferenceCount} ảnh đang dùng`,
      done: profileCount > 0 || activeReferenceCount > 0,
      active: Boolean(effectiveSeriesId) && !selectedEpisode,
    },
    {
      icon: FileText,
      label: 'Truyện chính',
      detail: selectedEpisode?.master_story_json
        ? 'Đã có bản chính'
        : selectedEpisode
          ? 'Cần tạo/chọn hướng'
          : 'Chưa chọn tập',
      done: Boolean(selectedEpisode?.master_story_json),
      active: Boolean(selectedEpisode) && !selectedEpisode?.master_story_json,
    },
    {
      icon: Clapperboard,
      label: 'Sản xuất',
      detail: imageAdaptation || videoAdaptation ? 'Đã có bản chuyển thể' : 'Ảnh/video chưa tạo',
      done: Boolean(imageAdaptation || videoAdaptation),
      active: Boolean(selectedEpisode?.master_story_json) && !imageAdaptation && !videoAdaptation,
    },
  ];

  return (
    <div className="h-full min-h-0 overflow-y-auto bg-background py-3 md:py-4 xl:overflow-hidden">
      <div className="mx-auto flex min-h-full w-full max-w-[1680px] flex-col gap-4 px-1 sm:px-2 xl:h-full xl:min-h-0">
      <header className="rounded-lg border border-border/80 bg-card/85 px-4 py-4 shadow-[0_18px_42px_-34px_rgba(0,0,0,0.55)] sm:px-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-foreground text-background">
                <BookOpen className="h-4 w-4" />
              </span>
              <p className="text-sm font-semibold uppercase text-muted-foreground">Xưởng truyện</p>
              <span className="rounded-full border border-border/70 bg-background/70 px-2.5 py-1 text-xs text-muted-foreground">
                Luồng theo chuỗi
              </span>
            </div>
            <h1 className="mt-3 max-w-3xl text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
              Soạn truyện, giữ mạch gốc, chuyển sang video
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Xưởng tạo truyện ảnh và chuyển sang video theo chuỗi. Tập trung vào nhân vật, mạch gốc,
              bản chính và câu lệnh đã duyệt trước khi chuyển sang luồng Video AI.
            </p>
          </div>
          <div className="grid w-full gap-2 sm:grid-cols-2 xl:max-w-xl xl:grid-cols-4">
            <MetricTile
              icon={BookOpen}
              label="Chuỗi"
              value={seriesCount}
              detail={`${episodeCount} tập`}
            />
            <MetricTile
              icon={UserRound}
              label="Nhân vật"
              value={profileCount}
              detail={`${referenceCount} ảnh tham chiếu`}
            />
            <MetricTile
              icon={ShieldCheck}
              label="Mạch gốc"
              value={staleCount ? `${staleCount}` : 'Ổn'}
              detail={staleCount ? 'cần tạo lại' : 'ổn định'}
              tone={staleCount ? 'warn' : 'good'}
            />
            <MetricTile
              icon={ImageIcon}
              label="Khung truyện"
              value={panels.length}
              detail={videoAdaptation ? 'có video' : 'ảnh/video'}
            />
          </div>
        </div>
        <div className="mt-4 grid gap-2 lg:grid-cols-4">
          {workflowSteps.map((step) => (
            <WorkflowStep key={step.label} {...step} />
          ))}
        </div>
        {notice ? (
          <output
            className="mt-4 rounded-lg border border-primary/25 bg-primary/10 px-3 py-2 text-sm leading-relaxed text-foreground"
            aria-live="polite"
          >
            {notice}
          </output>
        ) : null}
      </header>

      <div className="grid min-h-0 flex-1 gap-4 pb-4 xl:grid-cols-[300px_minmax(0,1fr)_300px] xl:overflow-hidden 2xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <aside className="min-h-0 overflow-auto rounded-lg border border-border/80 bg-card/80 p-4 shadow-[0_16px_36px_-32px_rgba(0,0,0,0.55)] [scrollbar-gutter:stable] xl:order-1">
          <SectionTitle icon={BookOpen} title="Chuỗi" />
          <div className="mt-4 rounded-lg border border-border/70 bg-background/70 p-3">
            {seriesQuery.isLoading ? (
              <SkeletonText />
            ) : selectedSeries ? (
              <div className="grid gap-2 text-sm">
                <p className="font-semibold text-foreground">{selectedSeries.title}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {seriesModeLabel(selectedSeries.series_mode)} ·{' '}
                  {selectedSeries.story_episode_count} tập truyện ·{' '}
                  {selectedSeries.video_episode_count} tập video ·{' '}
                  {selectedSeries.character_profiles?.length ?? 0} hồ sơ nhân vật
                </p>
                <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                  {selectedSeries.character_bible?.trim() ||
                    selectedSeries.world_bible?.trim() ||
                    'Series này chưa có preview Bible.'}
                </p>
              </div>
            ) : (
              <p className="text-sm leading-relaxed text-muted-foreground">
                Chưa có series truyện ảnh hoặc hybrid được chọn.
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSeriesPickerOpen(true)}
                disabled={createSeries.isPending}
              >
                <BookOpen className="h-4 w-4" />
                Chọn series
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSeriesCreateDialogOpen(true)}
                disabled={createSeries.isPending}
              >
                <Plus className="h-4 w-4" />
                Tạo series
              </Button>
            </div>
          </div>
        </aside>

        <aside className="min-h-0 overflow-auto rounded-lg border border-border/80 bg-card/80 p-4 shadow-[0_16px_36px_-32px_rgba(0,0,0,0.55)] [scrollbar-gutter:stable] xl:order-3">
          <SectionTitle icon={UserRound} title="Nhân vật và tập" />
          <div className="mt-4 grid gap-3">
            <div className="rounded-lg border border-border/70 bg-background/70 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">Hồ sơ nhân vật</p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!effectiveSeriesId || suggestProfiles.isPending}
                  onClick={() => suggestProfiles.mutate()}
                >
                  {suggestProfiles.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Gợi ý từ Bible
                </Button>
              </div>
              <div className="mt-3 grid gap-2">
                {(profilesQuery.data ?? []).map((profile) => (
                  <div
                    key={profile.id}
                    className="rounded-lg border border-border/60 bg-muted/20 p-2 text-xs"
                  >
                    <p className="font-medium text-foreground">{profile.name}</p>
                    <p className="mt-1 text-muted-foreground">
                      {profile.role || 'Chưa có vai trò'}
                    </p>
                    {profile.fixed_traits ? (
                      <p className="mt-1 line-clamp-2 text-muted-foreground">
                        Không đổi: {profile.fixed_traits}
                      </p>
                    ) : null}
                  </div>
                ))}
                {!profilesQuery.data?.length ? (
                  <p className="rounded-lg border border-dashed border-border p-2 text-xs text-muted-foreground">
                    Chưa có Hồ sơ nhân vật. Character Bible cũ vẫn là fallback.
                  </p>
                ) : null}
              </div>
              <div className="mt-3 rounded-lg border border-border/70 bg-background/80 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-foreground">Thư viện ảnh tham chiếu</p>
                  <span className="text-[11px] text-muted-foreground">
                    {referenceAssetsQuery.data?.total ?? 0} ảnh
                  </span>
                </div>
                <div className="mt-3 grid gap-2">
                  <FieldLabel label="Loại đối tượng" compact>
                    <select
                      value={referenceDraft.entity_type}
                      onChange={(event) =>
                        setReferenceDraft((current) => ({
                          ...current,
                          entity_type: event.target.value,
                          entity_id: '',
                          reference_role:
                            event.target.value === 'character' ? 'face_front' : 'wide_view',
                        }))
                      }
                      className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    >
                      <option value="character">Nhân vật</option>
                      <option value="location">Địa điểm</option>
                    </select>
                  </FieldLabel>
                  {referenceDraft.entity_type === 'character' ? (
                    <FieldLabel label="Nhân vật" compact>
                      <select
                        value={referenceDraft.entity_id || profilesQuery.data?.[0]?.id || ''}
                        onChange={(event) =>
                          setReferenceDraft((current) => ({
                            ...current,
                            entity_id: event.target.value,
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {(profilesQuery.data ?? []).map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                  ) : (
                    <FieldLabel label="Địa điểm" compact>
                      <input
                        value={referenceDraft.entity_id}
                        onChange={(event) =>
                          setReferenceDraft((current) => ({
                            ...current,
                            entity_id: event.target.value,
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                        placeholder="Mã/tên địa điểm"
                      />
                    </FieldLabel>
                  )}
                  <FieldLabel label="Vai trò ảnh" compact>
                    <select
                      value={referenceDraft.reference_role}
                      onChange={(event) =>
                        setReferenceDraft((current) => ({
                          ...current,
                          reference_role: event.target.value,
                        }))
                      }
                      className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    >
                      {referenceRoleOptions.map((role) => (
                        <option key={role} value={role}>
                          {referenceRoleLabel(role)}
                        </option>
                      ))}
                    </select>
                  </FieldLabel>
                  <FieldLabel label="Nhãn ảnh" compact>
                    <input
                      value={referenceDraft.label}
                      onChange={(event) =>
                        setReferenceDraft((current) => ({ ...current, label: event.target.value }))
                      }
                      className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      placeholder="Ví dụ: mặt chính diện, trang phục tập 2"
                    />
                  </FieldLabel>
                  <FieldLabel label="File ảnh" compact>
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(event) => setReferenceFile(event.target.files?.[0] ?? null)}
                      className="min-h-9 rounded-lg border border-dashed border-border bg-background px-2 py-1.5 text-xs text-muted-foreground file:mr-2 file:h-7 file:rounded-md file:border-0 file:bg-muted file:px-2 file:text-xs"
                    />
                  </FieldLabel>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={
                      busy ||
                      !referenceFile ||
                      (referenceDraft.entity_type === 'character' && !profilesQuery.data?.length)
                    }
                    onClick={() => uploadReferenceAsset.mutate()}
                  >
                    {uploadReferenceAsset.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    Tải ảnh
                  </Button>
                </div>
                <div className="mt-3 grid gap-2">
                  {(referenceAssetsQuery.data?.items ?? []).slice(0, 8).map((asset) => (
                    <div
                      key={asset.id}
                      className="rounded-lg border border-border/60 bg-muted/20 p-2 text-xs"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-medium text-foreground">
                            {asset.label || asset.original_filename || 'Ảnh tham chiếu'}
                          </p>
                          <p className="mt-1 text-muted-foreground">
                            {referenceEntityLabel(asset, profilesQuery.data ?? [])} ·{' '}
                            {referenceRoleLabel(asset.reference_role)} · rev {asset.revision}
                          </p>
                          <p className="mt-1 text-muted-foreground">
                            {statusLabel(asset.approval_status)} ·{' '}
                            {asset.active ? 'đang hoạt động' : 'chưa hoạt động'} · dùng{' '}
                            {asset.usage_count} lần
                          </p>
                        </div>
                        <ImageIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      </div>
                      {asset.thumbnail_path ? (
                        <p className="mt-1 truncate text-[11px] text-muted-foreground">
                          Thumb: {asset.thumbnail_path}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {asset.approval_status !== 'approved' || !asset.active ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-[11px]"
                            disabled={busy}
                            onClick={() =>
                              updateReferenceStatus.mutate({
                                asset,
                                approval_status: 'approved',
                                active: true,
                                reason: 'Duyệt ảnh tham chiếu để dùng trong prompt.',
                              })
                            }
                          >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Duyệt
                          </Button>
                        ) : null}
                        {asset.active ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-[11px]"
                            disabled={busy}
                            onClick={() =>
                              updateReferenceStatus.mutate({
                                asset,
                                active: false,
                                reason: 'Vô hiệu hóa ảnh tham chiếu khỏi prompt mới.',
                              })
                            }
                          >
                            <X className="h-3.5 w-3.5" />
                            Tắt
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-[11px]"
                          disabled={busy}
                          onClick={() => deleteReferenceAsset.mutate(asset)}
                        >
                          Xoá an toàn
                        </Button>
                      </div>
                    </div>
                  ))}
                  {!referenceAssetsQuery.isLoading && !referenceAssetsQuery.data?.items.length ? (
                    <p className="rounded-lg border border-dashed border-border p-2 text-xs text-muted-foreground">
                      Chưa có ảnh tham chiếu. Chỉ ảnh đã duyệt và active mới vào prompt.
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-border/70 bg-background/80 p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-foreground">Phiên bản và cũ</p>
                  <span className="text-muted-foreground">
                    Bản sửa {selectedSeries?.revision ?? 1}
                  </span>
                </div>
                {seriesVersionQuery.data?.items.length ? (
                  <div className="mt-2 text-muted-foreground">
                    <p>{seriesVersionQuery.data.items.length} bản ghi version.</p>
                    {seriesVersionQuery.data.diff_vi.slice(0, 3).map((line) => (
                      <p key={line} className="mt-1">
                        {line}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-muted-foreground">
                    Chưa có lịch sử version cho series này.
                  </p>
                )}
                <div className="mt-3 border-t border-border/60 pt-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-foreground">Artifact cần tạo lại</p>
                    <span className="text-muted-foreground">
                      {staleEventsQuery.data?.total ?? 0}
                    </span>
                  </div>
                  {(staleEventsQuery.data?.items ?? []).slice(0, 5).map((event) => (
                    <p key={event.id} className="mt-1 text-muted-foreground">
                      {event.artifact_type} · {event.reason_vi}
                    </p>
                  ))}
                  {staleEventsQuery.data?.items.length ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 h-8"
                      disabled={busy}
                      onClick={() => requestTargetedRegeneration.mutate()}
                    >
                      {requestTargetedRegeneration.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Tạo lại đúng phạm vi
                    </Button>
                  ) : (
                    <p className="mt-1 text-muted-foreground">Không có stale event active.</p>
                  )}
                </div>
              </div>
              {profileSuggestion ? (
                <div className="mt-3 rounded-lg border border-primary/30 bg-primary/10 p-3 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-foreground">Gợi ý hồ sơ nháp</p>
                      <p className="mt-1 text-muted-foreground">
                        {profileSuggestion.name} · {profileSuggestion.role || 'Chưa có vai trò'}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 px-2"
                      onClick={() => setProfileSuggestion(null)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  {profileSuggestion.fixed_traits ? (
                    <p className="mt-2 text-muted-foreground">
                      Không đổi: {profileSuggestion.fixed_traits}
                    </p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={approveProfileSuggestion.isPending}
                      onClick={() => approveProfileSuggestion.mutate()}
                    >
                      {approveProfileSuggestion.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                      Duyệt và lưu
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setProfileSuggestion(null)}>
                      <X className="h-4 w-4" />
                      Bỏ qua
                    </Button>
                  </div>
                </div>
              ) : null}
              <div className="mt-3 grid gap-2">
                <FieldLabel label="Tên nhân vật">
                  <input
                    value={profileDraft.name}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, name: event.target.value }))
                    }
                    className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    placeholder="Ví dụ: Linh"
                  />
                </FieldLabel>
                {(
                  [
                    ['role', 'Vai trò'],
                    ['face_description', 'Khuôn mặt'],
                    ['hair_description', 'Tóc'],
                    ['body_description', 'Vóc dáng'],
                    ['signature_outfit', 'Trang phục đặc trưng'],
                    ['personality', 'Tính cách'],
                    ['speech_style', 'Cách nói chuyện'],
                    ['fixed_traits', 'Những điều không được thay đổi'],
                  ] as const
                ).map(([field, placeholder]) => (
                  <FieldLabel key={field} label={placeholder}>
                    <textarea
                      value={(profileDraft[field] as string | null | undefined) ?? ''}
                      onChange={(event) =>
                        setProfileDraft((current) => ({ ...current, [field]: event.target.value }))
                      }
                      className="min-h-16 rounded-lg border border-input bg-background px-3 py-2 text-sm leading-relaxed outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      placeholder={`Nhập ${placeholder.toLowerCase()}`}
                    />
                  </FieldLabel>
                ))}
                <Button
                  size="sm"
                  className="justify-self-start"
                  disabled={createProfile.isPending || !profileDraft.name.trim()}
                  onClick={() => createProfile.mutate()}
                >
                  {createProfile.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  Lưu nhân vật
                </Button>
              </div>
            </div>

            <div className="rounded-lg border border-border/70 bg-background/70 p-3">
              <p className="text-sm font-semibold">Tạo tập Story Studio</p>
              <div className="mt-3 grid gap-2">
                <FieldLabel label="Tên tập">
                  <input
                    value={episodeDraft.title}
                    onChange={(event) =>
                      setEpisodeDraft((current) => ({ ...current, title: event.target.value }))
                    }
                    className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    placeholder="Ví dụ: Tập 01 - Cánh cửa sau mưa"
                  />
                </FieldLabel>
                <FieldLabel label="Đầu ra">
                  <select
                    value={
                      selectedSeries?.series_mode === 'image_story_only'
                        ? 'truyen_anh'
                        : episodeDraft.output_intent
                    }
                    disabled={selectedSeries?.series_mode === 'image_story_only'}
                    onChange={(event) =>
                      setEpisodeDraft((current) => ({
                        ...current,
                        output_intent: event.target.value as StoryOutputIntent,
                      }))
                    }
                    className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10 disabled:opacity-60"
                  >
                    <option value="truyen_anh">Truyện ảnh</option>
                    <option value="video_truyen">Video truyện</option>
                    <option value="ca_hai">Cả hai</option>
                  </select>
                </FieldLabel>
                <div className="grid gap-2 border-t border-border/60 pt-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <FieldLabel label="Số ảnh" compact>
                      <select
                        value={episodeDraft.output_settings.image.panel_mode}
                        onChange={(event) => {
                          const panelMode = event.target.value as StoryImagePanelMode;
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              image: {
                                ...current.output_settings.image,
                                panel_mode: panelMode,
                                panel_count:
                                  panelMode === 'manual'
                                    ? current.output_settings.image.panel_count ?? 24
                                    : null,
                              },
                            },
                          }));
                        }}
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        <option value="auto">{panelModeLabel('auto')}</option>
                        <option value="manual">{panelModeLabel('manual')}</option>
                      </select>
                    </FieldLabel>
                    <FieldLabel label="Panel ảnh" compact>
                      <input
                        type="number"
                        min={1}
                        max={200}
                        value={episodeDraft.output_settings.image.panel_count ?? ''}
                        disabled={episodeDraft.output_settings.image.panel_mode !== 'manual'}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              image: {
                                ...current.output_settings.image,
                                panel_count: optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10 disabled:opacity-60"
                        placeholder="Auto"
                      />
                    </FieldLabel>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <FieldLabel label="Tỷ lệ ảnh" compact>
                      <select
                        value={episodeDraft.output_settings.image.aspect_ratio}
                        onChange={(event) => {
                          const aspectRatio = event.target.value as StoryImageAspectRatio;
                          const size = imageAspectSizes[aspectRatio];
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              image: {
                                ...current.output_settings.image,
                                aspect_ratio: aspectRatio,
                                width: size.width,
                                height: size.height,
                              },
                            },
                          }));
                        }}
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {storyImageAspectOptions.map((aspectRatio) => (
                          <option key={aspectRatio} value={aspectRatio}>
                            {aspectRatio}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel label="Rộng" compact>
                      <input
                        type="number"
                        min={256}
                        max={8192}
                        value={episodeDraft.output_settings.image.width}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              image: {
                                ...current.output_settings.image,
                                width: optionalPositiveInt(event.target.value) ?? 720,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      />
                    </FieldLabel>
                    <FieldLabel label="Cao" compact>
                      <input
                        type="number"
                        min={256}
                        max={8192}
                        value={episodeDraft.output_settings.image.height}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              image: {
                                ...current.output_settings.image,
                                height: optionalPositiveInt(event.target.value) ?? 1280,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      />
                    </FieldLabel>
                  </div>
                  <div className="grid gap-2 border-t border-border/60 pt-3 sm:grid-cols-2">
                    <FieldLabel label="Tỷ lệ video" compact>
                      <select
                        value={episodeDraft.output_settings.video.aspect_ratio}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                aspect_ratio: event.target.value as StoryVideoAspectRatio,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {storyVideoAspectOptions.map((aspectRatio) => (
                          <option key={aspectRatio} value={aspectRatio}>
                            {aspectRatio}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel
                      label="Ngôn ngữ truyện/video"
                      hint="Dùng cho lời thoại, kịch bản, phụ đề và thuyết minh; không đổi ngôn ngữ app."
                      compact
                    >
                      <select
                        value={episodeDraft.output_settings.video.target_language}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            language_profile: event.target.value,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                target_language: event.target.value as VideoLanguage,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {LANGUAGE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel label="Mục đích video" compact>
                      <select
                        value={episodeDraft.output_settings.video.video_purpose}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                video_purpose: event.target.value as VideoPurpose,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {(
                          [
                            'custom',
                            'vietnam_market',
                            'global_short',
                            'educational_explainer',
                            'sales_ad',
                            'localized_variant',
                          ] as VideoPurpose[]
                        ).map((purpose) => (
                          <option key={purpose} value={purpose}>
                            {videoPurposeLabel(purpose)}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel label="Thoại" compact>
                      <select
                        value={episodeDraft.output_settings.video.dialogue_mode}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                dialogue_mode: event.target.value as DialogueMode,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {(['voiceover', 'character_lines', 'mixed'] as DialogueMode[]).map((mode) => (
                          <option key={mode} value={mode}>
                            {dialogueModeLabel(mode)}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel label="Mật độ lời" compact>
                      <select
                        value={episodeDraft.output_settings.video.narration_density}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                narration_density: event.target.value as NarrationDensity,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {(['light', 'balanced', 'dense'] as NarrationDensity[]).map((density) => (
                          <option key={density} value={density}>
                            {narrationDensityLabel(density)}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                    <FieldLabel
                      label="Lời kêu gọi hành động"
                      hint="Câu nhắc người xem ở cuối video. Chọn Không dùng nếu chỉ muốn kể truyện."
                      compact
                    >
                      <select
                        value={episodeDraft.output_settings.video.call_to_action_style ?? 'none'}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                call_to_action_style: event.target.value as CallToActionStyle,
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      >
                        {(['none', 'soft', 'direct', 'urgent'] as CallToActionStyle[]).map((style) => (
                          <option key={style} value={style}>
                            {callToActionStyleLabel(style)}
                          </option>
                        ))}
                      </select>
                    </FieldLabel>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-background/60 px-3 py-2 text-xs leading-5 text-muted-foreground">
                    <span className="font-semibold text-foreground">Cách chia video: </span>
                    {videoDurationSummary(episodeDraft.output_settings.video)}
                    <span className="mt-1 block">
                      Có thể dùng cách dễ là chỉ nhập Thời lượng video, hoặc cách kiểm soát là nhập Số prompt video + Giây mỗi prompt.
                    </span>
                  </div>
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                    <FieldLabel label="Thời lượng video" compact>
                      <input
                        type="number"
                        min={5}
                        max={7200}
                        value={episodeDraft.output_settings.video.target_duration_seconds ?? ''}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                target_duration_seconds: optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                        placeholder="Auto"
                      />
                    </FieldLabel>
                    <FieldLabel label="Giây mỗi shot" compact>
                      <input
                        type="number"
                        min={1}
                        max={5}
                        value={episodeDraft.output_settings.video.default_shot_duration_seconds ?? ''}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                default_shot_duration_seconds:
                                  optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      />
                    </FieldLabel>
                    <FieldLabel label="Số prompt video" compact>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={episodeDraft.output_settings.video.prompt_segment_count ?? ''}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                prompt_segment_count: optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                        placeholder="Auto"
                      />
                    </FieldLabel>
                    <FieldLabel label="Giây mỗi prompt" compact>
                      <input
                        type="number"
                        min={3}
                        max={30}
                        value={episodeDraft.output_settings.video.prompt_segment_duration_seconds ?? ''}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                prompt_segment_duration_seconds: optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                        placeholder="Auto"
                      />
                    </FieldLabel>
                    <FieldLabel label="Cảnh nhỏ / prompt" compact>
                      <input
                        type="number"
                        min={1}
                        max={5}
                        value={episodeDraft.output_settings.video.micro_scenes_per_prompt ?? ''}
                        onChange={(event) =>
                          setEpisodeDraft((current) => ({
                            ...current,
                            output_settings: {
                              ...current.output_settings,
                              video: {
                                ...current.output_settings.video,
                                micro_scenes_per_prompt: optionalPositiveInt(event.target.value),
                              },
                            },
                          }))
                        }
                        className="h-9 rounded-lg border border-input bg-background px-2 text-xs outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      />
                    </FieldLabel>
                  </div>
                </div>
                <FieldLabel
                  label="Nguồn nội dung"
                  hint="Có thể dán tóm tắt, beat chính, yêu cầu giữ canon hoặc phong cách thoại."
                >
                  <textarea
                    value={episodeDraft.source_input}
                    onChange={(event) =>
                      setEpisodeDraft((current) => ({
                        ...current,
                        source_input: event.target.value,
                      }))
                    }
                    className="min-h-32 rounded-lg border border-input bg-background px-3 py-3 text-sm leading-relaxed outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    placeholder="Nguồn truyện, ý tưởng, diễn biến hoặc yêu cầu tập này"
                  />
                </FieldLabel>
                <Button
                  size="sm"
                  className="justify-self-start"
                  disabled={
                    createEpisode.isPending ||
                    !effectiveSeriesId ||
                    (episodeDraft.output_settings.image.panel_mode === 'manual' &&
                      !episodeDraft.output_settings.image.panel_count)
                  }
                  onClick={() => createEpisode.mutate()}
                >
                  {createEpisode.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                  Tạo tập
                </Button>
              </div>
            </div>

            <div className="grid gap-2">
              {(episodesQuery.data ?? []).map((episode) => (
                <button
                  key={episode.id}
                  type="button"
                  onClick={() => {
                    setSelectedEpisodeId(episode.id);
                    setStorySuggestion(null);
                  }}
                  className={cn(
                    'cursor-pointer rounded-lg border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                    selectedEpisode?.id === episode.id
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-border/70 bg-background/70 hover:bg-muted/40',
                  )}
                >
                  <span className="block font-medium">
                    Tập {String(episode.episode_number).padStart(2, '0')} ·{' '}
                    {episode.title || 'Chưa đặt tên'}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {intentLabel(episode.output_intent)} · {statusLabel(episode.approval_status)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <main className="min-h-0 overflow-auto rounded-lg border border-border/80 bg-card/80 p-4 shadow-[0_16px_36px_-32px_rgba(0,0,0,0.55)] [scrollbar-gutter:stable] xl:order-2">
          {selectedEpisode ? (
            <div className="grid gap-4">
              <section className="rounded-lg border border-border/80 bg-background/80 p-4 shadow-[0_14px_34px_-30px_rgba(0,0,0,0.55)]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold leading-tight">
                      Tập {String(selectedEpisode.episode_number).padStart(2, '0')} ·{' '}
                      {selectedEpisode.title || 'Chưa đặt tên'}
                    </p>
                    <p className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <StatusPill>{intentLabel(selectedEpisode.output_intent)}</StatusPill>
                      <StatusPill
                        tone={selectedEpisode.approval_status === 'approved' ? 'good' : 'default'}
                      >
                        {statusLabel(selectedEpisode.approval_status)}
                      </StatusPill>
                      <StatusPill
                        tone={
                          failedCandidateCount
                            ? 'danger'
                            : allCandidatesGenerated
                              ? 'good'
                              : candidateRows.length
                                ? 'warn'
                                : 'default'
                        }
                      >
                        {completedCandidateCount}/{candidateRows.length || 3} hướng dùng được
                      </StatusPill>
                      {candidateRows.length ? (
                        <StatusPill tone={scoredCandidateCount === 3 ? 'good' : 'default'}>
                          {scoredCandidateCount}/3 đã chấm
                        </StatusPill>
                      ) : null}
                      <StatusPill>{panels.length} khung</StatusPill>
                      <StatusPill>
                        {selectedEpisodeOutputSettings.image.panel_mode === 'manual'
                          ? `${selectedEpisodeOutputSettings.image.panel_count ?? 0} ảnh`
                          : 'Ảnh tự động'}{' '}
                        · {selectedEpisodeOutputSettings.image.aspect_ratio} ·{' '}
                        {selectedEpisodeOutputSettings.image.width}x
                        {selectedEpisodeOutputSettings.image.height}
                      </StatusPill>
                      <StatusPill>
                        Video {selectedEpisodeOutputSettings.video.aspect_ratio} ·{' '}
                        {videoLanguageLabel(selectedEpisodeOutputSettings.video.target_language)} ·{' '}
                        {dialogueModeLabel(selectedEpisodeOutputSettings.video.dialogue_mode)}
                      </StatusPill>
                    </p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <div className="flex flex-wrap justify-start gap-2 sm:justify-end">
                    <Button
                      size="sm"
                      disabled={busy || !selectedEpisode}
                      onClick={() => autoRunToImagePrompts.mutate()}
                    >
                      {autoRunToImagePrompts.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4" />
                      )}
                      Tự động đến câu lệnh ảnh
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => generateCandidates.mutate()}>
                      {generateCandidates.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4" />
                      )}
                      Tạo 3 hướng
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy || !selectedEpisode.master_story_json}
                      onClick={() => approveMaster.mutate()}
                    >
                      <Check className="h-4 w-4" />
                      Duyệt bản chính
                    </Button>
                    </div>
                    {autoRunStep ? (
                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        {autoRunStep}
                      </p>
                    ) : null}
                  </div>
                </div>
                {selectedEpisodeSourceSummary?.has_structured_source ? (
                  <div className="mt-3 rounded-lg border border-primary/20 bg-primary/10 p-3 text-sm">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <Database className="h-4 w-4 text-primary" />
                      <span className="font-medium text-foreground">
                        Nguồn {sourceKindLabel(selectedEpisodeSourceSummary.source_kind)}
                      </span>
                      <StatusPill>rev {selectedEpisodeSourceSummary.revision ?? '-'}</StatusPill>
                      <StatusPill>{selectedEpisodeSourceSummary.chunk_count} đoạn</StatusPill>
                      <StatusPill>{selectedEpisodeSourceSummary.page_count} trang</StatusPill>
                      <StatusPill>{selectedEpisodeSourceSummary.panel_count} khung</StatusPill>
                      <StatusPill>{selectedEpisodeSourceSummary.dialogue_count} lời thoại</StatusPill>
                      {selectedEpisode.current_source_document_id ? (
                        <span className="max-w-full break-all rounded-full border border-border/60 bg-background/70 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                          {selectedEpisode.current_source_document_id}
                        </span>
                      ) : null}
                      {selectedEpisodeSourceSummary.comic_job_id ? (
                        <a
                          href={`/comic-series-analysis/${selectedEpisodeSourceSummary.comic_job_id}`}
                          className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-background/70 px-2 py-0.5 text-xs font-medium text-foreground transition hover:bg-muted/60"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Mở phân tích
                        </a>
                      ) : null}
                    </div>
                    {selectedEpisodeSourceLimitations.length ? (
                      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                        Giới hạn nguồn: {selectedEpisodeSourceLimitations.join(' · ')}
                      </p>
                    ) : null}
                  </div>
                ) : selectedEpisode.source_digest ? (
                  <div className="mt-3 rounded-lg border border-border/70 bg-muted/30 p-3 text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">Nguồn tập:</span>{' '}
                    {selectedEpisode.source_digest}
                  </div>
                ) : null}
                {staleAdaptations.length ? (
                  <div className="mt-3 flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-100">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <p>
                      Có {staleAdaptations.length} bản chuyển thể cần tạo lại vì truyện chính đã thay
                      đổi. Hãy duyệt lại truyện chính rồi tạo lại truyện ảnh hoặc video trước khi dựng
                      tiếp.
                    </p>
                  </div>
                ) : null}
              </section>

              <SeriesBrainPanel
                seriesId={effectiveSeriesId}
                episodeId={selectedEpisode.id}
                disabled={busy}
                onChanged={invalidateStory}
                onNotice={setNotice}
              />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <SectionTitle icon={ListChecks} title="Ba hướng kịch bản" />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={
                    busy ||
                    !allCandidatesGenerated
                  }
                  onClick={() => synthesizeMaster.mutate()}
                >
                  {synthesizeMaster.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Tổng hợp phần tốt nhất
                </Button>
              </div>
              <section className="grid gap-3 xl:grid-cols-3">
                {selectedEpisode.candidates.map((candidate) => {
                  const errorText = candidateErrorMessage(candidate);
                  return (
                  <div
                    key={candidate.id}
                    className={cn(
                      'rounded-lg border p-3 transition duration-200',
                      candidate.selected
                        ? 'border-primary/50 bg-primary/10 shadow-[0_16px_34px_-30px_rgba(0,0,0,0.6)]'
                        : 'border-border/70 bg-background/80 hover:border-border hover:bg-background',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">
                          {textValue(candidate.script_json.strategy_label) ||
                            candidate.strategy_type}
                        </p>
                        {candidate.selected ? (
                        <p className="mt-1 text-xs font-medium text-primary">
                            Đang chọn làm bản chính
                          </p>
                        ) : null}
                      </div>
                        <span className="rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium">
                        Điểm {totalScore(candidate)}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                      <span className="rounded-full border border-border bg-background px-2 py-0.5">
                        Tạo: {statusLabel(candidate.generation_status)}
                      </span>
                      <span className="rounded-full border border-border bg-background px-2 py-0.5">
                        Chấm: {statusLabel(candidate.evaluation_status)}
                      </span>
                      <span className="rounded-full border border-border bg-background px-2 py-0.5">
                        Lần {candidate.generation_attempt || 1}
                      </span>
                    </div>
                    {candidate.model_label || candidate.context_snapshot_id ? (
                      <div className="mt-2 rounded-lg border border-border/60 bg-muted/20 p-2 text-[11px] text-muted-foreground">
                        {candidate.model_label ? <p>Mô hình: {candidate.model_label}</p> : null}
                        {candidate.context_snapshot_id ? (
                          <p>Bản chụp: {candidate.context_snapshot_id}</p>
                        ) : null}
                      </div>
                    ) : null}
                    <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
                      {textValue(candidate.script_json.logline)}
                    </p>
                    {errorText ? (
                      <div className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs leading-relaxed text-destructive">
                        <p className="font-medium">Bản nháp này chưa dùng được</p>
                        <p className="mt-1 line-clamp-4">{errorText}</p>
                      </div>
                    ) : null}
                    <p className="mt-2 text-xs text-muted-foreground">
                      Mạnh: {candidate.strengths}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">Rủi ro: {candidate.risks}</p>
                    {candidateEvaluation(candidate)?.reason_vi ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        Lý do chấm: {textValue(candidateEvaluation(candidate)?.reason_vi)}
                      </p>
                    ) : null}
                    {candidateEvaluation(candidate) ? (
                      <div className="mt-2 grid gap-1 rounded-lg border border-border/60 bg-background/80 p-2 text-xs text-muted-foreground">
                        {listText(candidateEvaluation(candidate)?.evidence).length ? (
                          <p>
                            Bằng chứng:{' '}
                            {listText(candidateEvaluation(candidate)?.evidence)
                              .slice(0, 2)
                              .join(' | ')}
                          </p>
                        ) : null}
                        {listText(candidateEvaluation(candidate)?.weaknesses).length ? (
                          <p>
                            Điểm yếu:{' '}
                            {listText(candidateEvaluation(candidate)?.weaknesses)
                              .slice(0, 2)
                              .join(' | ')}
                          </p>
                        ) : null}
                        {listText(candidateEvaluation(candidate)?.recommended_parts).length ? (
                          <p>
                            Nên lấy:{' '}
                            {listText(candidateEvaluation(candidate)?.recommended_parts)
                              .slice(0, 2)
                              .join(' | ')}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <Button
                      size="sm"
                      className="mt-3 w-full"
                      variant={candidate.selected ? 'outline' : 'default'}
                      disabled={
                        selectCandidate.isPending || candidate.generation_status !== 'completed'
                      }
                      onClick={() => selectCandidate.mutate(candidate.id)}
                    >
                      {candidate.selected ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <FileText className="h-4 w-4" />
                      )}
                      Chọn làm bản chính
                    </Button>
                  </div>
                  );
                })}
                {!selectedEpisode.candidates.length ? (
                  <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground xl:col-span-3">
                    Chưa có bản nháp. Bấm “Tạo 3 hướng” để bắt đầu.
                  </div>
                ) : null}
              </section>

              {selectedEpisode.master_story_json ? (
                <section className="rounded-lg border border-border/70 bg-background/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <SectionTitle icon={FileText} title="Truyện chính" />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => suggestStoryUpdates.mutate()}
                      >
                        {suggestStoryUpdates.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Gợi ý cập nhật
                      </Button>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm">
                    <p className="font-medium">
                      {textValue(selectedEpisode.master_story_json.title)}
                    </p>
                    <p className="text-muted-foreground">
                      {textValue(selectedEpisode.master_story_json.logline)}
                    </p>
                    <p className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-muted/25 p-3 leading-6 text-muted-foreground">
                      {textValue(selectedEpisode.master_story_json.full_story)}
                    </p>
                  </div>
                  {storySuggestion ? (
                    <div className="mt-3 rounded-lg border border-primary/30 bg-primary/10 p-3 text-sm">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">Đề xuất cập nhật series</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Chỉ lưu mạch gốc hoặc Hồ sơ nhân vật sau khi bạn duyệt.
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            disabled={
                              approveStoryUpdates.isPending || !storySuggestion.suggestions.length
                            }
                            onClick={() => approveStoryUpdates.mutate()}
                          >
                            {approveStoryUpdates.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Check className="h-4 w-4" />
                            )}
                            Duyệt
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={rejectStoryUpdates.isPending}
                            onClick={() => rejectStoryUpdates.mutate()}
                          >
                            {rejectStoryUpdates.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <X className="h-4 w-4" />
                            )}
                            Từ chối
                          </Button>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-2">
                        {storySuggestion.suggestions.map((suggestion, index) => (
                          <div
                            key={`${suggestion.type ?? 'suggestion'}-${index}`}
                            className="rounded-lg border border-border/60 bg-background/70 p-3 text-xs"
                          >
                            <p className="font-medium text-foreground">
                              {suggestionTypeLabel(suggestion.type)}
                            </p>
                            <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
                              {textValue(suggestion.proposal)}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="grid gap-3 xl:grid-cols-2">
                <div className="rounded-lg border border-border/70 bg-background/80 p-4">
                  <SectionTitle icon={ImageIcon} title="Truyện ảnh" />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={busy || selectedEpisode.approval_status !== 'approved'}
                      onClick={() => createImage.mutate()}
                    >
                      <ImageIcon className="h-4 w-4" />
                      Tạo khung/câu lệnh
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!panels.length}
                      onClick={() => {
                        setPromptLibrarySnapshot(null);
                        setPromptLibraryOpen(true);
                      }}
                    >
                      <Maximize2 className="h-4 w-4" />
                      Mở popup câu lệnh
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!fullPromptText.trim()}
                      onClick={() => void copyPromptText('all-prompts', fullPromptText)}
                    >
                      {copiedPromptKey === 'all-prompts' ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                      Sao chép toàn bộ câu lệnh
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={
                        busy ||
                        !imageAdaptation ||
                        panelsWithBlockingQuality.length > 0 ||
                        (panelsWithBlockingCanon.length > 0 && !canonOverrideReason.trim())
                      }
                      onClick={() => approvePrompts.mutate()}
                    >
                      <Check className="h-4 w-4" />
                      Duyệt câu lệnh
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy || !imageAdaptation}
                      onClick={() => requestRender.mutate()}
                    >
                      <RefreshCw className="h-4 w-4" />
                      Render ảnh
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!imageAdaptation}
                      onClick={() => exportPrompts.mutate()}
                    >
                      <Download className="h-4 w-4" />
                      Xuất câu lệnh
                    </Button>
                  </div>
                  {panelsWithBlockingCanon.length ? (
                    <div className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs">
                      <div className="flex gap-2 text-destructive">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                        <p>
                          {panelsWithBlockingCanon.length} khung có lỗi mạch gốc chặn. Muốn duyệt vẫn
                          được nhưng phải nhập lý do override để lưu nhật ký.
                        </p>
                      </div>
                      <textarea
                        value={canonOverrideReason}
                        onChange={(event) => setCanonOverrideReason(event.target.value)}
                        className="mt-3 min-h-16 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-foreground/40"
                        placeholder="Lý do ghi đè mạch gốc"
                      />
                    </div>
                  ) : null}
                  {panelsWithBlockingQuality.length ? (
                    <div className="mt-3 flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <p>
                        {panelsWithBlockingQuality.length} khung chưa đạt điểm chất lượng kỹ thuật.
                        Hãy bấm “Tự sửa câu lệnh” hoặc sửa tay trước khi duyệt.
                      </p>
                    </div>
                  ) : null}
                  <div className="mt-3 grid gap-2">
                    {panels.map((panel) => (
                      <div
                        key={panel.order}
                        className="rounded-lg border border-border/60 bg-card/70 p-3 text-xs"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-medium text-foreground">Khung {panel.order}</p>
                            <p className="mt-1 text-muted-foreground">
                              Câu lệnh {statusLabel(panel.prompt_status).toLowerCase()} · Ảnh{' '}
                              {statusLabel(panel.render_status).toLowerCase()}
                            </p>
                          </div>
                          {panel.asset?.image_url ||
                          panel.asset?.image_path ||
                          panel.asset?.provider_asset_id ? (
                            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-700 dark:text-emerald-200">
                              Ảnh đã render
                            </span>
                          ) : null}
                          {qualityCheck(panel) ? (
                            <span
                              className={cn(
                                'rounded-full border px-2 py-0.5',
                                qualityCheck(panel)?.passed
                                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200'
                                  : 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-100',
                              )}
                            >
                              Chất lượng {qualityScoreLabel(panel)}
                            </span>
                          ) : null}
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 px-2"
                            disabled={!panel.prompt?.trim()}
                            onClick={() =>
                              void copyPromptText(`panel-${panel.order}`, panelPromptBlock(panel))
                            }
                          >
                            {copiedPromptKey === `panel-${panel.order}` ? (
                              <Check className="h-3.5 w-3.5" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                            Sao chép câu lệnh
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 px-2"
                            disabled={
                              busy || !imageAdaptation || qualityCheck(panel)?.passed === true
                            }
                            onClick={() => repairPanelPrompt.mutate(panel.order)}
                          >
                            {repairPanelPrompt.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RefreshCw className="h-3.5 w-3.5" />
                            )}
                            Tự sửa câu lệnh
                          </Button>
                        </div>
                        <p className="mt-2 leading-5 text-foreground/85">
                          {panel.caption_or_dialogue}
                        </p>
                        {panel.reader_prompt_vi || panel.prompt_explanation_vi ? (
                          <div className="mt-2 rounded-lg border border-sky-500/25 bg-sky-500/10 p-2 leading-5 text-sky-900 dark:text-sky-100">
                            <p className="font-medium">Bản đọc tiếng Việt</p>
                            <p className="mt-1 whitespace-pre-wrap">
                              {panel.reader_prompt_vi || panel.prompt_explanation_vi}
                            </p>
                          </div>
                        ) : null}
                        <div className="mt-2 grid gap-1 rounded-lg border border-border/60 bg-background/80 p-2 leading-5 text-muted-foreground">
                          {panel.scene_context ? (
                            <p>
                              <span className="font-medium text-foreground">Bối cảnh: </span>
                              {panel.scene_context}
                            </p>
                          ) : null}
                          {panel.camera_angle || panel.composition_notes ? (
                            <p>
                              <span className="font-medium text-foreground">Góc máy/bố cục: </span>
                              {[panel.camera_angle, panel.composition_notes].filter(Boolean).join(' · ')}
                            </p>
                          ) : null}
                          {panel.dialogue_note ? (
                            <p>
                              <span className="font-medium text-foreground">Note thoại: </span>
                              {panel.dialogue_note}
                            </p>
                          ) : null}
                          {panel.visual_description ? (
                            <p>
                              <span className="font-medium text-foreground">Hình ảnh: </span>
                              {panel.visual_description}
                            </p>
                          ) : null}
                        </div>
                        <div className="mt-2 rounded-lg border border-border/60 bg-background/70 p-2 leading-5 text-muted-foreground">
                          <p className="font-medium text-foreground">Bản gửi AI render</p>
                          <p className="mt-1 line-clamp-3">{panel.render_prompt || panel.prompt}</p>
                        </div>
                        {panel.canon_check ? (
                          <div
                            className={cn(
                              'mt-2 rounded-lg border p-2',
                              panel.canon_check.passed
                                ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-800 dark:text-emerald-100'
                                : 'border-destructive/30 bg-destructive/10 text-destructive',
                            )}
                          >
                            <p className="font-medium">
                              {panel.canon_check.passed ? 'Mạch gốc đạt' : 'Mạch gốc có lỗi chặn'}
                            </p>
                            {(panel.canon_check.blocking_conflicts ?? [])
                              .slice(0, 2)
                              .map((item, index) => (
                                <p
                                  key={`panel-${panel.order}-canon-block-${index}`}
                                  className="mt-1"
                                >
                                  {recordText(item, 'message') || briefJson(item)}
                                </p>
                              ))}
                            {(panel.canon_check.warnings ?? []).slice(0, 2).map((item, index) => (
                              <p
                                key={`panel-${panel.order}-canon-warning-${index}`}
                                className="mt-1"
                              >
                                Cảnh báo: {recordText(item, 'message') || briefJson(item)}
                              </p>
                            ))}
                          </div>
                        ) : null}
                        {qualityCheck(panel) ? (
                          <div
                            className={cn(
                              'mt-2 rounded-lg border p-2',
                              qualityCheck(panel)?.passed
                                ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-800 dark:text-emerald-100'
                                : 'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100',
                            )}
                          >
                            <p className="font-medium">
                              {qualityCheck(panel)?.passed
                                ? 'Prompt đạt quality'
                                : 'Prompt cần sửa'}{' '}
                              · {qualityScoreLabel(panel)}
                            </p>
                            {listText(qualityCheck(panel)?.blocking_errors)
                              .slice(0, 3)
                              .map((item, index) => (
                                <p
                                  key={`panel-${panel.order}-quality-error-${index}`}
                                  className="mt-1"
                                >
                                  Lỗi chặn: {item}
                                </p>
                              ))}
                            {listText(qualityCheck(panel)?.warnings)
                              .slice(0, 3)
                              .map((item, index) => (
                                <p
                                  key={`panel-${panel.order}-quality-warning-${index}`}
                                  className="mt-1"
                                >
                                  Cảnh báo: {item}
                                </p>
                              ))}
                            {listText(qualityCheck(panel)?.suggestions)
                              .slice(0, 3)
                              .map((item, index) => (
                                <p
                                  key={`panel-${panel.order}-quality-suggestion-${index}`}
                                  className="mt-1"
                                >
                                  Gợi ý: {item}
                                </p>
                              ))}
                            {listText(qualityCheck(panel)?.evidence)
                              .slice(0, 2)
                              .map((item, index) => (
                                <p
                                  key={`panel-${panel.order}-quality-evidence-${index}`}
                                  className="mt-1"
                                >
                                  Bằng chứng: {item}
                                </p>
                              ))}
                          </div>
                        ) : null}
                        {panel.repair_status ||
                        panel.repair_attempt ||
                        panel.prompt_versions?.length ? (
                          <div className="mt-2 rounded-lg border border-border/60 bg-background/80 p-2 text-muted-foreground">
                            <p>
                              Sửa prompt: {statusLabel(panel.repair_status || 'none')} · lần{' '}
                              {panel.repair_attempt || 0}
                              {panel.prompt_versions?.length
                                ? ` · ${panel.prompt_versions.length} phiên bản`
                                : ''}
                            </p>
                            {latestPanelVersion(panel) ? (
                              <p className="mt-1">
                                Gần nhất:{' '}
                                {recordText(latestPanelVersion(panel), 'reason') ||
                                  'Không có lý do'}{' '}
                                {listText(latestPanelVersion(panel)?.changes).length
                                  ? `· ${listText(latestPanelVersion(panel)?.changes).slice(0, 2).join(' | ')}`
                                  : ''}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                        {panel.series_context_trace_id ||
                        panel.selected_memory_cards?.length ||
                        panel.context_group_usage?.length ? (
                          <div className="mt-2 rounded-lg border border-border/60 bg-background/80 p-2 text-muted-foreground">
                            {panel.series_context_trace_id ? (
                              <p>Trace: {panel.series_context_trace_id}</p>
                            ) : null}
                            {panel.selected_memory_cards?.length ? (
                              <p className="mt-1">
                                Thẻ nhớ:{' '}
                                {panel.selected_memory_cards
                                  .map(
                                    (card) => recordText(card, 'title') || recordText(card, 'id'),
                                  )
                                  .join(', ')}
                              </p>
                            ) : null}
                            {panel.context_group_usage?.length ? (
                              <p className="mt-1">
                                Ngữ cảnh:{' '}
                                {panel.context_group_usage
                                  .map(
                                    (group) =>
                                      `${recordText(group, 'title') || recordText(group, 'group')}: ${recordText(group, 'used_chars') || 0}`,
                                  )
                                  .join(' · ')}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                        {panel.asset?.image_url ? (
                          <a
                            className="mt-3 inline-flex h-8 items-center gap-2 rounded-lg border border-border bg-background px-3 text-xs font-medium hover:bg-muted/40"
                            href={panel.asset.image_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            Mở ảnh
                          </a>
                        ) : null}
                        {panel.asset?.image_path || panel.asset?.provider_asset_id ? (
                          <p className="mt-2 whitespace-pre-wrap rounded-lg bg-background/80 p-2 text-muted-foreground">
                            {panel.asset.image_path ? `File: ${panel.asset.image_path}` : null}
                            {panel.asset.image_path && panel.asset.provider_asset_id ? '\n' : ''}
                            {panel.asset.provider_asset_id
                              ? `Asset provider: ${panel.asset.provider_asset_id}`
                              : null}
                          </p>
                        ) : null}
                        {panel.failure_reason ? (
                          <p className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-destructive">
                            Lỗi render: {panel.failure_reason}
                          </p>
                        ) : null}
                      </div>
                    ))}
                    {imageAdaptation && !panels.length ? (
                      <p className="text-sm text-muted-foreground">Chưa có panel.</p>
                    ) : null}
                  </div>
                </div>

                <div className="rounded-lg border border-border/70 bg-background/80 p-4">
                  <SectionTitle icon={Clapperboard} title="Video truyện" />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={busy || !hasPanelPromptSource}
                      onClick={() => createVideoFromPrompts.mutate()}
                    >
                      {createVideoFromPrompts.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Clapperboard className="h-4 w-4" />
                      )}
                      Tạo prompt video
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={
                        busy ||
                        selectedEpisode.approval_status !== 'approved' ||
                        selectedEpisode.output_intent === 'truyen_anh'
                      }
                      onClick={() => createVideo.mutate()}
                    >
                      <Clapperboard className="h-4 w-4" />
                      Handoff từ Master
                    </Button>
                    {videoAdaptation?.payload_json?.ai_video_url ? (
                      <a
                        className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm hover:bg-muted/40"
                        href={String(videoAdaptation.payload_json.ai_video_url)}
                      >
                        <ExternalLink className="h-4 w-4" />
                        Mở project video
                      </a>
                    ) : null}
                    {videoMp4Url ? (
                      <a
                        className="inline-flex h-9 items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 text-sm font-medium text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-200"
                        href={videoMp4Url}
                      >
                        <Download className="h-4 w-4" />
                        Tải MP4
                      </a>
                    ) : null}
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Nút “Tạo prompt video” dùng prompt truyện ảnh làm nguồn, tự chạy AI Video đến
                    bước prompt video rồi dừng. Flow này không render ảnh, không gọi Veo, không tạo
                    voice/subtitle/MP4.
                  </p>
                  {!hasPanelPromptSource ? (
                    <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-900 dark:text-amber-100">
                      Chưa có prompt truyện ảnh để handoff video. Hãy tạo panel/prompt ở phần Truyện ảnh trước.
                    </p>
                  ) : null}
                  {videoAdaptation ? (
                    <div className="mt-3 rounded-lg border border-border/60 bg-muted/20 p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-foreground">
                          {videoRenderJob
                            ? `Render MP4 ${statusLabel(videoRenderJob.status).toLowerCase()}`
                            : `Handoff ${statusLabel(videoAdaptation.status).toLowerCase()}`}
                        </p>
                        {renderProgressLabel(videoRenderJob?.progress) ? (
                          <span className="rounded-full border border-border bg-background px-2 py-0.5 text-xs text-muted-foreground">
                            {renderProgressLabel(videoRenderJob?.progress)}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <StatusPill>Nguồn: {handoffSourceLabel(videoHandoffSource)}</StatusPill>
                        {videoHandoffSource === 'image_story_prompts' ? (
                          <StatusPill>
                            {videoSourcePanelCount ?? panels.length} panel ·{' '}
                            {videoSourcePromptCount ?? panels.filter((panel) => panel.prompt?.trim()).length}{' '}
                            prompt
                          </StatusPill>
                        ) : null}
                        {videoAutoRunId ? (
                          <StatusPill>
                            Auto-run: {statusLabel(videoAutoRunStatus || 'queued')}
                          </StatusPill>
                        ) : null}
                      </div>
                      {videoAutoRunStep ? (
                        <p className="mt-2 text-muted-foreground">
                          Auto-run hiện tại: {videoAutoRunStep}
                        </p>
                      ) : null}
                      {videoRenderJob?.current_step ? (
                        <p className="mt-2 text-muted-foreground">
                          Bước hiện tại: {videoRenderJob.current_step}
                        </p>
                      ) : null}
                      {videoRenderJob?.failure_reason ? (
                        <p className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-destructive">
                          Lỗi render MP4: {videoRenderJob.failure_reason}
                        </p>
                      ) : null}
                      {videoMp4Url ? (
                        <p className="mt-2 text-muted-foreground">
                          MP4 đã hoàn tất từ pipeline AI Video và sẵn sàng tải xuống.
                        </p>
                      ) : null}
                      {!videoRenderJob && linkedVideoProjectId ? (
                        <p className="mt-2 text-muted-foreground">
                          Project video đã liên kết, chưa có render MP4 hoàn tất.
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </section>

              {exportText ? (
                <section className="rounded-lg border border-border/70 bg-background/70 p-4">
                  <SectionTitle icon={Download} title="Prompt export" />
                  <textarea
                    readOnly
                    value={exportText}
                    className="mt-3 min-h-48 w-full rounded-lg border border-input bg-muted/20 px-3 py-2 font-mono text-xs leading-relaxed outline-none"
                  />
                </section>
              ) : null}
            </div>
          ) : (
            <div className="grid h-full place-items-center rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Chọn hoặc tạo một Story Episode để bắt đầu.
            </div>
          )}
        </main>
      </div>
      <SeriesPickerDialog
        open={seriesPickerOpen}
        onOpenChange={setSeriesPickerOpen}
        context="story_studio"
        series={seriesQuery.data ?? []}
        selectedSeriesId={effectiveSeriesId}
        loading={seriesQuery.isLoading || seriesQuery.isFetching}
        error={seriesQuery.error ? getErrorMessage(seriesQuery.error) : null}
        disabled={busy}
        onSelect={selectStorySeries}
        onCreateNew={() => {
          setSeriesPickerOpen(false);
          setSeriesCreateDialogOpen(true);
        }}
      />
      <SeriesCreateDialog
        open={seriesCreateDialogOpen}
        onOpenChange={setSeriesCreateDialogOpen}
        context="story_studio"
        defaultMode="image_story_only"
        saving={createSeries.isPending}
        error={createSeries.error ? getErrorMessage(createSeries.error) : null}
        nextActions={['select', 'manage_characters']}
        defaultNextAction="select"
        submitLabel="Tạo series"
        onSubmit={(draft, nextAction) => createSeries.mutate({ draft, nextAction })}
      />
      <PromptLibraryModal
        open={promptLibraryOpen}
        panels={promptLibraryPanels}
        allPromptText={promptLibraryText}
        copiedPromptKey={copiedPromptKey}
        onClose={() => setPromptLibraryOpen(false)}
        onCopy={(key, value) => void copyPromptText(key, value)}
      />
      </div>
    </div>
  );
}

function PromptLibraryModal({
  open,
  panels,
  allPromptText,
  copiedPromptKey,
  onClose,
  onCopy,
}: {
  open: boolean;
  panels: PanelPayload[];
  allPromptText: string;
  copiedPromptKey: string | null;
  onClose: () => void;
  onCopy: (key: string, value: string) => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    previouslyFocusedElementRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusFrame = window.requestAnimationFrame(() => dialogRef.current?.focus());

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;

      const focusableElements = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (!focusableElements.length) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;
      if (event.shiftKey && (activeElement === firstElement || !dialogRef.current.contains(activeElement))) {
        event.preventDefault();
        lastElement.focus();
      } else if (
        !event.shiftKey &&
        (activeElement === lastElement || !dialogRef.current.contains(activeElement))
      ) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener('keydown', handleKeyDown);
      if (previouslyFocusedElementRef.current?.isConnected) {
        previouslyFocusedElementRef.current.focus();
      }
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <button
        type="button"
        tabIndex={-1}
        aria-label="Đóng popup prompt"
        className="absolute inset-0 cursor-default bg-black/55 backdrop-blur-sm"
        onClick={onClose}
      />
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="relative z-10 flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-border bg-background shadow-2xl outline-none"
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 p-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-foreground">
              Toàn bộ prompt ảnh
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-muted-foreground">
              {panels.length} prompt · cuộn để đọc toàn bộ danh sách trước khi copy sang tool render.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!allPromptText.trim()}
              onClick={() => onCopy('all-prompts-modal', allPromptText)}
            >
              {copiedPromptKey === 'all-prompts-modal' ? (
                <Check className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
              Copy tất cả
            </Button>
            <Button size="sm" variant="outline" onClick={onClose} aria-label="Đóng popup prompt">
              <X className="h-4 w-4" />
              Đóng
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 [scrollbar-gutter:stable]">
          {panels.length ? (
            <div className="grid gap-4">
              {panels.map((panel) => {
                const block = panelPromptBlock(panel);
                const copyKey = `modal-panel-${panel.order}`;
                return (
                  <article
                    key={`prompt-modal-panel-${panel.order}`}
                    className="rounded-lg border border-border/70 bg-card/70 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">
                          Panel {String(panel.order).padStart(2, '0')}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Prompt {statusLabel(panel.prompt_status).toLowerCase()} · Ảnh{' '}
                          {statusLabel(panel.render_status).toLowerCase()}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!panel.prompt?.trim()}
                        onClick={() => onCopy(copyKey, block)}
                      >
                        {copiedPromptKey === copyKey ? (
                          <Check className="h-4 w-4" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                        Copy prompt
                      </Button>
                    </div>
                    <pre className="mt-3 whitespace-pre-wrap break-words rounded-lg border border-border/60 bg-muted/20 p-3 text-sm leading-6 text-foreground">
                      {block}
                    </pre>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              Chưa có prompt ảnh để hiển thị. Hãy bấm “Auto đến prompt ảnh” hoặc “Tạo panel/prompt”.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

type BrainTab = 'cards' | 'states' | 'traces' | 'canon';

function SeriesBrainPanel({
  seriesId,
  episodeId,
  disabled,
  onChanged,
  onNotice,
}: {
  seriesId: string;
  episodeId: string;
  disabled: boolean;
  onChanged: () => void;
  onNotice: (message: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<BrainTab>('cards');
  const [cardDraft, setCardDraft] = useState({
    card_type: 'canon_rule' as SeriesMemoryCardType,
    title: '',
    content: '',
  });

  const memoryCardsQuery = useQuery({
    queryKey: ['series-brain', seriesId, 'memory-cards'],
    queryFn: () => apiClient.listSeriesMemoryCards(seriesId),
    enabled: !!seriesId,
  });
  const currentStatesQuery = useQuery({
    queryKey: ['series-brain', seriesId, 'current-states'],
    queryFn: () => apiClient.listSeriesCurrentStates(seriesId),
    enabled: !!seriesId,
  });
  const tracesQuery = useQuery({
    queryKey: ['series-brain', seriesId, 'traces', episodeId],
    queryFn: () =>
      apiClient.listSeriesContextTraces(seriesId, {
        story_episode_id: episodeId,
        limit: 12,
      }),
    enabled: !!seriesId && !!episodeId,
  });
  const canonChecksQuery = useQuery({
    queryKey: ['series-brain', seriesId, 'canon-checks', episodeId],
    queryFn: () =>
      apiClient.listSeriesCanonChecks(seriesId, {
        story_episode_id: episodeId,
        limit: 12,
      }),
    enabled: !!seriesId && !!episodeId,
  });

  const refreshBrain = () => {
    queryClient.invalidateQueries({ queryKey: ['series-brain', seriesId] });
    onChanged();
  };

  const createCard = useMutation({
    mutationFn: () => {
      if (!cardDraft.title.trim()) throw new Error('Tên thẻ nhớ là bắt buộc.');
      if (!cardDraft.content.trim()) throw new Error('Nội dung thẻ nhớ là bắt buộc.');
      return apiClient.createSeriesMemoryCard(seriesId, {
        card_type: cardDraft.card_type,
        title: cardDraft.title.trim(),
        content: { text: cardDraft.content.trim() },
        status: 'draft',
      });
    },
    onSuccess: () => {
      setCardDraft((current) => ({ ...current, title: '', content: '' }));
      onNotice('Đã lưu thẻ nhớ nháp. Thẻ chưa thành canon cho tới khi được duyệt.');
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const suggestCards = useMutation({
    mutationFn: () =>
      apiClient.suggestSeriesMemoryCards(seriesId, {
        include_legacy_bible: true,
        include_latest_summary: true,
        save_drafts: true,
      }),
    onSuccess: (result) => {
      onNotice(result.message);
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const setCardStatus = useMutation({
    mutationFn: ({
      card,
      status,
    }: {
      card: SeriesMemoryCardResponse;
      status: 'approved' | 'rejected' | 'archived';
    }) => apiClient.setSeriesMemoryCardStatus(seriesId, card.id, { status }),
    onSuccess: () => {
      onNotice('Đã cập nhật trạng thái thẻ nhớ.');
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const proposeState = useMutation({
    mutationFn: () =>
      apiClient.proposeSeriesCurrentState(seriesId, {
        source_type: 'story_episode',
        source_id: episodeId,
        notes: 'Đề xuất trạng thái hiện tại từ Story Studio.',
      }),
    onSuccess: () => {
      onNotice(
        'Đã tạo bản đề xuất trạng thái. Trạng thái hiện tại chưa đổi cho tới khi được duyệt.',
      );
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const setStateStatus = useMutation({
    mutationFn: ({
      state,
      approval_status,
    }: {
      state: SeriesCurrentStateResponse;
      approval_status: 'approved' | 'rejected' | 'archived';
    }) => apiClient.setSeriesCurrentStateStatus(seriesId, state.id, { approval_status }),
    onSuccess: () => {
      onNotice('Đã cập nhật trạng thái phiên bản series.');
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const compileTrace = useMutation({
    mutationFn: () =>
      apiClient.compileSeriesContext(seriesId, {
        task_type: 'image_panel_prompt',
        story_episode_id: episodeId,
        target_ref_type: 'story_episode',
        target_ref_id: episodeId,
        current_payload: { source: 'story_studio' },
        persist_trace: true,
      }),
    onSuccess: () => {
      onNotice('Đã biên dịch thử ngữ cảnh và lưu trace an toàn.');
      refreshBrain();
    },
    onError: (error) => onNotice(getErrorMessage(error)),
  });

  const cards = memoryCardsQuery.data?.items ?? [];
  const approvedCards = cards.filter((card) => card.status === 'approved');
  const draftCards = cards.filter((card) => card.status !== 'approved');
  const states = currentStatesQuery.data?.items ?? [];
  const statesById = useMemo(() => new Map(states.map((state) => [state.id, state])), [states]);
  const latestApprovedState = states.find((state) => state.approval_status === 'approved') ?? null;
  const pendingStates = states.filter((state) => state.approval_status !== 'approved');
  const traces = tracesQuery.data?.items ?? [];
  const canonChecks = canonChecksQuery.data ?? [];
  const mutationBusy =
    createCard.isPending ||
    suggestCards.isPending ||
    setCardStatus.isPending ||
    proposeState.isPending ||
    setStateStatus.isPending ||
    compileTrace.isPending;

  return (
    <section className="rounded-lg border border-border/70 bg-background/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <SectionTitle icon={Brain} title="Bộ não chuỗi" />
          <p className="mt-2 text-sm text-muted-foreground">
            {approvedCards.length} thẻ đã duyệt · {draftCards.length} thẻ chờ ·{' '}
            {latestApprovedState
              ? `trạng thái v${latestApprovedState.revision}`
              : 'chưa có trạng thái duyệt'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || mutationBusy || !seriesId}
            onClick={() => suggestCards.mutate()}
          >
            {suggestCards.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Database className="h-4 w-4" />
            )}
            Gợi ý thẻ
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || mutationBusy || !episodeId}
            onClick={() => proposeState.mutate()}
          >
            {proposeState.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ListChecks className="h-4 w-4" />
            )}
            Đề xuất trạng thái
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || mutationBusy || !episodeId}
            onClick={() => compileTrace.mutate()}
          >
            {compileTrace.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            Lưu vết thử
          </Button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {(
          [
            ['cards', 'Thẻ nhớ'],
            ['states', 'Trạng thái'],
            ['traces', 'Vết kiểm tra'],
            ['canon', 'Kiểm tra mạch gốc'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key)}
            className={cn(
              'h-8 rounded-lg border px-3 text-xs font-medium transition-colors',
              activeTab === key
                ? 'border-primary/40 bg-primary/10 text-foreground'
                : 'border-border bg-background text-muted-foreground hover:bg-muted/40',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'cards' ? (
        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="grid max-h-80 gap-2 overflow-auto pr-1">
            {memoryCardsQuery.isLoading ? <SkeletonText /> : null}
            {cards.map((card) => (
              <div
                key={card.id}
                className="rounded-lg border border-border/60 bg-muted/20 p-3 text-xs"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-foreground">{card.title}</p>
                    <p className="mt-1 text-muted-foreground">
                      {memoryTypeLabel(card.card_type)} · {statusLabel(card.status).toLowerCase()} ·
                      v{card.revision} · {Math.round(card.importance * 100)}%
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {card.status !== 'approved' ? (
                      <Button
                        size="sm"
                        className="h-7 px-2"
                        disabled={disabled || mutationBusy}
                        onClick={() => setCardStatus.mutate({ card, status: 'approved' })}
                      >
                        <Check className="h-3.5 w-3.5" />
                        Duyệt
                      </Button>
                    ) : null}
                    {card.status !== 'rejected' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2"
                        disabled={disabled || mutationBusy}
                        onClick={() => setCardStatus.mutate({ card, status: 'rejected' })}
                      >
                        <X className="h-3.5 w-3.5" />
                        Từ chối
                      </Button>
                    ) : null}
                    {card.status !== 'archived' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2"
                        disabled={disabled || mutationBusy}
                        onClick={() => setCardStatus.mutate({ card, status: 'archived' })}
                      >
                        Lưu trữ
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
                  {briefJson(card.content)}
                </p>
              </div>
            ))}
            {!memoryCardsQuery.isLoading && !cards.length ? (
              <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
                Chưa có thẻ nhớ. Có thể tạo nháp từ sổ tay chuỗi hoặc nhập thủ công.
              </p>
            ) : null}
          </div>

          <div className="rounded-lg border border-border/60 bg-background/80 p-3">
            <p className="text-sm font-semibold">Thêm thẻ nháp</p>
            <div className="mt-3 grid gap-2">
              <select
                value={cardDraft.card_type}
                onChange={(event) =>
                  setCardDraft((current) => ({
                    ...current,
                    card_type: event.target.value as SeriesMemoryCardType,
                  }))
                }
                className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
              >
                {(
                  [
                    'canon_rule',
                    'series_identity',
                    'relationship',
                    'location',
                    'prop',
                    'story_thread',
                    'visual_style',
                    'episode_summary',
                    'arc_summary',
                    'series_summary',
                    'reviewed_note',
                  ] as SeriesMemoryCardType[]
                ).map((type) => (
                  <option key={type} value={type}>
                    {memoryTypeLabel(type)}
                  </option>
                ))}
              </select>
              <input
                value={cardDraft.title}
                onChange={(event) =>
                  setCardDraft((current) => ({ ...current, title: event.target.value }))
                }
                className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                placeholder="Tên thẻ"
              />
              <textarea
                value={cardDraft.content}
                onChange={(event) =>
                  setCardDraft((current) => ({ ...current, content: event.target.value }))
                }
                className="min-h-24 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-foreground/40"
                placeholder="Nội dung đã đọc được, quy tắc canon, địa điểm, đạo cụ hoặc mạch truyện"
              />
              <Button
                size="sm"
                disabled={
                  disabled || mutationBusy || !cardDraft.title.trim() || !cardDraft.content.trim()
                }
                onClick={() => createCard.mutate()}
              >
                {createCard.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Lưu nháp
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === 'states' ? (
        <div className="mt-4 grid gap-2">
          {currentStatesQuery.isLoading ? <SkeletonText /> : null}
          {latestApprovedState ? (
            <StateRow
              state={latestApprovedState}
              label="Đang dùng"
              previousState={
                latestApprovedState.previous_state_id
                  ? statesById.get(latestApprovedState.previous_state_id)
                  : null
              }
              disabled={disabled || mutationBusy}
              onSetStatus={(approval_status) =>
                setStateStatus.mutate({ state: latestApprovedState, approval_status })
              }
            />
          ) : (
            <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
              Chưa có trạng thái hiện tại đã duyệt. Bộ chọn vẫn dùng thẻ nhớ, hồ sơ nhân vật và
              Bible cũ.
            </p>
          )}
          {pendingStates.map((state) => (
            <StateRow
              key={state.id}
              state={state}
              label="Chờ quyết định"
              previousState={
                state.previous_state_id
                  ? statesById.get(state.previous_state_id)
                  : latestApprovedState
              }
              disabled={disabled || mutationBusy}
              onSetStatus={(approval_status) => setStateStatus.mutate({ state, approval_status })}
            />
          ))}
        </div>
      ) : null}

      {activeTab === 'traces' ? (
        <div className="mt-4 grid gap-2">
          {tracesQuery.isLoading ? <SkeletonText /> : null}
          {traces.map((trace) => (
            <div
              key={trace.id}
              className="rounded-lg border border-border/60 bg-muted/20 p-3 text-xs"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-foreground">{trace.task_type}</p>
                  <p className="mt-1 text-muted-foreground">
                    {trace.selected_cards.length} thẻ · {trace.selected_character_profiles.length}{' '}
                    hồ sơ · {trace.truncated_groups.length} nhóm rút gọn
                  </p>
                </div>
                <span className="rounded-full border border-border bg-background px-2 py-0.5 text-muted-foreground">
                  {new Date(trace.created_at).toLocaleString()}
                </span>
              </div>
              <div className="mt-2 grid gap-1 sm:grid-cols-2">
                {trace.group_budget.map((group, index) => (
                  <p
                    key={`${trace.id}-${recordText(group, 'group') || index}`}
                    className="rounded-lg bg-background/80 px-2 py-1 text-muted-foreground"
                  >
                    {recordText(group, 'title') || recordText(group, 'group')}:{' '}
                    {recordText(group, 'used_chars') || 0} ký tự
                    {group.truncated ? ' · rút gọn' : ''}
                  </p>
                ))}
              </div>
              {trace.selected_cards.length ? (
                <p className="mt-2 text-muted-foreground">
                  Thẻ đã dùng:{' '}
                  {trace.selected_cards
                    .map((card) => recordText(card, 'title') || recordText(card, 'id'))
                    .join(', ')}
                </p>
              ) : null}
            </div>
          ))}
          {!tracesQuery.isLoading && !traces.length ? (
            <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
              Chưa có vết kiểm tra cho tập này. Tạo bản nháp, khung/câu lệnh hoặc bấm “Lưu vết thử”.
            </p>
          ) : null}
        </div>
      ) : null}

      {activeTab === 'canon' ? (
        <div className="mt-4 grid gap-2">
          {canonChecksQuery.isLoading ? <SkeletonText /> : null}
          {canonChecks.map((check) => (
            <CanonCheckRow
              key={check.id ?? `${check.prompt_kind}-${check.created_at}`}
              check={check}
            />
          ))}
          {!canonChecksQuery.isLoading && !canonChecks.length ? (
            <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
              Chưa có canon check cho tập này. Prompt ảnh/video sẽ tự ghi kết quả khi được tạo hoặc
              duyệt.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function StateRow({
  state,
  label,
  previousState,
  disabled,
  onSetStatus,
}: {
  state: SeriesCurrentStateResponse;
  label: string;
  previousState?: SeriesCurrentStateResponse | null;
  disabled: boolean;
  onSetStatus: (status: 'approved' | 'rejected' | 'archived') => void;
}) {
  const diffRows = previousState ? stateDiffRows(state, previousState) : [];
  const changedRows = diffRows.filter((row) => row.changed);
  const rowsToShow = changedRows.length ? changedRows : diffRows.slice(0, 3);

  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-xs">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-foreground">
            {label} · v{state.revision} · sau tập {state.based_on_episode_number}
          </p>
          <p className="mt-1 text-muted-foreground">
            {statusLabel(state.approval_status)} · {state.open_threads.length} mạch mở ·{' '}
            {state.unresolved_conflicts.length} xung đột
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {state.approval_status !== 'approved' ? (
            <Button
              size="sm"
              className="h-7 px-2"
              disabled={disabled}
              onClick={() => onSetStatus('approved')}
            >
              <Check className="h-3.5 w-3.5" />
              Duyệt
            </Button>
          ) : null}
          {state.approval_status !== 'rejected' ? (
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2"
              disabled={disabled}
              onClick={() => onSetStatus('rejected')}
            >
              <X className="h-3.5 w-3.5" />
              Từ chối
            </Button>
          ) : null}
        </div>
      </div>
      {state.open_threads.length ? (
        <div className="mt-2 grid gap-1">
          {state.open_threads.slice(0, 3).map((thread, index) => (
            <p
              key={`${state.id}-thread-${index}`}
              className="rounded-lg bg-background/80 px-2 py-1 text-muted-foreground"
            >
              {recordText(thread, 'title') || briefJson(thread)}
            </p>
          ))}
        </div>
      ) : null}
      {state.approval_status !== 'approved' && previousState ? (
        <div className="mt-3 border-t border-border/60 pt-3">
          <p className="font-medium text-foreground">
            So sánh trước khi duyệt · {changedRows.length || 'không có'} mục thay đổi
          </p>
          <div className="mt-2 grid gap-2">
            {rowsToShow.map((row) => (
              <div
                key={`${state.id}-${row.key}`}
                className="grid gap-1 sm:grid-cols-[120px_minmax(0,1fr)_minmax(0,1fr)]"
              >
                <p
                  className={cn(
                    'font-medium',
                    row.changed ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {row.label}
                </p>
                <p className="min-w-0 whitespace-pre-wrap break-words text-muted-foreground">
                  <span className="font-medium text-foreground/80">Cũ: </span>
                  {row.oldValue}
                </p>
                <p className="min-w-0 whitespace-pre-wrap break-words text-muted-foreground">
                  <span className="font-medium text-foreground/80">Mới: </span>
                  {row.newValue}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CanonCheckRow({ check }: { check: SeriesCanonCheckResponse }) {
  const blocking = check.blocking_conflicts ?? [];
  const warnings = check.warnings ?? [];
  return (
    <div
      className={cn(
        'rounded-lg border p-3 text-xs',
        check.passed
          ? 'border-emerald-500/25 bg-emerald-500/10'
          : 'border-destructive/30 bg-destructive/10',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-foreground">
            {check.passed ? 'Đạt mạch gốc' : 'Có lỗi mạch gốc'} · {check.prompt_kind}
          </p>
          <p className="mt-1 text-muted-foreground">
            {blocking.length} lỗi chặn · {warnings.length} cảnh báo ·{' '}
            {check.evidence_card_ids.length} nguồn
          </p>
        </div>
        {check.override_reason ? (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-800 dark:text-amber-100">
            Đã override
          </span>
        ) : null}
      </div>
      {[...blocking, ...warnings].slice(0, 3).map((item, index) => (
        <p
          key={`${check.id ?? check.prompt_kind}-${index}`}
          className="mt-2 rounded-lg bg-background/80 p-2 text-muted-foreground"
        >
          {recordText(item, 'message') || briefJson(item)}
        </p>
      ))}
      {check.override_reason ? (
        <p className="mt-2 rounded-lg bg-background/80 p-2 text-muted-foreground">
          Lý do override: {check.override_reason}
        </p>
      ) : null}
    </div>
  );
}

function MetricTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'default',
}: {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  detail: string;
  tone?: 'default' | 'good' | 'warn';
}) {
  return (
    <div
      className={cn(
        'rounded-lg border px-3 py-2.5',
        tone === 'good'
          ? 'border-emerald-500/25 bg-emerald-500/10'
          : tone === 'warn'
            ? 'border-amber-500/30 bg-amber-500/10'
            : 'border-border/70 bg-background/70',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
      <p className="mt-1 text-lg font-semibold leading-none text-foreground">{value}</p>
      <p className="mt-1 truncate text-[11px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function WorkflowStep({
  icon: Icon,
  label,
  detail,
  done,
  active,
}: {
  icon: LucideIcon;
  label: string;
  detail: string;
  done: boolean;
  active: boolean;
}) {
  return (
    <div
      className={cn(
        'grid min-h-16 grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-lg border px-3 py-3 transition',
        done
          ? 'border-emerald-500/25 bg-emerald-500/10'
          : active
            ? 'border-primary/35 bg-primary/10'
            : 'border-border/70 bg-background/55',
      )}
    >
      <span
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-lg border',
          done
            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200'
            : active
              ? 'border-primary/35 bg-background/80 text-foreground'
              : 'border-border bg-background text-muted-foreground',
        )}
      >
        {done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}

function StatusPill({
  children,
  tone = 'default',
}: {
  children: ReactNode;
  tone?: 'default' | 'good' | 'warn' | 'danger';
}) {
  return (
    <span
      className={cn(
        'inline-flex min-h-7 items-center rounded-full border px-2.5 py-1 font-medium',
        tone === 'good'
          ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200'
          : tone === 'warn'
            ? 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-100'
            : tone === 'danger'
              ? 'border-destructive/30 bg-destructive/10 text-destructive'
              : 'border-border bg-background text-muted-foreground',
      )}
    >
      {children}
    </span>
  );
}

function FieldLabel({
  label,
  hint,
  compact = false,
  children,
}: {
  label: string;
  hint?: string;
  compact?: boolean;
  children: ReactNode;
}) {
  const generatedId = useId();
  const controlId =
    isValidElement<{ id?: string }>(children) && children.props.id
      ? children.props.id
      : generatedId;
  const control = isValidElement<{ id?: string }>(children)
    ? cloneElement(children, { id: controlId })
    : children;

  return (
    <div className={cn('grid gap-1.5 text-xs font-medium text-foreground', compact && 'gap-1')}>
      <label htmlFor={controlId}>{label}</label>
      {control}
      {hint ? (
        <span className="text-[11px] font-normal leading-5 text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

function SectionTitle({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background">
        <Icon className="h-4 w-4" />
      </span>
      <p className="text-sm font-semibold">{title}</p>
    </div>
  );
}

function SkeletonText() {
  return (
    <div className="grid gap-2">
      <div className="h-12 animate-pulse rounded-lg bg-muted" />
      <div className="h-12 animate-pulse rounded-lg bg-muted/70" />
    </div>
  );
}
