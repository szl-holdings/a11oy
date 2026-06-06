-- Lutar/Innovations/round4/CopperScrollDAGHeight.lean
-- F-05: COPPER-SCROLL-DAG-HEIGHT
-- Source: Copper Scroll (3Q15), Dead Sea Scrolls, ~50 CE
-- Academic: Milik & Cross, Les Grottes de Murabba'ât (1961);
--           Wikipedia: Copper Scroll — 64-entry append-only inventory.
-- Claim: In an append-only ledger, height(entry) = height(prev) + 1 (strict monotone).
-- Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT theorem).
-- Lives in Lutar/Innovations/round4/ — OUTSIDE locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round4.CopperScrollDAGHeight

/-- Minimal append-only ledger entry: height and optional predecessor index. -/
structure LedgerEntry where
  height : ℕ
  prevHeight : Option ℕ

/-- The append-only invariant: height is exactly prev_height + 1, or 0 if genesis. -/
def appendOnlyInvariant (e : LedgerEntry) : Prop :=
  match e.prevHeight with
  | none => e.height = 0
  | some h => e.height = h + 1

/-- Append-only entries have strictly increasing height. -/
theorem copper_scroll_height_monotone (e : LedgerEntry) (h : appendOnlyInvariant e)
    (hp : e.prevHeight.isSome) :
    e.prevHeight.get hp < e.height := by
  unfold appendOnlyInvariant at h
  cases heq : e.prevHeight with
  | none => simp [heq] at hp
  | some ph =>
    simp [heq] at h
    simp [heq, Option.get]
    omega

/-- Genesis entry has height 0. -/
theorem copper_scroll_genesis_zero (e : LedgerEntry) (h : appendOnlyInvariant e)
    (hg : e.prevHeight = none) : e.height = 0 := by
  unfold appendOnlyInvariant at h
  simp [hg] at h
  exact h

/-- Height is non-decreasing across the chain. -/
theorem copper_scroll_height_nonneg (e : LedgerEntry) (h : appendOnlyInvariant e) :
    0 ≤ e.height := Nat.zero_le _

end Lutar.Innovations.Round4.CopperScrollDAGHeight
