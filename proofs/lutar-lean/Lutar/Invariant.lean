/-
# The Lutar Invariant Λ_k

Definition:

    Λ_k(x₁,...,x_k) := (x₁ · x₂ · ... · x_k)^(1/k)

i.e. the *weighted geometric mean* with all weights equal to the Egyptian unit
fraction `1/k`. This is the concrete witness function whose uniqueness we
prove in `Uniqueness.lean`.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Algebra.BigOperators.Group.Finset
import Lutar.Axioms

namespace Lutar

open NNReal

/-- The Lutar Invariant: geometric mean with unit-fraction weights. -/
noncomputable def Λ (k : ℕ) (x : Axes k) : NNReal :=
  if hk : k = 0 then 0
  else
    let prod : NNReal := (Finset.univ : Finset (Fin k)).prod x
    prod ^ ((1 : ℝ) / (k : ℝ))

/-- For `k ≥ 1`, Λ is well-defined as the k-th root of the axis product. -/
theorem Λ_def {k : ℕ} (hk : 0 < k) (x : Axes k) :
    Λ k x = ((Finset.univ : Finset (Fin k)).prod x) ^ ((1 : ℝ) / (k : ℝ)) := by
  simp [Λ, hk.ne']

end Lutar

/-! ## A3 normalize proof (V14PF-T1 / PhD-Math integrity-remediation 2026-05-28) -/

/-- **a3_normalize_proof** (V14PF-T1).
The concrete witness `Lutar.Λ k` satisfies the A3 diagonal commitment:
`Λ k (fun _ => c) = c` for all `c : NNReal` and `k > 0`.

This proves that the new `IsEgyptianExact.A3_normalize` field is not empty:
the geometric mean witness satisfies it. Together with A1, A2, A4, this is
the S1 condition required to upgrade `lutar_unique` from Conjecture to Theorem.

Proof (V14PF-T1 Mathlib chain):
  1. `Finset.prod_const`: `∏_{i ∈ univ} c = c ^ Finset.card univ = c ^ k`.
  2. `NNReal.rpow_natCast`: `c ^ k = c ^ (k : ℝ)`.
  3. `NNReal.rpow_mul`: `(c ^ (k : ℝ)) ^ (1/k) = c ^ (k · (1/k)) = c ^ 1`.
  4. `NNReal.rpow_one`: `c ^ 1 = c`. -/
theorem a3_normalize_proof (k : ℕ) (hk : 0 < k) (c : NNReal) :
    Lutar.Λ k (fun _ => c) = c := by
  simp only [Lutar.Λ, hk.ne', dite_false]
  rw [Finset.prod_const, Finset.card_fin]
  rw [← NNReal.rpow_natCast c k, ← NNReal.rpow_mul]
  simp [hk.ne']
