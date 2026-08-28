import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleStop,
  CloudUpload,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api/client';
import type {
  AutomationConnectionCreate,
  AutomationConnectionResponse,
  RoxyProfileListResponse,
  RoxyWorkspaceListResponse,
} from '@/lib/api/types';

const inputLabel = 'space-y-1.5 text-sm';
const selectClass =
  'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi không xác định.';
}

function formatBytes(value: number): string {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `automation-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const jobLabels: Record<string, string> = {
  queued: 'Đang chờ',
  scheduled: 'Đã lên lịch',
  preparing: 'Đang chuẩn bị',
  uploading: 'Đang upload',
  finalizing: 'Đang hoàn tất',
  completed: 'Đã đăng',
  failed: 'Lỗi',
  interrupted: 'Bị gián đoạn',
  cancelled: 'Đã hủy',
};

export function AutomationHub() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [roxyKey, setRoxyKey] = useState('');
  const [roxyHost, setRoxyHost] = useState('http://127.0.0.1:50000');
  const [roxyLabel, setRoxyLabel] = useState('RoxyBrowser local');
  const [roxyConnectionId, setRoxyConnectionId] = useState('');
  const [workspaces, setWorkspaces] = useState<RoxyWorkspaceListResponse | null>(null);
  const [workspaceId, setWorkspaceId] = useState('');
  const [profiles, setProfiles] = useState<RoxyProfileListResponse | null>(null);
  const [profileId, setProfileId] = useState('');

  const [publisherPlatform, setPublisherPlatform] = useState<'youtube' | 'facebook' | 'tiktok'>('youtube');
  const [publisherLabel, setPublisherLabel] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [refreshToken, setRefreshToken] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [facebookPageId, setFacebookPageId] = useState('');

  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [jobPlatform, setJobPlatform] = useState<'youtube' | 'facebook' | 'tiktok'>('youtube');
  const [jobAssetId, setJobAssetId] = useState('');
  const [jobConnectionId, setJobConnectionId] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [jobTags, setJobTags] = useState('');
  const [jobPrivacy, setJobPrivacy] = useState('private');
  const [jobMode, setJobMode] = useState('standard');
  const [jobSchedule, setJobSchedule] = useState('');

  const statusQuery = useQuery({
    queryKey: ['automation-hub', 'status'],
    queryFn: () => apiClient.getAutomationHubStatus(),
    refetchInterval: 5000,
  });
  const connectionsQuery = useQuery({
    queryKey: ['automation-hub', 'connections'],
    queryFn: () => apiClient.listAutomationConnections(),
  });
  const assetsQuery = useQuery({
    queryKey: ['automation-hub', 'assets'],
    queryFn: () => apiClient.listAutomationAssets(),
  });
  const jobsQuery = useQuery({
    queryKey: ['automation-hub', 'jobs'],
    queryFn: () => apiClient.listAutomationPublishJobs(),
    refetchInterval: 2000,
  });

  const refreshConnections = () => queryClient.invalidateQueries({ queryKey: ['automation-hub', 'connections'] });
  const refreshAssets = () => queryClient.invalidateQueries({ queryKey: ['automation-hub', 'assets'] });
  const refreshJobs = () => queryClient.invalidateQueries({ queryKey: ['automation-hub', 'jobs'] });
  const refreshStatus = () => queryClient.invalidateQueries({ queryKey: ['automation-hub', 'status'] });

  const enabled = statusQuery.data?.enabled === true;
  const sidecarIsManaged = statusQuery.data?.sidecar.managed === true;
  const managedSidecarRunning = sidecarIsManaged && statusQuery.data?.sidecar.running === true;
  const externalSidecarReady = statusQuery.data?.sidecar.ready === true && !sidecarIsManaged;
  const allConnections = connectionsQuery.data ?? [];
  const roxyConnections = allConnections.filter((item) => item.platform === 'roxy');
  const publishingConnections = allConnections.filter(
    (item) => item.kind === 'publisher' && item.platform === jobPlatform,
  );

  const createConnection = useMutation({
    mutationFn: (data: AutomationConnectionCreate) => apiClient.createAutomationConnection(data),
    onSuccess: (connection) => {
      setAccessToken('');
      setRefreshToken('');
      setClientId('');
      setClientSecret('');
      setRoxyKey('');
      refreshConnections();
      if (connection.platform === 'roxy') setRoxyConnectionId(connection.id);
      toast({ title: 'Đã lưu connection', description: 'Secret đã được mã hóa và không hiển thị lại.' });
    },
    onError: (error) => toast({ title: 'Không lưu được connection', description: errorMessage(error), variant: 'destructive' }),
  });

  const saveRoxyConnectionMutation = useMutation({
    mutationFn: () => {
      const publicConfig = { api_host: roxyHost };
      const secret = { api_key: roxyKey };
      if (roxyConnectionId) {
        return apiClient.updateAutomationConnection(roxyConnectionId, {
          label: roxyLabel || 'RoxyBrowser local',
          public_config: publicConfig,
          secret,
          scopes: [],
        });
      }
      return apiClient.createAutomationConnection({
        kind: 'roxy',
        platform: 'roxy',
        label: roxyLabel || 'RoxyBrowser local',
        public_config: publicConfig,
        secret,
        scopes: [],
      });
    },
    onSuccess: (connection) => {
      setRoxyKey('');
      setRoxyConnectionId(connection.id);
      refreshConnections();
      toast({
        title: roxyConnectionId ? 'Đã cập nhật Roxy connection' : 'Đã lưu Roxy connection',
        description: 'Secret đã được mã hóa. Hãy kiểm tra API lại sau khi xoay key.',
      });
    },
    onError: (error) => toast({ title: 'Không lưu được Roxy connection', description: errorMessage(error), variant: 'destructive' }),
  });

  const checkConnection = useMutation({
    mutationFn: (connectionId: string) => apiClient.checkAutomationConnection(connectionId),
    onSuccess: (connection) => {
      refreshConnections();
      toast({
        title: connection.status === 'ready' ? 'Connection sẵn sàng' : 'Connection cần cấu hình lại',
        description: connection.failure_reason ?? connection.label,
      });
    },
    onError: (error) => toast({ title: 'Không kiểm tra được connection', description: errorMessage(error), variant: 'destructive' }),
  });

  const deleteConnection = useMutation({
    mutationFn: (connectionId: string) => apiClient.deleteAutomationConnection(connectionId),
    onSuccess: () => refreshConnections(),
    onError: (error) => toast({ title: 'Không xóa được connection', description: errorMessage(error), variant: 'destructive' }),
  });

  const loadWorkspaces = useMutation({
    mutationFn: (connectionId: string) => apiClient.listRoxyWorkspaces(connectionId),
    onSuccess: (data) => {
      setWorkspaces(data);
      const first = data.rows[0]?.id;
      if (first) setWorkspaceId(String(first));
    },
    onError: (error) => toast({ title: 'Không đọc được workspace', description: errorMessage(error), variant: 'destructive' }),
  });

  const loadProfiles = useMutation({
    mutationFn: ({ connectionId, selectedWorkspaceId }: { connectionId: string; selectedWorkspaceId: number }) =>
      apiClient.listRoxyProfiles(connectionId, selectedWorkspaceId),
    onSuccess: (data) => {
      setProfiles(data);
      if (data.rows[0]?.dir_id) setProfileId(data.rows[0].dir_id);
    },
    onError: (error) => toast({ title: 'Không đọc được profile', description: errorMessage(error), variant: 'destructive' }),
  });

  const openProfile = useMutation({
    mutationFn: () =>
      apiClient.openRoxyProfile({
        connection_id: roxyConnectionId,
        workspace_id: Number(workspaceId),
        dir_id: profileId,
        force_open: true,
      }),
    onSuccess: (data) =>
      toast({ title: 'Đã mở RoxyBrowser profile', description: String(data.ws ?? data.http ?? profileId) }),
    onError: (error) => toast({ title: 'Không mở được profile', description: errorMessage(error), variant: 'destructive' }),
  });

  const closeProfile = useMutation({
    mutationFn: () => apiClient.closeRoxyProfiles({ connection_id: roxyConnectionId, dir_ids: [profileId] }),
    onSuccess: () => toast({ title: 'Đã yêu cầu đóng profile' }),
    onError: (error) => toast({ title: 'Không đóng được profile', description: errorMessage(error), variant: 'destructive' }),
  });

  const sidecarMutation = useMutation({
    mutationFn: (action: 'start' | 'stop') =>
      action === 'start' ? apiClient.startAutomationSidecar() : apiClient.stopAutomationSidecar(),
    onSuccess: () => refreshStatus(),
    onError: (error) => toast({ title: 'Sidecar gặp lỗi', description: errorMessage(error), variant: 'destructive' }),
  });

  const uploadAsset = useMutation({
    mutationFn: (file: File) => apiClient.uploadAutomationAsset(file),
    onSuccess: (asset) => {
      setAssetFile(null);
      setJobAssetId(asset.id);
      refreshAssets();
      toast({ title: 'Đã tạo asset snapshot', description: asset.filename });
    },
    onError: (error) => toast({ title: 'Không upload được asset', description: errorMessage(error), variant: 'destructive' }),
  });

  const createJob = useMutation({
    mutationFn: () =>
      apiClient.createAutomationPublishJob({
        asset_id: jobAssetId,
        connection_id: jobConnectionId,
        platform: jobPlatform,
        publish_mode: jobPlatform === 'tiktok' ? jobMode : 'standard',
        title: jobTitle,
        description: jobDescription,
        tags: jobTags
          .split(/[\s,]+/)
          .map((item) => item.trim())
          .filter(Boolean),
        privacy: jobPrivacy || null,
        scheduled_at: jobSchedule ? new Date(jobSchedule).toISOString() : null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: () => {
      refreshJobs();
      toast({ title: 'Đã tạo publishing job', description: 'Job chạy trong hàng đợi riêng của Automation Hub.' });
    },
    onError: (error) => toast({ title: 'Không tạo được job', description: errorMessage(error), variant: 'destructive' }),
  });

  const jobAction = useMutation({
    mutationFn: ({ jobId, action }: { jobId: string; action: 'cancel' | 'retry' }) =>
      action === 'cancel'
        ? apiClient.cancelAutomationPublishJob(jobId)
        : apiClient.retryAutomationPublishJob(jobId),
    onSuccess: () => refreshJobs(),
    onError: (error) => toast({ title: 'Không cập nhật được job', description: errorMessage(error), variant: 'destructive' }),
  });

  const workspaceRows = workspaces?.rows ?? [];
  const profileRows = profiles?.rows ?? [];
  const selectedJobConnection = useMemo(
    () => publishingConnections.find((item) => item.id === jobConnectionId),
    [publishingConnections, jobConnectionId],
  );

  function saveRoxyConnection() {
    saveRoxyConnectionMutation.mutate();
  }

  function savePublisherConnection() {
    const secret: Record<string, unknown> = {};
    const publicConfig: Record<string, unknown> = {};
    let scopes: string[] = [];
    if (publisherPlatform === 'youtube') {
      secret.access_token = accessToken;
      if (refreshToken) secret.refresh_token = refreshToken;
      if (clientId) secret.client_id = clientId;
      if (clientSecret) secret.client_secret = clientSecret;
      scopes = ['https://www.googleapis.com/auth/youtube.upload'];
    } else if (publisherPlatform === 'facebook') {
      secret.page_access_token = accessToken;
      publicConfig.page_id = facebookPageId;
      scopes = ['pages_manage_posts'];
    } else {
      secret.access_token = accessToken;
      scopes = ['video.upload'];
    }
    createConnection.mutate({
      kind: 'publisher',
      platform: publisherPlatform,
      label: publisherLabel || `${publisherPlatform} publishing`,
      public_config: publicConfig,
      secret,
      scopes,
    });
  }

  return (
    <div className="h-full overflow-y-auto px-2 py-4 sm:px-4 lg:px-6">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 pb-16">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-accent">
              <Bot className="h-4 w-4" /> Workflow độc lập
            </div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Automation Hub</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
              Quản lý RoxyBrowser và đăng video bằng API chính thức. Job ở đây không thay đổi trạng thái AI Video,
              voice, subtitle hoặc render.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void Promise.all([statusQuery.refetch(), connectionsQuery.refetch(), assetsQuery.refetch(), jobsQuery.refetch()])}>
            <RefreshCw className="h-4 w-4" /> Làm mới
          </Button>
        </div>

        <Card className={enabled ? 'border-emerald-500/30' : 'border-amber-500/40'}>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              {enabled ? <ShieldCheck className="h-5 w-5 text-emerald-500" /> : <AlertTriangle className="h-5 w-5 text-amber-500" />}
              Trạng thái tách biệt
            </CardTitle>
            <CardDescription>
              {enabled
                ? `Worker publishing: ${statusQuery.data?.worker.running ?? 0}/${statusQuery.data?.worker.max_concurrency ?? 1} đang chạy · ${statusQuery.data?.worker.queued ?? 0} đang chờ.`
                : 'Backend đang khóa action có side effect. Bật feature flag rồi khởi động lại backend.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            <StatusPill label="Feature" value={enabled ? 'Đã bật' : 'Đang tắt'} ok={enabled} />
            <StatusPill
              label="Secret store"
              value={statusQuery.data?.secret_store.ready ? 'Sẵn sàng' : 'Chưa sẵn sàng'}
              ok={statusQuery.data?.secret_store.ready === true}
            />
            <StatusPill
              label="Playwright MCP"
              value={statusQuery.data?.sidecar.ready ? 'HTTP sidecar sẵn sàng' : 'Chưa chạy'}
              ok={statusQuery.data?.sidecar.ready === true}
            />
            {(statusQuery.data?.prerequisites ?? []).map((item) => (
              <div key={item} className="md:col-span-3 rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
                {item}
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">RoxyBrowser / AI Browser</CardTitle>
              <CardDescription>Local API quản lý profile; Playwright MCP chạy sidecar loopback riêng.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={inputLabel} htmlFor="automation-roxy-label">
                  <span>Tên connection</span>
                  <Input id="automation-roxy-label" value={roxyLabel} onChange={(event) => setRoxyLabel(event.target.value)} disabled={!enabled} />
                </label>
                <label className={inputLabel} htmlFor="automation-roxy-host">
                  <span>Local API host</span>
                  <Input id="automation-roxy-host" value={roxyHost} onChange={(event) => setRoxyHost(event.target.value)} disabled={!enabled} />
                </label>
                <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-roxy-key">
                  <span>Roxy API key</span>
                  <Input
                    id="automation-roxy-key"
                    type="password"
                    autoComplete="new-password"
                    value={roxyKey}
                    onChange={(event) => setRoxyKey(event.target.value)}
                    placeholder="Secret được mã hóa; không hiển thị lại"
                    disabled={!enabled}
                  />
                </label>
              </div>
              <Button disabled={!enabled || !roxyKey || saveRoxyConnectionMutation.isPending} onClick={saveRoxyConnection}>
                {saveRoxyConnectionMutation.isPending && <Loader2 className="animate-spin" />}
                {roxyConnectionId ? 'Cập nhật Roxy connection' : 'Lưu Roxy connection'}
              </Button>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className={inputLabel} htmlFor="automation-roxy-connection">
                  <span>Connection đã lưu</span>
                  <select
                    id="automation-roxy-connection"
                    className={selectClass}
                    value={roxyConnectionId}
                    onChange={(event) => {
                      const connectionId = event.target.value;
                      setRoxyConnectionId(connectionId);
                      setRoxyKey('');
                      const connection = roxyConnections.find((item) => item.id === connectionId);
                      if (connection) {
                        setRoxyLabel(connection.label);
                        const apiHost = connection.public_config.api_host;
                        if (typeof apiHost === 'string') setRoxyHost(apiHost);
                      }
                    }}
                  >
                    <option value="">Chọn connection</option>
                    {roxyConnections.map((item) => (
                      <option key={item.id} value={item.id}>{item.label} · {item.status}</option>
                    ))}
                  </select>
                </label>
                <div className="flex items-end gap-2">
                  <Button variant="outline" disabled={!enabled || !roxyConnectionId || checkConnection.isPending} onClick={() => checkConnection.mutate(roxyConnectionId)}>
                    Kiểm tra API
                  </Button>
                  <Button variant="outline" disabled={!enabled || !roxyConnectionId || loadWorkspaces.isPending} onClick={() => loadWorkspaces.mutate(roxyConnectionId)}>
                    Workspace
                  </Button>
                </div>
                <label className={inputLabel} htmlFor="automation-roxy-workspace">
                  <span>Workspace</span>
                  <select id="automation-roxy-workspace" className={selectClass} value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)}>
                    <option value="">Chọn workspace</option>
                    {workspaceRows.map((item) => (
                      <option key={item.id} value={item.id}>{item.workspaceName ?? `Workspace ${item.id}`}</option>
                    ))}
                  </select>
                </label>
                <div className="flex items-end">
                  <Button
                    variant="outline"
                    disabled={!enabled || !roxyConnectionId || !workspaceId || loadProfiles.isPending}
                    onClick={() => loadProfiles.mutate({ connectionId: roxyConnectionId, selectedWorkspaceId: Number(workspaceId) })}
                  >
                    Tải profile
                  </Button>
                </div>
                <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-roxy-profile">
                  <span>Browser profile</span>
                  <select id="automation-roxy-profile" className={selectClass} value={profileId} onChange={(event) => setProfileId(event.target.value)}>
                    <option value="">Chọn profile</option>
                    {profileRows.map((item) => (
                      <option key={item.dir_id} value={item.dir_id}>{item.window_name ?? item.dir_id} · {item.core_type ?? 'Chrome'}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!enabled || !profileId || openProfile.isPending} onClick={() => openProfile.mutate()}>
                  <Play className="h-4 w-4" /> Mở profile
                </Button>
                <Button variant="outline" disabled={!enabled || !profileId || closeProfile.isPending} onClick={() => closeProfile.mutate()}>
                  <CircleStop className="h-4 w-4" /> Đóng profile
                </Button>
                <Button
                  variant="secondary"
                  disabled={!enabled || sidecarMutation.isPending || externalSidecarReady}
                  onClick={() => sidecarMutation.mutate(managedSidecarRunning ? 'stop' : 'start')}
                >
                  {externalSidecarReady
                    ? 'Sidecar ngoài đang chạy'
                    : managedSidecarRunning
                      ? 'Dừng sidecar'
                      : 'Khởi động sidecar'}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Sidecar ready không đồng nghĩa đã kết nối browser. Hub không tự giải CAPTCHA/2FA và không dùng browser để né audit nền tảng.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Kết nối xuất bản</CardTitle>
              <CardDescription>YouTube, Facebook Page và TikTok Draft dùng API chính thức.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={inputLabel} htmlFor="automation-publisher-platform">
                  <span>Nền tảng</span>
                  <select id="automation-publisher-platform" className={selectClass} value={publisherPlatform} onChange={(event) => setPublisherPlatform(event.target.value as 'youtube' | 'facebook' | 'tiktok')}>
                    <option value="youtube">YouTube</option>
                    <option value="facebook">Facebook Page</option>
                    <option value="tiktok">TikTok</option>
                  </select>
                </label>
                <label className={inputLabel} htmlFor="automation-publisher-label">
                  <span>Tên connection</span>
                  <Input id="automation-publisher-label" value={publisherLabel} onChange={(event) => setPublisherLabel(event.target.value)} placeholder="Kênh chính" disabled={!enabled} />
                </label>
                {publisherPlatform === 'facebook' && (
                  <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-facebook-page-id">
                    <span>Facebook Page ID</span>
                    <Input id="automation-facebook-page-id" value={facebookPageId} onChange={(event) => setFacebookPageId(event.target.value)} disabled={!enabled} />
                  </label>
                )}
                <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-publisher-access-token">
                  <span>{publisherPlatform === 'facebook' ? 'Page access token' : 'Access token'}</span>
                  <Input id="automation-publisher-access-token" type="password" autoComplete="new-password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} disabled={!enabled} />
                </label>
                {publisherPlatform === 'youtube' && (
                  <>
                    <label className={inputLabel} htmlFor="automation-youtube-refresh-token"><span>Refresh token</span><Input id="automation-youtube-refresh-token" type="password" value={refreshToken} onChange={(event) => setRefreshToken(event.target.value)} disabled={!enabled} /></label>
                    <label className={inputLabel} htmlFor="automation-youtube-client-id"><span>OAuth client ID</span><Input id="automation-youtube-client-id" value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={!enabled} /></label>
                    <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-youtube-client-secret"><span>OAuth client secret</span><Input id="automation-youtube-client-secret" type="password" value={clientSecret} onChange={(event) => setClientSecret(event.target.value)} disabled={!enabled} /></label>
                  </>
                )}
              </div>
              <Button disabled={!enabled || !accessToken || (publisherPlatform === 'facebook' && !facebookPageId)} onClick={savePublisherConnection}>
                Lưu connection mã hóa
              </Button>
              <div className="space-y-2">
                {allConnections.filter((item) => item.kind === 'publisher').map((item) => (
                  <ConnectionRow key={item.id} connection={item} onCheck={() => checkConnection.mutate(item.id)} onDelete={() => deleteConnection.mutate(item.id)} />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Video asset</CardTitle>
              <CardDescription>Hub tạo snapshot riêng; file nguồn và render state không bị sửa.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="text-sm font-medium" htmlFor="automation-asset-file">Chọn file video</label>
              <Input id="automation-asset-file" type="file" accept="video/*,.mp4,.mov,.m4v,.webm,.avi,.mkv" disabled={!enabled} onChange={(event) => setAssetFile(event.target.files?.[0] ?? null)} />
              <Button disabled={!enabled || !assetFile || uploadAsset.isPending} onClick={() => assetFile && uploadAsset.mutate(assetFile)}>
                {uploadAsset.isPending ? <Loader2 className="animate-spin" /> : <CloudUpload />} Upload thành asset
              </Button>
              <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
                {(assetsQuery.data ?? []).map((asset) => (
                  <button
                    key={asset.id}
                    type="button"
                    onClick={() => setJobAssetId(asset.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm ${jobAssetId === asset.id ? 'border-accent bg-accent/10' : 'border-border hover:bg-muted/50'}`}
                  >
                    <span className="block truncate font-medium">{asset.filename}</span>
                    <span className="text-xs text-muted-foreground">{formatBytes(asset.size_bytes)} · {asset.sha256.slice(0, 12)}</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Tạo publishing job</CardTitle>
              <CardDescription>YouTube/Facebook dùng lịch native; TikTok Draft chờ scheduler local đến đúng giờ.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <label className={inputLabel} htmlFor="automation-job-platform">
                <span>Nền tảng</span>
                <select id="automation-job-platform" className={selectClass} value={jobPlatform} onChange={(event) => { const next = event.target.value as 'youtube' | 'facebook' | 'tiktok'; setJobPlatform(next); setJobConnectionId(''); setJobMode(next === 'tiktok' ? 'draft' : 'standard'); }}>
                  <option value="youtube">YouTube</option>
                  <option value="facebook">Facebook Page</option>
                  <option value="tiktok">TikTok</option>
                </select>
              </label>
              <label className={inputLabel} htmlFor="automation-job-connection">
                <span>Connection ready</span>
                <select id="automation-job-connection" className={selectClass} value={jobConnectionId} onChange={(event) => setJobConnectionId(event.target.value)}>
                  <option value="">Chọn connection</option>
                  {publishingConnections.map((item) => <option key={item.id} value={item.id}>{item.label} · {item.status}</option>)}
                </select>
              </label>
              <label className={inputLabel} htmlFor="automation-job-asset">
                <span>Asset</span>
                <select id="automation-job-asset" className={selectClass} value={jobAssetId} onChange={(event) => setJobAssetId(event.target.value)}>
                  <option value="">Chọn video</option>
                  {(assetsQuery.data ?? []).map((asset) => <option key={asset.id} value={asset.id}>{asset.filename}</option>)}
                </select>
              </label>
              <label className={inputLabel} htmlFor="automation-job-visibility">
                <span>{jobPlatform === 'tiktok' ? 'Mode' : 'Privacy'}</span>
                {jobPlatform === 'tiktok' ? (
                  <select id="automation-job-visibility" className={selectClass} value={jobMode} onChange={(event) => setJobMode(event.target.value)}>
                    <option value="draft">Draft / Inbox</option>
                    <option value="direct" disabled={!statusQuery.data?.direct_post_enabled}>Direct Post</option>
                  </select>
                ) : (
                  <select id="automation-job-visibility" className={selectClass} value={jobPrivacy} onChange={(event) => setJobPrivacy(event.target.value)}>
                    <option value="private">Private</option>
                    <option value="unlisted">Unlisted</option>
                    <option value="public">Public</option>
                  </select>
                )}
              </label>
              <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-job-title"><span>Tiêu đề</span><Input id="automation-job-title" value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} /></label>
              <label className={`${inputLabel} sm:col-span-2`} htmlFor="automation-job-description"><span>Mô tả</span><Textarea id="automation-job-description" value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} /></label>
              <label className={inputLabel} htmlFor="automation-job-tags"><span>Hashtag / tag</span><Input id="automation-job-tags" value={jobTags} onChange={(event) => setJobTags(event.target.value)} placeholder="#ai #video" /></label>
              <label className={inputLabel} htmlFor="automation-job-schedule"><span>Lịch đăng</span><Input id="automation-job-schedule" type="datetime-local" value={jobSchedule} onChange={(event) => setJobSchedule(event.target.value)} /></label>
              <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                <Button disabled={!enabled || !jobAssetId || !jobConnectionId || selectedJobConnection?.status !== 'ready' || createJob.isPending} onClick={() => createJob.mutate()}>
                  {createJob.isPending && <Loader2 className="animate-spin" />} Tạo job riêng
                </Button>
                {selectedJobConnection && selectedJobConnection.status !== 'ready' && <span className="text-xs text-amber-600">Connection cần được kiểm tra thành công.</span>}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Publishing jobs</CardTitle>
            <CardDescription>Polling riêng mỗi 2 giây; job lỗi không làm hỏng workflow media nguồn.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {(jobsQuery.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">Chưa có publishing job.</p>}
            {(jobsQuery.data ?? []).map((job) => (
              <div key={job.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[1fr_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{job.title || job.platform}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{job.platform}</span>
                    <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">{jobLabels[job.status] ?? job.status}</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{job.id} · lần thử {job.attempt_count}</p>
                  {job.failure_reason && <p className="mt-1 text-sm text-destructive">{job.failure_reason}</p>}
                  {job.provider_url && (
                    <a href={job.provider_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-sm text-accent hover:underline">
                      Mở bài đăng <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {!['completed', 'failed', 'interrupted', 'cancelled'].includes(job.status) && (
                    <Button size="sm" variant="outline" onClick={() => jobAction.mutate({ jobId: job.id, action: 'cancel' })}>Hủy</Button>
                  )}
                  {['failed', 'interrupted', 'cancelled'].includes(job.status) && !job.provider_post_id && (
                    <Button size="sm" variant="outline" onClick={() => jobAction.mutate({ jobId: job.id, action: 'retry' })}>Retry an toàn</Button>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatusPill({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <AlertTriangle className="h-4 w-4 text-amber-500" />}
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function ConnectionRow({
  connection,
  onCheck,
  onDelete,
}: {
  connection: AutomationConnectionResponse;
  onCheck: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{connection.label}</p>
        <p className="text-xs text-muted-foreground">{connection.platform} · {connection.status} · secret {connection.secret_fingerprint ?? 'chưa có'}</p>
        {connection.failure_reason && <p className="mt-1 text-xs text-destructive">{connection.failure_reason}</p>}
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={onCheck}>Kiểm tra</Button>
        <Button size="icon" variant="ghost" aria-label={`Xóa ${connection.label}`} onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}
