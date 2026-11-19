# Canonical Evidence Graph v1

The Canonical Evidence Graph (CEG) provides content-addressed evidence edges and
bounded snapshots for a11oy. It indexes observer-supplied facts without turning
a health check into a readiness claim. The runtime adapter combines a captured
environment observation with a cached process-source witness. It does not
persist an append-only ledger.

## Contract

Each edge has schema `szl.evidence-edge/v1` and is content addressed from its
canonical JSON payload. The resulting `receipt_id` is stable for identical payloads and changes when
any payload field changes. A new process capture can have a new timestamp and
therefore a different content address.

Edges own immutable copies of their nested JSON values. Changing a caller's
input or a dictionary returned by `payload()` or `as_dict()` cannot change an
existing edge or break a child's reference to it. A changed observation must
construct a new edge and therefore receives a new content address.

Payloads accept JSON objects with string keys, arrays, strings, booleans, nulls,
integers, and finite numbers. Python tuples are normalized to JSON arrays.
Nonfinite numbers, cycles, unsupported types, and non-string object keys are
rejected before receipt creation. The existing sorted-key UTF-8 JSON encoding
is preserved for valid payloads; it is not an RFC 8785 implementation.

The payload carries:

- `subject`: the thing being observed, with a stable kind and id.
- `source_revision`: an explicit source revision when the observer has one.
- `artifact_sha256`: an optional lowercase SHA-256 digest.
- `runtime`: runtime identity such as a Space and revision.
- `evidence`: the observation type, route or URI, timestamp, and measured state.
- `authority`: an explicit boolean showing whether execution authority exists.
- `parents`: prior edge IDs, allowing a hash-linked DAG.
- `invariant_ids`: observer-supplied labels for checks it claims to have evaluated.
- `verdict`: the observer's label, one of `VERIFIED`, `OBSERVED`, `DEGRADED`, or
  `UNAVAILABLE`.
- `reason`: a human-readable explanation for the verdict.

A CEG edge never contains a secret, access token, private key, or credential
material. It also never infers authority from a hostname or a display label.

Content addressing detects payload changes; it does not authenticate the
observer or verify a signature. Neither an invariant label nor `VERIFIED`
supplies a Lean proof, freshness check, boot binding, coverage check, or
execution authority. The CEG does not evaluate those claims; an independent
verifier must do so before a consumer relies on them.

## Read-only API

The server registers read-only routes when the module is available:

- `GET /api/a11oy/v1/evidence/graph?limit=256`
- `GET /api/a11oy/v1/evidence/query?verdict=OBSERVED&invariant_id=freshness`
- `GET /api/a11oy/v1/evidence/openlineage` — static JobEvent metadata, not a run
- `GET /api/a11oy/v1/evidence/discovery` — bounded, non-authorizing gap projection

The discovery route never assigns model qualification from an observer label,
including `VERIFIED`, and never submits experiments or infers a current
model or runtime from a historical receipt. See [Proof-to-Discovery v1](PROOF_TO_DISCOVERY_V1.md)
for the separate modeled experiment-value calculation and missing admission gates.

Snapshots accept at most 1,024 input edges and return at most 256 unique edges.
Input overflow raises an error after consuming at most 1,025 items, including
the item that establishes overflow. Edges are sorted by content ID before the
output limit. Output truncation is explicit; it is not a complete-ledger claim.

`digest_sha256` hashes exactly `{"schema": GRAPH_SCHEMA, "edges": returned_edges}`
using the documented Python canonical encoding. Counts and the digest describe
the same returned records. A query filters the source snapshot before applying
its requested output limit. `source_digest_sha256`, `source_edge_count`,
`source_total_input_edges`, and `source_bounded` describe that source separately.
`matched_edge_count` is the number of matching unique source edges before the
selection limit; `selected_edge_count` is the number returned. Query clients
that need the unfiltered identity must use `source_digest_sha256`.

`receipt_head` remains for v1 compatibility and carries the explicit semantics
`LEXICOGRAPHIC_LAST_RECEIPT_ID`. It is not chronology. `ledger_head` is null.
`causal_heads` are IDs not referenced as parents by another returned edge;
their scope is only `RETURNED_EDGES`, not the complete graph. Parents omitted
by truncation or selection are distinguished from parents absent from the
known input. Their IDs accompany the counts. A bounded legacy source that
lacks this distinction yields unresolved references rather than asserting
they are missing. The graph does not validate acyclicity, temporal ordering,
authenticity, or a persistent append sequence.

The runtime adapter reads only explicit identity variables:

- `A11OY_SOURCE_REVISION`, `GIT_COMMIT`, `SOURCE_REVISION`, or the
  explicit Space build identity `SZL_GIT_SHA`
- `A11OY_RUNTIME_REVISION` or `HF_REVISION`

Identity values must be full lowercase Git SHA-1 or SHA-256 revisions. Conflicting
aliases or malformed values produce an explicit degraded result with no runtime
identity edge. If all variables are absent, runtime identity is unavailable;
historical receipt edges can still exist. No identity is inferred from paths,
hostnames, or mutable labels.

The environment is captured once when the routes are registered. Repeated GETs
retain the same environment observation, receipt ID and graph digest while the
cached witness is unchanged. `captured_at` records that process capture;
`retrieved_at` records the request time outside the hashed evidence.
The graph's legacy `observed_at` field has explicit
`PROCESS_ENVIRONMENT_CAPTURE_TIME` semantics in these routes.

### Cached runtime witness

When the execution observer exists, GET reads only
`observer.process_identity.snapshot()`. It never starts verification, invokes
admission, performs network work, signs a receipt, or writes storage. A report
must have the known method, source-copy scope, false authority/attestation
flags, valid revision and digest fields, no error, and a boot ID matching both
the identity object and its owning service. Invalid, blocked or unreadable
reports remain explicit. Internal exception text and arbitrary witness fields
are not exported.

A valid report becomes an `OBSERVED` runtime-source-witness edge. CEG does not
reverify its attestation. A parent link to the captured runtime edge expresses
only a matching source observation. Conflicting explicit source or runtime
identities yield `DEGRADED` with no matching parent link. Imported historical
training/evaluation records remain unbound, even if their names resemble the
running model.

`state_meaning=EVIDENCE_AVAILABILITY_ONLY` applies to the outer status.
It is not execution readiness. `runtime_identity_state`, `receipt_bundle`,
`provenance_witness` and `blockers` expose their separate availability.
Missing witness data cannot be used to infer authorization; the response's
`execution_authority` remains false.

### Temporal and source assessments

`edge_assessments` supplies derived metadata outside the content digest:
runtime observation, cached witness, historical artifact, or other observer
scope; source relation; and temporal-window status. A missing expiration is
`UNKNOWN`, including for historical receipts. A timezone-aware observation
plus an explicit later `valid_until` may be `WITHIN_DECLARED_WINDOW` or
`EXPIRED`; malformed, naive, future, or reversed times are `INVALID`.
A declared window is not authenticated freshness and never upgrades the edge
verdict, verifies a claim, or grants authority.

## Extension path

Future observers can append edges for a deployment attestation, route probe,
model evaluation, energy meter, or authority grant. They should preserve the
same source and runtime identities, name the invariants they evaluated, and
link to parent receipt IDs. A separate signer or provider must supply
cryptographic signatures and energy measurements; the CEG only indexes those
facts and reports missing evidence honestly.

## Bundled training and evaluation observations

The runtime also loads the reviewed `evidence_graph_receipts.json` release artifact
once when routes are registered. The offline importer checks exact raw receipt
bytes against an explicit SHA-256 and emits only allowlisted metadata. The bundle
ships through the existing Dockerfile-derived publication path; GET performs no
network access, signing, file writes, or catalog refresh.

The initial catalog contains two already-public artifact observations: the x402
v1 training receipt and x402 v2 differential evaluation. Each URI is pinned to an
immutable HF commit. Their classification and reported results remain observer
assertions; both edges have `verdict=OBSERVED`, `claims_verified=false`, no source
or runtime binding, no parent linkage, and no execution authority. In particular,
the v1 training receipt was assembled from Hub artifacts and discloses that its
completing boot's energy and wall time are unavailable. The importer does not
convert that receipt into verified execution or measured energy.

`receipt_bundle.state` reports catalog availability separately from runtime
identity. An invalid or unreadable bundle exposes an explicit unavailable reason;
a missing runtime identity remains unavailable even when historical receipts
exist. `receipt_bundle.signature_status` stays `UNSIGNED`. The live API's
`runtime_identity_state` and the imported edges' null source fields prevent old
receipts from being represented as evidence for the current runtime.

Use `GET /api/a11oy/v1/evidence/query?subject_kind=training` or
`GET /api/a11oy/v1/evidence/query?subject_kind=evaluation` to inspect these
observations. See [Offline receipt import](evidence-receipt-import.md) for the
bounded importer, rejected inputs, and the review/publication boundary. Private
receipts are excluded from this public release catalog.


## Evidence Inspector

The existing `/frontier` page includes a read-only Evidence Inspector that fetches
the graph route from the same origin. Its table, detail view, parent navigation,
filters and raw JSON all use the returned records. It displays the digest scope,
capture/retrieval times, source and witness identities, explicit blockers,
historical scope and missing/omitted references. It computes no replacement
health score, signature, digest or freshness claim in the browser.

Refresh failures clear the displayed result and show unavailable status. The
panel does not retain a previous successful result as current. Artifact links
use a narrow HTTPS host allowlist, DOM content is text-only, and no credentials
or mutation controls are introduced. Fixed JS and CSS asset routes are included
in the explicit Dockerfile source set and deployment coverage contract.

See [Frontier design evidence](frontier-evidence-design.md) for prior art,
the next experiments, and the boundary between this implemented slice and
proposed research.
