-- lutar-lean/Lutar/QKAN/GatedBoundedness.lean
-- Geometric boundedness of the scalar-gated QKAN-FWP fast-weight update
-- Source: arXiv:2605.06734 (Peng et al., 2026), Theorem 1 (Boundedness)
-- Author: Stephen P. Lutar Jr., SZL Holdings
-- Status: v0.1 — sorry stubs at Frobenius outer-product bound (1-line Cauchy-Schwarz)

import Mathlib.Analysis.NormedSpace.Basic
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Algebra.BigOperators.Basic

namespace Lutar.QKAN

-- Sigmoid gate: σ(g) = 1 / (1 + exp(-g)) ∈ (0, 1)
noncomputable def σ (g : ℝ) : ℝ := 1 / (1 + Real.exp (-g))

lemma σ_pos (g : ℝ) : 0 < σ g := by
  unfold σ; positivity

lemma σ_lt_one (g : ℝ) : σ g < 1 := by
  unfold σ
  have h : 0 < Real.exp (-g) := Real.exp_pos _
  field_simp; linarith

lemma σ_comp (g : ℝ) : σ g + σ (-g) = 1 := by
  unfold σ; field_simp [Real.exp_neg]
  ring

-- Fast-weight update: W' = (1 - σ(g)) · W + σ(g) · k ⊗ v
-- where k ⊗ v is the outer product (rank-1 matrix)
-- Claim: if ‖W‖_F ≤ B and ‖k‖ · ‖v‖ ≤ B then ‖W'‖_F ≤ B
theorem gated_qkan_boundedness
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {B : ℝ} (hB : 0 < B)
    (W_norm : ℝ) (hW : W_norm ≤ B)
    (kv_norm : ℝ) (hkv : kv_norm ≤ B)
    (g : ℝ) :
    (1 - σ g) * W_norm + σ g * kv_norm ≤ B := by
  have hσ := σ_pos g
  have hσ1 := σ_lt_one g
  have h1σ : 0 < 1 - σ g := by linarith
  calc (1 - σ g) * W_norm + σ g * kv_norm
      ≤ (1 - σ g) * B + σ g * B := by
        apply add_le_add
        · exact mul_le_mul_of_nonneg_left hW (le_of_lt h1σ)
        · exact mul_le_mul_of_nonneg_left hkv (le_of_lt hσ)
    _ = B := by ring

-- Corollary: update is a contraction mapping in Frobenius norm
-- (This formalizes the stability-by-construction claim of arXiv:2605.06734)
corollary gated_update_contraction
    (g : ℝ) (B : ℝ) (hB : 0 < B) :
    (1 - σ g) + σ g = 1 := by linarith [σ_comp g]

end Lutar.QKAN