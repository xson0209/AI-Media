import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouterState } from '@tanstack/react-router';
import {
  AlertTriangle,
  ArrowRight,
  BookOpenCheck,
  Check,
  ChevronRight,
  Gauge,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trophy,
  Undo2,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import type {
  ResearchIdeaResponse,
  ResearchRecommendationResponse,
  ResearchScoreResponse,
  ResearchScriptResponse,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import { ChatDevelopmentPanel } from './ChatDevelopmentPanel';
import { HandoffDialog } from './HandoffDialog';
import { RunReviewPanel } from './RunReviewPanel';
import { SourcePanel } from './SourcePanel';

function searchProjectId(search: unknown): string | null {
  if (typeof search === 'string') return new URLSearchParams(search).get('projectId');
  if (search && typeof search === 'object') {
    const value = (search as Record<string, unknown>).projectId;
    return typeof value === 'string' ? value : null;
  }
  return null;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Bản nháp',
    researching: 'Đang nghiên cứu',
    ready_for_review: 'Chờ duyệt',
    approved: 'Đã duyệt',
    archived: 'Đã lưu trữ',
    partial: 'Có giới hạn',
    completed: 'Hoàn tất',
    failed: 'Có lỗi',
    candidate: 'Ứng viên',
    accepted: 'Đã chọn',
    recommended: 'Khuyên chọn',
    alternative: 'Phương án khác',
    blocked: 'Cần chỉnh',
    stale: 'Cần chấm lại',
    complete: 'Đủ dữ liệu',
    incomplete: 'Chưa đủ dữ liệu',
  };
  return labels[status] ?? status;
}

function scoreFor(scores: ResearchScoreResponse[], targetId: string): ResearchScoreResponse | undefined {
  return scores.find((score) => score.target_id === targetId && score.recommendation_status !== 'stale')
    ?? scores.find((score) => score.target_id === targetId);
}

const criterionLabels: Record<string, string> = {
  hook: 'Hook và lời hứa',
  structure: 'Cấu trúc 3 phút',
  conflict_emotion: 'Xung đột và cảm xúc',
  retention: 'Retention và payoff',
  originality: 'Độ mới',
  series_potential: 'Tiềm năng series',
  feasibility: 'Khả năng sản xuất',
};

function listValue(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)) : [];
}

function scoreComponents(content: Record<string, unknown>): Record<string, number> {
  const supported = ['hook', 'structure', 'conflict_emotion', 'retention', 'originality', 'series_potential', 'feasibility'];
  return Object.fromEntries(supported.flatMap((key) => {
    const value = Number(content[key]);
    return Number.isFinite(value) ? [[key, value]] : [];
  }));
}

export function ResearchWorkspace() {
  const routerState = useRouterState();
  const queryClient = useQueryClient();
  const requestedProjectId = searchProjectId(routerState.location.search);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(requestedProjectId);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState('sources');
  const [newTitle, setNewTitle] = useState('');
  const [newBrief, setNewBrief] = useState('');
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const appliedRequestedProjectIdRef = useRef<string | null>(null);

  const projectsQuery = useQuery({
    queryKey: ['research', 'projects'],
    queryFn: () => apiClient.listResearchProjects(),
  });
  const projects = projectsQuery.data ?? [];

  useEffect(() => {
    if (
      requestedProjectId
      && appliedRequestedProjectIdRef.current !== requestedProjectId
      && projects.some((project) => project.id === requestedProjectId)
    ) {
      appliedRequestedProjectIdRef.current = requestedProjectId;
      setSelectedProjectId(requestedProjectId);
      return;
    }
    if (!selectedProjectId && projects[0]) setSelectedProjectId(projects[0].id);
  }, [projects, requestedProjectId, selectedProjectId]);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const runsQuery = useQuery({
    queryKey: ['research', 'runs', selectedProjectId],
    queryFn: () => apiClient.listResearchRuns(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });
  const ideasQuery = useQuery({
    queryKey: ['research', 'ideas', selectedProjectId],
    queryFn: () => apiClient.listResearchIdeas(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });
  const scriptsQuery = useQuery({
    queryKey: ['research', 'scripts', selectedProjectId],
    queryFn: () => apiClient.listResearchScripts(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });
  const scoresQuery = useQuery({
    queryKey: ['research', 'scores', selectedProjectId],
    queryFn: () => apiClient.listResearchScores(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });
  const recommendationQuery = useQuery({
    queryKey: ['research', 'recommendation', selectedProjectId],
    queryFn: () => apiClient.getResearchRecommendation(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });
  const memoryQuery = useQuery({
    queryKey: ['research', 'memory', selectedProjectId],
    queryFn: () => apiClient.getResearchMemory(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  });

  const refreshProject = () => {
    void queryClient.invalidateQueries({ queryKey: ['research'] });
  };

  const createProjectMutation = useMutation({
    mutationFn: () => apiClient.createResearchProject({ title: newTitle.trim(), brief: newBrief.trim() }),
    onSuccess: (project) => {
      setNewTitle('');
      setNewBrief('');
      setSelectedProjectId(project.id);
      setNotice('Đã tạo Research Project mới.');
      refreshProject();
    },
  });

  const scoreMutation = useMutation({
    mutationFn: (target: { type: 'idea' | 'script'; id: string; content: Record<string, unknown> }) => apiClient.scoreResearchContent(selectedProjectId!, {
      target_type: target.type,
      target_id: target.id,
      components: scoreComponents(target.content),
      run_ai: true,
    }),
    onSuccess: () => {
      setActiveTab('scoring');
      void queryClient.invalidateQueries({ queryKey: ['research', 'scores', selectedProjectId] });
      void queryClient.invalidateQueries({ queryKey: ['research', 'recommendation', selectedProjectId] });
    },
  });

  const overrideMutation = useMutation({
    mutationFn: ({ scoreId, selected }: { scoreId: string; selected: boolean }) => apiClient.overrideResearchScore(
      selectedProjectId!,
      scoreId,
      selected
        ? { status: 'recommended', reason: 'Người dùng chọn phương án này trong Research Workspace.' }
        : { status: null, reason: 'Người dùng bỏ lựa chọn để đánh giá lại.' },
    ),
    onSuccess: (_score, variables) => {
      setNotice(variables.selected ? 'Đã lưu lựa chọn của bạn, tách riêng với đánh giá AI.' : 'Đã bỏ lựa chọn thủ công; khuyến nghị AI vẫn được giữ nguyên.');
      void queryClient.invalidateQueries({ queryKey: ['research', 'scores', selectedProjectId] });
      void queryClient.invalidateQueries({ queryKey: ['research', 'recommendation', selectedProjectId] });
    },
  });

  const approveMutation = useMutation<ResearchIdeaResponse | ResearchScriptResponse, Error, { type: 'idea' | 'script'; id: string }>({
    mutationFn: (target: { type: 'idea' | 'script'; id: string }) => target.type === 'idea'
      ? apiClient.setResearchIdeaStatus(selectedProjectId!, target.id, 'accepted')
      : apiClient.setResearchScriptStatus(selectedProjectId!, target.id, 'accepted'),
    onSuccess: () => {
      setNotice('Đã đưa phương án vào memory chuẩn.');
      refreshProject();
    },
  });


  const ideas = ideasQuery.data ?? [];
  const scripts = scriptsQuery.data ?? [];
  const scores = scoresQuery.data ?? [];
  const recommendation = recommendationQuery.data;
  const currentScores = recommendation?.ranked_scores ?? scores.filter((score) => score.recommendation_status !== 'stale');
  const acceptedCount = ideas.filter((idea) => idea.status === 'accepted').length + scripts.filter((script) => script.status === 'accepted').length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto py-3 [&_button]:min-h-11 [&_input:not([type='checkbox'])]:min-h-11 lg:overflow-hidden">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div>
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-muted-foreground">
            <BookOpenCheck className="h-4 w-4" aria-hidden="true" />
            Nghiên cứu ý tưởng
          </div>
          <h1 className="mt-1 text-xl font-semibold tracking-normal">Không gian dự án nghiên cứu</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Gom nguồn, phát triển nhiều hướng, chấm điểm và chỉ handoff phần bạn đã duyệt.</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{projects.length} dự án</Badge>
          <Button variant="outline" size="sm" onClick={refreshProject} aria-label="Làm mới nghiên cứu">
            <RefreshCw className="mr-2 h-4 w-4" /> Làm mới
          </Button>
        </div>
      </header>

      {notice && (
        <div className="flex items-start justify-between gap-3 border border-border bg-muted/30 px-3 py-2 text-sm" aria-live="polite">
          <span>{notice}</span>
          <button type="button" className="flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground" onClick={() => setNotice(null)} aria-label="Đóng thông báo"><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="grid min-h-0 flex-none gap-3 lg:flex-1 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="flex min-h-[360px] flex-col border border-border bg-card/60 lg:min-h-0">
          <div className="border-b border-border p-3">
            <p className="text-sm font-semibold">Dự án nghiên cứu</p>
            <p className="mt-1 text-xs text-muted-foreground">Chọn nhiều dự án để làm ngữ cảnh.</p>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {projectsQuery.isLoading && <div className="flex justify-center p-6"><Loader2 className="h-5 w-5 animate-spin" /></div>}
            {projects.map((project) => {
              const active = project.id === selectedProjectId;
              const checked = selectedProjectIds.includes(project.id);
              return (
                <div key={project.id} className={cn('mb-1 flex items-start gap-2 border px-2 py-2 transition-colors', active ? 'border-primary/60 bg-primary/5' : 'border-transparent hover:border-border')}>
                  <label className="flex h-11 w-11 shrink-0 cursor-pointer items-start justify-center pt-3">
                    <input type="checkbox" checked={checked} onChange={() => setSelectedProjectIds((current) => current.includes(project.id) ? current.filter((id) => id !== project.id) : [...current, project.id])} className="h-4 w-4 accent-primary" aria-label={`Chọn ${project.title} làm ngữ cảnh`} />
                  </label>
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSelectedProjectId(project.id)}>
                    <span className="block truncate text-sm font-medium">{project.title}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{statusLabel(project.status)} · r{project.revision}</span>
                  </button>
                  <ChevronRight className={cn('mt-1 h-4 w-4 shrink-0 text-muted-foreground', active && 'text-primary')} aria-hidden="true" />
                </div>
              );
            })}
            {!projects.length && !projectsQuery.isLoading && <p className="p-4 text-center text-sm text-muted-foreground">Chưa có dự án nghiên cứu.</p>}
          </div>
          <div className="border-t border-border p-3">
            <Input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Tên dự án mới" aria-label="Tên dự án mới" />
            <Textarea value={newBrief} onChange={(event) => setNewBrief(event.target.value)} placeholder="Brief ban đầu" className="mt-2 min-h-20" aria-label="Brief ban đầu" />
            <Button className="mt-2 w-full" size="sm" disabled={!newTitle.trim() || createProjectMutation.isPending} onClick={() => createProjectMutation.mutate()}>
              {createProjectMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Tạo dự án
            </Button>
          </div>
        </aside>

        <main className="min-h-[520px] overflow-visible border border-border bg-card/30 p-3 sm:p-4 lg:min-h-0 lg:overflow-y-auto">
          {!selectedProject ? (
            <div className="flex min-h-[420px] items-center justify-center text-center">
              <div className="max-w-md"><Sparkles className="mx-auto h-8 w-8 text-primary" /><h2 className="mt-3 text-lg font-semibold">Bắt đầu một dự án nghiên cứu</h2><p className="mt-2 text-sm text-muted-foreground">Tạo project ở bên trái, sau đó thêm nguồn và chọn hướng phát triển.</p></div>
            </div>
          ) : (
            <>
              <section className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold">{selectedProject.title}</h2><Badge variant="outline">{statusLabel(selectedProject.status)}</Badge><Badge variant="secondary">Memory r{selectedProject.revision}</Badge></div>
                  <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{selectedProject.brief || selectedProject.description || 'Chưa có brief.'}</p>
                  {selectedProjectIds.length > 1 && <p className="mt-2 text-xs text-primary">Đang chọn {selectedProjectIds.length} project làm context tổng hợp.</p>}
                </div>
                <Button disabled={acceptedCount === 0} onClick={() => setHandoffOpen(true)}>
                  <ArrowRight className="mr-2 h-4 w-4" /> Đóng gói sang AI Video
                </Button>
              </section>

              <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-3">
                <TabsList className="flex h-auto flex-wrap justify-start gap-1 bg-muted/40 p-1">
                  <TabsTrigger value="sources">Nguồn</TabsTrigger>
                  <TabsTrigger value="runs">Lần chạy</TabsTrigger>
                  <TabsTrigger value="options">Phương án</TabsTrigger>
                  <TabsTrigger value="scoring">Chấm điểm</TabsTrigger>
                  <TabsTrigger value="chat">Phát triển content</TabsTrigger>
                  <TabsTrigger value="memory">Memory</TabsTrigger>
                </TabsList>

                <TabsContent value="sources" className="mt-3"><SourcePanel projectId={selectedProject.id} onNotice={setNotice} /></TabsContent>

                <TabsContent value="runs" className="mt-3"><RunReviewPanel projectId={selectedProject.id} selectedProjectIds={selectedProjectIds} runs={runsQuery.data ?? []} ideas={ideas} onNotice={setNotice} onOpenOptions={() => setActiveTab('options')} /></TabsContent>

                <TabsContent value="options" className="mt-3 space-y-3">
                  {recommendation && <RecommendationSummary recommendation={recommendation} ideas={ideas} scripts={scripts} />}
                  {ideas.map((idea) => { const score = scoreFor(scores, idea.id); return <IdeaRow key={idea.id} idea={idea} score={score} onScore={() => scoreMutation.mutate({ type: 'idea', id: idea.id, content: idea.content })} onApprove={() => approveMutation.mutate({ type: 'idea', id: idea.id })} scoring={scoreMutation.isPending} approving={approveMutation.isPending} />; })}
                  {scripts.map((script) => { const score = scoreFor(scores, script.id); return <ScriptRow key={script.id} script={script} score={score} onScore={() => scoreMutation.mutate({ type: 'script', id: script.id, content: script.content_json })} onApprove={() => approveMutation.mutate({ type: 'script', id: script.id })} scoring={scoreMutation.isPending} approving={approveMutation.isPending} />; })}
                  {!ideas.length && !scripts.length && <EmptyState label="Chưa có phương án. Hãy chạy một lần nghiên cứu." />}
                </TabsContent>

                <TabsContent value="scoring" className="mt-3 space-y-3">
                  <div className="border border-border bg-card p-3"><h3 className="font-medium">Chấm điểm và phương án khuyên chọn</h3><p className="mt-1 text-sm text-muted-foreground">Rubric hiện hành gồm bảy tiêu chí, thang 100 điểm và safety gate.</p></div>
                  {recommendation && <RecommendationSummary recommendation={recommendation} ideas={ideas} scripts={scripts} />}
                  {currentScores.map((score) => <ScoreRow
                    key={score.id}
                    score={score}
                    title={ideas.find((idea) => idea.id === score.target_id)?.title ?? scripts.find((script) => script.id === score.target_id)?.title}
                    selected={recommendation?.selected_score_id === score.id}
                    onSelect={() => overrideMutation.mutate({ scoreId: score.id, selected: true })}
                    onClear={() => overrideMutation.mutate({ scoreId: score.id, selected: false })}
                    selecting={overrideMutation.isPending}
                  />)}
                  {!currentScores.length && <EmptyState label="Chưa có điểm. Mở tab Phương án để chấm từng hướng." />}
                  {recommendation?.has_stale && <p className="flex items-center gap-2 border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-800 dark:text-amber-200"><AlertTriangle className="h-4 w-4 shrink-0" /> Có bản chấm cũ đã stale và không còn được dùng để khuyên chọn.</p>}
                </TabsContent>

                <TabsContent value="chat" className="mt-3"><ChatDevelopmentPanel projectId={selectedProject.id} projects={projects} selectedProjectIds={selectedProjectIds} onNotice={setNotice} /></TabsContent>

                <TabsContent value="memory" className="mt-3"><pre className="max-h-[620px] overflow-auto whitespace-pre-wrap border border-border bg-card p-4 font-mono text-xs leading-5">{memoryQuery.data || 'Chưa có memory.'}</pre></TabsContent>
              </Tabs>
              <HandoffDialog
                projectId={selectedProject.id}
                projectTitle={selectedProject.title}
                projectRevision={selectedProject.revision}
                ideas={ideas}
                scripts={scripts}
                scores={scores}
                recommendation={recommendation}
                open={handoffOpen}
                onOpenChange={setHandoffOpen}
                onNotice={setNotice}
              />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function IdeaRow({ idea, score, onScore, onApprove, scoring, approving }: { idea: ResearchIdeaResponse; score?: ResearchScoreResponse; onScore: () => void; onApprove: () => void; scoring: boolean; approving: boolean }) {
  return <div className="border border-border bg-card p-3"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{idea.title}</h3><Badge variant={idea.status === 'accepted' ? 'default' : 'outline'}>{statusLabel(idea.status)}</Badge>{score && <Badge variant={score.recommendation_status === 'recommended' ? 'default' : 'secondary'}>{statusLabel(score.recommendation_status)} · {score.total_score}/100</Badge>}</div><p className="mt-2 text-sm leading-6 text-muted-foreground">{idea.summary || String(idea.content.hook || 'Chưa có mô tả.')}</p></div><div className="flex shrink-0 gap-2"><Button size="sm" variant="outline" disabled={scoring} onClick={onScore}>{scoring ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="mr-1.5 h-4 w-4" />} Chấm</Button>{idea.status !== 'accepted' && <Button size="sm" disabled={approving} onClick={onApprove}>{approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="mr-1.5 h-4 w-4" />} Duyệt</Button>}</div></div>{score?.recommendation_reason && <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">{score.recommendation_reason}</p>}</div>;
}

function ScriptRow({ script, score, onScore, onApprove, scoring, approving }: { script: ResearchScriptResponse; score?: ResearchScoreResponse; onScore: () => void; onApprove: () => void; scoring: boolean; approving: boolean }) {
  return <div className="border border-border bg-card p-3"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{script.title}</h3><Badge variant={script.status === 'accepted' ? 'default' : 'outline'}>{statusLabel(script.status)}</Badge>{score && <Badge variant={score.recommendation_status === 'recommended' ? 'default' : 'secondary'}>{statusLabel(score.recommendation_status)} · {score.total_score}/100</Badge>}</div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{script.content || 'Kịch bản seed chưa có nội dung.'}</p></div><div className="flex shrink-0 gap-2"><Button size="sm" variant="outline" disabled={scoring} onClick={onScore}>{scoring ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="mr-1.5 h-4 w-4" />} Chấm</Button>{script.status !== 'accepted' && <Button size="sm" disabled={approving} onClick={onApprove}>{approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="mr-1.5 h-4 w-4" />} Duyệt</Button>}</div></div>{score?.recommendation_reason && <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">{score.recommendation_reason}</p>}</div>;
}

function targetTitle(targetId: string, ideas: ResearchIdeaResponse[], scripts: ResearchScriptResponse[]): string {
  return ideas.find((idea) => idea.id === targetId)?.title
    ?? scripts.find((script) => script.id === targetId)?.title
    ?? targetId;
}

function RecommendationSummary({ recommendation, ideas, scripts }: { recommendation: ResearchRecommendationResponse; ideas: ResearchIdeaResponse[]; scripts: ResearchScriptResponse[] }) {
  const selectedTitle = recommendation.selected_target_id ? targetTitle(recommendation.selected_target_id, ideas, scripts) : null;
  const recommendedTitles = recommendation.recommended_target_ids.map((id) => targetTitle(id, ideas, scripts));
  const topTie = recommendation.tie_groups.find((group) => group.rank === 1);
  return (
    <section className={cn('border px-3 py-3', selectedTitle ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-primary/40 bg-primary/5')} aria-label="Tóm tắt phương án khuyên chọn">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold">
            {selectedTitle ? <ShieldCheck className="h-4 w-4 text-emerald-600" /> : <Trophy className="h-4 w-4 text-primary" />}
            {selectedTitle ? 'Lựa chọn của bạn' : 'Phương án AI khuyên chọn'}
          </div>
          <p className="mt-1 break-words text-sm">
            {selectedTitle ?? (recommendedTitles.length ? recommendedTitles.join(' · ') : 'Chưa có phương án đủ điều kiện')}
          </p>
          {recommendation.summary_reason && <p className="mt-1 text-xs leading-5 text-muted-foreground">{recommendation.summary_reason}</p>}
        </div>
        <Badge variant={selectedTitle ? 'secondary' : 'outline'}>{recommendation.rubric_version}</Badge>
      </div>
      {topTie && <p className="mt-2 flex items-start gap-2 text-xs text-muted-foreground"><Gauge className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Nhóm dẫn đầu có {topTie.target_ids.length} phương án trong khoảng 3 điểm; xem trade-off trước khi duyệt.</p>}
    </section>
  );
}

function ScoreRow({ score, title, selected, onSelect, onClear, selecting }: { score: ResearchScoreResponse; title?: string; selected: boolean; onSelect: () => void; onClear: () => void; selecting: boolean }) {
  const strengths = listValue(score.tradeoffs.strengths);
  const weaknesses = listValue(score.tradeoffs.weaknesses);
  const risks = listValue(score.tradeoffs.risks);
  const violations = listValue(score.safety_gate.violations);
  const improvements = listValue(score.improvement_actions);
  const evidence = score.evidence_refs.map((item) => typeof item === 'string' ? item : JSON.stringify(item));
  const limitations = score.limitations.map((item) => typeof item === 'string' ? item : JSON.stringify(item));
  return (
    <article className={cn('border bg-card p-3 sm:p-4', selected ? 'border-emerald-500/60' : 'border-border')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="break-words font-medium">{title || score.target_id}</h4>
            <Badge variant="outline">{score.target_type === 'script' ? 'Kịch bản' : 'Ý tưởng'}</Badge>
            {score.rank != null && <Badge variant="secondary">Hạng {score.rank}</Badge>}
            {score.tie_group != null && <Badge variant="outline">Nhóm tương đương {score.tie_group}</Badge>}
            <Badge variant={score.completeness_status === 'complete' ? 'secondary' : 'outline'}>{statusLabel(score.completeness_status)}</Badge>
            {selected && <Badge>Đang chọn</Badge>}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Confidence {Math.round((score.confidence ?? 0) * 100)}% · {score.rubric_version}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xl font-semibold tabular-nums">{score.total_score}/100</p>
          <Badge variant={score.recommendation_status === 'recommended' ? 'default' : 'outline'}>{statusLabel(score.recommendation_status)}</Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-x-5 sm:grid-cols-2">
        {Object.entries(score.components).map(([key, item]) => (
          <div key={key} className="border-t border-border py-3 first:border-t-0 sm:[&:nth-child(2)]:border-t-0">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{criterionLabels[key] ?? key}</span>
              <span className="shrink-0 tabular-nums">{item.score}/10</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden bg-muted" aria-hidden="true"><div className="h-full bg-primary" style={{ width: `${item.score * 10}%` }} /></div>
            <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{item.explanation}</p>
          </div>
        ))}
      </div>

      <div className={cn('mt-2 flex items-start gap-2 border px-3 py-2 text-sm', score.safety_gate.passed ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-amber-500/50 bg-amber-500/5')}>
        {score.safety_gate.passed ? <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
        <div><p className="font-medium">{score.safety_gate.passed ? 'Đạt safety gate' : 'Chưa đạt safety gate'}</p>{violations.length > 0 && <p className="mt-1 text-xs leading-5 text-muted-foreground">{violations.join(' · ')}</p>}</div>
      </div>

      <p className="mt-3 text-sm leading-6 text-muted-foreground">{score.recommendation_reason}</p>

      {(strengths.length > 0 || weaknesses.length > 0 || risks.length > 0) && (
        <div className="mt-4 grid gap-4 border-t border-border pt-3 md:grid-cols-3">
          <ScoreList title="Điểm mạnh" items={strengths} />
          <ScoreList title="Điểm yếu" items={weaknesses} />
          <ScoreList title="Rủi ro" items={risks} emptyLabel="Chưa ghi nhận rủi ro riêng." />
        </div>
      )}

      {improvements.length > 0 && <div className="mt-4 border-t border-border pt-3"><p className="text-sm font-medium">Hành động cải thiện</p><ol className="mt-2 space-y-1 text-sm leading-6 text-muted-foreground">{improvements.map((item, index) => <li key={item}>{index + 1}. {item}</li>)}</ol></div>}

      {(evidence.length > 0 || limitations.length > 0) && (
        <div className="mt-4 grid gap-4 border-t border-border pt-3 md:grid-cols-2">
          <ScoreList title={`Evidence (${evidence.length})`} items={evidence} />
          <ScoreList title={`Giới hạn (${limitations.length})`} items={limitations} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-border pt-3">
        {selected ? (
          <Button variant="outline" size="sm" disabled={selecting} onClick={onClear}>{selecting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Undo2 className="mr-2 h-4 w-4" />} Bỏ lựa chọn</Button>
        ) : (
          <Button variant="outline" size="sm" disabled={selecting || score.recommendation_status === 'stale'} onClick={onSelect}>{selecting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />} Chọn phương án này</Button>
        )}
      </div>
    </article>
  );
}

function ScoreList({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel?: string }) {
  return <div><p className="text-sm font-medium">{title}</p>{items.length > 0 ? <ul className="mt-2 space-y-1 text-xs leading-5 text-muted-foreground">{items.map((item) => <li key={item} className="break-words">• {item}</li>)}</ul> : emptyLabel ? <p className="mt-2 text-xs text-muted-foreground">{emptyLabel}</p> : null}</div>;
}

function EmptyState({ label }: { label: string }) { return <div className="border border-dashed border-border p-8 text-center text-sm text-muted-foreground">{label}</div>; }
