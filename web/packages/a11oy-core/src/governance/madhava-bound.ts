/**
 * R4-I1 — Madhava alternating-series bound (TH14, PAC-Bayes refinement)
 *
 * Madhava of Sangamagrama (~1340–1425 CE) discovered the alternating
 * series for arctan and π that bears his name:
 *
 *     arctan(x) = Σ_{n=0}^{∞} (-1)^n · x^(2n+1) / (2n+1)
 *
 * — three centuries before Gregory and Leibniz [Plofker 2009 §7.4,
 *  Joseph 2010 ch. 9]. For an alternating series with monotone-decreasing
 * absolute terms, the truncation error after N terms is bounded by the
 * magnitude of the first omitted term (Leibniz criterion / Madhava
 * remainder):
 *
 *     | Σ_{n=0}^{∞} a_n  −  Σ_{n=0}^{N−1} a_n |  ≤  |a_N|.
 *
 * **Use in TH14 PAC-Bayes refinement.** When the posterior log-likelihood
 * estimator is expressed as an alternating series in some parameter
 * (e.g. a series representation of the conformal calibration map), the
 * Madhava bound supplies a *deterministic* tightening of the PAC-Bayes
 * slack term in TH13 — instead of bounding the truncation by `+∞`, we
 * bound it by the next-term magnitude. The McAllester bound becomes
 *
 *     R(Q) ≤ R̂_N(Q) + slack_TH13 + madhavaRemainder(N).
 *
 * Sources:
 *   - Plofker, K. (2009), *Mathematics in India*, Princeton UP,
 *     ISBN 978-0691120676, §7.4 ("Kerala mathematicians and infinite
 *     series").
 *   - Joseph, G. G. (2010), *The Crest of the Peacock: Non-European
 *     Roots of Mathematics*, 3rd ed., Princeton UP, ISBN 978-0691135267,
 *     ch. 9.
 *   - Original: Mādhava (~1400 CE), via Yuktibhāṣā of Jyeṣṭhadeva (~1530
 *     CE); see Sarma 2008, ed., *Ganita-Yukti-Bhāṣā*, Hindustan Book
 *     Agency.
 *
 * Lean obligation: `Lutar/PACBayes/MadhavaBound.lean`,
 *   `madhava_alt_series_bound` — proved using
 *   `Mathlib.Analysis.SpecificLimits.Basic`.
 */

/** Compute the Nth Madhava partial sum for arctan(x), N terms. */
export function madhavaArctan(x: number, N: number): number {
  if (!Number.isInteger(N) || N < 1) {
    throw new RangeError(`madhavaArctan: N must be a positive integer, got ${N}`);
  }
  let sum = 0;
  let term = x;
  const x2 = x * x;
  for (let n = 0; n < N; n++) {
    sum += (n % 2 === 0 ? 1 : -1) * term / (2 * n + 1);
    term *= x2;
  }
  return sum;
}

/**
 * Madhava remainder bound after N terms of arctan(x).
 *
 * For |x| ≤ 1, the absolute terms |x|^(2n+1)/(2n+1) decrease monotonically,
 * so the Leibniz/Madhava remainder gives
 *
 *     | arctan(x) − S_N |  ≤  |x|^(2N+1) / (2N+1).
 */
export function madhavaRemainder(x: number, N: number): number {
  if (Math.abs(x) > 1) {
    throw new RangeError(
      `madhavaRemainder: |x|=${Math.abs(x)} > 1; Leibniz bound does not apply`,
    );
  }
  if (!Number.isInteger(N) || N < 1) {
    throw new RangeError(`madhavaRemainder: N must be a positive integer, got ${N}`);
  }
  return Math.pow(Math.abs(x), 2 * N + 1) / (2 * N + 1);
}

/** PAC-Bayes refinement input. */
export interface MadhavaPACBayesInput {
  /** TH13 slack term √((KL + ln(2√n/δ))/(2n)) ≥ 0. */
  readonly slackTH13: number;
  /** The number of series terms used in the posterior approximation. */
  readonly N: number;
  /** The series-evaluation parameter |x| ≤ 1. */
  readonly x: number;
  /** Empirical risk computed from the N-term truncation. */
  readonly empiricalRiskN: number;
}

export interface MadhavaPACBayesResult {
  /** Madhava remainder term `|x|^(2N+1)/(2N+1)`. */
  readonly madhavaRemainder: number;
  /** Tight upper bound: R̂_N + slack_TH13 + madhavaRemainder. */
  readonly upperBound: number;
}

/**
 * Apply the Madhava refinement to a TH13 PAC-Bayes upper bound. The
 * caller supplies the series truncation length N and parameter x; the
 * function returns the deterministic correction.
 */
export function madhavaPACBayesRefinement(
  input: MadhavaPACBayesInput,
): MadhavaPACBayesResult {
  const remainder = madhavaRemainder(input.x, input.N);
  return {
    madhavaRemainder: remainder,
    upperBound: input.empiricalRiskN + input.slackTH13 + remainder,
  };
}
