import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_DESTINATIONS } from '@/data/fabric';
import type { RelayDestination } from '@/data/fabric/types';
import { useInnovationStore } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, Search, CheckCircle, Zap, Database, ArrowRight } from 'lucide-react';

type AdapterKind = 'crm' | 'support' | 'marketing' | 'data' | 'collab' | 'webhook' | 'erp';
type ProbeStatus = 'idle' | 'probing' | 'done' | 'error';

interface DiscoveredDestination {
  readonly id: string;
  readonly name: string;
  readonly adapterKind: AdapterKind;
  readonly probeAtMs: number;
  readonly schemaFieldsFound: number;
  readonly opsFound: string[];
  readonly rpmCap: number;
  readonly authMechanism: string;
  readonly piiAllowed: boolean;
  readonly contractStrength: number;
  readonly obsCoverage: number;
  readonly synthesized: RelayDestination;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}
function hex8(n: number) { return n.toString(16).padStart(8, '0').slice(0, 8); }

const ADAPTER_ACCENTS: Record<AdapterKind, string> = {
  crm: '#3b82f6', support: '#10b981', marketing: '#f97316', data: '#06b6d4', collab: '#a855f7', webhook: '#6366f1', erp: '#f59e0b',
};

const TEMPLATES: Record<AdapterKind, { ops: string[]; rpm: number; pii: boolean; entities: string[] }> = {
  crm: { ops: ['upsert', 'update'], rpm: 480, pii: true, entities: ['contact', 'account', 'opportunity'] },
  support: { ops: ['upsert', 'update', 'event'], rpm: 360, pii: true, entities: ['ticket', 'contact'] },
  marketing: { ops: ['upsert', 'delete'], rpm: 600, pii: true, entities: ['contact'] },
  data: { ops: ['mirror'], rpm: 4000, pii: true, entities: ['account', 'event', 'kpi_snapshot'] },
  collab: { ops: ['event', 'upsert'], rpm: 600, pii: false, entities: ['document', 'event'] },
  webhook: { ops: ['event'], rpm: 1200, pii: false, entities: ['event'] },
  erp: { ops: ['upsert', 'mirror'], rpm: 120, pii: true, entities: ['account', 'invoice'] },
};

function synthesizeDestination(adapterName: string, kind: AdapterKind): RelayDestination {
  const seed = fnv1a(`${adapterName}:${kind}`);
  const tmpl = TEMPLATES[kind];
  const id = `dst-disc-${hex8(seed)}`;
  const contractStrength = 0.78 + (seed % 18) / 100;
  const obsCoverage = 0.72 + (seed % 22) / 100;
  const healthScore = Math.round(85 + (seed % 12));
  return {
    id,
    name: adapterName,
    category: kind as RelayDestination['category'],
    accent: ADAPTER_ACCENTS[kind],
    supportedOps: tmpl.ops as RelayDestination['supportedOps'],
    supportedEntityTypes: tmpl.entities as RelayDestination['supportedEntityTypes'],
    rateLimit: tmpl.rpm >= 1000 ? 'lenient' : tmpl.rpm >= 400 ? 'moderate' : tmpl.rpm >= 200 ? 'strict' : 'tight',
    rateLimitRpm: tmpl.rpm,
    authState: 'connected',
    authRotatesAt: null,
    piiAllowed: tmpl.pii,
    fieldContractStrength: Math.round(contractStrength * 100) / 100,
    observabilityCoverage: Math.round(obsCoverage * 100) / 100,
    healthScore,
    governanceState: 'green',
    anchorHash: `0x${hex8(seed)}`,
  };
}

export default function DestinationDiscoveryPage() {
  const { discoveredDestinations, addDiscoveredDestination } = useInnovationStore();
  const [adapterName, setAdapterName] = useState('');
  const [adapterKind, setAdapterKind] = useState<AdapterKind>('crm');
  const [probeStatus, setProbeStatus] = useState<ProbeStatus>('idle');
  const [probeLog, setProbeLog] = useState<string[]>([]);
  const [discovered, setDiscovered] = useState<DiscoveredDestination[]>([]);
  const registeredIds = useMemo(() => new Set(discoveredDestinations.map((d) => d.id)), [discoveredDestinations]);

  const runProbe = () => {
    if (!adapterName.trim()) return;
    const name = adapterName.trim();
    setProbeStatus('probing');
    setProbeLog([]);

    const tmpl = TEMPLATES[adapterKind];
    const steps = [
      `→ Connecting to adapter endpoint (${adapterKind.toUpperCase()})...`,
      `→ Negotiating auth protocol (OAuth2 / Bearer)...`,
      `→ Fetching schema catalog from /schema endpoint...`,
      `→ Found ${tmpl.entities.length} entity types: [${tmpl.entities.join(', ')}]`,
      `→ Probing supported operations: [${tmpl.ops.join(', ')}]`,
      `→ Rate limit detection: ${tmpl.rpm} rpm cap`,
      `→ PII contract probe: ${tmpl.pii ? 'PII allowed with redaction contract' : 'PII not permitted'}`,
      `→ Field-contract scoring... ${Math.round((0.78 + fnv1a(name) % 18 / 100) * 100)}%`,
      `→ Observability coverage probe... ${Math.round((0.72 + fnv1a(name + 'obs') % 22 / 100) * 100)}%`,
      `→ Synthesis complete — RelayDestination record synthesized`,
    ];

    let i = 0;
    const interval = setInterval(() => {
      if (i < steps.length) {
        setProbeLog((prev) => [...prev, steps[i]!]);
        i++;
      } else {
        clearInterval(interval);
        const seed = fnv1a(`${name}:${adapterKind}`);
        const synthDest = synthesizeDestination(name, adapterKind);
        const disc: DiscoveredDestination = {
          id: synthDest.id,
          name,
          adapterKind,
          probeAtMs: 380 + (seed % 240),
          schemaFieldsFound: 12 + (seed % 24),
          opsFound: tmpl.ops,
          rpmCap: tmpl.rpm,
          authMechanism: 'OAuth2 / Bearer',
          piiAllowed: tmpl.pii,
          contractStrength: synthDest.fieldContractStrength,
          obsCoverage: synthDest.observabilityCoverage,
          synthesized: synthDest,
        };
        setDiscovered((prev) => [disc, ...prev]);
        setProbeStatus('done');
        setAdapterName('');
      }
    }, 200);
  };

  const registerDestination = (disc: DiscoveredDestination) => {
    addDiscoveredDestination({
      ...disc.synthesized,
      discoveredAt: '2026-05-05T03:55:00Z',
      probeAtMs: disc.probeAtMs,
    });
  };

  const allDestinations = [
    ...discovered.filter((d) => registeredIds.has(d.id)).map((d) => d.synthesized),
    ...RELAY_DESTINATIONS.slice(0, 8),
  ];

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 09"
        title="Destination Contract Auto-Discovery"
        blurb="Register a new destination adapter and Cartographer probes its schema, supported operations, rate-limit semantics, and PII contract. A full RelayDestination record is synthesized automatically — no manual registration."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Destinations registered" value={RELAY_DESTINATIONS.length} tone="gold" />
        <FabricStat label="Probed this session" value={discovered.length} />
        <FabricStat label="Synthesized + registered" value={registeredIds.size} tone="good" />
        <FabricStat label="Probe time (avg)" value={discovered.length > 0 ? `${Math.round(discovered.reduce((s, d) => s + d.probeAtMs, 0) / discovered.length)}ms` : '—'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <FabricCard title="ADAPTER REGISTRATION">
          <div className="space-y-4">
            <div>
              <div className="label-mono mb-2">ADAPTER NAME</div>
              <input
                value={adapterName}
                onChange={(e) => { setAdapterName(e.target.value); setProbeStatus('idle'); setProbeLog([]); }}
                placeholder="e.g. Nexus CRM, Atlas Support…"
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm"
              />
            </div>

            <div>
              <div className="label-mono mb-2">ADAPTER KIND</div>
              <div className="grid grid-cols-4 gap-1.5">
                {(Object.keys(TEMPLATES) as AdapterKind[]).map((kind) => (
                  <button
                    key={kind}
                    onClick={() => setAdapterKind(kind)}
                    className="px-2 py-1.5 rounded-lg text-[11px] font-mono border transition-all"
                    style={{ borderColor: adapterKind === kind ? ADAPTER_ACCENTS[kind] : 'rgba(255,255,255,0.08)', color: adapterKind === kind ? ADAPTER_ACCENTS[kind] : '#666', background: adapterKind === kind ? `${ADAPTER_ACCENTS[kind]}10` : 'transparent' }}
                  >
                    {kind}
                  </button>
                ))}
              </div>
            </div>

            <Button onClick={runProbe} isLoading={probeStatus === 'probing'} disabled={!adapterName.trim()} className="w-full">
              <Search className="w-4 h-4 mr-2" /> Probe Adapter
            </Button>

            {probeLog.length > 0 && (
              <div className="rounded-lg p-3 font-mono text-[11px] space-y-1 max-h-48 overflow-y-auto" style={{ background: '#080808', border: '1px solid rgba(255,255,255,0.04)' }}>
                {probeLog.map((line, i) => (
                  <div key={i} className={i === probeLog.length - 1 && probeStatus === 'done' ? 'text-[#5a8a6e]' : probeStatus === 'probing' && i === probeLog.length - 1 ? 'text-[#c9b787]' : 'text-[#555]'}>
                    {line}
                  </div>
                ))}
                {probeStatus === 'probing' && <div className="text-[#c9b787] animate-pulse">_</div>}
              </div>
            )}
          </div>
        </FabricCard>

        <div className="space-y-4">
          {discovered.map((disc) => {
            const isRegistered = registeredIds.has(disc.id);
            return (
              <FabricCard key={disc.id} title={`SYNTHESIZED — ${disc.name.toUpperCase()}`} className="animate-scale-in">
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <FabricStat label="Schema fields" value={disc.schemaFieldsFound} tone="gold" />
                  <FabricStat label="Probe time" value={`${disc.probeAtMs}ms`} />
                  <FabricStat label="Contract strength" value={`${Math.round(disc.contractStrength * 100)}%`} tone="good" />
                  <FabricStat label="Observability" value={`${Math.round(disc.obsCoverage * 100)}%`} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] mb-3">
                  <div>
                    <div className="label-mono">OPS</div>
                    <div className="flex gap-1 flex-wrap mt-1">{disc.opsFound.map((op) => <Badge key={op} variant="default">{op}</Badge>)}</div>
                  </div>
                  <div>
                    <div className="label-mono">RATE LIMIT</div>
                    <div className="font-mono text-[#f5f5f5] mt-1">{disc.rpmCap} rpm</div>
                  </div>
                  <div>
                    <div className="label-mono">AUTH</div>
                    <div className="font-mono text-[#f5f5f5] mt-1">{disc.authMechanism}</div>
                  </div>
                  <div>
                    <div className="label-mono">PII CONTRACT</div>
                    <div className={`mt-1 ${disc.piiAllowed ? 'text-[#d4a853]' : 'text-[#5a8a6e]'}`}>{disc.piiAllowed ? 'PII allowed (redaction)' : 'No PII'}</div>
                  </div>
                </div>
                <div className="font-mono text-[10px] text-[#555] mb-3">ID: {disc.synthesized.id} · anchor: {disc.synthesized.anchorHash}</div>
                {isRegistered ? (
                  <div className="flex items-center gap-2 text-[12px] text-[#5a8a6e]">
                    <CheckCircle className="w-4 h-4" /> Registered in destination catalog
                  </div>
                ) : (
                  <Button onClick={() => registerDestination(disc)} className="w-full">
                    <Zap className="w-4 h-4 mr-1.5" /> Register Destination
                  </Button>
                )}
              </FabricCard>
            );
          })}

          {discovered.length === 0 && (
            <div className="conduit-card p-6 text-center">
              <Database className="w-8 h-8 mx-auto mb-3 text-[#333]" />
              <div className="text-sm text-[#555]">No adapters probed yet. Enter a name and probe above.</div>
            </div>
          )}
        </div>
      </div>

      <FabricCard title="DESTINATION CATALOG (LIVE)">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {allDestinations.map((d) => {
            const isNew = registeredIds.has(d.id);
            return (
              <div key={d.id} className="flex items-center gap-3 p-2 rounded text-[12px]" style={{ background: isNew ? 'rgba(201,183,135,0.04)' : '#0e0e0e', border: `1px solid ${isNew ? 'rgba(201,183,135,0.15)' : 'rgba(255,255,255,0.04)'}` }}>
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: d.accent }} />
                <div className="flex-1 min-w-0">
                  <div className="text-[#f5f5f5] truncate">{d.name}</div>
                  <div className="text-[10px] text-[#666]">{d.category} · {d.rateLimitRpm} rpm</div>
                </div>
                <GovernanceDot state={d.governanceState} />
                {isNew && <Badge variant="active">new</Badge>}
              </div>
            );
          })}
        </div>
        <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)] flex items-center justify-between">
          <span className="text-[11px] text-[#666]">{RELAY_DESTINATIONS.length + registeredIds.size} total destinations</span>
          <Link href="/destinations" className="text-[11px] text-[#c9b787] hover:underline flex items-center gap-1">View Destinations surface <ArrowRight className="w-3 h-3" /></Link>
        </div>
      </FabricCard>
    </div>
  );
}
