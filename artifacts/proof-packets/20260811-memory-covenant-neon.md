# Memory Covenant — isolated Neon proof packet

Date: 2026-08-11

## Scope

This packet records source-independent database acceptance evidence for the governed memory schema added in `migrations/20260811_memory_covenant_v2.sql`.

The database used for this proof is an isolated Neon project created specifically for Memory Covenant qualification. It is not the unrelated existing production project and no production deployment claim is made.

## Observed target

- Neon project ID: `young-snow-70923323`
- Branch ID: `br-bitter-block-a6kuzqxt`
- Database: `neondb`
- PostgreSQL schema: `public`

No connection string, password, token, or signing secret is stored in this packet.

## Migration outcome

The schema transaction completed successfully through Neon using individual statements in one database transaction.

Observed authoritative tables:

- `memory_records`
- `memory_evidence_refs`
- `memory_outbox`
- `memory_receipts`
- `memory_query_audit`
- `memory_index_generations`
- `memory_idempotency`

## Isolation and append-only controls

Post-migration catalog verification observed:

| Table | RLS enabled | FORCE RLS | Policies | User triggers |
|---|---:|---:|---:|---:|
| memory_records | yes | yes | 1 | 1 |
| memory_evidence_refs | yes | yes | 1 | 0 |
| memory_outbox | yes | no | 1 | 1 |
| memory_receipts | yes | yes | 1 | 1 |
| memory_query_audit | yes | yes | 1 | 1 |
| memory_index_generations | yes | yes | 1 | 0 |
| memory_idempotency | yes | yes | 1 | 1 |

The non-FORCE posture on `memory_outbox` is intentional for a separately controlled worker path. Application principals must not own the tables. Worker privilege and lease-function qualification remain a separate runtime acceptance gate before worker activation.

## Honest status

`DATABASE_SCHEMA_APPLIED_AND_CATALOG_VERIFIED`

This proves that the PostgreSQL covenant schema can be installed on the isolated target and that the expected RLS/policy/trigger objects exist. It does **not** prove application runtime wiring, worker-role membership, vxdb indexing, end-to-end API behavior, production deployment, or protected-main promotion.

## Next protected gates

The implementation branch must still pass repository CI, exact-head review, signed+DCO successor normalization, protected merge, deployment, and exact revision readback before any production-complete label is valid.
