# P0 audit — Memory Covenant v2

**Audit date:** 2026-08-20  
**Promotion branch:** `feat/memory-covenant-v2-current-main-20260820`  
**Protected source at branch creation:** `fc897dd3719c56220f6794d3561bf35899af8b30`

## Decision

**Source contract: QUALIFICATION READY**  
**Production database deployment: NOT CLAIMED**

The Memory Covenant work was separated from stale PR #1334 because that branch mixed already-merged token-ingress code with two still-unpromoted database migrations. This successor contains only the database contract, static and PostgreSQL acceptance tests, and updated evidence.

## Controls under review

| Control | Source mechanism | Qualification mechanism |
|---|---|---|
| Authoritative relational memory records | `memory_records` with canonical JSON/hash checks | static contract + PostgreSQL catalog |
| Tenant and security-domain isolation | RLS policies using `a11oy_memory_context_matches` | same-domain and cross-domain rollback tests |
| Owner bypass prevention | FORCE RLS on six application tables | catalog assertion |
| Bounded cross-tenant worker capability | `memory_lease_outbox` SECURITY DEFINER function | role, ACL, bounds, and lease transaction tests |
| Worker least privilege | function EXECUTE only; no direct memory-table grants | exact grant comparison |
| Append-only evidence | mutation-rejection trigger with SQLSTATE `55000` | update/delete negative controls |
| Idempotent migration | IF NOT EXISTS / OR REPLACE / bounded DROP-IF-EXISTS | migrations applied twice in CI |
| Derivable index generations | explicit provider/model/revision/identity state | schema checks and catalog evidence |
| Audit and receipt integrity | canonical digest and namespace constraints | schema checks plus append-only tests |
| Rollback safety | acceptance data and temporary role membership in one transaction | zero-residue assertion |

## Fail-closed static contract

`scripts/validate_memory_covenant_v2.py` rejects:

- missing tables, policies, RLS, or FORCE RLS;
- FORCE RLS on the bounded worker outbox;
- missing `USING` or `WITH CHECK` tenant/domain policy clauses;
- removal or weakening of append-only triggers and SQLSTATE `55000`;
- LOGIN, SUPERUSER, or BYPASSRLS role escalation;
- application privilege expansion;
- direct worker table grants;
- PUBLIC function execution or `GRANT ALL`;
- unbounded lease counts or durations;
- missing fixed `search_path` or `SKIP LOCKED`;
- destructive table/schema operations, RLS disablement, or extension installation;
- non-idempotent table/index creation and UTF-8 BOM corruption.

`tests/test_memory_covenant_v2.py` supplies adversarial mutations for each critical boundary.

## PostgreSQL 18 acceptance

The repository workflow starts an isolated PostgreSQL 18 service and:

1. applies both migrations;
2. reapplies both migrations to prove idempotency;
3. captures tables, policies, triggers, role posture, and function posture;
4. executes a rollback-only transaction proving isolation, append-only rejection, and bounded worker leasing;
5. verifies zero persistent acceptance residue;
6. uploads the evidence artifact for 90 days.

## Connected Neon revalidation

The previously identified isolated Neon validation project was read through the connected control plane. PostgreSQL `18.6`, all seven tables, exact RLS/FORCE-RLS posture, bounded roles, append-only triggers, and the SECURITY DEFINER lease function were present. A rollback-only transaction re-proved same-domain access, cross-domain denial, SQLSTATE `55000`, worker leasing, and zero residue.

See `artifacts/proof-packets/20260820-memory-covenant-neon.md` for the exact evidence boundary.

## Promotion conditions

The branch may merge only when the exact head is current with protected `main` and every required repository workflow is terminal green, including the Memory Covenant static and PostgreSQL acceptance jobs, Tests, CodeQL, container/SBOM, DCO, Doctrine, secret and vulnerability scans, Hugging Face parity, and repository integrity guards.

Promotion must use the normal protected squash path with an exact-head guard and a physical DCO trailer. No force update, administrator bypass, direct-main write, or self-approval is authorized.

## Remaining lifecycle boundaries

A protected source merge does not prove production activation. Separate deployment evidence is required for:

- applying the migrations to the intended production database;
- binding the production application login to `a11oy_memory_app`;
- binding the production worker login to `a11oy_memory_worker`;
- proving production RLS behavior through the real application connection path;
- proving durable worker leasing and receipt generation under production load;
- recording immutable deployment and rollback receipts.

Until those steps occur, the truthful state is **source-qualified database contract, not production-deployed memory service**.
