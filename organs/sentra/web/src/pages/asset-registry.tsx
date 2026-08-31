// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useEffect, useState } from 'react';
import {
  ChevronDown, ChevronRight, Cloud, Cpu, Database, Filter, Globe, Search, Server, Shield, ShieldAlert, ShieldCheck, ShieldOff, User, XCircle
} from 'lucide-react';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  useSentraStore, ensureSeeded, EXECUTABLE_STATUSES, NON_EXECUTABLE_STATUSES,
  type RegistryAsset, type OwnershipStatus, type AssetType, type AssetCriticality, type AssetStatus
} from '@/lib/sentra-store';

const OWNERSHIP_CONFIG: Record<OwnershipStatus, { label: string; color: string; icon: typeof Shield; executable: boolean; description: string }> = {
  owned: { label: 'OWNED', color: '#4ade80', icon: ShieldCheck, executable: true, description: 'Tenant-owned asset — full defensive action authorized' },
  authorized: { label: 'AUTHORIZED', color: '#60a5fa', icon: Shield, executable: true, description: 'Third-party asset with formal authorization — defensive action permitted per authorization reference' },
  contracted_scope: { label: 'CONTRACTED SCOPE', color: '#c9b787', icon: Shield, executable: true, description: 'Asset within contracted engagement scope — action permitted per SOW reference' },
  lab: { label: 'LAB', color: '#a78bfa', icon: Cpu, executable: true, description: 'Research/lab environment — defensive testing authorized' },
  blocked: { label: 'BLOCKED', color: '#e05252', icon: ShieldOff, executable: false, description: 'Asset is blocked — no action permitted' },
  unknown: { label: 'UNKNOWN', color: '#8a8a8a', icon: ShieldAlert, executable: false, description: 'Ownership unconfirmed — no action permitted until registered' },
  external: { label: 'EXTERNAL', color: '#f59e0b', icon: Globe, executable: false, description: 'External third-party asset — no action permitted' },
  attacker: { label: 'ATTACKER', color: '#ef4444', icon: XCircle, executable: false, description: 'Confirmed attacker-controlled asset — observe and report only' },
  unverified: { label: 'UNVERIFIED', color: '#8a8a8a', icon: ShieldAlert, executable: false, description: 'Ownership unverified — no action permitted' },
};

const TYPE_ICON: Record<AssetType, typeof Server> = {
  endpoint: Cpu, server: Server, cloud_resource: Cloud, identity: User, network_device: Globe,
  repository: Database, database: Database, container: Server, iam_role: User, api_gateway: Globe, other: Cpu,
};

const STATUS_COLOR: Record<AssetStatus, string> = {
  active: '#4ade80', isolated: '#f59e0b', compromised: '#e05252', decommissioned: '#8a8a8a', quarantined: '#c9b787',
};

const CRIT_COLOR: Record<AssetCriticality, string> = {
  critical: '#e05252', high: '#f59e0b', medium: '#c9b787', low: '#8a8a8a',
};

function OwnershipBadge({ status }: { status: OwnershipStatus }) {
  const cfg = OWNERSHIP_CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold border w-fit"
      style={{ color: cfg.color, borderColor: `${cfg.color}30`, background: `${cfg.color}10` }} title={cfg.description}>
      <Icon className="w-2.5 h-2.5" />
      {cfg.label}
      {cfg.executable ? (
        <ShieldCheck className="w-2 h-2 ml-0.5" />
      ) : (
        <ShieldOff className="w-2 h-2 ml-0.5" />
      )}
    </span>
  );
}

function AssetRow({ asset }: { asset: RegistryAsset }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = TYPE_ICON[asset.type] ?? Server;
  const cfg = OWNERSHIP_CONFIG[asset.ownership_status];

  return (
    <>
      <tr className={cn('hover:bg-slate-800/30 transition-colors cursor-pointer border-b border-slate-800/50', expanded && 'bg-slate-800/20')}
        onClick={() => setExpanded(x => !x)}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
            <Icon className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-slate-200">{asset.name}</div>
              <div className="text-[10px] font-mono text-slate-600">{asset.id}</div>
            </div>
          </div>
        </td>
        <td className="px-4 py-3">
          <span className="text-[10px] font-mono text-slate-400 px-2 py-0.5 rounded bg-slate-800 border border-slate-700">{asset.type.replace(/_/g, ' ').toUpperCase()}</span>
        </td>
        <td className="px-4 py-3"><OwnershipBadge status={asset.ownership_status} /></td>
        <td className="px-4 py-3">
          <span className="text-[10px] font-mono font-bold" style={{ color: CRIT_COLOR[asset.criticality] }}>{asset.criticality.toUpperCase()}</span>
        </td>
        <td className="px-4 py-3">
          <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold border"
            style={{ color: STATUS_COLOR[asset.status], borderColor: `${STATUS_COLOR[asset.status]}30`, background: `${STATUS_COLOR[asset.status]}10` }}>
            {asset.status.toUpperCase()}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className="text-[10px] font-mono text-slate-500">{asset.provider.toUpperCase()}</span>
        </td>
        <td className="px-4 py-3">
          <span className="text-[10px] font-mono text-slate-500">{asset.env}</span>
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-1">
            {cfg.executable ? (
              <span className="flex items-center gap-1 text-[9px] font-mono text-green-400">
                <ShieldCheck className="w-2.5 h-2.5" /> YES
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[9px] font-mono text-red-400">
                <ShieldOff className="w-2.5 h-2.5" /> NO
              </span>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/60">
          <td colSpan={8} className="px-6 py-4 border-b border-slate-800">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div>
                <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Asset Details</div>
                <div className="space-y-1">
                  {asset.hostname && <div className="flex justify-between"><span className="text-slate-500">Hostname</span><span className="text-slate-300 font-mono">{asset.hostname}</span></div>}
                  {asset.ip_address && <div className="flex justify-between"><span className="text-slate-500">IP Address</span><span className="text-slate-300 font-mono">{asset.ip_address}</span></div>}
                  <div className="flex justify-between"><span className="text-slate-500">Region</span><span className="text-slate-300 font-mono">{asset.region}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Environment</span><span className="text-slate-300 font-mono">{asset.env}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Integration</span><span className="text-slate-300 font-mono">{asset.integration_id ?? '—'}</span></div>
                </div>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Ownership & Authorization</div>
                <div className="space-y-1">
                  <div className="flex justify-between"><span className="text-slate-500">Status</span><span style={{ color: cfg.color }} className="font-mono font-bold">{cfg.label}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Executable</span><span className={cfg.executable ? 'text-green-400' : 'text-red-400'} >{cfg.executable ? 'YES' : 'NO'}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Auth Ref</span><span className="text-slate-300 font-mono">{asset.authorization_reference || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Owners</span><span className="text-slate-300">{asset.owners.join(', ') || '—'}</span></div>
                </div>
                <div className="mt-2 p-2 rounded bg-slate-800/60 text-[10px] text-slate-500 italic">{cfg.description}</div>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Tags</div>
                <div className="flex flex-wrap gap-1">
                  {asset.tags.map(tag => (
                    <span key={tag} className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">{tag}</span>
                  ))}
                  {asset.tags.length === 0 && <span className="text-slate-600">No tags</span>}
                </div>
                <div className="mt-3 text-[10px] font-mono text-slate-600">
                  Created: {new Date(asset.created_at).toLocaleDateString()}<br />
                  Updated: {new Date(asset.updated_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AssetRegistry() {
  useEffect(() => { ensureSeeded(); }, []);
  const store = useSentraStore();

  const [search, setSearch] = useState('');
  const [ownershipFilter, setOwnershipFilter] = useState<OwnershipStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [critFilter, setCritFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [execFilter, setExecFilter] = useState<'all' | 'executable' | 'non-executable'>('all');

  const assets = store.assets;
  const filtered = assets.filter(a => {
    if (ownershipFilter !== 'all' && a.ownership_status !== ownershipFilter) return false;
    if (typeFilter !== 'all' && a.type !== typeFilter) return false;
    if (critFilter !== 'all' && a.criticality !== critFilter) return false;
    if (statusFilter !== 'all' && a.status !== statusFilter) return false;
    if (execFilter === 'executable' && !EXECUTABLE_STATUSES.includes(a.ownership_status)) return false;
    if (execFilter === 'non-executable' && !NON_EXECUTABLE_STATUSES.includes(a.ownership_status)) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.name.toLowerCase().includes(q) || a.id.toLowerCase().includes(q) || a.type.includes(q);
    }
    return true;
  });

  const executableCount = assets.filter(a => EXECUTABLE_STATUSES.includes(a.ownership_status)).length;
  const nonExecCount = assets.filter(a => NON_EXECUTABLE_STATUSES.includes(a.ownership_status)).length;
  const compromisedCount = assets.filter(a => a.status === 'compromised').length;
  const isolatedCount = assets.filter(a => a.status === 'isolated').length;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Server className="w-4 h-4 text-[#c9b787]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Sentra — Asset Registry</span>
        </div>
        <h1 className="text-2xl font-display font-bold text-slate-100">Asset Registry</h1>
        <p className="text-sm text-slate-500 mt-1">
          Tenant-owned and authorized assets eligible for defensive action. Ownership status determines executability.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Assets', value: assets.length, color: '#f5f5f5' },
          { label: 'Executable', value: executableCount, color: '#4ade80', sub: 'owned/authorized/lab' },
          { label: 'Non-Executable', value: nonExecCount, color: '#e05252', sub: 'external/attacker/unknown' },
          { label: 'Compromised/Isolated', value: compromisedCount + isolatedCount, color: '#f59e0b', sub: `${compromisedCount} compromised` },
        ].map(({ label, value, color, sub }) => (
          <div key={label} className="rounded-lg border p-4" style={{ background: 'rgba(255,255,255,0.025)', borderColor: 'rgba(255,255,255,0.08)' }}>
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">{label}</div>
            <div className="text-2xl font-display font-bold" style={{ color }}>{value}</div>
            {sub && <div className="text-[10px] text-slate-600 font-mono mt-0.5">{sub}</div>}
          </div>
        ))}
      </div>

      {/* Ownership legend */}
      <div className="rounded-lg border p-3" style={{ background: 'rgba(201,183,135,0.04)', borderColor: 'rgba(201,183,135,0.12)' }}>
        <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Ownership Status Legend</div>
        <div className="flex flex-wrap gap-3">
          {Object.entries(OWNERSHIP_CONFIG).map(([status, cfg]) => {
            const Icon = cfg.icon;
            return (
              <div key={status} className="flex items-center gap-1.5">
                <Icon className="w-3 h-3" style={{ color: cfg.color }} />
                <span className="text-[10px] font-mono font-bold" style={{ color: cfg.color }}>{cfg.label}</span>
                <span className="text-[10px] text-slate-600">— {cfg.executable ? 'executable' : 'blocked'}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search assets…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#c9b787]/40" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          {[
            { value: ownershipFilter, setter: setOwnershipFilter as (v: string) => void, options: [['all', 'All Ownership'], ...Object.keys(OWNERSHIP_CONFIG).map(k => [k, OWNERSHIP_CONFIG[k as OwnershipStatus].label])] },
            { value: typeFilter, setter: setTypeFilter, options: [['all', 'All Types'], ['endpoint', 'Endpoint'], ['server', 'Server'], ['cloud_resource', 'Cloud'], ['identity', 'Identity'], ['database', 'Database'], ['repository', 'Repo'], ['container', 'Container'], ['network_device', 'Network'], ['other', 'Other']] },
            { value: critFilter, setter: setCritFilter, options: [['all', 'All Criticality'], ['critical', 'Critical'], ['high', 'High'], ['medium', 'Medium'], ['low', 'Low']] },
            { value: statusFilter, setter: setStatusFilter, options: [['all', 'All Status'], ['active', 'Active'], ['isolated', 'Isolated'], ['compromised', 'Compromised'], ['quarantined', 'Quarantined'], ['decommissioned', 'Decommissioned']] },
            { value: execFilter, setter: setExecFilter as (v: string) => void, options: [['all', 'Executability: All'], ['executable', 'Executable Only'], ['non-executable', 'Non-Executable Only']] },
          ].map(({ value, setter, options }, i) => (
            <select key={i} value={value} onChange={e => setter(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none">
              {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          ))}
        </div>
        <span className="text-[10px] font-mono text-slate-600">{filtered.length} of {assets.length}</span>
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-800/50 border-b border-slate-700/50 text-[10px] font-mono uppercase tracking-wider text-slate-500">
                {['Asset', 'Type', 'Ownership', 'Criticality', 'Status', 'Provider', 'Env', 'Executable'].map(h => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 100).map(asset => <AssetRow key={asset.id} asset={asset} />)}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 border-t border-slate-800 text-[10px] text-slate-600 font-mono flex items-center justify-between">
          <span>Showing {Math.min(filtered.length, 100)} of {filtered.length} assets · Click row to expand</span>
          {filtered.length > 100 && <span className="text-[#c9b787]">Showing first 100 — use filters to narrow</span>}
        </div>
      </div>
    </div>
  );
}
