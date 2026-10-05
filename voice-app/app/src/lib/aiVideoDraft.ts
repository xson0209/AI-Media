import type {
  CallToActionStyle,
  CtaAction,
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
  ctaAction?: CtaAction;
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

export function parseAIVideoFormDraft(raw: string): AIVideoFormDraft {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Bản nháp phải là một object.');
  }
  const draft = value as Record<string, unknown>;
  if (draft.source !== 'video-inspiration' || !Array.isArray(draft.sources)) {
    throw new Error('Bản nháp thiếu nguồn Video Inspiration hoặc danh sách chất liệu.');
  }
  for (const source of draft.sources) {
    if (
      !source ||
      typeof source !== 'object' ||
      typeof source.block_type !== 'string' ||
      typeof source.content !== 'string'
    ) {
      throw new Error('Chất liệu trong bản nháp phải có loại và nội dung dạng văn bản.');
    }
  }
  for (const key of [
    'createdAt',
    'title',
    'visualStyle',
    'notice',
    'targetLanguage',
    'videoPurpose',
    'dialogueMode',
    'narrationDensity',
    'callToActionStyle',
    'ctaAction',
  ]) {
    if (draft[key] !== undefined && typeof draft[key] !== 'string') {
      throw new Error(`Trường ${key} trong bản nháp phải là văn bản.`);
    }
  }
  if (
    draft.preserveConfiguration !== undefined &&
    typeof draft.preserveConfiguration !== 'boolean'
  ) {
    throw new Error('preserveConfiguration trong bản nháp phải là boolean.');
  }
  return value as AIVideoFormDraft;
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
    ctaAction: 'none',
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
  if (draft.ctaAction) config.ctaAction = draft.ctaAction;
  return config;
}
