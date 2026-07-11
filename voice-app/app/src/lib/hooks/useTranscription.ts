import { useMutation } from '@tanstack/react-query';
import { apiClient, type AudioTrimOptions } from '@/lib/api/client';
import type { WhisperModelSize } from '@/lib/api/types';
import type { LanguageCode } from '@/lib/constants/languages';

export function useTranscription() {
  return useMutation({
    mutationFn: ({
      file,
      language,
      model,
      trimOptions,
    }: {
      file: File;
      language?: LanguageCode;
      model?: WhisperModelSize;
      trimOptions?: AudioTrimOptions;
    }) => apiClient.transcribeAudio(file, language, model, trimOptions),
  });
}
