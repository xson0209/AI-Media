import { AlertTriangle, Check, Copy, Download, FileText, Loader2, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ProductVideoPromptResponse, ProductVideoShotResponse } from '@/lib/api/types';

function beatLabel(role: string | null): string {
  const labels: Record<string, string> = {
    hook: 'Hook',
    problem: 'Vấn đề',
    product_reveal: 'Ra mắt sản phẩm',
    demo: 'Demo',
    proof: 'Bằng chứng',
    benefit: 'Lợi ích',
    use_case: 'Tình huống dùng',
    offer: 'Ưu đãi',
    cta: 'CTA',
    re_hook: 'Hook lại',
  };
  if (!role) return 'Chưa gán nhịp';
  return labels[role] ?? role;
}

/** Mirrors the backend blank-motion rule so the UI flags the same shots. */
function isBlankMotion(value: string | null | undefined): boolean {
  if (!value) return true;
  const token = value.trim().toLowerCase();
  return token === '' || ['none', 'n/a', 'na', 'static', 'no motion', 'không'].includes(token);
}

function motionCount(shot: ProductVideoShotResponse): number {
  return [shot.camera_motion, shot.subject_motion, shot.environment_motion].filter(
    (value) => !isBlankMotion(value),
  ).length;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      }}
    >
      {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
      {copied ? 'Đã copy' : 'Copy prompt'}
    </Button>
  );
}

export function ProductVideoPromptPanel({
  shots,
  prompts,
  isLoading,
  error,
  onRetry,
  onDownload,
  isDownloading,
}: {
  shots: ProductVideoShotResponse[];
  prompts: ProductVideoPromptResponse[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onDownload: () => void;
  isDownloading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-muted-foreground" aria-live="polite">
        <Loader2 className="h-4 w-4 animate-spin" />
        Đang sinh prompt...
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4" aria-live="assertive">
        <p className="flex items-start gap-2 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </p>
        <div>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Thử lại
          </Button>
        </div>
      </div>
    );
  }

  if (prompts.length === 0) {
    if (shots.length > 0) {
      return (
        <div className="grid gap-3">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
            <p className="text-sm font-medium">Đã lập kế hoạch {shots.length} cảnh</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Các cảnh đã sẵn sàng. Bấm <span className="font-medium text-foreground">Sinh prompt</span>{' '}
              ở phía trên để tạo prompt pack và copy sang Google Flow.
            </p>
          </div>
          <div className="grid gap-2">
            {shots.map((shot, index) => {
              const motions = motionCount(shot);
              return (
                <div
                  key={shot.id}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 p-3 text-xs"
                >
                  <Badge variant="outline">Cảnh {shot.shot_order ?? index + 1}</Badge>
                  <Badge variant="secondary">{beatLabel(shot.beat_role)}</Badge>
                  <span className="font-medium">{shot.shot_type}</span>
                  <span className="text-muted-foreground">{shot.framing}</span>
                  <span className="ml-auto text-muted-foreground">
                    {shot.duration_seconds}s · {motions}/3 chuyển động
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    return (
      <div className="grid min-h-40 place-items-center gap-2 rounded-lg border border-dashed border-border/60 p-6 text-center">
        <FileText className="h-5 w-5 text-muted-foreground" />
        <p className="text-sm font-medium">Chưa có prompt nào</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          Chạy bước lập kế hoạch cảnh trước, rồi bấm Sinh prompt. Prompt xong mới copy được sang
          Google Flow.
        </p>
      </div>
    );
  }

  const shotById = new Map(shots.map((shot) => [shot.id, shot]));

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {prompts.length} prompt — dán lần lượt vào Flow, mỗi prompt một clip.
        </p>
        <Button variant="outline" size="sm" onClick={onDownload} disabled={isDownloading}>
          {isDownloading ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Download className="mr-1.5 h-3.5 w-3.5" />
          )}
          Tải cả pack
        </Button>
      </div>

      {prompts.map((prompt, index) => {
        const shot = shotById.get(prompt.shot_id);
        const motions = shot ? motionCount(shot) : 0;
        return (
          <div key={prompt.id} className="grid gap-2 rounded-lg border border-border/60 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Clip {prompt.shot_order ?? index + 1}</Badge>
              {shot ? <Badge variant="secondary">{beatLabel(shot.beat_role)}</Badge> : null}
              {shot ? <span className="text-xs text-muted-foreground">{shot.shot_type}</span> : null}
              {shot && motions < 2 ? (
                <Badge variant="destructive" title="Prompt này thiếu nguồn chuyển động">
                  chỉ {motions}/3 chuyển động
                </Badge>
              ) : null}
              <span className="ml-auto">
                <CopyButton text={prompt.prompt} />
              </span>
            </div>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-muted/50 p-3 text-xs leading-relaxed">
              {prompt.prompt}
            </pre>
            {prompt.prompt_explanation_vi ? (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer">Giải thích tiếng Việt</summary>
                <p className="mt-1 whitespace-pre-wrap">{prompt.prompt_explanation_vi}</p>
              </details>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
