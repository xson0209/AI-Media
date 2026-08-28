import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  redirect,
  useRouterState,
} from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { AppFrame } from '@/components/AppFrame/AppFrame';
import { AIVideoAssistant } from '@/components/AIVideoAssistant/AIVideoAssistant';
import { CapturesTab } from '@/components/CapturesTab/CapturesTab';
import { EffectsTab } from '@/components/EffectsTab/EffectsTab';
import { MainEditor } from '@/components/MainEditor/MainEditor';
import { ModelsTab } from '@/components/ModelsTab/ModelsTab';
import { AboutPage } from '@/components/ServerTab/AboutPage';
import { AIPlanningPage } from '@/components/ServerTab/AIPlanningPage';
import { CapturesPage } from '@/components/ServerTab/CapturesPage';
import { ChangelogPage } from '@/components/ServerTab/ChangelogPage';
import { GeneralPage } from '@/components/ServerTab/GeneralPage';
import { GenerationPage } from '@/components/ServerTab/GenerationPage';
import { GpuPage } from '@/components/ServerTab/GpuPage';
import { LogsPage } from '@/components/ServerTab/LogsPage';
import { MCPPage } from '@/components/ServerTab/MCPPage';
import { SettingsLayout } from '@/components/ServerTab/ServerTab';
import { Sidebar } from '@/components/Sidebar';
import { StoriesTab } from '@/components/StoriesTab/StoriesTab';
import { StoryStudio } from '@/components/StoryStudio/StoryStudio';
import { Toaster } from '@/components/ui/toaster';
import { ComicSeriesAnalysis } from '@/components/ComicSeriesAnalysis/ComicSeriesAnalysis';
import { VideoInspiration } from '@/components/VideoInspiration/VideoInspiration';
import { VoicesTab } from '@/components/VoicesTab/VoicesTab';
import { useGenerationProgress } from '@/lib/hooks/useGenerationProgress';
import { useModelDownloadToast } from '@/lib/hooks/useModelDownloadToast';
import { MODEL_DISPLAY_NAMES, useRestoreActiveTasks } from '@/lib/hooks/useRestoreActiveTasks';
import { cn } from '@/lib/utils/cn';

const researchFeatureEnabled = import.meta.env.VITE_FEATURE_RESEARCH !== 'false';
const ResearchWorkspace = lazy(async () => {
  const module = await import('@/components/ResearchWorkspace/ResearchWorkspace');
  return { default: module.ResearchWorkspace };
});

const ProductVideo = lazy(async () => {
  const module = await import('@/components/ProductVideo/ProductVideo');
  return { default: module.ProductVideo };
});

function ProductVideoRoute() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-0 flex-1 items-center justify-center" aria-live="polite">
          <span className="text-sm text-muted-foreground">Đang mở luồng video sản phẩm...</span>
        </div>
      }
    >
      <ProductVideo />
    </Suspense>
  );
}

function ResearchWorkspaceRoute() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-0 flex-1 items-center justify-center" aria-live="polite">
          <span className="text-sm text-muted-foreground">Đang mở không gian nghiên cứu...</span>
        </div>
      }
    >
      <ResearchWorkspace />
    </Suspense>
  );
}

// Simple platform check that works in both web and Tauri
const isMacOS = () => navigator.platform.toLowerCase().includes('mac');

// Root layout component
function RootLayout() {
  const routerState = useRouterState();
  const isWideWorkspace =
    routerState.location.pathname === '/ai-video' ||
    routerState.location.pathname === '/product-video' ||
    routerState.location.pathname === '/story-studio' ||
    routerState.location.pathname === '/video-inspiration' ||
    routerState.location.pathname === '/research' ||
    routerState.location.pathname.startsWith('/comic-series-analysis');

  // Monitor active downloads/generations and show toasts for them
  const activeDownloads = useRestoreActiveTasks();

  // Subscribe to SSE for pending generations — handles completion, auto-play, and history refresh
  useGenerationProgress();

  return (
    <AppFrame>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar isMacOS={isMacOS()} />

        <main className="flex-1 ml-20 overflow-hidden flex flex-col">
          <div
            className={cn(
              'h-full overflow-hidden flex flex-col',
              isWideWorkspace ? 'w-full px-2 sm:px-3' : 'container mx-auto px-8 max-w-[1800px]',
            )}
          >
            <Outlet />
          </div>
        </main>
      </div>

      {/* Show download toasts for any active downloads (from anywhere) */}
      {activeDownloads.map((download) => {
        const displayName = MODEL_DISPLAY_NAMES[download.model_name] || download.model_name;
        return (
          <DownloadToastRestorer
            key={download.model_name}
            modelName={download.model_name}
            displayName={displayName}
          />
        );
      })}

      <Toaster />
    </AppFrame>
  );
}

/**
 * Component that restores a download toast for a specific model.
 */
function DownloadToastRestorer({
  modelName,
  displayName,
}: {
  modelName: string;
  displayName: string;
}) {
  // Use the download toast hook to restore the toast
  useModelDownloadToast({
    modelName,
    displayName,
    enabled: true,
  });

  return null;
}

// Root route with layout
const rootRoute = createRootRoute({
  component: RootLayout,
});

// Index route: AI Video is the local default workspace.
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/ai-video' });
  },
});

// Generate route (existing Voice/TTS workspace)
const generateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/generate',
  component: MainEditor,
});

// Stories route
const storiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/stories',
  component: StoriesTab,
});

// Voices route
const voicesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/voices',
  component: VoicesTab,
});

// Captures route (prototype — will replace AudioTab once the new flow is ready)
const capturesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/captures',
  component: CapturesTab,
});

// Effects route
const effectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/effects',
  component: EffectsTab,
});

const aiVideoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ai-video',
  component: AIVideoAssistant,
});

const productVideoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/product-video',
  component: ProductVideoRoute,
});

const storyStudioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/story-studio',
  component: StoryStudio,
  // Deep-link from Comic Series Analysis handoff (task 9.7). Missing or
  // unknown ids are tolerated — the component falls back gracefully.
  validateSearch: (search: Record<string, unknown>): { seriesId?: string; episodeId?: string } => ({
    seriesId: typeof search.seriesId === 'string' ? search.seriesId : undefined,
    episodeId: typeof search.episodeId === 'string' ? search.episodeId : undefined,
  }),
});

const comicSeriesAnalysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/comic-series-analysis',
  component: ComicSeriesAnalysis,
});

const comicSeriesAnalysisDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/comic-series-analysis/$analysisId',
  component: ComicSeriesAnalysis,
});

const videoInspirationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/video-inspiration',
  component: VideoInspiration,
});

// Models route
const modelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models',
  component: ModelsTab,
});

// Settings layout route (parent for sub-tabs)
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsLayout,
});

// Settings sub-routes
const settingsGeneralRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/',
  component: GeneralPage,
});

const settingsGenerationRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/generation',
  component: GenerationPage,
});

const settingsCapturesRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/captures',
  component: CapturesPage,
});

const settingsMCPRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/mcp',
  component: MCPPage,
});

const researchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research',
  component: ResearchWorkspaceRoute,
  beforeLoad: () => {
    if (!researchFeatureEnabled) {
      throw redirect({ to: '/ai-video' });
    }
  },
});

const settingsAIPlanningRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/ai-planning',
  component: AIPlanningPage,
});

const settingsGpuRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/gpu',
  component: GpuPage,
});

const settingsChangelogRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/changelog',
  component: ChangelogPage,
});

const settingsLogsRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/logs',
  component: LogsPage,
});

const settingsAboutRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: '/about',
  component: AboutPage,
});

// Redirect old /server path to /settings
const serverRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/server',
  beforeLoad: () => {
    throw redirect({ to: '/settings' });
  },
});

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute,
  generateRoute,
  storiesRoute,
  capturesRoute,
  voicesRoute,
  effectsRoute,
  videoInspirationRoute,
  researchRoute,
  comicSeriesAnalysisRoute,
  comicSeriesAnalysisDetailRoute,
  aiVideoRoute,
  productVideoRoute,
  storyStudioRoute,
  modelsRoute,
  settingsRoute.addChildren([
    settingsGeneralRoute,
    settingsGenerationRoute,
    settingsCapturesRoute,
    settingsMCPRoute,
    settingsAIPlanningRoute,
    settingsGpuRoute,
    settingsLogsRoute,
    settingsChangelogRoute,
    settingsAboutRoute,
  ]),
  serverRedirectRoute,
]);

// Create router
export const router = createRouter({ routeTree });

// Register router for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
