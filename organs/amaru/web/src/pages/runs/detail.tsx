import { useParams, Link } from 'wouter';
import { useSyncRun, useRetrySyncRunRow } from '@/lib/api-hooks';
import { Badge } from '@/components/ui';
import { Button } from '@/components/ui';
import { CheckCircle2, XCircle, AlertCircle, RefreshCw, ArrowLeft, Clock, Rows } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

function formatDuration(ms: number | null): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function runStatusBadgeVariant(status: string) {
  if (status === 'success') return 'success' as const;
  if (status === 'failed') return 'failed' as const;
  if (status === 'running') return 'running' as const;
  if (status === 'partial') return 'partial' as const;
  return 'default' as const;
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle2 className="w-5 h-5 text-green-400" />;
  if (status === 'failed') return <XCircle className="w-5 h-5 text-rose-400" />;
  if (status === 'running') return <RefreshCw className="w-5 h-5 text-yellow-400 animate-spin" />;
  if (status === 'partial') return <AlertCircle className="w-5 h-5 text-orange-400" />;
  return <Clock className="w-5 h-5 text-muted-foreground" />;
}

export default function RunsDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? '';
  const { data: run, isLoading, refetch, isFetching } = useSyncRun(id);
  const retryRow = useRetrySyncRunRow();

  const handleRetry = (rowId: string) => {
    retryRow.mutate({ runId: id, rowId }, {
      onSuccess: () => { toast.success('Row queued for retry'); refetch(); },
      onError: () => toast.error('Failed to retry row'),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 rounded skeleton-conduit" />
        <div className="h-32 rounded-lg skeleton-conduit" />
        <div className="h-64 rounded-lg skeleton-conduit" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="conduit-card p-12 text-center">
        <p className="text-muted-foreground">Run not found.</p>
        <Link href="/runs"><Button variant="outline" size="sm" className="mt-4">Back to Runs</Button></Link>
      </div>
    );
  }

  const successRate = run.rowsRead > 0 ? Math.round((run.rowsWritten / run.rowsRead) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/runs">
          <button className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <StatusIcon status={run.status} />
            <h1 className="text-xl font-display font-bold tracking-tight truncate">
              Run: {id.slice(0, 8)}
            </h1>
            <Badge variant={runStatusBadgeVariant(run.status)}>{run.status}</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            {run.sync?.name ?? run.syncId} &middot; triggered by {run.triggeredBy}
          </p>
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

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Rows Read', value: run.rowsRead.toLocaleString(), color: 'text-foreground' },
          { label: 'Rows Written', value: run.rowsWritten.toLocaleString(), color: 'text-green-400' },
          { label: 'Rows Failed', value: run.rowsFailed.toLocaleString(), color: run.rowsFailed > 0 ? 'text-rose-400' : 'text-muted-foreground' },
          { label: 'Duration', value: formatDuration(run.durationMs), color: 'text-foreground' },
        ].map((stat) => (
          <div key={stat.label} className="conduit-stat p-4">
            <div className={cn("text-2xl font-display font-bold tracking-tight", stat.color)}>{stat.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div className="conduit-card p-5">
        <h2 className="font-semibold text-sm mb-3">Timeline</h2>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Started</dt>
          <dd className="font-mono text-xs">{formatTime(run.startedAt)}</dd>
          <dt className="text-muted-foreground">Finished</dt>
          <dd className="font-mono text-xs">{formatTime(run.finishedAt)}</dd>
          <dt className="text-muted-foreground">Success rate</dt>
          <dd className="font-mono">
            <span className={cn(successRate >= 95 ? 'text-green-400' : successRate >= 80 ? 'text-yellow-400' : 'text-rose-400')}>
              {successRate}%
            </span>
          </dd>
          {run.errorMessage && (
            <>
              <dt className="text-muted-foreground">Error</dt>
              <dd className="text-rose-400 text-xs">{run.errorMessage}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Failed rows */}
      {run.sampleErrors && run.sampleErrors.length > 0 && (
        <div className="conduit-card overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3 border-b border-border">
            <Rows className="w-4 h-4 text-rose-400" />
            <h2 className="font-semibold text-sm">Failed Rows</h2>
            <span className="ml-auto text-xs text-muted-foreground">{run.rowsFailed} total</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Row</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Source Data</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Error</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {run.sampleErrors.map((row) => (
                  <tr key={row.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{row.rowIndex}</td>
                    <td className="px-4 py-2 max-w-xs">
                      <code className="text-xs font-mono text-muted-foreground truncate block">
                        {JSON.stringify(row.sourceData).slice(0, 80)}…
                      </code>
                    </td>
                    <td className="px-4 py-2 text-rose-400 text-xs max-w-sm">
                      <span className="truncate block">{row.errorMessage ?? '—'}</span>
                    </td>
                    <td className="px-4 py-2">
                      {row.retried ? (
                        <span className="text-xs text-muted-foreground">Retried</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={row.retried || retryRow.isPending}
                        onClick={() => handleRetry(row.id)}
                        className="text-xs h-7"
                      >
                        Retry
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {run.rowsFailed === 0 && run.status === 'success' && (
        <div className="conduit-card p-8 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-3" />
          <p className="font-semibold">All rows synced successfully</p>
          <p className="text-sm text-muted-foreground mt-1">No errors to display.</p>
        </div>
      )}
    </div>
  );
}
