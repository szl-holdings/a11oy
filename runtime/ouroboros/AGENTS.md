# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Ouroboros is a bounded-loop runtime implementing the Lutar Invariant (Λ). It consists of:

- **Root package** (`src/`, `packages/`) — Core loop kernel, consistency, depth allocator, React trace UI, and governance packages
- **Runtime modules** (`runtime/`) — Scoped packages: types, lambda-gate, bekenstein, closure, category, glr
- **Agentic layer** (`agentic/`) — MCP server, a11oy-core orchestrator, formulas library, bot-reviewer

### Running tests

- **Primary test suite**: `pnpm test` at root (runs 218 tests covering `src/` and `packages/`)
- **Agentic tests**: `cd agentic && pnpm test` (43 tests)
- **Runtime/types**: `cd runtime/types && pnpm test` (standalone, no workspace deps)
- **Other runtime packages** (lambda-gate, bekenstein, glr, category, closure): require `@szl/ouroboros-types` built first (`cd runtime/types && npx tsc`), then symlinked into each package's `node_modules/@szl/ouroboros-types`. Lambda-gate must also be built (`cd runtime/lambda-gate && npx tsc`) before closure/category tests can run.

### Lint and typecheck

- `pnpm lint` — runs Biome on `src/`
- `pnpm typecheck` — runs `tsc --noEmit` against root tsconfig

### Running services

- **MCP Server** (port 8090): `cd agentic && npx tsx mcp-server/src/index.ts`
  - Healthcheck: `GET /healthz`
  - Tools listing: `GET /tools`
  - Call tool: `POST /call/<tool_name>`
- **Lambda-Gate receipt server** (port 3001): `cd runtime/lambda-gate && npx tsx src/server.ts`
  - Requires runtime/types to be built first
  - Submit receipt: `POST /receipts` (full Receipt object with hash, timestamp, lambda, axes, payloadRef)
  - Retrieve: `GET /receipts/:hash`
  - Verify: `POST /verify`

### Gotchas

- The runtime sub-packages use `workspace:*` protocol but there is no `pnpm-workspace.yaml`. Root `pnpm install` only installs root deps. Runtime packages need manual symlink setup (copy node_modules from types, then symlink `@szl/ouroboros-types` and `@szl/ouroboros-lambda-gate`).
- The agentic `package.json` has a `"workspaces"` field (npm format) that pnpm warns about but the tests still pass because vitest resolves relative paths.
- MCP server uses relative file imports (`../../formulas/src/index.js`) so it works with `npx tsx` without needing workspace resolution.
- The `route` MCP tool requires `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` env vars; without them it falls back to stub mode.
- Node.js >= 20 required (v22 recommended); pnpm 10.26.1 is the pinned package manager.
- `esbuild` build scripts may be "ignored" by pnpm — this is fine for development; the test suites and servers work without esbuild native binaries.
