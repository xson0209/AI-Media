import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  FileImage,
  FileText,
  FileVideo,
  LibraryBig,
  Link as LinkIcon,
  Loader2,
  Plus,
  RefreshCw,
  Upload,
} from 'lucide-react';
import { useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import type { ResearchSourceResponse, ResearchSourceType, VideoSeriesResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import { numberValue, researchStatusLabel, stringList } from './researchUi';

const sourceOptions: Array<{ type: ResearchSourceType; label: string; icon: typeof FileText }> = [
  { type: 'video_url', label: 'Link video', icon: FileVideo },
  { type: 'video_upload', label: 'Tải video', icon: Upload },
  { type: 'story_url', label: 'Link truyện', icon: LinkIcon },
  { type: 'image_upload', label: 'Tải ảnh', icon: FileImage },
  { type: 'screenshot_upload', label: 'Screenshot repo', icon: FileImage },
  { type: 'github_repo', label: 'GitHub repo', icon: LinkIcon },
  { type: 'text', label: 'Dán text', icon: FileText },
  { type: 'docs_url', label: 'Link tài liệu', icon: LinkIcon },
  { type: 'series_memory', label: 'Bộ nhớ Series', icon: LibraryBig },
];

const activeSourceStatuses = new Set(['queued', 'analyzing']);

interface SourcePanelProps {
  projectId: string;
  onNotice: (message: string) => void;
}

export function SourcePanel({ projectId, onNotice }: SourcePanelProps) {
  const queryClient = useQueryClient();
  const [sourceType, setSourceType] = useState<ResearchSourceType>('video_url');
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [repositoryRef, setRepositoryRef] = useState('');
  const [screenshotRepositoryUrl, setScreenshotRepositoryUrl] = useState('');
  const [seriesId, setSeriesId] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isUrl = sourceType === 'video_url' || sourceType === 'story_url' || sourceType === 'docs_url' || sourceType === 'github_repo';
  const isUpload = sourceType === 'video_upload' || sourceType === 'image_upload' || sourceType === 'screenshot_upload';
  const isSeriesMemory = sourceType === 'series_memory';
  const canSubmitSource = sourceType === 'text'
    ? Boolean(sourceText.trim())
    : sourceType === 'docs_url'
      ? Boolean(sourceUrl.trim() || sourceText.trim())
      : sourceType === 'video_url' || sourceType === 'story_url' || sourceType === 'github_repo'
        ? Boolean(sourceUrl.trim())
        : false;

  const sourcesQuery = useQuery({
    queryKey: ['research', 'sources', projectId],
    queryFn: () => apiClient.listResearchSources(projectId),
    refetchInterval: (query) => query.state.data?.some((source) => activeSourceStatuses.has(source.status)) ? 2500 : false,
  });

  const seriesQuery = useQuery({
    queryKey: ['ai-video', 'series', 'research-source-picker'],
    queryFn: () => apiClient.listVideoSeries(),
    enabled: sourceType === 'series_memory',
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['research', 'sources', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'ideas', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'scores', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'recommendation', projectId] });
  };

  const sourceMutation = useMutation({
    mutationFn: () => apiClient.addResearchTextSource(projectId, {
      source_type: sourceType,
      title: sourceTitle.trim() || undefined,
      input_url: isUrl ? sourceUrl.trim() || undefined : undefined,
      repository_ref: (sourceType === 'github_repo' || sourceType === 'screenshot_upload') ? repositoryRef.trim() || undefined : undefined,
      content: sourceType === 'text' || sourceType === 'docs_url' ? sourceText.trim() || undefined : undefined,
    }),
    onSuccess: () => {
      setSourceTitle('');
      setSourceUrl('');
      setSourceText('');
      setRepositoryRef('');
      setScreenshotRepositoryUrl('');
      onNotice('Đã thêm nguồn. Link video/truyện đang chạy pipeline phân tích tương ứng; text có thể review ngay.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không thêm được nguồn.'),
  });

  const seriesMemoryMutation = useMutation({
    mutationFn: () => apiClient.linkResearchSeriesMemory(projectId, {
      series_id: seriesId,
      max_chars: 40000,
    }),
    onSuccess: () => {
      setSeriesId('');
      onNotice('Đã liên kết trực tiếp Series Memory. Research chỉ đọc canon đã duyệt và không sửa Series nguồn.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không liên kết được Series Memory.'),
  });

  const retryMutation = useMutation({
    mutationFn: (sourceId: string) => apiClient.retryResearchSource(projectId, sourceId),
    onSuccess: (source) => {
      onNotice(source.status === 'needs_review'
        ? 'Nguồn public không qua được policy. Hãy upload file hoặc dán nội dung.'
        : 'Đã yêu cầu pipeline nguồn phân tích lại và cập nhật source package.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không thử lại được nguồn.'),
  });

  const approveMutation = useMutation({
    mutationFn: (source: ResearchSourceResponse) => apiClient.approveResearchSource(
      projectId,
      source.id,
      `Memory proposal: ${source.title || source.source_type}`,
    ),
    onSuccess: () => {
      onNotice('Đã tạo memory proposal dạng ứng viên. Nội dung chưa trở thành canon cho tới khi bạn duyệt.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không tạo được memory proposal.'),
  });

  const handleUpload = async (file: File) => {
    setUploadProgress(12);
    try {
      await apiClient.uploadResearchSource(projectId, sourceType, file, sourceTitle.trim() || file.name, {
        repository_url: sourceType === 'screenshot_upload' ? screenshotRepositoryUrl.trim() || undefined : undefined,
        repository_ref: sourceType === 'screenshot_upload' ? repositoryRef.trim() || undefined : undefined,
      });
      setUploadProgress(100);
      onNotice(sourceType === 'screenshot_upload'
        ? 'Đã lưu screenshot gốc và chuyển sang pipeline đọc màn hình/repository. Ảnh gốc sẽ được giữ cho bước dựng AI Video.'
        : 'Đã lưu original riêng và chuyển nguồn vào pipeline Video Inspiration hoặc Comic Analysis.');
      refresh();
    } catch (error) {
      setUploadProgress(0);
      onNotice(error instanceof Error ? error.message : 'Không tải được nguồn.');
    } finally {
      window.setTimeout(() => setUploadProgress(0), 800);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const selectSourceType = (nextType: ResearchSourceType) => {
    if (nextType === sourceType) return;
    setSourceType(nextType);
    setSourceTitle('');
    setSourceUrl('');
    setSourceText('');
    setRepositoryRef('');
    setScreenshotRepositoryUrl('');
    setSeriesId('');
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const selectedSeries = (seriesQuery.data ?? []).find((series) => series.id === seriesId);

  return (
    <div className="space-y-3">
      <section className="border border-border bg-card p-3" aria-label="Thêm nguồn nghiên cứu">
        <fieldset className="flex flex-wrap gap-2">
          <legend className="sr-only">Loại nguồn</legend>
          {sourceOptions.map((option) => {
            const Icon = option.icon;
            return (
              <Button
                key={option.type}
                type="button"
                size="sm"
                variant={sourceType === option.type ? 'default' : 'outline'}
                aria-pressed={sourceType === option.type}
                onClick={() => selectSourceType(option.type)}
              >
                <Icon className="mr-1.5 h-4 w-4" aria-hidden="true" />
                {option.label}
              </Button>
            );
          })}
        </fieldset>

        <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <div className="min-w-0 space-y-2">
            {!isSeriesMemory && <Input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} placeholder="Tên nguồn (không bắt buộc)" aria-label="Tên nguồn" />}
            {isUrl && <Input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="Dán link HTTP/HTTPS public" aria-label="Link nguồn public" />}
            {(sourceType === 'github_repo' || sourceType === 'screenshot_upload') && <Input value={repositoryRef} onChange={(event) => setRepositoryRef(event.target.value)} placeholder="Branch/tag/commit (mặc định branch chính)" aria-label="Branch hoặc commit repo" />}
            {sourceType === 'screenshot_upload' && <Input value={screenshotRepositoryUrl} onChange={(event) => setScreenshotRepositoryUrl(event.target.value)} placeholder="Repo GitHub liên quan (không bắt buộc)" aria-label="Repo GitHub liên quan" />}
            {(sourceType === 'text' || sourceType === 'docs_url') && (
              <Textarea value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder="Dán nội dung, tài liệu hoặc ghi chú nghiên cứu" className="min-h-28" aria-label="Nội dung nguồn" />
            )}
            {isSeriesMemory && (
              <div className="space-y-2">
                <div>
                  <label htmlFor="research-series-memory" className="text-sm font-medium">Series cần nghiên cứu</label>
                  <Select value={seriesId} onValueChange={setSeriesId}>
                    <SelectTrigger id="research-series-memory" className="mt-1.5 min-h-11">
                      <SelectValue placeholder={seriesQuery.isLoading ? 'Đang tải danh sách series...' : 'Chọn Series Memory'} />
                    </SelectTrigger>
                    <SelectContent>
                      {(seriesQuery.data ?? []).map((series) => (
                        <SelectItem key={series.id} value={series.id}>{series.title}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {selectedSeries && <SeriesMemoryPreview series={selectedSeries} />}
                {!seriesQuery.isLoading && !(seriesQuery.data ?? []).length && (
                  <p className="text-sm text-muted-foreground">Chưa có Series trong AI Video hoặc Story Studio.</p>
                )}
              </div>
            )}
          </div>
          <div>
            {isSeriesMemory ? (
              <Button type="button" disabled={seriesMemoryMutation.isPending || !seriesId} onClick={() => seriesMemoryMutation.mutate()}>
                {seriesMemoryMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LibraryBig className="mr-2 h-4 w-4" />}
                Liên kết memory
              </Button>
            ) : isUpload ? (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="sr-only"
                  accept={sourceType === 'image_upload' || sourceType === 'screenshot_upload' ? 'image/*' : 'video/mp4'}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void handleUpload(file);
                  }}
                />
                <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="mr-2 h-4 w-4" /> Chọn file
                </Button>
              </>
            ) : (
              <Button type="button" disabled={sourceMutation.isPending || !canSubmitSource} onClick={() => sourceMutation.mutate()}>
                {sourceMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                Thêm nguồn
              </Button>
            )}
          </div>
        </div>
        {uploadProgress > 0 && (
          <output className="mt-3 block" aria-live="polite">
            <div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Kiểm tra và lưu nguồn</span><span>{uploadProgress}%</span></div>
            <Progress value={uploadProgress} className="h-2" />
          </output>
        )}
      </section>

      {sourcesQuery.isLoading && <div className="flex justify-center p-8"><Loader2 className="h-5 w-5 animate-spin" /></div>}
      {(sourcesQuery.data ?? []).map((source) => <SourceRow
        key={source.id}
        source={source}
        retrying={retryMutation.isPending}
        approving={approveMutation.isPending}
        onRetry={() => retryMutation.mutate(source.id)}
        onApprove={() => approveMutation.mutate(source)}
      />)}
      {!sourcesQuery.isLoading && !(sourcesQuery.data ?? []).length && (
        <div className="border border-dashed border-border p-8 text-center text-sm text-muted-foreground">Chưa có nguồn nghiên cứu.</div>
      )}
    </div>
  );
}

function SourceRow({ source, retrying, approving, onRetry, onApprove }: {
  source: ResearchSourceResponse;
  retrying: boolean;
  approving: boolean;
  onRetry: () => void;
  onApprove: () => void;
}) {
  const progress = Math.round(numberValue(source.result.progress) * 100);
  const summary = typeof source.result.summary === 'string' ? source.result.summary : 'Chưa có tóm tắt.';
  const validation = source.result.media_validation && typeof source.result.media_validation === 'object'
    ? source.result.media_validation as Record<string, unknown>
    : null;
  const adapter = source.result.adapter && typeof source.result.adapter === 'object'
    ? source.result.adapter as Record<string, unknown>
    : null;
  const limitations = stringList(source.limitations);
  const canRetry = ['queued', 'partial', 'needs_review', 'failed', 'stale'].includes(source.status);
  const proposalCreated = typeof source.result.memory_proposal_id === 'string';
  const isSeriesMemory = source.source_type === 'series_memory';
  const Icon = isSeriesMemory ? LibraryBig : source.source_type.includes('video') ? FileVideo : source.source_type.includes('image') || source.source_type === 'screenshot_upload' ? FileImage : source.source_type === 'github_repo' ? LinkIcon : FileText;
  const seriesRevision = numberValue(source.provenance.series_revision);

  return (
    <article className="border border-border bg-card p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-border bg-muted/40"><Icon className="h-4 w-4" /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="break-words text-sm font-medium">{source.title || source.source_type}</h3>
              <Badge variant={source.status === 'needs_review' || source.status === 'failed' ? 'destructive' : 'outline'}>{researchStatusLabel(source.status)}</Badge>
              <Badge variant="secondary">r{source.revision}</Badge>
            </div>
            <p className="mt-1 break-words text-sm leading-6 text-muted-foreground">{summary}</p>
            {source.source_type === 'github_repo' && typeof source.result.repository === 'object' && source.result.repository ? <p className="mt-1 text-xs text-muted-foreground">Commit: {String((source.result.repository as Record<string, unknown>).commit_sha || 'chưa resolve')} · Files: {numberValue((source.result.coverage as Record<string, unknown> | undefined)?.files_read)}</p> : null}
            {source.source_type === 'screenshot_upload' && Array.isArray(source.result.visual_assets) ? <p className="mt-1 text-xs text-muted-foreground">Ảnh gốc được giữ lại · {numberValue((source.result.visual_assets as unknown[]).length)} asset · {Array.isArray(source.result.evidence_refs) ? source.result.evidence_refs.length : 0} vùng có bằng chứng</p> : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canRetry && <Button size="sm" variant="outline" disabled={retrying} onClick={onRetry}>{retrying ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1.5 h-4 w-4" />} {isSeriesMemory ? 'Làm mới memory' : 'Thử lại'}</Button>}
          {!proposalCreated && ['ready_for_review', 'partial', 'approved'].includes(source.status) && (
            <Button size="sm" variant="outline" disabled={approving} onClick={onApprove}>{approving ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Check className="mr-1.5 h-4 w-4" />} Tạo memory proposal</Button>
          )}
        </div>
      </div>

      <div className="mt-3 grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground"><span>Tiến trình gói nguồn</span><span>{progress}%</span></div>
          <Progress value={progress} className="mt-1.5 h-2" />
        </div>
        <div className="text-xs leading-5 text-muted-foreground">
          {isSeriesMemory ? (
            <p>Nguồn nội bộ chỉ đọc · Series r{seriesRevision || 1} · chỉ dùng canon đã duyệt.</p>
          ) : validation ? (
            <p>{String(validation.detected_mime || 'Media hợp lệ')} · {numberValue(validation.byte_size).toLocaleString('vi-VN')} byte{validation.duration_seconds ? ` · ${Math.round(numberValue(validation.duration_seconds))} giây` : ''}{validation.width ? ` · ${validation.width}×${validation.height}` : ''}</p>
          ) : <p>URL/text được coi là dữ liệu không tin cậy; không được dùng làm system instruction.</p>}
          {adapter && <p>Pipeline: {adapter.pipeline === 'video_inspiration' ? 'Video Inspiration' : adapter.pipeline === 'document_fetch' ? 'Trình đọc tài liệu' : 'Comic Series Analysis'}{adapter.job_id ? ` · job ${String(adapter.job_id).slice(0, 8)}` : ''}</p>}
        </div>
      </div>

      {(source.error_code || limitations.length > 0) && (
        <div className={cn('mt-3 flex items-start gap-2 border px-3 py-2 text-xs leading-5', source.error_code ? 'border-destructive/40 bg-destructive/5' : 'border-amber-500/40 bg-amber-500/5')} role={source.error_code ? 'alert' : undefined}>
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{source.error_code ? `${source.error_code}: ` : ''}{limitations.join(' · ')}</p>
        </div>
      )}
    </article>
  );
}

function SeriesMemoryPreview({ series }: { series: VideoSeriesResponse }) {
  return (
    <div className="border border-border bg-muted/30 px-3 py-2 text-sm" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{series.title}</span>
        <Badge variant="secondary">r{series.revision}</Badge>
      </div>
      <p className="mt-1 text-muted-foreground">
        {series.video_episode_count} tập video · {series.story_episode_count} tập truyện · {series.character_profiles.length} nhân vật
      </p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">Nghiên cứu sẽ đọc trực tiếp bộ nhớ đã duyệt qua Series Brain. Series nguồn không bị chỉnh sửa.</p>
    </div>
  );
}
