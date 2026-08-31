/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Audit

namespace LutarPolicy

/--
T1, default denial: when no rule matches the exact principal, action, artifact digest,
and environment, the policy evaluator rejects the request.
-/
theorem T1_default_denial
    (state : PolicyState)
    (request : Request)
    (noMatch : ¬ HasMatchingRule state request) :
    evaluate state request = .reject := by
  unfold evaluate
  split <;> simp_all

/--
T1 execution consequence: a request with no matching authorization rule is not executable.
-/
theorem T1_default_denial_not_executable
    (state : PolicyState)
    (request : Request)
    (noMatch : ¬ HasMatchingRule state request) :
    ¬ Executable state request := by
  simp [Executable, T1_default_denial state request noMatch]

/--
T2, rejected means no authorized receipt: the receipt function cannot return a receipt
for a request rejected by the policy evaluator.
-/
theorem T2_rejected_cannot_mint_receipt
    (state : PolicyState)
    (request : Request)
    (rejected : evaluate state request = .reject) :
    mintReceipt state request = none := by
  simp [mintReceipt, rejected]

def witnessProvenance : ProvenanceResult :=
  {
    subjectDigest := "sha256:witness"
    accepted := true
    sourceRepository := "github.com/szl-holdings/a11oy"
  }

def positiveRequest : Request :=
  {
    principal := "agent:build-1"
    action := .artifactBuild
    artifactDigest := "sha256:witness"
    environment := .staging
    expiresAt := 10
    approval := none
    provenance := witnessProvenance
    rollbackTarget := none
  }

def positiveRule : Rule :=
  {
    principal := positiveRequest.principal
    action := positiveRequest.action
    artifactDigest := positiveRequest.artifactDigest
    environment := positiveRequest.environment
  }

def positiveState : PolicyState :=
  {
    now := 1
    version := "policy:witness"
    rules := [positiveRule]
    revokedPrincipals := []
    revokedVersions := []
  }

def negativeRequest : Request :=
  { positiveRequest with principal := "agent:not-authorized" }

theorem positive_authorization_witness :
    evaluate positiveState positiveRequest = .allow := by
  decide

theorem non_vacuity_authorized_action_exists :
    ∃ state request, Executable state request :=
  ⟨positiveState, positiveRequest, positive_authorization_witness⟩

theorem negative_default_denial_witness :
    evaluate positiveState negativeRequest = .reject := by
  decide

theorem negative_receipt_witness :
    mintReceipt positiveState negativeRequest = none := by
  decide

end LutarPolicy
