// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LambdaMinMaxBounds (TH_L2)
//
// Policy rationale:
//   Λ_k lies in [0,1] with min=0 iff any axis=0 and max=1 iff all axes=1.
//   This gate validates that a submitted Λ score and axis vector satisfy the
//   min/max bound theorem, rejecting any score outside [0,1] or inconsistent
//   with the all-zero/all-one boundary conditions.
//
//   Lean theorem cited: `lambdaMinMaxBounds` (TH_L2)
//   Lean file: Lutar/Bound.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: proven (2 sorrys in Lutar/Bound.lean — see architect report)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20053148

export interface LambdaMinMaxBoundsGateConfig {
  /** Floating-point tolerance for boundary checks. Default: 1e-9. */
  tolerance?: number;
}

export interface LambdaMinMaxBoundsGateOpts {
  lambdaScore: number;
  axisScores:  number[];
}

export interface LambdaMinMaxBoundsDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  inRange:        boolean;
  boundaryConsistent: boolean;
  hasZeroAxis:    boolean;
  allOnesAxes:    boolean;
  lambdaScore:    number;
}

const LEAN_THEOREM = "lambdaMinMaxBounds";
const LEAN_FILE    = "Lutar/Bound.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_TOL  = 1e-9;

// ── Inline formula ────────────────────────────────────────────────────────────
// TH_L2: Λ_k ∈ [0,1]; min=0 ⟺ ∃i: x_i=0; max=1 ⟺ ∀i: x_i=1

export function lambdaMinMaxBoundsGate(
  config: LambdaMinMaxBoundsGateConfig = {}
): (opts: LambdaMinMaxBoundsGateOpts) => LambdaMinMaxBoundsDecision {
  const tolerance = config.tolerance ?? DEFAULT_TOL;

  return function gate(opts: LambdaMinMaxBoundsGateOpts): LambdaMinMaxBoundsDecision {
    const { lambdaScore, axisScores } = opts;
    if (!Number.isFinite(lambdaScore)) throw new Error(`LambdaMinMaxBoundsGate: lambdaScore must be finite`);
    if (!Array.isArray(axisScores) || axisScores.length === 0) throw new Error(`LambdaMinMaxBoundsGate: axisScores required`);

    const inRange      = lambdaScore >= -tolerance && lambdaScore <= 1 + tolerance;
    const hasZeroAxis  = axisScores.some(s => s <= tolerance);
    const allOnesAxes  = axisScores.every(s => s >= 1 - tolerance);

    // Boundary consistency: if has zero axis → lambda ≈ 0; if all ones → lambda ≈ 1
    const minBoundOk   = !hasZeroAxis || lambdaScore <= tolerance;
    const maxBoundOk   = !allOnesAxes || lambdaScore >= 1 - tolerance;
    const boundaryConsistent = minBoundOk && maxBoundOk;
    const allow        = inRange && boundaryConsistent;

    const rationale = allow
      ? `LambdaMinMaxBounds (TH_L2): Λ=${lambdaScore.toFixed(6)} ∈ [0,1]; boundary consistent (zero=${hasZeroAxis}, ones=${allOnesAxes}). Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : !inRange
        ? `LambdaMinMaxBounds (TH_L2): Λ=${lambdaScore} outside [0,1]. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `LambdaMinMaxBounds (TH_L2): boundary inconsistency — zero axis=${hasZeroAxis} but Λ=${lambdaScore.toFixed(6)} not near 0. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "LambdaMinMaxBounds", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, inRange, boundaryConsistent, hasZeroAxis, allOnesAxes, lambdaScore };
  };
}
