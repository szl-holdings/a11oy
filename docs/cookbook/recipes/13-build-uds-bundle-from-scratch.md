# Build a UDS bundle from scratch

> **Start with one organ's Zarf package, prove it deploys, then grow the `uds-bundle.yaml` to all five flagships — the inverse of recipe 02.**
>
> **Headline number: 1 organ → 5 organs in one bundle, all doctrine-locked.**

Recipe 02 *deploys* the published bundle. This recipe *builds* one, so you can package your own
organ (**[recipe 07](07-build-your-own-organ.md)**) alongside the flagships.

> **Trademark note.** "UDS" references Defense Unicorns' Unified Defense Stack (USPTO Serial
> 99831122); SZL is not affiliated. See <https://defenseunicorns.com/uds>.

---

## Prerequisites

```bash
brew install zarf defenseunicorns/tap/uds      # Zarf v0.77.0+, uds-cli
# Docker/k3d for a local UDS Core v1.5.0 cluster
```

---

## Quickstart — one-organ bundle

```yaml
# zarf.yaml — package a single organ (amaru) as a Zarf component
kind: ZarfPackageConfig
metadata:
  name: szl-amaru
  version: uds-v0.2.0
components:
  - name: amaru
    required: true
    images:
      - ghcr.io/szl-holdings/amaru:uds-v0.2.0
    charts:
      - name: amaru
        namespace: szl
        localPath: ./chart
```

```yaml
# uds-bundle.yaml — start with one organ
kind: UDSBundle
metadata:
  name: szl-uds-bundle
  version: uds-v0.2.0
packages:
  - name: szl-amaru
    path: .
    ref: uds-v0.2.0
```

```bash
zarf package create . --confirm
uds create . --confirm
uds deploy szl-uds-bundle-*.tar.zst --confirm
kubectl -n szl exec deploy/amaru -- curl -sf localhost:8080/api/amaru/healthz && echo OK
```

---

## Full walkthrough

### Step 1 — Package one organ and prove it

Get a single organ green before adding more. The acceptance test is the doctrine probe:
`/api/amaru/v1/honest` must report `v11 / 749 / 14 / 163 / c7c0ba17`.

### Step 2 — Add the three CRDs

The mesh contract is three K8s-native CRDs (from
[uds-bundles](https://github.com/szl-holdings/uds-bundles)):

| CRD | Role |
|---|---|
| `LambdaGate` | declares the Λ floor (0.9) and axis set for the namespace |
| `KhipuReceipt` | the receipt CR type organs emit |
| `DoctrineLock` | pins the namespace to `c7c0ba17`; Pepr fails CLOSED on mismatch |

### Step 3 — Grow to five

Add the other four organs as packages. Order matters only for readability; the mesh is
peer-to-peer:

```yaml
packages:
  - { name: szl-a11oy,     path: ../a11oy,     ref: uds-v0.2.0 }
  - { name: szl-sentra,    path: ../sentra,    ref: uds-v0.2.0 }
  - { name: szl-amaru,     path: ../amaru,     ref: uds-v0.2.0 }
  - { name: szl-rosie,     path: ../rosie,     ref: uds-v0.2.0 }
  - { name: szl-killinchu, path: ../killinchu, ref: uds-v0.2.0 }
```

### Step 4 — Attach SBOMs + provenance

Zarf emits SPDX + CycloneDX SBOMs automatically. Sign the bundle image with keyless cosign so it
verifies via **[recipe 06](06-cosign-rekor-slsa-l1.md)**. This is what makes the bundle SLSA L1
(honest): SBOM + DCO + provenance pointer.

### Step 5 — Verify the whole mesh

Run the recipe-02 health loop: all five organs (plus any custom organ from recipe 07) must report
the same locked doctrine. A single mismatch is a `DoctrineLock` failure, by design.

---

## See also

- **[02 — Deploy the 5-flagship UDS bundle](02-deploy-5-flagship-uds-bundle.md)** — deploy the published one.
- **[07 — Build your own organ](07-build-your-own-organ.md)** — add a sixth.
- **[15 — Air-gapped install](15-air-gapped-install.md)** — ship it offline.
- Repo: [uds-bundles](https://github.com/szl-holdings/uds-bundles)

## Cite this recipe

```bibtex
@misc{szl_cookbook_build_bundle_2026,
  title        = {Build a UDS bundle from scratch (SZL Cookbook recipe 13)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/13-build-uds-bundle-from-scratch.md}},
  note         = {UDS Core v1.5.0; CRDs LambdaGate/KhipuReceipt/DoctrineLock. Doctrine v11 c7c0ba17.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
