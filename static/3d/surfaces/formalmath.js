// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/formalmath.js — FORMAL-MATH RETRIEVAL-AUGMENTED TACTIC SELECTION organ
// for the holographic frontier ring (LeanDojo/ReProver-style premise retrieval +
// best-first proof search). Renders the synthetic tactic tree explored by the live
// snapshot from /api/killinchu/v1/formalmath/retrieve as a branching lattice-blue
// wireframe: nodes sized/colored proof-teal by retrieval similarity (the branch's
// premise_bias score), grey dashed edges mark unexplored/pruned branches beyond the
// live search_trace. A HUD shows the top retrieved premise + the tree depth reached.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is; it is
// never upgraded.
//
// Surface export shape (mirrors testtime.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   goal, corpus_size, k, top_k_premises[], similarity_scores{},
//   simulated_proof_tree_depth, nodes_expanded, search_trace[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   LeanDojo (premise-annotated Lean data/benchmark toolkit):
//     Yang et al. 2023, NeurIPS (Datasets and Benchmarks Track)
//     https://github.com/lean-dojo/LeanDojo
//   ReProver (Retrieval-Augmented Prover; ByT5 premise retriever + tactic generator):
//     lean-dojo/ReProver
//     https://github.com/lean-dojo/ReProver
//   DeepSeek-Prover-V2 (subgoal decomposition + recursive proof search for Lean 4):
//     DeepSeek-AI et al. 2025, arXiv:2504.21801
//     https://arxiv.org/abs/2504.21801
//
// HONESTY LABELS: MODELED (deterministic bag-of-tokens cosine retrieval + best-first
//   search simulation; NOT connected to Lean 4 or Mathlib; NEVER-CLAIMED-AS
//   DeepSeek-Prover or ReProver output). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (tactic-tree wireframe / explored edges), proof-teal
//   0x3af4c8 (nodes sized/colored by retrieval similarity / HUD accent), greys
//   (unexplored/pruned branches, degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "formalmath";
const TITLE = "Formal-Math Retrieval-Augmented Tactic Selection (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the formal-math organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/formalmath/retrieve?seed=42&goal=theorem%20add_comm_example%20(a%20b%20%3A%20Nat)%20%3A%20a%20%2B%20b%20%3D%20b%20%2B%20a&corpus_size=24&k=5";

// data-viz hues — purple BANNED
const C_TREE    = 0x5b8dee;  // lattice-blue (tactic-tree wireframe / explored edges)
const C_NODE    = 0x3af4c8;  // proof-teal (nodes, sized/colored by retrieval similarity)
const C_UNEXPL  = 0x5a6570;  // grey (unexplored / pruned branch, dashed)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// tactic-tree layout geometry
const DEPTH_LEN   = 2.4;   // world-units between depth levels along X
const LANE_GAP    = 1.1;   // world-units between sibling nodes (Y)
const MAX_DEPTH   = 6;     // matches server _MAX_DEPTH
const MAX_TRACE   = 64;    // matches server search_trace cap
const BRANCH      = 3;     // matches server _BRANCH_FACTOR (layout hint only)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor        = null;
let _spine        = null;                 // THREE.Line — root->depth axis
let _nodeMesh     = [];                   // Array<THREE.Mesh> — one per trace slot
let _edgeLines    = [];                   // Array<THREE.Line> — explored edges (lattice-blue)
let _unexplLines  = [];                   // Array<THREE.Line> — grey dashed unexplored-branch stubs
let _marker       = null;                 // THREE.Mesh — HUD "top premise" pulsing marker

// live state
const S = {
  label:        null,
  goal:         null,   // goal
  corpusSize:   null,   // corpus_size
  k:            null,   // k
  topPremises:  null,   // top_k_premises[]
  simScores:    null,   // similarity_scores{}
  treeDepth:    null,   // simulated_proof_tree_depth
  nodesExpand:  null,   // nodes_expanded
  trace:        null,   // search_trace[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(5, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(6, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLattice();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onFormalmath, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Pre-allocate a fixed pool of node meshes + edge/unexplored-branch lines sized to
// MAX_TRACE; we toggle visibility/position/color in-place as live data arrives
// (no per-poll geometry churn).
function _buildLattice() {
  const THREE = _THREE;

  // root->depth spine (visual reading guide only)
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(DEPTH_LEN * MAX_DEPTH, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_TREE, transparent: true, opacity: 0.35 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const nodeGeo = new THREE.IcosahedronGeometry(0.16, 0);
  for (let i = 0; i < MAX_TRACE; i++) {
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.35, wireframe: true, transparent: true, opacity: 0.0 }),
    );
    mesh.visible = false;
    _group.add(mesh);
    _nodeMesh.push(mesh);

    // explored-edge line (parent -> this node), lattice-blue wireframe-style
    const edgeGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0)]);
    const edgeMat = new THREE.LineBasicMaterial({ color: C_TREE, transparent: true, opacity: 0.0 });
    const edge = new THREE.Line(edgeGeo, edgeMat);
    edge.visible = false;
    _group.add(edge);
    _edgeLines.push(edge);

    // unexplored/pruned-branch stub: short grey dashed line hinting at a
    // branch beyond what the bounded search_trace sample shows
    const unGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0)]);
    const unMat = new THREE.LineDashedMaterial({ color: C_UNEXPL, transparent: true, opacity: 0.0, dashSize: 0.12, gapSize: 0.09 });
    const un = new THREE.Line(unGeo, unMat);
    un.computeLineDistances();
    un.visible = false;
    _group.add(un);
    _unexplLines.push(un);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.24, 0),
    new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, 1.4, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onFormalmath(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.goal        = typeof j.goal === "string" ? j.goal : null;
  S.corpusSize  = typeof j.corpus_size === "number" ? j.corpus_size : null;
  S.k           = typeof j.k === "number" ? j.k : null;
  S.topPremises = Array.isArray(j.top_k_premises) ? j.top_k_premises : null;
  S.simScores   = (j.similarity_scores && typeof j.similarity_scores === "object") ? j.similarity_scores : null;
  S.treeDepth   = typeof j.simulated_proof_tree_depth === "number" ? j.simulated_proof_tree_depth : null;
  S.nodesExpand = typeof j.nodes_expanded === "number" ? j.nodes_expanded : null;
  S.trace       = Array.isArray(j.search_trace) ? j.search_trace : null;

  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the branching lattice from live search_trace[]
// =============================================================================
// Layout: each trace entry gets a lane index within its depth level (stable
// hash of node_id keeps lanes reproducible across polls), positioned at
// x = depth * DEPTH_LEN, y = (lane - laneCount/2) * LANE_GAP.
function _laneFor(nodeId, depth, seenAtDepth) {
  const n = seenAtDepth.get(depth) || 0;
  seenAtDepth.set(depth, n + 1);
  return n;
}

function _updateLattice() {
  const THREE = _THREE;
  const live = S.state === "live";
  const trace = live && S.trace && S.trace.length ? S.trace.slice(0, MAX_TRACE) : [];

  // find max similarity among top_k_premises for node-size/color normalization
  let maxSim = 0.0;
  if (live && S.topPremises && S.topPremises.length) {
    maxSim = S.topPremises.reduce((m, p) => Math.max(m, p.similarity || 0), 0);
  }
  const simByName = {};
  if (live && S.topPremises) S.topPremises.forEach((p) => { simByName[p.name] = p.similarity; });

  const seenAtDepth = new Map();
  const posByNodeId = new Map();

  for (let i = 0; i < MAX_TRACE; i++) {
    const mesh = _nodeMesh[i];
    const edge = _edgeLines[i];
    const un   = _unexplLines[i];

    if (i >= trace.length || !live) {
      mesh.visible = false;
      edge.visible = false;
      un.visible = false;
      continue;
    }

    const row = trace[i];
    const depth = Math.min(MAX_DEPTH, row.depth || 0);
    const lane = _laneFor(row.node_id, depth, seenAtDepth);
    const laneCountEstimate = Math.max(1, Math.pow(BRANCH, depth));
    const x = depth * DEPTH_LEN;
    const y = (lane - laneCountEstimate / 2) * LANE_GAP * (1 / Math.max(1, Math.log2(laneCountEstimate + 1)));
    posByNodeId.set(row.node_id, { x, y, depth });

    // node size/color driven by this branch's premise_bias similarity
    const biasSim = row.premise_bias != null ? (simByName[row.premise_bias] || 0) : 0;
    const norm = maxSim > 0 ? Math.min(1, biasSim / maxSim) : 0;
    const scale = 0.7 + 1.6 * norm; // proof-teal nodes grow with retrieval similarity

    mesh.position.set(x, y, 0);
    mesh.scale.setScalar(scale);
    mesh.visible = true;
    mesh.material.opacity = 0.55 + 0.4 * norm;
    mesh.material.color.setHex(C_NODE);
    mesh.material.emissive.setHex(C_NODE);
    mesh.material.emissiveIntensity = 0.25 + 0.4 * norm;

    // explored edge: from root (depth 0 anchor) or a coarse parent-depth
    // anchor back to this node (bounded trace has no explicit parent id, so
    // we draw a lattice-blue edge from the previous depth-level's centroid X
    // for a clean branching-lattice read, per the wireframe brief).
    const parentX = Math.max(0, x - DEPTH_LEN);
    edge.geometry.setFromPoints([new THREE.Vector3(parentX, 0, 0), new THREE.Vector3(x, y, 0)]);
    edge.geometry.attributes.position.needsUpdate = true;
    edge.material.color.setHex(C_TREE);
    edge.material.opacity = 0.5;
    edge.visible = true;

    // unexplored-branch stub: a short grey dashed line fanning out beyond this
    // node, hinting at sibling branches beyond the bounded trace sample
    const stubX = x + DEPTH_LEN * 0.55;
    const stubY = y + LANE_GAP * 0.4;
    un.geometry.setFromPoints([new THREE.Vector3(x, y, 0), new THREE.Vector3(stubX, stubY, 0)]);
    un.geometry.attributes.position.needsUpdate = true;
    un.computeLineDistances();
    un.material.color.setHex(C_UNEXPL);
    un.material.opacity = depth < MAX_DEPTH ? 0.35 : 0.0;
    un.visible = depth < MAX_DEPTH;
  }

  _spine.material.color.setHex(live ? C_TREE : C_DIM);
  _spine.material.opacity = live ? 0.35 : 0.12;

  // HUD marker: sits above the deepest/most-similar node, pulses proof-teal
  if (_marker) {
    if (live && trace.length) {
      const best = trace.reduce((a, b) => ((b.priority || 0) > (a.priority || 0) ? b : a), trace[0]);
      const pos = posByNodeId.get(best.node_id) || { x: 0, y: 1.4 };
      _marker.position.set(pos.x, (pos.y || 0) + 0.8, 0);
      _marker.material.color.setHex(C_NODE);
      _marker.material.emissive.setHex(C_NODE);
      _marker.material.opacity = 0.85;
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;
  if (_marker) {
    _marker.rotation.y += 0.022;
    _marker.rotation.x += 0.011;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _marker.scale.setScalar(pulse);
  }
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
    maxWidth: "min(94%,440px)",
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
    'Retrieves the most relevant <b>premises</b> for a goal by <b>cosine similarity</b> over ' +
    'hand-rolled bag-of-tokens vectors (no embeddings), then runs a deterministic ' +
    '<b>best-first search</b> over a synthetic tactic tree, biased by the retrieved premises ' +
    '\u2014 the LeanDojo/ReProver premise-selection concept. Honesty label <b>MODELED</b> ' +
    '(NOT connected to Lean 4 or Mathlib). 0 runtime CDN.';
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
  nm.textContent = "formal-math retrieval + tactic search";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:58%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("fm-goal",    "goal"));
  grid.appendChild(kpiRow("fm-corpus",  "corpus_size"));
  grid.appendChild(kpiRow("fm-k",       "k (top-k retrieved)"));
  grid.appendChild(kpiRow("fm-top",     "top premise \u2014 MODELED"));
  grid.appendChild(kpiRow("fm-sim",     "top similarity"));
  grid.appendChild(kpiRow("fm-depth",   "proof-tree depth"));
  grid.appendChild(kpiRow("fm-nodes",   "nodes expanded"));
  grid.appendChild(kpiRow("fm-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "LeanDojo github.com/lean-dojo/LeanDojo \u00b7 ReProver github.com/lean-dojo/ReProver \u00b7 DeepSeek-Prover-V2 arXiv:2504.21801. MODELED \u00b7 not claimed-as.";
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
  pd.id = "fm-plain";
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
  const top    = (S.topPremises && S.topPremises[0]) ? S.topPremises[0].name : "loading\u2026";
  const simPct = (S.topPremises && S.topPremises[0]) ? (S.topPremises[0].similarity * 100).toFixed(1) + "%" : "loading\u2026";
  const depth  = S.treeDepth != null ? String(S.treeDepth) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Proving a math theorem in a system like Lean often needs the " +
    "<i>right supporting fact</i> (a \u201cpremise\u201d) from a huge library. Instead of " +
    "searching blindly, this organ scores every candidate premise by how many words it shares " +
    "with the goal (<b>" + top + "</b> scored highest here, at <b>" + simPct + "</b> similarity), " +
    "then explores a tree of possible next proof steps, trying the most promising branches " +
    "first \u2014 reaching a simulated depth of <b>" + depth + "</b> steps. Plain: find the most " +
    "relevant facts first, then search smart instead of exhaustively. This is a <b>MODELED</b> " +
    "toy simulation of the LeanDojo/ReProver idea \u2014 it is not connected to real Lean 4 or " +
    "Mathlib, and is not DeepSeek-Prover or ReProver output.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  const top = S.topPremises && S.topPremises[0] ? S.topPremises[0] : null;
  _set("fm-goal",   t || (S.goal ? (S.goal.length > 34 ? S.goal.slice(0, 34) + "\u2026" : S.goal) : "\u2014"));
  _set("fm-corpus", t || (S.corpusSize != null ? String(S.corpusSize) : "\u2014"));
  _set("fm-k",      t || (S.k != null ? String(S.k) : "\u2014"));
  _set("fm-top",    t || (top ? top.name : "\u2014"));
  _set("fm-sim",    t || (top ? pct(top.similarity, 2) : "\u2014"));
  _set("fm-depth",  t || (S.treeDepth != null ? String(S.treeDepth) : "\u2014"));
  _set("fm-nodes",  t || (S.nodesExpand != null ? String(S.nodesExpand) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("fm-label",  t || (S.label || "MODELED"));
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
  _floor = null; _spine = null; _nodeMesh = []; _edgeLines = []; _unexplLines = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.goal = S.corpusSize = S.k = S.topPremises = S.simScores = null;
  S.treeDepth = S.nodesExpand = S.trace = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
