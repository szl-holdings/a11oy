import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  Scale,
  Shield,
} from 'lucide-react';
import { Link } from 'wouter';

const BG = { surface: 'var(--gi-bg-surface)', elevated: 'var(--gi-bg-raised)' };
const BORDER = { subtle: 'rgba(255,255,255,0.04)', muted: 'rgba(255,255,255,0.07)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.55)',
  tertiary: 'rgba(255,255,255,0.28)',
  muted: 'rgba(255,255,255,0.14)',
};
const ACCENT = '#d4a054';

const DEMO_STATS = {
  decisionsThisWeek: 23,
  approved: 18,
  pending: 3,
  escalated: 2,
  avgConfidence: 81,
  avgAccuracy: 89,
  totalProtected: '$14.2M',
};

const RECENT_DECISIONS = [
  {
    id: 'REC-0421',
    title: 'Vessel reroute — M/V Meridian',
    outcome: 'achieved' as const,
    pack: 'SEXTANT',
    color: '#38bdf8',
    impact: '$2.1M protected',
  },
  {
    id: 'REC-0419',
    title: 'Contract renewal acceleration',
    outcome: 'achieved' as const,
    pack: 'PRAXIS',
    color: '#d4a054',
    impact: '$890K secured',
  },
  {
    id: 'REC-0418',
    title: 'Security posture remediation',
    outcome: 'achieved' as const,
    pack: 'PARAGON',
    color: '#4f6ef7',
    impact: '94% → 97% score',
  },
];

const OUTCOME_CFG = {
  achieved: { color: '#6b8f71', icon: CheckCircle },
  pending: { color: '#c8953c', icon: Clock },
  missed: { color: '#c45a4a', icon: AlertTriangle },
};

export function GovernedDecisionSummary() {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
    >
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ borderBottom: `1px solid ${BORDER.subtle}` }}
      >
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4" style={{ color: ACCENT }} />
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
            Governed Decision Loop
          </span>
        </div>
        <Link
          href="/operations/governed-decision-loop"
          className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded"
          style={{ color: ACCENT, background: `${ACCENT}10`, border: `1px solid ${ACCENT}25` }}
        >
          Full View <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      <div className="p-5">
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            {
              label: 'Decisions',
              value: DEMO_STATS.decisionsThisWeek,
              color: ACCENT,
              icon: Activity,
            },
            { label: 'Approved', value: DEMO_STATS.approved, color: '#6b8f71', icon: CheckCircle },
            { label: 'Pending', value: DEMO_STATS.pending, color: '#c8953c', icon: Clock },
            {
              label: 'Protected',
              value: DEMO_STATS.totalProtected,
              color: '#8b7ac8',
              icon: Shield,
            },
          ].map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="text-center p-2 rounded-lg"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${BORDER.subtle}`,
                }}
              >
                <Icon className="w-3 h-3 mx-auto mb-1" style={{ color: s.color }} />
                <div className="text-lg font-bold font-mono" style={{ color: s.color }}>
                  {s.value}
                </div>
                <div className="text-[8px] uppercase tracking-wider" style={{ color: TEXT.muted }}>
                  {s.label}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-4 mb-4">
          <div>
            <div
              className="text-[8px] font-mono uppercase tracking-wider"
              style={{ color: TEXT.muted }}
            >
              Avg Confidence
            </div>
            <div className="flex items-center gap-1 mt-0.5">
              <div
                className="w-12 h-1 rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.04)' }}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${DEMO_STATS.avgConfidence}%`, background: '#8b7ac8' }}
                />
              </div>
              <span className="text-[10px] font-mono font-bold" style={{ color: '#8b7ac8' }}>
                {DEMO_STATS.avgConfidence}%
              </span>
            </div>
          </div>
          <div>
            <div
              className="text-[8px] font-mono uppercase tracking-wider"
              style={{ color: TEXT.muted }}
            >
              Prediction Accuracy
            </div>
            <div className="flex items-center gap-1 mt-0.5">
              <div
                className="w-12 h-1 rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.04)' }}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${DEMO_STATS.avgAccuracy}%`, background: '#6b8f71' }}
                />
              </div>
              <span className="text-[10px] font-mono font-bold" style={{ color: '#6b8f71' }}>
                {DEMO_STATS.avgAccuracy}%
              </span>
            </div>
          </div>
        </div>

        <div
          className="text-[9px] font-bold uppercase tracking-widest mb-2"
          style={{ color: TEXT.muted }}
        >
          Recent Outcomes
        </div>
        <div className="space-y-1.5">
          {RECENT_DECISIONS.map((d) => {
            const cfg = OUTCOME_CFG[d.outcome];
            const Icon = cfg.icon;
            return (
              <div
                key={d.id}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${BORDER.subtle}`,
                }}
              >
                <Icon className="w-3 h-3 shrink-0" style={{ color: cfg.color }} />
                <span
                  className="text-[9px] px-1 py-0.5 rounded shrink-0"
                  style={{
                    background: `${d.color}12`,
                    color: d.color,
                    border: `1px solid ${d.color}25`,
                  }}
                >
                  {d.pack}
                </span>
                <span className="text-[10px] flex-1 truncate" style={{ color: TEXT.secondary }}>
                  {d.title}
                </span>
                <span className="text-[9px] font-mono shrink-0" style={{ color: cfg.color }}>
                  {d.impact}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
