import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Check, Download, Eye, FileText, Film, Layers, Loader2, Music2, Settings2, Sparkles, Trash2, UploadCloud, Video } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import type {
  DownloadedBlob,
  VideoLanguage,
  VideoRenderReadinessResponse,
  VideoRenderSettings,
  VideoRenderSfxAssetResponse,
  VideoRenderWatermarkBackendStatus,
  VideoSourceVisualAsset,
  VideoShotClipBatchResult,
  VideoShotResponse,
} from '@/lib/api/types';
import {
  buildClipBatchPlan,
  clipBatchSkipReasonLabel,
  type ClipBatchMatched,
  type ClipBatchPlan,
} from '@/lib/clipBatchMatch';
import {
  CLIP_AUDIO_CHOICE_BED,
  CLIP_AUDIO_CHOICE_CLIP_ONLY,
  CLIP_AUDIO_CHOICE_DROP,
  type ClipAudioChoice,
  clipAudioChoiceFromSettings,
  loadRenderSettings,
  saveRenderSettings,
  settingsForClipAudioChoice,
} from '@/lib/renderSettingsStore';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';

interface AIVideoRenderPanelProps {
  projectId: string | null | undefined;
  shots: VideoShotResponse[];
  targetLanguage?: VideoLanguage | null;
  /** API namespace used by the shared panel (News Video uses /news-video). */
  apiPrefix?: string;
  /** Explicit project speech mode; legacy routes fall back to target language. */
  speechSource?: string | null;
  onNotice: (message: string) => void;
}

/** Shared by the batch picker and the per-shot picker so both take the same formats. */
const CLIP_FILE_ACCEPT = 'video/mp4,video/quicktime,video/webm,video/x-matroska';

/**
 * Provider recorded for clips picked through the batch import. It only narrows the
 * watermark mark scan from every detector down to one; a wrong value costs cleanup
 * coverage but never damages the clip, which is why defaulting it is safe.
 */
const BATCH_CLIP_PROVIDER = 'veo';

function shotLabel(shot: VideoShotResponse): string {
  return `Phân đoạn ${String(shot.shot_order).padStart(2, '0')}`;
}

/**
 * What each audio level does to the voice and to the clip audio. Spelled out per level
 * because the levels differ in whether a voice is needed at all, which is the difference
 * that decides whether the render is even unblocked.
 */
function clipAudioChoiceHint(choice: ClipAudioChoice, veoNativeVietnamese: boolean): string {
  if (choice === CLIP_AUDIO_CHOICE_CLIP_ONLY) {
    return veoNativeVietnamese
      ? 'Âm thanh gốc: MP4 chỉ dùng audio của clip ở mức nguyên bản, gồm cả câu thoại tiếng Việt do clip Veo phát. Không cần tạo giọng đọc trước khi dựng; phân đoạn nào clip không có audio thì sẽ im lặng.'
      : 'Âm thanh gốc: MP4 chỉ dùng tiếng gốc của clip ở mức nguyên bản và bỏ hẳn giọng đọc, kể cả khi project đã có giọng đọc. Không cần tạo giọng đọc trước khi dựng; phân đoạn nào clip không có audio thì sẽ im lặng.';
  }
  if (choice === CLIP_AUDIO_CHOICE_BED) {
    return veoNativeVietnamese
      ? 'Kết hợp: tiếng gốc chỉ được thêm cho phân đoạn không có thoại. Phân đoạn có thoại tiếng Việt vốn đã dùng chính audio của clip nên được giữ nguyên để không bị vọng tiếng.'
      : 'Kết hợp: giọng đọc là tiếng chính, tiếng gốc của clip xuống làm nền và tự động hạ mức khi có giọng đọc. Phân đoạn không có giọng đọc sẽ phát tiếng gốc thay vì im lặng.';
  }
  return veoNativeVietnamese
    ? 'Voice: MP4 chỉ dùng câu thoại tiếng Việt lấy từ clip Veo và bỏ phần tiếng gốc còn lại. Phân đoạn có thoại vẫn cần clip có audio mới dựng được.'
    : 'Voice: MP4 chỉ dùng giọng đọc và bỏ hẳn tiếng gốc của clip. Shot nào có narration vẫn cần giọng đọc hoàn tất mới dựng được.';
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

// Đo trên clip thật: cv2 nhanh hơn migan khoảng 27 lần mà chất lượng gần như trùng
// (PSNR 50,7 dB, SSIM 0,9965 giữa hai bản của cùng một clip), nên nhãn phải nói rõ
// migan chậm hơn nhiều thay vì gợi ý là bản đẹp hơn.
const WATERMARK_BACKEND_LABELS: Record<string, string> = {
  cv2: 'Nhanh — OpenCV (khuyên dùng, chất lượng tương đương)',
  migan: 'MI-GAN — chậm hơn nhiều, chỉ dùng khi OpenCV lấp chưa sạch',
};

/**
 * Region-fill backend readiness, keyed by backend id. Returns null while
 * readiness has no data yet so the UI can avoid disabling options too early.
 */
function watermarkBackendStatus(
  readiness: VideoRenderReadinessResponse | undefined,
  backend: string,
): VideoRenderWatermarkBackendStatus | null {
  return readiness?.watermark_backends?.find((item) => item.backend === backend) ?? null;
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

export function AIVideoRenderPanel({ projectId, shots, targetLanguage, apiPrefix = '/ai-video', speechSource, onNotice }: AIVideoRenderPanelProps) {
  const platform = usePlatform();
  const queryClient = useQueryClient();
  // Settings are restored per project, so the panel always shows what is actually in
  // effect rather than the defaults.
  const [settings, setSettings] = useState<VideoRenderSettings>(() => loadRenderSettings(projectId));
  const [settingsOwner, setSettingsOwner] = useState<string | null>(projectId ?? null);
  const [uploadingShotId, setUploadingShotId] = useState<string | null>(null);
  const [previewShotId, setPreviewShotId] = useState<string | null>(null);
  // Picking files only builds this plan; nothing is uploaded until the user confirms,
  // because importing a clip deactivates whatever the shot already held.
  const [batchPlan, setBatchPlan] = useState<ClipBatchPlan<File, VideoShotResponse> | null>(null);
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(null);
  const [batchResult, setBatchResult] = useState<VideoShotClipBatchResult | null>(null);
  const [sourceSelections, setSourceSelections] = useState<Record<string, { asset_id: string; region_id?: string; motion: 'hold' | 'zoom'; highlight: boolean }>>({});
  const usesVeoNativeVietnameseSpeech = speechSource
    ? speechSource === 'veo_narration' || speechSource === 'veo_dialogue'
    : targetLanguage === 'vi';

  // Switching project swaps in that project's saved settings during render, so the panel
  // never shows one project's choices while another is selected.
  if ((projectId ?? null) !== settingsOwner) {
    setSettingsOwner(projectId ?? null);
    setSettings(loadRenderSettings(projectId));
  }

  useEffect(() => {
    if (projectId && projectId === settingsOwner) saveRenderSettings(projectId, settings);
  }, [projectId, settingsOwner, settings]);

  const enabled = !!projectId && shots.length > 0;
  const renderQueryKey = useMemo(() => ['ai-video', 'render', projectId, settings], [projectId, settings]);

  const clipQueries = useQueries({
    queries: shots.map((shot) => ({
      queryKey: ['ai-video', 'shot-clip', projectId, shot.id],
      queryFn: () => apiClient.getVideoShotClip(projectId!, shot.id, apiPrefix),
      enabled,
      retry: false,
    })),
  });

  const readinessQuery = useQuery({
    queryKey: [...renderQueryKey, 'readiness'],
    queryFn: () => apiClient.getVideoRenderReadiness(projectId!, settings, apiPrefix),
    enabled,
  });

  const latestJobQuery = useQuery({
    queryKey: ['ai-video', 'render-job-latest', projectId],
    queryFn: () => apiClient.getLatestVideoRenderJob(projectId!, apiPrefix),
    enabled: !!projectId,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 2000 : false;
    },
  });

  const sfxAssetsQuery = useQuery({
    queryKey: ['ai-video', 'render-sfx-assets', projectId],
    queryFn: () => apiClient.listVideoRenderSfxAssets(projectId!, apiPrefix),
    enabled: !!projectId,
    retry: false,
  });

  const sourceVisualsQuery = useQuery({
    queryKey: ['ai-video', 'source-visuals', projectId],
    queryFn: () => apiClient.listVideoSourceVisuals(projectId!, apiPrefix),
    enabled: !!projectId,
    retry: false,
  });

  const invalidateRender = () => {
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'shot-clip'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-sfx-assets', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'source-visuals', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-job-latest', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'debug', projectId] });
  };

  const uploadClip = useMutation({
    mutationFn: ({ shot, file }: { shot: VideoShotResponse; file: File }) => apiClient.uploadVideoShotClip(shot.project_id, shot.id, file, undefined, apiPrefix),
    onMutate: ({ shot }) => setUploadingShotId(shot.id),
    onSuccess: (_, { shot }) => {
      onNotice(`Đã tải clip video cho ${shotLabel(shot)}.`);
      invalidateRender();
    },
    onSettled: () => setUploadingShotId(null),
  });

  const importBatch = useMutation({
    mutationFn: (matched: ClipBatchMatched<File, VideoShotResponse>[]) => {
      setBatchProgress({ done: 0, total: matched.length });
      return apiClient.uploadVideoShotClipBatch(
        projectId!,
        matched.map((entry) => ({ shotId: entry.shot.id, shotOrder: entry.shotOrder, file: entry.file })),
        {
          provider: BATCH_CLIP_PROVIDER,
          routePrefix: apiPrefix,
          onProgress: (done, total) => setBatchProgress({ done, total }),
        },
      );
    },
    onSuccess: (result) => {
      // Successful files stay imported even when others failed, so the summary is the
      // report and there is nothing to roll back.
      setBatchResult(result);
      setBatchPlan(null);
      onNotice(
        result.failed.length
          ? `Đã nạp ${result.succeeded.length}/${result.total} clip, ${result.failed.length} file lỗi.`
          : `Đã nạp ${result.succeeded.length}/${result.total} clip theo lô.`,
      );
      invalidateRender();
    },
    onSettled: () => setBatchProgress(null),
  });

  const deleteClip = useMutation({
    mutationFn: (shot: VideoShotResponse) => apiClient.deleteVideoShotClip(shot.project_id, shot.id, apiPrefix),
    onSuccess: (_, shot) => {
      onNotice(`Đã xóa clip video của ${shotLabel(shot)}.`);
      invalidateRender();
    },
  });

  const createScreenshotClip = useMutation({
    mutationFn: ({ shot, selection }: { shot: VideoShotResponse; selection: { asset_id: string; region_id?: string; motion: 'hold' | 'zoom'; highlight: boolean } }) => apiClient.createVideoScreenshotClip(projectId!, shot.id, selection, apiPrefix),
    onSuccess: (_, { shot }) => {
      onNotice(`Đã dựng clip từ screenshot gốc cho ${shotLabel(shot)}; chữ/code trong ảnh được giữ nguyên.`);
      invalidateRender();
    },
  });

  const uploadSfxAsset = useMutation({
    mutationFn: (file: File) => apiClient.uploadVideoRenderSfxAsset(projectId!, file, apiPrefix),
    onSuccess: (asset) => {
      onNotice(`Đã tải hiệu ứng/nhạc nền: ${asset.filename}.`);
      invalidateRender();
    },
  });

  const deleteSfxAsset = useMutation({
    mutationFn: (asset: VideoRenderSfxAssetResponse) => apiClient.deleteVideoRenderSfxAsset(projectId!, asset.asset_id, apiPrefix),
    onSuccess: () => {
      onNotice('Đã xóa hiệu ứng/nhạc nền.');
      invalidateRender();
    },
  });

  const createRender = useMutation({
    mutationFn: () => apiClient.createVideoRenderJob(projectId!, settings, apiPrefix),
    onSuccess: () => {
      onNotice('Đã bắt đầu dựng MP4. Bạn có thể theo dõi tiến độ trong bảng này.');
      invalidateRender();
    },
  });

  const saveDownload = async (download: Promise<DownloadedBlob>) => {
    const result = await download;
    await platform.filesystem.saveFile(result.filename, result.blob, [{ name: 'Tệp dựng', extensions: ['mp4', 'md', 'json', 'csv'] }]);
  };

  const shotIdsWithClip = useMemo(() => {
    const ids = new Set<string>();
    shots.forEach((shot, index) => {
      if (clipQueries[index]?.data) ids.add(shot.id);
    });
    return ids;
  }, [shots, clipQueries]);

  const handleBatchFiles = (files: File[]) => {
    setBatchResult(null);
    setBatchPlan(files.length ? buildClipBatchPlan(files, shots, { shotIdsWithClip }) : null);
  };

  const latestJob = latestJobQuery.data;
  const readiness = readinessQuery.data;
  const sfxAssets = sfxAssetsQuery.data ?? [];
  const busy = latestJob?.status === 'queued' || latestJob?.status === 'running';
  const reviewArtifact = latestJob?.enhanced_artifacts_json?.items?.find((item) => item.kind === 'ai_review_report');
  const manifestArtifact = latestJob?.enhanced_artifacts_json?.items?.find((item) => item.kind === 'timeline_manifest');
  const sourceVisuals = sourceVisualsQuery.data ?? [];
  const operationError = uploadClip.error || importBatch.error || deleteClip.error || createScreenshotClip.error || uploadSfxAsset.error || deleteSfxAsset.error || createRender.error;

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
        {shots.length ? (
          <ClipBatchImport
            plan={batchPlan}
            progress={batchProgress}
            result={batchResult}
            importing={importBatch.isPending}
            onPick={handleBatchFiles}
            onCancel={() => setBatchPlan(null)}
            onConfirm={() => batchPlan && importBatch.mutate(batchPlan.matched)}
            onDismissResult={() => setBatchResult(null)}
          />
        ) : null}

        {sourceVisuals.length ? <SourceVisualSummary assets={sourceVisuals} projectId={projectId} apiPrefix={apiPrefix} /> : null}

        {shots.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
            Chưa có phân đoạn. Hãy tạo bản phân đoạn trước khi tải clip lên và dựng MP4.
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
                clipMissing ? 'Cần clip video' : null,
                needsVoice
                  ? usesVeoNativeVietnameseSpeech
                    ? 'Clip Veo cần audio lời thoại'
                    : 'Cần giọng đọc'
                  : null,
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
                      {clip?.status === 'ready' ? 'clip video sẵn sàng' : clipInvalid ? 'clip video lỗi' : 'thiếu clip video'}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <div className="rounded-lg border border-border/60 bg-card/40 px-2.5 py-2">
                      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Thời lượng</p>
                      <p className="mt-1 truncate text-xs font-semibold text-foreground">
                        {formatDuration(
                          shot.english_narration?.trim() && usesVeoNativeVietnameseSpeech
                            ? clip?.duration_seconds
                            : shot.english_narration?.trim()
                              ? shot.audio_duration
                              : shot.duration_seconds,
                        )}
                      </p>
                    </div>
                    <div className="rounded-lg border border-border/60 bg-card/40 px-2.5 py-2">
                      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Clip video</p>
                      <p className="mt-1 truncate text-xs font-semibold text-foreground">{formatDuration(clip?.duration_seconds)}</p>
                    </div>
                  </div>

                  {clip?.original_filename ? (
                    <p className="mt-2 truncate text-xs leading-relaxed text-foreground/75">Tệp: {clip.original_filename}</p>
                  ) : null}
                  {usesVeoNativeVietnameseSpeech && shot.english_narration?.trim() && clip?.status === 'ready' ? (
                    <p
                      className={cn(
                        'mt-2 text-xs font-medium',
                        clip.has_audio
                          ? 'text-emerald-700 dark:text-emerald-300'
                          : 'text-destructive',
                      )}
                    >
                      {clip.has_audio
                        ? 'Clip có audio tiếng Việt để dùng khi dựng.'
                        : 'Clip không có audio; cần tạo/tải lại clip Veo có lời thoại.'}
                    </p>
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
                  {clip?.status === 'ready' && previewShotId === shot.id ? (
                    <div className="mt-3 overflow-hidden rounded-lg border border-border/70 bg-black">
                      {/* biome-ignore lint/a11y/useMediaCaption: raw clip preview is available before a project subtitle track exists */}
                      <video
                        key={clip.id}
                        className="aspect-video w-full bg-black object-contain"
                        controls
                        preload="metadata"
                        src={apiClient.getVideoShotClipDownloadUrl(projectId, shot.id, apiPrefix)}
                      />
                    </div>
                  ) : null}

                  <div className="mt-3 grid gap-2">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="min-h-10 w-full active:translate-y-[1px]"
                        disabled={!clip || clip.status !== 'ready'}
                        onClick={() => setPreviewShotId((current) => (current === shot.id ? null : shot.id))}
                      >
                        <Eye className="h-4 w-4" />
                        {previewShotId === shot.id ? 'Ẩn xem trước' : 'Xem clip video'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="min-h-10 w-full active:translate-y-[1px]"
                        disabled={!clip || clip.status !== 'ready'}
                        onClick={() => saveDownload(apiClient.downloadVideoShotClip(projectId, shot.id, clip?.original_filename || 'clip.mp4', apiPrefix))}
                      >
                        <Download className="h-4 w-4" />
                        Tải clip video
                      </Button>
                    </div>
                    <label
                      aria-disabled={isUploading}
                      className={cn(
                        'flex min-h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-input bg-card/70 px-3 py-2 text-sm font-medium text-foreground transition duration-200 hover:border-accent hover:bg-accent hover:text-accent-foreground active:translate-y-[1px]',
                        isUploading && 'pointer-events-none opacity-60',
                      )}
                    >
                      {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                      <span className="truncate">{isUploading ? 'Đang tải lên' : clip ? 'Thay clip video' : 'Chọn clip video'}</span>
                      <input
                        type="file"
                        accept={CLIP_FILE_ACCEPT}
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
                      Xóa clip video
                    </Button>
                    {sourceVisuals.length ? <SourceVisualButton
                      shot={shot}
                      assets={sourceVisuals}
                      selection={sourceSelections[shot.id]}
                      onSelectionChange={(selection) => setSourceSelections((current) => ({ ...current, [shot.id]: selection }))}
                      busy={createScreenshotClip.isPending}
                      onCreate={(selection) => createScreenshotClip.mutate({ shot, selection })}
                    /> : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="grid gap-3 border-t border-border/70 pt-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Settings2 className="h-4 w-4" />
            Thiết lập dựng
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <SettingSelect label="Độ phân giải" value={settings.resolution} onChange={(value) => setSettings((current) => ({ ...current, resolution: value as VideoRenderSettings['resolution'] }))}>
              <option value="auto">Theo tỷ lệ dự án</option>
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
            </SettingSelect>
            <SettingSelect label="Số khung/giây (FPS)" value={String(settings.fps)} onChange={(value) => setSettings((current) => ({ ...current, fps: Number(value) }))}>
              <option value="24">24</option>
              <option value="30">30</option>
              <option value="60">60</option>
            </SettingSelect>
            <SettingSelect label="Khung hình" value={settings.fit_mode} onChange={(value) => setSettings((current) => ({ ...current, fit_mode: value as VideoRenderSettings['fit_mode'] }))}>
              <option value="crop">Cắt vừa khung</option>
              <option value="pad">Giữ toàn ảnh</option>
            </SettingSelect>
            <SettingSelect label="Phụ đề" value={settings.subtitle_mode} onChange={(value) => setSettings((current) => ({ ...current, subtitle_mode: value as VideoRenderSettings['subtitle_mode'] }))}>
              <option value="burn_in">Nhúng phụ đề vào video</option>
              <option value="sidecar">SRT rời</option>
              <option value="none">Không phụ đề</option>
            </SettingSelect>
          </div>
          <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,9.5rem),1fr))]">
            {/*
              One dropdown decides both the voice and the clip audio, so it is labelled
              "Âm thanh" rather than after the clip. Each option states the result the user
              gets instead of the API field it maps to.
            */}
            <SettingSelect
              label="Âm thanh"
              value={clipAudioChoiceFromSettings(settings)}
              onChange={(value) => setSettings((current) => settingsForClipAudioChoice(current, value))}
            >
              <option value={CLIP_AUDIO_CHOICE_BED}>Kết hợp</option>
              <option value={CLIP_AUDIO_CHOICE_DROP}>Voice</option>
              <option value={CLIP_AUDIO_CHOICE_CLIP_ONLY}>Âm thanh gốc</option>
            </SettingSelect>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {clipAudioChoiceHint(clipAudioChoiceFromSettings(settings), usesVeoNativeVietnameseSpeech)}
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {usesVeoNativeVietnameseSpeech
              ? 'Nhúng phụ đề dùng câu thoại tiếng Việt đã duyệt và thời lượng clip Veo. Nếu thay clip, hãy tạo lại phụ đề trước khi dựng.'
              : 'Nhúng phụ đề dùng file .srt đã chia mốc theo giọng đọc và dựng chữ karaoke màu vàng theo từng từ. Nếu thời gian lệch, tạo lại phụ đề sau khi giọng đọc đã hoàn tất.'}
          </p>
        </div>

        <div className="min-w-0 rounded-lg border border-border/75 bg-background/70 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4" />
            Làm sạch dấu AI trước khi dựng
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 sm:items-end">
            <ToggleRow
              label="Làm sạch dấu AI trên clip trước khi dựng"
              checked={Boolean(settings.watermark_cleanup)}
              onChange={(checked) => setSettings((current) => ({ ...current, watermark_cleanup: checked }))}
            />
            {settings.watermark_cleanup ? (
              <SettingSelect
                label="Cách lấp vùng dấu"
                value={settings.watermark_backend ?? 'cv2'}
                onChange={(value) => setSettings((current) => ({ ...current, watermark_backend: value as VideoRenderSettings['watermark_backend'] }))}
              >
                {(['cv2', 'migan'] as const).map((backend) => {
                  const status = watermarkBackendStatus(readiness, backend);
                  // No readiness data yet means nothing gets disabled.
                  const unavailable = status ? !status.ready : false;
                  return (
                    <option key={backend} value={backend} disabled={unavailable}>
                      {WATERMARK_BACKEND_LABELS[backend]}
                      {unavailable ? ' (chưa sẵn sàng)' : ''}
                    </option>
                  );
                })}
              </SettingSelect>
            ) : null}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Chỉ dùng cho nội dung bạn có quyền chỉnh sửa. Hệ thống xử lý các dấu AI nhìn thấy được hỗ trợ và metadata đã xác minh; clip gốc luôn được giữ lại.
          </p>
          {settings.watermark_cleanup ? (
            <div className="mt-3 grid gap-2">
              <div
                className={cn(
                  'rounded-lg border px-3 py-2 text-xs leading-relaxed',
                  statusTone(Boolean(readiness?.watermark_cleanup_ready)),
                )}
              >
                {readinessQuery.isFetching && !readiness
                  ? 'Đang kiểm tra watermark worker.'
                  : readiness?.watermark_cleanup_ready
                    ? `Watermark worker sẵn sàng${readiness.watermark_cleanup_revision ? ` · revision ${readiness.watermark_cleanup_revision.slice(0, 12)}` : ''}.`
                    : readiness?.watermark_cleanup_failure_reason || 'Watermark worker chưa sẵn sàng.'}
              </div>
              {(readiness?.watermark_backends ?? [])
                .filter((status) => !status.ready)
                .map((status) => (
                  <div
                    key={status.backend}
                    className={cn('rounded-lg border px-3 py-2 text-xs leading-relaxed', statusTone(false))}
                  >
                    <span className="font-semibold">{WATERMARK_BACKEND_LABELS[status.backend] ?? status.backend} chưa sẵn sàng.</span>{' '}
                    {status.failure_reason || 'Chưa rõ nguyên nhân.'}
                  </div>
                ))}
              {watermarkBackendStatus(readiness, settings.watermark_backend ?? 'cv2')?.model_cache === 'not_cached' ? (
                <div className={cn('rounded-lg border px-3 py-2 text-xs leading-relaxed', statusTone(false))}>
                  Model chưa có trong cache: lần dựng đầu cần mạng để tải khoảng 28 MB nên sẽ lâu hơn.
                </div>
              ) : null}
              <p className="text-xs leading-relaxed text-muted-foreground">
                Cách lấp vùng chỉ ảnh hưởng chất lượng vùng được lấp, không ảnh hưởng khả năng phát hiện dấu AI.
              </p>
            </div>
          ) : null}
        </div>

        <div className="min-w-0 rounded-lg border border-border/75 bg-background/70 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4" />
            Hiệu ứng giữ chân
          </div>
          <div className="mt-3 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,9.5rem),1fr))]">
            <ToggleRow
              label="Chuyển cảnh/hiệu ứng âm thanh"
              checked={Boolean(settings.enhanced_render)}
              onChange={(checked) => setSettings((current) => ({ ...current, enhanced_render: checked }))}
            />
            <ToggleRow
              label="Trộn hiệu ứng/nhạc nền thật"
              checked={Boolean(settings.enhanced_audio)}
              disabled={!settings.enhanced_render}
              onChange={(checked) => setSettings((current) => ({ ...current, enhanced_audio: checked }))}
            />
            <ToggleRow
              label="Đánh giá AI"
              checked={Boolean(settings.ai_review)}
              disabled={!settings.enhanced_render}
              onChange={(checked) => setSettings((current) => ({ ...current, ai_review: checked }))}
            />
          </div>
          <div className="mt-3 grid min-w-0 gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr))] sm:items-end">
            <SettingSelect
              label="Số vòng tự sửa"
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
              <span className="min-w-0 whitespace-normal">{uploadSfxAsset.isPending ? 'Đang tải lên' : 'Thêm hiệu ứng/nhạc nền'}</span>
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
                      {(asset.cue_aliases || []).join(', ') || 'chưa có tên gợi nhớ'} · {asset.status}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 shrink-0 p-0"
                    disabled={deleteSfxAsset.isPending}
                    onClick={() => deleteSfxAsset.mutate(asset)}
                    title="Xóa tài nguyên"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-muted-foreground">
              Chưa có hiệu ứng/nhạc nền. Gợi ý như tiếng kính vỡ sẽ được ghi dự phòng nếu chưa tải tài nguyên thật.
            </p>
          )}
        </div>

        <div className={cn('rounded-lg border p-3 text-sm', statusTone(!!readiness?.ready))}>
          <div className="flex items-start gap-2">
            {readiness?.ready ? <Check className="mt-0.5 h-4 w-4" /> : <AlertCircle className="mt-0.5 h-4 w-4" />}
            <div className="min-w-0">
              <p className="font-medium">{readiness?.ready ? 'Đã đủ điều kiện dựng MP4.' : 'Chưa đủ điều kiện dựng MP4.'}</p>
              {!readiness ? <p className="mt-1 text-xs opacity-80">Đang kiểm tra điều kiện dựng.</p> : null}
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
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderJob(projectId, latestJob.id, apiPrefix))}
          >
            <Download className="h-4 w-4" />
            <span className="min-w-0">Tải MP4</span>
          </Button>
          <Button
            className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]"
            variant="outline"
            disabled={!latestJob || latestJob.status !== 'completed' || !reviewArtifact}
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderEnhancedArtifact(projectId, latestJob.id, reviewArtifact?.kind || 'ai_review_report', apiPrefix))}
          >
            <FileText className="h-4 w-4" />
            <span className="min-w-0">Tải đánh giá AI</span>
          </Button>
          <Button
            className="min-h-11 min-w-0 whitespace-normal px-3 text-center leading-tight active:translate-y-[1px]"
            variant="outline"
            disabled={!latestJob || latestJob.status !== 'completed' || !manifestArtifact}
            onClick={() => latestJob && saveDownload(apiClient.downloadVideoRenderEnhancedArtifact(projectId, latestJob.id, manifestArtifact?.kind || 'timeline_manifest', apiPrefix))}
          >
            <Download className="h-4 w-4" />
            <span className="min-w-0">Tải bảng dòng thời gian</span>
          </Button>
        </div>
      </div>
    </section>
  );
}

interface ClipBatchImportProps {
  plan: ClipBatchPlan<File, VideoShotResponse> | null;
  progress: { done: number; total: number } | null;
  result: VideoShotClipBatchResult | null;
  importing: boolean;
  onPick: (files: File[]) => void;
  onCancel: () => void;
  onConfirm: () => void;
  onDismissResult: () => void;
}

/**
 * Batch clip import: pick many files at once, review the match table, then confirm.
 *
 * The picker deliberately does not import on selection. An import deactivates the clip a
 * shot already holds, so one wrong folder would silently replace every clip that was
 * already correct; the confirm step turns that into a harmless mistake.
 */
function SourceVisualSummary({ assets, projectId, apiPrefix }: { assets: VideoSourceVisualAsset[]; projectId: string; apiPrefix: string }) {
  return <div className="rounded-lg border border-primary/25 bg-primary/5 p-3">
    <div className="flex items-center gap-2 text-sm font-semibold"><Layers className="h-4 w-4" /> Screenshot/code gốc đã chuyển sang AI Video</div>
    <p className="mt-1 text-xs leading-5 text-muted-foreground">Chọn ảnh và vùng bên dưới để dựng crop/zoom/highlight bằng FFmpeg. Ảnh, chữ và code gốc không bị AI vẽ lại.</p>
    <div className="mt-2 flex gap-2 overflow-x-auto pb-1">{assets.map((asset) => <img key={asset.id} src={apiClient.getVideoSourceVisualUrl(projectId, asset.id, apiPrefix)} alt={`Screenshot ${asset.id}`} className="h-16 w-28 rounded border border-border object-cover" loading="lazy" />)}</div>
  </div>;
}

function SourceVisualButton({ shot, assets, selection, onSelectionChange, busy, onCreate }: { shot: VideoShotResponse; assets: VideoSourceVisualAsset[]; selection?: { asset_id: string; region_id?: string; motion: 'hold' | 'zoom'; highlight: boolean }; onSelectionChange: (selection: { asset_id: string; region_id?: string; motion: 'hold' | 'zoom'; highlight: boolean }) => void; busy: boolean; onCreate: (selection: { asset_id: string; region_id?: string; motion: 'hold' | 'zoom'; highlight: boolean }) => void }) {
  const current = selection ?? { asset_id: assets[0].id, region_id: assets[0].regions[0]?.id, motion: 'hold' as const, highlight: Boolean(assets[0].regions[0]) };
  const asset = assets.find((item) => item.id === current.asset_id) ?? assets[0];
  return <div className="rounded-lg border border-primary/20 bg-primary/5 p-2.5">
    <p className="text-xs font-medium">Dựng từ screenshot gốc</p>
    <div className="mt-2 grid gap-2 sm:grid-cols-2">
      <select aria-label={`${shotLabel(shot)} screenshot`} className="min-h-9 rounded-md border border-input bg-background px-2 text-xs" value={current.asset_id} onChange={(event) => { const next = assets.find((item) => item.id === event.target.value) ?? assets[0]; onSelectionChange({ ...current, asset_id: next.id, region_id: next.regions[0]?.id, highlight: Boolean(next.regions[0]) }); }}>
        {assets.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}
      </select>
      <select aria-label={`${shotLabel(shot)} vùng screenshot`} className="min-h-9 rounded-md border border-input bg-background px-2 text-xs" value={current.region_id ?? ''} onChange={(event) => onSelectionChange({ ...current, region_id: event.target.value || undefined, highlight: Boolean(event.target.value) })}>
        <option value="">Toàn ảnh</option>
        {asset.regions.map((region) => <option key={region.id} value={region.id}>{region.label || region.id}</option>)}
      </select>
      <select aria-label={`${shotLabel(shot)} chuyển động screenshot`} className="min-h-9 rounded-md border border-input bg-background px-2 text-xs" value={current.motion} onChange={(event) => onSelectionChange({ ...current, motion: event.target.value as 'hold' | 'zoom' })}><option value="hold">Giữ khung</option><option value="zoom">Zoom nhẹ</option></select>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onCreate(current)}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Film className="h-4 w-4" />} Dựng clip gốc</Button>
    </div>
  </div>;
}

function ClipBatchImport({
  plan,
  progress,
  result,
  importing,
  onPick,
  onCancel,
  onConfirm,
  onDismissResult,
}: ClipBatchImportProps) {
  const matched = plan?.matched ?? [];
  const skipped = plan?.skipped ?? [];

  return (
    <div className="min-w-0 rounded-lg border border-border/75 bg-background/70 p-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Layers className="h-4 w-4" />
        Nạp nhiều clip theo số phân đoạn
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        Đặt tên mỗi file theo số phân đoạn (<span className="font-mono">1.mp4</span>,{' '}
        <span className="font-mono">2.mp4</span>, …) rồi chọn tất cả trong một lần. Bảng khớp hiện ra
        để bạn kiểm tra trước, chưa có gì được nạp cho tới khi bạn bấm xác nhận.
      </p>

      <label
        aria-disabled={importing}
        className={cn(
          'mt-3 flex min-h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-input bg-card/70 px-3 py-2 text-sm font-medium text-foreground transition duration-200 hover:border-accent hover:bg-accent hover:text-accent-foreground active:translate-y-[1px]',
          importing && 'pointer-events-none opacity-60',
        )}
      >
        <UploadCloud className="h-4 w-4" />
        <span className="truncate">Chọn nhiều clip video</span>
        <input
          type="file"
          multiple
          accept={CLIP_FILE_ACCEPT}
          className="sr-only"
          disabled={importing}
          onChange={(event) => {
            onPick(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = '';
          }}
        />
      </label>
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">MP4, MOV, WEBM hoặc MKV.</p>

      {plan ? (
        <div className="mt-3 grid gap-2 rounded-lg border border-border/60 bg-card/40 p-2.5">
          {matched.map((entry) => (
            <div key={`${entry.filename}-${entry.shotOrder}`} className="flex min-w-0 items-start justify-between gap-2 text-xs">
              <span className="min-w-0 flex-1 truncate font-mono text-foreground/80">{entry.filename}</span>
              <span className="shrink-0 text-muted-foreground">→</span>
              <span className="min-w-0 flex-1 text-right font-medium text-foreground">
                {shotLabel(entry.shot)}
                {entry.replacesExistingClip ? (
                  <span className="ml-1 font-normal text-amber-700 dark:text-amber-300">(thay clip đang có)</span>
                ) : null}
              </span>
            </div>
          ))}
          {skipped.map((entry) => (
            <div key={`skip-${entry.filename}`} className="flex min-w-0 items-start justify-between gap-2 text-xs">
              <span className="min-w-0 flex-1 truncate font-mono text-muted-foreground line-through">{entry.filename}</span>
              <span className="shrink-0 text-muted-foreground">→</span>
              <span className="min-w-0 flex-1 text-right font-medium text-amber-800 dark:text-amber-200">
                Bỏ qua: {clipBatchSkipReasonLabel(entry.reason)}
              </span>
            </div>
          ))}
          <div className="mt-1 border-t border-border/60 pt-2 text-xs font-medium">
            {matched.length
              ? `${matched.length} file sẽ được nạp · ${skipped.length} bỏ qua`
              : 'Không có file nào khớp phân đoạn. Hãy đổi tên file theo số phân đoạn rồi chọn lại.'}
          </div>
          {progress ? (
            <p className="text-xs text-muted-foreground">
              Đang nạp {progress.done}/{progress.total} file.
            </p>
          ) : null}
          <div className="mt-1 grid gap-2 sm:grid-cols-2">
            <Button size="sm" variant="outline" className="min-h-10 w-full" disabled={importing} onClick={onCancel}>
              Huỷ
            </Button>
            <Button size="sm" className="min-h-10 w-full" disabled={importing || matched.length === 0} onClick={onConfirm}>
              {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              <span className="min-w-0 truncate">Nạp {matched.length} clip</span>
            </Button>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="mt-3 grid gap-2 rounded-lg border border-border/60 bg-card/40 p-2.5 text-xs">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 font-medium">
              Đã nạp {result.succeeded.length}/{result.total} file
              {result.failed.length ? ` · ${result.failed.length} file lỗi` : ''}.
            </p>
            <Button size="sm" variant="ghost" className="h-6 shrink-0 px-2 text-xs" onClick={onDismissResult}>
              Đóng
            </Button>
          </div>
          {/* Failures are listed per file: the loaded clips stay loaded, nothing is undone. */}
          {result.failed.map((failure) => (
            <p key={`${failure.shotOrder}-${failure.file.name}`} className="leading-relaxed text-destructive">
              <span className="font-mono">{failure.file.name}</span> (phân đoạn{' '}
              {String(failure.shotOrder).padStart(2, '0')}): {failure.message}
            </p>
          ))}
        </div>
      ) : null}
    </div>
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
          <p className="truncate text-xs text-muted-foreground">Ghép clip, giọng đọc và phụ đề theo thời lượng thật</p>
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
