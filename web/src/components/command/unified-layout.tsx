import { EvidenceDrawer } from '@szl-holdings/design-system/cockpit/evidence-drawer';
import { useAuth } from '@szl-holdings/replit-auth-web';
import {
  useDemoMode,
} from '@szl-holdings/shared-ui/demo-mode';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Brain,
  Building,
  CheckCircle2,
  CheckSquare,
  ChevronRight,
  Clapperboard,
  Code,
  Cpu,
  Crown,
  Database,
  DollarSign,
  FileText,
  FlaskConical,
  GitBranch,
  GitCommit,
  GitMerge,
  Globe,
  Globe2,
  Heart,
  Inbox,
  Layers,
  LayoutDashboard,
  Lightbulb,
  Lock,
  Map,
  Menu,
  Mic,
  Network,
  Phone,
  Play,
  Radio,
  RotateCcw,
  Satellite,
  Scale,
  Search,
  Server,
  Shield,
  ShieldCheck,
  Sigma,
  Target,
  Users,
  Workflow,
  X,
  Zap,
} from 'lucide-react';
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'wouter';
import { FabricShellProvider, useFabricShell } from '../../lib/fabric-shell-context';
import { VoiceCommandPanel } from './voice-command-panel';

export type WorkspaceMode = 'strategy' | 'operations' | 'infrastructure';

const T = {
  bg: '#0a0a0a',
  surface: 'rgba(255,255,255,0.018)',
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.12)',
  text: '#f5f5f5',
  textDim: '#8a8a8a',
  textMuted: '#5e5e5e',
  accent: '#c9b787',
  mono: 'ui-monospace, SFMono-Regular, Menlo, monospace',
};

const WORKSPACE_TABS: {
  mode: WorkspaceMode;
  label: string;
  icon: typeof LayoutDashboard;
}[] = [
  { mode: 'strategy', label: 'Strategy', icon: Globe2 },
  { mode: 'operations', label: 'Operations', icon: Zap },
  { mode: 'infrastructure', label: 'Infrastructure', icon: Shield },
];

type NavItemDef = { href: string; label: string; icon: typeof LayoutDashboard; external?: boolean };
type NavGroup = { section: string; items: NavItemDef[] };

const ECOSYSTEM_APPS_NAV: NavGroup = {
  section: 'Ecosystem Apps',
  items: [
    { href: '/conduit/', label: 'Conduit — Reverse ETL', icon: Workflow, external: true },
    { href: '/counsel/', label: 'Counsel — Legal', icon: Scale, external: true },
    { href: '/imperium/', label: 'IMPERIUM', icon: Crown, external: true },
    { href: '/governance/lexicon', label: 'LEXICON — License Intelligence', icon: Zap, external: false },
    { href: '/stephen-site/', label: 'Stephen Site', icon: Globe, external: true },
  ],
};

const CARLOTA_NAV: NavGroup = {
  section: 'Carlota Jo',
  items: [
    { href: '/carlota/pipeline', label: 'Lead Pipeline', icon: Users },
    { href: '/carlota-jo/', label: 'Consulting Site', icon: Globe, external: true },
  ],
};

const STRATEGY_NAV: NavGroup[] = [
  {
    section: 'ATLAS Spatial Runtime',
    items: [
      { href: '/strategy/atlas-runtime', label: 'Cross-Domain Twin View', icon: Layers },
      { href: '/strategy/digital-twins', label: 'Digital Twin Registry', icon: Cpu },
      { href: '/strategy/worldline-registry', label: 'Worldline Registry', icon: GitBranch },
      { href: '/vessels/atlas-runtime', label: 'SEXTANT ATLAS Runtime', icon: Satellite, external: true },
      { href: '/terra/atlas-runtime', label: 'DOMAINE ATLAS Runtime', icon: Map, external: true },
    ],
  },
  {
    section: 'Command',
    items: [
      { href: '/demo', label: 'Demo Launchpad', icon: Play },
      { href: '/strategy', label: 'Governed Decision Loop', icon: LayoutDashboard },
      { href: '/strategy/enterprise-state', label: 'Enterprise State', icon: Building },
      { href: '/strategy/executive-briefing', label: 'Executive Briefing', icon: FileText },
      { href: '/strategy/briefing', label: 'Briefing History', icon: BarChart3 },
    ],
  },
  {
    section: 'Cross-Platform Intelligence',
    items: [
      { href: '/strategy/cross-platform', label: 'Signal Correlation', icon: GitMerge },
      { href: '/intelligence/evidence', label: 'Evidence Explorer', icon: Sigma },
      { href: '/strategy/cross-platform/evidence', label: 'Evidence Registry', icon: Database },
      { href: '/strategy/cross-platform/run-health', label: 'Run Health', icon: Activity },
      { href: '/strategy/cross-platform/pilots', label: 'Pilot Intelligence', icon: Users },
    ],
  },
  {
    section: 'Primitives',
    items: [
      { href: '/strategy/simulation', label: 'Simulation', icon: Activity },
      { href: '/strategy/correlation-map', label: 'Outcome Graph', icon: Network },
      { href: '/strategy/signal-chains', label: 'Signal Chains', icon: GitCommit },
    ],
  },
  {
    section: 'Cognitive Runtime',
    items: [
      { href: '/cognitive', label: 'Command Center', icon: Brain },
      { href: '/cognitive/self-model', label: 'Self Model', icon: Cpu },
      { href: '/cognitive/world-model', label: 'World Model', icon: Globe },
      { href: '/cognitive/memory', label: 'Memory Explorer', icon: Archive },
      { href: '/cognitive/planner', label: 'Planner Studio', icon: GitMerge },
      { href: '/cognitive/verifier', label: 'Verifier Console', icon: CheckCircle2 },
      { href: '/cognitive/reflection', label: 'Reflection Console', icon: Lightbulb },
      { href: '/cognitive/traces', label: 'Trace Replay', icon: Clapperboard },
      { href: '/cognitive/policy-sim', label: 'Policy Simulation', icon: FlaskConical },
    ],
  },
  CARLOTA_NAV,
  ECOSYSTEM_APPS_NAV,
];

const OPERATIONS_NAV: NavGroup[] = [
  {
    section: 'A11oy Agent Runtime',
    items: [
      { href: '/agents', label: 'Operator Control Plane', icon: Bot },
      { href: '/agents/workcells', label: 'Workcells', icon: Layers },
      { href: '/agents/tools', label: 'Tool Registry', icon: Zap },
      { href: '/agents/evals', label: 'MirrorEval', icon: FlaskConical },
      { href: '/agents/memory', label: 'Memory Health', icon: Archive },
      { href: '/agents/model-router', label: 'Model Router', icon: Cpu },
      { href: '/agents/skills', label: 'Skills', icon: BookOpen },
    ],
  },
  {
    section: 'Tool Intelligence',
    items: [
      { href: '/operations/forge', label: 'Tool Intelligence Hub', icon: Sigma },
    ],
  },
  {
    section: 'Global Fabric',
    items: [{ href: '/operations/fabric', label: 'Global Operations Fabric', icon: Globe2 }],
  },
  {
    section: 'Governed Decision Loop',
    items: [
      { href: '/operations', label: 'Executive Command', icon: LayoutDashboard },
      { href: '/operations/prism/pulse', label: 'Pulse', icon: Heart },
      { href: '/operations/prism/signals', label: 'Signal Feed', icon: Radio },
      { href: '/operations/prism/atlas-execute', label: 'ATLAS Execute', icon: Play },
      { href: '/operations/rules-studio', label: 'Rules Studio', icon: GitBranch },
      { href: '/operations/blocker-board', label: 'Blocker Board', icon: AlertTriangle },
      { href: '/operations/approvals', label: 'Approvals', icon: CheckSquare },
      { href: '/operations/policy-approvals', label: 'Policy Approvals', icon: ShieldCheck },
      { href: '/operations/policy-manager', label: 'Policy Manager', icon: ShieldCheck },
      { href: '/operations/trust-audit', label: 'Proof Chain Audit', icon: Shield },
      { href: '/governed-cockpit', label: 'Governed Intelligence', icon: Shield },
      { href: '/operations/inbox', label: 'Command Inbox', icon: Inbox },
    ],
  },
  {
    section: 'Automations',
    items: [{ href: '/operations/automations', label: 'n8n Automation Bridge', icon: Workflow }],
  },
  {
    section: 'Counsel — Execution',
    items: [
      { href: '/operations/continuum/policy-compiler', label: 'Policy Compiler', icon: Code },
      { href: '/operations/continuum/canvas', label: 'Workflow Canvas', icon: Workflow },
      { href: '/operations/continuum/actions', label: 'Action Queue', icon: Activity },
      { href: '/operations/continuum/governance', label: 'Covenant Policy', icon: Lock },
      { href: '/operations/continuum/intelligence', label: 'Intelligence', icon: Brain },
      { href: '/operations/continuum/traces', label: 'Execution Traces', icon: GitBranch },
      { href: '/operations/runs', label: 'Run Console', icon: Play },
      { href: '/operations/evidence-explorer', label: 'Evidence Explorer', icon: Database },
      { href: '/operations/eval-studio', label: 'Eval Studio', icon: FlaskConical },
      { href: '/operations/ownership', label: 'Ownership Map', icon: Users },
    ],
  },
  {
    section: 'Precision Evolution Runtime',
    items: [
      { href: '/evolution', label: 'Runtime Overview', icon: Cpu },
      { href: '/evolution/evaluation', label: 'Evaluation Console', icon: FlaskConical },
      { href: '/evolution/governance', label: 'Governance Console', icon: ShieldCheck },
      { href: '/evolution/diagnostics', label: 'Diagnostics', icon: Activity },
    ],
  },
  {
    section: 'Observability',
    items: [
      { href: '/operations/autonomous-noc', label: 'Autonomous NOC', icon: Bot },
      { href: '/operations/slo', label: 'SLO Management', icon: Target },
      { href: '/operations/metrics', label: 'Metrics', icon: BarChart3 },
      { href: '/operations/logs', label: 'Log Analytics', icon: Database },
      { href: '/operations/tracing', label: 'Distributed Tracing', icon: GitBranch },
      { href: '/operations/topology', label: 'Service Topology', icon: Network },
      { href: '/operations/self-healing', label: 'Self-Healing', icon: RotateCcw },
    ],
  },
  {
    section: 'Operations',
    items: [
      { href: '/operations/what-changed', label: 'Twin State Changes', icon: Activity },
      { href: '/operations/digest', label: 'Digest Center', icon: FileText },
      { href: '/operations/finops', label: 'FinOps', icon: DollarSign },
      { href: '/operations/on-call', label: 'On-Call', icon: Phone },
      { href: '/operations/runbook-studio', label: 'Mission Runbooks', icon: BookOpen },
      { href: '/operations/noise-reduction', label: 'Noise Reduction', icon: Bell },
    ],
  },
  {
    section: 'Cognitive Consoles',
    items: [
      { href: '/cognitive/overview', label: 'Consoles Overview', icon: Brain },
      { href: '/cognitive/traces', label: 'Trace Replay', icon: Clapperboard },
      { href: '/cognitive/evals', label: 'Eval Console', icon: FlaskConical },
      { href: '/cognitive/policies', label: 'Policy Console', icon: ShieldCheck },
    ],
  },
  {
    section: 'Open Evaluation Layer',
    items: [
      { href: '/operations/open-eval-hub', label: 'Open Evaluation Hub', icon: FlaskConical },
      { href: '/agents/evals', label: 'MirrorEval', icon: Sigma },
      { href: '/operations/eval-studio', label: 'Eval Studio', icon: Layers },
      { href: '/evolution/evaluation', label: 'Evolution Eval Console', icon: GitBranch },
    ],
  },
  ECOSYSTEM_APPS_NAV,
];

const OPERATIONS_ADMIN_NAV: NavGroup = {
  section: 'Governance Admin',
  items: [
    { href: '/admin/command-center', label: 'Command Center', icon: LayoutDashboard },
    { href: '/operations/admin/analytics', label: 'Analytics Intelligence', icon: BarChart3 },
    { href: '/operations/admin/experiments', label: 'Experimentation', icon: FlaskConical },
    { href: '/operations/governance-tiers', label: 'Governance Tiers', icon: ShieldCheck },
    { href: '/operations/guardrail-configs', label: 'Guardrail Configs', icon: Lock },
  ],
};

const ADMIN_ROLES = new Set(['admin', 'super_admin']);

export function getOperationsNav(isAdmin: boolean): NavGroup[] {
  if (!isAdmin) return OPERATIONS_NAV;
  const ecosystemIdx = OPERATIONS_NAV.findIndex((g) => g === ECOSYSTEM_APPS_NAV);
  const insertAt = ecosystemIdx === -1 ? OPERATIONS_NAV.length : ecosystemIdx;
  return [
    ...OPERATIONS_NAV.slice(0, insertAt),
    OPERATIONS_ADMIN_NAV,
    ...OPERATIONS_NAV.slice(insertAt),
  ];
}

const INFRASTRUCTURE_NAV: NavGroup[] = [
  {
    section: 'IMPERIUM Command',
    items: [
      { href: '/infrastructure', label: 'Executive Console', icon: Crown },
      { href: '/infrastructure/intelligence', label: 'Intelligence Briefing', icon: Radio },
      { href: '/infrastructure/imperium-map', label: 'Resource Map', icon: Map },
      { href: '/infrastructure/imperium/atlas-execute', label: 'ATLAS Execute', icon: Play },
    ],
  },
  {
    section: 'Security & Governance',
    items: [
      { href: '/infrastructure/praetorian', label: 'Security Perimeter', icon: Shield },
      { href: '/infrastructure/senate', label: 'Governance Board', icon: BookOpen },
      { href: '/infrastructure/centurion', label: 'AI Operations', icon: Cpu },
    ],
  },
  {
    section: 'Command & Control',
    items: [
      { href: '/infrastructure/directives', label: 'Directive Cascade', icon: Zap },
      { href: '/infrastructure/coalition', label: 'Coalition Manager', icon: Users },
      { href: '/infrastructure/reserves', label: 'Strategic Reserves', icon: Database },
    ],
  },
  {
    section: 'Network',
    items: [
      { href: '/infrastructure/supply-lines', label: 'Network Topology', icon: Network },
      { href: '/infrastructure/geospatial', label: 'Geospatial Intel', icon: Satellite },
      { href: '/infrastructure/substrate', label: 'Substrate Inference', icon: Server },
    ],
  },
  {
    section: 'MCP Ecosystem',
    items: [
      { href: '/ecosystem', label: 'Topology Map', icon: Network },
      { href: '/ecosystem/observatory', label: 'Agent Observatory', icon: Bot },
      { href: '/ecosystem/inspector', label: 'Tool Inspector', icon: Search },
      { href: '/ecosystem/counterfactual', label: 'Counterfactual Studio', icon: GitBranch },
    ],
  },
];

function SectionHeader({ label }: { label: string }) {
  return (
    <div
      aria-hidden="true"
      style={{
        padding: '0.625rem 1rem 0.25rem',
        fontSize: '0.5625rem',
        fontWeight: 500,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        color: T.textMuted,
        fontFamily: T.mono,
        marginTop: '0.375rem',
      }}
    >
      {label}
    </div>
  );
}

function NavItem({
  href,
  label,
  icon: Icon,
  isActive,
  badge,
  external,
}: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  isActive: boolean;
  badge?: ReactNode;
  external?: boolean;
}) {
  const s: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.3rem 1rem',
    fontSize: '0.75rem',
    fontWeight: isActive ? 500 : 400,
    color: isActive ? T.text : T.textDim,
    background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
    borderLeft: isActive ? `2px solid ${T.accent}` : '2px solid transparent',
    textDecoration: 'none',
    letterSpacing: '-0.005em',
    transition: 'color 0.15s, background 0.15s',
    cursor: 'pointer',
  };
  const inner = (
    <>
      <Icon style={{ width: 13, height: 13, flexShrink: 0, color: isActive ? T.text : T.textMuted, opacity: isActive ? 1 : 0.7 }} />
      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      {badge}
      {external && (
        <ChevronRight style={{ width: 10, height: 10, flexShrink: 0, color: T.textMuted, transform: 'rotate(-45deg)' }} />
      )}
    </>
  );
  if (external) {
    return <a href={href} style={s}>{inner}</a>;
  }
  return <Link href={href} style={s}>{inner}</Link>;
}

function CountBadge({ count, title }: { count: number; title?: string }) {
  if (!count) return null;
  return (
    <span
      style={{
        fontSize: '0.5625rem',
        fontFamily: T.mono,
        fontWeight: 600,
        padding: '0 0.3rem',
        borderRadius: 4,
        color: T.textDim,
        background: 'rgba(255,255,255,0.04)',
        border: `1px solid ${T.border}`,
        minWidth: 14,
        textAlign: 'center',
        lineHeight: '15px',
        flexShrink: 0,
      }}
      title={title}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}

function ConsolesOverviewBadge() {
  const base = (import.meta.env.BASE_URL ?? '/a11oy/').replace(/\/$/, '');
  const apiUrl = (path: string) => `${base}/api${path}`;
  const fetchJson = <TData,>(url: string): Promise<TData> =>
    fetch(url, { credentials: 'include' }).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
    );

  const evalsQuery = useQuery<{ recentRuns?: Array<{ regressionSeverity?: string }> }>({
    queryKey: ['cognitive-overview-badge', 'evals-summary'],
    queryFn: () => fetchJson(apiUrl('/cognitive/evals/summary')),
    refetchInterval: 30_000, staleTime: 15_000, retry: 0,
  });
  const approvalsQuery = useQuery<{ data?: unknown[]; meta?: { total?: number } }>({
    queryKey: ['cognitive-overview-badge', 'approvals-pending'],
    queryFn: () => fetchJson(apiUrl('/approvals?status=pending&limit=10')),
    refetchInterval: 30_000, staleTime: 15_000, retry: 0,
  });
  const tracesQuery = useQuery<{ data?: Array<{ status?: string; errors?: unknown[] }> }>({
    queryKey: ['cognitive-overview-badge', 'traces-recent'],
    queryFn: () => fetchJson(apiUrl('/cognitive/traces?limit=10')),
    refetchInterval: 30_000, staleTime: 15_000, retry: 0,
  });

  const regressions = (evalsQuery.data?.recentRuns ?? []).filter(
    (r) => r.regressionSeverity && r.regressionSeverity !== 'none',
  ).length;
  const approvals = approvalsQuery.data?.meta?.total ?? approvalsQuery.data?.data?.length ?? 0;
  const flagged = (tracesQuery.data?.data ?? []).filter(
    (t) => t.status === 'flagged' || (t.errors && t.errors.length > 0),
  ).length;
  const total = regressions + approvals + flagged;

  return <CountBadge count={total} title={total ? `${total} items needing attention` : undefined} />;
}

function CommandCenterBadge() {
  const base = (import.meta.env.BASE_URL ?? '/a11oy/').replace(/\/$/, '');
  const { data } = useQuery<{ total: number }>({
    queryKey: ['admin', 'command-center-badge'],
    queryFn: () =>
      fetch(`${base}/api/admin/command-center/badge`, { credentials: 'include' }).then((r) =>
        r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
      ),
    refetchInterval: 60_000, staleTime: 30_000, retry: 0,
  });
  return <CountBadge count={data?.total ?? 0} />;
}

function PendingApprovalsBadge() {
  const { data } = useQuery<{ data?: unknown[]; meta?: { total?: number } }>({
    queryKey: ['guardian', 'actions-pending-count'],
    queryFn: () =>
      fetch('/api/guardian/actions?status=pending&limit=1', { credentials: 'include' }).then((r) =>
        r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
      ),
    refetchInterval: 30_000, staleTime: 15_000, retry: 0,
  });
  return <CountBadge count={data?.meta?.total ?? data?.data?.length ?? 0} />;
}

function WorkspaceSwitcher({
  mode,
  onModeChange,
}: {
  mode: WorkspaceMode;
  onModeChange: (m: WorkspaceMode) => void;
}) {
  return (
    <div style={{ padding: '0.5rem 0.75rem', borderBottom: `1px solid ${T.border}` }}>
      <div style={{ display: 'flex', gap: 2 }}>
        {WORKSPACE_TABS.map((tab) => {
          const isActive = mode === tab.mode;
          return (
            <button
              key={tab.mode}
              onClick={() => onModeChange(tab.mode)}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '0.375rem 0.25rem',
                borderRadius: 6,
                border: `1px solid ${isActive ? T.borderStrong : 'transparent'}`,
                background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <span
                style={{
                  fontSize: '0.5625rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  fontFamily: T.mono,
                  color: isActive ? T.text : T.textMuted,
                }}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function GlobalActivityTicker() {
  const { auditEvents } = useFabricShell();
  if (auditEvents.length === 0) return null;
  return (
    <div
      style={{
        height: 24,
        display: 'flex',
        alignItems: 'center',
        overflow: 'hidden',
        flexShrink: 0,
        background: T.bg,
        borderTop: `1px solid ${T.border}`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0 0.75rem',
          flexShrink: 0,
          borderRight: `1px solid ${T.border}`,
          height: '100%',
        }}
      >
        <Activity style={{ width: 10, height: 10, color: T.textMuted }} />
        <span
          style={{
            fontSize: '0.5rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.14em',
            fontFamily: T.mono,
            color: T.textMuted,
          }}
        >
          Fabric
        </span>
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1.5rem',
            paddingLeft: '0.75rem',
            whiteSpace: 'nowrap',
            animation: 'fabric-scroll 25s linear infinite',
          }}
        >
          {[...auditEvents.slice(0, 10), ...auditEvents.slice(0, 10)].map((ev, i) => (
            <span
              key={`${ev.eventId}-${i}`}
              style={{
                fontSize: '0.5625rem',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                color: T.textMuted,
              }}
            >
              <span
                style={{
                  width: 3,
                  height: 3,
                  borderRadius: '50%',
                  display: 'inline-block',
                  background: T.textMuted,
                }}
              />
              {ev.action}
            </span>
          ))}
        </div>
      </div>
      <style>{`@keyframes fabric-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }`}</style>
    </div>
  );
}

function GlobalEvidenceDrawerShell() {
  const { drawerOpen, drawerTitle, drawerEvidence, closeEvidenceDrawer } = useFabricShell();
  return (
    <EvidenceDrawer
      open={drawerOpen}
      onClose={closeEvidenceDrawer}
      title={drawerTitle}
      evidence={drawerEvidence}
      accent={T.accent}
    />
  );
}

function UnifiedLayoutInner({
  children,
  mode,
  onModeChange,
}: {
  children: ReactNode;
  mode: WorkspaceMode;
  onModeChange: (m: WorkspaceMode) => void;
}) {
  const [location, setLocation] = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [voicePanelOpen, setVoicePanelOpen] = useState(false);
  const { user } = useAuth();
  const userRoles: string[] = (user as { roles?: string[] } | null | undefined)?.roles ?? [];
  const isAdmin = userRoles.some((r) => ADMIN_ROLES.has(r));

  const navGroups =
    mode === 'strategy'
      ? STRATEGY_NAV
      : mode === 'operations'
        ? getOperationsNav(isAdmin)
        : INFRASTRUCTURE_NAV;

  const navScrollRef = useRef<HTMLElement | null>(null);
  const cognitiveSectionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (mode !== 'operations') return;
    if (!location.startsWith('/cognitive')) return;
    const scroller = navScrollRef.current;
    const target = cognitiveSectionRef.current;
    if (!scroller || !target) return;
    const scrollerRect = scroller.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offset = targetRect.top - scrollerRect.top + scroller.scrollTop;
    scroller.scrollTo({ top: offset, behavior: 'smooth' });
  }, [location, mode]);

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', background: T.bg, fontFeatureSettings: '"ss01", "cv11"' }}>
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.6)',
            zIndex: 10,
          }}
        />
      )}

      <aside
        style={{
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          width: 210,
          background: T.bg,
          borderRight: `1px solid ${T.border}`,
          position: 'relative',
          zIndex: 20,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            padding: '0 0.875rem',
            borderBottom: `1px solid ${T.border}`,
            gap: '0.5rem',
          }}
        >
          <div
            style={{
              width: 20,
              height: 20,
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1px solid ${T.borderStrong}`,
              fontSize: '0.5625rem',
              fontFamily: T.mono,
              color: T.text,
            }}
          >
            C
          </div>
          <div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 500, color: T.text, lineHeight: 1, letterSpacing: '-0.01em' }}>
              Command
            </div>
          </div>
        </div>

        <WorkspaceSwitcher
          mode={mode}
          onModeChange={(m) => {
            onModeChange(m);
            setSidebarOpen(false);
          }}
        />

        <nav
          ref={navScrollRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: '0.25rem 0',
          }}
        >
          {navGroups.map((group) => (
            <div
              key={group.section}
              ref={group.section === 'Cognitive Consoles' ? cognitiveSectionRef : undefined}
            >
              <SectionHeader label={group.section} />
              {group.items.map((item) => {
                const exactOnlyRoutes = ['/strategy', '/operations', '/infrastructure', '/cognitive', '/strategy/cross-platform'];
                const isActive = exactOnlyRoutes.includes(item.href)
                  ? location === item.href || (location === '/' && item.href === '/strategy')
                  : location.startsWith(item.href) && !exactOnlyRoutes.includes(item.href)
                    ? true
                    : location === item.href;
                const badge =
                  item.href === '/operations/policy-approvals' ? (
                    <PendingApprovalsBadge />
                  ) : item.href === '/cognitive/overview' ? (
                    <ConsolesOverviewBadge />
                  ) : item.href === '/admin/command-center' ? (
                    <CommandCenterBadge />
                  ) : undefined;
                return (
                  <NavItem
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    icon={item.icon}
                    isActive={isActive}
                    badge={badge}
                    external={item.external}
                  />
                );
              })}
            </div>
          ))}
        </nav>

        <div style={{ padding: '0.5rem 0.875rem', borderTop: `1px solid ${T.border}` }}>
          <div
            style={{
              fontSize: '0.5rem',
              textTransform: 'uppercase',
              letterSpacing: '0.14em',
              fontFamily: T.mono,
              fontWeight: 500,
              color: T.textMuted,
              marginBottom: '0.375rem',
            }}
          >
            Domain Packs
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {[
              { label: 'TENAX', href: '/sentra/' },
              { label: 'DOMAINE', href: '/terra/' },
              { label: 'SEXTANT', href: '/vessels/' },
              { label: 'Counsel', href: '/counsel/' },
            ].map((p) => (
              <a
                key={p.label}
                href={p.href}
                style={{
                  fontSize: '0.5625rem',
                  padding: '0.125rem 0.375rem',
                  borderRadius: 4,
                  fontFamily: T.mono,
                  color: T.textDim,
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${T.border}`,
                  textDecoration: 'none',
                  transition: 'color 0.15s',
                }}
              >
                {p.label}
              </a>
            ))}
          </div>
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <header
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 1.25rem',
            flexShrink: 0,
            zIndex: 10,
            borderBottom: `1px solid ${T.border}`,
            background: 'rgba(10,10,10,0.92)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              style={{
                display: 'none',
                padding: 4,
                borderRadius: 4,
                background: 'none',
                border: 'none',
                color: T.textDim,
                cursor: 'pointer',
              }}
              className="md-show"
            >
              {sidebarOpen ? <X style={{ width: 16, height: 16 }} /> : <Menu style={{ width: 16, height: 16 }} />}
            </button>
            <span style={{
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: T.text,
              letterSpacing: '-0.01em',
            }}>
              {WORKSPACE_TABS.find((t) => t.mode === mode)?.label}
            </span>
            <span style={{
              width: 1,
              height: 14,
              background: T.border,
            }} />
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.6875rem',
              fontFamily: T.mono,
              color: T.textDim,
              letterSpacing: '0.04em',
            }}>
              <span style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                background: T.accent,
                boxShadow: `0 0 6px ${T.accent}`,
              }} />
              Operational
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
            <button
              type="button"
              aria-label="Voice command"
              onClick={() => setVoicePanelOpen((o) => !o)}
              title="Open voice command"
              style={{
                padding: 4,
                borderRadius: 4,
                background: voicePanelOpen ? `${T.accent}18` : 'none',
                border: `1px solid ${voicePanelOpen ? `${T.accent}40` : 'transparent'}`,
                color: voicePanelOpen ? T.accent : T.textDim,
                cursor: 'pointer',
                transition: 'all 0.15s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Mic style={{ width: 14, height: 14 }} />
            </button>
            <button
              aria-label="Notifications"
              style={{
                padding: 4,
                borderRadius: 4,
                background: 'none',
                border: 'none',
                color: T.textDim,
                cursor: 'pointer',
                transition: 'color 0.15s',
              }}
            >
              <Bell style={{ width: 14, height: 14 }} />
            </button>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 500, color: T.text, lineHeight: 1.2, letterSpacing: '-0.005em' }}>
                {(user as { firstName?: string } | null)?.firstName ?? 'Stephen Lutar'}
              </div>
              <div style={{ fontSize: '0.5625rem', fontFamily: T.mono, color: T.textMuted, letterSpacing: '0.04em' }}>
                SZL Holdings
              </div>
            </div>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 6,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.5625rem',
                fontWeight: 600,
                fontFamily: T.mono,
                background: 'rgba(255,255,255,0.04)',
                border: `1px solid ${T.borderStrong}`,
                color: T.text,
              }}
            >
              SL
            </div>
          </div>
        </header>

        <main style={{ flex: 1, overflowY: 'auto', background: T.bg }}>
          {children}
        </main>

        <GlobalActivityTicker />
      </div>

      <GlobalEvidenceDrawerShell />
      <VoiceCommandPanel
        open={voicePanelOpen}
        onClose={() => setVoicePanelOpen(false)}
        onNavigate={(path, external) => {
          setVoicePanelOpen(false);
          if (external) {
            window.location.href = path;
          } else {
            setLocation(path);
          }
        }}
      />
    </div>
  );
}

export function UnifiedLayout({
  children,
  mode,
  onModeChange,
}: {
  children: ReactNode;
  mode: WorkspaceMode;
  onModeChange: (m: WorkspaceMode) => void;
}) {
  return (
    <FabricShellProvider>
      <UnifiedLayoutInner mode={mode} onModeChange={onModeChange}>
        {children}
      </UnifiedLayoutInner>
    </FabricShellProvider>
  );
}
