-- Lutar/Innovations/round9/VCGTruthfulness.lean
-- SPDX-License-Identifier: Apache-2.0
-- © 2026 Lutar, Stephen P. — SZL Holdings
-- ORCID: 0009-0001-0110-4173
--
-- VCG Dominant-Strategy Truthfulness — round9 Innovations graft (OUTSIDE locked kernel).
--
-- Classical theorem: Vickrey 1961, Clarke 1971, Groves 1973.
--   Vickrey, W. (1961). "Counterspeculation, Auctions, and Competitive Sealed Tenders."
--     Journal of Finance 16(1):8–37. DOI: https://doi.org/10.1111/j.1540-6261.1961.tb02789.x
--   Clarke, E.H. (1971). "Multipart Pricing of Public Goods."
--     Public Choice 11:17–33. DOI: https://doi.org/10.1007/BF01726210
--   Groves, T. (1973). "Incentives in Teams."
--     Econometrica 41(4):617–631. DOI: https://doi.org/10.2307/1914085
--   Nisan, Roughgarden, Tardos & Vazirani (eds., 2007). Algorithmic Game Theory,
--     Cambridge University Press, Ch. 9. ISBN: 9780521872829.
--   Roughgarden, T. (2016). Twenty Lectures on Algorithmic Game Theory, Ch. 7 (VCG).
--
-- Prior formal verification (Coq/Rocq, MathComp): Jouvelot, Sguerra, Arias,
--   "Towards a Generic Coq Proof of the Truthfulness of VCG Auctions for Search"
--   (Mines ParisTech, mech.v): https://www.cri.mines-paristech.fr/classement/doc/E-458.pdf
--
-- Lean 4 + Mathlib v4.13.0. Both previously proof-deferred obligations
-- (`vcgDominantStrategyTruth`, `vcgIndividualRationality`) are CLOSED here with
-- real Mathlib-backed proofs. No new axioms; no proof-deferred placeholders.
--
-- DCO:
--   Signed-off-by: Yachay <yachay@szlholdings.ai>
--   Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

import Mathlib.Data.Finset.Lattice
import Mathlib.Data.Finset.Max
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Order.Basic
import Mathlib.Algebra.Order.Sub.Defs
import Mathlib.Data.Real.Basic

open BigOperators Finset

namespace Lutar.Innovations.Round9.VCG

-- ── 1. Model ─────────────────────────────────────────────────────────────────

/-- Agent index type. -/
variable {N : Type*} [DecidableEq N] [Fintype N]

/-- Outcome type. Must be finite and inhabited. -/
variable {X : Type*} [DecidableEq X] [Fintype X] [Nonempty X]

/-- A valuation profile assigns to each agent a function `X → ℝ`. -/
abbrev ValProfile (N X : Type*) := N → X → ℝ

/-- Social welfare of outcome `x` under valuation profile `v`. -/
noncomputable def SW (v : ValProfile N X) (x : X) : ℝ :=
  ∑ i : N, v i x

/-- The welfare-maximising allocation rule `x*(v)`. -/
noncomputable def xStar (v : ValProfile N X) : X :=
  Classical.choose
    (Finset.exists_max_image Finset.univ (SW v) ⟨Classical.arbitrary X, mem_univ _⟩)

/-- `x*(v)` maximises social welfare. -/
lemma xStar_maximises (v : ValProfile N X) (x : X) : SW v x ≤ SW v (xStar v) := by
  have hspec :=
    Classical.choose_spec
      (Finset.exists_max_image Finset.univ (SW v) ⟨Classical.arbitrary X, mem_univ _⟩)
  exact hspec.2 x (mem_univ x)

/-- Social welfare restricted to agents other than `i`. -/
noncomputable def SW_others (v : ValProfile N X) (i : N) (x : X) : ℝ :=
  ∑ j ∈ Finset.univ.filter (· ≠ i), v j x

/-- Clarke pivot payment for agent `i`:
    `max_{x} SW_others(v,i,x) − SW_others(v,i,x*)`. -/
noncomputable def clarkeP (v : ValProfile N X) (i : N) : ℝ :=
  (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others v i)) -
    SW_others v i (xStar v)

/-- Agent `i`'s utility when its *true* valuation is `vi` but the *reported* full
    profile is `v` (so `v i` is `i`'s report). -/
noncomputable def utility (vi : X → ℝ) (v : ValProfile N X) (i : N) : ℝ :=
  vi (xStar v) - clarkeP v i

-- ── 2. Structural lemmas ─────────────────────────────────────────────────────

/-- Welfare splits into agent `i`'s term plus everyone else's term.
    `SW v x = v i x + SW_others v i x`. -/
lemma SW_split (v : ValProfile N X) (i : N) (x : X) :
    SW v x = v i x + SW_others v i x := by
  classical
  unfold SW SW_others
  -- `add_sum_erase`: `v i x + ∑_{j ∈ univ.erase i} v j x = ∑_{j} v j x`.
  have herase :
      v i x + (∑ j ∈ Finset.univ.erase i, v j x) = ∑ j : N, v j x :=
    Finset.add_sum_erase Finset.univ (fun j => v j x) (Finset.mem_univ i)
  -- `univ.filter (· ≠ i) = univ.erase i`.
  have hfilter : Finset.univ.filter (· ≠ i) = Finset.univ.erase i := by
    ext j; simp [Finset.mem_erase, Finset.mem_filter]
  rw [hfilter]
  linarith [herase]

/-- `SW_others` depends only on the reports of agents `j ≠ i`. If two profiles
    agree off `i`, their `SW_others i` agree pointwise. -/
lemma SW_others_congr {v w : ValProfile N X} {i : N}
    (h : ∀ j, j ≠ i → ∀ x, v j x = w j x) (x : X) :
    SW_others v i x = SW_others w i x := by
  classical
  unfold SW_others
  apply Finset.sum_congr rfl
  intro j hj
  have hji : j ≠ i := (Finset.mem_filter.mp hj).2
  exact h j hji x

/-- `sup'` of `SW_others` depends only on reports of agents `j ≠ i`. -/
lemma sup'_SW_others_congr {v w : ValProfile N X} {i : N}
    (h : ∀ j, j ≠ i → ∀ x, v j x = w j x) :
    (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others v i)) =
      (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others w i)) := by
  have hfun : SW_others v i = SW_others w i := by
    funext x; exact SW_others_congr h x
  rw [hfun]

-- ── 3. Main Theorem: Dominant-Strategy Truthfulness ──────────────────────────

/-- VCG Dominant-Strategy Truthfulness (Groves 1973).

    Fix agent `i` with true valuation `vi`, and fix the reports `v_others` of the
    other agents. For any report `vhat` of agent `i`, the truthful report weakly
    dominates: `utility vi vT i ≥ utility vi vD i`, where `vT` reports `vi` and
    `vD` reports `vhat` for agent `i` (both agreeing with `v_others` elsewhere). -/
theorem vcgDominantStrategyTruth
    (i : N)
    (vi : X → ℝ)                          -- true valuation of agent i
    (v_others : (j : N) → j ≠ i → X → ℝ)  -- fixed reports of the other agents
    (vhat : X → ℝ) :                      -- arbitrary report of agent i
    let vT : ValProfile N X := fun j x =>     -- truthful profile
      if h : j = i then vi x else v_others j h x
    let vD : ValProfile N X := fun j x =>     -- deviated profile
      if h : j = i then vhat x else v_others j h x
    utility vi vT i ≥ utility vi vD i := by
  intro vT vD
  classical
  -- vT and vD agree on every agent other than i.
  have hoff : ∀ j, j ≠ i → ∀ x, vT j x = vD j x := by
    intro j hj x
    simp only [vT, vD, dif_neg hj]
  -- The "others' max" constant is shared between the two profiles.
  have hsup : (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others vT i)) =
      (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others vD i)) :=
    sup'_SW_others_congr hoff
  -- vT reports vi for agent i, hence SW vT x = vi x + SW_others vT i x.
  have hvT_i : ∀ x, vT i x = vi x := by intro x; simp [vT]
  -- For agent i in vT, welfare splits with `vi`.
  have hsplit_vT : ∀ x, SW vT x = vi x + SW_others vT i x := by
    intro x
    have := SW_split vT i x
    rwa [hvT_i x] at this
  -- For vD, the i-term in the *utility* is still vi (the agent's TRUE value),
  -- and SW_others vD i = SW_others vT i (agree off i).
  have hSWothers_eq : ∀ x, SW_others vD i x = SW_others vT i x := by
    intro x
    exact (SW_others_congr hoff x).symm
  -- Define the key quantity: vi(x) + SW_others vT i x = SW vT x.
  -- Truthful utility:
  --   utility vi vT i = vi (xStar vT) - (sup - SW_others vT i (xStar vT))
  --                   = SW vT (xStar vT) - sup.
  have hUtilT : utility vi vT i =
      SW vT (xStar vT) -
        (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others vT i)) := by
    unfold utility clarkeP
    rw [hsplit_vT (xStar vT)]
    ring
  -- Deviated utility:
  --   utility vi vD i = vi (xStar vD) - (sup_vD - SW_others vD i (xStar vD)).
  -- Using sup_vD = sup_vT and SW_others vD i = SW_others vT i, and
  -- vi (xStar vD) + SW_others vT i (xStar vD) = SW vT (xStar vD):
  have hUtilD : utility vi vD i =
      SW vT (xStar vD) -
        (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others vT i)) := by
    unfold utility clarkeP
    rw [hsup, hSWothers_eq (xStar vD)]
    -- goal: vi (xStar vD) - (supT - SW_others vT i (xStar vD)) = SW vT (xStar vD) - supT
    have hsplitD : SW vT (xStar vD) = vi (xStar vD) + SW_others vT i (xStar vD) :=
      hsplit_vT (xStar vD)
    rw [hsplitD]; ring
  -- Now the inequality reduces to welfare maximality of x*(vT) under vT.
  rw [ge_iff_le, hUtilT, hUtilD]
  have hmax : SW vT (xStar vD) ≤ SW vT (xStar vT) := xStar_maximises vT (xStar vD)
  linarith

-- ── 4. Individual Rationality ────────────────────────────────────────────────

/-- Individual rationality: truthful utility is non-negative when the agent's
    valuation is everywhere non-negative (standard VCG IR). -/
theorem vcgIndividualRationality
    (i : N)
    (v : ValProfile N X)
    (hnn : ∀ x : X, v i x ≥ 0) :
    utility (v i) v i ≥ 0 := by
  classical
  -- utility (v i) v i = v i (x*) - (sup_others - SW_others v i (x*)).
  -- Suffices: sup_others ≤ SW v (x*), since SW v (x*) = v i (x*) + SW_others v i (x*).
  have hsplit_star : SW v (xStar v) = v i (xStar v) + SW_others v i (xStar v) :=
    SW_split v i (xStar v)
  -- Bound: every SW_others v i x ≤ SW v (x*).
  have hbound : ∀ x : X, SW_others v i x ≤ SW v (xStar v) := by
    intro x
    have h1 : SW_others v i x ≤ SW v x := by
      have := SW_split v i x      -- SW v x = v i x + SW_others v i x
      have hvi : 0 ≤ v i x := hnn x
      linarith
    have h2 : SW v x ≤ SW v (xStar v) := xStar_maximises v x
    linarith
  -- sup' of SW_others is ≤ SW v (x*).
  have hsup_le :
      (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others v i)) ≤
        SW v (xStar v) := by
    apply Finset.sup'_le
    intro b _
    exact hbound b
  -- Close. From hsup_le and hsplit_star:
  --   sup' ≤ SW v (x*) = v i (x*) + SW_others v i (x*),
  -- hence v i (x*) - (sup' - SW_others v i (x*)) ≥ 0.
  have hkey : (Finset.univ.sup' ⟨Classical.arbitrary X, mem_univ _⟩ (SW_others v i)) ≤
      v i (xStar v) + SW_others v i (xStar v) := by
    rw [← hsplit_star]; exact hsup_le
  unfold utility clarkeP
  rw [ge_iff_le]
  linarith [hkey]

end Lutar.Innovations.Round9.VCG
