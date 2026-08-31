/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Lutar — Axioms A1..A5

The Lutar Invariant Λ_k : (Fin k → ℝ≥0) → ℝ≥0 is the unique scalar
runtime-trust aggregator that satisfies the five axioms below.

We follow the convention used in `packages/ouroboros-invariant`:
weights are Egyptian unit fractions (1/k), values are in [0,1].

## A3 fix (PhD-Math V14-C1 / integrity-remediation 2026-05-28)

The original A3 field `weight_eq : (1:ℚ)/k = (1:ℚ)/k` was a tautology —
it did not constrain the aggregator at all. PhD-Math audit (V14-C1) flagged
this: any aggregator satisfied A3 vacuously.

The fix (V14PF-T1): replace with `A3_normalize`, the equal-weight diagonal
commitment S1: `∀ c, Λ (fun _ => c) = c`. This constrains Λ to be exactly
the geometric mean on the diagonal, which (together with A1, A2, A5) forces
uniqueness via the Cauchy functional equation argument documented in
`Lutar/Uniqueness.lean`.

The concrete proof that `Lutar.Λ k` satisfies `A3_normalize` is provided in
`Lutar/Invariant.lean` as `theorem a3_normalize_proof`, to avoid a circular
import (Invariant.lean already imports Axioms.lean for the type definitions).

**Postulation rationale** (why `k_pos` is a hypothesis in `IsEgyptianExact`):
Positivity of `k` is a structural precondition — it cannot be derived from
the axiom system itself, which is parametric in `k`. It is the standard
hypothesis required by `Finset.univ.sup'` nonemptiness in A4.

## A5 addition (PhD-Math audit 2026-06-02 / fix/uniqueness-a1-a5-2026-06-02)

A5 (permutation invariance) was MISSING from the original LutarAxioms structure.
This omission made the uniqueness claim (thm:unique-aggregator / TH10) FALSE:
the asymmetric geometric mean Φ(x₁,x₂) = x₁^(2/3)·x₂^(1/3) satisfies
A1–A4 but is not equal to Λ₂ = (x₁·x₂)^(1/2).

A5 is NECESSARY at step 7 of the Aczél 1966 Thm 5.1 proof: without it,
each axis exponent αᵢ is unconstrained (α₁=2/3, α₂=1/3 in the counterexample).
With A5, all αᵢ must equal α = 1/k.

References:
- THESIS_LEAN_RECONCILIATION.md (2026-06-02): full counterexample analysis
- PHASE3_FINAL_SUMMARY.md (2026-06-02) Gate 6: conjunctiveGateCounterexample
- Aczél, J. (1966). Lectures on Functional Equations. Academic Press. Thm 5.1.
- Hardy, G.H., Littlewood, J.E., Pólya, G. (1934). Inequalities. §2.18.

## Axiom provenance / v3 drift disclosure (HONESTY — do not remove)

The axiom *names* A1..A5 are stable, but two axioms changed MEANING between the
v3 Zenodo deposit and current HEAD (`c7c0ba17`, v14+). A reader comparing the
published v3 paper to this file MUST know the definitions differ:

| Axiom | v3 deposit (Zenodo 10.5281/zenodo.19983066, 2026-05-02) | Current HEAD (this file) |
|-------|----------------------------------------------------------|--------------------------|
| A2    | "zero-pinning" (Λ(...,0,...) = 0)                          | **Positive homogeneity, deg 1** (`IsHomogeneous`) |
| A4    | "page-curve concavity"                                    | **Bounded by max axis** (`IsBounded`) |

These are mathematically DISTINCT properties. **The v3 paper's proof claims were
verified against the v3 axiom set; they do NOT automatically carry over to the
current A2/A4 definitions without re-verification.** This is consistent with the
broader honesty posture: Λ-uniqueness is **Conjecture 1, never a theorem**, and
the four non-symmetry axioms alone do not pin Λ uniquely — A2 (1-homogeneity)
is the load-bearing axiom, and A5 (permutation invariance) is also necessary
(see the A5 counterexample above). Lean proofs in `Lutar/Uniqueness.lean` carry
tracked `sorry`s for the open Cauchy step; the bounty repo `szl-holdings/lambda-
bounty` is the public intake for a complete machine-checked proof.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Data.NNReal.Basic
import Mathlib.GroupTheory.Perm.Basic

open NNReal Real

namespace Lutar

/-- Axes vector: `k` non-negative reals in `[0,∞)`. -/
abbrev Axes (k : ℕ) := Fin k → NNReal

/-- A trust aggregator on `k` axes. -/
abbrev Aggregator (k : ℕ) := Axes k → NNReal

/-- **A1 — Monotonicity.** Increasing any axis cannot decrease Λ. -/
def IsMonotone {k : ℕ} (Λ : Aggregator k) : Prop :=
  ∀ x y : Axes k, (∀ i, x i ≤ y i) → Λ x ≤ Λ y

/-- **A2 — Positive homogeneity (degree 1).** Scaling every axis by `c`
scales the output by `c`. -/
def IsHomogeneous {k : ℕ} (Λ : Aggregator k) : Prop :=
  ∀ (c : NNReal) (x : Axes k), Λ (fun i => c * x i) = c * Λ x

/-- **A3 — Egyptian-exact diagonal normalization (V14PF-T1 fix).**
All `k` axes share the same unit-fraction weight `1/k`.
The *meaningful* constraint (S1 from Uniqueness.lean §S1): `Λ (fun _ => c) = c`.

This replaces the tautological `weight_eq : (1:ℚ)/k = (1:ℚ)/k` that was
present before the V14-C1 integrity fix. The field `A3_normalize` pins Λ
to the diagonal of the simplex. -/
structure IsEgyptianExact (k : ℕ) (Λ : Aggregator k) : Prop where
  /-- k must be positive for the geometric mean to be well-defined. -/
  k_pos        : 0 < k
  /-- Equal-weight diagonal commitment (S1 / V14PF-T1): the constant-vector
      input returns the constant. This is the meaningful content of A3. -/
  A3_normalize : ∀ c : NNReal, Λ (fun _ => c) = c

/-- **A4 — Bounded by max axis.** Λ is never larger than the largest axis. -/
def IsBounded {k : ℕ} (hk : 0 < k) (Λ : Aggregator k) : Prop :=
  ∀ x : Axes k,
    Λ x ≤ Finset.univ.sup' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x

/-- **A5 — Permutation invariance (2026-06-02 addition; NECESSARY for uniqueness).**
Reordering the input axes does not change the aggregator output.
This axiom is required to force all axis exponents αᵢ to be equal in the
Cauchy functional equation argument (Aczél 1966 Thm 5.1, step 7).
Without A5, the asymmetric aggregator Φ(x₁,x₂) = x₁^(2/3)·x₂^(1/3)
satisfies A1–A4 but ≠ Λ₂, falsifying the uniqueness claim. -/
def IsPermutationInvariant {k : ℕ} (Λ : Aggregator k) : Prop :=
  ∀ (x : Axes k) (σ : Fin k ≃ Fin k), Λ (x ∘ ↑σ) = Λ x

/-- The five Lutar axioms collected (A1–A5).
A5 added 2026-06-02: permutation invariance is NECESSARY for uniqueness.
PR: fix/uniqueness-a1-a5-2026-06-02.
Doctrine: Λ = Conjecture 1 (Lake CI must verify before theorem claim). -/
structure LutarAxioms {k : ℕ} (Λ : Aggregator k) : Prop where
  A1 : IsMonotone Λ
  A2 : IsHomogeneous Λ
  A3 : IsEgyptianExact k Λ
  A4 : IsBounded A3.k_pos Λ
  A5 : IsPermutationInvariant Λ

end Lutar
