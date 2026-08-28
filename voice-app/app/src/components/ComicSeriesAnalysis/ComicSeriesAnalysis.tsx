import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleStop,
  FileText,
  Image as ImageIcon,
  Link as LinkIcon,
  Loader2,
  MapPin,
  Quote,
  RefreshCw,
  Sparkles,
  Trash2,
  Upload,
  Users,
} from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SeriesPickerDialog } from '@/components/SeriesDialogs/SeriesDialogs';
import { apiClient } from '@/lib/api/client';
import { LANGUAGE_OPTIONS } from '@/lib/constants/languages';
import type {
  ComicAnalysisPackage,
  ComicCapabilitiesResponse,
  ComicJobListResponse,
  ComicJobDetail,
  ComicJobSummary,
  CallToActionStyle,
  DialogueMode,
  NarrationDensity,
  SeriesMode,
  StoryEpisodeOutputSettings,
  StoryImageAspectRatio,
  StoryImagePanelMode,
  StoryOutputIntent,
  StoryVideoAspectRatio,
  VideoLanguage,
  VideoPurpose,
  VideoSeriesResponse,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

type ComicHandoffTargetKind = 'new_series' | 'existing_series';
type ComicHandoffSeriesMode = Extract<SeriesMode, 'image_story_only' | 'hybrid'>;

const imageAspectSizes: Record<StoryImageAspectRatio, { width: number; height: number }> = {
  '9:16': { width: 720, height: 1280 },
  '16:9': { width: 1920, height: 1080 },
  '1:1': { width: 1080, height: 1080 },
  '4:5': { width: 1080, height: 1350 },
};
const storyImageAspectOptions = Object.keys(imageAspectSizes) as StoryImageAspectRatio[];
const storyVideoAspectOptions: StoryVideoAspectRatio[] = ['9:16', '16:9', '1:1'];
const DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_COUNT = 6;
const DEFAULT_STORY_VIDEO_PROMPT_SEGMENT_DURATION_SECONDS = 10;
const DEFAULT_STORY_VIDEO_MICRO_SCENES_PER_PROMPT = 4;
const COMIC_JOBS_PAGE_SIZE = 50;
const storyMarketOptions = [
  {
    value: 'viet_nam',
    label: 'Việt Nam',
    helper: 'Kể chuyện, ngôn ngữ và nhịp nội dung theo người xem Việt Nam.',
  },
  {
    value: 'viet_nam_short_vertical',
    label: 'Việt Nam · short dọc',
    helper: 'Tối ưu hook nhanh, nhịp dọc 9:16 cho TikTok/Reels/Shorts tại Việt Nam.',
  },
  {
    value: 'global',
    label: 'Quốc tế',
    helper: 'Cách kể trung tính hơn cho người xem quốc tế.',
  },
  {
    value: 'global_short',
    label: 'Quốc tế · short',
    helper: 'Nhịp nhanh, dễ hiểu cho short-form quốc tế.',
  },
] as const;

function defaultHandoffOutputSettings(): StoryEpisodeOutputSettings {
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

function optionalPositiveInt(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function panelModeLabel(value: StoryImagePanelMode): string {
  return value === 'manual' ? 'Chọn số ảnh' : 'Tự động';
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

const STEP_LABELS: Record<string, string> = {
  validate_source: 'Đang kiểm tra nguồn',
  fetch_html: 'Đang tải trang',
  render_browser: 'Đang render trình duyệt',
  extract_content: 'Đang trích nội dung',
  download_assets: 'Đang tải ảnh',
  normalize_images: 'Đang chuẩn hóa ảnh',
  ocr: 'Đang OCR',
  panel_analysis: 'Sẵn sàng phân tích nội dung truyện',
  character_analysis: 'Đang phân tích nhân vật',
  story_analysis: 'Đang phân tích cốt truyện',
  build_review: 'Đã có kết quả phân tích',
  rewrite_story: 'Đang viết kịch bản tối ưu',
  story_studio_handoff: 'Đang đưa vào Xưởng truyện',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Chờ tải nguồn',
  queued: 'Đang chờ',
  running: 'Đang xử lý',
  source_ready: 'Sẵn sàng phân tích',
  ready_for_review: 'Đã phân tích',
  approved: 'Đã duyệt',
  failed: 'Lỗi',
  cancelled: 'Đã hủy',
  interrupted: 'Bị gián đoạn',
};

const RESULT_COMPLETENESS_LABELS: Record<string, string> = {
  complete: 'Đủ dữ liệu nguồn',
  partial: 'Dữ liệu một phần',
  unavailable: 'Chưa lấy được dữ liệu',
};

const ERROR_MESSAGES: Record<string, string> = {
  COMIC_AUTHENTICATION_REQUIRED: 'Nguồn yêu cầu đăng nhập; hãy upload ảnh hoặc dán nội dung.',
  COMIC_ACCESS_DENIED: 'Máy chủ nguồn từ chối truy cập.',
  COMIC_CAPTCHA_REQUIRED: 'Nguồn yêu cầu CAPTCHA; hãy upload ảnh thay thế.',
  COMIC_NEEDS_UPLOAD: 'Không thể tự động tải nguồn; hãy tải ảnh lên.',
  COMIC_UNSUPPORTED_CONTENT: 'Loại nội dung này chưa được hỗ trợ.',
  COMIC_URL_INVALID: 'URL không hợp lệ; chỉ chấp nhận http hoặc https công khai.',
  COMIC_URL_BLOCKED: 'URL trỏ tới địa chỉ không công khai và đã bị chặn.',
  COMIC_RIGHTS_REQUIRED: 'Chế độ bám canon cần xác nhận quyền sử dụng nguồn.',
  COMIC_VISION_UNAVAILABLE: 'Chưa có công cụ vision khả dụng để đọc hình ảnh.',
};

const COMIC_ACTIVE_STATUSES = new Set(['queued', 'running']);
const COMIC_BLOCKED_STATUSES = new Set(['failed', 'interrupted']);
const COMIC_SOURCE_COLLECTION_STEPS = new Set([
  'validate_source',
  'fetch_html',
  'render_browser',
  'extract_content',
  'download_assets',
]);
const COMIC_ASSET_PREP_STEPS = new Set(['normalize_images', 'ocr']);
const COMIC_ANALYSIS_STEPS = ['panel_analysis', 'character_analysis', 'story_analysis', 'build_review'];

const COMIC_PROGRESS_MILESTONES = [
  {
    step: 'collect_source',
    label: 'Lấy nguồn',
    detail: 'Tải web/tệp, dựng nếu cần và gom ảnh truyện.',
  },
  {
    step: 'prepare_assets',
    label: 'Chuẩn hóa ảnh',
    detail: 'Kiểm tra codec, chuẩn hóa ảnh và đọc chữ OCR.',
  },
  {
    step: 'panel_analysis',
    label: 'Phân tích khung truyện',
    detail: 'Đọc hình ảnh, thoại, chữ, nhân vật và bối cảnh từng khung.',
  },
  {
    step: 'character_analysis',
    label: 'Nhân vật',
    detail: 'Gom nhân vật, quan hệ, địa điểm và bằng chứng quan sát.',
  },
  {
    step: 'story_analysis',
    label: 'Cốt truyện',
    detail: 'Sắp xếp diễn biến, xung đột, hook và điểm chưa chắc.',
  },
  {
    step: 'build_review',
    label: 'Gói xem trước',
    detail: 'Tạo gói xem trước để duyệt trước khi chuyển sang xưởng truyện.',
  },
  {
    step: 'rewrite_story',
    label: 'Kịch bản tối ưu',
    detail: 'Viết lại bản truyện rõ ràng để Xưởng truyện tạo bản nháp.',
  },
  {
    step: 'story_studio_handoff',
    label: 'Xưởng truyện',
    detail: 'Tạo series/tập và chuyển toàn bộ dữ liệu đã duyệt.',
  },
] as const;

type ComicProgressMilestoneStep = (typeof COMIC_PROGRESS_MILESTONES)[number]['step'];
type ComicMilestoneStatus = 'done' | 'current' | 'blocked' | 'pending';

function isComicJobActive(job: ComicJobSummary | ComicJobDetail | null | undefined): boolean {
  return Boolean(job && COMIC_ACTIVE_STATUSES.has(job.run_status));
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value)));
}

function comicJobPercent(job: ComicJobSummary | ComicJobDetail | null | undefined): number {
  const value = Number(job?.progress ?? 0);
  if (!Number.isFinite(value)) return 0;
  return clampPercent(value <= 1 ? value * 100 : value);
}

function comicCurrentStep(
  job: ComicJobSummary | ComicJobDetail | null | undefined,
  options?: { rewritePending?: boolean; handoffPending?: boolean },
): string | null {
  if (options?.handoffPending) return 'story_studio_handoff';
  if (options?.rewritePending) return 'rewrite_story';
  return job?.current_step || null;
}

function comicDisplayPercent(
  job: ComicJobSummary | ComicJobDetail | null | undefined,
  options?: {
    rewritePending?: boolean;
    handoffPending?: boolean;
    optimizedReady?: boolean;
  },
): number {
  const percent = comicJobPercent(job);
  if (options?.handoffPending) return Math.max(percent, 98);
  if (options?.rewritePending) return Math.max(percent, 96);
  if (options?.optimizedReady) return Math.max(percent, 100);
  return percent;
}

function comicProgressTone(
  job: ComicJobSummary | ComicJobDetail | null | undefined,
  options?: { rewritePending?: boolean; handoffPending?: boolean },
): 'busy' | 'done' | 'blocked' | 'idle' {
  if (options?.rewritePending || options?.handoffPending || isComicJobActive(job)) return 'busy';
  if (job && COMIC_BLOCKED_STATUSES.has(job.run_status)) return 'blocked';
  if (job?.run_status === 'approved' || job?.run_status === 'ready_for_review') return 'done';
  return 'idle';
}

function comicProgressSummary(
  job: ComicJobSummary | ComicJobDetail | null | undefined,
  packageValue: ComicAnalysisPackage | null | undefined,
  options?: { rewritePending?: boolean; handoffPending?: boolean },
): { title: string; detail: string; next: string } {
  if (!job) {
    return {
      title: 'Chưa chọn lần phân tích',
      detail: 'Tạo hoặc chọn một job để xem tiến trình.',
      next: 'Sau khi tạo job, thanh tiến trình sẽ tự cập nhật theo từng bước.',
    };
  }
  const step = comicCurrentStep(job, options);
  if (options?.handoffPending) {
    return {
      title: 'Đang đưa dữ liệu sang Story Studio',
      detail: 'Hệ thống đang duyệt package, tạo preview handoff, rồi tạo series/tập tương ứng.',
      next: 'Khi xong, giao diện sẽ tự chuyển sang Story Studio.',
    };
  }
  if (options?.rewritePending || step === 'rewrite_story') {
    return {
      title: 'Đang viết kịch bản tối ưu',
      detail: 'Codex đang rút gọn package phân tích và viết bản truyện đủ rõ để tạo candidate tiếp theo.',
      next: 'Không bấm lại nút trong lúc này; panel sẽ tự cập nhật khi có bản xem trước.',
    };
  }
  if (COMIC_BLOCKED_STATUSES.has(job.run_status)) {
    return {
      title: job.run_status === 'interrupted' ? 'Luồng bị gián đoạn' : 'Luồng đang dừng vì lỗi',
      detail: jobErrorMessage(job) ?? 'Một bước trong pipeline chưa hoàn tất.',
      next: 'Kiểm tra lỗi, sửa nguồn hoặc bấm phân tích lại khi đã sẵn sàng.',
    };
  }
  if (job.run_status === 'cancelled') {
    return {
      title: 'Tác vụ đã hủy',
      detail: 'Các dữ liệu đã tạo trước khi hủy vẫn được giữ trong job.',
      next: 'Bạn có thể chạy lại bước lấy nguồn hoặc phân tích khi cần.',
    };
  }
  if (packageValue?.optimized_script) {
    return {
      title: 'Kịch bản tối ưu đã sẵn sàng',
      detail: 'Package phân tích và bản kịch bản tối ưu đã đủ để tạo tập trong Story Studio.',
      next: 'Chọn series/tập và bấm “Đưa vào Story Studio”.',
    };
  }
  if ((job.analysis_revision || 0) > 0) {
    return {
      title: 'Package phân tích đã sẵn sàng',
      detail: 'Đã có panel, thoại, nhân vật, bối cảnh và cốt truyện để xem trước.',
      next: 'Bấm “Viết kịch bản tối ưu” để tạo bản truyện rõ hơn trước khi handoff.',
    };
  }
  if (job.run_status === 'source_ready') {
    return {
      title: 'Nguồn đã sẵn sàng để phân tích',
      detail: 'Ảnh/text nguồn đã được tải hoặc upload, đang chờ bước đọc nội dung truyện.',
      next: 'Bấm “Phân tích truyện” để đọc hình ảnh, thoại, nhân vật và bối cảnh.',
    };
  }
  if (isComicJobActive(job)) {
    return {
      title: STEP_LABELS[step || ''] ?? 'Đang xử lý truyện',
      detail: 'Hệ thống đang cập nhật job theo từng checkpoint; dữ liệu preview sẽ hiện dần khi có.',
      next: 'Bạn có thể để trang mở, panel sẽ tự refresh giống luồng AI Video.',
    };
  }
  return {
    title: STATUS_LABELS[job.run_status] ?? 'Đang chờ thao tác',
    detail: STEP_LABELS[step || ''] ?? 'Job chưa có bước xử lý hiện tại.',
    next: 'Chọn hành động tiếp theo ở góc phải của panel.',
  };
}

function comicMilestoneStatus(
  job: ComicJobSummary | ComicJobDetail | null | undefined,
  milestone: ComicProgressMilestoneStep,
  packageValue: ComicAnalysisPackage | null | undefined,
  options?: { rewritePending?: boolean; handoffPending?: boolean },
): ComicMilestoneStatus {
  if (!job) return 'pending';
  const step = comicCurrentStep(job, options);
  const hasSource = Boolean(job.current_source_document_id || (job.progress ?? 0) >= 0.5);
  const hasAnalysis = Number(job.analysis_revision || 0) > 0;
  const hasOptimized = Boolean(packageValue?.optimized_script);
  const blocked = COMIC_BLOCKED_STATUSES.has(job.run_status);
  const activeStep =
    milestone === 'collect_source'
      ? step && COMIC_SOURCE_COLLECTION_STEPS.has(step)
      : milestone === 'prepare_assets'
        ? step && COMIC_ASSET_PREP_STEPS.has(step)
        : step === milestone;

  if (blocked && activeStep) return 'blocked';
  if (milestone === 'story_studio_handoff') {
    if (options?.handoffPending) return 'current';
    return 'pending';
  }
  if (milestone === 'rewrite_story') {
    if (hasOptimized) return 'done';
    if (options?.rewritePending || step === 'rewrite_story') return blocked ? 'blocked' : 'current';
    return hasAnalysis ? 'pending' : 'pending';
  }
  if (milestone === 'collect_source') {
    if (hasSource || hasAnalysis) return 'done';
    return activeStep ? (blocked ? 'blocked' : 'current') : 'pending';
  }
  if (milestone === 'prepare_assets') {
    if (hasAnalysis || (hasSource && !COMIC_SOURCE_COLLECTION_STEPS.has(step || ''))) return 'done';
    return activeStep ? (blocked ? 'blocked' : 'current') : 'pending';
  }
  if (COMIC_ANALYSIS_STEPS.includes(milestone)) {
    if (hasAnalysis) return 'done';
    if (activeStep) return blocked ? 'blocked' : 'current';
  }
  return 'pending';
}

const READING_MODES = [
  { value: 'auto', label: 'Tự động' },
  { value: 'vertical', label: 'Truyện dọc' },
  { value: 'page_ltr', label: 'Trang trái → phải' },
  { value: 'page_rtl', label: 'Trang phải → trái' },
];

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' {
  if (status === 'failed' || status === 'interrupted') return 'destructive';
  if (status === 'approved' || status === 'ready_for_review') return 'default';
  return 'secondary';
}

function mutationError(...values: Array<unknown>): string | null {
  for (const value of values) {
    if (value instanceof Error) return value.message;
  }
  return null;
}

function jobErrorMessage(job: ComicJobSummary | ComicJobDetail): string | null {
  if (!job.error_code) return null;
  if (job.run_status === 'interrupted') {
    if (job.source_type === 'url') {
      return 'Lần tải nguồn trước bị gián đoạn. Bấm “Thử lại tải nguồn” để tiếp tục.';
    }
    return 'Lần phân tích trước bị gián đoạn. Bấm “Phân tích truyện” để chạy lại.';
  }
  return job.error_message || ERROR_MESSAGES[job.error_code] || 'Không thể hoàn tất tác vụ này.';
}

function confidenceLabel(value?: number | null): string | null {
  if (typeof value !== 'number') return null;
  return `${Math.round(value * 100)}% tin cậy`;
}

function formatUnknown(value: unknown): string {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

export function ComicSeriesAnalysis() {
  const queryClient = useQueryClient();
  const { analysisId: routeAnalysisId } = useParams({ strict: false });
  const [url, setUrl] = useState('');
  const [readingMode, setReadingMode] = useState('auto');
  const [rightsAttested, setRightsAttested] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(
    () => routeAnalysisId ?? null,
  );
  const [handoffTargetKind, setHandoffTargetKind] =
    useState<ComicHandoffTargetKind>('new_series');
  const [handoffTargetSeriesId, setHandoffTargetSeriesId] = useState('');
  const [handoffSeriesPickerOpen, setHandoffSeriesPickerOpen] = useState(false);
  const [handoffSeriesMode, setHandoffSeriesMode] =
    useState<ComicHandoffSeriesMode>('image_story_only');
  const [handoffSeriesTitle, setHandoffSeriesTitle] = useState('');
  const [handoffEpisodeTitle, setHandoffEpisodeTitle] = useState('');
  const [handoffEpisodeNumber, setHandoffEpisodeNumber] = useState('');
  const [handoffOutputIntent, setHandoffOutputIntent] =
    useState<StoryOutputIntent>('truyen_anh');
  const [handoffMarketProfile, setHandoffMarketProfile] = useState('global_short');
  const [handoffLanguageProfile, setHandoffLanguageProfile] = useState('en');
  const [handoffSourceInput, setHandoffSourceInput] = useState('');
  const [handoffOutputSettings, setHandoffOutputSettings] = useState<StoryEpisodeOutputSettings>(
    () => defaultHandoffOutputSettings(),
  );

  const jobsQuery = useInfiniteQuery({
    queryKey: ['comic-jobs'],
    queryFn: ({ pageParam }) => apiClient.listComicJobs(COMIC_JOBS_PAGE_SIZE, pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => {
      const loadedCount = pages.reduce((total, page) => total + page.jobs.length, 0);
      return lastPage.jobs.length > 0 && loadedCount < lastPage.total ? loadedCount : undefined;
    },
    refetchInterval: (query) => {
      const jobs = query.state.data?.pages.flatMap((page) => page.jobs) ?? [];
      return jobs.some((job) => job.run_status === 'queued' || job.run_status === 'running')
        ? 2500
        : false;
    },
  });
  const jobs = useMemo(
    () => jobsQuery.data?.pages.flatMap((page) => page.jobs) ?? [],
    [jobsQuery.data?.pages],
  );
  const jobsTotal = jobsQuery.data?.pages[0]?.total ?? 0;
  const capabilitiesQuery = useQuery({
    queryKey: ['comic-capabilities'],
    queryFn: () => apiClient.getComicCapabilities(),
  });
  const jobQuery = useQuery({
    queryKey: ['comic-job', selectedJobId],
    queryFn: () => apiClient.getComicJob(selectedJobId!),
    enabled: Boolean(selectedJobId),
    refetchInterval: (query) => {
      const job = query.state.data;
      return job?.run_status === 'queued' || job?.run_status === 'running' ? 2000 : false;
    },
  });
  const selectedSummary = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );
  const currentJob = jobQuery.data ?? selectedSummary;
  const canLoadAnalysisPackage = Boolean(
    selectedJobId &&
      currentJob &&
      (currentJob.analysis_revision > 0 ||
        currentJob.run_status === 'running' ||
        currentJob.run_status === 'ready_for_review' ||
        currentJob.run_status === 'approved'),
  );
  const packageQuery = useQuery({
    queryKey: ['comic-analysis-package', selectedJobId, currentJob?.analysis_revision],
    queryFn: () => apiClient.getComicAnalysisPackage(selectedJobId!),
    enabled: canLoadAnalysisPackage,
    refetchInterval: currentJob?.run_status === 'running' ? 2500 : false,
  });
  const analysisPackage = packageQuery.data ?? null;
  const seriesQuery = useQuery({
    queryKey: ['comic-handoff-series'],
    queryFn: () => apiClient.listVideoSeries(),
    enabled: Boolean(selectedJobId && analysisPackage?.optimized_script),
  });
  const handoffSeriesOptions = useMemo(
    () =>
      (seriesQuery.data ?? []).filter(
        (series) => series.series_mode === 'image_story_only' || series.series_mode === 'hybrid',
      ),
    [seriesQuery.data],
  );
  const selectedHandoffSeries = useMemo(
    () => handoffSeriesOptions.find((series) => series.id === handoffTargetSeriesId) ?? null,
    [handoffSeriesOptions, handoffTargetSeriesId],
  );
  const effectiveHandoffSeriesMode =
    handoffTargetKind === 'existing_series'
      ? selectedHandoffSeries?.series_mode
      : handoffSeriesMode;
  const effectiveHandoffOutputIntent: StoryOutputIntent =
    effectiveHandoffSeriesMode === 'image_story_only' ? 'truyen_anh' : handoffOutputIntent;
  const handoffEpisodeNumberCandidate = Number(handoffEpisodeNumber);
  const parsedHandoffEpisodeNumber =
    handoffEpisodeNumber.trim() &&
    Number.isInteger(handoffEpisodeNumberCandidate) &&
    handoffEpisodeNumberCandidate > 0
      ? handoffEpisodeNumberCandidate
      : undefined;
  const handoffEpisodeNumberValid =
    !handoffEpisodeNumber.trim() || parsedHandoffEpisodeNumber !== undefined;
  const handoffDefaultEpisodeTitle =
    analysisPackage?.optimized_script?.title || currentJob?.title || '';
  const handoffDefaultSeriesTitle = currentJob?.title || handoffDefaultEpisodeTitle;

  useEffect(() => {
    if (routeAnalysisId) {
      setSelectedJobId(routeAnalysisId);
    }
  }, [routeAnalysisId]);

  useEffect(() => {
    if (routeAnalysisId) return;
    if (!selectedJobId && jobs[0]?.id) {
      setSelectedJobId(jobs[0].id);
    }
  }, [jobs, routeAnalysisId, selectedJobId]);

  useEffect(() => {
    if (!handoffTargetSeriesId) return;
    if (!seriesQuery.data) return;
    if (handoffSeriesOptions.some((series) => series.id === handoffTargetSeriesId)) return;
    setHandoffTargetSeriesId('');
  }, [handoffSeriesOptions, handoffTargetSeriesId, seriesQuery.data]);

  const invalidateJob = async (jobId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['comic-jobs'] }),
      queryClient.invalidateQueries({ queryKey: ['comic-job', jobId] }),
      queryClient.invalidateQueries({ queryKey: ['comic-analysis-package', jobId] }),
    ]);
  };

  const patchComicJobInCache = (
    jobId: string,
    patch: Partial<ComicJobSummary>,
  ) => {
    queryClient.setQueryData<ComicJobDetail | undefined>(['comic-job', jobId], (current) =>
      current
        ? {
            ...current,
            ...patch,
            updated_at: new Date().toISOString(),
          }
        : current,
    );
    queryClient.setQueryData<InfiniteData<ComicJobListResponse> | undefined>(
      ['comic-jobs'],
      (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                jobs: page.jobs.map((job) =>
                  job.id === jobId
                    ? {
                        ...job,
                        ...patch,
                        updated_at: new Date().toISOString(),
                      }
                    : job,
                ),
              })),
            }
          : current,
    );
  };

  const createUrlMutation = useMutation({
    mutationFn: () =>
      apiClient.createComicUrlJob({
        url,
        reading_mode: readingMode,
        rights_attested: rightsAttested,
      }),
    onSuccess: async (job) => {
      setUrl('');
      setSelectedJobId(job.id);
      await invalidateJob(job.id);
    },
  });
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) =>
      apiClient.createComicUploadJob(files, {
        reading_mode: readingMode,
        rights_attested: rightsAttested,
      }),
    onSuccess: async (job) => {
      setSelectedJobId(job.id);
      await invalidateJob(job.id);
    },
  });
  const fetchMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.runComicJob(jobId),
    onMutate: (jobId) => {
      patchComicJobInCache(jobId, {
        run_status: 'queued',
        current_step: 'validate_source',
        progress: 0,
      });
    },
    onSuccess: (job) => invalidateJob(job.id),
    onSettled: (_value, _error, jobId) => {
      if (jobId) void invalidateJob(jobId);
    },
  });
  const retryMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.retryComicJob(jobId),
    onMutate: (jobId) => {
      patchComicJobInCache(jobId, {
        run_status: 'queued',
        current_step: 'validate_source',
        progress: 0,
      });
    },
    onSuccess: (job) => invalidateJob(job.id),
    onSettled: (_value, _error, jobId) => {
      if (jobId) void invalidateJob(jobId);
    },
  });
  const analyzeMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.analyzeComicJob(jobId),
    onMutate: (jobId) => {
      patchComicJobInCache(jobId, {
        run_status: 'running',
        current_step: 'panel_analysis',
        progress: Math.max(currentJob?.progress ?? 0.5, 0.55),
      });
    },
    onSuccess: (job) => invalidateJob(job.id),
    onSettled: (_value, _error, jobId) => {
      if (jobId) void invalidateJob(jobId);
    },
  });
  const rewriteMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.rewriteComicStory(jobId),
    onMutate: (jobId) => {
      patchComicJobInCache(jobId, {
        run_status: 'running',
        current_step: 'rewrite_story',
        progress: Math.max(currentJob?.progress ?? 0.95, 0.96),
      });
    },
    onSuccess: (value) => {
      if (!selectedJobId) return;
      queryClient.setQueryData(
        ['comic-analysis-package', selectedJobId, value.analysis_revision],
        value,
      );
      patchComicJobInCache(selectedJobId, {
        run_status: 'ready_for_review',
        current_step: 'build_review',
        progress: 1,
      });
      void invalidateJob(selectedJobId);
    },
    onSettled: (_value, _error, jobId) => {
      if (jobId) void invalidateJob(jobId);
    },
  });
  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.cancelComicJob(jobId),
    onSuccess: (job) => invalidateJob(job.id),
  });
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.deleteComicJob(jobId),
    onSuccess: async () => {
      setSelectedJobId(null);
      await queryClient.invalidateQueries({ queryKey: ['comic-jobs'] });
    },
  });
  const handoffMutation = useMutation({
    mutationFn: async ({
      job,
      packageValue,
      targetKind,
      targetSeriesId,
      targetSeriesMode,
      seriesTitle,
      episodeTitle,
      episodeNumber,
      outputIntent,
      marketProfile,
      languageProfile,
      sourceInput,
      outputSettings,
    }: {
      job: ComicJobSummary | ComicJobDetail;
      packageValue: ComicAnalysisPackage;
      targetKind: ComicHandoffTargetKind;
      targetSeriesId?: string;
      targetSeriesMode: ComicHandoffSeriesMode;
      seriesTitle?: string;
      episodeTitle?: string;
      episodeNumber?: number;
      outputIntent: StoryOutputIntent;
      marketProfile: string;
      languageProfile: string;
      sourceInput?: string;
      outputSettings: StoryEpisodeOutputSettings;
    }) => {
      patchComicJobInCache(job.id, {
        current_step: 'story_studio_handoff',
        progress: Math.max(job.progress ?? 0, 0.98),
      });
      const hasPromptSegmentSettings = Boolean(
        outputSettings.video.prompt_segment_count &&
          outputSettings.video.prompt_segment_duration_seconds,
      );
      const limitations: unknown[] =
        'limitations' in job && Array.isArray(job.limitations) ? job.limitations : [];
      const acceptedItems = [
        { item_type: 'episode', id: job.id, revision: job.analysis_revision },
        ...packageValue.panels.map((item) => ({
          item_type: 'panel',
          id: item.id,
          revision: job.analysis_revision,
        })),
        ...packageValue.dialogues.map((item) => ({
          item_type: 'dialogue',
          id: item.id,
          revision: job.analysis_revision,
        })),
        ...packageValue.characters.map((item) => ({
          item_type: 'character',
          id: item.id,
          revision: job.analysis_revision,
        })),
        ...packageValue.locations.map((item) => ({
          item_type: 'location',
          id: item.id,
          revision: job.analysis_revision,
        })),
      ];
      await apiClient.approveComicJob(job.id, {
        accepted_items: acceptedItems,
        excluded_items: [],
        unreviewed_items: [],
        accepted_limitations: limitations.map((item) =>
          typeof item === 'object' && item && 'code' in item ? String(item.code) : String(item),
        ),
      });
      const preview = await apiClient.previewComicHandoff(job.id, {
        target_kind: targetKind,
        target_series_id: targetKind === 'existing_series' ? targetSeriesId : undefined,
        target_series_mode: targetKind === 'new_series' ? targetSeriesMode : undefined,
        target_series_title: targetKind === 'new_series' ? seriesTitle : undefined,
        episode_title: episodeTitle || packageValue.optimized_script?.title || job.title,
        episode_number: episodeNumber,
        output_intent: outputIntent,
        market_profile: marketProfile,
        language_profile: languageProfile,
        source_input: sourceInput,
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
        selected_items: acceptedItems.map((item) => item.id),
      });
      return apiClient.commitComicHandoff(job.id, {
        handoff_id: preview.handoff_id,
        idempotency_key: `comic-${job.id}-revision-${job.analysis_revision}-handoff-${preview.handoff_id}`,
      });
    },
    onSuccess: (result) => window.location.assign(result.story_studio_url),
  });

  const isActive = isComicJobActive(currentJob);
  const anyBusy =
    fetchMutation.isPending ||
    retryMutation.isPending ||
    analyzeMutation.isPending ||
    rewriteMutation.isPending ||
    handoffMutation.isPending ||
    cancelMutation.isPending;
  const canRetry = Boolean(
    currentJob &&
      currentJob.source_type === 'url' &&
      ['failed', 'interrupted', 'cancelled'].includes(currentJob.run_status),
  );
  const canAnalyze = Boolean(
    currentJob &&
      !isActive &&
      currentJob.current_source_document_id &&
      ['source_ready', 'ready_for_review', 'approved', 'interrupted', 'failed'].includes(
        currentJob.run_status,
      ),
  );
  const canRewrite = Boolean(
    currentJob && analysisPackage && currentJob.analysis_revision > 0 && !isActive,
  );
  const canHandoff = Boolean(
    currentJob &&
      currentJob.analysis_revision > 0 &&
      analysisPackage?.optimized_script?.full_story?.trim() &&
      !isActive &&
      handoffEpisodeNumberValid &&
      (handoffTargetKind === 'new_series' || handoffTargetSeriesId),
  );
  const primaryError =
    (currentJob && jobErrorMessage(currentJob)) ||
    mutationError(
      createUrlMutation.error,
      uploadMutation.error,
      fetchMutation.error,
      retryMutation.error,
      analyzeMutation.error,
      rewriteMutation.error,
      handoffMutation.error,
      cancelMutation.error,
      deleteMutation.error,
      jobQuery.error,
      packageQuery.error,
    );
  const caps = capabilitiesQuery.data;
  const currentLimitations: unknown[] =
    currentJob && 'limitations' in currentJob && Array.isArray(currentJob.limitations)
      ? currentJob.limitations
      : [];

  return (
    <div className="min-h-0 flex-1 overflow-y-auto py-5">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-4 px-4 sm:px-6">
        <header className="flex flex-col gap-4 rounded-lg border border-border/80 bg-card/70 p-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">Phân tích truyện tranh</h1>
              {caps && !caps.codecs.full_capability_ready ? (
                <Badge variant="secondary" className="w-fit gap-1 whitespace-normal">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  Thiếu codec: {caps.codecs.missing_mandatory.join(', ')}
                </Badge>
              ) : null}
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Đọc hình ảnh, chữ, nhân vật và bối cảnh; viết kịch bản tối ưu rồi chuyển sang Story
              Studio.
            </p>
          </div>
          <ComicStatusCard
            job={currentJob}
            optimizedReady={Boolean(analysisPackage?.optimized_script)}
            busy={
              isActive ||
              retryMutation.isPending ||
              rewriteMutation.isPending ||
              handoffMutation.isPending
            }
          />
        </header>

        {primaryError ? (
          <div
            className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            role="alert"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0">
              <p className="font-medium">Chưa xử lý được bước này</p>
              <p className="mt-1 leading-relaxed">{primaryError}</p>
            </div>
          </div>
        ) : null}

        <div className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <aside className="order-2 min-w-0 space-y-4 xl:order-1">
            <CreatePanel
              url={url}
              setUrl={setUrl}
              readingMode={readingMode}
              setReadingMode={setReadingMode}
              rightsAttested={rightsAttested}
              setRightsAttested={setRightsAttested}
              onCreateUrl={() => createUrlMutation.mutate()}
              onUpload={(files) => uploadMutation.mutate(files)}
              creating={createUrlMutation.isPending || uploadMutation.isPending}
              error={mutationError(createUrlMutation.error, uploadMutation.error)}
            />
            <section className="rounded-lg border border-border/80 bg-card/65 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Các lần phân tích</h2>
                {jobsQuery.isFetching ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : null}
              </div>
              <JobList
                jobs={jobs}
                total={jobsTotal}
                loading={jobsQuery.isLoading}
                loadingMore={jobsQuery.isFetchingNextPage}
                hasMore={Boolean(jobsQuery.hasNextPage)}
                selectedJobId={selectedJobId}
                onSelect={setSelectedJobId}
                onLoadMore={() => void jobsQuery.fetchNextPage()}
              />
            </section>
            <CapabilityPanel caps={caps} />
          </aside>

          <main className="order-1 min-w-0 space-y-4 xl:order-2">
            {!currentJob ? (
              <div className="flex min-h-56 items-center justify-center rounded-lg border p-8 text-sm text-muted-foreground">
                Chọn một lần phân tích để xem kết quả và tiếp tục luồng.
              </div>
            ) : (
              <>
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate text-lg font-semibold">
                          {currentJob.title || 'Truyện chưa đặt tên'}
                        </h2>
                        <Badge variant={statusVariant(currentJob.run_status)}>
                          {STATUS_LABELS[currentJob.run_status] ?? currentJob.run_status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {STEP_LABELS[currentJob.current_step] ?? currentJob.current_step} ·{' '}
                        {RESULT_COMPLETENESS_LABELS[currentJob.result_completeness] ??
                          currentJob.result_completeness}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {currentJob.source_type === 'url' && currentJob.run_status === 'draft' ? (
                        <Button
                          type="button"
                          variant="outline"
                          className="min-h-11 rounded-full px-5"
                          disabled={anyBusy}
                          onClick={() => fetchMutation.mutate(currentJob.id)}
                        >
                          {fetchMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ArrowRight className="h-4 w-4" />
                          )}
                          Tải nguồn truyện
                        </Button>
                      ) : null}
                      {isActive ? (
                        <Button
                          type="button"
                          variant="outline"
                          className="min-h-11 rounded-full px-5"
                          disabled={cancelMutation.isPending}
                          onClick={() => cancelMutation.mutate(currentJob.id)}
                        >
                          {cancelMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <CircleStop className="h-4 w-4" />
                          )}
                          Hủy tác vụ
                        </Button>
                      ) : null}
                      {canRetry ? (
                        <Button
                          type="button"
                          variant="outline"
                          className="min-h-11 rounded-full px-5"
                          disabled={anyBusy}
                          onClick={() => retryMutation.mutate(currentJob.id)}
                        >
                          {retryMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                          Thử lại tải nguồn
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="outline"
                        className="min-h-11 rounded-full px-5"
                        disabled={!canAnalyze || anyBusy}
                        onClick={() => analyzeMutation.mutate(currentJob.id)}
                      >
                        {analyzeMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                        {currentJob.analysis_revision > 0
                          ? 'Phân tích lại truyện'
                          : 'Phân tích truyện'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="min-h-11 rounded-full px-5"
                        disabled={!canRewrite || anyBusy}
                        onClick={() => rewriteMutation.mutate(currentJob.id)}
                      >
                        {rewriteMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Viết kịch bản tối ưu
                      </Button>
                      <Button
                        type="button"
                        className="min-h-11 rounded-full px-5"
                        disabled={!canHandoff || anyBusy}
                        onClick={() =>
                          analysisPackage &&
                          handoffMutation.mutate({
                            job: currentJob,
                            packageValue: analysisPackage,
                            targetKind: handoffTargetKind,
                            targetSeriesId:
                              handoffTargetKind === 'existing_series'
                                ? handoffTargetSeriesId
                                : undefined,
                            targetSeriesMode: handoffSeriesMode,
                            seriesTitle: handoffSeriesTitle.trim() || undefined,
                            episodeTitle: handoffEpisodeTitle.trim() || undefined,
                            episodeNumber: parsedHandoffEpisodeNumber,
                            outputIntent: effectiveHandoffOutputIntent,
                            marketProfile: handoffMarketProfile,
                            languageProfile: handoffLanguageProfile,
                            sourceInput: handoffSourceInput.trim() || undefined,
                            outputSettings: handoffOutputSettings,
                          })
                        }
                      >
                        {handoffMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <ArrowRight className="h-4 w-4" />
                        )}
                        Đưa vào Story Studio
                      </Button>
                    </div>
                  </div>

                  <ComicRunProgressPanel
                    job={currentJob}
                    packageValue={analysisPackage}
                    isFetching={jobQuery.isFetching || jobsQuery.isFetching || packageQuery.isFetching}
                    rewritePending={rewriteMutation.isPending}
                    handoffPending={handoffMutation.isPending}
                    cancelPending={cancelMutation.isPending}
                    onCancel={() => cancelMutation.mutate(currentJob.id)}
                  />
                  {primaryError ? (
                    <p
                      className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-destructive"
                      role="alert"
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span className="break-words">{primaryError}</span>
                    </p>
                  ) : null}
                </section>

                {analysisPackage?.optimized_script ? (
                  <OptimizedScriptReadyCard packageValue={analysisPackage} />
                ) : null}

                {analysisPackage?.optimized_script ? (
                  <HandoffTargetPanel
                    targetKind={handoffTargetKind}
                    setTargetKind={setHandoffTargetKind}
                    targetSeriesId={handoffTargetSeriesId}
                    setTargetSeriesId={setHandoffTargetSeriesId}
                    seriesMode={handoffSeriesMode}
                    setSeriesMode={setHandoffSeriesMode}
                    seriesTitle={handoffSeriesTitle}
                    setSeriesTitle={setHandoffSeriesTitle}
                    episodeTitle={handoffEpisodeTitle}
                    setEpisodeTitle={setHandoffEpisodeTitle}
                    episodeNumber={handoffEpisodeNumber}
                    setEpisodeNumber={setHandoffEpisodeNumber}
                    outputIntent={handoffOutputIntent}
                    effectiveOutputIntent={effectiveHandoffOutputIntent}
                    setOutputIntent={setHandoffOutputIntent}
                    marketProfile={handoffMarketProfile}
                    setMarketProfile={setHandoffMarketProfile}
                    languageProfile={handoffLanguageProfile}
                    setLanguageProfile={setHandoffLanguageProfile}
                    sourceInput={handoffSourceInput}
                    setSourceInput={setHandoffSourceInput}
                    outputSettings={handoffOutputSettings}
                    setOutputSettings={setHandoffOutputSettings}
                    defaultSeriesTitle={handoffDefaultSeriesTitle}
                    defaultEpisodeTitle={handoffDefaultEpisodeTitle}
                    episodeNumberValid={handoffEpisodeNumberValid}
                    seriesOptions={handoffSeriesOptions}
                    selectedSeries={selectedHandoffSeries}
                    loadingSeries={seriesQuery.isFetching}
                    seriesError={mutationError(seriesQuery.error)}
                    onOpenSeriesPicker={() => setHandoffSeriesPickerOpen(true)}
                    disabled={anyBusy || isActive}
                  />
                ) : null}

                <AnalysisResults
                  packageValue={analysisPackage}
                  loading={packageQuery.isLoading}
                  limitations={currentLimitations}
                  finalized={Boolean(currentJob.analysis_revision > 0 && !isActive)}
                />

                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    className="text-destructive"
                    disabled={anyBusy || isActive || deleteMutation.isPending}
                    onClick={() => {
                      if (window.confirm('Xóa lần phân tích truyện này?')) {
                        deleteMutation.mutate(currentJob.id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" /> Xóa lần phân tích
                  </Button>
                </div>
              </>
            )}
          </main>
        </div>
        <SeriesPickerDialog
          open={handoffSeriesPickerOpen}
          onOpenChange={setHandoffSeriesPickerOpen}
          context="comic_handoff"
          series={seriesQuery.data ?? []}
          selectedSeriesId={handoffTargetSeriesId}
          loading={seriesQuery.isLoading || seriesQuery.isFetching}
          error={mutationError(seriesQuery.error)}
          disabled={anyBusy || isActive}
          onSelect={(series) => {
            setHandoffTargetKind('existing_series');
            setHandoffTargetSeriesId(series.id);
            setHandoffSeriesPickerOpen(false);
          }}
        />
      </div>
    </div>
  );
}

function ComicProgressBar({
  percent,
  tone,
  active,
  className,
  ariaLabel = 'Tiến độ phân tích truyện tranh',
}: {
  percent: number;
  tone: 'busy' | 'done' | 'blocked' | 'idle';
  active?: boolean;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <div
      className={cn('h-2 overflow-hidden rounded-full bg-background', className)}
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all duration-700 [transition-timing-function:cubic-bezier(0.16,1,0.3,1)]',
          tone === 'blocked' ? 'bg-destructive' : null,
          tone === 'done' ? 'bg-emerald-600' : null,
          tone === 'busy' ? 'bg-foreground' : null,
          tone === 'idle' ? 'bg-muted-foreground/60' : null,
          active ? 'animate-pulse' : null,
        )}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

function ComicStatusCard({
  job,
  optimizedReady,
  busy,
}: {
  job: ComicJobSummary | ComicJobDetail | null;
  optimizedReady: boolean;
  busy: boolean;
}) {
  const tone = busy ? 'busy' : comicProgressTone(job);
  const progress = comicDisplayPercent(job, { optimizedReady });
  return (
    <div className="min-w-[240px] rounded-lg border border-border/70 bg-background/80 p-3 shadow-sm">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium">
          {job ? (STATUS_LABELS[job.run_status] ?? job.run_status) : 'Chưa chọn job'}
        </span>
        <span className="font-mono text-muted-foreground tabular-nums">{progress}%</span>
      </div>
      <ComicProgressBar percent={progress} tone={tone} active={busy} className="mt-3" />
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {job
          ? (STEP_LABELS[job.current_step] ?? job.current_step)
          : 'Tạo hoặc chọn một lần phân tích.'}
      </p>
    </div>
  );
}

function ComicRunProgressPanel({
  job,
  packageValue,
  isFetching,
  rewritePending,
  handoffPending,
  cancelPending,
  onCancel,
}: {
  job: ComicJobSummary | ComicJobDetail;
  packageValue: ComicAnalysisPackage | null;
  isFetching: boolean;
  rewritePending: boolean;
  handoffPending: boolean;
  cancelPending: boolean;
  onCancel: () => void;
}) {
  const optimizedReady = Boolean(packageValue?.optimized_script);
  const percent = comicDisplayPercent(job, { rewritePending, handoffPending, optimizedReady });
  const tone = comicProgressTone(job, { rewritePending, handoffPending });
  const summary = comicProgressSummary(job, packageValue, { rewritePending, handoffPending });
  const active = tone === 'busy';
  const step = comicCurrentStep(job, { rewritePending, handoffPending });

  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-border/75 bg-background/75 shadow-[0_18px_38px_-28px_rgba(15,23,42,0.35)]">
      <div className="grid gap-4 border-b border-border/70 p-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium',
                tone === 'done'
                  ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : null,
                tone === 'busy'
                  ? 'border-sky-500/25 bg-sky-500/10 text-sky-700 dark:text-sky-300'
                  : null,
                tone === 'blocked'
                  ? 'border-destructive/25 bg-destructive/10 text-destructive'
                  : null,
                tone === 'idle'
                  ? 'border-border bg-muted/30 text-muted-foreground'
                  : null,
              )}
            >
              {isFetching && active ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {handoffPending
                ? 'Đang handoff'
                : rewritePending
                  ? 'Đang viết kịch bản'
                  : STATUS_LABELS[job.run_status] ?? job.run_status}
            </span>
            <span className="inline-flex items-center rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-muted-foreground">
              {job.source_type === 'url' ? 'Nguồn web' : 'Upload ảnh'}
            </span>
            <span className="rounded-full border border-border/70 bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground">
              Revision {job.analysis_revision || 0}
            </span>
            {step ? (
              <span className="rounded-full border border-border/70 bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground">
                {STEP_LABELS[step] ?? step}
              </span>
            ) : null}
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
            <ComicProgressBar
              percent={percent}
              tone={tone}
              active={active}
              className="mt-3 bg-background"
            />
          </div>
          {active ? (
            <Button
              size="sm"
              variant="outline"
              disabled={cancelPending || rewritePending || handoffPending}
              onClick={onCancel}
              className="w-full active:translate-y-[1px]"
            >
              {cancelPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CircleStop className="h-4 w-4" />
              )}
              Hủy
            </Button>
          ) : null}
        </div>
      </div>
      <div className="grid gap-0 divide-y divide-border/70 md:grid-cols-4 xl:grid-cols-8 md:divide-x md:divide-y-0">
        {COMIC_PROGRESS_MILESTONES.map((item) => {
          const milestoneStatus = comicMilestoneStatus(job, item.step, packageValue, {
            rewritePending,
            handoffPending,
          });
          return (
            <div
              key={item.step}
              className={cn(
                'min-h-32 p-4 transition-colors',
                milestoneStatus === 'current' ? 'bg-sky-500/[0.08]' : null,
                milestoneStatus === 'blocked' ? 'bg-destructive/[0.08]' : null,
                milestoneStatus === 'done' ? 'bg-emerald-500/[0.08]' : null,
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border',
                    milestoneStatus === 'done'
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                      : null,
                    milestoneStatus === 'current'
                      ? 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300'
                      : null,
                    milestoneStatus === 'blocked'
                      ? 'border-destructive/30 bg-destructive/10 text-destructive'
                      : null,
                    milestoneStatus === 'pending'
                      ? 'border-border bg-background text-muted-foreground'
                      : null,
                  )}
                >
                  {milestoneStatus === 'done' ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : milestoneStatus === 'current' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : milestoneStatus === 'blocked' ? (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
                  )}
                </span>
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

function OptimizedScriptReadyCard({ packageValue }: { packageValue: ComicAnalysisPackage }) {
  const script = packageValue.optimized_script;
  if (!script) return null;
  const sourceLabel =
    packageValue.optimized_script_source === 'local_fallback'
      ? 'Fallback nội bộ'
      : packageValue.optimized_script_source === 'codex'
        ? 'Codex'
        : 'Đã tạo';
  return (
    <section className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles className="h-5 w-5 text-emerald-500" />
            <h3 className="text-base font-semibold">Bản xem trước kịch bản tối ưu đã sẵn sàng</h3>
            <Badge variant="secondary">{sourceLabel}</Badge>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Hãy duyệt nội dung trong tab “Kịch bản tối ưu” bên dưới trước khi bấm “Đưa vào Story Studio”.
          </p>
          <p className="mt-3 line-clamp-2 text-sm leading-relaxed">{script.synopsis}</p>
        </div>
        <div className="grid min-w-[220px] grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-lg border bg-background/70 p-3">
            <div className="text-lg font-semibold">{script.plot_beats?.length ?? 0}</div>
            <div className="text-muted-foreground">plot beats</div>
          </div>
          <div className="rounded-lg border bg-background/70 p-3">
            <div className="text-lg font-semibold">{script.scene_outline?.length ?? 0}</div>
            <div className="text-muted-foreground">cảnh</div>
          </div>
          <div className="rounded-lg border bg-background/70 p-3">
            <div className="text-lg font-semibold">{script.character_arcs?.length ?? 0}</div>
            <div className="text-muted-foreground">arc</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function comicSeriesModeLabel(mode: SeriesMode | null | undefined): string {
  if (mode === 'image_story_only') return 'Series truyện ảnh';
  if (mode === 'hybrid') return 'Series truyện + video';
  return 'Series video';
}

function HandoffTargetPanel(props: {
  targetKind: ComicHandoffTargetKind;
  setTargetKind: (value: ComicHandoffTargetKind) => void;
  targetSeriesId: string;
  setTargetSeriesId: (value: string) => void;
  seriesMode: ComicHandoffSeriesMode;
  setSeriesMode: (value: ComicHandoffSeriesMode) => void;
  seriesTitle: string;
  setSeriesTitle: (value: string) => void;
  episodeTitle: string;
  setEpisodeTitle: (value: string) => void;
  episodeNumber: string;
  setEpisodeNumber: (value: string) => void;
  outputIntent: StoryOutputIntent;
  effectiveOutputIntent: StoryOutputIntent;
  setOutputIntent: (value: StoryOutputIntent) => void;
  marketProfile: string;
  setMarketProfile: (value: string) => void;
  languageProfile: string;
  setLanguageProfile: (value: string) => void;
  sourceInput: string;
  setSourceInput: (value: string) => void;
  outputSettings: StoryEpisodeOutputSettings;
  setOutputSettings: (value: StoryEpisodeOutputSettings | ((current: StoryEpisodeOutputSettings) => StoryEpisodeOutputSettings)) => void;
  defaultSeriesTitle: string;
  defaultEpisodeTitle: string;
  episodeNumberValid: boolean;
  seriesOptions: VideoSeriesResponse[];
  selectedSeries: VideoSeriesResponse | null;
  loadingSeries: boolean;
  seriesError: string | null;
  onOpenSeriesPicker: () => void;
  disabled: boolean;
}) {
  const newSeriesSelected = props.targetKind === 'new_series';
  const existingSeriesSelected = props.targetKind === 'existing_series';

  return (
    <section className="rounded-2xl border border-border/80 bg-card/75 p-5 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold">Đích Story Studio</h3>
            <Badge variant="secondary" className="rounded-full">
              Bước cuối
            </Badge>
          </div>
          <p className="mt-1 max-w-4xl text-sm leading-relaxed text-muted-foreground">
            Chọn tạo series mới hoặc thêm tập này vào một series truyện đã có. Series video-only
            được ẩn để tránh đưa truyện tranh nhầm sang luồng AI Video.
          </p>
        </div>
        {props.loadingSeries ? (
          <Badge variant="secondary" className="w-fit shrink-0 gap-1 rounded-full">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Đang tải series
          </Badge>
        ) : null}
      </div>

      <div className="mt-5 grid min-w-0 items-start gap-4 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <fieldset className="grid min-w-0 items-start gap-3 border-0 p-0 sm:grid-cols-2">
          <legend className="sr-only">Chọn đích Story Studio</legend>
          <button
            type="button"
            aria-pressed={newSeriesSelected}
            disabled={props.disabled}
            onClick={() => props.setTargetKind('new_series')}
            className={cn(
              'min-h-[128px] cursor-pointer rounded-xl border border-border bg-background/90 p-4 text-left shadow-sm transition duration-200 hover:border-primary/50 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60',
              newSeriesSelected && 'border-primary/80 bg-muted/45 ring-2 ring-primary/45',
            )}
          >
            <span className="flex items-start justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-sm font-semibold">Tạo series mới</span>
                <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                  Dùng khi chương này bắt đầu một bộ truyện mới trong Story Studio.
                </span>
              </span>
              {newSeriesSelected ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              ) : null}
            </span>
            <span className="mt-4 inline-flex rounded-full border border-border/70 px-2.5 py-1 text-xs text-muted-foreground">
              Tạo series + tập mới
            </span>
          </button>
          <button
            type="button"
            aria-pressed={existingSeriesSelected}
            disabled={props.disabled}
            onClick={() => props.setTargetKind('existing_series')}
            className={cn(
              'min-h-[128px] cursor-pointer rounded-xl border border-border bg-background/90 p-4 text-left shadow-sm transition duration-200 hover:border-primary/50 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60',
              existingSeriesSelected && 'border-primary/80 bg-muted/45 ring-2 ring-primary/45',
            )}
          >
            <span className="flex items-start justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-sm font-semibold">Thêm vào series hiện có</span>
                <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                  Tạo tập tiếp theo và giữ bộ nhớ, nhân vật, bối cảnh của series đã chọn.
                </span>
              </span>
              {existingSeriesSelected ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              ) : null}
            </span>
            <span className="mt-4 inline-flex rounded-full border border-border/70 px-2.5 py-1 text-xs text-muted-foreground">
              Nối vào continuity cũ
            </span>
          </button>
        </fieldset>

        <div className="space-y-4 rounded-xl border border-border/70 bg-background/60 p-4">
          {newSeriesSelected ? (
            <div className="space-y-3">
              <label htmlFor="comic-handoff-series-title" className="grid gap-1.5 text-sm">
                <span className="font-medium">Tên series mới</span>
                <Input
                  id="comic-handoff-series-title"
                  value={props.seriesTitle}
                  disabled={props.disabled}
                  onChange={(event) => props.setSeriesTitle(event.target.value)}
                  placeholder={props.defaultSeriesTitle || 'Nhập tên series mới'}
                  className="min-h-11 bg-card/70"
                />
                <span className="text-xs leading-relaxed text-muted-foreground">
                  Bỏ trống để dùng tên job phân tích hiện tại.
                </span>
              </label>

              <div>
                <p className="text-sm font-medium">Loại series mới</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Mặc định là truyện ảnh. Chọn hybrid nếu sau này series này cũng cần dùng cho video.
                </p>
              </div>
              <fieldset className="grid gap-2 border-0 p-0 sm:grid-cols-2">
                <legend className="sr-only">Loại series mới</legend>
                {(
                  [
                    ['image_story_only', 'Series truyện ảnh', 'Tối ưu cho Story Studio và tạo truyện ảnh.'],
                    ['hybrid', 'Series truyện + video', 'Giữ khả năng mở rộng sang video về sau.'],
                  ] as const
                ).map(([mode, title, description]) => {
                  const selected = props.seriesMode === mode;
                  return (
                    <button
                      key={mode}
                      type="button"
                      aria-pressed={selected}
                      disabled={props.disabled}
                      onClick={() => props.setSeriesMode(mode)}
                      className={cn(
                        'min-h-20 cursor-pointer rounded-lg border border-border bg-background/90 p-3 text-left shadow-sm transition duration-200 hover:border-primary/50 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60',
                        selected && 'border-primary/80 bg-muted/45 ring-1 ring-primary/50',
                      )}
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="font-medium">{title}</span>
                        {selected ? <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" /> : null}
                      </span>
                      <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                        {description}
                      </span>
                    </button>
                  );
                })}
              </fieldset>
            </div>
          ) : (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">Series hiện có</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    Chọn series truyện ảnh/hybrid để tạo tập tiếp theo.
                  </p>
                </div>
                {props.selectedSeries ? (
                  <Badge variant="secondary" className="shrink-0 rounded-full">
                    Đã chọn
                  </Badge>
                ) : null}
              </div>
              {props.seriesError ? (
                <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-relaxed text-destructive" role="alert">
                  {props.seriesError}
                </p>
              ) : !props.loadingSeries && !props.seriesOptions.length ? (
                <p className="rounded-lg border border-dashed p-4 text-xs leading-relaxed text-muted-foreground">
                  Chưa có series truyện ảnh/hybrid để chọn. Hãy tạo series mới hoặc tạo một series
                  phù hợp trước.
                </p>
              ) : (
                <div className="rounded-lg border border-border bg-background/90 p-3">
                  {props.selectedSeries ? (
                    <div className="min-w-0">
                      <p className="line-clamp-2 text-sm font-medium">{props.selectedSeries.title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {comicSeriesModeLabel(props.selectedSeries.series_mode)} · Tập hiện tại:{' '}
                        {props.selectedSeries.latest_episode_number || 0} ·{' '}
                        {props.selectedSeries.character_profiles?.length ?? 0} hồ sơ nhân vật
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Mở popup để xem Bible, số tập, nhân vật và chọn series phù hợp.
                    </p>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    disabled={props.disabled || props.loadingSeries}
                    onClick={props.onOpenSeriesPicker}
                  >
                    {props.loadingSeries ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <BookOpen className="h-4 w-4" />
                    )}
                    Chọn series
                  </Button>
                </div>
              )}
            </div>
          )}

          <label htmlFor="comic-handoff-episode-title" className="grid gap-1.5 text-sm">
            <span className="font-medium">Tiêu đề tập</span>
            <Input
              id="comic-handoff-episode-title"
              value={props.episodeTitle}
              disabled={props.disabled}
              onChange={(event) => props.setEpisodeTitle(event.target.value)}
              placeholder={props.defaultEpisodeTitle || 'Dùng tiêu đề từ kịch bản tối ưu'}
              className="min-h-11 bg-card/70"
            />
            <span className="text-xs leading-relaxed text-muted-foreground">
              Bỏ trống để dùng tiêu đề từ kịch bản tối ưu.
            </span>
          </label>

          <label htmlFor="comic-handoff-episode-number" className="grid gap-1.5 text-sm">
            <span className="font-medium">Số tập</span>
            <Input
              id="comic-handoff-episode-number"
              type="number"
              min={1}
              step={1}
              value={props.episodeNumber}
              disabled={props.disabled}
              aria-invalid={!props.episodeNumberValid}
              aria-describedby="comic-handoff-episode-number-help"
              onChange={(event) => props.setEpisodeNumber(event.target.value)}
              placeholder={
                props.selectedSeries
                  ? `Tự động: ${props.selectedSeries.latest_episode_number + 1}`
                  : 'Tự động'
              }
              className="min-h-11 bg-card/70"
            />
            <span
              id="comic-handoff-episode-number-help"
              className={cn(
                'text-xs leading-relaxed',
                props.episodeNumberValid ? 'text-muted-foreground' : 'text-destructive',
              )}
              role={props.episodeNumberValid ? undefined : 'alert'}
            >
              {props.episodeNumberValid
                ? 'Bỏ trống để backend tự lấy số tập tiếp theo.'
                : 'Số tập phải là số nguyên lớn hơn 0.'}
            </span>
          </label>
          <HandoffEpisodeSettingsFields
            disabled={props.disabled}
            seriesMode={props.targetKind === 'existing_series' ? props.selectedSeries?.series_mode : props.seriesMode}
            outputIntent={props.outputIntent}
            effectiveOutputIntent={props.effectiveOutputIntent}
            setOutputIntent={props.setOutputIntent}
            marketProfile={props.marketProfile}
            setMarketProfile={props.setMarketProfile}
            languageProfile={props.languageProfile}
            setLanguageProfile={props.setLanguageProfile}
            sourceInput={props.sourceInput}
            setSourceInput={props.setSourceInput}
            outputSettings={props.outputSettings}
            setOutputSettings={props.setOutputSettings}
          />
        </div>
      </div>
    </section>
  );
}

function HandoffEpisodeSettingsFields(props: {
  disabled: boolean;
  seriesMode: SeriesMode | undefined;
  outputIntent: StoryOutputIntent;
  effectiveOutputIntent: StoryOutputIntent;
  setOutputIntent: (value: StoryOutputIntent) => void;
  marketProfile: string;
  setMarketProfile: (value: string) => void;
  languageProfile: string;
  setLanguageProfile: (value: string) => void;
  sourceInput: string;
  setSourceInput: (value: string) => void;
  outputSettings: StoryEpisodeOutputSettings;
  setOutputSettings: (value: StoryEpisodeOutputSettings | ((current: StoryEpisodeOutputSettings) => StoryEpisodeOutputSettings)) => void;
}) {
  const imageOnly = props.seriesMode === 'image_story_only';
  const updateOutputSettings = (
    updater: (current: StoryEpisodeOutputSettings) => StoryEpisodeOutputSettings,
  ) => props.setOutputSettings(updater);
  const selectedLanguageProfile = props.languageProfile as VideoLanguage;
  const hasPromptSegmentSettings = Boolean(
    props.outputSettings.video.prompt_segment_count &&
      props.outputSettings.video.prompt_segment_duration_seconds,
  );
  const selectedMarketOption = storyMarketOptions.find((option) => option.value === props.marketProfile);

  return (
    <div className="space-y-3 rounded-xl border border-border/70 bg-card/55 p-4">
      <div>
        <p className="text-sm font-semibold">Cấu hình tập Story Studio</p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Các giá trị này sẽ được lưu vào episode tạo từ phân tích web/comic và dùng trước khi bấm “Tạo 3 hướng”.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <label className="grid gap-1.5 text-xs font-medium">
          Đầu ra
          <select
            value={props.effectiveOutputIntent}
            disabled={props.disabled || imageOnly}
            onChange={(event) => props.setOutputIntent(event.target.value as StoryOutputIntent)}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10 disabled:opacity-60"
          >
            <option value="truyen_anh">Truyện ảnh</option>
            <option value="video_truyen">Video truyện</option>
            <option value="ca_hai">Cả hai</option>
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Thị trường nội dung
          <select
            value={props.marketProfile}
            disabled={props.disabled}
            onChange={(event) => props.setMarketProfile(event.target.value)}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {storyMarketOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="text-[11px] font-normal leading-5 text-muted-foreground">
            {selectedMarketOption?.helper ??
              'Ảnh hưởng cách kể, văn hoá và nhịp nội dung; không phải ngôn ngữ giao diện.'}
          </span>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Ngôn ngữ truyện/video
          <select
            value={selectedLanguageProfile}
            disabled={props.disabled}
            onChange={(event) => {
              const targetLanguage = event.target.value as VideoLanguage;
              props.setLanguageProfile(targetLanguage);
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  target_language: targetLanguage,
                },
              }));
            }}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
                        {LANGUAGE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
          <span className="text-[11px] font-normal leading-5 text-muted-foreground">
            Dùng để tạo lời thoại, kịch bản, phụ đề và thuyết minh; không đổi ngôn ngữ app.
          </span>
        </label>
      </div>

      <div className="grid gap-2 border-t border-border/60 pt-3 sm:grid-cols-2">
        <label className="grid gap-1.5 text-xs font-medium">
          Số ảnh
          <select
            value={props.outputSettings.image.panel_mode}
            disabled={props.disabled}
            onChange={(event) => {
              const panelMode = event.target.value as StoryImagePanelMode;
              updateOutputSettings((current) => ({
                ...current,
                image: {
                  ...current.image,
                  panel_mode: panelMode,
                  panel_count: panelMode === 'manual' ? current.image.panel_count ?? 24 : null,
                },
              }));
            }}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            <option value="auto">{panelModeLabel('auto')}</option>
            <option value="manual">{panelModeLabel('manual')}</option>
          </select>
        </label>
        <label
          htmlFor="comic-output-image-panel-count"
          className="grid gap-1.5 text-xs font-medium"
        >
          Panel ảnh
          <Input
            id="comic-output-image-panel-count"
            type="number"
            min={1}
            max={200}
            value={props.outputSettings.image.panel_count ?? ''}
            disabled={props.disabled || props.outputSettings.image.panel_mode !== 'manual'}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                image: {
                  ...current.image,
                  panel_count: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
            placeholder="Auto"
          />
        </label>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <label className="grid gap-1.5 text-xs font-medium">
          Tỷ lệ ảnh
          <select
            value={props.outputSettings.image.aspect_ratio}
            disabled={props.disabled}
            onChange={(event) => {
              const aspectRatio = event.target.value as StoryImageAspectRatio;
              const size = imageAspectSizes[aspectRatio];
              updateOutputSettings((current) => ({
                ...current,
                image: {
                  ...current.image,
                  aspect_ratio: aspectRatio,
                  width: size.width,
                  height: size.height,
                },
              }));
            }}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {storyImageAspectOptions.map((aspectRatio) => (
              <option key={aspectRatio} value={aspectRatio}>
                {aspectRatio}
              </option>
            ))}
          </select>
        </label>
        <label
          htmlFor="comic-output-image-width"
          className="grid gap-1.5 text-xs font-medium"
        >
          Rộng
          <Input
            id="comic-output-image-width"
            type="number"
            min={256}
            max={8192}
            value={props.outputSettings.image.width}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                image: {
                  ...current.image,
                  width: optionalPositiveInt(event.target.value) ?? 720,
                },
              }))
            }
            className="h-10 bg-background"
          />
        </label>
        <label
          htmlFor="comic-output-image-height"
          className="grid gap-1.5 text-xs font-medium"
        >
          Cao
          <Input
            id="comic-output-image-height"
            type="number"
            min={256}
            max={8192}
            value={props.outputSettings.image.height}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                image: {
                  ...current.image,
                  height: optionalPositiveInt(event.target.value) ?? 1280,
                },
              }))
            }
            className="h-10 bg-background"
          />
        </label>
      </div>

      <div className="grid gap-2 border-t border-border/60 pt-3 sm:grid-cols-2">
        <label className="grid gap-1.5 text-xs font-medium">
          Tỷ lệ video
          <select
            value={props.outputSettings.video.aspect_ratio}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  aspect_ratio: event.target.value as StoryVideoAspectRatio,
                },
              }))
            }
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {storyVideoAspectOptions.map((aspectRatio) => (
              <option key={aspectRatio} value={aspectRatio}>
                {aspectRatio}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Ngôn ngữ video
          <select
            value={props.outputSettings.video.target_language}
            disabled={props.disabled}
            onChange={(event) => {
              const targetLanguage = event.target.value as VideoLanguage;
              props.setLanguageProfile(targetLanguage);
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  target_language: targetLanguage,
                },
              }));
            }}
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Mục đích video
          <select
            value={props.outputSettings.video.video_purpose}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  video_purpose: event.target.value as VideoPurpose,
                },
              }))
            }
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
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
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Thoại
          <select
            value={props.outputSettings.video.dialogue_mode}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  dialogue_mode: event.target.value as DialogueMode,
                },
              }))
            }
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {(['voiceover', 'character_lines', 'mixed'] as DialogueMode[]).map((mode) => (
              <option key={mode} value={mode}>
                {dialogueModeLabel(mode)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Mật độ lời
          <select
            value={props.outputSettings.video.narration_density}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  narration_density: event.target.value as NarrationDensity,
                },
              }))
            }
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {(['light', 'balanced', 'dense'] as NarrationDensity[]).map((density) => (
              <option key={density} value={density}>
                {narrationDensityLabel(density)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Lời kêu gọi hành động
          <select
            value={props.outputSettings.video.call_to_action_style ?? 'none'}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  call_to_action_style: event.target.value as CallToActionStyle,
                },
              }))
            }
            className="h-10 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
          >
            {(['none', 'soft', 'direct', 'urgent'] as CallToActionStyle[]).map((style) => (
              <option key={style} value={style}>
                {callToActionStyleLabel(style)}
              </option>
            ))}
          </select>
          <span className="text-[11px] font-normal leading-5 text-muted-foreground">
            Câu nhắc người xem ở cuối video. Chọn Không dùng nếu chỉ muốn kể truyện.
          </span>
        </label>
      </div>

      <div
        className={cn(
          'rounded-lg border px-3 py-2 text-xs leading-5',
          hasPromptSegmentSettings
            ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100'
            : 'border-border/70 bg-background/60 text-muted-foreground',
        )}
      >
        <span className="font-semibold text-foreground">Cách chia video: </span>
        {videoDurationSummary(props.outputSettings.video)}
        <span className="mt-1 block text-muted-foreground">
          Có thể dùng cách dễ là chỉ nhập Thời lượng video, hoặc cách kiểm soát là nhập Số prompt video + Giây mỗi prompt.
        </span>
      </div>

      <div className="grid min-w-0 gap-2 sm:grid-cols-2">
        <label
          htmlFor="comic-output-video-duration"
          className="grid gap-1.5 text-xs font-medium"
        >
          Thời lượng video
          <Input
            id="comic-output-video-duration"
            type="number"
            min={5}
            max={7200}
            value={props.outputSettings.video.target_duration_seconds ?? ''}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  target_duration_seconds: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
            placeholder="Auto"
          />
        </label>
        <label
          htmlFor="comic-output-video-shot-duration"
          className="grid gap-1.5 text-xs font-medium"
        >
          Giây mỗi shot
          <Input
            id="comic-output-video-shot-duration"
            type="number"
            min={1}
            max={5}
            value={props.outputSettings.video.default_shot_duration_seconds ?? ''}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  default_shot_duration_seconds: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
          />
        </label>
        <label
          htmlFor="comic-output-video-prompt-count"
          className="grid gap-1.5 text-xs font-medium"
        >
          Số prompt video
          <Input
            id="comic-output-video-prompt-count"
            type="number"
            min={1}
            max={100}
            value={props.outputSettings.video.prompt_segment_count ?? ''}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  prompt_segment_count: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
            placeholder="Auto"
          />
        </label>
        <label
          htmlFor="comic-output-video-prompt-duration"
          className="grid gap-1.5 text-xs font-medium"
        >
          Giây mỗi prompt
          <Input
            id="comic-output-video-prompt-duration"
            type="number"
            min={3}
            max={30}
            value={props.outputSettings.video.prompt_segment_duration_seconds ?? ''}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  prompt_segment_duration_seconds: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
            placeholder="Auto"
          />
        </label>
        <label
          htmlFor="comic-output-video-micro-scenes"
          className="grid gap-1.5 text-xs font-medium"
        >
          Cảnh nhỏ / prompt
          <Input
            id="comic-output-video-micro-scenes"
            type="number"
            min={1}
            max={5}
            value={props.outputSettings.video.micro_scenes_per_prompt ?? ''}
            disabled={props.disabled}
            onChange={(event) =>
              updateOutputSettings((current) => ({
                ...current,
                video: {
                  ...current.video,
                  micro_scenes_per_prompt: optionalPositiveInt(event.target.value),
                },
              }))
            }
            className="h-10 bg-background"
          />
        </label>
      </div>

      <label className="grid gap-1.5 text-xs font-medium">
        Ghi chú nguồn bổ sung
        <textarea
          value={props.sourceInput}
          disabled={props.disabled}
          onChange={(event) => props.setSourceInput(event.target.value)}
          className="min-h-24 rounded-lg border border-input bg-background px-3 py-3 text-sm leading-relaxed outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10 disabled:opacity-60"
          placeholder="Yêu cầu thêm cho tập này; dữ liệu phân tích web/comic vẫn được handoff tự động."
        />
      </label>
    </div>
  );
}

function CapabilityPanel({ caps }: { caps: ComicCapabilitiesResponse | undefined }) {
  const codecs = caps?.codecs.codecs ?? {};
  const svgStatus = codecs.svg?.status ?? 'checking';
  const heifStatus = codecs.heif?.status ?? 'checking';
  const avifStatus = codecs.avif?.status ?? 'checking';
  return (
    <section className="rounded-lg border border-border/80 bg-card/60 p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background">
          <CheckCircle2 className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Sẵn sàng phân tích</h2>
          <p className="truncate text-xs text-muted-foreground">
            Codec ảnh và handoff Story Studio
          </p>
        </div>
      </div>
      <div className="mt-4 space-y-2 text-sm">
        <div className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/60 p-3">
          <span className="text-muted-foreground">SVG</span>
          <Badge variant={svgStatus === 'ok' ? 'default' : 'secondary'}>{svgStatus}</Badge>
        </div>
        <div className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/60 p-3">
          <span className="text-muted-foreground">HEIF / AVIF</span>
          <Badge variant={heifStatus === 'ok' && avifStatus === 'ok' ? 'default' : 'secondary'}>
            {heifStatus} · {avifStatus}
          </Badge>
        </div>
      </div>
    </section>
  );
}

function CreatePanel(props: {
  url: string;
  setUrl: (value: string) => void;
  readingMode: string;
  setReadingMode: (value: string) => void;
  rightsAttested: boolean;
  setRightsAttested: (value: boolean) => void;
  onCreateUrl: () => void;
  onUpload: (files: File[]) => void;
  creating: boolean;
  error: string | null;
}) {
  return (
    <section className="rounded-lg border border-border/80 bg-card/65 p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background">
          <LinkIcon className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-semibold">Nguồn truyện</h2>
          <p className="text-xs text-muted-foreground">
            Link chương truyện hoặc upload ảnh thủ công
          </p>
        </div>
      </div>
      <div className="mt-5 flex flex-col gap-3">
        <div className="grid gap-2">
          <Input
            aria-label="Liên kết chương truyện"
            placeholder="https://... link chương truyện"
            value={props.url}
            onChange={(event) => props.setUrl(event.target.value)}
            className="min-h-11"
          />
          <select
            aria-label="Chế độ đọc truyện"
            className="min-h-11 rounded-md border bg-background px-3 text-sm"
            value={props.readingMode}
            onChange={(event) => props.setReadingMode(event.target.value)}
          >
            {READING_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          <Button
            onClick={props.onCreateUrl}
            disabled={!props.url.trim() || props.creating}
            className="min-h-11 w-full"
          >
            {props.creating ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Tạo từ link'}
          </Button>
          <label className="inline-flex">
            <input
              type="file"
              accept="image/*,.heic,.heif,.avif,.svg"
              multiple
              hidden
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (files.length) props.onUpload(files);
                event.target.value = '';
              }}
            />
            <Button variant="outline" asChild className="min-h-11 w-full">
              <span className="inline-flex cursor-pointer items-center justify-center gap-1">
                <Upload className="h-4 w-4" /> Upload ảnh
              </span>
            </Button>
          </label>
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={props.rightsAttested}
            onChange={(event) => props.setRightsAttested(event.target.checked)}
          />
          Tôi xác nhận có quyền phân tích / sử dụng nội dung nguồn này.
        </label>
        {props.error ? (
          <p className="text-sm text-destructive" role="alert">
            {props.error}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function JobList(props: {
  jobs: ComicJobSummary[];
  total: number;
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  selectedJobId: string | null;
  onSelect: (id: string) => void;
  onLoadMore: () => void;
}) {
  if (props.loading) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-lg border">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!props.jobs.length) {
    return (
      <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
        Chưa có lần phân tích nào.
      </div>
    );
  }
  return (
    <div>
      <ul className="flex flex-col gap-2">
        {props.jobs.map((job) => {
          const percent = comicJobPercent(job);
          const tone = comicProgressTone(job);
          const active = isComicJobActive(job);
          return (
            <li key={job.id}>
              <button
                type="button"
                onClick={() => props.onSelect(job.id)}
                className={cn(
                  'min-h-[108px] w-full cursor-pointer rounded-lg border bg-background/85 p-3 text-left shadow-sm transition duration-200 hover:border-primary/50 hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  props.selectedJobId === job.id && 'border-primary/80 bg-muted/50 ring-1 ring-primary/35',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 font-medium">{job.title || job.id.slice(0, 8)}</span>
                  <Badge variant={statusVariant(job.run_status)} className="shrink-0">
                    {STATUS_LABELS[job.run_status] ?? job.run_status}
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {job.source_type === 'url' ? 'Nguồn web' : 'Upload ảnh'} · revision{' '}
                  {job.analysis_revision}
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <ComicProgressBar
                    percent={percent}
                    tone={tone}
                    active={active}
                    className="h-1.5 flex-1 bg-muted"
                    ariaLabel={`Tiến độ ${job.title || job.id}`}
                  />
                  <span className="w-9 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
                    {percent}%
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      {props.hasMore ? (
        <div className="mt-3 flex justify-center">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={props.loadingMore}
            onClick={props.onLoadMore}
          >
            {props.loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Tải thêm ({props.jobs.length}/{props.total})
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function AnalysisResults(props: {
  packageValue: ComicAnalysisPackage | null;
  loading: boolean;
  limitations: unknown[];
  finalized: boolean;
}) {
  if (props.loading) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-lg border">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  const packageValue = props.packageValue;
  if (!packageValue || packageValue.analysis_revision <= 0) {
    return (
      <section className="rounded-lg border border-dashed p-10 text-center">
        <Sparkles className="mx-auto h-6 w-6 text-muted-foreground" />
        <h3 className="mt-3 font-semibold">Chưa có package phân tích</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Bấm “Phân tích truyện” để đọc hình ảnh, chữ, nhân vật, bối cảnh và cốt truyện.
        </p>
      </section>
    );
  }

  return (
    <Tabs defaultValue="content" className="min-w-0">
      <TabsList className="h-auto w-full flex-wrap justify-start rounded-lg p-1">
        <TabsTrigger value="content" className="min-h-10">
          <Sparkles className="mr-2 h-4 w-4" />
          Kịch bản tối ưu
        </TabsTrigger>
        <TabsTrigger value="visual" className="min-h-10">
          <ImageIcon className="mr-2 h-4 w-4" />
          Hình ảnh ({packageValue.panels.length})
        </TabsTrigger>
        <TabsTrigger value="text" className="min-h-10">
          <Quote className="mr-2 h-4 w-4" />
          Chữ &amp; thoại ({packageValue.dialogues.length})
        </TabsTrigger>
        <TabsTrigger value="characters" className="min-h-10">
          <Users className="mr-2 h-4 w-4" />
          Nhân vật ({packageValue.characters.length})
        </TabsTrigger>
        <TabsTrigger value="locations" className="min-h-10">
          <MapPin className="mr-2 h-4 w-4" />
          Bối cảnh ({packageValue.locations.length})
        </TabsTrigger>
        <TabsTrigger value="plot" className="min-h-10">
          <FileText className="mr-2 h-4 w-4" />
          Cốt truyện
        </TabsTrigger>
        <TabsTrigger value="warnings" className="min-h-10">
          <AlertTriangle className="mr-2 h-4 w-4" />
          Cảnh báo
        </TabsTrigger>
      </TabsList>

      <TabsContent value="content" className="mt-4">
        <section className="rounded-lg border border-border/80 bg-card/65 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">Kịch bản tối ưu</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Revision phân tích {packageValue.analysis_revision}
                {!props.finalized ? ' · đang nhận từng batch từ Codex' : ''}
              </p>
            </div>
            {packageValue.optimized_script ? (
              <Badge className="gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Sẵn sàng handoff
              </Badge>
            ) : !props.finalized ? (
              <Badge variant="secondary" className="gap-1">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Đang cập nhật package
              </Badge>
            ) : null}
          </div>
          {packageValue.optimized_script ? (
            <div className="mt-5 space-y-4">
              <div>
                <h4 className="text-lg font-semibold">{packageValue.optimized_script.title}</h4>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {packageValue.optimized_script.synopsis}
                </p>
              </div>
              <div className="rounded-lg border bg-background/60 p-4">
                <p className="text-sm font-semibold">Hook</p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
                  {packageValue.optimized_script.hook}
                </p>
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <ScriptList title="Plot beats" items={packageValue.optimized_script.plot_beats} />
                <ScriptList title="Scene outline" items={packageValue.optimized_script.scene_outline} />
                <ScriptList title="Character arcs" items={packageValue.optimized_script.character_arcs} />
              </div>
              <div className="rounded-lg border bg-background/60 p-4">
                <p className="text-sm font-semibold">Toàn bộ kịch bản</p>
                <p className="mt-2 max-h-[480px] overflow-y-auto whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
                  {packageValue.optimized_script.full_story}
                </p>
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {props.finalized
                ? 'Kết quả phân tích đã sẵn sàng. Bấm “Viết kịch bản tối ưu” để tạo nội dung đưa sang Story Studio.'
                : 'Hệ thống đang nhận dữ liệu phân tích theo từng batch. Nút viết kịch bản và handoff sẽ mở khi revision hoàn tất.'}
            </div>
          )}
        </section>
      </TabsContent>

      <TabsContent value="visual" className="mt-4">
        <ResultGrid empty="Chưa nhận diện được mô tả hình ảnh.">
          {packageValue.panels.map((panel) => (
            <article key={panel.id} className="overflow-hidden rounded-lg border bg-card/65">
              {panel.asset_id ? (
                <img
                  src={apiClient.getComicAssetPreviewUrl(panel.asset_id)}
                  alt={`Panel ${panel.reading_order + 1}: ${panel.visual_description || 'chưa có mô tả'}`}
                  loading="lazy"
                  className="aspect-video w-full bg-muted object-contain"
                />
              ) : null}
              <div className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">Panel {panel.reading_order + 1}</p>
                  <ConfidenceBadge value={panel.confidence} />
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {panel.visual_description || 'Cần review thủ công vì chưa có mô tả visual.'}
                </p>
              </div>
            </article>
          ))}
        </ResultGrid>
      </TabsContent>

      <TabsContent value="text" className="mt-4">
        <ResultGrid empty="Chưa OCR hoặc nhận diện được lời thoại.">
          {packageValue.dialogues.map((item) => (
            <article key={item.id} className="rounded-lg border bg-card/65 p-4">
              <div className="flex items-center justify-between gap-2">
                <Badge variant="secondary">{item.bubble_type}</Badge>
                <ConfidenceBadge value={item.confidence} />
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">
                {item.text || 'Không có nội dung'}
              </p>
            </article>
          ))}
        </ResultGrid>
      </TabsContent>

      <TabsContent value="characters" className="mt-4">
        <ResultGrid empty="Chưa nhận diện được nhân vật.">
          {packageValue.characters.map((item) => (
            <article key={item.id} className="rounded-lg border bg-card/65 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{item.name || 'Nhân vật chưa đặt tên'}</h3>
                  <p className="text-sm text-muted-foreground">
                    {item.role || 'Chưa xác định vai trò'}
                  </p>
                </div>
                <ConfidenceBadge value={item.confidence} />
              </div>
              <dl className="mt-4 grid gap-2 text-sm">
                <Detail label="Khuôn mặt" value={item.face_description} />
                <Detail label="Tóc" value={item.hair_description} />
                <Detail label="Trang phục" value={item.outfit_description} />
                <Detail label="Tính cách" value={item.personality} />
                <Detail label="Cách nói" value={item.speech_style} />
              </dl>
            </article>
          ))}
        </ResultGrid>
      </TabsContent>

      <TabsContent value="locations" className="mt-4">
        <ResultGrid empty="Chưa nhận diện được bối cảnh.">
          {packageValue.locations.map((item) => (
            <article key={item.id} className="rounded-lg border bg-card/65 p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-semibold">{item.name || 'Bối cảnh chưa đặt tên'}</h3>
                <ConfidenceBadge value={item.confidence} />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {item.description || 'Chưa có mô tả.'}
              </p>
              {item.world_rules ? (
                <p className="mt-3 rounded-md bg-muted/50 p-3 text-sm">
                  <span className="font-medium">Quy tắc thế giới:</span> {item.world_rules}
                </p>
              ) : null}
            </article>
          ))}
        </ResultGrid>
      </TabsContent>

      <TabsContent value="plot" className="mt-4">
        <section className="space-y-4 rounded-lg border bg-card/65 p-5">
          <div>
            <h3 className="font-semibold">Tóm tắt</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
              {packageValue.plot.synopsis || 'Chưa có tóm tắt cốt truyện.'}
            </p>
          </div>
          <div>
            <h3 className="font-semibold">Plot beats</h3>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
              {(packageValue.plot.plot_beats ?? []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </div>
          {(packageValue.plot.relationships ?? []).length ? (
            <div>
              <h3 className="font-semibold">Quan hệ</h3>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg bg-muted/50 p-4 text-xs">
                {formatUnknown(packageValue.plot.relationships)}
              </pre>
            </div>
          ) : null}
        </section>
      </TabsContent>

      <TabsContent value="warnings" className="mt-4">
        <section className="rounded-lg border bg-card/65 p-5">
          {props.limitations.length ? (
            <ul className="space-y-3">
              {Array.from(new Set(props.limitations.map(formatUnknown))).map((message) => (
                <li
                  key={message}
                  className="flex gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-sm"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                  <span className="break-words">{message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              Không có cảnh báo phân tích.
            </p>
          )}
        </section>
      </TabsContent>
    </Tabs>
  );
}

function ResultGrid(props: { children: ReactNode; empty: string }) {
  const items = Array.isArray(props.children)
    ? props.children.filter(Boolean)
    : props.children
      ? [props.children]
      : [];
  if (!items.length)
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        {props.empty}
      </div>
    );
  return <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{props.children}</div>;
}

function ScriptList({ title, items }: { title: string; items?: string[] | null }) {
  const values = items?.filter((item) => item.trim()) ?? [];
  return (
    <div className="rounded-lg border bg-background/60 p-4">
      <p className="text-sm font-semibold">{title}</p>
      {values.length ? (
        <ol className="mt-3 max-h-64 list-decimal space-y-2 overflow-y-auto pl-5 text-sm leading-relaxed text-muted-foreground">
          {values.map((item, index) => (
            <li key={`${title}-${index}-${item.slice(0, 32)}`}>{item}</li>
          ))}
        </ol>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Chưa có dữ liệu.</p>
      )}
    </div>
  );
}

function ConfidenceBadge({ value }: { value?: number | null }) {
  const label = confidenceLabel(value);
  return label ? (
    <Badge variant="secondary" className="shrink-0">
      {label}
    </Badge>
  ) : null;
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[96px_1fr] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
