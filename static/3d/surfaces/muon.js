// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/muon.js — MUON ORTHOGONALIZED-MOMENTUM OPTIMIZER organ for the
// holographic frontier ring (Muon = "MomentUm Orthogonalized by Newton–Schulz";
// Keller Jordan et al. / Moonshot AI). Renders the quintic Newton–Schulz
// orthogonalization of a synthetic momentum matrix as three live panels:
//   (1) SINGULAR-VALUE TRAJECTORY — one 3D line per singular value across the
//       Newton–Schulz iterations (x = iteration 0..ns, y = σ value), with the
//       Muon [0.68, 1.13] oscillation band drawn as two reference planes;
//   (2) BEFORE / AFTER HEATMAP — the raw normalized matrix G/||G||_F vs. the
//       orthogonalized output UVᵀ ≈ X_ns, as two grids of coloured cells;
//   (3) CONDITION-NUMBER BARS — κ = σ_max/σ_min raw vs. orthogonalized, honestly
//       showing spectral flattening.
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/muon/orthogonalize. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors ternary.js / kvcache.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   m, n, ns_steps, coeffs{a,b,c}, frob_norm_raw, aspect_scale, rank,
//   sv_spectrum[[...]], cond_raw, cond_ortho, cond_improvement,
//   band_lo, band_hi, frac_in_band, sv_min_final, sv_max_final,
//   matrix_raw[[...]], matrix_ortho[[...]]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   Muon: An optimizer for hidden layers in neural networks — Keller Jordan et al.
//     https://kellerjordan.github.io/posts/muon/
//   Muon is Scalable for LLM Training (Moonlight) — Moonshot AI arXiv:2502.16982
//     https://arxiv.org/abs/2502.16982
//   KellerJordan/Muon reference implementation: https://github.com/KellerJordan/Muon
//
// HONESTY LABELS: MODELED (deterministic reproduction of the Muon Newton–Schulz
//   ORTHOGONALIZATION mechanism on a toy synthetic momentum matrix; NOT a
//   trained model; trains nothing; the spectral flattening is MEASURED and
//   displayed; NEVER-CLAIMED-AS a production optimizer). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "muon";
const TITLE = "Muon Orthogonalized-Momentum Optimizer";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/muon/orthogonalize?seed=42&m=32&n=32&ns_steps=5";

// data-viz hues — purple BANNED
const C_SV       = 0x3af4c8;  // proof-teal  (singular-value trajectory lines)
const C_BAND     = 0x8a6bff;  // violet-blue ([0.68,1.13] band reference planes)
const C_RAW      = 0x5b8dee;  // lattice-blue (raw matrix heatmap / raw cond bar)
const C_ORTHO    = 0x3af4c8;  // proof-teal  (orthogonalized heatmap / ortho bar)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_ZERO     = 0x5a6570;  // grey (near-zero heatmap cell)
const C_GRID     = 0x1b3a44;  // floor / link colour

// layout geometry
const TRAJ_X0    = 0.0;    // trajectory panel origin x
const TRAJ_DX    = 1.5;    // world-units per Newton–Schulz iteration
const TRAJ_YSC   = 3.0;    // world-units per unit singular value
const HEAT_CELL  = 0.16;   // heatmap cell size
const HEAT_GAP   = 0.17;   // heatmap cell pitch
const HEAT_MAX   = 24;     // cap cells per axis rendered (perf)
const BAR_W      = 0.9;    // condition-number bar width

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _trajGroup  = null;   // THREE.Group — SV trajectory lines + band planes
let _heatRaw    = [];     // Array<THREE.Mesh> — before heatmap cells
let _heatOrtho  = [];     // Array<THREE.Mesh> — after heatmap cells
let _heatGroup  = null;
let _barRaw     = null;   // THREE.Mesh — raw condition-number bar
let _barOrtho   = null;   // THREE.Mesh — orthogonalized condition-number bar
let _barGroup   = null;

// live state
const S = {
  label:      null,
  m:          null,
  n:          null,
  nsSteps:    null,   // ns_steps
  coA:        null, coB: null, coC: null,   // coeffs
  frobRaw:    null,   // frob_norm_raw
  aspect:     null,   // aspect_scale
  rank:       null,
  svSpectrum: null,   // Array<Array<number>>
  condRaw:    null,   // cond_raw
  condOrtho:  null,   // cond_ortho
  condImp:    null,   // cond_improvement
  bandLo:     null,   // band_lo
  bandHi:     null,   // band_hi
  fracInBand: null,   // frac_in_band
  svMinFinal: null,   // sv_min_final
  svMaxFinal: null,   // sv_max_final
  matrixRaw:  null,   // Array<Array<number>>
  matrixOrtho:null,   // Array<Array<number>>
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 7, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(4, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildTrajectory();
  _buildHeatmaps();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onMuon, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

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

// SV trajectory panel: the band reference planes are pre-built here; the
// per-singular-value lines are rebuilt in-place whenever fresh data arrives
// (line count depends on live rank). Two translucent planes mark [0.68,1.13].
function _buildTrajectory() {
  const THREE = _THREE;
  _trajGroup = new THREE.Group();
  _trajGroup.position.set(TRAJ_X0, 0, -3.0);
  _group.add(_trajGroup);
  // band planes are added by _updateTrajectory once band bounds are known
}

// two grids of coloured cells (raw | orthogonalized). Pre-allocate a fixed
// HEAT_MAX x HEAT_MAX per side; toggle visibility/color in place (no churn).
function _buildHeatmaps() {
  const THREE = _THREE;
  _heatGroup = new THREE.Group();
  _heatGroup.position.set(0.0, 0.05, 3.2);
  _group.add(_heatGroup);
  const cellGeo = new THREE.PlaneGeometry(HEAT_CELL, HEAT_CELL);

  function makeGrid(offsetX, arr) {
    for (let r = 0; r < HEAT_MAX; r++) {
      for (let c = 0; c < HEAT_MAX; c++) {
        const mesh = new THREE.Mesh(
          cellGeo,
          new THREE.MeshBasicMaterial({ color: C_ZERO, transparent: true, opacity: 0.0, side: THREE.DoubleSide }),
        );
        mesh.rotation.x = -Math.PI / 2;
        mesh.position.set(offsetX + c * HEAT_GAP, 0.02, r * HEAT_GAP);
        mesh.visible = false;
        _heatGroup.add(mesh);
        arr.push(mesh);
      }
    }
  }
  makeGrid(0.0, _heatRaw);
  makeGrid(HEAT_MAX * HEAT_GAP + 0.8, _heatOrtho);
}

function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(-3.4, 0, 0.0);
  _group.add(_barGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  _barRaw = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_RAW, emissive: C_RAW, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barRaw.position.set(0, 0.5, 0);
  _barGroup.add(_barRaw);

  _barOrtho = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_ORTHO, emissive: C_ORTHO, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barOrtho.position.set(1.3, 0.5, 0);
  _barGroup.add(_barOrtho);
}

// =============================================================================
// live data handler
// =============================================================================
function _onMuon(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.m          = typeof src.m                === "number" ? src.m                : null;
  S.n          = typeof src.n                === "number" ? src.n                : null;
  S.nsSteps    = typeof src.ns_steps         === "number" ? src.ns_steps         : null;
  S.frobRaw    = typeof src.frob_norm_raw    === "number" ? src.frob_norm_raw    : null;
  S.aspect     = typeof src.aspect_scale     === "number" ? src.aspect_scale     : null;
  S.rank       = typeof src.rank             === "number" ? src.rank             : null;
  S.condRaw    = typeof src.cond_raw         === "number" ? src.cond_raw         : null;
  S.condOrtho  = typeof src.cond_ortho       === "number" ? src.cond_ortho       : null;
  S.condImp    = typeof src.cond_improvement === "number" ? src.cond_improvement : null;
  S.bandLo     = typeof src.band_lo          === "number" ? src.band_lo          : null;
  S.bandHi     = typeof src.band_hi          === "number" ? src.band_hi          : null;
  S.fracInBand = typeof src.frac_in_band     === "number" ? src.frac_in_band     : null;
  S.svMinFinal = typeof src.sv_min_final     === "number" ? src.sv_min_final     : null;
  S.svMaxFinal = typeof src.sv_max_final     === "number" ? src.sv_max_final     : null;

  if (src.coeffs && typeof src.coeffs === "object") {
    S.coA = typeof src.coeffs.a === "number" ? src.coeffs.a : null;
    S.coB = typeof src.coeffs.b === "number" ? src.coeffs.b : null;
    S.coC = typeof src.coeffs.c === "number" ? src.coeffs.c : null;
  }
  S.svSpectrum  = Array.isArray(src.sv_spectrum)  ? src.sv_spectrum  : null;
  S.matrixRaw   = Array.isArray(src.matrix_raw)   ? src.matrix_raw   : null;
  S.matrixOrtho = Array.isArray(src.matrix_ortho) ? src.matrix_ortho : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateTrajectory();
  _updateHeatmaps();
  _updateBars();
}

// Rebuild the SV trajectory lines + band planes from the live spectrum.
function _updateTrajectory() {
  const THREE = _THREE;
  if (!_trajGroup) return;
  const live = S.state === "live";

  // dispose previous trajectory children (lines + planes)
  for (let i = _trajGroup.children.length - 1; i >= 0; i--) {
    const o = _trajGroup.children[i];
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) {
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => { if (m.dispose) m.dispose(); });
    }
    _trajGroup.remove(o);
  }

  if (!live || !S.svSpectrum || !S.svSpectrum.length) return;

  const lo = (S.bandLo != null) ? S.bandLo : 0.68;
  const hi = (S.bandHi != null) ? S.bandHi : 1.13;
  const iters = S.svSpectrum.length;               // ns_steps + 1
  const width = (iters - 1) * TRAJ_DX;

  // two band reference planes at y = lo and y = hi (violet-blue, translucent)
  const planeGeo = new THREE.PlaneGeometry(width || TRAJ_DX, 5.0);
  [lo, hi].forEach((yv) => {
    const pm = new THREE.Mesh(
      planeGeo,
      new THREE.MeshBasicMaterial({ color: C_BAND, transparent: true, opacity: 0.10, side: THREE.DoubleSide }),
    );
    pm.rotation.x = -Math.PI / 2;
    pm.position.set(width / 2, yv * TRAJ_YSC, 2.5);
    _trajGroup.add(pm);
  });

  // one line per singular value: point (iter, σ_at_iter). Only draw a subset of
  // ranks if very large, to keep the panel legible & cheap.
  const rank = S.svSpectrum[0].length;
  const stride = rank > 32 ? Math.ceil(rank / 32) : 1;
  for (let s = 0; s < rank; s += stride) {
    const pts = [];
    for (let k = 0; k < iters; k++) {
      const sv = (S.svSpectrum[k] && typeof S.svSpectrum[k][s] === "number") ? S.svSpectrum[k][s] : 0.0;
      pts.push(new THREE.Vector3(k * TRAJ_DX, sv * TRAJ_YSC, 0));
    }
    const lg = new THREE.BufferGeometry().setFromPoints(pts);
    const lm = new THREE.LineBasicMaterial({ color: C_SV, transparent: true, opacity: 0.7 });
    _trajGroup.add(new THREE.Line(lg, lm));
  }
}

// colour a heatmap grid from a matrix: sign -> hue (raw=lattice-blue tint,
// ortho=proof-teal tint), |value| -> opacity. Near-zero -> grey.
function _paintHeat(arr, mat, baseColor) {
  const live = S.state === "live";
  const rows = (live && mat && mat.length) ? Math.min(mat.length, HEAT_MAX) : 0;
  const cols = (live && mat && mat[0]) ? Math.min(mat[0].length, HEAT_MAX) : 0;

  // find max-abs for normalization
  let amax = 0.0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = Math.abs(mat[r][c]);
      if (v > amax) amax = v;
    }
  }
  if (amax <= 0.0) amax = 1.0;

  for (let r = 0; r < HEAT_MAX; r++) {
    for (let c = 0; c < HEAT_MAX; c++) {
      const mesh = arr[r * HEAT_MAX + c];
      if (!live || r >= rows || c >= cols) { mesh.visible = false; continue; }
      mesh.visible = true;
      const v = mat[r][c];
      const mag = Math.min(1.0, Math.abs(v) / amax);
      const color = mag < 0.04 ? C_ZERO : baseColor;
      mesh.material.color.setHex(color);
      mesh.material.opacity = 0.18 + 0.75 * mag;
    }
  }
}

function _updateHeatmaps() {
  _paintHeat(_heatRaw,   S.matrixRaw,   C_RAW);
  _paintHeat(_heatOrtho, S.matrixOrtho, C_ORTHO);
}

// condition-number bars: height ∝ log10(κ) so the raw (large κ) and
// orthogonalized (κ≈1) bars are both legible.
function _updateBars() {
  const live = S.state === "live";
  function setBar(mesh, kappa, color) {
    if (!mesh) return;
    if (!live || kappa == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.05;
      mesh.position.y = 0.025;
      return;
    }
    const h = Math.max(0.08, Math.log10(Math.max(1.0, kappa)) + 0.15) * 2.2;
    mesh.scale.y = h;
    mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.4;
    mesh.material.opacity = 0.92;
  }
  setBar(_barRaw,   S.condRaw,   C_RAW);
  setBar(_barOrtho, S.condOrtho, C_ORTHO);
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
    'Muon (\u201cMomentUm Orthogonalized by Newton\u2013Schulz\u201d) replaces a momentum update matrix ' +
    'with the nearest <b>semi-orthogonal</b> matrix (UV\u1d40 from its SVD) via a hand-tuned <b>quintic ' +
    'Newton\u2013Schulz</b> recurrence X<sub>k+1</sub> = a\u00b7X + b\u00b7(XX\u1d40)X + c\u00b7(XX\u1d40)\u00b2X ' +
    '(a=3.4445, b=\u22124.7750, c=2.0315). This <b>flattens the singular-value spectrum</b> toward the ' +
    'non-convergent <b>[0.68, 1.13]</b> band so no direction dominates the step. Panels: singular-value ' +
    'trajectory, before/after matrix heatmap, condition-number bars (raw vs orthogonalized). Honesty label ' +
    '<b>MODELED</b> (deterministic mechanism reproduction on a toy matrix; trains nothing). 0 runtime CDN.';
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
  nm.textContent = "muon orthogonalized-momentum optimizer";
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

  grid.appendChild(kpiRow("mu-dims",   "momentum matrix (m \u00d7 n)"));
  grid.appendChild(kpiRow("mu-ns",     "Newton\u2013Schulz iterations"));
  grid.appendChild(kpiRow("mu-coeffs", "quintic coefficients (a / b / c)"));
  grid.appendChild(kpiRow("mu-rank",   "singular values tracked (rank)"));
  grid.appendChild(kpiRow("mu-condr",  "condition \u03ba \u2014 RAW"));
  grid.appendChild(kpiRow("mu-condo",  "condition \u03ba \u2014 ORTHOGONALIZED"));
  grid.appendChild(kpiRow("mu-condi",  "spectral-flattening factor"));
  grid.appendChild(kpiRow("mu-band",   "convergence band"));
  grid.appendChild(kpiRow("mu-frac",   "final \u03c3 inside band (MEASURED)"));
  grid.appendChild(kpiRow("mu-svrange","final \u03c3 range (min \u2192 max)"));
  grid.appendChild(kpiRow("mu-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Muon \u2014 Keller Jordan et al. (kellerjordan.github.io/posts/muon) \u00b7 Moonshot AI \u201cMuon is Scalable for LLM Training\u201d arXiv:2502.16982 \u00b7 github.com/KellerJordan/Muon. MODELED \u00b7 Newton\u2013Schulz demo, not a trained model.";
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
  pd.id = "mu-plain";
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
  const cr   = S.condRaw    != null ? S.condRaw.toFixed(1)    : "loading\u2026";
  const co   = S.condOrtho  != null ? S.condOrtho.toFixed(2)  : "loading\u2026";
  const imp  = S.condImp    != null ? S.condImp.toFixed(1) + "\u00d7" : "loading\u2026";
  const frac = S.fracInBand != null ? (S.fracInBand * 100).toFixed(0) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> When a model learns, each update is a grid of numbers (a \u201cmatrix\u201d). Some " +
    "directions in that grid can be far bigger than others, so the step lurches. Muon first <b>rebalances</b> " +
    "the update so every direction has roughly equal weight \u2014 like normalizing the volume across a mixing " +
    "board before pressing play. It does this not with an expensive exact calculation but with a fast, " +
    "GPU-friendly repeated formula (Newton\u2013Schulz) run about five times. Here the imbalance measure " +
    "(\u201ccondition number\u201d) drops from about <b>" + cr + "</b> to about <b>" + co + "</b> \u2014 a " +
    "<b>" + imp + "</b> flattening \u2014 and <b>" + frac + "</b> of the rebalanced values land in the target " +
    "<b>0.68\u20131.13</b> range the method aims for. This view is a <b>MODELED</b> deterministic reproduction " +
    "of that rebalancing MECHANISM on a small synthetic matrix \u2014 it <b>trains no model</b> and runs no GPU " +
    "kernel. The \u201c\u2248 2\u00d7 faster training vs. AdamW\u201d headline is a <b>claim about real training " +
    "runs</b> (Keller Jordan / Moonshot AI) that the estate does not independently verify.";
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
  _set("mu-dims",    t || ((S.m != null && S.n != null) ? (S.m + " \u00d7 " + S.n) : "\u2014"));
  _set("mu-ns",      t || (S.nsSteps != null ? String(S.nsSteps) : "\u2014"));
  _set("mu-coeffs",  t || ((S.coA != null) ? (fx(S.coA, 4) + " / " + fx(S.coB, 4) + " / " + fx(S.coC, 4)) : "\u2014"));
  _set("mu-rank",    t || (S.rank != null ? String(S.rank) : "\u2014"));
  _set("mu-condr",   t || fx(S.condRaw, 2));
  _set("mu-condo",   t || fx(S.condOrtho, 3));
  _set("mu-condi",   t || (S.condImp != null ? S.condImp.toFixed(1) + "\u00d7" : "\u2014"));
  _set("mu-band",    t || ((S.bandLo != null && S.bandHi != null) ? ("[" + S.bandLo + ", " + S.bandHi + "]") : "\u2014"));
  _set("mu-frac",    t || pct(S.fracInBand, 1));
  _set("mu-svrange", t || ((S.svMinFinal != null && S.svMaxFinal != null) ? (fx(S.svMinFinal, 3) + " \u2192 " + fx(S.svMaxFinal, 3)) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("mu-label",   t || (S.label || "MODELED"));
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
  _trajGroup = null;
  _heatRaw = []; _heatOrtho = []; _heatGroup = null;
  _barRaw = null; _barOrtho = null; _barGroup = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.m = S.n = S.nsSteps = null;
  S.coA = S.coB = S.coC = null;
  S.frobRaw = S.aspect = S.rank = null;
  S.svSpectrum = null;
  S.condRaw = S.condOrtho = S.condImp = null;
  S.bandLo = S.bandHi = S.fracInBand = S.svMinFinal = S.svMaxFinal = null;
  S.matrixRaw = S.matrixOrtho = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
