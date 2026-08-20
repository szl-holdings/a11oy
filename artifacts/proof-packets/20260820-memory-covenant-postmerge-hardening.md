<!-- SPDX-License-Identifier: Apache-2.0 -->

# Memory Covenant v2 post-merge hardening — local evidence packet

**Base:** protected `main` commit `e484563ab3bce2e655f27876042821e991e8651f`

**Scope:** source migrations and qualification gates only

**Status:** local static and embedded PostgreSQL 18 qualification passed; container CI remains pending

This packet records a corrective successor to the source merged through PR #1362.
It does not claim that a production database was migrated, that production logins
were bound to the capability roles, or that a memory worker is live.

## Source identities

| Source | SHA-256 |
|---|---|
| `migrations/20260811_memory_covenant_v2.sql` | `e8e1140d1ce11eb2e0cfe801d02719f2ffbce93e40adc2fcd05c4b036e9d46fe` |
| `migrations/20260811_memory_covenant_v2_security_hardening.sql` | `0bc83a2c069441324beefdb0346d6dd37898d6591183002cb1da91ae1287ff59` |
| `migrations/20260820_memory_covenant_v2_postmerge_hardening.sql` | `6e34097720a92b14b81e4933df0e296caa19f000c7bc2896aba88581c0fa45d1` |
| `scripts/validate_memory_covenant_v2.py` | `816406cc6448edaf5e2616f25d1ed5fd712fadb228f19599770e73345de76468` |
| `tests/test_memory_covenant_v2.py` | `9454a4528c56ff1e6f87a36febd775156d5ae7d26a754a1ab441741069215e5f` |
| `tests/memory_covenant_acceptance.sql` | `34cc7dc4ea7029732976f82af755c1632ca4a2c29657ee0e0bebc09efdeb9cc8` |
| `.github/workflows/memory-covenant-v2.yml` | `b4e56b9d0116a391be36d88427354c6c58607e14e9d0a2872a12b1a874706471` |

## Corrective controls

- `NULL`, zero, negative, and over-500 lease limits fail with SQLSTATE `22023`;
  null or out-of-range lease durations fail the same way.
- Existing application and worker roles are normalized to `NOSUPERUSER`,
  `NOCREATEDB`, `NOCREATEROLE`, `NOLOGIN`, `NOREPLICATION`, `INHERIT`, and
  `NOBYPASSRLS`. Missing role-management authority aborts the transaction.
- Every existing policy on each covenant table is removed before the sole
  tenant/security-domain isolation policy is installed, preventing permissive
  policy OR-composition from widening access.
- Query-audit and idempotency receipt references use composite
  `(tenant_id, security_domain, receipt_id)` foreign keys. Existing cross-domain
  rows stop the forward migration with SQLSTATE `23503` rather than being masked.
- Table and schema ACLs are revoked before the exact application grants are
  restored. The worker retains no direct memory-table privileges.
- Existing non-owner `EXECUTE` ACL entries on the `SECURITY DEFINER` lease
  function are catalog-audited and revoked before the worker-only grant is made.
- Migration object targets are `public`-qualified. Migration and definer-function
  search paths are pinned to `pg_catalog, pg_temp`, and application relations in
  the function body are schema-qualified.

## Local observations

| Check | Observation |
|---|---|
| Static migration validator | `PASS` |
| Adversarial validator tests | `31` tests passed |
| Python compilation | validator and adversarial tests compiled |
| PostgreSQL parser (`pglast 8.4`) | base `50`, hardening `21`, corrective `34`, acceptance `37` statements parsed |
| Embedded PostgreSQL `18.3` (`PGlite 0.5.5`) | seeded forward upgrade, expected corrupt-row rejection, full second pass, and acceptance passed |
| Unprivileged migration-role probe | rejected with SQLSTATE `42501`; transaction did not continue |
| Rollback residue | memory `0`, receipt `0`, outbox `0` |
| Workflow YAML parse (`PyYAML 6.0.3`) | passed |
| Whitespace check | `git diff --check` passed |
| PostgreSQL 18 container/Neon execution | not run locally: this workspace has no Docker or PostgreSQL server binaries |

The workflow now creates an attacker-selected current schema, applies the clean
install migrations, seeds the pre-correction role attributes, ACLs, permissive
policy, function grants, and receipt-only foreign keys, applies the forward
correction, reapplies the full migration sequence, and runs rollback-only
acceptance on PostgreSQL 18. Those runtime observations must come from the
exact-head CI run before promotion.

## Operational boundary

The forward migration is deliberately fail-closed. An installation containing
cross-domain audit or idempotency references requires explicit operator review
and data reconciliation before the transaction can succeed. This packet supplies
no production endpoint, database identity, row count, or live deployment claim.
