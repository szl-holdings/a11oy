# UDS-Mesh SDK

Λ-signed cross-organ OpenTelemetry span emission for the five SZL organs, with
BLS-aggregated batch receipts. Two parity implementations: `mesh.py` (Python) and
`mesh.ts` (TypeScript). Both produce the identical `szl.mesh.*` governance envelope
defined in [`../../schemas/spans/`](../../schemas/spans).

## What it does

1. **W3C Trace Context** — `TraceContext` parses/formats `traceparent` per the
   [W3C Trace Context REC](https://www.w3.org/TR/trace-context/) (version-00,
   32-hex trace-id / 16-hex span-id / 8-bit flags); rejects all-zero ids.
2. **Λ-signed spans** — every emitted span carries the cross-organ envelope
   (`szl.mesh.organ`, `szl.mesh.receipt_hash`, `szl.mesh.dsse_payload_type`,
   `szl.mesh.lambda_value`, `szl.mesh.governance_drift`) and a DSSE PAE v1 receipt
   (HMAC-SHA-256 dev signer; same PAE scheme as `formula_receipts.py`).
3. **BLS aggregate batch receipts** — a whole batch of mesh receipts verifies with
   **one** aggregate signature check instead of N, modelling the sorry-free Lean
   theorem `Lutar.Round11.BLS.aggregate_verify` (lutar-lean open PR #180):
   `Σ σ_i = (Σ sk_i)·h`. `verify_batch` / `verifyBatch` is an independent verifier
   that recomputes the RFC 6962 Merkle root and confirms the aggregate covers
   exactly the emitted receipts (and detects tampering).

## Python

```python
from mesh.sdk import MeshEmitter, TraceContext, verify_batch

e = MeshEmitter("sentra")
root = TraceContext.new_root()
e.emit("sentra.gate.evaluate", lambda_value=0.91, trace=root)
e.emit("sentra.gate.attest",  lambda_value=0.95, trace=root.child(),
       parent_span_id=root.span_id)

agg   = e.batch_aggregate()          # one BLS aggregate over the batch
spans = e.drain()                    # OTEL-shaped dicts ready for export
assert verify_batch(spans, agg, "mesh:sentra")
```

## TypeScript

```ts
import { MeshEmitter, TraceContext, verifyBatch } from "./mesh.js";

const e = new MeshEmitter("sentra");
const root = TraceContext.newRoot();
e.emit("sentra.gate.evaluate", 0.91, { trace: root });
e.emit("sentra.gate.attest", 0.95, { trace: root.child(), parentSpanId: root.spanId });

const agg = e.batchAggregate();
const spans = e.drain();
console.assert(verifyBatch(spans, agg, "mesh:sentra"));
```

## Honest crypto boundary

The BLS aggregation here is implemented over a prime-field additive homomorphism
that exercises the **same algebraic identity** proved in Lean (`Σ σ_i` vs
`(Σ sk_i)·h`). Production swaps `_BLSBackend` for `blst`/`py_ecc` BLS12-381; the
`aggregate_verify` contract is identical. Runtime coordinate:
`szl-holdings/amaru/szl_bls_aggregate.py`. This is disclosed, not hidden (HR-6).

## Formal references (lutar-lean, all in OPEN PRs)

- BLS batch verify — `Lutar.Round11.BLS.aggregate_verify`, `agg_sig_eq_agg_key_sig`,
  `pairing_strict_savings` — `Lutar/Innovations/round11/FrontierBLSAggregation.lean`
  (PR #180, sorry-free).
- Λ is **Conjecture 1**, never a theorem.

## Conformance

`pytest mesh/conformance/ -v` — validates all five schemas + that the SDK emits
spans conforming to them + BLS round-trip and tamper detection. 33 tests.
