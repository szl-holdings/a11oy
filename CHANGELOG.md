# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Release record of the capabilities shipped by the post-1.0.0 "waves" of work.
Every item carries an HONEST capability label per Doctrine v11 (MEASURED /
MODELED / SIMULATION / ROADMAP / SAMPLE). Λ remains **Conjecture 1** (never a
theorem); the locked-8 set stays at 8. No label is upgraded here.

### Added — governed-AI capabilities
- **Governed behavior-transfer harness** — model behavior-transfer harness wired
  into the `/code` run-loop and `/llm/route` (PRs #759, #763).
- **Governed eval / red-team arena** — `szl_eval_arena` + `evalarena` surface, a
  scored eval/red-team arena with a negative-control gate (PR #766).
- **Governed RAG (retrieval-with-receipts)** — retrieval whose answers carry
  provenance receipts (PR #776).
- **Governed agent loop** — composes `/code` + harness + eval into ONE signed
  run (PR #773); kernel-gated agentic loop / loop-forge surface (PR #757).
- **Governed VQC / QML frontier tab** — parameter-shift hybrid VQC, labeled
  **SIMULATION-ONLY** (PRs #764, #782). Not a physical quantum device.
- **Attested inference** — TEE attestation bound to a Λ-gated inference receipt;
  `tee_attestation` field auto-populates **MEASURED** only on a live TDX/Nitro
  node, otherwise honest **UNAVAILABLE** on CPU Spaces (PR #767).
- **Durable bounded receipt/energy ledger** — durable, size-bounded store with an
  honest **storage-pressure** signal (OK / PRESSURE / UNAVAILABLE), surfaced on
  `/healthz` (PR #774).
- **Measured energy channel** — real MEASURED joules via a live NVML
  counter-delta on the sovereign GLM node; **UNAVAILABLE** (never fabricated)
  when no meter is reachable; fleet-wide measured summary across both nodes
  (PRs #785, #789, #790). EU AI Act Art. 53 signed energy disclosure hook wired
  (honest UNAVAILABLE until a live meter + GPU node).
- **Frontier surfaces** — additive governed-provenance frontier tiles:
  zkinfer (zkML proof-of-inference), fmverif (proof-carrying inference),
  supplychain (model-artifact provenance), aigov (AI-governance conformance),
  hybridssm, edgefusion, agentmem — each labeled MODELED/ROADMAP, none
  overclaimed (PRs #734, #748, #754, #777, #778, #779, #780).
- **Substrate consolidation ("substrate finish")** — serve.py import sites
  repointed to the shared `szl_substrate` package via the guarded-fallback
  pattern (prefer shared package, fall back to the vendored root copy); the
  shared package now holds 68/68 movable modules with the drift allow-list
  reconciled (PR #792, tracking szl-substrate PR #8).
- **79 frontier board surfaces wired + verified** with a WIRED/LIVE matrix
  (PR #788); governed flywheel panels wired into the console UI (PR #793).

### Added — release engineering / observability
- **TRANSITIVE COPY-completeness guard** — the CI COPY guard now follows the
  transitive local-import closure from `serve.py`, so a module imported by a
  *registered submodule* (e.g. `szl_energy_measured` via
  `a11oy_harvest_endpoints`) is ALSO required in the Dockerfile per-file COPY
  set. Closes the recurring "forgot to COPY module X" class (bit a11oy 3x) that
  the old direct-only guard let through. The HF deploy DERIVES its pushed file
  set from the Dockerfile COPY sources, so this guard is the load-bearing gate
  for what actually ships.
- **Health rollup on `/api/a11oy/healthz`** — an honest observability roll-up:
  durable-ledger **storage pressure**, DSSE **signer availability** (live vs
  `UNSIGNED-LOCAL`), and a **frontier-endpoint liveness count** (live vs
  degraded tiles). No fabrication: a down sub-source reports UNAVAILABLE.
- **Release-record `[Unreleased]` section** (this section) + the
  `GET /api/a11oy/v1/version` inspection endpoint.

### Security / honesty
- Λ = **Conjecture 1** (never "green"); locked-8 stays at 8; no gate weakened.
- VQC is **SIMULATION-ONLY**; TEE attestation is **UNAVAILABLE** on CPU Spaces;
  energy joules are **MEASURED only** behind a live meter, else UNAVAILABLE.

---

## [1.0.0] — 2026-06-09

### Added
- Doctrine v11 compliance — kernel commit `c7c0ba17` (749 declarations / 14 axioms / 163 sorries)
- SLSA Build Level 1 provenance — honest declaration, not overclaimed
- Section 889 attestation — exactly 5 vendors assessed (Huawei, ZTE, Hytera, Hikvision, Dahua)
- DCO `Signed-off-by:` trailers on all commits per Linux Foundation DCO policy
- OpenTelemetry `traceparent` W3C header propagated end-to-end
- `/api/health` endpoint returning structured JSON with `sovereign: true`
- SBOM (CycloneDX) generated and attached to release
- Cosign keyless OIDC signing for container images
- OpenSSF Scorecard GHA workflow
- SECURITY.md with 90-day responsible disclosure policy
- SUPPORT.md with issue triage SLAs
- CODEOWNERS covering all critical paths
- Dependabot weekly dependency updates
- Trivy/Grype container vulnerability scanning gate
- SLO documentation (p50/p95/p99 targets + error budget)
- Threat model (STRIDE format)
- CITATION.cff for academic citeability

### Security
- Section 889 — no covered telecommunications equipment from Huawei, ZTE, Hytera, Hikvision, or Dahua
- No Iron Bank, FedRAMP, CMMC, or SWFT claims (capability honesty per Anthropic RSP)
- Λ = Conjecture 1 (never a theorem) — mathematical honesty enforced

### Notes
- Warhacker June 9, 2026 release

[Unreleased]: https://github.com/szl-holdings/a11oy/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0
