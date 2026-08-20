// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LambdaUniquenessConjecture (TH_L1)
//
// DOCTRINE v11 LOCKED — Invariant #2:
//   Λ = Conjecture 1 (NEVER a theorem). This gate validates scoring consistency
//   under the CONJECTURE that Λ_k as weighted geometric mean with Egyptian
//   unit-fraction weights is unique given the four axioms. The uniqueness is
//   NOT formally proved — it is Conjecture 1 per SZL Doctrine v11 (LOCKED).
//
//   Lean file: Lutar/Uniqueness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: conjecture-open (NOT a theorem — LOCKED by Doctrine v11)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20053148

export interface LambdaUniquenessConjectureGateConfig {
  /** Egyptian unit-fraction weights (must sum to 1). Default: equal weights 1/9. */
  weights?: number[];
  /** Tolerance for uniqueness check. Default: 1e-10. */
  tolerance?: number;
}

export interface LambdaUniquenessConjectureGateOpts {
  axisScores:    number[];
  submittedScore: number;
}

export interface LambdaUniquenessConjectureDecision {
  allow:            boolean;
  rationale:        string;
  formula:          string;
  leanConjecture:   string;
  leanFile:         string;
  leanCommitSha:    string;
  leanStatus:       string;
  canonicalScore:   number;
  submittedScore:   number;
  delta:            number;
  conjectureHolds:  boolean;
  lambdaScore:      number;
  isConjecture:     true;
  proven:           false;
  lambdaStatement:  string;
}

// DOCTRINE v11: Λ is Conjecture 1, NEVER a theorem
const LEAN_CONJECTURE = "lambdaUniquenessConjecture";
const LEAN_FILE       = "Lutar/Uniqueness.lean";
const LEAN_COMMIT     = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const LEAN_STATUS     = "conjecture-open (NOT a theorem — LOCKED by Doctrine v11)";
const LAMBDA_STMT     = "Conjecture 1 (NOT a theorem — LOCKED by Doctrine v11)";
const DEFAULT_TOL     = 1e-10;

// ── Inline formula ────────────────────────────────────────────────────────────
// TH_L1 (CONJECTURE): Λ_k = ∏_i(x_i^w_i) for Egyptian unit-fraction weights w_i
// NOTE: Uniqueness is CONJECTURED, not proved. Doctrine v11 Invariant #2: LOCKED.

function _weightedGeometricMean(scores: number[], weights: number[]): number {
  let result = 1;
  for (let i = 0; i < scores.length; i++) {
    result *= Math.pow(Math.max(scores[i], 1e-12), weights[i]);
  }
  return result;
}

export function lambdaUniquenessConjectureGate(
  config: LambdaUniquenessConjectureGateConfig = {}
): (opts: LambdaUniquenessConjectureGateOpts) => LambdaUniquenessConjectureDecision {
  const tolerance = config.tolerance ?? DEFAULT_TOL;

  return function gate(opts: LambdaUniquenessConjectureGateOpts): LambdaUniquenessConjectureDecision {
    const { axisScores, submittedScore } = opts;
    if (!Array.isArray(axisScores) || axisScores.length === 0) {
      throw new Error(`LambdaUniquenessConjectureGate: axisScores must be non-empty`);
    }
    if (!Number.isFinite(submittedScore)) throw new Error(`LambdaUniquenessConjectureGate: submittedScore must be finite`);

    const n       = axisScores.length;
    const weights = config.weights ?? Array(n).fill(1 / n);
    if (weights.length !== n) throw new Error(`LambdaUniquenessConjectureGate: weights length must match axisScores`);

    const canonicalScore  = _weightedGeometricMean(axisScores, weights);
    const delta           = Math.abs(submittedScore - canonicalScore);
    const conjectureHolds = delta <= tolerance;
    const allow           = conjectureHolds;
    const lambdaScore     = canonicalScore;

    // DOCTRINE: Always emit lambda_statement clarifying conjecture status
    const rationale = allow
      ? `LambdaUniquenessConjecture (TH_L1 CONJECTURE): submitted=${submittedScore.toFixed(6)} ≈ canonical=${canonicalScore.toFixed(6)} (Δ=${delta.toExponential(3)}). Scoring consistent with conjecture. Passes. NOTE: ${LAMBDA_STMT}`
      : `LambdaUniquenessConjecture (TH_L1 CONJECTURE): submitted=${submittedScore.toFixed(6)} ≠ canonical=${canonicalScore.toFixed(6)} (Δ=${delta.toExponential(3)} > tol=${tolerance.toExponential(3)}). Non-canonical scorer. Denied. NOTE: ${LAMBDA_STMT}`;

    return {
      allow,
      rationale,
      formula:         "LambdaUniquenessConjecture",
      leanConjecture:  LEAN_CONJECTURE,
      leanFile:        LEAN_FILE,
      leanCommitSha:   LEAN_COMMIT,
      leanStatus:      LEAN_STATUS,
      canonicalScore,
      submittedScore,
      delta,
      conjectureHolds,
      lambdaScore,
      isConjecture:    true,
      proven:          false,
      lambdaStatement: LAMBDA_STMT,
    };
  };
}

// Backward-compat alias with doctrine warning
/** @deprecated Use lambdaUniquenessConjectureGate — renamed per Doctrine v11 Invariant #2 */
export const lambdaUniquenessGate = lambdaUniquenessConjectureGate;
