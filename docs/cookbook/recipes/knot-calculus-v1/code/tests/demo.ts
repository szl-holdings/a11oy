/**
 * demo.ts — v15 knot-calculus-v1 cookbook walkthrough.
 *
 * Builds a 3-organ × 5-decision khipu root, verifies TH11, prints the
 * knot-invariant tag, computes a McAllester-1999 PAC-Bayes bound on a
 * worked governance-head example, then demonstrates a TH11 failure on
 * a tampered pendant value.
 *
 * Run: npx tsx tests/demo.ts
 */

import {
  buildDecision,
  buildOrgan,
  buildRoot,
  verifySumInvariant,
  knotInvariantTag,
  type OrganReceipt,
} from '../src/khipu-receipt.ts';

import { pacBayesBound, pacBayesNonVacuityThreshold } from '../src/pac-bayes-bound.ts';

function section(label: string): void {
  console.log(`\n=== ${label} ===`);
}

// --- 1. Build a 3-organ × 5-decision root and verify TH11 ----------------

section('1. Build root and verify TH11 (sum-of-sums invariant)');

const organs: OrganReceipt[] = [];
for (let i = 0; i < 3; i++) {
  const decisions = Array.from({ length: 5 }, (_, j) =>
    buildDecision(`organ-${i}/decision-${j}`, (i + 1) * 100 + j),
  );
  organs.push(buildOrgan(`organ-${i}`, decisions));
}
const root = buildRoot('demo-root-001', organs);
const v = verifySumInvariant(root);
console.log(`  rootValue = ${root.rootValue}`);
console.log(`  rootHash  = ${root.rootHash.slice(0, 16)}…`);
console.log(`  TH11 verifySumInvariant: ${v.ok ? 'PASS' : `FAIL — ${v.reason}`}`);

// --- 2. Emit the audit-Reidemeister knot tag -----------------------------

section('2. Emit knot-invariant tag (Conjecture R1/R2/R3, target v16)');

const tag = knotInvariantTag(root);
console.log(`  knotTag = ${tag}  (16-hex; same skeleton + rootValue → same tag)`);

// --- 3. PAC-Bayes bound on a worked governance-head example -------------

section('3. McAllester-1999 PAC-Bayes bound (TH13)');

const example = {
  empiricalRisk: 0.05,
  klDivergence:  0.5,
  sampleSize:    100_000,
  delta:         0.05,
};
const bound = pacBayesBound(example);
console.log(`  Inputs: R̂=${example.empiricalRisk}, KL=${example.klDivergence}, n=${example.sampleSize}, δ=${example.delta}`);
console.log(`  Slack   = ${bound.slack.toFixed(6)}`);
console.log(`  Upper   = ${bound.upperBound.toFixed(6)}`);
console.log(`  NonVac. = ${bound.nonVacuous}`);

const klMax = pacBayesNonVacuityThreshold(
  example.empiricalRisk,
  example.sampleSize,
  example.delta,
);
console.log(`  Largest KL still non-vacuous: ${klMax.toFixed(2)} nats`);

// --- 4. TH11 failure-mode demonstration ---------------------------------

section('4. TH11 failure mode (tampered pendant value)');

const tamperedOrgan: OrganReceipt = {
  kind: 'organ',
  organId: 'tamper-org',
  decisions: [buildDecision('d1', 10), buildDecision('d2', 20)],
  pendantValue: 999,           // wrong (decisions sum to 30)
  pendantHash: 'fakehash',
};
const tamperedRoot = buildRoot('demo-root-tamper', [tamperedOrgan]);
const vt = verifySumInvariant(tamperedRoot);
console.log(`  TH11 on tampered root: ${vt.ok ? 'PASS (BUG)' : `FAIL (correct) — ${vt.reason}`}`);

if (!v.ok || vt.ok) {
  console.error('\nDEMO FAILED: TH11 did not behave as expected.');
  process.exit(1);
}

console.log('\nDEMO PASS — TH11 confirmed on happy path and tampered path; tag + bound emitted.');
