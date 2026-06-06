# Consolidation: a11oy is the platform home

Per CEO directive, **a11oy** (`github.com/szl-holdings/a11oy`) is the TRUE consolidated
home of the SZL platform. This repository ingests the real source of the other organs
and shared infrastructure so that a11oy is self-contained — not merely a UI that calls
remote services.

## What lives where

- **`organs/sentra/`** — ingested source of the **policy** organ (Sentra). Includes
  `serve.py`, `console/`, `src/`, `szl_shared_formulas/`, and web/runtime source.
- **`organs/amaru/`** — ingested source of the **reasoning** organ (Amaru). Includes
  `serve.py`, `amaru_cortex_console.py`, `amaru_proof_tabs.py`,
  `amaru_formula_endpoints.py`, `sidecar/`, and `src/amaru/`.
- **`organs/rosie/`** — ingested source of the **operator** organ (Rosie). Includes
  `app.py`, `src/rosie/`, `packages/`, and `szl_router/`.
- **`mcp/`** — shared **MCP** (Model Context Protocol) infra: `mcp_server.py`,
  `test_mcp_stdio.py`, MCP client config, and integration docs.
- **`infra/vsp_otel/`** — shared **OpenTelemetry** middleware (`vsp-otel`): cross-pod
  W3C traceparent propagation + OTLP/gRPC spans, vendored uniformly mesh-wide.

a11oy's own existing files (`serve.py`, `pages/`, `vsp_otel/`, top-level `szl_*.py`,
etc.) are left intact. The ingested organ source is added strictly under the new
top-level directories listed above.

## Honest status (no overclaiming)

- This is a **source-only ingest** for consolidation. The organ code has been copied
  into a11oy; it has **NOT** yet been merged into a single runtime or wired together.
  The commit is *"ingest organ source for consolidation"*, not *"merged and wired"*.
- The **live Hugging Face Spaces** for sentra, amaru, and rosie currently run as
  backends that a11oy's UI calls. They remain the live backends for now and will be
  **retired only after** their endpoints are ported into the consolidated a11oy
  runtime. They are not touched by this ingest.
- Build artifacts, vendored dependencies, and large binaries were **not** ingested
  (see `team/INGEST_REPORT.md` for skip rules and counts).

## Doctrine (unchanged, kept honest)

- Trust score = **Conjecture 1** (a conjecture, not a proven theorem).
- **5 proven formulas** in the cookbook.
- Supply-chain posture: **SLSA Level 2**.

— Stephen P. Lutar Jr. · SZL Holdings
