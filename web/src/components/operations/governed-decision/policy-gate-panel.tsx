import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Scale,
  User,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

const BG = { surface: 'var(--gi-bg-surface)', elevated: 'var(--gi-bg-raised)' };
const BORDER = { subtle: 'rgba(255,255,255,0.04)', muted: 'rgba(255,255,255,0.07)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.55)',
  tertiary: 'rgba(255,255,255,0.28)',
  muted: 'rgba(255,255,255,0.14)',
};

export type PolicyOutcome = 'approved' | 'denied' | 'escalated' | 'pending';

export interface PolicyEvaluation {
  policyId: string;
  policyName: string;
  outcome: PolicyOutcome;
  reason: string;
  evaluatedAt: string;
  durationMs: number;
}

export interface ApprovalStep {
  role: string;
  approver: string;
  status: 'approved' | 'pending' | 'rejected';
  timestamp?: string;
  comment?: string;
}

export interface EscalationPath {
  from: string;
  to: string;
  reason: string;
  triggeredAt: string;
}

export interface AuditEntry {
  timestamp: string;
  action: string;
  actor: string;
  detail?: string;
}

export interface PolicyGatePanelProps {
  finalOutcome: PolicyOutcome;
  evaluations: PolicyEvaluation[];
  approvalChain: ApprovalStep[];
  escalation?: EscalationPath;
  auditTrail: AuditEntry[];
  compact?: boolean;
}

const OUTCOME_CFG: Record<
  PolicyOutcome,
  { color: string; bg: string; icon: typeof CheckCircle; label: string }
> = {
  approved: { color: '#6b8f71', bg: 'rgba(107,143,113,0.1)', icon: CheckCircle, label: 'Approved' },
  denied: { color: '#c45a4a', bg: 'rgba(196,90,74,0.1)', icon: XCircle, label: 'Denied' },
  escalated: {
    color: '#ec4899',
    bg: 'rgba(236,72,153,0.1)',
    icon: AlertTriangle,
    label: 'Escalated',
  },
  pending: { color: '#c8953c', bg: 'rgba(200,149,60,0.1)', icon: Clock, label: 'Pending' },
};

export function PolicyGatePanel({
  finalOutcome,
  evaluations,
  approvalChain,
  escalation,
  auditTrail,
  compact,
}: PolicyGatePanelProps) {
  const [showAudit, setShowAudit] = useState(false);
  const outcomeCfg = OUTCOME_CFG[finalOutcome];
  const OutcomeIcon = outcomeCfg.icon;

  if (compact) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Scale className="w-3.5 h-3.5" style={{ color: '#d4a054' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: '#d4a054' }}
          >
            Covenant Policy Gate
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: outcomeCfg.bg, border: `1px solid ${outcomeCfg.color}30` }}
          >
            <OutcomeIcon className="w-3.5 h-3.5" style={{ color: outcomeCfg.color }} />
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: outcomeCfg.color }}>
              {outcomeCfg.label}
            </div>
            <div className="text-[9px]" style={{ color: TEXT.tertiary }}>
              {evaluations.length} policies evaluated
            </div>
          </div>
          <div className="ml-auto flex -space-x-1">
            {approvalChain.map((step, i) => {
              const stepCfg =
                step.status === 'approved'
                  ? OUTCOME_CFG.approved
                  : step.status === 'rejected'
                    ? OUTCOME_CFG.denied
                    : OUTCOME_CFG.pending;
              const StepIcon = stepCfg.icon;
              return (
                <div
                  key={i}
                  className="w-5 h-5 rounded-full flex items-center justify-center"
                  style={{ background: stepCfg.bg, border: `2px solid ${stepCfg.color}` }}
                >
                  <StepIcon className="w-2.5 h-2.5" style={{ color: stepCfg.color }} />
                </div>
              );
            })}
          </div>
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
        <Scale className="w-4 h-4" style={{ color: '#d4a054' }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: '#d4a054' }}>
          Covenant Policy Gate
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span
            className="text-[9px] font-bold px-2 py-0.5 rounded"
            style={{ color: outcomeCfg.color, background: outcomeCfg.bg }}
          >
            {outcomeCfg.label.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="p-5">
        <div
          className="text-[9px] font-bold uppercase tracking-widest mb-2"
          style={{ color: TEXT.muted }}
        >
          Policy Evaluations
        </div>
        <div className="space-y-2 mb-4">
          {evaluations.map((ev) => {
            const evCfg = OUTCOME_CFG[ev.outcome];
            const EvIcon = evCfg.icon;
            return (
              <div
                key={ev.policyId}
                className="flex items-center gap-3 p-2.5 rounded-lg"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${BORDER.subtle}`,
                }}
              >
                <EvIcon className="w-3.5 h-3.5 shrink-0" style={{ color: evCfg.color }} />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-semibold" style={{ color: TEXT.primary }}>
                    {ev.policyName}
                  </div>
                  <div className="text-[9px]" style={{ color: TEXT.tertiary }}>
                    {ev.reason}
                  </div>
                </div>
                <span className="text-[9px] font-mono shrink-0" style={{ color: TEXT.muted }}>
                  {ev.durationMs}ms
                </span>
              </div>
            );
          })}
        </div>

        <div
          className="text-[9px] font-bold uppercase tracking-widest mb-2"
          style={{ color: TEXT.muted }}
        >
          Approval Chain
        </div>
        <div className="flex flex-col gap-2 mb-4">
          {approvalChain.map((step, i) => {
            const stepCfg =
              step.status === 'approved'
                ? OUTCOME_CFG.approved
                : step.status === 'rejected'
                  ? OUTCOME_CFG.denied
                  : OUTCOME_CFG.pending;
            const StepIcon = stepCfg.icon;
            return (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center"
                    style={{ background: stepCfg.bg, border: `2px solid ${stepCfg.color}` }}
                  >
                    <StepIcon className="w-3 h-3" style={{ color: stepCfg.color }} />
                  </div>
                  {i < approvalChain.length - 1 && (
                    <div
                      className="w-px flex-1 my-1"
                      style={{ background: BORDER.muted, minHeight: 16 }}
                    />
                  )}
                </div>
                <div className="flex-1 pb-2">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[10px] font-semibold" style={{ color: TEXT.primary }}>
                      {step.role}
                    </span>
                    <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
                      — {step.approver}
                    </span>
                    {step.timestamp && (
                      <span className="text-[9px] ml-auto font-mono" style={{ color: TEXT.muted }}>
                        {step.timestamp}
                      </span>
                    )}
                  </div>
                  {step.comment && (
                    <div className="text-[9px] italic" style={{ color: TEXT.tertiary }}>
                      "{step.comment}"
                    </div>
                  )}
                  {step.status === 'pending' &&
                    i > 0 &&
                    approvalChain[i - 1]?.status === 'approved' && (
                      <div className="flex gap-2 mt-1.5">
                        <button
                          className="px-2.5 py-1 rounded text-[9px] font-bold"
                          style={{ background: '#6b8f71', color: '#fff' }}
                        >
                          Approve
                        </button>
                        <button
                          className="px-2.5 py-1 rounded text-[9px]"
                          style={{
                            background: 'rgba(255,255,255,0.03)',
                            border: `1px solid ${BORDER.muted}`,
                            color: '#c45a4a',
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                </div>
              </div>
            );
          })}
        </div>

        {escalation && (
          <div
            className="p-3 rounded-lg mb-4"
            style={{
              background: 'rgba(236,72,153,0.05)',
              border: '1px solid rgba(236,72,153,0.15)',
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-3 h-3" style={{ color: '#ec4899' }} />
              <span className="text-[10px] font-bold" style={{ color: '#ec4899' }}>
                Escalation
              </span>
            </div>
            <div className="text-[10px]" style={{ color: TEXT.secondary }}>
              {escalation.from}{' '}
              <ArrowRight className="w-3 h-3 inline mx-1" style={{ color: TEXT.muted }} />{' '}
              {escalation.to}
            </div>
            <div className="text-[9px] mt-0.5" style={{ color: TEXT.tertiary }}>
              {escalation.reason} · {escalation.triggeredAt}
            </div>
          </div>
        )}

        <button
          onClick={() => setShowAudit(!showAudit)}
          className="flex items-center gap-1.5 text-[10px] font-medium"
          style={{ color: '#d4a054' }}
          aria-expanded={showAudit}
          aria-label={`${showAudit ? 'Hide' : 'Show'} audit trail`}
        >
          {showAudit ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Audit Trail ({auditTrail.length} events)
        </button>

        {showAudit && (
          <div className="mt-2 space-y-1">
            {auditTrail.map((entry, i) => (
              <div
                key={i}
                className="flex items-center gap-3 py-1.5 px-2 rounded"
                style={{ background: i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent' }}
              >
                <span className="text-[9px] font-mono w-16 shrink-0" style={{ color: TEXT.muted }}>
                  {entry.timestamp}
                </span>
                <User className="w-2.5 h-2.5 shrink-0" style={{ color: TEXT.tertiary }} />
                <span className="text-[10px] flex-1" style={{ color: TEXT.secondary }}>
                  {entry.action}
                </span>
                <span className="text-[9px] shrink-0" style={{ color: '#d4a054' }}>
                  {entry.actor}
                </span>
              </div>
            ))}
            <div
              className="flex items-center gap-1.5 pt-2 mt-1"
              style={{ borderTop: `1px solid ${BORDER.subtle}` }}
            >
              <span
                className="text-[7px] font-mono px-1.5 py-0.5 rounded"
                style={{
                  background: 'rgba(212,160,84,0.05)',
                  border: '1px solid rgba(212,160,84,0.12)',
                  color: 'rgba(212,160,84,0.45)',
                }}
              >
                synthetic · demo scenario
              </span>
              <span className="text-[7px] font-mono" style={{ color: TEXT.muted }}>
                No live systems connected — audit log is illustrative
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
