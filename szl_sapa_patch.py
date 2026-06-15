# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) — SAPA route + tab registrar (front-inserted).
# ===========================================================================
# szl_sapa_patch.py — serves the SAPA Energy-per-Successful-Goal surface.
#
# FRONTIER (additive): the joules-per-SUCCESSFUL-GOAL unit on top of the live
# MEASURED joules/token path. Computation lives in szl_sapa.py (shared,
# byte-identical both apps). This module ONLY wires routes + the /sapa tab.
#
# Routes (FRONT-INSERTED before the SPA catch-all, idempotent by route name —
# learned from the WAQAY/Yupay nav-injection fix: insert at position 0 so the
# explicit routes beat the SPA history fallback /{full_path}):
#     GET /api/<ns>/v1/sapa            — full SAPA snapshot (machine-readable)
#     GET /api/<ns>/v1/sapa/receipt    — DSSE-signed energy-per-goal receipt
#     GET /api/<ns>/v1/sapa/timeseries — energy-per-goal time-series (honest)
#     GET /sapa                        — served tab (0-CDN holo-kit visuals)
#
# DOCTRINE (v11): locked=8 @ c7c0ba17; Λ = Conjecture 1; SLSA L1/L2-roadmap;
# 0 user-visible codenames; effectors SIMULATED; 0 runtime CDN; data labelled
# MEASURED/MODELED/SAMPLE/ROADMAP; never fabricates a joule; never weakens a gate.
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ===========================================================================
from __future__ import annotations

import sys as _sapa_sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.routing import APIRoute as _AR

import szl_sapa

# In-memory honest time-series of the energy-per-goal headline (per Space, non
# -persistent across restart — same honest ceiling as the Khipu DAG). Every call
# to the snapshot endpoint appends a point. NEVER fabricated: points carry the
# real headline label, so a 'pending — no meter' point is recorded as null J.
_TS: "deque[dict[str, Any]]" = deque(maxlen=240)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_point(snap: dict) -> None:
    _TS.append({
        "ts": _now_iso(),
        "joules_per_successful_goal": snap.get("joules_per_successful_goal"),
        "success_rate": snap.get("success_rate"),
        "agentic_multiplier_x": snap.get("agentic_multiplier_x"),
        "label": snap.get("headline_label"),
        "successful": (snap.get("goals") or {}).get("successful"),
        "attempted": (snap.get("goals") or {}).get("attempted"),
    })


# ---------------------------------------------------------------------------
# The served /sapa tab — 0-CDN holo-kit visuals. Pure inline HTML/CSS/JS, no
# external assets, no CDN. Reuses window.SZLLabels badge tones when present
# (graceful fallback to inline pills otherwise). Pulls /api/<ns>/v1/sapa/*.
# ---------------------------------------------------------------------------
def _page_html(ns: str) -> str:
    base = "/api/%s/v1/sapa" % ns
    return """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAPA — Energy per Successful Goal · """ + ns + """</title>
<style>
:root{--bg:#070b12;--card:#0e1626;--ink:#e8eefc;--sub:#8aa0c8;--line:#1c2942;
--live:#27e0a8;--model:#ffcf6b;--road:#7da2ff;--pend:#9aa7bd;--accent:#5ce0ff;}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 700px at 70% -10%,#10203a 0,var(--bg) 60%);
color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:26px 18px 60px}
h1{font-size:1.5rem;margin:.2rem 0 .1rem;letter-spacing:.2px}
.sub{color:var(--sub);margin:.1rem 0 1.1rem;font-size:.93rem}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:linear-gradient(180deg,#0f1a2e,var(--card));border:1px solid var(--line);
border-radius:16px;padding:16px 16px 14px;box-shadow:0 1px 0 #ffffff08 inset,0 14px 40px #0008}
.hero{grid-column:1/-1;display:flex;flex-wrap:wrap;align-items:flex-end;gap:24px}
.big{font-variant-numeric:tabular-nums;font-size:2.6rem;font-weight:700;line-height:1}
.big small{font-size:.9rem;color:var(--sub);font-weight:500}
.row{display:flex;align-items:center;justify-content:space-between;gap:10px}
h3{margin:0 0 8px;font-size:1rem}
.kv{display:flex;justify-content:space-between;border-top:1px dashed var(--line);padding:7px 0;font-size:.92rem}
.kv .k{color:var(--sub)}.kv .v{font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.4px;border:1px solid #fff2}
.pill.MEASURED{background:#0c3;color:#012;background:var(--live)}
.pill.MODELED{background:var(--model);color:#241a00}
.pill.ROADMAP{background:var(--road);color:#04122e}
.pill.pending{background:var(--pend);color:#10151f}
.note{color:var(--sub);font-size:.82rem;margin:.6rem 0 0}
.spark{height:74px;width:100%;display:block}
.mult{font-size:2rem;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums}
.foot{color:var(--sub);font-size:.78rem;margin-top:22px;border-top:1px solid var(--line);padding-top:12px}
a{color:var(--accent)}code{color:#bcd2ff}
.tag{font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.6px}
</style></head><body><div class="wrap">
<h1>SAPA · Energy per <span style="color:var(--accent)">Successful Goal</span></h1>
<p class="sub">The frontier agentic unit on top of SZL's live <b>MEASURED joules/token</b>:
total MEASURED joules across <b>every inference step of a completed, Restraint-passed agent trajectory</b>,
divided by goals completed. Failed/retried goals inflate the cost <b>honestly</b>.
Inspired by A-LEMS / Energy-per-Successful-Goal (<a href="https://arxiv.org/abs/2605.22883">arXiv:2605.22883</a>) —
this is <b>our</b> implementation against our own meter + signed corpus.</p>

<div class="grid">
  <div class="card hero">
    <div><div class="tag">Joules / successful goal</div>
      <div class="big" id="jpg">—<small> J</small></div>
      <span class="pill pending" id="jpg_pill">pending</span></div>
    <div><div class="tag">Agentic multiplier</div>
      <div class="mult" id="mult">—×</div>
      <span class="note" style="margin:0">vs naive per-token (EpG ref: 4.33×)</span></div>
    <div><div class="tag">Success rate</div>
      <div class="big" id="sr">—<small> %</small></div></div>
  </div>

  <article class="card">
    <div class="row"><h3>Joules / successful goal</h3><span class="pill pending" id="p1">pending</span></div>
    <div class="kv"><span class="k">J / successful goal</span><span class="v" id="k_jpg">—</span></div>
    <div class="kv"><span class="k">J / goal attempted</span><span class="v" id="k_jpa">—</span></div>
    <div class="kv"><span class="k">agentic multiplier</span><span class="v" id="k_mult">—</span></div>
    <p class="note" id="n1">Awaiting the live joule-meter + completed goals.</p>
  </article>

  <article class="card">
    <div class="row"><h3>Joules / token (live, existing)</h3><span class="pill ROADMAP" id="p2">ROADMAP</span></div>
    <div class="kv"><span class="k">J / token</span><span class="v" id="k_jpt">—</span></div>
    <div class="kv"><span class="k">GPU energy (J, cum.)</span><span class="v" id="k_gj">—</span></div>
    <div class="kv"><span class="k">joules honesty</span><span class="v" id="k_jh">—</span></div>
    <p class="note">MEASURED only on a live on-box NVML reading (<code>gpu_energy_joules_total</code>). Source: <code>/energy</code>.</p>
  </article>

  <article class="card">
    <div class="row"><h3>Goal trajectories</h3><span class="pill ROADMAP" id="p3">ROADMAP</span></div>
    <div class="kv"><span class="k">attempted</span><span class="v" id="g_att">—</span></div>
    <div class="kv"><span class="k">successful (Restraint-passed)</span><span class="v" id="g_ok">—</span></div>
    <div class="kv"><span class="k">failed / retried</span><span class="v" id="g_bad">—</span></div>
    <div class="kv"><span class="k">total trajectory steps</span><span class="v" id="g_steps">—</span></div>
    <p class="note" id="n3">Source: a11oy_react_core runs + per-step receipts.</p>
  </article>

  <article class="card" style="grid-column:1/-1">
    <div class="row"><h3>Energy-per-goal time-series</h3><span class="pill pending" id="p4">live</span></div>
    <svg class="spark" id="spark" viewBox="0 0 600 74" preserveAspectRatio="none"></svg>
    <p class="note" id="n4">Each point is a real snapshot; a <code>pending — no meter</code> point is recorded as null (never fabricated).</p>
  </article>

  <article class="card" style="grid-column:1/-1">
    <div class="row"><h3>Signed energy-per-goal receipt (DSSE)</h3><span class="pill ROADMAP" id="p5">—</span></div>
    <div class="kv"><span class="k">payloadType</span><span class="v"><code>application/vnd.szl.sapa+json</code></span></div>
    <div class="kv"><span class="k">signed</span><span class="v" id="r_signed">—</span></div>
    <div class="kv"><span class="k">keyid</span><span class="v" id="r_keyid">—</span></div>
    <p class="note" id="r_note">Receipt is DSSE-signed with the SZLHOLDINGS Cosign key when the runtime secret is present; else honestly UNSIGNED (never faked). Verify at <code>/api/""" + ns + """/khipu/verify</code>.</p>
  </article>
</div>

<p class="foot">SAPA = Quechua <i>sapa</i> ("each / whole"). Doctrine v11 · kernel c7c0ba17 · SLSA L1 (L2 roadmap) ·
Λ = Conjecture 1 · 0 runtime CDN · effectors SIMULATED · trust never 100%.
Labels: <b>MEASURED</b> (real fresh on-box joules) · <b>MODELED</b> (labelled illustrative basis) · <b>ROADMAP</b> / <b>pending</b> (no number faked).
Inspiration: A-LEMS / EpG arXiv:2605.22883 · Watt-Counts arXiv:2604.09048 · Energy-per-Token arXiv:2603.20224.</p>
</div>
<script>
var BASE=""" + '"' + base + '"' + """;
function pill(el,label){if(!el)return;var c=(label||"").indexOf("pending")===0?"pending":(label||"ROADMAP");
el.className="pill "+c;el.textContent=label||"—";}
function fmt(v,d){return (v===null||v===undefined)?"—":(typeof v==="number"?v.toLocaleString(undefined,{maximumFractionDigits:d===undefined?2:d}):v);}
function getJSON(u){return fetch(u,{headers:{"accept":"application/json"}}).then(function(r){return r.json();});}
function apply(s){
  var lbl=s.headline_label||"pending";
  document.getElementById("jpg").innerHTML=fmt(s.joules_per_successful_goal,1)+"<small> J</small>";
  pill(document.getElementById("jpg_pill"),lbl);pill(document.getElementById("p1"),lbl);
  document.getElementById("mult").textContent=(s.agentic_multiplier_x==null?"—":(s.agentic_multiplier_x+"×"));
  document.getElementById("sr").innerHTML=(s.success_rate==null?"—":(s.success_rate*100).toFixed(1))+"<small> %</small>";
  document.getElementById("k_jpg").textContent=fmt(s.joules_per_successful_goal,1);
  document.getElementById("k_jpa").textContent=fmt(s.joules_per_goal_attempted,1);
  document.getElementById("k_mult").textContent=(s.agentic_multiplier_x==null?"—":(s.agentic_multiplier_x+"× ("+(s.agentic_multiplier_label||"")+")"));
  document.getElementById("n1").textContent=s.energy_basis_note||"";
  pill(document.getElementById("p2"),s.joules_per_token_label||"ROADMAP");
  document.getElementById("k_jpt").textContent=fmt(s.joules_per_token,6);
  document.getElementById("k_gj").textContent=fmt(s.gpu_energy_joules_total,1);
  document.getElementById("k_jh").textContent=s.joules_honesty||"—";
  var g=s.goals||{};
  pill(document.getElementById("p3"),(g.successful>0?(lbl==="MEASURED"?"MEASURED":"MODELED"):"ROADMAP"));
  document.getElementById("g_att").textContent=fmt(g.attempted,0);
  document.getElementById("g_ok").textContent=fmt(g.successful,0);
  document.getElementById("g_bad").textContent=fmt(g.failed_or_retried,0);
  document.getElementById("g_steps").textContent=fmt(g.total_trajectory_steps,0);
  if(g.source)document.getElementById("n3").textContent="Source: "+g.source;
}
function spark(points){
  var svg=document.getElementById("spark");if(!svg)return;
  var pts=points.filter(function(p){return p.joules_per_successful_goal!=null;});
  if(!pts.length){svg.innerHTML='<text x="8" y="40" fill="#8aa0c8" font-size="12">no MEASURED/MODELED points yet — honest pending</text>';return;}
  var ys=pts.map(function(p){return p.joules_per_successful_goal;});
  var mn=Math.min.apply(null,ys),mx=Math.max.apply(null,ys);var rng=(mx-mn)||1;
  var n=pts.length,d="";
  for(var i=0;i<n;i++){var x=(n===1)?300:(i/(n-1))*592+4;var y=70-((ys[i]-mn)/rng)*62;d+=(i?"L":"M")+x.toFixed(1)+" "+y.toFixed(1)+" ";}
  svg.innerHTML='<path d="'+d+'" fill="none" stroke="#5ce0ff" stroke-width="2"/>'+
    '<text x="8" y="14" fill="#8aa0c8" font-size="11">'+mx.toFixed(0)+' J</text>'+
    '<text x="8" y="70" fill="#8aa0c8" font-size="11">'+mn.toFixed(0)+' J</text>';
}
function tick(){
  getJSON(BASE).then(apply).catch(function(){});
  getJSON(BASE+"/timeseries").then(function(t){spark((t&&t.points)||[]);}).catch(function(){});
  getJSON(BASE+"/receipt").then(function(r){
    pill(document.getElementById("p5"),(r.signed?"MEASURED":"ROADMAP"));
    document.getElementById("r_signed").textContent=(r.signed===true?"true (DSSE ECDSA-P256)":"false (UNSIGNED — no key secret, never faked)");
    document.getElementById("r_keyid").textContent=r.keyid||"—";
    if(r.honesty)document.getElementById("r_note").textContent=r.honesty;
  }).catch(function(){});
}
tick();setInterval(tick,15000);
</script></body></html>"""


# ---------------------------------------------------------------------------
# Route handlers.
# ---------------------------------------------------------------------------
def _make_handlers(ns: str):
    async def _sapa_snapshot(request: Request):  # noqa: ANN001
        try:
            snap = szl_sapa.compute_sapa()
            _record_point(snap)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)[:200], "headline_label": szl_sapa.PENDING,
                                 "joules_per_successful_goal": None, "ns": ns}, status_code=200)
        return JSONResponse({**snap, "ns": ns})

    async def _sapa_receipt(request: Request):  # noqa: ANN001
        try:
            snap = szl_sapa.compute_sapa()
            rec = szl_sapa.sapa_receipt(snap)
            # If the host app exposes the Khipu signed-receipt path, also append
            # to the DAG (so the SAPA receipt joins the W3C-traced ledger). Best
            # effort, never raises.
            try:
                emit = getattr(getattr(request.app, "state", None), "szl_emit_signed_receipt", None)
                if callable(emit):
                    node = emit(rec["receipt"], request)
                    rec["khipu_digest"] = node.get("digest")
                    rec["khipu_index"] = node.get("index")
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)[:200], "signed": False, "ns": ns}, status_code=200)
        return JSONResponse({**rec, "ns": ns,
                             "verify_at": "/api/%s/khipu/verify" % ns})

    async def _sapa_timeseries(request: Request):  # noqa: ANN001
        pts = list(_TS)
        measured_pts = [p for p in pts if p.get("joules_per_successful_goal") is not None]
        return JSONResponse({
            "ns": ns, "metric": "energy_per_successful_goal_timeseries",
            "count": len(pts), "measured_or_modeled_count": len(measured_pts),
            "points": pts,
            "note": ("In-memory per-Space series (non-persistent across restart). A "
                     "'pending — no meter' snapshot is recorded with null joules — never fabricated."),
            "doctrine": szl_sapa.DOCTRINE,
        })

    async def _sapa_page(request: Request):  # noqa: ANN001
        return HTMLResponse(_page_html(ns))

    return _sapa_snapshot, _sapa_receipt, _sapa_timeseries, _sapa_page


# ---------------------------------------------------------------------------
# Public registration — FRONT-INSERT (idempotent by route name).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy", serve_tab: bool = True) -> dict:
    """Front-insert SAPA routes before the SPA catch-all (idempotent by name).

    serve_tab=True also installs the served /sapa HTML tab (a11oy gets the tab;
    killinchu gets the API surface only by default, matching the task spec —
    pass serve_tab=True for killinchu too if a tab is wanted there).
    """
    base = "/api/%s/v1/sapa" % ns
    snap_h, rcpt_h, ts_h, page_h = _make_handlers(ns)

    new_routes = [
        _AR(base, snap_h, methods=["GET"],
            name="szl_sapa_%s_snapshot" % ns, include_in_schema=False,
            summary="FRONTIER: Energy per Successful Goal (SAPA) snapshot"),
        _AR("%s/receipt" % base, rcpt_h, methods=["GET"],
            name="szl_sapa_%s_receipt" % ns, include_in_schema=False,
            summary="SAPA DSSE-signed energy-per-goal receipt"),
        _AR("%s/timeseries" % base, ts_h, methods=["GET"],
            name="szl_sapa_%s_timeseries" % ns, include_in_schema=False,
            summary="SAPA energy-per-goal time-series"),
    ]
    if serve_tab:
        new_routes.append(
            _AR("/sapa", page_h, methods=["GET"],
                name="szl_sapa_%s_page" % ns, include_in_schema=False,
                summary="SAPA served tab — energy per successful goal"))

    skip = {r.name for r in new_routes}
    existing = [r for r in app.router.routes if getattr(r, "name", "") not in skip]
    app.router.routes.clear()
    app.router.routes.extend(new_routes + existing)
    for r in new_routes:
        print("[szl-sapa] %s %s front-inserted (ns=%s)" % (list(r.methods), r.path, ns),
              file=_sapa_sys.stderr)
    return {"ok": True, "ns": ns, "registered": [r.path for r in new_routes],
            "schema": szl_sapa.SAPA_SCHEMA}
