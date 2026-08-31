// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/flowmatch.js — RECTIFIED-FLOW / FLOW-MATCHING ODE-SAMPLER organ for the
// holographic frontier ring. Renders the ODE trajectory of a rectified-flow sampler:
// dx/dt = v(x,t) = x1 - x0 (a constant straight-line velocity field), integrated with
// explicit-Euler steps from a noise point x0 ~ N(0,I) to a target point x1.
//
// Renders a 3D flow path driven by a live closed-form snapshot from
// /api/killinchu/v1/flowmatch/sample:
//   1. A noise-cloud marker at x0 (start of the flow).
//   2. The Euler-integrated trajectory as a growing line from x0 toward x1 — for the
//      rectified (straight-line) case this path IS a straight line.
//   3. A target marker at x1 (end of the flow).
// A HUD shows final_error DROPPING as steps increase (few-step vs many-step comparison)
// plus straightness_score and steps_to_converge — the rectified-flow win: few steps
// already converge. Honesty label "MODELED" is read VERBATIM from the JSON and
// displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors testtime.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   dims, steps, x0, x1, trajectory[], final_error, straightness_score,
//   steps_to_converge, few_vs_many{few_steps,few_step_error,many_steps,many_step_error}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Flow Matching for Generative Modeling: Lipman et al. 2022, arXiv:2210.02747
//     https://arxiv.org/abs/2210.02747
//   Rectified Flow ("Flow Straight and Fast"): Liu et al. 2022, arXiv:2209.03003
//     https://arxiv.org/abs/2209.03003
//   FLUX (production rectified-flow model, Black Forest Labs — cited only, NEVER
//     claimed as SZL's own): https://github.com/black-forest-labs/flux
//
// HONESTY LABELS: MODELED (deterministic analytic rectified-flow ODE integration on a
//   toy noise->target case; NOT a trained flow/diffusion model; NEVER-CLAIMED-AS FLUX
//   or Stable Diffusion 3). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (trajectory path), violet-blue 0x8a6bff (noise/target
//   markers — data-viz only), proof-teal 0x3af4c8 (HUD accent / convergence marker).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "flowmatch";
const TITLE = "Rectified Flow · Flow-Matching ODE Sampler (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the flow-matching organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/flowmatch/sample?seed=42&steps=8&dims=3";

// data-viz hues — purple BANNED
const C_PATH    = 0x5b8dee;  // lattice-blue (ODE trajectory path)
const C_MARKERS = 0x8a6bff;  // violet-blue (x0 noise / x1 target markers — data-viz only)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal accent (HUD / convergence marker)
const C_GRID    = 0x1b3a44;  // floor / link colour

// path layout geometry
const PATH_SCALE = 1.6;   // world-units per unit of raw x/y/z coordinate

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _pathLine  = null;    // THREE.Line — Euler-integrated trajectory
let _pathDots  = [];      // Array<THREE.Mesh> — markers along the trajectory
let _x0Marker  = null;    // THREE.Mesh — noise-cloud start marker
let _x1Marker  = null;    // THREE.Mesh — target end marker
let _converge  = null;    // THREE.Mesh — pulsing "converged" HUD marker
let _floor     = null;

// live state
const S = {
  label:        null,
  dims:         null,
  steps:        null,
  x0:           null,
  x1:           null,
  trajectory:   null,   // [{t, x}, ...]
  finalError:   null,
  straightness: null,
  stepsToConverge: null,
  fewSteps:     null,
  fewError:     null,
  manySteps:    null,
  manyError:    null,
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(2, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(2, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPath();
  _buildMarkers();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSample, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate the trajectory line geometry with a fixed max point-count; update
// point positions in-place as live data arrives (no per-poll geometry churn).
const _MAX_PTS = 130; // covers up to 128-step many-step trajectories

function _buildPath() {
  const THREE = _THREE;
  const pts = new Array(_MAX_PTS).fill(0).map(() => new THREE.Vector3(0, 0, 0));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: C_PATH, transparent: true, opacity: 0.85, linewidth: 2 });
  _pathLine = new THREE.Line(geo, mat);
  _group.add(_pathLine);

  const dotGeo = new THREE.SphereGeometry(0.07, 10, 8);
  for (let i = 0; i < _MAX_PTS; i++) {
    const m = new THREE.Mesh(dotGeo, new THREE.MeshStandardMaterial({ color: C_PATH, emissive: C_PATH, emissiveIntensity: 0.3 }));
    m.visible = false;
    _group.add(m);
    _pathDots.push(m);
  }
}

function _buildMarkers() {
  const THREE = _THREE;
  // noise-cloud start marker (x0) — wireframe icosahedron, violet-blue
  _x0Marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.28, 1),
    new THREE.MeshStandardMaterial({ color: C_MARKERS, emissive: C_MARKERS, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _group.add(_x0Marker);

  // target end marker (x1) — solid octahedron, violet-blue
  _x1Marker = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.30, 0),
    new THREE.MeshStandardMaterial({ color: C_MARKERS, emissive: C_MARKERS, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }),
  );
  _group.add(_x1Marker);

  // convergence pulse marker — proof-teal, sits at the ODE's final point
  _converge = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.16, 1),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.6, wireframe: true, transparent: true, opacity: 0.9 }),
  );
  _group.add(_converge);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSample(j) {
  // read honesty label VERBATIM — never upgrade
  S.label        = (j.label || "MODELED").toUpperCase();
  S.dims         = typeof j.dims  === "number" ? j.dims  : null;
  S.steps        = typeof j.steps === "number" ? j.steps : null;
  S.x0           = Array.isArray(j.x0) ? j.x0 : null;
  S.x1           = Array.isArray(j.x1) ? j.x1 : null;
  S.trajectory   = Array.isArray(j.trajectory) ? j.trajectory : null;
  S.finalError   = typeof j.final_error === "number" ? j.final_error : null;
  S.straightness = typeof j.straightness_score === "number" ? j.straightness_score : null;
  S.stepsToConverge = typeof j.steps_to_converge === "number" ? j.steps_to_converge : null;

  const fvm = j.few_vs_many || {};
  S.fewSteps   = typeof fvm.few_steps  === "number" ? fvm.few_steps  : null;
  S.fewError   = typeof fvm.few_step_error  === "number" ? fvm.few_step_error  : null;
  S.manySteps  = typeof fvm.many_steps === "number" ? fvm.many_steps : null;
  S.manyError  = typeof fvm.many_step_error === "number" ? fvm.many_step_error : null;

  _updatePath();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the trajectory path + markers from live data
// =============================================================================
function _proj(vec) {
  // Project a small dims-length vector (2..8 dims) down to 3D world coords by
  // taking the first 3 components (pad with 0 if fewer). Pure display mapping —
  // does not alter any reported numeric values.
  const x = (vec[0] || 0) * PATH_SCALE;
  const y = (vec[1] || 0) * PATH_SCALE;
  const z = (vec[2] || 0) * PATH_SCALE;
  return [x, y, z];
}

function _updatePath() {
  const live = S.state === "live";

  if (live && S.trajectory && S.trajectory.length) {
    const pos = _pathLine.geometry.attributes.position;
    const n = Math.min(_MAX_PTS, S.trajectory.length);
    for (let i = 0; i < _MAX_PTS; i++) {
      const row = S.trajectory[Math.min(i, n - 1)];
      const [x, y, z] = _proj(row.x || []);
      pos.setXYZ(i, x, y, z);
      if (i < n) {
        _pathDots[i].position.set(x, y, z);
        _pathDots[i].visible = true;
      } else {
        _pathDots[i].visible = false;
      }
    }
    pos.needsUpdate = true;
    _pathLine.geometry.computeBoundingSphere();
    _pathLine.material.color.setHex(C_PATH);
    _pathLine.material.opacity = 0.85;

    // x0 / x1 markers
    if (S.x0) { const [x, y, z] = _proj(S.x0); _x0Marker.position.set(x, y, z); }
    if (S.x1) { const [x, y, z] = _proj(S.x1); _x1Marker.position.set(x, y, z); }
    _x0Marker.material.color.setHex(C_MARKERS); _x0Marker.material.emissive.setHex(C_MARKERS); _x0Marker.material.opacity = 0.85;
    _x1Marker.material.color.setHex(C_MARKERS); _x1Marker.material.emissive.setHex(C_MARKERS); _x1Marker.material.opacity = 0.9;

    // convergence marker sits at the ODE's final integrated point
    const lastRow = S.trajectory[S.trajectory.length - 1];
    if (lastRow && lastRow.x) {
      const [x, y, z] = _proj(lastRow.x);
      _converge.position.set(x, y, z);
    }
    _converge.material.color.setHex(C_ACCENT);
    _converge.material.emissive.setHex(C_ACCENT);
    _converge.material.opacity = 0.9;
  } else {
    _pathDots.forEach((d) => { d.visible = false; });
    _pathLine.material.color.setHex(C_DIM);
    _pathLine.material.opacity = 0.25;
    _x0Marker.material.color.setHex(C_DIM); _x0Marker.material.emissive.setHex(C_DIM); _x0Marker.material.opacity = 0.3;
    _x1Marker.material.color.setHex(C_DIM); _x1Marker.material.emissive.setHex(C_DIM); _x1Marker.material.opacity = 0.3;
    _converge.material.color.setHex(C_DIM); _converge.material.emissive.setHex(C_DIM); _converge.material.opacity = 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00010) * 0.15;
  if (_converge) {
    _converge.rotation.y += 0.02;
    _converge.rotation.x += 0.01;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _converge.scale.setScalar(pulse);
  }
  if (_x1Marker) { _x1Marker.rotation.y += 0.01; }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "flow-matching", name: "fm" }],
    legend: ["MODELED"],
    description:
      'A <b>rectified-flow ODE sampler</b>: integrate dx/dt = v(x,t) = x1 \u2212 x0 (a ' +
      '<b>straight-line velocity field</b>) from noise x0 to a target x1 with Euler steps. ' +
      'Honesty label <b>MODELED</b> (analytic toy case; NOT a trained flow/diffusion model; ' +
      'never claimed as FLUX or SD3). 0 runtime CDN.',
    citations:
      "Lipman et al. arXiv:2210.02747 (Flow Matching) \u00b7 Liu et al. arXiv:2209.03003 (Rectified Flow) \u00b7 FLUX github.com/black-forest-labs/flux (cited only). MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["fm-dims"]     = _show.addField("dims");
  _el["fm-steps"]    = _show.addField("steps (Euler)");
  _el["fm-err"]      = _show.addField("final_error \u2014 MODELED");
  _el["fm-straight"] = _show.addField("straightness_score");
  _el["fm-conv"]     = _show.addField("steps_to_converge");
  _el["fm-few"]      = _show.addField("few-step error");
  _el["fm-many"]     = _show.addField("many-step error");
  _el["fm-label"]    = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const steps = S.steps != null ? String(S.steps) : "loading\u2026";
  const few   = S.fewSteps != null ? String(S.fewSteps) : "1";
  const many  = S.manySteps != null ? String(S.manySteps) : "128";
  const str   = S.straightness != null ? (S.straightness * 100).toFixed(2) + "%" : "loading\u2026";
  return (
    "<b>What this means:</b> Older generative-AI samplers (like standard diffusion) need " +
    "<i>many small steps</i> to trace a curved path from random noise to a real output. " +
    "<b>Rectified flow</b> instead learns (or here, defines) a <b>straight-line path</b> " +
    "from noise to the target, so a model can take just <b>" + few + " step</b> and land " +
    "almost exactly on target \u2014 versus needing <b>" + many + " steps</b> the old way, " +
    "with barely any extra benefit. The path here is <b>" + str + " straight</b>. This is " +
    "the same core idea behind fast production image generators like FLUX. This view is a " +
    "<b>MODELED</b> analytic toy case (not a trained model, not FLUX itself), used at " +
    "steps=" + steps + " to show the effect live.");
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
function sci(v, d) { return typeof v === "number" ? v.toExponential(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("fm-dims",     t || (S.dims != null ? String(S.dims) : "\u2014"));
  _set("fm-steps",    t || (S.steps != null ? String(S.steps) : "\u2014"));
  _set("fm-err",      t || sci(S.finalError, 3));
  _set("fm-straight", t || pct(S.straightness, 2));
  _set("fm-conv",     t || (S.stepsToConverge != null ? String(S.stepsToConverge) : "\u2014"));
  _set("fm-few",      t || (S.fewSteps != null ? `${sci(S.fewError, 2)} (n=${S.fewSteps})` : "\u2014"));
  _set("fm-many",     t || (S.manySteps != null ? `${sci(S.manyError, 2)} (n=${S.manySteps})` : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("fm-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("fm", S.label || "MODELED", { text: "flow-matching" }); _show.refreshPlain(); }
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
  _pathLine = null; _pathDots = []; _x0Marker = null; _x1Marker = null; _converge = null; _floor = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.dims = S.steps = S.x0 = S.x1 = S.trajectory = null;
  S.finalError = S.straightness = S.stepsToConverge = null;
  S.fewSteps = S.fewError = S.manySteps = S.manyError = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
