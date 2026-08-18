# Proof Packet — Memory Covenant bounded index worker

Date: 2026-08-17  
Branch: `codex/p0-a11oy-stage-20260811`

## Implemented source

- `routers/memory_index_worker.py`
  - leases only through `memory_lease_outbox`;
  - requires a non-superuser, non-`BYPASSRLS` member of `a11oy_memory_worker`;
  - verifies both bounded worker functions exist;
  - validates the event generation against the configured immutable generation digest and requires `ACTIVE` state;
  - passes the outbox event id to the injected adapter as its idempotency key;
  - commits the lease before calling an external adapter, avoiding a database lock across provider latency;
  - stores only bounded, secret-screened settlement metadata;
  - converts unexpected adapter failures to error-class-only retry evidence;
  - settles only the exact worker/event lease;
  - exposes no arbitrary environment import path and selects no mock/default provider.
- `migrations/20260817_memory_covenant_worker_completion.sql`
  - adds a bounded `SECURITY DEFINER` completion function;
  - requires worker-role membership;
  - allows only DONE, RETRY, or FAILED settlement of the caller's exact lease;
  - bounds retry delay to 1..3600 seconds;
  - revokes public execution and grants only the worker capability.
- `migrations/20260817_memory_covenant_worker_generation_access.sql`
  - grants the worker read access to the authoritative generation table while its tenant/security-domain RLS remains in force.
- `tests/test_memory_index_worker.py`
  - covers successful idempotent upsert, permanent generation mismatch, transient retry, secret-shaped result rejection, unsafe principal refusal, empty queue behavior, configuration bounds, and SQL authority limits.
- `.github/workflows/memory-index-worker.yml`
  - installs the exact sealed PostgreSQL driver, compiles the worker, runs focused tests, checks SQL authority anchors, and rejects whitespace errors.

## Operational state

Current state: `IMPLEMENTED / EXACT_HEAD_CI_PENDING`.

The queue lifecycle and authority boundaries are implemented. Provider activation is deliberately not inferred. A reviewed adapter must be injected in code and must implement idempotent upsert/delete behavior for the declared generation. No embedding endpoint, API key, model, vector database, or deployment was selected or invoked by this change.

## Non-claims

- No external index provider was called.
- No embedding was generated.
- No outbox row was leased from production.
- No database migration was applied to production.
- No Hugging Face, Fireworks, GitHub protected-main, model, or GPU mutation occurred.
- No adapter result containing credential-shaped fields may be persisted.

## Rollback

Revert the worker module, two worker migrations, focused tests, workflow, and this packet. Any database rollback must use the governed migration process and verify that no active worker depends on the functions before removal.
