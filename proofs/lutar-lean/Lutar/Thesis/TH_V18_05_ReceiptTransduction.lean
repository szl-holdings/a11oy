/-
# TH-V18-05 — Receipt Transduction Invariance (composition of Lutar.Transduction)

Theorem: any encoder-decoder round-trip for receipts preserves the contentId
AND the body. This composes `Lutar.Transduction.ReceiptInvariant` theorems.

## Lean Czar status: valid
## Proof method: exact (re-export of compiled Lutar module)
## Axioms used: none
## Composes: Lutar.Transduction.ReceiptInvariant (compiled, 0 sorry)
## Citations:
  - Cerrón-Palomino (2013) DOI 10.3726/978-3-653-02485-2 — Andean khipu
  - Lutar.Transduction.ReceiptInvariant (v16 graft R2-G6)
-/
import Lutar.Transduction.ReceiptInvariant

namespace Lutar.Thesis.Transduction

open Lutar.Transduction.Receipt

/-- **TH-V18-05**: Round-trip-preserving encoder-decoder keeps contentId intact.
    Direct reuse of compiled Lutar.Transduction theorem. -/
theorem th_v18_05_receipt_transduction_invariant
    {β E : Type _}
    (f : Receipt β → E) (g : E → Receipt β)
    (h_round : ∀ r, g (f r) = r) :
    ∀ r : Receipt β, (g (f r)).contentId = r.contentId :=
  receipt_transduction_invariant f g h_round

/-- **TH-V18-05b**: Round-trip also preserves the body (stronger than contentId).
    Direct reuse of compiled Lutar.Transduction corollary. -/
theorem th_v18_05b_receipt_body_preserved
    {β E : Type _}
    (f : Receipt β → E) (g : E → Receipt β)
    (h_round : ∀ r, g (f r) = r) :
    ∀ r : Receipt β, (g (f r)).body = r.body :=
  receipt_round_trip_preserves_body f g h_round

/-- **TH-V18-05c**: identity encoder-decoder is a round-trip. -/
theorem th_v18_05c_identity_round_trip {β : Type _} :
    ∀ r : Receipt β, (id (id r)).contentId = r.contentId :=
  fun _ => rfl

/-- **TH-V18-05d**: contentId is a receipt invariant under any automorphism. -/
theorem th_v18_05d_contentId_is_invariant
    {β : Type _} (r : Receipt β) (f : Receipt β → Receipt β)
    (hf : f r = r) :
    (f r).contentId = r.contentId := by rw [hf]

end Lutar.Thesis.Transduction
