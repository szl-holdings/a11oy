// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime mirror of Lean theorem `FalsePosition`
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Calibration/FalsePosition.lean
//   Blob SHA: 8a6624ce183ede9d634f4d251f53c57f54ffaae4
//   Commit SHA (main): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Theorem statement (Lean):
//   false_position_correct (m c x₁ x₂ T : ℝ) (hm : m ≠ 0) (hx : x₁ ≠ x₂) :
//     m * falsePosition(x₁, m*x₁+c, x₂, m*x₂+c, T) + c = T
//
// The Egyptian aha / false-position method (Rhind Mathematical Papyrus, ~1650 BCE):
// given an affine gate f(x) = m·x + c and two samples (x₁,y₁),(x₂,y₂) with
// y_i = m·x_i + c, the one-step correction recovers any target T exactly:
//   x* = x₁ + (T − y₁)·(x₂ − x₁)/(y₂ − y₁)
//
// References:
//   Imhausen 2016, Mathematics in Ancient Egypt, Princeton UP ch.3 §3.4
//   Robins & Shute 1987, The Rhind Mathematical Papyrus, British Museum Press

/** Inputs for the false-position correction step. */
export interface FalsePositionOpts {
  /** First sample input. */
  x1: number;
  /** First sample output y₁ = f(x₁). */
  y1: number;
  /** Second sample input (must differ from x₁). */
  x2: number;
  /** Second sample output y₂ = f(x₂). */
  y2: number;
  /** Target output value T. */
  T: number;
}

/** Result of falsePosition. */
export interface FalsePositionResult {
  /** The corrected input x* such that f(x*) = T for any affine f. */
  xStar: number;
  /** Λ-score: 1 when correction is exact; degrades with numerical drift. */
  lambdaScore: number;
}

/**
 * One-step false-position correction for an affine gate.
 *
 * Lean theorem: `false_position_correct`
 * Lean file: Lutar/Calibration/FalsePosition.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * Closed form: x* = x₁ + (T − y₁)·(x₂ − x₁)/(y₂ − y₁)
 *
 * @throws if y₁ === y₂ (degenerate: the two samples don't span a slope)
 */
export function falsePosition(opts: FalsePositionOpts): FalsePositionResult {
  const { x1, y1, x2, y2, T } = opts;
  for (const [name, v] of [["x1", x1], ["y1", y1], ["x2", x2], ["y2", y2], ["T", T]] as [string, number][]) {
    if (!Number.isFinite(v)) throw new Error(`${name} must be finite`);
  }
  const dy = y2 - y1;
  if (Math.abs(dy) < Number.EPSILON * Math.max(Math.abs(y1), Math.abs(y2), 1))
    throw new Error("y₁ = y₂: samples are degenerate (slope = 0)");

  const xStar = x1 + ((T - y1) * (x2 - x1)) / dy;

  // Λ-score: 1 − |f(x*) − T| / (1 + |T|), where f is reconstructed from samples
  // Since the theorem guarantees f(x*) = T for *exact* affine f, we measure
  // the floating-point residual as a proxy for numerical quality.
  const m = dy / (x2 - x1);
  const c = y1 - m * x1;
  const residual = Math.abs(m * xStar + c - T);
  const lambdaScore = Math.max(0, 1 - residual / (1 + Math.abs(T)));

  return { xStar, lambdaScore };
}

/**
 * Scalar overload: returns only the corrected input x*.
 * Used by the a11oy policy gate and OTel span wrapper.
 */
export function falsePositionScalar(x1: number, y1: number, x2: number, y2: number, T: number): number {
  return falsePosition({ x1, y1, x2, y2, T }).xStar;
}
