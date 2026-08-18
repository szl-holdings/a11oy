# Proof Packet — Memory Covenant runtime boundary

Date: 2026-08-17  
Branch: `codex/p0-a11oy-work-20260811`

## Purpose

This packet records the source/runtime integration of the PostgreSQL-authoritative Memory Covenant. It supplements the isolated Neon schema proof; it does not relabel that isolated database as production.

## Runtime implementation

- `routers/memory_covenant.py`
  - registers `GET /api/a11oy/v1/memory-covenant/status` and `POST /api/a11oy/v1/memory-covenant/query`;
  - requires an externally managed `A11OY_MEMORY_DATABASE_URL` without exposing its value;
  - loads `psycopg` only when the runtime is explicitly configured;
  - starts every database operation as read-only;
  - rejects superuser and `BYPASSRLS` principals;
  - requires membership in `a11oy_memory_app`;
  - verifies `memory_records` exists with RLS and FORCE RLS enabled;
  - sets tenant and security-domain context transaction-locally before querying;
  - returns bounded metadata only, never `record_json` content;
  - creates no receipt merely because data was read;
  - exposes no public memory write, outbox lease, index-worker, provider, or credential route.
- `routers/frontier_reads.py`
  - registers the controller through the existing guarded pre-SPA-catch-all seam.
- `tests/test_memory_covenant_runtime.py`
  - covers safe and unsafe principal identities, no-configuration refusal, transaction-local scope, metadata-only results, input bounds, duplicate fields, non-finite JSON, and idempotent registration.
- `tests/test_memory_covenant_route_wiring.py`
  - boots the assembled application and proves the status/query paths are present while write/worker/index paths remain absent.
- `.github/workflows/memory-covenant-runtime.yml`
  - uses immutable action revisions, hash-locked Python dependencies, compile/tests, migration-authority assertions, and scoped whitespace validation.

## Activation truth

Current source disposition: `APPLIED / EXACT_HEAD_CI_PENDING`.

A deployed runtime becomes `READY` only when an approved secret manager supplies the database URL, the PostgreSQL driver is installed, the login is a non-bypass member of `a11oy_memory_app`, and the covenant schema/RLS checks pass. Otherwise the public status remains an honest `UNAVAILABLE` or `BLOCKED` response.

The source change does not install a database credential, add a public mutation endpoint, activate the index worker, call an embedding provider, deploy to Hugging Face, or merge protected main.

## Prior database evidence

The isolated Neon acceptance target remains:

- Project: `young-snow-70923323`
- Branch: `br-bitter-block-a6kuzqxt`
- Database: `neondb`

The earlier packet recorded schema application, non-bypass role qualification, same-domain visibility, cross-domain denial, append-only receipt enforcement, and rollback residue of zero. That evidence proves database-contract feasibility only.

## Rollback

Revert the commits adding or modifying:

- `routers/memory_covenant.py`
- `routers/frontier_reads.py`
- `routers/__init__.py`
- `tests/test_memory_covenant_runtime.py`
- `tests/test_memory_covenant_route_wiring.py`
- `.github/workflows/memory-covenant-runtime.yml`
- this packet

The database migration is separately reversible through the governed database migration process; this runtime integration does not mutate database state by itself.
