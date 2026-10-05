import { useNavigate, useRouter, useSearch } from '@tanstack/react-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AI_VIDEO_DRAFT_STORAGE_KEY,
  type AIVideoFormDraft,
  parseAIVideoFormDraft,
} from '../aiVideoDraft';

export interface AIVideoProjectSearch {
  projectId?: string;
  draft?: 'video-inspiration';
}

export function parseAIVideoProjectSearch(search: Record<string, unknown>): AIVideoProjectSearch {
  return {
    projectId:
      typeof search.projectId === 'string' && search.projectId.trim()
        ? search.projectId.trim()
        : undefined,
    draft: search.draft === 'video-inspiration' ? 'video-inspiration' : undefined,
  };
}

interface DraftReceipt {
  draft: AIVideoFormDraft | null;
  notice: string | null;
}

const emptyReceipt: DraftReceipt = { draft: null, notice: null };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Owns project selection, navigation and the lifetime of an incoming form draft. */
export function useAIVideoProjectSession() {
  const search = useSearch({ from: '/ai-video' });
  const navigate = useNavigate({ from: '/ai-video' });
  const router = useRouter();
  const [receipt, setReceipt] = useState<DraftReceipt>(emptyReceipt);
  const receivedRawDraft = useRef<string | null>(null);
  const draftSource = search.draft;

  const receiveDraft = useCallback((source: AIVideoProjectSearch['draft']) => {
    if (source !== 'video-inspiration') {
      receivedRawDraft.current = null;
      setReceipt(emptyReceipt);
      return;
    }

    let raw: string | null;
    try {
      raw = window.sessionStorage.getItem(AI_VIDEO_DRAFT_STORAGE_KEY);
    } catch (error) {
      setReceipt({
        draft: null,
        notice: `Chưa đọc được bản nháp từ Video Inspiration: ${errorMessage(error)}`,
      });
      return;
    }
    if (!raw) {
      setReceipt({
        draft: null,
        notice:
          'Không còn bản nháp từ Video Inspiration. Hãy mở lại chất liệu từ Video Inspiration hoặc chọn dự án khác.',
      });
      return;
    }
    if (raw === receivedRawDraft.current) return;

    try {
      const draft = parseAIVideoFormDraft(raw);
      receivedRawDraft.current = raw;
      setReceipt({
        draft,
        notice:
          draft.notice ||
          'Đã đưa dữ liệu từ Video Inspiration vào form. Hãy chọn cấu hình rồi mới tạo dự án.',
      });
    } catch (error) {
      setReceipt({
        draft: null,
        notice: `Bản nháp từ Video Inspiration không hợp lệ: ${errorMessage(error)}`,
      });
    }
  }, []);

  useEffect(() => {
    receiveDraft(draftSource);
  }, [draftSource, receiveDraft]);

  useEffect(
    () =>
      router.subscribe('onResolved', (event) => {
        if (event.toLocation.pathname === '/ai-video') {
          receiveDraft(parseAIVideoProjectSearch(event.toLocation.search).draft);
        }
      }),
    [router, receiveDraft],
  );

  const selectProject = useCallback(
    (projectId: string | null) => {
      const consumedRawDraft = receivedRawDraft.current;
      void navigate({
        to: '/ai-video',
        search: (current) => ({ ...current, projectId: projectId || undefined, draft: undefined }),
      })
        .then(() => {
          if (!consumedRawDraft) return;
          try {
            // Another handoff may have replaced the draft while navigation was pending.
            if (window.sessionStorage.getItem(AI_VIDEO_DRAFT_STORAGE_KEY) === consumedRawDraft) {
              window.sessionStorage.removeItem(AI_VIDEO_DRAFT_STORAGE_KEY);
            }
          } catch (error) {
            setReceipt((current) => ({
              ...current,
              notice: `Đã chuyển dự án, nhưng chưa xoá được bản nháp tạm: ${errorMessage(error)}`,
            }));
          }
        })
        .catch((error: unknown) => {
          setReceipt((current) => ({
            ...current,
            notice: `Chưa chuyển được dự án: ${errorMessage(error)}`,
          }));
        });
    },
    [navigate],
  );

  return {
    selectedProjectId: draftSource === 'video-inspiration' ? null : (search.projectId ?? null),
    incomingDraft: draftSource === 'video-inspiration' ? receipt.draft : null,
    sessionNotice: receipt.notice,
    selectProject,
  };
}
