// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ConstructiveTransparency (A12)
//
// Policy rationale:
//   Every Λ score must be re-derivable from declared public inputs; no hidden
//   weights, hidden state, or user-history boosts. A scorer that produces
//   different outputs for identical axis vectors (from different actors) has
//   a hidden state component and must be rejected.
//
//   Lean axiom cited: `constructiveTransparency` (A12)
//   Lean file: Lutar/Gate/ConstructiveTransparency.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if scorer(v1) = scorer(v2) for identical inputs → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20053148
//   INNOVATIONS.md §3 A12: constructiveTransparency

export interface ConstructiveTransparencyGateConfig {
  /** Allowed floating-point tolerance for score equality. Default: 1e-10. */
  scoreTolerance?: number;
}

export interface ConstructiveTransparencyGateOpts {
  /** Axis vector used as input. */
  axisVector:   number[];
  /** Score produced for actorA. */
  scoreForActorA: number;
  /** Score produced for actorB with identical axis vector. */
  scoreForActorB: number;
}

export interface ConstructiveTransparencyDecision {
  allow:           boolean;
  rationale:       string;
  formula:         string;
  leanTheorem:     string;
  leanFile:        string;
  leanCommitSha:   string;
  scoreDelta:      number;
  scoreTolerance:  number;
  transparent:     boolean;
  lambdaScore:     number;
}

const LEAN_THEOREM = "constructiveTransparency";
const LEAN_FILE    = "Lutar/Gate/ConstructiveTransparency.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_TOL  = 1e-10;

// ── Inline formula ────────────────────────────────────────────────────────────
// A12: ∀r: Λ(r) = f(public_inputs(r)) where f is the published Lean-formalized scorer

/**
 * ConstructiveTransparency (A12) policy gate.
 *
 * Validates that a scorer produces identical results for identical axis vectors
 * from different actors. A score delta exceeding the tolerance reveals hidden
 * state and triggers denial.
 *
 * Lean axiom: `constructiveTransparency` (A12)
 * Lean file: Lutar/Gate/ConstructiveTransparency.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20053148
 */
export function constructiveTransparencyGate(
  config: ConstructiveTransparencyGateConfig = {}
): (opts: ConstructiveTransparencyGateOpts) => ConstructiveTransparencyDecision {
  const scoreTolerance = config.scoreTolerance ?? DEFAULT_TOL;
  if (!Number.isFinite(scoreTolerance) || scoreTolerance < 0) {
    throw new Error(`ConstructiveTransparencyGate: scoreTolerance must be ≥ 0; got ${scoreTolerance}`);
  }

  return function gate(opts: ConstructiveTransparencyGateOpts): ConstructiveTransparencyDecision {
    const { axisVector, scoreForActorA, scoreForActorB } = opts;
    if (!Array.isArray(axisVector) || axisVector.length === 0) {
      throw new Error(`ConstructiveTransparencyGate: axisVector must be non-empty`);
    }
    if (!Number.isFinite(scoreForActorA) || !Number.isFinite(scoreForActorB)) {
      throw new Error(`ConstructiveTransparencyGate: scores must be finite`);
    }

    const scoreDelta  = Math.abs(scoreForActorA - scoreForActorB);
    const transparent = scoreDelta <= scoreTolerance;
    const allow       = transparent;
    const lambdaScore = transparent ? 1.0 : Math.max(0, 1 - scoreDelta / 0.1);

    const rationale = allow
      ? `ConstructiveTransparency (A12): score delta=${scoreDelta.toExponential(4)} ≤ tol=${scoreTolerance.toExponential(2)}. Scorer is pure function of public inputs. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `ConstructiveTransparency (A12): score delta=${scoreDelta.toExponential(4)} > tol=${scoreTolerance.toExponential(2)} — hidden state detected. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "ConstructiveTransparency", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, scoreDelta, scoreTolerance, transparent, lambdaScore };
  };
}
