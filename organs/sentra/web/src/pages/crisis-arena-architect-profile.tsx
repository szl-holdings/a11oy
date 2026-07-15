// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/sentra/src/pages/crisis-arena-architect-profile.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  BarChart2,
  ChevronLeft,
  Loader2,
  Shield,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'wouter';

const BASE = '/api';

type ThreatArchetype =
  | 'ransomware'
  | 'insider'
  | 'supply_chain'
  | 'regulatory'
  | 'cascade'
  | 'black_swan';
type ArchetypeBadge = 'Black Swan' | 'Cascade' | 'Insider' | 'Regulator';

interface ArchetypeStat {
  archetype: ThreatArchetype;
  badge: ArchetypeBadge;
  count: number;
  totalScore: number;
}

interface HighlightEntry {
  title: string;
  archetype: ThreatArchetype;
  businessImpactScore: number;
  blastRadius: string[];
  acceptedAt: string;
}

interface PublicArchitectProfile {
  id: string;
  handle: string;
  displayName: string;
  bio: string;
  reputationScore: number;
  acceptedCount: number;
  submissionCount: number;
  totalImpactUsd: number;
  badges: ArchetypeBadge[];
  archetypeStats: ArchetypeStat[];
  joinedAt: string;
  highlights: HighlightEntry[];
}

const BADGE_STYLE: Record<ArchetypeBadge, { bg: string; border: string; text: string }> = {
  'Black Swan': {
    bg: 'bg-[color:var(--gi-error-bg)]',
    border: 'border-[color:var(--gi-error-border)]',
    text: 'text-[color:var(--gi-error-text)]',
  },
  Cascade: {
    bg: 'bg-[color:var(--gi-warning-bg)]',
    border: 'border-[color:var(--gi-warning-border)]',
    text: 'text-[color:var(--gi-warning-text)]',
  },
  Insider: {
    bg: 'bg-[color:var(--gi-neutral-bg)]',
    border: 'border-[color:var(--gi-neutral-border)]',
    text: 'text-[color:var(--gi-neutral-text)]',
  },
  Regulator: {
    bg: 'bg-[color:var(--gi-accent-violet)]/10',
    border: 'border-[color:var(--gi-accent-violet)]/30',
    text: 'text-[color:var(--gi-accent-violet)]',
  },
};

const ARCHETYPE_COLORS: Record<ThreatArchetype, string> = {
  ransomware: 'text-[color:var(--gi-error-text)]',
  cascade: 'text-[color:var(--gi-warning-text)]',
  supply_chain: 'text-[color:var(--gi-accent-amber)]',
  regulatory: 'text-[color:var(--gi-accent-violet)]',
  insider: 'text-[color:var(--gi-accent-blue)]',
  black_swan: 'text-[color:var(--gi-error-text)]',
};

function formatUsd(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export default function CrisisArenaArchitectProfile() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? '';
  const [profile, setProfile] = useState<PublicArchitectProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    async function load() {
      setLoading(true);
      const res = await fetch(`${BASE}/crisis-arena/architects/${id}/public`);
      if (res.status === 404) {
        setNotFound(true);
      } else if (res.ok) {
        setProfile((await res.json()) as PublicArchitectProfile);
      }
      setLoading(false);
    }
    void load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <Loader2 className="w-6 h-6 text-[color:var(--gi-accent-blue)] animate-spin" />
      </div>
    );
  }

  if (notFound || !profile) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-4">
        <Shield className="w-10 h-10 text-[color:var(--gi-text-muted)]" />
        <p className="text-[color:var(--gi-text-muted)] text-sm">
          Analyst profile not found or is private.
        </p>
        <Link href="/crisis-arena/leaderboard">
          <button className="flex items-center gap-2 px-4 py-2 bg-[color:var(--gi-bg-surface)] border border-[color:var(--gi-border-default)] text-[color:var(--gi-text-secondary)] rounded-xl text-xs hover:border-[color:var(--gi-border-strong)] transition-colors">
            <ChevronLeft className="w-3.5 h-3.5" /> Back to Analyst Rankings
          </button>
        </Link>
      </div>
    );
  }

  const hitRate =
    profile.submissionCount > 0
      ? Math.round((profile.acceptedCount / profile.submissionCount) * 100)
      : 0;

  return (
    <div className="space-y-8 animate-fade-in p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <Link href="/crisis-arena/leaderboard">
          <button className="flex items-center gap-1.5 text-[11px] text-[color:var(--gi-text-muted)] hover:text-[color:var(--gi-text-secondary)] transition-colors">
            <ChevronLeft className="w-3.5 h-3.5" /> Analyst Rankings
          </button>
        </Link>
        <span className="text-[color:var(--gi-border-subtle)]">·</span>
        <span className="text-[11px] text-[color:var(--gi-text-muted)]">Analyst Profile</span>
      </div>

      <div className="bg-[color:var(--gi-bg-surface)] border border-[color:var(--gi-border-subtle)] rounded-2xl p-7">
        <div className="flex items-start gap-6 flex-wrap">
          <div className="w-16 h-16 rounded-2xl bg-[color:var(--gi-accent-blue)]/10 border border-[color:var(--gi-accent-blue)]/20 flex items-center justify-center shrink-0">
            <Activity className="w-7 h-7 text-[color:var(--gi-accent-blue)]" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <h1 className="text-2xl font-bold text-[color:var(--gi-text-primary)]">
                {profile.displayName}
              </h1>
              <span className="text-sm font-mono text-[color:var(--gi-text-muted)]">
                @{profile.handle}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap mb-3">
              {profile.badges.map((b) => (
                <span
                  key={b}
                  className={cn(
                    'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border',
                    BADGE_STYLE[b].bg,
                    BADGE_STYLE[b].text,
                    BADGE_STYLE[b].border,
                  )}
                >
                  {b}
                </span>
              ))}
            </div>
            {profile.bio && (
              <p className="text-sm text-[color:var(--gi-text-secondary)] leading-relaxed max-w-lg">
                {profile.bio}
              </p>
            )}
            <p className="text-[10px] text-[color:var(--gi-text-muted)] font-mono mt-2">
              Analyst since {new Date(profile.joinedAt).toLocaleDateString()}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <div className="text-3xl font-bold text-[color:var(--gi-accent-blue)] font-mono">
              {profile.reputationScore.toLocaleString()}
            </div>
            <div className="text-[10px] text-[color:var(--gi-text-muted)] uppercase tracking-wider">
              Performance Score
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: 'Accepted',
            value: profile.acceptedCount.toString(),
            icon: Users,
            color: 'text-[color:var(--gi-success-text)]',
          },
          {
            label: 'Submissions',
            value: profile.submissionCount.toString(),
            icon: Activity,
            color: 'text-[color:var(--gi-accent-blue)]',
          },
          {
            label: 'Acceptance Rate',
            value: `${hitRate}%`,
            icon: TrendingUp,
            color: 'text-[color:var(--gi-accent-amber)]',
          },
          {
            label: 'Total Impact',
            value: formatUsd(profile.totalImpactUsd),
            icon: Shield,
            color: 'text-[color:var(--gi-accent-violet)]',
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[color:var(--gi-bg-surface)] border border-[color:var(--gi-border-subtle)] rounded-xl p-4 text-center"
          >
            <stat.icon className={cn('w-4 h-4 mx-auto mb-2', stat.color)} />
            <div className="text-xl font-bold text-[color:var(--gi-text-primary)] font-mono">
              {stat.value}
            </div>
            <div className="text-[9px] text-[color:var(--gi-text-muted)] uppercase tracking-wider">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {profile.archetypeStats.length > 0 && (
        <div>
          <h2 className="text-[10px] text-[color:var(--gi-text-muted)] font-mono uppercase tracking-wider mb-4 flex items-center gap-2">
            <BarChart2 className="w-3.5 h-3.5" /> Threat Archetype Coverage
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {profile.archetypeStats.map((stat) => (
              <div
                key={stat.archetype}
                className="bg-[color:var(--gi-bg-surface)] border border-[color:var(--gi-border-subtle)] rounded-xl p-4"
              >
                <div
                  className={cn(
                    'text-[10px] font-mono uppercase tracking-wider mb-2',
                    ARCHETYPE_COLORS[stat.archetype],
                  )}
                >
                  {stat.archetype.replace('_', ' ')}
                </div>
                <div className="text-base font-bold text-[color:var(--gi-text-primary)]">
                  {stat.count} accepted
                </div>
                <div className="text-[10px] text-[color:var(--gi-text-muted)] mt-1">
                  Avg BIS: {stat.count > 0 ? Math.round(stat.totalScore / stat.count) : 0}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {profile.highlights.length > 0 && (
        <div>
          <h2 className="text-[10px] text-[color:var(--gi-text-muted)] font-mono uppercase tracking-wider mb-4 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-[color:var(--gi-accent-blue)]" /> Top Accepted
            Scenarios
          </h2>
          <div className="space-y-3">
            {profile.highlights.map((h, i) => (
              <div
                key={i}
                className="bg-[color:var(--gi-bg-surface)] border border-[color:var(--gi-border-subtle)] rounded-xl p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span
                        className={cn(
                          'text-[9px] font-mono uppercase tracking-wider',
                          ARCHETYPE_COLORS[h.archetype],
                        )}
                      >
                        {h.archetype.replace('_', ' ')}
                      </span>
                      <span className="text-[9px] text-[color:var(--gi-text-muted)]">
                        {relativeTime(h.acceptedAt)}
                      </span>
                    </div>
                    <div className="text-sm font-bold text-[color:var(--gi-text-primary)] mb-1">
                      {h.title}
                    </div>
                    <div className="text-[10px] text-[color:var(--gi-text-muted)] font-mono">
                      Blast radius: {h.blastRadius.join(', ')}
                    </div>
                  </div>
                  <div className="text-center shrink-0">
                    <div
                      className={cn(
                        'text-xl font-bold font-mono',
                        h.businessImpactScore >= 80
                          ? 'text-[color:var(--gi-error-text)]'
                          : h.businessImpactScore >= 60
                            ? 'text-[color:var(--gi-accent-amber)]'
                            : 'text-[color:var(--gi-text-secondary)]',
                      )}
                    >
                      {h.businessImpactScore}
                    </div>
                    <div className="text-[8px] text-[color:var(--gi-text-muted)] uppercase">
                      BIS
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-center pt-4">
        <Link href="/crisis-arena/leaderboard">
          <button className="flex items-center gap-2 px-5 py-2.5 bg-[color:var(--gi-bg-surface)] hover:border-[color:var(--gi-border-strong)] border border-[color:var(--gi-border-default)] text-[color:var(--gi-text-secondary)] font-medium rounded-xl transition-all text-sm">
            <Users className="w-4 h-4 text-[color:var(--gi-accent-blue)]" /> View Full Analyst
            Rankings
          </button>
        </Link>
      </div>
    </div>
  );
}
