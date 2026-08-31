// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for MeasurabilityHonestyFloor (A3)
//
// Policy rationale:
//   The measurabilityHonesty axis carries a stricter floor (0.95) requiring
//   that all claims in an artifact are anchored to verifiable evidence.
//   Superlatives without citations, inflated closure claims, or bandaid
//   fixes all reduce this axis below the floor and trigger denial.
//
//   Lean axiom cited: `measurabilityHonestyFloor` (A3)
//   Lean file: Lutar/Gate/MeasurabilityHonesty.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if measurabilityHonesty >= 0.95 → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §4.1: measurabilityHonestyFloor axiom

export interface MeasurabilityHonestyFloorGateConfig {
  /** Measurability honesty floor. Default: 0.95. */
  honestyFloor?: number;
}

export interface MeasurabilityHonestyFloorGateOpts {
  /** measurabilityHonesty axis score in [0,1]. */
  measurabilityHonesty: number;
  /** Count of unsupported claims detected. Each adds a 0.05 penalty. */
  unsupportedClaimCount?: number;
}

export interface MeasurabilityHonestyFloorDecision {
  allow:                boolean;
  rationale:            string;
  formula:              string;
  leanTheorem:          string;
  leanFile:             string;
  leanCommitSha:        string;
  honestyFloor:         number;
  effectiveScore:       number;
  unsupportedClaimCount: number;
  lambdaScore:          number;
}

const LEAN_THEOREM  = "measurabilityHonestyFloor";
const LEAN_FILE     = "Lutar/Gate/MeasurabilityHonesty.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_FLOOR = 0.95;
const CLAIM_PENALTY = 0.05;

// ── Inline formula ────────────────────────────────────────────────────────────
// A3: measurabilityHonesty axis floor = 0.95; effectiveScore = score - count*0.05

/**
 * MeasurabilityHonestyFloor (A3) policy gate.
 *
 * Enforces the 0.95 floor on measurabilityHonesty, with an additional
 * per-unsupported-claim penalty of 0.05. Doctrine v6: no marketing
 * superlatives, no bandaid fixes, all gaps disclosed.
 *
 * Lean axiom: `measurabilityHonestyFloor` (A3)
 * Lean file: Lutar/Gate/MeasurabilityHonesty.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function measurabilityHonestyFloorGate(
  config: MeasurabilityHonestyFloorGateConfig = {}
): (opts: MeasurabilityHonestyFloorGateOpts) => MeasurabilityHonestyFloorDecision {
  const honestyFloor = config.honestyFloor ?? DEFAULT_FLOOR;
  if (!Number.isFinite(honestyFloor) || honestyFloor < 0 || honestyFloor > 1) {
    throw new Error(`MeasurabilityHonestyFloorGate: honestyFloor must be in [0,1]; got ${honestyFloor}`);
  }

  return function gate(opts: MeasurabilityHonestyFloorGateOpts): MeasurabilityHonestyFloorDecision {
    const { measurabilityHonesty, unsupportedClaimCount = 0 } = opts;
    if (!Number.isFinite(measurabilityHonesty) || measurabilityHonesty < 0 || measurabilityHonesty > 1) {
      throw new Error(`MeasurabilityHonestyFloorGate: measurabilityHonesty must be in [0,1]; got ${measurabilityHonesty}`);
    }
    if (!Number.isInteger(unsupportedClaimCount) || unsupportedClaimCount < 0) {
      throw new Error(`MeasurabilityHonestyFloorGate: unsupportedClaimCount must be non-negative integer; got ${unsupportedClaimCount}`);
    }

    const effectiveScore = Math.max(0, measurabilityHonesty - unsupportedClaimCount * CLAIM_PENALTY);
    const allow          = effectiveScore >= honestyFloor;
    const lambdaScore    = effectiveScore;

    const rationale = allow
      ? `MeasurabilityHonestyFloor (A3): score=${effectiveScore.toFixed(4)} ≥ floor ${honestyFloor} (${unsupportedClaimCount} unsupported claims penalized). Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `MeasurabilityHonestyFloor (A3): score=${effectiveScore.toFixed(4)} < floor ${honestyFloor} (${unsupportedClaimCount} unsupported claims @ -${CLAIM_PENALTY} each). Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "MeasurabilityHonestyFloor", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, honestyFloor, effectiveScore, unsupportedClaimCount, lambdaScore };
  };
}
