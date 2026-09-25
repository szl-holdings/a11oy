# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
package anatomy.supplychain

import rego.v1

base := valid_input

test_malformed_digest_blocks if {
	bad := json.patch(base, [{"op": "replace", "path": "/statement/subject/0/digest/sha256", "value": "not-a-digest"}])
	result := decision with input as bad
	result.outcome == "BLOCK"
}

test_missing_builder_blocks if {
	bad := json.patch(base, [{"op": "replace", "path": "/statement/predicate/runDetails/builder/id", "value": ""}])
	result := decision with input as bad
	result.outcome == "BLOCK"
}

test_missing_build_definition_blocks if {
	bad := json.patch(base, [{"op": "replace", "path": "/statement/predicate/buildDefinition", "value": {}}])
	result := decision with input as bad
	result.outcome == "BLOCK"
}

test_non_slsa_reviews if {
	other := json.patch(base, [{"op": "replace", "path": "/statement/predicateType", "value": "https://example.com/not-slsa"}])
	result := decision with input as other
	result.outcome == "REVIEW"
}

test_envelope_presence_is_not_verification if {
	unsigned := object.union(base, {"verification": {"verified": false, "envelopePresent": true, "signatureCount": 1}})
	result := decision with input as unsigned
	result.outcome == "REVIEW"
	not result.verified
}

test_mixed_subjects_block if {
	bad := json.patch(base, [{"op": "add", "path": "/statement/subject/-", "value": {"name": "bad", "digest": {}}}])
	result := decision with input as bad
	result.outcome == "BLOCK"
}

test_nonobject_statement_blocks if {
	every value in [null, false, 4, "x", []] {
		result := decision with input as {"statement": value}
		result.outcome == "BLOCK"
	}
}

test_wrong_artifact_digest_reviews if {
	wrong := json.patch(base, [{"op": "replace", "path": "/verification/artifactSha256", "value": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}])
	result := decision with input as wrong
	result.outcome == "REVIEW"
	not result.verified
}

test_wrong_identity_reviews if {
	wrong := json.patch(base, [{"op": "replace", "path": "/verification/certificateIdentity", "value": "https://github.com/other/repo"}])
	result := decision with input as wrong
	result.outcome == "REVIEW"
}
