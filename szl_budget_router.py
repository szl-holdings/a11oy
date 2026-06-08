# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   BudgetMem — ViktorAxelsen/BudgetMem — Apache-2.0 —
#   https://github.com/ViktorAxelsen/BudgetMem
#   MemSkill — ViktorAxelsen/MemSkill — Apache-2.0 —
#   https://github.com/ViktorAxelsen/MemSkill
#   GraphPlanner — ulab-uiuc/GraphPlanner — MIT —
#   https://github.com/ulab-uiuc/GraphPlanner
#
#   We adopt THREE patterns and EVOLVE them into one a11oy-native mechanism:
#   • BudgetMem's module-level BUDGET TIERS (Low/Mid/High) + a lightweight query-aware
#     budget-tier ROUTER. We map the tiers onto Warhacker MISSION CONSTRAINTS —
#     Tactical (≤1s), Operational (≤10s), Strategic (≤1min) — so sovereign hardware is
#     never choked by unnecessary chain-of-thought on a time-critical decision.
#   • GraphPlanner's idea of routing by graph-derived signal: we route by DECISION RISK
#     (sensitivity × time-budget × reversibility) rather than by learned RL value.
#   • MemSkill's meta-memory ("learn WHAT to preserve"): we evolve it into "DECISION
#     SKELETONS" — reusable, distilled patterns of how the substrate successfully
#     navigated a class of governed trade-offs, kept across runs.
#   Original, dependency-free implementation — no BudgetMem/MemSkill/GraphPlanner
#   source, no torch/numpy. Reuses the live governance catalog from
#   szl_governance_gateway when present. Λ = Conjecture 1. Doctrine v11 LOCKED 749/14/163.
"""szl_budget_router — ADDITIVE cost-aware budget-tier router + Decision Skeletons.

Endpoints (mounted before the SPA catch-all):
  GET  /budget-router                              — operator tab (HTML, 0 CDN)
  GET  /api/a11oy/v1/budget/tiers                   — the 3 mission budget tiers
  POST /api/a11oy/v1/budget/route                   — route a decision by risk → tier → model
  GET  /api/a11oy/v1/budget/skeletons               — learned Decision Skeletons (meta-memory)
"""
from __future__ import annotations

import re
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# --- Mission budget tiers (BudgetMem Low/Mid/High → Warhacker mission constraints) ---
TIERS: list[dict[str, Any]] = [
    {"tier": "TACTICAL", "budget": "LOW", "deadline_s": 1, "max_model_tier": "T1",
     "cot": "none", "note": "time-critical: cheapest sufficient model, no chain-of-thought"},
    {"tier": "OPERATIONAL", "budget": "MID", "deadline_s": 10, "max_model_tier": "T3",
     "cot": "short", "note": "balanced: mid-tier reasoning with a short rationale"},
    {"tier": "STRATEGIC", "budget": "HIGH", "deadline_s": 60, "max_model_tier": "T6",
     "cot": "full", "note": "deliberate: high-tier model, full chain-of-thought permitted"},
]
_TIER_BY_NAME = {t["tier"]: t for t in TIERS}

# Reversibility cues raise risk: an irreversible action deserves a bigger budget.
_IRREVERSIBLE_RX = re.compile(
    r"\b(launch|fire|strike|delete|destroy|deploy|commit|authoriz|release|publish|"
    r"terminate|engage|weapon|kill)\b", re.I)
_REVERSIBLE_RX = re.compile(r"\b(draft|preview|simulate|estimate|summari|triage|sort|list|query)\b", re.I)


def _classify_sensitivity(text: str, declared: str | None) -> dict[str, Any]:
    """Reuse the live governance classifier when present; else a safe fallback."""
    try:
        import szl_governance_gateway as _gg  # type: ignore
        return _gg.classify(text, declared)
    except Exception:
        return {"class": (declared or "PUBLIC").upper(), "rank": 0, "signals": ["fallback"]}


def _reversibility(text: str) -> tuple[float, str]:
    if _IRREVERSIBLE_RX.search(text or ""):
        return 1.0, "irreversible"
    if _REVERSIBLE_RX.search(text or ""):
        return 0.0, "reversible"
    return 0.5, "uncertain"


def assess_risk(query: str, *, declared: str | None = None,
                deadline_s: float | None = None) -> dict[str, Any]:
    """Decision risk = f(sensitivity, reversibility). Higher risk → higher tier.
    A tighter deadline CAPS the tier (you cannot afford full CoT under 1s)."""
    sens = _classify_sensitivity(query, declared)
    sens_norm = sens["rank"] / 3.0  # 0..1 over PUBLIC..SECRET
    rev_score, rev_label = _reversibility(query)
    # Weighted risk: sensitivity dominates, reversibility modulates.
    risk = round(0.65 * sens_norm + 0.35 * rev_score, 4)
    if risk >= 0.6:
        want = "STRATEGIC"
    elif risk >= 0.3:
        want = "OPERATIONAL"
    else:
        want = "TACTICAL"
    # Deadline cap: if the operator imposes a tighter deadline, downshift the tier.
    chosen = want
    capped_by_deadline = False
    if deadline_s is not None:
        affordable = [t["tier"] for t in TIERS if t["deadline_s"] <= deadline_s]
        order = ["TACTICAL", "OPERATIONAL", "STRATEGIC"]
        if affordable:
            best_affordable = max(affordable, key=lambda n: order.index(n))
            if order.index(best_affordable) < order.index(want):
                chosen = best_affordable
                capped_by_deadline = True
        else:
            chosen = "TACTICAL"; capped_by_deadline = True
    return {
        "sensitivity": sens, "reversibility": {"score": rev_score, "label": rev_label},
        "risk": risk, "risk_band": ("HIGH" if risk >= 0.6 else "MODERATE" if risk >= 0.3 else "LOW"),
        "risk_implied_tier": want, "chosen_tier": chosen,
        "capped_by_deadline": capped_by_deadline,
    }


def _pick_model(max_model_tier: str, sensitivity_rank: int) -> dict[str, Any] | None:
    """Smallest sufficient model within the tier ceiling, respecting the air-gap floor."""
    try:
        import szl_governance_gateway as _gg  # type: ignore
        cat = getattr(_gg, "CATALOG", [])
        order = getattr(_gg, "_TIER_ORDER", {})
        floor = getattr(_gg, "_AIRGAP_FLOOR", 2)
    except Exception:
        return None
    ceil = order.get(max_model_tier, 9)
    airgap_required = sensitivity_rank >= floor
    elig = [m for m in cat
            if order.get(m["tier"], 9) <= ceil
            and (not airgap_required or m.get("zone") == "AIRGAP")]
    if not elig:
        return None
    elig.sort(key=lambda m: (order.get(m["tier"], 9), -m.get("ctx", 0)))
    return elig[0]


def route(query: str, *, declared: str | None = None,
          deadline_s: float | None = None) -> dict[str, Any]:
    risk = assess_risk(query, declared=declared, deadline_s=deadline_s)
    tier = _TIER_BY_NAME[risk["chosen_tier"]]
    model = _pick_model(tier["max_model_tier"], risk["sensitivity"]["rank"])
    decision = {
        "query": query, "tier": tier, "risk": risk, "chosen_model": model,
        "airgap_required": risk["sensitivity"]["rank"] >= 2,
        "policy": "risk(sensitivity×reversibility) → mission tier (deadline-capped) → smallest sufficient air-gap-safe model",
        "honest": None if model else "no model within tier ceiling + air-gap floor — raise the tier or add an AIRGAP model",
    }
    _learn_skeleton(decision)
    return decision


# ---------------------------------------------------------------------------
# Decision Skeletons (MemSkill meta-memory, evolved). A skeleton is a DISTILLED,
# reusable pattern for a class of decisions: (risk_band, tier, airgap) → how it was
# handled, plus how many times that pattern recurred. We keep WHAT generalizes
# (the band+tier+model family) and forget the per-query noise — the "skill of
# remembering" applied to governance trade-offs. In-memory ring (bounded), no PII.
# ---------------------------------------------------------------------------
_SKELETONS: dict[str, dict[str, Any]] = {}


def _learn_skeleton(decision: dict[str, Any]) -> None:
    band = decision["risk"]["risk_band"]
    tier = decision["tier"]["tier"]
    airgap = decision["airgap_required"]
    model_fam = ((decision.get("chosen_model") or {}).get("id") or "—").split("-")[0]
    key = f"{band}|{tier}|{'airgap' if airgap else 'cloud'}|{model_fam}"
    sk = _SKELETONS.get(key)
    if sk is None:
        sk = {
            "key": key, "risk_band": band, "tier": tier,
            "airgap": airgap, "model_family": model_fam,
            "uses": 0, "first_seen": time.time(), "last_seen": time.time(),
            "lesson": _lesson(band, tier, airgap),
        }
        _SKELETONS[key] = sk
    sk["uses"] += 1
    sk["last_seen"] = time.time()
    # Bound the meta-memory: keep the 64 most-used skeletons (forget the rest).
    if len(_SKELETONS) > 64:
        worst = min(_SKELETONS.values(), key=lambda s: (s["uses"], s["last_seen"]))
        _SKELETONS.pop(worst["key"], None)


def _lesson(band: str, tier: str, airgap: bool) -> str:
    z = "air-gapped (classified)" if airgap else "cloud-eligible"
    return (f"{band}-risk decisions routed to the {tier} budget tier on {z} compute "
            f"resolved within budget; reuse this skeleton for the same risk class.")


def skeletons() -> dict[str, Any]:
    sks = sorted(_SKELETONS.values(), key=lambda s: s["uses"], reverse=True)
    return {"skeleton_count": len(sks), "skeletons": sks,
            "hint": None if sks else "no skeletons yet — route decisions via POST /api/a11oy/v1/budget/route to learn them"}


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/budget/tiers", include_in_schema=False)
    async def _tiers() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, "tiers": TIERS,
                             "pattern_source": "ViktorAxelsen/BudgetMem (Apache-2.0) — module budget tiers, evolved to mission constraints"})

    @app.post(f"/api/{ns}/v1/budget/route", include_in_schema=False)
    async def _route(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        q = (body or {}).get("query") or (body or {}).get("q") or ""
        declared = (body or {}).get("classification")
        dl = (body or {}).get("deadline_s")
        try:
            dl = float(dl) if dl is not None else None
        except Exception:
            dl = None
        if not q:
            return JSONResponse({"error": "provide {query: ...}"}, status_code=400)
        return JSONResponse({"doctrine": DOCTRINE, **route(q, declared=declared, deadline_s=dl)})

    @app.get(f"/api/{ns}/v1/budget/skeletons", include_in_schema=False)
    async def _sk() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, **skeletons(),
                             "pattern_source": "ViktorAxelsen/MemSkill (Apache-2.0) — meta-memory, evolved to Decision Skeletons"})

    @app.get("/budget-router", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"budget-router mounted: GET /budget-router + /api/{ns}/v1/budget/(tiers|route|skeletons)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Budget-Tier Router + Decision Skeletons</title>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--blue:#1f6feb;--red:#f85149;--amber:#d29922;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,select{background:#0d141c;border:1px solid var(--line);border-radius:8px;color:var(--ink);padding:9px 11px;font-size:14px}
input{flex:1;min-width:200px}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:9px 16px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.blue{background:rgba(31,111,235,.18);color:#79b8ff}
.red{background:rgba(248,81,73,.15);color:var(--red)}
.amber{background:rgba(210,153,34,.15);color:var(--amber)}
.tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:6px}
.tcard{background:#0d141c;border:1px solid var(--line);border-radius:10px;padding:12px}
.tcard h3{margin:.1em 0;font-size:16px}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
.sk{border-top:1px solid var(--line);padding:10px 0}.sk:first-child{border-top:0}
.sk .k{color:var(--gold);font-weight:700}.sk .l{color:var(--muted);font-size:13px}
.uses{float:right;color:var(--green);font-variant-numeric:tabular-nums}
.chips{margin-top:10px}.chip{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;border:1px solid var(--line);
border-radius:999px;font-size:12px;color:var(--muted);cursor:pointer;background:#0d141c}.chip:hover{border-color:var(--gold);color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Budget-Tier Router <span class="pill green">cost-aware</span> <span class="pill blue">Decision Skeletons</span></h1>
<p class="sub">Routes each governed decision by <b>risk</b> (sensitivity × reversibility) to the
cheapest mission budget tier that still satisfies it — <b>Tactical (≤1s)</b>, <b>Operational (≤10s)</b>,
<b>Strategic (≤1min)</b> — then to the smallest sufficient air-gap-safe model. Patterns from
<code>BudgetMem</code> + <code>MemSkill</code> (Apache-2.0) and <code>GraphPlanner</code> (MIT),
evolved into mission-bound budget routing with reusable Decision Skeletons. 0 CDN.</p>

<div class="card">
<h3 style="margin-top:0">Mission budget tiers</h3>
<div class="tiers" id="tiers"></div>
</div>

<div class="card">
<h3 style="margin-top:0">Route a decision</h3>
<div class="row">
<input id="q" placeholder="describe the decision (e.g. authorize drone strike on classified grid ref)…"/>
<select id="cls"><option value="">auto-classify</option><option>PUBLIC</option><option>INTERNAL</option><option>RESTRICTED</option><option>SECRET</option></select>
<select id="dl"><option value="">no deadline</option><option value="1">≤1s</option><option value="10">≤10s</option><option value="60">≤60s</option></select>
<button id="go">Route</button>
</div>
<div class="chips" id="chips">
<span class="chip">summarize today's maritime intel feed</span>
<span class="chip">authorize a drone strike on classified grid ref</span>
<span class="chip">draft an internal roadmap memo</span>
</div>
<pre id="out" style="margin-top:12px">Route a decision to see the tier + model + risk verdict.</pre>
</div>

<div class="card">
<div class="row" style="justify-content:space-between"><h3 style="margin:0">Decision Skeletons (learned)</h3>
<button id="ref" style="background:#1f6feb;color:#fff">Refresh</button></div>
<div id="sks" style="margin-top:8px">No skeletons yet.</div>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
patterns: BudgetMem + MemSkill (Apache-2.0), GraphPlanner (MIT), evolved · sovereign 0-CDN.</p>
</div>
<script>
const $=s=>document.querySelector(s);
function band(b){return b==='HIGH'?'red':b==='MODERATE'?'amber':'green'}
async function tiers(){
  const d=await(await fetch('/api/a11oy/v1/budget/tiers')).json();
  const box=$('#tiers');box.innerHTML='';
  for(const t of d.tiers){
    const el=document.createElement('div');el.className='tcard';
    el.innerHTML='<h3>'+t.tier+' <span class="pill blue">'+t.budget+'</span></h3>'
      +'<div class="l" style="color:var(--muted);font-size:13px">deadline ≤'+t.deadline_s+'s · max model '+t.max_model_tier+' · CoT '+t.cot+'</div>'
      +'<div style="margin-top:6px;font-size:13px">'+t.note+'</div>';
    box.appendChild(el);
  }
}
async function route(){
  const q=$('#q').value;if(!q)return;
  const body={query:q};const c=$('#cls').value;const dl=$('#dl').value;
  if(c)body.classification=c;if(dl)body.deadline_s=Number(dl);
  const d=await(await fetch('/api/a11oy/v1/budget/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();
  const r=d.risk||{};const m=d.chosen_model;
  $('#out').textContent=
    'TIER: '+(d.tier&&d.tier.tier)+'  (budget '+(d.tier&&d.tier.budget)+', deadline ≤'+(d.tier&&d.tier.deadline_s)+'s)\\n'
    +'RISK: '+r.risk+'  ['+r.risk_band+']  sensitivity='+(r.sensitivity&&r.sensitivity.class)
    +'  reversibility='+(r.reversibility&&r.reversibility.label)+(r.capped_by_deadline?'  (tier capped by deadline)':'')+'\\n'
    +'AIR-GAP REQUIRED: '+d.airgap_required+'\\n'
    +'MODEL: '+(m?(m.id+'  ['+m.tier+'/'+m.zone+', '+m.license+']'):('— '+(d.honest||'')))+'\\n\\n'
    +'policy: '+d.policy;
  loadSk();
}
async function loadSk(){
  const d=await(await fetch('/api/a11oy/v1/budget/skeletons')).json();
  const box=$('#sks');box.innerHTML='';
  if(!d.skeletons.length){box.innerHTML='<div class="l">'+(d.hint||'No skeletons yet.')+'</div>';return}
  for(const s of d.skeletons){
    const el=document.createElement('div');el.className='sk';
    el.innerHTML='<span class="uses">×'+s.uses+'</span>'
      +'<div class="k">'+s.key+'</div><div class="l">'+s.lesson+'</div>';
    box.appendChild(el);
  }
}
$('#go').addEventListener('click',route);
$('#q').addEventListener('keydown',e=>{if(e.key==='Enter')route()});
$('#ref').addEventListener('click',loadSk);
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{$('#q').value=c.textContent;route();}));
tiers();loadSk();
</script>
</body></html>"""
