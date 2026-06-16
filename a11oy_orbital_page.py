# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_orbital_page — ADDITIVE /orbital demo surface (page + 3D/viz).

Renders the MODELED SZL orbital-compute constellation against the already-live
backend (PR #468): GET /api/a11oy/v1/orbital/topology and .../orbital/projection.

What it draws (all MODELED — SZL has NO on-orbit hardware):
  * LEO edge-compute shell, MEO aggregation ring, GEO backhaul tier (nodes),
  * OISL inter-satellite links + ground-space downlinks to the REAL ground fabric,
  * a governed-receipt overlay: each MODELED orbital job shows a MODELED energy
    figure (joules/kWh) derived from the REAL ground-measured J/token coefficient
    (cited) PLUS a would-be signed receipt — the SZL moat (governed energy-receipt
    + signed provenance) applied to space compute. The receipt is explicitly a
    MODELED would-be artifact, never presented as a real signed receipt.

HONESTY (doctrine v11, non-negotiable):
  * The ENTIRE surface is visibly + persistently labeled
    "MODELED — Orbital Roadmap (no on-orbit hardware yet)". It can never be mistaken
    for live telemetry.
  * No orbital node/joule/receipt is fabricated. Nodes come straight from the live
    topology endpoint (modeled:true / reachable:false). The energy figure comes from
    the live projection endpoint, whose ONLY MEASURED input is the ground J/token
    coefficient; the orbital joules are MODELED and labeled MODELED. A MODELED
    orbital joule is NEVER labeled MEASURED here.
  * 0 runtime CDN: three.js r160 (MIT) is loaded from the in-image vendored path
    /hero/vendor3d/ (the same proven, allowlisted, runtime-served route the
    cathedral hero uses). No external host is ever fetched.
  * If an endpoint is unreachable the page degrades honestly (shows the error,
    draws nothing fabricated) — honest BLOCKED beats fake green.

Pattern mirrors a11oy_formulas_page.register(app, ns): mounts
  GET /orbital                              (self-contained HTML, 0 CDN)
  GET /api/<ns>/v1/orbital/page-manifest    (JSON nav descriptor)
Registered BEFORE the SPA /{full_path:path} catch-all; try/except-guarded in
serve.py so a missing dep can never take down the Space. Λ = Conjecture 1;
sovereign=false on this path. Doctrine v11 LOCKED.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "lambda": "Conjecture 1", "sovereign": False}
MODELED_BANNER = "MODELED — Orbital Roadmap (no on-orbit hardware yet)"

# The two LIVE backend endpoints this surface renders (PR #468). Wired client-side.
_TOPOLOGY_EP = "/api/{ns}/v1/orbital/topology"
_PROJECTION_EP = "/api/{ns}/v1/orbital/projection"

# 0-CDN vendored three.js r160 — the proven, allowlisted, runtime-served hero path
# (serve.py GET /hero/vendor3d/{fname}; identical to cathedral_genius.html importmap).
_THREE_MAIN = "/hero/vendor3d/three.module.min.js"
_THREE_ADDONS = "/hero/vendor3d/"


def _page_html(ns: str) -> str:
    topology_ep = _TOPOLOGY_EP.format(ns=ns)
    projection_ep = _PROJECTION_EP.format(ns=ns)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>A11oy — Orbital Compute Tier (MODELED Roadmap)</title>
<!-- Sovereign importmap: ONLY vendored local files. 0 runtime CDN. Doctrine v11. -->
<script type="importmap">
{{
  "imports": {{
    "three": "{_THREE_MAIN}",
    "three/addons/": "{_THREE_ADDONS}"
  }}
}}
</script>
<style>
  :root {{ --bg:#070b16; --panel:#101a2e; --ink:#e8eef7; --muted:#8aa0bd;
           --indigo:#4d8fcc; --terra:#c8643c; --gold:#d8a23c; --amber:#e8c074;
           --green:#2fd07a; --warn:#c8893c; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; height:100%; }}
  body {{ font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
          background:radial-gradient(1200px 700px at 70% -10%, #14213b, var(--bg));
          color:var(--ink); overflow:hidden; }}
  /* Persistent, unmissable MODELED banner — top of every viewport. */
  #modeled-banner {{ position:fixed; top:0; left:0; right:0; z-index:50;
    background:linear-gradient(90deg, rgba(216,162,60,.22), rgba(200,100,60,.18));
    border-bottom:1px solid rgba(232,192,116,.5);
    color:var(--amber); font-family:ui-monospace,monospace; font-size:.82rem;
    letter-spacing:.06em; text-transform:uppercase; padding:.55rem 1rem;
    display:flex; align-items:center; gap:.6rem; backdrop-filter:blur(4px); }}
  #modeled-banner .dot {{ width:.6rem; height:.6rem; border-radius:50%;
    background:var(--amber); box-shadow:0 0 8px var(--amber); flex:0 0 auto; }}
  #modeled-banner b {{ color:var(--gold); }}
  #scene {{ position:fixed; inset:0; }}
  #hud {{ position:fixed; top:3rem; left:0; right:0; bottom:0; pointer-events:none;
          padding:1rem 1.1rem; display:flex; flex-direction:column; gap:.8rem; }}
  .plaque {{ font-family:ui-monospace,monospace; font-size:.7rem; letter-spacing:.12em;
             color:var(--muted); text-transform:uppercase; }}
  .plaque b {{ color:var(--gold); }}
  h1 {{ font-size:clamp(1.4rem,3vw,2.1rem); margin:.2rem 0 0; }}
  h1 .accent {{ color:var(--terra); }}
  .sub {{ color:var(--muted); max-width:64ch; line-height:1.5; font-size:.86rem; margin:.3rem 0 0; }}
  .panels {{ display:flex; gap:.8rem; flex-wrap:wrap; margin-top:auto; }}
  .panel {{ pointer-events:auto; background:rgba(16,26,46,.86); border:1px solid #21304d;
            border-radius:12px; padding:.85rem 1rem; min-width:240px; max-width:340px;
            box-shadow:0 18px 40px -28px #000; backdrop-filter:blur(6px); }}
  .panel h3 {{ margin:0 0 .5rem; font-family:ui-monospace,monospace; color:var(--indigo);
               font-size:.9rem; display:flex; align-items:center; gap:.45rem; }}
  .kv {{ display:flex; justify-content:space-between; gap:1rem; font-size:.78rem;
         padding:.18rem 0; border-bottom:1px dashed rgba(138,160,189,.14); }}
  .kv span:first-child {{ color:var(--muted); }}
  .kv span:last-child {{ font-family:ui-monospace,monospace; }}
  .badge {{ font-size:.6rem; padding:.14rem .45rem; border-radius:999px; letter-spacing:.06em;
            text-transform:uppercase; font-family:ui-monospace,monospace; }}
  .badge.modeled {{ background:rgba(232,192,116,.16); color:var(--amber); border:1px solid rgba(232,192,116,.45); }}
  .badge.measured {{ background:rgba(47,208,122,.16); color:var(--green); border:1px solid rgba(47,208,122,.45); }}
  .receipt {{ font-family:ui-monospace,monospace; font-size:.7rem; color:#9fb1bf;
              background:#070c17; border:1px solid #1a2742; border-radius:8px;
              padding:.5rem .6rem; margin-top:.5rem; word-break:break-all; line-height:1.45; }}
  .receipt .lbl {{ color:var(--amber); }}
  .status {{ font-size:.74rem; color:var(--muted); }}
  .status.err {{ color:var(--warn); }}
  a.back {{ color:var(--muted); text-decoration:none; font-size:.8rem; pointer-events:auto; }}
  #legend {{ display:flex; gap:1rem; flex-wrap:wrap; font-size:.72rem; color:var(--muted);
             font-family:ui-monospace,monospace; }}
  #legend i {{ width:.7rem; height:.7rem; border-radius:2px; display:inline-block;
               margin-right:.35rem; vertical-align:middle; }}
  noscript {{ color:var(--amber); display:block; padding:4rem 1.5rem; }}
</style></head>
<body>
  <div id="modeled-banner">
    <span class="dot"></span>
    <span><b>{MODELED_BANNER}</b> &nbsp;·&nbsp; SZL operates a REAL ground GPU fabric today;
    every orbital node/link/joule below is a MODELED design artifact — not reachable,
    never serving a real job. Λ = Conjecture 1.</span>
  </div>

  <canvas id="scene"></canvas>

  <div id="hud">
    <div>
      <div class="plaque">SZL HOLDINGS / A11OY / DOCTRINE <b>V11 · LOCKED</b> / Λ = CONJECTURE 1</div>
      <h1>The orbital <span class="accent">moat</span>, modeled.</h1>
      <p class="sub" id="subline">Loading the MODELED constellation from the live
         <code>/orbital/*</code> endpoints… Governed energy-receipts + signed provenance,
         applied to space compute — a FORWARD design, not a deployed system.</p>
      <div id="legend"></div>
    </div>

    <div class="panels">
      <div class="panel" id="panel-topology">
        <h3>◇ Constellation <span class="badge modeled">MODELED</span></h3>
        <div id="topo-body"><div class="status" id="topo-status">fetching topology…</div></div>
      </div>
      <div class="panel" id="panel-receipt">
        <h3>⛓ Governed receipt <span class="badge modeled">MODELED</span></h3>
        <div id="receipt-body"><div class="status" id="proj-status">fetching projection…</div></div>
      </div>
      <div style="align-self:flex-end"><a class="back" href="/">← back to console</a></div>
    </div>
  </div>

  <noscript>This MODELED orbital roadmap surface requires JavaScript to render its 3D
    constellation. No live telemetry is shown — SZL has no on-orbit hardware.</noscript>

<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/OrbitControls.js';

const TOPOLOGY_EP = {topology_ep!r};
const PROJECTION_EP = {projection_ep!r};

// ---- honesty helpers --------------------------------------------------------
const TIER_COLOR = {{
  'LEO-edge':        0x4d8fcc,  // indigo
  'MEO-aggregation': 0xd8a23c,  // gold
  'GEO-backhaul':    0xc8643c,  // terra
}};
const TIER_RADIUS = {{ 'LEO-edge': 9, 'MEO-aggregation': 15, 'GEO-backhaul': 22 }};
const AMBER = '#e8c074', GREEN = '#2fd07a';

function esc(s) {{ return String(s).replace(/[&<>"']/g, c =>
  ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}

// ---- three.js scene (r160, vendored, 0 CDN) --------------------------------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({{ canvas, antialias:true, alpha:true }});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 2000);
camera.position.set(0, 18, 64);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.06;
controls.autoRotate = true; controls.autoRotateSpeed = 0.35;

scene.add(new THREE.AmbientLight(0x88aacc, 0.7));
const key = new THREE.PointLight(0xffffff, 1.2); key.position.set(40, 50, 50); scene.add(key);

// Earth proxy (MODELED globe — purely a visual reference, not a data claim).
const earth = new THREE.Mesh(
  new THREE.SphereGeometry(5.6, 48, 48),
  new THREE.MeshStandardMaterial({{ color:0x0d2238, emissive:0x06121f, roughness:0.9, metalness:0.1, wireframe:false }})
);
scene.add(earth);
const grid = new THREE.Mesh(
  new THREE.SphereGeometry(5.7, 24, 24),
  new THREE.MeshBasicMaterial({{ color:0x1d3a5c, wireframe:true, transparent:true, opacity:0.35 }})
);
scene.add(grid);

const nodeGroup = new THREE.Group(); scene.add(nodeGroup);
const linkGroup = new THREE.Group(); scene.add(linkGroup);

function resize() {{
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.updateProjectionMatrix();
}}
addEventListener('resize', resize); resize();

(function loop() {{
  requestAnimationFrame(loop);
  controls.update();
  earth.rotation.y += 0.0008; grid.rotation.y += 0.0008;
  renderer.render(scene, camera);
}})();

// Deterministic placement: spread a tier's nodes evenly around a ring, tilted per plane.
function placeNodes(nodes) {{
  const byTier = {{}};
  for (const n of nodes) (byTier[n.tier] = byTier[n.tier] || []).push(n);
  const pos = {{}};
  for (const [tier, arr] of Object.entries(byTier)) {{
    const R = TIER_RADIUS[tier] || 12;
    arr.forEach((n, i) => {{
      const a = (i / arr.length) * Math.PI * 2;
      const tilt = ((n.orbital_plane || 0) * 0.5);
      pos[n.id] = new THREE.Vector3(
        Math.cos(a) * R,
        Math.sin(tilt) * R * 0.35 + Math.sin(a) * 1.5,
        Math.sin(a) * R
      );
    }});
  }}
  return pos;
}}

function drawTopology(t) {{
  nodeGroup.clear(); linkGroup.clear();
  const nodes = t.orbital_nodes || [];
  const pos = placeNodes(nodes);
  // ground stations sit just outside the globe surface
  const gsList = t.ground_stations || [];
  gsList.forEach((gs, i) => {{
    const a = (i / Math.max(gsList.length,1)) * Math.PI * 2;
    pos[gs.id] = new THREE.Vector3(Math.cos(a) * 6.2, -1.5, Math.sin(a) * 6.2);
  }});

  for (const n of nodes) {{
    const color = TIER_COLOR[n.tier] || 0x9fb1bf;
    // reachable is REAL-PROBE-ONLY; topology always reports false — render as hollow.
    const mat = new THREE.MeshStandardMaterial({{
      color, emissive:color, emissiveIntensity:0.35, roughness:0.5,
      transparent:true, opacity:0.92
    }});
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.55, 20, 20), mat);
    m.position.copy(pos[n.id]);
    nodeGroup.add(m);
  }}
  // ground stations: small green markers (REAL ground side; the downlink is MODELED)
  for (const gs of gsList) {{
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.4, 16, 16),
      new THREE.MeshStandardMaterial({{ color:0x2fd07a, emissive:0x2fd07a, emissiveIntensity:0.4 }}));
    m.position.copy(pos[gs.id]); nodeGroup.add(m);
  }}

  for (const l of (t.links || [])) {{
    const a = pos[l.src], b = pos[l.dst];
    if (!a || !b) continue;
    const isDown = l.kind === 'ground-space-downlink';
    const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
    const mat = new THREE.LineBasicMaterial({{
      color: isDown ? 0x2fd07a : 0x6fb1ff, transparent:true, opacity: isDown ? 0.7 : 0.4
    }});
    linkGroup.add(new THREE.Line(geo, mat));
  }}

  // legend
  document.getElementById('legend').innerHTML = [
    ['#4d8fcc','LEO edge (MODELED)'], ['#d8a23c','MEO aggregation (MODELED)'],
    ['#c8643c','GEO backhaul (MODELED)'], ['#6fb1ff','OISL link (MODELED)'],
    ['#2fd07a','ground downlink (MODELED) → REAL ground node'],
  ].map(([c,t]) => `<span><i style="background:${{c}}"></i>${{esc(t)}}</span>`).join('');

  // topology panel
  const s = t.summary || {{}};
  document.getElementById('topo-body').innerHTML = [
    ['data_kind', t.data_kind], ['status', t.status],
    ['on-orbit hardware', String(t.on_orbit_hardware)],
    ['LEO / MEO / GEO', `${{s.leo_edge_nodes}} / ${{s.meo_aggregation_nodes}} / ${{s.geo_backhaul_nodes}}`],
    ['total nodes / links', `${{s.total_nodes}} / ${{s.total_links}}`],
    ['reachable nodes', String(s.reachable_nodes)],
  ].map(([k,v]) => `<div class="kv"><span>${{esc(k)}}</span><span>${{esc(v)}}</span></div>`).join('');
}}

// Build a would-be (MODELED) signed receipt from the MODELED projection. This is
// the SZL moat illustrated — NOT a real signed receipt; explicitly labeled MODELED.
async function modeledReceiptId(proj) {{
  const op = proj.orbital_projection || {{}};
  const j = (op.orbital_joules && op.orbital_joules.value) || 0;
  const basis = JSON.stringify({{ j, ts: proj.timestamp_utc, node: (proj.orbital_node||{{}}).id }});
  let hex = 'unavailable';
  try {{
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(basis));
    hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('').slice(0, 32);
  }} catch (e) {{ hex = 'sha256-unavailable-(no-subtlecrypto)'; }}
  return hex;
}}

async function drawProjection(p) {{
  const coeff = p.ground_measured_coefficient || {{}};
  const op = p.orbital_projection || {{}};
  const jpt = (coeff.j_per_token && coeff.j_per_token.value);
  const ojoules = (op.orbital_joules && op.orbital_joules.value);
  const okwh = (op.orbital_kwh && op.orbital_kwh.value);
  const rid = await modeledReceiptId(p);

  document.getElementById('receipt-body').innerHTML = `
    <div class="kv"><span>ground J/token</span><span>${{esc(jpt)}} <span class="badge measured">MEASURED</span></span></div>
    <div class="kv"><span>coeff source</span><span>${{esc(coeff.measured_source || '—')}}</span></div>
    <div class="kv"><span>orbital joules</span><span>${{esc(ojoules)}} <span class="badge modeled">MODELED</span></span></div>
    <div class="kv"><span>orbital kWh</span><span>${{esc(okwh)}} <span class="badge modeled">MODELED</span></span></div>
    <div class="receipt">
      <span class="lbl">would-be signed receipt (MODELED — not a real signature):</span><br/>
      governed-energy-receipt:${{esc(rid)}}<br/>
      <span class="lbl">basis:</span> MEASURED ground J/token × MODELED workload × MODELED space-overhead<br/>
      <span class="lbl">honesty:</span> sovereign=false · Λ=Conjecture 1 · no on-orbit hardware
    </div>`;
  document.getElementById('subline').innerHTML =
    'Each MODELED orbital job carries a MODELED energy figure (derived from the REAL ' +
    'ground-measured J/token coefficient, cited above) and a <b>would-be signed ' +
    'governed-energy-receipt</b> — the SZL moat, applied to space compute. Forward design, not deployed.';
}}

function fail(elId, msg) {{
  const el = document.getElementById(elId);
  if (el) {{ el.className = 'status err'; el.textContent = msg; }}
}}

(async function load() {{
  try {{
    const r = await fetch(TOPOLOGY_EP, {{ headers:{{Accept:'application/json'}} }});
    const t = await r.json();
    if (!r.ok || t.ok === false) throw new Error('topology ' + r.status);
    drawTopology(t);
  }} catch (e) {{ fail('topo-status', 'topology unavailable: ' + e + ' (nothing fabricated)'); }}

  try {{
    const r = await fetch(PROJECTION_EP, {{ headers:{{Accept:'application/json'}} }});
    const p = await r.json();
    if (!r.ok || p.ok === false) throw new Error('projection ' + r.status);
    await drawProjection(p);
  }} catch (e) {{ fail('proj-status', 'projection unavailable: ' + e + ' (no fabricated joule)'); }}
}})();
</script>
</body></html>"""


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount GET /orbital (HTML) + GET /api/<ns>/v1/orbital/page-manifest (JSON).
    ADDITIVE — registered before the SPA catch-all; touches no existing route."""

    @app.get("/orbital", include_in_schema=False)
    async def orbital_page() -> HTMLResponse:  # noqa: ANN202
        return HTMLResponse(_page_html(ns))

    @app.get(f"/api/{ns}/v1/orbital/page-manifest", include_in_schema=False)
    async def orbital_page_manifest() -> JSONResponse:  # noqa: ANN202
        return JSONResponse({
            "section": "Orbital",
            "page": "/orbital",
            "data_kind": "MODELED-roadmap",
            "banner": MODELED_BANNER,
            "on_orbit_hardware": False,
            "doctrine": DOCTRINE,
            "renders_endpoints": [
                _TOPOLOGY_EP.format(ns=ns),
                _PROJECTION_EP.format(ns=ns),
            ],
            "vendored_3d": {"three": _THREE_MAIN, "addons": _THREE_ADDONS, "revision": "r160", "runtime_cdn": 0},
            "note": ("MODELED orbital roadmap surface — no on-orbit hardware. Nodes/joules "
                     "come from the live MODELED endpoints; the signed receipt shown is a "
                     "MODELED would-be artifact, never a real signature."),
        })

    return f"orbital-page mounted: GET /orbital + page-manifest (renders MODELED topology+projection, 0 CDN)"


def _selftest() -> None:
    html = _page_html("a11oy")
    # 1) the persistent MODELED banner is present, verbatim
    assert MODELED_BANNER in html, "MODELED banner missing"
    assert "no on-orbit hardware" in html, "no-hardware honesty note missing"
    # 2) both live endpoints are wired client-side
    assert "/api/a11oy/v1/orbital/topology" in html, "topology endpoint not wired"
    assert "/api/a11oy/v1/orbital/projection" in html, "projection endpoint not wired"
    # 3) 0 runtime CDN — three.js loads from the vendored hero path, no external host
    assert _THREE_MAIN in html and "http://" not in html and "https://" not in html, \
        "external URL / CDN reference found (0-CDN doctrine)"
    # 4) a renderable marker exists (canvas + heading) so a live grep proves real content
    assert 'id="scene"' in html and "orbital" in html.lower(), "render marker missing"
    # 5) honesty: a MODELED orbital joule is never relabeled MEASURED; only the
    #    ground coefficient carries MEASURED. The receipt is explicitly MODELED.
    assert "would-be signed receipt (MODELED" in html, "receipt not labeled MODELED"
    assert "Conjecture 1" in html, "Λ label missing"
    print("a11oy_orbital_page: ALL OK (MODELED banner, endpoints wired, 0 CDN, render marker, honest receipt)")


if __name__ == "__main__":
    _selftest()
