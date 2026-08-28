import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clapperboard, Copy, Loader2, Plus } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AIVideoRenderPanel } from '@/components/AIVideoAssistant/AIVideoRenderPanel';
import { AIVideoPublishingMetadataPanel } from '@/components/AIVideoAssistant/AIVideoPublishingMetadataPanel';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import type { NewsSpeechMode, VideoProjectResponse, VideoLanguage, VideoPublishingGeneratePlatform } from '@/lib/api/types';

const speechOptions: Array<{ value: NewsSpeechMode; label: string }> = [
  { value: 'voicebox_khong_context', label: 'TTS Voicebox hậu kỳ (không lời trong Veo)' },
  { value: 'voicebox_co_context', label: 'TTS Voicebox + ngữ cảnh nhịp hình' },
  { value: 'veo_narration', label: 'Veo 3 tự đọc lời dẫn' },
  { value: 'veo_dialogue', label: 'Presenter/nhân vật thoại trong Veo 3' },
  { value: 'none', label: 'Không lời' },
];

export function NewsVideo() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [topic, setTopic] = useState('');
  const [sourceNote, setSourceNote] = useState('');
  const [speechSource, setSpeechSource] = useState<NewsSpeechMode>('voicebox_khong_context');
  const [notice, setNotice] = useState<string | null>(null);
  const projects = useQuery({ queryKey: ['news-video', 'projects'], queryFn: () => apiClient.listNewsVideoProjects() });
  const detail = useQuery({
    queryKey: ['news-video', 'project', selectedId],
    queryFn: () => apiClient.getNewsVideoProject(selectedId as string),
    enabled: Boolean(selectedId),
  });
  const metadata = useQuery({ queryKey: ['news-video', 'metadata', selectedId], queryFn: () => apiClient.getVideoPublishingMetadata(selectedId as string), enabled: Boolean(selectedId), retry: false });
  const generateMetadata = useMutation({ mutationFn: (platform: VideoPublishingGeneratePlatform = 'all') => apiClient.generateVideoPublishingMetadata(selectedId as string, { platform, force: true }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['news-video', 'metadata', selectedId] }) });
  const create = useMutation({
    mutationFn: () => apiClient.createNewsVideoProject({
      topic: topic.trim(), source_note: sourceNote.trim() || undefined,
      title: topic.slice(0, 160) || 'Video tin tức',
      language: 'vi', target_language: 'vi', phase: 'phase2', aspect_ratio: '9:16',
      speech_source: speechSource, prompt_segment_duration_seconds: 8,
    }),
    onSuccess: (project) => { setSelectedId(project.id); void queryClient.invalidateQueries({ queryKey: ['news-video', 'projects'] }); },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Không tạo được dự án.'),
  });
  const plan = useMutation({
    mutationFn: () => apiClient.planNewsVideoProject(selectedId as string),
    onSuccess: () => { setNotice('Đã sinh shot. Tiếp theo hãy tạo prompt Veo 3.'); void queryClient.invalidateQueries({ queryKey: ['news-video', 'project', selectedId] }); },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Không sinh được shot.'),
  });
  const prompts = useMutation({
    mutationFn: () => apiClient.generateNewsVideoPrompts(selectedId as string),
    onSuccess: () => { setNotice('Đã tạo provider-ready prompt. Bạn có thể copy sang Veo 3.'); void queryClient.invalidateQueries({ queryKey: ['news-video', 'project', selectedId] }); },
    onError: (error) => setNotice(error instanceof Error ? error.message : 'Không tạo được prompt.'),
  });
  const project = detail.data;
  const copyShotPrompt = async (shotId: string) => {
    if (!selectedId) return;
    try {
      const result = await apiClient.getNewsVideoPrompt(selectedId, shotId);
      await navigator.clipboard.writeText(result.content);
      setNotice('Đã copy prompt provider-ready. Dán thủ công vào Veo 3 để render.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Không đọc được prompt.');
    }
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto py-4">
      <div className="flex items-center gap-3"><Clapperboard className="h-6 w-6" /><div><h1 className="text-xl font-semibold">Video tin tức</h1><p className="text-sm text-muted-foreground">Nhập tin → sinh prompt → dán Veo 3 → tải MP4 → upload đúng shot.</p></div></div>
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card><CardHeader><CardTitle>Dự án</CardTitle></CardHeader><CardContent className="space-y-3">
          <Textarea value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Chủ đề hoặc nội dung bài tin..." />
          <Textarea value={sourceNote} onChange={(e) => setSourceNote(e.target.value)} placeholder="Ghi chú nguồn/URL (hệ thống không tự đọc URL)" />
          <select className="w-full rounded-md border bg-background p-2 text-sm" value={speechSource} onChange={(e) => setSpeechSource(e.target.value as NewsSpeechMode)}>{speechOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
          <Button className="w-full" disabled={!topic.trim() || create.isPending} onClick={() => create.mutate()}>{create.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Tạo dự án 9:16</Button>
          <div className="space-y-1">{projects.data?.map((item: VideoProjectResponse) => <button type="button" key={item.id} className="block w-full rounded border p-2 text-left text-sm hover:bg-muted" onClick={() => setSelectedId(item.id)}>{item.title}<span className="ml-2 text-xs text-muted-foreground">{item.status}</span></button>)}</div>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Luồng thủ công Veo 3</CardTitle></CardHeader><CardContent className="space-y-4">
          {!project ? <p className="text-sm text-muted-foreground">Chọn hoặc tạo dự án để bắt đầu.</p> : <>
            <div className="flex flex-wrap gap-2"><Badge>9:16</Badge><Badge>Tiếng Việt</Badge><Badge>{speechOptions.find((x) => x.value === (project.speech_source ?? speechSource))?.label}</Badge></div>
            <div className="flex flex-wrap gap-2"><Button disabled={plan.isPending} onClick={() => plan.mutate()}>1. Sinh shot</Button><Button disabled={prompts.isPending} onClick={() => prompts.mutate()}>2. Sinh prompt Veo 3</Button><Button variant="outline" onClick={() => setNotice('Copy prompt ở panel AI Video sau khi prompt pack hoàn tất.') }><Copy className="mr-2 h-4 w-4" />Hướng dẫn copy</Button></div>
            <Button variant="outline" onClick={() => void apiClient.downloadNewsVideoPromptPack(selectedId!)}>Tải prompt pack UTF-8</Button>
            <p className="rounded-md bg-muted p-3 text-sm">3. Copy provider-ready prompt sang Veo 3, tự render và tải MP4. 4. Quay lại chọn đúng shot để upload clip thủ công. Không tự mở Veo hoặc tự tiêu credit.</p>
            {notice && <p className="text-sm text-amber-600">{notice}</p>}
            <div className="space-y-2">{project.shots?.map((shot) => <div key={shot.id} className="rounded border p-3 text-sm"><div className="flex items-center justify-between"><span>Shot {String(shot.shot_order).padStart(2, '0')}</span><div className="flex items-center gap-2"><Badge variant="outline">{shot.prompt_status}</Badge><Button size="sm" variant="outline" onClick={() => void copyShotPrompt(shot.id)}><Copy className="mr-1 h-3 w-3" />Copy prompt</Button></div></div><p className="mt-1 text-muted-foreground">{shot.vietnamese_description || shot.english_narration || 'Chưa có mô tả'}</p></div>)}</div>
            <div className="space-y-2">{project.shots?.map((shot) => <div key={`${shot.id}-mode`} className="flex items-center gap-2 text-xs"><span className="w-16">Shot {shot.shot_order}</span><select className="rounded border bg-background p-1" value={shot.speech_source_override ?? ''} onChange={(e) => void apiClient.updateNewsVideoShot(selectedId!, shot.id, { speech_mode: (e.target.value || null) as NewsSpeechMode }).then(() => detail.refetch())}><option value="">Theo project</option>{speechOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>)}</div>
            <AIVideoRenderPanel projectId={selectedId} shots={project.shots ?? []} targetLanguage={project.target_language as VideoLanguage} onNotice={setNotice} />
            <AIVideoPublishingMetadataPanel metadata={metadata.data} isLoading={metadata.isLoading} isGenerating={generateMetadata.isPending} disabled={!selectedId} projectTitle={project.title} onGenerateAll={() => generateMetadata.mutate('all')} onGeneratePlatform={(platform) => generateMetadata.mutate(platform)} />
          </>}
        </CardContent></Card>
      </div>
    </div>
  );
}
