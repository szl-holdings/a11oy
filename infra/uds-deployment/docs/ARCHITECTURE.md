# SZL UDS Architecture — How SZL Sits Next to uds-core

**Doctrine:** No source-level coupling. AGPL-safe. Network-only communication.

---

## Cluster Layout

```
┌─────────────────────────── k3d cluster: uds-szl-demo ──────────────────────────┐
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        uds-core (slim-dev)                               │   │
│  │                                                                          │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │   │
│  │  │  istio-system   │  │   pepr-system    │  │  monitoring (Prom)     │  │   │
│  │  │  (ambient mesh) │  │  ┌────────────┐  │  │  (optional slim-dev)   │  │   │
│  │  │                 │  │  │ pepr-       │  │  │                        │  │   │
│  │  │  ┌───────────┐  │  │  │ admission  │  │  └────────────────────────┘  │   │
│  │  │  │ tenant    │  │  │  └────────────┘  │                              │   │
│  │  │  │ gateway   │  │  │  ┌────────────┐  │                              │   │
│  │  │  └─────┬─────┘  │  │  │ pepr-      │  │                              │   │
│  │  │        │        │  │  │ watcher    │  │                              │   │
│  │  └────────│────────┘  │  └────────────┘  │                              │   │
│  │           │           └────────┬─────────┘                              │   │
│  └───────────│───────────────────┬│────────────────────────────────────────┘   │
│              │                   ││                                             │
│              │            Admission webhook                                     │
│              │            (HTTP → szl-receipts:8443)                            │
│              │                   ││                                             │
│              │       ┌───────────▼▼───────────────────────────────────┐        │
│              │       │           szl-receipts namespace                │        │
│              │       │                                                 │        │
│              │       │  ┌──────────────────────────────────────────┐  │        │
│              │       │  │ szl-receipts-server (python:3.12-slim)   │  │        │
│              │       │  │  ┌──────────────────────────────────┐    │  │        │
│              │       │  │  │ POST /receipt  ← Pepr webhook    │    │  │        │
│              │       │  │  │ GET  /receipts ← dashboard/SIEM  │    │  │        │
│              │       │  │  │ GET  /stream   ← SSE feed        │    │  │        │
│              │       │  │  │ GET  /metrics  ← Prometheus      │    │  │        │
│              │       │  │  │ GET  /health   ← K8s probes      │    │  │        │
│              │       │  │  └──────────────────────────────────┘    │  │        │
│              │       │  │                                           │  │        │
│              │       │  │  [nginx sidecar]  ← dashboard HTML       │  │        │
│              │       │  └──────────────────────────────────────────┘  │        │
│              │       │                                                 │        │
│              │       │  UDS Package CR → Istio VirtualService →       │        │
│              └───────┤  tenant gateway exposes szl.uds.dev            │        │
│                      │                                                 │        │
│                      └─────────────────────────────────────────────────┘        │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    szl-demo-workload namespace                          │     │
│  │   Deployment/szl-demo-agent  ──annotated──►  szl.receipt.id: a3f2b1…  │     │
│  │   Job/szl-demo-job            ──annotated──►  szl.receipt.id: b4c3d2…  │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Receipt Flow (sequence)

```
User/CI                  Kubernetes API       Pepr Admission         SZL Receipts Server
   │                           │                    │                        │
   │── kubectl apply ──────────►│                    │                        │
   │                           │── admission req ───►│                        │
   │                           │                    │── compute specHash      │
   │                           │                    │── build DSSE envelope   │
   │                           │                    │── SetAnnotation(        │
   │                           │                    │     szl.receipt.id,…)   │
   │                           │◄── mutated obj ────│                        │
   │                           │── write etcd        │                        │
   │                           │                    │── POST /receipt ───────►│
   │                           │                    │                        │── verify HMAC
   │                           │                    │                        │── store receipt
   │                           │                    │                        │── SSE broadcast
   │                           │                    │◄── {id, valid} ────────│
   │                           │                    │── Log receipt.id        │
   │                           │                    │                        │
   │  Browser / SIEM           │                    │                        │
   │── GET /stream ────────────────────────────────────────────────────────►│
   │◄── SSE: {id, envelope, valid} ─────────────────────────────────────────│
```

---

## Why This is AGPL-Safe

| Concern | Status | Reason |
|---------|--------|--------|
| Modifies uds-core source | No | Add-on ships as a separate Zarf package |
| Links against AGPL library at build time | No | No uds-core Go/TS code imported |
| Runs in the same process as AGPL code | No | Separate pods, separate namespace |
| Communicates with AGPL service via network | Yes (Pepr webhook) | Network communication is explicitly permitted under AGPL §13 |
| Bundles AGPL binaries in the Zarf package | No | Only includes the szl-receipts server and Pepr policy |

The Pepr policy references `pepr` (the npm package, Apache-2.0 licensed as of v1.x). It does not import any uds-core-specific code.

---

## What SZL Adds vs. What uds-core Provides

| Capability | uds-core | SZL Receipts |
|-----------|----------|--------------|
| Network policy enforcement (Istio) | ✓ | — |
| Pod security standards | ✓ | — |
| Secrets management | ✓ | — |
| K8s admission controller framework (Pepr) | ✓ | Uses it |
| Governance receipt emission on admission | — | ✓ |
| DSSE-wrapped audit trail | — | ✓ |
| Workload annotation with receipt ID | — | ✓ |
| Receipt SSE feed for dashboards/SIEM | — | ✓ |
| Lean theorem cross-link (Phase 2) | — | Phase 2 |

---

## Phase 2 Roadmap

1. **Ed25519 signing** — replace HMAC-SHA-256 with a proper keypair; verify with cosign
2. **Zarf package signing** — cosign-sign the package at build time for supply chain provenance
3. **DoD ATF assessment** — package submission for DoD Platform One assessment
4. **Lean theorem cross-link** — embed a Lean proof reference in each receipt payload
5. **UDS Package CR conformance** — submit a conformance PR to uds-core for szl-receipts
6. **HA mode** — multiple replicas with shared PVC for receipt store

---

*Apache-2.0 | Doctrine v6 strict | https://szlholdings.com*
