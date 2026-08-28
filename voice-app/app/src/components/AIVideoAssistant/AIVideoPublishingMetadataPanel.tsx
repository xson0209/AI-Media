import { AlertCircle, Check, Copy, Download, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import type {
  VideoPublishingMetadataResponse,
  VideoPublishingPlatform,
} from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';

const PLATFORM_TABS: Array<{ key: VideoPublishingPlatform; label: string }> = [
  { key: 'youtube', label: 'YouTube' },
  { key: 'tiktok', label: 'TikTok' },
  { key: 'facebook', label: 'Facebook' },
];

const FIELD_LABELS = {
  title: 'Tiêu đề video',
  description: 'Mô tả',
  hashtags: 'Hashtag',
  thumbnail_prompt: 'Prompt tạo ảnh thumbnail',
} as const;

/** Gộp toàn bộ nội dung đăng của cả 3 nền tảng thành một khối text phẳng để copy hoặc xuất .txt. */
function allPlatformsText(metadata: VideoPublishingMetadataResponse | null | undefined): string {
  if (!metadata?.platforms) return '';
  const blocks: string[] = [];
  for (const tab of PLATFORM_TABS) {
    const content = metadata.platforms[tab.key];
    if (!content) continue;
    const lines = [
      `===== ${tab.label.toUpperCase()} =====`,
      '',
      `${FIELD_LABELS.title}:`,
      content.title?.trim() || '(chưa có)',
      '',
      `${FIELD_LABELS.description}:`,
      content.description?.trim() || '(chưa có)',
      '',
      `${FIELD_LABELS.hashtags}:`,
      (content.hashtags ?? []).join(' ').trim() || '(chưa có)',
      '',
      `${FIELD_LABELS.thumbnail_prompt}:`,
      content.thumbnail_prompt?.trim() || '(chưa có)',
    ];
    blocks.push(lines.join('\n'));
  }
  return blocks.join('\n\n');
}

function statusText(metadata: VideoPublishingMetadataResponse | null | undefined): string {
  if (!metadata || metadata.status === 'missing') return 'Chưa có nội dung đăng';
  if (metadata.status === 'generating') return 'Đang tạo nội dung đăng';
  if (metadata.stale || metadata.status === 'stale') return 'Nội dung cần tạo lại';
  if (metadata.status === 'failed') return 'Tạo nội dung đăng thất bại';
  if (metadata.status === 'completed') return 'Nội dung đăng đã sẵn sàng';
  return metadata.status;
}

async function writeClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!ok) throw new Error('Clipboard rejected');
}

interface CopyFieldProps {
  fieldKey: string;
  label: string;
  value: string;
  copiedKey: string | null;
  failedKey: string | null;
  onCopy: (fieldKey: string, value: string) => void;
  multiline?: boolean;
}

function CopyField({
  fieldKey,
  label,
  value,
  copiedKey,
  failedKey,
  onCopy,
  multiline = true,
}: CopyFieldProps) {
  const copyLabel = `Copy ${label}`;
  return (
    <div className="rounded-lg border border-border/70 bg-background/70 p-3">
      <div className="flex min-h-10 items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          {copiedKey === fieldKey ? (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-300">
              <Check className="h-3.5 w-3.5" />
              Đã copy
            </p>
          ) : failedKey === fieldKey ? (
            <p className="mt-1 text-xs text-destructive">Không thể copy tự động</p>
          ) : null}
        </div>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-10 w-10 shrink-0"
          title={copyLabel}
          aria-label={copyLabel}
          disabled={!value.trim()}
          onClick={() => onCopy(fieldKey, value)}
        >
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      <textarea
        readOnly
        value={value}
        rows={multiline ? 5 : 2}
        className={cn(
          'mt-2 w-full resize-none rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm leading-relaxed text-foreground outline-none',
          multiline ? 'h-36' : 'h-20',
        )}
      />
    </div>
  );
}

interface AIVideoPublishingMetadataPanelProps {
  metadata: VideoPublishingMetadataResponse | null | undefined;
  isLoading: boolean;
  isGenerating: boolean;
  disabled: boolean;
  /** Lý do nút tạo đang bị chặn, hiển thị để người dùng biết cần làm gì trước. */
  disabledReason?: string | null;
  /** Cảnh báo chất lượng: vẫn tạo được, chỉ nhắc nội dung có thể chưa tối ưu. */
  warning?: string | null;
  projectTitle?: string | null;
  onGenerateAll: () => void;
  onGeneratePlatform: (platform: VideoPublishingPlatform) => void;
}

export function AIVideoPublishingMetadataPanel({
  metadata,
  isLoading,
  isGenerating,
  disabled,
  disabledReason,
  warning,
  projectTitle,
  onGenerateAll,
  onGeneratePlatform,
}: AIVideoPublishingMetadataPanelProps) {
  const platformBridge = usePlatform();
  const [activePlatform, setActivePlatform] = useState<VideoPublishingPlatform>('youtube');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [exportState, setExportState] = useState<'idle' | 'done' | 'failed'>('idle');

  const platform = metadata?.platforms?.[activePlatform];
  const fields = useMemo(
    () => [
      {
        key: `${activePlatform}:title`,
        label: 'Tiêu đề video',
        value: platform?.title ?? '',
        multiline: false,
      },
      {
        key: `${activePlatform}:description`,
        label: 'Mô tả',
        value: platform?.description ?? '',
        multiline: true,
      },
      {
        key: `${activePlatform}:hashtags`,
        label: 'Hashtag',
        value: (platform?.hashtags ?? []).join(' '),
        multiline: false,
      },
      {
        key: `${activePlatform}:thumbnail_prompt`,
        label: 'Prompt tạo ảnh thumbnail',
        value: platform?.thumbnail_prompt ?? '',
        multiline: true,
      },
    ],
    [activePlatform, platform],
  );

  const hasAnyPlatform = PLATFORM_TABS.some((tab) => metadata?.platforms?.[tab.key]);
  const canGenerate = !disabled && !isGenerating;
  const combinedText = useMemo(() => allPlatformsText(metadata), [metadata]);
  const hasCombinedText = !!combinedText.trim();

  const handleCopy = async (fieldKey: string, value: string) => {
    try {
      await writeClipboard(value);
      setCopiedKey(fieldKey);
      setFailedKey(null);
      window.setTimeout(() => setCopiedKey((current) => (current === fieldKey ? null : current)), 1800);
    } catch {
      setFailedKey(fieldKey);
      setCopiedKey(null);
    }
  };

  const handleExportTxt = async () => {
    const slug = (projectTitle ?? 'noi-dung-dang-video')
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .toLowerCase();
    const filename = `${slug || 'noi-dung-dang-video'}-noi-dung-dang.txt`;
    try {
      await platformBridge.filesystem.saveFile(
        filename,
        new Blob([combinedText], { type: 'text/plain;charset=utf-8' }),
        [{ name: 'Nội dung đăng video', extensions: ['txt'] }],
      );
      setExportState('done');
      window.setTimeout(() => setExportState((current) => (current === 'done' ? 'idle' : current)), 1800);
    } catch {
      setExportState('failed');
    }
  };

  return (
    <section className="rounded-lg border border-border/80 bg-card/40 p-5">
      <div className="flex flex-col gap-3 border-b border-border/70 pb-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold">Nội dung đăng video</h2>
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
                metadata?.status === 'completed' && !metadata.stale
                  ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : null,
                metadata?.stale || metadata?.status === 'stale'
                  ? 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-200'
                  : null,
                metadata?.status === 'failed'
                  ? 'border-destructive/25 bg-destructive/10 text-destructive'
                  : null,
                !metadata || metadata.status === 'missing'
                  ? 'border-border bg-muted/30 text-muted-foreground'
                  : null,
              )}
            >
              {isLoading || isGenerating ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              {statusText(metadata)}
            </span>
          </div>
          {metadata?.stale || metadata?.status === 'stale' ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-amber-700 dark:text-amber-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              Nội dung cũ vẫn copy được nhưng có thể không còn khớp video hiện tại.
            </p>
          ) : metadata?.status === 'failed' && metadata.failure_reason ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {metadata.failure_reason}
            </p>
          ) : null}
          {disabled && disabledReason ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {disabledReason}
            </p>
          ) : warning ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {warning}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant={hasAnyPlatform ? 'outline' : 'default'}
            disabled={!canGenerate}
            title={disabled && disabledReason ? disabledReason : undefined}
            onClick={onGenerateAll}
          >
            {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {hasAnyPlatform ? 'Tạo lại tất cả' : 'Tạo nội dung đăng video'}
          </Button>
          {hasAnyPlatform ? (
            <Button
              type="button"
              variant="outline"
              disabled={!canGenerate}
              title={disabled && disabledReason ? disabledReason : undefined}
              onClick={() => onGeneratePlatform(activePlatform)}
            >
              <RefreshCw className="h-4 w-4" />
              Tạo lại nền tảng này
            </Button>
          ) : null}
        </div>
      </div>

      {hasCombinedText ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-background/50 p-3">
          <p className="mr-auto text-xs text-muted-foreground">
            Lấy toàn bộ nội dung đăng của cả 3 nền tảng trong một lần.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleCopy('all-platforms', combinedText)}
          >
            {copiedKey === 'all-platforms' ? (
              <Check className="h-4 w-4" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
            Copy tất cả
          </Button>
          <Button type="button" variant="outline" onClick={() => void handleExportTxt()}>
            {exportState === 'done' ? (
              <Check className="h-4 w-4" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Xuất .txt
          </Button>
          {failedKey === 'all-platforms' ? (
            <p className="w-full text-xs text-destructive">Không thể copy tự động.</p>
          ) : null}
          {exportState === 'failed' ? (
            <p className="w-full text-xs text-destructive">Không xuất được file .txt.</p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Nền tảng đăng video">
        {PLATFORM_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activePlatform === tab.key}
            className={cn(
              'min-h-10 rounded-md border px-3 py-2 text-sm font-medium transition-colors',
              activePlatform === tab.key
                ? 'border-accent/45 bg-accent/10 text-foreground'
                : 'border-border bg-background/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground',
            )}
            onClick={() => setActivePlatform(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {fields.map((field) => (
          <CopyField
            key={field.key}
            fieldKey={field.key}
            label={field.label}
            value={field.value}
            copiedKey={copiedKey}
            failedKey={failedKey}
            onCopy={handleCopy}
            multiline={field.multiline}
          />
        ))}
      </div>
    </section>
  );
}
