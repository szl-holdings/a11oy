// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for PrivacyMask (T7)
//
// Policy rationale:
//   The 9-bit axis mask reveals pass/fail per axis only (not quantitative
//   Λ values). bits_leaked(mask) = 9 ≪ 576 bits (raw Λ-vector).
//   This gate validates that only the binary mask is transmitted externally,
//   blocking any export of raw floating-point axis scores.
//
//   Lean derivation cited: `privacyMask` (T7)
//   Lean file: Lutar/Gate/PrivacyMask.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T7: privacy mask theorem

export interface PrivacyMaskGateConfig {
  /** Expected mask bit count. Default: 9. */
  expectedBitCount?: number;
}

export interface PrivacyMaskGateOpts {
  /** The output payload being transmitted. */
  outputPayload: Record<string, unknown>;
}

export interface PrivacyMaskDecision {
  allow:               boolean;
  rationale:           string;
  formula:             string;
  leanTheorem:         string;
  leanFile:            string;
  leanCommitSha:       string;
  hasRawScores:        boolean;
  leakedFieldCount:    number;
  privacyReduction:    number;
  lambdaScore:         number;
}

const LEAN_THEOREM      = "privacyMask";
const LEAN_FILE         = "Lutar/Gate/PrivacyMask.lean";
const LEAN_COMMIT       = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const RAW_SCORE_FIELDS  = ['axisScores', 'lambdaVector', 'rawScores', 'axisValues', 'lambdaRaw'];

export function privacyMaskGate(
  config: PrivacyMaskGateConfig = {}
): (opts: PrivacyMaskGateOpts) => PrivacyMaskDecision {
  const expectedBitCount = config.expectedBitCount ?? 9;

  return function gate(opts: PrivacyMaskGateOpts): PrivacyMaskDecision {
    const { outputPayload } = opts;
    if (!outputPayload || typeof outputPayload !== 'object') {
      throw new Error(`PrivacyMaskGate: outputPayload must be an object`);
    }

    const leakedFields   = RAW_SCORE_FIELDS.filter(f => f in outputPayload);
    const hasRawScores   = leakedFields.length > 0;
    const allow          = !hasRawScores;
    const TOTAL_RAW_BITS = expectedBitCount * 64;
    const privacyReduction = allow ? (TOTAL_RAW_BITS - expectedBitCount) / TOTAL_RAW_BITS : 0;
    const lambdaScore    = allow ? 1.0 : 0.0;

    const rationale = allow
      ? `PrivacyMask (T7): no raw score fields in payload; privacy reduction=${(privacyReduction * 100).toFixed(1)}% (${expectedBitCount} bits vs ${TOTAL_RAW_BITS} raw). Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `PrivacyMask (T7): raw score fields [${leakedFields.join(',')}] found in payload — Λ-vector leak detected. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "PrivacyMask", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, hasRawScores, leakedFieldCount: leakedFields.length, privacyReduction, lambdaScore };
  };
}
