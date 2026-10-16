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
//   1. reported remainderBound ≥ 0. The flag does not replay Lean.
//   2. float residual |Math.atan(x) − partial| versus the reported expression.
//      This is not a Lean proof that the limit is arctan, and a flushed 0 is
//      SUBNORMAL_OR_UNDERFLOW rather than a proven error of zero.
//   3. reported remainder decreases as N increases on the finite spot range
//   4. at x = 0 the partial and the reported bound are 0

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

  // Property 2: float residual against Math.atan. Not a Lean arctan theorem.
  it("P2: |Math.atan(x) − partial| ≤ reported remainder for |x| ≤ 1", () => {
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

  // Property 5: the reported float is nonnegative. This does not replay Lean.
  it("P5: reported boundNonneg flag is true without claiming a Lean replay", () => {
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

  // Property 6: a finite lambda is in [0,1]. Underflow does not report 1.
  it("P6: lambdaScore is in [0,1] only for a finite remainder", () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 50 }),
        (x, N) => {
          const { lambdaScore, remainderBoundState } = madhavaBound({ x, N });
          if (remainderBoundState === "SUBNORMAL_OR_UNDERFLOW") return lambdaScore === null;
          return typeof lambdaScore === "number" && lambdaScore >= 0 && lambdaScore <= 1;
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

    it("x=0.5 N=600 is underflow and does not report a perfect lambda", () => {
      const r = madhavaBound({ x: 0.5, N: 600 });
      expect(r.remainderBoundState).toBe("SUBNORMAL_OR_UNDERFLOW");
      expect(r.remainderBound).toBe(0);
      expect(r.lambdaScore).toBeNull();
      expect(r.accuracyClaim).toBe("NOT_ASSERTED");
      expect(r.leanScope).toBe("nonnegativity_only");
      expect(r.floatTruncationError).toBe("NOT_BOUNDED");
    });

    it("throws above the truncation cap", () => {
      expect(() => madhavaBound({ x: 0.5, N: 10001 })).toThrow();
    });
  });
});
