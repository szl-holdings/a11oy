# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
package anatomy.supplychain

import rego.v1

# This is an internal projection. evaluate_supply_chain strips all untrusted
# verification fields and populates them only from the in-process gh verifier.
obj(value) := value if is_object(value)

else := {}

statement := obj(object.get(obj(input), "statement", {}))
verification := obj(object.get(obj(input), "verification", {}))
predicate := obj(object.get(statement, "predicate", {}))
run_details := obj(object.get(predicate, "runDetails", {}))
builder := obj(object.get(run_details, "builder", {}))
build_definition := obj(object.get(predicate, "buildDefinition", {}))

nonempty_string(value) if {
	is_string(value)
	value != ""
}

default valid_statement_type := false

valid_statement_type if {
	object.get(statement, "_type", "") == "https://in-toto.io/Statement/v1"
}

default valid_subject_digest := false

valid_subject_digest if {
	subjects := object.get(statement, "subject", [])
	is_array(subjects)
	count(subjects) > 0
	count(subjects) <= 1000
	every subject in subjects {
		is_object(subject)
		nonempty_string(object.get(subject, "name", ""))
		sha := object.get(obj(object.get(subject, "digest", {})), "sha256", "")
		is_string(sha)
		regex.match("^[a-fA-F0-9]{64}$", sha)
	}
}

default is_slsa := false

is_slsa if {
	object.get(statement, "predicateType", "") == "https://slsa.dev/provenance/v1"
}

default verified := false

verified if {
	object.get(verification, "verified", false) == true
	object.get(verification, "source", "") == "in-process-gh-attestation-verify"
	repository := object.get(verification, "repository", "")
	workflow := object.get(verification, "workflow", "")
	ref := object.get(verification, "ref", "")
	nonempty_string(repository)
	nonempty_string(workflow)
	nonempty_string(ref)
	object.get(verification, "certificateIdentity", "") == sprintf("https://github.com/%s/%s@%s", [repository, workflow, ref])
	subjects := object.get(statement, "subject", [])
	is_array(subjects)
	some subject in subjects
	artifact_digest := object.get(verification, "artifactSha256", "")
	is_string(artifact_digest)
	regex.match("^[a-fA-F0-9]{64}$", artifact_digest)
	object.get(obj(object.get(obj(subject), "digest", {})), "sha256", "") == artifact_digest
}

deny contains "statement type is not in-toto Statement/v1" if not valid_statement_type
deny contains "every subject must have a name and valid SHA-256 digest" if not valid_subject_digest
deny contains "predicateType must be a nonempty string" if {
	not nonempty_string(object.get(statement, "predicateType", ""))
}

deny contains "predicate must be an object" if {
	not is_object(object.get(statement, "predicate", null))
}

deny contains "SLSA provenance is missing buildDefinition.buildType" if {
	is_slsa
	not nonempty_string(object.get(build_definition, "buildType", ""))
}

deny contains "SLSA provenance is missing runDetails.builder.id" if {
	is_slsa
	not nonempty_string(object.get(builder, "id", ""))
}

review contains "predicate is not supported SLSA provenance/v1" if not is_slsa
review contains "cryptographic verification has not been proven" if not verified

default outcome := "BLOCK"

outcome := "BLOCK" if count(deny) > 0

outcome := "REVIEW" if {
	count(deny) == 0
	count(review) > 0
}

outcome := "ALLOW" if {
	count(deny) == 0
	count(review) == 0
	verified
}

decision := {
	"outcome": outcome,
	"deny": sort([message | some message in deny]),
	"review": sort([message | some message in review]),
	"verified": verified,
	"slsa": is_slsa,
}
