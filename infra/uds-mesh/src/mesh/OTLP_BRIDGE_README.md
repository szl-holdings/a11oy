# OTLP bridge (WU-3)

`src/mesh/otlp_bridge.py` is a **thin integration layer** that bridges uds-mesh's
in-process span dicts into the OTLP/HTTP-JSON `ExportTraceServiceRequest` shape and
hands the batch to the vsp-otel Λ-gate exporter/collector.

It lands in the **canonical home `szl-holdings/uds-mesh`** per **ADR-0001**.

## HONESTY OVER CHECKLIST

- The authoritative OTLP **wire encoder/exporter** is in `szl-holdings/vsp-otel`
  (`runtime/src/otlp/exporter.ts`, PR #61 `feat/real-otlp-exporter`). This module
  **does not reimplement** that wire format — it produces a compatible request and
  delegates transport.
- The OTLP/HTTP-JSON encode→decode here is **REAL** and round-trips
  (resourceSpans → scopeSpans → spans; ns timestamps as strings). SZL anchor attrs
  (`szl.anchor_formula.id`, `szl.lean_commit_sha`, `szl.mesh.organ`) survive.
- **No network in CI:** `transport` defaults to an in-proc collector handler; the
  real HTTP transport is used only when `MESH_OTLP_ENDPOINT` is set.
- The batch DSSE receipt reuses `pinn_dsse.sign_payload` — UNSIGNED marker when the
  cosign key is absent (never a fabricated signature).

## Usage

```python
from mesh.otlp_bridge import OtlpBridge
bridge = OtlpBridge()                      # in-proc transport (CI-safe)
res = bridge.export([{"trace_id": "...", "span_id": "...", "name": "rosie.decision.evaluate",
                      "start_ns": 0, "end_ns": 0, "attributes": {"szl.mesh.organ": "rosie"}}])
# res == {"code": "SUCCESS", "accepted": 1, "batch_receipt": {...DSSE...}}
```

Tests: `pytest tests/test_otlp_bridge.py`.

---

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem).

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
