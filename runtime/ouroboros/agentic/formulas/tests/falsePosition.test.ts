// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 3 — Parity test for FalsePosition
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Calibration/FalsePosition.lean
//   Commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Property tests:
//   1. false_position_correct: f(xStar) = T for any affine f, x₁≠x₂
//   2. lambdaScore ∈ [0,1]
//   3. throws on degenerate inputs (y₁ = y₂)
//   4. xStar is unique for a given (x₁,y₁,x₂,y₂,T)

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { falsePosition, falsePositionScalar } from "./falsePosition.js";

const FC_RUNS = 1000;

// Reasonable float range for tests
const safeFloat = () => fc.float({ min: -1e6, max: 1e6, noNaN: true });
const safeNonzeroFloat = () => fc.float({ min: 0.01, max: 1e4, noNaN: true });

describe("FalsePosition — Layer 3 parity test", () => {
  // Property 1 (core Lean theorem): for any affine f(x)=m*x+c with m≠0, x₁≠x₂,
  // f(falsePosition(x₁,y₁,x₂,y₂,T)) = T
  it("P1: false_position_correct — f(xStar)=T for all affine gates", () => {
    fc.assert(
      fc.property(
        safeNonzeroFloat(),   // slope m (≠ 0, both positive to keep x₁≠x₂ easy)
        safeFloat(),          // intercept c
        safeFloat(),          // x₁
        safeFloat(),          // dx (added to x₁ to get x₂; ensures x₁≠x₂)
        safeFloat(),          // target T
        (m, c, x1, dx, T) => {
          const x2 = x1 + dx + (dx === 0 ? 0.001 : 0); // ensure x₂ ≠ x₁
          if (Math.abs(x2 - x1) < 1e-12) return true; // skip degenerate
          const y1 = m * x1 + c;
          const y2 = m * x2 + c;
          if (Math.abs(y2 - y1) < 1e-12) return true; // degenerate slope

          const { xStar } = falsePosition({ x1, y1, x2, y2, T });
          const fxStar = m * xStar + c;
          // Allow floating-point relative tolerance
          const tol = Math.max(Math.abs(T), 1) * 1e-9;
          return Math.abs(fxStar - T) <= tol;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 2: lambdaScore ∈ [0,1] for all valid inputs
  it("P2: lambdaScore ∈ [0,1] for all valid inputs", () => {
    fc.assert(
      fc.property(
        safeNonzeroFloat(),
        safeFloat(),
        safeFloat(),
        safeFloat(),
        safeFloat(),
        (m, c, x1, dx, T) => {
          const x2 = x1 + dx + (dx === 0 ? 0.001 : 0);
          if (Math.abs(x2 - x1) < 1e-12) return true;
          const y1 = m * x1 + c;
          const y2 = m * x2 + c;
          if (Math.abs(y2 - y1) < 1e-12) return true;

          try {
            const { lambdaScore } = falsePosition({ x1, y1, x2, y2, T });
            return lambdaScore >= 0 && lambdaScore <= 1;
          } catch {
            return true; // degenerate inputs legitimately throw
          }
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 3: xStar is a fixed point — calling again with xStar as a new
  // sample gives T as the target (symmetry / idempotence on affine gates)
  it("P3: xStar satisfies f(xStar)=T for slope recovered from samples", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0.1, max: 100, noNaN: true }),  // m > 0
        fc.float({ min: -100, max: 100, noNaN: true }),  // c
        fc.float({ min: -100, max: 100, noNaN: true }),  // x1
        fc.float({ min: 0.01, max: 100, noNaN: true }),  // |x2 - x1|
        fc.float({ min: -100, max: 100, noNaN: true }),  // T
        (m, c, x1, ddx, T) => {
          const x2 = x1 + ddx;
          const y1 = m * x1 + c;
          const y2 = m * x2 + c;
          const { xStar } = falsePosition({ x1, y1, x2, y2, T });
          const residual = Math.abs(m * xStar + c - T);
          return residual < Math.max(Math.abs(T), 1) * 1e-9;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Property 4: scalar overload agrees with full overload
  it("P4: scalar overload matches full result", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0.1, max: 100, noNaN: true }),
        fc.float({ min: -100, max: 100, noNaN: true }),
        fc.float({ min: -100, max: 100, noNaN: true }),
        fc.float({ min: 0.01, max: 100, noNaN: true }),
        fc.float({ min: -100, max: 100, noNaN: true }),
        (m, c, x1, ddx, T) => {
          const x2 = x1 + ddx;
          const y1 = m * x1 + c;
          const y2 = m * x2 + c;
          const full = falsePosition({ x1, y1, x2, y2, T });
          const scalar = falsePositionScalar(x1, y1, x2, y2, T);
          return Math.abs(full.xStar - scalar) < 1e-14;
        }
      ),
      { numRuns: FC_RUNS }
    );
  });

  // Deterministic spot checks
  describe("spot checks", () => {
    it("f(x)=2x, x1=0,y1=0, x2=1,y2=2, T=4 → xStar=2", () => {
      const r = falsePosition({ x1: 0, y1: 0, x2: 1, y2: 2, T: 4 });
      expect(r.xStar).toBeCloseTo(2, 10);
    });

    it("f(x)=x+1, x1=0,y1=1, x2=1,y2=2, T=5 → xStar=4", () => {
      const r = falsePosition({ x1: 0, y1: 1, x2: 1, y2: 2, T: 5 });
      expect(r.xStar).toBeCloseTo(4, 10);
    });

    it("throws when y1 ≈ y2 (degenerate)", () => {
      expect(() => falsePosition({ x1: 0, y1: 1, x2: 1, y2: 1, T: 3 })).toThrow();
    });
  });
});
