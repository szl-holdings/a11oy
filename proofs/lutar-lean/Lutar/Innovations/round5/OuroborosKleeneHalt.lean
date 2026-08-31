-- Lutar/Innovations/round5/OuroborosKleeneHalt.lean
-- OUROBOROS-KLEENE-HALT: Least fixed point of monotone operator (Kleene)
-- Source: Kleene, J. Symbolic Logic 3(4):150-155, 1938
-- Doctrine: v11 LOCKED 749/14/163 | Innovations/round5/ outside locked kernel
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

import Mathlib.Order.Fixedpoint

namespace Lutar.Innovations.Round5

/-- Kleene First Recursion Theorem: monotone operator on a complete lattice has a least fixed point.
    Source: Kleene (1938), J. Symbolic Logic 3(4):150-155. DOI: 10.2307/2267778
    Mathlib: OrderHom.lfp_eq, OrderHom.lfp_le -/
theorem ouroboros_kleene_least_fixed_point
    {alpha : Type} [CompleteLattice alpha]
    (Phi : alpha ->o alpha)
    : exists x : alpha, Phi x = x /\ forall y : alpha, Phi y = y -> x <= y := by
  exact ⟨OrderHom.lfp Phi, OrderHom.lfp_eq Phi, fun y hy => OrderHom.lfp_le Phi hy.le⟩

end Lutar.Innovations.Round5
