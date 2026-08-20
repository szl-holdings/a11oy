/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Theorems

namespace LutarPolicy.Tests

theorem principal_mutation_breaks_authorization :
    evaluate positiveState
      { positiveRequest with principal := "agent:mutated" } = .reject := by
  decide

theorem artifact_mutation_breaks_authorization :
    evaluate positiveState
      { positiveRequest with artifactDigest := "sha256:mutated" } = .reject := by
  decide

end LutarPolicy.Tests
