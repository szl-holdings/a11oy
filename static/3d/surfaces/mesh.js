// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/mesh.js — SOVEREIGN MESH ORCHESTRATION holographic surface (Wave-P Dev2).
//
// Both fleet GPU nodes rendered as lit nodes in a live mesh; edges are routing links; each
// node's glow tracks its LIVE measured watts; honest label pills read STRAIGHT off the JSON.
//
// EVERY value on screen traces to a REAL a11oy endpoint (doctrine v11 — never fabricate):
//   * /api/a11oy/v1/mesh/status   — per-node {state, reachable, models, watts, joules_label}
//        (LIVE / DEGRADED / OFFLINE state machine across omen + betterwithage)
//   * /api/a11oy/v1/mesh/route     — which node WOULD serve, cheapest-live-watt (advisory)
//   * /api/a11oy/v1/mesh/quorum    — 3-of-4 witness-quorum VIEW (CONJECTURE 2, never proven)
//
// Honest degradation: on 404 / error / degraded the badge shows NO-LIVE-DATA / DEGRADED and
// the dependent geometry greys out — no crash, no fabricated number. A node with no live
// meter reading glows at a FIXED structural dim (never a fabricated wattage). Watts drive glow
// ONLY when joules_label === "measured".
//
// 0 runtime CDN: three resolves through ctx.THREE (page importmap -> /static/3d/vendor/).

import { createShowcase } from "./_showcase.js";

const ID = "mesh";
const TITLE = "Sovereign Mesh · Cross-Node Orchestration";
const EP_STATUS = "/api/a11oy/v1/mesh/status";
const EP_ROUTE = "/api/a11oy/v1/mesh/route";
const EP_QUORUM = "/api/a11oy/v1/mesh/quorum";

// palette (estate lattice — lattice-blue / violet-blue / proof-teal / greys only)
const C_LIVE = 0x3af4c8;     // proof-teal — LIVE node
const C_DEGRADED = 0xd7b96b; // gold — DEGRADED node (up, no live meter)
const C_OFFLINE = 0x4a5a68;  // grey — OFFLINE / unreachable
const C_EDGE = 0x5b8dee;     // lattice-blue — routing edge (idle)
const C_ROUTE = 0x8a6bff;    // violet-blue — the chosen route edge
const C_DIM = 0x394654;

// =========================================================================================
// module state
// =========================================================================================
let _stage = null, _THREE = null, _ctx = null;
let _hStatus = null, _hRoute = null, _hQuorum = null;
let _show = null;
let _group = null;
let _nodeMeshes = {};        // name -> { core, halo, ring, pos }
let _edges = [];             // routing edges between node pairs
let _quorumRing = null;      // witness quorum ring of beads
let _particles = null;       // routing particles flowing along the chosen edge
let _billboard = null;
let _frameReg = false;

// live state (NEVER seeded with fake numbers — null until a real fetch lands)
const S = {
  nodes: [],                 // [{name,label,state,reachable,models,watts,joules_label}]
  meshState: null, dataLabel: null,
  route: null, routeBasis: null, routeState: "init",
  quorum: null, quorumState: "init",
  statusState: "init", degraded: false,
};

// fixed node anchors (omen left, betterwithage right; self implied at center of the mesh)
const NODE_POS = {
  omen: [-4.2, 0.6, 0],
  betterwithage: [4.2, 0.6, 0],
};
const CENTER = [0, 0.6, 0];

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);

  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 5.5, 14);
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildNodes();
  _buildEdges();
  _buildCenterHub();
  _buildQuorumRing();
  _buildParticles();
  _buildNodeLabels();

  try {
    _billboard = ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "sovereign mesh", scale: 0.6, position: [0, 5.2, 0] });
    _group.add(_billboard);
  } catch (_) {}

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  _hStatus = ctx.live.poll(EP_STATUS, 5000, _onStatus, { badge: _badge, onState: _onStatusState });
  _hRoute = ctx.live.poll(EP_ROUTE, 7000, _onRoute, { badge: _routeBadge, onState: (mt) => { S.routeState = mt.state; } });
  _hQuorum = ctx.live.poll(EP_QUORUM, 9000, _onQuorum, { badge: _quorumBadge, onState: (mt) => { S.quorumState = mt.state; } });

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(20, 20, 0x1d2a36, 0x12202b);
  grid.position.y = -0.02;
  if (grid.material) {
    const mats = Array.isArray(grid.material) ? grid.material : [grid.material];
    mats.forEach((m) => { m.transparent = true; m.opacity = 0.35; });
  }
  _group.add(grid);
}

function _buildNodes() {
  const THREE = _THREE;
  Object.keys(NODE_POS).forEach((name) => {
    const p = NODE_POS[name];
    const g = new THREE.Group();
    g.position.set(p[0], p[1], p[2]);
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.9, 1),
      new THREE.MeshStandardMaterial({ color: C_OFFLINE, emissive: C_OFFLINE, emissiveIntensity: 0.4, metalness: 0.4, roughness: 0.4 }),
    );
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(1.25, 24, 24),
      new THREE.MeshBasicMaterial({ color: C_OFFLINE, transparent: true, opacity: 0.12, side: THREE.BackSide, depthWrite: false }),
    );
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(1.4, 1.55, 40),
      new THREE.MeshBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.5, side: THREE.DoubleSide }),
    );
    ring.rotation.x = -Math.PI / 2; ring.position.y = -0.55;
    g.add(core, halo, ring);
    _group.add(g);
    _nodeMeshes[name] = { group: g, core, halo, ring, pos: p };
  });
}

function _edgeLine(a, b, color) {
  const THREE = _THREE;
  const geo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(a[0], a[1], a[2]), new THREE.Vector3(b[0], b[1], b[2])]);
  return new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }));
}

function _buildEdges() {
  // routing links: omen<->center, betterwithage<->center, omen<->betterwithage
  const pairs = [
    ["omen", CENTER, "omen-self"],
    ["betterwithage", CENTER, "betterwithage-self"],
  ];
  pairs.forEach(([name, to, id]) => {
    const line = _edgeLine(NODE_POS[name], to, C_EDGE);
    line.userData = { id, node: name };
    _group.add(line);
    _edges.push(line);
  });
  // direct node<->node link
  const direct = _edgeLine(NODE_POS.omen, NODE_POS.betterwithage, C_EDGE);
  direct.userData = { id: "direct", node: null };
  _group.add(direct);
  _edges.push(direct);
}

function _buildCenterHub() {
  const THREE = _THREE;
  const hub = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.55, 0),
    new THREE.MeshStandardMaterial({ color: C_EDGE, emissive: C_EDGE, emissiveIntensity: 0.6, metalness: 0.5, roughness: 0.35 }),
  );
  hub.position.set(CENTER[0], CENTER[1], CENTER[2]);
  hub.userData.isHub = true;
  _group.add(hub);
  _nodeMeshes.__hub = { core: hub };
}

function _buildQuorumRing() {
  // 4 witness beads arranged in a ring above the mesh — 3-of-4 BFT view (CONJECTURE 2).
  const THREE = _THREE;
  _quorumRing = new THREE.Group();
  _quorumRing.position.set(0, 3.4, 0);
  _quorumRing.beads = [];
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2;
    const bead = new THREE.Mesh(
      new THREE.SphereGeometry(0.2, 16, 16),
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.4, metalness: 0.3, roughness: 0.5 }),
    );
    bead.position.set(Math.cos(a) * 1.5, 0, Math.sin(a) * 1.5);
    _quorumRing.add(bead); _quorumRing.beads.push(bead);
  }
  _group.add(_quorumRing);
}

function _buildParticles() {
  // routing particles that flow along the chosen route edge only when a live route lands.
  const THREE = _THREE;
  const N = 60;
  const geo = new THREE.BufferGeometry();
  const posn = new Float32Array(N * 3);
  geo.setAttribute("position", new THREE.BufferAttribute(posn, 3));
  const mat = new THREE.PointsMaterial({ color: C_ROUTE, size: 0.18, transparent: true, opacity: 0.9, depthWrite: false });
  _particles = new THREE.Points(geo, mat);
  _particles.userData = { N, p: [], active: false };
  for (let i = 0; i < N; i++) _particles.userData.p.push({ t: Math.random(), speed: 0.006 + Math.random() * 0.01 });
  _particles.visible = false;
  _group.add(_particles);
}

function _buildNodeLabels() {
  const THREE = _THREE;
  try {
    const mk = (txt, pos, color) => {
      const c = document.createElement("canvas"); const x = c.getContext("2d");
      x.font = "600 30px ui-monospace,monospace"; const w = x.measureText(txt).width + 16;
      c.width = w; c.height = 40; x.font = "600 30px ui-monospace,monospace";
      x.fillStyle = color; x.textBaseline = "middle"; x.fillText(txt, 8, 22);
      const t = new THREE.CanvasTexture(c);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false }));
      sp.scale.set(0.5 * (w / 40), 0.5, 1); sp.position.set(pos[0], pos[1], pos[2]);
      _group.add(sp);
    };
    mk("omen · RTX 4060 Ti", [-4.2, -1.4, 0], "#9fb1bf");
    mk("betterwithage · RTX 5050", [4.2, -1.4, 0], "#9fb1bf");
    mk("orchestrator", [0, -1.0, 0], "#5b8dee");
  } catch (_) {}
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onStatusState(meta) {
  S.statusState = meta.state;
  if (meta.state !== "live" && meta.state !== "degraded") {
    // greyed honest state — all nodes dim, KPIs show the honest token
    Object.keys(NODE_POS).forEach((name) => _paintNode(name, null));
    _paintKPIs();
  }
}

function _onStatus(json, meta) {
  S.degraded = !!meta.degraded;
  S.dataLabel = meta.label || (json && json.data_label) || null;
  S.meshState = (json && json.mesh_state) || null;
  S.nodes = (json && Array.isArray(json.nodes)) ? json.nodes : [];

  // paint each node from its REAL state + measured watts
  Object.keys(NODE_POS).forEach((name) => {
    const n = S.nodes.find((x) => x && x.name === name) || null;
    _paintNode(name, n);
  });
  _paintEdges();

  // honesty billboard reflects the server's label verbatim
  if (_billboard && _ctx && S.dataLabel) {
    try {
      _group.remove(_billboard);
      _billboard = _ctx.label.billboard(_THREE, S.dataLabel, { text: S.meshState ? ("mesh: " + S.meshState) : "sovereign mesh", scale: 0.58, position: [0, 5.2, 0] });
      _group.add(_billboard);
    } catch (_) {}
  }
  _paintKPIs();
  _rawDump(json);
}

function _onRoute(json, meta) {
  S.routeState = meta.state;
  if (meta.state !== "live" || !json) { S.route = null; S.routeBasis = null; _paintEdges(); _paintKPIs(); return; }
  S.route = typeof json.route === "string" ? json.route : null;
  S.routeBasis = typeof json.basis === "string" ? json.basis : null;
  _paintEdges();
  _paintKPIs();
}

function _onQuorum(json, meta) {
  S.quorumState = meta.state;
  if (meta.state !== "live" || !json) { S.quorum = null; _paintQuorum(); return; }
  S.quorum = {
    reachable: typeof json.witnesses_reachable === "number" ? json.witnesses_reachable : null,
    total: typeof json.witnesses_total === "number" ? json.witnesses_total : 4,
    threshold: typeof json.threshold === "number" ? json.threshold : 3,
    wouldForm: !!json.quorum_would_form,
    witnesses: Array.isArray(json.witnesses) ? json.witnesses : [],
    conjecture: json.conjecture || null,
  };
  _paintQuorum();
  _paintKPIs();
}

// =========================================================================================
// painters — colors/glow strictly from REAL state (never a fabricated wattage)
// =========================================================================================
function _stateColor(state) {
  if (state === "LIVE") return C_LIVE;
  if (state === "DEGRADED") return C_DEGRADED;
  return C_OFFLINE;
}

function _paintNode(name, n) {
  const nm = _nodeMeshes[name];
  if (!nm) return;
  const state = n ? n.state : null;
  const col = _stateColor(state);
  nm.core.material.color.setHex(col);
  nm.core.material.emissive.setHex(col);
  nm.halo.material.color.setHex(col);
  nm.ring.material.color.setHex(state ? col : C_DIM);

  // glow tracks LIVE MEASURED watts ONLY — otherwise a fixed structural dim (never faked).
  const measured = n && n.joules_label === "measured" && typeof n.watts === "number";
  if (measured) {
    // map ~5..120 W to emissive 0.5..2.2 (a visual proxy; the NUMBER shown is the server's)
    const w = Math.max(0, n.watts);
    const e = 0.5 + Math.min(w / 60, 1) * 1.7;
    nm.core.material.emissiveIntensity = e;
    nm.halo.material.opacity = 0.12 + Math.min(w / 60, 1) * 0.18;
  } else {
    nm.core.material.emissiveIntensity = state === "LIVE" ? 0.8 : (state ? 0.5 : 0.3);
    nm.halo.material.opacity = 0.12;
  }
}

function _paintEdges() {
  const routeUp = S.routeState === "live" && S.route;
  _edges.forEach((line) => {
    const isRoute = routeUp && line.userData.node === S.route && line.userData.id !== "direct";
    line.material.color.setHex(isRoute ? C_ROUTE : C_EDGE);
    line.material.opacity = isRoute ? 0.95 : 0.4;
  });
  // particle stream flows only along a live chosen route
  if (_particles) {
    _particles.userData.active = !!(routeUp && NODE_POS[S.route]);
    _particles.visible = _particles.userData.active;
  }
}

function _paintQuorum() {
  if (!_quorumRing) return;
  const q = S.quorum;
  const live = S.quorumState === "live" && q;
  _quorumRing.beads.forEach((bead, i) => {
    let col = C_DIM, e = 0.4;
    if (live) {
      const w = q.witnesses[i];
      const reach = w ? !!w.reachable : (i < (q.reachable || 0));
      col = reach ? C_LIVE : C_OFFLINE;
      e = reach ? 1.0 : 0.35;
    }
    bead.material.color.setHex(col);
    bead.material.emissive.setHex(col);
    bead.material.emissiveIntensity = e;
  });
}

// =========================================================================================
// per-frame animation
// =========================================================================================
function _onFrame() {
  if (_quorumRing) _quorumRing.rotation.y += 0.004;
  if (_nodeMeshes.__hub && _nodeMeshes.__hub.core) _nodeMeshes.__hub.core.rotation.y += 0.01;
  // gentle node breathing
  const t = performance.now() * 0.002;
  Object.keys(NODE_POS).forEach((name, i) => {
    const nm = _nodeMeshes[name];
    if (nm && nm.halo) { const s = 1 + 0.04 * Math.sin(t + i); nm.halo.scale.set(s, s, s); }
  });
  // routing particles along the chosen edge (center <-> chosen node)
  if (_particles && _particles.userData.active) {
    const to = NODE_POS[S.route];
    if (to) {
      const posn = _particles.geometry.attributes.position, p = _particles.userData.p;
      for (let i = 0; i < p.length; i++) {
        p[i].t += p[i].speed; if (p[i].t >= 1) p[i].t -= 1;
        const tt = p[i].t;
        posn.setXYZ(i,
          CENTER[0] * (1 - tt) + to[0] * tt,
          CENTER[1] * (1 - tt) + to[1] * tt + Math.sin(tt * Math.PI) * 0.4,
          CENTER[2] * (1 - tt) + to[2] * tt);
      }
      posn.needsUpdate = true;
    }
  }
}

// =========================================================================================
// DOM overlay (HUD): badges, KPIs, raw JSON, honesty legend, sources
// =========================================================================================
let _badge = null, _routeBadge = null, _quorumBadge = null;
let _el = {};

function _buildOverlay() {
  const ctx = _ctx;
  _badge = ctx.live.createBadge();
  _routeBadge = ctx.live.createBadge();
  _quorumBadge = ctx.live.createBadge();

  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "STRUCTURAL-ONLY", text: "mesh status", name: "lbl" }],
    description:
      'Both sovereign GPU nodes as a LIVE mesh: ' +
      '<span style="color:#3af4c8">LIVE</span> (models + live watts), ' +
      '<span style="color:#d7b96b">DEGRADED</span> (models up, no live meter), ' +
      '<span style="color:#9fb1bf">OFFLINE</span> (unreachable). Node glow tracks MEASURED watts; ' +
      'the <span style="color:#8a6bff">violet</span> edge is the cheapest-live-watt route (advisory).',
    citations:
      "Grounded in SZL org libs — szl-router (own-GPU-first + receipts) · szl-mesh (CRDT/DSSE/BFT) · " +
      "khipu-consensus (BFT 3-of-4; safety = Conjecture 2). Routing is ADVISORY (Λ = Conjecture 1, trust ≤ 0.97); " +
      "MEASURED watts only from a live NVML reading this request; never a fabricated dispatch or proven consensus.",
  });

  const host = _show.body;

  // secondary badge row (route + quorum) folded into the body
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#5b8dee"; return s; };
  badgeRow.appendChild(tag("route")); badgeRow.appendChild(_routeBadge.el);
  badgeRow.appendChild(tag("quorum")); badgeRow.appendChild(_quorumBadge.el);
  host.appendChild(badgeRow);

  // full doctrine legend (all 4 chips)
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; host.appendChild(lg);

  // KPIs
  const kpi = document.createElement("div");
  kpi.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:2px";
  const cell = (id, label, color) => {
    const d = document.createElement("div");
    d.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:7px;padding:7px 9px";
    const b = document.createElement("b"); b.id = "k-" + id;
    b.style.cssText = "display:block;font-size:15px;font-variant-numeric:tabular-nums;color:" + (color || "#d7b96b");
    b.textContent = "—";
    const s = document.createElement("span"); s.style.cssText = "font-size:10.5px;color:#9fb1bf"; s.textContent = label;
    d.appendChild(b); d.appendChild(s); _el[id] = b; return d;
  };
  kpi.appendChild(cell("mesh", "mesh state", "#3af4c8"));
  kpi.appendChild(cell("route", "cheapest-watt route", "#8a6bff"));
  kpi.appendChild(cell("omenw", "omen watts", "#3af4c8"));
  kpi.appendChild(cell("bwaw", "betterwithage watts", "#3af4c8"));
  kpi.appendChild(cell("quorum", "witness quorum (BFT · C2)", "#d7b96b"));
  kpi.appendChild(cell("basis", "route basis", "#5b8dee"));
  host.appendChild(kpi);

  // per-node models line
  _el.models = document.createElement("div");
  _el.models.style.cssText = "font-size:10.5px;color:#9fb1bf;line-height:1.5";
  _el.models.textContent = "models: awaiting live mesh status";
  host.appendChild(_el.models);

  // raw dump (collapsible)
  const det = document.createElement("details");
  det.style.cssText = "margin-top:2px";
  const sum = document.createElement("summary");
  sum.style.cssText = "cursor:pointer;color:#3af4c8;font:11px ui-monospace,monospace";
  sum.textContent = "raw /mesh/status";
  _el.raw = document.createElement("div");
  _el.raw.style.cssText = "white-space:pre-wrap;font:10.5px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;max-height:150px;overflow:auto;margin-top:6px";
  _el.raw.textContent = "—";
  det.appendChild(sum); det.appendChild(_el.raw);
  host.appendChild(det);
}

function _nodeByName(name) { return S.nodes.find((x) => x && x.name === name) || null; }

function _wattsText(n) {
  if (!n) return "—";
  if (n.joules_label === "measured" && typeof n.watts === "number") return n.watts.toFixed(1) + " W";
  if (n.state === "OFFLINE" || !n.reachable) return "OFFLINE";
  return "no-live-meter";
}

function _paintKPIs() {
  const live = S.statusState === "live";
  const dash = "—";
  const meshTxt = S.meshState ? S.meshState : (live ? dash : (S.statusState === "missing" ? "NO-LIVE-DATA" : S.statusState.toUpperCase()));
  _el.mesh && (_el.mesh.textContent = meshTxt);
  _el.route && (_el.route.textContent = S.route ? S.route : (S.routeState === "missing" ? "NO-LIVE-DATA" : dash));
  _el.basis && (_el.basis.textContent = S.routeBasis || dash);
  _el.omenw && (_el.omenw.textContent = _wattsText(_nodeByName("omen")));
  _el.bwaw && (_el.bwaw.textContent = _wattsText(_nodeByName("betterwithage")));
  if (_el.quorum) {
    if (S.quorum && typeof S.quorum.reachable === "number") {
      _el.quorum.textContent = S.quorum.reachable + "/" + S.quorum.total + (S.quorum.wouldForm ? " ✓" : " ✗");
    } else {
      _el.quorum.textContent = S.quorumState === "missing" ? "NO-LIVE-DATA" : dash;
    }
  }
  if (_show) {
    try { _show.setChip("lbl", S.dataLabel || "STRUCTURAL-ONLY", { text: S.meshState ? ("mesh: " + S.meshState) : "mesh status" }); } catch (_) {}
  }
  if (_el.models) {
    if (S.nodes.length) {
      _el.models.textContent = S.nodes.map((n) =>
        (n.name || "?") + ": " + (n.state || "?") + " · " + (Array.isArray(n.models) ? n.models.length : 0) + " model(s)").join("   ·   ");
    } else if (live) {
      _el.models.textContent = "models: mesh reachable but no node reported models this request";
    }
  }
}

function _rawDump(json) {
  if (_el.raw) { try { _el.raw.textContent = JSON.stringify(json, null, 1); } catch (_) {} }
}

// =========================================================================================
// unmount — stop every poll, free everything we added
// =========================================================================================
function unmount() {
  try { if (_hStatus) _hStatus.stop(); } catch (_) {}
  try { if (_hRoute) _hRoute.stop(); } catch (_) {}
  try { if (_hQuorum) _hQuorum.stop(); } catch (_) {}
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach((m) => { if (m.map && m.map.dispose) m.map.dispose(); if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _hStatus = _hRoute = _hQuorum = null;
  _show = _group = _billboard = _quorumRing = _particles = null;
  _nodeMeshes = {}; _edges = [];
  _el = {}; _badge = _routeBadge = _quorumBadge = null;
  S.nodes = []; S.route = S.routeBasis = S.quorum = S.meshState = S.dataLabel = null;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_STATUS, EP_ROUTE, EP_QUORUM], mount, unmount };
