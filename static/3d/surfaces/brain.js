// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brain.js — LIVING NEURAL-BRAIN (SZL ORIGINAL). Renders the estate's
// OWN harvested knowledge graph (GET /api/a11oy/v1/brain/graph) as a
// neural-network-shaped brain: the SZL answer to the leaked Obsidian
// "self-writing neural-vault", but real, owned, and honest.
//
// FEED-FORWARD LAYERS (the `layer` field on every node):
//   field (-1)  harvested field leaders (outer world; papers/repos/people/orgs)
//   input (0)   repos + surfaces (the estate's own inputs)
//   hidden (1)  topic clusters
//   hidden (2)  formulas — the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} highlighted
//   output (3)  estate root + live endpoints (the thesis)
// Links fire along edges; node size scales with connectivity (degree).
//
// PERFORMANCE (the graph is ~9.4k nodes / ~14k edges — never render it all):
//   * ?summary=1 first → instant honest count pills + the axis-expand list.
//   * full graph fetched once (progressive) → we render a PERFORMANT SUBSET:
//     the estate core (layers 0..3) + the top-connected field leaders, with a
//     per-axis expand control. Long-tail field leaders draw via ONE InstancedMesh
//     (LOD); the estate core + top leaders draw as individual meshes so the shared
//     showcase labels (top-N + hover/tap) can target them. Hard cap on rendered
//     nodes keeps it smooth on mobile.
//
// HONESTY (Doctrine v11 — read VERBATIM, never upgraded):
//   * BOTH counts shown: distinct_artifacts (the honest headline) AND the raw
//     node_count, with the endpoint's note that ~56% of nodes are arXiv
//     co-author `person` nodes — NEVER present the raw total as distinct work.
//   * locked-proven = EXACTLY 8; harvest adds nothing to it.
//   * Λ = Conjecture 1 → GREY node, NEVER green/proven.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//   * inspiration (leaked neural-vault) is cited as prior art, never claimed.
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brain";
const TITLE = "Brain — live knowledge graph";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_SUMMARY = "/api/a11oy/v1/brain/graph?summary=1";
const EP_GRAPH   = "/api/a11oy/v1/brain/graph";

// palette (doctrine v11) — NO purple
const C_FIELD   = 0x3a5a8c;  // lattice-blue (dim) — harvested field leaders
const C_INPUT   = 0x5b8dee;  // lattice-blue — repos + surfaces (input)
const C_TOPIC   = 0x8a6bff;  // violet-blue — topic clusters
const C_FORMULA = 0x8a6bff;  // violet-blue — formulas
const C_LOCKED  = 0x3af4c8;  // proof-teal — locked-proven core
const C_ESTATE  = 0x3af4c8;  // proof-teal — estate root (output)
const C_ENDPT   = 0x5b8dee;  // lattice-blue — live endpoints
const C_CONJ    = 0x5a6570;  // GREY — conjectures (Λ) — never green
const C_EDGE    = 0x1b3a44;  // dim link
const C_FIRE    = 0x3af4c8;  // firing pulse (proof-teal)

// feed-forward x-position per layer (field outer-left → estate output-right)
const LAYER_X = { "-1": -14, "0": -6.5, "1": -1.0, "2": 4.5, "3": 10.5 };
// disc radius per layer (field ring is broad; the estate core is compact)
const LAYER_R = { "-1": 8.5, "0": 4.2, "1": 2.0, "2": 3.2, "3": 1.6 };

// render budget (LOD): keep the estate core + this many top-connected leaders
const FIELD_TOP  = 480;   // default top-connected field leaders
const MAX_NODES  = 1650;  // hard cap on rendered nodes (mobile-safe)
const LABEL_MESH_MAX = 220; // nodes drawn as individual meshes (labelable)
const MAX_EDGES  = 6500;  // rendered edge cap
const FIRE_MAX   = 220;   // simultaneous firing pulses

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _polls = [], _frameReg = false, _t0 = 0;

// scene objects
let _sphereGeo = null;                 // shared unit sphere for individual meshes
let _labelMeshes = [];                 // individual Mesh nodes (labelable/hover)
let _inst = null, _instGeo = null, _instMat = null; // InstancedMesh long tail
let _edges = null, _edgeGeo = null, _edgeMat = null; // LineSegments
let _fire = null, _fireGeo = null, _fireMat = null;  // firing pulse Points
let _fireEdges = [];                   // [{a:Vec3, b:Vec3, off}] sampled edges
let _pos = {};                         // id -> Vector3 (rendered nodes)

// axis expand control
let _activeAxes = new Set();           // axes fully included beyond top-N
let _axisBtns = {};                    // axis -> button el

const S = {
  label: null, state: "init", loaded: false,
  // honest counts (from ?summary=1 / full)
  nodeCount: null, linkCount: null, distinct: null, persons: null,
  artifactNote: null, lockedFlagged: null,
  byLayer: null, byKind: null, byAxis: null,
  // full graph (client cache)
  nodes: null, links: null, byId: null,
  // render stats
  renderedNodes: 0, renderedEdges: 0, fieldShown: 0,
};

// -------------------------------------------------------------------------- //
// deterministic layout: golden-angle disc in the Y-Z plane per layer, laid
// out along X feed-forward. Stable (hash-seeded), no RNG needed on the client.
// -------------------------------------------------------------------------- //
function _hash(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h;
}

function _layout(rendered) {
  _pos = {};
  const byLayer = {};
  rendered.forEach((n) => { const L = String(n.layer); (byLayer[L] = byLayer[L] || []).push(n); });
  Object.keys(byLayer).forEach((L) => {
    const arr = byLayer[L];
    const x = LAYER_X[L] != null ? LAYER_X[L] : 0;
    const R = LAYER_R[L] != null ? LAYER_R[L] : 4;
    const N = arr.length;
    arr.forEach((n, i) => {
      const r = R * Math.sqrt((i + 0.5) / N);
      const theta = i * 2.399963229728653; // golden angle
      const jx = ((_hash(n.id) % 200) / 200 - 0.5) * 1.6; // depth jitter along x
      _pos[n.id] = new _THREE.Vector3(x + jx, r * Math.cos(theta), r * Math.sin(theta));
    });
  });
}

// node visual: colour + radius by kind/layer/degree. Conjectures stay grey.
function _isConj(n) {
  return (n.conjecture != null) || n.formula_id === "F23";
}
function _nodeColor(n) {
  if (_isConj(n)) return C_CONJ;
  if (n.kind === "formula") return n.locked ? C_LOCKED : C_FORMULA;
  if (n.kind === "estate") return C_ESTATE;
  if (n.kind === "endpoint") return C_ENDPT;
  if (n.kind === "topic") return C_TOPIC;
  if (n.layer === 0) return C_INPUT;
  return C_FIELD;
}
function _nodeRadius(n) {
  const deg = n.degree || 0;
  let r = 0.14 + 0.055 * Math.sqrt(deg);
  if (n.locked) r = Math.max(r, 0.42);
  if (n.kind === "estate") r = Math.max(r, 0.55);
  return Math.min(r, 0.9);
}

// -------------------------------------------------------------------------- //
// mount
// -------------------------------------------------------------------------- //
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  _sphereGeo = new _THREE.SphereGeometry(1, 10, 8);

  _buildOverlay(ctx);
  _badge = ctx.live.createBadge();
  if (_show) _show.setBadge(_badge);

  // Phase 1: tiny summary → honest count pills + axis list (polls, keeps badge live).
  _polls.push(ctx.live.poll(EP_SUMMARY, 20000, _onSummary, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));
  // Phase 2: full graph fetched ONCE (progressive) → render a performant subset.
  _fetchFullGraph();

  // top-N + hover/tap labels bound to the labelable individual meshes only.
  if (_show) {
    _show.attachSceneLabels({
      objects: () => _labelMeshes,
      text: (o) => (o.userData && o.userData.node && (o.userData.node.title || o.userData.node.id)) || "",
      weight: (o) => (o.userData && o.userData.node && o.userData.node.degree) || 0,
      topN: 12, hover: true, fadeNear: 10, fadeFar: 70,
    });
  }

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j) {
  const lbl = (j && j.label != null) ? j.label : "MODELED";
  return String(lbl).toUpperCase();
}

function _onSummary(j) {
  if (!j) { S.state = "error"; _paintOverlay(); return; }
  S.label = _readLabel(j);
  const sm = j.summary || {};
  S.nodeCount = j.node_count != null ? j.node_count : sm.node_count;
  S.linkCount = j.link_count != null ? j.link_count : sm.link_count;
  S.distinct  = j.distinct_artifacts != null ? j.distinct_artifacts : sm.distinct_artifacts;
  S.persons   = j.person_node_count != null ? j.person_node_count : sm.person_node_count;
  S.artifactNote = j.artifact_note || null;
  S.lockedFlagged = sm.locked_flagged != null ? sm.locked_flagged : S.lockedFlagged;
  S.byLayer = sm.by_layer || S.byLayer;
  S.byKind  = sm.by_kind || S.byKind;
  S.byAxis  = sm.by_axis || S.byAxis;
  _buildAxisControls();
  _paintOverlay();
}

function _fetchFullGraph() {
  fetch(EP_GRAPH, { headers: { accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      const nodes = Array.isArray(j.nodes) ? j.nodes : [];
      const links = Array.isArray(j.links) ? j.links : [];
      if (!nodes.length) return;
      S.nodes = nodes; S.links = links;
      S.byId = {};
      nodes.forEach((n) => { S.byId[n.id] = n; });
      S.label = _readLabel(j);
      // full payload carries the honest counts too — prefer them
      if (j.node_count != null) S.nodeCount = j.node_count;
      if (j.link_count != null) S.linkCount = j.link_count;
      if (j.distinct_artifacts != null) S.distinct = j.distinct_artifacts;
      if (j.person_node_count != null) S.persons = j.person_node_count;
      if (j.artifact_note) S.artifactNote = j.artifact_note;
      if (j.summary) {
        S.byAxis = j.summary.by_axis || S.byAxis;
        S.byKind = j.summary.by_kind || S.byKind;
        S.byLayer = j.summary.by_layer || S.byLayer;
        if (j.summary.locked_flagged != null) S.lockedFlagged = j.summary.locked_flagged;
      }
      S.loaded = true;
      _buildAxisControls();
      _rebuild();
      _paintOverlay();
    })
    .catch(() => { S.state = "error"; _paintOverlay(); });
}

// -------------------------------------------------------------------------- //
// subset selection + build
// -------------------------------------------------------------------------- //
function _selectRendered() {
  const nodes = S.nodes || [];
  const core = [];   // layers 0..3 — always rendered
  const field = [];  // layer -1
  nodes.forEach((n) => { (n.layer === -1 ? field : core).push(n); });
  field.sort((a, b) => (b.degree || 0) - (a.degree || 0));

  const chosen = new Map();
  core.forEach((n) => chosen.set(n.id, n));

  // top-connected field leaders (LOD default set)
  for (let i = 0; i < field.length && chosen.size < MAX_NODES && i < FIELD_TOP; i++) {
    chosen.set(field[i].id, field[i]);
  }
  // axis-expand: fully include leaders on any active axis (up to the cap)
  if (_activeAxes.size) {
    for (let i = 0; i < field.length && chosen.size < MAX_NODES; i++) {
      const n = field[i];
      if (n.axis && _activeAxes.has(n.axis)) chosen.set(n.id, n);
    }
  }
  const rendered = Array.from(chosen.values());
  S.fieldShown = rendered.filter((n) => n.layer === -1).length;
  return rendered;
}

function _rebuild() {
  if (!_group || !S.nodes) return;
  _clearScene();
  const rendered = _selectRendered();
  S.renderedNodes = rendered.length;
  _layout(rendered);

  // pick which nodes get an individual (labelable) mesh: highest-degree first,
  // but always keep the estate core (layers 1..3) individual so the thesis is
  // hoverable. The long tail draws via one InstancedMesh.
  const ranked = rendered.slice().sort((a, b) => {
    const pa = a.layer >= 1 ? 1e9 : 0, pb = b.layer >= 1 ? 1e9 : 0;
    return (pb + (b.degree || 0)) - (pa + (a.degree || 0));
  });
  const individualSet = new Set(ranked.slice(0, Math.min(LABEL_MESH_MAX, ranked.length)).map((n) => n.id));

  const tail = [];
  rendered.forEach((n) => {
    if (individualSet.has(n.id)) _addLabelMesh(n);
    else tail.push(n);
  });
  _buildInstanced(tail);
  _buildEdges(rendered);
  _buildFire();
}

function _addLabelMesh(n) {
  const mat = new _THREE.MeshStandardMaterial({
    color: _nodeColor(n),
    emissive: _isConj(n) ? 0x000000 : _nodeColor(n),
    emissiveIntensity: _isConj(n) ? 0.0 : 0.32,
    metalness: 0.1, roughness: _isConj(n) ? 0.95 : 0.5,
    transparent: true, opacity: _isConj(n) ? 0.6 : 0.96,
  });
  const mesh = new _THREE.Mesh(_sphereGeo, mat);
  const r = _nodeRadius(n);
  mesh.scale.setScalar(r);
  mesh.position.copy(_pos[n.id]);
  mesh.userData = { node: n, baseEmissive: mat.emissiveIntensity, isConj: _isConj(n) };
  _labelMeshes.push(mesh);
  _group.add(mesh);
}

function _buildInstanced(tail) {
  if (!tail.length) return;
  _instGeo = new _THREE.SphereGeometry(1, 8, 6);
  _instMat = new _THREE.MeshStandardMaterial({
    metalness: 0.1, roughness: 0.6, transparent: true, opacity: 0.9,
    emissiveIntensity: 0.28, vertexColors: false,
  });
  _inst = new _THREE.InstancedMesh(_instGeo, _instMat, tail.length);
  _inst.instanceColor = new _THREE.InstancedBufferAttribute(new Float32Array(tail.length * 3), 3);
  const m = new _THREE.Matrix4();
  const q = new _THREE.Quaternion();
  const s = new _THREE.Vector3();
  const c = new _THREE.Color();
  tail.forEach((n, i) => {
    const r = _nodeRadius(n);
    s.set(r, r, r);
    m.compose(_pos[n.id], q, s);
    _inst.setMatrixAt(i, m);
    c.setHex(_nodeColor(n));
    _inst.setColorAt(i, c);
  });
  _inst.instanceMatrix.needsUpdate = true;
  if (_inst.instanceColor) _inst.instanceColor.needsUpdate = true;
  // give the instanced material a base emissive so the tail is visible under bloom
  _instMat.emissive = new _THREE.Color(C_FIELD);
  _group.add(_inst);
}

function _buildEdges(rendered) {
  const ids = new Set(rendered.map((n) => n.id));
  const links = S.links || [];
  const pts = [];
  const sample = [];
  for (let i = 0; i < links.length && pts.length / 2 < MAX_EDGES; i++) {
    const l = links[i];
    const a = _pos[l.source], b = _pos[l.target];
    if (!a || !b || !ids.has(l.source) || !ids.has(l.target)) continue;
    pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
    if (sample.length < FIRE_MAX && (i % 3 === 0)) sample.push({ a, b, off: Math.random() });
  }
  S.renderedEdges = pts.length / 2;
  if (!pts.length) return;
  _edgeGeo = new _THREE.BufferGeometry();
  _edgeGeo.setAttribute("position", new _THREE.Float32BufferAttribute(pts, 3));
  _edgeMat = new _THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.22 });
  _edges = new _THREE.LineSegments(_edgeGeo, _edgeMat);
  _group.add(_edges);
  _fireEdges = sample;
}

function _buildFire() {
  if (!_fireEdges.length) return;
  _fireGeo = new _THREE.BufferGeometry();
  _fireGeo.setAttribute("position", new _THREE.Float32BufferAttribute(new Float32Array(_fireEdges.length * 3), 3));
  _fireMat = new _THREE.PointsMaterial({
    color: C_FIRE, size: 0.32, transparent: true, opacity: 0.95,
    blending: _THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
  });
  _fire = new _THREE.Points(_fireGeo, _fireMat);
  _group.add(_fire);
}

function _clearScene() {
  _labelMeshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _labelMeshes = [];
  if (_inst) { _group.remove(_inst); _inst.dispose && _inst.dispose(); }
  if (_instGeo) _instGeo.dispose();
  if (_instMat) _instMat.dispose();
  _inst = _instGeo = _instMat = null;
  if (_edges) { _group.remove(_edges); }
  if (_edgeGeo) _edgeGeo.dispose();
  if (_edgeMat) _edgeMat.dispose();
  _edges = _edgeGeo = _edgeMat = null;
  if (_fire) { _group.remove(_fire); }
  if (_fireGeo) _fireGeo.dispose();
  if (_fireMat) _fireMat.dispose();
  _fire = _fireGeo = _fireMat = null;
  _fireEdges = [];
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + firing pulses travelling source→target
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = Math.sin(t * 0.08) * 0.5 + t * 0.03;

  // firing pulses: each sampled edge carries a point that travels src→dst on loop
  if (_fire && _fireGeo && _fireEdges.length) {
    const arr = _fireGeo.attributes.position.array;
    for (let i = 0; i < _fireEdges.length; i++) {
      const e = _fireEdges[i];
      let f = (t * 0.5 + e.off) % 1;
      const j = i * 3;
      arr[j]     = e.a.x + (e.b.x - e.a.x) * f;
      arr[j + 1] = e.a.y + (e.b.y - e.a.y) * f;
      arr[j + 2] = e.a.z + (e.b.z - e.a.z) * f;
    }
    _fireGeo.attributes.position.needsUpdate = true;
  }

  // subtle "breathing" on the locked-8 / estate individual meshes so the proven
  // core reads as alive (conjecture meshes stay flat grey — never brighten).
  const pulse = 0.32 + 0.18 * (0.5 + 0.5 * Math.sin(t * 1.6));
  _labelMeshes.forEach((m) => {
    if (!m.material || m.userData.isConj) return;
    const n = m.userData.node;
    if (n && (n.locked || n.kind === "estate")) m.material.emissiveIntensity = pulse;
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper)
// -------------------------------------------------------------------------- //
function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    chips: [{ label: "MODELED", text: "knowledge graph", name: "src" }],
    legend: ["MEASURED", "MODELED", "SAMPLE"],
    description:
      "<b>The estate's own brain.</b> Every node is a REAL harvested artifact — a repo, " +
      "surface, formula, topic, or a field leader (paper / lab / org / person) — laid out " +
      "feed-forward: harvested field leaders (outer) &rarr; repos &amp; surfaces (input) &rarr; " +
      "topics &rarr; formulas (the <b>locked-8</b> proven core in proof-teal) &rarr; the estate " +
      "thesis (output). Pulses fire along real edges; node size grows with connectivity. " +
      "This is the SZL answer to the leaked Obsidian neural-vault — but real, owned, and honest.",
    citations:
      "Graph is LIVE from /api/a11oy/v1/brain/graph (pure read — no signing on GET). " +
      "Inspiration: the viral “self-writing Obsidian neural-vault”, cited as prior art, " +
      "never claimed as ours. Λ = Conjecture 1 (grey, never proven green).",
    plain: { html: _plainHtml },
  });

  // HONEST count pills (always visible in the pill row): BOTH the distinct
  // headline AND the raw total, with the ~56% co-author note in the tooltip.
  _pillDistinct = _mkPill("— distinct", "Distinct real artifacts (repos+papers+orgs+datasets+…) — the honest headline.");
  _pillNodes    = _mkPill("— nodes", "Raw node total. Includes arXiv co-author person nodes (~56%); NOT all distinct work.");
  _show.pills.appendChild(_pillDistinct);
  _show.pills.appendChild(_pillNodes);

  // KPI rows (collapsible body)
  _el.distinct = _show.addField("Distinct artifacts");
  _el.nodes    = _show.addField("Total nodes");
  _el.persons  = _show.addField("Co-author nodes");
  _el.links    = _show.addField("Edges");
  _el.locked   = _show.addField("Locked-proven");
  _el.rendered = _show.addField("Rendered (subset)");
  _el.field    = _show.addField("Field leaders shown");

  // axis-expand control container (populated once summary/full arrives)
  _axisWrap = document.createElement("div");
  _axisWrap.style.cssText = "display:flex;flex-direction:column;gap:6px;margin-top:2px";
  const cap = document.createElement("div");
  cap.textContent = "Expand an axis (adds its field leaders):";
  cap.style.cssText = "font-size:10.5px;color:#9fb1bf";
  _axisRow = document.createElement("div");
  _axisRow.style.cssText = "display:flex;flex-wrap:wrap;gap:5px";
  _axisWrap.appendChild(cap); _axisWrap.appendChild(_axisRow);
  _show.appendBody(_axisWrap);

  // honest artifact note (verbatim from the endpoint)
  _noteEl = document.createElement("div");
  _noteEl.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_noteEl);
}

let _pillDistinct = null, _pillNodes = null, _axisWrap = null, _axisRow = null, _noteEl = null;
const _el = {};

function _mkPill(text, title) {
  const el = document.createElement("span");
  el.title = title || "";
  el.textContent = text;
  el.style.cssText =
    "font:600 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;padding:3px 9px;border-radius:999px;" +
    "border:1px solid #1c2836;background:#0a1117;color:#cfe3ea;letter-spacing:.2px;white-space:nowrap";
  return el;
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _buildAxisControls() {
  if (!_axisRow || !S.byAxis) return;
  const top = Object.keys(S.byAxis).slice(0, 8);
  // only (re)build if the set of buttons changed
  const have = Object.keys(_axisBtns).sort().join(",");
  const want = top.slice().sort().join(",");
  if (have === want) return;
  _axisRow.textContent = "";
  _axisBtns = {};
  top.forEach((ax) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = ax + " (" + S.byAxis[ax] + ")";
    b.dataset.axis = ax;
    _styleAxisBtn(b, _activeAxes.has(ax));
    b.addEventListener("click", () => {
      if (_activeAxes.has(ax)) _activeAxes.delete(ax); else _activeAxes.add(ax);
      _styleAxisBtn(b, _activeAxes.has(ax));
      if (S.loaded) { _rebuild(); _paintOverlay(); }
    });
    _axisBtns[ax] = b;
    _axisRow.appendChild(b);
  });
}

function _styleAxisBtn(b, on) {
  b.style.cssText =
    "font:11px ui-monospace,Menlo,monospace;padding:3px 8px;border-radius:7px;cursor:pointer;" +
    (on
      ? "border:1px solid #3af4c8;background:#08201a;color:#3af4c8;"
      : "border:1px solid #1c2836;background:#0e1722;color:#9fb6cc;");
}

function _paintOverlay() {
  if (!_show) return;
  const deg = (S.state === "error");
  _show.setChip("src", S.label || "MODELED", { text: "knowledge graph" });

  if (_pillDistinct) _pillDistinct.textContent = _fmt(S.distinct) + " distinct";
  if (_pillNodes) _pillNodes.textContent = _fmt(S.nodeCount) + " nodes";

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  set("distinct", deg ? "—" : _fmt(S.distinct));
  set("nodes", deg ? "—" : _fmt(S.nodeCount));
  set("persons", deg ? "—" : (S.persons != null ? _fmt(S.persons) + " (~56%, not distinct work)" : "—"));
  set("links", deg ? "—" : _fmt(S.linkCount));
  set("locked", deg ? "—" : (S.lockedFlagged != null ? S.lockedFlagged + " (exactly 8)" : "8 (exactly 8)"));
  set("rendered", S.loaded ? _fmt(S.renderedNodes) + " nodes · " + _fmt(S.renderedEdges) + " edges" : "loading…");
  const fieldTotal = S.byLayer && S.byLayer["-1"] != null ? S.byLayer["-1"] : null;
  set("field", S.loaded ? _fmt(S.fieldShown) + (fieldTotal != null ? " of " + _fmt(fieldTotal) : "") : "loading…");

  if (_noteEl) _noteEl.textContent = S.artifactNote || "";
  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "Each ball is one real thing our estate knows about — a code repo, a live surface, one of " +
    "our math formulas, a topic, or a leader out in the field (a paper, lab, company, or author). " +
    "They're arranged like a neural network reading left-to-right: the outside world flows in " +
    "through our inputs, through topics and formulas, to the estate's thesis on the right. The " +
    "bright teal balls are the <b>8 formulas we've actually machine-proven</b>; grey balls (like " +
    "Λ) are things we <b>have not</b> proven and never light up green. Two counts are shown on " +
    "purpose: <b>" + _fmt(S.distinct) + " distinct artifacts</b> is the honest headline, while the raw " +
    "<b>" + _fmt(S.nodeCount) + " nodes</b> includes ~56% arXiv co-author names — real, but not distinct " +
    "work. We render a fast subset (the estate core + the best-connected leaders); tap an axis to " +
    "pull in more. Label <b>" + (S.label || "MODELED") + "</b> — a faithful drawing of our real graph."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearScene(); } catch (_) {}
  try { if (_sphereGeo) _sphereGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _sphereGeo = null;
  _group = _show = _badge = null;
  _pillDistinct = _pillNodes = _axisWrap = _axisRow = _noteEl = null;
  _axisBtns = {}; _activeAxes = new Set();
  Object.keys(_el).forEach((k) => delete _el[k]);
  _pos = {}; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = null; S.state = "init"; S.loaded = false;
  S.nodeCount = S.linkCount = S.distinct = S.persons = null;
  S.artifactNote = null; S.lockedFlagged = null;
  S.byLayer = S.byKind = S.byAxis = null;
  S.nodes = S.links = S.byId = null;
  S.renderedNodes = S.renderedEdges = S.fieldShown = 0;
}

export default { id: ID, title: TITLE, endpoints: [EP_SUMMARY, EP_GRAPH], mount, unmount };
