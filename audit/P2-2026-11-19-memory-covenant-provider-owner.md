<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# P2 audit — Memory Covenant v2 under a provider-managed (non-superuser) owner

**Base:** protected `main` `02fe78903c859aa7ef570b96bcb36724b5d59bb4`

**Disposition:** source fix prepared; promotion requires exact-head CI on all three
Memory Covenant jobs, owner review of the ADMIN-retention decision below, and a
separate, owner-approved rehearsal on a disposable provider branch before any
provider database is touched.

## Finding

Providers such as Neon are modeled as never granting the superuser attribute,
with the project owner holding `CREATEDB`, `CREATEROLE` and `BYPASSRLS` instead.
These attributes are MODELED: they were not read back from any provider.
(Corrected 2026-11-24: an earlier wording stated them as fact.) Three
properties of the role-hardening and corrective migrations made them unusable
by such an owner:

1. `ALTER ROLE <capability> NOSUPERUSER NOCREATEDB … NOBYPASSRLS` names the
   superuser attribute. PostgreSQL rejects that from any caller that is not a
   superuser, even when the statement only clears the attribute:
   *"Only roles with the SUPERUSER attribute may change the SUPERUSER attribute."*
   The whole transaction rolls back, so the corrective migration could not be
   applied at all by a provider owner once the capability roles existed.
2. The acceptance invariant "no capability membership retains ADMIN OPTION"
   can never pass on a provider database. A non-superuser owner that creates a
   role receives ADMIN on it through an implicit grant that PostgreSQL records
   with the bootstrap superuser as grantor. The owner cannot revoke that grant.
   The parent's inbound sweep only warned, kept the ADMIN row, and added a
   self-granted membership row with SET true. Without the owner's ADMIN, no one
   could grant `a11oy_memory_app` or `a11oy_memory_worker` to a new runtime
   login on a provider database. (An earlier draft of this note said the sweep
   *removed* the owner's ADMIN; an independent review showed that does not
   reproduce, and this item is corrected.)
3. A caller that is not a superuser can revoke only membership grants it made.
   Run by the owner, `REVOKE ADMIN OPTION FOR … FROM <delegate>` on a delegate
   granted by another role only emits a WARNING and keeps the grant, so the
   sweep could report success while leaving delegation in place.

## Change

- **Principal precondition.** The hardening and corrective migrations open
  with a fail-closed check, before any other statement. The migration
  principal must be a superuser or hold `BYPASSRLS`, and must own schema
  `public` (in PostgreSQL 15 and later, own the database). Without the first,
  the corrective's cross-domain preflight and the foreign-key validation for the
  tenant/domain keys run under FORCE RLS with every policy stripped. They see
  no rows, pass, and leave `convalidated = true` constraints that real rows
  violate. Without the second, PostgreSQL reduces the schema privilege sweep to
  warnings. Both abort with SQLSTATE `42501`.
- **Attribute convergence under a row lock.** For each existing capability role,
  the migration first refuses by name a superuser role that this principal
  cannot clear. It then issues `ALTER ROLE <capability> NOCREATEROLE`, which
  rewrites and locks that role's catalog row until COMMIT. Next it reads the
  remaining attributes from `pg_catalog.pg_roles` and issues one guarded
  `ALTER ROLE` per deviating attribute. A concurrent `ALTER ROLE` by an
  untrusted ADMIN holder now waits and fails with
  *tuple concurrently updated*. Before this change it slipped in after the
  read and survived the migration.
- **Inbound sweep.** It skips only `CURRENT_USER`, the migration principal that
  owns every covenant relation and definer function. Swept delegates are
  re-granted `WITH INHERIT FALSE, SET FALSE, ADMIN FALSE`. PostgreSQL 16 and
  later leave SET true unless it is named, so the earlier grant let a former
  delegate `SET ROLE a11oy_memory_worker` and lease every tenant's outbox
  events. That gap predates this change.
- **Fail-closed assertions after both sweeps.** The migration aborts with `42501`
  if any of the following survived:
  - an outbound membership;
  - a non-owner ADMIN delegation;
  - a swept delegate's grant from another grantor that still carries SET or
    INHERIT;
  - any capability-role attribute deviation.
- **Acceptance.**
  - It exempts exactly the owner of `public.memory_records` from the "no ADMIN
    OPTION" rule; every other holder still fails it. **This narrows an existing
    acceptance invariant on purpose and needs the owner's explicit approval.**
    Without it, a provider deployment cannot provision runtime logins.
  - It now also re-checks the audit and idempotency rows against
    `memory_receipts`, so a constraint validated without seeing the rows still
    fails.
  - It asserts that the seeded fixture delegate, `a11oy_memory_stale_grantee`,
    holds ADMIN, INHERIT and SET all false. It checks that fixture only, not
    every swept delegate. (Corrected 2026-11-24: an earlier wording claimed
    every swept delegate. The 2026-11-24 note adds a check, in the migrations
    and the acceptance, that fails closed on any non-owner row with SET but
    neither INHERIT nor ADMIN.)
- **Static validator.** It now pins whole statements instead of substrings:
  - the precondition, which must open the transaction;
  - both role-convergence blocks;
  - both sweeps;
  - the assertion block;
  - the acceptance exemption.

  Outside those statements it rejects any role-attribute column, any use of the
  `observed` record, and any `ALTER ROLE` or `ALTER USER` on a capability role.
  An extra predicate, a reordered or `WITH`-form `ALTER`, and an assignment to
  `observed` each previously passed every static gate; each now fails one. The
  validator is still a text check: dynamic SQL can defeat it, so the database
  jobs remain the authority.

  (Corrected 2026-11-24: plain static SQL defeated it as well. Its regex
  comment stripping cut lines at a `--` inside a string literal and did not
  nest block comments. A pinned statement copied into a literal or a comment
  still counted. The 2026-11-24 note replaces it with a lexer and counts pins
  only where PostgreSQL runs them. After that note's third review, it also
  refuses the control characters, such as NUL and CR, at which psql reads a
  file differently from the lexer, and it refuses dynamic SQL outside the
  pinned statements. The validator stays advisory against any deliberate
  edit; that note lists its limits.)
- **CI.**
  - The superuser job seeds a delegate with a run-unique name and requires the
    corrective to strip ADMIN, INHERIT and SET.
  - A stale owner without `BYPASSRLS` is now refused by the precondition. A
    superuser rerun proves the provenance preflight still refuses the planted
    binding rows.
  - The provider-owner job applies all three migrations twice as a
    non-superuser owner. It then converges seeded attribute deviations and a
    run-unique owner-granted delegate. It also proves, each with its exact
    message, that the migration aborts on:
    - a SUPERUSER capability role;
    - a delegate given ADMIN by another grantor;
    - an outbound membership the owner cannot revoke;
    - a swept delegate with SET from another grantor;
    - a principal without `BYPASSRLS`;
    - a principal that does not own schema `public`.

    After every refusal rolls back, it re-applies cleanly and runs the
    rollback-only acceptance.

## Operating constraints (documented, not changed)

- The migration principal must hold `BYPASSRLS` (or be a superuser) and own the
  database. Whether a given provider's owner role has these attributes is
  MODELED until read back from that provider. (Added 2026-11-24: the base
  migration now checks this too.)
- (Added 2026-11-24.) On every run the migrations issue `ALTER ROLE
  <capability> NOCREATEROLE` on each existing capability role, which needs
  `CREATEROLE` and ADMIN on that role. Clearing `CREATEDB` or `REPLICATION`
  needs the principal to hold that attribute itself. Both refusals are
  PostgreSQL's own errors, not named refusals.
- (Added 2026-11-24.) No ADMIN holder may be connected while the migrations
  run. A grant it issues during the sweep can land after COMMIT. The new
  grantor check refuses such a row on the next run and in the acceptance, but
  it cannot prevent it.
- (Added 2026-11-24.) Runtime logins must INHERIT their capability role. A
  SET-only membership is refused, and the lease guard tests `USAGE`.
- Capability roles exist once per cluster, which on Neon means once per branch
  (MODELED). Because the exemption is limited to `CURRENT_USER`, only one owner
  role per cluster can apply the covenant.
- With `createrole_self_grant` set, the owner also receives INHERIT or SET rows
  on the capability roles. The migrations do not touch those rows, and the
  acceptance does not check them. If the owner self-grants SET later, that row
  persists.
- Once a runtime binding is committed, re-applying the base or corrective
  migration is refused with `23514` by design. Runners must track applied
  versions rather than re-apply every file on each deploy. The CI's two-pass
  idempotency covers an empty bindings table only. (Added 2026-11-24.) A
  version-tracking runner will not re-run a file that was edited after it was
  applied. Live installs must re-apply the hardening deliberately, and the
  corrective too where no binding is committed yet; see the 2026-11-24 note.
- Former delegates swept by an older release keep a row with SET true. The
  current sweep does not select them, because they no longer hold ADMIN. A
  provider readback should list every membership row on both capability roles
  before promotion. (Updated 2026-11-24: such a row now makes the migrations and
  the acceptance fail closed until an operator removes it.)
- Known pre-existing gap, not fixed here: the outbound assertion reads only
  `pg_auth_members`. A capability role that owns the database is implicitly a
  member of `pg_database_owner`. The acceptance catches this only indirectly,
  through its schema CREATE check. (Fixed 2026-11-24: the migrations and the
  acceptance now fail closed when a capability role owns the database or any
  schema.)

## Qualification (local, before any push)

| Check | Result |
|---|---|
| Static contract (`scripts/validate_memory_covenant_v2.py`) | PASS |
| Adversarial validator tests | 104 passed (78 pre-existing, 9 from the first revision, 17 for the review findings) |
| Exact-head review tests | 3 passed |
| `git diff --check` | clean |
| Workflow replay, all three jobs, PostgreSQL 18.6 (`io.zonky.test.postgres:embedded-postgres-binaries-linux-amd64:18.6.0`) | every step exits 0; every expected refusal printed its exact message; all three acceptance runs PASS (corrective-only and final in the superuser job, and the provider-owner job) |
| Reviewer race reproductions (corrective and hardening; BYPASSRLS, worker LOGIN and natural-lock variants) | attacker's `ALTER ROLE` fails with *tuple concurrently updated*; capability attributes stay clean. Same scripts against the previous revision: the attribute survives |
| Non-`BYPASSRLS` owner with legacy cross-domain rows | refused by the precondition before any foreign key exists. Previous revision: both tenant/domain keys committed as validated over violating rows |
| Swept delegate's `SET ROLE a11oy_memory_worker` | *permission denied to set role*. Previous revision: allowed |

The replay ran the workflow's own `run:` scripts with a shim routing
`docker exec … psql` to a local server on a Linux abstract socket. It is not
GitHub Actions, and the PostgreSQL build is a third-party one; exact-head hosted
CI remains the promotion authority.

## Labels

- **MEASURED (local PostgreSQL 18.6):** every behaviour in *Finding* and
  *Qualification*, except the provider owner's attributes in the opening
  paragraph of *Finding*, which are MODELED.
- **MODELED:** the provider owner's attributes (`LOGIN NOSUPERUSER CREATEDB
  CREATEROLE BYPASSRLS`, with or without `REPLICATION`). No provider database was
  contacted.
- **Not claimed:** that any provider database was migrated, that the provider's
  real owner role matches the model, production readiness, or a causal-frontier
  closure (still tracked in #3684).

## Follow-up outside this repository

`szl-org-health` pins the corrective migration's Git blob in its database
contracts. Once this change merges, those pins must move to the new blob in a
separate reviewed change.
