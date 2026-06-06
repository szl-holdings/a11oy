import {
  Activity,
  Brain,
  CheckCircle,
  Clock,
  Eye,
  Pause,
  Play,
  XCircle,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import {
  routeModel,
  emitProof,
  crossProductHandoff,
} from '@workspace/a11oy-orchestration/client';

const ACCENT = '#f5f5f5';
const DS = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    muted: 'rgba(255,255,255,0.25)',
  },
};

type KillChainStage = 'recon' | 'weaponize' | 'deliver' | 'exploit' | 'install' | 'c2' | 'actions';
type ThreatStatus =
  | 'detected'
  | 'classified'
  | 'auto_contained'
  | 'pending_approval'
  | 'contained'
  | 'dismissed';
type MitreTactic =
  | 'initial_access'
  | 'execution'
  | 'persistence'
  | 'privilege_escalation'
  | 'lateral_movement'
  | 'exfiltration';

interface ThreatIncident {
  id: string;
  title: string;
  timestamp: number;
  confidenceScore: number;
  severity: 'critical' | 'high' | 'medium';
  status: ThreatStatus;
  killChainStage: KillChainStage;
  mitreTactic: MitreTactic;
  mitreId: string;
  affectedAssets: string[];
  blastRadius: number;
  autonomousActions: string[];
  requiresApproval: boolean;
  approvalTimeout?: number;
  ttps: string[];
  adversaryGroup?: string;
}

interface PlaybookStep {
  id: string;
  action: string;
  status: 'pending' | 'running' | 'done' | 'skipped';
  durationMs?: number;
  requiresApproval: boolean;
}

const KILL_CHAIN: { id: KillChainStage; label: string; color: string }[] = [
  { id: 'recon', label: 'Recon', color: '#6b7280' },
  { id: 'weaponize', label: 'Weaponize', color: '#8a8a8a' },
  { id: 'deliver', label: 'Deliver', color: '#c9b787' },
  { id: 'exploit', label: 'Exploit', color: '#c9b787' },
  { id: 'install', label: 'Install', color: '#c9b787' },
  { id: 'c2', label: 'C2', color: '#f5f5f5' },
  { id: 'actions', label: 'Actions', color: '#f5f5f5' },
];

const _SEED_THREATS: ThreatIncident[] = [
  {
    id: 't001',
    title: 'APT29 lateral movement via PtH on DC-PROD-03',
    timestamp: Date.now() - 180000,
    confidenceScore: 94,
    severity: 'critical',
    status: 'auto_contained',
    killChainStage: 'c2',
    mitreTactic: 'lateral_movement',
    mitreId: 'T1550.002',
    affectedAssets: ['DC-PROD-03', 'WORKSTATION-44', 'ADC-01'],
    blastRadius: 78,
    autonomousActions: [
      'Isolated DC-PROD-03 from network segment',
      'Revoked PtH credentials batch',
      'Triggered forensic snapshot',
      'Notified SOC tier-2',
    ],
    requiresApproval: false,
    ttps: ['Pass-the-Hash', 'LSASS Dump', 'SMB Lateral'],
    adversaryGroup: 'APT29 (Cozy Bear)',
  },
  {
    id: 't002',
    title: 'Ransomware precursor: shadow copy deletion attempt',
    timestamp: Date.now() - 360000,
    confidenceScore: 88,
    severity: 'critical',
    status: 'pending_approval',
    killChainStage: 'actions',
    mitreTactic: 'execution',
    mitreId: 'T1490',
    affectedAssets: ['FILE-SRV-02', 'BACKUP-01'],
    blastRadius: 91,
    autonomousActions: ['Blocked vssadmin.exe execution', 'Quarantined process chain'],
    requiresApproval: true,
    approvalTimeout: 120,
    ttps: ['Shadow Copy Deletion', 'Volume Shadow Admin Abuse'],
    adversaryGroup: undefined,
  },
  {
    id: 't003',
    title: 'Credential spray against Azure AD — 847 attempts',
    timestamp: Date.now() - 600000,
    confidenceScore: 79,
    severity: 'high',
    status: 'classified',
    killChainStage: 'exploit',
    mitreTactic: 'initial_access',
    mitreId: 'T1110.003',
    affectedAssets: ['AzureAD-Tenant', 'MFA-Bypass-attempt×3'],
    blastRadius: 45,
    autonomousActions: ['Rate-limited source IPs', 'MFA enforcement hardened'],
    requiresApproval: false,
    ttps: ['Password Spray', 'Azure AD SSPR Abuse'],
  },
  {
    id: 't004',
    title: 'Suspicious Cobalt Strike beacon — FINANCE-WS-11',
    timestamp: Date.now() - 900000,
    confidenceScore: 96,
    severity: 'critical',
    status: 'contained',
    killChainStage: 'install',
    mitreTactic: 'persistence',
    mitreId: 'T1055.001',
    affectedAssets: ['FINANCE-WS-11'],
    blastRadius: 32,
    autonomousActions: [
      'Process terminated',
      'Memory forensic captured',
      'Host isolated',
      'C2 IP blocked at perimeter',
    ],
    requiresApproval: false,
    ttps: ['Process Injection', 'DLL Injection', 'Shellcode Execution'],
    adversaryGroup: 'FIN7',
  },
];

function ThreatCard({
  threat,
  onSelect,
  selected,
}: {
  threat: ThreatIncident;
  onSelect: () => void;
  selected: boolean;
}) {
  const stage = KILL_CHAIN.find((k) => k.id === threat.killChainStage)!;
  const statusConfig: Record<ThreatStatus, { label: string; color: string }> = {
    detected: { label: 'Detected', color: '#c9b787' },
    classified: { label: 'Classified', color: '#8a8a8a' },
    auto_contained: { label: 'Auto-Contained', color: '#6b8f71' },
    pending_approval: { label: 'Approval Required', color: '#f5f5f5' },
    contained: { label: 'Contained', color: '#6b8f71' },
    dismissed: { label: 'Dismissed', color: '#6b7280' },
  };
  const sc = statusConfig[threat.status];

  return (
    <button
      onClick={onSelect}
      className="w-full text-left rounded-xl border p-4 transition-all"
      style={{
        borderColor: selected ? `${ACCENT}40` : DS.border,
        background: selected ? `${ACCENT}08` : DS.surface,
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-bold text-white truncate">{threat.title}</div>
          <div className="text-[9px] mt-0.5 font-mono" style={{ color: DS.text.muted }}>
            {threat.mitreId} · {threat.adversaryGroup ?? 'Unknown Actor'} ·{' '}
            {Math.round((Date.now() - threat.timestamp) / 60000)}m ago
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className="px-1.5 py-0.5 rounded text-[9px] font-bold"
            style={{ background: `${sc.color}15`, color: sc.color }}
          >
            {sc.label}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-[9px]" style={{ color: DS.text.muted }}>
              Confidence
            </span>
            <span
              className="text-[10px] font-bold font-mono ml-auto"
              style={{ color: threat.confidenceScore > 90 ? ACCENT : '#c9b787' }}
            >
              {threat.confidenceScore}%
            </span>
          </div>
          <div className="h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${threat.confidenceScore}%`,
                background: threat.confidenceScore > 90 ? ACCENT : '#c9b787',
              }}
            />
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px]" style={{ color: DS.text.muted }}>
            Blast Radius
          </div>
          <div
            className="text-[11px] font-bold font-mono"
            style={{ color: threat.blastRadius > 70 ? ACCENT : '#c9b787' }}
          >
            {threat.blastRadius}
          </div>
        </div>
        <div
          className="px-2 py-1 rounded text-[9px] font-bold"
          style={{ background: `${stage.color}20`, color: stage.color }}
        >
          {stage.label}
        </div>
      </div>

      {threat.requiresApproval && threat.status === 'pending_approval' && (
        <div
          className="mt-2 flex items-center gap-2 p-2 rounded-lg"
          style={{ background: 'rgba(245,245,245,0.1)', border: '1px solid rgba(245,245,245,0.2)' }}
        >
          <Clock className="w-3 h-3 text-[#f5f5f5]" />
          <span className="text-[10px] text-[#f5f5f5]">
            Human approval required — {threat.approvalTimeout}s timeout
          </span>
        </div>
      )}
    </button>
  );
}

function KillChainViz({ stage }: { stage: KillChainStage }) {
  const idx = KILL_CHAIN.findIndex((k) => k.id === stage);
  return (
    <div className="flex items-center gap-1">
      {KILL_CHAIN.map((k, i) => (
        <div key={k.id} className="flex items-center gap-1">
          <div
            className="px-2 py-1 rounded text-[8px] font-bold transition-all"
            style={{
              background: i <= idx ? `${k.color}25` : 'rgba(255,255,255,0.03)',
              color: i <= idx ? k.color : 'rgba(255,255,255,0.2)',
              border: `1px solid ${i === idx ? `${k.color}60` : 'transparent'}`,
            }}
          >
            {k.label}
          </div>
          {i < KILL_CHAIN.length - 1 && (
            <div
              className="w-3 h-px"
              style={{ background: i < idx ? `${k.color}40` : 'rgba(255,255,255,0.05)' }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export default function AutonomousThreatEngine() {
  const [threats, setThreats] = useState<ThreatIncident[]>([]);
  const [selected, setSelected] = useState<string | null>('t001');
  const [autonomous, setAutonomous] = useState(true);
  const [playbook, setPlaybook] = useState<PlaybookStep[]>([]);
  const [scanPulse, setScanPulse] = useState(0);
  const _intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadIncidents = useCallback(async () => {
    try {
      const data = await api.threatEngine.incidents({ limit: 50 });
      if (data?.incidents?.length) {
        type IncidentRow = {
          id: string; title: string; detectedAt?: string; createdAt?: string;
          confidenceScore?: number; severity: string; status: string;
          killChainStage: string; mitreTactic: string; mitreId?: string;
          affectedAssets?: string[]; blastRadius?: number; autonomousActions?: string[];
          requiresApproval?: boolean; approvalTimeoutSecs?: number;
          ttps?: string[]; adversaryGroup?: string;
        };
        const mapped: ThreatIncident[] = data.incidents.map((i: IncidentRow) => ({
          id: i.id,
          title: i.title,
          timestamp: new Date(i.detectedAt ?? i.createdAt).getTime(),
          confidenceScore: i.confidenceScore ?? 80,
          severity: i.severity as ThreatIncident['severity'],
          status: i.status as ThreatStatus,
          killChainStage: i.killChainStage as KillChainStage,
          mitreTactic: i.mitreTactic as MitreTactic,
          mitreId: i.mitreId,
          affectedAssets: (i.affectedAssets as string[]) ?? [],
          blastRadius: i.blastRadius ?? 0,
          autonomousActions: (i.autonomousActions as string[]) ?? [],
          requiresApproval: i.requiresApproval ?? false,
          approvalTimeout: i.approvalTimeoutSecs,
          ttps: (i.ttps as string[]) ?? [],
          adversaryGroup: i.adversaryGroup ?? undefined,
        }));
        setThreats(mapped);
        setSelected(mapped[0]?.id ?? null);
      }
    } catch {
      /* fall back to seed data */
    }
  }, []);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

  const selectedThreat = threats.find((t) => t.id === selected) ?? null;

  useEffect(() => {
    const t = setInterval(() => setScanPulse((p) => (p + 1) % 100), 100);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!selectedThreat) return;
    setPlaybook([
      {
        id: 'p1',
        action: 'Threat classification via MITRE ATT&CK mapping',
        status: 'done',
        durationMs: 340,
        requiresApproval: false,
      },
      {
        id: 'p2',
        action: 'Kill chain stage determination',
        status: 'done',
        durationMs: 210,
        requiresApproval: false,
      },
      {
        id: 'p3',
        action: 'Blast radius calculation',
        status: 'done',
        durationMs: 180,
        requiresApproval: false,
      },
      {
        id: 'p4',
        action: 'Autonomous containment — network isolation',
        status: selectedThreat.status !== 'detected' ? 'done' : 'running',
        durationMs: 890,
        requiresApproval: false,
      },
      {
        id: 'p5',
        action: 'Credential revocation for affected accounts',
        status:
          selectedThreat.status === 'contained' || selectedThreat.status === 'auto_contained'
            ? 'done'
            : 'pending',
        requiresApproval: selectedThreat.requiresApproval,
      },
      {
        id: 'p6',
        action: 'Forensic memory snapshot collection',
        status: selectedThreat.status === 'contained' ? 'done' : 'pending',
        requiresApproval: false,
      },
      {
        id: 'p7',
        action: 'SOC tier-2 notification + enriched brief',
        status: 'done',
        durationMs: 120,
        requiresApproval: false,
      },
    ]);
  }, [selected, selectedThreat?.status]);

  const criticalCount = threats.filter((t) => t.severity === 'critical').length;
  const pendingApproval = threats.filter(
    (t) => t.requiresApproval && t.status === 'pending_approval',
  ).length;
  const autoContained = threats.filter(
    (t) => t.status === 'auto_contained' || t.status === 'contained',
  ).length;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-3.5 h-3.5" style={{ color: ACCENT }} />
            <span
              className="text-[10px] font-bold uppercase tracking-widest font-mono"
              style={{ color: ACCENT }}
            >
              PARAGON · Autonomous Threat Engine
            </span>
            <span
              className="px-1.5 py-0.5 rounded text-[8px] font-bold animate-pulse"
              style={{ background: 'rgba(245,245,245,0.15)', color: ACCENT }}
            >
              AUTONOMOUS ACTIVE
            </span>
          </div>
          <h1 className="text-xl font-bold text-white">Autonomous Threat Engine</h1>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
            Continuously scans, classifies, and auto-remediates threats using MITRE ATT&CK mapping
            with configurable human-in-the-loop approval gates.
          </p>
        </div>
        <button
          onClick={() => setAutonomous((v) => !v)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all"
          style={{
            color: autonomous ? ACCENT : 'rgba(255,255,255,0.5)',
            borderColor: autonomous ? 'rgba(245,245,245,0.3)' : 'rgba(255,255,255,0.1)',
            background: autonomous ? 'rgba(245,245,245,0.08)' : 'transparent',
          }}
        >
          {autonomous ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          {autonomous ? 'Autonomous: ON' : 'Autonomous: PAUSED'}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Active Threats', value: threats.length.toString(), color: ACCENT, pulse: true },
          {
            label: 'Critical Severity',
            value: criticalCount.toString(),
            color: '#c9b787',
            pulse: criticalCount > 0,
          },
          {
            label: 'Approval Required',
            value: pendingApproval.toString(),
            color: '#c9b787',
            pulse: pendingApproval > 0,
          },
          {
            label: 'Auto-Contained',
            value: autoContained.toString(),
            color: '#6b8f71',
            pulse: false,
          },
        ].map((c) => (
          <div
            key={c.label}
            className="rounded-xl border p-4 text-center"
            style={{ borderColor: `${c.color}20`, background: `${c.color}06` }}
          >
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <span className="text-2xl font-bold font-mono" style={{ color: c.color }}>
                {c.value}
              </span>
              {c.pulse && (
                <span
                  className="w-2 h-2 rounded-full animate-pulse shrink-0"
                  style={{ background: c.color }}
                />
              )}
            </div>
            <div
              className="text-[9px] uppercase tracking-wider"
              style={{ color: 'rgba(255,255,255,0.3)' }}
            >
              {c.label}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-2 space-y-3">
          <div
            className="text-[10px] font-bold uppercase tracking-wider"
            style={{ color: DS.text.muted }}
          >
            Threat Queue
          </div>
          {threats.map((t) => (
            <ThreatCard
              key={t.id}
              threat={t}
              selected={selected === t.id}
              onSelect={() => setSelected(t.id)}
            />
          ))}

          <div
            className="rounded-xl border p-3"
            style={{ borderColor: DS.border, background: DS.surface }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Eye className="w-3 h-3" style={{ color: ACCENT }} />
              <span className="text-[10px] font-bold text-white">Autonomous Scan</span>
              <span className="ml-auto text-[9px] font-mono" style={{ color: ACCENT }}>
                {scanPulse}%
              </span>
            </div>
            <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }}>
              <div
                className="h-full rounded-full transition-none"
                style={{ width: `${scanPulse}%`, background: `${ACCENT}60` }}
              />
            </div>
            <div className="text-[9px] mt-2" style={{ color: DS.text.muted }}>
              Scanning 1,247 endpoints · 23 threat feeds active · 14ms detection latency
            </div>
          </div>
        </div>

        <div className="col-span-3 space-y-4">
          {selectedThreat ? (
            <>
              <div
                className="rounded-xl border p-4"
                style={{ borderColor: DS.border, background: DS.surface }}
              >
                <div className="text-[10px] font-bold text-white mb-3">Kill Chain Position</div>
                <KillChainViz stage={selectedThreat.killChainStage} />

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[9px] mb-2" style={{ color: DS.text.muted }}>
                      MITRE ATT&CK Mapping
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedThreat.ttps.map((ttp) => (
                        <span
                          key={ttp}
                          className="px-1.5 py-0.5 rounded text-[8px]"
                          style={{ background: `${ACCENT}15`, color: ACCENT }}
                        >
                          {ttp}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 text-[10px] font-mono" style={{ color: '#8a8a8a' }}>
                      {selectedThreat.mitreId} · {selectedThreat.mitreTactic.replace(/_/g, ' ')}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] mb-2" style={{ color: DS.text.muted }}>
                      Affected Assets
                    </div>
                    {selectedThreat.affectedAssets.map((a) => (
                      <div key={a} className="flex items-center gap-1.5 mb-1">
                        <span className="w-1 h-1 rounded-full" style={{ background: ACCENT }} />
                        <span className="text-[10px] font-mono text-white/70">{a}</span>
                      </div>
                    ))}
                    {selectedThreat.adversaryGroup && (
                      <div className="mt-2 text-[10px]" style={{ color: '#c9b787' }}>
                        Actor: {selectedThreat.adversaryGroup}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div
                className="rounded-xl border p-4"
                style={{ borderColor: DS.border, background: DS.surface }}
              >
                <div className="text-[10px] font-bold text-white mb-3 flex items-center gap-2">
                  <Zap className="w-3 h-3" style={{ color: ACCENT }} />
                  Autonomous Containment Playbook
                </div>
                <div className="space-y-2">
                  {playbook.map((step) => {
                    const icons = {
                      done: CheckCircle,
                      running: Activity,
                      pending: Clock,
                      skipped: XCircle,
                    };
                    const Icon = icons[step.status];
                    const colors = {
                      done: '#6b8f71',
                      running: ACCENT,
                      pending: 'rgba(255,255,255,0.25)',
                      skipped: '#6b7280',
                    };
                    const color = colors[step.status];
                    return (
                      <div
                        key={step.id}
                        className="flex items-center gap-3 p-2 rounded-lg"
                        style={{
                          background:
                            step.status === 'running' ? `${ACCENT}08` : 'rgba(255,255,255,0.02)',
                        }}
                      >
                        <Icon
                          className="w-3.5 h-3.5 shrink-0"
                          style={{
                            color,
                            animation:
                              step.status === 'running' ? 'spin 1s linear infinite' : 'none',
                          }}
                        />
                        <span
                          className="flex-1 text-[10px]"
                          style={{
                            color:
                              step.status === 'pending' ? DS.text.muted : 'rgba(255,255,255,0.8)',
                          }}
                        >
                          {step.action}
                        </span>
                        {step.requiresApproval && step.status === 'pending' && (
                          <span
                            className="text-[8px] px-1.5 py-0.5 rounded"
                            style={{ background: '#c9b78715', color: '#c9b787' }}
                          >
                            APPROVAL
                          </span>
                        )}
                        {step.durationMs && (
                          <span className="text-[9px] font-mono" style={{ color: color }}>
                            {step.durationMs}ms
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {selectedThreat.requiresApproval &&
                  selectedThreat.status === 'pending_approval' && (
                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={async () => {
                          const t = selectedThreat;
                          const id = t.id;
                          setThreats((prev) =>
                            prev.map((x) => (x.id === id ? { ...x, status: 'contained' } : x)),
                          );
                          try {
                            await api.threatEngine.updateStatus(id, 'contained');
                          } catch {
                            /* best-effort — local state already updated */
                          }
                          // Material action → A11oy fabric: governed model
                          // call for the triage decision, an action_executed
                          // proof anchored to this incident, and (for
                          // critical/high severity) a cross-product handoff
                          // to Counsel for breach-notification review.
                          try {
                            await routeModel({
                              product: 'sentra',
                              model: 'Qwen/Qwen3-8B',
                              purpose: `threat triage · ${t.mitreId} · ${t.title}`,
                              deepLink: `/sentra/autonomous-threat-engine?id=${id}`,
                            });
                            await emitProof({
                              product: 'sentra',
                              kind: 'action_executed',
                              summary: `Contained ${t.mitreId} on ${t.affectedAssets[0] ?? 'host'} (blast ${t.blastRadius})`,
                              deepLink: `/sentra/autonomous-threat-engine?id=${id}`,
                              payload: {
                                incidentId: id,
                                mitreId: t.mitreId,
                                severity: t.severity,
                                blastRadius: t.blastRadius,
                              },
                            });
                            if (t.severity === 'critical' || t.severity === 'high') {
                              await crossProductHandoff({
                                fromProduct: 'sentra',
                                toProduct: 'counsel',
                                reason: `Breach-notification review for ${t.mitreId}`,
                                refId: id,
                                deepLink: `/sentra/autonomous-threat-engine?id=${id}`,
                                payload: {
                                  severity: t.severity,
                                  affectedAssets: t.affectedAssets,
                                },
                              });
                            }
                          } catch {
                            // Fabric proof emission is best-effort: containment
                            // proceeds even if the proof bus is unreachable.
                          }
                        }}
                        className="flex-1 py-2 rounded-lg text-xs font-bold"
                        style={{ background: ACCENT, color: 'white' }}
                        data-testid="approve-containment"
                      >
                        Approve & Escalate to Counsel
                      </button>
                      <button
                        onClick={async () => {
                          const id = selectedThreat.id;
                          setThreats((prev) =>
                            prev.map((t) => (t.id === id ? { ...t, status: 'dismissed' } : t)),
                          );
                          try {
                            await api.threatEngine.updateStatus(id, 'dismissed');
                          } catch {
                            /* best-effort — local state already updated */
                          }
                        }}
                        className="px-4 py-2 rounded-lg text-xs font-medium"
                        style={{
                          background: 'rgba(255,255,255,0.06)',
                          color: 'rgba(255,255,255,0.5)',
                        }}
                      >
                        Override
                      </button>
                    </div>
                  )}
              </div>
            </>
          ) : (
            <div
              className="flex items-center justify-center h-48 rounded-xl border"
              style={{ borderColor: DS.border }}
            >
              <p className="text-sm" style={{ color: DS.text.muted }}>
                Select a threat to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
