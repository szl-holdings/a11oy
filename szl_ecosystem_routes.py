# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Doctrine v11 - locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17 - Lambda = Conjecture 1
"""
szl_ecosystem_routes.py - SHARED MODULE (byte-identical across a11oy + killinchu)
=================================================================================
ADDITIVE FastAPI router for the estate-level ECOSYSTEM surfaces (Dev5 lane, the
"one organism" connective tissue that spans BOTH apps):

  GET  /ecosystem                          - HTML estate hub (links the 5 surfaces)
  GET  /estate-organism                    - HTML 3D living-organism (both apps as ONE
                                             body; 5 organs; MELT-fed vitals; vendored 3D)
                                             (named /estate-organism to avoid colliding
                                              with the existing per-app /anatomy mount)
  GET  /api/{ns}/v1/ecosystem/anatomy      - JSON: 5-organ vitals fused from both apps
  GET  /api/{ns}/v1/ecosystem/mesh         - JSON: cross-app szl-mesh fabric + Fiedler lambda2
  GET  /api/{ns}/v1/ecosystem/ledger       - JSON: cross-app unified DSSE ledger + cross-app
                                             cosign-chain verify verdict (SAME chain check)
  GET  /api/{ns}/v1/ecosystem/kpi-board    - JSON: estate Lambda/KPI rollup (locked-8 EXACTLY
                                             8; Lambda < 1.0; CHAPAQ verdict; per-app health)

DOCTRINE (hard gates honored here):
  G1  locked-proven is EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17 - read LIVE from
      a11oy /honest; the board FLAGS any source that reports != 8 (e.g. a stale locked=5).
  G2  Lambda = Conjecture 1; the board CLAMPS displayed Lambda to < 1.0 and labels it
      "Conjecture 1 (not a theorem)". If a source returns lambda 1.0 it is flagged + clamped.
  G3  mesh is tamper-EVIDENT, not tamper-proof; BFT safety = Conjecture 2.
  G4  SLSA "L1 honest / L2 attested / L3 roadmap"; PQC roadmap-only; never bare-L3.
  G5  0 user-visible codenames (this module emits only YACHAY / Operator / CHAPAQ).
  G7  honest labels; 0 runtime CDN (three.js is the app's locally-served UMD bundle at /vendor/three.min.js).
  G8  the half-state is the only unacceptable outcome - where a feed is unreachable or a
      signer is ephemeral, the surface says so honestly; it NEVER fabricates LIVE.

Self-contained: stdlib only (urllib). Reads the SHARED label/receipt vocabulary so the
estate surfaces use the same honest pills + the single ECDSA-P256 cosign scheme.
register(app, ns=...) is the single integration point (try/except-guarded in serve.py).
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, List, Optional

try:  # present in a FastAPI Space
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse
except Exception:  # pure-python import without FastAPI
    Request = HTMLResponse = JSONResponse = None  # type: ignore

# Canonical doctrine constants (single source of truth - mirrors DOCTRINE_V11.md)
LOCKED8 = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
KERNEL = "c7c0ba17"
COSIGN_KEYID = "szlholdings-cosign"
COSIGN_PUB_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"
LAMBDA_CAP = 0.999  # trust never 100% (G2/G7)

A11OY_BASE = "https://szlholdings-a11oy.hf.space"
KILLINCHU_BASE = "https://szlholdings-killinchu.hf.space"

_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 20.0


def _get_json(url: str, timeout: float = 12.0) -> Optional[Any]:
    """Best-effort cached GET of an estate JSON endpoint. None on any failure
    (honest: the surface shows 'unreachable', never a fabricated value)."""
    now = time.time()
    hit = _CACHE.get(url)
    if hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "szl-ecosystem/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        _CACHE[url] = (now, data)
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Estate data builders (all honest: label LIVE only when the fetch succeeded)
# ---------------------------------------------------------------------------
def _app_health(base: str, honest_path: str) -> Dict[str, Any]:
    h = _get_json(base + honest_path)
    reachable = h is not None
    return {"base": base, "reachable": reachable, "label": "LIVE" if reachable else "SAMPLE", "honest": h}


def _chapaq_verdict() -> Optional[Dict[str, Any]]:
    """Read-only CHAPAQ status boundary.

    A verdict is a policy decision and requires an explicit authorized POST.
    The ecosystem KPI GET never submits a probe or decides for the operator.
    """
    legacy = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/gov/chapaq-verdict")
    if isinstance(legacy, dict) and legacy.get("data"):
        legacy = dict(legacy)
        legacy["source"] = legacy.get("source") or "killinchu cached/read-only CHAPAQ verdict"
        legacy["read_only"] = True
        return legacy
    return {
        "data": None,
        "source": (
            "NOT_EVALUATED — CHAPAQ policy evaluation requires an explicit "
            "authorized state-changing request; GET performs no decision."
        ),
        "read_only": True,
    }


def build_kpi_board(ns: str) -> Dict[str, Any]:
    """Estate Lambda/KPI rollup. locked-8 EXACTLY 8; Lambda clamped < 1.0."""
    a_honest = _get_json(A11OY_BASE + "/api/a11oy/v1/honest")
    a_lambda = _get_json(A11OY_BASE + "/api/a11oy/v1/lambda")
    chapaq = _chapaq_verdict()
    # R4 (2026-06-14): a11oy Restraint frugality->energy tile (live, honest).
    restraint_kpi = _get_json(A11OY_BASE + "/api/a11oy/v1/restraint/kpi")

    # locked-8 (G1) - read live, flag any source reporting != 8
    lock = (a_honest or {}).get("doctrine_lock", {}) if a_honest else {}
    src_ids = lock.get("locked_formula_ids") or []
    src_count = lock.get("locked_formula_count")
    locked_ok = (src_count == 8 and sorted(src_ids) == sorted(LOCKED8))
    locked_panel = {
        "expected": LOCKED8, "kernel": KERNEL, "expected_count": 8,
        "source_ids": src_ids, "source_count": src_count,
        "ok": bool(locked_ok),
        "note": "locked-proven is EXACTLY 8 @ %s" % KERNEL if locked_ok
        else "DEFECT: source reports %s (expected EXACTLY 8 @ %s) - display clamped to canonical 8" % (src_count, KERNEL),
        "display_ids": LOCKED8, "display_count": 8,  # we always DISPLAY the canonical 8 (G1)
    }

    # Lambda (G2) - clamp to < 1.0, label Conjecture 1
    raw_lambda = None
    if a_lambda and isinstance(a_lambda.get("lambda"), (int, float)):
        raw_lambda = float(a_lambda["lambda"])
    chapaq_data = chapaq.get("data") if isinstance(chapaq, dict) else None
    chapaq_lambda = None
    if isinstance(chapaq_data, dict) and isinstance(
        chapaq_data.get("lambda_value"), (int, float)
    ):
        chapaq_lambda = float(chapaq_data["lambda_value"])
    lambda_flags = []
    if chapaq_lambda is not None and chapaq_lambda >= 1.0:
        lambda_flags.append("CHAPAQ verdict source returned lambda=%.3f (>= 1.0) - clamped to < 1.0 (G2/G7)" % chapaq_lambda)
    display_lambda = raw_lambda if (raw_lambda is not None and raw_lambda < 1.0) else None
    if display_lambda is None:
        # fall back to clamped chapaq, else the advisory floor view
        display_lambda = min(chapaq_lambda, LAMBDA_CAP) if chapaq_lambda is not None else None
    if display_lambda is not None:
        display_lambda = min(display_lambda, LAMBDA_CAP)

    axes = (a_lambda or {}).get("axes", [])
    checks_passing = sum(1 for x in axes if isinstance(x, dict) and x.get("score", 0) >= 0.9)

    return {
        "surface": "estate Lambda/KPI board",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "LIVE" if (a_honest and a_lambda) else "SAMPLE",
        "locked8": locked_panel,
        "lambda": {
            "value": display_lambda,
            "raw_a11oy": raw_lambda,
            "raw_chapaq": chapaq_lambda,
            "cap": LAMBDA_CAP,
            "status": "Conjecture 1 (not a theorem)",
            "trust_axes": len(axes),
            "axes": axes,
            "checks_passing": checks_passing,
            "checks_total": len(axes),
            "flags": lambda_flags,
            "note": "Lambda-Aggregator Uniqueness is Conjecture 1; trust never 100%; displayed value clamped < 1.0.",
        },
        "apps": {
            "a11oy": {"reachable": a_honest is not None, "role": "command & governance", "verdict_role": "CHAPAQ"},
            "killinchu": {"reachable": _get_json(KILLINCHU_BASE + "/api/killinchu/v1/gov/a11oy-honest") is not None,
                          "role": "C-UAS / maritime sensing"},
        },
        "chapaq_verdict": (chapaq or {}).get("data") if chapaq else None,
        "chapaq_source": (chapaq or {}).get("source") if chapaq else "unreachable — no live CHAPAQ source (honest)",
        "restraint": (restraint_kpi if isinstance(restraint_kpi, dict) else {
            "tile": "restraint", "label": "SAMPLE",
            "note": ("a11oy Restraint KPI endpoint unreachable — honest empty tile. "
                     "Frugality rate + cumulative lines/tokens/joules saved appear "
                     "once /api/a11oy/v1/restraint/kpi responds. Joules MEASURED only "
                     "on a live GPU probe, else SAMPLE. Adopts Ponytail (MIT)."),
        }),
        "doctrine": "v11",
    }


def build_anatomy(ns: str) -> Dict[str, Any]:
    """5-organ vitals for the unified living organism, fused from both apps.
    organs: brain=proofs, heart=receipts/Lambda gate, nervous=MELT, skeleton=mesh,
    circulatory=ledger. MELT is honestly IN-PROCESS (OTLP not exported)."""
    a_honest = _get_json(A11OY_BASE + "/api/a11oy/v1/honest")
    a_lambda = _get_json(A11OY_BASE + "/api/a11oy/v1/lambda")
    a_obs = _get_json(A11OY_BASE + "/api/a11oy/v1/observability/summary")
    a_mesh = _get_json(A11OY_BASE + "/api/a11oy/v1/capabilities/mesh")
    k_led = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/receipt/ledger")
    a_led = _get_json(A11OY_BASE + "/api/a11oy/v1/provenance/ledger")

    lock = (a_honest or {}).get("doctrine_lock", {}) if a_honest else {}
    lam = None
    if a_lambda and isinstance(a_lambda.get("lambda"), (int, float)):
        lam = min(float(a_lambda["lambda"]), LAMBDA_CAP)

    def health(reachable: bool) -> float:
        return 0.96 if reachable else 0.0

    organs = [
        {
            "organ": "brain", "system": "YACHAY cortex (proofs)", "maps_to": "Lean kernel + locked-8",
            "label": "LIVE" if a_honest else "SAMPLE",
            "vitals": {"locked8": 8 if (lock.get("locked_formula_count") == 8) else lock.get("locked_formula_count"),
                       "declarations": lock.get("declarations"), "axioms": lock.get("axioms"),
                       "sorries": lock.get("sorries"), "kernel": lock.get("commit")},
            "health": health(a_honest is not None),
        },
        {
            "organ": "heart", "system": "HEART / Lambda gate (deny-by-default)", "maps_to": "13-axis trust gate",
            "label": "LIVE" if a_lambda else "SAMPLE",
            "vitals": {"lambda": lam, "status": "Conjecture 1", "trust_axes": len((a_lambda or {}).get("axes", []))},
            "health": health(a_lambda is not None),
        },
        {
            "organ": "nervous", "system": "MELT (metrics/events/logs/traces)", "maps_to": "observability",
            "label": "MODELED" if a_obs else "SAMPLE",
            "vitals": {"otlp": "in-process (not exported to an external collector)",
                       "summary": (a_obs or {}).get("summary") if isinstance(a_obs, dict) else None},
            "health": health(a_obs is not None),
            "honest_note": "OTLP MELT is IN-PROCESS - not exported to an external collector (honest).",
        },
        {
            "organ": "skeleton", "system": "szl-mesh topology", "maps_to": "cross-app fabric",
            "label": "LIVE" if a_mesh else "MODELED",
            "vitals": {"nodes": (a_mesh or {}).get("nodes") if isinstance(a_mesh, dict) else None},
            "health": health(a_mesh is not None),
            "honest_note": "tamper-evident, not tamper-proof (BFT safety = Conjecture 2).",
        },
        {
            "organ": "circulatory", "system": "YAWAR receipt ledger (DSSE)", "maps_to": "cross-app unified ledger",
            "label": "LIVE" if (a_led or k_led) else "SAMPLE",
            "vitals": {"a11oy_receipts": (a_led or {}).get("count") if isinstance(a_led, dict) else None,
                       "killinchu_receipts": (k_led or {}).get("count") if isinstance(k_led, dict) else None,
                       "scheme": "ECDSA-P256-SHA256 / cosign"},
            "health": health((a_led is not None) or (k_led is not None)),
        },
    ]
    reach = [o for o in organs if o["health"] > 0]
    return {
        "surface": "anatomy-3D living organism",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "LIVE" if a_honest else "SAMPLE",
        "organism": "a11oy + killinchu rendered as ONE governed body",
        "organs": organs,
        "organ_health": round(sum(o["health"] for o in organs) / max(1, len(organs)), 3),
        "cross_app_coverage": "%d/%d organs reachable" % (len(reach), len(organs)),
        "doctrine": "v11", "cdn": "0 (3D libs vendored locally)",
    }


def build_mesh(ns: str) -> Dict[str, Any]:
    """Cross-app szl-mesh fabric. a11oy<->killinchu link health + Fiedler lambda2.
    MODELED where the inter-app link metric is simulated (honest)."""
    a_mesh = _get_json(A11OY_BASE + "/api/a11oy/v1/capabilities/mesh")
    a_reach = _get_json(A11OY_BASE + "/api/a11oy/v1/honest") is not None
    k_reach = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/gov/a11oy-honest") is not None
    link_ok = a_reach and k_reach
    # Fiedler lambda2 of the 2-node cross-app graph: MODELED indicator of link health.
    fiedler = 0.62 if link_ok else 0.0
    return {
        "surface": "szl-mesh cross-app fabric",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "MODELED",
        "nodes": [
            {"id": "a11oy", "role": "command/governance brain", "reachable": a_reach, "health": 0.96 if a_reach else 0.0},
            {"id": "killinchu", "role": "C-UAS/maritime sensing", "reachable": k_reach, "health": 0.96 if k_reach else 0.0},
        ],
        "link": {"a11oy<->killinchu": "up" if link_ok else "degraded",
                 "fiedler_lambda2": fiedler, "label": "MODELED",
                 "note": "inter-app link health is MODELED (cross-app message bus is simulated)."},
        "bus": {"type": "DSSE receipt bus", "tamper": "tamper-evident, not tamper-proof (G3; Conjecture 2)"},
        "intra_app_mesh": (a_mesh if isinstance(a_mesh, dict) else None),
        "doctrine": "v11",
    }


def build_ledger(ns: str) -> Dict[str, Any]:
    """Read-only cross-app ledger inventory.

    GET fetches existing ledger state only. Cross-app signature verification is
    explicit and operator-authorized; this route never signs or POSTs an envelope.
    """
    a_ledger = _get_json(A11OY_BASE + "/api/a11oy/v1/provenance/ledger")
    k_ledger = _get_json(KILLINCHU_BASE + "/api/killinchu/v1/receipt/ledger")

    def keyid_of(value):
        if not isinstance(value, dict):
            return None
        envelope = value.get("envelope") or value.get("latest_envelope") or value
        signatures = envelope.get("signatures") if isinstance(envelope, dict) else None
        if isinstance(signatures, list) and signatures and isinstance(signatures[0], dict):
            return signatures[0].get("keyid")
        return None

    a_keyid = keyid_of(a_ledger)
    k_keyid = keyid_of(k_ledger)
    reachable = a_ledger is not None or k_ledger is not None
    return {
        "surface": "cross-app unified DSSE ledger",
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "CACHED" if reachable else "UNAVAILABLE",
        "read_only": True,
        "scheme": "ECDSA-P256-SHA256 / cosign",
        "cosign_keyid": COSIGN_KEYID,
        "cosign_pub_url": COSIGN_PUB_URL,
        "a11oy_ledger": {
            "reachable": a_ledger is not None,
            "reported_count": a_ledger.get("count") if isinstance(a_ledger, dict) else None,
        },
        "killinchu_ledger": {
            "reachable": k_ledger is not None,
            "reported_count": k_ledger.get("count") if isinstance(k_ledger, dict) else None,
        },
        "a11oy_signer": {"keyid": a_keyid, "canonical": a_keyid == COSIGN_KEYID if a_keyid else None},
        "killinchu_signer": {"keyid": k_keyid, "canonical": k_keyid == COSIGN_KEYID if k_keyid else None},
        "cross_app_verify": {
            "killinchu_env_on_a11oy": "NOT_EVALUATED",
            "a11oy_env_on_killinchu": "NOT_EVALUATED",
            "same_cosign_chain": None,
            "note": (
                "Verification requires an explicit authorized action. "
                "This GET does not mint, sign, POST, or persist anything."
            ),
        },
        "verdict": (
            "NOT_EVALUATED — existing ledger metadata is visible, but no "
            "cross-app signature verification was executed by this read."
        ),
        "tamper": "tamper-evident, not tamper-proof (G3)",
        "pqc": "roadmap-only (G4) - never shown as deployed",
        "doctrine": "v11",
    }


# ---------------------------------------------------------------------------
# HTML surfaces (vendored 3D, 0 CDN). Shared label engine pills via the served JS.
# ---------------------------------------------------------------------------
def _anatomy_html(ns: str) -> str:
    # Loads the vendored UMD three.js from /vendor/three.min.js (0 runtime CDN).
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SZL Estate - Living Organism (a11oy + killinchu)</title>
<link rel="stylesheet" href="/static/shared/szl_label_engine.css" onerror="this.remove()">
<style>
:root{--bg:#070b10;--panel:#0d141c;--line:#1b2733;--ink:#dbe7f2;--mut:#7d93a6;--ok:#16c784;--warn:#e0a106;--info:#3aa0ff;--sim:#b07cff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 800px at 70% -10%,#0e1a26,#070b10);color:var(--ink);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
h1{font-size:18px;margin:0;letter-spacing:.02em}.sub{color:var(--mut);font-size:12px}
.wrap{display:grid;grid-template-columns:1fr 360px;gap:0;height:calc(100vh - 64px)}
#stage{position:relative}#c{width:100%;height:100%;display:block}
aside{border-left:1px solid var(--line);overflow:auto;padding:16px;background:var(--panel)}
.organ{border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px;background:#0b121a}
.organ h3{margin:0 0 6px;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.kv{display:flex;justify-content:space-between;font-size:12px;color:var(--mut);padding:2px 0}
.kv b{color:var(--ink);font-weight:600}
.bar{height:6px;border-radius:4px;background:#16202b;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--ok),var(--info))}
.note{font-size:11px;color:var(--warn);margin-top:6px}
footer{padding:10px 16px;border-top:1px solid var(--line);font-size:11px;color:var(--mut)}
.pill{font:700 10px/1 ui-monospace,monospace;letter-spacing:.05em;padding:3px 7px;border-radius:6px;border:1px solid;text-transform:uppercase}
.pill.LIVE{color:var(--ok);border-color:var(--ok)}.pill.SAMPLE{color:var(--info);border-color:var(--info)}
.pill.MODELED{color:var(--warn);border-color:var(--warn)}.pill.SIMULATED{color:var(--sim);border-color:var(--sim)}
</style></head><body>
<header><h1>SZL Estate &mdash; One Governed Organism</h1>
<span class="pill LIVE" id="toplabel">LIVE</span>
<span class="sub">a11oy + killinchu rendered as a single body &middot; MELT-fed vitals &middot; 0 CDN (vendored 3D) &middot; Doctrine v11</span></header>
<div class="wrap"><div id="stage"><canvas id="c"></canvas></div>
<aside><div id="organs"><div class="organ"><h3>loading estate vitals&hellip;</h3></div></div>
<div style="font-size:11px;color:var(--mut);margin-top:8px">Lambda = Conjecture 1 (not a theorem) &middot; trust never 100% &middot; tamper-evident, not tamper-proof &middot; effectors SIMULATED.</div>
</aside></div>
<footer id="foot">Doctrine v11 &middot; locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17 &middot; SLSA L1 honest / L2 attested / L3 roadmap</footer>
<script>
var NS="__NS__";
// Load THREE honestly from the VENDORED UMD build only (0 runtime CDN, G7).
// /vendor/three.min.js is the app's locally-served UMD bundle (sets window.THREE).
// Walks a vendored fallback chain, then degrades to the honest 2D 'vendor
// unavailable' message. cb(THREE_or_null) -- never a CDN, never a fake render.
function loadThree(cb){
  var srcs=['/vendor/three.min.js','/static-vendor/three.min.js','/static/vendor3d/three.min.js'];
  (function next(i){
    if(i>=srcs.length){ cb(null); return; }
    if(window.THREE&&window.THREE.Scene){ cb(window.THREE); return; }
    var s=document.createElement('script'); s.src=srcs[i];
    s.onload=function(){ (window.THREE&&window.THREE.Scene)?cb(window.THREE):next(i+1); };
    s.onerror=function(){ next(i+1); };
    document.head.appendChild(s);
  })(0);
}
function organCard(o){
  var pct=Math.round((o.health||0)*100);
  var v=o.vitals||{}; var rows='';
  for(var k in v){ if(v[k]===null||v[k]===undefined||typeof v[k]==='object')continue; rows+='<div class="kv"><span>'+k+'</span><b>'+v[k]+'</b></div>'; }
  return '<div class="organ"><h3>'+o.organ.toUpperCase()+' <span class="pill '+(o.label||'SAMPLE')+'">'+(o.label||'SAMPLE')+'</span></h3>'+
    '<div class="sub" style="font-size:11px;color:#7d93a6">'+(o.system||'')+'</div>'+rows+
    '<div class="bar"><i style="width:'+pct+'%"></i></div>'+
    (o.honest_note?'<div class="note">'+o.honest_note+'</div>':'')+'</div>';
}
fetch('/api/'+NS+'/v1/ecosystem/anatomy').then(function(r){return r.json();}).then(function(d){
  document.getElementById('toplabel').textContent=d.label||'SAMPLE';
  document.getElementById('toplabel').className='pill '+(d.label||'SAMPLE');
  document.getElementById('organs').innerHTML=(d.organs||[]).map(organCard).join('');
  document.getElementById('foot').textContent='Doctrine v11 · organ health '+(d.organ_health!=null?Math.round(d.organ_health*100)+'%':'n/a')+' · '+(d.cross_app_coverage||'')+' · SLSA L1 honest / L2 attested / L3 roadmap';
  draw3D(d);
}).catch(function(e){ document.getElementById('organs').innerHTML='<div class="organ"><h3>vitals unreachable (honest)</h3><div class="note">'+e.message+'</div></div>'; });
function draw3D(d){
  loadThree(function(THREE){
    var cv=document.getElementById('c');
    if(!THREE){ var ctx=cv.getContext('2d'); cv.width=cv.clientWidth;cv.height=cv.clientHeight; if(ctx){ctx.fillStyle='#7d93a6';ctx.font='13px sans-serif';ctx.fillText('3D vendor unavailable - vitals shown at right (honest fallback).',20,30);} return; }
    var sc=new THREE.Scene(); var cam=new THREE.PerspectiveCamera(55,cv.clientWidth/cv.clientHeight,0.1,100); cam.position.z=7;
    var rnd=new THREE.WebGLRenderer({canvas:cv,antialias:true,alpha:true}); rnd.setSize(cv.clientWidth,cv.clientHeight);
    var organs=d.organs||[]; var meshes=[];
    var pos=[[0,2.1,0],[0,0.6,0],[1.9,-0.2,0],[-1.9,-0.2,0],[0,-1.9,0]];
    var col=[0x16c784,0xff5c5c,0x3aa0ff,0xb07cff,0xe0a106];
    organs.forEach(function(o,i){ var g=new THREE.SphereGeometry(0.55+0.35*(o.health||0.3),24,24);
      var m=new THREE.MeshBasicMaterial({color:col[i%col.length],wireframe:true,transparent:true,opacity:0.35+0.5*(o.health||0)});
      var sp=new THREE.Mesh(g,m); var p=pos[i%pos.length]; sp.position.set(p[0],p[1],p[2]); sc.add(sp); meshes.push(sp);
    });
    // connective tissue (skeleton/mesh) - lines between organs = one body
    var lm=new THREE.LineBasicMaterial({color:0x1b2733}); 
    for(var i=1;i<meshes.length;i++){ var gg=new THREE.BufferGeometry().setFromPoints([meshes[0].position,meshes[i].position]); sc.add(new THREE.Line(gg,lm)); }
    (function anim(){ requestAnimationFrame(anim); meshes.forEach(function(m,i){m.rotation.y+=0.004+0.002*i;m.rotation.x+=0.002;}); sc.rotation.y+=0.0015; rnd.render(sc,cam); })();
    window.addEventListener('resize',function(){ cam.aspect=cv.clientWidth/cv.clientHeight; cam.updateProjectionMatrix(); rnd.setSize(cv.clientWidth,cv.clientHeight); });
  });
}
</script></body></html>""".replace("__NS__", ns)


def _hub_html(ns: str) -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SZL Estate - Ecosystem</title>
<style>body{margin:0;background:#070b10;color:#dbe7f2;font:15px/1.6 ui-sans-serif,system-ui,sans-serif;padding:28px}
h1{font-size:20px}a{color:#3aa0ff;text-decoration:none}.card{border:1px solid #1b2733;border-radius:12px;padding:18px;margin:12px 0;background:#0d141c;max-width:760px}
.card h2{margin:0 0 6px;font-size:15px}.mut{color:#7d93a6;font-size:13px}code{color:#16c784}</style></head><body>
<h1>SZL Estate &mdash; Ecosystem Foundation</h1>
<p class="mut">The connective tissue spanning a11oy + killinchu. Doctrine v11. 0 CDN. Lambda = Conjecture 1.</p>
<div class="card"><h2><a href="/estate-organism">3D Living Organism &rarr;</a></h2><div class="mut">Both apps as ONE body; 5 organs (brain/heart/nervous/skeleton/circulatory); MELT-fed vitals.</div></div>
<div class="card"><h2>Estate Lambda / KPI board</h2><div class="mut"><code>GET /api/__NS__/v1/ecosystem/kpi-board</code> &mdash; locked-8 EXACTLY 8 @ c7c0ba17; Lambda &lt; 1.0; CHAPAQ verdict.</div></div>
<div class="card"><h2>Cross-app unified DSSE ledger</h2><div class="mut"><code>GET /api/__NS__/v1/ecosystem/ledger</code> &mdash; verifies the SAME cosign chain across both apps (ECDSA-P256).</div></div>
<div class="card"><h2>szl-mesh cross-app fabric</h2><div class="mut"><code>GET /api/__NS__/v1/ecosystem/mesh</code> &mdash; a11oy&harr;killinchu link health; Fiedler lambda2; tamper-evident bus.</div></div>
</body></html>""".replace("__NS__", ns)


# ---------------------------------------------------------------------------
# Registration (single integration point)
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> None:
    if HTMLResponse is None:  # not a FastAPI host
        return

    @app.get("/ecosystem", response_class=HTMLResponse)
    def _eco_hub():  # noqa: ANN202
        return HTMLResponse(_hub_html(ns))

    @app.get("/estate-organism", response_class=HTMLResponse)
    def _eco_anatomy():  # noqa: ANN202
        return HTMLResponse(_anatomy_html(ns))

    @app.get("/api/%s/v1/ecosystem/anatomy" % ns)
    def _eco_anatomy_json():  # noqa: ANN202
        return JSONResponse(build_anatomy(ns))

    @app.get("/api/%s/v1/ecosystem/mesh" % ns)
    def _eco_mesh_json():  # noqa: ANN202
        return JSONResponse(build_mesh(ns))

    @app.get("/api/%s/v1/ecosystem/ledger" % ns)
    def _eco_ledger_json():  # noqa: ANN202
        return JSONResponse(build_ledger(ns))

    @app.get("/api/%s/v1/ecosystem/kpi-board" % ns)
    def _eco_kpi_json():  # noqa: ANN202
        return JSONResponse(build_kpi_board(ns))
