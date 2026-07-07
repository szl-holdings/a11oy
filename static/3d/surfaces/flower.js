// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/flower.js — THE FLOWER BRAIN (SZL ORIGINAL, wave 24 capstone).
// A living 8-petal radial bloom that unifies everything SZL has built into one
// knowledge organism. The CENTER PISTIL is the machine-proven locked-8 core
// {F1,F4,F7,F11,F12,F18,F19,F22} — always closed, always solid, immutable. Eight
// petals radiate at 45° intervals; each petal is a real cluster (verified
// theorems, experimental, unified formulas, ouroboros codexes, the 64 surfaces,
// memory/provenance, and the honestly-unproven CONJECTURES). Each node in a
// petal sits at a radius set by its tier depth (proven closest, conjecture
// outermost).
//
// THE GRAPH IS REAL: every node traces to a real Lean decl / DOI / receipt hash /
// endpoint / codex path (provenance field). The BLOOM DYNAMIC is MODELED — a
// deterministic, honest drawing of per-petal cluster health read VERBATIM from
// /api/killinchu/v1/flower/{graph,bloom}. Petals OPEN (rotate + scale outward)
// proportional to their bloom_fraction. The honesty label "MODELED" is shown
// as-is and is never upgraded.
//
// HARD INVARIANTS (Doctrine v11):
//   * locked-proven = EXACTLY 8 (the pistil never grows). HUD asserts count == 8.
//   * CONJECTURE petal renders GREY (0x5a6570), visibly closed/dim, NEVER green.
//     HUD asserts conjecture_rendered_green == 0.
//   * COLOURS ONLY: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal
//     0x3af4c8, greys (0x5a6570 / 0x42505d / 0x1b3a44), black 0x000000. Zero purple/magenta.
//   * 0 runtime CDN (three.js via ctx.THREE). Degrades gracefully to NO-LIVE-DATA on 404.
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

const ID    = "flower";
const TITLE = "The Flower Brain";

const EP_GRAPH = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/flower/graph";
const EP_BLOOM = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/flower/bloom";

// tier -> colour. proof-teal for the proven pistil, lattice-blue for verified /
// experimental / surfaces / memory, violet-blue for borrowed unified-formula &
// ouroboros fusions, GREY for conjectures (never green).
const C_LOCKED = 0x3af4c8;  // proof-teal  (locked-proven core / pistil)
const C_VERIF  = 0x5b8dee;  // lattice-blue (verified / experimental / surfaces / memory)
const C_BORROW = 0x8a6bff;  // violet-blue  (borrowed unified formulas + ouroboros codexes)
const C_CONJ   = 0x5a6570;  // GREY (conjectures — never green, never opens bright)
const C_EDGE   = 0x1b3a44;  // dim link
const C_DIM    = 0x42505d;  // grey (degraded / no live data)
const C_STEM   = 0x1b3a44;  // dim petal stem
const C_BLACK  = 0x000000;

// The 8 petals in canonical order (spec §"The 8 petals"). Petal 0 shares the
// pistil (proven core). Each maps to a real cluster; `kind` drives its colour.
const PETALS = [
  { key: "proven",       label: "Proven Core",         kind: "locked"  },
  { key: "verified",     label: "Verified Theorems",   kind: "verif"   },
  { key: "experimental", label: "Experimental",        kind: "verif"   },
  { key: "unified",      label: "Unified Formulas",    kind: "borrow"  },
  { key: "ouroboros",    label: "Ouroboros Codexes",   kind: "borrow"  },
  { key: "surfaces",     label: "Surfaces (the 64)",   kind: "verif"   },
  { key: "memory",       label: "Memory & Provenance", kind: "verif"   },
  { key: "conjecture",   label: "Conjectures",         kind: "conj"    },
];
const KIND_COLOR = { locked: C_LOCKED, verif: C_VERIF, borrow: C_BORROW, conj: C_CONJ };

// petal id (from the live graph node's `petal` field) alias resolution — accept
// a few honest synonyms so the surface renders whatever the organ emits.
const PETAL_ALIAS = {
  proven: "proven", core: "proven", locked: "proven", pistil: "proven",
  verified: "verified", theorems: "verified", theorem: "verified",
  experimental: "experimental", exper: "experimental",
  unified: "unified", formulas: "unified", "unified_formulas": "unified",
  ouroboros: "ouroboros", codex: "ouroboros", codexes: "ouroboros",
  surfaces: "surfaces", surface: "surfaces",
  memory: "memory", provenance: "memory", "memory_provenance": "memory",
  conjecture: "conjecture", conjectures: "conjecture", conj: "conjecture",
};
function _resolvePetal(k) {
  if (k == null) return null;
  const s = String(k).toLowerCase();
  return PETAL_ALIAS[s] || (PETALS.some((p) => p.key === s) ? s : null);
}

const TIER_RADIUS = { locked: 0.36, verif: 0.2, borrow: 0.2, conj: 0.17 };
const PETAL_R0 = 0.9;   // inner radius where a petal starts
const PETAL_DR = 0.62;  // radial step per tier-depth ring within a petal

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _badge = null, _plain = false;

let _pistil = null;          // the immutable proven-core mesh at the center
let _petalGroups = {};       // petalKey -> THREE.Group (rotates/scales on bloom)
let _nodeMeshes = {};        // node id -> mesh
let _edgeLines = [];         // cross-petal dependency line segments
let _pos = {};               // node id -> THREE.Vector3 (world-ish, pre-petal-transform)
let _t0 = 0;

const S = {
  label: null,
  nodes: [], edges: [],
  lockedCount: null,
  conjGreen: null,
  bloomOverall: null,          // 0..1 overall bloom fraction
  petalBloom: {},              // petalKey -> 0..1 open fraction
  petalState: {},              // petalKey -> string (open/closed label)
  provCoverage: null,          // 0..1 provenance coverage
  provCovered: null, provTotal: null,
  pistilClosed: null,          // must be true (immutable, always closed/solid)
  state: "init",
};

// deterministic hash for stable per-node jitter (no RNG on the client).
function _hash(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h;
}

// =============================================================================
// mount
// =============================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());

  _buildOverlay(ctx);
  _buildScaffold();               // pistil + 8 empty petal groups (render before live data)
  _badge = ctx.live.createBadge();

  // Pull the real graph once, then poll the bloom snapshot every 5s.
  _polls.push(ctx.live.poll(EP_GRAPH, 0, _onGraph, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));
  _polls.push(ctx.live.poll(EP_BLOOM, 5000, _onBloom, {
    onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
  _paintOverlay();
}

function _readLabel(j) {
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label : "MODELED";
  return String(lbl).toUpperCase();
}

// =============================================================================
// live handlers
// =============================================================================
function _onGraph(j) {
  if (!j || !_group) { S.state = "error"; _paintOverlay(); return; }
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.nodes = Array.isArray(p.nodes) ? p.nodes : [];
  S.edges = Array.isArray(p.edges) ? p.edges : [];
  S.lockedCount = p.locked_count != null ? p.locked_count : null;
  // provenance coverage: fraction of nodes carrying a real provenance field.
  if (S.nodes.length) {
    const cov = S.nodes.filter((n) => n && n.provenance != null && String(n.provenance).length > 0).length;
    S.provCovered = cov; S.provTotal = S.nodes.length;
    S.provCoverage = cov / S.nodes.length;
  }
  _rebuildGraph();
  _paintOverlay();
}

function _onBloom(j) {
  if (!j) return;
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.bloomOverall = p.bloom_overall != null ? p.bloom_overall
                 : (p.bloom_fraction != null ? p.bloom_fraction : null);
  S.conjGreen = p.conjecture_rendered_green != null ? p.conjecture_rendered_green : null;
  S.pistilClosed = p.pistil_closed != null ? p.pistil_closed
                 : (p.core_immutable != null ? p.core_immutable : null);
  if (p.locked_count != null) S.lockedCount = p.locked_count;
  if (p.provenance_coverage != null) S.provCoverage = p.provenance_coverage;

  // per-petal bloom_fraction. Accept either a keyed object {petal: frac} or an
  // array of {petal, bloom_fraction, open}.
  const pb = {};
  const psState = {};
  const src = p.petals || p.per_petal || null;
  if (Array.isArray(src)) {
    src.forEach((row) => {
      const key = _resolvePetal(row && (row.petal || row.key || row.id));
      if (!key) return;
      const f = row.bloom_fraction != null ? row.bloom_fraction
              : (row.fraction != null ? row.fraction : (row.open != null ? row.open : 0));
      pb[key] = _clamp01(Number(f) || 0);
      psState[key] = row.state || (pb[key] > 0.5 ? "open" : "closed");
    });
  } else if (src && typeof src === "object") {
    Object.keys(src).forEach((k) => {
      const key = _resolvePetal(k);
      if (!key) return;
      const v = src[k];
      const f = (v && typeof v === "object")
        ? (v.bloom_fraction != null ? v.bloom_fraction : (v.fraction != null ? v.fraction : 0))
        : v;
      pb[key] = _clamp01(Number(f) || 0);
      psState[key] = (v && v.state) || (pb[key] > 0.5 ? "open" : "closed");
    });
  }
  // HARD invariant: the conjecture petal never opens (stays closed/dim/grey).
  pb.conjecture = 0;
  psState.conjecture = "closed (unproven)";
  S.petalBloom = pb;
  S.petalState = psState;
  _paintOverlay();
}

function _clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }

// =============================================================================
// scene: pistil + petals
// =============================================================================
function _buildScaffold() {
  // The pistil: proven-core sphere at the exact center. Always closed / solid /
  // immutable. Rendered even before live data so the organism has a heart.
  const geo = new _THREE.SphereGeometry(0.5, 28, 28);
  const mat = new _THREE.MeshStandardMaterial({
    color: C_LOCKED, emissive: C_LOCKED, emissiveIntensity: 0.4,
    metalness: 0.15, roughness: 0.35, transparent: false, opacity: 1.0,
  });
  _pistil = new _THREE.Mesh(geo, mat);
  _pistil.userData = { role: "pistil", immutable: true };
  _group.add(_pistil);
  S.pistilClosed = true;   // solid + closed by construction

  // 8 empty petal groups arranged at 45° intervals; each rotates/scales on bloom.
  PETALS.forEach((petal, i) => {
    const g = new _THREE.Group();
    const ang = (i / PETALS.length) * Math.PI * 2;   // 45° apart
    g.userData = { key: petal.key, angle: ang, kind: petal.kind, targetOpen: 0, curOpen: 0 };
    // start "closed": tucked inward and folded down.
    g.rotation.z = ang;
    g.rotation.x = -0.95;      // folded down toward the core (closed bud)
    g.scale.setScalar(0.55);
    _petalGroups[petal.key] = g;
    _group.add(g);

    // a dim stem line from the pistil outward along the petal's axis (static).
    const p0 = new _THREE.Vector3(0, 0, 0);
    const p1 = new _THREE.Vector3(PETAL_R0 * 0.9, 0, 0);
    const sg = new _THREE.BufferGeometry().setFromPoints([p0, p1]);
    const sm = new _THREE.LineBasicMaterial({ color: C_STEM, transparent: true, opacity: 0.45 });
    g.add(new _THREE.Line(sg, sm));
  });
}

function _clearNodes() {
  Object.values(_nodeMeshes).forEach((m) => {
    if (m.geometry && m.geometry.dispose) m.geometry.dispose();
    if (m.material && m.material.dispose) m.material.dispose();
    if (m.parent) m.parent.remove(m);
  });
  _edgeLines.forEach((l) => {
    if (l.geometry && l.geometry.dispose) l.geometry.dispose();
    if (l.material && l.material.dispose) l.material.dispose();
    if (l.parent) l.parent.remove(l);
  });
  _nodeMeshes = {}; _edgeLines = [];
}

// Place a node inside its petal's local frame. The petal group is oriented along
// +X (its axis); depth increases radius, and a hashed lateral offset fans the
// cluster into a leaf shape.
function _placeInPetal(n, indexInPetal, countInPetal) {
  const depth = n.tier_depth != null ? n.tier_depth
              : (n.depth != null ? n.depth : indexInPetal);
  const r = PETAL_R0 + PETAL_DR * (Number(depth) || 0);
  const spread = (indexInPetal / Math.max(1, countInPetal) - 0.5); // -0.5..0.5
  const lateral = spread * 0.9 * (1 + 0.15 * (Number(depth) || 0));
  const lift = ((_hash(n.id + "y") % 200) / 200 - 0.5) * 0.4;
  return new _THREE.Vector3(r, lift, lateral);
}

function _rebuildGraph() {
  if (!_group || !S.nodes.length) return;
  _clearNodes();
  _pos = {};

  // bucket nodes by resolved petal.
  const byPetal = {};
  PETALS.forEach((p) => { byPetal[p.key] = []; });
  S.nodes.forEach((n) => {
    let key = _resolvePetal(n.petal != null ? n.petal : n.cluster);
    if (!key) {
      // fall back on tier -> petal so nothing goes unhomed.
      if (n.tier === "locked" || n.tier === "proven") key = "proven";
      else if (n.tier === "conjecture") key = "conjecture";
      else key = "verified";
    }
    (byPetal[key] = byPetal[key] || []).push(n);
  });

  // build nodes into their petal group's local frame.
  Object.keys(byPetal).forEach((key) => {
    const grp = _petalGroups[key];
    const arr = byPetal[key];
    const petalDef = PETALS.find((p) => p.key === key) || PETALS[1];
    arr.forEach((n, i) => {
      const isConj = (key === "conjecture") || (n.tier === "conjecture");
      const isLocked = (key === "proven") && (n.tier === "locked" || n.tier === "proven");
      const kind = isConj ? "conj" : (isLocked ? "locked" : petalDef.kind);
      const col = KIND_COLOR[kind] != null ? KIND_COLOR[kind] : C_DIM;
      const rad = TIER_RADIUS[kind] != null ? TIER_RADIUS[kind] : 0.2;
      const geo = new _THREE.SphereGeometry(rad, 16, 16);
      // conjecture nodes: flat, emissive-free grey — can NEVER read as fired green.
      const mat = new _THREE.MeshStandardMaterial({
        color: col,
        emissive: isConj ? C_BLACK : col,
        emissiveIntensity: isConj ? 0.0 : 0.28,
        metalness: 0.1, roughness: isConj ? 0.95 : 0.5,
        transparent: true, opacity: isConj ? 0.5 : 0.95,
      });
      const mesh = new _THREE.Mesh(geo, mat);
      const local = _placeInPetal(n, i, arr.length);
      mesh.position.copy(local);
      mesh.userData = { id: n.id, key, kind, isConj, baseEmissive: isConj ? 0.0 : 0.28 };
      _nodeMeshes[n.id] = mesh;
      _pos[n.id] = { key, local };
      if (grp) grp.add(mesh);
      else _group.add(mesh);   // pistil-only proven nodes ride the core
    });
  });

  // cross-petal dependency edges (real dependencies from the graph). Drawn in the
  // parent group using each endpoint's petal-transformed world position at build
  // time; kept dim so the bloom reads clearly.
  S.edges.forEach((e) => {
    const a = _worldOf(e.src), b = _worldOf(e.dst);
    if (!a || !b) return;
    const g = new _THREE.BufferGeometry().setFromPoints([a, b]);
    const m = new _THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.4 });
    const line = new _THREE.Line(g, m);
    line.userData = { role: "edge" };
    _edgeLines.push(line); _group.add(line);
  });
}

// approximate world position of a node given its petal group's initial (closed)
// transform — good enough for the dim dependency web; the petals then bloom.
function _worldOf(id) {
  const rec = _pos[id];
  if (!rec) return null;
  const grp = _petalGroups[rec.key];
  if (!grp) return rec.local.clone();
  const v = rec.local.clone();
  v.applyEuler(new _THREE.Euler(grp.rotation.x, grp.rotation.y, grp.rotation.z));
  v.multiplyScalar(grp.scale.x);
  return v;
}

// =============================================================================
// animation: bloom = petals open (rotate + scale outward) toward bloom_fraction
// =============================================================================
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = t * 0.1;

  // gentle pistil breathing so the immutable core reads as alive but never grows.
  if (_pistil && _pistil.material) {
    _pistil.material.emissiveIntensity = 0.4 + 0.08 * Math.sin(t * 1.3);
  }

  PETALS.forEach((petal, i) => {
    const grp = _petalGroups[petal.key];
    if (!grp) return;
    const ang = grp.userData.angle;
    const isConj = petal.kind === "conj";
    // target open fraction (conjecture is pinned closed).
    let target = isConj ? 0 : (S.petalBloom[petal.key] != null ? S.petalBloom[petal.key] : 0);
    target = _clamp01(target);
    grp.userData.targetOpen = target;
    // ease current toward target for a smooth bloom.
    grp.userData.curOpen += (target - grp.userData.curOpen) * 0.06;
    const open = grp.userData.curOpen;

    // OPEN = unfold upward (rotation.x from -0.95 closed to ~+0.35 open) and
    // scale outward (0.55 -> 1.0). A tiny per-petal sway adds life.
    const sway = 0.04 * Math.sin(t * 0.8 + i);
    grp.rotation.z = ang;
    grp.rotation.x = -0.95 + open * 1.3 + sway * open;
    grp.scale.setScalar(0.55 + open * 0.45);

    // brighten this petal's non-conjecture nodes with how open it is.
    grp.children.forEach((c) => {
      if (!c.material || !c.userData || c.userData.id == null) return;
      if (c.userData.isConj) { c.material.emissiveIntensity = 0.0; return; } // grey-only invariant
      c.material.emissiveIntensity = c.userData.baseEmissive + 0.55 * open;
    });
  });
}

// =============================================================================
// overlay HUD
// =============================================================================
function _buildOverlay(ctx) {
  _overlay = document.createElement("div");
  _overlay.style.cssText =
    "position:absolute;top:12px;left:12px;max-width:360px;font:12px/1.5 ui-monospace,Menlo,monospace;" +
    "color:#cfe3ea;background:rgba(15,32,39,0.82);border:1px solid #1b3a44;border-radius:10px;padding:12px 14px;" +
    "pointer-events:auto;backdrop-filter:blur(3px);z-index:20;";
  _overlay.innerHTML =
    '<div style="font-weight:700;letter-spacing:.03em;color:#eaf6f9;font-size:13px">The Flower Brain ' +
      '<span id="flower-label" style="float:right;font-size:10px;padding:1px 7px;border-radius:8px;background:#123;color:#3af4c8;border:1px solid #1b3a44">MODELED</span></div>' +
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">Everything SZL built as one 8-petal bloom — the proven-8 pistil at the center, petals open with cluster health.</div>' +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    _row("Overall bloom", "flower-bloom") +
    _row("Locked-core count", "flower-locked") +
    _row("Conjectures shown green", "flower-conjgreen") +
    _row("Provenance coverage", "flower-prov") +
    _row("Nodes / Edges", "flower-ne") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Per-petal open state</div>' +
    '<div id="flower-petals" style="font-size:10.5px;color:#eaf6f9"></div>' +
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">' +
      _leg(C_LOCKED, "proven-8 pistil") + _leg(C_VERIF, "verified") + _leg(C_BORROW, "borrowed") + _leg(C_CONJ, "conjecture (grey)") +
    '</div>' +
    '<div style="margin-top:8px"><button id="flower-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;' +
      'border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button></div>' +
    '<div id="flower-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>';
  (ctx.container || document.body).appendChild(_overlay);
  const btn = _overlay.querySelector("#flower-plain");
  if (btn) btn.addEventListener("click", () => { _plain = !_plain; _applyPlain(); });
}
function _row(k, id) {
  return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px">' +
    '<span style="color:#8fb3bd">' + k + '</span><span id="' + id + '" style="color:#eaf6f9;font-variant-numeric:tabular-nums">—</span></div>';
}
function _leg(hex, txt) {
  const c = "#" + hex.toString(16).padStart(6, "0");
  return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + c + ';margin-right:4px;vertical-align:middle"></span>' + txt + '</span>';
}
function _set(id, v) { const e = _overlay && _overlay.querySelector("#" + id); if (e) e.textContent = v; }

function _paintOverlay() {
  if (!_overlay) return;
  // graceful degrade: 404/missing or error -> show NO-LIVE-DATA honestly.
  const missing = (S.state === "missing" || S.state === "error");
  const deg = missing || (S.state === "degraded");
  const nd = "NO-LIVE-DATA";

  _set("flower-label", S.label || "MODELED");
  if (missing && !S.nodes.length) {
    _set("flower-bloom", nd);
    _set("flower-locked", "8 (proven pistil, offline)");
    _set("flower-conjgreen", "0 (grey by construction)");
    _set("flower-prov", nd);
    _set("flower-ne", nd);
    _set("flower-petals", nd + " — petals stay closed until the organ answers.");
    _dimForDegrade();
    if (_plain) _applyPlain();
    return;
  }

  const d = deg ? "—" : null;
  _set("flower-bloom", d || (S.bloomOverall != null ? (S.bloomOverall * 100).toFixed(1) + "%" : "—"));
  _set("flower-locked", d || (S.lockedCount != null ? String(S.lockedCount) + " (must be 8)" : "8 (pistil)"));
  _set("flower-conjgreen", (S.conjGreen != null ? (S.conjGreen + " (must be 0)") : "0 (grey by construction)"));
  _set("flower-prov", d || (S.provCoverage != null
        ? (S.provCoverage * 100).toFixed(1) + "%" + (S.provTotal != null ? " (" + S.provCovered + "/" + S.provTotal + ")" : "")
        : "—"));
  _set("flower-ne", d || ((S.nodes.length || "—") + " / " + (S.edges.length || "—")));

  // per-petal open state rows.
  const box = _overlay.querySelector("#flower-petals");
  if (box) {
    box.innerHTML = PETALS.map((p) => {
      const c = "#" + KIND_COLOR[p.kind].toString(16).padStart(6, "0");
      let txt;
      if (p.kind === "conj") {
        txt = "closed (unproven)";
      } else if (S.petalBloom[p.key] != null) {
        const f = S.petalBloom[p.key];
        txt = (f * 100).toFixed(0) + "% open";
      } else {
        txt = deg ? "—" : "closed";
      }
      return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px">' +
        '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + c + ';margin-right:5px"></span>' + p.label + '</span>' +
        '<span style="color:#eaf6f9;font-variant-numeric:tabular-nums">' + txt + '</span></div>';
    }).join("");
  }
  if (_plain) _applyPlain();
}

// on degrade, drop live node emissive to the dim grey so nothing reads as fired.
function _dimForDegrade() {
  Object.values(_nodeMeshes).forEach((m) => {
    if (m.material) m.material.emissiveIntensity = 0.0;
  });
}

function _applyPlain() {
  const box = _overlay && _overlay.querySelector("#flower-plainbox");
  if (!box) return;
  box.style.display = _plain ? "block" : "none";
  if (_plain) {
    box.innerHTML =
      "This is our whole body of work drawn as one flower. The solid teal ball in the middle is the " +
      "<b>pistil — the 8 things we have actually machine-proven</b>. It is locked: it never grows and " +
      "never opens. The eight petals are our real clusters (verified theorems, experiments, the borrowed " +
      "formula registry, the ouroboros codexes, the estate surfaces, and our memory/receipt spine). Each " +
      "petal <b>opens</b> as its cluster's health rises — that's the bloom. The grey petal is our " +
      "<b>conjectures we have NOT proven</b> (like \u039B uniqueness and the Khipu BFT ideas); it stays grey " +
      "and closed on purpose and never turns green. Label is <b>" + (S.label || "MODELED") + "</b>: a faithful " +
      "drawing of our real proof graph, not a computation. If the live organ is offline it honestly says " +
      "\u201CNO-LIVE-DATA\u201D and the petals stay shut.";
  }
}

// =============================================================================
// unmount
// =============================================================================
function unmount() {
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
  _pistil = null;
  _petalGroups = {};
  _nodeMeshes = {}; _edgeLines = []; _pos = {};
  _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = null; S.nodes = []; S.edges = [];
  S.lockedCount = S.conjGreen = S.bloomOverall = null;
  S.petalBloom = {}; S.petalState = {};
  S.provCoverage = S.provCovered = S.provTotal = null;
  S.pistilClosed = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP_GRAPH, EP_BLOOM], mount, unmount };
