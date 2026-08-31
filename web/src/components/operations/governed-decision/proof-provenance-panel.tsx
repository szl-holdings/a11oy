import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  Eye,
  FlaskConical,
  GitBranch,
  Link2,
  Shield,
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

export interface ProofEntry {
  id: string;
  sourceClass: 'llm_generated' | 'llm_summarized' | 'human_authored' | 'system_computed' | 'hybrid';
  contentType: string;
  modelId?: string;
  modelProvider?: string;
  confidenceScore: number;
  reviewState: 'unreviewed' | 'approved' | 'flagged' | 'retracted';
  exportSafety: 'safe' | 'pending_review' | 'restricted' | 'blocked';
  generatedAt: string;
  reviewedBy?: string;
  reviewedAt?: string;
  reviewNote?: string;
  inputSources: { type: string; label: string }[];
  parentProofId?: string;
}

const REVIEW_STATE_CFG = {
  unreviewed: { color: '#c8953c', bg: 'rgba(200,149,60,0.1)', icon: Clock, label: 'Unreviewed' },
  approved: { color: '#6b8f71', bg: 'rgba(107,143,113,0.1)', icon: CheckCircle, label: 'Approved' },
  flagged: { color: '#ec4899', bg: 'rgba(236,72,153,0.1)', icon: AlertTriangle, label: 'Flagged' },
  retracted: {
    color: '#c45a4a',
    bg: 'rgba(196,90,74,0.1)',
    icon: AlertTriangle,
    label: 'Retracted',
  },
};

const SOURCE_CLASS_LABELS: Record<string, string> = {
  llm_generated: 'AI Generated',
  llm_summarized: 'AI Summarized',
  human_authored: 'Human Authored',
  system_computed: 'System Computed',
  hybrid: 'Hybrid',
};

const EXPORT_SAFETY_CFG: Record<string, { color: string; label: string }> = {
  safe: { color: '#6b8f71', label: 'Export Safe' },
  pending_review: { color: '#c8953c', label: 'Pending Review' },
  restricted: { color: '#ec4899', label: 'Restricted' },
  blocked: { color: '#c45a4a', label: 'Blocked' },
};

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? '#6b8f71' : pct >= 60 ? '#c8953c' : '#c45a4a';
  return (
    <div className="flex items-center gap-2">
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.04)' }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-[10px] font-mono font-bold" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

interface ProofProvenancePanelProps {
  entries: ProofEntry[];
  compact?: boolean;
}

export function ProofProvenancePanel({ entries, compact }: ProofProvenancePanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(entries[0]?.id ?? null);

  if (compact) {
    const entry = entries[0];
    if (!entry) return null;
    const reviewCfg = REVIEW_STATE_CFG[entry.reviewState];
    const ReviewIcon = reviewCfg.icon;
    return (
      <div
        className="rounded-xl p-4"
        style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-3.5 h-3.5" style={{ color: '#d4a054' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: '#d4a054' }}
          >
            Proof Chain
          </span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <span
            className="text-[9px] px-1.5 py-0.5 rounded font-bold"
            style={{ color: reviewCfg.color, background: reviewCfg.bg }}
          >
            <ReviewIcon className="w-2.5 h-2.5 inline mr-1" />
            {reviewCfg.label}
          </span>
          <span className="text-[10px] font-mono" style={{ color: TEXT.tertiary }}>
            {SOURCE_CLASS_LABELS[entry.sourceClass]}
          </span>
          <ConfidenceBar score={entry.confidenceScore} />
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
        <Shield className="w-4 h-4" style={{ color: '#d4a054' }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-bold uppercase tracking-widest"
              style={{ color: '#d4a054' }}
            >
              Proof Chain
            </span>
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded"
              style={{
                background: 'rgba(212,160,84,0.08)',
                border: '1px solid rgba(212,160,84,0.2)',
                color: '#d4a054',
              }}
            >
              Decision Receipt
            </span>
          </div>
          <div className="text-[9px] font-mono mt-0.5" style={{ color: TEXT.muted }}>
            Immutable provenance — source, model, confidence, reviewer, lineage
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="flex items-center gap-1 text-[7px] font-mono px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(212,160,84,0.06)',
              border: '1px solid rgba(212,160,84,0.12)',
              color: 'rgba(212,160,84,0.5)',
            }}
          >
            <FlaskConical className="w-2.5 h-2.5" />
            synthetic
          </span>
          <span className="text-[10px] font-mono" style={{ color: TEXT.tertiary }}>
            {entries.length} record{entries.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="divide-y" style={{ borderColor: BORDER.subtle }}>
        {entries.map((entry) => {
          const isExpanded = expandedId === entry.id;
          const reviewCfg = REVIEW_STATE_CFG[entry.reviewState];
          const ReviewIcon = reviewCfg.icon;
          const exportCfg = EXPORT_SAFETY_CFG[entry.exportSafety];

          return (
            <div key={entry.id}>
              <button
                onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                className="w-full flex items-center gap-3 px-5 py-3 transition-colors hover:bg-white/[0.02]"
                aria-expanded={isExpanded}
                aria-label={`${entry.contentType} — ${isExpanded ? 'collapse' : 'expand'} details`}
              >
                <div
                  className="w-6 h-6 rounded flex items-center justify-center shrink-0"
                  style={{ background: reviewCfg.bg, border: `1px solid ${reviewCfg.color}30` }}
                >
                  <ReviewIcon className="w-3 h-3" style={{ color: reviewCfg.color }} />
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold" style={{ color: TEXT.primary }}>
                      {entry.contentType}
                    </span>
                    <span className="text-[9px] font-mono" style={{ color: TEXT.tertiary }}>
                      #{entry.id}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
                      {SOURCE_CLASS_LABELS[entry.sourceClass]}
                    </span>
                    {entry.modelId && (
                      <>
                        <span style={{ color: TEXT.muted }}>·</span>
                        <span className="text-[9px] font-mono" style={{ color: TEXT.tertiary }}>
                          {entry.modelId}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="w-24 shrink-0">
                  <ConfidenceBar score={entry.confidenceScore} />
                </div>
                {isExpanded ? (
                  <ChevronDown className="w-3 h-3 shrink-0" style={{ color: TEXT.tertiary }} />
                ) : (
                  <ChevronRight className="w-3 h-3 shrink-0" style={{ color: TEXT.tertiary }} />
                )}
              </button>

              {isExpanded && (
                <div className="px-5 pb-4 ml-9">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                    {[
                      { label: 'Review State', value: reviewCfg.label, color: reviewCfg.color },
                      { label: 'Export Safety', value: exportCfg.label, color: exportCfg.color },
                      {
                        label: 'Source',
                        value: SOURCE_CLASS_LABELS[entry.sourceClass],
                        color: TEXT.secondary,
                      },
                      { label: 'Generated', value: entry.generatedAt, color: TEXT.secondary },
                    ].map((f) => (
                      <div key={f.label}>
                        <div
                          className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
                          style={{ color: TEXT.muted }}
                        >
                          {f.label}
                        </div>
                        <div className="text-[10px] font-semibold" style={{ color: f.color }}>
                          {f.value}
                        </div>
                      </div>
                    ))}
                  </div>

                  {entry.modelProvider && (
                    <div className="flex items-center gap-2 mb-2">
                      <Cpu className="w-3 h-3" style={{ color: TEXT.tertiary }} />
                      <span className="text-[10px]" style={{ color: TEXT.tertiary }}>
                        Provider: {entry.modelProvider} · Model: {entry.modelId}
                      </span>
                    </div>
                  )}

                  {entry.inputSources.length > 0 && (
                    <div className="mb-2">
                      <div
                        className="text-[8px] font-mono uppercase tracking-wider mb-1"
                        style={{ color: TEXT.muted }}
                      >
                        Input Sources
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {entry.inputSources.map((src, i) => (
                          <span
                            key={i}
                            className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded"
                            style={{
                              background: 'rgba(255,255,255,0.03)',
                              border: `1px solid ${BORDER.muted}`,
                              color: TEXT.secondary,
                            }}
                          >
                            <Link2 className="w-2.5 h-2.5" />
                            {src.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {entry.reviewedBy && (
                    <div
                      className="flex items-center gap-2 mt-2 pt-2"
                      style={{ borderTop: `1px solid ${BORDER.subtle}` }}
                    >
                      <Eye className="w-3 h-3" style={{ color: TEXT.tertiary }} />
                      <span className="text-[10px]" style={{ color: TEXT.tertiary }}>
                        Reviewed by {entry.reviewedBy} on {entry.reviewedAt}
                      </span>
                      {entry.reviewNote && (
                        <span className="text-[10px] italic" style={{ color: TEXT.tertiary }}>
                          — "{entry.reviewNote}"
                        </span>
                      )}
                    </div>
                  )}

                  {entry.parentProofId && (
                    <div className="flex items-center gap-2 mt-1">
                      <GitBranch className="w-3 h-3" style={{ color: TEXT.tertiary }} />
                      <span className="text-[10px]" style={{ color: TEXT.tertiary }}>
                        Derived from proof #{entry.parentProofId}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
