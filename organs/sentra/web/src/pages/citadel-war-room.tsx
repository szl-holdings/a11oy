import { LiveClock } from '@szl-holdings/shared-ui/live-clock';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  ClipboardList,
  Database,
  FileText,
  Pause,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  Shield,
  Users,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

const DS = {
  bg: '#070b12',
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    muted: 'rgba(255,255,255,0.25)',
  },
};

const SEV: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#c9b787',
  low: '#c9b787',
  info: '#4a6070',
};

interface CrisisEvent {
  id: string;
  time: string;
  elapsed: string;
  title: string;
  detail: string;
  severity: 'critical' | 'high' | 'medium' | 'info';
  source: string;
  actor?: string;
  domain?: string;
  confirmed: boolean;
}

interface Decision {
  id: string;
  time: string;
  title: string;
  rationale: string;
  decidedBy: string;
  outcome: string;
  status: 'enacted' | 'pending' | 'superseded';
}

interface ResourceAssignment {
  id: string;
  role: string;
  name: string;
  domain: string;
  task: string;
  status: 'active' | 'standby' | 'unavailable';
  eta?: string;
  escalatable?: boolean;
}

interface CommEntry {
  id: string;
  time: string;
  from: string;
  role: string;
  message: string;
  type: 'intel' | 'action' | 'escalation' | 'update' | 'broadcast';
  priority?: 'urgent' | 'normal';
}

const STATIC_TIMELINE: CrisisEvent[] = [
  {
    id: 'E001',
    time: '14:22',
    elapsed: 'T+0',
    title: 'Initial Alert — SIEM Detection',
    detail: 'APT29 TTP pattern matched on DC-PROD-03. Lateral movement via SMB. Confidence 96/100.',
    severity: 'critical',
    source: 'SIEM · Sentinel Watch',
    actor: 'APT29',
    domain: 'defense',
    confirmed: true,
  },
  {
    id: 'E002',
    time: '14:24',
    elapsed: 'T+2m',
    title: 'Crisis Declared — ICS Level 3',
    detail:
      'J. Chen declared Crisis ICS Level 3. Crisis response activated. Playbook PB-APT-001 initiated.',
    severity: 'critical',
    source: 'Incident Command',
    confirmed: true,
  },
  {
    id: 'E003',
    time: '14:26',
    elapsed: 'T+4m',
    title: 'Labs Pre-Detection Confirmed',
    detail:
      'Neural explorer had flagged pattern 8 minutes before SIEM alert. APT29 C2 beacon on INC-2846 linked.',
    severity: 'high',
    source: 'PARAGON Labs · AI',
    confirmed: true,
  },
  {
    id: 'E004',
    time: '14:29',
    elapsed: 'T+7m',
    title: 'Managed Client Impact Assessment',
    detail:
      'DC-PROD-03 is Northgate managed asset. SLA ticket #4827 potentially compromised. Client notified.',
    severity: 'high',
    source: 'MSP Command',
    actor: 'Northgate',
    domain: 'operations',
    confirmed: true,
  },
  {
    id: 'E005',
    time: '14:31',
    elapsed: 'T+9m',
    title: 'Evidence Preservation Initiated',
    detail:
      'Memory dump ordered on DC-PROD-03. Log preservation on 4 adjacent hosts. Chain of custody active.',
    severity: 'medium',
    source: 'Forensics · J. Park',
    confirmed: true,
  },
  {
    id: 'E006',
    time: '14:35',
    elapsed: 'T+13m',
    title: 'CVE-2024-3400 Correlation',
    detail:
      'Unpatched PA Firewall FW-EDGE-01 identified as likely initial access vector. CVE linked to this campaign.',
    severity: 'critical',
    source: 'Vulnerability Intel',
    confirmed: true,
  },
  {
    id: 'E007',
    time: '14:38',
    elapsed: 'T+16m',
    title: 'HITL Isolation Request — Pending Approval',
    detail:
      'Automated containment recommendation: isolate DC-PROD-03 via EDR. Awaiting analyst approval.',
    severity: 'high',
    source: 'SOAR · Playbook PB-APT-001',
    confirmed: false,
  },
  {
    id: 'E008',
    time: '14:47',
    elapsed: 'T+25m',
    title: 'S3 Exfiltration Pattern — ALT-5821',
    detail:
      'Data exfil pattern on 3 S3 buckets correlated with APT29 staging. TTL-based extraction. Blocked at edge.',
    severity: 'critical',
    source: 'Cloud Monitor',
    confirmed: true,
  },
  {
    id: 'E009',
    time: '14:52',
    elapsed: 'T+30m',
    title: 'C2 Beacon Severed — INC-2846',
    detail:
      'APT29 C2 communication path severed. Firewall rule deployed. Beacon re-establishment attempts detected.',
    severity: 'high',
    source: 'Network Defense · M. Rodriguez',
    confirmed: true,
  },
  {
    id: 'E010',
    time: '15:03',
    elapsed: 'T+41m',
    title: 'CISO Brief Delivered',
    detail:
      'Executive brief delivered to CISO. Board notification drafted. PR hold in place. Legal engaged.',
    severity: 'medium',
    source: 'Incident Command',
    confirmed: true,
  },
  {
    id: 'E011',
    time: '15:05',
    elapsed: 'T+43m',
    title: 'Containment Phase Active',
    detail:
      'Primary containment complete. Secondary sweep of adjacent hosts underway. Attribution confidence 94%.',
    severity: 'medium',
    source: 'SOC Lead',
    confirmed: true,
  },
];

const DECISIONS: Decision[] = [
  {
    id: 'D001',
    time: '14:26',
    title: 'Declare ICS Level 3 Crisis',
    rationale:
      'Confirmed APT29 lateral movement on production infrastructure with 3 managed clients at risk. Escalation threshold met.',
    decidedBy: 'J. Chen (Incident Commander)',
    outcome: 'Full crisis response activation. PB-APT-001 initiated. All hands on deck.',
    status: 'enacted',
  },
  {
    id: 'D002',
    time: '14:38',
    title: 'Defer Northgate Service Migration',
    rationale:
      'TKT-4827 (Northgate server migration) paused. DC-PROD-03 is the target host — migrating now would disrupt forensics and risk evidence contamination.',
    decidedBy: 'R. Davis (MSP Lead)',
    outcome: "TKT-4827 moved to 'Hold — Security Event' status. Northgate CISO notified.",
    status: 'enacted',
  },
  {
    id: 'D003',
    time: '14:39',
    title: 'Hold EDR Isolation — Preserve Evidence',
    rationale:
      "Isolation of DC-PROD-03 will sever the attacker's active session, but also destroy live forensic opportunity. Decision: monitor + collect before isolating.",
    decidedBy: 'J. Chen (Incident Commander)',
    outcome:
      '15-minute evidence collection window. EDR isolation held pending memory dump completion.',
    status: 'enacted',
  },
  {
    id: 'D004',
    time: '14:52',
    title: 'Execute EDR Isolation on DC-PROD-03',
    rationale:
      'Evidence collection complete. Memory dump captured. Live threat still active. Risk of further lateral movement exceeds forensic benefit of continued monitoring.',
    decidedBy: 'J. Chen + S. Park (Approver)',
    outcome: 'DC-PROD-03 isolated at 14:52. 3 adjacent hosts flagged for secondary sweep.',
    status: 'enacted',
  },
  {
    id: 'D005',
    time: '15:03',
    title: 'Engage External Forensics — CrowdStrike IR',
    rationale:
      'Internal IR capacity stretched across 4 concurrent incidents. APT29 campaign requires dedicated specialized expertise for full attribution and remediation.',
    decidedBy: 'J. Chen (Incident Commander)',
    outcome:
      'CrowdStrike IR engaged. SLA: 4-hour on-site response. Legal hold on all logs initiated.',
    status: 'pending',
  },
];

const RESOURCES: ResourceAssignment[] = [
  { id: 'R001', role: 'Incident Commander', name: 'J. Chen', domain: 'Defense', task: 'Directing containment and managing ICS L3 protocol', status: 'active' },
  { id: 'R002', role: 'Lead Threat Analyst', name: 'S. Park', domain: 'Defense', task: 'APT29 TTP attribution, C2 mapping, kill chain analysis', status: 'active' },
  { id: 'R003', role: 'Forensics Lead', name: 'M. Rodriguez', domain: 'Defense', task: 'Memory dump analysis, DC-PROD-03 forensic imaging', status: 'active' },
  { id: 'R004', role: 'MSP Client Lead', name: 'R. Davis', domain: 'Operations', task: 'Northgate communication, SLA breach mitigation, client impact', status: 'active' },
  { id: 'R005', role: 'Intel Analyst', name: 'Neural Intelligence System', domain: 'Labs', task: 'Real-time threat correlation, APT29 campaign pattern analysis', status: 'active' },
  { id: 'R006', role: 'Network Defense', name: 'A. Thompson', domain: 'Defense', task: 'Firewall rule deployment, C2 path severing, perimeter hardening', status: 'active' },
  { id: 'R007', role: 'Legal Counsel', name: 'K. Wilson (PRISM)', domain: 'Legal', task: 'Evidence preservation requirements, breach notification obligations', status: 'standby', eta: '30m' },
  { id: 'R008', role: 'Executive Liaison', name: 'P. Santos', domain: 'Executive', task: 'CISO briefing, board notification draft, PR hold coordination', status: 'standby' },
  { id: 'R009', role: 'Cloud Security', name: 'T. Kim', domain: 'Infrastructure', task: 'S3 bucket forensics, CloudTrail preservation, IAM audit', status: 'active' },
  { id: 'R010', role: 'External IR (Pending)', name: 'CrowdStrike', domain: 'External', task: 'Deep APT29 attribution, remediation roadmap, threat hunt', status: 'unavailable', eta: '4h on-site' },
];

const INIT_COMMS: CommEntry[] = [
  { id: 'C001', time: '14:22', from: 'Sentinel SIEM', role: 'Automated System', message: 'ALERT P1: APT29 lateral movement detected on DC-PROD-03. MITRE T1021.002. Confidence 96. Incident INC-2847 opened.', type: 'intel', priority: 'urgent' },
  { id: 'C002', time: '14:25', from: 'J. Chen', role: 'Incident Commander', message: 'Confirming ICS activation. Level 3. Crisis response open. All leads report in. PB-APT-001 active. Northgate impact assessment needed immediately.', type: 'action', priority: 'urgent' },
  { id: 'C003', time: '14:27', from: 'Neural Intelligence System', role: 'AI Intel Agent', message: 'Neural explorer analysis complete. APT29 C2 infrastructure overlaps with INC-2846. Pre-detection signal was 8 minutes ahead of SIEM. Attribution confidence: 94%.', type: 'intel' },
  { id: 'C004', time: '14:29', from: 'R. Davis', role: 'MSP Client Lead', message: "Northgate CISO K. O'Brien contacted. Confirmed DC-PROD-03 is critical infrastructure for their migration. TKT-4827 placed on hold. They're requesting hourly updates.", type: 'update' },
  { id: 'C005', time: '14:33', from: 'S. Park', role: 'Lead Threat Analyst', message: 'APT29 Kill chain mapped: Recon → FW exploit (CVE-2024-3400) → Initial access → Credential harvesting → Lateral move SMB → DC-PROD-03. Staging via S3.', type: 'intel' },
  { id: 'C006', time: '14:41', from: 'J. Chen', role: 'Incident Commander', message: 'Decision logged: Holding EDR isolation for 15 min evidence window. M. Rodriguez — begin memory dump NOW. S. Park — continue live monitoring. A. Thompson — block all SMB to DC-PROD-03 adjacent hosts.', type: 'action', priority: 'urgent' },
  { id: 'C007', time: '14:52', from: 'J. Chen', role: 'Incident Commander', message: 'EDR isolation approved and executed on DC-PROD-03 at 14:52. Memory dump complete. 3 adjacent hosts flagged. C2 beacon severed by A. Thompson 14:50. Moving to eradication phase prep.', type: 'action' },
  { id: 'C008', time: '15:02', from: 'P. Santos', role: 'Executive Liaison', message: 'CISO brief delivered. Board notification draft ready — holding pending legal review. PR statement drafted. No external disclosure. Legal hold on all logs confirmed by K. Wilson.', type: 'update' },
  { id: 'C009', time: '15:05', from: 'INCIDENT SYSTEM', role: 'Automated Broadcast', message: 'BROADCAST: Crisis status update distributed to all connected verticals. SEXTANT, DOMAINE, PRISM, PARAGON — crisis banner active. Cross-domain impact assessment underway.', type: 'broadcast' },
];

const COMM_COLORS: Record<string, string> = {
  intel: '#8a8a8a',
  action: '#f5f5f5',
  escalation: '#c9b787',
  update: '#c9b787',
  broadcast: '#22d3ee',
};

const STATUS_COLORS: Record<string, string> = {
  active: '#c9b787',
  standby: '#c9b787',
  unavailable: '#4a6070',
};

const DECISION_COLORS: Record<string, string> = {
  enacted: '#c9b787',
  pending: '#c9b787',
  superseded: '#4a6070',
};

type WarRoomTab = 'timeline' | 'resources' | 'decisions' | 'comms' | 'drill';

function ElapsedTimer({ startMin }: { startMin: number }) {
  const [elapsed, setElapsed] = useState(startMin);
  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1 / 60), 1000);
    return () => clearInterval(t);
  }, [startMin]);
  const h = Math.floor(elapsed / 60);
  const m = Math.floor(elapsed % 60);
  const s = Math.floor((elapsed * 60) % 60);
  return (
    <span className="font-mono tabular-nums">
      {h > 0 ? `${h}h ` : ''}
      {m}m {String(s).padStart(2, '0')}s
    </span>
  );
}

type DrillScenario = {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed';
  runId?: number;
  actor?: string;
  tactics?: string[];
};

function mapDrillScenario(s: Record<string, unknown>): DrillScenario {
  const rawStatus = (s.status as string) ?? 'pending';
  const status: DrillScenario['status'] =
    rawStatus === 'running' ? 'running' :
    rawStatus === 'completed' ? 'completed' :
    rawStatus === 'failed' ? 'failed' :
    rawStatus === 'paused' ? 'paused' : 'pending';
  const technique = typeof s.technique === 'string' ? s.technique : '';
  const runId: number | undefined = typeof s.runId === 'number' ? s.runId : typeof s.id === 'number' ? s.id : undefined;
  const actor: string | undefined = typeof s.actor === 'string' ? s.actor : undefined;
  const tactics: string[] | undefined = technique ? technique.split('+').map((t: string) => t.trim()) : undefined;
  return {
    id: typeof s.id === 'string' ? s.id : `SIM-${String(runId ?? 0).padStart(3, '0')}`,
    name: typeof s.name === 'string' ? s.name : 'Crisis Response Exercise',
    status,
    ...(runId !== undefined ? { runId } : {}),
    ...(actor !== undefined ? { actor } : {}),
    ...(tactics !== undefined ? { tactics } : {}),
  };
}

const DRILL_STATUS_COLOR: Record<string, string> = {
  running: '#c9b787',
  paused: '#c9b787',
  pending: '#4a6070',
  completed: '#c9b787',
  failed: '#f5f5f5',
};

export default function CitadelWarRoom() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<WarRoomTab>('timeline');
  const [newComm, setNewComm] = useState('');
  const [localComms, setLocalComms] = useState<CommEntry[]>(INIT_COMMS);
  const commEndRef = useRef<HTMLDivElement>(null);
  const [drillActiveId, setDrillActiveId] = useState<string | null>(null);

  const { data: incidentsData, isLoading: incidentsLoading } = useQuery<
    unknown,
    Error,
    Record<string, unknown>[]
  >({
    queryKey: ['war-room-incidents'],
    queryFn: () => api.incidents.list() as Promise<unknown>,
    select: (res: unknown) =>
      (res as { data?: Record<string, unknown>[] } | undefined)?.data ?? [],
  });

  const { data: drillScenarios, isLoading: drillsLoading } = useQuery({
    queryKey: ['war-room-drill-scenarios'],
    queryFn: () => api.digitalTwin.scenarios(),
    refetchInterval: 8000,
    select: (res: { data?: { scenarios?: Record<string, unknown>[] } }) =>
      (res?.data?.scenarios ?? []).map(mapDrillScenario),
  });

  const invalidateDrills = () => queryClient.invalidateQueries({ queryKey: ['war-room-drill-scenarios'] });

  const drillRunMutation = useMutation({
    mutationFn: (id: string) => api.digitalTwin.runScenario(id),
    onMutate: (id) => setDrillActiveId(id),
    onSuccess: (_, id) => {
      const msg: CommEntry = {
        id: `C${Date.now()}`,
        time: new Date().toISOString().slice(11, 16),
        from: 'Drill Control',
        role: 'Exercise Director',
        message: `Drill scenario ${id} STARTED — exercise inject active. All participants respond as trained.`,
        type: 'action',
        priority: 'urgent',
      };
      setLocalComms((prev) => [...prev, msg]);
      invalidateDrills();
    },
    onError: (err: Error) => {
      toast.error(err?.message ?? 'Failed to start drill scenario');
    },
    onSettled: () => setDrillActiveId(null),
  });

  const drillPauseMutation = useMutation({
    mutationFn: (id: string) => api.digitalTwin.pauseScenario(id),
    onMutate: (id) => setDrillActiveId(id),
    onSuccess: (_, id) => {
      const msg: CommEntry = {
        id: `C${Date.now()}`,
        time: new Date().toISOString().slice(11, 16),
        from: 'Drill Control',
        role: 'Exercise Director',
        message: `Drill scenario ${id} PAUSED — exercise inject on hold. Awaiting debrief before continuation.`,
        type: 'update',
      };
      setLocalComms((prev) => [...prev, msg]);
      invalidateDrills();
    },
    onError: (err: Error) => {
      toast.error(err?.message ?? 'Failed to pause drill scenario');
    },
    onSettled: () => setDrillActiveId(null),
  });

  const drillResumeMutation = useMutation({
    mutationFn: (id: string) => api.digitalTwin.resumeScenario(id),
    onMutate: (id) => setDrillActiveId(id),
    onSuccess: (_, id) => {
      const msg: CommEntry = {
        id: `C${Date.now()}`,
        time: new Date().toISOString().slice(11, 16),
        from: 'Drill Control',
        role: 'Exercise Director',
        message: `Drill scenario ${id} RESUMED — continuing exercise inject.`,
        type: 'action',
      };
      setLocalComms((prev) => [...prev, msg]);
      invalidateDrills();
    },
    onError: (err: Error) => {
      toast.error(err?.message ?? 'Failed to resume drill scenario');
    },
    onSettled: () => setDrillActiveId(null),
  });

  const drillBusy = drillRunMutation.isPending || drillPauseMutation.isPending || drillResumeMutation.isPending;

  const activeIncident = (incidentsData ?? []).find(
    (inc: Record<string, unknown>) =>
      inc.status === 'open' || inc.status === 'investigating' || inc.status === 'active',
  ) as Record<string, unknown> | undefined;

  const crisisName = typeof activeIncident?.title === 'string'
    ? activeIncident.title
    : 'APT29 Enterprise Infiltration';
  const incidentId = typeof activeIncident?.id === 'number' || typeof activeIncident?.id === 'string'
    ? String(activeIncident.id)
    : 'INC-2847';

  useEffect(() => {
    commEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localComms]);

  const addNoteMutation = useMutation({
    mutationFn: (note: string) =>
      api.command.addNote(note, typeof activeIncident?.id === 'number' ? activeIncident.id : undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['war-room-incidents'] });
    },
  });

  const sendComm = () => {
    if (!newComm.trim()) return;
    const entry: CommEntry = {
      id: `C${Date.now()}`,
      time: new Date().toISOString().slice(11, 16),
      from: 'You',
      role: 'War Room Operator',
      message: newComm.trim(),
      type: 'update',
    };
    setLocalComms((prev) => [...prev, entry]);
    addNoteMutation.mutate(newComm.trim());
    setNewComm('');
  };

  const elapsedMin = activeIncident?.createdAt
    ? Math.floor((Date.now() - new Date(activeIncident.createdAt as string).getTime()) / 60000)
    : 43;

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: DS.bg, color: DS.text.primary }}
    >
      <div
        className="shrink-0 px-4 py-2.5 border-b flex items-center gap-3"
        style={{ borderColor: 'rgba(245,245,245,0.2)', background: 'rgba(245,245,245,0.04)' }}
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#f5f5f5] animate-pulse" />
          <span className="text-sm font-bold tracking-tight text-[#f5f5f5]">
            CRISIS RESPONSE CENTER
          </span>
          <span
            className="text-[9px] px-2 py-0.5 rounded font-mono uppercase font-bold"
            style={{
              background: 'rgba(245,245,245,0.2)',
              color: '#fca5a5',
              border: '1px solid rgba(245,245,245,0.3)',
            }}
          >
            ICS L3 ACTIVE
          </span>
          <span
            className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded font-mono uppercase border"
            style={{ background: 'rgba(201,183,135,0.08)', borderColor: 'rgba(201,183,135,0.25)', color: '#c9b787' }}
          >
            <Database className="w-2.5 h-2.5" />
            {incidentsLoading ? 'Loading…' : activeIncident ? `Live · ${incidentId}` : 'Scenario'}
          </span>
        </div>
        <div className="h-4 w-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold truncate" style={{ color: DS.text.primary }}>
              {crisisName}
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold shrink-0"
              style={{ background: 'rgba(245,245,245,0.15)', color: '#f5f5f5' }}
            >
              CYBERATTACK
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold shrink-0"
              style={{ background: 'rgba(201,183,135,0.15)', color: '#c9b787' }}
            >
              CONTAINMENT
            </span>
          </div>
          <p className="text-[10px] truncate" style={{ color: DS.text.muted }}>
            Active lateral movement on production infrastructure. 3 managed clients potentially
            affected. Estimated breach exposure $17.4M.
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-4">
          <div className="text-right">
            <div className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
              ELAPSED
            </div>
            <div className="text-[11px] text-[#f5f5f5]">
              <ElapsedTimer startMin={elapsedMin} />
            </div>
          </div>
          <div className="text-right">
            <div className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
              WAR ROOM TIME
            </div>
            <div className="text-[11px]" style={{ color: DS.text.secondary }}>
              <LiveClock className="font-mono tabular-nums" />
            </div>
          </div>
          <div className="text-right">
            <div className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
              COMMANDER
            </div>
            <div className="text-[11px] font-semibold" style={{ color: DS.text.primary }}>
              J. Chen
            </div>
          </div>
        </div>
      </div>

      <div
        className="shrink-0 flex items-center gap-0 px-4 border-b"
        style={{ borderColor: DS.border }}
      >
        {(
          [
            { id: 'timeline', label: 'Crisis Timeline', icon: Activity },
            { id: 'resources', label: 'Resource Board', icon: Users },
            { id: 'decisions', label: 'Decision Log', icon: ClipboardList },
            { id: 'comms', label: 'Comm Feed', icon: Radio },
            { id: 'drill', label: 'Drill Scenarios', icon: Shield },
          ] as { id: WarRoomTab; label: string; icon: typeof Activity }[]
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-[11px] font-semibold transition-all border-b-2"
            style={{
              borderColor: activeTab === id ? '#f5f5f5' : 'transparent',
              color: activeTab === id ? '#f5f5f5' : DS.text.muted,
              background: activeTab === id ? 'rgba(245,245,245,0.04)' : 'transparent',
            }}
          >
            <Icon className="w-3 h-3" />
            {label}
            {id === 'comms' && (
              <span
                className="text-[8px] px-1 py-0.5 rounded-full font-bold"
                style={{ background: 'rgba(245,245,245,0.2)', color: '#f5f5f5' }}
              >
                {localComms.length}
              </span>
            )}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2 py-1.5">
          <a
            href="/citadel-playbooks"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-semibold transition-all"
            style={{
              background: 'rgba(245,245,245,0.08)',
              color: '#f5f5f5',
              border: '1px solid rgba(245,245,245,0.2)',
            }}
          >
            <Zap className="w-3 h-3" />
            Playbooks
          </a>
          <a
            href="/citadel-after-action"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-semibold transition-all"
            style={{
              background: 'rgba(255,255,255,0.05)',
              color: DS.text.secondary,
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <FileText className="w-3 h-3" />
            After-Action
          </a>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === 'timeline' && (
          <div className="h-full overflow-y-auto px-4 py-3">
            <div className="max-w-3xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] font-bold uppercase tracking-wider"
                    style={{ color: DS.text.muted }}
                  >
                    Minute-by-Minute Event Log
                  </span>
                  <span
                    className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                    style={{ background: 'rgba(201,183,135,0.1)', color: '#c9b787' }}
                  >
                    LIVE · {STATIC_TIMELINE.length} events
                  </span>
                </div>
                <div className="flex gap-2">
                  {(['critical', 'high', 'medium', 'info'] as const).map((s) => (
                    <div key={s} className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: SEV[s] }} />
                      <span
                        className="text-[8px] capitalize font-mono"
                        style={{ color: DS.text.muted }}
                      >
                        {s}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-0">
                {STATIC_TIMELINE.map((event, idx) => (
                  <div key={event.id} className="flex gap-3 group">
                    <div className="flex flex-col items-center">
                      <div
                        className="w-2 h-2 rounded-full mt-2 shrink-0"
                        style={{
                          background: SEV[event.severity],
                          boxShadow:
                            event.severity === 'critical'
                              ? `0 0 8px ${SEV[event.severity]}50`
                              : 'none',
                        }}
                      />
                      {idx < STATIC_TIMELINE.length - 1 && (
                        <div
                          className="w-px flex-1 mt-1"
                          style={{ background: 'rgba(255,255,255,0.06)' }}
                        />
                      )}
                    </div>
                    <div className="pb-4 flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span
                          className="text-[10px] font-mono font-bold"
                          style={{ color: DS.text.muted }}
                        >
                          {event.time}
                        </span>
                        <span
                          className="text-[9px] font-mono"
                          style={{ color: 'rgba(255,255,255,0.2)' }}
                        >
                          {event.elapsed}
                        </span>
                        {!event.confirmed && (
                          <span
                            className="text-[8px] px-1 py-0.5 rounded font-bold"
                            style={{ background: 'rgba(201,183,135,0.1)', color: '#c9b787' }}
                          >
                            UNCONFIRMED
                          </span>
                        )}
                      </div>
                      <div
                        className="text-[12px] font-semibold mb-1"
                        style={{ color: DS.text.primary }}
                      >
                        {event.title}
                      </div>
                      <div className="text-[11px] mb-1.5" style={{ color: DS.text.secondary }}>
                        {event.detail}
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className="text-[9px] px-1.5 py-0.5 rounded font-mono"
                          style={{
                            background: `${SEV[event.severity]}12`,
                            color: SEV[event.severity],
                            border: `1px solid ${SEV[event.severity]}30`,
                          }}
                        >
                          {event.severity.toUpperCase()}
                        </span>
                        <span className="text-[9px]" style={{ color: DS.text.muted }}>
                          {event.source}
                        </span>
                        {event.actor && (
                          <span
                            className="text-[9px] font-mono"
                            style={{ color: 'rgba(138,138,138,0.8)' }}
                          >
                            {event.actor}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'resources' && (
          <div className="h-full overflow-y-auto px-4 py-3">
            <div className="max-w-3xl space-y-2">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: DS.text.muted }}>
                  Assigned Personnel
                </span>
                <div className="flex items-center gap-3 text-[9px]">
                  {(['active', 'standby', 'unavailable'] as const).map((s) => (
                    <div key={s} className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_COLORS[s] }} />
                      <span style={{ color: DS.text.muted }}>{s}</span>
                    </div>
                  ))}
                </div>
              </div>
              {RESOURCES.map((r) => (
                <div
                  key={r.id}
                  className="rounded-lg p-3 flex items-start gap-3"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <div
                    className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                    style={{ background: STATUS_COLORS[r.status] }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-[11px] font-semibold" style={{ color: DS.text.primary }}>
                          {r.name}
                        </div>
                        <div className="text-[10px]" style={{ color: DS.text.muted }}>{r.role} · {r.domain}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {r.eta && (
                          <span className="text-[9px] font-mono" style={{ color: DS.text.muted }}>ETA {r.eta}</span>
                        )}
                        <span
                          className="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase"
                          style={{ background: `${STATUS_COLORS[r.status]}15`, color: STATUS_COLORS[r.status] }}
                        >
                          {r.status}
                        </span>
                      </div>
                    </div>
                    <div className="text-[10px] mt-1" style={{ color: DS.text.secondary }}>{r.task}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'decisions' && (
          <div className="h-full overflow-y-auto px-4 py-3">
            <div className="max-w-3xl space-y-3">
              <span className="text-[10px] font-bold uppercase tracking-wider block mb-3" style={{ color: DS.text.muted }}>
                Commander Decision Log
              </span>
              {DECISIONS.map((d) => (
                <div
                  key={d.id}
                  className="rounded-lg p-4"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="text-[12px] font-semibold" style={{ color: DS.text.primary }}>{d.title}</div>
                      <div className="text-[9px] font-mono" style={{ color: DS.text.muted }}>{d.time} · {d.decidedBy}</div>
                    </div>
                    <span
                      className="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase shrink-0"
                      style={{ background: `${DECISION_COLORS[d.status]}15`, color: DECISION_COLORS[d.status] }}
                    >
                      {d.status}
                    </span>
                  </div>
                  <div className="text-[11px] mb-2" style={{ color: DS.text.secondary }}>{d.rationale}</div>
                  <div
                    className="text-[10px] rounded px-2 py-1.5"
                    style={{ background: 'rgba(255,255,255,0.03)', color: DS.text.muted }}
                  >
                    <span className="font-bold">Outcome:</span> {d.outcome}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'comms' && (
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
              {localComms.map((comm) => (
                <div
                  key={comm.id}
                  className="rounded-lg p-3"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: COMM_COLORS[comm.type] }}
                    />
                    <span className="text-[11px] font-semibold" style={{ color: DS.text.primary }}>
                      {comm.from}
                    </span>
                    <span className="text-[9px]" style={{ color: DS.text.muted }}>{comm.role}</span>
                    <span className="text-[9px] font-mono ml-auto" style={{ color: DS.text.muted }}>{comm.time}</span>
                    {comm.priority === 'urgent' && (
                      <span className="text-[8px] px-1 py-0.5 rounded font-bold" style={{ background: 'rgba(245,245,245,0.2)', color: '#f5f5f5' }}>
                        URGENT
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] leading-relaxed" style={{ color: DS.text.secondary }}>
                    {comm.message}
                  </div>
                </div>
              ))}
              <div ref={commEndRef} />
            </div>
            <div
              className="shrink-0 p-3 border-t"
              style={{ borderColor: DS.border }}
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newComm}
                  onChange={(e) => setNewComm(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendComm(); } }}
                  placeholder="Send comm to war room…"
                  className="flex-1 rounded-lg px-3 py-2 text-[11px] outline-none"
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: `1px solid ${DS.border}`,
                    color: DS.text.primary,
                  }}
                  aria-label="Type war room communication"
                />
                <button
                  type="button"
                  onClick={sendComm}
                  className="px-3 py-2 rounded-lg text-[11px] font-semibold transition-colors"
                  style={{
                    background: 'rgba(245,245,245,0.15)',
                    color: '#f5f5f5',
                    border: '1px solid rgba(245,245,245,0.25)',
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'drill' && (
          <div className="h-full overflow-y-auto px-4 py-3">
            <div className="max-w-3xl space-y-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span
                    className="text-[10px] font-bold uppercase tracking-wider block"
                    style={{ color: DS.text.muted }}
                  >
                    Crisis Response Drill Scenarios
                  </span>
                  <p className="text-[10px] mt-0.5" style={{ color: DS.text.muted }}>
                    Start, pause, or resume tabletop exercises. Lifecycle events auto-log to Comm Feed.
                  </p>
                </div>
                <span
                  className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded font-mono uppercase border"
                  style={{ background: 'rgba(201,183,135,0.08)', borderColor: 'rgba(201,183,135,0.25)', color: '#c9b787' }}
                >
                  <Database className="w-2.5 h-2.5" />
                  {drillsLoading ? 'Loading…' : `${(drillScenarios ?? []).length} scenarios`}
                </span>
              </div>

              {drillsLoading && (
                <div className="flex items-center gap-2 text-xs py-4" style={{ color: DS.text.muted }}>
                  <div className="w-3.5 h-3.5 border-2 border-[#f5f5f5]/40 border-t-red-400 rounded-full animate-spin" />
                  Loading drill scenarios from PARAGON…
                </div>
              )}

              {(!drillScenarios || drillScenarios.length === 0) && !drillsLoading && (
                <div
                  className="rounded-xl p-4 text-center"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <p className="text-[11px]" style={{ color: DS.text.muted }}>
                    No drill scenarios found. Create scenarios in the Adversary Engine to run them here.
                  </p>
                </div>
              )}

              {(drillScenarios ?? []).map((scenario) => {
                const busy = drillBusy && drillActiveId === scenario.id;
                const sc = DRILL_STATUS_COLOR[scenario.status] ?? '#4a6070';
                return (
                  <div
                    key={scenario.id}
                    className="rounded-lg p-4"
                    style={{
                      background:
                        scenario.status === 'running'
                          ? 'rgba(201,183,135,0.04)'
                          : scenario.status === 'paused'
                            ? 'rgba(201,183,135,0.04)'
                            : DS.surface,
                      border: `1px solid ${scenario.status === 'running' ? 'rgba(201,183,135,0.2)' : scenario.status === 'paused' ? 'rgba(201,183,135,0.2)' : DS.border}`,
                    }}
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span
                            className="text-[12px] font-semibold truncate"
                            style={{ color: DS.text.primary }}
                          >
                            {scenario.name}
                          </span>
                          {scenario.status === 'running' && (
                            <span
                              className="w-1.5 h-1.5 rounded-full animate-pulse shrink-0"
                              style={{ background: sc }}
                            />
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[9px] font-mono">
                          <span style={{ color: DS.text.muted }}>{scenario.id}</span>
                          {scenario.actor && (
                            <>
                              <span style={{ color: DS.text.muted }}>·</span>
                              <span style={{ color: sc }}>{scenario.actor}</span>
                            </>
                          )}
                        </div>
                        {scenario.tactics && scenario.tactics.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {scenario.tactics.slice(0, 4).map((t) => (
                              <span
                                key={t}
                                className="text-[9px] px-1 py-0.5 rounded"
                                style={{
                                  background: 'rgba(255,255,255,0.05)',
                                  border: `1px solid ${DS.border}`,
                                  color: DS.text.muted,
                                }}
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <span
                        className="text-[9px] px-2 py-0.5 rounded font-mono uppercase shrink-0"
                        style={{ background: `${sc}15`, color: sc, border: `1px solid ${sc}30` }}
                      >
                        {scenario.status}
                      </span>
                    </div>

                    {/* Lifecycle controls */}
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t" style={{ borderColor: DS.border }}>
                      {(scenario.status === 'pending') && (
                        <button
                          type="button"
                          onClick={() => drillRunMutation.mutate(scenario.id)}
                          disabled={busy || drillBusy}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-semibold transition-colors disabled:opacity-50"
                          style={{
                            background: 'rgba(201,183,135,0.1)',
                            color: '#c9b787',
                            border: '1px solid rgba(201,183,135,0.25)',
                          }}
                          aria-label={`Start drill ${scenario.id}`}
                        >
                          {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                          Start Exercise
                        </button>
                      )}
                      {scenario.status === 'running' && (
                        <button
                          type="button"
                          onClick={() => drillPauseMutation.mutate(scenario.id)}
                          disabled={busy || drillBusy}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-semibold transition-colors disabled:opacity-50"
                          style={{
                            background: 'rgba(201,183,135,0.1)',
                            color: '#c9b787',
                            border: '1px solid rgba(201,183,135,0.25)',
                          }}
                          aria-label={`Pause drill ${scenario.id}`}
                        >
                          {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Pause className="w-3 h-3" />}
                          Pause for Debrief
                        </button>
                      )}
                      {scenario.status === 'paused' && (
                        <button
                          type="button"
                          onClick={() => drillResumeMutation.mutate(scenario.id)}
                          disabled={busy || drillBusy}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-semibold transition-colors disabled:opacity-50"
                          style={{
                            background: 'rgba(201,183,135,0.1)',
                            color: '#c9b787',
                            border: '1px solid rgba(201,183,135,0.25)',
                          }}
                          aria-label={`Resume drill ${scenario.id}`}
                        >
                          {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                          Resume Exercise
                        </button>
                      )}
                      {scenario.status === 'completed' && (
                        <span className="text-[10px]" style={{ color: '#c9b787' }}>
                          ✓ Exercise complete — review after-action report
                        </span>
                      )}
                      {scenario.status === 'failed' && (
                        <span className="text-[10px]" style={{ color: '#f5f5f5' }}>
                          Exercise ended with errors — check scenario log
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
