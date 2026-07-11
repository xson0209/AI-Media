import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  FileVideo,
  Image as ImageIcon,
  Languages,
  Link as LinkIcon,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
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
import type { VideoInspirationJobResponse, VideoInspirationTargetLanguage } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

const STEP_LABELS: Record<string, string> = {
  source_ready: 'Đã nhận video',
  downloading: 'Đang lấy video từ link',
  extract_audio: 'Đang tách lời nói',
  transcribe: 'Đang chuyển lời nói thành chữ',
  extract_frames: 'Đang lấy hình ảnh đại diện',
  visual_analysis: 'Đang phân tích hình ảnh',
  content_analysis: 'Đang phân tích nội dung',
  rewrite: 'Đang viết kịch bản mới',
  handoff: 'Đang chuyển sang AI Video',
  completed: 'Hoàn tất',
  failed: 'Đã lỗi',
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Đã tải lên',
  analyzing: 'Đang phân tích',
  analyzed: 'Đã phân tích',
  transcript_edited: 'Đã sửa transcript',
  direction_edited: 'Đã lưu định hướng',
  rewriting: 'Đang viết lại',
  rewritten: 'Đã có kịch bản mới',
  handoff: 'Đang chuyển tiếp',
  ai_video_ready: 'Đã chuyển sang AI Video',
  failed: 'Có lỗi',
};

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

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

function languageLabel(language: VideoInspirationTargetLanguage): string {
  return language === 'vi' ? 'Tiếng Việt' : 'Tiếng Anh';
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
  return STATUS_LABELS[job.status] || job.status;
}

function stepLabel(job?: VideoInspirationJobResponse | null): string {
  if (!job) return 'Hãy upload MP4 hoặc dán link công khai';
  return STEP_LABELS[job.current_step] || job.current_step || statusLabel(job);
}

function progressValue(job?: VideoInspirationJobResponse | null): number {
  if (!job) return 0;
  const value = Number(job.progress || 0);
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function isJobActive(job?: VideoInspirationJobResponse | null): boolean {
  return !!job && ['analyzing', 'rewriting', 'handoff'].includes(job.status);
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

function formatAnalysisValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join('\n');
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value ?? '');
}

function analysisEntries(job?: VideoInspirationJobResponse | null) {
  if (!job?.analysis_json) return [];
  return Object.entries(job.analysis_json).filter(([key]) => key !== 'rewrite');
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

function joinDraftSections(sections: Array<[string, string | null | undefined]>): string {
  return sections
    .map(([label, value]) => {
      const text = (value || '').trim();
      return text ? `${label}:\n${text}` : '';
    })
    .filter(Boolean)
    .join('\n\n')
    .slice(0, 28000);
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
  const title = job.script_title || jobTitle(job);
  const hook = firstDraftText(job.hook, analysisText(job, 'hook_vi'), draftText(rewrite.hook));
  const bigIdea = firstDraftText(
    job.big_idea,
    analysisText(job, 'main_idea_vi'),
    draftText(rewrite.big_idea),
    job.rewritten_script,
  );
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
    visualStyle: joinDraftSections([
      ['Định hướng hình ảnh từ người dùng', userDirection],
      ['Tóm tắt hình ảnh video gốc', job.visual_summary],
      ['Dữ liệu frame đại diện từ video gốc', frameNotes],
      ['Nhịp hình ảnh cần học và cải thiện', analysisText(job, 'visual_rhythm_vi')],
      ['Gợi ý hình ảnh từ bản rewrite', visualSuggestions],
    ]),
    sources: [
      {
        block_type: 'idea',
        content: joinDraftSections([
          ['Tên dự án', title],
          ['Ý tưởng chính', bigIdea],
          ['Hook nên dùng', hook],
          ['Ngôn ngữ của bản rewrite hiện tại', outputLanguageNote],
          ['Cơ hội viết mới từ phân tích', analysisText(job, 'rewrite_opportunities_vi')],
        ]),
      },
      {
        block_type: 'rough_script',
        content: joinDraftSections([
          ['Kịch bản mới đã duyệt', job.rewritten_script],
          ['Cấu trúc segment/cảnh từ bản rewrite', draftText(rewrite.segments)],
          ['Transcript gốc để đối chiếu', job.transcript_text],
        ]),
      },
      {
        block_type: 'character_notes',
        content: joinDraftSections([
          ['Nhân vật và bối cảnh', analysisText(job, 'characters_context_vi')],
          ['Bối cảnh/hình ảnh đã quan sát', job.visual_summary],
          ['Frame đại diện cần dùng làm dữ liệu hình ảnh', frameNotes],
          ['Ghi chú thêm từ người dùng', userDirection],
        ]),
      },
      {
        block_type: 'style_notes',
        content: joinDraftSections([
          ['Phong cách video', userDirection],
          ['Nhịp dựng / camera / mood', analysisText(job, 'visual_rhythm_vi')],
          ['Dữ liệu frame/video inspiration', frameNotes],
          ['Gợi ý hình ảnh theo từng đoạn', visualSuggestions],
          ['Ghi chú phân tích', analysisText(job, 'notes_vi')],
        ]),
      },
      {
        block_type: 'must_have',
        content: joinDraftSections([
          ['Bắt buộc giữ ý tưởng chính', bigIdea],
          ['Bắt buộc có hook', hook],
          ['Điểm mạnh cần giữ lại', analysisText(job, 'strengths_vi')],
          ['Cơ hội phát triển cần tận dụng', analysisText(job, 'rewrite_opportunities_vi')],
          ['Định hướng người dùng', userDirection],
        ]),
      },
      {
        block_type: 'avoid',
        content: joinDraftSections([
          ['Điểm yếu cần tránh/sửa', analysisText(job, 'weaknesses_vi')],
          ['Không được copy sát video gốc', draftText(rewrite.originality_note)],
          ['Lưu ý chất lượng', analysisText(job, 'notes_vi')],
          [
            'Nguyên tắc',
            'Không paraphrase transcript. Không tự chạy AI Video trước khi người dùng chọn thị trường, ngôn ngữ, thời lượng và cách chạy.',
          ],
          [
            'Cấu hình',
            'Không tự quyết định thị trường, ngôn ngữ final, thời lượng, tỷ lệ, voice hoặc chế độ chạy; người dùng sẽ chọn trong AI Video.',
          ],
        ]),
      },
    ],
    notice:
      'Đã đưa dữ liệu từ Video Inspiration vào form AI Video. Hãy chọn thị trường, ngôn ngữ, thời lượng và cách chạy trước khi tạo dự án.',
  };
}

function mutationError(...errors: unknown[]): string | null {
  const error = errors.find(Boolean);
  return error ? getErrorMessage(error) : null;
}

function useVideoInspirationMutations(setSelectedJobId: (jobId: string) => void) {
  const queryClient = useQueryClient();

  const rememberJob = (job: VideoInspirationJobResponse) => {
    queryClient.setQueryData(['video-inspiration', 'job', job.id], job);
    queryClient.invalidateQueries({ queryKey: ['video-inspiration', 'jobs'] });
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
      mutationFn: ({ jobId, allowAudioOnly }: { jobId: string; allowAudioOnly: boolean }) =>
        apiClient.analyzeVideoInspirationJob(jobId, { allow_audio_only: allowAudioOnly }),
      onSuccess: rememberJob,
    }),
    saveTranscript: useMutation({
      mutationFn: ({ jobId, text }: { jobId: string; text: string }) =>
        apiClient.updateVideoInspirationTranscript(jobId, { transcript_text: text }),
      onSuccess: rememberJob,
    }),
    saveDirection: useMutation({
      mutationFn: ({ jobId, userDirection }: { jobId: string; userDirection: string }) =>
        apiClient.updateVideoInspirationDirection(jobId, {
          user_direction: userDirection.trim() || null,
        }),
      onSuccess: rememberJob,
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
      onSuccess: rememberJob,
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
      onSuccess: rememberJob,
    }),
  };
}

export function VideoInspiration() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<VideoInspirationTargetLanguage>('vi');
  const [sourceUrl, setSourceUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [allowAudioOnly, setAllowAudioOnly] = useState(false);
  const [useBrowserCookies, setUseBrowserCookies] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [userDirectionDraft, setUserDirectionDraft] = useState('');
  const [transcriptDraft, setTranscriptDraft] = useState('');
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

  const jobs = jobsQuery.data?.items ?? [];
  const currentJob = jobQuery.data ?? currentJobFallback;
  const busy =
    mutations.upload.isPending ||
    mutations.fromUrl.isPending ||
    mutations.analyze.isPending ||
    mutations.saveTranscript.isPending ||
    mutations.saveDirection.isPending ||
    mutations.rewrite.isPending ||
    mutations.saveScript.isPending ||
    isJobActive(currentJob);
  const currentProgress = progressValue(currentJob);
  const entries = useMemo(() => analysisEntries(currentJob), [currentJob]);
  const primaryError =
    localError ||
    currentJob?.failure_reason ||
    mutationError(
      mutations.upload.error,
      mutations.fromUrl.error,
      mutations.analyze.error,
      mutations.saveTranscript.error,
      mutations.saveDirection.error,
      mutations.rewrite.error,
      mutations.saveScript.error,
      jobQuery.error,
      jobsQuery.error,
    );

  useEffect(() => {
    if (!selectedJobId && jobs[0]?.id) {
      setSelectedJobId(jobs[0].id);
    }
  }, [selectedJobId, jobs]);

  useEffect(() => {
    if (!currentJob) return;
    setTranscriptDraft(currentJob.transcript_text || '');
    setUserDirectionDraft(currentJob.user_direction || '');
    setScriptDraft(currentJob.rewritten_script || '');
    setScriptTitleDraft(currentJob.script_title || '');
    setBigIdeaDraft(currentJob.big_idea || '');
    setHookDraft(currentJob.hook || '');
    setTargetLanguage(currentJob.target_language);
  }, [currentJob]);

  const uploadDisabled = busy || !selectedFile;
  const urlDisabled = busy || !sourceUrl.trim();
  const canAnalyze = !!currentJob && !busy;
  const canRewrite = !!currentJob?.analysis_json && !busy;
  const canHandoff = !!currentJob?.rewritten_script?.trim() && !busy;
  const trimmedUserDirection = userDirectionDraft.trim();
  const directionChanged = (currentJob?.user_direction || '') !== trimmedUserDirection;
  const canSaveDirection = !!currentJob && !busy && directionChanged;

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
      setLocalError('Cần có kịch bản mới trước khi đưa sang form AI Video.');
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
              Đưa video vào, lấy lời nói và hình ảnh làm chất liệu, rồi viết thành kịch bản mới để
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
                  <p className="text-xs text-muted-foreground">MP4 hoặc link công khai</p>
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
                    disabled={busy}
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
                      disabled={busy}
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
                      disabled={busy}
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
                  <div className="grid grid-cols-2 gap-2">
                    {(['vi', 'en'] as const).map((language) => (
                      <Button
                        key={language}
                        type="button"
                        variant={targetLanguage === language ? 'default' : 'outline'}
                        className="h-11"
                        disabled={busy}
                        onClick={() => setTargetLanguage(language)}
                      >
                        {languageLabel(language)}
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
                    disabled={busy}
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
                    {mutations.saveDirection.isPending ? (
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
                    disabled={busy}
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
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canAnalyze}
                    onClick={() =>
                      currentJob &&
                      mutations.analyze.mutate({
                        jobId: currentJob.id,
                        allowAudioOnly,
                      })
                    }
                  >
                    {mutations.analyze.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    Phân tích video
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
                    {mutations.rewrite.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    Viết kịch bản mới
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
                <TabsTrigger value="analysis" className="min-h-10">
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Phân tích
                </TabsTrigger>
                <TabsTrigger value="script" className="min-h-10">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Kịch bản mới
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
                      disabled={!currentJob || busy}
                      onClick={() =>
                        currentJob &&
                        mutations.saveTranscript.mutate({
                          jobId: currentJob.id,
                          text: transcriptDraft,
                        })
                      }
                    >
                      {mutations.saveTranscript.isPending ? (
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
                    disabled={!currentJob || busy}
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
                      <h3 className="text-base font-semibold">Kịch bản mới</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Bản này dùng để điền form AI Video; anh tự chọn cấu hình rồi mới tạo/chạy.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!currentJob || busy || !scriptDraft.trim()}
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
                      {mutations.saveScript.isPending ? (
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
                        disabled={!currentJob || busy}
                        placeholder="Tên kịch bản mới"
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
                        disabled={!currentJob || busy}
                        placeholder="Ý chính của bản mới"
                        className="h-11"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium" htmlFor="video-script-hook">
                      Hook
                      <Input
                        id="video-script-hook"
                        value={hookDraft}
                        onChange={(event) => setHookDraft(event.target.value)}
                        disabled={!currentJob || busy}
                        placeholder="Mở đầu 0-3 giây"
                        className="h-11"
                      />
                    </label>
                  </div>

                  <Textarea
                    value={scriptDraft}
                    onChange={(event) => setScriptDraft(event.target.value)}
                    disabled={!currentJob || busy}
                    placeholder="Kịch bản mới sẽ xuất hiện sau khi bấm Viết kịch bản mới."
                    className="mt-4 min-h-[460px] resize-y text-sm leading-relaxed"
                  />
                </section>
              </TabsContent>
            </Tabs>
          </main>
        </div>
      </div>
    </div>
  );
}
