# GDW Wave 28 Evidence

Date: 2026-07-28

Status: `MEASURED` historical isolated-harness evidence. It does not validate
the post-merge governance and atomicity correction, which requires its own
protected merge, exact-source relock, and live checks.

## Operational scope

The A11oy runtime is the canonical implementation owner. This change adds:

- authenticated GDW step, metrics, metadata, and integrity APIs;
- replay-safe request IDs with conflict rejection;
- versioned owner-scoped SQLite persistence with a serialized writer queue;
- ACCEPT, REJECT, and QUARANTINE state transitions;
- a policy dispatcher for `kda_local`, `laguna_hybrid`, and `mla_global`;
- deterministic local receipts (the original run used the in-memory A11oy
  substrate; those receipts were not cryptographically signed);
- durable receipt/proof outbox projection; synchronous external export is
  rejected by the corrective contract;
- Prometheus text metrics, dashboard exports, Postman checks, burst and Locust load tools;
- CUDA memory comparison tooling for KDA and MLA state;
- Lean models for scheduler soundness, activation receipts, replay, and delta-state invariants.

The API policy selects a route but does not claim that the selected research kernel was executed. Kernel execution remains explicit in response metadata.

## Acceptance evidence

### API and persistence

- Final burst: `10,000 / 10,000` HTTP-successful requests.
- Transport errors: `0`.
- Malformed JSON responses: `0`.
- Accepted state transitions: `10,000`.
- Missing receipts: `0`.
- SQLite integrity: `ok`.
- Orphan receipts: `0`.
- Persisted rows: `10,000` sessions, `10,000` requests, `10,000` receipts, and `10,000` proof-outbox records.
- Proof drain: `10,000` exported, `0` pending, SQLite integrity `ok`.
- Throughput: `42.05221442` requests/second.
- Latency: p50 `2,880.92855 ms`, p95 `19,368.32543 ms`, p99 `36,283.72173 ms`.

The run satisfies functional completeness and integrity gates. The observed p95 and p99 do not establish a production latency SLA.

### Failure and remediation

The first synchronous-proof 10,000-request run returned `9,967` successful
responses and `33` errors. Receipts and SQLite integrity appeared complete, but
the run failed the strict response gate and did not prove cross-system
atomicity. The post-merge correction moves both receipt and proof projections
behind one transactional effect outbox with deterministic idempotency keys and
leased claims. The restoration branch additionally binds stable principals,
per-owner/global quotas, retention tombstones, bounded retry/dead-letter state,
verified persistent `/data` paths, a network-safe journal, and a supervised
drain worker. It also fails closed on unknown policy flows, reports the
in-process writer/judge boundary, validates row-to-payload effect bindings, and
refuses non-identical artifact replacement. The historical final fresh run
completed with zero transport or response errors; it is not evidence for the
corrected implementation until the corrected harness is rerun.

### Postman

- Collection items: `6 / 6`.
- Requests: `6 / 6`.
- Assertions: `18 / 18`.
- Failures: `0`.

The collection exercised the assembled `serve:app`, including authentication, schema, replay, conflict, and multistep behavior.

### CUDA memory

Environment:

- PyTorch: `2.12.1+cu130`.
- CUDA runtime: `13.0`.
- GPU: `NVIDIA GeForce RTX 5050 Laptop GPU`.

All `12 / 12` benchmark scenarios completed without OOM. The measured allocation model used `512` bytes per MLA token and `131,072` bytes per KDA session. At batch `16` and sequence length `16,384`, MLA allocated `134,217,728` bytes and KDA allocated `2,097,152` bytes.

These figures are benchmark-harness allocation measurements, not model-quality or end-to-end serving claims.

### Lean

- Elan: `4.2.3`.
- Lean: `4.13.0`.
- `lake build LutarPolicy`: passed, `17` targets.
- GDW modules built: `SchedulerSoundness`, `DeltaStateInvariant`, `ActivationReceipt`, and `ReceiptReplay`.
- Placeholder scan: no `sorry` or `axiom` declarations.

The Lean files prove properties of the committed abstract models. They do not prove arbitrary Python, CUDA, or distributed runtime behavior.

### Focused software gates

- GDW runtime, attention, and benchmark-tool tests: passed.
- CUDA router/dispatcher tests: `3` passed.
- Assembled OpenAPI schema: passed.
- Serve router parity: passed.
- Git whitespace check: passed.

The isolated test environment initially lacked the existing project `cryptography` dependency, which prevented the compute-pool contract from registering. Installing that declared runtime dependency restored the route and the OpenAPI gate passed.

## Source boundary

Research-informed naming and policy references are grounded in:

- Kimi Linear technical report: <https://yzhang.site/assets/pubs/techreport/2025/kda.pdf>
- NVIDIA GatedDeltaNet: <https://github.com/NVlabs/GatedDeltaNet>
- Gated Delta Networks paper: <https://arxiv.org/abs/2412.06464>
- TorchLean: <https://lean-dojo.github.io/TorchLean/>
- Laguna technical report: <https://arxiv.org/abs/2605.27605>

No third-party repository code was copied into this change.

## Release boundary

This evidence does not establish that:

- GitHub branch protection and required checks have accepted the exact head;
- the change has been independently reviewed;
- the protected PR has merged;
- a new container image has been published;
- Hugging Face is serving the merged source;
- `a-11-oy.com` or `a11oy.net` is serving the GDW routes;
- production latency, durability across restarts, or external load behavior meets an SLA.

Those claims require separate, live evidence after protected merge and deployment.
