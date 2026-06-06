# vsp-otel

**Layer 4 (Λ-gate exporter) of the SZL 7-layer architecture.**
Λ-signed OpenTelemetry exporter for SZL audit fibers.

[![tests](https://github.com/szl-holdings/vsp-otel/actions/workflows/tests.yml/badge.svg)](https://github.com/szl-holdings/vsp-otel/actions/workflows/tests.yml)
&nbsp;Doctrine **v11 LOCKED** · 749 / 14 / 163 · SLSA L1 honest · DOI [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995)

---

`vsp-otel` is an **OTLP/HTTP collector exporter shim**: any OpenTelemetry-instrumented
service can point its exporter at vsp-otel with **no code change**. For every span it
computes a governance Λ, rejects spans below the floor, DSSE-signs the survivors, and
forwards them to your existing backend (Tempo / Jaeger / any OTLP collector).

```
 your app  ──OTLP──▶  vsp-otel  ──(Λ ≥ 0.90, DSSE-signed)──▶  Tempo / Jaeger
 (any lang, OTel SDK)   :4318
```

## Make it real — what landed

- **`collector/`** — a deployable OTLP/HTTP collector exporter shim (FastAPI, with a
  zero-dependency stdlib fallback):
  - **`lambda_gate.py`** — Λ over span A1–A5 axes; **`LAMBDA_FLOOR = 0.90`** (the
    a11oy doctrine constant); fail-closed rejection.
  - **`dsse.py`** — DSSE in-toto attestation per accepted span (ECDSA P-256 /
    HMAC dev; cosign keyless OIDC in production).
  - **`stats.py`** — **Welford** online mean/variance for span latency +
    **HyperLogLog** for unique-trace cardinality.
  - **`app.py`** — `/v1/traces` (OTLP ingest), `/healthz`, `/metrics` (Prometheus).
- **`Dockerfile`** — per-file `COPY` only (doctrine §build), non-root, SLSA L1 honest (no L2 provenance workflow present).
- **`deploy/helm/vsp-otel/`** — Helm chart (`helm lint` clean); 2 replicas, security
  context, optional ServiceMonitor, configurable floor + forward endpoint.
- **`docs/INTEGRATION.md`** — "your existing OTel SDK already works — just point the
  exporter at vsp-otel."
- **`tests/`** — 9 tests: Λ-gate accept/reject, Welford exactness, HLL cardinality,
  DSSE shape, full OTLP pipeline. All passing.

The pre-existing TypeScript runtime (`runtime/`) — the in-process `signSpan` exporter
and its anchor-formula injection — is unchanged and remains the library form; the new
`collector/` is the standalone deployable form.

```bash
pip install -r collector/requirements.txt
pytest tests/ -v                                  # 9 passed
uvicorn collector.app:app --port 4318             # run the shim
curl localhost:4318/healthz                        # {"status":"ok","lambda_floor":0.9}
```

## Verified live (make-real strike, 2026-06-03)

Posting two spans (one with A1–A5 = 0.97, one with A1 = 0.4) to a running instance:

```json
{"received":2,"accepted":1,"rejected":1,"lambda_floor":0.9,
 "unique_traces_est":2,"latency_ms":{"count":2,"mean":3.5,"variance":4.5,"stddev":2.12}}
```

The high-Λ span passed and was DSSE-signed; the low-A1 span was rejected by the
geometric-mean gate. `/metrics` exposed `vsp_spans_total`, `vsp_lambda_floor`,
`vsp_span_latency_ms_mean`, `vsp_unique_traces_estimate`.

## Formal references (lutar-lean — all in OPEN PRs, cite honestly)

| Used for | Lean reference | Status |
|---|---|---|
| Welford latency mean/variance | [`Lutar.Round11.Welford.welford_mean_exact`, `weightedMean_increment`](https://github.com/szl-holdings/lutar-lean/pull/180) | **theorem** (sorry-free), PR #180 · runtime: `sentra/runtime/welford_gate.py` |
| DSSE in-toto attestations | [`Lutar.Round10.CryptoDSSE.dsse_classical_euf_cma`](https://github.com/szl-holdings/lutar-lean/pull/179) | conditional EUF-CMA **theorem** (0 real sorry), PR #179 |
| Rekor transparency (cosign keyless) | [`Lutar.Round10.CryptoRekor.rekor_inclusion_completeness`](https://github.com/szl-holdings/lutar-lean/pull/179) | completeness **theorem**; soundness is an honest tagged `sorry` (Conjecture 1), PR #179 |
| Bekenstein throughput ceiling (audit-fiber budget) | [`Lutar.Round10...bekensteinCeiling_mono_E`](https://github.com/szl-holdings/lutar-lean/pull/177) | **theorem** (0 real sorry), PR #177 |

> **Λ is Conjecture 1 — never a theorem.** Cited PRs are open on `lutar-lean`. The
> Λ-gate's geometric-mean aggregation mirrors a11oy's graph-Λ construction but Λ
> itself remains conjectural. HONESTY OVER CHECKLIST.

## Honest boundaries (disclosed, not hidden — HR-6)

- **Cosign keyless** (Fulcio OIDC + Rekor inclusion) is **wired but lands with CI**
  (Doctrine v12 §2); dev/CI uses ECDSA P-256 or an HMAC fallback. The DSSE envelope
  shape and PAE v1 encoding are production-final.
- The Λ axis scores are supplied by the instrumented org as span attributes; vsp-otel
  aggregates and gates them — it does not itself infer A1–A5.

## Architecture in context

`vsp-otel` (L4) signs and forwards spans that conform to the `uds-mesh` (L5) schemas;
the receipts it stamps are validated by `hatun-mcp` (L6) `validate-receipt-against-doctrine`.

---

*License: Apache-2.0 · © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173*

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
