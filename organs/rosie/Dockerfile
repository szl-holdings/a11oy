# SPDX-License-Identifier: Apache-2.0
# Rosie Operator Console — Docker runtime (mirrors a11oy winning pattern).
# HF Spaces sdk: docker runs this CMD, which executes our uvicorn __main__ block,
# serving BOTH the 11-tab Gradio UI (root) AND the mirrored /v1/* FastAPI contract
# (root + /api/rosie + /api/a11oy) on a single port. Under sdk: gradio, HF would
# auto-launch only `demo` and drop the FastAPI POST/DELETE routes — root cause of
# the 405s. Docker hands control to app.py so the full hybrid app is served.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOME=/home/user \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

# HF Spaces best-practice: run as a non-root user (uid 1000).
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# BE hardening: slowapi rate limiter (60/min/IP). pydantic+fastapi already present.
RUN pip install --no-cache-dir "slowapi>=0.1.9"


COPY --chown=user app.py rosie_v2_additions.py ./
# ADDITIVE (Doctrine v10/v11): shared agentic-RAG service (organ=all; rosie inherits everything).
COPY --chown=user szl_rag.py ./
# H-backplane (ADDITIVE, Doctrine v10/v11): lean-kernel proxy + /lean page.
COPY --chown=user lean_wire.py ./
# Anatomy substrate (ADDITIVE): portable formulas+composer + Gradio tabs module.
COPY --chown=user szl_formulas.py rosie_anatomy_tabs.py ./

USER user
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).
COPY szl_be_hardening.py ./szl_be_hardening.py

EXPOSE 7860

# Executes the uvicorn __main__ block in app.py -> serves Gradio UI + FastAPI /v1/*.
COPY --chown=user szl_brain.py szl_wire.py szl_jack.py szl_formulas.py ./
# ADDITIVE (Yachay / Provenance Hardening): Wire D + DSSE/Cosign real-signing modules.
# Explicit per-file COPY (this Dockerfile never uses `COPY . .`), else the modules
# never enter the image and szl_provenance import fails at boot.
COPY --chown=user szl_dsse.py szl_provenance.py ./
COPY --chown=user rosie_brain_tab.py rosie_dinn_tab.py rosie_moat_tabs.py rosie_upgrades_tab.py ./
COPY --chown=user thesis_corpus_171.csv ./
COPY --chown=user OUROBOROS_RUN_ALL.py run_all_json.py cursor_reinstill.json lean_wire.py ./
# ADDITIVE (Live 3D Wires / PURIQ Doctrine v12, Yachay): explicit per-file COPY.
# rosie Dockerfile never uses `COPY . .`; without these the `import szl_live_wires`
# in app.py raises ModuleNotFoundError and /live-wires 404s under the Gradio mount.
COPY --chown=user szl_live_wires.py live_wires.html live_wires_3d.js ./
# ADDITIVE (Rosie v3.0.0 Operator Console, Yachay / Perplexity Computer Agent):
# explicit per-file COPY (this Dockerfile never uses `COPY . .`). Without these
# `import rosie_v3` raises ModuleNotFoundError and every /api/rosie/v2/* 404s.
# ./data is created at runtime for the persisted sqlite chain + ECDSA signing key.
COPY --chown=user rosie_v3.py console.html .rosie_build_sha ./
# Persisted chain + signing key live under the user-owned home (uid 1000 owns
# /home/user via `useradd -m`). rosie_v3 creates ROSIE_DATA_DIR at runtime.
ENV ROSIE_DATA_DIR=/home/user/data
# ── UNAY + Khipu-LMDB v2 organs (ADDITIVE, Yachay / Perplexity Computer Agent).
# Explicit per-file COPY (this Dockerfile never uses `COPY . .`). Without these
# `import szl_unay_routes` raises ModuleNotFoundError and every /api/rosie/v2/unay
# + /api/rosie/v2/khipu/lmdb path 404s. Real sqlite-vss + real lmdb.
COPY --chown=user szl_unay.py szl_khipu_lmdb.py szl_khipu_replicate.py szl_unay_routes.py ./
# ADDITIVE (UNAY persistence proof, Yachay): committed LMDB snapshot restored at
# boot by szl_unay_routes._restore_snapshot — survives rebuilds via git object store
# (this Space has no persistent disk; the repo IS the durable layer).
COPY --chown=user _unay_snapshot/ ./_unay_snapshot/
# ADDITIVE (Warhacker aliases, Yachay 2026-06-01): /khipu/* + /api/rosie/v3/doctrine + /wires/D.
COPY --chown=user szl_warhacker_aliases.py ./szl_warhacker_aliases.py
# ADDITIVE (Understudy Parity, Yachay / Perplexity Computer Agent 2026-06-01):
# Rosie as a11oy's failover understudy — full LLM router / agentic RAG / MCP /
# PURIQ organs / 23 formulas / AYNI / WAYRA / understudy-promote under
# /api/rosie/v2/*. Explicit per-file COPY (this Dockerfile never uses `COPY . .`);
# without it `import szl_understudy` raises ModuleNotFoundError and every
# /api/rosie/v2 understudy path 404s. Imports szl_dsse/szl_brain/szl_rag/
# szl_formulas already COPYd above; honest 503 fallback if any are absent.
COPY --chown=user szl_understudy.py ./szl_understudy.py
# ADDITIVE (Sentra mesh immune filter, Yachay / Perplexity Computer Agent 2026-06-01):
# Rosie routes every command payload through Sentra's /sentra/rosie/filter before
# dispatch. Explicit per-file COPY (this Dockerfile never uses `COPY . .`); without
# it `import szl_sentra_client` raises ModuleNotFoundError and the dispatcher's
# immune hook fails open silently. httpx already in requirements.txt.
COPY --chown=user szl_sentra_client.py ./szl_sentra_client.py
# ADDITIVE (V4 Fleet Panel, 2026-06-02, Dev2 Inti):
# explicit per-file COPY (this Dockerfile never uses COPY . .).
# app.py now registers /api/health + /fleet + /thesis + /api/rosie/v4/fleet
# on _rosie_api BEFORE gr.mount_gradio_app — fixes the 404s on these routes.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user szl_v4_fleet.py ./szl_v4_fleet.py
COPY --chown=user web/v4_fleet_panel.html ./web/v4_fleet_panel.html


# ADDITIVE (5x-hammer, 2026-06-03): Lambda route fix module. Per-file COPY (never COPY . .).
COPY --chown=user szl_rosie_lambda_fix.py ./szl_rosie_lambda_fix.py

# ADDITIVE (SZL Ken Agent Pattern v1, CTO Yachay Convergence Cycle 1, 2026-06-03):
# Explicit per-file COPY of szl_ken.py (this Dockerfile never uses `COPY . .`).
# app.py / serve.py tries `import szl_ken` at startup; without this COPY the import
# fails silently and /v1/agent/loop + /v1/mcp/tools return 404 instead of 200.
# ADDITIVE ONLY — zero existing routes touched. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user szl_ken.py ./szl_ken.py

# ADDITIVE (Formulas → Ecosystem echo, Opus 4.8, 2026-06-03): per-file COPY of the
# shared formulas package + endpoint shim (this Dockerfile never uses `COPY . .`).
# app.py imports rosie_formula_endpoints which imports szl_shared_formulas.byzantine_quorum
# — without these COPYs the import fails and /api/rosie/v1/formula/* fall through.
# Echoes a11oy front-door formula: Byzantine quorum (n>=3f+1). thesis_v22.pdf §2 + real Lean.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user szl_shared_formulas/__init__.py ./szl_shared_formulas/__init__.py
COPY --chown=user szl_shared_formulas/byzantine_quorum.py ./szl_shared_formulas/byzantine_quorum.py
COPY --chown=user rosie_formula_endpoints.py ./rosie_formula_endpoints.py

# ADDITIVE (Formulas catalog #118 ship-fix, Opus 4.8, 2026-06-03): ROOT-CAUSE of the
# live /formulas 404. PR #118 wired `import szl_formula_catalog` + the Round-12 Ayni
# quorum module, but this Dockerfile never `COPY . .`'d them into the image, so the
# import raised ModuleNotFoundError (swallowed by the try/except) and GET /formulas
# + /api/rosie/v1/formula/ayni-quorum 404'd live. Per-file COPY (never `COPY . .`).
# Doctrine v11 LOCKED 749/14/163. ADDITIVE ONLY.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user szl_formula_catalog.py ./szl_formula_catalog.py
COPY --chown=user szl_shared_formulas/ayni_quorum.py ./szl_shared_formulas/ayni_quorum.py

# ADDITIVE (Closeout / Wire+UI pass, Opus 4.8, 2026-06-03): ROOT-CAUSE of the live
# /drones 404 and the dead FRONTIER block. This Dockerfile never uses `COPY . .`,
# so these modules never entered the runtime image and their `import` in app.py
# raised ModuleNotFoundError — silently swallowed by the surrounding try/except.
# With these per-file COPYs, /drones serves the visual fleet panel,
# /api/rosie/drones/{fleet,incidents} resolve, and the frontier rollup registers.
# Doctrine v11 LOCKED 749/14/163. ADDITIVE ONLY.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user rosie_drone_routes.py ./rosie_drone_routes.py
COPY --chown=user rosie_frontier_patch.py ./rosie_frontier_patch.py

# ADDITIVE (Closeout, Opus 4.8, 2026-06-03): the REAL MCP console package + premium
# operator console assets + the three real MCP client example configs. app.py serves
# web/console.html at /console/v3, imports src/rosie.{orchestrator,tool_router,
# observability,mcp_server} for the 5 organ tiles + WS MCP stream, and reads
# examples/*.json for the 'Setup MCP' copy-to-clipboard button. Without these COPYs
# the console endpoints 404 and the MCP block import fails. Per-file COPY (never
# `COPY . .`). Doctrine v11 LOCKED 749/14/163. ADDITIVE ONLY.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user src/rosie/__init__.py ./src/rosie/__init__.py
COPY --chown=user src/rosie/orchestrator.py ./src/rosie/orchestrator.py
COPY --chown=user src/rosie/tool_router.py ./src/rosie/tool_router.py
COPY --chown=user src/rosie/observability.py ./src/rosie/observability.py
COPY --chown=user src/rosie/mcp_server.py ./src/rosie/mcp_server.py
COPY --chown=user web/console.html ./web/console.html
COPY --chown=user web/console.js ./web/console.js
COPY --chown=user examples/claude-desktop-config.json ./examples/claude-desktop-config.json
COPY --chown=user examples/codex-config.json ./examples/codex-config.json
COPY --chown=user examples/continue-config.json ./examples/continue-config.json
COPY --chown=user examples/README.md ./examples/README.md

# ADDITIVE (Parity drift fix, 2026-06-04, Perplexity Computer Agent):
# szl_khipu_aggregate.py and szl_puriq_frontdoor.py exist in repo and are imported
# by app.py via try/except, but were never COPY'd into the Docker image.
# Without these COPYs: /khipu-3d falls through to Gradio (no 3D DAG) and
# /puriq/frontdoor 404s.
# Per-file COPY. Doctrine v11 LOCKED 749/14/163.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
COPY --chown=user szl_khipu_aggregate.py ./szl_khipu_aggregate.py
COPY --chown=user szl_puriq_frontdoor.py ./szl_puriq_frontdoor.py

# ADDITIVE (Rosie-as-Jarvis squad, 2026-06-04): grounded operator assistant.
# rosie_jarvis.py is imported by app.py and serves /api/rosie/v1/jarvis/* + /jarvis.
# Deps (szl_brain.py, szl_dsse.py, src/rosie/*) are already COPY'd above.
# Per-file COPY (never COPY . .). Doctrine v11 LOCKED 749/14/163 @ c7c0ba17.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
COPY --chown=user rosie_jarvis.py ./rosie_jarvis.py
COPY --chown=user web/jarvis.html ./web/jarvis.html

CMD ["python", "app.py"]
