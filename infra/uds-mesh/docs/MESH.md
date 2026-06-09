<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# UDS-Mesh — architecture, wires, and honest gaps

**Canonical home:** `szl-holdings/uds-mesh` (ADR-0001, ACCEPTED 2026-06-03).
**Doctrine:** v11 LOCKED — 749/14/163 @ `c7c0ba17` · Λ = **Conjecture 1** (never a theorem) · SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap where `slsa-verifier` confirms · **HONESTY OVER CHECKLIST**.

This document describes what is actually wired in `main` today, the protocol on each
wire, the thesis-v22 formula behind each organ, and the boundaries that are **not** yet
crossed. Where a capability is local-only or unsigned, it is labelled as such — no
capability is asserted that the merged code does not exhibit.

---

## 1. Architecture

Five organs form the mesh. `a11oy` is the policy/receipt substrate the others register
with; `rosie` is the human-facing console; `amaru` (memory), `sentra` (immune), and
`killinchu`/`vessels` (fabric) are the remaining organs. A cross-organ **verdict** is
gated by a Byzantine quorum, co-signed into **one** BLS12-381 aggregate signature, and
observed through **OTLP** spans that carry a single W3C `traceparent`.

```
                            ┌──────────────────────────────────────────────┐
                            │              rosie  (operator console)         │
                            │   issues command  ───────────────┐            │
                            └───────────────────────────────────┼───────────┘
                                                                 │ W3C traceparent
                                                                 ▼  (00-<trace>-<span>-01)
   organ verdicts {action, λ-gate}                ┌────────────────────────────┐
   ┌─────────┐  ┌─────────┐  ┌─────────┐          │  a11oy — policy/receipt      │
   │ a11oy   │  │ sentra  │  │ amaru * │  ……  ──▶ │  substrate (orchestrator)    │
   └────┬────┘  └────┬────┘  └────┬────┘          │                              │
        │            │            │  (* byzantine)│  ┌────────────────────────┐  │
        └────────────┴────────────┘               │  │ F1  Byzantine quorum    │  │
                     │  5 verdicts                 │  │     n ≥ 3f+1, agree≥2f+1 │  │
                     ▼                             │  │  ── names suspected_byz  │  │
            ┌────────────────────┐                │  └───────────┬────────────┘  │
            │  Byzantine QUORUM  │  REFUSE on      │              │ merged verdict │
            │  (F1) + FLP/CAP    │  partition /    │  ┌───────────▼────────────┐  │
            │  partition guard   │  no quorum      │  │ F-PB PAC-Bayes bound    │  │
            └─────────┬──────────┘                 │  │  confidence_lower_bound  │  │
                      │ 4 honest organs agree      │  │  + Welford streaming var │  │
                      ▼                             │  └───────────┬────────────┘  │
            ┌────────────────────┐                 │              │ allow_merge?   │
            │ BLS12-381 AGGREGATE │  one signature  │  ┌───────────▼────────────┐  │
            │ (FastAggregateVerify)│ over Khipu root │  │ DSSE receipt (pinn_dsse)│  │
            └─────────┬──────────┘                 │  │  signed | UNSIGNED mark  │  │
                      │ aggregate_signature (96 B)  │  └───────────┬────────────┘  │
                      ▼                             └──────────────┼───────────────┘
            ┌────────────────────┐                                │ OTLP spans
            │   OTLP BRIDGE       │  in-proc → OTLP/HTTP-JSON ─────┘
            │  (W3C TraceContext) │  ──────────────────────────────────────────┐
            └─────────────────────┘                                             ▼
   Istio STRICT mTLS (PeerAuthentication) + ISTIO_MUTUAL (DestinationRule)  ┌─────────────┐
   ════════════════════════════════════════════════════════════════════════│ OTel        │
   per-organ namespaces: a11oy · sentra · amaru · killinchu · rosie         │ Collector   │
                                                                            │ :4317 gRPC  │
                                                          forwards (cross-repo) :4318 HTTP │
                                                                            └──────┬──────┘
                                                                                   ▼
                                                       vsp-otel Λ-gate verifier (vsp-otel PR #61)
                                                       ── NOT deployed in prod cluster (see §4) ──
```

`*` = the lone **byzantine** sensor in the closeout E2E scenario (`amaru`). The quorum
names it and proceeds on the 4 honest organs.

---

## 2. The wires and their protocols

| Wire | From → To | Protocol / encoding | Implementation | Status |
|------|-----------|---------------------|----------------|--------|
| **Trace propagation** | rosie / organs → quorum → bridge | **W3C TraceContext** `traceparent` (`00-<16B trace_id>-<8B span_id>-<flags>`); parent/child `parentSpanId` linkage | `mesh.otlp_bridge.to_otlp_json` / `parse_otlp_json` | **LIVE (in-proc)** |
| **Telemetry export** | bridge → OTel Collector | **OTLP/HTTP-JSON** `ExportTraceServiceRequest` (`resourceSpans → scopeSpans → spans`); SZL anchor attrs (`szl.anchor_formula.id`, …) preserved | `mesh.otlp_bridge.OtlpBridge.export` (in-proc transport default; HTTP transport via `MESH_OTLP_ENDPOINT`) | **LIVE in-proc; HTTP transport untested over network in CI** |
| **Receipts** | quorum / bridge | **DSSE** envelope (PAE), payload types `application/vnd.szl.mesh-quorum-receipt+json`, `…mesh-otlp-batch-receipt+json`; cosign keyid `szlholdings-cosign` | `pinn_dsse.sign_payload` / `verify_envelope` | **LIVE bytes; SIGNED only when cosign key present, else explicit `UNSIGNED` marker** |
| **Cross-organ co-signature** | 4 honest organs → verifier | **BLS12-381 aggregate** (G2ProofOfPossession ciphersuite, IETF CFRG draft) via `py_ecc.bls`; `Aggregate` + `FastAggregateVerify` — ONE signature replaces N pairings | `mesh.formulas.bls_aggregate.cosign_chain` / `verify_aggregate` | **LIVE (real pairing crypto)** |
| **Pod-to-pod transport** | organ ↔ organ ↔ collector | **Istio STRICT mTLS** (`PeerAuthentication`) + `ISTIO_MUTUAL` (`DestinationRule`); OTLP gRPC :4317 / HTTP :4318 receiver → `memory_limiter`/`batch` → OTLP exporter | `manifests/istio/*.yaml`, `manifests/otel/collector.yaml` | **DECLARED + offline-validated; NOT deployed to a live cluster** |

---

## 3. Formulas — real thesis-v22 citations with Lean permalinks

Each organ-side computation is anchored to a thesis-v22 formula and a Lean theorem in
`szl-holdings/lutar-lean`. Permalinks are pinned to the exact commit the runtime cites
and were verified to resolve at those commits.

| ID | Formula | Code | Thesis | Lean theorem (permalink) |
|----|---------|------|--------|--------------------------|
| **F1** | Byzantine quorum `n ≥ 3f+1`, agreement `≥ 2f+1`; FLP/CAP partition guard (CP choice) | `src/mesh/quorum.py`, `mesh.formulas.pac_bayes_quorum.byzantine_quorum` | thesis_v22.pdf §2 | `KhipuConsensus.lean::faultyCount` — [permalink](https://github.com/szl-holdings/lutar-lean/blob/abd58d159f1bdb79a017d71a6b94ab160ead8d9d/Lutar/KhipuConsensus.lean#L116) |
| **F-PB** | PAC-Bayes (McAllester/Bégin) additive bound: `risk ≤ emp_risk + √((KL+ln(2√n/δ))/2n)`; `confidence = 1 − risk` | `mesh.formulas.pac_bayes_quorum.pac_bayes_bound` / `gate_merge` | thesis_v22.pdf §2 | `PACBayes.lean::pacBayesBound_eq_add_slack` — [permalink](https://github.com/szl-holdings/lutar-lean/blob/abd58d159f1bdb79a017d71a6b94ab160ead8d9d/Lutar/PACBayes.lean#L165) |
| **F-BLS** | BLS12-381 aggregate: aggregate of per-signer signatures equals signature under aggregate key (`FastAggregateVerify`) | `mesh.formulas.bls_aggregate.cosign_chain` | thesis_v22.pdf §2 | `FrontierBLSAggregation.lean::aggregate_verify` (L95); `agg_sig_eq_agg_key_sig` (L82, sorry-free) — [permalink](https://github.com/szl-holdings/lutar-lean/blob/f3153a684e7d9b77462d58185bd1eae0aeacd1bc/Lutar/Innovations/round11/FrontierBLSAggregation.lean#L95) |
| **F-W** | Welford online mean/variance (numerically exact streaming) + z-score anomaly gate | `mesh.formulas.welford_streaming.StreamingStats` | thesis_v22.pdf §2 | `FrontierWelfordVariance.lean::welford_mean_exact` — [permalink](https://github.com/szl-holdings/lutar-lean/blob/f3153a684e7d9b77462d58185bd1eae0aeacd1bc/Lutar/Innovations/round11/FrontierWelfordVariance.lean#L89) |

> **Λ discipline.** Λ (the cross-organ gate) is **Conjecture 1 — never a theorem.** The
> Lean artifacts above prove the *component* lemmas (quorum counting, the PAC-Bayes
> algebraic bound, BLS aggregate correctness, Welford exactness); they do **not** prove
> Λ itself. `KhipuConsensus.lean::faultyCount` is cited under **Conjecture 2 (safety)**.

---

## 4. Honest gaps (what is NOT wired)

- **Cross-pod OTLP collector is NOT deployed in any production cluster — local/in-proc
  only.** The default `OtlpBridge` transport re-parses the OTLP request in-process
  (mirroring the collector's ingest count); it touches no network. An HTTP transport
  exists (`MESH_OTLP_ENDPOINT`) but is **not exercised over a real network in CI** and
  is not pointed at a running collector in production. The collector manifest forwards
  to `vsp-otel-collector.szl-mesh.svc…:4318` (the Λ-gate verifier from **vsp-otel
  PR #61**), but **no live cluster runs it.** Cross-pod `traceparent` propagation is
  therefore **demonstrated in-process, not across pods in production.**
- **Istio mTLS is declared, not deployed.** `PeerAuthentication: STRICT` and
  `DestinationRule: ISTIO_MUTUAL` exist for all five organ namespaces and validate
  offline (`kubeconform` / `kubectl --dry-run=client`), but no Istio control plane or
  sidecar injection runs in CI. Per `docs/roadmap/MESH_INTERCONNECT.md`, the real
  interconnect (a11oy orchestrator service, per-module UDS `Package` CRs, sidecar
  injection, AuthorizationPolicies) is a **v0.4.0 roadmap item — not shipped.**
- **DSSE receipts are UNSIGNED in keyless runtimes.** When `SZL_COSIGN_PRIVATE_PEM`
  is absent, `pinn_dsse` returns an explicit `UNSIGNED` marker — receipt bytes and the
  PAE hash are still integrity-bound and verify once the key is provided, but **no
  signature is fabricated.**
- **SLSA scope.** SLSA **L1 (honest) + L2 (attested via public Sigstore + Rekor) only**,
  and only where `slsa-verifier` actually confirms. No Iron Bank / FedRAMP / CMMC L2+ /
  No SWFT / Mission Owner claims (none held, not pursued). Section-889 vendor list unchanged.
- **BLS keys are demo-derived.** Per-organ BLS secret keys are derived deterministically
  from the organ id for reproducibility; in production each organ holds its own
  HSM-backed key. The crypto (pairings, aggregate verification) is real either way.

---

## 5. End-to-end verification (closeout)

The closeout ran a real 5-organ / 1-byzantine scenario against the merged `main`
(`mesh.formulas.*`, `mesh.quorum`, `mesh.otlp_bridge`, `pinn_dsse`) — no mocks. All five
subsystem checks passed: the quorum **named** the byzantine (`amaru`); BLS produced **one**
aggregate signature from the 4 honest organs, independently re-verified, with a tampered-root
negative control failing as required; OTLP spans propagated with a shared W3C `traceparent`
and preserved parent/child + anchor attributes; and the PAC-Bayes confidence lower bound was
computed (`gate_merge` → `allow_merge=true`). Raw transcript:
`team/uds-mesh-closeout/proofs/e2e_byzantine_test.txt`. Repo suite: **209 passed, 1 skipped**;
substrate self-test **275 tests GREEN**.

---

*License: Apache-2.0 · © 2026 Lutar, Stephen P. — SZL Holdings*

Doctrine v11 LOCKED — 749/14/163 @ `c7c0ba17` · Λ = Conjecture 1 (never a theorem) · SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap · HONESTY OVER CHECKLIST

Signed-off-by: stephenlutar2-hash <stephenlutar2-hash@users.noreply.github.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
