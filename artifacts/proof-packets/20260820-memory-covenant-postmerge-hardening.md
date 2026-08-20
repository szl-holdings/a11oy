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
| `migrations/20260811_memory_covenant_v2.sql` | `f764d178bb222dcabc6a802e711b1b55388e043b85360b6ee6ab5d61bb645400` |
| `migrations/20260811_memory_covenant_v2_security_hardening.sql` | `8de8b006a13e2864c29669b7dc1367ae4c2d4033f12c209a682853cb75a2b4d5` |
| `migrations/20260820_memory_covenant_v2_postmerge_hardening.sql` | `c0411bbaedd7c42213d684f8d93425ca5141f67b017970395aa43e5d71167e97` |
| `scripts/validate_memory_covenant_v2.py` | `17313d59257353cbd382cceefd51f2267f3b1e55fcf3208b6443d1c848105f4d` |
| `tests/test_memory_covenant_v2.py` | `34af23695cf9f21ae9c4f922747e3d2dfab12baf349636fbb4a32aeb4bf89404` |
| `tests/memory_covenant_acceptance.sql` | `9317f9864736ab0781c3438ae9f4c67d77867c626892cdc77c3735b714f69cb0` |
| `.github/workflows/memory-covenant-v2.yml` | `de6c32e2c9ab0be8e2abb3473ec7f2254877f679fb7797e0bed5ac0634ec55b7` |

## Corrective controls

- `NULL`, zero, negative, and over-500 lease limits fail with SQLSTATE `22023`;
  null or out-of-range lease durations fail the same way.
- Existing application and worker roles are normalized to `NOSUPERUSER`,
  `NOCREATEDB`, `NOCREATEROLE`, `NOLOGIN`, `NOREPLICATION`, `INHERIT`, and
  `NOBYPASSRLS`. Missing role-management authority aborts the transaction.
- Every outbound membership from either capability role is revoked, preventing
  inherited privileges or a later `SET ROLE` into a stale privileged parent.
- Every existing policy on each covenant table is removed before the sole
  tenant/security-domain isolation policy is installed, preventing permissive
  policy OR-composition from widening access.
- Query-audit and idempotency receipt references use composite
  `(tenant_id, security_domain, receipt_id)` foreign keys. Existing cross-domain
  rows stop the forward migration with SQLSTATE `23503` rather than being masked.
- Every non-owner table and column ACL on covenant relations is revoked before
  the exact application grants are restored. Non-owner `CREATE` ACLs on the
  public schema are removed, while unrelated schema `USAGE` is preserved.
- Covenant relation and function ownership converges on the trusted migration
  principal, closing implicit owner privileges that no ACL revoke can remove.
- Existing non-owner and `PUBLIC` function ACLs are catalog-audited and revoked
  across the trigger, RLS-context, and lease helpers before the exact
  application/worker `EXECUTE` grants are restored.
- RLS custom GUCs are accepted only when the immutable `session_user` role OID
  has an owner-managed tenant/domain binding. A dropped and recreated role does
  not inherit a stale name-based binding.
- A forward upgrade from the historical unbound helper rejects pre-existing
  context-binding rows with SQLSTATE `23514`; it never blesses data that could
  have been planted before this authorization source existed.
- Migration object targets are `public`-qualified. Migration and definer-function
  search paths are pinned to `pg_catalog, pg_temp`, and application relations in
  the function body are schema-qualified.

## Local observations

| Check | Observation |
|---|---|
| Static migration validator | `PASS` |
| Adversarial validator tests | `43` tests passed |
| Python compilation | validator and adversarial tests compiled |
| PostgreSQL parser (`pglast 8.4`) | base `66`, hardening `24`, corrective `51`, acceptance `40` statements parsed |
| Embedded PostgreSQL `18.3` (`PGlite 0.5.5`) | stale owners, inherited role, arbitrary/PUBLIC ACLs, expected untrusted-binding and corrupt-row rejections, full second pass, custom-GUC impersonation denial, and acceptance passed |
| Unprivileged migration-role probe | rejected with SQLSTATE `42501`; transaction did not continue |
| Rollback residue | memory `0`, receipt `0`, outbox `0` |
| Workflow YAML parse (`PyYAML 6.0.3`) | passed |
| Whitespace check | `git diff --check` passed |
| PostgreSQL 18 container/Neon execution | not run locally: this workspace has no Docker or PostgreSQL server binaries |

The workflow now checks out and verifies the requested head SHA, records source
SHA-256 identities, creates an attacker-selected current schema, and applies the
clean-install migrations. It seeds an historical unbound helper, an untrusted
binding row, inherited capability membership, arbitrary
table and column ACLs, schema `CREATE`, `PUBLIC` and arbitrary function grants,
pre-correction role attributes, a permissive policy, and receipt-only foreign
keys. It proves both untrusted-binding and cross-domain-data preflights fail,
then applies the forward correction, reapplies the full migration sequence,
captures exact catalog ACL/membership evidence, and runs rollback-only
acceptance on PostgreSQL 18. Those runtime observations must come from the
exact-head CI run before promotion.

## Operational boundary

The forward migration is deliberately fail-closed. An installation containing
cross-domain audit or idempotency references requires explicit operator review
and data reconciliation before the transaction can succeed. This packet supplies
no production endpoint, database identity, row count, or live deployment claim.
Application logins also require an explicit owner-managed row in
`memory_context_bindings`; absent that binding, tenant-table access denies.
