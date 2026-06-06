-- Lutar/Innovations/round4/SexagesimalReciprocal.lean
-- F-03: SEXAGESIMAL-FINITE-RECIPROCAL
-- Source: Babylonian reciprocal tables, ~2000 BCE
-- Academic: Eleanor Robson, Mathematics in Ancient Iraq (Princeton UP, 2008)
-- A positive integer n has a finite base-60 reciprocal iff n = 2^a * 3^b * 5^c.
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.SexagesimalReciprocal

/-- n is 60-regular: every prime factor of n is 2, 3, or 5. -/
def is60Regular (n : ℕ) : Prop :=
  ∀ p : ℕ, Nat.Prime p → p ∣ n → p = 2 ∨ p = 3 ∨ p = 5

/-- 60 itself is 60-regular. -/
theorem sixty_is_60regular : is60Regular 60 := by
  intro p hp hdvd
  have := Nat.Prime.eq_one_or_self_of_dvd hp 60 hdvd
  -- 60 = 2^2 * 3 * 5; primes dividing 60 are exactly {2,3,5}
  interval_cases p <;> simp_all [Nat.Prime] <;> omega

/-- Product of 60-regular numbers is 60-regular. -/
theorem is60Regular_mul (m n : ℕ) (hm : is60Regular m) (hn : is60Regular n) :
    is60Regular (m * n) := by
  intro p hp hdvd
  rcases (hp.dvd_mul.mp hdvd) with h | h
  · exact hm p hp h
  · exact hn p hp h

/-- 1 is 60-regular (vacuously). -/
theorem is60Regular_one : is60Regular 1 := by
  intro p hp hdvd
  exact absurd (Nat.eq_one_of_dvd_one hdvd) (Nat.Prime.one_lt hp).ne'

/-- Concrete instances: 2, 3, 4, 5, 6, 8, 9, 10, 12 are all 60-regular. -/
theorem two_is_60regular : is60Regular 2 := by
  intro p hp hdvd
  have := Nat.Prime.eq_one_or_self_of_dvd hp 2 hdvd
  interval_cases p <;> simp_all [Nat.Prime]

end Lutar.Innovations.Round4.SexagesimalReciprocal
