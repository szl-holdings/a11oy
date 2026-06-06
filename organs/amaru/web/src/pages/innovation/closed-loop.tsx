import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { RELAY_OUTCOMES, RELAY_DESTINATIONS, RELAY_MAPPINGS } from '@/data/fabric';
import type { RelayOutcome } from '@/data/fabric/types';
import { useInnovationStore, type ClosedLoopOutcomeRecord } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, GovernanceDot } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, ArrowRight, RefreshCw, Zap, CheckCircle, RotateCcw } from 'lucide-react';

type MutationKind = 'lead_lost' | 'deal_closed' | 'ticket_resolved' | 'subscription_cancelled' | 'opportunity_reopened';

interface DestinationMutation {
  readonly id: string;
  readonly destinationId: string;
  readonly destinationName: string;
  readonly kind: MutationKind;
  readonly entityId: string;
  readonly entityLabel: string;
  readonly fieldChanged: string;
  readonly oldValue: string;
  readonly newValue: string;
  readonly capturedAt: string;
  readonly outcomeRef: string | null;
  status: 'captured' | 'processing' | 'ingested';
}

type CapturedOutcome = ClosedLoopOutcomeRecord;

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}
function hex8(n: number) { return n.toString(16).padStart(8, '0').slice(0, 8); }

const MUTATION_TEMPLATES: readonly { kind: MutationKind; field: string; old: string; newVal: string; label: string }[] = [
  { kind: 'lead_lost', field: 'deal_stage', old: 'discovery', newVal: 'lost', label: 'Lead marked lost' },
  { kind: 'deal_closed', field: 'deal_stage', old: 'negotiation', newVal: 'closed_won', label: 'Deal closed won' },
  { kind: 'ticket_resolved', field: 'ticket_status', old: 'open', newVal: 'resolved', label: 'Ticket resolved' },
  { kind: 'subscription_cancelled', field: 'plan_tier', old: 'enterprise', newVal: 'cancelled', label: 'Subscription cancelled' },
  { kind: 'opportunity_reopened', field: 'deal_stage', old: 'lost', newVal: 'discovery', label: 'Opportunity reopened' },
];

const SEED_MUTATIONS: DestinationMutation[] = [
  {
    id: 'mut-001',
    destinationId: 'dst-crm-activate',
    destinationName: 'Activate CRM',
    kind: 'lead_lost',
    entityId: 'crm-acct-M2219',
    entityLabel: 'ACC-VTG-M2219 (Vantage Industrial AG)',
    fieldChanged: 'deal_stage',
    oldValue: 'discovery',
    newValue: 'lost',
    capturedAt: '2026-05-05T01:22:00Z',
    outcomeRef: RELAY_OUTCOMES[0]?.id ?? null,
    status: 'ingested',
  },
  {
    id: 'mut-002',
    destinationId: 'dst-crm-meridian',
    destinationName: 'Meridian CRM',
    kind: 'deal_closed',
    entityId: 'crm-acct-5541',
    entityLabel: 'Northbridge Capital',
    fieldChanged: 'deal_stage',
    oldValue: 'negotiation',
    newValue: 'closed_won',
    capturedAt: '2026-05-05T02:45:00Z',
    outcomeRef: RELAY_OUTCOMES[1]?.id ?? null,
    status: 'ingested',
  },
];

const KIND_BADGE: Record<MutationKind, string> = {
  lead_lost: '#b85450',
  deal_closed: '#5a8a6e',
  ticket_resolved: '#78aac8',
  subscription_cancelled: '#b85450',
  opportunity_reopened: '#d4a853',
};

export default function ClosedLoopPage() {
  const { closedLoopOutcomes, addClosedLoopOutcome } = useInnovationStore();
  const [mutations, setMutations] = useState<DestinationMutation[]>(SEED_MUTATIONS);
  const injectedOutcomes = closedLoopOutcomes;
  const [selectedTemplate, setSelectedTemplate] = useState(0);
  const [selectedDestId, setSelectedDestId] = useState(RELAY_DESTINATIONS[0]?.id ?? '');
  const [injecting, setInjecting] = useState(false);

  const injectMutation = () => {
    const tmpl = MUTATION_TEMPLATES[selectedTemplate]!;
    const dest = RELAY_DESTINATIONS.find((d) => d.id === selectedDestId);
    if (!dest) return;
    setInjecting(true);

    const mutId = `mut-${hex8(fnv1a(`${tmpl.kind}:${selectedDestId}:${mutations.length}`))}`;
    const newMut: DestinationMutation = {
      id: mutId,
      destinationId: selectedDestId,
      destinationName: dest.name,
      kind: tmpl.kind,
      entityId: `entity-${hex8(fnv1a(`${mutId}:ent`))}`,
      entityLabel: `Demo Entity (${dest.name})`,
      fieldChanged: tmpl.field,
      oldValue: tmpl.old,
      newValue: tmpl.newVal,
      capturedAt: '2026-05-05T03:55:00Z',
      outcomeRef: null,
      status: 'captured',
    };
    setMutations((prev) => [newMut, ...prev]);

    setTimeout(() => {
      setMutations((prev) => prev.map((m) => m.id === mutId ? { ...m, status: 'processing' as const } : m));
      setTimeout(() => {
        const mapping = RELAY_MAPPINGS.find((m) => m.destinationId === selectedDestId);
        const outcomeId = `ro-${hex8(fnv1a(`outcome:${mutId}`))}`;
        const liftPct = tmpl.kind === 'deal_closed' ? 0.18 : tmpl.kind === 'lead_lost' ? -0.08 : 0.04;
        const newOutcome: CapturedOutcome = {
          id: outcomeId,
          syncId: mapping?.id ?? 'sync-demo',
          syncName: mapping?.name ?? `${dest.name} Sync`,
          verticalId: mapping?.verticalId ?? 'lyte',
          destinationId: selectedDestId,
          observedAtIso: '2026-05-05T03:55:00Z',
          predictedMetric: tmpl.field,
          predictedValue: tmpl.kind === 'deal_closed' ? 1 : 0,
          actualValue: 1,
          predictionError: Math.round((fnv1a(mutId) % 20 - 10) / 100 * 100) / 100,
          liftPct,
          lessonLearned: `Reverse-Reverse capture: ${dest.name} mutation '${tmpl.field}=${tmpl.newVal}' observed. Forecaster updated lift estimate by ${(liftPct * 100).toFixed(1)}%.`,
          policyUpdateCandidate: tmpl.kind === 'subscription_cancelled' || tmpl.kind === 'lead_lost',
          evidenceRef: `evidence/${mutId}`,
          reverseMutationId: mutId,
          capturedFromDestinationId: selectedDestId,
        };
        setMutations((prev) => prev.map((m) => m.id === mutId ? { ...m, status: 'ingested' as const, outcomeRef: outcomeId } : m));
        addClosedLoopOutcome(newOutcome);
        setInjecting(false);
      }, 800);
    }, 500);
  };

  const allOutcomes = useMemo(() => [...injectedOutcomes, ...RELAY_OUTCOMES.slice(0, 4)], [injectedOutcomes]);

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 06"
        title="Reverse-Reverse ETL"
        blurb="When a destination mutates (CRM rep marks lead lost), Amaru captures that signal and feeds it back as an outcome, updating Forecaster's lift model and closing the activation learning loop."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Mutations captured" value={mutations.length} tone="gold" />
        <FabricStat label="Ingested" value={mutations.filter((m) => m.status === 'ingested').length} tone="good" />
        <FabricStat label="Outcomes created" value={allOutcomes.length} />
        <FabricStat label="Loop closures (session)" value={injectedOutcomes.length} tone="good" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <FabricCard title="INJECT DESTINATION MUTATION">
          <div className="space-y-4">
            <div>
              <div className="label-mono mb-2">DESTINATION</div>
              <select
                value={selectedDestId}
                onChange={(e) => setSelectedDestId(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm"
              >
                {RELAY_DESTINATIONS.slice(0, 10).map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div className="label-mono mb-2">MUTATION TYPE</div>
              <div className="space-y-1">
                {MUTATION_TEMPLATES.map((tmpl, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedTemplate(i)}
                    className="flex items-center gap-3 w-full text-left px-3 py-2 rounded border transition-all text-[12px]"
                    style={{ borderColor: selectedTemplate === i ? '#c9b787' : 'rgba(255,255,255,0.06)', background: selectedTemplate === i ? 'rgba(201,183,135,0.05)' : 'transparent' }}
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0`} style={{ background: KIND_BADGE[tmpl.kind] }} />
                    <span className="text-[#f5f5f5] flex-1">{tmpl.label}</span>
                    <span className="font-mono text-[#555] text-[10px]">{tmpl.field} → {tmpl.newVal}</span>
                  </button>
                ))}
              </div>
            </div>

            <Button onClick={injectMutation} isLoading={injecting} className="w-full">
              <Zap className="w-4 h-4 mr-2" /> Inject Mutation
            </Button>

            <div className="p-3 rounded text-[11px] text-[#666]" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
              The Courier adapter polls the destination webhook endpoint. On mutation detection, Scribe emits a reverse-capture event. Forecaster recalibrates the lift estimate. Outcome record appears in the Outcomes surface within the same session.
            </div>
          </div>
        </FabricCard>

        <FabricCard title="MUTATION CAPTURE FEED">
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {mutations.map((mut) => (
              <div key={mut.id} className="p-3 rounded text-[12px]" style={{ background: '#0e0e0e', border: '1px solid rgba(255,255,255,0.04)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: KIND_BADGE[mut.kind] }} />
                    <span className="font-mono text-[10px] text-[#c9b787]">{mut.kind.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {mut.status === 'ingested' && <CheckCircle className="w-3.5 h-3.5 text-[#5a8a6e]" />}
                    {mut.status === 'processing' && <RefreshCw className="w-3.5 h-3.5 text-[#d4a853] animate-spin" />}
                    <Badge variant={mut.status === 'ingested' ? 'success' : mut.status === 'processing' ? 'partial' : 'default'}>{mut.status}</Badge>
                  </div>
                </div>
                <div className="text-[#f5f5f5]">{mut.entityLabel}</div>
                <div className="text-[11px] text-[#666] mt-0.5">
                  <span className="text-[#8a8a8a]">{mut.destinationName}</span>
                  <span className="mx-1">·</span>
                  <span className="font-mono">{mut.fieldChanged}: </span>
                  <span className="text-[#b85450]">{mut.oldValue}</span>
                  <ArrowRight className="w-3 h-3 inline mx-0.5" />
                  <span className="text-[#5a8a6e]">{mut.newValue}</span>
                </div>
                {mut.outcomeRef && <div className="text-[10px] text-[#555] mt-1 font-mono">→ outcome {mut.outcomeRef}</div>}
              </div>
            ))}
          </div>
        </FabricCard>
      </div>

      <FabricCard title="OUTCOMES SURFACE — CLOSED-LOOP SIGNALS" className="mb-4">
        <div className="space-y-2">
          {allOutcomes.slice(0, 8).map((o) => {
            const isNew = 'reverseMutationId' in o;
            return (
              <div key={o.id} className="flex items-center justify-between text-[12px] p-2 rounded" style={{ background: isNew ? 'rgba(201,183,135,0.04)' : '#0e0e0e', border: `1px solid ${isNew ? 'rgba(201,183,135,0.15)' : 'rgba(255,255,255,0.04)'}` }}>
                <div className="flex items-center gap-3 min-w-0">
                  {isNew ? <RotateCcw className="w-3.5 h-3.5 text-[#c9b787] shrink-0" /> : <GovernanceDot state="green" />}
                  <div className="min-w-0">
                    <div className="text-[#f5f5f5] truncate">{o.syncName}</div>
                    <div className="text-[10px] text-[#666]">{o.predictedMetric} · {new Date(o.observedAtIso).toLocaleDateString()}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`font-mono tabular-nums ${o.liftPct >= 0 ? 'text-[#5a8a6e]' : 'text-[#b85450]'}`}>{(o.liftPct * 100).toFixed(1)}%</span>
                  {isNew && <Badge variant="active">new</Badge>}
                  {o.policyUpdateCandidate && <Badge variant="partial">policy</Badge>}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)]">
          <Link href="/outcomes" className="text-[11px] text-[#c9b787] hover:underline">View full Outcomes surface →</Link>
        </div>
      </FabricCard>
    </div>
  );
}
