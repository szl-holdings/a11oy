/**
 * khipu-positional.test.ts — runtime tests for the khipu positional encoding.
 *
 * Run: npx tsx web/src/lib/qkan-fwp/__tests__/khipu-positional.test.ts
 */

import assert from 'node:assert/strict';
import {
  khipuPositionalEncoding,
  khipuPositionalQuery,
  khipuSkeletonTag,
} from '../khipu-positional.ts';

const results: Array<{ id: string; ok: boolean; detail?: string }> = [];

function test(id: string, fn: () => void) {
  try {
    fn();
    results.push({ id, ok: true });
  } catch (e) {
    results.push({ id, ok: false, detail: e instanceof Error ? e.message : String(e) });
  }
}

test('T_khipu_pe_deterministic: same (organId, idx) → same vector', () => {
  const a = khipuPositionalEncoding({ organId: 'heart', decisionIndex: 3 }, 16);
  const b = khipuPositionalEncoding({ organId: 'heart', decisionIndex: 3 }, 16);
  for (let i = 0; i < 16; i++) assert.equal(a[i], b[i]);
});

test('T_khipu_pe_organ_distinct: different organId → different vector', () => {
  const a = khipuPositionalEncoding({ organId: 'heart', decisionIndex: 0 }, 16);
  const b = khipuPositionalEncoding({ organId: 'liver', decisionIndex: 0 }, 16);
  let diff = 0;
  for (let i = 0; i < 16; i++) if (Math.abs(a[i]! - b[i]!) > 1e-9) diff++;
  assert.ok(diff >= 8, `expected at least 8 differing dims, got ${diff}`);
});

test('T_khipu_pe_validate: odd dimension is rejected', () => {
  assert.throws(() =>
    khipuPositionalEncoding({ organId: 'x', decisionIndex: 0 }, 7),
  );
});

test('T_khipu_pe_validate: negative decisionIndex rejected', () => {
  assert.throws(() =>
    khipuPositionalEncoding({ organId: 'x', decisionIndex: -1 }, 8),
  );
});

test('T_khipu_positional_query: PE is added to fast-weight query', () => {
  // Identity fast-weight (W = I) so queried(key) = key, plus PE.
  const d = 8;
  const W = { W: new Float64Array(d * d), d };
  for (let i = 0; i < d; i++) W.W[i * d + i] = 1;
  const key = new Float64Array([0, 0, 0, 0, 0, 0, 0, 0]);
  const out = khipuPositionalQuery(W, key, { organId: 'heart', decisionIndex: 2 });
  const pe = khipuPositionalEncoding({ organId: 'heart', decisionIndex: 2 }, d);
  for (let i = 0; i < d; i++) assert.equal(out[i], pe[i]);
});

test('T_khipu_skeleton_R2: organ order does not change skeleton tag', () => {
  const t1 = khipuSkeletonTag([
    { organId: 'a', decisionIndex: 0 },
    { organId: 'a', decisionIndex: 1 },
    { organId: 'b', decisionIndex: 0 },
  ]);
  const t2 = khipuSkeletonTag([
    { organId: 'b', decisionIndex: 0 },
    { organId: 'a', decisionIndex: 1 },
    { organId: 'a', decisionIndex: 0 },
  ]);
  assert.equal(t1, t2);
});

test('T_khipu_skeleton_sensitive: extra decision shifts skeleton tag', () => {
  const t1 = khipuSkeletonTag([
    { organId: 'a', decisionIndex: 0 },
    { organId: 'b', decisionIndex: 0 },
  ]);
  const t2 = khipuSkeletonTag([
    { organId: 'a', decisionIndex: 0 },
    { organId: 'a', decisionIndex: 1 },
    { organId: 'b', decisionIndex: 0 },
  ]);
  assert.notEqual(t1, t2);
});

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;
console.log('\nkhipu-positional test results:');
for (const r of results) {
  const status = r.ok ? 'PASS' : 'FAIL';
  console.log(`  ${status}  ${r.id}${r.detail ? `  — ${r.detail}` : ''}`);
}
console.log(`\nTOTAL: ${results.length}  PASSED: ${passed}  FAILED: ${failed}`);
if (failed > 0) process.exit(1);
