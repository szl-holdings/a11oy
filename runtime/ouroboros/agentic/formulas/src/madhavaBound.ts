// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime for the classical Mādhava first-omitted term.
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/PACBayes/MadhavaBound.lean
//   Commit SHA (main pin used by this module): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Pinned Lean result:
//   madhavaRemainderBound_nonneg : the named bound expression is nonnegative.
// The classical statement
//   |arctan(x) - partial(x,N)| ≤ |x|^(2N+1)/(2N+1)
// is not that Lean theorem. This module does not claim a float64 error bound.
//
// References:
//   Plofker 2009, Mathematics in India, Princeton UP §7.4
//   Joseph 2010, The Crest of the Peacock, 3rd ed., Princeton UP ch.9

/** Inputs for the classical Mādhava remainder expression. */
export interface MadhavaBoundOpts {
  /** |x| must satisfy 0 ≤ |x| ≤ 1 for this expression. */
  x: number;
  /** Truncation index. Integer N in 1..10000. */
  N: number;
}

/** Result of madhavaBound. */
export interface MadhavaBoundResult {
  /** The N-term partial sum: Σ_{n=0}^{N-1} (-1)^n x^{2n+1}/(2n+1). */
  partial: number;
  /**
   * Reported classical first-omitted-term value.
   * 0 when the exact expression is below the normal float64 range.
   */
  remainderBound: number;
  remainderBoundState: "FINITE" | "SUBNORMAL_OR_UNDERFLOW";
  /**
   * True when the reported float is >= 0.
   * This flag does not replay the Lean proof.
   */
  boundNonneg: boolean;
  /** Null when remainderBoundState is SUBNORMAL_OR_UNDERFLOW. Not an accuracy score. */
  lambdaScore: number | null;
  accuracyClaim: "NOT_ASSERTED";
  leanScope: "nonnegativity_only";
  floatTruncationError: "NOT_BOUNDED";
  comparison: "log_space_first_omitted_term";
}

const MADHAVA_MAX_TERMS = 10_000;
const FLOAT_MIN_NORMAL_LOG = Math.log(2.2250738585072014e-308);

function logBound(absX: number, n: number): number {
  if (absX === 0) return Number.NEGATIVE_INFINITY;
  if (absX === 1) return -Math.log(2 * n + 1);
  return (2 * n + 1) * Math.log(absX) - Math.log(2 * n + 1);
}

function classicalRemainder(absX: number, n: number): { value: number; state: MadhavaBoundResult["remainderBoundState"] } {
  const logValue = logBound(absX, n);
  if (absX === 0) return { value: 0, state: "FINITE" };
  if (absX === 1) return { value: 1 / (2 * n + 1), state: "FINITE" };
  if (logValue < FLOAT_MIN_NORMAL_LOG) return { value: 0, state: "SUBNORMAL_OR_UNDERFLOW" };
  const value = Math.exp(logValue);
  if (value === 0 || !Number.isFinite(value)) return { value: 0, state: "SUBNORMAL_OR_UNDERFLOW" };
  return { value, state: "FINITE" };
}

/**
 * Compute the partial sum and the classical first-omitted-term expression.
 *
 * Lean `madhavaRemainderBound_nonneg` is nonnegativity only.
 * accuracyClaim is NOT_ASSERTED.
 *
 * @throws if |x| > 1 or N is outside 1..10000
 */
export function madhavaBound(opts: MadhavaBoundOpts): MadhavaBoundResult {
  const { x, N } = opts;
  if (typeof x !== "number" || !Number.isFinite(x)) throw new Error("x must be finite");
  if (!Number.isInteger(N) || N < 1 || N > MADHAVA_MAX_TERMS) {
    throw new Error(`N must be an integer in 1..${MADHAVA_MAX_TERMS}`);
  }
  if (Math.abs(x) > 1 + Number.EPSILON)
    throw new Error(`|x| must be ≤ 1 for Madhava bound; got |x| = ${Math.abs(x)}`);

  let partial = 0;
  for (let n = 0; n < N; n++) {
    const sign = n % 2 === 0 ? 1 : -1;
    partial += (sign * Math.pow(x, 2 * n + 1)) / (2 * n + 1);
  }

  const remainder = classicalRemainder(Math.abs(x), N);
  const boundNonneg = remainder.value >= 0;
  const lambdaScore = remainder.state === "FINITE"
    ? Math.max(0, Math.min(1, 1 - remainder.value))
    : null;

  return {
    partial,
    remainderBound: remainder.value,
    remainderBoundState: remainder.state,
    boundNonneg,
    lambdaScore,
    accuracyClaim: "NOT_ASSERTED",
    leanScope: "nonnegativity_only",
    floatTruncationError: "NOT_BOUNDED",
    comparison: "log_space_first_omitted_term",
  };
}

/**
 * Scalar overload: returns only the reported remainder expression.
 * A 0 result can mean a true zero or SUBNORMAL_OR_UNDERFLOW. Call madhavaBound
 * when the state label is required.
 */
export function madhavaBoundScalar(x: number, N: number): number {
  return madhavaBound({ x, N }).remainderBound;
}
