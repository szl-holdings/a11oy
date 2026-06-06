/**
 * Guard Dog Brain — Sentra dashboard panel showing the ROSIE-derived brain
 * state at a glance: optimizer status, last evolved heuristic, recent proofs,
 * constitution version. Each tile deep-links into /brain/*.
 */
import { Brain, FileCheck, FlaskConical, ShieldCheck, Sigma } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'wouter';
import { useA11oyConstitution } from '@/brain/hooks/useA11oyConstitution';
import { loadProofEntries, type ProofEntry } from '@/brain/data/proofLedger';
import { getMergedResearchLibrary } from '@/brain/data/mergedResearch';

const STATUS_COPY: Record<'live' | 'fallback' | 'loading', { label: string; color: string }> = {
  live: { label: 'Live', color: '#22c55e' },
  fallback: { label: 'Seed', color: '#f59e0b' },
  loading: { label: 'Loading', color: '#64748b' },
};

export function GuardDogBrainPanel() {
  const { status, constitutionVersion, clauses } = useA11oyConstitution();
  const [proofs, setProofs] = useState<ProofEntry[]>([]);
  const [research, setResearch] = useState(() => getMergedResearchLibrary());

  useEffect(() => {
    const refresh = () => {
      setProofs(loadProofEntries().slice(0, 3));
      setResearch(getMergedResearchLibrary());
    };
    refresh();
    window.addEventListener('storage', refresh);
    // The IncidentPipelineCard fires this custom event after each approved
    // run so the dashboard updates without waiting on a cross-tab storage
    // event (storage events do not fire in the same tab that wrote them).
    window.addEventListener('sentra-brain-updated', refresh);
    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener('sentra-brain-updated', refresh);
    };
  }, []);

  const lastResearch = research[0];
  const statusCopy = STATUS_COPY[status];

  // Runtime optimizer status: derived from the proof ledger, which records
  // every Guard Dog Brain pipeline run. The most recent proof entry tells us
  // what the optimizer actually did most recently, not just what's available
  // in the catalog.
  const lastProof = proofs[0];
  const optimizerStatus: { label: string; tone: string; detail: string } = lastProof
    ? lastProof.outcome === 'optimal'
      ? { label: 'Optimal', tone: '#22c55e', detail: lastProof.problemLabel }
      : lastProof.outcome === 'sub-optimal'
      ? { label: 'Sub-optimal', tone: '#c9b787', detail: lastProof.problemLabel }
      : lastProof.outcome === 'blocked'
      ? { label: 'Blocked', tone: '#f59e0b', detail: lastProof.problemLabel }
      : { label: 'Infeasible', tone: '#ef4444', detail: lastProof.problemLabel }
    : { label: 'Idle', tone: '#64748b', detail: 'No runs yet' };

  return (
    <div className="sentra-panel p-5 space-y-4" data-testid="guard-dog-brain-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#c9b787]/10 border border-[#c9b787]/20 flex items-center justify-center">
            <Brain className="w-4 h-4 text-[#c9b787]" />
          </div>
          <div>
            <div className="text-sm font-display font-bold text-slate-100">Guard Dog Brain</div>
            <div className="text-[10px] text-slate-500 font-mono">
              ROSIE inside Sentra · Constitution v{constitutionVersion}
            </div>
          </div>
        </div>
        <span
          className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider"
          style={{ background: `${statusCopy.color}15`, color: statusCopy.color, border: `1px solid ${statusCopy.color}30` }}
          data-testid="guard-dog-brain-status"
        >
          {statusCopy.label}
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <Link href="/brain/optimizer" className="block">
          <div
            className="rounded-lg p-3 bg-slate-900/40 border border-slate-700/30 hover:border-[#c9b787]/40 transition-colors"
            data-testid="guard-dog-brain-optimizer-status"
            data-status={optimizerStatus.label.toLowerCase()}
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              <Sigma className="w-3 h-3" style={{ color: optimizerStatus.tone }} />
              <span className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Optimizer</span>
            </div>
            <div
              className="text-lg font-mono font-bold"
              style={{ color: optimizerStatus.tone }}
            >
              {optimizerStatus.label}
            </div>
            <div className="text-[10px] text-slate-500 truncate">{optimizerStatus.detail}</div>
          </div>
        </Link>

        <Link href="/brain/proofs" className="block">
          <div className="rounded-lg p-3 bg-slate-900/40 border border-slate-700/30 hover:border-[#c9b787]/40 transition-colors">
            <div className="flex items-center gap-1.5 mb-1.5">
              <FileCheck className="w-3 h-3 text-[#22c55e]" />
              <span className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Recent proofs</span>
            </div>
            <div className="text-lg font-mono font-bold text-slate-100" data-testid="guard-dog-brain-proof-count">
              {proofs.length}
            </div>
            <div className="text-[10px] text-slate-500 truncate">
              {proofs[0]?.problemLabel ?? 'No proofs yet'}
            </div>
          </div>
        </Link>

        <Link href="/brain/research" className="block">
          <div className="rounded-lg p-3 bg-slate-900/40 border border-slate-700/30 hover:border-[#c9b787]/40 transition-colors">
            <div className="flex items-center gap-1.5 mb-1.5">
              <FlaskConical className="w-3 h-3 text-[#8b5cf6]" />
              <span className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Last evolved heuristic</span>
            </div>
            <div className="text-[11px] font-semibold text-slate-100 truncate">{lastResearch?.title ?? '—'}</div>
            <div className="text-[10px] text-slate-500 truncate">{lastResearch?.distillation ?? ''}</div>
          </div>
        </Link>

        <Link href="/brain/constitution" className="block">
          <div className="rounded-lg p-3 bg-slate-900/40 border border-slate-700/30 hover:border-[#c9b787]/40 transition-colors">
            <div className="flex items-center gap-1.5 mb-1.5">
              <ShieldCheck className="w-3 h-3 text-[#06b6d4]" />
              <span className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Constitution</span>
            </div>
            <div className="text-lg font-mono font-bold text-slate-100">v{constitutionVersion}</div>
            <div className="text-[10px] text-slate-500">{clauses.length} clauses active</div>
          </div>
        </Link>
      </div>
    </div>
  );
}
