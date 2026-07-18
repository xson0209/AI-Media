import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleStop,
  FileText,
  FileVideo,
  Film,
  Image as ImageIcon,
  Languages,
  Link as LinkIcon,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
  Volume2,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { AI_VIDEO_DRAFT_STORAGE_KEY, type AIVideoFormDraft } from '@/lib/aiVideoDraft';
import { apiClient } from '@/lib/api/client';
import { ALL_LANGUAGES, LANGUAGE_OPTIONS } from '@/lib/constants/languages';
import { useProfiles } from '@/lib/hooks/useProfiles';
import type {
  VideoInspirationAnalysisMode,
  VideoInspirationHandoffResponse,
  VideoInspirationJobResponse,
  VideoInspirationTargetLanguage,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

const STEP_LABELS: Record<string, string> = {
  queued: 'Đang chờ đến lượt xử lý',
  source_ready: 'Đã nhận video',
  downloading: 'Đang lấy video từ link',
  extract_audio: 'Đang tách lời nói',
  transcribe: 'Đang chuyển lời nói thành chữ',
  extract_frames: 'Đang lấy hình ảnh đại diện',
  visual_analysis: 'Đang phân tích hình ảnh',
  content_analysis: 'Đang phân tích nội dung',
  rewrite: 'Đang viết kịch bản tối ưu',
  rewrite_brief: 'Đang tạo brief kịch bản',
  rewrite_candidates: 'Đang tạo các bản nháp',
  rewrite_review: 'Đang chấm điểm bản nháp',
  rewrite_synthesis: 'Đang tổng hợp bản cuối',
  handoff: 'Đang chuyển sang Video AI',
  retrying: 'Đang xếp lịch chạy lại',
  cancelling: 'Đang hủy tác vụ',
  cancelled: 'Đã hủy',
  completed: 'Hoàn tất',
  failed: 'Đã lỗi',
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Đã tải lên',
  queued: 'Đang xếp hàng',
  analyzing: 'Đang phân tích',
  analyzed: 'Đã phân tích',
  transcript_edited: 'Đã sửa transcript',
  direction_edited: 'Đã lưu định hướng',
  rewriting: 'Đang viết lại',
  rewritten: 'Đã có kịch bản tối ưu',
  handoff: 'Đang chuyển tiếp',
  retrying: 'Đang chạy lại',
  cancelling: 'Đang hủy',
  cancelled: 'Đã hủy',
  ai_video_ready: 'Đã chuyển sang Video AI',
  failed: 'Có lỗi',
};

const ACTIVE_JOB_STATUSES = new Set([
  'queued',
  'analyzing',
  'rewriting',
  'handoff',
  'retrying',
  'cancelling',
]);

const ANALYSIS_LABELS: Record<string, string> = {
  main_idea_vi: 'Ý chính',
  hook_vi: 'Hook gốc',
  structure_vi: 'Cấu trúc',
  characters_context_vi: 'Nhân vật / bối cảnh',
  visual_rhythm_vi: 'Nhịp hình ảnh',
  strengths_vi: 'Điểm mạnh',
  weaknesses_vi: 'Điểm yếu',
  rewrite_opportunities_vi: 'Cơ hội viết mới',
  notes_vi: 'Ghi chú',
};

const AI_VIDEO_DRAFT_SECTION_MAX_LENGTH = 28000;
const AI_VIDEO_VISUAL_STYLE_MAX_LENGTH = 2000;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

function languageLabel(language: VideoInspirationTargetLanguage): string {
  return ALL_LANGUAGES[language] ?? String(language);
}

function jobTitle(job: VideoInspirationJobResponse): string {
  return (
    job.script_title ||
    job.original_filename ||
    (job.source_type === 'url' ? job.source_platform : 'Video mới')
  );
}

function statusLabel(job?: VideoInspirationJobResponse | null): string {
  if (!job) return 'Chưa có video';
  if (isJobStale(job)) return 'Bị gián đoạn';
  return STATUS_LABELS[job.status] || 'Đang xử lý';
}

function stepLabel(job?: VideoInspirationJobResponse | null): string {
  if (!job) return 'Hãy upload MP4 hoặc dán link công khai';
  if (isJobStale(job)) {
    return job.stale_reason || 'Job bị gián đoạn quá lâu. Bấm chạy lại phân tích để tiếp tục.';
  }
  return STEP_LABELS[job.current_step] || STATUS_LABELS[job.status] || 'Hệ thống đang xử lý job này';
}

function progressValue(job?: VideoInspirationJobResponse | null): number {
  if (!job) return 0;
  const value = Number(job.progress || 0);
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function isJobActive(job?: VideoInspirationJobResponse | null): boolean {
  return !!job && !isJobStale(job) && ACTIVE_JOB_STATUSES.has(job.status);
}

function isJobStale(job?: VideoInspirationJobResponse | null): boolean {
  return !!job?.is_stale;
}

function handoffStatusLabel(status: string | null | undefined): string {
  if (status === 'ready') return 'Sẵn sàng';
  if (status === 'created') return 'Đã tạo';
  if (status === 'project_created') return 'Đã tạo project';
  if (status === 'failed') return 'Có lỗi';
  if (status === 'cancelled') return 'Đã hủy';
  return 'Đã lưu';
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatSeconds(value: number | null | undefined): string {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds)) return '0.0s';
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return minutes > 0 ? `${minutes}:${rest.toFixed(1).padStart(4, '0')}` : `${rest.toFixed(1)}s`;
}

function percentMetric(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '0%';
  return `${Math.round(Math.max(0, Math.min(1, numeric)) * 100)}%`;
}

function completionLabel(value?: string | null): string {
  if (value === 'full') return 'Đầy đủ';
  if (value === 'partial') return 'Một phần';
  if (value === 'insufficient') return 'Thiếu dữ liệu';
  return 'Chưa chạy';
}

function analysisModeLabel(value: VideoInspirationAnalysisMode): string {
  return value === 'high_quality' ? 'Chất lượng cao' : 'Nhanh';
}

function formatAnalysisValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join('\n');
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value ?? '');
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function structuredPreview(value: unknown, limit = 1400): string {
  const format = (item: unknown): string => {
    if (Array.isArray(item)) {
      return item
        .slice(0, 8)
        .map((entry, index) => `${index + 1}. ${format(entry)}`)
        .join('\n');
    }
    if (item && typeof item === 'object') {
      return Object.entries(item as Record<string, unknown>)
        .filter(([, nested]) => nested !== null && nested !== undefined && String(nested).trim() !== '')
        .slice(0, 10)
        .map(([key, nested]) => `${key}: ${format(nested)}`)
        .join('\n');
    }
    return String(item ?? '').trim();
  };
  const text = format(value).trim();
  if (!text) return 'ChÆ°a cÃ³ dá»¯ liá»‡u.';
  return text.length > limit ? `${text.slice(0, limit).trimEnd()}...` : text;
}

function analysisEntries(job?: VideoInspirationJobResponse | null) {
  if (!job?.analysis_json) return [];
  return Object.entries(job.analysis_json).filter(([key]) => key !== 'rewrite' && !key.startsWith('rewrite_'));
}

function draftText(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((item) => draftText(item))
      .filter(Boolean)
      .join('\n');
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('title' in record || 'narration' in record || 'visual_suggestion' in record) {
      return [
        draftText(record.title),
        draftText(record.narration),
        draftText(record.visual_suggestion),
      ]
        .filter(Boolean)
        .join('\n');
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value ?? '').trim();
}

function analysisText(job: VideoInspirationJobResponse, key: string): string {
  return draftText(job.analysis_json?.[key]);
}

function rewritePayload(job: VideoInspirationJobResponse): Record<string, unknown> {
  const value = job.analysis_json?.rewrite;
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function rewriteSourceBlocks(rewrite: Record<string, unknown>): Record<string, unknown> {
  const value = rewrite.ai_video_source_blocks;
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function sourceBlockText(blocks: Record<string, unknown>, key: string): string {
  return draftText(blocks[key]);
}

function optimizedRewritePanels(job: VideoInspirationJobResponse) {
  const rewrite = rewritePayload(job);
  return [
    ['Hook 3-5 giây', firstDraftText(draftText(rewrite.hook_3_5s), job.hook || '', draftText(rewrite.hook))],
    ['Nhịp giữ chân', draftText(rewrite.retention_plan)],
    ['Âm thanh', firstDraftText(draftText(rewrite.sound_design_plan), draftText(rewrite.audio_direction))],
    ['Gợi ý hình ảnh', firstDraftText(draftText(rewrite.visual_suggestions), draftText(rewrite.segments))],
  ].filter(([, value]) => value.trim());
}

function truncateDraftText(value: string, limit: number): string {
  const text = value.trim();
  if (text.length <= limit) return text;
  const cut = text.slice(0, Math.max(0, limit - 3)).trimEnd();
  const boundary = Math.max(cut.lastIndexOf('\n'), cut.lastIndexOf('. '), cut.lastIndexOf('; '));
  if (boundary > cut.length * 0.55) return `${cut.slice(0, boundary + 1).trimEnd()}...`;
  return `${cut}...`;
}

function joinDraftSections(
  sections: Array<[string, string | null | undefined]>,
  limit = AI_VIDEO_DRAFT_SECTION_MAX_LENGTH,
): string {
  return sections
    .map(([label, value]) => {
      const text = (value || '').trim();
      return text ? `${label}:\n${text}` : '';
    })
    .filter(Boolean)
    .join('\n\n')
    .slice(0, limit);
}

function compactDraftSections(
  sections: Array<[string, string | null | undefined]>,
  sectionLimit: number,
  limit: number,
): string {
  return joinDraftSections(
    sections.map(([label, value]) => [
      label,
      value ? truncateDraftText(value, sectionLimit) : value,
    ]),
    limit,
  );
}

function firstDraftText(...values: Array<string | null | undefined>): string {
  return values.find((value) => value?.trim())?.trim() || '';
}

function frameDraftText(job: VideoInspirationJobResponse): string {
  return (job.frames ?? [])
    .map((frame, index) => {
      const description = frame.description_vi?.trim();
      if (!description) return '';
      return `Frame #${index + 1} (${frame.timestamp_seconds.toFixed(1)}s): ${description}`;
    })
    .filter(Boolean)
    .join('\n');
}

function buildAIVideoDraft(job: VideoInspirationJobResponse): AIVideoFormDraft {
  const rewrite = rewritePayload(job);
  const sourceBlocks = rewriteSourceBlocks(rewrite);
  const title = job.script_title || jobTitle(job);
  const hook3to5 = firstDraftText(
    draftText(rewrite.hook_3_5s),
    job.hook,
    draftText(rewrite.hook),
    analysisText(job, 'hook_vi'),
  );
  const bigIdea = firstDraftText(
    job.big_idea,
    draftText(rewrite.big_idea),
    analysisText(job, 'main_idea_vi'),
    job.rewritten_script,
  );
  const viewerQuestion = draftText(rewrite.viewer_question);
  const curiosityGap = draftText(rewrite.curiosity_gap);
  const retentionPlan = draftText(rewrite.retention_plan);
  const soundDesignPlan = draftText(rewrite.sound_design_plan);
  const audioDirection = draftText(rewrite.audio_direction);
  const visualSuggestions = firstDraftText(
    draftText(rewrite.visual_suggestions),
    draftText(rewrite.segments),
  );
  const userDirection = job.user_direction || '';
  const frameNotes = frameDraftText(job);
  const outputLanguageNote = languageLabel(job.target_language);

  return {
    source: 'video-inspiration',
    createdAt: new Date().toISOString(),
    title,
    visualStyle: compactDraftSections([
      ['Định hướng hình ảnh từ người dùng', userDirection],
      ['Tóm tắt hình ảnh video gốc', job.visual_summary],
      ['Phong cách từ bản tối ưu', sourceBlockText(sourceBlocks, 'style_notes')],
      ['Nhịp hình ảnh cần học và cải thiện', analysisText(job, 'visual_rhythm_vi')],
      ['Gợi ý hình ảnh từ bản rewrite', visualSuggestions],
    ], 320, AI_VIDEO_VISUAL_STYLE_MAX_LENGTH),
    sources: [
      {
        block_type: 'idea',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho ô ý tưởng', sourceBlockText(sourceBlocks, 'idea')],
          ['Tên dự án', title],
          ['Ý tưởng chính', bigIdea],
          ['Hook 3-5 giây đầu để giữ chân người xem', hook3to5],
          ['Câu hỏi người xem sẽ giữ trong đầu', viewerQuestion],
          ['Khoảng tò mò cần giữ', curiosityGap],
          ['Ngôn ngữ của bản rewrite hiện tại', outputLanguageNote],
          ['Cơ hội viết mới từ phân tích', analysisText(job, 'rewrite_opportunities_vi')],
        ]),
      },
      {
        block_type: 'rough_script',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho ô kịch bản thô', sourceBlockText(sourceBlocks, 'rough_script')],
          ['Kịch bản tối ưu đã duyệt', job.rewritten_script],
          ['Cấu trúc segment/cảnh từ bản rewrite', draftText(rewrite.segments)],
          ['Transcript gốc để đối chiếu', job.transcript_text],
        ]),
      },
      {
        block_type: 'character_notes',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho nhân vật/bối cảnh', sourceBlockText(sourceBlocks, 'character_notes')],
          ['Nhân vật và bối cảnh', analysisText(job, 'characters_context_vi')],
          ['Bối cảnh/hình ảnh đã quan sát', job.visual_summary],
          ['Frame đại diện cần dùng làm dữ liệu hình ảnh', frameNotes],
          ['Ghi chú thêm từ người dùng', userDirection],
        ]),
      },
      {
        block_type: 'style_notes',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho phong cách video', sourceBlockText(sourceBlocks, 'style_notes')],
          ['Phong cách video', userDirection],
          ['Nhịp dựng / camera / mood', analysisText(job, 'visual_rhythm_vi')],
          ['Retention plan', retentionPlan],
          ['Sound design plan', soundDesignPlan],
          ['Audio direction', audioDirection],
          ['Dữ liệu frame/video inspiration', frameNotes],
          ['Gợi ý hình ảnh theo từng đoạn', visualSuggestions],
          ['Ghi chú phân tích', analysisText(job, 'notes_vi')],
        ]),
      },
      {
        block_type: 'must_have',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho phần bắt buộc', sourceBlockText(sourceBlocks, 'must_have')],
          ['Bắt buộc giữ ý tưởng chính', bigIdea],
          ['Bắt buộc có hook 3-5 giây đầu', hook3to5],
          ['Bắt buộc có payoff retention', draftText((rewrite.retention_plan as Record<string, unknown> | undefined)?.payoff)],
          ['Điểm mạnh cần giữ lại', analysisText(job, 'strengths_vi')],
          ['Cơ hội phát triển cần tận dụng', analysisText(job, 'rewrite_opportunities_vi')],
          ['Định hướng người dùng', userDirection],
        ]),
      },
      {
        block_type: 'avoid',
        content: joinDraftSections([
          ['Dữ liệu đã tối ưu cho phần cần tránh', sourceBlockText(sourceBlocks, 'avoid')],
          ['Điểm yếu cần tránh/sửa', analysisText(job, 'weaknesses_vi')],
          ['Không được copy sát video gốc', draftText(rewrite.originality_note)],
          ['Tránh lỗi âm thanh', 'Không để nhạc nền hoặc SFX che narration; tránh đoạn mở đầu quá tĩnh và không có âm thanh định hướng.'],
          ['Lưu ý chất lượng', analysisText(job, 'notes_vi')],
          [
            'Nguyên tắc',
            'Không diễn giải lại transcript. Không tự chạy Video AI trước khi người dùng chọn thị trường, ngôn ngữ, thời lượng và cách chạy.',
          ],
          [
            'Cấu hình',
            'Không tự quyết định thị trường, ngôn ngữ cuối, thời lượng, tỷ lệ, giọng đọc hoặc chế độ chạy; người dùng sẽ chọn trong Video AI.',
          ],
        ]),
      },
    ],
    notice:
      'Đã đưa dữ liệu từ Video Inspiration vào biểu mẫu Video AI. Mặc định là tạo câu lệnh + giọng đọc + phụ đề, chưa chạy Veo/MP4. Hãy chọn hồ sơ giọng và ngôn ngữ trước khi tạo dự án.',
  };
}

function mutationError(...errors: unknown[]): string | null {
  const error = errors.find(Boolean);
  return error ? getErrorMessage(error) : null;
}

function useVideoInspirationMutations(setSelectedJobId: (jobId: string) => void) {
  const queryClient = useQueryClient();

  const cacheJob = (job: VideoInspirationJobResponse) => {
    queryClient.setQueryData(['video-inspiration', 'job', job.id], job);
    queryClient.invalidateQueries({ queryKey: ['video-inspiration', 'jobs'] });
  };

  const rememberJob = (job: VideoInspirationJobResponse) => {
    cacheJob(job);
    setSelectedJobId(job.id);
  };

  return {
    upload: useMutation({
      mutationFn: ({
        file,
        targetLanguage,
        userDirection,
      }: {
        file: File;
        targetLanguage: VideoInspirationTargetLanguage;
        userDirection: string;
      }) => apiClient.uploadVideoInspirationJob(file, targetLanguage, userDirection),
      onSuccess: rememberJob,
    }),
    fromUrl: useMutation({
      mutationFn: ({
        url,
        targetLanguage,
        userDirection,
        useBrowserCookies,
      }: {
        url: string;
        targetLanguage: VideoInspirationTargetLanguage;
        userDirection: string;
        useBrowserCookies: boolean;
      }) =>
        apiClient.createVideoInspirationJobFromUrl({
          url,
          target_language: targetLanguage,
          user_direction: userDirection.trim() || null,
          use_browser_cookies: useBrowserCookies,
        }),
      onSuccess: rememberJob,
    }),
    analyze: useMutation({
      mutationFn: ({
        jobId,
        allowAudioOnly,
        analysisMode,
      }: {
        jobId: string;
        allowAudioOnly: boolean;
        analysisMode: VideoInspirationAnalysisMode;
      }) =>
        apiClient.analyzeVideoInspirationJob(jobId, {
          allow_audio_only: allowAudioOnly,
          analysis_mode: analysisMode,
        }),
      onSuccess: cacheJob,
    }),
    saveTranscript: useMutation({
      mutationFn: ({ jobId, text }: { jobId: string; text: string }) =>
        apiClient.updateVideoInspirationTranscript(jobId, { transcript_text: text }),
      onSuccess: cacheJob,
    }),
    saveDirection: useMutation({
      mutationFn: ({ jobId, userDirection }: { jobId: string; userDirection: string }) =>
        apiClient.updateVideoInspirationDirection(jobId, {
          user_direction: userDirection.trim() || null,
        }),
      onSuccess: cacheJob,
    }),
    saveTextEvent: useMutation({
      mutationFn: ({
        jobId,
        eventId,
        text,
        role,
      }: {
        jobId: string;
        eventId: string;
        text: string;
        role: string;
      }) =>
        apiClient.updateVideoInspirationTextEvent(jobId, eventId, {
          text,
          role: role || null,
        }),
      onSuccess: cacheJob,
    }),
    rewrite: useMutation({
      mutationFn: ({
        jobId,
        targetLanguage,
        userDirection,
      }: {
        jobId: string;
        targetLanguage: VideoInspirationTargetLanguage;
        userDirection: string;
      }) =>
        apiClient.rewriteVideoInspirationJob(jobId, {
          target_language: targetLanguage,
          user_direction: userDirection,
        }),
      onSuccess: cacheJob,
    }),
    cancel: useMutation({
      mutationFn: (jobId: string) => apiClient.cancelVideoInspirationJob(jobId),
      onSuccess: cacheJob,
    }),
    retry: useMutation({
      mutationFn: (jobId: string) => apiClient.retryVideoInspirationJob(jobId),
      onSuccess: cacheJob,
    }),
    saveScript: useMutation({
      mutationFn: ({
        jobId,
        rewrittenScript,
        scriptTitle,
        bigIdea,
        hook,
      }: {
        jobId: string;
        rewrittenScript: string;
        scriptTitle: string;
        bigIdea: string;
        hook: string;
      }) =>
        apiClient.updateVideoInspirationScript(jobId, {
          rewritten_script: rewrittenScript,
          script_title: scriptTitle || null,
          big_idea: bigIdea || null,
          hook: hook || null,
      }),
      onSuccess: cacheJob,
    }),
    createHandoff: useMutation({
      mutationFn: (jobId: string) => apiClient.createVideoInspirationHandoff(jobId),
      onSuccess: (handoff) => {
        queryClient.invalidateQueries({ queryKey: ['video-inspiration', 'handoffs', handoff.job_id] });
      },
    }),
    createProjectFromHandoff: useMutation({
      mutationFn: ({
        jobId,
        voiceProfileId,
      }: {
        jobId: string;
        voiceProfileId: string | null;
      }): Promise<VideoInspirationHandoffResponse> =>
        apiClient.createAIVideoProjectFromInspiration(jobId, {
          start_full_materials: true,
          mode: 'full_auto',
          voice_profile_id: voiceProfileId,
        }),
      onSuccess: (result) => {
        cacheJob(result.job);
        queryClient.invalidateQueries({ queryKey: ['video-inspiration', 'handoffs', result.job.id] });
        window.location.assign(result.ai_video_url);
      },
    }),
  };
}

export function VideoInspiration() {
  const { data: profiles } = useProfiles();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<VideoInspirationTargetLanguage>('vi');
  const [sourceUrl, setSourceUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [allowAudioOnly, setAllowAudioOnly] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<VideoInspirationAnalysisMode>('quick');
  const [useBrowserCookies, setUseBrowserCookies] = useState(false);
  const [handoffVoiceProfileId, setHandoffVoiceProfileId] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [userDirectionDraft, setUserDirectionDraft] = useState('');
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const [textEventDrafts, setTextEventDrafts] = useState<Record<string, string>>({});
  const [scriptDraft, setScriptDraft] = useState('');
  const [scriptTitleDraft, setScriptTitleDraft] = useState('');
  const [bigIdeaDraft, setBigIdeaDraft] = useState('');
  const [hookDraft, setHookDraft] = useState('');

  const mutations = useVideoInspirationMutations((jobId) => setSelectedJobId(jobId));

  const jobsQuery = useQuery({
    queryKey: ['video-inspiration', 'jobs'],
    queryFn: () => apiClient.listVideoInspirationJobs(30, 0),
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => isJobActive(job)) ? 2500 : false,
  });

  const currentJobFallback = jobsQuery.data?.items.find((job) => job.id === selectedJobId) ?? null;
  const jobQuery = useQuery({
    queryKey: ['video-inspiration', 'job', selectedJobId],
    queryFn: () => apiClient.getVideoInspirationJob(selectedJobId!),
    enabled: !!selectedJobId,
    initialData: currentJobFallback || undefined,
    refetchInterval: (query) => (isJobActive(query.state.data) ? 2000 : false),
  });
  const handoffsQuery = useQuery({
    queryKey: ['video-inspiration', 'handoffs', selectedJobId],
    queryFn: () => apiClient.listVideoInspirationHandoffs(selectedJobId!),
    enabled: !!selectedJobId,
  });

  const jobs = jobsQuery.data?.items ?? [];
  const currentJob = jobQuery.data ?? currentJobFallback;
  const isCurrentJobStale = isJobStale(currentJob);
  const latestHandoff = handoffsQuery.data?.items[0] ?? null;
  const latestHandoffPayload = asRecord(latestHandoff?.payload_json);
  const currentJobId = currentJob?.id ?? null;
  const sourceCreatePending = mutations.upload.isPending || mutations.fromUrl.isPending;
  const analyzePendingForCurrent =
    mutations.analyze.isPending && mutations.analyze.variables?.jobId === currentJobId;
  const rewritePendingForCurrent =
    mutations.rewrite.isPending && mutations.rewrite.variables?.jobId === currentJobId;
  const saveTranscriptPendingForCurrent =
    mutations.saveTranscript.isPending && mutations.saveTranscript.variables?.jobId === currentJobId;
  const saveDirectionPendingForCurrent =
    mutations.saveDirection.isPending && mutations.saveDirection.variables?.jobId === currentJobId;
  const saveTextEventPendingForCurrent =
    mutations.saveTextEvent.isPending && mutations.saveTextEvent.variables?.jobId === currentJobId;
  const saveScriptPendingForCurrent =
    mutations.saveScript.isPending && mutations.saveScript.variables?.jobId === currentJobId;
  const createHandoffPendingForCurrent =
    mutations.createHandoff.isPending && mutations.createHandoff.variables === currentJobId;
  const createProjectPendingForCurrent =
    mutations.createProjectFromHandoff.isPending &&
    mutations.createProjectFromHandoff.variables?.jobId === currentJobId;
  const cancelPendingForCurrent =
    mutations.cancel.isPending && mutations.cancel.variables === currentJobId;
  const retryPendingForCurrent = mutations.retry.isPending && mutations.retry.variables === currentJobId;
  const currentJobMutationPending =
    analyzePendingForCurrent ||
    rewritePendingForCurrent ||
    saveTranscriptPendingForCurrent ||
    saveDirectionPendingForCurrent ||
    saveTextEventPendingForCurrent ||
    saveScriptPendingForCurrent ||
    createHandoffPendingForCurrent ||
    createProjectPendingForCurrent ||
    cancelPendingForCurrent ||
    retryPendingForCurrent;
  const currentJobActive = isJobActive(currentJob);
  const currentJobLocked = currentJobActive || currentJobMutationPending;
  const currentJobActionError = mutationError(
    mutations.analyze.variables?.jobId === currentJobId ? mutations.analyze.error : null,
    mutations.saveTranscript.variables?.jobId === currentJobId
      ? mutations.saveTranscript.error
      : null,
    mutations.saveDirection.variables?.jobId === currentJobId
      ? mutations.saveDirection.error
      : null,
    mutations.saveTextEvent.variables?.jobId === currentJobId
      ? mutations.saveTextEvent.error
      : null,
    mutations.rewrite.variables?.jobId === currentJobId ? mutations.rewrite.error : null,
    mutations.cancel.variables === currentJobId ? mutations.cancel.error : null,
    mutations.retry.variables === currentJobId ? mutations.retry.error : null,
    mutations.saveScript.variables?.jobId === currentJobId ? mutations.saveScript.error : null,
    mutations.createHandoff.variables === currentJobId ? mutations.createHandoff.error : null,
    mutations.createProjectFromHandoff.variables?.jobId === currentJobId
      ? mutations.createProjectFromHandoff.error
      : null,
  );
  const currentProgress = progressValue(currentJob);
  const entries = useMemo(() => analysisEntries(currentJob), [currentJob]);
  const optimizedPanels = useMemo(
    () => (currentJob ? optimizedRewritePanels(currentJob) : []),
    [currentJob],
  );
  const serverUserDirection = currentJob?.user_direction || '';
  const serverTargetLanguage = currentJob?.target_language ?? 'vi';
  const serverAnalysisMode = currentJob?.analysis_mode === 'high_quality' ? 'high_quality' : 'quick';
  const serverTranscript = currentJob?.transcript_text || '';
  const serverScript = currentJob?.rewritten_script || '';
  const serverScriptTitle = currentJob?.script_title || '';
  const serverBigIdea = currentJob?.big_idea || '';
  const serverHook = currentJob?.hook || '';
  const serverTextEventsSignature = JSON.stringify(
    (currentJob?.on_screen_text_events ?? []).map((event) => [event.id, event.text]),
  );
  const recommendedHandoffVoiceProfile = useMemo(() => {
    const available = profiles ?? [];
    return (
      available.find((profile) => profile.language === targetLanguage) ??
      available.find((profile) => profile.language === serverTargetLanguage) ??
      available[0] ??
      null
    );
  }, [profiles, serverTargetLanguage, targetLanguage]);
  const effectiveHandoffVoiceProfileId =
    handoffVoiceProfileId || recommendedHandoffVoiceProfile?.id || '';
  const effectiveHandoffVoiceProfile =
    profiles?.find((profile) => profile.id === effectiveHandoffVoiceProfileId) ?? null;
  const primaryError =
    localError ||
    currentJob?.failure_reason ||
    (isCurrentJobStale
      ? currentJob?.stale_reason || 'Job bị gián đoạn quá lâu. Bấm chạy lại phân tích để tiếp tục.'
      : null) ||
    mutationError(
      mutations.upload.error,
      mutations.fromUrl.error,
      currentJobActionError,
      jobQuery.error,
      jobsQuery.error,
      handoffsQuery.error,
    );

  useEffect(() => {
    if (!selectedJobId && jobs[0]?.id) {
      setSelectedJobId(jobs[0].id);
    }
  }, [selectedJobId, jobs]);

  useEffect(() => {
    if (!currentJobId) return;
    setUserDirectionDraft(serverUserDirection);
    setTargetLanguage(serverTargetLanguage);
    setAnalysisMode(serverAnalysisMode);
  }, [currentJobId, serverAnalysisMode, serverTargetLanguage, serverUserDirection]);

  useEffect(() => {
    if (!currentJobId) return;
    setTranscriptDraft(serverTranscript);
    setScriptDraft(serverScript);
    setScriptTitleDraft(serverScriptTitle);
    setBigIdeaDraft(serverBigIdea);
    setHookDraft(serverHook);
    setTextEventDrafts(Object.fromEntries(JSON.parse(serverTextEventsSignature)));
  }, [
    currentJobId,
    serverBigIdea,
    serverHook,
    serverScript,
    serverScriptTitle,
    serverTextEventsSignature,
    serverTranscript,
  ]);

  const uploadDisabled = sourceCreatePending || !selectedFile;
  const urlDisabled = sourceCreatePending || !sourceUrl.trim();
  const currentJobRetryable =
    !!currentJob && (isCurrentJobStale || ['failed', 'cancelled'].includes(currentJob.status));
  const canAnalyze = !!currentJob && !currentJobLocked && !currentJobRetryable;
  const canRewrite = !!currentJob?.analysis_json && !currentJobLocked;
  const canHandoff = !!currentJob?.rewritten_script?.trim() && !currentJobLocked;
  const canCreateStructuredHandoff =
    !!currentJob?.rewritten_script?.trim() &&
    !!currentJob?.analysis_package_json &&
    !currentJobLocked;
  const canCreateProjectFromHandoff =
    !!latestHandoff &&
    !latestHandoff.created_project_id &&
    !currentJobLocked &&
    !!effectiveHandoffVoiceProfileId;
  const trimmedUserDirection = userDirectionDraft.trim();
  const directionChanged = (currentJob?.user_direction || '') !== trimmedUserDirection;
  const canSaveDirection = !!currentJob && !currentJobLocked && directionChanged;
  const canCancel = !!currentJob && currentJobActive && !cancelPendingForCurrent;
  const canRetry = currentJobRetryable && !currentJobMutationPending;
  const analyzeButtonText = currentJob?.analysis_json ? 'Phân tích lại video' : 'Phân tích video';

  const handleUpload = () => {
    setLocalError(null);
    if (!selectedFile) {
      setLocalError('Hãy chọn một file .mp4 trước.');
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith('.mp4')) {
      setLocalError('Hiện tại chỉ nhận file .mp4.');
      return;
    }
    mutations.upload.mutate({
      file: selectedFile,
      targetLanguage,
      userDirection: userDirectionDraft,
    });
  };

  const handleUrlImport = () => {
    setLocalError(null);
    const url = sourceUrl.trim();
    if (!url) {
      setLocalError('Hãy dán link video công khai trước.');
      return;
    }
    mutations.fromUrl.mutate({
      url,
      targetLanguage,
      userDirection: userDirectionDraft,
      useBrowserCookies,
    });
  };

  const handleOpenAIVideoDraft = () => {
    setLocalError(null);
    if (!currentJob?.rewritten_script?.trim()) {
      setLocalError('Cần có kịch bản tối ưu trước khi đưa sang form AI Video.');
      return;
    }
    try {
      window.sessionStorage.setItem(
        AI_VIDEO_DRAFT_STORAGE_KEY,
        JSON.stringify(buildAIVideoDraft(currentJob)),
      );
      window.location.assign('/ai-video?draft=video-inspiration');
    } catch (error) {
      setLocalError(
        `Chưa đưa được dữ liệu sang AI Video: ${getErrorMessage(error)}. Hãy thử lưu kịch bản rồi bấm lại.`,
      );
    }
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto py-5">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-4">
        <header className="flex flex-col gap-3 rounded-lg border border-border/80 bg-card/70 p-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">Lấy cảm hứng từ video</h1>
              <Badge variant="secondary" className="h-7 px-3">
                {languageLabel(targetLanguage)}
              </Badge>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Đưa video vào, lấy lời nói và hình ảnh làm chất liệu, rồi viết thành kịch bản tối ưu để
              điền sẵn form AI Video trước khi anh tự chọn cấu hình và chạy.
            </p>
          </div>
          <div className="min-w-[220px] rounded-lg border border-border/70 bg-background/60 p-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{statusLabel(currentJob)}</span>
              <span className="text-muted-foreground">{currentProgress}%</span>
            </div>
            <Progress value={currentProgress} className="mt-3 h-2" />
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              {stepLabel(currentJob)}
            </p>
          </div>
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

        <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="rounded-lg border border-border/80 bg-card/65 p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background">
                  <FileVideo className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-semibold">Nguồn video</h2>
                  <p className="text-xs text-muted-foreground">
                    MP4 hoặc link công khai · job cũ vẫn tiếp tục chạy nền
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4">
                <div className="grid gap-2">
                  <label className="text-sm font-medium" htmlFor="video-inspiration-file">
                    Upload file MP4
                  </label>
                  <Input
                    id="video-inspiration-file"
                    type="file"
                    accept="video/mp4,.mp4"
                    disabled={sourceCreatePending}
                    onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                    className="h-11 cursor-pointer"
                  />
                  <Button
                    type="button"
                    size="lg"
                    disabled={uploadDisabled}
                    onClick={handleUpload}
                    className="w-full"
                  >
                    {mutations.upload.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    Tạo job từ MP4
                  </Button>
                </div>

                <div className="border-t border-border/70 pt-4">
                  <label className="text-sm font-medium" htmlFor="video-inspiration-url">
                    Link YouTube / TikTok / Facebook / Instagram
                  </label>
                  <div className="mt-2 flex gap-2">
                    <Input
                      id="video-inspiration-url"
                      value={sourceUrl}
                      onChange={(event) => setSourceUrl(event.target.value)}
                      disabled={sourceCreatePending}
                      placeholder="Dán link công khai"
                      className="h-11"
                    />
                    <Button
                      type="button"
                      size="icon"
                      disabled={urlDisabled}
                      onClick={handleUrlImport}
                      aria-label="Tạo job từ link"
                      title="Tạo job từ link"
                      className="h-11 w-11"
                    >
                      {mutations.fromUrl.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <LinkIcon className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  <label className="mt-3 flex min-h-11 items-start gap-3 rounded-lg border border-border/70 bg-background/60 p-3 text-sm">
                    <input
                      type="checkbox"
                      checked={useBrowserCookies}
                      disabled={sourceCreatePending}
                      onChange={(event) => setUseBrowserCookies(event.target.checked)}
                      className="mt-1 h-4 w-4"
                    />
                    <span className="leading-relaxed text-muted-foreground">
                      Dùng phiên đăng nhập trình duyệt của tôi nếu nền tảng yêu cầu xác minh. App
                      chỉ dùng trong lần tải này và không lưu cookie.
                    </span>
                  </label>
                </div>

                <div className="grid gap-2 border-t border-border/70 pt-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Languages className="h-4 w-4" />
                    Ngôn ngữ kịch bản mới
                  </div>
                  <select
                    value={targetLanguage}
                    disabled={sourceCreatePending}
                    onChange={(event) =>
                      setTargetLanguage(event.target.value as VideoInspirationTargetLanguage)
                    }
                    className="min-h-11 rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                  >
                    {LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid gap-2 border-t border-border/70 pt-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Film className="h-4 w-4" />
                    Chế độ phân tích
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {(['quick', 'high_quality'] as const).map((mode) => (
                      <Button
                        key={mode}
                        type="button"
                        variant={analysisMode === mode ? 'default' : 'outline'}
                        className="h-11"
                        disabled={sourceCreatePending}
                        onClick={() => setAnalysisMode(mode)}
                      >
                        {analysisModeLabel(mode)}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="grid gap-2 border-t border-border/70 pt-4">
                  <div className="flex items-center justify-between gap-3">
                    <label className="text-sm font-medium" htmlFor="video-user-direction">
                      Mong muốn phát triển thêm ý tưởng
                    </label>
                    <span className="shrink-0 text-xs text-muted-foreground">Không bắt buộc</span>
                  </div>
                  <Textarea
                    id="video-user-direction"
                    value={userDirectionDraft}
                    onChange={(event) => setUserDirectionDraft(event.target.value)}
                    placeholder="Ví dụ: làm thành video người que 3D, vẫn giữ chủ đề nhân quả, nhịp kể nhanh hơn."
                    className="min-h-[116px] resize-y text-sm leading-relaxed"
                  />
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Nếu nhập, AI sẽ dùng phần này để định hướng kịch bản mới và phần đưa vào form AI
                    Video.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canSaveDirection}
                    onClick={() =>
                      currentJob &&
                      mutations.saveDirection.mutate({
                        jobId: currentJob.id,
                        userDirection: userDirectionDraft,
                      })
                    }
                    className="min-h-11 w-full"
                  >
                    {saveDirectionPendingForCurrent ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Lưu định hướng
                  </Button>
                </div>

                <label className="flex min-h-11 items-start gap-3 rounded-lg border border-border/70 bg-background/60 p-3 text-sm">
                  <input
                    type="checkbox"
                    checked={allowAudioOnly}
                    onChange={(event) => setAllowAudioOnly(event.target.checked)}
                    className="mt-1 h-4 w-4"
                  />
                  <span className="leading-relaxed text-muted-foreground">
                    Cho phép phân tích chỉ từ lời nói nếu công cụ xem hình ảnh chưa sẵn sàng.
                  </span>
                </label>
              </div>
            </section>

            <section className="rounded-lg border border-border/80 bg-card/65 p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Job gần đây</h2>
                {jobsQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              </div>
              <div className="mt-4 space-y-2">
                {jobs.length ? (
                  jobs.map((job) => {
                    const selected = job.id === currentJob?.id;
                    return (
                      <button
                        type="button"
                        key={job.id}
                        onClick={() => setSelectedJobId(job.id)}
                        className={cn(
                          'w-full rounded-lg border p-3 text-left transition-colors',
                          selected
                            ? 'border-accent bg-accent/10 text-foreground'
                            : 'border-border/70 bg-background/60 text-muted-foreground hover:bg-muted/50',
                        )}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="min-w-0 truncate text-sm font-medium">
                            {jobTitle(job)}
                          </span>
                          <span className="shrink-0 text-xs">{progressValue(job)}%</span>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                          <span className="truncate">{statusLabel(job)}</span>
                          <span className="shrink-0">{formatDate(job.updated_at)}</span>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                    Chưa có job nào.
                  </div>
                )}
              </div>
            </section>
          </aside>

          <main className="min-w-0 space-y-4">
            <section className="rounded-lg border border-border/80 bg-card/65 p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold">
                    {currentJob ? jobTitle(currentJob) : 'Chưa chọn video'}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">{stepLabel(currentJob)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {currentJobActive ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!canCancel}
                      onClick={() => currentJob && mutations.cancel.mutate(currentJob.id)}
                    >
                      {cancelPendingForCurrent ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <CircleStop className="h-4 w-4" />
                      )}
                      Hủy tác vụ
                    </Button>
                  ) : null}
                  {currentJob && currentJobRetryable ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!canRetry}
                      onClick={() => mutations.retry.mutate(currentJob.id)}
                    >
                      {retryPendingForCurrent ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Thử chạy lại
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canAnalyze}
                    onClick={() =>
                      currentJob &&
                      mutations.analyze.mutate({
                        jobId: currentJob.id,
                        allowAudioOnly,
                        analysisMode,
                      })
                    }
                  >
                    {analyzePendingForCurrent ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    {analyzeButtonText}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canRewrite}
                    onClick={() =>
                      currentJob &&
                      mutations.rewrite.mutate({
                        jobId: currentJob.id,
                        targetLanguage,
                        userDirection: userDirectionDraft,
                      })
                    }
                  >
                    {rewritePendingForCurrent ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    Viết kịch bản tối ưu
                  </Button>
                  <Button type="button" disabled={!canHandoff} onClick={handleOpenAIVideoDraft}>
                    <ArrowRight className="h-4 w-4" />
                    Đưa vào form AI Video
                  </Button>
                </div>
              </div>
            </section>

            <Tabs defaultValue="transcript" className="min-w-0">
              <TabsList className="h-auto w-full flex-wrap justify-start rounded-lg p-1">
                <TabsTrigger value="transcript" className="min-h-10">
                  <FileText className="mr-2 h-4 w-4" />
                  Transcript
                </TabsTrigger>
                <TabsTrigger value="frames" className="min-h-10">
                  <ImageIcon className="mr-2 h-4 w-4" />
                  Hình ảnh
                </TabsTrigger>
                <TabsTrigger value="timeline" className="min-h-10">
                  <Film className="mr-2 h-4 w-4" />
                  Timeline
                </TabsTrigger>
                <TabsTrigger value="analysis" className="min-h-10">
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Phân tích
                </TabsTrigger>
                <TabsTrigger value="script" className="min-h-10">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Kịch bản tối ưu
                </TabsTrigger>
                <TabsTrigger value="handoff" className="min-h-10">
                  <ArrowRight className="mr-2 h-4 w-4" />
                  Handoff
                </TabsTrigger>
              </TabsList>

              <TabsContent value="transcript" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-base font-semibold">Lời nói trong video gốc</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Có thể sửa lại trước khi phân tích hoặc viết kịch bản.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!currentJob || currentJobLocked}
                      onClick={() =>
                        currentJob &&
                        mutations.saveTranscript.mutate({
                          jobId: currentJob.id,
                          text: transcriptDraft,
                        })
                      }
                    >
                      {saveTranscriptPendingForCurrent ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      Lưu transcript
                    </Button>
                  </div>
                  <Textarea
                    value={transcriptDraft}
                    onChange={(event) => setTranscriptDraft(event.target.value)}
                    disabled={!currentJob || currentJobLocked}
                    placeholder="Transcript sẽ xuất hiện sau khi bấm Phân tích video."
                    className="mt-4 min-h-[420px] resize-y text-sm leading-relaxed"
                  />
                </section>
              </TabsContent>

              <TabsContent value="frames" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <h3 className="text-base font-semibold">Frame đại diện và ghi chú hình ảnh</h3>
                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {currentJob?.frames?.length ? (
                      currentJob.frames.map((frame) => (
                        <div
                          key={frame.id}
                          className="overflow-hidden rounded-lg border border-border/80 bg-background/60"
                        >
                          <img
                            src={apiClient.getVideoInspirationFrameUrl(frame.id)}
                            alt={`Frame tại ${frame.timestamp_seconds.toFixed(1)} giây`}
                            loading="lazy"
                            className="aspect-video w-full bg-muted object-cover"
                          />
                          <div className="p-3 text-sm">
                            <p className="font-medium">{frame.timestamp_seconds.toFixed(1)} giây</p>
                            <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
                              {frame.description_vi || 'Chưa có mô tả hình ảnh.'}
                            </p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
                        Chưa có frame. Hãy bấm Phân tích video.
                      </div>
                    )}
                  </div>
                  <div className="mt-4 rounded-lg border border-border/70 bg-background/60 p-4">
                    <p className="text-sm font-semibold">Tóm tắt hình ảnh</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                      {currentJob?.visual_summary || 'Chưa có tóm tắt hình ảnh.'}
                    </p>
                  </div>
                </section>
              </TabsContent>

              <TabsContent value="timeline" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-base font-semibold">Timeline đa phương thức</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Retention ở đây là dự đoán nguy cơ từ nội dung, không phải dữ liệu rời xem thực tế.
                      </p>
                    </div>
                    <Badge variant="outline" className="w-fit">
                      {completionLabel(currentJob?.analysis_completeness)}
                    </Badge>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    {[
                      ['Shot', currentJob?.coverage_metrics_json?.shot_coverage_ratio],
                      ['Hình ảnh', currentJob?.coverage_metrics_json?.visual_description_coverage_ratio],
                      ['Transcript', currentJob?.coverage_metrics_json?.transcript_coverage_ratio],
                      ['Âm thanh', currentJob?.coverage_metrics_json?.audio_event_coverage_ratio],
                      ['Beat', currentJob?.coverage_metrics_json?.retention_beat_coverage_ratio],
                    ].map(([label, value]) => (
                      <div key={label as string} className="rounded-lg border border-border/70 bg-background/60 p-3">
                        <p className="text-xs text-muted-foreground">{label as string}</p>
                        <p className="mt-1 text-lg font-semibold">{percentMetric(value)}</p>
                      </div>
                    ))}
                  </div>

                  {Array.isArray(currentJob?.limitations_json) && currentJob.limitations_json.length ? (
                    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-950 dark:text-amber-100">
                      <p className="font-semibold">Hạn chế phân tích</p>
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {currentJob.limitations_json.map((item) => (
                          <li key={String(item)}>{String(item)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  <div className="mt-4 grid gap-4 xl:grid-cols-[1.25fr_1fr]">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Film className="h-4 w-4" />
                        Shot và keyframe
                      </div>
                      {(currentJob?.shots ?? []).length ? (
                        (currentJob?.shots ?? []).slice(0, 24).map((shot) => {
                          const shotFrames = (currentJob?.frames ?? []).filter((frame) => frame.shot_id === shot.id);
                          return (
                            <div key={shot.id} className="rounded-lg border border-border/75 bg-background/60 p-4">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-sm font-semibold">
                                  Shot {shot.shot_order} · {formatSeconds(shot.start_seconds)}-{formatSeconds(shot.end_seconds)}
                                </p>
                                <span className="text-xs text-muted-foreground">
                                  {shotFrames.length} keyframe
                                </span>
                              </div>
                              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                                {shot.visual_description_vi || 'Chưa có mô tả chắc chắn cho shot này.'}
                              </p>
                              {shotFrames.length ? (
                                <div className="mt-3 grid grid-cols-3 gap-2">
                                  {shotFrames.slice(0, 3).map((frame) => (
                                    <img
                                      key={frame.id}
                                      src={apiClient.getVideoInspirationFrameUrl(frame.id)}
                                      alt={`Keyframe ${formatSeconds(frame.timestamp_seconds)}`}
                                      loading="lazy"
                                      className="aspect-video rounded-md border border-border/70 bg-muted object-cover"
                                    />
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          );
                        })
                      ) : (
                        <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
                          Chưa có shot timeline. Hãy bấm Phân tích video.
                        </div>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="rounded-lg border border-border/75 bg-background/60 p-4">
                        <p className="flex items-center gap-2 text-sm font-semibold">
                          <FileText className="h-4 w-4" />
                          Transcript segment
                        </p>
                        <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
                          {(currentJob?.transcript_segments ?? []).length ? (
                            (currentJob?.transcript_segments ?? []).slice(0, 16).map((segment) => (
                              <div key={segment.id} className="rounded-md border border-border/60 p-3 text-sm">
                                <p className="text-xs text-muted-foreground">
                                  {formatSeconds(segment.start_seconds)}-{formatSeconds(segment.end_seconds)} · {segment.timestamp_precision} · {segment.source}
                                </p>
                                <p className="mt-1 whitespace-pre-wrap leading-relaxed">{segment.text}</p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">Chưa có transcript segment.</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-lg border border-border/75 bg-background/60 p-4">
                        <p className="flex items-center gap-2 text-sm font-semibold">
                          <Volume2 className="h-4 w-4" />
                          Âm thanh
                        </p>
                        <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                          {(currentJob?.audio_events ?? []).length ? (
                            (currentJob?.audio_events ?? []).slice(0, 18).map((event) => (
                              <div key={event.id} className="rounded-md border border-border/60 p-3 text-sm">
                                <p className="text-xs text-muted-foreground">
                                  {formatSeconds(event.start_seconds)}-{formatSeconds(event.end_seconds)} · {event.event_type}
                                  {typeof event.confidence === 'number' ? ` · tin cậy ${Math.round(event.confidence * 100)}%` : ''}
                                </p>
                                <p className="mt-1">{event.description_vi || 'Sự kiện âm thanh.'}</p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">Chưa có timeline âm thanh.</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-lg border border-border/75 bg-background/60 p-4">
                        <p className="text-sm font-semibold">Chữ trên màn hình</p>
                        <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                          {(currentJob?.on_screen_text_events ?? []).length ? (
                            (currentJob?.on_screen_text_events ?? []).slice(0, 12).map((event) => {
                              const draft = textEventDrafts[event.id] ?? event.text;
                              return (
                                <div key={event.id} className="rounded-md border border-border/60 p-3 text-sm">
                                  <p className="text-xs text-muted-foreground">
                                    {formatSeconds(event.start_seconds)}-{formatSeconds(event.end_seconds)} · {event.role}
                                  </p>
                                  <Textarea
                                    value={draft}
                                    disabled={currentJobLocked}
                                    onChange={(changeEvent) =>
                                      setTextEventDrafts((current) => ({
                                        ...current,
                                        [event.id]: changeEvent.target.value,
                                      }))
                                    }
                                    className="mt-2 min-h-20 resize-y text-sm"
                                  />
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="mt-2"
                                    disabled={
                                      !currentJob ||
                                      currentJobLocked ||
                                      !draft.trim() ||
                                      draft === event.text
                                    }
                                    onClick={() =>
                                      currentJob &&
                                      mutations.saveTextEvent.mutate({
                                        jobId: currentJob.id,
                                        eventId: event.id,
                                        text: draft,
                                        role: event.role,
                                      })
                                    }
                                  >
                                    <Save className="h-4 w-4" />
                                    Lưu chữ
                                  </Button>
                                </div>
                              );
                            })
                          ) : (
                            <p className="text-sm text-muted-foreground">Chưa nhận diện chữ trên màn hình.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 rounded-lg border border-border/75 bg-background/60 p-4">
                    <p className="text-sm font-semibold">Beat giữ chân dự đoán</p>
                    <div className="mt-3 grid gap-3 lg:grid-cols-2">
                      {(currentJob?.content_retention_beats ?? []).length ? (
                        (currentJob?.content_retention_beats ?? []).slice(0, 12).map((beat) => (
                          <div key={beat.id} className="rounded-md border border-border/60 p-3 text-sm">
                            <p className="text-xs text-muted-foreground">
                              {formatSeconds(beat.start_seconds)}-{formatSeconds(beat.end_seconds)} · {beat.role}
                              {typeof beat.confidence === 'number' ? ` · tin cậy ${Math.round(beat.confidence * 100)}%` : ''}
                            </p>
                            <p className="mt-2 font-medium">{beat.why_continue || beat.new_information || 'Beat nội dung'}</p>
                            {beat.drop_off_risks_json && Array.isArray(beat.drop_off_risks_json) && beat.drop_off_risks_json.length ? (
                              <p className="mt-2 text-muted-foreground">
                                Nguy cơ: {beat.drop_off_risks_json.map(String).join('; ')}
                              </p>
                            ) : null}
                          </div>
                        ))
                      ) : (
                        <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
                          Chưa có beat retention dự đoán.
                        </div>
                      )}
                    </div>
                  </div>
                </section>
              </TabsContent>

              <TabsContent value="analysis" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <h3 className="text-base font-semibold">Phân tích video gốc</h3>
                  <div className="mt-4 grid gap-3">
                    {entries.length ? (
                      entries.map(([key, value]) => (
                        <div
                          key={key}
                          className="rounded-lg border border-border/75 bg-background/60 p-4"
                        >
                          <p className="text-sm font-semibold">{ANALYSIS_LABELS[key] || key}</p>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                            {formatAnalysisValue(value)}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
                        Chưa có phân tích. Hãy bấm Phân tích video.
                      </div>
                    )}
                  </div>
                </section>
              </TabsContent>

              <TabsContent value="script" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <h3 className="text-base font-semibold">Kịch bản tối ưu</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Bản này có sẵn hook 3-5 giây, retention, âm thanh và source block cho AI Video; anh tự chọn cấu hình rồi mới tạo/chạy.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!currentJob || currentJobLocked || !scriptDraft.trim()}
                      onClick={() =>
                        currentJob &&
                        mutations.saveScript.mutate({
                          jobId: currentJob.id,
                          rewrittenScript: scriptDraft,
                          scriptTitle: scriptTitleDraft,
                          bigIdea: bigIdeaDraft,
                          hook: hookDraft,
                        })
                      }
                    >
                      {saveScriptPendingForCurrent ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      Lưu kịch bản
                    </Button>
                  </div>

                  <div className="mt-4 grid gap-3 lg:grid-cols-3">
                    <label className="grid gap-2 text-sm font-medium" htmlFor="video-script-title">
                      Tên ý tưởng
                      <Input
                        id="video-script-title"
                        value={scriptTitleDraft}
                        onChange={(event) => setScriptTitleDraft(event.target.value)}
                        disabled={!currentJob || currentJobLocked}
                        placeholder="Tên kịch bản tối ưu"
                        className="h-11"
                      />
                    </label>
                    <label
                      className="grid gap-2 text-sm font-medium"
                      htmlFor="video-script-big-idea"
                    >
                      Big idea
                      <Input
                        id="video-script-big-idea"
                        value={bigIdeaDraft}
                        onChange={(event) => setBigIdeaDraft(event.target.value)}
                        disabled={!currentJob || currentJobLocked}
                        placeholder="Ý chính của bản mới"
                        className="h-11"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium" htmlFor="video-script-hook">
                      Hook 3-5 giây
                      <Input
                        id="video-script-hook"
                        value={hookDraft}
                        onChange={(event) => setHookDraft(event.target.value)}
                        disabled={!currentJob || currentJobLocked}
                        placeholder="Mở đầu 3-5 giây để giữ chân người xem"
                        className="h-11"
                      />
                    </label>
                  </div>

                  {optimizedPanels.length ? (
                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      {optimizedPanels.map(([label, value]) => (
                        <div
                          key={label}
                          className="rounded-lg border border-border/75 bg-background/60 p-4"
                        >
                          <p className="text-sm font-semibold">{label}</p>
                          <p className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                            {value}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <Textarea
                    value={scriptDraft}
                    onChange={(event) => setScriptDraft(event.target.value)}
                    disabled={!currentJob || currentJobLocked}
                    placeholder="Kịch bản tối ưu sẽ xuất hiện sau khi bấm Viết kịch bản tối ưu."
                    className="mt-4 min-h-[460px] resize-y text-sm leading-relaxed"
                  />
                </section>
              </TabsContent>

              <TabsContent value="handoff" className="mt-4">
                <section className="rounded-lg border border-border/80 bg-card/65 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-base font-semibold">Handoff bền vững sang AI Video</h3>
                      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                        Handoff lưu ở backend, tách nguồn quan sát, bài học được phép học và nội dung đích đã duyệt. Tạo project ở đây sẽ tự chạy tới câu lệnh, giọng đọc và phụ đề; Veo/MP4 vẫn không tự chạy.
                      </p>
                    </div>
                    {latestHandoff && !latestHandoff.created_project_id ? (
                      <label className="grid gap-1 text-sm lg:min-w-[280px]">
                        <span className="font-medium">Giọng đọc cho video</span>
                        <select
                          value={effectiveHandoffVoiceProfileId}
                          disabled={currentJobLocked || createProjectPendingForCurrent || !profiles?.length}
                          onChange={(event) => setHandoffVoiceProfileId(event.target.value)}
                          className="min-h-10 rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                        >
                          {profiles?.length ? (
                            profiles.map((profile) => (
                              <option key={profile.id} value={profile.id}>
                                {profile.name} · {profile.language}
                              </option>
                            ))
                          ) : (
                            <option value="">Chưa có giọng đọc</option>
                          )}
                        </select>
                        <span className="text-xs leading-relaxed text-muted-foreground">
                          {effectiveHandoffVoiceProfile
                            ? `Sẽ dùng giọng “${effectiveHandoffVoiceProfile.name}” để tự tạo voice và phụ đề.`
                            : 'Cần có hồ sơ giọng đọc trước khi chạy tới voice và phụ đề.'}
                        </span>
                      </label>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        disabled={!canCreateStructuredHandoff}
                        onClick={() => currentJob && mutations.createHandoff.mutate(currentJob.id)}
                      >
                        {createHandoffPendingForCurrent ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Save className="h-4 w-4" />
                        )}
                        Tạo handoff backend
                      </Button>
                      {latestHandoff?.created_project_id ? (
                        <Button
                          type="button"
                          onClick={() =>
                            window.location.assign(`/ai-video?projectId=${latestHandoff.created_project_id}`)
                          }
                        >
                          <ArrowRight className="h-4 w-4" />
                          Mở project AI Video
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          disabled={!canCreateProjectFromHandoff}
                          onClick={() =>
                            currentJob &&
                            mutations.createProjectFromHandoff.mutate({
                              jobId: currentJob.id,
                              voiceProfileId: effectiveHandoffVoiceProfileId || null,
                            })
                          }
                        >
                          {createProjectPendingForCurrent ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ArrowRight className="h-4 w-4" />
                          )}
                          Tạo project + giọng/phụ đề
                        </Button>
                      )}
                    </div>
                  </div>

                  {!currentJob?.analysis_package_json ? (
                    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-950 dark:text-amber-100">
                      Cần chạy phân tích timeline trước khi tạo handoff backend.
                    </div>
                  ) : null}

                  {latestHandoff ? (
                    <div className="mt-4 space-y-4">
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <Badge variant="outline">
                          Trạng thái: {handoffStatusLabel(latestHandoff.status)}
                        </Badge>
                        <Badge variant="outline">Revision {latestHandoff.revision}</Badge>
                        <Badge variant="outline">Script rev {latestHandoff.approved_script_revision}</Badge>
                        <Badge variant="outline">{formatDate(latestHandoff.updated_at)}</Badge>
                      </div>

                      <div className="grid gap-3 lg:grid-cols-2">
                        {[
                          ['Nguồn quan sát', latestHandoffPayload.source_observations],
                          ['Bài học được phép học', latestHandoffPayload.learnable_lessons],
                          ['Nội dung đích đã duyệt', latestHandoffPayload.target_content],
                          [
                            'Giữ nguyên bản và giới hạn',
                            {
                              originality_boundaries: latestHandoffPayload.originality_boundaries,
                              evidence_refs: latestHandoffPayload.evidence_refs,
                              limitations: latestHandoffPayload.limitations,
                            },
                          ],
                        ].map(([label, value]) => (
                          <div
                            key={String(label)}
                            className="rounded-lg border border-border/75 bg-background/60 p-4"
                          >
                            <p className="text-sm font-semibold">{String(label)}</p>
                            <p className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                              {structuredPreview(value)}
                            </p>
                          </div>
                        ))}
                      </div>

                      <div className="rounded-lg border border-border/75 bg-background/60 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold">Source blocks tương thích</p>
                          <Badge variant="outline">{latestHandoff.source_blocks_json?.length ?? 0} block</Badge>
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                          {(latestHandoff.source_blocks_json ?? []).slice(0, 8).map((block, index) => {
                            const item = asRecord(block);
                            const blockKey = JSON.stringify(block);
                            return (
                              <div key={blockKey} className="rounded-lg border border-border/70 p-3">
                                <p className="text-xs font-medium uppercase text-muted-foreground">
                                  {String(item.block_type ?? `block-${index + 1}`)}
                                </p>
                                <p className="mt-2 line-clamp-5 whitespace-pre-wrap text-sm leading-relaxed">
                                  {structuredPreview(item.content, 700)}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
                      Chưa có handoff backend. Lưu kịch bản, chạy phân tích timeline rồi bấm Tạo handoff backend để review trước khi tạo AI Video project.
                    </div>
                  )}
                </section>
              </TabsContent>
            </Tabs>
          </main>
        </div>
      </div>
    </div>
  );
}
