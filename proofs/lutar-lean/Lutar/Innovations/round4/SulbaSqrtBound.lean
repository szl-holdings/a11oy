-- Lutar/Innovations/round4/SulbaSqrtBound.lean
-- F-08: SULBA-SQRT-RATIONAL-BOUND
-- Source: Baudhayana Sulba Sutra, ~800 BCE
-- Academic: MacTutor History of Mathematics, St Andrews — Sulba Sutras;
--           Datta, The Science of the Sulba (University of Calcutta, 1932).
-- Approximation: sqrt(2) ≈ 1 + 1/3 + 1/(3*4) - 1/(3*4*34) = 577/408
-- (577/408)^2 = 332929/166464; 2 = 332928/166464; error^2 = 1/166464^2.
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.SulbaSqrtBound

/-- The Sulba Sutra approximation to √2. -/
def sulbaSqrt2 : ℚ := 577 / 408

/-- The Sulba formula: 1 + 1/3 + 1/12 - 1/408 = 577/408. -/
theorem sulba_formula_eq : (1 : ℚ) + 1/3 + 1/(3*4) - 1/(3*4*34) = sulbaSqrt2 := by
  decide

/-- The Sulba approximation is positive. -/
theorem sulba_positive : 0 < sulbaSqrt2 := by decide

/-- (577/408)² = 332929/166464 — exact rational computation. -/
theorem sulba_square_exact : sulbaSqrt2 ^ 2 = 332929 / 166464 := by decide

/-- The Sulba approximation squared slightly exceeds 2 (it's an overestimate). -/
theorem sulba_overestimates_2 : sulbaSqrt2 ^ 2 > 2 := by decide

/-- The error in (577/408)² vs 2 is exactly 1/166464. -/
theorem sulba_square_error_exact : sulbaSqrt2 ^ 2 - 2 = 1 / 166464 := by decide

/-- The squared error is less than 1/100000 (usable precision bound). -/
theorem sulba_square_error_small : sulbaSqrt2 ^ 2 - 2 < 1 / 100000 := by decide

/-- The Sulba value is less than 3/2. -/
theorem sulba_less_than_threehalves : sulbaSqrt2 < 3 / 2 := by decide

/-- The Sulba value is greater than 1. -/
theorem sulba_greater_than_one : sulbaSqrt2 > 1 := by decide

end Lutar.Innovations.Round4.SulbaSqrtBound
