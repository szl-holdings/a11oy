// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for BekensteinBound (A7)
//
// *** STAGED — ADVISORY ONLY ***
// Lean status: conjectured (formal proof pending lutar-lean Paper R2)
// This gate issues warnings but does NOT block production by default.
//
// Policy rationale:
//   Receipt chain entropy H(R_n) is bounded by the information-theoretic
//   limit from registry area: H(R_n) ≤ 8·sizeBytes bits. This is an advisory
//   check — chains exceeding the bound indicate anomalous entropy generation
//   that may signal state corruption or replay attacks.
//
//   Lean axiom cited: `bekensteinBound` (A7)
//   Lean file: Lutar/Gate/BekensteinBound.lean (pending — conjectured)
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: advisory (severity: 'warning') — entropy > 8*sizeBytes → warn
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.19944926
//   Thesis §4.5: bekensteinBound axiom; TH6 DPI proof discharges this

export interface BekensteinBoundGateConfig {
  /** Bits-per-byte multiplier. Default: 8 (maximum information density). */
  bitsPerByte?: number;
  /**
   * If true, deny on bound violation. Default: false (advisory / warning only).
   * STAGED: set to false until TH6 formal proof lands on lutar-lean.
   */
  enforced?: boolean;
}

export interface BekensteinBoundGateOpts {
  /** Measured chain entropy in bits (Shannon estimator). */
  chainEntropyBits: number;
  /** Registry size in bytes. */
  registrySizeBytes: number;
}

export interface BekensteinBoundDecision {
  allow:             boolean;
  rationale:         string;
  formula:           string;
  leanTheorem:       string;
  leanFile:          string;
  leanCommitSha:     string;
  severity:          'warning' | 'error';
  staged:            boolean;
  chainEntropyBits:  number;
  boundBits:         number;
  withinBound:       boolean;
  lambdaScore:       number;
}

const LEAN_THEOREM   = "bekensteinBound";
const LEAN_FILE      = "Lutar/Gate/BekensteinBound.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_BPB    = 8;

// ── Inline formula ────────────────────────────────────────────────────────────
// A7 (conjectured): H(R_n) ≤ 8·sizeBytes bits (advisory; TH6 DPI discharges formally)

/**
 * BekensteinBound (A7) policy gate — STAGED ADVISORY.
 *
 * Checks receipt chain entropy against the information-theoretic registry bound.
 * Issues a warning by default; can be made enforcing once TH6 is formally proved.
 *
 * Lean axiom: `bekensteinBound` (A7) — conjectured; TH6 provides elementary proof
 * Lean file: Lutar/Gate/BekensteinBound.lean (pending; commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.19944926
 */
export function bekensteinBoundGate(
  config: BekensteinBoundGateConfig = {}
): (opts: BekensteinBoundGateOpts) => BekensteinBoundDecision {
  const bitsPerByte = config.bitsPerByte ?? DEFAULT_BPB;
  const enforced    = config.enforced ?? false;
  if (!Number.isFinite(bitsPerByte) || bitsPerByte <= 0) {
    throw new Error(`BekensteinBoundGate: bitsPerByte must be > 0; got ${bitsPerByte}`);
  }

  return function gate(opts: BekensteinBoundGateOpts): BekensteinBoundDecision {
    const { chainEntropyBits, registrySizeBytes } = opts;
    if (!Number.isFinite(chainEntropyBits) || chainEntropyBits < 0) {
      throw new Error(`BekensteinBoundGate: chainEntropyBits must be ≥ 0; got ${chainEntropyBits}`);
    }
    if (!Number.isFinite(registrySizeBytes) || registrySizeBytes <= 0) {
      throw new Error(`BekensteinBoundGate: registrySizeBytes must be > 0; got ${registrySizeBytes}`);
    }

    const boundBits    = bitsPerByte * registrySizeBytes;
    const withinBound  = chainEntropyBits <= boundBits;
    const severity     = enforced ? 'error' as const : 'warning' as const;
    const allow        = withinBound || !enforced;
    const lambdaScore  = withinBound ? 1.0 : boundBits / chainEntropyBits;

    const stagedNote   = enforced ? '' : ' [STAGED-ADVISORY: not blocking]';
    const rationale = withinBound
      ? `BekensteinBound (A7): H(chain)=${chainEntropyBits.toFixed(2)} bits ≤ bound=${boundBits.toFixed(2)} bits (${registrySizeBytes} bytes × ${bitsPerByte}). Within bound.${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `BekensteinBound (A7): H(chain)=${chainEntropyBits.toFixed(2)} bits > bound=${boundBits.toFixed(2)} bits — anomalous entropy.${stagedNote} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "BekensteinBound", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, severity, staged: !enforced, chainEntropyBits, boundBits, withinBound, lambdaScore };
  };
}
