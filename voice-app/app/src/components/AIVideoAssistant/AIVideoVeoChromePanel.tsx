import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  Check,
  Chrome,
  Loader2,
  Pencil,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  StopCircle,
  UserRoundCheck,
  Video,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import type {
  VideoClipGenerationItemResponse,
  VideoClipGenerationJobResponse,
  VideoProviderSessionResponse,
  VideoShotClipResponse,
  VideoShotResponse,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

interface AIVideoVeoChromePanelProps {
  projectId: string | null | undefined;
  shots: VideoShotResponse[];
  onNotice: (message: string) => void;
}

type CreditPolicy = 'approve_dont_ask_again' | 'manual_per_item';

const ACTIVE_JOB_STATUSES = new Set([
  'queued',
  'running',
  'needs_login',
  'needs_user_action',
  'needs_credit_approval',
]);

const BLOCKING_IDENTITY = new Set(['unknown', 'mismatch', 'needs_user_action']);
const panelButtonClass = 'h-auto min-h-10 w-full justify-start whitespace-normal px-3 py-2 text-left leading-snug';
const panelCardClass = 'rounded-lg border border-border/75 bg-background/70 p-3';

function statusTone(ok: boolean) {
  return ok
    ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200';
}

function dangerTone() {
  return 'border-destructive/30 bg-destructive/10 text-destructive';
}

function formatDateTime(value?: string | null): string {
  if (!value) return 'chưa xác minh';
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function shotLabel(shot: VideoShotResponse): string {
  return `Segment ${String(shot.shot_order).padStart(2, '0')}`;
}

function sessionStatusText(session?: VideoProviderSessionResponse | null): string {
  if (!session) return 'Chưa cấu hình phiên Veo3/Chrome.';
  if (session.status === 'ready') return 'Phiên Chrome/Veo3 đã sẵn sàng.';
  if (session.status === 'checking') return 'Đang kiểm tra phiên Chrome/Veo3.';
  if (session.status === 'needs_login') return 'Cần đăng nhập hoặc xác minh lại Google/Veo3.';
  if (session.status === 'invalid') return 'Phiên Chrome/Veo3 đang lỗi.';
  return 'Chưa cấu hình phiên Veo3/Chrome.';
}

function identityText(session?: VideoProviderSessionResponse | null): string {
  if (!session) return 'Chưa có định danh tài khoản.';
  if (session.identity_status === 'confirmed') return 'Tài khoản đã được xác nhận.';
  if (session.identity_status === 'detected') return 'Đã phát hiện tài khoản, nên xác nhận trước khi chạy.';
  if (session.identity_status === 'mismatch') return 'Tài khoản Google có thể đã thay đổi.';
  return 'Chưa xác định tài khoản, cần đặt nhãn và xác nhận.';
}

function jobStatusText(job?: VideoClipGenerationJobResponse | null): string {
  if (!job) return 'Chưa có job tạo clip Veo.';
  if (job.status === 'queued') return 'Đang chờ chạy job Veo.';
  if (job.status === 'running') return job.current_step || 'Đang tạo clip bằng Veo.';
  if (job.status === 'needs_login') return 'Cần đăng nhập lại Google/Veo3 rồi resume job.';
  if (job.status === 'needs_credit_approval') return 'Flow đang chờ phê duyệt credit.';
  if (job.status === 'completed') return 'Đã tạo/import clip Veo xong.';
  if (job.status === 'completed_with_render_blocked') return 'Clip đã xong nhưng render MP4 còn thiếu điều kiện.';
  if (job.status === 'cancelled') return 'Job tạo clip đã hủy.';
  if (job.status === 'failed') return 'Job tạo clip bị lỗi.';
  return job.current_step || job.status;
}

function itemStatusText(item?: VideoClipGenerationItemResponse, clip?: VideoShotClipResponse | null): string {
  if (item?.status === 'completed') return 'Đã import clip Veo';
  if (item?.status === 'skipped') return 'Đã có clip Veo';
  if (item?.status === 'opening_provider') return 'Đang mở Veo';
  if (item?.status === 'submitting_prompt') return 'Đang gửi prompt';
  if (item?.status === 'resolving_followup') return 'Đang chọn duration';
  if (item?.status === 'credit_policy_check' || item?.status === 'approving_credit') return 'Đang xử lý credit';
  if (item?.status === 'waiting_generation') return 'Đang chờ Veo tạo clip';
  if (item?.status === 'downloading') return 'Đang tải clip';
  if (item?.status === 'importing') return 'Đang import clip';
  if (item?.status === 'needs_login') return 'Cần đăng nhập lại';
  if (item?.status === 'needs_credit_approval') return 'Cần phê duyệt credit';
  if (item?.status === 'failed') return 'Lỗi tạo clip';
  if (item?.status === 'cancelled') return 'Đã hủy';
  if (clip?.source === 'provider' && clip.status === 'ready') return 'Đã có clip Veo';
  if (clip?.status === 'ready') return 'Đã có clip thủ công';
  return 'Chờ tạo clip';
}

function sessionCanRun(session?: VideoProviderSessionResponse | null): boolean {
  return !!session && session.status === 'ready' && !BLOCKING_IDENTITY.has(session.identity_status);
}

export function AIVideoVeoChromePanel({ projectId, shots, onNotice }: AIVideoVeoChromePanelProps) {
  const queryClient = useQueryClient();
  const [force, setForce] = useState(false);
  const [autoRender, setAutoRender] = useState(true);
  const [creditPolicy, setCreditPolicy] = useState<CreditPolicy>('approve_dont_ask_again');
  const [maxCredit, setMaxCredit] = useState('');
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState('');

  const sessionQuery = useQuery({
    queryKey: ['ai-video', 'veo-session-default'],
    queryFn: () => apiClient.getDefaultVeoProviderSession(),
    retry: false,
  });

  const latestJobQuery = useQuery({
    queryKey: ['ai-video', 'clip-generation-job-latest', projectId],
    queryFn: () => apiClient.getLatestVideoClipGenerationJob(projectId!),
    enabled: !!projectId,
    retry: false,
    refetchInterval: (query) => {
      const job = query.state.data;
      const status = job?.status;
      if (status && ACTIVE_JOB_STATUSES.has(status)) return 2500;
      if (status === 'completed' && job?.auto_render && !job.render_job_id) return 2500;
      return false;
    },
  });

  const clipQueries = useQueries({
    queries: shots.map((shot) => ({
      queryKey: ['ai-video', 'shot-clip', projectId, shot.id],
      queryFn: () => apiClient.getVideoShotClip(projectId!, shot.id),
      enabled: !!projectId && shots.length > 0,
      retry: false,
    })),
  });

  const session = sessionQuery.data;
  const latestJob = latestJobQuery.data;
  const latestJobRenderJobId = latestJob?.render_job_id;
  const latestJobStatus = latestJob?.status;
  const activeJob = !!latestJob && ACTIVE_JOB_STATUSES.has(latestJob.status);

  useEffect(() => {
    if (session?.connection_label && !editingLabel) {
      setLabelDraft(session.connection_label);
    }
  }, [editingLabel, session?.connection_label]);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'veo-session-default'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'clip-generation-job-latest', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'shot-clip'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render'] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-job-latest', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ai-video', 'debug', projectId] });
  };

  useEffect(() => {
    if (!projectId) return;
    if (latestJobRenderJobId || latestJobStatus === 'completed_with_render_blocked') {
      queryClient.invalidateQueries({ queryKey: ['ai-video', 'render'] });
      queryClient.invalidateQueries({ queryKey: ['ai-video', 'render-job-latest', projectId] });
      queryClient.invalidateQueries({ queryKey: ['ai-video', 'debug', projectId] });
    }
  }, [latestJobRenderJobId, latestJobStatus, projectId, queryClient]);

  const openLogin = useMutation({
    mutationFn: () => apiClient.openVeoProviderLogin({ provider: 'veo' }),
    onSuccess: () => {
      onNotice('Đã mở Chrome profile riêng để đăng nhập Google/Veo3.');
      invalidateAll();
    },
  });

  const checkSession = useMutation({
    mutationFn: () => apiClient.checkVeoProviderSession(),
    onSuccess: () => {
      onNotice('Đã kiểm tra phiên Veo3/Chrome.');
      invalidateAll();
    },
  });

  const changeAccount = useMutation({
    mutationFn: (sessionId: string) => apiClient.changeVeoProviderAccount(sessionId),
    onSuccess: () => {
      onNotice('Đã mở Chrome để đổi tài khoản Google cho Veo3.');
      invalidateAll();
    },
  });

  const saveLabel = useMutation({
    mutationFn: () =>
      apiClient.updateVeoProviderSessionLabel(session!.id, {
        connection_label: labelDraft.trim(),
      }),
    onSuccess: () => {
      setEditingLabel(false);
      onNotice('Đã lưu nhãn kết nối Veo3.');
      invalidateAll();
    },
  });

  const confirmIdentity = useMutation({
    mutationFn: () => apiClient.confirmVeoProviderSessionIdentity(session!.id),
    onSuccess: () => {
      onNotice('Đã xác nhận tài khoản Veo3 đang dùng.');
      invalidateAll();
    },
  });

  const startJob = useMutation({
    mutationFn: () =>
      apiClient.startVideoClipGenerationJob(projectId!, {
        session_id: session?.id,
        force,
        auto_render: autoRender,
        credit_approval_policy: creditPolicy,
        max_credit_per_job: maxCredit.trim() ? Number(maxCredit) : null,
      }),
    onSuccess: () => {
      onNotice('Đã bắt đầu tạo clip bằng Veo. Chrome sẽ dùng profile đã đăng nhập.');
      invalidateAll();
    },
  });

  const retryJob = useMutation({
    mutationFn: () => apiClient.retryVideoClipGenerationJob(projectId!, latestJob!.id, { force }),
    onSuccess: () => {
      onNotice('Đã retry job tạo clip Veo.');
      invalidateAll();
    },
  });

  const resumeJob = useMutation({
    mutationFn: () => apiClient.resumeVideoClipGenerationJob(projectId!, latestJob!.id, {}),
    onSuccess: () => {
      onNotice('Đã resume job tạo clip Veo.');
      invalidateAll();
    },
  });

  const cancelJob = useMutation({
    mutationFn: () => apiClient.cancelVideoClipGenerationJob(projectId!, latestJob!.id),
    onSuccess: () => {
      onNotice('Đã hủy job tạo clip Veo.');
      invalidateAll();
    },
  });

  const approveCredit = useMutation({
    mutationFn: (itemId: string) =>
      apiClient.approveVideoClipGenerationCredit(projectId!, latestJob!.id, itemId, { approve: true }),
    onSuccess: () => {
      onNotice('Đã phê duyệt credit cho item hiện tại.');
      invalidateAll();
    },
  });

  const itemByShotId = useMemo(() => {
    const map = new Map<string, VideoClipGenerationItemResponse>();
    for (const item of latestJob?.items || []) {
      map.set(item.shot_id, item);
    }
    return map;
  }, [latestJob?.items]);

  const missingPromptShots = shots.filter((shot) => shot.prompt_status !== 'completed');
  const canRun = !!projectId && shots.length > 0 && sessionCanRun(session) && missingPromptShots.length === 0 && !activeJob;
  const operationError =
    openLogin.error ||
    checkSession.error ||
    changeAccount.error ||
    saveLabel.error ||
    confirmIdentity.error ||
    startJob.error ||
    retryJob.error ||
    resumeJob.error ||
    cancelJob.error ||
    approveCredit.error;

  return (
    <section className="overflow-hidden rounded-lg border border-border/80 bg-card/60 p-4">
      <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background">
            <Chrome className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight">Veo3 qua Chrome</h2>
            <p className="truncate text-xs text-muted-foreground">Đăng nhập một lần, dùng lại Chrome profile riêng</p>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {!projectId ? (
          <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
            Chọn hoặc tạo project phase 2 để tạo clip bằng Veo.
          </div>
        ) : null}

        <div
          className={cn(
            'rounded-lg border p-3 text-sm',
            sessionCanRun(session) ? statusTone(true) : session?.identity_status === 'mismatch' ? dangerTone() : statusTone(false),
          )}
        >
          <div className="flex items-start gap-2">
            {sessionCanRun(session) ? <ShieldCheck className="mt-0.5 h-4 w-4" /> : <AlertCircle className="mt-0.5 h-4 w-4" />}
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {sessionCanRun(session) ? `Đang dùng: ${session?.connection_label || 'Veo3 Flow'}` : sessionStatusText(session)}
              </p>
              <p className="mt-1 break-words text-xs leading-relaxed opacity-85">
                {session?.provider_tool || 'veo3_flow'} · {session?.verified_account_hint || 'chưa đọc được account hint'} · {identityText(session)}
              </p>
              <p className="mt-1 text-xs opacity-75">Xác minh gần nhất: {formatDateTime(session?.identity_verified_at || session?.last_checked_at)}</p>
              {session?.failure_reason ? <p className="mt-2 text-xs leading-relaxed">{session.failure_reason}</p> : null}
            </div>
          </div>
        </div>

        <div className="grid gap-2">
          {!sessionCanRun(session) ? (
            <Button className={panelButtonClass} disabled={openLogin.isPending} onClick={() => openLogin.mutate()}>
              {openLogin.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Chrome className="h-4 w-4" />}
              Đăng nhập Google kết nối Veo3
            </Button>
          ) : null}
          {session ? (
            <Button className={panelButtonClass} variant="outline" disabled={checkSession.isPending} onClick={() => checkSession.mutate()}>
              {checkSession.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Kiểm tra phiên
            </Button>
          ) : null}
          {session ? (
            <Button className={panelButtonClass} variant="outline" disabled={changeAccount.isPending} onClick={() => changeAccount.mutate(session.id)}>
              {changeAccount.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserRoundCheck className="h-4 w-4" />}
              Đổi tài khoản
            </Button>
          ) : null}
        </div>

        {session ? (
          <div className={panelCardClass}>
            <div className="grid gap-3">
              <label className="grid flex-1 gap-2 text-sm font-medium">
                <span>Nhãn kết nối</span>
                <input
                  value={labelDraft}
                  disabled={!editingLabel}
                  onChange={(event) => setLabelDraft(event.target.value)}
                  className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10 disabled:opacity-75"
                  placeholder="Veo3 - Gmail chính"
                />
              </label>
              <div className="grid gap-2">
                {editingLabel ? (
                  <Button className={panelButtonClass} disabled={!labelDraft.trim() || saveLabel.isPending} onClick={() => saveLabel.mutate()}>
                    {saveLabel.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    Lưu nhãn
                  </Button>
                ) : (
                  <Button className={panelButtonClass} variant="outline" onClick={() => setEditingLabel(true)}>
                    <Pencil className="h-4 w-4" />
                    Sửa nhãn
                  </Button>
                )}
                {BLOCKING_IDENTITY.has(session.identity_status) ? (
                  <Button className={panelButtonClass} disabled={!labelDraft.trim() || confirmIdentity.isPending} onClick={() => confirmIdentity.mutate()}>
                    {confirmIdentity.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                    Xác nhận dùng tài khoản này
                  </Button>
                ) : (
                  <Button className={panelButtonClass} variant="outline" disabled>
                    <ShieldCheck className="h-4 w-4" />
                    Đã xác nhận
                  </Button>
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div className={cn('grid gap-3', panelCardClass)}>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Video className="h-4 w-4" />
            Tạo clip tự động
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Gửi từng prompt sang Veo, tải clip về đúng segment rồi import vào project.
          </p>
          <div className="grid gap-3">
            <label className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-lg border border-border/75 px-3 py-2 text-sm">
              <input className="mt-1" type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              <span className="min-w-0">
                <span className="block font-medium">Tạo lại clip đã có</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                  Tắt mục này để bỏ qua segment đã có clip Veo và tránh tốn credit không cần thiết.
                </span>
              </span>
            </label>
            <label className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-lg border border-border/75 px-3 py-2 text-sm">
              <input className="mt-1" type="checkbox" checked={autoRender} onChange={(event) => setAutoRender(event.target.checked)} />
              <span className="min-w-0">
                <span className="block font-medium">Tự dựng MP4 sau khi đủ clip</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                  Bật để hệ thống tự chuyển sang render MP4 khi mọi segment đã có clip, voice và phụ đề hợp lệ.
                </span>
              </span>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              <span>Chính sách credit</span>
              <select
                value={creditPolicy}
                onChange={(event) => setCreditPolicy(event.target.value as CreditPolicy)}
                className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
              >
                <option value="approve_dont_ask_again">Phê duyệt, không hỏi lại</option>
                <option value="manual_per_item">Phê duyệt thủ công từng lần</option>
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              <span>Giới hạn credit mỗi job</span>
              <input
                value={maxCredit}
                onChange={(event) => setMaxCredit(event.target.value.replace(/[^\d]/g, ''))}
                className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-2 focus:ring-foreground/10"
                placeholder="Để trống nếu không giới hạn"
              />
            </label>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Mặc định Flow sẽ dùng “Phê duyệt, không hỏi lại” trong job do bạn khởi chạy, nhưng vẫn dừng nếu vượt giới hạn credit hoặc cần xác minh tài khoản.
          </p>
          {missingPromptShots.length > 0 ? (
            <div className={cn('rounded-lg border p-3 text-xs leading-relaxed', statusTone(false))}>
              Thiếu prompt video completed cho {missingPromptShots.length} segment. Hãy tạo prompt video trước khi chạy Veo.
            </div>
          ) : null}
          <Button className={panelButtonClass} disabled={!canRun || startJob.isPending} onClick={() => startJob.mutate()}>
            {startJob.isPending || activeJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Tạo clip bằng Veo
          </Button>
        </div>

        <div className="space-y-3">
          {shots.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
              Chưa có segment để tạo clip.
            </div>
          ) : (
            shots.map((shot, index) => {
              const clip = clipQueries[index]?.data;
              const item = itemByShotId.get(shot.id);
              const ok = item?.status === 'completed' || item?.status === 'skipped' || clip?.status === 'ready';
              return (
                <div key={shot.id} className={panelCardClass}>
                  <div className="flex flex-col gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold">{shotLabel(shot)}</p>
                        <span className={cn('rounded-full border px-2 py-0.5 text-xs', statusTone(ok))}>
                          {shot.prompt_status !== 'completed' ? 'thiếu prompt' : itemStatusText(item, clip)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        Prompt: {shot.prompt_status === 'completed' ? 'đã có' : 'chưa sẵn sàng'} · Clip: {clip?.status === 'ready' ? clip.original_filename || 'đã có file' : 'chưa có'}
                      </p>
                      {item?.failure_reason ? <p className="mt-1 text-xs leading-relaxed text-destructive">{item.failure_reason}</p> : null}
                    </div>
                    {item?.credit_cost ? (
                      <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                        {item.credit_cost} credit
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {latestJob ? (
          <div className={panelCardClass}>
            <div className="flex flex-col gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold">Job Veo gần nhất</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{jobStatusText(latestJob)}</p>
                {latestJob.failure_reason ? <p className="mt-1 text-xs leading-relaxed text-destructive">{latestJob.failure_reason}</p> : null}
              </div>
              <span className="w-fit rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {Math.round((latestJob.progress || 0) * 100)}%
              </span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-emerald-600 transition-[width] duration-300" style={{ width: `${Math.round((latestJob.progress || 0) * 100)}%` }} />
            </div>
            <div className="mt-3 grid gap-2">
              {latestJob.status === 'needs_login' || latestJob.status === 'needs_user_action' ? (
                <Button className={panelButtonClass} variant="outline" disabled={openLogin.isPending} onClick={() => openLogin.mutate()}>
                  {openLogin.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Chrome className="h-4 w-4" />}
                  Mở Chrome đăng nhập
                </Button>
              ) : null}
              {latestJob.status === 'needs_login' || latestJob.status === 'needs_user_action' || latestJob.status === 'failed' ? (
                <Button className={panelButtonClass} variant="outline" disabled={resumeJob.isPending} onClick={() => resumeJob.mutate()}>
                  {resumeJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  Resume
                </Button>
              ) : null}
              {latestJob.status === 'failed' || latestJob.status === 'completed_with_render_blocked' ? (
                <Button className={panelButtonClass} variant="outline" disabled={retryJob.isPending} onClick={() => retryJob.mutate()}>
                  {retryJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Retry lỗi
                </Button>
              ) : null}
              {activeJob ? (
                <Button className={panelButtonClass} variant="outline" disabled={cancelJob.isPending} onClick={() => cancelJob.mutate()}>
                  {cancelJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />}
                  Hủy job
                </Button>
              ) : null}
            </div>
            {latestJob.status === 'needs_credit_approval' ? (
              <div className="mt-3 grid gap-2">
                {latestJob.items
                  .filter((item) => item.status === 'needs_credit_approval')
                  .map((item) => (
                    <Button
                      key={item.id}
                      className={panelButtonClass}
                      variant="outline"
                      disabled={approveCredit.isPending}
                      onClick={() => approveCredit.mutate(item.id)}
                    >
                      {approveCredit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                      Phê duyệt lần này cho Segment {String(item.shot_order).padStart(2, '0')}
                    </Button>
                  ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {operationError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {operationError instanceof Error ? operationError.message : 'Có lỗi không xác định.'}
          </div>
        ) : null}
      </div>
    </section>
  );
}
