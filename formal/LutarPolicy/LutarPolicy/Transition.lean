/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
namespace LutarPolicy

inductive Lifecycle where
  | proposed | schemaValidated | policyEvaluated | approvalRequired
  | authorized | rejected | executing | verified | committed | deployed
  | observed | closed | rolledBack
  deriving DecidableEq, Repr

def validTransition : Lifecycle → Lifecycle → Bool
  | .proposed, .schemaValidated => true
  | .proposed, .rejected => true
  | .schemaValidated, .policyEvaluated => true
  | .schemaValidated, .rejected => true
  | .policyEvaluated, .approvalRequired => true
  | .policyEvaluated, .authorized => true
  | .policyEvaluated, .rejected => true
  | .approvalRequired, .authorized => true
  | .approvalRequired, .rejected => true
  | .authorized, .executing => true
  | .authorized, .rejected => true
  | .executing, .verified => true
  | .executing, .rolledBack => true
  | .verified, .committed => true
  | .verified, .rolledBack => true
  | .committed, .deployed => true
  | .committed, .closed => true
  | .committed, .rolledBack => true
  | .deployed, .observed => true
  | .deployed, .rolledBack => true
  | .observed, .closed => true
  | .observed, .rolledBack => true
  | .rejected, .closed => true
  | .rolledBack, .closed => true
  | _, _ => false

end LutarPolicy
