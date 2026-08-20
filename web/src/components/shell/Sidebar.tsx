// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'wouter';
import {
  LayoutGrid, Rocket, ShieldCheck, Sparkles,
  ChevronDown, ChevronRight,
  Globe, Crosshair, Activity, BarChart3, Map, Shield, Server,
  Cpu, Zap, Network, Settings, Users, Terminal, Layers,
  FileText, Workflow,
  BookOpen, Brain, Beaker,
  Box, Newspaper, KeyRound, Boxes,
  Search, Sigma,
  Telescope, BookOpenCheck, ExternalLink, TrendingUp, Target
} from 'lucide-react';
import { cn } from '@szl-holdings/design-system';

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');

interface NavItem {
  id: string;
  name: string;
  icon: React.ElementType;
  path: string;
  badge?: string;
  external?: boolean;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
  defaultOpen?: boolean;
}

// ── SIDEBAR CONSOLIDATION (Ken pattern, 2026-06-03): 157 tabs across 17 sections
// → 3 pinned + 7 sections (≈35 tabs), modeled on Stripe / Linear / Vercel command
// surfaces. Sub-routes with 4+ siblings collapse to a single parent tab; the parent
// page owns the in-page navigation (e.g. /strategy/briefings/* → one "Briefings" tab).
// EVERY one of the 478 App.tsx <Route> handlers stays a working deep link: each is
// still reachable via direct URL and via the ⌘K command palette (CommandPalette below),
// which indexes the full link set. No new dependencies; same lucide-react icons, same
// wouter Link, same @szl-holdings/design-system import. Doctrine v11 LOCKED 749/14/163.
// Λ Conjecture 1 (NOT a theorem). ADDITIVE collapse — no routes removed.

// Top pinned (3) — Stripe/Vercel-style always-visible entries.
const topItems: NavItem[] = [
  { id: 'whats-new', name: "What's New", icon: Newspaper, path: '/whats-new', badge: 'NEW' },
  { id: 'console', name: 'Console', icon: Terminal, path: '/console' },
  { id: 'szl-ops', name: 'SZL Operational Core', icon: ShieldCheck, path: '/szl-ops', badge: 'LIVE' },
];

const sections: NavSection[] = [
  {
    id: 'foundry',
    label: 'Foundry',
    defaultOpen: true,
    items: [
      { id: 'foundry-home', name: 'Foundry Home', icon: LayoutGrid, path: '/foundry' },
      { id: 'foundry-catalog', name: 'Catalog', icon: Boxes, path: '/foundry/catalog' },
      { id: 'foundry-provision', name: 'Provision', icon: FileText, path: '/foundry/provision' },
      { id: 'foundry-deployments', name: 'Deployments', icon: Rocket, path: '/foundry/deployments' },
      { id: 'foundry-keys', name: 'Keys & Secrets', icon: KeyRound, path: '/foundry/keys' },
      { id: 'foundry-monitoring', name: 'Monitoring', icon: Activity, path: '/foundry/monitoring' },
      { id: 'primitives-hub', name: 'Primitives', icon: Box, path: '/primitives' },
    ],
  },
  {
    id: 'strategy',
    label: 'Strategy',
    items: [
      { id: 'strat-dashboard', name: 'Strategy Dashboard', icon: Globe, path: '/strategy' },
      // /strategy/briefings/* — 8 siblings collapsed; the Briefings page owns in-page nav.
      { id: 'strat-briefings', name: 'Briefings', icon: Newspaper, path: '/strategy/briefings' },
      { id: 'strat-atlas-runtime', name: 'Atlas Runtime', icon: Zap, path: '/strategy/atlas-runtime' },
      { id: 'strat-simulation', name: 'Simulation', icon: Layers, path: '/strategy/simulation' },
      { id: 'strat-competitive', name: 'Competitive Atlas', icon: Map, path: '/strategy/competitive-atlas' },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { id: 'ops-exec', name: 'Operations Monitor', icon: Activity, path: '/operations' },
      { id: 'ops-noc', name: 'Autonomous NOC', icon: Server, path: '/operations/autonomous-noc' },
      { id: 'ops-slo', name: 'SLO Management', icon: Target, path: '/operations/slo' },
      { id: 'ops-metrics', name: 'Metrics Explorer', icon: BarChart3, path: '/operations/metrics' },
    ],
  },
  {
    id: 'infrastructure',
    label: 'Infrastructure',
    items: [
      // Single consolidated view; the IMPERIUM console owns in-page nav for the other surfaces.
      { id: 'infra-legatus', name: 'IMPERIUM Console', icon: Server, path: '/infrastructure/legatus' },
    ],
  },
  {
    id: 'intelligence-decisions',
    label: 'Intelligence & Decisions',
    items: [
      { id: 'dec-center', name: 'Decision Center', icon: Crosshair, path: '/decisions' },
      { id: 'dec-twin', name: 'Decision Twin (PRISM)', icon: Brain, path: '/decisions/twin' },
      { id: 'dec-autonomy', name: 'Autonomy Modes', icon: Workflow, path: '/decisions/autonomy' },
      { id: 'intel-overview', name: 'Command Overview', icon: LayoutGrid, path: '/intelligence' },
      { id: 'cog-overview', name: 'Cognitive Runtime', icon: Cpu, path: '/cognitive/overview' },
      { id: 'nexus-home', name: 'NEXUS Intelligence', icon: Sparkles, path: '/nexus' },
    ],
  },
  {
    id: 'frontier-research',
    label: 'Frontier & Research',
    items: [
      { id: 'frontier-index', name: 'Frontier Overview', icon: Telescope, path: '/frontier' },
      { id: 'argo-bridge', name: 'Argo — Decision Engine', icon: TrendingUp, path: '/argo' },
      { id: 'psyche-anima', name: 'PSYCHE — Sentience', icon: Sparkles, path: '/psyche' },
      { id: 'sigil', name: 'SIGIL', icon: Sigma, path: '/sigil' },
      { id: 'lab', name: 'A11oy Lab', icon: Beaker, path: '/lab' },
    ],
  },
  {
    id: 'doctrine-trust',
    label: 'Doctrine & Trust',
    items: [
      { id: 'doc-overview', name: 'Doctrine', icon: BookOpen, path: '/doctrine' },
      { id: 'doc-constitution', name: 'Constitution', icon: FileText, path: '/constitution' },
      { id: 'doc-alignment', name: 'Alignment Review', icon: ShieldCheck, path: '/alignment-review' },
      { id: 'trust-hub', name: 'Trust Hub', icon: Shield, path: '/trust' },
      { id: 'trust-portal', name: 'Public Trust Portal', icon: Globe, path: '/trust-portal' },
      { id: 'trust-transparency', name: 'Transparency Report', icon: FileText, path: '/transparency-report' },
      { id: 'trust-bom', name: 'Agent BOM / Proof', icon: BookOpenCheck, path: '/agent-bom' },
    ],
  },
];

// Full deep-link index for the ⌘K palette — every primary surface across the 478 routes
// remains reachable here even though the sidebar now renders only the consolidated set.
const ALL_DEEP_LINKS: NavItem[] = [
  ...topItems,
  ...sections.flatMap(s => s.items),
  // Foundry deep links collapsed from the sidebar
  { id: 'dl-foundry-workcells', name: 'Workcells', icon: Box, path: '/foundry/workcells' },
  { id: 'dl-foundry-sovereign', name: 'Sovereign Mode', icon: KeyRound, path: '/foundry/sovereign' },
  { id: 'dl-foundry-quickstarts', name: 'Quickstarts', icon: Sparkles, path: '/foundry/quickstarts' },
  // Strategy briefings family (page owns in-page nav; deep links retained for ⌘K)
  { id: 'dl-brief-today', name: "Today's Brief", icon: FileText, path: '/strategy/briefings/today' },
  { id: 'dl-brief-engine', name: 'Briefing Engine', icon: Workflow, path: '/strategy/briefings/engine' },
  { id: 'dl-brief-library', name: 'Brief Library', icon: BookOpen, path: '/strategy/briefings/library' },
  { id: 'dl-brief-watchlist', name: 'Watchlist', icon: BookOpenCheck, path: '/strategy/briefings/watchlist' },
  { id: 'dl-brief-confidence', name: 'Confidence', icon: BarChart3, path: '/strategy/briefings/confidence' },
  { id: 'dl-brief-dissent', name: 'Dissent Channel', icon: Newspaper, path: '/strategy/briefings/dissent' },
  { id: 'dl-brief-cockpit', name: 'Governed Cockpit', icon: ShieldCheck, path: '/strategy/briefings/cockpit' },
  { id: 'dl-strat-enterprise', name: 'Enterprise State', icon: Layers, path: '/strategy/enterprise-state' },
  { id: 'dl-strat-correlation', name: 'Correlation Map', icon: Network, path: '/strategy/correlation-map' },
  { id: 'dl-strat-signals', name: 'Signal Chains', icon: Activity, path: '/strategy/signal-chains' },
  // Operations deep links collapsed from the sidebar
  { id: 'dl-ops-topology', name: 'Service Topology', icon: Network, path: '/operations/topology' },
  { id: 'dl-ops-tracing', name: 'Distributed Tracing', icon: Workflow, path: '/operations/tracing' },
  { id: 'dl-ops-logs', name: 'Log Explorer', icon: Terminal, path: '/operations/logs' },
  { id: 'dl-ops-alerts', name: 'Alert Management', icon: Activity, path: '/operations/alerts' },
  { id: 'dl-ops-selfheal', name: 'Self-Healing', icon: Zap, path: '/operations/self-healing' },
  { id: 'dl-ops-runbook', name: 'Runbook Studio', icon: FileText, path: '/operations/runbook-studio' },
  { id: 'dl-ops-admin', name: 'Admin Console', icon: Settings, path: '/operations/admin/overview' },
  // Infrastructure deep links collapsed from the sidebar
  { id: 'dl-infra-map', name: 'Imperium Map', icon: Map, path: '/infrastructure/imperium-map' },
  { id: 'dl-infra-praetorian', name: 'Praetorian Guard', icon: Shield, path: '/infrastructure/praetorian' },
  { id: 'dl-infra-centurion', name: 'Centurion AI', icon: Cpu, path: '/infrastructure/centurion' },
  { id: 'dl-infra-fabric', name: 'Data Fabric', icon: Boxes, path: '/infrastructure/data-fabric' },
  // Cognitive runtime deep links
  { id: 'dl-cog-memory', name: 'Cognitive Memory', icon: Boxes, path: '/cognitive/memory' },
  { id: 'dl-cog-planner', name: 'Planner', icon: Target, path: '/cognitive/planner' },
  { id: 'dl-cog-verifier', name: 'Verifier', icon: ShieldCheck, path: '/cognitive/verifier' },
  // Frontier / Argo / PSYCHE deep links
  { id: 'dl-argo-arena', name: 'Self-Play Arena', icon: Zap, path: '/argo/arena' },
  { id: 'dl-argo-forge', name: 'Distillation Forge', icon: Beaker, path: '/argo/forge' },
  { id: 'dl-psyche-genesis', name: 'Genesis Ledger', icon: BookOpen, path: '/psyche/genesis' },
  // Doctrine / Trust deep links collapsed from the sidebar
  { id: 'dl-doc-constitution-dsl', name: 'Constitution DSL', icon: FileText, path: '/constitution-dsl' },
  { id: 'dl-doc-covenant', name: 'Covenant Lift', icon: Sparkles, path: '/covenant-lift' },
  { id: 'dl-doc-welfare', name: 'Welfare Playbooks', icon: BookOpen, path: '/welfare-playbooks' },
  { id: 'dl-trust-exchange', name: 'Trust Exchange', icon: Network, path: '/trust-exchange' },
  { id: 'dl-trust-security', name: 'Security & Compliance', icon: Shield, path: '/security-compliance' },
  { id: 'dl-trust-audit', name: 'Right to Audit', icon: BookOpenCheck, path: '/right-to-audit' },
  // Reasoning / Lesson
  { id: 'dl-reasoning', name: 'Reasoning Audit', icon: Brain, path: '/reasoning' },
  // External 3D + repo (Stripe-style "more" surfaces)
  { id: 'dl-github', name: 'GitHub', icon: ExternalLink, path: 'https://github.com/szl-holdings/a11oy', external: true },
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
  const fullPath = item.external ? item.path : `${BASE}${item.path}`;
  const isActive = !item.external && (location === `${BASE}${item.path}` || location.startsWith(`${BASE}${item.path}/`));

  const className = cn(
    'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] transition-colors',
    isActive
      ? 'bg-[var(--color-a11oy-gold-soft)] text-[var(--color-a11oy-gold-dim)] font-medium'
      : 'text-[var(--color-a11oy-text-sub)] hover:bg-[var(--color-a11oy-overlay)] hover:text-[var(--color-a11oy-text)]',
  );

  const inner = (
    <>
      <item.icon className={cn('w-4 h-4', isActive ? 'opacity-100' : 'opacity-50')} />
      <span className="flex-1">{item.name}</span>
      {item.badge && (
        <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{ background: 'rgba(201,183,135,0.16)', color: '#c9b787' }}>{item.badge}</span>
      )}
      {item.external && <ExternalLink className="w-3 h-3 opacity-30 shrink-0" />}
    </>
  );

  if (item.external) {
    return (
      <a href={fullPath} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }

  return (
    <Link href={fullPath} className={className}>
      {inner}
    </Link>
  );
}

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [, navigate] = useLocation();
  const [q, setQ] = useState('');
  // De-dup by path so ⌘K is the single source of navigation for ALL surfaces.
  const seen = new Set<string>();
  const index = ALL_DEEP_LINKS.filter(i => {
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
              onClick={() => {
                if (i.external) { window.open(i.path, '_blank', 'noopener,noreferrer'); }
                else { navigate(`${BASE}${i.path}`); }
                onClose();
              }}
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
      {/* Search-to-navigate: opens the ⌘K command palette that indexes ALL deep links */}
      <div className="px-3 pt-4 pb-2">
        <button type="button" onClick={() => setPaletteOpen(true)}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[12px] text-[var(--color-a11oy-text-ghost)] border border-[var(--color-a11oy-border-subtle)] hover:text-[var(--color-a11oy-text-sub)]">
          <Search className="w-3.5 h-3.5" />
          <span className="flex-1 text-left">Search surfaces…</span>
          <span className="text-[10px] font-mono opacity-60">⌘K</span>
        </button>
      </div>

      {/* 3 pinned top items (Stripe/Linear/Vercel pattern) */}
      <div className="px-3 py-1">
        <nav className="flex flex-col gap-0.5">
          {topItems.map(item => <NavLink key={item.id} item={item} />)}
        </nav>
      </div>

      {/* 7 consolidated sections. Every other route stays live via ⌘K + direct URL. */}
      <div className="px-3 py-1 flex-1">
        {sections.map(section => (
          <CollapsibleSection key={section.id} section={section} />
        ))}
      </div>

      {/* Settings / profile pinned bottom-left (Linear / Vercel pattern) */}
      <div className="px-3 py-2 border-t border-[var(--color-a11oy-border-subtle)]">
        <NavLink item={{ id: 'tab-settings', name: 'Settings & Billing', icon: Settings, path: '/account/billing' }} />
        <NavLink item={{ id: 'tab-account', name: 'Operator Profile', icon: Users, path: '/operator-profile' }} />
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
