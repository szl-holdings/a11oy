// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { useState } from 'react';
import { Link } from 'wouter';
import { AMARU_AGENTS, RELAY_MAPPINGS, RELAY_MODELS, RELAY_DESTINATIONS, RELAY_POLICIES, RELAY_SOURCES } from '@/data/fabric';
import type { AmaruAgent } from '@/data/fabric/types';
import { runCoalition, parseDslRules } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricCard, FabricDrawer, MicroBar, SeverityChip } from '@/components/fabric/primitives';
import { Badge, Button, Select } from '@/components/ui';
import { useInnovationStore, applyMappingOverrides } from '@/lib/innovation-store';
import { Settings } from 'lucide-react';
import { AtelierEmbedFrame } from '@/components/AtelierEmbedFrame';

export default function AgentsPage() {
  const { mapperStats, dslVersions, mappingOverrides, goldenMerges } = useInnovationStore();
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [mappingId, setMappingId] = useState<string>(RELAY_MAPPINGS[0]?.id ?? '');
  const [seed, setSeed] = useState(42);
  const [run, setRun] = useState<ReturnType<typeof runCoalition> | null>(null);
  const activeDsl = dslVersions[0] ?? null;
  const activeDslRules = activeDsl ? parseDslRules(activeDsl.content) : [];

  const drawer = drawerId ? AMARU_AGENTS.find((a) => a.id === drawerId)! : null;

  const trigger = () => {
    const seedMapping = RELAY_MAPPINGS.find((mp) => mp.id === mappingId);
    if (!seedMapping) return;
    // Apply approved drift repairs to the mapping definition before handing
    // it to the coalition, so the run reflects the repaired field set,
    // transformations, and any governance promotion.
    const m = applyMappingOverrides(seedMapping, mappingOverrides);
    const model = RELAY_MODELS.find((mo) => mo.id === m.modelId);
    const dest = RELAY_DESTINATIONS.find((d) => d.id === m.destinationId);
    const src = model ? RELAY_SOURCES.find((s) => s.id === model.sourceId) : undefined;
    if (!model || !dest || !src) return;
    const goldenIdentity = goldenMerges[0]?.entityName;
    setRun(runCoalition({
      mapping: m, model, destination: dest, source: src,
      policies: RELAY_POLICIES, seed, nowIso: '2026-05-05T03:55:00Z',
      dslRules: activeDslRules,
      dslVersion: activeDsl?.version,
      goldenMergeCount: goldenMerges.length,
      goldenIdentity,
    }));
  };

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 08"
        title="Agents"
        blurb="The eight Amaru agents that compose the spine — Cartographer, Mapper, Courier, Sentinel, Verity, Forecaster, Fixer, Scribe. Modeled after A11oy's Fabric pattern but Amaru-native: data activation specialists, governed by the Codex Kernel."
        trailing={
          <div className="flex items-center gap-2">
            <span className="label-mono">replay</span>
            <Select value={mappingId} onChange={(e) => setMappingId(e.target.value)} className="w-72">
              {RELAY_MAPPINGS.slice(0, 24).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </Select>
            <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} className="w-16 h-9 rounded-md bg-transparent border border-input px-2 text-sm" />
            <Button size="sm" onClick={trigger}>Run coalition</Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <FabricStat label="Agents" value={AMARU_AGENTS.length} tone="gold" />
        <FabricStat label="Recent decisions" value={AMARU_AGENTS.reduce((s, a) => s + a.recentDecisionCount, 0).toLocaleString()} />
        <FabricStat label="Recent blocks" value={AMARU_AGENTS.reduce((s, a) => s + a.recentBlockCount, 0)} tone="warn" />
        <FabricStat label="Avg approval rate" value={`${Math.round((AMARU_AGENTS.reduce((s, a) => s + a.approvalRate, 0) / AMARU_AGENTS.length) * 100)}%`} tone="good" />
        <FabricStat
          label="Mapper accept rate"
          value={mapperStats ? `${Math.round((mapperStats.accepted / Math.max(1, mapperStats.totalDecided)) * 100)}%` : '—'}
          tone={mapperStats && mapperStats.accepted / Math.max(1, mapperStats.totalDecided) >= 0.8 ? 'good' : 'warn'}
          sub={mapperStats ? `${mapperStats.totalDecided} calibrated · θ=${mapperStats.threshold.toFixed(2)}` : 'no calibration data'}
        />
      </div>
      {mapperStats && (
        <div className="mb-6 p-3 rounded text-[12px] flex items-center justify-between" style={{ background: 'rgba(201,183,135,0.04)', border: '1px solid rgba(201,183,135,0.15)' }}>
          <div className="flex items-center gap-2">
            <Settings className="w-3.5 h-3.5 text-[#c9b787]" />
            <span className="text-[#f5f5f5]">Mapper calibration loop active</span>
            <span className="text-[#666] font-mono">{mapperStats.accepted} accepted · {mapperStats.rejected} rejected · θ={mapperStats.threshold.toFixed(2)}</span>
          </div>
          <Link href="/innovation/mapper-accuracy" className="text-[11px] text-[#c9b787] hover:underline">View calibration →</Link>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        {AMARU_AGENTS.map((a: AmaruAgent) => (
          <button key={a.id} onClick={() => setDrawerId(a.id)} className="conduit-card p-4 text-left">
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-[#f5f5f5] text-base font-medium">{a.name} <span className="text-[#666] text-[12px] font-mono">/ {a.mythosName}</span></div>
                <div className="text-[12px] text-[#8a8a8a] mt-1">{a.role}</div>
              </div>
              <Badge variant="active">Σ-axis {a.lutarAxisAffinity}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-[11px]">
              <div><div className="label-mono">decisions</div><div className="font-mono tabular-nums text-[#f5f5f5]">{a.recentDecisionCount}</div></div>
              <div><div className="label-mono">blocks</div><div className="font-mono tabular-nums text-[#d4a853]">{a.recentBlockCount}</div></div>
              <div><div className="label-mono">approval</div><div className="font-mono tabular-nums text-[#5a8a6e]">{Math.round(a.approvalRate * 100)}%</div></div>
            </div>
            <div className="mt-3"><MicroBar value={a.avgConfidence * 100} max={100} tone="gold" /></div>
          </button>
        ))}
      </div>

      {run && (
        <FabricCard title={`COALITION RUN · ${run.runId} · ${run.verdict.toUpperCase()}`} trailing={<span className="font-mono text-[12px] text-[#c9b787]">Σ {(run.sigma.sigma * 100).toFixed(1)}%</span>}>
          <div className="grid grid-cols-4 gap-2 text-[11px] mb-3">
            <div><div className="label-mono">P</div><div className="font-mono tabular-nums text-[#f5f5f5]">{(run.sigma.axes.P * 100).toFixed(0)}%</div></div>
            <div><div className="label-mono">K</div><div className="font-mono tabular-nums text-[#f5f5f5]">{(run.sigma.axes.K * 100).toFixed(0)}%</div></div>
            <div><div className="label-mono">Φ</div><div className="font-mono tabular-nums text-[#f5f5f5]">{(run.sigma.axes.phi * 100).toFixed(0)}%</div></div>
            <div><div className="label-mono">C</div><div className="font-mono tabular-nums text-[#f5f5f5]">{(run.sigma.axes.C * 100).toFixed(0)}%</div></div>
          </div>
          <div className="space-y-1.5">
            {run.events.map((e) => (
              <div key={e.id} className="flex items-center justify-between text-[12px] py-1.5 px-2 rounded bg-[#0e0e0e]">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <SeverityChip level={e.severity} />
                  <span className="font-mono text-[#c9b787] w-24">{e.type}</span>
                  <span className="text-[#f5f5f5] truncate">{e.summary}</span>
                </div>
                <span className="font-mono text-[10px] text-[#666] shrink-0 ml-2">{e.stateHash}</span>
              </div>
            ))}
          </div>
        </FabricCard>
      )}

      <FabricDrawer open={!!drawer} onClose={() => setDrawerId(null)} title={drawer?.name ?? ''} subtitle={drawer?.role}>
        {drawer && (
          <>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">RESPONSIBILITIES</div>
              <ul className="space-y-1 text-[12px] text-[#f5f5f5]">
                {drawer.responsibilities.map((r, i) => <li key={i}>· {r}</li>)}
              </ul>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-[#5a8a6e]">ALLOWED</div>
                <ul className="space-y-1 text-[11px] text-[#8a8a8a]">{drawer.allowedActions.map((a, i) => <li key={i}>· {a}</li>)}</ul>
              </div>
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-[#b85450]">BLOCKED</div>
                <ul className="space-y-1 text-[11px] text-[#8a8a8a]">{drawer.blockedActions.map((a, i) => <li key={i}>· {a}</li>)}</ul>
              </div>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">GOVERNANCE LIMITS</div>
              <ul className="space-y-1 text-[11px] text-[#d4a853]">
                {drawer.governanceLimits.map((g, i) => <li key={i}>· {g}</li>)}
              </ul>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">I/O CONTRACTS</div>
              <div className="text-[11px] space-y-1">
                <div><span className="text-[#666]">in:</span> <span className="font-mono text-[#8a8a8a]">{drawer.inputs.join(', ')}</span></div>
                <div><span className="text-[#666]">out:</span> <span className="font-mono text-[#8a8a8a]">{drawer.outputs.join(', ')}</span></div>
              </div>
            </div>
          </>
        )}
      </FabricDrawer>

      <div className="mt-8">
        <div className="label-mono mb-3 text-[#c9b787]">CROSS-SPACE COMPOSITION · A11OY ATELIER</div>
        <div className="text-[11px] text-[#8a8a8a] mb-3 max-w-[60ch] leading-relaxed">
          This Atelier Space runs inside Amaru under its own Constitution and emits proofs back to the public ledger. Telemetry from this embed feeds the governance-weighted leaderboard.
        </div>
        <AtelierEmbedFrame spaceSlug="cross-vertical-executive-brief" title="Cross-Vertical Executive Brief — composed" />
      </div>
    </div>
  );
}
