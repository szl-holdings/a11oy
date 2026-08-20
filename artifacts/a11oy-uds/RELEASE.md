# Cutting an A11oy.UDS release

This bundle ships as a tagged GitHub release on
[`szl-holdings/a11oy`](https://github.com/szl-holdings/a11oy/releases).

## One command

From the repo root, with `zarf`, `cosign`, and `zstd` available
(`.local/bin/{cosign,zarf}` in this repl):

```bash
# 1. Bump artifacts/a11oy-uds/package.json version if you're cutting a new tag.

# 2. Build + sign all UDS bundles (runs scripts/release/uds-release.sh).
COSIGN_KEY=.local/cosign/cosign.key COSIGN_PASSWORD="" \
  bash scripts/release/uds-release.sh

# 3. Publish to the per-product repo (idempotent — replaces an existing tag).
node scripts/release/publish-github-release.mjs a11oy-uds
```

`DRY_RUN=1 node scripts/release/publish-github-release.mjs a11oy-uds` plans
the upload without touching GitHub.

## What gets uploaded

For tag `uds-v<VERSION>` (taken from `package.json`), the publisher uploads
every file in `dist/a11oy-uds/`:

- `a11oy-uds-<VERSION>.tar.zst` — Zarf package
- `a11oy-uds-<VERSION>.tar.zst.sha256` — sha256 sidecar
- `a11oy-uds-<VERSION>.tar.zst.sig` — cosign signature
- `a11oy-uds-dev.pub` — cosign public key for verification

## Verify from the public URL

After publishing, smoke-test exactly what an air-gap operator sees:

```bash
bash .local/smoke-runner.sh
```

See `.agents/memory/a11oy-uds-release-flow.md` for the full history of
why each step exists (build/sign separation, deterministic-tar flags,
extensionless-ESM-import sed, etc.).
