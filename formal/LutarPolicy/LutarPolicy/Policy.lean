/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
import LutarPolicy.Action
import LutarPolicy.Identity
import LutarPolicy.Artifact
import LutarPolicy.Environment

namespace LutarPolicy

inductive Decision where
  | allow
  | reject
  deriving DecidableEq, Repr

structure Request where
  principal : Principal
  action : Action
  artifact : Artifact
  environment : Environment
  matchingRule : Bool
  validApproval : Bool
  deriving DecidableEq, Repr

def evaluate (request : Request) : Decision :=
  if request.matchingRule &&
      (!request.action.highRisk || request.validApproval) &&
      (request.environment != .production ||
        (request.artifact.provenanceAccepted && request.artifact.rollbackAvailable))
  then .allow
  else .reject

def executable : Decision → Prop
  | .allow => True
  | .reject => False

instance (decision : Decision) : Decidable (executable decision) :=
  match decision with
  | .allow => isTrue trivial
  | .reject => isFalse id

end LutarPolicy
