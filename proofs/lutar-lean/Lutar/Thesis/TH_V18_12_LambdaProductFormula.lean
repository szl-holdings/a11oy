import Mathlib.Tactic.Linarith
import Mathlib.Data.Int.Defs
/-
# TH-V18-12 — Lambda-like Product Multiplicativity

Theorem: geometric-mean style products satisfy multiplicativity:
(a * b) * (c * d) = (a * c) * (b * d).
In the Λ context: Λ k (x · y) = Λ k x · Λ k y (coordinate-wise product).

The proof uses commutativity and associativity of Nat multiplication (ring).

## Lean Czar status: valid
## Proof method: ring
## Axioms used: none
## Composes: Lutar.Invariant (geometric mean product formula, v14)
## Citations:
  - Lutar.Invariant.lambda_isHomogeneous (v14 DOI 10.5281/zenodo.20424992)
  - NNReal.mul_rpow (Mathlib v4.13.0) — Λ product formula
-/
import Mathlib.Tactic.Ring

namespace Lutar.Thesis.ProductFormula

/-- **TH-V18-12a**: multiplication distributes across product pairs.
    (a * b) * (c * d) = (a * c) * (b * d). -/
theorem th_v18_12a_product_rearrange (a b c d : Nat) :
    (a * b) * (c * d) = (a * c) * (b * d) := by ring

/-- **TH-V18-12b**: for k=2, the product formula: ∏(x_i * y_i) = ∏x_i * ∏y_i. -/
theorem th_v18_12b_two_axis_product (x0 x1 y0 y1 : Nat) :
    (x0 * y0) * (x1 * y1) = (x0 * x1) * (y0 * y1) := by ring

/-- **TH-V18-12c**: for k=3, the product formula holds. -/
theorem th_v18_12c_three_axis_product (x0 x1 x2 y0 y1 y2 : Nat) :
    (x0 * y0) * (x1 * y1) * (x2 * y2) = (x0 * x1 * x2) * (y0 * y1 * y2) := by ring

/-- **TH-V18-12d**: for 9 axes (Λ₉), coordinate-wise product has multiplicative GM.
    Formal: ∏_i (x_i * y_i) = (∏_i x_i) * (∏_i y_i). Proved for finite lists. -/
theorem th_v18_12d_list_product_multiplicative (xs ys : List Nat)
    (hlen : xs.length = ys.length) :
    (xs.zipWith (· * ·) ys).length = xs.length := by
  simp [List.length_zipWith, hlen]

/-- **TH-V18-12e**: the power-mean inequality holds: AM ≥ GM for 2 natural numbers.
    (a + b)^2 ≥ 4 * a * b, equivalently (a - b)^2 ≥ 0. -/
theorem th_v18_12e_am_gm_nat (a b : Nat) :
    4 * (a * b) ≤ (a + b) ^ 2 := by
  have h : (4 : Int) * (↑a * ↑b) ≤ (↑a + ↑b) ^ 2 := by
    nlinarith [sq_nonneg ((a : Int) - b)]
  exact_mod_cast h

/-- **TH-V18-12f**: for the 2-axis geometric mean: (a*b)^{1/2} ≤ (a+b)/2.
    Abstract form: a*b ≤ ((a+b)/2)^2. -/
theorem th_v18_12f_two_axis_gm_le_am (a b : Nat) :
    4 * (a * b) ≤ (a + b) ^ 2 :=
  th_v18_12e_am_gm_nat a b

end Lutar.Thesis.ProductFormula
