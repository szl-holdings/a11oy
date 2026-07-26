/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Identity
import LutarPolicy.Environment
import LutarPolicy.Artifact
import LutarPolicy.Approval

namespace LutarPolicy

inductive ActionType where
  | artifactBuild
  | deployStaging
  | deployProduction
  | secretRotate
  | identityChange
  deriving DecidableEq, Repr

structure Request where
  principal : Principal
  action : ActionType
  artifactDigest : ArtifactDigest
  environment : Environment
  expiresAt : Nat
  approval : Option Approval
  provenance : ProvenanceResult
  rollbackTarget : Option ArtifactDigest
  deriving DecidableEq, Repr

end LutarPolicy
