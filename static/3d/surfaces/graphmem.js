// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/graphmem.js — GOVERNED MULTI-GRAPH AGENTIC MEMORY (MAGMA) organ for the
// holographic frontier ring, clean-room-inspired by (NOT a reproduction of) MAGMA:
// A Multi-Graph based Agentic Memory Architecture (arXiv:2601.03236).
//
// Renders the same 12-item synthetic memory corpus across FOUR stacked graph LAYERS —
// semantic / temporal / causal / entity — each on its own horizontal plane, with the
// typed edges of that layer drawn in-plane. On each poll, the query's POLICY-GUIDED
// TRAVERSAL PATH is highlighted hop-by-hop across the layers (each hop lit on the layer
// whose graph it used), and the retrieved node set lights up. Honesty label "MODELED"
// is read VERBATIM from the JSON (top-level `label` OR nested `payload.label`) and shown
// as-is; it is never upgraded.
//
// Surface export shape (mirrors episodic.js / titans.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   corpus[]            — {id, text, t, tags, entity, cause}
//   graphs.{semantic|temporal|causal|entity} — adjacency lists (id -> [ids])
//   traversal.path[]    — {hop, from, to, graph}  (the explainable PATH)
//   traversal.retrieved — retrieved node ids (typed multi-graph)
//   baseline.retrieved  — monolithic flat-BFS top-k (the honest comparison)
//   scores              — typed vs flat precision/recall/F1 vs a gold set
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   MAGMA — A Multi-Graph based Agentic Memory Architecture (Jiang, Li, Li, Li):
//     https://arxiv.org/abs/2601.03236
//   Multi-Agent Memory from a Computer Architecture Perspective (Yu et al.; positioning):
//     https://arxiv.org/abs/2603.10062
//
// HONESTY LABEL: MODELED (toy symbolic simulation of the multi-graph + policy-traversal
//   MECHANISM; four hand-built graphs over a 12-item synthetic corpus; the 'policy' is a
//   fixed state machine, not a learned agent; relevance scored vs a hand-labeled gold set;
//   does NOT reproduce MAGMA's LoCoMo/LongMemEval results). Read verbatim; never upgraded.
// COLOURS: lattice-blue 0x5b8dee (nodes / temporal + semantic layer edges), violet-blue
//   0x8a6bff (retrieved-set flash + causal + entity layer edges — data-viz only),
//   proof-teal 0x3af4c8 (highlighted TRAVERSAL PATH + query start marker), greys for
//   degraded / no-data. Purple BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored r170 through the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

const ID    = "graphmem";
const TITLE = "Multi-Graph Agentic Memory · MAGMA (live)";

// Endpoint on the dedicated killinchu Space (isolated compute), reached cross-origin.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/graphmem/traverse?seed=42&query_type=why_query&max_hops=3&top_k=4";

// data-viz hues — purple BANNED
const C_NODE   = 0x5b8dee;  // lattice-blue (memory-item node / temporal + semantic edges)
const C_TOP    = 0x8a6bff;  // violet-blue (retrieved-set flash + causal + entity edges — data-viz only)
const C_PATH   = 0x3af4c8;  // proof-teal (highlighted traversal PATH + query start marker)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / non-retrieved node)
const C_GRID   = 0x1b3a44;  // floor / link colour

// four graph layers, each on its own y-plane
const LAYERS = ["semantic", "temporal", "causal", "entity"];
const LAYER_Y = { semantic: 0.8, temporal: 3.2, causal: 5.6, entity: 8.0 };
const LAYER_EDGE_COL = { semantic: C_NODE, temporal: C_NODE, causal: C_TOP, entity: C_TOP };

const N_SLOTS = 12;   // memory items in the fixed synthetic corpus
const RADIUS  = 6.5;  // radius of the node ring within each layer plane

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _nodes = {};        // { layerName: Array<THREE.Mesh> } — node ring replicated per layer
let _edgeLines = {};    // { layerName: THREE.LineSegments } — typed edges per layer
let _pathLines = null;  // THREE.LineSegments — highlighted traversal path (cross-layer)
let _startMarker = {};  // { layerName: THREE.Mesh } — query start marker per layer

// per-node flash timers (retrieved highlight) — one bank shared across layers by index
const _flash = new Float32Array(N_SLOTS);

// live state
const S = {
  label:      null,
  corpus:     null,   // Array<{id,text,t,tags,entity,cause}>
  graphs:     null,   // {semantic,temporal,causal,entity} adjacency
  path:       null,   // Array<{hop,from,to,graph}>
  retrieved:  null,   // Array<int> typed traversal retrieved set
  baseRetr:   null,   // Array<int> flat baseline retrieved set
  queryType:  null,
  queryText:  null,
  scores:     null,   // {typed_traversal, flat_baseline, f1_gain}
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 26);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 4.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLayers();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onTraverse, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(48, 48, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

// node ring position for slot i within a layer plane
function _slotPos(i, y) {
  const THREE = _THREE;
  const a = (i / N_SLOTS) * Math.PI * 2;
  return new THREE.Vector3(Math.cos(a) * RADIUS, y, Math.sin(a) * RADIUS);
}

function _buildLayers() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.26, 14, 10);
  _nodes = {}; _startMarker = {};
  LAYERS.forEach((layer) => {
    const y = LAYER_Y[layer];
    // faint layer plane label ring (torus) to visually separate the four graphs
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(RADIUS, 0.03, 6, 64),
      new THREE.MeshBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.35 }),
    );
    ring.rotation.x = Math.PI / 2; ring.position.y = y;
    _group.add(ring);

    const arr = [];
    for (let i = 0; i < N_SLOTS; i++) {
      const mat = new THREE.MeshStandardMaterial({
        color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15,
        metalness: 0.25, roughness: 0.55,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(_slotPos(i, y));
      _group.add(mesh);
      arr.push(mesh);
    }
    _nodes[layer] = arr;

    // query start marker for this layer (teal octahedron, hidden until live)
    const mk = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.44, 0),
      new THREE.MeshStandardMaterial({ color: C_PATH, emissive: C_PATH, emissiveIntensity: 0.35, wireframe: true, transparent: true, opacity: 0.0 }),
    );
    mk.position.copy(_slotPos(0, y));
    _group.add(mk);
    _startMarker[layer] = mk;
  });
}

// =============================================================================
// live data handler
// =============================================================================
function _onTraverse(j) {
  // The endpoint may return fields at the TOP LEVEL or nested under `payload`.
  // Read the honesty label VERBATIM from whichever holds it — never upgrade.
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.corpus    = Array.isArray(p.corpus) ? p.corpus : null;
  S.graphs    = (p.graphs && typeof p.graphs === "object") ? p.graphs : null;
  const trav  = p.traversal || {};
  S.path      = Array.isArray(trav.path) ? trav.path : null;
  S.retrieved = Array.isArray(trav.retrieved) ? trav.retrieved : null;
  const base  = p.baseline || {};
  S.baseRetr  = Array.isArray(base.retrieved) ? base.retrieved : null;
  S.queryType = p.query_type || null;
  S.queryText = (p.query && p.query.text) || null;
  S.scores    = (p.scores && typeof p.scores === "object") ? p.scores : null;

  _layoutGraphs();
  _paintOverlay();
}

// =============================================================================
// geometry updater — colours nodes per layer, draws typed edges, highlights PATH
// =============================================================================
function _layoutGraphs() {
  const THREE = _THREE;
  const live = S.state === "live";
  const retr = new Set(S.retrieved || []);
  const graphs = S.graphs || {};

  // colour nodes on each layer: retrieved -> violet flash, else lattice-blue; grey if not live
  LAYERS.forEach((layer) => {
    const arr = _nodes[layer] || [];
    arr.forEach((mesh, i) => {
      const got = retr.has(i);
      const col = live ? (got ? C_TOP : C_NODE) : C_DIM;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = live ? (got ? 0.85 : 0.22) : 0.1;
      mesh.scale.setScalar(live ? (got ? 1.15 : 0.7) : 0.55);
      if (live && got) _flash[i] = 90;
    });
  });

  // rebuild typed edge geometry per layer
  LAYERS.forEach((layer) => {
    if (_edgeLines[layer]) {
      _group.remove(_edgeLines[layer]);
      _edgeLines[layer].geometry.dispose();
      _edgeLines[layer].material.dispose();
      _edgeLines[layer] = null;
    }
    const adj = graphs[layer];
    if (!adj) return;
    const y = LAYER_Y[layer];
    const pts = [];
    Object.keys(adj).forEach((k) => {
      const a = parseInt(k, 10);
      const dsts = adj[k] || [];
      dsts.forEach((b) => {
        if (a < 0 || b < 0 || a >= N_SLOTS || b >= N_SLOTS) return;
        pts.push(_slotPos(a, y), _slotPos(b, y));
      });
    });
    if (pts.length) {
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      const col = live ? LAYER_EDGE_COL[layer] : C_DIM;
      _edgeLines[layer] = new THREE.LineSegments(
        g, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: live ? 0.32 : 0.08 }),
      );
      _group.add(_edgeLines[layer]);
    }
  });

  // highlighted TRAVERSAL PATH — teal segments, each hop drawn on its graph's layer
  if (_pathLines) {
    _group.remove(_pathLines); _pathLines.geometry.dispose(); _pathLines.material.dispose(); _pathLines = null;
  }
  const path = S.path || [];
  if (path.length && live) {
    const pts = [];
    path.forEach((h) => {
      const y = LAYER_Y[h.graph] != null ? LAYER_Y[h.graph] : LAYER_Y.semantic;
      if (h.from < 0 || h.to < 0 || h.from >= N_SLOTS || h.to >= N_SLOTS) return;
      pts.push(_slotPos(h.from, y), _slotPos(h.to, y));
    });
    if (pts.length) {
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      _pathLines = new THREE.LineSegments(
        g, new THREE.LineBasicMaterial({ color: C_PATH, transparent: true, opacity: 0.9 }),
      );
      _group.add(_pathLines);
    }
  }

  // start marker per layer at the query start node
  const startNode = (path[0] && typeof path[0].from === "number") ? path[0].from : 0;
  LAYERS.forEach((layer) => {
    const mk = _startMarker[layer];
    if (!mk) return;
    mk.position.copy(_slotPos(startNode, LAYER_Y[layer]));
    const col = live ? C_PATH : C_DIM;
    mk.material.color.setHex(col);
    mk.material.emissive.setHex(col);
    mk.material.emissiveIntensity = live ? 0.5 : 0.1;
    mk.material.opacity = live ? 0.7 : 0.0;
  });
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.2;
  const live = S.state === "live";
  LAYERS.forEach((layer) => {
    const mk = _startMarker[layer];
    if (mk) { mk.rotation.y += 0.01; mk.rotation.x += 0.004; }
    const arr = _nodes[layer] || [];
    arr.forEach((mesh, i) => {
      if (_flash[i] > 0) {
        const f = _flash[i] / 90;
        const col = live ? C_TOP : C_DIM;
        mesh.material.emissive.setHex(col);
        mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.2 + 0.9 * f);
      }
    });
  });
  // decay flash once per frame (shared across layers)
  for (let i = 0; i < _flash.length; i++) if (_flash[i] > 0) _flash[i] -= 1;
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,460px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'One synthetic memory corpus stored across <b>four typed graphs</b> \u2014 semantic, ' +
    'temporal, causal, entity \u2014 shown as four stacked layers. A query runs a fixed ' +
    '<b>policy-guided traversal</b>; the teal <b>PATH</b> shows exactly which node it ' +
    'reached via which graph, versus a monolithic flat-BFS baseline. Honesty label ' +
    '<b>MODELED</b> (toy symbolic sim; clean-room-inspired by MAGMA \u2014 not a ' +
    'reproduction). 0 runtime CDN.';
  _overlay.appendChild(sub);

  const brow = document.createElement("div");
  brow.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  if (_badge && _badge.el) brow.appendChild(_badge.el);
  _overlay.appendChild(brow);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "graphmem";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";

  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:60%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("gm-query",  "query type"));
  grid.appendChild(kpiRow("gm-typed",  "typed traversal (retrieved \u2192 F1)"));
  grid.appendChild(kpiRow("gm-flat",   "flat baseline (retrieved \u2192 F1)"));
  grid.appendChild(kpiRow("gm-gain",   "F1 gain (typed \u2212 flat)"));
  grid.appendChild(kpiRow("gm-hops",   "traversal PATH hops"));
  grid.appendChild(kpiRow("gm-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "MAGMA arxiv.org/abs/2601.03236 (Jiang, Li, Li, Li) \u00b7 Multi-Agent Memory arxiv.org/abs/2603.10062 (Yu et al.). MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "gm-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  (ctx.container || document.body).appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const qt = S.queryText || S.queryType || "loading\u2026";
  const ts = (S.scores && S.scores.typed_traversal) ? S.scores.typed_traversal : null;
  const bs = (S.scores && S.scores.flat_baseline) ? S.scores.flat_baseline : null;
  const tf = ts ? fx(ts.f1, 3) : "\u2026";
  const bf = bs ? fx(bs.f1, 3) : "\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Most AI memory today is one big \u201csimilarity\u201d pile: ask " +
    "a question and it hands back whatever looks vaguely related, with no way to say <i>how</i> " +
    "it\u2019s related. This organ demonstrates a <b>different design</b>: the same memories are " +
    "stored in <b>four separate graphs</b> \u2014 by meaning, by time, by cause-and-effect, and by " +
    "who/what is involved. A question then <b>walks the right graph</b>: \u201cwhy did X happen?\u201d " +
    "follows the cause chain; \u201cwhat happened around then?\u201d follows the timeline. Right now for " +
    "\u201c<b>" + qt + "</b>\u201d the typed walk scores <b>F1 " + tf + "</b> versus <b>" + bf + "</b> for " +
    "the flat baseline \u2014 and, crucially, it returns the <b>exact path</b> that justifies each " +
    "answer, so it\u2019s auditable. " +
    "Honest caveat: this is a <b>MODELED</b> toy simulation \u2014 four graphs hand-built from a " +
    "12-item synthetic corpus with integer adjacency lists; the \u201cpolicy\u201d is a fixed state " +
    "machine, not a learned agent; \u201crelevance\u201d is scored against a hand-labeled gold set. It " +
    "shows the ordering/explainability advantage of typed traversal on constructed queries; it " +
    "does <b>not</b> reproduce MAGMA\u2019s LoCoMo/LongMemEval results and makes no claim about real " +
    "long-horizon agent performance.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("gm-query", t || (S.queryType || "\u2014"));

  const ts = (S.scores && S.scores.typed_traversal) ? S.scores.typed_traversal : null;
  const bs = (S.scores && S.scores.flat_baseline) ? S.scores.flat_baseline : null;
  const nT = S.retrieved ? S.retrieved.length : null;
  const nB = S.baseRetr ? S.baseRetr.length : null;
  _set("gm-typed", t || (ts ? (nT + " \u2192 F1 " + fx(ts.f1, 3)) : "\u2014"));
  _set("gm-flat",  t || (bs ? (nB + " \u2192 F1 " + fx(bs.f1, 3)) : "\u2014"));
  _set("gm-gain",  t || (S.scores && typeof S.scores.f1_gain === "number" ? fx(S.scores.f1_gain, 3) : "\u2014"));
  _set("gm-hops",  t || (S.path ? String(S.path.length) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("gm-label", t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _overlay = null;
  _nodes = {}; _edgeLines = {}; _pathLines = null; _startMarker = {};
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.corpus = S.graphs = S.path = S.retrieved = S.baseRetr = null;
  S.queryType = S.queryText = S.scores = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
