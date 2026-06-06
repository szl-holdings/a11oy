/-
# Egyptian unit-fraction reconstruction (Axiom A3 support)

The Lutar Invariant requires every weight to be an exact unit fraction `1/n`.
This file proves the basic lemma we need: for any `k ≥ 1`, the constant
weight vector `(1/k, ..., 1/k)` over `Fin k` sums to exactly 1 with no
rounding error.

We also state the uniqueness corollary: a "single unit fraction" weight
distribution over `k` equal-importance axes is forced to be `1/k`.
-/
import Mathlib.Data.Rat.Defs
import Mathlib.Data.Fin.Basic
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Tactic

namespace Lutar.Egyptian

/-- The constant unit-fraction weight: `w i = 1/k` for all `i : Fin k`. -/
def unitWeight (k : ℕ) (_ : Fin k) : ℚ := if k = 0 then 0 else 1 / (k : ℚ)

/-- **Egyptian exactness.** The unit-weight vector sums to 1 (when `k ≥ 1`). -/
theorem unitWeight_sum_eq_one {k : ℕ} (hk : 0 < k) :
    (Finset.univ : Finset (Fin k)).sum (fun i => unitWeight k i) = 1 := by
  have hk' : (k : ℚ) ≠ 0 := by exact_mod_cast hk.ne'
  simp only [unitWeight, hk.ne', if_false, Finset.sum_const, Finset.card_univ,
             Fintype.card_fin, nsmul_eq_mul]
  field_simp

/-- **Uniqueness of equal-importance unit fractions.** If every axis carries
the same unit-fraction weight `1/n` for some `n : ℕ`, and the weights sum to
1 over `k` axes, then `n = k`. -/
theorem unitWeight_unique {k n : ℕ} (hk : 0 < k) (hn : 0 < n)
    (h : (k : ℚ) * (1 / n) = 1) : n = k := by
  have hn' : (n : ℚ) ≠ 0 := by exact_mod_cast hn.ne'
  field_simp at h
  exact_mod_cast h.symm

end Lutar.Egyptian
