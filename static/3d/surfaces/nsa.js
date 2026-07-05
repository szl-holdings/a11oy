// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/nsa.js — NATIVE SPARSE ATTENTION (NSA) organ for the holographic
// frontier ring (DeepSeek-AI Yuan et al. 2025-style three-branch sparse
// attention). Renders a token sequence as a lattice-blue spine; the
// SLIDING-WINDOW branch lights the trailing window in lattice-blue, the
// TOP-K SELECTION branch lights its chosen blocks in proof-teal, and the
// COMPRESSION branch's pooled summary tokens float above the spine in
// violet-blue. A HUD shows the branch eval counts + the measured sparsity
// ratio vs the dense O(seq_len^2) reference and the dense-oracle recall
// parity check. Honesty label "MODELED" is read VERBATIM from the JSON and
// displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   config{seq_len,dim,block_size,topk,window,query_pos}, branches{compression,
//   selection,sliding_window}, gate_combined_score, gate_weights,
//   flops_accounting{this_query,whole_sequence_projection}, parity_check
//
// LEADER ADOPTED & CITED (clean-room reimplementation; NOT claimed as SZL's own):
//   Native Sparse Attention (DeepSeek-AI, Yuan et al. 2025):
//     https://arxiv.org/abs/2502.11089
//   Community discussion (reference only):
//     https://news.ycombinator.com/item?id=46181231
//
// HONESTY LABELS: MODELED (deterministic pure-Python reimplementation of the
//   NSA three-branch sparsity pattern over synthetic LCG-seeded data; NOT a
//   trained model, NOT the DeepSeek-AI reference kernel). Read verbatim from
//   JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (spine / sliding-window), violet-blue
//   0x8a6bff (compression summary tokens), proof-teal 0x3af4c8 (top-k
//   selection / HUD accent), greys (degraded / unselected). Purple BANNED.
// 0 RUNTIME CDN. Vendored three.js r170 via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "nsa";
const TITLE = "Native Sparse Attention · Compress + Select + Slide (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the nsa organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/nsa/simulate?seed=42&seq_len=256&dim=16&block_size=16&topk=4&window=16";

// data-viz hues — purple BANNED
const C_SPINE    = 0x5b8dee;  // lattice-blue (sequence spine / sliding-window tokens)
const C_COMPRESS = 0x8a6bff;  // violet-blue (compression summary tokens, floating above spine)
const C_SELECT   = 0x3af4c8;  // proof-teal (top-k selected block tokens / HUD accent)
const C_UNSEL    = 0x3a4552;  // grey (unselected / dense-only tokens)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// sequence lattice layout geometry
const MAX_TOKENS   = 256;  // cap on seq_len positions rendered along the spine
const SPINE_LEN    = 22;   // world-units the full spine spans along X
const SUMMARY_Y    = 1.6;  // height above spine for compression summary tokens
const WINDOW_Z     = 0.0;  // spine sits at z=0; selected blocks nudge +z, summaries -z visually via y

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor        = null;
let _spineLine    = null;                // THREE.Line — full sequence spine
let _tokenMesh    = [];                  // Array<THREE.Mesh> — one per rendered position (len MAX_TOKENS)
let _summaryMesh  = [];                  // Array<THREE.Mesh> — compression summary tokens
let _summaryLinks = [];                  // Array<THREE.Line> — link from spine to each summary
let _gateMarker   = null;                // THREE.Mesh — pulsing marker sized by gate_combined_score

// live state
const S = {
  label:        null,
  seqLen:       null,
  dim:          null,
  blockSize:    null,
  topk:         null,
  window:       null,
  queryPos:     null,
  windowPositions: null,   // branches.sliding_window.window_positions[]
  selectedBlocks: null,    // branches.selection.selected_block_indices[]
  nSummary:     null,      // branches.compression.n_summary_tokens
  gateScore:    null,      // gate_combined_score
  gateWeights:  null,      // gate_weights{}
  denseEvals:   null,      // flops_accounting.this_query.dense_evals
  nsaEvals:     null,      // flops_accounting.this_query.nsa_evals
  sparsityRatio: null,     // flops_accounting.this_query.sparsity_ratio
  recall:       null,      // parity_check.recall_vs_dense_oracle
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(SPINE_LEN * 0.5, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpine();
  _buildGateMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onNsa, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed lattice of token meshes along the spine (X axis) plus a
// fixed pool of summary-token meshes above it. Toggle visibility / color / y
// in-place as live data arrives (no per-poll geometry churn).
function _buildSpine() {
  const THREE = _THREE;

  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(SPINE_LEN, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_SPINE, transparent: true, opacity: 0.4 });
    _spineLine = new THREE.Line(geo, mat);
    _group.add(_spineLine);
  }

  const tokenGeo = new THREE.BoxGeometry(0.10, 0.10, 0.10);
  for (let i = 0; i < MAX_TOKENS; i++) {
    const x = (i / (MAX_TOKENS - 1)) * SPINE_LEN;
    const mesh = new THREE.Mesh(
      tokenGeo,
      new THREE.MeshStandardMaterial({ color: C_UNSEL, emissive: C_UNSEL, emissiveIntensity: 0.15, transparent: true, opacity: 0.25 }),
    );
    mesh.position.set(x, 0, 0);
    mesh.visible = false;
    _group.add(mesh);
    _tokenMesh.push(mesh);
  }

  // pre-allocate a modest pool of summary meshes (compression branch);
  // actual count comes from live data and is capped for perf.
  const MAX_SUMMARIES = 32;
  const summaryGeo = new THREE.OctahedronGeometry(0.22, 0);
  for (let i = 0; i < MAX_SUMMARIES; i++) {
    const mesh = new THREE.Mesh(
      summaryGeo,
      new THREE.MeshStandardMaterial({ color: C_COMPRESS, emissive: C_COMPRESS, emissiveIntensity: 0.35, transparent: true, opacity: 0.0 }),
    );
    mesh.visible = false;
    _group.add(mesh);
    _summaryMesh.push(mesh);

    const linkGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, SUMMARY_Y, 0)]);
    const linkMat = new THREE.LineBasicMaterial({ color: C_COMPRESS, transparent: true, opacity: 0.2 });
    const link = new THREE.Line(linkGeo, linkMat);
    link.visible = false;
    _group.add(link);
    _summaryLinks.push(link);
  }
}

function _buildGateMarker() {
  const THREE = _THREE;
  _gateMarker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.3, 1),
    new THREE.MeshStandardMaterial({ color: C_SELECT, emissive: C_SELECT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _gateMarker.position.set(SPINE_LEN * 0.5, -0.9, 0);
  _group.add(_gateMarker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onNsa(j) {
  const payload = j && j.payload ? j.payload : j;  // receipt wrapper or bare payload
  if (!payload) return;

  // read honesty label VERBATIM — never upgrade
  S.label = (payload.label || "MODELED").toUpperCase();

  const cfg = payload.config || {};
  S.seqLen    = typeof cfg.seq_len    === "number" ? cfg.seq_len    : null;
  S.dim       = typeof cfg.dim        === "number" ? cfg.dim        : null;
  S.blockSize = typeof cfg.block_size === "number" ? cfg.block_size : null;
  S.topk      = typeof cfg.topk       === "number" ? cfg.topk       : null;
  S.window    = typeof cfg.window     === "number" ? cfg.window     : null;
  S.queryPos  = typeof cfg.query_pos  === "number" ? cfg.query_pos  : null;

  const br = payload.branches || {};
  const sw = br.sliding_window || {};
  const sel = br.selection || {};
  const comp = br.compression || {};
  S.windowPositions = Array.isArray(sw.window_positions) ? sw.window_positions : null;
  S.selectedBlocks  = Array.isArray(sel.selected_block_indices) ? sel.selected_block_indices : null;
  S.nSummary        = typeof comp.n_summary_tokens === "number" ? comp.n_summary_tokens : null;

  S.gateScore   = typeof payload.gate_combined_score === "number" ? payload.gate_combined_score : null;
  S.gateWeights = payload.gate_weights || null;

  const fa = (payload.flops_accounting || {}).this_query || {};
  S.denseEvals    = typeof fa.dense_evals    === "number" ? fa.dense_evals    : null;
  S.nsaEvals      = typeof fa.nsa_evals      === "number" ? fa.nsa_evals      : null;
  S.sparsityRatio = typeof fa.sparsity_ratio === "number" ? fa.sparsity_ratio : null;

  const pc = payload.parity_check || {};
  S.recall = typeof pc.recall_vs_dense_oracle === "number" ? pc.recall_vs_dense_oracle : null;

  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the sequence lattice from live data
// =============================================================================
function _updateLattice() {
  const live = S.state === "live";
  const seqLen = live && S.seqLen ? Math.min(S.seqLen, MAX_TOKENS) : 0;
  const blockSize = S.blockSize || 16;
  const windowSet = new Set(live && S.windowPositions ? S.windowPositions : []);
  const selBlocks = live && S.selectedBlocks ? S.selectedBlocks : [];
  const selPositions = new Set();
  selBlocks.forEach((bi) => {
    const start = bi * blockSize;
    for (let p = start; p < start + blockSize && p < seqLen; p++) selPositions.add(p);
  });

  for (let i = 0; i < MAX_TOKENS; i++) {
    const mesh = _tokenMesh[i];
    if (!live || i >= seqLen) { mesh.visible = false; continue; }
    mesh.visible = true;

    const inWindow = windowSet.has(i);
    const inSelected = selPositions.has(i);
    let color, opacity, emissiveIntensity, y;
    if (inWindow && inSelected) {
      color = C_SELECT; opacity = 0.98; emissiveIntensity = 0.6; y = 0.12;
    } else if (inSelected) {
      color = C_SELECT; opacity = 0.85; emissiveIntensity = 0.5; y = 0.06;
    } else if (inWindow) {
      color = C_SPINE; opacity = 0.85; emissiveIntensity = 0.45; y = 0.06;
    } else {
      color = C_UNSEL; opacity = 0.2; emissiveIntensity = 0.1; y = 0.0;
    }
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = emissiveIntensity;
    mesh.material.opacity = opacity;
    mesh.position.y = y;
  }

  // compression summary tokens float above the spine, evenly spaced.
  const nSummary = live && S.nSummary ? Math.min(S.nSummary, _summaryMesh.length) : 0;
  for (let i = 0; i < _summaryMesh.length; i++) {
    const mesh = _summaryMesh[i];
    const link = _summaryLinks[i];
    if (!live || i >= nSummary) { mesh.visible = false; link.visible = false; continue; }
    const frac = nSummary > 1 ? i / (nSummary - 1) : 0;
    const x = frac * SPINE_LEN;
    mesh.position.set(x, SUMMARY_Y, 0);
    mesh.visible = true;
    mesh.material.opacity = 0.75;

    link.geometry.dispose();
    link.geometry = new _THREE.BufferGeometry().setFromPoints([
      new _THREE.Vector3(x, 0, 0), new _THREE.Vector3(x, SUMMARY_Y, 0),
    ]);
    link.visible = true;
  }

  // spine degrades to grey when not live
  _spineLine.material.color.setHex(live ? C_SPINE : C_DIM);
  _spineLine.material.opacity = live ? 0.4 : 0.15;

  if (_gateMarker) {
    if (live && S.gateScore != null) {
      _gateMarker.material.color.setHex(C_SELECT);
      _gateMarker.material.emissive.setHex(C_SELECT);
      _gateMarker.material.opacity = 0.85;
      const scale = 0.85 + Math.min(1.5, Math.abs(S.gateScore) * 3);
      _gateMarker.scale.setScalar(scale);
    } else {
      _gateMarker.material.color.setHex(C_DIM);
      _gateMarker.material.emissive.setHex(C_DIM);
      _gateMarker.material.opacity = 0.3;
      _gateMarker.scale.setScalar(1.0);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.1;
  if (_gateMarker) {
    _gateMarker.rotation.y += 0.02;
    _gateMarker.rotation.x += 0.01;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
    _gateMarker.scale.multiplyScalar(1.0);
    _gateMarker.rotation.z = Math.sin(t * 0.001) * 0.15;
    void pulse;
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
    'Three parallel branches replace one dense O(L\u00b2) attention pass: a coarse ' +
    '<b>compression</b> branch pools blocks of tokens into summaries, a <b>top-k selection</b> ' +
    'branch scores blocks cheaply then attends fully only to the winners, and a local ' +
    '<b>sliding-window</b> branch always covers recent context. A fixed-weight gate combines ' +
    'all three. Honesty label <b>MODELED</b> (deterministic reimplementation over synthetic, ' +
    'LCG-seeded data; NOT a trained model). 0 runtime CDN.';
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
  nm.textContent = "native sparse attention";
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

  grid.appendChild(kpiRow("nsa-seqlen",   "seq_len (tokens)"));
  grid.appendChild(kpiRow("nsa-blocks",   "block_size / topk / window"));
  grid.appendChild(kpiRow("nsa-nsummary", "compression summary tokens"));
  grid.appendChild(kpiRow("nsa-selblocks","selected blocks (top-k)"));
  grid.appendChild(kpiRow("nsa-gate",     "gate_combined_score \u2014 MODELED"));
  grid.appendChild(kpiRow("nsa-evals",    "NSA vs dense evals (this query)"));
  grid.appendChild(kpiRow("nsa-sparsity", "sparsity ratio \u2014 MODELED"));
  grid.appendChild(kpiRow("nsa-recall",   "recall vs dense oracle"));
  grid.appendChild(kpiRow("nsa-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "DeepSeek-AI, Yuan et al. 2025 arXiv:2502.11089 (Native Sparse Attention) \u00b7 " +
    "discussion news.ycombinator.com/item?id=46181231. MODELED \u00b7 not claimed-as.";
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
  pd.id = "nsa-plain";
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
  const seq     = S.seqLen        != null ? String(S.seqLen) : "loading\u2026";
  const ratio   = S.sparsityRatio != null ? (S.sparsityRatio * 100).toFixed(1) + "%" : "loading\u2026";
  const rec     = S.recall        != null ? (S.recall * 100).toFixed(1) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Normal (\u201cdense\u201d) attention checks every word against every " +
    "other word \u2014 cost grows with the square of the text length. Native Sparse Attention instead " +
    "splits the job three ways: a cheap <b>skim</b> of the whole document (compression), a focused " +
    "<b>deep read</b> of only the most relevant chunks (top-k selection), and always keeping the " +
    "<b>last few words</b> in view (sliding window). Combined with fixed weights, this uses only " +
    "about <b>" + ratio + "</b> of the work a full dense pass would need on a " + seq + "-token " +
    "sequence, while still covering about <b>" + rec + "</b> of the spots a full dense scan would " +
    "have flagged as important. This is a <b>MODELED</b> demonstration of the sparsity pattern on " +
    "synthetic data \u2014 not a trained model, not the original DeepSeek-AI kernel.";
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
  _set("nsa-seqlen",   t || (S.seqLen != null ? String(S.seqLen) : "\u2014"));
  _set("nsa-blocks",   t || ((S.blockSize != null && S.topk != null && S.window != null)
                        ? `${S.blockSize} / ${S.topk} / ${S.window}` : "\u2014"));
  _set("nsa-nsummary", t || (S.nSummary != null ? String(S.nSummary) : "\u2014"));
  _set("nsa-selblocks",t || (S.selectedBlocks ? `[${S.selectedBlocks.join(", ")}]` : "\u2014"));
  _set("nsa-gate",     t || fx(S.gateScore, 4));
  _set("nsa-evals",    t || ((S.nsaEvals != null && S.denseEvals != null)
                        ? `${S.nsaEvals} / ${S.denseEvals}` : "\u2014"));
  _set("nsa-sparsity", t || pct(S.sparsityRatio, 2));
  _set("nsa-recall",   t || pct(S.recall, 1));
  // honesty label verbatim — never upgraded
  _set("nsa-label", t || (S.label || "MODELED"));
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
  _floor = null; _spineLine = null; _tokenMesh = []; _summaryMesh = []; _summaryLinks = []; _gateMarker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.dim = S.blockSize = S.topk = S.window = S.queryPos = null;
  S.windowPositions = S.selectedBlocks = S.nSummary = S.gateScore = S.gateWeights = null;
  S.denseEvals = S.nsaEvals = S.sparsityRatio = S.recall = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
