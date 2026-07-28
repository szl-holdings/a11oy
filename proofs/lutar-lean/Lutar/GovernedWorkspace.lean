/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import Mathlib.Data.Nat.Defs

/-!
# Governed workspace disposal hooks

The minimal state-selection law checked by the immutable kernel boundary:
rejection preserves the parent state and acceptance selects the candidate.
This is a structural hook, not a proof that an external policy is correct.
-/

namespace Lutar.GovernedWorkspace

inductive Decision where
  | accept
  | reject
  deriving DecidableEq, Repr

structure State where
  step : Nat
  digest : String
  deriving DecidableEq, Repr

def dispose (decision : Decision) (parent candidate : State) : State :=
  match decision with
  | .accept => candidate
  | .reject => parent

theorem reject_preserves_parent (parent candidate : State) :
    dispose .reject parent candidate = parent := by
  rfl

theorem accept_selects_candidate (parent candidate : State) :
    dispose .accept parent candidate = candidate := by
  rfl

theorem reject_preserves_step (parent candidate : State) :
    (dispose .reject parent candidate).step = parent.step := by
  rfl

end Lutar.GovernedWorkspace
