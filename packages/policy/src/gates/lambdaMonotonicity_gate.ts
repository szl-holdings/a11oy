// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LambdaMonotonicity (T2)
//
// Policy rationale:
//   Adding consistent evidence to a receipt must weakly increase all axis
//   scores. If a proposed evidence augmentation decreases any axis score, it
//   is classified as conflicting evidence and rejected at the gate.
//
//   Lean derivation cited: `lambdaMonotonicity` (T2)
//   Lean file: Lutar/Gate/LambdaMonotonicity.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T2: lambda monotonicity derivation

export interface LambdaMonotonicityGateConfig {
  /** Allowed floating-point tolerance for monotonicity check. Default: 1e-9. */
  tolerance?: number;
}

export interface LambdaMonotonicityGateOpts {
  /** Original axis scores. */
  originalScores:  number[];
  /** Proposed augmented axis scores (after adding evidence). */
  augmentedScores: number[];
}

export interface LambdaMonotonicityDecision {
  allow:               boolean;
  rationale:           string;
  formula:             string;
  leanTheorem:         string;
  leanFile:            string;
  leanCommitSha:       string;
  decreasingAxes:      number[];
  minDelta:            number;
  lambdaScore:         number;
}

const LEAN_THEOREM = "lambdaMonotonicity";
const LEAN_FILE    = "Lutar/Gate/LambdaMonotonicity.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_TOL  = 1e-9;

// ── Inline formula ────────────────────────────────────────────────────────────
// T2: r' = r ⊕ e_consistent ⟹ Λ(r') ≥ Λ(r) (Lean A1: IsMonotone)

export function lambdaMonotonicityGate(
  config: LambdaMonotonicityGateConfig = {}
): (opts: LambdaMonotonicityGateOpts) => LambdaMonotonicityDecision {
  const tolerance = config.tolerance ?? DEFAULT_TOL;

  return function gate(opts: LambdaMonotonicityGateOpts): LambdaMonotonicityDecision {
    const { originalScores, augmentedScores } = opts;
    if (!Array.isArray(originalScores) || !Array.isArray(augmentedScores)) {
      throw new Error(`LambdaMonotonicityGate: both score arrays required`);
    }
    if (originalScores.length !== augmentedScores.length) {
      throw new Error(`LambdaMonotonicityGate: score arrays must have equal length`);
    }

    const decreasingAxes: number[] = [];
    let minDelta = Infinity;
    for (let i = 0; i < originalScores.length; i++) {
      const delta = augmentedScores[i] - originalScores[i];
      if (delta < minDelta) minDelta = delta;
      if (delta < -tolerance) decreasingAxes.push(i);
    }

    const allow       = decreasingAxes.length === 0;
    const lambdaScore = allow ? 1.0 : Math.max(0, 1 + minDelta);

    const rationale = allow
      ? `LambdaMonotonicity (T2): all ${originalScores.length} axes weakly increased (minDelta=${minDelta.toExponential(4)}). Consistent evidence. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `LambdaMonotonicity (T2): axes [${decreasingAxes.join(',')}] decreased — conflicting evidence. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "LambdaMonotonicity", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, decreasingAxes, minDelta, lambdaScore };
  };
}
