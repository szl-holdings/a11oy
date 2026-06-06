import { useMemo, useState } from 'react';
import { RELAY_RUN_EVENTS } from '@/data/fabric';
import { rankSyncRisk, generateRecommendedAction } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, SeverityChip, Sparkline } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { AmaruEventsPanel } from '@/components/AmaruLive';

export default function ObservabilityPage() {
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [vertical, setVertical] = useState('');
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const rows = useMemo(() => {
    return RELAY_RUN_EVENTS.filter((e) => {
      if (q && !`${e.syncName} ${e.summary}`.toLowerCase().includes(q.toLowerCase())) return false;
      if (type && e.type !== type) return false;
      if (vertical && e.verticalId !== vertical) return false;
      return true;
    }).slice(0, 200);
  }, [q, type, vertical]);

  const total = RELAY_RUN_EVENTS.length;
  const failed = RELAY_RUN_EVENTS.filter((e) => e.type === 'failed' || e.type === 'rolled_back').length;
  const blocked = RELAY_RUN_EVENTS.filter((e) => e.type === 'quarantined').length;
  const completed = RELAY_RUN_EVENTS.filter((e) => e.type === 'completed').length;

  const risk = rankSyncRisk(RELAY_RUN_EVENTS).slice(0, 6);

  // Throughput sparkline by hour over last 12 hours.
  const sparkData = useMemo(() => {
    const buckets = new Array(12).fill(0);
    const now = Date.parse('2026-05-05T03:55:00Z');
    for (const e of RELAY_RUN_EVENTS) {
      if (e.type !== 'completed') continue;
      const idx = Math.floor((now - Date.parse(e.atIso)) / (60 * 60 * 1000));
      if (idx >= 0 && idx < 12) buckets[11 - idx] += e.recordsAffected;
    }
    return buckets;
  }, []);

  const drawer = drawerId ? RELAY_RUN_EVENTS.find((e) => e.id === drawerId)! : null;

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 06"
        title="Observability"
        blurb="Every step every agent took on every batch. Hash-chained, replay-grade, and witnessable. Click any event to see the witness; click any sync to see what Forecaster expected."
        trailing={
          <div className="text-right">
            <div className="label-mono">Throughput · last 12h</div>
            <Sparkline values={sparkData} width={180} height={40} tone="gold" />
          </div>
        }
      />
      <AmaruEventsPanel limit={30} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Events captured" value={total} tone="gold" />
        <FabricStat label="Completed" value={completed} tone="good" />
        <FabricStat label="Failed / rolled back" value={failed} tone={failed > 10 ? 'bad' : 'warn'} />
        <FabricStat label="Quarantined" value={blocked} tone="warn" />
      </div>

      <div className="conduit-card p-4 mb-6">
        <div className="label-mono mb-3 text-[#c9b787]">SYNC RISK · TOP 6</div>
        <div className="space-y-2">
          {risk.map((r) => (
            <div key={r.syncId} className="flex items-center justify-between text-[12px] p-2 rounded bg-[#0e0e0e]">
              <div className="min-w-0 flex-1">
                <div className="font-mono text-[#f5f5f5] truncate">{r.syncName}</div>
                <div className="text-[10px] text-[#666] truncate">{r.drivers.join(' · ') || 'no recent issues'}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <Badge variant={r.health === 'failing' ? 'failed' : r.health === 'degraded' ? 'partial' : 'success'}>{r.health}</Badge>
                <div className="font-mono tabular-nums text-[#c9b787] w-10 text-right">{r.score}</div>
                <div className="text-[10px] text-[#8a8a8a] w-44 text-right truncate">{generateRecommendedAction(r)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <FabricToolbar>
        <Input placeholder="Search events…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={type} onChange={(e) => setType(e.target.value)} className="max-w-xs">
          <option value="">All event types</option>
          {Array.from(new Set(RELAY_RUN_EVENTS.map((e) => e.type))).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </Select>
        <Select value={vertical} onChange={(e) => setVertical(e.target.value)} className="max-w-xs">
          <option value="">All verticals</option>
          {Array.from(new Set(RELAY_RUN_EVENTS.map((e) => e.verticalId))).map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </Select>
      </FabricToolbar>

      <div className="conduit-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#666] border-b border-[rgba(255,255,255,0.06)]">
            <tr>
              <th className="text-left px-4 py-3">When</th>
              <th className="text-left px-4 py-3">Sync</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Agent</th>
              <th className="text-right px-4 py-3">Records</th>
              <th className="text-right px-4 py-3">Latency</th>
              <th className="text-left px-4 py-3">Sev</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[#1a1a1a] cursor-pointer transition-colors" onClick={() => setDrawerId(e.id)}>
                <td className="px-4 py-2 font-mono text-[11px] text-[#666]">{new Date(e.atIso).toLocaleTimeString()}</td>
                <td className="px-4 py-2 text-[12px] text-[#f5f5f5] truncate max-w-xs">{e.syncName}</td>
                <td className="px-4 py-2 text-[11px] text-[#8a8a8a] font-mono">{e.type}</td>
                <td className="px-4 py-2 text-[11px] text-[#c9b787]">{e.agentId ?? '—'}</td>
                <td className="px-4 py-2 text-right tabular-nums text-[11px] text-[#8a8a8a]">{e.recordsAffected ? e.recordsAffected.toLocaleString() : '—'}</td>
                <td className="px-4 py-2 text-right tabular-nums text-[11px] text-[#8a8a8a]">{e.latencyMs}ms</td>
                <td className="px-4 py-2"><SeverityChip level={e.severity} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FabricDrawer open={!!drawer} onClose={() => setDrawerId(null)} title={drawer?.summary ?? ''} subtitle={drawer ? `${drawer.syncName} · ${drawer.type}` : ''}>
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Records" value={drawer.recordsAffected.toLocaleString()} />
              <FabricStat label="Latency" value={`${drawer.latencyMs}ms`} />
              <FabricStat label="Agent" value={drawer.agentId ?? '—'} tone="gold" />
              <FabricStat label="Severity" value={drawer.severity.toUpperCase()} tone={drawer.severity === 'critical' ? 'bad' : drawer.severity === 'high' ? 'warn' : 'neutral'} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">STATE HASH</div>
              <div className="font-mono text-[11px] text-[#8a8a8a] break-all">{drawer.stateHash}</div>
            </div>
            {drawer.evidenceRef && (
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-[#c9b787]">EVIDENCE REF</div>
                <div className="font-mono text-[11px] text-[#8a8a8a]">{drawer.evidenceRef}</div>
              </div>
            )}
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
