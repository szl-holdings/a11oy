// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime mirror of Lean theorem `MadhavaBound`
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/PACBayes/MadhavaBound.lean
//   Blob SHA: c8c07dc93a5dbfd6350673065c81b50eb28b940b
//   Commit SHA (main): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Theorem statement (Lean):
//   madhavaRemainderBound_nonneg : ∀ x N, 0 ≤ madhavaRemainderBound x N
//   MadhavaBound (main): |arctan(x) - madhavaArctanPartial(x,N)| ≤ |x|^(2N+1)/(2N+1)
//
// Mādhava of Sangamagrama (~1340–1425 CE) alternating-series remainder bound:
// for |x| ≤ 1, the N-term arctan partial sum satisfies
//   |arctan(x) − Σ_{n=0}^{N-1} (-1)^n x^{2n+1}/(2n+1)| ≤ |x|^{2N+1}/(2N+1)
//
// PAC-Bayes interpretation: the bound governs truncation error in the
// Madhava-Leibniz π expansion used as a calibration sentinel in the SZL
// governance pipeline.
//
// References:
//   Plofker 2009, Mathematics in India, Princeton UP §7.4
//   Joseph 2010, The Crest of the Peacock, 3rd ed., Princeton UP ch.9

/** Inputs for the Mādhava arctan remainder-bound computation. */
export interface MadhavaBoundOpts {
  /** |x| must satisfy 0 ≤ |x| ≤ 1 for the Leibniz criterion to apply. */
  x: number;
  /** Number of terms N ≥ 1 already summed. */
  N: number;
}

/** Result of madhavaBound. */
export interface MadhavaBoundResult {
  /** The N-term partial sum: Σ_{n=0}^{N-1} (-1)^n x^{2n+1}/(2n+1). */
  partial: number;
  /** The remainder bound: |x|^{2N+1}/(2N+1). */
  remainderBound: number;
  /** Whether the bound is provably non-negative (always true by theorem). */
  boundNonneg: boolean;
  /** Λ-score: 1 − remainderBound (saturates at 1 when bound→0). */
  lambdaScore: number;
}

/**
 * Compute the Mādhava arctan partial sum and its Leibniz remainder bound.
 *
 * Lean theorem: `madhavaRemainderBound_nonneg` and `MadhavaBound`
 * Lean file: Lutar/PACBayes/MadhavaBound.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * @throws if |x| > 1 or N < 1 (bound only applies in those ranges)
 */
export function madhavaBound(opts: MadhavaBoundOpts): MadhavaBoundResult {
  const { x, N } = opts;
  if (!Number.isFinite(x)) throw new Error("x must be finite");
  if (!Number.isInteger(N) || N < 1) throw new Error("N must be a positive integer");
  if (Math.abs(x) > 1 + Number.EPSILON)
    throw new Error(`|x| must be ≤ 1 for Madhava bound; got |x| = ${Math.abs(x)}`);

  // Partial sum: Σ_{n=0}^{N-1} (-1)^n * x^(2n+1) / (2n+1)
  let partial = 0;
  for (let n = 0; n < N; n++) {
    const sign = n % 2 === 0 ? 1 : -1;
    const term = (sign * Math.pow(x, 2 * n + 1)) / (2 * n + 1);
    partial += term;
  }

  // Remainder bound: |x|^(2N+1) / (2N+1)  [Lean: madhavaRemainderBound]
  const remainderBound = Math.pow(Math.abs(x), 2 * N + 1) / (2 * N + 1);

  // By theorem, remainderBound ≥ 0 always (pow of |x| ≥ 0, denominator > 0)
  const boundNonneg = remainderBound >= 0;

  // Λ-score: 1 - bound, clamped to [0,1]
  const lambdaScore = Math.max(0, Math.min(1, 1 - remainderBound));

  return { partial, remainderBound, boundNonneg, lambdaScore };
}

/**
 * Scalar overload: returns only the remainder bound (≥ 0).
 * Used by the a11oy policy gate and OTel span wrapper.
 */
export function madhavaBoundScalar(x: number, N: number): number {
  return madhavaBound({ x, N }).remainderBound;
}
