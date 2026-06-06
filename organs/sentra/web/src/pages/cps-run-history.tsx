import { useEffect, useState } from 'react';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  RotateCcw,
  Shield,
  XCircle,
  Eye,
  Zap,
  FileText,
} from 'lucide-react';
import { cpsApi } from '@/lib/cps-api';

const STATUS_CONFIG: Record<string, { icon: typeof Shield; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: 'text-emerald-400', label: 'Completed' },
  'awaiting-approval': { icon: Clock, color: 'text-amber-400', label: 'Awaiting Approval' },
  acting: { icon: Zap, color: 'text-blue-400', label: 'Acting' },
  detecting: { icon: Eye, color: 'text-blue-300', label: 'Detecting' },
  deciding: { icon: Activity, color: 'text-blue-300', label: 'Deciding' },
  recovering: { icon: RotateCcw, color: 'text-cyan-400', label: 'Recovering' },
  'rolled-back': { icon: RotateCcw, color: 'text-orange-400', label: 'Rolled Back' },
  failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
  blocked: { icon: AlertTriangle, color: 'text-red-400', label: 'Blocked' },
  pending: { icon: Clock, color: 'text-slate-400', label: 'Pending' },
};

export default function CpsRunHistory() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [proofBundles, setProofBundles] = useState<Record<string, any>>({});

  useEffect(() => {
    cpsApi.runs.list().then((data) => {
      setRuns(Array.isArray(data) ? data : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  async function handleRollback(runId: string) {
    try {
      const updated = await cpsApi.runs.rollback(runId);
      setRuns((prev) => prev.map((r) => (r.id === runId ? updated : r)));
    } catch { /* handled by UI */ }
  }

  async function handleViewProof(runId: string) {
    if (proofBundles[runId]) return;
    try {
      const bundle = await cpsApi.runs.proofBundle(runId);
      setProofBundles((prev) => ({ ...prev, [runId]: bundle }));
    } catch { /* handled by UI */ }
  }

  function downloadProofBundle(runId: string) {
    const bundle = proofBundles[runId];
    if (!bundle) return;
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `proof-bundle-${runId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-500 font-mono text-sm">Loading CPS Runs...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">CPS Run History</h1>
          <p className="text-slate-400 mt-1">Payload execution log with proof bundles</p>
        </div>
        <div className="flex gap-3">
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Total Runs</div>
            <div className="text-2xl font-display font-bold text-[#c9b787]">{runs.length}</div>
          </div>
          <div className="sentra-panel px-4 py-2 text-center">
            <div className="text-[10px] text-slate-500 font-mono uppercase">Completed</div>
            <div className="text-2xl font-display font-bold text-emerald-400">
              {runs.filter((r) => r.status === 'completed').length}
            </div>
          </div>
        </div>
      </header>

      <div className="space-y-3">
        {runs.length === 0 && (
          <div className="sentra-panel p-8 text-center text-slate-500">
            No CPS runs yet. Execute a payload from the catalog to begin.
          </div>
        )}
        {runs.map((run) => {
          const statusCfg = STATUS_CONFIG[run.status] ?? STATUS_CONFIG.pending;
          const StatusIcon = statusCfg.icon;
          const expanded = expandedId === run.id;
          const proof = proofBundles[run.id];

          return (
            <div key={run.id} className="sentra-panel p-0 overflow-hidden">
              <div
                className="p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
                onClick={() => {
                  setExpandedId(expanded ? null : run.id);
                  if (!expanded && run.proofBundle) handleViewProof(run.id);
                }}
              >
                <div className="flex items-center gap-4">
                  <StatusIcon className={cn('w-5 h-5 flex-shrink-0', statusCfg.color)} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">{run.payloadId}</span>
                      <span className="text-[10px] font-mono text-slate-500">v{run.payloadVersion}</span>
                      <span className={cn('text-[10px] font-mono px-2 py-0.5 rounded', statusCfg.color)}>
                        {statusCfg.label}
                      </span>
                      <span className="text-[10px] font-mono text-slate-600 px-2 py-0.5 rounded bg-slate-800">
                        {run.maturityMode}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 font-mono">
                      {run.id.slice(0, 8)} · {new Date(run.startedAt).toLocaleString()}
                      {run.detect && ` · ${run.detect.signals?.length ?? 0} signal(s) · ${((run.detect.confidence ?? 0) * 100).toFixed(0)}% confidence`}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    {(run.status === 'completed' || run.status === 'acting') && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRollback(run.id); }}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-orange-400 border border-orange-400/30 rounded hover:bg-orange-400/10 transition-colors"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Rollback
                      </button>
                    )}
                    {run.proofBundle && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleViewProof(run.id); downloadProofBundle(run.id); }}
                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-[#c9b787] border border-[#c9b787]/30 rounded hover:bg-[#c9b787]/10 transition-colors"
                      >
                        <Download className="w-3 h-3" />
                        Proof
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {expanded && (
                <div className="border-t border-white/5 p-5 space-y-4 bg-black/20">
                  {run.error && (
                    <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-300">
                      {run.error}
                    </div>
                  )}

                  {run.governanceChecks?.length > 0 && (
                    <div>
                      <h4 className="text-xs font-mono text-slate-500 uppercase mb-2">Governance Checks</h4>
                      <div className="grid gap-1.5">
                        {run.governanceChecks.map((check: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            {check.passed
                              ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                            <span className={check.passed ? 'text-slate-300' : 'text-red-300'}>{check.detail}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {run.actions?.length > 0 && (
                    <div>
                      <h4 className="text-xs font-mono text-slate-500 uppercase mb-2">Actions</h4>
                      <div className="grid gap-1.5">
                        {run.actions.map((action: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 p-2 rounded bg-slate-900/50 text-sm">
                            <Zap className="w-3.5 h-3.5 text-[#c9b787]" />
                            <span className="text-slate-300">{action.result?.type ?? 'action'}</span>
                            <span className={cn(
                              'text-[10px] font-mono px-1.5 py-0.5 rounded',
                              action.status === 'executed' ? 'text-emerald-400 bg-emerald-500/10' :
                              action.status === 'skipped' ? 'text-slate-400 bg-slate-500/10' :
                              'text-red-400 bg-red-500/10',
                            )}>
                              {action.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {proof && (
                    <div>
                      <h4 className="text-xs font-mono text-slate-500 uppercase mb-2 flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        Proof Bundle
                      </h4>
                      <div className="p-3 rounded-lg bg-slate-900/50 border border-white/5 text-[11px] font-mono text-slate-400 space-y-1">
                        <div>Signature: <span className="text-[#c9b787]">{proof.signature}</span></div>
                        <div>Classification: {proof.classification}</div>
                        <div>Residual Risk: {proof.residualRisk}</div>
                        <div>Generated: {new Date(proof.generatedAt).toLocaleString()}</div>
                      </div>
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
