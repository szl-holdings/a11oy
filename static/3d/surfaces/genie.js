// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/genie.js — GENERATIVE / INTERACTIVE LATENT-ACTION WORLD-MODEL organ for the
// holographic frontier ring, inspired by (clean-room, not a reproduction of) Google
// DeepMind's Genie / Genie 2 / Genie 3 generative interactive world models.
//
// DISTINCT FROM worldmodel.js: that surface renders a PREDICTOR's latent trajectory —
// two static-ish paths (observed vs predicted) with a "surprise" gap between them. THIS
// surface instead renders a GENERATED, EVOLVING NxN GRID-WORLD — a lattice of cells that
// visibly changes shape/colour every time a new latent action code is applied, i.e. a
// *playable* rollout being generated frame-by-frame, not a predicted path being scored.
// There is no "observed vs predicted" comparison here at all — only forward generation.
//
// Renders the live /api/killinchu/v1/genie/rollout snapshot as an NxN plane of cubes
// (the generated grid-world state) that steps forward through the rollout's
// generated_states[] on a timer, each step driven by the next latent action_code in the
// sequence. A HUD shows the action-code sequence + coherence score. Honesty label
// "MODELED" is read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors interpretability.js / worldmodel.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   grid_size, n_latent_actions, rollout_horizon   — rollout shape
//   action_codes[]                                  — the latent-action-code sequence applied
//   latent_action_codebook[]                        — clustered latent-action centroids (dx,dy,dstate)
//   generated_states[]                              — per-step {mean, active_cells, delta_from_prev}
//   coherence_score                                 — MODELED world-consistency analogue
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Genie (v1): Bruce, Segar, Mnih et al. (2024) arXiv:2402.15391
//     https://arxiv.org/abs/2402.15391
//   Genie 2 (Google DeepMind blog):
//     https://deepmind.google/discover/blog/genie-2-a-large-scale-foundation-world-model/
//   Genie 3 (Google DeepMind blog):
//     https://deepmind.google/discover/blog/genie-3-a-new-frontier-for-world-models/
//
// HONESTY LABELS: MODELED (a toy simulation of the Genie COMPUTATION SHAPE; no video
//   tokenizer, no trained dynamics model, no learned latent-action model, no borrowed
//   weights). Read verbatim from JSON; never upgraded here. SZL does not claim parity
//   with any real Genie model.
// COLOURS: lattice-blue 0x5b8dee (generated cell — low activation), violet-blue 0x8a6bff
//   (generated cell — high activation / most-recently-changed flash — data-viz only),
//   proof-teal 0x3af4c8 (coherence halo), greys for degraded/no-data. Purple BANNED.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

const ID    = "genie";
const TITLE = "Genie · Generative Latent-Action World (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the genie organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/genie/rollout?seed=42&grid=8&horizon=16&n_latent_actions=6";

// data-viz hues — purple BANNED
const C_LO     = 0x5b8dee;  // lattice-blue (generated cell, low activation)
const C_HI     = 0x8a6bff;  // violet-blue (generated cell, high activation / just-changed flash)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (coherence halo)
const C_GRID   = 0x1b3a44;  // floor / wire colour

const MAX_GRID = 16;   // visual cap on grid_size (endpoint clamps grid<=64; we tile at most 16x16 cells for perf)
const CELL     = 0.62; // world-unit spacing between generated cells
const STEP_MS  = 650;  // ms between generated-rollout steps (one latent action applied per tick)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _cells = [];       // Array<THREE.Mesh> — one per generated grid cell (row-major)
let _halo = null;      // THREE.Mesh — coherence halo above the grid
let _floor = null;

// rollout playback state (steps through generated_states[] to visibly "play" the world)
let _stepTimer = null;
let _curStep = 0;

// live state
const S = {
  label:        null,
  gridSize:     null,
  nActions:     null,
  horizon:      null,
  actionCodes:  null,   // Array<int>
  codebook:     null,   // Array<{code,dx,dy,dstate}>
  states:       null,   // Array<{step,action_code,mean,active_cells,delta_from_prev}>
  coherence:    null,
  state:        "init",
};

// deterministic per-cell base pattern so the grid has visible structure even before the
// first generated step lands (re-derived client-side from grid_size only — cosmetic).
function _basePattern(n, r, c) {
  return 0.5 + 0.5 * Math.sin((r * 1.7 + c * 2.3));
}

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHalo();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onRollout, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

function _buildHalo() {
  const THREE = _THREE;
  // Coherence halo — a torus above the grid whose fullness/brightness tracks
  // coherence_score (higher = generated rollout stays more "on-manifold").
  _halo = new THREE.Mesh(
    new THREE.TorusGeometry(3.2, 0.035, 10, 64),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.35, transparent: true, opacity: 0.4 }),
  );
  _halo.position.set(0, 3.4, 0);
  _halo.rotation.x = Math.PI / 2;
  _group.add(_halo);
}

function _disposeGrid() {
  _cells.forEach((m) => {
    if (m.geometry && m.geometry.dispose) m.geometry.dispose();
    if (m.material && m.material.dispose) m.material.dispose();
    if (_group) _group.remove(m);
  });
  _cells = [];
}

// (re)build the NxN generated-grid-world lattice
function _buildGrid(n) {
  const THREE = _THREE;
  _disposeGrid();
  const dim = Math.min(n || 8, MAX_GRID);
  const geo = new THREE.BoxGeometry(CELL * 0.86, 0.2, CELL * 0.86);
  const offset = (dim - 1) / 2;
  for (let r = 0; r < dim; r++) {
    for (let c = 0; c < dim; c++) {
      const v = _basePattern(dim, r, c);
      const mat = new THREE.MeshStandardMaterial({
        color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.12,
        metalness: 0.2, roughness: 0.6,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set((c - offset) * CELL, 0, (r - offset) * CELL);
      mesh.userData.baseHeight = 0.2;
      mesh.userData.value = v;
      _group.add(mesh);
      _cells.push(mesh);
    }
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onRollout(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.gridSize    = typeof j.grid_size === "number" ? j.grid_size : null;
  S.nActions    = typeof j.n_latent_actions === "number" ? j.n_latent_actions : null;
  S.horizon     = typeof j.rollout_horizon === "number" ? j.rollout_horizon : null;
  S.actionCodes = Array.isArray(j.action_codes) ? j.action_codes : null;
  S.codebook    = Array.isArray(j.latent_action_codebook) ? j.latent_action_codebook : null;
  S.states      = Array.isArray(j.generated_states) ? j.generated_states : null;
  S.coherence   = typeof j.coherence_score === "number" ? j.coherence_score : null;

  const dim = Math.min(S.gridSize || 8, MAX_GRID);
  if (_cells.length !== dim * dim) _buildGrid(dim);

  _curStep = 0;
  _startPlayback();
  _updateHalo();
  _paintOverlay();
}

// =============================================================================
// rollout playback — visibly EVOLVE the grid one generated step at a time,
// driven by the corresponding latent action_code (this is what makes the organ
// "generative/interactive" rather than a static readout)
// =============================================================================
function _startPlayback() {
  if (_stepTimer) { clearInterval(_stepTimer); _stepTimer = null; }
  if (!S.states || !S.states.length) return;
  _applyStep(0);
  _stepTimer = setInterval(() => {
    _curStep = (_curStep + 1) % S.states.length;
    _applyStep(_curStep);
  }, STEP_MS);
}

function _applyStep(i) {
  const live = S.state === "live";
  const step = S.states && S.states[i];
  const dim = Math.min(S.gridSize || 8, MAX_GRID);
  if (!step || !_cells.length) return;

  // Deterministically re-derive a per-cell activation for THIS step from the step's
  // scalar summary (mean/delta) + each cell's base pattern + which latent action code
  // is currently being applied — a light client-side visual analogue of the server's
  // generated lattice (full per-cell state is not shipped over the wire to keep the
  // payload small; the endpoint's generated_states[] gives the authoritative summary).
  const code = step.action_code != null ? step.action_code : 0;
  const codebookEntry = (S.codebook && S.codebook[code]) ? S.codebook[code] : { dx: 1, dy: 0, dstate: 0.5 };
  const mean = typeof step.mean === "number" ? step.mean : 0.5;
  const delta = typeof step.delta_from_prev === "number" ? step.delta_from_prev : 0;

  _cells.forEach((mesh, idx) => {
    const r = Math.floor(idx / dim), c = idx % dim;
    const phase = (r * codebookEntry.dx + c * codebookEntry.dy) * 0.6 + i * 0.4;
    const v = live ? Math.max(0, Math.min(1, mean + 0.35 * Math.sin(phase) * codebookEntry.dstate)) : mesh.userData.value;
    mesh.userData.value = v;
    const col = v > 0.62 ? C_HI : C_LO;
    if (live) {
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.15 + 0.75 * v;
      const h = 0.2 + v * 1.3;
      mesh.scale.set(1, h / mesh.userData.baseHeight, 1);
      mesh.position.y = (h - 0.2) / 2;
    } else {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.1;
      mesh.scale.set(1, 1, 1);
      mesh.position.y = 0;
    }
  });

  _paintOverlay(delta);
}

// =============================================================================
// halo updater — driven by coherence_score
// =============================================================================
function _updateHalo() {
  const live = S.state === "live";
  if (!_halo) return;
  const coh = S.coherence != null ? S.coherence : 0.5;
  const col = live ? C_ACCENT : C_DIM;
  _halo.material.color.setHex(col);
  _halo.material.emissive.setHex(col);
  _halo.material.emissiveIntensity = live ? 0.2 + 0.6 * coh : 0.12;
  _halo.material.opacity = live ? 0.5 : 0.2;
  _halo.scale.setScalar(live ? (0.6 + coh) : 0.8);  // fuller halo = higher generated-world coherence
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.15;
  if (_halo) _halo.rotation.z += 0.0035;
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
    'A small <b>latent-action codebook</b> is clustered from state deltas, then applied ' +
    'step-by-step to <b>GENERATE</b> a brand-new grid-world \u2014 the grid you see evolving ' +
    'below \u2014 rather than predicting a pre-recorded path. Honesty label <b>MODELED</b> ' +
    '(a toy simulation of the Genie-style computation shape \u2014 no trained dynamics model, ' +
    'no video tokenizer, no borrowed weights). 0 runtime CDN.';
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
  nm.textContent = "genie";
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

  grid.appendChild(kpiRow("gn-grid",   "grid_size \u00d7 n_latent_actions"));
  grid.appendChild(kpiRow("gn-step",   "step (action code applied)"));
  grid.appendChild(kpiRow("gn-seq",    "action-code sequence"));
  grid.appendChild(kpiRow("gn-coh",    "coherence score \u2014 MODELED"));
  grid.appendChild(kpiRow("gn-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Bruce, Segar, Mnih et al. arXiv:2402.15391 (Genie) \u00b7 deepmind.google Genie 2 blog \u00b7 deepmind.google Genie 3 blog. MODELED \u00b7 not claimed-as \u00b7 not claimed at parity.";
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
  pd.id = "gn-plain";
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
  const coh = S.coherence != null ? (S.coherence * 100).toFixed(1) + "%" : "loading\u2026";
  const na  = S.nActions != null ? String(S.nActions) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of just watching and predicting a pre-recorded clip, " +
    "this organ <b>generates a brand-new interactive world</b> one step at a time \u2014 each " +
    "step conditioned on one of <b>" + na + "</b> discrete \u201clatent actions\u201d, the same " +
    "idea behind Google DeepMind's Genie models: learn a small action vocabulary with no " +
    "labels, then let you \u2018play\u2019 the generated world through it. The grid evolves live " +
    "as each action is applied, and it stays <b>" + coh + "</b> consistent with itself " +
    "step-to-step. " +
    "Plain: this is the shape of computation behind a playable AI-generated world \u2014 but " +
    "this view is a <b>MODELED</b> toy simulation of the technique, not a readout from any " +
    "trained Genie model or real video.";
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

function _paintOverlay(latestDelta) {
  const t = _tok(S.state);
  _set("gn-grid",  t || ((S.gridSize != null && S.nActions != null) ? (S.gridSize + "\u00d7" + S.gridSize + "  \u00d7  " + S.nActions) : "\u2014"));
  const stepInfo = (S.states && S.states[_curStep]) ? S.states[_curStep] : null;
  _set("gn-step",  t || (stepInfo ? ("#" + stepInfo.step + "  code=" + stepInfo.action_code + "  \u0394=" + fx(stepInfo.delta_from_prev, 4)) : "\u2014"));
  const seq = S.actionCodes ? S.actionCodes.slice(0, 12).join(",") + (S.actionCodes.length > 12 ? "\u2026" : "") : "\u2014";
  _set("gn-seq",   t || seq);
  _set("gn-coh",   t || fx(S.coherence, 4));
  // honesty label verbatim — never upgraded
  _set("gn-label", t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  if (_stepTimer) { clearInterval(_stepTimer); _stepTimer = null; }
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
  _cells = []; _halo = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.gridSize = S.nActions = S.horizon = null;
  S.actionCodes = S.codebook = S.states = S.coherence = null;
  S.state = "init";
  _curStep = 0;
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
