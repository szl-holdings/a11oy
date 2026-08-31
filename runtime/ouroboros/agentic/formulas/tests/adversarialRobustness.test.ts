// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 3 — Parity test for AdversarialRobustness
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Composition/AdversarialRobustness.lean
//   Commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Property tests:
//   1. epsilon2 = lipschitz1 * lipschitz2 * delta (composition rule)
//   2. composedLipschitz = lipschitz1 * lipschitz2
//   3. robust is true for all valid (positive) inputs
//   4. lambdaScore ∈ (0,1]
//   5. epsilon2 is monotone-increasing in delta

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { adversarialRobustness, adversarialRobustnessScalar } from "./adversarialRobustness.js";

const FC_RUNS = 1000;

// Positive finite floats bounded to avoid overflow
const posFloat = () => fc.float({ min: 1e-6, max: 1e6, noNaN: true });

describe("AdversarialRobustness — Layer 3 parity test", () => {
  // Property 1 (Lean: robustness_preserved_by_composition):
  // ε₂ = L₁·L₂·δ (the composed output perturbation bound)
  it("P1: epsilon2 = lipschitz1 * lipschitz2 * delta exactly", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        posFloat(),
        (l1, l2, delta) => {
          const r = adversarialRobustness({ lipschitz1: l1, lipschitz2: l2, delta });
          const expected = l1 * l2 * delta;
          const tol = Math.max(expected, 1) * 1e-10;
          return Math.abs(r.epsilon2 - expected) < tol;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 2: composedLipschitz = L₁·L₂
  it("P2: composedLipschitz = lipschitz1 * lipschitz2", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        posFloat(),
        (l1, l2, delta) => {
          const r = adversarialRobustness({ lipschitz1: l1, lipschitz2: l2, delta });
          const expected = l1 * l2;
          const tol = Math.max(expected, 1) * 1e-10;
          return Math.abs(r.composedLipschitz - expected) < tol;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 3: robust is always true for valid positive inputs
  it("P3: robust === true for all positive finite inputs", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        posFloat(),
        (l1, l2, delta) => {
          return adversarialRobustness({ lipschitz1: l1, lipschitz2: l2, delta }).robust === true;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 4: lambdaScore ∈ (0,1]
  it("P4: lambdaScore ∈ (0,1] for all valid inputs", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        posFloat(),
        (l1, l2, delta) => {
          const { lambdaScore } = adversarialRobustness({ lipschitz1: l1, lipschitz2: l2, delta });
          return lambdaScore > 0 && lambdaScore <= 1;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 5: epsilon2 is monotone-increasing in delta (fixed L₁, L₂)
  it("P5: epsilon2 is monotone-increasing in delta", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        fc.float({ min: 1e-6, max: 1e5, noNaN: true }),  // delta1
        fc.float({ min: 1e-6, max: 1e5, noNaN: true }),  // delta2
        (l1, l2, d1, d2) => {
          if (d1 > d2) return true; // only test d1 ≤ d2
          const e1 = adversarialRobustnessScalar(l1, l2, d1);
          const e2 = adversarialRobustnessScalar(l1, l2, d2);
          return e1 <= e2 + 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 6: scalar overload matches full result
  it("P6: scalar overload matches full result epsilon2", () => {
    fc.assert(
      fc.property(
        posFloat(),
        posFloat(),
        posFloat(),
        (l1, l2, delta) => {
          const full = adversarialRobustness({ lipschitz1: l1, lipschitz2: l2, delta });
          const scalar = adversarialRobustnessScalar(l1, l2, delta);
          return Math.abs(full.epsilon2 - scalar) < 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Deterministic spot checks
  describe("spot checks", () => {
    it("L1=2, L2=3, δ=0.1 → ε₁=0.2, ε₂=0.6, composedL=6", () => {
      const r = adversarialRobustness({ lipschitz1: 2, lipschitz2: 3, delta: 0.1 });
      expect(r.epsilon1).toBeCloseTo(0.2, 10);
      expect(r.epsilon2).toBeCloseTo(0.6, 10);
      expect(r.composedLipschitz).toBeCloseTo(6, 10);
      expect(r.robust).toBe(true);
    });

    it("L1=L2=1 (identity): epsilon2 = delta", () => {
      const r = adversarialRobustness({ lipschitz1: 1, lipschitz2: 1, delta: 0.5 });
      expect(r.epsilon2).toBeCloseTo(0.5, 10);
    });

    it("throws for L1 ≤ 0", () => {
      expect(() => adversarialRobustness({ lipschitz1: 0, lipschitz2: 1, delta: 1 })).toThrow();
    });

    it("throws for delta ≤ 0", () => {
      expect(() => adversarialRobustness({ lipschitz1: 1, lipschitz2: 1, delta: 0 })).toThrow();
    });
  });
});
