// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/matgran.js — MATRYOSHKA REPRESENTATION GRANULARITY (matgran) organ
// for the holographic frontier ring (MRL / MIPIC-style). Renders the accuracy-
// vs-dimensionality curve as two rising ribbons of bars over a shared prefix
// axis {2,4,8,16,32}: a lattice-blue ribbon for the NESTED (front-loaded)
// embedding and a grey ribbon for the NON-NESTED control. A proof-teal marker
// tracks the storage saving at each prefix (taller bar = bigger cache saving).
// The honest signal reads directly off the geometry: the nested ribbon stays
// tall (accurate) at extreme-low prefixes while the non-nested ribbon collapses.
// A HUD shows per-prefix nested/non-nested accuracy + storage saving read live
// from /api/killinchu/v1/matgran/truncate. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors mla.js / ternary.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   D, prefixes, curve[{d, nested_accuracy, non_nested_accuracy, storage_saving}],
//   full_accuracy
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   MIPIC (2026 anchor; refines nested representations via self-distilled
//   intra-relational alignment + progressive information chaining):
//     Phung Gia Huy et al. 2026, arXiv:2604.24374
//     https://arxiv.org/abs/2604.24374
//   Matryoshka Representation Learning (foundational):
//     Kusupati et al. 2022, arXiv:2205.13147
//     https://arxiv.org/abs/2205.13147
//
// HONESTY LABELS: MODELED (deterministic toy analytic sim of the nested-
//   representation mechanism; NOT a trained encoder; NEVER-CLAIMED-AS MIPIC or
//   MRL). Read verbatim from JSON (top-level 'label' OR nested 'payload.label');
//   never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (nested ribbon), proof-teal 0x3af4c8 (storage-
//   saving markers / HUD accent), greys (non-nested ribbon / degraded state).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "matgran";
const TITLE = "Matryoshka Representation Granularity · Prefix-Truncation Simulator (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin. This keeps the matgran organ's rebuilds/faults isolated from the
// flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/matgran/truncate?seed=42&D=32&prefixes=2,4,8,16,32&num_classes=6&num_points=240&nesting=1&distill=1";

// data-viz hues — purple BANNED
const C_NESTED  = 0x5b8dee;  // lattice-blue (nested / front-loaded ribbon)
const C_SAVE    = 0x3af4c8;  // proof-teal (storage-saving markers / HUD accent)
const C_NONNEST = 0x8a9099;  // grey (non-nested control ribbon)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// bar/ribbon layout geometry
const BAR_HALF_W = 0.34;   // bar half-width/depth (box footprint)
const COL_STEP   = 1.7;    // world-units between adjacent prefix columns
const ROW_GAP    = 1.5;    // world-units between the nested and non-nested rows (z)
const MAX_BAR_H  = 7.0;    // world-units — bar height at accuracy = 1.0
const MIN_BAR_H  = 0.12;   // world-units — floor height so a bar never vanishes
const SAVE_H     = 4.0;    // world-units — storage-saving marker height at saving = 1.0

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor    = null;
let _nestBars = [];   // THREE.Mesh[] — nested-embedding accuracy bars (lattice-blue)
let _nonBars  = [];   // THREE.Mesh[] — non-nested control accuracy bars (grey)
let _saveMk   = [];   // THREE.Mesh[] — storage-saving markers (proof-teal)
let _nestTargetH = [];
let _nonTargetH  = [];
let _saveTargetH = [];

// live state
const S = {
  label:    null,
  D:        null,   // full embedding dim
  prefixes: null,   // list of prefix widths
  curve:    null,   // list of {d, nested_accuracy, non_nested_accuracy, storage_saving}
  fullAcc:  null,   // full_accuracy
  state:    "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(7, 6, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onMatgran, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _repaintBars(); } }));

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

// A default of 5 prefix columns; each column has: a lattice-blue nested bar
// (front z-row), a grey non-nested bar (back z-row), and a proof-teal storage-
// saving marker (thin, offset). We build the max expected count (5) up front
// and hide extras / show fewer as the live curve dictates. Base of each bar
// sits at y=0 via geometry translation, so scaling Y grows it upward.
function _buildBars() {
  const THREE = _THREE;
  const N = 5; // default prefix count {2,4,8,16,32}

  const barGeo = new THREE.BoxGeometry(BAR_HALF_W * 2, 1, BAR_HALF_W * 2);
  barGeo.translate(0, 0.5, 0);
  const saveGeo = new THREE.BoxGeometry(BAR_HALF_W * 0.9, 1, BAR_HALF_W * 0.9);
  saveGeo.translate(0, 0.5, 0);

  for (let i = 0; i < N; i++) {
    const x = i * COL_STEP;

    const nb = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_NESTED, emissive: C_NESTED, emissiveIntensity: 0.3, transparent: true, opacity: 0.9 }),
    );
    nb.position.set(x, 0, -ROW_GAP / 2);
    nb.scale.set(1, MIN_BAR_H, 1);
    nb.visible = false;
    _group.add(nb); _nestBars.push(nb);

    const ob = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_NONNEST, emissive: C_NONNEST, emissiveIntensity: 0.14, transparent: true, opacity: 0.7 }),
    );
    ob.position.set(x, 0, ROW_GAP / 2);
    ob.scale.set(1, MIN_BAR_H, 1);
    ob.visible = false;
    _group.add(ob); _nonBars.push(ob);

    const mk = new THREE.Mesh(
      saveGeo,
      new THREE.MeshStandardMaterial({ color: C_SAVE, emissive: C_SAVE, emissiveIntensity: 0.42, transparent: true, opacity: 0.92 }),
    );
    mk.position.set(x + BAR_HALF_W * 1.5, 0, 0);
    mk.scale.set(1, MIN_BAR_H, 1);
    mk.visible = false;
    _group.add(mk); _saveMk.push(mk);

    _nestTargetH.push(MIN_BAR_H);
    _nonTargetH.push(MIN_BAR_H);
    _saveTargetH.push(MIN_BAR_H);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onMatgran(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label    = String(lbl).toUpperCase();
  S.D        = src && typeof src.D === "number" ? src.D : null;
  S.prefixes = src && Array.isArray(src.prefixes) ? src.prefixes : null;
  S.curve    = src && Array.isArray(src.curve) ? src.curve : null;
  S.fullAcc  = src && typeof src.full_accuracy === "number" ? src.full_accuracy : null;

  _updateBars();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the bars + markers from live data
// =============================================================================
function _updateBars() {
  const live = S.state === "live" && Array.isArray(S.curve);
  const n = _nestBars.length;

  for (let i = 0; i < n; i++) {
    const row = live && i < S.curve.length ? S.curve[i] : null;
    const show = !!row;

    _nestBars[i].visible = show;
    _nonBars[i].visible = show;
    _saveMk[i].visible = show;

    if (!row) {
      _nestTargetH[i] = MIN_BAR_H;
      _nonTargetH[i] = MIN_BAR_H;
      _saveTargetH[i] = MIN_BAR_H;
      continue;
    }

    const na = typeof row.nested_accuracy === "number" ? row.nested_accuracy : 0;
    const oa = typeof row.non_nested_accuracy === "number" ? row.non_nested_accuracy : 0;
    const sv = typeof row.storage_saving === "number" ? row.storage_saving : 0;

    _nestTargetH[i] = Math.max(MIN_BAR_H, MAX_BAR_H * na);
    _nonTargetH[i]  = Math.max(MIN_BAR_H, MAX_BAR_H * oa);
    _saveTargetH[i] = Math.max(MIN_BAR_H, SAVE_H * sv);
  }

  _repaintBars();
}

function _repaintBars() {
  const live = S.state === "live" && Array.isArray(S.curve);
  const nestColor = live ? C_NESTED : C_DIM;
  const nonColor  = live ? C_NONNEST : C_DIM;
  const saveColor = live ? C_SAVE : C_DIM;
  for (let i = 0; i < _nestBars.length; i++) {
    _nestBars[i].material.color.setHex(nestColor);
    _nestBars[i].material.emissive.setHex(nestColor);
    _nestBars[i].material.opacity = live ? 0.9 : 0.2;
    _nonBars[i].material.color.setHex(nonColor);
    _nonBars[i].material.emissive.setHex(nonColor);
    _nonBars[i].material.opacity = live ? 0.7 : 0.18;
    _saveMk[i].material.color.setHex(saveColor);
    _saveMk[i].material.emissive.setHex(saveColor);
    _saveMk[i].material.opacity = live ? 0.92 : 0.18;
  }
}

// =============================================================================
// per-frame animation — smooth bar-height easing + gentle rotation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.10;

  const ease = 0.08;
  for (let i = 0; i < _nestBars.length; i++) {
    _nestBars[i].scale.y += (_nestTargetH[i] - _nestBars[i].scale.y) * ease;
    _nonBars[i].scale.y  += (_nonTargetH[i]  - _nonBars[i].scale.y)  * ease;
    _saveMk[i].scale.y   += (_saveTargetH[i] - _saveMk[i].scale.y)   * ease;
    // gentle pulse on the storage-saving markers to draw the eye to the "win"
    const pulse = 1.0 + 0.04 * Math.sin(t * 0.005 + i);
    _saveMk[i].scale.x = pulse; _saveMk[i].scale.z = pulse;
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#d7b96b",
    badge: _badge,
    chips: [{ label: "MODELED", text: "nested embedding", name: "mg" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'One embedding is trained so its <b>front prefixes</b> are each usable embeddings ' +
      '\u2014 truncate to the first 2/4/8/16/32 dims to trade accuracy for storage with no ' +
      'retraining. The <b>lattice-blue</b> bars are the <b>nested</b> (front-loaded) embedding\u2019s ' +
      'accuracy at each prefix; the <b>grey</b> bars are a <b>non-nested</b> control (same directions, ' +
      'shuffled); the <b>proof-teal</b> markers are the storage saving at each prefix. Nested stays ' +
      'accurate under truncation; non-nested collapses. Honesty label <b>MODELED</b> ' +
      '(deterministic toy sim; NOT a trained encoder). 0 runtime CDN.',
    citations:
      "MIPIC arXiv:2604.24374 (refines nested reps) \u00b7 MRL arXiv:2205.13147 (foundational). MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["mg-D"]        = _show.addField("D (full width)");
  _el["mg-prefixes"] = _show.addField("prefixes evaluated");
  _el["mg-nested"]   = _show.addField("nested acc @ prefixes");
  _el["mg-nonnest"]  = _show.addField("non-nested acc @ prefixes");
  _el["mg-saving"]   = _show.addField("storage saving @ prefixes");
  _el["mg-full"]     = _show.addField("full_accuracy (d = D)");
  _el["mg-label"]    = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  let lowGain = "loading\u2026";
  if (Array.isArray(S.curve) && S.curve.length) {
    const c0 = S.curve[0];
    if (c0 && typeof c0.nested_accuracy === "number" && typeof c0.non_nested_accuracy === "number") {
      lowGain = "at d=" + c0.d + ": nested " + (c0.nested_accuracy * 100).toFixed(0) +
                "% vs non-nested " + (c0.non_nested_accuracy * 100).toFixed(0) + "%";
    }
  }
  return (
    "<b>What this means:</b> An embedding is a list of numbers that captures the meaning of " +
    "something (a word, an image). Normally, if you want a shorter, cheaper embedding you have " +
    "to train a whole new model. <b>Matryoshka</b> embeddings are trained so the FIRST few " +
    "numbers already hold the most important information \u2014 so you can just CHOP the vector " +
    "to whatever length your budget allows and it still works. Here, the front-loaded " +
    "(<b>nested</b>) embedding stays accurate even when chopped hard (" + lowGain + "), while a " +
    "<b>non-nested</b> vector (same numbers in a scrambled order) falls apart when chopped. " +
    "Shorter vectors mean big storage/compute savings (the teal markers). " +
    "<b>Honesty:</b> this is a <b>MODELED</b> toy analytic sim of the nested-representation " +
    "MECHANISM \u2014 synthetic Gaussian clusters, a closed-form front-loaded projection, and a " +
    "nearest-centroid probe. There is NO trained encoder, NO SIA/PIC training, and NO CKA " +
    "self-distillation over real models. It shows WHY prefix-nested embeddings degrade " +
    "gracefully versus a non-nested control; it does NOT reproduce MIPIC\u2019s STS/NLI/" +
    "classification results or MRL\u2019s ImageNet speed-ups, and the \u201cself-distillation\u201d " +
    "step is a one-pass toy stand-in. Not a run of MIPIC or MRL.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function _fmtList(arr, mul, dp, suffix) {
  if (!Array.isArray(arr) || !arr.length) return "\u2014";
  return arr.map((v) => (typeof v === "number" ? (v * mul).toFixed(dp) + (suffix || "") : "\u2014")).join(" / ");
}

function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("mg-D",        t || (S.D != null ? String(S.D) : "\u2014"));
  _set("mg-prefixes", t || (Array.isArray(S.prefixes) ? S.prefixes.join(", ") : "\u2014"));

  let nestedList = null, nonList = null, saveList = null;
  if (Array.isArray(S.curve)) {
    nestedList = S.curve.map((r) => r.nested_accuracy);
    nonList = S.curve.map((r) => r.non_nested_accuracy);
    saveList = S.curve.map((r) => r.storage_saving);
  }
  _set("mg-nested",  t || _fmtList(nestedList, 1, 3, ""));
  _set("mg-nonnest", t || _fmtList(nonList, 1, 3, ""));
  _set("mg-saving",  t || _fmtList(saveList, 100, 0, "%"));
  _set("mg-full",    t || (S.fullAcc != null ? S.fullAcc.toFixed(3) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("mg-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("mg", S.label || "MODELED", { text: "nested embedding" }); _show.refreshPlain(); }
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
  _floor = null;
  _nestBars = []; _nonBars = []; _saveMk = [];
  _nestTargetH = []; _nonTargetH = []; _saveTargetH = [];
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.D = S.prefixes = S.curve = S.fullAcc = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
