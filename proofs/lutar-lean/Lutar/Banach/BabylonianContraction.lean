/-
# R3-G1 — Babylonian (Heron) iteration as a Banach contraction

The recurrence  `x_{n+1} = (x_n + S/x_n) / 2`  due to YBC 7289
(Old-Babylonian, c. 1800 BCE) computes `√S`. By AM-GM, every iterate after
the first satisfies `x_n ≥ √S`, and on the half-line `I = [√S, ∞)` the map
`T(x) = (x + S/x)/2` has derivative `T'(x) = (1 - S/x²)/2 ∈ [0, 1/2)`, hence
is a Banach contraction with Lipschitz constant `≤ 1/2`
[Banach 1922, *Fund. Math.* 3, 133–181].

This is the *lineage hook* for TH12 `ΛGateLID_DPO_stability`: the same
contraction shape underwrites convergence of the policy-loop rollback step.

Citations:
- Neugebauer, O. (1957). *The Exact Sciences in Antiquity* (2nd ed.). Dover.
- Friberg, J. (2007). *A Remarkable Collection of Babylonian Mathematical Texts.* Springer.
- Høyrup, J. (2002). *Lengths, Widths, Surfaces.* Springer.
- YBC 7289 catalog entry: Yale Peabody Museum, Babylonian Collection.

Status: statement compiles; structural proof recorded with two tagged
`sorry`s — (i) the algebraic Lipschitz bound on `I`, (ii) the AM-GM step
guaranteeing the iterate lands in `I`. Both are Mathlib-trivial.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Data.Real.Sqrt

namespace Lutar.Banach.Babylonian

open Real

/-- The Babylonian iteration map for `√S`:  `T(x) = (x + S/x)/2`. -/
noncomputable def T (S x : ℝ) : ℝ := (x + S / x) / 2

/-- The post-step invariant half-line  `I = { x : √S ≤ x }`. -/
def invariantHalfLine (S : ℝ) : Set ℝ := { x | Real.sqrt S ≤ x }

/-- **AM-GM step.** For `S ≥ 0` and `x > 0`, the next iterate lands in `I`. -/
theorem one_step_into_invariant (S x : ℝ) (hS : 0 ≤ S) (hx : 0 < x) :
    T S x ∈ invariantHalfLine S := by
  -- `(x + S/x)/2 ≥ √(x · S/x) = √S` is AM-GM applied to `x` and `S/x`.
  unfold T invariantHalfLine
  simp only [Set.mem_setOf_eq]
  -- Show √S ≤ (x + S/x)/2
  have hx_ne : x ≠ 0 := ne_of_gt hx
  -- Case split on S = 0
  by_cases hS0 : S = 0
  · subst hS0
    simp only [Real.sqrt_zero, zero_div, add_zero]
    positivity
  · have hSpos : 0 < S := lt_of_le_of_ne hS (Ne.symm hS0)
    have hSxpos : 0 < S / x := div_pos hSpos hx
    -- Key: (x + S/x)² ≥ 4S, combined with x + S/x > 0, gives x + S/x ≥ 2√S
    have hsum_pos : 0 < x + S / x := by linarith
    have h_sq : 4 * S ≤ (x + S / x) ^ 2 := by
      have : 0 ≤ (x - S / x) ^ 2 := sq_nonneg _
      have hexp : (x + S / x) ^ 2 = (x - S / x) ^ 2 + 4 * (x * (S / x)) := by ring
      have hkey : x * (S / x) = S := by field_simp
      rw [hexp, hkey]
      linarith
    -- From 4S ≤ (x + S/x)², derive 2√S ≤ x + S/x
    have h_sum_sq_rw : Real.sqrt ((x + S / x) ^ 2) = x + S / x :=
      Real.sqrt_sq hsum_pos.le
    have h_4S_sqrt : Real.sqrt (4 * S) = 2 * Real.sqrt S := by
      rw [show (4 : ℝ) = 2 ^ 2 by norm_num]
      rw [show 2 ^ 2 * S = S * 2 ^ 2 by ring]
      rw [Real.sqrt_mul hS]
      rw [Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 2)]
      ring
    have hle := Real.sqrt_le_sqrt h_sq
    rw [h_4S_sqrt, h_sum_sq_rw] at hle
    linarith

/-- **Lipschitz bound on the invariant half-line.**
    For `S > 0` and any `x, y ∈ I`, `|T(x) - T(y)| ≤ (1/2) · |x - y|`. -/
theorem babylonian_lipschitz_le_half
    (S : ℝ) (hS : 0 < S) {x y : ℝ}
    (hx : x ∈ invariantHalfLine S) (hy : y ∈ invariantHalfLine S) :
    |T S x - T S y| ≤ (1/2) * |x - y| := by
  -- `T'(x) = (1 - S/x²)/2`; for x ≥ √S, 0 ≤ 1 - S/x² ≤ 1, so |T'| ≤ 1/2.
  -- MVT or direct algebra gives the bound. Concretely:
  --   T(x) - T(y) = (x - y)/2 + (S/x - S/y)/2
  --              = (x - y)/2 - S·(x - y)/(2·x·y)
  --              = (x - y) · (1 - S/(x·y)) / 2
  -- and x, y ≥ √S ⇒ x·y ≥ S ⇒ 0 ≤ 1 - S/(x·y) < 1.
  unfold T
  unfold invariantHalfLine at hx hy
  simp only [Set.mem_setOf_eq] at hx hy
  have hsqrt_S_nn : 0 ≤ Real.sqrt S := Real.sqrt_nonneg _
  have hsqrt_S_pos : 0 < Real.sqrt S := Real.sqrt_pos.mpr hS
  have hx_pos : 0 < x := lt_of_lt_of_le hsqrt_S_pos hx
  have hy_pos : 0 < y := lt_of_lt_of_le hsqrt_S_pos hy
  have hxy_pos : 0 < x * y := mul_pos hx_pos hy_pos
  have hx_ne : x ≠ 0 := ne_of_gt hx_pos
  have hy_ne : y ≠ 0 := ne_of_gt hy_pos
  have hxy_ne : x * y ≠ 0 := ne_of_gt hxy_pos
  -- x·y ≥ S (since x ≥ √S, y ≥ √S, and √S · √S = S)
  have hxy_ge_S : S ≤ x * y := by
    have h1 : Real.sqrt S * Real.sqrt S ≤ x * y :=
      mul_le_mul hx hy hsqrt_S_nn hx_pos.le
    rwa [Real.mul_self_sqrt hS.le] at h1
  -- Algebraic identity: T(x) - T(y) = (x - y) * (1 - S/(x*y)) / 2
  have hdiff : (x + S / x) / 2 - (y + S / y) / 2 =
      (x - y) * (1 - S / (x * y)) / 2 := by
    field_simp
    ring
  rw [hdiff]
  -- |((x - y) * (1 - S/(x*y))) / 2| = |x - y| * |1 - S/(x*y)| / 2
  rw [abs_div, abs_mul]
  -- RHS: 1/2 * |x - y|
  -- Goal: |x - y| * |1 - S/(x*y)| / |2| ≤ 1/2 * |x - y|
  have h2pos : (0:ℝ) < 2 := by norm_num
  rw [abs_of_pos h2pos]
  -- Suffices: |1 - S/(x*y)| ≤ 1
  have hSxy_nn : 0 ≤ S / (x * y) := div_nonneg hS.le hxy_pos.le
  have hSxy_le_1 : S / (x * y) ≤ 1 := (div_le_one hxy_pos).mpr hxy_ge_S
  have h_abs_le_1 : |1 - S / (x * y)| ≤ 1 := by
    rw [abs_le]
    constructor
    · linarith
    · linarith
  have h_xy_nn : 0 ≤ |x - y| := abs_nonneg _
  -- |x - y| * |1 - S/(x*y)| / 2 ≤ 1/2 * |x - y|
  rw [div_le_iff h2pos]
  rw [show (1/2 : ℝ) * |x - y| * 2 = |x - y| by ring]
  calc |x - y| * |1 - S / (x * y)|
      ≤ |x - y| * 1 := mul_le_mul_of_nonneg_left h_abs_le_1 h_xy_nn
    _ = |x - y| := mul_one _

/-- **Main: Babylonian iteration is a Banach contraction on `I`.**

    Formally: the restriction `T_S : I → I` is well-defined (one_step_into_invariant
    applied to any `x ∈ I` since `I ⊆ (0, ∞)` when `S > 0`) and Lipschitz with
    constant `1/2 < 1`, hence by the Banach fixed-point theorem
    [Banach 1922; Mathlib `ContractionMappingTheorem`] has a unique fixed
    point in the complete subspace `I`, which is `√S`. -/
theorem babylonian_sqrt_is_banach_contraction
    (S : ℝ) (hS : 0 < S) :
    ∀ x y, x ∈ invariantHalfLine S → y ∈ invariantHalfLine S →
      |T S x - T S y| ≤ (1/2) * |x - y| :=
  fun x y hx hy => babylonian_lipschitz_le_half S hS hx hy

/-- **Fixed-point identity.**  `T S (√S) = √S`. -/
theorem T_fixedPoint_sqrt (S : ℝ) (hS : 0 < S) : T S (Real.sqrt S) = Real.sqrt S := by
  unfold T
  have hsq : Real.sqrt S * Real.sqrt S = S := Real.mul_self_sqrt hS.le
  have hsqpos : 0 < Real.sqrt S := Real.sqrt_pos.mpr hS
  have hsqne : Real.sqrt S ≠ 0 := ne_of_gt hsqpos
  -- In Mathlib v4.13.0 field_simp closes this goal using mul_self_sqrt directly
  field_simp [Real.mul_self_sqrt hS.le]

end Lutar.Banach.Babylonian
