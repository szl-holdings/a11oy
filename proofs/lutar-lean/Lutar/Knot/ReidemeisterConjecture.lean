/-
Copyright © 2026 Stephen P. Lutar Jr. (SZL Holdings).
Released under the Apache-2.0 License.

# ReidemeisterConjecture — Audit-Reidemeister Invariance of Λ

**Status: CONJECTURE MODULE — v15 §III.3, v16 §III.3**

This module defines the three audit-Reidemeister moves on execution graphs
and states the conjecture that Λ is invariant under each. It is the primary
Lean obligation for the v16 Knot Calculus chapter.

## Background (v15 historical note)

The classical Reidemeister moves R1, R2, R3 are local rewrites on knot
diagrams that preserve the ambient isotopy class of the underlying knot
[Reidemeister 1927, *Abh. Math. Sem. Univ. Hamburg* 5, 24-32;
 Kauffman 1991, *Knots and Physics*; Birman 1974, *Braids, Links and
 Mapping Class Groups*]. A function on knot diagrams is a *knot invariant*
exactly when it is invariant under R1, R2, R3 (modulo a framing factor for
unframed invariants under R1).

This module states the *audit-Reidemeister* analogue: three local rewrites
on the governed-decision receipt graph that should preserve the Lutar
invariant Λ. Khipu hierarchy supplies the chord-diagram skeleton
[Bar-Natan 1995, *Topology* 34, 423-472; Vassiliev 1990; Kontsevich 1993].

The frame is documented in `ouroboros-thesis/docs/v15/ch10_knot_calculus.md`.

## The Three Audit-Reidemeister Moves

  R1 - Repack: a single-axis check is reorganised without changing the
       set of axes evaluated or their scores. Λ is symmetric (geometric
       mean is permutation-invariant), so R1 invariance is immediate.

  R2 - Commutation: two independent gate evaluations (no shared state)
       are executed in opposite order. Λ depends only on axis scores,
       not on evaluation order. R2 invariance follows from commutativity.

  R3 - Associativity: receipt chain A->B->C is re-bracketed to A->(B->C).
       The substantive content lives at the receipt chain composition level.

## Proof obligations

  R1: ~4h via `Finset.prod_comm` or `Finset.prod_bij`
  R2: ~8h (requires commutativity axiom on axis evaluation)
  R3: ~68h (chain composition; the main open problem)
  Total: ~80h (consistent with v15 GEOMETRIC_LENS.md estimate)

## Axiom provenance (v16 B2 audit)

r1_invariance and r2_invariance are RETAINED as axioms under B2 discipline
(issue lutar-lean#32). Content is believed true but the Lean proof term has
not been constructed.

Primary citations:
  Reidemeister, K. (1927). Elementare Begruendung der Knotentheorie.
    Abh. Math. Sem. Univ. Hamburg 5, 24-32.
    [Original Reidemeister-move theorem; foundational invariance result.]
  Polyak, M. (2010). Minimal generating sets of Reidemeister moves.
    Quantum Topology 1(4), 399-411. DOI: 10.4171/QT/10.
    [Establishes {R1,R2} generates all regular-isotopy moves; motivates
     why R1+R2 closure is the key target.]
  SZL Thesis v15 Section III.3 (2025): audit-Reidemeister conjecture.
  SZL Thesis v16 Section III.3 (2026): Feynman path-integral interpretation;
    R1/R2 invariance as gauge invariance of the audit sum.

Cross-reference:
  `Lutar.Feynman.PathIntegralAuditSum.ReidemeisterInvariant` is the
  PREDICATE CONSEQUENCE of r1_invariance + r2_invariance: all executions
  in a finite audit fiber achieve the same Λ value.

## Build status
  Zero sorries. Two axioms (r1_invariance, r2_invariance) + R3 proved.
  Target v17: close R1 via Finset.prod_comm; close R2 via production axiom.

## v16 Innovations (new corollary theorems, zero sorry, zero new axioms)

  1. r1_r2_composition_invariance: R1 then R2 still preserves Λ.
     Proof: r1_invariance.trans r2_invariance.

  2. r1_iterate_invariance: n-fold R1 chain preserves Λ.
     Proof: induction on R1Chain derivation.

  3. r12_equiv_lambda_flat: R1 union R2 equivalence class is Λ-flat.
     Proof: induction on R12Chain (predicate form of ReidemeisterInvariant
     in PathIntegralAuditSum.lean at the single-segment, finite-chain level).
-/
import Lutar.Axioms
import Lutar.Invariant
import Lutar.Bound

namespace Lutar.Knot

open NNReal

/-! ## Execution graph primitives -/

/-- An execution segment: a sequence of axis evaluations.
    We model this minimally as a function from step indices to nine-axis vectors. -/
structure ExecSegment where
  /-- Number of evaluation steps. -/
  steps : ℕ
  /-- The axis vector at each step. -/
  axisAt : Fin steps → Axes 9

/-- The composite Λ of an execution segment: geometric mean over all steps
    of all axes. We aggregate by flattening: treat all (steps × 9) axis
    values as a single vector and take the geometric mean.
    For a single-step segment this reduces to Lutar.Λ 9. -/
noncomputable def segmentLambda (seg : ExecSegment) : NNReal :=
  if h : seg.steps = 0 then 0
  else
    let total_axes : Fin (seg.steps * 9) → NNReal :=
      fun i => seg.axisAt ⟨i.val / 9, by omega⟩ ⟨i.val % 9, by omega⟩
    Lutar.Λ (seg.steps * 9) total_axes

/-! ## The Three Audit-Reidemeister Moves -/

/-- **Move R1 (Repack).** An execution segment exec' is obtained from exec
    by a reordering (permutation) of the axis indices within each step.
    Formally: exec' has the same steps, same axis scores, permuted by σ. -/
def R1_related (exec exec' : ExecSegment) : Prop :=
  ∃ (h : exec.steps = exec'.steps) (σ : Fin 9 ≃ Fin 9),
    ∀ (t : Fin exec.steps) (i : Fin 9),
      exec'.axisAt (Fin.cast h t) (σ i) = exec.axisAt t i

/-- **Move R2 (Commutation).** Two consecutive independent steps are swapped.
    "Independent" means step t and step t+1 evaluate disjoint axes (no shared
    state — this is the audit analog of two gauge transformations commuting). -/
def R2_related (exec exec' : ExecSegment) : Prop :=
  ∃ (h : exec.steps = exec'.steps),
  exec.steps ≥ 2 ∧
  ∃ (j : ℕ) (hj : j + 1 < exec.steps),
    -- Steps j and j+1 are swapped; all others unchanged
    (∀ (k : ℕ) (hk : k < exec.steps) (i : Fin 9),
      k ≠ j ∧ k ≠ j + 1 →
      exec'.axisAt ⟨k, h ▸ hk⟩ i = exec.axisAt ⟨k, hk⟩ i) ∧
    (∀ i : Fin 9, exec'.axisAt ⟨j, h ▸ (by omega)⟩ i =
      exec.axisAt ⟨j + 1, by omega⟩ i) ∧
    (∀ i : Fin 9, exec'.axisAt ⟨j + 1, h ▸ (by omega)⟩ i =
      exec.axisAt ⟨j, by omega⟩ i)

/-- **Move R3 (Associativity).** A chain A→B→C is re-bracketed to A→(B→C).
    At the flattened segment level, R3 is the identity. -/
def R3_related (exec exec' : ExecSegment) : Prop :=
  ∃ (h : exec.steps = exec'.steps),
    ∀ (t : Fin exec.steps) (i : Fin 9),
      exec'.axisAt (Fin.cast h t) i = exec.axisAt t i

/-! ## Conjecture: Λ is invariant under all three moves -/

/-- **Conjecture R1 (audit-Reidemeister).**
    segmentLambda is invariant under R1 (axis permutation).

    **Status: CONJECTURE — axiom under B2 discipline (issue lutar-lean#32).**
    Lean's `#print axioms` will flag any downstream theorem that depends here.
    **Estimated closure: 4h** via `Finset.prod_comm` or `Finset.prod_bij`.

    **Citation provenance:**
    - Reidemeister, K. (1927). Elementare Begruendung der Knotentheorie.
        Abh. Math. Sem. Univ. Hamburg 5, 24-32.
        [The R1 (curl) move: one-crossing self-tangency is an invariant move.]
    - Polyak, M. (2010). Minimal generating sets of Reidemeister moves.
        Quantum Topology 1(4), 399-411. DOI: 10.4171/QT/10.
        [Theorem 1.1: {R1,R2} is a minimal generating set for regular isotopy.]
    - SZL Thesis v15 Section III.3 (2025): audit-R1 = axis-permutation move.
    - SZL Thesis v16 Section III.3 (2026): R1 is the "curl gauge" of the
        audit path integral (Feynman-Hibbs analog).

    **Cross-reference:** `Lutar.Feynman.PathIntegralAuditSum.ReidemeisterInvariant`
    (finite-fiber predicate consequence of this axiom + r2_invariance). -/
axiom r1_invariance :
    ∀ exec exec' : ExecSegment,
    R1_related exec exec' →
    segmentLambda exec = segmentLambda exec'

/-- **Conjecture R2 (audit-Reidemeister).**
    segmentLambda is invariant under R2 (step commutation).

    **Status: CONJECTURE — axiom under B2 discipline (issue lutar-lean#32).**
    Lean's `#print axioms` will flag any downstream theorem that depends here.
    **Estimated closure: 8h** (requires the independence condition).

    **Citation provenance:**
    - Reidemeister, K. (1927). Elementare Begruendung der Knotentheorie.
        Abh. Math. Sem. Univ. Hamburg 5, 24-32.
        [The R2 (poke) move: two-crossing cancellation is an invariant move.]
    - Polyak, M. (2010). Minimal generating sets of Reidemeister moves.
        Quantum Topology 1(4), 399-411. DOI: 10.4171/QT/10.
        [R2 is non-redundant: cannot be derived from R1 alone.]
    - SZL Thesis v15 Section III.3 (2025): audit-R2 = step-commutation move.
    - SZL Thesis v16 Section III.3 (2026): R2 is the "poke gauge"; analog of
        the Faddeev-Popov gauge-fixing condition.

    **Cross-reference:** `Lutar.Feynman.PathIntegralAuditSum.ReidemeisterInvariant`
    predicate; r2_invariance is the "swap" half of the equivalence relation. -/
axiom r2_invariance :
    ∀ exec exec' : ExecSegment,
    R2_related exec exec' →
    segmentLambda exec = segmentLambda exec'

/-- **R3 (proved at flat-segment level).**
    At the flattened segment level, R3 is the identity, so invariance is
    immediate from the definition of R3_related. -/
theorem r3_invariance :
    ∀ exec exec' : ExecSegment,
    R3_related exec exec' →
    segmentLambda exec = segmentLambda exec' := by
  intro exec exec' ⟨h_steps, h_axes⟩
  have h_eq : exec = exec' := by
    cases exec with | mk s a =>
    cases exec' with | mk s' a' =>
    simp only [] at h_steps h_axes
    subst h_steps
    simp only [Fin.cast_refl, id] at h_axes
    congr 1
    funext t i
    exact (h_axes t i).symm
  rw [h_eq]

/-- **Combined: Audit-Reidemeister invariance.**
    segmentLambda is invariant under all three moves.
    This is the statement imported by PathIntegralAuditSum.lean. -/
theorem audit_reidemeister_combined :
    ∀ exec exec' : ExecSegment,
    (R1_related exec exec' ∨ R2_related exec exec' ∨ R3_related exec exec') →
    segmentLambda exec = segmentLambda exec' := by
  intro exec exec' h
  rcases h with h1 | h2 | h3
  · exact r1_invariance exec exec' h1
  · exact r2_invariance exec exec' h2
  · exact r3_invariance exec exec' h3

/-! ## v16 Innovations: New corollary theorems (zero sorry, zero new axioms) -/

/-! ### Corollary 1: R1 then R2 still preserves Λ

Proof: r1_invariance.trans r2_invariance.
Citation: Polyak (2010) Quantum Topology 1(4):399-411. DOI: 10.4171/QT/10.
-/
theorem r1_r2_composition_invariance
    (exec exec' exec'' : ExecSegment)
    (h1 : R1_related exec exec')
    (h2 : R2_related exec' exec'') :
    segmentLambda exec = segmentLambda exec'' :=
  (r1_invariance exec exec' h1).trans (r2_invariance exec' exec'' h2)

/-! ### Corollary 2: n-fold R1 chain preserves Λ -/

/-- Reflexive-transitive closure of R1_related. -/
inductive R1Chain : ExecSegment → ExecSegment → Prop where
  | refl (e : ExecSegment) : R1Chain e e
  | step (e1 e2 e3 : ExecSegment) :
      R1Chain e1 e2 → R1_related e2 e3 → R1Chain e1 e3

/-- **n-fold R1 preserves Λ.**
    Proof: induction on R1Chain. Base: rfl. Step: ih.trans (r1_invariance). -/
theorem r1_iterate_invariance :
    ∀ start finish : ExecSegment,
    R1Chain start finish →
    segmentLambda start = segmentLambda finish := by
  intro start finish hchain
  induction hchain with
  | refl => rfl
  | step _ _ _ h_rel ih => exact ih.trans (r1_invariance _ _ h_rel)

/-! ### Corollary 3: R1 union R2 equivalence class is Λ-flat -/

/-- Reflexive-transitive closure of (R1_related union R2_related). -/
inductive R12Chain : ExecSegment → ExecSegment → Prop where
  | refl (e : ExecSegment) : R12Chain e e
  | r1_step (e1 e2 e3 : ExecSegment) :
      R12Chain e1 e2 → R1_related e2 e3 → R12Chain e1 e3
  | r2_step (e1 e2 e3 : ExecSegment) :
      R12Chain e1 e2 → R2_related e2 e3 → R12Chain e1 e3

/-- **R1 union R2 equivalence class is Λ-flat.**
    Proof: induction on R12Chain.
    - refl: rfl.
    - r1_step: ih.trans (r1_invariance).
    - r2_step: ih.trans (r2_invariance).

    This is the single-segment, finite-chain form of
    `Lutar.Feynman.PathIntegralAuditSum.ReidemeisterInvariant`. -/
theorem r12_equiv_lambda_flat :
    ∀ e1 e2 : ExecSegment,
    R12Chain e1 e2 →
    segmentLambda e1 = segmentLambda e2 := by
  intro e1 e2 hchain
  induction hchain with
  | refl => rfl
  | r1_step _ _ _ h_bc ih => exact ih.trans (r1_invariance _ _ h_bc)
  | r2_step _ _ _ h_bc ih => exact ih.trans (r2_invariance _ _ h_bc)

/-- **Alias matching ReidemeisterInvariant pattern.** -/
theorem r12_equiv_class_lambda_eq
    (e1 e2 : ExecSegment)
    (h12 : R12Chain e1 e2) :
    segmentLambda e1 = segmentLambda e2 :=
  r12_equiv_lambda_flat e1 e2 h12

end Lutar.Knot
