import { Link, useMatchRoute } from '@tanstack/react-router';
import {
  ArrowUp,
  AudioLines,
  BookImage,
  BookOpenCheck,
  BookOpenText,
  Box,
  Captions,
  Clapperboard,
  FileVideo,
  type LucideIcon,
  Mic,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sparkles,
  Volume2,
  Wand2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import voiceboxLogo from '@/assets/voicebox-logo.png';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';
import type { UpdateStatus } from '@/platform/types';
import { usePlayerStore } from '@/stores/playerStore';
import { version } from '../../package.json';

const researchFeatureEnabled = import.meta.env.VITE_FEATURE_RESEARCH !== 'false';

interface SidebarProps {
  isMacOS?: boolean;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
}

const tabs: Array<{
  id: string;
  path: string;
  icon: LucideIcon;
  labelKey?: string;
  label?: string;
}> = [
  { id: 'main', path: '/generate', icon: Volume2, labelKey: 'nav.generate' },
  { id: 'stories', path: '/stories', icon: AudioLines, labelKey: 'nav.stories' },
  { id: 'captures', path: '/captures', icon: Captions, labelKey: 'nav.captures' },
  { id: 'voices', path: '/voices', icon: Mic, labelKey: 'nav.voices' },
  { id: 'effects', path: '/effects', icon: Wand2, labelKey: 'nav.effects' },
  {
    id: 'video-inspiration',
    path: '/video-inspiration',
    icon: FileVideo,
    label: 'Lấy cảm hứng từ video',
  },
  { id: 'research', path: '/research', icon: BookOpenCheck, label: 'Nghiên cứu ý tưởng' },
  { id: 'ai-video', path: '/ai-video', icon: Clapperboard, label: 'Dự án prompt video' },
  { id: 'news-video', path: '/news-video', icon: Clapperboard, label: 'Video tin tức' },
  { id: 'product-video', path: '/product-video', icon: Package, label: 'Prompt video sản phẩm' },
  {
    id: 'content-tools',
    path: '/content-tools',
    icon: Sparkles,
    label: 'Tạo nội dung thành video',
  },
  {
    id: 'comic-series-analysis',
    path: '/comic-series-analysis',
    icon: BookImage,
    label: 'Phân tích truyện tranh',
  },
  { id: 'story-studio', path: '/story-studio', icon: BookOpenText, label: 'Story Studio' },
  { id: 'models', path: '/models', icon: Box, labelKey: 'nav.models' },
  { id: 'settings', path: '/settings', icon: Settings, labelKey: 'nav.settings' },
];

export function Sidebar({ isMacOS, expanded, onExpandedChange }: SidebarProps) {
  const { t } = useTranslation();
  const matchRoute = useMatchRoute();
  const isPlayerOpen = !!usePlayerStore((s) => s.audioUrl);
  const platform = usePlatform();

  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>(platform.updater.getStatus());
  useEffect(() => platform.updater.subscribe(setUpdateStatus), [platform.updater]);

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-30 flex h-full flex-col overflow-hidden border-r border-border bg-sidebar py-6 transition-[width] duration-200 ease-out',
        expanded ? 'w-[260px]' : 'w-20',
        isMacOS && 'pt-14',
      )}
      aria-label="Điều hướng chính"
    >
      {/* Brand and menu toggle */}
      <div
        className={cn(
          'mb-2 flex w-full shrink-0 items-center gap-3 px-3',
          expanded ? 'justify-between' : 'flex-col',
        )}
      >
        <img
          src={voiceboxLogo}
          alt="Voicebox"
          className="sidebar-logo h-12 w-12 shrink-0 object-contain"
        />
        <button
          type="button"
          onClick={() => onExpandedChange(!expanded)}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label={expanded ? 'Thu gọn menu' : 'Mở rộng menu'}
          aria-expanded={expanded}
          aria-controls="sidebar-navigation"
          title={expanded ? 'Thu gọn menu' : 'Mở rộng menu'}
        >
          {expanded ? (
            <PanelLeftClose className="h-5 w-5" aria-hidden="true" />
          ) : (
            <PanelLeftOpen className="h-5 w-5" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav
        id="sidebar-navigation"
        className={cn('min-h-0 flex-1 overflow-y-auto', expanded ? 'w-full px-3' : 'w-full px-4')}
        aria-label="Các khu vực"
      >
        <div className="flex flex-col gap-2">
          {tabs
            .filter((tab) => researchFeatureEnabled || tab.id !== 'research')
            .map((tab, index) => {
              const Icon = tab.icon;
              const isActive =
                tab.path === '/'
                  ? matchRoute({ to: '/', fuzzy: false })
                  : matchRoute({ to: tab.path, fuzzy: true });

              // Accent fades as buttons get further from the logo
              const accentOpacity = Math.max(0.08, 0.5 - index * 0.07);

              return (
                <Link
                  key={tab.id}
                  to={tab.path}
                  className={cn(
                    'relative flex items-center overflow-hidden transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                    expanded
                      ? 'min-h-11 w-full gap-3 rounded-xl px-3'
                      : 'mx-auto h-12 w-12 justify-center rounded-full',
                    isActive
                      ? 'bg-white/[0.07] text-foreground shadow-lg backdrop-blur-sm border border-white/[0.08]'
                      : 'text-muted-foreground hover:bg-muted/50',
                  )}
                  title={tab.label ?? (tab.labelKey ? t(tab.labelKey) : tab.id)}
                  aria-label={tab.label ?? (tab.labelKey ? t(tab.labelKey) : tab.id)}
                >
                  {isActive && (
                    <div
                      className={cn(
                        'pointer-events-none absolute inset-0',
                        expanded ? 'rounded-xl' : 'rounded-full',
                      )}
                      style={{
                        maskImage: 'linear-gradient(to bottom, black, transparent 60%)',
                        WebkitMaskImage: 'linear-gradient(to bottom, black, transparent 60%)',
                        border: `1px solid hsl(var(--accent) / ${accentOpacity})`,
                      }}
                    />
                  )}
                  <Icon className="relative z-10 h-5 w-5 shrink-0" aria-hidden="true" />
                  <span
                    className={cn(
                      'relative z-10 truncate text-sm font-medium transition-[opacity,transform,max-width] duration-150',
                      expanded
                        ? 'max-w-[190px] translate-x-0 opacity-100'
                        : 'pointer-events-none max-w-0 -translate-x-2 opacity-0',
                    )}
                    aria-hidden={!expanded}
                  >
                    {tab.label ?? (tab.labelKey ? t(tab.labelKey) : tab.id)}
                  </span>
                </Link>
              );
            })}
        </div>
      </nav>

      {/* Version */}
      <div
        className={cn(
          'mt-auto flex shrink-0 gap-1.5 px-3 pt-4 transition-all duration-300',
          expanded ? 'w-full items-start' : 'w-full flex-col items-center',
        )}
        style={{ paddingBottom: isPlayerOpen ? '7rem' : undefined }}
      >
        <span className="text-[10px] text-muted-foreground/50">v{version}</span>
        {updateStatus.available && (
          <Link
            to="/settings"
            className="rounded-full bg-accent/15 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-accent transition-colors hover:bg-accent/25"
          >
            <span className={cn(!expanded && 'sr-only')}>{t('nav.updateBadge')}</span>
            {!expanded && <ArrowUp className="h-3 w-3" aria-hidden="true" />}
          </Link>
        )}
      </div>
    </aside>
  );
}
