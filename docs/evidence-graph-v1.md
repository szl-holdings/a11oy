# Canonical Evidence Graph v1

The Canonical Evidence Graph (CEG) is a bounded, append-only evidence index for
a11oy. It connects independently observed facts without turning a health check
into a readiness claim.

## Contract

Each edge has schema `szl.evidence-edge/v1` and is content addressed from its
canonical JSON payload. The resulting `receipt_id` is stable across process
restarts and changes when any payload field changes.

The payload carries:

- `subject`: the thing being observed, with a stable kind and id.
- `source_revision`: an explicit source revision when the observer has one.
- `artifact_sha256`: an optional lowercase SHA-256 digest.
- `runtime`: runtime identity such as a Space and revision.
- `evidence`: the observation type, route or URI, timestamp, and measured state.
- `authority`: an explicit boolean showing whether execution authority exists.
- `parents`: prior edge IDs, allowing a hash-linked DAG.
- `invariant_ids`: named checks that the observer claims to have evaluated.
- `verdict`: one of `VERIFIED`, `OBSERVED`, `DEGRADED`, or `UNAVAILABLE`.
- `reason`: a human-readable explanation for the verdict.

A CEG edge never contains a secret, access token, private key, or credential
material. It also never infers authority from a hostname or a display label.

## Read-only API

The server registers two routes when the module is available:

- `GET /api/a11oy/v1/evidence/graph?limit=256`
- `GET /api/a11oy/v1/evidence/query?verdict=OBSERVED&invariant_id=freshness`

The response identifies whether the graph is bounded, the number of input and
included edges, dangling parent references, verdict counts, invariant counts,
the receipt head, and a graph digest. Querying filters the returned edge list
but preserves the digest of the unfiltered snapshot.

The runtime adapter reads only explicit identity variables:

- `A11OY_SOURCE_REVISION`, `GIT_COMMIT`, `SOURCE_REVISION`, or the
  explicit Space build identity `SZL_GIT_SHA`
- `A11OY_RUNTIME_REVISION` or `HF_REVISION`

If these variables are absent, the API returns
`state=UNAVAILABLE` with an empty graph. It does not guess from the process
path, hostname, or a mutable UI label.

## Extension path

Future observers can append edges for a deployment attestation, route probe,
model evaluation, energy meter, or authority grant. They should preserve the
same source and runtime identities, name the invariants they evaluated, and
link to parent receipt IDs. A separate signer or provider must supply
cryptographic signatures and energy measurements; the CEG only indexes those
facts and reports missing evidence honestly.
