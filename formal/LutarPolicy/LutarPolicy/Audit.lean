/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
import LutarPolicy.Transition

namespace LutarPolicy

structure AuditEvent where
  requestId : String
  fromState : Lifecycle
  toState : Lifecycle
  traceId : String
  deriving DecidableEq, Repr

def emitsRequiredAuditEvent (event : AuditEvent) : Prop :=
  validTransition event.fromState event.toState = true ∧ event.requestId ≠ "" ∧ event.traceId ≠ ""

end LutarPolicy
