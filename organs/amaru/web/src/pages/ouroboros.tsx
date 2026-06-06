/**
 * Conduit/Amaru Ouroboros — Seked + Unit-Fraction inspection.
 *
 * Demonstrates two RMP primitives applied to Amaru's hardest problems:
 *
 *  1. Seked slope audit (RMP 56–60) — bounded saturation detection.
 *     Conventional dy/dx blows up near a vertical asymptote; the
 *     Egyptian seked is bounded and stable.
 *
 *  2. Unit-fraction decomposition (RMP 2/n table) — turn any threshold
 *     into a sum of distinct unit fractions so it's auditable by a
 *     human and reproducible across heterogeneous runtimes with no
 *     floating-point drift.
 *
 * Wires to /api/ouroboros/amaru/observe-metric and /audit-threshold.
 */
import { useState } from 'react';
import { AmaruReceiptsPanel } from '@/components/AmaruLive';

interface SekedReading {
  seked: number;
  palms: number;
  cubits: number;
  verdict: 'STABLE' | 'RISING' | 'SATURATING' | 'VERTICAL';
}

interface AmaruSignal {
  metricId: string;
  reading: SekedReading;
  degrees: number;
  recommendation: 'CONTINUE' | 'WATCH' | 'THROTTLE' | 'HALT';
  timestamp: number;
}

interface UnitFractionDecomposition {
  numerator: number;
  denominator: number;
  terms: number[];
  exact: boolean;
}

interface ThresholdAudit {
  raw: { p: number; q: number };
  decomposition: UnitFractionDecomposition;
  inspectable: boolean;
  explanation: string;
}

const RECOMMENDATION_COLORS: Record<AmaruSignal['recommendation'], string> = {
  CONTINUE: 'text-[#c9b787] border-[rgba(201,183,135,0.4)] bg-[rgba(201,183,135,0.1)]',
  WATCH:    'text-[#c9b787] border-[rgba(201,183,135,0.3)] bg-[rgba(201,183,135,0.06)]',
  THROTTLE: 'text-[#f5f5f5] border-[rgba(245,245,245,0.25)] bg-[rgba(245,245,245,0.06)]',
  HALT:     'text-[#f5f5f5] border-[rgba(245,245,245,0.4)] bg-[rgba(245,245,245,0.12)]',
};

export default function OuroborosPage() {
  // Seked surface
  const [metricId, setMetricId] = useState('cpu-saturation');
  const [horizontal, setHorizontal] = useState('5');
  const [vertical, setVertical] = useState('10');
  const [signal, setSignal] = useState<AmaruSignal | null>(null);
  const [sekedLoading, setSekedLoading] = useState(false);
  const [sekedError, setSekedError] = useState<string | null>(null);

  // Unit-fraction surface
  const [p, setP] = useState('3');
  const [q, setQ] = useState('7');
  const [audit, setAudit] = useState<ThresholdAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  async function observe() {
    setSekedLoading(true);
    setSekedError(null);
    try {
      const res = await fetch('/api/ouroboros/amaru/observe-metric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metricId,
          horizontal: Number(horizontal),
          vertical: Number(vertical),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSignal(await res.json());
    } catch (e) {
      setSekedError((e as Error).message);
    } finally {
      setSekedLoading(false);
    }
  }

  async function inspect() {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const res = await fetch('/api/ouroboros/amaru/audit-threshold', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ p: Number(p), q: Number(q) }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAudit(await res.json());
    } catch (e) {
      setAuditError((e as Error).message);
    } finally {
      setAuditLoading(false);
    }
  }

  return (
    <div className="space-y-8 animate-fade-in-up">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-[#c9b787]">
            OUROBOROS · RMP 56–60 + 2/n TABLE
          </span>
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
            style={{ backgroundColor: 'rgba(201,183,135,0.06)', color: 'rgba(201,183,135,0.6)', border: '1px solid rgba(201,183,135,0.2)' }}
          >
            Governed by A11oy
          </span>
        </div>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-[#f5f5f5]">
          Seked Audit + Unit-Fraction Thresholds
        </h1>
        <p className="mt-1 text-sm text-[#8a8a8a] max-w-2xl">
          Bounded saturation detection (Egyptian seked, c. 1650 BCE) and
          inspectable threshold decomposition — both primitives free of
          floating-point drift across heterogeneous runtimes, governed by
          A11oy approval tiers.
        </p>
      </div>

      <AmaruReceiptsPanel limit={15} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0e0e0e] p-5">
          <div className="text-sm font-semibold text-[#f5f5f5]">Seked slope audit</div>
          <div className="mt-1 text-xs text-[#666]">
            Submit a (dx, dy) sample. The auditor maintains a rolling window
            and emits a recommendation: CONTINUE / WATCH / THROTTLE / HALT.
          </div>
          <div className="mt-4 space-y-3">
            <label className="block text-xs text-[#8a8a8a]">
              Metric ID
              <input
                value={metricId}
                onChange={(e) => setMetricId(e.target.value)}
                className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0a0a0a] px-3 py-1.5 text-sm text-[#f5f5f5]"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[#8a8a8a]">
                Horizontal (dx)
                <input
                  type="number"
                  value={horizontal}
                  onChange={(e) => setHorizontal(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0a0a0a] px-3 py-1.5 text-sm text-[#f5f5f5] font-mono"
                />
              </label>
              <label className="block text-xs text-[#8a8a8a]">
                Vertical (dy)
                <input
                  type="number"
                  value={vertical}
                  onChange={(e) => setVertical(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0a0a0a] px-3 py-1.5 text-sm text-[#f5f5f5] font-mono"
                />
              </label>
            </div>
            <button
              onClick={observe}
              disabled={sekedLoading}
              className="w-full rounded-md bg-[#c9b787] px-3 py-2 text-sm font-medium text-[#0a0a0a] hover:bg-[#a89868] disabled:opacity-50"
            >
              {sekedLoading ? 'Sampling…' : 'Submit sample'}
            </button>
            {sekedError && (
              <div className="rounded-md border border-[rgba(245,245,245,0.3)] bg-[rgba(245,245,245,0.06)] p-2 text-xs text-[#f5f5f5]">
                {sekedError}
              </div>
            )}
          </div>
          {signal && (
            <div className="mt-5 space-y-3">
              <div
                className={`inline-block rounded-md border px-3 py-1 text-xs font-mono uppercase tracking-wider ${RECOMMENDATION_COLORS[signal.recommendation]}`}
              >
                {signal.recommendation}
              </div>
              <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div>
                  <dt className="text-[#666]">verdict</dt>
                  <dd className="text-[#f5f5f5]">{signal.reading.verdict}</dd>
                </div>
                <div>
                  <dt className="text-[#666]">seked</dt>
                  <dd className="text-[#c9b787]">{signal.reading.seked.toFixed(3)}</dd>
                </div>
                <div>
                  <dt className="text-[#666]">palms / cubit</dt>
                  <dd className="text-[#f5f5f5]">
                    {signal.reading.palms.toFixed(2)} / {signal.reading.cubits}
                  </dd>
                </div>
                <div>
                  <dt className="text-[#666]">slope (deg)</dt>
                  <dd className="text-[#f5f5f5]">{signal.degrees.toFixed(2)}°</dd>
                </div>
              </dl>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0e0e0e] p-5">
          <div className="text-sm font-semibold text-[#f5f5f5]">Threshold decomposition</div>
          <div className="mt-1 text-xs text-[#666]">
            Decompose a rational threshold p/q into distinct unit fractions
            (RMP 2/n table) so it's inspectable by a human auditor.
          </div>
          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[#8a8a8a]">
                p (numerator)
                <input
                  type="number"
                  value={p}
                  onChange={(e) => setP(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0a0a0a] px-3 py-1.5 text-sm text-[#f5f5f5] font-mono"
                />
              </label>
              <label className="block text-xs text-[#8a8a8a]">
                q (denominator)
                <input
                  type="number"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0a0a0a] px-3 py-1.5 text-sm text-[#f5f5f5] font-mono"
                />
              </label>
            </div>
            <button
              onClick={inspect}
              disabled={auditLoading}
              className="w-full rounded-md bg-[#c9b787] px-3 py-2 text-sm font-medium text-[#0a0a0a] hover:bg-[#a89868] disabled:opacity-50"
            >
              {auditLoading ? 'Decomposing…' : 'Decompose threshold'}
            </button>
            {auditError && (
              <div className="rounded-md border border-[rgba(245,245,245,0.3)] bg-[rgba(245,245,245,0.06)] p-2 text-xs text-[#f5f5f5]">
                {auditError}
              </div>
            )}
          </div>
          {audit && (
            <div className="mt-5 space-y-3">
              <div className="rounded-md bg-[#0a0a0a] p-3">
                <div className="font-mono text-[#c9b787] text-sm">{audit.explanation}</div>
              </div>
              <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div>
                  <dt className="text-[#666]">terms</dt>
                  <dd className="text-[#f5f5f5]">{audit.decomposition.terms.length}</dd>
                </div>
                <div>
                  <dt className="text-[#666]">exact</dt>
                  <dd className={audit.decomposition.exact ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}>
                    {String(audit.decomposition.exact)}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-[#666]">decomposition</dt>
                  <dd className="text-[#f5f5f5]">
                    {audit.decomposition.terms.map((t) => `1/${t}`).join(' + ') || '∅'}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0e0e0e] p-5">
        <div className="text-sm font-semibold text-[#f5f5f5]">Why this matters for Amaru</div>
        <p className="mt-2 text-sm text-[#8a8a8a]">
          Amaru coordinates fleets of heterogeneous syncs across cost,
          throughput, and error-rate dimensions. The seked auditor refuses
          to blow up at vertical asymptotes — it returns HALT instead of
          NaN — and the unit-fraction decomposition lets every fleet-wide
          alert and kill-switch threshold be reproduced byte-for-byte
          across runtimes that disagree on floating-point. Both primitives
          are governed by A11oy approval tiers.
        </p>
        <div className="mt-3 text-xs font-mono text-[#c9b787]">
          POST /api/ouroboros/amaru/observe-metric · POST /api/ouroboros/amaru/audit-threshold
        </div>
      </div>
    </div>
  );
}
