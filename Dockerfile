# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v9
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
    "lmdb>=1.4.0" \
    "sqlite-vss>=0.1.2"

# Clone a11oy source for the serve runtime (receipt-substrate + policy gates only)
RUN git clone --depth=1 --filter=blob:none --sparse \
    https://github.com/szl-holdings/a11oy.git /app/a11oy-src && \
    cd /app/a11oy-src && \
    git sparse-checkout set \
        packages/receipt-substrate/src \
        packages/policy/src/gates

# Copy the pre-built SPA (Brand Orchestration Layer) to the static root.
# index.html + assets/* are served directly at / and /assets/*; unknown GET -> index.html.
COPY console/ ./static/

# Copy serve orchestrator and gates manifest
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

CMD ["python", "serve.py"]
