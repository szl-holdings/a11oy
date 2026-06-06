import { useMemo, useState } from 'react';
import { RELAY_SOURCES } from '@/data/fabric';
import type { RelaySource } from '@/data/fabric/types';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';

export default function SourcesPage() {
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const [state, setState] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'rows' | 'tables' | 'quality'>('name');
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const rows = useMemo(() => {
    const filtered = RELAY_SOURCES.filter((s) => {
      if (q && !`${s.name} ${s.owner}`.toLowerCase().includes(q.toLowerCase())) return false;
      if (kind && s.kind !== kind) return false;
      if (state && s.governanceState !== state) return false;
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sortBy === 'rows') return b.rowCount - a.rowCount;
      if (sortBy === 'tables') return b.tableCount - a.tableCount;
      if (sortBy === 'quality') return b.qualityScore - a.qualityScore;
      return a.name.localeCompare(b.name);
    });
  }, [q, kind, state, sortBy]);

  const totalRows = RELAY_SOURCES.reduce((s, r) => s + r.rowCount, 0);
  const piiCount = RELAY_SOURCES.filter((s) => s.piiDetected).length;
  const greenCount = RELAY_SOURCES.filter((s) => s.governanceState === 'green').length;
  const stale = RELAY_SOURCES.filter((s) => s.freshnessTier === 'stale').length;

  const drawer = drawerId ? RELAY_SOURCES.find((s) => s.id === drawerId)! : null;

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 01"
        title="Sources"
        blurb="Every warehouse, OLTP store, event stream, object store, and webhook the spine has touched. Cartographer profiles each one on connect — quality, freshness, PII surface — and surfaces candidate models for the Mapper."
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Sources" value={RELAY_SOURCES.length} sub={`${greenCount} green · ${stale} stale`} tone="gold" />
        <FabricStat label="Rows under spine" value={(totalRows / 1_000_000_000).toFixed(1) + 'B'} />
        <FabricStat label="PII-bearing" value={piiCount} sub={`${Math.round((piiCount / RELAY_SOURCES.length) * 100)}% of fleet`} tone="warn" />
        <FabricStat label="Realtime tier" value={RELAY_SOURCES.filter((s) => s.freshnessTier === 'realtime').length} tone="good" />
      </div>

      <FabricToolbar>
        <Input placeholder="Search sources or owners…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={kind} onChange={(e) => setKind(e.target.value)} className="max-w-xs">
          <option value="">All kinds</option>
          {Array.from(new Set(RELAY_SOURCES.map((s) => s.kind))).map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </Select>
        <Select value={state} onChange={(e) => setState(e.target.value)} className="max-w-xs">
          <option value="">All governance states</option>
          <option value="green">Green</option>
          <option value="amber">Amber</option>
          <option value="red">Red</option>
        </Select>
        <Select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="max-w-xs">
          <option value="name">Sort: Name</option>
          <option value="rows">Sort: Rows ↓</option>
          <option value="tables">Sort: Tables ↓</option>
          <option value="quality">Sort: Quality ↓</option>
        </Select>
      </FabricToolbar>

      <div className="conduit-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#666] border-b border-[rgba(255,255,255,0.06)]">
            <tr>
              <th className="text-left px-4 py-3">Source</th>
              <th className="text-left px-4 py-3">Kind</th>
              <th className="text-right px-4 py-3">Tables</th>
              <th className="text-right px-4 py-3">Rows</th>
              <th className="text-left px-4 py-3">Freshness</th>
              <th className="text-left px-4 py-3">Quality</th>
              <th className="text-left px-4 py-3">PII</th>
              <th className="text-left px-4 py-3">State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s: RelaySource) => (
              <tr
                key={s.id}
                className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[#1a1a1a] cursor-pointer transition-colors"
                onClick={() => setDrawerId(s.id)}
              >
                <td className="px-4 py-3">
                  <div className="font-mono text-[#f5f5f5]">{s.name}</div>
                  <div className="text-[11px] text-[#666]">{s.owner}</div>
                </td>
                <td className="px-4 py-3 text-[#8a8a8a]">{s.kind.replace(/_/g, ' ')}</td>
                <td className="px-4 py-3 text-right tabular-nums text-[#8a8a8a]">{s.tableCount}</td>
                <td className="px-4 py-3 text-right tabular-nums text-[#8a8a8a]">{(s.rowCount / 1_000_000).toFixed(1)}M</td>
                <td className="px-4 py-3">
                  <div className="text-[12px] text-[#f5f5f5]">{s.freshnessTier.replace('_', ' ')}</div>
                  <div className="text-[10px] text-[#666]">{s.freshnessLagSeconds < 60 ? `${s.freshnessLagSeconds}s` : `${Math.round(s.freshnessLagSeconds / 60)}m`} lag</div>
                </td>
                <td className="px-4 py-3 w-32"><MicroBar value={s.qualityScore} max={100} tone={s.qualityScore >= 85 ? 'good' : s.qualityScore >= 70 ? 'warn' : 'bad'} /></td>
                <td className="px-4 py-3">{s.piiDetected ? <Badge variant="partial">PII</Badge> : <span className="text-[#666] text-[12px]">—</span>}</td>
                <td className="px-4 py-3"><GovernanceDot state={s.governanceState} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FabricDrawer
        open={!!drawer}
        onClose={() => setDrawerId(null)}
        title={drawer?.name ?? ''}
        subtitle={drawer ? `${drawer.kind} · owner ${drawer.owner}` : ''}
      >
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Tables" value={drawer.tableCount} />
              <FabricStat label="Rows" value={(drawer.rowCount / 1_000_000).toFixed(1) + 'M'} />
              <FabricStat label="Freshness lag" value={drawer.freshnessLagSeconds + 's'} tone={drawer.freshnessLagSeconds < 60 ? 'good' : 'warn'} />
              <FabricStat label="Quality" value={drawer.qualityScore} tone={drawer.qualityScore >= 85 ? 'good' : 'warn'} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">PII CLASSES DETECTED</div>
              {drawer.piiClassesDetected.length === 0 ? (
                <div className="text-[12px] text-[#666]">None detected</div>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {drawer.piiClassesDetected.map((c) => (
                    <Badge key={c} variant="partial">{c}</Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">VERTICAL COVERAGE</div>
              <div className="flex flex-wrap gap-1">
                {drawer.verticalCoverage.map((v) => (
                  <Badge key={v} variant="default">{v}</Badge>
                ))}
              </div>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">ANCHOR HASH</div>
              <div className="font-mono text-[12px] text-[#8a8a8a] break-all">{drawer.anchorHash}</div>
              <div className="text-[11px] text-[#666] mt-1">Last profiled {new Date(drawer.lastProfiledAt).toLocaleString()}</div>
            </div>
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
