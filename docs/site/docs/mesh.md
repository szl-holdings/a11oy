---
title: "UDS Mesh — the nervous system"
description: "The 7-organ trace + receipt mesh: what is LIVE, what is in-process, what is roadmap."
outline: deep
---

# UDS Mesh — the nervous system

The SZL substrate is modeled as a body. Five flagship organs ship in the UDS bundle
(**a11oy**, **sentra**, **amaru**, **rosie** + **killinchu**-when-unblocked); two
structural organs complete the anatomy (**skeleton** = vessels / deployment fabric,
**wires** = the W3C-`traceparent` nervous signal). The mesh is the **nervous system**
that carries trace context + DSSE receipts between them.

::: tip Honest status legend
`LIVE` = wired and verified in-process · `IN-PROC` = real within a single organ, not
cross-pod · `ROADMAP` = v0.4.0, not shipped. **Honesty over checklist.**
:::

```mermaid
flowchart TB
    classDef live fill:#0f3a2e,stroke:#5ad1c0,color:#e8eef7;
    classDef inproc fill:#2a3550,stroke:#7aa2ff,color:#e8eef7;
    classDef roadmap fill:#3a2f0f,stroke:#e0c060,color:#e8eef7;

    subgraph BODY["SZL UDS substrate — anatomy"]
      direction TB
      ROSIE["🧠 brain / nervous-cortex<br/><b>rosie</b> — operator console<br/>rosie.decision.*<br/>(issues commands)"]:::inproc
      A11OY["❤️ heart / switch-fabric<br/><b>a11oy</b> — policy + receipt substrate<br/>a11oy.graph.* · /honest · MCP tools<br/>Wire D traceparent + DSSE Khipu DAG"]:::live
      AMARU["🩸 blood / memory cortex<br/><b>amaru</b> — convergent sync<br/>amaru.sync.* (KL-drift bounded)"]:::inproc
      SENTRA["🛡️ immune system<br/><b>sentra</b> — fail-closed safety gate<br/>sentra.gate.* (ALLOW/DENY)"]:::live
      KILLINCHU["📡 nervous / courier<br/><b>killinchu</b> — receipt relay<br/>killinchu.courier.*<br/>(PRIVATE — not in bundle)"]:::roadmap
      VESSELS["🦴 skeleton / deployment fabric<br/><b>vessels</b> — structural proving ground<br/>(deprecated sibling of killinchu)"]:::roadmap
      WIRES["🔌 wires / W3C trace context<br/>traceparent: 00-&lt;trace&gt;-&lt;span&gt;-01<br/>tracestate: szl=&lt;span&gt;"]:::live
    end

    RECEIPTS["📜 szl-receipts<br/>DSSE Khipu Merkle DAG<br/>(receipt sink)"]:::inproc

    ROSIE -->|"Wire C: /v1/events + Khipu ingest (IN-PROC)"| A11OY
    A11OY -->|"Wire B: /v1/verdict + /v1/inspect (IN-PROC)"| SENTRA
    A11OY -->|"Wire E: SSE cortex-subscribe (IN-PROC ring buffer)"| AMARU
    A11OY -->|"Wire F: /v1/receipts/ingest (IN-PROC)"| VESSELS
    KILLINCHU -.->|"courier relay (ROADMAP)"| RECEIPTS
    A11OY -->|"DSSE receipt (traceparent embedded) — LIVE"| RECEIPTS
    SENTRA -->|"gate verdict receipt — LIVE"| RECEIPTS

    WIRES -.->|"traceparent on every request (LIVE in-process)"| ROSIE
    WIRES -.-> A11OY
    WIRES -.-> AMARU
    WIRES -.-> SENTRA
```

## Wire status table (verified 2026-06-03)

| Wire | Edge | What it carries | Status |
|---|---|---|---|
| **B** | a11oy ↔ sentra (immune) | gate verdict / inspect | **LIVE (in-process)** |
| **C** | a11oy ↔ rosie (receipt stream) | decision events + Khipu ingest | **LIVE (in-process)** |
| **D** | W3C traceparent | real trace-id/span-id generation + propagation | **LIVE in-process; cross-Space broker NOT wired** |
| **E** | a11oy ↔ amaru (cortex sync) | brand-decision SSE events | **LIVE (in-memory ring buffer)** |
| **F** | a11oy ↔ vessels (receipts) | DSSE receipts into Khipu DAG | **LIVE (in-process)** |
| OTLP | any organ → collector | OTEL span export | **NOT WIRED — schema only (roadmap)** |
| cross-pod | organ ↔ organ over k8s Service | mTLS service mesh (Istio Package CR) | **ROADMAP v0.4.0** (verified: in-cluster sentra→a11oy ClusterIP times out today) |

## What is real vs. aspirational

**Real, verified live (2026-06-03):**

- Every organ emits **real W3C trace context** — `traceparent: 00-<trace>-<span>-01`,
  `tracestate: szl=<span>`, plus an `x-szl-wire-d: LIVE` marker — on every HTTP response.
  Incoming `trace_id` is preserved across the request (propagation verified).
- **a11oy** binds that traceparent into every **DSSE Khipu receipt** envelope (verified
  by decoding the base64 DSSE payload — the traceparent is embedded).
- Span **schemas** are published and shared under a `szl.mesh.*` envelope
  (`a11oy.graph`, `sentra.gate`, `amaru.sync`, `rosie.decision`, `killinchu.courier`).
- In-cluster proof: **a11oy + sentra both run 1/1 Ready** in the `szl-stress` kind
  cluster; a11oy serves `{"status":"ok"}` on port 7860.

**Honest gaps (not yet wired):**

- **No OTLP export.** No `opentelemetry` package, no exporter, no collector — spans are a
  documented schema, not a live telemetry signal.
- **DSSE receipts are UNSIGNED** today (`signatures: []`) — the cosign private key
  (`SZL_COSIGN_PRIVATE_PEM`) is not present in the runtime.
- **Cross-pod organ traffic is NOT wired.** An in-cluster `sentra → a11oy` ClusterIP call
  times out; there is no Istio `Package` CR / service-discovery wiring in the bundle charts.

> Until modules actually call each other across pods and spans are exported, this is a
> **live in-process governance signal**, not distributed telemetry — honestly short of a
> full service mesh. See `uds-bundles/mesh/docs/roadmap/MESH_INTERCONNECT.md`.

---

*Sources:
[`uds-bundles/mesh/schemas/spans/`](https://github.com/szl-holdings/uds-bundles/tree/main/mesh/schemas/spans),
[`MESH_INTERCONNECT.md`](https://github.com/szl-holdings/uds-bundles/blob/main/mesh/docs/roadmap/MESH_INTERCONNECT.md),
and the flagship `szl_provenance.py` / `szl_wire.py` runtime. Verified live by the
uds-fully-operational squad. Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED ·
SLSA L1 honest · Section 889 = 5 vendors.*
