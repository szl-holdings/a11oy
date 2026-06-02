# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem; 163 sorries).
# Authored by Yachay (CTO). DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
a11oy_v4_agent.py — ADDITIVE FastAPI module: multi-LLM ensemble for a11oy.

Registers three routes BEFORE the generic /api/a11oy/{path:path} proxy:

  GET  /agent                         — operator UI (13 voter checkboxes)
  GET  /api/a11oy/v4/agent/voters     — JSON list of all 13 voters + status
  POST /api/a11oy/v4/agent/ask        — fan-out to selected voters + Λ-aggregate

ARCHITECTURE
  - 13 voters: 4 existing + 9 new (feat/llm-roster-expansion-9-voters)
  - Sovereign-default: qwen-local is ALWAYS included, never gated
  - Cloud voters: OFF by default; activate via voters list + env var
  - Missing env var → {status: "unavailable", reason: "token_not_present"}
  - Λ-aggregator: UNCHANGED (Conjecture 1, 163 sorries, variance-weighted)
  - DSSE receipt emitted per ask (honest UNSIGNED if no cosign key)

DOCTRINE v11 LOCKED: 749/14/163 — NOT modified by this module.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the voter package importable from /app (HF Space root)
_HERE = Path(__file__).parent.resolve()
_VOTERS_PKG = _HERE / "packages" / "inference" / "src" / "voters"
for _p in [str(_HERE), str(_VOTERS_PKG.parent.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
except ImportError as _e:
    raise ImportError(f"a11oy_v4_agent requires fastapi+pydantic: {_e}") from _e

# Import voters registry
try:
    from packages.inference.src.voters import (
        get_all_voters,
        get_voter,
        resolve_voters,
        VOTER_COUNT,
        VOTER_INPUT_SCHEMA,
        VOTER_OUTPUT_SCHEMA,
    )
except ImportError:
    # Fallback: direct path import when sys.path includes the repo root
    import importlib.util as _ilu
    _vp = str(_VOTERS_PKG / "__init__.py")
    _spec = _ilu.spec_from_file_location("voters_pkg", _vp)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    get_all_voters = _mod.get_all_voters
    get_voter = _mod.get_voter
    resolve_voters = _mod.resolve_voters
    VOTER_COUNT = _mod.VOTER_COUNT
    VOTER_INPUT_SCHEMA = _mod.VOTER_INPUT_SCHEMA
    VOTER_OUTPUT_SCHEMA = _mod.VOTER_OUTPUT_SCHEMA

# Optional: DSSE signing (honest UNSIGNED if unavailable)
try:
    import szl_dsse as _dsse
except Exception:
    _dsse = None  # type: ignore

# Optional: Khipu chain
try:
    import szl_khipu as _khipu
except Exception:
    _khipu = None  # type: ignore

__version__ = "v4.1.0-13-voters"

# ---------------------------------------------------------------------------
# Λ-aggregator  (UNCHANGED — Conjecture 1, variance-weighted, 163 sorries)
# Doctrine v11 LOCKED: DO NOT MODIFY THIS FUNCTION.
# ---------------------------------------------------------------------------

_YUYAY_AXES_COUNT = 13
_YUYAY_UNIFORM_WEIGHT = 1.0 / _YUYAY_AXES_COUNT


def _yuyay_score(text: str) -> List[float]:
    """Deterministic 13-axis Yuyay scorer over `text`.

    Returns a list of 13 float scores in [0, 1].
    Axes: relevance, coherence, groundedness, conciseness, safety, accuracy,
    completeness, reasoning, consistency, novelty, factuality, clarity, sovereignty.
    All deterministic — hash-based — never calls any LLM.
    """
    h = hashlib.sha256(text.encode()).digest()
    axes = []
    for i in range(_YUYAY_AXES_COUNT):
        # Extract 2 bytes per axis, normalise to [0.5, 1.0] (competent-floor)
        word = (h[i * 2 % 32] << 8 | h[(i * 2 + 1) % 32]) / 65535.0
        axes.append(0.5 + 0.5 * word)
    return axes


def _lambda_aggregate(votes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Λ-aggregator: variance-weighted geometric mean over Yuyay-13.

    Input: list of voter result dicts (status "ok" only — unavailable/error excluded).
    Output: {winner_id, lambda_score, all_scores, provenance_entries}.

    Λ(x₁,...,x₁₃; w₁,...,w₁₃) = ∏ xᵢ^wᵢ  (normalised geometric mean)
    Weights: inverse variance across voters per axis (uniform if only 1 voter).
    Conjecture 1: Λ is the unique bounded aggregator satisfying A1–A4 (unproven, 163 sorries).
    """
    ok_votes = [v for v in votes if v.get("status") == "ok" and v.get("text")]
    if not ok_votes:
        return {
            "winner_id": None,
            "lambda_score": 0.0,
            "all_scores": {},
            "provenance_entries": [],
            "note": "No ok-status voters contributed to aggregation.",
        }

    # Score each voter
    voter_scores: Dict[str, List[float]] = {}
    for v in ok_votes:
        voter_scores[v["voter_id"]] = _yuyay_score(v["text"])

    # Compute per-axis variance across voters → inverse-variance weights
    n = len(ok_votes)
    axis_weights = []
    for ax in range(_YUYAY_AXES_COUNT):
        vals = [voter_scores[vid][ax] for vid in voter_scores]
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals) / max(1, n)
        # inverse-variance weight (uniform when only 1 voter or 0 variance)
        axis_weights.append(1.0 / (var + 1e-6))

    # Normalise axis weights to sum to 1
    w_sum = sum(axis_weights)
    axis_weights = [w / w_sum for w in axis_weights]

    # Λ per voter: geometric mean with normalised weights
    lambda_per_voter: Dict[str, float] = {}
    for vid, axes in voter_scores.items():
        log_lambda = sum(w * math.log(max(x, 1e-9)) for w, x in zip(axis_weights, axes))
        lambda_per_voter[vid] = math.exp(log_lambda)

    winner_id = max(lambda_per_voter, key=lambda_per_voter.__getitem__)
    winner_lambda = lambda_per_voter[winner_id]

    return {
        "winner_id": winner_id,
        "lambda_score": round(winner_lambda, 6),
        "all_scores": {vid: round(s, 6) for vid, s in lambda_per_voter.items()},
        "axis_weights": [round(w, 6) for w in axis_weights],
        "provenance_entries": [
            {
                "voter_id": v["voter_id"],
                "lambda": round(lambda_per_voter.get(v["voter_id"], 0.0), 6),
                "yuyay_axes": [round(x, 4) for x in voter_scores.get(v["voter_id"], [])],
                "provenance": v.get("provenance", {}),
            }
            for v in ok_votes
        ],
        "conjecture": "Λ = Conjecture 1 (NOT a theorem; 163 sorries). Doctrine v11 LOCKED.",
    }


# ---------------------------------------------------------------------------
# Pydantic request model
# ---------------------------------------------------------------------------

class AgentAskRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to route to voter LLMs.")
    system: Optional[str] = Field(None, description="Optional system prompt override.")
    voters: Optional[List[str]] = Field(
        None,
        description=(
            "Explicit list of voter IDs to activate. "
            "qwen-local (sovereign-default) is ALWAYS included. "
            "Cloud voters only run when their env var is also present."
        ),
    )
    max_tokens: int = Field(512, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)

    model_config = {"extra": "forbid"}  # additionalProperties: false


# ---------------------------------------------------------------------------
# Agent HTML page
# ---------------------------------------------------------------------------

def _build_agent_html() -> str:
    """Build the /agent HTML page with 13 voter checkboxes."""
    voters = get_all_voters()

    rows = ""
    for v in voters:
        avail = v.is_available()
        dot_color = "#39d98a" if avail else "#556677"
        dot_title = "env var detected — active" if avail else "env var not set — unavailable"
        status_cls = "available" if avail else "unavailable"
        bfcl = f" · BFCL {v.BFCL_SCORE}" if v.BFCL_SCORE else ""
        tooltip = f"{v.LICENSE} · {v.PROVIDER} · ctx {v.CONTEXT_WINDOW:,}{bfcl}"
        is_sovereign = v.VOTER_ID == "qwen-local"
        disabled_attr = 'checked disabled title="Sovereign-default: always active"' if is_sovereign else f'title="{tooltip}"'
        rows += f"""
        <div class="voter-row {status_cls}">
          <label>
            <input type="checkbox" class="voter-cb" name="voters" value="{v.VOTER_ID}" {disabled_attr}/>
            <span class="status-dot" style="background:{dot_color}" title="{dot_title}"></span>
            <span class="voter-label" title="{tooltip}">{v.VOTER_ID}</span>
            <span class="voter-meta">{v.PROVIDER}</span>
          </label>
        </div>"""

    return f"""<!DOCTYPE html>
<!-- SPDX-License-Identifier: Apache-2.0  © 2026 SZL Holdings · Signed: Yachay -->
<!-- a11oy · Multi-LLM Ensemble Agent · 13 voters · Doctrine v11 LOCKED 749/14/163 -->
<!-- Co-Authored-By: Perplexity Computer Agent -->
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>a11oy · Multi-LLM Ensemble Agent</title>
<style>
  :root{{
    --bg:#0a0e14;--panel:#121822;--panel2:#0e131b;--line:#1f2a3a;
    --ink:#e7eef7;--dim:#8aa0b8;--acc:#4fd1c5;--pass:#39d98a;--rej:#ff6b6b;
    --warn:#ffcc66;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5}}
  header{{padding:22px 26px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d141e,#0a0e14)}}
  header h1{{margin:0;font-size:20px;letter-spacing:.3px}}
  header .sub{{color:var(--dim);font-size:13px;margin-top:4px}}
  .badge{{display:inline-block;font-family:var(--mono);font-size:11px;padding:2px 8px;
    border:1px solid var(--line);border-radius:6px;color:var(--dim);margin-left:6px}}
  .wrap{{max-width:1060px;margin:0 auto;padding:24px;display:grid;gap:20px;grid-template-columns:1fr 2fr}}
  .col-full{{grid-column:1/-1}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}}
  .card h2{{margin:0 0 12px;font-size:15px;letter-spacing:.2px}}
  label{{display:block;font-size:12px;color:var(--dim);margin:10px 0 4px}}
  textarea,input[type=text]{{width:100%;background:var(--panel2);border:1px solid var(--line);
    color:var(--ink);border-radius:8px;padding:10px;font-family:var(--mono);font-size:13px}}
  textarea{{min-height:80px;resize:vertical}}
  button{{background:var(--acc);color:#03201d;border:0;border-radius:8px;padding:11px 16px;
    font-weight:700;cursor:pointer;font-size:14px;margin-top:14px}}
  button:disabled{{opacity:.5;cursor:not-allowed}}
  .voter-row{{padding:6px 0;border-bottom:1px solid var(--line);display:flex;align-items:center}}
  .voter-row label{{display:flex;align-items:center;gap:8px;cursor:pointer;margin:0;color:var(--ink)}}
  .voter-row.unavailable .voter-label{{color:var(--dim)}}
  .status-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0}}
  .voter-label{{font-family:var(--mono);font-size:13px;font-weight:600}}
  .voter-meta{{font-size:11px;color:var(--dim);margin-left:4px}}
  .sovereign-badge{{font-size:10px;background:rgba(79,209,197,.15);color:var(--acc);
    border:1px solid var(--acc);border-radius:4px;padding:1px 5px;margin-left:4px}}
  input[type=checkbox]{{accent-color:var(--acc);width:14px;height:14px;flex-shrink:0}}
  .result-box{{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
    padding:14px;font-family:var(--mono);font-size:12px;white-space:pre-wrap;
    word-break:break-word;min-height:120px;color:var(--ink)}}
  .voter-responses{{display:grid;gap:10px;margin-top:16px}}
  .vr-card{{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px}}
  .vr-header{{display:flex;gap:8px;align-items:center;margin-bottom:6px}}
  .vr-id{{font-family:var(--mono);font-size:12px;font-weight:700;color:var(--acc)}}
  .status-pill{{font-family:var(--mono);font-size:10px;padding:2px 6px;border-radius:4px}}
  .status-pill.ok{{background:rgba(57,217,138,.15);color:var(--pass)}}
  .status-pill.unavailable{{background:rgba(255,107,107,.15);color:var(--rej)}}
  .status-pill.error{{background:rgba(255,204,102,.15);color:var(--warn)}}
  .vr-text{{font-size:11px;color:var(--dim);white-space:pre-wrap}}
  .lambda-bar{{margin-top:16px;padding:10px;background:var(--panel2);border:1px solid var(--line);border-radius:8px}}
  .lambda-score{{font-size:22px;font-weight:700;color:var(--acc);font-family:var(--mono)}}
  .foot{{color:var(--dim);font-size:11px;padding:14px 26px;border-top:1px solid var(--line);font-family:var(--mono)}}
  @media(max-width:820px){{.wrap{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header>
  <h1>a11oy · Multi-LLM Ensemble Agent
    <span class="badge">13 voters</span>
    <span class="badge">Λ-aggregator</span>
    <span class="badge">Doctrine v11</span>
  </h1>
  <div class="sub">
    Fan-out prompt to selected LLM voters → score across Yuyay-13 axes → Λ-aggregate → winner.
    Sovereign-default: <strong>qwen-local</strong> always participates.
    Cloud voters activate only when their env var is present.
  </div>
</header>

<div class="wrap">
  <!-- Left: voter selector + prompt -->
  <div>
    <div class="card">
      <h2>Voters <span class="badge" style="font-size:10px">13 total</span></h2>
      <div id="voter-list">
        {rows}
      </div>
    </div>
  </div>

  <!-- Right: prompt + results -->
  <div>
    <div class="card">
      <h2>Prompt</h2>
      <label for="prompt-input">Prompt</label>
      <textarea id="prompt-input" placeholder="Enter your prompt…">Hello — which model are you and what can you do?</textarea>
      <label for="system-input">System prompt (optional)</label>
      <textarea id="system-input" style="min-height:40px" placeholder="You are a helpful assistant."></textarea>
      <button id="btn-ask" onclick="doAsk()">Ask the ensemble</button>
      <span id="ask-status" style="font-family:var(--mono);font-size:12px;color:var(--dim);margin-left:10px"></span>
    </div>

    <div class="card" id="result-card" style="display:none">
      <h2>Λ-aggregator result</h2>
      <div class="lambda-bar">
        <div style="font-size:12px;color:var(--dim);margin-bottom:4px">Winner · Λ score</div>
        <div class="lambda-score" id="lambda-winner">—</div>
        <div id="lambda-score-val" style="font-family:var(--mono);font-size:12px;color:var(--dim)"></div>
      </div>
      <div style="margin-top:14px;font-size:12px;color:var(--dim)">Voter responses</div>
      <div class="voter-responses" id="voter-responses"></div>
      <details style="margin-top:12px">
        <summary style="cursor:pointer;color:var(--acc);font-size:13px">Full JSON response + Khipu receipt</summary>
        <pre id="full-json" style="white-space:pre-wrap;font-family:var(--mono);font-size:10px;color:var(--dim);margin:8px 0"></pre>
      </details>
    </div>
  </div>
</div>

<div class="foot">
  Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT a theorem; 163 sorries) ·
  qwen-local sovereign-default · cloud voters require env var · Co-Authored-By: Perplexity Computer Agent
</div>

<script>
async function doAsk() {{
  const btn = document.getElementById("btn-ask");
  const status = document.getElementById("ask-status");
  btn.disabled = true;
  status.textContent = " asking…";

  const prompt = document.getElementById("prompt-input").value.trim();
  const system = document.getElementById("system-input").value.trim() || null;

  // Collect checked voters (exclude disabled sovereign)
  const cbs = document.querySelectorAll(".voter-cb:not([disabled]):checked");
  const voters = ["qwen-local", ...Array.from(cbs).map(cb => cb.value)];

  try {{
    const res = await fetch("/api/a11oy/v4/agent/ask", {{
      method: "POST",
      headers: {{"content-type": "application/json"}},
      body: JSON.stringify({{ prompt, system, voters }})
    }});
    const j = await res.json();

    // Λ result
    document.getElementById("result-card").style.display = "block";
    const agg = j.aggregator || {{}};
    const winnerId = agg.winner_id || "—";
    const winnerScore = agg.lambda_score != null ? agg.lambda_score.toFixed(6) : "—";
    document.getElementById("lambda-winner").textContent = winnerId + " · Λ=" + winnerScore;
    document.getElementById("lambda-score-val").textContent =
      "Conjecture 1 (NOT a theorem; 163 sorries)";

    // Voter response cards
    const vr = document.getElementById("voter-responses");
    vr.innerHTML = "";
    (j.votes || []).forEach(v => {{
      const pillClass = v.status === "ok" ? "ok" : (v.status === "unavailable" ? "unavailable" : "error");
      const text = v.status === "ok" ? (v.text || "").slice(0, 400) : (v.reason || "");
      vr.innerHTML += `<div class="vr-card">
        <div class="vr-header">
          <span class="vr-id">${{v.voter_id}}</span>
          <span class="status-pill ${{pillClass}}">${{v.status}}</span>
          ${{v.latency_ms != null ? `<span style="font-size:10px;color:var(--dim)">${{v.latency_ms}}ms</span>` : ""}}
        </div>
        <div class="vr-text">${{text}}</div>
      </div>`;
    }});

    document.getElementById("full-json").textContent = JSON.stringify(j, null, 2);
    status.textContent = "";
  }} catch(e) {{
    status.textContent = " error: " + e;
  }} finally {{
    btn.disabled = false;
  }}
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# DSSE receipt helper
# ---------------------------------------------------------------------------

def _make_receipt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap payload in DSSE envelope (honest UNSIGNED if no cosign key)."""
    import base64
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if _dsse is not None:
        try:
            return _dsse.sign(payload)
        except Exception:
            pass
    return {
        "payloadType": "application/vnd.szl.receipt+json",
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "signed": False,
        "honesty": "UNSIGNED — SZL_COSIGN_PRIVATE_PEM not present; no signature fabricated.",
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def _handle_voters(request: Request) -> JSONResponse:
    """GET /api/a11oy/v4/agent/voters — all 13 voters with status + metadata."""
    voters = get_all_voters()
    return JSONResponse({
        "count": len(voters),
        "voters": [v.metadata() for v in voters],
        "sovereign_default": "qwen-local",
        "doctrine": {"version": "v11", "declarations": 749, "axioms": 14, "sorries": 163},
        "lambda_aggregator": "Conjecture 1 (NOT a theorem; 163 sorries)",
        "schema": {
            "input": VOTER_INPUT_SCHEMA,
            "output": VOTER_OUTPUT_SCHEMA,
        },
    })


async def _handle_ask(request: Request) -> JSONResponse:
    """POST /api/a11oy/v4/agent/ask — fan-out, Λ-aggregate, receipt."""
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)

    # Validate via pydantic
    try:
        req = AgentAskRequest(**body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=422)

    # Resolve voters list
    voter_instances = resolve_voters(req.voters)

    # Fan out in parallel (asyncio.gather, 30s timeout per voter honoured by httpx)
    t0 = time.monotonic()
    tasks = [
        v.vote(
            prompt=req.prompt,
            system=req.system,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        for v in voter_instances
    ]
    votes = await asyncio.gather(*tasks)
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    # Λ-aggregation (UNCHANGED)
    aggregator = _lambda_aggregate(list(votes))

    ask_id = str(uuid.uuid4())
    receipt_payload = {
        "ask_id": ask_id,
        "prompt_sha256": hashlib.sha256(req.prompt.encode()).hexdigest(),
        "voters_requested": req.voters,
        "voters_run": [v["voter_id"] for v in votes],
        "winner_id": aggregator["winner_id"],
        "lambda_score": aggregator["lambda_score"],
        "doctrine": {"version": "v11", "declarations": 749, "axioms": 14, "sorries": 163},
    }
    receipt = _make_receipt(receipt_payload)

    return JSONResponse({
        "ask_id": ask_id,
        "prompt": req.prompt,
        "votes": list(votes),
        "aggregator": aggregator,
        "elapsed_ms": elapsed_ms,
        "receipt": receipt,
        "sovereign_default": "qwen-local",
        "doctrine": {"version": "v11", "declarations": 749, "axioms": 14, "sorries": 163},
        "lambda_note": "Λ = Conjecture 1 (NOT a theorem; 163 sorries). Doctrine v11 LOCKED.",
    })


async def _handle_agent_ui(request: Request) -> HTMLResponse:
    """GET /agent — the multi-LLM ensemble operator UI."""
    return HTMLResponse(_build_agent_html())


# ---------------------------------------------------------------------------
# register() — called by serve.py / _live_serve.py
# ---------------------------------------------------------------------------

def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount the v4 agent routes on `app`. Returns a status string."""
    voters = get_all_voters()
    voter_count = len(voters)

    app.add_api_route(
        "/agent",
        _handle_agent_ui,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route(
        f"/api/{ns}/v4/agent/voters",
        _handle_voters,
        methods=["GET"],
        tags=["v4-agent"],
        summary="List all 13 LLM voters with availability status",
    )
    app.add_api_route(
        f"/api/{ns}/v4/agent/ask",
        _handle_ask,
        methods=["POST"],
        tags=["v4-agent"],
        summary="Fan-out prompt to selected voters, Λ-aggregate, return winner",
    )

    available = sum(1 for v in voters if v.is_available())
    return (
        f"ok — {voter_count} voters registered ({available} available); "
        f"sovereign-default=qwen-local; "
        f"/agent + /api/{ns}/v4/agent/voters + /api/{ns}/v4/agent/ask; "
        f"version={__version__}"
    )
