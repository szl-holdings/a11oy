// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for AdversarialRobustness
//
// Policy rationale:
//   A composed pipeline is allowed to deploy only when the end-to-end
//   adversarial output perturbation bound ε₂ = L₁·L₂·δ is at or below the
//   configured maximum tolerable perturbation. The Lean theorem proves that
//   if each component is (δ,ε)-robust, the composition is (δ,ε₂)-robust.
//   This gate enforces that the composed system does not amplify adversarial
//   inputs beyond the policy tolerance.
//
//   Lean theorem cited: `robustness_preserved_by_composition`
//   Lean file: Lutar/Composition/AdversarialRobustness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if adversarialRobustness(opts).epsilon2 ≤ maxEpsilon → allow; else → deny
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/Composition/AdversarialRobustness.lean
//   Runtime: szl-holdings/ouroboros agentic/formulas/adversarialRobustness.ts
//   Madry et al. 2018, arXiv:1706.06083

export interface PolicyDecision {
  allow:             boolean;
  rationale:         string;
  formula:           string;
  leanTheorem:       string;
  leanFile:          string;
  leanCommitSha:     string;
  epsilon2:          number;
  composedLipschitz: number;
  maxEpsilon:        number;
  lambdaScore:       number;
}

export interface AdversarialRobustnessGateConfig {
  /**
   * Maximum tolerable ε₂ (end-to-end output perturbation).
   * Default: 1.0 (unit ball tolerance).
   */
  maxEpsilon?: number;
}

export interface AdversarialRobustnessGateOpts {
  lipschitz1: number;
  lipschitz2: number;
  delta: number;
}

const LEAN_THEOREM  = "robustness_preserved_by_composition";
const LEAN_FILE     = "Lutar/Composition/AdversarialRobustness.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_EPS   = 1.0;

// ── Inline formula ────────────────────────────────────────────────────────────
// Lean: robustness_preserved_by_composition:
//   IsRobust mX mY f δ ε₁ → IsRobust mY mZ g ε₁ ε₂ → IsRobust mX mZ (f∘g) δ ε₂
//
// Note (PhD audit 2026-05-29): The Lean theorem is stated for *abstract metric spaces*
// and does not assume Lipschitz structure. The computation below (ε₂ = L₁·L₂·δ) is
// the **Lipschitz special case** where S₁ has Lipschitz constant L₁ (so ε₁ = L₁·δ)
// and S₂ has Lipschitz constant L₂ (so ε₂ = L₂·ε₁ = L₁·L₂·δ). This is a valid
// and common instantiation of the theorem, but it is a specific case, not the
// full generality of `robustness_preserved_by_composition`. Consumers who need
// non-Lipschitz robustness certificates should instantiate the Lean theorem
// directly with their own metric model.
function _composedEpsilon(l1: number, l2: number, delta: number): { epsilon2: number; composedLipschitz: number } {
  return { epsilon2: l1 * l2 * delta, composedLipschitz: l1 * l2 };
}

/**
 * AdversarialRobustness policy gate.
 *
 * Allows pipeline deployment only when the composed adversarial output
 * perturbation bound ε₂ ≤ maxEpsilon.
 *
 * Lean theorem: `robustness_preserved_by_composition`
 * Lean file: Lutar/Composition/AdversarialRobustness.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
export function adversarialRobustnessGate(
  config: AdversarialRobustnessGateConfig = {}
): (opts: AdversarialRobustnessGateOpts) => PolicyDecision {
  const maxEpsilon = config.maxEpsilon ?? DEFAULT_EPS;
  if (!Number.isFinite(maxEpsilon) || maxEpsilon < 0) {
    throw new Error(`AdversarialRobustnessGate: maxEpsilon must be ≥ 0; got ${maxEpsilon}`);
  }

  return function gate(opts: AdversarialRobustnessGateOpts): PolicyDecision {
    const { lipschitz1, lipschitz2, delta } = opts;
    if (lipschitz1 <= 0 || !Number.isFinite(lipschitz1)) {
      throw new Error(`AdversarialRobustnessGate: lipschitz1 must be > 0; got ${lipschitz1}`);
    }
    if (lipschitz2 <= 0 || !Number.isFinite(lipschitz2)) {
      throw new Error(`AdversarialRobustnessGate: lipschitz2 must be > 0; got ${lipschitz2}`);
    }
    if (delta <= 0 || !Number.isFinite(delta)) {
      throw new Error(`AdversarialRobustnessGate: delta must be > 0; got ${delta}`);
    }

    const { epsilon2, composedLipschitz } = _composedEpsilon(lipschitz1, lipschitz2, delta);
    const lambdaScore = 1 / (1 + epsilon2);
    const allow = epsilon2 <= maxEpsilon;

    const rationale = allow
      ? `AdversarialRobustness ε₂ = ${epsilon2.toExponential(4)} ≤ maxEpsilon ${maxEpsilon}: ` +
        `composed pipeline is (${delta},${epsilon2})-robust. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `AdversarialRobustness ε₂ = ${epsilon2.toExponential(4)} > maxEpsilon ${maxEpsilon}: ` +
        `perturbation amplification exceeds policy tolerance — deny deployment. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return {
      allow,
      rationale,
      formula:           "AdversarialRobustness",
      leanTheorem:       LEAN_THEOREM,
      leanFile:          LEAN_FILE,
      leanCommitSha:     LEAN_COMMIT,
      epsilon2,
      composedLipschitz,
      maxEpsilon,
      lambdaScore,
    };
  };
}
