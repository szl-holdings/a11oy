// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/hrm.js — HIERARCHICAL REASONING MODEL (HRM) organ for the
// holographic frontier ring. Renders the two-timescale H-slow / L-fast control
// loop solving a toy mini-Sudoku Latin-square grid: a live 3D grid whose cells
// fill in as the FAST low-level executor (L) propagates local constraints and
// the SLOW high-level planner (H) advances an abstract-plan bar once per tick.
// Live snapshot comes from /api/killinchu/v1/hrm/solve.
//
// >>> HONESTY IS THE POINT OF THIS ORGAN <<<
//   Per the ARC Prize independent analysis (arcprize.org/blog/hrm-analysis),
//   the H/L hierarchy is NOT the dominant driver of HRM's headline results — a
//   parameter-matched single-module Transformer came within ~5pp. So this
//   surface renders the H/L result BESIDE a size-matched FLAT single-module
//   baseline (same total update budget) and states the caveat plainly in the
//   "what this means" copy. It does NOT repeat the paper's stronger framing.
//
// Surface export shape (mirrors mor.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   n, h_ticks, l_steps, clues, empty_start, hierarchical{solved,h_ticks_used,
//   l_updates_total,guided_placements,h_plan_trace[],filled_trace[]},
//   flat_baseline{solved,refine_rounds,l_updates_total,guided_placements},
//   hierarchy_edge{both_solved,hier_updates_total,flat_updates_total,
//   l_updates_delta,updates_ratio,verdict}, final_grid[][], solution_grid[][],
//   caveat
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Hierarchical Reasoning Model (two-timescale H/L architecture modeled here):
//     Wang et al. 2025, arXiv:2506.21734  https://arxiv.org/abs/2506.21734
//   Official HRM code (reference only): github.com/sapientinc/HRM
//   ARC Prize independent analysis (the honesty caveat source):
//     https://arcprize.org/blog/hrm-analysis
//   ARC Prize analysis code (reference only):
//     github.com/arcprize/hierarchical-reasoning-model-analysis
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the H/L control
//   loop on a toy grid; NOT the HRM network; NEVER-CLAIMED-AS production). Read
//   verbatim from JSON; never upgraded here. The endpoint puts the label at the
//   TOP LEVEL of its JSON response (j.label); we read that (with a defensive
//   nested payload.label fallback) and display it as-is.
// COLOURS: lattice-blue 0x5b8dee (empty / shallow), violet-blue 0x8a6bff
//   (guided / H-planner accent), proof-teal 0x3af4c8 (solved cell / HUD
//   accent), greys (degraded / no-live-data). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still
//   shown. Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "hrm";
const TITLE = "Hierarchical Reasoning Model · H-slow / L-fast (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the HRM organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/hrm/solve?seed=42&n=4&h_ticks=12&l_steps=8";

// data-viz hues — purple BANNED.
const C_EMPTY   = 0x5b8dee;  // lattice-blue (empty / freshly-considered cell)
const C_GUIDED  = 0x8a6bff;  // violet-blue  (H-planner top-down guided placement)
const C_SOLVED  = 0x3af4c8;  // proof-teal   (filled/solved cell / HUD accent)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// grid layout geometry
const MAX_N     = 9;    // largest grid side we pre-allocate cells for
const CELL      = 1.15; // world-units between grid cells
const MAX_CELLS = MAX_N * MAX_N;

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor     = null;
let _cellMesh  = [];    // Array<THREE.Mesh> — one per grid cell (n×n active subset)
let _planBar   = null;  // THREE.Mesh — H-slow abstract-plan progress bar
let _flatBar   = null;  // THREE.Mesh — flat-baseline progress bar (honest ablation)
let _marker    = null;  // THREE.Mesh — HUD "converged" pulsing marker

// live state
const S = {
  label:        null,
  n:            null,   // grid side
  hTicks:       null,   // h_ticks (budget)
  lSteps:       null,   // l_steps
  clues:        null,   // clues
  emptyStart:   null,   // empty_start
  hier:         null,   // hierarchical{...}
  flat:         null,   // flat_baseline{...}
  edge:         null,   // hierarchy_edge{...}
  finalGrid:    null,   // final_grid[][]
  caveat:       null,   // caveat string
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildGrid();
  _buildBars();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onHrm, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateScene(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(30, 30, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Pre-allocate MAX_N×MAX_N cell meshes; we position/show only the active n×n
// subset per poll (no geometry churn). Each cell is a small tile that rises &
// recolours as it gets filled by the L-executor / H-planner.
function _buildGrid() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(CELL * 0.8, 0.5, CELL * 0.8);
  for (let i = 0; i < MAX_CELLS; i++) {
    const mesh = new THREE.Mesh(
      cellGeo,
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.12, transparent: true, opacity: 0.0 }),
    );
    mesh.visible = false;
    _group.add(mesh);
    _cellMesh.push(mesh);
  }
}

// Two upright progress bars behind the grid: the H-slow abstract-plan bar
// (proof-teal) and the size-matched FLAT baseline bar (violet-blue). Showing
// them side by side is the honest ablation — they end up nearly equal.
function _buildBars() {
  const THREE = _THREE;
  const barGeo = new THREE.BoxGeometry(0.7, 1.0, 0.7);
  _planBar = new THREE.Mesh(
    barGeo,
    new THREE.MeshStandardMaterial({ color: C_SOLVED, emissive: C_SOLVED, emissiveIntensity: 0.35, transparent: true, opacity: 0.0 }),
  );
  _planBar.position.set(-1.1, 0.02, -(MAX_N * CELL * 0.5) - 1.6);
  _planBar.scale.y = 0.05;
  _group.add(_planBar);

  _flatBar = new THREE.Mesh(
    barGeo,
    new THREE.MeshStandardMaterial({ color: C_GUIDED, emissive: C_GUIDED, emissiveIntensity: 0.3, transparent: true, opacity: 0.0 }),
  );
  _flatBar.position.set(1.1, 0.02, -(MAX_N * CELL * 0.5) - 1.6);
  _flatBar.scale.y = 0.05;
  _group.add(_flatBar);
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.30, 1),
    new THREE.MeshStandardMaterial({ color: C_SOLVED, emissive: C_SOLVED, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, 4.0, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onHrm(j) {
  // read honesty label VERBATIM — never upgrade. Endpoint puts label at the
  // TOP LEVEL of the JSON (this module's own response shape), so read j.label;
  // fall back to a nested payload.label defensively in case of a wrapper.
  const rawLabel = (j && typeof j.label === "string") ? j.label
                 : (j && j.payload && typeof j.payload.label === "string") ? j.payload.label
                 : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : (j || {});

  S.label      = String(rawLabel).toUpperCase();
  S.n          = typeof src.n           === "number" ? src.n           : null;
  S.hTicks     = typeof src.h_ticks     === "number" ? src.h_ticks     : null;
  S.lSteps     = typeof src.l_steps     === "number" ? src.l_steps     : null;
  S.clues      = typeof src.clues       === "number" ? src.clues       : null;
  S.emptyStart = typeof src.empty_start === "number" ? src.empty_start : null;
  S.hier       = (src.hierarchical && typeof src.hierarchical === "object") ? src.hierarchical : null;
  S.flat       = (src.flat_baseline && typeof src.flat_baseline === "object") ? src.flat_baseline : null;
  S.edge       = (src.hierarchy_edge && typeof src.hierarchy_edge === "object") ? src.hierarchy_edge : null;
  S.finalGrid  = Array.isArray(src.final_grid) ? src.final_grid : null;
  S.caveat     = typeof src.caveat === "string" ? src.caveat : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the grid + progress bars from live data
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const n = live && S.n ? Math.min(S.n, MAX_N) : 0;
  const grid = live && S.finalGrid ? S.finalGrid : null;

  // --- solved-grid tiles ---
  const x0 = -(n - 1) * CELL * 0.5;
  const z0 = -(n - 1) * CELL * 0.5;
  for (let i = 0; i < MAX_CELLS; i++) {
    const mesh = _cellMesh[i];
    if (!live || n <= 0 || i >= n * n) { mesh.visible = false; continue; }
    const r = (i / n) | 0;
    const c = i % n;
    mesh.visible = true;
    mesh.position.set(x0 + c * CELL, 0.25, z0 + r * CELL);
    const filled = grid && grid[r] && typeof grid[r][c] === "number" && grid[r][c] !== 0;
    // solved cells glow proof-teal and rise; unfilled cells stay low lattice-blue
    const color = filled ? C_SOLVED : C_EMPTY;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = filled ? 0.5 : 0.16;
    mesh.material.opacity = filled ? 0.95 : 0.4;
    const h = filled ? 0.9 : 0.25;
    mesh.scale.y = h;
    mesh.position.y = h * 0.5;
  }

  // --- H-slow plan bar (proof-teal): final abstract-plan value (fraction filled) ---
  if (_planBar) {
    const trace = live && S.hier && Array.isArray(S.hier.h_plan_trace) ? S.hier.h_plan_trace : null;
    const plan = trace && trace.length ? trace[trace.length - 1] : (live && S.hier && S.hier.solved ? 1 : 0);
    if (live && plan != null) {
      _planBar.material.color.setHex(C_SOLVED); _planBar.material.emissive.setHex(C_SOLVED);
      _planBar.material.opacity = 0.9;
      const h = 0.15 + plan * 3.4; _planBar.scale.y = h; _planBar.position.y = h * 0.5;
    } else {
      _planBar.material.color.setHex(C_DIM); _planBar.material.emissive.setHex(C_DIM);
      _planBar.material.opacity = 0.3; _planBar.scale.y = 0.05; _planBar.position.y = 0.02;
    }
  }

  // --- FLAT baseline bar (violet-blue): honest ablation, ends up near-equal ---
  if (_flatBar) {
    const flatSolved = live && S.flat && S.flat.solved;
    const flatFrac = flatSolved ? 1 : (live && S.emptyStart != null && S.n != null && S.flat
      ? Math.max(0, Math.min(1, (S.n * S.n - (S.emptyStart - (S.flat.l_updates_total || 0))) / (S.n * S.n)))
      : 0);
    if (live) {
      _flatBar.material.color.setHex(C_GUIDED); _flatBar.material.emissive.setHex(C_GUIDED);
      _flatBar.material.opacity = 0.9;
      const h = 0.15 + flatFrac * 3.4; _flatBar.scale.y = h; _flatBar.position.y = h * 0.5;
    } else {
      _flatBar.material.color.setHex(C_DIM); _flatBar.material.emissive.setHex(C_DIM);
      _flatBar.material.opacity = 0.3; _flatBar.scale.y = 0.05; _flatBar.position.y = 0.02;
    }
  }

  // --- converged marker ---
  if (_marker) {
    if (live && S.hier && S.hier.solved) {
      _marker.material.color.setHex(C_SOLVED); _marker.material.emissive.setHex(C_SOLVED);
      _marker.material.opacity = 0.85; _marker.scale.setScalar(1.0);
    } else {
      _marker.material.color.setHex(C_DIM); _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3; _marker.scale.setScalar(0.7);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.16;
  if (_marker) {
    _marker.rotation.y += 0.022;
    _marker.rotation.x += 0.011;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.004);
    _marker.scale.setScalar((S.hier && S.hier.solved ? 1.0 : 0.7) * pulse);
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
    'Two interdependent recurrent modules at different timescales solve a mini-Sudoku: a ' +
    '<b>fast low-level executor (L)</b> propagates local cell constraints to convergence, and a ' +
    '<b>slow high-level planner (H)</b> advances an abstract plan once per tick and nudges the ' +
    'executor when it stalls. Cells glow <b>teal</b> as they solve. ' +
    'Honesty label <b>MODELED</b> (deterministic control-loop simulation on a toy grid; NOT the HRM network). 0 runtime CDN.';
  _overlay.appendChild(sub);

  // explicit honesty-caveat banner (the ARC Prize finding) — always shown
  const dist = document.createElement("div");
  dist.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.5;border:1px solid #26333f;border-radius:7px;padding:7px 9px;background:#0a1117";
  dist.innerHTML =
    '<b style="color:#3af4c8">Honesty caveat.</b> ' +
    'Independent analysis by the <b>ARC Prize team</b> (arcprize.org/blog/hrm-analysis) found the ' +
    'H/L <b>hierarchy is NOT the dominant driver</b> of HRM\u2019s headline results \u2014 a ' +
    'parameter-matched <i>single-module</i> Transformer came within <b>~5 points</b>. The real ' +
    'drivers were an <b>outer refinement loop</b>, heavy <b>data augmentation</b>, and a per-task ' +
    '<b>puzzle-embedding</b>. So this organ shows the H/L result <i>beside</i> a size-matched ' +
    '<b>flat baseline</b> (violet bar) \u2014 they end up nearly equal. We do <i>not</i> overclaim the hierarchy.';
  _overlay.appendChild(dist);

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
  nm.textContent = "hierarchical reasoning model";
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

  grid.appendChild(kpiRow("hrm-grid",     "puzzle (mini-Sudoku n\u00d7n)"));
  grid.appendChild(kpiRow("hrm-clues",    "clues / empty at start"));
  grid.appendChild(kpiRow("hrm-hsolved",  "H/L hierarchical: solved?"));
  grid.appendChild(kpiRow("hrm-hticks",   "H-slow ticks used"));
  grid.appendChild(kpiRow("hrm-hupdates", "H/L total updates \u2014 MODELED"));
  grid.appendChild(kpiRow("hrm-fsolved",  "flat baseline (size-matched): solved?"));
  grid.appendChild(kpiRow("hrm-fupdates", "flat total updates \u2014 MODELED"));
  grid.appendChild(kpiRow("hrm-ratio",    "updates ratio (hier / flat)"));
  grid.appendChild(kpiRow("hrm-verdict",  "honest verdict"));
  grid.appendChild(kpiRow("hrm-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Wang et al. arXiv:2506.21734 (HRM) \u00b7 github.com/sapientinc/HRM \u00b7 ARC Prize analysis arcprize.org/blog/hrm-analysis. MODELED \u00b7 not claimed-as.";
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
  pd.id = "hrm-plain";
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
  const nn      = S.n != null ? (S.n + "\u00d7" + S.n) : "small";
  const hSolved = S.hier && S.hier.solved ? "yes" : "not yet";
  const ratio   = S.edge && S.edge.updates_ratio != null ? S.edge.updates_ratio.toFixed(2) : "\u2248 1";
  const verdict = S.edge && typeof S.edge.verdict === "string" ? S.edge.verdict : null;
  pd.innerHTML =
    "<b>What this means:</b> A hard puzzle (here a " + nn + " mini-Sudoku) is solved by two " +
    "cooperating parts of one model running at different speeds: a <b>fast \u201cworker\u201d</b> that " +
    "fills in whatever cells are locally forced, and a <b>slow \u201cplanner\u201d</b> that steps back " +
    "once in a while to see the big picture and unstick the worker. It reaches the answer in a " +
    "single pass, without writing out its reasoning step-by-step (solved: " + hSolved + "). " +
    "<b>But here is the honest part:</b> the independent <b>ARC Prize</b> team re-examined HRM and " +
    "found this slow/fast <i>hierarchy is not actually the main reason it works</i> \u2014 an " +
    "ordinary <i>single-module</i> model of the same size got within about <b>5 points</b>. The real " +
    "gains came from repeatedly <b>refining</b> the answer, lots of <b>data augmentation</b>, and " +
    "<b>memorizing each puzzle\u2019s identity</b>. To keep us honest, this view runs a size-matched " +
    "<b>flat baseline</b> right next to the hierarchy: they use almost the same effort " +
    "(updates ratio \u2248 <b>" + ratio + "</b>)" +
    (verdict ? " \u2014 <i>" + verdict + "</i>" : "") + ". " +
    "The hierarchy gives a <b>small, real</b> benefit, not the dominant one the paper implies. " +
    "This whole view is a <b>MODELED</b> simulation of the control loop on a toy grid, not a run " +
    "of the real 27M-parameter HRM network.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function _yn(v) { return v === true ? "yes" : v === false ? "no" : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("hrm-grid",     t || (S.n != null ? (S.n + "\u00d7" + S.n + " Latin square") : "\u2014"));
  _set("hrm-clues",    t || ((S.clues != null && S.emptyStart != null) ? (S.clues + " clues / " + S.emptyStart + " empty") : "\u2014"));
  _set("hrm-hsolved",  t || (S.hier ? _yn(S.hier.solved) : "\u2014"));
  _set("hrm-hticks",   t || (S.hier && S.hier.h_ticks_used != null ? String(S.hier.h_ticks_used) : "\u2014"));
  _set("hrm-hupdates", t || (S.edge && S.edge.hier_updates_total != null ? String(S.edge.hier_updates_total) : "\u2014"));
  _set("hrm-fsolved",  t || (S.flat ? _yn(S.flat.solved) : "\u2014"));
  _set("hrm-fupdates", t || (S.edge && S.edge.flat_updates_total != null ? String(S.edge.flat_updates_total) : "\u2014"));
  _set("hrm-ratio",    t || (S.edge && S.edge.updates_ratio != null ? S.edge.updates_ratio.toFixed(3) : "\u2014"));
  _set("hrm-verdict",  t || (S.edge && typeof S.edge.verdict === "string"
    ? (S.edge.verdict.length > 64 ? S.edge.verdict.slice(0, 61) + "\u2026" : S.edge.verdict)
    : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("hrm-label", t || (S.label || "MODELED"));
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
  _floor = null; _cellMesh = []; _planBar = null; _flatBar = null; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.n = S.hTicks = S.lSteps = S.clues = S.emptyStart = null;
  S.hier = S.flat = S.edge = S.finalGrid = S.caveat = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
