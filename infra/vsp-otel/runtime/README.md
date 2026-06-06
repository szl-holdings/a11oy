# vsp-otel

**Operationalizes:** VSP — Λ-signed OTel Span Exporter  
**Repo:** szl-holdings/vsp-otel  
**Path:** ./ (root)

## What it does

Wraps an OpenTelemetry span pipeline with a Λ-signing layer. Every span exported through this module receives:

1. Axis score derivation from span attributes (`lambda.*` attribute namespace)
2. Λ-gate evaluation (uses `@szl/ouroboros-lambda-gate` as upstream)
3. A SHA-256 receipt hash stored in the gate's receipt store if `pass=true`

### Span attribute convention

Encode axis scores as span attributes with the `lambda.` prefix:

```
lambda.moralGrounding = 0.96
lambda.measurabilityHonesty = 0.95
...
```

Missing axes default to `0.90` (gate floor).

## HTTP endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spans/verify` | Sign span(s) and return `{lambda, axes, pass}` |
| `POST` | `/spans/export` | Batch export; returns `{total, passed, failed}` |
| `GET`  | `/spans/:hash`  | Retrieve stored receipt for a span hash |

### Example `/spans/verify` response

```json
{
  "spanId":      "span-001",
  "lambda":      0.923,
  "axes":        { "moralGrounding": 0.96, ... },
  "pass":        true,
  "receiptHash": "a3f1..."
}
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `VSP_PORT` | `3004` | HTTP listen port |

## Upstream dependency

`@szl/ouroboros-lambda-gate` — receipt storage and gate evaluation.

## Install & test

```bash
pnpm install
pnpm test
# Start server
VSP_PORT=3004 node dist/server.js
```
