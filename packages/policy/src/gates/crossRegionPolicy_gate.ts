// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for CrossRegionPolicy (T9)
//
// Policy rationale:
//   Cross-region receipts must pass BOTH source exit policy AND destination
//   entry policy. The stricter policy dominates component-wise. A receipt
//   attempting to cross a region boundary must meet the max(floor_src, floor_dst)
//   conjunctive requirement.
//
//   Lean derivation cited: `crossRegionPolicy` (T9)
//   Lean file: Lutar/Gate/CrossRegionPolicy.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T9: cross-region policy dominance

export interface CrossRegionPolicyGateConfig {
  /** Default floor if not specified per region. Default: 0.90. */
  defaultFloor?: number;
}

export interface CrossRegionPolicyGateOpts {
  axisScores:    number[];
  srcExitFloor:  number;
  dstEntryFloor: number;
}

export interface CrossRegionPolicyDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  effectiveFloor: number;
  failingAxes:    number[];
  minAxis:        number;
  lambdaScore:    number;
}

const LEAN_THEOREM = "crossRegionPolicy";
const LEAN_FILE    = "Lutar/Gate/CrossRegionPolicy.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

export function crossRegionPolicyGate(
  config: CrossRegionPolicyGateConfig = {}
): (opts: CrossRegionPolicyGateOpts) => CrossRegionPolicyDecision {
  const defaultFloor = config.defaultFloor ?? 0.90;

  return function gate(opts: CrossRegionPolicyGateOpts): CrossRegionPolicyDecision {
    const { axisScores, srcExitFloor, dstEntryFloor } = opts;
    if (!Array.isArray(axisScores) || axisScores.length === 0) {
      throw new Error(`CrossRegionPolicyGate: axisScores must be non-empty`);
    }
    if (!Number.isFinite(srcExitFloor) || !Number.isFinite(dstEntryFloor)) {
      throw new Error(`CrossRegionPolicyGate: floors must be finite`);
    }

    const effectiveFloor = Math.max(srcExitFloor, dstEntryFloor, defaultFloor);
    const failingAxes    = axisScores.map((s, i) => ({ s, i })).filter(x => x.s < effectiveFloor).map(x => x.i);
    const minAxis        = Math.min(...axisScores);
    const allow          = failingAxes.length === 0;
    const lambdaScore    = minAxis / effectiveFloor;

    const rationale = allow
      ? `CrossRegionPolicy (T9): effectiveFloor=max(${srcExitFloor},${dstEntryFloor})=${effectiveFloor}; min axis=${minAxis.toFixed(4)} ≥ floor. Cross-region pass. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `CrossRegionPolicy (T9): axes [${failingAxes.join(',')}] < effectiveFloor=${effectiveFloor}. Cross-region denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "CrossRegionPolicy", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, effectiveFloor, failingAxes, minAxis, lambdaScore };
  };
}
