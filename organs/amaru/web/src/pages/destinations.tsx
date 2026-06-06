import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_DESTINATIONS, RELAY_RUN_EVENTS } from '@/data/fabric';
import { calculateDestinationHealth } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { useInnovationStore } from '@/lib/innovation-store';
import { Search } from 'lucide-react';

export default function DestinationsPage() {
  const { discoveredDestinations } = useInnovationStore();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const allDestinations = useMemo(() => [...discoveredDestinations, ...RELAY_DESTINATIONS], [discoveredDestinations]);
  const discoveredIds = useMemo(() => new Set(discoveredDestinations.map((d) => d.id)), [discoveredDestinations]);

  const rows = useMemo(() => {
    return allDestinations
      .filter((d) => {
        if (q && !d.name.toLowerCase().includes(q.toLowerCase())) return false;
        if (cat && d.category !== cat) return false;
        return true;
      })
      .map((d) => ({ ...d, computedHealth: calculateDestinationHealth(d, RELAY_RUN_EVENTS) }))
      .sort((a, b) => a.computedHealth - b.computedHealth);
  }, [q, cat, allDestinations]);

  const greenCount = allDestinations.filter((d) => d.governanceState === 'green').length;
  const amberCount = allDestinations.filter((d) => d.governanceState === 'amber').length;
  const redCount = allDestinations.filter((d) => d.governanceState === 'red').length;
  const expiringAuth = allDestinations.filter((d) => d.authState !== 'connected').length;

  const drawer = drawerId ? allDestinations.find((d) => d.id === drawerId) ?? null : null;
  const drawerEvents = drawer ? RELAY_RUN_EVENTS.filter((e) => e.destinationId === drawer.id).slice(0, 12) : [];

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 03"
        title="Destinations"
        blurb="Every system the spine writes into — CRM, support, marketing, collab, data, webhook, finance, logistics. Each one has a contract, a rate envelope, an auth state, and a health score derived from the last 50 deliveries."
        trailing={
          <Link href="/innovation/destination-discovery" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
            <Search className="w-3.5 h-3.5" /> Auto-Discovery →
          </Link>
        }
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Destinations" value={allDestinations.length} tone="gold" sub={`${greenCount} green · ${amberCount} amber · ${redCount} red${discoveredDestinations.length > 0 ? ` · +${discoveredDestinations.length} discovered` : ''}`} />
        <FabricStat label="Auth attention" value={expiringAuth} tone={expiringAuth > 0 ? 'warn' : 'good'} sub="expiring / rotation / expired / untested" />
        <FabricStat label="Avg health" value={Math.round(RELAY_DESTINATIONS.reduce((s, d) => s + d.healthScore, 0) / RELAY_DESTINATIONS.length)} tone="good" />
        <FabricStat label="PII-permitted" value={RELAY_DESTINATIONS.filter((d) => d.piiAllowed).length} />
      </div>

      <FabricToolbar>
        <Input placeholder="Search destinations…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={cat} onChange={(e) => setCat(e.target.value)} className="max-w-xs">
          <option value="">All categories</option>
          {Array.from(new Set(RELAY_DESTINATIONS.map((d) => d.category))).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Select>
      </FabricToolbar>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {rows.map((d) => (
          <button key={d.id} onClick={() => setDrawerId(d.id)} className="conduit-card p-4 text-left" style={discoveredIds.has(d.id) ? { borderColor: 'rgba(201,183,135,0.25)' } : undefined}>
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: d.accent, boxShadow: `0 0 6px ${d.accent}55` }} />
                <div>
                  <div className="text-[#f5f5f5] text-sm font-medium flex items-center gap-1.5">{d.name}{discoveredIds.has(d.id) && <Badge variant="active">discovered</Badge>}</div>
                  <div className="text-[11px] text-[#666] mt-0.5">{d.category} · {d.rateLimitRpm} rpm</div>
                </div>
              </div>
              <GovernanceDot state={d.governanceState} />
            </div>
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-[#8a8a8a]"><span>health</span><span className="font-mono tabular-nums">{d.computedHealth}</span></div>
              <MicroBar value={d.computedHealth} max={100} tone={d.computedHealth >= 85 ? 'good' : d.computedHealth >= 70 ? 'warn' : 'bad'} />
              <div className="flex items-center justify-between text-[11px] text-[#8a8a8a]"><span>contract</span><span className="font-mono tabular-nums">{Math.round(d.fieldContractStrength * 100)}%</span></div>
              <MicroBar value={d.fieldContractStrength * 100} max={100} tone="gold" />
            </div>
            <div className="flex items-center gap-1 mt-3 flex-wrap">
              <Badge variant={d.authState === 'connected' ? 'success' : d.authState === 'expiring' ? 'partial' : 'failed'}>{d.authState.replace('_', ' ')}</Badge>
              {d.piiAllowed && <Badge variant="partial">PII OK</Badge>}
            </div>
          </button>
        ))}
      </div>

      <FabricDrawer
        open={!!drawer}
        onClose={() => setDrawerId(null)}
        title={drawer?.name ?? ''}
        subtitle={drawer ? `${drawer.category} · ${drawer.rateLimit}` : ''}
      >
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Health" value={calculateDestinationHealth(drawer, RELAY_RUN_EVENTS)} tone="good" />
              <FabricStat label="Rate envelope" value={`${drawer.rateLimitRpm} rpm`} />
              <FabricStat label="Contract strength" value={`${Math.round(drawer.fieldContractStrength * 100)}%`} tone="gold" />
              <FabricStat label="Observability" value={`${Math.round(drawer.observabilityCoverage * 100)}%`} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">AUTH</div>
              <div className="text-[12px] text-[#f5f5f5]">{drawer.authState.replace('_', ' ')}</div>
              {drawer.authRotatesAt && (
                <div className="text-[11px] text-[#8a8a8a] mt-1">Rotates {new Date(drawer.authRotatesAt).toLocaleDateString()}</div>
              )}
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">SUPPORTED OPERATIONS</div>
              <div className="flex gap-1 flex-wrap">
                {drawer.supportedOps.map((o) => <Badge key={o} variant="default">{o}</Badge>)}
              </div>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">RECENT EVENTS</div>
              <div className="space-y-1">
                {drawerEvents.length === 0 && <div className="text-[12px] text-[#666]">No recent activity</div>}
                {drawerEvents.map((e) => (
                  <div key={e.id} className="flex items-center justify-between text-[11px] py-1">
                    <div className="font-mono text-[#8a8a8a]">{e.type}</div>
                    <div className="text-[#666]">{new Date(e.atIso).toLocaleTimeString()}</div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
