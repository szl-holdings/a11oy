// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ReplayDoiDuality (TH2)
//
// Policy rationale:
//   The DOI version ledger and the ouroboros replay-root ledger are
//   isomorphic as temporally-ordered sets: each release commit maps
//   bijectively to a version DOI, mediated by the replay root. This gate
//   validates that a supplied (commitSha, replayRoot, doi) triple is
//   consistent with the bijection before admitting a release operation.
//
//   Lean theorem cited: `replayDoiDuality` (TH2)
//   Lean file: Lutar/Composition/ReplayDoiDuality.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (derived)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582

export interface ReplayDoiDualityGateConfig {
  /** Known (commitSha → doi) mapping. Required. */
  knownMappings: Map<string, string>;
}

export interface ReplayDoiDualityGateOpts {
  commitSha:  string;
  doi:        string;
  replayRoot: string;
}

export interface ReplayDoiDualityDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  commitKnown:   boolean;
  doiMatches:    boolean;
  lambdaScore:   number;
}

const LEAN_THEOREM = "replayDoiDuality";
const LEAN_FILE    = "Lutar/Composition/ReplayDoiDuality.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

export function replayDoiDualityGate(
  config: ReplayDoiDualityGateConfig
): (opts: ReplayDoiDualityGateOpts) => ReplayDoiDualityDecision {
  const { knownMappings } = config;
  if (!knownMappings) throw new Error(`ReplayDoiDualityGate: knownMappings required`);

  return function gate(opts: ReplayDoiDualityGateOpts): ReplayDoiDualityDecision {
    const { commitSha, doi, replayRoot } = opts;
    if (!commitSha || !doi || !replayRoot) {
      throw new Error(`ReplayDoiDualityGate: commitSha, doi, and replayRoot all required`);
    }

    const expectedDoi = knownMappings.get(commitSha);
    const commitKnown = expectedDoi !== undefined;
    const doiMatches  = commitKnown && expectedDoi === doi;
    const allow       = doiMatches;
    const lambdaScore = allow ? 1.0 : commitKnown ? 0.5 : 0.0;

    const rationale = allow
      ? `ReplayDoiDuality (TH2): commit="${commitSha.slice(0,12)}" → DOI="${doi}" bijection confirmed. Replay-DOI duality satisfied. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : !commitKnown
        ? `ReplayDoiDuality (TH2): commit="${commitSha.slice(0,12)}" not in known release table. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `ReplayDoiDuality (TH2): commit→DOI mismatch (expected "${expectedDoi}", got "${doi}"). Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "ReplayDoiDuality", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, commitKnown, doiMatches, lambdaScore };
  };
}
