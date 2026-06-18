// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/router.js — MODEL ROUTER / Inference Economics holographic surface (Dev7).
//
// Leader/technique modeled (NOT claimed-as): OpenRouter "State of AI" + RouteLLM
//   (UC Berkeley / LMSYS). Technique: 3D cost-quality crossover surface + model
//   embedding scatter + routing-decision particle stream + latency/cost waterfall.
//
// EVERY value on screen traces to a REAL a11oy endpoint (doctrine v11 — never fabricate):
//   * /api/a11oy/v1/router/active-flux-crossover        — live route / regime /
//        crossover_difficulty / small-vs-large weights for the current query
//   * /api/a11oy/v1/router/active-flux-crossover/sweep   — the full crossover curve
//        (small/local vs large/cloud weight over query difficulty 0→1)
//   * /api/a11oy/v1/compute-pool-hardened                — the REAL sovereign model
//        list (qwen/llama/deepseek/mistral on rtx-betterwithage + chaski) for the scatter
//        (egress-scrubbed: private node addresses stripped; models[] honest when present)
//
// The crossover is MODELED (a deterministic active-flux PI-bandwidth routing law, the
// complement to a RouteLLM Thompson-sampling bandit) — the honesty label is read STRAIGHT
// from the JSON (data_label) and rendered as a 3D billboard chip + DOM chips. The surface
// geometry mirrors the SAME closed-form blend the server computes so the warp tracks the
// live crossover_difficulty exactly; the displayed routing decision is always the server's.
//
// Degrades gracefully: if an endpoint 404s / errors / returns degraded, the badge shows the
// honest NO-LIVE-DATA / DEGRADED state and the dependent geometry greys out — no crash, no
// fabricated number. The compute-pool scatter falls back to a STRUCTURAL-ONLY honest note if
// the live node list has no models[] field.
//
// 0 runtime CDN: three resolves through the page importmap to /static/3d/vendor/.

const ID = "router";
const TITLE = "Model Router · Inference Economics";
const EP_CROSS = "/api/a11oy/v1/router/active-flux-crossover";
const EP_SWEEP = "/api/a11oy/v1/router/active-flux-crossover/sweep";
const EP_POOL = "/api/a11oy/v1/compute-pool-hardened";

// palette (matches the estate)
const C_SMALL = 0x6fb1ff;   // small/local — easy / low-"frequency"
const C_LARGE = 0xffb56b;   // large/cloud — hard / high-"frequency"
const C_TEAL = 0x39d3c4;    // crossover / live
const C_GOLD = 0xe8c074;    // current query / MODELED
const C_DIM = 0x4a5a68;

// crossover difficulty span (server maps d∈[0,1] -> f = d·SPAN Hz; mirrored here ONLY to
// shape geometry — every shown VALUE is the server's, this never overrides a live number).
const SPAN_HZ = 60.0;
const REF_CONST = 150.0;

// ---- closed-form blend, byte-faithful to szl_cuas_formulas.active_flux_blend -----------
function crossoverFreq(bw) { return REF_CONST / Math.max(bw, 1e-6); }
function blend(bw, f) {
  const wx = 2 * Math.PI * crossoverFreq(bw);
  const we = 2 * Math.PI * Math.max(f, 0);
  const d = Math.sqrt(wx * wx + we * we) || 1e-12;
  return { hc: wx / d, hv: we / d };            // hc = small/local weight, hv = large/cloud
}
function crossoverDifficulty(bw) { return crossoverFreq(bw) / SPAN_HZ; } // d at which routing flips

// =========================================================================================
// module state
// =========================================================================================
let _stage = null, _THREE = null, _ctx = null;
let _hCross = null, _hSweep = null, _hPool = null;
let _overlay = null, _panel = null;
let _group = null;                 // everything we add to the scene
let _surface = null;               // the warped cost-quality plane
let _surfaceBaseY = null;          // base positions for re-warp
let _ridge = null;                 // crossover ridge line on the surface
let _queryPlane = null;            // vertical plane at the current query difficulty
let _crossoverMarker = null;       // the live crossover point bead + halo
let _sweepRibbon = null;           // sweep curve as a 3D ribbon
let _scatter = null;               // model-capability instanced scatter
let _scatterLabels = [];
let _particles = null;             // routing-decision particle stream
let _waterfall = null;             // latency/cost waterfall columns
let _regimeZones = null;           // easy/hard color floor zones
let _billboard = null;
let _frameReg = false;

// live state (NEVER seeded with fake numbers — null until a real fetch lands)
const S = {
  bw: 12.0, qd: 0.5,
  route: null, regime: null, crossoverDifficulty: null,
  wSmall: null, wLarge: null, label: null, modelsMeta: null,
  sweep: null, pool: null, poolLabel: null,
  crossState: "init", sweepState: "init", poolState: "init",
  degraded: false,
};

const SURF_NX = 56, SURF_NZ = 40;  // surface resolution

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);

  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 7.5, 17);
  try { _stage.setBloom(true); } catch (_) {}

  _buildRegimeZones();
  _buildSurface();
  _buildRidge();
  _buildQueryPlane();
  _buildCrossoverMarker();
  _buildSweepRibbon();
  _buildScatter();
  _buildParticles();
  _buildWaterfall();
  _buildLawOverlay();
  _buildFlipBeacon();
  _buildAxesLabels();

  try {
    _billboard = ctx.label.billboard(THREE, "MODELED", { text: "routing crossover", scale: 0.62, position: [0, 6.4, 0] });
    _group.add(_billboard);
  } catch (_) {}

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  _hCross = ctx.live.poll(_crossUrl(), 4000, _onCross, { badge: _badge, onState: _onCrossState });
  _hSweep = ctx.live.poll(_sweepUrl(), 6000, _onSweep, { badge: _sweepBadge, onState: (mt) => { S.sweepState = mt.state; } });
  _hPool = ctx.live.poll(EP_POOL, 9000, _onPool, { badge: _poolBadge, onState: (mt) => { S.poolState = mt.state; } });

  return { id: ID, started: true };
}

function _crossUrl() { return `${EP_CROSS}?query_difficulty=${S.qd.toFixed(3)}&bw=${S.bw.toFixed(2)}`; }
function _sweepUrl() { return `${EP_SWEEP}?bw=${S.bw.toFixed(2)}&points=61`; }

// =========================================================================================
// scene builders
// =========================================================================================
const SURF_W = 14, SURF_D = 10, SURF_Y0 = 0;

function _buildRegimeZones() {
  // DEMO: regime color floor zones — easy (small/local) vs hard (large/cloud) split at the
  // live crossover difficulty. Two translucent quads under the surface, repositioned on data.
  const THREE = _THREE;
  _regimeZones = new THREE.Group();
  const mkZone = (color) => {
    const g = new THREE.PlaneGeometry(1, SURF_D);
    const m = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false });
    const mesh = new THREE.Mesh(g, m);
    mesh.rotation.x = -Math.PI / 2; mesh.position.y = SURF_Y0 - 0.02;
    return mesh;
  };
  _regimeZones.easy = mkZone(C_SMALL);
  _regimeZones.hard = mkZone(C_LARGE);
  _regimeZones.add(_regimeZones.easy, _regimeZones.hard);
  _group.add(_regimeZones);
}

function _buildSurface() {
  // DEMO (the key viz): 3D cost-quality crossover surface. x = query difficulty (0→1),
  // z = π-bandwidth axis (informational depth band), y = large/cloud routing weight (cost
  // proxy). Vertex colors = small (blue) vs large (orange) dominance. Warps live as the
  // bandwidth/difficulty change. Mirrors the server's closed-form blend exactly.
  const THREE = _THREE;
  const geo = new THREE.PlaneGeometry(SURF_W, SURF_D, SURF_NX - 1, SURF_NZ - 1);
  geo.rotateX(-Math.PI / 2);
  const colors = new Float32Array(geo.attributes.position.count * 3);
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true, metalness: 0.25, roughness: 0.5,
    emissive: 0x0a141c, emissiveIntensity: 0.6,
    side: THREE.DoubleSide, transparent: true, opacity: 0.96, flatShading: false,
  });
  _surface = new THREE.Mesh(geo, mat);
  _group.add(_surface);

  // wireframe overlay for the holographic grid look
  const wf = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x16313c, wireframe: true, transparent: true, opacity: 0.35 }));
  _surface.add(wf);

  _surfaceBaseY = new Float32Array(geo.attributes.position.count);
  _warpSurface();  // initial shape from the mirrored law (greyed until live confirms)
}

function _warpSurface() {
  // Recompute surface heights/colors from the current bw across a small bandwidth band so
  // the z-axis shows how the crossover ridge moves with π-bandwidth. PURE geometry from the
  // closed-form law (NOT a fabricated telemetry value — the displayed numbers stay server-fed).
  if (!_surface) return;
  const pos = _surface.geometry.attributes.position;
  const col = _surface.geometry.attributes.color;
  const live = S.crossState === "live" && !S.degraded;
  for (let iz = 0; iz < SURF_NZ; iz++) {
    // map z row to a bandwidth band around the live bw (±55%) so the ridge sweeps in depth
    const tz = iz / (SURF_NZ - 1);
    const bwRow = S.bw * (0.45 + 0.9 * tz);
    for (let ix = 0; ix < SURF_NX; ix++) {
      const d = ix / (SURF_NX - 1);
      const b = blend(bwRow, d * SPAN_HZ);
      const idx = iz * SURF_NX + ix;
      const h = b.hv * 4.2;            // large/cloud weight as height (cost proxy)
      pos.setY(idx, h);
      _surfaceBaseY[idx] = h;
      // color: blue where small dominates, orange where large dominates, teal at the ridge
      const mix = b.hv; // 0..1 toward large
      let r, g, bl;
      const near = Math.abs(b.hc - b.hv) < 0.04;
      if (near) { r = 0.22; g = 0.83; bl = 0.77; }   // teal ridge
      else {
        r = 0.43 * (1 - mix) + 1.0 * mix;
        g = 0.69 * (1 - mix) + 0.71 * mix;
        bl = 1.0 * (1 - mix) + 0.42 * mix;
      }
      const dim = live ? 1.0 : 0.4;
      col.setXYZ(idx, r * dim, g * dim, bl * dim);
    }
  }
  pos.needsUpdate = true; col.needsUpdate = true;
  _surface.geometry.computeVertexNormals();
}

function _buildRidge() {
  // DEMO: live crossover RIDGE — the locus where small/local weight == large/cloud weight,
  // drawn as a glowing teal line laid on the surface. This is the "flip" the router makes.
  const THREE = _THREE;
  const pts = [];
  for (let iz = 0; iz < SURF_NZ; iz++) pts.push(new THREE.Vector3(0, 0, 0));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  _ridge = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_TEAL, transparent: true, opacity: 0.95 }));
  _group.add(_ridge);
  _updateRidge();
}

function _updateRidge() {
  if (!_ridge) return;
  const arr = _ridge.geometry.attributes.position;
  for (let iz = 0; iz < SURF_NZ; iz++) {
    const tz = iz / (SURF_NZ - 1);
    const bwRow = S.bw * (0.45 + 0.9 * tz);
    const cd = Math.min(crossoverDifficulty(bwRow), 1);   // difficulty where flip happens
    const x = (cd - 0.5) * SURF_W;
    const z = (tz - 0.5) * SURF_D;
    const h = blend(bwRow, cd * SPAN_HZ).hv * 4.2 + 0.05;
    arr.setXYZ(iz, x, h, z);
  }
  arr.needsUpdate = true;
}

function _buildQueryPlane() {
  // DEMO: query-difficulty slider plane — a gold vertical sheet at the current query's x,
  // sliced through the surface, showing exactly where THIS query sits on the cost curve.
  const THREE = _THREE;
  const g = new THREE.PlaneGeometry(SURF_D, 5);
  const m = new THREE.MeshBasicMaterial({ color: C_GOLD, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false });
  _queryPlane = new THREE.Mesh(g, m);
  _queryPlane.rotation.y = Math.PI / 2;
  _group.add(_queryPlane);
  _updateQueryPlane();
}

function _updateQueryPlane() {
  if (!_queryPlane) return;
  _queryPlane.position.set((S.qd - 0.5) * SURF_W, 2.4, 0);
}

function _buildCrossoverMarker() {
  // DEMO: live crossover POINT — a bead + pulsing halo sitting at the live crossover_difficulty
  // (read from the endpoint, not computed). The halo color tracks the live regime.
  const THREE = _THREE;
  _crossoverMarker = new THREE.Group();
  const bead = new THREE.Mesh(new THREE.SphereGeometry(0.22, 20, 20),
    new THREE.MeshStandardMaterial({ color: C_TEAL, emissive: C_TEAL, emissiveIntensity: 1.1 }));
  const halo = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.42, 32),
    new THREE.MeshBasicMaterial({ color: C_TEAL, transparent: true, opacity: 0.6, side: THREE.DoubleSide }));
  halo.rotation.x = -Math.PI / 2;
  _crossoverMarker.bead = bead; _crossoverMarker.halo = halo;
  _crossoverMarker.add(bead, halo);
  _group.add(_crossoverMarker);
}

function _buildSweepRibbon() {
  // DEMO: sweep curve ribbon — the /sweep endpoint's full small-vs-large weight curve over
  // difficulty, rendered as a floating ribbon behind the surface. Lights up only with live data.
  const THREE = _THREE;
  _sweepRibbon = new THREE.Group();
  const mkLine = (color) => {
    const pts = [];
    for (let i = 0; i < 61; i++) pts.push(new THREE.Vector3(0, 0, 0));
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    return new THREE.Line(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
  };
  _sweepRibbon.small = mkLine(C_SMALL);
  _sweepRibbon.large = mkLine(C_LARGE);
  _sweepRibbon.position.set(0, 0.1, -SURF_D / 2 - 1.6);
  _sweepRibbon.add(_sweepRibbon.small, _sweepRibbon.large);
  _sweepRibbon.visible = false;
  _group.add(_sweepRibbon);
}

function _buildScatter() {
  // DEMO: model-capability scatter — the REAL sovereign models from /compute-pool, placed in a
  // 2D capability embedding (size proxy on x, locality on z) as an instanced scatter. Built
  // lazily when the live node list arrives; honest STRUCTURAL-ONLY note if models[] absent.
  const THREE = _THREE;
  _scatter = new THREE.Group();
  _scatter.position.set(0, 0.2, SURF_D / 2 + 2.4);
  _group.add(_scatter);
}

function _buildParticles() {
  // DEMO: routing-decision particle STREAM — each particle is a query flowing across the cost
  // surface toward small/local (blue) or large/cloud (orange) per the LIVE route. The split of
  // blue:orange particles tracks the live small:large weights (so the stream IS the decision).
  const THREE = _THREE;
  const N = 220;
  const geo = new THREE.BufferGeometry();
  const posn = new Float32Array(N * 3);
  const colr = new Float32Array(N * 3);
  geo.setAttribute("position", new THREE.BufferAttribute(posn, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colr, 3));
  const mat = new THREE.PointsMaterial({ size: 0.16, vertexColors: true, transparent: true, opacity: 0.92, depthWrite: false });
  _particles = new THREE.Points(geo, mat);
  _particles.userData.N = N;
  _particles.userData.p = [];
  for (let i = 0; i < N; i++) _particles.userData.p.push(_spawnParticle(i));
  _group.add(_particles);
}

function _spawnParticle(i) {
  // a query enters at high z (incoming) with a random difficulty, routes to its model lane
  const large = Math.random() < (S.wLarge != null ? S.wLarge : 0.5);
  const d = Math.random();
  return {
    d, large,
    t: Math.random(),
    speed: 0.004 + Math.random() * 0.006,
    z0: SURF_D / 2 + 2.0,
  };
}

function _buildWaterfall() {
  // DEMO: latency / cost WATERFALL — three stacked columns (queue → prefill → decode) per
  // tier, height encodes the modeled relative cost of the dominant route. Small/local is cheap
  // & shallow; large/cloud is tall. Re-heights live from the server weights. Modeled proxy,
  // labeled as such (no fabricated millisecond meter — these are routing-weight proportions).
  const THREE = _THREE;
  _waterfall = new THREE.Group();
  _waterfall.position.set(-SURF_W / 2 - 2.6, 0, 0);
  const stages = ["queue", "prefill", "decode"];
  _waterfall.cols = [];
  for (let lane = 0; lane < 2; lane++) {       // lane0 small/local, lane1 large/cloud
    for (let s = 0; s < stages.length; s++) {
      const m = new THREE.MeshStandardMaterial({
        color: lane === 0 ? C_SMALL : C_LARGE,
        emissive: lane === 0 ? C_SMALL : C_LARGE, emissiveIntensity: 0.25,
        metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.85,
      });
      const box = new THREE.Mesh(new THREE.BoxGeometry(0.7, 1, 0.7), m);
      box.position.set(lane * 1.1, 0.5, (s - 1) * 1.0);
      box.userData = { lane, stage: s };
      _waterfall.add(box); _waterfall.cols.push(box);
    }
  }
  _group.add(_waterfall);
}

let _lawOverlay = null;
function _buildLawOverlay() {
  // DEMO: active-flux LAW OVERLAY — the H_c (small) / H_v (large) complementary blend as a
  // floating mini Bode-style curve (the actual textbook active-flux hand-off shape the router
  // generalizes). Sits to the right of the surface; re-draws on bandwidth change.
  const THREE = _THREE;
  _lawOverlay = new THREE.Group();
  _lawOverlay.position.set(SURF_W / 2 + 2.8, 2.2, 0);
  const mk = (color) => {
    const pts = []; for (let i = 0; i < 48; i++) pts.push(new THREE.Vector3(0, 0, 0));
    return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
  };
  _lawOverlay.hc = mk(C_SMALL); _lawOverlay.hv = mk(C_LARGE);
  _lawOverlay.add(_lawOverlay.hc, _lawOverlay.hv);
  _group.add(_lawOverlay);
  _updateLawOverlay();
}
function _updateLawOverlay() {
  if (!_lawOverlay) return;
  const hcP = _lawOverlay.hc.geometry.attributes.position;
  const hvP = _lawOverlay.hv.geometry.attributes.position;
  for (let i = 0; i < 48; i++) {
    const d = i / 47;
    const b = blend(S.bw, d * SPAN_HZ);
    const x = (d - 0.5) * 3.4;
    hcP.setXYZ(i, x, b.hc * 2.6 - 1.3, 0);
    hvP.setXYZ(i, x, b.hv * 2.6 - 1.3, 0);
  }
  hcP.needsUpdate = true; hvP.needsUpdate = true;
}

let _flipBeacon = null;
function _buildFlipBeacon() {
  // DEMO: regime-FLIP beacon — a cone that points at the dominant tier and recolors blue↔orange
  // the instant the LIVE route flips small/local ↔ large/cloud (the router's decision, made visible).
  const THREE = _THREE;
  _flipBeacon = new THREE.Mesh(
    new THREE.ConeGeometry(0.5, 1.1, 18),
    new THREE.MeshStandardMaterial({ color: C_SMALL, emissive: C_SMALL, emissiveIntensity: 0.8, metalness: 0.3, roughness: 0.4 }),
  );
  _flipBeacon.position.set(0, 5.4, 0);
  _group.add(_flipBeacon);
}
function _updateFlipBeacon() {
  if (!_flipBeacon) return;
  const large = S.route === "large/cloud";
  const live = S.crossState === "live" && !S.degraded;
  const col = !live ? C_DIM : (large ? C_LARGE : C_SMALL);
  _flipBeacon.material.color.setHex(col);
  _flipBeacon.material.emissive.setHex(col);
  _flipBeacon.rotation.z = large ? Math.PI : 0;   // point toward the dominant lane
}

function _buildAxesLabels() {
  // axis billboards so the surface is readable (these are labels, not data values)
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
    mk("easy →  query difficulty  → hard", [0, -0.4, SURF_D / 2 + 0.8], "#9fb1bf");
    mk("small/local", [-SURF_W / 2 - 0.4, 0.4, SURF_D / 2 + 0.8], "#6fb1ff");
    mk("large/cloud", [SURF_W / 2 - 1.6, 4.4, SURF_D / 2 + 0.8], "#ffb56b");
  } catch (_) {}
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onCrossState(meta) {
  S.crossState = meta.state;
  S.label = meta.label || S.label;
  if (meta.state !== "live" && meta.state !== "degraded") {
    // greyed honest state — warp dims, KPIs show the honest token
    _warpSurface();
    _paintKPIs();
  }
}

function _onCross(json, meta) {
  S.degraded = !!meta.degraded;
  S.label = meta.label || json.data_label || json.status || null;
  if (typeof json.route === "string") S.route = json.route;
  if (typeof json.regime === "string") S.regime = json.regime;
  if (typeof json.crossover_difficulty === "number") S.crossoverDifficulty = json.crossover_difficulty;
  if (typeof json.weight_small_local === "number") S.wSmall = json.weight_small_local;
  if (typeof json.weight_large_cloud === "number") S.wLarge = json.weight_large_cloud;
  if (json.models) S.modelsMeta = json.models;

  // honesty billboard reflects the server's label verbatim
  if (_billboard && _ctx && S.label) {
    try {
      _group.remove(_billboard);
      _billboard = _ctx.label.billboard(_THREE, S.label, { text: S.route ? ("route: " + S.route) : "routing crossover", scale: 0.6, position: [0, 6.4, 0] });
      _group.add(_billboard);
    } catch (_) {}
  }

  _warpSurface();
  _updateRidge();
  _updateRegimeZones();
  _updateCrossoverMarker();
  _updateWaterfall();
  _updateLawOverlay();
  _updateFlipBeacon();
  _paintKPIs();
  _rawDump(json);
}

function _onSweep(json, meta) {
  if (meta.state !== "live") { if (_sweepRibbon) _sweepRibbon.visible = false; return; }
  if (!json || !Array.isArray(json.curve)) { if (_sweepRibbon) _sweepRibbon.visible = false; return; }
  S.sweep = json.curve;
  _updateSweepRibbon(json.curve);
}

function _onPool(json, meta) {
  S.poolState = meta.state;
  S.poolLabel = meta.label || (json && json.status) || null;
  if (meta.state !== "live" || !json) { _renderScatter(null); return; }
  S.pool = json;
  // extract REAL model list from live nodes[].models[] (sovereign models on the GPU nodes)
  const models = [];
  const nodes = Array.isArray(json.nodes) ? json.nodes : [];
  nodes.forEach((n) => {
    const ms = Array.isArray(n.models) ? n.models : [];
    ms.forEach((mn) => models.push({
      name: String(mn), node: n.name, sovereign: !!n.sovereign,
      gpu: /gpu/i.test(String(n.kind || "")),
    }));
  });
  _renderScatter(models.length ? models : null, json);
}

// =========================================================================================
// live updaters
// =========================================================================================
function _updateRegimeZones() {
  if (!_regimeZones) return;
  const cd = S.crossoverDifficulty != null ? S.crossoverDifficulty : crossoverDifficulty(S.bw);
  const cdc = Math.min(Math.max(cd, 0), 1);
  const easyW = cdc * SURF_W, hardW = (1 - cdc) * SURF_W;
  _regimeZones.easy.scale.x = Math.max(easyW, 1e-3);
  _regimeZones.easy.position.x = -SURF_W / 2 + easyW / 2;
  _regimeZones.hard.scale.x = Math.max(hardW, 1e-3);
  _regimeZones.hard.position.x = SURF_W / 2 - hardW / 2;
  const liveEasy = S.route === "small/local", liveHard = S.route === "large/cloud";
  _regimeZones.easy.material.opacity = liveEasy ? 0.18 : 0.07;
  _regimeZones.hard.material.opacity = liveHard ? 0.18 : 0.07;
}

function _updateCrossoverMarker() {
  if (!_crossoverMarker) return;
  const cd = S.crossoverDifficulty != null ? S.crossoverDifficulty : crossoverDifficulty(S.bw);
  const cdc = Math.min(Math.max(cd, 0), 1);
  const x = (cdc - 0.5) * SURF_W;
  const h = blend(S.bw, cdc * SPAN_HZ).hv * 4.2;
  _crossoverMarker.position.set(x, h + 0.1, 0);
  const live = S.crossState === "live" && !S.degraded;
  const col = live ? C_TEAL : C_DIM;
  _crossoverMarker.bead.material.color.setHex(col);
  _crossoverMarker.bead.material.emissive.setHex(col);
  _crossoverMarker.halo.material.color.setHex(col);
}

function _updateSweepRibbon(curve) {
  if (!_sweepRibbon) return;
  const n = curve.length;
  const small = _sweepRibbon.small.geometry.attributes.position;
  const large = _sweepRibbon.large.geometry.attributes.position;
  // resize buffers if the server returned a different point count
  if (small.count !== n) {
    _sweepRibbon.small.geometry.setFromPoints(curve.map(() => new _THREE.Vector3()));
    _sweepRibbon.large.geometry.setFromPoints(curve.map(() => new _THREE.Vector3()));
  }
  const sp = _sweepRibbon.small.geometry.attributes.position;
  const lp = _sweepRibbon.large.geometry.attributes.position;
  for (let i = 0; i < n; i++) {
    const d = typeof curve[i].difficulty === "number" ? curve[i].difficulty : i / (n - 1);
    const ws = typeof curve[i].small_local === "number" ? curve[i].small_local : 0;
    const wl = typeof curve[i].large_cloud === "number" ? curve[i].large_cloud : 0;
    const x = (d - 0.5) * SURF_W;
    sp.setXYZ(i, x, ws * 4.2 + 0.05, 0);
    lp.setXYZ(i, x, wl * 4.2 + 0.05, 0);
  }
  sp.needsUpdate = true; lp.needsUpdate = true;
  _sweepRibbon.visible = true;
}

function _updateWaterfall() {
  if (!_waterfall) return;
  const ws = S.wSmall != null ? S.wSmall : 0.5;
  const wl = S.wLarge != null ? S.wLarge : 0.5;
  // modeled relative cost proxy per stage (queue<prefill<decode), scaled by route weight
  const stageScale = [0.5, 1.2, 2.4];
  _waterfall.cols.forEach((box) => {
    const w = box.userData.lane === 0 ? ws : wl;
    const baseTier = box.userData.lane === 0 ? 0.6 : 1.6;  // large/cloud intrinsically costlier
    const h = Math.max(0.08, w * baseTier * stageScale[box.userData.stage]);
    box.scale.y = h; box.position.y = h / 2;
    const live = S.crossState === "live" && !S.degraded;
    box.material.opacity = live ? 0.9 : 0.35;
  });
}

function _renderScatter(models, poolJson) {
  // (re)build the instanced scatter from the REAL live model list
  const THREE = _THREE;
  // clear old
  _scatterLabels.forEach((l) => { try { _scatter.remove(l); } catch (_) {} });
  _scatterLabels = [];
  for (let i = _scatter.children.length - 1; i >= 0; i--) _scatter.remove(_scatter.children[i]);

  if (!models) {
    // honest STRUCTURAL-ONLY note — no fabricated scatter
    try {
      const note = _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "model scatter · awaiting live compute-pool models[]", scale: 0.5, position: [0, 1.4, 0] });
      _scatter.add(note); _scatterLabels.push(note);
    } catch (_) {}
    return;
  }

  // place models in a simple capability embedding:
  //  x ← inferred size rank (parse "Nb" param hint from the name when present)
  //  z ← locality (sovereign GPU front, hosted back)
  //  y ← small lift for the GPU-resident sovereign models
  const sizeOf = (nm) => {
    const m = /(\d+(?:\.\d+)?)\s*b/i.exec(nm);
    return m ? parseFloat(m[1]) : 4;     // default mid if unparseable
  };
  const maxB = Math.max(8, ...models.map((m) => sizeOf(m.name)));
  models.forEach((mo, i) => {
    const b = sizeOf(mo.name);
    const x = (b / maxB - 0.5) * 9;             // small ← → large
    const z = (mo.sovereign ? -1 : 1) * 1.6 + (i % 3 - 1) * 0.5;
    const y = (mo.gpu ? 0.8 : 0.2) + (i % 2) * 0.3;
    const col = b / maxB > 0.5 ? C_LARGE : C_SMALL;
    const node = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.22 + 0.12 * (b / maxB), 0),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.5, metalness: 0.4, roughness: 0.4 }),
    );
    node.position.set(x, y, z);
    _scatter.add(node);
    // tiny name label
    try {
      const c = document.createElement("canvas"); const cx = c.getContext("2d");
      cx.font = "600 26px ui-monospace,monospace";
      const txt = mo.name.length > 22 ? mo.name.slice(0, 21) + "…" : mo.name;
      const w = cx.measureText(txt).width + 12; c.width = w; c.height = 34;
      cx.font = "600 26px ui-monospace,monospace"; cx.fillStyle = mo.sovereign ? "#2fd07a" : "#9fb1bf";
      cx.textBaseline = "middle"; cx.fillText(txt, 6, 18);
      const t = new THREE.CanvasTexture(c);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false }));
      sp.scale.set(0.42 * (w / 34), 0.42, 1); sp.position.set(x, y + 0.45, z);
      _scatter.add(sp); _scatterLabels.push(sp);
    } catch (_) {}
  });
  try {
    const hdr = _ctx.label.billboard(THREE, S.poolLabel || "MEASURED", { text: `sovereign models live (${models.length})`, scale: 0.5, position: [0, 2.2, 0] });
    _scatter.add(hdr); _scatterLabels.push(hdr);
  } catch (_) {}
}

// =========================================================================================
// per-frame animation (routing-decision particle stream + halo pulse)
// =========================================================================================
function _onFrame() {
  const THREE = _THREE;
  if (_crossoverMarker) {
    const s = 1 + 0.18 * Math.sin(performance.now() * 0.004);
    _crossoverMarker.halo.scale.set(s, s, s);
  }
  if (_particles) {
    const p = _particles.userData.p, posn = _particles.geometry.attributes.position, colr = _particles.geometry.attributes.color;
    const live = S.crossState === "live" && !S.degraded;
    for (let i = 0; i < p.length; i++) {
      const q = p[i];
      q.t += q.speed;
      if (q.t >= 1) { p[i] = _spawnParticle(i); continue; }
      const x = (q.d - 0.5) * SURF_W;
      // travel from incoming z toward the model lane; lift over the surface ridge
      const z = q.z0 * (1 - q.t) + (q.large ? -SURF_D / 2 - 1 : -SURF_D / 2 - 1) * q.t;
      const h = blend(S.bw, q.d * SPAN_HZ);
      const y = (q.large ? h.hv : h.hc) * 4.2 + 0.5 + Math.sin(q.t * Math.PI) * 0.6;
      posn.setXYZ(i, x, y, z);
      const dim = live ? 1 : 0.35;
      if (q.large) colr.setXYZ(i, 1.0 * dim, 0.71 * dim, 0.42 * dim);
      else colr.setXYZ(i, 0.43 * dim, 0.69 * dim, 1.0 * dim);
    }
    posn.needsUpdate = true; colr.needsUpdate = true;
  }
  if (_scatter) _scatter.rotation.y += 0.0015;
  if (_flipBeacon) _flipBeacon.position.y = 5.4 + 0.12 * Math.sin(performance.now() * 0.003);
}

// =========================================================================================
// DOM overlay (HUD): badges, sliders, KPIs, raw JSON, honesty legend, sources
// =========================================================================================
let _badge = null, _sweepBadge = null, _poolBadge = null;
let _el = {};

function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  _overlay.className = "szl3d-router-overlay";
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,430px)", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.5";
  sub.innerHTML = 'Modeled on <b>OpenRouter State of AI</b> + <b>RouteLLM</b>. ' +
    '<span style="color:#6fb1ff">small/local</span> = easy / low-"frequency", ' +
    '<span style="color:#ffb56b">large/cloud</span> = hard / high-"frequency". ' +
    'Deterministic active-flux PI-bandwidth crossover — the complement to a RouteLLM bandit.';
  _overlay.appendChild(sub);

  // badges
  _badge = ctx.live.createBadge();
  _sweepBadge = ctx.live.createBadge();
  _poolBadge = ctx.live.createBadge();
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#6fb1ff"; return s; };
  badgeRow.appendChild(tag("crossover")); badgeRow.appendChild(_badge.el);
  badgeRow.appendChild(tag("sweep")); badgeRow.appendChild(_sweepBadge.el);
  badgeRow.appendChild(tag("compute-pool")); badgeRow.appendChild(_poolBadge.el);
  _overlay.appendChild(badgeRow);

  // sliders
  _overlay.appendChild(_mkSlider("π-bandwidth ω_c", "bw", 3, 40, 0.5, S.bw, (v) => v.toFixed(1) + " Hz", _onSliderBw));
  _overlay.appendChild(_mkSlider("query difficulty (easy→hard)", "qd", 0, 1, 0.02, S.qd, (v) => v.toFixed(2), _onSliderQd));

  // KPIs
  const kpi = document.createElement("div");
  kpi.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:2px";
  const cell = (id, label, color) => {
    const d = document.createElement("div");
    d.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:7px;padding:7px 9px";
    const b = document.createElement("b"); b.id = "k-" + id;
    b.style.cssText = "display:block;font-size:16px;font-variant-numeric:tabular-nums;color:" + (color || "#e8c074");
    b.textContent = "—";
    const s = document.createElement("span"); s.style.cssText = "font-size:10.5px;color:#9fb1bf"; s.textContent = label;
    d.appendChild(b); d.appendChild(s); _el[id] = b; return d;
  };
  kpi.appendChild(cell("route", "live route", "#39d3c4"));
  kpi.appendChild(cell("cross", "crossover difficulty", "#e8c074"));
  kpi.appendChild(cell("small", "small/local weight", "#6fb1ff"));
  kpi.appendChild(cell("large", "large/cloud weight", "#ffb56b"));
  _overlay.appendChild(kpi);

  // honesty chip + label
  const honest = document.createElement("div");
  honest.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  _el.chip = ctx.label.chip("MODELED", { text: "routing law" });
  honest.appendChild(_el.chip);
  _overlay.appendChild(honest);

  // legend
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);

  // models line
  _el.models = document.createElement("div");
  _el.models.style.cssText = "font-size:10.5px;color:#9fb1bf;line-height:1.5";
  _el.models.textContent = "models: awaiting live router payload";
  _overlay.appendChild(_el.models);

  // raw dump (collapsible)
  const det = document.createElement("details");
  det.style.cssText = "margin-top:2px";
  const sum = document.createElement("summary");
  sum.style.cssText = "cursor:pointer;color:#39d3c4;font:11px ui-monospace,monospace";
  sum.textContent = "raw /router/active-flux-crossover";
  _el.raw = document.createElement("div");
  _el.raw.style.cssText = "white-space:pre-wrap;font:10.5px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;max-height:150px;overflow:auto;margin-top:6px";
  _el.raw.textContent = "—";
  det.appendChild(sum); det.appendChild(_el.raw);
  _overlay.appendChild(det);

  // sources (text only — NOT fetch-shaped, doctrine 0-CDN safe)
  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Adopted & generalized — sources: Active-flux IEEE/APEC 2001 (911711) · Li Yu PI-bandwidth · RouteLLM (LMSYS) · OpenRouter State of AI. MODELED deterministic complement; NOT in the locked-8; Λ = Conjecture 1; trust < 100%.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

function _mkSlider(labelText, key, min, max, step, val, fmt, onInput) {
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;align-items:center;gap:8px";
  const lab = document.createElement("label");
  lab.style.cssText = "color:#9fb1bf;min-width:150px;font-size:11px";
  lab.textContent = labelText;
  const inp = document.createElement("input");
  inp.type = "range"; inp.min = min; inp.max = max; inp.step = step; inp.value = val;
  inp.style.cssText = "flex:1;accent-color:#39d3c4";
  const out = document.createElement("span");
  out.style.cssText = "color:#39d3c4;font:11px ui-monospace,monospace;min-width:58px;text-align:right";
  out.textContent = fmt(val);
  inp.addEventListener("input", () => { out.textContent = fmt(parseFloat(inp.value)); onInput(parseFloat(inp.value)); });
  wrap.appendChild(lab); wrap.appendChild(inp); wrap.appendChild(out);
  return wrap;
}

let _bwDebounce = 0, _qdDebounce = 0;
function _onSliderBw(v) {
  S.bw = v;
  _warpSurface(); _updateRidge(); _updateRegimeZones(); _updateCrossoverMarker(); _updateQueryPlane(); _updateLawOverlay();
  // re-point the live polls at the new bandwidth (sliders WARP the surface; live values
  // come back from the re-pointed endpoints — we never compute the displayed route locally)
  clearTimeout(_bwDebounce);
  _bwDebounce = setTimeout(() => { _repoll(); }, 180);
}
function _onSliderQd(v) {
  S.qd = v; _updateQueryPlane();
  clearTimeout(_qdDebounce);
  _qdDebounce = setTimeout(() => { if (_hCross) { _hCross.stop(); _hCross = _ctx.live.poll(_crossUrl(), 4000, _onCross, { badge: _badge, onState: _onCrossState }); } }, 160);
}
function _repoll() {
  if (_hCross) { _hCross.stop(); _hCross = _ctx.live.poll(_crossUrl(), 4000, _onCross, { badge: _badge, onState: _onCrossState }); }
  if (_hSweep) { _hSweep.stop(); _hSweep = _ctx.live.poll(_sweepUrl(), 6000, _onSweep, { badge: _sweepBadge, onState: (mt) => { S.sweepState = mt.state; } }); }
}

function _paintKPIs() {
  const live = S.crossState === "live" && !S.degraded;
  const dash = "—";
  _el.route && (_el.route.textContent = S.route ? S.route : (live ? dash : (S.crossState === "missing" ? "NO-LIVE-DATA" : S.crossState.toUpperCase())));
  _el.cross && (_el.cross.textContent = S.crossoverDifficulty != null ? S.crossoverDifficulty.toFixed(3) : dash);
  _el.small && (_el.small.textContent = S.wSmall != null ? S.wSmall.toFixed(3) : dash);
  _el.large && (_el.large.textContent = S.wLarge != null ? S.wLarge.toFixed(3) : dash);
  if (_el.chip && _ctx) {
    try { _ctx.label.updateChip(_el.chip, S.label || "MODELED", { text: S.regime ? ("regime: " + S.regime) : "routing law" }); } catch (_) {}
  }
  if (_el.models) {
    if (S.modelsMeta) {
      _el.models.textContent = "router models: small/local = " + (S.modelsMeta.small_local || "?") +
        "  ·  large/cloud = " + (S.modelsMeta.large_cloud || "?") + "  (" + (S.modelsMeta.source || "?") + ")";
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
  try { if (_hCross) _hCross.stop(); } catch (_) {}
  try { if (_hSweep) _hSweep.stop(); } catch (_) {}
  try { if (_hPool) _hPool.stop(); } catch (_) {}
  clearTimeout(_bwDebounce); clearTimeout(_qdDebounce);
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
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
  _hCross = _hSweep = _hPool = null;
  _overlay = _group = _surface = _ridge = _queryPlane = _crossoverMarker = null;
  _sweepRibbon = _scatter = _particles = _waterfall = _regimeZones = _billboard = null;
  _lawOverlay = _flipBeacon = null;
  _scatterLabels = []; _el = {}; _badge = _sweepBadge = _poolBadge = null;
  S.route = S.regime = S.crossoverDifficulty = S.wSmall = S.wLarge = S.label = null;
  S.sweep = S.pool = S.modelsMeta = null;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_CROSS, EP_SWEEP, EP_POOL], mount, unmount };
