// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/circuits.js — ATTRIBUTION-GRAPH / CIRCUIT-TRACING organ for the holographic
// frontier ring. Renders the pruned attribution graph as a 3D layered node cloud: an
// input embedding node at the base, feature nodes stacked by layer, a transcoder-error
// node, and the output logit node at the top. Edges are the direct linear effects
// between nodes (brighter = stronger). The retained (backward-traced, threshold-pruned)
// sub-graph is what drives the modeled output. A HUD shows attribution_completeness and
// the top causal features (MODELED ablation delta_logit) from the live snapshot at the
// a11oy-native endpoint /api/a11oy/v1/circuits/attribution. Honesty label "MODELED" is
// read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors kvcache.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from the live endpoint):
//   layers, features_per_layer, prune_threshold_tau, n_nodes_kept, n_edges_kept,
//   attribution_completeness, output_logit, transcoder_error_share,
//   nodes[] {id, kind, activation}, edges[] {src, dst, effect}, top_causal[] {node, delta_logit}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   Circuit Tracing — attribution graphs (cross-layer transcoders + backward tracing):
//     Ameisen, Lindsey, Pearce, Gurnee et al. 2025, Transformer Circuits Thread
//     https://transformer-circuits.pub/2025/attribution-graphs/methods.html
//   Sparse Feature Circuits (greedy attribution -> sparse causal graphs):
//     Marks, Rager, Michaud, Belinkov, Bau, Mueller 2024, arXiv:2406.02395
//     https://arxiv.org/abs/2406.02395
//
// HONESTY LABELS: MODELED (deterministic simulation of the circuit-tracing METHOD on a
//   seeded replacement model; a HYPOTHESIS object, NOT a real attribution graph of a
//   real model; NO live weights / GPU). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (feature nodes / edges), proof-teal 0x3af4c8 (output
//   logit + top-causal accent), amber 0xd9b46a (embedding / input node), grey 0x5a6570
//   (transcoder-error node), 0x1b3a44 (floor/links). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "circuits";
const TITLE = "Attribution Graph · Circuit Tracing (MODELED)";

// a11oy-NATIVE self-hosted endpoint (same-origin, szl_circuit_graphs.py).
const EP = "/api/a11oy/v1/circuits/attribution?seed=42&layers=5&features=6&tau=0.12";

// data-viz hues — purple BANNED
const C_FEATURE = 0x5b8dee;  // lattice-blue (feature node / edge)
const C_LOGIT   = 0x3af4c8;  // proof-teal (output logit / top-causal accent)
const C_EMB     = 0xd9b46a;  // amber (input embedding node)
const C_ERROR   = 0x5a6570;  // grey (transcoder-error node)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

const LAYER_GAP = 2.2;   // world-units of vertical spacing between layers
const NODE_GAP  = 1.6;   // horizontal spacing between nodes in a layer
const MAX_NODES = 80;    // perf cap on rendered node slots
const MAX_EDGES = 200;   // perf cap on rendered edges

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _floor = null;
let _nodeMesh = [];   // Array<THREE.Mesh> — one per rendered node slot
let _edgeLine = [];   // Array<THREE.Line> — one per rendered edge
let _nodePos = {};    // id -> THREE.Vector3 (for edge endpoints)

const S = {
  label:        null,
  layers:       null,
  features:     null,
  tau:          null,
  nNodesKept:   null,
  nEdgesKept:   null,
  completeness: null,
  outputLogit:  null,
  errorShare:   null,
  nodes:        null,
  edges:        null,
  topCausal:    null,
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onCircuits, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// =============================================================================
// live data handler — reads label VERBATIM, never upgrades
// =============================================================================
function _onCircuits(j) {
  S.label        = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.layers       = typeof j.layers === "number" ? j.layers : null;
  S.features     = typeof j.features_per_layer === "number" ? j.features_per_layer : null;
  S.tau          = typeof j.prune_threshold_tau === "number" ? j.prune_threshold_tau : null;
  S.nNodesKept   = typeof j.n_nodes_kept === "number" ? j.n_nodes_kept : null;
  S.nEdgesKept   = typeof j.n_edges_kept === "number" ? j.n_edges_kept : null;
  S.completeness = typeof j.attribution_completeness === "number" ? j.attribution_completeness : null;
  S.outputLogit  = typeof j.output_logit === "number" ? j.output_logit : null;
  S.errorShare   = typeof j.transcoder_error_share === "number" ? j.transcoder_error_share : null;
  S.nodes        = Array.isArray(j.nodes) ? j.nodes : null;
  S.edges        = Array.isArray(j.edges) ? j.edges : null;
  S.topCausal    = Array.isArray(j.top_causal) ? j.top_causal : null;

  _rebuildGraph();
  _paintOverlay();
}

// =============================================================================
// graph geometry — rebuilt on each live snapshot (bounded node/edge counts)
// =============================================================================
function _disposeGraph() {
  const THREE = _THREE;
  _nodeMesh.forEach((m) => { try { m.geometry.dispose(); m.material.dispose(); _group.remove(m); } catch (_) {} });
  _edgeLine.forEach((l) => { try { l.geometry.dispose(); l.material.dispose(); _group.remove(l); } catch (_) {} });
  _nodeMesh = []; _edgeLine = []; _nodePos = {};
}

function _layerOf(node) {
  if (node.kind === "embedding") return -1;                 // base
  if (node.kind === "output_logit") return 999;             // top
  if (node.kind === "transcoder_error") return 998;         // near top, offset
  // feature id "L<l>F<f>"
  const m = /^L(\d+)F(\d+)$/.exec(node.id || "");
  return m ? parseInt(m[1], 10) : 0;
}

function _rebuildGraph() {
  if (!_THREE || !_group) return;
  _disposeGraph();
  const live = S.state === "live";
  const nodes = live && S.nodes ? S.nodes.slice(0, MAX_NODES) : [];
  const edges = live && S.edges ? S.edges.slice(0, MAX_EDGES) : [];
  if (!nodes.length) { _paintOverlay(); return; }

  const THREE = _THREE;
  const nLayers = (typeof S.layers === "number" ? S.layers : 5);

  // group nodes by layer, lay each layer out horizontally centered
  const byLayer = {};
  nodes.forEach((n) => { const L = _layerOf(n); (byLayer[L] = byLayer[L] || []).push(n); });
  Object.keys(byLayer).forEach((L) => {
    const row = byLayer[L];
    const y = (L === "-1") ? 0.0
            : (L === "999") ? (nLayers + 1) * LAYER_GAP
            : (L === "998") ? (nLayers + 1) * LAYER_GAP
            : (parseInt(L, 10) + 1) * LAYER_GAP;
    const xOffsetErr = (L === "998") ? NODE_GAP * 1.5 : 0.0;
    const width = (row.length - 1) * NODE_GAP;
    row.forEach((n, i) => {
      const x = (i * NODE_GAP - width / 2) + xOffsetErr;
      const pos = new THREE.Vector3(x, y, 0);
      _nodePos[n.id] = pos;

      let color = C_FEATURE, r = 0.22;
      if (n.kind === "embedding") { color = C_EMB; r = 0.30; }
      else if (n.kind === "output_logit") { color = C_LOGIT; r = 0.34; }
      else if (n.kind === "transcoder_error") { color = C_ERROR; r = 0.18; }
      const act = typeof n.activation === "number" ? n.activation : 0.0;
      const mesh = new THREE.Mesh(
        new THREE.IcosahedronGeometry(r + Math.min(0.18, act * 0.05), 1),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.45, transparent: true, opacity: 0.92 }),
      );
      mesh.position.copy(pos);
      _group.add(mesh);
      _nodeMesh.push(mesh);
    });
  });

  // edges: line from src node to dst node, brighter for larger |effect|
  let maxEff = 0.0001;
  edges.forEach((e) => { maxEff = Math.max(maxEff, Math.abs(e.effect || 0)); });
  edges.forEach((e) => {
    const a = _nodePos[e.src], b = _nodePos[e.dst];
    if (!a || !b) return;
    const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
    const strength = Math.min(1.0, Math.abs(e.effect || 0) / maxEff);
    const mat = new THREE.LineBasicMaterial({ color: C_FEATURE, transparent: true, opacity: 0.15 + 0.6 * strength });
    const line = new THREE.Line(geo, mat);
    _group.add(line);
    _edgeLine.push(line);
  });
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.18;
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MODELED", text: "attribution graph", name: "cir" }],
    legend: ["MODELED"],
    description:
      'Mechanistic interpretability first resolves a residual stream into sparse ' +
      '<b>features</b>, then wires those features into a <b>circuit</b> \u2014 an ' +
      '<b>attribution graph</b> whose nodes are features (plus the input embedding, a ' +
      'transcoder-error node, and the output logit) and whose edges are the direct ' +
      'linear effect of one node on another. A backward, threshold-pruned trace from ' +
      'the logit recovers the sub-graph that drives the prediction; a MODELED causal ' +
      'ablation reports each node\u2019s delta_logit. Honesty label <b>MODELED</b> ' +
      '(deterministic simulation of the method on a seeded replacement model; a ' +
      'HYPOTHESIS object, NOT a real attribution graph of a real model). 0 runtime CDN.',
    citations:
      "Circuit Tracing \u2014 Ameisen/Lindsey et al. 2025 (transformer-circuits.pub) \u00b7 " +
      "Sparse Feature Circuits \u2014 Marks et al. arXiv:2406.02395. MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["cir-layers"] = _show.addField("layers \u00d7 features/layer");
  _el["cir-tau"]    = _show.addField("prune threshold \u03c4");
  _el["cir-nodes"]  = _show.addField("nodes kept (pruned graph)");
  _el["cir-edges"]  = _show.addField("edges kept (pruned graph)");
  _el["cir-comp"]   = _show.addField("attribution_completeness \u2014 MODELED");
  _el["cir-logit"]  = _show.addField("output_logit");
  _el["cir-err"]    = _show.addField("transcoder_error_share");
  _el["cir-top"]    = _show.addField("top causal feature (\u0394 logit)");
  _el["cir-label"]  = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const comp = S.completeness != null ? (S.completeness * 100).toFixed(1) + "%" : "loading\u2026";
  const top  = (S.topCausal && S.topCausal[0]) ? S.topCausal[0].node : "loading\u2026";
  return (
    "<b>What this means:</b> When a model answers, information flows through a chain of " +
    "internal \u201cfeatures\u201d (interpretable concepts) before it lands on an answer. " +
    "This view traces that chain BACKWARD from the answer, keeping only the features that " +
    "actually mattered \u2014 an <b>attribution graph</b>. The kept graph explains about " +
    "<b>" + comp + "</b> of what pushed the answer, and the single most influential feature " +
    "here is <b>" + top + "</b> (measured by how much the answer moves when we switch that " +
    "feature off). This is a <b>MODELED</b> deterministic simulation of the circuit-tracing " +
    "method on a seeded stand-in model \u2014 a hypothesis about how a model COULD compute, " +
    "not a measurement of any real deployed model.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "\u2014"; }
function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("cir-layers", t || ((S.layers != null && S.features != null) ? (S.layers + " \u00d7 " + S.features) : "\u2014"));
  _set("cir-tau",    t || fx(S.tau, 3));
  _set("cir-nodes",  t || (S.nNodesKept != null ? String(S.nNodesKept) : "\u2014"));
  _set("cir-edges",  t || (S.nEdgesKept != null ? String(S.nEdgesKept) : "\u2014"));
  _set("cir-comp",   t || pct(S.completeness, 1));
  _set("cir-logit",  t || fx(S.outputLogit, 4));
  _set("cir-err",    t || pct(S.errorShare, 1));
  _set("cir-top",    t || ((S.topCausal && S.topCausal[0]) ? (S.topCausal[0].node + " (" + fx(S.topCausal[0].delta_logit, 4) + ")") : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("cir-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("cir", S.label || "MODELED", { text: "attribution graph" }); _show.refreshPlain(); }
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
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
  _group = _show = null;
  _floor = null; _nodeMesh = []; _edgeLine = []; _nodePos = {};
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.layers = S.features = S.tau = null;
  S.nNodesKept = S.nEdgesKept = S.completeness = S.outputLogit = S.errorShare = null;
  S.nodes = S.edges = S.topCausal = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
