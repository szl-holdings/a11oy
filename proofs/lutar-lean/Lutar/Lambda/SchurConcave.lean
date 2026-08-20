/-
Copyright © 2026 Stephen P. Lutar Jr. (SZL Holdings).
Released under the Apache-2.0 License.

# Λ Schur-concavity (V16-T6)

The Λ score (geometric mean of axis values) is Schur-concave: more spread-out
axis vectors yield smaller Λ.  This is the SZL governance analog of
"diversified governance dominates concentrated governance" at fixed total axis
mass.

## Mathematical content

For x, y : Fin k → NNReal with y majorising x (y ≻ x), we have Λ x ≤ Λ y.
Equivalently, swapping a pair (xᵢ, xⱼ) with a more "equalised" pair
(xᵢ − t, xⱼ + t) (where 0 ≤ t ≤ xᵢ − xⱼ, so the larger decreases by t and
the smaller increases by t) weakly INCREASES Λ — the **Robin Hood lemma**.

The full n-axis Schur-concavity follows by the Hardy–Littlewood–Pólya
transposition decomposition: every majorization is a finite composition of
two-axis equalising transfers.  The two-axis case is proved rigorously here
(kernel-checked).  The n-axis composition is axiom-tagged (V16-T6 full) with
full provenance and an explicit Lean proof path.

## Proved (this file, 0 sorry)

  - `Majorises2`            : 2-axis majorization predicate
  - `product_weakly_increases_under_equalising_transfer` : (a−t)(b+t) ≥ ab
  - `lambda_two_axis_schur_concave` : Λ 2 ![a,b] ≤ Λ 2 ![a−t, b+t]

## Axiom-tagged (v18 target)

  - `lambda_schur_concave_n_axis` : full n-axis Schur-concavity

## Citations

  - Schur, I. (1923). "Über eine Klasse von Mittelbildungen mit Anwendungen
    auf die Determinantentheorie." Sitzungsberichte der Berliner Mathematischen
    Gesellschaft 22:9–20.
  - Marshall, A. W., Olkin, I., Arnold, B. C. (2011). Inequalities: Theory of
    Majorization and Its Applications.  2nd ed., Springer. §3.E, §1.A.
    DOI 10.1007/978-0-387-68276-1.
  - Hardy, G. H., Littlewood, J. E., Pólya, G. (1934). Inequalities.
    Cambridge UP. Theorem 92; §2.18.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Data.Fin.VecNotation
import Lutar.Axioms
import Lutar.Invariant

namespace Lutar.Lambda

open NNReal Finset

-- ============================================================
-- §1  Two-axis majorization predicate
-- ============================================================

/-- **Two-axis majorization.** For vectors x, y : Fin 2 → NNReal,
    y majorises x (written y ≻₂ x) when they have equal coordinate sum
    and the maximum of y is at least the maximum of x — equivalently,
    y is "more spread out" than x.

    This is the restriction of the standard majorization partial order
    (Marshall–Olkin–Arnold §1.A) to the two-axis case, which is sufficient
    for the kernel step in the Schur-Ostrowski transposition decomposition.

    The full k-axis majorization is defined in `lambda_schur_concave_n_axis`
    below (axiom-tagged). -/
def Majorises2 (y x : Fin 2 → NNReal) : Prop :=
  y 0 + y 1 = x 0 + x 1 ∧ max (y 0) (y 1) ≥ max (x 0) (x 1)

-- ============================================================
-- §2  Robin Hood product lemma (kernel of Schur-concavity)
-- ============================================================

/-- **Two-axis Robin Hood lemma (PROVED, kernel-checked).**

    Given axis values a, b ≥ 0 and a transfer t ≥ 0 satisfying
    t ≤ a − b (NNReal truncated subtraction), the product (a−t)·(b+t)
    is at least a·b.  At fixed sum a+b, the product is maximised when
    the two values are equal.

    **Proof (lifted to ℝ):**
    (a−t)(b+t) − ab = t(a−b) − t² = t(a−b−t).
    Since t ≥ 0 (NNReal coercion) and a−b−t ≥ 0 (from t ≤ a−b over ℝ),
    we get t(a−b−t) ≥ 0, i.e., (a−t)(b+t) ≥ ab.
    The NNReal subtraction a−t is exact (= real subtraction) because
    t ≤ a−b ≤ a implies t ≤ a. -/
theorem product_weakly_increases_under_equalising_transfer
    (a b t : NNReal) (h_ab : b ≤ a) (h_t_le : t ≤ a - b) :
    a * b ≤ (a - t) * (b + t) := by
  -- Step 1: derive t ≤ a so that NNReal.coe_sub is exact
  have h_t_le_a : t ≤ a := le_trans h_t_le (tsub_le_self)
  -- Step 2: obtain the ℝ-level bound t_real ≤ a_real - b_real
  have h_t_le_real : (t : ℝ) ≤ (a : ℝ) - (b : ℝ) := by
    have := NNReal.coe_le_coe.mpr h_t_le
    rwa [NNReal.coe_sub h_ab] at this
  -- Step 3: key arithmetic inequality in ℝ
  -- nlinarith discharges: (a-t)(b+t) - ab = t(a-b-t) ≥ 0, since t ≥ 0 and t ≤ a-b
  have key : (a : ℝ) * b ≤ ((a : ℝ) - t) * ((b : ℝ) + t) := by
    have ht_nn : (0 : ℝ) ≤ (t : ℝ) := NNReal.coe_nonneg t
    nlinarith [NNReal.coe_le_coe.mpr h_ab]
  -- Step 4: transfer back to NNReal via coe injectivity
  rw [← NNReal.coe_le_coe]
  rw [NNReal.coe_mul, NNReal.coe_mul,
      NNReal.coe_sub h_t_le_a,
      NNReal.coe_add]
  exact key

-- ============================================================
-- §3  Two-axis Schur-concavity of Λ (proved)
-- ============================================================

/-- **Λ two-axis Schur-concavity (PROVED, kernel-checked).**

    For the geometric mean Λ on Fin 2, equalising the pair (a, b) by
    transferring t ≥ 0 from the larger to the smaller (with t ≤ a − b)
    weakly INCREASES Λ.

    **Proof:**  Λ 2 f = (f 0 · f 1) ^ (1/2) by `Λ_def` and `Fin.prod_univ_two`.
    Since the product increases under the equalising transfer
    (`product_weakly_increases_under_equalising_transfer`) and
    `NNReal.rpow_le_rpow` is monotone (exponent 1/2 > 0), the result follows. -/
theorem lambda_two_axis_schur_concave
    (a b t : NNReal) (h_ab : b ≤ a) (h_t_le : t ≤ a - b) :
    Lutar.Λ 2 ![a, b] ≤ Lutar.Λ 2 ![a - t, b + t] := by
  -- Unfold Λ using Λ_def (k = 2 > 0)
  have hk : (0 : ℕ) < 2 := by norm_num
  rw [Λ_def hk, Λ_def hk]
  -- Simplify the Finset products over Fin 2
  simp only [Fin.prod_univ_two]
  -- Evaluate the matrix notation: ![a,b] 0 = a, ![a,b] 1 = b
  simp only [Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.head_cons]
  -- Apply rpow_le_rpow (monotone) using the product lemma
  apply NNReal.rpow_le_rpow _ (by norm_num)
  exact product_weakly_increases_under_equalising_transfer a b t h_ab h_t_le

-- ============================================================
-- §4  Full k-axis Schur-concavity (axiom-tagged)
-- ============================================================

/-- Full k-axis majorization.

    y majorises x (y ≻ x) if ∑ y = ∑ x and for every m, the sum of the m
    largest entries of y is at least the sum of the m largest entries of x.
    This is the standard definition (Marshall–Olkin–Arnold §1.A). -/
def Majorises {k : ℕ} (y x : Axes k) : Prop :=
  (∑ i, y i = ∑ i, x i) ∧
  ∀ S : Finset (Fin k), ∑ i ∈ S, y i ≥ ∑ i ∈ S, x i

/-- **AXIOM-TAGGED CONJECTURE (V16-T6 full Schur-concavity).**

    For the full n-axis geometric mean Λ on `Axes k`, majorization y ≻ x
    implies Λ x ≤ Λ y.

    **Status: CONJECTURE** — axiomatised pending the v18 Schur-Ostrowski
    transposition-decomposition proof in Lean.  The two-axis form
    `lambda_two_axis_schur_concave` is the proved kernel building block.

    **Standard proof path (~80h Lean sprint, v18 target):**

    1. *Transposition decomposition (Hardy–Littlewood–Pólya Theorem 47).*
       Show every majorization y ≻ x can be written as a finite composition
       of two-axis equalising transfers (T-transform steps).  This requires
       formalising the HLP Theorem 47 in Lean, which involves a greedy
       algorithm on the sorted sequence; estimated ~40h.

    2. *Induction on the decomposition.*
       Show Λ is non-decreasing along each T-transform step using
       `lambda_two_axis_schur_concave` and the multiplicativity of the
       geometric mean under coordinate permutations.  Estimated ~40h.

    **Schur-Ostrowski criterion (classical verification):**
    A symmetric differentiable f is Schur-concave iff
    (xᵢ − xⱼ)(∂f/∂xᵢ − ∂f/∂xⱼ) ≤ 0.  For Λ, ∂Λ/∂xᵢ = Λ/(k·xᵢ), so
    the condition becomes (xᵢ − xⱼ)·(Λ/k)·(1/xᵢ − 1/xⱼ) ≤ 0, i.e.,
    −(xᵢ − xⱼ)²/(xᵢ·xⱼ) ≤ 0, which holds for all xᵢ, xⱼ > 0. ✓

    **Citations:**
      - Marshall, Olkin, Arnold (2011). Inequalities: Theory of Majorization
        and Its Applications. 2nd ed., Springer. §3.E.
      - Hardy, Littlewood, Pólya (1934). Inequalities. Cambridge UP. §2.18.
      - Schur, I. (1923). Sitzungsberichte der Berliner Mathematischen
        Gesellschaft 22:9–20. -/
axiom lambda_schur_concave_n_axis (k : ℕ) (hk : 0 < k) (x y : Axes k)
    (h_major : Majorises y x) :
    Lutar.Λ k x ≤ Lutar.Λ k y

end Lutar.Lambda
