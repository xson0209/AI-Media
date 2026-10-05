import { QueryClientProvider, useQuery } from '@tanstack/react-query';
import { createRoot } from 'react-dom/client';
import { NewsVideo } from '../../src/components/NewsVideo/NewsVideo';
import { apiClient } from '../../src/lib/api/client';
import { queryClient } from '../../src/lib/queryClient';
import { PlatformProvider } from '../../src/platform/PlatformContext';
import { useServerStore } from '../../src/stores/serverStore';
import { webPlatform } from '../../../web/src/platform';

const fixture = {
  savedFiles: [] as Array<{ filename: string; text: string; extensions?: string[] }>,
  failSave: false,
  holdSave: false,
  finishSave: () => {},
};
Object.assign(window, { workflowFixture: fixture });
const platform = {
  ...webPlatform,
  filesystem: {
    ...webPlatform.filesystem,
    async saveFile(filename: string, blob: Blob, filters?: Array<{ name: string; extensions: string[] }>) {
      if (fixture.holdSave) await new Promise<void>((resolve) => { fixture.finishSave = resolve; });
      if (fixture.failSave) throw new Error('Disk unavailable');
      fixture.savedFiles.push({ filename, text: await blob.text(), extensions: filters?.[0]?.extensions });
    },
  },
};
useServerStore.getState().setServerUrl(`${window.location.origin}/server-a`);

function ServerControls() {
  const health = useQuery({ queryKey: ['health-fixture'], queryFn: () => apiClient.getHealth(), retry: false });
  const inactive = useQuery<string>({ queryKey: ['inactive-server-data'], enabled: false });
  const seeded = useQuery<string>({
    queryKey: ['seeded-server-data'],
    queryFn: async () => (await apiClient.getHealth()).status,
    enabled: Boolean(health.data),
    initialData: health.data?.status,
  });
  return (
    <div>
      <output id="health">{health.data?.status ?? 'empty'}</output>
      <output id="inactive">{inactive.data ?? 'empty'}</output>
      <output id="seeded">{seeded.data ?? 'empty'}</output>
      <button type="button" onClick={() => useServerStore.getState().setServerUrl(`${window.location.origin}/server-a`)}>Server A</button>
      <button type="button" onClick={() => useServerStore.getState().setServerUrl(`${window.location.origin}/server-b`)}>Server B</button>
      <button type="button" onClick={() => useServerStore.getState().setServerUrl(useServerStore.getState().serverUrl)}>Same server</button>
      <button type="button" onClick={() => queryClient.setQueryData(['inactive-server-data'], 'cached-A')}>Seed inactive cache</button>
      <button type="button" onClick={() => void health.refetch()}>Refetch health</button>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <PlatformProvider platform={platform}>
      <ServerControls />
      <NewsVideo />
    </PlatformProvider>
  </QueryClientProvider>,
);
