import { useEffect, useState } from 'react';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  CheckCircle2,
  Clock,
  Shield,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  AlertTriangle,
  Timer,
  User,
} from 'lucide-react';
import { cpsApi, type MaturityGate } from '@/lib/cps-api';

export default function CpsApprovals() {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [gates, setGates] = useState<Record<string, MaturityGate>>({});
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      cpsApi.approvals.list().catch(() => []),
      cpsApi.payloads.maturityGates().catch(() => ({ gates: {} as Record<string, MaturityGate> })),
    ]).then(([data, g]) => {
      setApprovals(Array.isArray(data) ? data : []);
      setGates(g?.gates ?? {});
      setLoading(false);
    });
  }, []);

  async function handleRespond(id: string, approved: boolean, reason?: string) {
    setProcessingId(id);
    try {
      await cpsApi.approvals.respond(id, approved, reason);
      setApprovals((prev) => prev.map((a) => (
        a.id === id ? { ...a, status: approved ? 'approved' : 'rejected', respondedAt: new Date().toISOString() } : a
      )));
    } catch { /* handled by UI */ }
    setProcessingId(null);
  }

  const pending = approvals.filter((a) => a.status === 'pending');
  const resolved = approvals.filter((a) => a.status !== 'pending');
  const gateList = Object.values(gates);
  const blockedGates = gateList.filter((g) => !g.allowed);
  const passingGates = gateList.filter((g) => g.allowed);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-500 font-mono text-sm">Loading CPS Approvals...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {gateList.length > 0 && (
        <section className="sentra-panel p-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#c9b787]" />
              <span className="text-sm font-medium text-slate-200">CPS Maturity Promotion Gates</span>
              <span className="text-[10px] font-mono text-slate-500">
                (composite confidence ≥ 75% · no regression)
              </span>
            </div>
            <div className="flex gap-3 text-[11px] font-mono">
              <span className="flex items-center gap-1 text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                {passingGates.length} passing
              </span>
              <span className={cn('flex items-center gap-1', blockedGates.length > 0 ? 'text-red-400' : 'text-slate-500')}>
                <ShieldAlert className="w-3.5 h-3.5" />
                {blockedGates.length} blocked
              </span>
            </div>
          </div>
          {blockedGates.length > 0 && (
            <div className="mt-3 grid gap-2">
              {blockedGates.map((g) => (
                <div
                  key={g.payloadId}
                  className="flex items-start gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20"
                >
                  <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-slate-200">{g.payloadName}</span>
                      <span className="text-[10px] font-mono text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded">
                        promotion blocked
                      </span>
                      {g.compositeConfidence != null && (
                        <span className="text-[10px] font-mono text-slate-500">
                          confidence {(g.compositeConfidence * 100).toFixed(0)}% / required{' '}
                          {(g.requiredThreshold * 100).toFixed(0)}%
                        </span>
                      )}
                      {g.regressionInLastRun && (
                        <span className="text-[10px] font-mono text-amber-400">regression detected</span>
                      )}
                    </div>
                    <ul className="mt-1.5 space-y-0.5 text-[11px] text-slate-400 pl-4 list-disc">
                      {g.blockers.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">CPS Approval Queue</h1>
          <p className="text-slate-400 mt-1">
            Policy-gated actions requiring explicit authorization before execution
          </p>
        </div>
        <div className="flex gap-3">
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Pending</div>
            <div className="text-2xl font-display font-bold text-amber-400">{pending.length}</div>
          </div>
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Resolved</div>
            <div className="text-2xl font-display font-bold text-slate-400">{resolved.length}</div>
          </div>
        </div>
      </header>

      {pending.length > 0 && (
        <section>
          <h2 className="text-sm font-mono text-amber-400/80 uppercase tracking-wider mb-3">Pending Approvals</h2>
          <div className="space-y-3">
            {pending.map((approval) => {
              const deadlineDate = new Date(approval.deadlineAt);
              const isUrgent = deadlineDate.getTime() - Date.now() < 60 * 60 * 1000;

              return (
                <div key={approval.id} className={cn(
                  'sentra-panel p-5',
                  isUrgent && 'border-amber-500/30',
                )}>
                  <div className="flex items-start gap-4">
                    <Clock className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-200">Run {approval.runId?.slice(0, 8)}</span>
                        <span className={cn(
                          'text-[10px] font-mono px-2 py-0.5 rounded border',
                          approval.tier === 'executive' || approval.tier === 'dual-executive'
                            ? 'text-red-400 bg-red-500/10 border-red-500/20'
                            : approval.tier === 'supervisor'
                              ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                              : 'text-blue-400 bg-blue-500/10 border-blue-500/20',
                        )}>
                          {approval.tier} approval
                        </span>
                        {isUrgent && (
                          <span className="text-[10px] font-mono text-red-400 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Urgent
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1 font-mono flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Timer className="w-3 h-3" />
                          Deadline: {deadlineDate.toLocaleString()}
                        </span>
                        <span>Requested: {new Date(approval.requestedAt).toLocaleString()}</span>
                      </div>
                      {approval.tier === 'dual-executive' && (
                        <div className="mt-2 text-[11px] font-mono">
                          <span className="text-amber-400/70">
                            Dual-executive: {approval.dualApprovals?.length ?? 0}/{approval.requiredDualCount ?? 2} approvals collected
                          </span>
                          {approval.dualApprovals?.map((da: { approver: string; approvedAt: string }, i: number) => (
                            <span key={i} className="ml-2 text-emerald-400/60">
                              [{da.approver} at {new Date(da.approvedAt).toLocaleTimeString()}]
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleRespond(approval.id, true)}
                        disabled={processingId === approval.id}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs font-mono text-emerald-400 border border-emerald-400/30 rounded-lg hover:bg-emerald-400/10 transition-colors disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => handleRespond(approval.id, false, 'Rejected by operator')}
                        disabled={processingId === approval.id}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs font-mono text-red-400 border border-red-400/30 rounded-lg hover:bg-red-400/10 transition-colors disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Reject
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {resolved.length > 0 && (
        <section>
          <h2 className="text-sm font-mono text-slate-500 uppercase tracking-wider mb-3">Resolved</h2>
          <div className="space-y-2">
            {resolved.map((approval) => (
              <div key={approval.id} className="sentra-panel p-4">
                <div className="flex items-center gap-3">
                  {approval.status === 'approved'
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    : <XCircle className="w-4 h-4 text-red-400" />}
                  <span className="text-sm text-slate-300">Run {approval.runId?.slice(0, 8)}</span>
                  <span className={cn(
                    'text-[10px] font-mono px-2 py-0.5 rounded',
                    approval.status === 'approved' ? 'text-emerald-400' : 'text-red-400',
                  )}>
                    {approval.status}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">{approval.tier}</span>
                  {approval.approver && (
                    <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                      <User className="w-3 h-3" /> {approval.approver}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-600 ml-auto">
                    {approval.respondedAt ? new Date(approval.respondedAt).toLocaleString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {approvals.length === 0 && (
        <div className="sentra-panel p-8 text-center text-slate-500">
          No approval requests yet. Approvals are generated when CPS payloads execute actions that require authorization.
        </div>
      )}
    </div>
  );
}
