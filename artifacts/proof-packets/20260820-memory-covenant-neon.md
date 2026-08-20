# Memory Covenant v2 — Neon revalidation proof packet

**Revalidated:** 2026-08-20  
**Scope:** PostgreSQL schema, role/RLS hardening, append-only controls, and bounded outbox leasing  
**Source branch:** `feat/memory-covenant-v2-current-main-20260820`

## Exact migration identity

| Path | Git blob |
|---|---|
| `migrations/20260811_memory_covenant_v2.sql` | `c6de618869feb1489dff0452b421e635c03f0830` |
| `migrations/20260811_memory_covenant_v2_security_hardening.sql` | `fdd23ae500a48825c23c1a927c5a9e084deaea49` |

These migrations were extracted from the stale mixed P0 branch onto exact protected `main`. Already-merged token-routing files were not replayed.

## Connected validation environment

The connected Neon control plane identified the isolated validation project used by the earlier proof packet:

- project name: `a11oy-memory-covenant-validation-20260811`
- project identifier: `young-snow-70923323`
- validation branch: `br-bitter-block-a6kuzqxt`
- database: `neondb`
- PostgreSQL: `18.6`

No connection string, hostname, password, token, or credential value is recorded in this packet.

## Catalog readback

A read-only catalog query confirmed the following live database state:

- seven expected tables are present:
  - `memory_records`
  - `memory_evidence_refs`
  - `memory_outbox`
  - `memory_receipts`
  - `memory_query_audit`
  - `memory_index_generations`
  - `memory_idempotency`
- RLS is enabled on all seven tables;
- FORCE RLS is enabled on the six tenant-scoped application tables;
- `memory_outbox` is deliberately `NO FORCE ROW LEVEL SECURITY` so its owner-executed, bounded `SECURITY DEFINER` lease function can operate across tenant partitions;
- every table has exactly one tenant/security-domain isolation policy;
- append-only triggers protect `memory_receipts`, `memory_query_audit`, and `memory_idempotency`;
- `a11oy_memory_app` and `a11oy_memory_worker` are `NOLOGIN`, `INHERIT`, `NOBYPASSRLS`, non-superuser roles;
- `memory_lease_outbox(text, integer, integer)` is `SECURITY DEFINER`;
- PUBLIC execution is revoked from the lease function;
- the worker role receives function execution rather than direct table-wide privileges.

## Rollback-only acceptance transaction

A single transaction was executed against the isolated validation branch and then rolled back. It re-proved:

1. **Same-domain visibility:** an application-role row was visible with the matching tenant and security-domain context.
2. **Cross-domain confidentiality:** the same row became invisible after changing the security-domain context.
3. **Cross-domain write denial:** inserting a row for another security domain was rejected by RLS.
4. **Append-only enforcement:** an attempted receipt update was rejected with SQLSTATE `55000`.
5. **Bounded worker leasing:** the dedicated worker capability leased one ready outbox event with a bounded owner, expiry, and attempt increment.
6. **Zero residue:** after rollback, the test memory, receipt, and outbox row counts were all zero.

The acceptance transaction did not leave role memberships, records, receipts, leases, or audit rows behind.

## Reproducible repository qualification

`.github/workflows/memory-covenant-v2.yml` reproduces the contract without touching Neon:

- runs the fail-closed static validator and adversarial tests;
- starts an isolated PostgreSQL 18 service;
- applies both migrations twice to prove idempotency;
- captures exact catalog evidence;
- executes `tests/memory_covenant_acceptance.sql` as a rollback-only transaction;
- requires zero persistent acceptance residue;
- retains the evidence artifact for 90 days.

## Truth boundary

This packet proves the migration contract against an isolated Neon validation branch and a reproducible PostgreSQL 18 CI environment. It does **not** claim that a production database was migrated, that an application login has inherited the capability roles in production, that a production worker is running, or that any live application is using the schema. Those are separate deployment and runtime-readback lifecycles.
