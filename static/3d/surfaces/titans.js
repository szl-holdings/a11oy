// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/titans.js — TITANS NEURAL LONG-TERM MEMORY organ for the
// holographic frontier ring (Behrouz et al. 2025, Google — "learning to
// memorize at test time"). Renders a streaming token sequence flowing past a
// ring of fast-weight MEMORY SLOTS: each incoming token pulses with its
// SURPRISE signal, salient (high-surprise) tokens imprint strongly on their
// slot (proof-teal) and persist far longer than a fixed sliding window, while
// filler decays (grey) via the weight-decay forgetting gate. A HUD contrasts
// neural_recall vs window_recall from the live snapshot at
// /api/killinchu/v1/titans/recall. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / episodic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint, inside payload):
//   n_tokens, window, mem_dim, n_salient, neural_recall, window_recall,
//   recall_gain, mean_surprise, peak_surprise, forget_rate, momentum,
//   memory_trace[], salient_positions[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Titans: Learning to Memorize at Test Time (neural long-term memory
//   arithmetic simulated here):
//     Behrouz, Zhong & Mirrokni 2025, Google, arXiv:2501.00663
//     https://arxiv.org/abs/2501.00663
//   Google Research blog — Titans / MIRAS long-term memory (reference):
//     https://research.google/blog/titans-miras-helping-ai-have-long-term-memory/
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the surprise /
//   momentum / forgetting memory-update arithmetic; NOT the Titans model;
//   NEVER-CLAIMED-AS a trained memory module). Read verbatim from JSON; never
//   upgraded here. The endpoint nests its fields under `payload`, and the label
//   at the top level — this surface handles the label at top-level OR inside
//   payload.label defensively.
// COLOURS: lattice-blue 0x5b8dee (streaming tokens / spine), violet-blue
//   0x8a6bff (memory-slot ring / momentum), proof-teal 0x3af4c8 (salient
//   imprint / HUD accent), greys (forgotten / degraded state). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "titans";
const TITLE = "Titans · Neural Long-Term Memory (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the titans organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/titans/recall?seed=42&n_tokens=512&window=64&mem_dim=32";

// data-viz hues — purple BANNED
const C_STREAM  = 0x5b8dee;  // lattice-blue (streaming filler token / spine)
const C_SLOT    = 0x8a6bff;  // violet-blue (memory-slot ring / momentum term)
const C_SALIENT = 0x3af4c8;  // proof-teal (salient imprint / HUD accent)
const C_FORGET  = 0x5a6570;  // grey (forgotten / low-activation slot)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// layout geometry
const RING_R      = 5.0;    // radius of the memory-slot ring
const MAX_SLOTS   = 48;     // cap on mem_dim slots rendered (perf)
const STREAM_LEN  = 14.0;   // world-units the token stream spans along X
const MAX_STREAM  = 96;     // cap on streamed token markers rendered (== trace cap)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _ring       = null;               // THREE.LineLoop — memory-slot ring
let _slotMesh   = [];                 // Array<THREE.Mesh> — memory slots around the ring
let _streamMesh = [];                 // Array<THREE.Mesh> — streamed token markers along X
let _core       = null;               // THREE.Mesh — central "memory energy" core

// live state
const S = {
  label:        null,
  nTokens:      null,   // n_tokens
  window:       null,   // window
  memDim:       null,   // mem_dim
  nSalient:     null,   // n_salient
  neuralRecall: null,   // neural_recall
  windowRecall: null,   // window_recall
  recallGain:   null,   // recall_gain
  meanSurprise: null,   // mean_surprise
  peakSurprise: null,   // peak_surprise
  forgetRate:   null,   // forget_rate
  momentum:     null,   // momentum
  trace:        null,   // memory_trace[]
  salientPos:   null,   // salient_positions[]
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
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRing();
  _buildStream();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onTitans, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Ring of memory slots (fast-weight vector M). Pre-allocated at MAX_SLOTS; we
// toggle visibility / colour / scale in-place as live data arrives.
function _buildRing() {
  const THREE = _THREE;

  // ring outline
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * RING_R, 0, Math.sin(a) * RING_R));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_SLOT, transparent: true, opacity: 0.4 });
    _ring = new THREE.LineLoop(geo, mat);
    _group.add(_ring);
  }

  const slotGeo = new THREE.OctahedronGeometry(0.24, 0);
  for (let i = 0; i < MAX_SLOTS; i++) {
    const a = (i / MAX_SLOTS) * Math.PI * 2;
    const mesh = new THREE.Mesh(
      slotGeo,
      new THREE.MeshStandardMaterial({ color: C_SLOT, emissive: C_SLOT, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * RING_R, 0.6, Math.sin(a) * RING_R);
    mesh.visible = false;
    _group.add(mesh);
    _slotMesh.push(mesh);
  }
}

// A line of token markers streaming along X toward the ring (the input context
// window). Salient tokens glow proof-teal; filler is lattice-blue and fades.
function _buildStream() {
  const THREE = _THREE;
  const tokGeo = new THREE.SphereGeometry(0.14, 8, 8);
  for (let i = 0; i < MAX_STREAM; i++) {
    const x = -STREAM_LEN / 2 + (i / (MAX_STREAM - 1)) * STREAM_LEN;
    const mesh = new THREE.Mesh(
      tokGeo,
      new THREE.MeshStandardMaterial({ color: C_STREAM, emissive: C_STREAM, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(x, 3.4, 0);
    mesh.visible = false;
    _group.add(mesh);
    _streamMesh.push(mesh);
  }
}

function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.7, 1),
    new THREE.MeshStandardMaterial({ color: C_SALIENT, emissive: C_SALIENT, emissiveIntensity: 0.45, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, 0.6, 0);
  _group.add(_core);
}

// =============================================================================
// live data handler
// =============================================================================
function _onTitans(j) {
  // The endpoint nests its metrics under `payload`; the honesty label may sit
  // at the TOP LEVEL or (defensively) inside payload.label. Read it VERBATIM
  // from wherever it is — never upgrade.
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label        = String(rawLabel).toUpperCase();

  S.nTokens      = typeof p.n_tokens      === "number" ? p.n_tokens      : null;
  S.window       = typeof p.window        === "number" ? p.window        : null;
  S.memDim       = typeof p.mem_dim       === "number" ? p.mem_dim       : null;
  S.nSalient     = typeof p.n_salient     === "number" ? p.n_salient     : null;
  S.neuralRecall = typeof p.neural_recall === "number" ? p.neural_recall : null;
  S.windowRecall = typeof p.window_recall === "number" ? p.window_recall : null;
  S.recallGain   = typeof p.recall_gain   === "number" ? p.recall_gain   : null;
  S.meanSurprise = typeof p.mean_surprise === "number" ? p.mean_surprise : null;
  S.peakSurprise = typeof p.peak_surprise === "number" ? p.peak_surprise : null;
  S.forgetRate   = typeof p.forget_rate   === "number" ? p.forget_rate   : null;
  S.momentum     = typeof p.momentum      === "number" ? p.momentum      : null;
  S.trace        = Array.isArray(p.memory_trace)      ? p.memory_trace      : null;
  S.salientPos   = Array.isArray(p.salient_positions) ? p.salient_positions : null;

  _updateMemory();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the ring + stream from live data
// =============================================================================
function _updateMemory() {
  const live = S.state === "live";
  const slots = live && S.memDim ? Math.min(S.memDim, MAX_SLOTS) : 0;

  // ring outline degrades to grey when not live
  if (_ring) {
    _ring.material.color.setHex(live ? C_SLOT : C_DIM);
    _ring.material.opacity = live ? 0.4 : 0.12;
  }

  // memory slots: brightness scales with neural_recall (how much salient
  // content the memory has retained); a fraction glow proof-teal as "salient
  // imprints", the rest violet-blue, un-lit slots grey.
  const recall = live && S.neuralRecall != null ? S.neuralRecall : 0;
  const litCount = Math.round(slots * recall);
  for (let i = 0; i < MAX_SLOTS; i++) {
    const mesh = _slotMesh[i];
    if (i >= slots) { mesh.visible = false; continue; }
    mesh.visible = true;
    const imprinted = i < litCount;
    const color = imprinted ? C_SALIENT : (live ? C_SLOT : C_FORGET);
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = imprinted ? 0.6 : (live ? 0.25 : 0.08);
    mesh.material.opacity = imprinted ? 0.95 : (live ? 0.55 : 0.25);
    const sc = imprinted ? 1.25 : 0.85;
    mesh.scale.setScalar(sc);
  }

  // streamed token markers: colour by surprise / salience from the trace
  const trace = live && S.trace && S.trace.length ? S.trace.slice(0, MAX_STREAM) : [];
  const peak = live && S.peakSurprise ? S.peakSurprise : 1;
  for (let i = 0; i < MAX_STREAM; i++) {
    const mesh = _streamMesh[i];
    const t = i < trace.length ? trace[i] : null;
    if (!live || !t) { mesh.visible = false; continue; }
    mesh.visible = true;
    const salient = !!t.salient;
    const surprise = typeof t.surprise === "number" ? t.surprise : 0;
    const color = salient ? C_SALIENT : C_STREAM;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    // brighter with surprise; salient tokens spike
    const norm = peak > 0 ? Math.min(1, surprise / peak) : 0;
    mesh.material.emissiveIntensity = (salient ? 0.5 : 0.15) + 0.5 * norm;
    mesh.material.opacity = salient ? 0.95 : 0.35 + 0.4 * norm;
    const sc = salient ? 1.4 : 0.8 + 0.5 * norm;
    mesh.scale.setScalar(sc);
  }

  // central core: size/colour reflect the long-term-memory advantage (recall_gain)
  if (_core) {
    if (live && S.recallGain != null) {
      _core.material.color.setHex(C_SALIENT);
      _core.material.emissive.setHex(C_SALIENT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.8 + Math.max(0, S.recallGain) * 1.2);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.8);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.14;
  if (_ring) _ring.rotation.y += 0.0015;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.009;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.recallGain != null) ? (0.8 + Math.max(0, S.recallGain) * 1.2) : 0.8;
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
    'A neural memory that <b>learns to memorize at test time</b>: fast weights updated online by a ' +
    '<b>surprise</b> signal with <b>momentum</b>, regularised by <b>weight-decay forgetting</b>. ' +
    'Salient (high-surprise) tokens imprint and <b>persist far beyond a fixed window</b>, so recall ' +
    'stays high where a plain sliding window fails. ' +
    'Honesty label <b>MODELED</b> (deterministic surprise/momentum/forgetting simulation; NOT the Titans model). 0 runtime CDN.';
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
  nm.textContent = "titans neural long-term memory";
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

  grid.appendChild(kpiRow("ti-ntokens", "context length (n_tokens)"));
  grid.appendChild(kpiRow("ti-window",  "sliding window (fixed)"));
  grid.appendChild(kpiRow("ti-salient", "salient items planted"));
  grid.appendChild(kpiRow("ti-neural",  "neural_recall \u2014 MODELED"));
  grid.appendChild(kpiRow("ti-winrec",  "window_recall (baseline)"));
  grid.appendChild(kpiRow("ti-gain",    "recall_gain (LTM advantage)"));
  grid.appendChild(kpiRow("ti-surprise","mean / peak surprise"));
  grid.appendChild(kpiRow("ti-forget",  "forget_rate / momentum"));
  grid.appendChild(kpiRow("ti-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Behrouz et al. 2025 (Google) \u00b7 Titans: Learning to Memorize at Test Time \u00b7 arXiv:2501.00663 \u00b7 research.google/blog Titans/MIRAS. MODELED \u00b7 not claimed-as.";
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
  pd.id = "ti-plain";
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
  const nTok    = S.nTokens      != null ? String(S.nTokens) : "loading\u2026";
  const win     = S.window       != null ? String(S.window)  : "loading\u2026";
  const nRec    = S.neuralRecall != null ? (S.neuralRecall * 100).toFixed(0) + "%" : "loading\u2026";
  const wRec    = S.windowRecall != null ? (S.windowRecall * 100).toFixed(0) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Most AI models only \u201cremember\u201d the last few thousand words in front " +
    "of them (a fixed <b>window</b> \u2014 here just <b>" + win + "</b> tokens). Titans adds a small " +
    "<b>learning memory</b> that updates itself <i>while it reads</i>: whenever something " +
    "<b>surprising or important</b> shows up, it writes it down harder and holds onto it, while " +
    "boring filler slowly fades. So across a long stream of <b>" + nTok + "</b> tokens, this memory " +
    "still recalls about <b>" + nRec + "</b> of the important items \u2014 versus only <b>" + wRec + "</b> " +
    "for a plain fixed window that has long since scrolled them away. Plain: it learns what matters " +
    "and keeps it, instead of forgetting everything old. This view is a <b>MODELED</b> simulation of " +
    "that surprise-with-momentum-and-forgetting update rule, not a run of the real Titans model.";
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
  _set("ti-ntokens", t || (S.nTokens != null ? String(S.nTokens) : "\u2014"));
  _set("ti-window",  t || (S.window  != null ? String(S.window)  : "\u2014"));
  _set("ti-salient", t || (S.nSalient != null ? String(S.nSalient) : "\u2014"));
  _set("ti-neural",  t || pct(S.neuralRecall, 1));
  _set("ti-winrec",  t || pct(S.windowRecall, 1));
  _set("ti-gain",    t || (S.recallGain != null ? "+" + (S.recallGain * 100).toFixed(1) + "%" : "\u2014"));
  _set("ti-surprise", t || (S.meanSurprise != null || S.peakSurprise != null
        ? fx(S.meanSurprise, 3) + " / " + fx(S.peakSurprise, 3)
        : "\u2014"));
  _set("ti-forget",  t || (S.forgetRate != null || S.momentum != null
        ? fx(S.forgetRate, 3) + " / " + fx(S.momentum, 2)
        : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("ti-label", t || (S.label || "MODELED"));
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
  _floor = null; _ring = null; _slotMesh = []; _streamMesh = []; _core = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nTokens = S.window = S.memDim = S.nSalient = null;
  S.neuralRecall = S.windowRecall = S.recallGain = null;
  S.meanSurprise = S.peakSurprise = S.forgetRate = S.momentum = null;
  S.trace = S.salientPos = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
