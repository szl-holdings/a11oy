/**
 * Amaru — Convergent Sync. (Inca: the cosmic two-headed serpent that bridges
 * worlds and bites its own tails — our Andean Ouroboros.)
 *
 * A correct reverse-ETL is idempotent: running the sync twice should produce
 * the same destination state. In practice, downstream systems mutate, and
 * a single pass leaves the destination drifted. This page runs a sync as
 * repeated idempotent passes through the Ouroboros kernel until the diff
 * vector goes to zero.
 *
 * The trace becomes the audit artifact — every entity gets an answer to
 * "in how many passes did your destination state stop changing?"
 */

import { useCallback, useMemo, useState } from 'react';
import {
  type LoopTrace,
  allocateDepth,
  numericConsistency,
  runLoop,
} from '@workspace/ouroboros';
import { LoopGlyph, OuroborosTrace } from '@workspace/ouroboros/react';

interface EntityRow {
  id: string;
  source: number;
  dest: number;
  passesToConverge: number;
  converged: boolean;
}

interface SyncState {
  rows: EntityRow[];
  diff: number;
  pass: number;
}

const SCENARIOS = [
  {
    id: 'crm-stable',
    label: 'CRM contact sync (stable downstream)',
    rows: () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: `contact_${1000 + i}`,
        source: 100 + i * 7,
        dest: 95 + i * 6 + (i % 3 === 0 ? 4 : 0),
        passesToConverge: 0,
        converged: false,
      })),
    drift: 0.04,
  },
  {
    id: 'billing-noisy',
    label: 'Billing usage rollup (noisy destination)',
    rows: () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: `usage_${i}`,
        source: 1000 + i * 23,
        dest: 800 + i * 21 + (i % 2 === 0 ? 30 : -20),
        passesToConverge: 0,
        converged: false,
      })),
    drift: 0.12,
  },
  {
    id: 'orders-divergent',
    label: 'Orders sync (one entity refuses to converge)',
    rows: () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: `order_${5000 + i}`,
        source: 50 + i * 5,
        dest: 48 + i * 5 + (i === 7 ? 18 : 0),
        passesToConverge: 0,
        converged: false,
      })),
    drift: 0.06,
    troubleId: 'order_5007',
  },
] as const;

function buildPass(driftFactor: number, troubleId?: string) {
  return async function pass(state: SyncState): Promise<{ state: SyncState; output: number }> {
    const passNum = state.pass + 1;
    const nextRows: EntityRow[] = state.rows.map((r) => {
      if (r.converged) return r;
      // Each pass moves dest 60% toward source, + drift noise.
      const drift = (Math.sin(r.source + passNum) * driftFactor) || 0;
      let nextDest = r.dest + (r.source - r.dest) * 0.6 + drift;
      // The "trouble" entity oscillates and never converges.
      if (troubleId && r.id === troubleId) {
        nextDest = r.dest + (r.source - r.dest) * 0.2 + (passNum % 2 === 0 ? 6 : -6);
      }
      const closeEnough = Math.abs(nextDest - r.source) < 0.5;
      return {
        ...r,
        dest: nextDest,
        converged: closeEnough,
        passesToConverge: closeEnough && r.passesToConverge === 0 ? passNum : r.passesToConverge,
      };
    });
    const diff = nextRows.reduce((sum, r) => sum + Math.abs(r.dest - r.source), 0);
    await new Promise((r) => setTimeout(r, 6));
    return {
      state: { rows: nextRows, diff, pass: passNum },
      output: diff,
    };
  };
}

const syncDelta = (a: SyncState, b: SyncState): number => Math.abs(a.diff - b.diff);

export default function ConvergentSync() {
  const [scenarioId, setScenarioId] = useState<(typeof SCENARIOS)[number]['id']>(SCENARIOS[0].id);
  const [trace, setTrace] = useState<LoopTrace<SyncState, number> | null>(null);
  const [running, setRunning] = useState(false);
  const [maxSteps, setMaxSteps] = useState(8);
  const [adaptive, setAdaptive] = useState(false);

  const scenario = useMemo(
    () => SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0],
    [scenarioId],
  );

  const allocator = useMemo(
    () =>
      allocateDepth({
        recentDeltas: trace ? trace.steps.slice(-3).map((s) => s.deltaMagnitude).reverse() : [],
        maxSteps,
      }),
    [trace, maxSteps],
  );

  const run = useCallback(async () => {
    setRunning(true);
    try {
      // Adaptive depth: when enabled and a prior trace exists, the
      // EntropyDepthAllocator's recommendation governs the actual budget
      // (capped by the user's ceiling). This is the operational use of the
      // primitive — not just a displayed recommendation.
      const effectiveBudget =
        adaptive && trace
          ? Math.min(maxSteps, Math.max(1, allocator.recommendedSteps))
          : maxSteps;
      const result = await runLoop<SyncState, number>({
        initialState: { rows: scenario.rows(), diff: 999, pass: 0 },
        step: buildPass(scenario.drift, 'troubleId' in scenario ? scenario.troubleId : undefined),
        delta: syncDelta,
        consistency: (a, b) => numericConsistency(a, b),
        config: {
          maxSteps: effectiveBudget,
          convergenceThreshold: 0.5,
          label: `conduit.sync.convergent[${scenario.id}]${adaptive && trace ? '.adaptive' : ''}`,
        },
      });
      setTrace(result);
    } finally {
      setRunning(false);
    }
  }, [scenario, maxSteps, adaptive, trace, allocator]);

  const rows = trace?.finalState.rows ?? scenario.rows();
  const convergedCount = rows.filter((r) => r.converged).length;
  const stuckRows = rows.filter((r) => !r.converged);
  const conv = trace ? Math.max(0, 1 - Math.min(1, (trace.steps.at(-1)?.deltaMagnitude ?? 1) / 5)) : 0;

  return (
    <div
      style={{
        minHeight: '100%',
        background: '#0a0a0a',
        color: '#eaeaea',
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        padding: '28px clamp(16px, 4vw, 56px)',
      }}
      data-testid="page-convergent-sync"
    >
      <header style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <LoopGlyph size={52} convergence={conv} spinning={running} color="#a0c4ff" />
        <div>
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'rgba(160,196,255,0.85)',
              marginBottom: 4,
            }}
          >
            Amaru · Convergent Sync
          </div>
          <h1 style={{ fontSize: 22, margin: 0, fontWeight: 500 }}>
            Idempotent passes until the diff is zero
          </h1>
          <p style={{ margin: '6px 0 0', fontSize: 13, color: 'rgba(255,255,255,0.55)', maxWidth: 720 }}>
            A sync isn't done when it ran — it's done when running it again wouldn't change
            anything. Entities that need extra passes are flagged. Entities that never
            converge become Sentra-investigation candidates.
          </p>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 320px) 1fr', gap: 20 }}>
        <div
          style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6,
            padding: 16,
          }}
        >
          <h2 style={{ fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.55)', margin: 0 }}>
            Sync target
          </h2>
          <select
            value={scenarioId}
            onChange={(e) => {
              setScenarioId(e.target.value as typeof scenarioId);
              setTrace(null);
            }}
            style={{
              marginTop: 10,
              width: '100%',
              padding: '8px 10px',
              background: 'rgba(255,255,255,0.04)',
              color: '#eaeaea',
              border: '1px solid rgba(255,255,255,0.14)',
              borderRadius: 4,
              fontSize: 13,
              fontFamily: 'inherit',
            }}
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          <label style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', display: 'block', marginTop: 18 }}>
            Max passes · {maxSteps}
            <input
              type="range"
              min={2}
              max={16}
              value={maxSteps}
              onChange={(e) => setMaxSteps(Number(e.target.value))}
              style={{ width: '100%', marginTop: 4 }}
            />
          </label>

          <label
            style={{
              fontSize: 11,
              color: 'rgba(255,255,255,0.7)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              marginTop: 12,
            }}
          >
            <input
              type="checkbox"
              checked={adaptive}
              onChange={(e) => setAdaptive(e.target.checked)}
              data-testid="adaptive-toggle"
            />
            <span>
              Adaptive depth budget{' '}
              {adaptive ? (
                trace ? (
                  <span style={{ color: '#a0c4ff' }}>
                    · using {Math.min(maxSteps, Math.max(1, allocator.recommendedSteps))} of {maxSteps}
                  </span>
                ) : (
                  <span style={{ color: 'rgba(255,255,255,0.4)' }}>· needs prior run</span>
                )
              ) : (
                <span style={{ color: 'rgba(255,255,255,0.4)' }}>· off</span>
              )}
            </span>
          </label>

          <button
            type="button"
            onClick={run}
            disabled={running}
            data-testid="run-sync"
            style={{
              marginTop: 18,
              width: '100%',
              padding: '10px 14px',
              background: running ? 'rgba(160,196,255,0.18)' : '#a0c4ff',
              color: running ? '#a0c4ff' : '#0a0a0a',
              border: 'none',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: 500,
              cursor: running ? 'wait' : 'pointer',
              letterSpacing: '0.04em',
            }}
          >
            {running ? 'Syncing…' : 'Run Convergent Sync'}
          </button>

          <div
            style={{
              marginTop: 16,
              padding: 12,
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 4,
              fontSize: 11,
              color: 'rgba(255,255,255,0.7)',
              lineHeight: 1.5,
            }}
          >
            <div style={{ color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.14em', fontSize: 9, marginBottom: 6 }}>
              Allocator
            </div>
            <div>recommends <span style={{ color: '#a0c4ff' }}>{allocator.recommendedSteps}</span> pass(es)</div>
            <div>trajectory: {allocator.trajectory}</div>
          </div>

          <div
            style={{
              marginTop: 14,
              padding: 12,
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 4,
              fontSize: 11,
              color: 'rgba(255,255,255,0.7)',
            }}
          >
            <div style={{ color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.14em', fontSize: 9, marginBottom: 6 }}>
              Summary
            </div>
            <div>converged: <span style={{ color: '#7ed7c1' }}>{convergedCount}</span> / {rows.length}</div>
            <div>stuck: <span style={{ color: stuckRows.length ? '#ff8c8c' : 'rgba(255,255,255,0.45)' }}>{stuckRows.length}</span></div>
            {trace ? <div style={{ marginTop: 4 }}>final diff: {trace.finalState.diff.toFixed(2)}</div> : null}
          </div>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <div
            style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 6,
              padding: 16,
              maxHeight: 360,
              overflow: 'auto',
            }}
          >
            <div style={{ fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.55)', marginBottom: 10 }}>
              Entity convergence ledger
            </div>
            <div style={{ display: 'grid', gap: 4 }}>
              {rows.map((r) => (
                <div
                  key={r.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '120px 70px 70px 70px 1fr',
                    fontSize: 11,
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                    padding: '4px 6px',
                    borderRadius: 3,
                    background: r.converged ? 'rgba(126,215,193,0.06)' : !trace ? 'transparent' : 'rgba(255,140,140,0.06)',
                    color: r.converged ? '#7ed7c1' : 'rgba(255,255,255,0.7)',
                  }}
                >
                  <span>{r.id}</span>
                  <span>src {r.source.toFixed(0)}</span>
                  <span>dst {r.dest.toFixed(0)}</span>
                  <span>{r.converged ? `✓ p${r.passesToConverge}` : trace ? '✗ stuck' : '—'}</span>
                  <span style={{ color: 'rgba(255,255,255,0.4)' }}>Δ {Math.abs(r.dest - r.source).toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>

          {trace ? (
            <OuroborosTrace
              trace={trace}
              describeOutput={(o) => (typeof o === 'number' ? `total diff: ${o.toFixed(2)}` : '')}
            />
          ) : (
            <div
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px dashed rgba(255,255,255,0.12)',
                borderRadius: 6,
                padding: 24,
                color: 'rgba(255,255,255,0.45)',
                fontSize: 13,
                textAlign: 'center',
              }}
            >
              Run the sync to generate a convergence trace.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
