# NOTE: npm vs pnpm — workspace:* Protocol

**Authored:** 2026-05-31, Hampichiq (sandbox-cert remediation)  
**Context:** Sandbox cert report F-06 — `npm install` in `web/` fails with
`EUNSUPPORTEDPROTOCOL: Unsupported URL Type "workspace:": workspace:*`

## Root cause

`web/package.json` uses `workspace:*` syntax for internal SZL packages
(e.g., `@szl-holdings/analytics`, `@szl/alloy`). This is pnpm workspace
syntax. When `npm install` is run in `web/` standalone, npm does not
understand this protocol.

## Why pnpm, not npm

The project uses pnpm workspaces. The `workspace:*` dependencies are
internal packages from the SZL Holdings monorepo. They do not exist as
published npm packages. Converting them to pinned npm versions is not
possible — they are unpublished, internal.

The correct install command for this repo is:

```bash
# From the repo root:
pnpm install
```

Not `npm install`.

## What this PR adds

This PR adds:
1. `pnpm-workspace.yaml` at root — declares the workspace structure
   (`web/`, `runtime/*`, `stubs/*`) and the `catalog:` version pins for
   external dependencies.
2. `package.json` at root — marks the root as a private workspace package,
   needed for pnpm to recognise the workspace root.

With these two files present, `pnpm install` from the root will resolve all
`workspace:*` deps correctly by linking them to the local packages directory.

## Why the dual-use tests still pass without pnpm install

The dual-use tests (`web/src/lib/dual-use/__tests__/`) have no dependencies
on the `workspace:*` internal packages. They only import `../dual-use-detector`
(same directory) and use vitest. Vitest is installed globally in the CI
environment (`/usr/local/bin/vitest`). So the 4 → 21 dual-use tests run
cleanly without a full `web/` install.

The `workspace:*` blocker only affects the full web stack
(`safety-gate.test.ts`, `risk.test.ts`, React components). Those tests
require a pnpm workspace install from root.

## Remaining gap

The `@szl-holdings/*` and `@workspace/*` packages referenced in
`web/package.json` are internal monorepo packages. They need to exist as
subdirectories under the pnpm workspace root (or be replaced with published
versions). Until those packages are present in this repo's workspace
structure, `pnpm install` will still report unresolvable workspace deps.

**This is a known gap, not introduced by this PR.** It was present before
this remediation. The fix in this PR (adding `pnpm-workspace.yaml`) is the
correct structural foundation; completing the workspace requires either
publishing the internal packages or adding them as workspace members.

## Decision record

- Do NOT convert `workspace:*` to pinned npm versions — these are internal packages.
- Do NOT remove `workspace:*` deps — they are real runtime dependencies.
- ADD `pnpm-workspace.yaml` — this is the correct pnpm workspace declaration.
- DOCUMENT this file — so the next sandbox-cert run understands what changed.

*SZL Holdings · Apache-2.0 · Doctrine v7 · Hampichiq*
