// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for TemporalConsistency (A10)
//
// Policy rationale:
//   Gate verdict is invariant under time-shift within the registered clock-drift
//   bound ε_clock. If a receipt's timestamp differs from evaluation time by more
//   than the drift bound, the temporal consistency property is violated and the
//   receipt is rejected.
//
//   Lean axiom cited: `temporalConsistency` (A10)
//   Lean file: Lutar/Gate/TemporalConsistency.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if |evalTime - receiptTime| ≤ clockDriftBound → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §3 A10: temporalConsistency

export interface TemporalConsistencyGateConfig {
  /** Clock-drift bound in milliseconds. Default: 5000ms (5 seconds). */
  clockDriftBoundMs?: number;
}

export interface TemporalConsistencyGateOpts {
  receiptTimestampMs: number;
  evalTimestampMs:    number;
}

export interface TemporalConsistencyDecision {
  allow:              boolean;
  rationale:          string;
  formula:            string;
  leanTheorem:        string;
  leanFile:           string;
  leanCommitSha:      string;
  clockDriftBoundMs:  number;
  driftMs:            number;
  withinBound:        boolean;
  lambdaScore:        number;
}

const LEAN_THEOREM     = "temporalConsistency";
const LEAN_FILE        = "Lutar/Gate/TemporalConsistency.lean";
const LEAN_COMMIT      = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_DRIFT_MS = 5000;

// ── Inline formula ────────────────────────────────────────────────────────────
// A10: ∀ input, ∀ ΔT ≤ ε_clock: verdict(Λ, input, t) = verdict(Λ, input, t + ΔT)

/**
 * TemporalConsistency (A10) policy gate.
 *
 * Passes when the absolute time difference between receipt timestamp and
 * evaluation time falls within the registered clock-drift bound.
 *
 * Lean axiom: `temporalConsistency` (A10)
 * Lean file: Lutar/Gate/TemporalConsistency.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function temporalConsistencyGate(
  config: TemporalConsistencyGateConfig = {}
): (opts: TemporalConsistencyGateOpts) => TemporalConsistencyDecision {
  const clockDriftBoundMs = config.clockDriftBoundMs ?? DEFAULT_DRIFT_MS;
  if (!Number.isFinite(clockDriftBoundMs) || clockDriftBoundMs < 0) {
    throw new Error(`TemporalConsistencyGate: clockDriftBoundMs must be ≥ 0; got ${clockDriftBoundMs}`);
  }

  return function gate(opts: TemporalConsistencyGateOpts): TemporalConsistencyDecision {
    const { receiptTimestampMs, evalTimestampMs } = opts;
    if (!Number.isFinite(receiptTimestampMs)) throw new Error(`TemporalConsistencyGate: receiptTimestampMs must be finite`);
    if (!Number.isFinite(evalTimestampMs))    throw new Error(`TemporalConsistencyGate: evalTimestampMs must be finite`);

    const driftMs      = Math.abs(evalTimestampMs - receiptTimestampMs);
    const withinBound  = driftMs <= clockDriftBoundMs;
    const allow        = withinBound;
    const lambdaScore  = withinBound ? 1.0 : clockDriftBoundMs / driftMs;

    const rationale = allow
      ? `TemporalConsistency (A10): drift=${driftMs}ms ≤ bound=${clockDriftBoundMs}ms. Verdict stable. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `TemporalConsistency (A10): drift=${driftMs}ms > bound=${clockDriftBoundMs}ms — clock violation. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "TemporalConsistency", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, clockDriftBoundMs, driftMs, withinBound, lambdaScore };
  };
}
