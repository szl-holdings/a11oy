/-
# R2-G6 — Receipt transduction invariant

For any encoder `f : Receipt → E` and decoder `g : E → Receipt` that form a
round-trip identity on `Receipt` (`g ∘ f = id`), `contentId` is preserved
along the round trip. The Andean khipu transcription tradition treats
content identity as preserved under round-trip translation
[Cerrón-Palomino 2013, *Las lenguas de los incas*, Peter Lang,
DOI 10.3726/978-3-653-02485-2].

Status: complete proof, zero `sorry`.
-/

namespace Lutar.Transduction.Receipt

/-- A receipt carries a stable content identifier. -/
structure Receipt (β : Type _) where
  contentId : String
  body      : β

/-- **R2-G6 — Receipt transduction invariant.**

    If `g ∘ f = id` (round-trip identity), then the contentId is preserved
    by the round trip for every input. Proof: rewrite by the round-trip
    identity. -/
theorem receipt_transduction_invariant
    {β E : Type _}
    (f : Receipt β → E) (g : E → Receipt β)
    (h_round : ∀ r, g (f r) = r) :
    ∀ r : Receipt β, (g (f r)).contentId = r.contentId := by
  intro r
  rw [h_round r]

/-- Corollary: body is also preserved (the round-trip identity is stronger
    than the contentId-only invariant). -/
theorem receipt_round_trip_preserves_body
    {β E : Type _}
    (f : Receipt β → E) (g : E → Receipt β)
    (h_round : ∀ r, g (f r) = r) :
    ∀ r : Receipt β, (g (f r)).body = r.body := by
  intro r
  rw [h_round r]

end Lutar.Transduction.Receipt
