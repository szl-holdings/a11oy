# a11oy — Security & Provenance

## Threat surface

The shipped payload is **pure-functional TypeScript compiled to ESM
JavaScript**. It contains:

- No network code (no `fetch`, no `http`, no sockets).
- No filesystem code (no `fs`, no `child_process`).
- No `eval`, no dynamic `Function(...)` construction.
- No native bindings, no WASM modules.
- No third-party runtime dependencies (the `package.json` files declare
  zero `dependencies` blocks).

The runtime is consumed by a host process that supplies inputs and persists
outputs. The host process — not this payload — owns I/O, authentication,
and authorization.

## Build provenance

Every tarball ships a `MANIFEST.json` at its root with:

| field             | meaning                                                   |
|-------------------|-----------------------------------------------------------|
| `name`            | `a11oy-uds`                                               |
| `version`         | semver from `artifacts/a11oy-uds/package.json`            |
| `gitSha`          | short SHA of the source commit                            |
| `builtAt`         | ISO-8601 UTC build timestamp                              |
| `hashAlgorithm`   | always `sha256`                                           |
| `sourcePackaged`  | `false` on release builds (compiled `dist/`, not `src/`)  |
| `fileCount`       | total file count across both packages                     |
| `totalBytes`      | sum of `files[].size`                                     |
| `files[].path`    | path relative to `/opt/a11oy/`                            |
| `files[].size`    | byte length                                               |
| `files[].sha256`  | SHA-256 hex digest of the file                            |

The manifest is sorted by `path` so a re-run on the same inputs produces
byte-identical output. The build script (`artifacts/a11oy-uds/scripts/build.sh`)
refuses to package `src/` instead of `dist/` unless the operator explicitly
sets `A11OY_UDS_ALLOW_SOURCE_FALLBACK=1` — this is forbidden for release
output and the `sourcePackaged` field would surface the violation.

## Signature chain (dev channel — this hand-off)

```
a11oy-uds-<version>.tar.zst                 ← Zarf package (zstd-compressed tar)
a11oy-uds-<version>.tar.zst.sha256          ← GNU coreutils sha256 sidecar
a11oy-uds-<version>.tar.zst.sig             ← cosign blob signature (PEM-key)
a11oy-uds-dev.pub                           ← matching cosign public key
```

Verify:

```bash
sha256sum -c a11oy-uds-<version>.tar.zst.sha256
cosign verify-blob \
  --key a11oy-uds-dev.pub \
  --signature a11oy-uds-<version>.tar.zst.sig \
  a11oy-uds-<version>.tar.zst
```

The public key is also committed to source at
`artifacts/a11oy-uds/release-keys/a11oy-uds-dev.pub` so a verifier can pin to
the in-source copy rather than the bundled one.

Trust root: in-band hand-off + matching public key. Suitable for the dev
channel and direct operator delivery. **Not** suitable for ungated
download-and-deploy scenarios — use the release channel instead.

## Signature chain (release channel — GHCR + cosign keyless OIDC)

Once published from a `v*.*.*` git tag, the same byte-identical tarball is
pushed to `ghcr.io/szl-holdings/a11oy-uds:<version>` and signed via cosign
keyless OIDC against the GitHub Actions workflow identity. Verify:

```bash
# Identity regex matches whichever szl-holdings repo currently hosts the
# `a11oy-uds-publish.yml` workflow file. The workflow may live in
# `szl-holdings/platform` (monorepo) or `szl-holdings/a11oy` (extracted);
# both produce the same byte-identical tarball and a valid Fulcio cert.
cosign verify \
  --certificate-identity-regexp 'https://github.com/szl-holdings/.+/\.github/workflows/a11oy-uds-publish\.yml@.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/szl-holdings/a11oy-uds:<version>
```

Trust root: GitHub's OIDC issuer + the published workflow identity. Suitable
for any UDS / Zarf consumer with internet egress to the Sigstore Rekor +
Fulcio infrastructure.

## Determinism

The build is reproducible:

- Zarf produces a sorted tar with the package metadata canonicalised by the
  `zarf` binary (no operator-controlled fields leak in).
- The non-zarf fallback (development only) uses
  `tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="${BUILD_TS}"`
  followed by `zstd -19` so the output sha256 is fixed by the inputs and the
  build timestamp alone.

This is what makes cross-channel digest comparison meaningful: the dev
hand-off tarball and the GHCR-published tarball have **the same sha256** when
built from the same git SHA at the same `builtAt`.

## Key rotation

The dev-channel cosign key is project-managed. To rotate:

1. Generate a new keypair:
   `COSIGN_PASSWORD="" cosign generate-key-pair`
2. Update `artifacts/a11oy-uds/release-keys/a11oy-uds-dev.pub`.
3. Re-sign the existing tarball(s) and update the `.sig` sidecars.
4. Cut a new prerelease so consumers see the new key alongside the new
   signature.

The release-channel keyless OIDC signature has no static key to rotate — its
identity is tied to the GitHub Actions workflow file path and the repo SHA.

## Vulnerability surface

Because the runtime has zero third-party runtime dependencies and no I/O,
the dependency-derived vulnerability surface is empty. The development
dependencies used to **build** the runtime (TypeScript, etc.) do not ship to
the operator — they are pruned out of the `dist/` staging step.

SBOMs for the package are generated by Zarf at build time and can be
extracted post-hoc:

```bash
zarf package inspect sbom-extract a11oy-uds-<version>.tar.zst --output ./sbom
```

The extracted SBOM enumerates every staged file with size + sha256 and
flags any non-zero dependency entries. For v0.1.0 the dependency entry count
is zero.
