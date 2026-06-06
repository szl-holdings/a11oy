// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  Cloud,
  Eye,
  Globe,
  Key,
  Layers,
  Loader2,
  Network,
  Search,
  Server,
  ShieldAlert,
  Wifi,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  type AttackSurfaceResponse,
  getAttackSurfacePage,
} from '../lib/sentra-api';

const TYPE_ICONS: Record<string, typeof Server> = {
  web: Globe, api: Network, rdp: Server, ssh: Key,
  database: Layers, cloud: Cloud, iot: Wifi, email: Activity,
};

const TYPE_COLORS: Record<string, string> = {
  web: '#8a8a8a', api: '#c9b787', rdp: '#f5f5f5', ssh: '#c9b787',
  database: '#c9b787', cloud: '#8a8a8a', iot: '#f5f5f5', email: '#c9b787',
};

export default function AttackSurfaceCommand() {
  const [data, setData] = useState<AttackSurfaceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'shadow' | 'critical'>('all');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getAttackSurfacePage()
      .then((res) => {
        if (!active) return;
        if (!res) {
          setError('Unable to load Attack Surface data.');
        } else {
          setData(res);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-xs text-zinc-400">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading Attack Surface data…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-[#f5f5f5]/30 bg-[#f5f5f5]/5 p-4 text-xs text-[#f5f5f5]">
          {error ?? 'Attack Surface data unavailable.'}
        </div>
      </div>
    );
  }

  const { discoveredAssets, supplyChainVendors, responsePlaybooks } = data;
  const totalAssets = discoveredAssets.length;
  const unknownAssets = discoveredAssets.filter((a) => !a.isKnown).length;
  const shadowIT = discoveredAssets.filter((a) => a.isShadowIT).length;
  const criticalExposed = discoveredAssets.filter((a) => a.severity === 'critical').length;
  const discoveryRate = totalAssets > 0 ? Math.round((unknownAssets / totalAssets) * 100) : 0;

  const filtered = filter === 'shadow'
    ? discoveredAssets.filter((a) => a.isShadowIT)
    : filter === 'critical'
      ? discoveredAssets.filter((a) => a.severity === 'critical')
      : discoveredAssets;

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Globe className="w-5 h-5 text-[#8a8a8a]" />
            <h1 className="text-lg font-semibold text-white">Attack Surface Command</h1>
            <span className="text-[9px] px-2 py-0.5 rounded-full border border-[#8a8a8a]/30 bg-[#8a8a8a]/10 text-[#8a8a8a] font-mono uppercase">
              Xpanse-Style
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            Continuous external asset discovery — shadow IT detection, supply-chain exposure, automated response playbooks
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[10px] text-[#c9b787]">
            <Search className="w-3 h-3" />
            Scanning continuously
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Total Assets Discovered', value: totalAssets.toString(), sub: 'across all segments', color: '#8a8a8a', icon: Globe },
          { label: 'Unknown Assets', value: unknownAssets.toString(), sub: `${discoveryRate}% discovery rate`, color: '#f5f5f5', icon: AlertTriangle },
          { label: 'Shadow IT Detected', value: shadowIT.toString(), sub: 'unmanaged services', color: '#c9b787', icon: Eye },
          { label: 'Critical Exposures', value: criticalExposed.toString(), sub: 'internet-facing risk', color: '#f5f5f5', icon: ShieldAlert },
          { label: 'Vendor Exposure', value: supplyChainVendors.length.toString(), sub: 'third-party risk vectors', color: '#c9b787', icon: Network },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-xl font-bold text-white font-mono">{m.value}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
              <Search className="w-3.5 h-3.5 text-[#8a8a8a]" />
              External Asset Discovery
            </h2>
            <div className="flex items-center gap-1">
              {(['all', 'shadow', 'critical'] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)} className={cn(
                  'text-[10px] px-2 py-1 rounded border transition-colors',
                  filter === f ? 'bg-white/10 border-white/20 text-white' : 'border-white/5 text-zinc-500 hover:text-zinc-300',
                )}>
                  {f === 'all' ? 'All' : f === 'shadow' ? 'Shadow IT' : 'Critical'}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            {filtered.map((asset) => {
              const Icon = TYPE_ICONS[asset.type] ?? Server;
              const isSelected = selectedAsset === asset.id;
              return (
                <button key={asset.id} onClick={() => setSelectedAsset(isSelected ? null : asset.id)} className={cn(
                  'w-full rounded-xl border p-3 text-left transition-all',
                  isSelected ? 'border-[#8a8a8a]/40 bg-[#8a8a8a]/5' :
                  asset.severity === 'critical' ? 'border-[#f5f5f5]/15 bg-white/3 hover:bg-white/5' :
                  'border-white/8 bg-white/3 hover:bg-white/5',
                )}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${TYPE_COLORS[asset.type]}15`, border: `1px solid ${TYPE_COLORS[asset.type]}30` }}>
                      <Icon className="w-4 h-4" style={{ color: TYPE_COLORS[asset.type] }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-medium text-white">{asset.domain}</span>
                        {asset.isShadowIT && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10">Shadow IT</span>
                        )}
                        {!asset.isKnown && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10">Unknown</span>
                        )}
                        <span className={cn(
                          'text-[9px] px-1.5 py-0.5 rounded border',
                          asset.severity === 'critical' ? 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10' :
                          asset.severity === 'high' ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10' :
                          'text-zinc-400 border-zinc-700 bg-zinc-800/50',
                        )}>
                          {asset.severity}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-zinc-500 mt-1">
                        <span className="font-mono">{asset.ip}:{asset.port}</span>
                        <span>{asset.org}</span>
                        <span>{asset.cves} CVEs</span>
                        <span>Last: {asset.lastSeen}</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <span className={cn('text-sm font-bold font-mono', asset.risk >= 90 ? 'text-[#f5f5f5]' : asset.risk >= 75 ? 'text-[#c9b787]' : 'text-zinc-400')}>
                        {asset.risk}
                      </span>
                      <span className="text-[9px] text-zinc-500 block">risk</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Network className="w-3.5 h-3.5 text-[#c9b787]" />
              Supply Chain Exposure
            </h2>
            <div className="space-y-2">
              {supplyChainVendors.map((vendor) => (
                <div key={vendor.id} className={cn(
                  'rounded-xl border p-3',
                  vendor.risk === 'critical' ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/3' : 'border-white/8 bg-white/3',
                )}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-medium text-white">{vendor.name}</span>
                    <span className={cn(
                      'text-[9px] px-1.5 py-0.5 rounded border',
                      vendor.risk === 'critical' ? 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10' :
                      vendor.risk === 'high' ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10' :
                      'text-zinc-400 border-zinc-700 bg-zinc-800/50',
                    )}>
                      {vendor.risk}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                    <span>{vendor.exposedAssets} exposed assets</span>
                    <span>{vendor.breachHistory} prior breaches</span>
                    <span>Assessed: {vendor.lastAssessment}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-[#c9b787]" />
              Active Response Playbooks
            </h2>
            <div className="space-y-2">
              {responsePlaybooks.map((pb) => (
                <div key={pb.id} className="rounded-xl border border-white/8 bg-white/3 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-medium text-white">{pb.name}</span>
                    {pb.autoExecute && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10">Auto</span>
                    )}
                  </div>
                  <p className="text-[10px] text-zinc-400 mb-1.5">{pb.trigger}</p>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>{pb.actions.length} actions</span>
                    <span>Last run: {pb.lastRun}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
