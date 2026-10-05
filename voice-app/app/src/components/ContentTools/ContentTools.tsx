import {
  ArrowRight,
  BookOpen,
  Check,
  Clipboard,
  FileAudio,
  Layers3,
  Loader2,
  Mic2,
  Podcast,
  Sparkles,
} from 'lucide-react';
import { useSearch } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import type {
  ContentToolAngle,
  ContentToolMode,
  ContentToolsGenerateResponse,
} from '@/lib/api/types';

type ToolDefinition = {
  mode: ContentToolMode;
  label: string;
  description: string;
  icon: typeof Podcast;
};

const tools: ToolDefinition[] = [
  {
    mode: 'podcast_short',
    label: 'Podcast → video ngắn',
    description: 'Chọn đoạn đáng chú ý, tạo hook, script và prompt cảnh bổ trợ.',
    icon: Podcast,
  },
  {
    mode: 'multi_angle',
    label: 'Một nội dung → nhiều góc kể',
    description: 'Biến cùng một nội dung thành hướng dẫn, kể chuyện, so sánh, phản biện và hỏi đáp.',
    icon: Layers3,
  },
  {
    mode: 'lesson_story',
    label: 'Bài học → truyện minh họa',
    description: 'Đưa bài học vào nhân vật, lựa chọn, hậu quả và hành động có thể nhìn thấy.',
    icon: BookOpen,
  },
];

const angleOptions: Array<{ value: ContentToolAngle; label: string }> = [
  { value: 'how_to', label: 'Hướng dẫn' },
  { value: 'story', label: 'Kể chuyện' },
  { value: 'comparison', label: 'So sánh' },
  { value: 'counterpoint', label: 'Phản biện' },
  { value: 'q_and_a', label: 'Hỏi đáp' },
];

function copyToClipboard(text: string, onCopied: () => void, onError: (message: string) => void) {
  void navigator.clipboard.writeText(text).then(onCopied).catch(() => onError('Không copy được. Hãy chọn và copy thủ công.'));
}

export function ContentTools() {
  const search = useSearch({ from: '/content-tools' });
  const [mode, setMode] = useState<ContentToolMode>(search.kind ?? 'podcast_short');
  const [sourceText, setSourceText] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [title, setTitle] = useState('');
  const [audience, setAudience] = useState('');
  const [ageBand, setAgeBand] = useState('');
  const [visualStyle, setVisualStyle] = useState('Cinematic, rõ chủ thể, nhân vật nhất quán');
  const [lessonOutcome, setLessonOutcome] = useState('');
  const [duration, setDuration] = useState(60);
  const [angles, setAngles] = useState<ContentToolAngle[]>(angleOptions.map((option) => option.value));
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [result, setResult] = useState<ContentToolsGenerateResponse | null>(null);
  const [activeAngle, setActiveAngle] = useState(0);
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const selectedTool = useMemo(() => tools.find((tool) => tool.mode === mode) ?? tools[0], [mode]);
  const activeResult = result?.angles[Math.min(activeAngle, Math.max(0, (result?.angles.length ?? 1) - 1))];

  const toggleAngle = (angle: ContentToolAngle) => {
    setAngles((current) => (current.includes(angle) ? current.filter((item) => item !== angle) : [...current, angle]));
  };

  const handleGenerate = async () => {
    setError(null);
    setCopied(null);
    setIsGenerating(true);
    try {
      let transcript = sourceText.trim();
      if (audioFile) {
        if (mode !== 'podcast_short') {
          throw new Error('File audio chỉ dùng cho chế độ Podcast → video ngắn.');
        }
        const transcription = await apiClient.transcribeAudio(audioFile, 'vi');
        transcript = [transcript, transcription.text].filter(Boolean).join('\n\n');
      }
      if (!transcript && !sourceUrl.trim()) {
        throw new Error('Hãy nhập nội dung, transcript, URL hoặc chọn file audio.');
      }
      if (mode === 'multi_angle' && angles.length === 0) {
        throw new Error('Chọn ít nhất một góc kể.');
      }
      const generated = await apiClient.generateContentTool({
        mode,
        source_text: transcript || undefined,
        source_url: sourceUrl.trim() || undefined,
        title: title.trim() || undefined,
        language: 'vi',
        target_duration_seconds: duration,
        angles: mode === 'multi_angle' ? angles : undefined,
        audience: audience.trim() || undefined,
        age_band: ageBand.trim() || undefined,
        visual_style: visualStyle.trim() || undefined,
        lesson_outcome: mode === 'lesson_story' ? lessonOutcome.trim() || undefined : undefined,
      });
      setResult(generated);
      setActiveAngle(0);
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : 'Không tạo được nội dung.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleModeChange = (nextMode: string) => {
    if (nextMode === 'podcast_short' || nextMode === 'multi_angle' || nextMode === 'lesson_story') {
      setMode(nextMode);
      setError(null);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto py-5 lg:py-7">
      <header className="flex flex-wrap items-start justify-between gap-4 px-1">
        <div className="max-w-3xl">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-orange-400">
            <Sparkles className="h-4 w-4" aria-hidden="true" /> Content workspace
          </div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Tạo nội dung thành video</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground sm:text-base">
            Chọn nguồn và cách kể, sau đó nhận bản nháp có thể kiểm tra, chỉnh sửa và đưa sang AI Video.
          </p>
        </div>
        <Badge variant="outline" className="border-orange-400/40 text-orange-300">Draft trước khi xuất bản</Badge>
      </header>

      <Tabs value={mode} onValueChange={handleModeChange} className="space-y-4">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-1 bg-muted/60 p-1 sm:grid-cols-3">
          {tools.map((tool) => {
            const Icon = tool.icon;
            return (
              <TabsTrigger key={tool.mode} value={tool.mode} className="min-h-16 justify-start gap-3 px-4 py-3 text-left data-[state=active]:bg-background">
                <Icon className="h-5 w-5 shrink-0 text-orange-400" aria-hidden="true" />
                <span className="min-w-0"><span className="block truncate font-semibold">{tool.label}</span><span className="mt-1 block truncate text-xs font-normal text-muted-foreground">{tool.description}</span></span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        {tools.map((tool) => <TabsContent key={tool.mode} value={tool.mode} className="mt-0" />)}
      </Tabs>

      <div className="grid min-h-0 gap-5 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        <Card className="border-white/10 bg-card/80">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg"><Mic2 className="h-5 w-5 text-orange-400" />Nguồn và định hướng</CardTitle>
            <CardDescription>{selectedTool.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><label htmlFor="content-tools-source" className="text-sm font-medium">Nội dung hoặc transcript</label><Textarea id="content-tools-source" value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder={mode === 'podcast_short' ? 'Dán transcript podcast hoặc ghi chú nội dung…' : mode === 'lesson_story' ? 'Mô tả bài học, kỹ năng hoặc quy tắc ứng xử…' : 'Dán bài viết, kịch bản hoặc nội dung gốc…'} className="min-h-36 resize-y" /></div>
            <div className="space-y-2"><label htmlFor="content-tools-url" className="text-sm font-medium">URL nguồn <span className="font-normal text-muted-foreground">(tuỳ chọn)</span></label><Input id="content-tools-url" type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…" /></div>
            {mode === 'podcast_short' && <div className="space-y-2"><label htmlFor="content-tools-audio" className="text-sm font-medium">File podcast <span className="font-normal text-muted-foreground">(tuỳ chọn)</span></label><Input id="content-tools-audio" type="file" accept="audio/*,.mp3,.m4a,.wav,.ogg,.webm" onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)} className="h-auto py-2 file:mr-3 file:rounded file:border-0 file:bg-muted file:px-2 file:py-1 file:text-xs" />{audioFile && <p className="flex items-center gap-1 text-xs text-muted-foreground"><FileAudio className="h-3.5 w-3.5" />{audioFile.name} · sẽ transcription trước khi tạo</p>}</div>}
            <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><label htmlFor="content-tools-title" className="text-sm font-medium">Tiêu đề <span className="font-normal text-muted-foreground">(tuỳ chọn)</span></label><Input id="content-tools-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: 5 phút đọc sách" /></div><div className="space-y-2"><label htmlFor="content-tools-duration" className="text-sm font-medium">Thời lượng (giây)</label><Input id="content-tools-duration" type="number" min={15} max={600} value={duration} onChange={(event) => setDuration(Number(event.target.value) || 60)} /></div></div>
            <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><label htmlFor="content-tools-audience" className="text-sm font-medium">Đối tượng <span className="font-normal text-muted-foreground">(tuỳ chọn)</span></label><Input id="content-tools-audience" value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="Người mới bắt đầu…" /></div><div className="space-y-2"><label htmlFor="content-tools-age" className="text-sm font-medium">Nhóm tuổi</label><Input id="content-tools-age" value={ageBand} onChange={(event) => setAgeBand(event.target.value)} placeholder="Ví dụ: 6–9 tuổi" /></div></div>
            <div className="space-y-2"><label htmlFor="content-tools-style" className="text-sm font-medium">Phong cách hình ảnh</label><Input id="content-tools-style" value={visualStyle} onChange={(event) => setVisualStyle(event.target.value)} /></div>
            {mode === 'lesson_story' && <div className="space-y-2"><label htmlFor="content-tools-outcome" className="text-sm font-medium">Hành vi muốn người xem học được</label><Textarea id="content-tools-outcome" value={lessonOutcome} onChange={(event) => setLessonOutcome(event.target.value)} placeholder="Sau câu chuyện, người xem sẽ…" className="min-h-20" /></div>}
            {mode === 'multi_angle' && <fieldset className="space-y-2"><legend className="text-sm font-medium">Góc kể cần tạo</legend><div className="flex flex-wrap gap-2">{angleOptions.map((option) => <label key={option.value} className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-2 text-xs transition-colors has-[:checked]:border-orange-400 has-[:checked]:bg-orange-400/10"><input type="checkbox" className="accent-orange-500" checked={angles.includes(option.value)} onChange={() => toggleAngle(option.value)} />{option.label}</label>)}</div></fieldset>}
            {error && <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}
            <Button className="w-full" size="lg" disabled={isGenerating} onClick={() => void handleGenerate()} aria-busy={isGenerating}>{isGenerating ? <Loader2 className="animate-spin" aria-hidden="true" /> : <ArrowRight aria-hidden="true" />}{isGenerating ? 'Đang tạo bản nháp…' : 'Tạo script và prompt video'}</Button>
            <p className="text-xs leading-5 text-muted-foreground">Kết quả là bản nháp để bạn kiểm tra claim, quyền sử dụng nguồn và chỉnh sửa trước khi xuất bản.</p>
          </CardContent>
        </Card>

        <Card className="min-h-[540px] border-white/10 bg-card/80" aria-live="polite" aria-busy={isGenerating}>
          <CardHeader className="border-b border-border/60"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-lg">Kết quả</CardTitle><CardDescription>{result ? `${result.title} · ${result.angles.length} phiên bản` : 'Script, hook và prompt cảnh sẽ xuất hiện ở đây.'}</CardDescription></div>{result && <Badge variant="outline" className="shrink-0 text-emerald-400"><Check className="mr-1 h-3 w-3" />Đã tạo</Badge>}</div></CardHeader>
          <CardContent className="space-y-5 pt-5">
            {!result && !isGenerating && <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed border-border/70 px-6 text-center"><Sparkles className="mb-3 h-9 w-9 text-orange-400/70" /><p className="font-medium">Bắt đầu từ nguồn nội dung của bạn</p><p className="mt-1 max-w-sm text-sm leading-6 text-muted-foreground">Chọn một tool, nhập nguồn và tạo bản nháp có thể đưa tiếp sang AI Video.</p></div>}
            {isGenerating && <div className="flex min-h-[400px] flex-col items-center justify-center gap-3 text-center"><Loader2 className="h-8 w-8 animate-spin text-orange-400" /><p className="font-medium">Đang phân tích và viết prompt…</p><p className="text-sm text-muted-foreground">Nếu nguồn dài, bước này có thể mất một lúc.</p></div>}
            {result && !isGenerating && <>
              <div className="rounded-lg border border-orange-400/20 bg-orange-400/5 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-orange-300">Tóm tắt nguồn</p><p className="mt-2 text-sm leading-6">{result.source_summary}</p>{result.selected_excerpt && <blockquote className="mt-3 border-l-2 border-orange-400/50 pl-3 text-sm italic text-muted-foreground">{result.selected_excerpt}</blockquote>}</div>
              {result.angles.length > 1 && <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Các phiên bản nội dung">{result.angles.map((angle, index) => <button key={`${angle.angle}-${index}`} type="button" role="tab" aria-selected={activeAngle === index} onClick={() => setActiveAngle(index)} className={`shrink-0 rounded-full border px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 ${activeAngle === index ? 'border-orange-400 bg-orange-400/10 text-orange-200' : 'border-border text-muted-foreground hover:text-foreground'}`}>{angle.label}</button>)}</div>}
              {activeResult && <div className="space-y-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hook</p><p className="mt-1 text-base font-medium leading-6">{activeResult.hook}</p></div><div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Lời hứa với người xem</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{activeResult.promise}</p></div><div className="rounded-lg bg-muted/50 p-4"><div className="mb-2 flex items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Script</p><Button size="sm" variant="ghost" onClick={() => copyToClipboard(activeResult.script, () => setCopied('script'), (message) => setError(message))}><Clipboard className="h-3.5 w-3.5" />{copied === 'script' ? 'Đã copy' : 'Copy'}</Button></div><p className="whitespace-pre-wrap text-sm leading-6">{activeResult.script}</p></div><div className="space-y-3"><div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Prompt theo cảnh</p><Button size="sm" variant="outline" onClick={() => copyToClipboard(activeResult.scenes.map((scene) => scene.video_prompt).join('\n\n'), () => setCopied('prompts'), (message) => setError(message))}><Clipboard className="h-3.5 w-3.5" />{copied === 'prompts' ? 'Đã copy' : 'Copy toàn bộ'}</Button></div>{activeResult.scenes.map((scene) => <div key={`${scene.order}-${scene.title}`} className="rounded-lg border border-border/70 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{String(scene.order).padStart(2, '0')} · {scene.title}</p><Badge variant="outline">{scene.duration_seconds}s</Badge></div><p className="mt-2 text-sm leading-6 text-muted-foreground">{scene.visual_description}</p><div className="mt-3 rounded-md bg-background/80 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Video prompt</p><p className="mt-1 text-sm leading-6">{scene.video_prompt}</p></div>{scene.negative_prompt && <p className="mt-2 text-xs text-muted-foreground">Tránh: {scene.negative_prompt}</p>}</div>)}</div></div>}
              <div className="flex flex-wrap gap-2 border-t border-border/60 pt-4">{result.next_steps.map((step) => <Badge key={step} variant="secondary">{step}</Badge>)}</div>
            </>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
