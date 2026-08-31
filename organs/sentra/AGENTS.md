# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a satellite repo extracted from the `szl-holdings/platform` monorepo. It contains:

- **`web/`** — React 19 + Vite + TypeScript SPA (Sentra Cyber Resilience Command dashboard)
- **`runtime/confluence/`** — TypeScript library implementing Church-Rosser confluence for replay paths
- **`runtime/doi-bind/`** — TypeScript library for DOI manifest building from receipt chains
- **`src/*.py`** — Python utility scripts (threat signature scanner, replay verifier)

### Key Architecture Note

The `web/` SPA has ~30 `workspace:*` dependencies that normally come from the parent monorepo. This dev environment uses **stub packages** in `stubs/` to satisfy those dependencies. The stubs provide:
- No-op React components (render children or null)
- Minimal hook implementations returning expected shapes
- Empty data arrays for data layer stubs

### Running Services

| Command | What it does |
|---------|-------------|
| `pnpm --filter @workspace/sentra dev` | Starts Vite dev server on port 5173 at `/sentra/` |
| `pnpm --filter @workspace/sentra test` | Runs vitest (48 tests, 1 pre-existing failure in `hard-block-coverage.test.ts`) |
| `pnpm --filter @workspace/sentra lint` | Runs biome lint on `web/src/` |
| `pnpm --filter @szl/sentra-confluence test` | Runs confluence package tests (6 tests) |
| `pnpm --filter @szl/sentra-doi-bind test` | Runs doi-bind package tests (8 tests) |
| `pnpm --filter @szl/sentra-confluence build` | TypeScript build for confluence |
| `pnpm --filter @szl/sentra-doi-bind build` | TypeScript build for doi-bind |

### Gotchas

- **pnpm 11 supply-chain policy**: Fresh lockfile entries can fail `pnpm install` with `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`. On Cursor Cloud VMs, set user config once: `pnpm config set minimumReleaseAge 0 --location user` (persists in `~/.config/pnpm/config.yaml`).
- **pnpm 11 build scripts**: Vite needs `esbuild` postinstall scripts. Either add `allowBuilds: { esbuild: true }` to `pnpm-workspace.yaml` (run `pnpm approve-builds esbuild`), or set `pnpm config set strictDepBuilds false --location user` so install completes with a warning (prebuilt esbuild binaries usually still work for dev).
- **Lint script vs Biome version**: `pnpm --filter @workspace/sentra lint` uses `web/biome.json` (Biome 1.x schema) while the repo root installs Biome 2.4 — the script fails on unknown keys like `files.ignore`. Align configs or run lint from a matching Biome version until fixed upstream.
- **`typecheck` script**: `pnpm --filter @workspace/sentra typecheck` expects `tsc` on PATH; `typescript` is not declared in `web/package.json` in this satellite repo, so typecheck may fail until added.
- **Production `build`**: `pnpm --filter @workspace/sentra build` can fail on missing stub exports (e.g. `useStandardQuery` from `@szl-holdings/api-client-react`). Dev server (`pnpm dev`) is the supported local workflow here.
- **Pre-existing test failure**: `web/src/lib/dual-use/__tests__/hard-block-coverage.test.ts` has 1 failing test (`permitted context downgrades the gate...`) — this is a logic bug in the existing code, not a setup issue.
- **Stub limitations**: The web app renders with stub dependencies. Pages that rely heavily on API data will show error messages or empty states. Navigation and routing work correctly.
- **No API server**: The Express 5 API server (`@workspace/api-server`) lives in the parent monorepo. Pages will show "failed to fetch" errors — this is expected.
- **Tailwind CSS**: The `index.css` has `@source` directives pointing to monorepo paths that don't exist here. Tailwind still works for local classes.
- **`web/src/lib/theme.ts`**: Contains JSX in a `.ts` file (should be `.tsx`). Biome is configured to skip this file.
- **Python**: Scripts in `src/` use only stdlib modules. No `requirements.txt` needed.
- **Node.js**: Uses Node 22 (per Dockerfile). pnpm is the package manager.
