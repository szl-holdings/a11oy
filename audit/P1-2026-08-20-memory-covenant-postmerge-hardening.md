<!-- SPDX-License-Identifier: Apache-2.0 -->

# P1 audit — Memory Covenant v2 post-merge hardening

**Base:** `e484563ab3bce2e655f27876042821e991e8651f`

**Disposition:** corrective source prepared locally; promotion blocked on exact-head review and PostgreSQL 18 CI

## Findings closed in source

1. `NULL` no longer bypasses the outbox lease bound.
2. Pre-existing worker and application roles are fully normalized to
   non-privileged attributes; insufficient authority aborts instead of emitting
   a notice and continuing.
3. Stale permissive RLS policies are removed before the one expected isolation
   policy is recreated on each table.
4. Query-audit and idempotency rows bind receipts by tenant, security domain, and
   receipt ID, with a fail-closed preflight for legacy cross-domain rows.
5. Role/table/schema ACL application is subtractive, and stale non-owner
   `SECURITY DEFINER` function grants are catalog-audited and revoked.
6. Migration targets and application relations are schema-qualified; migration
   and function search paths exclude mutable application schemas.
7. Capability roles cannot retain inherited parents, and arbitrary non-owner
   table, column, schema-`CREATE`, helper-function, or `PUBLIC` ACLs are removed
   before the exact contract is restored.
   Relation and function owners also converge on the trusted migration
   principal so implicit owner authority cannot survive the upgrade.
8. User-settable tenant/domain GUCs no longer authorize a context alone. The
   immutable session principal OID must also have an owner-managed binding, and
   the PostgreSQL acceptance test denies an attempted unbound-domain switch.
   A historical forward upgrade also rejects any pre-existing binding rows as
   untrusted instead of treating potentially planted authorization as valid.
9. Hosted proof checks out the requested SHA explicitly and records commit and
   source-file identities alongside catalog membership and ACL evidence.

## Qualification

- `python3 scripts/validate_memory_covenant_v2.py` — passed.
- `python3 tests/test_memory_covenant_v2.py -v` — 43 tests passed.
- `python3 -m py_compile ...` — passed.
- PostgreSQL parser pass over all three migrations and acceptance SQL — passed.
- Embedded PostgreSQL `18.3` (`PGlite 0.5.5`) seeded stale object owners,
  inherited membership, and arbitrary/PUBLIC ACLs, rejected both a planted
  binding row and the corrupt cross-domain row, converged on a second pass,
  denied custom-GUC impersonation, and left zero rollback residue — passed.
- An unprivileged migration-role probe stopped at role creation with SQLSTATE
  `42501`; it did not continue under a notice-only fallback.
- Workflow YAML parse and `git diff --check` — passed.

Docker and server-process PostgreSQL binaries were not available in this local
workspace. The exact-head container workflow remains the required promotion
authority for the seeded forward-upgrade scenario, two-pass idempotency, catalog
inspection, cross-domain denial, append-only behavior, bounded worker leasing,
and rollback residue.

## Claims withheld

- No production database migration.
- No production application or worker role binding.
- No production context-binding rows; application access remains fail-closed
  until an owner binds the runtime login OID to approved tenant/domain pairs.
- No live worker or service readiness claim.
- No exact-head CI or independent review claim until those records exist.
