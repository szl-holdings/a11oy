// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for BekensteinEntropyMeasure (T4)
//
// Policy rationale:
//   H(R_n) ≤ 8·sizeBytes bits. A receipt chain of sizeBytes bytes admits a
//   Shannon entropy of at most 8·sizeBytes bits (max-entropy of a uniform
//   distribution over 2^(8·sizeBytes) symbols; processing cannot increase it
//   — Data Processing Inequality). This gate validates that the
//   Shannon-estimated chain entropy falls within that elementary byte bound.
//
//   HONESTY (SZL Doctrine v11): this is the elementary DPI byte-count bound,
//   NOT the physical Bekenstein entropy-area bound S ≤ 2πkRE/(ℏc) — that
//   physical bound has no counterpart in the SZL codebase (F1-4 errata; see
//   Lutar/DPI/DPIBound.lean, where the byte bound's positivity/monotonicity
//   are the proven theorem TH6).
//
//   Lean derivation cited: `bekensteinEntropyMeasure` (T4)
//   Lean file: Lutar/Gate/BekensteinEntropyMeasure.lean
//   PHANTOM CITATION: this lean_file is a planned/aspirational proof
//   obligation and does NOT yet exist in szl-holdings/lutar-lean. The
//   TypeScript gate is live and runtime-enforced; the Lean formalization is
//   NOT machine-checked. Disclosed per SZL Doctrine v11. The elementary byte
//   bound it computes is structurally backed by TH6 (Lutar/DPI/DPIBound.lean).
//
// References:
//   Cover & Thomas, Elements of Information Theory (2006), §2.8 (DPI)
//   Zenodo: https://doi.org/10.5281/zenodo.19944926

export interface BekensteinEntropyMeasureGateConfig {
  /** Bits per byte bound multiplier. Default: 8. */
  bitsPerByte?: number;
}

export interface BekensteinEntropyMeasureGateOpts {
  /** Shannon entropy estimate for the receipt hash distribution (bits). */
  shannonEntropyBits: number;
  /** Registry size in bytes (A). */
  registrySizeBytes: number;
}

export interface BekensteinEntropyMeasureDecision {
  allow:              boolean;
  rationale:          string;
  formula:            string;
  leanTheorem:        string;
  leanFile:           string;
  leanCommitSha:      string;
  shannonEntropyBits: number;
  boundBits:          number;
  ratio:              number;
  lambdaScore:        number;
}

const LEAN_THEOREM = "bekensteinEntropyMeasure";
const LEAN_FILE    = "Lutar/Gate/BekensteinEntropyMeasure.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_BPB  = 8;

export function bekensteinEntropyMeasureGate(
  config: BekensteinEntropyMeasureGateConfig = {}
): (opts: BekensteinEntropyMeasureGateOpts) => BekensteinEntropyMeasureDecision {
  const bitsPerByte = config.bitsPerByte ?? DEFAULT_BPB;
  if (!Number.isFinite(bitsPerByte) || bitsPerByte <= 0) {
    throw new Error(`BekensteinEntropyMeasureGate: bitsPerByte must be > 0; got ${bitsPerByte}`);
  }

  return function gate(opts: BekensteinEntropyMeasureGateOpts): BekensteinEntropyMeasureDecision {
    const { shannonEntropyBits, registrySizeBytes } = opts;
    if (!Number.isFinite(shannonEntropyBits) || shannonEntropyBits < 0) {
      throw new Error(`BekensteinEntropyMeasureGate: shannonEntropyBits must be ≥ 0`);
    }
    if (!Number.isFinite(registrySizeBytes) || registrySizeBytes <= 0) {
      throw new Error(`BekensteinEntropyMeasureGate: registrySizeBytes must be > 0`);
    }

    const boundBits    = bitsPerByte * registrySizeBytes;
    const allow        = shannonEntropyBits <= boundBits;
    const ratio        = shannonEntropyBits / boundBits;
    const lambdaScore  = allow ? 1 - ratio * 0.5 : 0;

    const rationale = allow
      ? `BekensteinEntropyMeasure (T4): H=${shannonEntropyBits.toFixed(2)} bits ≤ bound=${boundBits.toFixed(2)} bits (ratio=${ratio.toFixed(3)}). Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `BekensteinEntropyMeasure (T4): H=${shannonEntropyBits.toFixed(2)} bits > bound=${boundBits.toFixed(2)} bits. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "BekensteinEntropyMeasure", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, shannonEntropyBits, boundBits, ratio, lambdaScore };
  };
}
