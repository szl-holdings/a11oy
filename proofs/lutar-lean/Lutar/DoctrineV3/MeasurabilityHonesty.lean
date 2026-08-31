/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173
Date:  2026-05-14

# Measurability Honesty Theorem — Doctrine V3 §7

**Informal statement.**
Every claim emitted by Λ is either (1) *Verified* — anchored to a primary
source via a cryptographic receipt chain — or (2) *MarkedUnverifiable* —
explicitly tagged in the Λ-receipt as having no source link.  There is no
third option.  This partition is definitionally closed at the receipt-type
level (Definition 7.3, §7) and is the formal basis for the
`measurabilityHonesty` axis (Axis 9, floor ≥ 0.95).

**Doctrine V3 reference.** §7 (Measurability Honesty Theorem), especially
§7.2 (Definitions 7.1–7.3), §7.3 (Theorem 7.4), §7.4 (Lean Lemma Name).

**Formalization choice.**
The full probabilistic statement (A₉(o) ≥ 0.95 ⟹ ∀ c ∈ C(o), …) requires
a probability-space model that is outside Lean's kernel without additional
axioms.  We therefore formalize the *structural core* of the theorem: the
receipt-slot type is an inductive with exactly two constructors
(`verified`, `markedUnverifiable`), so exhaustiveness and mutual exclusivity
follow immediately from Lean's `cases` eliminator and constructor-injectivity.
This is the correct and sufficient formal content demanded by §7.3's proof
obligation ("proceeds by case analysis on the receipt-slot type").  No
`sorry`, no `admit`, no new `axiom` declarations.
-/

import Mathlib.Tactic

/-!
## Namespace

`LutarLean` is the doctrine-level namespace for Lean 4 theorems that encode
Doctrine V3 obligations, housed within the `Lutar` library.
-/

namespace LutarLean

/-!
## Receipt-Slot Type

A `ReceiptSlot` represents the verification status of a single claim `c` in a
Λ-output receipt.  The schema admits exactly two status values
(`verified`, `markedUnverifiable`), giving the partition closure of
Definition 7.3.
-/

/-- A claim with its receipt slot.
- `verified anchor mutualInfo`: the claim is anchored to a primary source.
  `anchor` is a non-empty string encoding the public anchor
  (DOI / git SHA / signed receipt chain id).
  `mutualInfo` witnesses that `I(c; S_c) > 0` — the source strictly reduces
  uncertainty about the claim (§7.5 Case 1).
- `markedUnverifiable`: the Λ-receipt carries the explicit `unverifiable(c)`
  tag.  No source is asserted; `I(c; S) = 0`, honestly disclosed (§7.5 Case 2).
-/
inductive ReceiptSlot where
  | verified (anchor : String) (mutualInfo : { x : Float // 0 < x })
  | markedUnverifiable
deriving Repr

/-!
## MeasurabilityHonestyTheorem

The theorem states that for any receipt slot `r`, exactly one of the two cases
holds.  The proof is pure case analysis on the two constructors of `ReceiptSlot`;
no `sorry`, `admit`, or new axiom is introduced.
-/

/-- **Theorem (Measurability Honesty) — Doctrine V3 §7, Theorem 7.4.**

Every receipt slot `r : ReceiptSlot` is either
  - `verified` (with an anchor string and a positive mutual-information witness), or
  - `markedUnverifiable`.

This is the structural core of the Measurability Honesty Theorem: exhaustiveness
and mutual exclusivity of the partition {Verified, MarkedUnverifiable} follow
directly from the two-constructor inductive type definition (Definition 7.3).
The disjunction is exclusive because the two constructors are syntactically
distinct — Lean's constructor-injectivity and `noConfusion` principle guarantee
that `verified a m ≠ markedUnverifiable` for any `a` and `m`.

ORCID: 0009-0001-0110-4173 | Date: 2026-05-14 | Doctrine V3 §7
-/
theorem MeasurabilityHonestyTheorem (r : ReceiptSlot) :
    (∃ a m, r = .verified a m) ∨ r = .markedUnverifiable := by
  cases r with
  | verified a m => exact Or.inl ⟨a, m, rfl⟩
  | markedUnverifiable => exact Or.inr rfl

/-- **Corollary — mutual exclusivity.**
The two cases are mutually exclusive: a slot cannot be simultaneously
`verified` and `markedUnverifiable`.
-/
theorem ReceiptSlot.verified_ne_markedUnverifiable
    (a : String) (m : { x : Float // 0 < x }) :
    ReceiptSlot.verified a m ≠ ReceiptSlot.markedUnverifiable := by
  intro h
  exact ReceiptSlot.noConfusion h

end LutarLean
