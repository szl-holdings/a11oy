import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  Cpu,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { sentraTwin as fallbackTwin, type CyberAsset, type Incident, type ControlDrift } from '@/data/sentra-twin';
import { listCyberTwinAssets, listCyberTwinIncidents, listCyberTwinControlDrifts, getCyberTwinPosture } from '@/lib/sentra-api';
import { SourceBadge, useApiQuery } from '@/lib/use-api-query';
import { useSentraCoreLive } from '@/lib/use-sentra-core-live';
import { DataStateBadge } from '@szl-holdings/shared-ui/data-state-badge';
import { GuardDogBrainPanel } from '@/components/GuardDogBrainPanel';
import { IncidentPipelineCard } from '@/components/IncidentPipelineCard';

interface PostureDriftLive {
  lambda_score: number;
  added: Array<{ control_id: string }>;
  removed: Array<{ control_id: string }>;
  changed: Array<{ control_id: string }>;
}

const POSTURE_DRIFT_BODY = {
  baseline: {
    snapshot_id: 'dashboard-baseline',
    captured_at: '2026-05-01T00:00:00.000Z',
    controls: [
      { id: 'pr-ac-01', name: 'mfa-enforced', severity: 'critical' },
      { id: 'pr-ds-01', name: 'encryption-at-rest', severity: 'high' },
      { id: 'de-cm-01', name: 'edr-coverage', severity: 'high' },
      { id: 'rs-rp-01', name: 'incident-response-plan', severity: 'high' },
    ],
  },
  current: {
    snapshot_id: 'dashboard-current',
    captured_at: '2026-05-18T00:00:00.000Z',
    controls: [
      { id: 'pr-ac-01', name: 'mfa-enforced', severity: 'critical', state: 'partial' },
      { id: 'de-cm-01', name: 'edr-coverage', severity: 'high' },
      { id: 'rs-rp-01', name: 'incident-response-plan', severity: 'high' },
    ],
  },
} as const;

const BASELINE_ENTITIES = [
  {
    name: 'api-gateway-prod',
    type: 'Service',
    normalTraffic: '12.4k req/min',
    current: '12.1k req/min',
    deviation: 2,
    status: 'normal',
  },
  {
    name: 'db-replica-01',
    type: 'Database',
    normalTraffic: '840 conn/min',
    current: '2,341 conn/min',
    deviation: 178,
    status: 'anomaly',
  },
  {
    name: 'auth-service',
    type: 'Service',
    normalTraffic: '3.2k req/min',
    current: '3.4k req/min',
    deviation: 6,
    status: 'normal',
  },
  {
    name: 'analytics-worker-03',
    type: 'Compute',
    normalTraffic: 'Idle 82%',
    current: 'Idle 12%',
    deviation: 85,
    status: 'watch',
  },
];

const NL_EXAMPLES = [
  'show assets with unusual outbound connections in the last 6h',
  'which controls have drifted from policy since Monday?',
  'list incidents touching the auth-service blast radius',
];

interface EmulationRunPoint {
  ranAt: string;
  overallCompositeScore: number | null;
  rollingFourWeekAvg: number | null;
}

function MiniSparkline({ values, color }: { values: number[]; color: string }) {
  const width = 140;
  const height = 36;
  if (values.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-[9px] font-mono text-[#555]"
        style={{ width, height }}
      >
        awaiting history
      </div>
    );
  }
  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = w / (values.length - 1);
  const points = values.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + h - ((v - min) / range) * h;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const path = `M${points.join(' L')}`;
  const areaPath = `${path} L${(pad + w).toFixed(2)},${(pad + h).toFixed(2)} L${pad.toFixed(2)},${(pad + h).toFixed(2)} Z`;
  const lastX = pad + (values.length - 1) * stepX;
  const lastY = pad + h - ((values[values.length - 1]! - min) / range) * h;
  return (
    <svg width={width} height={height} aria-hidden="true">
      <path d={areaPath} fill={color} fillOpacity={0.14} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={2} fill={color} />
    </svg>
  );
}

function CyberResilienceTrendTile() {
  const [points, setPoints] = useState<EmulationRunPoint[] | null>(null);
  useEffect(() => {
    const base = import.meta.env.BASE_URL.replace(/\/$/, '');
    const apiBase = `${base}/../api`.replace('/sentra/../', '/');
    fetch(`${apiBase}/firestorm/emulation/runs?limit=8`, { credentials: 'include' })
      .then(r => (r.ok ? r.json() : null))
      .then((data: { runs?: EmulationRunPoint[] } | null) => {
        if (data?.runs) setPoints(data.runs);
      })
      .catch(() => {});
  }, []);

  const ordered = (points ?? []).slice().reverse();
  const series = ordered
    .map(r => r.rollingFourWeekAvg)
    .filter((v): v is number => v != null);
  const latest = series.length > 0 ? series[series.length - 1]! : null;
  const first = series.length > 1 ? series[0]! : null;
  const delta = latest != null && first != null ? latest - first : null;
  const color = '#c9b787';
  const insufficient = series.length < 2;

  return (
    <div className="stat-panel p-6">
      <div className="flex items-center gap-3 text-[#c9b787] mb-2">
        <TrendingUp className="w-5 h-5" />
        <span className="text-sm font-medium">Cyber Resilience Trend</span>
      </div>
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-4xl font-display font-bold">
            {latest != null ? `${(latest * 100).toFixed(0)}%` : '—'}
          </div>
          <div className="text-xs text-[#c9b787]/60 mt-2 font-mono">4-WEEK ROLLING AVG</div>
        </div>
        {insufficient ? (
          <div
            className="flex items-center justify-center text-[9px] font-mono text-[#555] text-right"
            style={{ width: 140, height: 36 }}
          >
            insufficient<br />rolling history
          </div>
        ) : (
          <MiniSparkline values={series} color={color} />
        )}
      </div>
      {delta != null && (
        <div
          className="text-[10px] font-mono mt-2"
          style={{ color: delta >= 0 ? '#22c55e' : '#ef4444' }}
        >
          {delta >= 0 ? '▲' : '▼'} {Math.abs(delta * 100).toFixed(1)}% over last {series.length} runs
        </div>
      )}
    </div>
  );
}

function PatternOfLifePanel() {
  return (
    <div className="sentra-panel p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-display font-bold flex items-center gap-2">
          <Brain className="w-4 h-4 text-[#f5f5f5]" />
          Behavioral Baseline
        </h2>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#c9b787] animate-pulse" />
          <span className="text-[9px] font-mono text-[#666] uppercase tracking-wider">
            Pattern of Life · Live
          </span>
        </div>
      </div>
      <div className="space-y-2">
        {BASELINE_ENTITIES.map((e) => {
          const devColor =
            e.status === 'anomaly'
              ? 'text-[#f5f5f5]'
              : e.status === 'watch'
                ? 'text-[#c9b787]'
                : 'text-[#c9b787]';
          const barColor =
            e.status === 'anomaly'
              ? 'bg-[#f5f5f5]'
              : e.status === 'watch'
                ? 'bg-[#c9b787]'
                : 'bg-[#c9b787]';
          const barWidth =
            e.status === 'anomaly'
              ? '100%'
              : e.status === 'watch'
                ? '70%'
                : `${Math.min(100, 50 + e.deviation)}%`;
          return (
            <div
              key={e.name}
              className="grid grid-cols-12 gap-2 items-center py-2 border-b border-[rgba(255,255,255,0.06)] last:border-0"
            >
              <div className="col-span-3">
                <div className="text-[11px] font-mono text-[#e0e0e0] truncate">{e.name}</div>
                <div className="text-[9px] text-[#555] uppercase">{e.type}</div>
              </div>
              <div className="col-span-3 text-[10px] text-[#666] font-mono">
                {e.normalTraffic}
              </div>
              <div
                className="col-span-3 text-[10px] font-mono font-semibold"
                style={{
                  color:
                    e.status === 'anomaly'
                      ? '#f5f5f5'
                      : e.status === 'watch'
                        ? '#c9b787'
                        : '#c9b787',
                }}
              >
                {e.current}
              </div>
              <div className="col-span-2 flex flex-col gap-1">
                <div className="w-full h-1 rounded-full bg-[#1a1a1a] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: barWidth }}
                  />
                </div>
              </div>
              <div className={`col-span-1 text-[9px] font-mono font-bold ${devColor} text-right`}>
                {e.status === 'normal' ? '—' : `+${e.deviation}%`}
              </div>
            </div>
          );
        })}
      </div>
      <div className="text-[9px] font-mono text-[#555]">
        Baseline computed over rolling 30-day window · Antigena autonomous response: ENABLED
      </div>
    </div>
  );
}

function NLThreatQueryBar() {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(false);
  return (
    <div className="sentra-panel p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4 text-[#f5f5f5]/60" />
        <span className="text-[10px] font-mono uppercase tracking-widest text-[#666]">
          Threat Intelligence Query
        </span>
        <span
          className="text-[9px] font-mono px-1.5 py-0.5 rounded"
          style={{
            background: 'rgba(201,183,135,0.08)',
            border: '1px solid rgba(201,183,135,0.12)',
            color: '#f5f5f5',
          }}
        >
          NL-powered
        </span>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setActive(true)}
          onBlur={() => setActive(false)}
          placeholder="Ask in plain English — e.g. 'show assets with unusual outbound activity this week'"
          className="flex-1 bg-transparent text-xs text-[#e0e0e0] placeholder:text-[#555] outline-none"
          style={{
            background: 'rgba(201,183,135,0.03)',
            border: `1px solid ${active ? 'rgba(201,183,135,0.25)' : 'rgba(201,183,135,0.08)'}`,
            borderRadius: 8,
            padding: '8px 12px',
            transition: 'border-color 0.15s',
          }}
        />
        <button
          className="px-3 py-2 rounded-lg text-[10px] font-mono font-bold uppercase tracking-wider transition-colors"
          style={{
            background: 'rgba(201,183,135,0.08)',
            border: '1px solid rgba(201,183,135,0.15)',
            color: '#f5f5f5',
          }}
        >
          Run
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {NL_EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => setQuery(ex)}
            className="text-[9px] font-mono text-[#555] hover:text-[#8a8a8a] transition-colors px-2 py-1 rounded"
            style={{
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const assetFetcher = useCallback(() => listCyberTwinAssets(), []);
  const incidentFetcher = useCallback(() => listCyberTwinIncidents(), []);
  const driftFetcher = useCallback(() => listCyberTwinControlDrifts(), []);
  const { data: assets, source } = useApiQuery<CyberAsset[]>(assetFetcher, 'assets', fallbackTwin.assets);
  const { data: incidents } = useApiQuery<Incident[]>(incidentFetcher, 'incidents', fallbackTwin.incidents);
  const { data: controlDrifts } = useApiQuery<ControlDrift[]>(driftFetcher, 'controlDrifts', fallbackTwin.controlDrifts);

  const [posture, setPosture] = useState({ recoveryPosture: fallbackTwin.recoveryPosture, financialExposure: fallbackTwin.financialExposure });
  useEffect(() => {
    getCyberTwinPosture()
      .then((res) => {
        if (res && typeof res.recoveryPosture === 'number') {
          setPosture({ recoveryPosture: res.recoveryPosture, financialExposure: res.financialExposure });
        }
      })
      .catch(() => {});
  }, []);

  const livePostureDrift = useSentraCoreLive<PostureDriftLive>({
    endpoint: '/posture-drift',
    body: POSTURE_DRIFT_BODY,
  });
  const isLivePosture = livePostureDrift.source === 'live' && livePostureDrift.data !== null;

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-3xl font-display font-bold text-[#f5f5f5]">Cyber Resilience Command</h1>
          <SourceBadge source={source} />
        </div>
        <p className="text-[#8a8a8a] mt-1">Operational status and posture overview</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="stat-panel p-6">
          <div className="flex items-center gap-3 text-[#f5f5f5] mb-2">
            <ShieldAlert className="w-5 h-5" />
            <span className="text-sm font-medium">Active Incidents</span>
          </div>
          <div className="text-4xl font-display font-bold">{incidents.length}</div>
          <div className="text-xs text-[#f5f5f5]/60 mt-2 font-mono">CRITICAL STATUS</div>
        </div>

        <div className="stat-panel p-6">
          <div className="flex items-center gap-3 text-[#c9b787] mb-2">
            <Cpu className="w-5 h-5" />
            <span className="text-sm font-medium">Assets at Risk</span>
          </div>
          <div className="text-4xl font-display font-bold">
            {assets.filter((a) => a.exposureScore > 70).length}
          </div>
          <div className="text-xs text-[#c9b787]/60 mt-2 font-mono">EXPOSURE &gt; 70</div>
        </div>

        <div className="stat-panel p-6">
          <div className="flex items-center gap-3 text-[#8a8a8a] mb-2">
            <RotateCcw className="w-5 h-5" />
            <span className="text-sm font-medium">Recovery Posture</span>
          </div>
          <div className="text-4xl font-display font-bold">{posture.recoveryPosture}%</div>
          <div className="w-full bg-[#1a1a1a] h-1 mt-3 rounded-full overflow-hidden">
            <div
              className="bg-[#8a8a8a] h-full transition-all duration-1000"
              style={{ width: `${posture.recoveryPosture}%` }}
            />
          </div>
        </div>

        <div className="stat-panel p-6" data-testid="dashboard-posture-drift">
          <div className="flex items-center gap-3 text-[#8a8a8a] mb-2">
            <ShieldCheck className="w-5 h-5" />
            <span className="text-sm font-medium">Posture Drift</span>
            <span className="ml-auto">
              <DataStateBadge
                state={isLivePosture ? 'live' : livePostureDrift.source === 'offline' ? 'stub' : 'seeded'}
                pulse={isLivePosture}
              />
            </span>
          </div>
          {isLivePosture && livePostureDrift.data ? (
            <>
              <div className="text-4xl font-display font-bold text-emerald-300">
                Λ {livePostureDrift.data.lambda_score.toFixed(2)}
              </div>
              <div className="text-xs text-[#8a8a8a]/60 mt-2 font-mono">
                {livePostureDrift.data.removed.length} REMOVED · {livePostureDrift.data.changed.length} CHANGED · {livePostureDrift.data.added.length} ADDED
              </div>
            </>
          ) : (
            <>
              <div className="text-4xl font-display font-bold">
                {controlDrifts.filter((d) => d.status === 'drift_detected').length}
              </div>
              <div className="text-xs text-[#8a8a8a]/60 mt-2 font-mono">RESPOND / RECOVER FAMILY</div>
            </>
          )}
        </div>

        <CyberResilienceTrendTile />
      </div>

      <NLThreatQueryBar />

      <GuardDogBrainPanel />

      <IncidentPipelineCard />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PatternOfLifePanel />
        <div className="sentra-panel p-5 space-y-3">
          <h2 className="text-sm font-display font-bold flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-[#8a8a8a]" />
            Time to Recover Estimate
          </h2>
          <div className="flex items-end gap-3">
            <div className="text-4xl font-display font-bold text-[#8a8a8a]">4.2h</div>
            <div className="text-xs text-[#666] mb-1.5">
              estimated mean time to recover (MTTR)
            </div>
          </div>
          <div className="space-y-2">
            {[
              { label: 'Containment', estimate: '45 min', progress: 90, color: '#f5f5f5' },
              { label: 'Eradication', estimate: '1.5h', progress: 45, color: '#c9b787' },
              { label: 'Recovery', estimate: '2h', progress: 20, color: '#8a8a8a' },
              { label: 'Validation', estimate: '30 min', progress: 0, color: '#8a8a8a' },
            ].map((s) => (
              <div key={s.label} className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-[#8a8a8a]">{s.label}</span>
                  <span className="font-mono text-[#666]">{s.estimate}</span>
                </div>
                <div className="w-full h-1 rounded-full bg-[#1a1a1a] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${s.progress}%`, background: s.color }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="text-[9px] font-mono text-[#555]">
            Agent-verified · Updated on each control state change
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 sentra-panel p-6">
          <h2 className="text-lg font-display font-bold mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-[#f5f5f5]" />
            Critical Incident Timeline
          </h2>
          <div className="space-y-6">
            {incidents.map((incident) => (
              <div key={incident.id} className="sentra-card p-4">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-[#f5f5f5]">{incident.title}</h3>
                  <span className="px-2 py-0.5 rounded bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 text-[10px] text-[#f5f5f5] font-mono">
                    {incident.severity.toUpperCase()}
                  </span>
                </div>
                <p className="text-sm text-[#8a8a8a] mb-4">{incident.description}</p>
                <div className="flex items-center gap-6 text-[11px] font-mono text-[#666]">
                  <div className="flex items-center gap-2">
                    <Zap className="w-3 h-3" />
                    STAGE: {incident.mitreStage}
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-3 h-3" />
                    ID: {incident.id}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="sentra-panel p-6">
          <h2 className="text-lg font-display font-bold mb-6 flex items-center gap-2">
            <BarChart3 className="text-[#f5f5f5] w-5 h-5" />
            Financial Exposure
          </h2>
          <div className="space-y-6">
            <div className="text-5xl font-display font-bold text-[#f5f5f5]">
              ${(posture.financialExposure / 1000000).toFixed(1)}M
            </div>
            <p className="text-sm text-[#8a8a8a]">
              Estimated cost avoidance via recommended isolation and recovery actions.
            </p>

            <div className="space-y-3 pt-4 border-t border-[rgba(255,255,255,0.06)]">
              <div className="flex justify-between text-xs">
                <span className="text-[#666]">Ransomware Impact</span>
                <span className="text-[#e0e0e0]">$1.8M</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[#666]">Operational Downtime</span>
                <span className="text-[#e0e0e0]">$850K</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[#666]">Data Recovery Costs</span>
                <span className="text-[#e0e0e0]">$150K</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
