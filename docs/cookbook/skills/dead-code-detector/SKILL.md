---
name: dead-code-detector
description: Find and safely remove dead code (unused exports, unreachable branches, stale feature flags, orphaned files) across the TypeScript/React monorepo. Use when doing a cleanup sprint, before a major refactor, or when bundle size needs reducing. Adapted from Antigravity Awesome Skills dead-code patterns.
---

# Dead Code Detector

Systematic process for locating and safely removing code that is no longer used. Always run `pre-flight-thinking` first — dead code removal can have surprising dependencies.

## Detection Techniques

### 1. Unused TypeScript Exports

Enable strict checks in `tsconfig.json` if not already set:
```json
"noUnusedLocals": true,
"noUnusedParameters": true
```

Then run:
```bash
pnpm tsc --noEmit 2>&1 | grep "is declared but"
```

### 2. Orphaned Files (Never Imported)

```bash
# Find .ts/.tsx files that are never imported by any other file
# Start with files that have no import references at all
grep -rL "from.*<filename-without-ext>" --include="*.ts" --include="*.tsx" src/
```

For a more thorough scan, use `ts-prune` or `knip`:
```bash
pnpm dlx knip --include files,exports,types
```

### 3. Unreachable Code Branches

Look for:
- `if (false)` or `if (0)` blocks
- Code after unconditional `return`, `throw`, or `continue`
- Switch cases that can never be reached given the union type

TypeScript surfaces some of these with `"allowUnreachableCode": false` in tsconfig.

### 4. Stale Feature Flags

Search for feature flag constants that are hardcoded to a final value:
```bash
grep -rn "FEATURE_FLAG\|featureFlag\|FF_\|isEnabled" --include="*.ts" --include="*.tsx"
```

If a flag is always `true` or always `false`, the conditional is dead.

### 5. Unused CSS / Tailwind Classes

For Tailwind: run `pnpm dlx tailwind-rg` or inspect the PurgeCSS output of the Vite build.

## Safe Removal Process

1. **Verify nothing imports the symbol** — grep across all packages including `artifacts/`.
2. **Remove the export** (not the whole file yet).
3. **Run `pnpm tsc --noEmit`** — a type error at a call site means it was used.
4. **If zero errors**, remove the file or function body.
5. **Run `pnpm lint`** to catch any residual references in config or test files.
6. **Commit as `refactor(<scope>): remove unused <description>`** for clean history.

## What NOT to Remove

- Symbols with `@public` or `@api` JSDoc tags — they may be used externally.
- Re-exports from a package's `index.ts` — they are part of the public API.
- Anything referenced by a string (e.g., dynamic imports, `require(variableName)`).
- Code guarded by `process.env.NODE_ENV` — it may be active in a different environment.
