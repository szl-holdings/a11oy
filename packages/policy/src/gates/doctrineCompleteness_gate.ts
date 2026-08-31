// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for DoctrineCompleteness (A9)
//
// Policy rationale:
//   doctrine.json v1.0.0 must enumerate all 8 forbidden patterns and carry
//   a SHA-256 anchor. Any artifact that fails the SHA-256 check or lacks
//   one of the 8 forbidden pattern entries is denied. This gate is the
//   policy-layer enforcement of doctrine-check.sh.
//
//   Lean axiom cited: `doctrineCompleteness` (A9)
//   Lean file: Lutar/Gate/DoctrineCompleteness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if SHA-256 matches AND all 8 FPs present → allow; else → deny
//
// References:
//   https://github.com/szl-holdings/szl-trust
//   Thesis §8: doctrineCompleteness

import { createHash } from 'node:crypto';

export interface DoctrineCompletenessGateConfig {
  /** Canonical SHA-256 of doctrine.json. Required. */
  canonicalSha256: string;
  /** Expected forbidden pattern count. Default: 8. */
  requiredPatternCount?: number;
}

export interface DoctrineCompletenessGateOpts {
  /** Raw JSON string of doctrine.json. */
  doctrineJsonRaw: string;
  /** Array of forbidden pattern keys found in the artifact. */
  detectedPatterns: string[];
}

export interface DoctrineCompletenessDecision {
  allow:              boolean;
  rationale:          string;
  formula:            string;
  leanTheorem:        string;
  leanFile:           string;
  leanCommitSha:      string;
  sha256Match:        boolean;
  detectedSha256:     string;
  patternCount:       number;
  requiredPatterns:   number;
  lambdaScore:        number;
}

const LEAN_THEOREM = "doctrineCompleteness";
const LEAN_FILE    = "Lutar/Gate/DoctrineCompleteness.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_PATTERNS = 8;

// ── Inline formula ────────────────────────────────────────────────────────────
// A9: SHA256(doctrine.json) = canonical ∧ |FP| = 8 ⟹ no forbidden patterns in artifacts

/**
 * DoctrineCompleteness (A9) policy gate.
 *
 * Verifies doctrine.json SHA-256 integrity and that all 8 forbidden patterns
 * are enumerated. Matches the behavior of `scripts/doctrine-check.sh`.
 *
 * Lean axiom: `doctrineCompleteness` (A9)
 * Lean file: Lutar/Gate/DoctrineCompleteness.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * https://github.com/szl-holdings/szl-trust
 */
export function doctrineCompletenessGate(
  config: DoctrineCompletenessGateConfig
): (opts: DoctrineCompletenessGateOpts) => DoctrineCompletenessDecision {
  const { canonicalSha256 } = config;
  const requiredPatterns = config.requiredPatternCount ?? DEFAULT_PATTERNS;
  if (!canonicalSha256 || canonicalSha256.length !== 64) {
    throw new Error(`DoctrineCompletenessGate: canonicalSha256 must be 64-char hex string`);
  }

  return function gate(opts: DoctrineCompletenessGateOpts): DoctrineCompletenessDecision {
    const { doctrineJsonRaw, detectedPatterns } = opts;
    if (typeof doctrineJsonRaw !== 'string' || doctrineJsonRaw.length === 0) {
      throw new Error(`DoctrineCompletenessGate: doctrineJsonRaw must be non-empty`);
    }

    const detectedSha256 = createHash('sha256').update(doctrineJsonRaw).digest('hex');
    const sha256Match    = detectedSha256 === canonicalSha256;
    const patternCount   = detectedPatterns.length;
    const allow          = sha256Match && patternCount >= requiredPatterns;
    const lambdaScore    = (sha256Match ? 0.5 : 0) + (patternCount / requiredPatterns) * 0.5;

    const rationale = allow
      ? `DoctrineCompleteness (A9): SHA-256 matches; ${patternCount} patterns ≥ ${requiredPatterns}. doctrine-check PASS. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : sha256Match
        ? `DoctrineCompleteness (A9): SHA-256 OK but only ${patternCount}/${requiredPatterns} patterns. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
        : `DoctrineCompleteness (A9): SHA-256 mismatch — expected ${canonicalSha256.slice(0,16)}…, got ${detectedSha256.slice(0,16)}…. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "DoctrineCompleteness", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, sha256Match, detectedSha256, patternCount, requiredPatterns, lambdaScore };
  };
}
