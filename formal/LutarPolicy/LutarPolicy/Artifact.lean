/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

namespace LutarPolicy

abbrev ArtifactDigest := String

structure ProvenanceResult where
  subjectDigest : ArtifactDigest
  accepted : Bool
  sourceRepository : String
  deriving DecidableEq, Repr

end LutarPolicy
