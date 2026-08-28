import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, GitBranch, Loader2, MessageSquareText, Send, Undo2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import type { ResearchChatAction, ResearchChatResponse, ResearchProjectResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

interface ChatDevelopmentPanelProps {
  projectId: string;
  projects: ResearchProjectResponse[];
  selectedProjectIds: string[];
  onNotice: (message: string) => void;
}

const actions: Array<{ value: ResearchChatAction; label: string }> = [
  { value: 'develop', label: 'Phát triển tiếp' },
  { value: 'next_episode', label: 'Viết tập sau' },
  { value: 'variant', label: 'Tạo biến thể' },
  { value: 'increase_drama', label: 'Tăng drama' },
  { value: 'fix_logic', label: 'Sửa logic' },
  { value: 'develop_character', label: 'Phát triển nhân vật' },
  { value: 'script_seed', label: 'Tạo script seed' },
];

export function ChatDevelopmentPanel({ projectId, projects, selectedProjectIds, onNotice }: ChatDevelopmentPanelProps) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const [action, setAction] = useState<ResearchChatAction>('develop');
  const [mode, setMode] = useState<'research' | 'creative' | 'both'>('both');
  const [branchName, setBranchName] = useState('');
  const [threadId, setThreadId] = useState<string | undefined>();
  const [latest, setLatest] = useState<ResearchChatResponse | null>(null);
  const [latestPromoted, setLatestPromoted] = useState(false);

  useEffect(() => {
    void projectId;
    setMessage('');
    setAction('develop');
    setMode('both');
    setBranchName('');
    setThreadId(undefined);
    setLatest(null);
    setLatestPromoted(false);
  }, [projectId]);

  const threadsQuery = useQuery({
    queryKey: ['research', 'chat-threads', projectId],
    queryFn: () => apiClient.listResearchChatThreads(projectId),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['research', 'chat-threads', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'ideas', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'scripts', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'memory', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['research', 'recommendation', projectId] });
  };
  const chatMutation = useMutation({
    mutationFn: () => apiClient.researchChat(projectId, {
      message: message.trim(),
      mode,
      selected_project_ids: selectedProjectIds.filter((id) => id !== projectId),
      action,
      thread_id: threadId,
      branch_name: action === 'variant' ? (branchName.trim() || undefined) : branchName.trim() || undefined,
      run_ai: true,
    }),
    onSuccess: (response) => {
      setLatest(response);
      setLatestPromoted(false);
      setThreadId(response.thread_id);
      setMessage('');
      onNotice('Đã tạo bản nháp. Draft chưa thay đổi memory chuẩn.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không tạo được bản nháp chat.'),
  });
  const approveMutation = useMutation({
    mutationFn: (type: 'idea' | 'script' | 'memory_card') => apiClient.approveResearchChatMessage(projectId, latest!.assistant_message_id, type),
    onSuccess: (_response, type) => {
      setLatestPromoted(true);
      onNotice(type === 'script' ? 'Đã duyệt script seed và tạo revision memory.' : 'Đã duyệt nội dung chat; memory đã được compile lại.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không duyệt được draft chat.'),
  });
  const rejectMutation = useMutation({
    mutationFn: () => apiClient.rejectResearchChatMessage(projectId, latest!.assistant_message_id),
    onSuccess: () => {
      setLatest(null);
      setLatestPromoted(false);
      onNotice('Đã bỏ qua draft; canon không thay đổi.');
      refresh();
    },
    onError: (error) => onNotice(error instanceof Error ? error.message : 'Không bỏ qua được draft.'),
  });

  return (
    <div className="space-y-3">
      <section className="border border-border bg-card p-3">
        <div className="flex items-center gap-2"><MessageSquareText className="h-4 w-4 text-primary" aria-hidden="true" /><h3 className="font-medium">Trò chuyện để phát triển tiếp</h3></div>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">Chat dùng memory và source đã duyệt. Mỗi câu trả lời là draft; bạn quyết định phần nào thành canon.</p>
        <fieldset className="mt-3 flex flex-wrap gap-2">
          <legend className="sr-only">Action phát triển nội dung</legend>
          {actions.map((item) => <Button key={item.value} size="sm" variant={action === item.value ? 'default' : 'outline'} aria-pressed={action === item.value} onClick={() => setAction(item.value)}>{item.label}</Button>)}
        </fieldset>
        <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(180px,0.35fr)]">
          <Textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ví dụ: Viết tiếp tập 2, giữ cú twist cuối tập 1 nhưng làm nhân vật chính bị hiểu lầm nặng hơn." className="min-h-32" aria-label="Yêu cầu phát triển nội dung" />
          <div className="space-y-2">
            <fieldset className="flex flex-wrap gap-2"><legend className="sr-only">Vai trò AI trong chat</legend><Button size="sm" variant={mode === 'research' ? 'default' : 'outline'} onClick={() => setMode('research')}>Nghiên cứu</Button><Button size="sm" variant={mode === 'creative' ? 'default' : 'outline'} onClick={() => setMode('creative')}>Sáng tạo</Button><Button size="sm" variant={mode === 'both' ? 'default' : 'outline'} onClick={() => setMode('both')}>Cả hai</Button></fieldset>
            <Input value={branchName} onChange={(event) => setBranchName(event.target.value)} placeholder={action === 'variant' ? 'Tên nhánh thay thế' : 'Tên nhánh (không bắt buộc)'} aria-label="Tên nhánh chat" />
            <Button className="w-full" disabled={!message.trim() || chatMutation.isPending} onClick={() => chatMutation.mutate()}>{chatMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />} Tạo bản nháp</Button>
          </div>
        </div>
        {selectedProjectIds.filter((id) => id !== projectId).length > 0 && <p className="mt-2 text-xs text-primary">Context liên quan: {selectedProjectIds.filter((id) => id !== projectId).map((id) => projects.find((project) => project.id === id)?.title || id).join(' · ')}</p>}
      </section>

      {latest && <DraftReview response={latest} promoted={latestPromoted} approving={approveMutation.isPending} rejecting={rejectMutation.isPending} onApprove={(type) => approveMutation.mutate(type)} onReject={() => rejectMutation.mutate()} />}

      {(threadsQuery.data ?? []).length > 0 && <section className="border border-border bg-card p-3"><div className="flex items-center gap-2"><GitBranch className="h-4 w-4" /><h3 className="font-medium">Lịch sử nhánh</h3></div><div className="mt-2 space-y-2">{(threadsQuery.data ?? []).map((thread) => <button key={thread.id} type="button" className={cn('flex min-h-11 w-full items-center justify-between gap-3 border px-3 py-2 text-left', thread.id === threadId ? 'border-primary bg-primary/5' : 'border-border')} onClick={() => { setThreadId(thread.id); setLatest(null); setLatestPromoted(false); }}><span className="min-w-0"><span className="block truncate text-sm font-medium">{thread.branch_name}</span><span className="block text-xs text-muted-foreground">{thread.messages.length} tin nhắn · {new Date(thread.updated_at).toLocaleString('vi-VN')}</span></span><Badge variant="outline">{thread.status === 'active' ? 'Đang mở' : thread.status}</Badge></button>)}</div></section>}
    </div>
  );
}

function DraftReview({ response, promoted, approving, rejecting, onApprove, onReject }: { response: ResearchChatResponse; promoted: boolean; approving: boolean; rejecting: boolean; onApprove: (type: 'idea' | 'script' | 'memory_card') => void; onReject: () => void }) {
  const continuity = response.continuity;
  const continuityRows = ['hook', 'conflict', 'reversal', 'payoff', 'open_loop'].filter((key) => continuity[key]);
  return <article className="border border-primary/30 bg-primary/5 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2 text-sm font-medium"><GitBranch className="h-4 w-4" /> Draft · nhánh {response.branch_name}</div><Badge variant="outline">{promoted ? 'Đã đưa vào memory' : 'Chưa vào memory'}</Badge></div><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{response.draft}</p>{continuityRows.length > 0 && <div className="mt-4 grid gap-2 border-t border-primary/20 pt-3 sm:grid-cols-2">{continuityRows.map((key) => <div key={key}><p className="text-xs font-medium uppercase text-muted-foreground">{key === 'open_loop' ? 'Câu hỏi mở' : key}</p><p className="mt-1 text-sm leading-5">{String(continuity[key])}</p></div>)}</div>}<div className="mt-4 flex flex-wrap gap-2 border-t border-primary/20 pt-3">{promoted ? <p className="text-sm text-muted-foreground">Draft này đã được duyệt. Tạo draft mới nếu bạn muốn promotion theo loại khác.</p> : <><Button size="sm" variant="outline" disabled={approving} onClick={() => onApprove('idea')}><Check className="mr-1.5 h-4 w-4" /> Duyệt thành ý tưởng</Button><Button size="sm" variant="outline" disabled={approving} onClick={() => onApprove('script')}><Check className="mr-1.5 h-4 w-4" /> Duyệt script seed</Button><Button size="sm" variant="outline" disabled={approving} onClick={() => onApprove('memory_card')}><Check className="mr-1.5 h-4 w-4" /> Duyệt memory card</Button><Button size="sm" variant="ghost" disabled={rejecting} onClick={onReject}><Undo2 className="mr-1.5 h-4 w-4" /> Bỏ qua</Button></>}</div></article>;
}
