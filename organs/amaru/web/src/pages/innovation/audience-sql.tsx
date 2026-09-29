import { useState, useMemo } from 'react';
import { Link } from 'wouter';
import { RELAY_MODELS, RELAY_DESTINATIONS, RELAY_POLICIES } from '@/data/fabric';
import { useInnovationStore } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, FabricDrawer, GovernanceDot, MicroBar } from '@/components/fabric/primitives';
import { Badge, Button, Select } from '@/components/ui';
import { Play, Shield, ChevronRight, CheckCircle, AlertTriangle, XCircle, ArrowLeft } from 'lucide-react';

type PiiClass = 'none' | 'email' | 'phone' | 'name' | 'address' | 'gov_id' | 'financial' | 'health';

const PII_SEVERITY: Record<PiiClass, number> = { none: 0, name: 1, address: 2, email: 2, phone: 2, financial: 3, gov_id: 4, health: 4 };

interface AudienceRecord {
  readonly id: string;
  readonly name: string;
  readonly modelId: string;
  readonly sql: string;
  readonly estimatedRows: number;
  readonly destinationId: string;
  readonly piiGateResult: 'pass' | 'warn' | 'block';
  readonly createdAt: string;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}

function estimateRows(modelId: string, sql: string): number {
  const base = fnv1a(`rows:${modelId}:${sql.length}`) % 48000 + 2000;
  return base - (base % 100);
}

const PRESET_QUERIES: readonly { label: string; sql: string }[] = [
  { label: 'High-value churned accounts', sql: "SELECT id, legal_name, billing_email, mrr_cents, arr_cents\nFROM lyte.account\nWHERE plan_tier = 'enterprise'\n  AND renewal_at < NOW() + INTERVAL '30 days'\nORDER BY arr_cents DESC" },
  { label: 'Voyage contacts needing outreach', sql: "SELECT c.id, c.full_name, c.email, c.port_code\nFROM vessels.port_contact c\nWHERE c.last_contacted_at < NOW() - INTERVAL '60 days'\n  AND c.voyage_count_ytd > 5" },
  { label: 'High-risk open matters', sql: "SELECT m.id, m.title, m.client_name, m.practice_area, m.risk_level\nFROM counsel.active_matter m\nWHERE m.risk_level = 'high'\n  AND m.days_open > 45" },
  { label: 'Terra inspections due soon', sql: "SELECT a.id, a.parcel_id, a.address, a.inspection_due_at\nFROM terra.property_asset a\nWHERE a.inspection_due_at BETWEEN NOW() AND NOW() + INTERVAL '14 days'" },
];

export default function AudienceSqlPage() {
  const { audiences: storeAudiences, addAudience } = useInnovationStore();
  const [selectedModelId, setSelectedModelId] = useState(RELAY_MODELS[0]?.id ?? '');
  const [sql, setSql] = useState(PRESET_QUERIES[0]!.sql);
  const [selectedDestId, setSelectedDestId] = useState(RELAY_DESTINATIONS[0]?.id ?? '');
  const [previewRun, setPreviewRun] = useState<{ rows: number; piiResult: 'pass' | 'warn' | 'block'; compat: boolean } | null>(null);
  const audiences = storeAudiences as readonly AudienceRecord[];
  const [drawerAudience, setDrawerAudience] = useState<AudienceRecord | null>(null);
  const [audienceName, setAudienceName] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  const selectedModel = useMemo(() => RELAY_MODELS.find((m) => m.id === selectedModelId), [selectedModelId]);
  const selectedDest = useMemo(() => RELAY_DESTINATIONS.find((d) => d.id === selectedDestId), [selectedDestId]);

  const piiFields = useMemo(() => {
    if (!selectedModel) return [];
    return selectedModel.fields.filter((f) => f.piiClass !== 'none');
  }, [selectedModel]);

  const maxPiiSeverity = useMemo(() => {
    return piiFields.reduce((max, f) => Math.max(max, PII_SEVERITY[f.piiClass]), 0);
  }, [piiFields]);

  const destCompatMatrix = useMemo(() => {
    if (!selectedModel) return [];
    return RELAY_DESTINATIONS.slice(0, 12).map((d) => {
      const entityMatch = d.supportedEntityTypes.includes(selectedModel.entityType);
      const piiOk = !piiFields.length || d.piiAllowed;
      const compat = entityMatch && (piiOk || maxPiiSeverity === 0);
      return { dest: d, entityMatch, piiOk, compat };
    });
  }, [selectedModel, piiFields, maxPiiSeverity]);

  const runPreview = () => {
    if (!selectedModel || !selectedDest) return;
    setPreviewLoading(true);
    setTimeout(() => {
      const rows = estimateRows(selectedModelId, sql);
      const piiResult: 'pass' | 'warn' | 'block' =
        maxPiiSeverity >= 4 && !selectedDest.piiAllowed ? 'block' :
        maxPiiSeverity >= 2 && !selectedDest.piiAllowed ? 'warn' :
        'pass';
      const compat = selectedDest.supportedEntityTypes.includes(selectedModel.entityType);
      setPreviewRun({ rows, piiResult, compat });
      setPreviewLoading(false);
    }, 600);
  };

  const buildAudience = () => {
    if (!previewRun || !selectedModel || !selectedDest) return;
    const name = audienceName.trim() || `Audience ${audiences.length + 1}`;
    addAudience({
      id: `aud-${fnv1a(`${name}:${selectedModelId}:${audiences.length}`).toString(16).slice(0, 8)}`,
      name,
      modelId: selectedModelId,
      modelName: selectedModel.name,
      sql,
      estimatedRows: previewRun.rows,
      destinationId: selectedDestId,
      destinationName: selectedDest.name,
      piiGateResult: previewRun.piiResult,
      createdAt: '2026-05-05T03:55:00Z',
    });
    setAudienceName('');
  };

  const policyCount = useMemo(() =>
    RELAY_POLICIES.filter((p) => selectedModel && p.scope.includes(selectedModel.verticalId)).length,
    [selectedModel]
  );

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 01"
        title="Audience SQL Studio"
        blurb="Define activation audiences over models using SQL or visual presets. Live row-count preview before any data moves. PII gate overlay shows which fields are blocked. Destination compatibility matrix shows where this audience can land."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-link hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Available models" value={RELAY_MODELS.length} tone="gold" />
        <FabricStat label="PII fields detected" value={piiFields.length} tone={piiFields.length > 3 ? 'warn' : 'neutral'} />
        <FabricStat label="Active policies" value={policyCount} />
        <FabricStat label="Audiences built" value={audiences.length} tone="good" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="space-y-4">
          <FabricCard title="SQL EDITOR">
            <div className="space-y-3">
              <div className="flex gap-2">
                <Select value={selectedModelId} onChange={(e) => { setSelectedModelId(e.target.value); setPreviewRun(null); }} className="flex-1">
                  {RELAY_MODELS.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.entityType})</option>)}
                </Select>
              </div>
              <div className="flex flex-wrap gap-1 pb-1">
                {PRESET_QUERIES.map((pq) => (
                  <button key={pq.label} onClick={() => { setSql(pq.sql); setPreviewRun(null); }} className="text-[10px] font-mono px-2 py-0.5 rounded border border-line-subtle text-ink hover:bg-wash/8 transition-colors">
                    {pq.label}
                  </button>
                ))}
              </div>
              <textarea
                value={sql}
                onChange={(e) => { setSql(e.target.value); setPreviewRun(null); }}
                rows={8}
                className="w-full font-mono text-[12px] bg-ground text-ink border border-line rounded-lg p-3 resize-y focus-visible:outline-none focus-visible:border-focus focus-visible:shadow-[var(--shadow-focus)]"
                spellCheck={false}
              />
              <div className="flex gap-2">
                <Select value={selectedDestId} onChange={(e) => { setSelectedDestId(e.target.value); setPreviewRun(null); }} className="flex-1">
                  {RELAY_DESTINATIONS.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </Select>
                <Button onClick={runPreview} isLoading={previewLoading} disabled={!sql.trim()}>
                  <Play className="w-3.5 h-3.5 mr-1.5" /> Preview
                </Button>
              </div>
            </div>
          </FabricCard>

          {previewRun && (
            <FabricCard title="PREVIEW RESULT" className="animate-scale-in">
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="conduit-stat p-3">
                  <div className="label-mono mb-1">Est. Rows</div>
                  <div className="text-xl font-semibold text-ink tabular-nums">{previewRun.rows.toLocaleString()}</div>
                </div>
                <div className="conduit-stat p-3">
                  <div className="label-mono mb-1">PII Gate</div>
                  <div className={`text-sm font-medium flex items-center gap-1 mt-1 ${previewRun.piiResult === 'pass' ? 'text-ink-good' : previewRun.piiResult === 'warn' ? 'text-ink-warn' : 'text-ink-bad'}`}>
                    {previewRun.piiResult === 'pass' ? <CheckCircle className="w-4 h-4" /> : previewRun.piiResult === 'warn' ? <AlertTriangle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {previewRun.piiResult.toUpperCase()}
                  </div>
                </div>
                <div className="conduit-stat p-3">
                  <div className="label-mono mb-1">Dest Compat</div>
                  <div className={`text-sm font-medium flex items-center gap-1 mt-1 ${previewRun.compat ? 'text-ink-good' : 'text-ink-bad'}`}>
                    {previewRun.compat ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {previewRun.compat ? 'Compatible' : 'Mismatch'}
                  </div>
                </div>
              </div>
              {previewRun.piiResult !== 'pass' && (
                <div className="mb-3 p-2 rounded text-[11px]" style={{ background: 'color-mix(in srgb, var(--color-warning) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning) 20%, transparent)' }}>
                  <Shield className="inline w-3 h-3 text-ink-warn mr-1" />
                  <span className="text-ink-warn">PII warning:</span> <span className="text-ink-sub">model contains PII fields ({piiFields.map((f) => f.piiClass).join(', ')}) and destination {selectedDest?.piiAllowed ? 'allows PII with redaction' : 'does not permit PII'}. Sentinel will apply redaction transforms.</span>
                </div>
              )}
              {previewRun.compat && previewRun.piiResult !== 'block' && (
                <div className="flex gap-2">
                  <input
                    value={audienceName}
                    onChange={(e) => setAudienceName(e.target.value)}
                    placeholder="Audience name…"
                    className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 text-sm"
                  />
                  <Button size="sm" variant="outline" onClick={buildAudience}>Build audience →</Button>
                </div>
              )}
            </FabricCard>
          )}
        </div>

        <div className="space-y-4">
          <FabricCard title="PII GATE OVERLAY">
            {selectedModel ? (
              <div className="space-y-2">
                <div className="text-[11px] text-ink-sub mb-2">Fields in <span className="text-ink font-mono">{selectedModel.name}</span> — {selectedModel.fieldCount} total</div>
                {selectedModel.fields.map((f) => (
                  <div key={f.name} className="flex items-center justify-between py-1 border-b border-line-subtle last:border-0 text-[12px]">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${f.piiClass !== 'none' ? 'bg-warning' : 'bg-success'}`} />
                      <span className="font-mono text-ink truncate">{f.name}</span>
                      <span className="text-ink-sub">{f.type}{f.nullable ? '?' : ''}</span>
                    </div>
                    {f.piiClass !== 'none' ? (
                      <Badge variant="partial">{f.piiClass}</Badge>
                    ) : (
                      <span className="text-[10px] text-ink-good font-mono">safe</span>
                    )}
                  </div>
                ))}
              </div>
            ) : <div className="text-[12px] text-ink-sub">Select a model above.</div>}
          </FabricCard>

          <FabricCard title="DESTINATION COMPATIBILITY MATRIX">
            <div className="space-y-1.5">
              {destCompatMatrix.map(({ dest, entityMatch, piiOk, compat }) => (
                <div key={dest.id} className="flex items-center gap-3 text-[11px] py-1">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dest.accent }} />
                  <span className="text-ink truncate w-36">{dest.name}</span>
                  <div className="flex-1">
                    <MicroBar value={dest.fieldContractStrength * 100} max={100} tone={compat ? 'good' : 'bad'} />
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <span className={`text-[10px] font-mono px-1 py-0.5 rounded ${entityMatch ? 'text-ink-good' : 'text-ink-bad'}`}>{entityMatch ? '✓ entity' : '✕ entity'}</span>
                    <span className={`text-[10px] font-mono px-1 py-0.5 rounded ${piiOk ? 'text-ink-good' : 'text-ink-warn'}`}>{piiOk ? '✓ pii' : 'pii · review'}</span>
                  </div>
                  <GovernanceDot state={dest.governanceState} />
                </div>
              ))}
            </div>
          </FabricCard>
        </div>
      </div>

      {audiences.length > 0 && (
        <FabricCard title={`AUDIENCES BUILT (${audiences.length})`} className="mb-6">
          <div className="space-y-2">
            {audiences.map((aud) => {
              const model = RELAY_MODELS.find((m) => m.id === aud.modelId);
              const dest = RELAY_DESTINATIONS.find((d) => d.id === aud.destinationId);
              return (
                <button key={aud.id} onClick={() => setDrawerAudience(aud)} className="conduit-card p-3 text-left w-full">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div>
                        <div className="text-ink text-[13px] font-medium">{aud.name}</div>
                        <div className="text-[11px] text-ink-sub font-mono">{model?.name ?? aud.modelId} → {dest?.name ?? aud.destinationId}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="font-mono tabular-nums text-ink text-[12px]">{aud.estimatedRows.toLocaleString()} rows</span>
                      <Badge variant={aud.piiGateResult === 'pass' ? 'success' : aud.piiGateResult === 'warn' ? 'partial' : 'failed'}>{aud.piiGateResult}</Badge>
                      <ChevronRight className="w-4 h-4 text-ink-sub" />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </FabricCard>
      )}

      <FabricDrawer open={!!drawerAudience} onClose={() => setDrawerAudience(null)} title={drawerAudience?.name ?? ''} subtitle={`${drawerAudience?.estimatedRows.toLocaleString()} estimated rows`}>
        {drawerAudience && (() => {
          const model = RELAY_MODELS.find((m) => m.id === drawerAudience.modelId);
          const dest = RELAY_DESTINATIONS.find((d) => d.id === drawerAudience.destinationId);
          return (
            <>
              <div className="grid grid-cols-2 gap-3">
                <FabricStat label="Est. rows" value={drawerAudience.estimatedRows.toLocaleString()} tone="gold" />
                <FabricStat label="PII gate" value={drawerAudience.piiGateResult.toUpperCase()} tone={drawerAudience.piiGateResult === 'pass' ? 'good' : drawerAudience.piiGateResult === 'warn' ? 'warn' : 'bad'} />
              </div>
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-ink">SOURCE MODEL</div>
                <div className="text-[12px] text-ink">{model?.name ?? drawerAudience.modelId}</div>
                <Link href="/models" className="text-[10px] text-link hover:underline mt-1 block">View in Models →</Link>
              </div>
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-ink">DESTINATION</div>
                <div className="flex items-center gap-2">
                  {dest && <span className="w-2 h-2 rounded-full" style={{ background: dest.accent }} />}
                  <div className="text-[12px] text-ink">{dest?.name ?? drawerAudience.destinationId}</div>
                  <GovernanceDot state={dest?.governanceState ?? 'amber'} />
                </div>
              </div>
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-ink">SQL</div>
                <pre className="font-mono text-[11px] text-ink bg-ground p-3 rounded overflow-x-auto whitespace-pre-wrap">{drawerAudience.sql}</pre>
              </div>
              <div className="conduit-card p-4">
                <div className="label-mono mb-2 text-ink">EVIDENCE REF</div>
                <div className="font-mono text-[11px] text-ink-sub">evidence/{drawerAudience.id}</div>
              </div>
            </>
          );
        })()}
      </FabricDrawer>
    </div>
  );
}
