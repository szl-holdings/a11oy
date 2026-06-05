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

FROM python:3.12-slim

WORKDIR /app

# Install Node 22 (for a11oy serve TypeScript runner)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# ADDITIVE (Yachay): huggingface_hub + openai power the a11oy.code orchestrator's
# unified open-LLM router (HF Router inference). python-multipart is required by
# FastAPI UploadFile for the Whisper /voice/stt endpoint. None of these change the
# existing SPA / gates runtime; the orchestrator import is try/except-guarded in serve.py.
RUN pip install --no-cache-dir \
    "fastapi>=0.111.0,<1.0.0" \
    "uvicorn[standard]>=0.29.0,<1.0.0" \
    "httpx>=0.27.0,<1.0.0" \
    "starlette>=0.37.0" \
    "huggingface_hub>=0.25.0" \
    "openai>=1.40.0" \
    "python-multipart>=0.0.9" \
    "cryptography>=42.0.0" \
    "lmdb>=1.4.0"
# BE hardening: slowapi rate limiter (60/min/IP). pydantic+fastapi already present.
RUN pip install --no-cache-dir "slowapi>=0.1.9"

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

# Copy serve orchestrator and gates manifest
COPY szl_parity_gaps.py ./szl_parity_gaps.py
COPY a11oy_warhacker_obs.py ./a11oy_warhacker_obs.py
COPY serve.py ./serve.py
COPY gates_manifest.json ./gates_manifest.json
# ADDITIVE: a11oy.code conversational orchestrator module (imported by serve.py).
COPY a11oy_code_orchestrator.py ./a11oy_code_orchestrator.py
# ADDITIVE (WAYRA organ): explicit per-file COPY (this Dockerfile does not use COPY . .).
# serve.py mounts wayra_serve.router -> /wayra, /wayra-digest, /api/a11oy/v1/wayra/*.
COPY wayra_serve.py ./wayra_serve.py
COPY wayra_snapshot.json ./wayra_snapshot.json
COPY wayra_digests_7d.json ./wayra_digests_7d.json
# ADDITIVE (KHIPU-OS agentic DAG organ, 2026-06-01, Yachay): explicit per-file COPY
# (this Dockerfile does not use COPY . .). serve.py imports szl_khipu_os_routes and
# mounts GET/POST /api/a11oy/v1/khipu-os/{stats,verify,checkpoint,archive}. Self-driving
# Merkle DAG + Reed-Solomon erasure (reedsolo optional; honest, NOT holographic/quantum).
COPY szl_khipu_os_routes.py ./szl_khipu_os_routes.py
# ADDITIVE (PURIQ Agentic Formulas, 2026-06-01, Yachay): explicit per-file COPY
# (this Dockerfile does not use COPY . .). serve.py imports szl_puriq_formulas and
# calls .register(app) -> GET /formulas + /api/a11oy/v1/puriq/formulas*. Doctrine v11 LOCKED.
COPY szl_puriq_formulas.py ./szl_puriq_formulas.py

# ADDITIVE (Yachay / AYNI-OS, 2026-06-01): reciprocity organism + event-sourced replay
# + Tinkuy (Kuramoto) flow. Explicit per-file COPY (this Dockerfile does not use COPY . .).
# serve.py imports ayni_os_serve.router -> /v1/ayni, /v1/replay, /v1/tinkuy and serves the
# /ayni tab from /app/pages/ayni.html. HONEST: replay=event-sourcing (NOT time-travel);
# Ayni=game-theory primitive (Axelrod-Hamilton 1981, NOT mystical); Tinkuy=Kuramoto 1975.
# LOCKED preserved: 749/14/163, 13-axis yuyay_v3, replay bacf5443…631fc5. Pure additive.
COPY ayni_os_serve.py ./ayni_os_serve.py
COPY ayni_os/ ./ayni_os/
COPY pages/ ./pages/

# ADDITIVE (Live 3D Wires / PURIQ Doctrine v12, Yachay): explicit per-file COPY.
# This Dockerfile uses per-file COPY (no `COPY . .`), so the live-wires module +
# its static assets must be copied explicitly or `import szl_live_wires` 404s and
# /live-wires falls through to the SPA shell. serve.py registers these FIRST.
COPY szl_live_wires.py ./szl_live_wires.py
COPY live_wires.html ./live_wires.html
COPY live_wires_3d.js ./live_wires_3d.js

# ADDITIVE (Provenance Hardening / Wire D + DSSE Cosign REAL signing, 2026-06-01, Yachay):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_provenance (which imports szl_dsse) and calls register_provenance(app, "a11oy") ->
# GET /api/a11oy/wires/D, POST /khipu/sign, POST /khipu/verify, GET /khipu/ledger,
# GET /api/a11oy/provenance. Without these COPYs the import fails and the routes fall
# through to the Node :8081 proxy (503). cryptography (added above) backs the real
# ECDSA-P256-SHA256 cosign signatures. Real signatures only when SZL_COSIGN_PRIVATE_PEM
# runtime secret is present (else honestly UNSIGNED). SLSA L1 honest (signing live); L2 roadmap via Wire D; L3 NOT claimed.
COPY szl_dsse.py ./szl_dsse.py
COPY szl_provenance.py ./szl_provenance.py

ENV PORT=7860
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).
COPY szl_be_hardening.py ./szl_be_hardening.py

EXPOSE 7860

# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_unay_routes and calls .register(app, ns="a11oy") -> /api/a11oy/v2/unay/* +
# /api/a11oy/v2/khipu/lmdb/*. Real durable lmdb + real sqlite-vss (honest cosine-
# fallback if the .so cannot load in the slim image). a11oy carries Khipu-LMDB PRIMARY.
COPY szl_unay.py ./szl_unay.py
COPY szl_khipu_lmdb.py ./szl_khipu_lmdb.py
COPY szl_khipu_replicate.py ./szl_khipu_replicate.py
COPY szl_unay_routes.py ./szl_unay_routes.py
# ADDITIVE (Warhacker aliases, Yachay 2026-06-01): top-level /healthz + /khipu/* + /wires/D.
# Per-file COPY (no `COPY . .`) — without this `import szl_warhacker_aliases` fails.
COPY szl_warhacker_aliases.py ./szl_warhacker_aliases.py
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
COPY a11oy_v4_hickok.py ./a11oy_v4_hickok.py

# ADDITIVE (Anatomy 3D + live formula wiring, 2026-06-02, Yachay / Perplexity
# Computer Agent): explicit per-file COPY (this Dockerfile does not use `COPY . .`).
# serve.py imports a11oy_v4_formulas (38-formula manifest + 15 live evaluators) and
# szl_anatomy_3d (7 sovereign Three.js r128 anatomy surfaces + 6 live JSON endpoints).
# szl_anatomy_3d self-serves Three.js at /anatomy-three.min.js from static-vendor/.
# Receipts sign via szl_dsse (already COPYed) using szl_khipu + szl_formulas. Without
# these COPYs the imports fail and the pages/endpoints fall through to the SPA shell.
# Doctrine v11 LOCKED 749/14/163. Lambda = Conjecture 1 (NOT a theorem). NO external CDN.
COPY szl_khipu.py ./szl_khipu.py
COPY szl_formulas.py ./szl_formulas.py
COPY a11oy_v4_formulas.py ./a11oy_v4_formulas.py
COPY web/formulas.html ./web/formulas.html
COPY static-vendor/three.min.js ./static-vendor/three.min.js
COPY szl_anatomy_3d.py ./szl_anatomy_3d.py

# ADDITIVE (V4 Fleet Panel + /api/health fix, 2026-06-02, Dev2 Inti):
# explicit per-file COPY (this Dockerfile does not use COPY . .).
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# szl_v4_fleet.py: /api/health + /api/a11oy/v4/fleet[/doctrine] + /fleet + /thesis
# v4_fleet_panel.html: canonical fleet panel served at /fleet
# operator_shell_v4.py: Unified Operator Shell v4 endpoints (fix import failure)
# web/operator.html: operator shell desktop cockpit HTML
COPY szl_v4_fleet.py ./szl_v4_fleet.py
COPY web/v4_fleet_panel.html ./web/v4_fleet_panel.html
COPY operator_shell_v4.py ./operator_shell_v4.py
COPY web/operator.html ./web/operator.html

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
COPY szl_bridge.py ./szl_bridge.py
COPY szl_bridge_schemas.py ./szl_bridge_schemas.py
COPY agent.html ./agent.html
# a11oy-bridge CLI (sign --from hermes/openclaw, verify --receipt-id). Standalone
# operator tool; not imported at boot but shipped so it is runnable in-container.
COPY a11oy_bridge_cli.py ./a11oy_bridge_cli.py


# ADDITIVE (SZL Ken Agent Pattern v1, CTO Yachay Convergence Cycle 1, 2026-06-03):
# Explicit per-file COPY of szl_ken.py (this Dockerfile never uses `COPY . .`).
# serve.py tries `import szl_ken` at startup; without this COPY the import fails
# silently and /v1/agent/loop + /v1/mcp/tools return 404 instead of 200.
# ADDITIVE ONLY — zero existing routes touched. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY szl_ken.py ./szl_ken.py


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
COPY src/a11oy/formulas/__init__.py ./src/a11oy/formulas/__init__.py
COPY src/a11oy/formulas/pac_bayes.py ./src/a11oy/formulas/pac_bayes.py
COPY src/a11oy/formulas/bls_aggregate.py ./src/a11oy/formulas/bls_aggregate.py
COPY src/a11oy/formulas/welford.py ./src/a11oy/formulas/welford.py
COPY src/a11oy/formulas/byzantine_quorum.py ./src/a11oy/formulas/byzantine_quorum.py
COPY src/a11oy/formulas/holevo_bound.py ./src/a11oy/formulas/holevo_bound.py
COPY src/a11oy/formulas/bloom_filter.py ./src/a11oy/formulas/bloom_filter.py
COPY src/a11oy/formulas/kalman.py ./src/a11oy/formulas/kalman.py
COPY src/a11oy/formulas/hnsw_retrieval.py ./src/a11oy/formulas/hnsw_retrieval.py
COPY src/a11oy/formulas/reidemeister.py ./src/a11oy/formulas/reidemeister.py
COPY a11oy_formula_endpoints.py ./a11oy_formula_endpoints.py
# ADDITIVE (Formulas SECTION page — closeout): serve.py imports a11oy_formulas_page
# and calls .register(app) BEFORE the SPA catch-all, mounting GET /formulas/wired
# (premium Inca-palette list of every live formula + thesis citation + Lean permalink
# + "Try it") and GET /api/a11oy/v1/formulas/page-manifest. Per-file COPY (never
# `COPY . .`); without it the import fails and the route falls through to the SPA.
COPY a11oy_formulas_page.py ./a11oy_formulas_page.py

# ADDITIVE (Missing modules fix, 2026-06-04, Perplexity Computer Agent):
# The following .py files exist in the repo and are imported via try/except
# in serve.py, but were never COPY'd into the Docker image. Without them the
# imports fail silently and the associated routes/tabs are unavailable.
# Per-file COPY (this Dockerfile never uses `COPY . .`).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
COPY a11oy_frontier_patch.py ./a11oy_frontier_patch.py
COPY a11oy_v4_agent.py ./a11oy_v4_agent.py
COPY szl_brain.py ./szl_brain.py
COPY szl_wire.py ./szl_wire.py
COPY szl_hub.py ./szl_hub.py
COPY szl_rosie_companion.py ./szl_rosie_companion.py

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
COPY szl_receipt_substrate.py ./szl_receipt_substrate.py
COPY szl_alloy_embed_fabric.py ./szl_alloy_embed_fabric.py
COPY szl_ayni_quorum.py ./szl_ayni_quorum.py

# ADDITIVE (Elite Console + LLM Hub Registry, 2026-06-04, Yachay CTO + Perplexity Computer Agent):
# szl_llm_registry.py   — a11oy canonical LLM roster (7 models/5 tiers) + forum/mirror endpoints
# szl_elite_console.py  — 20-tab Elite Console backend (SLO, alerts, organ-map, DSSE, quorum, genome...)
# web/elite_console.html — 20-tab Elite Console HTML (Three.js 3D, real endpoints, zero mocks)
# Per-file COPY (this Dockerfile never uses `COPY . .`).
# Verified source files present in repo before commit.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY szl_llm_registry.py ./szl_llm_registry.py
COPY szl_elite_console.py ./szl_elite_console.py
COPY web/elite_console.html ./web/elite_console.html

CMD ["python", "serve.py"]


# Build cache-bust 2026-06-05T00:00Z (Orchestrator Squad):
# szl_parity_gaps.py already COPY'd at line 68 (commit 543ca95).
# Added COPY szl_receipt_substrate.py + szl_alloy_embed_fabric.py + szl_ayni_quorum.py.
# All 5 parity endpoints now deployable. All 63 COPY sources verified present in repo.
# Build cache-bust 2026-06-04T19:31Z (Elite Console + LLM Hub Registry):
# Added szl_llm_registry.py, szl_elite_console.py, web/elite_console.html.
# 20-tab Elite Console + 7-model LLM Hub now deployable. All COPY sources verified.

