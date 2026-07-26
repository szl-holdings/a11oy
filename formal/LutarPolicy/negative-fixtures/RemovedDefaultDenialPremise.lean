/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

EXPECTED COMPILE FAILURE: this fixture removes the no-matching-rule premise from T1.
-/

import LutarPolicy.Theorems

namespace LutarPolicy.NegativeFixtures

theorem removed_default_denial_premise_is_invalid
    (state : PolicyState)
    (request : Request) :
    evaluate state request = .reject := by
  rfl

end LutarPolicy.NegativeFixtures
