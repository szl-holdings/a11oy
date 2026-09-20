package anatomy.supplychain

import rego.v1

statement := object.get(input, "statement", {})
verification := object.get(input, "verification", {})
predicate := object.get(statement, "predicate", {})
run_details := object.get(predicate, "runDetails", {})
builder := object.get(run_details, "builder", {})
build_definition := object.get(predicate, "buildDefinition", {})

default valid_statement_type := false
valid_statement_type if {
  object.get(statement, "_type", "") == "https://in-toto.io/Statement/v1"
}

default valid_subject_digest := false
valid_subject_digest if {
  some subject in object.get(statement, "subject", [])
  digest := object.get(object.get(subject, "digest", {}), "sha256", "")
  regex.match("^[a-fA-F0-9]{64}$", digest)
}

default is_slsa := false
is_slsa if {
  startswith(object.get(statement, "predicateType", ""), "https://slsa.dev/provenance/")
}

default verified := false
verified if {
  object.get(verification, "verified", false) == true
}

deny contains "statement type is not in-toto Statement/v1" if {
  not valid_statement_type
}

deny contains "no subject has a valid SHA-256 digest" if {
  not valid_subject_digest
}

deny contains "SLSA provenance is missing buildDefinition" if {
  is_slsa
  count(build_definition) == 0
}

deny contains "SLSA provenance is missing runDetails.builder.id" if {
  is_slsa
  object.get(builder, "id", "") == ""
}

review contains "predicate is not SLSA provenance" if {
  valid_statement_type
  not is_slsa
}

review contains "cryptographic verification has not been proven" if {
  valid_statement_type
  not verified
}

default outcome := "BLOCK"
outcome := "BLOCK" if { count(deny) > 0 }
outcome := "REVIEW" if { count(deny) == 0; count(review) > 0 }
outcome := "ALLOW" if { count(deny) == 0; count(review) == 0 }

decision := {
  "outcome": outcome,
  "deny": sort([message | some message in deny]),
  "review": sort([message | some message in review]),
  "verified": verified,
  "slsa": is_slsa,
}
