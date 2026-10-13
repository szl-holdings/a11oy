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
//   axiom liu_hui_pi_converges : some real limit exists.
//     That axiom does not identify the limit with π and does not prove
//     that this float64 function implements the real recurrence.
//
// Liu Hui's polygon-doubling method (3rd c. CE):
//   Start from regular hexagon inscribed in unit circle (s₀² = 1),
//   double sides via the real recurrence s_{n+1}² = 2 − sqrt(4 − s_n²).
//   For s_n² in (0, 4] that equals s_n² / (2 + sqrt(4 − s_n²)).
//   The rationalized form is the one evaluated here. The subtracted form
//   cancels in float64 and returns a zero estimate by k=27.
//   π estimate at step k: n_k * sqrt(s_k²) / 2, where n_k = 6·2^k
//   k=4 gives the 96-gon (Liu Hui's classical bound 3.141...).
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
 * Lean theorem: `sideSquared_bounds` (well-definedness). `liuHuiPi` is a definition.
 * Axiom `liu_hui_pi_converges` asserts only that some limit exists.
 * Lean file: Lutar/Banach/LiuHuiPi.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * @throws if k is not a non-negative integer or is outside the supported domain 0..50
 */
export function liuHuiPi(opts: LiuHuiPiOpts): LiuHuiPiResult {
  const { k } = opts;
  if (!Number.isInteger(k) || k < 0) throw new Error("k must be a non-negative integer");
  if (k > 50) throw new Error("k > 50 is outside the supported domain");

  // Rationalized Liu Hui step. On the reals, for sq in (0, 4]:
  //   2 - sqrt(4 - sq) = sq / (2 + sqrt(4 - sq))
  // Float64 subtraction collapses to 0 by k=27. The quotient does not.
  let sq = 1; // s₀² = 1 (hexagon inscribed in unit circle)
  for (let i = 0; i < k; i++) {
    const radicand = 4 - sq;
    if (!(radicand >= 0)) {
      throw new Error(`sideSquared invariant violated: radicand ${radicand} at step ${i}`);
    }
    sq = sq / (2 + Math.sqrt(radicand));
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
 * The policy gate keeps an inline copy of this recurrence. The numeric
 * gate test checks the two copies against the same reference.
 */
export function liuHuiPiScalar(k: number): number {
  return liuHuiPi({ k }).piEstimate;
}
