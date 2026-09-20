package anatomy.supplychain

import rego.v1

base := {
  "statement": {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{
      "name": "anatomy-ledger.tar.gz",
      "digest": {"sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    }],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
      "buildDefinition": {"buildType": "https://github.com/actions/attest-build-provenance"},
      "runDetails": {"builder": {"id": "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml"}},
    },
  },
  "verification": {"verified": true},
}

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
  result.verified == false
}
