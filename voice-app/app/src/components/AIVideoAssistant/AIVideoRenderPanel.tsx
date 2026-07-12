import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Check, Download, FileText, Film, Loader2, Music2, Settings2, Sparkles, Trash2, UploadCloud, Video } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import type { DownloadedBlob, VideoRenderSettings, VideoRenderSfxAssetResponse, VideoShotResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';

interface AIVideoRenderPanelProps {
  projectId: string | null | undefined;
  shots: VideoShotResponse[];
  onNotice: (message: string) => void;
}

const DEFAULT_SETTINGS: VideoRenderSettings = {
  resolution: 'auto',
  fps: 30,
  fit_mode: 'crop',
  duration_mode: 'freeze',
  subtitle_mode: 'burn_in',
  mute_clip_audio: true,
  background_color: '#111827',
  enhanced_render: true,
  enhanced_audio: true,
  ai_review: true,
  max_fix_attempts: 1,
};

function shotLabel(shot: VideoShotResponse): string {
  return `Segment ${String(shot.shot_order).padStart(2, '0')}`;
}

function formatDuration(value?: number | null): string {
  if (!value) return 'chưa rõ';
  return `${value.toFixed(value >= 10 ? 1 : 2)}s`;
}

function statusTone(ok: boolean) {
  return ok
    ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200';
}

function RenderSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((index) => (
        <div key={index} className="rounded-lg border border-border/70 p-3">
          <div className="h-4 w-28 animate-pulse rounded bg-muted" />
          <div className="mt-3 h-3 w-full animate-pulse rounded bg-muted" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

export function AIVideoRenderPanel({ projectId, shots, onNotice }: AIVideoRenderPanelProps) {
  const platform = usePlatform();
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState<VideoRenderSettings>(DEFAULT_SETTINGS);
  const [uploadingShotId, setUploadingShotId] = useState<string | null>(null);

  const enabled = !!projectId && shots.length > 0;
  const renderQueryKey = useMemo(() => ['ai-video', 'render', projectId, settings], [projectId, settings]);

  const clipQueries = useQueries({
    queries: shots.map((shot) => ({
      queryKey: ['ai-video', 'shot-clip', projectId, shot.id],
      queryFn: () => apiClient.getVideoShotClip(projectId!, shot.id),
      enabled,
      retry: false,
    })),
  });

  const readinessQuery = useQuery({
    queryKey: [...renderQueryKey, 'readiness'],
    queryFn: () => apiClient.getVideoRenderReadiness(projectId!, settings),
    enabled,
  });

  const latestJobQuery = useQuery({
    queryKey: ['ai-video', 'render-job-latest', projectId],
    queryFn: () => apiClient.getLatestVideoRenderJob(projectId!),
    enabled: !!projectId,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 2000 : false;
    },
  });

  const sfxAssetsQuery = useQuery({
    queryKey: ['ai-video', 'render-sfx-assets', projectId],
    queryFn: () => apiClient.listVideoRenderSfxAssets(projectId!),
    enabled: !!projectId,
    retry: false,
  });

  const invalidateRender = () => {
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'shot-clip'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-sfx-assets', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-job-latest', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'debug', projectId] });
  };

  const uploadClip = useMutation({
    mutationFn: ({ shot, file }: { shot: VideoShotResponse; file: File }) => apiClient.uploadVideoShotClip(shot.project_id, shot.id, file),
    onMutate: ({ shot }) => setUploadingShotId(shot.id),
    onSuccess: (_, { shot }) => {
      onNotice(`Đã upload video clip cho ${shotLabel(shot)}.`);
      invalidateRender();
    },
    onSettled: () => setUploadingShotId(null),
  });

  const deleteClip = useMutation({
    mutationFn: (shot: VideoShotResponse) => apiClient.deleteVideoShotClip(shot.project_id, shot.id),
    onSuccess: (_, shot) => {
      onNotice(`Đã xóa video clip của ${shotLabel(shot)}.`);
      invalidateRender();
    },
  });

  const uploadSfxAsset = useMutation({
    mutationFn: (file: File) => apiClient.uploadVideoRenderSfxAsset(projectId!, file),
    onSuccess: (asset) => {
      onNotice(`Đã upload SFX/BGM: ${asset.filename}.`);
      invalidateRender();
    },
  });

  const deleteSfxAsset = useMutation({
    mutationFn: (asset: VideoRenderSfxAssetResponse) => apiClient.deleteVideoRenderSfxAsset(projectId!, asset.asset_id),
    onSuccess: () => {
      onNotice('Đã xóa asset SFX/BGM.');
      invalidateRender();
    },
  });

  const createRender = useMutation({
    mutationFn: () => apiClient.createVideoRenderJob(projectId!, settings),
    onSuccess: () => {
      onNotice('Đã bắt đầu dựng MP4. Bạn có thể theo dõi tiến độ trong panel này.');
      invalidateRender();
    },
  });

  const saveDownload = async (download: Promise<DownloadedBlob>) => {
    const result = await download;
    await platform.filesystem.saveFile(result.filename, result.blob, [{ name: 'Tệp render', extensions: ['mp4', 'md', 'json', 'csv'] }]);
  };

  const latestJob = latestJobQuery.data;
  const readiness = readinessQuery.data;
  const sfxAssets = sfxAssetsQuery.data ?? [];
  const busy = latestJob?.status === 'queued' || latestJob?.status === 'running';
  const reviewArtifact = latestJob?.enhanced_artifacts_json?.items?.find((item) => item.kind === 'ai_review_report');
  const manifestArtifact = latestJob?.enhanced_artifacts_json?.items?.find((item) => item.kind === 'timeline_manifest');
  const operationError = uploadClip.error || deleteClip.error || uploadSfxAsset.error || deleteSfxAsset.error || createRender.error;

  if (!projectId) {
    return (
      <section className="min-w-0 rounded-lg border border-border/80 bg-card/60 p-4 sm:p-5">
        <RenderHeader />
        <div className="mt-4 rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
          Chọn hoặc tạo dự án để dựng nhanh MP4.
        </div>
      </section>
    );
  }

  return (
    <section className="min-w-0 rounded-lg border border-border/80 bg-card/60 p-4 sm:p-5">
      <RenderHeader />

      <div className="mt-4 space-y-4">
        {shots.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
            Chưa có segment. Hãy tạo segment breakdown trước khi upload clip và dựng MP4.
          </div>
        ) : clipQueries.some((query) => query.isLoading) ? (
          <RenderSkeleton />
        ) : (
          <div className="space-y-3">
            {shots.map((shot, index) => {
              const clip = clipQueries[index]?.data;
              const clipMissing = readiness?.missing_clip_shot_ids.includes(shot.id);
              const clipInvalid = readiness?.invalid_clip_shot_ids.includes(shot.id) || clip?.status === 'failed';
              const needsVoice = readiness?.missing_voice_shot_ids.includes(shot.id);
              const needsTimer = readiness?.missing_timer_shot_ids.includes(shot.id);
              const isUploading = uploadingShotId === shot.id;
              const requirementBadges = [
                clipMissing ? 'Cần clip' : null,
                needsVoice ? 'Cần voice' : null,
                needsTimer ? 'Cần thời lượng' : null,
              ].filter((label): label is string => Boolean(label));
              return (
                <div
                  key={shot.id}
                  className="rounded-xl border border-border/70 bg-background/80 p-3 shadow-[0_16px_36px_-30px_rgba(15,23,42,0.45)] transition duration-200 active:translate-y-[1px] active:scale-[0.995]"
                >
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <p className="min-w-0 text-sm font-semibold leading-tight tracking-tight">{shotLabel(shot)}</p>
                    <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5', statusTone(!!clip && clip.status === 'ready'))}>
                      {clip?.status === 'ready' ? 'clip sẵn sàng' : clipInvalid ? 'clip lỗi' : 'thiếu clip'}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <div className="rounded-lg border border-border/60 bg-card/40 px-2.5 py-2">
                      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Timer</p>
                      <p className="mt-1 truncate text-xs font-semibold text-foreground">
                        {formatDuration(shot.english_narration?.trim() ? shot.audio_duration : shot.duration_seconds)}
                      </p>
                    </div>
                    <div className="rounded-lg border border-border/60 bg-card/40 px-2.5 py-2">
                      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Clip</p>
                      <p className="mt-1 truncate text-xs font-semibold text-foreground">{formatDuration(clip?.duration_seconds)}</p>
                    </div>
                  </div>

                  {clip?.original_filename ? (
                    <p className="mt-2 truncate text-xs leading-relaxed text-foreground/75">File: {clip.original_filename}</p>
                  ) : null}
                  {clip?.failure_reason ? <p className="mt-2 text-xs leading-relaxed text-destructive">{clip.failure_reason}</p> : null}
                  {requirementBadges.length ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {requirementBadges.map((label) => (
                        <span
                          key={label}
                          className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-[11px] font-medium leading-none text-amber-800 dark:text-amber-200"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="mt-3 grid gap-2">
                    <label
                      aria-disabled={isUploading}
                      className={cn(
                        'flex min-h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-input bg-card/70 px-3 py-2 text-sm font-medium text-foreground transition duration-200 hover:border-accent hover:bg-accent hover:text-accent-foreground active:translate-y-[1px]',
                        isUploading && 'pointer-events-none opacity-60',
                      )}
                    >
                      {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                      <span className="truncate">{isUploading ? 'Đang upload' : clip ? 'Thay clip' : 'Chọn clip'}</span>
                      <input
                        type="file"
                        accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                        className="sr-only"
                        disabled={isUploading}
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          if (file) uploadClip.mutate({ shot, file });
                          event.currentTarget.value = '';
                        }}
                      />
                    </label>
                    <p className="text-[11px] leading-relaxed text-muted-foreground">MP4, MOV, WEBM hoặc MKV.</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-10 w-full active:translate-y-[1px]"
                      disabled={!clip || deleteClip.isPending}
                      onClick={() => deleteClip.mutate(shot)}
                    >
                      {deleteClip.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      Xóa clip
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="grid gap-3 border-t border-border/70 pt-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Settings2 className="h-4 w-4" />
            Thiết lập render
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <SettingSelect label="Độ phân giải" value={settings.resolution} onChange={(value) => setSettings((current) => ({ ...current, resolution: value as VideoRenderSettings['resolution'] }))}>
              <option value="auto">Theo tỷ lệ dự án</option>
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
            </SettingSelect>
            <SettingSelect label="FPS" value={String(settings.fps)} onChange={(value) => setSettings((current) => ({ ...current, fps: Number(value) }))}>
              <option value="24">24</option>
              <option value="30">30</option>
              <option value="60">60</option>
            </SettingSelect>
            <SettingSelect label="Khung hình" value={settings.fit_mode} onChange={(value) => setSettings((current) => ({ ...current, fit_mode: value as VideoRenderSettings['fit_mode'] }))}>
              <option value="crop">Crop đầy khung</option>
              <option value="pad">Giữ toàn ảnh</option>
            </SettingSelect>
            <SettingSelect label="Phụ đề" value={settings.subtitle_mode} onChange={(value) => setSettings((current) => ({ ...current, subtitle_mode: value as VideoRenderSettings['subtitle_mode'] }))}>
              <option value="burn_in">Burn-in vào video</option>
              <option value="sidecar">SRT rời</option>
              <option value="none">Không phụ đề</option>
            </SettingSelect>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Burn-in dùng file .srt đã chia cue theo voice và render karaoke màu vàng theo từng từ. Nếu timing lệch, tạo lại phụ đề sau khi voice đã hoàn tất.
          </p>
        </div>

        <div className="min-w-0 rounded-lg border border-border/75 bg-background/70 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4" />
            Hiệu ứng giữ chân
          </div>
          <div className="mt-3 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,9.5rem),1fr))]">
            <ToggleRow
              label="Chuyển cảnh/SFX"
              checked={Boolean(settings.enhanced_render)}
              onChange={(checked) => setSettings((current) => ({ ...current, enhanced_render: checked }))}
            />
            <ToggleRow
              label="Mix SFX/BGM thật"
              checked={Boolean(settings.enhanced_audio)}
              disabled={!settings.enhanced_render}
              onChange={(checked) => setSettings((current) => ({ ...current, enhanced_audio: checked }))}
            />
            <ToggleRow
              label="AI review"
              checked={Boolean(settings.ai_review)}
              disabled={!settings.enhanced_render}
              onChange={(checked) => setSettings((current) => ({ ...current, ai_review: checked }))}
            />
          </div>
          <div className="mt-3 grid min-w-0 gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr))] sm:items-end">
            <SettingSelect
              label="Số vòng auto-fix"
              value={String(settings.max_fix_attempts ?? 1)}
              onChange={(value) => setSettings((current) => ({ ...current, max_fix_attempts: Number(value) }))}
            >
              <option value="0">0</option>
              <option value="1">1</option>
              <option value="2">2</option>
            </SettingSelect>
            <label
              aria-disabled={uploadSfxAsset.isPending}
              className={cn(
                'flex min-h-11 w-full min-w-0 cursor-pointer items-center justify-center gap-2 rounded-lg border border-input bg-card/70 px-3 py-2 text-center text-sm font-medium leading-tight text-foreground transition hover:border-accent hover:bg-accent hover:text-accent-foreground active:translate-y-[1px]',
                uploadSfxAsset.isPending && 'pointer-events-none opacity-60',
              )}
            >
              {uploadSfxAsset.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Music2 className="h-4 w-4" />}
              <span className="min-w-0 whitespace-normal">{uploadSfxAsset.isPending ? 'Đang upload' : 'Thêm SFX/BGM'}</span>
              <input
                type="file"
                accept="audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/flac,.wav,.mp3,.m4a,.aac,.ogg,.flac"
                className="sr-only"
                disabled={uploadSfxAsset.isPending}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  if (file) uploadSfxAsset.mutate(file);
                  event.currentTarget.value = '';
                }}
              />
            </label>
          </div>
          {sfxAssets.length ? (
            <div className="grid gap-2">
              {sfxAssets.map((asset) => (
                <div key={asset.asset_id} className="flex min-w-0 items-center justify-between gap-2 rounded-lg border border-border/60 px-2.5 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold">{asset.filename}</p>
                    <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                      {(asset.cue_aliases || []).join(', ') || 'chưa có alias'} · {asset.status}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 shrink-0 p-0"
                    disabled={deleteSfxAsset.isPending}
                    onClick={() => deleteSfxAsset.mutate(asset)}
                    title="Xóa asset"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-muted-foreground">
              Chưa có asset SFX/BGM. Cue như tiếng kính vỡ sẽ được ghi fallback nếu chưa upload asset thật.
            </p>
          )}
        </div>

        <div className={cn('rounded-lg border p-3 text-sm', statusTone(!!readiness?.ready))}>
          <div className="flex items-start gap-2">
            {readiness?.ready ? <Check className="mt-0.5 h-4 w-4" /> : <AlertCircle className="mt-0.5 h-4 w-4" />}
            <div className="min-w-0">
              <p className="font-medium">{readiness?.ready ? 'Đã đủ điều kiện dựng MP4.' : 'Chưa đủ điều kiện dựng MP4.'}</p>
              {!readiness ? <p className="mt-1 text-xs opacity-80">Đang kiểm tra readiness render.</p> : null}
              {readiness && !readiness.ready ? (
                <ul className="mt-2 space-y-1 text-xs opacity-85">
                  {readiness.missing_reasons.map((reason) => <li key={reason}>{reason}</li>)}
                </ul>
              ) : null}
              {readiness?.warnings.length ? (
                <ul className="mt-2 space-y-1 text-xs opacity-85">
                  {readiness.warnings.map((warning) => <li key={`${warning.code}-${warning.shot_id}`}>{warning.message}</li>)}
                </ul>
              ) : null}
            </div>
          </div>
        </div>

        {operationError ? <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{operationError instanceof Error ? operationError.message : 'Có lỗi không xác định.'}</div> : null}

        {latestJob ? (
          <div className="rounded-lg border border-border/75 bg-background/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Lần dựng gần nhất</p>
                <p className="mt-1 text-xs text-muted-foreground">{latestJob.current_step || latestJob.status}</p>
              </div>
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">{Math.round((latestJob.progress || 0) * 100)}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-emerald-600 transition-[width] duration-300" style={{ width: `${Math.round((latestJob.progress || 0) * 100)}%` }} />
            </div>
            {latestJob.failure_reason ? <p className="mt-2 text-xs leading-relaxed text-destructive">{latestJob.failure_reason}</p> : null}
            {latestJob.review_status ? (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="rounded-full border border-border px-2 py-1">Review: {latestJob.review_status}</span>
                <span className="rounded-full border border-border px-2 py-1">Auto-fix: {latestJob.fix_attempt_count ?? 0}</span>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="grid min-w-0 gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,9.75rem),1fr))]">
          <Button className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]" disabled={!readiness?.ready || busy || createRender.isPending} onClick={() => createRender.mutate()}>
            {createRender.isPending || busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Video className="h-4 w-4" />}
            <span className="min-w-0">Dựng MP4</span>
          </Button>
          <Button
            className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]"
            variant="outline"
            disabled={!latestJob || latestJob.status !== 'completed' || latestJob.stale}
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderJob(projectId, latestJob.id))}
          >
            <Download className="h-4 w-4" />
            <span className="min-w-0">Tải MP4</span>
          </Button>
          <Button
            className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]"
            variant="outline"
            disabled={!latestJob || latestJob.status !== 'completed' || !reviewArtifact}
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderEnhancedArtifact(projectId, latestJob.id, reviewArtifact?.kind || 'ai_review_report'))}
          >
            <FileText className="h-4 w-4" />
            <span className="min-w-0">Tải AI review</span>
          </Button>
          <Button
            className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]"
            variant="outline"
            disabled={!latestJob || latestJob.status !== 'completed' || !manifestArtifact}
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderEnhancedArtifact(projectId, latestJob.id, manifestArtifact?.kind || 'timeline_manifest'))}
          >
            <Download className="h-4 w-4" />
            <span className="min-w-0">Tải manifest</span>
          </Button>
        </div>
      </div>
    </section>
  );
}

function RenderHeader() {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background">
          <Film className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold tracking-tight">Dựng nhanh MP4</h2>
          <p className="truncate text-xs text-muted-foreground">Ghép clip, voice và phụ đề theo timer thật</p>
        </div>
      </div>
    </div>
  );
}

function ToggleRow({ label, checked, disabled, onChange }: { label: string; checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label
      className={cn(
        'flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/40 px-3 py-2 text-sm font-medium leading-tight',
        disabled && 'opacity-55',
      )}
    >
      <span className="min-w-0 whitespace-normal">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.checked)}
        className="h-4 w-4 shrink-0 accent-emerald-600"
      />
    </label>
  );
}

function SettingSelect({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-foreground">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
      >
        {children}
      </select>
      <span className="text-xs font-normal leading-relaxed text-muted-foreground">Có thể đổi trước khi bấm Dựng MP4.</span>
    </label>
  );
}
