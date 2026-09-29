import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_POLICIES } from '@/data/fabric';
import { groupPoliciesBySeverity } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, GovernanceDot, SeverityChip } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { useInnovationStore } from '@/lib/innovation-store';
import { Code } from 'lucide-react';

export default function PoliciesPage() {
  const { dslVersions, dslActiveRuleCount } = useInnovationStore();
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const rows = useMemo(() => {
    return RELAY_POLICIES.filter((p) => {
      if (q && !p.name.toLowerCase().includes(q.toLowerCase()) && !p.condition.toLowerCase().includes(q.toLowerCase())) return false;
      if (kind && p.kind !== kind) return false;
      return true;
    });
  }, [q, kind]);

  const grouped = groupPoliciesBySeverity(RELAY_POLICIES);
  const drawer = drawerId ? RELAY_POLICIES.find((p) => p.id === drawerId)! : null;

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 05"
        title="Policies"
        blurb="The registry Sentinel evaluates against every batch. Each rule is a condition, an enforcement action, a Lutar weight, and a recent-hit log — the spine never ships unless this registry says it can."
        trailing={
          <Link href="/innovation/policy-dsl" className="flex items-center gap-1.5 text-[11px] font-mono text-link hover:underline">
            <Code className="w-3.5 h-3.5" /> Policy DSL →
          </Link>
        }
      />
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
        <FabricStat label="Policies" value={RELAY_POLICIES.length} tone="gold" />
        <FabricStat label="Critical" value={grouped.critical.length} tone="bad" />
        <FabricStat label="High" value={grouped.high.length} tone="warn" />
        <FabricStat label="Medium" value={grouped.medium.length} />
        <FabricStat label="Low / info" value={grouped.low.length + grouped.info.length} />
        <FabricStat label="DSL versions" value={dslVersions.length} tone={dslVersions.length > 0 ? 'good' : 'neutral'} sub={dslActiveRuleCount > 0 ? `${dslActiveRuleCount} active rules` : undefined} />
      </div>
      {dslVersions.length > 0 && (
        <div className="mb-4 p-3 rounded text-[12px] flex items-center justify-between" style={{ background: 'color-mix(in srgb, var(--text) 4%, transparent)', border: '1px solid color-mix(in srgb, var(--text) 15%, transparent)' }}>
          <div className="flex items-center gap-2">
            <Code className="w-3.5 h-3.5 text-ink" />
            <span className="text-ink">Latest DSL version</span>
            <span className="font-mono text-ink">v{dslVersions[0]!.version}</span>
            <span className="text-ink-sub">— {dslVersions[0]!.description}</span>
            <span className="text-ink-sub font-mono">({dslVersions[0]!.ruleCount} rules)</span>
          </div>
          <Link href="/innovation/policy-dsl" className="text-[11px] text-link hover:underline">Edit DSL →</Link>
        </div>
      )}

      <FabricToolbar>
        <Input placeholder="Search policies / conditions…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={kind} onChange={(e) => setKind(e.target.value)} className="max-w-xs">
          <option value="">All kinds</option>
          {Array.from(new Set(RELAY_POLICIES.map((p) => p.kind))).map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </Select>
      </FabricToolbar>

      <div className="space-y-2">
        {rows.map((p) => (
          <button key={p.id} onClick={() => setDrawerId(p.id)} className="conduit-card p-4 text-left w-full">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <SeverityChip level={p.severity} />
                <div className="min-w-0">
                  <div className="text-sm text-ink truncate">{p.name}</div>
                  <div className="font-mono text-[11px] text-ink-sub truncate">{p.condition}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <Badge variant={p.enforcement === 'block' || p.enforcement === 'rollback' ? 'failed' : p.enforcement === 'require_approval' ? 'partial' : 'default'}>{p.enforcement}</Badge>
                <span className="text-[11px] text-ink-sub font-mono">{p.recentHits.length} hits</span>
                <GovernanceDot state={p.governanceState} />
              </div>
            </div>
          </button>
        ))}
      </div>

      <FabricDrawer open={!!drawer} onClose={() => setDrawerId(null)} title={drawer?.name ?? ''} subtitle={drawer?.kind}>
        {drawer && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Severity" value={drawer.severity.toUpperCase()} tone={drawer.severity === 'critical' ? 'bad' : drawer.severity === 'high' ? 'warn' : 'neutral'} />
              <FabricStat label="Enforcement" value={drawer.enforcement} tone="gold" />
              <FabricStat label="Lutar weight" value={`${drawer.lutarWeight.num}/${drawer.lutarWeight.den}`} />
              <FabricStat label="Recent hits" value={drawer.recentHits.length} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-ink">CONDITION</div>
              <pre className="font-mono text-[11px] text-ink bg-ground p-3 rounded overflow-x-auto whitespace-pre-wrap">{drawer.condition}</pre>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-ink">SCOPE</div>
              <div className="flex flex-wrap gap-1">
                {drawer.scope.map((v) => <Badge key={v} variant="default">{v}</Badge>)}
              </div>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-ink">RECENT HITS</div>
              {drawer.recentHits.length === 0 && <div className="text-[12px] text-ink-sub">No recent hits.</div>}
              <div className="space-y-2">
                {drawer.recentHits.map((h, i) => (
                  <div key={i} className="text-[11px] p-2 rounded bg-ground-deep">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-ink-sub">{h.syncId}</span>
                      <Badge variant={h.outcome === 'block' ? 'failed' : h.outcome === 'rollback' ? 'failed' : h.outcome === 'require_approval' ? 'partial' : 'default'}>{h.outcome}</Badge>
                    </div>
                    <div className="text-ink mt-1">{h.summary}</div>
                    <div className="text-ink-sub mt-1">{new Date(h.atIso).toLocaleString()}</div>
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
