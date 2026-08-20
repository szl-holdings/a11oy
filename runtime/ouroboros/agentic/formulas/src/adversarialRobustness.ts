// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime mirror of Lean theorem `AdversarialRobustness`
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Composition/AdversarialRobustness.lean
//   Blob SHA: a96e448f83da40f06f005e7f8ff0492e0870e819
//   Commit SHA (main): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Theorem statement (Lean):
//   robustness_preserved_by_composition:
//     IsRobust mX mY f δ ε₁ → IsRobust mY mZ g ε₁ ε₂ →
//     IsRobust mX mZ (compose_fn f g) δ ε₂
//
// Lipschitz robustness composition: if system f is (δ,ε₁)-robust and
// system g is (ε₁,ε₂)-robust, then f∘g is (δ,ε₂)-robust.
// A (δ,ε)-robust system maps every δ-ball in input space to an ε-ball
// in output space — adversarial perturbations are bounded end-to-end.
//
// References:
//   Madry et al. 2018, Towards Deep Learning Models Resistant to Adversarial Attacks,
//   ICLR 2018. arXiv:1706.06083

/** Inputs for the adversarial robustness bound check. */
export interface AdversarialRobustnessOpts {
  /**
   * Lipschitz constants of the two composed systems.
   * For a Lipschitz-L function: if |x−x'| ≤ δ then |f(x)−f(x')| ≤ L·δ.
   * The theorem applies with ε₁ = L1·δ, ε₂ = L2·ε₁ = L1·L2·δ.
   */
  lipschitz1: number;
  lipschitz2: number;
  /** Input perturbation budget δ > 0. */
  delta: number;
}

/** Result of adversarialRobustness. */
export interface AdversarialRobustnessResult {
  /** Output perturbation bound after f: ε₁ = lipschitz1 · δ. */
  epsilon1: number;
  /** Output perturbation bound after g∘f: ε₂ = lipschitz2 · ε₁. */
  epsilon2: number;
  /** Composed Lipschitz constant: L = lipschitz1 · lipschitz2. */
  composedLipschitz: number;
  /**
   * Whether the composed system satisfies the robustness predicate
   * (ε₂ is finite and the composition is (δ,ε₂)-robust).
   */
  robust: boolean;
  /**
   * Λ-score: 1/(1 + ε₂) — higher is better (tighter bound = more robust).
   */
  lambdaScore: number;
}

/**
 * Compute the adversarial robustness bound for two composed Lipschitz systems.
 *
 * Lean theorem: `robustness_preserved_by_composition`
 * Lean file: Lutar/Composition/AdversarialRobustness.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * @throws if any argument is non-positive or non-finite
 */
export function adversarialRobustness(opts: AdversarialRobustnessOpts): AdversarialRobustnessResult {
  const { lipschitz1, lipschitz2, delta } = opts;
  if (!Number.isFinite(lipschitz1) || lipschitz1 <= 0)
    throw new Error(`lipschitz1 must be > 0; got ${lipschitz1}`);
  if (!Number.isFinite(lipschitz2) || lipschitz2 <= 0)
    throw new Error(`lipschitz2 must be > 0; got ${lipschitz2}`);
  if (!Number.isFinite(delta) || delta <= 0)
    throw new Error(`delta must be > 0; got ${delta}`);

  // ε₁ = L₁ · δ  (output perturbation of f)
  const epsilon1 = lipschitz1 * delta;
  // ε₂ = L₂ · ε₁  (output perturbation of g∘f)
  const epsilon2 = lipschitz2 * epsilon1;
  // Composed Lipschitz constant
  const composedLipschitz = lipschitz1 * lipschitz2;

  // Robustness predicate: both ε values are finite positive reals
  const robust = Number.isFinite(epsilon2) && epsilon2 > 0;

  // Λ-score: 1/(1+ε₂) in (0,1]; higher ε₂ → lower Λ
  const lambdaScore = 1 / (1 + epsilon2);

  return { epsilon1, epsilon2, composedLipschitz, robust, lambdaScore };
}

/**
 * Scalar overload: returns only the composed output bound ε₂.
 * Used by the a11oy policy gate and OTel span wrapper.
 */
export function adversarialRobustnessScalar(lipschitz1: number, lipschitz2: number, delta: number): number {
  return adversarialRobustness({ lipschitz1, lipschitz2, delta }).epsilon2;
}
