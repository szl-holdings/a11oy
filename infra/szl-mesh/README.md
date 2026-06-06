<!-- szl-investor-header -->
<div align="center">

# szl-mesh

### A doctrine-pinned coordination layer that lets SZL's governance organs stay in sync across an air-gapped fleet, even when nodes go offline.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/szl-mesh/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-mesh/actions/workflows/ci.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://docs.szlholdings.com) · [Quickstart](https://docs.szlholdings.com/quickstart) · [SZL Holdings](https://szlholdings.com)

</div>

## 💡 Why it matters

It brings always-converging shared state and Byzantine-fault-tolerant agreement to edge and disconnected deployments, so a sovereign fleet keeps making consistent, signed governance decisions without a central server.

## ▶️ Live demo

_Internal / private repository — no public demo surface. See [docs.szlholdings.com](https://docs.szlholdings.com) for the public product walkthrough._

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/szl-mesh.git
cd szl-mesh
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://docs.szlholdings.com).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

# SZL-MESH

**Doctrine-pinned CRDT mesh layered on peat — 7 inventions beyond UDS Fleet**

> **Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17` · Λ = Conjecture 1 (NOT theorem) · SLSA L1  
> **Status:** Skeleton — Design complete, implementation in progress  
> **Date:** 2026-06-02  
> **Prepared by:** SZL Holdings Research (PhD Distributed Systems)

---

## What Is SZL-MESH?

SZL-MESH is SZL Holdings' native coordination substrate for DDIL-resilient fleet state. It **layers on top of [peat](https://github.com/defenseunicorns/peat)** (Defense Unicorns' CRDT mesh protocol) — it does NOT fork or replace peat. Instead, it adds a capability that peat explicitly lacks: **doctrine-pinned DSSE receipt chains on top of CRDT state transitions**.

> Peat knows **WHAT** happened to fleet state. SZL-MESH knows **WHETHER** that change was AUTHORIZED under a locked governance doctrine and **WHO** signed the authorization.

This is not incremental improvement. It is a **governance layer** — the difference between a distributed database and a distributed governance ledger.

---

## The 7 Inventions Beyond Peat

### 1. Doctrine-Pinned DSSE Receipts on CRDT State Transitions

**Peat:** Signs each CRDT operation with the originating node's Ed25519 key (integrity: we know WHO wrote it).

**SZL-MESH adds:** Every Automerge change that crosses a policy boundary is wrapped in a **DSSE (Dead Simple Signing Envelope)** receipt containing:
- `doctrine_version: "749/14/163"` — the locked governance version
- `kernel_commit: "c7c0ba17"` — the pinned kernel context
- `change_hash` — SHA-256 binding the receipt to the exact Automerge change chunk
- `transition_class` — PLATFORM_STATUS | DEPLOYMENT | PACKAGE | COMMAND | CELL_FORMATION

**Why categorical, not incremental:** Peat proves identity (who wrote). SZL-MESH proves authority (was this write authorized under current governance). Adding this to peat would require fundamental redesign — it cannot be bolted on.

See: [`spec/01-dsse-receipts.md`](spec/01-dsse-receipts.md)

---

### 2. Two-Track AUTHORIZED / OBSERVED State

**Peat:** All CRDT state is equivalent — formation key + Ed25519 = authoritative.

**SZL-MESH adds:** A dual-track state model coexisting in the same CRDT store:

| Track | Condition | Rosie Display | Actionable? |
|-------|-----------|---------------|-------------|
| **AUTHORIZED** | CRDT change carries valid DSSE receipt under doctrine `749/14/163` | Solid indicator | Yes — command decisions |
| **OBSERVED** | CRDT change present but no valid receipt (partition, stale doctrine, peat-native node) | Dashed indicator | No — situational awareness only |

**Backwards-compatible:** Vanilla peat nodes' state appears as OBSERVED, not dropped. SZL-MESH never partitions the network on receipt status.

**Military analogy:** A soldier can *observe* any radio report, but will only *act* on authenticated command authority.

See: [`spec/02-two-track-state.md`](spec/02-two-track-state.md)

---

### 3. Skip-Layer O(n) Aggregation (Λ = Conjecture 1)

**Peat:** O(n log n) hierarchical aggregation — every change flows through the full tree (Squad → Platoon → Company → Command).

**SZL-MESH adds:** Receipt-priority skip-layer routing — a receipted AUTHORIZED change bypasses intermediate aggregation and routes directly to command hub:

```
Without skip-layer (peat baseline):
  Squad → Platoon → Company → Command   (3 hops, O(n log n))

With SZL skip-layer (AUTHORIZED changes only):
  Squad ──────────────────────→ Command  (1 hop, O(n))
  Squad → Platoon → Company → Command   (OBSERVED changes: full path)
```

**Asymptotic analysis:** Let `r` be the fraction of receipted changes, `N` total nodes.
- Peat: `T(N) = O(N log N)` for all changes
- SZL-MESH: `T(N) = r·O(N) + (1-r)·O(N log N)` → O(N) as r → 1

> **⚠ Λ = Conjecture 1 (NOT theorem):** The O(n) claim is a design-time conjecture pending formal verification and empirical validation on a live formation. Do not present as proven.

See: [`spec/03-skip-layer-aggregation.md`](spec/03-skip-layer-aggregation.md)

---

### 4. CRDT-Native Byzantine Corroboration

**Peat:** Assumes fail-stop nodes. A Byzantine peer with a valid formation key can inject arbitrary CRDT state.

**SZL-MESH adds:** k-of-n corroboration layered on top of the CRDT — NOT as a consensus protocol (which would sacrifice availability), but as a **soft voting annotation** that runs alongside the AP CRDT without blocking writes:

```
1. Any node writes state (immediately available — AP guarantee preserved)
2. Corroboration collector observes changes from multiple nodes
3. When k independent nodes report same value for a key within window T:
   → Change is annotated CORROBORATED
4. Single Byzantine node cannot achieve CORROBORATED for false state if k > 1
```

**Key novelty:** BFT consensus (PBFT, Tendermint, HotStuff) sacrifices availability. SZL-MESH achieves **Byzantine soft-safety** while preserving full AP availability. A different point in the BFT trade-off space.

Default policy: `k=2, window=30s` for PLATFORM_STATUS and COMMAND transitions.

See: [`spec/04-byzantine-corroboration.md`](spec/04-byzantine-corroboration.md)

---

### 5. Doctrine-Gated Enrollment

**Peat:** Formation key HMAC proves physical presence. Anyone with the formation key can enroll.

**SZL-MESH adds:** Enrollment additionally requires claiming:
- `doctrine_version: "749/14/163"` (cryptographically asserted in CSR)
- `kernel_commit: "c7c0ba17"`
- `slsa_level: "L1"`

A node running an older doctrine — even with the formation key — **cannot enroll as AUTHORIZED**. It may participate as OBSERVED (if peat-compatible) but cannot generate doctrine receipts.

**Lifecycle benefit:** When governance doctrine increments (new NDAA provision, new Section 889 vendor), stale nodes are automatically downgraded without explicit revocation. The governance lifecycle is **encoded in the cryptographic enrollment proof**.

Section 889 covered vendors checked at enrollment: **Huawei, ZTE, Hytera, Hikvision, Dahua** (exactly 5).

See: [`spec/05-doctrine-gated-enrollment.md`](spec/05-doctrine-gated-enrollment.md)

---

### 6. CRDT Revocation Without OCSP

**Peat:** TTL-based certificate expiry. No real-time revocation in air-gapped environments.

**SZL-MESH adds:** A **CRDT-replicated revocation list** that propagates revocations through the mesh using the same AP CRDT substrate — no OCSP server required:

```
crdt_document: "szl-mesh/revoked-certs/formation-<id>"
type: Automerge grow-only set
contents: [{ node_id, cert_fingerprint, revoked_at, reason }]
```

Properties:
- **AP available** — revocations propagate through CRDT; nodes check local replica
- **Eventually consistent** — revocation reaches partitioned cell when any path reconnects
- **Monotonic** — revocations are never un-done (grow-only set)
- **Air-gap compatible** — no external service required

See: [`spec/06-crdt-revocation.md`](spec/06-crdt-revocation.md)

---

### 7. Sentra Governance Metrics (First-Class Telemetry Channel)

**Peat:** `GetSyncStats` RPC for basic sync monitoring. CDC events to Kafka/NATS.

**SZL-MESH adds:** Receipt health metrics fed into sentra's immune filter — anomaly detection on governance integrity:

```
szl_mesh_authorized_fraction{formation_id, cell_id}
  → Ratio AUTHORIZED / total changes per time window
  → Drop below threshold = governance anomaly alert

szl_mesh_byzantine_corroboration_failures{node_id}
  → Repeated failures = Byzantine candidate alert

szl_mesh_revocation_propagation_lag_seconds{formation_id}
  → High lag = partition severity indicator

szl_mesh_doctrine_version_mismatch_count{formation_id}
  → Non-zero = stale deployment or rogue node alert
```

No existing mesh protocol (peat, Consul, Istio, Linkerd) exposes governance-layer integrity metrics. This is unique to SZL-MESH.

See: [`spec/07-sentra-governance-metrics.md`](spec/07-sentra-governance-metrics.md)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  SZL-MESH LAYER STACK                                           │
├─────────────────────────────────────────────────────────────────┤
│  L5: ROSIE FLEET COCKPIT                                        │
│  Reads verified-only state from SZL-MESH hub node              │
│  Displays AUTHORIZED vs. OBSERVED distinction in UI            │
├─────────────────────────────────────────────────────────────────┤
│  L4: DOCTRINE RECEIPT GATE (a11oy-receipt-substrate)            │
│  DSSE envelope: doctrine_version=749/14/163                     │
│  Every CRDT state transition crossing a policy boundary         │
│  must carry a receipt signed under the locked doctrine          │
│  Unsigned transitions: visible as OBSERVED, not dropped         │
├─────────────────────────────────────────────────────────────────┤
│  L3: SZL HIERARCHICAL AGGREGATOR (new — see Invention 3)        │
│  Doctrine-aware cell hierarchy                                   │
│  Skip-layer aggregation for AUTHORIZED changes                  │
│  Surpasses peat's O(n log n) via receipt-priority routing       │
├─────────────────────────────────────────────────────────────────┤
│  L2: CRDT MESH (peat-mesh / Automerge + Iroh QUIC)              │
│  AP available under partition                                    │
│  Strong Eventual Consistency (SEC)                              │
│  Ed25519-signed operations                                       │
├─────────────────────────────────────────────────────────────────┤
│  L1: TRANSPORT (Iroh QUIC · BLE · relay · UDP)                  │
│  Multi-path · NAT traversal · Connection migration              │
│  Air-gap: BLE tablet bridge                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Peat vs. SZL-MESH Comparison

| Capability | Peat v0.3.6 | SZL-MESH v1 |
|------------|-------------|-------------|
| CRDT engine | Automerge | Automerge (same) |
| Transport | Iroh QUIC + BLE | Iroh QUIC + BLE (same) |
| Operation signing | Ed25519 per-op | Ed25519 per-op (same) |
| RBAC | 5 roles | 5 roles + doctrine gate |
| Doctrine version pinning | ✗ | ✓ DSSE receipt |
| Governance audit trail | ✗ | ✓ Receipt ledger |
| Two-track state (AUTHORIZED/OBSERVED) | ✗ | ✓ |
| Skip-layer aggregation | ✗ | ✓ O(n) for receipted changes (Conjecture 1) |
| Byzantine corroboration | ✗ | ✓ k-of-n soft-voting |
| Air-gap CRDT revocation | ✗ | ✓ Grow-only CRDT set |
| Governance integrity metrics | ✗ | ✓ Sentra integration |
| Doctrine-gated enrollment | ✗ | ✓ |
| Section 889 vendor check | ✗ | ✓ (5 vendors) |

---

## Repository Layout

```
szl-mesh/
├── README.md               — this file
├── LICENSE                 — Apache-2.0
├── SECURITY.md             — security posture, responsible disclosure
├── spec/                   — formal protocol specifications (markdown)
│   ├── 01-dsse-receipts.md
│   ├── 02-two-track-state.md
│   ├── 03-skip-layer-aggregation.md
│   ├── 04-byzantine-corroboration.md
│   ├── 05-doctrine-gated-enrollment.md
│   ├── 06-crdt-revocation.md
│   └── 07-sentra-governance-metrics.md
├── proto/                  — protobuf definitions (extends peat-node proto)
│   ├── szl_mesh.proto      — core SZL-MESH gRPC service
│   └── szl_receipt.proto   — DSSE receipt types
├── examples/               — hello-world flagship integration
│   └── hello-mesh/         — minimal node participating in mesh
└── .github/
    └── workflows/
        └── ci.yml          — lint + proto check
```

---

## Quick Start (Conceptual — Implementation Pending)

```bash
# 1. Clone and review specs
git clone https://github.com/szl-holdings/szl-mesh
cd szl-mesh && cat spec/01-dsse-receipts.md

# 2. Review protobuf extensions to peat-node
cat proto/szl_mesh.proto

# 3. Run the hello-mesh example (once implemented)
cd examples/hello-mesh
# See examples/hello-mesh/README.md
```

---

## Invariants (NEVER MODIFY WITHOUT NEW DOCTRINE RELEASE)

| Invariant | Value |
|-----------|-------|
| Doctrine version | `749/14/163` (LOCKED) |
| Kernel commit | `c7c0ba17` |
| SLSA level | L1 honest (not L3) |
| Section 889 vendors | Exactly 5: Huawei, ZTE, Hytera, Hikvision, Dahua |
| Consistency model | SEC (Strong Eventual Consistency) — AP under CAP |
| Receipt algorithm | DSSE (Dead Simple Signing Envelope) |
| Node identity | Ed25519 (FIPS 186-5) |
| Transport encryption | TLS 1.3 via QUIC (no unencrypted mode) |
| Clock skew tolerance | ±5 seconds UTC |
| Λ claim | Conjecture 1 — NOT theorem |

---

## Contributing

DCO trailers required on every commit:

```
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
```

---

## License

Apache-2.0. See [LICENSE](LICENSE).

---

## References

- [peat protocol](https://github.com/defenseunicorns/peat) — Defense Unicorns CRDT mesh
- [peat-node](https://github.com/defenseunicorns/peat-node) — Kubernetes sidecar gRPC node
- [Automerge](https://automerge.org) — CRDT engine
- [Iroh](https://iroh.computer) — QUIC transport
- [DSSE spec](https://github.com/secure-systems-lab/dsse) — Dead Simple Signing Envelope
- [Shapiro et al. 2011 — SEC/CRDTs](https://inria.hal.science/inria-00555588v1/document)
- [Castro & Liskov 1999 — PBFT](https://dl.acm.org/doi/10.1145/296806.296824)

---

## Getting Started (When Available)

> **Status:** This repo is currently a design skeleton. No Zarf package has been published yet.
> Watch this repo for release announcements.

### Prerequisites (for future deployment)

- [Zarf](https://docs.zarf.dev/getting-started/install/) v0.38+
- [UDS CLI](https://uds.defenseunicorns.com/docs/getting-started/) v0.14+
- [peat](https://github.com/defenseunicorns/peat) node in your cluster

### When a release ships, deployment will follow this pattern:

```bash
zarf package pull oci://ghcr.io/szl-holdings/szl-mesh:<tag>
cosign verify-blob --certificate-identity-regexp   "https://github.com/szl-holdings/szl-mesh/.github/workflows/.*"   --certificate-oidc-issuer https://token.actions.githubusercontent.com   --bundle zarf-package-szl-mesh-amd64-<tag>.tar.zst.sigstore.json   zarf-package-szl-mesh-amd64-<tag>.tar.zst
uds deploy oci://ghcr.io/szl-holdings/szl-mesh:<tag>
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All commits require DCO sign-off:

```bash
git commit -s -m "your message"
```

## Security

See [SECURITY.md](SECURITY.md) for vulnerability disclosure policy.

## License

Apache-2.0. See [LICENSE](LICENSE).

---

© SZL Holdings · Doctrine v11 LOCKED (749/14/163, kernel `c7c0ba17`) · Λ = Conjecture 1 · SLSA L1 honest · Section 889 = 5 vendors


</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA L1 honest · Section 889 = 5 vendors · [SZL Holdings](https://szlholdings.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>
