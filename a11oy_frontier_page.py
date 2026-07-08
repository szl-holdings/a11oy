# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_frontier_page — ADDITIVE /frontier unified-ecosystem showcase surface.

Renders the WHOLE SZL governed-provenance stack as ONE honest showcase, driven by
the already-live backend roll-up (PR #472): GET /api/a11oy/v1/frontier/manifest.

Each capability tile from the manifest is drawn as a holographic card carrying:
  * its capability name + human status,
  * its HONEST label badge — MEASURED / MODELED / ROADMAP / SAMPLE / UNAVAILABLE
    (read verbatim from the manifest; this page NEVER upgrades a label), and
  * a provenance pointer — where the real evidence lives (ledger chain-head digest,
    the cosign/Rekor verify path for the signed UDS bundle, the MODELED orbital
    endpoints + /orbital page, the live compute-pool probe path, the restraint
    doctrine surface). So a reader can go check the real artifact.

The whole stack on one surface:
  - live energy receipts (MEASURED — operator joules + signed ledger chain.ok),
  - signed UDS bundle (Sigstore/cosign keyless + public Rekor transparency log),
  - the multi-node sovereign GPU fabric (REAL reachability probe),
  - the MODELED orbital tier (links out to the /orbital page),
  - governance / restraint (codified doctrine + signed DSSE receipts),
  - the ROADMAP composite inference-provenance-receipt play (clearly labeled).

HONESTY (doctrine v11, non-negotiable):
  * A persistent honest banner is pinned to the top of every viewport and a
    per-tile honest banner sits on every MODELED / ROADMAP / SAMPLE / UNAVAILABLE
    tile — they can never be mistaken for live MEASURED telemetry.
  * No label is fabricated or upgraded. The page renders exactly what the manifest
    reports; a down sub-source shows as an honest UNAVAILABLE tile.
  * 0 runtime CDN: three.js r160 (MIT) is loaded from the in-image vendored path
    /hero/vendor3d/ (the same proven, allowlisted, runtime-served route the
    cathedral hero + /orbital page use). No external host is ever fetched.
  * If the manifest is unreachable the page degrades honestly (shows the error,
    draws nothing fabricated) — honest BLOCKED beats fake green. NO white screen:
    the heading, banner, and 3D canvas render before the fetch resolves.

Pattern mirrors a11oy_orbital_page.register(app, ns): mounts
  GET /frontier                              (self-contained HTML, 0 CDN)
  GET /api/<ns>/v1/frontier/page-manifest    (JSON nav descriptor)
Registered BEFORE the SPA /{full_path:path} catch-all; try/except-guarded in
serve.py so a missing dep can never take down the Space. Λ = Conjecture 1;
sovereign=false on this path. Doctrine v11 LOCKED.
"""
from __future__ import annotations

import pathlib
import re

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "lambda": "Conjecture 1", "sovereign": False}

# --------------------------------------------------------------------------- #
# Frontier 3D-surface manifest (GET /api/<ns>/v1/frontier/surfaces)
#
# A machine-verifiable roll-up of every 3D holographic frontier surface. The
# SINGLE SOURCE OF TRUTH for the surface LIST is the `SURFACES` array declared in
# static/3d/holographic.html (the same array the holographic viewer loads); the
# SINGLE SOURCE OF TRUTH for each surface's honesty LABEL is the surface's own JS
# source — the label is PARSED from the file, never hardcoded a second time here.
#
# Doctrine v11 honesty (non-negotiable):
#   * A missing asset at runtime -> UNAVAILABLE with a reason, NEVER a fabricated
#     present/green tile.
#   * The label is read from the surface source and reported VERBATIM — never
#     upgraded. Where a surface declares no doctrine token at all, it is honestly
#     UNAVAILABLE (undeclared), not padded to a nicer label.
#   * This is a pure READ (parse files on disk). It signs nothing and appends to
#     no provenance chain — receipts belong on writes, never on GETs.
# --------------------------------------------------------------------------- #

# Repo root — this module lives flat at the repo root next to static/3d/.
_REPO_ROOT = pathlib.Path(__file__).resolve().parent
_HOLOGRAPHIC_REL = "static/3d/holographic.html"

# Recognized doctrine honesty vocabulary (weakest→strongest claim ordering is not
# needed here — this is just the accepted set). UNAVAILABLE is reserved for a
# missing asset or an undeclared label; it is never a "normal" surface label.
_VALID_LABELS = ("MEASURED", "LIVE", "SAMPLE", "MODELED", "STRUCTURAL-ONLY", "ROADMAP")
UNAVAILABLE = "UNAVAILABLE"

# `{ id: "grpo", cat: "x", [flag: true,] title: "GRPO Reward Dynamics", mod: ".../grpo.js" }`
# id -> title -> mod is the stable authored order; interstitial keys (cat, flag, ...) are
# tolerated so the manifest tracks the real single-source registry rather than reporting 0.
_SURFACE_ENTRY_RE = re.compile(
    r'\{\s*id:\s*"([^"]+)"[^{}]*?\btitle:\s*"([^"]+)"[^{}]*?\bmod:\s*"([^"]+)"[^{}]*\}')
# Runtime-default label the surface renders absent live data: `S.label = (j.label || "MODELED")`.
_LABEL_DEFAULT_RE = re.compile(r'\b\w+\.label\s*=\s*\(\s*[\w.]+\s*\|\|\s*"([A-Z][A-Z-]+)"')
# Declared honesty chip / billboard token (surfaces without a runtime-default label).
_LABEL_CHIP_RE = re.compile(r'\.chip\(\s*"([A-Z][A-Z-]+)"')
_LABEL_BILL_RE = re.compile(r'billboard\([^,]*,\s*"([A-Z][A-Z-]+)"')
# Any quoted UPPER token (last-resort scan, e.g. the hub surface's ROADMAP literal).
_TOKEN_RE = re.compile(r'"([A-Z][A-Z-]+)"')


def _derive_label(src: str) -> tuple[str | None, str]:
    """Derive a surface's honesty label from its JS source. Returns (label, source).

    Ordered, deterministic, and never over-claims: the headline label is the
    surface's own declared token, read verbatim. A surface can never be reported
    stronger than it declares (none of these first-match rules can yield MEASURED
    for a surface that only models/samples)."""
    m = _LABEL_DEFAULT_RE.search(src)
    if m and m.group(1) in _VALID_LABELS:
        return m.group(1), "js-runtime-default"
    for rx, source in ((_LABEL_CHIP_RE, "js-honesty-chip"),
                       (_LABEL_BILL_RE, "js-honesty-billboard"),
                       (_TOKEN_RE, "js-doctrine-literal")):
        for mm in rx.finditer(src):
            if mm.group(1) in _VALID_LABELS:
                return mm.group(1), source
    return None, "none"


def _declared_labels(src: str) -> list[str]:
    """Every recognized doctrine token the surface source declares (audit trail)."""
    return sorted({t for t in _TOKEN_RE.findall(src) if t in _VALID_LABELS})


def _build_surface_entry(sid: str, title: str, mod: str) -> dict:
    """Build one manifest entry for a surface. Missing asset -> honest UNAVAILABLE."""
    asset_rel = mod.lstrip("/")
    asset_path = _REPO_ROOT / asset_rel
    entry: dict = {"id": sid, "title": title, "asset": mod, "label_verbatim": True}
    if not asset_path.is_file():
        entry.update({
            "label": UNAVAILABLE,
            "label_source": "missing-asset",
            "declared_labels": [],
            "present": False,
            "reason": f"surface asset not found at {mod}",
        })
        return entry
    src = asset_path.read_text(encoding="utf-8", errors="replace")
    label, label_source = _derive_label(src)
    entry["present"] = True
    entry["declared_labels"] = _declared_labels(src)
    if label is None:
        entry.update({
            "label": UNAVAILABLE,
            "label_source": "no-declared-label",
            "reason": "surface source declares no recognized doctrine honesty token",
        })
    else:
        entry.update({"label": label, "label_source": label_source})
    return entry


def build_surfaces_manifest(ns: str = "a11oy") -> dict:
    """Compose the machine-verifiable 3D-surface manifest from the live registry.

    The surface list is parsed from static/3d/holographic.html's SURFACES array;
    each label is parsed from the surface's own JS. Never fabricates a surface,
    a count, or a label. If holographic.html itself is missing the manifest still
    returns 200 with an honest empty list + error."""
    endpoint = f"/api/{ns}/v1/frontier/surfaces"
    holo = _REPO_ROOT / _HOLOGRAPHIC_REL
    base = {
        "endpoint": endpoint,
        "source": _HOLOGRAPHIC_REL,
        "hub": "frontier",
        "doctrine": {
            "version": "v11",
            "lambda": "Conjecture 1",
            "note": ("surface list parsed from holographic.html SURFACES; each label "
                     "parsed from the surface JS source and reported verbatim, never "
                     "upgraded; missing asset -> UNAVAILABLE, never fabricated"),
        },
    }
    if not holo.is_file():
        base.update({"ok": False, "count": 0, "surfaces": [],
                     "error": f"registry not found at {_HOLOGRAPHIC_REL}",
                     "summary": {"count": 0, "label_counts": {}, "labels_valid": True}})
        return base

    html = holo.read_text(encoding="utf-8", errors="replace")
    entries = _SURFACE_ENTRY_RE.findall(html)
    surfaces = [_build_surface_entry(sid, title, mod) for sid, title, mod in entries]

    label_counts: dict[str, int] = {}
    for s in surfaces:
        label_counts[s["label"]] = label_counts.get(s["label"], 0) + 1
    valid_set = set(_VALID_LABELS) | {UNAVAILABLE}
    labels_valid = all(s["label"] in valid_set for s in surfaces)

    base.update({
        "ok": True,
        "count": len(surfaces),
        "surfaces": surfaces,
        "summary": {
            "count": len(surfaces),
            "present": sum(1 for s in surfaces if s.get("present")),
            "unavailable": sum(1 for s in surfaces if s["label"] == UNAVAILABLE),
            "label_counts": label_counts,
            "labels_valid": labels_valid,
        },
    })
    return base
HONEST_BANNER = (
    "HONEST SHOWCASE — every tile carries its own label (MEASURED / MODELED / "
    "ROADMAP / SAMPLE) and a provenance pointer; no label is upgraded, nothing is faked"
)

# The LIVE backend roll-up this surface renders (PR #472). Wired client-side.
_MANIFEST_EP = "/api/{ns}/v1/frontier/manifest"
# The 3D-surface manifest this page renders its surface list from (one source of truth).
_SURFACES_EP = "/api/{ns}/v1/frontier/surfaces"

# 0-CDN vendored three.js r160 — the proven, allowlisted, runtime-served hero path
# (serve.py GET /hero/vendor3d/{fname}; identical to the /orbital page importmap).
_THREE_MAIN = "/hero/vendor3d/three.module.min.js"
_THREE_ADDONS = "/hero/vendor3d/"


def _page_html(ns: str) -> str:
    manifest_ep = _MANIFEST_EP.format(ns=ns)
    surfaces_ep = _SURFACES_EP.format(ns=ns)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>A11oy — SZL Frontier (Unified Ecosystem Showcase)</title>
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
           --green:#2fd07a; --warn:#c8893c; --violet:#9d7ad8; --red:#d8624a; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; min-height:100%; }}
  body {{ font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
          background:radial-gradient(1200px 700px at 70% -10%, #14213b, var(--bg));
          color:var(--ink); }}
  /* Persistent, unmissable HONEST banner — top of every viewport. */
  #honest-banner {{ position:fixed; top:0; left:0; right:0; z-index:50;
    background:linear-gradient(90deg, rgba(77,143,204,.22), rgba(157,122,216,.18));
    border-bottom:1px solid rgba(232,192,116,.5);
    color:var(--amber); font-family:ui-monospace,monospace; font-size:.8rem;
    letter-spacing:.05em; padding:.55rem 1rem;
    display:flex; align-items:center; gap:.6rem; backdrop-filter:blur(4px); }}
  #honest-banner .dot {{ width:.6rem; height:.6rem; border-radius:50%;
    background:var(--amber); box-shadow:0 0 8px var(--amber); flex:0 0 auto; }}
  #honest-banner b {{ color:var(--gold); }}
  /* 3D ecosystem constellation backdrop. */
  #scene {{ position:fixed; inset:0; z-index:0; }}
  /* Scrollable content layer above the canvas. */
  #wrap {{ position:relative; z-index:1; max-width:1180px; margin:0 auto;
           padding:4.2rem 1.2rem 4rem; }}
  .plaque {{ font-family:ui-monospace,monospace; font-size:.7rem; letter-spacing:.12em;
             color:var(--muted); text-transform:uppercase; }}
  .plaque b {{ color:var(--gold); }}
  h1 {{ font-size:clamp(1.6rem,3.4vw,2.5rem); margin:.3rem 0 0; }}
  h1 .accent {{ color:var(--terra); }}
  .sub {{ color:var(--muted); max-width:70ch; line-height:1.55; font-size:.9rem; margin:.45rem 0 0; }}
  #rollup {{ display:flex; gap:.7rem; flex-wrap:wrap; margin:1.1rem 0 .3rem;
             font-family:ui-monospace,monospace; font-size:.72rem; }}
  .chip {{ background:rgba(16,26,46,.8); border:1px solid #21304d; border-radius:999px;
           padding:.3rem .7rem; color:var(--muted); }}
  .chip b {{ color:var(--ink); }}
  #legend {{ display:flex; flex-wrap:wrap; gap:.4rem .6rem; margin:.9rem 0 .2rem;
             font-family:ui-monospace,monospace; font-size:.66rem; }}
  .lg {{ padding:.22rem .55rem; border-radius:999px; letter-spacing:.03em;
         border:1px solid transparent; white-space:nowrap; }}
  .lg.measured {{ color:var(--green);  border-color:rgba(47,208,122,.45);  background:rgba(47,208,122,.1); }}
  .lg.modeled  {{ color:var(--amber);  border-color:rgba(232,192,116,.45); background:rgba(232,192,116,.1); }}
  .lg.roadmap  {{ color:var(--violet); border-color:rgba(157,122,216,.5);  background:rgba(157,122,216,.1); }}
  .lg.sample   {{ color:var(--indigo); border-color:rgba(77,143,204,.45);  background:rgba(77,143,204,.1); }}
  #grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
           gap:1rem; margin-top:1.2rem; }}
  .card {{ background:rgba(16,26,46,.84); border:1px solid #21304d; border-radius:14px;
           padding:1rem 1.1rem; box-shadow:0 18px 40px -28px #000;
           backdrop-filter:blur(6px); position:relative; overflow:hidden;
           display:flex; flex-direction:column; gap:.55rem; }}
  .card::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px;
                   background:var(--edge,var(--indigo)); opacity:.85; }}
  .card h3 {{ margin:.15rem 0 0; font-family:ui-monospace,monospace; font-size:.96rem;
              color:var(--ink); display:flex; align-items:center; gap:.5rem;
              justify-content:space-between; }}
  .card .cat {{ font-family:ui-monospace,monospace; font-size:.62rem; letter-spacing:.1em;
                text-transform:uppercase; color:var(--muted); }}
  .card .stat {{ font-size:.82rem; color:var(--ink); line-height:1.4; }}
  .badge {{ font-size:.6rem; padding:.16rem .5rem; border-radius:999px; letter-spacing:.06em;
            text-transform:uppercase; font-family:ui-monospace,monospace; flex:0 0 auto;
            white-space:nowrap; }}
  .badge.measured  {{ background:rgba(47,208,122,.16); color:var(--green);  border:1px solid rgba(47,208,122,.45); }}
  .badge.modeled   {{ background:rgba(232,192,116,.16); color:var(--amber); border:1px solid rgba(232,192,116,.45); }}
  .badge.roadmap   {{ background:rgba(157,122,216,.16); color:var(--violet); border:1px solid rgba(157,122,216,.5); }}
  .badge.sample    {{ background:rgba(77,143,204,.16); color:var(--indigo); border:1px solid rgba(77,143,204,.45); }}
  .badge.unavailable {{ background:rgba(216,98,74,.16); color:var(--red); border:1px solid rgba(216,98,74,.5); }}
  .badge.structural-only {{ background:rgba(138,151,163,.16); color:#9fb1bf; border:1px solid rgba(138,151,163,.5); }}
  .badge.live {{ background:rgba(47,208,122,.16); color:var(--green); border:1px solid rgba(47,208,122,.45); }}
  /* 3D-surface list — compact honest pills, one per surface. */
  #surfaces-section {{ margin-top:1.6rem; }}
  #surfaces-section h2 {{ font-size:clamp(1.1rem,2vw,1.4rem); margin:.2rem 0 0; }}
  #surfaces-list {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1rem; }}
  .surface-pill {{ display:flex; align-items:center; gap:.5rem; background:rgba(16,26,46,.84);
    border:1px solid #21304d; border-radius:10px; padding:.4rem .6rem;
    font-family:ui-monospace,monospace; font-size:.72rem; color:var(--ink); }}
  .surface-pill .sid {{ color:var(--muted); }}
  /* Per-tile persistent honest banner on non-MEASURED tiles. */
  .tile-banner {{ font-family:ui-monospace,monospace; font-size:.66rem; line-height:1.4;
                  border-radius:8px; padding:.4rem .55rem; letter-spacing:.03em; }}
  .tile-banner.modeled {{ background:rgba(232,192,116,.1); color:var(--amber); border:1px solid rgba(232,192,116,.35); }}
  .tile-banner.roadmap {{ background:rgba(157,122,216,.1); color:var(--violet); border:1px solid rgba(157,122,216,.4); }}
  .tile-banner.sample {{ background:rgba(77,143,204,.1); color:var(--indigo); border:1px solid rgba(77,143,204,.35); }}
  .tile-banner.unavailable {{ background:rgba(216,98,74,.1); color:var(--red); border:1px solid rgba(216,98,74,.4); }}
  .prov {{ font-family:ui-monospace,monospace; font-size:.68rem; color:#9fb1bf;
           background:#070c17; border:1px solid #1a2742; border-radius:8px;
           padding:.5rem .6rem; word-break:break-all; line-height:1.5; }}
  .prov .lbl {{ color:var(--indigo); }}
  .prov a {{ color:var(--green); text-decoration:none; }}
  .prov a:hover {{ text-decoration:underline; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:.3rem .9rem; font-family:ui-monospace,monospace;
           font-size:.7rem; color:var(--muted); }}
  .meta b {{ color:var(--ink); }}
  .status-line {{ font-family:ui-monospace,monospace; font-size:.74rem; color:var(--muted); margin-top:1.4rem; }}
  .status-line.err {{ color:var(--warn); }}
  a.back {{ color:var(--muted); text-decoration:none; font-size:.8rem; }}
  a.orbital-link {{ color:var(--amber); text-decoration:none; }}
  a.orbital-link:hover {{ text-decoration:underline; }}
  noscript {{ color:var(--amber); display:block; padding:4rem 1.5rem; }}
</style></head>
<body>
  <div id="honest-banner">
    <span class="dot"></span>
    <span><b>SZL FRONTIER — UNIFIED ECOSYSTEM SHOWCASE.</b> &nbsp;{HONEST_BANNER}.
    Λ = Conjecture 1 · sovereign=false on this surface.</span>
  </div>

  <canvas id="scene"></canvas>

  <div id="wrap">
    <div class="plaque">SZL HOLDINGS / A11OY / DOCTRINE <b>V11 · LOCKED</b> / Λ = CONJECTURE 1</div>
    <h1>The whole stack, <span class="accent">honestly</span> labeled.</h1>
    <p class="sub" id="subline">Every capability we run, on one screen — live from
       <code>/frontier/manifest</code>. Each tile is tagged with how real it is and links
       straight to the proof.</p>
    <div id="legend">
      <span class="lg measured">MEASURED — live, measured now</span>
      <span class="lg modeled">MODELED — derived from real data</span>
      <span class="lg roadmap">ROADMAP — named next work</span>
      <span class="lg sample">SAMPLE — illustrative only</span>
    </div>
    <div id="rollup"></div>

    <!-- 3D holographic surfaces — count + honest labels, from the SAME manifest the
         holographic showcase is built from (one source of truth: /frontier/surfaces). -->
    <div id="surfaces-section">
      <h2 id="surfaces-h">3D holographic surfaces</h2>
      <p class="sub" id="surfaces-sub">The holographic frontier surfaces, listed live from
        <code>/frontier/surfaces</code> — the same machine-verifiable manifest that names each
        surface's asset and its honest label (parsed from the surface source, never upgraded).</p>
      <div id="surfaces-rollup"></div>
      <div id="surfaces-list"></div>
      <div class="status-line" id="surfaces-status">fetching /frontier/surfaces…</div>
    </div>

    <div id="grid"></div>
    <div class="status-line" id="status">fetching /frontier/manifest…</div>
    <div class="status-line"><a class="back" href="/">← back to console</a> &nbsp;·&nbsp;
      <a class="orbital-link" href="/orbital">orbital tier (MODELED) →</a></div>
  </div>

  <noscript>This unified frontier showcase renders the live capability roll-up with
    JavaScript. Nothing is fabricated; the raw honest data is at
    <code>{manifest_ep}</code>.</noscript>

<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/OrbitControls.js';

const MANIFEST_EP = {manifest_ep!r};

const LABEL_CLASS = {{
  MEASURED:'measured', MODELED:'modeled', ROADMAP:'roadmap',
  SAMPLE:'sample', UNAVAILABLE:'unavailable',
}};
const LABEL_COLOR = {{
  MEASURED:0x2fd07a, MODELED:0xe8c074, ROADMAP:0x9d7ad8,
  SAMPLE:0x4d8fcc, UNAVAILABLE:0xd8624a,
}};
const EDGE_HEX = {{
  MEASURED:'#2fd07a', MODELED:'#e8c074', ROADMAP:'#9d7ad8',
  SAMPLE:'#4d8fcc', UNAVAILABLE:'#d8624a',
}};

function esc(s) {{ return String(s).replace(/[&<>"']/g, c =>
  ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
function cls(label) {{ return LABEL_CLASS[label] || 'sample'; }}

// ---- three.js holographic ecosystem constellation (r160, vendored, 0 CDN) ----
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({{ canvas, antialias:true, alpha:true }});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 2000);
camera.position.set(0, 6, 60);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.06;
controls.enablePan = false; controls.enableZoom = false;
controls.autoRotate = true; controls.autoRotateSpeed = 0.28;

scene.add(new THREE.AmbientLight(0x88aacc, 0.7));
const key = new THREE.PointLight(0xffffff, 1.1); key.position.set(40, 50, 50); scene.add(key);

// A central governed-provenance core; capability tiles orbit it as labeled nodes.
const core = new THREE.Mesh(
  new THREE.IcosahedronGeometry(4.2, 1),
  new THREE.MeshStandardMaterial({{ color:0x16304f, emissive:0x0a1a30,
    roughness:0.5, metalness:0.2, wireframe:true, transparent:true, opacity:0.55 }})
);
scene.add(core);

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
  core.rotation.y += 0.0012; core.rotation.x += 0.0005;
  renderer.render(scene, camera);
}})();

// Place capability tiles evenly on a ring around the core, colored by honest label.
function drawConstellation(tiles) {{
  nodeGroup.clear(); linkGroup.clear();
  const n = tiles.length || 1;
  tiles.forEach((t, i) => {{
    const a = (i / n) * Math.PI * 2;
    const R = 16, y = Math.sin(a * 2) * 3;
    const p = new THREE.Vector3(Math.cos(a) * R, y, Math.sin(a) * R);
    const color = LABEL_COLOR[t.label] || 0x9fb1bf;
    const mat = new THREE.MeshStandardMaterial({{
      color, emissive:color, emissiveIntensity:0.4, roughness:0.45,
      transparent:true, opacity:0.95 }});
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.9, 22, 22), mat);
    m.position.copy(p); nodeGroup.add(m);
    // spoke from the core to each capability node
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), p]);
    linkGroup.add(new THREE.Line(geo,
      new THREE.LineBasicMaterial({{ color, transparent:true, opacity:0.35 }})));
  }});
}}

// ---- provenance pointer renderer (links the real artifact paths) -------------
function provHtml(prov) {{
  if (!prov || typeof prov !== 'object') return '';
  const rows = [];
  for (const [k, v] of Object.entries(prov)) {{
    if (v == null || v === '') continue;
    let val = esc(v);
    // make in-app endpoint pointers clickable so a reader can go check the artifact
    if (typeof v === 'string' && v.startsWith('/api/') && !v.includes('{{')) {{
      val = `<a href="${{esc(v)}}">${{esc(v)}}</a>`;
    }} else if (v === '/orbital') {{
      val = `<a href="/orbital">${{esc(v)}}</a>`;
    }}
    rows.push(`<div><span class="lbl">${{esc(k)}}:</span> ${{val}}</div>`);
  }}
  return rows.join('');
}}

// selected honest extra facts worth surfacing per tile (never fabricated; shown only if present)
const EXTRA_KEYS = [
  'joules_measured_total','measured_jobs','chain_length','links_intact',
  'survives_redeploy','length','nodes_total','nodes_reachable','gpu_reachable',
  'modeled_nodes','reachable_nodes','on_orbit_hardware','on_artifact_minted',
  'doctrine_version','signed_receipts',
];
function metaHtml(t) {{
  const rows = [];
  for (const k of EXTRA_KEYS) {{
    if (t[k] === undefined || t[k] === null) continue;
    rows.push(`<span>${{esc(k)}} <b>${{esc(t[k])}}</b></span>`);
  }}
  return rows.length ? `<div class="meta">${{rows.join('')}}</div>` : '';
}}

function tileCard(t) {{
  const label = t.label || 'SAMPLE';
  const c = cls(label);
  const edge = EDGE_HEX[label] || '#4d8fcc';
  // Persistent per-tile honest banner on every non-MEASURED tile.
  let banner = '';
  if (label === 'MODELED')
    banner = `<div class="tile-banner modeled">MODELED — design artifact derived from a real measurement; not live telemetry.</div>`;
  else if (label === 'ROADMAP')
    banner = `<div class="tile-banner roadmap">ROADMAP — named forward work; no artifact is minted or fabricated.</div>`;
  else if (label === 'SAMPLE')
    banner = `<div class="tile-banner sample">SAMPLE — illustrative value, never billable or live.</div>`;
  else if (label === 'UNAVAILABLE')
    banner = `<div class="tile-banner unavailable">UNAVAILABLE — sub-source down right now; reported honestly, not faked.</div>`;
  return `<div class="card" style="--edge:${{edge}}">
    <div class="cat">${{esc(t.category || '')}}</div>
    <h3><span>${{esc(t.name || '')}}</span><span class="badge ${{c}}">${{esc(label)}}</span></h3>
    <div class="stat">${{esc(t.status || '')}}</div>
    ${{banner}}
    ${{metaHtml(t)}}
    <div class="prov">${{provHtml(t.provenance)}}</div>
  </div>`;
}}

function fail(msg) {{
  const el = document.getElementById('status');
  if (el) {{ el.className = 'status-line err'; el.textContent = msg; }}
}}

(async function load() {{
  try {{
    const r = await fetch(MANIFEST_EP, {{ headers:{{Accept:'application/json'}} }});
    const m = await r.json();
    if (!r.ok || m.ok === false) throw new Error('manifest ' + r.status);
    const tiles = m.capabilities || [];
    const s = m.summary || {{}};
    const lc = s.label_counts || {{}};

    // roll-up chips (honest counts straight from the manifest)
    document.getElementById('rollup').innerHTML = [
      `<span class="chip"><b>${{esc(s.tiles ?? tiles.length)}}</b> capabilities</span>`,
      `<span class="chip">MEASURED <b>${{esc(lc.MEASURED || 0)}}</b></span>`,
      `<span class="chip">MODELED <b>${{esc(lc.MODELED || 0)}}</b></span>`,
      `<span class="chip">ROADMAP <b>${{esc(lc.ROADMAP || 0)}}</b></span>`,
      `<span class="chip">all sources live: <b>${{esc(String(s.all_sources_live))}}</b></span>`,
      (s.degraded_tiles && s.degraded_tiles.length)
        ? `<span class="chip">degraded: <b>${{esc(s.degraded_tiles.join(', '))}}</b></span>` : '',
    ].join('');

    document.getElementById('grid').innerHTML = tiles.map(tileCard).join('');
    drawConstellation(tiles);

    const el = document.getElementById('status');
    el.textContent = 'live · composed from ' + esc(MANIFEST_EP) +
      ' · ' + esc(s.tiles ?? tiles.length) + ' tiles · all_sources_live=' +
      esc(String(s.all_sources_live));
    document.getElementById('subline').innerHTML =
      'Every capability we run, on one screen — composed live by <code>/frontier/manifest</code>. ' +
      'Each tile shows its <b>honest label</b> and a <b>link to the proof</b>. No label is upgraded.';
  }} catch (e) {{
    fail('manifest unavailable: ' + e + ' (nothing fabricated — raw data at ' + MANIFEST_EP + ')');
  }}
}})();

// ---- 3D-surface list: rendered FROM /frontier/surfaces (one source of truth) ---
const SURFACES_EP = {surfaces_ep!r};
const SURF_CLASS = {{
  MEASURED:'measured', LIVE:'live', SAMPLE:'sample', MODELED:'modeled',
  'STRUCTURAL-ONLY':'structural-only', ROADMAP:'roadmap', UNAVAILABLE:'unavailable',
}};
function surfCls(label) {{ return SURF_CLASS[label] || 'unavailable'; }}

(async function loadSurfaces() {{
  const statusEl = document.getElementById('surfaces-status');
  try {{
    const r = await fetch(SURFACES_EP, {{ headers:{{Accept:'application/json'}} }});
    const m = await r.json();
    const surfaces = m.surfaces || [];
    const s = m.summary || {{}};
    const lc = s.label_counts || {{}};

    // honest roll-up: true count + per-label counts, straight from the manifest
    const chips = [`<span class="chip"><b>${{esc(m.count ?? surfaces.length)}}</b> surfaces</span>`];
    for (const [label, n] of Object.entries(lc)) {{
      chips.push(`<span class="chip">${{esc(label)}} <b>${{esc(n)}}</b></span>`);
    }}
    if (s.unavailable) chips.push(`<span class="chip">unavailable <b>${{esc(s.unavailable)}}</b></span>`);
    chips.push(`<span class="chip">labels valid: <b>${{esc(String(s.labels_valid))}}</b></span>`);
    document.getElementById('surfaces-rollup').innerHTML = chips.join('');

    // one honest pill per surface: id · title · label badge
    document.getElementById('surfaces-list').innerHTML = surfaces.map(su => {{
      const label = su.label || 'UNAVAILABLE';
      return `<span class="surface-pill" title="${{esc(su.asset || '')}}">`
        + `<span class="sid">${{esc(su.id)}}</span>`
        + `<span>${{esc(su.title || '')}}</span>`
        + `<span class="badge ${{surfCls(label)}}">${{esc(label)}}</span></span>`;
    }}).join('');

    statusEl.className = 'status-line';
    statusEl.textContent = (m.ok === false)
      ? ('surface registry unavailable: ' + esc(m.error || 'unknown') + ' (nothing fabricated)')
      : ('live · ' + esc(m.count ?? surfaces.length) + ' surfaces from ' + esc(SURFACES_EP)
         + ' · labels_valid=' + esc(String(s.labels_valid)));
  }} catch (e) {{
    statusEl.className = 'status-line err';
    statusEl.textContent = 'surfaces unavailable: ' + e + ' (nothing fabricated — raw data at ' + SURFACES_EP + ')';
  }}
}})();
</script>
</body></html>"""


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount GET /frontier (HTML) + GET /api/<ns>/v1/frontier/page-manifest (JSON).
    ADDITIVE — registered before the SPA catch-all; touches no existing route."""

    @app.get("/frontier", include_in_schema=False)
    async def frontier_page() -> HTMLResponse:  # noqa: ANN202
        return HTMLResponse(_page_html(ns))

    @app.get(f"/api/{ns}/v1/frontier/surfaces")
    async def frontier_surfaces() -> JSONResponse:  # noqa: ANN202
        """Machine-verifiable manifest of every 3D frontier surface.

        id + title + honesty label (parsed from the surface source, verbatim) +
        asset path. Missing asset -> UNAVAILABLE with reason. Pure read; no sign."""
        return JSONResponse(build_surfaces_manifest(ns))

    @app.get(f"/api/{ns}/v1/frontier/page-manifest", include_in_schema=False)
    async def frontier_page_manifest() -> JSONResponse:  # noqa: ANN202
        return JSONResponse({
            "section": "Frontier",
            "page": "/frontier",
            "kind": "unified-ecosystem-showcase",
            "banner": HONEST_BANNER,
            "doctrine": DOCTRINE,
            "renders_endpoints": [_MANIFEST_EP.format(ns=ns), _SURFACES_EP.format(ns=ns)],
            "links": {"orbital_page": "/orbital", "manifest": _MANIFEST_EP.format(ns=ns),
                      "surfaces": _SURFACES_EP.format(ns=ns)},
            "vendored_3d": {"three": _THREE_MAIN, "addons": _THREE_ADDONS,
                            "revision": "r160", "runtime_cdn": 0},
            "note": ("Unified frontier showcase — renders the live /frontier/manifest "
                     "roll-up. Every tile carries its honest label (MEASURED/MODELED/"
                     "ROADMAP/SAMPLE) verbatim from the manifest and a provenance pointer; "
                     "no label is upgraded, nothing is fabricated."),
        })

    return ("frontier-page mounted: GET /frontier + page-manifest + "
            f"/api/{ns}/v1/frontier/surfaces (3D-surface manifest, parsed from "
            "holographic.html; renders /frontier/manifest roll-up + surface list, 0 CDN)")


def _selftest() -> None:
    html = _page_html("a11oy")
    # 1) the persistent HONEST banner is present
    assert "SZL FRONTIER — UNIFIED ECOSYSTEM SHOWCASE" in html, "honest banner missing"
    assert "no label is upgraded" in html, "honesty note missing"
    # 2) the live manifest endpoint is wired client-side
    assert "/api/a11oy/v1/frontier/manifest" in html, "manifest endpoint not wired"
    # 3) 0 runtime CDN — three.js loads from the vendored hero path, no external host
    assert _THREE_MAIN in html and "http://" not in html and "https://" not in html, \
        "external URL / CDN reference found (0-CDN doctrine)"
    # 4) a renderable marker exists (canvas + heading) so a live grep proves real content
    assert 'id="scene"' in html and "frontier" in html.lower(), "render marker missing"
    # 5) honest per-tile banners for every non-MEASURED label class exist in the renderer
    for lbl in ("MODELED", "ROADMAP", "SAMPLE", "UNAVAILABLE"):
        assert lbl in html, f"label class {lbl} banner missing"
    # 6) links to the orbital MODELED tier are present
    assert 'href="/orbital"' in html, "orbital tier link missing"
    assert "Conjecture 1" in html, "Λ label missing"
    # 7) the 3D-surface manifest is wired into the page (one source of truth)
    assert "/api/a11oy/v1/frontier/surfaces" in html, "surfaces endpoint not wired"
    assert 'id="surfaces-list"' in html and 'id="surfaces-rollup"' in html, \
        "surfaces section markers missing"
    assert "loadSurfaces" in html, "surfaces client loader missing"

    # 8) the manifest builder parses the live registry honestly
    man = build_surfaces_manifest("a11oy")
    assert man["ok"] is True, f"surfaces manifest not ok: {man.get('error')}"
    assert man["count"] == len(man["surfaces"]) and man["count"] > 0, "surface count mismatch"
    valid = set(_VALID_LABELS) | {UNAVAILABLE}
    assert all(su["label"] in valid for su in man["surfaces"]), "invalid honesty label found"
    assert man["summary"]["labels_valid"] is True, "labels_valid should be True"
    # missing asset -> honest UNAVAILABLE, never fabricated present/green
    miss = _build_surface_entry("nope", "Nope", "/static/3d/surfaces/__does_not_exist__.js")
    assert miss["label"] == UNAVAILABLE and miss["present"] is False and "reason" in miss, \
        "missing asset must be UNAVAILABLE with a reason"
    print("a11oy_frontier_page: ALL OK (honest banner, manifest wired, 0 CDN, render marker, "
          "per-tile honest banners, orbital link, "
          f"{man['count']} surfaces parsed, labels {man['summary']['label_counts']})")


if __name__ == "__main__":
    _selftest()
