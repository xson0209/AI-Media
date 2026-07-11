import { zodResolver } from '@hookform/resolvers/zod';
import { Mic, Monitor, Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { useAudioPlayer } from '@/lib/hooks/useAudioPlayer';
import { useAudioRecording } from '@/lib/hooks/useAudioRecording';
import { useAddSample, useProfile } from '@/lib/hooks/useProfiles';
import { useSystemAudioCapture } from '@/lib/hooks/useSystemAudioCapture';
import { useTranscription } from '@/lib/hooks/useTranscription';
import {
  type AudioSegmentSelection,
  formatAudioSegment,
  getAudioDuration,
  VOICE_SAMPLE_MAX_DURATION_SECONDS,
  VOICE_SAMPLE_RECORDING_MAX_DURATION_SECONDS,
} from '@/lib/utils/audio';
import { usePlatform } from '@/platform/PlatformContext';
import { AudioSampleRecording } from './AudioSampleRecording';
import { AudioSegmentPickerDialog } from './AudioSegmentPickerDialog';
import { AudioSampleSystem } from './AudioSampleSystem';
import { AudioSampleUpload } from './AudioSampleUpload';

const sampleSchema = z.object({
  file: z.instanceof(File, { message: 'Vui lòng chọn tệp âm thanh' }),
  referenceText: z
    .string()
    .min(1, 'Cần nhập văn bản tham chiếu')
    .max(1000, 'Văn bản tham chiếu phải dưới 1000 ký tự'),
});

type SampleFormValues = z.infer<typeof sampleSchema>;

interface SampleUploadProps {
  profileId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SampleUpload({ profileId, open, onOpenChange }: SampleUploadProps) {
  const { t } = useTranslation();
  const platform = usePlatform();
  const addSample = useAddSample();
  const transcribe = useTranscription();
  const { data: profile } = useProfile(profileId);
  const { toast } = useToast();
  const [mode, setMode] = useState<'upload' | 'record' | 'system'>('upload');
  const [audioDuration, setAudioDuration] = useState<number | null>(null);
  const [sampleSegment, setSampleSegment] = useState<AudioSegmentSelection | null>(null);
  const [segmentPickerOpen, setSegmentPickerOpen] = useState(false);
  const { isPlaying, playPause, cleanup: cleanupAudio } = useAudioPlayer();

  const form = useForm<SampleFormValues>({
    resolver: zodResolver(sampleSchema),
    defaultValues: {
      referenceText: '',
    },
  });

  const selectedFile = form.watch('file');
  const sampleRequiresSegment =
    audioDuration !== null && audioDuration > VOICE_SAMPLE_MAX_DURATION_SECONDS;
  const sampleSegmentLabel = sampleSegment
    ? t('audioSegmentPicker.selectedSegmentLabel', {
        range: formatAudioSegment(sampleSegment),
      })
    : sampleRequiresSegment
      ? t('audioSegmentPicker.segmentRequired')
      : undefined;
  const sampleTrimOptions = sampleSegment
    ? {
        trimStartSeconds: sampleSegment.startSeconds,
        trimDurationSeconds: sampleSegment.durationSeconds,
      }
    : undefined;

  const {
    isRecording,
    duration,
    error: recordingError,
    startRecording,
    stopRecording,
    cancelRecording,
  } = useAudioRecording({
    maxDurationSeconds: VOICE_SAMPLE_RECORDING_MAX_DURATION_SECONDS,
    onRecordingComplete: (blob, recordedDuration) => {
      // Convert blob to File object
      const file = new File([blob], `recording-${Date.now()}.webm`, {
        type: blob.type || 'audio/webm',
      }) as File & { recordedDuration?: number };
      // Store the actual recorded duration to bypass metadata reading issues on Windows
      if (recordedDuration !== undefined) {
        file.recordedDuration = recordedDuration;
      }
      form.setValue('file', file, { shouldValidate: true });
      toast({
        title: 'Ghi âm hoàn tất',
        description: 'Âm thanh đã được ghi thành công.',
      });
    },
  });

  const {
    isRecording: isSystemRecording,
    duration: systemDuration,
    error: systemRecordingError,
    isSupported: isSystemAudioSupported,
    startRecording: startSystemRecording,
    stopRecording: stopSystemRecording,
    cancelRecording: cancelSystemRecording,
  } = useSystemAudioCapture({
    maxDurationSeconds: VOICE_SAMPLE_RECORDING_MAX_DURATION_SECONDS,
    onRecordingComplete: (blob, recordedDuration) => {
      // Convert blob to File object
      const file = new File([blob], `system-audio-${Date.now()}.wav`, {
        type: blob.type || 'audio/wav',
      }) as File & { recordedDuration?: number };
      // Store the actual recorded duration to bypass metadata reading issues on Windows
      if (recordedDuration !== undefined) {
        file.recordedDuration = recordedDuration;
      }
      form.setValue('file', file, { shouldValidate: true });
      toast({
        title: 'Đã ghi âm thanh hệ thống',
        description: 'Âm thanh đã được ghi thành công.',
      });
    },
  });

  useEffect(() => {
    if (selectedFile && selectedFile instanceof File) {
      setSampleSegment(null);
      setSegmentPickerOpen(false);
      getAudioDuration(selectedFile as File & { recordedDuration?: number })
        .then((duration) => {
          setAudioDuration(duration);
          if (duration > VOICE_SAMPLE_MAX_DURATION_SECONDS) {
            form.clearErrors('file');
            setSegmentPickerOpen(true);
          } else {
            form.clearErrors('file');
          }
        })
        .catch((error) => {
          console.error('Failed to get audio duration:', error);
          setAudioDuration(null);
          const isRecordedFile =
            selectedFile.name.startsWith('recording-') ||
            selectedFile.name.startsWith('system-audio-');
          if (!isRecordedFile) {
            form.setError('file', {
              type: 'manual',
              message: t('profileForm.validation.audioFailed'),
            });
          } else {
            form.clearErrors('file');
          }
        });
    } else {
      setAudioDuration(null);
      setSampleSegment(null);
      setSegmentPickerOpen(false);
      form.clearErrors('file');
    }
  }, [selectedFile, form, t]);

  // Show recording errors
  useEffect(() => {
    if (recordingError) {
      toast({
        title: 'Lỗi ghi âm',
        description: recordingError,
        variant: 'destructive',
      });
    }
  }, [recordingError, toast]);

  // Show system audio recording errors
  useEffect(() => {
    if (systemRecordingError) {
      toast({
        title: 'Lỗi ghi âm thanh hệ thống',
        description: systemRecordingError,
        variant: 'destructive',
      });
    }
  }, [systemRecordingError, toast]);

  function requireConfirmedSegment(): boolean {
    if (!sampleRequiresSegment || sampleSegment) {
      return true;
    }

    form.setError('file', {
      type: 'manual',
      message: t('audioSegmentPicker.segmentRequired'),
    });
    setSegmentPickerOpen(true);
    return false;
  }

  async function handleTranscribe() {
    const file = form.getValues('file');
    if (!file) {
      toast({
        title: 'Chưa chọn tệp',
        description: 'Vui lòng chọn tệp âm thanh trước.',
        variant: 'destructive',
      });
      return;
    }

    if (!requireConfirmedSegment()) {
      return;
    }

    try {
      const language = profile?.language as 'en' | 'zh' | undefined;
      const result = await transcribe.mutateAsync({
        file,
        language,
        trimOptions: sampleTrimOptions,
      });

      form.setValue('referenceText', result.text, { shouldValidate: true });
    } catch (error) {
      toast({
        title: 'Chép lời thất bại',
        description: error instanceof Error ? error.message : 'Không thể chép lời âm thanh',
        variant: 'destructive',
      });
    }
  }

  async function onSubmit(data: SampleFormValues) {
    if (!requireConfirmedSegment()) {
      return;
    }

    try {
      await addSample.mutateAsync({
        profileId,
        file: data.file,
        referenceText: data.referenceText,
        trimOptions: sampleTrimOptions,
      });

      toast({
        title: 'Đã thêm mẫu',
        description: 'Mẫu âm thanh đã được thêm thành công.',
      });

      handleOpenChange(false);
    } catch (error) {
      toast({
        title: 'Lỗi',
        description: error instanceof Error ? error.message : 'Không thể thêm mẫu',
        variant: 'destructive',
      });
    }
  }

  function handleOpenChange(newOpen: boolean) {
    if (!newOpen) {
      form.reset();
      setMode('upload');
      setAudioDuration(null);
      setSampleSegment(null);
      setSegmentPickerOpen(false);
      if (isRecording) {
        cancelRecording();
      }
      if (isSystemRecording) {
        cancelSystemRecording();
      }
      cleanupAudio();
    }
    onOpenChange(newOpen);
  }

  function handleCancelRecording() {
    if (mode === 'record') {
      cancelRecording();
    } else if (mode === 'system') {
      cancelSystemRecording();
    }
    form.resetField('file');
    setAudioDuration(null);
    setSampleSegment(null);
    setSegmentPickerOpen(false);
    cleanupAudio();
  }

  function handlePlayPause() {
    const file = form.getValues('file');
    playPause(file, sampleSegment ?? undefined);
  }

  function handleSegmentCancel() {
    setSegmentPickerOpen(false);
    if (!sampleSegment) {
      form.resetField('file');
      setAudioDuration(null);
    }
    cleanupAudio();
  }

  function handleSegmentConfirm(selection: AudioSegmentSelection) {
    setSampleSegment(selection);
    setSegmentPickerOpen(false);
    form.clearErrors('file');
    cleanupAudio();
  }

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Thêm mẫu âm thanh</DialogTitle>
            <DialogDescription>
              Tải lên tệp âm thanh và cung cấp văn bản tham chiếu khớp với âm thanh.
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <Tabs
                value={mode}
                onValueChange={(v) => setMode(v as 'upload' | 'record' | 'system')}
              >
                <TabsList
                  className={`grid w-full ${platform.metadata.isTauri && isSystemAudioSupported ? 'grid-cols-3' : 'grid-cols-2'}`}
                >
                  <TabsTrigger value="upload" className="flex items-center gap-2">
                    <Upload className="h-4 w-4 shrink-0" />
                    Tải lên
                  </TabsTrigger>
                  <TabsTrigger value="record" className="flex items-center gap-2">
                    <Mic className="h-4 w-4 shrink-0" />
                    Ghi âm
                  </TabsTrigger>
                  {platform.metadata.isTauri && isSystemAudioSupported && (
                    <TabsTrigger value="system" className="flex items-center gap-2">
                      <Monitor className="h-4 w-4 shrink-0" />
                      Âm thanh hệ thống
                    </TabsTrigger>
                  )}
                </TabsList>

                <TabsContent value="upload" className="space-y-4">
                  <FormField
                    control={form.control}
                    name="file"
                    render={({ field: { onChange, name } }) => (
                      <AudioSampleUpload
                        file={selectedFile}
                        onFileChange={onChange}
                        onTranscribe={handleTranscribe}
                        onPlayPause={handlePlayPause}
                        segmentLabel={sampleSegmentLabel}
                        onEditSegment={
                          sampleRequiresSegment ? () => setSegmentPickerOpen(true) : undefined
                        }
                        isPlaying={isPlaying}
                        isTranscribing={transcribe.isPending}
                        isDisabled={sampleRequiresSegment && !sampleSegment}
                        fieldName={name}
                      />
                    )}
                  />
                </TabsContent>

                <TabsContent value="record" className="space-y-4">
                  <FormField
                    control={form.control}
                    name="file"
                    render={() => (
                      <AudioSampleRecording
                        file={selectedFile}
                        isRecording={isRecording}
                        duration={duration}
                        onStart={startRecording}
                        onStop={stopRecording}
                        onCancel={handleCancelRecording}
                        onTranscribe={handleTranscribe}
                        onPlayPause={handlePlayPause}
                        isPlaying={isPlaying}
                        isTranscribing={transcribe.isPending}
                      />
                    )}
                  />
                </TabsContent>

                {platform.metadata.isTauri && isSystemAudioSupported && (
                  <TabsContent value="system" className="space-y-4">
                    <FormField
                      control={form.control}
                      name="file"
                      render={() => (
                        <AudioSampleSystem
                          file={selectedFile}
                          isRecording={isSystemRecording}
                          duration={systemDuration}
                          onStart={startSystemRecording}
                          onStop={stopSystemRecording}
                          onCancel={handleCancelRecording}
                          onTranscribe={handleTranscribe}
                          onPlayPause={handlePlayPause}
                          isPlaying={isPlaying}
                          isTranscribing={transcribe.isPending}
                        />
                      )}
                    />
                  </TabsContent>
                )}
              </Tabs>

              <FormField
                control={form.control}
                name="referenceText"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Văn bản tham chiếu</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Nhập đúng nội dung được nói trong âm thanh..."
                        className="min-h-[100px]"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                  Hủy
                </Button>
                <Button type="submit" disabled={addSample.isPending}>
                  {addSample.isPending ? 'Đang tải lên...' : 'Thêm mẫu'}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
      <AudioSegmentPickerDialog
        file={selectedFile}
        open={segmentPickerOpen && !!selectedFile && sampleRequiresSegment}
        audioDurationSeconds={audioDuration ?? 0}
        maxDurationSeconds={VOICE_SAMPLE_MAX_DURATION_SECONDS}
        initialStartSeconds={sampleSegment?.startSeconds}
        onConfirm={handleSegmentConfirm}
        onCancel={handleSegmentCancel}
      />
    </>
  );
}
