// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardQuery } from '@szl-holdings/api-client-react';

import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Database,
  Eye,
  GitBranch,
  Globe,
  Layers,
  Loader2,
  Lock,
  Network,
  Radio,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  ExecutiveSafeModeProvider,
  useExecutiveSafeMode,
  useExecutiveSafeModeToggle,
} from '../lib/executive-safe-mode-context';

type TwinHealth = 'stable' | 'degraded' | 'awaiting_approval' | 'offline';

interface DigitalTwin {
  id: string;
  name: string;
  domain: string;
  type: 'endpoint' | 'network' | 'cloud' | 'ot' | 'identity' | 'app';
  health: TwinHealth;
  driftScore: number;
  lastSync: string;
  proofState: 'verified' | 'pending' | 'unverified';
  incidents: number;
  evidence: string[];
  worldline: string;
}

interface ThreatEvent {
  id: string;
  twinId: string;
  timestamp: string;
  type: 'lateral_move' | 'exfil' | 'privilege_escalation' | 'persistence';
  severity: 'critical' | 'high' | 'medium';
  description: string;
  mitre: string;
}

interface AegisIncident {
  id: number;
  title: string;
  severity: string;
  status: string;
  mitreTactic?: string | null;
  mitreId?: string | null;
  assetId?: number | null;
  description?: string | null;
  createdAt: string;
  updatedAt: string;
}

const SEED_TWINS: DigitalTwin[] = [
  {
    id: 'tw-001',
    name: 'PROD-DC-CLUSTER',
    domain: 'Endpoint',
    type: 'endpoint',
    health: 'stable',
    driftScore: 2,
    lastSync: '12s ago',
    proofState: 'verified',
    incidents: 0,
    evidence: ['Config snapshot v4.2', 'Baseline hash match', 'Last audit: 6h ago'],
    worldline: 'WL-ALPHA',
  },
  {
    id: 'tw-002',
    name: 'CORE-NETWORK-FABRIC',
    domain: 'Network',
    type: 'network',
    health: 'stable',
    driftScore: 4,
    lastSync: '28s ago',
    proofState: 'verified',
    incidents: 0,
    evidence: ['Flow telemetry active', 'BGP routes nominal', 'Topology hash: 9a3f'],
    worldline: 'WL-ALPHA',
  },
  {
    id: 'tw-003',
    name: 'AWS-VPC-PROD',
    domain: 'Cloud',
    type: 'cloud',
    health: 'degraded',
    driftScore: 31,
    lastSync: '4m ago',
    proofState: 'pending',
    incidents: 2,
    evidence: ['IAM drift detected', '3 SGs misconfigured', 'Pending operator review'],
    worldline: 'WL-BETA',
  },
  {
    id: 'tw-004',
    name: 'OT-SCADA-CONTROL',
    domain: 'OT/ICS',
    type: 'ot',
    health: 'awaiting_approval',
    driftScore: 18,
    lastSync: '11m ago',
    proofState: 'pending',
    incidents: 1,
    evidence: ['PLC firmware delta', 'Protocol anomaly flagged', 'Awaiting CISO sign-off'],
    worldline: 'WL-GAMMA',
  },
  {
    id: 'tw-005',
    name: 'IDENTITY-FABRIC-AD',
    domain: 'Identity',
    type: 'identity',
    health: 'stable',
    driftScore: 6,
    lastSync: '45s ago',
    proofState: 'verified',
    incidents: 0,
    evidence: ['Group policy snapshot', 'Privileged accounts: 12', 'MFA coverage: 98.4%'],
    worldline: 'WL-ALPHA',
  },
  {
    id: 'tw-006',
    name: 'APP-TIER-K8S',
    domain: 'Application',
    type: 'app',
    health: 'degraded',
    driftScore: 24,
    lastSync: '7m ago',
    proofState: 'unverified',
    incidents: 3,
    evidence: ['Pod drift: 6 containers', 'CVE-2024-3890 exposed', 'Security context missing'],
    worldline: 'WL-BETA',
  },
  {
    id: 'tw-007',
    name: 'DB-CLUSTER-PG',
    domain: 'Database',
    type: 'endpoint',
    health: 'stable',
    driftScore: 1,
    lastSync: '18s ago',
    proofState: 'verified',
    incidents: 0,
    evidence: ['Schema hash verified', 'Replication lag: 0ms', 'Encryption: AES-256'],
    worldline: 'WL-ALPHA',
  },
  {
    id: 'tw-008',
    name: 'PERIMETER-FW-CLUSTER',
    domain: 'Network',
    type: 'network',
    health: 'stable',
    driftScore: 3,
    lastSync: '22s ago',
    proofState: 'verified',
    incidents: 0,
    evidence: ['Ruleset v71 active', 'GeoIP blocks active', 'Zero policy gaps'],
    worldline: 'WL-ALPHA',
  },
];

const SEED_EVENTS: ThreatEvent[] = [
  {
    id: 'evt-001',
    twinId: 'tw-003',
    timestamp: '14:32:01',
    type: 'privilege_escalation',
    severity: 'critical',
    description: 'IAM role chaining to cross-account admin detected in AWS VPC',
    mitre: 'T1548.005',
  },
  {
    id: 'evt-002',
    twinId: 'tw-006',
    timestamp: '14:28:45',
    type: 'lateral_move',
    severity: 'high',
    description: 'East-west movement via K8s service account token abuse',
    mitre: 'T1552.007',
  },
  {
    id: 'evt-003',
    twinId: 'tw-004',
    timestamp: '14:21:12',
    type: 'persistence',
    severity: 'high',
    description: 'Unauthorized PLC ladder logic modification attempt',
    mitre: 'T0873',
  },
  {
    id: 'evt-004',
    twinId: 'tw-006',
    timestamp: '14:15:33',
    type: 'exfil',
    severity: 'medium',
    description: 'Unusual egress from app tier to non-whitelisted endpoint',
    mitre: 'T1048.003',
  },
  {
    id: 'evt-005',
    twinId: 'tw-003',
    timestamp: '14:08:22',
    type: 'privilege_escalation',
    severity: 'high',
    description: 'Temporary security credentials escalated to persistent access',
    mitre: 'T1078.004',
  },
];

const SEVERITY_TYPE_MAP: Record<string, ThreatEvent['type']> = {
  critical: 'privilege_escalation',
  high: 'lateral_move',
  medium: 'persistence',
  low: 'exfil',
};

function incidentToEvent(inc: AegisIncident, idx: number): ThreatEvent {
  const twinIds = ['tw-003', 'tw-006', 'tw-004', 'tw-003', 'tw-006'];
  const sev = (
    ['critical', 'high', 'medium'].includes(inc.severity) ? inc.severity : 'medium'
  ) as ThreatEvent['severity'];
  return {
    id: `inc-${inc.id}`,
    twinId: twinIds[idx % twinIds.length] ?? 'tw-003',
    timestamp: new Date(inc.createdAt).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
    type: SEVERITY_TYPE_MAP[inc.severity] ?? 'lateral_move',
    severity: sev,
    description: inc.title,
    mitre: inc.mitreId ?? inc.mitreTactic ?? 'T1000',
  };
}

const HEALTH_CONFIG: Record<
  TwinHealth,
  { color: string; label: string; bg: string; border: string; dot?: boolean }
> = {
  stable: {
    color: '#c9b787',
    label: 'Stable',
    bg: 'rgba(201,183,135,0.08)',
    border: 'rgba(201,183,135,0.2)',
    dot: false,
  },
  degraded: {
    color: '#c9b787',
    label: 'Degraded',
    bg: 'rgba(201,183,135,0.08)',
    border: 'rgba(201,183,135,0.2)',
    dot: true,
  },
  awaiting_approval: {
    color: '#8b7ac8',
    label: 'Awaiting Approval',
    bg: 'rgba(139,122,200,0.08)',
    border: 'rgba(139,122,200,0.2)',
    dot: true,
  },
  offline: {
    color: '#f5f5f5',
    label: 'Offline',
    bg: 'rgba(245,245,245,0.08)',
    border: 'rgba(245,245,245,0.2)',
    dot: true,
  },
};

const SEV_COLOR: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#6b7280',
};
const TYPE_ICON: Record<string, typeof Server> = {
  endpoint: Server,
  network: Network,
  cloud: Globe,
  ot: Zap,
  identity: Shield,
  app: Layers,
  database: Database,
};

const PROOF_CONFIG: Record<string, { color: string; label: string }> = {
  verified: { color: '#c9b787', label: 'Proof Verified' },
  pending: { color: '#c9b787', label: 'Proof Pending' },
  unverified: { color: '#f5f5f5', label: 'Unverified' },
};

function DriftBadge({ score }: { score: number }) {
  const color = score <= 5 ? '#c9b787' : score <= 15 ? '#c9b787' : '#f5f5f5';
  return (
    <span
      className="text-[8px] font-bold font-mono px-1.5 py-0.5 rounded"
      style={{ color, background: `${color}15`, border: `1px solid ${color}30` }}
    >
      Δ {score}%
    </span>
  );
}

function TwinStatusRail({ twins }: { twins: DigitalTwin[] }) {
  return (
    <div className="flex gap-1 flex-wrap">
      {twins.map((tw) => {
        const h = HEALTH_CONFIG[tw.health];
        return (
          <div
            key={tw.id}
            className="flex items-center gap-1 px-2 py-1 rounded-lg"
            style={{ background: h.bg, border: `1px solid ${h.border}` }}
          >
            {h.dot && (
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse shrink-0"
                style={{ background: h.color }}
              />
            )}
            <span className="text-[9px] font-mono" style={{ color: h.color }}>
              {tw.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function EvidenceOverlay({ twin, onClose }: { twin: DigitalTwin; onClose: () => void }) {
  const h = HEALTH_CONFIG[twin.health];
  const proof = PROOF_CONFIG[twin.proofState];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end p-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-2xl border flex flex-col gap-0 overflow-hidden"
        style={{ background: '#0c1420', borderColor: 'rgba(255,255,255,0.1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
          <div className="flex items-center justify-between mb-2">
            <span
              className="text-[9px] font-bold uppercase tracking-widest font-mono"
              style={{ color: 'rgba(139,122,200,0.8)' }}
            >
              ATLAS · Evidence Overlay
            </span>
            <button
              onClick={onClose}
              className="text-[10px] text-slate-500 hover:text-white px-1.5 py-0.5 rounded hover:bg-white/5 transition-colors"
            >
              ✕
            </button>
          </div>
          <div className="text-sm font-bold text-white">{twin.name}</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className="text-[9px] px-1.5 py-0.5 rounded border"
              style={{ color: h.color, background: h.bg, borderColor: h.border }}
            >
              {h.label}
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded"
              style={{ color: proof.color, background: `${proof.color}15` }}
            >
              {proof.label}
            </span>
            <DriftBadge score={twin.driftScore} />
          </div>
        </div>
        <div className="p-4 space-y-2">
          <div
            className="text-[9px] font-bold uppercase tracking-widest mb-2"
            style={{ color: 'rgba(255,255,255,0.3)' }}
          >
            Evidence Chain
          </div>
          {twin.evidence.map((ev, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-[10px]"
              style={{ color: 'rgba(255,255,255,0.65)' }}
            >
              <CheckCircle className="w-2.5 h-2.5 mt-0.5 shrink-0" style={{ color: '#c9b787' }} />
              {ev}
            </div>
          ))}
        </div>
        <div
          className="p-4 border-t flex items-center gap-2"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}
        >
          <span className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Worldline: {twin.worldline}
          </span>
          <span className="ml-auto text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Sync: {twin.lastSync}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function AegisAtlasRuntime() {
  return (
    <ExecutiveSafeModeProvider>
      <AegisAtlasRuntimeContent />
    </ExecutiveSafeModeProvider>
  );
}

function AegisAtlasRuntimeContent() {
  const [selectedTwin, setSelectedTwin] = useState<DigitalTwin | null>(null);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [_pulse, setPulse] = useState(false);
  const safeMode = useExecutiveSafeMode();
  const [, setSafeMode] = useExecutiveSafeModeToggle();

  const {
    data: incidentData,
    isLoading: loadingIncidents,
    refetch,
  } = useStandardQuery<AegisIncident[]>({
    queryKey: ['firestorm-incidents-atlas'],
    queryFn: () => apiFetch<AegisIncident[]>('/firestorm/incidents'),
    staleTime: 30000,
    retry: 1,
  });

  const liveIncidents = Array.isArray(incidentData) ? incidentData : [];
  const liveEvents: ThreatEvent[] = liveIncidents
    .filter(
      (inc) => ['critical', 'high', 'medium'].includes(inc.severity) && inc.status !== 'resolved',
    )
    .slice(0, 8)
    .map((inc, idx) => incidentToEvent(inc, idx));

  const events = liveEvents.length > 0 ? liveEvents : SEED_EVENTS;

  const TWINS = SEED_TWINS.map((tw) => ({
    ...tw,
    incidents:
      liveIncidents.filter(
        (inc) => inc.status !== 'resolved' && ['critical', 'high'].includes(inc.severity),
      ).length > 0 && tw.health !== 'stable'
        ? tw.incidents + liveIncidents.filter((inc) => inc.status !== 'resolved').length
        : tw.incidents,
  }));

  const visibleTwins = safeMode
    ? TWINS.filter((t) => t.health === 'stable' && t.proofState === 'verified')
    : TWINS;
  const visibleEvents = safeMode ? [] : events;

  const stable = TWINS.filter((t) => t.health === 'stable');
  const degraded = TWINS.filter((t) => t.health === 'degraded');
  const awaiting = TWINS.filter((t) => t.health === 'awaiting_approval');

  function handleSync() {
    setLastRefresh(new Date());
    refetch();
  }

  useEffect(() => {
    const t = setInterval(() => {
      setPulse((p) => !p);
    }, 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
            <span
              className="text-[10px] font-bold uppercase tracking-widest font-mono"
              style={{ color: '#8b7ac8' }}
            >
              PARAGON · ATLAS Spatial Runtime
            </span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">Posture Twin Theater</h1>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
            Live spatial twin state with incident theater, drift monitoring, and evidence-verified
            proof states.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setSafeMode(!safeMode)}
            className="flex items-center gap-1.5 text-[11px] border px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
            style={
              safeMode
                ? {
                    color: '#8b7ac8',
                    borderColor: 'rgba(139,122,200,0.4)',
                    background: 'rgba(139,122,200,0.1)',
                  }
                : { color: 'rgba(255,255,255,0.4)', borderColor: 'rgba(255,255,255,0.08)' }
            }
          >
            <Lock className="w-3 h-3" /> {safeMode ? 'Safe Mode ON' : 'Safe Mode'}
          </button>
          <button
            onClick={handleSync}
            className="flex items-center gap-1.5 text-[11px] border px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors shrink-0"
            style={{ color: 'rgba(255,255,255,0.4)', borderColor: 'rgba(255,255,255,0.08)' }}
          >
            {loadingIncidents ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <RefreshCw className="w-3 h-3" />
            )}{' '}
            Sync
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Twins Online', value: TWINS.length, color: '#8b7ac8' },
          { label: 'Stable', value: stable.length, color: '#c9b787' },
          {
            label: 'Degraded',
            value: degraded.length,
            color: '#c9b787',
            pulse: degraded.length > 0,
          },
          {
            label: 'Awaiting Approval',
            value: awaiting.length,
            color: '#8b7ac8',
            pulse: awaiting.length > 0,
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

      {liveIncidents.length > 0 && !safeMode && (
        <div
          className="rounded-xl border px-4 py-2.5 flex items-center gap-3"
          style={{ borderColor: 'rgba(245,245,245,0.12)', background: 'rgba(245,245,245,0.02)' }}
        >
          <Activity className="w-3 h-3 shrink-0" style={{ color: '#f5f5f5' }} />
          <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
            <span className="font-bold font-mono" style={{ color: '#f5f5f5' }}>
              {liveIncidents.filter((i) => i.status !== 'resolved').length}
            </span>{' '}
            live incident
            {liveIncidents.filter((i) => i.status !== 'resolved').length !== 1 ? 's' : ''} ingested
            from PARAGON — Incident Theater shows real-time feed
          </span>
          <span className="ml-auto text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.2)' }}>
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
        </div>
      )}

      {safeMode && (
        <div
          className="rounded-xl border p-3 flex items-center gap-3"
          style={{ borderColor: 'rgba(139,122,200,0.25)', background: 'rgba(139,122,200,0.06)' }}
        >
          <Lock className="w-3.5 h-3.5 shrink-0" style={{ color: '#8b7ac8' }} />
          <div>
            <div className="text-[10px] font-bold" style={{ color: '#8b7ac8' }}>
              Executive Safe Mode Active
            </div>
            <div className="text-[9px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Only verified/stable twins shown. {TWINS.length - visibleTwins.length} degraded or
              unreviewed twin{TWINS.length - visibleTwins.length !== 1 ? 's' : ''} hidden. Incident
              theater suppressed pending review.
            </div>
          </div>
        </div>
      )}

      <div
        className="rounded-xl border p-4"
        style={{ borderColor: 'rgba(139,122,200,0.12)', background: 'rgba(139,122,200,0.02)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Radio className="w-3 h-3" style={{ color: '#8b7ac8' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest font-mono"
            style={{ color: '#8b7ac8' }}
          >
            Twin Status Rail
          </span>
          <span
            className="ml-auto text-[9px] font-mono"
            style={{ color: 'rgba(255,255,255,0.25)' }}
          >
            Last sync: {lastRefresh.toLocaleTimeString()}
          </span>
        </div>
        <TwinStatusRail twins={visibleTwins} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: 'rgba(255,255,255,0.07)' }}
        >
          <div
            className="p-4 border-b flex items-center gap-2"
            style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.01)' }}
          >
            <Layers className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
            <span className="text-[11px] font-semibold text-white">Spatial Twin Grid</span>
            <span
              className="ml-auto text-[9px] font-mono"
              style={{ color: 'rgba(255,255,255,0.3)' }}
            >
              {visibleTwins.length}
              {safeMode ? ` / ${TWINS.length} (filtered)` : ''} twins
            </span>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {visibleTwins.map((tw) => {
              const h = HEALTH_CONFIG[tw.health];
              const TIcon = TYPE_ICON[tw.type] ?? Server;
              const proof = PROOF_CONFIG[tw.proofState];
              return (
                <div
                  key={tw.id}
                  className="p-3.5 hover:bg-white/3 transition-colors cursor-pointer group"
                  onClick={() => setSelectedTwin(tw)}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="p-1.5 rounded-lg shrink-0"
                      style={{ background: `${h.color}15`, border: `1px solid ${h.color}25` }}
                    >
                      <TIcon className="w-3 h-3" style={{ color: h.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[11px] font-semibold text-white truncate">
                          {tw.name}
                        </span>
                        <DriftBadge score={tw.driftScore} />
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px]" style={{ color: 'rgba(255,255,255,0.3)' }}>
                          {tw.domain}
                        </span>
                        <span className="text-[9px]" style={{ color: proof.color }}>
                          · {proof.label}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 flex items-center gap-2">
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded border flex items-center gap-1"
                        style={{ color: h.color, background: h.bg, borderColor: h.border }}
                      >
                        {h.dot && (
                          <span
                            className="w-1 h-1 rounded-full animate-pulse"
                            style={{ background: h.color }}
                          />
                        )}
                        {h.label}
                      </span>
                      {tw.incidents > 0 && (
                        <span
                          className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                          style={{ color: '#f5f5f5', background: 'rgba(245,245,245,0.1)' }}
                        >
                          {tw.incidents}i
                        </span>
                      )}
                      <Eye
                        className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ color: 'rgba(255,255,255,0.35)' }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
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
            <Activity className="w-3.5 h-3.5" style={{ color: '#f5f5f5' }} />
            <span className="text-[11px] font-semibold text-white">Incident Theater</span>
            <span
              className="ml-auto text-[9px] font-bold uppercase tracking-widest"
              style={{ color: liveEvents.length > 0 ? '#f5f5f5' : 'rgba(255,255,255,0.3)' }}
            >
              {liveEvents.length > 0 ? 'LIVE' : 'SEED'}
            </span>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {safeMode && visibleEvents.length === 0 && (
              <div className="p-6 flex flex-col items-center gap-2 text-center">
                <Lock className="w-5 h-5" style={{ color: 'rgba(139,122,200,0.4)' }} />
                <div className="text-[10px] font-medium" style={{ color: 'rgba(139,122,200,0.6)' }}>
                  Incident Theater Suppressed
                </div>
                <div className="text-[9px]" style={{ color: 'rgba(255,255,255,0.25)' }}>
                  Active incident data is hidden in executive safe mode until reviewed and approved
                  by the SOC team.
                </div>
              </div>
            )}
            {visibleEvents.map((ev) => {
              const twin = TWINS.find((t) => t.id === ev.twinId);
              return (
                <div key={ev.id} className="p-3.5">
                  <div className="flex items-start gap-3">
                    <div
                      className="p-1.5 rounded-lg shrink-0 mt-0.5"
                      style={{
                        background: `${SEV_COLOR[ev.severity]}15`,
                        border: `1px solid ${SEV_COLOR[ev.severity]}25`,
                      }}
                    >
                      <AlertTriangle
                        className="w-3 h-3"
                        style={{ color: SEV_COLOR[ev.severity] }}
                      />
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
                        <span
                          className="text-[9px] font-mono"
                          style={{ color: 'rgba(255,255,255,0.25)' }}
                        >
                          {ev.timestamp}
                        </span>
                        <span
                          className="text-[9px] font-mono px-1 py-0.5 rounded"
                          style={{
                            color: 'rgba(139,122,200,0.7)',
                            background: 'rgba(139,122,200,0.08)',
                          }}
                        >
                          {ev.mitre}
                        </span>
                      </div>
                      <div className="text-[11px] text-white mb-0.5 leading-snug">
                        {ev.description}
                      </div>
                      {twin && (
                        <div
                          className="flex items-center gap-1 text-[9px]"
                          style={{ color: 'rgba(255,255,255,0.3)' }}
                        >
                          <ChevronRight className="w-2.5 h-2.5" />
                          <span>{twin.name}</span>
                          <span>· {twin.worldline}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div
        className="rounded-xl border p-4"
        style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.01)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
          <span className="text-[11px] font-semibold text-white">Worldline Map</span>
          <a
            href="/command/strategy/worldline-registry"
            className="ml-auto flex items-center gap-1 text-[9px] px-2 py-1 rounded-lg border transition-colors hover:bg-white/5"
            style={{
              color: '#8b7ac8',
              borderColor: 'rgba(139,122,200,0.25)',
              background: 'rgba(139,122,200,0.06)',
            }}
          >
            <Eye className="w-2.5 h-2.5" />
            View Worldline Registry →
          </a>
        </div>
        <div className="flex gap-4 flex-wrap">
          {['WL-ALPHA', 'WL-BETA', 'WL-GAMMA'].map((wl) => {
            const wlTwins = TWINS.filter((t) => t.worldline === wl);
            const allStable = wlTwins.every((t) => t.health === 'stable');
            const color = allStable
              ? '#c9b787'
              : wlTwins.some((t) => t.health === 'degraded')
                ? '#c9b787'
                : '#8b7ac8';
            return (
              <a
                key={wl}
                href="/command/strategy/worldline-registry"
                className="rounded-lg border px-4 py-3 flex-1 min-w-[160px] block hover:brightness-110 transition-all cursor-pointer"
                style={{
                  borderColor: `${color}25`,
                  background: `${color}08`,
                  textDecoration: 'none',
                }}
              >
                <div
                  className="text-[9px] font-bold uppercase tracking-widest mb-1 font-mono"
                  style={{ color }}
                >
                  {wl}
                </div>
                <div className="text-lg font-bold" style={{ color }}>
                  {wlTwins.length}
                </div>
                <div className="text-[9px]" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  twins ·{' '}
                  {allStable
                    ? 'All stable'
                    : `${wlTwins.filter((t) => t.health !== 'stable').length} need attention`}
                </div>
              </a>
            );
          })}
        </div>
      </div>

      {selectedTwin && (
        <EvidenceOverlay twin={selectedTwin} onClose={() => setSelectedTwin(null)} />
      )}
    </div>
  );
}
