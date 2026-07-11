import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  BookOpen,
  Bug,
  Check,
  Clapperboard,
  Copy,
  Cpu,
  Download,
  FileText,
  Film,
  Gauge,
  Loader2,
  Lock,
  type LucideIcon,
  MemoryStick,
  Mic2,
  MoreHorizontal,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Thermometer,
  Trash2,
  Unlock,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import type {
  CallToActionStyle,
  DialogueMode,
  DownloadedBlob,
  NarrationDensity,
  SystemResourcesResponse,
  VideoAutoRunMaterialTarget,
  VideoAutoRunMode,
  VideoAutoRunResponse,
  VideoAutoRunStatus,
  VideoAutoRunStep,
  VideoLanguage,
  VideoProjectDetailResponse,
  VideoProjectResponse,
  VideoPromptContentResponse,
  VideoPurpose,
  VideoSceneResponse,
  VideoSeriesResponse,
  VideoShotResponse,
  VideoSourceBlockResponse,
} from '@/lib/api/types';
import { getLanguageOptionsForEngine } from '@/lib/constants/languages';
import { useProfiles } from '@/lib/hooks/useProfiles';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';
import { AIVideoRenderPanel } from './AIVideoRenderPanel';
import { AIVideoVeoChromePanel } from './AIVideoVeoChromePanel';

type AspectRatio = '9:16' | '16:9' | '1:1';
type ProjectCreationMode = 'quick' | 'manual';

interface SourceDraft {
  block_type: string;
  label: string;
  helper: string;
  content: string;
}

interface DraftForm {
  title: string;
  targetLanguage: VideoLanguage;
  videoPurpose: VideoPurpose;
  dialogueMode: DialogueMode;
  narrationDensity: NarrationDensity;
  callToActionStyle: CallToActionStyle;
  promptSegmentCount: number;
  promptSegmentDuration: number;
  microScenesPerPrompt: number;
  aspectRatio: AspectRatio;
  visualStyle: string;
  voiceProfileId: string;
  sources: SourceDraft[];
}

interface SeriesDraft {
  title: string;
  character_bible: string;
  world_bible: string;
  style_bible: string;
  continuity_rules: string;
  negative_rules: string;
  previous_episode_summary: string;
}

interface EpisodeDraft {
  seriesId: string;
  episodeTitle: string;
  topic: string;
}

const SOURCE_TEMPLATES: SourceDraft[] = [
  {
    block_type: 'idea',
    label: 'Ý tưởng chính',
    helper: 'Nêu video muốn làm bằng tiếng Việt. Đây là nguồn bắt buộc.',
    content: '',
  },
  {
    block_type: 'rough_script',
    label: 'Kịch bản thô',
    helper: 'Dán kịch bản, đoạn thoại hoặc ghi chú dài nếu đã có.',
    content: '',
  },
  {
    block_type: 'character_notes',
    label: 'Nhân vật và bối cảnh',
    helper: 'Ghi chi tiết cần giữ nhất quán: nhân vật, trang phục, đạo cụ, địa điểm.',
    content: '',
  },
  {
    block_type: 'style_notes',
    label: 'Phong cách video',
    helper: 'Ví dụ: cinematic, documentary, fast cuts, warm light, realistic.',
    content: '',
  },
  {
    block_type: 'must_have',
    label: 'Bắt buộc phải có',
    helper: 'Các ý không được bỏ khi AI phát triển lại nội dung.',
    content: '',
  },
  {
    block_type: 'avoid',
    label: 'Cần tránh',
    helper: 'Những chi tiết, giọng văn hoặc hình ảnh không muốn xuất hiện.',
    content: '',
  },
];

const initialForm: DraftForm = {
  title: '',
  targetLanguage: 'en',
  videoPurpose: 'global_short',
  dialogueMode: 'voiceover',
  narrationDensity: 'dense',
  callToActionStyle: 'soft',
  promptSegmentCount: 6,
  promptSegmentDuration: 10,
  microScenesPerPrompt: 3,
  aspectRatio: '9:16',
  visualStyle:
    'cinematic realistic video, natural light, consistent character details, fast editorial pacing',
  voiceProfileId: '',
  sources: SOURCE_TEMPLATES,
};

interface VideoPurposeOption {
  value: VideoPurpose;
  label: string;
  description: string;
  recommendedTargetLanguage: VideoLanguage;
  dialogueMode: DialogueMode;
  narrationDensity: NarrationDensity;
  subtitle: string;
  tone: string;
  cta: CallToActionStyle;
}

const VIDEO_PURPOSE_OPTIONS: VideoPurposeOption[] = [
  {
    value: 'vietnam_market',
    label: 'Thị trường Việt Nam',
    description: 'Tối ưu cho audience Việt Nam, lời kể tự nhiên và dễ nghe.',
    recommendedTargetLanguage: 'vi',
    dialogueMode: 'voiceover',
    narrationDensity: 'balanced',
    subtitle: 'Phụ đề tiếng Việt khớp giọng đọc.',
    tone: 'Đời thường, rõ ý, tránh cảm giác dịch máy.',
    cta: 'soft',
  },
  {
    value: 'global_short',
    label: 'Short quốc tế / tiếng Anh',
    description: 'Tối ưu cho short quốc tế bằng tiếng Anh, hook nhanh.',
    recommendedTargetLanguage: 'en',
    dialogueMode: 'voiceover',
    narrationDensity: 'dense',
    subtitle: 'Phụ đề tiếng Anh khớp giọng đọc.',
    tone: 'Câu ngắn, quốc tế, dễ hiểu trong vài giây đầu.',
    cta: 'soft',
  },
  {
    value: 'educational_explainer',
    label: 'Giải thích / giáo dục',
    description: 'Ưu tiên thoại rõ nghĩa, đủ ngữ cảnh và nhịp dễ nghe.',
    recommendedTargetLanguage: 'vi',
    dialogueMode: 'voiceover',
    narrationDensity: 'dense',
    subtitle: 'Phụ đề giữ đủ ý giải thích.',
    tone: 'Mỗi ý một nhịp, có ví dụ cụ thể.',
    cta: 'none',
  },
  {
    value: 'sales_ad',
    label: 'Quảng cáo / bán hàng',
    description: 'Tập trung hook, lợi ích chính và CTA rõ.',
    recommendedTargetLanguage: 'vi',
    dialogueMode: 'voiceover',
    narrationDensity: 'light',
    subtitle: 'Phụ đề ngắn, dễ đọc, hỗ trợ CTA.',
    tone: 'Mở bằng vấn đề hoặc lời hứa, kết bằng hành động.',
    cta: 'direct',
  },
  {
    value: 'localized_variant',
    label: 'Bản theo ngôn ngữ khác',
    description: 'Tạo bản riêng cho audience hoặc ngôn ngữ mới từ cùng source.',
    recommendedTargetLanguage: 'en',
    dialogueMode: 'voiceover',
    narrationDensity: 'balanced',
    subtitle: 'Phụ đề theo ngôn ngữ bản dịch.',
    tone: 'Giữ ý tưởng gốc, viết lại idiom và ví dụ cho tự nhiên.',
    cta: 'soft',
  },
  {
    value: 'custom',
    label: 'Tùy chỉnh',
    description: 'Tự chọn ngôn ngữ, giọng, kiểu thoại và mật độ lời kể.',
    recommendedTargetLanguage: 'en',
    dialogueMode: 'voiceover',
    narrationDensity: 'balanced',
    subtitle: 'Phụ đề theo ngôn ngữ video.',
    tone: 'Bám source và visual style của người dùng.',
    cta: 'none',
  },
];

function purposeOption(value: VideoPurpose): VideoPurposeOption {
  return VIDEO_PURPOSE_OPTIONS.find((item) => item.value === value) ?? VIDEO_PURPOSE_OPTIONS[0];
}

function usesQwenVietnameseBypass(
  targetLanguage: VideoLanguage,
  profile?: { language?: string | null } | null,
): boolean {
  return targetLanguage === 'vi' && (profile?.language || '').toLowerCase() === 'vi';
}

function aiVideoVoiceRequestBase(
  profileId: string,
  targetLanguage: VideoLanguage,
  profile?: { language?: string | null } | null,
) {
  return usesQwenVietnameseBypass(targetLanguage, profile)
    ? {
        profile_id: profileId,
        language: targetLanguage,
        engine: 'qwen' as const,
        model_size: '1.7B' as const,
      }
    : { profile_id: profileId, language: targetLanguage };
}

const emptySeriesDraft: SeriesDraft = {
  title: '',
  character_bible: '',
  world_bible: '',
  style_bible: '',
  continuity_rules: '',
  negative_rules: '',
  previous_episode_summary: '',
};

const emptyEpisodeDraft: EpisodeDraft = {
  seriesId: '',
  episodeTitle: '',
  topic: '',
};

const DEFAULT_PROMPT_SEGMENT_SECONDS = 10;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

function isSceneBusy(scene: VideoSceneResponse): boolean {
  return ['generating', 'loading_model'].includes(scene.voice_status);
}

function isShotBusy(shot: VideoShotResponse): boolean {
  return ['generating', 'loading_model'].includes(shot.voice_status);
}

function statusTone(ok: boolean) {
  return ok
    ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200';
}

const SKELETON_ROW_KEYS = ['first', 'second', 'third', 'fourth', 'fifth'];

function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {SKELETON_ROW_KEYS.slice(0, count).map((key) => (
        <div key={key} className="rounded-lg border border-border/70 p-4">
          <div className="h-4 w-32 animate-pulse rounded bg-muted" />
          <div className="mt-4 h-3 w-full animate-pulse rounded bg-muted" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

function FieldBlock({
  label,
  help,
  children,
  error,
}: {
  label: string;
  help?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <>
      {/* biome-ignore lint/a11y/noLabelWithoutControl: FieldBlock wraps its input/select/textarea through children. */}
      <label className="grid min-w-0 gap-2 [&_input]:w-full [&_select]:w-full [&_textarea]:w-full">
        <span className="text-sm font-medium text-foreground">{label}</span>
        {children}
        {error ? <span className="text-xs leading-relaxed text-destructive">{error}</span> : null}
        {help && !error ? (
          <span className="text-xs leading-relaxed text-muted-foreground">{help}</span>
        ) : null}
      </label>
    </>
  );
}

function StepHeader({
  icon: Icon,
  title,
  meta,
}: {
  icon: LucideIcon;
  title: string;
  meta?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold tracking-tight">{title}</h2>
          {meta && <p className="truncate text-xs text-muted-foreground">{meta}</p>}
        </div>
      </div>
    </div>
  );
}

function TextPanel({
  title,
  value,
  empty,
  description,
}: {
  title: string;
  value?: string | null;
  empty: string;
  description?: string;
}) {
  return (
    <div className="rounded-lg border border-border/75 bg-background/70 p-4">
      <p className="text-sm font-semibold">{title}</p>
      {description ? (
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
      ) : null}
      <div className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-sm leading-relaxed text-foreground/85">
        {value?.trim() ? value : <span className="text-muted-foreground">{empty}</span>}
      </div>
    </div>
  );
}

function shotLabel(shot: VideoShotResponse): string {
  return `Segment ${String(shot.shot_order).padStart(2, '0')}`;
}

function shotMicroScenes(shot: VideoShotResponse): NonNullable<VideoShotResponse['micro_scenes']> {
  return Array.isArray(shot.micro_scenes) ? shot.micro_scenes : [];
}

function formatSeconds(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

function projectPromptDuration(project: VideoProjectDetailResponse | null | undefined): number {
  return project?.prompt_segment_duration_seconds || DEFAULT_PROMPT_SEGMENT_SECONDS;
}

function projectPromptCount(
  project: VideoProjectDetailResponse | null | undefined,
  storedShotCount = 0,
): number | null {
  if (!project) return null;
  if (project.prompt_segment_count) return project.prompt_segment_count;
  if (project.target_duration_seconds && project.target_duration_seconds > 0) {
    return Math.max(1, Math.ceil(project.target_duration_seconds / projectPromptDuration(project)));
  }
  return storedShotCount > 0 ? storedShotCount : null;
}

function normalizeAspectRatio(value: string | null | undefined): AspectRatio {
  return value === '16:9' || value === '1:1' ? value : '9:16';
}

function segmentTimelineLabel(
  project: VideoProjectDetailResponse | null | undefined,
  shotOrder: number,
): string | null {
  const targetDurationSeconds = project?.target_duration_seconds;
  if (!targetDurationSeconds || targetDurationSeconds <= 0) {
    return null;
  }
  const promptDuration = projectPromptDuration(project);
  const start = Math.max(0, shotOrder - 1) * promptDuration;
  const end = Math.min(targetDurationSeconds, start + promptDuration);
  return `${formatSeconds(start)}-${formatSeconds(end)}s timeline`;
}

function videoLanguageLabel(language: VideoLanguage | null | undefined): string {
  return language === 'vi' ? 'tiếng Việt' : 'tiếng Anh';
}

function dialogueModeLabel(mode: DialogueMode | null | undefined): string {
  if (mode === 'character_lines') return 'nhân vật nói';
  if (mode === 'mixed') return 'kết hợp';
  return 'thuyết minh';
}

function narrationDensityLabel(density: NarrationDensity | null | undefined): string {
  if (density === 'light') return 'ít thoại';
  if (density === 'dense') return 'dày thoại';
  return 'vừa phải';
}

function callToActionStyleLabel(style: CallToActionStyle | null | undefined): string {
  if (style === 'soft') return 'nhẹ nhàng';
  if (style === 'direct') return 'trực tiếp';
  if (style === 'urgent') return 'khẩn cấp';
  return 'không';
}

function voiceProfileLanguageLabel(language: string | null | undefined): string {
  if (language === 'vi' || language === 'en') return videoLanguageLabel(language);
  return language || 'không rõ';
}

function episodeDisplay(
  project: Pick<VideoProjectResponse, 'episode_number' | 'episode_title' | 'title'>,
): string {
  if (!project.episode_number && !project.episode_title) return project.title;
  const number = project.episode_number
    ? `Tập ${String(project.episode_number).padStart(2, '0')}`
    : 'Tập';
  return project.episode_title ? `${number} · ${project.episode_title}` : number;
}

function groupProjectsBySeries(
  projects: VideoProjectResponse[] | undefined,
  seriesList: VideoSeriesResponse[] | undefined,
) {
  const seriesById = new Map((seriesList ?? []).map((series) => [series.id, series]));
  const seriesGroups = new Map<
    string,
    { series: VideoSeriesResponse | null; projects: VideoProjectResponse[] }
  >();
  const standalone: VideoProjectResponse[] = [];
  for (const project of projects ?? []) {
    if (!project.series_id) {
      standalone.push(project);
      continue;
    }
    const group = seriesGroups.get(project.series_id) ?? {
      series: seriesById.get(project.series_id) ?? null,
      projects: [],
    };
    group.projects.push(project);
    seriesGroups.set(project.series_id, group);
  }
  return { seriesGroups: Array.from(seriesGroups.values()), standalone };
}

function missingPromptExplanationText(): string {
  return 'Chưa có bản giải thích tiếng Việt riêng. Hãy tạo lại prompt video nếu cần bản giải thích đầy đủ.';
}

function metadataText(
  data: Record<string, unknown> | null | undefined,
  keys: string[],
  fallback = 'chưa có',
): string {
  if (!data) return fallback;
  for (const key of keys) {
    const value = data[key];
    if (typeof value === 'string' && value.trim()) return value;
    if (Array.isArray(value) && value.length)
      return value
        .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
        .join('; ');
  }
  return fallback;
}

function qualityWarnings(data: Record<string, unknown> | null | undefined): string[] {
  const warnings = data?.warnings;
  const missing = data?.missing_fields;
  return [
    ...(Array.isArray(missing) ? missing.map(String) : []),
    ...(Array.isArray(warnings) ? warnings.map(String) : []),
  ];
}

const AUTO_RUN_STEPS: Array<{ step: VideoAutoRunStep; label: string }> = [
  { step: 'validate', label: 'Kiểm tra đầu vào' },
  { step: 'develop_story', label: 'Phát triển kịch bản' },
  { step: 'waiting_planning', label: 'Chờ Codex' },
  { step: 'review_story', label: 'Duyệt kịch bản' },
  { step: 'generate_shots', label: 'Segment' },
  { step: 'generate_prompts', label: 'Prompt video' },
  { step: 'review_prompts', label: 'Duyệt prompt' },
  { step: 'generate_clips', label: 'Tạo clip Veo' },
  { step: 'waiting_clips', label: 'Chờ clip Veo' },
  { step: 'generate_voice', label: 'Tạo giọng' },
  { step: 'waiting_voice', label: 'Chờ giọng' },
  { step: 'generate_subtitle', label: 'Tạo SRT' },
  { step: 'generate_render', label: 'Render MP4' },
  { step: 'waiting_render', label: 'Chờ MP4' },
  { step: 'completed', label: 'Hoàn tất' },
];
const PROMPTS_ONLY_SKIPPED_STEPS = new Set<VideoAutoRunStep>([
  'generate_clips',
  'waiting_clips',
  'generate_voice',
  'waiting_voice',
  'generate_subtitle',
  'generate_render',
  'waiting_render',
]);
const VIDEO_CLIPS_SKIPPED_STEPS = new Set<VideoAutoRunStep>();
const FULL_MATERIALS_SKIPPED_STEPS = new Set<VideoAutoRunStep>([
  'generate_clips',
  'waiting_clips',
  'generate_render',
  'waiting_render',
]);

function autoRunStepsForTarget(target: VideoAutoRunMaterialTarget): Array<{
  step: VideoAutoRunStep;
  label: string;
}> {
  if (target === 'prompts_only') {
    return AUTO_RUN_STEPS.filter((item) => !PROMPTS_ONLY_SKIPPED_STEPS.has(item.step));
  }
  if (target === 'video_clips') {
    return AUTO_RUN_STEPS.filter((item) => !VIDEO_CLIPS_SKIPPED_STEPS.has(item.step));
  }
  return AUTO_RUN_STEPS.filter((item) => !FULL_MATERIALS_SKIPPED_STEPS.has(item.step));
}

function isAutoRunActiveStatus(status: VideoAutoRunStatus | string | null | undefined): boolean {
  return (
    !!status &&
    [
      'queued',
      'running',
      'waiting_planning',
      'waiting_voice',
      'waiting_clips',
      'waiting_render',
      'needs_review',
      'needs_input',
    ].includes(status)
  );
}

function isAutoRunBusyStatus(status: VideoAutoRunStatus | string | null | undefined): boolean {
  return !!status && ['queued', 'running', 'waiting_planning', 'waiting_voice', 'waiting_clips', 'waiting_render'].includes(status);
}

function isAutoRunActive(run: VideoAutoRunResponse | null | undefined): boolean {
  return isAutoRunActiveStatus(run?.status);
}

function isAutoRunBusy(run: VideoAutoRunResponse | null | undefined): boolean {
  return isAutoRunBusyStatus(run?.status);
}

function autoRunStatusText(status: VideoAutoRunStatus | string | null | undefined): string {
  switch (status) {
    case 'queued':
      return 'Đang chờ chạy';
    case 'running':
      return 'Đang chạy';
    case 'waiting_planning':
      return 'Đang chờ Codex';
    case 'waiting_voice':
      return 'Đang chờ giọng';
    case 'waiting_clips':
      return 'Đang chờ clip';
    case 'waiting_render':
      return 'Đang chờ MP4';
    case 'needs_review':
      return 'Cần duyệt';
    case 'needs_input':
      return 'Cần bổ sung';
    case 'completed':
      return 'Đã xong';
    case 'failed':
      return 'Lỗi';
    case 'cancelled':
      return 'Đã hủy';
    default:
      return status ?? 'Chưa chạy';
  }
}

function autoRunStatusLabel(run: VideoAutoRunResponse): string {
  return autoRunStatusText(run.status);
}

function autoRunReviewLabel(stage: VideoAutoRunResponse['review_stage']): string {
  if (stage === 'story') return 'chiến lược, tính nhất quán và kịch bản';
  if (stage === 'prompts') return 'prompt video';
  return 'nội dung';
}

function autoRunStepLabel(step: string | null | undefined): string {
  return AUTO_RUN_STEPS.find((item) => item.step === step)?.label ?? step ?? 'Chưa chạy';
}

function subtitleStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'completed':
      return 'Đã có phụ đề';
    case 'stale':
      return 'Cần tạo lại phụ đề';
    case 'failed':
      return 'Phụ đề bị lỗi';
    case 'missing':
    case undefined:
    case null:
      return 'Chưa có phụ đề';
    default:
      return status;
  }
}

function formatAutoRunCount(done: number, total: number): string {
  if (total <= 0) return 'Chưa có dữ liệu';
  return `${done}/${total}`;
}

function autoRunProgressPercent(run: VideoAutoRunResponse): number {
  return Math.min(100, Math.max(0, Math.round((run.progress || 0) * 100)));
}

function autoRunPlainSummary(run: VideoAutoRunResponse): {
  title: string;
  detail: string;
  next: string;
} {
  const promptCount = formatAutoRunCount(
    run.summary.prompt_completed_count,
    run.summary.prompt_required_count,
  );
  const voiceCount = formatAutoRunCount(
    run.summary.voice_completed_count,
    run.summary.voice_required_count,
  );
  const clipCount = formatAutoRunCount(
    run.summary.clip_completed_count,
    run.summary.clip_required_count,
  );
  const promptsOnly = run.material_target === 'prompts_only';
  const videoClips = run.material_target === 'video_clips';
  if (run.status === 'needs_review') {
    const reviewTarget =
      run.review_stage === 'story'
        ? 'kịch bản và hướng kể chuyện'
        : run.review_stage === 'prompts'
          ? promptsOnly
            ? 'prompt video trước khi upload ảnh'
            : videoClips
              ? 'prompt video trước khi gửi sang Veo'
            : 'prompt video trước khi tạo giọng'
          : 'nội dung vừa tạo';
    return {
      title: `Cần bạn duyệt ${reviewTarget}`,
      detail: 'Hệ thống đã dừng lại để bạn kiểm tra nội dung trước khi đi tiếp.',
      next: 'Xem nội dung bên dưới, chỉnh nếu cần, rồi bấm tiếp tục sau khi duyệt.',
    };
  }
  if (run.status === 'needs_input') {
    return {
      title: 'Cần bổ sung thông tin',
      detail: run.failure_reason || 'Auto-run thiếu dữ liệu cần thiết để chạy tiếp.',
      next: 'Sửa phần được nhắc trong thông báo, sau đó bấm Retry.',
    };
  }
  if (run.status === 'failed') {
    return {
      title: 'Auto-run đang dừng vì lỗi',
      detail: run.failure_reason || 'Một bước tạo nguyên liệu chưa hoàn tất.',
      next: 'Kiểm tra lỗi, sửa cấu hình hoặc nội dung liên quan, rồi bấm Retry.',
    };
  }
  if (run.status === 'completed') {
    if (promptsOnly) {
      return {
        title: 'Prompt video đã sẵn sàng',
        detail: `Prompt ${promptCount}. Voice và phụ đề được bỏ qua theo lựa chọn của bạn.`,
        next: 'Bạn có thể upload ảnh hoặc copy prompt sang Gemini để AI tự tạo thoại từ nội dung prompt.',
      };
    }
    if (videoClips) {
      return {
        title: 'MP4 đã render xong',
        detail: `Prompt ${promptCount}, clip đã import ${clipCount}, render ${run.summary.render_job_status || 'completed'}.`,
        next: 'Bạn có thể tải MP4 ở panel render hoặc kiểm tra clip trong panel Veo.',
      };
    }
    return {
      title: 'Nguyên liệu lõi đã sẵn sàng',
      detail: `Prompt ${promptCount}, voice ${voiceCount}, ${subtitleStatusLabel(run.summary.subtitle_status).toLowerCase()}.`,
      next: 'Bạn có thể kiểm tra prompt, nghe voice, tải phụ đề hoặc qua panel render MP4.',
    };
  }
  if (run.status === 'cancelled') {
    return {
      title: 'Auto-run đã được hủy',
      detail: 'Các nguyên liệu đã tạo trước đó vẫn nằm trong project.',
      next: 'Bạn có thể chạy lại auto-run hoặc tiếp tục làm thủ công từng phần.',
    };
  }
  switch (run.current_step) {
    case 'validate':
      return {
        title: 'Đang kiểm tra dữ liệu đầu vào',
        detail: 'Hệ thống kiểm tra project, nguồn nội dung, cấu hình segment và công cụ AI.',
        next: 'Nếu thiếu thông tin bắt buộc, hệ thống sẽ dừng và chỉ rõ cần bổ sung gì.',
      };
    case 'develop_story':
      return {
        title: 'Đang viết chiến lược và kịch bản',
        detail: 'AI đang biến yêu cầu đầu vào thành story, continuity và kịch bản chi tiết.',
        next: 'Sau bước này hệ thống sẽ dừng để duyệt hoặc tự đi tiếp theo chế độ bạn chọn.',
      };
    case 'waiting_planning':
      return {
        title: 'Đang chờ lượt dùng AI planning',
        detail: 'Project đang xếp hàng để tránh chạy nhiều tác vụ AI nặng cùng lúc.',
        next: 'Khi có slot trống, hệ thống sẽ tự tiếp tục bước đang chờ.',
      };
    case 'generate_shots':
      return {
        title: 'Đang chia video thành các segment',
        detail: 'AI đang tạo từng đoạn hình ảnh, nhịp dựng, mô tả tiếng Việt và narration.',
        next: 'Sau đó hệ thống sẽ tạo prompt video tương ứng cho từng segment.',
      };
    case 'generate_prompts':
      return {
        title: 'Đang tạo prompt video',
        detail:
          run.summary.prompt_required_count > 0
            ? `Đã có ${promptCount} prompt đạt yêu cầu trong project.`
            : 'AI đang chuẩn bị prompt video cho các segment vừa tạo.',
        next: promptsOnly
          ? 'Khi prompt sẵn sàng, bạn có thể upload ảnh hoặc để Gemini tạo thoại từ prompt.'
          : videoClips
            ? 'Khi prompt sẵn sàng, hệ thống sẽ gửi sang Veo, tải clip, tạo voice/SRT rồi render MP4.'
          : 'Khi prompt sẵn sàng, bạn có thể duyệt trước khi hệ thống tạo voice.',
      };
    case 'review_story':
      return {
        title: 'Đang chờ duyệt kịch bản',
        detail: 'Kịch bản đã có, nhưng hệ thống chưa tạo các nguyên liệu tốn thời gian.',
        next: 'Kiểm tra story và bấm tiếp tục nếu đúng ý.',
      };
    case 'review_prompts':
      return {
        title: 'Đang chờ duyệt prompt video',
        detail: promptsOnly
          ? `Prompt hiện tại: ${promptCount}. Voice và phụ đề sẽ không chạy trong auto-run này.`
          : videoClips
            ? `Prompt hiện tại: ${promptCount}. Veo chưa chạy cho đến khi bạn duyệt.`
          : `Prompt hiện tại: ${promptCount}. Voice chưa chạy cho đến khi bạn duyệt.`,
        next: promptsOnly
          ? 'Kiểm tra prompt từng segment, chỉnh nếu cần, rồi bấm tiếp tục để mở bước upload ảnh.'
          : videoClips
            ? 'Kiểm tra prompt từng segment, chỉnh nếu cần, rồi bấm tiếp tục để chạy Veo và render MP4.'
          : 'Kiểm tra prompt từng segment, chỉnh nếu cần, rồi bấm tiếp tục.',
      };
    case 'generate_clips':
      return {
        title: 'Đang gửi prompt sang Veo',
        detail: `Clip đã import ${clipCount}. Hệ thống sẽ tự dùng phiên Chrome/Veo mặc định.`,
        next: 'Nếu Veo yêu cầu đăng nhập hoặc credit thủ công, auto-run sẽ dừng và báo rõ bước cần xử lý.',
      };
    case 'waiting_clips':
      return {
        title: 'Đang chờ Veo tạo và tải clip',
        detail: `Clip đã import ${clipCount}. File tải về sẽ được map vào đúng segment trong project.`,
        next: 'Panel sẽ tự cập nhật khi từng clip được tải về và import.',
      };
    case 'generate_voice':
      return {
        title: 'Đang tạo giọng đọc cho các segment',
        detail: `Voice đã xong ${voiceCount}. Hệ thống chỉ tạo cho segment còn thiếu hoặc cần tạo lại.`,
        next: 'Khi mọi voice bắt buộc hoàn tất, hệ thống sẽ tạo phụ đề .srt.',
      };
    case 'waiting_voice':
      return {
        title: 'Đang chờ voice hoàn tất',
        detail: `Voice đã xong ${voiceCount}. Tác vụ giọng đọc có thể cần thêm thời gian.`,
        next: 'Panel sẽ tự cập nhật; bạn không cần bấm lại Auto chạy.',
      };
    case 'generate_subtitle':
      return {
        title: 'Đang tạo phụ đề .srt',
        detail: `Prompt ${promptCount}, voice ${voiceCount}; hệ thống đang ghép phụ đề theo audio.`,
        next: videoClips ? 'Sau bước này hệ thống sẽ tự render MP4.' : 'Sau bước này nguyên liệu lõi sẽ sẵn sàng.',
      };
    case 'generate_render':
      return {
        title: 'Đang tạo job render MP4',
        detail: `Clip ${clipCount}, voice ${voiceCount}, phụ đề ${subtitleStatusLabel(run.summary.subtitle_status).toLowerCase()}.`,
        next: 'Hệ thống sẽ tự dựng file MP4 cuối cùng.',
      };
    case 'waiting_render':
      return {
        title: 'Đang render MP4',
        detail: run.summary.render_job_status ? `Render job: ${run.summary.render_job_status}.` : 'FFmpeg đang dựng video cuối cùng.',
        next: 'Panel sẽ tự cập nhật khi file MP4 hoàn tất.',
      };
    default:
      return {
        title: autoRunStepLabel(run.current_step),
        detail: `Tiến độ tổng ${autoRunProgressPercent(run)}%.`,
        next: 'Hệ thống sẽ tự cập nhật khi bước hiện tại đổi trạng thái.',
      };
  }
}

function autoRunMilestoneStatus(
  run: VideoAutoRunResponse,
  step: VideoAutoRunStep,
): 'done' | 'current' | 'blocked' | 'pending' {
  if (run.completed_steps.includes(step)) return 'done';
  if (run.current_step === 'waiting_voice' && step === 'generate_voice') return 'current';
  if (run.current_step === 'waiting_clips' && step === 'generate_clips') return 'current';
  if (run.current_step === 'waiting_render' && step === 'generate_render') return 'current';
  if (run.current_step === step && ['failed', 'needs_input'].includes(run.status)) return 'blocked';
  if (run.current_step === step && !['completed', 'failed', 'cancelled'].includes(run.status))
    return 'current';
  return 'pending';
}

function AutoRunProgressPanel({
  run,
  isFetching,
  onCancel,
  cancelPending,
}: {
  run: VideoAutoRunResponse;
  isFetching: boolean;
  onCancel: () => void;
  cancelPending: boolean;
}) {
  const summary = autoRunPlainSummary(run);
  const percent = autoRunProgressPercent(run);
  const milestoneItems: Array<{
    step: VideoAutoRunStep;
    label: string;
    detail: string;
    metric?: string;
  }> = [
    {
      step: 'develop_story',
      label: 'Viết nền câu chuyện',
      detail: 'Ý tưởng, continuity và kịch bản chi tiết.',
    },
    {
      step: 'generate_shots',
      label: 'Chia thành segment',
      detail: 'Mỗi đoạn có hành động, camera, narration và nhịp dựng.',
      metric: run.summary.shot_count > 0 ? `${run.summary.shot_count} segment` : undefined,
    },
    {
      step: 'generate_prompts',
      label: 'Tạo prompt video',
      detail: 'Prompt gốc để copy sang công cụ tạo video.',
      metric: formatAutoRunCount(
        run.summary.prompt_completed_count,
        run.summary.prompt_required_count,
      ),
    },
    {
      step: 'generate_clips',
      label: 'Tạo clip Veo',
      detail: 'Gửi prompt, chờ tạo video, tải file và import vào đúng segment trước khi render.',
      metric: formatAutoRunCount(run.summary.clip_completed_count, run.summary.clip_required_count),
    },
    {
      step: 'generate_voice',
      label: 'Tạo giọng đọc',
      detail: 'Voice cho các segment có narration.',
      metric: formatAutoRunCount(
        run.summary.voice_completed_count,
        run.summary.voice_required_count,
      ),
    },
    {
      step: 'generate_subtitle',
      label: 'Tạo phụ đề',
      detail: 'File .srt theo voice đã tạo.',
      metric: subtitleStatusLabel(run.summary.subtitle_status),
    },
    {
      step: 'generate_render',
      label: 'Render MP4',
      detail: 'Dựng clip, voice và phụ đề thành file cuối.',
      metric: run.summary.render_job_status || undefined,
    },
  ];
  const allowedSteps = new Set(autoRunStepsForTarget(run.material_target).map((item) => item.step));
  const milestones = milestoneItems.filter((item) => allowedSteps.has(item.step));

  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-border/75 bg-background/75 shadow-[0_18px_38px_-28px_rgba(15,23,42,0.35)]">
      <div className="grid gap-4 border-b border-border/70 p-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium',
                run.status === 'completed'
                  ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : null,
                isAutoRunBusy(run)
                  ? 'border-sky-500/25 bg-sky-500/10 text-sky-700 dark:text-sky-300'
                  : null,
                ['needs_review', 'needs_input'].includes(run.status)
                  ? 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200'
                  : null,
                ['failed', 'cancelled'].includes(run.status)
                  ? 'border-destructive/25 bg-destructive/10 text-destructive'
                  : null,
              )}
            >
              {isFetching && isAutoRunActive(run) ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              {autoRunStatusLabel(run)}
            </span>
            <span className="inline-flex items-center rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-muted-foreground">
              {run.material_target === 'prompts_only'
                ? 'Chỉ prompt video'
                : run.material_target === 'video_clips'
                  ? 'Veo + MP4'
                  : 'Prompt + voice + SRT'}
            </span>
            <span className="rounded-full border border-border/70 bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground">
              {run.mode === 'review_gated' ? 'Duyệt từng chặng' : 'Tự chạy hết'}
            </span>
          </div>
          <p className="mt-3 text-lg font-semibold tracking-tight text-foreground">
            {summary.title}
          </p>
          <p className="mt-1 max-w-[72ch] text-sm leading-relaxed text-muted-foreground">
            {summary.detail}
          </p>
          <p className="mt-2 max-w-[72ch] text-sm leading-relaxed text-foreground/80">
            {summary.next}
          </p>
        </div>
        <div className="grid content-between gap-3 rounded-lg border border-border/70 bg-muted/20 p-3">
          <div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                Tiến độ
              </span>
              <span className="font-mono text-lg font-semibold tabular-nums">{percent}%</span>
            </div>
            <div
              className="mt-3 h-2 overflow-hidden rounded-full bg-background"
              role="progressbar"
              aria-label="Tiến độ auto-run"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
            >
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-700 [transition-timing-function:cubic-bezier(0.16,1,0.3,1)]',
                  run.status === 'failed' ? 'bg-destructive' : 'bg-foreground',
                  isAutoRunBusy(run) ? 'animate-pulse' : null,
                )}
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
          {isAutoRunBusy(run) ? (
            <Button
              size="sm"
              variant="outline"
              disabled={cancelPending}
              onClick={onCancel}
              className="w-full active:translate-y-[1px]"
            >
              {cancelPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" />
              )}
              Hủy
            </Button>
          ) : null}
        </div>
      </div>
      <div className="grid gap-0 divide-y divide-border/70 md:grid-cols-5 md:divide-x md:divide-y-0">
        {milestones.map((item) => {
          const status = autoRunMilestoneStatus(run, item.step);
          return (
            <div
              key={item.step}
              className={cn(
                'min-h-32 p-4 transition-colors',
                status === 'current' ? 'bg-sky-500/[0.08]' : null,
                status === 'blocked' ? 'bg-destructive/[0.08]' : null,
                status === 'done' ? 'bg-emerald-500/[0.08]' : null,
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border',
                    status === 'done'
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                      : null,
                    status === 'current'
                      ? 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300'
                      : null,
                    status === 'blocked'
                      ? 'border-destructive/30 bg-destructive/10 text-destructive'
                      : null,
                    status === 'pending'
                      ? 'border-border bg-background text-muted-foreground'
                      : null,
                  )}
                >
                  {status === 'done' ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : status === 'current' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : status === 'blocked' ? (
                    <AlertCircle className="h-3.5 w-3.5" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
                  )}
                </span>
                {item.metric ? (
                  <span className="max-w-24 truncate rounded-full border border-border/70 bg-background px-2 py-0.5 text-right font-mono text-[11px] text-muted-foreground">
                    {item.metric}
                  </span>
                ) : null}
              </div>
              <p className="mt-3 text-sm font-semibold leading-snug text-foreground">
                {item.label}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.detail}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CreativeDirectionSummary({ project }: { project: VideoProjectDetailResponse }) {
  const retention = project.retention_plan_json;
  const sound = project.sound_design_plan_json;
  return (
    <div className="rounded-lg border border-border/75 bg-background/70 p-4 lg:col-span-3">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold">Retention và âm thanh</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Bản tiếng Việt để kiểm tra nhịp giữ chân, pattern interrupt và sound design trước khi
            tạo segment.
          </p>
        </div>
        {!retention || !sound ? (
          <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-800 dark:text-amber-200">
            chưa có creative direction đầy đủ
          </span>
        ) : null}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
          <p className="text-xs font-medium uppercase text-muted-foreground">Retention map</p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/85">
            Hook: {metadataText(retention, ['hook_0_2s', 'hook'])}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Curiosity: {metadataText(retention, ['curiosity_gap', 'viewer_question'])}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Payoff: {metadataText(retention, ['payoff_plan'])}
          </p>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
          <p className="text-xs font-medium uppercase text-muted-foreground">Sound design</p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/85">
            Nhạc: {metadataText(sound, ['music_mood'])}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Năng lượng: {metadataText(sound, ['energy_curve'])}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Mix: {metadataText(sound, ['mixing_notes'])}
          </p>
        </div>
      </div>
    </div>
  );
}

function resourceTone(status: string | null | undefined): string {
  switch (status) {
    case 'critical':
      return 'border-red-500/35 bg-red-500/12 text-red-700 dark:text-red-200';
    case 'warning':
      return 'border-amber-500/35 bg-amber-500/12 text-amber-800 dark:text-amber-200';
    case 'normal':
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
    default:
      return 'border-border/70 bg-background/55 text-muted-foreground';
  }
}

function resourceBarTone(status: string | null | undefined): string {
  switch (status) {
    case 'critical':
      return 'bg-red-500';
    case 'warning':
      return 'bg-amber-500';
    case 'normal':
      return 'bg-emerald-500';
    default:
      return 'bg-muted-foreground/35';
  }
}

function formatResourcePercent(percent: number | null | undefined): string {
  return typeof percent === 'number' ? `${Math.round(percent)}%` : 'N/A';
}

function formatResourceMemory(
  used: number | null | undefined,
  total: number | null | undefined,
  unit: string | null | undefined,
): string {
  if (typeof used !== 'number' || typeof total !== 'number') return 'chưa có số đo';
  const divisor = unit === 'MB' ? 1024 : 1;
  const displayUnit = unit === 'MB' ? 'GB' : (unit ?? '');
  return `${(used / divisor).toFixed(1)} / ${(total / divisor).toFixed(1)} ${displayUnit}`.trim();
}

function formatResourceTemperature(
  used: number | null | undefined,
  unit: string | null | undefined,
  status: string | null | undefined,
): string {
  if (typeof used === 'number') {
    const suffix = unit === 'C' ? '°C' : (unit ?? '');
    return `${Math.round(used)}${suffix}`;
  }
  if (status === 'normal') return 'Ổn định';
  if (status === 'warning') return 'Cảnh báo';
  if (status === 'critical') return 'Nóng';
  return 'N/A';
}

function ResourceMetricRow({
  icon: Icon,
  label,
  detail,
  percent,
  status,
  value,
}: {
  icon: LucideIcon;
  label: string;
  detail: string;
  percent: number | null | undefined;
  status: string | null | undefined;
  value?: string;
}) {
  const width = Math.max(0, Math.min(100, typeof percent === 'number' ? percent : 0));
  return (
    <div className={cn('rounded-lg border px-3 py-2.5', resourceTone(status))}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 shrink-0" />
          <span className="truncate text-xs font-medium uppercase tracking-[0.12em]">{label}</span>
        </div>
        <span className="shrink-0 font-mono text-sm font-semibold tabular-nums">
          {value ?? formatResourcePercent(percent)}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-current/10">
        <span
          className={cn(
            'block h-full origin-left rounded-full transition-transform duration-700 [transition-timing-function:cubic-bezier(0.16,1,0.3,1)]',
            resourceBarTone(status),
          )}
          style={{ transform: `scaleX(${width / 100})` }}
        />
      </div>
      <p className="mt-1.5 truncate text-[11px] opacity-80">{detail}</p>
    </div>
  );
}

function SystemResourcePanel({
  resources,
  loading,
  error,
}: {
  resources?: SystemResourcesResponse;
  loading: boolean;
  error: unknown;
}) {
  const sampledAt = resources?.sampled_at
    ? new Date(resources.sampled_at).toLocaleTimeString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : null;

  return (
    <section className="rounded-lg border border-border/80 bg-card/60 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">Tải máy</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {sampledAt ? `Cập nhật ${sampledAt}` : 'Đang đo CPU, RAM, GPU và nhiệt độ'}
          </p>
        </div>
        <span
          className={cn(
            'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
            resources
              ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
              : 'border-border bg-background text-muted-foreground',
          )}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="h-4 w-4" />}
        </span>
      </div>

      <div className="mt-4 grid gap-2">
        {loading && !resources ? (
          <SkeletonRows count={4} />
        ) : error ? (
          <div className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-xs leading-relaxed text-destructive">
            Không đọc được thông số máy. Hãy restart backend nếu vừa cập nhật code.
          </div>
        ) : resources ? (
          <>
            <ResourceMetricRow
              icon={Cpu}
              label="CPU"
              detail={`${resources.cpu_count ?? '?'} core logic`}
              percent={resources.cpu.percent}
              status={resources.cpu.status}
            />
            <ResourceMetricRow
              icon={MemoryStick}
              label="RAM"
              detail={formatResourceMemory(
                resources.memory.used,
                resources.memory.total,
                resources.memory.unit,
              )}
              percent={resources.memory.percent}
              status={resources.memory.status}
            />
            <ResourceMetricRow
              icon={Gauge}
              label="GPU"
              detail={
                resources.gpu.percent == null
                  ? (resources.gpu_type ?? resources.gpu.label ?? 'GPU chưa có số đo')
                  : formatResourceMemory(
                      resources.gpu.used,
                      resources.gpu.total,
                      resources.gpu.unit,
                    )
              }
              percent={resources.gpu.percent}
              status={resources.gpu.status}
            />
            <ResourceMetricRow
              icon={Thermometer}
              label="Nhiệt"
              detail={resources.thermal?.label ?? 'Nhiệt độ hệ thống'}
              value={formatResourceTemperature(
                resources.thermal?.used,
                resources.thermal?.unit,
                resources.thermal?.status,
              )}
              percent={resources.thermal?.percent}
              status={resources.thermal?.status}
            />
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
            Chưa có dữ liệu tải máy.
          </div>
        )}
      </div>
    </section>
  );
}

export function AIVideoAssistant() {
  const platform = usePlatform();
  const queryClient = useQueryClient();
  const { data: profiles } = useProfiles();
  const [form, setForm] = useState<DraftForm>(initialForm);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creationMode, setCreationMode] = useState<ProjectCreationMode>('quick');
  const [autoMode, setAutoMode] = useState<VideoAutoRunMode>('full_auto');
  const [autoMaterialTarget, setAutoMaterialTarget] =
    useState<VideoAutoRunMaterialTarget>('video_clips');
  const [seriesDraft, setSeriesDraft] = useState<SeriesDraft>(emptySeriesDraft);
  const [episodeDraft, setEpisodeDraft] = useState<EpisodeDraft>(emptyEpisodeDraft);
  const [episodeDialogOpen, setEpisodeDialogOpen] = useState(false);
  const [editingSeriesId, setEditingSeriesId] = useState<string | null>(null);
  const [projectMenuId, setProjectMenuId] = useState<string | null>(null);
  const [sidePanelOpen, setSidePanelOpen] = useState(true);
  const [voiceSelectorOpen, setVoiceSelectorOpen] = useState(false);
  const [playingVoiceKey, setPlayingVoiceKey] = useState<string | null>(null);
  const voicePreviewRef = useRef<HTMLAudioElement | null>(null);

  const selectProject = (projectId: string | null) => {
    setSelectedProjectId(projectId);
    setVoiceSelectorOpen(false);
  };

  const projectsQuery = useQuery({
    queryKey: ['ai-video', 'projects'],
    queryFn: () => apiClient.listVideoProjects(),
    refetchInterval: (query) =>
      query.state.data?.some((project) => isAutoRunBusyStatus(project.active_run_status))
        ? 2000
        : 5000,
  });
  const seriesQuery = useQuery({
    queryKey: ['ai-video', 'series'],
    queryFn: () => apiClient.listVideoSeries(),
  });
  const providerQuery = useQuery({
    queryKey: ['ai-video', 'planning-check'],
    queryFn: () => apiClient.checkAIPlanningProvider(false),
  });
  const systemResourcesQuery = useQuery({
    queryKey: ['health', 'system-resources'],
    queryFn: () => apiClient.getSystemResources(),
    refetchInterval: 3000,
  });
  const projectQuery = useQuery({
    queryKey: ['ai-video', 'project', selectedProjectId],
    queryFn: () => apiClient.getVideoProject(selectedProjectId!),
    enabled: !!selectedProjectId,
    refetchInterval: (query) => {
      const project = query.state.data;
      return project?.scenes.some(isSceneBusy) || project?.shots.some(isShotBusy) ? 2500 : false;
    },
  });
  const statusQuery = useQuery({
    queryKey: ['ai-video', 'status', selectedProjectId],
    queryFn: () => apiClient.getVideoProjectStatus(selectedProjectId!),
    enabled: !!selectedProjectId,
    refetchInterval: (query) => (query.state.data?.planning_active ? 2000 : 5000),
  });
  const readinessQuery = useQuery({
    queryKey: ['ai-video', 'package-readiness', selectedProjectId],
    queryFn: () => apiClient.getVideoPackageReadiness(selectedProjectId!),
    enabled: !!selectedProjectId,
  });
  const debugQuery = useQuery({
    queryKey: ['ai-video', 'debug', selectedProjectId],
    queryFn: () => apiClient.getVideoProjectDebug(selectedProjectId!),
    enabled: !!selectedProjectId,
  });
  const autoRunQuery = useQuery({
    queryKey: ['ai-video', 'auto-run', 'latest', selectedProjectId],
    queryFn: () => apiClient.getLatestVideoAutoRun(selectedProjectId!),
    enabled: !!selectedProjectId,
    refetchInterval: (query) => (isAutoRunActive(query.state.data) ? 2000 : false),
  });
  const projectAutoRunQueries = useQueries({
    queries: (projectsQuery.data ?? []).map((project) => ({
      queryKey: ['ai-video', 'auto-run', 'latest', project.id],
      queryFn: () => apiClient.getLatestVideoAutoRun(project.id),
      refetchInterval: (query: { state: { data: VideoAutoRunResponse | null | undefined } }) =>
        isAutoRunActive(query.state.data) ? 2000 : 5000,
    })),
  });

  const selectedProject = projectQuery.data;
  const activeProjectId = selectedProject?.id ?? selectedProjectId;
  const latestAutoRun = autoRunQuery.data ?? null;
  const liveAutoRunsByProjectId = new Map<string, VideoAutoRunResponse>();
  for (const query of projectAutoRunQueries) {
    const run = query.data;
    if (run && isAutoRunActive(run)) {
      liveAutoRunsByProjectId.set(run.project_id, run);
    }
  }
  if (latestAutoRun && isAutoRunActive(latestAutoRun)) {
    liveAutoRunsByProjectId.set(latestAutoRun.project_id, latestAutoRun);
  }
  const projectsWithLiveRunState = useMemo(() => {
    const projects = projectsQuery.data ?? [];
    if (!liveAutoRunsByProjectId.size) return projects;
    return projects.map((project) =>
      liveAutoRunsByProjectId.has(project.id)
        ? {
            ...project,
            active_run_status: liveAutoRunsByProjectId.get(project.id)!.status,
            active_run_step: liveAutoRunsByProjectId.get(project.id)!.current_step,
            active_run_progress: liveAutoRunsByProjectId.get(project.id)!.progress,
          }
        : project,
    );
  }, [liveAutoRunsByProjectId, projectsQuery.data]);
  const groupedProjects = useMemo(
    () => groupProjectsBySeries(projectsWithLiveRunState, seriesQuery.data),
    [projectsWithLiveRunState, seriesQuery.data],
  );
  const selectedSeries = useMemo(
    () => seriesQuery.data?.find((series) => series.id === selectedProject?.series_id) ?? null,
    [selectedProject?.series_id, seriesQuery.data],
  );
  const episodeDialogSeries = useMemo(
    () => seriesQuery.data?.find((series) => series.id === episodeDraft.seriesId) ?? null,
    [episodeDraft.seriesId, seriesQuery.data],
  );
  const activeVideoLanguage = selectedProject?.target_language ?? form.targetLanguage;
  const activeVideoLanguageLabel = videoLanguageLabel(activeVideoLanguage);
  const selectedPurposeOption = purposeOption(form.videoPurpose);
  const activeVoiceProfileId = form.voiceProfileId.trim();
  const hasVoiceProfile = activeVoiceProfileId.length > 0;
  const providerReady = !!providerQuery.data?.ready;
  const approvedScenes = selectedProject?.scenes.filter((scene) => scene.approved) ?? [];
  const shots = selectedProject?.shots ?? [];
  const usesPromptSegments =
    !!selectedProject?.target_duration_seconds && selectedProject.target_duration_seconds > 0;
  const selectedPromptDuration = projectPromptDuration(selectedProject);
  const selectedMicroScenesPerPrompt = selectedProject?.micro_scenes_per_prompt || 3;
  const selectedPromptCount = projectPromptCount(selectedProject, shots.length);
  const selectedTotalMicroScenes = selectedPromptCount
    ? selectedPromptCount * selectedMicroScenesPerPrompt
    : null;
  const selectedSegmentCountMismatch = Boolean(
    selectedProject?.prompt_segment_count &&
      shots.length > 0 &&
      shots.length !== selectedProject.prompt_segment_count,
  );
  const usesShotNarration = selectedProject?.phase === 'phase2' && shots.length > 0;
  const narratedShots = shots.filter((shot) => shot.english_narration?.trim());
  const promptSegmentCount = Math.max(1, Number(form.promptSegmentCount) || 1);
  const promptSegmentDuration = Math.max(
    3,
    Number(form.promptSegmentDuration) || DEFAULT_PROMPT_SEGMENT_SECONDS,
  );
  const microScenesPerPrompt = Math.max(1, Number(form.microScenesPerPrompt) || 1);
  const derivedTotalDuration = promptSegmentCount * promptSegmentDuration;
  const derivedMicroSceneCount = promptSegmentCount * microScenesPerPrompt;
  const secondsPerMicroScene = promptSegmentDuration / microScenesPerPrompt;
  const promptConfigError =
    secondsPerMicroScene < 1.5 ? 'Mỗi cảnh nhỏ cần tối thiểu khoảng 1.5 giây.' : null;
  const selectedPromptConfigMatches = Boolean(
    selectedProject?.prompt_segment_count === promptSegmentCount &&
      selectedProject?.prompt_segment_duration_seconds === promptSegmentDuration &&
      selectedProject?.micro_scenes_per_prompt === microScenesPerPrompt,
  );
  const canCreateProject =
    form.sources.some((source) => source.content.trim()) && !promptConfigError;
  const promptContentKey = shots
    .filter((shot) => shot.prompt_status !== 'missing')
    .map((shot) => `${shot.id}:${shot.prompt_status}`)
    .join('|');
  const promptContentsQuery = useQuery({
    queryKey: ['ai-video', 'shot-prompts', activeProjectId, promptContentKey],
    enabled: !!activeProjectId && !!promptContentKey,
    queryFn: async () => {
      const entries = await Promise.all(
        shots
          .filter((shot) => shot.prompt_status !== 'missing')
          .map(async (shot): Promise<[string, VideoPromptContentResponse] | null> => {
            try {
              return [shot.id, await apiClient.getVideoShotPrompt(shot.project_id, shot.id)];
            } catch {
              return null;
            }
          }),
      );
      return Object.fromEntries(
        entries.filter((entry): entry is [string, VideoPromptContentResponse] => entry !== null),
      );
    },
  });
  const promptByShotId = promptContentsQuery.data ?? {};
  const autoRunBlocking = isAutoRunActive(latestAutoRun);
  const autoRunBusy = isAutoRunBusy(latestAutoRun);
  const planningActive = !!statusQuery.data?.planning_active;
  const planningActiveStep = statusQuery.data?.planning_active_step ?? null;
  const planningBlockedMessage = planningActiveStep
    ? `Dự án đang chạy AI planning (${planningActiveStep}). Hãy chờ bước này hoàn tất rồi thử lại.`
    : 'Dự án đang chạy AI planning. Hãy chờ bước này hoàn tất rồi thử lại.';
  const projectPlanningBusy = autoRunBusy || planningActive;
  const activeProjectRuns = projectsWithLiveRunState.filter((project) =>
    isAutoRunActiveStatus(project.active_run_status),
  );
  const busyProjectRunCount = activeProjectRuns.filter((project) =>
    isAutoRunBusyStatus(project.active_run_status),
  ).length;
  const waitingProjectRunCount = activeProjectRuns.length - busyProjectRunCount;

  const selectedVoiceProfile = useMemo(() => {
    return profiles?.find((profile) => profile.id === activeVoiceProfileId) ?? null;
  }, [activeVoiceProfileId, profiles]);
  const selectedVoiceName = selectedVoiceProfile?.name ?? 'Chưa chọn giọng';
  const selectedVoiceEngine =
    selectedVoiceProfile?.default_engine || selectedVoiceProfile?.preset_engine || 'qwen';
  const qwenVietnameseBypass = usesQwenVietnameseBypass(form.targetLanguage, selectedVoiceProfile);
  const selectedVoiceSupportsLanguage = selectedVoiceProfile
    ? qwenVietnameseBypass ||
      getLanguageOptionsForEngine(selectedVoiceEngine).some(
        (option) => option.value === form.targetLanguage,
      )
    : true;
  const selectedVoiceLanguageMatches = selectedVoiceProfile
    ? selectedVoiceProfile.language === form.targetLanguage
    : true;
  const voiceCompatibilityWarning = !selectedVoiceProfile
    ? null
    : !selectedVoiceLanguageMatches
      ? `Hồ sơ giọng đang là ${voiceProfileLanguageLabel(selectedVoiceProfile.language)} nhưng ngôn ngữ video là ${videoLanguageLabel(form.targetLanguage)}.`
      : !selectedVoiceSupportsLanguage
        ? `Bộ tạo giọng ${selectedVoiceEngine} có thể chưa hỗ trợ ${videoLanguageLabel(form.targetLanguage)}.`
        : null;
  const showVoiceSelector = !hasVoiceProfile || voiceSelectorOpen;

  useEffect(() => {
    if (!selectedProjectId || !projectsQuery.data) return;
    if (projectsQuery.data.some((project) => project.id === selectedProjectId)) return;
    const nextProjectId = projectsQuery.data[0]?.id ?? null;
    setSelectedProjectId(nextProjectId);
    setVoiceSelectorOpen(false);
    setProjectMenuId(null);
  }, [selectedProjectId, projectsQuery.data]);

  useEffect(() => {
    if (!selectedProject) return;
    setForm((current) => ({
      ...current,
      targetLanguage: selectedProject.target_language ?? current.targetLanguage,
      videoPurpose: selectedProject.video_purpose ?? current.videoPurpose,
      dialogueMode: selectedProject.dialogue_mode ?? current.dialogueMode,
      narrationDensity: selectedProject.narration_density ?? current.narrationDensity,
      callToActionStyle: selectedProject.call_to_action_style || 'none',
      promptSegmentCount:
        projectPromptCount(selectedProject, shots.length) ?? current.promptSegmentCount,
      promptSegmentDuration: projectPromptDuration(selectedProject),
      microScenesPerPrompt: selectedProject.micro_scenes_per_prompt || current.microScenesPerPrompt,
      aspectRatio: normalizeAspectRatio(selectedProject.aspect_ratio),
      visualStyle: selectedProject.visual_style || current.visualStyle,
      voiceProfileId: selectedProject.voice_profile_id || '',
    }));
  }, [selectedProject, shots.length]);

  useEffect(() => {
    if (!latestAutoRun || latestAutoRun.project_id !== selectedProjectId) return;
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'project', latestAutoRun.project_id] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'projects'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'status', latestAutoRun.project_id] });
    queryClient.invalidateQueries({
      queryKey: ['ai-video', 'package-readiness', latestAutoRun.project_id],
    });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'debug', latestAutoRun.project_id] });
  }, [latestAutoRun, queryClient, selectedProjectId]);

  useEffect(() => {
    if (!editingSeriesId) return;
    const series = seriesQuery.data?.find((item) => item.id === editingSeriesId);
    if (!series) return;
    setSeriesDraft({
      title: series.title,
      character_bible: series.character_bible || '',
      world_bible: series.world_bible || '',
      style_bible: series.style_bible || '',
      continuity_rules: series.continuity_rules || '',
      negative_rules: series.negative_rules || '',
      previous_episode_summary: series.previous_episode_summary || '',
    });
  }, [editingSeriesId, seriesQuery.data]);

  useEffect(() => {
    return () => {
      const audio = voicePreviewRef.current;
      if (!audio) return;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    };
  }, []);

  const invalidateProject = () => queryClient.invalidateQueries({ queryKey: ['ai-video'] });

  const openEpisodeDialog = (seriesId?: string | null) => {
    const nextSeriesId = seriesId ?? episodeDraft.seriesId ?? editingSeriesId ?? '';
    setEpisodeDraft((current) => ({
      ...current,
      seriesId: nextSeriesId,
    }));
    if (nextSeriesId) {
      setEditingSeriesId(nextSeriesId);
    }
    setEpisodeDialogOpen(true);
  };

  const toggleVoicePreview = (key: string, url: string) => {
    let audio = voicePreviewRef.current;
    if (!audio) {
      audio = new Audio();
      voicePreviewRef.current = audio;
    }

    if (playingVoiceKey === key) {
      audio.pause();
      audio.currentTime = 0;
      setPlayingVoiceKey(null);
      return;
    }

    audio.pause();
    audio.currentTime = 0;
    audio.src = url;
    audio.onended = () => {
      setPlayingVoiceKey((current) => (current === key ? null : current));
    };
    audio.onerror = () => {
      setPlayingVoiceKey((current) => (current === key ? null : current));
      setNotice('Không phát được preview giọng. Hãy thử tải âm thanh để kiểm tra file.');
    };

    audio
      .play()
      .then(() => setPlayingVoiceKey(key))
      .catch(() => {
        setPlayingVoiceKey(null);
        setNotice(
          'Trình duyệt chưa cho phát preview. Bấm lại nút Nghe thử sau một thao tác trên trang.',
        );
      });
  };

  const createProject = useMutation({
    mutationFn: async () => {
      const sourceBlocks = form.sources
        .filter((source) => source.content.trim())
        .map((source) => ({ block_type: source.block_type, content: source.content.trim() }));
      const topic = sourceBlocks[0]?.content || form.title.trim() || 'Dự án video mới';
      const project = await apiClient.createVideoProject({
        title: form.title.trim() || null,
        topic,
        language: 'vi',
        target_language: form.targetLanguage,
        video_purpose: form.videoPurpose,
        dialogue_mode: form.dialogueMode,
        narration_density: form.narrationDensity,
        call_to_action_style: form.callToActionStyle,
        target_duration_seconds: null,
        prompt_segment_count: promptSegmentCount,
        prompt_segment_duration_seconds: promptSegmentDuration,
        micro_scenes_per_prompt: microScenesPerPrompt,
        aspect_ratio: form.aspectRatio,
        visual_style: form.visualStyle,
        voice_profile_id: form.voiceProfileId || null,
        phase: 'phase2',
        default_shot_duration_seconds: null,
        source_blocks: sourceBlocks,
      });

      if (creationMode !== 'quick') {
        return { project, autoRun: null, autoRunError: null };
      }

      try {
        const autoRun = await apiClient.startVideoAutoRun(project.id, {
          mode: autoMode,
          material_target: autoMaterialTarget,
          force: false,
        });
        return { project, autoRun, autoRunError: null };
      } catch (error) {
        return { project, autoRun: null, autoRunError: getErrorMessage(error) };
      }
    },
    onSuccess: ({ project, autoRun, autoRunError }) => {
      selectProject(project.id);
      if (autoRun) {
        queryClient.setQueryData(['ai-video', 'auto-run', 'latest', project.id], autoRun);
        setNotice(
          autoRun.material_target === 'prompts_only'
            ? 'Đã tạo dự án và bắt đầu dựng nhanh tới prompt video. Voice và phụ đề sẽ bỏ qua.'
            : autoRun.material_target === 'video_clips'
              ? 'Đã tạo dự án và bắt đầu tự tạo prompt, gửi sang Veo, tải clip, tạo voice/SRT rồi render MP4.'
            : autoRun.mode === 'review_gated'
              ? 'Đã tạo dự án và bắt đầu dựng nhanh. Hệ thống sẽ dừng ở các điểm cần duyệt.'
              : 'Đã tạo dự án và bắt đầu dựng nhanh ở chế độ tự chạy hết.',
        );
      } else if (autoRunError) {
        setNotice(`Đã tạo dự án, nhưng chưa bắt đầu dựng nhanh: ${autoRunError}`);
      } else {
        setNotice('Đã tạo dự án phase 2. Bước tiếp theo là để AI phát triển kịch bản.');
      }
      invalidateProject();
    },
  });

  const saveSeries = useMutation({
    mutationFn: async () => {
      const payload = {
        title: seriesDraft.title.trim(),
        character_bible: seriesDraft.character_bible.trim() || null,
        world_bible: seriesDraft.world_bible.trim() || null,
        style_bible: seriesDraft.style_bible.trim() || null,
        continuity_rules: seriesDraft.continuity_rules.trim() || null,
        negative_rules: seriesDraft.negative_rules.trim() || null,
        previous_episode_summary: seriesDraft.previous_episode_summary.trim() || null,
      };
      if (!payload.title) throw new Error('Tên series là bắt buộc.');
      return editingSeriesId
        ? apiClient.updateVideoSeries(editingSeriesId, payload)
        : apiClient.createVideoSeries(payload);
    },
    onSuccess: (series) => {
      setEditingSeriesId(series.id);
      setEpisodeDraft((current) => ({ ...current, seriesId: series.id }));
      setNotice('Đã lưu Series Bible. Các tập tạo sau sẽ dùng context này.');
      invalidateProject();
    },
  });

  const createEpisode = useMutation({
    mutationFn: async () => {
      if (!episodeDraft.seriesId) throw new Error('Chọn series trước khi tạo tập.');
      const topic = episodeDraft.topic.trim();
      if (!topic) throw new Error('Nhập ý tưởng tập mới.');
      return apiClient.createVideoSeriesEpisode(episodeDraft.seriesId, {
        topic,
        episode_title: episodeDraft.episodeTitle.trim() || null,
        target_language: form.targetLanguage,
        video_purpose: form.videoPurpose,
        dialogue_mode: form.dialogueMode,
        narration_density: form.narrationDensity,
        call_to_action_style: form.callToActionStyle,
        prompt_segment_count: promptSegmentCount,
        prompt_segment_duration_seconds: promptSegmentDuration,
        micro_scenes_per_prompt: microScenesPerPrompt,
        aspect_ratio: form.aspectRatio,
        visual_style: form.visualStyle,
        voice_profile_id: form.voiceProfileId || null,
        phase: 'phase2',
        default_shot_duration_seconds: null,
        source_blocks: [{ block_type: 'idea', content: topic }],
        reuse_latest_config: true,
      });
    },
    onSuccess: (project) => {
      selectProject(project.id);
      setEpisodeDialogOpen(false);
      setEpisodeDraft((current) => ({ ...current, episodeTitle: '', topic: '' }));
      setNotice('Đã tạo tập mới trong series. Project này sẽ dùng cùng Series Bible khi planning.');
      invalidateProject();
    },
  });

  const renameProject = useMutation({
    mutationFn: async (project: VideoProjectResponse) => {
      const currentTitle = project.title.trim();
      const nextTitle = window.prompt('Nhập tên mới cho project video:', currentTitle);
      if (nextTitle === null) return null;
      const title = nextTitle.trim();
      if (!title || title === currentTitle) return null;
      return apiClient.updateVideoProject(project.id, { title });
    },
    onSuccess: (project) => {
      if (!project) return;
      setProjectMenuId(null);
      setNotice('Đã đổi tên project video.');
      invalidateProject();
    },
  });

  const resetGeneratedData = useMutation({
    mutationFn: async (project: VideoProjectResponse) => {
      const ok = window.confirm(
        `Xoá dữ liệu đã tạo của “${project.title}”? Source blocks, cấu hình và liên kết series sẽ được giữ lại.`,
      );
      if (!ok) return null;
      return apiClient.resetVideoProjectGeneratedData(project.id);
    },
    onSuccess: (result) => {
      if (!result) return;
      setNotice(result.message);
      invalidateProject();
    },
  });

  const deleteProject = useMutation({
    mutationFn: async (project: VideoProjectResponse) => {
      const ok = window.confirm(
        `Xoá vĩnh viễn project “${project.title}” và toàn bộ artifact liên quan? Thao tác này không xoá Series Bible.`,
      );
      if (!ok) return null;
      await apiClient.deleteVideoProject(project.id);
      return project.id;
    },
    onSuccess: (deletedId) => {
      if (!deletedId) return;
      const nextProject = projectsQuery.data?.find((project) => project.id !== deletedId) ?? null;
      selectProject(nextProject?.id ?? null);
      setProjectMenuId(null);
      setNotice('Đã xoá project video.');
      invalidateProject();
    },
  });

  const localizeProject = useMutation({
    mutationFn: async (project: VideoProjectResponse) => {
      const targetLanguage: VideoLanguage = project.target_language === 'vi' ? 'en' : 'vi';
      const ok = window.confirm(
        `Tạo bản ${videoLanguageLabel(targetLanguage)} riêng từ “${project.title}”? Bản mới sẽ dùng nguồn/cấu hình hiện tại và tạo lại kịch bản, giọng đọc, phụ đề, gói xuất riêng.`,
      );
      if (!ok) return null;
      return apiClient.localizeVideoProject(project.id, {
        target_language: targetLanguage,
        video_purpose: 'localized_variant',
        dialogue_mode: project.dialogue_mode,
        narration_density: project.narration_density,
        call_to_action_style: project.call_to_action_style ?? 'none',
      });
    },
    onSuccess: (project) => {
      if (!project) return;
      setProjectMenuId(null);
      selectProject(project.id);
      setNotice(
        'Đã tạo bản dịch riêng. Hãy chọn giọng phù hợp rồi tạo lại kịch bản, giọng đọc và phụ đề cho bản này.',
      );
      invalidateProject();
    },
  });

  const deleteSourceBlock = useMutation({
    mutationFn: async (block: VideoSourceBlockResponse) => {
      const isLast = (selectedProject?.source_blocks.length ?? 0) <= 1;
      const message = isLast
        ? 'Đây là khối nguồn cuối cùng. Xoá khối này sẽ khiến dự án không còn đầu vào để tự chạy. Vẫn xoá?'
        : `Xoá khối nguồn #${block.sort_order}? Kịch bản, segment và prompt hiện có sẽ được đánh dấu cần tạo lại.`;
      const ok = window.confirm(message);
      if (!ok) return null;
      return apiClient.deleteVideoSourceBlock(block.project_id, block.id, isLast);
    },
    onSuccess: (result) => {
      if (!result) return;
      setNotice('Đã xoá khối nguồn và đánh dấu dữ liệu cần tạo lại.');
      invalidateProject();
    },
  });

  const developStory = useMutation({
    mutationFn: (force: boolean) => {
      if (planningActive) throw new Error(planningBlockedMessage);
      return apiClient.developVideoStory(activeProjectId!, force);
    },
    onSuccess: () => {
      setNotice(
        'AI đã tạo chiến lược kịch bản, ghi chú nhất quán và kịch bản chi tiết. Hãy đọc và duyệt trước khi tạo segment.',
      );
      invalidateProject();
    },
  });

  const approveStory = useMutation({
    mutationFn: (approved: boolean) => apiClient.approveVideoStory(activeProjectId!, approved),
    onSuccess: (_, approved) => {
      setNotice(
        approved
          ? 'Đã duyệt kịch bản. Có thể tạo prompt segment theo cấu hình dự án.'
          : 'Đã bỏ duyệt kịch bản. Bạn có thể viết lại nội dung.',
      );
      invalidateProject();
    },
  });

  const generateShots = useMutation({
    mutationFn: async () => {
      if (!activeProjectId) throw new Error('Chưa chọn dự án.');
      if (planningActive) throw new Error(planningBlockedMessage);
      if (promptConfigError) throw new Error(promptConfigError);
      if (!selectedPromptConfigMatches) {
        await apiClient.updateVideoProject(activeProjectId, {
          prompt_segment_count: promptSegmentCount,
          prompt_segment_duration_seconds: promptSegmentDuration,
          micro_scenes_per_prompt: microScenesPerPrompt,
        });
      }
      return apiClient.generateVideoShots(activeProjectId);
    },
    onSuccess: () => {
      setNotice(`Đã tạo đúng ${promptSegmentCount} prompt segment theo cấu hình hiện tại.`);
      invalidateProject();
    },
  });

  const generatePrompts = useMutation({
    mutationFn: () => {
      if (planningActive) throw new Error(planningBlockedMessage);
      return apiClient.generateVideoPromptPack(activeProjectId!);
    },
    onSuccess: () => {
      setNotice('Prompt gốc và bản giải thích tiếng Việt đã sẵn sàng để đọc, copy hoặc tải xuống.');
      invalidateProject();
    },
  });

  const lockShot = useMutation({
    mutationFn: ({ shot, locked }: { shot: VideoShotResponse; locked: boolean }) =>
      apiClient.lockVideoShot(shot.project_id, shot.id, locked),
    onSuccess: invalidateProject,
  });

  const regenerateShot = useMutation({
    mutationFn: (shot: VideoShotResponse) =>
      apiClient.regenerateVideoShot(shot.project_id, shot.id),
    onSuccess: invalidateProject,
  });

  const saveProjectVoice = useMutation({
    mutationFn: (profileId: string) => {
      if (!activeProjectId) throw new Error('Chưa chọn dự án.');
      return apiClient.updateVideoProject(activeProjectId, { voice_profile_id: profileId || null });
    },
    onSuccess: (_, profileId) => {
      setNotice(profileId ? 'Đã lưu hồ sơ giọng cho dự án.' : 'Đã bỏ hồ sơ giọng khỏi dự án.');
      invalidateProject();
    },
  });

  const saveProjectPurposeSettings = useMutation({
    mutationFn: (
      next: Pick<
        DraftForm,
        | 'targetLanguage'
        | 'videoPurpose'
        | 'dialogueMode'
        | 'narrationDensity'
        | 'callToActionStyle'
      >,
    ) => {
      if (!activeProjectId) throw new Error('Chưa chọn dự án.');
      return apiClient.updateVideoProject(activeProjectId, {
        target_language: next.targetLanguage,
        video_purpose: next.videoPurpose,
        dialogue_mode: next.dialogueMode,
        narration_density: next.narrationDensity,
        call_to_action_style: next.callToActionStyle,
      });
    },
    onSuccess: () => {
      setNotice(
        'Đã lưu mục đích video và cấu hình thoại cho dự án. Artifact phụ thuộc sẽ cần tạo lại nếu contract thay đổi.',
      );
      invalidateProject();
    },
  });

  const updatePurposeSettings = (
    patch: Partial<
      Pick<
        DraftForm,
        | 'targetLanguage'
        | 'videoPurpose'
        | 'dialogueMode'
        | 'narrationDensity'
        | 'callToActionStyle'
      >
    >,
  ) => {
    const next = { ...form, ...patch };
    setForm(next);
    if (activeProjectId) {
      saveProjectPurposeSettings.mutate({
        targetLanguage: next.targetLanguage,
        videoPurpose: next.videoPurpose,
        dialogueMode: next.dialogueMode,
        narrationDensity: next.narrationDensity,
        callToActionStyle: next.callToActionStyle,
      });
    }
  };

  const handleVideoPurposeChange = (value: VideoPurpose) => {
    const preset = purposeOption(value);
    updatePurposeSettings({
      videoPurpose: value,
      targetLanguage: preset.recommendedTargetLanguage,
      dialogueMode: preset.dialogueMode,
      narrationDensity: preset.narrationDensity,
      callToActionStyle: preset.cta,
    });
  };

  const handleVoiceProfileChange = (profileId: string) => {
    setForm((current) => ({ ...current, voiceProfileId: profileId }));
    if (profileId) {
      setVoiceSelectorOpen(false);
    }
    if (activeProjectId) {
      saveProjectVoice.mutate(profileId);
    }
  };

  const requireVoiceProfile = () => {
    if (!activeVoiceProfileId) throw new Error('Chưa chọn hồ sơ giọng cho dự án video.');
    return activeVoiceProfileId;
  };

  const generateSceneVoice = useMutation({
    mutationFn: (scene: VideoSceneResponse) => {
      const profileId = requireVoiceProfile();
      return apiClient.createVideoSceneVoice(scene.project_id, scene.id, {
        ...aiVideoVoiceRequestBase(profileId, activeVideoLanguage, selectedVoiceProfile),
        force: scene.voice_status === 'failed' || scene.voice_status === 'stale',
      });
    },
    onSuccess: invalidateProject,
  });

  const generateShotVoice = useMutation({
    mutationFn: (shot: VideoShotResponse) => {
      const profileId = requireVoiceProfile();
      return apiClient.createVideoShotVoice(shot.project_id, shot.id, {
        ...aiVideoVoiceRequestBase(profileId, activeVideoLanguage, selectedVoiceProfile),
        force: shot.voice_status === 'failed' || shot.voice_status === 'stale',
      });
    },
    onSuccess: invalidateProject,
  });

  const generateSubtitle = useMutation({
    mutationFn: () => apiClient.generateVideoSubtitle(activeProjectId!),
    onSuccess: () => {
      setNotice('Đã tạo phụ đề .srt theo thời lượng thật của âm thanh.');
      invalidateProject();
    },
  });

  const createPackage = useMutation({
    mutationFn: () => apiClient.createVideoPackage(activeProjectId!),
    onSuccess: () => {
      setNotice('Đã tạo ZIP nguyên liệu prompt video.');
      invalidateProject();
    },
  });

  const refreshAfterAutoRun = (run?: VideoAutoRunResponse | null) => {
    if (run) {
      queryClient.setQueryData(['ai-video', 'auto-run', 'latest', run.project_id], run);
    }
    invalidateProject();
  };

  const startAutoRun = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error('Chưa chọn dự án.');
      if (planningActive) throw new Error(planningBlockedMessage);
      return apiClient.startVideoAutoRun(activeProjectId, {
        mode: autoMode,
        material_target: autoMaterialTarget,
        force: false,
      });
    },
    onSuccess: (run) => {
      setNotice(
        run.material_target === 'prompts_only'
          ? 'Auto-run đã bắt đầu tới prompt video. Voice và phụ đề sẽ bỏ qua.'
        : run.material_target === 'video_clips'
          ? 'Auto-run đã bắt đầu: tạo prompt, gửi sang Veo, tải clip, tạo voice/SRT rồi render MP4.'
          : run.mode === 'review_gated'
            ? 'Auto-run đã bắt đầu và sẽ dừng ở các điểm cần duyệt.'
            : 'Auto-run đã bắt đầu ở chế độ tự chạy hết.',
      );
      refreshAfterAutoRun(run);
    },
  });

  const continueAutoRun = useMutation({
    mutationFn: (approved: boolean) => {
      if (!activeProjectId || !latestAutoRun)
        throw new Error('Không tìm thấy auto-run để tiếp tục.');
      return apiClient.continueVideoAutoRun(activeProjectId, latestAutoRun.id, { approved });
    },
    onSuccess: (run) => {
      setNotice(
        run.status === 'cancelled'
          ? 'Auto-run đã dừng sau khi không duyệt.'
          : 'Auto-run đang chạy tiếp từ nội dung mới nhất.',
      );
      refreshAfterAutoRun(run);
    },
  });

  const cancelAutoRun = useMutation({
    mutationFn: () => {
      if (!activeProjectId || !latestAutoRun) throw new Error('Không tìm thấy auto-run để hủy.');
      return apiClient.cancelVideoAutoRun(activeProjectId, latestAutoRun.id);
    },
    onSuccess: (run) => {
      setNotice('Đã hủy auto-run. Các nguyên liệu đã tạo trước đó vẫn giữ trong dự án.');
      refreshAfterAutoRun(run);
    },
  });

  const retryAutoRun = useMutation({
    mutationFn: () => {
      if (!activeProjectId || !latestAutoRun) throw new Error('Không tìm thấy auto-run để retry.');
      return apiClient.retryVideoAutoRun(activeProjectId, latestAutoRun.id);
    },
    onSuccess: (run) => {
      setNotice('Auto-run đang retry từ bước còn thiếu hoặc lỗi gần nhất.');
      refreshAfterAutoRun(run);
    },
  });

  const saveDownload = async (download: Promise<DownloadedBlob>, extensions: string[]) => {
    const result = await download;
    await platform.filesystem.saveFile(result.filename, result.blob, [
      { name: 'AI Video Assistant', extensions },
    ]);
  };

  const copyShotPrompt = async (shot: VideoShotResponse) => {
    const prompt = await apiClient.getVideoShotPrompt(shot.project_id, shot.id);
    await navigator.clipboard.writeText(prompt.content);
    setNotice(`Đã copy prompt gốc của ${shotLabel(shot)}.`);
  };

  const copyDebug = async () => {
    await navigator.clipboard.writeText(JSON.stringify(debugQuery.data ?? {}, null, 2));
    setNotice('Đã copy thông tin debug đã redaction.');
  };

  const operationError =
    createProject.error ||
    developStory.error ||
    approveStory.error ||
    generateShots.error ||
    generatePrompts.error ||
    saveProjectVoice.error ||
    saveProjectPurposeSettings.error ||
    generateSceneVoice.error ||
    generateShotVoice.error ||
    generateSubtitle.error ||
    createPackage.error ||
    saveSeries.error ||
    createEpisode.error ||
    renameProject.error ||
    resetGeneratedData.error ||
    deleteProject.error ||
    localizeProject.error ||
    deleteSourceBlock.error ||
    startAutoRun.error ||
    continueAutoRun.error ||
    cancelAutoRun.error ||
    retryAutoRun.error ||
    lockShot.error ||
    regenerateShot.error;

  const renderRecentProject = (project: VideoProjectResponse) => {
    const selected = selectedProjectId === project.id;
    const projectRunActive = isAutoRunActiveStatus(project.active_run_status);
    const projectRunBusy = isAutoRunBusyStatus(project.active_run_status);
    const projectRunFailed = project.active_run_status === 'failed';
    const projectProgress = Math.min(
      100,
      Math.max(0, Math.round((project.active_run_progress ?? 0) * 100)),
    );
    const projectProgressScale =
      Math.max(projectRunBusy && projectProgress === 0 ? 5 : projectProgress, 0) / 100;
    const projectRunStep = autoRunStepLabel(project.active_run_step);
    const projectRunStatus = autoRunStatusText(project.active_run_status);
    const projectMeta = projectRunFailed
      ? `Lỗi · ${projectRunStep}`
      : projectRunActive
        ? projectRunStatus
        : `${project.shot_count || project.scene_count} mục · ${project.status}`;
    const activeTone = projectRunBusy ? 'sky' : 'amber';

    return (
      <div
        key={project.id}
        className={cn(
          'relative overflow-visible rounded-lg border transition duration-200',
          projectRunFailed
            ? selected
              ? 'border-red-300/70 bg-red-600 text-white shadow-[0_0_0_1px_rgba(248,113,113,0.35)]'
              : 'border-red-500/45 bg-red-500/12 hover:bg-red-500/18'
            : selected
              ? 'border-foreground/30 bg-foreground text-background'
              : 'border-border bg-background/60 hover:bg-muted/60',
          projectRunActive && !selected && activeTone === 'sky'
            ? 'border-sky-500/35 bg-sky-500/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
            : null,
          projectRunActive && !selected && activeTone === 'amber'
            ? 'border-amber-500/35 bg-amber-500/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
            : null,
          projectRunActive ? 'pb-1.5' : null,
        )}
      >
        {projectRunFailed ? (
          <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-red-300/90 to-transparent" />
        ) : null}
        {projectRunBusy ? (
          <>
            <span className="pointer-events-none absolute inset-0 rounded-lg border border-sky-400/50 opacity-70 animate-pulse" />
            <span className="pointer-events-none absolute inset-x-0 top-0 h-px animate-pulse bg-gradient-to-r from-transparent via-sky-300/90 to-transparent" />
          </>
        ) : null}
        <div className="grid grid-cols-[minmax(0,1fr)_36px] items-stretch">
          <button
            type="button"
            onClick={() => selectProject(project.id)}
            className="min-w-0 px-3 py-2 text-left text-sm transition-transform active:scale-[0.99]"
          >
            <span className="block truncate font-medium">
              {project.series_id ? episodeDisplay(project) : project.title}
            </span>
            <span className="mt-1 flex min-w-0 items-center gap-1.5 text-xs opacity-75">
              {projectRunBusy ? (
                <span className="relative flex h-2 w-2 shrink-0" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-sky-500" />
                </span>
              ) : projectRunFailed ? (
                <span className="h-2 w-2 shrink-0 rounded-full bg-red-500" aria-hidden="true" />
              ) : projectRunActive ? (
                <span className="h-2 w-2 shrink-0 rounded-full bg-amber-500" aria-hidden="true" />
              ) : null}
              <span className="min-w-0 truncate">{projectMeta}</span>
            </span>
            {projectRunFailed ? (
              <span
                className={cn(
                  'mt-2 inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em]',
                  selected
                    ? 'border-white/30 bg-white/10 text-white/90'
                    : 'border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-200',
                )}
              >
                <span className="truncate">Auto-run đã dừng</span>
              </span>
            ) : null}
            {projectRunActive ? (
              <span className="mt-2 flex min-w-0 items-center justify-between gap-2 text-[10px] uppercase tracking-[0.14em]">
                <span
                  className={cn(
                    'min-w-0 truncate rounded-full border px-2 py-0.5',
                    selected
                      ? 'border-background/25 bg-background/10 text-background/85'
                      : activeTone === 'sky'
                        ? 'border-sky-500/25 bg-sky-500/10 text-sky-700 dark:text-sky-200'
                        : 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200',
                  )}
                >
                  {projectRunStep}
                </span>
                <span className="shrink-0 font-mono tabular-nums opacity-75">
                  {projectProgress > 0 ? `${projectProgress}%` : '0%'}
                </span>
              </span>
            ) : null}
          </button>
          <button
            type="button"
            aria-label="Mở menu dự án"
            onClick={() =>
              setProjectMenuId((current) => (current === project.id ? null : project.id))
            }
            className="flex h-full min-h-12 w-9 items-center justify-center border-l border-current/10 opacity-75 transition hover:opacity-100"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>
        {projectRunActive ? (
          <div
            className={cn(
              'pointer-events-none absolute inset-x-0 bottom-0 h-1.5 overflow-hidden',
              selected
                ? 'bg-background/20'
                : activeTone === 'sky'
                  ? 'bg-sky-500/15'
                  : 'bg-amber-500/15',
            )}
            role="progressbar"
            aria-label={`Tiến độ ${projectRunStep}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={projectProgress}
          >
            <span
              className={cn(
                'block h-full origin-left transition-transform duration-700 [transition-timing-function:cubic-bezier(0.16,1,0.3,1)]',
                selected
                  ? 'bg-background/90'
                  : activeTone === 'sky'
                    ? 'bg-sky-400'
                    : 'bg-amber-400',
                projectRunBusy ? 'animate-pulse' : null,
              )}
              style={{ transform: `scaleX(${projectProgressScale})` }}
            />
          </div>
        ) : null}
        {projectMenuId === project.id ? (
          <div className="absolute right-1 top-10 z-30 grid w-44 gap-1 rounded-lg border border-border bg-background p-1 text-foreground shadow-lg shadow-foreground/10">
            <Button
              size="sm"
              variant="ghost"
              className="h-8 justify-start rounded-md px-2 text-xs"
              disabled={renameProject.isPending}
              onClick={() => renameProject.mutate(project)}
            >
              <Pencil className="h-4 w-4" />
              <span className="truncate">Đổi tên</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 justify-start rounded-md px-2 text-xs"
              disabled={localizeProject.isPending || projectRunBusy}
              onClick={() => localizeProject.mutate(project)}
            >
              <Copy className="h-4 w-4" />
              <span className="truncate">Tạo bản dịch</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 justify-start rounded-md px-2 text-xs"
              disabled={resetGeneratedData.isPending || projectRunBusy}
              onClick={() => resetGeneratedData.mutate(project)}
            >
              <RefreshCw className="h-4 w-4" />
              <span className="truncate">Đặt lại dữ liệu</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 justify-start rounded-md px-2 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground"
              disabled={deleteProject.isPending || projectRunBusy}
              onClick={() => deleteProject.mutate(project)}
            >
              <Trash2 className="h-4 w-4" />
              <span className="truncate">Xoá dự án</span>
            </Button>
          </div>
        ) : null}
      </div>
    );
  };

  const recentProjectsPanel = (
    <section className="rounded-lg border border-border/80 bg-card/60 p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">Dự án gần đây</p>
        {activeProjectRuns.length ? (
          <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-sky-700 dark:text-sky-200">
            {busyProjectRunCount
              ? `${busyProjectRunCount} đang chạy`
              : `${waitingProjectRunCount} chờ`}
          </span>
        ) : null}
      </div>
      {activeProjectRuns.length ? (
        <div className="mt-3 border-y border-sky-500/20 py-3" aria-live="polite">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-2 font-medium">
              <span className="relative flex h-2 w-2 shrink-0" aria-hidden="true">
                {busyProjectRunCount ? (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-70" />
                ) : null}
                <span
                  className={cn(
                    'relative inline-flex h-2 w-2 rounded-full',
                    busyProjectRunCount ? 'bg-sky-500' : 'bg-amber-500',
                  )}
                />
              </span>
              <span className="min-w-0 truncate">
                {busyProjectRunCount ? 'Prompt đang chạy' : 'Prompt đang chờ xử lý'}
              </span>
            </span>
            <span className="shrink-0 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              {busyProjectRunCount ? `${busyProjectRunCount} chạy` : null}
              {busyProjectRunCount && waitingProjectRunCount ? ' · ' : null}
              {waitingProjectRunCount ? `${waitingProjectRunCount} chờ` : null}
            </span>
          </div>
          <div className="mt-2 grid gap-1">
            {activeProjectRuns.slice(0, 4).map((project) => {
              const projectRunBusy = isAutoRunBusyStatus(project.active_run_status);
              const projectProgress = Math.min(
                100,
                Math.max(0, Math.round((project.active_run_progress ?? 0) * 100)),
              );
              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => selectProject(project.id)}
                  className="grid min-h-7 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-md px-1 py-1 text-left text-xs transition hover:bg-muted/45 active:scale-[0.99]"
                >
                  <span className="min-w-0 truncate text-foreground/85">
                    {project.series_id ? episodeDisplay(project) : project.title}
                  </span>
                  <span
                    className={cn(
                      'shrink-0 font-mono tabular-nums',
                      projectRunBusy
                        ? 'text-sky-700 dark:text-sky-200'
                        : 'text-amber-800 dark:text-amber-200',
                    )}
                  >
                    {autoRunStepLabel(project.active_run_step)} · {projectProgress}%
                  </span>
                </button>
              );
            })}
            {activeProjectRuns.length > 4 ? (
              <p className="px-1 text-xs text-muted-foreground">
                +{activeProjectRuns.length - 4} prompt khác đang active
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="mt-3 space-y-2">
        {groupedProjects.seriesGroups.map((group) => (
          <div
            key={group.series?.id ?? group.projects[0]?.series_id}
            className="space-y-2 rounded-lg border border-border/70 bg-muted/15 p-2"
          >
            <div className="flex items-center justify-between gap-2 px-1 text-xs font-medium uppercase text-muted-foreground">
              <span className="min-w-0 truncate">
                {group.series?.title ?? group.projects[0]?.series_title ?? 'Series'}
              </span>
              <span>{group.projects.length} tập</span>
            </div>
            {group.projects
              .slice()
              .sort((a, b) => (a.episode_number ?? 0) - (b.episode_number ?? 0))
              .map(renderRecentProject)}
            <Button
              size="sm"
              variant="outline"
              className="w-full"
              onClick={() => {
                const seriesId = group.series?.id ?? group.projects[0]?.series_id ?? '';
                openEpisodeDialog(seriesId);
              }}
            >
              <Plus className="h-4 w-4" />
              Tạo tập mới
            </Button>
          </div>
        ))}
        {groupedProjects.standalone.length ? (
          <div className="space-y-2">
            <p className="px-1 text-xs font-medium uppercase text-muted-foreground">Dự án lẻ</p>
            {groupedProjects.standalone.slice(0, 12).map(renderRecentProject)}
          </div>
        ) : null}
        {!projectsQuery.data?.length && (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Chưa có dự án nào.
          </div>
        )}
      </div>
    </section>
  );

  const renderVideoSettingsPanel = (className?: string) => (
    <div className={cn('rounded-lg border border-border/70 bg-background/70 p-4', className)}>
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
        Thiết lập video mới
      </p>
      <div className="mt-4 grid gap-4">
        <FieldBlock
          label="Mục đích video"
          help="Ảnh hưởng tới ngôn ngữ gợi ý, giọng, kiểu thoại, lời kể, phụ đề và phong cách kịch bản."
        >
          <select
            value={form.videoPurpose}
            onChange={(event) => handleVideoPurposeChange(event.target.value as VideoPurpose)}
            disabled={saveProjectPurposeSettings.isPending}
            className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
          >
            {VIDEO_PURPOSE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </FieldBlock>
        <div className="grid gap-2 border-y border-border/70 py-3 text-xs leading-relaxed">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-foreground">{selectedPurposeOption.label}</span>
            <span className="shrink-0 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
              gợi ý {videoLanguageLabel(selectedPurposeOption.recommendedTargetLanguage)}
            </span>
          </div>
          <p className="text-muted-foreground">{selectedPurposeOption.description}</p>
          <div className="grid gap-1 text-muted-foreground sm:grid-cols-2 xl:grid-cols-1">
            <span>
              Giọng:{' '}
              {voiceCompatibilityWarning ??
                (selectedVoiceProfile
                  ? 'hồ sơ hiện tại phù hợp với lựa chọn đang hiển thị.'
                  : 'chưa chọn hồ sơ giọng.')}
            </span>
            <span>
              Thoại: {dialogueModeLabel(form.dialogueMode)} ·{' '}
              {narrationDensityLabel(form.narrationDensity)}
            </span>
            <span>Phụ đề: {selectedPurposeOption.subtitle}</span>
            <span>CTA: {callToActionStyleLabel(form.callToActionStyle)}</span>
            <span>Sắc thái: {selectedPurposeOption.tone}</span>
          </div>
        </div>
        <FieldBlock
          label="Ngôn ngữ video"
          help="Đây là ngôn ngữ cuối cùng cho giọng đọc, lời kể, phụ đề và chữ người xem đọc. Có thể chỉnh lại sau khi chọn mục đích video."
        >
          <select
            value={form.targetLanguage}
            onChange={(event) =>
              updatePurposeSettings({
                targetLanguage: event.target.value as VideoLanguage,
              })
            }
            disabled={saveProjectPurposeSettings.isPending}
            className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
          >
            <option value="en">Tiếng Anh</option>
            <option value="vi">Tiếng Việt</option>
          </select>
        </FieldBlock>
        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-3">
          <FieldBlock label="Mode thoại">
            <select
              value={form.dialogueMode}
              onChange={(event) =>
                updatePurposeSettings({
                  dialogueMode: event.target.value as DialogueMode,
                })
              }
              disabled={saveProjectPurposeSettings.isPending}
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            >
              <option value="voiceover">Thuyết minh</option>
              <option value="character_lines">Nhân vật nói</option>
              <option value="mixed">Kết hợp</option>
            </select>
          </FieldBlock>
          <FieldBlock label="Mật độ thoại">
            <select
              value={form.narrationDensity}
              onChange={(event) =>
                updatePurposeSettings({
                  narrationDensity: event.target.value as NarrationDensity,
                })
              }
              disabled={saveProjectPurposeSettings.isPending}
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            >
              <option value="light">Ít thoại</option>
              <option value="balanced">Vừa phải</option>
              <option value="dense">Dày thoại</option>
            </select>
          </FieldBlock>
          <FieldBlock label="CTA">
            <select
              value={form.callToActionStyle}
              onChange={(event) =>
                updatePurposeSettings({
                  callToActionStyle: event.target.value as CallToActionStyle,
                })
              }
              disabled={saveProjectPurposeSettings.isPending}
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            >
              <option value="none">Không</option>
              <option value="soft">Nhẹ nhàng</option>
              <option value="direct">Trực tiếp</option>
              <option value="urgent">Khẩn cấp</option>
            </select>
          </FieldBlock>
        </div>
        <div className="grid min-w-0 gap-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-foreground">Cách chạy</span>
            <span className="truncate text-[11px] text-muted-foreground">
              {creationMode === 'quick' ? 'Tự chạy sau khi tạo' : 'Tự bấm từng bước'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
            {[
              { mode: 'quick' as const, label: 'Dựng nhanh' },
              { mode: 'manual' as const, label: 'Thủ công' },
            ].map((item) => (
              <button
                key={item.mode}
                type="button"
                aria-pressed={creationMode === item.mode}
                disabled={createProject.isPending}
                onClick={() => setCreationMode(item.mode)}
                className={cn(
                  'h-8 min-w-0 rounded-md px-2 text-center text-sm font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60',
                  creationMode === item.mode
                    ? 'bg-foreground text-background shadow-sm'
                    : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
                )}
              >
                <span className="block truncate">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
        {creationMode === 'quick' ? (
          <div className="grid gap-2 border-t border-border/70 pt-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-foreground">Mức tự động</span>
              <span className="truncate text-[11px] text-muted-foreground">
                {autoMode === 'review_gated' ? 'Dừng để duyệt' : 'Tự chạy hết'}
              </span>
            </div>
            <div className="grid gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
              {[
                {
                  mode: 'review_gated' as const,
                  label: 'Duyệt từng chặng',
                  helper: 'Dừng ở kịch bản và prompt',
                },
                {
                  mode: 'full_auto' as const,
                  label: 'Tự chạy hết',
                  helper: 'Tự duyệt bước giữa',
                },
              ].map((item) => (
                <button
                  key={item.mode}
                  type="button"
                  aria-pressed={autoMode === item.mode}
                  disabled={createProject.isPending}
                  onClick={() => setAutoMode(item.mode)}
                  className={cn(
                    'grid min-h-11 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md px-2.5 py-2 text-left transition active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60',
                    autoMode === item.mode
                      ? 'bg-foreground text-background shadow-sm'
                      : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold leading-tight">
                      {item.label}
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] leading-snug opacity-75">
                      {item.helper}
                    </span>
                  </span>
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full border border-current/35',
                      autoMode === item.mode ? 'bg-current' : 'bg-transparent',
                    )}
                  />
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {creationMode === 'quick' ? (
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium">Đầu ra auto-run</span>
              <span className="truncate text-[11px] text-muted-foreground">
                {autoMaterialTarget === 'video_clips'
                  ? 'Veo + voice/SRT + MP4'
                  : autoMaterialTarget === 'full_materials'
                    ? 'Voice + phụ đề khớp timing'
                    : 'Chỉ prompt, upload ảnh ngay'}
              </span>
            </div>
            <div className="grid gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
              {[
                {
                  target: 'video_clips' as const,
                  label: 'Tạo MP4 bằng Veo',
                  helper: 'Prompt, gửi Veo, tải clip, tạo voice/SRT và render MP4',
                  icon: Clapperboard,
                },
                {
                  target: 'full_materials' as const,
                  label: 'Tạo voice + phụ đề',
                  helper: 'Prompt, voice và SRT theo cue audio',
                  icon: Mic2,
                },
                {
                  target: 'prompts_only' as const,
                  label: 'Chỉ prompt video',
                  helper: 'Bỏ qua voice/SRT để upload ảnh ngay',
                  icon: FileText,
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.target}
                    type="button"
                    aria-pressed={autoMaterialTarget === item.target}
                    disabled={createProject.isPending}
                    onClick={() => setAutoMaterialTarget(item.target)}
                    className={cn(
                      'grid min-h-11 min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-md px-2.5 py-2 text-left transition active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60',
                      autoMaterialTarget === item.target
                        ? 'bg-foreground text-background shadow-sm'
                        : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold leading-tight">
                        {item.label}
                      </span>
                      <span className="mt-0.5 block text-[11px] leading-snug opacity-75">
                        {item.helper}
                      </span>
                    </span>
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full border border-current/35',
                        autoMaterialTarget === item.target ? 'bg-current' : 'bg-transparent',
                      )}
                    />
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
        <div className="grid grid-cols-3 gap-3">
          <FieldBlock label="Số prompt">
            <input
              type="number"
              min={1}
              max={100}
              value={form.promptSegmentCount}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  promptSegmentCount: Number(event.target.value),
                }))
              }
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            />
          </FieldBlock>
          <FieldBlock label="Giây/prompt">
            <input
              type="number"
              min={3}
              max={30}
              value={form.promptSegmentDuration}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  promptSegmentDuration: Number(event.target.value),
                }))
              }
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            />
          </FieldBlock>
          <FieldBlock label="Cảnh nhỏ">
            <input
              type="number"
              min={1}
              max={5}
              value={form.microScenesPerPrompt}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  microScenesPerPrompt: Number(event.target.value),
                }))
              }
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            />
          </FieldBlock>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FieldBlock label="Tỷ lệ">
            <select
              value={form.aspectRatio}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  aspectRatio: event.target.value as AspectRatio,
                }))
              }
              className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
            >
              <option value="9:16">9:16 ( dọc )</option>
              <option value="16:9">16:9 ( ngang )</option>
              <option value="1:1">1:1</option>
            </select>
          </FieldBlock>
        </div>
        <div className="grid min-w-0 gap-2 rounded-lg border border-border/70 bg-muted/20 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-foreground">Prompt segment</span>
            <span className="rounded-full border border-border bg-background px-2 py-0.5 text-xs font-medium text-foreground">
              {promptSegmentCount} prompt
            </span>
          </div>
          <span className="text-xs leading-relaxed text-muted-foreground">
            {promptSegmentCount} prompt x {promptSegmentDuration}s = {derivedTotalDuration}s;{' '}
            {promptSegmentCount} x {microScenesPerPrompt} = {derivedMicroSceneCount} cảnh nhỏ. Mỗi
            cảnh nhỏ khoảng {formatSeconds(secondsPerMicroScene)}s.
          </span>
          {promptConfigError ? (
            <span className="text-xs leading-relaxed text-destructive">{promptConfigError}</span>
          ) : null}
        </div>
        <div className={cn('rounded-lg border p-3 text-sm', statusTone(providerReady))}>
          <div className="flex items-start gap-2">
            {providerReady ? (
              <Check className="mt-0.5 h-4 w-4" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4" />
            )}
            <div>
              <p className="font-medium">
                {providerQuery.data?.message ?? 'Đang kiểm tra Codex CLI.'}
              </p>
              <p className="mt-1 text-xs opacity-80">
                {providerQuery.data?.request_id ?? 'Chưa có request ID.'}
              </p>
            </div>
          </div>
        </div>
        <Button
          type="button"
          onClick={() => createProject.mutate()}
          disabled={!canCreateProject || createProject.isPending}
          className="w-full active:translate-y-[1px]"
        >
          {createProject.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : creationMode === 'quick' ? (
            <Play className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          {creationMode === 'quick' ? 'Tạo và dựng nhanh' : 'Tạo dự án thủ công'}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="h-full min-h-0 overflow-y-auto bg-background py-3 md:py-4 xl:overflow-hidden">
      <div
        className={cn(
          'relative grid min-h-full w-full grid-cols-1 gap-4 transition-[grid-template-columns] duration-200 xl:h-full xl:min-h-0 xl:overflow-hidden',
          sidePanelOpen
            ? 'xl:grid-cols-[320px_minmax(0,1fr)_300px]'
            : 'xl:grid-cols-[minmax(0,1fr)_300px]',
        )}
      >
        <section
          className={cn(
            'order-2 min-w-0 space-y-4 xl:h-full xl:min-h-0 xl:overflow-y-auto xl:overscroll-contain xl:pb-4 xl:pr-1 [scrollbar-gutter:stable]',
            sidePanelOpen ? null : 'xl:pl-14',
          )}
        >
          <section className="rounded-lg border border-border/80 bg-card/45 p-4 shadow-[0_18px_42px_-32px_rgba(0,0,0,0.45)] sm:p-5 md:p-6">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-1">
              <div className="min-w-0">
                <div className="flex min-w-0 flex-col items-start gap-3 sm:flex-row">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-foreground text-background">
                    <Clapperboard className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h1 className="max-w-full break-words text-lg font-semibold leading-tight tracking-tight sm:text-2xl md:text-3xl">
                      <span>Dự án prompt video</span>
                    </h1>
                    <p className="mt-1 max-w-[70ch] text-sm leading-relaxed text-muted-foreground">
                      <span className="hidden sm:inline">
                        Nhập tiếng Việt, AI phát triển kịch bản, chia video thành prompt segment
                        theo cấu hình và giữ continuity giữa các segment.
                      </span>
                      <span className="sm:hidden">
                        Nhập tiếng Việt. AI tạo prompt segment liền mạch.
                      </span>
                    </p>
                  </div>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <FieldBlock
                    label="Tên dự án"
                    help="Có thể để trống, hệ thống sẽ lấy từ ý tưởng chính."
                  >
                    <input
                      value={form.title}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, title: event.target.value }))
                      }
                      className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      placeholder="Ví dụ: Cú trở lại ở World Cup"
                    />
                  </FieldBlock>
                  <FieldBlock label="Hồ sơ giọng" help={`Đang chọn: ${selectedVoiceName}`}>
                    <select
                      value={form.voiceProfileId}
                      onChange={(event) => handleVoiceProfileChange(event.target.value)}
                      disabled={saveProjectVoice.isPending}
                      className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                    >
                      <option value="">Chọn sau</option>
                      {profiles?.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                        </option>
                      ))}
                    </select>
                  </FieldBlock>
                </div>
                {voiceCompatibilityWarning ? (
                  <div className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-800 dark:text-amber-200">
                    {voiceCompatibilityWarning}
                  </div>
                ) : null}

                <div className="mt-5 grid gap-4">
                  {form.sources.map((source, index) => (
                    <FieldBlock key={source.block_type} label={source.label} help={source.helper}>
                      <textarea
                        value={source.content}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            sources: current.sources.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, content: event.target.value } : item,
                            ),
                          }))
                        }
                        className="min-h-24 w-full min-w-0 rounded-lg border border-input bg-background px-3 py-3 text-sm leading-relaxed outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                      />
                    </FieldBlock>
                  ))}
                  <FieldBlock
                    label="Phong cách hình ảnh"
                    help="Áp dụng cho toàn bộ video: chất liệu hình ảnh, ánh sáng, màu sắc, camera và nhịp animation."
                  >
                    <textarea
                      value={form.visualStyle}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, visualStyle: event.target.value }))
                      }
                      className="min-h-24 w-full min-w-0 rounded-lg border border-input bg-background px-3 py-3 text-sm leading-relaxed outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                    />
                  </FieldBlock>
                </div>
              </div>

              <div className="xl:hidden">{renderVideoSettingsPanel()}</div>
            </div>
          </section>

          {operationError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              {getErrorMessage(operationError)}
            </div>
          )}
          {notice && (
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">
              {notice}
            </div>
          )}

          {selectedProject ? (
            <section
              className={cn(
                'rounded-lg border p-4 text-sm',
                selectedSegmentCountMismatch
                  ? 'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100'
                  : 'border-border/80 bg-card/40',
              )}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] opacity-70">
                    Dự án đang chọn
                  </p>
                  <p className="mt-1 truncate text-base font-semibold">{selectedProject.title}</p>
                  <p className="mt-1 text-xs opacity-75">
                    {selectedProject.series_id
                      ? `${selectedSeries?.title || selectedProject.series_title || 'Series'} · ${episodeDisplay(selectedProject)}`
                      : 'Project lẻ'}
                    {' · '}
                    {selectedProject.prompt_segment_count
                      ? 'Cấu hình prompt segment trực tiếp'
                      : 'Project legacy hoặc chưa có cấu hình prompt segment trực tiếp'}
                  </p>
                </div>
                <div className="flex min-w-0 flex-col gap-3 md:items-end">
                  <div className="flex flex-wrap gap-2 text-xs md:justify-end">
                    <span className="rounded-full border border-current/20 bg-background/40 px-2 py-1">
                      {shots.length} segment đã lưu
                    </span>
                    {selectedPromptCount ? (
                      <span className="rounded-full border border-current/20 bg-background/40 px-2 py-1">
                        {selectedPromptCount} prompt cấu hình
                      </span>
                    ) : null}
                    <span className="rounded-full border border-current/20 bg-background/40 px-2 py-1">
                      {selectedPromptDuration}s/prompt
                    </span>
                    <span className="rounded-full border border-current/20 bg-background/40 px-2 py-1">
                      {selectedMicroScenesPerPrompt} cảnh nhỏ/prompt
                    </span>
                    {selectedTotalMicroScenes ? (
                      <span className="rounded-full border border-current/20 bg-background/40 px-2 py-1">
                        {selectedTotalMicroScenes} cảnh nhỏ
                      </span>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2 md:justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={resetGeneratedData.isPending || projectPlanningBusy}
                      onClick={() => resetGeneratedData.mutate(selectedProject)}
                    >
                      {resetGeneratedData.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Xoá dữ liệu đã tạo
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={deleteProject.isPending || projectPlanningBusy}
                      onClick={() => deleteProject.mutate(selectedProject)}
                    >
                      {deleteProject.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                      Xoá project
                    </Button>
                  </div>
                </div>
              </div>
              {selectedSegmentCountMismatch ? (
                <p className="mt-3 text-xs leading-relaxed opacity-85">
                  Dữ liệu đang lệch: project cấu hình {selectedProject.prompt_segment_count} prompt
                  nhưng DB còn {shots.length} segment đã lưu. Tạo lại segment breakdown sẽ thay phần
                  segment chưa khóa bằng cấu trúc mới.
                </p>
              ) : null}
            </section>
          ) : null}

          {selectedProject ? (
            <section className="rounded-lg border border-border/80 bg-card/40 p-5">
              <div className="flex items-center justify-between gap-3 border-b border-border/70 pb-3">
                <StepHeader
                  icon={FileText}
                  title="Nguồn nội dung"
                  meta={`${selectedProject.source_blocks.length} đoạn đang lưu`}
                />
              </div>
              <div className="mt-4 space-y-3">
                {selectedProject.source_blocks.length ? (
                  selectedProject.source_blocks.map((block) => (
                    <div
                      key={block.id}
                      className="grid gap-3 rounded-lg border border-border/70 bg-background/70 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-medium uppercase text-muted-foreground">
                          #{block.sort_order} · {block.block_type}
                        </p>
                        <p className="mt-2 line-clamp-4 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/85">
                          {block.content}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={deleteSourceBlock.isPending || projectPlanningBusy}
                        onClick={() => deleteSourceBlock.mutate(block)}
                      >
                        {deleteSourceBlock.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        Xoá đoạn
                      </Button>
                    </div>
                  ))
                ) : (
                  <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                    Dự án chưa có khối nguồn.
                  </div>
                )}
              </div>
            </section>
          ) : null}

          {selectedProject ? (
            <section className="rounded-lg border border-border/80 bg-card/40 p-5">
              <div className="flex flex-col gap-3 border-b border-border/70 pb-3 md:flex-row md:items-center md:justify-between">
                <StepHeader
                  icon={Sparkles}
                  title="Auto tạo nguyên liệu"
                  meta={
                    autoMaterialTarget === 'video_clips'
                      ? 'Prompt video, Veo, voice/SRT và MP4 hoàn chỉnh'
                      : autoMaterialTarget === 'prompts_only'
                        ? 'Prompt video để upload ảnh hoặc chạy Gemini'
                        : 'Prompt video, giọng đọc và phụ đề .srt khớp timing'
                  }
                />
                {latestAutoRun ? (
                  <span
                    className={cn(
                      'inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium',
                      latestAutoRun.status === 'completed'
                        ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                        : null,
                      ['queued', 'running', 'waiting_planning', 'waiting_voice', 'waiting_clips', 'waiting_render'].includes(
                        latestAutoRun.status,
                      )
                        ? 'border-sky-500/25 bg-sky-500/10 text-sky-700 dark:text-sky-300'
                        : null,
                      ['needs_review', 'needs_input'].includes(latestAutoRun.status)
                        ? 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200'
                        : null,
                      ['failed', 'cancelled'].includes(latestAutoRun.status)
                        ? 'border-destructive/25 bg-destructive/10 text-destructive'
                        : null,
                    )}
                  >
                    {autoRunQuery.isFetching && isAutoRunActive(latestAutoRun) ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : null}
                    {autoRunStatusLabel(latestAutoRun)}
                  </span>
                ) : null}
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
                <div className="grid gap-3">
                  {planningActive ? (
                    <div className="rounded-lg border border-sky-500/25 bg-sky-500/10 p-3 text-sm text-sky-800 dark:text-sky-200">
                      <div className="flex items-start gap-2">
                        <Loader2 className="mt-0.5 h-4 w-4 animate-spin" />
                        <div>
                          <p className="font-medium">Đang chạy AI planning</p>
                          <p className="mt-1 text-xs opacity-80">{planningBlockedMessage}</p>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  <div className="grid gap-3 sm:grid-cols-2">
                    {[
                      {
                        mode: 'review_gated' as const,
                        label: 'Duyệt từng chặng',
                        helper: 'Dừng ở kịch bản và prompt',
                      },
                      {
                        mode: 'full_auto' as const,
                        label: 'Tự chạy hết',
                        helper: 'Tự duyệt bước giữa',
                      },
                    ].map((item) => (
                      <button
                        key={item.mode}
                        type="button"
                        aria-pressed={autoMode === item.mode}
                        disabled={autoRunBlocking || planningActive || startAutoRun.isPending}
                        onClick={() => setAutoMode(item.mode)}
                        className={cn(
                          'min-h-20 rounded-lg border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60',
                          autoMode === item.mode
                            ? 'border-foreground/35 bg-foreground text-background'
                            : 'border-border bg-background/70 hover:bg-muted/50',
                        )}
                      >
                        <span className="block text-sm font-semibold">{item.label}</span>
                        <span className="mt-1 block text-xs opacity-75">{item.helper}</span>
                      </button>
                    ))}
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    {[
                      {
                        target: 'video_clips' as const,
                        label: 'Tạo MP4 bằng Veo',
                        helper: 'Tạo prompt, gửi Veo, tải clip, tạo voice/SRT và render MP4.',
                        icon: Clapperboard,
                      },
                      {
                        target: 'full_materials' as const,
                        label: 'Tạo voice + phụ đề',
                        helper:
                          'Tạo prompt, voice và .srt chia cue theo audio; render sẽ dùng karaoke vàng.',
                        icon: Mic2,
                      },
                      {
                        target: 'prompts_only' as const,
                        label: 'Chỉ prompt video',
                        helper: 'Bỏ qua voice/SRT để upload ảnh ngay',
                        icon: FileText,
                      },
                    ].map((item) => {
                      const Icon = item.icon;
                      return (
                        <button
                          key={item.target}
                          type="button"
                          aria-pressed={autoMaterialTarget === item.target}
                          disabled={autoRunBlocking || planningActive || startAutoRun.isPending}
                          onClick={() => setAutoMaterialTarget(item.target)}
                          className={cn(
                            'grid min-h-20 grid-cols-[auto_minmax(0,1fr)] items-start gap-3 rounded-lg border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60',
                            autoMaterialTarget === item.target
                              ? 'border-foreground/35 bg-foreground text-background'
                              : 'border-border bg-background/70 hover:bg-muted/50',
                          )}
                        >
                          <Icon className="mt-0.5 h-4 w-4" />
                          <span className="min-w-0">
                            <span className="block text-sm font-semibold">{item.label}</span>
                            <span className="mt-1 block text-xs opacity-75">{item.helper}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="grid content-start gap-3 rounded-lg border border-border/70 bg-background/70 p-4">
                  <Button
                    type="button"
                    disabled={
                      !activeProjectId ||
                      autoRunBlocking ||
                      planningActive ||
                      startAutoRun.isPending
                    }
                    onClick={() => startAutoRun.mutate()}
                    className="w-full active:translate-y-[1px]"
                  >
                    {startAutoRun.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Auto chạy
                  </Button>
                </div>
              </div>

              {latestAutoRun ? (
                <div className="space-y-4">
                  <AutoRunProgressPanel
                    run={latestAutoRun}
                    isFetching={autoRunQuery.isFetching}
                    cancelPending={cancelAutoRun.isPending}
                    onCancel={() => cancelAutoRun.mutate()}
                  />

                  {latestAutoRun.status === 'needs_review' ? (
                    <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-100">
                      <p className="font-medium">
                        Cần duyệt {autoRunReviewLabel(latestAutoRun.review_stage)}.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          disabled={continueAutoRun.isPending}
                          onClick={() => continueAutoRun.mutate(true)}
                        >
                          {continueAutoRun.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Check className="h-4 w-4" />
                          )}
                          Tiếp tục sau khi duyệt
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={continueAutoRun.isPending}
                          onClick={() => continueAutoRun.mutate(false)}
                        >
                          <X className="h-4 w-4" />
                          Không duyệt
                        </Button>
                      </div>
                    </div>
                  ) : null}

                  {['needs_input', 'failed'].includes(latestAutoRun.status) ? (
                    <div className="rounded-lg border border-destructive/25 bg-destructive/10 p-4 text-sm text-destructive">
                      <p className="font-medium">
                        {latestAutoRun.failure_reason || 'Auto-run cần xử lý trước khi chạy tiếp.'}
                      </p>
                      {latestAutoRun.error_code ? (
                        <p className="mt-1 text-xs opacity-80">{latestAutoRun.error_code}</p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          disabled={retryAutoRun.isPending}
                          onClick={() => retryAutoRun.mutate()}
                        >
                          {retryAutoRun.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                          Retry
                        </Button>
                        {latestAutoRun.status === 'needs_input' ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={cancelAutoRun.isPending}
                            onClick={() => cancelAutoRun.mutate()}
                          >
                            <X className="h-4 w-4" />
                            Hủy
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  {latestAutoRun.status === 'completed' ? (
                    <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">
                      {latestAutoRun.material_target === 'prompts_only'
                        ? 'Prompt video đã sẵn sàng. Bạn có thể upload ảnh hoặc copy prompt sang Gemini để tạo thoại theo prompt.'
                        : latestAutoRun.material_target === 'video_clips'
                          ? 'MP4 đã render xong. Bạn có thể tải video ở panel render hoặc kiểm tra clip trong panel Veo.'
                        : 'Nguyên liệu lõi đã sẵn sàng. Render MP4 vẫn dùng panel dựng riêng.'}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}

          <section className="rounded-lg border border-border/80 bg-card/40 p-5">
            <div className="flex flex-col gap-3 border-b border-border/70 pb-3 md:flex-row md:items-center md:justify-between">
              <StepHeader
                icon={BookOpen}
                title="Story, continuity và kịch bản"
                meta="Phải duyệt phần này trước khi tạo shot"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={
                    !activeProjectId ||
                    !providerReady ||
                    developStory.isPending ||
                    projectPlanningBusy
                  }
                  onClick={() => developStory.mutate(false)}
                >
                  {developStory.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  AI phát triển kịch bản
                </Button>
                <Button
                  variant="outline"
                  disabled={!activeProjectId || developStory.isPending || projectPlanningBusy}
                  onClick={() => developStory.mutate(true)}
                >
                  <RefreshCw className="h-4 w-4" />
                  Viết lại
                </Button>
                <Button
                  disabled={
                    !selectedProject?.story_strategy ||
                    approveStory.isPending ||
                    projectPlanningBusy
                  }
                  onClick={() => approveStory.mutate(!selectedProject?.story_approved)}
                >
                  <Check className="h-4 w-4" />
                  {selectedProject?.story_approved ? 'Bỏ duyệt' : 'Duyệt kịch bản'}
                </Button>
              </div>
            </div>
            <div className="mt-4">
              {projectQuery.isLoading ? (
                <SkeletonRows />
              ) : !selectedProject ? (
                <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                  Chưa có dự án. Nhập nguồn nội dung rồi bấm Tạo dự án phase 2.
                </div>
              ) : !selectedProject.story_strategy ? (
                <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                  Dự án đã có nguồn nội dung. Bấm AI phát triển kịch bản để tạo chiến lược nội dung
                  và ghi chú nhất quán.
                </div>
              ) : (
                <div className="grid gap-3 lg:grid-cols-3">
                  <TextPanel
                    title="Chiến lược kịch bản"
                    description={`Bản tiếng Việt để duyệt; nếu video cuối là ${activeVideoLanguageLabel}, phần sản xuất vẫn theo ngôn ngữ video.`}
                    value={selectedProject.story_strategy}
                    empty="Chưa có chiến lược kịch bản."
                  />
                  <TextPanel
                    title="Ghi chú nhất quán"
                    description="Bản tiếng Việt giúp kiểm tra nhân vật, bối cảnh, phong cách và tính nhất quán."
                    value={selectedProject.continuity_bible}
                    empty="Chưa có continuity bible."
                  />
                  <TextPanel
                    title="Kịch bản chi tiết"
                    description={`Bản đọc duyệt bằng tiếng Việt, kèm nội dung sản xuất theo ${activeVideoLanguageLabel} nếu khác.`}
                    value={selectedProject.detailed_script}
                    empty="Chưa có kịch bản."
                  />
                  <CreativeDirectionSummary project={selectedProject} />
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-border/80 bg-card/40 p-5">
            <div className="flex flex-col gap-3 border-b border-border/70 pb-3 md:flex-row md:items-center md:justify-between">
              <StepHeader
                icon={Film}
                title="Prompt segment"
                meta={`${shots.length} segment đã lưu${selectedPromptCount ? ` / ${selectedPromptCount} prompt cấu hình` : ''} · mỗi prompt ~${selectedPromptDuration}s, gồm ${selectedMicroScenesPerPrompt} cảnh nhỏ`}
              />
              <Button
                disabled={
                  !selectedProject?.story_approved ||
                  !!promptConfigError ||
                  generateShots.isPending ||
                  projectPlanningBusy
                }
                onClick={() => generateShots.mutate()}
              >
                {generateShots.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Film className="h-4 w-4" />
                )}
                Tạo segment breakdown
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              {shots.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                  Chưa có segment. Hãy duyệt kịch bản rồi tạo segment breakdown.
                </div>
              ) : (
                shots.map((shot) => {
                  const timelineLabel = segmentTimelineLabel(selectedProject, shot.shot_order);
                  const promptDuration = projectPromptDuration(selectedProject);
                  const microScenes = shotMicroScenes(shot);
                  const microSceneCount =
                    selectedProject?.micro_scenes_per_prompt || microScenes.length || 0;
                  return (
                    <div
                      key={shot.id}
                      className="rounded-lg border border-border/75 bg-background/70 p-4"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold">{shotLabel(shot)}</p>
                            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                              {usesPromptSegments
                                ? `prompt ${promptDuration}s`
                                : `${shot.duration_seconds ?? 3}s`}
                            </span>
                            {timelineLabel ? (
                              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                                {timelineLabel}
                              </span>
                            ) : null}
                            {usesPromptSegments ? (
                              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                                {microSceneCount || 'n'} cảnh nhỏ
                              </span>
                            ) : null}
                            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                              prompt: {shot.prompt_status}
                            </span>
                            {shot.locked && (
                              <span className="rounded-full border border-emerald-500/30 px-2 py-0.5 text-xs text-emerald-700 dark:text-emerald-300">
                                đã khóa
                              </span>
                            )}
                          </div>
                          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Bản tiếng Việt để duyệt segment
                          </p>
                          <p className="mt-1 text-sm leading-relaxed text-foreground/85">
                            {shot.vietnamese_description ||
                              'Chưa có bản tiếng Việt giải thích cảnh nhỏ.'}
                          </p>
                          {microScenes.length > 0 ? (
                            <div className="mt-3 grid gap-2 rounded-lg border border-border/60 bg-muted/20 p-3 text-xs text-muted-foreground">
                              {microScenes.map((microScene) => (
                                <div key={`${shot.id}-${microScene.order}`}>
                                  <span className="font-medium text-foreground/80">
                                    {formatSeconds(microScene.start_seconds)}-
                                    {formatSeconds(microScene.end_seconds)}s:{' '}
                                  </span>
                                  <span>
                                    {microScene.description_vi || microScene.visual_action}
                                  </span>
                                  {microScene.camera_note ? (
                                    <span> · {microScene.camera_note}</span>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Lời kể theo ngôn ngữ video ({activeVideoLanguageLabel})
                          </p>
                          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                            {shot.english_narration || 'Segment không có lời kể riêng.'}
                          </p>
                          <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                            <span>Góc máy: {shot.camera_angle || 'chưa có'}</span>
                            <span>Cỡ cảnh: {shot.framing || 'chưa có'}</span>
                            <span>Camera: {shot.camera_motion || 'chưa có'}</span>
                          </div>
                          <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                            <span>
                              Retention: {metadataText(shot.retention_json, ['retention_role'])}
                            </span>
                            <span>
                              Chuyển cảnh: {metadataText(shot.transition_json, ['transition_type'])}
                            </span>
                            <span>
                              SFX:{' '}
                              {metadataText(shot.sound_design_json, ['sound_cues', 'music_mood'])}
                            </span>
                          </div>
                          {qualityWarnings(shot.retainability_quality_check).length ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {qualityWarnings(shot.retainability_quality_check).map((item) => (
                                <span
                                  key={item}
                                  className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-800 dark:text-amber-200"
                                >
                                  {item}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={projectPlanningBusy}
                            onClick={() => lockShot.mutate({ shot, locked: !shot.locked })}
                          >
                            {shot.locked ? (
                              <Unlock className="h-4 w-4" />
                            ) : (
                              <Lock className="h-4 w-4" />
                            )}
                            {shot.locked ? 'Mở khóa' : 'Khóa'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={
                              shot.locked || regenerateShot.isPending || projectPlanningBusy
                            }
                            onClick={() => regenerateShot.mutate(shot)}
                          >
                            <RefreshCw className="h-4 w-4" />
                            Tạo lại
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          <section className="rounded-lg border border-border/80 bg-card/40 p-5">
            <div className="flex flex-col gap-3 border-b border-border/70 pb-3 md:flex-row md:items-center md:justify-between">
              <StepHeader
                icon={Sparkles}
                title="Prompt video"
                meta="Prompt gốc để copy, kèm bản giải thích tiếng Việt để đọc hiểu"
              />
              <Button
                variant="outline"
                disabled={!shots.length || generatePrompts.isPending || projectPlanningBusy}
                onClick={() => generatePrompts.mutate()}
              >
                {generatePrompts.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Tạo prompt video
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              {shots.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                  Chưa có segment để tạo prompt video.
                </div>
              ) : (
                shots.map((shot) => {
                  const promptContent = promptByShotId[shot.id];
                  return (
                    <div
                      key={shot.id}
                      className="flex flex-col gap-3 rounded-lg border border-border/75 bg-background/70 p-4"
                    >
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                          <p className="text-sm font-semibold">{shotLabel(shot)}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Trạng thái prompt: {shot.prompt_status}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={shot.prompt_status === 'missing'}
                            onClick={() => copyShotPrompt(shot)}
                          >
                            <Copy className="h-4 w-4" />
                            Copy prompt gốc
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={shot.prompt_status === 'missing'}
                            onClick={() =>
                              saveDownload(
                                apiClient.downloadVideoShotPrompt(shot.project_id, shot.id),
                                ['txt'],
                              )
                            }
                          >
                            <Download className="h-4 w-4" />
                            Tải prompt
                          </Button>
                        </div>
                      </div>
                      {shot.prompt_status !== 'missing' ? (
                        <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Bản giải thích tiếng Việt
                          </p>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground/85">
                            {promptContent?.prompt_explanation_vi?.trim() ||
                              missingPromptExplanationText()}
                          </p>
                          <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                            <span>
                              Retention: {promptContent?.retention_notes?.trim() || 'chưa có'}
                            </span>
                            <span>
                              Chuyển cảnh: {promptContent?.transition_notes?.trim() || 'chưa có'}
                            </span>
                            <span>
                              Âm thanh/SFX: {promptContent?.sound_design_notes?.trim() || 'chưa có'}
                            </span>
                          </div>
                          {promptContent?.content ? (
                            <details className="mt-3 text-sm">
                              <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                                Xem prompt gốc dùng để copy
                              </summary>
                              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs leading-relaxed text-muted-foreground">
                                {promptContent.content}
                              </pre>
                            </details>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          </section>

          <section className="rounded-lg border border-border/80 bg-card/40 p-5">
            <StepHeader
              icon={Mic2}
              title="Voice và phụ đề"
              meta={`Voice hiện tại: ${selectedVoiceName}`}
            />
            <div className="mt-4 space-y-3">
              <div
                className={cn(
                  'rounded-lg border p-4',
                  hasVoiceProfile
                    ? 'border-border/75 bg-background/70'
                    : 'border-amber-500/35 bg-amber-500/10',
                )}
              >
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">Hồ sơ giọng cho dự án này</p>
                    <p className="mt-1 truncate text-sm text-foreground/85">{selectedVoiceName}</p>
                    {hasVoiceProfile ? (
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        Giọng đọc sẽ tạo âm thanh theo ngôn ngữ video: {activeVideoLanguageLabel}.
                      </p>
                    ) : (
                      <p className="mt-1 text-xs leading-relaxed text-destructive">
                        Chưa chọn giọng nên chưa thể bấm Tạo giọng.
                      </p>
                    )}
                  </div>
                  {hasVoiceProfile && !showVoiceSelector ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={saveProjectVoice.isPending}
                      onClick={() => setVoiceSelectorOpen(true)}
                    >
                      <Pencil className="h-4 w-4" />
                      Đổi giọng
                    </Button>
                  ) : null}
                  {saveProjectVoice.isPending ? (
                    <div className="flex h-10 items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Đang lưu giọng
                    </div>
                  ) : null}
                </div>
                {showVoiceSelector ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <FieldBlock
                      label={hasVoiceProfile ? 'Chọn giọng mới' : 'Hồ sơ giọng'}
                      help={
                        hasVoiceProfile
                          ? 'Chỉ đổi khi muốn thay giọng cho dự án.'
                          : 'Có thể chọn ở đây hoặc ở phần thiết lập phía trên.'
                      }
                    >
                      <select
                        value={form.voiceProfileId}
                        onChange={(event) => handleVoiceProfileChange(event.target.value)}
                        disabled={saveProjectVoice.isPending}
                        className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                      >
                        <option value="">Chưa chọn giọng</option>
                        {profiles?.map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name}
                          </option>
                        ))}
                      </select>
                    </FieldBlock>
                    {hasVoiceProfile ? (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={saveProjectVoice.isPending}
                        onClick={() => setVoiceSelectorOpen(false)}
                      >
                        <X className="h-4 w-4" />
                        Huỷ
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
              {usesShotNarration ? (
                narratedShots.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                    Các segment hiện chưa có lời kể theo ngôn ngữ video để tạo giọng.
                  </div>
                ) : (
                  narratedShots.map((shot) => (
                    <div
                      key={shot.id}
                      className="flex flex-col gap-3 rounded-lg border border-border/75 bg-background/70 p-4 md:flex-row md:items-center md:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">{shotLabel(shot)}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          giọng: {shot.voice_status} · phụ đề: {shot.subtitle_status}
                        </p>
                        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground/80">
                          {shot.english_narration}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button
                          size="sm"
                          disabled={
                            isShotBusy(shot) ||
                            !hasVoiceProfile ||
                            saveProjectVoice.isPending ||
                            autoRunBusy
                          }
                          title={
                            !hasVoiceProfile
                              ? 'Chọn hồ sơ giọng trước khi tạo giọng đọc.'
                              : undefined
                          }
                          onClick={() => generateShotVoice.mutate(shot)}
                        >
                          {isShotBusy(shot) ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Mic2 className="h-4 w-4" />
                          )}
                          Tạo giọng
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={shot.voice_status !== 'completed'}
                          onClick={() =>
                            toggleVoicePreview(
                              `shot:${shot.id}`,
                              apiClient.getVideoShotVoiceUrl(shot.project_id, shot.id),
                            )
                          }
                        >
                          {playingVoiceKey === `shot:${shot.id}` ? (
                            <Pause className="h-4 w-4" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                          {playingVoiceKey === `shot:${shot.id}` ? 'Dừng nghe' : 'Nghe thử'}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={shot.voice_status !== 'completed'}
                          onClick={() =>
                            saveDownload(
                              apiClient.downloadVideoShotVoice(shot.project_id, shot.id),
                              ['wav', 'mp3'],
                            )
                          }
                        >
                          <Download className="h-4 w-4" />
                          Tải âm thanh
                        </Button>
                      </div>
                    </div>
                  ))
                )
              ) : approvedScenes.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
                  Sau khi AI phát triển kịch bản, cảnh có lời kể theo ngôn ngữ video sẽ xuất hiện ở
                  đây để tạo giọng.
                </div>
              ) : (
                approvedScenes.map((scene) => (
                  <div
                    key={scene.id}
                    className="flex flex-col gap-3 rounded-lg border border-border/75 bg-background/70 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="text-sm font-semibold">
                        Cảnh {String(scene.scene_order).padStart(2, '0')}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        giọng: {scene.no_narration ? 'không lời' : scene.voice_status} · phụ đề:{' '}
                        {scene.subtitle_status}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        disabled={
                          scene.no_narration ||
                          isSceneBusy(scene) ||
                          !hasVoiceProfile ||
                          saveProjectVoice.isPending ||
                          autoRunBusy
                        }
                        title={
                          !hasVoiceProfile ? 'Chọn hồ sơ giọng trước khi tạo giọng đọc.' : undefined
                        }
                        onClick={() => generateSceneVoice.mutate(scene)}
                      >
                        {isSceneBusy(scene) ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Mic2 className="h-4 w-4" />
                        )}
                        Tạo giọng
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={scene.voice_status !== 'completed'}
                        onClick={() =>
                          toggleVoicePreview(
                            `scene:${scene.id}`,
                            apiClient.getVideoSceneVoiceUrl(scene.project_id, scene.id),
                          )
                        }
                      >
                        {playingVoiceKey === `scene:${scene.id}` ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                        {playingVoiceKey === `scene:${scene.id}` ? 'Dừng nghe' : 'Nghe thử'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={scene.voice_status !== 'completed'}
                        onClick={() =>
                          saveDownload(
                            apiClient.downloadVideoSceneVoice(scene.project_id, scene.id),
                            ['wav', 'mp3'],
                          )
                        }
                      >
                        <Download className="h-4 w-4" />
                        Tải âm thanh
                      </Button>
                    </div>
                  </div>
                ))
              )}
              <div className="flex flex-wrap gap-2 pt-2">
                <Button
                  disabled={!activeProjectId || generateSubtitle.isPending || autoRunBusy}
                  onClick={() => generateSubtitle.mutate()}
                >
                  {generateSubtitle.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="h-4 w-4" />
                  )}
                  Tạo phụ đề .srt
                </Button>
                <Button
                  variant="outline"
                  disabled={!activeProjectId || statusQuery.data?.missing_subtitle}
                  onClick={() =>
                    saveDownload(apiClient.downloadVideoSubtitle(activeProjectId!), ['srt'])
                  }
                >
                  <Download className="h-4 w-4" />
                  Tải .srt
                </Button>
              </div>
            </div>
          </section>
        </section>

        <aside className="order-3 hidden min-h-0 xl:block xl:h-full xl:overflow-y-auto xl:overscroll-contain xl:pb-4 xl:pr-1 [scrollbar-gutter:stable]">
          {renderVideoSettingsPanel('bg-card/60')}
        </aside>

        <aside
          className={cn(
            'order-1 space-y-3',
            sidePanelOpen
              ? 'xl:h-full xl:min-h-0 xl:self-stretch xl:overflow-y-auto xl:overscroll-contain xl:pb-4 xl:pr-1 [scrollbar-gutter:stable]'
              : 'xl:absolute xl:left-0 xl:top-0',
          )}
        >
          <div
            className={cn(
              'rounded-lg border border-border/80 bg-card/70 p-2',
              sidePanelOpen ? 'flex items-center justify-between gap-3' : 'flex justify-center',
            )}
          >
            {sidePanelOpen ? (
              <div className="min-w-0 px-2">
                <p className="truncate text-sm font-semibold">Dự án</p>
                <p className="truncate text-xs text-muted-foreground">AI Video Assistant</p>
              </div>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-9 w-9 shrink-0"
              aria-label={sidePanelOpen ? 'Thu gọn panel dự án' : 'Mở panel dự án'}
              title={sidePanelOpen ? 'Thu gọn panel dự án' : 'Mở panel dự án'}
              onClick={() => setSidePanelOpen((open) => !open)}
            >
              {sidePanelOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </Button>
          </div>

          {sidePanelOpen ? (
            <>
              <SystemResourcePanel
                resources={systemResourcesQuery.data}
                loading={systemResourcesQuery.isLoading || systemResourcesQuery.isFetching}
                error={systemResourcesQuery.error}
              />
              {recentProjectsPanel}
              <section className="rounded-lg border border-border/80 bg-card/60 p-5">
                <StepHeader
                  icon={Package}
                  title="Tải nguyên liệu"
                  meta="Checklist trước khi xuất ZIP"
                />
                <div className="mt-4 space-y-3 text-sm">
                  {readinessQuery.isLoading ? (
                    <SkeletonRows />
                  ) : readinessQuery.data ? (
                    <>
                      <div
                        className={cn(
                          'rounded-lg border p-3',
                          statusTone(readinessQuery.data.ready),
                        )}
                      >
                        <p className="font-medium">
                          {readinessQuery.data.ready
                            ? 'Đã đủ điều kiện tạo ZIP.'
                            : 'Chưa đủ điều kiện tạo ZIP.'}
                        </p>
                        {!readinessQuery.data.ready && (
                          <ul className="mt-2 space-y-1 text-xs opacity-85">
                            {readinessQuery.data.missing_reasons.map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <Button
                        className="w-full active:translate-y-[1px]"
                        disabled={
                          !readinessQuery.data.ready || createPackage.isPending || autoRunBusy
                        }
                        onClick={() => createPackage.mutate()}
                      >
                        {createPackage.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Package className="h-4 w-4" />
                        )}
                        Tạo ZIP nguyên liệu
                      </Button>
                      <Button
                        className="w-full active:translate-y-[1px]"
                        variant="outline"
                        disabled={!readinessQuery.data.ready || statusQuery.data?.package_stale}
                        onClick={() =>
                          saveDownload(apiClient.downloadVideoPackage(activeProjectId!), ['zip'])
                        }
                      >
                        <Download className="h-4 w-4" />
                        Tải tất cả
                      </Button>
                    </>
                  ) : (
                    <div className="rounded-lg border border-dashed border-border p-5 text-muted-foreground">
                      Chọn hoặc tạo dự án để xem checklist.
                    </div>
                  )}
                </div>
              </section>

              <AIVideoVeoChromePanel projectId={activeProjectId} shots={shots} onNotice={setNotice} />

              <AIVideoRenderPanel projectId={activeProjectId} shots={shots} onNotice={setNotice} />

              <section className="rounded-lg border border-border/80 bg-card/60 p-5">
                <StepHeader icon={Bug} title="Debug local" meta="Dùng khi cần gửi lỗi để fix" />
                <details className="mt-4 text-sm">
                  <summary className="cursor-pointer rounded-lg border border-border px-3 py-2 text-muted-foreground hover:bg-muted/50">
                    Mở thông tin kỹ thuật
                  </summary>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={copyDebug}
                      disabled={!debugQuery.data}
                    >
                      <Copy className="h-4 w-4" />
                      Copy debug
                    </Button>
                    {selectedProject?.last_request_id && (
                      <span className="rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
                        Request ID: {selectedProject.last_request_id}
                      </span>
                    )}
                  </div>
                  <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
                    {JSON.stringify(
                      {
                        status: statusQuery.data,
                        readiness: readinessQuery.data,
                        debug: debugQuery.data,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </section>

              <section className="rounded-lg border border-border/80 bg-card/60 p-5">
                <StepHeader
                  icon={BookOpen}
                  title="Series Bible"
                  meta="Tuỳ chọn cho video dài tập"
                />
                <div className="mt-4 space-y-3">
                  <select
                    value={editingSeriesId ?? ''}
                    onChange={(event) => {
                      const value = event.target.value || null;
                      setEditingSeriesId(value);
                      setEpisodeDraft((current) => ({ ...current, seriesId: value || '' }));
                      if (!value) setSeriesDraft(emptySeriesDraft);
                    }}
                    className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                  >
                    <option value="">Tạo series mới</option>
                    {seriesQuery.data?.map((series) => (
                      <option key={series.id} value={series.id}>
                        {series.title}
                      </option>
                    ))}
                  </select>
                  <input
                    value={seriesDraft.title}
                    onChange={(event) =>
                      setSeriesDraft((current) => ({ ...current, title: event.target.value }))
                    }
                    className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                    placeholder="Tên series"
                  />
                  {(
                    [
                      ['character_bible', 'Nhân vật cố định'],
                      ['world_bible', 'Bối cảnh/world'],
                      ['style_bible', 'Style hình ảnh'],
                      ['continuity_rules', 'Continuity rules'],
                      ['negative_rules', 'Điều cần tránh'],
                      ['previous_episode_summary', 'Tóm tắt tập trước'],
                    ] as const
                  ).map(([field, placeholder]) => (
                    <textarea
                      key={field}
                      value={seriesDraft[field]}
                      onChange={(event) =>
                        setSeriesDraft((current) => ({ ...current, [field]: event.target.value }))
                      }
                      className="min-h-20 w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm leading-relaxed outline-none focus:border-foreground/40"
                      placeholder={placeholder}
                    />
                  ))}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={saveSeries.isPending || !seriesDraft.title.trim()}
                      onClick={() => saveSeries.mutate()}
                    >
                      {saveSeries.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                      Lưu series
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingSeriesId(null);
                        setSeriesDraft(emptySeriesDraft);
                      }}
                    >
                      <Plus className="h-4 w-4" />
                      Series mới
                    </Button>
                    {selectedProject?.series_id ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          apiClient
                            .updateVideoSeriesSummaryFromProject(selectedProject.id)
                            .then(() => {
                              setNotice('Đã cập nhật tóm tắt tập trước cho series.');
                              invalidateProject();
                            })
                            .catch((error) => setNotice(getErrorMessage(error)))
                        }
                      >
                        <RefreshCw className="h-4 w-4" />
                        Cập nhật summary
                      </Button>
                    ) : null}
                  </div>
                  <div className="border-t border-border/70 pt-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">Tạo tập mới</p>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          Điền thông tin tập trong popup trước khi tạo project.
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openEpisodeDialog(editingSeriesId)}
                      >
                        <Plus className="h-4 w-4" />
                        Tạo tập mới
                      </Button>
                    </div>
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </aside>
        <Dialog
          open={episodeDialogOpen}
          onOpenChange={(nextOpen) => {
            if (createEpisode.isPending) return;
            setEpisodeDialogOpen(nextOpen);
          }}
        >
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>Tạo tập mới</DialogTitle>
              <DialogDescription>
                Chọn series, đặt tên tập và nhập ý tưởng chính để tạo project tập mới.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4">
              <FieldBlock label="Series">
                <select
                  value={episodeDraft.seriesId}
                  onChange={(event) => {
                    const seriesId = event.target.value;
                    setEpisodeDraft((current) => ({ ...current, seriesId }));
                    setEditingSeriesId(seriesId || null);
                  }}
                  className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                >
                  <option value="">Chọn series</option>
                  {seriesQuery.data?.map((series) => (
                    <option key={series.id} value={series.id}>
                      {series.title}
                    </option>
                  ))}
                </select>
              </FieldBlock>
              {episodeDialogSeries ? (
                <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 px-3 py-3 text-xs leading-relaxed text-muted-foreground">
                  <div className="flex items-center justify-between gap-3">
                    <span className="min-w-0 truncate font-medium text-foreground">
                      {episodeDialogSeries.title}
                    </span>
                    <span className="shrink-0 rounded-full border border-border bg-background px-2 py-0.5">
                      Tập {(episodeDialogSeries.latest_episode_number ?? 0) + 1}
                    </span>
                  </div>
                  <span>
                    Dùng cấu hình hiện tại: {videoLanguageLabel(form.targetLanguage)} ·{' '}
                    {promptSegmentCount} prompt x {promptSegmentDuration}s ·{' '}
                    {microScenesPerPrompt} cảnh nhỏ/prompt
                  </span>
                </div>
              ) : null}
              <FieldBlock label="Tên tập" help="Có thể để trống nếu muốn hệ thống tự đặt tên.">
                <input
                  value={episodeDraft.episodeTitle}
                  onChange={(event) =>
                    setEpisodeDraft((current) => ({
                      ...current,
                      episodeTitle: event.target.value,
                    }))
                  }
                  className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40"
                  placeholder="Ví dụ: Tập 02 - Cú rẽ bất ngờ"
                />
              </FieldBlock>
              <FieldBlock
                label="Ý tưởng/source chính"
                help="Nội dung này sẽ thành source block đầu tiên của tập mới."
              >
                <textarea
                  value={episodeDraft.topic}
                  onChange={(event) =>
                    setEpisodeDraft((current) => ({ ...current, topic: event.target.value }))
                  }
                  className="min-h-32 w-full min-w-0 rounded-lg border border-input bg-background px-3 py-3 text-sm leading-relaxed outline-none focus:border-foreground/40"
                  placeholder="Nhập ý tưởng, diễn biến chính, hook hoặc ghi chú cho tập mới"
                />
              </FieldBlock>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEpisodeDialogOpen(false)}
                disabled={createEpisode.isPending}
              >
                Hủy
              </Button>
              <Button
                type="button"
                disabled={
                  createEpisode.isPending || !episodeDraft.seriesId || !episodeDraft.topic.trim()
                }
                onClick={() => createEpisode.mutate()}
              >
                {createEpisode.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Tạo tập mới
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
