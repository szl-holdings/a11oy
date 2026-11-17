# Evidence-bound telemetry summary for the 3D operations surface

**State:** implemented in source, awaiting source review, CI, protected-main merge and runtime publication. This is not a production readiness certificate.

## Gap and closure

On 2026-11-16 the deployed `/api/a11oy/v1/telemetry/summary` returned HTTP 404 while the 3D holographic page and `/api/a11oy/v1/otel/status` returned HTTP 200. The 3D evidence rail previously read the build and readiness sources only. This change registers a same-origin, no-store, read-only summary at the missing URL and consumes it in the evidence rail. It intentionally does not claim that the unconfigured OpenTelemetry collector or missing traces are active.

The new `szl.telemetry-summary/v1` payload has `status`, `source_revision`, `otel`, `traces`, `scope`, `read_only`, `receipt_minted`, and `production_authorization`. Only the existing runtime collector-delivery evidence may produce `LIVE`; in-process propagation without a fresh collector observation yields `DEGRADED`. A missing in-process probe is `UNAVAILABLE`. Traces remain explicitly `UNAVAILABLE` until independently admitted, rather than being inferred from an HTTP endpoint or empty ring.

The browser also requires the telemetry source revision to equal the independently fetched build revision. When either binding is missing or the schema is not recognized, it renders `UNAVAILABLE`. Telemetry never upgrades the separate estate-readiness badge.

## System integration boundary

The data path is `szl_runtime_contracts._otel_posture(app)` → `/api/a11oy/v1/telemetry/summary` → `_fetchEvidenceSnapshot()` → `evidence-rail-telemetry` on `static/3d/holographic.html`. It uses the same-origin, no-store JSON read already used for the readiness evidence rail. The backend performs no new upstream lookup, receipt minting, signing, disk write, action, or model inference on GET. All collector freshness rules remain owned by the existing runtime OTel contract.

Future admission of traces, model runs, KALLPA joules, KHIPU verification and HATUN decisions requires exact-source and freshness evidence; merely adding a field or showing a node in WebGL is not an admission event. Distinguish model metadata, workflow evidence, and executed or cryptographically verified effects.

## Relevant prior art and adaptation

- Palantir's Ontology combines data, logic, actions and security instead of treating a diagram as the operational backend: https://www.palantir.com/docs/foundry/architecture-center/ontology-system
- LangGraph treats durable state, interrupts and human approval as runtime contracts: https://github.com/langchain-ai/langgraph
- NVIDIA's NeMo Agent Toolkit was deprecated in October 2026 in favor of NeMo Relay, Helix and Fabric; do not build a new pinned dependency on the deprecated toolkit: https://docs.nvidia.com/nemo/agent-toolkit/latest/index.html
- ML.ENERGY publishes reproducible inference-energy benchmark methodology: https://github.com/ml-energy/benchmark

The SZL-specific addition is an explicit, revision-bound and evidence-typed projection to the existing 3D interface. No performance comparison or novel-theorem claim is made. Λ uniqueness remains Conjecture 1 (open). The existing eight locked-proven formula IDs and all governance decisions are unchanged.

## Acceptance and limitations

`tests/test_telemetry_summary_contract.py` verifies route precedence over SPA fallback, exact JSON schema, headers, source revision, no-write authority fields, positive collector witness, negative collector witness and frontend binding. The existing holographic and runtime-contract tests must also remain green. Source review and native CI precede merge. After deployment, verify the live same-origin GET is JSON with the exact merged build SHA and correctly reports `DEGRADED` or `UNAVAILABLE` until collector delivery is independently evidenced.

This change does **not** enable an OTel collector, replace an observability platform, attest traces, activate GPU metering, configure external credentials, authorize action, or make the whole estate `READY`.
