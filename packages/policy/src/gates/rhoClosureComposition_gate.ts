// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for RhoClosureComposition (T1)
//
// Policy rationale:
//   ρ(r1) ∧ ρ(r2) ⟹ ρ(r1∘r2) iff witness sets are pairwise disjoint
//   OR a third independent witness co-signs. This gate validates that a
//   composed receipt bundle satisfies the closure condition before admission.
//
//   Lean derivation cited: `rhoClosureComposition` (T1)
//   Lean file: Lutar/Gate/RhoClosureComposition.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T1: ρ-closure composition derivation

export interface RhoClosureCompositionGateConfig {
  /** Allow third-witness override for non-disjoint sets. Default: true. */
  allowThirdWitness?: boolean;
}

export interface RhoClosureCompositionGateOpts {
  witnessSet1:   string[];
  witnessSet2:   string[];
  thirdWitness?: string;
}

export interface RhoClosureCompositionDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  disjoint:       boolean;
  hasThirdWitness: boolean;
  sharedWitnesses: string[];
  lambdaScore:    number;
}

const LEAN_THEOREM = "rhoClosureComposition";
const LEAN_FILE    = "Lutar/Gate/RhoClosureComposition.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// T1: ρ(r1) ∧ ρ(r2) ⟹ ρ(r1∘r2) ⟺ W1 ∩ W2 = ∅ ∨ ∃w3 ∉ W1 ∪ W2

export function rhoClosureCompositionGate(
  config: RhoClosureCompositionGateConfig = {}
): (opts: RhoClosureCompositionGateOpts) => RhoClosureCompositionDecision {
  const allowThirdWitness = config.allowThirdWitness ?? true;

  return function gate(opts: RhoClosureCompositionGateOpts): RhoClosureCompositionDecision {
    const { witnessSet1, witnessSet2, thirdWitness } = opts;
    if (!Array.isArray(witnessSet1) || !Array.isArray(witnessSet2)) {
      throw new Error(`RhoClosureCompositionGate: witnessSet1 and witnessSet2 must be arrays`);
    }

    const set1           = new Set(witnessSet1);
    const union          = new Set([...witnessSet1, ...witnessSet2]);
    const sharedWitnesses = witnessSet2.filter(w => set1.has(w));
    const disjoint       = sharedWitnesses.length === 0;
    const hasThirdWitness = !!thirdWitness && !union.has(thirdWitness);
    const allow          = disjoint || (allowThirdWitness && hasThirdWitness);
    const lambdaScore    = allow ? 1.0 : 0.5;

    const rationale = allow
      ? disjoint
        ? `RhoClosureComposition (T1): witness sets disjoint — ρ-closure of composition holds. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `RhoClosureComposition (T1): sets non-disjoint but third-witness "${thirdWitness}" ∉ W1∪W2 — ρ-closure holds. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `RhoClosureComposition (T1): witness sets overlap [${sharedWitnesses.join(',')}] and no valid third witness — ρ-closure fails. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "RhoClosureComposition", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, disjoint, hasThirdWitness, sharedWitnesses, lambdaScore };
  };
}
