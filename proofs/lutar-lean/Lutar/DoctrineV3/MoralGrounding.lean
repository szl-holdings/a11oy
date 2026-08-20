/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173
Date:  2026-05-14

# Moral Grounding Theorem — Doctrine V3 §6

**Informal statement.**
For any output `o` produced by Λ, the moral safety predicate

    P_moral(o)  ⟺  ⋀_{h ∈ H} ¬ violates(o, h)

holds if and only if `o` does not violate any of the six enumerated harm
categories H = {h₁ (fabricated factual claim), h₂ (identity misattribution),
h₃ (unverifiable provenance), h₄ (suppressed uncertainty),
h₅ (adversarial instruction compliance), h₆ (scope boundary violation)}.

This section formalizes the finite conjunction decomposition of `P_moral`:
the predicate decomposes into a six-element conjunction, each component
computable by a decision procedure (§6.2), and the Lean proof closes by
exhaustive case analysis over the finite harm enumeration H.

**Doctrine V3 reference.** §6 (Moral Grounding Theorem), especially
§6.2 (Harm Category Enumeration H), §6.3 (Safety Predicate P_moral),
§6.4 (The Moral Grounding Theorem), §6.6 (Proof Sketch).

**Formalization choice.**
The full probabilistic statement (A₇(o) ≥ 0.95 ⟹ P_moral(o) with
probability ≥ 1 − ε) requires a probability-space model not available in
the kernel without additional axioms.  We formalize the *structural core*:
the harm enumeration H is an inductive type with exactly six constructors;
the safety predicate over H decomposes into a conjunction indexed by
`Fin 6` (equivalently, by the `HarmCategory` inductive); and the theorem
that ∀ h, ¬ violates(o, h) for a safe output `o` (one constructed to satisfy
all six non-violation predicates) follows by exhaustive case analysis over H.
This is the structural obligation demanded by §6.6: "the predicate P_moral
decomposes into a finite conjunction provable by case analysis."  No `sorry`,
`admit`, or new `axiom` declarations are introduced.
-/

import Mathlib.Tactic
import Mathlib.Data.Fintype.Basic

/-!
## Namespace
-/

namespace LutarLean

/-!
## Harm Category Enumeration H

The six harm categories from §6.2 are represented as an inductive type.
Each constructor corresponds exactly to one row of the §6.2 table.
-/

/-- The finite enumeration of harm categories H = {h₁, …, h₆} from §6.2. -/
inductive HarmCategory : Type where
  /-- h₁: fabricated factual claim (§6.2 row 1) -/
  | fabricatedFactualClaim
  /-- h₂: identity misattribution (§6.2 row 2) -/
  | identityMisattribution
  /-- h₃: unverifiable provenance (§6.2 row 3) -/
  | unverifiableProvenance
  /-- h₄: suppressed uncertainty (§6.2 row 4) -/
  | suppressedUncertainty
  /-- h₅: adversarial instruction compliance (§6.2 row 5) -/
  | adversarialInstructionCompliance
  /-- h₆: scope boundary violation (§6.2 row 6) -/
  | scopeBoundaryViolation
deriving Repr, DecidableEq

instance : Fintype HarmCategory where
  elems := {
    HarmCategory.fabricatedFactualClaim,
    HarmCategory.identityMisattribution,
    HarmCategory.unverifiableProvenance,
    HarmCategory.suppressedUncertainty,
    HarmCategory.adversarialInstructionCompliance,
    HarmCategory.scopeBoundaryViolation
  }
  complete := by
    intro h
    cases h <;> simp [Finset.mem_insert, Finset.mem_singleton]

/-!
## Output Type and Violation Predicate

We model outputs and violations in the minimal way needed to state and prove
the theorem without requiring external probabilistic infrastructure.
-/

/-- An output is modeled as a record carrying one Boolean violation flag per
harm category.  This is the computable representation of the §6.2 decision
procedures: `violatesFlag o h = true` iff the operational condition for `h`
is satisfied by `o`.  -/
structure Output where
  /-- The six violation flags, one per `HarmCategory`. -/
  violatesFlag : HarmCategory → Bool
-- Note: `deriving Repr` is intentionally omitted: function-typed fields
-- (`HarmCategory → Bool`) have no canonical `Repr` instance in Lean 4. This
-- is by design under the Doctrine V3 §6 formalization choice — we keep the
-- decision procedure as a function rather than enumerate it as a tuple, so
-- that adding harm categories does not perturb the proof. The structure is
-- still `DecidableEq`-extensible if needed via function extensionality.

/-- `violates o h` is the Prop-valued violation predicate, defined as the
truth of the Boolean flag in `o`. -/
def violates (o : Output) (h : HarmCategory) : Prop :=
  o.violatesFlag h = true

/-- The moral safety predicate: `o` is morally safe iff it does not violate
any of the six harm categories. -/
def P_moral (o : Output) : Prop :=
  ∀ h : HarmCategory, ¬ violates o h

/-!
## MoralGroundingTheorem

The theorem states that `P_moral` decomposes into the conjunction of six
non-violation clauses — one per harm category — and that for any output
whose Boolean violation flags are all `false`, the predicate holds by
exhaustive case analysis over the six constructors of `HarmCategory`.
-/

/-- **Theorem (Moral Grounding) — Doctrine V3 §6, Theorem (MoralGrounding).**

For any output `o : Output`, if all six violation flags are `false`
(i.e., the decision procedures for h₁–h₆ all return `false`),
then `P_moral(o)` holds.

The proof proceeds by exhaustive case analysis over `HarmCategory`
(the Lean `cases` / `decide` tactic discharges each of the six cases),
implementing the §6.6 proof obligation: "the predicate P_moral decomposes
into a finite conjunction provable by case analysis."

The 0.95 threshold and probabilistic dual-witness bound (§6.4) are not
encoded here because they require a probability-space axiom.  The structural
core — decomposition into a computable six-element conjunction + case analysis
— is sufficient as the Lean proof obligation for the doctrine.

ORCID: 0009-0001-0110-4173 | Date: 2026-05-14 | Doctrine V3 §6
-/
theorem MoralGroundingTheorem (o : Output)
    (hFlags : ∀ h : HarmCategory, o.violatesFlag h = false) :
    P_moral o := by
  intro h hViolates
  simp [violates] at hViolates
  have := hFlags h
  simp [this] at hViolates

/-- **Corollary — conjunction decomposition.**
`P_moral o` is equivalent to the explicit six-component conjunction
`¬ violates o h₁ ∧ … ∧ ¬ violates o h₆`.  This spells out the
"finite conjunction" of §6.3 in definitional form.
-/
theorem P_moral_iff_conjunction (o : Output) :
    P_moral o ↔
      ¬ violates o .fabricatedFactualClaim ∧
      ¬ violates o .identityMisattribution ∧
      ¬ violates o .unverifiableProvenance ∧
      ¬ violates o .suppressedUncertainty ∧
      ¬ violates o .adversarialInstructionCompliance ∧
      ¬ violates o .scopeBoundaryViolation := by
  constructor
  · intro h
    exact ⟨h _, h _, h _, h _, h _, h _⟩
  · intro ⟨h1, h2, h3, h4, h5, h6⟩ hc
    cases hc with
    | fabricatedFactualClaim => exact h1
    | identityMisattribution => exact h2
    | unverifiableProvenance => exact h3
    | suppressedUncertainty => exact h4
    | adversarialInstructionCompliance => exact h5
    | scopeBoundaryViolation => exact h6

end LutarLean
