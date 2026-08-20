# GDW Wave 28 Evidence

Date: 2026-07-28

Status: `MEASURED` historical isolated-harness evidence. It does not validate
the post-merge governance and atomicity correction, which requires its own
protected merge, exact-source relock, and live checks.

Successor status: `MEASURED_LOCAL` for the forward-only corrective working tree
only.
The local GDW adversarial suite passed `19 / 19` on 2026-07-28, and the
digest-registry/runtime-configuration suite passed `4 / 4`. The combined
focused promotion run passed `27`, skipped one hardware-dependent case, and
failed none. It covered strict
rejection of unknown policy flows and evaluator exceptions, persisted principal
ownership, cross-owner
read/replay/mutation denial, bounded request quotas and post-export reclamation,
canonical outbox tamper detection even after attacker-controlled rehashing,
generation-bound immutable artifacts across database reset, lease-token fencing,
replay telemetry, admin-only idempotent effect drain, and network-volume-safe
SQLite journal selection. The broad serve-router parity test exceeded a bounded
two-minute local run and remains `UNVERIFIED` in this working tree; the hosted
route/OpenAPI gates are separate evidence. This is not independent review,
protected merge, deployment, or production evidence.

On 2026-07-29, the forward integration suite passed `133`, skipped one
hardware-dependent case, and failed none. That run added digest-native
authentication compatibility, transactional v2 proof-only migration,
generation-visible responses/receipts/proof inputs, artifact readback and
tamper verification, owner-scoped artifact quotas, admin-global integrity and
drain controls, exact runtime-source verification, and both runtime
configuration suites. Compile, Docker source inclusion, OpenAPI, and Git
whitespace checks are separate gates; this remains local source evidence.

## Operational scope

The A11oy runtime is the canonical implementation owner. This change adds:

- principal-authenticated GDW step, metrics, metadata, and integrity APIs;
- replay-safe request IDs with conflict rejection;
- SQLite WAL persistence with a serialized writer queue;
- ACCEPT, REJECT, and QUARANTINE state transitions;
- a policy dispatcher for `kda_local`, `laguna_hybrid`, and `mla_global`;
- deterministic local receipts (the original run used the in-memory A11oy
  substrate; those receipts were not cryptographically signed);
- canonical receipt/proof intent plus full-digest-bound outbox projection;
  synchronous external export is rejected by the corrective contract;
- bounded owner/global request, session, and artifact quotas with finite
  retention and export-aware reclamation;
- immutable owner-scoped, generation- and content-bound artifact identities;
- token-fenced effect leases and fail-closed integrity checks;
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

The historical run satisfied its then-current functional and integrity gates.
The observed p95 and p99 do not establish a production latency SLA, and the run
does not exercise the successor semantics.

### Failure and remediation

The first synchronous-proof 10,000-request run returned `9,967` successful
responses and `33` errors. Receipts and SQLite integrity appeared complete, but
the run failed the strict response gate and did not prove cross-system
atomicity. The correction moves both receipt and proof projections behind one
transactional effect outbox with deterministic idempotency keys and leased
claims. The historical final fresh run completed with zero transport or response
errors; it is not evidence for the corrected implementation until the corrected
harness is rerun.

The first correction draft remained unsafe: unknown Colang flows could be
reported as evaluated without enforcement; one global token had no persisted
object ownership; outbox rows were not bound back to canonical response and
receipt identities; reset databases could overwrite evidence paths; and stale
workers could interfere with newer leases. The forward-only successor repairs
those contracts but remains draft and unreviewed at this evidence boundary.

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
