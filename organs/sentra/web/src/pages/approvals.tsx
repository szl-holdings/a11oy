// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  FileText,
  Shield,
  Terminal,
  XCircle,
} from 'lucide-react';
import { decideFix, type FixRequest, useMeshState } from '@/lib/mesh-store';

const TIER_STYLES: Record<string, string> = {
  critical: 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10',
  elevated: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  standard: 'text-[#8a8a8a] border-sky-500/30 bg-[#8a8a8a]/10',
};

const DOMAIN_ICON: Record<string, typeof Bot> = {
  'agent-mesh': Bot,
  'ot-response': AlertTriangle,
  'control-drift': Shield,
};

export default function Approvals() {
  const meshState = useMeshState();
  const items = meshState.fixRequests;
  const pending = items.filter((a) => a.status === 'pending');
  const resolved = items.filter((a) => a.status !== 'pending');

  return (
    <div className="space-y-8 animate-fade-in">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Guardian Approvals</h1>
          <p className="text-slate-400 mt-1">
            Policy-gated action queue — all high-impact changes require principal review
          </p>
        </div>
        <div className="flex gap-3">
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Pending</div>
            <div className="text-2xl font-display font-bold text-[#c9b787]">{pending.length}</div>
          </div>
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Mesh Index</div>
            <div className="text-2xl font-display font-bold text-[#c9b787]">
              {meshState.resilienceOverall}
            </div>
          </div>
        </div>
      </header>

      {pending.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-display font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#c9b787] animate-pulse" />
            Awaiting Decision
          </h2>
          {pending.map((item) => (
            <PendingCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {resolved.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-display font-bold text-slate-500 uppercase tracking-wider">
            Resolved
          </h2>
          {resolved.map((item) => (
            <ResolvedCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function PendingCard({ item }: { item: FixRequest }) {
  const Icon = DOMAIN_ICON[item.domain] ?? Shield;
  return (
    <div className="sentra-panel p-6 border-[#c9b787]/10">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded bg-[#c9b787]/10 border border-[#c9b787]/20 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-[#c9b787]" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="font-bold text-slate-100">{item.title}</h3>
            <span
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold border',
                TIER_STYLES[item.tier],
              )}
            >
              {item.tier}
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono border text-[#8a8a8a] border-sky-500/20 bg-[#8a8a8a]/10">
              {item.domain}
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono border text-slate-400 border-slate-700 bg-slate-800">
              executor: {item.fixType}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 font-mono mb-3">
            Requested by {item.requestedBy} · {new Date(item.requestedAt).toLocaleTimeString()}
          </div>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">{item.description}</p>
          <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
            <FileText className="w-3 h-3" />
            ProofEnvelope: {item.proofHash}
          </div>
          <div className="flex gap-3 mt-5 pt-4 border-t border-slate-800">
            <button
              onClick={() => decideFix(item.id, 'approved')}
              className="flex items-center gap-2 px-5 py-2 rounded bg-[#c9b787]/20 hover:bg-[#c9b787]/30 border border-[#c9b787]/30 text-[#c9b787] text-sm font-bold transition-colors"
            >
              <CheckCircle2 className="w-4 h-4" />
              Approve & Execute
            </button>
            <button
              onClick={() => decideFix(item.id, 'rejected')}
              className="flex items-center gap-2 px-5 py-2 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 text-sm font-bold transition-colors"
            >
              <XCircle className="w-4 h-4" />
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResolvedCard({ item }: { item: FixRequest }) {
  const approved = item.status === 'approved';
  return (
    <div className={cn('sentra-panel p-5', approved ? '' : 'opacity-60')}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          {approved ? (
            <CheckCircle2 className="w-4 h-4 text-[#c9b787] mt-0.5" />
          ) : (
            <XCircle className="w-4 h-4 text-slate-500 mt-0.5" />
          )}
          <div className="flex-1">
            <div className="text-sm font-bold text-slate-300">{item.title}</div>
            <div className="text-[10px] text-slate-500 font-mono">
              {item.requestedBy} ·{' '}
              {item.resolvedAt ? new Date(item.resolvedAt).toLocaleTimeString() : ''}
            </div>
            {approved && item.executionLog && item.executionLog.length > 0 && (
              <div className="mt-3 rounded border border-[#c9b787]/15 bg-[#c9b787]/5 p-3">
                <div className="flex items-center gap-2 text-[10px] text-[#c9b787] font-mono uppercase mb-2">
                  <Terminal className="w-3 h-3" />
                  Executor Log
                </div>
                <ul className="space-y-1 text-[11px] text-[#c9b787]/80 font-mono">
                  {item.executionLog.map((line, idx) => (
                    <li key={idx} className="flex gap-2">
                      <span className="text-[#c9b787]/60">›</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="text-[10px] font-mono text-[#8a8a8a]/60">{item.domain}</span>
          <span
            className={cn(
              'px-2 py-0.5 rounded border text-[10px] font-mono font-bold',
              approved
                ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10'
                : 'text-slate-500 border-slate-700 bg-slate-800',
            )}
          >
            {approved ? 'EXECUTED' : 'REJECTED'}
          </span>
        </div>
      </div>
    </div>
  );
}
