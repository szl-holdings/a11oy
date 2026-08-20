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
| `migrations/20260811_memory_covenant_v2.sql` | `ea36466ed0d3c30177622eed4914ddcb9f2ce58a87f7284d76256f3c8764a63b` |
| `migrations/20260811_memory_covenant_v2_security_hardening.sql` | `8de8b006a13e2864c29669b7dc1367ae4c2d4033f12c209a682853cb75a2b4d5` |
| `migrations/20260820_memory_covenant_v2_postmerge_hardening.sql` | `0c2587ff20dbed049581e62139dfb292c26d2548b6da95a9f0046a0833f442c0` |
| `scripts/validate_memory_covenant_v2.py` | `757e430a50c1154a5a28613659c44f817ffa45ba081bdbb367695614d1976010` |
| `tests/test_memory_covenant_v2.py` | `ca318f365064ecb04f5e356f469ab6ada12a937093c9a9601311c7285d9f4fad` |
| `tests/memory_covenant_acceptance.sql` | `f2f256d755b014923259e9912e8c108e707920cddcd9907572a20fddb9c16bb7` |
| `.github/workflows/memory-covenant-v2.yml` | `d81090fec7a8a1d016005709d92a39cf72f08c69262d47e16b31254beb4bb22a` |

## Corrective controls

- `NULL`, zero, negative, and over-500 lease limits fail with SQLSTATE `22023`;
  null or out-of-range lease durations fail the same way.
- Existing application and worker roles are normalized to `NOSUPERUSER`,
  `NOCREATEDB`, `NOCREATEROLE`, `NOLOGIN`, `NOREPLICATION`, `INHERIT`, and
  `NOBYPASSRLS`. Missing role-management authority aborts the transaction.
- Every outbound membership from either capability role is revoked, preventing
  inherited privileges or a later `SET ROLE` into a stale privileged parent.
- Every existing policy on each covenant table is removed before the sole
  tenant/security-domain isolation policy is installed on each application
  data table. The owner-only binding table remains policy-free, preventing
  permissive policy OR-composition from widening access.
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
- Before that preflight, the migration converges the binding-table owner and
  restores `ENABLE ROW LEVEL SECURITY` with `NO FORCE ROW LEVEL SECURITY`.
  The owner scan therefore observes physical rows independently of stale RLS
  policies without disabling RLS; a rejection rolls all three catalog changes
  back with the transaction.
- The forward correction recreates the updated-at and append-only helper bodies,
  removes every non-internal trigger from every covenant relation, restores the
  exact five-trigger set, and restores exact RLS state: FORCE on tenant data
  except the bounded-leasing outbox, and ENABLE/NO FORCE with zero policies on
  the owner-only context-binding table.
- Migration object targets are `public`-qualified. Migration and definer-function
  search paths are pinned to `pg_catalog, pg_temp`, and application relations in
  the function body are schema-qualified.

## Local observations

| Check | Observation |
|---|---|
| Static migration validator | `PASS` |
| Adversarial validator tests | `71` tests passed |
| Python compilation | validator and adversarial tests compiled |
| PostgreSQL parser (`pglast 8.4`) | base `68`, hardening `24`, corrective `74`, acceptance `43` statements parsed |
| Embedded PostgreSQL `18.3` (`PGlite 0.5.5`) | clean-install acceptance, FORCE-RLS/GUC-filter hidden-row reproduction, non-superuser corrective rejection, failed-preflight RLS/owner/policy atomicity, revoked temporary binding ACL/policy proof, full second pass, and final acceptance passed |
| Unprivileged migration-role probe | rejected with SQLSTATE `42501`; transaction did not continue |
| Rollback residue | memory `0`, receipt `0`, outbox `0` |
| Workflow YAML parse (`PyYAML 6.0.3`) | passed |
| GitHub Actions lint (`actionlint 1.7.12`) | passed |
| Whitespace check | `git diff --check` passed |
| PostgreSQL 18 container/Neon execution | not run locally: this workspace has no Docker or PostgreSQL server binaries |

The workflow now checks out and verifies the requested head SHA, records source
SHA-256 identities, creates an attacker-selected current schema, and applies the
clean-install migrations. It seeds a substring-spoofed unbound helper, an
untrusted binding row hidden from its non-superuser owner by FORCE RLS and a
GUC-filtered policy, no-op trigger helpers, missing and arbitrary triggers,
disabled RLS, inherited capability membership, arbitrary table and column ACLs,
schema `CREATE`, `PUBLIC` and arbitrary function grants, pre-correction role
attributes, a permissive policy, and receipt-only foreign keys. It proves that
the stale owner sees zero binding rows but the corrective preflight still fails,
then verifies that the rejected transaction preserves the prior owner, FORCE-RLS
state, and stale policy. It also proves the cross-domain-data preflight, applies
the forward correction, and runs full acceptance before any historical
migration is rerun.
It then grants a runtime application member temporary column-level INSERT plus
a temporary INSERT policy, plants a binding, revokes both authorities, proves
the live column ACL and policy catalogs are clean, and requires corrective
reapplication to fail because the row has no durable write provenance. The
failed preflight leaves the planted row intact for explicit
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
