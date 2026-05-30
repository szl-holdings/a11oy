// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for BekensteinSoundness (TH_L3)
//
// *** STAGED — ADVISORY ONLY ***
// Lean status: measured/conjectured (formal proof pending lutar-lean PR #12)
//
// Policy rationale:
//   Bekenstein indicator fires at 49.5% under uniform seed (measured).
//   This gate validates that a submitted fire-rate measurement falls within
//   the expected range [45%, 55%] around the 49.5% measured value.
//   Advisory only until the Lean proof is formally discharged.
//
//   Lean theorem cited: `bekensteinSoundness` (TH_L3)
//   Lean file: Lutar/BekensteinSoundness.lean (pending PR #12)
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// References:
//   https://github.com/szl-holdings/lutar-lean (pending PR #12)

export interface BekensteinSoundnessGateConfig {
  /** Expected fire rate center. Default: 0.495 (49.5%). */
  expectedFireRate?: number;
  /** Acceptable deviation from expected rate. Default: 0.05. */
  rateDeviation?: number;
  /** If true, block on violation. Default: false (advisory). */
  enforced?: boolean;
}

export interface BekensteinSoundnessGateOpts {
  /** Measured fire rate (0..1). */
  measuredFireRate: number;
  /** Sample size used to measure the rate. */
  sampleSize: number;
}

export interface BekensteinSoundnessDecision {
  allow:            boolean;
  rationale:        string;
  formula:          string;
  leanTheorem:      string;
  leanFile:         string;
  leanCommitSha:    string;
  severity:         'advisory' | 'error';
  staged:           boolean;
  measuredFireRate: number;
  expectedFireRate: number;
  deviation:        number;
  withinBand:       boolean;
  lambdaScore:      number;
}

const LEAN_THEOREM       = "bekensteinSoundness";
const LEAN_FILE          = "Lutar/BekensteinSoundness.lean";
const LEAN_COMMIT        = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_RATE       = 0.495;
const DEFAULT_DEVIATION  = 0.05;

export function bekensteinSoundnessGate(
  config: BekensteinSoundnessGateConfig = {}
): (opts: BekensteinSoundnessGateOpts) => BekensteinSoundnessDecision {
  const expectedFireRate = config.expectedFireRate ?? DEFAULT_RATE;
  const rateDeviation    = config.rateDeviation ?? DEFAULT_DEVIATION;
  const enforced         = config.enforced ?? false;

  return function gate(opts: BekensteinSoundnessGateOpts): BekensteinSoundnessDecision {
    const { measuredFireRate, sampleSize } = opts;
    if (!Number.isFinite(measuredFireRate) || measuredFireRate < 0 || measuredFireRate > 1) {
      throw new Error(`BekensteinSoundnessGate: measuredFireRate must be in [0,1]`);
    }
    if (!Number.isInteger(sampleSize) || sampleSize < 100) {
      throw new Error(`BekensteinSoundnessGate: sampleSize must be ≥ 100`);
    }

    const deviation    = Math.abs(measuredFireRate - expectedFireRate);
    const withinBand   = deviation <= rateDeviation;
    const severity     = enforced ? 'error' as const : 'advisory' as const;
    const allow        = withinBand || !enforced;
    const lambdaScore  = withinBand ? 1 - deviation / rateDeviation * 0.5 : 0;

    const stagedNote = enforced ? '' : ' [STAGED-ADVISORY]';
    const rationale = withinBand
      ? `BekensteinSoundness (TH_L3): rate=${(measuredFireRate*100).toFixed(1)}% within ±${(rateDeviation*100).toFixed(0)}% of ${(expectedFireRate*100).toFixed(1)}% (n=${sampleSize}).${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `BekensteinSoundness (TH_L3): rate=${(measuredFireRate*100).toFixed(1)}% deviation=${(deviation*100).toFixed(1)}% > band.${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "BekensteinSoundness", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, severity, staged: !enforced, measuredFireRate, expectedFireRate, deviation, withinBand, lambdaScore };
  };
}
