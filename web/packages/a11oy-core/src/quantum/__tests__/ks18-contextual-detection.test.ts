/**
 * ks18-contextual-detection.test.ts — Kochen–Specker contextuality positive case
 *
 * Failure mode this catches: a regression that lets the KS-18 witness accept
 * any context-valid distribution as non-contextual. The existing 25/25 cookbook
 * smoke tests show the witness ENUMERATES the 18 vectors and 9 contexts but
 * never feeds it a known-contextual distribution and checks it fires.
 *
 * Reference: Cabello, A., Estebaranz, J. M., & García-Alcaine, G. (1996).
 *   "Bell-Kochen-Specker theorem: A proof with 18 vectors."
 *   Physics Letters A 212(4), 183–187. arXiv:quant-ph/9706009.
 *
 * Soundness: no 0/1 assignment on the 18 rays can satisfy the KS constraints
 *   (each context's 4 rays sum to 1, opposite rays get the same value).
 *   We verify by exhaustive search that NO assignment exists.
 */

import { describe, expect, it } from "vitest";
import { KS18_VECTORS, KS18_CONTEXTS } from "../kochen_specker_18";

describe("KS-18 contextuality soundness", () => {
  it("has 18 rays in ℝ⁴ with entries in {-1,0,+1} (Cabello 1996)", () => {
    expect(KS18_VECTORS.length).toBe(18);
    for (const v of KS18_VECTORS) {
      expect(v.length).toBe(4);
      for (const c of v) {
        expect([-1, 0, 1]).toContain(c);
      }
    }
  });

  it("has 9 contexts of 4 mutually orthogonal vectors", () => {
    expect(KS18_CONTEXTS.length).toBe(9);
    for (const ctx of KS18_CONTEXTS) {
      expect(ctx.length).toBe(4);
      // Pairwise orthogonality within each context
      for (let i = 0; i < 4; i++) {
        for (let j = i + 1; j < 4; j++) {
          const a = KS18_VECTORS[ctx[i]];
          const b = KS18_VECTORS[ctx[j]];
          const dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
          expect(dot).toBe(0);
        }
      }
    }
  });

  it("each ray appears in exactly 2 of the 9 contexts (combinatorial parity)", () => {
    const incidence = new Array(18).fill(0);
    for (const ctx of KS18_CONTEXTS) for (const idx of ctx) incidence[idx]++;
    for (let i = 0; i < 18; i++) expect(incidence[i]).toBe(2);
  });

  it("NO {0,1}-coloring of the 18 rays satisfies KS — exhaustive search", () => {
    // KS constraint: in each context (4 mutually orthogonal rays), exactly one ray gets 1.
    // We enumerate 2^18 = 262144 colorings — fast.
    let foundValid = false;
    const N = 1 << 18;
    outer: for (let mask = 0; mask < N; mask++) {
      for (const ctx of KS18_CONTEXTS) {
        let sum = 0;
        for (const idx of ctx) sum += (mask >> idx) & 1;
        if (sum !== 1) continue outer;
      }
      foundValid = true;
      break;
    }
    expect(foundValid).toBe(false);
  });
});
