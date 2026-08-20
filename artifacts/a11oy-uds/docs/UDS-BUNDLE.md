# a11oy — UDS Bundle integration

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

The Zarf package shipped here is a **first-class member** of a Defense
Unicorns (UDS) bundle. The shipped `uds-bundle.yaml` composes it as a
single-package bundle so an operator can run `uds deploy` end-to-end without
hand-writing any UDS YAML.

## Bundle definition

```yaml
kind: UDSBundle
metadata:
  name: a11oy
  description: |
    A11oy — governed execution fabric. Single-package UDS bundle that
    stages @a11oy/core, @a11oy/connection, provenance sidecars, and the
    v0.2 shared packages under /opt/a11oy/ on the target node via Zarf.
  version: 0.2.0
  authors: A11oy / SZL Holdings
  url: https://github.com/szl-holdings/a11oy
  architecture: multi

packages:
  - name: a11oy-uds
    path: ../../dist/a11oy-uds  # relative to artifacts/a11oy-uds/uds-bundle.yaml
    ref: 0.2.0
```

The `path:` form points at a locally-built Zarf tarball; once the package
publishes to OCI it can be switched to:

```yaml
packages:
  - name: a11oy-uds
    repository: ghcr.io/szl-holdings/a11oy-uds
    ref: 0.2.0
```

both forms are valid UDS-CLI syntax (uds-cli v0.27+).

## Build the bundle

```bash
# Prereq: Zarf v0.49+, uds-cli v0.27+, and a built a11oy-uds Zarf package
# (run artifacts/a11oy-uds/scripts/build.sh first).

cd artifacts/a11oy-uds
uds create . --confirm
```

This produces `uds-bundle-a11oy-<arch>-0.2.0.tar.zst` next to the
`uds-bundle.yaml`. The bundle tarball is self-contained — it embeds the
referenced Zarf package(s) and can be moved across an air-gap.

## Inspect the bundle

```bash
uds inspect uds-bundle-a11oy-<arch>-0.2.0.tar.zst
```

Expected output (abbreviated):

```
kind: UDSBundle
metadata:
  name: a11oy
  version: 0.2.0
packages:
  - name: a11oy-uds
    ref: 0.2.0
    description: A11oy — governed execution fabric ...
```

## Deploy the bundle

```bash
uds deploy uds-bundle-a11oy-<arch>-0.2.0.tar.zst --confirm
```

UDS-CLI delegates each `packages[*]` entry to `zarf package deploy` under
the hood — the on-node effect is identical to running `zarf package deploy
a11oy-uds-0.2.0.tar.zst --confirm` directly.

## Remove the bundle

```bash
uds remove a11oy --confirm
```

This invokes `zarf package remove a11oy-uds --confirm` for each package in
the bundle (in reverse order).

## Multi-package composition

The same `a11oy-uds` Zarf package can be added to a richer multi-product
bundle alongside `sentra` and `amaru`:

```yaml
kind: UDSBundle
metadata:
  name: plane-1
  version: 0.1.0
packages:
  - name: a11oy-uds
    repository: ghcr.io/szl-holdings/a11oy-uds
    ref: 0.2.0
  - name: sentra
    repository: ghcr.io/szl-holdings/sentra
    ref: <pinned>
  - name: amaru
    repository: ghcr.io/szl-holdings/amaru
    ref: <pinned>
```

That composition is the role of the existing `szl-holdings/uds-mesh` repo;
the `a11oy-uds` package is one of the three legs it composes.

## Compatibility matrix

| component           | tested-against version | notes                                              |
|---------------------|-----------------------:|----------------------------------------------------|
| Zarf CLI            | v0.49.0                | `zarf package create` + `zarf package deploy`      |
| UDS CLI             | v0.27.0                | `uds create`, `uds inspect`, `uds deploy`, `uds remove` |
| cosign              | v2.4.1                 | blob signing + keyless OIDC verify                 |
| Kubernetes (target) | package-dependent      | v0.2 stages runtime, provenance, attestations, and shared package artifacts under `/opt/a11oy/` |

v0.2.0 is an operator proof-point package: it stages the A11oy runtime,
provenance sidecars, optional attestations, and shared package artifacts. It is
not a Defense Unicorns endorsement or UDS catalog acceptance claim; use
`zarf package inspect` and the manifest/attestation verifiers before deploy.
