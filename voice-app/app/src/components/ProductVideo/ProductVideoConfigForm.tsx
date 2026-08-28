import { Info } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { LANGUAGE_OPTIONS } from '@/lib/constants/languages';
import {
  PRODUCT_VIDEO_STYLE_CUSTOM,
  PRODUCT_VIDEO_STYLE_PRESETS,
  productVideoStylePreset,
} from '@/lib/constants/productVideoStyles';
import type { ProductVideoAspectRatio } from '@/lib/api/types';

/** Only vertical and horizontal — 1:1 is intentionally not offered here. */
const ASPECT_OPTIONS: { value: ProductVideoAspectRatio; label: string }[] = [
  { value: '9:16', label: 'Dọc 9:16' },
  { value: '16:9', label: 'Ngang 16:9' },
];

const PURPOSE_OPTIONS = [
  { value: 'sales_ad', label: 'Quảng cáo / bán hàng' },
  { value: 'vietnam_market', label: 'Thị trường Việt Nam' },
  { value: 'global_short', label: 'Global / short tiếng Anh' },
  { value: 'educational_explainer', label: 'Giải thích / giáo dục' },
  { value: 'localized_variant', label: 'Bản localize' },
  { value: 'custom', label: 'Tùy chỉnh' },
];

const DURATION_OPTIONS = [15, 20, 30, 45, 60, 90, 120, 150, 180];

/** Flow snaps clip length to 4/6/8/10s, so these are the only honest choices. */
const CLIP_LENGTH_OPTIONS = [4, 6, 8, 10];

export type ProductVideoFormState = {
  topic: string;
  targetLanguage: string;
  aspectRatio: ProductVideoAspectRatio;
  visualStyle: string;
  visualStylePreset: string;
  videoPurpose: string;
  dialogueMode: string;
  narrationDensity: string;
  callToActionStyle: string;
  creationMode: 'quick' | 'manual';
  automationMode: 'review_gated' | 'full_auto';
  outputTarget: 'render_ready' | 'prompt_pack' | 'shots_only';
  targetDurationSeconds: number;
  promptSegmentCount: number;
  promptSegmentDurationSeconds: number;
  microScenesPerPrompt: number;
};

export const initialProductVideoForm: ProductVideoFormState = {
  topic: '',
  targetLanguage: 'vi',
  aspectRatio: '9:16',
  visualStyle: productVideoStylePreset('ugc_street')?.text ?? '',
  visualStylePreset: 'ugc_street',
  videoPurpose: 'sales_ad',
  dialogueMode: 'voiceover',
  narrationDensity: 'light',
  callToActionStyle: 'direct',
  creationMode: 'quick',
  automationMode: 'full_auto',
  outputTarget: 'render_ready',
  targetDurationSeconds: 30,
  promptSegmentCount: 4,
  promptSegmentDurationSeconds: 8,
  microScenesPerPrompt: 3,
};

/**
 * Clip count and the duration you actually get. A 15s target with 8s clips
 * yields 16s, not 15s — we show the derived number instead of silently
 * rounding, because the user pastes one prompt per clip into Flow.
 */
export function deriveClipPlan(form: ProductVideoFormState) {
  const clipLength = form.promptSegmentDurationSeconds || 8;
  const clipCount = Math.max(
    1,
    form.promptSegmentCount || Math.ceil(form.targetDurationSeconds / clipLength),
  );
  return { clipCount, clipLength, actualSeconds: clipCount * clipLength };
}

function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs font-medium">{label}</Label>
      {children}
      {help ? <p className="text-xs text-muted-foreground">{help}</p> : null}
    </div>
  );
}

export function ProductVideoConfigForm({
  form,
  onChange,
  disabled,
}: {
  form: ProductVideoFormState;
  onChange: (next: ProductVideoFormState) => void;
  disabled?: boolean;
}) {
  const plan = deriveClipPlan(form);
  const set = <K extends keyof ProductVideoFormState>(
    key: K,
    value: ProductVideoFormState[K],
  ) => onChange({ ...form, [key]: value });

  const handlePresetChange = (value: string) => {
    const preset = productVideoStylePreset(value);
    onChange({
      ...form,
      visualStylePreset: value,
      visualStyle: value === PRODUCT_VIDEO_STYLE_CUSTOM ? '' : (preset?.text ?? form.visualStyle),
    });
  };

  // Editing the text means it is no longer the preset we shipped.
  const handleStyleTextChange = (value: string) => {
    const preset = productVideoStylePreset(form.visualStylePreset);
    const stillMatchesPreset = preset ? preset.text === value : false;
    onChange({
      ...form,
      visualStyle: value,
      visualStylePreset: stillMatchesPreset ? form.visualStylePreset : PRODUCT_VIDEO_STYLE_CUSTOM,
    });
  };

  return (
    <div className="grid gap-4">
      <Field label="Sản phẩm và ý tưởng" help="Mô tả sản phẩm, điểm bán, và thông điệp muốn truyền.">
        <Textarea
          value={form.topic}
          onChange={(event) => set('topic', event.target.value)}
          disabled={disabled}
          rows={3}
          placeholder="Ví dụ: hộp khô gà cay, nhấn vị cay và tiện mang đi, combo 2 hộp 99K"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Ngôn ngữ video">
          <Select
            value={form.targetLanguage}
            onValueChange={(value) => set('targetLanguage', value)}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Tỉ lệ video">
          <Select
            value={form.aspectRatio}
            onValueChange={(value) => set('aspectRatio', value as ProductVideoAspectRatio)}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ASPECT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Thể loại">
          <Select
            value={form.videoPurpose}
            onValueChange={(value) => set('videoPurpose', value)}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PURPOSE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field
          label="Thời lượng mục tiêu"
          help={`${form.targetDurationSeconds}s → ${plan.clipCount} clip × ${plan.clipLength}s = ${plan.actualSeconds}s thực tế`}
        >
          <Select
            value={String(form.targetDurationSeconds)}
            onValueChange={(value) => set('targetDurationSeconds', Number(value))}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DURATION_OPTIONS.map((seconds) => (
                <SelectItem key={seconds} value={String(seconds)}>
                  {seconds} giây
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Mode thoại">
          <Select value={form.dialogueMode} onValueChange={(value) => set('dialogueMode', value)} disabled={disabled}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="voiceover">Thuyết minh</SelectItem>
              <SelectItem value="character_lines">Nhân vật nói</SelectItem>
              <SelectItem value="mixed">Kết hợp</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Mật độ thoại">
          <Select value={form.narrationDensity} onValueChange={(value) => set('narrationDensity', value)} disabled={disabled}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="light">Ít thoại</SelectItem>
              <SelectItem value="balanced">Vừa phải</SelectItem>
              <SelectItem value="dense">Dày thoại</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="CTA">
          <Select value={form.callToActionStyle} onValueChange={(value) => set('callToActionStyle', value)} disabled={disabled}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Không</SelectItem>
              <SelectItem value="soft">Nhẹ nhàng</SelectItem>
              <SelectItem value="direct">Trực tiếp</SelectItem>
              <SelectItem value="urgent">Khẩn cấp</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium">Cách chạy</span>
          <span className="truncate text-[11px] text-muted-foreground">
            {form.creationMode === 'quick' ? 'Tự chạy sau khi tạo' : 'Tự bấm từng bước'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
          {[
            { value: 'quick' as const, label: 'Dựng nhanh' },
            { value: 'manual' as const, label: 'Thủ công' },
          ].map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={form.creationMode === item.value}
              disabled={disabled}
              onClick={() => set('creationMode', item.value)}
              className={`h-8 rounded-md px-2 text-sm font-medium transition ${form.creationMode === item.value ? 'bg-foreground text-background shadow-sm' : 'text-muted-foreground hover:bg-background/70 hover:text-foreground'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {form.creationMode === 'quick' ? (
        <>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium">Mức tự động</span>
              <span className="truncate text-[11px] text-muted-foreground">
                {form.automationMode === 'review_gated' ? 'Dừng để duyệt' : 'Tự chạy hết'}
              </span>
            </div>
            <div className="grid gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
              {[
                { value: 'review_gated' as const, label: 'Duyệt từng chặng', helper: 'Dừng sau khi lập kế hoạch' },
                { value: 'full_auto' as const, label: 'Tự chạy hết', helper: 'Tự sinh prompt pack nội bộ' },
              ].map((item) => (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={form.automationMode === item.value}
                  disabled={disabled}
                  onClick={() => set('automationMode', item.value)}
                  className={`grid min-h-11 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md px-2.5 py-2 text-left transition ${form.automationMode === item.value ? 'bg-foreground text-background shadow-sm' : 'text-muted-foreground hover:bg-background/70 hover:text-foreground'}`}
                >
                  <span><span className="block text-sm font-semibold leading-tight">{item.label}</span><span className="mt-0.5 block text-[11px] leading-snug opacity-75">{item.helper}</span></span>
                  <span className={`h-2 w-2 rounded-full border border-current/35 ${form.automationMode === item.value ? 'bg-current' : 'bg-transparent'}`} />
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium">Đầu ra tự chạy</span>
              <span className="truncate text-[11px] text-muted-foreground">
                {form.outputTarget === 'render_ready' ? 'Prompt + bridge dựng MP4' : form.outputTarget === 'prompt_pack' ? 'Prompt pack tải xuống' : 'Chỉ lập kế hoạch cảnh'}
              </span>
            </div>
            <div className="grid gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
              {[
                { value: 'render_ready' as const, label: 'Sẵn sàng dựng MP4', helper: 'Sinh prompt và chuẩn bị bridge; bạn vẫn upload clip rồi bấm Dựng MP4' },
                { value: 'prompt_pack' as const, label: 'Prompt pack thoại', helper: 'Sinh prompt để kiểm tra và tải xuống; không chạy provider/TTS' },
                { value: 'shots_only' as const, label: 'Chỉ câu lệnh video', helper: 'Chỉ lập kế hoạch cảnh, dừng trước bước sinh prompt' },
              ].map((item) => (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={form.outputTarget === item.value}
                  disabled={disabled}
                  onClick={() => set('outputTarget', item.value)}
                  className={`grid min-h-11 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md px-2.5 py-2 text-left transition ${form.outputTarget === item.value ? 'bg-foreground text-background shadow-sm' : 'text-muted-foreground hover:bg-background/70 hover:text-foreground'}`}
                >
                  <span><span className="block text-sm font-semibold leading-tight">{item.label}</span><span className="mt-0.5 block text-[11px] leading-snug opacity-75">{item.helper}</span></span>
                  <span className={`h-2 w-2 rounded-full border border-current/35 ${form.outputTarget === item.value ? 'bg-current' : 'bg-transparent'}`} />
                </button>
              ))}
            </div>
          </div>
        </>
      ) : null}

      <Field
        label="Phong cách"
        help="Chọn preset để điền sẵn rồi sửa thoải mái, hoặc chọn Tự nhập để viết từ đầu."
      >
        <Select
          value={form.visualStylePreset}
          onValueChange={handlePresetChange}
          disabled={disabled}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PRODUCT_VIDEO_STYLE_PRESETS.map((preset) => (
              <SelectItem key={preset.value} value={preset.value}>
                {preset.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Textarea
          value={form.visualStyle}
          onChange={(event) => handleStyleTextChange(event.target.value)}
          disabled={disabled}
          rows={6}
          className="mt-2 font-mono text-xs"
          placeholder="Mô tả phong cách bằng tiếng Anh: chủ thể, chuyển động camera, chuyển động hậu cảnh, ánh sáng."
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Số câu lệnh" help="Số clip/prompt sẽ lập kế hoạch.">
          <Input
            type="number"
            min={1}
            max={60}
            value={form.promptSegmentCount ?? 1}
            onChange={(event) =>
              set('promptSegmentCount', Math.min(60, Math.max(1, Number(event.target.value) || 1)))
            }
            disabled={disabled}
          />
        </Field>

        <Field label="Giây/câu lệnh" help="Flow chỉ nhận 4, 6, 8 hoặc 10 giây.">
          <Select
            value={String(form.promptSegmentDurationSeconds)}
            onValueChange={(value) => set('promptSegmentDurationSeconds', Number(value))}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CLIP_LENGTH_OPTIONS.map((seconds) => (
                <SelectItem key={seconds} value={String(seconds)}>
                  {seconds} giây
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Cảnh nhỏ" help="Số nhịp hình bên trong một clip. 1 đến 5.">
          <Input
            type="number"
            min={1}
            max={5}
            value={form.microScenesPerPrompt ?? 1}
            onChange={(event) =>
              set('microScenesPerPrompt', Math.min(5, Math.max(1, Number(event.target.value) || 1)))
            }
            disabled={disabled}
          />
        </Field>
      </div>

      <p className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          Luồng này dùng prompt sản phẩm riêng. Chế độ tự chạy chỉ lập kế hoạch và sinh prompt nội
          bộ — không tự gửi Veo, Chrome, TTS, phụ đề hay render. Sau đó bạn có thể tự dùng Flow,
          hoặc upload clip vào phần dựng MP4 bên dưới. Sẽ có {plan.clipCount} prompt cần dùng.
        </span>
      </p>
    </div>
  );
}
