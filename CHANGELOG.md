# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed - KANCHAY command bar and Lean-8 kernel chip
- Console chrome uses the KANCHAY house palette (void `#080c14`, proof teal
  `#3af4c8`, lattice `#5b8dee`, gold `#d7b96b`, Space Grotesk + JetBrains Mono).
  The last `:root` cascade does not restore gold/tan `#c9b787` / `#5fb3a3` on
  `#0a0a0a`. Honest UNKNOWN / ROADMAP / UNAVAILABLE empty states stay.
- Public header is Command | Proof registry ↗ (`https://a11oy.net`). Sidebar IA
  is Home / Operate / Build / Observe / Govern / Research / More. Investor View
  is an in-console `?view=investor` surface; `/investor` 307-aliases onto that
  same chrome (no stub page, no second IA).
- `go()` writes `?view=` (hash still resolves so legacy `/console#ask` links
  keep working). First fold is receipt stream + gate + Verify on a11oy.net;
  kernel pull and 13-axis radar sit below the fold. Λ stays Conjecture 1, gray.
- Kernel / locked-8 chips read `/api/a11oy/v1/honest` `locked_formula_count`
  (exactly 8). Genome LOCKED-PROVEN is labelled catalog, never the kernel.
  Public `/` and `/landing` no longer inject the operator widget.

### Added - investor smoke gate
- Added a fail-closed S1–S12 / L1–L6 / D1–D10 investor smoke gate
  (`.github/workflows/investor-smoke-gate.yml`, `scripts/investor_smoke_gate.py`).
  S7 is a kernel-chip bind: landing `#pt-locked` via `loadLockedKernel` or
  1394 `loadKernelLocked`, plus trust/console `#cnt-locked`, must read
  `/api/a11oy/v1/honest` `locked_formula_count` (8 or N/A). Genome
  `LOCKED-PROVEN=25` is a catalog tier. Bind job stays RED until PR 1396
  console `#cnt-locked`. S1 HEAD and S2 signer product landed in 1394 on
  main; this PR only probes. Live origin is measured, never invented.
  L1–L6 are SNAPSHOT 2026-08-28. S4/S6/S9 are UNAVAILABLE (no POST). See
  `docs/INVESTOR_SMOKE_GATE.md`.


### Changed - public ecosystem map
- `/ecosystem` is now an in-app map of command-center surfaces on a-11-oy.com.
  Hub atlas inventory, ROADMAP cuts, and the canonical stored receipt RECORD
  are linked to https://a11oy.net rather than duplicated here. Interactive
  `/verify` stays on this origin. Product | Proof origin header is on that
  page only. Console tiles use `?view=` keys (Home/Operate/Build/Observe/
  Govern/Research/More); hash fragments are not emitted here. ROADMAP
  chips parse `a11oy.net` as a hostname, not a URL prefix.

### Fixed - public identity lock

### Fixed - public identity lock
- Trust Center canonical (and og:url / twitter:url) is the product origin
  `https://a-11-oy.com/trust`. The unhyphenated third-party host is never
  emitted as canonical, og:url, twitter:url, or sameAs.
- HEAD on `/console`, `/trust`, and `/assurance` now matches GET (HTTP 200,
  same content-type, empty body) so crawlers and monitors that probe with
  HEAD no longer see JSON 405.
- This app no longer treats `a11oy.net` as sunset and no longer 301s that
  host onto `a-11-oy.com`. Two origins, two jobs: product command center vs
  public proof/registry. No `.com` → `.net` redirect was added.
- Hugging Face Space `runtime.domains` reports `a-11-oy.com` PENDING while
  Cloudflare still serves the apex (MEASURED 2026-08-28). That is an open
  DNS/provider defect (KALLPA / Stephen). This change does not claim the
  custom domain is verified and does not move HTML canonicals off
  `https://a-11-oy.com` to paper it over.
- HEAD on `/robots.txt` now matches GET (HTTP 200, empty body). FastAPI
  GET-only FileResponse / SPA catch-all had been returning JSON 405.
- HEAD on health JSON (`/healthz`, `/readyz`, `/api/health`,
  `/api/a11oy/healthz`, `/api/a11oy/v1/health`) now matches GET. QHAPAQ
  MEASURED GET 200 / HEAD 405 or 404 (the `/api/a11oy/{path}` proxy already
  accepted HEAD, so GET-only probes 404'd). Starlette `methods=["GET"]` was
  the cause.
- Lean health JSON (`/healthz`, `/api/health`, `/api/a11oy/v1/health`) now
  carries an honest signer enum (`ABSENT` / `UNAVAILABLE`). `DSSE-LIVE` stays
  only on `/api/a11oy/healthz` rollup.signer when `szl_dsse.signing_available()`
  is true. Never copy that stamp onto a probe that does not share the signer.
- ISS live feed labels units (degrees, km, km/h) or returns UNAVAILABLE.
  `GET /v1/live-fetch/status` stays an honest 404 (undeclared path); no fake
  status payload.
- killinchu inference runtime is labelled UNAVAILABLE on the landing (Hub
  page HTTP 200; `szlholdings-killinchu.hf.space` timed out). Do not treat
  a11oy's defense Λ as killinchu-live.
- Empty observability DAG (depth 0 / IDLE) and an empty compute-fabric
  probe are labelled UNAVAILABLE. Process-local zero is not a live number.
- `/api/a11oy/v1/observability/summary` does not feed SAMPLE chain depth 24
  as live `dag_depth`, and does not invent `organs_reachable` while
  `observation_state` is inventory / unobserved. `/landing` paints
  UNAVAILABLE in that case and no longer links killinchu at `*.hf.space`.
- `/killinchu` 307s to the Hub inventory page, not the timed-out inference
  Space. Runtime stays UNAVAILABLE. `hf-sync.yml`: staging Space ≠ prod DNS;
  GitHub SHA and Space runtime SHA can drift.
- Trust Center and `/verify` now say in plain language: the lasting public
  RECORD belongs on `a11oy.net`; `/verify` is the interactive tool on
  `a-11-oy.com`. The two hosts stay separate.
- Kernel locked-proven chip is bound from `GET /api/a11oy/v1/honest`
  (`locked_formula_count=8`, ids F1,F4,F7,F11,F12,F18,F19,F22). Genome
  `tier_counts.LOCKED-PROVEN=25` of 144 stays a catalog tag, labelled
  genome, never the kernel chip, never green. Lean-8 ≠ genome-144. The
  8 and the 25 are unchanged.
- Trust `#cnt-locked` and home `#pt-locked` bind
  `GET /api/a11oy/v1/honest` `locked_formula_count` only. Genome
  `tier_counts.LOCKED-PROVEN` stays a gray catalog tag (`#cnt-genome-locked` /
  `#pt-genome-locked`), never the kernel chip, never green. Λ stays
  Conjecture 1. No `/investor` stub.
- HEAD 405 is the app (`Server: szl`), including on
  `szlholdings-a11oy.hf.space`. `/sitemap.xml` now accepts HEAD.
  OPTIONS `/` and `/console` send `Allow` and `Access-Control-Allow-Methods`.
  HTTP `Link` rel=canonical is Host-aware in this app (not a Cloudflare
  transform): on Host `a-11-oy.com` / `www`, `https://a-11-oy.com{path}`;
  on `*.hf.space` the Space Hub canonical is omitted. Never
  `huggingface.co/spaces`, never the furniture host. HF custom domain stays PENDING/UNAVAILABLE.
  Keep orange-cloud (proxied apex). Do not grey-cloud. This PR does not
  change DNS; Stephen may add `_huggingface.a-11-oy.com` TXT later without
  dropping the Cloudflare proxy. www GET / is Cloudflare HTTP 404
  (UNAVAILABLE until Cloudflare 301 www → apex); this PR does not mint DNS
  and does not add a second HF custom domain.
  `x-szl-wire-d: LIVE` is DSSE Wire D provenance, not domain LIVE; that
  distinction lives in a11oy-only DX comments (`a11oy_canonical_domain.py`),
  not in shared `szl_provenance.py` (killinchu byte identity).

### Added - investor-hittable Khipu CPU lab
- Sovereign ensemble voter is now `khipu-gguf` against the pinned SZL-Khipu
  GGUF CPU lab (`/v1/chat/completions`, max_tokens<=32, temperature=0, no
  stream). Llama / Mistral / Qwen Hugging Face voters stay optional cloud
  voters, not the sovereign path.
- Same-origin `GET /api/a11oy/v1/khipu/status` and `POST /api/a11oy/v1/khipu/chat`
  so `/console` Try Khipu can reach the lab without CORS. Dummy Bearer
  `not-a-secret`; GET does not sign; POST passes through UNSIGNED
  `record_sha256`. GPU Inference Endpoint remains ROADMAP; Forge lab is
  SNAPSHOT; killinchu detector stays SIMULATED; Λ = Conjecture 1.

### Added - runtime evidence hardening
- Added the responsive `/frontier-now` and `/now` read-only estate cockpit with
  no-store summary/inventory projections, explicit unavailable capability and
  source/runtime binding states, and held public claims while equivalence proof
  is absent.
- Added separate process liveness, fail-closed dependency readiness, build
  identity, and OpenTelemetry posture endpoints. Unknown file-like and
  discovery paths now return a real 404 instead of the SPA shell.
- Replaced the Quant claim panel's placeholder rows with a validated,
  content-addressed local execution receipt covering real Ollama runs and CPU
  numerical references. Vendor-scale GPU comparisons remain explicitly
  unavailable unless a distinct execution receipt exists.
- Added a bounded, no-effector EvidenceOS involution probe derived clean-room
  from cited primary research, with deterministic digests and explicit
  PROVEN/MODELED/REPORTED boundaries.

### Changed - operational honesty
- Frontier now reports source reachability separately from operational
  readiness; a stopped operator, empty chain, modeled hardware, or unminted
  artifact can no longer produce a green compatibility rollup.
- Downgraded the operator action contract from `verified-runtime` to `roadmap`.
  Manifest and receipt-envelope validation no longer imply an authenticated,
  idempotent, durable action lifecycle.
- Removed author-supplied JUnit as action-contract promotion evidence.
  `verified-runtime` now requires execution of a digest-pinned qualification
  program already present byte-for-byte on protected `main`; the current
  program fails closed while the runtime remains `roadmap`.
- Hatun and Immune surfaces now start at unknown/probing and expose only signer,
  chain, verdict, and invocation evidence actually observed by the backend.
- Added mobile overflow, touch-target, and narrow-viewport handling to Hatun and
  Immune.

### Changed - HF Dockerfile COPY pin
- Stacked successor for PR 1396: this PR lands first on protected `main` with
  the shared COPY line tokens `static/shared/szl_command_bar.js` and
  `static/shared/szl_command_bar.css` (byte-identical to 1396 head `41443b93`)
  plus the protected-base admission pin for that insertion. ÑAWI keeps chrome
  (`pages/console.html`, serve allowlist, lockstep extra_mirror). After merge,
  1396 rebases with no Dockerfile delta. Ordinary candidates still fail closed
  on any other Dockerfile SHA change. The pin applies only while protected
  base still lacks those two tokens; once they are on `main` it does not
  intercept later Dockerfile edits. This PR's own Immutable HF repository byte
  parity is named-RED (baseline controller is unchanged; candidate changes
  that controller and Dockerfile). That RED is the gate, not a skip. PR 1363
  remains HOLD.

## [1.1.0] — 2026-07-13

Release record of the capabilities shipped by the post-1.0.0 "waves" of work.
Every item carries an HONEST capability label per Doctrine v11 (MEASURED /
MODELED / SIMULATION / ROADMAP / SAMPLE). Λ remains **Conjecture 1** (never a
theorem); the locked-8 set stays at 8. No label is upgraded here.

### Added — operational evidence
- **Brain evidence reranker** — three content-addressed canonical source
  families (SZL-Lake, Lean/Mathlib, formulas) produce eight deterministic,
  licensed rows across train/eval/test. Those rows are derived from the three
  canonical manifests, not admitted from the raw graph. All 9,464 raw graph
  nodes remain quarantined where license, revision, or freshness evidence is
  absent. Proof credit remains zero; the model and evaluation remain
  **BLOCKED** pending real receipts.
- **Preregistered numerical-computing dataset** — 1,328 deterministic cases
  spanning declared matrix families, dimensions, condition strata, seeds, and
  tolerances. Dataset readiness is distinct from external MATLAB/Octave engine
  availability and benchmark claims.
- **M1 model gate** — corpus, tokenizer, training receipt, offline reload,
  evaluation, provider identity, and GPU admission are evaluated independently.
  A valid adapter package does not become promoted or operational without a
  loadable local PEFT runtime and passing inference receipt.
- **Formal conjecture lab** — machine-readable proof obligations preserve
  theorem/conjecture boundaries and fail closed when formal evidence is absent.
- **Release identity surface** — canonical and legacy domains, associated
  research DOIs, GitHub release state, and the software-version DOI are exposed
  as separate fields. The v1.1.0 DOI remains `PENDING_ZENODO_READBACK` until a
  GitHub release is archived and a resolvable Zenodo version record is returned.

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
  `tee_attestation` is **SAMPLE** when evidence is merely observed on a live
  TDX/Nitro node and becomes **MEASURED** only after the configured verifier
  authenticates a fresh, request-bound, non-debug, allowlisted measurement;
  otherwise it is honest **UNAVAILABLE** on CPU Spaces (PR #767).
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
- **Versioned v1.1.0 release record** (this section) + the
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

[Unreleased]: https://github.com/szl-holdings/a11oy/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/szl-holdings/a11oy/releases/tag/v1.1.0
[1.0.0]: https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0
