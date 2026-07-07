# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# a11oy HF Docker Space — RESET build (Brand Orchestration Layer at /).
#
# RESET 2026-05-31 (Yachay CTO): a11oy is NOT a /console/ admin panel.
# Per Replit .replit-artifact/artifact.toml: BASE_PATH="/", serve="static" from dist/public,
# rewrite /* -> /index.html (SPA history fallback). The React SPA IS the Brand
# Orchestration Layer; its HomePage (Vessels-DNA / investor-facing landing) renders at /.
#
# Serves:
#   /            — SPA front door (Brand Orchestration Layer landing)
#   /assets/*    — SPA JS/CSS chunks (vite base="/")
#   /boardroom, /investor-demo, /sovereign, /fabric, /nexus, /command, ... — SPA routes (history fallback)
#   /api/a11oy/* — a11oy serve endpoints (health, gates, reason, policy/evaluate, proxy)
#
# HF Space requirement: listen on PORT 7860.

# ---------------------------------------------------------------------------
# IMAGE-LEANNESS: multi-stage build. The CPU demo tier needs llama-cpp-python
# compiled FROM SOURCE against glibc (see the long WHY note above the runtime
# install far below). That compile pulls in a heavy build toolchain
# (build-essential/cmake/ninja/git — hundreds of MB of apt .deb churn) plus
# compile intermediates. Doing it in a THROWAWAY builder stage and copying only
# the resulting prebuilt wheel keeps all of that OUT of the published runtime
# image, shrinking the final image + its layer count (faster GHCR pulls) without
# changing what the demo tier serves.
#
# CONDITIONAL COMPILE: a constrained builder (HF Spaces cpu-basic) sets
# A11OY_REQUIRE_LOCAL_LLM=0 and must NOT pay the heavy compile (it OOM/timed-out
# -> BUILD_ERROR). Select the builder by ARG: =1 -> llama-build-1 (real source
# compile), else -> llama-build-0 (empty, no compile). BuildKit only builds the
# stage actually referenced by the `llama-build` alias, so on the constrained
# path the compile is skipped entirely. The strict GHCR build sets =1.
ARG A11OY_REQUIRE_LOCAL_LLM=0

# Real compile path (=1): build the pinned llama-cpp-python from source into a
# prebuilt glibc wheel, then assert the bundled libllama.so links glibc
# (NEEDs libc.so.6), not musl. set -eux => a bad compile fails the build LOUD.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS llama-build-1
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build git; \
    CMAKE_ARGS="-DGGML_NATIVE=OFF" pip wheel --no-cache-dir --no-binary llama-cpp-python \
        --wheel-dir=/wheels "llama-cpp-python==0.3.19"
RUN python3 <<'GLIBCCHK'
import glob, sys, zipfile
whls = glob.glob("/wheels/llama_cpp_python-*.whl")
assert whls, "no llama_cpp_python wheel produced by the source build"
w = whls[0]
z = zipfile.ZipFile(w)
sos = [n for n in z.namelist() if n.endswith("libllama.so")]
assert sos, "libllama.so not present inside the built wheel " + w
data = z.read(sos[0])
assert b"libc.so.6" in data and b"libc.musl-x86_64.so.1" not in data, \
    "built libllama.so is not glibc-linked (would not load on python:3.12-slim): " + sos[0]
print("[a11oy] built glibc wheel OK:", w, "->", sos[0])
GLIBCCHK

# Skip path (!=1): no compile; just an empty wheel dir so the runtime
# COPY --from has a valid (empty) source on the constrained build.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS llama-build-0
RUN mkdir -p /wheels

# Pick the builder the runtime stage actually copies from.
FROM llama-build-${A11OY_REQUIRE_LOCAL_LLM} AS llama-build

# ---------------------------------------------------------------------------
# RUNTIME IMAGE (the published a11oy Space / GHCR image).
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS runtime

WORKDIR /app

# Install Node 22 (for a11oy serve TypeScript runner)
# Install GitHub CLI (gh) -- the a11oy.code github_read_file / github_open_issue /
# github_open_pr tools shell out to `gh` and read GH_TOKEN/GITHUB_TOKEN from the
# Space env. Official apt repo; curl + gnupg installed in the first half of this RUN.
# LAYER-CEILING CONSOLIDATION (build/docker, Opus 4.8): the Node-22 install and the
# gh install were two adjacent fail-loud apt RUNs; merged into ONE RUN to drop one
# image layer (BuildKit max-depth fix). Identical apt sources, identical packages,
# identical order of effect (Node first -> curl/gnupg present -> gh repo + gh), same
# fail-loud semantics (no `|| true`). The gh block re-runs `apt-get update` after the
# lists were cleaned by the Node block, exactly as before. Build-time tooling only.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# ADDITIVE (Yachay): huggingface_hub + openai power the a11oy.code orchestrator's
# unified open-LLM router (HF Router inference). python-multipart is required by
# FastAPI UploadFile for the Whisper /voice/stt endpoint. None of these change the
# existing SPA / gates runtime; the orchestrator import is try/except-guarded in serve.py.
# REPRODUCIBILITY (founder-flag #5, SWEEP-3): EXACT pins replace bounded ranges.
# Each == is the version pip ACTUALLY resolved in the current RUNNING build
# (HF Space commit 9cb85b2, build log 2026-06-18) — a lockfile that preserves
# current behavior, NOT an upgrade. Every pin satisfies the prior range.
# LAYER-CEILING CONSOLIDATION (build/docker, Opus 4.8): the three adjacent
# fail-loud `pip install --no-cache-dir` RUNs (core deps + slowapi + defusedxml)
# are merged into ONE RUN to drop two image layers (BuildKit max-depth fix). Same
# packages, same EXACT pins, same `--no-cache-dir`, same fail-loud semantics
# (none used `|| true`); pip resolves the identical set in one invocation. The
# per-pin rationale comments below are preserved verbatim.
# BE hardening: slowapi rate limiter (60/min/IP). pydantic+fastapi already present.
# Hardens the Odoo ERP connector's XML-RPC parser against XML entity-expansion /
# decompression-bomb attacks (bandit B411). szl_connectors/erp/odoo.py applies
# defusedxml.xmlrpc.monkey_patch() before parsing untrusted server responses;
# this pin makes that path active in the running image (pure-python wheel).
# Mirrors killinchu #150 so the byte-identical szl_connectors/erp/odoo.py is
# hardened in BOTH flagships rather than silently degrading to the stdlib parser.
RUN pip install --no-cache-dir \
    "fastapi==0.137.1" \
    "uvicorn[standard]==0.49.0" \
    "httpx==0.28.1" \
    "starlette==1.3.1" \
    "huggingface_hub==1.19.0" \
    "openai==2.43.0" \
    "python-multipart==0.0.32" \
    "cryptography==49.0.0" \
    "lmdb==2.2.1" \
    "slowapi==0.1.10" \
    "defusedxml==0.7.1" \
    "numpy==2.1.3"

# sqlite-vss removed from build: no pre-built wheel for python:3.12-slim;
# szl_khipu_lmdb.py and szl_unay.py already have honest try/except fallback
# to cosine similarity if the sqlite-vss .so cannot load. (P0 CI fix, Dev1 Rumi)

# a11oy source for the serve runtime (receipt-substrate + policy gates only).
# FIX (2026-06-03, HF Verification Squad): the previous `git clone` of the PRIVATE
# github.com/szl-holdings/a11oy repo failed in the HF build sandbox (no GitHub creds)
# with exit code 128, leaving the Space stuck in BUILD_ERROR. The required source is
# already vendored in THIS Space repo under packages/, so we COPY it locally to the
# exact path serve.py expects (/app/a11oy-src/packages/...). No network, no auth.
# Doctrine v11 LOCKED 749/14/163. ADDITIVE-equivalent: same files, same runtime path.
COPY packages/receipt-substrate/src /app/a11oy-src/packages/receipt-substrate/src
COPY packages/policy/src/gates /app/a11oy-src/packages/policy/src/gates

# Copy the pre-built SPA (Brand Orchestration Layer) to the static root.
# index.html + assets/* are served directly at / and /assets/*; unknown GET -> index.html.
COPY console/ ./static/

# Build cache-bust 2026-06-08T23:30Z (Wave23 instillation): knowledge.json was
# NEVER explicitly COPYed into the image, so /knowledge.json (SPA Formulas tab +
# /api/a11oy/v1/research/corpus) served a STALE in-layer copy. Pin it freshly into
# BOTH the static root (catch-all serves /app/static/knowledge.json) and /app root
# (research-corpus endpoint reads /app/knowledge.json). Wave23 = conditional Khipu
# BFT safety (Conjecture 2 conditional); locked-8 + Lambda Conjecture 1 UNCHANGED.
COPY knowledge.json ./static/knowledge.json

# Ayllu — a11oy-native agent community. a11oy_ayllu.py is imported (guarded) by
# serve.py; the ayllu/ package (loop, backend, personas + souls/*.md) is loaded at
# runtime, so the WHOLE dir must be COPY'd or the import falls back and Ayllu never
# registers live. (dockerfile-copy-guard verifies these sources exist on main.)
COPY a11oy_ayllu.py ./
COPY ayllu/ ./ayllu/
# Genome registry served to the console Genome panel + /api/a11oy/v1/genome.
# Per-file COPY (this Dockerfile uses no `COPY . .`); a missing line -> the endpoint
# degrades to an honest labeled 503 (never a faked payload), the panel shows it.
COPY data/genome.json ./data/genome.json
# ---------------------------------------------------------------------------
# CONSOLIDATED ROOT-FILE COPY LAYERS (segment A: pre-LLM-gate) — Docker max-depth fix, Opus 4.8.
# One image layer per COPY; collapsed root-file->same-name COPYs into grouped
# multi-source COPYs landing at the /app WORKDIR root. IDENTICAL file set ships
# to IDENTICAL paths (set-equality proven). Never `COPY . .`; subpath/dir COPYs
# untouched; A11OY_REQUIRE_LOCAL_LLM gate + demo-tier RUN logic untouched.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# ---------------------------------------------------------------------------
# Spaces-on-a-11-oy.com shared modules (Dev2+3) — reverse-proxy + console surface.
# Per-file COPY (this Dockerfile uses no `COPY . .`) or serve.py's guarded import
# falls back and /spaces + /api/<ns>/v1/spaces/health 404. Byte-identical a11oy+killinchu.
# LAYER-CEILING CONSOLIDATION (build/docker, Opus 4.8): three adjacent per-file
# root COPYs (all landing at the /app WORKDIR `./`, no comments between them) are
# merged into ONE single-line multi-source COPY to drop two image layers (BuildKit
# max-depth fix). IDENTICAL file set ships to the IDENTICAL `./` destination in the
# IDENTICAL order (sources concatenated in sequence; every basename is distinct so
# nothing overwrites anything). Same single-line grouped-COPY form already used for
# the segment-A/segment-B root-file COPY groups above, so any line-based COPY-set
# parser (e.g. hf-sync-backend) reads it exactly as it reads those. Never `COPY . .`.
# Energy/heart/engine/revenue/harvest organ modules: present in repo but were absent
# from every COPY line -> guarded imports threw ModuleNotFoundError -> dark 404 surfaces.
# energy operator/ledger/projection modules — imported by serve.py (guarded);
# MUST be per-file COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back to a STUB.
# energy LIVE feed (szl_energy_live) — imported by serve.py (guarded); MUST be per-file
# COPY'd or /api/a11oy/v1/energy/{live,mesh,harvest} fall through to the SPA catch-all.
# Orbital tier (MODELED roadmap) — imported by serve.py (guarded); MUST be per-file
# COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back and
# /api/a11oy/v1/orbital/{topology,projection} 404 live. szl_orbital_projection reuses
# szl_energy_operator (the REAL measured ground J/token coefficient), already COPY'd above.
# Orbital PAGE (frontend demo surface) — serve.py imports a11oy_orbital_page (guarded)
# to mount GET /orbital (the MODELED constellation demo, banner-labeled, 0 CDN via the
# vendor3d three.js COPY'd below). MUST be per-file COPY'd or /orbital falls back to the
# SPA catch-all (white screen / no orbital surface).
# Frontier PAGE (unified ecosystem showcase) — serve.py imports a11oy_frontier_page
# (guarded) to mount GET /frontier (the whole-stack showcase, driven by the live
# /frontier/manifest roll-up; honest per-tile labels + provenance; 0 CDN via the
# vendor3d three.js COPY'd below). MUST be per-file COPY'd or /frontier falls back to
# the SPA catch-all (white screen / no frontier surface).
# Frontier manifest — imported by serve.py (guarded). MUST be per-file COPY'd (this
# Dockerfile uses no `COPY . .`) or the import falls back and /api/a11oy/v1/frontier/
# manifest 404s live. Composes in-process from already-COPY'd surfaces (szl_energy_*,
# szl_uds_fleet, szl_orbital_*, szl_backend_hardening, szl_restraint) — no new deps.
# Governed Code-as-Action Kernel (GCAK) — serve.py imports a11oy_code_as_action
# (guarded) to mount the /api/a11oy/v1/agent/code/* routes; it in turn imports
# a11oy_governed_kernel (the persistent, gated, receipted kernel) and
# szl_lambda_tripwire (the Lambda 'Conjecture 1' restraint check). All three MUST
# be per-file COPY'd (this Dockerfile uses no `COPY . .`) or the guarded import
# falls back to a STUB and the agent code routes 404 live (merged-but-not-live).
# Composite inference-provenance receipt (CAPSTONE) — imported by serve.py (guarded).
# MUST be per-file COPY'd (this Dockerfile uses no `COPY . .`) or the import falls
# back and /api/a11oy/v1/provenance/receipt 404s live. Composes in-process from
# already-COPY'd surfaces (szl_immune, szl_materials, szl_khipu, szl_joules_truth,
# szl_formulas, a11oy_nemo_core) — no new deps.
# UNIVERSAL Khipu verifier (judge-facing audit layer) — imported by serve.py (guarded).
# MUST be per-file COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back
# and /api/a11oy/v1/khipu/{organs,chain,verify} 404s live. Reads the shared szl_khipu
# DAG in-process (already COPY'd above) — no new deps.
# DEMO-ONLY signing (Option B): szl_demo_sign exposes the demo-signing-key path so
# /verify shows a real ECDSA-P256 VERIFIED badge. MUST be per-file COPY'd or the
# guarded imports in serve.py (/demo-cosign.pub) and a11oy_vertical_feeds (infer
# fallback) fall back and the demo signature never appears. Production cosign key
# stays founder-gated; only the demo PUBLIC key ships in this module.
# REGRESSION RESTORE — serve.py imports these (guarded) but their per-file COPY was
# dropped, so in the HF image each guarded import falls back to a STUB (merged-but-not-
# live) and the copy-sync lockstep guard is red on main. szl_sda was added by the most
# recent SWEEP D1 commit without its COPY; szl_fabric_surface + szl_nemo_agents predate
# it. All their transitive local deps are already COPY'd above. Additive — restores the
# missing wiring the same way the sibling szl_* modules are COPY'd.
# K-Verify governed-inference benchmark — imported by serve.py (guarded). MUST be
# per-file COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back and
# /api/a11oy/v1/kverify/* 404s. Reuses szl_energy_operator (inference + NVML joules)
# + szl_khipu (the shared signed-receipt chain), both already COPY'd above.
# Governed Speculative Decoding (GAP 4) — imported by serve.py (guarded). MUST be
# per-file COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back and
# /api/a11oy/v1/specdec/* 404s AND hf-sync-backend.yml (it parses this COPY set) would
# not mirror it to the HF Space. Reimplements the acceptance-rejection math (Leviathan
# 2023 / Chen 2023; SpecExec/Sequoia MIT REFERENCE only) and probes the tower's ollama
# /api/tags at request time for a SAME-FAMILY draft+target pair; emits a MEASURED block
# when reachable, else an HONEST ROADMAP with quality_delta=UNAVAILABLE + on-metal runbook.
# Pure stdlib + httpx (already in the image); optional szl_demo_sign imported under guard.
# Immune (Hukulla) HONEST egress-gate surface — imported by serve.py (guarded).
# MUST be per-file COPY'd (no `COPY . .`) or the import falls back and the honest
# /api/a11oy/v1/immune/* namespace 404s. Reuses szl_khipu (the shared signed-
# receipt chain), already COPY'd above. Auto-mirrored to the HF Space by
# hf-sync-backend.yml (it parses the Dockerfile COPY set). web/immune.html (the
# served page) is per-file COPY'd below and declared image_only in
# .github/copy-sync-lockstep.json (same baked-only pattern as web/energy.html).
# SWEEP D5 — Fabric/Tawantin + Auto-review HONEST /status SUMMARY surfaces.
# szl_fabric_surface.py serves /api/a11oy/v1/{tawantin,fabric}/status (honest
# summary over compute-pool-hardened + energy operator/provenance — nodes
# reachable, sovereign count, MEASURED joules, signed-receipt head) and
# /api/a11oy/v1/autoreview/status (honest summary over the real autoreview
# classifier/calibration/dial; rates ROADMAP until real runs). MUST be per-file
# COPY'd (this Dockerfile uses no `COPY . .`) or serve.py's guarded import falls
# back and those /status routes 404 live AND hf-sync-backend.yml (it parses this
# COPY set) would not mirror it to the HF Space. Reuses the live sibling
# endpoints via loopback; no new dep. Summary-only — no fabricated node/joule data.
# SWEEP DEV 3 status module — imported by serve.py (guarded). MUST be per-file
# COPY'd (this Dockerfile uses no `COPY . .`) or the import falls back to a STUB
# and /api/a11oy/v1/{quant,qbio,holographic}/status 404 live. Reuses szl_quantum_bio,
# szl_formulas, szl_pnt_mesh, szl_backend_hardening, szl3d_holographic + szl_khipu
# (all already COPY'd above). hf-sync-backend.yml parses this COPY set to mirror it.
# Materials (Q'allariy) HONEST verifiable crystal-discovery surface — imported by
# serve.py (guarded). MUST be per-file COPY'd (no `COPY . .`) or the import falls
# back and /api/a11oy/v1/materials/* 404s AND hf-sync-backend.yml (it parses this
# Dockerfile COPY set) would not mirror it to the HF Space. Reuses szl_khipu (the
# shared signed-receipt chain), already COPY'd above. szl_materials is the SHARED
# Materials module (Crystal Novelty Certificate + appended DEV2/DEV3 groups).
# szl_materials_predict.py is the governed property-PREDICTION vertical (MODELED+SAMPLE
# numpy surrogate + calibrated ensemble UQ); MUST be per-file COPY'd (no `COPY . .`)
# or serve.py's guarded import falls back and /api/a11oy/v1/materials/predict 404s AND
# hf-sync-backend.yml (parses this COPY set) would not mirror it to the HF Space.
# SWEEP D1 (SDA): szl_sda.py serves the honest Space/Domain-Awareness + counter-UAS
# surface (/api/a11oy/v1/sda/* and /v1/sda/*). MUST be per-file COPY'd (no `COPY . .`)
# or serve.py's guarded `import szl_sda` falls back to the stub (merged-but-not-live,
# /api/a11oy/v1/sda/* 404s) AND hf-sync-backend (which parses this COPY set) would not
# mirror it to the HF Space. Reuses szl_khipu (shared signed-receipt chain, COPY'd
# above) and the REAL counter-UAS drone-cyber logic. Tracks are REPLAY/SAMPLE/MODELED.
# ADDITIVE (I3): FABRO-style Governed Factory + Constitutional Engines modules.
# MUST be COPY'd or serve.py's guarded imports fall back (merged-but-not-live).
# HTML/JS is inlined in these .py modules, so NO web/ or static-vendor COPY needed.
# MBSE / FMI GOVERNED DIGITAL-TWIN CO-SIM — two shared modules (byte-identical in
# killinchu). szl_mbse_cosim.py serves /api/a11oy/v1/mbse/* (governed water-tank +
# 6DOF FMU co-sim, Restraint gate, signed DSSE receipts). szl_mbse_nav.py serves
# /mbse /mbse-6dof /mbse-pipeline (0-CDN holo + inline-SVG charts) + the idempotent
# nav injector. MUST be COPY'd or serve.py's guarded imports fall back (merged-but-
# not-live) AND hf-sync-backend would not mirror them. Per-file COPY (no COPY . .).
# SWEEP D2 — MBSE + Factory honest STATUS surfaces. szl_mbse.py serves the
# honest LIVE /api/a11oy/v1/mbse/{status,models} over the real szl_mbse_cosim
# substance (+ wires its /info,/watertank,/sixdof,/pipeline). szl_factory.py
# serves /api/a11oy/v1/factory/status over the real a11oy_factory engine +
# agentic brain. MUST be COPY'd or serve.py's guarded imports fall back
# (merged-but-not-live) AND hf-sync would not mirror them. Per-file COPY.
# WILLAY — governed inverse of Fable 5 / Mythos 5 (safety verdicts signed & shown).
# szl_willay_gateway.py serves /willay + /api/a11oy/v1/willay/*; a11oy_willay_nav.py
# attaches the idempotent /console nav injector. MUST be COPY'd or serve.py's guarded
# imports fall back and /willay 404s. Per-file COPY (this Dockerfile uses no COPY . .).
# WAQAY — governed quantized vector index (TurboQuant-inspired, signed receipts + Restraint).
# szl_waqay.py serves /waqay + /api/a11oy/v1/waqay/*; a11oy_waqay_nav.py attaches the
# idempotent /console nav injector. MUST be COPY'd or serve.py's guarded imports fall back
# and /waqay 404s. szl_dsse.py / szl_provenance.py / a11oy_org_rag.py already COPYed above.
# Per-file COPY (this Dockerfile uses no COPY . .).
# YUPAY — governed multi-model audit harness (Quechua "to count/audit/reckon").
# szl_yupay.py serves /yupay + /api/a11oy/v1/yupay/*; a11oy_yupay_nav.py attaches the
# idempotent /console nav injector. MUST be COPY'd or serve.py's guarded imports fall back
# and /yupay 404s. szl_dsse.py / szl_provenance.py already COPYed above. Audit methodology
# inspired by the Kilo "same-codebase" audit + MiniMax sparse-attention paper (cited as
# published ideas only); SZL-Nemo is governed Qwen3-32B Apache, never an M3 derivative.
# a11oy_uds_portability_nav.py attaches the idempotent /console nav entry (P4).
# Agentic-PINN + physical-bounds mesh (pure-stdlib sibling of szl_energy_budget; serves
# /api/a11oy/v1/pinn/*). MUST be COPY'd or serve.py's guarded import falls back to a stub
# (merged-but-not-live) in the HF image. The optional on-metal artifacts it reads
# (physical_bounds_certificate.json / agentic_decision_trail.json) are NOT baked — the
# module honestly serves a SAMPLE certificate until Forge writes real ones on the box.
# Governed Inverse-PINN engine (governed-inverse-pinn) — adds POST /api/a11oy/v1/pinn/identify
# (+ GET demo, GET /pinn/health). Both modules MUST be COPY'd or serve.py's guarded import
# falls back (merged-but-not-live) in the HF image. NumPy-only (no torch/DeepXDE/scipy added).
# Governed CALPHAD inverse-discovery (materials-by-design vertical) — extends the
# inverse-PINN system registry with Redlich-Kister L_k discovery on the SAME
# /api/a11oy/v1/pinn/identify endpoint ({"demo":"calphad"}). Imported GUARDED by
# szl_governed_ipinn; MUST be COPY'd or the CALPHAD system is absent at runtime.
# PNT / quantum-sensing mesh (pure-stdlib closed-form web path; serves /api/a11oy/v1/pnt/*).
# szl_pnt_mesh.py loads the 4 engine modules dynamically via importlib, so ALL FIVE MUST be
# COPY'd or serve.py's guarded import falls back to a stub (merged-but-not-live) in the HF
# image. Heavy numpy/UKF/PINN solves are the Forge/GPU path; this web path never solves.
# Counter-UAS / killinchu surface backend (serves /api/a11oy/v1/counter-uas/*). Server-side
# proxy to OUR OWN killinchu Space (sense+evidence, signed verdict); browser surface stays
# 0-CDN (three.js-globe escape hatch, no Cesium). MUST be COPY'd or serve.py's guarded import
# falls back to a stub (merged-but-not-live) in the HF image. Per-file COPY (no `COPY . .`).
# ADDITIVE (I4 gpu-quant): Sovereign VRAM-resident GPU-Quant engine (PCA-Risk / TDA-Fracture
# / HJB-Kelly) backing /api/a11oy/v1/quant/* + the /quant tab. PURE-STDLIB (Jacobi eigen,
# Gaussian solve, union-find Betti) so it runs in the numpy-less HF image; cuML/giotto-tda
# are RUNTIME-PROBED — absent → honest CPU-SAMPLE/ROADMAP labels. MUST be COPY'd or serve.py's
# guarded import falls back to a stub (merged-but-not-live). Imports szl_dsse (already COPYed)
# for REAL ECDSA receipts in-Space + szl_energy_sovereign (already COPYed) for the 2-GPU tier
# panel. Per-file COPY (this Dockerfile never uses `COPY . .`). Mirrored byte-identical to HF.
# ADDITIVE (joules-honesty #349): single-source joules_label helper + its consumers.
# szl_joules_truth.py is imported by szl_energy_budget/szl_engine_status/revenue_endpoints/
# a11oy_harvest_endpoints/szl_anatomy_loop/szl_prod_hardening; revenue_model.py backs
# /revenue/estimate. Absent from every COPY line -> the guarded import fell back to the
# local 'sample' stub and /revenue/estimate ModuleNotFound'd (#349 merged-but-not-live).
# Per-file COPY (this Dockerfile never uses `COPY . .`); keeps the helper LIVE so 'measured'
# is decided in ONE place. Mirrored byte-identical to the HF Space (hf-sync APP_FILES lockstep).
# ADDITIVE (devM resilience): szl_resilience is imported by serve.py for the Hystrix
# circuit breaker + K8s liveness/readiness split. Per-file COPY (this Dockerfile does
# not use `COPY . .`); without this line `import szl_resilience` would ModuleNotFound
# at runtime and /health/live + /health/ready would 404 (the recurring dark-surface bug).
# ADDITIVE (devN observability): szl_observability is imported by serve.py for the
# OpenTelemetry-style distributed tracing + per-surface SLO summary. Per-file COPY
# (this Dockerfile does not use `COPY . .`); without this line `import szl_observability`
# would ModuleNotFound at runtime and /api/a11oy/v1/observability/* would 404 (the
# recurring dark-surface bug). Pure stdlib; no new pip dep.
# ADDITIVE (verifiable-corpus): the publisher module imported lazily (try/except)
# by szl_dsse + szl_wire to publish signed receipts to the public HF dataset
# SZLHOLDINGS/a11oy-verifiable-corpus. Per-file COPY (this Dockerfile never uses
# `COPY . .`); without it the lazy import is a no-op and receipts never publish.
# ADDITIVE (unified-receipt-ledger): vendored szl-lake durable store + ingest
# router mounted onto the live a11oy app under /api/lake/v1 (the one durable sink
# every SZL component POSTs to). Per-file COPY (this Dockerfile never uses
# `COPY . .`); without it the guarded import in serve.py silently falls back and
# the /api/lake/v1 routes never register. Durability mirrors to the HF dataset
# via szl_corpus_publish's HFBucket path (already COPY'd above).
# E8-lattice receipt ENCODING + verification layer over the sha3_256 receipt digests
# (GET/POST /api/a11oy/v1/e8/verify). Conway & Sloane closest-point on E8; error-
# DETECTION geometry only. Cites Viazovska 2016 (Lean-formalized) as prior art; NOT ours,
# NOT adversarial/BFT (Conjecture 2). numpy-guarded, degrades honestly.
# NEMOTRON SIGNED-TRAJECTORY build (2026-06-14): DSSE-signed agent-trajectory
# corpus pipeline (SZL-Nemo). Honest: DATASET property, not a model claim;
# QLoRA-ready, training = ROADMAP (2x80GB GPU). nvidia/Nemotron-Agentic-v1
# mapped under CC BY 4.0 attribution. Served at /signed-corpus.

# Copy serve orchestrator and gates manifest
# ADDITIVE (live-ops): orchestration + AI-observability module — per-file COPY Dockerfile
# omitted it, so import a11oy_warhacker_obs failed and /warhacker + /observability 404'd.
# DEV-WIRE-A (2026-06-09): additive pure-stdlib tab-upgrade metrics module imported
# by serve.py (try/except-guarded). NO numpy/scipy/networkx. Per-file COPY.
# ADDITIVE (cathedral front-door hero): sovereign 3D landing matching the org card.
# Served at / by serve.py (console one click in at /console). Placed AFTER
# `COPY console/ ./static/` (line 65) so vendor3d + hero js are not clobbered.
# ES-module Three.js r160 (MIT) vendored locally — NO CDN. Doctrine v11 LOCKED.
COPY static/a11oy_cathedral.js ./static/a11oy_cathedral.js
# Operator organ (Dev3) — ingested 3D infra-viz, vendored-three (0 CDN)
COPY static/a11oy_operator_organ.js ./static/a11oy_operator_organ.js
# (pages/operator_organ.html is copied below via `COPY pages/ ./pages/`)
COPY static/vendor3d/three.module.min.js static/vendor3d/OrbitControls.js static/vendor3d/THREE_LICENSE.txt ./static/vendor3d/
# ADDITIVE (Dev0, 2026-06-14): SHARED szl3d 3D toolkit + holographic shell. The
# vendored three.js r170 libs (WebGL2 + WebGPU builds + postprocessing addons),
# the szl3d toolkit (boot/live/label), the 9 surface stub modules, the /holographic
# shell page, and the browser self-test harness. Served same-origin under
# /static/3d/* by szl3d_holographic.register() (imported by serve.py) — 0 runtime
# CDN, the estate is sovereign. Whole-tree COPY (nested vendor/ tree). The register
# module + its pytest ship alongside the rest of the root .py modules.
COPY szl3d_holographic.py ./szl3d_holographic.py
# ADDITIVE (cathedral unification, GitHub-aligned): the ONE canonical genius
# cathedral served at /cathedral — IDENTICAL "Constellation · Khipu" scene as the
# SZLHOLDINGS/cathedral HF static space. cathedral_genius.html is that HF
# index.html byte-for-byte except its two asset paths (importmap -> /hero/vendor3d,
# module src -> /cathedral/app.js). app.js is the canonical ES module, served
# sovereign in-image. Reuses the vendor3d Three.js r160 above — 0 CDN.
COPY cathedral_genius.html ./cathedral_genius.html
COPY static/cathedral_app.js ./static/cathedral_app.js
# ADDITIVE (holographic front-door landing, Dev1): the governed-inference-field
# hero served at "/" by serve.py.spa_root (cathedral one click in at /cathedral,
# console at /console). a11oy_landing.html is the page; static/a11oy_landing.js is
# the ES module served at /landing/app.js. Reuses the vendor3d Three.js r160 above
# (MIT) via the page importmap — 0 runtime CDN. MUST be per-file COPY'd or "/"
# falls back to the cathedral/console. Doctrine v11 LOCKED; Λ = Conjecture 1.
COPY a11oy_landing.html ./a11oy_landing.html
COPY static/a11oy_landing.js ./static/a11oy_landing.js
# ADDITIVE: batch-2 sovereign security data module (imported by serve.py; try/except-guarded).
# ADDITIVE: a11oy.code conversational orchestrator module (imported by serve.py).
# ADDITIVE (a11oy Code agentic core, 2026-06-10): the GENUINELY-agentic loop + agentic
# RAG + MCP client that a11oy_code_orchestrator.py imports (try/except-guarded). All three
# are stdlib-only at import time (szl_brain/szl_rag/httpx/faiss are lazy + guarded), so they
# ship BYTE-IDENTICAL into both a11oy & killinchu images. Without these per-file COPYs
# (this Dockerfile never uses `COPY . .`) the agentic=true /chat/stream path, the
# /api/a11oy/code/agent/* and /rag/* endpoints degrade and the imports fail.
# szl_rag.py exists in the repo but was never COPY'd into the a11oy image; it backs the
# BAAI/bge vector recall in a11oy_org_rag (honest FTS5-only degradation without it).
# EGRESS FIX (2026-06-10): the org-RAG full build runs INSIDE this HF Space,
# which can reach huggingface.co but NOT api.github.com (Space egress is
# GitHub-blocked). Bundle the REAL highest-value files of the four GitHub-only
# corpus categories (thesis/formulas/doctrine/lean) in-image so a11oy_org_rag.py
# ingests them when GitHub is unreachable. corpus/INDEX.json records each file's
# real origin repo+path+blob_sha+commit_sha; chunks cite bundled:<repo>@<sha>:<path>
# (real files, honest provenance, NOT fabricated). BYTE-IDENTICAL across a11oy &
# killinchu. Per-file/dir COPY (this Dockerfile does not use COPY . .).
COPY corpus/ ./corpus/
# ADDITIVE: a11oy Code IDE page (served by orchestrator GET /api/a11oy/code/ide as a
# sibling of a11oy_code_orchestrator.py). Self-contained (vendored CodeMirror, 0 runtime
# CDN). Explicit per-file COPY (this Dockerfile does not use `COPY . .`).
# ADDITIVE (WAYRA organ): explicit per-file COPY (this Dockerfile does not use COPY . .).
# serve.py mounts wayra_serve.router -> /wayra, /wayra-digest, /api/a11oy/v1/wayra/*.
# ADDITIVE (KHIPU-OS agentic DAG organ, 2026-06-01, Yachay): explicit per-file COPY
# (this Dockerfile does not use COPY . .). serve.py imports szl_khipu_os_routes and
# mounts GET/POST /api/a11oy/v1/khipu-os/{stats,verify,checkpoint,archive}. Self-driving
# Merkle DAG + Reed-Solomon erasure (reedsolo optional; honest, NOT holographic/quantum).
# ADDITIVE (drift-heal parity, 2026-06-10): shared canonical szl_khipu_consensus.py must be
# byte-identical and present in BOTH a11oy & killinchu images (killinchu COPYs it; a11oy lacked
# the line). Additive per-file COPY only (no content edit; this Dockerfile does not use COPY . .).
# ADDITIVE (PURIQ Agentic Formulas, 2026-06-01, Yachay): explicit per-file COPY
# (this Dockerfile does not use COPY . .). serve.py imports szl_puriq_formulas and
# calls .register(app) -> GET /formulas + /api/a11oy/v1/puriq/formulas*. Doctrine v11 LOCKED.

# ADDITIVE (Yachay / AYNI-OS, 2026-06-01): reciprocity organism + event-sourced replay
# + Tinkuy (Kuramoto) flow. Explicit per-file COPY (this Dockerfile does not use COPY . .).
# serve.py imports ayni_os_serve.router -> /v1/ayni, /v1/replay, /v1/tinkuy and serves the
# /ayni tab from /app/pages/ayni.html. HONEST: replay=event-sourcing (NOT time-travel);
# Ayni=game-theory primitive (Axelrod-Hamilton 1981, NOT mystical); Tinkuy=Kuramoto 1975.
# LOCKED preserved: 749/14/163, 13-axis yuyay_v3, replay bacf5443…631fc5. Pure additive.
COPY ayni_os/ ./ayni_os/
# ayni_os_serve event-sources its ledger from the real signed-receipt corpus; it
# must be in the image or the loader honestly falls back to synthetic. Per-file
# Dockerfile (no `COPY . .`), so copy the corpus explicitly.
COPY infra/receipts-samples/ ./infra/receipts-samples/
COPY pages/ ./pages/

# ADDITIVE (Live 3D Wires / PURIQ Doctrine v12, Yachay): explicit per-file COPY.
# This Dockerfile uses per-file COPY (no `COPY . .`), so the live-wires module +
# its static assets must be copied explicitly or `import szl_live_wires` 404s and
# /live-wires falls through to the SPA shell. serve.py registers these FIRST.

# ADDITIVE (Provenance Hardening / Wire D + DSSE Cosign REAL signing, 2026-06-01, Yachay):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_provenance (which imports szl_dsse) and calls register_provenance(app, "a11oy") ->
# GET /api/a11oy/wires/D, POST /khipu/sign, POST /khipu/verify, GET /khipu/ledger,
# GET /api/a11oy/provenance. Without these COPYs the import fails and the routes fall
# through to the Node :8081 proxy (503). cryptography (added above) backs the real
# ECDSA-P256-SHA256 cosign signatures. Real signatures only when SZL_COSIGN_PRIVATE_PEM
# runtime secret is present (else honestly UNSIGNED). SLSA L1 honest (signing live); L2 roadmap via Wire D; L3 NOT claimed.

ENV PORT=7860
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).

EXPOSE 7860

# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_unay_routes and calls .register(app, ns="a11oy") -> /api/a11oy/v2/unay/* +
# /api/a11oy/v2/khipu/lmdb/*. Real durable lmdb + real sqlite-vss (honest cosine-
# fallback if the .so cannot load in the slim image). a11oy carries Khipu-LMDB PRIMARY.
# ADDITIVE (Warhacker aliases, Yachay 2026-06-01): top-level /healthz + /khipu/* + /wires/D.
# Per-file COPY (no `COPY . .`) — without this `import szl_warhacker_aliases` fails.
# ADDITIVE (Hickok dual-stream ingest, 2026-06-01, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# a11oy_v4_hickok and calls .register(app, ns="a11oy") -> POST /api/a11oy/v4/{dorsal,
# ventral,spt,when,what} + GET /api/a11oy/v4/stream (SSE) + GET /brain, plus the
# dual-stream router middleware on /agent/ask + /predict. Without this COPY the import
# fails and the routes fall through to the Node :8081 proxy (503). Every receipt carries
# neuro_citations[]. Anchors A36/A37/A38 (ts-only, honest `sorry` proofs). The three Lean
# anchor files (DualStreamRouting/InternalFeedback/HierarchicalLinearization.lean) arrive
# via the sparse-checkout of packages/policy/src/gates above (no explicit COPY needed).
# Grounded in Hickok & Poeppel 2007 (DOI 10.1038/nrn2113). Doctrine v11 LOCKED 749/14/163.

# ADDITIVE (Anatomy 3D + live formula wiring, 2026-06-02, Yachay / Perplexity
# Computer Agent): explicit per-file COPY (this Dockerfile does not use `COPY . .`).
# serve.py imports a11oy_v4_formulas (38-formula manifest + 15 live evaluators) and
# szl_anatomy_3d (7 sovereign Three.js r128 anatomy surfaces + 6 live JSON endpoints).
# szl_anatomy_3d self-serves Three.js at /anatomy-three.min.js from static-vendor/.
# Receipts sign via szl_dsse (already COPYed) using szl_khipu + szl_formulas. Without
# these COPYs the imports fail and the pages/endpoints fall through to the SPA shell.
# Doctrine v11 LOCKED 749/14/163. Lambda = Conjecture 1 (NOT a theorem). NO external CDN.
COPY static-vendor/three.min.js static-vendor/chart.umd.min.js static-vendor/3d-force-graph.min.js static-vendor/echarts.min.js static-vendor/echarts-gl.min.js static-vendor/globe.gl.min.js static-vendor/cytoscape.min.js static-vendor/d3.min.js static-vendor/katex.min.js static-vendor/katex.min.css static-vendor/dagre.min.js static-vendor/cytoscape-dagre.js static-vendor/d3-sankey.min.js static-vendor/ngraph.graph.min.js static-vendor/ngraph.path.min.js static-vendor/ngraph.forcelayout.min.js static-vendor/panzoom.min.js static-vendor/vivagraph.min.js static-vendor/ngraph.events.umd.js static-vendor/a11oy-operator-widget.js static-vendor/a11oy-operator-widget.css static-vendor/uPlot.iife.min.js static-vendor/uPlot.min.css ./static-vendor/

# ADDITIVE (Graph/Viz lane + Perplexity Computer Agent, 2026-06-06): AIR-GAP
# VENDORING. The operator console (pages/console.html) loads the 7 viz libs +
# KaTeX from /vendor/* instead of cdn.jsdelivr.net so the Space renders every
# graph with ZERO network egress (Warhacker #2 "Tychee" air-gap deploy stacks).
# Per-file COPY (this Dockerfile does NOT use `COPY . .`). The .js/.css ship as
# text under static-vendor/; the binary globe texture + KaTeX woff2 fonts ship
# as base64 TEXT in _vendor_blobs.py (decoded by the /vendor/* routes in serve.py)
# so NO LFS/Xet blob is committed. Doctrine v11 LOCKED. NO external CDN.
# Batch-1 uniqueness rebuild (2026-06-06): additional vendored graph-viz libs
# (MIT/ISC/BSD; NOTICE updated). Per-file COPY (this Dockerfile uses no COPY . .).
# DEV-WIRE-A (2026-06-09): anvaka graph-stack completion (0-CDN, in-image). BSD-3, anvaka.
# OPERATOR WIDGET (2026-06-10): a11oy floating governed-operator surface ("Chaski"),
# self-hosted in-image (0 CDN), served at /vendor/a11oy-operator-widget.js by serve.py.

# ADDITIVE (V4 Fleet Panel + /api/health fix, 2026-06-02, Dev2 Inti):
# explicit per-file COPY (this Dockerfile does not use COPY . .).
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# szl_v4_fleet.py: /api/health + /api/a11oy/v4/fleet[/doctrine] + /fleet + /thesis
# v4_fleet_panel.html: canonical fleet panel served at /fleet
# operator_shell_v4.py: Unified Operator Shell v4 endpoints (fix import failure)
# web/operator.html: operator shell desktop cockpit HTML

# ADDITIVE (Frontier wave, 2026-06-08): two founder tabs served from /app/web/
# via serve.py _ptg_serve. Sovereign pages, vendored 3D (globe.gl + three from
# static-vendor; earth-night texture from _vendor_blobs.py /vendor route), 0 CDN.
# Per-file COPY (this Dockerfile uses no COPY . .).
# ADDITIVE (Lane I1, 2026-06-14): SZL-Nemo core module + tab. Per-file COPY (this
# Dockerfile uses no COPY . .). a11oy_nemo_core.py is imported by serve.py
# (try/except guarded); web/nemo.html is served at /nemo + /a11oy/nemo via
# _ptg_serve. Without these COPYs the guarded import falls back and /nemo 404s.
# ADDITIVE (a11oy Restraint, 2026-06-14): the GOVERNED + MEASURED frugality gate
# module + tab. Per-file COPY (this Dockerfile uses no COPY . .). szl_restraint.py
# is imported by serve.py (try/except guarded) and serves
# /api/a11oy/v1/restraint/{evaluate,bench,info}; web/restraint.html is served at
# /restraint + /a11oy/restraint via _ptg_serve. Without these COPYs the guarded
# import falls back and /restraint 404s. The .py auto-mirrors to the HF Space via
# hf-sync-backend.yml (parses this COPY line); web/restraint.html is a baked-only
# served page declared in .github/copy-sync-lockstep.json image_only_assets
# (same pattern as web/nemo.html). Ladder + intensity adopted from Ponytail (MIT);
# governance + measurement are ours.
# QHAWAQ (FORMAL/LTL runtime constitutional intercept): the SHARED runtime monitor,
# BYTE-IDENTICAL to killinchu. Imported by serve.py (try/except guarded); serves
# /qhawaq + /api/a11oy/v1/qhawaq/*. Without this COPY the guarded import falls back
# and /qhawaq 404s. The .py auto-mirrors to the HF Space via hf-sync-backend.yml.
COPY szl_qhawaq.py ./szl_qhawaq.py

COPY szl_wallpa.py ./szl_wallpa.py
# ADDITIVE (WALLPA): Voice / expression organ — renders governed actions into audio output.
# Quechua wallpay = to create/express. Doctrine v13 §2.2. Routes: /api/a11oy/wallpa/{voices,
# speak,speak/stream,narrate-doctrine}. OSS-only TTS (Piper→Coqui→OpenVoice→synthetic fallback).
# F8 "Wallpa OSS-Only Safety" locked-proven theorem. Without this COPY the try/except in
# serve.py (edge organs loop, line ~2238) silently swallows the ImportError and all /wallpa
# endpoints return 404. The .py auto-mirrors to the HF Space via hf-sync-backend.yml.
# ADDITIVE (SAPA): Energy per Successful Goal — frontier agentic unit on top of
# the live MEASURED joules/token path. szl_sapa.py is the shared accounting layer
# (byte-identical a11oy<->killinchu); szl_sapa_patch.py front-inserts /sapa +
# /api/<ns>/v1/sapa/* before the SPA catch-all + Node proxy. Per-file COPY (this
# Dockerfile never uses `COPY . .`) or serve.py's guarded import falls back
# (merged-but-not-live) and /sapa 404s to the SPA shell. Mirrored byte-identical
# to the HF Space (hf-sync lockstep).
# ADDITIVE (R4 lane, 2026-06-14): a11oy Restraint -> ENERGY + KPI + MEASURED BENCH.
# szl_restraint_energy.py is imported by serve.py (try/except guarded) and serves
# /api/a11oy/v1/restraint/{energy,bench-measured,kpi}; web/restraint-bench.html is
# served at /restraint-bench (+ /a11oy/restraint-bench) via _ptg_serve. The bench
# harness benchmarks/restraint/run_bench.py is the runnable reproduce tool (writes
# benchmarks/restraint/results.json -> dashboard flips SAMPLE->MEASURED). The .py
# auto-mirrors to the HF Space via hf-sync-backend.yml (parses these COPY lines);
# web/restraint-bench.html is a baked-only image-only asset (copy-sync-lockstep.json).
# CONSUMES szl_restraint (R1) + szl_energy_sovereign (Forge) only; edits neither.
# 0 runtime CDN (fonts only); 0 visible codenames; Ponytail CITED (MIT).
COPY benchmarks/restraint/run_bench.py ./benchmarks/restraint/run_bench.py
# ADDITIVE (nonlinear-PINN frontier, 2026-07-02): szl_pinn_nonlinear.py is imported by
# serve.py (try/except guarded) and serves GET /api/a11oy/v1/pinn/burgers (MODELED
# Newton-linearized spectral collocation for steady nonlinear Burgers) + /pinn/bench
# (serves the committed honest cross-framework benchmark). Per-file COPY (this Dockerfile
# never uses `COPY . .`) or the guarded import falls back (merged-but-not-live) and both
# endpoints 404 to the SPA. The bench artifact benchmarks/pinn/results.json MUST ship too
# or /pinn/bench honestly degrades to NOT-RUN; benchmarks/pinn/run_bench.py is the runnable
# reproduce tool (SZL arm is NumPy-only; the DeepXDE comparison arm is a benchmark-ONLY dev
# dep — LGPL-2.1, lazy-imported in the harness, NEVER imported by serve.py/shipped code).
# Mirrors the restraint bench pattern above.
COPY szl_pinn_nonlinear.py ./szl_pinn_nonlinear.py
COPY benchmarks/pinn/results.json ./benchmarks/pinn/results.json
COPY benchmarks/pinn/run_bench.py ./benchmarks/pinn/run_bench.py
# ADDITIVE (Lane F1, 2026-06-14): the 3D/holographic SUBSTRATE demo page, served at
# /holo + /a11oy/holo via _ptg_serve. Loads the shared kit /static/shared/szl_holo3d.js
# (0 CDN). image-only like the other web/*.html demo pages (declared in
# .github/copy-sync-lockstep.json image_only_assets; baked into the GitHub-built image,
# live after a factory rebuild). Without this COPY /holo would 404 to the SPA shell.
# ADDITIVE (Lane F5, 2026-06-14): the three sovereign 3D surfaces served at
# /constitution, /quant and /estate-hologram (+ /a11oy/* aliases) via _ptg_serve.
# Each loads the shared kit /static/shared/szl_holo3d.js (0 CDN) and reads its live
# /api/a11oy/v1/{constitution,quant,ecosystem,engine}/* feeds. image-only like the
# other web/*.html demo pages (declared in copy-sync-lockstep.json image_only_assets;
# baked into the GitHub-built image, live after a factory rebuild + direct Space push).
# Without these COPYs the routes 404 to the SPA shell.
# WARHACKER SHOWCASE PAGES (demo lane, 2026-06-14): two PUBLIC companion pages served
# at /signature-is-not-proof and /defense-readiness (+ /a11oy/* aliases) via _ptg_serve.
# System fonts, 0 runtime CDN, no external scripts; live claims fetch real a11oy
# endpoints with an honest NO-LIVE-DATA fallback. image-only like the other web/*.html
# demo pages (declared in copy-sync-lockstep.json image_only_assets; baked into the
# GitHub-built image, live after a factory rebuild + direct Space push). Without these
# COPYs the routes 404 to the SPA shell.
# ADDITIVE (2026-06-17): web/determinacy.html is the ILLUSTRATIVE analytic-continuation
# proof-doctrine showcase page, served at /determinacy + /a11oy/determinacy from /app/web/.
# Real in-browser power-series arithmetic (no fabricated values); the math->receipt bridge
# is explicitly labelled illustrative; the live claim re-walks /api/a11oy/v1/khipu/organs
# with an honest NO-LIVE-DATA fallback. image_only (baked via this per-file COPY; NOT
# hf-sync mirrored) — same baked-only pattern as web/signature-is-not-proof.html; declared
# in copy-sync-lockstep.json image_only_assets + hf-module-drift-allow.json.
# ADDITIVE (SWEEP D1, 2026-06-16): web/sda.html is the honest, user-visible SDA —
# Space/Domain Awareness (Counter-UAS) page, served at /sda + /a11oy/sda from
# /app/web/. Binds to the LIVE /api/a11oy/v1/sda/* surface (status/tracks/verdict).
# image_only (baked via this per-file COPY; NOT hf-sync mirrored) — same baked-only
# pattern as web/immune.html + web/materials.html; declared in copy-sync-lockstep.json
# image_only_assets + hf-module-drift-allow.json accepted_divergences.
# ADDITIVE (2026-06-16): web/dns.html is the honest, user-visible DNS & Subdomains
# internal infrastructure roadmap, served at /dns + /a11oy/dns from /app/web/. Static
# page (0 runtime CDN, NO live data). image_only (baked via this per-file COPY; NOT
# hf-sync mirrored) — same baked-only pattern as web/sda.html + web/immune.html;
# declared in copy-sync-lockstep.json image_only_assets + hf-module-drift-allow.json
# accepted_divergences.
COPY web/formulas.html web/v4_fleet_panel.html web/operator.html web/fleet-c2.html web/living-anatomy.html web/nemo.html web/restraint.html web/restraint-bench.html web/holo.html web/constitution.html web/quant.html web/estate-hologram.html web/hologram.html web/signature-is-not-proof.html web/defense-readiness.html web/determinacy.html web/sda.html web/dns.html ./web/
# ADDITIVE (Lane A AGENTIC CORE, Dev A, 2026-06-14; QA9 restore 2026-06): the
# resumable ReAct agent-loop core module. Per-file COPY (this Dockerfile uses no
# COPY . .). a11oy_react_core.py is imported by serve.py (try/except guarded) and
# serves /api/a11oy/v1/agent/react/{run,resume,trace,checkpoints} (+ free
# top-level /api/a11oy/v1/agent/{resume,trace/{id},checkpoints}). Without this COPY
# the guarded import falls back to a stub in the image and the react endpoints
# 404. Restores wiring clobbered by a later integration-wave push built from a
# stale base (the register block in serve.py + this COPY were both lost).
# ADDITIVE (MEASURED physical-bounds cert wire-up): szl_physical_bounds.py is the
# single-source reader for the shipped physical_bounds_certificate.json (already
# COPY'd in this same line). Imported GUARDED by serve.py (GET /api/a11oy/v1/energy/
# physical-bounds) and szl_governed_api.py (govern/infer energy reference). Per-file
# COPY (this Dockerfile uses no `COPY . .`) or the guarded import falls back and the
# endpoint 404s / the govern receipt cannot cite the MEASURED reference.
COPY knowledge.json szl_parity_gaps.py compliance_crosswalk.py szl_compliance_mesh.py a11oy_warhacker_obs.py serve.py szl_governed_api.py szl_demo_tier1.py szl_assurance.py govern_showcase.html a11oy_wireA_metrics.py cathedral.html a11oy_operator_organ.py a11oy_hf_assets.py szl_b2_secdata.py gates_manifest.json a11oy_code_orchestrator.py a11oy_agent_loop.py a11oy_org_rag.py a11oy_mcp_client.py szl_rag.py a11oy_code_ide.html wayra_serve.py wayra_snapshot.json wayra_digests_7d.json szl_khipu_os_routes.py szl_spaces_proxy.py szl_spaces_surface.py szl_khipu_consensus.py szl_puriq_formulas.py ayni_os_serve.py szl_live_wires.py live_wires.html live_wires_3d.js szl_intoto.py szl_intoto_routes.py szl_scitt.py szl_dsse.py szl_provenance.py szl_be_hardening.py szl_unay.py szl_khipu_lmdb.py szl_khipu_replicate.py szl_unay_routes.py szl_warhacker_aliases.py a11oy_v4_hickok.py szl_khipu.py szl_formulas.py a11oy_v4_formulas.py szl_anatomy_3d.py szl_anatomy_routes.py _vendor_blobs.py szl_v4_fleet.py operator_shell_v4.py szl_bridge.py szl_bridge_schemas.py agent.html a11oy_bridge_cli.py szl_ken.py a11oy_formula_endpoints.py a11oy_formula_registry_guard.py a11oy_formulas_page.py a11oy_frontier_patch.py a11oy_v4_agent.py szl_brain.py szl_wire.py szl_hub.py szl_rosie_companion.py szl_receipt_substrate.py szl_alloy_embed_fabric.py szl_ayni_quorum.py szl_agentic_loop.py szl_ltc_dynamics.py szl_sgh_scheduler.py szl_formula_wiring.py szl_formula_surfaces.py a11oy_code_engine.py a11oy_code_runloop.py a11oy_code.py a11oy_seismic.py szl_warhacker_real.py szl_warhacker_demos.py NOTICE_warhacker_demos.txt szl_llm_registry.py szl_elite_console.py szl_alloy_models.py szl_scaling.py szl_allodial.py szl_entanglement.py szl_neuroplasticity.py szl_neuromorphic.py szl_kan.py szl_titans.py szl_mor.py szl_ternary.py szl_agentmem.py szl_edgefusion.py szl_hybridssm.py szl_aigov.py szl_chain_of_title.py szl_sovereign_compute.py szl_a11oy_interpretability.py a11oy_active_flux_router.py szl_energy_budget.py szl_energy_sovereign.py szl_energy_provenance.py szl_heart_blood.py szl_engine_status.py szl_backend_hardening.py revenue_endpoints.py a11oy_harvest_endpoints.py joule_billing.py szl_energy_ledger.py szl_energy_operator.py szl_energy_projection.py szl_cheapest_watt.py szl_energy_live.py szl_orbital_topology.py szl_orbital_projection.py a11oy_orbital_page.py a11oy_frontier_page.py szl_frontier_manifest.py szl_frontier_zkinfer.py szl_frontier_fmverif.py szl_frontier_supplychain.py a11oy_code_as_action.py a11oy_governed_kernel.py szl_lambda_tripwire.py szl_provenance_receipt.py szl_khipu_verify.py szl_attest_stack.py szl_demo_sign.py szl_sda.py szl_fabric_surface.py szl_nemo_agents.py szl_kverify.py szl_specdec.py szl_immune.py szl_quant_qbio_holo.py szl_materials.py szl_materials_predict.py a11oy_factory.py a11oy_constitution.py a11oy_nav_wireup.py szl_mbse_cosim.py szl_mbse_nav.py szl_mbse.py szl_factory.py szl_willay_gateway.py a11oy_willay_nav.py szl_waqay.py a11oy_waqay_nav.py szl_yupay.py a11oy_yupay_nav.py a11oy_uds_portability_nav.py szl_pinn_bounds.py physical_bounds_certificate.json agentic_decision_trail.json physical_bounds_certificate.dsse.json szl_pinn_inverse.py szl_governed_ipinn.py szl_calphad_inverse.py szl_pnt_mesh.py quantum_sensing_limits.py pnt_resilience.py nav_coasting.py fundamental_limits.py szl_counter_uas_proxy.py szl_gpu_quant.py szl_joules_truth.py revenue_model.py szl_prod_hardening.py szl_resilience.py szl_observability.py szl_corpus_publish.py szl_lake_store.py szl_lake_ingest.py szl_e8.py szl_trajectory_sign.py szl_nemotron_ingest.py szl_nemotron_corpus.py szl_nemo_verify.py a11oy_nemo_core.py szl_restraint.py szl_sapa.py szl_sapa_patch.py szl_restraint_energy.py a11oy_react_core.py szl_org_lambda.py a11oy_canonical_domain.py a11oy_formula_tiers.py szl_physical_bounds.py szl_kc_loop_forge.py szl_kc_loop_forge_metrics.py szl_kc_atlas.py szl_eval_arena.py szl_vqc.py szl_kc_jpt.py ./

# DEV2 Build 1: TEE/TDX attestation hook (2026-06-30) — imported by serve.py (guarded);
# MUST be per-file COPY'd or /api/a11oy/v1/tee/status + tee_attestation receipt field
# fall back to honest UNAVAILABLE stubs. Pattern: dstack-capsule Apache-2.0 arXiv 2606.03323.
COPY szl_tee_attest.py ./
# WAVE-H TEAM 3: attested-inference deepening (2026-07-07) — imported by serve.py (guarded);
# MUST be per-file COPY'd (this Dockerfile uses no `COPY . .`) or GET /api/a11oy/v1/attest/infer
# falls through to the SPA (404). Binds a MODELED device-attestation quote to a Λ-gated inference
# RECEIPT + SLSA provenance; DSSE real ECDSA-P256 in-Space / UNSIGNED-LOCAL locally. Reuses the
# already-COPY'd szl_tee_attest + szl_dsse + szl_org_lambda. Leaders (clean-room PATTERN): NVIDIA
# H100/H200 CC+NRAS, AMD SEV-SNP, Intel TDX, in-toto/SLSA, Sigstore/Rekor, Confidential Containers.
# The attestinfer.js surface ships via the existing `COPY static/3d/ ./static/3d/`. Λ = Conjecture 1.
COPY szl_attested_inference.py ./
# DEV2 Build 2: EU AI Act Art.53 signed energy disclosure (2026-06-30) — imported by
# serve.py (guarded); MUST be per-file COPY'd or /api/a11oy/v1/energy/eu-disclosure +
# energy_eu_disclosure receipt field fall back to honest UNAVAILABLE stubs.
# Methodology: HF-Energy-Score + GSF-SCI ISO-21031. DSSE-signed + Merkle-logged.
COPY szl_eu_energy.py ./
# BRAIN GRAPH (2026-07-07) — imported by serve.py (guarded); MUST be per-file COPY'd or
# GET /api/a11oy/v1/brain/graph falls through to the SPA HTML shell (no JSON). Harvests
# the real estate (surfaces+formulas+repos+topics) into a layered node/link brain graph.
COPY a11oy_brain_graph.py ./
# HARVESTED FIELD LEADERS (2026-07-07) — real research graph JSONL (papers/repos/labs/
# people/datasets/benchmarks/standards/axes, each with a verified url). a11oy_brain_graph
# reads these at runtime to merge the outer "field" layer into /brain/graph; MUST be
# COPY'd or the endpoint honestly reports harvest available=False (estate-only).
COPY brain/harvest ./brain/harvest

# DEV2: in-toto offline verifier recipe (Apache-2.0)
RUN mkdir -p /app/szl-cookbook
COPY szl-cookbook/verify-intoto-receipt.py /app/szl-cookbook/


# ADDITIVE (Cross-Harness Receipt Bridge — Hermes + OpenClaw; 2026-06-01, Yachay /
# Perplexity Computer Agent; closeout PR superseding #198 runtime files). serve.py
# already imports szl_bridge + a11oy_v4_agent and calls .register(app) BEFORE the
# /api/a11oy/{path} Node proxy + SPA catch-all, but the bridge runtime modules were
# never COPY'd, so `import szl_bridge` failed at boot and POST /api/a11oy/v4/bridge/
# {hermes,openclaw} + GET /api/a11oy/v4/bridge/receipt/{id} + GET /bridge fell through
# to the SPA (404). Explicit per-file COPY (this Dockerfile never uses `COPY . .`).
# szl_bridge imports szl_bridge_schemas (JSON Schema 2020-12 tool registry) and reuses
# the already-COPY'd szl_dsse + szl_receipt_substrate signing/ledger modules. Doctrine
# v11 LOCKED 749/14/163 UNCHANGED.
# a11oy-bridge CLI (sign --from hermes/openclaw, verify --receipt-id). Standalone
# operator tool; not imported at boot but shipped so it is runnable in-container.


# ADDITIVE (SZL Ken Agent Pattern v1, CTO Yachay Convergence Cycle 1, 2026-06-03):
# Explicit per-file COPY of szl_ken.py (this Dockerfile never uses `COPY . .`).
# serve.py tries `import szl_ken` at startup; without this COPY the import fails
# silently and /v1/agent/loop + /v1/mcp/tools return 404 instead of 200.
# ADDITIVE ONLY — zero existing routes touched. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>


# ADDITIVE (Formulas → Ecosystem instillation, Opus 4.8, 2026-06-03):
# Per-file COPY of the a11oy.formulas package (this Dockerfile never uses `COPY . .`).
# serve.py imports a11oy_formula_endpoints, which imports a11oy.formulas.* — without
# these COPYs the import fails and /api/a11oy/v1/formula/* fall through to the SPA shell.
# Real implementations of PAC-Bayes, BLS12-381 aggregate, Welford, Byzantine quorum,
# Holevo, Bloom, Kalman, HNSW (amaru-delegate), Reidemeister. Each cites thesis_v22.pdf
# + a real Lean theorem/obligation. Λ = Conjecture 1 (NEVER a theorem). SLSA L1 honest.
# L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY src/a11oy/__init__.py ./src/a11oy/__init__.py
COPY src/a11oy/formulas/__init__.py src/a11oy/formulas/pac_bayes.py src/a11oy/formulas/bls_aggregate.py src/a11oy/formulas/welford.py src/a11oy/formulas/byzantine_quorum.py src/a11oy/formulas/holevo_bound.py src/a11oy/formulas/bloom_filter.py src/a11oy/formulas/kalman.py src/a11oy/formulas/hnsw_retrieval.py src/a11oy/formulas/reidemeister.py src/a11oy/formulas/allodial.py src/a11oy/formulas/allodial_gate.py src/a11oy/formulas/entanglement.py ./src/a11oy/formulas/
# FIX (formula/* 404 repair): a11oy_formula_endpoints.py imports a11oy.formulas.{allodial,
# allodial_gate, entanglement} alongside the formulas above, but these three were NEVER
# COPY'd into the image. The package import therefore raised at boot, register() returned
# "formulas-unavailable", and EVERY /api/a11oy/v1/formula/* route (sovereign, quorum, holevo,
# bloom, kalman, formulas/index, …) 404'd through the Node proxy. Per-file COPY (this
# Dockerfile never uses `COPY . .`). Mirrored byte-identical to the HF Space (hf-sync
# APP_FILES lockstep). EXPERIMENTAL frontier gates — Λ = Conjecture 1 (never a theorem).
COPY src/a11oy/harvest/__init__.py src/a11oy/harvest/wasted_energy_harvest.py src/a11oy/harvest/harvest_budget.py ./src/a11oy/harvest/
# ADDITIVE (Formulas SECTION page — closeout): serve.py imports a11oy_formulas_page
# and calls .register(app) BEFORE the SPA catch-all, mounting GET /formulas/wired
# (premium Inca-palette list of every live formula + thesis citation + Lean permalink
# + "Try it") and GET /api/a11oy/v1/formulas/page-manifest. Per-file COPY (never
# `COPY . .`); without it the import fails and the route falls through to the SPA.

# ADDITIVE (Missing modules fix, 2026-06-04, Perplexity Computer Agent):
# The following .py files exist in the repo and are imported via try/except
# in serve.py, but were never COPY'd into the Docker image. Without them the
# imports fail silently and the associated routes/tabs are unavailable.
# Per-file COPY (this Dockerfile never uses `COPY . .`).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# ADDITIVE (Parity Gaps + Receipt Substrate fix, 2026-06-05, Orchestrator Squad):
# szl_parity_gaps.py was MISSING from the Dockerfile despite being imported by
# serve.py at line ~1722 and being the source of the 5 parity endpoints
# (compliance/export, lineage, policy/validate, receipts/replay, lambda/score).
# Without this COPY those endpoints 404'd.
# szl_receipt_substrate.py was likewise missing — the Dockerfile comment at line ~182
# said "already-COPY'd" but no COPY line existed; szl_bridge.py and szl_parity_gaps.py
# both import it via try/except, causing silent degradation.
# szl_alloy_embed_fabric.py + szl_ayni_quorum.py: exist in repo, imported in serve.py,
# but were never COPY'd — adding them makes their endpoints live.
# Per-file COPY (this Dockerfile never uses `COPY . .`).
# NOTE: szl_parity_gaps.py is already COPY'd at line 68 (above serve.py).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

# Governed agent loop module (RAG->tool-call->policy/trust->signed-receipt + canonical /mcp/).

# Formula-wiring module (ADDITIVE 2026-06-06): registers the kernel-verified theorem
# mechanisms as live executable checks + the /api/<ns>/v1/formulas/* endpoints
# (selftest, proof-summary). BYTE-IDENTICAL across a11oy + killinchu (single source of
# truth). Per-file COPY (this Dockerfile never uses `COPY . .`) -- without this
# `import szl_formula_wiring` fails at boot and the formula endpoints 404. Imports
# stdlib only; no weights, no keys.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# a11oy Code engine (governed chat/code/research; C20/W7-5 router; W5-3/W7-4 conformal;
# C10-C12 consensus; REAL restricted-subprocess sandbox). Per-file COPY (this Dockerfile
# never uses `COPY . .`) -- without this `import a11oy_code_engine` fails at boot and the
# /api/a11oy/v1/code/* routes fall through to the SPA. Imports only stdlib + the already-
# present szl_agentic_loop primitives; OPEN-WEIGHT roster only, NO closed weights, NO keys.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# a11oy.code 7-tier organ->model router (TIERS + route() + tiers_payload()).
# Per-file COPY (this Dockerfile never uses `COPY . .`) -- without this
# `import a11oy_code` fails at boot and the /api/a11oy/v1/code/{tiers,health,
# index,roster,route,auto,complete} router surface (registered in serve.py before
# the catch-all) silently no-ops, so the /code UI's GET /tiers + POST /route|/auto
# calls 404 and the chat cannot answer. Imports only stdlib (math/time/hashlib).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# a11oy Seismic forecaster (Doctrine v13): honest Reasenberg-Jones (1994) +
# Modified-Omori (Utsu 1961) aftershock-rate model over the LIVE public USGS
# feeds. Per-file COPY (this Dockerfile never uses `COPY . .`) -- without this,
# `import a11oy_seismic` fails at boot and the /api/a11oy/v1/seismic/{quakes,
# forecast,health} routes (registered in serve.py before the catch-all) silently
# no-op and fall through to the proxy (404). Stdlib only (math/urllib/json);
# clean-room MIT, public-domain science, NO third-party code, 0 runtime CDN.
# Statistical forecast -- NOT certainty, NOT a locked-proven claim.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# Warhacker mission tabs backend (5 investor-facing surfaces; reuses
# szl_agentic_loop primitives + the in-image signer). Per-file COPY
# (this Dockerfile never uses `COPY . .`) — without this
# `import szl_warhacker_real` fails at boot.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# Warhacker EXHAUSTIVE demos backend (5 full step-by-step demos: step timeline,
# catch tree, single-byte tamper test, formula-proof panel). Pure-Python, no
# external deps; reuses the in-image signer + loop verifier. Per-file COPY
# (this Dockerfile never uses `COPY . .`) — without this
# `import szl_warhacker_demos` fails at boot.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

# ---------------------------------------------------------------------------
# OPEN-WEIGHT ALLOY MODEL LAYER (model-integration squad, 2026-06-06, ADDITIVE)
# Forges the strongest OPEN-WEIGHT coding models into a11oy's brains, BOUND by
# proven formulas (C20/W7-5 router, W5-3/W7-4 conformal, C10-C12 consensus),
# UNIFIED into the existing LLM registry (one roster, not two).
#   * szl_alloy_models.py : roster + router + conformal + consensus + governed
#     suggest + local GGUF backend (honest tower-side label when no GGUF mounted).
#   * szl_llm_registry.py : the EXISTING registry module (was imported in serve.py
#     but NEVER COPY'd -> import failed silently / /llm/registry 404). This COPY
#     makes the unified roster genuinely LIVE.
#   * szl_elite_console.py: existing console module imported by serve.py.
# Per-file COPY (this Dockerfile never uses `COPY . .`). OPEN-WEIGHT only, NO
# closed weights, NO keys. Weights NOT redistributed (loaded by hf_repo at
# runtime / tower-side).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

# LIVE CPU demo tier: install llama.cpp + fetch ONE tiny Apache-2.0 GGUF
# (Qwen2.5-Coder-0.5B-Instruct Q4_K_M) so the demo tier serves REAL output on
# cpu-basic. The wheel install stays best-effort (honest tower-side fallback if
# no prebuilt wheel), but the GGUF weight below is now RELIABLY fetched (pinned
# revision + retry + integrity verify) so the published image always carries it.
# We never redistribute the weight in our repo — it is fetched from the HF repo.
# CPU demo-tier llama.cpp — BUILT FROM SOURCE against glibc (NOT a prebuilt wheel).
# WHY: abetlen's CPU wheel index ships the recent, Qwen2.5-capable 0.3.x cp312
# linux_x86_64 wheels built against MUSL libc — their bundled libllama.so NEEDs
# libc.musl-x86_64.so.1, which CANNOT load on this glibc python:3.12-slim base
# (dlopen fails: "libc.musl-x86_64.so.1: cannot open shared object file"), so the
# demo tier silently degrades to the honest tower-side label. The only glibc
# (manylinux) prebuilt cp312 wheels on that index are 0.2.6x — far too old to load
# the Qwen2.5 GGUF architecture. So we compile llama-cpp-python==0.3.19 from source
# here: recent enough to load the Qwen2.5-Coder GGUF AND producing a glibc-linked
# libllama.so that actually loads. NO `|| echo` mask — the demo tier is a HARD
# requirement of the published image (the ghcr-build-push "Demo tier serves REAL
# local model" step boots the image and fails the build if the alloy demo tier does
# not serve genuine local llama.cpp output), so a failed compile must fail LOUD.
# GUARD: .github/workflows/llama-wheel-guard.yml re-builds this exact pinned version
# from source on cp312/linux_x86_64 and asserts the resulting libllama.so links
# glibc (not musl) and imports — verifying, not assuming, the contract on each bump.
# GGML_NATIVE=OFF keeps the build portable (no -march=native) across CI + box CPUs.
#
# BUILD-ENV RESILIENCE (a11oy-build-resilience): the from-source compile is heavy.
# On the strict PUBLISHED-image path (GHCR / GitHub Actions, ample RAM+time) it MUST
# succeed and is verified glibc-linked + boot-tested by ghcr-build-push's "Demo tier
# serves REAL local model" step + llama-wheel-guard.yml. On a CONSTRAINED rebuild
# (HF Spaces cpu-basic rebuilds this Dockerfile from scratch and was OOM/timing-out
# -> BUILD_ERROR, bricking the whole Space), a compile failure must NOT brick the app:
# szl_alloy_models.py already returns an HONEST tower-side label (served_locally=False,
# never a fake completion) when llama_cpp is absent. So: fail-loud when
# A11OY_REQUIRE_LOCAL_LLM=1 (set in GHCR CI), else best-effort with an honest skip.
# This preserves the published image's hard real-model guarantee while keeping the
# HF Space reliably bootable. No fabricated data either way.
# IMAGE-LEANNESS (multi-stage): the heavy from-source compile happens in the
# `llama-build` stage near the top of this file. Here we only INSTALL the
# resulting prebuilt wheel — no compiler, no build-toolchain apt churn in the
# runtime image. On the constrained path (A11OY_REQUIRE_LOCAL_LLM!=1)
# `llama-build` is the empty builder, so the mounted wheel dir is empty and we
# skip the install: the demo tier serves the HONEST tower-side label
# (szl_alloy_models.py, served_locally=False), exactly as before. The strict
# GHCR build sets =1: the wheel is present, installed, and boot-verified
# glibc-linked + importable (fail-loud). Only the two runtime shared libs
# (libgomp1/libstdc++6) are added to the image.
ARG A11OY_REQUIRE_LOCAL_LLM=0
# The wheel is BIND-MOUNTED from the builder stage (not COPY'd) so it is
# available only for the duration of this RUN and NEVER becomes an image layer.
# A `COPY --from … /tmp/wheels` + later `rm` would bake the ~tens-of-MB wheel
# permanently into a layer (a later `rm` is just a whiteout — it does not reclaim
# the bytes), defeating the leanness goal. With the bind mount the runtime image
# carries only the INSTALLED llama_cpp + libgomp1/libstdc++6 — no wheel artifact,
# no compiler, and none of the toolchain-purge residue the old single-stage RUN
# left behind. On the constrained path (!=1) llama-build is the empty builder, so
# the mount is an empty dir and we skip install (honest tower-side label).
RUN --mount=type=bind,from=llama-build,source=/wheels,target=/wheels \
    set -eux; \
    if [ "${A11OY_REQUIRE_LOCAL_LLM}" != "1" ]; then \
      echo '[a11oy] A11OY_REQUIRE_LOCAL_LLM!=1 (constrained builder, e.g. HF cpu-basic): no llama.cpp wheel built/installed. The demo tier serves the HONEST tower-side label (szl_alloy_models.py, served_locally=False, never fake output). The strict GHCR-published image sets =1 and installs the prebuilt glibc wheel + boot-verifies real local output.'; \
    else \
      apt-get update; \
      apt-get install -y --no-install-recommends libgomp1 libstdc++6; \
      apt-get clean; \
      rm -rf /var/lib/apt/lists/*; \
      pip install --no-cache-dir /wheels/*.whl; \
      python3 -c "import llama_cpp, os, glob; base=os.path.dirname(llama_cpp.__file__); so=glob.glob(os.path.join(base,'**','libllama.so'), recursive=True); assert so, 'libllama.so not found under '+base; d=open(so[0],'rb').read(); assert b'libc.so.6' in d and b'libc.musl-x86_64.so.1' not in d, 'libllama.so is not glibc-linked: '+so[0]; print('[a11oy] llama_cpp installed from prebuilt glibc wheel OK:', so[0], getattr(llama_cpp,'__version__','?'))"; \
    fi
# GGUF weight — RELIABLY PRESENT (pinned revision + retry + integrity verify), NOT best-effort.
# Previously a single best-effort `hf_hub_download(...) || echo` step: a transient download
# failure silently shipped an image with NO model, so the alloy demo tier always degraded to
# the tower-side label. Now we pin the EXACT repo revision, retry with backoff, and HARD-VERIFY
# the downloaded file's byte size + sha256 against the published LFS digest. The build FAILS LOUD
# if the weight is not reliably present, so every published image genuinely carries the GGUF and
# the demo tier serves REAL on-CPU output. The honest tower-side fallback in szl_alloy_models.py
# remains for any runtime where the weight is absent (e.g. local dev / bring-your-own-weights).
# Apache-2.0 weight; fetched from the original HF repo, never redistributed in this repo.
ARG A11OY_ALLOY_GGUF_REPO=Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF
ARG A11OY_ALLOY_GGUF_FILE=qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
ARG A11OY_ALLOY_GGUF_REV=ebb2015119c907b064c512bf053e945850b5875f
ARG A11OY_ALLOY_GGUF_SHA256=1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32
ARG A11OY_ALLOY_GGUF_SIZE=491400064
ARG A11OY_REQUIRE_LOCAL_LLM=0
ENV A11OY_REQUIRE_LOCAL_LLM=${A11OY_REQUIRE_LOCAL_LLM}
RUN python3 <<'GGUFPY'
import hashlib, os, sys, time
from huggingface_hub import hf_hub_download

# RESILIENCE: on a constrained builder (A11OY_REQUIRE_LOCAL_LLM!=1, e.g. HF cpu-basic)
# the llama.cpp compile was skipped, so the 491MB GGUF is dead weight + slows the build.
# Skip the download too; the demo tier serves the HONEST tower-side label. The strict
# GHCR image sets =1 and DOES fetch + sha/size-verify the weight (boot-tested in CI).
if os.environ.get("A11OY_REQUIRE_LOCAL_LLM") != "1":
    print("[a11oy] A11OY_REQUIRE_LOCAL_LLM!=1: skipping GGUF weight fetch (demo tier = honest tower-side label). App boots normally.", flush=True)
    sys.exit(0)
repo      = os.environ["A11OY_ALLOY_GGUF_REPO"]
fname     = os.environ["A11OY_ALLOY_GGUF_FILE"]
rev       = os.environ["A11OY_ALLOY_GGUF_REV"]
want_sha  = os.environ["A11OY_ALLOY_GGUF_SHA256"].lower()
want_size = int(os.environ["A11OY_ALLOY_GGUF_SIZE"])
dest      = "/app/models"
os.makedirs(dest, exist_ok=True)

def verify(p):
    if not p or not os.path.exists(p):
        return "missing"
    sz = os.path.getsize(p)
    if sz != want_size:
        return "size %d != expected %d" % (sz, want_size)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != want_sha:
        return "sha256 %s != expected %s" % (got, want_sha)
    return None

last = None
for attempt in range(1, 7):
    try:
        p = hf_hub_download(repo_id=repo, filename=fname, revision=rev, local_dir=dest)
        last = verify(p)
        if last is None:
            print("[a11oy] GGUF verified present: %s (%d bytes, sha256 ok, rev %s)"
                  % (fname, want_size, rev[:12]), flush=True)
            sys.exit(0)
        print("[a11oy] attempt %d: integrity check failed: %s" % (attempt, last), flush=True)
        try:
            os.remove(p)
        except OSError:
            pass
    except Exception as e:
        last = "%s: %s" % (type(e).__name__, str(e)[:200])
        print("[a11oy] attempt %d: download failed: %s" % (attempt, last), flush=True)
    time.sleep(min(60, 5 * attempt))

# RESILIENCE (a11oy-build-resilience): fail-loud on the strict published-image path
# (A11OY_REQUIRE_LOCAL_LLM=1 in GHCR CI), else honest skip so a constrained HF rebuild
# still boots (demo tier shows the tower-side label, never fake output).
if os.environ.get("A11OY_REQUIRE_LOCAL_LLM") == "1":
    sys.stderr.write("[a11oy] FATAL: could not obtain a verified GGUF after retries: %s\n" % last)
    sys.exit(1)
sys.stderr.write("[a11oy] NOTE: GGUF weight not obtained (%s); demo tier will serve the HONEST tower-side label. App boots normally.\n" % last)
sys.exit(0)
GGUFPY
# Drop transient download metadata; the real weight stays at /app/models/<file>.
RUN rm -rf /app/models/.cache /root/.cache/huggingface 2>/dev/null || true
ENV A11OY_ALLOY_GGUF=/app/models/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf

# ── BUILD-TIME EXTERNAL-DOWNLOAD AUDIT ───────────────────────────────────────
# Context: llama-wheel-guard.yml added a weekly scheduled re-verify + ntfy page
# for the pinned llama-cpp-python wheel because an externally-hosted, build-time,
# OPTIONALLY-MASKED dependency can vanish upstream with NO repo edit and silently
# degrade a feature. This is the record of auditing the WHOLE Dockerfile for any
# OTHER download with that same silent-degradation shape. Every externally-hosted
# build-time fetch in this file falls into one of three buckets:
#
#   1. ALREADY GUARDED (externally-hosted, optionally-skipped, feature-degrading):
#      - llama-cpp-python source build (above, A11OY_REQUIRE_LOCAL_LLM-gated)
#        -> .github/workflows/llama-wheel-guard.yml (weekly schedule + ntfy page)
#      - GGUF weight hf_hub_download (above, A11OY_REQUIRE_LOCAL_LLM-gated)
#        -> .github/workflows/gguf-weight-guard.yml (weekly schedule + ntfy page)
#      These are the only two downloads that can disappear upstream AND degrade a
#      feature behind an honest fallback (the alloy demo tier's tower-side label),
#      so they are the only two that warrant the scheduled-reverify+page pattern.
#
#   2. FAIL-LOUD build tooling (NOT optionally masked -> no silent degrade):
#      - NodeSource installer  (curl -fsSL https://deb.nodesource.com/setup_22.x)
#      - GitHub CLI apt repo   (curl -fsSL https://cli.github.com/packages/...)
#      - PyPI pip installs     (fastapi/uvicorn/huggingface_hub/openai/slowapi/…)
#      All use `curl -fsSL` / plain `pip install` with NO `|| echo` / `|| true`
#      mask. If any of these vanish upstream the image build FAILS RED on the very
#      next push/PR/scheduled docker build — the disappearance is already loud, so
#      a separate re-verify guard would be redundant. (sqlite-vss was intentionally
#      dropped from the build and has an honest cosine-similarity fallback.)
#
#   3. IN-REPO COPY, not an external fetch at all (cannot vanish upstream):
#      knowledge.json, corpus/, live_snapshots/, and the szl_*/a11oy_* modules are
#      COPY'd from this repo. The former build-time `git clone` of the private
#      corpus was already replaced by an in-image COPY (see note near the top).
#
# Conclusion: no UNGUARDED masked/optional external build-time download remains.
# If a future edit adds one (e.g. another `hf_hub_download`, an `ADD <url>`, a
# `curl ... || echo`, or a pip `--index-url` to a third-party host that a feature
# silently falls back from), add a sibling scheduled guard mirroring
# llama-wheel-guard.yml / gguf-weight-guard.yml (weekly schedule + scheduled-run-
# only ntfy page via SLACK_WEBHOOK_URL) and list it in bucket 1 above.
# DCO: Signed-off-by: Forge <forge@szlholdings.ai>
# ─────────────────────────────────────────────────────────────────────────────

# ADDITIVE (Live-Data Layer, 2026-06-06, Warhacker): SHARED live-feed proxy module
# a11oy_live_feeds.py exposes GET /api/a11oy/v1/live/<feed> (server-side fetch+cache,
# CORS-safe same-origin, honest live/cached/self labels, NEVER fabricated). The
# bundled live_snapshots/ are the in-image fallback served labelled 'cached' when an
# upstream feed is unreachable. Per-file COPY (this Dockerfile never uses `COPY . .`)
# -- without these the import fails and the /v1/live/* routes fall through to the SPA.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ---------------------------------------------------------------------------
# CONSOLIDATED ROOT-FILE COPY LAYERS (segment B: post-LLM-gate) — Docker max-depth fix, Opus 4.8.
# One image layer per COPY; collapsed root-file->same-name COPYs into grouped
# multi-source COPYs landing at the /app WORKDIR root. IDENTICAL file set ships
# to IDENTICAL paths (set-equality proven). Never `COPY . .`; subpath/dir COPYs
# untouched; A11OY_REQUIRE_LOCAL_LLM gate + demo-tier RUN logic untouched.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# ---------------------------------------------------------------------------
COPY live_snapshots/ ./live_snapshots/

# ADDITIVE (Investor-WOW Layer, 2026-06-08, Dev1): a11oy_dev1_endpoints.py exposes
# the four founder-approved WOW surfaces: POST /v1/wow/govern (Drop-on-Anything
# governed turn + ungoverned-vs-governed catch), GET /v1/wow/ledger (unified
# cross-vertical tamper-evident receipt chain), /v1/wow/roi (cost-of-failure model,
# labeled assumptions), /v1/wow/router-latency (live router topology). Self-contained,
# DSSE-signed receipts, honest labels, 0 fabricated data, 0 CDN. Per-file COPY (this
# Dockerfile never uses `COPY . .`) -- without it the import fails and the /v1/wow/*
# routes fall through to the SPA. serve.py imports it try/except-guarded.
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
#
# Signing-key loader (a11oy_signing_key.py): load_signing_key() reads a11oy's
# PERSISTENT ECDSA P-256 receipt key from the mounted Secret. a11oy_dev1_endpoints.py
# imports it, so it MUST be COPY'd into the image (this Dockerfile never uses
# `COPY . .`). Without this line the import fails, the loader never runs, and
# serve.py silently falls back to a throwaway in-process key that changes on every
# restart -- which breaks offline verification of every receipt a11oy ever signed.
# Guarded by .github/workflows/signing-key-image-guard.yml.

# ADDITIVE (Vertical Packs Layer, 2026-06-08, Dev2): a11oy_vertical_feeds.py exposes
# the 5 vertical packs (Defense/Gov, Finance, Legal, Enterprise/Cyber, Real Estate)
# under /api/a11oy/v1/vert/* -- real live server-side feeds (CISA KEV, NVD, Federal
# Register, CourtListener, Yahoo, Coinbase, Frankfurter FX, GitHub events, NYC HPD/DOB,
# Treasury), each running the governed loop (szl_governance_gateway) + emitting
# DSSE-signed receipts (szl_dsse + szl_khipu, all already COPY'd above). Honest
# labels, 0 fabricated data, 0 CDN. Per-file COPY (this Dockerfile never uses
# `COPY . .`) -- without it the import fails and the /v1/vert/* routes fall through
# to the SPA. serve.py imports it try/except-guarded; register() self-reorders its
# routes to the front of the router so they beat the proxy + SPA catch-all.
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

# ADDITIVE (Deep Feeds Layer, 2026-06-08, Dev-A): a11oy_deva_feeds.py exposes the 10
# deep tabs (RealEstate 5: Market Pulse, Distress Radar, Ownership Graph, Deal Intel,
# Broker Edge; Finance 5: Quant Desk, Crypto Live, Markets Macro, Prediction Markets,
# Risk & Fraud Obs.) under /api/a11oy/v1/deva/* -- granular live server-side feeds
# (Yahoo v8, Coinbase, CoinGecko, Frankfurter FX, Treasury, NYC HPD wvxf-dwi5 + DOB,
# Polymarket gamma, SEC EDGAR, NVD), reusing a11oy_vertical_feeds governed_turn/_ledger
# + szl_khipu/szl_dsse for signed receipts. Honest labels, 0 fabricated data, 0 CDN.
# Per-file COPY (this Dockerfile never uses `COPY . .`); register() front-moves its
# routes so they beat the proxy + SPA catch-all.

# ADDITIVE (Provenance & Trust Anchor, 2026-06-08): a11oy_amaru_feeds.py exposes the
# 5 trust tabs (Public-Ledger Anchor LIVE, Post-Quantum Signing PQC, Receipt
# Provenance Graph 3D, Tamper/Audit Verifier, Anchor Health) under
# /api/a11oy/v1/provenance/* -- live CT signed tree heads (Google Argon/Xenon,
# Cloudflare Nimbus) + Bitcoin tip (mempool.space/blockstream), reusing
# a11oy_vertical_feeds governed_turn + szl_khipu/szl_dsse for signed receipts.
# Honest PQC labels (classical ECDSA-P256 live; ML-DSA/ML-KEM/SLH-DSA roadmap),
# 0 fabricated data, 0 CDN. Per-file COPY; register() front-moves its routes so
# they beat the proxy + SPA catch-all.

# ADDITIVE (MINED UPGRADES, 2026-06, Yachay): four self-contained operator surfaces,
# each adopting a PERMISSIVELY-licensed PATTERN (NOTICE updated) and evolving it into
# an a11oy-native mechanism. Stdlib-only (no torch/numpy/CDN). Per-file COPY (this
# Dockerfile never uses `COPY . .`) -- without these the imports fail and the
# /governance-gateway, /abacus-verify, /decision-uncertainty, /gor-audit routes
# fall through to the SPA shell. serve.py imports them try/except-guarded.

# ADDITIVE (RE-SWEEP WAVE 2, 2026-06, Yachay): four MORE operator surfaces from the
# P0 re-sweep backlog, each adopting a PERMISSIVE pattern (MIT/Apache; NOTICE updated)
# and evolving it into an a11oy-native mechanism. Stdlib-only (no torch/numpy/CDN);
# graph tabs render with the already-vendored cytoscape. Per-file COPY (this Dockerfile
# never uses `COPY . .`) -- without these the imports fail and /sovereign-search,
# /consensus-clusters, /mission-ledger, /budget-router fall through to the SPA shell.
# serve.py imports them try/except-guarded.

# ADDITIVE (WAVE9/10 INSTILLATION, 2026-06): the "Proven Formulas (experimental)"
# surface wiring a11oy-targeted lutar-lean Wave9+Wave10 theorems as honest cards with
# verbatim #print axioms + real in-image checks (Gershgorin matrix-health, Ville
# anytime-alarm, replay-determinism+tamper-localize, quorum-intersection, DSSE
# injectivity). Stdlib-only (no torch/numpy/CDN). Per-file COPY (this Dockerfile never
# uses `COPY . .`) -- without this the import fails and /proven-formulas +
# /api/a11oy/v1/proven/* fall through to the SPA shell, and the governance-gateway
# matrix-health pre-flight reports the module missing. serve.py + szl_governance_gateway
# import it try/except-guarded. LOCKED-proven stays EXACTLY 8; Lambda=Conjecture 1.
# Operational Readiness backend (deployed-vs-repo reality, live/cached/unreachable).
# serve.py imports this try/except-guarded; without this per-file COPY the import
# fails and /api/a11oy/v1/readiness 404s (falls through to the SPA shell).
# Quantum-Bio Λ-v5 backend (quantum-bio-v5): VERIFIED quantum-biology models
# (Mitchell pmf + two-ion, Lindblad coherence, radical-pair compass, Λ-v5 gate).
# serve.py imports this try/except-guarded; without this per-file COPY the import
# fails and /api/a11oy/v1/qbio/* 404s. Pure stdlib (+optional numpy already present).
# Contracting Readiness backend (SAM/CAGE + SBIR/STTR eligibility, web-sourced,
# honest verified/confirmed/needs_founder_input/needs_founder_action labels, source
# liveness probes, 0 fabricated org values). serve.py imports this try/except-guarded;
# without this per-file COPY the import fails and /api/a11oy/v1/contracting 404s.
# ADDITIVE (Open-Problem Bounty Board, bounties-tab-patch): stdlib-only bounty module
# + the canonical bounty YAMLs (single source of truth, copied byte-identical from
# szl-holdings/lutar-lean). Per-file/dir COPY (this Dockerfile never uses `COPY . .`)
# -- without these the import fails and /api/a11oy/v1/bounties 404s.
COPY bounties/ ./bounties/

# ---------------------------------------------------------------------------
# THEOREM-BACKED feature badges (provenance chain: paper DOI -> Lean proof
# file+sha256 -> deployed feature). serve.py imports szl_feature_badge and calls
# register(app, "a11oy") to mount /api/a11oy/v1/badge[s]. The module resolves
# each feature's Lean proof status LIVE from source, so the four backing .lean
# files (from szl-holdings/lutar-lean) are COPY'd preserving path (this
# Dockerfile never uses `COPY . .`). Without them the badge honestly degrades to
# proof_file_present:false instead of verifying the sha256 live.
COPY szl_feature_badge.py feature_provenance.json ./
COPY proofs/lutar-lean/Lutar/Thesis/TH_V18_08_KhipuChecksumInvariant.lean ./proofs/lutar-lean/Lutar/Thesis/TH_V18_08_KhipuChecksumInvariant.lean
COPY proofs/lutar-lean/Lutar/Thesis/TH_V18_05_ReceiptTransduction.lean ./proofs/lutar-lean/Lutar/Thesis/TH_V18_05_ReceiptTransduction.lean
COPY proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean ./proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean
COPY proofs/lutar-lean/Lutar/KhipuConsensus.lean ./proofs/lutar-lean/Lutar/KhipuConsensus.lean

# ---------------------------------------------------------------------------
# SZL Enterprise Connector Framework. serve.py imports szl_connectors_serve
# (which imports the szl_connectors/ package + szl_connector_mcp) and calls
# register(app, "a11oy") to mount /api/a11oy/connectors + per-connector
# health/read/write/oauth + the /integrations page. Per-file/dir COPY (this
# Dockerfile never uses `COPY . .`) -- without these the import fails and the
# connector routes fall through to the SPA. pages/integrations.html is already
# shipped by the wholesale `COPY pages/ ./pages/` above, so no extra page COPY
# is needed. 52 connectors (13 live-now / 38 credential-READY / 1 SAMPLE).
# Doctrine v11: honest states, no fabricated records, Lambda-gated+DSSE writes.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ---------------------------------------------------------------------------
COPY szl_connectors/ ./szl_connectors/

# ADDITIVE (Task: HF Dataset Bucket Foundation): the ONE shared Hugging Face
# 'bucket' client both flagships reuse. Durable, append-only, idempotent
# (content-addressed dedup), offline-tolerant local queue + flush, rate-aware
# batched Hub commits. Pure stdlib + huggingface_hub (lazy). BYTE-IDENTICAL
# across a11oy + killinchu (shared-file-drift enforces it via this COPY list).
# This Dockerfile never uses `COPY . .` — without this line `import
# szl_hf_bucket` fails. Imported lazily by callers; no boot-time side effects.
# Forge fix: these modules are on main + imported by serve.py (try/except) but were NEVER COPY'd
# into the image -> ModuleNotFoundError at startup -> /api/a11oy/v1/research/* + dark surfaces 404.
# copy-sync lockstep guard (CHECK 2): these modules are on main + imported by serve.py
# (try/except-guarded) but were NEVER COPY'd into the image, so the import silently fell
# back to a STUB on the Space (the recurring "merged-but-not-live" failure). conduction_aphasia
# backs /conduction; szl_a11oy_live_feeds backs the a11oy live-feeds organ; szl_jack is imported
# transitively by szl_live_wires. Per-file COPY (this Dockerfile never uses `COPY . .`). They
# auto-mirror to the HF Space via hf-sync-backend.yml (which parses these COPY lines).



# --- ESTATE ECOSYSTEM FOUNDATION (Dev5, 2026-06): byte-identical shared modules ---
# 3 shared JS (label engine / receipt-cosign / codename sanitizer) + codename gate + ecosystem router.
# szl_organ_health.py: same-origin /api/a11oy/v1/organ-health/<role> proxy that resolves an honest
# role slug -> real backend healthz SERVER-SIDE (G5 root-fix so /status never serves a codename URL).
COPY static/shared/szl_label_engine.js static/shared/szl_receipt_cosign.js static/shared/szl_codename_sanitizer.js static/shared/szl_holo3d.js ./static/shared/

# --- GOVERNANCE / EVAL / CALIBRATION layer (Dev B, 2026-06): ADDITIVE ---
# serve.py imports a11oy_governance_endpoints (try/except-guarded) which imports
# the shared modules below; the page /governance is served from web/governance.html.
# Per-file COPY (this Dockerfile NEVER uses `COPY . .`) — without these lines the
# import falls back to the non-fatal except and /api/a11oy/v1/gov/* + /governance
# 404 (the recurring "merged-but-not-live" failure). szl_conformal is a SHARED
# helper Dev D (killinchu) also imports for threat classification. The Colang
# policy files are the file-backed, independently-auditable single source of
# truth for the ROE flows. 0 runtime CDN (the page uses the already-vendored
# /vendor/chart.umd.min.js). These auto-mirror to the HF Space via the backend
# sync workflow which parses these COPY lines.
COPY policy/colang/roe_core.co policy/colang/killinchu_threat.co ./policy/colang/
# GOVERNED AUTO-REVIEW (Integration I2) — keystone autonomy layer: governed +
# signed evolution of Cursor's Auto-review. The classifier module runs INLINE
# before each Action node; verdicts are Lambda-gated, DSSE-signed, mapped to
# OPA/Rego + OSCAL + NIST AI RMF MANAGE, conformal-calibrated, with flapping
# detection. autoreview.html is served at /autoreview (0 runtime CDN; uses the
# already-vendored /vendor/chart.umd.min.js + in-image shared label/receipt
# engines). These COPY lines are parsed by the backend HF-sync workflow so the
# files reach the Space (avoids the recurring "merged-but-not-live" failure).
COPY scripts/check_tau_eval.py ./scripts/check_tau_eval.py
# Lean4Agent workflow-invariant scaffold (ROADMAP / EXPERIMENTAL — not a verified
# proof yet; rendered as ROADMAP in the UI). Shipped so the .lean source is in
# the image for audit; no Lean toolchain is invoked at runtime.
COPY lean4agent/WorkflowInvariants.lean lean4agent/README.md ./lean4agent/

# GRC ALIGNMENT surface (Lane I5) — in-product ISO 42001 / NIST AI RMF / 800-53 /
# EU AI Act coverage matrix, 13 Λ→NIST mapping, OPA/Rego gates, OSCAL component-def,
# DSSE Receipt Schema v2. Explicit per-file COPY (this Dockerfile never uses COPY . .).
# serve.py imports a11oy_grc which imports a11oy_grc_data AND a11oy_grc_restraint
# (stdlib-only restraint scoring); the OSCAL JSON + Rego bundle ship in the image for
# audit. Without a11oy_grc_restraint.py in this COPY set the transitive import falls
# back to a stub in the HF image (merged-but-not-live) and the copy-sync lockstep guard
# (CHECK 2) fails. szl_cuas_formulas.py (shared, byte-identical w/ killinchu) is already
# COPY'd above for the active-flux router + platform-dynamics math.
COPY compliance/oscal/a11oy-component-definition.json ./compliance/oscal/a11oy-component-definition.json
COPY compliance/rego/classification_boundary.rego compliance/rego/human_override_required.rego compliance/rego/deployment_readiness.rego compliance/rego/manifest.json ./compliance/rego/

# HOLOGRAPHIC 3D ENERGY SHOWCASE (Lane energy/06, 2026-06-14). The shared szl3d 3D
# toolkit (Dev0 foundation) + the 16-19 graph energy showcase. serve.py imports the
# top-level module szl3d_holographic (registers GET /static/3d/{path} + /holographic +
# /api/a11oy/v1/holographic/info) — it MUST be in this COPY set or the guarded import
# falls back to a stub in the HF image (copy-sync lockstep CHECK 2). The whole 3D asset
# tree (vendored three.js r170 WebGL2+WebGPU builds + addons, szl3d_{boot,live,label}.js,
# the 9 surface modules incl. the upgraded energy surface, the energy_showcase module,
# the selftest harness, VENDOR_MANIFEST.md) ships as a DIRECTORY COPY — bulk image-only
# vendored/authored 3D content, served same-origin at /static/3d (0 runtime CDN), exactly
# like `COPY console/ ./static/`. Directory COPYs are image-only per the guard (CHECK 3
# only flags per-file served assets); the two web/*.html pages below are per-file and are
# therefore declared in .github/copy-sync-lockstep.json image_only_assets.
COPY a11oy_threat_intel.py a11oy_live_feeds.py a11oy_signing_key.py a11oy_dev1_endpoints.py a11oy_vertical_feeds.py a11oy_deva_feeds.py a11oy_devb_endpoints.py a11oy_amaru_feeds.py szl_governance_gateway.py szl_abacus_verify.py szl_decision_uncertainty.py szl_gor_audit.py szl_sovereign_search.py szl_consensus_clusters.py szl_mission_ledger.py szl_budget_router.py szl_wave910_proofs.py szl_evidence_research.py szl_uds_fleet.py szl_readiness.py szl_quantum_bio.py szl_mosaic_governance.py szl_unified_formulas.py szl_cuas_formulas.py szl_contracting.py szl_bounties.py szl_putnam.py szl_connectors_serve.py szl_connector_mcp.py szl_conjecture_factory.py szl_hf_bucket.py szl_metrics_prom.py szl_research_infra.py szl_dark_surfaces_register.py szl_anatomy_loop.py conduction_aphasia.py szl_a11oy_live_feeds.py szl_jack.py szl_codename_gate.py szl_ecosystem_routes.py szl_organ_health.py a11oy_governance_endpoints.py szl_tau_eval.py szl_calibration.py szl_conformal.py szl_colang_policy.py szl_ietf_receipt.py a11oy_autoreview.py a11oy_grc.py a11oy_grc_data.py a11oy_grc_restraint.py szl3d_holographic.py szl_rekor_anchor.py ./
# feat/a11oy-models: live external model intel (LMArena Elo + HF Hub + Pareto) for llm/arena tabs.
COPY a11oy_model_intel.py ./a11oy_model_intel.py
# ADDITIVE (EXPERIMENTAL TIER INSTILLATION, 2026-06-30, Dev A): wires the full
# experimental (CI-green, NOT in locked-8) tier surface. Honesty doctrine v11.
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
COPY a11oy_experimental_tier.py ./a11oy_experimental_tier.py
# feat/a11oy-business: live SEC EDGAR + Treasury FiscalData + FRED markets data for business tab.
COPY a11oy_markets.py ./a11oy_markets.py
COPY static/3d/ ./static/3d/
# Standalone a11oy holographic energy page (/energy-holographic) + the upgraded HF energy
# page (/energy, mirrored to the SZLHOLDINGS/energy Space). Both load the shared showcase
# module above via the same-origin importmap. Per-file served assets -> image_only_assets.
# 3D Holographic Energy View (/energy-3d, /a11oy/energy-3d): standalone sovereign
# WebGL page + its ES module. The page (web/energy-3d.html) is served via _ptg_serve
# from /app/web/; its Three.js GPGPU particle + node-edge module (static/energy_3d.js)
# is served at /energy-3d/app.js. Binds LIVE to /api/a11oy/v1/energy/mesh; reuses the
# vendor3d Three.js r160 (MIT) above via the page importmap — 0 runtime CDN. Per-file
# served assets -> declared image_only in copy-sync-lockstep.json. Without these COPYs
# the route falls through to the SPA shell and the module 404s. Doctrine v11.
COPY static/energy_3d.js ./static/energy_3d.js
# Grid Energy Harvest honest dashboard (/energy-harvest); served via _ptg_serve from /app/web/.
# Immune (Hukulla) honest egress-gate page (/immune, /a11oy/immune). Standalone
# sovereign page (0 runtime CDN), binds to live /api/a11oy/v1/immune/* (status/
# gates/feed + a live inspect->verdict box showing real deny/allow + signed Khipu
# receipt digest). Per-file served asset -> declared image_only in copy-sync-
# lockstep.json (same baked-only pattern as web/energy.html). Codename-free.
# Materials (Q'allariy) honest Verifiable Alloy & Crystal Discovery page (/materials,
# /a11oy/materials). Standalone sovereign page (0 runtime CDN), binds to live
# /api/a11oy/v1/materials/* (novelty/certify/screen) + /immune/verdict fallback; a
# crystal-novelty form, a PAC-Bayes certificate panel, an Immune screen panel, and an
# honest PROVEN/CONJECTURE/ROADMAP claim-sheet footer. image_only (baked into the
# GitHub-built image via this per-file COPY, served from /app/web/) and declared an
# accepted divergence in .github/hf-module-drift-allow.json (same baked-only pattern
# as web/immune.html + web/energy.html). Codename-free.
COPY web/governance.html web/autoreview.html web/energy-holographic.html web/energy.html web/energy-3d.html web/energy-harvest.html web/immune.html web/materials.html web/proof.html web/trust.html ./web/
# a11oy /code GOVERNED RUN-LOOP view (2026-07-06): standalone sovereign page (0 CDN)
# served at /code by _ptg_serve("code.html"); binds to the REAL engine endpoints
# (a11oy_code_engine) + the a11oy_code_runloop orchestrator. Same baked-only per-file
# COPY pattern as web/immune.html + web/energy.html. Codename-free. Honest LIVE/MODELED.
COPY web/code.html ./web/

# GOVERNED MODEL-HARNESS (Wave F module + Wave G /code wire-in, 2026-07-07):
# szl_model_harness.py registers /api/a11oy/v1/harness/{profiles,profiles/{id},apply}
# and exposes an importable apply() core. a11oy_code_engine + a11oy_code_runloop +
# szl_llm_registry import it (try/except-guarded) so an OPTIONAL harness_profile_id on
# a /code run-loop step (or /llm/route) runs the model through the profile system layer
# + Λ-gate and folds the profile provenance into the step's SIGNED receipt. The profile
# BODIES live under harness_profiles/ (manifests + bodies/*.md, referenced by path/env —
# never inlined). MUST be per-file COPY'd (this Dockerfile uses no `COPY . .`) or the
# guarded import falls back and the harness endpoints 404 / harness_profile_id is a no-op
# (merged-but-not-live). Additive; behavior transfer is MODELED (disposition only, not
# capability). Λ = Conjecture 1 (advisory). Real DSSE in-Space, honest UNSIGNED locally.
COPY szl_model_harness.py ./szl_model_harness.py
COPY harness_profiles/ ./harness_profiles/

# git_sha wireup (FORGE-INSTRUCTION-gitsha-quiet-window): surface the deployed commit
# at the /honest endpoint so a stale box or Space is self-detecting. Provided at build
# time (box rebuild passes --build-arg SZL_GIT_SHA=$(git rev-parse HEAD); HF Space sets
# the SZL_GIT_SHA variable). Kept last so a per-build value busts no earlier cache.
ARG SZL_GIT_SHA=unknown
ARG SZL_BUILD_TIME=unknown
ENV SZL_GIT_SHA=${SZL_GIT_SHA} \
    SZL_BUILD_TIME=${SZL_BUILD_TIME}
CMD ["python", "serve.py"]


# Build cache-bust 2026-06-05T00:00Z (Orchestrator Squad):
# szl_parity_gaps.py already COPY'd at line 68 (commit 543ca95).
# Added COPY szl_receipt_substrate.py + szl_alloy_embed_fabric.py + szl_ayni_quorum.py.
# All 5 parity endpoints now deployable. All 63 COPY sources verified present in repo.

# Build cache-bust 2026-06-06T09:00Z (model-integration squad, Opus 4.8):
# Added OPEN-WEIGHT ALLOY MODEL LAYER: COPY szl_alloy_models.py + szl_llm_registry.py
# (was 404/never-copied) + szl_elite_console.py; optional non-fatal llama-cpp-python +
# tiny Apache-2.0 GGUF fetch for the live CPU demo tier (honest tower-side fallback).
# UNIFIED into the existing LLM registry (one roster). DeepSeek-Coder-V2 = CODE_PRIMARY.
# C20/W7-5 router, W5-3/W7-4 conformal, C10-C12 consensus; every call -> signed receipt.

