<!-- szl-investor-header -->
<div align="center">

# szl-uds-deployment

### A ready-to-run deployment that proves SZL's governance receipts working live on a Kubernetes cluster, signed and verifiable end to end.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/szl-uds-deployment/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-uds-deployment/actions/workflows/release.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://docs.szlholdings.com) · [Quickstart](https://docs.szlholdings.com/quickstart) · [SZL Holdings](https://szlholdings.com)

</div>

## 💡 Why it matters

It is the live reference deployment used for the 2026 Warhacker demo — showing policy enforcement and signed audit receipts running on real infrastructure, the way a customer would actually operate it in an air-gapped environment.

## ▶️ Live demo

_Internal / private repository — no public demo surface. See [docs.szlholdings.com](https://docs.szlholdings.com) for the public product walkthrough._

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/szl-uds-deployment.git
cd szl-uds-deployment
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://docs.szlholdings.com).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

<div align="center">

# ⚙️ szl-uds-deployment

> ⚠️ **STAGING — not production-grade.** This repository is a staging/pre-production deployment surface and should not be treated as a production deployment.

**uds deploy**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276) [![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-a6ce39?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173) [![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444?style=flat-square)](https://github.com/szl-holdings/lutar-lean) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Hugging Face](https://huggingface.co/SZLHOLDINGS) · [Demo](https://szlholdings-readme.static.hf.space/) · [GitHub Org](https://github.com/szl-holdings)

`receipts.in ≡ receipts.out`

</div>

---
> **STAGED-ADVISORY (2026-05-30 — Doctrine v11 LOCKED 749/14/163):** UDS catalog-grade delivery is BLOCKED pending:
> 1. **Founder action:** Push `ghcr.io/szl-holdings/vessels:0.3.1` to GHCR (requires org GHCR auth chain — cannot be done by agent)
> 2. **Signed assets:** Attach `vessels-uds-0.3.1.tar.zst` + `.sig` + `.sha256` + `vessels-uds-dev.pub` to vessels release `uds-v0.3.1-vessels` (vessels uses `-vessels` suffix for UDS git tags; no bare `uds-v0.3.1` tag exists on vessels)
> 3. **CI gate:** `scripts/verify_signed_assets.sh` must pass green before any PR may claim catalog-grade
>
> Current state: vessels `uds-v0.3.0` has **zero binary release assets**. `uds-v0.3.1` bare tag does not exist on vessels; vessels UDS tags use the `-vessels` suffix (`uds-v0.3.1-vessels` through `uds-v0.3.4-vessels` exist as git tags without GitHub releases).
> Catalog readiness scorecard: [SZLHOLDINGS/uds-governance-receipts — UDS_CATALOG_READINESS_2026-05-30.md](https://huggingface.co/datasets/SZLHOLDINGS/uds-governance-receipts/blob/main/UDS_CATALOG_READINESS_2026-05-30.md)

# szl-uds-deployment

[![GHAS Code Security](https://img.shields.io/badge/GHAS-Code_Security-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/szl-uds-deployment/security/code-scanning)
[![Secret Protection](https://img.shields.io/badge/GHAS-Secret_Protection-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/szl-uds-deployment/security/secret-scanning)
[![SLSA L1 · L2 roadmap](https://img.shields.io/badge/SLSA-L1_%E2%86%92_L2_roadmap-0B1F3A.svg?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

**SZL Governance Receipts — UDS Running Deployment**

DSSE-wrapped audit receipts emitted from live Kubernetes workloads on a UDS infrastructure stack (k3d + uds-cli + Pepr policies).

Built for [Warhacker 2026](https://warhacker.io), June 16-20, San Diego.

---

## What This Is

A UDS add-on that attaches cryptographic governance receipts to every Kubernetes Deployment and Job admitted to the cluster. The Pepr admission controller intercepts each workload API call, generates a DSSE-wrapped HMAC-SHA-256 receipt, posts it to an in-cluster receipt server, and annotates the resource with the receipt ID.

**This is NOT:**
- A replacement for uds-core security policies
- A certified DoD package (Phase 2 intent)
- A modification of uds-core (zero AGPL entanglement — network-only coupling)
- Production-hardened (demo-grade; see Phase 2 roadmap in ARCHITECTURE.md)

---

## Quick Start

```bash
# Prerequisites: Docker, k3d, uds CLI, zarf CLI
# See docs/INSTALL.md for one-liner installs

uds run start           # bootstrap k3d + deploy bundle (~90 seconds)
uds run demo:workload   # apply sample workload → receipt appears in feed
uds run demo:verify     # verify receipt chain from cluster
```

Dashboard: `http://localhost:8443` (after `uds run port-forward`)

---

## Repository Structure

```
szl-uds-deployment/
├── zarf.yaml                      # Zarf package definition
├── uds-bundle.yaml                # UDS bundle manifest
├── tasks.yaml                     # uds-cli task runner
├── tasks/
│   └── demo.yaml                  # demo sub-tasks
├── manifests/
│   └── namespace.yaml             # szl-receipts namespace
├── charts/
│   └── szl-receipts/              # Helm chart: receipt server + dashboard
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml    # MCP receipts server + nginx sidecar
│           ├── service.yaml       # ClusterIP + ServiceAccount + HMAC secret
│           ├── ingress.yaml       # UDS Package CR + ServiceMonitor
│           └── configmap.yaml     # Server Python source + dashboard HTML
├── pepr/                          # Pepr policy module
│   ├── package.json
│   ├── tsconfig.json
│   ├── pepr.ts                    # Module entry point
│   └── policies/
│       └── szl-receipt-on-deploy.ts  # Emit DSSE receipt on Deployment/Job
├── ui/
│   └── dashboard.yaml             # Standalone NGINX dashboard manifest
├── scripts/
│   ├── demo_workload.sh           # Interactive demo workload script
│   ├── demo_workload.yaml         # K8s manifests for demo workload
│   └── verify_receipts.sh         # Post-demo receipt chain verification
└── docs/
    ├── WARHACKER_DEMO.md          # 5-minute talk track (live cluster edition)
    ├── INSTALL.md                  # One-page install + deploy guide
    └── ARCHITECTURE.md            # Cluster diagram + AGPL compliance rationale
```

---

## License

Apache-2.0 — designed to be contributable to the Defense Unicorns ecosystem.

See [LICENSE](LICENSE) for full text.

---

## Contact

Stephen Paul Lutar JR — stephen@szlholdings.com  
[SZL Holdings](https://szlholdings.com)

## Optional Components

The following components are marked `required: false` in `zarf.yaml` and are **skipped on default install**:

- **`szl-receipts-pepr-policy`** — requires building the Pepr policy first:
  ```bash
  cd pepr && pnpm install && pnpm build
  # Produces dist/pepr/ which is imported by zarf.yaml
  ```
  To deploy with Pepr: `zarf package deploy <pkg> --components=szl-receipts-namespace,szl-receipts-server,szl-receipts-pepr-policy`

- **`szl-ui-dashboard`** — requires the `ui/chart` Helm chart directory (Phase 2 deliverable).
  To deploy once available: `zarf package deploy <pkg> --components=szl-receipts-namespace,szl-receipts-server,szl-ui-dashboard`

The default deploy (all `required: true` components only) installs namespace + server.

---


## Receipt Key

On first `uds deploy`, a Helm pre-install hook (Job `szl-key-init`) auto-generates
an Ed25519 keypair in the `pepr-system` namespace as Secret `szl-receipts-ed25519`.

**Zero founder action required.** The customer's cluster generates the key.
SZL never sees it. The founder never runs `generate-receipt-key.sh` manually.

### How it works

1. `uds deploy` runs the `szl-key-init` Helm chart as a pre-install hook (weight: -5)
2. A Job in the target namespace checks: does `szl-receipts-ed25519` already exist?
   - **Yes** → exits 0 immediately (BYOK path — your key is preserved)
   - **No** → generates Ed25519 keypair via `openssl genpkey -algorithm ED25519`,
     creates the Secret with `key.priv` and `key.pub`, shreds the private key from
     container tmpfs
3. `szl-receipts-server` starts and mounts the Secret for signing

### Bring Your Own Key (BYOK)

Pre-create the Secret before `uds deploy`:

```bash
kubectl create secret generic szl-receipts-ed25519 \
  --namespace pepr-system \
  --from-file=key.priv=/path/to/your-ed25519-private.pem \
  --from-file=key.pub=/path/to/your-ed25519-public.pem
```

The hook exits 0 without touching the existing Secret.

### Honest disclosure

If `pepr-system` namespace does not exist at hook time (uncommon — UDS Core creates
it), the hook fails and the receipts server falls back to `UNSIGNED-NO-ED25519-KEY`
sentinel mode. Receipts are still persisted but signatures show the sentinel string
rather than an Ed25519 signature.

**References:**
- `charts/szl-key-init/` — Helm chart with pre-install hook Job
- `charts/szl-key-init/templates/keygen-job.yaml` — Job template
- `charts/szl-key-init/templates/rbac.yaml` — minimal RBAC (get + create secrets only)
- `packages/szl-receipts/zarf.yaml` — szl-key-init added as required component


</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA L1 honest · Section 889 = 5 vendors · [SZL Holdings](https://szlholdings.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>
