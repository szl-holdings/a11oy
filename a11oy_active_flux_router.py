# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_active_flux_router.py — model-router CROSSOVER view (E2b).

ADOPTED-AND-GENERALIZED, not invented here. We take the active-flux observer's
PI-bandwidth crossover law (Li Yu / IEEE 911711) and apply it to MODEL ROUTING:

  * small / local  model  = LOW-"frequency" / EASY-query estimator (cf. current model)
  * large / cloud  model  = HIGH-"frequency" / HARD-query estimator (cf. voltage model)

A query's difficulty in [0,1] maps to a pseudo-electrical frequency; the SAME
1st-order complementary blend (shared szl_cuas_formulas.active_flux_blend) decides
the small-vs-large weighting, with the PI-correction bandwidth ω_c acting as the
deterministic crossover knob. This is the DETERMINISTIC COMPLEMENT to a RouteLLM
Thompson-sampling bandit: where the bandit learns a stochastic policy, the
active-flux crossover gives a principled, citable, reproducible routing flip. If
Dev C ships live router posteriors (/api/a11oy/v1/router/stats), this view augments
them with the crossover; otherwise it stands alone as the crossover surface.

HONEST LABELS (doctrine v11):
  * The crossover decision is MODELED (a deterministic routing law), not a measured
    production traffic meter. We never fabricate per-model throughput here.
  * Λ = Conjecture 1; Khipu BFT = Conjecture 2; locked-proven = EXACTLY 8 @ c7c0ba17.
    This adds NOTHING to the locked-8 — an EXPERIMENTAL adopt-and-evolve.
  * Trust never 100%; 0 runtime CDN (page is dependency-free <canvas>).

Sources (cited; adopted, NOT reclaimed as an SZL theorem):
  - Active-flux sensorless control, IEEE/APEC 2001 — https://doi.org/10.1109/APEC.2001.911711
  - Li Yu (李彧), PI-correction bandwidth in an Active-Flux observer (LinkedIn 2026).
  - Revised Hybrid Active Flux encoderless PMSM technique (IEEE).
  - TI InstaSPIN-FOC / FAST (SPRUHJ1).
  - RouteLLM (Ong et al., LMSYS) — the Bayesian bandit this crossover complements.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import szl_cuas_formulas as _af  # SHARED, byte-identical a11oy↔killinchu

SOURCES = {
    "Active-flux sensorless control (IEEE/APEC 2001)": "https://doi.org/10.1109/APEC.2001.911711",
    "Li Yu (李彧) — PI-correction bandwidth (LinkedIn 2026)":
        "https://www.linkedin.com/pulse/how-should-bandwidth-pi-correction-loop-active-flux-observer-%E5%BD%A7-%E6%9D%8E-qxksc",
    "Revised Hybrid Active-Flux encoderless PMSM (IEEE)": "https://ieeexplore.ieee.org/document/9319155",
    "TI InstaSPIN-FOC / FAST (SPRUHJ1)": "https://www.ti.com/lit/ug/spruhj1h/spruhj1h.pdf",
    "RouteLLM (LMSYS, the bandit this complements)": "https://github.com/lm-sys/RouteLLM",
}

_HONEST = (
    "MODELED — this is a DETERMINISTIC routing crossover law, the complement to a "
    "RouteLLM Thompson-sampling bandit; not a measured production traffic meter. "
    "Adopted the active-flux PI-bandwidth crossover (Li Yu / IEEE 911711) and "
    "generalized it under SZL governance to model routing; adds NOTHING to the "
    "locked-8 and Λ stays Conjecture 1. Trust never 100%."
)


def _small_large_models(brain=None) -> Dict[str, str]:
    """Map the real szl_brain tier catalog to the small/local and large/cloud
    endpoints of the crossover. Lowest-rank fast/local tier = small; highest-rank
    frontier-reasoning tier = large. Honest fallback labels when brain unavailable."""
    try:
        tiers = list(getattr(brain, "TIERS", []) or [])
        if tiers:
            ranked = sorted(tiers, key=lambda t: int(t.get("rank", t.get("tier", 0))))
            small = ranked[0].get("id", "tier-0")
            # prefer a sovereign/local tier as 'small' if present
            for t in ranked:
                if "sovereign" in str(t.get("id", "")).lower() or "local" in str(t.get("id", "")).lower():
                    small = t.get("id"); break
            large = ranked[-1].get("id", "tier-N")
            for t in reversed(ranked):
                if "opus" in str(t.get("id", "")).lower() or int(t.get("rank", 0)) >= 3:
                    large = t.get("id"); break
            return {"small_local": small, "large_cloud": large, "source": "szl_brain.TIERS"}
    except Exception:
        pass
    return {"small_local": "sovereign_local (small/fast)",
            "large_cloud": "frontier_reasoning (large/cloud)",
            "source": "honest_stub_catalog"}


def router_crossover(query_difficulty: float = 0.5, pi_bandwidth_hz: float = 12.0,
                     difficulty_span_hz: float = 60.0, brain=None) -> Dict[str, Any]:
    """Deterministic model-router crossover (GENERALIZED active-flux law). Maps query
    difficulty d∈[0,1] to f = d·span; the shared active_flux_blend() gives the small-vs-
    large weighting; the PI bandwidth ω_c is the crossover knob. Returns which model
    dominates + the crossover difficulty. Complement to a RouteLLM bandit. [MODELED]"""
    d = min(max(float(query_difficulty), 0.0), 1.0)
    f = d * difficulty_span_hz
    blend = _af.active_flux_blend(pi_bandwidth_hz, f)
    w_small = blend["current_model_weight"]
    w_large = blend["voltage_model_weight"]
    route = "small/local" if w_small >= w_large else "large/cloud"
    models = _small_large_models(brain)
    return {
        "query_difficulty": round(d, 4),
        "pi_bandwidth_hz": round(pi_bandwidth_hz, 4),
        "crossover_difficulty": round(blend["crossover_hz"] / max(difficulty_span_hz, 1e-6), 4),
        "weight_small_local": round(w_small, 6),
        "weight_large_cloud": round(w_large, 6),
        "route": route, "regime": "easy" if route == "small/local" else "hard",
        "models": models,
        "complement_to": "RouteLLM Thompson-sampling bandit (deterministic crossover complement)",
        "doctrine": ("GENERALIZED active-flux PI-bandwidth crossover for model routing; "
                     "deterministic complement to the Bayesian bandit; NOT in the locked-8; "
                     "Λ = Conjecture 1; trust never 100%"),
        "data_label": "MODELED",
        "status": "MODELED",
    }


def sweep(pi_bandwidth_hz: float = 12.0, points: int = 41,
          difficulty_span_hz: float = 60.0, brain=None) -> Dict[str, Any]:
    """Crossover curve over query difficulty 0→1 for a chosen PI bandwidth (MODELED)."""
    n = max(2, int(points))
    curve = []
    for i in range(n):
        d = i / (n - 1)
        f = d * difficulty_span_hz
        b = _af.active_flux_blend(pi_bandwidth_hz, f)
        curve.append({"difficulty": round(d, 4),
                      "small_local": b["current_model_weight"],
                      "large_cloud": b["voltage_model_weight"],
                      "route": "small/local" if b["current_model_weight"] >= b["voltage_model_weight"] else "large/cloud"})
    return {"pi_bandwidth_hz": pi_bandwidth_hz,
            "crossover_difficulty": round(_af.pi_crossover_freq(pi_bandwidth_hz) / max(difficulty_span_hz, 1e-6), 4),
            "points": n, "curve": curve, "models": _small_large_models(brain),
            "data_label": "MODELED", "status": "MODELED"}


def info(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "capability": "Model-Router Active-Flux Crossover",
        "ns": ns,
        "summary": ("Deterministic model-routing crossover: small/local = easy/low-frequency, "
                    "large/cloud = hard/high-frequency, with a tunable PI-bandwidth crossover. "
                    "Adopted from Li Yu / IEEE 911711, generalized under SZL governance; the "
                    "deterministic complement to a RouteLLM Thompson-sampling bandit."),
        "endpoints": {
            "crossover": f"/api/{ns}/v1/router/active-flux-crossover",
            "sweep": f"/api/{ns}/v1/router/active-flux-crossover/sweep",
            "page": "/router-crossover",
        },
        "doctrine": {"locked_proven": 8, "lambda": "Conjecture 1", "khipu_bft": "Conjecture 2",
                     "trust": "never 100%", "data_label": "MODELED"},
        "sources": SOURCES, "honest": _HONEST, "status": "EXPERIMENTAL",
    }


def _page_html(ns: str) -> str:
    return r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model-Router · Active-Flux Crossover — a11oy</title>
<style>
 :root{--bg:#070b10;--panel:#0d141c;--line:#1d2a36;--teal:#39d3c4;--gold:#e8c074;--cream:#eef3f6;
  --para:#9fb1bf;--small:#6fb1ff;--large:#ffb56b;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--cream);
  font:14px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,Arial}
 a{color:var(--teal);text-decoration:none}
 header{padding:14px 18px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0a1119,#070b10)}
 h1{font-size:18px;margin:0 0 2px}.sub{color:var(--para);font-size:12.5px;max-width:980px}
 .badge{display:inline-block;font-size:10.5px;padding:2px 7px;border-radius:6px;border:1px solid var(--line);
  margin-right:6px;color:var(--gold);background:#10171f;vertical-align:middle}
 .wrap{max-width:960px;margin:0 auto;padding:16px}
 .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
 .panel h2{font-size:14px;margin:0 0 8px}.pp{color:var(--para);font-size:12px;margin:0 0 10px}
 canvas{width:100%;height:300px;background:#060a0e;border:1px solid var(--line);border-radius:8px;display:block}
 .ctrl{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:12.5px;flex-wrap:wrap}
 .ctrl label{color:var(--para);min-width:200px}input[type=range]{flex:1;accent-color:var(--teal)}
 .val{color:var(--teal);font-variant-numeric:tabular-nums;min-width:64px;text-align:right}
 .kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
 @media(max-width:720px){.kpi{grid-template-columns:1fr 1fr}}
 .kpi div{background:#0a1117;border:1px solid var(--line);border-radius:7px;padding:8px}
 .kpi b{display:block;font-size:17px;color:var(--gold);font-variant-numeric:tabular-nums}
 .kpi span{font-size:11px;color:var(--para)}
 .legend{font-size:11.5px;color:var(--para);margin-top:6px}
 .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 4px 0 10px;vertical-align:middle}
 .out{white-space:pre-wrap;font:11.5px ui-monospace,monospace;color:#bfe;background:#06090d;
  border:1px solid var(--line);border-radius:7px;padding:8px;max-height:180px;overflow:auto}
 .src{font-size:11px;color:var(--para);margin-top:10px;line-height:1.7}.src a{color:var(--teal)}
 footer{padding:12px 18px;border-top:1px solid var(--line);color:var(--para);font-size:11px}
</style></head><body>
<header><h1>Model-Router · Active-Flux Crossover
  <span class="badge">MODELED</span><span class="badge">Λ = Conjecture 1</span>
  <span class="badge">0 runtime CDN</span></h1>
 <div class="sub">Deterministic complement to a RouteLLM Thompson-sampling bandit:
  <span style="color:var(--small)">small/local</span> = easy / low-"frequency", 
  <span style="color:var(--large)">large/cloud</span> = hard / high-"frequency", with a tunable
  <b>PI-correction bandwidth ω_c</b> as the crossover knob. <b>Adopted</b> from Li Yu / IEEE 911711,
  generalized under SZL governance. <a href="/">← a11oy</a></div></header>
<div class="wrap">
 <div class="panel">
  <h2>Routing weight vs query difficulty (active-flux crossover)</h2>
  <p class="pp">A lower PI bandwidth keeps the <span style="color:var(--small)">small/local</span> model
   dominant to higher difficulty; a higher bandwidth hands off to the
   <span style="color:var(--large)">large/cloud</span> model sooner. The crossover line marks the
   difficulty at which routing flips. MODELED 1st-order complementary blend.</p>
  <canvas id="plot" width="600" height="300"></canvas>
  <div class="legend"><span class="dot" style="background:var(--small)"></span>small/local weight
   <span class="dot" style="background:var(--large)"></span>large/cloud weight
   <span class="dot" style="background:var(--teal)"></span>crossover
   <span class="dot" style="background:var(--gold)"></span>current query</div>
  <div class="ctrl"><label>PI correction bandwidth ω_c</label>
   <input id="bw" type="range" min="3" max="40" step="0.5" value="12"><span class="val" id="bw-v">12.0 Hz</span></div>
  <div class="ctrl"><label>query difficulty (0 easy → 1 hard)</label>
   <input id="qd" type="range" min="0" max="1" step="0.02" value="0.5"><span class="val" id="qd-v">0.50</span></div>
 </div>
 <div class="panel">
  <h2>Routing decision @ this query</h2>
  <div class="kpi">
   <div><b id="k-route">—</b><span>dominant model</span></div>
   <div><b id="k-cross">—</b><span>crossover difficulty</span></div>
   <div><b id="k-small">—</b><span>small/local weight</span></div>
   <div><b id="k-large">—</b><span>large/cloud weight</span></div>
  </div>
  <div class="legend" id="k-models">—</div>
  <details style="margin-top:10px"><summary style="cursor:pointer;color:var(--teal)">raw /router/active-flux-crossover</summary>
   <div class="out" id="raw">—</div></details>
 </div>
</div>
<footer>Doctrine v11 · locked = 8 @ c7c0ba17 · Λ = Conjecture 1 · Khipu BFT = Conjecture 2 ·
 <b>routing crossover MODELED (deterministic complement to the RouteLLM bandit)</b> · 0 runtime CDN ·
 trust &lt; 100%.<br>Adopted &amp; generalized — sources:
 <a href="https://doi.org/10.1109/APEC.2001.911711" target="_blank" rel="noopener">Active-flux IEEE/APEC 2001 (911711)</a> ·
 <a href="https://www.linkedin.com/pulse/how-should-bandwidth-pi-correction-loop-active-flux-observer-%E5%BD%A7-%E6%9D%8E-qxksc" target="_blank" rel="noopener">Li Yu (LinkedIn)</a> ·
 <a href="https://ieeexplore.ieee.org/document/9319155" target="_blank" rel="noopener">Revised Hybrid Active Flux (IEEE)</a> ·
 <a href="https://github.com/lm-sys/RouteLLM" target="_blank" rel="noopener">RouteLLM</a>.</footer>
<script src="/static/shared/szl_label_engine.js" defer></script>
<script src="/static/shared/szl_receipt_cosign.js" defer></script>
<script src="/static/shared/szl_codename_sanitizer.js" defer></script>
<script>
"use strict";
const API="/api/__NS__/v1/router";
const $=id=>document.getElementById(id);
const SPAN=60;
function crossoverFreq(bw){return 150.0/Math.max(bw,1e-6);}
function blend(bw,f){const fx=crossoverFreq(bw),wx=2*Math.PI*fx,we=2*Math.PI*Math.max(f,0);
  const d=Math.sqrt(wx*wx+we*we)||1e-12;return {fx,hc:wx/d,hv:we/d};}
function drawPlot(){
  const bw=parseFloat($("bw").value),qd=parseFloat($("qd").value);
  const c=$("plot"),ctx=c.getContext("2d"),W=c.width,H=c.height,padL=40,padB=26,padT=12,padR=10;
  const x0=padL,x1=W-padR,y0=padT,y1=H-padB;ctx.clearRect(0,0,W,H);
  const fx=d=>x0+d*(x1-x0),fy=w=>y1-w*(y1-y0);
  ctx.strokeStyle="#142029";ctx.fillStyle="#5b6c78";ctx.font="10px ui-monospace,monospace";ctx.lineWidth=1;
  [0,.25,.5,.75,1].forEach(w=>{const y=fy(w);ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();ctx.fillText(w.toFixed(2),4,y+3);});
  [0,.25,.5,.75,1].forEach(d=>{const x=fx(d);ctx.beginPath();ctx.moveTo(x,y0);ctx.lineTo(x,y1);ctx.stroke();ctx.fillText(d.toFixed(2),x-8,y1+14);});
  ctx.fillText("query difficulty",(x0+x1)/2-36,H-2);
  const cd=crossoverFreq(bw)/SPAN;
  if(cd<=1){const cx=fx(cd);ctx.strokeStyle="#39d3c4";ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(cx,y0);ctx.lineTo(cx,y1);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle="#39d3c4";ctx.fillText("flip="+cd.toFixed(2),cx+3,y0+10);}
  const ox=fx(qd);ctx.strokeStyle="#e8c074";ctx.setLineDash([2,2]);ctx.beginPath();ctx.moveTo(ox,y0);ctx.lineTo(ox,y1);ctx.stroke();ctx.setLineDash([]);
  function curve(col,key){ctx.strokeStyle=col;ctx.lineWidth=2;ctx.beginPath();
    for(let i=0;i<=120;i++){const d=i/120,b=blend(bw,d*SPAN),w=key==="s"?b.hc:b.hv,X=fx(d),Y=fy(w);i?ctx.lineTo(X,Y):ctx.moveTo(X,Y);}ctx.stroke();}
  curve("#6fb1ff","s");curve("#ffb56b","l");
}
function setVal(){$("bw-v").textContent=parseFloat($("bw").value).toFixed(1)+" Hz";$("qd-v").textContent=parseFloat($("qd").value).toFixed(2);}
async function refresh(){
  const bw=$("bw").value,qd=$("qd").value;
  try{const r=await fetch(`${API}/active-flux-crossover?query_difficulty=${qd}&bw=${bw}`);const d=await r.json();
    $("k-route").textContent=d.route;$("k-cross").textContent=d.crossover_difficulty.toFixed(2);
    $("k-small").textContent=d.weight_small_local.toFixed(3);$("k-large").textContent=d.weight_large_cloud.toFixed(3);
    $("k-models").textContent="small/local = "+d.models.small_local+"  ·  large/cloud = "+d.models.large_cloud+"  ("+d.models.source+")";
    $("raw").textContent=JSON.stringify(d,null,1);
  }catch(e){$("raw").textContent="endpoint unreachable: "+e;}
}
function onChange(){setVal();drawPlot();refresh();}
["bw","qd"].forEach(id=>$(id).addEventListener("input",onChange));
window.addEventListener("resize",drawPlot);onChange();
</script></body></html>""".replace("__NS__", ns)


def register(app, ns: str = "a11oy", brain=None) -> Dict[str, Any]:
    """Attach the model-router active-flux crossover surface. ADDITIVE; BEFORE the
    SPA/proxy catch-all. Pure stdlib + shared szl_cuas_formulas math. 0 CDN.
    Registered at BOTH /api/<ns>/v1/... and the root /v1/... path (HF proxy strips
    /api/a11oy), matching the existing router/stats dual-registration pattern."""
    from starlette.responses import HTMLResponse, JSONResponse
    registered: List[str] = []
    # resolve the brain catalog lazily if not injected
    if brain is None:
        try:
            import szl_brain as _b
            brain = _b
        except Exception:
            brain = None

    def _cross(query_difficulty: str = "0.5", bw: str = "12.0"):
        try:
            return JSONResponse(router_crossover(query_difficulty=float(query_difficulty),
                                                 pi_bandwidth_hz=float(bw), brain=brain))
        except (ValueError, TypeError) as e:
            return JSONResponse({"error": {"code": "validation_error", "detail": str(e)}}, status_code=422)

    def _sweep(bw: str = "12.0", points: str = "41"):
        try:
            return JSONResponse(sweep(pi_bandwidth_hz=float(bw), points=int(points), brain=brain))
        except (ValueError, TypeError) as e:
            return JSONResponse({"error": {"code": "validation_error", "detail": str(e)}}, status_code=422)

    for prefix in (f"/api/{ns}/v1/router", "/v1/router"):
        app.add_api_route(f"{prefix}/active-flux-crossover", _cross, methods=["GET"])
        app.add_api_route(f"{prefix}/active-flux-crossover/sweep", _sweep, methods=["GET"])
        app.add_api_route(f"{prefix}/active-flux-crossover/info", lambda: JSONResponse(info(ns)), methods=["GET"])
        registered.append(f"GET {prefix}/active-flux-crossover")

    _html = _page_html(ns)

    async def _page():
        return HTMLResponse(_html)
    app.add_api_route("/router-crossover", _page, methods=["GET"])
    registered.append("GET /router-crossover")

    return {"registered": registered, "count": len(registered),
            "capability": "Model-Router Active-Flux Crossover", "data_label": "MODELED"}


def _selftest() -> None:
    assert abs(_af.pi_crossover_freq(5.0) - 30.0) < 1e-9
    easy = router_crossover(query_difficulty=0.05, pi_bandwidth_hz=5.0)
    hard = router_crossover(query_difficulty=0.95, pi_bandwidth_hz=5.0)
    assert easy["route"] == "small/local" and hard["route"] == "large/cloud"
    # higher PI bandwidth -> crossover difficulty DOWN -> large/cloud sooner
    lo_bw = router_crossover(query_difficulty=0.2, pi_bandwidth_hz=5.0)   # flip at 30/60=0.5 -> small
    hi_bw = router_crossover(query_difficulty=0.2, pi_bandwidth_hz=30.0)  # flip at 5/60=0.083 -> large
    assert lo_bw["route"] == "small/local" and hi_bw["route"] == "large/cloud"
    s = sweep(pi_bandwidth_hz=12.0, points=11)
    assert s["points"] == 11 and len(s["curve"]) == 11 and s["status"] == "MODELED"
    print("a11oy_active_flux_router: ALL OK (5 checks)")


if __name__ == "__main__":
    _selftest()
