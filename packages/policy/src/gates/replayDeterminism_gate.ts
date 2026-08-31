// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ReplayDeterminism (T5)
//
// Policy rationale:
//   For canonical JSON + pinned PRNG + frozen registry, 5× replay must yield
//   the canonical root "1ed4d253…". Any deviation from the expected root is
//   a determinism violation that blocks production deployment.
//
//   Lean derivation cited: `replayDeterminism` (T5)
//   Lean file: Lutar/Gate/ReplayDeterminism.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T5: replay determinism proof

export interface ReplayDeterminismGateConfig {
  /** Expected canonical Merkle root. Required. */
  canonicalRoot: string;
  /** Required replay run count. Default: 5. */
  requiredRuns?: number;
}

export interface ReplayDeterminismGateOpts {
  replayRoots: string[];
}

export interface ReplayDeterminismDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  canonicalRoot:  string;
  matchingRuns:   number;
  totalRuns:      number;
  lambdaScore:    number;
}

const LEAN_THEOREM  = "replayDeterminism";
const LEAN_FILE     = "Lutar/Gate/ReplayDeterminism.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_RUNS  = 5;

export function replayDeterminismGate(
  config: ReplayDeterminismGateConfig
): (opts: ReplayDeterminismGateOpts) => ReplayDeterminismDecision {
  const { canonicalRoot } = config;
  const requiredRuns = config.requiredRuns ?? DEFAULT_RUNS;
  if (!canonicalRoot) throw new Error(`ReplayDeterminismGate: canonicalRoot is required`);

  return function gate(opts: ReplayDeterminismGateOpts): ReplayDeterminismDecision {
    const { replayRoots } = opts;
    if (!Array.isArray(replayRoots) || replayRoots.length < requiredRuns) {
      throw new Error(`ReplayDeterminismGate: need ${requiredRuns} roots; got ${replayRoots?.length}`);
    }

    const matchingRuns = replayRoots.slice(0, requiredRuns).filter(r => r === canonicalRoot).length;
    const allow        = matchingRuns === requiredRuns;
    const lambdaScore  = matchingRuns / requiredRuns;

    const rationale = allow
      ? `ReplayDeterminism (T5): all ${requiredRuns} runs match canonical root "${canonicalRoot.slice(0,16)}…". Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `ReplayDeterminism (T5): ${matchingRuns}/${requiredRuns} runs matched — determinism violation. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "ReplayDeterminism", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, canonicalRoot, matchingRuns, totalRuns: replayRoots.length, lambdaScore };
  };
}
