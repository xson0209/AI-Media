import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { resetServerQueries } from '@/lib/queryClient';

export const DEFAULT_BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '17493';
export const DEFAULT_BACKEND_URL = `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`;

interface ServerStore {
  serverUrl: string;
  setServerUrl: (url: string) => void;

  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;

  mode: 'local' | 'remote';
  setMode: (mode: 'local' | 'remote') => void;

  keepServerRunningOnClose: boolean;
  setKeepServerRunningOnClose: (keepRunning: boolean) => void;

  customModelsDir: string | null;
  setCustomModelsDir: (dir: string | null) => void;
}

function configuredServerUrl(): string | null {
  const configured = import.meta.env.VITE_SERVER_URL?.trim();
  return configured || null;
}

function currentOriginBackendUrl(): string | null {
  if (!import.meta.env.PROD || typeof window === 'undefined') {
    return null;
  }

  const { protocol, origin, hostname } = window.location;
  if ((protocol === 'http:' || protocol === 'https:') && origin && hostname !== 'tauri.localhost') {
    return origin;
  }

  return null;
}

export function resolveBackendUrl(options: { storedServerUrl?: string | null } = {}): string {
  const configured = configuredServerUrl();
  if (configured) return configured;

  const currentOrigin = currentOriginBackendUrl();
  if (currentOrigin) return currentOrigin;

  const storedServerUrl = options.storedServerUrl?.trim();
  if (storedServerUrl) return storedServerUrl;

  return DEFAULT_BACKEND_URL;
}

export function getDefaultServerUrl(): string {
  return resolveBackendUrl();
}

export function isLoopbackVoiceboxServerUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return (
      parsed.port === DEFAULT_BACKEND_PORT &&
      (parsed.hostname === '127.0.0.1' ||
        parsed.hostname === 'localhost' ||
        parsed.hostname === '[::1]' ||
        parsed.hostname === '::1')
    );
  } catch {
    return false;
  }
}

export const useServerStore = create<ServerStore>()(
  persist(
    (set, get) => ({
      serverUrl: getDefaultServerUrl(),
      setServerUrl: (url) => {
        const prev = get().serverUrl;
        set({ serverUrl: url });
        if (url !== prev) {
          resetServerQueries();
        }
      },

      isConnected: false,
      setIsConnected: (connected) => set({ isConnected: connected }),

      mode: 'local',
      setMode: (mode) => set({ mode }),

      keepServerRunningOnClose: false,
      setKeepServerRunningOnClose: (keepRunning) => set({ keepServerRunningOnClose: keepRunning }),

      customModelsDir: null,
      setCustomModelsDir: (dir) => set({ customModelsDir: dir }),
    }),
    {
      name: 'voicebox-server',
    },
  ),
);
