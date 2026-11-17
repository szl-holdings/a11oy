<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# ORO evidence observation integration

Date: 2026-11-16. Scope: the canonical observation API and inspection page.
This is an implementation contract, not deployment qualification. Hosted state,
freshness, signature verification, and production readiness require their own
evidence. Rules: [AGENTS](../../AGENTS.md), [provenance](../../.claude/rules/provenance.md),
[honest status](../../.claude/rules/honest-status.md), and
[ADR-0001](../adr/ADR-0001-a11oy-state-store.md).

## Observation contract

`GET /api/a11oy/v1/oro/evidence` in
[`oro/evidence_api.py`](../../oro/evidence_api.py) supplies
`szl.oro-evidence-observation/v1` to
[`/oro/evidence`](../../oro/evidence_web/index.html). The API owns the observation
model; the page renders its source states, boundaries, and diagnostics without
deriving a separate readiness verdict.

Each request resolves the existing `app.state.szl_khipu_dag`. Its bounded read
runs in a threadpool through
[`project_source_snapshots`](../../oro/source_adapters.py) and
[`project_dag`](../../oro/evidence_dag.py). The HTTP inspector requires the
owner's passive evidence_window method; an owner exposing only the older
recent method is unavailable on this route. It requests at most 33 Wire F
nodes and projects at most 32. An omitted earlier parent remains an explicit
window boundary; no parent or cross-source causal edge is invented.

The managed window reader uses the existing space/sequence index and one
read-only SQLite transaction. It checks selected row lengths with the plain-column
[octet_length function](https://www.sqlite.org/lang_corefunc.html#octet_length)
before fetching JSON bodies and refuses a cumulative encoded window above 1 MiB.
Unsupported function availability or a non-UTF-8 inspection format yields an
unavailable inspection; neither changes storage admission or full-history reads.
The SQLite busy timeout is two seconds. It validates selected checksums, identities,
local continuity, and the retained head, without scanning earlier history.
Diagnostics state validation_scope BOUNDED_WINDOW_ONLY and history_validation
NOT_PERFORMED; the page states that limitation. Existing recent, full-history
validation, append, restoration, snapshot, and lease semantics remain intact.
This is a bound on the managed Khipu inspection, not a production latency or
throughput measurement.

Anatomy is a separate, allowlisted summary from
`szl_anatomy_brainloop.evidence_snapshot()`. This is the read-only v6 observation,
not the adapter's v7 modeled topology. It contributes no invented per-node
content hashes. Second Brain and Hatun remain `UNKNOWN` until their owners
supply admissible snapshots. No source retrieval POST runs during inspection.

| Observation | HTTP | Meaning |
| --- | --- | --- |
| `OBSERVED` | 200 | Required inspection reads succeeded; no readiness assertion. |
| `PARTIAL` | 200 | Khipu was readable but Anatomy was unavailable; source/window limitations remain visible. |
| `UNAVAILABLE` | 503 | Canonical Khipu was absent, failed, or violated its bounded contract. |

A successful bounded read may still describe a partial Khipu history.
`freshness: NOT_ASSERTED` applies because retrieval time does not prove source
age. Only a validated 40-hex configured root revision is exposed as declared
provenance; it does not establish the deployed image's identity.

Nodes remain `UNVERIFIED`; projection SHA-256 values are inspection checksums.
`execution_authority`, `promotion_authority`, and `signing_authority` are
always false. HTTP 200, a model response, and a graph projection cannot admit
an action or upgrade proof status.

## Why the standalone runtime is not mounted

[`ORORuntime`](../../oro/api.py) initializes its own store, signer, and authorizer.
Its development database defaults to `/tmp/a11oy-oro.sqlite`; its signer uses
[`Ed25519`](../../oro/signing.py). Mounting that runtime would introduce an
independent write and trust boundary. Calling both formats DSSE does not make
its key, payload, authorization, or persistence equivalent to canonical
ECDSA-P256 Khipu receipts.

The observation integration therefore does not construct `ORORuntime`,
`OROStore`, a signer, or a second canonical DAG. It does not checkpoint,
append receipts, verify by mutation, execute barriers, or promote releases.

ADR-0001 owns live storage through `a11oy_state_store`: registered stores,
local paths, immutable snapshots, restoration checks, CAS ownership, and writer
fencing. A separately configured SQLite path does not establish those
properties. Storage admission remains based on integrity, foreign keys, logical
fingerprints, and lease epochs; source revision identity is not a storage gate.
Storage durability must be checked through `GET /api/a11oy/v1/storage/status`.

## Prior art and the decisions it informs

These are documented capabilities and research methods, not measurements of
SZL. Public repository interfaces were reviewed; competitor code was not run.

| Primary source | Transferable pattern |
| --- | --- |
| [Palantir OSDK](https://www.palantir.com/docs/foundry/ontology-sdk/overview), [GitHub](https://github.com/palantir/osdk-ts) | Generate application contracts from shared typed objects; keep frontend and backend semantics aligned. |
| [Palantir action criteria](https://www.palantir.com/docs/foundry/action-types/submission-criteria), [Workflow Lineage](https://www.palantir.com/docs/foundry/workflow-lineage/overview) | Evaluate current action prerequisites and expose dependencies; a dependency graph alone establishes no proof. |
| [Apollo promotion](https://www.palantir.com/docs/apollo/managing-release-channels/configure-promotion-pipeline) | Require functional health: the documented liveness-only fallback cannot reject unhealthy application behavior without health reporting. |
| [LangGraph checkpoints](https://docs.langchain.com/oss/python/langgraph/checkpointers), [fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance), [GitHub](https://github.com/langchain-ai/langgraph) | Separate durable admission from checkpoints; replayed external calls require stable idempotency and outcome reconciliation. |
| [NVIDIA quality gates](https://docs.nvidia.com/nemo/evaluator/tutorials/quality-gate), [GitHub](https://github.com/NVIDIA-NeMo/Evaluator) | Preserve missing, insufficient, breached, and passing evidence; pin tested versions because the referenced documentation is nightly. |
| [LangSmith evaluations](https://docs.langchain.com/langsmith/evaluation-types), [tau-bench paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/1b126cc38b8638e07bef37e7b2bb72bf-Paper-Conference.pdf), [GitHub](https://github.com/sierra-research/tau-bench) | Evaluate resulting state and repeated reliability; curate observed failures into regression cases. |
| [Zeus paper](https://www.usenix.org/conference/nsdi23/presentation/you), [measurement docs](https://ml.energy/zeus/measure/), [GitHub](https://github.com/ml-energy/zeus), [NVML](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html) | Preserve measurement windows, device scope, units, and the energy/performance tradeoff. |

Official video references:
[Palantir DevCon 6: global branching and model migration](https://www.youtube.com/watch?v=U_KHJ5x5-8M)
and [USENIX: Zeus](https://www.youtube.com/watch?v=aZoD-jgO3fE).
Only official descriptions/metadata were reviewed; full videos were not watched.
No novelty or vendor-equivalent capability is claimed.

## Required next contracts — ROADMAP

Before canonical ORO execution, define and validate:

1. **Source ownership:** immutable revision/content bindings, bounded snapshots,
   observation time versus source time, expiry policy, redaction, and explicit
   failure states. A revision-shaped string is not verification.
2. **Persistence:** an ADR-0001 `StoreSpec`, canonical path resolution, restore and
   snapshot coverage, ownership fencing, shutdown/handover, and blocked-write
   behavior. Prove recovery using the storage status contract.
3. **Signing:** canonical payload/DSSE-PAE rules, ECDSA-P256 key ownership,
   verification, receipt-chain linkage, and honest unsigned behavior. Do not
   relabel an Ed25519 signature as canonical authority.
4. **Execution:** deterministic governance before effects, resource budgets,
   durable job admission, operation identities, retry deduplication, cancellation,
   provider reconciliation, and intent/outcome receipts.
5. **Proof and release:** bind claims to exact checker artifacts, assumptions,
   and results. Keep the eight locked formulas unchanged and conjectures labeled.
   Qualify deployment identity and functional probes independently of inspection.

## Acceptance evidence

[`oro/test_evidence_api.py`](../../oro/test_evidence_api.py) and page tests must cover
valid/bounded snapshots, missing or malformed Khipu, Anatomy failure, and
source replacement after route registration. Assert the response schema,
HTTP/status distinction, `NOT_ASSERTED` freshness, and all authority flags.

Use spies to establish no runtime/store/signer construction, checkpoint,
receipt write, or source POST. Verify JSON routing before the SPA catch-all,
Docker packaging, escaped untrusted text, unavailable states, and page/API
agreement. Preserve [adapter tests](../../oro/test_source_adapters.py) and
[DAG tests](../../oro/test_evidence_dag.py). Record actual commands/results
separately; this document asserts no passing test count or live deployment.

## Product extensions — ROADMAP, not implemented

**Evidence impact preview:** show which source/model/configuration changes
invalidate claims and which checks must rerun. Require explicit dependency
contracts; infer neither cross-source causality nor execution permission.

**Energy comparability:** compare quality, latency, and energy only within
compatible workloads, hardware, measurement windows, and scopes. NVML totals
are device-wide; missing telemetry is unavailable, not zero joules. Energy
claims require fresh exporter deltas. Carbon remains ROADMAP without a live
grid feed. Neither feature is part of this observation route.
