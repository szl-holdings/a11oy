<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# P2 audit — Memory Covenant v2, second review of the provider-owner change

**Base:** `main` `535db170e1dd595c4ab16990fae176e993d88b36`, which contains the
merged provider-owner change (#3755, squash `8d604a5`) described in
[`P2-2026-11-19-memory-covenant-provider-owner.md`](P2-2026-11-19-memory-covenant-provider-owner.md).

**Disposition:** source fix prepared as one local commit and not pushed.
Promotion still requires exact-head CI on all three Memory Covenant jobs, owner
review, and the separate, owner-approved rehearsal on a disposable provider
branch that the 2026-11-19 note requires. No provider database was contacted.

## What the second review found, and what changed

1. **A membership grant can race past the sweep. It is now detected and
   refused.** PostgreSQL authorizes `GRANT <role> TO x` against committed state
   before it takes the role's lock. An ADMIN holder connected during a
   migration can therefore issue a grant that waits behind the sweep and lands
   after COMMIT. The new row names a grantor that no longer holds ADMIN.
   - Both migrations' assertion blocks now check that every `pg_auth_members`
     row on a capability role names, as grantor, a superuser or a role that
     currently holds ADMIN on that role. The check fails closed with `42501`,
     *a capability-role membership was granted by a role that no longer holds
     ADMIN on it*. A grantor that no longer exists fails too.
   - The acceptance has the same check: *Memory Covenant capability membership
     has a grantor without ADMIN*.
   - This is detection, not prevention. The raced migration itself still exits
     0, and the row is refused on the next run and by the acceptance.
2. **Base migration precondition.** The base migration now opens with the same
   pinned principal precondition, right after `BEGIN` and the safe
   `search_path`: the principal must be a superuser or hold `BYPASSRLS`, and
   must own schema `public`. Before this change, a principal that the hardening
   and corrective refuse could still commit the base alone. The base replaces
   the RLS helper and revokes PUBLIC `EXECUTE` on it, and only the hardening
   grants `EXECUTE` back. A runtime login's read of `memory_receipts` then
   failed with *permission denied for function a11oy_memory_context_matches*.
   That was measured; every covenant table's policy calls the same helper. The
   validator requires the precondition in all three files.
3. **The validator now lexes SQL.** Regular-expression comment stripping is
   replaced by a lexer that follows PostgreSQL's scanner and psql's statement
   splitter. It handles:
   - single-quoted strings with `''` escapes and `E''` strings with backslash
     escapes;
   - double-quoted identifiers and dollar quotes;
   - `--` comments only outside literals, and nested block comments;
   - identifiers that contain `$`, so `a$$` is not a dollar quote.

   Its normalized output is byte-identical to the old one on the four files as
   they stood before this change, so every existing pattern check sees the same
   text it saw before.

   The contract now rejects text whose meaning a token check cannot see:
   - any tagged dollar quote (`$tag$`); the files use only `$$`;
   - psql meta-commands, except the acceptance's first line
     `\set ON_ERROR_STOP on`;
   - psql variable references, Unicode-escape literals and identifiers, and
     `BEGIN ATOMIC` bodies;
   - any mention of `standard_conforming_strings`, `backslash_quote` or
     `escape_string_warning`, since the lexer assumes PostgreSQL's default.

   Pins count only where the server runs them:
   - Whole statements (the precondition, the assertion block, the lease
     function and the acceptance's role DO block) count only as top-level
     statements.
   - Inner blocks (attribute convergence, both sweeps, and the acceptance's
     ADMIN exemption and attribute assertion) count only inside the body of a
     top-level `DO $$ … $$` statement.
   - The DO statements that hold those inner blocks are pinned whole as well, so
     dead code or an exception handler cannot be wrapped around them.

   Outside the pinned statements, the validator also rejects:
   - a role-attribute column, or any use of the `observed` record;
   - `ALTER ROLE`, `ALTER USER` or `ALTER GROUP` on a capability role;
   - `CREATE ROLE`, `CREATE USER` or `CREATE GROUP`;
   - a `GRANT` of a capability role, and any membership change built from a
     format string (`GRANT %I TO`, `REVOKE %I FROM`);
   - a role switch (`SET ROLE`, `SET SESSION AUTHORIZATION`, or `set_config`
     on `role`).
4. **CI coverage.**
   - **Provider-owner job:**
     - A principal that owns its own database but lacks `BYPASSRLS` is refused
       by the base, the hardening and the corrective with the row-security
       message. CI first confirms that this principal owns schema `public`, so
       the refusal isolates the `BYPASSRLS` requirement.
     - The provider owner, which holds `BYPASSRLS`, meets a legacy cross-domain
       audit row, seeded the way the superuser job seeds it. The corrective
       refuses with *memory_query_audit contains a cross-domain receipt
       reference*.
     - Every state refusal runs against the hardening and against the
       corrective alone. The states are: a superuser attribute, a
       foreign-grantor delegation, an outbound membership, a SET or INHERIT
       survivor, a SET-only member, the raced grant, a schema owned by a
       capability role, and the database owned by a capability role.
     - For the database-owner state, the owner inherits that capability role,
       so it still owns schema `public` and reaches the assertion block.
     - The corrective alone also converges re-seeded attribute deviations.
   - **Raced-grant fixture:** CI builds the raced grant's end state without a
     race. The delegate grants normally, so the member's row and its
     dependency on the grantor are real. A superuser then sets only the
     delegate's own `pg_auth_members` row to the shape the sweep leaves. CI
     requires the exact refusal from both migrations and from the acceptance.
   - **Superuser job:**
     - It proves the lease guard against a swept delegate given `EXECUTE`
       through another role and against a SET-only member, and proves that an
       inheriting worker login still leases.
     - The SET-only row is refused by the corrective and the acceptance.
     - The database owned by a capability role is refused by both migrations
       and the acceptance.
   - **Delegate names:** in both database jobs every seeded delegate can log
     in. It is named by a random letter plus 16 random hex digits, with no
     fixed prefix. The fixture delegate `a11oy_memory_stale_grantee` keeps its
     name, because the acceptance checks it by name, and it can now log in.
5. **Lease guard and SET-only rows.**
   - `memory_lease_outbox` in the hardening and the corrective, the two files
     that define it, now tests `pg_has_role(session_user,
     'a11oy_memory_worker', 'USAGE')`. In PostgreSQL 16 and later `MEMBER` is
     true for any membership row, even one with ADMIN, INHERIT and SET all
     false. The refusal message is now *session user does not inherit
     a11oy_memory_worker*; SQLSTATE `42501` is unchanged.
   - Both migrations and the acceptance refuse any non-owner membership row on
     a capability role that has SET but neither INHERIT nor ADMIN. That is the
     row older sweeps left behind.
   - The acceptance comment that called MEMBER "SET ROLE" is corrected.
6. **Ownership.** The assertion block fails closed when a capability role owns
   the current database or any schema, with *a capability role owns the
   database or a schema*. Owning the database makes a role a member of
   `pg_database_owner`, which owns schema `public`, and `pg_auth_members` does
   not show that path. The acceptance has the same check.
7. **Validator: acceptance pin and `if:` keys.**
   - The acceptance's role-attribute assertion is pinned as a whole statement,
     and so is the role DO block that holds it.
   - The validator rejects any `if:` key in
     `.github/workflows/memory-covenant-v2.yml`, in plain, quoted, escaped,
     tagged or flow-mapping form, and also merge keys and explicit `?` keys.
   - The two evidence-upload steps lost their `if: always()`, so evidence is
     now uploaded only when a job passes. On failure, the long steps print
     their evidence logs to the job log instead.
8. **Documentation.** This note; the corrections to the 2026-11-19 note are
   marked there.

## Operating constraints

- **Principal attributes.**
  - The principal must be a superuser or hold `BYPASSRLS`, and must own schema
    `public`, which in PostgreSQL 15 and later means owning the database. All
    three files now check this first.
  - Every run also issues `ALTER ROLE <capability> NOCREATEROLE` on each
    existing capability role, to lock its row. That needs `CREATEROLE` and
    ADMIN on the role: a principal with only one of the two is refused.
  - Clearing `CREATEDB` or `REPLICATION` on a capability role needs the
    principal to hold that attribute itself.
  - These refusals are PostgreSQL's own errors, not named refusals.
  - (MEASURED. By the same PostgreSQL rule, clearing `BYPASSRLS` needs
    `BYPASSRLS`. That case is REASONED, not measured here, and it cannot arise,
    because the precondition already requires `BYPASSRLS`.)
- **No ADMIN holder may be connected while the migrations run.** The grantor
  check finds a raced grant on the next run, but it cannot stop one from
  landing. (MEASURED)
- **Removing a raced row.** A superuser removed it with `REVOKE <role> FROM
  <member> GRANTED BY <grantor>`, after which the hardening applied. Of the
  routes tried without a superuser, two were denied:
  - the owner's direct `REVOKE … GRANTED BY`;
  - the same `REVOKE` issued while acting as the grantor, which no longer
    holds ADMIN.

  Dropping the member role worked where the owner administers that role. Other
  routes were not tried. (MEASURED)
- **Runtime logins must INHERIT their capability role.** A `NOINHERIT` login
  that is granted the role normally gets a SET-only row, and the migrations and
  the acceptance refuse it. The lease guard admits only a session user that
  inherits the worker role. (MEASURED)
- **A refusal is not a repair.** The migrations refuse to report success on a
  bad state but do not change it. While a capability role owns the database, a
  runtime login that inherits it can still drop a covenant table until an
  operator fixes the ownership. (MEASURED)
- **How live installs receive these edits.** This change edits files that
  already carry versions. A runner that tracks applied versions will not re-run
  them, so the hardening and the corrective must be re-applied deliberately:
  - The hardening carries the precondition, the attribute convergence, both
    sweeps, the whole assertion block and the USAGE lease guard.
  - Once a runtime binding is committed, the base and the corrective refuse
    with `23514` by design. On such an install, re-apply the hardening alone.
    Where no binding is committed yet, re-apply the hardening and then the
    corrective.
  - First remove any SET-only membership and any raced row, or the hardening
    refuses.
  - (MEASURED: on an install migrated with the previous files and holding one
    committed binding, the new base and corrective refused with `23514`, the
    new hardening applied, and the lease guard changed from `member` to
    `USAGE`.)
- **What a provider rehearsal can verify without a superuser.**
  - Re-applying the hardening as the owner re-runs its precondition and its
    whole assertion block.
  - The acceptance's catalog assertions also run as the owner.
    `tests/memory_covenant_acceptance.sql` runs as the owner up to its first
    `SET SESSION AUTHORIZATION`, which needs a superuser. On a clean database it
    stops there; with a SET-only member present, it stops earlier, at that
    member.
  - The row-security and lease probes that follow need a superuser, or real
    logins that the owner creates and binds.
  - The acceptance also fails on a database that holds an older pending outbox
    event. The second review measured this; this change does not alter it.
  - (MEASURED, except the probes through owner-created logins, which were not
    run)
- **Provider owner attributes.** The provider owner's attributes, and Neon's
  one-cluster-per-branch layout, are MODELED everywhere they are stated: the
  migration and acceptance comments, the validator, the tests, the workflow and
  both notes. Nothing was read back from a provider.
- **Static validator limits.** The validator is advisory against a deliberate
  edit:
  - A statement built at run time from concatenated strings is still invisible
    to it.
  - A pinned statement changed together with its pin passes by design.
  - The database jobs remain the authority. Measured example: a coordinated
    edit that re-admits a database owner without `BYPASSRLS`, applied to all
    three migrations and to the validator's pin, passes the validator and the
    unit tests. The provider-owner job then fails with *expected a refusal
    that did not happen*.

## Qualification (local, before any push)

| Check | Result |
|---|---|
| Static contract (`scripts/validate_memory_covenant_v2.py`) | PASS |
| `python3 -m pytest -q tests/test_memory_covenant_v2.py tests/test_memory_covenant_exact_head_review.py` | 141 passed and 15 subtests passed: 138 contract tests (104 pre-existing, 34 new) and 3 exact-head review tests |
| Normalization regression | lexer output byte-identical to the old normalization on the four pre-change files |
| Second-review attacks V1 to V6, rebuilt on this tree with the reviewers' own generator | each rejected by the validator |
| Second-review mutations R1, R2, R3, R5, M3, M5, D1, T1 and T2, applied to this tree | each rejected by the validator |
| Mutations P1 and P2, judged with their own edited validator | rejected, because they leave the base precondition unedited |
| Mutation M2 | not applied as written: its anchor matches two lines now. Its edit changes the pinned assertion block either way |
| A coordinated weakening of the precondition in all three migrations and in the pin | static gates pass by design; the replayed provider-owner job fails |
| Workflow replay, all three jobs, PostgreSQL 18.6 | every step exits 0. Every expected refusal prints its exact message (16 distinct messages): 26 migration refusals and 1 acceptance refusal in the provider-owner job, and 12 refusals in the superuser job |
| Grant race, interleaved by observed `pg_locks` state (hardening and corrective; superuser and provider owner) | the raced migration exits 0, and the member's row names a grantor without ADMIN. Both migrations refuse on the next run, and so does the acceptance. The previous files pass both next runs and the acceptance |
| CI catalog fixture against the raced end state | identical `pg_auth_members` rows and grantor dependency, with the same refusals |
| Base precondition (owner without `BYPASSRLS` on the historical state) | the new base refuses with the catalog fingerprint unchanged, and the runtime login still reads its tenant. The previous base committed and broke the runtime login |
| Base precondition (`BYPASSRLS` principal that does not own schema `public`, fresh database) | the new base refuses and creates no table. The previous base created 8 tables owned by that principal |
| Lease guard | a swept delegate given `EXECUTE` through another role and a SET-only member are refused by the guard. A worker login that inherits the role leases. With the previous files, all three leased every tenant |
| SET-only row left by the parent release's sweep (`02fe789`) | the new hardening, the new corrective and the new acceptance refuse it, and after the row is revoked both migrations apply |
| Capability role owning the database or a schema | both migrations and the acceptance refuse. The previous files passed both migrations; the previous acceptance caught database ownership only indirectly and passed schema ownership |

The replay ran the workflow's own `run:` scripts with a shim that routes `docker
exec … psql` to a local server on a Linux abstract socket. It is not GitHub
Actions, and `uses:` steps are skipped. The PostgreSQL build is a third-party
one (`io.zonky.test.postgres:embedded-postgres-binaries-linux-amd64:18.6.0`).
Exact-head hosted CI remains the promotion authority.

## Labels

- **MEASURED (local PostgreSQL 18.6):** every result in *Qualification*, and
  every operating constraint marked MEASURED.
- **REASONED, not measured:**
  - Behaviour on other PostgreSQL 18 minor releases. CI's `postgres:18` image
    floats, and that includes superuser updates to `pg_auth_members`, which the
    CI fixture relies on.
  - That GitHub reports a job skipped by `if:` as satisfying a required check.
- **MODELED:** the provider owner's attributes and Neon's
  one-cluster-per-branch layout.
- **Not claimed:** that any provider database was migrated, that the
  provider's real owner role matches the model, that hosted CI has run this
  change, production readiness, or prevention of the grant race.

## Follow-up outside this repository

`szl-org-health` pins the corrective migration's Git blob in its database
contracts. This change edits the corrective again, so those pins must move to
the new blob in a separate reviewed change, after this one merges.
