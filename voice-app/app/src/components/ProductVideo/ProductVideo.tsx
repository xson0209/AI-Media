import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clapperboard, Loader2, Plus, Sparkles, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIVideoRenderPanel } from '@/components/AIVideoAssistant/AIVideoRenderPanel';
import { apiClient } from '@/lib/api/client';
import type { ProductVideoProjectResponse, VideoLanguage } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import {
  type ProductVideoFormState,
  ProductVideoConfigForm,
  deriveClipPlan,
  initialProductVideoForm,
} from './ProductVideoConfigForm';
import { ProductVideoPromptPanel } from './ProductVideoPromptPanel';

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return 'Có lỗi không xác định.';
}

function formFromProject(project: ProductVideoProjectResponse): ProductVideoFormState {
  return {
    topic: project.topic,
    targetLanguage: project.target_language,
    aspectRatio: project.aspect_ratio,
    visualStyle: project.visual_style ?? '',
    visualStylePreset: project.visual_style_preset ?? 'custom',
    videoPurpose: project.video_purpose,
    dialogueMode: project.dialogue_mode ?? 'voiceover',
    narrationDensity: project.narration_density ?? 'light',
    callToActionStyle: project.call_to_action_style ?? 'direct',
    creationMode: project.creation_mode ?? 'quick',
    automationMode: project.automation_mode ?? 'full_auto',
    outputTarget: project.output_target ?? 'render_ready',
    targetDurationSeconds: project.target_duration_seconds ?? 30,
    promptSegmentCount:
      project.prompt_segment_count ??
      Math.max(1, Math.ceil((project.target_duration_seconds ?? 30) / (project.prompt_segment_duration_seconds ?? 8))),
    promptSegmentDurationSeconds: project.prompt_segment_duration_seconds ?? 8,
    microScenesPerPrompt: project.micro_scenes_per_prompt ?? 3,
  };
}

function requestFromForm(form: ProductVideoFormState) {
  return {
    topic: form.topic,
    target_language: form.targetLanguage,
    aspect_ratio: form.aspectRatio,
    visual_style: form.visualStyle,
    visual_style_preset: form.visualStylePreset,
    video_purpose: form.videoPurpose,
    dialogue_mode: form.dialogueMode,
    narration_density: form.narrationDensity,
    call_to_action_style: form.callToActionStyle,
    creation_mode: form.creationMode,
    automation_mode: form.automationMode,
    output_target: form.outputTarget,
    target_duration_seconds: form.targetDurationSeconds,
    prompt_segment_count: form.promptSegmentCount,
    prompt_segment_duration_seconds: form.promptSegmentDurationSeconds,
    micro_scenes_per_prompt: form.microScenesPerPrompt,
  };
}

export function ProductVideo() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<ProductVideoFormState>(initialProductVideoForm);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [renderNotice, setRenderNotice] = useState<string | null>(null);

  const projectsQuery = useQuery({
    queryKey: ['product-video', 'projects'],
    queryFn: () => apiClient.listProductVideoProjects(),
  });

  const detailQuery = useQuery({
    queryKey: ['product-video', 'project', selectedId],
    queryFn: () => apiClient.getProductVideoProject(selectedId as string),
    enabled: !!selectedId,
  });

  // Load the selected project's saved config so the style textarea and its
  // preset come back exactly as the user left them.
  useEffect(() => {
    if (detailQuery.data) setForm(formFromProject(detailQuery.data));
  }, [detailQuery.data]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const project = await apiClient.createProductVideoProject(requestFromForm(form));
      if (form.creationMode === 'manual') return { project, stageError: null };
      try {
        await apiClient.planProductVideoShots(project.id);
        if (form.automationMode === 'full_auto' && form.outputTarget !== 'shots_only') {
          await apiClient.generateProductVideoPrompts(project.id);
        }
        return { project, stageError: null };
      } catch (error) {
        return { project, stageError: errorMessage(error) };
      }
    },
    onSuccess: ({ project, stageError }) => {
      setSelectedId(project.id);
      setRenderNotice(
        stageError
          ? `Đã tạo dự án nhưng bước tự chạy chưa hoàn tất: ${stageError}`
          : form.creationMode === 'manual'
            ? 'Đã tạo dự án thủ công. Bạn có thể lập kế hoạch và sinh prompt từng bước.'
            : form.automationMode === 'review_gated'
              ? 'Đã lập kế hoạch và dừng để bạn duyệt trước khi sinh prompt.'
              : form.outputTarget === 'shots_only'
                ? 'Đã lập kế hoạch cảnh. Luồng dừng trước bước sinh prompt.'
                : form.outputTarget === 'prompt_pack'
                  ? 'Đã sinh prompt pack thoại. Chưa chạy provider, TTS hoặc render.'
                  : 'Đã sinh prompt và chuẩn bị bridge dựng MP4. Hãy upload clip rồi bấm Dựng MP4.',
      );
      queryClient.invalidateQueries({ queryKey: ['product-video', 'projects'] });
      queryClient.invalidateQueries({ queryKey: ['product-video', 'project', project.id] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => apiClient.updateProductVideoProject(selectedId as string, requestFromForm(form)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-video', 'projects'] });
      queryClient.invalidateQueries({ queryKey: ['product-video', 'project', selectedId] });
    },
  });

  const planMutation = useMutation({
    mutationFn: async () => {
      // Planning must use what is visible in the form. Persist it first so a
      // project reopened later keeps the edited style/preset exactly as shown.
      await apiClient.updateProductVideoProject(selectedId as string, requestFromForm(form));
      return apiClient.planProductVideoShots(selectedId as string);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-video', 'project', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['product-video', 'projects'] });
    },
  });

  const promptMutation = useMutation({
    mutationFn: () => apiClient.generateProductVideoPrompts(selectedId as string),
    onMutate: () => setPromptError(null),
    onError: (error) => setPromptError(errorMessage(error)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-video', 'project', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['product-video', 'projects'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (projectId: string) => apiClient.deleteProductVideoProject(projectId),
    onSuccess: () => {
      setSelectedId(null);
      setForm(initialProductVideoForm);
      queryClient.invalidateQueries({ queryKey: ['product-video', 'projects'] });
    },
  });

  const downloadMutation = useMutation({
    mutationFn: async () => {
      const { blob, filename } = await apiClient.downloadProductVideoPromptPack(
        selectedId as string,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  const projects = projectsQuery.data ?? [];
  const shots = detailQuery.data?.shots ?? [];
  const prompts = detailQuery.data?.prompts ?? [];
  const plan = deriveClipPlan(form);
  const busy =
    createMutation.isPending || updateMutation.isPending || planMutation.isPending || promptMutation.isPending;

  return (
    <div className="grid min-h-0 flex-1 gap-4 py-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col gap-3">
        <div className="flex items-center gap-2">
          <Clapperboard className="h-4 w-4" />
          <h1 className="text-sm font-semibold">Video sản phẩm</h1>
        </div>
        <Button
          variant={selectedId ? 'outline' : 'default'}
          size="sm"
          onClick={() => {
            setSelectedId(null);
            setForm(initialProductVideoForm);
            setRenderNotice(null);
          }}
        >
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Dự án mới
        </Button>

        <div className="min-h-0 flex-1 overflow-auto">
          {projectsQuery.isLoading ? (
            <p className="flex items-center gap-2 p-2 text-xs text-muted-foreground" aria-live="polite">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Đang tải danh sách...
            </p>
          ) : projectsQuery.error ? (
            <div className="grid gap-2 p-2">
              <p className="text-xs text-destructive">{errorMessage(projectsQuery.error)}</p>
              <Button variant="outline" size="sm" onClick={() => projectsQuery.refetch()}>
                Thử lại
              </Button>
            </div>
          ) : projects.length === 0 ? (
            <p className="p-2 text-xs text-muted-foreground">
              Chưa có dự án nào. Điền cấu hình bên phải và bấm Tạo dự án.
            </p>
          ) : (
            <ul className="grid gap-1.5">
              {projects.map((project) => (
                <li key={project.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(project.id);
                      setRenderNotice(null);
                    }}
                    className={cn(
                      'w-full rounded-lg border p-2 text-left text-xs transition',
                      selectedId === project.id
                        ? 'border-foreground/40 bg-muted'
                        : 'border-border/60 hover:bg-muted/50',
                    )}
                  >
                    <span className="line-clamp-2 font-medium">{project.title || project.topic}</span>
                    <span className="mt-1 flex items-center gap-1.5 text-muted-foreground">
                      <Badge variant="outline" className="text-[10px]">
                        {project.aspect_ratio}
                      </Badge>
                      <span>{project.derived_clip_count} clip</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <section className="grid min-h-0 gap-4 overflow-auto">
        <div className="grid gap-4 rounded-lg border border-border/60 p-4">
          <ProductVideoConfigForm form={form} onChange={setForm} disabled={busy} />

          <div className="flex flex-wrap items-center gap-2">
            {selectedId ? (
              <>
                <Button size="sm" onClick={() => planMutation.mutate()} disabled={busy}>
                  {planMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Lập kế hoạch {plan.clipCount} cảnh
                </Button>
                <Button size="sm" variant="outline" onClick={() => updateMutation.mutate()} disabled={busy}>
                  {updateMutation.isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
                  Lưu cấu hình
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => promptMutation.mutate()}
                  disabled={busy || shots.length === 0}
                >
                  {promptMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  Sinh prompt
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => deleteMutation.mutate(selectedId)}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                  Xóa
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                onClick={() => createMutation.mutate()}
                disabled={busy || form.topic.trim().length === 0}
              >
                {createMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                )}
                Tạo dự án
              </Button>
            )}
            {createMutation.error ? (
              <span className="text-xs text-destructive">{errorMessage(createMutation.error)}</span>
            ) : null}
            {planMutation.error ? (
              <span className="text-xs text-destructive">{errorMessage(planMutation.error)}</span>
            ) : null}
            {updateMutation.error ? (
              <span className="text-xs text-destructive">{errorMessage(updateMutation.error)}</span>
            ) : null}
          </div>
        </div>

        {selectedId ? (
          <div className="grid gap-3 rounded-lg border border-border/60 p-4">
            <h2 className="text-sm font-semibold">Prompt pack</h2>
            <ProductVideoPromptPanel
              shots={shots}
              prompts={prompts}
               isLoading={detailQuery.isLoading || promptMutation.isPending}
               error={promptError ?? (detailQuery.error ? errorMessage(detailQuery.error) : null)}
              onRetry={() => promptMutation.mutate()}
              onDownload={() => downloadMutation.mutate()}
              isDownloading={downloadMutation.isPending}
            />
          </div>
        ) : null}
        {selectedId && detailQuery.data?.render_project_id ? (
          <AIVideoRenderPanel
            projectId={detailQuery.data.render_project_id}
            shots={detailQuery.data.render_shots}
            targetLanguage={detailQuery.data.target_language as VideoLanguage}
            onNotice={setRenderNotice}
          />
        ) : null}
        {renderNotice ? (
          <p className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
            {renderNotice}
          </p>
        ) : null}
      </section>
    </div>
  );
}
