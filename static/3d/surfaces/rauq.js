// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/rauq.js — ATTENTION-PATTERN (recurrent attention-based) UNCERTAINTY organ for
// the holographic frontier ring. SUB-ORGAN UPGRADE of sement.
//
// Same uncertainty axis as sement (hallucination / abstain-vs-answer), DISTINCT mechanism:
// sement's true signal is MULTI-SAMPLE semantic entropy (resample K generations, cluster
// meanings); RAUQ here reads INTRINSIC ATTENTION PATTERNS in a SINGLE forward pass — no
// resampling. It identifies "uncertainty-aware" attention heads whose attention TO PRECEDING
// TOKENS systematically DROPS during incorrect generations, auto-selects them, recurrently
// aggregates their preceding-token attention with per-token confidence into one SEQUENCE-LEVEL
// uncertainty scalar, and thresholds it to flag likely-wrong generations.
//
// Driven by a live snapshot from /api/killinchu/v1/rauq/score. The organ renders, per
// selected head, an ATTENTION-MASS TIMELINE across the sequence: a lattice-blue polyline for a
// CORRECT example (preceding-token mass stays HIGH) and a violet-blue polyline for an INCORRECT
// example (preceding-token mass DROPS / falls on flagged spans). Two KPI columns compare the
// RAUQ attention-drop score against a cheap OUTPUT-ENTROPY baseline (AUROC / accuracy / F1) —
// the attention-drop signal separates the labeled toy set better. Honesty label "MODELED" is
// read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// IMPORTANT — MODELED, NOT A REAL TRANSFORMER:
//   This organ simulates the attention-pattern-uncertainty MECHANISM on synthetic toy data.
//   The "attention matrices" are SEEDED SYNTHETIC row-stochastic toys with correct/incorrect
//   regimes BUILT IN BY CONSTRUCTION; there is NO real transformer, NO forward pass, and NO
//   4-LLM / 12-task evaluation. "Head selection" separates a hand-made labeled toy set. It
//   demonstrates WHY a drop in preceding-token attention mass in selected heads can serve as a
//   single-pass uncertainty signal a naive output-entropy baseline misses on constructed cases;
//   it does NOT reproduce RAUQ's QA/summarization/translation results or its <1% real-latency
//   claim. Explicitly a SUB-ORGAN UPGRADE of sement (same uncertainty axis, distinct single-
//   pass-attention vs multi-sample-semantic-entropy mechanism — the true sement signal is
//   MULTI-SAMPLE), not a new axis. Stated plainly in "what this means" and echoed in the
//   endpoint's own JSON payload (honest_note).
//
// Surface export shape (mirrors sement.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// LEADER ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Vazhentsev, Rvanova, Kuzmin, Fadeeva, Lazichny, Panchenko, Panov, Baldwin, Sachan, Nakov &
//     Shelmanov (2025) "Uncertainty-Aware Attention Heads: Efficient Unsupervised Uncertainty
//     Quantification for LLMs" [RAUQ]. arXiv:2505.20045. https://arxiv.org/abs/2505.20045
//
// HONESTY LABEL: MODELED (simulation of the METHOD on synthetic toy data; seeded synthetic
//   attention matrices, regimes built in by construction, NO real transformer). Read verbatim.
// COLOURS: lattice-blue 0x5b8dee (correct-regime timeline / RAUQ column), violet-blue 0x8a6bff
//   (incorrect-regime timeline — data-viz only), proof-teal 0x3af4c8 (selected-head accent /
//   verdict), greys for dim/idle. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// This organ adds NOTHING to SZL's own locked-8 / Λ-Conjecture-1.

import { createShowcase } from "./_showcase.js";

const ID    = "rauq";
const TITLE = "Attention-Pattern (Recurrent Attention) Uncertainty · sub-organ of sement (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/rauq/score?seed=42&seq_len=8&num_heads=6&num_selected_heads=2&preceding_window=1&confidence_weight=0.4&threshold=0.5";

// data-viz hues — purple BANNED
const C_CORRECT = 0x5b8dee;  // lattice-blue (correct-regime timeline / RAUQ column)
const C_WRONG   = 0x8a6bff;  // violet-blue (incorrect-regime timeline — data-viz only)
const C_ACCENT  = 0x3af4c8;  // proof-teal accent (selected-head rails + verdict ring)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data / idle)
const C_GRID    = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _lines = [];        // Array<THREE.Line>   — timeline polylines (per selected head x regime)
let _nodes = [];        // Array<THREE.Mesh>   — per-position marker spheres
let _rails = [];        // Array<THREE.Mesh>   — one rail bar per selected head
let _ring  = null;      // verdict ring (rauq_beats_baseline)
let _built = false;
const _MAX_NODES = 256;
const _pulse = new Float32Array(_MAX_NODES);

// live state
const S = {
  label:       null,
  seqLen:      null,
  selectedHeads: [],   // Array<int>
  threshold:   null,
  beats:       null,   // rauq_beats_baseline
  // one representative correct + one incorrect example, per selected head timeline
  headTimelines: {},   // { headId: { correct: [..], incorrect: [..] } }
  rauq:     { auroc: null, accuracy: null, precision: null, recall: null, f1: null },
  baseline: { auroc: null, accuracy: null, precision: null, recall: null, f1: null },
  state:    "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 7, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildVerdict();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onScore, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateGeometry(); } }));

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
}

function _buildVerdict() {
  const THREE = _THREE;
  _ring = new THREE.Mesh(
    new THREE.TorusGeometry(1.5, 0.05, 10, 48),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.5 }),
  );
  _ring.position.set(0, 7.6, 0);
  _ring.rotation.x = Math.PI / 2;
  _group.add(_ring);
}

// Dispose only the timeline geometry (rebuilt whenever selected heads / data change).
function _clearTimelines() {
  const drop = (o) => {
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) {
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach((m) => { if (m.dispose) m.dispose(); });
      }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _lines.forEach(drop); _nodes.forEach(drop); _rails.forEach(drop);
  _lines = []; _nodes = []; _rails = [];
  _pulse.fill(0);
}

// Build one attention-mass timeline per selected head: a CORRECT polyline (lattice-blue,
// preceding-mass stays high) and an INCORRECT polyline (violet-blue, preceding-mass drops).
function _buildTimelines() {
  const THREE = _THREE;
  _clearTimelines();
  const heads = S.selectedHeads;
  const seqLen = S.seqLen || 8;
  if (!heads.length) return;

  const laneGap = 5.0;                       // z-separation between head lanes
  const x0 = -((seqLen - 1) * 1.2) / 2;      // centre the timeline in x
  const dx = 1.2;                            // x per token position
  const yScale = 6.0;                        // world-units per unit attention mass (mass 0..1)

  heads.forEach((h, li) => {
    const z = (li - (heads.length - 1) / 2) * laneGap;
    const tl = S.headTimelines[String(h)] || {};

    // rail bar under each lane (selected-head accent)
    const rail = new THREE.Mesh(
      new THREE.BoxGeometry((seqLen - 1) * dx + 0.4, 0.06, 0.12),
      new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.3, transparent: true, opacity: 0.55 }),
    );
    rail.position.set(0, 0.03, z);
    rail.userData.head = h;
    _group.add(rail); _rails.push(rail);

    [["correct", C_CORRECT], ["incorrect", C_WRONG]].forEach(([regime, col]) => {
      const series = Array.isArray(tl[regime]) ? tl[regime] : [];
      if (!series.length) return;
      const pts = [];
      for (let i = 0; i < series.length; i++) {
        const x = x0 + i * dx;
        const y = Math.max(0.05, Math.min(series[i] * yScale, 8.5));
        pts.push(new THREE.Vector3(x, y, z + (regime === "incorrect" ? 0.35 : -0.35)));
        // marker node
        const node = new THREE.Mesh(
          new THREE.SphereGeometry(0.11, 12, 12),
          new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.5 }),
        );
        node.position.copy(pts[pts.length - 1]);
        node.userData.pi = _nodes.length % _MAX_NODES;
        _group.add(node); _nodes.push(node);
      }
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.9 }));
      line.userData.regime = regime;
      _group.add(line); _lines.push(line);
    });
  });
  _built = true;
}

// =============================================================================
// live data handler — reads label VERBATIM (top-level 'label' OR nested 'payload.label')
// =============================================================================
function _onScore(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (p && p.label != null) ? p.label : (j && j.label != null ? j.label : "MODELED");
  S.label = String(rawLabel).toUpperCase();

  S.seqLen    = typeof p.seq_len   === "number"  ? p.seq_len   : null;
  S.threshold = typeof p.threshold === "number"  ? p.threshold : null;
  S.beats     = typeof p.rauq_beats_baseline === "boolean" ? p.rauq_beats_baseline : null;
  S.selectedHeads = Array.isArray(p.selected_heads) ? p.selected_heads.slice() : [];

  // metrics
  const rm = p.rauq_metrics || {}, bm = p.baseline_metrics || {};
  const grab = (o, dst) => {
    dst.auroc     = typeof o.auroc     === "number" ? o.auroc     : null;
    dst.accuracy  = typeof o.accuracy  === "number" ? o.accuracy  : null;
    dst.precision = typeof o.precision === "number" ? o.precision : null;
    dst.recall    = typeof o.recall    === "number" ? o.recall    : null;
    dst.f1        = typeof o.f1        === "number" ? o.f1        : null;
  };
  grab(rm, S.rauq); grab(bm, S.baseline);

  // Extract one representative correct + one incorrect example's per-selected-head timeline.
  S.headTimelines = {};
  const exs = Array.isArray(p.examples) ? p.examples : [];
  const firstCorrect = exs.find((e) => e && e.label === "correct");
  const firstWrong   = exs.find((e) => e && e.label === "incorrect");
  S.selectedHeads.forEach((h) => {
    const key = String(h);
    const tl = {};
    if (firstCorrect && firstCorrect.selected_head_preceding_timeline && Array.isArray(firstCorrect.selected_head_preceding_timeline[key])) {
      tl.correct = firstCorrect.selected_head_preceding_timeline[key].slice();
    }
    if (firstWrong && firstWrong.selected_head_preceding_timeline && Array.isArray(firstWrong.selected_head_preceding_timeline[key])) {
      tl.incorrect = firstWrong.selected_head_preceding_timeline[key].slice();
    }
    S.headTimelines[key] = tl;
  });

  _buildTimelines();
  _updateGeometry();
  _paintOverlay();
}

// =============================================================================
// geometry updater — colours by live/degraded state, verdict ring
// =============================================================================
function _updateGeometry() {
  const live = S.state === "live";
  _lines.forEach((ln) => {
    const col = live ? (ln.userData.regime === "incorrect" ? C_WRONG : C_CORRECT) : C_DIM;
    ln.material.color.setHex(col);
    ln.material.opacity = live ? 0.9 : 0.3;
  });
  _nodes.forEach((nd) => {
    if (!live) { nd.material.color.setHex(C_DIM); nd.material.emissive.setHex(C_DIM); nd.material.emissiveIntensity = 0.1; }
  });
  _rails.forEach((rl) => {
    const col = live ? C_ACCENT : C_DIM;
    rl.material.color.setHex(col); rl.material.emissive.setHex(col);
    rl.material.emissiveIntensity = live ? 0.3 : 0.1; rl.material.opacity = live ? 0.55 : 0.2;
  });
  if (_ring) {
    // verdict: RAUQ beats baseline -> calm teal; else violet-blue warning
    const beats = S.beats === true;
    const rcol = live ? (beats ? C_ACCENT : C_WRONG) : C_DIM;
    _ring.material.color.setHex(rcol); _ring.material.emissive.setHex(rcol);
    _ring.material.emissiveIntensity = live ? (beats ? 0.6 : 0.85) : 0.12;
    _ring.material.opacity = live ? 0.6 : 0.2;
    _ring.scale.setScalar(live ? (beats ? 1.0 : 1.15) : 0.8);
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.12;
  if (_ring) _ring.rotation.z += 0.004;
  const live = S.state === "live";
  _nodes.forEach((nd) => {
    const i = nd.userData.pi;
    if (_pulse[i] > 0) {
      _pulse[i] -= 1;
      const f = _pulse[i] / 60;
      nd.material.emissiveIntensity = Math.max(nd.material.emissiveIntensity, 0.2 + 0.6 * f);
    } else if (live) {
      nd.material.emissiveIntensity = 0.4;
    }
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "attention uncertainty", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'In a <b>single forward pass</b> we read a model\u2019s <b>attention patterns</b>: certain ' +
    '<b>uncertainty-aware heads</b> keep high attention on the <b>immediately-preceding token</b> ' +
    'when a generation is <b>correct</b>, but that mass <b>drops</b> when it is <b>incorrect</b>. ' +
    'We <b>auto-select</b> those heads by how well they separate a labeled set, <b>recurrently ' +
    'aggregate</b> their preceding-token attention with a confidence proxy into one ' +
    '<b>sequence-level uncertainty score</b>, and <b>flag</b> likely-wrong generations \u2014 beating ' +
    'a cheap <b>output-entropy</b> baseline. Sub-organ upgrade of <b>sement</b> (same uncertainty ' +
    'axis; sement\u2019s true signal is <b>multi-sample</b> semantic entropy, this is ' +
    '<b>single-pass attention</b>). Honesty label <b>MODELED</b> \u2014 a simulation of the method on ' +
    'synthetic toy data, <b>not</b> a real transformer. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "rauq \u00b7 attention-pattern uncertainty";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("rq-sel",   "auto-selected heads"));
  grid.appendChild(kpiRow("rq-thr",   "RAUQ flag threshold"));
  grid.appendChild(kpiRow("rq-ra",    "RAUQ \u00b7 AUROC / accuracy"));
  grid.appendChild(kpiRow("rq-rf",    "RAUQ \u00b7 precision / recall / F1"));
  grid.appendChild(kpiRow("rq-ba",    "baseline \u00b7 AUROC / accuracy"));
  grid.appendChild(kpiRow("rq-bf",    "baseline \u00b7 precision / recall / F1"));
  grid.appendChild(kpiRow("rq-beats", "attention-drop beats output-entropy"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Vazhentsev, Rvanova, Kuzmin, Fadeeva, Lazichny, Panchenko, Panov, Baldwin, " +
    "Sachan, Nakov & Shelmanov, arXiv:2505.20045 (2025) \u00b7 MODELED \u00b7 seeded synthetic attention " +
    "matrices, regimes built in by construction, no real transformer \u00b7 sub-organ upgrade of " +
    "sement (true sement signal is multi-sample) \u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "rauq-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const sel  = S.selectedHeads.length ? S.selectedHeads.join(", ") : "loading\u2026";
  const rAuroc = S.rauq.auroc != null ? S.rauq.auroc.toFixed(3) : "loading\u2026";
  const rAcc   = S.rauq.accuracy != null ? S.rauq.accuracy.toFixed(3) : "loading\u2026";
  const bAuroc = S.baseline.auroc != null ? S.baseline.auroc.toFixed(3) : "loading\u2026";
  const bAcc   = S.baseline.accuracy != null ? S.baseline.accuracy.toFixed(3) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> A transformer pays <b>attention</b> to earlier words as it writes. " +
    "In some heads, when the model is on solid ground it keeps a strong link to the <b>word it just " +
    "wrote</b>; when it starts to <b>make things up</b>, that link <b>weakens</b>. We find the heads " +
    "where this pattern is clearest (here heads <b>" + sel + "</b>), watch how their preceding-word " +
    "attention rises and falls across the sentence, and roll it into a single <b>uncertainty score</b> " +
    "\u2014 all in <b>one pass</b>, no re-asking the model. On our labeled toy set that attention-drop " +
    "score tells correct from incorrect almost perfectly (AUROC \u2248 <b>" + rAuroc + "</b>, accuracy " +
    "\u2248 <b>" + rAcc + "</b>), while a naive <b>output-entropy</b> baseline is much weaker " +
    "(AUROC \u2248 <b>" + bAuroc + "</b>, accuracy \u2248 <b>" + bAcc + "</b>). The blue timeline holds " +
    "high; the violet timeline collapses \u2014 that collapse is the signal." +
    "<br><br><b>Important honesty note:</b> this is a <b>MODELED</b> toy analytic simulation of the " +
    "attention-pattern-uncertainty <b>mechanism</b>, <b>not RAUQ</b> and <b>not a real transformer</b>. " +
    "The \u201cattention matrices\u201d are <b>seeded synthetic</b> row-stochastic toys with the " +
    "correct/incorrect regimes <b>built in by construction</b>; there is <b>no forward pass</b> and " +
    "<b>no 4-LLM / 12-task evaluation</b>, and \u201chead selection\u201d separates a <b>hand-made " +
    "labeled toy set</b>. It shows <b>why</b> a drop in preceding-token attention can be a single-pass " +
    "uncertainty signal that output-entropy misses, but it does <b>not</b> reproduce RAUQ\u2019s " +
    "QA/summarization/translation results or its <b>&lt;1% latency</b> claim. It is explicitly a " +
    "<b>sub-organ upgrade of sement</b> \u2014 same uncertainty axis, distinct <b>single-pass-attention</b> " +
    "vs <b>multi-sample semantic-entropy</b> mechanism (the true sement signal is <b>multi-sample</b>) " +
    "\u2014 not a new axis (Vazhentsev et al., arXiv:2505.20045, 2025).";
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
  _set("rq-sel", t || (S.selectedHeads.length ? S.selectedHeads.join(", ") : "\u2014"));
  _set("rq-thr", t || fx(S.threshold, 3));
  _set("rq-ra",  t || (S.rauq.auroc != null && S.rauq.accuracy != null ? fx(S.rauq.auroc, 3) + " / " + fx(S.rauq.accuracy, 3) : "\u2014"));
  _set("rq-rf",  t || (S.rauq.precision != null ? fx(S.rauq.precision, 3) + " / " + fx(S.rauq.recall, 3) + " / " + fx(S.rauq.f1, 3) : "\u2014"));
  _set("rq-ba",  t || (S.baseline.auroc != null && S.baseline.accuracy != null ? fx(S.baseline.auroc, 3) + " / " + fx(S.baseline.accuracy, 3) : "\u2014"));
  _set("rq-bf",  t || (S.baseline.precision != null ? fx(S.baseline.precision, 3) + " / " + fx(S.baseline.recall, 3) + " / " + fx(S.baseline.f1, 3) : "\u2014"));
  _set("rq-beats", t || (S.beats == null ? "\u2014" : (S.beats ? "YES \u2014 attention-drop separates better" : "no")));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "attention uncertainty" });
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
  _group = _show = null;
  _lines = []; _nodes = []; _rails = []; _ring = null;
  _built = false;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.threshold = S.beats = null;
  S.selectedHeads = []; S.headTimelines = {};
  S.rauq = { auroc: null, accuracy: null, precision: null, recall: null, f1: null };
  S.baseline = { auroc: null, accuracy: null, precision: null, recall: null, f1: null };
  S.state = "init";
  _pulse.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
