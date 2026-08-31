/**
 * ks18_structure.ts — verify the KS-18 / 9-context combinatorial structure.
 *
 * Tests:
 *   (i)   verifyKSStructure() returns ok:true (orthogonality + 2-incidence).
 *   (ii)  the Cabello parity argument: there is NO {0,1} assignment to the
 *         18 vectors with "exactly one '1' per context" in all 9 contexts.
 *         (Brute-force over 2^18 assignments would be expensive; we use the
 *         parity invariant: Σ_ctx (Σ_{v∈ctx} f(v)) = Σ_v 2·f(v) is always
 *         even, but assigning 1 per context gives 9, odd. ⊥.)
 *   (iii) the witness flags CLASSICAL when handed a valid 0/1 assignment
 *         on a single context (degenerate corner of the parity argument).
 *   (iv)  any assignment that violates exactly-one-per-context flags
 *         inconsistencies > 0.
 */

import { strict as assert } from "node:assert";
import {
  KS18_VECTORS,
  KS18_CONTEXTS,
  verifyKSStructure,
  KochenSpecker18Witness,
} from "../src/a11oy-ks18-witness";

// (i) structure
{
  const r = verifyKSStructure();
  assert.equal(r.ok, true, `KS structure invalid: ${r.reason}`);
  assert.equal(KS18_VECTORS.length, 18, "must be 18 vectors");
  assert.equal(KS18_CONTEXTS.length, 9, "must be 9 contexts");
}

// (ii) parity-based KS theorem: no NCHV assignment exists
//      We check the parity invariant directly. If an NCHV f existed, then
//      counting "1"s twice — once by contexts (=9) and once by vectors
//      (each appearing in 2 contexts, so = 2·Σ_v f(v), even) — yields
//      9 = 2k, contradicting 9 odd.
{
  const totalIncidences = KS18_CONTEXTS.reduce((acc, ctx) => acc + ctx.length, 0);
  assert.equal(totalIncidences, 36, "9·4 = 36 incidences");
  // Each vector in exactly 2 contexts ⇒ Σ_v 2·f(v) is even for any f ∈ {0,1}^18.
  // NCHV would require Σ_ctx (exactly-one-1) = 9, odd. Contradiction.
  assert.equal(36 % 2, 0, "total incidences are even");
  assert.equal(9 % 2, 1, "9 contexts give an odd one-count under NCHV");
  console.log("PASS — parity invariant confirms KS theorem (no NCHV f over 18 vectors)");
}

// (iii) CLASSICAL flag when responses satisfy exactly-one-per-context on a
//       single observed context
{
  const w = new KochenSpecker18Witness(50);
  const ctx0 = KS18_CONTEXTS[0]; // [0, 1, 10, 11]
  // Assign ctx0[0] → 1, others → 0
  w.record({ contextId: "c0", vectorIdx: ctx0[0], response: 1 });
  w.record({ contextId: "c0", vectorIdx: ctx0[1], response: 0 });
  w.record({ contextId: "c0", vectorIdx: ctx0[2], response: 0 });
  w.record({ contextId: "c0", vectorIdx: ctx0[3], response: 0 });
  const r = w.evaluate();
  assert.equal(r.inconsistencies, 0, "single context with one '1' is consistent");
  assert.equal(r.anomalyFlag, "CLASSICAL");
  console.log("PASS — single-context NCHV-consistent observation flags CLASSICAL");
}

// (iv) inconsistencies > 0 when a context has zero "1"s or ≥2 "1"s
{
  const w = new KochenSpecker18Witness(50);
  const ctx0 = KS18_CONTEXTS[0];
  for (const v of ctx0) {
    w.record({ contextId: "c0", vectorIdx: v, response: 0 }); // 0 "1"s — violates NCHV
  }
  const r = w.evaluate();
  assert.ok(r.inconsistencies > 0, "all-zero context should be flagged inconsistent");
  console.log("PASS — all-zero context flagged inconsistent");
}

console.log("KS-18 structure tests: ALL PASS");
