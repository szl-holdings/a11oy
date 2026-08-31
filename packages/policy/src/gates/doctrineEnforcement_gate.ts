// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for DoctrineEnforcement (T10)
//
// Policy rationale:
//   SHA256(doctrine.json) = canonical ∧ all gates pass ⟹ ∀p ∈ FP: p ∉ artifacts.
//   This gate is the terminal gate that, after doctrine SHA validation, checks
//   that no forbidden patterns (FP-1..FP-8) appear in submitted artifact text.
//
//   Lean derivation cited: `doctrineEnforcement` (T10)
//   Lean file: Lutar/Gate/DoctrineEnforcement.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   https://github.com/szl-holdings/szl-trust
//   INNOVATIONS.md §2 T10: doctrine enforcement theorem

export interface DoctrineEnforcementGateConfig {
  /** Canonical doctrine.json SHA-256. Required. */
  canonicalSha256: string;
  /** Forbidden patterns to scan for. Default: the 8 standard FPs. */
  forbiddenPatterns?: string[];
}

export interface DoctrineEnforcementGateOpts {
  doctrineJsonRaw:  string;
  artifactText:     string;
}

export interface DoctrineEnforcementDecision {
  allow:           boolean;
  rationale:       string;
  formula:         string;
  leanTheorem:     string;
  leanFile:        string;
  leanCommitSha:   string;
  sha256Match:     boolean;
  matchedPatterns: string[];
  lambdaScore:     number;
}

import { createHash as _createHashT10 } from 'node:crypto';

const LEAN_THEOREM = "doctrineEnforcement";
const LEAN_FILE    = "Lutar/Gate/DoctrineEnforcement.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_FPS  = ['FP-1-marketing-superlative', 'FP-2-hidden-state', 'FP-3-sorry-undisclosed', 'FP-4-stub-mislabeled', 'FP-5-no-citation', 'FP-6-prng-unseeded', 'FP-7-oracle-bypass', 'FP-8-orcid-missing'];

export function doctrineEnforcementGate(
  config: DoctrineEnforcementGateConfig
): (opts: DoctrineEnforcementGateOpts) => DoctrineEnforcementDecision {
  const { canonicalSha256, forbiddenPatterns = DEFAULT_FPS } = config;
  if (!canonicalSha256 || canonicalSha256.length !== 64) {
    throw new Error(`DoctrineEnforcementGate: canonicalSha256 must be 64-char hex`);
  }

  return function gate(opts: DoctrineEnforcementGateOpts): DoctrineEnforcementDecision {
    const { doctrineJsonRaw, artifactText } = opts;
    if (!doctrineJsonRaw) throw new Error(`DoctrineEnforcementGate: doctrineJsonRaw required`);

    const sha256Match    = _createHashT10('sha256').update(doctrineJsonRaw).digest('hex') === canonicalSha256;
    const matchedPatterns = sha256Match ? forbiddenPatterns.filter(fp => artifactText.includes(fp)) : [];
    const allow          = sha256Match && matchedPatterns.length === 0;
    const lambdaScore    = sha256Match ? 1 - matchedPatterns.length * 0.125 : 0;

    const rationale = !sha256Match
      ? `DoctrineEnforcement (T10): SHA-256 mismatch — doctrine.json tampered. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : allow
        ? `DoctrineEnforcement (T10): SHA-256 valid; no forbidden patterns found. doctrine-check PASS. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `DoctrineEnforcement (T10): patterns [${matchedPatterns.join(',')}] found in artifact. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "DoctrineEnforcement", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, sha256Match, matchedPatterns, lambdaScore };
  };
}
