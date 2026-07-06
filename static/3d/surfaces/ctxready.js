// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ctxready.js — CONTEXT-READY TRANSFORMER (CORRECTION-CHAIN UNROLL)
// organ for the holographic frontier ring (Mahesh Godavarti, arXiv:2606.27538).
// Renders the pre-contextualization + K-unroll mechanism as three live panels:
//   (1) PPL-PROXY CONVERGENCE CURVE — a row of bars, one per unroll step k,
//       height ∝ (ppl_proxy[k] − 1); the curve collapses toward 1.0 as the
//       correction chain settles (seq matches parallel);
//   (2) POINTER-CHASING LADDER — one tile per composition level; naive K=0
//       lights only a shallow fixed depth (staircase), the context-ready
//       K-unroll lights ALL levels solved;
//   (3) SEQ-vs-PARALLEL GAP BAR — the MEASURED |parallel_K − sequential|
//       PPL-proxy residual, shown as a single near-zero bar.
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/ctxready/unroll. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors keyless.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   L, d, D, k_unroll, levels, ppl_proxy_per_k[...], ppl_proxy_final,
//   ppl_proxy_sequential, seq_vs_parallel_gap, hidden_residual_final,
//   levels_solved_k0, levels_solved_kK, pointer_solved_k0[...],
//   pointer_solved_kK[...]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real):
//   The Context-Ready Transformer — Mahesh Godavarti. arXiv:2606.27538
//     https://arxiv.org/abs/2606.27538
//
// HONESTY LABELS: MODELED (deterministic reproduction of the pre-contextualization
//   + K-unroll MECHANISM on a toy synthetic sequence; NOT a trained transformer;
//   trains nothing; the ppl-proxy convergence, seq_vs_parallel_gap and pointer
//   levels-solved are MEASURED; NEVER-CLAIMED-AS the paper's A100 speedups or
//   dataset PPL). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "ctxready";
const TITLE = "Context-Ready Transformer";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/ctxready/unroll?seed=42&K=10&levels=10";

// data-viz hues — purple BANNED
const C_PPL   = 0x5b8dee;  // lattice-blue (ppl-proxy convergence bars)
const C_SOLVE = 0x3af4c8;  // proof-teal   (pointer level SOLVED)
const C_GAP   = 0x8a6bff;  // violet-blue  (seq-vs-parallel gap bar)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data / unsolved level)
const C_ZERO  = 0x5a6570;  // grey (settled / near-zero cell)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const PPL_MAX  = 24;    // cap unroll-step bars rendered
const BAR_W    = 0.24;  // ppl bar width
const BAR_GAP  = 0.34;  // ppl bar pitch
const LVL_MAX  = 16;    // cap pointer-ladder tiles rendered
const TILE     = 0.30;  // pointer tile size
const TILE_GAP = 0.40;  // pointer tile pitch

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor    = null;
let _pplBars  = [];    // Array<THREE.Mesh> — ppl-proxy convergence bars
let _pplGroup = null;
let _tilesK0  = [];    // Array<THREE.Mesh> — pointer ladder, naive K=0
let _tilesKK  = [];    // Array<THREE.Mesh> — pointer ladder, K-unroll
let _ladGroup = null;
let _barGap   = null;  // THREE.Mesh — seq-vs-parallel gap bar
let _gapGroup = null;

// live state
const S = {
  label:     null,
  L:         null,
  d:         null,
  D:         null,
  K:         null,   // k_unroll
  levels:    null,
  pplPerK:   null,   // Array<number>
  pplFinal:  null,   // ppl_proxy_final
  pplSeq:    null,   // ppl_proxy_sequential
  gap:       null,   // seq_vs_parallel_gap
  residFin:  null,   // hidden_residual_final
  solvedK0:  null,   // levels_solved_k0
  solvedKK:  null,   // levels_solved_kK
  maskK0:    null,   // Array<0|1>
  maskKK:    null,   // Array<0|1>
  state:     "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(5, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(2, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPplBars();
  _buildLadder();
  _buildGapBar();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onCtxready, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

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

// a row of thin bars, one per unroll step k; height ∝ (ppl_proxy[k] − 1).
function _buildPplBars() {
  const THREE = _THREE;
  _pplGroup = new THREE.Group();
  _pplGroup.position.set(-3.4, 0, 0.0);
  _group.add(_pplGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);
  for (let i = 0; i < PPL_MAX; i++) {
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_PPL, emissive: C_PPL, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(i * BAR_GAP, 0.025, 0);
    mesh.scale.y = 0.05;
    mesh.visible = false;
    _pplGroup.add(mesh);
    _pplBars.push(mesh);
  }
}

// two parallel columns of tiles (K=0 row and K-unroll row), one tile per level.
function _buildLadder() {
  const THREE = _THREE;
  _ladGroup = new THREE.Group();
  _ladGroup.position.set(0.2, 0.05, 2.6);
  _group.add(_ladGroup);
  const geo = new THREE.PlaneGeometry(TILE, TILE);

  function makeCol(offsetZ, arr) {
    for (let i = 0; i < LVL_MAX; i++) {
      const mesh = new THREE.Mesh(
        geo,
        new THREE.MeshBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.0, side: THREE.DoubleSide }),
      );
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(i * TILE_GAP, 0.02, offsetZ);
      mesh.visible = false;
      _ladGroup.add(mesh);
      arr.push(mesh);
    }
  }
  makeCol(0.0, _tilesK0);
  makeCol(TILE_GAP + 0.3, _tilesKK);
}

// single bar for the seq-vs-parallel PPL-proxy gap (should be ~0).
function _buildGapBar() {
  const THREE = _THREE;
  _gapGroup = new THREE.Group();
  _gapGroup.position.set(5.0, 0, 0.0);
  _group.add(_gapGroup);
  const geo = new THREE.BoxGeometry(0.7, 1.0, 0.7);
  _barGap = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_GAP, emissive: C_GAP, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barGap.position.set(0, 0.025, 0);
  _barGap.scale.y = 0.05;
  _gapGroup.add(_barGap);
}

// =============================================================================
// live data handler
// =============================================================================
function _onCtxready(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.L        = typeof src.L                     === "number" ? src.L                     : null;
  S.d        = typeof src.d                     === "number" ? src.d                     : null;
  S.D        = typeof src.D                     === "number" ? src.D                     : null;
  S.K        = typeof src.k_unroll              === "number" ? src.k_unroll              : null;
  S.levels   = typeof src.levels                === "number" ? src.levels                : null;
  S.pplFinal = typeof src.ppl_proxy_final       === "number" ? src.ppl_proxy_final       : null;
  S.pplSeq   = typeof src.ppl_proxy_sequential  === "number" ? src.ppl_proxy_sequential  : null;
  S.gap      = typeof src.seq_vs_parallel_gap   === "number" ? src.seq_vs_parallel_gap   : null;
  S.residFin = typeof src.hidden_residual_final === "number" ? src.hidden_residual_final : null;
  S.solvedK0 = typeof src.levels_solved_k0      === "number" ? src.levels_solved_k0      : null;
  S.solvedKK = typeof src.levels_solved_kK      === "number" ? src.levels_solved_kK      : null;

  S.pplPerK  = Array.isArray(src.ppl_proxy_per_k)  ? src.ppl_proxy_per_k  : null;
  S.maskK0   = Array.isArray(src.pointer_solved_k0) ? src.pointer_solved_k0 : null;
  S.maskKK   = Array.isArray(src.pointer_solved_kK) ? src.pointer_solved_kK : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updatePplBars();
  _updateLadder();
  _updateGapBar();
}

// ppl-proxy per k: height ∝ (value − 1), so a settled chain (→1) flattens.
function _updatePplBars() {
  const live = S.state === "live";
  const arr = (live && Array.isArray(S.pplPerK)) ? S.pplPerK : [];
  // find max (value − 1) for normalization
  let amax = 0.0;
  for (let i = 0; i < arr.length; i++) {
    const v = Math.max(0.0, arr[i] - 1.0);
    if (v > amax) amax = v;
  }
  if (amax <= 0.0) amax = 1.0;

  for (let i = 0; i < PPL_MAX; i++) {
    const mesh = _pplBars[i];
    if (!live || i >= arr.length) { mesh.visible = false; continue; }
    mesh.visible = true;
    const excess = Math.max(0.0, arr[i] - 1.0);
    const h = Math.max(0.06, (excess / amax) * 3.0);
    mesh.scale.y = h;
    mesh.position.y = h * 0.5;
    const settled = excess < 0.005;
    const color = settled ? C_ZERO : C_PPL;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = settled ? 0.15 : 0.4;
    mesh.material.opacity = settled ? 0.5 : 0.92;
  }
}

// pointer ladder: teal tile = solved, grey tile = unsolved.
function _paintCol(arr, mask) {
  const live = S.state === "live";
  const n = (live && Array.isArray(mask)) ? Math.min(mask.length, LVL_MAX) : 0;
  for (let i = 0; i < LVL_MAX; i++) {
    const mesh = arr[i];
    if (!live || i >= n) { mesh.visible = false; continue; }
    mesh.visible = true;
    const solved = mask[i] === 1 || mask[i] === true;
    const color = solved ? C_SOLVE : C_DIM;
    mesh.material.color.setHex(color);
    mesh.material.opacity = solved ? 0.9 : 0.32;
  }
}

function _updateLadder() {
  _paintCol(_tilesK0, S.maskK0);
  _paintCol(_tilesKK, S.maskKK);
}

// gap bar: height ∝ seq_vs_parallel_gap (near-zero when they match).
function _updateGapBar() {
  const live = S.state === "live";
  if (!_barGap) return;
  if (!live || S.gap == null) {
    _barGap.material.color.setHex(C_DIM);
    _barGap.material.emissive.setHex(C_DIM);
    _barGap.material.opacity = 0.3;
    _barGap.scale.y = 0.05;
    _barGap.position.y = 0.025;
    return;
  }
  // gap is tiny; amplify for visibility but floor at a visible sliver.
  const h = Math.max(0.06, Math.min(3.0, S.gap * 300.0));
  _barGap.scale.y = h;
  _barGap.position.y = h * 0.5;
  const tiny = S.gap < 1e-3;
  const color = tiny ? C_ZERO : C_GAP;
  _barGap.material.color.setHex(color);
  _barGap.material.emissive.setHex(color);
  _barGap.material.emissiveIntensity = tiny ? 0.15 : 0.4;
  _barGap.material.opacity = tiny ? 0.5 : 0.92;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.12;
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
    'The Context-Ready Transformer <b>pre-contextualizes</b> each token: a <b>correction network</b> mixes the ' +
    'previous position\u2019s block-output (a cached summary of past context) into the current token embedding ' +
    '<b>before</b> the block runs \u2014 x[t] = e[t] + \u03b1\u00b7C\u00b7h[t\u22121]. Unrolled <b>K</b> times over the full ' +
    'sequence in parallel, the correction chain converges to the exact left-to-right <b>recurrent</b> solution. ' +
    'Panels: the per-step <b>PPL-proxy</b> convergence curve (collapses toward 1.0), the <b>pointer-chasing</b> ' +
    'ladder (naive K=0 lights only a shallow depth \u2014 the staircase \u2014 while the K-unroll lights all levels ' +
    'solved), and the <b>seq-vs-parallel gap</b> bar (\u2248 0). Honesty label <b>MODELED</b> (deterministic ' +
    'mechanism reproduction on a toy sequence; trains nothing). 0 runtime CDN.';
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
  nm.textContent = "context-ready \u00b7 correction-chain unroll";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("cr-dims",     "sequence (L \u00d7 d), block depth D"));
  grid.appendChild(kpiRow("cr-k",        "unroll steps K"));
  grid.appendChild(kpiRow("cr-pplfin",   "PPL-proxy \u2014 parallel K-unroll (MEASURED)"));
  grid.appendChild(kpiRow("cr-pplseq",   "PPL-proxy \u2014 sequential recurrence"));
  grid.appendChild(kpiRow("cr-gap",      "seq-vs-parallel gap (\u2248 0)"));
  grid.appendChild(kpiRow("cr-resid",    "hidden residual @ K (settling)"));
  grid.appendChild(kpiRow("cr-levels",   "pointer-chasing levels"));
  grid.appendChild(kpiRow("cr-solvk0",   "levels solved \u2014 naive K=0 (staircase)"));
  grid.appendChild(kpiRow("cr-solvkk",   "levels solved \u2014 context-ready K-unroll"));
  grid.appendChild(kpiRow("cr-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Context-Ready Transformer \u2014 Mahesh Godavarti, \u201cThe Context-Ready Transformer\u201d arXiv:2606.27538 (arxiv.org/abs/2606.27538). MODELED \u00b7 correction-chain demo on a toy sequence, not a trained transformer; no A100 speedups or dataset PPL reproduced.";
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
  pd.id = "cr-plain";
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
  const k    = S.K        != null ? String(S.K)            : "loading\u2026";
  const gap  = S.gap      != null ? S.gap.toFixed(4)       : "loading\u2026";
  const s0   = S.solvedK0 != null ? String(S.solvedK0)     : "loading\u2026";
  const sk   = S.solvedKK != null ? String(S.solvedKK)     : "loading\u2026";
  const lv   = S.levels   != null ? String(S.levels)       : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Normally a language model must read a word, then run it through several thick layers " +
    "to figure out what it means <i>in context</i>. The Context-Ready Transformer does the opposite: before a word " +
    "even enters the block, it <b>pre-mixes</b> in a short summary of everything that came before \u2014 so the word " +
    "arrives already \u201ccontext-ready.\u201d To train it, that mixing step is <b>repeated K times</b> across the whole " +
    "sentence at once (here K=<b>" + k + "</b>). We watch a settling number (a perplexity stand-in) drop toward 1.0 " +
    "as the repeats converge, and confirm that doing it one-word-at-a-time (like a live chatbot) gives the <b>same</b> " +
    "answer \u2014 the difference here is just <b>" + gap + "</b>. On a \u201cfollow-the-pointer\u201d puzzle with <b>" + lv +
    "</b> chained hops, a naive single pass solves only <b>" + s0 + "</b>, but the repeated correction solves <b>" + sk +
    "</b> of them. This view is a <b>MODELED</b> deterministic reproduction of that MECHANISM on a tiny synthetic " +
    "sequence \u2014 it <b>trains no model</b> and runs no GPU. The paper\u2019s headline results \u2014 a 1.7\u00d7\u20132.6\u00d7 " +
    "speedup on an A100 and its dataset perplexity numbers \u2014 are <b>claims about real training runs</b> the " +
    "estate does not independently verify.";
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
  _set("cr-dims",   t || ((S.L != null && S.d != null && S.D != null) ? (S.L + " \u00d7 " + S.d + ", D=" + S.D) : "\u2014"));
  _set("cr-k",      t || (S.K != null ? String(S.K) : "\u2014"));
  _set("cr-pplfin", t || fx(S.pplFinal, 4));
  _set("cr-pplseq", t || fx(S.pplSeq, 4));
  _set("cr-gap",    t || fx(S.gap, 4));
  _set("cr-resid",  t || fx(S.residFin, 5));
  _set("cr-levels", t || (S.levels != null ? String(S.levels) : "\u2014"));
  _set("cr-solvk0", t || (S.solvedK0 != null ? String(S.solvedK0) : "\u2014"));
  _set("cr-solvkk", t || (S.solvedKK != null ? String(S.solvedKK) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("cr-label",  t || (S.label || "MODELED"));
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
  _floor = null;
  _pplBars = []; _pplGroup = null;
  _tilesK0 = []; _tilesKK = []; _ladGroup = null;
  _barGap = null; _gapGroup = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.L = S.d = S.D = S.K = S.levels = null;
  S.pplPerK = S.pplFinal = S.pplSeq = S.gap = S.residFin = null;
  S.solvedK0 = S.solvedKK = S.maskK0 = S.maskKK = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
