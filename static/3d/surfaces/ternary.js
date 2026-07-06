// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ternary.js — NATIVE 1.58-BIT TERNARY-WEIGHT LM organ for the
// holographic frontier ring (BitNet b1.58 BitLinear ternarization + multiply-
// free integer arithmetic, Microsoft Research-style). Renders a synthetic
// weight matrix as a 3D lattice of ternary cells: weights that ternarize to +1
// glow proof-teal (add), -1 glow lattice-blue (subtract), and 0 fade to grey
// (skip / structured sparsity). A HUD shows the three MEASURED metrics from the
// live snapshot at /api/killinchu/v1/ternary/quantize:
//   (1) COMPRESSION (bits/weight + x-shrink), (2) FIDELITY (the MEASURED,
//   non-zero rel_l2 / cosine error — reported, NOT hidden), (3) ARITHMETIC
//   PROFILE (float multiplies eliminated). Honesty label "MODELED" is read
//   VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors kvcache.js / aimc.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   rows, cols, batch, act_bits, beta, sparsity, ternary_counts{neg,zero,pos},
//   bits_per_weight_ternary, compression_vs_fp16, compression_vs_fp32,
//   rel_l2_error, cosine_error, float_muls_full, float_muls_ternary,
//   muls_eliminated, muls_eliminated_frac, int_ops_ternary
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   BitNet b1.58 2B4T Technical Report (mechanism simulated here):
//     Ma, Wang, Huang, Zhang, Hu, Song, Xia, Wei et al. (Microsoft Research)
//     arXiv:2504.12285  https://arxiv.org/abs/2504.12285
//   Official open weights: https://huggingface.co/microsoft/bitnet-b1.58-2B-4T
//   Official inference stack: https://github.com/microsoft/BitNet
//   Genealogy "The Era of 1-bit LLMs": arXiv:2402.17764
//     https://arxiv.org/abs/2402.17764
//
// HONESTY LABELS: MODELED (deterministic reproduction of the BitNet b1.58
//   ternary-quantization + integer-arithmetic MECHANISM on a toy synthetic
//   matrix; NOT the trained model; error is MEASURED and displayed;
//   NEVER-CLAIMED-AS a production inference engine). Read verbatim from JSON;
//   never upgraded here.
// COLOURS: proof-teal 0x3af4c8 (+1 -> add / HUD accent), lattice-blue 0x5b8dee
//   (-1 -> subtract), violet-blue 0x8a6bff (rescale/β accent), greys (0 -> skip /
//   degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "ternary";
const TITLE = "Native 1.58-bit Ternary-Weight LM · BitNet b1.58 (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
// This keeps the ternary organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/ternary/quantize?seed=42&rows=32&cols=32&batch=16&act_bits=8";

// data-viz hues — purple BANNED
const C_POS      = 0x3af4c8;  // proof-teal (+1 weight -> add)
const C_NEG      = 0x5b8dee;  // lattice-blue (-1 weight -> subtract)
const C_RESCALE  = 0x8a6bff;  // violet-blue (β rescale / accent marker)
const C_ZERO     = 0x5a6570;  // grey (0 weight -> skip / structured sparsity)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// lattice layout geometry
const CELL_GAP   = 0.44;   // world-units between weight cells
const MAX_SIDE   = 24;     // cap on cells rendered per axis (perf): MAX_SIDE^2 max
const CELL_Y     = 0.4;    // resting height of a weight cell

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor    = null;
let _cellMesh = [];                  // Array<THREE.Mesh> — flattened lattice cells
let _marker   = null;                // THREE.Mesh — β-rescale HUD marker

// live state
const S = {
  label:            null,
  rows:             null,
  cols:             null,
  batch:            null,
  actBits:          null,   // act_bits
  beta:             null,
  sparsity:         null,
  tcNeg:            null,   // ternary_counts.neg
  tcZero:           null,   // ternary_counts.zero
  tcPos:            null,   // ternary_counts.pos
  bitsPerWeight:    null,   // bits_per_weight_ternary
  compVsFp16:       null,   // compression_vs_fp16
  compVsFp32:       null,   // compression_vs_fp32
  relL2Error:       null,   // rel_l2_error (MEASURED)
  cosineError:      null,   // cosine_error (MEASURED)
  floatMulsFull:    null,   // float_muls_full
  floatMulsTernary: null,   // float_muls_ternary
  mulsEliminated:   null,   // muls_eliminated
  mulsElimFrac:     null,   // muls_eliminated_frac
  intOps:           null,   // int_ops_ternary
  state:            "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 8, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(5, 1, 5); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLattice();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onTernary, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed MAX_SIDE x MAX_SIDE lattice of weight-cell meshes. We
// toggle visibility / color / height in-place as live data arrives (no per-poll
// geometry churn). Each cell = one ternary weight; we colour by a deterministic
// sign pattern derived from live ternary_counts (client never invents weights it
// cannot see — it colours proportionally to the reported neg/zero/pos mix).
function _buildLattice() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(0.26, 0.26, 0.26);
  for (let r = 0; r < MAX_SIDE; r++) {
    for (let c = 0; c < MAX_SIDE; c++) {
      const mesh = new THREE.Mesh(
        cellGeo,
        new THREE.MeshStandardMaterial({ color: C_ZERO, emissive: C_ZERO, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
      );
      mesh.position.set(c * CELL_GAP, CELL_Y, r * CELL_GAP);
      mesh.visible = false;
      _group.add(mesh);
      _cellMesh.push(mesh);
    }
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.3, 1),
    new THREE.MeshStandardMaterial({ color: C_RESCALE, emissive: C_RESCALE, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(-1.2, 1.4, -1.2);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onTernary(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label            = String(lbl).toUpperCase();

  S.rows             = typeof src.rows                    === "number" ? src.rows                    : null;
  S.cols             = typeof src.cols                    === "number" ? src.cols                    : null;
  S.batch            = typeof src.batch                   === "number" ? src.batch                   : null;
  S.actBits          = typeof src.act_bits                === "number" ? src.act_bits                : null;
  S.beta             = typeof src.beta                    === "number" ? src.beta                    : null;
  S.sparsity         = typeof src.sparsity                === "number" ? src.sparsity                : null;
  S.bitsPerWeight    = typeof src.bits_per_weight_ternary === "number" ? src.bits_per_weight_ternary : null;
  S.compVsFp16       = typeof src.compression_vs_fp16     === "number" ? src.compression_vs_fp16     : null;
  S.compVsFp32       = typeof src.compression_vs_fp32     === "number" ? src.compression_vs_fp32     : null;
  S.relL2Error       = typeof src.rel_l2_error            === "number" ? src.rel_l2_error            : null;
  S.cosineError      = typeof src.cosine_error            === "number" ? src.cosine_error            : null;
  S.floatMulsFull    = typeof src.float_muls_full         === "number" ? src.float_muls_full         : null;
  S.floatMulsTernary = typeof src.float_muls_ternary      === "number" ? src.float_muls_ternary      : null;
  S.mulsEliminated   = typeof src.muls_eliminated         === "number" ? src.muls_eliminated         : null;
  S.mulsElimFrac     = typeof src.muls_eliminated_frac    === "number" ? src.muls_eliminated_frac    : null;
  S.intOps           = typeof src.int_ops_ternary         === "number" ? src.int_ops_ternary         : null;

  if (src.ternary_counts && typeof src.ternary_counts === "object") {
    S.tcNeg  = typeof src.ternary_counts.neg  === "number" ? src.ternary_counts.neg  : null;
    S.tcZero = typeof src.ternary_counts.zero === "number" ? src.ternary_counts.zero : null;
    S.tcPos  = typeof src.ternary_counts.pos  === "number" ? src.ternary_counts.pos  : null;
  }

  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — colours the lattice from the live ternary mix
// =============================================================================
// Deterministic per-cell PRNG (LCG, mirrors the module's family) so the lattice
// pattern is stable across polls and never fabricated beyond the reported mix.
function _cellSign(idx, pNeg, pZero) {
  let s = ((idx + 1) * 2654435761) >>> 0;
  s = (1664525 * s + 1013904223) >>> 0;
  const u = s / 4294967295;
  if (u < pZero) return 0;
  if (u < pZero + pNeg) return -1;
  return 1;
}

function _updateLattice() {
  const live = S.state === "live";
  const rows = live && S.rows ? Math.min(S.rows, MAX_SIDE) : 0;
  const cols = live && S.cols ? Math.min(S.cols, MAX_SIDE) : 0;

  const total = (S.tcNeg || 0) + (S.tcZero || 0) + (S.tcPos || 0);
  const pNeg  = total > 0 ? (S.tcNeg  || 0) / total : 0.33;
  const pZero = total > 0 ? (S.tcZero || 0) / total : 0.34;

  for (let r = 0; r < MAX_SIDE; r++) {
    for (let c = 0; c < MAX_SIDE; c++) {
      const mesh = _cellMesh[r * MAX_SIDE + c];
      if (!live || r >= rows || c >= cols) {
        mesh.visible = false;
        continue;
      }
      mesh.visible = true;
      const sign = _cellSign(r * MAX_SIDE + c, pNeg, pZero);
      let color;
      if (sign === 1)      color = C_POS;     // +1 -> add     -> proof-teal
      else if (sign === -1) color = C_NEG;    // -1 -> subtract -> lattice-blue
      else                 color = C_ZERO;    //  0 -> skip     -> grey
      mesh.material.color.setHex(color);
      mesh.material.emissive.setHex(color);
      mesh.material.emissiveIntensity = sign === 0 ? 0.12 : 0.55;
      mesh.material.opacity = sign === 0 ? 0.3 : 0.95;
      mesh.position.y = sign === 0 ? CELL_Y - 0.28 : CELL_Y;  // zeros sink (skipped)
    }
  }

  if (_marker) {
    if (live) {
      _marker.material.color.setHex(C_RESCALE);
      _marker.material.emissive.setHex(C_RESCALE);
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
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.14;
  if (_marker) {
    _marker.rotation.y += 0.025;
    _marker.rotation.x += 0.012;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _marker.scale.setScalar(pulse);
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
    'Every weight is constrained to a ternary code <b>{\u22121, 0, +1}</b> (~1.58 bits/weight) via ' +
    '<b>BitLinear</b>: scale \u03b2 = mean(|W|), then W<sub>t</sub> = round-clip(W/\u03b2). Because weights are ' +
    'ternary, the float matmul collapses into integer <b>add</b> (+1) / <b>subtract</b> (\u22121) / ' +
    '<b>skip</b> (0) \u2014 no per-weight multiply. HUD reports three MEASURED metrics: compression, ' +
    'fidelity error (shown, NOT hidden), and multiplies eliminated. Honesty label <b>MODELED</b> ' +
    '(deterministic mechanism reproduction on a toy matrix; NOT the trained BitNet model). 0 runtime CDN.';
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
  nm.textContent = "native 1.58-bit ternary-weight lm";
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

  grid.appendChild(kpiRow("tn-dims",     "matrix (rows \u00d7 cols)"));
  grid.appendChild(kpiRow("tn-actbits",  "activation bit-width (absmax)"));
  grid.appendChild(kpiRow("tn-beta",     "\u03b2 = mean(|W|) (absmean scale)"));
  grid.appendChild(kpiRow("tn-mix",      "ternary mix (\u22121 / 0 / +1)"));
  grid.appendChild(kpiRow("tn-sparsity", "sparsity (weights \u2192 0, skipped)"));
  grid.appendChild(kpiRow("tn-bpw",      "bits/weight (ternary) \u2014 MODELED"));
  grid.appendChild(kpiRow("tn-comp16",   "COMPRESSION vs fp16"));
  grid.appendChild(kpiRow("tn-comp32",   "COMPRESSION vs fp32"));
  grid.appendChild(kpiRow("tn-rell2",    "FIDELITY \u2014 rel L2 error (MEASURED)"));
  grid.appendChild(kpiRow("tn-cos",      "FIDELITY \u2014 cosine error (MEASURED)"));
  grid.appendChild(kpiRow("tn-muls",     "float-muls ELIMINATED"));
  grid.appendChild(kpiRow("tn-mulsfrac", "multiply-free fraction"));
  grid.appendChild(kpiRow("tn-intops",   "integer add/sub ops"));
  grid.appendChild(kpiRow("tn-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "BitNet b1.58 \u2014 Ma, Wang, Huang, Zhang, Hu, Song, Xia, Wei et al. (Microsoft Research) arXiv:2504.12285 \u00b7 genealogy arXiv:2402.17764. MODELED \u00b7 not claimed-as.";
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
  pd.id = "tn-plain";
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
  const comp   = S.compVsFp16   != null ? S.compVsFp16.toFixed(1) + "\u00d7"        : "loading\u2026";
  const relPct = S.relL2Error   != null ? (S.relL2Error * 100).toFixed(1) + "%"     : "loading\u2026";
  const mulPct = S.mulsElimFrac != null ? (S.mulsElimFrac * 100).toFixed(1) + "%"   : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Ordinary language models store each number (\u201cweight\u201d) using 16 or 32 " +
    "bits and multiply by it billions of times. This approach instead snaps every weight to just three " +
    "values \u2014 minus one, zero, or plus one \u2014 which needs only about 1.58 bits each. That shrinks storage " +
    "by roughly <b>" + comp + "</b>, and the big multiplications turn into simple add / subtract / skip \u2014 here " +
    "<b>" + mulPct + "</b> of the multiplies disappear. The catch, shown honestly, is a <b>MEASURED</b> " +
    "approximation error of about <b>" + relPct + "</b> on this toy matrix \u2014 we display it rather than hide it. " +
    "This view is a <b>MODELED</b> deterministic reproduction of the ternary-quantization and multiply-free " +
    "arithmetic MECHANISM on a small synthetic matrix, NOT the trained BitNet model. It does not reproduce " +
    "downstream accuracy, the 2B-parameter / 4T-token training, or the paper's energy figures. \u201cMatches " +
    "full precision\u201d is <b>Microsoft's claim</b> about their trained model \u2014 the estate does not independently " +
    "verify it.";
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
  _set("tn-dims",     t || ((S.rows != null && S.cols != null) ? (S.rows + " \u00d7 " + S.cols) : "\u2014"));
  _set("tn-actbits",  t || (S.actBits != null ? (S.actBits + "-bit") : "\u2014"));
  _set("tn-beta",     t || fx(S.beta, 4));
  _set("tn-mix",      t || ((S.tcNeg != null) ? (S.tcNeg + " / " + S.tcZero + " / " + S.tcPos) : "\u2014"));
  _set("tn-sparsity", t || pct(S.sparsity, 2));
  _set("tn-bpw",      t || fx(S.bitsPerWeight, 4));
  _set("tn-comp16",   t || (S.compVsFp16 != null ? S.compVsFp16.toFixed(2) + "\u00d7" : "\u2014"));
  _set("tn-comp32",   t || (S.compVsFp32 != null ? S.compVsFp32.toFixed(2) + "\u00d7" : "\u2014"));
  _set("tn-rell2",    t || pct(S.relL2Error, 2));
  _set("tn-cos",      t || pct(S.cosineError, 2));
  _set("tn-muls",     t || ((S.mulsEliminated != null && S.floatMulsFull != null) ? (S.mulsEliminated + " / " + S.floatMulsFull) : "\u2014"));
  _set("tn-mulsfrac", t || pct(S.mulsElimFrac, 2));
  _set("tn-intops",   t || (S.intOps != null ? String(S.intOps) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("tn-label", t || (S.label || "MODELED"));
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
  _floor = null; _cellMesh = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.rows = S.cols = S.batch = S.actBits = S.beta = S.sparsity = null;
  S.tcNeg = S.tcZero = S.tcPos = S.bitsPerWeight = null;
  S.compVsFp16 = S.compVsFp32 = S.relL2Error = S.cosineError = null;
  S.floatMulsFull = S.floatMulsTernary = S.mulsEliminated = S.mulsElimFrac = S.intOps = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
