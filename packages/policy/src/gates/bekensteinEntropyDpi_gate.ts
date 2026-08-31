// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for BekensteinEntropyDpi (TH6)
//
// Policy rationale:
//   H(receipt chain) ≤ H(registry) ≤ 8A bits, proved via the data processing
//   inequality (DPI). This gate provides the formally-proved enforcement of the
//   Bekenstein entropy bound, superseding the conjectured A7 gate. The DPI
//   proof is elementary: any deterministic function cannot increase entropy.
//
//   Lean theorem cited: `bekensteinEntropyDpi` (TH6)
//   Lean file: Lutar/EntropyBound.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: proven (sorry_count: 0; proof via DPI)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.19944926
//   INNOVATIONS.md §4 TH6: DPI entropy bound proof

export interface BekensteinEntropyDpiGateConfig {
  /** Bits-per-byte cap. Default: 8. */
  bitsPerByte?: number;
}

export interface BekensteinEntropyDpiGateOpts {
  chainEntropyBits:  number;
  registrySizeBytes: number;
}

export interface BekensteinEntropyDpiDecision {
  allow:             boolean;
  rationale:         string;
  formula:           string;
  leanTheorem:       string;
  leanFile:          string;
  leanCommitSha:     string;
  dpiProved:         true;
  chainEntropyBits:  number;
  dpiUpperBoundBits: number;
  withinDpiBound:    boolean;
  lambdaScore:       number;
}

const LEAN_THEOREM = "bekensteinEntropyDpi";
const LEAN_FILE    = "Lutar/EntropyBound.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_BPB  = 8;

// ── Inline formula ────────────────────────────────────────────────────────────
// TH6: H(chain) ≤ H(registry) ≤ 8A bits  [by DPI: Y=chain(X) ⟹ H(Y)≤H(X)]

export function bekensteinEntropyDpiGate(
  config: BekensteinEntropyDpiGateConfig = {}
): (opts: BekensteinEntropyDpiGateOpts) => BekensteinEntropyDpiDecision {
  const bitsPerByte = config.bitsPerByte ?? DEFAULT_BPB;
  if (!Number.isFinite(bitsPerByte) || bitsPerByte <= 0) {
    throw new Error(`BekensteinEntropyDpiGate: bitsPerByte must be > 0; got ${bitsPerByte}`);
  }

  return function gate(opts: BekensteinEntropyDpiGateOpts): BekensteinEntropyDpiDecision {
    const { chainEntropyBits, registrySizeBytes } = opts;
    if (!Number.isFinite(chainEntropyBits) || chainEntropyBits < 0) {
      throw new Error(`BekensteinEntropyDpiGate: chainEntropyBits must be ≥ 0`);
    }
    if (!Number.isFinite(registrySizeBytes) || registrySizeBytes <= 0) {
      throw new Error(`BekensteinEntropyDpiGate: registrySizeBytes must be > 0`);
    }

    const dpiUpperBoundBits = bitsPerByte * registrySizeBytes;
    const withinDpiBound    = chainEntropyBits <= dpiUpperBoundBits;
    const allow             = withinDpiBound;
    const lambdaScore       = withinDpiBound ? 1 - chainEntropyBits / (2 * dpiUpperBoundBits) : 0;

    const rationale = allow
      ? `BekensteinEntropyDpi (TH6): H(chain)=${chainEntropyBits.toFixed(2)} bits ≤ DPI bound=${dpiUpperBoundBits.toFixed(2)} bits. DPI-proved bound satisfied. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `BekensteinEntropyDpi (TH6): H(chain)=${chainEntropyBits.toFixed(2)} bits > DPI bound=${dpiUpperBoundBits.toFixed(2)} bits — anomalous. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "BekensteinEntropyDpi", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, dpiProved: true, chainEntropyBits, dpiUpperBoundBits: dpiUpperBoundBits, withinDpiBound, lambdaScore };
  };
}
