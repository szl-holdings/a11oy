// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/elf.js — ELF (EMBEDDED LANGUAGE FLOWS) continuous-embedding
// Flow-Matching organ for the holographic frontier ring (MODELED).
//
// Renders a continuous-time Flow-Matching process that runs ENTIRELY in a 2-D
// token-embedding space and stays continuous until the FINAL step, where a
// nearest-embedding readout maps the settled state to discrete tokens:
//   1. Six fixed symbol embeddings sit on the UNIT CIRCLE (the toy vocabulary).
//   2. Four noise points x0 flow along Euler-integrated trajectories toward the
//      TARGET-embedding cluster (the toy-grammar "sentence").
//   3. A HUD shows accuracy (fraction of positions decoding to the correct
//      symbol), the accuracy-vs-num_euler_steps curve (few-step quality), and the
//      guidance on/off ablation. Honesty label "MODELED" is read VERBATIM from the
//      JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors flowmatch.js / dllm.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint /api/killinchu/v1/elf/flow):
//   vocab_size, embedding_dim, num_euler_steps, guidance_scale, embeddings[],
//   target_tokens[], target_embeddings[], x0[], trajectory[], decoded_tokens[],
//   accuracy, accuracy_vs_steps[], guidance_ablation{on,off}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   ELF (Embedded Language Flows): Hu, Qiu, Lu, Zhao, Li, Kim, Andreas, He.
//     arXiv:2605.10938  https://arxiv.org/abs/2605.10938
//   LangFlow (Continuous Diffusion Rivals Discrete): arXiv:2604.11748
//     https://arxiv.org/abs/2604.11748
//   MLFM (Masked Language Flow Models): arXiv:2606.27617
//     https://arxiv.org/abs/2606.27617
//   Classifier-Free Guidance: Ho & Salimans 2022, arXiv:2207.12598
//     https://arxiv.org/abs/2207.12598
//
// HONESTY LABELS: MODELED (inspired-not-real; deterministic analytic toy
//   Flow-Matching in a 2-D embedding space with 6 symbols + hand-fit linear
//   velocity field; NOT ELF/LangFlow/MLFM; reproduces NONE of their perplexity
//   numbers). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (trajectory paths), violet-blue 0x8a6bff (noise
//   x0 + target markers — data-viz only), proof-teal 0x3af4c8 (HUD accent /
//   decoded-correct marker). Purple BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored r170 via page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "elf";
const TITLE = "ELF · Continuous-Embedding Flow Matching (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/elf/flow?seed=42&num_euler_steps=8&guidance_scale=2.0";

// data-viz hues — purple BANNED
const C_PATH    = 0x5b8dee;  // lattice-blue (Euler-integrated trajectory paths)
const C_MARKERS = 0x8a6bff;  // violet-blue (noise x0 + target markers — data-viz only)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal (correct-decode marker / HUD accent)
const C_GRID    = 0x1b3a44;  // floor / link colour

// layout geometry
const EMB_SCALE  = 4.2;   // world-units per unit of embedding coordinate (unit-circle -> radius 4.2)
const SEQ_SPREAD = 2.6;   // z-offset per sequence position (fans the 4 positions apart)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _show = null;

// geometry handles
let _vocabDots = [];   // Array<THREE.Mesh> — the 6 unit-circle symbol embeddings
let _pathLines = [];   // Array<THREE.Line> — one Euler trajectory per sequence position
let _x0Marks   = [];   // Array<THREE.Mesh> — noise start markers per position
let _tgtMarks  = [];   // Array<THREE.Mesh> — target-embedding markers per position
let _decMarks  = [];   // Array<THREE.Mesh> — terminal decoded markers per position
let _floor     = null;

const _MAX_STEPS = 260; // trajectory point cap (num_euler_steps<=256 + endpoints)
const _SEQ = 4;         // toy-grammar sentence length
const _VOCAB = 6;       // unit-circle symbols

// live state
const S = {
  label:          null,
  vocabSize:      null,
  embeddingDim:   null,
  numEulerSteps:  null,
  guidanceScale:  null,
  embeddings:     null,   // [[x,y]*6]
  targetTokens:   null,   // [id*4]
  targetEmb:      null,   // [[x,y]*4]
  x0:             null,   // [[x,y]*4]
  trajectory:     null,   // [{t, x:[[x,y]*4]}]
  decoded:        null,   // [id*4]
  accuracy:       null,
  accVsSteps:     null,   // [{num_euler_steps, accuracy}]
  guidOn:         null,   // {guidance_scale, accuracy}
  guidOff:        null,   // {guidance_scale, accuracy}
  honestNote:     null,
  state:          "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildVocab();
  _buildPaths();
  _buildMarkers();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSample, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateScene(); } }));

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

// The 6 unit-circle symbol embeddings (drawn even before live data, from geometry).
function _buildVocab() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.14, 12, 10);
  for (let i = 0; i < _VOCAB; i++) {
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.3 }));
    const ang = 2 * Math.PI * i / _VOCAB;
    m.position.set(Math.cos(ang) * EMB_SCALE, Math.sin(ang) * EMB_SCALE, 0);
    _group.add(m);
    _vocabDots.push(m);
  }
  // faint unit-circle ring
  const ringGeo = new THREE.TorusGeometry(EMB_SCALE, 0.02, 8, 96);
  const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.4 }));
  _group.add(ring);
  _vocabDots.push(ring);
}

function _buildPaths() {
  const THREE = _THREE;
  for (let p = 0; p < _SEQ; p++) {
    const pts = new Array(_MAX_STEPS).fill(0).map(() => new THREE.Vector3(0, 0, 0));
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_PATH, transparent: true, opacity: 0.85, linewidth: 2 });
    const line = new THREE.Line(g, mat);
    _group.add(line);
    _pathLines.push(line);
  }
}

function _buildMarkers() {
  const THREE = _THREE;
  const x0Geo  = new THREE.IcosahedronGeometry(0.20, 1);
  const tgtGeo = new THREE.OctahedronGeometry(0.24, 0);
  const decGeo = new THREE.IcosahedronGeometry(0.16, 1);
  for (let p = 0; p < _SEQ; p++) {
    // noise-cloud start marker (x0) — wireframe icosahedron, violet-blue
    const x0m = new THREE.Mesh(x0Geo, new THREE.MeshStandardMaterial({ color: C_MARKERS, emissive: C_MARKERS, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }));
    _group.add(x0m); _x0Marks.push(x0m);
    // target-embedding marker — solid octahedron, violet-blue
    const tm = new THREE.Mesh(tgtGeo, new THREE.MeshStandardMaterial({ color: C_MARKERS, emissive: C_MARKERS, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }));
    _group.add(tm); _tgtMarks.push(tm);
    // terminal decoded marker — proof-teal (correct) pulse
    const dm = new THREE.Mesh(decGeo, new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.6, wireframe: true, transparent: true, opacity: 0.9 }));
    _group.add(dm); _decMarks.push(dm);
  }
}

// =============================================================================
// live data handler — reads label VERBATIM (top-level OR nested payload.label)
// =============================================================================
function _readLabel(j) {
  // read honesty label VERBATIM via _tok: top-level 'label' OR nested 'payload.label'
  const raw = (j && (j.label != null ? j.label : (j.payload && j.payload.label)));
  return (raw != null ? String(raw) : "MODELED").toUpperCase();
}

function _onSample(j) {
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : (j || {});
  S.label         = _readLabel(j);
  S.vocabSize     = typeof src.vocab_size === "number" ? src.vocab_size : null;
  S.embeddingDim  = typeof src.embedding_dim === "number" ? src.embedding_dim : null;
  S.numEulerSteps = typeof src.num_euler_steps === "number" ? src.num_euler_steps : null;
  S.guidanceScale = typeof src.guidance_scale === "number" ? src.guidance_scale : null;
  S.embeddings    = Array.isArray(src.embeddings) ? src.embeddings : null;
  S.targetTokens  = Array.isArray(src.target_tokens) ? src.target_tokens : null;
  S.targetEmb     = Array.isArray(src.target_embeddings) ? src.target_embeddings : null;
  S.x0            = Array.isArray(src.x0) ? src.x0 : null;
  S.trajectory    = Array.isArray(src.trajectory) ? src.trajectory : null;
  S.decoded       = Array.isArray(src.decoded_tokens) ? src.decoded_tokens : null;
  S.accuracy      = typeof src.accuracy === "number" ? src.accuracy : null;
  S.accVsSteps    = Array.isArray(src.accuracy_vs_steps) ? src.accuracy_vs_steps : null;
  const ab = src.guidance_ablation || {};
  S.guidOn        = ab.on  || null;
  S.guidOff       = ab.off || null;
  S.honestNote    = typeof src.honest_note === "string" ? src.honest_note : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// scene updater — draws vocab, trajectories, markers from live data
// =============================================================================
function _proj(vec, pos) {
  // Map a 2-D embedding coordinate to 3D world space; fan sequence positions
  // apart along z so all 4 trajectories are legible. Pure display mapping.
  const x = (vec[0] || 0) * EMB_SCALE;
  const y = (vec[1] || 0) * EMB_SCALE;
  const z = (pos - (_SEQ - 1) / 2) * SEQ_SPREAD;
  return [x, y, z];
}

function _updateScene() {
  const live = S.state === "live";

  // vocab embedding dots
  for (let i = 0; i < _VOCAB; i++) {
    const d = _vocabDots[i];
    if (!d || !d.material) continue;
    const c = live ? C_MARKERS : C_DIM;
    d.material.color.setHex(c); if (d.material.emissive) d.material.emissive.setHex(c);
    if (live && S.embeddings && S.embeddings[i]) {
      d.position.set(S.embeddings[i][0] * EMB_SCALE, S.embeddings[i][1] * EMB_SCALE, 0);
    }
  }

  if (live && S.trajectory && S.trajectory.length) {
    const n = Math.min(_MAX_STEPS, S.trajectory.length);
    for (let p = 0; p < _SEQ; p++) {
      const line = _pathLines[p];
      const pos = line.geometry.attributes.position;
      for (let i = 0; i < _MAX_STEPS; i++) {
        const row = S.trajectory[Math.min(i, n - 1)];
        const pt = (row && row.x && row.x[p]) ? row.x[p] : [0, 0];
        const [x, y, z] = _proj(pt, p);
        pos.setXYZ(i, x, y, z);
      }
      pos.needsUpdate = true;
      line.geometry.computeBoundingSphere();
      line.material.color.setHex(C_PATH); line.material.opacity = 0.85;

      // start / target / decoded markers per position
      if (S.x0 && S.x0[p]) { const [x, y, z] = _proj(S.x0[p], p); _x0Marks[p].position.set(x, y, z); }
      if (S.targetEmb && S.targetEmb[p]) { const [x, y, z] = _proj(S.targetEmb[p], p); _tgtMarks[p].position.set(x, y, z); }
      const last = S.trajectory[n - 1];
      if (last && last.x && last.x[p]) { const [x, y, z] = _proj(last.x[p], p); _decMarks[p].position.set(x, y, z); }

      _x0Marks[p].material.color.setHex(C_MARKERS); _x0Marks[p].material.emissive.setHex(C_MARKERS); _x0Marks[p].material.opacity = 0.85;
      _tgtMarks[p].material.color.setHex(C_MARKERS); _tgtMarks[p].material.emissive.setHex(C_MARKERS); _tgtMarks[p].material.opacity = 0.9;
      // decoded marker teal when correct, violet when wrong (data-viz only, no purple)
      const correct = S.decoded && S.targetTokens && S.decoded[p] === S.targetTokens[p];
      const dc = correct ? C_ACCENT : C_MARKERS;
      _decMarks[p].material.color.setHex(dc); _decMarks[p].material.emissive.setHex(dc); _decMarks[p].material.opacity = 0.9;
    }
  } else {
    for (let p = 0; p < _SEQ; p++) {
      if (_pathLines[p]) { _pathLines[p].material.color.setHex(C_DIM); _pathLines[p].material.opacity = 0.25; }
      [_x0Marks[p], _tgtMarks[p], _decMarks[p]].forEach((m) => {
        if (m && m.material) { m.material.color.setHex(C_DIM); if (m.material.emissive) m.material.emissive.setHex(C_DIM); m.material.opacity = 0.3; }
      });
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00010) * 0.18;
  const pulse = 1.0 + 0.16 * Math.sin(t * 0.004);
  for (let p = 0; p < _SEQ; p++) {
    if (_decMarks[p]) { _decMarks[p].rotation.y += 0.02; _decMarks[p].rotation.x += 0.01; _decMarks[p].scale.setScalar(pulse); }
    if (_tgtMarks[p]) { _tgtMarks[p].rotation.y += 0.01; }
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
    'A <b>continuous-embedding Flow-Matching</b> process: 6 symbols on a unit ' +
    'circle; noise points flow along Euler-integrated trajectories toward the ' +
    'target-embedding cluster, staying <b>continuous until the final step</b> ' +
    '(decode = nearest embedding, only at t=1). A <b>guidance</b> knob transfers ' +
    'classifier-free guidance from diffusion. Honesty label <b>MODELED</b> ' +
    '(inspired-not-real toy sim; NOT ELF/LangFlow/MLFM). 0 runtime CDN.';
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
  nm.textContent = "elf";
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

  grid.appendChild(kpiRow("elf-vocab",  "vocab_size"));
  grid.appendChild(kpiRow("elf-dim",    "embedding_dim"));
  grid.appendChild(kpiRow("elf-steps",  "num_euler_steps"));
  grid.appendChild(kpiRow("elf-guid",   "guidance_scale"));
  grid.appendChild(kpiRow("elf-tgt",    "target_tokens"));
  grid.appendChild(kpiRow("elf-dec",    "decoded_tokens"));
  grid.appendChild(kpiRow("elf-acc",    "accuracy \u2014 MODELED"));
  grid.appendChild(kpiRow("elf-curve",  "acc vs steps (few-step)"));
  grid.appendChild(kpiRow("elf-abl",    "guidance on / off"));
  grid.appendChild(kpiRow("elf-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "ELF arXiv:2605.10938 \u00b7 LangFlow arXiv:2604.11748 \u00b7 MLFM arXiv:2606.27617 \u00b7 CFG arXiv:2207.12598 (cited only). MODELED \u00b7 not claimed-as.";
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
  pd.id = "elf-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  // Fold the legacy panel into the shared showcase overlay (surfaces/_showcase.js):
  // title + live badge + doctrine legend live in the always-visible chrome; the
  // descriptive text + KPI card become the collapsible body so the 3D scene is the star.
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    legend: true,
  });
  _overlay.style.position = "static";
  _overlay.style.left = _overlay.style.top = "auto";
  _overlay.style.maxWidth = "none";
  _overlay.style.font = "inherit";
  if (_overlay.firstChild) _overlay.removeChild(_overlay.firstChild); // drop duplicate title
  _show.body.appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const steps = S.numEulerSteps != null ? String(S.numEulerSteps) : "loading\u2026";
  const acc   = S.accuracy != null ? (S.accuracy * 100).toFixed(0) + "%" : "loading\u2026";
  const accOff = (S.guidOff && typeof S.guidOff.accuracy === "number") ? (S.guidOff.accuracy * 100).toFixed(0) + "%" : "\u2014";
  pd.innerHTML =
    "<b>What this means:</b> Most language models pick words one discrete step at a " +
    "time. <b>ELF-style</b> models instead treat words as points in a continuous " +
    "<i>meaning-space</i> and <b>flow</b> from random noise toward the right meaning " +
    "along a smooth path \u2014 only turning the final settled point back into an actual " +
    "word at the very end. Because the whole path is continuous, tricks from image AI " +
    "(like a <b>guidance</b> dial that sharpens the result) carry straight over. Here, " +
    "6 toy symbols sit on a circle; 4 noise points flow to their targets and decode " +
    "with <b>" + acc + "</b> accuracy at " + steps + " steps \u2014 versus <b>" + accOff +
    "</b> with guidance turned off. " +
    "<b>Inspired-not-real (MODELED):</b> this is a tiny hand-fit demo of the mechanism, " +
    "NOT ELF/LangFlow/MLFM, and it reproduces none of their published quality numbers.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _curveStr() {
  if (!S.accVsSteps || !S.accVsSteps.length) return "\u2014";
  return S.accVsSteps.map((r) => `${r.num_euler_steps}:${(r.accuracy * 100).toFixed(0)}%`).join("  ");
}

function _paintOverlay() {
  const t = _tok(S.state);
  _set("elf-vocab", t || (S.vocabSize != null ? String(S.vocabSize) : "\u2014"));
  _set("elf-dim",   t || (S.embeddingDim != null ? String(S.embeddingDim) : "\u2014"));
  _set("elf-steps", t || (S.numEulerSteps != null ? String(S.numEulerSteps) : "\u2014"));
  _set("elf-guid",  t || (S.guidanceScale != null ? S.guidanceScale.toFixed(2) : "\u2014"));
  _set("elf-tgt",   t || (S.targetTokens ? "[" + S.targetTokens.join(",") + "]" : "\u2014"));
  _set("elf-dec",   t || (S.decoded ? "[" + S.decoded.join(",") + "]" : "\u2014"));
  _set("elf-acc",   t || pct(S.accuracy, 1));
  _set("elf-curve", t || _curveStr());
  const onA  = (S.guidOn && typeof S.guidOn.accuracy === "number") ? (S.guidOn.accuracy * 100).toFixed(0) + "%" : "\u2014";
  const offA = (S.guidOff && typeof S.guidOff.accuracy === "number") ? (S.guidOff.accuracy * 100).toFixed(0) + "%" : "\u2014";
  _set("elf-abl",   t || `${onA} / ${offA}`);
  // honesty label verbatim — never upgraded
  _set("elf-label", t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
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
  _group = _overlay = _show = null;
  _vocabDots = []; _pathLines = []; _x0Marks = []; _tgtMarks = []; _decMarks = []; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.vocabSize = S.embeddingDim = S.numEulerSteps = S.guidanceScale = null;
  S.embeddings = S.targetTokens = S.targetEmb = S.x0 = S.trajectory = S.decoded = null;
  S.accuracy = S.accVsSteps = S.guidOn = S.guidOff = S.honestNote = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
