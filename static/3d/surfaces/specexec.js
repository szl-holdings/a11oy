// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/specexec.js — TREE SPECULATIVE EXECUTION organ for the holographic
// frontier ring (token-tree speculative decoding: a static fixed-shape tree vs.
// an EAGLE-2-style dynamic Expansion/Rerank tree, verified against a scripted
// min(1,p/q) acceptance oracle). Renders three views from the live snapshot at
// /api/killinchu/v1/specexec/tree:
//   (1) a 3D TREE DIAGRAM — nodes laid out by depth (y-axis), colored by depth,
//       edges (root→child) widened by the child's synthetic confidence/value V_i;
//   (2) a TREE CAUSAL-ATTENTION MASK heatmap — the binary ancestor mask (each
//       node attends only to its ancestors) that lets the whole tree be verified
//       in ONE forward pass (SpecInfer);
//   (3) a BAR CHART of expected accepted-path length: static tree vs. dynamic
//       (Expansion/Rerank) tree under the same synthetic confidences.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is;
// it is never upgraded.
//
// Surface export shape (mirrors ternary.js / kvcache.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   depth, branch, budget, static_nodes, dynamic_nodes,
//   static_expected_accepted_path_length, dynamic_expected_accepted_path_length,
//   improvement_ratio, nodes[]{id,parent,depth,confidence,value,accepted},
//   attention_mask[][]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   Sequoia (DP-optimal token trees): arXiv:2402.12374
//     https://arxiv.org/abs/2402.12374
//   EAGLE-2 (context-aware dynamic draft tree; Expansion/Rerank): arXiv:2406.16858
//     https://arxiv.org/abs/2406.16858
//   Medusa (multi-head, tree attention, typical acceptance): arXiv:2401.10774
//     https://arxiv.org/abs/2401.10774
//   SpecInfer (token-tree verification; tree-structured causal mask), CMU PDF:
//     https://www.cs.cmu.edu/~zhihaoj2/papers/specinfer.pdf
//
// HONESTY LABELS: MODELED (deterministic toy tree-walk demonstrating the tree
//   topology + Expansion/Rerank value-propagation + min(1,p/q) acceptance
//   MECHANISM on a synthetic token-tree; NOT a live LLM; no real draft/target
//   model, no real tokens, no forward pass; expected-path-length values are
//   computed exactly and DISPLAYED). Read verbatim from JSON; never upgraded.
// COLOURS (allowed hues only; purple BANNED): lattice-blue 0x5b8dee,
//   violet-blue 0x8a6bff, proof-teal 0x3af4c8, greys 0x5a6570 / 0x42505d.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "specexec";
const TITLE = "Tree Speculative Execution";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/specexec/tree?seed=42&depth=4&branch=3&budget=24";

// data-viz hues — purple BANNED
const C_D0   = 0x3af4c8;  // proof-teal   (depth 0 / root)
const C_D1   = 0x5b8dee;  // lattice-blue (depth 1)
const C_D2   = 0x8a6bff;  // violet-blue  (depth 2)
const C_D3   = 0x3af4c8;  // proof-teal   (depth 3 — cycles back)
const C_DEEP = 0x5b8dee;  // lattice-blue (depth ≥ 4)
const C_EDGE = 0x3af4c8;  // proof-teal   (tree edges)
const C_DYN  = 0x3af4c8;  // proof-teal   (dynamic bar)
const C_STAT = 0x5b8dee;  // lattice-blue (static bar)
const C_MASK = 0x8a6bff;  // violet-blue  (attention-mask "attends" cell)
const C_DIM  = 0x42505d;  // grey (degraded / no-live-data)
const C_ZERO = 0x5a6570;  // grey (mask "no-attend" / empty)
const C_GRID = 0x1b3a44;  // floor / link colour

// layout geometry
const DEPTH_GAP = 1.6;    // world-units per depth level (y)
const SPREAD    = 6.0;    // horizontal spread of the tree (x)
const MASK_ORIGIN = { x: 9.0, y: 0.2, z: 0.0 };
const MASK_CELL   = 0.34;
const MASK_MAX    = 32;   // cap cells per axis (matches organ node cap)
const BAR_ORIGIN  = { x: -3.0, y: 0.0, z: 8.0 };

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor    = null;
let _treeGroup = null;               // THREE.Group — nodes + edges
let _maskMesh  = [];                 // Array<THREE.Mesh> — mask cells (MASK_MAX^2)
let _barStatic = null;               // THREE.Mesh — static bar
let _barDyn    = null;               // THREE.Mesh — dynamic bar

// live state
const S = {
  label:      null,
  depth:      null,
  branch:     null,
  budget:     null,
  staticNodes: null,
  dynamicNodes: null,
  staticEpl:  null,   // static_expected_accepted_path_length
  dynamicEpl: null,   // dynamic_expected_accepted_path_length
  improvement: null,  // improvement_ratio
  nodes:      null,   // array
  mask:       null,   // 2D array
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 9, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 2, 3); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildTreeGroup();
  _buildMaskGrid();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSnap, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _repaintScene(); } }));

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
  _floor = grid;
}

function _buildTreeGroup() {
  const THREE = _THREE;
  _treeGroup = new THREE.Group();
  _group.add(_treeGroup);
}

// Pre-allocate a fixed MASK_MAX x MASK_MAX grid of mask cells; toggle
// visibility / color in-place as live data arrives (no per-poll geometry churn).
function _buildMaskGrid() {
  const THREE = _THREE;
  const cellGeo = new THREE.PlaneGeometry(MASK_CELL * 0.9, MASK_CELL * 0.9);
  for (let r = 0; r < MASK_MAX; r++) {
    for (let c = 0; c < MASK_MAX; c++) {
      const mesh = new THREE.Mesh(
        cellGeo,
        new THREE.MeshBasicMaterial({ color: C_ZERO, transparent: true, opacity: 0.0, side: THREE.DoubleSide }),
      );
      mesh.position.set(MASK_ORIGIN.x + c * MASK_CELL, MASK_ORIGIN.y + (MASK_MAX - r) * MASK_CELL, MASK_ORIGIN.z);
      mesh.visible = false;
      _group.add(mesh);
      _maskMesh.push(mesh);
    }
  }
}

function _buildBars() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(0.9, 1.0, 0.9);
  _barStatic = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_STAT, emissive: C_STAT, emissiveIntensity: 0.4, transparent: true, opacity: 0.9 }),
  );
  _barStatic.position.set(BAR_ORIGIN.x, 0.5, BAR_ORIGIN.z);
  _barStatic.scale.y = 0.01;
  _group.add(_barStatic);

  _barDyn = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_DYN, emissive: C_DYN, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }),
  );
  _barDyn.position.set(BAR_ORIGIN.x + 1.4, 0.5, BAR_ORIGIN.z);
  _barDyn.scale.y = 0.01;
  _group.add(_barDyn);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSnap(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.depth        = typeof src.depth  === "number" ? src.depth  : null;
  S.branch       = typeof src.branch === "number" ? src.branch : null;
  S.budget       = typeof src.budget === "number" ? src.budget : null;
  S.staticNodes  = typeof src.static_nodes  === "number" ? src.static_nodes  : null;
  S.dynamicNodes = typeof src.dynamic_nodes === "number" ? src.dynamic_nodes : null;
  S.staticEpl    = typeof src.static_expected_accepted_path_length  === "number" ? src.static_expected_accepted_path_length  : null;
  S.dynamicEpl   = typeof src.dynamic_expected_accepted_path_length === "number" ? src.dynamic_expected_accepted_path_length : null;
  S.improvement  = typeof src.improvement_ratio === "number" ? src.improvement_ratio : null;
  S.nodes        = Array.isArray(src.nodes) ? src.nodes : null;
  S.mask         = Array.isArray(src.attention_mask) ? src.attention_mask : null;

  _repaintScene();
  _paintOverlay();
}

// =============================================================================
// scene painters
// =============================================================================
function _depthColor(d) {
  switch (d) {
    case 0: return C_D0;
    case 1: return C_D1;
    case 2: return C_D2;
    case 3: return C_D3;
    default: return C_DEEP;
  }
}

function _disposeTree() {
  if (!_treeGroup) return;
  const kids = _treeGroup.children.slice();
  kids.forEach((o) => {
    _treeGroup.remove(o);
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) {
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => { if (m.dispose) m.dispose(); });
    }
  });
}

function _repaintScene() {
  _repaintTree();
  _repaintMask();
  _repaintBars();
}

// 3D tree: place nodes by depth (y), spread siblings across x within each depth
// band; color by depth; edge tube radius scaled by child confidence/value.
function _repaintTree() {
  const THREE = _THREE;
  _disposeTree();
  const live = S.state === "live";
  const nodes = (live && S.nodes) ? S.nodes : null;
  if (!nodes || !nodes.length) {
    // degraded placeholder: a single dim node so the scene is never empty
    const geo = new THREE.SphereGeometry(0.22, 12, 12);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.35 }));
    m.position.set(0, DEPTH_GAP, 0);
    _treeGroup.add(m);
    return;
  }

  // group node indices by depth for horizontal layout
  const byDepth = {};
  let maxDepth = 0;
  nodes.forEach((n) => {
    const d = n.depth || 0;
    if (!byDepth[d]) byDepth[d] = [];
    byDepth[d].push(n);
    if (d > maxDepth) maxDepth = d;
  });

  // assign world positions
  const pos = {};  // id -> {x,y,z}
  Object.keys(byDepth).forEach((dk) => {
    const d = Number(dk);
    const arr = byDepth[d];
    const count = arr.length;
    arr.forEach((n, i) => {
      const frac = count > 1 ? (i / (count - 1)) : 0.5;
      const x = (frac - 0.5) * SPREAD;
      const y = DEPTH_GAP * (maxDepth - d) + 0.6;  // root highest
      const z = 0;
      pos[n.id] = { x, y, z };
    });
  });

  // nodes as spheres (radius scaled a touch by value)
  nodes.forEach((n) => {
    const p = pos[n.id];
    if (!p) return;
    const v = typeof n.value === "number" ? n.value : 0.5;
    const rad = 0.14 + 0.16 * Math.max(0, Math.min(1, v));
    const geo = new THREE.SphereGeometry(rad, 14, 14);
    const col = _depthColor(n.depth || 0);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.55, transparent: true, opacity: 0.95 }));
    m.position.set(p.x, p.y, p.z);
    _treeGroup.add(m);
  });

  // edges as thin cylinders; radius scaled by child confidence
  nodes.forEach((n) => {
    if (n.parent == null || n.parent < 0) return;
    const a = pos[n.id];
    const b = pos[n.parent];
    if (!a || !b) return;
    const conf = typeof n.confidence === "number" ? n.confidence : 0.5;
    const rad = 0.015 + 0.075 * Math.max(0, Math.min(1, conf));
    const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    const len = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.001;
    const geo = new THREE.CylinderGeometry(rad, rad, len, 8);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_EDGE, emissive: C_EDGE, emissiveIntensity: 0.35, transparent: true, opacity: 0.6 }));
    // midpoint
    m.position.set((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
    // orient cylinder (default +y) to point from b->a
    const up = new THREE.Vector3(0, 1, 0);
    const dir = new THREE.Vector3(dx, dy, dz).normalize();
    const quat = new THREE.Quaternion().setFromUnitVectors(up, dir);
    m.quaternion.copy(quat);
    _treeGroup.add(m);
  });
}

function _repaintMask() {
  const live = S.state === "live";
  const mask = (live && S.mask) ? S.mask : null;
  const n = mask ? Math.min(mask.length, MASK_MAX) : 0;
  for (let r = 0; r < MASK_MAX; r++) {
    for (let c = 0; c < MASK_MAX; c++) {
      const mesh = _maskMesh[r * MASK_MAX + c];
      if (!mask || r >= n || c >= n) {
        mesh.visible = false;
        continue;
      }
      mesh.visible = true;
      const on = mask[r] && mask[r][c] === 1;
      const col = on ? C_MASK : C_ZERO;
      mesh.material.color.setHex(col);
      mesh.material.opacity = on ? 0.9 : 0.14;
    }
  }
}

function _repaintBars() {
  const live = S.state === "live";
  const s = (live && typeof S.staticEpl === "number") ? S.staticEpl : 0;
  const d = (live && typeof S.dynamicEpl === "number") ? S.dynamicEpl : 0;
  const maxv = Math.max(s, d, 1);
  const scale = 5.0 / maxv;   // tallest bar ≈ 5 world units
  if (_barStatic) {
    const h = Math.max(0.01, s * scale);
    _barStatic.scale.y = h;
    _barStatic.position.y = h / 2;
    _barStatic.material.color.setHex(live ? C_STAT : C_DIM);
    _barStatic.material.emissive.setHex(live ? C_STAT : C_DIM);
    _barStatic.material.opacity = live ? 0.9 : 0.35;
  }
  if (_barDyn) {
    const h = Math.max(0.01, d * scale);
    _barDyn.scale.y = h;
    _barDyn.position.y = h / 2;
    _barDyn.material.color.setHex(live ? C_DYN : C_DIM);
    _barDyn.material.emissive.setHex(live ? C_DYN : C_DIM);
    _barDyn.material.opacity = live ? 0.9 : 0.35;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_treeGroup) _treeGroup.rotation.y = Math.sin(t * 0.00008) * 0.12;
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
    maxWidth: "min(94%,470px)",
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
    'Instead of drafting one linear chain, tree speculative decoding drafts a <b>tree</b> of candidate ' +
    'tokens \u2014 each root\u2192node path is a candidate sequence, siblings are alternatives at the same ' +
    'position. A <b>tree causal-attention mask</b> (each token attends only to its ancestors) lets the ' +
    'whole tree be verified in one pass. This view builds the tree two ways \u2014 a <b>static</b> fixed ' +
    'shape vs. an EAGLE-2-style <b>dynamic</b> Expansion/Rerank on synthetic confidences (value ' +
    'V<sub>i</sub> = product of confidences root\u2192i) \u2014 then walks both against a scripted ' +
    '<b>min(1, p/q)</b> acceptance oracle to count the expected accepted-path length. Honesty label ' +
    '<b>MODELED</b> (deterministic toy tree-walk, NOT a live LLM). 0 runtime CDN.';
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
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "tree speculative execution";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("sx-tree",     "tree (depth / branch / budget)"));
  grid.appendChild(kpiRow("sx-nodes",    "nodes (static / dynamic)"));
  grid.appendChild(kpiRow("sx-static",   "E[accepted path] \u2014 static (MEASURED)"));
  grid.appendChild(kpiRow("sx-dynamic",  "E[accepted path] \u2014 dynamic (MEASURED)"));
  grid.appendChild(kpiRow("sx-improve",  "improvement (dynamic / static)"));
  grid.appendChild(kpiRow("sx-mask",     "tree causal-attention mask"));
  grid.appendChild(kpiRow("sx-label",    "honesty label"));
  card.appendChild(grid);

  const legend = document.createElement("div");
  legend.style.cssText = "font-size:10px;color:#9fb1bf;line-height:1.5;display:flex;gap:10px;flex-wrap:wrap";
  legend.innerHTML =
    '<span style="color:#3af4c8">\u25cf dynamic / root</span>' +
    '<span style="color:#5b8dee">\u25cf static / depth</span>' +
    '<span style="color:#8a6bff">\u25cf mask attends</span>' +
    '<span style="color:#5a6570">\u25cf no-attend</span>';
  card.appendChild(legend);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Tree speculative decoding \u2014 Sequoia arXiv:2402.12374 \u00b7 EAGLE-2 arXiv:2406.16858 \u00b7 Medusa arXiv:2401.10774 \u00b7 SpecInfer (CMU). MODELED \u00b7 not claimed-as.";
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
  pd.id = "sx-plain";
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
  const sEpl = S.staticEpl   != null ? S.staticEpl.toFixed(2)   : "loading\u2026";
  const dEpl = S.dynamicEpl  != null ? S.dynamicEpl.toFixed(2)  : "loading\u2026";
  const imp  = S.improvement != null ? S.improvement.toFixed(2) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> To speed up a language model, a small \u201cdraft\u201d step guesses several of the " +
    "next words at once so the big model can check them in a single batch. Guessing a <b>tree</b> of possible " +
    "words (with branches for alternatives) beats guessing a single straight line, because more good guesses " +
    "survive the check. This view builds the guess-tree two ways: a fixed shape (<b>static</b>) and a smarter " +
    "shape that spends its limited budget on the most promising branches (<b>dynamic</b>, the EAGLE-2 idea). " +
    "Under the same scripted accept/reject rule, the static tree commits about <b>" + sEpl + "</b> words on " +
    "average and the dynamic tree about <b>" + dEpl + "</b> \u2014 roughly <b>" + imp + "</b> as many. The grid on " +
    "the right is the <b>attention mask</b>: it shows each guessed word only looking back at its own ancestors, " +
    "which is what lets the whole tree be checked in one pass. This is a <b>MODELED</b> deterministic toy " +
    "tree-walk on made-up confidence numbers \u2014 <b>not a live LLM</b>, no real model is queried, and no " +
    "wall-clock speedup is claimed. The numbers shown are computed exactly and displayed, not hidden.";
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
  _set("sx-tree",    t || ((S.depth != null && S.branch != null && S.budget != null) ? (S.depth + " / " + S.branch + " / " + S.budget) : "\u2014"));
  _set("sx-nodes",   t || ((S.staticNodes != null && S.dynamicNodes != null) ? (S.staticNodes + " / " + S.dynamicNodes) : "\u2014"));
  _set("sx-static",  t || fx(S.staticEpl, 3));
  _set("sx-dynamic", t || fx(S.dynamicEpl, 3));
  _set("sx-improve", t || (S.improvement != null ? S.improvement.toFixed(3) + "\u00d7" : "\u2014"));
  _set("sx-mask",    t || ((S.mask && S.mask.length) ? (S.mask.length + " \u00d7 " + S.mask.length) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("sx-label",   t || (S.label || "MODELED"));
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
  _floor = null; _treeGroup = null; _maskMesh = []; _barStatic = null; _barDyn = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.depth = S.branch = S.budget = null;
  S.staticNodes = S.dynamicNodes = null;
  S.staticEpl = S.dynamicEpl = S.improvement = null;
  S.nodes = S.mask = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
