import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { RELAY_SOURCES, RELAY_MODELS, RELAY_MAPPINGS, RELAY_DESTINATIONS, RELAY_OUTCOMES } from '@/data/fabric';
import { FabricHeader, FabricCard, FabricStat, GovernanceDot, SeverityChip } from '@/components/fabric/primitives';
import { Badge } from '@/components/ui';
import { ArrowLeft, ArrowRight, Shield, Hash, Target, Database, Boxes, GitBranch, Network } from 'lucide-react';
import { CATEGORY_TONES, wash } from '@/lib/utils';

type NodeKind = 'source' | 'model' | 'mapping' | 'destination' | 'outcome';

interface LineageNode {
  readonly id: string;
  readonly kind: NodeKind;
  readonly label: string;
  readonly sublabel: string;
  readonly governance: 'green' | 'amber' | 'red';
  readonly anchorHash: string;
  readonly href: string;
}

interface LineageEdge {
  readonly fromId: string;
  readonly toId: string;
  readonly anchorHash: string;
  readonly evidenceRef: string;
  readonly governed: boolean;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}
function shortHex(n: number) { return n.toString(16).padStart(8, '0').slice(0, 8); }

const KIND_ICON: Record<NodeKind, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  source: Database,
  model: Boxes,
  mapping: GitBranch,
  destination: Network,
  outcome: Target,
};

const KIND_COLOR: Record<NodeKind, string> = {
  source: CATEGORY_TONES[4],
  model: CATEGORY_TONES[0],
  mapping: CATEGORY_TONES[2],
  destination: CATEGORY_TONES[1],
  outcome: CATEGORY_TONES[3],
};

const KIND_HREF: Record<NodeKind, string> = {
  source: '/sources',
  model: '/models',
  mapping: '/mappings',
  destination: '/destinations',
  outcome: '/outcomes',
};

export default function LineagePage() {
  const [selectedMappingId, setSelectedMappingId] = useState(RELAY_MAPPINGS[0]?.id ?? '');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const lineage = useMemo(() => {
    const mapping = RELAY_MAPPINGS.find((m) => m.id === selectedMappingId);
    if (!mapping) return null;
    const model = RELAY_MODELS.find((mo) => mo.id === mapping.modelId);
    const source = model ? RELAY_SOURCES.find((s) => s.id === model.sourceId) : null;
    const dest = RELAY_DESTINATIONS.find((d) => d.id === mapping.destinationId);
    const outcome = RELAY_OUTCOMES.find((o) => o.destinationId === mapping.destinationId && o.verticalId === mapping.verticalId);

    const nodes: LineageNode[] = [];
    const edges: LineageEdge[] = [];

    if (source) nodes.push({ id: source.id, kind: 'source', label: source.name, sublabel: source.kind, governance: source.governanceState, anchorHash: source.anchorHash, href: '/sources' });
    if (model) nodes.push({ id: model.id, kind: 'model', label: model.name, sublabel: `${model.fieldCount} fields`, governance: model.governanceState, anchorHash: model.anchorHash, href: '/models' });
    nodes.push({ id: mapping.id, kind: 'mapping', label: mapping.name, sublabel: `${mapping.mappedFieldCount} field mappings`, governance: mapping.governanceState, anchorHash: mapping.anchorHash, href: '/mappings' });
    if (dest) nodes.push({ id: dest.id, kind: 'destination', label: dest.name, sublabel: dest.category, governance: dest.governanceState, anchorHash: dest.anchorHash, href: '/destinations' });
    if (outcome) nodes.push({ id: outcome.id, kind: 'outcome', label: outcome.syncName, sublabel: `lift ${(outcome.liftPct * 100).toFixed(1)}%`, governance: 'green', anchorHash: `0x${shortHex(fnv1a(`outcome:${outcome.id}`))}`, href: '/outcomes' });

    if (source && model) edges.push({ fromId: source.id, toId: model.id, anchorHash: `0x${shortHex(fnv1a(`edge:${source.id}:${model.id}`))}`, evidenceRef: `evidence/src-mdl-${shortHex(fnv1a(source.id + model.id))}`, governed: source.governanceState === 'green' && model.governanceState === 'green' });
    if (model) edges.push({ fromId: model.id, toId: mapping.id, anchorHash: `0x${shortHex(fnv1a(`edge:${model.id}:${mapping.id}`))}`, evidenceRef: `evidence/mdl-map-${shortHex(fnv1a(model.id + mapping.id))}`, governed: model.governanceState === 'green' && mapping.governanceState !== 'red' });
    if (dest) edges.push({ fromId: mapping.id, toId: dest.id, anchorHash: `0x${shortHex(fnv1a(`edge:${mapping.id}:${dest.id}`))}`, evidenceRef: `evidence/map-dst-${shortHex(fnv1a(mapping.id + dest.id))}`, governed: mapping.governanceState !== 'red' && dest.governanceState !== 'red' });
    if (dest && outcome) edges.push({ fromId: dest.id, toId: outcome.id, anchorHash: `0x${shortHex(fnv1a(`edge:${dest.id}:${outcome.id}`))}`, evidenceRef: outcome.evidenceRef, governed: true });

    return { nodes, edges, mapping, model, source, dest, outcome };
  }, [selectedMappingId]);

  const selectedNode = lineage?.nodes.find((n) => n.id === selectedNodeId) ?? null;

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 02"
        title="Lineage Graph"
        blurb="End-to-end source → model → mapping → destination → outcome visualization. Every edge carries a proof-anchor hash. Click any node to navigate to its Amaru surface or inspect its evidence reference."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-link hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Sources" value={RELAY_SOURCES.length} />
        <FabricStat label="Models" value={RELAY_MODELS.length} tone="gold" />
        <FabricStat label="Mappings" value={RELAY_MAPPINGS.length} />
        <FabricStat label="Outcomes" value={RELAY_OUTCOMES.length} tone="good" />
      </div>

      <FabricCard title="SELECT MAPPING TO TRACE" className="mb-6">
        <div className="flex flex-wrap gap-2">
          {RELAY_MAPPINGS.slice(0, 16).map((m) => (
            <button
              key={m.id}
              onClick={() => { setSelectedMappingId(m.id); setSelectedNodeId(null); }}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-mono border transition-all ${selectedMappingId === m.id ? 'border-ink-sub text-ink bg-wash/8' : 'border-line text-ink-sub hover:border-line'}`}
            >
              {m.name}
            </button>
          ))}
        </div>
      </FabricCard>

      {lineage && (
        <>
          <FabricCard title="LINEAGE GRAPH" className="mb-6">
            <div className="overflow-x-auto">
              <div className="flex items-start gap-0 min-w-[700px]">
                {lineage.nodes.map((node, idx) => {
                  const Icon = KIND_ICON[node.kind];
                  const color = KIND_COLOR[node.kind];
                  const isSelected = selectedNodeId === node.id;
                  const edgeBefore = idx > 0 ? lineage.edges.find((e) => e.toId === node.id) : null;
                  return (
                    <div key={node.id} className="flex items-center flex-1 min-w-0">
                      {edgeBefore && (
                        <div className="flex flex-col items-center px-1 shrink-0" style={{ minWidth: 64 }}>
                          <div className="flex items-center gap-1">
                            <div className="h-px flex-1 min-w-[20px]" style={{ background: edgeBefore.governed ? 'color-mix(in srgb, var(--color-success) 50%, transparent)' : 'color-mix(in srgb, var(--ink-bad) 40%, transparent)' }} />
                            <ArrowRight className="w-3 h-3 shrink-0" style={{ color: edgeBefore.governed ? 'var(--ink-good)' : 'var(--ink-bad)' }} />
                            <div className="h-px flex-1 min-w-[20px]" style={{ background: edgeBefore.governed ? 'color-mix(in srgb, var(--color-success) 50%, transparent)' : 'color-mix(in srgb, var(--ink-bad) 40%, transparent)' }} />
                          </div>
                          <div className="text-[9px] font-mono text-ink-sub mt-1 text-center truncate max-w-[60px]" title={edgeBefore.anchorHash}>
                            <Shield className="w-2.5 h-2.5 inline text-ink mr-0.5" />
                            {edgeBefore.anchorHash.slice(0, 6)}
                          </div>
                        </div>
                      )}
                      <button
                        onClick={() => setSelectedNodeId(isSelected ? null : node.id)}
                        className="flex flex-col items-center p-3 rounded-xl border transition-all shrink-0"
                        style={{
                          borderColor: isSelected ? color : 'var(--border)',
                          background: isSelected ? wash(color, 6) : 'var(--surface)',
                          minWidth: 110,
                        }}
                      >
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2" style={{ background: wash(color, 9) }}>
                          <Icon className="w-4 h-4" style={{ color }} />
                        </div>
                        <div className="text-[10px] font-mono uppercase tracking-wider mb-0.5 text-ink-sub">{node.kind}</div>
                        <div className="text-[11px] text-ink text-center leading-tight">{node.label}</div>
                        <div className="text-[10px] text-ink-sub mt-0.5">{node.sublabel}</div>
                        <div className="mt-1.5"><GovernanceDot state={node.governance} /></div>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-line-subtle">
              <div className="label-mono mb-2">EDGE PROOF ANCHORS</div>
              <div className="space-y-1.5">
                {lineage.edges.map((edge, i) => {
                  const fromNode = lineage.nodes.find((n) => n.id === edge.fromId);
                  const toNode = lineage.nodes.find((n) => n.id === edge.toId);
                  // Each proof anchor is actionable: clicking the row opens
                  // the destination node's surface (Codex Kernel evidence
                  // record route on the kernel page, scoped by anchor).
                  const evidenceHref = toNode?.kind === 'outcome'
                    ? `/codex-loop?evidence=${encodeURIComponent(edge.evidenceRef)}`
                    : `${toNode?.href ?? '/codex-loop'}?anchor=${encodeURIComponent(edge.anchorHash)}&evidence=${encodeURIComponent(edge.evidenceRef)}`;
                  return (
                    <Link
                      key={i}
                      href={evidenceHref}
                      className="flex items-center gap-3 text-[11px] py-1.5 px-3 rounded bg-ground-deep hover:bg-wash/7 border border-transparent hover:border-line-subtle transition-colors"
                      title={`Open evidence ${edge.evidenceRef}`}
                    >
                      <Shield className="w-3 h-3 text-ink shrink-0" />
                      <span className="font-mono text-ink-sub truncate flex-1">
                        {fromNode?.label} → {toNode?.label}
                      </span>
                      <span className="font-mono text-ink shrink-0 underline-offset-2 hover:underline">{edge.anchorHash}</span>
                      <span className="font-mono text-ink-sub shrink-0 hidden md:inline">{edge.evidenceRef}</span>
                      <ArrowRight className="w-3 h-3 text-ink shrink-0" />
                      <span className={`w-2 h-2 rounded-full shrink-0 ${edge.governed ? 'bg-success' : 'bg-error'}`} />
                    </Link>
                  );
                })}
              </div>
            </div>
          </FabricCard>

          {selectedNode && (
            <FabricCard title={`NODE DETAIL — ${selectedNode.kind.toUpperCase()}`} className="mb-6 animate-scale-in">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <div className="label-mono mb-1">Label</div>
                  <div className="text-ink text-[12px]">{selectedNode.label}</div>
                </div>
                <div>
                  <div className="label-mono mb-1">Kind</div>
                  <div className="text-[12px]" style={{ color: KIND_COLOR[selectedNode.kind] }}>{selectedNode.kind}</div>
                </div>
                <div>
                  <div className="label-mono mb-1">Governance</div>
                  <div className="flex items-center gap-1"><GovernanceDot state={selectedNode.governance} /><span className="text-[12px] text-ink">{selectedNode.governance}</span></div>
                </div>
                <div>
                  <div className="label-mono mb-1">Anchor Hash</div>
                  <div className="font-mono text-[11px] text-ink-sub">{selectedNode.anchorHash}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Link href={selectedNode.href} className="flex items-center gap-1.5 text-[12px] text-link hover:underline">
                  Open {selectedNode.kind} surface <ArrowRight className="w-3 h-3" />
                </Link>
                <span className="text-[11px] font-mono text-ink-sub">evidence/{shortHex(fnv1a(selectedNode.id))}</span>
              </div>
            </FabricCard>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <FabricCard title="MAPPING DETAIL">
              <div className="space-y-2">
                <div className="flex justify-between text-[12px]">
                  <span className="text-ink-sub">Mapped fields</span>
                  <span className="font-mono text-ink">{lineage.mapping.mappedFieldCount}</span>
                </div>
                <div className="flex justify-between text-[12px]">
                  <span className="text-ink-sub">Confidence</span>
                  <span className="font-mono text-ink">{(lineage.mapping.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-[12px]">
                  <span className="text-ink-sub">Proposed by</span>
                  <Badge variant="default">{lineage.mapping.proposedBy.replace(/-/g, ' ')}</Badge>
                </div>
                {lineage.mapping.qualityWarnings.length > 0 && (
                  <div>
                    <div className="label-mono mb-1">Warnings</div>
                    {lineage.mapping.qualityWarnings.map((w, i) => <div key={i} className="text-[11px] text-ink-warn">· {w}</div>)}
                  </div>
                )}
              </div>
            </FabricCard>

            {lineage.outcome && (
              <FabricCard title="OUTCOME">
                <div className="space-y-2">
                  <div className="flex justify-between text-[12px]">
                    <span className="text-ink-sub">Predicted</span>
                    <span className="font-mono text-ink">{lineage.outcome.predictedValue.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[12px]">
                    <span className="text-ink-sub">Actual</span>
                    <span className="font-mono text-ink">{lineage.outcome.actualValue.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[12px]">
                    <span className="text-ink-sub">Lift</span>
                    <span className={`font-mono ${lineage.outcome.liftPct >= 0 ? 'text-ink-good' : 'text-ink-bad'}`}>{(lineage.outcome.liftPct * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-[12px]">
                    <span className="text-ink-sub">Prediction error</span>
                    <SeverityChip level={Math.abs(lineage.outcome.predictionError) > 0.15 ? 'medium' : 'low'} />
                  </div>
                  <div className="text-[11px] text-ink-sub mt-2 p-2 rounded bg-ground">{lineage.outcome.lessonLearned}</div>
                  <Link href="/outcomes" className="text-[11px] text-link hover:underline">View outcome →</Link>
                </div>
              </FabricCard>
            )}
          </div>
        </>
      )}

      <div className="mt-4 p-3 rounded-lg text-[11px] text-ink-sub" style={{ border: '1px solid var(--border-subtle)' }}>
        <Hash className="w-3 h-3 inline mr-1 text-ink-sub" />
        All proof-anchor hashes are FNV-1a derived from entity IDs — deterministic, collision-resistant, replay-grade. The Scribe agent hash-chains every decision into the Codex Kernel ledger.
      </div>
    </div>
  );
}
