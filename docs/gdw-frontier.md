# Governed Delta Workspace operational harness

GDW binds an authenticated FastAPI control surface to deny-by-default routing,
SQLite WAL state, idempotency keys, A11oy's receipt substrate, structured theorem
inputs, load tooling, and an offline evidence dashboard.

## Truth boundary

> GDW Frontier Push Pack is a MODELED instrumentation and verification extension for the Governed Delta Workspace. It provides load testing, operator validation, hybrid scheduling research hooks, KDA-vs-MLA memory benchmarking, and Lean-oriented proof export. It does not claim frontier benchmark superiority, proprietary activation access, or production-scale guarantees beyond the measured harness outputs.

The implementation is real code. Each benchmark remains `UNMEASURED` until its
own output is captured. Exporting a theorem input is not a proof; Lean results are
reported separately. The control API chooses a route but does not claim that a
model kernel ran. The optional Torch dispatcher and memory benchmark are the
executable kernel-facing surfaces.

For high-volume runs, `GDW_PROOF_EXPORT_MODE=outbox` atomically stores theorem
inputs in SQLite and a separate drain writes the JSON files. The default `sync`
mode writes each artifact before returning and is used by the Postman flow.

## Runtime

Set `GDW_AUTH_TOKEN`, `GDW_DB_PATH`, and `GDW_PROOF_DIR`, then start `serve:app`.
Every write requires `Authorization: Bearer ...` and a unique `X-Request-Id`.
Reusing an id with identical content replays the prior response; changing the
content returns HTTP 409.

Routes:

- `GET /api/a11oy/v1/gdw/healthz`
- `GET /api/a11oy/v1/gdw/bench/meta`
- `GET /api/a11oy/v1/gdw/metrics`
- `GET /api/a11oy/v1/gdw/integrity`
- `GET /api/a11oy/v1/gdw/sessions/{session_id}`
- `POST /api/a11oy/v1/gdw/step`

## Research lineage

- Kimi Linear technical report: https://yzhang.site/assets/pubs/techreport/2025/kda.pdf
- Gated DeltaNet paper and code: https://arxiv.org/abs/2412.06464
- Laguna technical report: https://arxiv.org/abs/2605.27605
- TorchLean: https://github.com/lean-dojo/TorchLean

These references motivate measurable routes and proof-compatible boundaries.
They are not evidence that this implementation achieves the cited model results.
