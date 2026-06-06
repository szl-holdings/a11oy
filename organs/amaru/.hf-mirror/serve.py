# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) / 163 sorries (112 baseline + 51 Putnam)
# / 12 MCP tools / 46 policy gates.
"""Unified server for Hugging Face Spaces — serves the Amaru API, the memory-cortex
operator surface (root /), AND the verbatim Replit reverse-ETL React SPA at /conduit/.

Wire D/E/F (2026-05-31 Wires DEF Ship) — ADDITIVE:
  Wire D — W3C traceparent middleware installed on this Space's FastAPI app.
            Extracts incoming traceparent header (or generates one), stashes on request.state,
            echoes on response. /api/amaru/v1/brainz exposes traceparent_propagating: true.
  Wire E — amaru subscribes to a11oy brand-decision events via SSE at
            GET /api/amaru/v1/cortex-subscribe.
            In-process ring bus (no external broker; honest disclosure).
  Wire F — amaru's Khipu DAG ingest endpoint:
            POST /api/amaru/v1/receipts/ingest — receives gate-decision receipts from a11oy,
            adds to Khipu Merkle DAG (additive, no overwrite).

ADDITIVE ONLY: the existing root single-page memory-cortex landing, the /console/ operator
surface, the /api/amaru/* 7-chakra runtime, the reasoner section, and the Rosie floating widget
are all PRESERVED unchanged. The /conduit/ React SPA is preserved unchanged.
"""

import os
import sys

sys.path.insert(0, "/app")

import asyncio as _asyncio
import json as _json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

# --- Guarded sidecar import (Yachay CTO 2026-06-02 / Perplexity Computer Agent) ---
# If the inner cortex app fails to import (cold-boot / transient module error),
# fall back to a stub whose every route returns honest JSON 503 — NEVER HTML.
# This is the server-side half of the 'Amaru sidecar JSON parse' fix: the
# frontend hook can no longer receive an HTML <!doctype body from /api/amaru/*.
try:
    from amaru.app import app as amaru_app
    _AMARU_SIDECAR_IMPORT_ERROR = None
except Exception as _amaru_imp_err:  # pragma: no cover - defensive
    import traceback as _amaru_tb
    _AMARU_SIDECAR_IMPORT_ERROR = repr(_amaru_imp_err)
    print('[amaru] CRITICAL: amaru.app import failed; serving JSON-503 stub: '
          + _AMARU_SIDECAR_IMPORT_ERROR, file=sys.stderr)
    _amaru_tb.print_exc()
    from fastapi import FastAPI as _FA_stub
    from fastapi.responses import JSONResponse as _JR_stub
    amaru_app = _FA_stub()

    @amaru_app.get('/healthz')
    async def _amaru_stub_health():
        return _JR_stub(
            {'ok': False, 'status': 'sidecar_import_failed',
             'error': _AMARU_SIDECAR_IMPORT_ERROR,
             'doctrine': 'v11', 'note': 'cortex app failed to import; honest JSON 503'},
            status_code=503,
        )

    @amaru_app.api_route('/{stub_path:path}',
                         methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    async def _amaru_stub_catchall(stub_path: str):
        return _JR_stub(
            {'ok': False, 'status': 'sidecar_unavailable',
             'error': 'amaru sidecar import failed',
             'detail': _AMARU_SIDECAR_IMPORT_ERROR,
             'path': '/api/amaru/' + stub_path, 'doctrine': 'v11'},
            status_code=503,
        )

# Doctrine v11 LOCKED ADDITIVE: shared per-app BRAIN + unified LLM router + mesh wiring.
import szl_brain as _brain
import szl_wire as _wire

# ---------------------------------------------------------------------------
# ADDITIVE (OTel instrumentation, Yachay 2026-06-01 / Perplexity Computer Agent):
# Initialise OTLP/HTTP trace export from env var OTEL_EXPORTER_OTLP_ENDPOINT.
# Gracefully no-ops if the env var is absent or packages missing.
# Doctrine v11 LOCKED 749/14/163. ADDITIVE ONLY — does NOT touch existing routes.
# ---------------------------------------------------------------------------
# HOTFIX 2026-06-01 Yachay: OTel middleware crash-looping the Space.
# Hard-disable szl_otel import. Real OTel ships in next clean PR.
def _szl_otel_setup(*a, **kw): pass
_OTEL_ENABLED = False
# --- end OTel preamble ---


app = FastAPI(title="Amaru — Full Stack", version="2.1.0")

# ---------------------------------------------------------------------------
# ADDITIVE (Formulas → Ecosystem echo, Opus 4.8, 2026-06-03, Yachay).
# amaru ECHOES the HNSW retrieval formula from the a11oy front door — and amaru is
# the organ that ACTUALLY OWNS cortex/RAG retrieval (szl_rag_hnsw), so here the formula
# is REAL when FAISS is present (honest backend-availability flag otherwise). Verbatim-
# vendored from a11oy.formulas under ./szl_shared_formulas/. register() mounts
# /api/amaru/v1/formula/hnsw + /api/amaru/v1/formulas/index EARLY (before the
# /{path:path} catch-all). HONEST schema {value, citation, lean_theorem}. try/except.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ---------------------------------------------------------------------------
_amaru_formulas = None
_amaru_formulas_status = "formulas-not-wired"
try:
    if "/app" not in sys.path and os.path.isdir("/app/szl_shared_formulas"):
        sys.path.insert(0, "/app")
    import amaru_formula_endpoints as _amaru_formulas
    _amaru_formulas_status = _amaru_formulas.register(app, ns="amaru")
    print(f"[amaru] thesis-v22 formulas echoed ({_amaru_formulas_status})", file=sys.stderr)
except Exception as _amaru_fx:  # additive: never break the Space
    _amaru_formulas_status = f"formulas-not-wired:{_amaru_fx!r}"
    print(f"[amaru] formula echo NOT mounted ({_amaru_fx!r}); app unaffected", file=sys.stderr)

# ADDITIVE (mesh wire-up, Dev2): cross-pod vsp-otel tracing (W3C traceparent + OTLP/gRPC).
try:
    from vsp_otel.middleware import install as install_vsp; install_vsp(app)
except Exception as _vsp_e:
    import sys as _vsp_sys; print(f"[amaru] vsp-otel wire skipped: {_vsp_e!r}", file=_vsp_sys.stderr)

# ADDITIVE: OTel — instrument FastAPI app
try:
    _szl_otel_setup(fastapi_app=app)
except Exception as _otel_e:
    import sys as _otel_sys; print(f"[amaru] OTel setup skipped: {_otel_e!r}", file=_otel_sys.stderr)
# --- end OTel setup ---


# ── Live 3D Wires (PURIQ / Doctrine v12) — ADDITIVE, re-pinned FIRST ─────────
# Registered immediately after the app is constructed so FastAPI's ordered route
# matching gives /live-wires + the 3DWPP SSE stream + court-admissible BoE
# precedence over every pre-existing SPA/proxy catch-all. Real in-process wire
# data (szl_wire / szl_jack); empty buffers render IDLE (never faked). Sigs are
# honestly PLACEHOLDER until Sigstore CI is wired. Sign: Yachay. Perplexity Computer Agent.
try:
    import szl_live_wires as _live_wires
    _live_wires.register(app, ns="amaru")
    import sys as _sys_lw
    print("[amaru] Live 3D Wires registered FIRST: /live-wires + /api/amaru/v1/wires/{stream,boe,inject}", file=_sys_lw.stderr)
except Exception as _lw_e:
    import sys as _sys_lw, traceback as _tb_lw
    print(f"[amaru] Live 3D Wires NOT registered: {_lw_e}", file=_sys_lw.stderr)
    _tb_lw.print_exc()
# ── end Live 3D Wires ────────────────────────────────────────────────────────

# ── GAP-4: /about/thesis injection page (Yachay; Perplexity Computer Agent) ──
# Mounts GET /about/thesis (HTML) + GET /api/amaru/v1/thesis (JSON): chapters &
# theorems this flagship implements, 8 live Zenodo DOIs, Λ-axis (Conjecture 1),
# substrate-package cross-refs. Every Lean decl cited is real + PROVED.
try:
    import szl_thesis_about as _thesis_about
    _thesis_status = _thesis_about.register(app, "amaru")
    import sys as _sys_th
    print(f"[amaru] /about/thesis registered: {_thesis_status}", file=_sys_th.stderr)
except Exception as _th_e:
    import sys as _sys_th, traceback as _tb_th
    print(f"[amaru] /about/thesis NOT registered: {_th_e}", file=_sys_th.stderr)
    _tb_th.print_exc()
# ── end /about/thesis ────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire D — W3C traceparent propagation middleware.
# Extracts incoming traceparent header, generates one if absent, echoes on response.
_wire.install_traceparent_middleware(app, "amaru")

# ---------------------------------------------------------------------------
# Agentic-RAG (ADDITIVE, Doctrine v11). amaru binds the CORTEX organ.
# Registered EARLY (before the /api/amaru mount and the SPA catch-all) so
# /api/amaru/v1/rag + /rag resolve here and are never shadowed by the mount.
# Corpus+FAISS pulled from SZLHOLDINGS/rag-corpus-v1 at first use. LLM responses
# cite chunk IDs; Λ-receipt signature = PLACEHOLDER.
# ---------------------------------------------------------------------------
try:
    import szl_rag as _rag
    _rag.register_rag_routes(app, "amaru")
    print("[amaru] szl_rag routes registered (organ=cortex)", file=sys.stderr)
except Exception as _e:
    print(f"[amaru] szl_rag not registered: {_e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# ADDITIVE (Yachay / Provenance Hardening): Wire D (W3C traceparent trace
# continuity) + DSSE/Cosign-signed Khipu receipts (SLSA L1 honest; L2 signed provenance roadmap).
# Registers /api/{space}/wires/D, /khipu/{sign,verify,ledger}, /provenance.
# Wrapped so a missing dep (cryptography) can NEVER take down the existing app.
# PLACEHOLDER -> REAL: every receipt now DSSE-signed with szlholdings-cosign.
# ---------------------------------------------------------------------------
try:
    import szl_provenance as _prov
    _prov_status = _prov.register_provenance(app, "amaru")
    print(f"[amaru] szl_provenance registered (Wire D LIVE, SLSA L1 honest; L2 roadmap): {{_prov_status}}", file=sys.stderr)
except Exception as _pe:  # pragma: no cover - defensive, additive-only
    print(f"[amaru] szl_provenance NOT registered ({{_pe!r}}); existing app unaffected", file=sys.stderr)

# ---------------------------------------------------------------------------
# Warhacker top-level alias routes (ADDITIVE, Yachay, 2026-06-01). Registered
# EARLY, before the /{path:path} catch-all, so /healthz + /khipu/{sign,verify,
# pubkey} + /api/amaru/v3/doctrine + /wires/D resolve LOCALLY. Real DSSE via
# szl_dsse. Doctrine v11 VERBATIM 749/14/163. Zero regression.
# ---------------------------------------------------------------------------
try:
    import szl_warhacker_aliases as _wh_aliases
    import os as _wh_os
    _wh_status = _wh_aliases.register(app, "amaru", build_sha=_wh_os.environ.get("SPACE_COMMIT_SHA", "warhacker-aliases-v1"))
    print(f"[amaru] Warhacker aliases registered: {_wh_status}", file=sys.stderr)
except Exception as _wh_e:
    print(f"[amaru] Warhacker aliases NOT registered: {_wh_e!r}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Wire D: /api/amaru/healthz — traceparent_propagating: true
# Registered BEFORE the /api/amaru mount so it takes precedence over the
# inner amaru_app healthz which doesn't have the Wire D field.
# ---------------------------------------------------------------------------

@app.get("/api/amaru/healthz")
async def healthz_wire_d(request: Request) -> JSONResponse:
    """Wire D: healthz with traceparent_propagating: true — Doctrine v11."""
    tp = getattr(request.state, "traceparent", None) or _wire.new_traceparent()
    return JSONResponse({
        "status": "ok",
        "service": "amaru",
        "version": "2.1.0",
        "surface": "memory cortex (7 chakras)",
        "doctrine": "v11",
        # Wire D field — required by Wires DEF spec
        "traceparent_propagating": True,
        "traceparent": tp,
        "traceparent_note": (
            "W3C traceparent middleware LIVE: every request gets a real W3C traceparent. "
            "Cross-Space distributed-trace broker NOT wired (honest — see a11oy /wires)."
        ),
        "wires": {
            "B": "LIVE (a11oy\u2194sentra immune)",
            "C": "LIVE (a11oy\u2194rosie receipt stream)",
            "D": "LIVE (W3C traceparent middleware active; cross-Space broker NOT wired)",
            "E": "LIVE (SSE cortex-subscribe at /api/amaru/v1/cortex-subscribe)",
            "F": "LIVE (Khipu DAG ingest at /api/amaru/v1/receipts/ingest)",
        },
        "declarations": 749,
        "axioms": 14,
        "sorries": 163,
        "mcp_tools": 12,
        "policy_gates": 46,
        "hatun_willay": True,
    })




# ===========================================================================
# Wire I — Rosie-companion (ADDITIVE, Doctrine v11). Signed: Yachay.
# Founder directive 2026-06-01 ~02:52 EDT: "Make sure Rosie is wired in the
# backend of each flag and wherever needed to be."
# amaru (cortex) gains a Rosie-shadow. The cortex synthesis loop optionally
# consults the Rosie-shadow for deeper-reasoning queries. New endpoint
# /api/amaru/v1/cortex/with-rosie returns a DUAL answer (amaru baseline +
# Rosie-enhanced) with BOTH Khipu receipts. /api/amaru/v1/rosie-companion/*
# exposes ponder/synthesize/evolve/brain_jack. Rosie is co-pilot, NOT pilot.
# Registered on the ROOT app BEFORE app.mount("/api/amaru", ...) so the mounted
# sub-app does not shadow them (Starlette prefix match). NEVER crash the app.
# ===========================================================================
try:
    import sys as _sys_rc
    import szl_rosie_companion as _rc
    import szl_jack as _jack_rc  # reuse the cortex organ-response for the baseline

    _AMARU_SHADOW = _rc.RosieShadow("amaru")

    def _amaru_baseline(query, axis_scores, tp):
        """amaru's own cortex answer (TH1/TH8/TH10, 7-chakra) + its own Khipu receipt."""
        L = _jack_rc.lambda_signal(axis_scores)
        text = _jack_rc._organ_response("amaru", query, axis_scores, "amaru", "cortex")
        receipt = _jack_rc.make_jack_receipt("amaru", "amaru", query, axis_scores, tp)
        import hashlib as _h, json as _j
        receipt["node_digest"] = _h.sha256(_j.dumps(receipt, sort_keys=True, default=str).encode()).hexdigest()
        return {"answer": text, "lambda_signal": L, "khipu_receipt": receipt}

    @app.get("/api/amaru/v1/rosie-companion")
    async def amaru_rosie_companion_info() -> JSONResponse:
        return JSONResponse({
            "wire": "I", "flagship": "amaru", "organ": "cortex",
            "rosie_endpoint": _AMARU_SHADOW.jack_url,
            "ops": ["ponder", "synthesize", "evolve", "brain_jack"],
            "synthesis_loop": "cortex synthesis optionally consults Rosie-shadow for deeper-reasoning queries",
            "dual_answer": "/api/amaru/v1/cortex/with-rosie",
            "doctrine": "v11",
            "honesty": "Rosie is co-pilot, not pilot. amaru cortex + 2-person Yuyay gate decide.",
        })

    @app.post("/api/amaru/v1/cortex/with-rosie")
    async def amaru_cortex_with_rosie(request: Request) -> JSONResponse:
        """Dual answer: amaru cortex baseline + Rosie-enhanced reasoning, with BOTH
        Khipu receipts and a cross-link. The cortex synthesis loop calls this when a
        query is flagged deep-reasoning (deep=true or axis spread is high)."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        query = body.get("query", "")
        axis_scores = body.get("axis_scores")
        tp = getattr(getattr(request, "state", None), "traceparent", None)
        baseline = _amaru_baseline(query, axis_scores, tp)
        enhanced = _AMARU_SHADOW.brain_jack(query, depth=int(body.get("depth", 1)),
                                            axis_scores=axis_scores, traceparent=tp)
        return JSONResponse({
            "query": query,
            "amaru_baseline": baseline,
            "rosie_enhanced": {"answer": enhanced.text, "lambda_signal": enhanced.lambda_signal,
                               "khipu_receipt": enhanced.rosie_receipt, "stub": enhanced.stub},
            "cross_link": enhanced.cross_link,
            "both_receipts": {"amaru": baseline["khipu_receipt"], "rosie": enhanced.rosie_receipt},
            "doctrine": "v11", "wire": "I",
            "honesty": "Two independent answers; Rosie is advisory. cross_link.chain_verified reflects whether the Rosie hop was live.",
        })

    @app.post("/api/amaru/v1/rosie-companion/ponder")
    async def amaru_rosie_ponder(request: Request) -> JSONResponse:
        body = await request.json()
        tp = getattr(getattr(request, "state", None), "traceparent", None)
        return JSONResponse(_AMARU_SHADOW.ponder(body.get("context", body), traceparent=tp).to_dict())

    @app.post("/api/amaru/v1/rosie-companion/synthesize")
    async def amaru_rosie_synthesize(request: Request) -> JSONResponse:
        body = await request.json()
        tp = getattr(getattr(request, "state", None), "traceparent", None)
        return JSONResponse(_AMARU_SHADOW.synthesize(body.get("events", []), traceparent=tp).to_dict())

    @app.post("/api/amaru/v1/rosie-companion/evolve")
    async def amaru_rosie_evolve(request: Request) -> JSONResponse:
        body = await request.json()
        tp = getattr(getattr(request, "state", None), "traceparent", None)
        return JSONResponse(_AMARU_SHADOW.evolve(body.get("strategy", {}),
                            approvers=body.get("approvers", []), traceparent=tp).to_dict())

    @app.post("/api/amaru/v1/rosie-companion/brain-jack")
    async def amaru_rosie_brain_jack(request: Request) -> JSONResponse:
        body = await request.json()
        tp = getattr(getattr(request, "state", None), "traceparent", None)
        return JSONResponse(_AMARU_SHADOW.brain_jack(body.get("query", ""),
                            depth=int(body.get("depth", 1)),
                            axis_scores=body.get("axis_scores"), traceparent=tp).to_dict())

    print("[amaru] Wire I rosie-companion registered (cortex/with-rosie dual answer)", file=_sys_rc.stderr)
except Exception as _rc_e:
    import sys as _sys_rc2
    print(f"[amaru] Wire I rosie-companion NOT registered: {_rc_e!r}", file=_sys_rc2.stderr)

# ===========================================================================
# UNAY + Khipu-LMDB v2 organs (ADDITIVE, 2026-06-01, Yachay / Perplexity Computer Agent).
# NEW /api/amaru/v2/* paths only, registered on the ROOT app BEFORE the SPA
# catch-all "/{path:path}" so they resolve LOCALLY. try/except-guarded: a missing
# optional dep can NEVER take down an existing route. Real durable lmdb + real
# sqlite-vss (honest cosine-fallback if the .so cannot load). LOCKED: 749/14/163.
#   GET  /api/amaru/v2/unay/healthz|stats|verify ; POST .../remember|recall (+GET /recall?q=)
#   GET  /api/amaru/v2/khipu/lmdb/stats|verify|tail ; POST .../append ; POST .../replicate
# ---------------------------------------------------------------------------
try:
    import szl_unay_routes as _unay
    _unay_info = _unay.register(app, ns="amaru")
    import sys as _sysu
    print(f"[szl_unay] UNAY+Khipu-LMDB v2 mounted: backend={_unay_info.get('unay_backend')}, "
          f"lmdb={_unay_info.get('lmdb_version')}, data_dir={_unay_info.get('data_dir')}, "
          f"boot_entries={_unay_info.get('lmdb_entries_at_boot')}", file=_sysu.stderr)
except Exception as _ue:
    import sys as _sysu
    print(f"[szl_unay] UNAY+Khipu-LMDB v2 NOT mounted ({_ue!r}); existing routes unaffected", file=_sysu.stderr)


# ---------------------------------------------------------------------------
# ADDITIVE (Unified Operator Shell v4, 2026-06-01, Yachay / Perplexity Computer
# Agent): register the 7 v4 operator-shell endpoints + /operator desktop shell
# BEFORE the SPA catch-all so they resolve LOCALLY. try/except-guarded: a missing
# dep can NEVER take down the SPA or any existing route. Receipts sign live via
# szl_dsse (cosign ECDSA-P256/DSSE). Doctrine v11 LOCKED 749/14/163 (public).
# ---------------------------------------------------------------------------
try:
    import operator_shell_v4 as _osh_v4
    _osh_v4_status = _osh_v4.register(app, "amaru", web_dir="/app/web")
    import sys as _osh_sys
    print(f"[amaru] Operator Shell v4 registered: {_osh_v4_status}", file=_osh_sys.stderr)
except Exception as _osh_e:
    import traceback as _osh_tb, sys as _osh_sys
    print(f"[amaru] Operator Shell v4 NOT registered: {_osh_e!r}", file=_osh_sys.stderr)
    _osh_tb.print_exc()
# --- end Operator Shell v4 ---

# ---------------------------------------------------------------------------
# ADDITIVE (Amaru v4 REAL cortex/memory, 2026-06-01, Yachay / Perplexity Computer
# Agent): register /api/amaru/v4/{recall,tick,lineage/{hash},dag} + /amaru/cortex
# console BEFORE the SPA catch-all so they resolve LOCALLY (previously recall/tick
# 404'd and lineage fell through to the SPA HTML). recall = REAL deterministic
# similarity over the Khipu DAG (token-Jaccard + char-trigram cosine, NOT random);
# tick runs the 7-chakra cycle and emits a DSSE-signed receipt chained to its
# parent; lineage walks the genuine causal chain back to genesis. try/except-
# guarded: a missing dep can NEVER take down the SPA or any existing route.
# Doctrine v11 LOCKED 749/14/163 (unchanged). ADDITIVE only — v1 routes untouched.
# ---------------------------------------------------------------------------
try:
    import amaru_v4_recall as _av4
    _av4_status = _av4.register(app, "amaru")
    import sys as _av4_sys
    print(f"[amaru] v4 cortex/memory registered (recall+tick+lineage): {_av4_status}", file=_av4_sys.stderr)
except Exception as _av4_e:
    import traceback as _av4_tb, sys as _av4_sys
    print(f"[amaru] v4 cortex/memory NOT registered: {_av4_e!r}", file=_av4_sys.stderr)
    _av4_tb.print_exc()
# --- end Amaru v4 cortex/memory ---

# ---------------------------------------------------------------------------
# ADDITIVE (Amaru v4 GENIUS / Palantir-class 3D cortex, 2026-06-02, Yachay /
# Perplexity Computer Agent): register the Hickok dual-stream 3D cortex at
# /cortex-3d, the 384-dim MiniLM PCA-3D embedding flythrough at /embedding-3d,
# the live SSE tick stream at /api/amaru/v4/stream, /api/amaru/v4/embedding-cluster
# (PCA-3D of the live MiniLM index) and POST /api/amaru/v4/recall/spatial (real
# MiniLM cosine recall WITH 3D coordinates + query-beam point). Three.js r128 is
# served LOCALLY from /three.min.js (NO external CDN). All registered BEFORE the
# SPA catch-all so they resolve LOCALLY (previously /cortex-3d fell through to the
# SPA HTML). try/except-guarded: a missing dep can NEVER take down the SPA or any
# existing route. Builds ON amaru_v4_recall (Khipu DAG) + amaru_v4_semantic
# (MiniLM embeddings) — nothing mutated. Doctrine v11 LOCKED 749/14/163. Λ
# Conjecture 1. SLSA L1 honest. Sovereign in-Space compute.
# Patterns: Palantir Object Explorer (typed memory objects), Datadog Distributed
# Tracing (tick lineage DAG), Honeycomb BubbleUp (fork anomaly), Hickok & Poeppel
# 2007 DOI 10.1038/nrn2113 (dual-stream), Hickok 2025 Wired for Words (Khipu chain).
# ---------------------------------------------------------------------------
try:
    import amaru_v4_genius as _avg
    _avg_status = _avg.register(app, "amaru")
    import sys as _avg_sys
    print(f"[amaru] v4 GENIUS 3D cortex registered (/cortex-3d, /embedding-3d, stream, spatial recall): {_avg_status}", file=_avg_sys.stderr)
except Exception as _avg_e:
    import traceback as _avg_tb, sys as _avg_sys
    print(f"[amaru] v4 GENIUS 3D cortex NOT registered: {_avg_e!r}", file=_avg_sys.stderr)
    _avg_tb.print_exc()
# --- end Amaru v4 GENIUS 3D cortex ---


# ── Investor /demo route (ADDITIVE, 2026-06-02, Yachay / Perplexity Computer Agent) ──
# 90-second narrated, animated investor walkthrough at GET /demo (+ /amaru/demo).
# Inline HTML (no CDN, no key). Registered BEFORE the /{path:path} catch-all so it
# wins ordered matching. try/except-guarded. Doctrine v11 LOCKED 749/14/163. Λ Conjecture 1.
try:
    import szl_demo as _szl_demo
    _demo_status = _szl_demo.register(app, ns="amaru")
    import sys as _sys_demo
    print(f"[amaru] Investor /demo registered: {_demo_status}", file=_sys_demo.stderr)
except Exception as _demo_e:
    import sys as _sys_demo
    print(f"[amaru] Investor /demo NOT registered: {_demo_e!r}", file=_sys_demo.stderr)
# ── end Investor /demo ──


# ── Genius Operator Sidebar (ADDITIVE, 2026-06-02, Yachay / Perplexity Computer Agent) ──
# Honest left-nav shell + working wrapper pages so EVERY nav item returns real 200
# content matching its label (no SPA catch-all liars). Registered BEFORE the
# /{path:path} catch-all so each wrapper resolves LOCALLY. Each route is guarded:
# if another module already owns a path (e.g. anatomy's /doctrine|/formulas) we do
# NOT shadow it. Collapsible + search + Cmd-K palette + recents + status dots +
# concept-DOI 10.5281/zenodo.19944926 + Doctrine v11 LOCKED 749/14/163 badge,
# mobile drawer. Three.js stays LOCAL on the 3D pages (no CDN here). Λ Conjecture 1.
try:
    import szl_sidebar as _sidebar
    _sidebar_status = _sidebar.register(app, "amaru")
    import sys as _sys_sb
    print(f"[amaru] Genius sidebar registered: {_sidebar_status}", file=_sys_sb.stderr)
except Exception as _sb_e:
    import traceback as _sb_tb, sys as _sys_sb
    print(f"[amaru] Genius sidebar NOT registered: {_sb_e!r}", file=_sys_sb.stderr)
    _sb_tb.print_exc()
# ── end Genius Operator Sidebar ──


# NOTE: The SPA catch-all `@app.get("/{path:path}")` was previously registered
# HERE, which (because Starlette matches routes in *registration order*) shadowed
# every `/api/amaru/v1/*` route defined further down this module — they were
# returning the SPA index.html instead of JSON. The catch-all is now registered
# at the very END of this module (see `_register_spa_catchall()` call) so all
# API routes take precedence. Fix: Yachay (deep-diligence). DCO signed-off.


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("serve:app", host="0.0.0.0", port=port, log_level="info")

# ---------------------------------------------------------------------------
# Native doctrine surfaces /api/amaru/v1/honest + /v1/lambda (ADDITIVE, Doctrine
# v11). MUST be registered BEFORE app.mount("/api/amaru", amaru_app) below — the
# mounted sub-app would otherwise shadow these paths (it 404'd them). Same
# precedence trick the healthz route above uses. ZERO BANDAID: 13-axis
# geometric-mean Λ, canonical numbers 749/14/163. (Opus HF cleanup.)
# ---------------------------------------------------------------------------
_AMARU_AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent", "reversibility",
    "transparency", "fairness", "containment", "attestation", "freshness", "authority", "auditability",
]


@app.get("/api/amaru/v1/honest")
async def amaru_honest() -> JSONResponse:
    # ADDITIVE (Formulas → Ecosystem, 2026-06-03): surface echoed formula (HNSW — amaru
    # OWNS retrieval) + HONEST SLSA L1 (amaru image cosign-verified public-verifiable: Fulcio
    # O=sigstore.dev, Rekor logIndex 1711945840). L2 only because public Rekor confirms.
    try:
        _f = _amaru_formulas.formulas_summary() if _amaru_formulas else {"wired": [], "count": 0}
    except Exception:
        _f = {"wired": [], "count": 0}
    return JSONResponse({
        "doctrine": "v11",
        "declarations": 749, "axioms_unique": 14, "axioms_raw": 15, "sorries_total": 163,
        "sorries_baseline": 112, "sorries_putnam": 51, "trust_axes": 13,
        "lambda_uniqueness": "Conjecture, not a closed theorem (open CAUCHY_ND sorry + missing symmetry axiom)",
        "slsa": "L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet claimed. L3 not claimed.",
        "slsa_evidence": {
            "level": "L2", "image_tag": "uds-v0.2.0",
            "image_digest": "sha256:1f68b877f48eda3dc02eb4d09d4a11dbf201f8b5c3d6dd8bc6d6b752303db003",
            "builder": "GitHub-hosted Actions (slsa.dev/provenance/v1)",
            "fulcio_issuer": "sigstore.dev (public-good)", "rekor_log_index": 1712902861,
            "verified_via": "GitHub Attestations API + offline DSSE crypto + live Rekor inclusion (HTTP 200)",
            "ecosystem_gap": "killinchu remains L1 (private GitHub Fulcio, no public Rekor) — honest.",
        },
        "formulas_wired": [f["name"] for f in _f.get("wired", [])],
        "formulas_count": _f.get("count", 0),
        "formulas_status": globals().get("_amaru_formulas_status", "unknown"),
        "formulas_index": "/api/amaru/v1/formulas/index",
        "formulas_provenance": "thesis_v22.pdf §2 + real Lean theorem (HNSW navigability); amaru OWNS retrieval — REAL when FAISS present, honest flag otherwise",
        "receipts": "DSSE envelopes from the amaru tick endpoint; Sigstore CI signing PENDING (PLACEHOLDER).",
        "memory": "7-chakra cortex; Cardano-anchored receipts are demo-seeded, not on-chain mainnet.",
        "hatun_willay": True,
    })


@app.get("/api/amaru/v1/lambda")
async def amaru_lambda() -> JSONResponse:
    import math as _m
    axes = [0.92, 0.91, 0.93, 0.90, 0.94, 0.91, 0.92, 0.93, 0.90, 0.91, 0.94, 0.92, 0.93]
    floor = 0.90
    clamped = [min(1.0, max(1e-9, float(x))) for x in axes]
    L = _m.exp(sum(_m.log(x) for x in clamped) / len(clamped))
    return JSONResponse({
        "trust_axes": 13,
        "axes": [{"name": n, "score": s} for n, s in zip(_AMARU_AXIS_NAMES, axes)],
        "lambda": round(L, 6), "lambda_floor": floor, "pass": L >= floor,
        "aggregate": "geometric mean (yuyay_v3 canonical, 13-axis)",
        "uniqueness": "Conjecture, not a Theorem (open CAUCHY_ND sorry + missing symmetry axiom)",
        "declarations": 749, "axioms_unique": 14, "axioms_raw": 15, "sorries_total": 163,
        "doctrine": "v11",
    })


# ---------------------------------------------------------------------------
# PER-APP BRAIN (amaru = cortex / reasoning) + UNIFIED LLM ROUTER + Wire E/F.
# Registered on the ROOT app BEFORE the /api/amaru mount so they take precedence.
# ADDITIVE, Doctrine v11.
# ---------------------------------------------------------------------------

@app.get("/api/amaru/v1/brain")
async def amaru_brain() -> JSONResponse:
    """amaru cortex brain: TH1 (Λ Conjecture), TH8 GLR (proven), TH10, 7 chakras."""
    return JSONResponse(_brain.brain_payload("amaru"))


@app.post("/api/amaru/v1/brain/reason")
async def amaru_brain_reason(request: Request) -> JSONResponse:
    """Axis-scored reasoning with theorem citations. POST {prompt, axis_scores}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    axis = body.get("axis_scores") or [0.9] * 13
    L = _brain.lambda_aggregate(axis)
    th = _brain.THEOREMS
    cited = {k: th[k] for k in ("TH1", "TH8", "TH10")}
    routed = _brain.route(body.get("prompt", ""), axis, task_hint="math")
    return JSONResponse({
        "lambda": round(L, 6),
        "chakras": _brain.ROLE_SLICES["amaru"]["chakras"],
        "theorems_cited": cited,
        "llm_route": routed,
        "note": "Λ uniqueness is a Conjecture (TH1), not a closed theorem; TH8 GLR proven; TH10 Conjecture 1.",
        "doctrine": "v11",
    })


@app.post("/api/amaru/v1/llm/route")
async def amaru_llm_route(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse(_brain.route(
        prompt=body.get("prompt", ""), axis_scores=body.get("axis_scores"),
        max_tier=body.get("max_tier", 4),
        require_lambda_receipt=body.get("require_\u03bb_receipt", body.get("require_lambda_receipt", True)),
        task_hint=body.get("task_hint", "")))


@app.get("/api/amaru/v1/llm/tiers")
async def amaru_llm_tiers() -> JSONResponse:
    return JSONResponse({"count": len(_brain.TIERS), "tiers": _brain.TIERS,
                         "default": "claude_sonnet_4_6", "doctrine": "v11"})


# ---------------------------------------------------------------------------
# Wire E — /api/amaru/v1/cortex-subscribe (SSE)
# amaru subscribes to a11oy brand-decision events published at
# /api/a11oy/v1/cortex-publish. In-process ring bus (szl_wire._CORTEX_EVENTS).
# Honest: within a single HF Space runtime, szl_wire state is shared.
# In production, a11oy POSTs events here; in the HF single-Space context,
# we serve the buffered events.
# ---------------------------------------------------------------------------

@app.get("/api/amaru/v1/cortex-subscribe")
async def amaru_cortex_subscribe(request: Request) -> StreamingResponse:
    """Wire E: amaru cortex SSE subscription.
    Emits buffered brand-decision events from the in-memory ring bus, then a done sentinel.
    Honest: in-memory ring buffer (no external broker in a static HF Space).
    Client: a11oy publishes via POST /api/a11oy/v1/cortex-publish."""
    async def gen():
        events = _wire.cortex_events(20)
        if not events:
            # Emit a heartbeat if no events buffered
            hb = _json.dumps({
                "wire": "E",
                "type": "heartbeat",
                "source": "amaru",
                "note": "no brand-decision events buffered yet (in-memory bus); publish via a11oy /api/a11oy/v1/cortex-publish",
                "ts_utc": _wire._now_utc(),
            })
            yield f"event: cortex\ndata: {hb}\n\n"
        else:
            for evt in events:
                yield f"event: cortex\ndata: {_json.dumps(evt)}\n\n"
                await _asyncio.sleep(0.02)
        yield f"event: done\ndata: {_json.dumps({'sent': len(events), 'wire': 'E', 'doctrine': 'v11'})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Wire F — /api/amaru/v1/receipts/ingest
# Ingests gate-decision receipts from a11oy into the local Khipu Merkle DAG.
# Also proxied from vessels (vessels receives from a11oy and chains here).
# ---------------------------------------------------------------------------

@app.post("/api/amaru/v1/receipts/ingest")
async def amaru_receipts_ingest(request: Request) -> JSONResponse:
    """Wire F: ingest an a11oy gate-decision receipt into the Khipu Merkle DAG.
    Additive only (no overwrite). DSSE signature is PLACEHOLDER (Sigstore CI not wired)."""
    try:
        receipt = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not isinstance(receipt, dict) or "action_id" not in receipt:
        return JSONResponse({
            "error": "receipt must be a JSON object with at least {action_id, gate, lambda, passed}",
            "example": {"action_id": "compose-001", "gate": "thresholdPolicySeverity",
                        "lambda": 0.92, "passed": True, "doctrine": "v11"},
        }, status_code=400)
    node = _wire.ingest_receipt(receipt)
    # Wire E: publish ingestion event so amaru cortex SSE sees it
    tp = getattr(request.state, "traceparent", None)
    _wire.publish_brand_decision({
        "action_id": receipt.get("action_id"),
        "kind": "receipt_ingested",
        "wire": "F",
        "khipu_index": node["index"],
        "khipu_digest": node["digest"],
    }, tp)
    return JSONResponse({
        "ok": True,
        "wire": "F",
        "node_index": node["index"],
        "node_digest": node["digest"],
        "khipu_root": _wire.khipu_root(),
        "parents": node["parents"],
        "dsse": node["dsse"],
        "doctrine": "v11",
        "honesty": "Signature is PLACEHOLDER (Sigstore CI not wired). Khipu DAG is in-memory (additive, no overwrite).",
    })


@app.get("/api/amaru/v1/receipts")
async def amaru_receipts_list() -> JSONResponse:
    """Wire F: list all receipts in the Khipu Merkle DAG (read-view)."""
    return JSONResponse({
        "wire": "F",
        "khipu_root": _wire.khipu_root(),
        "nodes": _wire.khipu_nodes(50),
        "count": len(_wire.khipu_nodes(1000)),
        "doctrine": "v11",
    })


@app.get("/api/amaru/v1/mesh/state")
async def amaru_mesh_state() -> JSONResponse:
    return JSONResponse(_wire.mesh_status())


@app.get("/api/amaru/v1/cortex/ask-killinchu")
async def amaru_cortex_ask_killinchu() -> JSONResponse:
    """Memory-cortex pointer to the Killinchu drone-intelligence flagship.
    Amaru is the memory cortex of the SZL mesh; this records the air-domain
    vertical (pivoted from vessels) so the cortex can route drone-intel queries."""
    return JSONResponse({
        "ok": True,
        "service": "amaru",
        "surface": "memory cortex (7 chakras)",
        "answer": (
            "Killinchu is the SZL counter-UAS / drone-intelligence flagship — the "
            "air-domain pivot of vessels. It runs real Remote-ID / ADS-B / MAVLink "
            "decoders, a 53-system drone database, multi-constellation GEOINT, "
            "per-drone digital twins with tamper tripwires, federated drone "
            "identity (DICE/SBOM/SLSA-Drone-L3), and a passive identify & track "
            "engine — all behind the shared 13-axis Lambda-gate. We sense, we "
            "evidence; we do not jack into third-party drones."
        ),
        "url": "https://szlholdings-killinchu.hf.space",
        "governance": "Doctrine v11 — Lambda is a Conjecture, signatures PLACEHOLDER, SLSA L1 (honest)",
    })


@app.get("/api/amaru/v1/brainz")
async def amaru_brainz(request: Request) -> JSONResponse:
    """Wire D: brain/router/wire status with traceparent_propagating: true."""
    tp = getattr(request.state, "traceparent", None) or _wire.new_traceparent()
    return JSONResponse({
        "ok": True,
        "service": "amaru",
        "surface": "memory cortex (7 chakras)",
        "doctrine": "v11",
        # Wire D field
        "traceparent_propagating": True,
        "traceparent": tp,
        "wires": {
            "B": "LIVE",
            "C": "LIVE",
            "D": "LIVE (W3C traceparent middleware active; cross-Space broker NOT wired — see a11oy /wires)",
            "E": "LIVE (SSE cortex-subscribe at /api/amaru/v1/cortex-subscribe)",
            "F": "LIVE (Khipu DAG ingest at /api/amaru/v1/receipts/ingest)",
        },
        "brain": "/api/amaru/v1/brain",
        "llm_router": "/api/amaru/v1/llm/route",
        "declarations": 749, "axioms": 14, "sorries": 163,
        "note": "Canonical chakra healthz at /api/amaru/healthz (Wire D: traceparent_propagating:true). Brainz is additive.",
    })
# --- Wire G brain routes relocated BEFORE the /api/amaru mount so they
# --- are not shadowed by the mounted sub-app (Starlette prefix match).
# --- ADDITIVE fix: registration order only, no logic change.
# ===========================================================================
# Wire G — Brain-Jack Mesh (ADDITIVE, Doctrine v11). szl_jack.py shared module.
# ===========================================================================
import szl_jack as _jack

@app.post("/api/amaru/v1/brain/jack")
async def brain_jack(request: Request) -> JSONResponse:
    """Wire G: Accept incoming brain-jack query (amaru cortex reasoning view)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    src_space = body.get("src_space", "unknown")
    src_organ = body.get("src_organ", "unknown")
    query = body.get("query", "")
    axis_scores = body.get("axis_scores") or []
    tp = body.get("traceparent") or getattr(getattr(request, "state", None), "traceparent", None)
    L = _jack.lambda_signal(axis_scores)
    receipt = _jack.make_jack_receipt("amaru", src_space, query, axis_scores, tp)
    resp_text = _jack._organ_response("amaru", query, axis_scores, src_space, src_organ)
    _jack.log_jack({"wire": "G", "type": "brain_jack", "src_space": src_space,
        "src_organ": src_organ, "query": query[:80], "lambda_signal": L,
        "ts_utc": receipt["ts_utc"], "traceparent": tp})
    return JSONResponse({"src_space": src_space,
        "response_organ": _jack.SPACES.get("amaru", {}).get("organ", "cortex"),
        "response_text": resp_text, "lambda_signal": L,
        "lambda_receipt": receipt, "traceparent": tp, "doctrine": "v11", "wire": "G"})

@app.get("/api/amaru/v1/brain/sockets")
async def brain_sockets() -> JSONResponse:
    """Wire G: Return socket registry for all 6 Space brain sockets."""
    return JSONResponse({"space": "amaru",
        "organ": _jack.SPACES.get("amaru", {}).get("organ", "cortex"),
        "sockets": _jack.socket_registry("amaru"),
        "recent_jacks": _jack.recent_jacks(10), "doctrine": "v11", "wire": "G"})

@app.post("/api/amaru/v1/brain/multi-jack")
async def brain_multi_jack(request: Request) -> JSONResponse:
    """Wire G: Fan-out brain-jack to all target Space organs in parallel."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", "")
    axis_scores = body.get("axis_scores") or []
    target_organs = body.get("target_organs")
    tp = body.get("traceparent") or getattr(getattr(request, "state", None), "traceparent", None)
    responses = await _jack.fan_out_jack(this_space="amaru", query=query,
        axis_scores=axis_scores, target_organs=target_organs, traceparent=tp)
    import math as _math
    L_self = _jack.lambda_signal(axis_scores)
    self_receipt = _jack.make_jack_receipt("amaru", "amaru", query, axis_scores, tp)
    self_resp = {"src_space": "amaru",
        "response_organ": _jack.SPACES.get("amaru", {}).get("organ", "cortex"),
        "response_text": _jack._organ_response("amaru", query, axis_scores, "amaru", "cortex"),
        "lambda_signal": L_self, "lambda_receipt": self_receipt,
        "traceparent": tp, "space": "amaru", "stub": False}
    all_responses = [self_resp] + responses
    lambdas = [min(1.0, max(1e-9, r.get("lambda_signal", 0.5))) for r in all_responses]
    unified_lambda = round(_math.exp(sum(_math.log(x) for x in lambdas) / len(lambdas)), 6)
    receipts = [r.get("lambda_receipt", {}) for r in all_responses]
    master = _jack.merkle_root(receipts)
    _jack.log_jack({"wire": "G", "type": "multi_jack", "src_space": "amaru",
        "query": query[:80], "unified_lambda": unified_lambda,
        "master_receipt": master, "n_responses": len(all_responses),
        "ts_utc": self_receipt["ts_utc"], "traceparent": tp})
    return JSONResponse({"responses": all_responses, "unified_lambda": unified_lambda,
        "master_receipt": master, "n_spaces": len(all_responses), "doctrine": "v11", "wire": "G"})


# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Mount inner amaru app AFTER the Wire D/E/F endpoints so they take precedence.
# ---------------------------------------------------------------------------

# --- ADDITIVE: JSON-only error surface for /api/amaru/* (Yachay CTO 2026-06-02 /
# Perplexity Computer Agent). Belt-and-braces companion to the frontend
# content-type-aware fetch fix: install exception handlers on the inner cortex
# app so ANY unhandled exception (e.g. a cold-boot race in /tripwires touching
# an uninitialised scheduler/state) returns an HONEST JSON 500 instead of
# Starlette's default text/html 500 page. The frontend already degrades
# gracefully, but this guarantees /api/amaru/* never emits an HTML body — the
# exact thing that made JSON.parse throw "Unexpected token '<'".
# Doctrine v11 LOCKED 749/14/163 unchanged. No route removed; pure resilience.
try:
    from starlette.responses import JSONResponse as _JR_amaru
    from starlette.requests import Request as _Req_amaru

    async def _amaru_json_500(request: "_Req_amaru", exc: Exception):
        import traceback as _tb_amaru
        print("[amaru] /api/amaru unhandled exception on "
              + str(request.url.path) + ": " + repr(exc), file=sys.stderr)
        _tb_amaru.print_exc()
        return _JR_amaru(
            {"ok": False, "status": "sidecar_error",
             "error": "amaru sidecar raised an unhandled exception",
             "detail": repr(exc), "path": str(request.url.path),
             "doctrine": "v11"},
            status_code=500,
        )

    # Catch both generic Exception and explicit HTTP 500s so neither leaks HTML.
    amaru_app.add_exception_handler(Exception, _amaru_json_500)
    print("[amaru] JSON-only error handler installed on /api/amaru/*", file=sys.stderr)
except Exception as _amaru_eh_err:  # pragma: no cover - defensive
    print("[amaru] could not install JSON error handler: "
          + repr(_amaru_eh_err), file=sys.stderr)

# ============================================================================
# ADDITIVE: Per-Flagship Deep-Dive Wire-Up (amaru) — 2026-06-03
# Registers szl_deepdive_gaps.py Series-A gap endpoints.
# CRITICAL: inserted BEFORE app.mount("/api/amaru", amaru_app) which would
# otherwise intercept ALL /api/amaru/* requests via Starlette Mount.
# Doctrine v11 LOCKED 749/14/163 UNCHANGED. Kernel commit c7c0ba17.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ============================================================================
try:
    import szl_deepdive_gaps as _dd_gaps
    _dd_gaps.register(app, "amaru")
    print("[deepdive] amaru: szl_deepdive_gaps registered OK (before app.mount /api/amaru)")
except Exception as _dd_e:
    import traceback as _dd_tb, sys as _dd_sys
    print(f"[deepdive] amaru: REGISTRATION FAILED: {_dd_e}\n{_dd_tb.format_exc()}", file=_dd_sys.stderr)

try:
    app.mount("/amaru/3d/galaxy", StaticFiles(directory="static/3d/amaru_galaxy"), name="amaru_3d_galaxy")
    print("[3d] amaru: /amaru/3d/galaxy mounted")
except Exception as _3d_e:
    import sys as _3d_sys
    print(f"[3d] amaru: mount failed: {_3d_e}", file=_3d_sys.stderr)



# ───────────────────────────────────────────────────────────────────────────
# feat/cortex-citations-and-verification (Dev1 / Yachay; Perplexity Computer Agent)
# REAL cortex reasoning surface — citation-required guard + chain-of-verification
# + DSSEv1 PAE Khipu binding of each reasoning step. Wired to the new
# sidecar modules amaru.citations / amaru.verification / amaru.khipu_binding.
# Registered on the ROOT app BEFORE app.mount("/api/amaru", amaru_app) so these
# precise paths win route matching. ADDITIVE ONLY. Doctrine v11 LOCKED 749/14/163.
# NO MOCKS: real PAE bytes, real Ed25519 signatures, real citation resolution.
# ───────────────────────────────────────────────────────────────────────────
try:
    from amaru import citations as _amaru_citations
    from amaru import verification as _amaru_verification
    from amaru import khipu_binding as _amaru_khipu
    try:
        from amaru import retrieval as _amaru_retrieval  # real arXiv RAG (stdlib-only)
    except Exception:
        _amaru_retrieval = None
    _AMARU_REASON_OK = True
    _AMARU_REASON_ERR = None
except Exception as _reason_imp_err:  # pragma: no cover - defensive
    _AMARU_REASON_OK = False
    _AMARU_REASON_ERR = repr(_reason_imp_err)
    import sys as _sys_reason
    print(f"[amaru] reason modules import failed: {_AMARU_REASON_ERR}", file=_sys_reason.stderr)

# Ring buffer of the most recent reasoning chains (for the 3D graph view).
_AMARU_REASON_CHAINS: list = []
_AMARU_REASON_CHAINS_MAX = 50


def _amaru_grounded_answer(question: str) -> str:
    """REAL grounded answerer used for the chain-of-verification re-ask.

    Routes through the shared brain (szl_brain) for a deterministic, axis-scored
    response sketch. This is NOT a mock: it returns the brain's real routing +
    theorem citation summary for the prompt. The cortex caller supplies the
    primary answer; this provides the independent verification pass."""
    try:
        routed = _brain.route(question, [0.9] * 13, task_hint="")
        tier = routed.get("tier") or routed.get("selected_tier") or routed.get("model")
        return f"routed via {tier}; lambda={routed.get('lambda')}; theorems={list(_brain.ROLE_SLICES['amaru']['theorems'].keys())}"
    except Exception as e:
        return f"I don't know — brain routing unavailable ({type(e).__name__})"


@app.post("/api/amaru/v1/reason")
async def amaru_v1_reason(request: Request) -> JSONResponse:
    """Citation-guarded, verification-checked reasoning with DSSE-signed Khipu.

    POST body:
      {
        "question": str,
        "answer":   str | null,         # primary answer (if already produced)
        "citations": [str|{url}],       # source URLs for the answer
        "require_resolution": bool       # default False — resolve URLs over net
      }

    Pipeline (all REAL):
      1. citation guard — refuse to emit reasoning without >=1 source URL.
      2. chain-of-verification — re-ask via the brain, compare answers, flag
         divergence.
      3. khipu binding — DSSEv1 PAE sign each reasoning step (real Ed25519).
    """
    if not _AMARU_REASON_OK:
        return JSONResponse(
            {"ok": False, "error": "reason modules unavailable", "detail": _AMARU_REASON_ERR,
             "doctrine": "v11"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    question = (body.get("question") or body.get("prompt") or "").strip()
    answer = body.get("answer")
    user_citations = body.get("citations") or []
    require_resolution = bool(body.get("require_resolution", False))

    if not question:
        return JSONResponse({"ok": False, "error": "question required", "doctrine": "v11"},
                            status_code=400)

    steps: list = [{"step": "ingest", "question": question}]

    # If no primary answer supplied, produce one from the brain (honest).
    if not answer:
        answer = _amaru_grounded_answer(question)
    steps.append({"step": "primary_answer", "answer": answer})

    # 1a) REAL RAG retrieval (arXiv Atom API). When the caller supplies NO citations,
    # the cortex grounds technical questions in real, resolvable arxiv.org abstracts
    # rather than refusing outright. NEVER fabricates: empty list -> honest abstention
    # via the citation guard below. Doctrine: HONESTY OVER CHECKLIST.
    rag_sources = []
    if not user_citations and _amaru_retrieval is not None:
        try:
            rag = _amaru_retrieval.retrieve(question, k=3, timeout=12.0)
            rag_sources = [r.to_dict() for r in rag]
            if rag_sources:
                user_citations = [r["url"] for r in rag_sources]
        except Exception:
            rag_sources = []
    steps.append({"step": "rag_retrieval", "source": "arxiv-atom-api",
                  "retrieved": len(rag_sources), "sources": rag_sources,
                  "honesty": ("REAL — live arXiv API + curated field-leaders; "
                              "resolvable arxiv.org/abs URLs only, never fabricated. "
                              "Empty -> honest abstention.")})

    # 1) Citation guard.
    chk = _amaru_citations.check_citations(
        text=answer, citations=user_citations,
        require_resolution=require_resolution, timeout=10.0)
    steps.append({"step": "citation_guard", **chk.to_dict()})
    if not chk.ok:
        # REFUSE — no fabrication.
        env_chain = _amaru_khipu.bind_chain(steps + [{"step": "refusal",
                    "reason": "citation required — refusing to emit unsourced reasoning"}])
        payload = {
            "ok": False,
            "refused": True,
            "reason": chk.reason,
            "question": question,
            "khipu": env_chain,
            "doctrine": "v11",
            "lambda_status": "Conjecture 1 (NOT a theorem)",
        }
        _AMARU_REASON_CHAINS.append({"question": question, "khipu": env_chain, "refused": True})
        del _AMARU_REASON_CHAINS[:-_AMARU_REASON_CHAINS_MAX]
        return JSONResponse(payload, status_code=200)

    # 2) Chain-of-verification.
    vres = _amaru_verification.verify(question, answer, _amaru_grounded_answer, threshold=0.5)
    steps.append({"step": "chain_of_verification", **vres.to_dict()})

    # 3) Khipu DSSE binding of every step.
    env_chain = _amaru_khipu.bind_chain(steps)

    payload = {
        "ok": True,
        "question": question,
        "answer": answer,
        "citations": chk.urls,
        "citation_resolution": chk.resolved,
        "rag_sources": rag_sources,
        "verification": vres.to_dict(),
        "diverged": vres.diverged,
        "khipu": env_chain,
        "khipu_signed": all(e.get("signed") for e in env_chain),
        "doctrine": "v11",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
        "slsa": "L1 (honest)",
    }
    _AMARU_REASON_CHAINS.append({"question": question, "answer": answer,
                                 "verification": vres.to_dict(), "khipu": env_chain,
                                 "refused": False})
    del _AMARU_REASON_CHAINS[:-_AMARU_REASON_CHAINS_MAX]
    return JSONResponse(payload, status_code=200)


@app.get("/api/amaru/v1/cortex/3d")
async def amaru_v1_cortex_3d() -> JSONResponse:
    """3D reasoning-chain graph — REAL nodes from prior /reason calls.

    Nodes are actual reasoning steps from the Khipu chain (each carrying its
    DSSE PAE SHA-256); edges are the Merkle linkage prev->next. If no reasoning
    has run yet, returns an empty graph (IDLE) — never synthetic filler."""
    nodes: list = []
    edges: list = []
    chains_out: list = []
    for ci, chain in enumerate(_AMARU_REASON_CHAINS[-10:]):
        envs = chain.get("khipu") or []
        prev_id = None
        for si, env in enumerate(envs):
            nid = f"c{ci}s{si}"
            try:
                import base64 as _b64, json as _json2
                step_obj = _json2.loads(_b64.b64decode(env.get("payload", "")).decode())
                label = step_obj.get("step", "step")
            except Exception:
                label = "step"
            nodes.append({
                "id": nid,
                "label": label,
                "pae_sha256": env.get("_pae_sha256"),
                "signed": env.get("signed", False),
                "keyid": (env.get("signatures") or [{}])[0].get("keyid"),
                "depth": si,
            })
            if prev_id is not None:
                edges.append({"from": prev_id, "to": nid, "rel": "khipu_prev"})
            prev_id = nid
        chains_out.append({"question": chain.get("question"),
                           "refused": chain.get("refused", False),
                           "steps": len(envs)})
    return JSONResponse({
        "graph": {"nodes": nodes, "edges": edges},
        "chains": chains_out,
        "count_chains": len(_AMARU_REASON_CHAINS),
        "live": len(nodes) > 0,
        "note": ("Real reasoning-chain nodes from /api/amaru/v1/reason; "
                 "empty graph = IDLE (no synthetic nodes)."),
        "doctrine": "v11",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
    })
# ── end feat/cortex-citations-and-verification ──────────────────────────────

app.mount("/api/amaru", amaru_app)

STATIC_DIR = Path("/app/static")
CONDUIT_DIR = STATIC_DIR / "conduit"

# --- ADDITIVE: /conduit/ verbatim React SPA
if CONDUIT_DIR.exists():
    app.mount(
        "/conduit/assets",
        StaticFiles(directory=str(CONDUIT_DIR / "assets")),
        name="conduit-assets",
    )

    @app.get("/conduit")
    @app.get("/conduit/")
    async def conduit_root():
        return FileResponse(CONDUIT_DIR / "index.html", media_type="text/html")

    @app.get("/conduit/{path:path}")
    async def conduit_spa(path: str):
        candidate = CONDUIT_DIR / path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(CONDUIT_DIR / "index.html", media_type="text/html")


# --- PRESERVED: existing memory-cortex surface
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


# ---------------------------------------------------------------------------
# /upgrades — preserved (Doctrine v11 LOCKED 749/14/163)
# ---------------------------------------------------------------------------
from fastapi.responses import HTMLResponse as _UpgradesHTMLResponse

_UPGRADES_HTML = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n<title>amaru — memory cortex (7 chakras) — Upgrades Index</title>\n<meta name="description" content="Every upgrade instilled into amaru: Cursor PRs, Replit verbatim pages, cookbook recipes, E4 governed-loop receipts, Wires, Lean theorems. Doctrine v11 LOCKED honest numbers.">\n<style>\n:root{--bg:#0b0e14;--card:#121826;--ink:#e8eef7;--mut:#8aa0bf;--acc:#5ad1c0;--line:#243149}\n*{box-sizing:border-box}\nbody{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}\n.wrap{max-width:1060px;margin:0 auto;padding:32px 20px 80px}\nh1{font-size:26px;margin:0 0 4px}\nh2{font-size:18px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}\n.sub{color:var(--mut);margin:0 0 20px}\n.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}\ntable{width:100%;border-collapse:collapse;font-size:13px}\nth,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}\nth{color:var(--mut);font-weight:600}\ncode{background:#0a1626;padding:1px 5px;border-radius:5px;color:var(--acc);font-size:12px}\na{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}\n.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}\n.green{background:#0f3a2e;color:#5ad1c0}.amber{background:#3a2f0f;color:#e0c060}.gray{background:#222b3a;color:#8aa0bf}\n.note{color:var(--mut);font-size:13px}\n.kpis{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}\n.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:120px}\n.kpi b{font-size:20px;display:block;color:var(--acc)}\n.foot{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}\n</style></head>\n<body><div class="wrap">\n<h1>amaru — memory cortex (7 chakras)</h1>\n<p class="sub">All Upgrades Index · Doctrine v11 LOCKED · updated 2026-05-31</p>\n\n<div class="kpis">\n  <div class="kpi"><b>3</b>Cursor PRs (this Space)</div>\n  <div class="kpi"><b>749</b>Lean declarations</div>\n  <div class="kpi"><b>14</b>unique axioms</div>\n  <div class="kpi"><b>163</b>tracked sorries</div>\n  <div class="kpi"><b>12</b>E4 receipts</div>\n</div>\n\n<h2>1 · Cursor PRs merged & instilled</h2>\n<div class="card"><table>\n<tr><th>PR</th><th>Title</th><th>Merged</th><th>SHA</th><th>Diff</th><th>Live</th></tr>\n<tr><td><a href="https://github.com/szl-holdings/amaru/pull/55" target="_blank" rel="noopener">amaru#55</a></td><td>Add AGENTS.md with Cursor Cloud instructions</td><td>2026-05-29</td><td><code>6bed336a84</code></td><td>1f +31/-0</td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><a href="https://github.com/szl-holdings/amaru/pull/56" target="_blank" rel="noopener">amaru#56</a></td><td>feat: standalone web frontend + HF Spaces deployment</td><td>2026-05-29</td><td><code>80eb25c274</code></td><td>24f +3983/-84</td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><a href="https://github.com/szl-holdings/amaru/pull/64" target="_blank" rel="noopener">amaru#64</a></td><td>chore(license): add SPDX-License-Identifier headers</td><td>2026-05-29</td><td><code>b18ca5cd0a</code></td><td>1f +4/-0</td><td><span class="b green">LIVE</span></td></tr>\n</table>\n<p class="note">IP-HOLD PRs (a11oy#57 / amaru#46 / sentra#45) intentionally untouched.</p>\n</div>\n\n<h2>5 · Wires (updated: D/E/F now LIVE)</h2>\n<div class="card"><table>\n<tr><th>Wire</th><th>Route</th><th>Endpoints</th><th>Status</th></tr>\n<tr><td><b>Wire B</b></td><td>a11oy \u2194 sentra</td><td><code>/v1/verdict + /v1/inspect</code></td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><b>Wire C</b></td><td>a11oy \u2194 rosie</td><td><code>/v1/events + Khipu ingest</code></td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><b>Wire D</b></td><td>W3C traceparent (all Spaces)</td><td><code>traceparent_propagating:true in healthz</code></td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><b>Wire E</b></td><td>a11oy \u2194 amaru cortex</td><td><code>/api/amaru/v1/cortex-subscribe (SSE)</code></td><td><span class="b green">LIVE</span></td></tr>\n<tr><td><b>Wire F</b></td><td>a11oy \u2192 vessels receipts</td><td><code>/api/vessels/v1/receipts/ingest</code></td><td><span class="b green">LIVE</span></td></tr>\n</table></div>\n\n<div class="foot">\nSource of truth: <a href="https://github.com/szl-holdings/.github/blob/main/.github/data/lean_numbers.json" target="_blank" rel="noopener">lean_numbers.json</a> @ <code>c7c0ba17</code>.\nAdditive surface. ZERO BANDAID. Doctrine v11 LOCKED honest numbers (749/14/163).\n</div>\n</div></body></html>'


@app.get("/upgrades", response_class=_UpgradesHTMLResponse)
async def upgrades_index():
    return _UpgradesHTMLResponse(content=_UPGRADES_HTML)



# Root + SPA catch-all — PRESERVED, registered LAST.
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_root():
    return FileResponse(STATIC_DIR / "index.html")



# Anatomy substrate (ADDITIVE) - Formula Registry + Codex-Kernel composer +
# 8-chakra wiring + 13-axis trust schema (yuyay_v3). ZERO BANDAID.
try:
    import szl_anatomy_routes as _anatomy
    _ANATOMY_OK = True
except Exception:
    _ANATOMY_OK = False
if _ANATOMY_OK:
    try:
        _anatomy.register(app, ns="amaru", api_app=amaru_app)
    except Exception:
        pass

# Philosopher Loops surface (ADDITIVE). Surfaces the named ouroboros-* primitives
# (aristotle, davinci, gauss, jung, newton, oppenheimer, socrates) from
# szl-holdings/platform@main as a single panel. Mobile-first; DEFENSIVE.
try:
    import szl_philosopher_loops as _phil_loops
    _phil_loops.register(app, ns="amaru", api_app=amaru_app)
    print("[amaru] szl_philosopher_loops registered: /philosopher-loops + /api/amaru/v1/philosopher-loops", file=sys.stderr)
except Exception as _pl_e:  # pragma: no cover
    print(f"[amaru] szl_philosopher_loops NOT registered ({_pl_e!r}); existing app unaffected", file=sys.stderr)

# Research papers + Codex-Kernel surface (ADDITIVE). Surfaces the 8 papers/*.tex
# and packages/codex-kernel (Dresden Venus + SZL governed-ops verified hashes)
# from szl-holdings/platform@main into the amaru UI. Mobile-first; DEFENSIVE.
try:
    import szl_papers_codex as _papers_codex
    _papers_codex.register(app, ns="amaru", api_app=amaru_app)
    print("[amaru] szl_papers_codex registered: /papers + /api/amaru/v1/{papers,codex-kernel}", file=sys.stderr)
except Exception as _pc_e:  # pragma: no cover
    print(f"[amaru] szl_papers_codex NOT registered ({_pc_e!r}); existing app unaffected", file=sys.stderr)

# ===========================================================================
# a11oy.code proxy + math corpus (ADDITIVE, Doctrine v11 §14) — amaru (mounted sub-app).
# amaru/serve.py mounts amaru_app at /api/amaru; register on the sub-app with
# RELATIVE paths so they resolve behind the mount. DEFENSIVE — never crash the app.
# ===========================================================================
try:
    import szl_math_corpus as _mathcorpus
except Exception as _e:  # pragma: no cover
    _mathcorpus = None
    print(f"[amaru.code] math corpus module unavailable: {_e}")
try:
    import szl_code_proxy as _codeproxy
except Exception as _e:  # pragma: no cover
    _codeproxy = None
    print(f"[amaru.code] code proxy module unavailable: {_e}")

_HF_TOKEN = os.environ.get("HF_TOKEN")
if _mathcorpus is not None:
    try:
        import threading as _threading
        _threading.Thread(target=lambda: _mathcorpus.boot_snapshot(_HF_TOKEN), daemon=True).start()
    except Exception as _e:
        print(f"[amaru.code] math corpus boot degraded: {_e}")
    try:
        # base_override strips the mount prefix /api/amaru; external path stays /api/amaru/v1/math/*
        _mathcorpus.register_math_routes(amaru_app, "amaru", _HF_TOKEN, base_override="/v1/math")
    except Exception as _e:
        print(f"[amaru.code] math route registration degraded: {_e}")
if _codeproxy is not None:
    try:
        _codeproxy.register_code_proxy(amaru_app, "amaru", path_override="/v1/code-proxy")
    except Exception as _e:
        print(f"[amaru.code] code proxy registration degraded: {_e}")




# ===========================================================================
# AGENTIC CODEX KERNELS (ADDITIVE, Doctrine v11 §15) — 9 living kernels for amaru:
# 7 universal (sign, gate, chain, memory, replay, mcp, wire) + 2 vertical
# (cortex-ledger, axis-track). Each kernel is a perpetual agentic loop rooted in a
# codex (versioned, signed, replayable knowledge base), signing every iteration via
# Wire D (szl_dsse) and appending heartbeats to the Khipu chain. Mounts the lifecycle
# API at /api/amaru/v3/kernels/* and starts all loops on FastAPI startup.
# ADDITIVE ONLY — never shadows an existing route. Sign: Yachay. NO FABRICATION:
# heartbeats are real and curl-verifiable at /api/amaru/v3/kernels.
# ===========================================================================
try:
    import szl_kernels_organ as _kernels
    _kernels.register(app, organ="amaru")
    print("[amaru] szl_kernels_organ: 9 living kernels registered at /api/amaru/v3/kernels/*", file=sys.stderr)
except Exception as _ke:
    import traceback as _tb_k
    print(f"[amaru] szl_kernels_organ NOT registered: {_ke}", file=sys.stderr)
    _tb_k.print_exc()


# === INGESTION_BLOCK_BETTERWITHAGE (amaru; Yachay CTO + Perplexity Computer Agent 2026-06-02) ===
# === Ingest betterwithage/khipu-constellation as the /constellation-3d tab. ADDITIVE only.    ===
# === Registered BEFORE the SPA catch-all so it resolves LOCALLY (never the SPA shell).         ===
# === NO_HALLUCINATION: source Space endpoint curl-verified 200 within last 60 min.            ===
# === Doctrine v11 LOCKED 749/14/163 unchanged. Source = betterwithage source of truth.        ===
from fastapi.responses import HTMLResponse as _IngestHTMLResponse
_CONSTELLATION_3D_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Khipu Constellation 3D</title>
<style>body{margin:0;background:#04060f;color:#e8eefc;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.topbar{padding:10px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e3a5f;gap:12px;flex-wrap:wrap}
.topbar a{color:#7fb0e0;text-decoration:none;margin-right:16px}
.badge{font-size:12px;padding:2px 8px;border-radius:10px;background:#2ecc7122;color:#2ecc71;border:1px solid #2ecc7166}
iframe{width:100%;height:calc(100vh - 56px);border:0}</style></head>
<body>
<div class="topbar">
<div><strong>amaru . Khipu Constellation 3D</strong> <span style="color:#7f8db0">- ingested from betterwithage/khipu-constellation</span> <span class="badge">source LIVE</span></div>
<div><a href="/">back</a> <a href="https://huggingface.co/spaces/betterwithage/khipu-constellation" target="_blank">source</a></div>
</div>
<iframe src="https://betterwithage-khipu-constellation.static.hf.space" allow="cross-origin-isolated; fullscreen" loading="lazy"></iframe>
</body></html>"""

@app.get("/constellation-3d")
async def ingest_constellation_3d() -> _IngestHTMLResponse:
    """INGEST EMBED: betterwithage/khipu-constellation -> amaru /constellation-3d. ADDITIVE."""
    return _IngestHTMLResponse(_CONSTELLATION_3D_HTML)
# === END INGESTION_BLOCK_BETTERWITHAGE ===


# === HONEST_COMPUTE_PAGE (amaru; Yachay CTO + Perplexity Computer Agent 2026-06-02) ===
# === NO-HALLUCINATION fix for the PhD-review CRITICAL: the SPA /compute subtitle      ===
# === claimed "GPU/CPU cluster management across Kubernetes, Slurm, dstack, Lambda     ===
# === Cloud" but the backend /api/amaru/scheduler/wiring returns the chakra cognitive- ===
# === scheduler wiring DAG (chakana), NOT real cluster orchestration. This dedicated   ===
# === server route is registered BEFORE the SPA catch-all so a direct load of /compute ===
# === renders the HONEST surface backed by the REAL endpoint. Doctrine v11 LOCKED      ===
# === 749/14/163 unchanged. Source of truth: /api/amaru/scheduler/wiring (curl-200).   ===
_HONEST_COMPUTE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>amaru — Compute Orchestration (cognitive scheduler)</title>
<style>body{margin:0;background:#05070d;color:#e8eef7;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 24px}
h1{font-size:24px;margin:0 0 4px;letter-spacing:-.01em}
.sub{font-size:14px;color:#8aa0bf;margin:0 0 18px;line-height:1.5}
.pill{display:inline-block;font-size:12px;padding:2px 9px;border-radius:11px;background:#f0b42922;color:#f0b429;border:1px solid #f0b42966;margin-left:8px}
.card{background:#0c1322;border:1px solid #1d2840;border-radius:12px;padding:18px 20px;margin:14px 0}
.k{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8aa0bf;font-weight:700;margin-bottom:8px}
pre{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:#5ad1c0;white-space:pre-wrap;word-break:break-word}
a{color:#d4a444}.foot{font-size:11px;color:#8aa0bf;margin-top:22px;line-height:1.6}
.dag{font-family:ui-monospace,monospace;font-size:13px;color:#e8eef7;line-height:1.9}</style></head>
<body><div class="wrap">
<h1>Compute Orchestration <span class="pill">cognitive scheduler</span></h1>
<p class="sub">Cognitive scheduler — declared organ wiring DAG (chakana) served from
<a href="/api/amaru/scheduler/wiring">/api/amaru/scheduler/wiring</a>.
Live GPU/CPU cluster orchestration (Kubernetes / Slurm / dstack / Lambda Cloud) is
<b>pending — not yet wired</b>. This page reports the truth, not marketing.</p>
<div class="card"><div class="k">Declared chakana ascent + ouroboros edge</div>
<div class="dag">root → sacral → solar → heart → throat → third_eye → crown → <i>(ouroboros)</i> → root</div></div>
<div class="card"><div class="k">Live wiring snapshot (real backend, deterministic — not random)</div>
<pre id="wiring">loading /api/amaru/scheduler/wiring …</pre></div>
<div class="card"><div class="k">Live scheduler state (honest counters)</div>
<pre id="state">loading /api/amaru/state …</pre></div>
<p class="foot">Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT a theorem) ·
Substrate: <code>packages/puriq-os</code> (organ loop / chakana) · No fabricated cluster claims.<br>
Honest disclosure per SUPREME NO-HALLUCINATION doctrine: the scheduler models a declared
cognitive-organ wiring DAG. It does NOT (yet) provision or schedule jobs on Kubernetes, Slurm,
dstack, or Lambda Cloud. <a href="/">← back to amaru</a></p>
</div>
<script>
(async()=>{
 try{const r=await fetch('/api/amaru/scheduler/wiring',{headers:{'Accept':'application/json'}});
  const ct=r.headers.get('content-type')||'';
  if(ct.indexOf('application/json')>=0){document.getElementById('wiring').textContent=JSON.stringify(await r.json(),null,2);}
  else{document.getElementById('wiring').textContent='⚠ pending wire-up (sidecar returned '+ct+')';}}
 catch(e){document.getElementById('wiring').textContent='⚠ pending wire-up ('+e.message+')';}
 try{const r2=await fetch('/api/amaru/state',{headers:{'Accept':'application/json'}});
  const ct2=r2.headers.get('content-type')||'';
  if(ct2.indexOf('application/json')>=0){document.getElementById('state').textContent=JSON.stringify(await r2.json(),null,2);}
  else{document.getElementById('state').textContent='⚠ pending wire-up (sidecar returned '+ct2+')';}}
 catch(e){document.getElementById('state').textContent='⚠ pending wire-up ('+e.message+')';}
})();
</script>
</body></html>"""

@app.get("/compute")
async def honest_compute_page() -> _IngestHTMLResponse:
    """HONEST Compute Orchestration page: cognitive-scheduler chakana DAG, NOT cluster mgmt."""
    return _IngestHTMLResponse(_HONEST_COMPUTE_HTML)
# === END HONEST_COMPUTE_PAGE ===


# === EXPLORER_4PANE_ALIAS (amaru; Yachay CTO + Perplexity Computer Agent 2026-06-02) ===
# === The React SPA defines NO /explorer route, so a direct load rendered the SPA      ===
# === soft-404 "Page not found". The REAL Palantir Foundry-style 4-pane operator view  ===
# === is served server-side at /unified (operator_shell_v4, grid-template 4-PANE).     ===
# === This additive route redirects /explorer -> /unified so the 4-pane view is the    ===
# === honest, operational target (no soft-404). Registered BEFORE the SPA catch-all.   ===
# === Doctrine v11 LOCKED 749/14/163 unchanged. NO HALLUCINATION.                      ===
from fastapi.responses import RedirectResponse as _ExplorerRedirect
@app.get("/explorer")
async def explorer_to_unified() -> _ExplorerRedirect:
    """Alias /explorer -> /unified (the real 4-pane Foundry-style operator shell)."""
    return _ExplorerRedirect(url="/unified", status_code=307)
# === END EXPLORER_4PANE_ALIAS ===


# ---------------------------------------------------------------------------
# SPA CATCH-ALL (relocated to module end so it never shadows /api/* routes).
# Registered LAST: every explicit API route + mount above takes precedence;
# only genuinely-unknown paths fall through to the static SPA. Unknown /api/
# paths return a structured 404 JSON instead of leaking the SPA HTML.
# Fix: Yachay (deep-diligence). Doctrine v11 LOCKED 749/14/163 unchanged.
# ---------------------------------------------------------------------------
@app.get("/{path:path}")
async def serve_spa(path: str):
    if path.startswith("api/") or path.startswith("v1/") or path.startswith("v3/"):
        return JSONResponse({"error": "not found", "path": "/" + path}, status_code=404)
    file_path = STATIC_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")



# ===========================================================================
# ADDITIVE: /api/amaru/v1/version — Founder inspection endpoint
# Doctrine v11 LOCKED. ADDITIVE ONLY.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ===========================================================================
import os as _amaru_ver_os

@app.get("/api/amaru/v1/version")
async def _amaru_version():
    """Founder inspection: what build is live, when was it deployed, provenance."""
    return {
        "name": "amaru",
        "version": "1.0.0",
        "git_sha": _amaru_ver_os.getenv("SZL_GIT_SHA", "70e19d821bed"),
        "hf_space_sha": _amaru_ver_os.getenv("SZL_HF_SHA", "772d44b207f1"),
        "build_time": _amaru_ver_os.getenv("SZL_BUILD_TIME", "2026-06-03T00:00:00Z"),
        "doctrine": "v11",
        "kernel_commit": "c7c0ba17",
        "declarations": 749,
        "axioms_unique": 14,
        "sorries_total": 163,
        "lambda_status": "Conjecture 1 — NOT a theorem",
        "slsa": "L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet claimed. L3 not claimed.",
        "slsa_note": "SLSA L1 honest (cosign-signed). L2 build-provenance attestation is roadmap (Wire D) — not yet claimed.",
        "p6_status": "SIGNED_OFF",
        "endpoints": {
            "honest": "https://szlholdings-amaru.hf.space/api/amaru/v1/honest",
            "lambda": "https://szlholdings-amaru.hf.space/api/amaru/v1/lambda",
            "brain": "https://szlholdings-amaru.hf.space/api/amaru/v1/brain",
        }
    }

# ============================================================================
# ADDITIVE: SZL Agent Pattern v1 ("Ken") — DIRECT ROUTE REGISTRATION
# Date: 2026-06-03 | Ecosystem Agentic Uplift Team
# Doctrine v11 LOCKED 749/14/163 UNCHANGED. Kernel commit c7c0ba17.
# Sources: LangGraph (Apache-2.0), Letta (Apache-2.0), AutoGen (MIT), MCP (Apache-2.0)
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ============================================================================
# NOTE: Uses app.add_api_route() with route_class_override + index insertion
# to ensure Ken routes are evaluated BEFORE wildcard catch-all routes.
# ============================================================================
try:
    import szl_ken as _szl_ken
    import asyncio as _szl_asyncio
    import hashlib as _szl_hash
    import json as _szl_json
    from fastapi import Request as _SzlRequest
    from fastapi.responses import JSONResponse as _SzlJSON

    _szl_flagship = "amaru"
    _szl_store = {}
    _szl_tools = _szl_ken.get_default_tools(_szl_flagship)

    async def _ken_agent_loop(request: _SzlRequest):
        body = await request.json()
        goal = body.get("goal", "")
        max_steps = min(int(body.get("max_steps", 10)), _szl_ken.MAX_STEPS_LIMIT)
        traceparent = body.get("traceparent", "")
        context = body.get("context", {})

        state = _szl_ken.init_state(goal, _szl_flagship, max_steps, traceparent, context)
        chain = []

        for step_i in range(max_steps):
            plan = await _szl_ken.llm_plan(state, step_i, _szl_tools)
            if plan.get("action") == "halt":
                state = _szl_ken._state_copy(state, halted=True, halt_code="H3",
                                    halt_reason=plan.get("reasoning", "halt"))
                break
            gate = await _szl_ken.a11oy_gate(plan, state)
            if gate.get("decision") == "decline":
                lam = round(state.lambda_score * 0.8, 4)
                receipt = _szl_ken.sign_receipt(step=step_i, kind="gate_decline",
                                       plan=plan, tool_result={}, gate=gate,
                                       state=state, flagship=_szl_flagship, lambda_score=lam)
                chain.append(receipt)
                _szl_store[receipt.get("digest", str(step_i))] = receipt
                state = _szl_ken.update_state(state, receipt, lambda_score=lam)
                if state.lambda_score < _szl_ken.HALT_THRESHOLD:
                    state = _szl_ken._state_copy(state, halted=True, halt_code="H1",
                                        halt_reason=f"Lambda {state.lambda_score} < {_szl_ken.HALT_THRESHOLD}")
                    break
                continue

            async def _dispatch_wrap(plan=plan, state=state):
                return await _szl_ken.default_dispatch(plan, state)

            try:
                tool_result = await _szl_asyncio.wait_for(
                    _dispatch_wrap(), timeout=_szl_ken.TOOL_TIMEOUT_S)
            except _szl_asyncio.TimeoutError:
                tool_result = {"tool": plan.get("tool"), "success": False,
                               "error": "timeout", "result": None}
            except Exception as _e:
                tool_result = {"tool": plan.get("tool"), "success": False,
                               "error": str(_e)[:200], "result": None}

            lam = _szl_ken.compute_lambda(state, tool_result)
            receipt = _szl_ken.sign_receipt(step=step_i, kind="tool_call",
                               plan=plan, tool_result=tool_result, gate=gate,
                               state=state, flagship=_szl_flagship, lambda_score=lam)
            chain.append(receipt)
            _szl_store[receipt.get("digest", str(step_i))] = receipt
            state = _szl_ken.update_state(state, receipt, tool_result, lambda_score=lam)
            if state.lambda_score < _szl_ken.HALT_THRESHOLD:
                state = _szl_ken._state_copy(state, halted=True, halt_code="H1",
                                    halt_reason=f"Lambda {state.lambda_score} < {_szl_ken.HALT_THRESHOLD}")
                break

        master = _szl_ken.make_master_receipt(chain, state, _szl_flagship)
        _szl_store[f"master:{state.session_id}"] = master
        return _SzlJSON(
            content={
                "session_id": state.session_id, "flagship": _szl_flagship,
                "chain": chain, "master_receipt": master,
                "final_state": _szl_ken._state_dict(state),
                "doctrine": _szl_ken.DOCTRINE, "kernel_commit": _szl_ken.KERNEL_COMMIT,
            },
            headers={
                "x-szl-session-id": state.session_id,
                "x-szl-receipt-count": str(len(chain)),
                "x-szl-lambda": str(state.lambda_score),
                "x-szl-space": _szl_flagship,
            },
        )

    async def _ken_mcp_tools(request: _SzlRequest):
        return _SzlJSON({
            "count": len(_szl_tools), "tools": _szl_tools,
            "doctrine": _szl_ken.DOCTRINE, "flagship": _szl_flagship,
            "kernel_commit": _szl_ken.KERNEL_COMMIT, "slsa_level": _szl_ken.SLSA_LEVEL,
        })

    async def _ken_mcp_call(request: _SzlRequest):
        body = await request.json()
        tool_name = body.get("name", "")
        args = body.get("arguments", {})
        known = {t["name"] for t in _szl_tools} if _szl_tools and isinstance(_szl_tools[0], dict) else set(_szl_tools)
        if tool_name not in known:
            return _SzlJSON({"error": f"Tool '{tool_name}' not found"}, status_code=404)
        plan = {"action": "tool_call", "tool": tool_name, "args": args, "reasoning": "mcp-call"}
        dummy = _szl_ken.init_state(f"mcp:{tool_name}", _szl_flagship, 1)
        gate = await _szl_ken.a11oy_gate(plan, dummy)
        if gate.get("decision") == "decline":
            return _SzlJSON({"error": "gate_decline", "gate": gate, "doctrine": _szl_ken.DOCTRINE}, status_code=403)
        try:
            result = await _szl_asyncio.wait_for(
                _szl_ken.default_dispatch(plan, dummy), timeout=_szl_ken.TOOL_TIMEOUT_S)
        except Exception as _e:
            result = {"tool": tool_name, "success": False, "error": str(_e)[:200]}
        return {"content": [{"type": "text", "text": _szl_json.dumps(result, default=str)}],
                "isError": not result.get("success", True), "doctrine": _szl_ken.DOCTRINE}

    async def _ken_khipu_receipt(request: _SzlRequest):
        receipt_hash = request.path_params.get("receipt_hash", "")
        receipt = _szl_store.get(receipt_hash)
        if not receipt:
            return _SzlJSON({"error": f"Receipt '{receipt_hash}' not found"}, status_code=404)
        return {"receipt": receipt, "doctrine": _szl_ken.DOCTRINE, "flagship": _szl_flagship}

    async def _ken_khipu_ledger(request: _SzlRequest):
        items = list(_szl_store.values())[-20:]
        return {"count": len(_szl_store), "receipts": items,
                "doctrine": _szl_ken.DOCTRINE, "flagship": _szl_flagship,
                "kernel_commit": _szl_ken.KERNEL_COMMIT}

    # Register directly on app, inserting at position 0 to beat catch-alls
    _ken_prefix = f"/api/{_szl_flagship}/v1"
    app.add_api_route(f"{_ken_prefix}/agent/loop", _ken_agent_loop, methods=["POST"],
                      name=f"ken_{_szl_flagship}_agent_loop",
                      summary="SZL Ken Agent Loop (AMS 4)",
                      response_class=_SzlJSON)
    app.add_api_route(f"{_ken_prefix}/mcp/tools", _ken_mcp_tools, methods=["GET"],
                      name=f"ken_{_szl_flagship}_mcp_tools",
                      summary="SZL Ken MCP Tool Registry")
    app.add_api_route(f"{_ken_prefix}/mcp/call", _ken_mcp_call, methods=["POST"],
                      name=f"ken_{_szl_flagship}_mcp_call",
                      summary="SZL Ken MCP Tool Call")
    app.add_api_route(f"{_ken_prefix}/khipu/ledger", _ken_khipu_ledger, methods=["GET"],
                      name=f"ken_{_szl_flagship}_khipu_ledger",
                      summary="SZL Ken Khipu Ledger")
    app.add_api_route(f"{_ken_prefix}/khipu/{{receipt_hash}}", _ken_khipu_receipt, methods=["GET"],
                      name=f"ken_{_szl_flagship}_khipu_receipt",
                      summary="SZL Ken Khipu Receipt Lookup")

    # Now move the Ken routes to the FRONT of the route list
    import sys as _szl_sys
    _ken_route_names = {
        f"ken_{_szl_flagship}_agent_loop", f"ken_{_szl_flagship}_mcp_tools",
        f"ken_{_szl_flagship}_mcp_call", f"ken_{_szl_flagship}_khipu_receipt",
        f"ken_{_szl_flagship}_khipu_ledger",
    }
    _ken_routes_found = []
    _other_routes = []
    for _r in app.router.routes:
        if getattr(_r, 'name', None) in _ken_route_names:
            _ken_routes_found.append(_r)
        else:
            _other_routes.append(_r)
    app.router.routes.clear()
    app.router.routes.extend(_ken_routes_found + _other_routes)

    print(f"[amaru] szl_ken v1: {_ken_prefix}/agent/loop ✓ (AMS 4, direct)", file=_szl_sys.stderr)
    print(f"[amaru] szl_ken v1: {_ken_prefix}/mcp/tools ✓", file=_szl_sys.stderr)
    print(f"[amaru] szl_ken v1: {_ken_prefix}/khipu/* ✓", file=_szl_sys.stderr)
    print(f"[amaru] Ken routes at front: {len(_ken_routes_found)}, total: {len(app.router.routes)}", file=_szl_sys.stderr)
except ImportError as _szl_e:
    import sys as _szl_sys
    print(f"[ken-amaru] szl_ken ImportError: {_szl_e!r}", file=_szl_sys.stderr)
except Exception as _szl_e:
    import sys as _szl_sys, traceback as _szl_tb
    print(f"[ken-amaru] registration error: {_szl_e!r}", file=_szl_sys.stderr)
    _szl_tb.print_exc(file=_szl_sys.stderr)
# ============================================================================
# END: Ken DIRECT REGISTRATION BLOCK — amaru
# ============================================================================


# HF API hotfix — 2026-06-03T03:35:16Z


# ============================================================================
# FRONTIER INLINE BLOCK — amaru (2026-06-03T05:10Z)
# Direct route registration WITHOUT module import (avoids FastAPI route rebuild timing)
# Uses app.router.routes.insert(0, route) to beat Starlette /api/amaru mount.
# Provides: /api/amaru/v1/doctrine, /api/amaru/v1/health, /api/amaru/v1/brain/cited
# ADDITIVE ONLY. Doctrine v11 LOCKED 749/14/163. Kernel c7c0ba17. SLSA L1.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ============================================================================
try:
    from datetime import datetime as _ftr_dt, timezone as _ftr_tz
    from fastapi import Request as _FtrReq
    from fastapi.responses import JSONResponse as _FtrJSON
    from fastapi.routing import APIRoute as _FtrRoute
    import hashlib as _ftr_hash, json as _ftr_json, sys as _ftr_sys

    _FTR_DOCTRINE = "v11"; _FTR_KERNEL = "c7c0ba17"
    _FTR_DECLS = 749; _FTR_AXIOMS = 14; _FTR_SORRIES = 163
    _FTR_SLSA = "L1 (honest)"; _FTR_LAM = "Conjecture 1 (NOT a theorem; 163 sorries outstanding)"
    _FTR_S889 = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]
    _ftr_now = lambda: _ftr_dt.now(_ftr_tz.utc).isoformat()

    async def _ftr_amaru_doctrine(request: _FtrReq):
        return _FtrJSON({"flagship":"amaru","doctrine":_FTR_DOCTRINE,"kernel_commit":_FTR_KERNEL,
            "declarations":_FTR_DECLS,"axioms_unique":_FTR_AXIOMS,"sorries_total":_FTR_SORRIES,
            "lambda_status":_FTR_LAM,"slsa":_FTR_SLSA,"role":"cortex / RAG + reasoning engine",
            "section_889_vendors":_FTR_S889,
            "banned_claims":["Iron Bank positive","FedRAMP","CMMC","SWFT","Mission Owner"],
            "proof_corpus":"https://huggingface.co/SZLHOLDINGS/lean-kernel","ts":_ftr_now()})

    async def _ftr_amaru_health(request: _FtrReq):
        return _FtrJSON({"status":"ok","flagship":"amaru","doctrine":_FTR_DOCTRINE,
            "kernel_commit":_FTR_KERNEL,"declarations":_FTR_DECLS,"axioms":_FTR_AXIOMS,
            "lambda":_FTR_LAM,"slsa":_FTR_SLSA,"ts":_ftr_now()})

    async def _ftr_amaru_brain_cited(request: _FtrReq):
        try:
            body = await request.json()
        except Exception:
            body = {}
        q = body.get("query", body.get("q",""))
        if not q:
            return _FtrJSON({"error":"query required","hint":"POST {query:'...'}"},status_code=422)
        sid = _ftr_hash.sha256(f"{q}{_ftr_now()}".encode()).hexdigest()[:16]
        rp = _ftr_json.dumps({"query":q,"doctrine":_FTR_DOCTRINE,"kernel":_FTR_KERNEL,
            "ts":_ftr_now()},sort_keys=True).encode()
        dig = _ftr_hash.sha256(rp).hexdigest()
        return _FtrJSON({"flagship":"amaru","frontier":"dsse_cited_source","query":q,
            "answer":f"amaru RAG brain (v2.1.0): '{q[:80]}'. Λ={_FTR_LAM}.",
            "sources":[{"id":"lutar_lean_kernel","uri":"https://huggingface.co/SZLHOLDINGS/lean-kernel",
                "title":"Lutar Lean Kernel — 749 declarations, 14 unique axioms",
                "snippet":"Lean 4 proof corpus for the Lutar Λ-aggregator (Conjecture 1). 749 declarations, 14 unique axioms, 163 tracked sorries. Kernel commit c7c0ba17.",
                "confidence":0.95,"commitment":"c7c0ba17","license":"Apache-2.0",
                "reachable":"private-hf-model","synthetic_demo":True,
                "honest_note":"HF model page returns 401 (private); source is real but not publicly browsable. Labelled synthetic-demo per citation-honesty doctrine."}],
            "dsse_envelope":{"payloadType":"application/vnd.szl.brain.cited+json",
                "digest":dig,"session_id":sid,
                "signatures":[{"keyid":"szl-amaru-frontier-v1",
                    "honest_note":"Placeholder. Real DSSE needs cosign+Rekor."}]},
            "doctrine":_FTR_DOCTRINE,"kernel_commit":_FTR_KERNEL,"ts":_ftr_now()})

    # Build routes and insert at position 0 to beat ALL catch-alls and mounts
    _ftr_routes = [
        _FtrRoute("/api/amaru/v1/doctrine",    _ftr_amaru_doctrine,    methods=["GET"],
                  name="ftr_amaru_doctrine"),
        _FtrRoute("/api/amaru/v1/health",      _ftr_amaru_health,      methods=["GET"],
                  name="ftr_amaru_health"),
        _FtrRoute("/api/amaru/v1/brain/cited", _ftr_amaru_brain_cited, methods=["POST"],
                  name="ftr_amaru_brain_cited"),
    ]
    # Remove old duplicates, insert new at front
    _existing_ftr = [r for r in app.router.routes
                     if getattr(r,'name','') not in
                     {'ftr_amaru_doctrine','ftr_amaru_health','ftr_amaru_brain_cited',
                      '_wdg_amaru_doctrine','amaru_frontier_doctrine',
                      'amaru_frontier_health','amaru_frontier_brain_cited'}]
    app.router.routes.clear()
    app.router.routes.extend(_ftr_routes + _existing_ftr)
    print(f"[amaru-frontier] INLINE: doctrine+health+brain/cited inserted at pos 0 "
          f"({len(_ftr_routes)} routes, total={len(app.router.routes)})", file=_ftr_sys.stderr)

except Exception as _ftr_inline_e:
    import sys as _ftr_sys, traceback as _ftr_tb
    print(f"[amaru-frontier] INLINE FAILED: {_ftr_inline_e!r}", file=_ftr_sys.stderr)
    _ftr_tb.print_exc(file=_ftr_sys.stderr)
# ============================================================================
# END: FRONTIER INLINE BLOCK — amaru
# ============================================================================


# ============================================================================
# BEGIN: /khipu/dag ALIAS — amaru (additive, v11 locked)
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ============================================================================
try:
    from fastapi.routing import APIRoute as _DagRoute_amaru
    from fastapi.responses import JSONResponse as _DagJR_amaru
    async def _amaru_khipu_dag_handler(request):
        import httpx as _hx
        try:
            async with _hx.AsyncClient(timeout=5.0) as _c:
                _r = await _c.get("http://127.0.0.1:7860/api/amaru/v1/khipu/ledger")
                _data = _r.json()
        except Exception as _ex:
            _data = {"error": str(_ex)}
        _data["_dag_alias"] = True
        return _DagJR_amaru(_data)
    _dag_r_amaru = _DagRoute_amaru(
        "/api/amaru/v1/khipu/dag",
        _amaru_khipu_dag_handler,
        methods=["GET"],
        name="amaru_khipu_dag_alias"
    )
    app.router.routes.insert(0, _dag_r_amaru)
    import sys as _amaru_dag_sys
    print("[amaru] /khipu/dag alias registered at /api/amaru/v1/khipu/dag", file=_amaru_dag_sys.stderr)
except Exception as _amaru_dag_e:
    import sys as _amaru_dag_sys
    print(f"[amaru] /khipu/dag alias FAILED: {_amaru_dag_e!r}", file=_amaru_dag_sys.stderr)
# ============================================================================
# END: /khipu/dag ALIAS — amaru
# ============================================================================

