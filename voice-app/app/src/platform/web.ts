import { resolveBackendUrl } from '@/stores/serverStore';
import type { Platform, ServerLogEntry, UpdateStatus } from './types';

const idleUpdateStatus: UpdateStatus = {
  checking: false,
  available: false,
  downloading: false,
  installing: false,
  readyToInstall: false,
};

function saveBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const webPlatform: Platform = {
  filesystem: {
    async saveFile(filename, blob) {
      saveBlob(filename, blob);
    },
    async openPath(path) {
      window.open(path, '_blank', 'noopener,noreferrer');
    },
    async pickDirectory() {
      return null;
    },
  },
  updater: {
    async checkForUpdates() {},
    async downloadAndInstall() {},
    async restartAndInstall() {},
    getStatus() {
      return idleUpdateStatus;
    },
    subscribe() {
      return () => {};
    },
  },
  audio: {
    async isSystemAudioSupported() {
      return false;
    },
    async startSystemAudioCapture() {
      throw new Error('System audio capture is only available in the desktop app.');
    },
    async stopSystemAudioCapture() {
      throw new Error('System audio capture is only available in the desktop app.');
    },
    async listOutputDevices() {
      return [];
    },
    async playToDevices() {},
    stopPlayback() {},
  },
  lifecycle: {
    async startServer() {
      return resolveBackendUrl();
    },
    async stopServer() {},
    async restartServer() {
      return resolveBackendUrl();
    },
    async setKeepServerRunning() {},
    async setupWindowCloseHandler() {},
    subscribeToServerLogs(_callback: (entry: ServerLogEntry) => void) {
      return () => {};
    },
  },
  metadata: {
    async getVersion() {
      return import.meta.env.VITE_APP_VERSION ?? 'web-dev';
    },
    isTauri: false,
  },
};
