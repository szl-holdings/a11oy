// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/kla.js — KACZMARZ LINEAR ATTENTION (KLA) organ for the holographic
// frontier ring. Visualizes the recurrent linear-attention memory state being
// UPDATED, one streamed key-value pair at a time, by an orthogonal Kaczmarz
// projection onto the constraint S·k = v — a principled scalar replacing the
// ad-hoc gate of gated linear attention. Two convergence tracks race along a
// pipeline: KLA (proof-teal) vs the ad-hoc GATED baseline (grey), heights driven
// by their live running reconstruction error from
// /api/killinchu/v1/kla/update. A HUD shows kla vs gated final error, the
// improvement_ratio, and convergence steps. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   dim, steps, lr, tol, kla_final_recon_error, gated_final_recon_error,
//   kla_convergence_step, gated_convergence_step, improvement_ratio,
//   kla_error_curve[], gated_error_curve[]
//
// LEADER ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   KLA — Kaczmarz Linear Attention (projection update rule modeled here):
//     (2026) arXiv:2605.08587
//     https://arxiv.org/abs/2605.08587
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the Kaczmarz
//   projection state-update arithmetic; NOT a trained GLA model; NEVER-CLAIMED-AS
//   a production kernel). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (streamed key-value / pipeline spine), violet-
//   blue 0x8a6bff (constraint hyperplane accent), proof-teal 0x3af4c8 (KLA
//   convergence track / HUD accent), greys (gated baseline / degraded state).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "kla";
const TITLE = "Kaczmarz Linear Attention · Projection State-Update (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the KLA organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/kla/update?seed=42&dim=8&steps=256&lr=1.0";

// data-viz hues — purple BANNED
const C_STREAM = 0x5b8dee;  // lattice-blue (streamed key-value pair / pipeline spine)
const C_PLANE  = 0x8a6bff;  // violet-blue (constraint hyperplane / projection accent)
const C_KLA    = 0x3af4c8;  // proof-teal (KLA convergence track / HUD accent)
const C_GATED  = 0x5a6570;  // grey (ad-hoc gated baseline track)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// convergence-track pipeline layout geometry
const TRACK_LEN   = 22.0;  // world-units the two tracks span along X (stream axis)
const N_BARS      = 32;    // number of sampled error points rendered per track
const BAR_W       = 0.42;  // bar width
const KLA_Z       = -1.4;  // Z lane for the KLA track
const GATED_Z     = 1.4;   // Z lane for the gated baseline track
const MAX_H       = 6.0;   // max bar height (world units) at max error

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor    = null;
let _spine    = null;               // THREE.Line — stream axis (pipeline spine)
let _plane    = null;               // THREE.Mesh — constraint hyperplane accent
let _klaBars   = [];                // Array<THREE.Mesh> — KLA convergence track
let _gatedBars = [];                // Array<THREE.Mesh> — gated baseline track
let _marker    = null;              // THREE.Mesh — projection "head" pulsing marker

// live state
const S = {
  label:      null,
  dim:        null,   // dim
  steps:      null,   // steps
  lr:         null,   // lr
  tol:        null,   // tol
  klaErr:     null,   // kla_final_recon_error
  gatedErr:   null,   // gated_final_recon_error
  klaConv:    null,   // kla_convergence_step
  gatedConv:  null,   // gated_convergence_step
  improve:    null,   // improvement_ratio
  klaCurve:   null,   // kla_error_curve[]
  gatedCurve: null,   // gated_error_curve[]
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(2, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpine();
  _buildPlane();
  _buildTracks();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onKla, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

function _buildSpine() {
  const THREE = _THREE;
  const x0 = -TRACK_LEN / 2, x1 = TRACK_LEN / 2;
  const pts = [new THREE.Vector3(x0, 0, 0), new THREE.Vector3(x1, 0, 0)];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: C_STREAM, transparent: true, opacity: 0.5 });
  _spine = new THREE.Line(geo, mat);
  _group.add(_spine);
}

// A translucent tilted plane standing in for the S·k = v constraint hyperplane
// that each Kaczmarz step projects the memory state onto.
function _buildPlane() {
  const THREE = _THREE;
  const geo = new THREE.PlaneGeometry(5.5, 5.5, 1, 1);
  const mat = new THREE.MeshStandardMaterial({
    color: C_PLANE, emissive: C_PLANE, emissiveIntensity: 0.14,
    transparent: true, opacity: 0.10, side: THREE.DoubleSide, wireframe: false,
  });
  _plane = new THREE.Mesh(geo, mat);
  _plane.rotation.y = Math.PI / 5;
  _plane.rotation.x = Math.PI / 12;
  _plane.position.set(-TRACK_LEN / 2 + 3.0, 2.6, 0);
  _group.add(_plane);
}

// Pre-allocate two fixed rows of bars: KLA lane + gated lane, N_BARS each.
// We toggle height/color/opacity in-place as live curve data arrives (no
// per-poll geometry churn).
function _buildTracks() {
  const THREE = _THREE;
  const x0 = -TRACK_LEN / 2;
  const dx = TRACK_LEN / (N_BARS - 1);
  const barGeo = new THREE.BoxGeometry(BAR_W, 1, BAR_W); // unit height; scaled in Y

  for (let i = 0; i < N_BARS; i++) {
    const x = x0 + i * dx;

    const klaMesh = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_KLA, emissive: C_KLA, emissiveIntensity: 0.3, transparent: true, opacity: 0.0 }),
    );
    klaMesh.position.set(x, 0.0, KLA_Z);
    klaMesh.scale.y = 0.001;
    klaMesh.visible = false;
    _group.add(klaMesh);
    _klaBars.push(klaMesh);

    const gatedMesh = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_GATED, emissive: C_GATED, emissiveIntensity: 0.12, transparent: true, opacity: 0.0 }),
    );
    gatedMesh.position.set(x, 0.0, GATED_Z);
    gatedMesh.scale.y = 0.001;
    gatedMesh.visible = false;
    _group.add(gatedMesh);
    _gatedBars.push(gatedMesh);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.30, 1),
    new THREE.MeshStandardMaterial({ color: C_KLA, emissive: C_KLA, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(-TRACK_LEN / 2, 0.4, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onKla(j) {
  // Honesty label read VERBATIM — never upgraded. This module's endpoint puts
  // the label at TOP LEVEL (j.label); we also defensively check payload.label
  // in case the response is wrapped, then fall back to the honest default.
  const rawLabel = (j && j.label != null) ? j.label
                 : (j && j.payload && j.payload.label != null) ? j.payload.label
                 : "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.dim        = typeof j.dim                     === "number" ? j.dim                     : null;
  S.steps      = typeof j.steps                   === "number" ? j.steps                   : null;
  S.lr         = typeof j.lr                       === "number" ? j.lr                      : null;
  S.tol        = typeof j.tol                      === "number" ? j.tol                     : null;
  S.klaErr     = typeof j.kla_final_recon_error    === "number" ? j.kla_final_recon_error   : null;
  S.gatedErr   = typeof j.gated_final_recon_error  === "number" ? j.gated_final_recon_error : null;
  S.klaConv    = typeof j.kla_convergence_step      === "number" ? j.kla_convergence_step    : null;
  S.gatedConv  = typeof j.gated_convergence_step    === "number" ? j.gated_convergence_step  : null;
  S.improve    = typeof j.improvement_ratio         === "number" ? j.improvement_ratio       : null;
  S.klaCurve   = Array.isArray(j.kla_error_curve)   ? j.kla_error_curve   : null;
  S.gatedCurve = Array.isArray(j.gated_error_curve) ? j.gated_error_curve : null;

  _updateTracks();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the two convergence tracks from live curve data
// =============================================================================
function _updateTracks() {
  const live = S.state === "live";
  const kla = live && S.klaCurve && S.klaCurve.length ? S.klaCurve : [];
  const gated = live && S.gatedCurve && S.gatedCurve.length ? S.gatedCurve : [];

  // shared error scale so the two lanes are directly comparable (higher bar =
  // higher reconstruction error = worse). Normalize by the max error seen.
  let maxErr = 0.0;
  for (let i = 0; i < kla.length; i++) if (kla[i] > maxErr) maxErr = kla[i];
  for (let i = 0; i < gated.length; i++) if (gated[i] > maxErr) maxErr = gated[i];
  if (maxErr <= 1e-9) maxErr = 1.0;

  function fill(bars, curve, colHi, colLo, emiHi, emiLo) {
    for (let i = 0; i < N_BARS; i++) {
      const mesh = bars[i];
      // sample the (possibly shorter/longer) curve across the N_BARS bars
      const showBar = live && curve.length > 0;
      if (!showBar) { mesh.visible = false; mesh.scale.y = 0.001; mesh.material.opacity = 0.0; continue; }
      const idx = Math.min(curve.length - 1, Math.round((i / (N_BARS - 1)) * (curve.length - 1)));
      const err = curve[idx];
      const h = Math.max(0.02, (err / maxErr) * MAX_H);
      mesh.visible = true;
      mesh.scale.y = h;
      mesh.position.y = h / 2;
      mesh.material.color.setHex(colHi);
      mesh.material.emissive.setHex(emiHi);
      mesh.material.emissiveIntensity = emiLo;
      mesh.material.opacity = 0.92;
    }
  }

  fill(_klaBars, kla, C_KLA, C_KLA, 0.55, 0.5);
  fill(_gatedBars, gated, C_GATED, C_GATED, 0.2, 0.16);

  // spine + plane + marker degrade to grey when not live
  _spine.material.color.setHex(live ? C_STREAM : C_DIM);
  _spine.material.opacity = live ? 0.5 : 0.15;
  if (_plane) {
    _plane.material.color.setHex(live ? C_PLANE : C_DIM);
    _plane.material.emissive.setHex(live ? C_PLANE : C_DIM);
    _plane.material.opacity = live ? 0.12 : 0.05;
  }
  if (_marker) {
    if (live && S.improve != null) {
      _marker.material.color.setHex(C_KLA);
      _marker.material.emissive.setHex(C_KLA);
      _marker.material.opacity = 0.85;
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  if (_plane) _plane.rotation.z = Math.sin(t * 0.0005) * 0.06;
  if (_marker) {
    _marker.rotation.y += 0.025;
    _marker.rotation.x += 0.012;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _marker.scale.setScalar(pulse);
    // marker sweeps along the stream axis to read as the "projection head"
    const x0 = -TRACK_LEN / 2, x1 = TRACK_LEN / 2;
    const frac = (Math.sin(t * 0.0006) * 0.5 + 0.5);
    _marker.position.x = x0 + frac * (x1 - x0);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "projection update", name: "kla" }],
    legend: ["MODELED", "SAMPLE"],
    description:
    'A linear-attention layer stores memory as a matrix <b>S</b>. Each new key-value pair ' +
    '(<b>k</b>,<b>v</b>) defines a constraint <b>S·k = v</b>; <b>KLA</b> updates the state by ' +
    'the orthogonal <b>Kaczmarz projection</b> onto that constraint ' +
    '(step = lr·(v \\u2212 S·k) k<sup>T</sup>/(k·k)) \\u2014 a <i>principled</i> scalar replacing ' +
    'the <b>ad-hoc gate</b> of gated linear attention. Teal track = KLA, grey track = gated ' +
    'baseline; bar height = reconstruction error. ' +
    'Honesty label <b>MODELED</b> (deterministic projection simulation; NOT a trained model). 0 runtime CDN.',
    citations:
      "Kaczmarz Linear Attention arXiv:2605.08587 (orthogonal projection state-update vs ad-hoc gate). MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["kla-dim"]       = _show.addField("state dim (S is dim\\u00d7dim)");
  _el["kla-steps"]     = _show.addField("key-value pairs streamed");
  _el["kla-klaerr"]    = _show.addField("KLA recon error \\u2014 MODELED");
  _el["kla-gatederr"]  = _show.addField("gated recon error (baseline)");
  _el["kla-improve"]   = _show.addField("improvement_ratio (gated\\u00f7kla)");
  _el["kla-klaconv"]   = _show.addField("KLA convergence step");
  _el["kla-gatedconv"] = _show.addField("gated convergence step");
  _el["kla-label"]     = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const imp = S.improve != null ? S.improve.toFixed(2) + "\u00d7" : "loading\u2026";
  const ke  = S.klaErr != null ? S.klaErr.toFixed(3) : "loading\u2026";
  const ge  = S.gatedErr != null ? S.gatedErr.toFixed(3) : "loading\u2026";
  return (
    "<b>What this means:</b> A fast \\u201clinear attention\\u201d model remembers things in a running " +
    "memory <b>M</b> instead of re-reading the whole past every time. When a new fact arrives, older " +
    "systems just <i>fade</i> the memory by a hand-tuned amount (an \\u201cad-hoc gate\\u201d) and hope " +
    "for the best. <b>KLA</b> instead does the geometrically <i>correct</i> thing: it nudges the memory " +
    "by exactly the right, calculated amount so the new fact is stored while disturbing old facts as " +
    "little as possible \\u2014 like adjusting one note in a chord without knocking the others out of tune. " +
    "Here KLA rebuilds the stream of facts with error <b>" + ke + "</b> versus the old gate\\u2019s <b>" + ge + "</b>, " +
    "about a <b>" + imp + "</b> improvement, and it locks in sooner. Plain: a principled dial replaces a " +
    "guessed one, so the model remembers more accurately. This view is a <b>MODELED</b> simulation of " +
    "the projection math (arXiv:2605.08587), not a run of a trained model.");
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
  _set("kla-dim",       t || (S.dim   != null ? String(S.dim)   : "\u2014"));
  _set("kla-steps",     t || (S.steps != null ? String(S.steps) : "\u2014"));
  _set("kla-klaerr",    t || fx(S.klaErr, 4));
  _set("kla-gatederr",  t || fx(S.gatedErr, 4));
  _set("kla-improve",   t || (S.improve != null ? S.improve.toFixed(3) + "\u00d7" : "\u2014"));
  _set("kla-klaconv",   t || (S.klaConv   != null ? String(S.klaConv)   : "\u2014"));
  _set("kla-gatedconv", t || (S.gatedConv != null ? String(S.gatedConv) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("kla-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("kla", S.label || "MODELED", { text: "projection update" }); _show.refreshPlain(); }
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
  _floor = null; _spine = null; _plane = null;
  _klaBars = []; _gatedBars = []; _marker = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.dim = S.steps = S.lr = S.tol = null;
  S.klaErr = S.gatedErr = S.klaConv = S.gatedConv = S.improve = null;
  S.klaCurve = S.gatedCurve = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
