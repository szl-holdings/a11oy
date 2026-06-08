> **Trademark notice.** SZL Holdings' use of "UDS" references Defense Unicorns' Unified Defense Stack (USPTO Serial 99831122). SZL Holdings is not affiliated with Defense Unicorns. SZL contributions to the UDS ecosystem are made through upstream PRs. See: https://defenseunicorns.com/uds

# uds-bundles

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap](https://img.shields.io/badge/SLSA-L1%20honest%20%C2%B7%20L2%20build--attested%20(Rekor)%20%C2%B7%20L3%2B%20roadmap-2C5F2D?style=flat-square)](https://slsa.dev)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](SECURITY.md)

**Five airgap-deployable Zarf bundles for the SZL governed agentic mesh — built on Unified Defense Stack (UDS) Core v1.5.0.**

---

## What this is

`uds-bundles` packages the five SZL flagship organs as Unified Defense Stack (UDS)-compatible Zarf bundles:

| Bundle | Organ | Role |
|--------|-------|------|
| `szl-a11oy` | Governance gate | Policy overlay + Λ-gate + agentic /code orchestrator |
| `szl-sentra` | Immune system | 8-gate fail-CLOSED verdict pipeline |
| `szl-amaru` | Memory cortex | Khipu Merkle DAG + DSSE-signed receipt chain |
| `szl-rosie` | Operator application | Human-on-the-loop decision approval gates (full 10-view operator app) |
| `szl-killinchu` | Counter-UAS | Λ-gate defensive application (ADS-B + MAVLink) |

Each bundle ships: `uds-bundle.yaml` · `zarf.yaml` · Helm chart · Pepr policies + ValidatingAdmissionPolicy + Cilium NetworkPolicy · SPDX + CycloneDX SBOMs · SLSA v1.2 provenance · `serviceMesh.mode: ambient`.

Three K8s-native CRDs in `crds/`: **LambdaGate** · **KhipuReceipt** · **DoctrineLock**.

---

## How to use

### Prerequisites

```bash
# Install Zarf v0.77.0+
brew install zarf   # or: https://zarf.dev/install

# Install uds-cli
brew install defenseunicorns/tap/uds

# Running UDS Core v1.5.0 cluster required
```

### Deploy a single bundle

```bash
git clone https://github.com/szl-holdings/uds-bundles
cd uds-bundles

# Build the Zarf package locally (requires Docker)
zarf package create bundles/szl-sentra/ --confirm

# Deploy to a running UDS Core cluster
zarf package deploy zarf-package-szl-sentra-amd64-0.2.0.tar.zst --confirm
```

See `bundles/DEPLOY_RUNBOOK.md` for Scenario A (single organ), B (sentra + amaru), C (full mesh).

---

## How to verify

```bash
# Verify cosign signature (keyless)
cosign verify-blob   --certificate-identity "https://github.com/szl-holdings/uds-bundles/.github/workflows/zarf-bundle-build.yml@refs/tags/v0.2.0"   --certificate-oidc-issuer "https://token.actions.githubusercontent.com"   bundle.tar.zst

# Inspect SLSA provenance
cat bundles/szl-a11oy/attestations/a11oy.slsa-provenance.json

# Check Doctrine lock
kubectl get doctrinelock -n szl-a11oy
```

---

## Per-organ provenance matrix (SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap — all organs)

Each organ image is referenced in this bundle by **immutable digest** (not a floating tag).
**Honest doctrine:** All five organ images are **SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap**. Each organ has GitHub
Actions-generated build provenance (cosign keyless-signed, Rekor-anchored), and its build-attested (Rekor) SLSA
provenance attestation cryptographically verifies via `cosign verify-attestation --type
slsaprovenance <organ-image> --certificate-identity-regexp "https://github.com/szl-holdings/<organ>/"
--certificate-oidc-issuer "https://token.actions.githubusercontent.com"`. **L3 is NOT claimed**
(no FedRAMP, Iron Bank, or CMMC).

| Organ | Image (digest-pinned) | Build provenance | Rekor entry |
|-------|------------------------|-----------------|-------------|
| `szl-a11oy` | `ghcr.io/szl-holdings/a11oy@sha256:8aaea251609104b554baaac161a0e44cb59a909296e0b37d25ba94b3ab921530` | cosign keyless + `slsa.dev/provenance/v1` DSSE | logIndex **1710578865** |
| `szl-sentra` | `ghcr.io/szl-holdings/sentra@sha256:32360746e0084ca0c7233bbca2709c1b1e907b6ffa91c166444d8aeb196fa002` | cosign keyless + DSSE | logIndex **1710576247** |
| `szl-amaru` | `ghcr.io/szl-holdings/amaru@sha256:435ac605a21feaa9c273c6877232307e88f304f81b2248b73c6dcfa31d997993` | cosign keyless + DSSE | logIndex **1712902861** |
| `szl-rosie` | `ghcr.io/szl-holdings/rosie@sha256:86429fd4a07e209c02004e0ddd5ec408a2587a720a7e91cf5fbe1fe88e188a01` | cosign keyless + DSSE | logIndex **1710599687** |
| `szl-killinchu` | `ghcr.io/szl-holdings/killinchu@sha256:e872344f2fc8e7d8085042d5b5660c8bd62887a7d2f2353f44f882d782e8cd75` | cosign keyless + DSSE | `bundles/szl-killinchu/attestations/killinchu.slsa-provenance.json` |

The published mesh bundle artifact is `oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0`. It composes all five organ Zarf packages. **Honest scope:** the L2 SLSA build-provenance attestation that cryptographically verifies is on the **five organ images** (above), **not on the bundle artifact itself** — bundle-level attestation is not yet published (blocked on an owner-only GHCR `szl-uds-bundle` package-write grant). Do not claim the bundle is L2-attested until `cosign verify-attestation` returns a provenance payload for the bundle.

## Honest disclosure

- **Organ images: SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap.** All five organ images are **SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap** — each has GitHub Actions-generated build provenance (cosign keyless-signed, Rekor-anchored) and its build-attested (Rekor) SLSA provenance attestation verifies via `cosign verify-attestation --type slsaprovenance` under strict per-organ identity. **L3 is NOT claimed anywhere** (doctrine: L3 is banned; no FedRAMP, Iron Bank, or CMMC).
- **Bundle artifact: signed, NOT yet attested.** The mesh bundle `szl-uds-bundle:uds-v0.2.0` is real and deployable, but the **bundle artifact itself is not yet SLSA-attested** (owner-only GHCR package-write grant pending). The attestations that verify are on the organ images, not the bundle.
- **Λ = Conjecture 1**, NOT a theorem — Lake Verifier testing the proof; 163 sorries open
- **Proved PURIQ formulas = exactly 5** — F1, F11, F12, F18, F19 (Lean 4, zero-sorry); the remaining 18 are Roadmap
- **Section 889** = exactly 5 banned vendors: Huawei, ZTE, Hytera, Hikvision, Dahua
- **`uds-v0.2.0` is the published, signed mesh bundle** — the per-flagship Zarf source packages under `bundles/szl-<flagship>/` can also be built locally with `zarf package create bundles/szl-<flagship>/`.
- No Iron Bank, no FedRAMP, no CMMC — deploy on YOUR operational hardware

---

## Compatibility

| Component | Version |
|-----------|---------|
| UDS Core | v1.5.0 |
| Zarf | ≥ v0.77.0 |
| Kubernetes | v1.35+ (tested on v1.36.1) |
| cosign | v3.0.6 (GHSA-w6c6-c85g-mmv6 patched) |

---

**Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT a theorem) · Apache-2.0**

*Signed-off-by: Yachay <yachay@szlholdings.ai>*


