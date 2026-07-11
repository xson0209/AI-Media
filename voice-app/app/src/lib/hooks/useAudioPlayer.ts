import { useRef, useState } from 'react';
import { useToast } from '@/components/ui/use-toast';

interface PlaybackSegment {
  startSeconds: number;
  durationSeconds: number;
}

export function useAudioPlayer() {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentFileRef = useRef<File | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const segmentEndRef = useRef<number | null>(null);
  const { toast } = useToast();

  const cleanupCurrentAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    currentFileRef.current = null;
    segmentEndRef.current = null;
  };

  const playPause = (file: File | null | undefined, segment?: PlaybackSegment) => {
    if (!file) return;

    const segmentEnd = segment ? segment.startSeconds + segment.durationSeconds : null;

    if (audioRef.current && currentFileRef.current !== file) {
      cleanupCurrentAudio();
      setIsPlaying(false);
    }

    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        segmentEndRef.current = segmentEnd;
        if (segment) {
          audioRef.current.currentTime = segment.startSeconds;
        }
        audioRef.current.play();
        setIsPlaying(true);
      }
    } else {
      const objectUrl = URL.createObjectURL(file);
      const audio = new Audio(objectUrl);
      audioRef.current = audio;
      currentFileRef.current = file;
      objectUrlRef.current = objectUrl;
      segmentEndRef.current = segmentEnd;
      if (segment) {
        audio.currentTime = segment.startSeconds;
      }

      audio.addEventListener('timeupdate', () => {
        const end = segmentEndRef.current;
        if (end !== null && audio.currentTime >= end) {
          cleanupCurrentAudio();
          setIsPlaying(false);
        }
      });

      audio.addEventListener('ended', () => {
        setIsPlaying(false);
        cleanupCurrentAudio();
      });

      audio.addEventListener('error', () => {
        setIsPlaying(false);
        toast({
          title: 'Playback error',
          description: 'Failed to play audio file',
          variant: 'destructive',
        });
        cleanupCurrentAudio();
      });

      audio.play();
      setIsPlaying(true);
    }
  };

  const cleanup = () => {
    cleanupCurrentAudio();
    setIsPlaying(false);
  };

  return {
    isPlaying,
    playPause,
    cleanup,
  };
}
