const BASE = import.meta.env.BASE_URL?.replace(/\/$/, '') ?? '/conduit';
const API = `${BASE.startsWith('/conduit') ? '' : ''}`;

function apiUrl(path: string): string {
  const base = typeof window !== 'undefined' ? window.location.origin : '';
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrfCookie(): Promise<string | null> {
  let token = getCsrfToken();
  if (token) return token;
  await fetch(apiUrl('/api/csrf-token'), { credentials: 'include' });
  return getCsrfToken();
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  };

  if (init?.method && !['GET', 'HEAD', 'OPTIONS'].includes(init.method.toUpperCase())) {
    const csrfToken = await ensureCsrfCookie();
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
  }

  const res = await fetch(apiUrl(`/api${path}`), {
    credentials: 'include',
    headers,
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error || `API error ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────────────────────────
export type ConnectionStatus = 'active' | 'error' | 'untested';
export type SyncStatus = 'active' | 'paused' | 'draft' | 'error';
export type RunMode = 'manual' | 'scheduled' | 'on_change';
export type Semantics = 'insert' | 'upsert' | 'mirror';
export type RunStatus = 'running' | 'success' | 'failed' | 'partial';
export type MappingTransform = 'uppercase' | 'lowercase' | 'concat' | 'split' | 'format_date' | 'lookup' | 'json_extract' | 'constant' | 'conditional' | null;

export interface Connection {
  id: string;
  tenantId: string;
  name: string;
  destination: string;
  status: ConnectionStatus;
  credentialMeta: Record<string, unknown>;
  testedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Sync {
  id: string;
  tenantId: string;
  name: string;
  sourceType: string;
  sourceMeta: Record<string, unknown>;
  connectionId: string;
  objectType: string;
  runMode: RunMode;
  scheduleExpr: string | null;
  semantics: Semantics;
  upsertKey: string | null;
  status: SyncStatus;
  lastRunId: string | null;
  lastRunAt: string | null;
  lastRunStatus: string | null;
  createdAt: string;
  updatedAt: string;
  connection?: Connection | null;
  mappingCount?: number;
}

export interface SyncMapping {
  id: string;
  syncId: string;
  sourceField: string;
  destinationField: string;
  transform: MappingTransform;
  transformConfig: Record<string, unknown>;
  sortOrder: number;
}

export interface SyncRun {
  id: string;
  syncId: string;
  status: RunStatus;
  rowsRead: number;
  rowsWritten: number;
  rowsFailed: number;
  durationMs: number | null;
  errorMessage: string | null;
  triggeredBy: string;
  startedAt: string;
  finishedAt: string | null;
  syncName?: string;
  sync?: Sync | null;
  sampleErrors?: SyncRunRow[];
}

export interface SyncRunRow {
  id: string;
  runId: string;
  rowIndex: number;
  sourceData: Record<string, unknown>;
  errorMessage: string | null;
  retried: boolean;
  retriedAt: string | null;
}

export interface ConduitStats {
  totalSyncs: number;
  activeSyncs: number;
  totalRuns: number;
  successfulRuns: number;
  failedRuns: number;
  totalRowsWritten: number;
  successRate: number;
  recentRuns: SyncRun[];
}

export interface Template {
  id: string;
  name: string;
  sourceType: string;
  destination: string;
  description: string;
  category: string;
  icon: string;
  mappingCount: number;
  mappings: Array<{ sourceField: string; destinationField: string; transform: string | null; transformConfig: Record<string, unknown>; sortOrder: number }>;
}

export interface DestinationObject {
  name: string;
  label: string;
  description: string;
}

export interface DestinationField {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  updateable?: boolean;
}

export interface SourcePreview {
  fields: string[];
  rows: Array<Record<string, unknown>>;
  totalRows: number;
}

// ─── Stats ────────────────────────────────────────────────────────────────────
export const getStats = () => apiFetch<ConduitStats>('/conduit/stats');

// ─── Admin Usage ──────────────────────────────────────────────────────────────
export interface AdminUsageAlertEntry {
  meterKey: string;
  threshold: number;
  notifiedAt: string;
}

export interface AdminUsageRow {
  orgId: number;
  orgName: string;
  orgSlug: string;
  plan: string;
  status: string;
  members: number;
  activeUsers: number;
  apiCalls: number;
  storageMB: number;
  overages: { apiCalls: 'none' | 'warn' | 'over'; members: 'none' | 'warn' | 'over'; storage: 'none' | 'warn' | 'over' };
  planLimits: { apiCalls: number | null; members: number | null; storageMB: number | null };
  lastAlertSentAt: string | null;
  alertThresholdsFired: AdminUsageAlertEntry[];
}

export interface AdminUsageResponse {
  period: { from: string; to: string };
  totals: { orgs: number; apiCalls: number; activeUsers: number; overageCount: number; warnCount: number };
  rows: AdminUsageRow[];
  pagination: { limit: number; offset: number; total: number; hasMore: boolean };
}

export const getAdminUsage = (params?: { plan?: string; org?: string; limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.plan) q.set('plan', params.plan);
  if (params?.org) q.set('org', params.org);
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  const qs = q.toString();
  return apiFetch<AdminUsageResponse>(`/admin/usage${qs ? `?${qs}` : ''}`);
};

// ─── Quota Violations (admin) ────────────────────────────────────────────────
export interface QuotaViolationRow {
  id: number;
  featureKey: string;
  violationType: 'soft' | 'hard';
  action: string;
  currentUsage: number | null;
  limitValue: number | null;
  metadata: Record<string, unknown> | null;
  occurredAt: string;
}

export interface QuotaViolationsResponse {
  orgId: number;
  rows: QuotaViolationRow[];
  pagination: { limit: number; offset: number; total: number; hasMore: boolean };
}

export const getOrgQuotaViolations = (
  orgId: number,
  params?: { limit?: number; offset?: number; type?: 'soft' | 'hard'; feature?: string },
) => {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  if (params?.type) q.set('type', params.type);
  if (params?.feature) q.set('feature', params.feature);
  const qs = q.toString();
  return apiFetch<QuotaViolationsResponse>(
    `/admin/orgs/${orgId}/quota-violations${qs ? `?${qs}` : ''}`,
  );
};

// ─── Connections ──────────────────────────────────────────────────────────────
export const listConnections = () => apiFetch<Connection[]>('/conduit/connections');
export const getConnection = (id: string) => apiFetch<Connection>(`/conduit/connections/${id}`);
export const createConnection = (body: { name: string; destination: string; credentials?: Record<string, string> }) =>
  apiFetch<Connection>('/conduit/connections', { method: 'POST', body: JSON.stringify(body) });
export const updateConnection = (id: string, body: { name?: string; credentials?: Record<string, string> }) =>
  apiFetch<Connection>(`/conduit/connections/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
export const deleteConnection = (id: string) => apiFetch<void>(`/conduit/connections/${id}`, { method: 'DELETE' });
export const testConnection = (id: string) =>
  apiFetch<{ success: boolean; message: string; errors: string[]; latencyMs: number }>(`/conduit/connections/${id}/test`, { method: 'POST' });
export const validateCredentials = (body: { destination: string; credentials: Record<string, string> }) =>
  apiFetch<{ success: boolean; message: string; errors: string[]; latencyMs: number }>('/conduit/connections/validate', { method: 'POST', body: JSON.stringify(body) });

// ─── Syncs ────────────────────────────────────────────────────────────────────
export const listSyncs = () => apiFetch<Sync[]>('/conduit/syncs');
export const getSync = (id: string) => apiFetch<Sync>(`/conduit/syncs/${id}`);
export const createSync = (body: {
  name: string; connectionId: string; objectType: string; runMode: RunMode;
  semantics: Semantics; sourceType?: string; sourceMeta?: Record<string, unknown>;
  scheduleExpr?: string; upsertKey?: string;
}) => apiFetch<Sync>('/conduit/syncs', { method: 'POST', body: JSON.stringify(body) });
export const updateSync = (id: string, body: Partial<Omit<Sync, 'id' | 'tenantId' | 'createdAt' | 'updatedAt'>>) =>
  apiFetch<Sync>(`/conduit/syncs/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
export const deleteSync = (id: string) => apiFetch<void>(`/conduit/syncs/${id}`, { method: 'DELETE' });
export const runSync = (id: string) => apiFetch<SyncRun>(`/conduit/syncs/${id}/run`, { method: 'POST' });

// ─── Mappings ─────────────────────────────────────────────────────────────────
export const getSyncMappings = (syncId: string) => apiFetch<SyncMapping[]>(`/conduit/syncs/${syncId}/mappings`);
export const putSyncMappings = (syncId: string, mappings: Array<Omit<SyncMapping, 'id' | 'syncId'>>) =>
  apiFetch<SyncMapping[]>(`/conduit/syncs/${syncId}/mappings`, { method: 'PUT', body: JSON.stringify({ mappings }) });

// ─── Sync Runs ────────────────────────────────────────────────────────────────
export const listSyncRuns = (params?: { syncId?: string; status?: RunStatus; limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.syncId) q.set('syncId', params.syncId);
  if (params?.status) q.set('status', params.status);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiFetch<{ data: SyncRun[]; total: number }>(`/conduit/sync-runs?${q.toString()}`);
};
export const getSyncRun = (id: string) => apiFetch<SyncRun>(`/conduit/sync-runs/${id}`);
export const listSyncRunRows = (runId: string, params?: { limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiFetch<SyncRunRow[]>(`/conduit/sync-runs/${runId}/rows?${q.toString()}`);
};
export const retrySyncRunRow = (runId: string, rowId: string) =>
  apiFetch<void>(`/conduit/sync-runs/${runId}/rows/${rowId}/retry`, { method: 'POST' });

// ─── Templates ────────────────────────────────────────────────────────────────
export const listTemplates = () => apiFetch<Template[]>('/conduit/templates');
export const getTemplate = (id: string) => apiFetch<Template>(`/conduit/templates/${id}`);
export const applyTemplate = (id: string, body: { connectionId: string; name?: string }) =>
  apiFetch<Sync>(`/conduit/templates/${id}/apply`, { method: 'POST', body: JSON.stringify(body) });

// ─── Destination Metadata ─────────────────────────────────────────────────────
export const listDestinationObjects = (destination: string) =>
  apiFetch<DestinationObject[]>(`/conduit/destinations/${destination}/objects`);
export const listDestinationFields = (destination: string, objectType: string) =>
  apiFetch<DestinationField[]>(`/conduit/destinations/${destination}/objects/${objectType}/fields`);

// ─── Source Preview ───────────────────────────────────────────────────────────
export const previewSource = (body: { sourceType: string; sourceMeta?: Record<string, unknown>; mappings?: Array<Omit<SyncMapping, 'id' | 'syncId'>> }) =>
  apiFetch<SourcePreview>('/conduit/sources/preview', { method: 'POST', body: JSON.stringify(body) });

// ─── AGI Forecast ─────────────────────────────────────────────────────────────
export interface AgiForecastDerived {
  horizonVelocity: number | null;
  alignmentDebt: number | null;
  lutarReadiness: number | null;
}

export interface AgiForecastHistoryEntry {
  date: string;
  derived: AgiForecastDerived;
  receiptHash: string;
}

export interface AgiForecastStatusPresent {
  present: true;
  lastRunAt: string;
  date: string;
  runCount: number;
  statuses: Array<{
    id: string;
    label?: string;
    source?: string;
    ok: boolean;
    lastFetchedAt: string | null;
    value?: number | string | null;
    error?: string | null;
  }>;
  summary: {
    id: string;
    date: string;
    ingestionPolicy: 'PUBLIC_ONLY';
    derived: AgiForecastDerived;
    receiptHash: string;
  };
  history: AgiForecastHistoryEntry[];
}

export interface AgiForecastStatusAbsent {
  present: false;
  message: string;
}

export type AgiForecastStatus = AgiForecastStatusPresent | AgiForecastStatusAbsent;

export const getAgiForecastStatus = () => apiFetch<AgiForecastStatus>('/agi-forecast/status');

export interface AgiForecastRefreshResponse {
  lastRunAt: string;
  date: string;
  runCount: number;
  statuses: AgiForecastStatusPresent['statuses'];
  summary: AgiForecastStatusPresent['summary'];
}

export const refreshAgiForecast = () =>
  apiFetch<AgiForecastRefreshResponse>('/agi-forecast/refresh', { method: 'POST' });

// ─── Destination list ─────────────────────────────────────────────────────────
export const DESTINATIONS = [
  { id: 'salesforce', label: 'Salesforce', color: '#00A1E0' },
  { id: 'hubspot', label: 'HubSpot', color: '#FF7A59' },
  { id: 'slack', label: 'Slack', color: '#4A154B' },
  { id: 'google_sheets', label: 'Google Sheets', color: '#34A853' },
  { id: 'notion', label: 'Notion', color: '#000000' },
  { id: 'airtable', label: 'Airtable', color: '#FCB400' },
  { id: 'zendesk', label: 'Zendesk', color: '#03363D' },
  { id: 'marketo', label: 'Marketo', color: '#5C4EFA' },
  { id: 'intercom', label: 'Intercom', color: '#1F8DED' },
  { id: 'pipedrive', label: 'Pipedrive', color: '#1A1A2E' },
  { id: 'mailchimp', label: 'Mailchimp', color: '#FFE01B' },
  { id: 'segment', label: 'Segment', color: '#52BD95' },
  { id: 'webhook', label: 'Webhook', color: '#6366F1' },
  { id: 'lambda_cloud', label: 'Lambda Cloud', color: '#6C3AED' },
  { id: 'dstack', label: 'dstack', color: '#06B6D4' },
] as const;

export type DestinationId = typeof DESTINATIONS[number]['id'];
