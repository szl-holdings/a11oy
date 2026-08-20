/**
 * pac-bayes-bound.test.ts — runtime tests for the McAllester-1999 bound.
 *
 * Coverage:
 *  - monotonicity in KL (more posterior–prior drift → looser bound)
 *  - tight bound: with large n, small KL, large δ → upperBound near R̂
 *  - non-vacuity threshold: KL above threshold yields ≥ 1 upper bound
 *  - 9-axis worst-axis identification
 *  - input validation: rejects bad delta, negative KL, etc.
 *
 * Run: npx tsx web/packages/a11oy-core/src/governance/__tests__/pac-bayes-bound.test.ts
 */

import assert from 'node:assert/strict';
import {
  pacBayesBound,
  pacBayesNonVacuityThreshold,
  nineAxisPacBayesBound,
} from '../pac-bayes-bound.ts';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({
      id,
      ok: false,
      detail: e instanceof Error ? e.message : String(e),
    });
  }
}

// --- monotonicity ----------------------------------------------------------

test('T_pac_mono_kl: bound is monotone non-decreasing in KL', () => {
  const a = pacBayesBound({
    empiricalRisk: 0.1,
    klDivergence: 0.5,
    sampleSize: 10_000,
    delta: 0.05,
  });
  const b = pacBayesBound({
    empiricalRisk: 0.1,
    klDivergence: 5.0,
    sampleSize: 10_000,
    delta: 0.05,
  });
  assert.ok(b.upperBound >= a.upperBound);
  assert.ok(b.slack > a.slack);
});

// --- tight bound -----------------------------------------------------------

test('T_pac_tight: large n + small KL + permissive delta → tight bound', () => {
  const r = pacBayesBound({
    empiricalRisk: 0.05,
    klDivergence: 0.01,
    sampleSize: 1_000_000,
    delta: 0.1,
  });
  // Bound is non-vacuous and within 0.01 of empirical.
  assert.equal(r.nonVacuous, true);
  assert.ok(r.slack < 0.01, `expected slack < 0.01, got ${r.slack}`);
});

// --- non-vacuity threshold -------------------------------------------------

test('T_pac_nonvacuity: KL above threshold yields vacuous bound', () => {
  const n = 10_000;
  const delta = 0.05;
  const risk = 0.2;
  const klMax = pacBayesNonVacuityThreshold(risk, n, delta);
  assert.ok(klMax > 0);
  const justAbove = pacBayesBound({
    empiricalRisk: risk,
    klDivergence: klMax * 1.01,
    sampleSize: n,
    delta,
  });
  assert.equal(justAbove.nonVacuous, false);
  const justBelow = pacBayesBound({
    empiricalRisk: risk,
    klDivergence: klMax * 0.99,
    sampleSize: n,
    delta,
  });
  assert.equal(justBelow.nonVacuous, true);
});

// --- 9-axis ---------------------------------------------------------------

test('T_pac_nineAxis_worst: identifies worst axis correctly', () => {
  const risks = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.50]; // axis 8 dominates
  const kls = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1];
  const out = nineAxisPacBayesBound({
    perAxisEmpiricalRisk: risks,
    perAxisKL: kls,
    sampleSize: 50_000,
    delta: 0.05,
  });
  assert.equal(out.worstAxis, 8);
  assert.ok(out.worstResult.upperBound > out.perAxis[0]!.upperBound);
});

test('T_pac_nineAxis_length_check: wrong-length input is rejected', () => {
  assert.throws(() =>
    nineAxisPacBayesBound({
      perAxisEmpiricalRisk: [0.1, 0.2],
      perAxisKL: [0.1, 0.2],
      sampleSize: 1000,
      delta: 0.05,
    }),
  );
});

// --- validation ------------------------------------------------------------

test('T_pac_validate_delta: delta=0 or delta=1 rejected', () => {
  assert.throws(() =>
    pacBayesBound({
      empiricalRisk: 0.1,
      klDivergence: 0.1,
      sampleSize: 1000,
      delta: 0,
    }),
  );
  assert.throws(() =>
    pacBayesBound({
      empiricalRisk: 0.1,
      klDivergence: 0.1,
      sampleSize: 1000,
      delta: 1,
    }),
  );
});

test('T_pac_validate_kl: negative KL rejected', () => {
  assert.throws(() =>
    pacBayesBound({
      empiricalRisk: 0.1,
      klDivergence: -0.1,
      sampleSize: 1000,
      delta: 0.05,
    }),
  );
});

test('T_pac_validate_risk: risk outside [0,1] rejected', () => {
  assert.throws(() =>
    pacBayesBound({
      empiricalRisk: 1.5,
      klDivergence: 0.1,
      sampleSize: 1000,
      delta: 0.05,
    }),
  );
});

// --- Summary ---------------------------------------------------------------

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;
console.log('\npac-bayes-bound test results:');
for (const r of results) {
  const status = r.ok ? 'PASS' : 'FAIL';
  console.log(`  ${status}  ${r.id}${r.detail ? `  — ${r.detail}` : ''}`);
}
console.log(`\nTOTAL: ${results.length}  PASSED: ${passed}  FAILED: ${failed}`);
if (failed > 0) process.exit(1);
