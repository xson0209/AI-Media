import { useMutation } from '@tanstack/react-query';
import { ArrowRight, Loader2, Video } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiClient } from '@/lib/api/client';
import type {
  ResearchIdeaResponse,
  ResearchRecommendationResponse,
  ResearchScoreResponse,
  ResearchScriptResponse,
} from '@/lib/api/types';

type ResearchVideoAspectRatio = '9:16' | '16:9' | '1:1';

interface HandoffTarget {
  id: string;
  type: 'idea' | 'script';
  title: string;
  score: ResearchScoreResponse;
}

interface HandoffDialogProps {
  projectId: string;
  projectTitle: string;
  projectRevision: number;
  ideas: ResearchIdeaResponse[];
  scripts: ResearchScriptResponse[];
  scores: ResearchScoreResponse[];
  recommendation?: ResearchRecommendationResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNotice: (message: string) => void;
}

export function HandoffDialog({ projectId, projectTitle, projectRevision, ideas, scripts, scores, recommendation, open, onOpenChange, onNotice }: HandoffDialogProps) {
  const accepted = useMemo(() => [
    ...ideas.filter((idea) => idea.status === 'accepted').map((idea) => ({ id: idea.id, type: 'idea' as const, title: idea.title })),
    ...scripts.filter((script) => script.status === 'accepted').map((script) => ({ id: script.id, type: 'script' as const, title: script.title })),
  ], [ideas, scripts]);
  const currentScoreByTargetId = useMemo(() => {
    const current = new Map<string, ResearchScoreResponse>();
    for (const score of scores) {
      if (score.recommendation_status !== 'stale' && !current.has(score.target_id)) {
        current.set(score.target_id, score);
      }
    }
    return current;
  }, [scores]);
  const scoredTargetIds = useMemo(() => new Set(scores.map((score) => score.target_id)), [scores]);
  const eligibleTargets = useMemo<HandoffTarget[]>(() => accepted.flatMap((item) => {
    const score = currentScoreByTargetId.get(item.id);
    return score ? [{ ...item, score }] : [];
  }), [accepted, currentScoreByTargetId]);
  const eligibleTargetIds = useMemo(() => new Set(eligibleTargets.map((item) => item.id)), [eligibleTargets]);
  const acceptedWithoutScores = useMemo(
    () => accepted.filter((item) => !scoredTargetIds.has(item.id)),
    [accepted, scoredTargetIds],
  );
  const acceptedWithOnlyStaleScores = useMemo(
    () => accepted.filter((item) => scoredTargetIds.has(item.id) && !currentScoreByTargetId.has(item.id)),
    [accepted, currentScoreByTargetId, scoredTargetIds],
  );
  const recommendationTargetIds = useMemo(() => Array.from(new Set([
    recommendation?.selected_target_id,
    ...(recommendation?.recommended_target_ids ?? []),
  ].filter((targetId): targetId is string => Boolean(targetId)))), [recommendation]);
  const unapprovedRecommendationTargets = useMemo(() => recommendationTargetIds.filter((targetId) => {
    const idea = ideas.find((item) => item.id === targetId);
    const script = scripts.find((item) => item.id === targetId);
    return (idea && idea.status !== 'accepted') || (script && script.status !== 'accepted') || (!idea && !script);
  }), [ideas, recommendationTargetIds, scripts]);
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const [selectionTouched, setSelectionTouched] = useState(false);
  const [title, setTitle] = useState(projectTitle);
  const [duration, setDuration] = useState('180');
  const [aspectRatio, setAspectRatio] = useState<ResearchVideoAspectRatio>('9:16');

  useEffect(() => {
    if (!open) return;
    setTitle(projectTitle);
    setDuration('180');
    setAspectRatio('9:16');
    const recommendedTargetId = recommendationTargetIds.find((targetId) => eligibleTargetIds.has(targetId));
    setSelectedTargetId(recommendedTargetId ?? eligibleTargets[0]?.id ?? '');
    setSelectionTouched(false);
  }, [eligibleTargetIds, eligibleTargets, open, projectTitle, recommendationTargetIds]);

  const mutation = useMutation({
    mutationFn: () => apiClient.handoffResearchToAIVideo(projectId, {
      accepted_idea_ids: eligibleTargets.filter((item) => item.type === 'idea').map((item) => item.id),
      accepted_script_ids: eligibleTargets.filter((item) => item.type === 'script').map((item) => item.id),
      selected_target_id: selectedTargetId || undefined,
      selection_source: selectionTouched
        ? 'user_override'
        : recommendationTargetIds.includes(selectedTargetId)
          ? 'ai'
          : 'none',
      title: title.trim() || projectTitle,
      target_language: 'vi',
      target_duration_seconds: Math.max(1, Math.min(3600, Number(duration) || 180)),
      aspect_ratio: aspectRatio,
      idempotency_key: `${projectId}-${projectRevision}-${selectedTargetId || 'none'}-${duration}-${aspectRatio}`,
    }),
    onSuccess: (handoff) => {
      onNotice('Đã tạo AI Video project từ handoff. Đang mở luồng AI Video để tiếp tục với Codex.');
      onOpenChange(false);
      if (handoff.deep_link) window.location.assign(handoff.deep_link);
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không đóng gói được handoff.'),
  });

  const canSubmit = eligibleTargets.length > 0 && eligibleTargetIds.has(selectedTargetId) && !mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="[&>button]:min-h-11 [&>button]:min-w-11">
        <DialogHeader>
          <DialogTitle>Đóng gói sang AI Video</DialogTitle>
          <DialogDescription>Chỉ nội dung đã duyệt, có score hiện hành và memory hiện tại được chuyển sang project AI Video mới.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex items-start gap-3 border border-primary/30 bg-primary/5 p-3"><Video className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><div><p className="text-sm font-medium">Project AI Video mới</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Handoff tạo source blocks và Project Memory; bước viết story/kịch bản được tiếp tục ở AI Video.</p></div></div>
          <div><label htmlFor="handoff-title" className="text-sm font-medium">Tên project AI Video</label><Input id="handoff-title" className="mt-1.5" value={title} onChange={(event) => setTitle(event.target.value)} /></div>
          <div>
            <p className="text-sm font-medium">Phương án chính</p>
            {eligibleTargets.length ? (
              <div className="mt-2 space-y-2">
                {eligibleTargets.map((item) => (
                  <label key={item.id} className="flex min-h-11 cursor-pointer flex-wrap items-center gap-3 border border-border px-3 py-2">
                    <input
                      type="radio"
                      name="handoff-target"
                      value={item.id}
                      checked={selectedTargetId === item.id}
                      onChange={() => {
                        setSelectedTargetId(item.id);
                        setSelectionTouched(true);
                      }}
                      className="h-4 w-4 accent-primary"
                    />
                    <span className="min-w-0 flex-1 break-words text-sm">{item.title}</span>
                    <Badge variant="outline">{item.type === 'idea' ? 'Ý tưởng' : 'Kịch bản'}</Badge>
                    <Badge variant="secondary">{item.score.total_score}/100</Badge>
                  </label>
                ))}
              </div>
            ) : (
              <p className="mt-2 border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                Chưa có idea/script vừa được duyệt vừa có score hiện hành. Hãy duyệt và chấm điểm ít nhất một phương án trước khi handoff.
              </p>
            )}
          </div>
          {acceptedWithoutScores.length > 0 && (
            <p className="border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs leading-5 text-amber-800 dark:text-amber-200">
              {acceptedWithoutScores.length} nội dung đã duyệt chưa có score và sẽ chưa được đưa vào handoff. Hãy chấm điểm nếu muốn sử dụng.
            </p>
          )}
          {acceptedWithOnlyStaleScores.length > 0 && (
            <p className="border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs leading-5 text-amber-800 dark:text-amber-200">
              {acceptedWithOnlyStaleScores.length} nội dung chỉ còn score stale và sẽ chưa được đưa vào handoff. Hãy chấm lại sau thay đổi nguồn hoặc nội dung.
            </p>
          )}
          {unapprovedRecommendationTargets.length > 0 && (
            <p className="border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs leading-5 text-destructive">
              Lựa chọn AI/người dùng hiện tại đang trỏ tới nội dung chưa được duyệt nên đã bị bỏ qua. Hãy duyệt nội dung đó hoặc chọn phương án hợp lệ khác.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2"><div><label htmlFor="handoff-duration" className="text-sm font-medium">Thời lượng (giây)</label><Input id="handoff-duration" type="number" min={1} max={3600} className="mt-1.5" value={duration} onChange={(event) => setDuration(event.target.value)} /></div><div><label htmlFor="handoff-aspect" className="text-sm font-medium">Tỉ lệ khung hình</label><Select value={aspectRatio} onValueChange={(value) => setAspectRatio(value as ResearchVideoAspectRatio)}><SelectTrigger id="handoff-aspect" className="mt-1.5"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="9:16">9:16 dọc</SelectItem><SelectItem value="16:9">16:9 ngang</SelectItem><SelectItem value="1:1">1:1 vuông</SelectItem></SelectContent></Select></div></div>
          <p className="text-xs leading-5 text-muted-foreground">AI Video sẽ mở bằng project vừa tạo. Handoff không tự chạy planning, render hoặc generation.</p>
        </div>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Hủy</Button><Button disabled={!canSubmit} onClick={() => mutation.mutate()}>{mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />} Tạo và mở AI Video</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
