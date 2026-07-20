<!-- VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — artifacts/api-server/README.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
# artifacts/api-server — Canonical Express API

This is the **canonical Express HTTP transport** for the SZL Holdings platform.

**Reference:** `docs/architecture/architecture.md` v4 (April 2026) and `ops/frontier/repo-topology-map.md` both name `artifacts/api-server` as the single backend for all platform surfaces.

## Topology

```
Web artifacts (szl-holdings, command, vessels, terra, carlota-jo, pulse, aegis)
       ↓
artifacts/api-server  ←  the single API entrypoint
       ↓
lib/db (Drizzle) + lib/services (business logic) + lib/ai-engine + packages/*
```

Per the architecture v4 platform layer model:
- Command surfaces (Lyte, CORTEX, Command, Pulse, etc.) consume this API
- Execution fabric (Alloy / `lib/workflow-engine`) runs underneath
- Domain packs (Vessels, Terra, Carlota Jo, Sentra, Counsel) extend the shared core through this API

## Tech

- Express 5
- TypeScript 5.x
- Routes mounted from `src/routes/`
- Business logic delegated to `@workspace/ouroboros-integrations` and `lib/*`
- Port 8080 (mapped to 80 externally per `.replit` port registry)

## Other servers in the workspace

The platform also runs several specialized service-tier servers — these are NOT the public API, they are internal services consumed via `lib/services`:

- `apps/alloy-runtime-api` — internal AEEP runtime
- `apps/alloy-embedding-api` — embedding gateway
- `apps/alloy-ingestion-orchestrator` — ingestion control plane
- `services/substrate-mcp-gateway` — MCP transport
- `services/alloy-fabric-api` / `services/alloy-fabric-ingest-control`
- `workers/alloy-vector-worker` / `workers/alloy-rank-worker`
- `apps/eval-runner` (FastAPI), `apps/substrate-inference`

For new public API routes, add a route file under `src/routes/` here.

## Historical note

Earlier package.json description claimed "5,500+ endpoints across 11 product surfaces" — that count was an aspirational projection, not a verified figure. PR #242 corrected the description to neutral language. PR #241 incorrectly repointed `.replit` to `apps/alloy-runtime-api`; PR #248 restored the correct pointer here.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
