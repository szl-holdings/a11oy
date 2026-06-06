import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Clock,
  ExternalLink,
  Filter,
  Flame,
  Globe,
  Shield,
  Swords,
  Target,
  Trophy,
  Users,
  Zap,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link } from 'wouter';
import {
  CRISIS_SCENARIOS as fallbackScenarios,
  SCENARIO_CATEGORY_LABELS,
  THREAT_ACTOR_LABELS,
  type AttackCategory,
  type CrisisScenario,
  type ThreatActor,
} from '@/data/crisis-scenarios';
import { listCrisisScenarios } from '@/lib/sentra-api';
import { SourceBadge, useApiQuery } from '@/lib/use-api-query';

const CATEGORY_COLORS: Record<string, string> = {
  ransomware: 'text-red-400 border-red-500/30 bg-red-500/10',
  'supply-chain': 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  insider: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  'ot-ics': 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  bec: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
  cloud: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
  deepfake: 'text-pink-400 border-pink-500/30 bg-pink-500/10',
  'multi-vector': 'text-red-400 border-red-500/30 bg-red-500/10',
};

const ACTOR_COLORS: Record<string, string> = {
  APT28: 'text-red-400',
  APT41: 'text-amber-400',
  Lazarus: 'text-purple-400',
  MuddyWater: 'text-orange-400',
  'CISA-Generic': 'text-slate-400',
  Insider: 'text-blue-400',
};

const DIFFICULTY_COLORS: Record<string, string> = {
  entry: 'text-emerald-400 border-emerald-500/30',
  intermediate: 'text-amber-400 border-amber-500/30',
  advanced: 'text-orange-400 border-orange-500/30',
  'nation-state': 'text-red-400 border-red-500/30',
};

function StatCard({ icon: Icon, label, value, color }: { icon: typeof Shield; label: string; value: string; color: string }) {
  return (
    <div className="sentra-panel p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(245,245,245,0.06)', border: '1px solid rgba(245,245,245,0.10)' }}>
        <Icon className="w-5 h-5" style={{ color }} />
      </div>
      <div>
        <div className="text-2xl font-display font-bold text-slate-100">{value}</div>
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mt-0.5">{label}</div>
      </div>
    </div>
  );
}

type FilterState = {
  category: AttackCategory | 'all';
  actor: ThreatActor | 'all';
  difficulty: string;
};

export default function CrisisSimulator() {
  const [filters, setFilters] = useState<FilterState>({ category: 'all', actor: 'all', difficulty: 'all' });
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const fetcher = useCallback(() => listCrisisScenarios(), []);
  const { data: CRISIS_SCENARIOS, source } = useApiQuery<CrisisScenario[]>(fetcher, 'scenarios', fallbackScenarios);

  const filtered = CRISIS_SCENARIOS.filter((s) => {
    if (filters.category !== 'all' && s.category !== filters.category) return false;
    if (filters.actor !== 'all' && s.threatActor !== filters.actor) return false;
    if (filters.difficulty !== 'all' && s.difficulty !== filters.difficulty) return false;
    return true;
  });

  const categories = Object.entries(SCENARIO_CATEGORY_LABELS) as [AttackCategory, string][];
  const actors = Object.entries(THREAT_ACTOR_LABELS) as [ThreatActor, string][];

  return (
    <div className="space-y-6 animate-fade-in">
      <header className="flex items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-red-400">
              CLASSIFIED · SIMULATION MODE
            </span>
            <SourceBadge source={source} />
          </div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Crisis Simulation Engine</h1>
          <p className="text-slate-400 mt-1 max-w-2xl">
            Branching, time-pressured crisis exercises modeled from real nation-state adversary playbooks (APT28/GRU, APT41/MSS, Lazarus/DPRK, MuddyWater/MOIS). Make decisions under pressure, earn a post-exercise resilience grade.
          </p>
        </div>
        <Link href="/resilience-leaderboard">
          <button className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-colors shrink-0"
            style={{ background: 'rgba(201,183,135,0.08)', border: '1px solid rgba(201,183,135,0.20)', color: '#c9b787' }}>
            <Trophy className="w-3.5 h-3.5" />
            Resilience Leaderboard
            <ExternalLink className="w-3 h-3 opacity-60" />
          </button>
        </Link>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Swords} label="Scenarios Available" value={`${CRISIS_SCENARIOS.length}`} color="#ef4444" />
        <StatCard icon={Users} label="Adversary Groups" value="4" color="#c9b787" />
        <StatCard icon={Target} label="MITRE Techniques" value="40+" color="#8a8a8a" />
        <StatCard icon={Shield} label="Regulatory Frameworks" value="8" color="#f5f5f5" />
      </div>

      <div className="sentra-panel p-5">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Filter Scenarios</span>
        </div>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilters((f) => ({ ...f, category: 'all' }))}
              className={cn('px-3 py-1 rounded text-[11px] font-mono font-bold border transition-colors',
                filters.category === 'all' ? 'bg-[#f5f5f5]/15 border-[#f5f5f5]/40 text-[#f5f5f5]' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
              )}
            >All Categories</button>
            {categories.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setFilters((f) => ({ ...f, category: id }))}
                className={cn('px-3 py-1 rounded text-[11px] font-mono font-bold border transition-colors',
                  filters.category === id ? 'bg-[#f5f5f5]/15 border-[#f5f5f5]/40 text-[#f5f5f5]' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
                )}
              >{label}</button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilters((f) => ({ ...f, actor: 'all' }))}
              className={cn('px-3 py-1 rounded text-[11px] font-mono font-bold border transition-colors',
                filters.actor === 'all' ? 'bg-[#f5f5f5]/15 border-[#f5f5f5]/40 text-[#f5f5f5]' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
              )}
            >All Actors</button>
            {actors.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setFilters((f) => ({ ...f, actor: id }))}
                className={cn('px-3 py-1 rounded text-[11px] font-mono font-bold border transition-colors',
                  filters.actor === id ? 'bg-[#f5f5f5]/15 border-[#f5f5f5]/40 text-[#f5f5f5]' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
                )}
              >{label.split(' · ')[0]}</button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {(['all', 'entry', 'intermediate', 'advanced', 'nation-state'] as const).map((d) => (
              <button
                key={d}
                onClick={() => setFilters((f) => ({ ...f, difficulty: d }))}
                className={cn('px-3 py-1 rounded text-[11px] font-mono font-bold border transition-colors',
                  filters.difficulty === d ? 'bg-[#f5f5f5]/15 border-[#f5f5f5]/40 text-[#f5f5f5]' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
                )}
              >{d === 'all' ? 'All Difficulties' : d.charAt(0).toUpperCase() + d.slice(1).replace('-', '-')}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="text-[10px] font-mono text-slate-600 uppercase">
        {filtered.length} of {CRISIS_SCENARIOS.length} scenarios
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((scenario) => {
          const catStyle = CATEGORY_COLORS[scenario.category] ?? 'text-slate-400 border-slate-500/30 bg-slate-500/10';
          const actorColor = ACTOR_COLORS[scenario.threatActor] ?? 'text-slate-400';
          const diffStyle = DIFFICULTY_COLORS[scenario.difficulty] ?? 'text-slate-400 border-slate-500/30';
          const isHovered = hoveredId === scenario.id;
          const totalDecisions = scenario.phases.reduce((acc, p) => acc + p.decisionPoints.length, 0);

          return (
            <div
              key={scenario.id}
              onMouseEnter={() => setHoveredId(scenario.id)}
              onMouseLeave={() => setHoveredId(null)}
              className={cn(
                'sentra-panel p-5 transition-all duration-200',
                isHovered && 'border-[#f5f5f5]/20',
              )}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={cn('text-[9px] px-1.5 py-0.5 rounded border font-mono uppercase font-bold', catStyle)}>
                      {SCENARIO_CATEGORY_LABELS[scenario.category]}
                    </span>
                    <span className={cn('text-[9px] px-1.5 py-0.5 rounded border font-mono uppercase font-bold bg-transparent', diffStyle)}>
                      {scenario.difficulty}
                    </span>
                  </div>
                  <h3 className="text-base font-display font-bold text-slate-100">{scenario.title}</h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">{scenario.subtitle}</p>
                </div>
                <div className="shrink-0 text-right">
                  <div className="flex items-center gap-1 justify-end">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <span className="text-[10px] font-mono text-slate-500">{scenario.estimatedMinutes}m</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-slate-400 mb-4 line-clamp-2 leading-relaxed">{scenario.background}</p>

              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <div className="flex items-center gap-1.5">
                  <Flame className={cn('w-3 h-3', actorColor)} />
                  <span className={cn('text-[10px] font-mono font-bold', actorColor)}>
                    {THREAT_ACTOR_LABELS[scenario.threatActor]}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[10px] text-slate-500 font-mono">
                  <BookOpen className="w-3 h-3" />
                  {scenario.phases.length} phases · {totalDecisions} decision points
                </div>
                <div className="flex items-center gap-1 text-[10px] text-slate-500 font-mono">
                  <Users className="w-3 h-3" />
                  {scenario.roles.join(' · ')}
                </div>
              </div>

              <div className="flex items-center gap-2 mb-4 flex-wrap">
                {scenario.mitreTags.slice(0, 3).map((tag) => (
                  <span key={tag.id} className="text-[9px] px-1.5 py-0.5 rounded font-mono bg-slate-800 border border-slate-700 text-slate-400">
                    {tag.id}
                  </span>
                ))}
                {scenario.mitreTags.length > 3 && (
                  <span className="text-[9px] text-slate-600 font-mono">+{scenario.mitreTags.length - 3} more</span>
                )}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <span className="text-[9px] font-mono text-slate-600 flex items-center gap-1.5">
                  <Globe className="w-3 h-3" />
                  {scenario.sourceRef.split(' · ')[0]}
                </span>
                <Link href={`/crisis-simulator/${scenario.id}`}>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold transition-colors"
                    style={{ background: 'rgba(245,245,245,0.08)', border: '1px solid rgba(245,245,245,0.15)', color: '#f5f5f5' }}>
                    <Zap className="w-3 h-3" />
                    Launch Simulation
                    <ChevronRight className="w-3 h-3" />
                  </button>
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="sentra-panel p-16 text-center">
          <AlertTriangle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">No scenarios match the selected filters.</p>
        </div>
      )}

      <div className="sentra-panel p-5 border-[#c9b787]/20" style={{ borderColor: 'rgba(201,183,135,0.15)' }}>
        <div className="flex items-start gap-4">
          <Shield className="w-5 h-5 text-[#c9b787] shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-slate-200 mb-1">Intelligence Sources</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              All scenarios are modeled from real adversary TTPs: <span className="text-slate-400">MITRE ATT&CK adversary profiles</span>, <span className="text-slate-400">NSA/CISA/FBI joint advisories</span>, <span className="text-slate-400">CISA Tabletop Exercise Packages (CTEPs)</span>, <span className="text-slate-400">FCEB Red Team findings (AA24-193A)</span>, and <span className="text-slate-400">ICS-CERT OT advisories</span>. Scenarios are for organizational preparedness training only — not penetration testing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
