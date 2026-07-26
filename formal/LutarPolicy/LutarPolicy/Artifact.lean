/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
namespace LutarPolicy

structure Artifact where
  digest : String
  provenanceAccepted : Bool
  rollbackAvailable : Bool
  deriving DecidableEq, Repr

end LutarPolicy
