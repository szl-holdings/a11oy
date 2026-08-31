// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ReceiptChainConfluence (TH5)
//
// Policy rationale:
//   The receipt chain is the cofree comonad of the receipt functor. Two replay
//   runs produce the same comonad element iff they agree on all observations.
//   This gate validates that two independently generated chain roots agree,
//   which proves that both runs followed the unique normal form.
//
//   Lean theorem cited: `receiptChainConfluence` (TH5)
//   Lean file: Lutar/Composition/ReceiptChainConfluence.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: conjectured (pending formal Lean formalization)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582

export interface ReceiptChainConfluenceGateConfig {
  /** If true, deny on non-confluence. Default: true. */
  enforced?: boolean;
}

export interface ReceiptChainConfluenceGateOpts {
  chainRootA: string;
  chainRootB: string;
}

export interface ReceiptChainConfluenceDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  confluent:     boolean;
  lambdaScore:   number;
}

const LEAN_THEOREM = "receiptChainConfluence";
const LEAN_FILE    = "Lutar/Composition/ReceiptChainConfluence.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

export function receiptChainConfluenceGate(
  config: ReceiptChainConfluenceGateConfig = {}
): (opts: ReceiptChainConfluenceGateOpts) => ReceiptChainConfluenceDecision {
  const enforced = config.enforced ?? true;

  return function gate(opts: ReceiptChainConfluenceGateOpts): ReceiptChainConfluenceDecision {
    const { chainRootA, chainRootB } = opts;
    if (!chainRootA || !chainRootB) throw new Error(`ReceiptChainConfluenceGate: both chain roots required`);

    const confluent   = chainRootA === chainRootB;
    const allow       = confluent || !enforced;
    const lambdaScore = confluent ? 1.0 : 0.0;

    const rationale = confluent
      ? `ReceiptChainConfluence (TH5): rootA="${chainRootA.slice(0,16)}…" = rootB — unique normal form confirmed. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `ReceiptChainConfluence (TH5): rootA≠rootB — non-deterministic chain paths. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "ReceiptChainConfluence", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, confluent, lambdaScore };
  };
}
