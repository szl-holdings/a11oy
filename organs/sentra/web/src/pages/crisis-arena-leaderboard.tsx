import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  BarChart2,
  ChevronRight,
  ExternalLink,
  Globe,
  Loader2,
  Shield,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'wouter';

const BASE = '/api';

type ArchetypeBadge = 'Black Swan' | 'Cascade' | 'Insider' | 'Regulator';

interface LeaderboardEntry {
  rank: number;
  id: string;
  handle: string;
  displayName: string;
  reputationScore: number;
  acceptedCount: number;
  submissionCount: number;
  totalImpactUsd: number;
  badges: ArchetypeBadge[];
  topScenarioTitles: string[];
}

interface MonthlyMover {
  architectId: string;
  handle: string;
  gain: number;
}

interface LeaderboardData {
  leaderboard: LeaderboardEntry[];
  monthlyMovers: MonthlyMover[];
  totalImpactUsd: number;
  totalAccepted: number;
  totalArchitects: number;
  archetypeSpecialists: Record<string, { handle: string; count: number }>;
  generatedAt: string;
}

interface SummaryData {
  totalArchitects: number;
  totalImpactUsd: number;
  totalAccepted: number;
  openEngagements: number;
  pendingSubmissions: number;
  topArchitect: string | null;
}

const BADGE_STYLE: Record<ArchetypeBadge, { bg: string; text: string; border: string }> = {
  'Black Swan': { bg: 'bg-[color:var(--gi-error-bg)]', text: 'text-[color:var(--gi-accent-red)]', border: 'border-[color:var(--gi-error-border)]' },
  Cascade:      { bg: 'bg-[color:var(--gi-warning-bg)]', text: 'text-[color:var(--gi-accent-amber)]', border: 'border-[color:var(--gi-warning-border)]' },
  Insider:      { bg: 'bg-[color:var(--gi-warning-bg)]', text: 'text-[color:var(--gi-accent-amber)]', border: 'border-[color:var(--gi-warning-border)]' },
  Regulator:    { bg: 'bg-[color:var(--gi-neutral-bg)]', text: 'text-[color:var(--gi-accent-violet)]', border: 'border-[color:var(--gi-neutral-border)]' },
};

function formatUsd(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

export default function CrisisArenaLeaderboard() {
  const [data, setData] = useState<LeaderboardData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LeaderboardEntry | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [lbRes, sumRes] = await Promise.all([
          fetch(`${BASE}/crisis-arena/leaderboard`),
          fetch(`${BASE}/crisis-arena/summary`),
        ]);
        if (lbRes.ok) setData(await lbRes.json() as LeaderboardData);
        if (sumRes.ok) setSummary(await sumRes.json() as SummaryData);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: 'var(--gi-bg-base)', color: 'var(--gi-text-primary)' }}>
      <section className="relative px-6 pt-16 pb-10 border-b" style={{ borderColor: 'var(--gi-border-subtle)' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: 'var(--gi-error-bg)', border: '1px solid var(--gi-error-border)' }}>
              <Activity className="w-3.5 h-3.5" style={{ color: 'var(--gi-accent-red)' }} />
            </div>
            <span className="text-xs font-mono uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>Sentra · Adversarial Simulation Program</span>
          </div>
          <h1 className="text-2xl font-bold mb-2" style={{ letterSpacing: '-0.02em', color: 'var(--gi-text-primary)' }}>
            Analyst Performance Registry
          </h1>
          <p className="text-sm leading-relaxed mb-6 max-w-xl" style={{ color: 'var(--gi-text-secondary)' }}>
            Scenario analysts ranked by accepted submissions, business impact surfaced, and archetype coverage across active engagements.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <Link href="/crisis-arena/engagements">
              <button className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md transition-colors" style={{ background: 'var(--gi-accent-red)', color: 'var(--gi-bg-base)' }}>
                Active Engagements <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </Link>
            <Link href="/crisis-arena/architect">
              <button className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-md transition-colors" style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-default)', color: 'var(--gi-text-secondary)' }}>
                Analyst Workspace
              </button>
            </Link>
          </div>
        </div>
      </section>

      {summary && (
        <section className="px-6 py-8 max-w-5xl mx-auto border-b" style={{ borderColor: 'var(--gi-border-subtle)' }}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: Globe, label: 'Impact Surfaced', value: formatUsd(summary.totalImpactUsd), accent: 'var(--gi-accent-red)' },
              { icon: BarChart2, label: 'Accepted Scenarios', value: summary.totalAccepted.toString(), accent: 'var(--gi-accent-amber)' },
              { icon: Users, label: 'Registered Analysts', value: summary.totalArchitects.toString(), accent: 'var(--gi-accent-violet)' },
              { icon: Shield, label: 'Open Engagements', value: summary.openEngagements.toString(), accent: 'var(--gi-accent-green)' },
            ].map((stat) => (
              <div
                key={stat.label}
                className="rounded-lg p-4"
                style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-subtle)' }}
              >
                <stat.icon className="w-4 h-4 mb-2" style={{ color: stat.accent }} />
                <div className="text-xl font-bold font-mono mb-0.5" style={{ color: 'var(--gi-text-primary)' }}>{stat.value}</div>
                <div className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="px-6 pb-16 max-w-5xl mx-auto">
        <div className="flex items-center justify-between mt-8 mb-5">
          <h2 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--gi-text-primary)' }}>
            <TrendingUp className="w-4 h-4" style={{ color: 'var(--gi-accent-amber)' }} />
            Analyst Rankings
          </h2>
          <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>
            Ranked by Performance Score
          </span>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--gi-text-muted)' }} />
          </div>
        )}

        {!loading && data && (
          <div className="space-y-2">
            {data.leaderboard.map((entry) => (
              <div
                key={entry.id}
                className="rounded-lg p-4 cursor-pointer transition-all"
                style={{
                  background: 'var(--gi-bg-surface)',
                  border: selected?.id === entry.id
                    ? '1px solid var(--gi-border-strong)'
                    : '1px solid var(--gi-border-subtle)',
                }}
                onClick={() => setSelected(selected?.id === entry.id ? null : entry)}
              >
                <div className="flex items-center gap-4">
                  <div className="text-xs font-mono w-8 text-center shrink-0" style={{ color: 'var(--gi-text-muted)' }}>
                    #{entry.rank}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-semibold" style={{ color: 'var(--gi-text-primary)' }}>{entry.displayName}</span>
                      <span className="text-[11px] font-mono" style={{ color: 'var(--gi-text-muted)' }}>@{entry.handle}</span>
                      {entry.badges.map((b) => (
                        <span
                          key={b}
                          className={cn(
                            'px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border',
                            BADGE_STYLE[b].bg,
                            BADGE_STYLE[b].text,
                            BADGE_STYLE[b].border,
                          )}
                        >
                          {b}
                        </span>
                      ))}
                    </div>
                    {entry.topScenarioTitles[0] && (
                      <p className="text-[11px] truncate" style={{ color: 'var(--gi-text-muted)' }}>
                        Lead scenario: {entry.topScenarioTitles[0]}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-5 shrink-0">
                    <div className="text-center">
                      <div className="text-sm font-bold font-mono" style={{ color: 'var(--gi-text-primary)' }}>
                        {entry.reputationScore.toLocaleString()}
                      </div>
                      <div className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>Score</div>
                    </div>
                    <div className="text-center hidden sm:block">
                      <div className="text-sm font-bold font-mono" style={{ color: 'var(--gi-accent-amber)' }}>
                        {entry.acceptedCount}
                      </div>
                      <div className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>
                        Accepted
                      </div>
                    </div>
                    <div className="text-center hidden md:block">
                      <div className="text-sm font-bold font-mono" style={{ color: 'var(--gi-accent-green)' }}>
                        {formatUsd(entry.totalImpactUsd)}
                      </div>
                      <div className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>
                        Impact
                      </div>
                    </div>
                    <Link
                      href={`/crisis-arena/architect/${entry.id}`}
                      onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                      <ExternalLink className="w-3.5 h-3.5 transition-colors" style={{ color: 'var(--gi-text-muted)' }} />
                    </Link>
                  </div>
                </div>

                {selected?.id === entry.id && (
                  <div className="mt-4 pt-4 grid grid-cols-1 md:grid-cols-2 gap-4" style={{ borderTop: '1px solid var(--gi-border-subtle)' }}>
                    <div>
                      <div className="text-[10px] font-mono uppercase mb-2" style={{ color: 'var(--gi-text-muted)' }}>
                        Top Scenarios
                      </div>
                      <ul className="space-y-1.5">
                        {entry.topScenarioTitles.map((t, i) => (
                          <li key={i} className="flex items-start gap-2 text-[11px]" style={{ color: 'var(--gi-text-secondary)' }}>
                            <span className="w-3.5 h-3.5 flex items-center justify-center shrink-0 mt-0.5 text-[9px] font-mono" style={{ color: 'var(--gi-text-muted)' }}>{i + 1}.</span>
                            {t}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="text-[10px] font-mono uppercase mb-2" style={{ color: 'var(--gi-text-muted)' }}>
                        Performance Metrics
                      </div>
                      <div className="space-y-1.5 text-[11px]">
                        <div className="flex justify-between">
                          <span style={{ color: 'var(--gi-text-muted)' }}>Total Submissions</span>
                          <span className="font-mono" style={{ color: 'var(--gi-text-primary)' }}>{entry.submissionCount}</span>
                        </div>
                        <div className="flex justify-between">
                          <span style={{ color: 'var(--gi-text-muted)' }}>Accepted</span>
                          <span className="font-mono" style={{ color: 'var(--gi-accent-green)' }}>{entry.acceptedCount}</span>
                        </div>
                        <div className="flex justify-between">
                          <span style={{ color: 'var(--gi-text-muted)' }}>Acceptance Rate</span>
                          <span className="font-mono" style={{ color: 'var(--gi-text-primary)' }}>
                            {entry.submissionCount > 0
                              ? Math.round((entry.acceptedCount / entry.submissionCount) * 100)
                              : 0}
                            %
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span style={{ color: 'var(--gi-text-muted)' }}>Impact Surfaced</span>
                          <span className="font-mono" style={{ color: 'var(--gi-accent-amber)' }}>
                            {formatUsd(entry.totalImpactUsd)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && data?.monthlyMovers && data.monthlyMovers.length > 0 && (
          <div className="mt-10">
            <h2 className="text-sm font-bold flex items-center gap-2 mb-5" style={{ color: 'var(--gi-text-primary)' }}>
              <Activity className="w-4 h-4" style={{ color: 'var(--gi-accent-green)' }} />
              Period Momentum
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {data.monthlyMovers.map((mover, i) => (
                <div
                  key={mover.architectId}
                  className="rounded-lg p-4"
                  style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-subtle)' }}
                >
                  <div className="text-[10px] font-mono uppercase tracking-wider mb-2" style={{ color: 'var(--gi-text-muted)' }}>
                    #{i + 1} this period
                  </div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--gi-text-primary)' }}>@{mover.handle}</div>
                  <div className="text-[11px] mt-1" style={{ color: 'var(--gi-accent-green)' }}>
                    +{mover.gain.toFixed(0)} pts
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!loading && data?.archetypeSpecialists && (
          <div className="mt-10">
            <h2 className="text-sm font-bold flex items-center gap-2 mb-5" style={{ color: 'var(--gi-text-primary)' }}>
              <BarChart2 className="w-4 h-4" style={{ color: 'var(--gi-accent-violet)' }} />
              Archetype Specialists
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(data.archetypeSpecialists).map(([arch, spec]) => (
                <div
                  key={arch}
                  className="rounded-lg p-4"
                  style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-subtle)' }}
                >
                  <div className="text-[10px] font-mono uppercase tracking-wider mb-2" style={{ color: 'var(--gi-text-muted)' }}>
                    {arch.replace('_', ' ')}
                  </div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--gi-text-primary)' }}>@{spec.handle}</div>
                  <div className="text-[11px] mt-1" style={{ color: 'var(--gi-text-muted)' }}>{spec.count} accepted</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-14 border-t pt-10" style={{ borderColor: 'var(--gi-border-subtle)' }}>
          <div className="rounded-lg px-6 py-6 max-w-xl" style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-default)' }}>
            <Activity className="w-6 h-6 mb-3" style={{ color: 'var(--gi-accent-red)' }} />
            <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--gi-text-primary)' }}>Submit Adversarial Scenarios</h3>
            <p className="text-xs leading-relaxed mb-5" style={{ color: 'var(--gi-text-secondary)' }}>
              Contribute crisis scenarios to active engagements. Accepted submissions are scored for business impact and archetype coverage, then graduated into live tabletop exercises.
            </p>
            <Link href="/crisis-arena/architect">
              <button className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md transition-colors" style={{ background: 'var(--gi-accent-red)', color: 'var(--gi-bg-base)' }}>
                Open Analyst Workspace <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
