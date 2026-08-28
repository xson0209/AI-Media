import { AlertCircle, Check, Loader2, Play, Save } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import type { AIPlanningTestResponse } from '@/lib/api/types';
import { useAIPlanningSettings } from '@/lib/hooks/useSettings';
import { cn } from '@/lib/utils/cn';
import { SettingRow, SettingSection } from './SettingRow';

type AIPlanningPreset = {
  key: string;
  model: string;
  reasoningEffort: 'xhigh' | 'ultra';
  label: string;
  helper: string;
};

const AI_PLANNING_PRESETS: AIPlanningPreset[] = [
  {
    key: 'gpt-5.5-xhigh',
    model: 'gpt-5.5',
    reasoningEffort: 'xhigh',
    label: 'gpt-5.5 · xhigh',
    helper: 'Nhẹ hơn, dùng khi provider đang chậm hoặc cần phản hồi nhanh hơn.',
  },
  {
    key: 'gpt-5.6-sol-ultra',
    model: 'gpt-5.6-sol',
    reasoningEffort: 'ultra',
    label: 'gpt-5.6-sol · ultra',
    helper: 'Chất lượng cao nhất, phù hợp khi cần kịch bản/prompt kỹ nhưng có thể chậm.',
  },
  {
    key: 'gpt-5.6-sol-xhigh',
    model: 'gpt-5.6-sol',
    reasoningEffort: 'xhigh',
    label: 'gpt-5.6-sol · xhigh',
    helper: 'Cân bằng hơn ultra, vẫn giữ chất lượng cao cho Story/Prompt.',
  },
  {
    key: 'gpt-5.6-luna-xhigh',
    model: 'gpt-5.6-luna',
    reasoningEffort: 'xhigh',
    label: 'gpt-5.6-luna · xhigh',
    helper: 'Nhanh và tiết kiệm hơn cho planning/prompt hằng ngày, vẫn dùng suy luận xhigh.',
  },
  {
    key: 'gpt-5.6-terra-ultra',
    model: 'gpt-5.6-terra',
    reasoningEffort: 'ultra',
    label: 'gpt-5.6-terra · ultra',
    helper: 'Preset mạnh cho tác vụ khó, dùng khi cần suy luận sâu.',
  },
  {
    key: 'gpt-5.6-terra-xhigh',
    model: 'gpt-5.6-terra',
    reasoningEffort: 'xhigh',
    label: 'gpt-5.6-terra · xhigh',
    helper: 'Preset terra ít nặng hơn ultra, phù hợp khi provider đang chậm.',
  },
];

function presetKey(model: string | null | undefined, effort: string | null | undefined): string {
  const normalizedModel = (model || 'gpt-5.6-sol').trim();
  const normalizedEffort = (effort || 'ultra').trim().toLowerCase();
  return (
    AI_PLANNING_PRESETS.find(
      (preset) =>
        preset.model === normalizedModel && preset.reasoningEffort === normalizedEffort,
    )?.key ?? 'custom'
  );
}

function configLabel(model: string | null | undefined, effort: string | null | undefined): string {
  return [(model || 'gpt-5.6-sol').trim(), (effort || 'ultra').trim()]
    .filter(Boolean)
    .join(' · ');
}

function metadataLabel(result: AIPlanningTestResponse | null): string {
  if (!result) return '';
  const model = result.effective_model || result.requested_model || 'không rõ model';
  const effort = result.effective_reasoning_effort || result.requested_reasoning_effort;
  return [model, effort].filter(Boolean).join(' · ');
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

export function AIPlanningPage() {
  const queryClient = useQueryClient();
  const aiPlanning = useAIPlanningSettings();
  const [selectedPresetKey, setSelectedPresetKey] = useState('gpt-5.6-sol-ultra');
  const [testResult, setTestResult] = useState<AIPlanningTestResponse | null>(null);
  const currentPresetKey = presetKey(
    aiPlanning.settings?.model,
    aiPlanning.settings?.model_reasoning_effort,
  );
  const selectedPreset = useMemo(
    () => AI_PLANNING_PRESETS.find((preset) => preset.key === selectedPresetKey),
    [selectedPresetKey],
  );

  useEffect(() => {
    setSelectedPresetKey(currentPresetKey);
  }, [currentPresetKey]);

  const testMutation = useMutation({
    mutationFn: () => apiClient.testAIPlanningSettings(),
    onSuccess: (result) => {
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ['ai-video', 'planning-check'] });
    },
  });

  const saveAndTest = async () => {
    const preset = AI_PLANNING_PRESETS.find((item) => item.key === selectedPresetKey);
    if (!preset) return;

    setTestResult(null);
    await aiPlanning.updateAsync({
      model: preset.model,
      model_reasoning_effort: preset.reasoningEffort,
    });
    await testMutation.mutateAsync();
  };

  const testOnly = async () => {
    setTestResult(null);
    await testMutation.mutateAsync();
  };

  const currentLabel = configLabel(
    aiPlanning.settings?.model,
    aiPlanning.settings?.model_reasoning_effort,
  );
  const isBusy = aiPlanning.isUpdating || testMutation.isPending;
  const saveError = aiPlanning.error ? errorMessage(aiPlanning.error) : null;
  const testError = testMutation.error ? errorMessage(testMutation.error) : null;

  return (
    <div className="flex max-w-5xl items-start gap-8">
      <div className="min-w-0 flex-1 space-y-8">
        <SettingSection
          title="AI planning / Codex"
          description="Cấu hình model dùng chung cho AI Video, Story Studio, tạo truyện, tạo kịch bản và các bước AI planning khác."
        >
          <SettingRow
            title="Preset model"
            description="Chọn cấu hình trước khi chạy. Bấm “Lưu và test Codex” để lưu cấu hình rồi gửi prompt “xin chào” tới Codex."
            action={
              <span className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-muted-foreground">
                Đang lưu: {currentLabel}
              </span>
            }
          >
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
              <label className="grid min-w-0 gap-2">
                <span className="sr-only">Preset AI planning</span>
                <select
                  value={selectedPresetKey}
                  disabled={isBusy || aiPlanning.isLoading}
                  onChange={(event) => {
                    setSelectedPresetKey(event.target.value);
                    setTestResult(null);
                  }}
                  className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-foreground/40 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {currentPresetKey === 'custom' ? (
                    <option value="custom">Tùy chỉnh hiện có: {currentLabel}</option>
                  ) : null}
                  {AI_PLANNING_PRESETS.map((preset) => (
                    <option key={preset.key} value={preset.key}>
                      {preset.label}
                    </option>
                  ))}
                </select>
                <span className="text-xs leading-relaxed text-muted-foreground">
                  {selectedPreset?.helper ??
                    'Cấu hình hiện tại không nằm trong preset nhanh. Chọn một preset để chuẩn hóa.'}
                </span>
              </label>
              <div className="grid gap-2 sm:min-w-44">
                <Button
                  type="button"
                  disabled={isBusy || !selectedPreset}
                  onClick={saveAndTest}
                  className="w-full"
                >
                  {isBusy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Lưu và test Codex
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={isBusy}
                  onClick={testOnly}
                  className="w-full"
                >
                  {testMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Test lại
                </Button>
              </div>
            </div>
          </SettingRow>

          <SettingRow
            title="Thông tin kết nối"
            description="Đường dẫn Codex và timeout backend đang dùng cho bài test."
          >
            <dl className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3 text-sm sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="text-xs font-medium text-muted-foreground">Codex path</dt>
                <dd className="mt-1 break-all">
                  {aiPlanning.settings?.codex_path || 'Chưa cấu hình'}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Timeout</dt>
                <dd className="mt-1">{aiPlanning.settings?.timeout_seconds ?? 600}s</dd>
              </div>
            </dl>
          </SettingRow>
        </SettingSection>

        <section
          aria-live="polite"
          className={cn(
            'rounded-lg border p-4',
            testResult?.ready
              ? 'border-emerald-500/30 bg-emerald-500/10'
              : testResult
                ? 'border-destructive/30 bg-destructive/10'
                : 'border-border bg-card/50',
          )}
        >
          <div className="flex items-start gap-3">
            {testMutation.isPending ? (
              <Loader2 className="mt-0.5 h-4 w-4 animate-spin" />
            ) : testResult?.ready ? (
              <Check className="mt-0.5 h-4 w-4 text-emerald-600" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 text-muted-foreground" />
            )}
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {testMutation.isPending
                  ? 'Đang gửi “xin chào” tới Codex…'
                  : testResult?.message ?? 'Chưa test cấu hình hiện tại.'}
              </p>
              {testResult ? (
                <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                  <p className="break-words">Prompt test: {testResult.prompt}</p>
                  <p className="break-words">
                    Model thực chạy: {metadataLabel(testResult) || 'chưa xác định'}
                  </p>
                  <p className="break-words">
                    Request ID: {testResult.request_id || 'chưa có'}
                  </p>
                  {testResult.fallback_used ? (
                    <p className="break-words">
                      Fallback: {testResult.fallback_reason || 'có dùng fallback'}
                    </p>
                  ) : null}
                  {testResult.output_text ? (
                    <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap rounded-md border border-border/70 bg-background p-3 text-sm text-foreground">
                      {testResult.output_text}
                    </pre>
                  ) : null}
                  {testResult.error_code ? (
                    <p className="break-words text-destructive">
                      Mã lỗi: {testResult.error_code}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {saveError ? (
                <p className="mt-2 text-sm text-destructive">
                  Không lưu được cấu hình: {saveError}
                </p>
              ) : null}
              {testError ? (
                <p className="mt-2 text-sm text-destructive">
                  Không test được Codex: {testError}
                </p>
              ) : null}
            </div>
          </div>
        </section>
      </div>

      <aside className="hidden w-[280px] shrink-0 space-y-4 lg:block">
        <div className="rounded-lg border border-border/70 bg-card/50 p-4">
          <h3 className="text-sm font-semibold">Cách dùng</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-4 text-sm leading-relaxed text-muted-foreground">
            <li>Chọn preset model phù hợp.</li>
            <li>Bấm “Lưu và test Codex”.</li>
            <li>
              Nếu Codex trả về text, cấu hình được xem là dùng được cho AI Video và Story
              Studio.
            </li>
          </ol>
        </div>
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200">
          <p className="font-medium">Lưu ý hiệu năng</p>
          <p className="mt-2 leading-relaxed">
            <code>ultra</code> có thể chậm khi provider đang tải cao. Nếu test lâu hoặc
            fail, thử <code>xhigh</code> trước.
          </p>
        </div>
      </aside>
    </div>
  );
}
