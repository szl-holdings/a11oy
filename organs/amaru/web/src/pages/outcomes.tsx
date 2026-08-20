import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_OUTCOMES } from '@/data/fabric';
import { calculateOutcomeLift, calculatePredictionError } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { useInnovationStore } from '@/lib/innovation-store';
import { RotateCcw } from 'lucide-react';

export default function OutcomesPage() {
  const { closedLoopOutcomes } = useInnovationStore();
  const [q, setQ] = useState('');
  const [vertical, setVertical] = useState('');
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const allOutcomes = useMemo(() => [...closedLoopOutcomes, ...RELAY_OUTCOMES], [closedLoopOutcomes]);
  const closedLoopIds = useMemo(() => new Set(closedLoopOutcomes.map((o) => o.id)), [closedLoopOutcomes]);

  const rows = useMemo(() => {
    return allOutcomes.filter((o) => {
      if (q && !o.syncName.toLowerCase().includes(q.toLowerCase())) return false;
      if (vertical && o.verticalId !== vertical) return false;
      return true;
    });
  }, [q, vertical, allOutcomes]);

  const lift = calculateOutcomeLift(allOutcomes);
  const err = calculatePredictionError(allOutcomes);
  const policyCandidates = allOutcomes.filter((o) => o.policyUpdateCandidate).length;
  const drawer = drawerId ? allOutcomes.find((o) => o.id === drawerId) ?? null : null;

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 07"
        title="Outcomes"
        blurb="The closed loop. Forecaster predicts the destination KPI lift each sync should produce; the actual is observed; the prediction error feeds the cadence recommender. Lessons accumulate as policy update candidates."
        trailing={
          <Link href="/innovation/closed-loop" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
            <RotateCcw className="w-3.5 h-3.5" /> Closed-Loop Capture →
          </Link>
        }
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Outcomes observed" value={allOutcomes.length} tone="gold" sub={closedLoopOutcomes.length > 0 ? `+${closedLoopOutcomes.length} closed-loop` : undefined} />
        <FabricStat label="Avg lift" value={`${(lift * 100).toFixed(1)}%`} tone={lift >= 0.05 ? 'good' : 'warn'} />
        <FabricStat label="Avg prediction error" value={`±${(err * 100).toFixed(1)}%`} tone="neutral" />
        <FabricStat label="Policy candidates" value={policyCandidates} tone="warn" />
      </div>

      <FabricToolbar>
        <Input placeholder="Search outcomes…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={vertical} onChange={(e) => setVertical(e.target.value)} className="max-w-xs">
          <option value="">All verticals</option>
          {Array.from(new Set(RELAY_OUTCOMES.map((o) => o.verticalId))).map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </Select>
      </FabricToolbar>

      <div className="conduit-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#666] border-b border-[rgba(255,255,255,0.06)]">
            <tr>
              <th className="text-left px-4 py-3">Observed</th>
              <th className="text-left px-4 py-3">Sync</th>
              <th className="text-left px-4 py-3">Metric</th>
              <th className="text-right px-4 py-3">Predicted</th>
              <th className="text-right px-4 py-3">Actual</th>
              <th className="text-right px-4 py-3">Error</th>
              <th className="text-right px-4 py-3">Lift</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[#1a1a1a] cursor-pointer" onClick={() => setDrawerId(o.id)} style={closedLoopIds.has(o.id) ? { background: 'rgba(201,183,135,0.04)' } : undefined}>
                <td className="px-4 py-2 font-mono text-[11px] text-[#666]">{new Date(o.observedAtIso).toLocaleDateString()}</td>
                <td className="px-4 py-2 text-[12px] text-[#f5f5f5]">{closedLoopIds.has(o.id) && <RotateCcw className="w-3 h-3 inline mr-1.5 text-[#c9b787]" />}{o.syncName}</td>
                <td className="px-4 py-2 font-mono text-[11px] text-[#8a8a8a]">{o.predictedMetric}</td>
                <td className="px-4 py-2 text-right tabular-nums text-[12px] text-[#8a8a8a]">{o.predictedValue.toLocaleString()}</td>
                <td className="px-4 py-2 text-right tabular-nums text-[12px] text-[#f5f5f5]">{o.actualValue.toLocaleString()}</td>
                <td className={`px-4 py-2 text-right tabular-nums text-[12px] ${Math.abs(o.predictionError) > 0.1 ? 'text-[#d4a853]' : 'text-[#5a8a6e]'}`}>{(o.predictionError * 100).toFixed(1)}%</td>
                <td className={`px-4 py-2 text-right tabular-nums text-[12px] ${o.liftPct >= 0 ? 'text-[#5a8a6e]' : 'text-[#b85450]'}`}>{(o.liftPct * 100).toFixed(1)}%</td>
                <td className="px-4 py-2">{o.policyUpdateCandidate && <Badge variant="partial">policy</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FabricDrawer open={!!drawer} onClose={() => setDrawerId(null)} title={drawer?.syncName ?? ''} subtitle={drawer ? `${drawer.predictedMetric} · ${drawer.verticalId}` : ''}>
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Predicted" value={drawer.predictedValue.toLocaleString()} />
              <FabricStat label="Actual" value={drawer.actualValue.toLocaleString()} tone="gold" />
              <FabricStat label="Prediction error" value={`${(drawer.predictionError * 100).toFixed(1)}%`} tone={Math.abs(drawer.predictionError) > 0.1 ? 'warn' : 'good'} />
              <FabricStat label="Lift" value={`${(drawer.liftPct * 100).toFixed(1)}%`} tone={drawer.liftPct >= 0 ? 'good' : 'bad'} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">LESSON</div>
              <div className="text-[12px] text-[#f5f5f5]">{drawer.lessonLearned}</div>
              {drawer.policyUpdateCandidate && <div className="mt-2"><Badge variant="partial">policy update candidate</Badge></div>}
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">EVIDENCE REF</div>
              <div className="font-mono text-[11px] text-[#8a8a8a]">{drawer.evidenceRef}</div>
            </div>
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
