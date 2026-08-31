// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import { AlertTriangle, Bell, CheckCircle2, Eye, EyeOff, Filter, RefreshCw, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { EmptyState, PageHeader, SeverityChip, StatusChip } from '@/lib/data-provenance';
import { listAlerts, updateAlert, type SentraAlert } from '@/lib/sentra-api';

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<SentraAlert[]>([]);
  const [source, setSource] = useState<'live' | 'seed' | 'loading'>('loading');
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [updating, setUpdating] = useState<string | null>(null);

  const load = async () => {
    setSource('loading');
    const result = await listAlerts();
    setAlerts(result.alerts);
    setSource(result.source);
  };

  useEffect(() => {
    void load();
  }, []);

  const handleStatus = async (id: string, status: SentraAlert['status']) => {
    setUpdating(id);
    const result = await updateAlert(id, status);
    if (result.ok) {
      setAlerts((prev) => prev.map((a) => (a.id === id ? result.alert : a)));
    }
    setUpdating(null);
  };

  const filtered = alerts
    .filter((a) => {
      if (severityFilter !== 'all' && a.severity !== severityFilter) return false;
      if (statusFilter !== 'all' && a.status !== statusFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          a.title.toLowerCase().includes(q) ||
          a.source.toLowerCase().includes(q) ||
          (a.asset ?? '').toLowerCase().includes(q)
        );
      }
      return true;
    })
    .sort((a, b) => {
      const sev = (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
      if (sev !== 0) return sev;
      return new Date(b.detectedAt).getTime() - new Date(a.detectedAt).getTime();
    });

  const openCount = alerts.filter((a) => a.status === 'open').length;
  const criticalOpen = alerts.filter((a) => a.severity === 'critical' && a.status === 'open').length;

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Alerts"
        subtitle="Real-time security alert feed across all monitored surfaces"
        provenance={source}
        actions={
          <button
            onClick={() => { void load(); }}
            className="p-2 rounded transition-colors hover:bg-slate-800 text-slate-500 hover:text-slate-300"
            aria-label="Refresh alerts"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Open Alerts</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{openCount}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Critical</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{criticalOpen}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Acknowledged</div>
          <div className="text-2xl font-display font-bold text-[#8a8a8a]">
            {alerts.filter((a) => a.status === 'acknowledged').length}
          </div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Suppressed</div>
          <div className="text-2xl font-display font-bold text-slate-500">
            {alerts.filter((a) => a.status === 'suppressed').length}
          </div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search alerts…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#f5f5f5]/40"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="suppressed">Suppressed</option>
          </select>
        </div>
      </div>

      {source === 'loading' ? (
        <div className="sentra-panel animate-pulse">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex gap-4 px-6 py-4 border-b border-slate-800">
              <div className="h-3 w-16 bg-slate-800 rounded" />
              <div className="h-3 flex-1 bg-slate-800 rounded" />
              <div className="h-3 w-20 bg-slate-800 rounded" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="No alerts match your filters"
          subtitle="Try adjusting the severity or status filter"
        />
      ) : (
        <div className="sentra-panel overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-800/50 border-b border-slate-700 text-[11px] uppercase tracking-wider text-slate-400 font-mono">
                <th className="px-5 py-3 font-medium">Alert</th>
                <th className="px-5 py-3 font-medium">Severity</th>
                <th className="px-5 py-3 font-medium">Source</th>
                <th className="px-5 py-3 font-medium">Asset</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Detected</th>
                <th className="px-5 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filtered.map((alert) => (
                <tr
                  key={alert.id}
                  className={cn(
                    'hover:bg-slate-800/30 transition-colors',
                    alert.severity === 'critical' && alert.status === 'open' && 'bg-[#f5f5f5]/[0.03]',
                  )}
                >
                  <td className="px-5 py-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle
                        className={cn(
                          'w-3.5 h-3.5 mt-0.5 shrink-0',
                          alert.severity === 'critical'
                            ? 'text-[#f5f5f5]'
                            : alert.severity === 'high'
                              ? 'text-[#c9b787]'
                              : alert.severity === 'medium'
                                ? 'text-[#c9b787]'
                                : 'text-slate-500',
                        )}
                      />
                      <div>
                        <div className="text-xs font-semibold text-slate-200">{alert.title}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5 font-mono">{alert.id}</div>
                        <div className="text-[10px] text-slate-600 mt-0.5 max-w-xs">{alert.description}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <SeverityChip severity={alert.severity} />
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-slate-400 font-mono">{alert.source}</span>
                      {(alert.source.includes('webhook') || alert.source.includes('splunk')) && (
                        <span className="inline-block px-1.5 py-0.5 rounded text-[9px] font-mono uppercase border border-[#c9b787]/30 bg-[#c9b787]/10 text-[#c9b787] w-fit">
                          SIEM
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-400 font-mono">{alert.asset ?? '—'}</td>
                  <td className="px-5 py-4">
                    <StatusChip status={alert.status} />
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500 font-mono whitespace-nowrap">
                    {relativeTime(alert.detectedAt)}
                  </td>
                  <td className="px-5 py-4">
                    {alert.status === 'open' ? (
                      <button
                        onClick={() => { void handleStatus(alert.id, 'acknowledged'); }}
                        disabled={updating === alert.id}
                        className="px-2 py-1 rounded text-[10px] font-mono border border-sky-500/30 bg-[#8a8a8a]/10 text-[#8a8a8a] hover:bg-[#8a8a8a]/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <Eye className="w-3 h-3" />
                        ACK
                      </button>
                    ) : alert.status === 'acknowledged' ? (
                      <button
                        onClick={() => { void handleStatus(alert.id, 'suppressed'); }}
                        disabled={updating === alert.id}
                        className="px-2 py-1 rounded text-[10px] font-mono border border-slate-600 text-slate-500 hover:bg-slate-800 transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <EyeOff className="w-3 h-3" />
                        Suppress
                      </button>
                    ) : (
                      <button
                        onClick={() => { void handleStatus(alert.id, 'open'); }}
                        disabled={updating === alert.id}
                        className="px-2 py-1 rounded text-[10px] font-mono border border-slate-700 text-slate-600 hover:bg-slate-800 transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        Reopen
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

