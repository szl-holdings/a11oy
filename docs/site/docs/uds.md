# UDS — customer deployment & hand-off

This is the **customer hand-off page** for deploying an SZL flagship as a signed UDS
(Unified Delivery System / Defense Unicorns) payload. It mirrors the
[CUSTOMER_DEPLOYMENT_README](https://github.com/szl-holdings/uds-bundles) shipped in
`uds-bundles`. For the live multi-organ demo surface, see [UDS — Unified Demo Surface](/uds/).

> Doctrine v11 **LOCKED** — 749/14/163 · kernel `c7c0ba17` · **Λ = Conjecture 1** · SLSA L1 honest ·
> Section 889 = exactly 5 vendors.

## 30-second summary

SZL flagships ship as **Zarf/UDS packages** stored as OCI artifacts in GHCR. Each artifact is
**cosign-signed (keyless OIDC)**, carries a **CycloneDX + SPDX SBOM**, and emits **DSSE Khipu
receipts** at runtime. Deploy into any UDS Core / k3d cluster, airgap-friendly. Receipt-key
material is regenerable; rotation forks the Khipu DAG.

## 1 · Pull the OCI artifact

Container packages are published under `ghcr.io/szl-holdings/<flagship>`:

```bash
# Example: a11oy. Substitute sentra / amaru / rosie / killinchu as needed.
zarf package pull oci://ghcr.io/szl-holdings/a11oy:uds-v0.2.0
```

> **Honest note.** GHCR publication is gated on the org "Read and write" workflow permission;
> at hand-off time some flagship images may be pending that founder action. Confirm the exact
> tag against the [latest release assets](https://github.com/szl-holdings/a11oy/releases).

## 2 · Verify the signature (cosign, keyless OIDC)

```bash
cosign verify ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

This checks that the artifact was built by a `szl-holdings` GitHub Actions workflow via the
OIDC issuer — no long-lived signing key. SBOMs are attached as release assets.

## 3 · Deploy on UDS

```bash
# UDS Core must be running first (k3d example):
uds deploy k3d-core
# Then deploy the flagship payload:
uds deploy oci://ghcr.io/szl-holdings/a11oy:uds-v0.2.0
```

## 4 · Helm hook — receipt-key flow

The flagship chart registers a **pre-install / pre-upgrade Helm hook** that provisions the
DSSE receipt keypair into the cluster before the workload starts:

```yaml
# values.yaml (excerpt)
receiptKey:
  algorithm: ed25519       # Ed25519 (not RSA) — post-quantum prep, smaller signatures
  rotation:
    enabled: true
    onRotate: fork-khipu   # rotating the keypair forks the Khipu DAG (auditable)
```

```yaml
# templates/receipt-key-hook.yaml (excerpt)
metadata:
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation
```

The hook generates (or rotates) the Ed25519 keypair, stores it as a Kubernetes Secret, and
writes a rotation receipt into the Khipu chain. On rotation the DAG **forks** so historic
receipts stay verifiable against the prior key.

## 5 · Airgap

UDS packages are self-contained (images + SBOM + signatures bundled). Pull on a connected
host, transfer the `.tar.zst`, and `uds deploy` the local file — no registry egress required
at the airgapped site.

## Section 889 admission

Exactly **5 vendors** are blocked at admission via a Pepr policy: Huawei, ZTE, Hytera,
Hikvision, Dahua. No Iron Bank / FedRAMP / CMMC / SWFT / Mission Owner claims.

---
*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 · SLSA L1 honest*
