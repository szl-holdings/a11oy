<!-- szl-investor-header -->
<div align="center">

# szl-build-env

### A one-command local environment that boots SZL's full 5-organ governance stack — service mesh, telemetry, and signed-image verification — in under 10 minutes.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/szl-build-env/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-build-env/actions/workflows/ci.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://docs.szlholdings.com) · [Quickstart](https://docs.szlholdings.com/quickstart) · [SZL Holdings](https://szlholdings.com)

</div>

## 💡 Why it matters

Engineers and design partners can stand up the entire governed-AI stack on a laptop and see policy enforcement, audit receipts, and supply-chain verification working end to end — no cloud account, no air-gap setup required.

## ▶️ Live demo

_Internal / private repository — no public demo surface. See [docs.szlholdings.com](https://docs.szlholdings.com) for the public product walkthrough._

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/szl-build-env.git
cd szl-build-env
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://docs.szlholdings.com).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

# szl-build-env

**Local build environment for SZL Holdings.** Brings up a full **5-organ + Istio
ambient mesh + OpenTelemetry** stack on a single-node [kind](https://kind.sigs.k8s.io)
cluster so any SZL engineer can develop against the real fleet topology in
**under 10 minutes**.

> Doctrine v11 LOCKED `749/14/163` @ kernel commit `c7c0ba17`.
> **NOT** Iron Bank · **NOT** FedRAMP · **NOT** CMMC L2+. SLSA **L1 honest** (no build-provenance attestation workflow — L2 not yet produced).
> Mesh: **Istio ambient** (ztunnel + waypoint), *not* sidecar injection — by doctrine we are not Iron Bank.

---

## What you get

| Layer | Component | Pin |
|-------|-----------|-----|
| Cluster | kind, single node | node image `v1.32.2` |
| Mesh | Istio **ambient** (ztunnel + waypoint) | `1.25.0` |
| Telemetry | OpenTelemetry Collector → Jaeger | collector `0.135.0` |
| Workloads | 5 organs: `a11oy`, `sentra`, `amaru`, `killinchu`, `rosie` | bundle `uds-v0.2.0` |
| Supply chain | `cosign verify` + `slsa-verifier` init gate | honest fail-closed |

Organ images are pulled from the published bundle
`oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0`
(individual images `ghcr.io/szl-holdings/<organ>:uds-v0.2.0`).

---

## 10-minute quickstart

```bash
# 0. prerequisites (see Host prerequisites below) — Docker, kubectl, kind, istioctl
git clone https://github.com/szl-holdings/szl-build-env.git
cd szl-build-env

# 1. bring up the whole stack (kind + istio ambient + otel + 5 organs)
make up           # ~6-8 min on a warm Docker cache

# 2. prove the supply-chain gate is honest (cosign + slsa-verifier per organ)
make verify

# 3. send a request and watch one traceparent propagate across all 5 organs
make trace        # opens / prints the Jaeger trace tree

# 4. tear everything down
make down
```

One-shot golden path for a demo:

```bash
make demo         # up -> verify -> seed request -> show cross-organ trace + DSSE chain
```

---

## Host prerequisites

| Tool | Min version | Install |
|------|-------------|---------|
| Docker Desktop / Engine | 24+, **8 GB RAM** allocated | https://docs.docker.com/get-docker/ |
| kubectl | 1.30+ | https://kubernetes.io/docs/tasks/tools/ |
| kind | 0.32.0 | `go install sigs.k8s.io/kind@v0.32.0` |
| istioctl | 1.25.0 | `make istioctl` (downloads pinned binary into `./bin`) |
| cosign | 2.x | https://docs.sigstore.dev/cosign/system_config/installation/ |
| slsa-verifier | 2.x | https://github.com/slsa-framework/slsa-verifier#installation |
| jq | any | `brew install jq` / `apt install jq` |

> **Docker memory:** the ambient mesh + 5 organs + collector need ~6 GB working set.
> Set Docker Desktop to **8 GB+** (Settings → Resources). Less than 6 GB will OOM ztunnel.

---

## Repository layout

```
kind/cluster.yaml                  single-node kind config (pinned node image)
bootstrap/install-istio-ambient.sh Istio ambient installer (pinned 1.25.0)
bootstrap/install-otel-collector.sh OTLP collector + Jaeger exporter
manifests/organs/*.yaml            5 organ Deployments (cosign-gated initContainer)
manifests/mesh/waypoint.yaml       ambient waypoint for inter-organ L7 routing
manifests/otel/collector.yaml      OTLP collector config (DSSE-aware processor stub)
verify/cosign-init.sh              the fail-closed supply-chain gate
verify/run-acceptance.sh           /healthz + end-to-end traceparent propagation check
demo/greene-demo.sh                June 9 scripted demo
.github/workflows/ci.yml           PR CI: make up + make verify in kind
HONEST_GAPS.md                     everything currently stubbed and why
```

---

## Honest gaps

Read [`HONEST_GAPS.md`](./HONEST_GAPS.md) before you trust a green check.
Short version:

- **`killinchu` image is private.** It will `ImagePullBackOff` until the founder
  flips the GHCR package to public (or you add a pull secret). The other 4 organs
  pull anonymously. `make verify` reports this honestly rather than skipping it.
- **DSSE receipt chain is signature-light** until a real `COSIGN_KEY` /
  Sigstore identity is wired. The collector's DSSE processor is a documented stub.
- **SLSA L1 is honest; L2 attestation is verified only where provenance exists.**
  `slsa-verifier` runs against every organ but only enforces on images that ship
  a provenance attestation.

No secrets are committed to this repo. See `HONEST_GAPS.md` § Secrets.

---

## License

Apache-2.0. See [`LICENSE`](./LICENSE).


</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA L1 honest · Section 889 = 5 vendors · [SZL Holdings](https://szlholdings.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>
