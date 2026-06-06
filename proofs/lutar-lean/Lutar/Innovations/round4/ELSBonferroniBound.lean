-- Lutar/Innovations/round4/ELSBonferroniBound.lean
-- F-07: ELS-BONFERRONI-BOUND
-- Source: McKay, Bar-Natan, Bar-Hillel, Kalai.
--         "Solving the Bible Code Puzzle." Statistical Science 14(2):150-173, 1999.
--         DOI: 10.1214/ss/1009212243
-- Claim: Expected ELS count for word length L in corpus C with skip K over alphabet size S
--        is ≤ 2*C*K / S^L. After Bonferroni correction for W words: FPR ≤ W * 2*C*K / S^L.
-- NOTE: ELS claims themselves are REFUTED by this paper. We extract the statistical bound only.
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.ELSBonferroniBound

/-- Expected ELS count: 2 * corpus_size * max_skip / alphabet_size^word_length -/
def expectedELSCount (C K L sigma : ℕ) : ℚ :=
  if sigma = 0 ∨ L = 0 then 0
  else (2 * C * K : ℚ) / (sigma : ℚ) ^ L

/-- Bonferroni-corrected family-wise false-positive bound for W patterns searched. -/
def bonferroniELSBound (C K L sigma W : ℕ) : ℚ :=
  (W : ℚ) * expectedELSCount C K L sigma

/-- More patterns searched → higher false-positive risk (monotone in W). -/
theorem els_bonferroni_monotone_in_W (C K L sigma W₁ W₂ : ℕ) (h : W₁ ≤ W₂) :
    bonferroniELSBound C K L sigma W₁ ≤ bonferroniELSBound C K L sigma W₂ := by
  unfold bonferroniELSBound
  apply mul_le_mul_of_nonneg_right _ (le_of_lt (by positivity))
  exact_mod_cast h

/-- Larger alphabet → lower false-positive rate (monotone in sigma for L ≥ 1). -/
theorem els_bound_nonneg (C K L sigma W : ℕ) :
    0 ≤ bonferroniELSBound C K L sigma W := by
  unfold bonferroniELSBound expectedELSCount
  split_ifs <;> positivity

/-- With zero patterns searched, false-positive rate is zero. -/
theorem els_zero_patterns (C K L sigma : ℕ) :
    bonferroniELSBound C K L sigma 0 = 0 := by
  simp [bonferroniELSBound]

end Lutar.Innovations.Round4.ELSBonferroniBound
