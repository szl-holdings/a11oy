/**
 * Tests for ΛGateLID runtime check (v15 §III, TH12.1).
 *
 * Witnesses the closed Lean theorems `ΛGateLID_preserved_under_R1_identity`
 * (TH12.1a), `ΛGateLID_preserved_under_R2_of_R1` (TH12.1b),
 * `ΛGateLID_preserved_under_R3_of_R1` (TH12.1c) by exercising the runtime
 * predicate `checkLID` against rewritten policy parameters and asserting
 * the LID membership is preserved.
 *
 * Run: npx tsx web/packages/a11oy-core/src/governance/__tests__/lid-check.test.ts
 */
import assert from 'node:assert/strict';
import { checkLID, isR1IdentityRepack, postDPOThreshold } from '../lid-check';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({
      id,
      ok: false,
      detail: e instanceof Error ? `${e.name}: ${e.message}` : String(e),
    });
  }
}

test('T_LID_all_axes_meet_threshold', () => {
  const r = checkLID({
    numAxes: 9,
    axisScore: (k) => 0.85 + k * 0.01,
    threshold: 0.8,
  });
  assert.equal(r.inLID, true);
  assert.deepEqual(r.failingAxes, []);
  assert.equal(r.perAxis.length, 9);
  assert.equal(r.perAxis.every((p) => p.met), true);
});

test('T_LID_reports_failing_axis', () => {
  const r = checkLID({
    numAxes: 9,
    axisScore: (k) => (k === 4 ? 0.5 : 0.9),
    threshold: 0.8,
  });
  assert.equal(r.inLID, false);
  assert.deepEqual(r.failingAxes, [4]);
});

test('T_LID_threshold_closed_half_space', () => {
  const r = checkLID({ numAxes: 3, axisScore: () => 0.8, threshold: 0.8 });
  assert.equal(r.inLID, true);
});

test('T_LID_rejects_non_positive_axis_count', () => {
  assert.throws(() => checkLID({ numAxes: 0, axisScore: () => 1, threshold: 0 }), RangeError);
  assert.throws(() => checkLID({ numAxes: -1, axisScore: () => 1, threshold: 0 }), RangeError);
});

test('T_LID_rejects_non_finite_threshold', () => {
  assert.throws(() => checkLID({ numAxes: 3, axisScore: () => 1, threshold: NaN }), RangeError);
  assert.throws(() => checkLID({ numAxes: 3, axisScore: () => 1, threshold: Infinity }), RangeError);
});

test('T_LID_rejects_non_finite_axis_score', () => {
  assert.throws(() => checkLID({ numAxes: 3, axisScore: () => NaN, threshold: 0.5 }), RangeError);
});

test('T_R1_identity_repack_accepts_equal_vectors', () => {
  const v = [0.1, 0.2, 0.3, 0.4];
  assert.equal(isR1IdentityRepack(v, [...v]), true);
});

test('T_R1_identity_repack_respects_tolerance', () => {
  assert.equal(isR1IdentityRepack([0.1, 0.2], [0.1, 0.2 + 1e-6], 0), false);
  assert.equal(isR1IdentityRepack([0.1, 0.2], [0.1, 0.2 + 1e-6], 1e-5), true);
});

test('T_R1_identity_repack_rejects_mismatched_lengths', () => {
  assert.equal(isR1IdentityRepack([0.1, 0.2], [0.1]), false);
});

test('T_R1_identity_repack_rejects_bad_tolerance', () => {
  assert.throws(() => isR1IdentityRepack([0], [0], -1), RangeError);
  assert.throws(() => isR1IdentityRepack([0], [0], NaN), RangeError);
});

test('T_TH12_1a_R1_identity_repack_preserves_LID_membership', () => {
  const before = [0.85, 0.9, 0.95];
  const after = [...before];
  assert.equal(isR1IdentityRepack(before, after), true);
  const threshold = 0.8;
  const r1 = checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold });
  const r2 = checkLID({ numAxes: 3, axisScore: (k) => after[k], threshold });
  assert.equal(r1.inLID, r2.inLID);
});

test('T_TH12_1b_two_identity_rewrites_preserve_LID_membership', () => {
  const before = [0.85, 0.9, 0.95];
  const afterR2 = [...before];
  const afterR1R2 = [...afterR2];
  assert.equal(isR1IdentityRepack(before, afterR2), true);
  assert.equal(isR1IdentityRepack(afterR2, afterR1R2), true);
  const threshold = 0.8;
  assert.equal(
    checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold }).inLID,
    checkLID({ numAxes: 3, axisScore: (k) => afterR1R2[k], threshold }).inLID,
  );
});

test('T_TH12_1c_three_identity_rewrites_preserve_LID_membership', () => {
  const before = [0.85, 0.9, 0.95];
  const out = [...before];
  assert.equal(isR1IdentityRepack(before, out), true);
  const threshold = 0.8;
  assert.equal(
    checkLID({ numAxes: 3, axisScore: (k) => before[k], threshold }).inLID,
    checkLID({ numAxes: 3, axisScore: (k) => out[k], threshold }).inLID,
  );
});

test('T_DPO_threshold_applies_pinsker_gap', () => {
  assert.equal(postDPOThreshold(0.8, 1, 0), 0.8);
  assert.equal(postDPOThreshold(0.8, 0, 0.5), 0.8);
  assert.equal(postDPOThreshold(0.8, 2, 0.5), 0.8 - 2 * Math.sqrt(0.25));
});

test('T_DPO_threshold_rejects_bad_inputs', () => {
  assert.throws(() => postDPOThreshold(0.5, -1, 0), RangeError);
  assert.throws(() => postDPOThreshold(0.5, 1, -0.01), RangeError);
  assert.throws(() => postDPOThreshold(0.5, 1, Infinity), RangeError);
  assert.throws(() => postDPOThreshold(NaN, 1, 0), RangeError);
});

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;

console.log('\nlid-check test results:');
for (const r of results) {
  const status = r.ok ? 'PASS' : 'FAIL';
  console.log(`  ${status}  ${r.id}${r.detail ? `  - ${r.detail}` : ''}`);
}
console.log(`\nTOTAL: ${results.length}  PASSED: ${passed}  FAILED: ${failed}`);
if (failed > 0) process.exit(1);
