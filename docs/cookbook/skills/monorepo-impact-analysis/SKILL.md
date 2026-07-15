<!-- VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — .agents/skills/monorepo-impact-analysis/SKILL.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
---
name: monorepo-impact-analysis
description: Analyze the blast radius of a proposed change across this pnpm monorepo before implementing it. Use before any edit that touches a shared package, a public API, a database schema, or a route. Adapted from Claude Agent Blueprints monorepo patterns.
---

# Monorepo Impact Analysis

Before making a change that could ripple across packages, map the full impact surface. This prevents broken builds, surprise regressions, and incomplete migrations.

## Step 1 — Locate the Change Point

Identify the exact file(s) and exported symbol(s) that will change.

```bash
# Find all files that import the symbol
grep -r "symbolName" --include="*.ts" --include="*.tsx" -l

# Find all packages that depend on the package being changed
grep -r "\"@szl/shared\"" packages/*/package.json artifacts/*/package.json
```

## Step 2 — Classify the Change

| Type | Risk | Action |
|------|------|--------|
| Internal implementation (not exported) | Low | Change freely, run local tests |
| Exported type or interface | Medium | Check all consumers, update in one PR |
| REST/GraphQL API route shape | High | Run `api-contract-review` first |
| Database schema | High | Write a migration, coordinate with API layer |
| Shared UI component props | Medium | Grep all usages, update call sites |
| Environment variable or config key | High | Update `.env.example` and deployment docs |

## Step 3 — Build the Impact Map

List every artifact and package affected:

```
Changed: packages/shared/src/utils/formatDate.ts
Consumers:
  - artifacts/szl-holdings (direct import)
  - artifacts/command (via @szl/shared re-export)
  - artifacts/pulse (via @szl/shared re-export)
  - artifacts/api-server (direct import)
Risk: Medium — pure utility, no side effects, tests exist
```

## Step 4 — Order the Changes

For multi-package changes, always update in dependency order:
1. Shared libraries first (e.g., `packages/shared`)
2. API server second (if it consumes the shared lib)
3. Web/mobile artifacts last (they consume the API)

Never update consumers before the provider is updated and built.

## Step 5 — Verify

After changes:
```bash
pnpm --filter <changed-package> build
pnpm tsc --noEmit
pnpm lint
```

Check that no artifact's dev server shows a module-not-found error.

## Red Flags That Require a Pause

- The change touches `packages/shared/src/index.ts` (public API surface)
- The change modifies a Drizzle schema file
- The change renames or removes an API route
- The change modifies `artifact.toml` or `.replit`

For any red flag, consult `pre-flight-thinking` and get explicit confirmation before proceeding.
