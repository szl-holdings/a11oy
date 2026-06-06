import { useState } from 'react';
import { Link } from 'wouter';
import { useInnovationStore } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, FabricDrawer, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, Merge, CheckCircle, AlertTriangle, Users, GitMerge } from 'lucide-react';

interface SourceRecord {
  readonly source: string;
  readonly sourceKind: string;
  readonly entityId: string;
  readonly accountId: string;
  readonly registrationNumber: string;
  readonly ticker: string;
  readonly region: string;
  readonly lastSeen: string;
  readonly confidence: number;
  readonly fields: Record<string, string>;
}

interface IdentityCluster {
  readonly id: string;
  readonly entityType: string;
  readonly records: readonly SourceRecord[];
  readonly overallConfidence: number;
  readonly conflictFields: readonly string[];
  mergeStatus: 'pending' | 'merged' | 'dismissed';
  resolvedFields: Record<string, { value: string; sourceIdx: number }>;
}

const SEED_CLUSTERS: IdentityCluster[] = [
  {
    id: 'cluster-001',
    entityType: 'organisation',
    records: [
      { source: 'CRM', sourceKind: 'crm', entityId: 'crm-acct-8812', accountId: 'ACC-AXM-8812', registrationNumber: 'EIN-82-4419201', ticker: 'AXM', region: 'NA-WEST', lastSeen: '2026-05-04', confidence: 0.94, fields: { plan_tier: 'enterprise', deal_stage: 'closed_won', lifetime_value_usd: '128000', industry: 'industrial_iot' } },
      { source: 'Warehouse', sourceKind: 'warehouse', entityId: 'wh-acct-A4421', accountId: 'ACC-AXM-A4421', registrationNumber: 'EIN-82-4419201', ticker: 'AXM', region: 'NA-WEST', lastSeen: '2026-05-03', confidence: 0.88, fields: { arr_cents: '1280000', mrr_cents: '106667', churn_risk: '0.12' } },
      { source: 'Support', sourceKind: 'support', entityId: 'sup-org-A4421', accountId: 'ACC-AXM-8812', registrationNumber: 'EIN-82-4419201', ticker: 'AXM', region: 'NA-WEST', lastSeen: '2026-04-28', confidence: 0.91, fields: { open_tickets: '2', avg_csat: '4.7', last_ticket_sev: 'medium' } },
    ],
    overallConfidence: 0.91,
    conflictFields: ['accountId'],
    mergeStatus: 'pending',
    resolvedFields: {
      accountId: { value: 'ACC-AXM-8812', sourceIdx: 0 },
      registrationNumber: { value: 'EIN-82-4419201', sourceIdx: 0 },
      ticker: { value: 'AXM', sourceIdx: 0 },
      region: { value: 'NA-WEST', sourceIdx: 0 },
    },
  },
  {
    id: 'cluster-002',
    entityType: 'organisation',
    records: [
      { source: 'CRM', sourceKind: 'crm', entityId: 'crm-acct-5541', accountId: 'ACC-NBC-5541', registrationNumber: 'LEI-549300NBC2026X', ticker: 'NBC', region: 'NA-EAST', lastSeen: '2026-05-02', confidence: 0.96, fields: { industry: 'finance', employees_band: '2000_5000', region_detail: 'northeast' } },
      { source: 'Billing', sourceKind: 'oltp_postgres', entityId: 'bill-9921', accountId: 'ACC-NBC-9921', registrationNumber: 'LEI-549300NBC2026X', ticker: 'NBC', region: 'NA-EAST', lastSeen: '2026-05-05', confidence: 0.97, fields: { mrr_cents: '487500', plan_tier: 'enterprise', renewal_at: '2026-12-01' } },
    ],
    overallConfidence: 0.97,
    conflictFields: ['accountId'],
    mergeStatus: 'pending',
    resolvedFields: {
      accountId: { value: 'ACC-NBC-5541', sourceIdx: 0 },
      registrationNumber: { value: 'LEI-549300NBC2026X', sourceIdx: 0 },
      ticker: { value: 'NBC', sourceIdx: 0 },
      region: { value: 'NA-EAST', sourceIdx: 0 },
    },
  },
  {
    id: 'cluster-003',
    entityType: 'organisation',
    records: [
      { source: 'Marketing', sourceKind: 'event_stream', entityId: 'mkt-acct-L8821', accountId: 'ACC-VTG-L8821', registrationNumber: 'EIN-47-9920113', ticker: 'VTG', region: 'NA-WEST', lastSeen: '2026-04-30', confidence: 0.72, fields: { lead_score: '88', utm_source: 'partner_directory', form_fill: 'demo_request' } },
      { source: 'CRM', sourceKind: 'crm', entityId: 'crm-acct-M2219', accountId: 'ACC-VTG-M2219', registrationNumber: 'EIN-47-9920113', ticker: 'VTG', region: 'NA-WEST', lastSeen: '2026-05-01', confidence: 0.78, fields: { deal_stage: 'discovery', deal_owner_team: 'team-pacific', est_close: '2026-07-15' } },
    ],
    overallConfidence: 0.75,
    conflictFields: ['accountId'],
    mergeStatus: 'pending',
    resolvedFields: {
      accountId: { value: 'ACC-VTG-L8821', sourceIdx: 0 },
      registrationNumber: { value: 'EIN-47-9920113', sourceIdx: 0 },
      ticker: { value: 'VTG', sourceIdx: 0 },
      region: { value: 'NA-WEST', sourceIdx: 0 },
    },
  },
];

const FIELD_LABELS: Record<string, string> = {
  accountId: 'Account ID',
  registrationNumber: 'Registration #',
  ticker: 'Ticker',
  region: 'Region',
};

function getRecordField(r: SourceRecord, field: string): string {
  if (field === 'accountId') return r.accountId;
  if (field === 'registrationNumber') return r.registrationNumber;
  if (field === 'ticker') return r.ticker;
  if (field === 'region') return r.region;
  return r.fields[field] ?? '';
}

export default function GoldenRecordPage() {
  const { recordGoldenMerge } = useInnovationStore();
  const [clusters, setClusters] = useState<IdentityCluster[]>(SEED_CLUSTERS);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const drawer = clusters.find((c) => c.id === drawerId) ?? null;

  const mergeCluster = (id: string) => {
    setClusters((prev) => prev.map((c) => {
      if (c.id !== id) return c;
      recordGoldenMerge({
        clusterId: c.id,
        entityName: c.records[0]?.accountId ?? c.id,
        entityType: c.entityType,
        confidence: c.overallConfidence,
        sourcesUnified: c.records.length,
        mergedAt: '2026-05-05T03:55:00Z',
      });
      return { ...c, mergeStatus: 'merged' as const };
    }));
    setDrawerId(null);
  };

  const dismiss = (id: string) => {
    setClusters((prev) => prev.map((c) => c.id === id ? { ...c, mergeStatus: 'dismissed' as const } : c));
    setDrawerId(null);
  };

  const totalClusters = clusters.length;
  const mergedCount = clusters.filter((c) => c.mergeStatus === 'merged').length;
  const pendingCount = clusters.filter((c) => c.mergeStatus === 'pending').length;
  const avgConfidence = clusters.reduce((s, c) => s + c.overallConfidence, 0) / Math.max(1, totalClusters);
  const totalSourcesUnified = clusters.reduce((s, c) => s + c.records.length, 0);

  return (
    <div>
      <FabricHeader
        eyebrow="INNOVATION · 04 / 10"
        title="Golden Record · Cross-Source Identity Unification"
        blurb="The Mapper fuses entity records across CRM, warehouse, support, billing, and marketing into a single golden record per organisation — purely organisational identifiers (account IDs, registration numbers, tickers, regions). No personal identifiers in seed data; this surface deals only with org-level identity. Merges propagate into mapping behavior."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3.5 h-3.5" /> Innovation index
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <FabricStat label="Identity clusters" value={totalClusters} tone="gold" />
        <FabricStat label="Merged" value={mergedCount} tone="good" />
        <FabricStat label="Pending review" value={pendingCount} tone="warn" />
        <FabricStat label="Sources unified" value={totalSourcesUnified} />
        <FabricStat label="Avg confidence" value={`${Math.round(avgConfidence * 100)}%`} tone="gold" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        {clusters.map((c) => (
          <button key={c.id} onClick={() => setDrawerId(c.id)} className="conduit-card p-4 text-left">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-[#c9b787]" />
                <div>
                  <div className="text-[#f5f5f5] text-sm font-medium font-mono">{c.records[0]?.accountId}</div>
                  <div className="text-[11px] text-[#666] mt-0.5">{c.entityType} · {c.records.length} sources · ticker {c.records[0]?.ticker}</div>
                </div>
              </div>
              {c.mergeStatus === 'merged' ? <Badge variant="success">merged</Badge> :
                c.mergeStatus === 'dismissed' ? <Badge variant="default">dismissed</Badge> :
                <Badge variant="partial">pending</Badge>}
            </div>
            <div className="space-y-1.5 mt-3">
              <div className="flex items-center justify-between text-[11px]"><span className="text-[#8a8a8a]">overall confidence</span><span className="font-mono tabular-nums text-[#c9b787]">{(c.overallConfidence * 100).toFixed(0)}%</span></div>
              <MicroBar value={c.overallConfidence * 100} max={100} tone={c.overallConfidence >= 0.9 ? 'good' : c.overallConfidence >= 0.75 ? 'gold' : 'warn'} />
            </div>
            {c.conflictFields.length > 0 && (
              <div className="mt-2 flex items-center gap-1.5 text-[10px] text-[#d4a853]">
                <AlertTriangle className="w-3 h-3" />
                <span>{c.conflictFields.length} conflict field(s): {c.conflictFields.join(', ')}</span>
              </div>
            )}
          </button>
        ))}
      </div>

      <FabricDrawer
        open={!!drawer}
        onClose={() => setDrawerId(null)}
        title={drawer ? `${drawer.records[0]?.accountId} · ${drawer.entityType}` : ''}
        subtitle={drawer ? `${drawer.records.length} sources · ${(drawer.overallConfidence * 100).toFixed(0)}% confidence` : ''}
      >
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Sources" value={drawer.records.length} tone="gold" />
              <FabricStat label="Confidence" value={`${(drawer.overallConfidence * 100).toFixed(0)}%`} tone={drawer.overallConfidence >= 0.9 ? 'good' : 'warn'} />
              <FabricStat label="Conflicts" value={drawer.conflictFields.length} tone={drawer.conflictFields.length > 0 ? 'warn' : 'good'} />
              <FabricStat label="Status" value={drawer.mergeStatus} tone={drawer.mergeStatus === 'merged' ? 'good' : 'neutral'} />
            </div>
            <FabricCard title="GOLDEN RECORD (RESOLVED)" trailing={<GovernanceDot state="green" />}>
              <div className="space-y-2">
                {Object.entries(drawer.resolvedFields).map(([field, { value, sourceIdx }]) => (
                  <div key={field} className="flex items-center justify-between text-[12px] py-1.5 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                    <span className="font-mono text-[#8a8a8a]">{FIELD_LABELS[field] ?? field}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[#f5f5f5]">{value}</span>
                      <Badge variant="default">{drawer.records[sourceIdx]?.source}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </FabricCard>
            <FabricCard title="SOURCE RECORDS">
              <div className="space-y-3">
                {drawer.records.map((r, i) => (
                  <div key={i} className="p-3 rounded bg-[#0e0e0e] border border-[rgba(255,255,255,0.04)]">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="active">{r.source}</Badge>
                        <span className="font-mono text-[10px] text-[#666]">{r.entityId}</span>
                      </div>
                      <span className="font-mono text-[11px] text-[#c9b787]">{(r.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                      <div><span className="text-[#666]">account </span><span className="font-mono text-[#8a8a8a]">{r.accountId}</span></div>
                      <div><span className="text-[#666]">reg# </span><span className="font-mono text-[#8a8a8a]">{r.registrationNumber}</span></div>
                      <div><span className="text-[#666]">ticker </span><span className="font-mono text-[#8a8a8a]">{r.ticker}</span></div>
                      <div><span className="text-[#666]">region </span><span className="font-mono text-[#8a8a8a]">{r.region}</span></div>
                      <div className="col-span-2"><span className="text-[#666]">last seen </span><span className="font-mono text-[#8a8a8a]">{r.lastSeen}</span></div>
                      {Object.entries(r.fields).slice(0, 4).map(([k, v]) => (
                        <div key={k}><span className="text-[#666]">{k} </span><span className="font-mono text-[#8a8a8a]">{v}</span></div>
                      ))}
                    </div>
                    {drawer.conflictFields.some((f) => getRecordField(r, f) !== drawer.resolvedFields[f]?.value) && (
                      <div className="mt-2 text-[10px] text-[#d4a853]">⚠ differs on resolved field(s)</div>
                    )}
                  </div>
                ))}
              </div>
            </FabricCard>
            {drawer.mergeStatus === 'pending' && (
              <div className="flex gap-2">
                <Button onClick={() => mergeCluster(drawer.id)} className="flex-1"><GitMerge className="w-3.5 h-3.5 mr-1.5" />Merge into golden record</Button>
                <Button onClick={() => dismiss(drawer.id)} variant="ghost">Dismiss</Button>
              </div>
            )}
            {drawer.mergeStatus === 'merged' && (
              <div className="flex items-center gap-2 text-[12px] text-[#5a8a6e]"><CheckCircle className="w-4 h-4" />Golden record committed · downstream mappings updated</div>
            )}
          </>
        )}
      </FabricDrawer>

      <div className="conduit-card p-4 mt-6">
        <div className="flex items-center gap-2 mb-2"><Merge className="w-4 h-4 text-[#c9b787]" /><span className="label-mono">FORMULA · Identity confidence</span></div>
        <pre className="font-mono text-[11px] text-[#f5f5f5] bg-[#0a0a0a] p-3 rounded overflow-x-auto">{`overall_confidence(cluster) = avg(record.confidence) × source_diversity_bonus
source_diversity_bonus = 1 + 0.05 × min(4, distinct_source_kinds(cluster))
conflict_penalty(field) = 1 - (0.1 × distinct_values(field) / records.length)
merge_eligible iff overall_confidence ≥ 0.85 ∧ no_critical_conflicts`}</pre>
      </div>
    </div>
  );
}
