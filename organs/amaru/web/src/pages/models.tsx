import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { RELAY_MODELS, RELAY_SOURCES, RELAY_DESTINATIONS, RELAY_MAPPINGS } from '@/data/fabric';
import type { RelayModel } from '@/data/fabric/types';
import { calculateActivationReadiness, classifyPiiRisk } from '@/lib/agentic';
import { FabricHeader, FabricStat, FabricToolbar, FabricDrawer, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Input, Select, Badge } from '@/components/ui';
import { Zap } from 'lucide-react';

export default function ModelsPage() {
  const [q, setQ] = useState('');
  const [vertical, setVertical] = useState('');
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [readinessMin, setReadinessMin] = useState(0);
  const [sortBy, setSortBy] = useState<'readiness' | 'quality' | 'name' | 'pii'>('readiness');

  const rows = useMemo(() => {
    const filtered = RELAY_MODELS.filter((m) => {
      if (q && !m.name.toLowerCase().includes(q.toLowerCase())) return false;
      if (vertical && m.verticalId !== vertical) return false;
      if (m.activationReadiness < readinessMin) return false;
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sortBy === 'quality') return b.qualityScore - a.qualityScore;
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'pii') return b.piiFieldCount - a.piiFieldCount;
      return b.activationReadiness - a.activationReadiness;
    });
  }, [q, vertical, readinessMin, sortBy]);

  const drawer = drawerId ? RELAY_MODELS.find((m) => m.id === drawerId)! : null;
  const drawerSource = drawer ? RELAY_SOURCES.find((s) => s.id === drawer.sourceId) : null;
  const drawerMappings = drawer ? RELAY_MAPPINGS.filter((mp) => mp.modelId === drawer.id) : [];

  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 02"
        title="Models"
        blurb="Composed entities the business actually uses. Each model is sourced, typed, scored, and replay-grade — its anchor hash is the witness the rest of the fabric trusts."
        trailing={
          <Link href="/innovation/audience-sql" className="flex items-center gap-1.5 text-[11px] font-mono text-[#c9b787] hover:underline">
            <Zap className="w-3.5 h-3.5" /> Audience SQL Studio →
          </Link>
        }
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Models" value={RELAY_MODELS.length} tone="gold" />
        <FabricStat label="PII-bearing" value={RELAY_MODELS.filter((m) => m.piiFieldCount > 0).length} tone="warn" />
        <FabricStat label="Avg readiness" value={Math.round(RELAY_MODELS.reduce((s, m) => s + m.activationReadiness, 0) / RELAY_MODELS.length)} tone="good" />
        <FabricStat label="Verticals covered" value={new Set(RELAY_MODELS.map((m) => m.verticalId)).size} />
      </div>

      <FabricToolbar>
        <Input placeholder="Search models…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={vertical} onChange={(e) => setVertical(e.target.value)} className="max-w-xs">
          <option value="">All verticals</option>
          {Array.from(new Set(RELAY_MODELS.map((m) => m.verticalId))).map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </Select>
        <div className="flex items-center gap-2 text-[12px] text-[#8a8a8a]">
          <span className="label-mono">readiness ≥</span>
          <input type="range" min={0} max={100} step={5} value={readinessMin} onChange={(e) => setReadinessMin(Number(e.target.value))} className="accent-[#c9b787]" />
          <span className="font-mono tabular-nums w-8 text-right">{readinessMin}</span>
        </div>
        <Select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="max-w-xs">
          <option value="readiness">Sort: Readiness ↓</option>
          <option value="quality">Sort: Quality ↓</option>
          <option value="pii">Sort: PII fields ↓</option>
          <option value="name">Sort: Name</option>
        </Select>
      </FabricToolbar>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {rows.map((m: RelayModel) => (
          <button
            key={m.id}
            onClick={() => setDrawerId(m.id)}
            className="conduit-card p-4 text-left"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <div className="font-mono text-[#f5f5f5] text-sm">{m.name}</div>
                <div className="text-[11px] text-[#666] mt-0.5">{m.entityType} · {m.fieldCount} fields</div>
              </div>
              <GovernanceDot state={m.governanceState} />
            </div>
            <div className="space-y-1.5 mt-3">
              <div className="flex items-center justify-between text-[11px] text-[#8a8a8a]"><span>readiness</span><span className="font-mono tabular-nums text-[#c9b787]">{m.activationReadiness}</span></div>
              <MicroBar value={m.activationReadiness} max={100} tone={m.activationReadiness >= 85 ? 'good' : m.activationReadiness >= 70 ? 'warn' : 'bad'} />
              <div className="flex items-center justify-between text-[11px] text-[#8a8a8a]"><span>quality</span><span className="font-mono tabular-nums">{m.qualityScore}</span></div>
              <MicroBar value={m.qualityScore} max={100} tone={m.qualityScore >= 85 ? 'good' : 'warn'} />
            </div>
            <div className="flex items-center gap-1 mt-3">
              <Badge variant="default">{m.verticalId}</Badge>
              {m.piiFieldCount > 0 && <Badge variant="partial">{m.piiFieldCount} PII</Badge>}
            </div>
          </button>
        ))}
      </div>

      <FabricDrawer
        open={!!drawer}
        onClose={() => setDrawerId(null)}
        title={drawer?.name ?? ''}
        subtitle={drawer ? `${drawer.entityType} · source ${drawerSource?.name ?? '—'}` : ''}
      >
        {drawer && drawerSource && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <FabricStat label="Activation readiness" value={drawer.activationReadiness} tone="gold" />
              <FabricStat label="Fields" value={drawer.fieldCount} />
              <FabricStat label="Quality" value={drawer.qualityScore} tone={drawer.qualityScore >= 85 ? 'good' : 'warn'} />
              <FabricStat label="PII fields" value={drawer.piiFieldCount} tone={drawer.piiFieldCount > 4 ? 'warn' : 'neutral'} />
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">SQL PREVIEW</div>
              <pre className="font-mono text-[11px] text-[#f5f5f5] bg-[#0a0a0a] p-3 rounded overflow-x-auto">{drawer.sqlPreview}</pre>
            </div>
            <div className="conduit-card p-4">
              <div className="label-mono mb-2 text-[#c9b787]">FIELDS</div>
              <div className="space-y-1">
                {drawer.fields.map((f) => (
                  <div key={f.name} className="flex items-center justify-between text-[12px] py-1 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                    <div>
                      <span className="font-mono text-[#f5f5f5]">{f.name}</span>
                      <span className="text-[#666] ml-2">{f.type}{f.nullable ? '?' : ''}</span>
                    </div>
                    {f.piiClass !== 'none' && <Badge variant="partial">{f.piiClass}</Badge>}
                  </div>
                ))}
              </div>
            </div>
            {drawerMappings.length > 0 && (
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-[#c9b787]">DESTINATION MAPPINGS</div>
                <div className="space-y-2">
                  {drawerMappings.map((mp) => {
                    const dst = RELAY_DESTINATIONS.find((d) => d.id === mp.destinationId)!;
                    const ready = calculateActivationReadiness(drawer, dst, mp);
                    const risk = classifyPiiRisk(drawer, dst);
                    return (
                      <div key={mp.id} className="flex items-center justify-between text-[12px] p-2 rounded bg-[#0e0e0e]">
                        <div>
                          <div className="text-[#f5f5f5]">{dst.name}</div>
                          <div className="text-[10px] text-[#666]">{ready.bandLabel} · pii {risk.tier}</div>
                        </div>
                        <span className="font-mono tabular-nums text-[#c9b787]">{ready.score}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </FabricDrawer>
    </div>
  );
}
