// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/nested.js — NESTED LEARNING / CONTINUUM MEMORY SYSTEM ("Hope")
// organ for the holographic frontier ring (Behrouz, Razaviyayn, Zhong &
// Mirrokni, Google Research, NeurIPS 2025 — "the illusion of deep learning
// architectures"). Renders a THREE-TIER PLASTICITY LADDER of memory levels at
// different update clocks (fast k=1, medium k=8, slow k=64), fed by a streaming
// toy continual-learning task-block sequence. A HUD contrasts the FORGETTING
// CURVE of task A for a single-clock baseline vs the multi-timescale CMS
// schedule from the live snapshot at /api/killinchu/v1/nested/schedule. The
// slow "core" (protected by a surprise gate) glows proof-teal as it retains
// early tasks; the always-on baseline overwrites and forgets (grey). Honesty
// label "MODELED" is read VERBATIM from the JSON and displayed as-is; never
// upgraded.
//
// Surface export shape (mirrors titans.js / episodic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint, inside payload):
//   num_tasks, block_len, n_tokens, k_fast, k_med, k_slow, gate, levels[],
//   taskA_baseline[], taskA_cms[], retainedA_baseline, retainedA_cms,
//   retention_delta, mean_retention_delta, slow_writes_cms,
//   slow_writes_baseline, mean_surprise, peak_surprise, momentum, forget_curve[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Nested Learning: The Illusion of Deep Learning Architectures (the paradigm,
//   Continuum Memory System, and "Hope" proof-of-concept simulated here):
//     Behrouz, Razaviyayn, Zhong & Mirrokni 2025, Google Research, NeurIPS 2025
//     https://arxiv.org/abs/2512.24695
//   Google Research blog — Introducing Nested Learning (official announcement):
//     https://research.google/blog/introducing-nested-learning-a-new-ml-paradigm-for-continual-learning/
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the multi-
//   timescale update-scheduling + optimizer-as-memory arithmetic; NOT the Hope
//   architecture; NEVER-CLAIMED-AS a trained model). Independent-ablation
//   nuance: the NeurIPS paper was noted in public commentary to lack full
//   ablations in its first version, so this demonstrates the SCHEDULING
//   MECHANISM reduces forgetting on a controlled toy stream — NOT reproducing
//   Hope's benchmark wins. Read verbatim from JSON; never upgraded here. The
//   endpoint nests its fields under `payload`, with the label at the top level —
//   this surface handles the label at top-level OR inside payload.label
//   defensively.
// COLOURS: lattice-blue 0x5b8dee (fast level / task stream / spine), violet-blue
//   0x8a6bff (medium level / clock ring), proof-teal 0x3af4c8 (protected slow
//   core / retention / HUD accent), greys (forgotten / degraded state). Purple
//   BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "nested";
const TITLE = "Nested Learning · Continuum Memory System (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the nested organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/nested/schedule?seed=42&num_tasks=6&k_fast=1&k_med=8&k_slow=64&gate=0.15";

// data-viz hues — purple BANNED
const C_FAST    = 0x5b8dee;  // lattice-blue (fast level / task stream / spine)
const C_MED     = 0x8a6bff;  // violet-blue (medium level / clock ring)
const C_SLOW    = 0x3af4c8;  // proof-teal (protected slow core / retention / HUD accent)
const C_FORGET  = 0x5a6570;  // grey (forgotten / overwritten baseline point)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// layout geometry
const LEVEL_Y     = [0.7, 2.2, 3.7];  // y of fast / med / slow tiers (bottom -> top)
const LEVEL_R     = [1.4, 2.6, 3.8];  // ring radius of each tier
const RING_SEG    = 64;                // ring outline segments
const MAX_BLOCKS  = 96;                // cap on forgetting-curve markers rendered
const CURVE_SPAN  = 12.0;              // world-units the forgetting curve spans along X

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _rings      = [];                 // Array<THREE.LineLoop> — one clock ring per level
let _tiers      = [];                 // Array<THREE.Mesh> — the three memory-level nodes
let _baseMarks  = [];                 // Array<THREE.Mesh> — baseline forgetting-curve markers
let _cmsMarks   = [];                 // Array<THREE.Mesh> — CMS forgetting-curve markers
let _core       = null;               // THREE.Mesh — central slow-core "retention" node

// live state
const S = {
  label:        null,
  numTasks:     null,   // num_tasks
  blockLen:     null,   // block_len
  nTokens:      null,   // n_tokens
  kFast:        null,   // k_fast
  kMed:         null,   // k_med
  kSlow:        null,   // k_slow
  gate:         null,   // gate
  taskABase:    null,   // taskA_baseline[]
  taskACms:     null,   // taskA_cms[]
  retainBase:   null,   // retainedA_baseline
  retainCms:    null,   // retainedA_cms
  retDelta:     null,   // retention_delta
  meanDelta:    null,   // mean_retention_delta
  slowWritesCms:  null, // slow_writes_cms
  slowWritesBase: null, // slow_writes_baseline
  meanSurprise: null,   // mean_surprise
  peakSurprise: null,   // peak_surprise
  momentum:     null,   // momentum
  curve:        null,   // forget_curve[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLadder();
  _buildCurve();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onNested, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// The plasticity LADDER: three stacked clock rings (fast/med/slow) each with a
// central level node. Higher rings = slower clocks = more protected memory.
function _buildLadder() {
  const THREE = _THREE;
  const cols = [C_FAST, C_MED, C_SLOW];

  for (let lvl = 0; lvl < 3; lvl++) {
    const r = LEVEL_R[lvl];
    const y = LEVEL_Y[lvl];

    // clock ring outline
    const pts = [];
    for (let i = 0; i <= RING_SEG; i++) {
      const a = (i / RING_SEG) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: cols[lvl], transparent: true, opacity: 0.4 });
    const ring = new THREE.LineLoop(geo, mat);
    _group.add(ring);
    _rings.push(ring);

    // level node (the memory level itself)
    const node = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.34, 0),
      new THREE.MeshStandardMaterial({ color: cols[lvl], emissive: cols[lvl], emissiveIntensity: 0.3, transparent: true, opacity: 0.85 }),
    );
    node.position.set(0, y, 0);
    _group.add(node);
    _tiers.push(node);
  }
}

// Two rows of forgetting-curve markers streaming along X: task-A accuracy after
// each task block for the single-clock baseline (front row) and the multi-
// timescale CMS schedule (back row). Height encodes retained accuracy.
function _buildCurve() {
  const THREE = _THREE;
  const mGeo = new THREE.SphereGeometry(0.13, 8, 8);
  for (let i = 0; i < MAX_BLOCKS; i++) {
    const x = -CURVE_SPAN / 2 + (i / (MAX_BLOCKS - 1)) * CURVE_SPAN;

    const b = new THREE.Mesh(
      mGeo,
      new THREE.MeshStandardMaterial({ color: C_FORGET, emissive: C_FORGET, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    b.position.set(x, 0.2, 2.4);
    b.visible = false;
    _group.add(b);
    _baseMarks.push(b);

    const c = new THREE.Mesh(
      mGeo,
      new THREE.MeshStandardMaterial({ color: C_SLOW, emissive: C_SLOW, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    c.position.set(x, 0.2, -2.4);
    c.visible = false;
    _group.add(c);
    _cmsMarks.push(c);
  }
}

function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.6, 1),
    new THREE.MeshStandardMaterial({ color: C_SLOW, emissive: C_SLOW, emissiveIntensity: 0.45, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, LEVEL_Y[2], 0);
  _group.add(_core);
}

// =============================================================================
// live data handler
// =============================================================================
function _onNested(j) {
  // The endpoint nests its metrics under `payload`; the honesty label may sit at
  // the TOP LEVEL or (defensively) inside payload.label. Read it VERBATIM from
  // wherever it is — never upgrade.
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label        = String(rawLabel).toUpperCase();

  S.numTasks     = typeof p.num_tasks   === "number" ? p.num_tasks   : null;
  S.blockLen     = typeof p.block_len   === "number" ? p.block_len   : null;
  S.nTokens      = typeof p.n_tokens    === "number" ? p.n_tokens    : null;
  S.kFast        = typeof p.k_fast      === "number" ? p.k_fast      : null;
  S.kMed         = typeof p.k_med       === "number" ? p.k_med       : null;
  S.kSlow        = typeof p.k_slow      === "number" ? p.k_slow      : null;
  S.gate         = typeof p.gate        === "number" ? p.gate        : null;
  S.retainBase   = typeof p.retainedA_baseline === "number" ? p.retainedA_baseline : null;
  S.retainCms    = typeof p.retainedA_cms      === "number" ? p.retainedA_cms      : null;
  S.retDelta     = typeof p.retention_delta    === "number" ? p.retention_delta    : null;
  S.meanDelta    = typeof p.mean_retention_delta === "number" ? p.mean_retention_delta : null;
  S.slowWritesCms  = typeof p.slow_writes_cms      === "number" ? p.slow_writes_cms      : null;
  S.slowWritesBase = typeof p.slow_writes_baseline === "number" ? p.slow_writes_baseline : null;
  S.meanSurprise = typeof p.mean_surprise === "number" ? p.mean_surprise : null;
  S.peakSurprise = typeof p.peak_surprise === "number" ? p.peak_surprise : null;
  S.momentum     = typeof p.momentum      === "number" ? p.momentum      : null;
  S.taskABase    = Array.isArray(p.taskA_baseline) ? p.taskA_baseline : null;
  S.taskACms     = Array.isArray(p.taskA_cms)      ? p.taskA_cms      : null;
  S.curve        = Array.isArray(p.forget_curve)   ? p.forget_curve   : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the ladder + forgetting curve from live data
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const cols = [C_FAST, C_MED, C_SLOW];

  // clock rings + level nodes degrade to grey when not live
  for (let lvl = 0; lvl < 3; lvl++) {
    const ring = _rings[lvl];
    if (ring) {
      ring.material.color.setHex(live ? cols[lvl] : C_DIM);
      ring.material.opacity = live ? 0.4 : 0.12;
    }
    const node = _tiers[lvl];
    if (node) {
      const c = live ? cols[lvl] : C_FORGET;
      node.material.color.setHex(c);
      node.material.emissive.setHex(c);
      node.material.emissiveIntensity = live ? 0.35 : 0.08;
      node.material.opacity = live ? 0.9 : 0.25;
    }
  }

  // forgetting-curve markers: height = retained task-A accuracy per block.
  const base = live && S.taskABase && S.taskABase.length ? S.taskABase.slice(0, MAX_BLOCKS) : [];
  const cms  = live && S.taskACms  && S.taskACms.length  ? S.taskACms.slice(0, MAX_BLOCKS)  : [];
  const n = Math.max(base.length, cms.length);
  for (let i = 0; i < MAX_BLOCKS; i++) {
    const bm = _baseMarks[i];
    const cm = _cmsMarks[i];
    if (!live || i >= n) { bm.visible = false; cm.visible = false; continue; }

    if (i < base.length) {
      const a = base[i];
      bm.visible = true;
      bm.position.y = 0.2 + a * 3.2;
      // baseline that has forgotten (low retention) fades to grey
      const c = a >= 0.5 ? C_FAST : C_FORGET;
      bm.material.color.setHex(c);
      bm.material.emissive.setHex(c);
      bm.material.emissiveIntensity = 0.2 + 0.5 * a;
      bm.material.opacity = 0.35 + 0.55 * a;
      bm.scale.setScalar(0.7 + 0.7 * a);
    } else { bm.visible = false; }

    if (i < cms.length) {
      const a = cms[i];
      cm.visible = true;
      cm.position.y = 0.2 + a * 3.2;
      cm.material.color.setHex(C_SLOW);
      cm.material.emissive.setHex(C_SLOW);
      cm.material.emissiveIntensity = 0.25 + 0.6 * a;
      cm.material.opacity = 0.4 + 0.55 * a;
      cm.scale.setScalar(0.7 + 0.7 * a);
    } else { cm.visible = false; }
  }

  // slow core: size/brightness reflect how much of task A the protected core
  // retains (retainedA_cms), and pulse brighter with the retention advantage.
  if (_core) {
    if (live && S.retainCms != null) {
      _core.material.color.setHex(C_SLOW);
      _core.material.emissive.setHex(C_SLOW);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.6 + S.retainCms * 1.0);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.6);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.14;
  // rings spin at their own clock rate — fast ring spins fastest
  if (_rings[0]) _rings[0].rotation.y += 0.010;
  if (_rings[1]) _rings[1].rotation.y += 0.0035;
  if (_rings[2]) _rings[2].rotation.y += 0.0009;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.009;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.retainCms != null) ? (0.6 + S.retainCms * 1.0) : 0.6;
    _core.scale.setScalar(base * pulse);
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
    'A model as a stack of memory levels updating at <b>different clocks</b> (fast/medium/slow), with ' +
    'the <b>optimizer itself as associative memory</b>. On a toy continual-learning stream, the slow ' +
    '<b>protected core</b> (a surprise-gated timescale) <b>retains earlier tasks</b> where a single-clock ' +
    'baseline overwrites and <b>forgets</b> them. ' +
    'Honesty label <b>MODELED</b> (deterministic scheduling simulation; NOT the Hope architecture). 0 runtime CDN.';
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
  nm.textContent = "nested learning / continuum memory system";
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

  grid.appendChild(kpiRow("ne-tasks",   "continual-learning tasks"));
  grid.appendChild(kpiRow("ne-clocks",  "clocks k_fast / k_med / k_slow"));
  grid.appendChild(kpiRow("ne-gate",    "slow-core surprise gate"));
  grid.appendChild(kpiRow("ne-retbase", "task-A retained \u2014 single-clock"));
  grid.appendChild(kpiRow("ne-retcms",  "task-A retained \u2014 CMS (MODELED)"));
  grid.appendChild(kpiRow("ne-delta",   "retention gain (CMS \u2212 baseline)"));
  grid.appendChild(kpiRow("ne-writes",  "slow-core writes CMS / baseline"));
  grid.appendChild(kpiRow("ne-surprise","mean / peak surprise"));
  grid.appendChild(kpiRow("ne-momentum","momentum (optimizer-as-memory)"));
  grid.appendChild(kpiRow("ne-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Behrouz, Razaviyayn, Zhong & Mirrokni 2025 (Google Research) \u00b7 Nested Learning: The Illusion of Deep Learning Architectures \u00b7 NeurIPS 2025 \u00b7 arXiv:2512.24695 \u00b7 research.google/blog Nested Learning. MODELED \u00b7 not claimed-as.";
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
  pd.id = "ne-plain";
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
  const rBase = S.retainBase != null ? (S.retainBase * 100).toFixed(0) + "%" : "loading\u2026";
  const rCms  = S.retainCms  != null ? (S.retainCms  * 100).toFixed(0) + "%" : "loading\u2026";
  const dPct  = S.retDelta   != null ? "+" + (S.retDelta * 100).toFixed(0) + " points" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> When an AI learns a new skill it often <b>forgets the old one</b> " +
    "(\u201ccatastrophic forgetting\u201d). Nested Learning treats the model as a <b>stack of memories that " +
    "update at different speeds</b> \u2014 a fast one that chases whatever it is learning right now, and " +
    "slower ones that only commit knowledge once it has <b>settled</b>. The slowest \u201ccore\u201d is " +
    "<b>protected</b>: it refuses to overwrite itself during the noisy middle of learning something new. " +
    "Here we teach it several small tasks in a row and then check how much of the <b>first</b> task it still " +
    "remembers. A plain single-speed model keeps only about <b>" + rBase + "</b> of task A, while the " +
    "multi-speed schedule keeps about <b>" + rCms + "</b> \u2014 a gain of roughly <b>" + dPct + "</b> less " +
    "forgetting on this toy stream. " +
    "<b>Honest caveat:</b> this is a <b>MODELED</b> toy simulation of the scheduling idea (tiny linear " +
    "tasks, hand-set clocks), <b>not the \u201cHope\u201d model</b>. The paper was noted publicly to lack full " +
    "ablations in its first version, so this only shows the <b>scheduling mechanism</b> reduces forgetting " +
    "on a controlled stream \u2014 it does <b>not</b> reproduce Hope's language-modeling or needle-in-haystack " +
    "results or its claimed wins over Titans / Transformers.";
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
  _set("ne-tasks",   t || (S.numTasks != null ? String(S.numTasks) : "\u2014"));
  _set("ne-clocks",  t || (S.kFast != null || S.kMed != null || S.kSlow != null
        ? (S.kFast != null ? String(S.kFast) : "\u2014") + " / " +
          (S.kMed  != null ? String(S.kMed)  : "\u2014") + " / " +
          (S.kSlow != null ? String(S.kSlow) : "\u2014")
        : "\u2014"));
  _set("ne-gate",    t || fx(S.gate, 3));
  _set("ne-retbase", t || pct(S.retainBase, 1));
  _set("ne-retcms",  t || pct(S.retainCms, 1));
  _set("ne-delta",   t || (S.retDelta != null ? "+" + (S.retDelta * 100).toFixed(1) + "%" : "\u2014"));
  _set("ne-writes",  t || (S.slowWritesCms != null || S.slowWritesBase != null
        ? (S.slowWritesCms != null ? String(S.slowWritesCms) : "\u2014") + " / " +
          (S.slowWritesBase != null ? String(S.slowWritesBase) : "\u2014")
        : "\u2014"));
  _set("ne-surprise", t || (S.meanSurprise != null || S.peakSurprise != null
        ? fx(S.meanSurprise, 3) + " / " + fx(S.peakSurprise, 3)
        : "\u2014"));
  _set("ne-momentum", t || fx(S.momentum, 2));
  // honesty label verbatim — never upgraded
  _set("ne-label", t || (S.label || "MODELED"));
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
  _floor = null; _rings = []; _tiers = []; _baseMarks = []; _cmsMarks = []; _core = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.numTasks = S.blockLen = S.nTokens = null;
  S.kFast = S.kMed = S.kSlow = S.gate = null;
  S.taskABase = S.taskACms = null;
  S.retainBase = S.retainCms = S.retDelta = S.meanDelta = null;
  S.slowWritesCms = S.slowWritesBase = null;
  S.meanSurprise = S.peakSurprise = S.momentum = null;
  S.curve = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
