// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime mirror of Lean theorem `LiuHuiPi`
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Banach/LiuHuiPi.lean
//   Blob SHA: 3c98c3a608d2d204900737b72fac60e51025083b
//   Commit SHA (main): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Theorem statement (Lean):
//   sideSquared_bounds : ∀ n, 0 ≤ sideSquared n ∧ sideSquared n ≤ 4
//   liuHuiPi (k) = (6·2^k) * sqrt(sideSquared k) / 2
//
// Liu Hui's polygon-doubling method (3rd c. CE):
//   Start from regular hexagon inscribed in unit circle (s₀² = 1),
//   double sides via recurrence: s_{n+1}² = 2 − sqrt(4 − s_n²)
//   π estimate at step k: n_k * sqrt(s_k²) / 2, where n_k = 6·2^k
//   k=4 gives the 96-gon (Liu Hui's classical bound 3.141...).
//
// Banach interpretation: the sequence liuHuiPi(k) is monotone-increasing
// and bounded above by π — a contraction fixed-point argument.
//
// References:
//   Cullen 1996, Astronomy and Mathematics in Ancient China, CUP
//   Martzloff 1997, A History of Chinese Mathematics, Springer

/** Inputs for the Liu Hui π estimate. */
export interface LiuHuiPiOpts {
  /** Doubling step k ≥ 0. k=4 is Liu Hui's 96-gon. */
  k: number;
}

/** Result of liuHuiPi. */
export interface LiuHuiPiResult {
  /** Number of sides at step k: n_k = 6·2^k. */
  sideCount: number;
  /** Squared inscribed-side length at step k. */
  sideSquared: number;
  /** Polygon π estimate: n_k * sqrt(sideSquared) / 2. */
  piEstimate: number;
  /** Absolute error vs Math.PI. */
  absError: number;
  /** Λ-score: 1 − absError / π (measures proximity to true π). */
  lambdaScore: number;
}

/**
 * Compute Liu Hui's polygon-doubling estimate of π at step k.
 *
 * Lean theorem: `sideSquared_bounds`, `liuHuiPi`
 * Lean file: Lutar/Banach/LiuHuiPi.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * @throws if k is not a non-negative integer or exceeds 50 (floating-point saturation)
 */
export function liuHuiPi(opts: LiuHuiPiOpts): LiuHuiPiResult {
  const { k } = opts;
  if (!Number.isInteger(k) || k < 0) throw new Error("k must be a non-negative integer");
  if (k > 50) throw new Error("k > 50 saturates floating-point; result is unreliable");

  // Recurrence: sideSquared(0) = 1; sideSquared(n+1) = 2 − sqrt(4 − sideSquared(n))
  let sq = 1; // s₀² = 1 (hexagon inscribed in unit circle)
  for (let i = 0; i < k; i++) {
    sq = 2 - Math.sqrt(4 - sq);
  }

  // Theorem: sq ∈ [0, 4] for all n (sideSquared_bounds)
  if (sq < 0 || sq > 4) {
    throw new Error(`sideSquared invariant violated: got ${sq} at k=${k}`);
  }

  const sideCount = 6 * Math.pow(2, k);
  const piEstimate = (sideCount * Math.sqrt(sq)) / 2;
  const absError = Math.abs(piEstimate - Math.PI);
  const lambdaScore = Math.max(0, 1 - absError / Math.PI);

  return { sideCount, sideSquared: sq, piEstimate, absError, lambdaScore };
}

/**
 * Scalar overload: returns only the π estimate.
 * Used by the a11oy policy gate and OTel span wrapper.
 */
export function liuHuiPiScalar(k: number): number {
  return liuHuiPi({ k }).piEstimate;
}
