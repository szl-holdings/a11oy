/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Receipt

namespace LutarPolicy

def Executable (state : PolicyState) (request : Request) : Prop :=
  evaluate state request = .allow

inductive Transition where
  | authorized (receipt : AuthorizationReceipt)
  | denied
  deriving DecidableEq, Repr

def transition (state : PolicyState) (request : Request) : Transition :=
  match mintReceipt state request with
  | some receipt => .authorized receipt
  | none => .denied

end LutarPolicy
