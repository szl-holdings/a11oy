import { UsageIndicator } from '@szl-holdings/shared-ui/billing';
import { AnalyticsProvider } from '@szl-holdings/shared-ui/analytics-provider';
import { AppModeBanner, AppModeProvider } from '@szl-holdings/shared-ui/app-mode-banner';
import {
  type CommandItem,
  CommandPalette,
  createBaselineWebActions,
  getEcosystemSwitchCommands,
  useCommandPalette,
} from '@szl-holdings/shared-ui/command-palette';
import {
  DashboardShell as SharedDashboardShell,
  SidebarNav,
  type SidebarNavSection,
} from '@szl-holdings/shared-ui/design-system';
import { EcosystemNav } from '@szl-holdings/shared-ui/ecosystem-nav';
import {
  type SentientAction,
  type SentientCrossLink,
  SentientLayer,
  type SentientUpdate,
  useSentientLayer,
} from '@szl-holdings/shared-ui/sentient-layer';
import { Toaster } from '@szl-holdings/shared-ui/ui/sonner';
import { useSessionRevocationToast } from '@szl-holdings/shared-ui/use-session-revocation-toast';
import {
  useEffectiveAccent,
  useUserPreferences,
} from '@szl-holdings/shared-ui/use-user-preferences';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  BookLock,
  BookOpen,
  Bot,
  Brain,
  Sigma,
  Briefcase,
  Bug,
  Cpu,
  CheckCircle2,
  Crosshair,
  Database,
  Eye,
  FileText,
  Filter,
  Fingerprint,
  FlaskConical,
  Gauge,
  GitBranch,
  GitMerge,
  Globe,
  KeyRound,
  Landmark,
  Layers,
  LayoutDashboard,
  Lightbulb,
  Lock,
  Menu,
  Microscope,
  Network,
  Plug,
  Presentation,
  Radio,
  RotateCcw,
  Scale,
  Search,
  Server,
  Settings as SettingsIcon,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Swords,
  Target,
  Terminal,
  TrendingUp,
  Trophy,
  Users,
  Workflow,
  Zap,
  Sparkles,
  Atom,
  CircuitBoard,
  Dna,
  Telescope,
  Smartphone,
  Waves,
  Inbox,
} from 'lucide-react';
import {
  type ComponentType,
  lazy,
  type ReactNode,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Link, Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import AllSlides from '@/pages/slides/AllSlides';
import PresenterMode from '@/pages/slides/PresenterMode';
import S01Cover from '@/pages/slides/S01Cover';
import S02SeriesProblem from '@/pages/slides/S02SeriesProblem';
import S03Category from '@/pages/slides/S03Category';
import S04Product from '@/pages/slides/S04Product';
import S05Demo from '@/pages/slides/S05Demo';
import S06Market from '@/pages/slides/S06Market';
import S07SeriesDomains from '@/pages/slides/S07SeriesDomains';
import S08BusinessModel from '@/pages/slides/S08BusinessModel';
import S08DividerMoat from '@/pages/slides/S08DividerMoat';
import S09Ask from '@/pages/slides/S09Ask';
import S13DividerVerdict from '@/pages/slides/S13DividerVerdict';

const SLIDES = [
  S01Cover, S02SeriesProblem, S03Category, S04Product, S05Demo,
  S08DividerMoat, S06Market, S07SeriesDomains, S13DividerVerdict,
  S08BusinessModel, S09Ask,
];
const TOTAL = SLIDES.length;

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 60000, retry: 1 } },
});

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
const SENTRA_BRAND_ACCENT = '#c9b787';

type LazyComp = ReturnType<typeof lazy>;
type IconComp = ComponentType<{ className?: string }>;

type NavItem = {
  path: string;
  label: string;
  icon: IconComp;
  comp: LazyComp;
  hideFromSidebar?: boolean;
};

type NavSection = {
  id: string;
  label: string;
  items: NavItem[];
};

const L = (importer: () => Promise<{ default: ComponentType<unknown> }>): LazyComp =>
  lazy(importer);

const NAV_SECTIONS: NavSection[] = [
  {
    id: 'os-layer',
    label: 'OS Layer',
    items: [
      { path: '/decision-center', label: 'Decision Center', icon: Zap, comp: L(() => import('@/pages/decision-center')) },
    ],
  },
  {
    id: 'loop-layer',
    label: 'Loop Layer',
    items: [
      { path: '/recursive-threat-modeler', label: 'Recursive Threat Modeler', icon: RotateCcw, comp: L(() => import('@/pages/recursive-threat-modeler')) },
    ],
  },
  {
    id: 'sigil',
    label: 'SIGIL',
    items: [
      { path: '/sigil', label: 'SIGIL · Σ', icon: Sigma, comp: L(() => import('@/pages/sigil')) },
    ],
  },
  {
    id: 'core',
    label: 'Core',
    items: [
      { path: '/overwatch-r0513', label: 'R0513 OVERWATCH', icon: Eye, comp: L(() => import('@/pages/overwatch-r0513')) },
      { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, comp: L(() => import('@/pages/dashboard')) },
      { path: '/threats', label: 'Threat Overview', icon: ShieldAlert, comp: L(() => import('@/pages/threat-overview')) },
      { path: '/assets', label: 'Asset Risk Graph', icon: Cpu, comp: L(() => import('@/pages/asset-risk-graph')) },
      { path: '/recovery', label: 'Recovery Readiness', icon: RotateCcw, comp: L(() => import('@/pages/recovery-readiness')) },
      { path: '/incident', label: 'Incident Commander', icon: Activity, comp: L(() => import('@/pages/incident-commander')) },
      { path: '/remediation', label: 'Remediation Pipeline', icon: Sparkles, comp: L(() => import('@/pages/remediation-pipeline')) },
      { path: '/exposure', label: 'Exposure Board', icon: BarChart3, comp: L(() => import('@/pages/exposure-board')) },
      { path: '/controls', label: 'Control Drift', icon: ShieldCheck, comp: L(() => import('@/pages/control-drift')) },
      { path: '/resilience', label: 'Resilience Scorecard', icon: Shield, comp: L(() => import('@/pages/resilience-scorecard')) },
      { path: '/emulation-scorecard', label: 'Emulation Scorecards', icon: Shield, comp: L(() => import('@/pages/emulation-scorecard')) },
      { path: '/forecast', label: 'Forecast', icon: TrendingUp, comp: L(() => import('@/pages/forecast')) },
      { path: '/predictive-engine', label: 'Predictive Threat Engine', icon: Gauge, comp: L(() => import('@/pages/predictive-threat-engine')) },
    ],
  },
  {
    id: 'soc',
    label: 'SOC Operations',
    items: [
      { path: '/soc', label: 'SOC Dashboard', icon: Shield, comp: L(() => import('@/pages/soc-dashboard')) },
      { path: '/agentic-soc', label: 'Agentic SOC', icon: Bot, comp: L(() => import('@/pages/agentic-soc')) },
      { path: '/autonomous-soc', label: 'Autonomous SOC Command', icon: Brain, comp: L(() => import('@/pages/autonomous-soc-command')) },
      { path: '/ai-swarm-defense', label: 'AI Swarm Defense', icon: Shield, comp: L(() => import('@/pages/ai-swarm-defense')) },
      { path: '/alerts', label: 'Alerts', icon: AlertTriangle, comp: L(() => import('@/pages/alerts')) },
      { path: '/incidents', label: 'Incidents', icon: Bug, comp: L(() => import('@/pages/incidents-page')) },
      { path: '/investigations', label: 'Investigations', icon: Search, comp: L(() => import('@/pages/investigations-board')) },
      { path: '/cases', label: 'Cases', icon: Briefcase, comp: L(() => import('@/pages/cases-page')) },
      { path: '/aegis/cps-command', label: 'CPS Executive Command', icon: Landmark, comp: L(() => import('@/pages/aegis-cps-executive')) },
      { path: '/findings', label: 'Findings', icon: Target, comp: L(() => import('@/pages/findings-page')) },
      { path: '/detector-framework', label: 'Detector Framework', icon: Target, comp: L(() => import('@/pages/detector-framework')) },
      { path: '/action-queue', label: 'Action Queue', icon: Zap, comp: L(() => import('@/pages/action-queue')) },
      { path: '/forensics', label: 'Forensics Timeline', icon: Microscope, comp: L(() => import('@/pages/forensics-timeline')) },
      { path: '/deception-grid', label: 'Deception Grid', icon: Filter, comp: L(() => import('@/pages/deception-grid')) },
      { path: '/identity-threat', label: 'Identity Threat', icon: Fingerprint, comp: L(() => import('@/pages/identity-threat')) },
      { path: '/identity-blast-radius', label: 'Identity Blast Radius', icon: ShieldAlert, comp: L(() => import('@/pages/identity-blast-radius')) },
      { path: '/ot-ics', label: 'OT / ICS', icon: Cpu, comp: L(() => import('@/pages/ot-ics-dashboard')) },
      { path: '/sentinel-duel', label: 'Sentinel Duel', icon: Swords, comp: L(() => import('@/pages/sentinel-duel')) },
      { path: '/response-queue', label: 'Response Queue', icon: Inbox, comp: L(() => import('@/pages/response-queue')) },
      { path: '/evidence-ledger', label: 'Evidence Ledger', icon: BookLock, comp: L(() => import('@/pages/evidence-ledger')) },
    ],
  },
  {
    id: 'intelligence',
    label: 'Threat Intelligence',
    items: [
      { path: '/threat-intelligence', label: 'Threat Intelligence', icon: Brain, comp: L(() => import('@/pages/threat-intelligence')) },
      { path: '/threat-intel-feed', label: 'Intel Feed', icon: Radio, comp: L(() => import('@/pages/threat-intel-feed')) },
      { path: '/threat-graph', label: 'Threat Graph', icon: GitMerge, comp: L(() => import('@/pages/threat-graph')) },
      { path: '/threat-actor', label: 'Threat Actor Profiling', icon: Users, comp: L(() => import('@/pages/threat-actor-profiling')) },
      { path: '/threat-kill-chain', label: 'Kill Chain', icon: Swords, comp: L(() => import('@/pages/threat-kill-chain')) },
      { path: '/threat-hunting', label: 'Threat Hunting', icon: Crosshair, comp: L(() => import('@/pages/threat-hunting')) },
      { path: '/hunt-agents', label: 'Hunt Agents', icon: Bot, comp: L(() => import('@/pages/hunt-agents')) },
      { path: '/adversary', label: 'Adversary Engine', icon: Crosshair, comp: L(() => import('@/pages/adversary-engine')) },
      { path: '/attack-path', label: 'Attack Paths', icon: GitBranch, comp: L(() => import('@/pages/attack-path-viz')) },
      { path: '/mitre', label: 'MITRE ATT&CK', icon: Target, comp: L(() => import('@/pages/mitre-attack-page')) },
      { path: '/predictive', label: 'Predictive Intelligence', icon: TrendingUp, comp: L(() => import('@/pages/predictive-intelligence')) },
      { path: '/breach-cost', label: 'Breach Cost', icon: BarChart3, comp: L(() => import('@/pages/breach-cost-predictor')) },
      { path: '/stix-taxii', label: 'STIX / TAXII', icon: Database, comp: L(() => import('@/pages/stix-taxii')) },
      { path: '/threat-nlp', label: 'ML Threat Correlation', icon: Brain, comp: L(() => import('@/pages/threat-nlp')) },
      { path: '/aef-search', label: 'AEF Knowledge Search', icon: Search, comp: L(() => import('@/pages/aef-knowledge-search')) },
    ],
  },
  {
    id: 'brain',
    label: 'Guard Dog Brain',
    items: [
      { path: '/brain/optimizer',    label: 'Decision Optimizer',  icon: Sigma,        comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainOptimizerPage }))) },
      { path: '/brain/research',     label: 'Research Library',    icon: FlaskConical, comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainResearchPage }))) },
      { path: '/brain/proofs',       label: 'Proof Ledger',        icon: BookLock,     comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainProofsPage }))) },
      { path: '/brain/constitution', label: 'Constitution',        icon: ShieldCheck,  comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainConstitutionPage }))) },
      { path: '/brain/evolution',    label: 'Evolution Fabric',    icon: Dna,          comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainEvolutionPage }))) },
      { path: '/brain/bench',        label: 'Evidence Bench',      icon: Microscope,   comp: L(() => import('@/pages/brain/brain-routes').then((m) => ({ default: m.BrainBenchPage }))), hideFromSidebar: true },
    ],
  },
  {
    id: 'response',
    label: 'Response & Automation',
    items: [
      { path: '/soar/playbooks', label: 'SOAR Playbooks', icon: BookOpen, comp: L(() => import('@/pages/soar-playbooks')) },
      { path: '/soar/builder', label: 'SOAR Builder', icon: Workflow, comp: L(() => import('@/pages/soar-builder')) },
      { path: '/soar/automation-hub', label: 'SOAR Automation Hub', icon: Workflow, comp: L(() => import('@/pages/soar-automation-hub')) },
      { path: '/response', label: 'Response Orchestration', icon: Zap, comp: L(() => import('@/pages/response-orchestration')) },
      { path: '/watchlists', label: 'Watchlists', icon: Eye, comp: L(() => import('@/pages/watchlists')) },
      { path: '/xdr', label: 'XDR Console', icon: Network, comp: L(() => import('@/pages/xdr-console')) },
      { path: '/xdr-workbench', label: 'XDR Workbench', icon: Terminal, comp: L(() => import('@/pages/xdr-incident-workbench')) },
    ],
  },
  {
    id: 'war-room',
    label: 'War Room & Exercises',
    items: [
      { path: '/crisis-simulator', label: 'Crisis Simulator', icon: Swords, comp: L(() => import('@/pages/crisis-simulator')) },
      { path: '/resilience-leaderboard', label: 'Resilience Leaderboard', icon: Trophy, comp: L(() => import('@/pages/resilience-leaderboard')) },
      { path: '/citadel-war-room', label: 'Citadel War Room', icon: Radio, comp: L(() => import('@/pages/citadel-war-room')) },
      { path: '/citadel-playbooks', label: 'Citadel Playbooks', icon: BookOpen, comp: L(() => import('@/pages/citadel-playbooks')) },
      { path: '/citadel-after-action', label: 'After-Action Report', icon: FileText, comp: L(() => import('@/pages/citadel-after-action')) },
      { path: '/purple-team', label: 'Purple Team', icon: Swords, comp: L(() => import('@/pages/purple-team')) },
      { path: '/scenario-library', label: 'Scenario Library', icon: BookOpen, comp: L(() => import('@/pages/scenario-library')) },
      { path: '/chaos-drills', label: 'Chaos Engineering Drills', icon: Zap, comp: L(() => import('@/pages/chaos-engineering-drills')) },
    ],
  },
  {
    id: 'digital-twin',
    label: 'Digital Twin & ATLAS',
    items: [
      { path: '/threat-twin-view', label: 'Threat Twin', icon: Shield, comp: L(() => import('@/pages/threat-twin-view')) },
      { path: '/mitre-atlas', label: 'MITRE ATLAS Overlay', icon: Layers, comp: L(() => import('@/pages/mitre-atlas-overlay')) },
      { path: '/atlas-runtime', label: 'Threat Mesh', icon: Layers, comp: L(() => import('@/pages/atlas-runtime')) },
      { path: '/atlas-runtime/correlation', label: 'Worldline Correlation', icon: Network, comp: L(() => import('@/pages/atlas-correlation')) },
      { path: '/replay', label: 'Incident Replay', icon: RotateCcw, comp: L(() => import('@/pages/replay')) },
    ],
  },
  {
    id: 'quantum-resilience',
    label: 'Quantum & Microsystem Resilience',
    items: [
      { path: '/quantum/threat-surface', label: 'Quantum Threat Surface', icon: Atom, comp: L(() => import('@/pages/quantum-threat-surface')) },
      { path: '/quantum/supply-chain', label: 'Hardware Supply Chain', icon: CircuitBoard, comp: L(() => import('@/pages/hardware-supply-chain')) },
      { path: '/quantum/microsystem-integrity', label: 'Microsystem Integrity', icon: Fingerprint, comp: L(() => import('@/pages/microsystem-integrity')) },
      { path: '/quantum/photonic-grid', label: 'Photonic & Quantum Sensor Grid', icon: Waves, comp: L(() => import('@/pages/photonic-sensor-grid')) },
      { path: '/quantum/bio-cyber', label: 'Bio-Cyber Convergence', icon: Dna, comp: L(() => import('@/pages/bio-cyber-convergence')) },
      { path: '/quantum/threat-horizon', label: 'DARPA Threat Horizon', icon: Telescope, comp: L(() => import('@/pages/darpa-threat-horizon')) },
    ],
  },
  {
    id: 'agent-mesh',
    label: 'Agent Mesh',
    items: [
      { path: '/mesh/map', label: 'Mesh Map', icon: Network, comp: L(() => import('@/pages/mesh-map')) },
      { path: '/mesh/exposures', label: 'Exposures', icon: Eye, comp: L(() => import('@/pages/mesh-exposures')) },
      { path: '/mesh/containment', label: 'Containment Rules', icon: BookLock, comp: L(() => import('@/pages/containment-rules')) },
      { path: '/mesh/drift', label: 'Mesh Drift', icon: GitBranch, comp: L(() => import('@/pages/mesh-drift')) },
      { path: '/mesh/connectors', label: 'Connectors', icon: Plug, comp: L(() => import('@/pages/mesh-connectors')) },
    ],
  },
  {
    id: 'edr-siem',
    label: 'EDR & SIEM',
    items: [
      { path: '/edr/agents', label: 'Endpoint Mesh', icon: Cpu, comp: L(() => import('@/pages/endpoint-mesh')) },
      { path: '/siem/connections', label: 'SIEM Connections', icon: Zap, comp: L(() => import('@/pages/siem-connections')) },
      { path: '/siem/export', label: 'SIEM Export', icon: ArrowUpRight, comp: L(() => import('@/pages/siem-export')) },
    ],
  },
  {
    id: 'compliance',
    label: 'Compliance & Risk',
    items: [
      { path: '/compliance', label: 'Compliance', icon: ShieldCheck, comp: L(() => import('@/pages/compliance-page')) },
      { path: '/compliance/evidence', label: 'Evidence', icon: FileText, comp: L(() => import('@/pages/compliance-evidence')) },
      { path: '/compliance/control-graph', label: 'Control Graph', icon: GitMerge, comp: L(() => import('@/pages/control-evidence-graph')) },
      { path: '/compliance/audit-chain', label: 'Audit Chain', icon: Lock, comp: L(() => import('@/pages/audit-chain')) },
      { path: '/replay-attestation', label: 'Replay Attestation', icon: ShieldCheck, comp: L(() => import('@/pages/replay-attestation')) },
      { path: '/compliance/zero-trust', label: 'Zero Trust', icon: KeyRound, comp: L(() => import('@/pages/zero-trust-scorecard')) },
      { path: '/compliance/vulnerabilities', label: 'Vulnerabilities', icon: Bug, comp: L(() => import('@/pages/vulnerability-dashboard')) },
      { path: '/compliance/vuln-lifecycle', label: 'Vuln Lifecycle', icon: GitBranch, comp: L(() => import('@/pages/vuln-lifecycle')) },
      { path: '/attack-surface', label: 'Attack Surface Command', icon: Globe, comp: L(() => import('@/pages/attack-surface-command')) },
      { path: '/compliance/assets', label: 'Asset Inventory', icon: Server, comp: L(() => import('@/pages/asset-inventory')) },
      { path: '/compliance/risk-scoring', label: 'Risk Scoring', icon: Gauge, comp: L(() => import('@/pages/risk-scoring')) },
      { path: '/compliance/executive-risk', label: 'Executive Risk', icon: TrendingUp, comp: L(() => import('@/pages/executive-risk')) },
      { path: '/compliance/board-view', label: 'Board View', icon: Landmark, comp: L(() => import('@/pages/executive-board-view')) },
      { path: '/compliance/hardening', label: 'Hardening Controls', icon: ShieldCheck, comp: L(() => import('@/pages/hardening-controls')) },
      { path: '/compliance/governance-review', label: 'Governance Review', icon: Scale, comp: L(() => import('@/pages/governance-review')) },
    ],
  },
  {
    id: 'intel',
    label: 'Research Intelligence',
    items: [
      { path: '/intel/dashboard', label: 'Intel Dashboard', icon: Brain, comp: L(() => import('@/pages/intel/dashboard')) },
      { path: '/intel/experiments', label: 'Experiments', icon: FlaskConical, comp: L(() => import('@/pages/intel/experiments')) },
      { path: '/intel/models', label: 'Models', icon: Layers, comp: L(() => import('@/pages/intel/models')) },
      { path: '/intel/projects', label: 'Projects', icon: GitBranch, comp: L(() => import('@/pages/intel/projects')) },
      { path: '/intel/insights', label: 'Insights', icon: Lightbulb, comp: L(() => import('@/pages/intel/insights')) },
      { path: '/intel/federated-learning', label: 'Federated Learning', icon: Lock, comp: L(() => import('@/pages/federated-learning')) },
      { path: '/intel/darpa-mto', label: 'DARPA MTO Innovation', icon: FlaskConical, comp: L(() => import('@/pages/darpa-mto-hub')) },
      { path: '/intel/pqc-readiness', label: 'PQC Readiness', icon: Lock, comp: L(() => import('@/pages/pqc-readiness')) },
      { path: '/intel/hardware-trust', label: 'Hardware Root of Trust', icon: Cpu, comp: L(() => import('@/pages/hardware-root-of-trust')) },
      { path: '/intel/adversarial-defense', label: 'Adversarial ML Defense', icon: Swords, comp: L(() => import('@/pages/adversarial-defense-console')) },
      { path: '/intel/cyber-roadmap', label: 'Cyber Innovation Roadmap', icon: Microscope, comp: L(() => import('@/pages/cyber-innovation-roadmap')) },
      { path: '/intel/photonic-inference', label: 'Photonic Inference Tier', icon: Zap, comp: L(() => import('@/pages/photonic-inference')) },
      { path: '/intel/threat-feed-health', label: 'Live Feed Health', icon: Activity, comp: L(() => import('@/pages/threat-feed-health')) },
    ],
  },
  {
    id: 'governance',
    label: 'Governance',
    items: [
      { path: '/governed-cockpit', label: 'Governed Intelligence', icon: Shield, comp: L(() => import('@/pages/governed-cockpit')) },
      { path: '/governance/enterprise', label: 'Enterprise Governance', icon: Globe, comp: L(() => import('@/pages/governance/enterprise-governance')) },
      { path: '/governance/executive-reports', label: 'Executive Reports', icon: FileText, comp: L(() => import('@/pages/governance/executive-reports')) },
      { path: '/governance/trust-analytics', label: 'Trust Analytics', icon: ShieldCheck, comp: L(() => import('@/pages/governance/trust-analytics')) },
      { path: '/governance/incident-analytics', label: 'Incident Analytics', icon: BarChart3, comp: L(() => import('@/pages/governance/incident-analytics')) },
      { path: '/governance/agent-config', label: 'Agent Config', icon: SettingsIcon, comp: L(() => import('@/pages/governance/agent-config')) },
      { path: '/governance/ouroboros', label: 'Ouroboros Anchor', icon: Lock, comp: L(() => import('@/pages/ouroboros')) },
      { path: '/thesis', label: 'Ouroboros Thesis (v9 + v10)', icon: BookOpen, comp: L(() => import('@/pages/thesis')) },
      { path: '/multi-fund', label: 'Multi-Fund View', icon: Layers, comp: L(() => import('@/pages/multi-fund-view')) },
      { path: '/reports', label: 'Reports', icon: FileText, comp: L(() => import('@/pages/reports-page')) },
      { path: '/pdf-export', label: 'PDF Export', icon: Presentation, comp: L(() => import('@/pages/aegis-pdf-export')) },
      { path: '/what-changed', label: 'What Changed', icon: Activity, comp: L(() => import('@/pages/aegis-what-changed')) },
      { path: '/enterprise-tiers', label: 'Enterprise Tiers', icon: Landmark, comp: L(() => import('@/pages/aegis-pricing')) },
      { path: '/settings', label: 'Settings', icon: SettingsIcon, comp: L(() => import('@/pages/settings/unified-settings')) },
    ],
  },
  {
    id: 'cps',
    label: 'Cyber Payload Standard',
    items: [
      { path: '/cps/catalog', label: 'CPS Catalog', icon: Shield, comp: L(() => import('@/pages/cps-catalog')) },
      { path: '/cps/runs', label: 'Run History', icon: Activity, comp: L(() => import('@/pages/cps-run-history')) },
      { path: '/cps/approvals', label: 'CPS Approvals', icon: CheckCircle2, comp: L(() => import('@/pages/cps-approvals')) },
      { path: '/cps/executive', label: 'Executive Command', icon: Landmark, comp: L(() => import('@/pages/aegis-cps-executive')) },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { path: '/approvals', label: 'Approvals', icon: Shield, comp: L(() => import('@/pages/approvals')) },
      { path: '/trust', label: 'Trust & Provenance', icon: Lock, comp: L(() => import('@/pages/trust-provenance')) },
      { path: '/mobile', label: 'Mobile Command', icon: Smartphone, comp: L(() => import('@/pages/mobile/mobile-shell')) },
    ],
  },
  {
    id: 'threat-hunter',
    label: 'Threat Hunter',
    items: [
      { path: '/hunt', label: 'Hunt Proposer', icon: Brain, comp: L(() => import('@/pages/hunt')) },
      { path: '/remediation', label: 'Remediation Plans', icon: ShieldCheck, comp: L(() => import('@/pages/remediation-plans')) },
      { path: '/red-team', label: 'Red-Team Library', icon: Crosshair, comp: L(() => import('@/pages/red-team')) },
      { path: '/frontier-ai-lab', label: 'Frontier AI Threat Lab', icon: Brain, comp: L(() => import('@/pages/frontier-ai-threat-lab')) },
      { path: '/weaponized-intel', label: 'Weaponized Intel Feed', icon: Radio, comp: L(() => import('@/pages/weaponized-intel-feed')) },
    ],
  },
  {
    id: 'crisis-arena',
    label: 'Adversarial Simulation',
    items: [
      { path: '/crisis-arena/leaderboard', label: 'Analyst Rankings', icon: Users, comp: L(() => import('@/pages/crisis-arena-leaderboard')) },
      { path: '/crisis-arena/engagements', label: 'Engagements', icon: Activity, comp: L(() => import('@/pages/crisis-arena-engagements')) },
      { path: '/crisis-arena/architect', label: 'Analyst Workspace', icon: Zap, comp: L(() => import('@/pages/crisis-arena-architect')) },
    ],
  },
  {
    id: 'benchmarks',
    label: 'Benchmarks',
    items: [
      { path: '/benchmarks', label: 'Benchmarks & Leaderboards', icon: Trophy, comp: L(() => import('@/pages/benchmarks')) },
    ],
  },
  {
    id: 'predictive-cortex',
    label: 'Predictive Defense Cortex',
    items: [
      { path: '/future-threat-horizon', label: 'Future Threat Horizon', icon: Telescope, comp: L(() => import('@/pages/future-threat-horizon')) },
      { path: '/layered-intercept', label: 'Layered Intercept', icon: Layers, comp: L(() => import('@/pages/layered-intercept')) },
      { path: '/red-team-hub', label: 'Red Team Hub', icon: Crosshair, comp: L(() => import('@/pages/red-team-hub')) },
      { path: '/governed-adversary-loop', label: 'Governed Adversary Loop', icon: GitMerge, comp: L(() => import('@/pages/governed-adversary-loop')) },
      { path: '/a11oy-brain', label: 'a11oy Brain', icon: Brain, comp: L(() => import('@/pages/a11oy-brain-panel')) },
    ],
  },
  {
    id: 'sentra-command',
    label: 'Sentra Command ⬡',
    items: [
      { path: '/command-center', label: 'Command Center', icon: ShieldCheck, comp: L(() => import('@/pages/command-center')) },
      { path: '/asset-registry', label: 'Asset Registry', icon: Server, comp: L(() => import('@/pages/asset-registry')) },
      { path: '/containment-actions', label: 'Containment Actions', icon: Lock, comp: L(() => import('@/pages/containment-actions')) },
      { path: '/evidence-vault', label: 'Evidence Vault', icon: BookLock, comp: L(() => import('@/pages/evidence-vault')) },
      { path: '/approval-queue', label: 'Approval Queue', icon: CheckCircle2, comp: L(() => import('@/pages/approval-queue-sentra')) },
      { path: '/integrations-hub', label: 'Integrations Hub', icon: Plug, comp: L(() => import('@/pages/integrations-hub')) },
      { path: '/reports-generator', label: 'Reports Generator', icon: FileText, comp: L(() => import('@/pages/reports-generator')) },
      { path: '/policy-log', label: 'Policy Enforcement Log', icon: ShieldAlert, comp: L(() => import('@/pages/policy-enforcement-log')) },
      { path: '/audit-trail', label: 'Audit Trail', icon: Database, comp: L(() => import('@/pages/audit-trail-v2')) },
    ],
  },
];

// TAB CAP — Sentra Deep Operational C (2026-06-03)
// Sentra's deliberate surface: Command ⬡ + Guard Dog Brain only.
// Matching landing pills: Verdict, Evidence Vault, Command Center, Audit Trail,
//   Proof Ledger, Constitution, Decision Optimizer, Evolution Fabric, Research Library.
// All 23 sections remain accessible via ⌘K command palette (ALL_ROUTES).
// REVERSIBILITY: restore to NAV_SECTIONS to re-expose all sections instantly.
// Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1 honest
// Signed-off-by: Yachay <yachay@szlholdings.ai>
// Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
const SIDEBAR_SECTION_IDS = new Set([
  'sentra-command',  // Verdict surface, Command Center, Evidence Vault, Audit Trail
  'brain',           // Guard Dog Brain: Proof Ledger, Constitution, Evolution Fabric
]);
const VISIBLE_NAV_SECTIONS = NAV_SECTIONS.filter((s) => SIDEBAR_SECTION_IDS.has(s.id));
// ALL_ROUTES preserves every route for ⌘K palette and direct URL navigation
const ALL_ROUTES: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

const SLIDES_NAV: NavItem = {
  path: '/slides',
  label: 'Investor Deck',
  icon: Presentation,
  comp: L(() => import('@/pages/aegis-home')),
};

const MobileShell = lazy(() => import('@/pages/mobile/mobile-shell'));
const IncidentDetailV2Page = lazy(() => import('@/pages/incident-detail-v2'));
const SentraLandingPage = lazy(() => import('@/pages/sentra-landing'));
const SentraPricingPage = lazy(() => import('@/pages/pricing'));
const SentraBillingPage = lazy(() => import('@/pages/billing-account'));
const CrisisArenaArchitectProfilePage = lazy(() => import('@/pages/crisis-arena-architect-profile'));
const HuntDetailPage = lazy(() => import('@/pages/hunt-detail'));
const CrisisSimulatorRunPage = lazy(() => import('@/pages/crisis-simulator-run'));

// R7 Series-A blocker: aliases for stale hrefs found in pages/components.
const AliasDashboardPage = lazy(() => import('@/pages/dashboard'));
const AliasEnterpriseDemoPage = lazy(() => import('@/pages/enterprise-demo'));
const AliasDecisionConsolePage = lazy(() => import('@/pages/decision-console'));
const AliasTradecraftPage = lazy(() => import('@/pages/tradecraft-engine'));
const AliasXdrConsolePage = lazy(() => import('@/pages/xdr-console'));
const AliasGovEnterprisePage = lazy(() => import('@/pages/governance/enterprise-governance'));
const AliasGovTrustAnalyticsPage = lazy(() => import('@/pages/governance/trust-analytics'));
const AliasMspOpsObservabilityPage = lazy(() => import('@/pages/msp/ops-observability'));
const AliasMspProviderSettingsPage = lazy(() => import('@/pages/msp/provider-settings'));
const AliasWorldlineRegistryPage = lazy(() => import('@/pages/worldline-registry'));
const AliasBenchmarksPage = lazy(() => import('@/pages/benchmarks'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <div className="w-6 h-6 border-2 border-[#f5f5f5]/40 border-t-white rounded-full animate-spin" />
    </div>
  );
}

function renderIcon(Icon: IconComp): ReactNode {
  return <Icon className="w-3.5 h-3.5" />;
}

function buildSidebarSections(): SidebarNavSection[] {
  const intro: SidebarNavSection = {
    id: 'intro',
    items: [
      { id: '/', label: 'Home', href: '/', icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
      { id: SLIDES_NAV.path, label: SLIDES_NAV.label, href: SLIDES_NAV.path, icon: renderIcon(SLIDES_NAV.icon) },
      {
        id: 'a11oy-intelligence',
        label: 'A11oy Intelligence',
        href: '/intelligence/',
        icon: <Sparkles className="w-3.5 h-3.5" />,
      },
    ],
  };
  const sections: SidebarNavSection[] = VISIBLE_NAV_SECTIONS.map((sec) => ({
    id: sec.id,
    label: sec.label,
    items: sec.items
      .filter((item) => !item.hideFromSidebar)
      .map((item) => ({
        id: item.path,
        label: item.label,
        href: item.path,
        icon: renderIcon(item.icon),
      })),
  }));
  return [intro, ...sections];
}

function DashboardRoutes() {
  return (
    <Switch>
      {ALL_ROUTES.map(({ path, comp: Comp }) => (
        <Route key={path} path={path}>
          <Suspense fallback={<PageLoader />}>
            <Comp />
          </Suspense>
        </Route>
      ))}

      <Route path="/incidents/:id">
        <Suspense fallback={<PageLoader />}>
          <IncidentDetailV2Page />
        </Suspense>
      </Route>

      <Route path="/crisis-simulator/:id">
        <Suspense fallback={<PageLoader />}>
          <CrisisSimulatorRunPage />
        </Suspense>
      </Route>
      <Route path="/hunt/:id">
        <Suspense fallback={<PageLoader />}>
          <HuntDetailPage />
        </Suspense>
      </Route>
      <Route path="/crisis-arena/architect/:id">
        <Suspense fallback={<PageLoader />}>
          <CrisisArenaArchitectProfilePage />
        </Suspense>
      </Route>
      <Route path="/pricing">
        <Suspense fallback={<PageLoader />}>
          <SentraPricingPage />
        </Suspense>
      </Route>
      <Route path="/account/billing">
        <Suspense fallback={<PageLoader />}>
          <SentraBillingPage />
        </Suspense>
      </Route>
      {/* R7 Series-A blocker: nav→route aliases. Older pages still
          ship hardcoded hrefs that pre-date the route consolidation. We
          mount each missing path against the real page component instead
          of leaving the user with the "Page not found" wall. */}
      <Route path="/home"><Suspense fallback={<PageLoader />}><AliasDashboardPage /></Suspense></Route>
      <Route path="/demo"><Suspense fallback={<PageLoader />}><AliasEnterpriseDemoPage /></Suspense></Route>
      <Route path="/decision-console"><Suspense fallback={<PageLoader />}><AliasDecisionConsolePage /></Suspense></Route>
      <Route path="/tradecraft"><Suspense fallback={<PageLoader />}><AliasTradecraftPage /></Suspense></Route>
      <Route path="/xdr-console"><Suspense fallback={<PageLoader />}><AliasXdrConsolePage /></Suspense></Route>
      <Route path="/gov/governance"><Suspense fallback={<PageLoader />}><AliasGovEnterprisePage /></Suspense></Route>
      <Route path="/gov/trust-analytics"><Suspense fallback={<PageLoader />}><AliasGovTrustAnalyticsPage /></Suspense></Route>
      <Route path="/msp/ops-console"><Suspense fallback={<PageLoader />}><AliasMspOpsObservabilityPage /></Suspense></Route>
      <Route path="/ops/provider-settings"><Suspense fallback={<PageLoader />}><AliasMspProviderSettingsPage /></Suspense></Route>
      <Route path="/command/strategy/worldline-registry"><Suspense fallback={<PageLoader />}><AliasWorldlineRegistryPage /></Suspense></Route>
      <Route path="/command/open-eval-hub"><Suspense fallback={<PageLoader />}><AliasBenchmarksPage /></Suspense></Route>
      <Route>
        <div className="flex flex-col items-center justify-center h-full p-10 text-center">
          <Shield className="w-10 h-10 text-[#f5f5f5]/50 mb-4" />
          <h1 className="text-xl font-bold text-[#f5f5f5] mb-2">Page not found</h1>
          <p className="text-sm text-[#f5f5f5]/60 mb-6">That route isn't wired up yet.</p>
          <Link href="/" className="text-xs text-[#f5f5f5] hover:text-[#f5f5f5] underline">
            Return home
          </Link>
        </div>
      </Route>
    </Switch>
  );
}

function SentraSidebarContent({
  expanded,
  onMobileClose,
  onToggleCollapse,
}: {
  expanded: boolean;
  onMobileClose?: () => void;
  onToggleCollapse?: () => void;
}) {
  const [location, navigate] = useLocation();
  const accent = useEffectiveAccent(SENTRA_BRAND_ACCENT);
  const sections = buildSidebarSections();

  return (
    <SidebarNav
      sections={sections}
      currentPath={location}
      accentColor={accent}
      collapsed={!expanded}
      onNavigate={(item) => {
        if (item.href) {
          if (item.href.startsWith('/intelligence/') || /^https?:\/\//.test(item.href)) {
            window.open(item.href, '_blank', 'noopener,noreferrer');
          } else {
            navigate(item.href);
          }
        }
        onMobileClose?.();
      }}
      header={
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
            style={{ background: 'rgba(201,183,135,0.08)', border: '1px solid rgba(201,183,135,0.25)' }}
          >
            <Shield className="w-4 h-4 text-[#c9b787]" />
          </div>
          {expanded && (
            <div className="flex-1 min-w-0">
              <h1 className="text-sm font-semibold text-[#f5f5f5] truncate tracking-tight">Sentra</h1>
              <p className="text-[10px] truncate font-mono uppercase tracking-wider text-[#666]">
                Cyber Resilience
              </p>
            </div>
          )}
        </div>
      }
      footer={
        expanded ? (
          <div className="space-y-2">
            <div
              className="rounded-lg px-3 py-2.5"
              style={{
                background: 'rgba(201,183,135,0.03)',
                border: '1px solid rgba(201,183,135,0.1)',
              }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#5a8a6e] animate-pulse" style={{ boxShadow: '0 0 6px rgba(90,138,110,0.5)' }} />
                <span className="text-[9px] font-mono uppercase tracking-wider text-[#666]">
                  a11oy orchestrated
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#666]">Active agents</span>
                  <span className="text-[9px] font-mono text-[#5a8a6e]">12 online</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#666]">Threat posture</span>
                  <span className="text-[9px] font-mono text-[#c9b787]">Guarded</span>
                </div>
              </div>
            </div>
            <UsageIndicator
              featureKey="agent_runs"
              label="Agent usage"
              accentColor="#c9b787"
              billingHref={`${BASE}/account/billing`}
            />
            <button
              onClick={onToggleCollapse}
              className="flex items-center justify-center w-full py-1 text-[10px] rounded transition-colors hover:bg-white/5 text-[#f5f5f5]/40"
              aria-label="Collapse sidebar"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path d="M8 2L5 6l3 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        ) : (
          <button
            onClick={onToggleCollapse}
            className="flex items-center justify-center w-7 h-7 mx-auto rounded transition-colors hover:bg-white/5 text-[#f5f5f5]/40"
            aria-label="Expand sidebar"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M4 2l3 4-3 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )
      }
    />
  );
}

function SlideDeck() {
  function getInitialSlide(): number {
    const match = window.location.pathname.match(/slide(?:s\/)?(\d+)/);
    if (match) {
      const n = parseInt(match[1], 10);
      if (n >= 1 && n <= TOTAL) return n;
    }
    return 1;
  }

  const isEmbed =
    typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('embed') === '1';

  const [current, setCurrent] = useState(getInitialSlide);
  const Slide = SLIDES[current - 1];
  const channelRef = useRef<BroadcastChannel | null>(null);

  const goTo = useCallback(
    (n: number) => {
      const clamped = Math.min(Math.max(n, 1), TOTAL);
      setCurrent(clamped);
      history.replaceState(null, '', `${BASE}/slides/${clamped}${isEmbed ? '?embed=1' : ''}`);
      channelRef.current?.postMessage({ type: 'audience:current', slide: clamped });
    },
    [isEmbed],
  );

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel('sentra-deck-sync');
    channelRef.current = channel;
    channel.onmessage = (ev) => {
      const data = ev.data ?? {};
      if (data.type === 'presenter:goto' && typeof data.slide === 'number') {
        setCurrent((c) => {
          if (c === data.slide) return c;
          history.replaceState(null, '', `${BASE}/slides/${data.slide}${isEmbed ? '?embed=1' : ''}`);
          return data.slide;
        });
      } else if (data.type === 'presenter:hello') {
        setCurrent((c) => {
          channel.postMessage({ type: 'audience:current', slide: c });
          return c;
        });
      }
    };
    channel.postMessage({ type: 'audience:current', slide: current });
    return () => {
      channel.close();
      channelRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEmbed]);

  useEffect(() => {
    if (isEmbed) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'p' || e.key === 'P') {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        e.preventDefault();
        const url = `${BASE}/slides/presenter?slide=${current}`;
        window.open(url, 'sentra-presenter', 'width=1280,height=860,noopener');
        return;
      }
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
        setCurrent((c) => {
          const next = Math.min(c + 1, TOTAL);
          history.replaceState(null, '', `${BASE}/slides/${next}`);
          channelRef.current?.postMessage({ type: 'audience:current', slide: next });
          return next;
        });
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        setCurrent((c) => {
          const prev = Math.max(c - 1, 1);
          history.replaceState(null, '', `${BASE}/slides/${prev}`);
          channelRef.current?.postMessage({ type: 'audience:current', slide: prev });
          return prev;
        });
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div
      style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}
      onClick={() => { if (!isEmbed) goTo(current + 1); }}
    >
      {isEmbed ? (
        <Slide />
      ) : (
        <div
          key={current}
          className="szl-slide-anim"
          data-variant={
            (Slide as { displayName?: string; name?: string }).displayName?.includes('Divider') ||
            (Slide as { displayName?: string; name?: string }).name?.includes('Divider')
              ? 'dramatic'
              : 'default'
          }
        >
          <Slide />
        </div>
      )}
      {!isEmbed && (
        <div
          style={{
            position: 'fixed', bottom: '2.5vh', left: '50%', transform: 'translateX(-50%)',
            display: 'flex', gap: '0.5vw', zIndex: 100,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {SLIDES.map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i + 1)}
              aria-label={`Go to slide ${i + 1}`}
              style={{
                width: i + 1 === current ? '2.2vw' : '0.55vw',
                height: '0.35vh', minHeight: '3px', borderRadius: '2px',
                background: i + 1 === current ? '#f5f5f5' : 'rgba(255,255,255,0.18)',
                border: 'none', cursor: 'pointer', padding: 0,
              }}
            />
          ))}
        </div>
      )}
      {!isEmbed && (
        <Link
          href="/"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', top: '2vh', left: '2vw',
            fontFamily: 'Inter, sans-serif', fontSize: '11px', color: 'rgba(255,255,255,0.4)',
            textDecoration: 'none', padding: '6px 10px',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '6px', zIndex: 100,
          }}
        >
          ← Exit deck
        </Link>
      )}
      {!isEmbed && (
        <div
          style={{ position: 'fixed', top: '2vh', right: '2vw', display: 'flex', gap: 8, zIndex: 100 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={() => {
              const url = `${BASE}/slides/presenter?slide=${current}`;
              window.open(url, 'sentra-presenter', 'width=1280,height=860,noopener');
            }}
            title="Open presenter mode (P)"
            style={{
              fontFamily: 'Inter, sans-serif', fontSize: '11px', color: 'rgba(255,255,255,0.85)',
              padding: '6px 10px', background: 'rgba(138,138,138,0.18)',
              border: '1px solid rgba(138,138,138,0.45)', borderRadius: '6px', cursor: 'pointer',
            }}
          >
            Presenter (P)
          </button>
          <button
            type="button"
            onClick={() => { window.open(`${BASE}/slides/print?print=1`, '_blank', 'noopener'); }}
            title="Export deck as PDF"
            style={{
              fontFamily: 'Inter, sans-serif', fontSize: '11px', color: 'rgba(255,255,255,0.7)',
              padding: '6px 10px', background: 'rgba(245,245,245,0.08)',
              border: '1px solid rgba(245,245,245,0.25)', borderRadius: '6px', cursor: 'pointer',
            }}
          >
            Export PDF
          </button>
        </div>
      )}
      {!isEmbed && (
        <div
          style={{
            position: 'fixed', bottom: '2.5vh', right: '2.5vw',
            fontFamily: 'Inter, sans-serif', fontSize: 'clamp(9px, 1vw, 13px)',
            color: 'rgba(255,255,255,0.18)', zIndex: 100,
          }}
        >
          {current} / {TOTAL}
        </div>
      )}
    </div>
  );
}

function AppShell({
  sidebarOpen,
  setSidebarOpen,
  sidebarCollapsed,
  onToggleCollapse,
  sidebarHovered,
  setSidebarHovered,
}: {
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
  sidebarCollapsed: boolean;
  onToggleCollapse: () => void;
  sidebarHovered: boolean;
  setSidebarHovered: (v: boolean) => void;
}) {
  const [location, navigate] = useLocation();
  const accent = useEffectiveAccent(SENTRA_BRAND_ACCENT);
  const sidebarExpanded = !sidebarCollapsed || sidebarHovered;

  const navCommands: CommandItem[] = ALL_ROUTES.map((item) => ({
    id: `nav-${item.path}`,
    label: item.label,
    group: 'Navigate',
    action: () => navigate(item.path),
  }));

  const paletteCommands: CommandItem[] = [
    ...createBaselineWebActions(navigate),
    ...getEcosystemSwitchCommands('sentra'),
    { id: 'nav-home', label: 'Home', group: 'Navigate', action: () => navigate('/') },
    { id: 'nav-slides', label: 'Investor Deck', group: 'Navigate', action: () => navigate('/slides') },
    ...navCommands,
    { id: 'nav-hunt', label: 'Threat Hunt — Hunt Proposer', group: 'Threat Hunter', action: () => navigate('/hunt') },
    { id: 'nav-remediation', label: 'Threat Hunt — Remediation Plans', group: 'Threat Hunter', action: () => navigate('/remediation') },
    { id: 'nav-red-team', label: 'Threat Hunt — Red-Team Library', group: 'Threat Hunter', action: () => navigate('/red-team') },
  ];
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette(paletteCommands);
  const { open: sentientOpen, show: sentientShow, hide: sentientHide } = useSentientLayer();

  const sentientUpdates: SentientUpdate[] = [
    {
      id: 'u1',
      headline: 'CVE-2024-21412: Critical NTLM bypass — 3 assets exposed',
      surface: 'Sentra',
      severity: 'critical',
      timestamp: new Date(Date.now() - 12 * 60000).toISOString(),
      href: '/threats',
    },
    {
      id: 'u2',
      headline: 'Control drift detected — MFA policy deviation on 4 endpoints',
      surface: 'Sentra',
      severity: 'warning',
      timestamp: new Date(Date.now() - 38 * 60000).toISOString(),
      href: '/controls',
    },
    {
      id: 'u3',
      headline: 'Resilience score improved: 73 → 81 after patch cycle',
      surface: 'Sentra',
      severity: 'info',
      timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
      href: '/dashboard',
    },
    {
      id: 'u4',
      headline: 'Incident IC-2409 escalated to P1 — awaiting CISO approval',
      surface: 'Sentra',
      severity: 'critical',
      timestamp: new Date(Date.now() - 55 * 60000).toISOString(),
      href: '/incident',
    },
  ];

  const sentientActions: SentientAction[] = [
    {
      id: 'a1',
      label: 'Isolate affected endpoints (4 hosts)',
      description: 'Agent recommends network isolation for CVE-2024-21412 exposure. Confidence: 94%. Reversible within 15 min.',
      confidence: 0.94,
      policyVerdict: 'requires_approval',
      href: '/approvals',
    },
    {
      id: 'a2',
      label: 'Trigger emergency MFA re-enrollment',
      description: 'Policy drift on SAML MFA — re-enrollment for 4 accounts recommended. Low blast radius.',
      confidence: 0.88,
      policyVerdict: 'allowed',
      href: '/controls',
    },
    {
      id: 'a3',
      label: 'Escalate IC-2409 to executive stakeholders',
      description: 'P1 incident open >45 min with no CISO acknowledgement — auto-escalation recommended.',
      confidence: 0.91,
      policyVerdict: 'requires_approval',
      href: '/incident',
    },
  ];

  const sentientCrossLinks: SentientCrossLink[] = [
    {
      id: 'cl1',
      surface: 'Counsel',
      surfaceAccent: '#8a8a8a',
      label: 'Active legal matter: data breach disclosure',
      description: 'Counsel has a linked data-breach matter with a 72h regulatory disclosure deadline.',
      href: '/counsel/dashboard',
      preservedContext: { surface: 'sentra', domain: 'incident' },
    },
    {
      id: 'cl2',
      surface: 'KORA',
      surfaceAccent: '#8a8a8a',
      label: '3 pending decisions in Decision Center',
      description: "KORA's Decision Center has 3 Sentra-sourced recommendations queued for approval.",
      href: '/lyte/decision-center',
      preservedContext: { surface: 'sentra' },
    },
    {
      id: 'cl3',
      surface: 'SEXTANT',
      surfaceAccent: '#8a8a8a',
      label: 'Fleet asset under active threat — MV Atlantic Falcon',
      description: "SEXTANT flagged MV Atlantic Falcon's onboard systems for a related CVE exposure.",
      href: '/vessels/fleet',
      preservedContext: { surface: 'sentra' },
    },
  ];

  const isPrintAllSlides = location === '/slides/print' || location.startsWith('/slides/print');
  const isPresenter = location === '/slides/presenter' || location.startsWith('/slides/presenter');
  const isSlides = location.startsWith('/slides') || location.startsWith('/slide');

  const isMobile = location.startsWith('/mobile');

  if (isPrintAllSlides) {
    return <AllSlides />;
  }

  if (isPresenter) {
    return <PresenterMode />;
  }

  if (isSlides) {
    return <SlideDeck />;
  }

  if (isMobile) {
    return (
      <Suspense fallback={<PageLoader />}>
        <MobileShell />
      </Suspense>
    );
  }

  if (location === '/' || location === '') {
    return (
      <>
        <EcosystemNav currentAppId="sentra" currentAppName="Sentra" accentColor={accent} />
        <Suspense fallback={<div style={{ height: '100vh', background: '#0a0a0a' }} />}>
          <main id="main-content" tabIndex={-1}>
            <SentraLandingPage />
          </main>
        </Suspense>
        <CommandPalette
          open={paletteOpen}
          onClose={() => setPaletteOpen(false)}
          commands={paletteCommands}
          appName="Sentra"
          accentColor={accent}
          placeholder="Search Sentra — pages, entities, actions..."
        />
        <Toaster position="bottom-right" theme="dark" />
      </>
    );
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: '#0a0a0a' }}>
      <EcosystemNav currentAppId="sentra" currentAppName="Sentra" accentColor={accent} />
      {/* ── Persistent Defensive-Only Doctrine Banner ── */}
      <div
        className="flex items-center justify-center gap-2 px-4 py-1 shrink-0"
        style={{ background: 'rgba(201,183,135,0.05)', borderBottom: '1px solid rgba(201,183,135,0.12)' }}
        role="banner"
        aria-label="Sentra defensive-only doctrine enforced"
      >
        <ShieldCheck className="w-3 h-3 text-[#c9b787] shrink-0" />
        <span className="text-[9px] font-mono uppercase tracking-widest text-[#c9b787]">
          DEFENSIVE ONLY
        </span>
        <span className="text-[9px] font-mono text-slate-600 hidden sm:inline">
          · All offensive, retaliatory &amp; attacker-side actions denied by policy · NIST SP 800-61r2 · CISA CIRCIA · MITRE D3FEND
        </span>
      </div>
      <SharedDashboardShell
        sidebar={
          <SentraSidebarContent
            expanded={sidebarExpanded}
            onMobileClose={() => setSidebarOpen(false)}
            onToggleCollapse={onToggleCollapse}
          />
        }
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        sidebarWidth={sidebarExpanded ? '14rem' : '3.5rem'}
        sidebarEvents={{
          onMouseEnter: () => setSidebarHovered(true),
          onMouseLeave: () => setSidebarHovered(false),
        }}
        theme={{ sidebarBg: '#0e0e0e', pageBg: '#0a0a0a', headerBg: 'rgba(10,10,10,0.92)' }}
        accentColor={accent}
        topbar={
          <div className="flex items-center gap-3 w-full md:hidden">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded transition-colors text-[#f5f5f5]/50"
              aria-label="Toggle navigation"
            >
              <Menu className="w-4 h-4" />
            </button>
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#f5f5f5]/80">
              Sentra
            </span>
          </div>
        }
      >
        <div data-szl-shell-main className="flex-1 overflow-auto h-full">
          <DashboardRoutes />
        </div>
      </SharedDashboardShell>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={paletteCommands}
        appName="Sentra"
        accentColor={accent}
        placeholder="Search Sentra — pages, entities, actions..."
      />
      <SentientLayer
        open={sentientOpen}
        onClose={sentientHide}
        onOpen={sentientShow}
        surfaceId="sentra"
        surfaceName="Sentra Cyber Resilience"
        accentColor={accent}
        updates={sentientUpdates}
        actions={sentientActions}
        crossLinks={sentientCrossLinks}
      />
      <Toaster position="bottom-right" theme="dark" />
    </div>
  );
}

export default function App() {
  useSessionRevocationToast();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { prefs, setPreference, isLoaded } = useUserPreferences();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => prefs.sidebar_collapsed);
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const userOverriddenSidebarRef = useRef(false);

  useEffect(() => {
    if (isLoaded && !userOverriddenSidebarRef.current) {
      setSidebarCollapsed(prefs.sidebar_collapsed);
    }
  }, [isLoaded, prefs.sidebar_collapsed]);

  const toggleCollapsed = useCallback(() => {
    userOverriddenSidebarRef.current = true;
    setSidebarCollapsed((prev) => {
      const next = !prev;
      setPreference('sidebar_collapsed', next);
      return next;
    });
  }, [setPreference]);

  return (
    <AppModeProvider>
      <AppModeBanner />
      <AnalyticsProvider appName="sentra">
        <QueryClientProvider client={queryClient}>
          <WouterRouter base={BASE}>
            <AppShell
              sidebarOpen={sidebarOpen}
              setSidebarOpen={setSidebarOpen}
              sidebarCollapsed={sidebarCollapsed}
              onToggleCollapse={toggleCollapsed}
              sidebarHovered={sidebarHovered}
              setSidebarHovered={setSidebarHovered}
            />
          </WouterRouter>
        </QueryClientProvider>
      </AnalyticsProvider>
    </AppModeProvider>
  );
}
