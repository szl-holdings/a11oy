// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/frontierindex.js — FRONTIER INDEX · honest ecosystem catalog + self-audit.
//
// The map OF the maps. It renders the whole ecosystem as a constellation of surface
// nodes and, for EACH one, shows the honest data label that surface's OWN backend
// actually emits right now, whether it is a11oy-native or a cross-origin fallback, and
// whether it declares cited papers. HONEST BY CONSTRUCTION: every value is read VERBATIM
// from the same-origin catalog, which is itself derived live from the app's surface
// registry + registered routes + each surface's own response — never a hand-maintained
// list that can drift.
//
// DATA: live snapshot from the same-origin endpoint /api/a11oy/v1/frontier-index/catalog:
//   ok, label (MODELED, VERBATIM), summary{ surfaces, backend_counts, label_counts,
//   surfaces_with_citations }, surfaces[]{ id, title, category, backend, label,
//   citations[], endpoint }, doctrine{ locked_proven, lambda, trust_ceiling }.
//
// VISUALIZES:
//   1. an ECOSYSTEM RING — one small node per registered surface, arranged in a ring,
//      colored by its HONEST backend kind: a11oy-native (teal), cross-origin-fallback
//      (amber), frontend-only (grey). A node with cited papers gets a thin bright halo.
//   2. a CENTRAL INDEX HUB — the self node; links fan out to every surface it enumerated.
//   3. a per-node ACTIVITY PULSE that sweeps the ring, lighting each node in turn so the
//      viewer can read that the catalog covers the WHOLE estate, not a curated subset.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (an introspective view,
//   not a measurement). Each per-surface label shown is that surface's OWN label read
//   VERBATIM and NEVER upgraded: a down/proxy surface shows UNAVAILABLE, never a fake OK.
//   No green "1.0 / VERIFIED" state anywhere. Trust ceiling 0.97, NEVER 100%.
// COLOURS: teal 0x3af4c8 (a11oy-native), amber 0xf4b23a (cross-origin-fallback), grey
//   0x42505d (frontend-only / pending), lattice-blue 0x5b8dee (hub / links). PURPLE BANNED.
//   No green/1.0 verified state.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "frontierindex";
const TITLE = "Frontier Index · honest ecosystem catalog (live, self-audited)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/frontier-index/catalog";

// data-viz hues — purple BANNED, no green
const C_NATIVE   = 0x3af4c8;  // teal   — a11oy-native (backend answered with an honest label)
const C_FALLBACK = 0xf4b23a;  // amber  — cross-origin-fallback (route exists, no native label)
const C_FRONTEND = 0x42505d;  // grey   — frontend-only (no local /api route) / pending
const C_HUB      = 0x5b8dee;  // lattice-blue — central index hub + links
const C_GRID     = 0x1b3a44;  // floor / link colour

const RING_R = 6.2;           // ecosystem ring radius (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _hub = null;              // THREE.Mesh — central index node
let _nodes = [];              // Array<{ mesh, halo, backend, cited }>
let _links = [];              // Array<THREE.Line>
let _sweep = 0;               // ring-sweep phase

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,   // top honesty label VERBATIM (MODELED)
  count:     null,    // total surfaces enumerated
  native:    null,
  fallback:  null,
  frontend:  null,
  cited:     null,
  trustCeil: null,
  lambda:    null,
  locked:    null,
  surfaces:  [],      // [{ id, backend, label, cited }]
  state:     "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHub();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildHub() {
  const THREE = _THREE;
  _hub = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.9, 1),
    new THREE.MeshStandardMaterial({
      color: C_HUB, emissive: C_HUB, emissiveIntensity: 0.4,
      transparent: true, opacity: 0.9, wireframe: true,
    }),
  );
  _hub.position.set(0, 1.2, 0);
  _group.add(_hub);
}

// Build (or rebuild) one ring node per enumerated surface. Called on each live snapshot so
// the constellation always mirrors the CURRENT catalog (never a stale hard-coded set).
function _buildNodes() {
  const THREE = _THREE;
  _disposeNodes();
  const list = S.surfaces;
  const n = list.length;
  if (!n) return;

  const nodeGeo = new THREE.SphereGeometry(0.26, 14, 10);
  const haloGeo = new THREE.RingGeometry(0.34, 0.42, 20);

  for (let i = 0; i < n; i++) {
    const surf = list[i];
    const ang = (i / n) * Math.PI * 2;
    const x = Math.cos(ang) * RING_R;
    const z = Math.sin(ang) * RING_R;
    const color = _backendColor(surf.backend);

    const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.92,
    }));
    mesh.position.set(x, 1.2, z);
    _group.add(mesh);

    // cited-papers halo — a thin bright ring only when the surface declares citations.
    let halo = null;
    if (surf.cited) {
      halo = new THREE.Mesh(haloGeo, new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.5, side: THREE.DoubleSide,
      }));
      halo.position.copy(mesh.position);
      halo.lookAt(0, 1.2, 0);
      _group.add(halo);
    }

    // link hub -> node
    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 1.2, 0), new THREE.Vector3(x, 1.2, z),
    ]);
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({
      color: C_HUB, transparent: true, opacity: 0.12,
    }));
    _group.add(line);
    _links.push(line);

    _nodes.push({ mesh, halo, backend: surf.backend, cited: !!surf.cited });
  }
}

function _backendColor(backend) {
  if (backend === "a11oy-native") return C_NATIVE;
  if (backend === "cross-origin-fallback") return C_FALLBACK;
  return C_FRONTEND;
}

function _disposeNodes() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _nodes.forEach((nd) => { rm(nd.mesh); rm(nd.halo); });
  _links.forEach(rm);
  _nodes = []; _links = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  const sm = (j && j.summary) || {};
  const bc = sm.backend_counts || {};
  S.count    = typeof sm.surfaces === "number" ? sm.surfaces : null;
  S.native   = typeof bc["a11oy-native"] === "number" ? bc["a11oy-native"] : 0;
  S.fallback = typeof bc["cross-origin-fallback"] === "number" ? bc["cross-origin-fallback"] : 0;
  S.frontend = typeof bc["frontend-only"] === "number" ? bc["frontend-only"] : 0;
  S.cited    = typeof sm.surfaces_with_citations === "number" ? sm.surfaces_with_citations : 0;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  const arr = Array.isArray(j && j.surfaces) ? j.surfaces : [];
  S.surfaces = arr.map((e) => ({
    id: e && e.id,
    backend: e && e.backend,
    label: e && e.label,
    cited: !!(e && Array.isArray(e.citations) && e.citations.length),
  }));

  _buildNodes();
  _paintOverlay();
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.12;
  if (_hub) { _hub.rotation.y += 0.01; _hub.rotation.x += 0.004; }

  // ring-sweep: light each node in turn so the whole estate reads as covered.
  const live = S.state === "live";
  if (_nodes.length) {
    _sweep = (t * 0.0002) % 1;
    const lead = Math.floor(_sweep * _nodes.length);
    for (let i = 0; i < _nodes.length; i++) {
      const nd = _nodes[i];
      const near = Math.abs(i - lead) <= 1 || Math.abs(i - lead) >= _nodes.length - 1;
      const base = live ? 0.3 : 0.12;
      nd.mesh.material.emissiveIntensity = near && live ? 0.85 : base;
      nd.mesh.material.opacity = live ? 0.92 : 0.4;
      if (nd.halo) { nd.halo.rotation.z += 0.01; nd.halo.material.opacity = live ? 0.5 : 0.2; }
    }
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "ecosystem index", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The <b>map of the maps</b>: every registered frontier surface, with the honest data ' +
    'label its <b>own backend</b> actually emits right now, whether it is <b>a11oy-native</b> ' +
    'or a <b>cross-origin fallback</b>, and whether it cites papers. <b>Honest by ' +
    'construction</b> — derived live from the app’s surface registry + registered routes + ' +
    'each surface’s own response, never a hand-maintained list that can drift. This tab’s ' +
    'own label is <b>MODELED</b>; per-surface labels are read <b>VERBATIM</b> and never ' +
    'upgraded. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("fi-count",  "surfaces enumerated"));
  grid.appendChild(kpiRow("fi-native", "a11oy-native (own honest label)"));
  grid.appendChild(kpiRow("fi-fall",   "cross-origin-fallback"));
  grid.appendChild(kpiRow("fi-front",  "frontend-only"));
  grid.appendChild(kpiRow("fi-cited",  "surfaces citing papers"));
  grid.appendChild(kpiRow("fi-locked", "locked proofs"));
  grid.appendChild(kpiRow("fi-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("fi-lambda", "Λ"));
  card.appendChild(grid);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> a11oy-native &nbsp; ' +
    '<span style="color:#f4b23a">■</span> cross-origin-fallback &nbsp; ' +
    '<span style="color:#8494a1">■</span> frontend-only &nbsp; · halo = cites papers. ' +
    'MODELED · labels read verbatim, never upgraded.';
  card.appendChild(leg);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "fi-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  pd.innerHTML =
    "<b>What this means:</b> this is a single honest index of everything the platform " +
    "shows. For each surface it asks that surface’s <b>own</b> backend, live, what data " +
    "label it stands behind (for example <b>MODELED</b>, <b>SAMPLE</b>, or <b>UNAVAILABLE</b>) " +
    "and repeats it <b>word-for-word</b> — it never rounds a claim up. It also says whether " +
    "the surface is served by a11oy directly or is a fallback to another service, and whether " +
    "it cites real papers. The point is <b>anti-drift</b>: because the list is generated from " +
    "the running app itself, it cannot quietly disagree with what is actually wired. A CI " +
    "guard re-checks every label independently and fails the build if this catalog ever " +
    "claimed a label a backend does not emit. No “verified/1.0” state; trust ceiling 0.97.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _n(v) { return v == null ? "—" : String(v); }

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "ecosystem index" });
  _set("fi-count",  t || _n(S.count));
  _set("fi-native", t || _n(S.native));
  _set("fi-fall",   t || _n(S.fallback));
  _set("fi-front",  t || _n(S.frontend));
  _set("fi-cited",  t || _n(S.cited));
  _set("fi-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("fi-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("fi-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — dispose everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeNodes();
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _hub = null; _nodes = []; _links = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _sweep = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.count = S.native = S.fallback = S.frontend = S.cited = null;
  S.trustCeil = S.lambda = S.locked = null; S.surfaces = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
