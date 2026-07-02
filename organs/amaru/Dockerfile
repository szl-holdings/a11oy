# SPDX-License-Identifier: LicenseRef-SZL-Proprietary
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# amaru HF Docker Space — serves the amaru memory-cortex operator surface + the
# real 7-chakra runtime API at /api/amaru/* + the verbatim Replit reverse-ETL
# React SPA at /conduit/ (BASE_PATH=/conduit/, title "Amaru — The Andean Ouroboros").
#
# The root front-end is now the verbatim Replit React SPA (base=/). The /conduit/ surface is the pre-built React SPA (vite, base
# /conduit/) copied verbatim from the Replit artifact and served statically.
# ADDITIVE ONLY: no existing route, console, reasoner, or Rosie widget is touched.
# No Node build step is required at image build time — the SPA is shipped pre-built.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS backend

WORKDIR /app
COPY sidecar/ ./sidecar/
RUN pip install --no-cache-dir ./sidecar
# BE hardening: slowapi rate limiter (60/min/IP). pydantic+fastapi already present.
RUN pip install --no-cache-dir "slowapi>=0.1.9"

# ADDITIVE (Yachay / Provenance Hardening): cryptography for DSSE+Cosign Khipu signing.
RUN pip install --no-cache-dir "cryptography>=42.0"

FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

WORKDIR /app

COPY --from=backend /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY sidecar/src/amaru /app/amaru

# ADDITIVE (Doctrine v10/v11): agentic-RAG deps. CPU-only torch (no CUDA).
# Powers /api/amaru/v1/rag + /rag over SZLHOLDINGS/rag-corpus-v1 (BGE-base + FAISS).
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    "faiss-cpu>=1.8.0" \
    "sentence-transformers>=3.0.0" \
    "torch>=2.2.0" \
    "huggingface_hub>=0.23.0"

# Root front-end: the VERBATIM Replit reverse-ETL React SPA (Vite base="/"),
# served at root / per founder directive + a11oy winning pattern. The full
# /api/amaru/* runtime, Wires, brain-jack, /upgrades, /rag are PRESERVED below.
RUN mkdir -p /app/static/assets
COPY static/index.html /app/static/index.html
COPY static/assets/ /app/static/assets/

# PRESERVED: the prior /conduit/ React SPA (base=/conduit/) left intact.
COPY conduit/ /app/static/conduit/

COPY serve.py /app/serve.py
# Premium cortex reasoning UI (GET /amaru/reason). serve.py imports this.
COPY amaru_reason_page.py /app/amaru_reason_page.py
# Anatomy substrate (ADDITIVE): canonical formulas + composer routes.
COPY szl_formulas.py /app/szl_formulas.py
COPY szl_anatomy_routes.py /app/szl_anatomy_routes.py

# ADDITIVE (Doctrine v10): shared per-app BRAIN + unified LLM router + mesh wires.
COPY szl_brain.py /app/szl_brain.py
# FIX (ADDITIVE): Wire-G module imported by serve.py but COPY was omitted -> ModuleNotFoundError at startup.
COPY szl_jack.py /app/szl_jack.py
# ADDITIVE (Doctrine v10/v11): shared agentic-RAG service (organ=cortex).
COPY szl_rag.py /app/szl_rag.py
COPY szl_wire.py /app/szl_wire.py
COPY szl_dsse.py /app/szl_dsse.py
COPY szl_provenance.py /app/szl_provenance.py


# ADDITIVE (Yachay / Live 3D Wires, PURIQ-proposed): COPY the live-wires
# module + host page + scene core so `import szl_live_wires` resolves in-container.
# Without these the register() call in the server silently fails and /live-wires
# falls through to the SPA shell. ADDITIVE ONLY. Sign: Yachay.
COPY szl_live_wires.py /app/szl_live_wires.py
COPY live_wires.html /app/live_wires.html
COPY live_wires_3d.js /app/live_wires_3d.js

# ADDITIVE (Wire I): Rosie-companion module baked into the image. Yachay.
COPY szl_rosie_companion.py ./szl_rosie_companion.py
COPY serve.py ./serve.py
ENV PORT=7860
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).
COPY szl_be_hardening.py ./szl_be_hardening.py

EXPOSE 7860

# a11oy.code (ADDITIVE, Doctrine v11 §14): math-corpus + code-proxy for amaru.
COPY szl_math_corpus.py ./szl_math_corpus.py
COPY szl_code_proxy.py ./szl_code_proxy.py

# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay): real durable lmdb persistence
# + optional sqlite-vss vector recall (szl_unay degrades to honest cosine-fallback if
# the extension cannot load in the slim image). Never affects existing routes.
RUN pip install --no-cache-dir "lmdb>=1.4.0" "sqlite-vss>=0.1.2"
# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_unay_routes and calls .register(app, ns="amaru") -> /api/amaru/v2/unay/* +
# /api/amaru/v2/khipu/lmdb/*. Real durable lmdb + real sqlite-vss honest fallback.
COPY szl_unay.py ./szl_unay.py
COPY szl_khipu_lmdb.py ./szl_khipu_lmdb.py
COPY szl_khipu_replicate.py ./szl_khipu_replicate.py
COPY szl_unay_routes.py ./szl_unay_routes.py
# ADDITIVE (Warhacker aliases, Yachay 2026-06-01): top-level /healthz + /khipu/* + /wires/D.
# Per-file COPY (no `COPY . .`) — without this `import szl_warhacker_aliases` fails.
COPY szl_warhacker_aliases.py ./szl_warhacker_aliases.py
# ADDITIVE (V4 Fleet Panel, 2026-06-02, Dev2 Inti):
# explicit per-file COPY (this Dockerfile does not use COPY . .).
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# szl_v4_fleet.py: /api/health + /api/amaru/v4/fleet[/doctrine] + /fleet + /thesis
# web/v4_fleet_panel.html: canonical fleet panel served at /fleet
COPY szl_v4_fleet.py ./szl_v4_fleet.py
COPY web/v4_fleet_panel.html ./web/v4_fleet_panel.html


# ADDITIVE (SZL Ken Agent Pattern v1, CTO Yachay Convergence Cycle 1, 2026-06-03):
# Explicit per-file COPY of szl_ken.py (this Dockerfile never uses `COPY . .`).
# serve.py tries `import szl_ken` at startup; without this COPY the import fails
# silently and /v1/agent/loop + /v1/mcp/tools return 404 instead of 200.
# ADDITIVE ONLY — zero existing routes touched. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY szl_ken.py ./szl_ken.py

# ADDITIVE (Formulas → Ecosystem echo, Opus 4.8, 2026-06-03): per-file COPY of the
# shared formulas package + endpoint shim (this Dockerfile never uses `COPY . .`).
# serve.py imports amaru_formula_endpoints which imports szl_shared_formulas.hnsw_retrieval
# — amaru OWNS retrieval, so this is REAL when FAISS is present. thesis_v22.pdf §2 + real Lean.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY szl_shared_formulas/__init__.py ./szl_shared_formulas/__init__.py
COPY szl_shared_formulas/hnsw_retrieval.py ./szl_shared_formulas/hnsw_retrieval.py
COPY amaru_formula_endpoints.py ./amaru_formula_endpoints.py

# ADDITIVE (Missing modules fix, 2026-06-04, Perplexity Computer Agent):
# The following .py files exist in the repo and are imported via try/except
# in serve.py, but were never COPY'd into the Docker image.
# Per-file COPY (this Dockerfile never uses `COPY . .`).
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
COPY operator_shell_v4.py ./operator_shell_v4.py
COPY szl_deepdive_gaps.py ./szl_deepdive_gaps.py
COPY szl_philosopher_loops.py ./szl_philosopher_loops.py
COPY szl_papers_codex.py ./szl_papers_codex.py

CMD ["python", "serve.py"]
# ============================================================================
# ELITE PARITY BLOCK (2026-06-04, Perplexity Computer Agent)
# Explicit per-file COPY of new elite parity modules + amaru package dir.
# serve.py imports: amaru_parity_elite, amaru_cortex_console, amaru package.
# ADDITIVE ONLY. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# ============================================================================
COPY amaru_parity_elite.py ./amaru_parity_elite.py
COPY amaru_cortex_console.py ./amaru_cortex_console.py
# amaru/ package — confidence.py, retrieval_eval.py, citations.py, verification.py,
# khipu_binding.py, etc. Fixes the 503 on /api/amaru/v1/confidence + /eval.
# Previously these lived only in sidecar/src/amaru/ but the sidecar install
# path resolves differently at runtime — copying the package directly is the
# correct fix (matches the `from amaru import confidence` import style).
COPY amaru/__init__.py ./amaru/__init__.py
COPY amaru/confidence.py ./amaru/confidence.py
COPY amaru/retrieval_eval.py ./amaru/retrieval_eval.py
COPY amaru/citations.py ./amaru/citations.py
COPY amaru/verification.py ./amaru/verification.py
COPY amaru/khipu_binding.py ./amaru/khipu_binding.py
COPY amaru/retrieval.py ./amaru/retrieval.py
COPY amaru/version.py ./amaru/version.py
COPY amaru/yawar_bus.py ./amaru/yawar_bus.py
COPY amaru/telemetry.py ./amaru/telemetry.py
COPY amaru/overwatch.py ./amaru/overwatch.py
COPY amaru/receipts.py ./amaru/receipts.py
COPY amaru/huklla.py ./amaru/huklla.py
COPY amaru/dinn_dsse.py ./amaru/dinn_dsse.py
# ============================================================================
# END: ELITE PARITY BLOCK
# ============================================================================
