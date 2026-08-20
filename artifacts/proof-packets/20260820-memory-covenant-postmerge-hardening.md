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
| `migrations/20260811_memory_covenant_v2.sql` | `9a4031c279d45f6c3d051eed8237b27a849f2a52c2a25e26c3ef323cdfc922fb` |
| `migrations/20260811_memory_covenant_v2_security_hardening.sql` | `8de8b006a13e2864c29669b7dc1367ae4c2d4033f12c209a682853cb75a2b4d5` |
| `migrations/20260820_memory_covenant_v2_postmerge_hardening.sql` | `bff25f0494eb7335ece7c1fe6d8e56fea9dbdebb693f065e27f173ef33d3db85` |
| `scripts/validate_memory_covenant_v2.py` | `f38980338fde2052884151a61a9a33a67f6a4ddb657bf181cd276e4f4fddfa5c` |
| `tests/test_memory_covenant_v2.py` | `cd0ef454fc14225fc3b76bf24f25a8660ad55a752d3e76e15e21f2935c5b185a` |
| `tests/memory_covenant_acceptance.sql` | `7ddeefaa4df7bdc0cfb0b23f4edf4c32e2aff5ad954254b4cb05376ac33bcfe4` |
| `.github/workflows/memory-covenant-v2.yml` | `ab9f444ca0e42f8a4d210572fb2c36c9f93a0afcfab1dcfc6707cb724257ddd7` |

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
- Every base or corrective reapplication rejects a nonempty context-binding
  table with SQLSTATE `23514`. This schema has no durable row-level write
  provenance, so canonical current owners, helper source, and owner-only ACLs
  cannot distinguish an approved binding from one planted under a temporary
  INSERT grant that was later revoked. Operators must reconcile and reprovision
  bindings explicitly; present catalog state is never silently blessed.
- The forward correction recreates the updated-at and append-only helper bodies,
  removes every non-internal trigger from every covenant relation, restores the
  exact five-trigger set, and restores ENABLE/FORCE RLS state (with the explicit
  NO FORCE exception required by bounded outbox leasing).
- Migration object targets are `public`-qualified. Migration and definer-function
  search paths are pinned to `pg_catalog, pg_temp`, and application relations in
  the function body are schema-qualified.

## Local observations

| Check | Observation |
|---|---|
| Static migration validator | `PASS` |
| Adversarial validator tests | `60` tests passed |
| Python compilation | validator and adversarial tests compiled |
| PostgreSQL parser (`pglast 8.4`) | base `66`, hardening `24`, corrective `72`, acceptance `43` statements parsed |
| Embedded PostgreSQL `18.3` (`PGlite 0.5.5`) | exact acceptance, revoked temporary binding-INSERT ACL proof, base and corrective nonempty-row rejection, failed-preflight atomicity, full second pass, and final acceptance passed |
| Unprivileged migration-role probe | rejected with SQLSTATE `42501`; transaction did not continue |
| Rollback residue | memory `0`, receipt `0`, outbox `0` |
| Workflow YAML parse (`PyYAML 6.0.3`) | passed |
| Whitespace check | `git diff --check` passed |
| PostgreSQL 18 container/Neon execution | not run locally: this workspace has no Docker or PostgreSQL server binaries |

The workflow now checks out and verifies the requested head SHA, records source
SHA-256 identities, creates an attacker-selected current schema, and applies the
clean-install migrations. It seeds a substring-spoofed unbound helper, an
untrusted binding row, no-op trigger helpers, missing and arbitrary triggers,
disabled RLS, inherited capability membership, arbitrary table and column ACLs,
schema `CREATE`, `PUBLIC` and arbitrary function grants, pre-correction role
attributes, a permissive policy, and receipt-only foreign keys. It proves the
untrusted-binding and cross-domain-data preflights fail, applies the forward
correction, and runs full acceptance before any historical migration is rerun.
It then grants a runtime application member temporary column-level INSERT,
plants a binding, revokes the grant, proves the live column ACL is clean, and
requires corrective reapplication to fail because the row has no durable write
provenance. The failed preflight leaves the planted row intact for explicit
operator handling. Only after cleanup does the workflow reapply the full
migration sequence, capture exact catalog ACL/membership evidence, and run
rollback-only acceptance again on PostgreSQL 18. Those hosted observations
must come from exact-head CI before promotion.

## Operational boundary

The forward migration is deliberately fail-closed. An installation containing
cross-domain audit or idempotency references requires explicit operator review
and data reconciliation before the transaction can succeed. This packet supplies
no production endpoint, database identity, row count, or live deployment claim.
Application logins also require an explicit owner-managed row in
`memory_context_bindings`; absent that binding, tenant-table access denies.
