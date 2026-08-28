import {
  AlertTriangle,
  BookOpen,
  Check,
  Film,
  Image as ImageIcon,
  Layers3,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Users,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { SeriesMode, VideoSeriesCreate, VideoSeriesResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils/cn';

export type SeriesPickerContext =
  | 'ai_video_direct'
  | 'story_studio'
  | 'comic_handoff'
  | 'view_all';

export type SeriesCreateNextAction = 'select' | 'manage_characters' | 'create_episode';

export interface SeriesDraftInput extends Required<Pick<VideoSeriesCreate, 'title'>> {
  series_mode: SeriesMode;
  character_bible: string;
  world_bible: string;
  style_bible: string;
  continuity_rules: string;
  negative_rules: string;
  previous_episode_summary: string;
}

const SERIES_MODE_OPTIONS: Array<{
  mode: SeriesMode;
  label: string;
  shortLabel: string;
  description: string;
  icon: typeof ImageIcon;
}> = [
  {
    mode: 'image_story_only',
    label: 'Series truyện ảnh',
    shortLabel: 'Truyện ảnh',
    description: 'Dùng cho Story Studio và các tập truyện ảnh.',
    icon: ImageIcon,
  },
  {
    mode: 'video_story_only',
    label: 'Series video',
    shortLabel: 'Video',
    description: 'Dùng cho AI Video tạo tập video trực tiếp.',
    icon: Film,
  },
  {
    mode: 'hybrid',
    label: 'Series truyện + video',
    shortLabel: 'Truyện + video',
    description: 'Dùng cho Story Studio và handoff sang video.',
    icon: Layers3,
  },
];

const CREATE_NEXT_ACTIONS: Array<{
  action: SeriesCreateNextAction;
  label: string;
  description: string;
  icon: typeof Check;
}> = [
  {
    action: 'select',
    label: 'Chọn series này',
    description: 'Lưu xong sẽ đặt series này làm series đang chọn.',
    icon: Check,
  },
  {
    action: 'manage_characters',
    label: 'Quản lý nhân vật',
    description: 'Lưu xong sẽ mở khu hồ sơ nhân vật của series.',
    icon: Users,
  },
  {
    action: 'create_episode',
    label: 'Tạo tập mới',
    description: 'Lưu xong sẽ mở popup tạo tập cho series vừa tạo.',
    icon: Plus,
  },
];
const DEFAULT_CREATE_NEXT_ACTIONS: SeriesCreateNextAction[] = ['select'];

export function seriesModeLabel(mode: SeriesMode | null | undefined): string {
  return SERIES_MODE_OPTIONS.find((item) => item.mode === mode)?.label ?? 'Series video';
}

export function seriesModeShortLabel(mode: SeriesMode | null | undefined): string {
  return SERIES_MODE_OPTIONS.find((item) => item.mode === mode)?.shortLabel ?? 'Video';
}

export function allowedSeriesModes(context: SeriesPickerContext): SeriesMode[] {
  if (context === 'ai_video_direct') return ['video_story_only'];
  if (context === 'story_studio' || context === 'comic_handoff') {
    return ['image_story_only', 'hybrid'];
  }
  return ['image_story_only', 'video_story_only', 'hybrid'];
}

export function seriesCompatibilityReason(
  series: Pick<VideoSeriesResponse, 'series_mode'>,
  context: SeriesPickerContext,
): string | null {
  if (allowedSeriesModes(context).includes(series.series_mode)) return null;
  if (context === 'ai_video_direct') {
    return 'AI Video trực tiếp chỉ tạo tập từ series video. Series truyện ảnh/hybrid nên đi qua Story Studio.';
  }
  if (context === 'story_studio') {
    return 'Story Studio chỉ dùng series truyện ảnh hoặc truyện + video.';
  }
  if (context === 'comic_handoff') {
    return 'Handoff truyện tranh không dùng series video-only để tránh sai luồng.';
  }
  return null;
}

export function defaultSeriesModeForContext(context: SeriesPickerContext): SeriesMode {
  return allowedSeriesModes(context)[0] ?? 'video_story_only';
}

function contextLabel(context: SeriesPickerContext): string {
  if (context === 'ai_video_direct') return 'AI Video trực tiếp';
  if (context === 'story_studio') return 'Story Studio';
  if (context === 'comic_handoff') return 'Handoff truyện tranh';
  return 'Quản lý series';
}

function contextUsageText(context: SeriesPickerContext, mode: SeriesMode): string {
  const compatible = allowedSeriesModes(context).includes(mode);
  if (compatible && mode === 'video_story_only') return 'Dùng được trong AI Video trực tiếp.';
  if (compatible && mode === 'image_story_only') return 'Dùng được trong Story Studio và handoff truyện tranh.';
  if (compatible && mode === 'hybrid') return 'Dùng được trong Story Studio, truyện ảnh và handoff sang video.';
  return seriesCompatibilityReason({ series_mode: mode }, context) ?? 'Có thể xem trong quản lý series.';
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'Chưa rõ';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function compactText(value: string | null | undefined, empty = 'Chưa có nội dung'): string {
  const text = (value ?? '').trim().replace(/\s+/g, ' ');
  if (!text) return empty;
  return text.length > 150 ? `${text.slice(0, 150).trim()}...` : text;
}

function providerBindingLabel(series: VideoSeriesResponse): string {
  const binding = series.provider_project_binding;
  if (!binding) return 'Chưa gắn provider';
  const status =
    binding.status === 'active'
      ? 'đang hoạt động'
      : binding.status === 'needs_check'
        ? 'cần kiểm tra'
        : binding.status === 'invalid'
          ? 'không hợp lệ'
          : binding.status === 'rotated'
            ? 'đã xoay khóa'
            : binding.status;
  return `${binding.provider} · ${status}`;
}

function searchHaystack(series: VideoSeriesResponse): string {
  return [
    series.title,
    seriesModeLabel(series.series_mode),
    series.character_bible,
    series.world_bible,
    series.style_bible,
    series.continuity_rules,
    series.negative_rules,
    series.previous_episode_summary,
  ]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('vi-VN');
}

function SeriesPreviewLines({ series }: { series: VideoSeriesResponse }) {
  const previewItems = [
    ['Nhân vật', series.character_bible],
    ['World', series.world_bible],
    ['Style', series.style_bible],
    ['Nhất quán', series.continuity_rules],
    ['Cần tránh', series.negative_rules],
    ['Tập trước', series.previous_episode_summary],
  ] as const;
  return (
    <div className="grid gap-1.5 text-xs leading-5 text-muted-foreground">
      {previewItems.map(([label, value]) => (
        <p key={label} className="min-w-0">
          <span className="font-medium text-foreground">{label}: </span>
          <span>{compactText(value)}</span>
        </p>
      ))}
    </div>
  );
}

function SeriesSummaryStats({ series }: { series: VideoSeriesResponse }) {
  const stats = [
    ['Tập', series.episode_count ?? 0],
    ['Truyện', series.story_episode_count ?? 0],
    ['Video', series.video_episode_count ?? 0],
    ['Nhân vật', series.character_profiles?.length ?? 0],
  ] as const;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {stats.map(([label, value]) => (
        <div key={label} className="rounded-md border border-border/70 bg-background/70 px-2 py-1.5">
          <p className="text-[11px] text-muted-foreground">{label}</p>
          <p className="text-sm font-semibold tabular-nums">{value}</p>
        </div>
      ))}
    </div>
  );
}

export function SeriesPickerDialog({
  open,
  onOpenChange,
  context,
  series,
  selectedSeriesId,
  loading,
  error,
  onSelect,
  onCreateNew,
  disabled,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  context: SeriesPickerContext;
  series: VideoSeriesResponse[];
  selectedSeriesId?: string | null;
  loading?: boolean;
  error?: string | null;
  onSelect: (series: VideoSeriesResponse) => void;
  onCreateNew?: () => void;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [modeFilter, setModeFilter] = useState<SeriesMode | 'all'>('all');
  const normalizedQuery = query.trim().toLocaleLowerCase('vi-VN');
  const allowedModes = allowedSeriesModes(context);
  const filteredSeries = useMemo(() => {
    return series.filter((item) => {
      const matchesQuery = !normalizedQuery || searchHaystack(item).includes(normalizedQuery);
      const matchesMode = modeFilter === 'all' || item.series_mode === modeFilter;
      return matchesQuery && matchesMode;
    });
  }, [modeFilter, normalizedQuery, series]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Chọn series</DialogTitle>
          <DialogDescription>
            {contextLabel(context)} · series không phù hợp sẽ bị khóa kèm lý do.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">Tìm kiếm</span>
              <span className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none focus:border-foreground/40"
                  placeholder="Tìm theo tên, Bible, nhân vật, world hoặc style"
                />
              </span>
            </label>
            <div className="grid gap-1.5 text-sm">
              <span className="font-medium">Lọc loại</span>
              <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Lọc loại series">
                <button
                  type="button"
                  aria-pressed={modeFilter === 'all'}
                  onClick={() => setModeFilter('all')}
                  className={cn(
                    'h-10 rounded-md border px-3 text-sm transition',
                    modeFilter === 'all'
                      ? 'border-foreground/40 bg-foreground text-background'
                      : 'border-border bg-background hover:bg-muted/50',
                  )}
                >
                  Tất cả
                </button>
                {SERIES_MODE_OPTIONS.map((item) => (
                  <button
                    key={item.mode}
                    type="button"
                    aria-pressed={modeFilter === item.mode}
                    onClick={() => setModeFilter(item.mode)}
                    className={cn(
                      'h-10 rounded-md border px-3 text-sm transition',
                      modeFilter === item.mode
                        ? 'border-foreground/40 bg-foreground text-background'
                        : 'border-border bg-background hover:bg-muted/50',
                    )}
                  >
                    {item.shortLabel}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-md border border-border/70 bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
            Loại dùng được trong ngữ cảnh này: {allowedModes.map(seriesModeShortLabel).join(', ')}.
          </div>

          {error ? (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : loading ? (
            <div className="flex items-center gap-2 rounded-md border border-border/70 bg-muted/30 p-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Đang tải danh sách series...
            </div>
          ) : !filteredSeries.length ? (
            <div className="rounded-md border border-dashed border-border p-8 text-sm text-muted-foreground">
              Không có series nào khớp bộ lọc hiện tại.
            </div>
          ) : (
            <div className="grid gap-3">
              {filteredSeries.map((item) => {
                const reason = seriesCompatibilityReason(item, context);
                const selected = selectedSeriesId === item.id;
                const disabledCard = disabled || Boolean(reason);
                return (
                  <button
                    key={item.id}
                    type="button"
                    disabled={disabledCard}
                    onClick={() => onSelect(item)}
                    className={cn(
                      'w-full rounded-lg border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      selected
                        ? 'border-primary/70 bg-primary/10'
                        : 'border-border bg-background hover:border-foreground/30 hover:bg-muted/30',
                      disabledCard ? 'cursor-not-allowed opacity-65 hover:border-border hover:bg-background' : null,
                    )}
                  >
                    <span className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <span className="min-w-0 space-y-3">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="line-clamp-2 text-base font-semibold text-foreground">
                            {item.title}
                          </span>
                          <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground">
                            {seriesModeLabel(item.series_mode)}
                          </span>
                          {selected ? (
                            <span className="rounded-full border border-primary/35 bg-primary/10 px-2 py-0.5 text-xs text-primary">
                              Đang chọn
                            </span>
                          ) : null}
                        </span>
                        <SeriesSummaryStats series={item} />
                        <SeriesPreviewLines series={item} />
                        {reason ? (
                          <span className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs leading-relaxed text-amber-900 dark:text-amber-100">
                            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <span>{reason}</span>
                          </span>
                        ) : null}
                      </span>
                      <span className="grid shrink-0 gap-2 text-xs text-muted-foreground lg:w-44">
                        <span className="rounded-md border border-border/70 bg-muted/30 px-2 py-1.5">
                          {providerBindingLabel(item)}
                        </span>
                        <span className="rounded-md border border-border/70 bg-muted/30 px-2 py-1.5">
                          Cập nhật {formatDateTime(item.updated_at)}
                        </span>
                        <span className="rounded-md border border-border/70 bg-muted/30 px-2 py-1.5">
                          Revision {item.revision ?? 1}
                        </span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <DialogFooter>
          {onCreateNew ? (
            <Button type="button" variant="outline" onClick={onCreateNew} disabled={disabled}>
              <Plus className="h-4 w-4" />
              Tạo series mới
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Đóng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function emptyDraft(mode: SeriesMode, title = ''): SeriesDraftInput {
  return {
    title,
    series_mode: mode,
    character_bible: '',
    world_bible: '',
    style_bible: '',
    continuity_rules: '',
    negative_rules: '',
    previous_episode_summary: '',
  };
}

export function SeriesCreateDialog({
  open,
  onOpenChange,
  context,
  initialTitle,
  defaultMode,
  allowedModes,
  saving,
  error,
  nextActions = DEFAULT_CREATE_NEXT_ACTIONS,
  defaultNextAction = 'select',
  submitLabel = 'Lưu series',
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  context: SeriesPickerContext;
  initialTitle?: string;
  defaultMode?: SeriesMode;
  allowedModes?: SeriesMode[];
  saving?: boolean;
  error?: string | null;
  nextActions?: SeriesCreateNextAction[];
  defaultNextAction?: SeriesCreateNextAction;
  submitLabel?: string;
  onSubmit: (draft: SeriesDraftInput, nextAction: SeriesCreateNextAction) => void;
}) {
  const modes = useMemo(() => allowedModes ?? allowedSeriesModes(context), [allowedModes, context]);
  const modesKey = modes.join('|');
  const nextActionsKey = nextActions.join('|');
  const fallbackMode = defaultMode ?? modes[0] ?? defaultSeriesModeForContext(context);
  const [draft, setDraft] = useState<SeriesDraftInput>(() => emptyDraft(fallbackMode, initialTitle));
  const [nextAction, setNextAction] = useState<SeriesCreateNextAction>(defaultNextAction);

  useEffect(() => {
    if (!open) return;
    setDraft((current) => {
      const mode = modes.includes(current.series_mode) ? current.series_mode : fallbackMode;
      const title = current.title || initialTitle || '';
      return { ...current, title, series_mode: mode };
    });
    if (!nextActions.includes(nextAction)) {
      setNextAction(nextActions[0] ?? 'select');
    }
  }, [fallbackMode, initialTitle, modesKey, nextAction, nextActionsKey, open]);

  const visibleNextActions = CREATE_NEXT_ACTIONS.filter((item) =>
    nextActions.includes(item.action),
  );
  const canSubmit = draft.title.trim().length > 0 && !saving;

  return (
    <Dialog open={open} onOpenChange={(value) => (saving ? undefined : onOpenChange(value))}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Tạo series mới</DialogTitle>
          <DialogDescription>
            {contextLabel(context)} · chọn loại series và nhập Series Bible trước khi lưu.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          {error ? (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium">Tên series</span>
            <input
              value={draft.title}
              disabled={saving}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40 disabled:opacity-60"
              placeholder="Ví dụ: Thành phố sau mưa"
            />
          </label>

          <div className="grid gap-2">
            <p className="text-sm font-medium">Loại series</p>
            <div className="grid gap-2 md:grid-cols-3" role="radiogroup" aria-label="Loại series">
              {SERIES_MODE_OPTIONS.map((item) => {
                const Icon = item.icon;
                const allowed = modes.includes(item.mode);
                const selected = draft.series_mode === item.mode;
                return (
                  <button
                    key={item.mode}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    disabled={saving || !allowed}
                    onClick={() => setDraft((current) => ({ ...current, series_mode: item.mode }))}
                    className={cn(
                      'min-h-28 rounded-lg border p-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60',
                      selected
                        ? 'border-primary/70 bg-primary/10'
                        : 'border-border bg-background hover:bg-muted/40',
                    )}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0">
                        <span className="flex items-center gap-2 text-sm font-semibold">
                          <Icon className="h-4 w-4 shrink-0" />
                          {item.label}
                        </span>
                        <span className="mt-2 block text-xs leading-relaxed text-muted-foreground">
                          {allowed ? item.description : seriesCompatibilityReason({ series_mode: item.mode }, context)}
                        </span>
                      </span>
                      {selected ? <Check className="h-4 w-4 shrink-0 text-primary" /> : null}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {(
              [
                ['character_bible', 'Nhân vật cố định'],
                ['world_bible', 'Bối cảnh/world'],
                ['style_bible', 'Style hình ảnh'],
                ['continuity_rules', 'Quy tắc nhất quán'],
                ['negative_rules', 'Điều cần tránh'],
                ['previous_episode_summary', 'Tóm tắt tập trước'],
              ] as const
            ).map(([field, label]) => (
              <label key={field} className="grid gap-1.5 text-sm">
                <span className="font-medium">{label}</span>
                <textarea
                  value={draft[field]}
                  disabled={saving}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, [field]: event.target.value }))
                  }
                  className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed outline-none focus:border-foreground/40 disabled:opacity-60"
                  placeholder={label}
                />
              </label>
            ))}
          </div>

          <div className="grid gap-3 rounded-md border border-border/70 bg-muted/25 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <BookOpen className="h-4 w-4" />
              Preview trước khi lưu
            </div>
            <div className="grid gap-1.5 text-xs leading-5 text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Tên: </span>
                {draft.title.trim() || 'Chưa nhập tên'}
              </p>
              <p>
                <span className="font-medium text-foreground">Loại: </span>
                {seriesModeLabel(draft.series_mode)}
              </p>
              <p>
                <span className="font-medium text-foreground">Dùng được: </span>
                {contextUsageText(context, draft.series_mode)}
              </p>
              <p>
                <span className="font-medium text-foreground">Nhân vật: </span>
                {compactText(draft.character_bible)}
              </p>
              <p>
                <span className="font-medium text-foreground">World/style: </span>
                {[compactText(draft.world_bible), compactText(draft.style_bible)]
                  .filter((item) => item !== 'Chưa có nội dung')
                  .join(' · ') || 'Chưa có nội dung'}
              </p>
            </div>
          </div>

          {visibleNextActions.length > 1 ? (
            <div className="grid gap-2">
              <p className="text-sm font-medium">Sau khi lưu</p>
              <div className="grid gap-2 md:grid-cols-3" role="radiogroup" aria-label="Hành động sau khi lưu">
                {visibleNextActions.map((item) => {
                  const Icon = item.icon;
                  const selected = nextAction === item.action;
                  return (
                    <button
                      key={item.action}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      disabled={saving}
                      onClick={() => setNextAction(item.action)}
                      className={cn(
                        'min-h-20 rounded-lg border p-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60',
                        selected
                          ? 'border-primary/70 bg-primary/10'
                          : 'border-border bg-background hover:bg-muted/40',
                      )}
                    >
                      <span className="flex items-start gap-2">
                        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                        <span>
                          <span className="block text-sm font-semibold">{item.label}</span>
                          <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                            {item.description}
                          </span>
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <div className="flex items-start gap-2 rounded-md border border-sky-500/25 bg-sky-500/10 p-3 text-xs leading-relaxed text-sky-900 dark:text-sky-100">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Series Bible càng rõ thì AI càng dễ giữ đúng nhân vật, world, style và các điều cần tránh qua nhiều tập.
            </span>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Hủy
          </Button>
          <Button type="button" disabled={!canSubmit} onClick={() => onSubmit(draft, nextAction)}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
