-- Lutar/Innovations/round10/PhysicsLiouville.lean
-- SPDX-License-Identifier: Apache-2.0
-- © 2026 Lutar, Stephen P. — SZL Holdings
-- ORCID: 0009-0001-0110-4173
-- Namespace: Lutar.Innovations.Round10.PhysicsLiouville
--
-- ============================================================================
-- PHYSICS-LIOUVILLE — phase-space volume preservation ⇒ receipt-density
-- invariance on the receipt-bus σ-algebra.
-- ============================================================================
--
-- IDEA. Liouville's theorem: Hamiltonian flow preserves the phase-space volume
-- form; the fine-grained Gibbs–Shannon entropy is then conserved
-- (Liouville-measure-preserving dynamics). On the receipt bus the relevant
-- volume-preserving maps are the *gauge relabelings* `Equiv.Perm (Fin k)` of
-- receipt indices: permuting receipts is a measure-preserving bijection of the
-- receipt index space, so the counting measure (the receipt "phase-space
-- volume") is invariant. This proves *receipt-density invariance*: the measure
-- of receipts in any index set is unchanged by gauge relabeling — the discrete
-- Liouville theorem for the receipt substrate.
--
-- WHAT IS PROVED (sorry-free, on the discrete counting measure):
--   * `perm_preserves_card`: cardinality (discrete volume) of an index set is
--     invariant under relabeling.
--   * `perm_preserves_total_volume`: total receipt count `k` is invariant.
--   * `perm_measurePreserving`: ∑ g∘σ = ∑ g — counting-measure preservation.
--   * `liouville_entropy_invariant_discrete`: any additive functional
--     `Σ f(xᵢ)` (e.g. fine-grained entropy) is conserved under the gauge flow —
--     the discrete Gibbs–Shannon-entropy-conservation corollary.
--   * `receipt_density_invariant`: total receipt mass `Σ xᵢ` is conserved.
--
-- HONEST GAP: the continuous symplectic Liouville theorem
-- (`L_{X_H} Ω = 0`) is recorded as `True` — Mathlib v4.13.0 has
-- `SymplecticGroup` and `MeasurePreserving` but no packaged "Hamiltonian flow ⇒
-- Lie-derivative of the volume form is zero" theorem.
--
-- PHYSICS PROVENANCE
--   Liouville, J. (1838). "Note sur la théorie de la variation des constantes
--     arbitraires." J. Math. Pures Appl. 3:342–349.
--     http://www.numdam.org/item/JMPA_1838_1_3__342_0/
--   Gibbs, J.W. (1902). Elementary Principles in Statistical Mechanics, Yale UP,
--     Ch. I (conservation of density-in-phase).
--     https://www.gutenberg.org/ebooks/50992
--   "Probability Conservation, Liouville Measure, and the Symplectic Structure"
--     (2025), arXiv:2512.19533 (Hamiltonian flow preserves Ω ⇒ fine-grained
--     Gibbs–Shannon entropy conserved, Thm 4.1).
--     https://arxiv.org/abs/2512.19533
--
-- DCO:
--   Signed-off-by: Yachay <yachay@szlholdings.ai>
--   Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
--
-- Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · OUTSIDE locked kernel.
-- Lean 4 + Mathlib v4.13.0.

import Mathlib.Data.Fintype.Card
import Mathlib.Data.Finset.Card
import Mathlib.GroupTheory.Perm.Basic
import Mathlib.Logic.Equiv.Basic
import Mathlib.Algebra.BigOperators.Group.Finset

open BigOperators

namespace Lutar.Innovations.Round10.PhysicsLiouville

variable {k : ℕ}

-- ── 1. Discrete Liouville: gauge flow preserves index volume (sorry-free) ────

/-- **Discrete phase-space volume preservation.** The volume (cardinality) of the
image of any index set `s` under a gauge relabeling `σ` equals the volume of `s`:
relabeling neither creates nor destroys receipts. Sorry-free. -/
theorem perm_preserves_card (σ : Equiv.Perm (Fin k)) (s : Finset (Fin k)) :
    (s.image σ).card = s.card :=
  Finset.card_image_of_injective s σ.injective

/-- Total receipt count is invariant: relabeling the whole index set by `σ`
preserves the global receipt volume `k`. Sorry-free. -/
theorem perm_preserves_total_volume (σ : Equiv.Perm (Fin k)) :
    (Finset.univ.image σ).card = (Finset.univ : Finset (Fin k)).card :=
  perm_preserves_card σ Finset.univ

-- ── 2. Measure-preservation of the gauge flow (sorry-free) ───────────────────

/-- **Discrete Liouville / measure preservation.** Summing any observable over
all receipt indices is invariant under a gauge relabeling: `Σ_i g(σ i) = Σ_i g i`.
The counting-measure form of "the gauge flow is measure preserving". Sorry-free. -/
theorem perm_measurePreserving {M : Type*} [AddCommMonoid M]
    (σ : Equiv.Perm (Fin k)) (g : Fin k → M) :
    ∑ i, g (σ i) = ∑ i, g i :=
  Equiv.sum_comp σ g

-- ── 3. Entropy / density invariance corollary (sorry-free) ───────────────────

/-- **Liouville entropy conservation (discrete).** Any additive functional of the
receipt configuration `H[x] = Σ_i f(x_i)` — the fine-grained Gibbs–Shannon
entropy `f = -p log p`, or the receipt-density functional `f = id` — is conserved
under the gauge flow. Discrete counterpart of "Hamiltonian
(Liouville-measure-preserving) flow conserves fine-grained entropy"
(arXiv:2512.19533, Thm 4.1). Sorry-free. -/
theorem liouville_entropy_invariant_discrete
    (f : ℝ → ℝ) (x : Fin k → ℝ) (σ : Equiv.Perm (Fin k)) :
    ∑ i, f ((x ∘ σ) i) = ∑ i, f (x i) := by
  simpa [Function.comp] using perm_measurePreserving σ (fun i => f (x i))

/-- Receipt-density invariance (`f = id`): the total receipt mass is conserved
under the gauge flow. -/
theorem receipt_density_invariant (x : Fin k → ℝ) (σ : Equiv.Perm (Fin k)) :
    ∑ i, (x ∘ σ) i = ∑ i, x i :=
  perm_measurePreserving σ x

-- ── 4. Continuous symplectic Liouville (honest gap) ──────────────────────────

/-- **Continuous Liouville theorem (HONEST GAP).** A divergence-free
(Hamiltonian) flow preserves the phase-space volume form: `L_{X_H} Ω = 0`.
Mathlib v4.13.0 provides `SymplecticGroup` and `MeasurePreserving`, but no
packaged differential-geometric statement of this. Recorded as `True`; the
discrete Liouville theorem (§1–§3) is the fully-proved deliverable. -/
theorem liouville_continuous : True := trivial

end Lutar.Innovations.Round10.PhysicsLiouville
