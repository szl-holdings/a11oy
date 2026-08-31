/-
SPDX-License-Identifier: Apache-2.0
Copyright 2026 Stephen P. Lutar Jr.
-/

namespace LutarPolicy.GDW

inductive SchedulerMode where
  | kdaLocal
  | lagunaHybrid
  | mlaGlobal
  deriving DecidableEq, Repr

structure State where
  step : Nat
  digest : String
  deriving DecidableEq, Repr

inductive Decision where
  | accept
  | reject
  | quarantine
  deriving DecidableEq, Repr

def transition (decision : Decision) (before : State) (nextDigest : String) : State :=
  match decision with
  | .accept => { step := before.step + 1, digest := nextDigest }
  | .reject => before
  | .quarantine => before

theorem scheduler_mode_is_valid (mode : SchedulerMode) :
    mode = .kdaLocal \/ mode = .lagunaHybrid \/ mode = .mlaGlobal := by
  cases mode <;> simp

theorem rejected_transition_preserves_state (before : State) (nextDigest : String) :
    transition .reject before nextDigest = before := by
  rfl

theorem quarantined_transition_preserves_state (before : State) (nextDigest : String) :
    transition .quarantine before nextDigest = before := by
  rfl

theorem accepted_transition_advances_step (before : State) (nextDigest : String) :
    (transition .accept before nextDigest).step = before.step + 1 := by
  rfl

end LutarPolicy.GDW
