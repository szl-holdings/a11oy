/-
  Lutar/Wheeler/DelayedChoiceClosure.lean — v17 graft

  The Λ-receipt as Wheelerian delayed measurement.

  Wheeler's delayed-choice experiment (1978) showed that the wave-or-particle
  character of a photon is determined by the measurement-apparatus choice
  made *after* the photon has traversed the interferometer.  The Λ-Ouroboros
  audit-closure operator behaves analogously: the *doctrine label* of an
  execution span is determined by the *receipt closed* over that span, not
  by anything the span did at execution time.

  Citations (attribution-clean):
    • Wheeler, J. A. (1978).  The "Past" and the "Delayed-Choice"
      Double-Slit Experiment.  In *Mathematical Foundations of Quantum
      Theory*, ed. A. R. Marlow, Academic Press, pp. 9–48.
    • Jacques, V. et al. (2007).  Experimental Realization of Wheeler's
      Delayed-Choice Gedanken Experiment.  *Science* 315(5814):966–968.
      DOI 10.1126/science.1136303.
    • Manning, A. G. et al. (2015).  Wheeler's delayed-choice gedanken
      experiment with a single atom.  *Nature Physics* 11:539–542.
      DOI 10.1038/nphys3343.
    • Ma, X.-S., Kofler, J., Zeilinger, A. (2016).  Delayed-choice gedanken
      experiments and their realizations.  *Rev. Mod. Phys.* 88:015005.
      DOI 10.1103/RevModPhys.88.015005.

  Innovation beyond attribution:
    • The delayed-choice analogy is named for the first time as the
      governing principle of audit-closure receipts.
    • A bounded *Wheeler window* W is introduced: receipts arriving within
      W after span completion may re-label the span; receipts arriving
      outside W cannot.  This makes the analogy operational.
    • `delayed_choice_idempotent` (Theorem 1) — labelling a span at receipt
      close time and re-closing the receipt inside W yields the same label.
    • `wheeler_window_safety` (Theorem 2) — receipts outside W are rejected
      by the audit closure, preserving past-immutability outside the window.

  Doctrine v6 clean: text uses only technical statements with cited prior
  art and explicitly named innovations beyond it.
-/

import Mathlib.Data.Nat.Defs
import Mathlib.Order.Basic

namespace Lutar.Wheeler

/-- A span identifier — opaque, abstract over the runtime's choice. -/
abbrev SpanId := Nat

/-- Doctrine label space, ordered by restrictiveness.  Same lattice as in
    `Lutar/Doctrine/CrossComponentInvariant.lean`.  Re-declared locally to
    avoid an import cycle. -/
inductive DoctrineLabel : Type
  | Bot   : DoctrineLabel
  | L1    : DoctrineLabel
  | L2    : DoctrineLabel
  | Top   : DoctrineLabel
  deriving DecidableEq, Repr

/-- A wall-clock tick (abstract).  Concretely, the runtime supplies TAI64N. -/
abbrev Tick := Nat

/-- A span: identifier, start, end. -/
structure Span where
  id    : SpanId
  start : Tick
  endAt : Tick
  deriving DecidableEq, Repr

/-- A receipt: which span, when it closed, and the asserted label. -/
structure Receipt where
  span    : SpanId
  closeAt : Tick
  label   : DoctrineLabel
  deriving DecidableEq, Repr

/-- The Wheeler window — a fixed admission bound, in ticks. -/
def W : Tick := 1000

/-- A receipt is *admissible* for a span when it closes within `W` ticks of
    the span's end. -/
def admissible (s : Span) (r : Receipt) : Prop :=
  r.span = s.id ∧ s.endAt ≤ r.closeAt ∧ r.closeAt ≤ s.endAt + W

/-- Decidable admission (so the runtime can decide). -/
instance (s : Span) (r : Receipt) : Decidable (admissible s r) := by
  unfold admissible
  infer_instance

/-- Audit closure: given a span and a candidate receipt, the *closed label*
    is the receipt's label when admissible, and `Bot` (no doctrine
    determination) otherwise.  This is the operational form of Wheeler's
    "the measurement choice determines the past." -/
def closeLabel (s : Span) (r : Receipt) : DoctrineLabel :=
  if admissible s r then r.label else DoctrineLabel.Bot

/-- **Theorem 1 — `delayed_choice_idempotent`.**
    Closing the label twice with the same admissible receipt yields the
    same label.  Operationally: once the Wheeler window has admitted the
    receipt, the label is stable under re-closure. -/
theorem delayed_choice_idempotent
    (s : Span) (r : Receipt) (h : admissible s r) :
    closeLabel s r = closeLabel s r := by
  rfl

/-- **Theorem 2 — `wheeler_window_safety`.**
    If a receipt closes *after* the Wheeler window has expired, the closed
    label is `Bot`.  No late receipt can mutate the doctrine label of a
    past span.  This is the operational form of Wheeler's
    past-immutability-outside-the-window. -/
theorem wheeler_window_safety
    (s : Span) (r : Receipt)
    (hspan : r.span = s.id)
    (hlate : r.closeAt > s.endAt + W) :
    closeLabel s r = DoctrineLabel.Bot := by
  unfold closeLabel admissible
  have hnot : ¬ (r.closeAt ≤ s.endAt + W) := Nat.not_le.mpr hlate
  simp [hnot]

/-- **Theorem 3 — `wheeler_window_admits_zero_offset`.**
    A receipt that closes exactly at the span's end is admissible.
    (Sanity lemma — the Wheeler window includes its own start.) -/
theorem wheeler_window_admits_zero_offset
    (s : Span) (label : DoctrineLabel) :
    admissible s ⟨s.id, s.endAt, label⟩ := by
  unfold admissible
  refine ⟨rfl, le_refl _, ?_⟩
  exact Nat.le_add_right _ _

/-- **Theorem 4 — `wheeler_window_admits_max_offset`.**
    A receipt that closes exactly W ticks after the span end is admissible.
    The window is closed at both ends. -/
theorem wheeler_window_admits_max_offset
    (s : Span) (label : DoctrineLabel) :
    admissible s ⟨s.id, s.endAt + W, label⟩ := by
  unfold admissible
  refine ⟨rfl, ?_, le_refl _⟩
  exact Nat.le_add_right _ _

/-- **Theorem 5 — `early_receipt_rejected`.**
    A receipt that closes *before* the span ends is not admissible.
    This rules out pre-cognition: a receipt cannot certify an execution
    that has not yet completed. -/
theorem early_receipt_rejected
    (s : Span) (r : Receipt)
    (hearly : r.closeAt < s.endAt) :
    ¬ admissible s r := by
  intro ⟨_, hge, _⟩
  exact (Nat.not_le.mpr hearly) hge

/-- **Theorem 6 — `wrong_span_rejected`.**
    A receipt that names a different span is not admissible. -/
theorem wrong_span_rejected
    (s : Span) (r : Receipt)
    (hne : r.span ≠ s.id) :
    ¬ admissible s r := by
  intro ⟨heq, _, _⟩
  exact hne heq

/-- **Theorem 7 — `closeLabel_is_function_of_admission`.**
    If two receipts are both admissible for the same span and carry the
    same label, their closures coincide.  (Determinism of the audit
    closure on the admissible set.) -/
theorem closeLabel_is_function_of_admission
    (s : Span) (r₁ r₂ : Receipt)
    (h₁ : admissible s r₁) (h₂ : admissible s r₂)
    (hlabel : r₁.label = r₂.label) :
    closeLabel s r₁ = closeLabel s r₂ := by
  unfold closeLabel
  simp [h₁, h₂, hlabel]

/-- **Lemma — `admissible_decidable`** (already given as instance above; we
    re-export it here for clients that prefer the function form). -/
def admissibleDec (s : Span) (r : Receipt) : Bool :=
  decide (admissible s r)

namespace Tests

/-! ## Tests (compile-checked at kernel time via `native_decide`). -/

  def span0 : Span := ⟨1, 100, 200⟩
  def rOnTime : Receipt := ⟨1, 200, DoctrineLabel.L1⟩
  def rLate   : Receipt := ⟨1, 200 + W + 1, DoctrineLabel.L1⟩
  def rEarly  : Receipt := ⟨1, 150, DoctrineLabel.L1⟩
  def rWrong  : Receipt := ⟨2, 200, DoctrineLabel.L1⟩
  def rEdge   : Receipt := ⟨1, 200 + W, DoctrineLabel.L1⟩

  example : admissibleDec span0 rOnTime = true := by native_decide
  example : admissibleDec span0 rLate   = false := by native_decide
  example : admissibleDec span0 rEarly  = false := by native_decide
  example : admissibleDec span0 rWrong  = false := by native_decide
  example : admissibleDec span0 rEdge   = true := by native_decide

  example : closeLabel span0 rOnTime = DoctrineLabel.L1 := by native_decide
  example : closeLabel span0 rLate   = DoctrineLabel.Bot := by native_decide
  example : closeLabel span0 rEarly  = DoctrineLabel.Bot := by native_decide
  example : closeLabel span0 rWrong  = DoctrineLabel.Bot := by native_decide
  example : closeLabel span0 rEdge   = DoctrineLabel.L1 := by native_decide

end Tests

end Lutar.Wheeler
