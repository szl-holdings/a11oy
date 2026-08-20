/-
# TH-V18-01 — Lambda Monotonicity under DPI-Scaling

Theorem: for all k ≥ 1 and axis vectors x ≤ y (component-wise),
Λ k x ≤ Λ k y. This is A1 expressed directly on Lutar.Λ.

Proof: direct application of `Lutar.lambda_isMonotone` from `Lutar/Uniqueness.lean`.

Lean Czar status: valid
Proof method: exact (existing theorem)
Axioms used: none (fully proved)
-/
import Lutar.Invariant
import Lutar.Uniqueness
import Lutar.Axioms
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Algebra.BigOperators.Group.Finset

namespace Lutar.Thesis

open NNReal

/-- TH-V18-01: Λ k is monotone: axis-wise ≤ implies Λ ≤.
    Proof: direct application of `Lutar.lambda_isMonotone`. -/
theorem th_v18_01_lambda_monotone {k : ℕ} (hk : 0 < k)
    (x y : Fin k → NNReal) (hxy : ∀ i, x i ≤ y i) :
    Λ k x ≤ Λ k y :=
  Lutar.lambda_isMonotone hk x y hxy

end Lutar.Thesis
