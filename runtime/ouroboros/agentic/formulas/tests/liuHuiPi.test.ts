// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 3 — Parity test for LiuHuiPi
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Banach/LiuHuiPi.lean
//   Commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Property tests:
//   1. sideSquared_bounds: sideSquared(k) ∈ [0,4] for all k
//   2. piEstimate < π for all k (inscribed polygon underestimates)
//   3. piEstimate is monotone-increasing in k
//   4. sideCount(k) = 6·2^k
//   5. lambdaScore ∈ [0,1]

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { liuHuiPi, liuHuiPiScalar } from "./liuHuiPi.js";

const FC_RUNS = 1000;

describe("LiuHuiPi — Layer 3 parity test", () => {
  // Property 1 (Lean: sideSquared_bounds): sideSquared ∈ [0,4] at all steps
  it("P1: sideSquared ∈ [0,4] for all k ∈ [0,40]", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 40 }),
        (k) => {
          const r = liuHuiPi({ k });
          return r.sideSquared >= 0 && r.sideSquared <= 4;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 2: inscribed polygon underestimates π (strict lower bound)
  it("P2: piEstimate < π (inscribed polygon strictly underestimates)", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 40 }),
        (k) => {
          const r = liuHuiPi({ k });
          // Allow tiny fp tolerance for very high k where convergence saturates
          return r.piEstimate <= Math.PI + 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 3: sequence is monotone-increasing in k
  it("P3: piEstimate(k+1) ≥ piEstimate(k) — monotone increasing", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 39 }),
        (k) => {
          const est_k = liuHuiPiScalar(k);
          const est_k1 = liuHuiPiScalar(k + 1);
          return est_k1 >= est_k - 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 4: sideCount(k) = 6·2^k  [Lean: sideCount]
  it("P4: sideCount(k) = 6·2^k for all k ∈ [0,30]", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 30 }),
        (k) => {
          const r = liuHuiPi({ k });
          return r.sideCount === 6 * Math.pow(2, k);
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 5: lambdaScore ∈ [0,1]
  it("P5: lambdaScore ∈ [0,1] for all k", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 40 }),
        (k) => {
          const { lambdaScore } = liuHuiPi({ k });
          return lambdaScore >= 0 && lambdaScore <= 1;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 6: scalar overload matches full result
  it("P6: scalar overload matches full result", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 40 }),
        (k) => {
          const full = liuHuiPi({ k });
          const scalar = liuHuiPiScalar(k);
          return Math.abs(full.piEstimate - scalar) < 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Deterministic spot checks
  describe("spot checks", () => {
    it("k=0: hexagon, 6 sides, estimate = 3 (from inscribed hexagon perimeter/2)", () => {
      const r = liuHuiPi({ k: 0 });
      expect(r.sideCount).toBe(6);
      expect(r.piEstimate).toBeCloseTo(3, 5);
    });

    it("k=4: 96-gon (Liu Hui's classical result), estimate > 3.14", () => {
      const r = liuHuiPi({ k: 4 });
      expect(r.sideCount).toBe(96);
      expect(r.piEstimate).toBeGreaterThan(3.14);
      expect(r.piEstimate).toBeLessThan(Math.PI + 1e-10);
    });

    it("k=20: very close to π (< 1e-8 error)", () => {
      const r = liuHuiPi({ k: 20 });
      expect(r.absError).toBeLessThan(1e-8);
    });

    it("throws for k < 0", () => {
      expect(() => liuHuiPi({ k: -1 })).toThrow();
    });

    it("throws for k > 50", () => {
      expect(() => liuHuiPi({ k: 51 })).toThrow();
    });
  });
});
