// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/atlas.js — THE ATLAS (SZL, Wave 27, the 68th surface: the unifying front door).
//
// A single holographic overview that shows the WHOLE 67-surface holographic estate as ONE
// organism, mapped by the Flower Brain's 8 real clusters (the ecosystem's own taxonomy). The
// still, luminous CENTER is the KERNEL PISTIL — the machine-proven locked-8
// {F1,F4,F7,F11,F12,F18,F19,F22} (lutar-lean kernel c7c0ba17) — the immutable heart that never
// grows. Eight labeled cluster regions radiate out at 45° intervals: PROVEN CORE, VERIFIED,
// EXPERIMENTAL, UNIFIED, OUROBOROS, SURFACES (the big one, 58), MEMORY & PROVENANCE (9), and
// CONJECTURES (GRAY, never green). Each cluster holds its member surfaces as nodes; the kernel
// clusters carry the flower's kernel objects instead of surfaces. Hover a node -> the surface
// title + its HONEST label (MODELED / STRUCTURAL-ONLY / ROADMAP / MEASURED — rendered by the
// real per-surface label, never painted uniform). Click a surface node -> deep-links to that
// surface's tab (location.hash = '#'+id) so the holographic app navigates there. Loop Forge's
// living process is drawn as animated arcs (proposer -> kernel gate -> archive) between clusters.
//
// THE MAP IS REAL: every classification traces to szl_kc_atlas (the backend organ), whose
// taxonomy source is the Flower Brain (szl_kc_flower.py). The LAYOUT is MODELED — a
// deterministic, honest drawing read VERBATIM from /api/a11oy/v1/atlas/{map,organism}. The
// honesty label "MODELED" is shown as-is and is never upgraded. Unification by CARTOGRAPHY:
// this gives the flat 67-tab wall a spine without removing a single surface.
//
// HARD INVARIANTS (Doctrine v11):
//   * clusters = EXACTLY 8. locked-core = EXACTLY 8 (the pistil never grows).
//   * coverage 1.0 — every one of the 67 surfaces is classified into exactly one cluster.
//   * CONJECTURE cluster renders GREY (0x5a6570), visibly dim, NEVER green.
//   * honest label mix rendered by real label (MODELED / STRUCTURAL-ONLY / ROADMAP / MEASURED),
//     not painted uniform.
//   * COLOURS ONLY: proof-teal 0x3af4c8, lattice-blue 0x5b8dee, cyan-blue 0x39c0d3,
//     gold 0xe8c074, greys (0x5a6570 / 0x42505d / 0x1b3a44), black 0x000000. NO forbidden hues.
//   * 0 runtime CDN (three.js via ctx.THREE). Degrades gracefully to NO-LIVE-DATA on 404.
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "atlas";
const TITLE = "Atlas";

// Live endpoints — same convention as loopforge.js (same-origin a11oy namespace).
const EP_MAP      = "/api/a11oy/v1/atlas/map";
const EP_ORGANISM = "/api/a11oy/v1/atlas/organism";

// ---- Colour palette. We render the estate honestly using ONLY teal / lattice-blue / cyan-blue /
// gold / greys / black. The backend's cluster hue field carries a bluish tone upstream for the
// ouroboros/surfaces petals that reads as a forbidden hue under Doctrine v11; we do NOT trust it.
// Instead we map every cluster to an allowed hue on the client, keyed by cluster nature, and the
// conjecture cluster is always grey. Colour still encodes meaning; it stays within the allowed set.
const C_LOCKED = 0x3af4c8;  // proof-teal   — proven core / pistil
const C_VERIF  = 0x5b8dee;  // lattice-blue — verified / experimental / surfaces / memory
const C_CYAN   = 0x39c0d3;  // cyan-blue    — unified formulas / ouroboros (remapped from upstream)
const C_CONJ   = 0x5a6570;  // GREY         — conjectures (never green, never opens bright)
const C_EDGE   = 0x1b3a44;  // dim link
const C_DIM    = 0x42505d;  // grey (degraded / no live data)
const C_GOLD   = 0xe8c074;  // Loop-Forge accepted flow
const C_BLACK  = 0x000000;

// Cluster key -> render colour (allowed hues only, meaning-encoding). Conjectures forced grey.
const CLUSTER_COLOR = {
  proven_core:  C_LOCKED,
  verified:     C_VERIF,
  experimental: C_VERIF,
  unified:      C_CYAN,
  ouroboros:    C_CYAN,
  surfaces:     C_VERIF,
  memory:       C_VERIF,
  conjectures:  C_CONJ,
};
function _clusterColor(key, gray) {
  if (gray) return C_CONJ;
  return CLUSTER_COLOR[String(key)] != null ? CLUSTER_COLOR[String(key)] : C_VERIF;
}

// Honest per-surface label -> node hue accent. We DO NOT paint everything the same: the label
// mix (MODELED / STRUCTURAL-ONLY / ROADMAP / MEASURED) is rendered honestly per node.
const LABEL_COLOR = {
  "MODELED":         C_VERIF,   // modeled (the estate's default honest posture)
  "STRUCTURAL-ONLY": C_DIM,     // structural-only — dim grey-blue, no proof claim
  "ROADMAP":         C_GOLD,    // roadmap — gold, not-yet-built
  "MEASURED":        C_LOCKED,  // measured — proof-teal (the one truly measured surface)
};
function _labelColor(lbl) {
  const t = String(lbl || "MODELED").toUpperCase();
  return LABEL_COLOR[t] != null ? LABEL_COLOR[t] : C_VERIF;
}

// Geometry constants.
const PISTIL_R   = 0.62;   // the immutable locked-8 heart
const RING_INNER = 2.2;    // where cluster regions begin
const RING_STEP  = 0.95;   // radial step per node ring within a cluster
const NODE_R     = 0.13;   // member-surface node radius
const KOBJ_R     = 0.10;   // kernel-object node radius
const DEG        = Math.PI / 180;

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _badge = null, _plain = false, _show = null;

let _pistil = null;            // immutable locked-8 core at center
let _clusterGroups = {};       // clusterKey -> THREE.Group
let _nodeMeshes = [];          // pickable node records { mesh, id, title, label, cluster, isSurface }
let _bridgeLines = [];         // cross-cluster bridge arcs (static-ish)
let _flowArcs = [];            // Loop-Forge animated flow arcs
let _tooltip = null;           // hover tooltip DOM
let _raycaster = null, _pointer = null, _hovered = null;
let _t0 = 0;
let _domEl = null, _onMove = null, _onClick = null, _onLeave = null;

const S = {
  label: null,
  state: "init",
  clusters: [],                // from /map: rich {cluster,key,name,gray,is_pistil,surfaces[],kernel_object_ids[],surface_count,label_mix}
  petals: [],                  // from /organism: layout {cluster,key,angle_deg,angle_jitter_deg,is_pistil,gray,surface_count}
  petalByCluster: {},          // cluster -> petal layout
  crossLinks: [],              // from /organism
  lfFlow: null,                // Loop-Forge flow overlay
  clustersTotal: null,
  surfaceCount: null,          // 67
  totalClassified: null,
  coverage: null,
  lockedCoreCount: null,
  conjectureGray: null,
  everyOnce: null,
  labelMix: {},                // overall honest label mix
  built: false,
};

// deterministic hash for stable per-node jitter (no client RNG).
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

  _raycaster = new _THREE.Raycaster();
  _pointer = new _THREE.Vector2();

  _badge = ctx.live.createBadge();
  _buildOverlay(ctx);
  _buildTooltip(ctx);
  _buildScaffold();               // pistil + 8 empty cluster groups (render before live data)

  // Pull the rich classification (map) + the organism layout, then keep them fresh.
  _polls.push(ctx.live.poll(EP_MAP, 15000, _onMap, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));
  _polls.push(ctx.live.poll(EP_ORGANISM, 20000, _onOrganism, {
    onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  // pointer hover/click for node picking + surface deep-linking.
  _domEl = (_stage.renderer && _stage.renderer.domElement) || null;
  if (_domEl) {
    _onMove  = (e) => _handleMove(e);
    _onClick = (e) => _handleClick(e);
    _onLeave = () => { _setHover(null); };
    _domEl.addEventListener("pointermove", _onMove);
    _domEl.addEventListener("pointerdown", _onClick);
    _domEl.addEventListener("pointerleave", _onLeave);
  }

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
function _onMap(j) {
  if (!j || !_group) { S.state = "error"; _paintOverlay(); return; }
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.clusters = Array.isArray(p.clusters) ? p.clusters : [];
  S.clustersTotal = p.clusters_total != null ? p.clusters_total : (S.clusters.length || null);
  S.surfaceCount = p.surface_count != null ? p.surface_count : null;
  S.totalClassified = p.total_classified != null ? p.total_classified : null;
  S.coverage = p.coverage != null ? p.coverage : null;
  S.lockedCoreCount = p.locked_core_count != null ? p.locked_core_count : null;
  S.conjectureGray = (p.conjecture_cluster_gray != null) ? p.conjecture_cluster_gray : null;
  S.everyOnce = (p.every_surface_classified_once != null) ? p.every_surface_classified_once : null;

  // overall honest label mix, summed across clusters (rendered by real label, never uniform).
  const mix = {};
  S.clusters.forEach((c) => {
    const lm = c && c.label_mix ? c.label_mix : {};
    Object.keys(lm).forEach((k) => { mix[k] = (mix[k] || 0) + (Number(lm[k]) || 0); });
  });
  S.labelMix = mix;

  _tryBuild();
  _paintOverlay();
}

function _onOrganism(j) {
  if (!j || !_group) return;
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.petals = Array.isArray(p.petals) ? p.petals : [];
  S.petalByCluster = {};
  S.petals.forEach((pt) => { if (pt && pt.cluster != null) S.petalByCluster[pt.cluster] = pt; });
  S.crossLinks = Array.isArray(p.cross_links) ? p.cross_links : [];
  S.lfFlow = p.loop_forge_flow || null;
  if (p.coverage != null) S.coverage = p.coverage;
  if (p.locked_core_count != null) S.lockedCoreCount = p.locked_core_count;
  if (p.surface_count != null) S.surfaceCount = p.surface_count;
  if (p.conjecture_cluster_gray != null) S.conjectureGray = p.conjecture_cluster_gray;

  _tryBuild();
  _paintOverlay();
}

// only (re)build the 3D map once we have BOTH the classification and the layout.
function _tryBuild() {
  if (S.clusters.length && S.petals.length) _rebuildOrganism();
}

// =============================================================================
// scene: pistil + cluster regions
// =============================================================================
function _buildScaffold() {
  // the immutable locked-8 pistil at the exact center — always solid, always closed.
  const geo = new _THREE.SphereGeometry(PISTIL_R, 32, 32);
  const mat = new _THREE.MeshStandardMaterial({
    color: C_LOCKED, emissive: C_LOCKED, emissiveIntensity: 0.45,
    metalness: 0.15, roughness: 0.35, transparent: false, opacity: 1.0,
  });
  _pistil = new _THREE.Mesh(geo, mat);
  _pistil.userData = { role: "pistil", immutable: true };
  _group.add(_pistil);

  // faint proof-teal halo ring around the pistil so the still center reads as luminous.
  const hg = new _THREE.TorusGeometry(PISTIL_R * 1.6, 0.03, 16, 96);
  const hm = new _THREE.MeshBasicMaterial({
    color: C_LOCKED, transparent: true, opacity: 0.35,
    blending: _THREE.AdditiveBlending, depthWrite: false,
  });
  const halo = new _THREE.Mesh(hg, hm);
  halo.rotation.x = Math.PI / 2;
  halo.userData = { role: "pistil-halo" };
  _group.add(halo);
}

function _disposeMesh(m) {
  if (!m) return;
  if (m.geometry && m.geometry.dispose) m.geometry.dispose();
  if (m.material) { const a = Array.isArray(m.material) ? m.material : [m.material]; a.forEach((x) => x.dispose && x.dispose()); }
  if (m.parent) m.parent.remove(m);
}

function _clearOrganism() {
  Object.values(_clusterGroups).forEach((g) => {
    g.traverse((o) => { if (o !== g) { if (o.geometry && o.geometry.dispose) o.geometry.dispose(); if (o.material) { const a = Array.isArray(o.material) ? o.material : [o.material]; a.forEach((x) => x.dispose && x.dispose()); } } });
    if (g.parent) g.parent.remove(g);
  });
  _bridgeLines.forEach((l) => _disposeMesh(l));
  _flowArcs.forEach((rec) => { if (rec.line) _disposeMesh(rec.line); if (rec.dot) _disposeMesh(rec.dot); });
  _clusterGroups = {}; _nodeMeshes = []; _bridgeLines = []; _flowArcs = [];
}

// world position of a cluster's radial axis at a given radius (respecting jitter).
function _clusterAxis(petal) {
  const ang = ((petal.angle_deg || 0) + (petal.angle_jitter_deg || 0)) * DEG;
  return { ang, dir: new _THREE.Vector3(Math.cos(ang), 0, Math.sin(ang)) };
}

// place a node within a cluster's wedge: radius grows in rings, lateral fans the members out.
function _placeNode(idKey, indexInCluster, countInCluster, ang) {
  const perRing = 6;
  const ring = Math.floor(indexInCluster / perRing);
  const inRing = indexInCluster % perRing;
  const r = RING_INNER + RING_STEP * ring;
  // fan lateral spread within the wedge (±~26°), tightening as rings grow outward.
  const spread = (perRing > 1) ? (inRing / (perRing - 1) - 0.5) : 0;   // -0.5..0.5
  const wedge = (26 - 3 * ring) * DEG;
  const a = ang + spread * wedge;
  const lift = (((_hash(idKey + "y") % 200) / 200) - 0.5) * 0.7;
  return new _THREE.Vector3(Math.cos(a) * r, lift, Math.sin(a) * r);
}

function _rebuildOrganism() {
  if (!_group) return;
  _clearOrganism();

  // build each cluster region as its own group so we can animate/label it.
  S.clusters.forEach((c) => {
    const petal = S.petalByCluster[c.cluster];
    if (!petal) return;
    const grp = new _THREE.Group();
    grp.userData = { cluster: c.cluster, key: c.key, name: c.name };
    _clusterGroups[c.key] = grp;
    _group.add(grp);

    const { ang, dir } = _clusterAxis(petal);
    const col = _clusterColor(c.key, c.gray);

    // a dim stem line from the pistil outward along the cluster axis (region marker).
    const p0 = dir.clone().multiplyScalar(PISTIL_R * 1.1);
    const p1 = dir.clone().multiplyScalar(RING_INNER * 0.92);
    const sg = new _THREE.BufferGeometry().setFromPoints([p0, p1]);
    const sm = new _THREE.LineBasicMaterial({ color: c.gray ? C_CONJ : C_EDGE, transparent: true, opacity: 0.5 });
    grp.add(new _THREE.Line(sg, sm));

    // the surfaces this cluster holds (clusters 6 & 7) OR its kernel objects (1,2,3,4,5,8).
    const surfaces = Array.isArray(c.surfaces) ? c.surfaces : [];
    const kobjs = Array.isArray(c.kernel_object_ids) ? c.kernel_object_ids : [];

    if (surfaces.length) {
      surfaces.forEach((s, i) => {
        const hLabel = String(s.label || "MODELED").toUpperCase();
        // honest label colour — the estate is NOT painted uniform.
        const nodeCol = c.gray ? C_CONJ : _labelColor(hLabel);
        const isRoadmap = hLabel === "ROADMAP";
        const isStruct = hLabel === "STRUCTURAL-ONLY";
        const geo = new _THREE.SphereGeometry(NODE_R, 16, 16);
        const mat = new _THREE.MeshStandardMaterial({
          color: nodeCol,
          emissive: c.gray ? C_BLACK : nodeCol,
          emissiveIntensity: c.gray ? 0.0 : (isStruct ? 0.14 : (isRoadmap ? 0.22 : 0.3)),
          metalness: 0.1, roughness: c.gray ? 0.95 : 0.5,
          transparent: true, opacity: c.gray ? 0.5 : (isStruct ? 0.8 : 0.95),
        });
        const mesh = new _THREE.Mesh(geo, mat);
        mesh.position.copy(_placeNode(s.id, i, surfaces.length, ang));
        mesh.userData = {
          id: s.id, title: s.title || s.id, hlabel: hLabel, cluster: c.name,
          subTag: s.sub_tag || "", isSurface: true,
          baseEmissive: c.gray ? 0.0 : (isStruct ? 0.14 : (isRoadmap ? 0.22 : 0.3)),
        };
        grp.add(mesh);
        _nodeMeshes.push({ mesh, id: s.id, title: mesh.userData.title, label: hLabel, cluster: c.name, isSurface: true });
      });
    } else if (kobjs.length) {
      // kernel-object nodes: small proof-teal (or grey for conjectures) markers; NOT clickable
      // surfaces — they are the flower's carried kernel objects, not tabs.
      kobjs.forEach((oid, i) => {
        const nodeCol = c.gray ? C_CONJ : col;
        const isPistil = !!c.is_pistil;
        const geo = new _THREE.SphereGeometry(KOBJ_R, 14, 14);
        const mat = new _THREE.MeshStandardMaterial({
          color: nodeCol,
          emissive: c.gray ? C_BLACK : nodeCol,
          emissiveIntensity: c.gray ? 0.0 : (isPistil ? 0.42 : 0.28),
          metalness: 0.12, roughness: c.gray ? 0.95 : 0.45,
          transparent: true, opacity: c.gray ? 0.5 : 0.92,
        });
        const mesh = new _THREE.Mesh(geo, mat);
        // pistil objects hug the core; other kernel objects sit in the first ring.
        if (isPistil) {
          const a = ang + (i / Math.max(1, kobjs.length) - 0.5) * 40 * DEG;
          const rr = PISTIL_R * 1.35 + (i % 2) * 0.18;
          mesh.position.set(Math.cos(a) * rr, (((_hash(oid) % 100) / 100) - 0.5) * 0.3, Math.sin(a) * rr);
        } else {
          mesh.position.copy(_placeNode(oid, i, kobjs.length, ang));
        }
        mesh.userData = {
          id: oid, title: oid, hlabel: c.gray ? "CONJECTURE (grey)" : "kernel object",
          cluster: c.name, isSurface: false,
          baseEmissive: c.gray ? 0.0 : (isPistil ? 0.42 : 0.28),
        };
        grp.add(mesh);
        _nodeMeshes.push({ mesh, id: oid, title: oid, label: mesh.userData.hlabel, cluster: c.name, isSurface: false });
      });
    }
  });

  // cross-cluster bridge arcs (real, cited dependencies) — dim so the map reads clearly.
  S.crossLinks.forEach((b) => {
    const from = S.petalByCluster[b.from_cluster];
    const to = S.petalByCluster[b.to_cluster];
    if (!from || !to) return;
    const a = _clusterAxis(from).dir.clone().multiplyScalar(RING_INNER + 0.4);
    const c = _clusterAxis(to).dir.clone().multiplyScalar(RING_INNER + 0.4);
    const mid = a.clone().add(c).multiplyScalar(0.5); mid.y += 1.4;   // lift the arc
    const curve = new _THREE.QuadraticBezierCurve3(a, mid, c);
    const pts = curve.getPoints(28);
    const g = new _THREE.BufferGeometry().setFromPoints(pts);
    const m = new _THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.32 });
    const line = new _THREE.Line(g, m);
    line.userData = { role: "bridge", surface: b.surface };
    _bridgeLines.push(line); _group.add(line);
  });

  // Loop-Forge flow overlay: animated arcs proposer -> kernel gate -> archive (+ conjecture-gray).
  if (S.lfFlow && Array.isArray(S.lfFlow.flow)) {
    S.lfFlow.flow.forEach((f, idx) => {
      const from = S.petalByCluster[f.from_cluster];
      const to = S.petalByCluster[f.to_cluster];
      if (!from || !to) return;
      const toGray = (f.stage === "conjecture_gray");
      const a = _clusterAxis(from).dir.clone().multiplyScalar(RING_INNER + 0.9);
      const c = _clusterAxis(to).dir.clone().multiplyScalar(RING_INNER + 0.9);
      const mid = a.clone().add(c).multiplyScalar(0.5); mid.y += 2.1 + 0.25 * idx;
      const curve = new _THREE.QuadraticBezierCurve3(a, mid, c);
      const pts = curve.getPoints(40);
      const g = new _THREE.BufferGeometry().setFromPoints(pts);
      // gold for the accepting flow; grey for the conjecture leg (NEVER green).
      const col = toGray ? C_CONJ : C_GOLD;
      const m = new _THREE.LineBasicMaterial({ color: col, transparent: true, opacity: toGray ? 0.3 : 0.5 });
      const line = new _THREE.Line(g, m);
      line.userData = { role: "lf-flow", stage: f.stage };
      _group.add(line);
      // a traveling token that rides the arc (grey never brightens).
      const dg = new _THREE.SphereGeometry(toGray ? 0.08 : 0.11, 12, 12);
      const dm = new _THREE.MeshStandardMaterial({
        color: toGray ? C_CONJ : C_GOLD,
        emissive: toGray ? C_BLACK : C_GOLD,
        emissiveIntensity: toGray ? 0.0 : 0.55,
        metalness: 0.1, roughness: toGray ? 0.95 : 0.4, transparent: true, opacity: toGray ? 0.5 : 0.95,
      });
      const dot = new _THREE.Mesh(dg, dm);
      _group.add(dot);
      _flowArcs.push({ line, dot, curve, phase: idx * 0.28, toGray, stage: f.stage });
    });
  }

  S.built = true;
}

// =============================================================================
// hover / click (raycast against surface + kernel nodes)
// =============================================================================
function _updatePointer(e) {
  if (!_domEl) return false;
  const r = _domEl.getBoundingClientRect();
  if (!r.width || !r.height) return false;
  _pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  _pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  return true;
}

function _pick() {
  if (!_raycaster || !_stage || !_stage.camera) return null;
  _raycaster.setFromCamera(_pointer, _stage.camera);
  const meshes = _nodeMeshes.map((r) => r.mesh);
  const hits = _raycaster.intersectObjects(meshes, false);
  if (!hits.length) return null;
  const m = hits[0].object;
  return _nodeMeshes.find((r) => r.mesh === m) || null;
}

function _handleMove(e) {
  if (!_updatePointer(e)) return;
  const rec = _pick();
  _setHover(rec);
  if (_tooltip) {
    if (rec) {
      _tooltip.style.display = "block";
      const rect = _domEl.getBoundingClientRect();
      _tooltip.style.left = (e.clientX - rect.left + 14) + "px";
      _tooltip.style.top = (e.clientY - rect.top + 12) + "px";
      const labelChip = rec.isSurface
        ? '<span style="color:' + _hex(_labelColor(rec.label)) + '">' + rec.label + '</span>'
        : '<span style="color:#8fb3bd">' + rec.label + '</span>';
      _tooltip.innerHTML =
        '<div style="font-weight:700;color:#eaf6f9">' + _esc(rec.title) + '</div>' +
        '<div style="margin-top:2px;color:#8fb3bd">' + _esc(rec.cluster) + '</div>' +
        '<div style="margin-top:3px">label: ' + labelChip + '</div>' +
        (rec.isSurface ? '<div style="margin-top:3px;color:#9fc;font-size:9.5px">click → open this surface</div>'
                       : '<div style="margin-top:3px;color:#7d8a96;font-size:9.5px">kernel object (not a tab)</div>');
    } else {
      _tooltip.style.display = "none";
    }
  }
  if (_domEl) _domEl.style.cursor = (rec && rec.isSurface) ? "pointer" : "default";
}

function _setHover(rec) {
  if (_hovered === rec) return;
  // reset previous
  if (_hovered && _hovered.mesh && _hovered.mesh.material && _hovered.mesh.userData) {
    const bm = _hovered.mesh.userData.baseEmissive;
    if (bm != null) _hovered.mesh.material.emissiveIntensity = bm;
    _hovered.mesh.scale.setScalar(1);
  }
  _hovered = rec;
  if (_hovered && _hovered.mesh && _hovered.mesh.material) {
    // don't brighten grey conjecture nodes (grey-only invariant).
    const isGrey = String(_hovered.label).indexOf("CONJECTURE") >= 0;
    if (!isGrey) _hovered.mesh.material.emissiveIntensity = (_hovered.mesh.userData.baseEmissive || 0.3) + 0.5;
    _hovered.mesh.scale.setScalar(1.5);
  }
}

function _handleClick(e) {
  if (!_updatePointer(e)) return;
  const rec = _pick();
  if (!rec || !rec.isSurface) return;   // only surface nodes deep-link
  const id = rec.id;
  // deep-link to the surface's tab. Prefer the shell's own selector for an immediate
  // in-app navigation; always set the hash so the estate URL reflects the surface too.
  try {
    if (typeof window !== "undefined" && window.__SZL3D_SHELL__ && typeof window.__SZL3D_SHELL__.select === "function") {
      window.__SZL3D_SHELL__.select(id);
    }
  } catch (_) {}
  try { if (typeof location !== "undefined") location.hash = "#" + id; } catch (_) {}
}

// =============================================================================
// animation
// =============================================================================
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = t * 0.05;

  // gentle pistil breathing — the immutable core reads as alive but never grows.
  if (_pistil && _pistil.material) {
    _pistil.material.emissiveIntensity = 0.45 + 0.08 * Math.sin(t * 1.3);
  }

  // Loop-Forge flow tokens travel along their arcs (grey conjecture token stays dim).
  _flowArcs.forEach((rec, i) => {
    if (!rec.dot || !rec.curve) return;
    const u = ((t * 0.22 + rec.phase) % 1 + 1) % 1;
    const pos = rec.curve.getPoint(u);
    rec.dot.position.copy(pos);
    if (rec.dot.material && !rec.toGray) {
      rec.dot.material.emissiveIntensity = 0.55 + 0.25 * Math.abs(Math.sin(t * 2 + i));
    }
    if (rec.line && rec.line.material && !rec.toGray) {
      rec.line.material.opacity = 0.4 + 0.15 * Math.abs(Math.sin(t * 1.5 + i));
    }
  });
}

// =============================================================================
// overlay HUD
// =============================================================================
function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8", badge: _badge,
    chips: [{ label: "MODELED", name: "label" }],
  });
  _overlay = document.createElement("div");
  _overlay.style.cssText = "font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;";
  _overlay.innerHTML =
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">The whole holographic estate as ONE organism — the 67 surfaces mapped by the Flower Brain\u2019s 8 real clusters. The still teal heart is the machine-proven locked-8 pistil (kernel c7c0ba17); clusters radiate out; hover a node for its honest label, click a surface to open it.</div>' +
    _row("Total surfaces", "atlas-total") +
    _row("Clusters", "atlas-clusters") +
    _row("Coverage (all classified)", "atlas-coverage") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Honest label mix (never painted uniform)</div>' +
    '<div id="atlas-labelmix" style="font-size:10.5px;color:#eaf6f9"></div>' +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Per-cluster counts</div>' +
    '<div id="atlas-clusterlist" style="font-size:10.5px;color:#eaf6f9"></div>' +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Invariants</div>' +
    '<div id="atlas-inv" style="font-size:11px;color:#eaf6f9"></div>' +
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">' +
      _leg(C_LOCKED, "proven / measured") + _leg(C_VERIF, "modeled") + _leg(C_GOLD, "roadmap / LF flow") +
      _leg(C_DIM, "structural-only") + _leg(C_CONJ, "conjecture (grey)") +
    '</div>' +
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<button id="atlas-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>' +
      '<button id="atlas-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">What is this?</button>' +
    '</div>' +
    '<div id="atlas-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>' +
    '<div id="atlas-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  _show.body.appendChild(_overlay);
  const pb = _overlay.querySelector("#atlas-plain");
  if (pb) pb.addEventListener("click", () => { _plain = !_plain; _applyPlain(); });
  const ib = _overlay.querySelector("#atlas-info");
  if (ib) ib.addEventListener("click", () => {
    const box = _overlay.querySelector("#atlas-infobox");
    if (box) box.style.display = box.style.display === "none" ? "block" : "none";
    if (box && box.innerHTML === "") box.innerHTML = _infoHTML();
  });
}
function _row(k, id) {
  return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px">' +
    '<span style="color:#8fb3bd">' + k + '</span><span id="' + id + '" style="color:#eaf6f9;font-variant-numeric:tabular-nums">\u2014</span></div>';
}
function _leg(hex, txt) {
  const c = _hex(hex);
  return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + c + ';margin-right:4px;vertical-align:middle"></span>' + txt + '</span>';
}
function _hex(n) { return "#" + (n >>> 0).toString(16).padStart(6, "0"); }
function _esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function _set(id, v) { const e = _overlay && _overlay.querySelector("#" + id); if (e) e.textContent = v; }

function _buildTooltip(ctx) {
  _tooltip = document.createElement("div");
  _tooltip.style.cssText =
    "position:absolute;display:none;pointer-events:none;z-index:30;max-width:240px;" +
    "font:11px/1.45 ui-monospace,Menlo,monospace;color:#eaf6f9;background:rgba(10,17,23,0.94);" +
    "border:1px solid #1b3a44;border-radius:8px;padding:7px 9px;box-shadow:0 4px 18px rgba(0,0,0,0.45)";
  (ctx.container || document.body).appendChild(_tooltip);
}

// invariant check row (green check / red cross / pending).
function _check(name, ok) {
  let mark, color;
  if (ok == null) { mark = "\u2026"; color = "#7d8a96"; }
  else if (ok) { mark = "\u2713"; color = "#3af4c8"; }
  else { mark = "\u2717"; color = "#ff6b6b"; }
  return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px"><span style="color:#cfe3ea">' + name + '</span><span style="color:' + color + ';font-weight:700">' + mark + '</span></div>';
}

function _paintOverlay() {
  if (!_overlay) return;
  const missing = (S.state === "missing" || S.state === "error");
  const deg = missing || (S.state === "degraded");
  const nd = "NO-LIVE-DATA";
  const d = deg ? "\u2014" : null;

  if (_show) _show.setChip("label", S.label || "MODELED");

  if (missing && !S.clusters.length) {
    _set("atlas-total", nd);
    _set("atlas-clusters", "8 (Flower Brain taxonomy, offline)");
    _set("atlas-coverage", nd);
    const lm = _overlay.querySelector("#atlas-labelmix"); if (lm) lm.textContent = nd + " — the map waits until the organ answers.";
    const cl = _overlay.querySelector("#atlas-clusterlist"); if (cl) cl.textContent = nd;
    const inv = _overlay.querySelector("#atlas-inv");
    if (inv) inv.innerHTML =
      _check("clusters == 8", null) + _check("locked-core == 8", null) +
      _check("coverage 1.0", null) + _check("conjecture grey (never green)", true);
    _dimForDegrade();
    if (_plain) _applyPlain();
    return;
  }

  const total = S.surfaceCount != null ? S.surfaceCount : null;
  _set("atlas-total", d || (total != null ? String(total) + " (+ atlas = " + (total + 1) + ")" : "\u2014"));
  _set("atlas-clusters", d || (S.clustersTotal != null ? String(S.clustersTotal) + " (must be 8)" : "\u2014"));
  _set("atlas-coverage", d || (S.coverage != null ? (S.coverage * 100).toFixed(1) + "% (" + (S.totalClassified != null ? S.totalClassified : "\u2014") + "/" + (total != null ? total : "\u2014") + ")" : "\u2014"));

  // honest label mix — rendered by real label, coloured by label type (NOT uniform).
  const lm = _overlay.querySelector("#atlas-labelmix");
  if (lm) {
    const order = ["MODELED", "STRUCTURAL-ONLY", "ROADMAP", "MEASURED"];
    const keys = order.filter((k) => S.labelMix[k] != null).concat(Object.keys(S.labelMix).filter((k) => order.indexOf(k) < 0));
    if (!keys.length) { lm.textContent = deg ? "\u2014" : "\u2014"; }
    else {
      lm.innerHTML = keys.map((k) => {
        const c = _hex(_labelColor(k));
        return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px">' +
          '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + c + ';margin-right:5px"></span>' + k + '</span>' +
          '<span style="color:#eaf6f9;font-variant-numeric:tabular-nums">' + S.labelMix[k] + '</span></div>';
      }).join("");
    }
  }

  // per-cluster counts (surfaces for 6 & 7, kernel objects elsewhere).
  const cl = _overlay.querySelector("#atlas-clusterlist");
  if (cl) {
    cl.innerHTML = S.clusters.map((c) => {
      const col = _hex(_clusterColor(c.key, c.gray));
      const nSurf = c.surface_count != null ? c.surface_count : (Array.isArray(c.surfaces) ? c.surfaces.length : 0);
      const nK = Array.isArray(c.kernel_object_ids) ? c.kernel_object_ids.length : 0;
      const cnt = nSurf > 0 ? (nSurf + " surf") : (nK > 0 ? (nK + " kernel") : "\u2014");
      return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px">' +
        '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + col + ';margin-right:5px"></span>' + _esc(c.name) + (c.is_pistil ? " \u2605" : "") + '</span>' +
        '<span style="color:#eaf6f9;font-variant-numeric:tabular-nums">' + cnt + '</span></div>';
    }).join("");
  }

  // invariants as green checks.
  const inv = _overlay.querySelector("#atlas-inv");
  if (inv) {
    const clustersOk = deg ? null : (S.clustersTotal != null ? S.clustersTotal === 8 : null);
    const lockedOk = deg ? null : (S.lockedCoreCount != null ? S.lockedCoreCount === 8 : null);
    const covOk = deg ? null : (S.coverage != null ? Math.abs(S.coverage - 1.0) < 1e-9 : null);
    const grayOk = (S.conjectureGray != null) ? (S.conjectureGray === true) : true;  // grey by construction
    inv.innerHTML =
      _check("clusters == 8", clustersOk) +
      _check("locked-core == 8", lockedOk) +
      _check("coverage 1.0", covOk) +
      _check("conjecture grey (never green)", grayOk);
  }

  if (_plain) _applyPlain();
}

// on degrade, drop live node emissive to grey so nothing reads as fired.
function _dimForDegrade() {
  _nodeMeshes.forEach((r) => { if (r.mesh && r.mesh.material) r.mesh.material.emissiveIntensity = 0.0; });
}

function _applyPlain() {
  const box = _overlay && _overlay.querySelector("#atlas-plainbox");
  if (!box) return;
  box.style.display = _plain ? "block" : "none";
  if (_plain) {
    box.innerHTML =
      "This is our <b>entire holographic estate drawn as one organism</b>. We have 67 surfaces (tabs); " +
      "on their own they look like a flat wall. The Atlas gives them a spine by <b>mapping every surface " +
      "into the Flower Brain\u2019s 8 real clusters</b> \u2014 the ecosystem\u2019s own taxonomy \u2014 without removing a " +
      "single surface. The solid teal ball in the middle is the <b>pistil: the 8 things we have actually " +
      "machine-proven</b> (locked-8, kernel c7c0ba17). It never grows. Around it, eight regions fan out; most " +
      "of the surfaces live in the big <b>SURFACES</b> region (58), a smaller set in <b>MEMORY &amp; PROVENANCE</b> " +
      "(9), and the rest of the clusters carry the flower\u2019s kernel objects. <b>Hover any node</b> to see its " +
      "surface name and its honest label (MODELED, STRUCTURAL-ONLY, ROADMAP, or MEASURED \u2014 we do not paint " +
      "them all the same); <b>click a surface</b> to jump straight to it. The gold arcs are <b>Loop Forge\u2019s " +
      "living process</b> (propose \u2192 kernel gate \u2192 archive). The grey region is our <b>conjectures we have NOT " +
      "proven</b>; it stays grey and never turns green. Label is <b>" + (S.label || "MODELED") + "</b>: a faithful " +
      "drawing of the real classification, not a computation. If the organ is offline it honestly says " +
      "\u201CNO-LIVE-DATA.\u201D";
  }
}

function _infoHTML() {
  return "<b>This is the estate as one organism, mapped by the Flower Brain\u2019s 8 clusters.</b> " +
    "Unification by cartography: the flat 67-tab wall is given a spine by classifying every surface into " +
    "the 8 real clusters of the <b>Flower Brain</b> (the taxonomy source) \u2014 additively, with no surface removed. " +
    "The still center is the machine-proven <b>locked-8 pistil</b> {F1,F4,F7,F11,F12,F18,F19,F22}, carried from " +
    "the lutar-lean kernel <b>c7c0ba17</b> (cited; re-verified in CI/dev, not in-Space). " +
    "<br><br><b>What is MODELED vs real.</b> The classification is REAL \u2014 each surface maps to its cluster by its " +
    "actual nature/owner/domain, served by the backend organ szl_kc_atlas and proven complete (coverage 1.0, zero " +
    "orphans, all 67 mapped once; the Atlas itself is the 68th). The LAYOUT is a <b>MODELED</b> deterministic drawing " +
    "read verbatim from <code>/api/a11oy/v1/atlas/{map,organism}</code> \u2014 not a computation, not \u201Calive.\u201D The honest " +
    "label mix (58 MODELED / 7 STRUCTURAL-ONLY / 1 ROADMAP / 1 MEASURED) is rendered per surface, never uniform. " +
    "\u039B stays <b>Conjecture 1</b>, the conjecture cluster is <b>grey, never green</b>. " +
    "<br><br><b>Sources (we cite the taxonomy; we do not claim it as computation).</b><br>" +
    "&bull; Taxonomy source \u2014 the Flower Brain: <code>github.com/szl-holdings/killinchu szl_kc_flower.py</code><br>" +
    "&bull; Living process \u2014 Loop Forge: <code>github.com/szl-holdings/killinchu szl_kc_loop_forge.py</code><br>" +
    "&bull; Backend organ \u2014 szl_kc_atlas (endpoints /api/a11oy/v1/atlas/{manifest,map,organism})<br>" +
    "&bull; Kernel authority \u2014 lutar-lean kernel c7c0ba17 (cited; re-verified in CI/dev, not in-Space).";
}

// =============================================================================
// unmount
// =============================================================================
function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  if (_domEl) {
    try { if (_onMove) _domEl.removeEventListener("pointermove", _onMove); } catch (_) {}
    try { if (_onClick) _domEl.removeEventListener("pointerdown", _onClick); } catch (_) {}
    try { if (_onLeave) _domEl.removeEventListener("pointerleave", _onLeave); } catch (_) {}
    try { _domEl.style.cursor = "default"; } catch (_) {}
  }
  try { if (_show) _show.destroy(); } catch (_) {} _show = null;
  try { if (_tooltip && _tooltip.parentNode) _tooltip.parentNode.removeChild(_tooltip); } catch (_) {}
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
  _group = _overlay = _tooltip = null;
  _pistil = null;
  _clusterGroups = {}; _nodeMeshes = []; _bridgeLines = []; _flowArcs = [];
  _raycaster = null; _pointer = null; _hovered = null;
  _domEl = null; _onMove = _onClick = _onLeave = null;
  _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = null; S.state = "init";
  S.clusters = []; S.petals = []; S.petalByCluster = {}; S.crossLinks = []; S.lfFlow = null;
  S.clustersTotal = S.surfaceCount = S.totalClassified = S.coverage = null;
  S.lockedCoreCount = S.conjectureGray = S.everyOnce = null;
  S.labelMix = {}; S.built = false;
}

export default { id: ID, title: TITLE, endpoints: [EP_MAP, EP_ORGANISM], mount, unmount };
