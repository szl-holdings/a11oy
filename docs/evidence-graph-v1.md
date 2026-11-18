# Canonical Evidence Graph v1

The Canonical Evidence Graph (CEG) provides content-addressed evidence edges and
bounded snapshots for a11oy. It indexes observer-supplied facts without turning
a health check into a readiness claim. The current runtime adapter is an
environment observation, not a persistent append-only ledger.

## Contract

Each edge has schema `szl.evidence-edge/v1` and is content addressed from its
canonical JSON payload. The resulting `receipt_id` is stable across process
restarts and changes when any payload field changes.

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

The response identifies whether the graph is bounded, the number of input and
included edges, dangling parent references, verdict counts, invariant counts,
the receipt head, and a graph digest. The current `receipt_head` is the last
edge in receipt-ID sort order, not a chronological ledger head. Parent
references are counted, not validated for temporal ordering or completeness;
a bounded snapshot may exclude a referenced parent. Querying filters the returned edge list
but preserves the digest of the unfiltered snapshot.

The runtime adapter reads only explicit identity variables:

- `A11OY_SOURCE_REVISION`, `GIT_COMMIT`, `SOURCE_REVISION`, or the
  explicit Space build identity `SZL_GIT_SHA`
- `A11OY_RUNTIME_REVISION` or `HF_REVISION`

If these variables are absent, the API returns
`state=UNAVAILABLE` with an empty graph. It does not guess from the process
path, hostname, or a mutable UI label.

Each GET timestamps a new environment observation. Repeated reads can therefore
have different edge IDs and graph digests even when source identity is
unchanged. These read paths do not append to storage or sign receipts.

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
