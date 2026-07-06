// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/slidesparse.js — STRUCTURED-SPARSE LAYOUT PACKING organ for the
// holographic frontier ring (SlideSparse (2N-2):2N sliding-window decomposition
// + activation lifting, Furu Wei group-style). Renders one 2N-wide structured-
// sparse weight block as a row of cells, then lifts it into N-1 OVERLAPPING
// 4-wide 2:4 windows stacked above it — each window 2:4-compliant (<=2 nonzeros
// per 4) — visually showing that the N-1 windows recompose the block EXACTLY
// (lossless). A throughput-proxy bar trio compares dense (lattice-blue), strict-
// 2:4 (grey/over-pruned) and slidesparse (proof-teal) effective-MAC speedups
// against the N/(N-1) ceiling read live from /api/killinchu/v1/slidesparse/pack.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is; it
// is never upgraded.
//
// Surface export shape (mirrors ternary.js / aimc.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   N, block_width, windows_per_block, sparsity_pattern, prune_fraction,
//   matrix_rows, matrix_cols, blocks_total, mode, reconstruction_error, lossless,
//   slidesparse_recon_error, strict_2to4_recon_error, dense_macs,
//   strict_2to4_macs, slidesparse_macs, speedup_dense, speedup_strict_2to4,
//   speedup_slidesparse, throughput_ceiling, ceiling_gap,
//   activation_lifting_perm[], sample_window_masks[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   SlideSparse: Fast and Flexible (2N-2):2N Structured Sparsity (mechanism
//   simulated here):
//     Shao, Hao, Song, Xia, Zhang, Huang, Wu, Xu, Xu, Dong, Chi, Zou, Wei
//     (Furu Wei group)  arXiv:2603.05232  https://arxiv.org/abs/2603.05232
//
// HONESTY LABELS: MODELED (deterministic reproduction of the SlideSparse sliding-
//   window-decomposition + activation-lifting PACKING mechanism on a toy synthetic
//   matrix; NO GPU, NO Sparse Tensor Core, NO vLLM, NO CUDA; 'throughput' is a
//   counted MAC proxy, 'accuracy' a reconstruction-error proxy; NEVER-CLAIMED-AS a
//   real tensor-core run or SlideSparse's 1.33x Qwen2.5-7B result). Read verbatim
//   from JSON; never upgraded here. NEW AXIS: structured-sparse layout/packing —
//   orthogonal to ternary bit-precision + aimc analog compute.
// COLOURS: proof-teal 0x3af4c8 (slidesparse path / kept nonzero / HUD accent),
//   lattice-blue 0x5b8dee (dense baseline / block cells), violet-blue 0x8a6bff
//   (window frame / activation-lifting accent), greys (pruned zeros / strict-2:4
//   over-prune / degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "slidesparse";
const TITLE = "Structured-Sparse Layout Packing · SlideSparse (2N-2):2N (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
// This keeps the slidesparse organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/slidesparse/pack?seed=42&N=4&mode=slidesparse";

// data-viz hues — purple BANNED
const C_SLIDE   = 0x3af4c8;  // proof-teal (slidesparse path / kept nonzero)
const C_DENSE   = 0x5b8dee;  // lattice-blue (dense baseline / block cell)
const C_WINDOW  = 0x8a6bff;  // violet-blue (window frame / activation-lifting)
const C_PRUNE   = 0x5a6570;  // grey (pruned zero / dropped weight)
const C_STRICT  = 0x6b7a86;  // grey (strict-2:4 over-pruned baseline)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// layout geometry
const MAX_BLOCK   = 32;    // cap on block cells rendered (perf): 2N <= MAX_BLOCK
const MAX_WINDOWS = 15;    // cap on windows rendered (perf): N-1 <= MAX_WINDOWS
const CELL_GAP    = 0.6;   // world-units between block cells along X
const WIN_Y_GAP   = 0.62;  // vertical spacing between stacked windows
const BLOCK_Y     = 0.4;   // resting height of the source block row
const MAX_BAR_H   = 4.2;   // world-units — throughput bar height at ceiling
const MIN_BAR_H   = 0.04;  // floor height so a bar never fully vanishes
const BAR_GAP     = 1.1;   // spacing between the three throughput bars

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor     = null;
let _blockCell = [];                 // Array<THREE.Mesh> — the 2N source-block cells
let _winCell   = [];                 // Array<Array<THREE.Mesh>> — window x 4 cells
let _winFrame  = [];                 // Array<THREE.LineSegments> — window frames
let _barDense  = null;               // THREE.Mesh — dense speedup bar
let _barStrict = null;               // THREE.Mesh — strict-2:4 speedup bar
let _barSlide  = null;               // THREE.Mesh — slidesparse speedup bar
let _ceilLine  = null;               // THREE.Line — N/(N-1) ceiling marker
let _liftMark  = null;               // THREE.Mesh — activation-lifting pulse marker

// live state
const S = {
  label:        null,
  N:            null,
  blockWidth:   null,   // block_width (2N)
  winsPerBlock: null,   // windows_per_block (N-1)
  pattern:      null,   // sparsity_pattern e.g. "6:8"
  pruneFrac:    null,   // prune_fraction
  rows:         null,   // matrix_rows
  cols:         null,   // matrix_cols
  blocksTotal:  null,   // blocks_total
  mode:         null,   // mode
  reconErr:     null,   // reconstruction_error (for mode)
  lossless:     null,   // lossless
  slideRecon:   null,   // slidesparse_recon_error
  strictRecon:  null,   // strict_2to4_recon_error
  denseMacs:    null,   // dense_macs
  strictMacs:   null,   // strict_2to4_macs
  slideMacs:    null,   // slidesparse_macs
  spDense:      null,   // speedup_dense
  spStrict:     null,   // speedup_strict_2to4
  spSlide:      null,   // speedup_slidesparse
  ceiling:      null,   // throughput_ceiling N/(N-1)
  ceilingGap:   null,   // ceiling_gap
  liftPerm:     null,   // activation_lifting_perm[]
  winMasks:     null,   // sample_window_masks[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 7, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildBlock();
  _buildWindows();
  _buildBars();
  _buildLiftMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSlide, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// The 2N-wide structured-sparse source block: a row of cells along X. Kept
// nonzeros glow lattice-blue; the 2 dropped (pruned) entries fade to grey and
// sink. Coloured in-place from the live window masks (no per-poll churn).
function _buildBlock() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(0.34, 0.34, 0.34);
  for (let i = 0; i < MAX_BLOCK; i++) {
    const mesh = new THREE.Mesh(
      cellGeo,
      new THREE.MeshStandardMaterial({ color: C_PRUNE, emissive: C_PRUNE, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(i * CELL_GAP, BLOCK_Y, 0);
    mesh.visible = false;
    _group.add(mesh);
    _blockCell.push(mesh);
  }
}

// N-1 overlapping 4-wide 2:4 windows, stacked upward above the source block.
// Each window is a violet-blue wireframe frame around its 4 cells; kept nonzeros
// in a window glow proof-teal, empty slots stay grey. Positioned at the window's
// column offset so it visually overlays the exact columns it recomposes.
function _buildWindows() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(0.28, 0.28, 0.28);
  for (let w = 0; w < MAX_WINDOWS; w++) {
    const row = [];
    for (let k = 0; k < 4; k++) {
      const mesh = new THREE.Mesh(
        cellGeo,
        new THREE.MeshStandardMaterial({ color: C_PRUNE, emissive: C_PRUNE, emissiveIntensity: 0.12, transparent: true, opacity: 0.0 }),
      );
      mesh.visible = false;
      _group.add(mesh);
      row.push(mesh);
    }
    _winCell.push(row);

    // window frame (violet-blue wireframe box spanning the 4-wide window)
    const frameGeo = new THREE.BoxGeometry(4 * CELL_GAP, 0.5, 0.5);
    const edges = new THREE.EdgesGeometry(frameGeo);
    const frame = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: C_WINDOW, transparent: true, opacity: 0.0 }),
    );
    frame.visible = false;
    _group.add(frame);
    _winFrame.push(frame);
  }
}

// Three throughput-proxy bars (dense / strict-2:4 / slidesparse effective-MAC
// speedup) plus a horizontal N/(N-1) ceiling marker line the slidesparse bar
// should reach but never exceed.
function _buildBars() {
  const THREE = _THREE;
  const barGeo = new THREE.BoxGeometry(0.5, 1, 0.5);
  barGeo.translate(0, 0.5, 0); // base at y=0; scaling Y grows upward

  function mkBar(color, emis) {
    const m = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: emis, transparent: true, opacity: 0.9 }),
    );
    m.scale.set(1, MIN_BAR_H, 1);
    m.visible = false;
    _group.add(m);
    return m;
  }
  const baseX = -3.2, baseZ = -3.0;
  _barDense  = mkBar(C_DENSE, 0.3);  _barDense.position.set(baseX,               0, baseZ);
  _barStrict = mkBar(C_STRICT, 0.25); _barStrict.position.set(baseX + BAR_GAP,   0, baseZ);
  _barSlide  = mkBar(C_SLIDE, 0.45); _barSlide.position.set(baseX + 2 * BAR_GAP, 0, baseZ);

  const pts = [
    new THREE.Vector3(baseX - 0.5, MIN_BAR_H, baseZ),
    new THREE.Vector3(baseX + 2 * BAR_GAP + 0.5, MIN_BAR_H, baseZ),
  ];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  _ceilLine = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_WINDOW, transparent: true, opacity: 0.6 }));
  _group.add(_ceilLine);
}

function _buildLiftMarker() {
  const THREE = _THREE;
  _liftMark = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.3, 1),
    new THREE.MeshStandardMaterial({ color: C_WINDOW, emissive: C_WINDOW, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _liftMark.position.set(-1.2, 1.4, 2.2);
  _group.add(_liftMark);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSlide(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;

  S.label        = String(lbl).toUpperCase();
  S.N            = typeof src.N                       === "number" ? src.N                       : null;
  S.blockWidth   = typeof src.block_width             === "number" ? src.block_width             : null;
  S.winsPerBlock = typeof src.windows_per_block       === "number" ? src.windows_per_block       : null;
  S.pattern      = typeof src.sparsity_pattern        === "string" ? src.sparsity_pattern        : null;
  S.pruneFrac    = typeof src.prune_fraction          === "number" ? src.prune_fraction          : null;
  S.rows         = typeof src.matrix_rows             === "number" ? src.matrix_rows             : null;
  S.cols         = typeof src.matrix_cols             === "number" ? src.matrix_cols             : null;
  S.blocksTotal  = typeof src.blocks_total            === "number" ? src.blocks_total            : null;
  S.mode         = typeof src.mode                    === "string" ? src.mode                    : null;
  S.reconErr     = typeof src.reconstruction_error    === "number" ? src.reconstruction_error    : null;
  S.lossless     = typeof src.lossless                === "boolean" ? src.lossless               : null;
  S.slideRecon   = typeof src.slidesparse_recon_error === "number" ? src.slidesparse_recon_error : null;
  S.strictRecon  = typeof src.strict_2to4_recon_error === "number" ? src.strict_2to4_recon_error : null;
  S.denseMacs    = typeof src.dense_macs              === "number" ? src.dense_macs              : null;
  S.strictMacs   = typeof src.strict_2to4_macs        === "number" ? src.strict_2to4_macs        : null;
  S.slideMacs    = typeof src.slidesparse_macs        === "number" ? src.slidesparse_macs        : null;
  S.spDense      = typeof src.speedup_dense           === "number" ? src.speedup_dense           : null;
  S.spStrict     = typeof src.speedup_strict_2to4     === "number" ? src.speedup_strict_2to4     : null;
  S.spSlide      = typeof src.speedup_slidesparse     === "number" ? src.speedup_slidesparse     : null;
  S.ceiling      = typeof src.throughput_ceiling      === "number" ? src.throughput_ceiling      : null;
  S.ceilingGap   = typeof src.ceiling_gap             === "number" ? src.ceiling_gap             : null;
  S.liftPerm     = Array.isArray(src.activation_lifting_perm) ? src.activation_lifting_perm : null;
  S.winMasks     = Array.isArray(src.sample_window_masks)     ? src.sample_window_masks     : null;

  _updateBlock();
  _updateWindows();
  _updateBars();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
// Which block columns are kept (nonzero)? Derive from the live window masks:
// every column that appears (mask=1) in some window is a kept nonzero; the rest
// are the pruned/dropped entries. Client never invents structure it cannot see.
function _keptColumns() {
  const kept = {};
  if (!S.winMasks) return kept;
  for (const win of S.winMasks) {
    if (!win || !Array.isArray(win.mask)) continue;
    const off = typeof win.offset === "number" ? win.offset : 0;
    for (let k = 0; k < 4; k++) {
      if (win.mask[k]) kept[off + k] = true;
    }
  }
  return kept;
}

function _updateBlock() {
  const live = S.state === "live";
  const width = live && S.blockWidth ? Math.min(S.blockWidth, MAX_BLOCK) : 0;
  const kept = _keptColumns();
  for (let i = 0; i < MAX_BLOCK; i++) {
    const mesh = _blockCell[i];
    if (!live || i >= width) { mesh.visible = false; continue; }
    mesh.visible = true;
    const isKept = kept[i] === true;
    const color = isKept ? C_DENSE : C_PRUNE;   // kept -> lattice-blue; dropped -> grey
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = isKept ? 0.5 : 0.12;
    mesh.material.opacity = isKept ? 0.95 : 0.3;
    mesh.position.y = isKept ? BLOCK_Y : BLOCK_Y - 0.3;  // dropped entries sink
  }
}

function _updateWindows() {
  const live = S.state === "live";
  const masks = live && S.winMasks ? S.winMasks : [];
  for (let w = 0; w < MAX_WINDOWS; w++) {
    const has = live && w < masks.length;
    const row = _winCell[w];
    const frame = _winFrame[w];
    if (!has) {
      for (let k = 0; k < 4; k++) row[k].visible = false;
      frame.visible = false;
      continue;
    }
    const win = masks[w];
    const off = typeof win.offset === "number" ? win.offset : 0;
    const yLevel = BLOCK_Y + (w + 1) * WIN_Y_GAP + 0.6;
    for (let k = 0; k < 4; k++) {
      const mesh = row[k];
      mesh.visible = true;
      const on = win.mask && win.mask[k];
      const color = on ? C_SLIDE : C_PRUNE;   // kept nonzero -> proof-teal; empty -> grey
      mesh.material.color.setHex(color);
      mesh.material.emissive.setHex(color);
      mesh.material.emissiveIntensity = on ? 0.55 : 0.1;
      mesh.material.opacity = on ? 0.95 : 0.2;
      mesh.position.set((off + k) * CELL_GAP, yLevel, 0);
    }
    frame.visible = true;
    frame.material.opacity = 0.45;
    frame.position.set((off + 1.5) * CELL_GAP, yLevel, 0);
  }
}

function _updateBars() {
  const live = S.state === "live";
  const ceiling = live && typeof S.ceiling === "number" && S.ceiling > 0 ? S.ceiling : 1.0;
  // scale so the N/(N-1) ceiling sits at MAX_BAR_H; dense (1.0) is the reference.
  const scaleFor = (v) => {
    if (typeof v !== "number") return MIN_BAR_H;
    return Math.max(MIN_BAR_H, (v / ceiling) * MAX_BAR_H);
  };

  const showBar = (bar, v, colorLive) => {
    bar.visible = live;
    if (!live) return;
    bar.scale.y = scaleFor(v);
    const c = live ? colorLive : C_DIM;
    bar.material.color.setHex(c);
    bar.material.emissive.setHex(c);
  };
  showBar(_barDense,  S.spDense,  C_DENSE);
  showBar(_barStrict, S.spStrict, C_STRICT);
  showBar(_barSlide,  S.spSlide,  C_SLIDE);

  if (_ceilLine) {
    // ceiling marker sits at MAX_BAR_H (the N/(N-1) line)
    _ceilLine.position.y = live ? MAX_BAR_H : MIN_BAR_H;
    _ceilLine.material.opacity = live ? 0.6 : 0.12;
    _ceilLine.material.color.setHex(live ? C_WINDOW : C_DIM);
  }
  if (_liftMark) {
    const c = live ? C_WINDOW : C_DIM;
    _liftMark.material.color.setHex(c);
    _liftMark.material.emissive.setHex(c);
    _liftMark.material.opacity = live ? 0.85 : 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.12;
  if (_liftMark) {
    _liftMark.rotation.y += 0.024;
    _liftMark.rotation.x += 0.011;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _liftMark.scale.setScalar(pulse);
  }
  // gentle upward shimmer on the window cells to suggest the lift/decomposition
  for (let w = 0; w < _winCell.length; w++) {
    const row = _winCell[w];
    for (let k = 0; k < 4; k++) {
      const m = row[k];
      if (m.visible) m.material.emissiveIntensity = 0.2 + 0.2 * (0.5 + 0.5 * Math.sin(t * 0.003 + (w * 4 + k) * 0.5));
    }
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
    'NVIDIA Sparse Tensor Cores accelerate ONLY the rigid <b>2:4</b> pattern (50% prune) \u2014 often ' +
    'too harsh for accuracy. Milder <b>(2N-2):2N</b> patterns (e.g. <b>6:8</b>, 25% prune) keep ' +
    'accuracy but get no hardware support. SlideSparse is a pure <b>data-layout / packing</b> ' +
    'transform: a <b>sliding-window decomposition</b> splits each (2N-2):2N block into <b>N-1 ' +
    'overlapping 4-wide 2:4 windows</b> that recompose the block <b>EXACTLY</b> (lossless), so mild ' +
    'sparsity runs on existing 2:4 cores; <b>activation lifting</b> fuses the matching activation ' +
    'rearrangement. Honesty label <b>MODELED</b> \u2014 a toy counted-MAC proxy, NOT a GPU/tensor-core ' +
    'run. 0 runtime CDN.';
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
  nm.textContent = "structured-sparse layout packing";
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

  grid.appendChild(kpiRow("ss-pattern",  "sparsity pattern (2N-2):2N"));
  grid.appendChild(kpiRow("ss-block",    "block width (2N)"));
  grid.appendChild(kpiRow("ss-wins",     "windows / block (N-1)"));
  grid.appendChild(kpiRow("ss-prune",    "prune fraction"));
  grid.appendChild(kpiRow("ss-blocks",   "blocks packed"));
  grid.appendChild(kpiRow("ss-slrecon",  "RECON \u2014 slidesparse error (EXACT)"));
  grid.appendChild(kpiRow("ss-strecon",  "RECON \u2014 strict-2:4 error (baseline)"));
  grid.appendChild(kpiRow("ss-lossless", "lossless reconstruction"));
  grid.appendChild(kpiRow("ss-spstrict", "THROUGHPUT \u2014 strict-2:4 speedup"));
  grid.appendChild(kpiRow("ss-spslide",  "THROUGHPUT \u2014 slidesparse speedup"));
  grid.appendChild(kpiRow("ss-ceiling",  "ceiling N/(N-1) \u2014 MODELED proxy"));
  grid.appendChild(kpiRow("ss-gap",      "gap to ceiling"));
  grid.appendChild(kpiRow("ss-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "SlideSparse: Fast and Flexible (2N-2):2N Structured Sparsity \u2014 Shao, Hao, Song, Xia, Zhang, Huang, Wu, Xu, Xu, Dong, Chi, Zou, Wei (Furu Wei group) arXiv:2603.05232. MODELED \u00b7 not claimed-as \u00b7 counted-MAC proxy, not a GPU/tensor-core run.";
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
  pd.id = "ss-plain";
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
  const pat   = S.pattern    != null ? S.pattern : "loading\u2026";
  const wins  = S.winsPerBlock != null ? String(S.winsPerBlock) : "loading\u2026";
  const spd   = S.spSlide    != null ? S.spSlide.toFixed(2) + "\u00d7" : "loading\u2026";
  const ceil  = S.ceiling    != null ? S.ceiling.toFixed(2) + "\u00d7" : "loading\u2026";
  const strErr = S.strictRecon != null ? S.strictRecon.toFixed(3) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Modern AI chips have a special fast path that only works if you delete " +
    "exactly half of the numbers in a very rigid on/off pattern (\u201c2:4\u201d). Deleting half is often too " +
    "aggressive and hurts the model, so people use gentler patterns like <b>" + pat + "</b> (deleting " +
    "only a quarter) \u2014 but then the fast path won\u2019t take them, and the chip falls back to the slow " +
    "route. <b>SlideSparse</b> is a clever re-packing trick: it slices each gentle-sparsity block into " +
    "<b>" + wins + "</b> small overlapping windows that each DO obey the rigid 2:4 rule, and those windows " +
    "add back up to the original block <b>with zero error</b> \u2014 so you keep the accuracy of gentle " +
    "pruning AND regain the hardware fast path. Here the fast path reaches about <b>" + spd + "</b> speed " +
    "(its theoretical ceiling is <b>" + ceil + "</b>), while forcing the rigid 2:4 pattern instead would " +
    "corrupt the weights (reconstruction error \u2248 <b>" + strErr + "</b>). <b>Important honesty note:</b> " +
    "this is a <b>MODELED</b> toy on a small synthetic matrix running on an ordinary CPU \u2014 there is " +
    "<b>NO GPU, NO Sparse Tensor Core, NO CUDA, NO vLLM</b>; \u201cspeed\u201d here is a counted " +
    "multiply-accumulate proxy, not a hardware measurement. It does NOT reproduce SlideSparse\u2019s " +
    "reported 1.33\u00d7 speedup on Qwen2.5-7B or its real GPU results. This is a <b>new axis</b> \u2014 " +
    "structured-sparse layout/packing \u2014 separate from the ternary bit-precision and analog in-memory " +
    "compute organs.";
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
  _set("ss-pattern",  t || (S.pattern != null ? S.pattern : "\u2014"));
  _set("ss-block",    t || (S.blockWidth != null ? String(S.blockWidth) : "\u2014"));
  _set("ss-wins",     t || (S.winsPerBlock != null ? String(S.winsPerBlock) : "\u2014"));
  _set("ss-prune",    t || (S.pruneFrac != null ? (S.pruneFrac * 100).toFixed(1) + "%" : "\u2014"));
  _set("ss-blocks",   t || (S.blocksTotal != null ? S.blocksTotal.toLocaleString() : "\u2014"));
  _set("ss-slrecon",  t || (S.slideRecon != null ? S.slideRecon.toFixed(6) : "\u2014"));
  _set("ss-strecon",  t || fx(S.strictRecon, 6));
  _set("ss-lossless", t || (S.lossless != null ? (S.lossless ? "YES (zero error)" : "no") : "\u2014"));
  _set("ss-spstrict", t || (S.spStrict != null ? S.spStrict.toFixed(3) + "\u00d7" : "\u2014"));
  _set("ss-spslide",  t || (S.spSlide != null ? S.spSlide.toFixed(3) + "\u00d7" : "\u2014"));
  _set("ss-ceiling",  t || (S.ceiling != null ? S.ceiling.toFixed(3) + "\u00d7" : "\u2014"));
  _set("ss-gap",      t || (S.ceilingGap != null ? S.ceilingGap.toFixed(6) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("ss-label", t || (S.label || "MODELED"));
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
  _floor = null; _blockCell = []; _winCell = []; _winFrame = [];
  _barDense = _barStrict = _barSlide = _ceilLine = _liftMark = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.N = S.blockWidth = S.winsPerBlock = S.pattern = S.pruneFrac = null;
  S.rows = S.cols = S.blocksTotal = S.mode = null;
  S.reconErr = S.lossless = S.slideRecon = S.strictRecon = null;
  S.denseMacs = S.strictMacs = S.slideMacs = null;
  S.spDense = S.spStrict = S.spSlide = S.ceiling = S.ceilingGap = null;
  S.liftPerm = S.winMasks = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
