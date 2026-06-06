/-
# R3-G3 — BM 13901 completing-the-square root

The Old Babylonian tablet BM 13901 (~1800 BCE, British Museum) records
the closed-form solution of `x² + b·x = c` as
`x = √(c + (b/2)²) − b/2`. We formalise its correctness over `ℝ`.

Sources:
  * Høyrup, J. (2002), *Lengths, Widths, Surfaces: A Portrait of Old
    Babylonian Algebra*, Springer-Verlag, ISBN 978-0387953038, ch. 1.
  * Robson, E. (2008), *Mathematics in Ancient Iraq*, Princeton UP,
    ISBN 978-0691091822, ch. 4.1.
  * Neugebauer, O. (1957), *The Exact Sciences in Antiquity*, Brown
    University Press, ch. II.

Runtime counterpart:
  `a11oy/web/packages/a11oy-core/src/thresholds/quadratic-solver.ts`.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Analysis.SpecialFunctions.Sqrt
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.FieldSimp

namespace Lutar.Thresholds

open Real

/-- BM 13901 closed-form root for `x² + b·x = c`. Requires `c + (b/2)² ≥ 0`
    for the square root to be real. -/
noncomputable def babylonianRoot (b c : ℝ) : ℝ :=
  Real.sqrt (c + (b / 2) ^ 2) - b / 2

/-- **R3-G3 theorem.** For `c + (b/2)² ≥ 0`, the closed-form root satisfies
    `x² + b·x = c`. Closes by expanding `(sqrt z)² = z` (when `z ≥ 0`)
    and `ring`. -/
theorem quadratic_root_correct
    (b c : ℝ) (h : 0 ≤ c + (b / 2) ^ 2) :
    let x := babylonianRoot b c
    x ^ 2 + b * x = c := by
  -- Expand the definition and use sq_sqrt.
  simp only [babylonianRoot]
  have hsq : Real.sqrt (c + (b / 2) ^ 2) ^ 2 = c + (b / 2) ^ 2 :=
    Real.sq_sqrt h
  -- Now the goal is a pure-real ring identity given that (sqrt _)² is c + (b/2)².
  -- Let s = sqrt(c + (b/2)²); we need (s - b/2)² + b·(s - b/2) = c.
  -- Expand: s² − s·b + (b/2)² + b·s − b²/2 = s² + (b/2)² − b²/2 = s² − b²/4 = c.
  set s : ℝ := Real.sqrt (c + (b / 2) ^ 2) with hs_def
  -- (s - b/2)^2 + b * (s - b/2) = s^2 - b^2/4
  have hgoal : (s - b / 2) ^ 2 + b * (s - b / 2) = s ^ 2 - (b / 2) ^ 2 := by
    ring
  rw [hgoal, hsq]
  ring

/-- Non-negativity: when `c ≥ 0`, the BM root is non-negative.
    `√(c + (b/2)²) ≥ √((b/2)²) = |b/2| ≥ b/2`, so `x = √(...) − b/2 ≥ 0`. -/
theorem babylonianRoot_nonneg
    (b c : ℝ) (hc : 0 ≤ c) :
    0 ≤ babylonianRoot b c := by
  unfold babylonianRoot
  have h1 : (b / 2) ^ 2 ≤ c + (b / 2) ^ 2 := by linarith
  have h2 : 0 ≤ (b / 2) ^ 2 := sq_nonneg _
  have h3 : 0 ≤ c + (b / 2) ^ 2 := by linarith
  have h4 : Real.sqrt ((b / 2) ^ 2) ≤ Real.sqrt (c + (b / 2) ^ 2) :=
    Real.sqrt_le_sqrt h1
  have h5 : Real.sqrt ((b / 2) ^ 2) = |b / 2| := by
    -- In Mathlib v4.13.0: Real.sqrt_sq_eq_abs applies directly to (b/2)^2 = |b/2|^2
    rw [← sq_abs (b / 2)]
    exact Real.sqrt_sq (abs_nonneg _)
  have h6 : b / 2 ≤ |b / 2| := le_abs_self _
  linarith

end Lutar.Thresholds
