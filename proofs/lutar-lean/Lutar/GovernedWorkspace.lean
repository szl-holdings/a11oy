/-!
# Governed workspace disposal contracts

This module checks the structural reject/accept behavior modeled by the Python
reference kernel. It does not assert cryptographic signing or production
durability.
-/

namespace Lutar.GovernedWorkspace

structure State where
  digest : Nat
  step : Nat
  deriving DecidableEq

structure Proposal where
  parentDigest : Nat
  nextDigest : Nat

inductive Decision where
  | accept
  | reject
  deriving DecidableEq

def dispose
    (state : State)
    (proposal : Proposal)
    (policyPass invariantPass : Bool) : State × Decision :=
  if proposal.parentDigest = state.digest ∧ policyPass ∧ invariantPass then
    ({ digest := proposal.nextDigest, step := state.step + 1 }, .accept)
  else
    (state, .reject)

theorem stale_parent_rejected
    (state : State)
    (proposal : Proposal)
    (policyPass invariantPass : Bool)
    (stale : proposal.parentDigest ≠ state.digest) :
    (dispose state proposal policyPass invariantPass).2 = .reject := by
  simp [dispose, stale]

theorem policy_rejection_preserves_state
    (state : State)
    (proposal : Proposal)
    (invariantPass : Bool) :
    (dispose state proposal false invariantPass).1 = state := by
  simp [dispose]

theorem invariant_rejection_preserves_state
    (state : State)
    (proposal : Proposal)
    (policyPass : Bool) :
    (dispose state proposal policyPass false).1 = state := by
  simp [dispose]

theorem accepted_transition_advances_one_step
    (state : State)
    (proposal : Proposal)
    (parent : proposal.parentDigest = state.digest) :
    (dispose state proposal true true).1.step = state.step + 1 := by
  simp [dispose, parent]

end Lutar.GovernedWorkspace
