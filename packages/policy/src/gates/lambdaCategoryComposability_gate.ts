// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LambdaCategoryComposability (TH4)
//
// *** STAGED — ADVISORY ONLY ***
// Lean status: conjectured (pending Lutar/LaxFunctor.lean)
// This gate issues warnings but does NOT block production by default.
//
// Policy rationale:
//   The Λ-Category is a monoidal category; the gate function Λ is a monoidal
//   functor. Gate composition is a natural transformation. TH1 (composability)
//   follows as a corollary. This gate validates that parallel receipt evaluation
//   (monoidal product) preserves the gate semantics.
//
//   Lean theorem cited: `lambdaCategoryComposability` (TH4)
//   Lean file: Lutar/LaxFunctor.lean (pending — conjectured)
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §4 TH4: Λ-Category composability theorem

export interface LambdaCategoryComposabilityGateConfig {
  /** If true, deny on composition failure. Default: false (advisory). */
  enforced?: boolean;
}

export interface LambdaCategoryComposabilityGateOpts {
  /** Λ score of receipt r1. */
  lambdaR1:  number;
  /** Λ score of receipt r2. */
  lambdaR2:  number;
  /** Λ score of composed receipt r1⊗r2 (monoidal product). */
  lambdaComposed: number;
}

export interface LambdaCategoryComposabilityDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  severity:       'advisory' | 'error';
  staged:         boolean;
  monoidalValid:  boolean;
  lambdaScore:    number;
}

const LEAN_THEOREM = "lambdaCategoryComposability";
const LEAN_FILE    = "Lutar/LaxFunctor.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// TH4: Λ monoidal: Λ(r1⊗r2) ≥ min(Λ(r1), Λ(r2)) [lax functor inequality]

export function lambdaCategoryComposabilityGate(
  config: LambdaCategoryComposabilityGateConfig = {}
): (opts: LambdaCategoryComposabilityGateOpts) => LambdaCategoryComposabilityDecision {
  const enforced = config.enforced ?? false;

  return function gate(opts: LambdaCategoryComposabilityGateOpts): LambdaCategoryComposabilityDecision {
    const { lambdaR1, lambdaR2, lambdaComposed } = opts;
    for (const [name, v] of [['lambdaR1', lambdaR1], ['lambdaR2', lambdaR2], ['lambdaComposed', lambdaComposed]] as [string, number][]) {
      if (!Number.isFinite(v) || v < 0 || v > 1) throw new Error(`LambdaCategoryComposabilityGate: ${name} must be in [0,1]`);
    }

    // Lax functor: composed ≥ min(r1, r2) (may need additional witness for strict equality)
    const minComponent  = Math.min(lambdaR1, lambdaR2);
    const monoidalValid = lambdaComposed >= minComponent - 1e-9;
    const severity      = enforced ? 'error' as const : 'advisory' as const;
    const allow         = monoidalValid || !enforced;
    const lambdaScore   = lambdaComposed;

    const stagedNote = enforced ? '' : ' [STAGED-ADVISORY]';
    const rationale = monoidalValid
      ? `LambdaCategoryComposability (TH4): Λ(r1⊗r2)=${lambdaComposed.toFixed(4)} ≥ min(${lambdaR1.toFixed(4)},${lambdaR2.toFixed(4)})=${minComponent.toFixed(4)}. Monoidal functor property holds.${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `LambdaCategoryComposability (TH4): Λ(composed)=${lambdaComposed.toFixed(4)} < min=${minComponent.toFixed(4)} — lax functor violation.${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "LambdaCategoryComposability", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, severity, staged: !enforced, monoidalValid, lambdaScore };
  };
}
