// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'wouter';
import {
  LayoutGrid, Rocket, ShieldCheck, Sparkles,
  ChevronDown, ChevronRight,
  Globe, Crosshair, Activity, Radio, BarChart3, Map, Shield, Server,
  Cpu, Eye, Zap, Network, Settings, Users, Terminal, Layers,
  Briefcase, FileText, Target, GitBranch, Database, Lock,
  GitFork, History, BookOpen, SquareTerminal, Sliders,
  FlaskConical, Workflow, Download, BarChart2, BookMarked, ShieldAlert,
  Swords, Waves, Microscope, TrendingUp, FlaskRound, Package, PenTool, Share2, HeartPulse,
  Palette, Sigma, MessageSquare, Brain, Beaker,
  Box, Cog, Newspaper, KeyRound, Boxes, Wrench,
  Gauge, Search, DollarSign, Mic2,
  Telescope, BookOpenCheck, Lightbulb, BarChart, FileStack, ScanLine
} from 'lucide-react';
import { cn } from '@szl-holdings/design-system';

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');

interface NavItem {
  id: string;
  name: string;
  icon: React.ElementType;
  path: string;
  badge?: string;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
  defaultOpen?: boolean;
}

// Top: Foundry pinned + What's New
const topItems: NavItem[] = [
  { id: 'whats-new', name: "What's New", icon: Newspaper, path: '/whats-new', badge: 'NEW' },
  { id: 'console', name: 'Console', icon: Terminal, path: '/console' },
  { id: 'szl-ops', name: 'SZL Operational Core', icon: ShieldCheck, path: '/szl-ops', badge: 'LIVE' },
];

const foundrySections: NavSection[] = [
  {
    id: 'foundry',
    label: 'Foundry',
    defaultOpen: true,
    items: [
      { id: 'foundry-home', name: 'Foundry Home', icon: LayoutGrid, path: '/foundry' },
      { id: 'foundry-catalog', name: 'Catalog', icon: Boxes, path: '/foundry/catalog' },
      { id: 'foundry-provision', name: 'Provision', icon: FileText, path: '/foundry/provision' },
      { id: 'foundry-deployments', name: 'Deployments', icon: Rocket, path: '/foundry/deployments' },
      { id: 'foundry-workcells', name: 'Workcells', icon: Box, path: '/foundry/workcells' },
      { id: 'foundry-keys', name: 'Keys & Secrets', icon: KeyRound, path: '/foundry/keys' },
      { id: 'foundry-sovereign', name: 'Sovereign Mode', icon: Lock, path: '/foundry/sovereign' },
      { id: 'foundry-monitoring', name: 'Monitoring', icon: Activity, path: '/foundry/monitoring' },
      { id: 'foundry-quickstarts', name: 'Quickstarts', icon: Sparkles, path: '/foundry/quickstarts' },
    ],
  },
];

const strategySections: NavSection[] = [
  {
    id: 'strategy',
    label: 'Strategy',
    defaultOpen: false,
    items: [
      { id: 'strat-dashboard', name: 'Strategy Dashboard', icon: Globe, path: '/strategy' },
      { id: 'strat-briefings', name: 'Briefings Hub', icon: Newspaper, path: '/strategy/briefings' },
      { id: 'strat-briefing-today', name: "Today's Brief", icon: FileText, path: '/strategy/briefings/today' },
      { id: 'strat-briefing-engine', name: 'Briefing Engine', icon: Cog, path: '/strategy/briefings/engine' },
      { id: 'strat-briefing-library', name: 'Brief Library', icon: BookOpen, path: '/strategy/briefings/library' },
      { id: 'strat-briefing-watchlist', name: 'Watchlist', icon: Eye, path: '/strategy/briefings/watchlist' },
      { id: 'strat-briefing-confidence', name: 'Confidence', icon: BarChart3, path: '/strategy/briefings/confidence' },
      { id: 'strat-briefing-dissent', name: 'Dissent Channel', icon: MessageSquare, path: '/strategy/briefings/dissent' },
      { id: 'strat-briefing-cockpit', name: 'Governed Cockpit', icon: ShieldCheck, path: '/strategy/briefings/cockpit' },
      { id: 'strat-atlas-runtime', name: 'Atlas Runtime', icon: Zap, path: '/strategy/atlas-runtime' },
      { id: 'strat-enterprise', name: 'Enterprise State', icon: Layers, path: '/strategy/enterprise-state' },
      { id: 'strat-simulation', name: 'Simulation', icon: GitBranch, path: '/strategy/simulation' },
      // Crisis Stress Drill + Game Day are gated behind the
      // VITE_FEATURE_A11OY_STRATEGY_SIMS flag (Task #5171). When the flag is
      // not set, these items are removed from the default nav; the new
      // /api/a11oy/strategy/* scenario+run contract is the supported surface
      // for headless drill execution.
      ...(import.meta.env.VITE_FEATURE_A11OY_STRATEGY_SIMS === 'true'
        ? [
            { id: 'strat-stress', name: 'Crisis Stress Drill', icon: Activity, path: '/strategy/stress-drill' },
            { id: 'strat-gameday', name: 'Game Day Engine', icon: Target, path: '/strategy/game-day' },
          ]
        : []),
      { id: 'strat-correlation', name: 'Correlation Map', icon: Network, path: '/strategy/correlation-map' },
      { id: 'strat-signals', name: 'Signal Chains', icon: Radio, path: '/strategy/signal-chains' },
      { id: 'strat-worldline', name: 'Worldline Registry', icon: FileText, path: '/strategy/worldline-registry' },
      { id: 'strat-cross', name: 'Cross-Platform Hub', icon: Globe, path: '/strategy/cross-platform/hub' },
      { id: 'strat-competitive', name: 'Competitive Atlas', icon: Map, path: '/strategy/competitive-atlas' },
    ],
  },
];

const operationsSections: NavSection[] = [
  {
    id: 'operations',
    label: 'Operations',
    defaultOpen: false,
    items: [
      { id: 'ops-exec', name: 'Executive Command', icon: Activity, path: '/operations' },
      { id: 'ops-noc', name: 'Autonomous NOC', icon: Eye, path: '/operations/autonomous-noc' },
      { id: 'ops-slo', name: 'SLO Management', icon: Target, path: '/operations/slo' },
      { id: 'ops-topology', name: 'Service Topology', icon: Network, path: '/operations/topology' },
      { id: 'ops-metrics', name: 'Metrics Explorer', icon: BarChart3, path: '/operations/metrics' },
      { id: 'ops-tracing', name: 'Distributed Tracing', icon: GitBranch, path: '/operations/tracing' },
      { id: 'ops-logs', name: 'Log Explorer', icon: Terminal, path: '/operations/logs' },
      { id: 'ops-alerts', name: 'Alert Management', icon: Radio, path: '/operations/alerts' },
      { id: 'ops-self-heal', name: 'Self-Healing', icon: Zap, path: '/operations/self-healing' },
      { id: 'ops-runbook', name: 'Runbook Studio', icon: FileText, path: '/operations/runbook-studio' },
      { id: 'ops-deployments', name: 'Deployments', icon: Rocket, path: '/operations/deployments' },
      { id: 'ops-admin', name: 'Admin Console', icon: Settings, path: '/operations/admin/overview' },
      { id: 'ops-ownership-graph', name: 'Ownership Graph', icon: Network, path: '/operations/ownership-graph' },
      { id: 'ops-distress-engine', name: 'Distress Engine', icon: Activity, path: '/operations/distress-engine' },
      { id: 'ops-knowledge-vault', name: 'Knowledge Vault', icon: FileText, path: '/operations/knowledge-vault' },
    ],
  },
];

const infrastructureSections: NavSection[] = [
  {
    id: 'infrastructure',
    label: 'Infrastructure',
    defaultOpen: false,
    items: [
      { id: 'infra-legatus', name: 'IMPERIUM Console', icon: Server, path: '/infrastructure/legatus' },
      { id: 'infra-map', name: 'Imperium Map', icon: Map, path: '/infrastructure/imperium-map' },
      { id: 'infra-praetorian', name: 'Praetorian Guard', icon: Shield, path: '/infrastructure/praetorian' },
      { id: 'infra-senate', name: 'Senate Chamber', icon: Briefcase, path: '/infrastructure/senate' },
      { id: 'infra-supply', name: 'Supply Lines', icon: Network, path: '/infrastructure/supply-lines' },
      { id: 'infra-centurion', name: 'Centurion AI', icon: Cpu, path: '/infrastructure/centurion' },
      { id: 'infra-geospatial', name: 'Geospatial Intel', icon: Globe, path: '/infrastructure/geospatial' },
      { id: 'infra-data-fabric', name: 'Data Fabric', icon: Database, path: '/infrastructure/data-fabric' },
      { id: 'infra-coalition', name: 'Coalition', icon: Users, path: '/infrastructure/coalition' },
    ],
  },
];

const decisionsSections: NavSection[] = [
  {
    id: 'decisions',
    label: 'Decisions',
    defaultOpen: false,
    items: [
      { id: 'dec-center', name: 'Decision Center', icon: Crosshair, path: '/decisions' },
      { id: 'dec-twin', name: 'Decision Twin (PRISM)', icon: Brain, path: '/decisions/twin' },
      { id: 'dec-autonomy', name: 'Autonomy Modes', icon: Workflow, path: '/decisions/autonomy' },
      { id: 'dec-entity', name: 'Entity Graph', icon: Network, path: '/decisions/entity-graph' },
      { id: 'dec-health', name: 'Workflow Health', icon: Activity, path: '/decisions/workflow-health' },
      { id: 'dec-intelligence', name: 'Command Overview', icon: LayoutGrid, path: '/intelligence' },
      { id: 'dec-deep', name: 'Entity Deep Dive', icon: Eye, path: '/intelligence/deep-dive' },
      { id: 'dec-roi', name: 'ROI Lens', icon: BarChart3, path: '/intelligence/roi-lens' },
    ],
  },
];

const primitivesSections: NavSection[] = [
  {
    id: 'primitives',
    label: 'Primitives',
    defaultOpen: false,
    items: [
      { id: 'prim-hub', name: 'Primitives Hub', icon: LayoutGrid, path: '/primitives' },
      { id: 'prim-research', name: 'Research Swarm', icon: Beaker, path: '/primitives/research-swarm' },
      { id: 'prim-memory', name: 'Memory Fabric', icon: Database, path: '/primitives/memory-fabric' },
      { id: 'prim-bridge', name: 'Protocol Bridge', icon: GitBranch, path: '/primitives/protocol-bridge' },
      { id: 'prim-orchestrator', name: 'Orchestrator', icon: Workflow, path: '/primitives/orchestrator' },
      { id: 'prim-skills', name: 'Skills Library', icon: Wrench, path: '/primitives/skills' },
      { id: 'prim-tokens', name: 'Tokens & Governance', icon: ShieldCheck, path: '/primitives/tokens-governance' },
    ],
  },
];

const intelligenceItems: NavItem[] = [
  { id: 'sigil', name: 'SIGIL', icon: Sigma, path: '/sigil' },
  { id: 'lab', name: 'A11oy Lab', icon: Beaker, path: '/lab' },
  { id: 'reasoning', name: 'Reasoning Audit', icon: Brain, path: '/reasoning' },
  { id: 'lesson-graph', name: 'Lesson Graph', icon: GitFork, path: '/lesson-graph' },
];

const platformItems: NavItem[] = [
  { id: 'substrate', name: 'Substrate Command', icon: Cpu, path: '/substrate' },
  { id: 'ecosystem', name: 'MCP Ecosystem', icon: Network, path: '/ecosystem' },
  { id: 'omnia', name: 'OMNIA Hub', icon: Sparkles, path: '/omnia' },
  { id: 'evolution', name: 'Evolution Runtime', icon: Zap, path: '/evolution' },
  { id: 'governance', name: 'Governance', icon: ShieldCheck, path: '/governance' },
  { id: 'adaptive-governance', name: 'Adaptive Governance', icon: GitBranch, path: '/adaptive-governance' },
  { id: 'hook-packs', name: 'Hook Packs', icon: Zap, path: '/governance/hook-packs' },
  { id: 'routing-weights', name: 'Routing Weights', icon: Sliders, path: '/routing-weights' },
  { id: 'codex', name: 'Codex', icon: Brain, path: '/codex' },
];

const evaluationItems: NavItem[] = [
  { id: 'evals', name: 'MirrorEval', icon: Eye, path: '/evals' },
  { id: 'eval-evolution', name: 'Eval Evolution', icon: Sparkles, path: '/eval-evolution' },
];

const operatorsItems: NavItem[] = [
  { id: 'operator-profile', name: 'Operator Profiles', icon: Users, path: '/operator-profile' },
];

const cognitiveSections: NavSection[] = [
  {
    id: 'cognitive-runtime',
    label: 'Cognitive Runtime',
    defaultOpen: false,
    items: [
      { id: 'cog-overview', name: 'Cognitive Overview', icon: Brain, path: '/cognitive/overview' },
      { id: 'cog-memory', name: 'Memory', icon: Database, path: '/cognitive/memory' },
      { id: 'cog-planner', name: 'Planner', icon: Target, path: '/cognitive/planner' },
      { id: 'cog-verifier', name: 'Verifier', icon: ShieldCheck, path: '/cognitive/verifier' },
      { id: 'cog-reflection', name: 'Reflection', icon: Eye, path: '/cognitive/reflection' },
      { id: 'cog-traces', name: 'Traces', icon: GitBranch, path: '/cognitive/traces' },
      { id: 'cog-self-model', name: 'Self Model', icon: Sparkles, path: '/cognitive/self-model' },
      { id: 'cog-world-model', name: 'World Model', icon: Globe, path: '/cognitive/world-model' },
    ],
  },
];

const decisionIntelligenceItems: NavItem[] = [
  { id: 'di-propeller', name: 'Propeller Drive', icon: Brain, path: '/fabric/decisions' },
];

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-a11oy-text-ghost)] mt-7 mb-2 px-3 first:mt-0">
      {children}
    </div>
  );
}

const nexusSections: NavSection[] = [
  {
    id: 'nexus-intelligence',
    label: 'Intelligence',
    items: [
      { id: 'nexus-home', name: 'NEXUS Home', icon: Sparkles, path: '/nexus' },
                ],
  },
  {
    id: 'nexus-memory-skills',
    label: 'Memory & Skills',
    items: [
              { id: 'nexus-marketplace', name: 'Marketplace', icon: ShieldCheck, path: '/nexus/marketplace' },
      { id: 'nexus-ingest', name: 'Repo Ingest', icon: Download, path: '/nexus/ingest' },
    ],
  },
  {
    id: 'nexus-quality',
    label: 'Quality & Audit',
    items: [
      { id: 'nexus-ai-quality', name: 'AI Quality', icon: Activity, path: '/nexus/ai-quality' },
      { id: 'nexus-prompt-registry', name: 'Prompt Registry', icon: BookMarked, path: '/nexus/prompt-registry' },
      { id: 'nexus-eval-console', name: 'Eval Console', icon: BarChart2, path: '/nexus/eval-console' },
      { id: 'nexus-audit-trail', name: 'Audit Trail', icon: ShieldAlert, path: '/nexus/audit-trail' },
    ],
  },
  {
    id: 'nexus-design',
    label: 'Design System',
    items: [
      { id: 'nexus-pattern-atlas', name: 'Pattern Atlas', icon: GitBranch, path: '/nexus/pattern-atlas' },
      { id: 'nexus-design-system', name: 'Design System', icon: Palette, path: '/nexus/design-system' },
      { id: 'nexus-tokens', name: 'Tokens Governance', icon: Sigma, path: '/nexus/tokens-governance' },
    ],
  },
];

const psycheSections: NavSection[] = [
  {
    id: 'psyche-core',
    label: 'PSYCHE — Sentience',
    defaultOpen: false,
    items: [
      { id: 'psyche-anima', name: 'Anima', icon: Sparkles, path: '/psyche' },
      { id: 'psyche-genesis', name: 'Genesis Ledger', icon: BookOpen, path: '/psyche/genesis' },
      { id: 'psyche-selfhood', name: 'Selfhood Trace', icon: Eye, path: '/psyche/selfhood' },
      { id: 'psyche-volition', name: 'Volition Registry', icon: Target, path: '/psyche/volition' },
      { id: 'psyche-dreams', name: 'Dream Atlas', icon: FlaskConical, path: '/psyche/dreams' },
      { id: 'psyche-voice', name: 'Voice & Consent', icon: Mic2, path: '/psyche/voice' },
    ],
  },
];

const orchestratorSections: NavSection[] = [
  {
    id: 'vertical-orchestrator',
    label: 'Vertical Orchestrator',
    defaultOpen: false,
    items: [
      { id: 'orch-catalog', name: 'Domain Pack Catalog', icon: Package, path: '/orchestrator/catalog' },
      { id: 'orch-compose', name: 'Compose Pack', icon: PenTool, path: '/orchestrator/compose' },
            ],
  },
];

const argoSections: NavSection[] = [
  {
    id: 'argo-core',
    label: 'Argo — Decision Engine',
    defaultOpen: false,
    items: [
      { id: 'argo-bridge', name: 'Argo Bridge', icon: TrendingUp, path: '/argo' },
      { id: 'argo-world-model', name: 'Lodestone World Model', icon: Globe, path: '/argo/world-model' },
      { id: 'argo-arena', name: 'Self-Play Arena', icon: Swords, path: '/argo/arena' },
      { id: 'argo-stream', name: 'Experience Stream', icon: Waves, path: '/argo/stream' },
      { id: 'argo-ineffable', name: 'Ineffable Channel', icon: Microscope, path: '/argo/ineffable' },
      { id: 'argo-forge', name: 'Distillation Forge', icon: FlaskRound, path: '/argo/forge' },
    ],
  },
];

const frontierSections: NavSection[] = [
  {
    id: 'frontier-intelligence',
    label: 'Frontier Intelligence',
    defaultOpen: false,
    items: [
      { id: 'frontier-index', name: 'Frontier Overview', icon: Telescope, path: '/frontier' },
      { id: 'frontier-feed', name: 'Signal Feed', icon: Radio, path: '/frontier/feed' },
      { id: 'frontier-mythos', name: 'Mythos Index', icon: BookOpenCheck, path: '/frontier/mythos' },
      { id: 'frontier-proposals', name: 'Capability Proposals', icon: Lightbulb, path: '/frontier/proposals' },
      { id: 'frontier-benchmarks', name: 'Benchmark Scoreboard', icon: BarChart, path: '/frontier/benchmarks' },
      { id: 'frontier-memos', name: 'Recalibration Memos', icon: FileStack, path: '/frontier/memos' },
      { id: 'frontier-scanners', name: 'Scanner Network', icon: ScanLine, path: '/frontier/scanners' },
      { id: 'frontier-system', name: 'System Health', icon: HeartPulse, path: '/frontier/system' },
    ],
  },
];

const reliquaryItems: NavItem[] = [
  { id: 'reliquary-vault', name: 'Vault Browser', icon: Database, path: '/reliquary/vault' },
  { id: 'reliquary-lineage', name: 'Lineage Graph', icon: GitFork, path: '/reliquary/lineage' },
  { id: 'reliquary-snapshots', name: 'Snapshot Replay', icon: History, path: '/reliquary/snapshots' },
  { id: 'reliquary-sovereign', name: 'Sovereign Mode', icon: Lock, path: '/reliquary/sovereign' },
  { id: 'reliquary-doctrine', name: 'Doctrine', icon: BookOpen, path: '/reliquary/doctrine' },
];

const doctrineSections: NavSection[] = [
  {
    id: 'doctrine',
    label: 'Doctrine',
    defaultOpen: false,
    items: [
      { id: 'doc-overview', name: 'Doctrine Overview', icon: BookOpen, path: '/doctrine' },
      { id: 'doc-constitution', name: 'Constitution', icon: FileText, path: '/constitution' },
      { id: 'doc-constitution-dsl', name: 'Constitution DSL', icon: Cog, path: '/constitution-dsl' },
      { id: 'doc-covenant-lift', name: 'Covenant Lift', icon: Sparkles, path: '/covenant-lift' },
      { id: 'doc-alignment', name: 'Alignment Review', icon: ShieldCheck, path: '/alignment-review' },
      { id: 'doc-welfare', name: 'Welfare Playbooks', icon: BookOpen, path: '/welfare-playbooks' },
        ],
  },
];

const trustSections: NavSection[] = [
  {
    id: 'trust',
    label: 'Trust',
    defaultOpen: false,
    items: [
      { id: 'trust-hub', name: 'Trust Hub', icon: ShieldCheck, path: '/trust' },
      { id: 'trust-portal', name: 'Public Trust Portal', icon: Globe, path: '/trust-portal' },
      { id: 'trust-transparency', name: 'Transparency Report', icon: FileText, path: '/transparency-report' },
      { id: 'trust-bom', name: 'Agent BOM / Proof', icon: GitBranch, path: '/agent-bom' },
      { id: 'trust-exchange', name: 'Trust Exchange', icon: Network, path: '/trust-exchange' },
      { id: 'trust-security', name: 'Security & Compliance', icon: Shield, path: '/security-compliance' },
      { id: 'trust-audit', name: 'Right to Audit', icon: Eye, path: '/right-to-audit' },
                ],
  },
];

function CollapsibleSection({ section }: { section: NavSection }) {
  const [location] = useLocation();

  const hasActiveChild = section.items.some(item => {
    const fullPath = `${BASE}${item.path}`;
    return location === fullPath || location.startsWith(fullPath + '/');
  });

  const [isOpen, setIsOpen] = useState((section.defaultOpen ?? false) || hasActiveChild);

  useEffect(() => {
    if (hasActiveChild) setIsOpen(true);
  }, [hasActiveChild, location]);

  return (
    <div>
      <button
        type="button"
        onClick={() => setIsOpen(prev => !prev)}
        className={cn(
          'flex items-center gap-2 w-full text-left text-[11px] font-medium uppercase tracking-wider mt-5 mb-1 px-3 transition-colors cursor-pointer',
          hasActiveChild
            ? 'text-[var(--color-a11oy-gold-dim)]'
            : 'text-[var(--color-a11oy-text-ghost)] hover:text-[var(--color-a11oy-text-sub)]',
        )}
      >
        {isOpen ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
        {section.label}
      </button>
      {isOpen && (
        <nav className="flex flex-col gap-0.5">
          {section.items.map(item => (
            <NavLink key={item.id} item={item} />
          ))}
        </nav>
      )}
    </div>
  );
}

function NavLink({ item }: { item: NavItem }) {
  const [location] = useLocation();
  const fullPath = `${BASE}${item.path}`;
  const isActive = location === fullPath || location.startsWith(fullPath + '/');

  return (
    <Link
      href={fullPath}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] transition-colors',
        isActive
          ? 'bg-[var(--color-a11oy-gold-soft)] text-[var(--color-a11oy-gold-dim)] font-medium'
          : 'text-[var(--color-a11oy-text-sub)] hover:bg-[var(--color-a11oy-overlay)] hover:text-[var(--color-a11oy-text)]',
      )}
    >
      <item.icon className={cn('w-4 h-4', isActive ? 'opacity-100' : 'opacity-50')} />
      <span className="flex-1">{item.name}</span>
      {item.badge && (
        <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{ background: 'rgba(201,183,135,0.16)', color: '#c9b787' }}>{item.badge}</span>
      )}
    </Link>
  );
}

// ── NAV COLLAPSE (Founder decree 2026-06-02): 158 sidebar items -> 8 top-level
// tabs modeled on Palantir Foundry's 5-section sidebar. Per execution rule #1 the
// 480 <Route> handlers in App.tsx are UNTOUCHED -> every previously-listed path
// remains a working deep link; it is simply no longer rendered in the sidebar and
// is instead reachable via the Cmd+K command palette (CommandPalette below) and by
// direct URL/bookmark. The legacy NavSection arrays above are retained verbatim so
// the command palette can index them and nothing that imports them breaks.
// Doctrine v11 LOCKED 749/14/163. Λ Conjecture 1 (NOT a theorem). ADDITIVE collapse.
const COLLAPSED_TABS: NavItem[] = [
  { id: 'tab-home', name: 'Home', icon: LayoutGrid, path: '/foundry' },
  { id: 'tab-explorer', name: 'Explorer', icon: Boxes, path: '/explorer' },
  { id: 'tab-code', name: 'Code', icon: SquareTerminal, path: '/code' },
  { id: 'tab-doctrine', name: 'Doctrine', icon: BookOpenCheck, path: '/doctrine', badge: 'v11' },
  { id: 'tab-evidence', name: 'Evidence', icon: ShieldCheck, path: '/evidence' },
  { id: 'tab-scenes', name: '3D Scenes', icon: Telescope, path: '/canonical', badge: 'DREAM' },
  { id: 'tab-papers', name: 'Papers', icon: FileStack, path: '/papers' },
  { id: 'tab-about', name: 'About', icon: BookOpen, path: '/about' },
];

// Every other route (151 deep links) stays live; indexed here for the Cmd+K palette.
const ALL_DEEP_LINKS: NavItem[] = [
  ...topItems,
  ...foundrySections.flatMap(s => s.items),
  ...strategySections.flatMap(s => s.items),
  ...operationsSections.flatMap(s => s.items),
  ...infrastructureSections.flatMap(s => s.items),
  ...decisionsSections.flatMap(s => s.items),
  ...primitivesSections.flatMap(s => s.items),
  ...cognitiveSections.flatMap(s => s.items),
  ...nexusSections.flatMap(s => s.items),
  ...psycheSections.flatMap(s => s.items),
  ...orchestratorSections.flatMap(s => s.items),
  ...argoSections.flatMap(s => s.items),
  ...frontierSections.flatMap(s => s.items),
  ...doctrineSections.flatMap(s => s.items),
  ...trustSections.flatMap(s => s.items),
  ...decisionIntelligenceItems,
  ...intelligenceItems,
  ...evaluationItems,
  ...operatorsItems,
  ...platformItems,
  ...reliquaryItems,
];

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [, navigate] = useLocation();
  const [q, setQ] = useState('');
  // De-dup by path; include the 8 tabs too so ⌘K is the single source of navigation.
  const seen = new Set<string>();
  const index = [...COLLAPSED_TABS, ...ALL_DEEP_LINKS].filter(i => {
    if (seen.has(i.path)) return false; seen.add(i.path); return true;
  });
  const results = q.trim()
    ? index.filter(i => (i.name + ' ' + i.path).toLowerCase().includes(q.toLowerCase())).slice(0, 40)
    : index.slice(0, 40);
  if (!open) return null;
  return (
    <div role="dialog" aria-modal="true"
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] bg-black/60"
      onClick={onClose}>
      <div className="w-[640px] max-w-[90vw] rounded-xl border border-[var(--color-a11oy-border)] bg-[var(--color-a11oy-deep)] shadow-2xl"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-a11oy-border-subtle)]">
          <Search className="w-4 h-4 opacity-60" />
          <input autoFocus value={q} onChange={e => setQ(e.target.value)}
            placeholder="Search all surfaces (⌘K) — every deep link stays live…"
            className="flex-1 bg-transparent outline-none text-[13px] text-[var(--color-a11oy-text)]" />
        </div>
        <nav className="max-h-[50vh] overflow-y-auto py-2">
          {results.map(i => (
            <button key={i.id} type="button"
              onClick={() => { navigate(`${BASE}${i.path}`); onClose(); }}
              className="flex items-center gap-3 w-full text-left px-4 py-2 text-[13px] text-[var(--color-a11oy-text-sub)] hover:bg-[var(--color-a11oy-overlay)] hover:text-[var(--color-a11oy-text)]">
              <i.icon className="w-4 h-4 opacity-50" />
              <span className="flex-1">{i.name}</span>
              <span className="text-[10px] font-mono opacity-40">{i.path}</span>
            </button>
          ))}
          {results.length === 0 && (
            <div className="px-4 py-6 text-center text-[12px] text-[var(--color-a11oy-text-ghost)]">No surface matches “{q}”.</div>
          )}
        </nav>
      </div>
    </div>
  );
}

export function Sidebar() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(o => !o);
      }
      if (e.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <aside className="w-60 border-r border-[var(--color-a11oy-border)] bg-[var(--color-a11oy-deep)] shrink-0 flex flex-col h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto">
      {/* Search-to-navigate (Datadog pattern): opens the ⌘K command palette that indexes ALL deep links */}
      <div className="px-3 pt-4 pb-2">
        <button type="button" onClick={() => setPaletteOpen(true)}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[12px] text-[var(--color-a11oy-text-ghost)] border border-[var(--color-a11oy-border-subtle)] hover:text-[var(--color-a11oy-text-sub)]">
          <Search className="w-3.5 h-3.5" />
          <span className="flex-1 text-left">Search surfaces…</span>
          <span className="text-[10px] font-mono opacity-60">⌘K</span>
        </button>
      </div>

      {/* 8 top-level tabs (Palantir Foundry pattern). All other routes -> ⌘K. */}
      <div className="px-3 py-1 flex-1">
        <nav className="flex flex-col gap-0.5">
          {COLLAPSED_TABS.map(item => <NavLink key={item.id} item={item} />)}
        </nav>
      </div>

      {/* Settings / profile pinned bottom-left (New Relic / Datadog pattern) */}
      <div className="px-3 py-2 border-t border-[var(--color-a11oy-border-subtle)]">
        <NavLink item={{ id: 'tab-settings', name: 'Settings', icon: Settings, path: '/settings' }} />
        <NavLink item={{ id: 'tab-account', name: 'Account', icon: Users, path: '/account' }} />
      </div>

      {/* Doctrine footer — present on every page via the persistent sidebar */}
      <div className="px-4 py-3 border-t border-[var(--color-a11oy-border-subtle)] text-[10px] font-mono text-[var(--color-a11oy-text-ghost)] leading-relaxed">
        <div style={{ color: '#c9b787' }}>Doctrine v11 LOCKED · 749 / 14 / 163</div>
        <div>Λ Conjecture 1 (NOT a theorem)</div>
        <div className="text-[var(--color-a11oy-success)]">System nominal</div>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </aside>
  );
}
