/-
# TH-V18-04 — Egyptian Unit Fraction Weights Sum to 1

Theorem: the sum of k copies of the unit fraction 1/k equals 1 (in ℚ).
Formally: k × (1/k : ℚ) = 1 for k ≥ 1.

This underpins A3 (IsEgyptianExact): each axis carries weight 1/k,
and these weights form a probability simplex (sum to 1).

## Lean Czar status: valid
## Proof method: field_simp + ring (via cast arithmetic)
## Axioms used: none
## Composes: Lutar.Egyptian (v14) — IsEgyptianExact structure
## Citations:
  - Plofker (2009) Mathematics in India §3 — Egyptian unit fractions
  - Lutar.Axioms (IsEgyptianExact) DOI 10.5281/zenodo.20424992
-/
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.FieldSimp
import Mathlib.Data.Rat.Defs
import Mathlib.Data.Rat.Lemmas
import Mathlib.Algebra.Field.Rat

namespace Lutar.Thesis.Egyptian

/-- **TH-V18-04**: sum of k copies of 1/k = 1 in ℚ, for k ≥ 1.
    Proof: k × (1/k) = k/k = 1, using field arithmetic. -/
theorem th_v18_04_egyptian_weight_sum (k : ℕ) (hk : 0 < k) :
    (k : ℚ) * (1 / k) = 1 := by
  field_simp

/-- **TH-V18-04b**: for k = 9 axes (the Lutar Λ₉ gate), weights sum to 1. -/
theorem th_v18_04b_nine_axis_weight_sum :
    (9 : ℚ) * (1 / 9) = 1 := by norm_num

/-- **TH-V18-04c**: Egyptian fraction 1/k > 0 for k ≥ 1 (positive weight). -/
theorem th_v18_04c_egyptian_fraction_pos (k : ℕ) (hk : 0 < k) :
    (0 : ℚ) < 1 / k := by
  apply div_pos (by norm_num)
  exact_mod_cast hk

/-- **TH-V18-04d**: Egyptian fraction 1/k ≤ 1 for k ≥ 1 (normalised weight). -/
theorem th_v18_04d_egyptian_fraction_le_one (k : ℕ) (hk : 0 < k) :
    (1 : ℚ) / k ≤ 1 := by
  rw [div_le_one (by exact_mod_cast hk)]
  exact_mod_cast Nat.one_le_iff_ne_zero.mpr (Nat.pos_iff_ne_zero.mp hk)

/-- **TH-V18-04e**: weight is monotone decreasing in k (more axes → smaller weight per axis). -/
theorem th_v18_04e_weight_decreasing (k m : ℕ) (hk : 0 < k) (hm : 0 < m) (h : k ≤ m) :
    (1 : ℚ) / m ≤ 1 / k := by
  apply div_le_div_of_nonneg_left (by norm_num) (by exact_mod_cast hk) (by exact_mod_cast h)

end Lutar.Thesis.Egyptian
