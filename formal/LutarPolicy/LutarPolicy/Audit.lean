/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Transition

namespace LutarPolicy

structure AuditEvent where
  principal : Principal
  artifactDigest : ArtifactDigest
  policyVersion : PolicyVersion
  decision : Decision
  deriving DecidableEq, Repr

def auditEvent (state : PolicyState) (request : Request) : AuditEvent :=
  {
    principal := request.principal
    artifactDigest := request.artifactDigest
    policyVersion := state.version
    decision := evaluate state request
  }

end LutarPolicy
