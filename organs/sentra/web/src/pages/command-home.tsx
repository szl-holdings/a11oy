import { useStandardQuery } from '@szl-holdings/api-client-react';
import { LiveClock } from '@szl-holdings/shared-ui/live-clock';
import { type ActivationStep, ActivationBanner, HelpTip, useActivationState, useOnboardingAnalytics } from '@szl-holdings/shared-ui/onboarding';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertOctagon,
  BarChart3,
  ChevronRight,
  ClipboardCheck,
  Hexagon,
  Lock,
  Minus,
  Radio,
  Shield,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  UserCheck,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, } from 'react';
import { Link, useLocation } from 'wouter';
import { api } from '@/lib/api';

const BASE = import.meta.env.BASE_URL?.replace(/\/$/, '') ?? '';

const DS = {
  page: '#0a0a0a',
  surface: 'rgba(255,255,255,0.025)',
  elevated: 'rgba(255,255,255,0.035)',
  border: 'rgba(255,255,255,0.05)',
  borderMuted: 'rgba(255,255,255,0.04)',
  text: {
    primary: 'rgba(255,255,255,0.9)',
    secondary: 'rgba(255,255,255,0.5)',
    tertiary: 'rgba(255,255,255,0.28)',
    muted: 'rgba(255,255,255,0.14)',
  },
};

interface AegisIncident {
  id: number;
  title: string;
  severity: string;
  status: string;
  createdAt: string;
  updatedAt?: string;
  assignedAnalyst?: string | null;
  detectedAt?: string | Date;
}

interface AegisAlert {
  id: number;
  title: string;
  severity: string;
  status: string;
  createdAt: string;
}

interface LiveWorkflowAction {
  id: number;
  entityType: string;
  entityId: number;
  actionType: string;
  assignedTo?: string | null;
  status: string;
  notes?: string | null;
  triggeredBy?: string | null;
  createdAt: string;
}

interface LiveFinding {
  id: number;
  title: string;
  severity: string;
  status: string;
  remediationOwner?: string | null;
  createdAt: string;
}

function PulsingDot({ color = '#f5f5f5' }: { color?: string }) {
  return (
    <span className="relative flex w-2 h-2 shrink-0">
      <span
        className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
        style={{ backgroundColor: color }}
      />
      <span
        className="relative inline-flex rounded-full w-2 h-2"
        style={{ backgroundColor: color }}
      />
    </span>
  );
}

const SEV_COLORS: Record<
  string,
  { bg: string; text: string; border: string; dot: string; accent: string }
> = {
  critical: {
    bg: 'bg-[#f5f5f5]/10',
    text: 'text-[#f5f5f5]',
    border: 'border-[#f5f5f5]/25',
    dot: '#f5f5f5',
    accent: '#f5f5f5',
  },
  high: {
    bg: 'bg-[#c9b787]/10',
    text: 'text-[#c9b787]',
    border: 'border-[#c9b787]/25',
    dot: '#c9b787',
    accent: '#c9b787',
  },
  medium: {
    bg: 'bg-[#c9b787]/10',
    text: 'text-[#c9b787]',
    border: 'border-[#c9b787]/25',
    dot: '#8a8a8a',
    accent: '#8a8a8a',
  },
  low: {
    bg: 'bg-[#c9b787]/10',
    text: 'text-[#c9b787]',
    border: 'border-[#c9b787]/25',
    dot: '#c9b787',
    accent: '#c9b787',
  },
};

const STATUS_COLORS: Record<string, string> = {
  detection: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
  triage: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  investigation: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  containment: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  remediation: 'bg-[#8a8a8a]/10 text-[#8a8a8a] border-[#8a8a8a]/20',
  closed: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  open: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  in_progress: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  resolved: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
};

const FALLBACK_POSTURE = {
  controlsImplemented: 84,
  controlsTotal: 120,
  mttd: '18m',
  mttr: '4h 12m',
  slaBreaches: 2,
};

const FALLBACK_APPROVAL_QUEUE = [
  {
    id: 'APR-001',
    action: 'Isolate endpoint DC-PROD-03',
    type: 'containment',
    requestedBy: 'J. Chen',
    requestedAt: '12m ago',
    severity: 'critical',
    gate: 'approval_required',
  },
  {
    id: 'APR-002',
    action: 'Block outbound to 103.45.18.x',
    type: 'network_block',
    requestedBy: 'S. Park',
    requestedAt: '28m ago',
    severity: 'high',
    gate: 'approval_required',
  },
  {
    id: 'APR-003',
    action: 'Revoke OAuth tokens — svc-integration',
    type: 'iam_action',
    requestedBy: 'M. Rodriguez',
    requestedAt: '1h 4m ago',
    severity: 'high',
    gate: 'approval_required',
  },
];

const FALLBACK_DECISIONS = [
  {
    id: 'DEC-041',
    title: 'Lateral movement confirmed — APT29 TTP overlap',
    analyst: 'J. Chen',
    confidence: 88,
    at: '34m ago',
    outcome: 'escalated',
  },
  {
    id: 'DEC-040',
    title: 'Brute force — automated bot, not targeted',
    analyst: 'L. Kim',
    confidence: 95,
    at: '2h ago',
    outcome: 'closed',
  },
  {
    id: 'DEC-039',
    title: 'S3 exfil pattern — misconfig, not threat actor',
    analyst: 'S. Park',
    confidence: 71,
    at: '3h ago',
    outcome: 'remediation',
  },
];

const ACTION_TYPE_LABELS: Record<string, string> = {
  assign_owner: 'Assign Owner',
  escalate: 'Escalate',
  acknowledge: 'Acknowledge',
  remediate: 'Remediate',
  route_to_response: 'Route to Response',
  create_ticket: 'Create Ticket',
  notify: 'Notify',
};

function formatTimeAgo(dateStr: string): string {
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function MetricCard({
  label,
  value,
  sub,
  trend,
  color = '#c9b787',
}: {
  label: string;
  value: string;
  sub?: string;
  trend?: 'up' | 'down' | 'stable';
  color?: string;
}) {
  return (
    <div
      style={{
        background: DS.surface,
        border: `1px solid ${DS.border}`,
        borderRadius: '12px',
        padding: '1rem',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg, ${color}60, transparent)`,
        }}
      />
      <div
        className="text-[10px] font-mono uppercase tracking-[0.15em] mb-2"
        style={{ color: DS.text.tertiary }}
      >
        {label}
      </div>
      <div className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>
        {value}
      </div>
      {sub && (
        <div className="text-[10px] mt-1" style={{ color: DS.text.tertiary }}>
          {sub}
        </div>
      )}
      {trend && (
        <div className="mt-2 flex items-center gap-1">
          {trend === 'up' && <TrendingUp className="w-3 h-3 text-[#f5f5f5]" />}
          {trend === 'down' && <TrendingDown className="w-3 h-3 text-[#c9b787]" />}
          {trend === 'stable' && <Minus className="w-3 h-3 text-[#c9b787]" />}
          <span className="text-[10px]" style={{ color: DS.text.muted }}>
            30d trend
          </span>
        </div>
      )}
    </div>
  );
}

function PostureRing({ score }: { score: number }) {
  const r = 36;
  const c = 2 * Math.PI * r;
  const filled = (score / 100) * c;
  const color = score >= 80 ? '#c9b787' : score >= 60 ? '#c9b787' : '#f5f5f5';
  return (
    <div className="relative w-24 h-24 flex items-center justify-center">
      <svg width="96" height="96" className="rotate-[-90deg]">
        <circle cx="48" cy="48" r={r} strokeWidth="6" stroke="rgba(255,255,255,0.07)" fill="none" />
        <circle
          cx="48"
          cy="48"
          r={r}
          strokeWidth="6"
          stroke={color}
          fill="none"
          strokeDasharray={`${filled} ${c - filled}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>
          {score}
        </span>
        <span
          className="text-[8px] font-mono uppercase tracking-widest"
          style={{ color: DS.text.muted }}
        >
          posture
        </span>
      </div>
    </div>
  );
}

interface PostureSummary {
  riskScore: number | null;
  riskLevel: string;
  openIncidents: number;
  criticalAlerts: number;
  unresolvedFindings: number;
  totalAlerts: number;
  ztEnvironment?: string;
  ztPermissionClass?: string;
  ztDataLabels?: { sensitivityLabel: string; retentionClass: string; exportRestricted: boolean };
  fetchedAt: string;
  controlsImplemented?: number;
  controlsTotal?: number;
  mttd?: string;
  mttr?: string;
  slaBreaches?: number;
}

interface DecisionsPayload {
  decisions: LiveFinding[];
  pendingCount?: number;
  ztDataLabels?: { sensitivityLabel: string; retentionClass: string };
  fetchedAt: string;
}

interface PlaybooksPayload {
  playbooks: LiveWorkflowAction[];
  total?: number;
  ztDataLabels?: { sensitivityLabel: string; retentionClass: string };
  fetchedAt: string;
}

export default function CommandHome() {
  const { data: posture } = useStandardQuery<PostureSummary>({
    queryKey: ['command-posture'],
    queryFn: () => api.command.posture(),
    retry: false,
  });
  const { data: incidents = [] } = useStandardQuery<AegisIncident[]>({
    queryKey: ['aegis-incidents'],
    queryFn: () => api.incidents.list(),
  });
  const { data: alerts = [] } = useStandardQuery<AegisAlert[]>({
    queryKey: ['aegis-alerts'],
    queryFn: () => api.alerts.list(),
  });
  const { data: decisionsData, isSuccess: decisionsLoaded } = useStandardQuery<DecisionsPayload>({
    queryKey: ['command-decisions'],
    queryFn: () => api.command.decisions(),
    retry: false,
  });
  const { data: playbooksData, isSuccess: playbooksLoaded } = useStandardQuery<PlaybooksPayload>({
    queryKey: ['command-playbooks'],
    queryFn: () => api.command.playbooks(),
    retry: false,
  });
  const [, navigate] = useLocation();

  const activation = useActivationState({ apiBaseUrl: `${BASE}/api`, pollIntervalMs: 60_000 });
  const { trackChecklistItemCompleted, trackChecklistDismissed, trackTourCompleted } =
    useOnboardingAnalytics({
      platform: 'aegis',
      tourId: 'aegis-activation',
    });

  const handleNavigate = useCallback(
    (href: string) => {
      const base = BASE.replace(/\/$/, '');
      navigate(href.startsWith(base) ? href.slice(base.length) || '/' : href);
    },
    [navigate],
  );

  const TOUR_COMPLETED_KEY = 'szl_aegis_activation_tour_completed';
  const trackedAllCompleteRef = useRef(false);
  useEffect(() => {
    if (activation.isLoading) return;
    if (trackedAllCompleteRef.current) return;
    try {
      if (localStorage.getItem(TOUR_COMPLETED_KEY) === 'true') {
        trackedAllCompleteRef.current = true;
        return;
      }
    } catch {}
    if (
      activation.signalSourceConnected &&
      activation.workflowDeployed &&
      activation.actionTriaged &&
      activation.teamMemberInvited
    ) {
      trackedAllCompleteRef.current = true;
      try {
        localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
      } catch {}
      trackTourCompleted();
    }
  }, [
    activation.isLoading,
    activation.signalSourceConnected,
    activation.workflowDeployed,
    activation.actionTriaged,
    activation.teamMemberInvited,
    trackTourCompleted,
  ]);

  const activationSteps: ActivationStep[] = [
    {
      id: 'connect-feeds',
      label: 'Connect a threat feed',
      description: 'Link SIEM, EDR, or threat intelligence sources to PARAGON',
      completed: activation.signalSourceConnected,
      href: `${BASE}/settings/integrations`,
    },
    {
      id: 'deploy-playbook',
      label: 'Deploy an incident playbook',
      description: 'Activate automated response workflows for your threat landscape',
      completed: activation.workflowDeployed,
      href: `${BASE}/soc`,
    },
    {
      id: 'review-decision',
      label: 'Review a security decision',
      description: 'Approve or reject a pending action in the decision console',
      completed: activation.actionTriaged,
      href: `${BASE}/decision-console`,
    },
    {
      id: 'invite-analyst',
      label: 'Invite a security analyst',
      description: 'Add team members to collaborate on incident response',
      completed: activation.teamMemberInvited,
      href: `${BASE}/settings/team`,
    },
  ];

  const activeIncidents = incidents.filter((i) => i.status !== 'closed');
  const criticalIncidents = activeIncidents.filter((i) => i.severity === 'critical');
  const newAlerts = alerts.filter((a) => a.status === 'new');

  const postureScore = posture?.riskScore != null ? Math.round(posture.riskScore) : 72;
  const liveOpenIncidents = posture?.openIncidents ?? activeIncidents.length;
  const liveCriticalAlerts = posture?.criticalAlerts ?? criticalIncidents.length;
  const unresolvedFindings = posture?.unresolvedFindings ?? 0;

  const envLabel = posture?.ztEnvironment ?? 'PRODUCTION';
  const tenantLabel = posture?.ztPermissionClass
    ? `CLASS:${posture.ztPermissionClass.toUpperCase()}`
    : 'ORG-DEFAULT';
  const sessionClass = posture ? 'VERIFIED' : 'UNVERIFIED';

  const pendingActions = useMemo(() => {
    if (!playbooksLoaded) return null;
    const actions = playbooksData?.playbooks ?? [];
    return actions
      .filter((a) => a.status === 'pending')
      .map((a) => ({
        id: `ACT-${a.id}`,
        action: `${ACTION_TYPE_LABELS[a.actionType] ?? a.actionType} — ${a.entityType} #${a.entityId}`,
        type: a.actionType,
        requestedBy: a.triggeredBy ?? 'System',
        requestedAt: formatTimeAgo(a.createdAt),
        severity: a.actionType === 'escalate' || a.actionType === 'remediate' ? 'critical' : 'high',
        gate: 'approval_required',
      }));
  }, [playbooksData, playbooksLoaded]);

  const recentDecisions = useMemo(() => {
    if (!decisionsLoaded) return null;
    return (decisionsData?.decisions ?? []).slice(0, 5).map((d) => ({
      id: `FIND-${d.id}`,
      title: d.title,
      analyst: d.remediationOwner ?? 'Analyst',
      confidence: 0,
      at: formatTimeAgo(d.createdAt),
      outcome: d.status,
    }));
  }, [decisionsData, decisionsLoaded]);

  const approvalQueue = pendingActions ?? FALLBACK_APPROVAL_QUEUE;
  const displayDecisions = recentDecisions ?? FALLBACK_DECISIONS;
  const usingLive = posture != null;

  return (
    <div
      className="flex flex-col h-full min-h-screen"
      style={{ backgroundColor: DS.page, color: 'var(--gi-text-primary)' }}
    >
      {/* Topbar */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b relative overflow-hidden"
        style={{ borderColor: DS.border }}
      >
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '1px',
            background: `linear-gradient(90deg, ${postureScore >= 80 ? '#c9b787' : postureScore >= 60 ? '#c9b787' : '#f5f5f5'}40, transparent 60%)`,
          }}
        />
        <div className="flex items-center gap-3">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg,rgba(201,183,135,0.25),rgba(138,138,138,0.18))',
              border: '1px solid rgba(201,183,135,0.2)',
            }}
          >
            <Hexagon className="w-3.5 h-3.5 text-[#c9b787]" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
              Command Home
              <HelpTip
                tipId="aegis.command-home.posture"
                platform="aegis"
                title="Command Home"
                content="Single-pane operational view of cyber posture: live risk score, open incidents, critical alerts, and the approval queue. Every tile links to a deeper drill-down with the underlying evidence."
                accentColor="#c9b787"
                iconSize={11}
              />
            </h1>
            <p
              className="text-[9px] font-mono uppercase tracking-[0.15em]"
              style={{ color: DS.text.muted }}
            >
              PARAGON Cyber-Resilience Platform
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/30 text-[#c9b787]/80 bg-[#c9b787]/5">
              {envLabel}
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/30 text-[#c9b787]/80 bg-[#c9b787]/5">
              {tenantLabel}
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#8a8a8a]/30 text-[#8a8a8a]/80 bg-[#8a8a8a]/5">
              <Lock className="w-2.5 h-2.5 inline mr-0.5" />
              {sessionClass}
            </span>
            {usingLive && (
              <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70">
                LIVE
              </span>
            )}
          </div>
          <LiveClock
            className="font-mono tabular-nums text-[10px]"
            style={{ color: DS.text.muted }}
          />
        </div>
      </div>

      {/* Activation banner */}
      {!activation.isLoading && (
        <div style={{ padding: '0.5rem 1.5rem', borderBottom: `1px solid ${DS.border}` }}>
          <ActivationBanner
            steps={activationSteps.map((s) => ({
              ...s,
              action: () => {
                s.action?.();
                trackChecklistItemCompleted(s.id);
              },
            }))}
            accentColor="#c9b787"
            storageKey="aegis_activation_banner"
            variant="banner"
            onNavigate={handleNavigate}
            onDismiss={trackChecklistDismissed}
          />
        </div>
      )}

      {/* Threat level strip */}
      <div
        style={{
          padding: '0.5rem 1.5rem',
          borderBottom: `1px solid ${DS.border}`,
          display: 'flex',
          alignItems: 'center',
          gap: '1.5rem',
          overflow: 'hidden',
          background: 'rgba(0,0,0,0.3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
          <Radio className="w-3 h-3 text-[#f5f5f5] animate-pulse" />
          <span
            className="text-[9px] font-mono uppercase tracking-[0.15em]"
            style={{ color: DS.text.tertiary }}
          >
            Threat Feed
          </span>
        </div>
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          <div
            style={{
              display: 'flex',
              gap: '3rem',
              animation: 'scroll-left 30s linear infinite',
              whiteSpace: 'nowrap',
            }}
          >
            {[
              {
                tag: 'CRITICAL',
                msg: 'APT29 lateral movement — DC-PROD-03 quarantine pending',
                color: '#f5f5f5',
              },
              {
                tag: 'HIGH',
                msg: 'Outbound C2 beacon detected — blocked at perimeter',
                color: '#c9b787',
              },
              {
                tag: 'HIGH',
                msg: 'S3 exfil pattern — 3 buckets flagged for review',
                color: '#c9b787',
              },
              {
                tag: 'MEDIUM',
                msg: 'Brute force campaign — 847 attempts in 2h window',
                color: '#8a8a8a',
              },
              {
                tag: 'INFO',
                msg: 'Threat intel updated — 14 new IOCs added to block list',
                color: '#c9b787',
              },
            ].map((item, i) => (
              <span key={i} style={{ fontSize: '10px', color: DS.text.secondary, flexShrink: 0 }}>
                <span
                  style={{
                    color: item.color,
                    fontWeight: 700,
                    marginRight: '6px',
                    fontFamily: 'monospace',
                  }}
                >
                  [{item.tag}]
                </span>
                {item.msg}
              </span>
            ))}
          </div>
        </div>
        <style>{`@keyframes scroll-left { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }`}</style>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {/* Row 1: Posture + 4 KPI cards */}
        <div className="grid grid-cols-12 gap-4">
          {/* Posture panel */}
          <div
            className="col-span-12 lg:col-span-3"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              padding: '1.25rem',
            }}
          >
            <div
              style={{
                height: 2,
                background: `linear-gradient(90deg, ${postureScore >= 80 ? '#c9b787' : postureScore >= 60 ? '#c9b787' : '#f5f5f5'}, transparent)`,
                margin: '-1.25rem -1.25rem 1rem',
                borderRadius: '12px 12px 0 0',
              }}
            />
            <div className="flex items-center justify-between mb-4">
              <span
                className="text-[9px] font-mono uppercase tracking-[0.15em]"
                style={{ color: DS.text.tertiary }}
              >
                System Posture
              </span>
              <ShieldCheck className="w-3.5 h-3.5" style={{ color: DS.text.muted }} />
            </div>
            <div className="flex flex-col items-center gap-3">
              <PostureRing score={postureScore} />
              <div className="w-full space-y-2">
                {((): Array<{ label: string; value: string; color: string }> => {
                  const ctrlImpl =
                    posture?.controlsImplemented ?? FALLBACK_POSTURE.controlsImplemented;
                  const ctrlTotal = posture?.controlsTotal ?? FALLBACK_POSTURE.controlsTotal;
                  const mttd = posture?.mttd ?? FALLBACK_POSTURE.mttd;
                  const mttr = posture?.mttr ?? FALLBACK_POSTURE.mttr;
                  const slaB = posture?.slaBreaches ?? FALLBACK_POSTURE.slaBreaches;
                  return [
                    {
                      label: 'Controls Active',
                      value: `${ctrlImpl}/${ctrlTotal}`,
                      color: '#c9b787',
                    },
                    { label: 'MTTD', value: mttd, color: '#c9b787' },
                    { label: 'MTTR', value: mttr, color: '#c9b787' },
                    {
                      label: 'SLA Breaches',
                      value: String(slaB),
                      color: slaB > 0 ? '#f5f5f5' : '#c9b787',
                    },
                  ];
                })().map((row) => (
                  <div
                    key={row.label}
                    className="flex justify-between text-[10px]"
                    style={{
                      borderBottom: `1px solid ${DS.borderMuted}`,
                      paddingBottom: '0.375rem',
                    }}
                  >
                    <span style={{ color: DS.text.secondary }}>{row.label}</span>
                    <span className="font-mono font-bold" style={{ color: row.color }}>
                      {row.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 4 KPI metric cards */}
          <div className="col-span-12 lg:col-span-9 grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Active Incidents"
              value={String(liveOpenIncidents || activeIncidents.length)}
              sub={`${liveCriticalAlerts || criticalIncidents.length} critical`}
              trend="down"
              color="#f5f5f5"
            />
            <MetricCard
              label="Priority Alerts"
              value={String(posture?.totalAlerts ?? newAlerts.length)}
              sub={`${liveCriticalAlerts} critical`}
              trend="up"
              color="#c9b787"
            />
            <MetricCard
              label="Pending Approvals"
              value={String(approvalQueue.length)}
              sub="require action"
              trend="stable"
              color="#c9b787"
            />
            <MetricCard
              label="Unresolved Findings"
              value={String(unresolvedFindings || 0)}
              sub={unresolvedFindings > 0 ? 'open/confirmed' : '—'}
              trend="stable"
              color="#8a8a8a"
            />
          </div>
        </div>

        {/* Row 2: Incidents + Approval Queue + Findings count */}
        <div className="grid grid-cols-12 gap-4">
          {/* Active Incidents */}
          <div
            className="col-span-12 lg:col-span-5"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{ height: 2, background: 'linear-gradient(90deg, #f5f5f5, transparent)' }}
            />
            <div
              className="px-4 py-3 border-b flex items-center justify-between"
              style={{ borderColor: DS.borderMuted }}
            >
              <div className="flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-[#f5f5f5]" />
                <span className="text-xs font-semibold text-white">Active Incidents</span>
                {(activeIncidents.length > 0 || liveOpenIncidents > 0) && (
                  <PulsingDot color="#f5f5f5" />
                )}
              </div>
              <Link href="/incidents">
                <span className="text-[10px] text-[#c9b787]/60 hover:text-[#c9b787] cursor-pointer flex items-center gap-1">
                  All <ChevronRight className="w-3 h-3" />
                </span>
              </Link>
            </div>
            <div className="divide-y" style={{ borderColor: DS.borderMuted }}>
              {(activeIncidents.length > 0
                ? activeIncidents.slice(0, 5)
                : ((): AegisIncident[] => [
                    {
                      id: 1,
                      title: 'Lateral Movement — DC-PROD-03',
                      severity: 'critical',
                      status: 'investigation',
                      createdAt: new Date(Date.now() - 1200000).toISOString(),
                      assignedAnalyst: 'J. Chen',
                      detectedAt: new Date(Date.now() - 1200000),
                    },
                    {
                      id: 2,
                      title: 'C2 Beacon — APT29 Infrastructure',
                      severity: 'critical',
                      status: 'triage',
                      createdAt: new Date(Date.now() - 3600000).toISOString(),
                      assignedAnalyst: 'S. Park',
                      detectedAt: new Date(Date.now() - 3600000),
                    },
                    {
                      id: 3,
                      title: 'Data Exfil Pattern — S3 Bucket',
                      severity: 'high',
                      status: 'investigation',
                      createdAt: new Date(Date.now() - 7200000).toISOString(),
                      assignedAnalyst: 'M. Rodriguez',
                      detectedAt: new Date(Date.now() - 7200000),
                    },
                    {
                      id: 4,
                      title: 'Brute Force — Admin Portal',
                      severity: 'high',
                      status: 'containment',
                      createdAt: new Date(Date.now() - 10800000).toISOString(),
                      assignedAnalyst: null,
                      detectedAt: new Date(Date.now() - 10800000),
                    },
                    {
                      id: 5,
                      title: 'Unauth Access — Config Mgmt',
                      severity: 'medium',
                      status: 'triage',
                      createdAt: new Date(Date.now() - 18000000).toISOString(),
                      assignedAnalyst: 'L. Kim',
                      detectedAt: new Date(Date.now() - 18000000),
                    },
                  ])()
              ).map((inc: AegisIncident) => {
                const sev = SEV_COLORS[inc.severity] ?? SEV_COLORS.medium;
                const age = Math.round(
                  (Date.now() - new Date(inc.detectedAt ?? inc.createdAt).getTime()) / 60000,
                );
                const ageStr = age < 60 ? `${age}m` : `${Math.round(age / 60)}h`;
                return (
                  <Link key={inc.id} href="/incidents">
                    <div className="px-4 py-3 hover:bg-white/[0.02] cursor-pointer transition-colors">
                      <div className="flex items-start gap-3">
                        <div
                          className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                          style={{
                            backgroundColor: sev.dot,
                            boxShadow:
                              inc.severity === 'critical' ? `0 0 6px ${sev.dot}50` : 'none',
                          }}
                        />
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-xs font-medium truncate"
                            style={{ color: DS.text.primary }}
                          >
                            {inc.title}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span
                              className={cn(
                                'text-[9px] font-mono px-1 py-0.5 rounded border uppercase tracking-wider',
                                STATUS_COLORS[inc.status],
                              )}
                            >
                              {inc.status}
                            </span>
                            <span
                              className="text-[10px] font-mono"
                              style={{ color: DS.text.muted }}
                            >
                              {ageStr} ago
                            </span>
                            {inc.assignedAnalyst ? (
                              <span className="text-[10px]" style={{ color: DS.text.secondary }}>
                                → {inc.assignedAnalyst}
                              </span>
                            ) : (
                              <span className="text-[10px] text-[#c9b787]/70">unassigned</span>
                            )}
                          </div>
                        </div>
                        <span
                          className={cn(
                            'text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase shrink-0',
                            sev.bg,
                            sev.text,
                            sev.border,
                          )}
                        >
                          {inc.severity}
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Approval Queue */}
          <div
            className="col-span-12 lg:col-span-4"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{ height: 2, background: 'linear-gradient(90deg, #c9b787, transparent)' }}
            />
            <div
              className="px-4 py-3 border-b flex items-center justify-between"
              style={{ borderColor: DS.borderMuted }}
            >
              <div className="flex items-center gap-2">
                <ClipboardCheck className="w-3.5 h-3.5 text-[#c9b787]" />
                <span className="text-xs font-semibold text-white">Approval Queue</span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-[#c9b787]/15 text-[#c9b787] border border-[#c9b787]/20">
                  {approvalQueue.length}
                </span>
                {pendingActions && (
                  <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70">
                    LIVE
                  </span>
                )}
              </div>
              <Link href="/response-orchestration">
                <span className="text-[10px] text-[#c9b787]/60 hover:text-[#c9b787] cursor-pointer flex items-center gap-1">
                  All <ChevronRight className="w-3 h-3" />
                </span>
              </Link>
            </div>
            <div className="divide-y" style={{ borderColor: DS.borderMuted }}>
              {approvalQueue.map((item) => {
                const sev = SEV_COLORS[item.severity] ?? SEV_COLORS.high;
                return (
                  <div key={item.id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-start gap-2 min-w-0">
                        <div
                          className="w-1 h-1 rounded-full shrink-0 mt-1.5"
                          style={{ backgroundColor: sev.dot }}
                        />
                        <p
                          className="text-[11px] font-medium leading-snug"
                          style={{ color: DS.text.primary }}
                        >
                          {item.action}
                        </p>
                      </div>
                      <span
                        className={cn(
                          'text-[8px] font-mono px-1 py-0.5 rounded border shrink-0 uppercase',
                          sev.bg,
                          sev.text,
                          sev.border,
                        )}
                      >
                        {item.severity}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787]/80 uppercase tracking-wider">
                        approval_required
                      </span>
                      <span className="text-[10px]" style={{ color: DS.text.muted }}>
                        {item.requestedBy} · {item.requestedAt}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button className="flex-1 py-1.5 rounded text-[10px] font-semibold bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787] hover:bg-[#c9b787]/20 transition-colors">
                        Approve
                      </button>
                      <button className="flex-1 py-1.5 rounded text-[10px] font-semibold bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 text-[#f5f5f5] hover:bg-[#f5f5f5]/20 transition-colors">
                        Reject
                      </button>
                    </div>
                  </div>
                );
              })}
              {approvalQueue.length === 0 && (
                <div className="px-4 py-6 text-center text-[11px]" style={{ color: DS.text.muted }}>
                  No pending approvals
                </div>
              )}
            </div>
          </div>

          {/* Unresolved Findings */}
          <div
            className="col-span-12 lg:col-span-3"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{ height: 2, background: 'linear-gradient(90deg, #8a8a8a, transparent)' }}
            />
            <div
              className="px-4 py-3 border-b flex items-center justify-between"
              style={{ borderColor: DS.borderMuted }}
            >
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-3.5 h-3.5 text-[#8a8a8a]" />
                <span className="text-xs font-semibold text-white">Unresolved Findings</span>
              </div>
              <span className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
                {unresolvedFindings}
              </span>
            </div>
            <div className="px-4 py-6">
              <div className="flex flex-col items-center gap-2">
                <div
                  className="text-4xl font-bold font-mono tabular-nums"
                  style={{
                    color:
                      unresolvedFindings > 5
                        ? '#f5f5f5'
                        : unresolvedFindings > 0
                          ? '#c9b787'
                          : '#c9b787',
                  }}
                >
                  {unresolvedFindings}
                </div>
                <span className="text-[10px]" style={{ color: DS.text.tertiary }}>
                  open or confirmed
                </span>
                <div
                  style={{
                    width: 80,
                    height: 4,
                    background: 'rgba(255,255,255,0.05)',
                    borderRadius: 2,
                    overflow: 'hidden',
                    marginTop: 4,
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.min(unresolvedFindings * 10, 100)}%`,
                      background: unresolvedFindings > 5 ? '#f5f5f5' : '#c9b787',
                      borderRadius: 2,
                    }}
                  />
                </div>
                <Link href="/decision-console">
                  <span className="text-[10px] text-[#c9b787]/60 hover:text-[#c9b787] cursor-pointer flex items-center gap-1 mt-3">
                    Decision Console <ChevronRight className="w-3 h-3" />
                  </span>
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Row 3: Recent Decisions + Quick Stats */}
        <div className="grid grid-cols-12 gap-4">
          {/* Recent Decisions */}
          <div
            className="col-span-12 lg:col-span-7"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{ height: 2, background: 'linear-gradient(90deg, #c9b787, transparent)' }}
            />
            <div
              className="px-4 py-3 border-b flex items-center justify-between"
              style={{ borderColor: DS.borderMuted }}
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-[#c9b787]" />
                <span className="text-xs font-semibold text-white">Recent Decisions</span>
                {recentDecisions && (
                  <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70">
                    LIVE
                  </span>
                )}
              </div>
              <Link href="/decision-console">
                <span className="text-[10px] text-[#c9b787]/60 hover:text-[#c9b787] cursor-pointer flex items-center gap-1">
                  Decision Console <ChevronRight className="w-3 h-3" />
                </span>
              </Link>
            </div>
            <div className="divide-y" style={{ borderColor: DS.borderMuted }}>
              {displayDecisions.map((dec) => (
                <div
                  key={dec.id}
                  className="px-4 py-3 flex items-start gap-4 hover:bg-white/[0.01] transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium mb-1" style={{ color: DS.text.primary }}>
                      {dec.title}
                    </p>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px]" style={{ color: DS.text.secondary }}>
                        {dec.analyst}
                      </span>
                      <span className="text-[10px]" style={{ color: DS.text.muted }}>
                        {dec.at}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    {dec.confidence > 0 && (
                      <div className="flex items-center gap-1">
                        <div className="h-1 rounded-full bg-white/10 w-16 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[#c9b787]"
                            style={{ width: `${dec.confidence}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-[#c9b787] tabular-nums">
                          {dec.confidence}%
                        </span>
                      </div>
                    )}
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider border border-[#c9b787]/20 bg-[#c9b787]/10 text-[#c9b787]">
                      {dec.outcome}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Stats */}
          <div
            className="col-span-12 lg:col-span-5"
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{ height: 2, background: 'linear-gradient(90deg, #c9b787, transparent)' }}
            />
            <div
              className="px-4 py-3 border-b flex items-center gap-2"
              style={{ borderColor: DS.borderMuted }}
            >
              <BarChart3 className="w-3.5 h-3.5 text-[#c9b787]" />
              <span className="text-xs font-semibold text-white">Quick Stats</span>
            </div>
            <div className="divide-y" style={{ borderColor: DS.borderMuted }}>
              {[
                {
                  label: 'Total Alerts (all)',
                  value: posture?.totalAlerts ?? alerts.length,
                  color: DS.text.primary,
                },
                { label: 'Open Incidents', value: liveOpenIncidents, color: '#f5f5f5' },
                { label: 'Critical Alerts', value: liveCriticalAlerts, color: '#f5f5f5' },
                { label: 'Unresolved Findings', value: unresolvedFindings, color: '#c9b787' },
                { label: 'Pending Actions', value: approvalQueue.length, color: '#c9b787' },
              ].map((row) => (
                <div key={row.label} className="px-4 py-3 flex items-center justify-between">
                  <span className="text-[11px]" style={{ color: DS.text.secondary }}>
                    {row.label}
                  </span>
                  <div className="flex items-center gap-2">
                    <div
                      style={{
                        width: 60,
                        height: 3,
                        background: 'rgba(255,255,255,0.05)',
                        borderRadius: 2,
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min((Number(row.value) / 20) * 100, 100)}%`,
                          background: row.color,
                          borderRadius: 2,
                        }}
                      />
                    </div>
                    <span
                      className="text-[11px] font-mono font-bold w-8 text-right"
                      style={{ color: row.color }}
                    >
                      {row.value}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
