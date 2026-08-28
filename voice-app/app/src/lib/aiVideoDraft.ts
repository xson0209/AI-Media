import type {
  CallToActionStyle,
  DialogueMode,
  NarrationDensity,
  VideoPurpose,
} from './api/types';
import type { LanguageCode } from './constants/languages';

export const AI_VIDEO_DRAFT_STORAGE_KEY = 'voicebox.aiVideoDraft.v1';

export interface AIVideoDraftSourceBlock {
  block_type: string;
  content: string;
}

export interface AIVideoDraftFormConfig {
  targetLanguage?: LanguageCode;
  videoPurpose?: VideoPurpose;
  dialogueMode?: DialogueMode;
  narrationDensity?: NarrationDensity;
  callToActionStyle?: CallToActionStyle;
}

export interface AIVideoFormDraft extends AIVideoDraftFormConfig {
  source: 'video-inspiration';
  preserveConfiguration?: boolean;
  createdAt: string;
  title?: string;
  visualStyle?: string;
  sources: AIVideoDraftSourceBlock[];
  notice?: string;
}

export function videoInspirationDraftConfig(
  targetLanguage: LanguageCode,
): Required<AIVideoDraftFormConfig> {
  return {
    targetLanguage,
    videoPurpose: 'custom',
    dialogueMode: 'voiceover',
    narrationDensity: 'balanced',
    callToActionStyle: 'none',
  };
}

export function aiVideoDraftFormConfig(draft: AIVideoFormDraft): AIVideoDraftFormConfig {
  const config: AIVideoDraftFormConfig = {};
  if (draft.preserveConfiguration) return config;
  if (draft.targetLanguage) config.targetLanguage = draft.targetLanguage;
  if (draft.videoPurpose) config.videoPurpose = draft.videoPurpose;
  if (draft.dialogueMode) config.dialogueMode = draft.dialogueMode;
  if (draft.narrationDensity) config.narrationDensity = draft.narrationDensity;
  if (draft.callToActionStyle) config.callToActionStyle = draft.callToActionStyle;
  return config;
}
