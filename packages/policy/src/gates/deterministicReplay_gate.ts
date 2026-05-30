// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for DeterministicReplay (A5)
//
// Policy rationale:
//   For canonical JSON + pinned PRNG + frozen registry, 5× replay must yield
//   byte-identical Merkle roots. This gate validates that a submitted replay
//   bundle reports the same root across all runs — enforcing determinism as
//   a first-class policy property before admitting any production operation.
//
//   Lean axiom cited: `deterministicReplay` (A5)
//   Lean file: Lutar/Gate/DeterministicReplay.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if all replay roots are byte-identical → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §4.6: deterministicReplay axiom

export interface DeterministicReplayGateConfig {
  /** Required number of replay runs. Default: 5. */
  requiredRuns?: number;
}

export interface DeterministicReplayGateOpts {
  /** Array of Merkle root hex strings from N replay runs. */
  replayRoots: string[];
}

export interface DeterministicReplayDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  requiredRuns:  number;
  actualRuns:    number;
  uniqueRoots:   number;
  canonicalRoot: string;
  lambdaScore:   number;
}

const LEAN_THEOREM   = "deterministicReplay";
const LEAN_FILE      = "Lutar/Gate/DeterministicReplay.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_RUNS   = 5;

// ── Inline formula ────────────────────────────────────────────────────────────
// A5: ∀i ∈ {1..5}: root_i = canonical ⟺ canonical JSON ∧ pinned PRNG ∧ frozen registry

/**
 * DeterministicReplay (A5) policy gate.
 *
 * Validates that N replay runs produce byte-identical Merkle roots.
 * Accepts only if the run count meets the requirement and all roots
 * are identical.
 *
 * Lean axiom: `deterministicReplay` (A5)
 * Lean file: Lutar/Gate/DeterministicReplay.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function deterministicReplayGate(
  config: DeterministicReplayGateConfig = {}
): (opts: DeterministicReplayGateOpts) => DeterministicReplayDecision {
  const requiredRuns = config.requiredRuns ?? DEFAULT_RUNS;
  if (!Number.isInteger(requiredRuns) || requiredRuns < 1) {
    throw new Error(`DeterministicReplayGate: requiredRuns must be ≥ 1; got ${requiredRuns}`);
  }

  return function gate(opts: DeterministicReplayGateOpts): DeterministicReplayDecision {
    const { replayRoots } = opts;
    if (!Array.isArray(replayRoots) || replayRoots.length < requiredRuns) {
      throw new Error(`DeterministicReplayGate: need ${requiredRuns} roots; got ${replayRoots?.length}`);
    }
    for (const r of replayRoots) {
      if (typeof r !== 'string' || r.length === 0) {
        throw new Error(`DeterministicReplayGate: each root must be a non-empty string`);
      }
    }

    const uniqueSet    = new Set(replayRoots.slice(0, requiredRuns));
    const uniqueRoots  = uniqueSet.size;
    const canonicalRoot = replayRoots[0];
    const allow        = uniqueRoots === 1;
    const lambdaScore  = allow ? 1.0 : 1.0 / uniqueRoots;

    const rationale = allow
      ? `DeterministicReplay (A5): ${requiredRuns} runs → 1 unique root "${canonicalRoot.slice(0, 16)}…". Byte-identical replay confirmed. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `DeterministicReplay (A5): ${requiredRuns} runs → ${uniqueRoots} distinct roots — non-determinism detected. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "DeterministicReplay", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, requiredRuns, actualRuns: replayRoots.length, uniqueRoots, canonicalRoot, lambdaScore };
  };
}
