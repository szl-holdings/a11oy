/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Identity
import LutarPolicy.Environment
import LutarPolicy.Artifact

namespace LutarPolicy

structure Approval where
  approver : Principal
  targetDigest : ArtifactDigest
  environment : Environment
  expiresAt : Nat
  deriving DecidableEq, Repr

end LutarPolicy
