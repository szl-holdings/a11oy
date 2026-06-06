# Integrating vsp-otel — "your existing OTel SDK already works"

`vsp-otel` is an **OTLP/HTTP collector exporter shim**. It speaks the standard
OpenTelemetry OTLP protocol, so **you do not change your application code**. You
already emit spans with an OTel SDK; you just point that SDK's OTLP exporter at
vsp-otel instead of (or in front of) your existing backend.

```
 your app  ──OTLP──▶  vsp-otel  ──(Λ ≥ 0.90, DSSE-signed)──▶  Tempo / Jaeger / collector
 (any lang, OTel SDK)   :4318                                   (your existing backend)
```

## 1. Just change the endpoint

### OpenTelemetry Collector (recommended in front of your existing pipeline)
```yaml
exporters:
  otlphttp/vsp:
    endpoint: http://vsp-otel.observability.svc:4318
service:
  pipelines:
    traces:
      exporters: [otlphttp/vsp]   # was: [otlphttp/tempo]
```

### Python SDK
```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="http://vsp-otel:4318/v1/traces")
```

### Node SDK
```ts
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
const exporter = new OTLPTraceExporter({ url: "http://vsp-otel:4318/v1/traces" });
```

### Environment-variable form (works for every OTel SDK)
```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://vsp-otel:4318/v1/traces
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf   # or http/json
```

## 2. What vsp-otel does to each span

1. **Computes Λ** over the span's A1–A5 attributes (geometric mean, Λ Conjecture 1).
   Provide axis scores as span attributes; missing axes default to the floor:
   `lambda.a1` … `lambda.a5` (also accepts `lambda.moral_grounding`, …).
2. **Rejects** spans with `Λ < LAMBDA_FLOOR` (default **0.90**, the a11oy doctrine
   constant). Rejected spans are dropped (fail-closed) and counted in `/metrics`.
3. **Signs** accepted spans with a **DSSE in-toto attestation** and stamps the span
   with `szl.dsse.receipt_hash` + `szl.dsse.keyid`. Production uses cosign keyless
   OIDC (Fulcio + Rekor); dev uses ECDSA P-256 or an HMAC fallback.
4. **Tracks** span-latency online mean/variance (Welford) and unique-trace
   cardinality (HyperLogLog) — exposed at `/metrics` (Prometheus text format).
5. **Forwards** accepted+signed spans to `VSP_FORWARD_ENDPOINT`
   (Tempo / Jaeger / any OTLP/HTTP collector).

## 3. Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/traces` | OTLP/HTTP trace ingest (the OTel standard path) |
| GET | `/healthz` | liveness/readiness; reports `lambda_floor` |
| GET | `/metrics` | Prometheus metrics (`vsp_spans_total`, `vsp_lambda_floor`, `vsp_span_latency_ms_mean`, `vsp_unique_traces_estimate`) |

## 4. Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `LAMBDA_FLOOR` | `0.90` | reject spans below this Λ |
| `VSP_FORWARD_ENDPOINT` | _(unset)_ | downstream OTLP/HTTP endpoint |
| `VSP_SIGN_MODE` | `auto` | `auto` \| `ecdsa` \| (cosign keyless in prod) |
| `VSP_SIGN_KEY_PEM` | _(unset)_ | ECDSA P-256 private key PEM |
| `PORT` | `4318` | listen port |

## 5. Deploy

```bash
# Docker
docker build -t ghcr.io/szl-holdings/vsp-otel:0.1.0 .
docker run -p 4318:4318 -e VSP_FORWARD_ENDPOINT=http://tempo:4318/v1/traces \
  ghcr.io/szl-holdings/vsp-otel:0.1.0

# Kubernetes (Helm)
helm install vsp-otel ./deploy/helm/vsp-otel \
  --set forwardEndpoint=http://tempo.observability.svc:4318/v1/traces
```
