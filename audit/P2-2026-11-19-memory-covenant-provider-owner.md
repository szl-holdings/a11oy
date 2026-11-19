<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# P2 audit — Memory Covenant v2 under a provider-managed (non-superuser) owner

**Base:** protected `main` `02fe78903c859aa7ef570b96bcb36724b5d59bb4`

**Disposition:** source fix prepared; promotion requires exact-head CI on all three
Memory Covenant jobs, owner review of the ADMIN-retention decision below, and a
separate, owner-approved rehearsal on a disposable provider branch before any
provider database is touched.

## Finding

Providers such as Neon never grant the superuser attribute; the project owner
holds `CREATEDB`, `CREATEROLE` and `BYPASSRLS` instead. Three properties of the
role-hardening and corrective migrations made them unusable by such an owner:

1. `ALTER ROLE <capability> NOSUPERUSER NOCREATEDB … NOBYPASSRLS` names the
   superuser attribute. PostgreSQL rejects that from any caller that is not a
   superuser, even when the statement only clears the attribute:
   *"Only roles with the SUPERUSER attribute may change the SUPERUSER attribute."*
   The whole transaction rolls back, so the corrective migration could not be
   applied at all by a provider owner once the capability roles existed.
2. The inbound ADMIN sweep removes the owner's own ADMIN on both capability
   roles. Without a superuser, nobody can then grant `a11oy_memory_app` or
   `a11oy_memory_worker` to a new runtime login.
3. A caller that is not a superuser can revoke only membership grants it made.
   Run by the owner, `REVOKE ADMIN OPTION FOR … FROM <delegate>` on a delegate
   granted by another role only emits a WARNING and keeps the grant, so the
   sweep could report success while leaving delegation in place.

## Change

- Both role-hardening migrations read each existing capability role's
  attributes from `pg_catalog.pg_roles` and issue one guarded `ALTER ROLE` per
  deviating attribute. The superuser attribute is cleared only when the
  migration principal is itself a superuser; otherwise the transaction aborts
  with SQLSTATE `42501`. There is still no notice-only fallback.
- The inbound ADMIN sweep skips only `CURRENT_USER`, the migration principal
  that owns every covenant relation and definer function.
- New fail-closed assertions after both membership sweeps abort with `42501` if
  any outbound membership or any non-owner ADMIN delegation survived.
- The acceptance assertion now exempts exactly the owner of
  `public.memory_records` from the "no ADMIN OPTION" rule; every other holder
  still fails it. **This narrows an existing acceptance invariant on purpose and
  needs the owner's explicit approval.** Without it, a provider deployment
  cannot provision new runtime logins.
- The static validator requires the guarded per-attribute statements, the
  fail-closed superuser branch, the owner-only exemption, both assertions after
  both sweeps, and the acceptance exemption limited to the covenant owner. It
  rejects any combined `ALTER ROLE` that names the superuser attribute. Nine new
  adversarial tests cover these.
- A third workflow job, `provider-owner-acceptance`, creates a non-superuser
  owner with `CREATEDB CREATEROLE BYPASSRLS`, applies all three migrations twice
  as that owner, checks the owner still holds ADMIN on both capability roles and
  can grant a runtime login and write a binding (rolled back), then runs the
  rollback-only acceptance.

## Qualification (local, before any push)

| Check | Result |
|---|---|
| Static contract (`scripts/validate_memory_covenant_v2.py`) | PASS |
| Adversarial validator tests | 87 passed (78 existing + 9 new) |
| Exact-head review tests | 3 passed |
| `git diff --check` | clean |
| Workflow replay, all three jobs, PostgreSQL 18.6 (`io.zonky.test.postgres:embedded-postgres-binaries-linux-amd64:18.6.0`) | all steps exit 0; seeded hostile scenario produced exactly its three deliberate preflight rejections; three acceptance runs PASS |
| Same `provider-owner-acceptance` job against the unmodified `main` migrations | fails with the superuser-attribute error above (the job detects the regression) |

The replay ran the workflow's own `run:` scripts with a shim routing
`docker exec … psql` to a local server on a Linux abstract socket. It is not
GitHub Actions, and the PostgreSQL build is a third-party one; exact-head hosted
CI remains the promotion authority.

## Labels

- **MEASURED (local PostgreSQL 18.6):** every behaviour in *Finding* and
  *Qualification*.
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
