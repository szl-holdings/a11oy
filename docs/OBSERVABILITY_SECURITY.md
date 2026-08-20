# Observability security boundary

A11oy separates W3C trace propagation from OTLP export delivery. Propagation can be ready while export remains in-process-only; neither state is a proof, receipt, model run, or deployment attestation.

OTLP export is disabled unless the operator configures an endpoint that passes admission:

- `http` or `https` only;
- no URL credentials, query, fragment, or non-root path;
- loopback/private IP literals are accepted;
- DNS names require an exact `A11OY_OTEL_ALLOWED_HOSTS` entry;
- public IP literals are rejected;
- the status surface exposes only a SHA-256 endpoint fingerprint, never the endpoint or credentials.

The built-in status read is `GET /api/a11oy/v1/observability/status`. It mints no receipt. A configured exporter means an exporter was constructed; it does not claim that a collector received or persisted a span. Delivery requires collector-side evidence.

The traceparent parser accepts only the stable lowercase W3C v00 shape with non-zero trace/span IDs and flags `00` or `01`. Unknown versions are refused until a version-specific parser is implemented.
