# P0 Memory Covenant proof packet — 2026-08-11

## Scope

This packet records the real database-side qualification of the A11oy Memory Covenant v2 schema. It does not claim protected-main merge, Hugging Face deployment, runtime route activation, model training, GPU work, or production traffic.

## Source identity

- Repository: `szl-holdings/a11oy`
- Protected-main source used to seed the task: `90ed8c7289efbda085d82f0dc60cf821b22f5caf`
- Work branch: `codex/p0-a11oy-work-20260811`
- Task PR: `#1261`
- Base migration: `migrations/20260811_memory_covenant_v2.sql`
- Security hardening migration: `migrations/20260811_memory_covenant_v2_security_hardening.sql`

## Isolated acceptance database

The migration was exercised on a dedicated Neon project created for this qualification rather than against the unrelated existing application project.

- Neon project ID: `young-snow-70923323`
- Branch ID: `br-bitter-block-a6kuzqxt`
- Database: `neondb`
- PostgreSQL family: Neon PostgreSQL

No credential or connection string is recorded in this repository packet.

## Applied contract

The isolated database contains these governed tables:

- `memory_records`
- `memory_evidence_refs`
- `memory_outbox`
- `memory_receipts`
- `memory_query_audit`
- `memory_index_generations`
- `memory_idempotency`

Observed controls after migration:

- RLS enabled on every memory table.
- Forced RLS on authoritative record, evidence, receipt, query-audit, generation, and idempotency tables.
- `memory_outbox` keeps RLS enabled but does not force the table owner through RLS because the bounded `SECURITY DEFINER` lease function must service multiple tenant partitions.
- Append-only mutation guards are installed on `memory_receipts`, `memory_query_audit`, and `memory_idempotency`.
- `memory_records` and `memory_outbox` have `updated_at` maintenance triggers.
- `memory_lease_outbox()` is `SECURITY DEFINER`, bounded by worker ID, lease count, and lease duration, and execution is revoked from `PUBLIC`.
- Dedicated roles `a11oy_memory_app` and `a11oy_memory_worker` are `NOBYPASSRLS`.

## Acceptance observations

### RLS isolation

The initial owner-session probe was intentionally rejected as sufficient proof because the Neon migration owner reports `rolbypassrls=true`. A dedicated non-bypass application role was therefore created and used for the actual tenant-isolation acceptance test.

Under `SET ROLE a11oy_memory_app`:

- context `tenant-a / domain-a` inserted one test record;
- the same context observed `visible_same_domain = 1`;
- switching only the security domain to `domain-b` observed `visible_cross_domain = 0`;
- a cross-domain insert attempt was rejected by the RLS policy;
- the test rows were rolled back to the acceptance savepoint;
- post-rollback residue was `0` rows.

Verdict: **APPLIED_AND_VERIFIED** for database-level tenant + security-domain isolation under the intended non-bypass runtime role.

### Append-only receipt guard

A temporary receipt was inserted inside a savepoint. An attempted `UPDATE` was intercepted by the append-only trigger using SQLSTATE `55000`; the receipt operation remained unchanged. The savepoint was then rolled back.

Verdict: **APPLIED_AND_VERIFIED** for database-level append-only receipt mutation protection.

### Schema/control inventory

The acceptance query observed all seven memory tables with RLS enabled, the expected trigger set, one isolation policy per memory table, the context predicate function, the mutation-rejection function, the updated-at function, and the `SECURITY DEFINER` outbox lease function. The dedicated worker role exists and is not superuser or RLS-bypass capable.

Verdict: **APPLIED_AND_VERIFIED** for the isolated PostgreSQL control plane.

## Root cause discovered during qualification

Testing through the Neon owner role produced `visible_cross_domain = 1` because that provider-managed role has `BYPASSRLS`. This was not treated as a policy failure or hidden. The contract was hardened with an explicit `a11oy_memory_app` `NOBYPASSRLS` role and the acceptance test was rerun under that role, where the cross-domain result became `0`.

## Remaining boundaries

Database qualification does **not** prove the following yet:

- the application runtime is connected with a member login of `a11oy_memory_app`;
- the outbox worker is connected with the dedicated worker capability;
- a vector/embedding index worker has processed a real generation;
- the canonical container includes every new runtime dependency;
- protected PR checks are terminal green at the final exact head;
- independent review has approved the successor lineage;
- the source has merged to protected `main`;
- the canonical Hugging Face writer has deployed the exact merge SHA;
- `/api/build-info` and provider readback agree on the deployed immutable revision.

Until those gates are separately evidenced, the overall production release remains **NOT VERIFIED / NOT COMPLETE**.
