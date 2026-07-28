# Governed Delta Workspace operational harness

Runtime status: `UNAVAILABLE`.

The GDW paths remain registered so requests cannot fall through to a generic
proxy or application shell. Apart from health, each operational path returns
HTTP 503 with the stable reason `GDW_CONSOLIDATION_REQUIRED` before
authentication, database initialization, telemetry, receipt creation, or proof
export. Setting GDW environment variables cannot enable the surface.

## Truth boundary

> GDW Frontier Push Pack is a MODELED instrumentation and verification extension for the Governed Delta Workspace. It provides load testing, operator validation, hybrid scheduling research hooks, KDA-vs-MLA memory benchmarking, and Lean-oriented proof export. It does not claim frontier benchmark superiority, proprietary activation access, or production-scale guarantees beyond the measured harness outputs.

The implementation and isolated harness evidence remain in the repository for
audit, but they are not an available service. Each benchmark remains
`UNMEASURED` until its own output is captured. Exporting a theorem input is not a
proof; Lean results are reported separately. Prior local harness results do not
establish production readiness.

## Runtime

Routes:

- `GET /api/a11oy/v1/gdw/healthz`
- `GET /api/a11oy/v1/gdw/bench/meta`
- `GET /api/a11oy/v1/gdw/metrics`
- `GET /api/a11oy/v1/gdw/integrity`
- `GET /api/a11oy/v1/gdw/sessions/{session_id}`
- `POST /api/a11oy/v1/gdw/step`

`GET /api/a11oy/v1/gdw/healthz` reports `UNAVAILABLE`, `write_ready=false`,
and `external_effects=DISABLED`. Every other route above and its `/v1/gdw`
alias returns the same truth-labeled 503 hold.

Restoring service requires one canonical GDW implementation with:

- caller authentication, persistent ownership, authorization on every object,
  per-owner and global quotas, and explicit retention/reclamation;
- the canonical governance gateway, rather than local risk thresholds;
- state, request, receipt intent, and proof intent committed in one durable
  transaction, with external receipt/proof publication performed from
  retry-safe outboxes;
- conflict-free route ownership and exact regression evidence for rollback,
  replay, concurrency, and partial publication failures.

## Research lineage

- Kimi Linear technical report: https://yzhang.site/assets/pubs/techreport/2025/kda.pdf
- Gated DeltaNet paper and code: https://arxiv.org/abs/2412.06464
- Laguna technical report: https://arxiv.org/abs/2605.27605
- TorchLean: https://github.com/lean-dojo/TorchLean

These references motivate measurable routes and proof-compatible boundaries.
They are not evidence that this implementation achieves the cited model results.
