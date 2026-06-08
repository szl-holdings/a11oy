<!--
Copyright 2026 SZL Holdings
SPDX-License-Identifier: Apache-2.0
-->

# Offline quickstart — no registry auth

sentra depends on several private `@szl-holdings/*` packages that are published
to GitHub Packages. A fresh clone cannot fetch them without a `NODE_AUTH_TOKEN`,
so a plain `pnpm install` followed by `pnpm test` can fail with
`ERR_PNPM_FETCH_401` on, for example, `@szl-holdings/a11oy-policy` or
`@szl-holdings/a11oy-receipt-substrate`.

This repository already ships local **workspace stubs** for every one of those
packages under [`stubs/`](../stubs). Because the consuming packages reference
them as `workspace:*`, pnpm links the stubs directly and the suite runs fully
offline — no token required.

## Run it

The reliable entry point is the script directly (it sets the pnpm flags before
pnpm evaluates them):

```bash
bash scripts/offline-quickstart.sh test    # web safety-gate suite (vitest), no auth
bash scripts/offline-quickstart.sh build   # build the web app, no auth
bash scripts/offline-quickstart.sh dev      # start the web dev server, no auth
```

Convenience aliases are also wired into the root `package.json`. Because pnpm
evaluates its dependency-status guard before running a script, invoke them with
the guard disabled:

```bash
PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:offline
```

The script [`scripts/offline-quickstart.sh`](../scripts/offline-quickstart.sh):

1. confirms the `a11oy-policy` and `a11oy-receipt-substrate` stubs are present;
2. defaults `NODE_AUTH_TOKEN` to empty so the `.npmrc` reference resolves
   without warning (the stubs satisfy the `@szl-holdings/*` names locally, so
   the authenticated registry is never contacted for them); and
3. sets `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false` so pnpm does not re-trigger
   an authenticated install before running the script.

## Expected output

```
── sentra offline quickstart (no registry auth) ──
  found stubs/szl-holdings-a11oy-policy
  found stubs/szl-holdings-a11oy-receipt-substrate

 Test Files  3 passed (3)
      Tests  48 passed (48)
```

## When you do have a token

If you have a `NODE_AUTH_TOKEN` for the SZL GitHub Packages registry, the
standard `pnpm install` / `pnpm --dir web test` path works as documented in the
top-level README. The offline path above is the fallback for guests and
air-gapped demos.

## A repo that installs with zero auth

If you want to see a fully green clone-and-build with no token at all, the
`rosie` repository has no private
dependencies and installs clean.
