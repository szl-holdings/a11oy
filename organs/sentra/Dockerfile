# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# sentra HF Docker Space — FULL OPERATIONAL (round2 delivery)
#
# Routes:
#   /                          — VERBATIM Replit React SPA (Vite base="/", a11oy pattern) — REPLACES old landing per founder
#   /console/                  — Replit SPA console (verbatim, standalone)
#   /api/sentra/healthz        — liveness probe
#   /api/sentra/v1/verdict     — POST: Wire B full immune verdict
#   /api/sentra/v1/inspect     — POST: Wire B full-signal inspect
#   /api/sentra/v1/gates       — GET: list all 8 immune gates
#   /api/sentra/v1/gates/{id}  — GET: per-gate detail
#   /api/sentra/v1/gates/{id}/test  — POST: per-gate test
#   /api/sentra/v1/audit-log   — GET: recent verdict history
#   /api/sentra/v1/threats     — GET: threat-signature STIX corpus
#   /api/sentra/v1/forecast    — GET/POST: witnessed forecasting (Mādhava envelope, Cursor #65)
#
# Canonical (Doctrine v11): 749 decl / 14 unique axioms (15 raw, 1 dup) / 163 tracked sorries / 12 MCP tools / 46 policy gates
#   /brain                     — immune brain page (theorems + 8 gates + 5 LLM tiers + screening)
#   /api/sentra/v1/brain*      — brain JSON + screen; /llm/route + /llm/tiers; /mesh/state; /brainz
#
# HF Space requirement: listen on PORT 7860.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    "fastapi>=0.111.0,<1.0.0" \
    "uvicorn[standard]>=0.29.0,<1.0.0" \
    "pydantic>=2.7.0,<3.0.0"
# BE hardening: slowapi rate limiter (60/min/IP). pydantic+fastapi already present.
RUN pip install --no-cache-dir "slowapi>=0.1.9"

# ADDITIVE (Yachay / Provenance Hardening): cryptography for DSSE+Cosign Khipu signing.
RUN pip install --no-cache-dir "cryptography>=42.0"

# NOTE (P0 CI fix, Dev1 Rumi): torch+faiss+sentence-transformers removed from
# build-time pip install. At ~1GB+ they cause GH Actions OOM on ubuntu-latest
# (7GB RAM). szl_rag.py already has honest try/except lazy-load fallback:
# if the import fails it returns {"status":"rag_unavailable"} with no crash.
# Install huggingface_hub only (lightweight) for HF dataset caching utilities.
RUN pip install --no-cache-dir "huggingface_hub>=0.23.0"

# Verbatim Replit React SPA at root (Vite base="/"): index.html + assets in landing/.
# Old Vessels-DNA landing replaced per founder directive; /api/sentra/* contract preserved.
COPY landing/ ./landing/

# Copy console SPA (Replit verbatim, standalone)
COPY console/ ./console/

# Copy serve orchestrator
COPY serve.py ./serve.py
# Sentra <-> Killinchu cyber bridge (ADDITIVE): /drone-cyber tab + endpoints.
COPY sentra_drone_cyber.py ./sentra_drone_cyber.py
# a11oy.code (ADDITIVE, Doctrine v11 §14): math-corpus + code-proxy for sentra.
COPY szl_math_corpus.py ./szl_math_corpus.py
COPY szl_code_proxy.py ./szl_code_proxy.py

# Anatomy substrate (ADDITIVE): canonical formulas + composer routes.
COPY szl_formulas.py ./szl_formulas.py
COPY szl_anatomy_routes.py ./szl_anatomy_routes.py

# ADDITIVE (Doctrine v11): shared per-app BRAIN + unified LLM router + mesh wires.
COPY szl_brain.py ./szl_brain.py
# ADDITIVE (Doctrine v11): shared agentic-RAG service (organ=immune).
COPY szl_rag.py ./szl_rag.py
COPY szl_wire.py ./szl_wire.py
COPY szl_dsse.py ./szl_dsse.py
COPY szl_provenance.py ./szl_provenance.py
COPY szl_jack.py ./szl_jack.py


# ADDITIVE (Yachay / Live 3D Wires, PURIQ Doctrine v12): COPY the live-wires
# module + host page + scene core so `import szl_live_wires` resolves in-container.
# Without these the register() call in the server silently fails and /live-wires
# falls through to the SPA shell. ADDITIVE ONLY. Sign: Yachay.
COPY szl_live_wires.py ./szl_live_wires.py
COPY live_wires.html ./live_wires.html
COPY live_wires_3d.js ./live_wires_3d.js

# ADDITIVE (Wire I): Rosie-companion module baked into the image. Yachay.
COPY szl_rosie_companion.py ./szl_rosie_companion.py
COPY serve.py ./serve.py
ENV PORT=7860
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).
COPY szl_be_hardening.py ./szl_be_hardening.py

EXPOSE 7860

# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay): real durable lmdb persistence
# + optional sqlite-vss vector recall (szl_unay degrades to honest cosine-fallback if
# the extension cannot load in the slim image). Never affects existing routes.
RUN pip install --no-cache-dir "lmdb>=1.4.0"
# sqlite-vss removed: no pre-built wheel for python:3.12-slim (P0 CI fix, Dev1 Rumi)
# szl_unay.py has honest fallback to cosine similarity when sqlite-vss .so cannot load
# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile does not use `COPY . .`). serve.py imports
# szl_unay_routes and calls .register(app, ns="sentra") -> /api/sentra/v2/unay/* +
# /api/sentra/v2/khipu/lmdb/*. Real durable lmdb + real sqlite-vss honest fallback.
COPY szl_unay.py ./szl_unay.py
COPY szl_khipu_lmdb.py ./szl_khipu_lmdb.py
COPY szl_khipu_replicate.py ./szl_khipu_replicate.py
COPY szl_unay_routes.py ./szl_unay_routes.py
# ADDITIVE (Warhacker aliases, Yachay 2026-06-01): top-level /healthz + /khipu/* + /wires/D.
# Per-file COPY (no `COPY . .`) — without this `import szl_warhacker_aliases` fails.
COPY szl_warhacker_aliases.py ./szl_warhacker_aliases.py
# ADDITIVE (3D scene TABS, Yachay 2026-06-02): /threat-globe + /verdict-river as
# Three.js tabs fed by live /api/sentra/v1/{audit-log,gates}. Per-file COPY (no
# `COPY . .`) — without this `import sentra_v4_threat` silently fails and the
# routes fall through to the SPA shell. ADDITIVE; does NOT replace the front or
# the /console/ 8-gate experience. Doctrine v11 LOCKED 749/14/163.
COPY sentra_v4_threat.py ./sentra_v4_threat.py
# Re-COPY serve.py last so the route registrations above are baked in.
COPY serve.py ./serve.py
# ADDITIVE (V4 Fleet Panel + operator_shell_v4 fix, 2026-06-02, Dev2 Inti):
# explicit per-file COPY (this Dockerfile does not use COPY . .).
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# operator_shell_v4.py: Unified Operator Shell v4 (was missing — caused HTML bleed-through)
# szl_v4_fleet.py: /api/health + /api/sentra/v4/fleet[/doctrine] + /fleet + /thesis
# web/v4_fleet_panel.html: canonical fleet panel
COPY operator_shell_v4.py ./operator_shell_v4.py
COPY szl_v4_fleet.py ./szl_v4_fleet.py
COPY web/v4_fleet_panel.html ./web/v4_fleet_panel.html



# ADDITIVE (feat/immune-dsse-rekor-verify, Dev1 / Yachay; Perplexity Computer Agent):
# Per-file COPY (this Dockerfile uses no `COPY . .`) for the new immune provenance
# package. serve.py does `sys.path.insert(0, "/app/src")` then
# `from sentra import dsse, rekor, in_toto`. Without these COPYs the import fails
# and the new routes 503. cryptography>=42.0 already installed above.
# Doctrine v11 LOCKED 749/14/163. HONESTY OVER CHECKLIST — no mocks.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY src/sentra/__init__.py ./src/sentra/__init__.py
COPY src/sentra/dsse.py ./src/sentra/dsse.py
COPY src/sentra/rekor.py ./src/sentra/rekor.py
COPY src/sentra/in_toto.py ./src/sentra/in_toto.py
# Re-COPY serve.py last so the new route registrations are baked in.
COPY serve.py ./serve.py

# ADDITIVE (Formulas → Ecosystem echo, Opus 4.8, 2026-06-03): per-file COPY of the
# shared formulas package + endpoint shim (this Dockerfile never uses `COPY . .`).
# serve.py imports sentra_formula_endpoints which imports szl_shared_formulas.* —
# without these COPYs the import fails and /api/sentra/v1/formula/* fall through.
# Echoes a11oy front-door formulas: PAC-Bayes + Bloom. thesis_v22.pdf §2 + real Lean.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY szl_shared_formulas/__init__.py ./szl_shared_formulas/__init__.py
COPY szl_shared_formulas/pac_bayes.py ./szl_shared_formulas/pac_bayes.py
COPY szl_shared_formulas/bloom_filter.py ./szl_shared_formulas/bloom_filter.py
COPY sentra_formula_endpoints.py ./sentra_formula_endpoints.py

# ADDITIVE (CLOSEOUT, Opus 4.8, 2026-06-03): per-file COPY of the premium Immune
# Verdict Theatre UI + the operator-shell desktop HTML (PR #117 reconciliation).
# This Dockerfile uses NO `COPY . .` — without these explicit COPYs:
#   - /verdicts (served by serve.py) 503s / 404s (verdicts.html missing), and
#   - /operator (operator_shell_v4) returns "operator.html not deployed".
# verdicts.html: live SSE verdict stream + DSSE/in-toto/SLSA receipt viewer +
#   real Rekor RFC 6962 Merkle-proof recompute + Immune Cathedral nav (Inca palette).
# operator.html: the Immune Cathedral desktop shell (operator-shell v4, 7 endpoints).
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY web/verdicts.html ./web/verdicts.html
COPY web/operator.html ./web/operator.html
# ADDITIVE (Parity drift fix, 2026-06-04, Perplexity Computer Agent):
# sentra_parity.py exists in the repo and is imported by serve.py at startup
# (try: import sentra_parity as _sentra_parity; _sentra_parity.register(app, ns="sentra"))
# but was NEVER COPY'd into the Docker image. Without this COPY the import fails
# silently and /api/sentra/v1/{anomaly,policy/test,threats/full,policy/corpus}
# fall through to the SPA shell (returning HTML instead of JSON).
# Per-file COPY (this Dockerfile never uses `COPY . .`). Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY sentra_parity.py ./sentra_parity.py

# ADDITIVE (Missing modules drift fix, 2026-06-04, Perplexity Computer Agent):
# szl_ken.py and sentra_frontier_patch.py exist in repo and are imported by
# serve.py via try/except, but were never COPY'd. Without these COPYs the imports
# fail silently and their associated routes 404.
# Per-file COPY. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
COPY szl_ken.py ./szl_ken.py
COPY sentra_frontier_patch.py ./sentra_frontier_patch.py

# ADDITIVE (Elite 13-tab build, 2026-06-04, Perplexity Computer Agent):
# sentra_elite.py adds 12 new real endpoints (verdict/feed, elite/*, puriq/formulas*,
# anatomy, slsa/verify, llm/hub, llm/route/elite) + F1–F23 formula surface +
# 5-tier LLM hub (a11oy parity). Also re-copies console/index.html (new 13-tab UI).
# Per-file COPY (no `COPY . .`). Doctrine v11 LOCKED 749/14/163. SLSA L1 honest (L2 roadmap). No mocks.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY sentra_elite.py ./sentra_elite.py
COPY console/ ./console/

# Re-COPY serve.py last so all elite route registrations are baked in.
COPY serve.py ./serve.py

CMD ["python", "serve.py"]
