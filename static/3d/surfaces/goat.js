// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/goat.js — GOAT (Generalized Optimal-transport Attention with
// Trainable priors) organ for the holographic frontier ring. Renders TWO
// side-by-side attention-weight bar fields for the same query row:
//   LEFT  — plain SOFTMAX attention: a tall lattice-blue "sink" spike parks
//           runaway mass on token 0 (the attention-sink pathology).
//   RIGHT — GOAT OT-attention: mass redistributed by relevance via an entropic
//           Sinkhorn transport plan with a trainable key prior; the sink spike
//           collapses (proof-teal), mass spreads across relevant keys.
// A HUD shows sink_softmax vs sink_goat + sink_reduction, and animates the
// Sinkhorn convergence residual trace. All numbers come from the live snapshot
// at /api/killinchu/v1/goat/transport. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   n_q, n_k, iters, reg, prior, sink_softmax, sink_goat, sink_reduction,
//   sinkhorn_residuals[], attn_softmax_row0[], attn_goat_row0[], converged
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   GOAT — Generalized Optimal-transport Attention with Trainable priors
//     (attention-as-OT that removes attention sinks; simulated here):
//     Jan 2026, arXiv:2601.15380  https://arxiv.org/abs/2601.15380
//   Sinkhorn distances / entropic OT (the scaling recursion used):
//     Cuturi 2013, arXiv:1306.0895  https://arxiv.org/abs/1306.0895
//   Attention sinks (the phenomenon GOAT removes — reference only):
//     Xiao et al. 2023 (StreamingLLM), arXiv:2309.17453
//     https://arxiv.org/abs/2309.17453
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the
//   attention-as-optimal-transport arithmetic; NOT a trained transformer;
//   NEVER-CLAIMED-AS a production model). Read verbatim from JSON; never
//   upgraded here.
// COLOURS: lattice-blue 0x5b8dee (softmax bars / sink spike), violet-blue
//   0x8a6bff (Sinkhorn convergence trace / prior), proof-teal 0x3af4c8 (GOAT
//   OT bars / HUD accent), greys (degraded / no-live-data). Purple BANNED as
//   UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (page importmap / vendored).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "goat";
const TITLE = "GOAT · Optimal-Transport Attention (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin for the
// flagship). This keeps the GOAT organ's rebuilds/faults isolated.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/goat/transport?seed=42&n_q=12&n_k=16&iters=40&reg=1.0";

// data-viz hues — purple BANNED
const C_SOFT   = 0x5b8dee;  // lattice-blue (softmax bars / sink spike)
const C_GOAT   = 0x3af4c8;  // proof-teal (GOAT OT bars / HUD accent)
const C_CONV   = 0x8a6bff;  // violet-blue (Sinkhorn convergence trace / prior)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const BAR_GAP    = 0.42;   // world-units between attention-weight bars (Z)
const MAX_KEYS   = 16;     // cap on n_k rendered per attention row (perf)
const PANEL_DX   = 5.6;    // X separation between softmax panel and GOAT panel
const BAR_W      = 0.30;   // bar footprint
const BAR_MAXH   = 4.2;    // max bar height for weight = 1.0
const CONV_LEN   = 6.0;    // world-length of the convergence trace along X
const MAX_CONV   = 40;     // cap on residual points rendered

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor       = null;
let _softBars    = [];              // Array<THREE.Mesh> — softmax attention bars
let _goatBars    = [];              // Array<THREE.Mesh> — GOAT OT attention bars
let _convLine    = null;            // THREE.Line — Sinkhorn convergence residual trace
let _convDots    = [];              // Array<THREE.Mesh> — residual sample markers
let _sinkRingS   = null;            // THREE.Mesh — softmax sink halo (on token 0)
let _sinkRingG   = null;            // THREE.Mesh — GOAT sink halo (on token 0)

// live state
const S = {
  label:       null,
  nQ:          null,   // n_q
  nK:          null,   // n_k
  iters:       null,   // iters
  reg:         null,   // reg
  prior:       null,   // prior (string)
  sinkSoft:    null,   // sink_softmax
  sinkGoat:    null,   // sink_goat
  sinkRed:     null,   // sink_reduction
  residuals:   null,   // sinkhorn_residuals[]
  attnSoft:    null,   // attn_softmax_row0[]
  attnGoat:    null,   // attn_goat_row0[]
  converged:   null,   // converged (bool)
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildBars();
  _buildConvergence();
  _buildSinkHalos();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onGoat, { badge: _badge, onState: (m) => { S.state = m.state; _updateScene(); _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Pre-allocate two fixed rows of MAX_KEYS bars each (softmax panel on -X,
// GOAT panel on +X). Heights/colours are toggled in-place as live data arrives
// (no per-poll geometry churn).
function _buildBars() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(BAR_W, 1, BAR_W); // unit-height; scaled on update
  for (let k = 0; k < MAX_KEYS; k++) {
    const z = (k - (MAX_KEYS - 1) / 2) * BAR_GAP;

    const sMesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_SOFT, emissive: C_SOFT, emissiveIntensity: 0.28, transparent: true, opacity: 0.0 }),
    );
    sMesh.position.set(-PANEL_DX / 2, 0.001, z);
    sMesh.visible = false;
    _group.add(sMesh);
    _softBars.push(sMesh);

    const gMesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_GOAT, emissive: C_GOAT, emissiveIntensity: 0.28, transparent: true, opacity: 0.0 }),
    );
    gMesh.position.set(PANEL_DX / 2, 0.001, z);
    gMesh.visible = false;
    _group.add(gMesh);
    _goatBars.push(gMesh);
  }
}

// Sinkhorn convergence residual trace: a polyline (violet-blue) that runs
// along +X above the panels, y = log-scaled residual. Pre-allocate the line and
// the sample dots; update points in-place.
function _buildConvergence() {
  const THREE = _THREE;
  const pts = [];
  for (let i = 0; i < MAX_CONV; i++) pts.push(new THREE.Vector3(0, 0, 0));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: C_CONV, transparent: true, opacity: 0.85 });
  _convLine = new THREE.Line(geo, mat);
  _convLine.position.set(-CONV_LEN / 2, 5.0, -3.4);
  _convLine.visible = false;
  _group.add(_convLine);

  const dotGeo = new THREE.SphereGeometry(0.07, 8, 8);
  for (let i = 0; i < MAX_CONV; i++) {
    const d = new THREE.Mesh(
      dotGeo,
      new THREE.MeshStandardMaterial({ color: C_CONV, emissive: C_CONV, emissiveIntensity: 0.45, transparent: true, opacity: 0.0 }),
    );
    d.visible = false;
    _convLine.add(d);
    _convDots.push(d);
  }
}

// Sink halos: a ring around token-0's bar in each panel to spotlight the
// attention-sink location. Softmax halo glows large (sink present); GOAT halo
// shrinks (sink removed).
function _buildSinkHalos() {
  const THREE = _THREE;
  const z0 = (0 - (MAX_KEYS - 1) / 2) * BAR_GAP;

  _sinkRingS = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.05, 8, 32),
    new THREE.MeshStandardMaterial({ color: C_SOFT, emissive: C_SOFT, emissiveIntensity: 0.5, transparent: true, opacity: 0.0 }),
  );
  _sinkRingS.rotation.x = Math.PI / 2;
  _sinkRingS.position.set(-PANEL_DX / 2, 0.05, z0);
  _group.add(_sinkRingS);

  _sinkRingG = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.05, 8, 32),
    new THREE.MeshStandardMaterial({ color: C_GOAT, emissive: C_GOAT, emissiveIntensity: 0.5, transparent: true, opacity: 0.0 }),
  );
  _sinkRingG.rotation.x = Math.PI / 2;
  _sinkRingG.position.set(PANEL_DX / 2, 0.05, z0);
  _group.add(_sinkRingG);
}

// =============================================================================
// live data handler
// =============================================================================
function _onGoat(j) {
  // read honesty label VERBATIM — never upgrade. This module places the label
  // at TOP LEVEL of the JSON (j.label); also tolerate a nested payload.label.
  const rawLabel = (j && (j.label != null ? j.label : (j.payload && j.payload.label))) || "MODELED";
  S.label     = String(rawLabel).toUpperCase();
  S.nQ        = typeof j.n_q            === "number" ? j.n_q            : null;
  S.nK        = typeof j.n_k            === "number" ? j.n_k            : null;
  S.iters     = typeof j.iters          === "number" ? j.iters          : null;
  S.reg       = typeof j.reg            === "number" ? j.reg            : null;
  S.prior     = typeof j.prior          === "string" ? j.prior          : null;
  S.sinkSoft  = typeof j.sink_softmax   === "number" ? j.sink_softmax   : null;
  S.sinkGoat  = typeof j.sink_goat      === "number" ? j.sink_goat      : null;
  S.sinkRed   = typeof j.sink_reduction === "number" ? j.sink_reduction : null;
  S.residuals = Array.isArray(j.sinkhorn_residuals) ? j.sinkhorn_residuals : null;
  S.attnSoft  = Array.isArray(j.attn_softmax_row0) ? j.attn_softmax_row0 : null;
  S.attnGoat  = Array.isArray(j.attn_goat_row0) ? j.attn_goat_row0 : null;
  S.converged = typeof j.converged      === "boolean" ? j.converged     : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the two bar fields + convergence trace + halos
// =============================================================================
function _setBar(mesh, weight, live, color) {
  if (weight == null || !live) {
    mesh.visible = false;
    return;
  }
  mesh.visible = true;
  const h = Math.max(0.001, Math.min(1, weight) * BAR_MAXH);
  mesh.scale.y = h;
  mesh.position.y = h / 2;
  const c = live ? color : C_DIM;
  mesh.material.color.setHex(c);
  mesh.material.emissive.setHex(c);
  mesh.material.emissiveIntensity = live ? 0.28 + 0.5 * Math.min(1, weight) : 0.08;
  mesh.material.opacity = live ? 0.92 : 0.25;
}

function _updateScene() {
  const live = S.state === "live";
  const soft = live && S.attnSoft ? S.attnSoft : [];
  const goat = live && S.attnGoat ? S.attnGoat : [];

  for (let k = 0; k < MAX_KEYS; k++) {
    _setBar(_softBars[k], k < soft.length ? soft[k] : null, live, C_SOFT);
    _setBar(_goatBars[k], k < goat.length ? goat[k] : null, live, C_GOAT);
  }

  // sink halos: scale with the sink mass on token 0 in each panel
  if (_sinkRingS) {
    const on = live && S.sinkSoft != null;
    _sinkRingS.material.opacity = on ? 0.85 : 0.0;
    const c = live ? C_SOFT : C_DIM;
    _sinkRingS.material.color.setHex(c); _sinkRingS.material.emissive.setHex(c);
    _sinkRingS.scale.setScalar(on ? 0.6 + 1.6 * Math.min(1, S.sinkSoft) : 1.0);
  }
  if (_sinkRingG) {
    const on = live && S.sinkGoat != null;
    _sinkRingG.material.opacity = on ? 0.85 : 0.0;
    const c = live ? C_GOAT : C_DIM;
    _sinkRingG.material.color.setHex(c); _sinkRingG.material.emissive.setHex(c);
    _sinkRingG.scale.setScalar(on ? 0.6 + 1.6 * Math.min(1, S.sinkGoat) : 1.0);
  }

  _updateConvergence(live);
}

// Sinkhorn convergence trace — plot residuals (log-scaled) decreasing to 0.
function _updateConvergence(live) {
  if (!_convLine) return;
  const res = live && S.residuals && S.residuals.length ? S.residuals.slice(0, MAX_CONV) : [];
  const show = res.length > 1;
  _convLine.visible = show;
  const c = live ? C_CONV : C_DIM;
  _convLine.material.color.setHex(c);

  if (!show) {
    _convDots.forEach((d) => { d.visible = false; });
    return;
  }

  // log-scale the residuals into a readable height band; clamp tiny values.
  const logs = res.map((r) => Math.log10(Math.max(r, 1e-9)));   // e.g. 0.6 .. -9
  const lo = Math.min.apply(null, logs);
  const hi = Math.max.apply(null, logs);
  const span = Math.max(1e-6, hi - lo);
  const n = res.length;

  const pos = _convLine.geometry.attributes.position;
  for (let i = 0; i < MAX_CONV; i++) {
    if (i < n) {
      const x = (i / (n - 1)) * CONV_LEN;
      const y = ((logs[i] - lo) / span) * 2.6;   // higher residual => higher y
      pos.setXYZ(i, x, y, 0);
      const d = _convDots[i];
      d.visible = true;
      d.position.set(x, y, 0);
      d.material.color.setHex(c); d.material.emissive.setHex(c);
      d.material.opacity = 0.9;
    } else {
      // park unused vertices on the last point so the line does not stray
      const lastX = CONV_LEN, lastY = 0;
      pos.setXYZ(i, lastX, lastY, 0);
      _convDots[i].visible = false;
    }
  }
  pos.needsUpdate = true;
  _convLine.geometry.computeBoundingSphere();
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;
  if (_sinkRingS) _sinkRingS.rotation.z += 0.01;
  if (_sinkRingG) _sinkRingG.rotation.z -= 0.01;
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
    'Plain <b>softmax</b> attention (left, lattice-blue) dumps runaway mass onto one token \u2014 the ' +
    '<b>attention sink</b> (usually token 0). <b>GOAT</b> (right, proof-teal) reframes each attention row ' +
    'as an <b>optimal-transport</b> problem: an entropic <b>Sinkhorn</b> plan with a <b>trainable key prior</b> ' +
    'that pins the column mass, so the sink is structurally removed and mass spreads by relevance. ' +
    'Honesty label <b>MODELED</b> (deterministic OT/Sinkhorn simulation; NOT a trained transformer). 0 runtime CDN.';
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
  nm.textContent = "optimal-transport attention";
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

  grid.appendChild(kpiRow("gt-dims",    "queries \u00d7 keys (n_q \u00d7 n_k)"));
  grid.appendChild(kpiRow("gt-reg",     "Sinkhorn reg (temperature)"));
  grid.appendChild(kpiRow("gt-prior",   "key prior (trainable)"));
  grid.appendChild(kpiRow("gt-sinks",   "sink mass on token 0 \u2014 softmax"));
  grid.appendChild(kpiRow("gt-sinkg",   "sink mass on token 0 \u2014 GOAT"));
  grid.appendChild(kpiRow("gt-sinkred", "sink removed by GOAT \u2014 MODELED"));
  grid.appendChild(kpiRow("gt-conv",    "Sinkhorn converged?"));
  grid.appendChild(kpiRow("gt-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "GOAT arXiv:2601.15380 (attention-as-OT) \u00b7 Sinkhorn: Cuturi arXiv:1306.0895 \u00b7 attention sinks: Xiao et al. arXiv:2309.17453. MODELED \u00b7 not claimed-as.";
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
  pd.id = "gt-plain";
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
  const ss  = S.sinkSoft != null ? (S.sinkSoft * 100).toFixed(0) + "%" : "loading\u2026";
  const sg  = S.sinkGoat != null ? (S.sinkGoat * 100).toFixed(0) + "%" : "loading\u2026";
  const red = S.sinkRed  != null ? (S.sinkRed  * 100).toFixed(0) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> When a language model \u201cpays attention,\u201d it decides how much weight to put " +
    "on each earlier word. Normal attention (<b>softmax</b>) has a bad habit: it parks a huge chunk of that " +
    "weight on one throwaway token \u2014 usually the very first one \u2014 just to keep the rest of the row tidy. " +
    "Here that <b>attention sink</b> soaks up about <b>" + ss + "</b> of the weight, which is wasted. " +
    "<b>GOAT</b> treats attention like a <i>shipping problem</i>: it must deliver a fixed total of \u201cattention " +
    "cargo\u201d and, crucially, a <b>learned rule</b> caps how much any single token is allowed to receive \u2014 so no " +
    "token can hoard it. After GOAT, the sink token holds only about <b>" + sg + "</b>, a <b>" + red + " reduction</b>, " +
    "and the freed-up attention flows to genuinely relevant words. This view is a <b>MODELED</b> deterministic " +
    "simulation of the optimal-transport math (Sinkhorn), not a run of a real trained model.";
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
  _set("gt-dims",    t || (S.nQ != null && S.nK != null ? (S.nQ + " \u00d7 " + S.nK) : "\u2014"));
  _set("gt-reg",     t || fx(S.reg, 3));
  _set("gt-prior",   t || (S.prior || "\u2014"));
  _set("gt-sinks",   t || pct(S.sinkSoft, 1));
  _set("gt-sinkg",   t || pct(S.sinkGoat, 1));
  _set("gt-sinkred", t || pct(S.sinkRed, 1));
  _set("gt-conv",    t || (S.converged === true ? "yes (marginals matched)" : S.converged === false ? "not yet" : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("gt-label",   t || (S.label || "MODELED"));
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
  _floor = null; _softBars = []; _goatBars = [];
  _convLine = null; _convDots = []; _sinkRingS = null; _sinkRingG = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nQ = S.nK = S.iters = S.reg = S.prior = null;
  S.sinkSoft = S.sinkGoat = S.sinkRed = S.residuals = S.attnSoft = S.attnGoat = S.converged = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
