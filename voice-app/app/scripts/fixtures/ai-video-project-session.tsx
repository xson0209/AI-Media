import { createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router';
import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AI_VIDEO_DRAFT_STORAGE_KEY, aiVideoDraftFormConfig } from '../../src/lib/aiVideoDraft';
import {
  parseAIVideoProjectSearch,
  useAIVideoProjectSession,
} from '../../src/lib/hooks/useAIVideoProjectSession';

function Workspace() {
  const session = useAIVideoProjectSession();
  const [title, setTitle] = useState('Current form');
  const [language, setLanguage] = useState('en');
  const [hydrations, setHydrations] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!session.incomingDraft) return;
    setTitle(session.incomingDraft.title?.trim() || '');
    const config = aiVideoDraftFormConfig(session.incomingDraft);
    if (config.targetLanguage) setLanguage(config.targetLanguage);
    setHydrations((count) => count + 1);
  }, [session.incomingDraft]);

  useEffect(() => {
    Object.assign(window, {
      sessionFixture: {
        openDraft: (draft: unknown) => {
          window.sessionStorage.setItem(AI_VIDEO_DRAFT_STORAGE_KEY, JSON.stringify(draft));
          return router.navigate({ to: '/ai-video', search: { draft: 'video-inspiration' } });
        },
        replaceDraftAndSelect: (draft: unknown, projectId: string) => {
          window.sessionStorage.setItem(AI_VIDEO_DRAFT_STORAGE_KEY, JSON.stringify(draft));
          session.selectProject(projectId);
        },
      },
    });
  }, [session.selectProject]);

  return (
    <main>
      <output id="selected">{session.selectedProjectId ?? 'none'}</output>
      <output id="notice">{session.sessionNotice ?? ''}</output>
      <output id="hydrations">{hydrations}</output>
      <output id="language">{language}</output>
      <output id="revision">{revision}</output>
      <input
        aria-label="Draft title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <button type="button" onClick={() => session.selectProject('B')}>
        Select B
      </button>
      <button type="button" onClick={() => session.selectProject('C')}>
        Created C
      </button>
      <button type="button" onClick={() => session.selectProject(null)}>
        Clear selection
      </button>
      <button type="button" onClick={() => setRevision((value) => value + 1)}>
        Refresh workspace
      </button>
    </main>
  );
}

const rootRoute = createRootRoute();
const aiVideoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ai-video',
  component: Workspace,
  validateSearch: parseAIVideoProjectSearch,
});
const router = createRouter({ routeTree: rootRoute.addChildren([aiVideoRoute]) });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
