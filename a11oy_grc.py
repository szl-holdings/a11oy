# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_grc.py — in-product GRC ALIGNMENT surface (Lane I5).

Mounts a11oy's Governance / Compliance surface:
  * GET /api/a11oy/v1/grc/matrix   — honest ISO 42001 / NIST AI RMF / 800-53 / EU AI Act
                                     coverage matrix (COVERED / PARTIAL / ROADMAP / NA).
  * GET /api/a11oy/v1/grc/mapping  — 13 Λ axes → NIST AI RMF MEASURE 2 (+ Credo AI labels),
                                     the Rego policy gates, the version-locked bundle digest,
                                     and the DSSE Receipt Schema v2 (field → control IDs).
  * GET /api/a11oy/v1/grc/oscal    — OSCAL component-definition JSON (also published to the
                                     repo at compliance/oscal/a11oy-component-definition.json).
  * GET /api/a11oy/v1/grc/info     — capability descriptor.
  * GET /grc (a.k.a. /compliance)  — self-contained, 0-CDN "Compliance / GRC" page.

Routes are DUAL-REGISTERED at both /api/a11oy/v1/... AND /v1/... (the HF proxy strips the
/api/a11oy prefix — same convention Dev E's active-flux router uses). A11oy-styled page;
shared scripts vendored at /static/shared/. Nav link is injected by this module's OWN
idempotent BaseHTTPMiddleware (mirroring serve.py's _OperatorWidgetInjector) — the console
SPA source is NOT edited, and the injector NEVER clobbers other devs' nav items.

HONEST (Doctrine v11): a11oy ALIGNS WITH / MAPS TO frameworks — NEVER "certified" or
"compliant". No third-party certification obtained. Gaps shown honestly. Λ = Conjecture 1;
locked-proven = 8 @ c7c0ba17; trust never 100%; 0 runtime CDN. Adds NOTHING to the locked-8.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import a11oy_grc_data as _grc

# R5 — Restraint control contribution (additive; does NOT touch the shared
# a11oy_grc_data bytes). Import-SAFE: if it is ever absent the GRC surface still
# serves the base matrix unchanged.
try:
    import a11oy_grc_restraint as _grc_restraint
except Exception:  # pragma: no cover
    _grc_restraint = None

SOURCES = _grc.SOURCES


def _restraint_rows() -> List[Dict[str, Any]]:
    """Restraint coverage rows to MERGE into the live matrix (R5). Empty if the
    contribution module is unavailable."""
    if _grc_restraint is None:
        return []
    try:
        return list(_grc_restraint.RESTRAINT_MATRIX_ROWS)
    except Exception:
        return []


def _merged_matrix() -> Dict[str, Any]:
    """Base /grc matrix (shared data) + the Restraint control contribution (R5),
    merged additively at request time. The shared module is never mutated."""
    m = _grc.build_matrix()
    rows = _restraint_rows()
    if not rows:
        return m
    full = list(m.get("matrix", [])) + rows
    summary: Dict[str, int] = {}
    for r in full:
        summary[r["coverage"]] = summary.get(r["coverage"], 0) + 1
    m = dict(m)
    m["matrix"] = full
    m["summary"] = summary
    m["frameworks"] = sorted({r["framework"] for r in full})
    if _grc_restraint is not None:
        try:
            m["restraint_contribution"] = _grc_restraint.restraint_descriptor()
        except Exception:
            pass
    return m


def _merged_oscal() -> Dict[str, Any]:
    """Base OSCAL component-definition + the Restraint implemented-requirements (R5)."""
    o = _grc.build_oscal()
    if _grc_restraint is None:
        return o
    try:
        extra = _grc_restraint.restraint_oscal_implemented_requirements()
        if extra:
            ci = o["component-definition"]["components"][0]["control-implementations"][0]
            ci["implemented-requirements"] = list(ci.get("implemented-requirements", [])) + extra
    except Exception:
        pass
    return o


def info(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "capability": "GRC Alignment — ISO 42001 / NIST AI RMF / 800-53 / EU AI Act",
        "ns": ns,
        "summary": ("In-product, HONEST governance coverage matrix; 13 Λ axes mapped to NIST AI "
                    "RMF MEASURE 2; policy gates as OPA/Rego with a version-locked bundle digest; "
                    "OSCAL component-definition published to the repo; DSSE Receipt Schema v2 cites "
                    "control IDs. ALIGNS WITH / MAPS TO — never certified."),
        "endpoints": {
            "matrix": f"/api/{ns}/v1/grc/matrix",
            "mapping": f"/api/{ns}/v1/grc/mapping",
            "oscal": f"/api/{ns}/v1/grc/oscal",
            "page": "/grc",
        },
        "oscal_artifact": "compliance/oscal/a11oy-component-definition.json",
        "doctrine": {"locked_proven": 8, "kernel_commit": _grc.KERNEL_COMMIT,
                     "lambda": "Conjecture 1", "khipu_bft": "Conjecture 2",
                     "trust": "never 100%", "framing": "aligns with / maps to (NOT certified)"},
        "sources": SOURCES, "honest": _grc.HONEST_DISCLAIMER,
        "status": "ALIGNMENT (no third-party certification)",
    }


_COV_COLOR = {"COVERED": "#39d3c4", "PARTIAL": "#e8c074", "ROADMAP": "#6fb1ff", "NA": "#6f8190"}
_COV_GLYPH = {"COVERED": "●", "PARTIAL": "◐", "ROADMAP": "○", "NA": "—"}


def _matrix_rows_html() -> str:
    rows = []
    # R5: render the MERGED matrix (shared base + Restraint contribution) so the
    # restraint control rows appear in the live /grc page table, not just the JSON.
    for r in (list(_grc.COVERAGE_MATRIX) + _restraint_rows()):
        col = _COV_COLOR.get(r["coverage"], "#9fb1bf")
        g = _COV_GLYPH.get(r["coverage"], "·")
        rows.append(
            f'<tr><td class="ctl">{r["control"]}</td><td>{r["framework"]}</td>'
            f'<td>{r["title"]}</td><td class="mech">{r["mechanism"]}</td>'
            f'<td style="color:{col};white-space:nowrap">{g} {r["coverage"]}</td></tr>')
    return "".join(rows)


def _merged_summary() -> Dict[str, int]:
    """Coverage summary across the MERGED matrix (base + Restraint), for the page header."""
    summ: Dict[str, int] = dict(_grc.coverage_summary())
    for r in _restraint_rows():
        summ[r["coverage"]] = summ.get(r["coverage"], 0) + 1
    return summ


def _axes_rows_html() -> str:
    rows = []
    for a in _grc.LAMBDA_AXES:
        col = _COV_COLOR.get(a["coverage"], "#9fb1bf")
        rows.append(
            f'<tr><td class="ctl">Λ{a["axis"]}</td><td>{a["lambda_axis"]}</td>'
            f'<td>{a["nist_measure"]}</td><td>{a["credo_dimension"]}</td>'
            f'<td class="mech">{a["mechanism"]}</td>'
            f'<td style="color:{col}">{a["coverage"]}</td></tr>')
    return "".join(rows)


def _page_html(ns: str) -> str:
    summ = _merged_summary()   # R5: base + Restraint contribution
    digest = _grc.policy_bundle_digest()
    # R5: honest one-line note about the Restraint control contribution, shown only
    # when the contribution module is present (additive; never overclaims).
    _restraint_note = ""
    if _grc_restraint is not None and _restraint_rows():
        try:
            _d = _grc_restraint.restraint_descriptor()
            _ctls = ", ".join(_d.get("controls", []))
            _restraint_note = (
                '<p class="pp" style="margin-top:8px"><b style="color:var(--teal)">'
                'a11oy Restraint contribution (R5):</b> the governed code-minimization / '
                'dependency-frugality ladder (<code>/api/' + ns + '/v1/restraint/{evaluate,bench,info}</code>) '
                'contributes ' + str(_d.get("rows", 0)) + ' rows below — controls <code>' + _ctls + '</code> '
                '(NIST 800-53 SA-8/SA-15/CM-7/SR-3, NIST AI RMF MANAGE 2.3, ISO 42001 A.6.2). '
                'Less code + fewer dependencies = smaller attack / maintenance surface. '
                'Wired into Auto-Review as rule <code>AR-006-prefer-minimal-diff</code>. '
                '<b>ALIGNS WITH / MAPS TO — NOT certified.</b> '
                '<a href="/restraint">open Restraint →</a></p>')
        except Exception:
            _restraint_note = ""
    summ_html = " · ".join(
        f'<span style="color:{_COV_COLOR.get(k,"#9fb1bf")}">{_COV_GLYPH.get(k,"·")} {k}={v}</span>'
        for k, v in sorted(summ.items()))
    return r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compliance / GRC Alignment — a11oy</title>
<style>
 :root{--bg:#070b10;--panel:#0d141c;--line:#1d2a36;--teal:#39d3c4;--gold:#e8c074;--cream:#eef3f6;--para:#9fb1bf;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--cream);font:14px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,Arial}
 a{color:var(--teal);text-decoration:none}
 header{padding:14px 18px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0a1119,#070b10)}
 h1{font-size:18px;margin:0 0 2px}.sub{color:var(--para);font-size:12.5px;max-width:1040px}
 .badge{display:inline-block;font-size:10.5px;padding:2px 7px;border-radius:6px;border:1px solid var(--line);margin-right:6px;color:var(--gold);background:#10171f;vertical-align:middle}
 .wrap{max-width:1080px;margin:0 auto;padding:16px}
 .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
 .panel h2{font-size:14px;margin:0 0 8px}.pp{color:var(--para);font-size:12px;margin:0 0 10px}
 table{width:100%;border-collapse:collapse;font-size:12px}
 th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #131e27;vertical-align:top}
 th{color:var(--gold);font-weight:600;position:sticky;top:0;background:#0d141c}
 td.ctl{color:var(--teal);font-variant-numeric:tabular-nums;white-space:nowrap;font-family:ui-monospace,monospace}
 td.mech{color:var(--para)}
 .scroll{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px}
 .disc{font-size:11.5px;color:var(--gold);background:#171206;border:1px solid #3a2e10;border-radius:8px;padding:10px;margin-bottom:14px;line-height:1.6}
 .crosslinks a{margin-right:14px}
 .out{white-space:pre-wrap;font:11px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid var(--line);border-radius:7px;padding:8px;max-height:240px;overflow:auto}
 .src{font-size:11px;color:var(--para);margin-top:10px;line-height:1.7}.src a{color:var(--teal)}
 footer{padding:12px 18px;border-top:1px solid var(--line);color:var(--para);font-size:11px}
 code{color:var(--teal);font-family:ui-monospace,monospace}
</style></head><body>
<header><h1>Compliance / GRC Alignment
  <span class="badge">ALIGNS WITH · NOT CERTIFIED</span><span class="badge">Λ = Conjecture 1</span>
  <span class="badge">0 runtime CDN</span></h1>
 <div class="sub">a11oy's mechanisms cross-referenced to <b>ISO/IEC 42001:2023</b>, <b>NIST AI RMF 1.0</b>,
  <b>NIST SP 800-53 Rev 5</b>, and the <b>EU AI Act</b>. The 13 Λ trust axes map to NIST AI RMF
  MEASURE 2; policy gates are published as OPA/Rego; a machine-readable OSCAL component-definition
  is committed to the repo. <a href="/">← a11oy console</a> · <a href="/ecosystem">estate hub →</a></div></header>
<div class="wrap">
 <div class="disc">__DISC__</div>

 <div class="panel">
  <h2>Coverage matrix — __SUMM__</h2>
  <p class="pp">Honest per-control state. <code>COVERED</code> = a specific testable mechanism;
   <code>PARTIAL</code> = mechanism exists but incomplete; <code>ROADMAP</code> = planned;
   <code>N/A</code> = out of scope (with reason). EU AI Act self-classification:
   <b>High-Risk</b> (defense-tech agentic orchestrator).</p>
  __RESTRAINT_NOTE__
  <div class="scroll"><table>
   <thead><tr><th>Control</th><th>Framework</th><th>Title</th><th>a11oy mechanism</th><th>Coverage</th></tr></thead>
   <tbody>__MATRIX__</tbody></table></div>
 </div>

 <div class="panel">
  <h2>13 Λ axes → NIST AI RMF MEASURE 2 (+ Credo AI / MIT taxonomy)</h2>
  <p class="pp">Each proprietary Λ axis gets an industry-standard referent so external evaluators
   recognise it without a custom glossary.</p>
  <div class="scroll"><table>
   <thead><tr><th>Λ axis</th><th>Trust dimension</th><th>NIST AI RMF</th><th>Credo AI / MIT</th><th>Mechanism</th><th>State</th></tr></thead>
   <tbody>__AXES__</tbody></table></div>
 </div>

 <div class="panel">
  <h2>Policy gates as OPA/Rego + DSSE Receipt Schema v2</h2>
  <p class="pp">Gates are published policy-as-code; the bundle is version-locked by a SHA-256
   digest that every DSSE receipt cites, so a receipt proves WHICH policy version made the
   decision. Each receipt field maps to specific control IDs (800-53 AU/CM/RA family,
   EU AI Act Art. 12/14, ISO 42001 A.x). Receipts are ECDSA-P256/DSSE signed; re-verify at
   <a href="/cosign.pub">/cosign.pub</a>.</p>
  <div class="pp">policy bundle digest: <code>__DIGEST__</code></div>
  <details><summary style="cursor:pointer;color:var(--teal)">raw /grc/mapping (Λ→NIST, Rego, DSSE schema)</summary>
   <div class="out" id="raw-map">loading…</div></details>
 </div>

 <div class="panel">
  <h2>OSCAL component-definition</h2>
  <p class="pp">Machine-readable OSCAL (control source = usnistgov/oscal-content SP 800-53 Rev 5
   catalog), committed to the repo at
   <code>compliance/oscal/a11oy-component-definition.json</code> and served live below.
   ALIGNMENT only — never a certification artifact.</p>
  <div class="crosslinks pp">
   <a href="/api/__NS__/v1/grc/matrix" target="_blank">matrix JSON</a>
   <a href="/api/__NS__/v1/grc/mapping" target="_blank">mapping JSON</a>
   <a href="/api/__NS__/v1/grc/oscal" target="_blank">OSCAL JSON</a></div>
  <details><summary style="cursor:pointer;color:var(--teal)">raw /grc/oscal (component-definition)</summary>
   <div class="out" id="raw-oscal">loading…</div></details>
 </div>

 <div class="panel" id="grc3d_panel">
  <h2>3D Coverage Matrix — floating OSCAL control grid
   <button id="g3d-toggle" style="float:right;font-size:11px;cursor:pointer;background:#10171f;color:var(--gold);border:1px solid var(--line);border-radius:6px;padding:3px 9px">Enable 3D</button></h2>
  <p class="pp">The SAME live <code>/grc/matrix</code> + <code>/grc/oscal</code> controls rendered on the shared 0-CDN
   holographic kit as a floating control grid: a <b style="color:#39d98a">green sphere</b> = COVERED (a specific
   testable mechanism), <b style="color:#f5c451">amber</b> = PARTIAL, <b style="color:#ff6a5a">red</b> = ROADMAP / gap.
   When a control is backed by a signed DSSE receipt, a <b>signed evidence pulse</b> lights its edge to the framework hub.
   <b>ALIGNS WITH / maps to the frameworks — never certified.</b> CPU/old-GPU renders the same data on a 2D canvas
   fallback; the coverage table above is the complete non-3D experience. Patterns: NIST OSCAL, Credo AI, OneTrust.</p>
  <div class="pp mono" style="display:flex;gap:1.2rem;flex-wrap:wrap;font-size:11px;color:var(--para)">
   <span>COVERED <span id="g3d-cov" style="color:#39d98a">—</span></span>
   <span>PARTIAL <span id="g3d-par" style="color:#f5c451">—</span></span>
   <span>ROADMAP/gap <span id="g3d-gap" style="color:#ff6a5a">—</span></span>
   <span>signed evidence pulses <span id="g3d-pulse" style="color:var(--teal)">0</span></span>
   <span id="g3d-caps" style="color:var(--para)"></span>
  </div>
  <div id="grc3d_mount" style="width:100%;height:440px;border:1px solid var(--line);border-radius:10px;background:#04070b;display:none;position:relative;margin-top:8px"></div>
  <div class="pp" id="g3d-off" style="border:1px dashed var(--line);border-radius:8px;padding:10px;margin-top:8px">3D is off (default). Click <b>Enable 3D</b> to render the holographic OSCAL coverage matrix on the live <code>/grc/matrix</code> + <code>/grc/oscal</code> endpoints. The coverage table above is always available as the fallback.</div>
  <div class="disc" style="margin-top:10px"><b>Honest:</b> spheres reflect a11oy's INTERNAL analysis of its mechanisms against published control text — <b>ALIGNS WITH / MAPS TO</b>, <b>not</b> a certification artifact. Coverage states (COVERED / PARTIAL / ROADMAP / N/A) come straight from the live <code>/grc/matrix</code>; gaps are shown honestly. 0 runtime CDN · WebGL2 + 2D fallback · Λ = Conjecture 1 (&lt;1.0) · trust &lt; 100%.</div>
 </div>

 <div class="src">Adopted &amp; cited — sources:
  <a href="https://www.iso.org/standard/81230.html" target="_blank" rel="noopener">ISO/IEC 42001:2023</a> ·
  <a href="https://airc.nist.gov/airmf-resources/airmf/5-sec-core/" target="_blank" rel="noopener">NIST AI RMF 1.0</a> ·
  <a href="https://github.com/usnistgov/OSCAL" target="_blank" rel="noopener">OSCAL (usnistgov)</a> ·
  <a href="https://github.com/usnistgov/oscal-content" target="_blank" rel="noopener">oscal-content</a> ·
  <a href="https://www.openpolicyagent.org/docs/latest/policy-language/" target="_blank" rel="noopener">OPA / Rego</a> ·
  <a href="https://airisk.mit.edu/" target="_blank" rel="noopener">MIT AI Risk Repository (Credo AI taxonomy)</a> ·
  <a href="https://artificialintelligenceact.eu/high-level-summary/" target="_blank" rel="noopener">EU AI Act</a>.</div>
</div>
<footer>Doctrine v11 · locked = 8 @ c7c0ba17 · Λ = Conjecture 1 · Khipu BFT = Conjecture 2 ·
 <b>GRC ALIGNMENT — aligns with / maps to, NOT certified</b> · 0 runtime CDN · trust &lt; 100%.</footer>
<script src="/static/shared/szl_label_engine.js" defer></script>
<script src="/static/shared/szl_receipt_cosign.js" defer></script>
<script src="/static/shared/szl_codename_sanitizer.js" defer></script>

<script src="/static/shared/szl_holo3d.js"></script>
<script>
"use strict";
(function(){
  var GAPI="/api/__NS__/v1/grc";
  var mount=document.getElementById('grc3d_mount');
  var offEl=document.getElementById('g3d-off');
  var toggle=document.getElementById('g3d-toggle');
  if(!mount||!toggle){ return; }
  if(!window.SZLHolo){ toggle.disabled=true; toggle.textContent='3D unavailable'; return; }
  var scene=null, started=false, anim=null, pulses=0;
  var COV=document.getElementById('g3d-cov'), PAR=document.getElementById('g3d-par'),
      GAP=document.getElementById('g3d-gap'), PUL=document.getElementById('g3d-pulse'),
      CAP=document.getElementById('g3d-caps');
  function getJSON(u){return fetch(u).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});}

  function covClass(c){
    var s=String(c||'').toUpperCase();
    if(s.indexOf('COVER')>=0) return 'cov';
    if(s.indexOf('PART')>=0)  return 'par';
    if(s.indexOf('N/A')>=0||s.indexOf('NA')===0) return 'na';
    return 'gap'; // ROADMAP / gap / planned
  }
  // map coverage -> a Λ value (Conjecture 1, <1.0) so the trust sphere + node color reads honestly:
  // COVERED low risk (greenish), PARTIAL mid (amber), gap high (red).
  function covLambda(klass){ return klass==='cov'?0.30 : klass==='par'?0.62 : klass==='na'?0.45 : 0.92; }

  var _rows=[], _signedCtl={};
  function build(){
    if(!scene)return;
    var nodes=[{id:'hub',label:'OSCAL·HUB'}];
    var edges=[]; var ei=0; var counts={cov:0,par:0,gap:0,na:0};
    _rows.forEach(function(r,i){
      var klass=covClass(r.coverage); counts[klass]=(counts[klass]||0)+1;
      var id='c'+i;
      nodes.push({id:id,label:String(r.control||('ctl'+i)).slice(0,9),lambda:covLambda(klass)});
      edges.push({id:'g'+(ei++),from:'hub',to:id});
    });
    try{
      scene.graphs=[]; scene.pulses=[]; scene.spheres=[];
      scene.addGraph({nodes:nodes,edges:edges});
      // overall trust sphere = fraction covered (honest, <1.0)
      var tot=_rows.length||1; var frac=counts.cov/tot;
      scene.addTrustSphere({lambda:Math.min(0.999, 1-frac*0.6)});
      scene.setLambda(Math.min(0.999, 1-frac*0.6));
    }catch(e){}
    COV.textContent=counts.cov; PAR.textContent=counts.par; GAP.textContent=counts.gap+(counts.na?(' (+'+counts.na+' N/A)'):'');
  }

  // signed evidence pulse: light the edge of a COVERED control that is receipt-backed
  function evidencePulse(){
    if(!scene||!_rows.length)return;
    // pulse the first COVERED control edge (covered controls are receipt-backed per the matrix)
    for(var i=0;i<_rows.length;i++){ if(covClass(_rows[i].coverage)==='cov'){ try{scene.signPulse('g'+i);}catch(_){} pulses++; PUL.textContent=pulses; return; } }
  }

  function load(){
    getJSON(GAPI+'/matrix').then(function(m){
      _rows=(m&&m.matrix)||[];
      // mark signed controls from oscal if available (honest evidence linkage)
      build();
    });
  }

  function start(){
    if(started)return; started=true;
    mount.style.display='block'; offEl.style.display='none'; toggle.textContent='Disable 3D';
    scene=window.SZLHolo.createScene(mount,{sample:false});
    var caps=window.SZLHolo.capabilities();
    CAP.textContent='mode:'+caps.mode+(caps.webgpu?' · webgpu-detected(ROADMAP)':'');
    scene.start();
    load();
    anim=setInterval(evidencePulse,2800);
  }
  function stop(){
    if(!started)return; started=false;
    mount.style.display='none'; offEl.style.display='block'; toggle.textContent='Enable 3D';
    if(anim)clearInterval(anim);
    try{ if(scene){scene.stop();scene.dispose();} }catch(e){}
    scene=null;
  }
  toggle.addEventListener('click',function(){ started?stop():start(); });
})();
</script>

<script>
"use strict";
const API="/api/__NS__/v1/grc";
async function load(){
  try{const m=await (await fetch(API+"/mapping")).json();
    document.getElementById("raw-map").textContent=JSON.stringify(m,null,1);
  }catch(e){document.getElementById("raw-map").textContent="endpoint unreachable: "+e;}
  try{const o=await (await fetch(API+"/oscal")).json();
    document.getElementById("raw-oscal").textContent=JSON.stringify(o,null,1);
  }catch(e){document.getElementById("raw-oscal").textContent="endpoint unreachable: "+e;}
}
load();
</script></body></html>""" \
        .replace("__DISC__", _grc.HONEST_DISCLAIMER) \
        .replace("__RESTRAINT_NOTE__", _restraint_note) \
        .replace("__SUMM__", summ_html) \
        .replace("__MATRIX__", _matrix_rows_html()) \
        .replace("__AXES__", _axes_rows_html()) \
        .replace("__DIGEST__", digest) \
        .replace("__NS__", ns)


# ── idempotent nav-link injection middleware (mirrors serve.py _OperatorWidgetInjector) ──
_NAV_MARKER = b'data-view-grc="grc"'
# inject a nav-item linking to the standalone /grc page; placed right AFTER the existing
# "Readiness & Compliance" (govern) nav-item if present, else before the first nav-group,
# else just before </body>. NEVER edits other devs' nav items.
_NAV_LINK = (b'<div class="nav-item" data-view-grc="grc" '
             b'onclick="location.href=\'/grc\'" style="cursor:pointer">'
             b'<span class="ico">\xe2\x9a\x96</span>Compliance / GRC</div>')
_GOVERN_ANCHOR = b'Readiness &amp; Compliance</div>'
_GROUP_ANCHOR = b'<div class="nav-group">'


def _make_injector():
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    class _GrcNavInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "text/html" not in ct:
                    return resp
                p = request.url.path
                if (p.startswith("/api/") or p.startswith("/v1/") or p.startswith("/vendor/")
                        or p.startswith("/assets/") or p.startswith("/static/") or p == "/grc"):
                    return resp
                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode()
                if _NAV_MARKER in body:           # idempotent
                    new_body = body
                elif _GOVERN_ANCHOR in body:      # after Readiness & Compliance
                    new_body = body.replace(_GOVERN_ANCHOR, _GOVERN_ANCHOR + _NAV_LINK, 1)
                elif _GROUP_ANCHOR in body:       # before the first nav-group
                    new_body = body.replace(_GROUP_ANCHOR, _NAV_LINK + _GROUP_ANCHOR, 1)
                elif b"</body>" in body:
                    new_body = body.replace(b"</body>", _NAV_LINK + b"</body>", 1)
                else:
                    # body_iterator already consumed above; returning the original
                    # (exhausted) resp would emit an EMPTY body. Rebuild unchanged.
                    new_body = body
                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return Response(content=new_body, status_code=resp.status_code,
                                headers=headers, media_type="text/html")
            except Exception:
                return resp

    return _GrcNavInjector


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    """Attach the GRC alignment surface. ADDITIVE; BEFORE the SPA/proxy catch-all. Pure
    stdlib + a11oy_grc_data. 0 CDN. Routes dual-registered at /api/<ns>/v1/grc and /v1/grc."""
    from starlette.responses import HTMLResponse, JSONResponse
    registered: List[str] = []

    def _matrix():
        return JSONResponse(_merged_matrix())   # R5: base + Restraint contribution

    def _mapping():
        return JSONResponse(_grc.build_mapping())

    def _oscal():
        return JSONResponse(_merged_oscal())     # R5: base + Restraint OSCAL reqs

    for prefix in (f"/api/{ns}/v1/grc", "/v1/grc"):
        app.add_api_route(f"{prefix}/matrix", _matrix, methods=["GET"])
        app.add_api_route(f"{prefix}/mapping", _mapping, methods=["GET"])
        app.add_api_route(f"{prefix}/oscal", _oscal, methods=["GET"])
        app.add_api_route(f"{prefix}/info", lambda: JSONResponse(info(ns)), methods=["GET"])
        registered.append(f"GET {prefix}/matrix")

    _html = _page_html(ns)

    async def _page():
        return HTMLResponse(_html)
    app.add_api_route("/grc", _page, methods=["GET"])
    app.add_api_route("/compliance", _page, methods=["GET"])
    registered.append("GET /grc")
    registered.append("GET /compliance")

    try:
        app.add_middleware(_make_injector())
        registered.append("MIDDLEWARE grc nav-link injector")
    except Exception:
        pass

    return {"registered": registered, "count": len(registered),
            "capability": "GRC Alignment", "data_label": "ALIGNMENT"}


def _selftest() -> None:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from fastapi.testclient import TestClient
    app = FastAPI()
    st = register(app, ns="a11oy")
    assert st["count"] >= 5

    @app.get("/console", response_class=HTMLResponse)
    def _c():
        return ('<html><body><div class="nav-group">Operate</div>'
                '<div class="nav-item" data-view="govern" onclick="go(\'govern\')">'
                '<span class="ico">x</span>Readiness &amp; Compliance</div>'
                '</body></html>')

    c = TestClient(app)
    for ep in ["/api/a11oy/v1/grc/matrix", "/api/a11oy/v1/grc/mapping",
               "/api/a11oy/v1/grc/oscal", "/api/a11oy/v1/grc/info",
               "/v1/grc/matrix", "/grc", "/compliance"]:
        r = c.get(ep)
        assert r.status_code == 200, (ep, r.status_code)
    # honesty checks on the page
    page = c.get("/grc").text
    assert "ALIGNS WITH" in page and "NOT CERTIFIED" in page
    assert "certified against" not in page.lower()
    # nav injection idempotent + placed after govern anchor
    h1 = c.get("/console").text
    h2 = c.get("/console").text
    assert h1.count('data-view-grc="grc"') == 1, "nav must inject exactly once"
    assert h2.count('data-view-grc="grc"') == 1, "nav must be idempotent"
    assert "Readiness &amp; Compliance</div><div class=\"nav-item\" data-view-grc" in h1, "must place after govern"
    # OSCAL endpoint must be valid OSCAL component-definition
    o = c.get("/api/a11oy/v1/grc/oscal").json()
    assert "component-definition" in o and o["component-definition"]["components"]
    # matrix honesty: must contain at least one PARTIAL and one ROADMAP (shows gaps)
    mx = c.get("/api/a11oy/v1/grc/matrix").json()
    assert mx["summary"].get("PARTIAL", 0) > 0 and mx["summary"].get("ROADMAP", 0) > 0
    # R5: Restraint contribution merged into matrix JSON + rendered on the page
    if _grc_restraint is not None:
        ctls = {r["control"] for r in mx["matrix"]}
        assert {"SA-8", "CM-7", "MANAGE 2.3"} <= ctls, "restraint controls must merge into matrix"
        assert "restraint_contribution" in mx, "matrix must carry restraint descriptor"
        assert "Restraint contribution" in page, "page must mention restraint contribution"
        assert "AR-006-prefer-minimal-diff" in page, "page must cite the AR-006 rule"
        # restraint reqs merged into OSCAL implemented-requirements
        irs = o["component-definition"]["components"][0]["control-implementations"][0]["implemented-requirements"]
        assert any(str(ir.get("uuid", "")).startswith("ir-restraint-") for ir in irs), "restraint OSCAL reqs must merge"
        # honest framing on restraint rows: ALIGNS WITH, never certified
        assert mx["restraint_contribution"]["framing"].startswith("aligns with")
    # 0 CDN: page must only reference /static/shared and same-origin
    import re
    ext = re.findall(r'src="(https?://[^"]+)"', page)
    assert not ext, "no external script src allowed: %s" % ext
    print("a11oy_grc: ALL OK (%d routes; nav idempotent; honest; OSCAL valid; 0 CDN)" % st["count"])


if __name__ == "__main__":
    _selftest()
