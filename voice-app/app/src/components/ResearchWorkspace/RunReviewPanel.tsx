import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Check,
  GitMerge,
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { apiClient } from '@/lib/api/client';
import type { ResearchIdeaResponse, ResearchRunMode, ResearchRunResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import { researchStatusLabel } from './researchUi';

interface RunReviewPanelProps {
  projectId: string;
  selectedProjectIds: string[];
  runs: ResearchRunResponse[];
  ideas: ResearchIdeaResponse[];
  onNotice: (message: string) => void;
  onOpenOptions: () => void;
}

export function RunReviewPanel({ projectId, selectedProjectIds, runs, ideas, onNotice, onOpenOptions }: RunReviewPanelProps) {
  const queryClient = useQueryClient();
  const [runMode, setRunMode] = useState<ResearchRunMode>('both');
  const [reviewTab, setReviewTab] = useState<'research' | 'creative' | 'merge'>('merge');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const runMutation = useMutation({
    mutationFn: () => apiClient.createResearchRun(projectId, {
      mode: runMode,
      related_project_ids: selectedProjectIds.filter((id) => id !== projectId),
      run_ai: true,
    }),
    onSuccess: (run) => {
      setSelectedRunId(run.id);
      onNotice(run.status === 'completed' ? 'Đã hoàn tất lần nghiên cứu.' : 'Lần nghiên cứu đã trả trạng thái review.');
      void queryClient.invalidateQueries({ queryKey: ['research', 'runs', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['research', 'ideas', projectId] });
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không chạy được nghiên cứu.'),
  });
  const retryMutation = useMutation({
    mutationFn: (runId: string) => apiClient.retryResearchRun(projectId, runId, true),
    onSuccess: () => {
      onNotice('Đã tạo lần chạy thử lại; kết quả cũ vẫn được giữ để so sánh.');
      void queryClient.invalidateQueries({ queryKey: ['research', 'runs', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['research', 'ideas', projectId] });
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không thử lại được run.'),
  });
  const mergeMutation = useMutation({
    mutationFn: (runId: string) => apiClient.mergeResearchRun(projectId, runId),
    onSuccess: () => {
      onNotice('Đã hợp nhất lại các attempt; bất đồng được giữ trong review.');
      void queryClient.invalidateQueries({ queryKey: ['research', 'runs', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['research', 'ideas', projectId] });
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không hợp nhất được run.'),
  });

  const activeRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;

  return (
    <div className="space-y-3">
      <section className="border border-border bg-card p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-medium">Chạy nghiên cứu bằng hai vai trò</h3>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">AI nghiên cứu tài liệu tìm evidence và rủi ro; AI sáng tạo phát triển hook, beat và script seed. Chế độ Cả hai giữ hai attempt riêng rồi mới hợp nhất.</p>
          </div>
          <Button disabled={runMutation.isPending} onClick={() => runMutation.mutate()}>
            {runMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Chạy {runMode === 'both' ? 'cả hai' : runMode === 'research' ? 'nghiên cứu' : 'sáng tạo'}
          </Button>
        </div>
        <fieldset className="mt-3 grid gap-2 md:grid-cols-3">
          <legend className="sr-only">Chế độ nghiên cứu</legend>
          {([
            ['research', 'Nghiên cứu tài liệu', 'Docs, evidence, so sánh và rủi ro.'],
            ['creative', 'Phát triển content', 'Concept, hook, beat và script seed.'],
            ['both', 'Cả hai', 'Hai attempt độc lập, sau đó hợp nhất.'],
          ] as const).map(([value, label, description]) => (
            <button
              key={value}
              type="button"
              className={cn('min-h-16 border px-3 py-2 text-left transition-colors', runMode === value ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40')}
              aria-pressed={runMode === value}
              onClick={() => setRunMode(value)}
            >
              <span className="block text-sm font-medium">{label}</span>
              <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
            </button>
          ))}
        </fieldset>
      </section>

      {!runs.length && <div className="border border-dashed border-border p-8 text-center text-sm text-muted-foreground">Chưa có lần chạy. Chọn một mode ở trên để bắt đầu.</div>}
      {runs.map((run) => (
        <article key={run.id} className={cn('border bg-card p-3', activeRun?.id === run.id ? 'border-primary/60' : 'border-border')}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <button type="button" className="min-w-0 text-left" onClick={() => setSelectedRunId(run.id)}>
              <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{run.mode === 'both' ? 'Cả hai' : run.mode === 'research' ? 'Nghiên cứu tài liệu' : 'Phát triển content'}</span><Badge variant="outline">{researchStatusLabel(run.status)}</Badge><Badge variant="secondary">{new Date(run.created_at).toLocaleString('vi-VN')}</Badge></div>
              <p className="mt-1 text-xs text-muted-foreground">{Array.isArray(run.output.options) ? `${run.output.options.length} phương án hợp nhất` : 'Chưa có phương án'}{run.cost.token_metadata_available ? ' · Có metadata token/chi phí' : ''}</p>
            </button>
            <div className="flex flex-wrap gap-2">
              {run.status === 'failed' || run.status === 'partial' ? <Button size="sm" variant="outline" disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(run.id)}><RefreshCw className="mr-1.5 h-4 w-4" /> Thử lại</Button> : null}
              {run.mode === 'both' && <Button size="sm" variant="outline" disabled={mergeMutation.isPending} onClick={() => mergeMutation.mutate(run.id)}><GitMerge className="mr-1.5 h-4 w-4" /> Hợp nhất lại</Button>}
            </div>
          </div>
        </article>
      ))}

      {activeRun && (
        <section className="border border-border bg-card p-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium">Review run: {activeRun.id.slice(0, 8)}</h3>{activeRun.status === 'failed' ? <span className="flex items-center gap-1 text-xs text-destructive"><XCircle className="h-3.5 w-3.5" /> {activeRun.error_code || 'Run lỗi'}</span> : null}</div>
          <Tabs value={reviewTab} onValueChange={(value) => setReviewTab(value as typeof reviewTab)} className="mt-3">
            <TabsList className="grid w-full grid-cols-3"><TabsTrigger value="research">Nghiên cứu</TabsTrigger><TabsTrigger value="creative">Sáng tạo</TabsTrigger><TabsTrigger value="merge">Hợp nhất</TabsTrigger></TabsList>
            <TabsContent value="research" className="mt-3"><AttemptReview attempt={activeRun.output.attempts?.research} emptyLabel="Attempt nghiên cứu chưa trả kết quả." /></TabsContent>
            <TabsContent value="creative" className="mt-3"><AttemptReview attempt={activeRun.output.attempts?.creative} emptyLabel="Attempt sáng tạo chưa trả kết quả." /></TabsContent>
            <TabsContent value="merge" className="mt-3 space-y-2">
              {Array.isArray(activeRun.output.merge?.disagreements) && activeRun.output.merge.disagreements.length > 0 && <p className="border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs leading-5">Có bất đồng giữa hai attempt. Hệ thống giữ cả hai cách nhìn để bạn chọn, không tự đưa vào canon.</p>}
              {((activeRun.output.options ?? []) as Array<Record<string, unknown>>).map((option, index) => {
                const title = typeof option.title === 'string' ? option.title : `Phương án ${index + 1}`;
                const matchingIdea = ideas.find((idea) => idea.title === title);
                return <div key={`${activeRun.id}-${index}`} className="border border-border px-3 py-3"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-medium">{title}</h4>{option.recommendation_candidate ? <Badge>Ứng viên khuyên chọn</Badge> : null}</div><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{String(option.summary || option.hook || 'Chưa có tóm tắt.')}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>Đóng góp: {Array.isArray(option.contributions) ? option.contributions.map((item) => typeof item === 'object' && item && 'mode' in item ? String(item.mode) : '').filter(Boolean).join(' + ') || 'fallback' : String(option.source_provider || 'merged')}</span>{Array.isArray(option.disagreements) && option.disagreements.length > 0 ? <span>· Có điểm cần so sánh</span> : null}</div><Button size="sm" variant="outline" className="mt-3" onClick={onOpenOptions}>{matchingIdea ? <Check className="mr-1.5 h-4 w-4" /> : null} Mở review phương án và duyệt</Button></div>;
              })}
              {!activeRun.output.options?.length && <div className="border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Chưa có phương án hợp nhất để review.</div>}
            </TabsContent>
          </Tabs>
          {activeRun.output.repository_study && typeof activeRun.output.repository_study === 'object' ? <StudyReview study={activeRun.output.repository_study as Record<string, unknown>} /> : null}
        </section>
      )}
    </div>
  );
}

function StudyReview({ study }: { study: Record<string, unknown> }) {
  const facts = Array.isArray(study.facts) ? study.facts : [];
  const openQuestions = Array.isArray(study.open_questions) ? study.open_questions : [];
  return <div className="mt-4 border border-primary/30 bg-primary/5 p-3">
    <div className="flex flex-wrap items-center gap-2"><Badge>Fact preflight</Badge><span className="text-sm font-medium">Nguồn đã được đọc trước khi sáng tạo</span></div>
    <p className="mt-1 text-sm leading-6 text-muted-foreground">{String(study.summary || '')}</p>
    <div className="mt-3 space-y-2">{facts.slice(0, 12).map((fact, index) => { const value = typeof fact === 'object' && fact ? fact as Record<string, unknown> : {}; return <div key={String(value.id || index)} className="border border-border bg-background px-3 py-2 text-sm"><div className="flex flex-wrap items-center gap-2"><Badge variant="secondary">{String(value.verification || 'reviewed')}</Badge><span className="font-medium">{String(value.id || `fact-${index + 1}`)}</span></div><p className="mt-1 leading-6">{String(value.statement || '')}</p><p className="mt-1 text-xs text-muted-foreground">Bằng chứng: {Array.isArray(value.evidence) ? value.evidence.map((item) => typeof item === 'object' && item ? String((item as Record<string, unknown>).id || '') : '').filter(Boolean).join(', ') : '—'}</p></div>; })}</div>
    {openQuestions.length ? <p className="mt-2 text-xs leading-5 text-amber-700 dark:text-amber-300">Câu hỏi còn mở: {openQuestions.map(String).join(' · ')}</p> : null}
  </div>;
}

function AttemptReview({ attempt, emptyLabel }: { attempt?: { status: string; output: { options?: Array<Record<string, unknown>>; [key: string]: unknown }; error_code?: string | null; error_message?: string | null; duration_ms: number }; emptyLabel: string }) {
  if (!attempt) return <div className="border border-dashed border-border p-6 text-center text-sm text-muted-foreground">{emptyLabel}</div>;
  const options = attempt.output.options ?? [];
  return <div className="space-y-2"><div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Badge variant="outline">{researchStatusLabel(attempt.status)}</Badge><span>{attempt.duration_ms}ms</span>{attempt.error_code ? <span className="text-destructive">{attempt.error_code}</span> : null}</div>{options.map((option, index) => <div key={JSON.stringify(option)} className="border border-border px-3 py-3"><h4 className="font-medium">{String(option.title || `Phương án ${index + 1}`)}</h4><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{String(option.summary || option.hook || 'Chưa có tóm tắt.')}</p></div>)}{attempt.error_message ? <p className="border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs" role="alert">{attempt.error_message}</p> : null}{!options.length && !attempt.error_message && <div className="border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Attempt chưa có phương án.</div>}</div>;
}
