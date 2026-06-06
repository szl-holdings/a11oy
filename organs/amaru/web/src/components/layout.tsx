import React from 'react';
import { Link, useLocation } from 'wouter';
import { cn } from '@/lib/utils';
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

function NavLink({ item, isActive, collapsed }: { item: { name: string; href: string; icon: React.ComponentType<{ className?: string }> }; isActive: boolean; collapsed: boolean }) {
  return (
    <Link
      href={item.href}
      aria-label={collapsed ? item.name : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-[13px] font-medium",
        isActive
          ? "bg-[#0e0e0e] text-[#c9b787]"
          : "text-[#8a8a8a] hover:bg-[#141414] hover:text-[#f5f5f5]"
      )}
    >
      <item.icon className={cn("w-[18px] h-[18px] shrink-0", isActive ? "text-[#c9b787]" : "text-[#666]")} aria-hidden="true" />
      {!collapsed && <span>{item.name}</span>}
    </Link>
  );
}

function NavSection({ label, items, location, collapsed }: { label: string; items: ReadonlyArray<{ name: string; href: string; icon: React.ComponentType<{ className?: string }> }>; location: string; collapsed: boolean }) {
  return (
    <>
      {!collapsed && (
        <p className="px-3 pt-1 pb-2 text-[10px] font-mono uppercase tracking-[0.18em] text-[#555]">
          {label}
        </p>
      )}
      {items.map((item) => {
        const isActive = item.href === '/' ? location === '/' : (location === item.href || location.startsWith(item.href + '/'));
        return <NavLink key={item.name} item={item} isActive={isActive} collapsed={collapsed} />;
      })}
    </>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(true);

  const breadcrumb = (location === '/cockpit' || location === '/') ? 'Cockpit' : location.split('/').filter(Boolean).map(s => s.charAt(0).toUpperCase() + s.slice(1).replace(/-/g, ' ')).join(' / ');

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ background: '#0a0a0a', color: '#f5f5f5' }}>
      <aside
        className={cn(
          "flex flex-col border-r border-[rgba(255,255,255,0.06)] transition-all duration-300 z-10 shrink-0",
          isSidebarOpen ? "w-60" : "w-16"
        )}
        style={{ background: '#0e0e0e' }}
      >
        <div className="flex h-14 items-center justify-between px-4 border-b border-[rgba(255,255,255,0.06)]">
          {isSidebarOpen && (
            <Link href="/" className="flex items-center gap-2.5 font-display font-bold text-base tracking-tight">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center border border-[rgba(201,183,135,0.3)]" style={{ background: 'rgba(201,183,135,0.08)' }}>
                <span className="font-mono text-[11px] font-bold text-[#c9b787]">A</span>
              </div>
              <span className="text-[#f5f5f5]">Amaru</span>
            </Link>
          )}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            aria-label={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-expanded={isSidebarOpen}
            className="p-1.5 rounded-lg hover:bg-[#0e0e0e] text-[#666] hover:text-[#f5f5f5] transition-colors"
          >
            <Menu className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          <NavSection label="Amaru Core" items={coreItems} location={location} collapsed={!isSidebarOpen} />
          <div className="my-3 mx-3 h-px bg-[rgba(255,255,255,0.04)]" />
          <NavSection label="Activation Fabric" items={fabricItems} location={location} collapsed={!isSidebarOpen} />
          <div className="my-3 mx-3 h-px bg-[rgba(255,255,255,0.04)]" />
          <NavSection label="Sovereign AI Hub" items={sovereignItems} location={location} collapsed={!isSidebarOpen} />
          <div className="my-3 mx-3 h-px bg-[rgba(255,255,255,0.04)]" />
          <NavSection label="One-of-One" items={innovationItems} location={location} collapsed={!isSidebarOpen} />
          <div className="my-3 mx-3 h-px bg-[rgba(255,255,255,0.04)]" />
          <NavSection label="amaru Surfaces" items={amaruSurfaceItems} location={location} collapsed={!isSidebarOpen} />
          <div className="my-3 mx-3 h-px bg-[rgba(255,255,255,0.04)]" />

          {isSidebarOpen && (
            <p className="px-3 pt-1 pb-2 text-[10px] font-mono uppercase tracking-[0.18em] text-[#555]">
              Cross-Platform
            </p>
          )}
          {externalNavItems.map((item) => (
            <a
              key={item.name}
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={!isSidebarOpen ? item.name : undefined}
              className="flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 text-[13px] font-medium text-[#8a8a8a] hover:bg-[#141414] hover:text-[#f5f5f5]"
            >
              <item.icon className="w-[18px] h-[18px] shrink-0 text-[#666]" aria-hidden="true" />
              {isSidebarOpen && (
                <span className="flex-1 flex items-center justify-between">
                  {item.name}
                  <ExternalLink className="w-3 h-3 opacity-40" />
                </span>
              )}
            </a>
          ))}
        </nav>

        <div className="p-3 border-t border-[rgba(255,255,255,0.06)]">
          {isSidebarOpen ? (
            <div className="flex items-center gap-3 px-1">
              <div className="w-8 h-8 rounded-full flex items-center justify-center font-mono font-bold text-[10px] border border-[rgba(255,255,255,0.08)] text-[#c9b787]" style={{ background: 'rgba(201,183,135,0.08)' }}>
                OP
              </div>
              <div className="flex flex-col">
                <span className="text-[13px] font-medium text-[#f5f5f5] leading-none">Operator</span>
                <span className="text-[11px] text-[#666] mt-0.5">SZL System</span>
              </div>
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full flex items-center justify-center font-mono font-bold text-[10px] border border-[rgba(255,255,255,0.08)] text-[#c9b787] mx-auto" style={{ background: 'rgba(201,183,135,0.08)' }} title="Operator">
              OP
            </div>
          )}
        </div>
      </aside>

      <main id="main-content" tabIndex={-1} className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <header className="h-14 flex items-center px-6 border-b border-[rgba(255,255,255,0.06)] shrink-0 justify-between glass-panel">
           <div className="flex items-center gap-2 text-[13px] text-[#8a8a8a]">
              <span className="text-[#f5f5f5] font-medium">{breadcrumb}</span>
           </div>
           <div className="flex items-center gap-5">
              <div className="flex items-center gap-2 text-[10px] font-mono tracking-[0.15em] uppercase text-[#666]">
                 <span className="w-1.5 h-1.5 rounded-full bg-[#5a8a6e]" style={{ boxShadow: '0 0 6px rgba(90,138,110,0.5)' }}></span>
                 Governed Environment
              </div>
           </div>
        </header>
        <div className="flex-1 overflow-y-auto scroll-smooth" style={{ background: '#0a0a0a' }}>
          <div className="mx-auto w-full max-w-[1440px] animate-fade-in-up px-6 py-6 lg:px-8 lg:py-8">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
