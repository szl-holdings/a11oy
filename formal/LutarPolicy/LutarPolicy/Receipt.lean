/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Policy

namespace LutarPolicy

structure AuthorizationReceipt where
  principal : Principal
  artifactDigest : ArtifactDigest
  environment : Environment
  policyVersion : PolicyVersion
  expiresAt : Nat
  deriving DecidableEq, Repr

def mintReceipt
    (state : PolicyState)
    (request : Request) : Option AuthorizationReceipt :=
  match evaluate state request with
  | .allow =>
      some {
        principal := request.principal
        artifactDigest := request.artifactDigest
        environment := request.environment
        policyVersion := state.version
        expiresAt := request.expiresAt
      }
  | .reject => none

end LutarPolicy
