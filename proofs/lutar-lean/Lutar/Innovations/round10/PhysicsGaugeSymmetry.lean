-- Lutar/Innovations/round10/PhysicsGaugeSymmetry.lean
-- SPDX-License-Identifier: Apache-2.0
-- © 2026 Lutar, Stephen P. — SZL Holdings
-- ORCID: 0009-0001-0110-4173
-- Namespace: Lutar.Innovations.Round10.PhysicsGaugeSymmetry
--
-- ============================================================================
-- PHYSICS-GAUGE-A5 — "Hidden A5 from physical indistinguishability"
-- ============================================================================
-- The FLAGSHIP round10 contribution. It addresses the open question from
-- INTEGRATOR_FINAL (Cauchy_ND closure):
--
--   "Is there a natural physical reason for symmetry (A5) to be FORCED by the
--    structure of the receipt-bus?"
--
-- HONEST VERDICT (HONESTY OVER CHECKLIST):
--   Physics does NOT derive A5 from A1..A4 — that is mathematically impossible
--   (the counterexample Φ(x₁,x₂)=x₁^(2/3)·x₂^(1/3) satisfies A1..A4 and breaks
--   A5; see lutar-lean PR #148 and round9 CauchyNDClosure BLOCKER 2).
--
--   What physics DOES provide is a *principled justification* for ADOPTING A5:
--   if receipt indices are physical gauge labels (unobservable relabelings of
--   indistinguishable receipts), then the aggregator MUST be a gauge-invariant
--   observable, i.e. permutation-invariant. This turns A5 from an arbitrary
--   mathematical postulate into a *physical law* — the gauge principle — exactly
--   as charge conservation is "derived" from U(1) gauge invariance via Noether.
--
--   So: A5 is still an AXIOM, not a theorem of A1..A4. But it is now an axiom
--   with a one-line physics derivation from a single more-primitive principle
--   (gauge invariance / particle indistinguishability).
--
-- This file FORMALIZES that bridge:
--   1. `GaugeInvariant` = invariance of an aggregator under the gauge group
--      `Equiv.Perm (Fin k)` acting on receipt indices;
--   2. `gauge_iff_symmetric : GaugeInvariant Λ ↔ IsSymmetric Λ` — sorry-free;
--   3. `lutar_gauge_invariant` : the canonical equal-weight geometric mean Λ IS
--      gauge invariant, hence satisfies A5 — sorry-free;
--   4. `A5_not_forced_by_A1_A4` : the honest record that A5 is NOT a consequence
--      of A1..A4 (witness Φ), with an honest `sorry` on the multi-page witness
--      construction.
--
-- PHYSICS PROVENANCE
--   Gauge principle / indistinguishability ⇒ permutation invariance of
--   observables:
--     Weyl, H. (1929). "Elektron und Gravitation I." Z. Phys. 56:330–352.
--       DOI: https://doi.org/10.1007/BF01339504  (origin of the gauge principle)
--     Yang, C.N. & Mills, R.L. (1954). "Conservation of Isotopic Spin and
--       Isotopic Gauge Invariance." Phys. Rev. 96:191–195.
--       DOI: https://doi.org/10.1103/PhysRev.96.191
--     Messiah, A.M.L. & Greenberg, O.W. (1964). "Symmetrization Postulate and
--       Its Experimental Foundation." Phys. Rev. 136:B248–B267.
--       DOI: https://doi.org/10.1103/PhysRev.136.B248
--   Exchangeability = permutation-invariant joint law (probabilistic face of
--   indistinguishability):
--     de Finetti, B. (1937). "La prévision: ses lois logiques, ses sources
--       subjectives." Ann. Inst. H. Poincaré 7:1–68.
--       https://eudml.org/doc/79004
--     Hewitt, E. & Savage, L.J. (1955). "Symmetric measures on Cartesian
--       products." Trans. AMS 80:470–501.
--       DOI: https://doi.org/10.1090/S0002-9947-1955-0076206-8
--   Noether bridge (symmetry ⇒ conservation), the template imitated here:
--     Noether, E. (1918). "Invariante Variationsprobleme." Nachr. Ges. Wiss.
--       Göttingen, Math.-Phys. Kl. 1918:235–257.  https://eudml.org/doc/59024
--
-- DCO:
--   Signed-off-by: Yachay <yachay@szlholdings.ai>
--   Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
--
-- Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · OUTSIDE locked kernel.
-- Lean 4 + Mathlib v4.13.0.

import Mathlib.GroupTheory.Perm.Basic
import Mathlib.Logic.Equiv.Basic
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Data.NNReal.Basic
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Lutar.Axioms
import Lutar.Invariant

open NNReal BigOperators

namespace Lutar.Innovations.Round10.PhysicsGaugeSymmetry

variable {k : ℕ}

-- ── 1. The gauge group acting on receipt indices ─────────────────────────────

/-- **Gauge invariance of an aggregator.** A receipt aggregator `Λ` is gauge
invariant if relabelling the receipt indices by any `σ ∈ Equiv.Perm (Fin k)`
(the gauge group of index relabelings) leaves the aggregate unchanged.

Physically: receipt indices are *gauge labels* with no observable content — two
receipt streams differing only by an index permutation are physically
indistinguishable, so a physical observable (the trust aggregate) must be
invariant under the gauge group. -/
def GaugeInvariant (Λ : Lutar.Aggregator k) : Prop :=
  ∀ (σ : Equiv.Perm (Fin k)) (x : Lutar.Axes k), Λ (x ∘ σ) = Λ x

/-- **A5 — Permutation (symmetry) invariance** — the axiom proposed in
lutar-lean PR #148 to repair the A1..A4 uniqueness gap. Stated here so the
bridge can quantify over it without importing the (open) PR. -/
def IsSymmetric (Λ : Lutar.Aggregator k) : Prop :=
  ∀ (σ : Equiv.Perm (Fin k)) (x : Lutar.Axes k), Λ (x ∘ σ) = Λ x

-- ── 2. The gauge ⇔ A5 bridge (sorry-free) ────────────────────────────────────

/-- **THE BRIDGE.** Gauge invariance of the receipt aggregator is definitionally
equivalent to the proposed A5 symmetry axiom: adopting A5 is exactly demanding
that Λ be a gauge-invariant observable. This gauge-symmetry theorem is proven (Iff.rfl); note: Λ-uniqueness (Conjecture 1) remains unproven. -/
theorem gauge_iff_symmetric (Λ : Lutar.Aggregator k) :
    GaugeInvariant Λ ↔ IsSymmetric Λ := Iff.rfl

-- ── 3. The canonical Lutar invariant is gauge invariant (sorry-free) ─────────

/-- **The equal-weight geometric mean `Lutar.Λ` is gauge invariant.** The product
`∏ i, x i` is invariant under reindexing (`Equiv.prod_comp`), and the outer
`(·)^(1/k)` is applied to the same scalar, so the aggregate is
permutation-invariant. Hence the canonical Λ satisfies A5. -/
theorem lutar_gauge_invariant : GaugeInvariant (Lutar.Λ k) := by
  intro σ x
  by_cases hk : k = 0
  · subst hk; simp [Lutar.Λ]
  · have hkpos : 0 < k := Nat.pos_of_ne_zero hk
    rw [Lutar.Λ_def hkpos (x ∘ σ), Lutar.Λ_def hkpos x]
    congr 1
    -- ∏ i, (x ∘ σ) i = ∏ i, x (σ i) = ∏ i, x i, reindexing along σ.
    calc (Finset.univ : Finset (Fin k)).prod (x ∘ σ)
        = ∏ i, x (σ i) := by simp [Function.comp]
      _ = ∏ i, x i := Equiv.prod_comp σ x

/-- Corollary in A5 language: the canonical Λ satisfies the proposed A5 axiom. -/
theorem lutar_satisfies_A5 : IsSymmetric (Lutar.Λ k) :=
  (gauge_iff_symmetric (Lutar.Λ k)).mp lutar_gauge_invariant

-- ── 4. The honest non-derivability of A5 from A1..A4 ─────────────────────────

/-- **HONESTY RECORD — A5 is NOT a theorem of A1..A4.** The physics gives a
*reason to adopt* A5 (gauge invariance) but CANNOT turn A1..A4 into A5. The
standing witness is the asymmetric weighted geometric mean
Φ(x) = x₀^(2/3) · x₁^(1/3) on `k = 2`, which satisfies A1..A4 yet violates gauge
invariance (Φ(2,1) ≠ Φ(1,2)). We *state* the non-derivability as an existence
claim and mark the witness construction `sorry`: building Φ in NNReal and
discharging all four axioms is the multi-page functional-analysis exercise the
round9 siblings could not complete sorry-free (PR #148 / round9
CauchyNDClosure BLOCKER 2). The load-bearing results of THIS file are the
POSITIVE bridge (§2–§3), which are sorry-free; this is documentation of the
limit. -/
theorem A5_not_forced_by_A1_A4 :
    ∃ Λ : Lutar.Aggregator 2, Lutar.LutarAxioms Λ ∧ ¬ GaugeInvariant Λ := by
  -- Witness: Φ(x) = x 0 ^ (2/3 : ℝ) * x 1 ^ (1/3 : ℝ).
  -- A1 ✓ (exponents ≥ 0), A2 ✓ (2/3+1/3 = 1), A3 ✓ (c^(2/3)·c^(1/3)=c),
  -- A4 ✓ (Hardy–Littlewood–Pólya §2.18), ¬A5 ✓ (Φ(2,1) ≠ Φ(1,2)).
  sorry

end Lutar.Innovations.Round10.PhysicsGaugeSymmetry
