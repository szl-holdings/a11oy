// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useEffect, useState } from 'react';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Shield,
  Timer,
  XCircle,
  Zap,
  RotateCcw,
} from 'lucide-react';
import { cpsApi } from '@/lib/cps-api';

const MATURITY_BADGE: Record<string, { color: string; label: string }> = {
  shadow: { color: 'text-slate-400 bg-slate-500/20', label: 'Shadow' },
  'supervised-auto': { color: 'text-amber-400 bg-amber-500/20', label: 'Supervised' },
  autonomous: { color: 'text-emerald-400 bg-emerald-500/20', label: 'Autonomous' },
};

export default function CpsExecutive() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    cpsApi.executive.status().then((d) => {
      setData(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-500 font-mono text-sm">Loading Executive View...</div>
      </div>
    );
  }

  const summary = data?.summary ?? {};

  return (
    <div className="space-y-8 animate-fade-in">
      <header>
        <div className="flex items-center gap-2 text-[10px] font-mono text-[#c9b787]/70 uppercase tracking-widest mb-1">
          <Shield className="w-3 h-3" />
          Sentra
        </div>
        <h1 className="text-3xl font-display font-bold text-slate-100">CPS Executive Command</h1>
        <p className="text-slate-400 mt-1">
          Live containment status, approval lineage, business impact, and decision-deadline timers
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Total Payloads', value: summary.totalPayloads ?? 0, icon: Shield, color: 'text-[#c9b787]' },
          { label: 'Total Runs', value: summary.totalRuns ?? 0, icon: Activity, color: 'text-blue-400' },
          { label: 'Active Containment', value: summary.activeContainments ?? 0, icon: Zap, color: 'text-red-400' },
          { label: 'Pending Approvals', value: summary.pendingApprovals ?? 0, icon: Clock, color: 'text-amber-400' },
          { label: 'Completed (24h)', value: summary.completedLast24h ?? 0, icon: CheckCircle2, color: 'text-emerald-400' },
          { label: 'Rolled Back', value: summary.rolledBack ?? 0, icon: RotateCcw, color: 'text-orange-400' },
        ].map((kpi) => (
          <div key={kpi.label} className="sentra-panel p-4 text-center">
            <kpi.icon className={cn('w-5 h-5 mx-auto mb-2', kpi.color)} />
            <div className="text-2xl font-display font-bold text-slate-100">{kpi.value}</div>
            <div className="text-[10px] font-mono text-slate-500 uppercase mt-1">{kpi.label}</div>
          </div>
        ))}
      </div>

      {(data?.pendingApprovals?.length ?? 0) > 0 && (
        <section>
          <h2 className="text-sm font-mono text-amber-400/80 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Timer className="w-4 h-4" />
            Decision Deadline Timers
          </h2>
          <div className="grid gap-3">
            {data.pendingApprovals.map((approval: any) => {
              const deadline = new Date(approval.deadlineAt);
              const remaining = deadline.getTime() - Date.now();
              const hoursLeft = Math.max(0, Math.floor(remaining / (60 * 60 * 1000)));
              const minutesLeft = Math.max(0, Math.floor((remaining % (60 * 60 * 1000)) / (60 * 1000)));
              const isUrgent = remaining < 60 * 60 * 1000;

              return (
                <div key={approval.id} className={cn(
                  'sentra-panel p-4',
                  isUrgent ? 'border-red-500/30 bg-red-500/5' : 'border-amber-500/20',
                )}>
                  <div className="flex items-center gap-4">
                    <div className={cn(
                      'w-12 h-12 rounded-lg flex items-center justify-center font-display font-bold text-lg',
                      isUrgent ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400',
                    )}>
                      {hoursLeft}h
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-slate-200">
                        {approval.tier?.toUpperCase()} Approval Required
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                        Run {approval.runId?.slice(0, 8)} · {hoursLeft}h {minutesLeft}m remaining
                      </div>
                    </div>
                    {isUrgent && (
                      <AlertTriangle className="w-5 h-5 text-red-400 animate-pulse" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {(data?.activeContainments?.length ?? 0) > 0 && (
        <section>
          <h2 className="text-sm font-mono text-red-400/80 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Active Containments
          </h2>
          <div className="grid gap-3">
            {data.activeContainments.map((run: any) => (
              <div key={run.id} className="sentra-panel p-4 border-red-500/20">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-red-400" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-200">{run.payloadId}</div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      Status: {run.status} · {run.actions?.length ?? 0} action(s) · Started {new Date(run.startedAt).toLocaleString()}
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-red-400 bg-red-500/10 px-2 py-0.5 rounded">
                    ACTIVE
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-mono text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4" />
          Payload Performance
        </h2>
        <div className="grid gap-3">
          {(data?.byPayload ?? []).map((p: any) => {
            const maturity = MATURITY_BADGE[p.maturityMode] ?? MATURITY_BADGE.shadow;
            return (
              <div key={p.payloadId} className="sentra-panel p-4">
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">{p.payloadName}</span>
                      <span className={cn('text-[10px] font-mono px-2 py-0.5 rounded', maturity.color)}>
                        {maturity.label}
                      </span>
                    </div>
                    <div className="flex gap-4 mt-2 text-[11px] font-mono">
                      <span className="text-slate-400">Total: {p.totalRuns}</span>
                      <span className="text-emerald-400">Completed: {p.completedRuns}</span>
                      <span className="text-red-400">Failed: {p.failedRuns}</span>
                      {p.lastRunAt && (
                        <span className="text-slate-500">Last: {new Date(p.lastRunAt).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                  {p.totalRuns > 0 && (
                    <div className="w-16 text-right">
                      <div className="text-lg font-display font-bold text-emerald-400">
                        {p.totalRuns > 0 ? Math.round((p.completedRuns / p.totalRuns) * 100) : 0}%
                      </div>
                      <div className="text-[9px] font-mono text-slate-500">success</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {(data?.recentRuns?.length ?? 0) > 0 && (
        <section>
          <h2 className="text-sm font-mono text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Recent Activity
          </h2>
          <div className="space-y-2">
            {data.recentRuns.map((run: any) => (
              <div key={run.id} className="sentra-panel p-3">
                <div className="flex items-center gap-3">
                  {run.status === 'completed' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    : run.status === 'failed' || run.status === 'blocked' ? <XCircle className="w-4 h-4 text-red-400" />
                    : <Clock className="w-4 h-4 text-amber-400" />}
                  <span className="text-sm text-slate-300">{run.payloadId}</span>
                  <span className="text-[10px] font-mono text-slate-500">{run.status}</span>
                  <span className="text-[10px] text-slate-600 ml-auto">{new Date(run.startedAt).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
