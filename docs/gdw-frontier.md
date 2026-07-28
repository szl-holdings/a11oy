# Governed Delta Workspace operational harness

GDW binds an authenticated FastAPI control surface to deny-by-default routing,
the canonical file-backed Colang policy, versioned SQLite state, idempotency keys,
atomic local receipts, structured theorem inputs, load tooling, and an offline
evidence dashboard.

Policy evaluation is currently in-process, so receipts truthfully report
`writer_is_judge=true`; they do not claim an independent policy authority.
Unknown file-backed flows and policy evaluation errors fail closed instead of
being silently skipped. The runtime loads a fresh immutable policy snapshot for
each gate, roots the exact two reviewed Colang files in the evaluator source,
and binds the parser/evaluator digest into the snapshot. Policy, contract, and
evaluator drift cannot fall back to a cached allow.

## Truth boundary

> GDW Frontier Push Pack is a MODELED instrumentation and verification extension for the Governed Delta Workspace. It provides load testing, operator validation, hybrid scheduling research hooks, KDA-vs-MLA memory benchmarking, and Lean-oriented proof export. It does not claim frontier benchmark superiority, proprietary activation access, or production-scale guarantees beyond the measured harness outputs.

The implementation is real code. Each benchmark remains `UNMEASURED` until its
own output is captured. Exporting a theorem input is not a proof; Lean results are
reported separately. The control API chooses a route but does not claim that a
model kernel ran. The optional Torch dispatcher and memory benchmark are the
executable kernel-facing surfaces.

`GDW_PROOF_EXPORT_MODE=outbox` is the only accepted production mode. Each
accepted transition commits state, request, an explicitly `UNSIGNED_ATOMIC`
local receipt, and deterministic receipt/proof outbox records in one SQLite
transaction. A leased drain writes idempotently named JSON artifacts after
commit. This is durable local atomicity plus retry-safe projection, not
cross-system two-phase commit.

Each effect key binds namespace, owner, request, effect kind, and immutable
payload digest. A separate canonical intent binds those values to the persisted
request response, receipt (when mutating), and database-generation identity.
Every claim has an incrementing fencing generation and an observed-time lease;
stale or expired workers cannot attach an artifact. Artifacts are named by the
intent digest, so an identical retry reuses bytes while different content or a
different database generation receives a different path. Existing
non-identical artifacts are never overwritten.

## Runtime

Production starts through `gdw_runtime.py`, verifies an attached persistent
mount, provisions or validates schema v3, selects the declared network-safe
SQLite journal, then supervises the leased outbox drain and `serve.py`.
`GDW_CREDENTIALS_JSON` is a secret-managed version-1 credential registry whose
entries bind a stable `owner_id`, namespace, rotating `key_id`, and scopes to a
bearer credential. Raw bearer values are never persisted in the workspace.
Every write requires the `step:write` scope and a unique `X-Request-Id`.
Reusing an id with identical content replays the prior response; changing the
content returns HTTP 409. Session, request, receipt, proof, and effect identities
are scoped by namespace and owner.

Production requires schema v3, a valid database-generation identity, and
explicit `/data`-contained database, proof, and receipt paths. Valid active v2
effects migrate transactionally into v3; invalid or compacted v2 evidence fails
closed for an offline evidence-preserving migration. Any nonempty unscoped v1
store also requires an offline provenance migration and is never attributed to
a typed owner or environment variable. Per-owner and global quotas are enforced
inside the same write
transaction. Expiration preserves session and idempotency tombstones, garbage
collection never deletes unexported effects, and permanent export failures use
bounded backoff before `DEAD_LETTER`. Health reports `REAL` only after verified
storage, exact journal/synchronous settings, the current schema/database
generation, and a fresh successful pass from the currently running supervisor.
Without those conditions or a valid credential registry and exact governance
snapshot, health reports `UNAVAILABLE` and writes fail closed.

Routes:

- `GET /api/a11oy/v1/gdw/healthz`
- `GET /api/a11oy/v1/gdw/bench/meta`
- `GET /api/a11oy/v1/gdw/metrics`
- `GET /api/a11oy/v1/gdw/integrity`
- `GET /api/a11oy/v1/gdw/sessions/{session_id}`
- `POST /api/a11oy/v1/gdw/step`

## Research lineage

- Kimi Linear technical report: https://yzhang.site/assets/pubs/techreport/2025/kda.pdf
- Gated DeltaNet paper and code: https://arxiv.org/abs/2412.06464
- Laguna technical report: https://arxiv.org/abs/2605.27605
- TorchLean: https://github.com/lean-dojo/TorchLean

These references motivate measurable routes and proof-compatible boundaries.
They are not evidence that this implementation achieves the cited model results.
