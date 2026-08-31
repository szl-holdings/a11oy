-- Lutar/Innovations/round4/PlimptonReciprocal.lean
-- F-01: PLIMPTON-RECIPROCAL-TRIPLE
-- Source: Plimpton 322, Babylonian clay tablet ~1800 BCE
-- Academic: Neugebauer & Sachs, Mathematical Cuneiform Texts (1945)
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.PlimptonReciprocal

/-- Every reciprocal pair (p, q) with p * q = 1 generates a Pythagorean identity.
    Babylonian tablet Plimpton 322 (~1800 BCE) used this to tabulate Pythagorean triples
    via sexagesimal regular fractions x with reciprocal 1/x.
    The triple: s = (p - q)/2, d = (p + q)/2 satisfies d² - s² = 1. -/
theorem plimpton_reciprocal_triple (p q : ℚ) (h : p * q = 1) :
    let s := (p - q) / 2
    let d := (p + q) / 2
    d ^ 2 - s ^ 2 = 1 := by
  simp only
  field_simp
  nlinarith [h]

/-- Corollary: the triple (s, 1, d) satisfies s² + 1 = d², i.e., a Pythagorean identity. -/
theorem plimpton_pythagorean_identity (p q : ℚ) (h : p * q = 1) :
    ((p - q) / 2) ^ 2 + 1 = ((p + q) / 2) ^ 2 := by
  field_simp
  nlinarith [h]

end Lutar.Innovations.Round4.PlimptonReciprocal
