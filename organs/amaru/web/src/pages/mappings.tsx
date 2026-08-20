import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_MAPPINGS, RELAY_MODELS, RELAY_DESTINATIONS, RELAY_SOURCES, RELAY_POLICIES } from '@/data/fabric';
import { scoreMappingCompatibility, deriveApprovalRequirement, buildDryRunSummary, classifyPiiRisk } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, GovernanceDot, MicroBar, SeverityChip } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { ScanLine, GitBranch as DriftIcon } from 'lucide-react';
import { useInnovationStore, applyMappingOverrides } from '@/lib/innovation-store';

export default function MappingsPage() {
  const { driftDecisions, mappingOverrides } = useInnovationStore();
  const [q, setQ] = useState('');
  const [vertical, setVertical] = useState('');
  const [needsApproval, setNeedsApproval] = useState(false);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const driftByMappingId = useMemo(() => {
    const map = new Map<string, typeof driftDecisions[number][]>();
    for (const d of driftDecisions) {
      for (const mid of d.mappingIds) {
        const arr = map.get(mid) ?? [];
        arr.push(d);
        map.set(mid, arr);
      }
    }
    return map;
  }, [driftDecisions]);
  const approvedDriftCount = driftDecisions.filter((d) => d.status === 'approved').length;

  const effectiveMappings = useMemo(
    () => RELAY_MAPPINGS.map((m) => applyMappingOverrides(m, mappingOverrides)),
    [mappingOverrides],
  );

  const rows = useMemo(() => {
    return effectiveMappings
      .filter((m) => {
        if (q && !m.name.toLowerCase().includes(q.toLowerCase())) return false;
        if (vertical && m.verticalId !== vertical) return false;
        if (needsApproval && !m.approvalRequired) return false;
        return true;
      })
      .sort((a, b) => scoreMappingCompatibility(b) - scoreMappingCompatibility(a));
  }, [effectiveMappings, q, vertical, needsApproval]);

  const drawer = drawerId ? effectiveMappings.find((m) => m.id === drawerId) ?? null : null;
  const drawerModel = drawer ? RELAY_MODELS.find((mo) => mo.id === drawer.modelId) ?? null : null;
  const drawerDest = drawer ? RELAY_DESTINATIONS.find((d) => d.id === drawer.destinationId) ?? null : null;
  const drawerSource = drawerModel ? RELAY_SOURCES.find((s) => s.id === drawerModel.sourceId) ?? null : null;
  const dryRun = drawer && drawerModel && drawerSource ? buildDryRunSummary(drawer, drawerSource, RELAY_POLICIES) : null;
  const risk = drawer && drawerModel && drawerDest ? classifyPiiRisk(drawerModel, drawerDest) : null;
  const appr = drawer && drawerDest ? deriveApprovalRequirement(drawer, drawerDest) : null;

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 04"
        title="Mappings"
        blurb="The Mapper agent's proposals: model fields fanned into destination fields, with explicit transforms, confidence, PII handling, and a recommended approval level. Nothing ships without a witness."
        trailing={
          <div className="flex gap-3">
            <Link href="/innovation/lineage" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
              <ScanLine className="w-3.5 h-3.5" /> Lineage →
            </Link>
            <Link href="/innovation/drift-repair" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
              <DriftIcon className="w-3.5 h-3.5" /> Drift Repair →
            </Link>
          </div>
        }
      />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <FabricStat label="Mappings" value={RELAY_MAPPINGS.length} tone="gold" />
        <FabricStat label="Awaiting approval" value={RELAY_MAPPINGS.filter((m) => m.approvalRequired).length} tone="warn" />
        <FabricStat label="Avg compatibility" value={Math.round(RELAY_MAPPINGS.reduce((s, m) => s + m.compatibilityScore, 0) / RELAY_MAPPINGS.length)} tone="good" />
        <FabricStat label="PII transforms" value={RELAY_MAPPINGS.filter((m) => m.piiWarnings.length > 0).length} />
        <FabricStat label="Drift repairs" value={approvedDriftCount} tone={approvedDriftCount > 0 ? 'good' : 'neutral'} sub={driftDecisions.length > 0 ? `${driftDecisions.length} decisions` : undefined} />
      </div>

      <FabricToolbar>
        <Input placeholder="Search mappings…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={vertical} onChange={(e) => setVertical(e.target.value)} className="max-w-xs">
          <option value="">All verticals</option>
          {Array.from(new Set(RELAY_MAPPINGS.map((m) => m.verticalId))).map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-[12px] text-[#8a8a8a] px-2">
          <input type="checkbox" checked={needsApproval} onChange={(e) => setNeedsApproval(e.target.checked)} className="accent-[#c9b787]" />
          needs approval only
        </label>
      </FabricToolbar>

      <div className="conduit-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#666] border-b border-[rgba(255,255,255,0.06)]">
            <tr>
              <th className="text-left px-4 py-3">Mapping</th>
              <th className="text-left px-4 py-3">Vertical</th>
              <th className="text-left px-4 py-3">Compat</th>
              <th className="text-right px-4 py-3">Confidence</th>
              <th className="text-right px-4 py-3">Fields</th>
              <th className="text-left px-4 py-3">Proposed</th>
              <th className="text-left px-4 py-3">State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[#1a1a1a] cursor-pointer transition-colors" onClick={() => setDrawerId(m.id)}>
                <td className="px-4 py-3">
                  <div className="font-mono text-[#f5f5f5] text-[12px] flex items-center gap-1.5">
                    {m.name}
                    {(() => {
                      const decisions = driftByMappingId.get(m.id) ?? [];
                      const approved = decisions.filter((d) => d.status === 'approved').length;
                      if (approved > 0) return <Badge variant="success">{approved} drift fix{approved !== 1 ? 'es' : ''}</Badge>;
                      if (decisions.length > 0) return <Badge variant="partial">drift</Badge>;
                      return null;
                    })()}
                  </div>
                  {m.approvalRequired && <div className="text-[10px] text-[#d4a853] mt-0.5">approval: {m.approvalReason}</div>}
                </td>
                <td className="px-4 py-3"><Badge variant="default">{m.verticalId}</Badge></td>
                <td className="px-4 py-3 w-32"><MicroBar value={m.compatibilityScore} max={100} tone={m.compatibilityScore >= 80 ? 'good' : 'warn'} /></td>
                <td className="px-4 py-3 text-right tabular-nums text-[#c9b787]">{(m.confidence * 100).toFixed(0)}%</td>
                <td className="px-4 py-3 text-right tabular-nums text-[#8a8a8a]">{m.mappedFieldCount}</td>
                <td className="px-4 py-3 text-[11px] text-[#8a8a8a]">{m.proposedBy.replace(/-/g, ' ')}</td>
                <td className="px-4 py-3"><GovernanceDot state={m.governanceState} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FabricDrawer
        open={!!drawer}
        onClose={() => setDrawerId(null)}
        title={drawer?.name ?? ''}
        subtitle={drawer ? `compat ${drawer.compatibilityScore} · conf ${(drawer.confidence * 100).toFixed(0)}%` : ''}
      >
        {drawer && drawerModel && drawerDest && dryRun && risk && appr && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Compatibility" value={drawer.compatibilityScore} tone="gold" />
              <FabricStat label="Confidence" value={`${(drawer.confidence * 100).toFixed(0)}%`} tone="good" />
              <FabricStat label="PII tier" value={risk.tier.toUpperCase()} tone={risk.tier === 'critical' ? 'bad' : risk.tier === 'high' ? 'warn' : 'neutral'} />
              <FabricStat label="Approval level" value={appr.level.toUpperCase()} tone={appr.level === 'partner' ? 'warn' : 'neutral'} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">DRY RUN</div>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <div className="flex justify-between"><span className="text-[#8a8a8a]">extracted</span><span className="font-mono tabular-nums text-[#f5f5f5]">{dryRun.recordsExtracted.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-[#8a8a8a]">filtered</span><span className="font-mono tabular-nums text-[#f5f5f5]">{dryRun.recordsFiltered.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-[#8a8a8a]">redacted</span><span className="font-mono tabular-nums text-[#d4a853]">{dryRun.recordsRedacted.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-[#8a8a8a]">to deliver</span><span className="font-mono tabular-nums text-[#5a8a6e]">{dryRun.recordsToDeliver.toLocaleString()}</span></div>
                <div className="flex justify-between col-span-2"><span className="text-[#8a8a8a]">est latency</span><span className="font-mono tabular-nums text-[#f5f5f5]">{dryRun.estimatedLatencyMs}ms</span></div>
              </div>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">FIELD MAPPINGS</div>
              <div className="space-y-1">
                {drawer.transformations.map((t) => (
                  <div key={t.sourceField} className="flex items-center justify-between text-[12px] py-1.5 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="font-mono text-[#f5f5f5] truncate">{t.sourceField}</span>
                      <span className="text-[#666]">→</span>
                      <span className="font-mono text-[#8a8a8a] truncate">{t.destinationField}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="default">{t.transform}</Badge>
                      {t.piiHandling !== 'pass' && <SeverityChip level="medium" />}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {(drawer.qualityWarnings.length > 0 || drawer.piiWarnings.length > 0) && (
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-[#c9b787]">WARNINGS</div>
                <ul className="space-y-1 text-[12px] text-[#d4a853]">
                  {[...drawer.qualityWarnings, ...drawer.piiWarnings].map((w, i) => (
                    <li key={i}>· {w}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
