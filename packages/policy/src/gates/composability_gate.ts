// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for Composability (TH1)
//
// Policy rationale:
//   If systems A and B share a doctrine.json SHA, use compatible Λ-floors
//   (A exit ≤ B entry), and communicate via A2A receipt-envelope headers,
//   their composition A∘B is doctrine-locked. This gate validates the three
//   composability preconditions before allowing cross-system deployment.
//
//   Lean theorem cited: `composability` (TH1)
//   Lean file: Lutar/Composition/Composability.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (derived)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20162352
//   INNOVATIONS.md §4 TH1: composability theorem

export interface ComposabilityGateConfig {
  /** Require A2A envelope headers in payload. Default: true. */
  requireA2AHeaders?: boolean;
}

export interface ComposabilityGateOpts {
  doctrineShaA:     string;
  doctrineShaB:     string;
  aExitFloor:       number;
  bEntryFloor:      number;
  hasA2AHeaders:    boolean;
}

export interface ComposabilityDecision {
  allow:             boolean;
  rationale:         string;
  formula:           string;
  leanTheorem:       string;
  leanFile:          string;
  leanCommitSha:     string;
  doctrineMatch:     boolean;
  floorCompatible:   boolean;
  a2aHeadersPresent: boolean;
  lambdaScore:       number;
}

const LEAN_THEOREM = "composability";
const LEAN_FILE    = "Lutar/Composition/Composability.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

export function composabilityGate(
  config: ComposabilityGateConfig = {}
): (opts: ComposabilityGateOpts) => ComposabilityDecision {
  const requireA2AHeaders = config.requireA2AHeaders ?? true;

  return function gate(opts: ComposabilityGateOpts): ComposabilityDecision {
    const { doctrineShaA, doctrineShaB, aExitFloor, bEntryFloor, hasA2AHeaders } = opts;
    if (!doctrineShaA || !doctrineShaB) throw new Error(`ComposabilityGate: both doctrine SHAs required`);
    if (!Number.isFinite(aExitFloor) || !Number.isFinite(bEntryFloor)) {
      throw new Error(`ComposabilityGate: floors must be finite`);
    }

    const doctrineMatch      = doctrineShaA === doctrineShaB;
    const floorCompatible    = aExitFloor <= bEntryFloor;
    const a2aHeadersPresent  = hasA2AHeaders;
    const allow              = doctrineMatch && floorCompatible && (!requireA2AHeaders || a2aHeadersPresent);
    const lambdaScore        = [doctrineMatch, floorCompatible, a2aHeadersPresent].filter(Boolean).length / 3;

    const failures: string[] = [];
    if (!doctrineMatch) failures.push('doctrine SHA mismatch');
    if (!floorCompatible) failures.push(`A exit floor ${aExitFloor} > B entry floor ${bEntryFloor}`);
    if (requireA2AHeaders && !a2aHeadersPresent) failures.push('missing A2A headers');

    const rationale = allow
      ? `Composability (TH1): doctrine SHA match, A exit (${aExitFloor}) ≤ B entry (${bEntryFloor}), A2A headers present. A∘B doctrine-locked. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `Composability (TH1): preconditions failed — [${failures.join('; ')}]. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "Composability", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, doctrineMatch, floorCompatible, a2aHeadersPresent, lambdaScore };
  };
}
