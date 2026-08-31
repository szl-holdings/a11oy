// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import { ChevronDown, ChevronRight, Cpu, Database, Filter, RefreshCcw, Search, ShieldAlert } from 'lucide-react';
import { useCallback, useState } from 'react';
import { EmptyState, PageHeader, SeverityChip } from '@/lib/data-provenance';
import { sentraTwin as fallbackTwin, type CyberAsset } from '@/data/sentra-twin';
import { listCyberTwinAssets } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

type FilterType = 'all' | 'OT' | 'IT' | 'IoT';
type FilterCriticality = 'all' | 'critical' | 'high' | 'medium' | 'low';
type FilterStatus = 'all' | 'compromised' | 'isolated' | 'active';

const TYPE_ICON: Record<string, typeof Cpu> = {
  OT: ShieldAlert,
  IT: Database,
  IoT: Cpu,
};

function ExposureBar({ score }: { score: number }) {
  const color =
    score > 80 ? '#f5f5f5' : score > 50 ? '#c9b787' : score > 30 ? '#c9b787' : '#c9b787';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono text-slate-300 tabular-nums">{score}</span>
    </div>
  );
}

function AssetRow({ asset }: { asset: CyberAsset }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = TYPE_ICON[asset.type] ?? Cpu;

  return (
    <>
      <tr
        className={cn(
          'hover:bg-slate-800/30 transition-colors cursor-pointer',
          expanded && 'bg-slate-800/20',
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-5 py-4">
          <div className="flex items-center gap-3">
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            )}
            <div>
              <div className="font-bold text-slate-200">{asset.name}</div>
              <div className="text-[10px] text-slate-500 font-mono uppercase">{asset.id}</div>
            </div>
          </div>
        </td>
        <td className="px-5 py-4">
          <span
            className={cn(
              'px-2 py-0.5 rounded text-[10px] font-mono font-bold border flex items-center gap-1 w-fit',
              asset.type === 'OT'
                ? 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20'
                : asset.type === 'IT'
                  ? 'bg-[#8a8a8a]/10 text-[#8a8a8a] border-sky-500/20'
                  : 'bg-[#8a8a8a]/10 text-[#8a8a8a] border-[#8a8a8a]/20',
            )}
          >
            <Icon className="w-2.5 h-2.5" />
            {asset.type}
          </span>
        </td>
        <td className="px-5 py-4">
          <SeverityChip severity={asset.criticality} />
        </td>
        <td className="px-5 py-4">
          <ExposureBar score={asset.exposureScore} />
        </td>
        <td className="px-5 py-4">
          <div
            className={cn(
              'flex items-center gap-2 text-xs font-mono',
              asset.backupStatus === 'current'
                ? 'text-[#c9b787]'
                : asset.backupStatus === 'stale'
                  ? 'text-[#c9b787]'
                  : 'text-[#f5f5f5]',
            )}
          >
            <RefreshCcw className="w-3 h-3" />
            {asset.backupStatus.toUpperCase()}
          </div>
          {asset.lastBackupAt && (
            <div className="text-[10px] text-slate-600 mt-0.5 font-mono">
              {Math.floor((Date.now() - new Date(asset.lastBackupAt).getTime()) / 3_600_000)}h ago
            </div>
          )}
        </td>
        <td className="px-5 py-4 text-xs text-[#f5f5f5]/70 font-mono">
          {asset.controlGaps.length > 0 ? `${asset.controlGaps.length} gap${asset.controlGaps.length > 1 ? 's' : ''}` : '—'}
        </td>
        <td className="px-5 py-4">
          <span
            className={cn(
              'px-2 py-1 rounded-full text-[10px] font-bold border',
              asset.status === 'compromised'
                ? 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/30'
                : asset.status === 'isolated'
                  ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30'
                  : 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30',
            )}
          >
            {asset.status.toUpperCase()}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/60">
          <td colSpan={7} className="px-8 py-4 border-b border-slate-800">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <div className="text-[10px] text-slate-500 font-mono uppercase mb-2">Control Gaps</div>
                {asset.controlGaps.length > 0 ? (
                  <ul className="space-y-1">
                    {asset.controlGaps.map((gap, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-[#f5f5f5]">
                        <ShieldAlert className="w-3 h-3 shrink-0" />
                        {gap}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-600">No control gaps detected</p>
                )}
              </div>
              <div>
                <div className="text-[10px] text-slate-500 font-mono uppercase mb-2">Asset Details</div>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Criticality</span>
                    <span className="text-slate-300 font-mono uppercase">{asset.criticality}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Type</span>
                    <span className="text-slate-300 font-mono">{asset.type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Exposure Score</span>
                    <span
                      className="font-mono font-bold"
                      style={{
                        color:
                          asset.exposureScore > 80
                            ? '#f5f5f5'
                            : asset.exposureScore > 50
                              ? '#c9b787'
                              : '#c9b787',
                      }}
                    >
                      {asset.exposureScore}/100
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Backup</span>
                    <span className="text-slate-300 font-mono">{asset.backupStatus}</span>
                  </div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AssetRiskGraph() {
  const [typeFilter, setTypeFilter] = useState<FilterType>('all');
  const [critFilter, setCritFilter] = useState<FilterCriticality>('all');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [search, setSearch] = useState('');

  const assetFetcher = useCallback(() => listCyberTwinAssets(), []);
  const { data: allAssets, source } = useApiQuery<CyberAsset[]>(assetFetcher, 'assets', fallbackTwin.assets);

  const filtered = allAssets.filter((a) => {
    if (typeFilter !== 'all' && a.type !== typeFilter) return false;
    if (critFilter !== 'all' && a.criticality !== critFilter) return false;
    if (statusFilter !== 'all' && a.status !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.name.toLowerCase().includes(q) || a.id.toLowerCase().includes(q);
    }
    return true;
  });

  const atRisk = allAssets.filter((a) => a.exposureScore > 70).length;

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Asset Risk Graph"
        subtitle="Critical infrastructure exposure and protection status"
        provenance={source}
        provenanceLabel={source === 'live' ? 'Live API' : 'Seed Data'}
        actions={
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-slate-800 border border-slate-700 text-xs text-slate-300 font-mono">
            <Database className="w-3 h-3" />
            TOTAL: {allAssets.length}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Total Assets</div>
          <div className="text-2xl font-display font-bold text-slate-100">{allAssets.length}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">At Risk</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{atRisk}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Compromised</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">
            {allAssets.filter((a) => a.status === 'compromised').length}
          </div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Control Gaps</div>
          <div className="text-2xl font-display font-bold text-[#c9b787]">
            {allAssets.reduce((acc, a) => acc + a.controlGaps.length, 0)}
          </div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-40">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search assets…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#f5f5f5]/40"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as FilterType)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none"
          >
            <option value="all">All Types</option>
            <option value="OT">OT</option>
            <option value="IT">IT</option>
            <option value="IoT">IoT</option>
          </select>
          <select
            value={critFilter}
            onChange={(e) => setCritFilter(e.target.value as FilterCriticality)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none"
          >
            <option value="all">All Criticality</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as FilterStatus)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="compromised">Compromised</option>
            <option value="isolated">Isolated</option>
            <option value="active">Active</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Cpu}
          title="No assets match your filters"
          subtitle="Try adjusting the type, criticality, or status filter"
        />
      ) : (
        <div className="sentra-panel overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-800/50 border-b border-[#f5f5f5]/10 text-[11px] uppercase tracking-wider text-slate-400 font-mono">
                <th className="px-5 py-4 font-medium">Asset Name</th>
                <th className="px-5 py-4 font-medium">Type</th>
                <th className="px-5 py-4 font-medium">Criticality</th>
                <th className="px-5 py-4 font-medium">Exposure</th>
                <th className="px-5 py-4 font-medium">Backup</th>
                <th className="px-5 py-4 font-medium">Control Gaps</th>
                <th className="px-5 py-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filtered.map((asset) => (
                <AssetRow key={asset.id} asset={asset} />
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 border-t border-slate-800 text-[10px] text-slate-600 font-mono">
            Showing {filtered.length} of {allAssets.length} assets · Click a row to expand details
          </div>
        </div>
      )}
    </div>
  );
}
