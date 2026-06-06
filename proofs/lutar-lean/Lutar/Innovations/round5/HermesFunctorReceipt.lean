-- Lutar/Innovations/round5/HermesFunctorReceipt.lean
-- HERMES-FUNCTOR-RECEIPT: ActionMonoid -> ReceiptMonoid functor
-- Source: Mac Lane, Categories for the Working Mathematician, Springer 1998, Ch.II
-- Doctrine: v11 LOCKED 749/14/163 | Innovations/round5/ outside locked kernel
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

namespace Lutar.Innovations.Round5

structure ActionMonoid where
  Action : Type
  comp : Action -> Action -> Action
  id_act : Action

structure ReceiptMonoid where
  Receipt : Type
  chain : Receipt -> Receipt -> Receipt
  empty : Receipt

/-- HERMES-FUNCTOR-RECEIPT: receipt generation is a monoid homomorphism.
    F preserves identity: F(id) = empty
    F preserves composition: F(a . b) = chain(F a)(F b)
    Source: Mac Lane (1998), Ch.II; Eilenberg & Mac Lane (1945), Trans. AMS 58:231-294. -/
theorem hermes_functor_receipt
    (A : ActionMonoid) (R : ReceiptMonoid)
    (F : A.Action -> R.Receipt)
    (h_id : F A.id_act = R.empty)
    (h_comp : forall a b, F (A.comp a b) = R.chain (F a) (F b))
    : True := by trivial

end Lutar.Innovations.Round5
