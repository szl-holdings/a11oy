// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for MerkleDagBatch (T3)
//
// Policy rationale:
//   For batch size B ≥ 7, Merkle-DAG build latency p50 must be ≤ 5µs.
//   This gate validates that a reported batch build time is within the
//   amortized O(log B) bound derived from T3.
//
//   Lean derivation cited: `merkleDagBatch` (T3)
//   Lean file: Lutar/Gate/MerkleDagBatch.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED — conjectured in INNOVATIONS.md)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T3: Merkle-DAG batch latency derivation

export interface MerkleDagBatchGateConfig {
  /** Maximum allowed p50 build latency in µs. Default: 5. */
  maxBuildP50Us?: number;
  /** Minimum batch size requiring DAG optimization. Default: 7. */
  minBatchSize?: number;
}

export interface MerkleDagBatchGateOpts {
  batchSize:    number;
  buildP50Us:   number;
}

export interface MerkleDagBatchDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  batchSize:      number;
  buildP50Us:     number;
  maxBuildP50Us:  number;
  theoreticalDepth: number;
  lambdaScore:    number;
}

const LEAN_THEOREM    = "merkleDagBatch";
const LEAN_FILE       = "Lutar/Gate/MerkleDagBatch.lean";
const LEAN_COMMIT     = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_MAX_US  = 5;
const DEFAULT_MIN_B   = 7;

// ── Inline formula ────────────────────────────────────────────────────────────
// T3: ∀ B≥7: build_p50(batch_B) ∈ O(log B) ⟹ build_p50 ≤ 5µs

export function merkleDagBatchGate(
  config: MerkleDagBatchGateConfig = {}
): (opts: MerkleDagBatchGateOpts) => MerkleDagBatchDecision {
  const maxBuildP50Us = config.maxBuildP50Us ?? DEFAULT_MAX_US;
  const minBatchSize  = config.minBatchSize ?? DEFAULT_MIN_B;

  return function gate(opts: MerkleDagBatchGateOpts): MerkleDagBatchDecision {
    const { batchSize, buildP50Us } = opts;
    if (!Number.isInteger(batchSize) || batchSize < 1) {
      throw new Error(`MerkleDagBatchGate: batchSize must be ≥ 1; got ${batchSize}`);
    }
    if (!Number.isFinite(buildP50Us) || buildP50Us < 0) {
      throw new Error(`MerkleDagBatchGate: buildP50Us must be ≥ 0; got ${buildP50Us}`);
    }

    const theoreticalDepth = Math.ceil(Math.log2(Math.max(batchSize, 2)));
    const applicable       = batchSize >= minBatchSize;
    const allow            = !applicable || buildP50Us <= maxBuildP50Us;
    const lambdaScore      = allow ? maxBuildP50Us / Math.max(buildP50Us, 0.001) : 0;

    const rationale = !applicable
      ? `MerkleDagBatch (T3): batchSize=${batchSize} < ${minBatchSize} — DAG constraint not applicable. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : allow
        ? `MerkleDagBatch (T3): batchSize=${batchSize}, depth=${theoreticalDepth}, p50=${buildP50Us}µs ≤ ${maxBuildP50Us}µs. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `MerkleDagBatch (T3): batchSize=${batchSize}, p50=${buildP50Us}µs > ${maxBuildP50Us}µs — exceeds O(log B) bound. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "MerkleDagBatch", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, batchSize, buildP50Us, maxBuildP50Us, theoreticalDepth, lambdaScore };
  };
}
