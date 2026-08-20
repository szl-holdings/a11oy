# -*- coding: utf-8 -*-
# ===========================================================================
# szl_mbse_nav.py — SZL Governed MBSE / FMI Digital-Twin pages + nav wire-up
# ---------------------------------------------------------------------------
# SHARED, BYTE-IDENTICAL module across a11oy + killinchu (shared-file-drift
# guard enforced). Companion to szl_mbse_cosim.py (the governed co-sim engine).
#
# This module is ADDITIVE + idempotent and does TWO things, mirroring the proven
# a11oy_nav_wireup.py / killinchu_nav_wireup.py pattern:
#   (1) registers REAL served HTML routes (inline HTML, 0 runtime CDN) for the
#       three MBSE digital-twin surfaces:
#         /mbse           — Governed Water-Tank Co-Simulation (canonical FMI ex.)
#         /mbse-6dof      — killinchu 6DOF FMU twin (vessel/UAS dynamics)
#         /mbse-pipeline  — Requirement -> Lean -> FMU -> signed-receipt pipeline
#       Each page loads the existing 0-CDN holo kit (/static/shared/szl_holo3d.js)
#       for a holographic backdrop + a Lambda trust readout, fetches the live
#       /api/{ns}/v1/mbse/* feeds, renders THREE inline-SVG time-series charts,
#       and shows the signed DSSE receipt. NO external CDN asset is loaded.
#   (2) attaches an idempotent BaseHTTPMiddleware that injects an MBSE nav group
#       (one honest nav-item per surface) into the console sidebar, keyed by
#       data-mbse-nav="v1" so re-runs NEVER double-inject and other lanes' nav
#       items are NEVER clobbered. The console SPA source is NOT edited.
#
# The routes are inserted at position 0 (before the SPA catch-all) so they
# resolve to a real 200 document. On killinchu these surfaces appear as new tabs
# reachable from the left-nav (the /elite console links to /mbse-6dof).
#
# DOCTRINE (v11): locked = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
# Lambda = Conjecture 1 (NOT a theorem); Khipu BFT = Conjecture 2; SLSA L1/L2
# attested + L3 roadmap; 0 visible codenames; 0 runtime CDN; effectors SIMULATED
# human-on-loop; trust never 100%; honest MODELED/SIMULATED labels; never weakens
# a gate; never commits a key; additive-only.
#
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# ===========================================================================
from typing import Any, Dict, List

# The three MBSE surfaces. (path, icon-glyph, honest label).
_SURFACES = [
    ("/mbse",          "\u25C8", "MBSE Water-Tank Co-Sim (Governed)"),    # ◈
    ("/mbse-6dof",     "\u2708", "MBSE 6DOF FMU Twin (MODELED)"),         # ✈
    ("/mbse-pipeline", "\u2713", "Requirement \u2192 Lean \u2192 FMU \u2192 Receipt"),  # ✓
]

_NAV_MARKER = b'data-mbse-nav="v1"'
_FOOT_ANCHOR = b'<div class="side-foot">'
_GROUP_ANCHOR = b'<div class="nav-group">'
_NAVITEM_ANCHOR = b'<div class="nav-item"'


def _build_nav_block() -> bytes:
    """A new left-nav group + one nav-item per MBSE surface, mirroring the
    console's own nav-item markup (class="nav-item" + <span class="ico"> + label)
    so it inherits the console styling. 0 CDN, 0 inline <style>, 0 codenames."""
    items = []
    for path, ico, label in _SURFACES:
        items.append(
            '<div class="nav-item" data-mbse-nav="v1" data-mbse-path="%s" '
            'onclick="location.href=\'%s\'" style="cursor:pointer">'
            '<span class="ico">%s</span>%s</div>' % (path, path, ico, label)
        )
    block = (
        '<div class="nav-group" data-mbse-nav="v1">'
        'Digital Twin &amp; Co-Sim (MBSE/FMI)</div>'
        + "".join(items)
    )
    return block.encode("utf-8")


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    nav_block = _build_nav_block()

    class _MBSENavInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "text/html" not in ct:
                    return resp
                p = request.url.path
                if (p.startswith("/api/") or p.startswith("/v1/")
                        or p.startswith("/vendor/") or p.startswith("/assets/")
                        or p.startswith("/static/")):
                    return resp
                # Never inject into our own MBSE pages (they carry their own nav).
                if p in ("/mbse", "/mbse-6dof", "/mbse-pipeline"):
                    return resp

                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()

                if _NAV_MARKER not in body:
                    if _FOOT_ANCHOR in body:
                        body = body.replace(_FOOT_ANCHOR, nav_block + _FOOT_ANCHOR, 1)
                    elif _NAVITEM_ANCHOR in body:
                        idx = body.find(_NAVITEM_ANCHOR)
                        end = body.find(b"</div>", idx)
                        if end != -1:
                            cut = end + len(b"</div>")
                            body = body[:cut] + nav_block + body[cut:]
                    elif _GROUP_ANCHOR in body:
                        body = body.replace(_GROUP_ANCHOR, _GROUP_ANCHOR + nav_block, 1)

                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _MBSENavInjector


# ---------------------------------------------------------------------------
# Inline HTML page builder (0 runtime CDN). Loads the shared holo kit from
# /static/shared/szl_holo3d.js (vendored locally in the image), fetches the live
# /api/{ns}/v1/mbse feed, renders THREE inline-SVG time-series charts, a
# holographic backdrop scene + Lambda trust readout, and the signed receipt.
# ---------------------------------------------------------------------------
def _page_html(ns: str, kind: str) -> str:
    cfg = {
        "watertank": {
            "title": "Governed Water-Tank Co-Simulation",
            "sub": "Canonical FMI example \u2014 GOVERNED: Restraint gate + signed receipt per run",
            "api": "/api/%s/v1/mbse/watertank" % ns,
            "lead": ("OpenModelica-pattern plant FMU (A&middot;der(level)=inflow&middot;valve&minus;demand) "
                     "co-simulated with a PI level-controller FMU and a stochastic demand generator. "
                     "Fixed-step + fixed-seed &rarr; reproducible &rarr; same receipt hash."),
            "other": [("/mbse-6dof", "6DOF FMU Twin"), ("/mbse-pipeline", "Req\u2192Lean\u2192FMU\u2192Receipt")],
        },
        "sixdof": {
            "title": "killinchu 6DOF FMU Twin",
            "sub": "6-degree-of-freedom vessel/UAS dynamics \u2014 EFFECTORS SIMULATED, human-on-loop",
            "api": "/api/%s/v1/mbse/sixdof" % ns,
            "lead": ("6DOF rigid-body plant FMU co-simulated with an engagement state-machine FMU "
                     "(Idle&rarr;Detect&rarr;Evaluate&rarr;Engage&rarr;Assess&rarr;RTB) and a stochastic "
                     "threat generator. SIMULATION OUTPUT only \u2014 no live vessel/weapon control."),
            "other": [("/mbse", "Water-Tank Co-Sim"), ("/mbse-pipeline", "Req\u2192Lean\u2192FMU\u2192Receipt")],
        },
        "pipeline": {
            "title": "Requirement \u2192 Lean \u2192 FMU \u2192 Signed Receipt",
            "sub": "The MBSE verification thread \u2014 a requirement bound to a LOCKED Lean theorem, run, signed",
            "api": "/api/%s/v1/mbse/pipeline?requirement_id=WaterLevelReq" % ns,
            "lead": ("A SysML-v2-style requirement is captured, checked against the LOCKED-8 Lean theorem "
                     "set (kernel c7c0ba17), bound to an FMU run, executed, and the PASS/FAIL evidence is "
                     "committed into a signed DSSE provenance receipt."),
            "other": [("/mbse", "Water-Tank Co-Sim"), ("/mbse-6dof", "6DOF FMU Twin")],
        },
    }[kind]

    other_links = "".join(
        '<a href="%s">%s</a>' % (p, l) for p, l in cfg["other"]
    )
    # NOTE: braces in JS are escaped as {{ }} because this is a percent-free
    # .format-free f-string-free template built by .replace below. We use plain
    # string substitution tokens to avoid any formatting pitfalls.
    tpl = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — SZL __NSUP__</title>
<style>
:root{--bg:#0a0e14;--panel:#0f1620;--line:#1d2632;--ink:#cfd8e3;--mut:#7c8794;--gold:#d4a444;--ok:#27ae60;--warn:#e67e22;--red:#e74c3c;--blue:#2980b9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--gold);text-decoration:none}a:hover{text-decoration:underline}
header{padding:1.1rem 1.3rem;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:baseline;gap:.6rem}
h1{font-size:1.32rem;margin:0;color:#fff}.sub{color:var(--mut);font-size:.92rem}
.wrap{max-width:1180px;margin:0 auto;padding:1.1rem 1.3rem 3rem}
.badges{margin:.5rem 0 0;display:flex;flex-wrap:wrap;gap:.4rem}
.badge{font-size:.72rem;padding:.16rem .5rem;border:1px solid var(--line);border-radius:999px;color:var(--mut);background:#0d141d}
.badge.model{color:#0a0e14;background:var(--gold);border-color:var(--gold);font-weight:600}
.lead{color:var(--mut);max-width:900px;margin:.7rem 0 1rem}
.ctl{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin:.4rem 0 1rem}
button{background:var(--gold);color:#0a0e14;border:0;border-radius:6px;padding:.5rem .95rem;font-weight:600;cursor:pointer}
button.sec{background:#16202c;color:var(--ink);border:1px solid var(--line)}
select,input{background:#0d141d;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:.4rem .5rem}
#holo{height:200px;border:1px solid var(--line);border-radius:8px;background:#070b11;margin-bottom:1rem;position:relative;overflow:hidden}
.grid{display:grid;grid-template-columns:1fr;gap:1rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:.85rem 1rem}
.card h3{margin:.1rem 0 .5rem;font-size:.98rem;color:#fff}
svg{width:100%;height:190px;display:block}
.axis{stroke:var(--line);stroke-width:1}.ref{stroke:var(--mut);stroke-dasharray:4 3;stroke-width:1}
.bandln{stroke:var(--warn);stroke-dasharray:5 4;stroke-width:1}
.lab{fill:var(--mut);font-size:11px}
pre{background:#070b11;border:1px solid var(--line);border-radius:8px;padding:.8rem;overflow:auto;font-size:12px;color:#9fb3c6;max-height:330px}
.kv{display:flex;flex-wrap:wrap;gap:.5rem 1.4rem;margin:.4rem 0}
.kv b{color:#fff}.kv span{color:var(--mut)}
.verdict{font-weight:700}.v-pass{color:var(--ok)}.v-fail{color:var(--red)}
.rel{margin-top:1.4rem;padding-top:.7rem;border-top:1px solid var(--line);color:var(--mut);font-size:.9rem}
.rel a{margin-right:1rem}
.foot{margin-top:1.4rem;color:var(--mut);font-size:.78rem;border-top:1px solid var(--line);padding-top:.7rem}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{border-bottom:1px solid var(--line);padding:.3rem .4rem;text-align:left}
</style></head><body>
<header>
 <h1>__TITLE__</h1><span class="sub">__SUB__</span>
</header>
<div class="wrap">
 <div class="badges">
  <span class="badge model">MODELED / SIMULATED</span>
  <span class="badge">0 runtime CDN</span>
  <span class="badge">locked 8 @ c7c0ba17</span>
  <span class="badge">&Lambda; = Conjecture 1</span>
  <span class="badge">OpenModelica + FMPy pattern (never Cameo/Dymola)</span>
  <span class="badge" id="signbadge">receipt: &hellip;</span>
 </div>
 <p class="lead">__LEAD__</p>
 <div class="ctl">
  __EXTRA_CTL__
  <button id="run">Run governed co-sim</button>
  <span class="sub" id="status">idle</span>
 </div>
 <div id="holo" data-mbse-nav="v1"></div>
 <div id="verdict"></div>
 <div class="grid" id="charts"></div>
 <div class="card" style="margin-top:1rem"><h3>Signed provenance receipt (DSSE)</h3>
  <div class="kv" id="rkv"></div>
  <pre id="receipt">run a co-sim to produce a signed receipt&hellip;</pre>
 </div>
 <div id="extra"></div>
 <div class="rel">Related surfaces: __OTHER__</div>
 <div class="foot">All outputs MODELED/SIMULATED &mdash; not physical hardware. Effectors SIMULATED, human-on-loop; no live vessel/weapon control. Signed receipts are integrity proofs for the simulation run, not operational data. Trust is bounded and NEVER 100%. Doctrine v11 LOCKED 749/14/163 @ kernel c7c0ba17 &middot; &Lambda; = Conjecture 1 (NEVER theorem) &middot; Khipu BFT = Conjecture 2 &middot; SLSA L1/L2 attested, L3 roadmap. Stack: OpenModelica + FMPy + SysML-v2 patterns &mdash; never Cameo/Dymola (proprietary).</div>
</div>
<script src="/static/shared/szl_holo3d.js"></script>
<script>
(function(){
 var API="__API__", KIND="__KIND__";
 var COLORS={demand:"#e74c3c",level:"#2980b9",valve:"#27ae60",speed:"#d4a444",alt:"#2980b9",state:"#27ae60"};
 function esc(s){return String(s).replace(/[&<>]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
 function svgChart(ch){
   var w=1100,h=190,pl=54,pr=14,pt=14,pb=26;
   var xs=ch.x,ys=ch.y; if(!xs||!xs.length){return "<svg></svg>";}
   var ymin=Math.min.apply(null,ys),ymax=Math.max.apply(null,ys);
   if(ch.band){ymin=Math.min(ymin,ch.band[0]);ymax=Math.max(ymax,ch.band[1]);}
   if(ch.ref!=null){ymin=Math.min(ymin,ch.ref);ymax=Math.max(ymax,ch.ref);}
   if(ymax-ymin<1e-6){ymax=ymin+1;}
   var xmin=xs[0],xmax=xs[xs.length-1]; if(xmax-xmin<1e-6){xmax=xmin+1;}
   function X(v){return pl+(w-pl-pr)*(v-xmin)/(xmax-xmin);}
   function Y(v){return pt+(h-pt-pb)*(1-(v-ymin)/(ymax-ymin));}
   var d=""; for(var i=0;i<xs.length;i++){d+=(i?"L":"M")+X(xs[i]).toFixed(1)+","+Y(ys[i]).toFixed(1);}
   var col=COLORS[ch.key]||"#d4a444";
   var s='<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none">';
   s+='<line class="axis" x1="'+pl+'" y1="'+(h-pb)+'" x2="'+(w-pr)+'" y2="'+(h-pb)+'"/>';
   s+='<line class="axis" x1="'+pl+'" y1="'+pt+'" x2="'+pl+'" y2="'+(h-pb)+'"/>';
   if(ch.band){s+='<line class="bandln" x1="'+pl+'" y1="'+Y(ch.band[0]).toFixed(1)+'" x2="'+(w-pr)+'" y2="'+Y(ch.band[0]).toFixed(1)+'"/>';
     s+='<line class="bandln" x1="'+pl+'" y1="'+Y(ch.band[1]).toFixed(1)+'" x2="'+(w-pr)+'" y2="'+Y(ch.band[1]).toFixed(1)+'"/>';}
   if(ch.ref!=null){s+='<line class="ref" x1="'+pl+'" y1="'+Y(ch.ref).toFixed(1)+'" x2="'+(w-pr)+'" y2="'+Y(ch.ref).toFixed(1)+'"/>';}
   s+='<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="1.4"/>';
   s+='<text class="lab" x="'+(pl-6)+'" y="'+(pt+9)+'" text-anchor="end">'+ymax.toFixed(2)+'</text>';
   s+='<text class="lab" x="'+(pl-6)+'" y="'+(h-pb)+'" text-anchor="end">'+ymin.toFixed(2)+'</text>';
   s+='<text class="lab" x="'+pl+'" y="'+(h-8)+'">t='+xmin.toFixed(0)+'</text>';
   s+='<text class="lab" x="'+(w-pr)+'" y="'+(h-8)+'" text-anchor="end">t='+xmax.toFixed(0)+'</text>';
   s+='</svg>';
   return s;
 }
 var scene=null;
 function holo(trust){
   try{
     if(!window.SZLHolo){return;}
     var el=document.getElementById("holo"); el.innerHTML="";
     scene=window.SZLHolo.createScene(el,{});
     scene.addTrustSphere({lambda:(trust==null?0.5:trust),label:"trust (MODELED)"});
     scene.addGraph({nodes:[{id:"req"},{id:"lean"},{id:"fmu"},{id:"rcpt"}],
       edges:[{from:"req",to:"lean"},{from:"lean",to:"fmu"},{from:"fmu",to:"rcpt"}]});
     scene.setLambda(trust==null?0.5:trust);
     scene.start();
   }catch(e){}
 }
 function render(res){
   var st=document.getElementById("status");
   if(!res||res.ok===false){
     st.textContent=res&&res.restraint?("Restraint gate refused: "+res.restraint.reason):"run returned no data";
     return;
   }
   st.textContent="done";
   var rc=res.receipt||{};
   document.getElementById("signbadge").innerHTML="receipt: "+(res.signed?"SIGNED (DSSE)":"UNSIGNED (honest \u2014 no key in runtime)");
   var charts=res.charts||(res.fmu_run&&res.fmu_run.charts)||[];
   var html=""; for(var i=0;i<charts.length;i++){html+='<div class="card"><h3>Chart '+(i+1)+' &mdash; '+esc(charts[i].title)+'</h3>'+svgChart(charts[i])+'</div>';}
   document.getElementById("charts").innerHTML=html;
   var rkv=document.getElementById("rkv"); rkv.innerHTML="";
   function kv(k,v){rkv.innerHTML+='<div class="kv-i"><span>'+esc(k)+':</span> <b>'+esc(v)+'</b></div>';}
   kv("receipt_sha256",(rc.receipt_sha256||"").slice(0,24)+"\u2026");
   kv("kernel",rc.kernel_sha||"c7c0ba17");
   kv("trust",rc.trust!=null?rc.trust:"\u2014");
   kv("signed",res.signed?"yes (ECDSA-P256 DSSE)":"no (honest)");
   document.getElementById("receipt").textContent=JSON.stringify({receipt:rc,dsse_signed:res.signed},null,2);
   var vd=document.getElementById("verdict");
   if(KIND==="pipeline"){
     var v=res.verdict||""; var cls=v==="VERIFIED"?"v-pass":"v-fail";
     vd.innerHTML='<div class="card"><h3>Verification thread</h3><div class="verdict '+cls+'">verdict: '+esc(v)+'</div>'+
       '<table><tr><th>stage</th><th>detail</th></tr>'+
       (res.stages||[]).map(function(s){return '<tr><td>'+esc(s.stage)+'</td><td>'+esc(JSON.stringify(s))+'</td></tr>';}).join("")+'</table></div>';
   } else {
     var pass=res.requirement_pass; var rr=(rc.result||{});
     vd.innerHTML='<div class="card"><h3>Requirement assertion</h3><div class="verdict '+(pass?"v-pass":"v-fail")+'">'+
       esc(rc.requirement||"")+' &mdash; '+(pass?"PASS":"FAIL")+'</div></div>';
   }
   var ex=document.getElementById("extra"); ex.innerHTML="";
   if(KIND==="sixdof" && res.decisions){
     ex.innerHTML='<div class="card" style="margin-top:1rem"><h3>Engagement decision log (SIMULATION OUTPUT \u2014 not fire control)</h3>'+
       '<table><tr><th>t [s]</th><th>state</th><th>note</th></tr>'+
       res.decisions.map(function(d){return '<tr><td>'+esc(d.t)+'</td><td>'+esc(d.state)+'</td><td>'+esc(d.note)+'</td></tr>';}).join("")+'</table></div>';
   }
   holo(rc.trust);
 }
 function run(){
   document.getElementById("status").textContent="running governed co-sim\u2026";
   var url=API; var sel=document.getElementById("reqsel");
   if(sel){url=API.replace(/requirement_id=[^&]*/,"requirement_id="+encodeURIComponent(sel.value));}
   fetch(url).then(function(r){return r.json();}).then(render).catch(function(e){
     document.getElementById("status").textContent="error: "+e;});
 }
 document.getElementById("run").addEventListener("click",run);
 holo(0.5); run();
})();
</script>
</body></html>"""
    extra_ctl = ""
    if kind == "pipeline":
        extra_ctl = ('<label class="sub">requirement '
                     '<select id="reqsel"><option value="WaterLevelReq">WaterLevelReq (water-tank)</option>'
                     '<option value="EngagementEnvelopeReq">EngagementEnvelopeReq (6DOF)</option></select></label>')
    return (tpl
            .replace("__TITLE__", cfg["title"])
            .replace("__SUB__", cfg["sub"])
            .replace("__LEAD__", cfg["lead"])
            .replace("__API__", cfg["api"])
            .replace("__KIND__", kind)
            .replace("__OTHER__", other_links)
            .replace("__EXTRA_CTL__", extra_ctl)
            .replace("__NSUP__", ns))


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Register the three MBSE HTML page routes (inserted before the SPA catch-all)
    + attach the idempotent nav-injection middleware. ADDITIVE + idempotent."""
    from starlette.responses import HTMLResponse
    from starlette.routing import Route

    registered: List[str] = []
    try:
        existing = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    except Exception:
        existing = set()

    pages = [
        ("/mbse", "watertank"),
        ("/mbse-6dof", "sixdof"),
        ("/mbse-pipeline", "pipeline"),
    ]

    def _mk(kind):
        html = _page_html(ns, kind)

        async def _serve(request):
            return HTMLResponse(html)
        return _serve

    for path, kind in pages:
        if path in existing:
            registered.append(path + " (already registered, skipped)")
            continue
        fn = _mk(kind)
        try:
            app.router.routes.insert(0, Route(path, fn, methods=["GET"]))
            registered.append("GET " + path)
        except Exception:
            try:
                app.add_api_route(path, fn, methods=["GET"], include_in_schema=False)
                registered.append("GET " + path + " (api_route)")
            except Exception:
                pass

    # attach nav injector (idempotent middleware)
    try:
        app.add_middleware(_make_injector())
        registered.append("MIDDLEWARE mbse-nav injector (v1)")
    except Exception:
        pass

    return {
        "registered": registered,
        "count": len(registered),
        "capability": "MBSE Digital-Twin pages + nav wire-up",
        "surfaces": [p for p, _, _ in _SURFACES],
        "data_label": "MODELED",
    }


# ---------------------------------------------------------------------------
# Self-test: build the three pages, assert they are 0-CDN (only the same-image
# /static/shared kit is referenced), carry honest labels, load the holo kit, and
# that nav injection + page routes are idempotent.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import re
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    for k in ("watertank", "sixdof", "pipeline"):
        h = _page_html("a11oy", k)
        # 0 runtime CDN: the only src/href external refs must be same-origin paths.
        for m in re.findall(r'(?:src|href)="([^"]+)"', h):
            assert not m.startswith("http://") and not m.startswith("https://"), \
                "0-CDN violation in %s page: %s" % (k, m)
        assert "/static/shared/szl_holo3d.js" in h, "must load the shared holo kit (%s)" % k
        assert "MODELED" in h, "honest MODELED label (%s)" % k
        assert "c7c0ba17" in h, "kernel sha shown (%s)" % k
        assert "Conjecture 1" in h, "Lambda = Conjecture 1 (%s)" % k
    s6 = _page_html("killinchu", "sixdof")
    assert "EFFECTORS SIMULATED" in s6 or "human-on-loop" in s6, "6DOF effectors must be simulated"

    SAMPLE_CONSOLE = (
        '<html><body><aside>'
        '<div class="nav-group">Operate</div>'
        '<div class="nav-item" data-view="x" onclick="go(\'x\')">'
        '<span class="ico">A</span>Board</div>'
        '<div class="side-foot">footer</div>'
        '</aside></body></html>'
    )

    async def _console(req):
        return HTMLResponse(SAMPLE_CONSOLE)

    app = Starlette(routes=[Route("/console", _console)])
    st1 = register(app, ns="a11oy")
    assert any("GET /mbse" in r for r in st1["registered"]), st1
    st2 = register(app, ns="a11oy")
    assert any("already registered" in r for r in st2["registered"]), st2
    c = TestClient(app)
    for path in ("/mbse", "/mbse-6dof", "/mbse-pipeline"):
        r = c.get(path)
        assert r.status_code == 200 and "MODELED" in r.text, (path, r.status_code)
    h1 = c.get("/console").text
    h2 = c.get("/console").text
    assert h1.count('data-mbse-nav="v1"') == h2.count('data-mbse-nav="v1"'), "nav idempotent"
    # one group + one item per surface = 1 + 3 = 4 markers
    assert h1.count('data-mbse-nav="v1"') == 1 + len(_SURFACES), "group + one item per surface"
    assert "Board" in h1 and "footer</div>" in h1, "must not remove existing nav/footer"
    for path, _, _ in _SURFACES:
        assert ("location.href='%s'" % path) in h1, "nav must link %s" % path
    assert h1 == h2, "second render byte-identical (idempotent)"

    print("szl_mbse_nav: ALL OK (3 pages served; 0 CDN; holo kit loaded; honest "
          "labels; nav group + %d surfaces; idempotent; additive)" % len(_SURFACES))
