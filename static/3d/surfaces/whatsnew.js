// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/whatsnew.js — WHAT'S NEW · honest auto-derived estate changelog.
//
// A vertical TIMELINE of the estate's recently-added frontier surfaces. Each rung is one
// surface, most-recent at the top, carrying the honest data label its OWN backend emits and
// whether it cites papers. HONEST BY CONSTRUCTION: every value is read VERBATIM from the
// same-origin feed, which is itself derived live from the Frontier Index catalog (surface
// registry + registered routes + each surface's own response) plus the REAL git add-history —
// never a hand-maintained changelog that can drift.
//
// DATA: live snapshot from /api/a11oy/v1/whatsnew/feed:
//   ok, label (MODELED, VERBATIM), history{ source, label }, count,
//   summary{ shown, registered_surfaces, label_counts, items_with_citations },
//   items[]{ id, title, label, backend, citations[], added, added_source },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// VISUALIZES:
//   1. a TIMELINE SPINE — a vertical line; one node per recently-added surface, newest at top.
//   2. each node colored by its HONEST backend kind: a11oy-native (teal), cross-origin-
//      fallback (amber), frontend-only (grey). A node that cites papers gets a thin halo.
//   3. a descending PULSE that travels the spine so the feed reads as a living timeline.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived digest, not a
//   measurement). Each per-surface label is that surface's OWN label read VERBATIM and NEVER
//   upgraded; an unavailable surface shows UNAVAILABLE, never a fake OK. Commit dates are the
//   REAL git add-dates or honestly omitted — never fabricated. No green "1.0 / VERIFIED"
//   state. Trust ceiling 0.97, NEVER 100%.
// COLOURS: teal 0x3af4c8 (a11oy-native), amber 0xf4b23a (cross-origin-fallback), grey
//   0x42505d (frontend-only), lattice-blue 0x5b8dee (spine). PURPLE BANNED. No green.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "whatsnew";
const TITLE = "What's New · honest auto-derived estate changelog (live, drift-proof)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/whatsnew/feed";

// data-viz hues — purple BANNED, no green
const C_NATIVE   = 0x3af4c8;  // teal   — a11oy-native
const C_FALLBACK = 0xf4b23a;  // amber  — cross-origin-fallback
const C_FRONTEND = 0x42505d;  // grey   — frontend-only / pending
const C_SPINE    = 0x5b8dee;  // lattice-blue — timeline spine
const C_GRID     = 0x1b3a44;  // floor colour

const SPAN_Y = 9.0;           // vertical extent of the timeline spine (world units)
const TOP_Y  = 6.0;           // y of the newest node

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _spine = null;            // THREE.Line — the timeline spine
let _nodes = [];              // Array<{ mesh, halo, backend, cited }>
let _pulse = 0;               // descending-pulse phase

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,   // top honesty label VERBATIM (MODELED)
  count:     null,   // items shown
  registered:null,   // total registered surfaces
  cited:     null,
  histSrc:   null,   // "git-log" | "registry-order"
  histLabel: null,   // "LIVE" | "DEGRADED"
  trustCeil: null,
  lambda:    null,
  locked:    null,
  items:     [],     // [{ id, title, backend, label, cited, added }]
  state:     "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.5, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpine();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildSpine() {
  const THREE = _THREE;
  const g = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, TOP_Y, 0), new THREE.Vector3(0, TOP_Y - SPAN_Y, 0),
  ]);
  _spine = new THREE.Line(g, new THREE.LineBasicMaterial({
    color: C_SPINE, transparent: true, opacity: 0.4,
  }));
  _group.add(_spine);
}

// Build (or rebuild) one node per feed item, newest at the top. Called on each live snapshot
// so the timeline always mirrors the CURRENT feed (never a stale hard-coded set).
function _buildNodes() {
  const THREE = _THREE;
  _disposeNodes();
  const list = S.items;
  const n = list.length;
  if (!n) return;

  const nodeGeo = new THREE.SphereGeometry(0.28, 16, 12);
  const haloGeo = new THREE.RingGeometry(0.36, 0.46, 22);
  const step = n > 1 ? SPAN_Y / (n - 1) : 0;

  for (let i = 0; i < n; i++) {
    const it = list[i];
    const y = TOP_Y - step * i;                 // newest (i=0) at top
    const x = (i % 2 === 0) ? 1.1 : -1.1;        // alternate sides of the spine
    const color = _backendColor(it.backend);

    const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.3, transparent: true, opacity: 0.92,
    }));
    mesh.position.set(x, y, 0);
    _group.add(mesh);

    // connector spine -> node
    const cg = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, y, 0), new THREE.Vector3(x, y, 0),
    ]);
    const conn = new THREE.Line(cg, new THREE.LineBasicMaterial({
      color: C_SPINE, transparent: true, opacity: 0.18,
    }));
    _group.add(conn);

    let halo = null;
    if (it.cited) {
      halo = new THREE.Mesh(haloGeo, new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.5, side: THREE.DoubleSide,
      }));
      halo.position.copy(mesh.position);
      _group.add(halo);
    }

    _nodes.push({ mesh, halo, conn, backend: it.backend, cited: !!it.cited });
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
  _nodes.forEach((nd) => { rm(nd.mesh); rm(nd.halo); rm(nd.conn); });
  _nodes = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  const sm = (j && j.summary) || {};
  S.count      = typeof sm.shown === "number" ? sm.shown : null;
  S.registered = typeof sm.registered_surfaces === "number" ? sm.registered_surfaces : null;
  S.cited      = typeof sm.items_with_citations === "number" ? sm.items_with_citations : 0;

  const h = (j && j.history) || {};
  S.histSrc   = typeof h.source === "string" ? h.source : null;
  S.histLabel = typeof h.label === "string" ? h.label : null;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  const arr = Array.isArray(j && j.items) ? j.items : [];
  S.items = arr.map((e) => ({
    id: e && e.id,
    title: e && e.title,
    backend: e && e.backend,
    label: e && e.label,
    added: e && e.added,
    cited: !!(e && Array.isArray(e.citations) && e.citations.length),
  }));

  _buildNodes();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.10;

  const live = S.state === "live";
  if (_nodes.length) {
    _pulse = (t * 0.00018) % 1;
    const lead = Math.floor(_pulse * _nodes.length);
    for (let i = 0; i < _nodes.length; i++) {
      const nd = _nodes[i];
      const near = Math.abs(i - lead) <= 1;
      nd.mesh.material.emissiveIntensity = near && live ? 0.85 : (live ? 0.3 : 0.12);
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
    chips: [{ label: "MODELED", text: "what's new", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The estate’s <b>recently-added surfaces</b>, newest first, each with the honest data ' +
    'label its <b>own backend</b> emits and whether it cites papers. <b>Honest by ' +
    'construction</b> — derived live from the Frontier Index catalog + the <b>real git ' +
    'add-history</b>, never a hand-maintained changelog that can drift. This tab’s own ' +
    'label is <b>MODELED</b>; per-surface labels are read <b>VERBATIM</b> and never upgraded; ' +
    'commit dates are real or honestly omitted. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("wn-count",  "recently-added shown"));
  grid.appendChild(kpiRow("wn-reg",    "registered surfaces"));
  grid.appendChild(kpiRow("wn-cited",  "items citing papers"));
  grid.appendChild(kpiRow("wn-hist",   "history source"));
  grid.appendChild(kpiRow("wn-locked", "locked proofs"));
  grid.appendChild(kpiRow("wn-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("wn-lambda", "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable feed list (text mirror of the timeline; verbatim labels).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:190px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> a11oy-native &nbsp; ' +
    '<span style="color:#f4b23a">■</span> cross-origin-fallback &nbsp; ' +
    '<span style="color:#8494a1">■</span> frontend-only &nbsp; · halo = cites papers. ' +
    'MODELED · labels read verbatim, never upgraded.';
  card.appendChild(leg);

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
  pd.id = "wn-plain";
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
    "<b>What this means:</b> a live, honest changelog of what the platform shipped most " +
    "recently. The order comes from the <b>real git history</b> (when each surface was " +
    "actually added), and each entry shows that surface’s <b>own</b> honest data label " +
    "— word-for-word, never rounded up — plus whether it cites real papers. Because " +
    "the list is generated from the running app and the repository itself, it cannot quietly " +
    "disagree with what is actually wired. A CI guard fails the build if this feed ever lists " +
    "a surface that is not actually registered. No “verified/1.0” state; trust " +
    "ceiling 0.97.";
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

function _paintList() {
  const wrap = _el["list"];
  if (!wrap) return;
  wrap.innerHTML = "";
  S.items.forEach((it) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:66%";
    const when = it.added ? String(it.added).slice(0, 10) : "—";
    left.textContent = (it.id || "?") + "  ·  " + when;
    const lab = document.createElement("b");
    const col = it.backend === "a11oy-native" ? "#3af4c8" : (it.backend === "cross-origin-fallback" ? "#f4b23a" : "#8494a1");
    lab.style.cssText = "color:" + col + ";font-variant-numeric:tabular-nums";
    lab.textContent = it.label || "—";
    row.appendChild(left); row.appendChild(lab);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "what's new" });
  _set("wn-count",  t || _n(S.count));
  _set("wn-reg",    t || _n(S.registered));
  _set("wn-cited",  t || _n(S.cited));
  _set("wn-hist",   t || (S.histSrc ? (S.histSrc + (S.histLabel ? " (" + S.histLabel + ")" : "")) : "—"));
  _set("wn-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("wn-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("wn-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

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
  _spine = null; _nodes = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _pulse = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.count = S.registered = S.cited = null;
  S.histSrc = S.histLabel = null;
  S.trustCeil = S.lambda = S.locked = null; S.items = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
