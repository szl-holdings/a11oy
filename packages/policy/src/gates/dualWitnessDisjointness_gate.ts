// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for DualWitnessDisjointness (A4)
//
// Policy rationale:
//   For ρ-closure, witness_1_id ≠ witness_2_id must hold at registry write time.
//   A receipt with the same entity serving as both witnesses is invalid — it
//   collapses the dual-witness requirement to a single-witness signature, which
//   fails the independence property needed for audit closure.
//
//   Lean axiom cited: `dualWitnessDisjointness` (A4)
//   Lean file: Lutar/Gate/DualWitness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if witness_1_id != witness_2_id → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §4.3: dualWitnessDisjointness

export interface DualWitnessDisjointnessGateConfig {
  /** Optional: enforce non-empty witness IDs. Default: true. */
  requireNonEmpty?: boolean;
}

export interface DualWitnessDisjointnessGateOpts {
  witness1Id: string;
  witness2Id: string;
}

export interface DualWitnessDisjointnessDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  witness1Id:    string;
  witness2Id:    string;
  disjoint:      boolean;
  lambdaScore:   number;
}

const LEAN_THEOREM = "dualWitnessDisjointness";
const LEAN_FILE    = "Lutar/Gate/DualWitness.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// A4: ρ-closure requires witness_1_id ≠ witness_2_id

/**
 * DualWitnessDisjointness (A4) policy gate.
 *
 * Verifies that witness_1_id ≠ witness_2_id, enforcing the independence
 * requirement for ρ-closure. A shared witness collapses to single-witness
 * signing and is denied.
 *
 * Lean axiom: `dualWitnessDisjointness` (A4)
 * Lean file: Lutar/Gate/DualWitness.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function dualWitnessDisjointnessGate(
  config: DualWitnessDisjointnessGateConfig = {}
): (opts: DualWitnessDisjointnessGateOpts) => DualWitnessDisjointnessDecision {
  const requireNonEmpty = config.requireNonEmpty ?? true;

  return function gate(opts: DualWitnessDisjointnessGateOpts): DualWitnessDisjointnessDecision {
    const { witness1Id, witness2Id } = opts;
    if (requireNonEmpty && (!witness1Id || !witness2Id)) {
      throw new Error(`DualWitnessDisjointnessGate: witness IDs must be non-empty strings`);
    }

    const disjoint   = witness1Id !== witness2Id;
    const allow      = disjoint;
    const lambdaScore = disjoint ? 1.0 : 0.0;

    const rationale = allow
      ? `DualWitnessDisjointness (A4): witness1="${witness1Id.slice(0, 12)}" ≠ witness2="${witness2Id.slice(0, 12)}" — ρ-closure independent. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `DualWitnessDisjointness (A4): witness1 = witness2 = "${witness1Id.slice(0, 12)}" — same entity, collapses to single-witness. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "DualWitnessDisjointness", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, witness1Id, witness2Id, disjoint, lambdaScore };
  };
}
