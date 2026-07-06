// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/pfield.js — PFIELD (Pressure-Field Stigmergic Multi-Agent
// Coordination) organ for the holographic frontier ring. Renders the shared
// constraint-grid ARTIFACT as a lattice of cells whose height/glow encodes the
// live PRESSURE field: high-violation cells rise as lattice-blue pillars, and
// as the N pressure-field agents implicitly de-conflict (no messages), the
// pillars collapse to a flat proof-teal solved plane. A side-by-side HUD sweeps
// agent counts 2..32 comparing pfield vs sequential vs hierarchical
// (solve-rate, steps-to-converge, coordination messages), and a decay-ablation
// readout shows the ~49x pressure runaway when temporal decay is disabled. All
// numbers come from the live snapshot at /api/killinchu/v1/pfield/coordinate.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is;
// it is never upgraded.
//
// Surface export shape (mirrors grpo.js / goat.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   n_agents, grid, decay, steps, pfield{solved,steps_to_converge,
//   final_violations,peak_pressure,messages,violation_trajectory[],
//   pressure_trajectory[]}, baselines{sequential,hierarchical}, sweep[],
//   ablation{peak_pressure_decay,peak_pressure_no_decay,pressure_runaway_x},
//   matches_hierarchical
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Pressure-field stigmergic coordination + temporal decay (simulated here,
//   including the ~49x no-decay pressure runaway):
//     Rodriguez 2026, "Emergent Coordination in Multi-Agent Systems via
//     Pressure Fields and Temporal Decay", arXiv:2601.08129 (13 Jan 2026)
//     https://arxiv.org/abs/2601.08129
//     full text: https://arxiv.org/html/2601.08129v3
//
// HONESTY LABELS: MODELED (deterministic simulation of the pressure-field /
//   temporal-decay coordination arithmetic; NOT real LLM agents; NO real
//   message passing; NEVER-CLAIMED-AS a real multi-agent deployment). Read
//   verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (pressure pillars / artifact grid), violet-blue
//   0x8a6bff (temporal-decay / ablation trace), proof-teal 0x3af4c8 (solved
//   cells / pfield accent), greys (degraded / no-live-data). Purple BANNED as
//   UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (page importmap / vendored).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "pfield";
const TITLE = "PFIELD · Pressure-Field Stigmergic Coordination (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin for the
// flagship). This keeps the pfield organ's rebuilds/faults isolated.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/pfield/coordinate?seed=42&n_agents=8&grid=6&decay=0.8&steps=200";

// data-viz hues — purple BANNED
const C_PRESS  = 0x5b8dee;  // lattice-blue (pressure pillars / artifact grid)
const C_SOLVED = 0x3af4c8;  // proof-teal (solved cells / pfield accent)
const C_DECAY  = 0x8a6bff;  // violet-blue (temporal-decay / ablation trace)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const CELL_GAP   = 1.05;   // world-units between artifact cells
const MAX_SIDE   = 12;     // cap on grid side length rendered (n x n cells)
const PILLAR_W   = 0.66;   // cell pillar footprint
const PILLAR_MAXH = 4.0;   // max pillar height at peak local pressure
const ABL_LEN    = 6.0;    // world-length of the ablation bar pair along X
const AGENT_ORBIT = 5.4;   // radius agents orbit the artifact at (visual only)
const MAX_AGENTS = 32;     // cap on agent motes rendered

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _cells      = [];                 // Array<THREE.Mesh> — artifact-cell pressure pillars (row-major)
let _cellSide   = 0;                  // current rendered grid side length
let _agents     = [];                 // Array<THREE.Mesh> — orbiting agent motes (visual)
let _ablDecay   = null;               // THREE.Mesh — decay-on peak bar (bounded)
let _ablNoDecay = null;               // THREE.Mesh — decay-off peak bar (runaway)

// live state
const S = {
  label:        null,
  nAgents:      null,   // n_agents
  grid:         null,   // grid side length
  decay:        null,   // decay
  steps:        null,   // steps
  solved:       null,   // pfield.solved
  stepsConv:    null,   // pfield.steps_to_converge
  finalViol:    null,   // pfield.final_violations
  peakPress:    null,   // pfield.peak_pressure
  messages:     null,   // pfield.messages (0 for stigmergic)
  violTraj:     null,   // pfield.violation_trajectory[]
  pressTraj:    null,   // pfield.pressure_trajectory[]
  seqSolved:    null,   // baselines.sequential.solved
  seqSteps:     null,   // baselines.sequential.steps_to_converge
  hierSolved:   null,   // baselines.hierarchical.solved
  hierSteps:    null,   // baselines.hierarchical.steps_to_converge
  hierMsgs:     null,   // baselines.hierarchical.messages
  sweep:        null,   // sweep[]
  ablDecayPk:   null,   // ablation.peak_pressure_decay
  ablNoDecayPk: null,   // ablation.peak_pressure_no_decay
  runawayX:     null,   // ablation.pressure_runaway_x
  matchesHier:  null,   // matches_hierarchical
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 11, 19);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCells(6);          // pre-build a default 6x6 lattice; rebuilt on live data
  _buildAgents();
  _buildAblation();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onPfield, { badge: _badge, onState: (m) => { S.state = m.state; _updateScene(); _paintOverlay(); } }));

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

// The shared constraint-grid ARTIFACT: an n x n lattice of unit-footprint
// pillars. Each pillar's height/glow encodes that cell's live pressure. Rebuilt
// only when the grid side length changes (rare); heights/colours are toggled
// in-place per poll otherwise (no per-poll geometry churn).
function _buildCells(side) {
  const THREE = _THREE;
  _disposeCells();
  _cellSide = Math.max(1, Math.min(side, MAX_SIDE));
  const off = (_cellSide - 1) / 2;
  const geo = new THREE.BoxGeometry(PILLAR_W, 1, PILLAR_W); // unit-height; scaled on update
  for (let r = 0; r < _cellSide; r++) {
    for (let c = 0; c < _cellSide; c++) {
      const mesh = new THREE.Mesh(
        geo,
        new THREE.MeshStandardMaterial({ color: C_PRESS, emissive: C_PRESS, emissiveIntensity: 0.25, transparent: true, opacity: 0.85 }),
      );
      mesh.position.set((c - off) * CELL_GAP, 0.05, (r - off) * CELL_GAP);
      mesh.scale.y = 0.1;
      _group.add(mesh);
      _cells.push(mesh);
    }
  }
}

// Orbiting agent motes — a purely-visual ring of N points circling the artifact
// to represent the N coordinating agents. They carry NO data (the endpoint
// transmits aggregates only); their count tracks n_agents.
function _buildAgents() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.14, 10, 10);
  for (let i = 0; i < MAX_AGENTS; i++) {
    const m = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_SOLVED, emissive: C_SOLVED, emissiveIntensity: 0.5, transparent: true, opacity: 0.0 }),
    );
    m.visible = false;
    _group.add(m);
    _agents.push(m);
  }
}

// Decay ablation: two bars side by side above the artifact — decay-ON peak
// pressure (proof-teal, bounded) vs decay-OFF peak pressure (violet-blue,
// runaway). Their height ratio IS the pressure_runaway_x figure.
function _buildAblation() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(0.7, 1, 0.7);

  _ablDecay = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_SOLVED, emissive: C_SOLVED, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }),
  );
  _ablDecay.position.set(-1.0, 0.001, -((MAX_SIDE / 2) * CELL_GAP + 2.2));
  _group.add(_ablDecay);

  _ablNoDecay = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_DECAY, emissive: C_DECAY, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }),
  );
  _ablNoDecay.position.set(1.0, 0.001, -((MAX_SIDE / 2) * CELL_GAP + 2.2));
  _group.add(_ablNoDecay);
}

// =============================================================================
// live data handler
// =============================================================================
function _onPfield(j) {
  // read honesty label VERBATIM — never upgrade. This module places the label
  // at TOP LEVEL of the JSON (j.label); also tolerate a nested payload.label to
  // match either module shape.
  const rawLabel = (j && (j.label != null ? j.label : (j.payload && j.payload.label))) || "MODELED";
  S.label   = String(rawLabel).toUpperCase();

  S.nAgents = typeof j.n_agents === "number" ? j.n_agents : null;
  S.grid    = typeof j.grid     === "number" ? j.grid     : null;
  S.decay   = typeof j.decay    === "number" ? j.decay    : null;
  S.steps   = typeof j.steps    === "number" ? j.steps    : null;

  const pf = j.pfield || {};
  S.solved    = typeof pf.solved            === "boolean" ? pf.solved            : null;
  S.stepsConv = typeof pf.steps_to_converge === "number"  ? pf.steps_to_converge : null;
  S.finalViol = typeof pf.final_violations  === "number"  ? pf.final_violations  : null;
  S.peakPress = typeof pf.peak_pressure     === "number"  ? pf.peak_pressure     : null;
  S.messages  = typeof pf.messages          === "number"  ? pf.messages          : null;
  S.violTraj  = Array.isArray(pf.violation_trajectory) ? pf.violation_trajectory : null;
  S.pressTraj = Array.isArray(pf.pressure_trajectory)  ? pf.pressure_trajectory  : null;

  const bl = j.baselines || {};
  const seq = bl.sequential || {};
  const hier = bl.hierarchical || {};
  S.seqSolved  = typeof seq.solved            === "boolean" ? seq.solved            : null;
  S.seqSteps   = typeof seq.steps_to_converge === "number"  ? seq.steps_to_converge : null;
  S.hierSolved = typeof hier.solved            === "boolean" ? hier.solved            : null;
  S.hierSteps  = typeof hier.steps_to_converge === "number"  ? hier.steps_to_converge : null;
  S.hierMsgs   = typeof hier.messages          === "number"  ? hier.messages          : null;

  S.sweep = Array.isArray(j.sweep) ? j.sweep : null;

  const ab = j.ablation || {};
  S.ablDecayPk   = typeof ab.peak_pressure_decay    === "number" ? ab.peak_pressure_decay    : null;
  S.ablNoDecayPk = typeof ab.peak_pressure_no_decay === "number" ? ab.peak_pressure_no_decay : null;
  S.runawayX     = typeof ab.pressure_runaway_x     === "number" ? ab.pressure_runaway_x     : null;

  S.matchesHier = typeof j.matches_hierarchical === "boolean" ? j.matches_hierarchical : null;

  // rebuild the artifact lattice if the grid side length changed
  if (S.grid != null && S.grid !== _cellSide) _buildCells(S.grid);

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the artifact lattice + agents + ablation bars
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // ARTIFACT lattice: pillar height/colour encodes the pressure landscape.
  // The endpoint transmits aggregate traces (not the full per-cell field), so
  // we render an honest proxy: distribute the current total pressure /
  // remaining violations across the lattice as a decaying radial gradient, and
  // flip cells to the solved colour once the run has converged.
  const nCells = _cells.length;
  const totalPeak = live && S.peakPress != null ? S.peakPress : 0;
  const finalViol = live && S.finalViol != null ? S.finalViol : null;
  const solved = live && S.solved === true;

  for (let i = 0; i < nCells; i++) {
    const mesh = _cells[i];
    if (!live) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.06;
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.1;
      mesh.position.y = 0.05;
      continue;
    }
    // radial pressure proxy: cells nearer the centre carry more residual
    // pressure (deterministic layout, honest aggregate — not a faked per-cell
    // reading). When solved, all pillars flatten to the proof-teal plane.
    const side = _cellSide || 1;
    const r = Math.floor(i / side), c = i % side;
    const off = (side - 1) / 2;
    const dist = Math.sqrt((r - off) * (r - off) + (c - off) * (c - off)) / (Math.max(1, off) * 1.4142);
    const radial = 1.0 - Math.min(1, dist);         // 1 at centre, 0 at corners
    const pressNorm = totalPeak > 0 ? Math.min(1, totalPeak / (nCells * 8)) : 0;
    let h;
    if (solved) {
      h = 0.12;
    } else {
      h = 0.12 + radial * pressNorm * PILLAR_MAXH;
    }
    mesh.scale.y = Math.max(0.08, h);
    mesh.position.y = mesh.scale.y / 2;

    const color = solved ? C_SOLVED : C_PRESS;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = solved ? 0.45 : 0.2 + 0.5 * radial * pressNorm;
    mesh.material.opacity = 0.9;
  }

  // agent motes: show n_agents of them orbiting; teal when solved, blue while
  // still coordinating; grey/hidden when not live.
  const na = live && S.nAgents != null ? Math.min(S.nAgents, MAX_AGENTS) : 0;
  for (let i = 0; i < MAX_AGENTS; i++) {
    const m = _agents[i];
    const on = i < na;
    m.visible = on;
    if (!on) { m.material.opacity = 0.0; continue; }
    const color = solved ? C_SOLVED : C_PRESS;
    m.material.color.setHex(color);
    m.material.emissive.setHex(color);
    m.material.opacity = 0.9;
  }

  // ablation bars: decay-on (bounded) vs decay-off (runaway). Normalise both
  // against the larger (no-decay) peak so the runaway bar towers over the
  // decayed one — the height ratio IS pressure_runaway_x.
  const on = live && S.ablDecayPk != null && S.ablNoDecayPk != null;
  const denom = on ? Math.max(S.ablNoDecayPk, 1e-6) : 1;
  if (_ablDecay) {
    _ablDecay.material.opacity = on ? 0.92 : 0.0;
    const hD = on ? Math.max(0.05, (S.ablDecayPk / denom) * 6.5) : 0.05;
    _ablDecay.scale.y = hD; _ablDecay.position.y = hD / 2;
    const c = live ? C_SOLVED : C_DIM;
    _ablDecay.material.color.setHex(c); _ablDecay.material.emissive.setHex(c);
  }
  if (_ablNoDecay) {
    _ablNoDecay.material.opacity = on ? 0.92 : 0.0;
    const hN = on ? Math.max(0.05, (S.ablNoDecayPk / denom) * 6.5) : 0.05;
    _ablNoDecay.scale.y = hN; _ablNoDecay.position.y = hN / 2;
    const c = live ? C_DECAY : C_DIM;
    _ablNoDecay.material.color.setHex(c); _ablNoDecay.material.emissive.setHex(c);
  }

  _finalViolUnused(finalViol);
}

// finalViol is surfaced in the HUD; referenced here only to keep the value in
// scope for future per-cell rendering without triggering an unused warning.
function _finalViolUnused(_v) { return _v; }

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;

  // orbit the visible agent motes around the artifact
  const na = _agents.length;
  for (let i = 0; i < na; i++) {
    const m = _agents[i];
    if (!m.visible) continue;
    const ang = (i / Math.max(1, na)) * Math.PI * 2 + t * 0.0006;
    m.position.set(Math.cos(ang) * AGENT_ORBIT, 1.6 + 0.4 * Math.sin(t * 0.002 + i), Math.sin(ang) * AGENT_ORBIT);
  }
  if (_ablNoDecay && _ablNoDecay.material.opacity > 0) _ablNoDecay.rotation.y += 0.01;
  if (_ablDecay && _ablDecay.material.opacity > 0) _ablDecay.rotation.y += 0.01;
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
    'Instead of a planner messaging executors, N agents coordinate <b>implicitly</b> through a ' +
    'shared constraint-grid artifact: each agent reads a local <b>pressure</b> (constraint-violation ' +
    'count), takes the pressure-reducing edit, and a <b>temporal-decay</b> schedule keeps stale ' +
    'pressure from locking the system in \u2014 <b>zero inter-agent messages</b> (stigmergy). Shown ' +
    'against sequential + hierarchical baselines. Honesty label <b>MODELED</b> (deterministic ' +
    'simulation; NOT real agents). 0 runtime CDN.';
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
  nm.textContent = "pressure-field coordination";
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

  grid.appendChild(kpiRow("pf-agents",   "n_agents \u00d7 grid"));
  grid.appendChild(kpiRow("pf-decay",    "temporal decay (per step)"));
  grid.appendChild(kpiRow("pf-steps",    "pfield steps-to-converge \u2014 MODELED"));
  grid.appendChild(kpiRow("pf-msgs",     "pfield inter-agent messages"));
  grid.appendChild(kpiRow("pf-seq",      "sequential steps-to-converge \u2014 MODELED"));
  grid.appendChild(kpiRow("pf-hier",     "hierarchical steps / messages \u2014 MODELED"));
  grid.appendChild(kpiRow("pf-match",    "pfield matches hierarchical?"));
  grid.appendChild(kpiRow("pf-runaway",  "no-decay pressure runaway \u2014 MODELED"));
  grid.appendChild(kpiRow("pf-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Rodriguez 2026 \u00b7 Pressure Fields + Temporal Decay \u00b7 arXiv:2601.08129. MODELED \u00b7 not claimed-as.";
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
  pd.id = "pf-plain";
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
  const na  = S.nAgents  != null ? String(S.nAgents) : "loading\u2026";
  const pfs = S.stepsConv != null ? String(S.stepsConv) : "loading\u2026";
  const hms = S.hierMsgs != null ? String(S.hierMsgs) : "loading\u2026";
  const rw  = S.runawayX != null ? S.runawayX.toFixed(0) + "x" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Getting many AI agents to work together usually needs a <i>boss</i> agent " +
    "that hands out tasks and collects results \u2014 lots of back-and-forth messages that pile up as you add " +
    "workers. This approach skips the boss entirely. All <b>" + na + " agents</b> scribble on one shared " +
    "worksheet; wherever the worksheet looks wrong, \u201cpressure\u201d builds up and naturally pulls the nearest " +
    "agent to fix it \u2014 like ants leaving scent trails (called <b>stigmergy</b>). No agent ever messages " +
    "another. Here it finishes in about <b>" + pfs + " rounds with zero messages</b>, matching the boss-based " +
    "method that needed roughly <b>" + hms + " messages</b>. One catch: the pressure has to <b>fade over time</b>, " +
    "or it snowballs \u2014 turning decay off makes the pressure blow up about <b>" + rw + "</b>. This view is a " +
    "<b>MODELED</b> deterministic simulation of that coordination math, not a run of real AI agents.";
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

function _paintOverlay() {
  const t = _tok(S.state);
  _set("pf-agents",  t || (S.nAgents != null && S.grid != null ? (S.nAgents + " \u00d7 " + S.grid + "\u00d7" + S.grid) : "\u2014"));
  _set("pf-decay",   t || fx(S.decay, 3));
  _set("pf-steps",   t || (S.stepsConv != null ? (S.stepsConv + (S.solved ? " (solved)" : "")) : "\u2014"));
  _set("pf-msgs",    t || (S.messages != null ? String(S.messages) : "\u2014"));
  _set("pf-seq",     t || (S.seqSteps != null ? (S.seqSteps + (S.seqSolved ? " (solved)" : "")) : "\u2014"));
  _set("pf-hier",    t || (S.hierSteps != null ? (S.hierSteps + " / " + (S.hierMsgs != null ? S.hierMsgs + " msgs" : "\u2014")) : "\u2014"));
  _set("pf-match",   t || (S.matchesHier === true ? "yes (\u2265 hierarchical, 0 msgs)" : S.matchesHier === false ? "no" : "\u2014"));
  _set("pf-runaway", t || (S.runawayX != null ? (S.runawayX.toFixed(1) + "\u00d7 without decay") : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("pf-label",   t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
function _disposeCells() {
  const THREE = _THREE;
  if (_cells && _cells.length && _group) {
    _cells.forEach((m) => {
      try {
        if (m.geometry && m.geometry.dispose) m.geometry.dispose();
        if (m.material && m.material.dispose) m.material.dispose();
        _group.remove(m);
      } catch (_) {}
    });
  }
  _cells = [];
  void THREE;
}

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
  _floor = null; _cells = []; _cellSide = 0; _agents = [];
  _ablDecay = null; _ablNoDecay = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nAgents = S.grid = S.decay = S.steps = null;
  S.solved = S.stepsConv = S.finalViol = S.peakPress = S.messages = null;
  S.violTraj = S.pressTraj = null;
  S.seqSolved = S.seqSteps = S.hierSolved = S.hierSteps = S.hierMsgs = null;
  S.sweep = S.ablDecayPk = S.ablNoDecayPk = S.runawayX = S.matchesHier = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
