# SZL Telemetry Operations Twin

Status: **SOURCE IMPLEMENTED / DEPLOYMENT UNVERIFIED**

This contract defines a common evidence record for the 3D holographic surface, live search, second brain, Hatun, and Living Anatomy. The A11oy route implemented here reports its bounded process-local trace window; cross-service receipt and dataset coverage bindings remain unavailable. A visual state is allowed to say **LIVE** only when the record carries an observed timestamp, source revision, freshness bound, and a receipt or trace link.

## Canonical telemetry envelope

Every dataset, model, kernel, Space, service, organ, trace, span, and UI object uses a stable `canonical_id` and may carry:

- `trace_id`, `span_id`, and parent propagation status
- `source_revision`, provider, source URL, and observed timestamp
- freshness seconds and the next expected refresh time
- dataset/model/kernel identifiers, deployment revision, cohort, action, approval, and outcome
- sampling state, rights/license, and one of `OBSERVED`, `DERIVED`, `INFERRED`, `UNAVAILABLE`
- receipt ID and payload SHA-256; signatures remain explicit and are never inferred

The raw payload is not copied into the second brain. Projections keep bounded summaries, hashes, handles, and links to the source receipt.

## Projection surfaces

- **Holographic 3D:** each node resolves to a canonical object, then to its telemetry state, freshness, coverage, and proof link. Synthetic scene geometry is labeled separately from measured state.
- **Live search:** search returns canonical IDs, object kind, provider, source revision, state, and a safe source link. An empty or unbound catalog is shown as `UNAVAILABLE`.
- **Second brain:** session-scoped observations are receipt-backed and bounded. No external Space or private dataset is treated as live without an observed receipt.
- **Hatun:** evidence admission retains truth labels such as `RUNTIME_DECLARED`, `REPORTED`, `OBSERVED`, and `UNAVAILABLE`; declaration and route presence are never execution proof.
- **Living Anatomy:** organs show telemetry freshness and coverage only when a read-only summary endpoint returns an observed record. Route registration alone remains `UNMEASURED`.

## Dataset reconciliation

The catalog reconciliation lane is bounded to provider metadata and file or revision hashes. It records source revision, rights/license, freshness, and private/unavailable state. It does not mirror private data or model weights into the second brain.

## Current limitations

The local a11oy holographic source now includes explicit Telemetry, Freshness, and Coverage rows and probes the authoritative `/api/a11oy/v1/otel/status` route plus the process-local trace summary. Until the change is deployed and the collector is configured, it correctly displays `DEGRADED` or `UNAVAILABLE`. The existing 3D renderer is real WebGL with a 2D fallback, but measured telemetry still requires the receipt-backed service projection described above.

## Readback links

- Holographic evidence rail: `/api/a11oy/v1/readiness/tab-matrix?view=summary`
- OTel propagation/export status: `/api/a11oy/v1/otel/status`
- Bounded process-local telemetry summary: `/api/a11oy/v1/telemetry/summary`
- Trace ring: `/api/a11oy/v1/observability/traces`
- Hatun evidence: `/api/a11oy/v1/agent/evidence`
- Hatun invocation feed: `/api/a11oy/v1/agent/invocations`
- Build identity: `/api/build-info`
- Receipt verifier: `/verify`
## HTTP trace semantics and release verification

HTTP trace names use registered route templates, never path parameters or query
strings. Inbound W3C trace context is validated before reuse. Opaque request IDs
remain in the existing access logs rather than public trace records. HTTP server
5xx responses are errors; 4xx codes remain recorded without claiming a server
error, following [OpenTelemetry HTTP conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/).
Multiple hardening layers share a single trace per request.

The summary reads completed traces only. Empty windows are UNAVAILABLE;
windows whose newest completion is over 300 seconds old are STALE. The ring
resets on restart. Reads mint no receipt and assert neither collector delivery
nor dataset coverage. Those require independent evidence.

Publish through the existing protected-main hf-sync.yml path. Verify
/api/build-info against the merged revision, then make a harmless request and
read the summary and trace detail. Confirm a registered route template and a
measured duration, and separately verify collector delivery. No DNS or Space
allocation changes are part of this patch.
