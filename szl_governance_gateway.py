# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   LLMRouter — ulab-uiuc/LLMRouter — MIT License — https://github.com/ulab-uiuc/LLMRouter
#   We adopt the multi-strategy ROUTING PATTERN (score candidate models per query,
#   pick the best by a policy) and EVOLVE it from a cost/quality library into a
#   sovereign "Governance Gateway": routing is decided by DATA SENSITIVITY first
#   (air-gapped vs cloud), then tier/cost — and EVERY route decision emits a
#   hash-chained Khipu receipt (signed-decision substrate). This is original code;
#   no LLMRouter source is copied. The library's interface, weights, or files are
#   NOT vendored here — only the pattern is re-implemented clean.
"""szl_governance_gateway — ADDITIVE governance routing tab + API for a11oy.

Endpoints (mounted before the SPA catch-all in serve.py):
  GET  /governance-gateway                         — premium operator tab (HTML, 0 CDN)
  GET  /api/a11oy/v1/governance/catalog            — model catalog (placement zone + tier + license)
  POST /api/a11oy/v1/governance/route              — route a request -> decision + Khipu receipt
  GET  /api/a11oy/v1/governance/receipts           — last N route-decision receipts (audit)
  GET  /api/a11oy/v1/governance/verify             — verify the receipt hash-chain

HONESTY: this is a real, deterministic decision ENGINE. It does NOT call any model;
it decides WHERE a request may run (air-gap vs cloud) and WHICH tier, then signs that
decision. Sensitivity classification is a transparent rule set (keyword + explicit
classification override). Λ = Conjecture 1. Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

import html as _html
import json
import re
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# ---------------------------------------------------------------------------
# Model catalog. `zone` is the load-bearing governance field:
#   AIRGAP  — open-weight, self-hostable, may process RESTRICTED/SECRET data offline
#   CLOUD   — hosted API, only eligible for PUBLIC/INTERNAL data
# Distilled from console/static/viz/router/models.js (this Space's own registry).
# ---------------------------------------------------------------------------
CATALOG: list[dict[str, Any]] = [
    # AIRGAP (open-weight, self-host) — eligible for ANY sensitivity
    {"id": "qwen2.5-coder-0.5b", "tier": "T0", "zone": "AIRGAP", "license": "GREEN",
     "weights": "Apache-2.0", "ctx": 32768, "note": "in-image GGUF (already shipped)"},
    {"id": "olmo-2-32b",        "tier": "T2", "zone": "AIRGAP", "license": "GREEN",
     "weights": "Apache-2.0", "ctx": 4096,  "note": "clean lineage, self-host"},
    {"id": "deepseek-v3",       "tier": "T2", "zone": "AIRGAP", "license": "GREEN",
     "weights": "MIT",        "ctx": 164000, "note": "self-host MoE"},
    {"id": "qwen3-8b",          "tier": "T1", "zone": "AIRGAP", "license": "GREEN",
     "weights": "Apache-2.0", "ctx": 128000, "note": "fast triage, self-host"},
    {"id": "codestral-25.01",   "tier": "T3", "zone": "AIRGAP", "license": "AMBER",
     "weights": "MNPL",       "ctx": 256000, "note": "code, self-host (non-prod license)"},
    # CLOUD (hosted) — PUBLIC / INTERNAL only
    {"id": "claude-sonnet-4-6", "tier": "T2", "zone": "CLOUD", "license": "GREEN",
     "weights": "hosted",     "ctx": 200000, "note": "default reasoning (hosted)"},
    {"id": "gemini-3-1-pro",    "tier": "T5", "zone": "CLOUD", "license": "GREEN",
     "weights": "hosted",     "ctx": 1000000, "note": "long-context research (hosted)"},
    {"id": "gpt-5-4",           "tier": "T4", "zone": "CLOUD", "license": "AMBER",
     "weights": "hosted",     "ctx": 256000, "note": "reasoning-heavy (hosted)"},
]

# Sensitivity lattice (lowest -> highest). Higher classes MUST stay in-airgap.
SENSITIVITY = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]
_SENS_RANK = {s: i for i, s in enumerate(SENSITIVITY)}
# At/above this rank the gateway forbids CLOUD egress (air-gap mandatory).
_AIRGAP_FLOOR = _SENS_RANK["RESTRICTED"]

# Transparent keyword classifier (auditable, no ML black box). Explicit caller
# classification always wins; this only RAISES the floor, never lowers it.
_SECRET_RX = re.compile(r"\b(classified|ts/sci|top.?secret|nofor[nm]|sci\b|codeword)\b", re.I)
_RESTRICTED_RX = re.compile(
    r"\b(troop|targeting|weapon|coordinates?|grid ref|patient|phi\b|ssn|"
    r"medical record|injector|maritime intel|drone tasking|rules of engagement|roe)\b", re.I)
_INTERNAL_RX = re.compile(r"\b(internal|proprietary|roadmap|unreleased|pre-?release|nda)\b", re.I)


def classify(text: str, declared: str | None = None) -> dict[str, Any]:
    """Return {class, rank, signals} — declared class is a FLOOR, never lowered."""
    text = text or ""
    signals: list[str] = []
    inferred = "PUBLIC"
    if _SECRET_RX.search(text):
        inferred = "SECRET"; signals.append("secret-keyword")
    elif _RESTRICTED_RX.search(text):
        inferred = "RESTRICTED"; signals.append("restricted-keyword")
    elif _INTERNAL_RX.search(text):
        inferred = "INTERNAL"; signals.append("internal-keyword")
    final = inferred
    if declared and declared.upper() in _SENS_RANK:
        if _SENS_RANK[declared.upper()] > _SENS_RANK[inferred]:
            final = declared.upper(); signals.append(f"declared-floor:{declared.upper()}")
        else:
            final = inferred; signals.append(f"declared:{declared.upper()}(<=inferred)")
    return {"class": final, "rank": _SENS_RANK[final], "signals": signals}


# Tier ordering for cost-aware tie-breaking (prefer the SMALLEST tier that clears
# the requested minimum — the LLMRouter cost-minimization pattern, governance-bound).
_TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5, "T6": 6}


def route(query: str, *, classification: str | None = None,
          min_tier: str = "T1", task: str = "reason") -> dict[str, Any]:
    """Decide a route. Returns the full, auditable decision dict (no receipt yet)."""
    cls = classify(query, classification)
    airgap_required = cls["rank"] >= _AIRGAP_FLOOR
    min_rank = _TIER_ORDER.get(min_tier.upper(), 1)

    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for m in CATALOG:
        reasons = []
        if airgap_required and m["zone"] != "AIRGAP":
            reasons.append("cloud-egress-forbidden@sensitivity")
        if _TIER_ORDER.get(m["tier"], 0) < min_rank:
            reasons.append(f"below-min-tier({min_tier})")
        if reasons:
            rejected.append({"id": m["id"], "zone": m["zone"], "why": reasons})
        else:
            eligible.append(m)

    # LLMRouter-style scoring (evolved): prefer GREEN license, then smallest
    # sufficient tier (cost), then largest context as tie-break. Deterministic.
    def _score(m: dict[str, Any]) -> tuple:
        lic = {"GREEN": 0, "AMBER": 1, "RED": 2}.get(m["license"], 3)
        return (lic, _TIER_ORDER.get(m["tier"], 9), -m["ctx"])

    eligible.sort(key=_score)
    chosen = eligible[0] if eligible else None

    decision = {
        "task": task,
        "min_tier": min_tier.upper(),
        "sensitivity": cls,
        "airgap_required": airgap_required,
        "chosen": chosen,
        "eligible_count": len(eligible),
        "rejected": rejected,
        "policy": "sensitivity-first → license(GREEN) → smallest-tier → max-ctx",
        "honest": None if chosen else "no eligible model — raise tier ceiling or add an AIRGAP model",
    }
    return decision


def _emit_receipt(decision: dict[str, Any]) -> dict[str, Any]:
    """Hash-chained Khipu receipt for this route decision (signed-decision substrate)."""
    try:
        import szl_khipu
        dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
        payload = {
            "sensitivity": decision["sensitivity"]["class"],
            "airgap_required": decision["airgap_required"],
            "chosen": (decision["chosen"] or {}).get("id"),
            "zone": (decision["chosen"] or {}).get("zone"),
            "min_tier": decision["min_tier"],
        }
        return dag.emit("route", payload)
    except Exception as e:  # honest: receipt unavailable, never faked
        return {"error": f"receipt-unavailable: {e}", "chain_verified": False}


def matrix_health(matrix: list[list[float]] | None = None) -> dict[str, Any]:
    """WAVE9 MA1 (Gershgorin) pre-flight: certify a trust-weight matrix is strictly
    diagonally dominant ⇒ non-degenerate (no zero-eigenvalue collapse) BEFORE the
    gateway aggregates trust across voters/models. A real pre-aggregation safety
    gate. Delegates to the proven-formulas module's real in-image check.

    EXPERIMENTAL · CI-green on lutar-lean main — NOT a LOCKED theorem.
    #print axioms ⟶ [propext, Classical.choice, Quot.sound]."""
    if matrix is None:
        # Default: trust-weight matrix across the AIRGAP voter pool (diag = self-
        # trust, off-diag = cross-influence) — strictly diagonally dominant.
        matrix = [[1.0, 0.2, 0.1, 0.0],
                  [0.15, 0.9, 0.1, 0.05],
                  [0.0, 0.1, 0.8, 0.2],
                  [0.05, 0.0, 0.15, 0.7]]
    try:
        import szl_wave910_proofs as _w910
        res = _w910.gershgorin_check(matrix)
    except Exception as e:  # honest: never fake a pass
        return {"ok": False, "error": f"matrix-health check unavailable: {e}"}
    res["experimental"] = "EXPERIMENTAL · CI-green on lutar-lean main (NOT locked)"
    res["role"] = "pre-aggregation governance gate (Wave9 MA1 Gershgorin)"
    return res


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/governance/matrix-health", include_in_schema=False)
    async def _matrix_health(matrix: str = "") -> JSONResponse:
        m = None
        if matrix.strip():
            try:
                m = [[float(x) for x in row.split(",") if x.strip()]
                     for row in matrix.split(";") if row.strip()]
            except Exception as e:
                return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return JSONResponse(matrix_health(m))

    @app.get(f"/api/{ns}/v1/governance/catalog", include_in_schema=False)
    async def _catalog() -> JSONResponse:
        airgap = [m for m in CATALOG if m["zone"] == "AIRGAP"]
        return JSONResponse({
            "doctrine": DOCTRINE,
            "sensitivity_lattice": SENSITIVITY,
            "airgap_floor": SENSITIVITY[_AIRGAP_FLOOR],
            "models": CATALOG,
            "airgap_models": len(airgap),
            "cloud_models": len(CATALOG) - len(airgap),
            "pattern_source": "ulab-uiuc/LLMRouter (MIT) — routing pattern, evolved to governance gateway",
        })

    @app.post(f"/api/{ns}/v1/governance/route", include_in_schema=False)
    async def _route(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        q = str(body.get("query", "") or "")
        decision = route(
            q,
            classification=body.get("classification"),
            min_tier=str(body.get("min_tier", "T1")),
            task=str(body.get("task", "reason")),
        )
        receipt = _emit_receipt(decision)
        return JSONResponse({"decision": decision, "receipt": receipt})

    @app.get(f"/api/{ns}/v1/governance/receipts", include_in_schema=False)
    async def _receipts() -> JSONResponse:
        try:
            import szl_khipu
            dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
            return JSONResponse({"depth": dag.depth(), "head": dag.head(),
                                 "receipts": dag.tail(20)})
        except Exception as e:
            return JSONResponse({"error": f"khipu-unavailable: {e}", "receipts": []})

    @app.get(f"/api/{ns}/v1/governance/verify", include_in_schema=False)
    async def _verify() -> JSONResponse:
        try:
            import szl_khipu
            dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
            return JSONResponse(dag.verify_chain())
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"khipu-unavailable: {e}"})

    @app.get("/governance-gateway", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return ("governance-gateway mounted: GET /governance-gateway + "
            f"catalog/route/receipts/verify under /api/{ns}/v1/governance/* "
            f"({len(CATALOG)} models, airgap-floor={SENSITIVITY[_AIRGAP_FLOOR]})")


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Governance Gateway</title>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--amber:#d29922;--red:#f85149;--line:#1e2a36;--airgap:#1f6feb;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0;letter-spacing:.3px}
.sub{color:var(--muted);margin:0 0 18px}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.amber{background:rgba(210,153,34,.15);color:var(--amber)}
.airgap{background:rgba(31,111,235,.18);color:#79b8ff}
.cloud{background:rgba(217,180,106,.15);color:var(--gold)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
label{font-size:13px;color:var(--muted);display:block;margin-bottom:4px}
input,select,textarea{width:100%;background:#0d141c;border:1px solid var(--line);
color:var(--ink);border-radius:8px;padding:9px 10px;font:inherit}
textarea{min-height:70px;resize:vertical}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:10px 18px;
font-weight:700;cursor:pointer}button:hover{filter:brightness(1.08)}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;
overflow:auto;font-size:12.5px;white-space:pre-wrap;word-break:break-word}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Governance Gateway <span class="pill airgap">CHAPAQ&nbsp;routing</span></h1>
<p class="sub">Sovereign route control: every request is classified by data sensitivity,
routed to an air-gapped or cloud model accordingly, and the decision is sealed in a
hash-chained Khipu receipt. Pattern adopted from <code>ulab-uiuc/LLMRouter</code> (MIT)
and evolved into a sensitivity-first governance gateway. 0&nbsp;CDN — air-gap ready.</p>

<div class="grid2">
<div class="card">
<h3 style="margin-top:0">Route a request</h3>
<label>Query / task description</label>
<textarea id="q" placeholder="e.g. Summarize the maritime targeting brief for the patrol sector…"></textarea>
<div class="row" style="margin-top:10px">
<div style="flex:1;min-width:140px"><label>Declared classification (floor)</label>
<select id="cls"><option value="">(auto-classify)</option>
<option>PUBLIC</option><option>INTERNAL</option><option>RESTRICTED</option><option>SECRET</option></select></div>
<div style="flex:1;min-width:120px"><label>Minimum tier</label>
<select id="mt"><option>T0</option><option selected>T1</option><option>T2</option>
<option>T3</option><option>T4</option><option>T5</option></select></div>
</div>
<div class="row" style="margin-top:12px"><button id="go">Route &amp; sign</button></div>
</div>

<div class="card">
<h3 style="margin-top:0">Decision &amp; receipt</h3>
<pre id="out">Run a route to see the signed decision…</pre>
</div>
</div>

<div class="card">
<div class="row" style="justify-content:space-between">
<h3 style="margin:0">Model catalog</h3>
<span class="pill green" id="zonecount">loading…</span>
</div>
<table id="cat"><thead><tr><th>Model</th><th>Zone</th><th>Tier</th><th>License</th>
<th>Weights</th><th>Ctx</th><th>Note</th></tr></thead><tbody></tbody></table>
</div>

<div class="card">
<div class="row" style="justify-content:space-between">
<h3 style="margin:0">Trust-matrix health pre-flight
<span class="pill airgap" style="background:rgba(138,111,214,.18);color:#b79fee">Wave9 MA1 · EXPERIMENTAL · CI-green on main</span></h3>
<button id="mh" style="padding:6px 12px;font-size:13px">Run pre-flight</button>
</div>
<p class="sub" style="margin:8px 0">Before aggregating trust across the voter pool, the
Gershgorin <b>strict diagonal-dominance</b> check certifies the trust-weight matrix is
non-degenerate (no zero-eigenvalue collapse) ⇒ safe to aggregate. PASS/FAIL + per-row
slack below. <code>#print axioms ⟶ [propext, Classical.choice, Quot.sound]</code> ·
<a href="/proven-formulas" style="color:#79b8ff">see all proven formulas (experimental) →</a></p>
<pre id="mhout">Run the pre-flight to certify the trust matrix…</pre>
</div>

<div class="card">
<div class="row" style="justify-content:space-between">
<h3 style="margin:0">Decision receipts (audit chain)</h3>
<button id="ref" style="padding:6px 12px;font-size:13px">Refresh + verify</button>
</div>
<pre id="rec">No receipts yet — route a request above.</pre>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: ulab-uiuc/LLMRouter (MIT), evolved · sovereign 0-CDN · receipts via Khipu hash-chain.</p>
</div>
<script>
const $=s=>document.querySelector(s);
async function loadCat(){
  const r=await fetch('/api/a11oy/v1/governance/catalog');const d=await r.json();
  const tb=$('#cat tbody');tb.innerHTML='';
  d.models.forEach(m=>{
    const zc=m.zone==='AIRGAP'?'airgap':'cloud';
    const lc=m.license==='GREEN'?'green':(m.license==='AMBER'?'amber':'amber');
    tb.insertAdjacentHTML('beforeend',
      `<tr><td><code>${m.id}</code></td><td><span class="pill ${zc}">${m.zone}</span></td>
       <td>${m.tier}</td><td><span class="pill ${lc}">${m.license}</span></td>
       <td>${m.weights}</td><td>${m.ctx.toLocaleString()}</td><td>${m.note}</td></tr>`);
  });
  $('#zonecount').textContent=d.airgap_models+' air-gap · '+d.cloud_models+' cloud · floor '+d.airgap_floor;
}
$('#go').addEventListener('click',async()=>{
  $('#out').textContent='routing…';
  const body={query:$('#q').value,classification:$('#cls').value||null,min_tier:$('#mt').value,task:'reason'};
  try{
    const r=await fetch('/api/a11oy/v1/governance/route',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    const dec=d.decision;const ch=dec.chosen;
    let head='SENSITIVITY: '+dec.sensitivity.class+'  ('+dec.sensitivity.signals.join(', ')+')\\n';
    head+='AIR-GAP REQUIRED: '+dec.airgap_required+'\\n';
    head+='CHOSEN: '+(ch?ch.id+'  ['+ch.zone+' · '+ch.tier+' · '+ch.license+']':'(none — '+dec.honest+')')+'\\n';
    head+='RECEIPT: seq#'+(d.receipt.seq!==undefined?d.receipt.seq:'?')+'  digest '+(d.receipt.digest||'n/a').slice(0,16)+'…\\n\\n';
    $('#out').textContent=head+JSON.stringify(d,null,2);
    loadRec();
  }catch(e){$('#out').textContent='error: '+e;}
});
async function loadRec(){
  try{
    const r=await fetch('/api/a11oy/v1/governance/receipts');const d=await r.json();
    const v=await(await fetch('/api/a11oy/v1/governance/verify')).json();
    $('#rec').textContent='chain depth='+d.depth+'  verified='+v.ok+'  head='+(d.head||'').slice(0,20)+'…\\n\\n'
      +JSON.stringify(d.receipts.slice(-6),null,2);
  }catch(e){$('#rec').textContent='error: '+e;}
}
$('#ref').addEventListener('click',loadRec);
async function loadMH(){
  $('#mhout').textContent='running Gershgorin pre-flight…';
  try{
    const r=await fetch('/api/a11oy/v1/governance/matrix-health');const d=await r.json();
    let head='VERDICT: '+(d.verdict||'?')+'\\n';
    head+='strictly diagonally dominant: '+d.strictly_diagonally_dominant+'  ·  nonsingular certified: '+d.nonsingular_certified+'\\n';
    head+='min slack: '+d.min_slack+'  ·  '+(d.experimental||'')+'\\n\\n';
    $('#mhout').textContent=head+JSON.stringify(d.rows,null,2);
  }catch(e){$('#mhout').textContent='error: '+e;}
}
$('#mh').addEventListener('click',loadMH);
loadCat();
</script>
</body></html>"""
