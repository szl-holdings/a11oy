package anatomy.supplychain

import rego.v1

valid_input := {
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

test_verified_slsa_allows if {
  result := decision with input as valid_input
  result.outcome == "ALLOW"
}

test_unsigned_statement_reviews if {
  unsigned := object.union(valid_input, {"verification": {"verified": false}})
  result := decision with input as unsigned
  result.outcome == "REVIEW"
}

test_empty_input_blocks if {
  result := decision with input as {}
  result.outcome == "BLOCK"
}
