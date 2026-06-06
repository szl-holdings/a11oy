// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 3 — Parity test for MadhavaBound
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/PACBayes/MadhavaBound.lean
//   Commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Property tests:
//   1. remainderBound ≥ 0 for all valid (x, N)          [Lean: madhavaRemainderBound_nonneg]
//   2. |arctan(x) − partial| ≤ remainderBound for |x|≤1 [Lean: MadhavaBound]
//   3. remainderBound decreases as N increases           [Leibniz monotone-decreasing terms]
//   4. partial converges to arctan(x)                   [alternating series convergence]

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { madhavaBound, madhavaBoundScalar } from "./madhavaBound.js";

// fast-check: 1000 runs per property
const FC_RUNS = 1000;

describe("MadhavaBound — Layer 3 parity test", () => {
  // Property 1: remainderBound is always non-negative (Lean: madhavaRemainderBound_nonneg)
  it("P1: remainderBound ≥ 0 for all valid (x, N)", () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 50 }),
        (x, N) => {
          const r = madhavaBound({ x, N });
          return r.remainderBound >= 0;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 2: the partial sum is within remainderBound of arctan(x)
  // (This is the core Madhava-Leibniz remainder theorem statement)
  it("P2: |arctan(x) − partial| ≤ remainderBound for |x| ≤ 1", () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 30 }),
        (x, N) => {
          const r = madhavaBound({ x, N });
          const actualArctan = Math.atan(x);
          const residual = Math.abs(actualArctan - r.partial);
          // Allow small floating-point slack (1 ULP tolerance)
          const fpSlack = r.remainderBound * 1e-10 + Number.EPSILON * 8;
          return residual <= r.remainderBound + fpSlack;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 3: bound is monotone-decreasing in N for fixed x ≠ 0
  it("P3: remainderBound(x,N+1) ≤ remainderBound(x,N) for x ≠ 0", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0.01, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 49 }),
        (x, N) => {
          const rN = madhavaBoundScalar(x, N);
          const rN1 = madhavaBoundScalar(x, N + 1);
          // |x|^(2(N+1)+1)/(2(N+1)+1) ≤ |x|^(2N+1)/(2N+1) for 0<|x|≤1
          return rN1 <= rN + Number.EPSILON * 8;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 4: at x = 0, partial sum = 0 and bound = 0
  it("P4: at x=0, partial=0 and bound=0 for all N", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100 }),
        (N) => {
          const r = madhavaBound({ x: 0, N });
          return r.partial === 0 && r.remainderBound === 0;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 5: boundNonneg is always true (follows from theorem)
  it("P5: boundNonneg flag is always true", () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 50 }),
        (x, N) => {
          return madhavaBound({ x, N }).boundNonneg === true;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 6: lambdaScore ∈ [0,1]
  it("P6: lambdaScore ∈ [0,1] for all valid inputs", () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 50 }),
        (x, N) => {
          const { lambdaScore } = madhavaBound({ x, N });
          return lambdaScore >= 0 && lambdaScore <= 1;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Deterministic spot checks
  describe("spot checks", () => {
    it("N=1, x=1: partial=1, bound=1/3 ≈ 0.333", () => {
      const r = madhavaBound({ x: 1, N: 1 });
      expect(r.partial).toBeCloseTo(1, 10);
      expect(r.remainderBound).toBeCloseTo(1 / 3, 10);
    });

    it("N=2, x=1: partial=1-1/3=0.6667, bound=1/5=0.2", () => {
      const r = madhavaBound({ x: 1, N: 2 });
      expect(r.partial).toBeCloseTo(1 - 1 / 3, 10);
      expect(r.remainderBound).toBeCloseTo(1 / 5, 10);
    });

    it("arctan(1) = π/4 recovered within bound for large N", () => {
      const r = madhavaBound({ x: 1, N: 1000 });
      expect(Math.abs(r.partial - Math.PI / 4)).toBeLessThan(r.remainderBound + 1e-12);
    });

    it("throws for |x| > 1", () => {
      expect(() => madhavaBound({ x: 1.1, N: 5 })).toThrow();
    });

    it("throws for N < 1", () => {
      expect(() => madhavaBound({ x: 0.5, N: 0 })).toThrow();
    });
  });
});
