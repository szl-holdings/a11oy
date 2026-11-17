<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Runtime observation contract

The tools-layer adapter in scripts/szl_runtime_observation.py answers a bounded
question: do the required runtime responses, collected together for an explicit
target, consistently report the expected identity and operational state?

Its result has scope RUNTIME_OBSERVATION. OBSERVATIONS_PASS does not approve a
release, authenticate deployment bytes, verify a signature, establish hardware
provenance, or authorize execution. The existing release controller and its
independent evidence requirements retain those responsibilities.

## Inputs and decision

The caller supplies the HTTPS origin, repository, full source commit, and expected
signer fingerprint. Replay requires the same target independently of the snapshot.
There are no default production hosts, hardcoded release commits, optional registry
fallbacks, or status-only receipt inputs.

| Required observation | Check |
| --- | --- |
| Passive healthz, first and last | Service and capability readiness agree; source metadata matches the target; cached MCP inventory was fresh at capture |
| Process health, first and last | Exact signer booleans, observed public and loaded fingerprints, fresh self-test metadata, and stable runtime boot ID |
| Process liveness | Exact PROCESS_ALIVE status |
| Build information | Reported source commit matches the target and its origin is present |
| Storage v2 status | Fenced writable writer, active lease, canonical stores present and healthy, no active error or alert |
| Brain capabilities | Advertised capability rows and counts agree and report operational state without blockers |
| Deployment source v1 | Declared repository and commit match the target |

These checks consume the actual route contracts. The process-local signer may
correctly report execution_authorized=false and source_binding=UNKNOWN; neither
field is promoted into external authorization. The deployment-source contract
correctly reports STRUCTURAL_ONLY and has no publication_eligible or receipt_minted
requirement. Unknown build version or working-tree metadata is not fabricated.
Idle storage snapshot age and recovered historical errors are not active faults.

The report always includes these boundaries:

- release_approval: NOT_EVALUATED
- signature_verification: NOT_EVALUATED
- source_byte_binding: NOT_EVALUATED
- image_attestation: NOT_EVALUATED
- hardware_attestation: NOT_EVALUATED
- execution_authority: NONE

Every required response must be present with a UTC capture timestamp, exact URL,
HTTP status, JSON content type, byte limit, retained response bytes, and matching
SHA-256 digest. Duplicate JSON keys, nonfinite values, wrong JSON types, truncated
bodies, redirects, missing observations, and malformed contracts do not pass.
Integer 1 and string "true" do not count as boolean true.

The collection window and capture age are limited to 120 seconds, with at most
five seconds of clock skew. Signer cache and self-test age are capped at 60 seconds;
MCP cache age is capped at 30 seconds, even if a response claims a larger maximum.
Cache timestamps and reported ages must agree within five seconds. The timestamp
is recorded after receipt; this conservative bound includes both server clock
difference and response latency. A slower response produces a blocking
CACHE_TIMESTAMP_AGE_DISAGREEMENT finding instead of silently extending freshness.
Cache freshness is evaluated at capture, and a replay also checks the age of the captured responses. A historical
snapshot is retained evidence of an observation, not a continuing availability
claim; replaying it after its freshness window produces a nonzero exit.

## Collection and replay

Run from the repository root, replacing every example target value:

~~~sh
python scripts/szl_runtime_observation.py collect \
  --base-url https://runtime.example.invalid \
  --repository owner/repository \
  --source-revision SOURCE_COMMIT_40_HEX \
  --signer-fingerprint EXPECTED_FINGERPRINT_64_HEX \
  --evidence-dir audit/runtime-observations
~~~

The collector performs bounded HTTPS GETs without credentials or redirects. The
evidence directory must be controlled by the operator. It retains unsigned,
content-addressed snapshot and report JSON files using the existing release
guard's immutable_json helper. The stdout report names the snapshot file.

To observe an explicit MCP inventory refresh, add --active-mcp-probe. Both passive
health readings happen before that request. The optional request may update the
server's inventory cache; its response and following health read are reported
separately. They cannot erase a missing or expired passive observation, and the
tool never labels that refresh as a resolved persistent defect.

Replay the saved snapshot with an independently selected target:

~~~sh
python scripts/szl_runtime_observation.py evaluate \
  --base-url https://runtime.example.invalid \
  --repository owner/repository \
  --source-revision SOURCE_COMMIT_40_HEX \
  --signer-fingerprint EXPECTED_FINGERPRINT_64_HEX \
  --snapshot audit/runtime-observations/SNAPSHOT_FILE.json
~~~

| Exit | Verdict | Meaning |
| --- | --- | --- |
| 0 | OBSERVATIONS_PASS | Required observations satisfy this narrow contract |
| 1 | BLOCKED | Observed runtime state, target identity, or freshness does not satisfy the contract |
| 2 | ERROR | Missing input, malformed data, collection failure, or tool error prevents evaluation |

The snapshot_canonical_sha256 field hashes the canonical JSON value without a
trailing newline. The CLI's snapshot_file_sha256 hashes the exact file bytes,
including any newline. Each response's body_sha256 hashes the retained HTTP body
bytes. None of these hashes authenticates an author or substitutes for a signature.

Historical release-readiness files, blocker registries, proof labels, benchmark
labels, and attestation labels are not accepted as runtime snapshots or
release-admission records. Their independent verification is outside this tool.

## Offline verification

~~~sh
python -B -m unittest discover -s tests -p test_runtime_observation.py -v
~~~

The tests use explicit synthetic fixtures and a fake HTTP opener. They cover the
previous false-positive patterns, malformed nested values, byte and target
mismatches, freshness, restart continuity, collector ordering, bounded reads,
redirect refusal, and real subprocess exit codes. The existing offline evidence
reconciliation job in .github/workflows/tests.yml runs this suite without making
production requests.
