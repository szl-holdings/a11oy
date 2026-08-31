import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { RELAY_MAPPINGS, RELAY_SOURCES, RELAY_MODELS } from '@/data/fabric';
import { useInnovationStore } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, FabricDrawer, SeverityChip, GovernanceDot } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, AlertTriangle, CheckCircle, XCircle, GitBranch, Zap } from 'lucide-react';

type ProposalStatus = 'pending' | 'approved' | 'deferred' | 'blocked';

interface DriftProposal {
  readonly id: string;
  readonly sourceId: string;
  readonly sourceName: string;
  readonly driftType: 'column_added' | 'column_dropped' | 'type_changed' | 'nullable_changed' | 'table_dropped';
  readonly fieldName: string;
  readonly oldValue: string;
  readonly newValue: string;
  readonly affectedMappingIds: readonly string[];
  readonly blastRadiusRecords: number;
  readonly severity: 'critical' | 'high' | 'medium' | 'low';
  readonly diff: string;
  readonly proposedFix: string;
  readonly anchorHash: string;
  status: ProposalStatus;
}

const SEEDED_PROPOSALS: DriftProposal[] = [
  {
    id: 'drift-001',
    sourceId: 'src-pg-billing',
    sourceName: 'Billing Postgres',
    driftType: 'column_added',
    fieldName: 'tax_id',
    oldValue: '(not present)',
    newValue: 'text NOT NULL DEFAULT \'\'',
    affectedMappingIds: RELAY_MAPPINGS.slice(0, 3).map((m) => m.id),
    blastRadiusRecords: 48200,
    severity: 'medium',
    diff: '+ tax_id text NOT NULL DEFAULT \'\'\n  id uuid NOT NULL\n  legal_name text NOT NULL\n  billing_email text NOT NULL\n  mrr_cents integer NOT NULL',
    proposedFix: 'Add tax_id → tax_identifier mapping with identity transform. No PII class detected (plain text). Mapper confidence: 0.81. Approval required: lead level.',
    anchorHash: '0xa1f3d8c2',
    status: 'pending',
  },
  {
    id: 'drift-002',
    sourceId: 'src-pg-billing',
    sourceName: 'Billing Postgres',
    driftType: 'type_changed',
    fieldName: 'mrr_cents',
    oldValue: 'integer',
    newValue: 'bigint',
    affectedMappingIds: RELAY_MAPPINGS.slice(0, 5).map((m) => m.id),
    blastRadiusRecords: 122400,
    severity: 'high',
    diff: '- mrr_cents integer NOT NULL\n+ mrr_cents bigint NOT NULL\n  arr_cents integer NOT NULL\n  plan_tier text NOT NULL',
    proposedFix: 'No transform change required — Courier will upcast integer values on delivery. Destination schemas accepting number type are unaffected. High blast radius due to 5 dependent mappings. Approval required: partner level (financial field, type change).',
    anchorHash: '0xb2e4a901',
    status: 'pending',
  },
  {
    id: 'drift-003',
    sourceId: 'src-stream-clickstream',
    sourceName: 'Clickstream Events',
    driftType: 'column_dropped',
    fieldName: 'session_referrer_url',
    oldValue: 'text NULLABLE',
    newValue: '(dropped)',
    affectedMappingIds: RELAY_MAPPINGS.slice(2, 4).map((m) => m.id),
    blastRadiusRecords: 34700,
    severity: 'critical',
    diff: '  session_id text NOT NULL\n  account_id uuid NOT NULL\n- session_referrer_url text\n  device_type text NOT NULL\n  started_at timestamp NOT NULL',
    proposedFix: 'Remove session_referrer_url from affected mapping field sets. Replace with constant transform (value: null) for backward-compatible destination delivery. Approval required: partner level (breaking source change).',
    anchorHash: '0xc3f5b812',
    status: 'pending',
  },
  {
    id: 'drift-004',
    sourceId: 'src-pg-billing',
    sourceName: 'Billing Postgres',
    driftType: 'nullable_changed',
    fieldName: 'renewal_at',
    oldValue: 'timestamp NULLABLE',
    newValue: 'timestamp NOT NULL',
    affectedMappingIds: RELAY_MAPPINGS.slice(1, 2).map((m) => m.id),
    blastRadiusRecords: 8900,
    severity: 'low',
    diff: '  id uuid NOT NULL\n- renewal_at timestamp\n+ renewal_at timestamp NOT NULL\n  updated_at timestamp NOT NULL',
    proposedFix: 'Low severity — destination can handle either nullable/non-nullable for this field. No mapping change required. Mark as resolved after review.',
    anchorHash: '0xd4e6c923',
    status: 'pending',
  },
];

const DRIFT_TYPE_BADGE: Record<DriftProposal['driftType'], string> = {
  column_added: '#5a8a6e',
  column_dropped: '#b85450',
  type_changed: '#d4a853',
  nullable_changed: '#78aac8',
  table_dropped: '#b85450',
};

export default function DriftRepairPage() {
  const { recordDriftDecision, applyMappingOverride } = useInnovationStore();
  const [proposals, setProposals] = useState<DriftProposal[]>(SEEDED_PROPOSALS);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [filter, setFilter] = useState<ProposalStatus | ''>('');

  const drawer = proposals.find((p) => p.id === drawerId) ?? null;

  const persistDecision = (p: DriftProposal, status: 'approved' | 'deferred' | 'blocked') => {
    recordDriftDecision({
      id: `dd-${p.id}`,
      proposalId: p.id,
      fieldName: p.fieldName,
      sourceName: p.sourceName,
      severity: p.severity,
      mappingIds: p.affectedMappingIds,
      status,
      resolvedAt: '2026-05-05T03:55:00Z',
    });
  };

  const approve = (id: string) => {
    setProposals((prev) => prev.map((p) => {
      if (p.id !== id) return p;
      persistDecision(p, 'approved');
      // Concretely mutate every affected mapping definition by recording an
      // override. mappings.tsx and the coalition runtime read these overrides
      // to compute the post-repair mapping deterministically.
      const action: 'add_field' | 'drop_field' | 'rename_type' | 'tighten_nullable' =
        p.driftType === 'column_added' ? 'add_field'
          : p.driftType === 'column_dropped' || p.driftType === 'table_dropped' ? 'drop_field'
          : p.driftType === 'type_changed' ? 'rename_type'
          : 'tighten_nullable';
      const fieldDelta = action === 'add_field' ? 1 : action === 'drop_field' ? -1 : 0;
      const transform: 'identity' | 'constant' | 'conditional' =
        action === 'add_field' ? 'identity'
          : action === 'rename_type' ? 'identity'
          : action === 'drop_field' ? 'constant'
          : 'conditional';
      for (const mid of p.affectedMappingIds) {
        applyMappingOverride({
          mappingId: mid,
          proposalId: p.id,
          fieldName: p.fieldName,
          action,
          addedTransformation: { sourceField: p.fieldName, destinationField: p.fieldName, transform, confidence: 0.87, piiHandling: 'pass' as const, note: `Auto-repair from drift proposal ${p.id}` },
          fieldDelta,
          governanceShift: p.severity === 'low' || p.severity === 'medium' ? 'amber_to_green' : 'red_to_amber',
          appliedAt: '2026-05-05T03:55:00Z',
        });
      }
      return { ...p, status: 'approved' as ProposalStatus };
    }));
    setDrawerId(null);
  };
  const defer = (id: string) => setProposals((prev) => prev.map((p) => {
    if (p.id !== id) return p;
    persistDecision(p, 'deferred');
    return { ...p, status: 'deferred' as ProposalStatus };
  }));
  const block = (id: string) => {
    setProposals((prev) => prev.map((p) => {
      if (p.id !== id) return p;
      persistDecision(p, 'blocked');
      return { ...p, status: 'blocked' as ProposalStatus };
    }));
    setDrawerId(null);
  };

  const visible = useMemo(() => filter ? proposals.filter((p) => p.status === filter) : proposals, [proposals, filter]);

  const pending = proposals.filter((p) => p.status === 'pending').length;
  const approved = proposals.filter((p) => p.status === 'approved').length;

  const affectedMappings = useMemo(() => {
    const ids = new Set(proposals.flatMap((p) => p.affectedMappingIds));
    return RELAY_MAPPINGS.filter((m) => ids.has(m.id));
  }, [proposals]);

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 03"
        title="Schema Drift Auto-Repair"
        blurb="Cartographer detects source schema changes. Mapper predicts impact across dependent mappings. Fixer proposes governed repair proposals — diff preview, blast radius, and one-click approval. No schema drift becomes a silent runtime failure."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Drift proposals" value={proposals.length} tone="gold" />
        <FabricStat label="Pending" value={pending} tone={pending > 0 ? 'warn' : 'good'} />
        <FabricStat label="Approved" value={approved} tone="good" />
        <FabricStat label="Mappings affected" value={affectedMappings.length} />
      </div>

      <div className="flex gap-2 mb-4">
        {(['', 'pending', 'approved', 'deferred', 'blocked'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-lg text-[11px] font-mono border transition-all ${filter === s ? 'border-[#c9b787] text-[#c9b787] bg-[rgba(201,183,135,0.08)]' : 'border-[rgba(255,255,255,0.08)] text-[#666] hover:border-[rgba(255,255,255,0.15)]'}`}
          >
            {s || 'all'}
          </button>
        ))}
      </div>

      <div className="space-y-3 mb-6">
        {visible.map((p) => {
          const mappingCount = p.affectedMappingIds.length;
          return (
            <div key={p.id} onClick={() => setDrawerId(p.id)} className="conduit-card p-4 text-left w-full cursor-pointer">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <SeverityChip level={p.severity} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-[#f5f5f5] text-sm">{p.fieldName}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: `${DRIFT_TYPE_BADGE[p.driftType]}18`, color: DRIFT_TYPE_BADGE[p.driftType] }}>{p.driftType.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="text-[11px] text-[#8a8a8a]">{p.sourceName} · {mappingCount} mapping{mappingCount !== 1 ? 's' : ''} affected · {p.blastRadiusRecords.toLocaleString()} records at risk</div>
                    <div className="font-mono text-[10px] text-[#555] mt-1 truncate">{p.oldValue} → {p.newValue}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant={p.status === 'approved' ? 'success' : p.status === 'blocked' ? 'failed' : p.status === 'deferred' ? 'paused' : 'partial'}>{p.status}</Badge>
                  {p.status === 'pending' && (
                    <div className="flex gap-1">
                      <button onClick={(e) => { e.stopPropagation(); approve(p.id); }} className="text-[10px] px-2 py-0.5 rounded bg-[rgba(90,138,110,0.12)] text-[#5a8a6e] border border-[rgba(90,138,110,0.2)] hover:bg-[rgba(90,138,110,0.2)]">approve</button>
                      <button onClick={(e) => { e.stopPropagation(); defer(p.id); }} className="text-[10px] px-2 py-0.5 rounded bg-[rgba(138,138,138,0.1)] text-[#8a8a8a] border border-[rgba(138,138,138,0.15)] hover:bg-[rgba(138,138,138,0.18)]">defer</button>
                      <button onClick={(e) => { e.stopPropagation(); block(p.id); }} className="text-[10px] px-2 py-0.5 rounded bg-[rgba(184,84,80,0.1)] text-[#b85450] border border-[rgba(184,84,80,0.2)] hover:bg-[rgba(184,84,80,0.18)]">block</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {visible.length === 0 && <div className="text-[13px] text-[#666] text-center py-8">No proposals matching filter.</div>}
      </div>

      <FabricCard title="AFFECTED MAPPINGS">
        <div className="space-y-2">
          {affectedMappings.slice(0, 8).map((m) => {
            const relatedProposals = proposals.filter((p) => p.affectedMappingIds.includes(m.id));
            return (
              <div key={m.id} className="flex items-center justify-between text-[12px] p-2 rounded bg-[#0e0e0e]">
                <div className="flex items-center gap-2 min-w-0">
                  <GitBranch className="w-3.5 h-3.5 text-[#c9b787] shrink-0" />
                  <span className="font-mono text-[#f5f5f5] truncate">{m.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] text-[#666]">{relatedProposals.length} proposal{relatedProposals.length !== 1 ? 's' : ''}</span>
                  <GovernanceDot state={m.governanceState} />
                  <Link href="/mappings" className="text-[10px] text-[#c9b787] hover:underline">view →</Link>
                </div>
              </div>
            );
          })}
        </div>
      </FabricCard>

      <FabricDrawer open={!!drawer} onClose={() => setDrawerId(null)} title={`Drift Proposal · ${drawer?.fieldName ?? ''}`} subtitle={drawer?.driftType.replace(/_/g, ' ')}>
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Severity" value={drawer.severity.toUpperCase()} tone={drawer.severity === 'critical' ? 'bad' : drawer.severity === 'high' ? 'warn' : 'neutral'} />
              <FabricStat label="Blast radius" value={`${drawer.blastRadiusRecords.toLocaleString()} rec.`} tone="warn" />
              <FabricStat label="Affected mappings" value={drawer.affectedMappingIds.length} />
              <FabricStat label="Status" value={drawer.status.toUpperCase()} tone={drawer.status === 'approved' ? 'good' : drawer.status === 'blocked' ? 'bad' : 'neutral'} />
            </div>

            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">DIFF PREVIEW</div>
              <pre className="font-mono text-[11px] bg-[#0a0a0a] p-3 rounded overflow-x-auto whitespace-pre-wrap">
                {drawer.diff.split('\n').map((line, i) => (
                  <div key={i} className={line.startsWith('+') ? 'text-[#5a8a6e]' : line.startsWith('-') ? 'text-[#b85450]' : 'text-[#8a8a8a]'}>
                    {line}
                  </div>
                ))}
              </pre>
            </div>

            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">PROPOSED FIX</div>
              <div className="flex items-start gap-2">
                <Zap className="w-3.5 h-3.5 text-[#c9b787] shrink-0 mt-0.5" />
                <p className="text-[12px] text-[#f5f5f5] leading-relaxed">{drawer.proposedFix}</p>
              </div>
            </div>

            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">AGENT COALITION</div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex items-center gap-2"><span className="text-[#c9b787] w-24 font-mono">Cartographer</span><span className="text-[#8a8a8a]">Detected schema change on profiling pass</span></div>
                <div className="flex items-center gap-2"><span className="text-[#c9b787] w-24 font-mono">Mapper</span><span className="text-[#8a8a8a]">Computed blast radius across {drawer.affectedMappingIds.length} mappings</span></div>
                <div className="flex items-center gap-2"><span className="text-[#c9b787] w-24 font-mono">Fixer</span><span className="text-[#8a8a8a]">Proposed deterministic repair with confidence 0.87</span></div>
                <div className="flex items-center gap-2"><span className="text-[#c9b787] w-24 font-mono">Sentinel</span><span className="text-[#8a8a8a]">Approval gate: {drawer.severity === 'critical' || drawer.severity === 'high' ? 'partner' : 'lead'} level required</span></div>
              </div>
            </div>

            {drawer.status === 'pending' && (
              <div className="flex gap-2">
                <Button onClick={() => approve(drawer.id)} className="flex-1">
                  <CheckCircle className="w-4 h-4 mr-1.5" /> Approve repair
                </Button>
                <Button variant="outline" onClick={() => defer(drawer.id)}>Defer</Button>
                <Button variant="destructive" onClick={() => block(drawer.id)}>
                  <XCircle className="w-4 h-4 mr-1" />
                </Button>
              </div>
            )}

            {drawer.status !== 'pending' && (
              <div className={`p-3 rounded text-[12px] ${drawer.status === 'approved' ? 'text-[#5a8a6e]' : 'text-[#b85450]'}`} style={{ background: drawer.status === 'approved' ? 'rgba(90,138,110,0.1)' : 'rgba(184,84,80,0.1)' }}>
                {drawer.status === 'approved' ? <><CheckCircle className="w-4 h-4 inline mr-1" /> Repair approved — mapping updates applied</> : `Proposal ${drawer.status}`}
              </div>
            )}

            <div className="conduit-card p-3">
              <div className="label-mono mb-1">ANCHOR HASH</div>
              <div className="font-mono text-[11px] text-[#555]">{drawer.anchorHash}</div>
            </div>
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
