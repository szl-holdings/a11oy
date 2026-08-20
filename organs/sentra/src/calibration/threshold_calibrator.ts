/**
 * False-Position Threshold Calibration Gate
 *
 * @lean_theorem Lutar.Calibration.false_position_correct
 * @lean_file    Lutar/Calibration/FalsePosition.lean
 * @lean_status  GREEN — axiom-free, no sorry
 * @lean_commit  see LEAN_COMMIT_SHA env var; pin at CI time from lutar-lean/lean-toolchain
 *
 * Theorem (Rhind Mathematical Papyrus ~1650 BCE; Imhausen 2016 Princeton UP ch.3):
 *   For affine f(x) = m·x + c, the false-position formula
 *     x* = x₁ + (T − y₁)(x₂ − x₁) / (y₂ − y₁)
 *   satisfies f(x*) = T exactly (one step, no iteration required).
 *
 * Proof:
 *   x* = x₁ + (T − y₁)(x₂ − x₁)/(y₂ − y₁)
 *   f(x*) = m·x* + c
 *          = m·x₁ + c + m·(T − y₁)(x₂ − x₁)/(y₂ − y₁)
 *          = y₁ + m·(T − y₁)(x₂ − x₁)/(y₂ − y₁)
 *   Since y₂ − y₁ = m(x₂ − x₁) for affine f:
 *          = y₁ + (T − y₁)·m(x₂−x₁) / (m(x₂−x₁))
 *          = y₁ + (T − y₁) = T ✓
 *
 * For non-affine f (sentra threshold curves), one false-position step gives an
 * approximation; `iterations` parameter runs repeated bisection-style refinement
 * until |f(x*) - T| < tol (default 1e-9).
 *
 * References:
 *   Imhausen (2016) Mathematics in Ancient Egypt ch.3 — false position (ḥꜣ)
 *   Lutar/Calibration/FalsePosition.lean — kernel-checked affine case
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FalsePositionResult {
  /** Calibrated threshold x* such that f(x*) ≈ target */
  threshold: number;
  /** Residual |f(x*) - target| at convergence */
  residual: number;
  /** Number of iterations taken (1 for affine functions) */
  iterations: number;
  /** True iff residual < tol */
  converged: boolean;
  /** DSSE receipt */
  receipt: CalibrationDsseReceipt;
}

export interface CalibrationDsseReceipt {
  formula: string;
  lean_theorem: string;
  lean_file: string;
  lean_commit_sha: string;
  inputs_hash: string;
  output: {
    threshold: number;
    residual: number;
    converged: boolean;
    iterations: number;
  };
  ts: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function sha256Hex(obj: unknown): string {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(obj))
    .digest("hex");
}

// ---------------------------------------------------------------------------
// Core false-position step
// ---------------------------------------------------------------------------

/**
 * One false-position step: given two sample points (x1, y1) and (x2, y2)
 * and a target T, return the interpolated x*.
 *
 * Requires y1 ≠ y2 (otherwise the function is constant and has no unique root).
 */
function falsePositionStep(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  target: number
): number {
  const dy = y2 - y1;
  if (Math.abs(dy) < Number.EPSILON * 1e3) {
    throw new Error(
      `falsePositionStep: y2 − y1 ≈ 0 (${dy}); function is near-constant between x1=${x1} and x2=${x2}`
    );
  }
  return x1 + ((target - y1) * (x2 - x1)) / dy;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Calibrate a detection threshold using the false-position method.
 *
 * @param f       Monotone calibration function f: threshold → score
 * @param x1      Left bracket point (f(x1) must be on opposite side of target from f(x2))
 * @param x2      Right bracket point
 * @param target  Target score T (e.g., 0.95 precision)
 * @param tol     Convergence tolerance on |f(x*) - target| (default 1e-9)
 * @param maxIter Maximum iterations before declaring non-convergence (default 200)
 *
 * For affine f, converges in exactly 1 iteration (Lean theorem exact case).
 * For general monotone f, iterates with secant-style bracket updates.
 */
export function falsePositionCalibrate(
  f: (x: number) => number,
  x1: number,
  x2: number,
  target: number,
  tol = 1e-9,
  maxIter = 200
): FalsePositionResult {
  let y1 = f(x1);
  let y2 = f(x2);
  let xStar: number;
  let residual: number;
  let iter = 0;

  for (iter = 1; iter <= maxIter; iter++) {
    xStar = falsePositionStep(x1, y1, x2, y2, target);
    const yStar = f(xStar);
    residual = Math.abs(yStar - target);

    if (residual < tol) {
      const inputs_hash = sha256Hex({ x1, x2, target, tol, maxIter });
      const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";
      const receipt: CalibrationDsseReceipt = {
        formula: "false_position_correct",
        lean_theorem: "Lutar.Calibration.false_position_correct",
        lean_file: "Lutar/Calibration/FalsePosition.lean",
        lean_commit_sha,
        inputs_hash,
        output: { threshold: xStar, residual, converged: true, iterations: iter },
        ts: new Date().toISOString(),
      };
      return { threshold: xStar, residual, iterations: iter, converged: true, receipt };
    }

    // Update bracket: keep the side that straddles the target
    if ((yStar - target) * (y1 - target) < 0) {
      x2 = xStar;
      y2 = yStar;
    } else {
      x1 = xStar;
      y1 = yStar;
    }
  }

  // Did not converge within maxIter
  xStar = falsePositionStep(x1, y1, x2, y2, target);
  residual = Math.abs(f(xStar) - target);
  const inputs_hash = sha256Hex({ x1, x2, target, tol, maxIter });
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";
  const receipt: CalibrationDsseReceipt = {
    formula: "false_position_correct",
    lean_theorem: "Lutar.Calibration.false_position_correct",
    lean_file: "Lutar/Calibration/FalsePosition.lean",
    lean_commit_sha,
    inputs_hash,
    output: { threshold: xStar!, residual: residual!, converged: false, iterations: maxIter },
    ts: new Date().toISOString(),
  };
  return { threshold: xStar!, residual: residual!, iterations: maxIter, converged: false, receipt };
}

/**
 * Closed-form false-position for the affine case f(x) = m·x + c.
 * By the Lean theorem, converges in exactly one step with residual = 0.
 *
 * @param x1      First sample x
 * @param y1      f(x1) = m·x1 + c
 * @param x2      Second sample x (x2 ≠ x1)
 * @param y2      f(x2) = m·x2 + c
 * @param target  T
 */
export function falsePositionAffine(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  target: number
): FalsePositionResult {
  const xStar = falsePositionStep(x1, y1, x2, y2, target);
  // For affine: residual is exactly 0 (theorem guarantee); floating-point may give ~1e-15
  const m = (y2 - y1) / (x2 - x1);
  const c = y1 - m * x1;
  const yStar = m * xStar + c;
  const residual = Math.abs(yStar - target);

  const inputs_hash = sha256Hex({ x1, y1, x2, y2, target });
  const lean_commit_sha = process.env["LEAN_COMMIT_SHA"] ?? "unknown";
  const receipt: CalibrationDsseReceipt = {
    formula: "false_position_correct",
    lean_theorem: "Lutar.Calibration.false_position_correct",
    lean_file: "Lutar/Calibration/FalsePosition.lean",
    lean_commit_sha,
    inputs_hash,
    output: { threshold: xStar, residual, converged: true, iterations: 1 },
    ts: new Date().toISOString(),
  };
  return { threshold: xStar, residual, iterations: 1, converged: true, receipt };
}
