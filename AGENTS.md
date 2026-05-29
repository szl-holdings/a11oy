# AGENTS.md

## Cursor Cloud specific instructions

### Repo Context

This is a **standalone subset** of the `szl-holdings/platform` monorepo. The `web/` directory (React SPA) cannot run standalone — it depends on 22+ `workspace:*` packages from the parent monorepo. The buildable/testable surface is the **standalone packages** and the **root-level test suites**.

### Running Tests

| Component | Command | Notes |
|-----------|---------|-------|
| `packages/a11oy-knowledge` | `cd packages/a11oy-knowledge && npm test` | Vitest. 26/27 pass (1 pre-existing failure in TH2 proof sketch). |
| `__tests__/` (compliance + adversarial) | `npx jest __tests__/` | Jest/ts-jest. 106/110 pass (4 pre-existing failures). Requires root-level symlinks — see below. |
| `packages/qec-integrity` | `npx tsx packages/qec-integrity/src/qec_lineage.test.ts` | Custom runner, `node:assert/strict`. 24/24 pass. |
| `web/packages/a11oy-core` (vitest) | `cd web/packages/a11oy-core && npx vitest run` | Only `lid-check.test.ts` uses vitest API (15 tests). |
| `web/packages/a11oy-core` (custom) | `npx tsx web/packages/a11oy-core/src/<subdir>/__tests__/<file>.test.ts` | 7 test files use `node:assert/strict` custom runners: quaternion-state (16), madhava-bound (8), pac-bayes-bound (8), composition-ring (7), false-position (7), akhmim-table (9), quadratic-solver (7). Run each with `npx tsx`. |
| `web/packages/a11oy-core` (KS-18) | `npx tsx web/packages/a11oy-core/src/quantum/__tests__/kochen-specker-18.test.ts` | 3 tests. |

### Symlinks Required for `__tests__/`

The compliance/adversarial Jest tests reference files via relative paths from `__tests__/compliance/`:
- `../../a11oy-knowledge.schema.json` → must exist at repo root
- `../../policies/vertical` → must exist at repo root

These are set up by the update script as symlinks to `packages/knowledge/`:
```
ln -sf packages/knowledge/a11oy-knowledge.schema.json a11oy-knowledge.schema.json
mkdir -p policies
ln -sf ../packages/knowledge/vertical policies/vertical
```

### Benchmarks

- `npx tsx packages/measurement/composition_overhead.ts` — Λ-axis composition latency
- `npx tsx packages/measurement/merkle_dag_p50.ts` — Merkle DAG write latency

### Known Limitations

- **`web/` SPA cannot start**: depends on `workspace:*` packages and `vite.config.ts` from the parent monorepo.
- **`packages/a11oy-knowledge` build (`tsc`) fails**: pre-existing type errors (e.g., `import assert`, `ProposedAxiom` schema mismatches). Tests still pass via vitest.
- **`web/packages/a11oy-core` and `a11oy-connection` build (`tsc`) fails**: `tsconfig.json` extends `../../../../tsconfig.base.json` which only exists in the parent monorepo. A stub at `/tsconfig.base.json` is needed for vitest (handled by setup).
- **No root `pnpm-workspace.yaml` or `pnpm-lock.yaml`**: this repo uses npm for per-package installs.
- **No linting**: `biome lint` is configured in `web/package.json` but requires the parent monorepo's biome.json and Vite setup.
