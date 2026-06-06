import { useState } from 'react';
import { Link } from 'wouter';
import { useSyncRuns } from '@/lib/api-hooks';
import { Badge } from '@/components/ui';
import type { RunStatus } from '@/lib/api';
import { RefreshCw, CheckCircle2, XCircle, AlertCircle, Clock, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

const STATUS_OPTS: Array<{ label: string; value: RunStatus | '' }> = [
  { label: 'All', value: '' },
  { label: 'Running', value: 'running' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
  { label: 'Partial', value: 'partial' },
];

function runStatusBadgeVariant(status: string) {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'failed';
  if (status === 'running') return 'running';
  if (status === 'partial') return 'partial';
  return 'default';
}

function RunStatusIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle2 className="w-4 h-4 text-green-400" />;
  if (status === 'failed') return <XCircle className="w-4 h-4 text-rose-400" />;
  if (status === 'running') return <RefreshCw className="w-4 h-4 text-yellow-400 animate-spin" />;
  if (status === 'partial') return <AlertCircle className="w-4 h-4 text-orange-400" />;
  return <Clock className="w-4 h-4 text-muted-foreground" />;
}

function formatDuration(ms: number | null): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function RunsList() {
  const [statusFilter, setStatusFilter] = useState<RunStatus | ''>('');
  const { data, isLoading, refetch, isFetching } = useSyncRuns(statusFilter ? { status: statusFilter } : undefined);
  const runs = data?.data ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">Sync Runs</h1>
          <p className="text-sm text-muted-foreground mt-0.5">{total} total runs</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border bg-card hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2">
        {STATUS_OPTS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setStatusFilter(opt.value)}
            className={cn(
              "px-3 py-1 text-xs rounded-full border transition-colors font-medium",
              statusFilter === opt.value
                ? "bg-primary/10 border-primary/30 text-primary"
                : "border-border text-muted-foreground hover:border-border hover:text-foreground bg-card"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg skeleton-conduit" style={{ animationDelay: `${i * 60}ms` }} />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="conduit-card p-12 text-center">
          <Clock className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-muted-foreground">No runs found</p>
          <p className="text-sm text-muted-foreground mt-1">
            {statusFilter ? `No ${statusFilter} runs yet.` : 'Trigger a sync to see run history here.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map((run, i) => (
            <Link key={run.id} href={`/runs/${run.id}`}>
              <div className={cn("conduit-card p-4 flex items-center gap-4 cursor-pointer hover:border-primary/20 transition-colors group animate-fade-in-up", `stagger-${Math.min(i + 1, 6)}`)}>
                <RunStatusIcon status={run.status} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{run.syncName ?? run.syncId.slice(0, 8)}</span>
                    <Badge variant={runStatusBadgeVariant(run.status)}>{run.status}</Badge>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground font-mono">
                    <span>{formatTime(run.startedAt)}</span>
                    {run.finishedAt && <span>Duration: {formatDuration(run.durationMs)}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-6 text-right">
                  <div className="text-xs space-y-0.5">
                    <div className="text-muted-foreground">Read</div>
                    <div className="font-mono font-medium text-foreground">{run.rowsRead.toLocaleString()}</div>
                  </div>
                  <div className="text-xs space-y-0.5">
                    <div className="text-muted-foreground">Written</div>
                    <div className="font-mono font-medium text-green-400">{run.rowsWritten.toLocaleString()}</div>
                  </div>
                  {run.rowsFailed > 0 && (
                    <div className="text-xs space-y-0.5">
                      <div className="text-muted-foreground">Failed</div>
                      <div className="font-mono font-medium text-rose-400">{run.rowsFailed.toLocaleString()}</div>
                    </div>
                  )}
                  <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
