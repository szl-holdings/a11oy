# A11oy UDS Payload

A single-command, signed, declaratively-deployable A11oy payload for
**Defense-Unicorns (UDS)** environments. Drop it into a UDS bundle and run one
`zarf package deploy` — no bespoke installer, no per-environment glue.

The build emits `dist/a11oy-uds/a11oy-uds-<version>.tar.zst` containing:

- Built `@a11oy/core` runtime (orchestration kernel)
- Built `@a11oy/connection` transport layer
- `MANIFEST.json` — per-file `sha256`, size, build timestamp, git SHA
- Either a `cosign` signature (`*.tar.zst.sig`) when `COSIGN_KEY` is set, or
  an unsigned `*.tar.zst.sha256` sidecar otherwise

## Prerequisites

| Tool     | Min version | Required for                            |
| -------- | ----------- | --------------------------------------- |
| `node`   | 18+         | Manifest generation and verification    |
| `tar`    | any         | Fallback packaging when `zarf` missing  |
| `zstd`   | any         | Fallback packaging when `zarf` missing  |
| `zarf`   | 0.36+       | Native Zarf package creation/deploy     |
| `cosign` | 2+          | Signing (only when `COSIGN_KEY` is set) |

The build is **strict by default**: it always runs `tsc` for both packages
and refuses to produce a payload if either build is empty. Setting
`A11OY_UDS_ALLOW_SOURCE_FALLBACK=1` permits dev-only source packaging
(records `sourcePackaged: true` in `MANIFEST.json`) — never use this for
release output.

If `zarf` is unavailable, the build still produces a deterministic
`.tar.zst`, **but writes it to a clearly-separated `dist/a11oy-uds-fallback/`
directory with a `.fallback.tar.zst` suffix.** That fallback is NOT a Zarf
package and cannot be deployed via `zarf package deploy`; it exists so CI
can still validate the manifest/sign path without the `zarf` binary.

If `cosign` is missing (or `COSIGN_KEY` is unset), the build writes an
unsigned `.sha256` sidecar instead of a `.sig`.

## Build

From the repo root:

```bash
pnpm --filter @workspace/a11oy-uds run build
# or, directly:
bash artifacts/a11oy-uds/scripts/build.sh
```

To sign the output:

```bash
export COSIGN_KEY=cosign.key   # path to your cosign private key
bash artifacts/a11oy-uds/scripts/build.sh
```

Output:

- With `zarf`: `dist/a11oy-uds/a11oy-uds-<version>.tar.zst` (+ `.sig` or `.sha256`)
- Without `zarf` (dev only): `dist/a11oy-uds-fallback/a11oy-uds-<version>.fallback.tar.zst`

## Verify

The build runs `scripts/verify-manifest.mjs` automatically and refuses to
produce a tarball if any file's `sha256` does not round-trip. To re-verify on
demand (e.g. after unpacking):

```bash
pnpm --filter @workspace/a11oy-uds run verify
# or against an unpacked tarball:
node artifacts/a11oy-uds/scripts/verify-manifest.mjs /path/to/unpacked
```

If `cosign` was used to sign, verify the signature with the matching public
key:

```bash
cosign verify-blob \
  --key cosign.pub \
  --signature a11oy-uds-<version>.tar.zst.sig \
  a11oy-uds-<version>.tar.zst
```

Otherwise verify the unsigned sidecar:

```bash
cd dist/a11oy-uds && sha256sum -c a11oy-uds-<version>.tar.zst.sha256
```

## Operator runbook

### Deploy

```bash
zarf package deploy a11oy-uds-<version>.tar.zst --confirm
```

This stages the three declared components (`a11oy-core`,
`a11oy-connection`, `a11oy-provenance`) under `/opt/a11oy/` on the target
node.

### Inspect

Before deploy (or any time after), list components, images, and metadata:

```bash
zarf package inspect a11oy-uds-<version>.tar.zst
```

This emits the parsed `zarf.yaml`, the SBOM (if produced by Zarf), and the
per-file sha256 manifest baked into the payload.

### Rollback

```bash
# Remove the deployed package by name (matches metadata.name in zarf.yaml):
zarf package remove a11oy-uds --confirm

# Then re-deploy the previous known-good tarball:
zarf package deploy a11oy-uds-<previous-version>.tar.zst --confirm
```

Because every release ships with a content-addressed `MANIFEST.json` and
either a cosign signature or sha256 sidecar, you can always confirm that the
tarball you're rolling back to is bit-for-bit the one you originally
released.

## Attestation chain (optional component)

The `a11oy-attestations` Zarf component (optional, off by default) ships
a second sidecar — `ATTESTATIONS.json` — alongside `MANIFEST.json`. Where
`MANIFEST.json` is a flat per-file sha256 manifest, `ATTESTATIONS.json`
is a hash-chained provenance record over the *built subjects*
(`a11oy-core`, `a11oy-connection`). It is what the top-level
`szl-mesh` UDS bundle references as
`optionalComponents: [a11oy-attestations]`, and it is what enables
**offline** verification — no registry round-trip, no transparency log.

### Format

```jsonc
{
  "name": "a11oy-attestations",
  "version": "0.1.0",
  "gitSha": "abc1234",
  "builtAt": "2026-05-26T00:00:00Z",
  "hashAlgorithm": "sha256",
  "manifestSha256": "<sha256 of MANIFEST.json bytes>",
  "subjects": ["a11oy-core", "a11oy-connection"],
  "chain": [
    {
      "index": 0,
      "subject": "a11oy-core",
      "fileCount": 42,
      "totalBytes": 123456,
      "subjectSha256": "<digest of canonical subject lines>",
      "prevHash": "0000…0000",          // 64 zeros — genesis
      "entryHash": "<sha256 of link>"
    },
    {
      "index": 1,
      "subject": "a11oy-connection",
      "fileCount": 17,
      "totalBytes": 65432,
      "subjectSha256": "<digest>",
      "prevHash": "<chain[0].entryHash>",
      "entryHash": "<sha256 of link>"
    }
  ],
  "head": "<chain[N-1].entryHash>"
}
```

The subject digest is `sha256` of the canonical line-stream
`"<relPath>\t<sha256>\t<size>\n"` for every `MANIFEST.json` file under
`<subject>/`, sorted by `relPath`. The link hash is
`sha256("<index>\n<subject>\n<subjectSha256>\n<prevHash>\n")`. `prevHash`
for `index = 0` is 64 zeros (genesis). The terminal `head` field is the
last link's `entryHash`, so a verifier only needs to trust `head` to
trust the whole chain.

This is a **hash chain only** — there is no cryptographic signature on
the chain itself. Signing is handled by the existing cosign sidecar at
the tarball level; signing the chain head is intentionally out of scope.

### Verify

The build runs the verifier automatically and refuses to produce a
tarball if any link is broken. To re-verify on demand:

```bash
pnpm --filter @workspace/a11oy-uds run verify:attestations
# or against an unpacked deploy target (MANIFEST.json + ATTESTATIONS.json
# side by side under /opt/a11oy/ once both components are deployed):
node artifacts/a11oy-uds/scripts/verify-attestations.mjs \
  /opt/a11oy /opt/a11oy
```

### Opt in at deploy time

Because the component is `required: false` and `default: false`, a plain
`zarf package deploy` will skip it. Either opt in explicitly:

```bash
zarf package deploy a11oy-uds-<version>.tar.zst \
  --components a11oy-core,a11oy-connection,a11oy-provenance,a11oy-attestations \
  --confirm
```

…or deploy the parent `szl-mesh` UDS bundle, which lists
`a11oy-attestations` under `optionalComponents` for the `a11oy` package.

## Layout

```
artifacts/a11oy-uds/
├── README.md
├── package.json              # @workspace/a11oy-uds (build + verify scripts)
├── zarf.yaml                 # Zarf v1 package definition
├── scripts/
│   ├── build.sh              # End-to-end build + sign/sidecar pipeline
│   ├── write-manifest.mjs    # Generates MANIFEST.json
│   └── verify-manifest.mjs   # Re-hashes every file; fails on mismatch
└── build/                    # (generated) staged payload + MANIFEST.json
```

Build output lives at `dist/a11oy-uds/` at the repo root.

## Registry

Each tagged release (`v*.*.*`) is published to GitHub Container Registry as an
OCI artifact by the `Publish A11oy UDS payload` workflow
(`.github/workflows/a11oy-uds-publish.yml`):

| Channel | Coordinates                                          | Signed                  | When                       |
| ------- | ---------------------------------------------------- | ----------------------- | -------------------------- |
| release | `oci://ghcr.io/szl-holdings/a11oy-uds:<version>`     | yes (cosign keyless)    | push of a `v*.*.*` tag     |
| release | `oci://ghcr.io/szl-holdings/a11oy-uds:latest`        | yes (cosign keyless)    | tracks latest release      |
| dev     | `oci://ghcr.io/szl-holdings/a11oy-uds:dev-<sha>`     | no                      | push to `main`/`master`    |
| dev     | `oci://ghcr.io/szl-holdings/a11oy-uds:dev`           | no                      | tracks latest `main` build |

Pull a release by name + version:

```bash
zarf package pull oci://ghcr.io/szl-holdings/a11oy-uds:0.1.0
zarf package deploy zarf-package-a11oy-uds-*.tar.zst --confirm
```

Verify the cosign signature (release channel only) against the published
digest:

```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/szl-holdings/.+/\.github/workflows/a11oy-uds-publish\.yml@.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/szl-holdings/a11oy-uds:0.1.0
```

For pre-release testing, the unsigned dev channel publishes on every push to
`main`:

```bash
zarf package pull oci://ghcr.io/szl-holdings/a11oy-uds:dev
```

The release workflow also attaches the raw `*.tar.zst`, `*.sig`, and `*.sha256`
sidecars to the corresponding GitHub Release for air-gapped operators who
cannot reach GHCR.

## Out of scope

- Publishing to non-OCI registries (S3, Artifactory, etc.)
- Authoring Helm charts beyond what `zarf package create` consumes
- Deploy-time secrets management — UDS operators handle that out-of-band
