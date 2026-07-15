<!-- VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — .agents/skills/typescript-refactor/SKILL.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
---
name: typescript-refactor
description: Systematic TypeScript refactoring patterns for this pnpm monorepo. Use when extracting shared logic, improving type safety, eliminating any/unknown casts, or restructuring modules across packages. Adapted from Awesome Claude Code TypeScript patterns collection.
---

# TypeScript Refactor

A disciplined approach to TypeScript refactoring in this monorepo. Always run `pre-flight-thinking` before starting.

## Before You Touch Anything

1. Run `pnpm tsc --noEmit` from the workspace root to establish a clean baseline.
2. Identify all consumers of the symbol you are changing: `grep -r "importedName" --include="*.ts" --include="*.tsx"`.
3. Check whether the file is re-exported from a package's public index (`index.ts`). If yes, the change is a public API change — treat it like `api-contract-review`.

## Core Patterns

### Extract a Shared Utility
When the same logic appears in ≥ 2 packages:
- Create the util in `packages/shared/src/utils/<name>.ts`.
- Export it from `packages/shared/src/index.ts`.
- Replace each site with the import.
- Keep the original file with a deprecation comment until all consumers are updated.

### Eliminate `any` and `unknown` Casts
- Replace `any` with the narrowest correct type or a well-named generic.
- Replace `as unknown as T` casts with a proper type guard function.
- Use `satisfies` (TS 4.9+) instead of `as` when validating literal objects against an interface.

### Narrow Union Types
- Prefer discriminated unions (`type Result = { ok: true; data: T } | { ok: false; error: string }`) over optional fields.
- Add an exhaustive `assertNever(x: never)` helper in shared utils and call it in `switch` default branches.

### Improve Return Types
- Avoid implicit `void` returns on async functions that callers might await.
- Annotate exported functions with explicit return types so signature changes cause compile errors at the call site.

## Monorepo-Specific Rules

- Never import from a sibling package's `src/` directly — only from its published package name (e.g., `@szl/shared`, not `../../packages/shared/src`).
- After refactoring a shared package, run `pnpm --filter <changed-package> build` before testing dependents.
- Update `CHANGELOG.md` in the package if the public API surface changes.

## Verification Checklist

- [ ] `pnpm tsc --noEmit` passes with zero new errors
- [ ] `pnpm lint` passes
- [ ] All callers of the changed symbol have been updated
- [ ] No `@ts-ignore` or `@ts-expect-error` was added without a comment explaining why
