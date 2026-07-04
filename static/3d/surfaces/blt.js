// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/blt.js — BYTE LATENT TRANSFORMER ENTROPY-PATCHING organ for the
// holographic frontier ring (Meta FAIR tokenizer-free dynamic byte-patching
// idea). Renders the input byte stream as a 3D ribbon: entropy height per
// byte (lattice-blue), patch boundaries drawn as proof-teal cut-planes where
// entropy spikes, and low-entropy runs grouped visually into big grey/dim
// patches. A HUD shows num_patches + compute_savings_ratio. Honesty label
// "MODELED" is read VERBATIM from the JSON and displayed as-is; it is never
// upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   text_len, threshold, num_patches, avg_patch_len, patch_boundaries[],
//   entropy_series[], compute_savings_ratio
//
// LEADER ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Byte Latent Transformer (entropy-patching idea rendered here):
//     Pagnoni, Pasunuru, Rodriguez et al. 2024, Meta FAIR
//     arXiv:2412.09871 — https://arxiv.org/abs/2412.09871
//   Reference implementation (reference only):
//     github.com/facebookresearch/blt
//     https://github.com/facebookresearch/blt
//
// HONESTY LABELS: MODELED (deterministic order-2 Markov byte-entropy
//   patching simulation of the BLT dynamic-patching idea; NOT the trained
//   BLT entropy model; NEVER-CLAIMED-AS Meta FAIR BLT). Read verbatim from
//   JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (byte ribbon / entropy height), proof-teal
//   0x3af4c8 (patch-boundary cut-planes / HUD accent), greys (low-entropy
//   grouped runs / degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "blt";
const TITLE = "Byte Latent Transformer · Entropy-Patching (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the BLT organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/blt/entropy-patch?seed=42&threshold=2.5";

// data-viz hues — purple BANNED
const C_RIBBON  = 0x5b8dee;  // lattice-blue (byte ribbon / entropy height)
const C_CUT     = 0x3af4c8;  // proof-teal (patch-boundary cut-plane / HUD accent)
const C_PATCH   = 0x5a6570;  // grey (low-entropy grouped-patch fill)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// ribbon layout geometry
const SEG_LEN     = 0.16;  // world-units per byte along X (ribbon axis)
const MAX_SEGS    = 512;   // cap on rendered byte segments (perf; matches endpoint sample cap)
const HEIGHT_SCALE = 0.55; // world-units per bit of entropy (Y)
const MAX_CUTS    = 96;    // cap on rendered patch-boundary cut-planes (perf)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _spine      = null;               // THREE.Line — ribbon baseline axis
let _ribbon     = null;               // THREE.Line — entropy-height ribbon polyline
let _segMesh    = [];                 // Array<THREE.Mesh> — per-sample entropy pillars
let _cutPlanes  = [];                 // Array<THREE.Mesh> — patch-boundary cut-planes
let _marker     = null;               // THREE.Mesh — HUD "compute savings" pulsing marker

// live state
const S = {
  label:        null,
  textLen:      null,   // text_len
  threshold:    null,   // threshold
  numPatches:   null,   // num_patches
  avgPatchLen:  null,   // avg_patch_len
  boundaries:   null,   // patch_boundaries[]
  entropySeries: null,  // entropy_series[] -> [byte_idx, bits]
  savingsRatio: null,   // compute_savings_ratio
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(6, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRibbon();
  _buildCutPlanes();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onBlt, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed set of ribbon-segment pillars (entropy height per
// sampled byte) + a baseline spine. We toggle visibility/height/color
// in-place as live data arrives (no per-poll geometry churn).
function _buildRibbon() {
  const THREE = _THREE;

  // baseline spine: a straight line along X marking the byte-stream axis
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(SEG_LEN * (MAX_SEGS - 1) + 1, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_RIBBON, transparent: true, opacity: 0.35 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  // entropy-height ribbon: a polyline whose Y tracks entropy bits per byte
  {
    const pts = [];
    for (let i = 0; i < MAX_SEGS; i++) pts.push(new THREE.Vector3(i * SEG_LEN, 0, 0));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_RIBBON, transparent: true, opacity: 0.0 });
    _ribbon = new THREE.Line(geo, mat);
    _group.add(_ribbon);
  }

  const segGeo = new THREE.BoxGeometry(SEG_LEN * 0.8, 1, 0.22);
  for (let i = 0; i < MAX_SEGS; i++) {
    const mesh = new THREE.Mesh(
      segGeo,
      new THREE.MeshStandardMaterial({ color: C_RIBBON, emissive: C_RIBBON, emissiveIntensity: 0.22, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(i * SEG_LEN, 0, 0);
    mesh.scale.y = 0.0001;
    mesh.visible = false;
    _group.add(mesh);
    _segMesh.push(mesh);
  }
}

// Pre-allocate cut-plane meshes marking patch boundaries (proof-teal, thin
// vertical panels perpendicular to the ribbon axis).
function _buildCutPlanes() {
  const THREE = _THREE;
  const planeGeo = new THREE.PlaneGeometry(0.03, 2.2);
  for (let i = 0; i < MAX_CUTS; i++) {
    const mesh = new THREE.Mesh(
      planeGeo,
      new THREE.MeshBasicMaterial({ color: C_CUT, transparent: true, opacity: 0.0, side: THREE.DoubleSide }),
    );
    mesh.position.set(0, 1.1, 0);
    mesh.visible = false;
    _group.add(mesh);
    _cutPlanes.push(mesh);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.26, 1),
    new THREE.MeshStandardMaterial({ color: C_CUT, emissive: C_CUT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -0.7, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onBlt(j) {
  // read honesty label VERBATIM — never upgrade
  S.label         = (j.label || "MODELED").toUpperCase();
  S.textLen       = typeof j.text_len              === "number" ? j.text_len              : null;
  S.threshold     = typeof j.threshold             === "number" ? j.threshold             : null;
  S.numPatches    = typeof j.num_patches           === "number" ? j.num_patches           : null;
  S.avgPatchLen   = typeof j.avg_patch_len         === "number" ? j.avg_patch_len         : null;
  S.boundaries    = Array.isArray(j.patch_boundaries) ? j.patch_boundaries : null;
  S.entropySeries = Array.isArray(j.entropy_series)   ? j.entropy_series   : null;
  S.savingsRatio  = typeof j.compute_savings_ratio === "number" ? j.compute_savings_ratio : null;

  _updateRibbon();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the ribbon + cut-planes from live data
// =============================================================================
function _updateRibbon() {
  const live = S.state === "live";
  const series = live && S.entropySeries && S.entropySeries.length ? S.entropySeries.slice(0, MAX_SEGS) : [];
  const boundarySet = new Set(live && S.boundaries ? S.boundaries : []);

  // ribbon polyline points
  const positions = _ribbon.geometry.attributes.position;
  let maxH = 0;
  for (let i = 0; i < series.length; i++) maxH = Math.max(maxH, series[i][1] || 0);
  maxH = Math.max(maxH, 0.001);

  for (let i = 0; i < MAX_SEGS; i++) {
    const mesh = _segMesh[i];
    if (!live || i >= series.length) {
      mesh.visible = false;
      positions.setXYZ(i, i * SEG_LEN, 0, 0);
      continue;
    }
    const [byteIdx, hBits] = series[i];
    const h = Math.max(0.02, (hBits / maxH) * 2.4 * HEIGHT_SCALE);
    const isBoundary = boundarySet.has(byteIdx);

    mesh.visible = true;
    mesh.scale.y = Math.max(h, 0.02);
    mesh.position.set(i * SEG_LEN, h / 2, 0);

    // low-entropy runs (below threshold) render dim grey "grouped patch";
    // high-entropy spikes (>= threshold, i.e. a cut point) render lattice-blue.
    const spiky = S.threshold != null ? hBits > S.threshold : hBits > 2.5;
    const color = spiky ? C_RIBBON : C_PATCH;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = spiky ? 0.4 : 0.12;
    mesh.material.opacity = spiky ? 0.95 : 0.55;

    positions.setXYZ(i, i * SEG_LEN, h, 0);
  }
  positions.needsUpdate = true;
  _ribbon.material.opacity = live ? 0.5 : 0.0;
  _ribbon.material.color.setHex(live ? C_RIBBON : C_DIM);

  // patch-boundary cut-planes: place at each boundary's ribbon-space x
  const boundaries = live && S.boundaries ? S.boundaries.slice(0, MAX_CUTS) : [];
  // map boundary byte-index -> nearest sample index x-position (approx via
  // proportion of text_len, since entropy_series may be a downsample)
  const textLen = S.textLen || 1;
  for (let i = 0; i < MAX_CUTS; i++) {
    const plane = _cutPlanes[i];
    if (!live || i >= boundaries.length) {
      plane.visible = false;
      continue;
    }
    const byteIdx = boundaries[i];
    const frac = Math.min(1, byteIdx / textLen);
    const x = frac * SEG_LEN * (MAX_SEGS - 1);
    plane.visible = true;
    plane.position.set(x, 1.1, 0);
    plane.material.opacity = 0.55;
    plane.material.color.setHex(C_CUT);
  }

  _spine.material.color.setHex(live ? C_RIBBON : C_DIM);
  _spine.material.opacity = live ? 0.35 : 0.15;

  if (_marker) {
    if (live && S.savingsRatio != null) {
      _marker.material.color.setHex(C_CUT);
      _marker.material.emissive.setHex(C_CUT);
      _marker.material.opacity = 0.85;
      // marker rides along X proportional to compute_savings_ratio (visual "compute win" cue)
      const x = Math.min(SEG_LEN * (MAX_SEGS - 1), Math.log2(1 + (S.savingsRatio || 1)) * 2.2);
      _marker.position.set(x, -0.7, 0);
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
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;
  if (_marker) {
    _marker.rotation.y += 0.024;
    _marker.rotation.x += 0.011;
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
    maxWidth: "min(94%,440px)",
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
    'Instead of fixed-vocabulary tokens, bytes are grouped into <b>variable-length patches</b> ' +
    'cut wherever the next-byte entropy <b>spikes</b> (high surprise). Predictable spans (grey, ' +
    'low entropy) collapse into one big patch; unpredictable spans (lattice-blue, high entropy) ' +
    'fragment into many small patches at proof-teal cut-planes. ' +
    'Honesty label <b>MODELED</b> (deterministic order-2 Markov byte-entropy simulation of the BLT ' +
    'entropy-patching idea; NOT the trained BLT entropy model). 0 runtime CDN.';
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
  nm.textContent = "byte latent transformer · entropy-patching";
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

  grid.appendChild(kpiRow("blt-textlen",  "text_len (bytes)"));
  grid.appendChild(kpiRow("blt-threshold","threshold (bits)"));
  grid.appendChild(kpiRow("blt-numpatch", "num_patches"));
  grid.appendChild(kpiRow("blt-avglen",   "avg_patch_len"));
  grid.appendChild(kpiRow("blt-savings",  "compute_savings_ratio \u2014 MODELED"));
  grid.appendChild(kpiRow("blt-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Pagnoni et al. (Meta FAIR) arXiv:2412.09871 (Byte Latent Transformer) \u00b7 github.com/facebookresearch/blt (reference). MODELED \u00b7 not claimed-as.";
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
  pd.id = "blt-plain";
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
  const patches = S.numPatches  != null ? String(S.numPatches) : "loading\u2026";
  const bytes   = S.textLen     != null ? String(S.textLen)    : "loading\u2026";
  const ratio   = S.savingsRatio != null ? S.savingsRatio.toFixed(2) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Normal language models chop text into a fixed dictionary of " +
    "\u201ctokens\u201d before reading it. This organ instead reads raw <b>bytes</b> and asks, at every " +
    "position, \u201chow surprising is the next byte, given what came right before it?\u201d When that " +
    "surprise (entropy) spikes, it starts a new <b>patch</b>; when the text is predictable, it keeps " +
    "stretching the same patch. Here, <b>" + bytes + " bytes</b> collapsed into just <b>" + patches +
    " patches</b> \u2014 a <b>" + ratio + " compute-savings ratio</b>, because predictable stretches " +
    "(like repeated letters) get bundled into one cheap patch instead of being processed byte-by-byte. " +
    "This is the core idea behind Meta FAIR's Byte Latent Transformer (BLT): spend compute where the " +
    "data is hard, save it where the data is easy. This view is a <b>MODELED</b> stand-in entropy " +
    "signal built from the text itself, not a run of the real trained BLT model.";
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
  _set("blt-textlen",   t || (S.textLen    != null ? String(S.textLen) : "\u2014"));
  _set("blt-threshold", t || fx(S.threshold, 2));
  _set("blt-numpatch",  t || (S.numPatches != null ? String(S.numPatches) : "\u2014"));
  _set("blt-avglen",    t || fx(S.avgPatchLen, 3));
  _set("blt-savings",   t || (S.savingsRatio != null ? S.savingsRatio.toFixed(3) + "\u00d7" : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("blt-label", t || (S.label || "MODELED"));
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
  _floor = null; _spine = null; _ribbon = null; _segMesh = []; _cutPlanes = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.textLen = S.threshold = S.numPatches = null;
  S.avgPatchLen = S.boundaries = S.entropySeries = S.savingsRatio = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
