/**
 * PAC-Bayes governance head (v15 §10.2, TH13)
 *
 * Computes the McAllester-1999 PAC-Bayes generalization bound on the
 * governance head's empirical risk. Given a posterior Q over governance
 * policies and a prior P, the population risk R(Q) satisfies, with
 * probability ≥ 1−δ over the n-sample,
 *
 *     R(Q) ≤ R̂(Q) + √( ( KL(Q‖P) + ln(2√n / δ) ) / (2n) ).
 *
 * Sources:
 *   - McAllester (1999), "PAC-Bayesian Model Averaging", COLT.
 *   - McAllester (2003), "PAC-Bayesian Stochastic Model Selection",
 *     Machine Learning 51:5-21.
 *   - Lotfi et al. (2023), "Non-Vacuous Generalization Bounds for Large
 *     Language Models", NeurIPS 2023, arXiv:2312.17173.
 *   - Amari (1985), Differential-Geometrical Methods in Statistics,
 *     Springer Lecture Notes in Statistics 28. Amari (2016), Information
 *     Geometry and its Applications, Springer.
 *
 * Lean obligation: `Lutar/PACBayes.lean`, TH13
 * `governanceHead_PACBayes_bound` (closed-form arithmetic proved;
 * probabilistic Pr ≥ 1−δ quantifier is the documented residual).
 */

/** PAC-Bayes bound inputs. All quantities are real-valued. */
export interface PACBayesInput {
  /** Empirical risk R̂(Q) of the governance head's posterior on the n-sample.
   *  Must be in [0, 1] (0-1 loss or bounded surrogate). */
  readonly empiricalRisk: number;
  /** KL divergence KL(Q‖P) between posterior and prior, in nats. ≥ 0. */
  readonly klDivergence: number;
  /** Number of i.i.d. evaluation samples n. ≥ 1. */
  readonly sampleSize: number;
  /** Confidence parameter δ ∈ (0, 1). Bound holds with probability ≥ 1−δ. */
  readonly delta: number;
}

export interface PACBayesResult {
  /** The slack term √( (KL + ln(2√n/δ)) / (2n) ). */
  readonly slack: number;
  /** The risk upper bound R̂(Q) + slack. */
  readonly upperBound: number;
  /** Whether the bound is non-vacuous (upperBound < 1). */
  readonly nonVacuous: boolean;
}

function validate(x: PACBayesInput): void {
  if (!(x.empiricalRisk >= 0 && x.empiricalRisk <= 1)) {
    throw new Error(
      `empiricalRisk must be in [0, 1], got ${x.empiricalRisk}`,
    );
  }
  if (!(x.klDivergence >= 0)) {
    throw new Error(`klDivergence must be ≥ 0, got ${x.klDivergence}`);
  }
  if (!Number.isInteger(x.sampleSize) || x.sampleSize < 1) {
    throw new Error(
      `sampleSize must be a positive integer, got ${x.sampleSize}`,
    );
  }
  if (!(x.delta > 0 && x.delta < 1)) {
    throw new Error(`delta must be in (0, 1), got ${x.delta}`);
  }
}

/**
 * Compute the McAllester (1999) PAC-Bayes bound on the governance head's
 * population risk. The returned `upperBound` holds with probability
 * ≥ 1 − `delta` over the draw of the n-sample.
 */
export function pacBayesBound(input: PACBayesInput): PACBayesResult {
  validate(input);
  const { empiricalRisk, klDivergence, sampleSize: n, delta } = input;
  // Numerator: KL(Q‖P) + ln(2√n / δ)
  const numerator = klDivergence + Math.log((2 * Math.sqrt(n)) / delta);
  const slack = Math.sqrt(numerator / (2 * n));
  const upperBound = empiricalRisk + slack;
  return {
    slack,
    upperBound,
    nonVacuous: upperBound < 1,
  };
}

/**
 * Non-vacuity threshold: returns the largest KL divergence such that the
 * resulting bound is still non-vacuous (upperBound < 1), given the other
 * inputs held fixed. Used to size the posterior–prior gap an a11oy
 * governance head may carry before its certificate becomes worthless.
 *
 * Derivation: bound is non-vacuous iff
 *   R̂(Q) + √( (KL + ln(2√n/δ)) / (2n) ) < 1
 *   ⇒ KL < 2n (1 − R̂(Q))² − ln(2√n / δ).
 *
 * Returns 0 if no such KL exists (bound already vacuous at KL=0).
 */
export function pacBayesNonVacuityThreshold(
  empiricalRisk: number,
  sampleSize: number,
  delta: number,
): number {
  if (!(empiricalRisk >= 0 && empiricalRisk <= 1)) {
    throw new Error(`empiricalRisk must be in [0, 1], got ${empiricalRisk}`);
  }
  if (!Number.isInteger(sampleSize) || sampleSize < 1) {
    throw new Error(`sampleSize must be a positive integer, got ${sampleSize}`);
  }
  if (!(delta > 0 && delta < 1)) {
    throw new Error(`delta must be in (0, 1), got ${delta}`);
  }
  const slackBudget = (1 - empiricalRisk) ** 2 * 2 * sampleSize;
  const logTerm = Math.log((2 * Math.sqrt(sampleSize)) / delta);
  const klMax = slackBudget - logTerm;
  return klMax > 0 ? klMax : 0;
}

/**
 * Convenience: evaluate the bound across a11oy's 9-axis governance head.
 * Given per-axis empirical risks and per-axis KL divergences, returns the
 * worst-axis bound (the certificate is only as strong as the loosest axis).
 */
export function nineAxisPacBayesBound(args: {
  perAxisEmpiricalRisk: ReadonlyArray<number>;  // length 9
  perAxisKL: ReadonlyArray<number>;             // length 9
  sampleSize: number;
  delta: number;
}): { worstAxis: number; worstResult: PACBayesResult; perAxis: PACBayesResult[] } {
  const { perAxisEmpiricalRisk, perAxisKL, sampleSize, delta } = args;
  if (perAxisEmpiricalRisk.length !== 9 || perAxisKL.length !== 9) {
    throw new Error(
      `nineAxisPacBayesBound expects exactly 9 axes, got ${perAxisEmpiricalRisk.length} risks and ${perAxisKL.length} KLs`,
    );
  }
  const perAxis = perAxisEmpiricalRisk.map((r, i) =>
    pacBayesBound({
      empiricalRisk: r,
      klDivergence: perAxisKL[i]!,
      sampleSize,
      delta,
    }),
  );
  let worstAxis = 0;
  for (let i = 1; i < 9; i++) {
    if (perAxis[i]!.upperBound > perAxis[worstAxis]!.upperBound) worstAxis = i;
  }
  return { worstAxis, worstResult: perAxis[worstAxis]!, perAxis };
}
