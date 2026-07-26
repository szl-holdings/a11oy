/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

These theorems are kernel-checked but remain 0/12 PROVED publicly until the
four-theorem threshold and independent English-statement review are satisfied.
-/
import LutarPolicy.Policy

namespace LutarPolicy

/-- T1: no matching authorization rule implies the request is not executable. -/
theorem t1_default_denial (request : Request) (h : request.matchingRule = false) :
    ¬ executable (evaluate request) := by
  simp [evaluate, h, executable]

/-- T2: an evaluated rejection cannot be executable. -/
theorem t2_rejected_non_executable (request : Request) (h : evaluate request = .reject) :
    ¬ executable (evaluate request) := by
  simp [h, executable]

private def positiveArtifact : Artifact :=
  { digest := "sha256:positive", provenanceAccepted := true, rollbackAvailable := true }

private def positiveRequest : Request :=
  { principal := { name := "workload:release-agent" }
    action := .deployStaging
    artifact := positiveArtifact
    environment := .staging
    matchingRule := true
    validApproval := false }

private def negativeRequest : Request :=
  { positiveRequest with matchingRule := false }

/-- Positive non-vacuity witness: the supported domain contains an executable request. -/
example : executable (evaluate positiveRequest) := by native_decide

/-- Negative witness: the same request without a matching rule is rejected. -/
example : evaluate negativeRequest = .reject := by native_decide

/-- Assumption mutation: approval cannot compensate for a missing rule. -/
example : evaluate { negativeRequest with validApproval := true } = .reject := by native_decide

-- Critical-premise-removal control: this deliberately does not compile without the rule.
/--
error: tactic 'native_decide' evaluated that the proposition
  executable (evaluate LutarPolicy.negativeRequest)
is false
-/
#guard_msgs in
example : executable (evaluate negativeRequest) := by native_decide

end LutarPolicy
