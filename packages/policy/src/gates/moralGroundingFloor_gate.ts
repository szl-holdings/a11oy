// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for MoralGroundingFloor (A2)
//
// Policy rationale:
//   The moralGrounding axis carries a stricter floor (0.95) than the
//   default 0.90 because misattribution of authorship or suppression of
//   ORCID constitutes a governance-critical violation. This gate enforces
//   that higher bar independently of the composite Λ check.
//
//   Lean axiom cited: `moralGroundingFloor` (A2)
//   Lean file: Lutar/Gate/MoralGrounding.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if moralGrounding >= 0.95 → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §4.1: moralGroundingFloor axiom

export interface MoralGroundingFloorGateConfig {
  /** Moral grounding floor. Default: 0.95. */
  moralFloor?: number;
}

export interface MoralGroundingFloorGateOpts {
  /** moralGrounding axis score in [0,1]. */
  moralGrounding: number;
  /** Optional ORCID present flag — absence penalizes score. */
  orcidPresent?: boolean;
}

export interface MoralGroundingFloorDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  moralFloor:     number;
  moralGrounding: number;
  lambdaScore:    number;
}

const LEAN_THEOREM  = "moralGroundingFloor";
const LEAN_FILE     = "Lutar/Gate/MoralGrounding.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_FLOOR = 0.95;

// ── Inline formula ────────────────────────────────────────────────────────────
// A2: moralGrounding axis floor = 0.95 (stricter than default 0.90)

/**
 * MoralGroundingFloor (A2) policy gate.
 *
 * Enforces the elevated 0.95 floor on the moralGrounding axis. An absent
 * ORCID is treated as an automatic floor penalty, reducing the effective
 * score to 0.0.
 *
 * Lean axiom: `moralGroundingFloor` (A2)
 * Lean file: Lutar/Gate/MoralGrounding.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function moralGroundingFloorGate(
  config: MoralGroundingFloorGateConfig = {}
): (opts: MoralGroundingFloorGateOpts) => MoralGroundingFloorDecision {
  const moralFloor = config.moralFloor ?? DEFAULT_FLOOR;
  if (!Number.isFinite(moralFloor) || moralFloor < 0 || moralFloor > 1) {
    throw new Error(`MoralGroundingFloorGate: moralFloor must be in [0,1]; got ${moralFloor}`);
  }

  return function gate(opts: MoralGroundingFloorGateOpts): MoralGroundingFloorDecision {
    const { moralGrounding, orcidPresent = true } = opts;
    if (!Number.isFinite(moralGrounding) || moralGrounding < 0 || moralGrounding > 1) {
      throw new Error(`MoralGroundingFloorGate: moralGrounding must be in [0,1]; got ${moralGrounding}`);
    }

    const effectiveScore = orcidPresent ? moralGrounding : 0.0;
    const allow          = effectiveScore >= moralFloor;
    const lambdaScore    = effectiveScore;

    const rationale = allow
      ? `MoralGroundingFloor (A2): moralGrounding=${effectiveScore.toFixed(4)} ≥ floor ${moralFloor}; ORCID present=${orcidPresent}. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `MoralGroundingFloor (A2): moralGrounding=${effectiveScore.toFixed(4)} < floor ${moralFloor}; ORCID present=${orcidPresent}. Denied — authorship attribution required. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "MoralGroundingFloor", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, moralFloor, moralGrounding: effectiveScore, lambdaScore };
  };
}
