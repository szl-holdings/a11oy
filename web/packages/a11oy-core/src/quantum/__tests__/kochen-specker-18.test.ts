/**
 * Regression tests for the KS-18 parity witness cover.
 *
 * Run: npx tsx web/packages/a11oy-core/src/quantum/__tests__/kochen-specker-18.test.ts
 */

import assert from 'node:assert/strict';
import { KochenSpecker18Witness, KS18_CONTEXTS, KS18_VECTORS } from '../kochen_specker_18.ts';

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

test('T_KS18_shape: witness ships 18 vectors and 9 contexts', () => {
  assert.equal(KS18_VECTORS.length, 18);
  assert.equal(KS18_CONTEXTS.length, 9);
  for (const context of KS18_CONTEXTS) {
    assert.equal(context.length, 4);
    for (const vectorIndex of context) {
      assert.ok(vectorIndex >= 0 && vectorIndex < KS18_VECTORS.length);
    }
  }
});

test('T_KS18_cover: every vector label appears exactly twice', () => {
  const counts = new Array<number>(KS18_VECTORS.length).fill(0);
  for (const context of KS18_CONTEXTS) {
    for (const vectorIndex of context) {
      counts[vectorIndex]++;
    }
  }

  assert.deepEqual(counts, new Array<number>(KS18_VECTORS.length).fill(2));
});

test('T_KS18_empty_observation: no non-contextual model satisfies the parity cover', () => {
  const result = KochenSpecker18Witness.evaluate(new Map());

  assert.equal(result.contextual, true);
  assert.equal(result.reason, 'NO_NON_CONTEXTUAL_MODEL_FITS_OBSERVATIONS');
});

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;

console.log('\nkochen-specker-18 test results:');
for (const r of results) {
  const status = r.ok ? 'PASS' : 'FAIL';
  console.log(`  ${status}  ${r.id}${r.detail ? `  - ${r.detail}` : ''}`);
}
console.log(`\nTOTAL: ${results.length}  PASSED: ${passed}  FAILED: ${failed}`);
if (failed > 0) process.exit(1);
