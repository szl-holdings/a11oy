import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { RELAY_MAPPINGS, RELAY_MODELS, RELAY_DESTINATIONS, RELAY_SOURCES, RELAY_POLICIES } from '@/data/fabric';
import type { RelayPolicy } from '@/data/fabric/types';
import { FabricHeader, FabricCard, FabricStat, MicroBar, SeverityChip } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, Zap, DollarSign, Leaf, AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react';

interface CostEstimate {
  readonly mappingId: string;
  readonly mappingName: string;
  readonly destinationName: string;
  readonly apiCallsEstimated: number;
  readonly rateLimitRpm: number;
  readonly rateLimitHeadroom: number;
  readonly estimatedCostUsd: number;
  readonly energyWh: number;
  readonly carbonGramsCo2e: number;
  readonly budgetGateStatus: 'pass' | 'warn' | 'block';
  readonly budgetGateReason: string | null;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}

function computeEstimate(mappingId: string): CostEstimate {
  const mapping = RELAY_MAPPINGS.find((m) => m.id === mappingId)!;
  const model = RELAY_MODELS.find((mo) => mo.id === mapping.modelId);
  const dest = RELAY_DESTINATIONS.find((d) => d.id === mapping.destinationId);
  const source = model ? RELAY_SOURCES.find((s) => s.id === model.sourceId) : null;

  const baseRecords = source ? Math.round(source.rowCount * 0.0006) : 25000;
  const batchSize = 200;
  const apiCalls = Math.ceil(baseRecords / batchSize);
  const rpm = dest?.rateLimitRpm ?? 300;
  const headroom = Math.max(0, Math.min(100, Math.round(100 - (apiCalls / (rpm * 10)) * 100)));

  const seed = fnv1a(`cost:${mappingId}`);
  const costPerKRecord = 0.02 + (seed % 100) / 5000;
  const estimatedCostUsd = Math.round(baseRecords / 1000 * costPerKRecord * 100) / 100;

  const energyWhPerKRecord = 0.8 + (seed % 50) / 1000;
  const energyWh = Math.round(baseRecords / 1000 * energyWhPerKRecord * 10) / 10;
  const carbonIntensity = 0.233;
  const carbonGramsCo2e = Math.round(energyWh / 1000 * carbonIntensity * 1e6 * 10) / 10;

  const budgetGateStatus: 'pass' | 'warn' | 'block' =
    estimatedCostUsd > 50 ? 'block' :
    estimatedCostUsd > 20 || headroom < 20 ? 'warn' :
    'pass';
  const budgetGateReason = budgetGateStatus === 'block'
    ? `Estimated cost $${estimatedCostUsd.toFixed(2)} exceeds budget gate of $50.00`
    : budgetGateStatus === 'warn'
      ? `Cost $${estimatedCostUsd.toFixed(2)} or rate headroom ${headroom}% approaching limits`
      : null;

  return {
    mappingId,
    mappingName: mapping.name,
    destinationName: dest?.name ?? 'Unknown',
    apiCallsEstimated: apiCalls,
    rateLimitRpm: rpm,
    rateLimitHeadroom: headroom,
    estimatedCostUsd,
    energyWh,
    carbonGramsCo2e,
    budgetGateStatus,
    budgetGateReason,
  };
}

const BUDGET_POLICIES: readonly RelayPolicy[] = RELAY_POLICIES.filter((p) => p.kind === 'rate_limit' || p.kind === 'approval_gate').slice(0, 3);

export default function CostCarbonPage() {
  const [selectedMappingIds, setSelectedMappingIds] = useState<string[]>([RELAY_MAPPINGS[0]?.id ?? '']);
  const [estimates, setEstimates] = useState<CostEstimate[]>([]);
  const [loading, setLoading] = useState(false);

  const toggleMapping = (id: string) => {
    setSelectedMappingIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
    setEstimates([]);
  };

  const runEstimates = () => {
    if (!selectedMappingIds.length) return;
    setLoading(true);
    setTimeout(() => {
      setEstimates(selectedMappingIds.map(computeEstimate));
      setLoading(false);
    }, 700);
  };

  const totals = useMemo(() => ({
    apiCalls: estimates.reduce((s, e) => s + e.apiCallsEstimated, 0),
    costUsd: estimates.reduce((s, e) => s + e.estimatedCostUsd, 0),
    energyWh: estimates.reduce((s, e) => s + e.energyWh, 0),
    carbon: estimates.reduce((s, e) => s + e.carbonGramsCo2e, 0),
    blocked: estimates.filter((e) => e.budgetGateStatus === 'block').length,
  }), [estimates]);

  const SPARKLINE_DATA = [3.2, 4.1, 3.8, 5.2, 4.7, 6.1, 5.8, 7.2, 6.4, 5.9, 8.1, estimates.reduce((s, e) => s + e.estimatedCostUsd, 0)];

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 05"
        title="Sync Cost & Carbon Predictor"
        blurb="Before any sync runs, Forecaster estimates API call volume, rate-limit headroom, dollar cost, and energy/carbon footprint. Budget-gate policies block or warn based on these estimates."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {estimates.length > 0 ? (
          <>
            <FabricStat label="Total API calls" value={totals.apiCalls.toLocaleString()} tone="gold" />
            <FabricStat label="Est. cost" value={`$${totals.costUsd.toFixed(2)}`} tone={totals.blocked > 0 ? 'bad' : totals.costUsd > 20 ? 'warn' : 'good'} />
            <FabricStat label="Energy" value={`${totals.energyWh.toFixed(1)} Wh`} tone="neutral" />
            <FabricStat label="Carbon" value={`${totals.carbon.toFixed(1)} g CO₂e`} tone="good" />
          </>
        ) : (
          <>
            <FabricStat label="Mappings available" value={RELAY_MAPPINGS.length} tone="gold" />
            <FabricStat label="Selected" value={selectedMappingIds.length} />
            <FabricStat label="Budget policies" value={BUDGET_POLICIES.length} tone="warn" />
            <FabricStat label="Ready to estimate" value={selectedMappingIds.length > 0 ? 'Yes' : 'No'} tone={selectedMappingIds.length > 0 ? 'good' : 'neutral'} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <FabricCard title="SELECT SYNCS TO ESTIMATE">
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {RELAY_MAPPINGS.slice(0, 18).map((m) => {
              const dest = RELAY_DESTINATIONS.find((d) => d.id === m.destinationId);
              const isSelected = selectedMappingIds.includes(m.id);
              return (
                <button
                  key={m.id}
                  onClick={() => toggleMapping(m.id)}
                  className="flex items-center gap-3 w-full text-left px-3 py-2 rounded border transition-all text-[11px]"
                  style={{ borderColor: isSelected ? '#c9b787' : 'rgba(255,255,255,0.06)', background: isSelected ? 'rgba(201,183,135,0.05)' : 'transparent' }}
                >
                  <span className={`w-3 h-3 rounded border shrink-0 ${isSelected ? 'border-[#c9b787] bg-[#c9b787]' : 'border-[rgba(255,255,255,0.2)]'}`} />
                  <span className="font-mono text-[#f5f5f5] flex-1 truncate">{m.name}</span>
                  {dest && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dest.accent }} />}
                  <span className="text-[#666] shrink-0">{dest?.category ?? '—'}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)] flex justify-between items-center">
            <span className="text-[11px] text-[#666]">{selectedMappingIds.length} selected</span>
            <Button size="sm" onClick={runEstimates} isLoading={loading} disabled={!selectedMappingIds.length}>
              <TrendingUp className="w-3.5 h-3.5 mr-1.5" /> Run Forecaster
            </Button>
          </div>
        </FabricCard>

        <FabricCard title="BUDGET-GATE POLICIES">
          <div className="space-y-2 mb-4">
            {BUDGET_POLICIES.map((p) => (
              <div key={p.id} className="flex items-start gap-2 p-2 rounded bg-[#0e0e0e] text-[11px]">
                <SeverityChip level={p.severity} />
                <div>
                  <div className="text-[#f5f5f5]">{p.name}</div>
                  <div className="font-mono text-[#666] text-[10px]">{p.condition}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <div className="label-mono mb-2">COST TREND (last 12 runs · $)</div>
            <div className="flex items-end gap-1 h-16">
              {SPARKLINE_DATA.map((v, i) => {
                const max = Math.max(...SPARKLINE_DATA, 1);
                const pct = v / max;
                return (
                  <div key={i} className="flex-1 rounded-t transition-all" style={{ height: `${pct * 100}%`, background: i === SPARKLINE_DATA.length - 1 ? '#c9b787' : 'rgba(201,183,135,0.3)' }} title={`$${v.toFixed(2)}`} />
                );
              })}
            </div>
            <div className="flex justify-between text-[10px] text-[#555] font-mono mt-1">
              <span>-12 runs</span><span>now</span>
            </div>
          </div>
        </FabricCard>
      </div>

      {estimates.length > 0 && (
        <FabricCard title={`FORECAST RESULTS — ${estimates.length} SYNC${estimates.length !== 1 ? 'S' : ''}`} className="mb-6 animate-scale-in">
          {totals.blocked > 0 && (
            <div className="mb-4 p-3 rounded flex items-center gap-2 text-[12px]" style={{ background: 'rgba(184,84,80,0.08)', border: '1px solid rgba(184,84,80,0.2)' }}>
              <AlertTriangle className="w-4 h-4 text-[#b85450] shrink-0" />
              <span className="text-[#b85450]">{totals.blocked} sync{totals.blocked !== 1 ? 's' : ''} blocked by budget-gate policy</span>
            </div>
          )}
          <div className="space-y-3">
            {estimates.map((est) => (
              <div key={est.mappingId} className="p-4 rounded-lg" style={{ background: '#0e0e0e', border: '1px solid rgba(255,255,255,0.04)' }}>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-[#f5f5f5] text-sm font-medium">{est.mappingName}</div>
                    <div className="text-[11px] text-[#666]">→ {est.destinationName}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {est.budgetGateStatus === 'pass' ? <CheckCircle className="w-4 h-4 text-[#5a8a6e]" /> : est.budgetGateStatus === 'warn' ? <AlertTriangle className="w-4 h-4 text-[#d4a853]" /> : <AlertTriangle className="w-4 h-4 text-[#b85450]" />}
                    <Badge variant={est.budgetGateStatus === 'pass' ? 'success' : est.budgetGateStatus === 'warn' ? 'partial' : 'failed'}>{est.budgetGateStatus}</Badge>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  <div className="text-center p-2 rounded" style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <Zap className="w-3.5 h-3.5 text-[#c9b787] mx-auto mb-1" />
                    <div className="font-mono text-[#f5f5f5] text-sm">{est.apiCallsEstimated.toLocaleString()}</div>
                    <div className="label-mono mt-0.5">API calls</div>
                  </div>
                  <div className="text-center p-2 rounded" style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <DollarSign className="w-3.5 h-3.5 text-[#5a8a6e] mx-auto mb-1" />
                    <div className={`font-mono text-sm ${est.budgetGateStatus === 'block' ? 'text-[#b85450]' : est.budgetGateStatus === 'warn' ? 'text-[#d4a853]' : 'text-[#5a8a6e]'}`}>${est.estimatedCostUsd.toFixed(2)}</div>
                    <div className="label-mono mt-0.5">Est. cost</div>
                  </div>
                  <div className="text-center p-2 rounded" style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <Zap className="w-3.5 h-3.5 text-[#78aac8] mx-auto mb-1" />
                    <div className="font-mono text-[#f5f5f5] text-sm">{est.energyWh.toFixed(1)}</div>
                    <div className="label-mono mt-0.5">Wh energy</div>
                  </div>
                  <div className="text-center p-2 rounded" style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <Leaf className="w-3.5 h-3.5 text-[#5a8a6e] mx-auto mb-1" />
                    <div className="font-mono text-[#5a8a6e] text-sm">{est.carbonGramsCo2e.toFixed(1)}g</div>
                    <div className="label-mono mt-0.5">CO₂e</div>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-[#666]">
                    <span>Rate-limit headroom</span>
                    <span className="font-mono">{est.rateLimitHeadroom}% of {est.rateLimitRpm} rpm</span>
                  </div>
                  <MicroBar value={est.rateLimitHeadroom} max={100} tone={est.rateLimitHeadroom >= 40 ? 'good' : est.rateLimitHeadroom >= 20 ? 'warn' : 'bad'} />
                </div>

                {est.budgetGateReason && (
                  <div className="mt-2 text-[11px] text-[#d4a853]">· {est.budgetGateReason}</div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.04)] grid grid-cols-4 gap-3 text-center">
            <div><div className="label-mono">Total API</div><div className="font-mono text-[#c9b787]">{totals.apiCalls.toLocaleString()}</div></div>
            <div><div className="label-mono">Total cost</div><div className="font-mono text-[#c9b787]">${totals.costUsd.toFixed(2)}</div></div>
            <div><div className="label-mono">Total energy</div><div className="font-mono text-[#78aac8]">{totals.energyWh.toFixed(1)} Wh</div></div>
            <div><div className="label-mono">Total CO₂e</div><div className="font-mono text-[#5a8a6e]">{totals.carbon.toFixed(1)} g</div></div>
          </div>
        </FabricCard>
      )}

      <div className="p-3 rounded-lg text-[11px] text-[#555]" style={{ border: '1px solid rgba(255,255,255,0.04)' }}>
        Cost model: $0.02–$0.04 per 1k records · Energy: 0.8 Wh/1k records · Carbon: UK grid intensity 233 gCO₂e/kWh. All estimates are Forecaster-modeled; actual costs depend on destination API pricing. Budget gates are enforced by Sentinel policy evaluation.
      </div>
    </div>
  );
}
