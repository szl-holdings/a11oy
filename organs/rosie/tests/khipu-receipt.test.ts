/**
 * khipu-receipt.test.ts — runtime tests for the KhipuReceipt DAG.
 *
 * Coverage:
 *  - happy path: build a 3-organ × 5-decision root, verify invariants
 *  - TH11 failure mode: malformed sum where children do not equal parent
 *  - dual-attestation failure mode: missing signer / same signer
 *  - knotInvariantTag determinism + skeleton sensitivity
 *
 * Run: node --experimental-strip-types tests/khipu-receipt.test.ts
 */

import assert from 'node:assert/strict';
import {
  buildDecision,
  buildOrgan,
  buildRoot,
  verifySumInvariant,
  verifyDualAttestation,
  knotInvariantTag,
  type OrganReceipt,
  type KhipuRootReceipt,
} from '../src/khipu-receipt.ts';

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

// --- happy path -------------------------------------------------------------

test('T_khipu_happy: 3-organ x 5-decision build + verifySumInvariant pass', () => {
  const organs: OrganReceipt[] = [];
  for (let i = 0; i < 3; i++) {
    const decisions = Array.from({ length: 5 }, (_, j) =>
      buildDecision(`o${i}-d${j}`, (i + 1) * 100 + j),
    );
    organs.push(buildOrgan(`organ-${i}`, decisions));
  }
  const root = buildRoot('root-001', organs);
  const expected = organs.reduce(
    (a, o) => a + o.decisions.reduce((b, d) => b + d.value, 0),
    0,
  );
  assert.equal(root.rootValue, expected);
  const v = verifySumInvariant(root);
  assert.equal(v.ok, true);
});

// --- TH11 FAILURE MODE: malformed sum --------------------------------------

test('T_khipu_failure_TH11: malformed pendant sum is rejected', () => {
  const decisions = [
    buildDecision('d1', 10),
    buildDecision('d2', 20),
    buildDecision('d3', 30),
  ];
  // Tamper: forge a pendant with the wrong stored pendantValue (not 60).
  const tamperedOrgan: OrganReceipt = {
    kind: 'organ',
    organId: 'tamper-org',
    decisions,
    pendantValue: 999,            // wrong! decisions sum to 60.
    pendantHash: 'fakehash',
  };
  const root = buildRoot('root-tamper', [tamperedOrgan]);
  const v = verifySumInvariant(root);
  assert.equal(v.ok, false);
  if (!v.ok) {
    assert.match(v.reason, /pendantValue mismatch/);
  }
});

test('T_khipu_failure_TH11b: malformed root sum is rejected', () => {
  const decisions = [buildDecision('a', 5), buildDecision('b', 7)];
  const organ = buildOrgan('o1', decisions);
  // Tamper the rootValue manually.
  const tamperedRoot: KhipuRootReceipt = {
    kind: 'root',
    receiptId: 'root-bad',
    organs: [organ],
    rootValue: 100,                // wrong! organ pendantValue = 12.
    rootHash: 'fakehash',
  };
  const v = verifySumInvariant(tamperedRoot);
  assert.equal(v.ok, false);
  if (!v.ok) assert.match(v.reason, /rootValue mismatch/);
});

// --- Dual attestation tests ------------------------------------------------

test('T_khipu_dual_ok: distinct signers with non-empty signatures pass', () => {
  const root = buildRoot('r1', [buildOrgan('o', [buildDecision('d', 1)])], {
    signerA: 'alice',
    signerB: 'bob',
    signatureA: 'sigA',
    signatureB: 'sigB',
    attestedAt: '2026-05-28T12:00:00Z',
  });
  const v = verifyDualAttestation(root);
  assert.equal(v.ok, true);
});

test('T_khipu_dual_FAIL: same signer for both = rejected', () => {
  const root = buildRoot('r2', [buildOrgan('o', [buildDecision('d', 1)])], {
    signerA: 'alice',
    signerB: 'alice',          // SAME — must fail
    signatureA: 'sigA',
    signatureB: 'sigB',
    attestedAt: '2026-05-28T12:00:00Z',
  });
  const v = verifyDualAttestation(root);
  assert.equal(v.ok, false);
  if (!v.ok) assert.match(v.reason, /distinct/);
});

test('T_khipu_dual_FAIL_missing_signer: missing signer = rejected', () => {
  const root = buildRoot('r3', [buildOrgan('o', [buildDecision('d', 1)])], {
    signerA: 'alice',
    signerB: '',               // empty
    signatureA: 'sigA',
    signatureB: 'sigB',
    attestedAt: '2026-05-28T12:00:00Z',
  });
  const v = verifyDualAttestation(root);
  assert.equal(v.ok, false);
});

// --- knotInvariantTag tests ------------------------------------------------

test('T_khipu_knot_tag_deterministic: same input → same tag', () => {
  const r1 = buildRoot('rA', [
    buildOrgan('x', [buildDecision('a', 5), buildDecision('b', 7)]),
    buildOrgan('y', [buildDecision('c', 3)]),
  ]);
  const r2 = buildRoot('rA-copy', [
    buildOrgan('x', [buildDecision('a', 5), buildDecision('b', 7)]),
    buildOrgan('y', [buildDecision('c', 3)]),
  ]);
  assert.equal(knotInvariantTag(r1), knotInvariantTag(r2));
});

test('T_khipu_knot_tag_sensitive: different skeleton → different tag', () => {
  const r1 = buildRoot('rA', [
    buildOrgan('x', [buildDecision('a', 5)]),
  ]);
  const r2 = buildRoot('rB', [
    buildOrgan('x', [buildDecision('a', 5), buildDecision('b', 1)]),
  ]);
  assert.notEqual(knotInvariantTag(r1), knotInvariantTag(r2));
});

// --- Reidemeister R2 smoke test (commutativity) ---------------------------

test('T_reidemeister_R2: organ order does not change knot tag (sorted skeleton)', () => {
  const oA = buildOrgan('a', [buildDecision('d1', 1)]);
  const oB = buildOrgan('b', [buildDecision('d2', 2)]);
  const r_ab = buildRoot('r', [oA, oB]);
  const r_ba = buildRoot('r', [oB, oA]);
  // knotInvariantTag uses sorted skeleton → must be equal under organ swap.
  assert.equal(knotInvariantTag(r_ab), knotInvariantTag(r_ba));
});

// --- Reidemeister R1 smoke test (repack a single axis) --------------------

test('T_reidemeister_R1: identity repack of one decision preserves rootValue', () => {
  const decs = [buildDecision('a', 10), buildDecision('b', 20)];
  const r1 = buildRoot('rid', [buildOrgan('o', decs)]);
  // Repack: rebuild the same decisions (canonical encoding is deterministic).
  const decs2 = [buildDecision('a', 10), buildDecision('b', 20)];
  const r2 = buildRoot('rid', [buildOrgan('o', decs2)]);
  assert.equal(r1.rootValue, r2.rootValue);
  assert.equal(r1.rootHash, r2.rootHash);
});

// --- Summary ---------------------------------------------------------------

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;
console.log('\nkhipu-receipt test results:');
for (const r of results) {
  const status = r.ok ? 'PASS' : 'FAIL';
  console.log(`  ${status}  ${r.id}${r.detail ? `  — ${r.detail}` : ''}`);
}
console.log(`\nTOTAL: ${results.length}  PASSED: ${passed}  FAILED: ${failed}`);
if (failed > 0) process.exit(1);
