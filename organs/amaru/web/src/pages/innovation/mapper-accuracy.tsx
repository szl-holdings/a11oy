import { useState, useMemo, useEffect } from 'react';
import { Link } from 'wouter';
import { RELAY_MAPPINGS } from '@/data/fabric';
import { useInnovationStore } from '@/lib/innovation-store';
import { FabricHeader, FabricCard, FabricStat, MicroBar } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, CheckCircle, XCircle, TrendingUp, TrendingDown, Settings, AlertTriangle } from 'lucide-react';

interface MapperRecommendation {
  readonly id: string;
  readonly mappingId: string;
  readonly mappingName: string;
  readonly sourceField: string;
  readonly destField: string;
  readonly transform: string;
  readonly confidence: number;
  readonly reason: string;
  status: 'pending' | 'accepted' | 'rejected';
}

interface CalibrationHistory {
  readonly window: string;
  readonly recommended: number;
  readonly accepted: number;
  readonly rejected: number;
  readonly calibratedThreshold: number;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}

const TRANSFORMS = ['identity', 'format_date(ISO→MM/DD/YYYY)', 'concat(first_name, last_name)', 'currency_usd_cents→dollars', 'lowercase', 'trim_whitespace', 'enum_map(old→new)', 'hash_sha256', 'truncate_255'];

function buildRecs(mappings: typeof RELAY_MAPPINGS): MapperRecommendation[] {
  const recs: MapperRecommendation[] = [];
  mappings.slice(0, 6).forEach((m, mi) => {
    const count = 2 + (fnv1a(m.id) % 3);
    for (let i = 0; i < count; i++) {
      const seed = fnv1a(`${m.id}:${i}`);
      const conf = 0.62 + (seed % 38) / 100;
      const transformIdx = seed % TRANSFORMS.length;
      const reasons = [
        'Mapper found exact name match across 8 prior activations',
        'Semantic similarity 0.94 from embedding model',
        'Destination contract specifies this field as required',
        'Prior acceptance rate 91% for this field pair',
        'Type compatibility confirmed (string → string)',
        'Low-entropy field — identity transform optimal',
      ];
      recs.push({
        id: `rec-${m.id}-${i}`,
        mappingId: m.id,
        mappingName: m.name,
        sourceField: m.transformations[i % m.transformations.length]?.sourceField ?? `field_${i}`,
        destField: m.transformations[i % m.transformations.length]?.destinationField ?? `dest_field_${i}`,
        transform: TRANSFORMS[transformIdx]!,
        confidence: Math.round(conf * 100) / 100,
        reason: reasons[seed % reasons.length]!,
        status: 'pending',
      });
    }
  });
  return recs;
}

const HISTORY: readonly CalibrationHistory[] = [
  { window: '2026-W14', recommended: 48, accepted: 41, rejected: 7, calibratedThreshold: 0.72 },
  { window: '2026-W15', recommended: 52, accepted: 44, rejected: 8, calibratedThreshold: 0.74 },
  { window: '2026-W16', recommended: 61, accepted: 53, rejected: 8, calibratedThreshold: 0.76 },
  { window: '2026-W17', recommended: 55, accepted: 50, rejected: 5, calibratedThreshold: 0.78 },
  { window: '2026-W18 (current)', recommended: 0, accepted: 0, rejected: 0, calibratedThreshold: 0.80 },
];

export default function MapperAccuracyPage() {
  const { setMapperStats } = useInnovationStore();
  const [recs, setRecs] = useState<MapperRecommendation[]>(() => buildRecs(RELAY_MAPPINGS));
  const [threshold, setThreshold] = useState(0.80);
  const [calibrationApproved, setCalibrationApproved] = useState(false);
  const [proposedThreshold, setProposedThreshold] = useState<number | null>(null);

  const accept = (id: string) => setRecs((prev) => prev.map((r) => r.id === id ? { ...r, status: 'accepted' as const } : r));
  const reject = (id: string) => setRecs((prev) => prev.map((r) => r.id === id ? { ...r, status: 'rejected' as const } : r));
  const acceptAll = () => setRecs((prev) => prev.map((r) => r.status === 'pending' && r.confidence >= threshold ? { ...r, status: 'accepted' as const } : r));

  const accepted = recs.filter((r) => r.status === 'accepted').length;
  const rejected = recs.filter((r) => r.status === 'rejected').length;
  const pending = recs.filter((r) => r.status === 'pending').length;
  const totalDecided = accepted + rejected;
  const acceptRate = totalDecided > 0 ? Math.round(accepted / totalDecided * 100) : null;

  useEffect(() => {
    if (totalDecided > 0) {
      setMapperStats({ totalDecided, accepted, rejected, threshold, updatedAt: '2026-05-05T03:55:00Z' });
    }
  }, [totalDecided, accepted, rejected, threshold, setMapperStats]);

  const aboveThreshold = recs.filter((r) => r.confidence >= threshold);
  const belowThreshold = recs.filter((r) => r.confidence < threshold);

  const calibrationMetrics = useMemo(() => {
    if (totalDecided < 4) return null;
    const overconfident = recs.filter((r) => r.status === 'rejected' && r.confidence >= 0.85).length;
    const underconfident = recs.filter((r) => r.status === 'accepted' && r.confidence < 0.72).length;
    if (overconfident >= 2) return { direction: 'tighten' as const, by: 0.04, reason: `${overconfident} high-confidence recs rejected — Mapper is over-confident above 0.85` };
    if (underconfident >= 2) return { direction: 'loosen' as const, by: 0.04, reason: `${underconfident} low-confidence recs accepted — safe to lower threshold` };
    return { direction: 'stable' as const, by: 0, reason: 'Accept rate within calibration bounds — no adjustment needed' };
  }, [recs, totalDecided]);

  const proposeCalibration = () => {
    if (!calibrationMetrics || calibrationMetrics.direction === 'stable') return;
    const newT = calibrationMetrics.direction === 'tighten' ? threshold + calibrationMetrics.by : threshold - calibrationMetrics.by;
    setProposedThreshold(Math.round(newT * 100) / 100);
  };

  const approveCalibration = () => {
    if (proposedThreshold !== null) {
      setThreshold(proposedThreshold);
      setProposedThreshold(null);
      setCalibrationApproved(true);
    }
  };

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 08"
        title="Mapping Confidence Calibration"
        blurb="Verity tracks Mapper's recommended-vs-accepted ratio over time. Accept or reject field mapping recommendations. Calibration engine surfaces threshold adjustments — operator-approved before any change takes effect."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Recommendations" value={recs.length} tone="gold" />
        <FabricStat label="Accepted" value={accepted} tone="good" />
        <FabricStat label="Rejected" value={rejected} tone={rejected > 0 ? 'warn' : 'neutral'} />
        <FabricStat label="Accept rate" value={acceptRate !== null ? `${acceptRate}%` : '—'} tone={acceptRate !== null && acceptRate >= 80 ? 'good' : 'warn'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <FabricCard title="CALIBRATION HEATMAP">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <div className="label-mono">CURRENT THRESHOLD</div>
              <div className="font-mono text-[#c9b787] text-lg">{threshold.toFixed(2)}</div>
            </div>
            <MicroBar value={threshold * 100} max={100} tone="gold" />
            <div className="flex justify-between text-[10px] font-mono text-[#555] mt-1">
              <span>0.60</span><span>0.80</span><span>1.00</span>
            </div>
          </div>

          <div className="space-y-2 mb-4">
            <div className="label-mono">WEEKLY CALIBRATION HISTORY</div>
            {HISTORY.map((h, i) => {
              const rate = h.recommended > 0 ? Math.round(h.accepted / h.recommended * 100) : null;
              return (
                <div key={h.window} className="flex items-center gap-3 text-[11px] py-1">
                  <span className="font-mono text-[#666] w-24 shrink-0">{h.window.replace('2026-', '')}</span>
                  <div className="flex-1">
                    <MicroBar value={rate ?? 0} max={100} tone={rate !== null && rate >= 85 ? 'good' : rate !== null && rate >= 70 ? 'warn' : 'bad'} />
                  </div>
                  <span className="font-mono text-[#8a8a8a] shrink-0 w-10 text-right">{rate !== null ? `${rate}%` : '—'}</span>
                  <span className="font-mono text-[#555] shrink-0 w-8">{h.calibratedThreshold.toFixed(2)}</span>
                </div>
              );
            })}
          </div>

          {calibrationMetrics && (
            <div className={`p-3 rounded text-[12px] ${calibrationMetrics.direction === 'stable' ? 'text-[#5a8a6e]' : 'text-[#d4a853]'}`} style={{ background: calibrationMetrics.direction === 'stable' ? 'rgba(90,138,110,0.08)' : 'rgba(212,168,83,0.08)', border: `1px solid ${calibrationMetrics.direction === 'stable' ? 'rgba(90,138,110,0.2)' : 'rgba(212,168,83,0.2)'}` }}>
              <div className="flex items-start gap-2">
                {calibrationMetrics.direction === 'stable' ? <CheckCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> : <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
                <div>
                  <div className="font-medium">{calibrationMetrics.direction === 'stable' ? 'Threshold stable' : `Suggest ${calibrationMetrics.direction} by ${calibrationMetrics.by.toFixed(2)}`}</div>
                  <div className="text-[11px] opacity-80 mt-0.5">{calibrationMetrics.reason}</div>
                </div>
              </div>
              {calibrationMetrics.direction !== 'stable' && !proposedThreshold && (
                <Button size="sm" onClick={proposeCalibration} className="mt-2">
                  <Settings className="w-3 h-3 mr-1" /> Propose calibration
                </Button>
              )}
              {proposedThreshold !== null && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[11px]">New threshold: <strong className="font-mono">{proposedThreshold.toFixed(2)}</strong></span>
                  <Button size="sm" onClick={approveCalibration}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => setProposedThreshold(null)}>Cancel</Button>
                </div>
              )}
              {calibrationApproved && <div className="mt-2 text-[11px] text-[#5a8a6e]">✓ Calibration applied at {threshold.toFixed(2)}</div>}
            </div>
          )}
        </FabricCard>

        <FabricCard title="QUICK ACTIONS">
          <div className="space-y-3 mb-4">
            <div className="flex items-center justify-between text-[12px]">
              <span className="text-[#666]">Above threshold ({threshold.toFixed(2)})</span>
              <span className="font-mono text-[#f5f5f5]">{aboveThreshold.length} recs</span>
            </div>
            <div className="flex items-center justify-between text-[12px]">
              <span className="text-[#666]">Below threshold</span>
              <span className="font-mono text-[#d4a853]">{belowThreshold.length} recs</span>
            </div>
            <div className="flex items-center justify-between text-[12px]">
              <span className="text-[#666]">Pending review</span>
              <span className="font-mono text-[#f5f5f5]">{pending}</span>
            </div>
          </div>
          <Button onClick={acceptAll} variant="outline" className="w-full mb-2">
            <CheckCircle className="w-3.5 h-3.5 mr-1.5" /> Accept all above {threshold.toFixed(2)}
          </Button>

          <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.04)]">
            <div className="label-mono mb-2">FIELD PAIR ACCURACY</div>
            {['email → Email', 'name → full_name', 'mrr_cents → revenue', 'plan_tier → tier', 'updated_at → last_modified'].map((pair, i) => {
              const acc = 0.72 + i * 0.05;
              return (
                <div key={pair} className="flex items-center gap-2 text-[11px] py-1">
                  <span className="font-mono text-[#666] flex-1 truncate">{pair}</span>
                  <MicroBar value={acc * 100} max={100} tone={acc >= 0.85 ? 'good' : 'warn'} />
                  <span className="font-mono text-[#8a8a8a] shrink-0 w-8 text-right">{(acc * 100).toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </FabricCard>
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between">
          <div className="label-mono text-[#c9b787]">MAPPER RECOMMENDATIONS ({recs.length})</div>
          <span className="text-[11px] text-[#666]">Click accept ✓ or reject ✗ to calibrate</span>
        </div>
        {recs.map((rec) => (
          <div key={rec.id} className="conduit-card p-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-mono text-[#f5f5f5] text-[12px] truncate">{rec.sourceField} → {rec.destField}</span>
                    <span className="text-[10px] text-[#666] font-mono shrink-0">via {rec.transform.split('(')[0]}</span>
                  </div>
                  <div className="text-[10px] text-[#8a8a8a]">{rec.mappingName} · {rec.reason}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="flex items-center gap-1 mb-0.5">
                    {rec.confidence >= threshold ? <TrendingUp className="w-3 h-3 text-[#5a8a6e]" /> : <TrendingDown className="w-3 h-3 text-[#d4a853]" />}
                    <span className={`font-mono text-sm ${rec.confidence >= threshold ? 'text-[#5a8a6e]' : 'text-[#d4a853]'}`}>{(rec.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="text-[10px] text-[#555]">{rec.confidence >= threshold ? '≥ threshold' : '< threshold'}</div>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {rec.status === 'pending' ? (
                  <>
                    <button onClick={() => accept(rec.id)} className="p-1.5 rounded hover:bg-[rgba(90,138,110,0.15)] text-[#5a8a6e] transition-colors"><CheckCircle className="w-4 h-4" /></button>
                    <button onClick={() => reject(rec.id)} className="p-1.5 rounded hover:bg-[rgba(184,84,80,0.15)] text-[#b85450] transition-colors"><XCircle className="w-4 h-4" /></button>
                  </>
                ) : (
                  <Badge variant={rec.status === 'accepted' ? 'success' : 'failed'}>{rec.status}</Badge>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
