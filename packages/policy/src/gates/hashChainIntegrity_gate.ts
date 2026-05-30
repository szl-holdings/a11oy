// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for HashChainIntegrity (A6)
//
// Policy rationale:
//   Every spine entry must satisfy: entry.chain = SHA256(prev_entry).
//   This gate validates a submitted chain array for sequential hash linkage,
//   denying any sequence where a break in the chain is detected.
//
//   Lean axiom cited: `hashChainIntegrity` (A6)
//   Lean file: Lutar/Gate/HashChainIntegrity.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if all chain links are valid → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §3.4: hashChainIntegrity

import { createHash } from 'node:crypto';

export interface HashChainIntegrityGateConfig {
  /** Hash algorithm. Default: 'sha256'. */
  algorithm?: string;
}

export interface ChainEntry {
  entryId:   string;
  payload:   string;
  chainHash: string; // SHA256(JSON.stringify(prevEntry))
}

export interface HashChainIntegrityGateOpts {
  entries: ChainEntry[];
}

export interface HashChainIntegrityDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  entryCount:     number;
  firstBreakIndex: number | null;
  lambdaScore:    number;
}

const LEAN_THEOREM = "hashChainIntegrity";
const LEAN_FILE    = "Lutar/Gate/HashChainIntegrity.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// A6: ∀n≥1: entry[n].chain = SHA256(JSON.stringify(entry[n-1]))

function _hashEntry(entry: ChainEntry, algo: string): string {
  return createHash(algo).update(JSON.stringify(entry)).digest('hex');
}

/**
 * HashChainIntegrity (A6) policy gate.
 *
 * Verifies that each entry's chainHash equals SHA256 of the previous entry.
 * The genesis entry (index 0) is accepted without a predecessor check.
 *
 * Lean axiom: `hashChainIntegrity` (A6)
 * Lean file: Lutar/Gate/HashChainIntegrity.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function hashChainIntegrityGate(
  config: HashChainIntegrityGateConfig = {}
): (opts: HashChainIntegrityGateOpts) => HashChainIntegrityDecision {
  const algorithm = config.algorithm ?? 'sha256';

  return function gate(opts: HashChainIntegrityGateOpts): HashChainIntegrityDecision {
    const { entries } = opts;
    if (!Array.isArray(entries) || entries.length === 0) {
      throw new Error(`HashChainIntegrityGate: entries must be a non-empty array`);
    }

    let firstBreakIndex: number | null = null;
    for (let i = 1; i < entries.length; i++) {
      const expected = _hashEntry(entries[i - 1], algorithm);
      if (entries[i].chainHash !== expected) {
        firstBreakIndex = i;
        break;
      }
    }

    const allow       = firstBreakIndex === null;
    const lambdaScore = allow ? 1.0 : (firstBreakIndex! - 1) / entries.length;

    const rationale = allow
      ? `HashChainIntegrity (A6): ${entries.length} entries, all ${algorithm} links valid. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `HashChainIntegrity (A6): chain break at entry[${firstBreakIndex}] — expected hash mismatch. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "HashChainIntegrity", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, entryCount: entries.length, firstBreakIndex, lambdaScore };
  };
}
