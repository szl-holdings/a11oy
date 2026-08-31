import { useStandardQuery } from '@szl-holdings/api-client-react';

import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import {
  Activity,
  AlertTriangle,
  Anchor,
  Building2,
  Clock,
  Filter,
  GitBranch,
  Layers,
  Loader2,
  RefreshCw,
  Shield,
  Sparkles,
} from 'lucide-react';
import { useMemo, useState } from 'react';

type Domain = 'aegis' | 'vessels' | 'terra';

interface WorldlineOverlay {
  id: string | number;
  signalType: string;
  signalTimestamp: string;
  severity?: 'info' | 'warning' | 'critical' | null;
  affectedTwinCategories?: string[] | null;
  affectedEntityIds?: string[] | null;
  payload?: Record<string, unknown> | null;
  confidenceScore?: number | null;
}

interface OverlayApiResponse {
  overlays: WorldlineOverlay[];
  count: number;
}

interface CorrelationEvent {
  id: string;
  domain: Domain;
  timestamp: number;
  severity: 'info' | 'warning' | 'critical';
  signalType: string;
  entity: string;
  description: string;
  confidence: number;
}

interface Cluster {
  id: string;
  startedAt: number;
  endedAt: number;
  events: CorrelationEvent[];
  domains: Set<Domain>;
}

const DOMAIN_META: Record<
  Domain,
  {
    label: string;
    short: string;
    color: string;
    bg: string;
    border: string;
    icon: typeof Shield;
    twinCategory: string;
  }
> = {
  aegis: {
    label: 'PARAGON · Cybersecurity',
    short: 'AEG',
    color: '#f5f5f5',
    bg: 'rgba(245,245,245,0.08)',
    border: 'rgba(245,245,245,0.25)',
    icon: Shield,
    twinCategory: 'endpoint',
  },
  vessels: {
    label: 'SEXTANT · Maritime',
    short: 'VSL',
    color: '#8a8a8a',
    bg: 'rgba(56,189,248,0.08)',
    border: 'rgba(56,189,248,0.25)',
    icon: Anchor,
    twinCategory: 'vessel',
  },
  terra: {
    label: 'DOMAINE · Real Estate',
    short: 'TER',
    color: '#c9b787',
    bg: 'rgba(201,183,135,0.08)',
    border: 'rgba(201,183,135,0.25)',
    icon: Building2,
    twinCategory: 'property',
  },
};

const SEV_COLOR: Record<CorrelationEvent['severity'], string> = {
  critical: '#f5f5f5',
  warning: '#c9b787',
  info: '#6b7280',
};

const NOW = Date.now();

const SEED_EVENTS: CorrelationEvent[] = [
  // Cluster 1 — supply-chain coordinated event (3 domains within ~7 min)
  {
    id: 's-aeg-1',
    domain: 'aegis',
    timestamp: NOW - 12 * 60_000,
    severity: 'critical',
    signalType: 'lateral_movement',
    entity: 'AWS-VPC-PROD',
    description: 'Lateral movement via cross-account IAM role chain',
    confidence: 0.92,
  },
  {
    id: 's-vsl-1',
    domain: 'vessels',
    timestamp: NOW - 14 * 60_000,
    severity: 'critical',
    signalType: 'route_anomaly',
    entity: 'MV-001 Pacific Navigator',
    description: 'AIS gap + 8nm course deviation in Bab-el-Mandeb chokepoint',
    confidence: 0.88,
  },
  {
    id: 's-ter-1',
    domain: 'terra',
    timestamp: NOW - 18 * 60_000,
    severity: 'warning',
    signalType: 'facility_intrusion',
    entity: '84 Grand St — Bonded Warehouse',
    description: 'After-hours badge anomaly at bonded distribution facility',
    confidence: 0.81,
  },

  // Cluster 2 — financial-pressure coupling (vessels demurrage + terra distress)
  {
    id: 's-vsl-2',
    domain: 'vessels',
    timestamp: NOW - 95 * 60_000,
    severity: 'warning',
    signalType: 'port_disruption',
    entity: 'MV-004 Cape Resolute',
    description: 'Sustained anchorage at Suez approach — demurrage threshold breached',
    confidence: 0.74,
  },
  {
    id: 's-ter-2',
    domain: 'terra',
    timestamp: NOW - 98 * 60_000,
    severity: 'warning',
    signalType: 'lien_filing',
    entity: '210 Kent Ave',
    description: 'UCC-1 filing recorded against mixed-use parcel — same parent obligor',
    confidence: 0.79,
  },

  // Solo events (no correlation)
  {
    id: 's-aeg-2',
    domain: 'aegis',
    timestamp: NOW - 38 * 60_000,
    severity: 'warning',
    signalType: 'privilege_escalation',
    entity: 'K8s-prod-app',
    description: 'Service-account token used outside namespace',
    confidence: 0.7,
  },
  {
    id: 's-ter-3',
    domain: 'terra',
    timestamp: NOW - 4 * 60 * 60_000,
    severity: 'info',
    signalType: 'submarket_pressure',
    entity: 'Bushwick submarket',
    description: 'Cap-rate expansion +18bps WoW',
    confidence: 0.62,
  },
  {
    id: 's-vsl-3',
    domain: 'vessels',
    timestamp: NOW - 5 * 60 * 60_000,
    severity: 'info',
    signalType: 'weather_overlay',
    entity: 'North Atlantic',
    description: 'Force-7 system intersecting eastbound fleet corridor',
    confidence: 0.55,
  },

  // Cluster 3 — older coordinated event (proves time-window filter works)
  {
    id: 's-aeg-3',
    domain: 'aegis',
    timestamp: NOW - 6 * 60 * 60_000 - 60_000,
    severity: 'critical',
    signalType: 'exfil_attempt',
    entity: 'DB-CLUSTER-PG',
    description: 'Unusual egress to non-whitelisted endpoint from primary db replica',
    confidence: 0.86,
  },
  {
    id: 's-vsl-4',
    domain: 'vessels',
    timestamp: NOW - 6 * 60 * 60_000 - 4 * 60_000,
    severity: 'critical',
    signalType: 'sanctions_proximity',
    entity: 'MV-003 Meridian Bulk',
    description: 'Counterparty match to OFAC-listed shore agent',
    confidence: 0.83,
  },
];

const TIME_WINDOWS: Array<{ key: string; label: string; ms: number }> = [
  { key: '5m', label: '5 min', ms: 5 * 60_000 },
  { key: '15m', label: '15 min', ms: 15 * 60_000 },
  { key: '1h', label: '1 hour', ms: 60 * 60_000 },
  { key: '6h', label: '6 hours', ms: 6 * 60 * 60_000 },
];

const LOOKBACK_HOURS = 8;

function inferDomain(overlay: WorldlineOverlay): Domain {
  const cats = overlay.affectedTwinCategories ?? [];
  if (cats.some((c) => /vessel|maritime|ship/i.test(c))) return 'vessels';
  if (cats.some((c) => /property|real_?estate|parcel|building/i.test(c))) return 'terra';
  return 'aegis';
}

function overlayToEvent(o: WorldlineOverlay): CorrelationEvent {
  const domain = inferDomain(o);
  const sev = (o.severity ?? 'info') as CorrelationEvent['severity'];
  const entity = o.affectedEntityIds?.[0] ?? '—';
  const payloadDesc = (() => {
    const p = o.payload ?? {};
    const v =
      (p as Record<string, unknown>).description ??
      (p as Record<string, unknown>).message ??
      (p as Record<string, unknown>).summary;
    return typeof v === 'string' ? v : `${o.signalType} signal observed`;
  })();
  return {
    id: `wl-${o.id}`,
    domain,
    timestamp: new Date(o.signalTimestamp).getTime(),
    severity: sev,
    signalType: o.signalType,
    entity,
    description: payloadDesc,
    confidence: o.confidenceScore ?? 0.6,
  };
}

function clusterEvents(
  events: CorrelationEvent[],
  windowMs: number,
): { clusters: Cluster[]; loners: CorrelationEvent[] } {
  const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp);
  const groups: CorrelationEvent[][] = [];
  let current: CorrelationEvent[] = [];

  for (const ev of sorted) {
    if (current.length === 0) {
      current.push(ev);
      continue;
    }
    const lastTs = current[current.length - 1].timestamp;
    if (ev.timestamp - lastTs <= windowMs) {
      current.push(ev);
    } else {
      groups.push(current);
      current = [ev];
    }
  }
  if (current.length > 0) groups.push(current);

  const clusters: Cluster[] = [];
  const loners: CorrelationEvent[] = [];
  groups.forEach((g, idx) => {
    const domains = new Set<Domain>(g.map((e) => e.domain));
    if (g.length >= 2 && domains.size >= 2) {
      clusters.push({
        id: `cl-${idx}`,
        startedAt: g[0].timestamp,
        endedAt: g[g.length - 1].timestamp,
        events: g,
        domains,
      });
    } else {
      loners.push(...g);
    }
  });

  return { clusters, loners };
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function fmtRelative(ts: number): string {
  const diff = Date.now() - ts;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function useDomainOverlays(domain: Domain) {
  const meta = DOMAIN_META[domain];
  return useStandardQuery<OverlayApiResponse>({
    queryKey: ['correlation-overlays', meta.twinCategory],
    queryFn: () =>
      apiFetch<OverlayApiResponse>(
        `/atlas/spatial/worldline/overlays?twinCategory=${encodeURIComponent(meta.twinCategory)}&limit=50`,
      ),
    staleTime: 30_000,
    retry: 1,
  });
}

export default function AegisAtlasCorrelation() {
  const [windowKey, setWindowKey] = useState<string>('15m');
  const [enabledDomains, setEnabledDomains] = useState<Record<Domain, boolean>>({
    aegis: true,
    vessels: true,
    terra: true,
  });

  const aegisQ = useDomainOverlays('aegis');
  const vesselsQ = useDomainOverlays('vessels');
  const terraQ = useDomainOverlays('terra');

  const isLoading = aegisQ.isLoading || vesselsQ.isLoading || terraQ.isLoading;
  const isError = aegisQ.isError && vesselsQ.isError && terraQ.isError;

  const liveEvents: CorrelationEvent[] = useMemo(() => {
    const out: CorrelationEvent[] = [];
    [aegisQ.data, vesselsQ.data, terraQ.data].forEach((r) => {
      if (r?.overlays?.length) out.push(...r.overlays.map(overlayToEvent));
    });
    return out;
  }, [aegisQ.data, vesselsQ.data, terraQ.data]);

  const usingLive = liveEvents.length > 0;
  const baseEvents = usingLive ? liveEvents : SEED_EVENTS;

  const lookbackCutoff = Date.now() - LOOKBACK_HOURS * 60 * 60_000;
  const filteredEvents = baseEvents
    .filter((e) => enabledDomains[e.domain])
    .filter((e) => e.timestamp >= lookbackCutoff);

  const windowMs = TIME_WINDOWS.find((w) => w.key === windowKey)?.ms ?? 15 * 60_000;
  const { clusters, loners } = useMemo(
    () => clusterEvents(filteredEvents, windowMs),
    [filteredEvents, windowMs],
  );

  const totalEvents = filteredEvents.length;
  const correlatedCount = clusters.reduce((acc, c) => acc + c.events.length, 0);

  function handleRefresh() {
    aegisQ.refetch();
    vesselsQ.refetch();
    terraQ.refetch();
  }

  function toggleDomain(d: Domain) {
    setEnabledDomains((prev) => ({ ...prev, [d]: !prev[d] }));
  }

  const earliest =
    filteredEvents.length > 0
      ? Math.min(...filteredEvents.map((e) => e.timestamp))
      : Date.now() - LOOKBACK_HOURS * 60 * 60_000;
  const latest =
    filteredEvents.length > 0 ? Math.max(...filteredEvents.map((e) => e.timestamp)) : Date.now();
  const span = Math.max(latest - earliest, 60_000);

  return (
    <div className="max-w-7xl mx-auto space-y-5 p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <GitBranch className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
            <span
              className="text-[10px] font-bold uppercase tracking-widest font-mono"
              style={{ color: '#8b7ac8' }}
            >
              ATLAS · Cross-Domain Worldline Correlation
            </span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">
            Worldline Correlation Theater
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Time-aligned threat surface across PARAGON security incidents, SEXTANT route anomalies,
            and DOMAINE physical / financial signals.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 text-[11px] border px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
            style={{ color: 'rgba(255,255,255,0.45)', borderColor: 'rgba(255,255,255,0.08)' }}
          >
            {isLoading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <RefreshCw className="w-3 h-3" />
            )}
            Re-correlate
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Events (last 8h)', value: totalEvents, color: '#8b7ac8' },
          {
            label: 'Correlated Clusters',
            value: clusters.length,
            color: clusters.length > 0 ? '#f5f5f5' : '#6b7280',
            pulse: clusters.length > 0,
          },
          { label: 'Cross-Domain Events', value: correlatedCount, color: '#c9b787' },
          {
            label: 'Source',
            value: usingLive ? 'LIVE' : 'DEMO',
            color: usingLive ? '#c9b787' : '#8b7ac8',
          },
        ].map((c) => (
          <div
            key={c.label}
            className="rounded-xl border p-4"
            style={{ borderColor: 'rgba(255,255,255,0.07)', background: 'rgba(255,255,255,0.015)' }}
          >
            <div className="flex items-center justify-between mb-2">
              <div
                className="text-[9px] font-medium uppercase tracking-widest"
                style={{ color: 'rgba(255,255,255,0.35)' }}
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
            <div className="text-2xl font-bold font-mono" style={{ color: c.color }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>

      {isError && !usingLive && (
        <div
          className="rounded-xl border px-4 py-2.5 flex items-center gap-3"
          style={{ borderColor: 'rgba(201,183,135,0.2)', background: 'rgba(201,183,135,0.04)' }}
        >
          <AlertTriangle className="w-3 h-3 shrink-0" style={{ color: '#c9b787' }} />
          <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
            Live worldline overlay API unavailable — showing seeded demo correlation set.
          </span>
        </div>
      )}

      <div
        className="rounded-xl border p-4 flex flex-wrap items-center gap-4"
        style={{ borderColor: 'rgba(255,255,255,0.07)', background: 'rgba(255,255,255,0.01)' }}
      >
        <div className="flex items-center gap-2">
          <Filter className="w-3 h-3" style={{ color: '#8b7ac8' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: 'rgba(255,255,255,0.55)' }}
          >
            Domains
          </span>
        </div>
        <div className="flex gap-2">
          {(Object.keys(DOMAIN_META) as Domain[]).map((d) => {
            const meta = DOMAIN_META[d];
            const Icon = meta.icon;
            const on = enabledDomains[d];
            return (
              <button
                key={d}
                onClick={() => toggleDomain(d)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-colors"
                style={{
                  color: on ? meta.color : 'rgba(255,255,255,0.35)',
                  background: on ? meta.bg : 'transparent',
                  borderColor: on ? meta.border : 'rgba(255,255,255,0.08)',
                }}
              >
                <Icon className="w-3 h-3" />
                {meta.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <Clock className="w-3 h-3" style={{ color: '#8b7ac8' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: 'rgba(255,255,255,0.55)' }}
          >
            Cluster window
          </span>
          <div
            className="flex border rounded-lg overflow-hidden"
            style={{ borderColor: 'rgba(255,255,255,0.1)' }}
          >
            {TIME_WINDOWS.map((w) => (
              <button
                key={w.key}
                onClick={() => setWindowKey(w.key)}
                className="text-[10px] px-2.5 py-1 transition-colors"
                style={{
                  color: windowKey === w.key ? '#0c1420' : 'rgba(255,255,255,0.5)',
                  background: windowKey === w.key ? '#8b7ac8' : 'transparent',
                }}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div
        className="rounded-xl border overflow-hidden"
        style={{ borderColor: 'rgba(255,255,255,0.07)' }}
      >
        <div
          className="p-4 border-b flex items-center gap-2"
          style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.01)' }}
        >
          <Activity className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
          <span className="text-[11px] font-semibold text-white">Time-Aligned Worldline Lanes</span>
          <span className="ml-auto text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>
            {fmtTime(earliest)} → {fmtTime(latest)}
          </span>
        </div>
        <div className="p-4 space-y-3">
          {(Object.keys(DOMAIN_META) as Domain[])
            .filter((d) => enabledDomains[d])
            .map((d) => {
              const meta = DOMAIN_META[d];
              const Icon = meta.icon;
              const laneEvents = filteredEvents.filter((e) => e.domain === d);
              return (
                <div key={d} className="flex items-center gap-3">
                  <div className="w-32 shrink-0 flex items-center gap-2">
                    <Icon className="w-3 h-3" style={{ color: meta.color }} />
                    <span className="text-[10px] font-mono" style={{ color: meta.color }}>
                      {meta.short}
                    </span>
                    <span
                      className="text-[9px] font-mono ml-auto"
                      style={{ color: 'rgba(255,255,255,0.3)' }}
                    >
                      {laneEvents.length}
                    </span>
                  </div>
                  <div
                    className="relative h-8 flex-1 rounded-md border"
                    style={{
                      borderColor: 'rgba(255,255,255,0.06)',
                      background: 'rgba(255,255,255,0.015)',
                    }}
                  >
                    {clusters.map((cl) => {
                      const left = ((cl.startedAt - earliest) / span) * 100;
                      const width = Math.max(((cl.endedAt - cl.startedAt) / span) * 100, 1.2);
                      return (
                        <div
                          key={`${d}-${cl.id}`}
                          className="absolute top-0 bottom-0 rounded"
                          style={{
                            left: `${left}%`,
                            width: `${width}%`,
                            background: 'rgba(245,245,245,0.08)',
                            border: '1px dashed rgba(245,245,245,0.4)',
                          }}
                        />
                      );
                    })}
                    {laneEvents.map((ev) => {
                      const left = ((ev.timestamp - earliest) / span) * 100;
                      return (
                        <div
                          key={ev.id}
                          title={`${ev.signalType} — ${ev.description}`}
                          className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full"
                          style={{
                            left: `calc(${left}% - 5px)`,
                            background: SEV_COLOR[ev.severity],
                            boxShadow: `0 0 0 2px ${meta.bg}, 0 0 10px ${SEV_COLOR[ev.severity]}80`,
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          <div
            className="flex items-center gap-4 text-[9px] pt-2 border-t"
            style={{ color: 'rgba(255,255,255,0.4)', borderColor: 'rgba(255,255,255,0.05)' }}
          >
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SEV_COLOR.critical }} />
              critical
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SEV_COLOR.warning }} />
              warning
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SEV_COLOR.info }} />
              info
            </span>
            <span className="flex items-center gap-1 ml-auto">
              <span
                className="w-3 h-2 rounded border-dashed border"
                style={{ borderColor: 'rgba(245,245,245,0.6)', background: 'rgba(245,245,245,0.08)' }}
              />
              cross-domain cluster
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: 'rgba(245,245,245,0.18)' }}
        >
          <div
            className="p-4 border-b flex items-center gap-2"
            style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(245,245,245,0.04)' }}
          >
            <Sparkles className="w-3.5 h-3.5" style={{ color: '#f5f5f5' }} />
            <span className="text-[11px] font-semibold text-white">Correlated Clusters</span>
            <span
              className="ml-auto text-[9px] font-mono"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              {clusters.length} cluster{clusters.length === 1 ? '' : 's'}
            </span>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {clusters.length === 0 && (
              <div
                className="p-8 text-center text-[10px]"
                style={{ color: 'rgba(255,255,255,0.35)' }}
              >
                No cross-domain clusters in the current window.
              </div>
            )}
            {clusters.map((cl) => (
              <div key={cl.id} className="p-3.5">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span
                    className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                    style={{ color: '#f5f5f5', background: 'rgba(245,245,245,0.1)' }}
                  >
                    Cluster · {cl.events.length} events
                  </span>
                  <span className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {fmtTime(cl.startedAt)} → {fmtTime(cl.endedAt)}
                  </span>
                  <span className="ml-auto flex gap-1">
                    {Array.from(cl.domains).map((d) => {
                      const meta = DOMAIN_META[d];
                      return (
                        <span
                          key={d}
                          className="text-[8px] font-bold font-mono px-1.5 py-0.5 rounded"
                          style={{
                            color: meta.color,
                            background: meta.bg,
                            border: `1px solid ${meta.border}`,
                          }}
                        >
                          {meta.short}
                        </span>
                      );
                    })}
                  </span>
                </div>
                <div className="space-y-1.5">
                  {cl.events.map((ev) => {
                    const meta = DOMAIN_META[ev.domain];
                    return (
                      <div key={ev.id} className="flex items-start gap-2 text-[10px]">
                        <span
                          className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
                          style={{ background: SEV_COLOR[ev.severity] }}
                        />
                        <span className="font-mono shrink-0" style={{ color: meta.color }}>
                          {meta.short}
                        </span>
                        <span
                          className="font-mono shrink-0"
                          style={{ color: 'rgba(255,255,255,0.35)' }}
                        >
                          {fmtTime(ev.timestamp)}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-white truncate">{ev.description}</div>
                          <div className="text-[9px]" style={{ color: 'rgba(255,255,255,0.35)' }}>
                            {ev.entity} · {ev.signalType}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: 'rgba(255,255,255,0.07)' }}
        >
          <div
            className="p-4 border-b flex items-center gap-2"
            style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.01)' }}
          >
            <Layers className="w-3.5 h-3.5" style={{ color: 'rgba(255,255,255,0.55)' }} />
            <span className="text-[11px] font-semibold text-white">Uncorrelated Signal Stream</span>
            <span
              className="ml-auto text-[9px] font-mono"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              {loners.length} event{loners.length === 1 ? '' : 's'}
            </span>
          </div>
          <div className="divide-y divide-white/[0.04] max-h-[420px] overflow-y-auto">
            {loners.length === 0 && (
              <div
                className="p-8 text-center text-[10px]"
                style={{ color: 'rgba(255,255,255,0.35)' }}
              >
                All visible events are part of a cluster.
              </div>
            )}
            {[...loners]
              .sort((a, b) => b.timestamp - a.timestamp)
              .map((ev) => {
                const meta = DOMAIN_META[ev.domain];
                const Icon = meta.icon;
                return (
                  <div key={ev.id} className="p-3 flex items-start gap-3">
                    <div
                      className="p-1.5 rounded-lg shrink-0"
                      style={{ background: meta.bg, border: `1px solid ${meta.border}` }}
                    >
                      <Icon className="w-3 h-3" style={{ color: meta.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span
                          className="text-[9px] font-bold uppercase tracking-widest px-1 py-0.5 rounded"
                          style={{
                            color: SEV_COLOR[ev.severity],
                            background: `${SEV_COLOR[ev.severity]}15`,
                          }}
                        >
                          {ev.severity}
                        </span>
                        <span className="text-[9px] font-mono" style={{ color: meta.color }}>
                          {meta.short}
                        </span>
                        <span
                          className="text-[9px] font-mono ml-auto"
                          style={{ color: 'rgba(255,255,255,0.35)' }}
                        >
                          {fmtRelative(ev.timestamp)}
                        </span>
                      </div>
                      <div className="text-[10px] text-white leading-snug">{ev.description}</div>
                      <div
                        className="text-[9px] mt-0.5"
                        style={{ color: 'rgba(255,255,255,0.35)' }}
                      >
                        {ev.entity} · {ev.signalType}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </div>
  );
}
