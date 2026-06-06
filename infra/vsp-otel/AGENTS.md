# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

vsp-otel is a TypeScript OpenTelemetry span exporter that adds governance/compliance (Λ-axis) signing to observability spans. It runs as an HTTP server on port 3004 (configurable via `VSP_PORT`).

### Workspace setup (already handled by the update script)

This repo is designed as a leaf package in the `szl-holdings/platform` monorepo. The two `workspace:*` dependencies (`@szl/ouroboros-lambda-gate` and `@szl/ouroboros-types`) are provided as local stubs under `stubs/`. A root `pnpm-workspace.yaml` ties them together.

### Key commands

| Action | Command |
|--------|---------|
| Install deps | `pnpm install` (from root) |
| Lint | `pnpm lint` |
| Test | `pnpm test` |
| Build | `pnpm build` |
| Run server | `cd runtime && VSP_PORT=3004 node dist/server.js` |

### Non-obvious gotchas

- **TypeScript 6 `types` default:** TS6 defaults `types` to `[]`. The `runtime/tsconfig.json` must include `"types": ["node"]` for Node.js globals (`process`, `Buffer`, etc.) to be available during compilation.
- **pnpm install in CI:** When pnpm detects a node_modules layout change requiring purge, it refuses in non-TTY environments unless `CI=true` is set. The update script sets this.
- **Stub packages:** The `stubs/ouroboros-lambda-gate` and `stubs/ouroboros-types` packages provide working implementations of the upstream workspace dependencies. They implement the full gate-evaluation logic (weighted axis scoring with threshold 0.85) and in-memory receipt storage.
- **ESLint warnings:** The existing code produces unused-import warnings (types imported for type-only use but not recognized by the flat parser). These are warnings only, not errors.
