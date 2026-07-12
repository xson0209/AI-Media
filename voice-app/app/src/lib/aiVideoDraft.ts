export const AI_VIDEO_DRAFT_STORAGE_KEY = 'voicebox.aiVideoDraft.v1';

export interface AIVideoDraftSourceBlock {
  block_type: string;
  content: string;
}

export interface AIVideoFormDraft {
  source: 'video-inspiration';
  createdAt: string;
  title?: string;
  visualStyle?: string;
  sources: AIVideoDraftSourceBlock[];
  notice?: string;
}
