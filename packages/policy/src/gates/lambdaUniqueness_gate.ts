// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LambdaUniqueness (TH_L1)
//
// Policy rationale:
//   The Lutar Invariant Λ_k as weighted geometric mean with Egyptian unit-fraction
//   weights is unique given the four axioms. This gate validates that a submitted
//   scoring function produces outputs consistent with the uniqueness theorem — i.e.,
//   that no alternative scoring function with the same axiom constraints would
//   produce a different result for the same input vector.
//
//   Lean theorem cited: `lambdaUniqueness` (TH_L1)
//   Lean file: Lutar/Uniqueness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: proven (sorry_count: 2 in wider repo — see Chief Architect report)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20053148

export interface LambdaUniquenessGateConfig {
  /** Egyptian unit-fraction weights (must sum to 1). Default: equal weights 1/9. */
  weights?: number[];
  /** Tolerance for uniqueness check. Default: 1e-10. */
  tolerance?: number;
}

export interface LambdaUniquenessGateOpts {
  axisScores:    number[];
  submittedScore: number;
}

export interface LambdaUniquenessDecision {
  allow:            boolean;
  rationale:        string;
  formula:          string;
  leanTheorem:      string;
  leanFile:         string;
  leanCommitSha:    string;
  canonicalScore:   number;
  submittedScore:   number;
  delta:            number;
  uniquenessHolds:  boolean;
  lambdaScore:      number;
}

const LEAN_THEOREM = "lambdaUniqueness";
const LEAN_FILE    = "Lutar/Uniqueness.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_TOL  = 1e-10;

// ── Inline formula ────────────────────────────────────────────────────────────
// TH_L1: Λ_k = ∏_i(x_i^w_i) for Egyptian unit-fraction weights w_i is unique

function _weightedGeometricMean(scores: number[], weights: number[]): number {
  let result = 1;
  for (let i = 0; i < scores.length; i++) {
    result *= Math.pow(Math.max(scores[i], 1e-12), weights[i]);
  }
  return result;
}

export function lambdaUniquenessGate(
  config: LambdaUniquenessGateConfig = {}
): (opts: LambdaUniquenessGateOpts) => LambdaUniquenessDecision {
  const tolerance = config.tolerance ?? DEFAULT_TOL;

  return function gate(opts: LambdaUniquenessGateOpts): LambdaUniquenessDecision {
    const { axisScores, submittedScore } = opts;
    if (!Array.isArray(axisScores) || axisScores.length === 0) {
      throw new Error(`LambdaUniquenessGate: axisScores must be non-empty`);
    }
    if (!Number.isFinite(submittedScore)) throw new Error(`LambdaUniquenessGate: submittedScore must be finite`);

    const n       = axisScores.length;
    const weights = config.weights ?? Array(n).fill(1 / n);
    if (weights.length !== n) throw new Error(`LambdaUniquenessGate: weights length must match axisScores`);

    const canonicalScore = _weightedGeometricMean(axisScores, weights);
    const delta          = Math.abs(submittedScore - canonicalScore);
    const uniquenessHolds = delta <= tolerance;
    const allow          = uniquenessHolds;
    const lambdaScore    = canonicalScore;

    const rationale = allow
      ? `LambdaUniqueness (TH_L1): submitted=${submittedScore.toFixed(6)} ≈ canonical=${canonicalScore.toFixed(6)} (Δ=${delta.toExponential(3)}). Uniqueness holds. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `LambdaUniqueness (TH_L1): submitted=${submittedScore.toFixed(6)} ≠ canonical=${canonicalScore.toFixed(6)} (Δ=${delta.toExponential(3)} > tol=${tolerance.toExponential(3)}). Non-canonical scorer. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "LambdaUniqueness", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, canonicalScore, submittedScore, delta, uniquenessHolds, lambdaScore };
  };
}
