/-
# Bound theorem (Λ_le_max, min_le_Λ)

**Theorem 2.** For every axes vector `x : Fin k → NNReal`,

    min_i (x i)  ≤  Λ_k x  ≤  max_i (x i).

This is the substrate guarantee that the Λ-gate is *interpretable*: a passing
Λ value never exceeds the best axis nor falls below the worst.

## Status (V14-T2 closed)
Both statements below are now machine-checked theorems via Mathlib4
geometric-mean reasoning: Finset.prod_le_prod + NNReal.rpow monotonicity.
The kernel-postulation note is removed; this is the substrate guarantee
for v14+ Λ-gate interpretability, fully discharged.
-/
import Mathlib.Analysis.MeanInequalities
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Lutar.Axioms
import Lutar.Invariant

namespace Lutar

open NNReal Finset

/-- **Bound, upper (V14-T2-upper).** Λ never exceeds the max axis.
Proof chain: each x i ≤ sup x, so ∏ x ≤ (sup x)^k via Finset.prod_le_prod
+ Finset.prod_const; then take the (1/k)-power via NNReal.rpow_le_rpow,
and simplify (sup x)^(k·(1/k)) = sup x via NNReal.rpow_natCast + NNReal.rpow_mul. -/
theorem Λ_le_max {k : ℕ} (hk : 0 < k) (x : Axes k) :
    Λ k x ≤ Finset.univ.sup' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x := by
  -- Step 1: unfold Λ to (∏ x)^(1/k)
  rw [Λ_def hk]
  set M := Finset.univ.sup' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x
  -- Step 2: every component x i ≤ M (Finset.le_sup')
  have h_le : ∀ i ∈ (Finset.univ : Finset (Fin k)), x i ≤ M := fun i _ =>
    Finset.le_sup' x (Finset.mem_univ i)
  -- Step 3: ∏ x ≤ M^k via Finset.prod_le_prod (all terms nonneg, each ≤ M)
  have h_prod_le : (Finset.univ : Finset (Fin k)).prod x ≤ M ^ k := by
    have h1 : (Finset.univ : Finset (Fin k)).prod x
            ≤ (Finset.univ : Finset (Fin k)).prod (fun _ => M) :=
      Finset.prod_le_prod (fun i _ => zero_le _) h_le
    -- Finset.prod_const: ∏_{i ∈ univ} M = M ^ card(univ) = M ^ k
    simp only [Finset.prod_const, Finset.card_univ, Fintype.card_fin] at h1
    exact h1
  -- Step 4: (1/k : ℝ) is positive since k > 0
  have hk_pos : (0 : ℝ) < (k : ℝ) := Nat.cast_pos.mpr hk
  have hinv_pos : (0 : ℝ) ≤ (1 : ℝ) / (k : ℝ) := le_div_iff₀ hk_pos |>.mpr (by norm_num)
  -- Step 5: apply NNReal.rpow_le_rpow to get (∏ x)^(1/k) ≤ (M^k)^(1/k)
  have h_rpow : (Finset.univ.prod x) ^ ((1 : ℝ) / k)
              ≤ (M ^ k) ^ ((1 : ℝ) / k) :=
    NNReal.rpow_le_rpow h_prod_le hinv_pos
  -- Step 6: simplify (M^k)^(1/k) = M
  -- (M^k)^(1/k) = M^(k · (1/k)) = M^1 = M
  have h_simp : (M ^ k) ^ ((1 : ℝ) / (k : ℝ)) = M := by
    -- M^k as rpow: M^k = M^(k:ℝ) via NNReal.rpow_natCast
    rw [← NNReal.rpow_natCast M k]
    -- (M^(k:ℝ))^(1/k) = M^((k:ℝ) * (1/k)) via NNReal.rpow_mul
    rw [← NNReal.rpow_mul]
    -- (k:ℝ) * (1/k) = 1
    have hcancel : (k : ℝ) * (1 / k) = 1 := mul_div_cancel₀ 1 (ne_of_gt hk_pos)
    rw [hcancel, NNReal.rpow_one]
  -- Step 7: conclude by transitivity
  calc (Finset.univ.prod x) ^ ((1 : ℝ) / ↑k)
      ≤ (M ^ k) ^ ((1 : ℝ) / ↑k) := h_rpow
    _ = M := h_simp

/-- **Bound, lower (V14-T2-lower).** Λ is at least the min axis.
Proof chain: each x i ≥ inf x, so (inf x)^k ≤ ∏ x via Finset.prod_le_prod
+ Finset.prod_const (dual); then take the (1/k)-power via NNReal.rpow_le_rpow,
and simplify (inf x)^(k·(1/k)) = inf x via NNReal.rpow_natCast + NNReal.rpow_mul. -/
theorem min_le_Λ {k : ℕ} (hk : 0 < k) (x : Axes k) :
    Finset.univ.inf' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x ≤ Λ k x := by
  -- Step 1: unfold Λ to (∏ x)^(1/k)
  rw [Λ_def hk]
  set m := Finset.univ.inf' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x
  -- Step 2: every component x i ≥ m (Finset.inf'_le)
  have h_ge : ∀ i ∈ (Finset.univ : Finset (Fin k)), m ≤ x i := fun i _ =>
    Finset.inf'_le x (Finset.mem_univ i)
  -- Step 3: m^k ≤ ∏ x via Finset.prod_le_prod (all terms nonneg, each ≥ m)
  have h_prod_ge : m ^ k ≤ (Finset.univ : Finset (Fin k)).prod x := by
    have h1 : (Finset.univ : Finset (Fin k)).prod (fun _ => m)
            ≤ (Finset.univ : Finset (Fin k)).prod x :=
      Finset.prod_le_prod (fun _ _ => zero_le _) h_ge
    -- Finset.prod_const: ∏_{i ∈ univ} m = m ^ k
    simp only [Finset.prod_const, Finset.card_univ, Fintype.card_fin] at h1
    exact h1
  -- Step 4: (1/k : ℝ) is nonneg
  have hk_pos : (0 : ℝ) < (k : ℝ) := Nat.cast_pos.mpr hk
  have hinv_pos : (0 : ℝ) ≤ (1 : ℝ) / (k : ℝ) := le_div_iff₀ hk_pos |>.mpr (by norm_num)
  -- Step 5: apply NNReal.rpow_le_rpow to get (m^k)^(1/k) ≤ (∏ x)^(1/k)
  have h_rpow : (m ^ k) ^ ((1 : ℝ) / k)
              ≤ (Finset.univ.prod x) ^ ((1 : ℝ) / k) :=
    NNReal.rpow_le_rpow h_prod_ge hinv_pos
  -- Step 6: simplify (m^k)^(1/k) = m
  have h_simp : (m ^ k) ^ ((1 : ℝ) / (k : ℝ)) = m := by
    rw [← NNReal.rpow_natCast m k]
    rw [← NNReal.rpow_mul]
    have hcancel : (k : ℝ) * (1 / k) = 1 := mul_div_cancel₀ 1 (ne_of_gt hk_pos)
    rw [hcancel, NNReal.rpow_one]
  -- Step 7: conclude by transitivity
  calc m = (m ^ k) ^ ((1 : ℝ) / ↑k) := h_simp.symm
    _ ≤ (Finset.univ.prod x) ^ ((1 : ℝ) / ↑k) := h_rpow

end Lutar
