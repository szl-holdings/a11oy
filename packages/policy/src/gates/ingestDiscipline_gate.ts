// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for IngestDiscipline (A8)
//
// Policy rationale:
//   Every ingest requires: source_url + content_hash + license (allowlist) + ORCID.
//   Missing any of these four fields causes the ingest to be rejected before
//   any receipt is issued, preventing unlicensed or unattributed content from
//   entering the SZL knowledge graph.
//
//   Lean axiom cited: `ingestDiscipline` (A8)
//   Lean file: Lutar/Gate/IngestDiscipline.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if all 4 fields present + license in allowlist → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §7: ingestDiscipline

export interface IngestDisciplineGateConfig {
  /** Allowed SPDX license identifiers. Default: Apache-2.0, MIT, CC-BY-4.0. */
  licenseAllowList?: string[];
}

export interface IngestDisciplineGateOpts {
  sourceUrl:    string;
  contentHash:  string;
  license:      string;
  orcid:        string;
}

export interface IngestDisciplineDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  missingFields:  string[];
  licenseAllowed: boolean;
  lambdaScore:    number;
}

const LEAN_THEOREM = "ingestDiscipline";
const LEAN_FILE    = "Lutar/Gate/IngestDiscipline.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_LICENSES = ['Apache-2.0', 'MIT', 'CC-BY-4.0', 'CC-BY-SA-4.0', 'BSD-2-Clause', 'BSD-3-Clause'];
const ORCID_RE = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;

// ── Inline formula ────────────────────────────────────────────────────────────
// A8: ingest(x) valid ⟺ x.source_url ∧ x.content_hash ∧ x.license ∈ L ∧ x.orcid

/**
 * IngestDiscipline (A8) policy gate.
 *
 * Validates the four mandatory ingest fields and checks the license against
 * the configured allowlist. Rejects ingests that would admit unlicensed or
 * unattributed content.
 *
 * Lean axiom: `ingestDiscipline` (A8)
 * Lean file: Lutar/Gate/IngestDiscipline.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function ingestDisciplineGate(
  config: IngestDisciplineGateConfig = {}
): (opts: IngestDisciplineGateOpts) => IngestDisciplineDecision {
  const licenseAllowList = config.licenseAllowList ?? DEFAULT_LICENSES;

  return function gate(opts: IngestDisciplineGateOpts): IngestDisciplineDecision {
    const { sourceUrl, contentHash, license, orcid } = opts;
    const missingFields: string[] = [];

    if (!sourceUrl || !sourceUrl.startsWith('http')) missingFields.push('source_url');
    if (!contentHash || contentHash.length < 16)     missingFields.push('content_hash');
    if (!license)                                    missingFields.push('license');
    if (!orcid || !ORCID_RE.test(orcid))             missingFields.push('orcid');

    const licenseAllowed = licenseAllowList.includes(license);
    const allow          = missingFields.length === 0 && licenseAllowed;
    const lambdaScore    = allow ? 1.0 : (4 - missingFields.length) / 4 * (licenseAllowed ? 1 : 0.5);

    const denyReason = missingFields.length > 0
      ? `missing fields: [${missingFields.join(', ')}]`
      : `license "${license}" not in allowlist`;

    const rationale = allow
      ? `IngestDiscipline (A8): all 4 fields present; license="${license}" allowed. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `IngestDiscipline (A8): ${denyReason}. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "IngestDiscipline", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, missingFields, licenseAllowed, lambdaScore };
  };
}
