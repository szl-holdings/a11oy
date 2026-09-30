import React from 'react';
import { Link, useLocation } from 'wouter';
import {
  Activity,
  Brain,
  Cable,
  Cpu,
  Database,
  Eye,
  FlaskConical,
  FolderSync,
  History,
  Layers,
  LayoutTemplate,
  Settings,
  Menu,
  Gauge,
  Shield,
  Sparkles,
  ExternalLink,
  Users,
  GitBranch,
  ListChecks,
  Map,
  Telescope,
  Target,
  Wand2,
  Boxes,
  Network,
  Zap,
  FlaskRound,
  Merge,
  ScanLine,
  Leaf,
  RotateCcw,
  Clapperboard,
  SlidersHorizontal,
  SearchCheck,
  Code2,
  Infinity as InfinityIcon,
  Heart,
  Star,
  BookOpen,
  Cpu as CpuIcon,
  Globe,
  Archive,
} from 'lucide-react';

const coreItems = [
  { name: 'Operational Core', href: '/operational-core', icon: InfinityIcon },
  { name: 'Cockpit', href: '/cockpit', icon: Activity },
  { name: 'Brain', href: '/brain', icon: Brain },
  { name: 'Compute', href: '/compute', icon: Cpu },
  { name: 'Connections', href: '/connections', icon: Cable },
  { name: 'Syncs', href: '/syncs', icon: FolderSync },
  { name: 'Runs', href: '/runs', icon: History },
  { name: 'Templates', href: '/templates', icon: LayoutTemplate },
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Admin Usage', href: '/admin/usage', icon: Gauge },
  { name: 'AGI Forecast', href: '/agi-forecast', icon: Telescope },
];

const fabricItems = [
  { name: 'Sources', href: '/sources', icon: Database },
  { name: 'Models', href: '/models', icon: Boxes },
  { name: 'Destinations', href: '/destinations', icon: Network },
  { name: 'Mappings', href: '/mappings', icon: GitBranch },
  { name: 'Policies', href: '/policies', icon: ListChecks },
  { name: 'Observability', href: '/observability', icon: Telescope },
  { name: 'Outcomes', href: '/outcomes', icon: Target },
  { name: 'Agents', href: '/agents', icon: Users },
  { name: 'Roadmap', href: '/roadmap', icon: Map },
];

const sovereignItems = [
  { name: 'AI Hub', href: '/sovereign-ai-hub', icon: Shield },
  { name: 'Model Fleet', href: '/sovereign-ai-hub/model-fleet', icon: Layers },
  { name: 'Inference', href: '/sovereign-ai-hub/inference', icon: Eye },
  { name: 'Distillery', href: '/sovereign-ai-hub/distillery', icon: FlaskConical },
  { name: 'PRAXIS', href: '/sovereign-ai-hub/praxis', icon: Wand2 },
  { name: 'Data Estate', href: '/sovereign-ai-hub/data-estate', icon: Database },
  { name: 'Cognitive', href: '/sovereign-ai-hub/cognitive', icon: Brain },
];

const innovationItems = [
  { name: 'Innovation Brief', href: '/innovation', icon: Zap },
  { name: 'Audience SQL', href: '/innovation/audience-sql', icon: FlaskRound },
  { name: 'Lineage Graph', href: '/innovation/lineage', icon: ScanLine },
  { name: 'Drift Repair', href: '/innovation/drift-repair', icon: GitBranch },
  { name: 'Golden Record', href: '/innovation/golden-record', icon: Merge },
  { name: 'Cost & Carbon', href: '/innovation/cost-carbon', icon: Leaf },
  { name: 'Closed Loop', href: '/innovation/closed-loop', icon: RotateCcw },
  { name: 'Sim Theater', href: '/innovation/sim-theater', icon: Clapperboard },
  { name: 'Mapper Accuracy', href: '/innovation/mapper-accuracy', icon: SlidersHorizontal },
  { name: 'Dest Discovery', href: '/innovation/destination-discovery', icon: SearchCheck },
  { name: 'Policy DSL', href: '/innovation/policy-dsl', icon: Code2 },
];

const externalNavItems = [
  { name: 'A11oy Conductor', href: '/', icon: Sparkles },
];

// Pill-matching amaru API surfaces (landing page pills) — tab cap
const amaruSurfaceItems = [
  { name: 'Ask amaru', href: '/brain', icon: Brain },
  { name: 'Cited Viewer', href: '/brain', icon: BookOpen },
  { name: 'Health', href: '/api/amaru/healthz', icon: Heart },
  { name: 'Honest', href: '/api/amaru/v1/honest', icon: Star },
  { name: 'MCP Tools', href: '/api/amaru/v1/mcp/tools', icon: CpuIcon },
  { name: 'Agent Loop', href: '/agents', icon: InfinityIcon },
  { name: 'Receipts', href: '/api/amaru/v1/receipts', icon: Archive },
  { name: '3D Galaxy', href: '/constellation-3d', icon: Globe },
  { name: 'GitHub', href: 'https://github.com/szl-holdings/amaru', icon: Sparkles },
];

type NavItem = { name: string; href: string; icon: React.ComponentType<{ className?: string }> };

const MARK_SRC = `${import.meta.env.BASE_URL}szl/logos/szl_favicon.svg`;

/* Founder operator shell (szl-console.css .sidebar*): neutral links, the active item
   carries the single coral node via .sidebar__link[aria-current="page"]. */
function NavLink({ item, isActive, collapsed }: { item: NavItem; isActive: boolean; collapsed: boolean }) {
  return (
    <Link
      href={item.href}
      aria-label={collapsed ? item.name : undefined}
      title={collapsed ? item.name : undefined}
      aria-current={isActive ? 'page' : undefined}
      className="sidebar__link"
    >
      <span className="sidebar__icon" aria-hidden="true"><item.icon /></span>
      {!collapsed && <span>{item.name}</span>}
    </Link>
  );
}

const ALL_NAV_ITEMS: ReadonlyArray<NavItem> = [...coreItems, ...fabricItems, ...sovereignItems, ...innovationItems, ...amaruSurfaceItems];

/* aria-current marks ONE link, and with it the view's one coral marker: the most specific
   nav href that matches the route, first occurrence in nav order (several entries share
   /brain and /agents; /innovation also prefixes every innovation page). */
function activeNavName(location: string): string | undefined {
  let best: NavItem | undefined;
  for (const item of ALL_NAV_ITEMS) {
    const hit = item.href === '/' ? location === '/' : (location === item.href || location.startsWith(item.href + '/'));
    if (hit && (!best || item.href.length > best.href.length)) best = item;
  }
  return best?.name;
}

function NavSection({ label, items, activeName, collapsed }: { label: string; items: ReadonlyArray<NavItem>; activeName: string | undefined; collapsed: boolean }) {
  return (
    <>
      {!collapsed && <p className="sidebar__section">{label}</p>}
      {items.map((item) => (
        <NavLink key={item.name} item={item} isActive={item.name === activeName} collapsed={collapsed} />
      ))}
    </>
  );
}

function NavDivider() {
  return <div className="sidebar__divider" role="presentation" />;
}

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(true);
  const activeName = activeNavName(location);

  const breadcrumb = (location === '/cockpit' || location === '/') ? 'Cockpit' : location.split('/').filter(Boolean).map(s => s.charAt(0).toUpperCase() + s.slice(1).replace(/-/g, ' ')).join(' / ');

  return (
    <div className="flex h-screen w-full overflow-hidden bg-ground text-ink">
      <aside className="sidebar z-10" data-collapsed={isSidebarOpen ? undefined : 'true'}>
        <div className="sidebar__head">
          {isSidebarOpen && (
            <Link href="/" className="sidebar__brand">
              <img src={MARK_SRC} alt="" width={41} height={24} />
              <span>Amaru</span>
            </Link>
          )}
          <button
            type="button"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            aria-label={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-expanded={isSidebarOpen}
            className="sidebar__toggle pointer-coarse:w-11 pointer-coarse:h-11"
          >
            <Menu className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <nav aria-label="Main navigation" className="sidebar__nav">
          <NavSection label="Amaru Core" items={coreItems} activeName={activeName} collapsed={!isSidebarOpen} />
          <NavDivider />
          <NavSection label="Activation Fabric" items={fabricItems} activeName={activeName} collapsed={!isSidebarOpen} />
          <NavDivider />
          <NavSection label="Sovereign AI Hub" items={sovereignItems} activeName={activeName} collapsed={!isSidebarOpen} />
          <NavDivider />
          <NavSection label="One-of-One" items={innovationItems} activeName={activeName} collapsed={!isSidebarOpen} />
          <NavDivider />
          <NavSection label="amaru Surfaces" items={amaruSurfaceItems} activeName={activeName} collapsed={!isSidebarOpen} />
          <NavDivider />

          {isSidebarOpen && <p className="sidebar__section">Cross-Platform</p>}
          {externalNavItems.map((item) => (
            <a
              key={item.name}
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={!isSidebarOpen ? item.name : undefined}
              title={!isSidebarOpen ? item.name : undefined}
              className="sidebar__link"
            >
              <span className="sidebar__icon" aria-hidden="true"><item.icon /></span>
              {isSidebarOpen && (
                <span className="flex-1 flex items-center justify-between">
                  {item.name}
                  <ExternalLink className="w-3 h-3" aria-hidden="true" />
                </span>
              )}
            </a>
          ))}
        </nav>

        <div className="p-3 border-t border-line-subtle">
          {isSidebarOpen ? (
            <div className="flex items-center gap-3 px-1">
              <div className="w-8 h-8 rounded-full flex items-center justify-center font-mono font-semibold text-[10px] border border-line bg-surface-alt text-ink" aria-hidden="true">
                OP
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-medium text-ink leading-none">Operator</span>
                <span className="text-xs text-ink-ghost mt-1">SZL System</span>
              </div>
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full flex items-center justify-center font-mono font-semibold text-[10px] border border-line bg-surface-alt text-ink mx-auto" title="Operator">
              OP
            </div>
          )}
        </div>
      </aside>

      <main id="main-content" tabIndex={-1} className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <header className="h-14 flex items-center px-6 border-b border-line-subtle shrink-0 justify-between bg-ground">
           <div className="flex items-center gap-2 text-sm text-ink-sub">
              <span className="text-ink font-medium">{breadcrumb}</span>
           </div>
           <div className="flex items-center gap-5">
              <div className="flex items-center gap-2 text-xs font-semibold tracking-[var(--tracking-caps)] uppercase text-ink-ghost">
                 <span className="dot dot--ok" aria-hidden="true"></span>
                 Governed Environment
              </div>
           </div>
        </header>
        <div className="flex-1 overflow-y-auto scroll-smooth bg-ground">
          <div className="mx-auto w-full max-w-[1440px] animate-fade-in-up px-6 py-6 lg:px-8 lg:py-8">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
