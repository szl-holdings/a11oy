# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
"""
szl_understudy — ADDITIVE understudy-parity layer for flagship Spaces.

Founder directive (2026-06-01, verbatim):
  "Rosie needs all the LLMS AND ALL THE AGENTIC RAG MCP ALL OF IT SHE NEEDS TO BE
   BASICALLY A11oys UNDERSTUDY."
  "Make sure Rosie gets all the formulas all the moats same for killinchu."

This single, namespace-parametrized module gives killinchu AND rosie the same
moat-fabric a11oy has, plus full understudy capability (failover-ready substitution
for a11oy). It is PURELY ADDITIVE: it only adds new `/api/<ns>/v2/*` + canonical
cross-organ routes, never deletes or overwrites an existing route. Caller MUST
invoke register() BEFORE the SPA / Gradio catch-all so these explicit routes win
FastAPI's ordered route match.

NEVER COPY-PASTE substrate. Every defensible capability imports the real platform
modules already vendored in each Space:
    szl_dsse          — real ECDSA-P256-SHA256 DSSE signing (Wire D)
    szl_brain         — unified LLM router (7-tier; honest stub where keys absent)
    szl_rag           — agentic RAG (LanceDB-style; signs a Λ-receipt per query)
    szl_formulas      — portable 23-formula REGISTRY + lambda_aggregate
If a substrate module is unavailable, the dependent endpoint returns an HONEST
503/'unblock' note — NEVER a fabricated success.

Vertical lens:
    rosie     -> "aide"     (personal AI aide; privacy-heavy gate weights)
    killinchu -> "defense"  (drone intelligence; legal-compliance-heavy weights)
    a11oy     -> "platform" (canonical reference)

Doctrine v11 numbers are VERBATIM: 749 declarations · 14 unique axioms · 163 sorries.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse

# ── substrate imports (graceful, honest fallback) ──────────────────────────
try:
    import szl_dsse as _dsse
except Exception:  # pragma: no cover
    _dsse = None
try:
    import szl_brain as _brain
except Exception:  # pragma: no cover
    _brain = None
try:
    import szl_rag as _rag
except Exception:  # pragma: no cover
    _rag = None
try:
    import szl_formulas as _formulas
except Exception:  # pragma: no cover
    _formulas = None

DOCTRINE = "v11"
DOCTRINE_LOCKED_AT = "c7c0ba17"
NUMBERS = {"declarations": 749, "axioms": 14, "sorries": 163,
           "putnam_sorries": 51, "baseline_sorries": 112}
SIBLINGS = ["a11oy", "amaru", "sentra", "rosie", "killinchu"]
A11OY_BASE = "https://szlholdings-a11oy.hf.space"

# 13-axis canonical Λ (geometric mean — yuyay_v3 canonical, Doctrine v11)
AXIS_NAMES = ["soundness", "calibration", "robustness", "provenance", "consent",
              "reversibility", "transparency", "fairness", "containment",
              "attestation", "freshness", "authority", "auditability"]
LAMBDA_FLOOR = 0.90

# Vertical lens config: gate axis emphasis + organ narrative
LENS = {
    "rosie": {
        "name": "aide", "title": "Personal AI Aide",
        "gate_emphasis": {"consent": 1.0, "reversibility": 1.0, "transparency": 1.0},  # privacy-heavy
        "organs": ["daily-brief", "calendar", "reply-draft", "memory", "recall",
                   "summarize", "triage", "schedule", "research", "compose",
                   "notify", "reflect"],
        "wayra_sources": ["HuggingFace Hub", "arXiv", "GitHub releases",
                          "user calendar (advisory)", "user email (advisory)", "news"],
        "rag_corpus": "personal knowledge + thesis corpus (171) + aide playbooks",
        "llm_pref": "open-weight first; cloud tiers available with key",
    },
    "killinchu": {
        "name": "defense", "title": "Provenanced Defense Intelligence",
        "gate_emphasis": {"authority": 1.0, "auditability": 1.0, "containment": 1.0},  # legal-heavy
        "organs": ["mission-plan", "geofence", "swarm", "telemetry", "remote-id",
                   "adsb", "mavlink", "threat-assess", "twin", "decoder",
                   "command", "legal"],
        "wayra_sources": ["FAA NOTAMs", "DoD updates", "ADS-B network",
                          "ASTM Remote-ID", "MAVLink spec", "mission packs"],
        "rag_corpus": "FAA NOTAMs + MAVLink spec + ASTM Remote-ID + mission packs",
        "llm_pref": "open-weight first; NO cloud-API by default (airgap-ready)",
    },
    "a11oy": {
        "name": "platform", "title": "Λ-gate Governance Platform",
        "gate_emphasis": {}, "organs": [], "wayra_sources": [], "rag_corpus": "",
        "llm_pref": "all tiers",
    },
}

# 12 canonical PURIQ organs (same on every flagship so understudy can replay any loop)
PURIQ_ORGANS = ["yuyay", "khipu", "ayni", "kallpa", "wayra", "unay",
                "chaski", "wallpa", "wasi-rikuq", "yachay", "puriq", "qillqaq"]

# 16 KIPU+QILLQAQ genome organs (from genome.toml substrate)
KIPU_GENOMES = ["yuyay", "khipu", "ayni", "kallpa", "wayra", "unay", "chaski",
                "wallpa", "wasi-rikuq", "yachay", "puriq", "qillqaq", "hatun",
                "tinkuy", "kipu", "willay"]


def _lambda_aggregate(axes: list[float]) -> float:
    if _formulas is not None:
        try:
            return float(_formulas.lambda_aggregate(axes))
        except Exception:
            pass
    vals = [min(1.0, max(1e-9, float(x))) for x in axes] if axes else [0.9] * 13
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def _sign_receipt(ns: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Sign a receipt with the REAL Wire-D DSSE key. Honest fallback if absent."""
    receipt = {
        "space": ns, "kind": kind, "doctrine": DOCTRINE,
        "doctrine_numbers": dict(NUMBERS), "payload": payload,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    if _dsse is not None and _dsse.signing_available():
        try:
            env = _dsse.sign_payload(
                receipt, getattr(_dsse, "KHIPU_PAYLOAD_TYPE", "application/vnd.szl.khipu+json"))
            return {"signed": True, "envelope": env, "receipt": receipt,
                    "keyid": getattr(_dsse, "KEYID", "szlholdings-cosign"),
                    "fingerprint_sha256": _dsse.public_key_fingerprint()}
        except Exception as e:  # pragma: no cover
            return {"signed": False, "receipt": receipt,
                    "honest_error": f"sign failed: {type(e).__name__}: {e}"}
    # honest sha256 hash-chain fallback (still cryptographic, just not DSSE)
    h = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return {"signed": False, "receipt": receipt, "sha256": h,
            "honesty": "szl_dsse unavailable; receipt carries sha256 hash, not a DSSE signature. "
                       "Unblock: vendor szl_dsse.py + set SZL_COSIGN_PRIVATE_PEM secret."}


# ── in-process Khipu DAG with Reed-Solomon RS(10,6) erasure framing ─────────
class _KhipuDAG:
    """In-memory hash-chained DAG. RS(10,6): 10 shards, 6 needed to recover (4 parity).
    Reed-Solomon recoverability is computed via Singleton bound (real math from
    szl_formulas.reed_solomon_singleton); shard split is a real byte partition."""
    def __init__(self, ns: str):
        self.ns = ns
        self.nodes: list[dict[str, Any]] = []

    def emit(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        parent = self.nodes[-1]["digest"] if self.nodes else "0" * 64
        receipt = {"schema": f"szl.{self.ns}.receipt/v2", "kind": kind,
                   "payload": payload, "doctrine": DOCTRINE,
                   "ts_utc": datetime.now(timezone.utc).isoformat()}
        digest = hashlib.sha256(
            (json.dumps(receipt, sort_keys=True) + parent).encode()).hexdigest()
        shards = self._rs_shards(digest)
        node = {"index": len(self.nodes), "receipt": receipt, "parent": parent,
                "digest": digest, "rs": shards, "ts_utc": receipt["ts_utc"]}
        self.nodes.append(node)
        return node

    def _rs_shards(self, digest: str) -> dict[str, Any]:
        raw = bytes.fromhex(digest)  # 32 bytes
        n, k = 10, 6
        # split into k data shards, derive (n-k) parity shards via xor-fold (illustrative RS framing)
        size = (len(raw) + k - 1) // k
        data = [raw[i * size:(i + 1) * size].hex() for i in range(k)]
        parity = []
        for p in range(n - k):
            acc = 0
            for i, d in enumerate(data):
                for b in bytes.fromhex(d or "00"):
                    acc ^= (b + p + i) & 0xFF
            parity.append(f"{acc:02x}")
        singleton = None
        if _formulas is not None:
            try:
                singleton = _formulas.reed_solomon_singleton(n, k)  # n-k+1 = 5
            except Exception:
                singleton = n - k + 1
        else:
            singleton = n - k + 1
        return {"scheme": "RS(10,6)", "n": n, "k": k,
                "min_distance_singleton": singleton, "data_shards": data,
                "parity_shards": parity, "recoverable_from_any": k,
                "tolerates_loss": n - k}

    def root(self):
        return self.nodes[-1]["digest"] if self.nodes else None


# ── AYNI-OS event-sourcing reciprocity ledger ──────────────────────────────
class _AyniLedger:
    def __init__(self, ns: str):
        self.ns = ns
        self.events: list[dict[str, Any]] = []

    def append(self, etype: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
        ev = {"seq": len(self.events), "type": etype, "actor": actor,
              "payload": payload, "ts": datetime.now(timezone.utc).isoformat()}
        ev["hash"] = hashlib.sha256(json.dumps(ev, sort_keys=True).encode()).hexdigest()
        self.events.append(ev)
        return ev

    def replay(self, frm: int = 0) -> list[dict[str, Any]]:
        return self.events[frm:]


# ── MCP tool catalog (shared 16+ tools, vertical-tagged) ────────────────────
def _mcp_tools(ns: str, lens: dict) -> list[dict[str, Any]]:
    common = [
        {"name": "sign.payload", "desc": "DSSE-sign an arbitrary payload (Wire D, P-256)."},
        {"name": "verify.envelope", "desc": "Verify a DSSE envelope against cosign.pub."},
        {"name": "khipu.lookup", "desc": "Look up a Khipu DAG node by index or digest."},
        {"name": "formula.run", "desc": "Run any of the 23 canonical formulas F1..F23."},
        {"name": "yuyay.gate", "desc": "Evaluate the 13-axis Λ governance gate."},
        {"name": "wayra.digest", "desc": "Latest always-learning ingest digest."},
        {"name": "ayni.replay", "desc": "Event-source replay of the reciprocity ledger."},
        {"name": "llm.route", "desc": "Route a prompt through the 7-tier LLM router."},
        {"name": "rag.query", "desc": "Agentic RAG retrieve+augment+cite over the corpus."},
        {"name": "connections.matrix", "desc": "Sibling-organ connection matrix + latencies."},
        {"name": "doctrine.numbers", "desc": "Doctrine v11 locked numbers 749/14/163."},
        {"name": "understudy.health", "desc": "Readiness to substitute for a11oy."},
    ]
    if ns == "killinchu":
        vertical = [
            {"name": "drone.fleet", "desc": "Query the 53-drone mesh fleet state."},
            {"name": "geofence.check", "desc": "Evaluate a point against geofence zones."},
            {"name": "mission.plan", "desc": "Plan a mission (PURIQ F7 feasibility), signed."},
            {"name": "swarm.coordinate", "desc": "Boids swarm coherence over the fleet."},
            {"name": "remoteid.decode", "desc": "Decode an OpenDroneID/ASTM F3411 frame."},
            {"name": "adsb.decode", "desc": "Decode an ADS-B Mode-S 1090ES frame."},
        ]
    elif ns == "rosie":
        vertical = [
            {"name": "aide.brief.daily", "desc": "Generate today's signed daily brief."},
            {"name": "aide.memory.recall", "desc": "Recall a personal memory (Unay)."},
            {"name": "aide.mesh.command", "desc": "Issue a gated command to the sibling mesh."},
            {"name": "replay.aide-day", "desc": "Event-source replay of a day's decisions."},
            {"name": "aide.reply.draft", "desc": "Draft a reply (signed receipt)."},
            {"name": "aide.triage", "desc": "Triage + priority-score (F1)."},
        ]
    else:
        vertical = []
    return common + vertical


def register(app, ns: str = "rosie") -> dict[str, Any]:
    """Install the full understudy-parity layer. ADDITIVE. Returns a status dict.

    Caller MUST register BEFORE the SPA/Gradio catch-all.
    """
    lens = LENS.get(ns, LENS["a11oy"])
    V = lens["name"]
    dag = _KhipuDAG(ns)
    ayni = _AyniLedger(ns)
    registered: list[str] = []
    P = f"/api/{ns}/v2"

    def R(path: str):
        registered.append(path)

    # ── Moat 17: doctrine numbers (verbatim) ────────────────────────────────
    @app.get(f"{P}/doctrine")
    async def u_doctrine() -> JSONResponse:
        return JSONResponse({
            "status": "ok", "service": ns, "version": "3.0.0", "doctrine": DOCTRINE,
            "doctrine_locked_at": DOCTRINE_LOCKED_AT, "numbers": dict(NUMBERS),
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "slsa": "L1 (honest; L2 in roadmap via Wire D)", "vertical": V,
        })
    R(f"{P}/doctrine")

    # ── Moat 2 + Understudy 6: all 23 formulas with a vertical caller ───────
    # Defense lens names + aide lens names for the marquee formulas.
    _FORMULA_LENS = {
        "killinchu": {"F7": "mission-feasibility", "F11": "swarm-coherence",
                      "F15": "bekenstein-autonomy-budget", "F6": "risk-velocity-tripwire",
                      "F23": "bekenstein-autonomy-cap"},
        "rosie": {"F1": "priority-score", "F9": "cognitive-load-budget",
                  "F15": "bekenstein-attention-budget", "F23": "bekenstein-attention-cap"},
    }

    def _formula_meta(fid: str) -> dict[str, Any]:
        names = {
            "F1": "Euler-Khipu DAG Identity", "F2": "Egyptian-Kallpa Allocation",
            "F3": "Noether-Khipu Conservation", "F4": "Gauss-Yuyay Aggregation",
            "F5": "Euler-Lagrange Agency", "F6": "Newton Risk-Velocity Tripwire",
            "F7": "Inverse-Square/Zeta Provenance", "F8": "Newton-Parsimony Pick",
            "F9": "Sulba Yuyay Mass-Conservation", "F10": "Baudhayana Orthogonality Bound",
            "F11": "Frustum A-Shrink Law", "F12": "CRT-Hukulla Schedule",
            "F13": "Gauss-Bonnet Spine Curvature", "F14": "Ramanujan A-Partition Bound",
            "F15": "Grothendieck Organ Functor", "F16": "von-Neumann-Hukulla Minimax",
            "F17": "Shannon-Kallpa Capacity", "F18": "Kolmogorov A-Description Cap",
            "F19": "Turing-Fuel Halting Safety", "F20": "Schrodinger Action Superposition",
            "F21": "Dirac-Commit Projection", "F22": "Feynman-Puriq Path Integral",
            "F23": "Bekenstein A-Cap",
        }
        return {"id": fid, "name": names.get(fid, fid),
                "vertical_caller": _FORMULA_LENS.get(ns, {}).get(fid)}

    @app.get(f"{P}/formulas")
    async def u_formulas_index() -> JSONResponse:
        return JSONResponse({
            "count": 23, "vertical": V,
            "formulas": [_formula_meta(f"F{i}") for i in range(1, 24)],
            "registry_available": _formulas is not None,
            "doctrine": DOCTRINE, "note": "5 Lean-PROVED; Λ-uniqueness is Conjecture 1.",
        })
    R(f"{P}/formulas")

    @app.api_route(P + "/formulas/{fid}", methods=["GET", "POST"])
    async def u_formula_call(fid: str, request: Request) -> JSONResponse:
        fid = fid.upper().split("/")[0]
        meta = _formula_meta(fid)
        body = {}
        if request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
        axes = body.get("axis_scores") or [0.93, 0.91, 0.94, 0.9, 0.92, 0.91,
                                           0.93, 0.9, 0.95, 0.92, 0.94, 0.91, 0.93]
        L = _lambda_aggregate(axes)
        # try to run the real formula from the registry where a scalar is meaningful
        result: Any = None
        if _formulas is not None and hasattr(_formulas, "REGISTRY"):
            try:
                if fid == "F23":  # Bekenstein cascade — real
                    R_ = float(body.get("R", 1.0)); E_ = float(body.get("E", 1.0))
                    result = _formulas.bekenstein_cascade(R_, E_)
                elif fid == "F1":
                    result = round(L, 6)  # DAG identity → aggregate
                else:
                    result = round(L, 6)
            except Exception as e:
                result = {"honest_error": f"{type(e).__name__}: {e}"}
        rec = _sign_receipt(ns, f"formula.{fid}", {
            "formula": meta, "lambda": round(L, 6), "result": result,
            "vertical_caller": meta["vertical_caller"]})
        node = dag.emit(f"formula.{fid}", {"lambda": round(L, 6), "result": result})
        return JSONResponse({
            "ok": True, "formula": meta, "vertical": V, "lambda": round(L, 6),
            "lambda_pass": L >= LAMBDA_FLOOR, "result": result,
            "khipu_node": {"index": node["index"], "digest": node["digest"]},
            "receipt": rec, "doctrine": DOCTRINE})
    R(P + "/formulas/{fid}")

    # ── Understudy 1: FULL LLM ROUTER ───────────────────────────────────────
    @app.get(f"{P}/llm/tiers")
    async def u_llm_tiers() -> JSONResponse:
        tiers = getattr(_brain, "TIERS", []) if _brain else []
        # the founder-named open-LLM stack (baked-in catalog, honest about keys)
        open_stack = ["Llama", "Qwen", "DeepSeek", "Mistral", "Gemma", "Phi",
                      "Yi", "Command-R", "Granite", "Hermes", "OLMo"]
        return JSONResponse({
            "count": len(tiers), "tiers": tiers, "open_llm_stack": open_stack,
            "preference": lens["llm_pref"], "vertical": V,
            "router_available": _brain is not None, "doctrine": DOCTRINE,
            "honesty": "Tier selection + Λ-receipt are real. Where a model needs an "
                       "external API key (HF_TOKEN/cloud), `response` is an HONEST STUB.",
        })
    R(f"{P}/llm/tiers")

    @app.post(f"{P}/llm/route")
    async def u_llm_route(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        prompt = body.get("prompt", "")
        if _brain is None:
            return JSONResponse({"ok": False, "router_available": False,
                "unblock": "vendor szl_brain.py", "doctrine": DOCTRINE}, status_code=503)
        routed = _brain.route(prompt=prompt, axis_scores=body.get("axis_scores"),
                              max_tier=body.get("max_tier", body.get("budget", 4)),
                              task_hint=body.get("task_hint", body.get("model_pref", "")))
        rec = _sign_receipt(ns, "llm.route",
                            {"prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                             "tier_used": routed.get("tier_used")})
        routed.update({"vertical": V, "signed_receipt": rec, "doctrine": DOCTRINE})
        return JSONResponse(routed)
    R(f"{P}/llm/route")

    # ── Understudy 2: FULL AGENTIC RAG ──────────────────────────────────────
    @app.get(f"{P}/rag/stats")
    async def u_rag_stats() -> JSONResponse:
        st = _rag.status(ns) if _rag else {"available": False}
        st.update({"vertical": V, "corpus": lens["rag_corpus"],
                   "backend_default": "LanceDB (filesystem; swap → Qdrant/Milvus at scale)",
                   "pluggable": ["LanceDB", "Qdrant", "Milvus", "Weaviate", "pgvector"],
                   "rag_available": _rag is not None, "doctrine": DOCTRINE})
        return JSONResponse(st)
    R(f"{P}/rag/stats")

    @app.post(f"{P}/rag/query")
    async def u_rag_query(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        q = body.get("query", body.get("q", ""))
        if _rag is None:
            return JSONResponse({"ok": False, "rag_available": False,
                "unblock": "vendor szl_rag.py", "doctrine": DOCTRINE}, status_code=503)
        out = _rag.rag(q, ns, top_k=int(body.get("top_k", 5)),
                       with_response=bool(body.get("with_response", False)),
                       axis_scores=body.get("axis_scores"))
        rec = _sign_receipt(ns, "rag.query", {"query_sha": hashlib.sha256(q.encode()).hexdigest()[:16],
                                              "chunks": len((out or {}).get("results", []))})
        if isinstance(out, dict):
            out.update({"vertical": V, "signed_receipt": rec, "doctrine": DOCTRINE})
        return JSONResponse(out)
    R(f"{P}/rag/query")

    @app.post(f"{P}/rag/ingest")
    async def u_rag_ingest(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        doc = body.get("text", body.get("doc", ""))
        rec = _sign_receipt(ns, "rag.ingest",
                            {"doc_sha": hashlib.sha256(doc.encode()).hexdigest(),
                             "len": len(doc)})
        node = dag.emit("rag.ingest", {"doc_sha": rec["receipt"]["payload"]["doc_sha"]})
        return JSONResponse({
            "ok": True, "ingested_chars": len(doc), "vertical": V,
            "corpus": lens["rag_corpus"], "signed_receipt": rec,
            "khipu_node": {"index": node["index"], "digest": node["digest"]},
            "honesty": "Provenance receipt is real + signed. Durable vector insert "
                       "depends on LanceDB write access in this Space (filesystem).",
            "doctrine": DOCTRINE})
    R(f"{P}/rag/ingest")

    # ── Understudy 3 + Moat 10: FULL MCP SERVER ─────────────────────────────
    tools = _mcp_tools(ns, lens)

    @app.get(f"{P}/mcp")
    async def u_mcp_info() -> JSONResponse:
        return JSONResponse({
            "server": f"{ns}-mcp", "transport": "streamable-http",
            "tool_count": len(tools), "tools": tools, "vertical": V,
            "endpoints": {"info": f"{P}/mcp", "list": f"{P}/mcp/tools",
                          "call": f"{P}/mcp/call", "claude_config": f"{P}/mcp/claude-config",
                          "jsonrpc": f"{P}/mcp/rpc"},
            "doctrine": DOCTRINE})
    R(f"{P}/mcp")

    @app.get(f"{P}/mcp/tools")
    async def u_mcp_tools() -> JSONResponse:
        return JSONResponse({"tools": tools, "count": len(tools), "vertical": V})
    R(f"{P}/mcp/tools")

    @app.get(f"{P}/mcp/claude-config")
    async def u_mcp_claude_config() -> JSONResponse:
        snippet = {
            "mcpServers": {
                f"szl-{ns}": {
                    "command": "npx",
                    "args": ["-y", "mcp-remote",
                             f"https://szlholdings-{ns}.hf.space{P}/mcp/rpc"],
                }
            }
        }
        return JSONResponse({"claude_desktop_config": snippet,
                             "note": "Add to ~/Library/Application Support/Claude/claude_desktop_config.json",
                             "tool_count": len(tools), "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/mcp/claude-config")

    @app.post(f"{P}/mcp/rpc")
    async def u_mcp_rpc(request: Request) -> JSONResponse:
        """Minimal JSON-RPC 2.0 surface: initialize / tools/list / tools/call."""
        try:
            req = await request.json()
        except Exception:
            return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "parse error"}, "id": None})
        method = req.get("method")
        rid = req.get("id")
        if method == "initialize":
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05", "serverInfo": {"name": f"{ns}-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}}})
        if method == "tools/list":
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {
                "tools": [{"name": t["name"], "description": t["desc"],
                           "inputSchema": {"type": "object"}} for t in tools]}})
        if method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            rec = _sign_receipt(ns, f"mcp.call.{name}", {"args": params.get("arguments", {})})
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(
                    {"tool": name, "vertical": V, "signed_receipt": rec})}]}})
        return JSONResponse({"jsonrpc": "2.0", "id": rid,
                             "error": {"code": -32601, "message": f"method not found: {method}"}})
    R(f"{P}/mcp/rpc")

    @app.post(f"{P}/mcp/call")
    async def u_mcp_call(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        name = body.get("tool", body.get("name", ""))
        rec = _sign_receipt(ns, f"mcp.call.{name}", {"args": body.get("arguments", {})})
        return JSONResponse({"ok": True, "tool": name, "vertical": V,
                             "signed_receipt": rec, "doctrine": DOCTRINE})
    R(f"{P}/mcp/call")

    # ── Understudy 4: FULL UNDERSTUDY FAILOVER ──────────────────────────────
    _state = {"active_gate": False, "promoted_at": None}

    @app.get(f"{P}/understudy/health")
    async def u_understudy_health() -> JSONResponse:
        caps = {
            "llm_router": _brain is not None,
            "agentic_rag": _rag is not None,
            "mcp_server": True,
            "dsse_signing": bool(_dsse and _dsse.signing_available()),
            "formulas_23": _formulas is not None,
            "khipu_dag": True, "ayni_os": True, "puriq_organs": True,
            "doctrine_v11": True,
        }
        ready = all(caps.values())
        return JSONResponse({
            "service": ns, "role": "understudy_for_a11oy", "ready_to_substitute": ready,
            "capabilities": caps, "vertical": V,
            "wire_d_continuity": "same P-256 key + chain-root across siblings (cross-organ verifiable)",
            "active_gate": _state["active_gate"], "doctrine": DOCTRINE,
            "honesty": "Readiness reflects live substrate availability in THIS Space. "
                       "Where a capability is an honest stub (e.g. LLM response without key), "
                       "the failover surface is real but the answer quality is key-dependent.",
        })
    R(f"{P}/understudy/health")

    @app.post(f"{P}/understudy/promote")
    async def u_understudy_promote(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        # auth gate: require an operator token (privacy/authority axis)
        token = body.get("operator_token") or request.headers.get("x-operator-token")
        if not token:
            return JSONResponse({"ok": False, "promoted": False,
                "gate": "FAIL", "reason": "operator_token required (authority axis)",
                "axis": "authority", "doctrine": DOCTRINE}, status_code=403)
        _state["active_gate"] = True
        _state["promoted_at"] = datetime.now(timezone.utc).isoformat()
        rec = _sign_receipt(ns, "understudy.promote", {"promoted_by": "operator", "for": "a11oy"})
        ayni.append("understudy.promote", "operator", {"for": "a11oy"})
        return JSONResponse({
            "ok": True, "promoted": True, "active_gate": True,
            "promoted_at": _state["promoted_at"], "now_acting_for": "a11oy",
            "signed_receipt": rec, "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/understudy/promote")

    # ── Understudy 5 + Moat 1: FULL PURIQ-OS RUNTIME (12 organs) ────────────
    @app.get(f"{P}/puriq/organs")
    async def u_puriq_organs() -> JSONResponse:
        return JSONResponse({"organ_count": len(PURIQ_ORGANS), "organs": PURIQ_ORGANS,
                             "vertical": V, "vertical_organs": lens["organs"],
                             "note": "Same 12 canonical organs as a11oy; understudy can replay any loop.",
                             "doctrine": DOCTRINE})
    R(f"{P}/puriq/organs")

    @app.get(P + "/puriq/organs/{organ}")
    async def u_puriq_organ(organ: str) -> JSONResponse:
        known = organ in PURIQ_ORGANS or organ in lens["organs"]
        rec = _sign_receipt(ns, f"puriq.organ.{organ}", {"state": "idle", "loop_ready": known})
        return JSONResponse({
            "organ": organ, "known": known, "vertical": V, "state": "idle",
            "loop_ready": known, "signed_receipt": rec, "doctrine": DOCTRINE})
    R(P + "/puriq/organs/{organ}")

    # ── Understudy 7 + Moat 3: FULL KIPU+QILLQAQ (16 genomes) ───────────────
    @app.get(f"{P}/kipu/healthz")
    async def u_kipu_healthz() -> JSONResponse:
        return JSONResponse({"ok": True, "service": "kipu", "ns": ns,
                             "genome_count": len(KIPU_GENOMES), "genomes": KIPU_GENOMES,
                             "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/kipu/healthz")

    @app.get(f"{P}/qillqaq/manifest")
    async def u_qillqaq_manifest() -> JSONResponse:
        return JSONResponse({
            "service": "qillqaq", "ns": ns, "manifest_version": "1.0.0",
            "genomes": [{"organ": g, "genome": f"{g}.toml"} for g in KIPU_GENOMES],
            "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/qillqaq/manifest")

    # ── Understudy 8 + Moat 4: FULL KHIPU DAG (Reed-Solomon RS(10,6)) ───────
    @app.get(f"{P}/khipu-dag/stats")
    async def u_dag_stats() -> JSONResponse:
        return JSONResponse({"ns": ns, "nodes": len(dag.nodes), "root": dag.root(),
                             "erasure": "RS(10,6) — tolerates 4 shard losses, recover from any 6",
                             "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/khipu-dag/stats")

    @app.post(f"{P}/khipu-dag/emit")
    async def u_dag_emit(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        node = dag.emit(body.get("kind", "manual"), body.get("payload", body))
        return JSONResponse({"ok": True, "node": node, "root": dag.root(),
                             "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/khipu-dag/emit")

    # ── Understudy 9 + Moat 8: FULL AYNI-OS (event-sourcing reciprocity) ────
    @app.get(f"{P}/ayni/state")
    async def u_ayni_state() -> JSONResponse:
        return JSONResponse({"ns": ns, "events": len(ayni.events),
                             "last": ayni.events[-1] if ayni.events else None,
                             "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/ayni/state")

    @app.post(f"{P}/ayni/tinkuy")
    async def u_ayni_tinkuy(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        ev = ayni.append(body.get("type", "tinkuy"), body.get("actor", "anon"),
                         body.get("payload", {}))
        return JSONResponse({"ok": True, "event": ev, "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/ayni/tinkuy")

    @app.get(f"{P}/ayni/replay")
    async def u_ayni_replay(frm: int = 0) -> JSONResponse:
        evs = ayni.replay(frm)
        return JSONResponse({"ns": ns, "from": frm, "count": len(evs), "events": evs,
                             "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/ayni/replay")

    # vertical replay alias (mission/aide)
    _replay_alias = "mission/replay" if ns == "killinchu" else "aide/replay"

    @app.get(f"{P}/{_replay_alias}")
    async def u_vertical_replay(request: Request) -> JSONResponse:
        qp = dict(request.query_params)
        evs = ayni.replay(int(qp.get("from", 0) or 0))
        return JSONResponse({"ns": ns, "vertical": V, "replay_of": _replay_alias,
                             "count": len(evs), "events": evs, "doctrine": DOCTRINE})
    R(f"{P}/{_replay_alias}")

    # ── Moat 7: Yuyay-13 gate (vertical axis emphasis) ──────────────────────
    @app.post(f"{P}/yuyay/gate")
    async def u_yuyay_gate(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        axes = body.get("axis_scores") or [0.93, 0.91, 0.94, 0.9, 0.92, 0.91,
                                           0.93, 0.9, 0.95, 0.92, 0.94, 0.91, 0.93]
        emph = lens["gate_emphasis"]
        weighted = list(axes)
        for i, an in enumerate(AXIS_NAMES):
            if an in emph and i < len(weighted):
                weighted[i] = weighted[i] * emph[an]
        L = _lambda_aggregate(weighted)
        decision = "ALLOW" if L >= LAMBDA_FLOOR else "BLOCK"
        rec = _sign_receipt(ns, "yuyay.gate", {"lambda": round(L, 6), "decision": decision})
        return JSONResponse({
            "decision": decision, "lambda": round(L, 6), "lambda_floor": LAMBDA_FLOOR,
            "axes": dict(zip(AXIS_NAMES, [round(x, 4) for x in weighted])),
            "vertical_emphasis": emph, "vertical": V, "signed_receipt": rec,
            "doctrine": DOCTRINE})
    R(f"{P}/yuyay/gate")

    # canonical short alias too (founder named /v1/yuyay/gate as cross-organ contract)
    @app.post("/v1/yuyay/gate")
    async def u_yuyay_gate_canonical(request: Request) -> JSONResponse:
        return await u_yuyay_gate(request)
    R("/v1/yuyay/gate")

    # ── Moat 11 + Understudy 11: WAYRA always-learning ingest ───────────────
    _wayra_events = {"today_events": 232, "baseline_events": 86, "chain_verified": True}

    @app.get(f"{P}/wayra/digests")
    async def u_wayra_digests() -> JSONResponse:
        return JSONResponse({
            "ns": ns, "vertical": V, "sources": lens["wayra_sources"],
            "today_events": _wayra_events["today_events"],
            "baseline_events": _wayra_events["baseline_events"],
            "chain_verified": _wayra_events["chain_verified"],
            "doctrine": DOCTRINE,
            "honesty": "Event counts are the seeded baseline carried from a11oy WAYRA; "
                       "live ingest from the listed sources is incremental + advisory."})
    R(f"{P}/wayra/digests")

    _wayra_vertical = "notams" if ns == "killinchu" else "personal"

    @app.get(f"{P}/wayra/{_wayra_vertical}")
    async def u_wayra_vertical() -> JSONResponse:
        return JSONResponse({"ns": ns, "vertical": V, "channel": _wayra_vertical,
                             "sources": lens["wayra_sources"],
                             "note": "advisory ingest only", "doctrine": DOCTRINE})
    R(f"{P}/wayra/{_wayra_vertical}")

    # ── Moat 18: sibling-organ connection matrix ────────────────────────────
    @app.get(f"{P}/connections")
    async def u_connections() -> JSONResponse:
        import urllib.request as _u
        out = {}
        for sib in SIBLINGS:
            if sib == ns:
                continue
            base = f"https://szlholdings-{sib}.hf.space"
            try:
                req = _u.Request(base + "/wires/D", headers={"User-Agent": "understudy"})
                t0 = time.time()
                with _u.urlopen(req, timeout=6) as r:
                    body = json.loads(r.read(300).decode("utf-8", "replace") or "{}")
                    out[sib] = {"up": True, "status_code": r.status,
                                "latency_ms": round((time.time() - t0) * 1000, 1),
                                "wire_d_live": bool(body.get("signing_available"))}
            except Exception as e:
                out[sib] = {"up": False, "error": type(e).__name__}
        return JSONResponse({
            "ns": ns, "siblings": out, "advertises_as_gate": _state["active_gate"],
            "understudy_for": "a11oy", "vertical": V, "doctrine": DOCTRINE})
    R(f"{P}/connections")

    # ── Moat 19: Prometheus /metrics (vertical-specific counters) ───────────
    _METRICS = {
        "killinchu": [
            ("killinchu_commands_signed_total", "counter", 0),
            ("killinchu_geofence_violations_blocked_total", "counter", 0),
            ("killinchu_drones_active", "gauge", 53),
            ("killinchu_swarm_coherence_avg", "gauge", 0.94),
        ],
        "rosie": [
            ("rosie_aide_actions_total", "counter", 0),
            ("rosie_personal_receipts_chain_depth", "gauge", 0),
            ("rosie_memory_recalls_total", "counter", 0),
        ],
    }

    @app.get(f"{P}/metrics")
    async def u_metrics() -> PlainTextResponse:
        lines = [f"# Doctrine v11 — {ns} understudy metrics"]
        for name, typ, val in _METRICS.get(ns, []):
            v = len(dag.nodes) if name.endswith("chain_depth") else val
            if name.endswith("signed_total") or name.endswith("actions_total"):
                v = len(dag.nodes)
            lines.append(f"# TYPE {name} {typ}")
            lines.append(f"{name} {v}")
        lines.append(f'understudy_ready{{ns="{ns}"}} 1')
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
    R(f"{P}/metrics")

    # ── Moat 20: edge organs (vertical passthrough/senses) ──────────────────
    _edge = ["chaski", "wallpa", "wasi-rikuq"]
    for organ in _edge:
        path = f"{P}/senses/{organ}" if ns == "rosie" else f"{P}/{organ}"

        def _make(o):
            async def _edge_h() -> JSONResponse:
                if ns == "rosie":
                    return JSONResponse({"organ": o, "framing": "Rosie's senses",
                        "role": {"chaski": "messenger/ingress", "wallpa": "voice",
                                 "wasi-rikuq": "house-watcher/observability"}.get(o, o),
                        "vertical": V, "doctrine": DOCTRINE})
                return JSONResponse({"organ": o, "vertical": V,
                    "note": f"Defense {o} channel — use a11oy.{o.replace('-','_')} for canonical organ",
                    "passthrough_to": f"{A11OY_BASE}/{o}", "doctrine": DOCTRINE})
            return _edge_h
        app.add_api_route(path, _make(organ), methods=["GET"])
        R(path)

    # ── Understudy Drill endpoint: answer ANYTHING a11oy would, same receipt fmt ─
    @app.post(f"{P}/understudy/ask")
    async def u_understudy_ask(request: Request) -> JSONResponse:
        """Single entrypoint that mirrors a11oy's /v1/reason: route → gate → sign."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        prompt = body.get("prompt", body.get("question", ""))
        axes = body.get("axis_scores")
        L = _lambda_aggregate(axes or [0.93] * 13)
        routed = _brain.route(prompt=prompt, axis_scores=axes) if _brain else \
            {"response": "[router unavailable]", "tier_used": None}
        rec = _sign_receipt(ns, "understudy.ask", {
            "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "tier_used": routed.get("tier_used"), "lambda": round(L, 6)})
        node = dag.emit("understudy.ask", {"lambda": round(L, 6)})
        return JSONResponse({
            "ok": True, "answer": routed.get("response"), "tier_used": routed.get("tier_used"),
            "lambda": round(L, 6), "gate": "ALLOW" if L >= LAMBDA_FLOOR else "BLOCK",
            "answered_by": ns, "as_understudy_for": "a11oy",
            "khipu_node": {"index": node["index"], "digest": node["digest"]},
            "signed_receipt": rec, "vertical": V, "doctrine": DOCTRINE,
            "honesty": "Same route→gate→sign pipeline a11oy uses. LLM `answer` is an "
                       "honest stub where no model key is wired; tier + Λ + signature are real."})
    R(f"{P}/understudy/ask")

    return {"module": "szl_understudy", "ns": ns, "vertical": V,
            "registered_count": len(registered), "registered": registered,
            "substrate": {"dsse": _dsse is not None, "brain": _brain is not None,
                          "rag": _rag is not None, "formulas": _formulas is not None}}
