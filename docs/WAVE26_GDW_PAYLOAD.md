<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Wave 26 — Λ-AttnRes + Governed Delta Workspace

Status: **MODELED**

This package operationalizes the Wave 26 payload as one bounded governance
service with a deployable operator surface. It does not claim a trained model,
an accuracy improvement, a throughput result, or a formal proof of
unconditional Λ uniqueness.

## Taxonomy and runtime

The package lives at `web/packages/a11oy-core/py/szl_gdw/` and spans the
repository's `governance`, `provenance`, and `services` layers:

- `models.py`, `math_core.py`, and `lambda_attnres.py` define the immutable and
  numerical contracts.
- `kernel_adapter.py` is the fail-closed governance boundary.
- `workspace.py` builds a candidate state copy and submits it to the kernel.
- `persistence.py` atomically stores state, idempotency records, DSSE envelopes,
  and the Khipu receipt chain in versioned SQLite.
- `api.py` registers bounded routes before the SPA catch-all.
- `telemetry.py` exposes process-local operational counters only.
- `static/` is the accessible operator UI served at `/gdw`.

The production database defaults to
`/data/a11oy/gdw/workspace.sqlite3`. If `/data` is not an attached mount, the
complete route contract remains visible but state operations return `503`
without a temporary fallback. `SZL_GDW_ALLOW_EPHEMERAL=1` exists for explicit
local development only.

## API contract

| Method | Route | Mutation | Receipt |
|---|---|---:|---|
| `GET` | `/api/a11oy/v1/gdw/status` | no | none |
| `POST` | `/api/a11oy/v1/gdw/sessions` | yes | `session.create` |
| `GET` | `/api/a11oy/v1/gdw/sessions/{session_id}` | no | none |
| `POST` | `/api/a11oy/v1/gdw/sessions/{session_id}/step` | yes | `kernel.transition` |
| `GET` | `/api/a11oy/v1/gdw/receipts/{receipt_id}` | no | none |
| `GET` | `/api/a11oy/v1/gdw/telemetry` | no | none |
| `POST` | `/api/a11oy/v1/gdw/aggregate` | compute only | none |

Request bodies are capped at 1 MiB. Tensor dimensions, evidence items, experts,
identifiers, and request text have separate lower bounds. Non-finite values,
ragged tensors, stale parents, changed idempotency payloads, missing storage,
and kernel exceptions fail closed.

## Corrected semantics

The operational implementation closes defects in the modeled source payload:

- shape comparison checks `(summary_count, query_dimension)`;
- parameter validation raises normal `ValueError` instances;
- λ equals the exact endpoint at initialization values `0` and `1`;
- Egyptian projection closes as exact `Fraction(1)`;
- certificates contain canonical rational rows and are stable across the
  supported dtype presentation;
- proposal and receipt identifiers derive from canonical SHA-256 content rather
  than process memory addresses;
- proposals bind the pre-step parent hash;
- state is frozen and copy-on-write;
- rejection and dry-run return the original state without step advancement;
- committed responses, state, replay keys, DSSE envelopes, and receipt links are
  stored in one transaction;
- GET routes never sign or mint a receipt.

## Truth boundary

| Claim | Current label | Basis |
|---|---|---|
| Exact λ endpoints and rational closure | VERIFIED in focused code/formal checks when CI passes | deterministic contract tests and Lean hooks |
| API/persistence/replay behavior | VERIFIED when executed checks pass | local and CI integration suite |
| Aggregator output | MODELED | deterministic tensor computation |
| Training-loss improvement | UNAVAILABLE | no preregistered run |
| Downstream model quality | UNAVAILABLE | no evaluation |
| Hardware, energy, latency, throughput | UNAVAILABLE | no measured runtime evidence |
| Λ uniqueness | Conjecture 1 | unchanged |
| Locked theorem set | 8 | unchanged |

The primary design lineage carried verbatim in API responses is:

- [Attention Residuals](https://arxiv.org/abs/2603.15031)
- [Delta attention design lineage](https://arxiv.org/abs/2510.26692)
- [Gated DeltaNet](https://arxiv.org/abs/2412.06464)

These are cited as inspiration and prior art, not as evidence that this
implementation reproduces their reported experimental results.
