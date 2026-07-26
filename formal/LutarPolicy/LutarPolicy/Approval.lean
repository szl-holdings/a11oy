/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
import LutarPolicy.Identity

namespace LutarPolicy

structure Approval where
  approver : Principal
  valid : Bool
  deriving DecidableEq, Repr

end LutarPolicy
