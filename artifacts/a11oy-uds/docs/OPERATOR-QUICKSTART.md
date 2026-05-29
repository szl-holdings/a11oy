# A11oy.UDS — Operator Quickstart

A11oy ships as a signed Zarf payload for UDS/Zarf-compatible operator
workflows. This quickstart walks an operator from "download tarball" to
package verification. Do not present fallback tarballs as deployable Zarf
packages.

## 1. Pull + verify

```bash
BASE=https://github.com/szl-holdings/a11oy/releases/download/uds-v0.2.0
curl -fsSLO $BASE/a11oy-uds-0.2.0.tar.zst
curl -fsSLO $BASE/a11oy-uds-0.2.0.tar.zst.sha256
curl -fsSLO $BASE/a11oy-uds-0.2.0.tar.zst.sig
curl -fsSLO $BASE/a11oy-uds-dev.pub

sha256sum -c a11oy-uds-0.2.0.tar.zst.sha256
cosign verify-blob \
  --key a11oy-uds-dev.pub \
  --signature a11oy-uds-0.2.0.tar.zst.sig \
  a11oy-uds-0.2.0.tar.zst
```

Both checks must print `OK` / `Verified OK` before deploying.

## 2. Inspect

```bash
zarf package inspect a11oy-uds-0.2.0.tar.zst
```

For an unpacked or deployed package, verify the payload sidecars directly:

```bash
node artifacts/a11oy-uds/scripts/verify-manifest.mjs /opt/a11oy
node artifacts/a11oy-uds/scripts/verify-attestations.mjs /opt/a11oy /opt/a11oy
```

The attestation chain binds five subjects: `a11oy-core`,
`a11oy-connection`, and three v0.2 shared packages
(`shared/perception-loop`, `shared/sequence-pipeline`,
`shared/sparse-attention-kit`).

## 3. Deploy

```bash
zarf package deploy a11oy-uds-0.2.0.tar.zst --confirm
```

The bundle lands under `/opt/a11oy/`:

```
/opt/a11oy/
├── a11oy-core/                # KS-18 contextuality witness, Fisher manifold, POVM verdicts
├── a11oy-connection/          # tetrad-field gauge connection
├── MANIFEST.json
├── ATTESTATIONS.json
└── shared/                    # v0.2 cross-cutting packages
    ├── perception-loop/
    ├── sequence-pipeline/
    └── sparse-attention-kit/
```

## 4. Disable shared (kernel-only deploy)

```bash
zarf package deploy a11oy-uds-0.2.0.tar.zst --confirm --components=-a11oy-shared
```

This omits `/opt/a11oy/shared/` entirely; the KS-18 kernel and
attestation chain still ship.

## v0.2.0 — what changed

| Package                              | Purpose                                                                                                              | Receipt classes                |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------|--------------------------------|
| `@szl-holdings/perception-loop`      | Operator-loop perception envelope. **Privacy invariant: raw frames never leave the loop**; only feature-vector summaries enter the receipt stream. | `perception.observation.v1` family |
| `@szl-holdings/sequence-pipeline`    | Multi-stage hashed evidence pipeline (per-stage `evidence.stage.v1` linked into a sealed `evidence.sealed.v1`).        | `evidence.*.v1`                |
| `@szl-holdings/sparse-attention-kit` | Sparse-attention envelope (NSA / MoBA / MiniMax / FlashAttention re-expressed). **Non-negotiable contradiction-probe + fail-up-to-full escalation** — the MiniMax M2 lesson. | 12 `sparse.*.v1` receipts        |

Each shared package is hash-pinned in `MANIFEST.json` and listed as a
subject in `attestations.json`, so a tampered shared package fails
verification the same way a tampered core package would.
