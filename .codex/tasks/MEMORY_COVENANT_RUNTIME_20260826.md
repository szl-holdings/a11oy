# Memory Covenant Runtime — production source implementation

## Authority

- Repository: `szl-holdings/a11oy`
- Work branch: `feat/memory-covenant-runtime-20260826`
- Parent hardening head at branch creation: `ec4960e0b98006bcd2840a7704035899c14f7290`
- This is stacked on Memory Covenant post-merge hardening PR #1366. Do not merge this task before its base is protected-main.
- Read root/scoped `AGENTS.md`, current Memory migrations, `routers/frontier_reads.py`, `gdw_auth.py`, Docker/runtime dependency conventions, and exact current workflows before editing.

## Mission

Turn the merged PostgreSQL Memory Covenant contract into a real fail-closed A11oy runtime while preserving PostgreSQL as authority and treating vxdb as a rebuildable derived retrieval index. Implement source and tests; do not return a roadmap.

## Non-negotiable architecture

1. PostgreSQL is authoritative for records, lifecycle, context binding, receipts, query audit, index generations, idempotency, and outbox.
2. A runtime database login MUST be non-superuser, `NOBYPASSRLS`, and a member of `a11oy_memory_app`; fail closed otherwise.
3. HTTP callers never supply arbitrary tenant/domain authority. Deployment configuration fixes the tenant/domain and the database login must have the corresponding durable `memory_context_bindings` row.
4. Every database transaction sets tenant/domain with transaction-local `set_config`; RLS is still the database enforcement boundary.
5. Runtime mutations require bounded bearer authentication using a configured SHA-256 token digest; raw tokens are never retained, logged, returned, or committed.
6. GET/HEAD status and record reads remain side-effect-free. Search auditing is POST-only.
7. Every accepted mutation emits an exact-effect append-only receipt in the same PostgreSQL transaction. Denied operations produce no memory/index/outbox mutation.
8. Idempotency keys are mandatory for writes and lifecycle mutations; same key + different request digest fails closed.
9. Deletion is tombstoning, not hard deletion. Tombstoned, expired, quarantined, failed, or unauthorized records are never returned by retrieval.
10. vxdb is a derived index only. Direct application access to its path/object is prohibited. Loss of the index must be recoverable from PostgreSQL authoritative state plus evidence references.

## Runtime surface

Create an additive pre-catch-all router and supporting modules using repository naming/conventions. Required routes under `/api/a11oy/v1/memory-covenant`:

- `GET /status` — no mutation; reports CONFIGURED / UNAVAILABLE / DEGRADED without exposing DSNs/tokens.
- `GET /records/{memory_id}` — authenticated, RLS-bound authoritative read.
- `POST /records` — authenticated idempotent write; authoritative record + outbox + exact-effect receipt atomically.
- `POST /records/{memory_id}/tombstone` — authenticated idempotent tombstone + outbox delete + receipt atomically; legal hold fails closed.
- `POST /records/{memory_id}/quarantine` — authenticated idempotent quarantine + derived-index delete + receipt atomically.
- `POST /search` — authenticated; requires a verified ACTIVE index generation, obtains candidates only from the derived index, re-resolves every candidate through PostgreSQL under RLS/lifecycle/expiry checks, then writes `memory_query_audit` plus retrieval receipt atomically before returning results.
- `POST /reconcile` — operator/authenticated bounded request that compares authoritative searchable IDs with the active index generation and queues deterministic repair work; it does not silently claim repair succeeded.

Keep aliases out unless current route policy requires them.

## PostgreSQL client boundary

Use Psycopg 3, exact current release `psycopg==3.3.4` (binary extra is acceptable for the container if repository dependency policy permits). Runtime preflight on every new connection/pool must prove:

- `rolsuper = false`;
- `rolbypassrls = false`;
- runtime login is a member of `a11oy_memory_app`;
- tenant/domain configuration is canonical and non-empty;
- RLS-bound probe for the configured context succeeds only after transaction-local context is installed.

Use bounded connect/statement timeouts, explicit transactions, parameterized SQL only, fixed `search_path`, and no string-built SQL from request data.

## Derived vxdb boundary

Pin `vxdb==0.5.1`. Use embedded persistent mode only. Store it under a dedicated configured root with path-containment validation. Collection/index identity MUST include tenant, security domain, and immutable generation ID. Do not share a collection between security domains.

Generation identity includes at minimum provider, embedding model, revision, dimension, metric, normalization, and canonical identity digest. Mixed vector spaces are forbidden. A changed embedding identity creates a BUILDING generation and requires reconciliation/verification before activation.

The runtime must never invent embeddings. Use a configured bounded embedding provider through the existing A11oy provider/embedding boundary if one is genuinely wired; otherwise status/search must fail closed as `INDEX_UNAVAILABLE` while authoritative writes continue to queue outbox work.

## Worker

Implement a separate worker entry point using the existing bounded `memory_lease_outbox` SECURITY DEFINER function. Requirements:

- separate database login/member of `a11oy_memory_worker`;
- bounded batch, lease, attempt count, and backoff;
- validate each event against current authoritative record state before touching vxdb;
- upsert/delete only the target generation collection;
- mark DONE only after observed index effect; RETRY/FAILED must retain sanitized error class, never secrets;
- worker crash/restart is safe and lease expiry is recoverable;
- no worker startup in the web process unless explicitly configured; default off.

## Receipts

Canonical JSON only, no floats, secret-shaped fields rejected. Receipt chain is namespace-scoped (`tenant:security_domain`) and serialized with an advisory transaction lock or equivalent deterministic concurrency primitive. Include request digest, exact effect identifiers/digests, policy/runtime identity, previous digest, sequence, created-at, and explicit integrity mode. Do not claim a cryptographic signature when no managed signer is available.

## Evidence

Content bytes larger than a small bounded inline threshold should be content-addressed under a configured evidence root, with SHA-256 path containment and atomic write/rename. PostgreSQL stores the evidence reference and digest. Never trust user-provided filesystem paths.

## Container/runtime integration

- Register the router from the existing pre-catch-all seam (`routers/frontier_reads.py` or the current equivalent).
- `routers/` is already copied wholesale; ensure every additional non-router module/data file is explicitly included by the canonical Dockerfile.
- Add exact/policy-compliant runtime dependencies to the canonical image and repository dependency manifests/locks required by current CI.
- Do not dynamically install dependencies at runtime.
- Do not add a second web server or second canonical HF writer.

## Tests and hosted gates

Add focused unit/adversarial tests and a real PostgreSQL + real vxdb workflow lane. At minimum prove:

1. missing config/dependency/token => fail closed, existing A11oy still boots;
2. database owner/superuser/BYPASSRLS identity is rejected;
3. cross-tenant/domain read/write cannot be induced through body/query/header data;
4. arbitrary custom GUCs cannot grant authority;
5. denied write creates zero record/outbox/index mutation;
6. same idempotency key/same digest replays exact response; same key/different digest rejects;
7. receipt sequence/hash chain survives concurrent writes;
8. tombstone/expiry/quarantine become immediately non-returnable before asynchronous de-index completes;
9. search post-filters stale vxdb candidates through authoritative PostgreSQL;
10. prompt-injection text stored as content cannot affect router policy/tool authority;
11. generation mismatch/mixed dimension/revision fails closed;
12. worker lease recovery and two-worker SKIP LOCKED behavior are deterministic;
13. complete vxdb deletion followed by reconcile/rebuild restores equivalent searchable IDs/digests;
14. raw query text, bearer tokens, DSN/password material do not enter receipts, audit, logs, or API errors;
15. Docker image imports and registers the runtime; route registration is before proxy/SPA catch-all;
16. doctrine, secret scan, dependency/vulnerability, Docker/COPY, DCO, exact-head tests and all existing protected gates remain green.

Use real service integration where acceptance depends on database/index behavior. Mocks may support unit fault injection but cannot be the acceptance evidence for PostgreSQL/vxdb semantics.

## Promotion

Keep this PR draft while implementation is changing. After implementation:

1. integrate latest protected `main` as a normal parent, no force push;
2. run all exact-head hosted gates;
3. request fresh independent `@codex review` on that exact head;
4. repair every P0/P1 and material P2 without weakening gates;
5. only then mark ready and use the protected merge path;
6. after merge, observe canonical container/HF deployment workflows and exact deployed-SHA readback before claiming live runtime.

## Hard prohibitions

No direct main write. No force push. No admin bypass. No self-approval. No secret retrieval/display/copying. No fake production state. No default-open policy. No public vxdb path. No raw offensive-security execution. No model training or weight publication in this task.

## Definition of done

Source implementation, container wiring, real PostgreSQL/vxdb acceptance, proof packet, exact-head green CI, clean independent review, protected merge, and exact revision deployment/readback are all evidenced. Anything provider/account-bound that genuinely cannot execute must remain explicitly `BLOCKED_EXTERNAL_AUTHORITY`, not painted green.
