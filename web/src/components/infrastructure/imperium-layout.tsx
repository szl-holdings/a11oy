import { getThreatColor, IMPERIUM_DATA } from '../../lib/infrastructure/imperium-data';
import { cn } from '../../lib/infrastructure/utils';
import {
  Activity,
  BookOpen,
  ChevronRight,
  Cpu,
  Crown,
  Database,
  Globe2,
  Map,
  Menu,
  Network,
  Radio,
  Satellite,
  Server,
  Shield,
  Users,
  X,
  Zap,
} from 'lucide-react';
import React, { useState } from 'react';
import { Link, useLocation } from 'wouter';

const NAV_ITEMS = [
  {
    path: '/infrastructure',
    label: 'EXECUTIVE CONSOLE',
    sublabel: 'Executive Overview',
    icon: Crown,
  },
  {
    path: '/infrastructure/imperium-map',
    label: 'RESOURCE MAP',
    sublabel: 'Resource Hierarchy',
    icon: Map,
  },
  {
    path: '/infrastructure/praetorian',
    label: 'SECURITY PERIMETER',
    sublabel: 'Security Controls',
    icon: Shield,
  },
  {
    path: '/infrastructure/senate',
    label: 'GOVERNANCE BOARD',
    sublabel: 'Change Management',
    icon: BookOpen,
  },
  {
    path: '/infrastructure/supply-lines',
    label: 'NETWORK TOPOLOGY',
    sublabel: 'Service Mesh Routes',
    icon: Network,
  },
  {
    path: '/infrastructure/centurion',
    label: 'AI OPERATIONS',
    sublabel: 'Agent Profiles',
    icon: Cpu,
  },
  {
    path: '/infrastructure/intelligence',
    label: 'INTELLIGENCE',
    sublabel: 'Signals Briefing',
    icon: Radio,
  },
  {
    path: '/infrastructure/geospatial',
    label: 'GEOSPATIAL',
    sublabel: 'Intelligence Layers',
    icon: Satellite,
  },
  {
    path: '/infrastructure/directives',
    label: 'DIRECTIVE CASCADE',
    sublabel: 'Command & Control',
    icon: Zap,
  },
  {
    path: '/infrastructure/coalition',
    label: 'COALITION',
    sublabel: 'Stakeholder Manager',
    icon: Users,
  },
  {
    path: '/infrastructure/reserves',
    label: 'STRATEGIC RESERVES',
    sublabel: 'Reserve Drawdown',
    icon: Database,
  },
  {
    path: '/infrastructure/substrate',
    label: 'SUBSTRATE INFERENCE',
    sublabel: 'Edge GPU / oLLM',
    icon: Server,
  },
];

function ThreatBadge({ level }: { level: string }) {
  const color = getThreatColor(level as 'low' | 'medium' | 'high' | 'critical');
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-2 h-2 rounded-full animate-pulse-gold"
        style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
      />
      <span className="font-mono text-xs tracking-widest" style={{ color }}>
        {level}
      </span>
    </div>
  );
}

export function ImperiumLayout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const imperium = IMPERIUM_DATA;

  return (
    <div className="flex h-screen overflow-hidden bg-[#060810] hex-grid">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 flex flex-col transition-transform duration-300 lg:relative lg:translate-x-0',
          'border-r border-gold/10',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        )}
        style={{
          background: 'linear-gradient(180deg, #0a0d1a 0%, #060810 100%)',
        }}
      >
        {/* Header */}
        <div className="px-4 pt-6 pb-4 border-b border-gold/10">
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0"
              style={{
                background: 'rgba(201,162,39,0.1)',
                border: '1px solid rgba(201,162,39,0.3)',
              }}
            >
              <Globe2 className="w-4 h-4" style={{ color: '#c9a227' }} />
            </div>
            <div>
              <h1 className="font-display text-sm tracking-[0.15em] font-bold gold-text leading-tight">
                PLATFORM
              </h1>
              <p className="text-[10px] tracking-widest text-slate-500 uppercase leading-tight">
                Cloud Infrastructure
              </p>
            </div>
          </div>
          <div className="mt-3 px-2 py-2 rounded imperial-card flex items-center justify-between">
            <ThreatBadge level={imperium.threatLevel} />
            <span className="font-mono text-[10px] text-slate-500">HS {imperium.aquilaScore}</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 scrollbar-imperial">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              location === item.path ||
              (item.path !== '/infrastructure' && location.startsWith(item.path));
            return (
              <Link key={item.path} href={item.path}>
                <a
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-4 py-2.5 mx-2 rounded transition-all duration-200 group cursor-pointer',
                    isActive
                      ? 'bg-gold/10 border border-gold/25'
                      : 'hover:bg-white/3 border border-transparent hover:border-white/5',
                  )}
                >
                  <Icon
                    className="w-4 h-4 flex-shrink-0 transition-colors"
                    style={{ color: isActive ? '#c9a227' : 'rgba(148,163,184,0.6)' }}
                  />
                  <div className="min-w-0">
                    <div
                      className="font-display text-[10px] tracking-[0.12em] font-semibold transition-colors leading-tight"
                      style={{ color: isActive ? '#c9a227' : 'rgba(226,215,180,0.7)' }}
                    >
                      {item.label}
                    </div>
                    <div className="text-[10px] text-slate-600 group-hover:text-slate-500 transition-colors leading-tight truncate">
                      {item.sublabel}
                    </div>
                  </div>
                  {isActive && (
                    <ChevronRight
                      className="w-3 h-3 ml-auto flex-shrink-0"
                      style={{ color: '#c9a227' }}
                    />
                  )}
                </a>
              </Link>
            );
          })}
        </nav>

        {/* Footer stats */}
        <div className="px-4 py-3 border-t border-gold/10">
          <div className="grid grid-cols-3 gap-1 text-center">
            <div>
              <div className="font-mono text-xs font-bold gold-text">{imperium.totalResources}</div>
              <div className="text-[9px] tracking-wider text-slate-600 uppercase">Resources</div>
            </div>
            <div>
              <div className="font-mono text-xs font-bold gold-text">{imperium.legions.length}</div>
              <div className="text-[9px] tracking-wider text-slate-600 uppercase">Regions</div>
            </div>
            <div>
              <div className="font-mono text-xs font-bold text-green-400">
                {imperium.aquilaScore}
              </div>
              <div className="text-[9px] tracking-wider text-slate-600 uppercase">Health</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-4 py-3 border-b border-gold/10 flex-shrink-0"
          style={{ background: 'rgba(6,8,16,0.95)' }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="lg:hidden p-1.5 rounded hover:bg-white/5 transition-colors"
            >
              {mobileOpen ? (
                <X className="w-5 h-5 text-slate-400" />
              ) : (
                <Menu className="w-5 h-5 text-slate-400" />
              )}
            </button>
            <div className="hidden sm:flex items-center gap-2 text-slate-500 text-xs font-mono">
              <span className="tracking-widest">PLATFORM SZLHOLDINGS</span>
              <span>/</span>
              <span style={{ color: '#c9a227' }}>
                {NAV_ITEMS.find(
                  (n) =>
                    location === n.path ||
                    (n.path !== '/infrastructure' && location.startsWith(n.path)),
                )?.label || 'COMMAND'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-mono">
              <Activity className="w-3 h-3 text-green-400" />
              <span>ALL SYSTEMS ACTIVE</span>
            </div>
            <div
              className="px-2 py-1 rounded font-mono text-[10px] tracking-widest"
              style={{
                background: 'rgba(201,162,39,0.08)',
                border: '1px solid rgba(201,162,39,0.2)',
                color: '#c9a227',
              }}
            >
              {new Date().toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
              })}{' '}
              UTC
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto scrollbar-imperial p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
