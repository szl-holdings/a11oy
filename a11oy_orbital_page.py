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

RENDER RESILIENCE + MOBILE (2026-07 hardening):
  * The data panels are populated by a CLASSIC (non-module) script that fetches the
    two endpoints INDEPENDENTLY of three.js. A WebGL failure (mobile GPU, headless,
    lost context) or a three.js import failure can therefore NEVER blank the page —
    the constellation + receipt facts always render. The 3D scene is progressive
    enhancement inside a bounded stage with an honest "3D unavailable" fallback.
  * Every fetch carries an AbortController timeout so a hung endpoint degrades to an
    honest error instead of freezing forever on "fetching…".
  * Layout is a normal scrollable, responsive document (no fullscreen overflow-hidden
    canvas): a max-width column, a bounded 3D stage, and an auto-fit panel grid that
    stacks to one column on small screens.

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

# ---------------------------------------------------------------------------
# The page is a plain string template with @@TOKEN@@ placeholders (NOT an f-string)
# so the CSS/JS braces stay literal and cannot be mangled. Only five values are
# injected — the two endpoints, the two vendored three.js paths, and the banner.
# There is deliberately ZERO "http://"/"https://" anywhere (0-CDN doctrine): every
# asset is a same-origin relative path.
# ---------------------------------------------------------------------------
_PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>A11oy — Orbital Compute Tier (MODELED Roadmap)</title>
<!-- Sovereign importmap: ONLY vendored local files. 0 runtime CDN. Doctrine v11. -->
<script type="importmap">
{
  "imports": {
    "three": "@@THREE_MAIN@@",
    "three/addons/": "@@THREE_ADDONS@@"
  }
}
</script>
<style>
  :root { --bg:#070b16; --panel:#101a2e; --ink:#e8eef7; --muted:#8aa0bd;
          --indigo:#4d8fcc; --terra:#c8643c; --gold:#d8a23c; --amber:#e8c074;
          --green:#2fd07a; --warn:#c8893c; --line:#21304d; }
  * { box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { margin:0; min-height:100%;
         font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
         background-color:var(--bg);
         background-image:radial-gradient(1200px 700px at 70% -10%, #14213b, var(--bg));
         color:var(--ink); }
  /* Persistent, unmissable MODELED banner — sticky at the top of the scroll. */
  #modeled-banner { position:sticky; top:0; z-index:50;
    background:linear-gradient(90deg, rgba(216,162,60,.28), rgba(200,100,60,.22));
    border-bottom:1px solid rgba(232,192,116,.5);
    color:var(--amber); font-family:ui-monospace,monospace; font-size:.78rem;
    letter-spacing:.04em; padding:.6rem .9rem;
    display:flex; align-items:flex-start; gap:.55rem; backdrop-filter:blur(4px); }
  #modeled-banner .dot { width:.6rem; height:.6rem; border-radius:50%; margin-top:.2rem;
    background:var(--amber); box-shadow:0 0 8px var(--amber); flex:0 0 auto; }
  #modeled-banner b { color:var(--gold); text-transform:uppercase; letter-spacing:.06em; }
  .wrap { max-width:1120px; margin:0 auto; padding:1.1rem 1.1rem 3rem; }
  .plaque { font-family:ui-monospace,monospace; font-size:.66rem; letter-spacing:.14em;
            color:var(--muted); text-transform:uppercase; }
  .plaque b { color:var(--gold); }
  h1 { font-size:clamp(1.5rem,5vw,2.4rem); margin:.35rem 0 0; line-height:1.1; }
  h1 .accent { color:var(--terra); }
  .sub { color:var(--muted); max-width:66ch; line-height:1.55; font-size:.92rem; margin:.5rem 0 0; }
  .sub b { color:var(--amber); }
  .sub code { color:var(--indigo); }
  /* Bounded 3D stage (progressive enhancement) — never a fullscreen void. */
  #stage { position:relative; margin:1.15rem 0 0; border:1px solid var(--line);
           border-radius:16px; overflow:hidden; background:#060a13;
           height:clamp(260px, 48vh, 460px); }
  #scene { display:block; width:100%; height:100%; }
  #stage-fallback { position:absolute; inset:0; display:none; align-items:center;
    justify-content:center; text-align:center; padding:1.5rem; color:var(--muted);
    font-family:ui-monospace,monospace; font-size:.82rem; line-height:1.6; }
  #stage-fallback b { color:var(--amber); }
  #legend { display:flex; gap:.6rem 1.1rem; flex-wrap:wrap; font-size:.7rem; color:var(--muted);
            font-family:ui-monospace,monospace; margin:.85rem 0 0; }
  #legend i { width:.7rem; height:.7rem; border-radius:2px; display:inline-block;
              margin-right:.35rem; vertical-align:middle; }
  .panels { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 300px), 1fr));
            gap:.9rem; margin-top:1.2rem; }
  .panel { background:rgba(16,26,46,.86); border:1px solid var(--line);
           border-radius:14px; padding:1rem 1.05rem; box-shadow:0 18px 40px -30px #000; }
  .panel h3 { margin:0 0 .6rem; font-family:ui-monospace,monospace; color:var(--indigo);
              font-size:.92rem; display:flex; align-items:center; gap:.45rem; flex-wrap:wrap; }
  .kv { display:flex; justify-content:space-between; gap:1rem; font-size:.82rem;
        padding:.3rem 0; border-bottom:1px dashed rgba(138,160,189,.14); }
  .kv:last-child { border-bottom:0; }
  .kv span:first-child { color:var(--muted); }
  .kv span:last-child { font-family:ui-monospace,monospace; text-align:right; word-break:break-word; }
  .badge { font-size:.58rem; padding:.14rem .45rem; border-radius:999px; letter-spacing:.06em;
           text-transform:uppercase; font-family:ui-monospace,monospace; white-space:nowrap; }
  .badge.modeled { background:rgba(232,192,116,.16); color:var(--amber); border:1px solid rgba(232,192,116,.45); }
  .badge.measured { background:rgba(47,208,122,.16); color:var(--green); border:1px solid rgba(47,208,122,.45); }
  .receipt { font-family:ui-monospace,monospace; font-size:.72rem; color:#9fb1bf;
             background:#070c17; border:1px solid #1a2742; border-radius:10px;
             padding:.6rem .7rem; margin-top:.7rem; word-break:break-all; line-height:1.5; }
  .receipt .lbl { color:var(--amber); }
  .status { font-size:.8rem; color:var(--muted); }
  .status.err { color:var(--warn); }
  .foot { margin-top:1.6rem; display:flex; gap:1rem; flex-wrap:wrap; align-items:center; }
  a.back { color:var(--muted); text-decoration:none; font-size:.85rem;
           border:1px solid var(--line); border-radius:999px; padding:.42rem .95rem; }
  a.back:hover { color:var(--ink); border-color:var(--indigo); }
  noscript { color:var(--amber); display:block; padding:1.5rem 0; }
  @media (max-width:560px) {
    #modeled-banner { font-size:.72rem; }
    .wrap { padding:1rem .9rem 2.5rem; }
    .sub { font-size:.88rem; }
    #stage { height:clamp(220px, 42vh, 340px); }
  }
</style></head>
<body>
  <div id="modeled-banner">
    <span class="dot"></span>
    <span><b>@@MODELED_BANNER@@</b> &nbsp;·&nbsp; SZL operates a REAL ground GPU fabric today;
    every orbital node/link/joule below is a MODELED design artifact — not reachable,
    never serving a real job. &Lambda; = Conjecture 1.</span>
  </div>

  <main class="wrap">
    <div class="plaque">SZL HOLDINGS / A11OY / DOCTRINE <b>V11 · LOCKED</b> / &Lambda; = CONJECTURE 1</div>
    <h1>The orbital <span class="accent">moat</span>, modeled.</h1>
    <p class="sub" id="subline">Loading the MODELED constellation from the live
       <code>/orbital/*</code> endpoints… Governed energy-receipts + signed provenance,
       applied to space compute — a FORWARD design, not a deployed system.</p>

    <div id="stage">
      <canvas id="scene"></canvas>
      <div id="stage-fallback">
        <div><b>3D view unavailable on this device.</b><br/>
        The full MODELED constellation data is shown below — nothing is hidden.</div>
      </div>
    </div>
    <div id="legend"></div>

    <div class="panels">
      <div class="panel" id="panel-topology">
        <h3>&#9671; Constellation <span class="badge modeled">MODELED</span></h3>
        <div id="topo-body"><div class="status" id="topo-status">fetching topology…</div></div>
      </div>
      <div class="panel" id="panel-receipt">
        <h3>&#9939; Governed receipt <span class="badge modeled">MODELED</span></h3>
        <div id="receipt-body"><div class="status" id="proj-status">fetching projection…</div></div>
      </div>
    </div>

    <div class="foot"><a class="back" href="/">&larr; back to console</a></div>
  </main>

  <noscript>This MODELED orbital roadmap surface renders its constellation with
    JavaScript. No live telemetry is shown — SZL has no on-orbit hardware.</noscript>

<!-- DATA (classic script): fetches + renders the panels INDEPENDENTLY of three.js.
     Guarantees the constellation + receipt always show, even with no WebGL. -->
<script>
(function () {
  "use strict";
  var TOPOLOGY_EP = "@@TOPOLOGY_EP@@";
  var PROJECTION_EP = "@@PROJECTION_EP@@";

  window.OrbitalData = { topology: null, projection: null };
  var topoCbs = [];
  // Let the (optional) 3D layer subscribe to the topology the moment it lands.
  window.onOrbitalTopology = function (cb) {
    if (window.OrbitalData.topology) { try { cb(window.OrbitalData.topology); } catch (e) {} }
    else { topoCbs.push(cb); }
  };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(id) { return document.getElementById(id); }
  function fail(id, msg) { var e = el(id); if (e) { e.className = 'status err'; e.textContent = msg; } }

  // Fetch with an AbortController timeout so a hung endpoint degrades honestly
  // instead of freezing forever on "fetching…".
  function fetchJSON(url) {
    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 12000) : null;
    var opts = { headers: { Accept: 'application/json' } };
    if (ctrl) { opts.signal = ctrl.signal; }
    return fetch(url, opts).then(function (r) {
      if (timer) { clearTimeout(timer); }
      return r.json().then(function (j) { return { ok: r.ok, status: r.status, json: j }; });
    }).catch(function (e) { if (timer) { clearTimeout(timer); } throw e; });
  }

  function renderTopology(t) {
    var s = t.summary || {};
    el('topo-body').innerHTML = [
      ['data_kind', t.data_kind], ['status', t.status],
      ['on-orbit hardware', String(t.on_orbit_hardware)],
      ['LEO / MEO / GEO', s.leo_edge_nodes + ' / ' + s.meo_aggregation_nodes + ' / ' + s.geo_backhaul_nodes],
      ['total nodes / links', s.total_nodes + ' / ' + s.total_links],
      ['reachable nodes', String(s.reachable_nodes)]
    ].map(function (kv) {
      return '<div class="kv"><span>' + esc(kv[0]) + '</span><span>' + esc(kv[1]) + '</span></div>';
    }).join('');

    el('legend').innerHTML = [
      ['#4d8fcc', 'LEO edge (MODELED)'], ['#d8a23c', 'MEO aggregation (MODELED)'],
      ['#c8643c', 'GEO backhaul (MODELED)'], ['#6fb1ff', 'OISL link (MODELED)'],
      ['#2fd07a', 'ground downlink (MODELED) → REAL ground node']
    ].map(function (c) {
      return '<span><i style="background:' + c[0] + '"></i>' + esc(c[1]) + '</span>';
    }).join('');
  }

  // Build a would-be (MODELED) signed receipt from the MODELED projection. This is
  // the SZL moat illustrated — NOT a real signed receipt; explicitly labeled MODELED.
  function modeledReceiptId(proj) {
    var op = proj.orbital_projection || {};
    var j = (op.orbital_joules && op.orbital_joules.value) || 0;
    var basis = JSON.stringify({ j: j, ts: proj.timestamp_utc, node: (proj.orbital_node || {}).id });
    if (!(window.crypto && crypto.subtle)) {
      return Promise.resolve('sha256-unavailable-(no-subtlecrypto)');
    }
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(basis)).then(function (buf) {
      return Array.from(new Uint8Array(buf)).map(function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('').slice(0, 32);
    }).catch(function () { return 'sha256-unavailable'; });
  }

  function renderProjection(p) {
    var coeff = p.ground_measured_coefficient || {};
    var op = p.orbital_projection || {};
    var jpt = (coeff.j_per_token && coeff.j_per_token.value);
    var ojoules = (op.orbital_joules && op.orbital_joules.value);
    var okwh = (op.orbital_kwh && op.orbital_kwh.value);
    return modeledReceiptId(p).then(function (rid) {
      el('receipt-body').innerHTML =
        '<div class="kv"><span>ground J/token</span><span>' + esc(jpt) + ' <span class="badge measured">MEASURED</span></span></div>' +
        '<div class="kv"><span>coeff source</span><span>' + esc(coeff.measured_source || '—') + '</span></div>' +
        '<div class="kv"><span>orbital joules</span><span>' + esc(ojoules) + ' <span class="badge modeled">MODELED</span></span></div>' +
        '<div class="kv"><span>orbital kWh</span><span>' + esc(okwh) + ' <span class="badge modeled">MODELED</span></span></div>' +
        '<div class="receipt">' +
          '<span class="lbl">would-be signed receipt (MODELED — not a real signature):</span><br/>' +
          'governed-energy-receipt:' + esc(rid) + '<br/>' +
          '<span class="lbl">basis:</span> MEASURED ground J/token &times; MODELED workload &times; MODELED space-overhead<br/>' +
          '<span class="lbl">honesty:</span> sovereign=false · &Lambda;=Conjecture 1 · no on-orbit hardware' +
        '</div>';
      el('subline').innerHTML =
        'Each MODELED orbital job carries a MODELED energy figure (derived from the REAL ' +
        'ground-measured J/token coefficient, cited above) and a <b>would-be signed ' +
        'governed-energy-receipt</b> — the SZL moat, applied to space compute. Forward design, not deployed.';
    });
  }

  // Kick off both fetches immediately — independent of any 3D rendering.
  fetchJSON(TOPOLOGY_EP).then(function (res) {
    if (!res.ok || res.json.ok === false) { throw new Error('topology ' + res.status); }
    window.OrbitalData.topology = res.json;
    renderTopology(res.json);
    topoCbs.splice(0).forEach(function (cb) { try { cb(res.json); } catch (e) {} });
  }).catch(function (e) { fail('topo-status', 'topology unavailable: ' + e + ' (nothing fabricated)'); });

  fetchJSON(PROJECTION_EP).then(function (res) {
    if (!res.ok || res.json.ok === false) { throw new Error('projection ' + res.status); }
    window.OrbitalData.projection = res.json;
    return renderProjection(res.json);
  }).catch(function (e) { fail('proj-status', 'projection unavailable: ' + e + ' (no fabricated joule)'); });
})();
</script>

<!-- 3D (module script): three.js r160, vendored, 0 CDN. Pure progressive
     enhancement — wrapped so a WebGL/import failure shows an honest fallback and
     never blocks the data above. -->
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const stage = document.getElementById('stage');
const canvas = document.getElementById('scene');
const fallback = document.getElementById('stage-fallback');

function showFallback() {
  if (canvas) { canvas.style.display = 'none'; }
  if (fallback) { fallback.style.display = 'flex'; }
}

const TIER_COLOR = { 'LEO-edge': 0x4d8fcc, 'MEO-aggregation': 0xd8a23c, 'GEO-backhaul': 0xc8643c };
const TIER_RADIUS = { 'LEO-edge': 9, 'MEO-aggregation': 15, 'GEO-backhaul': 22 };

let renderer = null;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
} catch (e) {
  showFallback();
}

if (renderer) {
  try {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 2000);
    camera.position.set(0, 18, 64);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = 0.06;
    controls.autoRotate = true; controls.autoRotateSpeed = 0.35;
    controls.enablePan = false;
    controls.minDistance = 20; controls.maxDistance = 150;

    scene.add(new THREE.AmbientLight(0x88aacc, 0.7));
    const keyLight = new THREE.PointLight(0xffffff, 1.2); keyLight.position.set(40, 50, 50); scene.add(keyLight);

    // Earth proxy (MODELED globe — purely a visual reference, not a data claim).
    const earth = new THREE.Mesh(
      new THREE.SphereGeometry(5.6, 48, 48),
      new THREE.MeshStandardMaterial({ color: 0x0d2238, emissive: 0x06121f, roughness: 0.9, metalness: 0.1 })
    );
    scene.add(earth);
    const grid = new THREE.Mesh(
      new THREE.SphereGeometry(5.7, 24, 24),
      new THREE.MeshBasicMaterial({ color: 0x1d3a5c, wireframe: true, transparent: true, opacity: 0.35 })
    );
    scene.add(grid);

    const nodeGroup = new THREE.Group(); scene.add(nodeGroup);
    const linkGroup = new THREE.Group(); scene.add(linkGroup);

    // Deterministic placement: spread a tier's nodes evenly around a ring, tilted per plane.
    function placeNodes(nodes) {
      const byTier = {};
      for (const n of nodes) { (byTier[n.tier] = byTier[n.tier] || []).push(n); }
      const pos = {};
      for (const entry of Object.entries(byTier)) {
        const tier = entry[0], arr = entry[1];
        const R = TIER_RADIUS[tier] || 12;
        arr.forEach(function (n, i) {
          const a = (i / arr.length) * Math.PI * 2;
          const tilt = ((n.orbital_plane || 0) * 0.5);
          pos[n.id] = new THREE.Vector3(
            Math.cos(a) * R,
            Math.sin(tilt) * R * 0.35 + Math.sin(a) * 1.5,
            Math.sin(a) * R
          );
        });
      }
      return pos;
    }

    function drawTopology(t) {
      nodeGroup.clear(); linkGroup.clear();
      const nodes = t.orbital_nodes || [];
      const pos = placeNodes(nodes);
      // ground stations sit just outside the globe surface
      const gsList = t.ground_stations || [];
      gsList.forEach(function (gs, i) {
        const a = (i / Math.max(gsList.length, 1)) * Math.PI * 2;
        pos[gs.id] = new THREE.Vector3(Math.cos(a) * 6.2, -1.5, Math.sin(a) * 6.2);
      });

      for (const n of nodes) {
        const color = TIER_COLOR[n.tier] || 0x9fb1bf;
        // reachable is REAL-PROBE-ONLY; topology always reports false — render hollow.
        const m = new THREE.Mesh(
          new THREE.SphereGeometry(0.55, 20, 20),
          new THREE.MeshStandardMaterial({
            color: color, emissive: color, emissiveIntensity: 0.35, roughness: 0.5,
            transparent: true, opacity: 0.92
          })
        );
        m.position.copy(pos[n.id]); nodeGroup.add(m);
      }
      // ground stations: small green markers (REAL ground side; the downlink is MODELED)
      for (const gs of gsList) {
        const m = new THREE.Mesh(
          new THREE.SphereGeometry(0.4, 16, 16),
          new THREE.MeshStandardMaterial({ color: 0x2fd07a, emissive: 0x2fd07a, emissiveIntensity: 0.4 })
        );
        m.position.copy(pos[gs.id]); nodeGroup.add(m);
      }

      for (const l of (t.links || [])) {
        const a = pos[l.src], b = pos[l.dst];
        if (!a || !b) { continue; }
        const isDown = l.kind === 'ground-space-downlink';
        const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
        linkGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({
          color: isDown ? 0x2fd07a : 0x6fb1ff, transparent: true, opacity: isDown ? 0.7 : 0.4
        })));
      }
    }

    function resize() {
      const w = stage.clientWidth || 1, h = stage.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resize); resize();

    (function loop() {
      requestAnimationFrame(loop);
      controls.update();
      earth.rotation.y += 0.0008; grid.rotation.y += 0.0008;
      renderer.render(scene, camera);
    })();

    // Draw the constellation as soon as the classic script's fetch resolves.
    if (typeof window.onOrbitalTopology === 'function') {
      window.onOrbitalTopology(drawTopology);
    } else if (window.OrbitalData && window.OrbitalData.topology) {
      drawTopology(window.OrbitalData.topology);
    }
  } catch (e) {
    showFallback();
  }
}
</script>
</body></html>"""


def _page_html(ns: str) -> str:
    topology_ep = _TOPOLOGY_EP.format(ns=ns)
    projection_ep = _PROJECTION_EP.format(ns=ns)
    return (
        _PAGE_TEMPLATE
        .replace("@@MODELED_BANNER@@", MODELED_BANNER)
        .replace("@@TOPOLOGY_EP@@", topology_ep)
        .replace("@@PROJECTION_EP@@", projection_ep)
        .replace("@@THREE_MAIN@@", _THREE_MAIN)
        .replace("@@THREE_ADDONS@@", _THREE_ADDONS)
    )


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
    # 6) RENDER RESILIENCE — the data panels are populated by a script that does NOT
    #    depend on WebGL/three.js, so a WebGL failure can never blank the page. The
    #    3D layer subscribes to that data and degrades to an honest fallback.
    assert "window.OrbitalData" in html, "data layer not decoupled from 3D"
    assert 'id="stage-fallback"' in html, "3D fallback surface missing"
    assert "AbortController" in html, "fetch timeout (no-hang) guard missing"
    # 7) MOBILE — responsive viewport + a small-screen media query.
    assert "width=device-width" in html, "responsive viewport meta missing"
    assert "@media (max-width:560px)" in html, "mobile media query missing"
    print("a11oy_orbital_page: ALL OK (MODELED banner, endpoints wired, 0 CDN, render marker, "
          "honest receipt, WebGL-independent data, mobile-responsive)")


if __name__ == "__main__":
    _selftest()
