# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# szl_chain_of_title.rego — L6 CHAIN-OF-TITLE ATTESTATION POLICY.
#
# Input: an in-toto v1 Statement (https://in-toto.io/Statement/v1) carrying
# predicateType "https://szl.dev/chain-of-title/v1", as emitted by szl_attest.py
# and DSSE-signed via szl_dsse. Evaluate with OPA:
#
#     opa eval -i statement.json -d ops/szl_chain_of_title.rego \
#       'data.szl.attest.chain_of_title.verdict'
#
# The verdict is TRI-STATE and fails closed:
#
#   PASSED  — every rule below holds.
#   FAILED  — at least one rule does not hold (a tampered or under-provenanced
#             Statement is FAILED, never UNKNOWN).
#   UNKNOWN — reserved for the TRANSPARENCY strand, which this policy does not
#             and cannot evaluate offline: a Rekor inclusion proof is a live
#             network fact. When the caller requires transparency
#             (input.require_transparency == true) and no real inclusion proof
#             is present, the verdict is UNKNOWN — NEVER a fabricated PASSED.
#
# Doctrine v11 (binding): no fabricated PASSED / MEASURED / Rekor entry; Λ is
# Conjecture 1, never a theorem; the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
# c7c0ba17 is immutable and this policy only ATTESTS the pin, never extends it;
# provenance coverage must be fully disclosed at 1.0.
#
# Cited prior art (SZL claims none of it as its own):
#   in-toto Attestation Framework  — https://github.com/in-toto/attestation
#   SLSA v1.1 (Build L0-L3 + VSA)  — https://slsa.dev/spec/v1.1/
#   Sigstore / Rekor transparency  — https://docs.sigstore.dev/logging/overview/
#   DSSE                           — https://github.com/secure-systems-lab/dsse
#   sigstore/model-transparency    — https://github.com/sigstore/model-transparency
#
# This file is the AUTHORITATIVE statement of the policy. szl_attest.evaluate_policy
# mirrors it rule for rule in-process so the API verdict and an external OPA
# evaluation agree; tests/test_attest.py asserts the rule names stay in lockstep.

package szl.attest.chain_of_title

import future.keywords.if
import future.keywords.in

expected_predicate_type := "https://szl.dev/chain-of-title/v1"

expected_doctrine := "v11"

kernel_subject_name := "locked8_kernel"

# --------------------------------------------------------------------------- #
# Rule 1 — the predicate type is exactly the SZL chain-of-title type.
# --------------------------------------------------------------------------- #
predicate_type_matches if {
	input.predicateType == expected_predicate_type
}

# --------------------------------------------------------------------------- #
# Rule 2 — doctrine v11. An unversioned or drifted doctrine is not attestable.
# --------------------------------------------------------------------------- #
doctrine_is_v11 if {
	input.predicate.doctrine == expected_doctrine
}

# --------------------------------------------------------------------------- #
# Rule 3 — the locked-8 kernel was actually verified when the Statement was
# built (szl_attest re-checks the digest-verified formula registry). Must be
# boolean true; a truthy string or a missing field does not pass.
# --------------------------------------------------------------------------- #
kernel_verified if {
	input.predicate.provenance.kernel_verified == true
}

# --------------------------------------------------------------------------- #
# Rule 4 — every honesty invariant holds. These are the doctrine claims bound
# INTO the signed predicate; this is what makes the doctrine third-party
# checkable rather than a marketing line.
# --------------------------------------------------------------------------- #
honesty_invariants_all_true if {
	inv := input.predicate.honesty_invariants
	inv.no_fabricated_measured == true
	inv.lambda_is_conjecture_not_theorem == true
	inv.locked8_immutable == true
	inv.provenance_coverage == 1.0
}

# --------------------------------------------------------------------------- #
# Rule 5 — provenance coverage is exactly 1.0 (fully DISCLOSED: every field is
# a real read or an explicit null with its reason; nothing omitted).
# --------------------------------------------------------------------------- #
provenance_coverage_is_one if {
	input.predicate.provenance.provenance_coverage == 1.0
}

# --------------------------------------------------------------------------- #
# Rule 6 — the subject binds a NON-EMPTY locked-8 kernel gitCommit. An
# attestation with no bound kernel commit attests nothing.
# --------------------------------------------------------------------------- #
subject_binds_kernel_commit if {
	some s in input.subject
	s.name == kernel_subject_name
	commit := s.digest.gitCommit
	is_string(commit)
	trim_space(commit) != ""
}

# --------------------------------------------------------------------------- #
# Aggregate — passed iff ALL SIX rules hold. Default false: fail closed.
# --------------------------------------------------------------------------- #
default passed := false

passed if {
	predicate_type_matches
	doctrine_is_v11
	kernel_verified
	honesty_invariants_all_true
	provenance_coverage_is_one
	subject_binds_kernel_commit
}

# Named failures, so a denial always says which rule broke rather than just "no".
failed_rules contains "predicate_type_matches" if not predicate_type_matches

failed_rules contains "doctrine_is_v11" if not doctrine_is_v11

failed_rules contains "kernel_verified" if not kernel_verified

failed_rules contains "honesty_invariants_all_true" if not honesty_invariants_all_true

failed_rules contains "provenance_coverage_is_one" if not provenance_coverage_is_one

failed_rules contains "subject_binds_kernel_commit" if not subject_binds_kernel_commit

# --------------------------------------------------------------------------- #
# Transparency strand — evaluated ONLY from evidence the caller supplies. A
# real Rekor inclusion proof plus a log index is the only thing that counts.
# There is deliberately no branch that infers inclusion from anything else.
# --------------------------------------------------------------------------- #
default transparency_recorded := false

transparency_recorded if {
	input.rekor.status == "RECORDED"
	input.rekor.inclusion_proof != null
	input.rekor.log_index != null
}

default transparency_required := false

transparency_required if {
	input.require_transparency == true
}

# --------------------------------------------------------------------------- #
# The tri-state verdict. Order matters: FAILED wins over UNKNOWN, so a tampered
# Statement can never hide behind an unreachable log.
# --------------------------------------------------------------------------- #
verdict := "FAILED" if {
	not passed
}

verdict := "UNKNOWN" if {
	passed
	transparency_required
	not transparency_recorded
}

verdict := "PASSED" if {
	passed
	not transparency_required
}

verdict := "PASSED" if {
	passed
	transparency_required
	transparency_recorded
}

# Honest scope string, so a policy-only PASSED is never read as a
# transparency-anchored one.
verdict_scope := "policy-only: chain-of-title rules hold; transparency strand not evaluated" if {
	verdict == "PASSED"
	not transparency_recorded
}

verdict_scope := "policy + transparency: rules hold and a real Rekor inclusion proof is present" if {
	verdict == "PASSED"
	transparency_recorded
}

verdict_scope := "transparency required but no real inclusion proof present — UNKNOWN, never a fabricated PASSED" if {
	verdict == "UNKNOWN"
}

verdict_scope := sprintf("failed policy rules: %v", [sort(failed_rules)]) if {
	verdict == "FAILED"
}
