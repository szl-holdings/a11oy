<!-- SPDX-License-Identifier: Apache-2.0 -->
# vsp-otel · `runtime/src/otlp` — real OTLP/HTTP-JSON export (F4)

This package gives vsp-otel a **real OpenTelemetry exporter**. It converts the
repo from a bespoke span verifier into something that speaks the OTLP wire format
that standard OpenTelemetry collectors understand.

## Modules

| File | Role |
|------|------|
| `exporter.ts` | `VspOtlpExporter` (OTel-style `export(spans, cb)`), `toOtlpJson()` encoder, AnyValue attribute encoding, ns-timestamp encoding |
| `collector.ts` | `parseOtlpJson()` — the inverse decoder, for collector-side round-trip re-verification |
| `exporter.test.ts` | 10 vitest cases |

## What it produces

A spec-shaped `ExportTraceServiceRequest`:

```
resourceSpans[]
 └─ resource.attributes (AnyValue)
 └─ scopeSpans[]
     └─ scope { name: "@szl/vsp-otel", version }
     └─ spans[]
         └─ traceId, spanId, name, kind,
            startTimeUnixNano (string), endTimeUnixNano (string),
            attributes (AnyValue[]), status { code }
```

64-bit integers and nanosecond timestamps are encoded as **strings** per the
OTLP/HTTP-JSON encoding. The SZL anchor-formula attributes
(`szl.anchor_formula.id`, `szl.lean_theorem_ref`, `szl.lean_commit_sha`) survive
the encode→decode round-trip.

## Honesty boundaries (declared, never faked)

- **Transport is injectable.** The default transport captures the request
  **in-process and opens no socket**, keeping CI hermetic. A real `fetch()`-based
  transport activates **only** when an endpoint is supplied (constructor arg or
  `VSP_OTLP_ENDPOINT`).
- **No fake green.** A failing transport yields `ExportResultCode.FAILED` with the
  underlying error — it is never reported as success.
- **DSSE + Λ-state are separate.** The DSSE envelope binding and the Welford/Kalman
  streaming Λ-state estimator (architecture items F3/F5/F13) land in
  `feat/dsse-welford`, intentionally decoupled from the wire-format exporter.
- **Λ = Conjecture 1**, never a theorem. Doctrine v11 LOCKED 749/14/163 @ `c7c0ba17`
  is unchanged. SLSA L1 honest.

## Usage

```ts
import { VspOtlpExporter } from "./otlp/exporter.js";

const exporter = new VspOtlpExporter({ endpoint: process.env.VSP_OTLP_ENDPOINT });
exporter.export(spans, (result) => {
  if (result.code !== 0) console.error("export failed", result.error);
});
```
