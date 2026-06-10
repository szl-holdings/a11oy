# Verified Theorems

> **AUTO-GENERATED — do not edit by hand.** Produced by
> `.github/scripts/gen_verified_theorems.py` from the real `lake build`, and gated
> in CI by `check_verified_theorems_drift.py` (any hand edit or drift fails the
> build). Each entry below is a `theorem`/`lemma` on the governed uniqueness /
> identifiability surface that the Lean kernel checks with **zero `sorry`** and
> whose `#print axioms` footprint stays within
> `{propext, Classical.choice, Quot.sound}` plus the already-declared, cited repo
> axioms in `.github/data/lean_numbers.json`.
>
> **Honesty doctrine v11.** The locked-proven set stays exactly 5. Conjecture 1
> (unconditional Λ uniqueness, `∀ Φ, LutarAxioms Φ → Φ = Λ k`) is machine-checked
> **FALSE** under A1–A5 — `Lutar.Round13.maxAgg_ne_Lambda` exhibits the max
> aggregator as an A1–A5 counterexample — so it can never appear here. Only the
> *conditional* uniqueness (`lambda_unique_of_factors`) is REAL.


## `Lutar/Round13/Lambda_Uniqueness.lean`

- `lambda_satisfiesAxioms_round13 {k : ℕ} (hk : 0 < k) : LutarAxioms (Λ k)`
- `lambda_unique_of_factors {k : ℕ} (hk : 0 < k) (Φ : Aggregator k) (hL : LutarAxioms Φ) (αs : Fin k → NNReal) (hfac : Factors Φ αs) : Φ = Λ k`
- `maxAgg_A5 : IsPermutationInvariant maxAgg`
- `maxAgg_A3 : ∀ c : NNReal, maxAgg (fun _ => c) = c`
- `maxAgg_A2 : ∀ (c : NNReal) (x : Axes 2), maxAgg (fun i => c * x i) = c * maxAgg x`
- `maxAgg_ne_Lambda : maxAgg ≠ Λ 2`

## `Lutar/Uniqueness.lean`

- `lambda_isMonotone {k : Nat} (hk : 0 < k) : IsMonotone (Λ k)`
- `lambda_isHomogeneous {k : Nat} (hk : 0 < k) : IsHomogeneous (Λ k)`
- `lambda_isEgyptianExact {k : Nat} (hk : 0 < k) : IsEgyptianExact k (Λ k)`
- `lambda_isBounded {k : Nat} (hk : 0 < k) : IsBounded hk (Λ k)`
- `Lambda_A5_perm_invariant {k : Nat} (hk : 0 < k) (x : Axes k) (σ : Fin k ≃ Fin k) : Λ k (x ∘ ↑σ) = Λ k x`
- `lambda_isPermutationInvariant {k : Nat} (hk : 0 < k) : IsPermutationInvariant (Λ k)`
- `lambda_satisfiesAxioms {k : Nat} (hk : 0 < k) : LutarAxioms (Λ k)`

## `Lutar/Uniqueness/AxiomCheck.lean`

- `theoremU_axiom_sets_kernel_only : theoremUDisclosed.all (fun p => axiomsAllowed p.2) = true`
- `locked_count_five : lockedNames.length = 5`
- `theoremU_excluded_from_locked : theoremUDisclosed.all (fun p => ! lockedNames.contains p.1) = true`
- `conjecture1_still_open : openConjectures.length = 1`

## `Lutar/Uniqueness/LambdaEquiv.lean`

- `lambdaEquiv_refl {k : ℕ} (Φ : Aggregator k) : LambdaEquiv Φ Φ`
- `lambdaEquiv_symm {k : ℕ} {Φ Ψ : Aggregator k} (h : LambdaEquiv Φ Ψ) : LambdaEquiv Ψ Φ`
- `lambdaEquiv_trans {k : ℕ} {Φ Ψ Χ : Aggregator k} (h₁ : LambdaEquiv Φ Ψ) (h₂ : LambdaEquiv Ψ Χ) : LambdaEquiv Φ Χ`
- `lambdaEquiv_equivalence {k : ℕ} : Equivalence (@LambdaEquiv k)`
- `auditProbe_two : auditProbe 2 = (![4, 1] : Axes 2)`
- `lambdaEquiv_nondegenerate : ∃ Φ Ψ : Aggregator 2, ¬ LambdaEquiv Φ Ψ`

## `Lutar/Uniqueness/TheoremU.lean`

- `CorollaryU2_LambdaUnique_Factors {k : ℕ} (Φ : Aggregator k) (fa : FactorAssumptions Φ) : Φ = Λ k`
- `CorollaryU1_LambdaUnique_Separable {k : ℕ} (Φ : Aggregator k) (sa : SeparableAssumptions Φ) : Φ = Λ k`
- `identifiability_forces_lambda {k : ℕ} (Φ : Aggregator k) (ia : IdentifiabilityAssumptions Φ) : Φ = Λ k`
- `TheoremU_LambdaUnique {k : ℕ} (Φ Ψ : Aggregator k) (iaΦ : IdentifiabilityAssumptions Φ) (iaΨ : IdentifiabilityAssumptions Ψ) : LambdaEquiv Φ Ψ`
- `TheoremU_LambdaUnique_eq {k : ℕ} (Φ Ψ : Aggregator k) (iaΦ : IdentifiabilityAssumptions Φ) (iaΨ : IdentifiabilityAssumptions Ψ) : Φ = Ψ`
- `lambda_equiv_to_eq_of_anchored {k : ℕ} {Φ Ψ : Aggregator k} (_h : LambdaEquiv Φ Ψ) (hΦ : Anchored Φ) (hΨ : Anchored Ψ) : Φ = Ψ`
