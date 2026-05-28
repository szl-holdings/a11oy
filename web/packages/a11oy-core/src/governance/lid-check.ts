/**
 * Locally Invariant Domain (LID) check for the Λ-gate (v15 §III, TH12.1)
 *
 * Implements the runtime LID-membership predicate corresponding to
 * `ΛGateLID(τ) := { θ | ∀k: axisScore(θ, k) ≥ τ }` from
 * `Lutar/DPOFeasibility.lean`. A policy parameter sits in the LID iff every
 * governance-axis score meets the threshold τ.
 *
 * The Λ-gate LID is naturally an *orthotope* in parameter space (an
 * intersection of per-axis half-spaces). This is an instance of the abstract
 * domains of Elmecker-Plakolm et al. (2025); the Λ-gate adds no new domain
 * complexity beyond the orthotope case.
 *
 * Sources:
 *   - Elmecker-Plakolm, L., Fasterling, P., Sosnin, P., Tsay, C., Wicker, M.
 *     (2025). "Provably Safe Model Updates." arXiv:2512.01899. SaTML 2026.
 *   - Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C. D., Finn, C.
 *     (2023). "Direct Preference Optimization: Your Language Model is Secretly
 *     a Reward Model." NeurIPS 2023, arXiv:2305.18290.
 *   - Reidemeister, K. (1927). "Elementare Begründung der Knotentheorie."
 *     Abh. Math. Sem. Univ. Hamburg 5, 24-32. — taxonomy of audit-Reidemeister
 *     moves R1/R2/R3 referenced in ch10 §10.2 and `Lutar/Knot/ReidemeisterConjecture.lean`.
 *
 * Lean obligation: `Lutar/DPOFeasibility.lean`, §LIDPreservation. TH12.1a/b/c
 * (R1-identity-repack, R2-of-R1, R3-of-R1) are closed; TH12.1d (general R1)
 * is sorry-tagged pending `axisScore` concretisation in TH12.
 */

/** Per-axis governance score for a policy parameter. Real-valued; conventionally in [0, 1]. */
export type AxisScoreFn = (axisIndex: number) => number;

/** Inputs to the LID-membership check. */
export interface LIDCheckInput {
  /** Number of governance axes (default 9 for the Λ-gate). */
  readonly numAxes: number;
  /** Per-axis score evaluator for the policy parameter under test. */
  readonly axisScore: AxisScoreFn;
  /** Threshold τ. The LID is `{θ | ∀k: axisScore(θ, k) ≥ τ}`. */
  readonly threshold: number;
}

/** Result of an LID-membership check. */
export interface LIDCheckResult {
  /** True iff every axis score meets `threshold`. */
  readonly inLID: boolean;
  /** Indices (0-based) of axes that failed the threshold. Empty when `inLID` is true. */
  readonly failingAxes: readonly number[];
  /** Per-axis (score, met) audit trail for receipt embedding. */
  readonly perAxis: readonly { readonly axis: number; readonly score: number; readonly met: boolean }[];
}

/**
 * Check whether a policy parameter sits inside `ΛGateLID(threshold)`.
 *
 * Runs in O(numAxes) time with no allocations beyond the result objects.
 * Pure: the function does not mutate any input.
 *
 * @example
 *   const result = checkLID({
 *     numAxes: 9,
 *     axisScore: (k) => policyScores[k],
 *     threshold: 0.8,
 *   });
 *   if (!result.inLID) {
 *     // Reject the policy update; record `result.failingAxes` in the receipt.
 *   }
 */
export function checkLID(input: LIDCheckInput): LIDCheckResult {
  const { numAxes, axisScore, threshold } = input;
  if (!Number.isInteger(numAxes) || numAxes <= 0) {
    throw new RangeError(`checkLID: numAxes must be a positive integer, got ${numAxes}`);
  }
  if (!Number.isFinite(threshold)) {
    throw new RangeError(`checkLID: threshold must be finite, got ${threshold}`);
  }

  const perAxis: { axis: number; score: number; met: boolean }[] = [];
  const failingAxes: number[] = [];
  for (let k = 0; k < numAxes; k++) {
    const score = axisScore(k);
    if (!Number.isFinite(score)) {
      throw new RangeError(`checkLID: axisScore(${k}) returned non-finite value ${score}`);
    }
    const met = score >= threshold;
    perAxis.push({ axis: k, score, met });
    if (!met) failingAxes.push(k);
  }
  return { inLID: failingAxes.length === 0, failingAxes, perAxis };
}

/**
 * Compute the post-DPO LID threshold per TH12 (`ΛGateLID_DPO_stability`):
 *
 *     τ_post = τ - L · √(ε / 2)
 *
 * where `L` is the Λ-gate Lipschitz constant in TV distance and `ε` is the
 * KL budget of the DPO update. This is the threshold against which the
 * post-update policy is checked when certifying that a DPO step has stayed
 * inside the LID up to the Pinsker/Lipschitz gap.
 *
 * @param threshold Pre-update LID threshold τ.
 * @param lipschitz Λ-gate Lipschitz constant L (≥ 0).
 * @param klBudget KL divergence upper bound ε (≥ 0).
 */
export function postDPOThreshold(threshold: number, lipschitz: number, klBudget: number): number {
  if (!Number.isFinite(threshold)) throw new RangeError(`postDPOThreshold: threshold non-finite (${threshold})`);
  if (!(lipschitz >= 0) || !Number.isFinite(lipschitz)) {
    throw new RangeError(`postDPOThreshold: lipschitz must be a non-negative finite real, got ${lipschitz}`);
  }
  if (!(klBudget >= 0) || !Number.isFinite(klBudget)) {
    throw new RangeError(`postDPOThreshold: klBudget must be a non-negative finite real, got ${klBudget}`);
  }
  return threshold - lipschitz * Math.sqrt(klBudget / 2);
}

/**
 * Audit-Reidemeister R1 identity-repack predicate (TH12.1a).
 *
 * Verify at runtime that a parameter rewrite `r : θ ↦ θ'` acts as the identity
 * at every coordinate. Used as a *witness check* in the receipt: if the runtime
 * applies a single-axis repack to the policy parameter before LID evaluation,
 * this predicate certifies that the rewrite was an R1 identity-repack, in
 * which case TH12.1a guarantees the LID membership is unchanged.
 *
 * Returns `true` when `θ'` agrees with `θ` at every coordinate within
 * `tolerance` (default 0; bump for floating-point comparisons).
 */
export function isR1IdentityRepack(
  before: readonly number[],
  after: readonly number[],
  tolerance: number = 0,
): boolean {
  if (before.length !== after.length) return false;
  if (!(tolerance >= 0) || !Number.isFinite(tolerance)) {
    throw new RangeError(`isR1IdentityRepack: tolerance must be a non-negative finite real, got ${tolerance}`);
  }
  for (let j = 0; j < before.length; j++) {
    if (Math.abs(before[j] - after[j]) > tolerance) return false;
  }
  return true;
}
