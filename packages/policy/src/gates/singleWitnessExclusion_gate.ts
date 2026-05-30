// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for SingleWitnessExclusion (T8)
//
// Policy rationale:
//   Different actors with identical digest content produce different SHA-256
//   receipt hashes (different canonical JSON → different hash). Single-witness
//   closure fails for cross-actor pairs. This gate enforces T8: dual witness
//   is required whenever actor IDs differ.
//
//   Lean derivation cited: `singleWitnessExclusion` (T8)
//   Lean file: Lutar/Gate/SingleWitnessExclusion.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T8: single-witness exclusion

export interface SingleWitnessExclusionGateConfig {
  /** If false, same-actor single-witness is allowed. Default: true (require dual). */
  requireDualForSameActor?: boolean;
}

export interface SingleWitnessExclusionGateOpts {
  actor1Id:     string;
  actor2Id:     string;
  witnessCount: number;
}

export interface SingleWitnessExclusionDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  sameActor:      boolean;
  witnessCount:   number;
  dualRequired:   boolean;
  lambdaScore:    number;
}

const LEAN_THEOREM = "singleWitnessExclusion";
const LEAN_FILE    = "Lutar/Gate/SingleWitnessExclusion.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

export function singleWitnessExclusionGate(
  config: SingleWitnessExclusionGateConfig = {}
): (opts: SingleWitnessExclusionGateOpts) => SingleWitnessExclusionDecision {
  const requireDualForSameActor = config.requireDualForSameActor ?? true;

  return function gate(opts: SingleWitnessExclusionGateOpts): SingleWitnessExclusionDecision {
    const { actor1Id, actor2Id, witnessCount } = opts;
    if (!actor1Id || !actor2Id) throw new Error(`SingleWitnessExclusionGate: actor IDs required`);
    if (!Number.isInteger(witnessCount) || witnessCount < 0) {
      throw new Error(`SingleWitnessExclusionGate: witnessCount must be non-negative integer`);
    }

    const sameActor    = actor1Id === actor2Id;
    const dualRequired = !sameActor || requireDualForSameActor;
    const allow        = !dualRequired || witnessCount >= 2;
    const lambdaScore  = allow ? 1.0 : witnessCount / 2;

    const rationale = allow
      ? `SingleWitnessExclusion (T8): actors=${sameActor ? 'same' : 'different'}; witnesses=${witnessCount} ≥ ${dualRequired ? 2 : 1}. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `SingleWitnessExclusion (T8): different actors require dual-witness; got ${witnessCount}. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "SingleWitnessExclusion", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, sameActor, witnessCount, dualRequired, lambdaScore };
  };
}
