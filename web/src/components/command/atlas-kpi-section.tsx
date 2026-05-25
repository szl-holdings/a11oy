import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Cpu,
  ExternalLink,
  GitBranch,
  GitMerge,
  Globe,
  Layers,
  Network,
  RefreshCw,
  Shield,
  Zap,
} from 'lucide-react';
import { Link } from 'wouter';

const BASE = import.meta.env.BASE_URL?.replace(/\/$/, '') || '';

interface DomainTwinSummary {
  domain: string;
  label: string;
  color: string;
  twinCount: number;
  stableCount: number;
  degradedCount: number;
  awaitingCount: number;
  driftAvg: number;
  pendingActions: number;
  worldline: string;
  appPath: string;
  atlasRuntimePath?: string;
  icon: typeof Globe;
}

const DOMAIN_CONFIG: Omit<
  DomainTwinSummary,
  | 'twinCount'
  | 'stableCount'
  | 'degradedCount'
  | 'awaitingCount'
  | 'driftAvg'
  | 'pendingActions'
  | 'worldline'
>[] = [
  { domain: 'aegis', label: 'Sentra — Cyber Resilience', color: '#c9b787', appPath: '/sentra', icon: Shield },
  {
    domain: 'terra',
    label: "DOMAINE — Real Estate",
    color: '#10b981',
    appPath: '/terra',
    atlasRuntimePath: '/terra/atlas-runtime',
    icon: Globe,
  },
  {
    domain: 'vessels',
    label: 'SEXTANT — Maritime',
    color: '#06b6d4',
    appPath: '/vessels',
    atlasRuntimePath: '/vessels/atlas-runtime',
    icon: Network,
  },
  {
    domain: 'continuum',
    label: 'Counsel — Execution',
    color: '#4B8BDB',
    appPath: `${BASE}/operations`,
    icon: Zap,
  },
  {
    domain: 'prism',
    label: 'Prism — Counsel',
    color: '#f59e0b',
    appPath: `${BASE}/operations/prism`,
    icon: Activity,
  },
  {
    domain: 'lyte',
    label: "KORA — AIOps",
    color: '#d4a054',
    appPath: `${BASE}/operations`,
    icon: Activity,
  },
];

const DEMO_SUMMARIES: DomainTwinSummary[] = [
  {
    ...DOMAIN_CONFIG[0],
    twinCount: 8,
    stableCount: 5,
    degradedCount: 2,
    awaitingCount: 1,
    driftAvg: 12,
    pendingActions: 4,
    worldline: 'WL-BETA',
  },
  {
    ...DOMAIN_CONFIG[1],
    twinCount: 4,
    stableCount: 4,
    degradedCount: 0,
    awaitingCount: 0,
    driftAvg: 4,
    pendingActions: 0,
    worldline: 'WL-ALPHA',
  },
  {
    ...DOMAIN_CONFIG[2],
    twinCount: 6,
    stableCount: 5,
    degradedCount: 0,
    awaitingCount: 1,
    driftAvg: 8,
    pendingActions: 2,
    worldline: 'WL-DELTA',
  },
  {
    ...DOMAIN_CONFIG[3],
    twinCount: 3,
    stableCount: 3,
    degradedCount: 0,
    awaitingCount: 0,
    driftAvg: 2,
    pendingActions: 0,
    worldline: 'WL-ALPHA',
  },
  {
    ...DOMAIN_CONFIG[4],
    twinCount: 2,
    stableCount: 2,
    degradedCount: 0,
    awaitingCount: 0,
    driftAvg: 3,
    pendingActions: 0,
    worldline: 'WL-ALPHA',
  },
  {
    ...DOMAIN_CONFIG[5],
    twinCount: 4,
    stableCount: 2,
    degradedCount: 2,
    awaitingCount: 0,
    driftAvg: 18,
    pendingActions: 4,
    worldline: 'WL-BETA',
  },
];

interface AtlasBranchEvent {
  id: string;
  domain: 'vessels' | 'terra';
  domainLabel: string;
  domainColor: string;
  type: 'branch_activated' | 'scenario_simulation' | 'drift_spike' | 'worldline_merge';
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'critical';
  ts: string;
  atlasPath: string;
}

const EVENT_TYPE_META: Record<
  AtlasBranchEvent['type'],
  { label: string; icon: typeof GitBranch; color: string }
> = {
  branch_activated: { label: 'Branch Activated', icon: GitBranch, color: '#8b7ac8' },
  scenario_simulation: { label: 'Scenario Sim', icon: Cpu, color: '#06b6d4' },
  drift_spike: { label: 'Drift Spike', icon: AlertTriangle, color: '#f59e0b' },
  worldline_merge: { label: 'Worldline Merge', icon: GitMerge, color: '#10b981' },
};

const SEV_STYLE: Record<
  AtlasBranchEvent['severity'],
  { bg: string; border: string; badgeText: string }
> = {
  info: {
    bg: 'rgba(255,255,255,0.01)',
    border: 'rgba(255,255,255,0.06)',
    badgeText: 'rgba(255,255,255,0.35)',
  },
  warning: { bg: 'rgba(192,138,44,0.04)', border: 'rgba(192,138,44,0.2)', badgeText: '#f59e0b' },
  critical: { bg: 'rgba(239,68,68,0.05)', border: 'rgba(239,68,68,0.22)', badgeText: '#f87171' },
};

function relTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

interface ApiRunSummary {
  domain: string;
  runCount: number;
  successCount: number;
  pendingCount: number;
}

function useAtlasRunSummary() {
  return useQuery<{ data: ApiRunSummary[] }>({
    queryKey: ['atlas-run-summary'],
    queryFn: async () => {
      const domains = ['aegis', 'vessels', 'terra'];
      const results = await Promise.all(
        domains.map(async (d) => {
          try {
            const r = await fetch(`/api/${d}/atlas/runs?limit=5`);
            if (!r.ok) return null;
            const body = await r.json();
            const runs: { status?: string }[] = body?.data?.runs ?? body?.runs ?? [];
            return {
              domain: d,
              runCount: runs.length,
              successCount: runs.filter((r) => r.status === 'completed').length,
              pendingCount: runs.filter((r) => r.status === 'pending' || r.status === 'running')
                .length,
            } as ApiRunSummary;
          } catch {
            return null;
          }
        }),
      );
      return { data: results.filter(Boolean) as ApiRunSummary[] };
    },
    staleTime: 60_000,
    retry: 1,
  });
}

interface CrossDomainSummaryResponse {
  domains: Array<{
    domain: string;
    twinCount: number;
    stableCount: number;
    degradedCount: number;
    avgDriftScore: number;
    activeBranches: number;
    lastSync: string;
  }>;
  totals: {
    totalTwins: number;
    stableTotal: number;
    degradedTotal: number;
    activeBranchesTotal: number;
    avgDriftScore: number;
  };
  generatedAt: string;
}

function useCrossDomainSummary() {
  return useQuery<CrossDomainSummaryResponse>({
    queryKey: ['atlas-cross-domain-summary'],
    queryFn: () =>
      fetch('/api/atlas/spatial/cross-domain/summary')
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((r) => r.data ?? r),
    staleTime: 60_000,
    retry: 1,
  });
}

interface ApiAtlasBranch {
  id?: number;
  branchId: string;
  name: string;
  description?: string | null;
  twinId: string;
  entityId: string;
  twinCategory: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'archived';
  riskAssessment?: string | null;
  recommendedActions?: string[];
  parameters?: Record<string, unknown>;
  deltaMetrics?: Record<string, { before?: unknown; after?: unknown; changePercent?: number }>;
  confidenceScore?: number;
  metadata?: Record<string, unknown> | null;
  completedAt?: string | null;
  createdAt?: string | null;
}

interface AtlasBranchesResponse {
  data: { branches: ApiAtlasBranch[]; count: number };
}

function useAtlasBranches(twinCategory: 'vessel' | 'property') {
  return useQuery<AtlasBranchesResponse>({
    queryKey: ['atlas-branches', twinCategory],
    queryFn: () =>
      fetch(`/api/atlas/spatial/branches?twinCategory=${twinCategory}&limit=25`).then((r) =>
        r.ok ? r.json() : Promise.reject(r.status),
      ),
    staleTime: 60_000,
    retry: 1,
  });
}

function branchToEvent(b: ApiAtlasBranch): AtlasBranchEvent {
  const isVessel = b.twinCategory === 'vessel';
  const domain: AtlasBranchEvent['domain'] = isVessel ? 'vessels' : 'terra';
  const domainLabel = isVessel ? 'SEXTANT' : 'DOMAINE';
  const domainColor = isVessel ? '#06b6d4' : '#10b981';
  const atlasPath = isVessel ? '/vessels/atlas-runtime' : '/terra/atlas-runtime';

  let type: AtlasBranchEvent['type'] = 'scenario_simulation';
  if (b.status === 'completed') type = 'branch_activated';
  else if (b.status === 'archived') type = 'worldline_merge';
  else if (b.status === 'failed') type = 'drift_spike';
  else type = 'scenario_simulation';

  let severity: AtlasBranchEvent['severity'] = 'info';
  const risk = (b.riskAssessment ?? '').toLowerCase();
  if (b.status === 'failed' || risk.includes('critical') || risk.includes('high')) {
    severity = 'critical';
  } else if (
    b.status === 'pending' ||
    b.status === 'running' ||
    risk.includes('warn') ||
    risk.includes('medium')
  ) {
    severity = 'warning';
  }

  const description =
    b.description ??
    b.riskAssessment ??
    (b.recommendedActions && b.recommendedActions.length > 0
      ? b.recommendedActions.join(' • ')
      : `${b.twinCategory} twin ${b.entityId} — status ${b.status}`);

  const ts = b.completedAt ?? b.createdAt ?? new Date(0).toISOString();

  return {
    id: b.branchId,
    domain,
    domainLabel,
    domainColor,
    type,
    title: b.name,
    description,
    severity,
    ts,
    atlasPath,
  };
}

export function AtlasKpiSection() {
  const { data: runData, isLoading } = useAtlasRunSummary();
  const { data: crossDomain } = useCrossDomainSummary();
  const {
    data: vesselBranches,
    isLoading: vesselsLoading,
    isError: vesselsError,
  } = useAtlasBranches('vessel');
  const {
    data: propertyBranches,
    isLoading: propertyLoading,
    isError: propertyError,
  } = useAtlasBranches('property');
  const runSummaries: ApiRunSummary[] = runData?.data ?? [];

  const liveBranches = [
    ...(vesselBranches?.data?.branches ?? []),
    ...(propertyBranches?.data?.branches ?? []),
  ];
  const liveEvents = liveBranches
    .map(branchToEvent)
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
    .slice(0, 8);
  const branchesLoading = vesselsLoading || propertyLoading;
  const branchesPartialError = (vesselsError || propertyError) && !(vesselsError && propertyError);
  const branchesAllError = vesselsError && propertyError;

  const totalTwins =
    crossDomain?.totals.totalTwins ?? DEMO_SUMMARIES.reduce((s, d) => s + d.twinCount, 0);
  const totalDegraded =
    crossDomain?.totals.degradedTotal ??
    DEMO_SUMMARIES.reduce((s, d) => s + d.degradedCount + d.awaitingCount, 0);
  const totalPending = DEMO_SUMMARIES.reduce((s, d) => s + d.pendingActions, 0);
  const stableTotal =
    crossDomain?.totals.stableTotal ?? DEMO_SUMMARIES.reduce((s, d) => s + d.stableCount, 0);
  const stablePercent = totalTwins > 0 ? Math.round((stableTotal / totalTwins) * 100) : 0;

  const isActiveBranch = (s: ApiAtlasBranch['status']) => s === 'completed' || s === 'running';
  const activeBranchesVessels =
    vesselBranches?.data?.branches?.filter((b) => isActiveBranch(b.status)).length ??
    crossDomain?.domains?.find((d) => d.domain === 'vessels')?.activeBranches ??
    0;
  const activeBranchesTerra =
    propertyBranches?.data?.branches?.filter((b) => isActiveBranch(b.status)).length ??
    crossDomain?.domains?.find((d) => d.domain === 'terra')?.activeBranches ??
    0;

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-surface-border)',
        padding: '24px',
      }}
    >
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4" style={{ color: '#8b7ac8' }} />
          <span
            className="text-xs font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            ATLAS Spatial Runtime — Cross-Domain Health
          </span>
        </div>
        <div className="flex items-center gap-2">
          {totalDegraded > 0 && (
            <span
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-lg border"
              style={{
                color: '#f59e0b',
                borderColor: 'rgba(245,158,11,0.25)',
                background: 'rgba(245,158,11,0.06)',
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ background: '#f59e0b' }}
              />
              {totalDegraded} twin{totalDegraded !== 1 ? 's' : ''} need attention
            </span>
          )}
          <Link
            href={`${BASE}/strategy/atlas-runtime`}
            className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg border transition-all hover:bg-white/5"
            style={{
              color: '#8b7ac8',
              borderColor: 'rgba(139,122,200,0.25)',
              background: 'rgba(139,122,200,0.06)',
            }}
          >
            <Layers className="w-3 h-3" />
            Twin View
          </Link>
          <Link
            href={`${BASE}/strategy/worldline-registry`}
            className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg border transition-all hover:bg-white/5"
            style={{
              color: '#8b7ac8',
              borderColor: 'rgba(139,122,200,0.25)',
              background: 'rgba(139,122,200,0.06)',
            }}
          >
            <GitBranch className="w-3 h-3" />
            Worldlines →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total Twins', value: totalTwins, color: '#8b7ac8' },
          { label: 'Stable', value: `${stablePercent}%`, color: '#10b981' },
          {
            label: 'Need Attention',
            value: totalDegraded,
            color: totalDegraded > 0 ? '#f59e0b' : '#10b981',
            pulse: totalDegraded > 0,
          },
          {
            label: 'Pending Actions',
            value: totalPending,
            color: totalPending > 0 ? '#ef4444' : '#10b981',
            pulse: totalPending > 0,
          },
        ].map((c) => (
          <div
            key={c.label}
            className="rounded-xl border p-3"
            style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.01)' }}
          >
            <div className="flex items-center justify-between mb-1.5">
              <div
                className="text-[9px] font-medium uppercase tracking-widest"
                style={{ color: 'rgba(255,255,255,0.3)' }}
              >
                {c.label}
              </div>
              {c.pulse && (
                <span
                  className="w-1.5 h-1.5 rounded-full animate-pulse"
                  style={{ background: c.color }}
                />
              )}
            </div>
            <div className="text-xl font-bold font-mono" style={{ color: c.color }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {DEMO_SUMMARIES.map((d) => {
          const DIcon = d.icon;
          const isHealthy = d.degradedCount === 0 && d.awaitingCount === 0;
          const statusColor = isHealthy ? '#10b981' : d.degradedCount > 0 ? '#f59e0b' : '#8b7ac8';
          const runInfo = runSummaries.find((r) => r.domain === d.domain);
          const activeBranches =
            d.domain === 'vessels'
              ? activeBranchesVessels
              : d.domain === 'terra'
                ? activeBranchesTerra
                : undefined;

          return (
            <div
              key={d.domain}
              className="rounded-xl border p-3 flex flex-col gap-2"
              style={{ borderColor: `${statusColor}18`, background: `${statusColor}04` }}
            >
              <div className="flex items-center gap-2">
                <div
                  className="p-1.5 rounded-lg shrink-0"
                  style={{ background: `${d.color}12`, border: `1px solid ${d.color}20` }}
                >
                  <DIcon className="w-3 h-3" style={{ color: d.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className="text-[9px] font-bold uppercase tracking-widest truncate"
                    style={{ color: d.color }}
                  >
                    {d.label}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {isHealthy ? (
                    <CheckCircle className="w-3 h-3" style={{ color: '#10b981' }} />
                  ) : (
                    <AlertTriangle
                      className="w-3 h-3 animate-pulse"
                      style={{ color: statusColor }}
                    />
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-1.5">
                {[
                  { label: 'Twins', value: d.twinCount, color: 'rgba(255,255,255,0.6)' },
                  { label: 'Stable', value: d.stableCount, color: '#10b981' },
                  {
                    label: 'Drift Avg',
                    value: `Δ${d.driftAvg}%`,
                    color: d.driftAvg <= 5 ? '#10b981' : d.driftAvg <= 15 ? '#f59e0b' : '#ef4444',
                  },
                ].map((m) => (
                  <div
                    key={m.label}
                    className="rounded border px-1.5 py-1 text-center"
                    style={{
                      borderColor: 'rgba(255,255,255,0.05)',
                      background: 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <div
                      className="text-[7px] uppercase tracking-widest mb-0.5"
                      style={{ color: 'rgba(255,255,255,0.25)' }}
                    >
                      {m.label}
                    </div>
                    <div className="text-[9px] font-bold font-mono" style={{ color: m.color }}>
                      {m.value}
                    </div>
                  </div>
                ))}
              </div>

              {activeBranches !== undefined && (
                <div
                  className="flex items-center gap-1.5 px-1.5 py-1 rounded border"
                  style={{
                    borderColor: 'rgba(139,122,200,0.12)',
                    background: 'rgba(139,122,200,0.04)',
                  }}
                >
                  <GitBranch className="w-2.5 h-2.5 shrink-0" style={{ color: '#8b7ac8' }} />
                  <span className="text-[8px] font-mono" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    <span className="font-bold" style={{ color: '#8b7ac8' }}>
                      {activeBranches}
                    </span>{' '}
                    active branch{activeBranches !== 1 ? 'es' : ''}
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between text-[9px]">
                <span className="font-mono" style={{ color: 'rgba(255,255,255,0.25)' }}>
                  {d.worldline}
                  {d.pendingActions > 0 && (
                    <span className="ml-2 font-bold" style={{ color: '#f59e0b' }}>
                      {d.pendingActions} pending
                    </span>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  {runInfo && (
                    <span style={{ color: 'rgba(255,255,255,0.25)' }}>
                      {runInfo.runCount} run{runInfo.runCount !== 1 ? 's' : ''}
                      {runInfo.pendingCount > 0 && (
                        <span className="text-amber-400 ml-1">({runInfo.pendingCount} active)</span>
                      )}
                    </span>
                  )}
                  {isLoading && !runInfo && (
                    <RefreshCw
                      className="w-2.5 h-2.5 animate-spin"
                      style={{ color: 'rgba(255,255,255,0.2)' }}
                    />
                  )}
                  {d.atlasRuntimePath && (
                    <a
                      href={d.atlasRuntimePath}
                      className="flex items-center gap-0.5 text-[8px] font-bold uppercase tracking-wider transition-opacity hover:opacity-80"
                      style={{ color: d.color }}
                    >
                      ATLAS <ExternalLink className="w-2 h-2" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-5 pt-5" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <GitBranch className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
            <span
              className="text-[10px] font-bold uppercase tracking-widest"
              style={{ color: 'var(--color-fg-muted)' }}
            >
              What Changed — ATLAS Branch Activations &amp; Scenarios
            </span>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/vessels/atlas-runtime"
              className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded border transition-all hover:bg-white/5"
              style={{
                color: '#06b6d4',
                borderColor: 'rgba(6,182,212,0.2)',
                background: 'rgba(6,182,212,0.04)',
              }}
            >
              <Network className="w-2.5 h-2.5" /> SEXTANT ATLAS
            </a>
            <a
              href="/terra/atlas-runtime"
              className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded border transition-all hover:bg-white/5"
              style={{
                color: '#10b981',
                borderColor: 'rgba(16,185,129,0.2)',
                background: 'rgba(16,185,129,0.04)',
              }}
            >
              <Globe className="w-2.5 h-2.5" /> DOMAINE ATLAS
            </a>
          </div>
        </div>

        {branchesPartialError && (
          <div
            className="rounded-xl border px-3 py-2 text-[10px] mb-2"
            style={{
              background: 'rgba(245,158,11,0.05)',
              borderColor: 'rgba(245,158,11,0.2)',
              color: '#f59e0b',
            }}
          >
            {vesselsError ? 'SEXTANT' : 'DOMAINE'} ATLAS branch feed temporarily unavailable — showing
            partial results.
          </div>
        )}
        {liveEvents.length === 0 && (
          <div
            className="rounded-xl border px-3 py-4 text-center text-[10px]"
            style={{
              background: 'rgba(255,255,255,0.01)',
              borderColor: 'rgba(255,255,255,0.06)',
              color: 'rgba(255,255,255,0.4)',
            }}
          >
            {branchesLoading
              ? 'Loading recent ATLAS branch activity…'
              : branchesAllError
                ? 'ATLAS branch feed temporarily unavailable.'
                : 'No recent ATLAS branch activations or scenario simulations.'}
          </div>
        )}

        <div className="flex flex-col gap-2">
          {liveEvents.map((ev) => {
            const meta = EVENT_TYPE_META[ev.type];
            const MetaIcon = meta.icon;
            const sev = SEV_STYLE[ev.severity];
            return (
              <a
                key={ev.id}
                href={ev.atlasPath}
                className="rounded-xl border px-3 py-2.5 flex items-start gap-3 transition-all hover:bg-white/3 group"
                style={{ background: sev.bg, borderColor: sev.border, textDecoration: 'none' }}
              >
                <div
                  className="p-1.5 rounded-lg shrink-0 mt-0.5"
                  style={{
                    background: `${ev.domainColor}12`,
                    border: `1px solid ${ev.domainColor}20`,
                  }}
                >
                  <MetaIcon className="w-3 h-3" style={{ color: meta.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span
                      className="text-[9px] font-bold uppercase tracking-widest"
                      style={{ color: ev.domainColor }}
                    >
                      {ev.domainLabel}
                    </span>
                    <span
                      className="text-[8px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider"
                      style={{ background: `${meta.color}15`, color: meta.color }}
                    >
                      {meta.label}
                    </span>
                    {ev.severity !== 'info' && (
                      <span
                        className="text-[8px] font-bold uppercase tracking-wider"
                        style={{ color: sev.badgeText }}
                      >
                        {ev.severity}
                      </span>
                    )}
                    <span
                      className="text-[8px] font-mono ml-auto"
                      style={{ color: 'rgba(255,255,255,0.25)' }}
                    >
                      {relTime(ev.ts)}
                    </span>
                  </div>
                  <div
                    className="text-[10px] font-semibold mb-0.5"
                    style={{ color: 'rgba(255,255,255,0.75)' }}
                  >
                    {ev.title}
                  </div>
                  <div
                    className="text-[9px] leading-relaxed"
                    style={{ color: 'rgba(255,255,255,0.38)' }}
                  >
                    {ev.description}
                  </div>
                </div>
                <ChevronRight
                  className="w-3 h-3 shrink-0 mt-0.5 opacity-0 group-hover:opacity-40 transition-opacity"
                  style={{ color: 'rgba(255,255,255,0.5)' }}
                />
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}
