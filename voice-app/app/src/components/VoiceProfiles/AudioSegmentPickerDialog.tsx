import { Check, Pause, Play } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Slider } from '@/components/ui/slider';
import {
  type AudioSegmentSelection,
  formatAudioDuration,
  formatAudioSegment,
} from '@/lib/utils/audio';

interface AudioSegmentPickerDialogProps {
  file: File | null | undefined;
  open: boolean;
  audioDurationSeconds: number;
  maxDurationSeconds: number;
  initialStartSeconds?: number;
  onConfirm: (selection: AudioSegmentSelection) => void;
  onCancel: () => void;
}

export function AudioSegmentPickerDialog({
  file,
  open,
  audioDurationSeconds,
  maxDurationSeconds,
  initialStartSeconds = 0,
  onConfirm,
  onCancel,
}: AudioSegmentPickerDialogProps) {
  const { t } = useTranslation();
  const [segmentStartSeconds, setSegmentStartSeconds] = useState(0);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);

  const segmentDurationSeconds = Math.min(maxDurationSeconds, audioDurationSeconds);
  const maxStartSeconds = Math.max(0, audioDurationSeconds - segmentDurationSeconds);
  const clampedStartSeconds = Math.min(segmentStartSeconds, maxStartSeconds);
  const selection = useMemo<AudioSegmentSelection>(
    () => ({
      startSeconds: clampedStartSeconds,
      durationSeconds: segmentDurationSeconds,
      totalDurationSeconds: audioDurationSeconds,
    }),
    [audioDurationSeconds, clampedStartSeconds, segmentDurationSeconds],
  );

  useEffect(() => {
    if (!file || !open) {
      return;
    }

    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    setSegmentStartSeconds(Math.min(Math.max(0, initialStartSeconds), maxStartSeconds));

    return () => {
      URL.revokeObjectURL(url);
      setObjectUrl(null);
    };
  }, [file, initialStartSeconds, maxStartSeconds, open]);

  const stopPreview = useCallback(() => {
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
    }
    setIsPreviewing(false);
  }, []);

  useEffect(() => {
    return () => stopPreview();
  }, [stopPreview]);

  function handlePreview() {
    if (!objectUrl) {
      return;
    }

    if (isPreviewing) {
      stopPreview();
      return;
    }

    const audio = new Audio(objectUrl);
    const endSeconds = selection.startSeconds + selection.durationSeconds;
    audio.currentTime = selection.startSeconds;
    previewAudioRef.current = audio;

    audio.addEventListener('timeupdate', () => {
      if (audio.currentTime >= endSeconds) {
        stopPreview();
      }
    });
    audio.addEventListener('ended', stopPreview);
    audio.addEventListener('error', stopPreview);

    audio
      .play()
      .then(() => setIsPreviewing(true))
      .catch(stopPreview);
  }

  function handleCancel() {
    stopPreview();
    onCancel();
  }

  function handleConfirm() {
    stopPreview();
    onConfirm(selection);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          handleCancel();
        }
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('audioSegmentPicker.title')}</DialogTitle>
          <DialogDescription>{t('audioSegmentPicker.description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="rounded-md border bg-muted/30 p-3 text-sm">
            <div className="truncate font-medium">{file?.name}</div>
            <div className="mt-1 text-muted-foreground">
              {t('audioSegmentPicker.totalDuration', {
                duration: formatAudioDuration(audioDurationSeconds),
              })}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{t('audioSegmentPicker.selectedRange')}</span>
              <span className="tabular-nums text-muted-foreground">
                {formatAudioSegment(selection)}
              </span>
            </div>
            <Slider
              value={[clampedStartSeconds]}
              min={0}
              max={maxStartSeconds}
              step={0.1}
              disabled={maxStartSeconds <= 0}
              onValueChange={(value) => {
                stopPreview();
                setSegmentStartSeconds(value[0] ?? 0);
              }}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{formatAudioDuration(0)}</span>
              <span>
                {t('audioSegmentPicker.segmentDuration', {
                  duration: formatAudioDuration(segmentDurationSeconds),
                })}
              </span>
              <span>{formatAudioDuration(audioDurationSeconds)}</span>
            </div>
          </div>

          <Button type="button" variant="outline" onClick={handlePreview} className="gap-2">
            {isPreviewing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {isPreviewing ? t('audioSegmentPicker.stopPreview') : t('audioSegmentPicker.preview')}
          </Button>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
          <Button type="button" onClick={handleConfirm} className="gap-2">
            <Check className="h-4 w-4" />
            {t('audioSegmentPicker.useSegment')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
