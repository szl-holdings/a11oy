/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
import LutarPolicy.Identity
import LutarPolicy.Artifact
import LutarPolicy.Environment
import LutarPolicy.Policy

namespace LutarPolicy

structure Receipt where
  decision : Decision
  principal : Principal
  artifact : Artifact
  environment : Environment
  expiresAt : Nat
  policyVersion : String
  deriving DecidableEq, Repr

def Receipt.authorized (receipt : Receipt) (now : Nat) : Prop :=
  receipt.decision = .allow ∧ now < receipt.expiresAt

end LutarPolicy
