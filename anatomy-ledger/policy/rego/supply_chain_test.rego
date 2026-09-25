# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
package anatomy.supplychain

import rego.v1

# Synthetic policy-projection fixture, not cryptographic verification evidence.
valid_input := {
	"statement": {
		"_type": "https://in-toto.io/Statement/v1",
		"subject": [{"name": "artifact.tar.gz", "digest": {"sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}],
		"predicateType": "https://slsa.dev/provenance/v1",
		"predicate": {
			"buildDefinition": {"buildType": "https://github.com/actions/attest-build-provenance"},
			"runDetails": {"builder": {"id": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml"}},
		},
	},
	"verification": {
		"verified": true,
		"source": "in-process-gh-attestation-verify",
		"repository": "szl-holdings/a11oy",
		"workflow": ".github/workflows/anatomy-ledger.yml",
		"ref": "refs/heads/main",
		"certificateIdentity": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml@refs/heads/main",
		"artifactSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
	},
}

test_trusted_projection_allows if {
	result := decision with input as valid_input
	result.outcome == "ALLOW"
}

test_unsigned_statement_reviews if {
	unsigned := object.union(valid_input, {"verification": {"verified": false}})
	result := decision with input as unsigned
	result.outcome == "REVIEW"
}

test_verified_flag_alone_reviews if {
	claimed := {"statement": valid_input.statement, "verification": {"verified": true}}
	result := decision with input as claimed
	result.outcome == "REVIEW"
	not result.verified
}

test_empty_input_blocks if {
	result := decision with input as {}
	result.outcome == "BLOCK"
}
