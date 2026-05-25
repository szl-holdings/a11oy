import {
  Calendar,
  CheckCircle,
  Clock,
  MessageSquare,
  RotateCcw,
  Target,
  TrendingUp,
  User,
  XCircle,
} from 'lucide-react';

const BG = { surface: 'var(--gi-bg-surface)', elevated: 'var(--gi-bg-raised)' };
const BORDER = { subtle: 'rgba(255,255,255,0.04)', muted: 'rgba(255,255,255,0.07)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.55)',
  tertiary: 'rgba(255,255,255,0.28)',
  muted: 'rgba(255,255,255,0.14)',
};

export type OutcomeResult = 'achieved' | 'partial' | 'missed' | 'pending' | 'exceeded';

export interface OutcomeRecord {
  id: string;
  result: OutcomeResult;
  executedAction: string;
  executedAt: string;
  executedBy: string;
  executedByRole: string;
  outcomeRecordedAt?: string;
  predictedImpact: string;
  actualImpact?: string;
  accuracy?: number;
  feedbackNote?: string;
  laterImpact?: string;
  timeToOutcome?: string;
}

const RESULT_CFG: Record<
  OutcomeResult,
  { color: string; bg: string; icon: typeof CheckCircle; label: string }
> = {
  achieved: { color: '#6b8f71', bg: 'rgba(107,143,113,0.1)', icon: CheckCircle, label: 'Achieved' },
  exceeded: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', icon: TrendingUp, label: 'Exceeded' },
  partial: { color: '#c8953c', bg: 'rgba(200,149,60,0.1)', icon: Clock, label: 'Partial' },
  missed: { color: '#c45a4a', bg: 'rgba(196,90,74,0.1)', icon: XCircle, label: 'Missed' },
  pending: { color: TEXT.tertiary, bg: 'rgba(255,255,255,0.03)', icon: Clock, label: 'Pending' },
};

interface OutcomePanelProps {
  outcome: OutcomeRecord;
  compact?: boolean;
}

export function OutcomePanel({ outcome, compact }: OutcomePanelProps) {
  const cfg = RESULT_CFG[outcome.result];
  const ResultIcon = cfg.icon;

  if (compact) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-3.5 h-3.5" style={{ color: '#6b8f71' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: '#6b8f71' }}
          >
            Outcome
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}
          >
            <ResultIcon className="w-3.5 h-3.5" style={{ color: cfg.color }} />
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold" style={{ color: cfg.color }}>
              {cfg.label}
            </div>
            {outcome.actualImpact && (
              <div className="text-[9px]" style={{ color: TEXT.tertiary }}>
                {outcome.actualImpact}
              </div>
            )}
          </div>
          {outcome.accuracy != null && (
            <div className="text-right">
              <div
                className="text-sm font-bold font-mono"
                style={{ color: outcome.accuracy >= 80 ? '#6b8f71' : '#c8953c' }}
              >
                {outcome.accuracy}%
              </div>
              <div className="text-[8px]" style={{ color: TEXT.muted }}>
                Accuracy
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
    >
      <div
        className="flex items-center gap-2 px-5 py-3"
        style={{ borderBottom: `1px solid ${BORDER.subtle}` }}
      >
        <Target className="w-4 h-4" style={{ color: '#6b8f71' }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: '#6b8f71' }}>
          Outcome — Post-Execution Record
        </span>
      </div>

      <div className="p-5">
        <div className="flex items-start gap-4 mb-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: cfg.bg, border: `2px solid ${cfg.color}` }}
          >
            <ResultIcon className="w-5 h-5" style={{ color: cfg.color }} />
          </div>
          <div className="flex-1">
            <div className="text-lg font-bold mb-0.5" style={{ color: cfg.color }}>
              {cfg.label}
            </div>
            <div className="text-xs" style={{ color: TEXT.secondary }}>
              {outcome.executedAction}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div>
            <div
              className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
              style={{ color: TEXT.muted }}
            >
              Predicted
            </div>
            <div className="text-xs font-semibold" style={{ color: TEXT.secondary }}>
              {outcome.predictedImpact}
            </div>
          </div>
          <div>
            <div
              className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
              style={{ color: TEXT.muted }}
            >
              Actual
            </div>
            <div
              className="text-xs font-semibold"
              style={{ color: outcome.actualImpact ? cfg.color : TEXT.muted }}
            >
              {outcome.actualImpact ?? 'Pending'}
            </div>
          </div>
          {outcome.accuracy != null && (
            <div>
              <div
                className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
                style={{ color: TEXT.muted }}
              >
                Prediction Accuracy
              </div>
              <div className="flex items-center gap-1">
                <div
                  className="flex-1 h-1.5 rounded-full overflow-hidden"
                  style={{ background: 'rgba(255,255,255,0.04)' }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${outcome.accuracy}%`,
                      background: outcome.accuracy >= 80 ? '#6b8f71' : '#c8953c',
                    }}
                  />
                </div>
                <span
                  className="text-xs font-mono font-bold"
                  style={{ color: outcome.accuracy >= 80 ? '#6b8f71' : '#c8953c' }}
                >
                  {outcome.accuracy}%
                </span>
              </div>
            </div>
          )}
          {outcome.timeToOutcome && (
            <div>
              <div
                className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
                style={{ color: TEXT.muted }}
              >
                Time to Outcome
              </div>
              <div className="text-xs font-semibold" style={{ color: TEXT.secondary }}>
                {outcome.timeToOutcome}
              </div>
            </div>
          )}
        </div>

        <div
          className="flex items-center gap-4 pt-3"
          style={{ borderTop: `1px solid ${BORDER.subtle}` }}
        >
          <div className="flex items-center gap-2">
            <User className="w-3 h-3" style={{ color: TEXT.tertiary }} />
            <span className="text-[10px]" style={{ color: TEXT.secondary }}>
              {outcome.executedBy}
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${BORDER.muted}`,
                color: TEXT.tertiary,
              }}
            >
              {outcome.executedByRole}
            </span>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <Calendar className="w-3 h-3" style={{ color: TEXT.tertiary }} />
            <span className="text-[10px] font-mono" style={{ color: TEXT.tertiary }}>
              {outcome.executedAt}
            </span>
          </div>
        </div>

        {outcome.feedbackNote && (
          <div
            className="mt-3 p-3 rounded-lg"
            style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${BORDER.subtle}` }}
          >
            <div className="flex items-center gap-2 mb-1">
              <MessageSquare className="w-3 h-3" style={{ color: TEXT.tertiary }} />
              <span
                className="text-[9px] font-bold uppercase tracking-wider"
                style={{ color: TEXT.muted }}
              >
                Operator Feedback
              </span>
            </div>
            <div className="text-[10px] italic" style={{ color: TEXT.secondary }}>
              "{outcome.feedbackNote}"
            </div>
          </div>
        )}

        {outcome.laterImpact && (
          <div
            className="mt-2 flex items-center gap-2 p-2.5 rounded-lg"
            style={{
              background: 'rgba(107,143,113,0.05)',
              border: '1px solid rgba(107,143,113,0.12)',
            }}
          >
            <RotateCcw className="w-3 h-3" style={{ color: '#6b8f71' }} />
            <span className="text-[10px]" style={{ color: '#6b8f71' }}>
              Downstream: {outcome.laterImpact}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
