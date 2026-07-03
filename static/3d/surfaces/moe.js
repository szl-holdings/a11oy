// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/moe.js — MoE SPARSE-UPCYCLING ROUTER SIMULATOR organ for the holographic
// frontier ring.
//
// Renders a 3D expert-load HEAT-SURFACE driven by a live snapshot from
// /api/killinchu/v1/moe/route:
//   X axis = expert index (0..experts-1)
//   Y axis = cumulative load (bar height) for that expert, up to a "routing round"
//   Z axis = routing round (the routing_table sample is bucketed into rounds so the
//            surface shows load ACCUMULATING over rounds, not just a final snapshot)
// Under-loaded experts (below the mean) render as lattice-blue peaks; balanced /
// at-or-above-mean experts render as proof-teal peaks — so the load_balance_cv HUD
// number has a directly visible shape (a flat teal skyline = balanced; spiky blue/teal
// contrast = imbalanced / "hot expert" routing). Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors ssm.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   tokens, experts, topk
//   routing_table (sample) — bucketed into rounds to build the heat-surface
//   expert_load_counts[]   — final per-expert load counts
//   load_balance_cv        — coefficient of variation of expert_load_counts
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Sparse Upcycling — Komatsuzaki et al. (2023) "Sparse Upcycling: Training
//     Mixture-of-Experts from Dense Checkpoints". arXiv:2212.05055.
//     https://arxiv.org/abs/2212.05055
//   DeepSeekMoE — Dai et al. (2024) "DeepSeekMoE: Towards Ultimate Expert
//     Specialization in Mixture-of-Experts Language Models". arXiv:2401.06066.
//     https://arxiv.org/abs/2401.06066
//   Expert Upcycling (amazon-science, code):
//     https://github.com/amazon-science/expert-upcycling
//
// HONESTY LABELS: MODELED (deterministic top-K softmax router simulation illustrating
//   sparse-upcycling load balance; NOT a trained MoE; NEVER-CLAIMED-AS DeepSeekMoE/
//   Gemma-MoE/any production router). Read verbatim from JSON; never upgraded here.
// COLOURS: grey base grid, lattice-blue 0x5b8dee (under-loaded peaks), proof-teal
//   0x3af4c8 (balanced/at-or-above-mean peaks). Violet-blue 0x8a6bff reserved for HUD
//   accent only. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "moe";
const TITLE = "MoE Sparse-Upcycling Router Simulator (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the MoE-router organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/moe/route?seed=42&tokens=64&experts=8&topk=2";

// data-viz hues — purple BANNED
const C_UNDER   = 0x5b8dee;  // lattice-blue (under-loaded expert peaks)
const C_BALANCE = 0x3af4c8;  // proof-teal (balanced / at-or-above-mean expert peaks)
const C_ACCENT  = 0x8a6bff;  // violet-blue (HUD accent only — not used as a bar colour)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

const N_ROUNDS_MAX = 8;      // number of "routing rounds" the sample is bucketed into
const CELL_X = 1.1;          // world-units per expert column
const CELL_Z = 1.3;          // world-units per routing round row
const MAX_BAR_H = 5.0;       // world-units of max bar height (cumulative load axis)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor = null;
let _bars = [];          // Array<THREE.Mesh> — heat-surface bars, index = round*experts + expertIdx
let _barGeo = null;      // shared unit-box geometry (scaled per-bar)
let _labelGroup = null;  // small per-expert axis tick markers

// live state
const S = {
  label:      null,
  tokens:     null,
  experts:    null,
  topk:       null,
  routingTable: null,     // Array<{token, chosen_experts, weights}>
  loadCounts: null,       // Array<number> — final per-expert load counts
  loadCV:     null,       // load_balance_cv
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 9, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 1.5, 2); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHeatSurface();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onRoute, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed max grid of bar meshes (N_ROUNDS_MAX x MAX experts we ever
// expect, generously capped); we scale/recolor/position in-place as live data
// arrives (no per-poll geometry churn beyond count changes on shape change).
const _MAX_EXPERTS_GRID = 32;

function _buildHeatSurface() {
  const THREE = _THREE;
  _barGeo = new THREE.BoxGeometry(0.8, 1, 0.8); // unit height; scaled per-bar in Y
  _bars = [];
  for (let r = 0; r < N_ROUNDS_MAX; r++) {
    for (let e = 0; e < _MAX_EXPERTS_GRID; e++) {
      const mat = new THREE.MeshStandardMaterial({
        color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.85,
      });
      const m = new THREE.Mesh(_barGeo, mat);
      m.visible = false;
      m.position.set(e * CELL_X, 0, r * CELL_Z);
      _group.add(m);
      _bars.push(m);
    }
  }

  // baseline axes (expert axis + round axis), grey, data-viz only
  const axisPts = [
    new THREE.Vector3(-0.6, 0, -0.6), new THREE.Vector3(-0.6, 0, N_ROUNDS_MAX * CELL_Z),   // round axis
    new THREE.Vector3(-0.6, 0, -0.6), new THREE.Vector3(_MAX_EXPERTS_GRID * CELL_X, 0, -0.6), // expert axis
  ];
  const axisGeo = new THREE.BufferGeometry().setFromPoints(axisPts);
  const axisLine = new THREE.LineSegments(axisGeo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.4 }));
  _group.add(axisLine);
}

function _bar(round, expertIdx) {
  const idx = round * _MAX_EXPERTS_GRID + expertIdx;
  return (idx >= 0 && idx < _bars.length) ? _bars[idx] : null;
}

// =============================================================================
// live data handler
// =============================================================================
function _onRoute(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.tokens      = typeof j.tokens === "number" ? j.tokens : null;
  S.experts     = typeof j.experts === "number" ? j.experts : null;
  S.topk        = typeof j.topk === "number" ? j.topk : null;
  S.routingTable = Array.isArray(j.routing_table) ? j.routing_table : null;
  S.loadCounts  = Array.isArray(j.expert_load_counts) ? j.expert_load_counts : null;
  S.loadCV      = typeof j.load_balance_cv === "number" ? j.load_balance_cv : null;

  _updateHeatSurface();
  _paintOverlay();
}

// =============================================================================
// geometry updater — buckets the routing_table sample into rounds, accumulates
// per-expert load across rounds, and renders each (round, expert) cell as a bar
// whose height = cumulative load-so-far for that expert.
// =============================================================================
function _bucketIntoRounds(routingTable, nExperts) {
  // split the sampled routing_table (already token-ordered) into up to
  // N_ROUNDS_MAX contiguous chunks ("rounds"); accumulate per-expert counts
  // round-over-round so height = CUMULATIVE load (Z axis = round).
  const n = routingTable.length;
  const nRounds = Math.max(1, Math.min(N_ROUNDS_MAX, n));
  const chunkSize = Math.max(1, Math.ceil(n / nRounds));

  const cumulative = new Array(nExperts).fill(0);
  const rounds = []; // Array<Array<number>> — cumulative load per expert, per round

  for (let r = 0; r < nRounds; r++) {
    const start = r * chunkSize;
    const end = Math.min(n, start + chunkSize);
    for (let i = start; i < end; i++) {
      const row = routingTable[i];
      const chosen = Array.isArray(row.chosen_experts) ? row.chosen_experts : [];
      for (const e of chosen) {
        if (e >= 0 && e < nExperts) cumulative[e] += 1;
      }
    }
    rounds.push(cumulative.slice());
  }
  return rounds;
}

function _updateHeatSurface() {
  const live = S.state === "live";

  // hide everything first; re-show only the cells this snapshot uses
  for (const b of _bars) b.visible = false;

  if (!live || !S.routingTable || !S.loadCounts || !S.experts) {
    return;
  }

  const nExperts = Math.min(S.experts, _MAX_EXPERTS_GRID);
  const rounds = _bucketIntoRounds(S.routingTable, nExperts);
  const nRounds = rounds.length;

  // mean of the FINAL expert_load_counts (from the full endpoint result, not just
  // the sample) — used as the balanced/under-loaded colour threshold.
  const finalCounts = S.loadCounts.slice(0, nExperts);
  const mean = finalCounts.reduce((a, c) => a + c, 0) / Math.max(1, finalCounts.length);
  const maxCum = Math.max(1, ...rounds.map((row) => Math.max(1, ...row)));

  for (let r = 0; r < nRounds; r++) {
    const row = rounds[r];
    for (let e = 0; e < nExperts; e++) {
      const m = _bar(r, e);
      if (!m) continue;
      const cum = row[e] || 0;
      const h = Math.max(0.05, (cum / maxCum) * MAX_BAR_H);
      m.scale.y = h;
      m.position.set(e * CELL_X, h / 2, r * CELL_Z);
      // colour: under the FINAL mean -> lattice-blue (under-loaded); at/above -> proof-teal (balanced)
      const col = (finalCounts[e] >= mean) ? C_BALANCE : C_UNDER;
      m.material.color.setHex(col);
      m.material.emissive.setHex(col);
      m.material.emissiveIntensity = 0.35;
      m.material.opacity = 0.88;
      m.visible = true;
    }
  }
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
    'A <b>top-K softmax router</b> dispatches each synthetic token to its highest-weight ' +
    'experts. The heat-surface shows <b>cumulative expert load</b> building up across ' +
    'routing rounds (X = expert, Z = round, Y = cumulative load). <b style="color:#5b8dee">Blue</b> ' +
    'peaks are <b>under-loaded</b> experts (below mean); <b style="color:#3af4c8">teal</b> peaks are ' +
    '<b>balanced/at-or-above-mean</b>. Honesty label <b>MODELED</b> (deterministic router ' +
    'simulation — no trained MoE, never claimed as DeepSeekMoE/Gemma-MoE/any production ' +
    'router). 0 runtime CDN.';
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
  nm.textContent = "moe-router";
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

  grid.appendChild(kpiRow("moe-tokens",  "tokens routed"));
  grid.appendChild(kpiRow("moe-experts", "experts N"));
  grid.appendChild(kpiRow("moe-topk",    "top-K per token"));
  grid.appendChild(kpiRow("moe-cv",      "load_balance_cv"));
  grid.appendChild(kpiRow("moe-minmax",  "min / max expert load"));
  grid.appendChild(kpiRow("moe-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Komatsuzaki et al. arXiv:2212.05055 (Sparse Upcycling) \u00b7 Dai et al. arXiv:2401.06066 (DeepSeekMoE) \u00b7 github.com/amazon-science/expert-upcycling (Expert Upcycling). MODELED \u00b7 not claimed-as.";
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
  pd.id = "moe-plain";
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
  const tokens = S.tokens != null ? String(S.tokens) : "loading\u2026";
  const experts = S.experts != null ? String(S.experts) : "loading\u2026";
  const topk = S.topk != null ? String(S.topk) : "loading\u2026";
  const cv = S.loadCV != null ? S.loadCV.toFixed(3) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> A Mixture-of-Experts (MoE) layer has many small \u2018expert\u2019 " +
    "sub-networks, but only sends each token to a handful of them (here: top-<b>" + topk +
    "</b> out of <b>" + experts + "</b> experts) \u2014 this is what makes MoE models cheap to " +
    "run despite having huge total parameter counts. \u2018<b>Sparse upcycling</b>\u2019 is a real " +
    "training trick where you take an already-trained dense model and convert it into an " +
    "MoE by copying its layers into multiple experts and adding a fresh <b>router</b> " +
    "that learns to pick which expert handles which token. The hard part is <b>load " +
    "balance</b>: if the router always picks the same few experts, those experts get " +
    "overtrained and the rest are wasted. Here we routed <b>" + tokens + "</b> synthetic " +
    "tokens and measured <b>load_balance_cv = " + cv + "</b> (0 = perfectly even, higher " +
    "= some experts are getting hammered while others sit idle). " +
    "Plain: this is a toy, fully-deterministic stand-in for the router-fairness problem " +
    "real MoE systems have to solve \u2014 it is a <b>MODELED</b> simulation, not a trained " +
    "MoE and not a benchmark of any named production model.";
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
  _set("moe-tokens",  t || (S.tokens != null ? String(S.tokens) : "\u2014"));
  _set("moe-experts", t || (S.experts != null ? String(S.experts) : "\u2014"));
  _set("moe-topk",    t || (S.topk != null ? String(S.topk) : "\u2014"));
  _set("moe-cv",      t || fx(S.loadCV, 4));
  if (!t && Array.isArray(S.loadCounts) && S.loadCounts.length) {
    _set("moe-minmax", `${Math.min(...S.loadCounts)} / ${Math.max(...S.loadCounts)}`);
  } else {
    _set("moe-minmax", t || "\u2014");
  }
  // honesty label verbatim — never upgraded
  _set("moe-label", t || (S.label || "MODELED"));
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
  if (_barGeo && _barGeo.dispose) { try { _barGeo.dispose(); } catch (_) {} }
  _group = _overlay = null;
  _bars = []; _barGeo = null; _floor = null; _labelGroup = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.tokens = S.experts = S.topk = null;
  S.routingTable = S.loadCounts = S.loadCV = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
