import { useDemoMode } from '../../lib/operations/demo-mode';
import { EnvironmentLabel } from '@szl-holdings/shared-ui/alloy-decision-card';
import { SectionErrorBoundary } from '@szl-holdings/shared-ui/error-boundary';
import { useAuth } from '@szl-holdings/replit-auth-web';
import {
  GettingStartedChecklist,
  type OnboardingConfig,
  OnboardingWizard,
  useOnboardingState,
} from '@szl-holdings/shared-ui/onboarding';
import { RealtimeStatusIndicator } from '@szl-holdings/shared-ui/realtime-status-indicator';
import { useSandboxMode } from '@szl-holdings/shared-ui/sandbox-mode';
import { ServiceStatusRail } from '@szl-holdings/shared-ui/service-status-rail';
import { useRealtimeChannel } from '@szl-holdings/shared-ui/use-realtime-channel';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BellOff,
  BookOpen,
  Bot,
  Boxes,
  Brain,
  Building,
  Calculator,
  Calendar,
  CheckSquare,
  ChevronDown,
  Clapperboard,
  Code,
  Cpu,
  Database,
  DollarSign,
  Download,
  FileText,
  Flag,
  Gauge,
  GitBranch,
  Globe,
  Headphones,
  Heart,
  History,
  Inbox,
  Layers,
  LayoutDashboard,
  Menu,
  Monitor,
  Network,
  Phone,
  Play,
  Power,
  Radio,
  RotateCcw,
  Scale,
  Search,
  Send,
  Settings,
  Shield,
  Sliders,
  Target,
  TrendingUp,
  Users,
  Workflow,
  X,
  Zap,
} from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Link, useLocation } from 'wouter';

const COMMAND_ONBOARDING_CONFIG: OnboardingConfig = {
  appId: 'command',
  appName: 'KORA',
  accentColor: '#d4a054',
  steps: [
    {
      id: 'welcome',
      title: 'Welcome to Command',
      description:
        'Command is your business observability command center — detecting operational risk, surfacing ownership gaps, and routing action before business damage occurs.',
      placement: 'center',
      icon: Zap,
    },
    {
      id: 'prism',
      title: 'The PRISM Framework',
      description:
        "PRISM is Command's intelligence spine: Pulse (health), Risk (exposure), Intelligence (analysis), Signals (events), and Motion (action). Each dimension gives you a different lens on your business.",
      placement: 'center',
      icon: Activity,
    },
    {
      id: 'signals',
      title: 'Signals Feed',
      description:
        'Signals are cross-system events that matter — approval delays, ownership gaps, compliance exposure, SLA risks. Each signal carries evidence, confidence scores, and recommended next actions.',
      targetSelector: "a[href='/operations/prism/signals']",
      placement: 'right',
      icon: Radio,
    },
    {
      id: 'inbox',
      title: 'Command Inbox',
      description:
        'Your inbox surfaces the highest-priority items requiring your attention — ranked by business impact and urgency, not alert timestamp.',
      targetSelector: "a[href='/operations/inbox']",
      placement: 'right',
      icon: Inbox,
    },
    {
      id: 'ownership',
      title: 'Ownership Intelligence',
      description:
        "See who owns what, what's unassigned, where handoffs break, and who's overloaded — the gaps that cause issues to fall through the cracks.",
      targetSelector: "a[href='/operations/ownership']",
      placement: 'right',
      icon: Users,
    },
  ],
  checklist: [
    {
      id: 'explore-prism',
      label: 'Explore the PRISM framework',
      description: 'Check all five intelligence dimensions',
    },
    {
      id: 'check-signals',
      label: 'Review your signals feed',
      description: 'See cross-system events by urgency',
    },
    {
      id: 'check-inbox',
      label: 'Clear your command inbox',
      description: 'Review high-priority action items',
    },
    {
      id: 'check-ownership',
      label: 'Check ownership gaps',
      description: 'Review unassigned ownership areas',
    },
    {
      id: 'configure-alerts',
      label: 'Configure alert thresholds',
      description: 'Set risk tolerance and routing rules',
    },
    {
      id: 'explore-topology',
      label: 'Explore service topology',
      description: 'View system dependency relationships',
    },
  ],
};

const BG = { sidebar: '#060a12', header: 'rgba(6,10,18,0.85)', main: 'var(--gi-bg-base)' };
const BORDER = { subtle: 'rgba(255,255,255,0.04)', muted: 'rgba(255,255,255,0.06)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.5)',
  tertiary: 'rgba(255,255,255,0.28)',
  muted: 'rgba(255,255,255,0.14)',
};

const PRISM_ITEMS = [
  { key: 'P', label: 'Pulse', color: '#c9b787', icon: Heart, href: '/operations/prism/pulse' },
  {
    key: 'R',
    label: 'Risk',
    color: '#c45a4a',
    icon: AlertTriangle,
    href: '/operations/prism/risk',
  },
  {
    key: 'I',
    label: 'Intelligence',
    color: '#8b7ac8',
    icon: Brain,
    href: '/operations/prism/intelligence',
  },
  { key: 'S', label: 'Signals', color: '#c8953c', icon: Radio, href: '/operations/prism/signals' },
  { key: 'M', label: 'Motion', color: '#4a90b8', icon: Workflow, href: '/operations/prism/motion' },
];

const NAV_GROUPS = [
  {
    label: null,
    items: [
      { href: '/operations', label: 'Exec Command', icon: LayoutDashboard },
      { href: '/operations/demo-live', label: 'Live Demo', icon: Clapperboard },
    ],
  },
  {
    label: 'Core',
    items: [
      { href: '/operations/board-mode', label: 'Board Mode', icon: LayoutDashboard },
      { href: '/operations/blocker-board', label: 'Blocker Board', icon: AlertTriangle },
      { href: '/operations/bottleneck-heatmap', label: 'Bottleneck Heatmap', icon: BarChart3 },
      { href: '/operations/governed-decision-loop', label: 'Decision Loop', icon: Scale },
      { href: '/operations/decision-receipts', label: 'Decision Receipts', icon: FileText },
      { href: '/operations/digest', label: 'Digest Center', icon: FileText },
      { href: '/operations/approvals', label: 'Approvals', icon: CheckSquare },
      { href: '/operations/trust-audit', label: 'Trust & Audit', icon: Shield },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { href: '/operations/prism/pulse', label: 'Pulse', icon: Heart },
      { href: '/operations/prism/risk', label: 'Risk', icon: AlertTriangle },
      { href: '/operations/prism/intelligence', label: 'Intelligence', icon: Brain },
      { href: '/operations/prism/signals', label: 'Signals Feed', icon: Radio },
      { href: '/operations/prism/motion', label: 'Motion', icon: Workflow },
      { href: '/operations/living-topology', label: 'Living Topology', icon: Network },
      { href: '/operations/ai-ops', label: 'AI Quality Dashboard', icon: Brain },
      { href: '/operations/gpu-observatory', label: 'GPU & AI Observatory', icon: Cpu },
      { href: '/operations/business-signals', label: 'Business Signals', icon: DollarSign },
      { href: '/operations/predictive-intelligence', label: 'Predictive Intel', icon: TrendingUp },
      { href: '/operations/cognitive-runtime', label: 'Cognitive Runtime', icon: Brain },
      { href: '/operations/revenue-impact', label: 'Revenue Impact', icon: DollarSign },
      { href: '/operations/self-healing', label: 'Self-Healing Ops', icon: RotateCcw },
      { href: '/operations/failure-timeline', label: 'Failure Timeline', icon: TrendingUp },
      { href: '/operations/client-value', label: 'Client Value', icon: Users },
      { href: '/operations/ops-savings', label: 'Ops Savings', icon: Calculator },
      { href: '/operations/escalation-intelligence', label: 'Escalation Intel', icon: Brain },
      { href: '/operations/outcome-loop', label: 'Outcome Loop', icon: Activity },
      { href: '/operations/defer-lane', label: 'Defer Lane', icon: Gauge },
      { href: '/operations/shadow-mode', label: 'Shadow Mode', icon: Brain },
    ],
  },
  {
    label: 'Observability',
    items: [
      { href: '/operations/slo', label: 'SLO / SLI Management', icon: Target },
      { href: '/operations/finops', label: 'FinOps & Cloud Cost', icon: DollarSign },
      { href: '/operations/tracing', label: 'Distributed Tracing', icon: GitBranch },
      { href: '/operations/logs', label: 'Log Analytics', icon: Database },
      { href: '/operations/on-call', label: 'On-Call Management', icon: Phone },
      { href: '/operations/change-management', label: 'Change Intelligence', icon: Calendar },
      { href: '/operations/synthetic', label: 'Synthetic Monitoring', icon: Globe },
      { href: '/operations/capacity-planning', label: 'Capacity Planning', icon: Layers },
    ],
  },
  {
    label: 'Autonomous NOC',
    items: [
      { href: '/operations/autonomous-noc', label: 'Autonomous NOC', icon: Bot },
      { href: '/operations/noise-reduction', label: 'Noise Reduction', icon: BellOff },
      { href: '/operations/knowledge-graph', label: 'Knowledge Graph', icon: Network },
      { href: '/operations/runbook-studio', label: 'Runbook Studio', icon: BookOpen },
      { href: '/operations/dex', label: 'DEX Scoring', icon: Monitor },
      { href: '/operations/msp-command', label: 'MSP Command', icon: Building },
      { href: '/operations/dev-feedback', label: 'Dev Feedback', icon: Code },
    ],
  },
  {
    label: 'Operations',
    items: [
      { href: '/operations/inbox', label: 'Inbox', icon: Inbox },
      { href: '/operations/explorer', label: 'Explorer', icon: Search },
      { href: '/operations/topology', label: 'Topology', icon: Network },
      { href: '/operations/logs', label: 'Log Explorer', icon: Database },
      { href: '/operations/alert-management', label: 'Alert Management', icon: Bell },
      { href: '/operations/executive-summary', label: 'Executive Summary', icon: BarChart3 },
      { href: '/operations/ownership', label: 'Ownership', icon: Users },
      { href: '/operations/workflows', label: 'Workflows', icon: Workflow },
      { href: '/operations/readiness', label: 'Readiness', icon: Shield },
      { href: '/operations/continuum/actions', label: 'Action Queue', icon: Activity },
      { href: '/operations/continuum/templates', label: 'Templates', icon: Workflow },
      { href: '/operations/continuum/gates', label: 'Write-Back Gates', icon: CheckSquare },
      { href: '/operations/continuum/intelligence', label: 'Intelligence Fabric', icon: Zap },
      { href: '/operations/continuum/canvas', label: 'Workflow Canvas', icon: Brain },
      { href: '/operations/continuum/agents', label: 'Agent Monitor', icon: Radio },
      { href: '/operations/continuum/traces', label: 'Execution Traces', icon: Activity },
      { href: '/operations/continuum/governance', label: 'Governance', icon: Shield },
      { href: '/operations/continuum/integrations', label: 'Integration Health', icon: Network },
      { href: '/operations/continuum/compiler', label: 'Graph Compiler', icon: GitBranch },
      { href: '/operations/continuum/replay', label: 'Replay Timeline', icon: Play },
      { href: '/operations/continuum/simulate', label: 'Policy Simulator', icon: Shield },
      { href: '/operations/continuum/handoffs', label: 'Agent Handoffs', icon: Send },
      { href: '/operations/continuum/receipts', label: 'Trust Receipts', icon: FileText },
    ],
  },
];

const ADMIN_NAV = [
  { href: '/operations/admin/ops', label: 'Ops Console', icon: Network },
  { href: '/operations/admin/overview', label: 'System', icon: Settings },
  { href: '/operations/admin/settings', label: 'Platform Settings', icon: Settings },
  { href: '/operations/admin/tenant-health', label: 'Tenant Health', icon: Building },
  { href: '/operations/admin/users', label: 'Users', icon: Users },
  { href: '/operations/admin/flags', label: 'Flags', icon: Flag },
  { href: '/operations/admin/runtime-config', label: 'Runtime Config', icon: Sliders },
  { href: '/operations/admin/runtime-config/history', label: 'Runtime Config History', icon: History },
  { href: '/operations/admin/apps', label: 'Apps', icon: Boxes },
  { href: '/operations/admin/runs', label: 'Runs', icon: Play },
  { href: '/operations/admin/approvals', label: 'Queue', icon: CheckSquare },
  { href: '/operations/admin/audit', label: 'Audit', icon: FileText },
  { href: '/operations/admin/exports', label: 'Exports', icon: Download },
  { href: '/operations/admin/seeder', label: 'Seeder', icon: Database },
  { href: '/operations/admin/jobs', label: 'Jobs', icon: Activity },
  { href: '/operations/admin/kb', label: 'Knowledge Base', icon: BookOpen },
  { href: '/operations/admin/support', label: 'Support Ops', icon: Headphones },
];

const ADMIN_ROLES = ['admin', 'super_admin', 'ops'];

const PRISM_COLORS: Record<string, string> = {
  Pulse: '#d4a054',
  Risk: '#c45a4a',
  Intelligence: '#8b7ac8',
  Signals: '#c8953c',
  Motion: '#4a90b8',
};

function NavItem({
  href,
  icon: Icon,
  label,
  isActive,
  accent,
  onClick,
}: {
  href: string;
  icon: any;
  label: string;
  isActive: boolean;
  accent?: string;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-2.5 py-[5px] text-[10px] font-medium transition-all relative group',
        isActive ? '' : 'hover:bg-white/[0.03]',
      )}
      style={{ color: isActive ? (accent ?? '#d4a054') : TEXT.secondary }}
    >
      {isActive && (
        <div
          className="absolute left-0 top-1 bottom-1 w-[2px] rounded-r"
          style={{ background: accent ?? '#d4a054' }}
        />
      )}
      <Icon
        className="w-3 h-3 shrink-0"
        style={{
          color: isActive ? (accent ?? '#d4a054') : TEXT.tertiary,
          opacity: isActive ? 1 : 0.7,
        }}
      />
      <span>{label}</span>
    </Link>
  );
}

function DemoModeToggle() {
  const { state, activate, deactivate } = useDemoMode();
  const isActive = state.active;
  return (
    <div
      className="mx-1.5 mb-1"
      style={{ borderTop: `1px solid rgba(255,255,255,0.04)`, paddingTop: 6 }}
    >
      <button
        onClick={() => (isActive ? deactivate() : activate(state.currentScenario))}
        className="flex items-center justify-between w-full px-2.5 py-1.5 rounded transition-all text-[9px] font-medium"
        style={{
          background: isActive ? 'rgba(212,160,84,0.08)' : 'rgba(255,255,255,0.02)',
          border: `1px solid ${isActive ? 'rgba(212,160,84,0.2)' : 'rgba(255,255,255,0.05)'}`,
          color: isActive ? '#d4a054' : TEXT.tertiary,
        }}
        aria-label={isActive ? 'Deactivate demo mode' : 'Activate demo mode'}
        aria-pressed={isActive}
      >
        <div className="flex items-center gap-1.5">
          <Power className="w-2.5 h-2.5" />
          <span className="font-mono uppercase tracking-wider">Demo Mode</span>
        </div>
        <div className="flex items-center gap-1">
          {isActive && (
            <span className="relative flex h-1.5 w-1.5">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
                style={{ background: '#d4a054' }}
              />
              <span
                className="relative inline-flex rounded-full h-1.5 w-1.5"
                style={{ background: '#d4a054' }}
              />
            </span>
          )}
          <span
            className="text-[8px] font-mono"
            style={{ color: isActive ? '#d4a054' : TEXT.muted }}
          >
            {isActive ? 'ON' : 'OFF'}
          </span>
        </div>
      </button>
    </div>
  );
}

function AdminSection({ location }: { location: string }) {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const userRoles: string[] = (user as { roles?: string[] })?.roles ?? [];
  const isAdmin = userRoles.some((r) => ADMIN_ROLES.includes(r));
  if (!isAdmin) return null;
  const isInAdmin = location.startsWith('/operations/admin');
  if (!open && !isInAdmin) {
    return (
      <div className="mt-1 pt-1" style={{ borderTop: `1px solid ${BORDER.subtle}` }}>
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-2.5 py-[5px] text-[10px] font-medium w-full transition-all hover:bg-white/[0.03]"
          style={{ color: TEXT.tertiary }}
        >
          <Settings className="w-3 h-3 shrink-0" />
          <span>Settings</span>
          <ChevronDown className="w-2.5 h-2.5 ml-auto" />
        </button>
      </div>
    );
  }
  return (
    <div className="mt-1 pt-1" style={{ borderTop: `1px solid ${BORDER.subtle}` }}>
      <button onClick={() => setOpen(false)} className="flex items-center gap-2 px-2.5 pb-1 w-full">
        <span
          className="text-[8px] uppercase tracking-widest font-medium"
          style={{ color: TEXT.muted }}
        >
          Settings
        </span>
        <ChevronDown className="w-2.5 h-2.5 ml-auto rotate-180" style={{ color: TEXT.muted }} />
      </button>
      {ADMIN_NAV.map((item) => {
        const isActive = location === item.href || location.startsWith(item.href + '/') || (item.href !== '/operations/admin' && location.startsWith(item.href));
        return (
          <NavItem
            key={item.href}
            href={item.href}
            icon={item.icon}
            label={item.label}
            isActive={isActive}
          />
        );
      })}
    </div>
  );
}

export function CommandLayout({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { status: wsStatus } = useRealtimeChannel('command-metrics');
  const { replay: replayOnboarding } = useOnboardingState('command');
  const { sandboxActive } = useSandboxMode();
  const isDemoMode =
    sandboxActive || new URLSearchParams(window.location.search).get('demo') === 'true';
  const { state: demoState } = useDemoMode();
  const isLiveDemoActive = demoState.active;

  return (
    <div className="flex h-full overflow-hidden">
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-10 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'flex flex-col shrink-0 relative z-20 transition-transform duration-200',
          'fixed md:relative inset-y-0 left-0 w-48',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        )}
        style={{ background: BG.sidebar, borderRight: `1px solid ${BORDER.subtle}` }}
        role="navigation"
        aria-label="Sidebar navigation"
      >
        <div
          className="h-12 flex items-center px-3"
          style={{ borderBottom: `1px solid ${BORDER.subtle}` }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded flex items-center justify-center"
              style={{
                background: 'rgba(212,160,84,0.08)',
                border: `1px solid rgba(212,160,84,0.12)`,
              }}
            >
              <Zap className="w-3.5 h-3.5" style={{ color: '#d4a054' }} />
            </div>
            <div>
              <div
                className="text-[11px] font-bold tracking-wide leading-none"
                style={{ color: TEXT.primary }}
              >
                COMMAND
              </div>
              <div
                className="text-[7px] uppercase tracking-[0.15em] mt-px"
                style={{ color: 'rgba(212,160,84,0.5)' }}
              >
                Business Observability
              </div>
            </div>
          </div>
        </div>

        <div className="px-2 py-2" style={{ borderBottom: `1px solid ${BORDER.subtle}` }}>
          <div className="grid grid-cols-5 gap-0.5">
            {PRISM_ITEMS.map((p) => {
              const isActive = location.startsWith(p.href);
              return (
                <Link
                  key={p.key}
                  href={p.href}
                  className="flex flex-col items-center py-1 rounded transition-all"
                  style={{
                    background: isActive ? `${p.color}12` : 'transparent',
                    border: `1px solid ${isActive ? `${p.color}30` : 'transparent'}`,
                  }}
                >
                  <span className="text-[9px] font-black" style={{ color: p.color }}>
                    {p.key}
                  </span>
                  <span
                    className="text-[6px] uppercase tracking-wider"
                    style={{ color: `${p.color}70` }}
                  >
                    {p.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex-1 min-h-0 flex flex-col">
          <nav className="flex-1 min-h-0 px-1.5 py-2 flex flex-col gap-px overflow-y-auto">
            {NAV_GROUPS.map((group, gi) => (
              <div
                key={group.label ?? gi}
                className={gi > 0 ? 'mt-1 pt-1' : ''}
                style={gi > 0 ? { borderTop: `1px solid ${BORDER.subtle}` } : {}}
              >
                {group.label && (
                  <div
                    className="px-2.5 pb-1 text-[8px] font-medium uppercase tracking-widest"
                    style={{ color: TEXT.muted }}
                  >
                    {group.label}
                  </div>
                )}
                {group.items.map((item) => {
                  const isPrism = item.href.startsWith('/operations/prism/');
                  const prismColor = isPrism ? PRISM_COLORS[item.label] : undefined;
                  const isActive =
                    item.href === '/operations'
                      ? location === '/operations'
                      : location.startsWith(item.href);
                  return (
                    <NavItem
                      key={item.href}
                      href={item.href}
                      icon={item.icon}
                      label={item.label}
                      isActive={isActive}
                      accent={prismColor}
                      onClick={() => setSidebarOpen(false)}
                    />
                  );
                })}
              </div>
            ))}
            <AdminSection location={location} />
          </nav>

          <DemoModeToggle />

          {COMMAND_ONBOARDING_CONFIG.checklist && (
            <div className="mx-2 mb-2">
              <GettingStartedChecklist
                appId={COMMAND_ONBOARDING_CONFIG.appId}
                appName={COMMAND_ONBOARDING_CONFIG.appName}
                items={COMMAND_ONBOARDING_CONFIG.checklist}
                accentColor={COMMAND_ONBOARDING_CONFIG.accentColor}
                onReplayTour={replayOnboarding}
                collapsed
              />
            </div>
          )}
          <div
            className="shrink-0 mx-2 mb-2 px-2.5 py-2 rounded"
            style={{
              background: 'rgba(212,160,84,0.02)',
              border: `1px solid rgba(212,160,84,0.05)`,
            }}
          >
            <div
              className="text-[7px] uppercase tracking-widest font-mono mb-1.5"
              style={{ color: TEXT.muted }}
            >
              System Pulse
            </div>
            <div className="space-y-1">
              {[
                { k: 'Urgent', v: '5', c: '#c45a4a' },
                { k: 'Gaps', v: '8', c: '#c8953c' },
                { k: 'Latency', v: '34h', c: TEXT.tertiary },
              ].map((r) => (
                <div key={r.k} className="flex justify-between text-[8px]">
                  <span style={{ color: TEXT.tertiary }}>{r.k}</span>
                  <span className="font-mono" style={{ color: r.c }}>
                    {r.v}
                  </span>
                </div>
              ))}
            </div>
            <div
              className="mt-1.5 h-px overflow-hidden rounded-full"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              <div
                className="h-full"
                style={{ width: '38%', background: 'linear-gradient(90deg, #c45a4a, #c8953c)' }}
              />
            </div>
            <div className="flex justify-between mt-px">
              <span className="text-[7px]" style={{ color: TEXT.muted }}>
                Resolution
              </span>
              <span className="text-[7px] font-mono" style={{ color: TEXT.tertiary }}>
                38%
              </span>
            </div>
          </div>
        </div>

        <div className="px-3 py-2" style={{ borderTop: `1px solid ${BORDER.subtle}` }}>
          <div
            className="flex items-center gap-1.5 text-[8px] mb-1.5"
            style={{ color: TEXT.muted }}
          >
            <Zap className="w-2.5 h-2.5" />
            <span className="font-mono tracking-wide">SZL Business OS</span>
          </div>
          <div className="flex gap-1">
            {[
              { label: 'DOMAINE', href: '/terra/', color: '#a07848' },
              { label: 'Counsel', href: '/continuum', color: '#4B8BDB' },
              { label: 'SEXTANT', href: '/vessels/', color: '#38bdf8' },
            ].map((p) => (
              <a
                key={p.label}
                href={p.href}
                className="text-[7px] px-1 py-px rounded font-mono hover:opacity-80"
                style={{
                  color: p.color,
                  background: `${p.color}10`,
                  border: `1px solid ${p.color}18`,
                }}
              >
                {p.label}
              </a>
            ))}
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {isLiveDemoActive && (
          <div
            className="flex items-center justify-center gap-2.5 py-1 text-[9px] font-mono uppercase tracking-widest shrink-0"
            style={{
              background: 'rgba(212,160,84,0.12)',
              borderBottom: '1px solid rgba(212,160,84,0.25)',
              color: '#d4a054',
            }}
            role="status"
            aria-live="polite"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
                style={{ background: '#d4a054' }}
              />
              <span
                className="relative inline-flex rounded-full h-1.5 w-1.5"
                style={{ background: '#d4a054' }}
              />
            </span>
            <span>Demo Mode — Synthetic data only · No live systems connected</span>
            <span
              className="px-1.5 py-px rounded font-bold"
              style={{
                background: 'rgba(212,160,84,0.15)',
                border: '1px solid rgba(212,160,84,0.3)',
              }}
            >
              SEEDED
            </span>
          </div>
        )}
        <header
          className="h-10 flex items-center justify-between px-3 md:px-4 shrink-0 z-10"
          style={{
            borderBottom: `1px solid ${isLiveDemoActive ? 'rgba(212,160,84,0.15)' : BORDER.subtle}`,
            background: isLiveDemoActive ? 'rgba(212,160,84,0.03)' : BG.header,
            backdropFilter: 'blur(8px)',
          }}
        >
          <div className="flex items-center gap-2.5 text-[10px] font-mono">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-1 rounded hover:bg-white/5 mr-1"
              style={{ color: TEXT.secondary }}
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              aria-expanded={sidebarOpen}
            >
              {sidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
            <span
              className="w-1 h-1 rounded-full animate-pulse hidden sm:block"
              style={{ background: '#c45a4a' }}
              aria-hidden="true"
            />
            <span className="hidden sm:block" style={{ color: '#c45a4a' }}>
              5 Urgent
            </span>
            <span className="hidden sm:block" style={{ color: TEXT.muted }}>
              ·
            </span>
            <span style={{ color: '#c8953c' }}>8 Gaps</span>
            <span className="hidden sm:block" style={{ color: TEXT.muted }}>
              ·
            </span>
            <span className="hidden sm:block" style={{ color: '#d4a054' }}>
              $5.03M at risk
            </span>
            {isDemoMode && !isLiveDemoActive && (
              <span className="hidden sm:flex items-center ml-1 gap-1">
                <span style={{ color: TEXT.muted }}>·</span>
                <EnvironmentLabel environment="demo" />
                <EnvironmentLabel environment="seeded" />
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <RealtimeStatusIndicator status={wsStatus} compact />
            <button
              className="relative p-1 rounded hover:bg-white/5 transition-colors"
              style={{ color: TEXT.secondary }}
              aria-label="Notifications"
            >
              <Bell className="w-3.5 h-3.5" />
              <span
                className="absolute top-0.5 right-0.5 w-1 h-1 rounded-full animate-pulse"
                style={{ background: '#d4a054' }}
                aria-hidden="true"
              />
            </button>
            <div className="h-4 w-px" style={{ background: BORDER.subtle }} />
            <div className="flex items-center gap-2">
              <div className="text-right hidden sm:block">
                <div className="text-[10px] font-medium" style={{ color: TEXT.primary }}>
                  Stephen Lutar
                </div>
                <div className="text-[8px] font-mono" style={{ color: 'rgba(212,160,84,0.45)' }}>
                  SZL Holdings
                </div>
              </div>
              <div
                className="w-6 h-6 rounded flex items-center justify-center text-[9px] font-bold"
                style={{
                  background: 'rgba(212,160,84,0.1)',
                  border: `1px solid rgba(212,160,84,0.15)`,
                  color: '#d4a054',
                }}
              >
                SL
              </div>
            </div>
          </div>
        </header>
        <main
          id="main-content"
          className="flex-1 overflow-auto"
          style={{ background: BG.main }}
        >
          <SectionErrorBoundary sectionName="KORA">{children}</SectionErrorBoundary>
        </main>
        <ServiceStatusRail />
      </div>
      <OnboardingWizard config={COMMAND_ONBOARDING_CONFIG} />
    </div>
  );
}
