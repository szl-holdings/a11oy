// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for AnatomyReduction (TH3)
//
// Policy rationale:
//   Any multi-agent system implementing (R,A,E,Λ,ρ,W) with |R|>8 is bisimilar
//   to the canonical 8-region anatomy. Systems with |R|<8 are missing capability.
//   8 is both necessary and sufficient. This gate validates that a submitted
//   system topology meets the 8-region requirement before admission.
//
//   Lean theorem cited: `anatomyReduction` (TH3)
//   Lean file: Lutar/Composition/AnatomyReduction.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (derived)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20162352

export interface AnatomyReductionGateConfig {
  /** Required region count. Default: 8. */
  canonicalRegionCount?: number;
}

export interface AnatomyReductionGateOpts {
  /** Count of unique typed regions in the submitted system. */
  regionCount: number;
}

export interface AnatomyReductionDecision {
  allow:               boolean;
  rationale:           string;
  formula:             string;
  leanTheorem:         string;
  leanFile:            string;
  leanCommitSha:       string;
  regionCount:         number;
  canonicalRegionCount: number;
  bisimilar:           boolean;
  missing:             boolean;
  lambdaScore:         number;
}

const LEAN_THEOREM    = "anatomyReduction";
const LEAN_FILE       = "Lutar/Composition/AnatomyReduction.lean";
const LEAN_COMMIT     = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_REGIONS = 8;

export function anatomyReductionGate(
  config: AnatomyReductionGateConfig = {}
): (opts: AnatomyReductionGateOpts) => AnatomyReductionDecision {
  const canonicalRegionCount = config.canonicalRegionCount ?? DEFAULT_REGIONS;

  return function gate(opts: AnatomyReductionGateOpts): AnatomyReductionDecision {
    const { regionCount } = opts;
    if (!Number.isInteger(regionCount) || regionCount < 1) {
      throw new Error(`AnatomyReductionGate: regionCount must be ≥ 1; got ${regionCount}`);
    }

    const missing    = regionCount < canonicalRegionCount;
    const bisimilar  = regionCount >= canonicalRegionCount;
    const allow      = bisimilar;
    const lambdaScore = Math.min(1, regionCount / canonicalRegionCount);

    const rationale = allow
      ? `AnatomyReduction (TH3): |R|=${regionCount} ≥ ${canonicalRegionCount} — bisimilar to canonical 8-region anatomy. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `AnatomyReduction (TH3): |R|=${regionCount} < ${canonicalRegionCount} — missing ${canonicalRegionCount - regionCount} region(s); capability incomplete. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "AnatomyReduction", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, regionCount, canonicalRegionCount, bisimilar, missing, lambdaScore };
  };
}
