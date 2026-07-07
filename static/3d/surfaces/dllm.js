// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/dllm.js — DIFFUSION-LLM PARALLEL DENOISING organ for the holographic
// frontier ring (Mercury/LLaDA-style masked-diffusion decoding, MODELED).
//
// Renders the token sequence as a 3D row/grid lattice driven by a live closed-
// form snapshot from /api/killinchu/v1/dllm/denoise:
//   - ALL `length` positions start MASKED (grey cubes).
//   - Across `steps` denoising rounds, a highest-confidence-first schedule
//     unmasks a batch of NEW positions EACH round, in parallel (not left-to-
//     right) -- they light up lattice-blue -> violet-blue as rounds advance.
//   - A HUD shows parallelism_factor (= length/steps, tokens decided per
//     round) and the tokens_per_round schedule, contrasted against the
//     autoregressive baseline of 1.0 token/step.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is;
// it is never upgraded.
//
// Surface export shape (mirrors testtime.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   length, steps, parallelism_factor, tokens_per_round[], cumulative_unmasked[],
//   confidence_trajectory[], final_sequence[] (synthetic token ids)
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   LLaDA (masked diffusion LLM): Nie et al. 2025, arXiv:2502.09992
//     https://arxiv.org/abs/2502.09992  ·  https://github.com/ML-GSAI/LLaDA
//   Mercury (Inception Labs, commercial-scale diffusion LLM): arXiv:2506.17298
//     https://arxiv.org/abs/2506.17298
//   D3PM (discrete-state denoising diffusion foundation): Austin et al. 2021,
//     arXiv:2107.03006  https://arxiv.org/abs/2107.03006
//
// HONESTY LABELS: MODELED (clean-room deterministic simulation of the masked-
//   diffusion parallel-decoding SCHEDULE; NOT a trained diffusion LLM; NEVER-
//   CLAIMED-AS Mercury/LLaDA). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (unmasked tokens), violet-blue 0x8a6bff
//   (recently-unmasked / active-round highlight), proof-teal 0x3af4c8 (HUD
//   accent), greys (masked / degraded). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "dllm";
const TITLE = "Diffusion-LLM Parallel Denoising (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted twin (same-origin, szl_diffusion_llm.py):
// a real LLaDA-style linear reverse-diffusion schedule + confidence-first parallel-unmask
// over a seeded confidence field (label MODELED, read verbatim). The isolated killinchu
// Space stays a guarded cross-origin FALLBACK so a fault in either path never darkens the other.
const EP = "/api/a11oy/v1/dllm/denoise?seed=42&steps=8&length=64";
const EP_FALLBACK = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/dllm/denoise?seed=42&steps=8&length=64";

// data-viz hues — purple BANNED
const C_MASKED  = 0x3a4149;  // grey — still-masked token (pre-denoise)
const C_UNMASK  = 0x5b8dee;  // lattice-blue — committed/unmasked token
const C_RECENT  = 0x8a6bff;  // violet-blue — unmasked THIS round (active highlight)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal accent (HUD / round marker)
const C_GRID    = 0x1b3a44;  // floor / link colour

// grid layout geometry
const CELL      = 0.42;   // world-units per token cell
const GAP       = 0.10;   // world-units gap between cells
const MAX_COLS  = 16;     // wrap the row into a grid after this many columns

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _show = null;

// geometry handles
let _cells = [];     // Array<THREE.Mesh> — one per token position
let _floor = null;
let _roundMarker = null; // THREE.Mesh — pulsing "current round" indicator

// round-by-round playback state (client-side animation over the live schedule)
let _playTimer = null;
let _playRound = 0;

// live state
const S = {
  label:        null,
  length:       null,
  steps:        null,
  parallelism:  null,
  tokensPerRound: null,   // tokens_per_round[]
  cumulative:   null,     // cumulative_unmasked[]
  confidence:   null,     // confidence_trajectory[]
  finalSeq:     null,     // final_sequence[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(3, 6, 14);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRoundMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onDenoise, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.4;
  _group.add(grid);
  _floor = grid;
}

function _buildRoundMarker() {
  const THREE = _THREE;
  _roundMarker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.20, 1),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _roundMarker.position.set(0, 1.4, 0);
  _group.add(_roundMarker);
}

// Build (or rebuild) the token lattice once `length` is known from live data.
function _ensureCells(length) {
  if (_cells.length === length) return;
  // dispose old cells first
  _cells.forEach((m) => {
    _group.remove(m);
    if (m.geometry && m.geometry.dispose) m.geometry.dispose();
    if (m.material && m.material.dispose) m.material.dispose();
  });
  _cells = [];

  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(CELL, CELL, CELL);
  const cols = Math.min(MAX_COLS, Math.max(1, length));
  for (let i = 0; i < length; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const mat = new THREE.MeshStandardMaterial({ color: C_MASKED, emissive: C_MASKED, emissiveIntensity: 0.15, transparent: true, opacity: 0.85 });
    const m = new THREE.Mesh(geo, mat);
    m.position.set(col * (CELL + GAP), -row * (CELL + GAP), 0);
    _group.add(m);
    _cells.push(m);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onDenoise(j) {
  // read honesty label VERBATIM — never upgrade
  S.label        = (j.label || "MODELED").toUpperCase();
  S.length       = typeof j.length === "number" ? j.length : null;
  S.steps        = typeof j.steps === "number" ? j.steps : null;
  S.parallelism  = typeof j.parallelism_factor === "number" ? j.parallelism_factor : null;
  S.tokensPerRound = Array.isArray(j.tokens_per_round) ? j.tokens_per_round : null;
  S.cumulative   = Array.isArray(j.cumulative_unmasked) ? j.cumulative_unmasked : null;
  S.confidence   = Array.isArray(j.confidence_trajectory) ? j.confidence_trajectory : null;
  S.finalSeq     = Array.isArray(j.final_sequence) ? j.final_sequence : null;

  if (S.length) _ensureCells(S.length);
  _restartPlayback();
  _paintOverlay();
}

// =============================================================================
// round-by-round playback — animates the parallel unmask schedule so the
// viewer can SEE positions light up in batches per round, not left-to-right.
// =============================================================================
function _restartPlayback() {
  if (_playTimer) { clearInterval(_playTimer); _playTimer = null; }
  _playRound = 0;
  if (!(S.state === "live" && S.length && S.steps && S.tokensPerRound)) {
    _paintMasked();
    return;
  }
  // Deterministic-looking reveal order: fixed shuffled index list derived from
  // the cell count (client-side only, purely for visual ordering — the
  // authoritative parallel-unmask COUNTS per round come from the live endpoint).
  const order = _shuffledIndices(S.length);
  let cursor = 0;
  _paintMasked();

  _playTimer = setInterval(() => {
    if (_playRound >= S.tokensPerRound.length) {
      clearInterval(_playTimer); _playTimer = null;
      return;
    }
    const n = S.tokensPerRound[_playRound] || 0;
    for (let k = 0; k < n && cursor < order.length; k++, cursor++) {
      _lightCell(order[cursor], true);
    }
    // dim the "recent" highlight from the previous round back to steady unmasked-blue
    _settleColors();
    _playRound += 1;
    _updateRoundMarker();
  }, 650);
}

function _shuffledIndices(n) {
  // simple deterministic-seeded shuffle (Mulberry32-style) purely for display order
  let seed = (n * 2654435761) >>> 0;
  function rnd() {
    seed = (seed + 0x6D2B79F5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  const idx = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return idx;
}

function _paintMasked() {
  _cells.forEach((m) => {
    m.material.color.setHex(C_MASKED);
    m.material.emissive.setHex(C_MASKED);
    m.material.emissiveIntensity = 0.15;
    m.material.opacity = 0.85;
  });
}

function _lightCell(i, recent) {
  const m = _cells[i];
  if (!m) return;
  const c = recent ? C_RECENT : C_UNMASK;
  m.material.color.setHex(c);
  m.material.emissive.setHex(c);
  m.material.emissiveIntensity = recent ? 0.7 : 0.35;
  m.material.opacity = 1.0;
  m._recentTick = 3; // frames-ish counter handled in _onFrame settle pass
}

function _settleColors() {
  // cells lit "recent" (violet-blue) on the previous tick fade to steady
  // lattice-blue on this tick, so only the CURRENT round's batch glows bright.
  _cells.forEach((m) => {
    if (m.material.color.getHex() === C_RECENT) {
      m.material.color.setHex(C_UNMASK);
      m.material.emissive.setHex(C_UNMASK);
      m.material.emissiveIntensity = 0.35;
    }
  });
}

function _updateRoundMarker() {
  if (!_roundMarker || !_cells.length) return;
  const cols = Math.min(MAX_COLS, Math.max(1, S.length || 1));
  const x = ((cols - 1) * (CELL + GAP)) / 2;
  _roundMarker.position.set(x, 1.4, 0);
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.12;
  if (_roundMarker) {
    _roundMarker.rotation.y += 0.02;
    _roundMarker.rotation.x += 0.01;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _roundMarker.scale.setScalar(pulse);
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
    'Diffusion LLMs (<b>Mercury</b>/<b>LLaDA</b>-style) start from a <b>fully-masked</b> sequence ' +
    'and unmask ALL positions in <b>parallel</b> across denoising rounds \u2014 not left-to-right like ' +
    'autoregressive decoding. Honesty label <b>MODELED</b> (clean-room simulation of the decoding ' +
    'SCHEDULE; NOT a trained diffusion LLM). 0 runtime CDN.';
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
  nm.textContent = "dllm-parallel-denoise";
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

  grid.appendChild(kpiRow("dl-length",   "sequence length"));
  grid.appendChild(kpiRow("dl-steps",    "denoising rounds (steps)"));
  grid.appendChild(kpiRow("dl-parallel", "parallelism factor \u2014 MODELED"));
  grid.appendChild(kpiRow("dl-ar",       "vs autoregressive (1.0 tok/step)"));
  grid.appendChild(kpiRow("dl-tpr",      "tokens/round schedule"));
  grid.appendChild(kpiRow("dl-conf",     "confidence trajectory (last)"));
  grid.appendChild(kpiRow("dl-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "LLaDA \u2014 Nie et al. arXiv:2502.09992 (github.com/ML-GSAI/LLaDA) \u00b7 Mercury (Inception Labs) arXiv:2506.17298 \u00b7 D3PM \u2014 Austin et al. arXiv:2107.03006. MODELED \u00b7 not claimed-as.";
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
  pd.id = "dl-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  // Fold the legacy panel into the shared showcase overlay (surfaces/_showcase.js):
  // title + live badge + doctrine legend live in the always-visible chrome; the
  // descriptive text + KPI card become the collapsible body so the 3D scene is the star.
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    legend: true,
  });
  _overlay.style.position = "static";
  _overlay.style.left = _overlay.style.top = "auto";
  _overlay.style.maxWidth = "none";
  _overlay.style.font = "inherit";
  if (_overlay.firstChild) _overlay.removeChild(_overlay.firstChild); // drop duplicate title
  _show.body.appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const len   = S.length != null ? String(S.length) : "loading\u2026";
  const steps = S.steps  != null ? String(S.steps)  : "loading\u2026";
  const par   = S.parallelism != null ? S.parallelism.toFixed(2) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> A normal (autoregressive) AI writes one word at a time, so a " +
    len + "-token answer takes " + len + " sequential steps. A <b>diffusion LLM</b> instead starts " +
    "with a completely blank/masked answer and fills in <b>many words at once</b>, refining the " +
    "whole thing over just " + steps + " rounds. That is a <b>" + par + "x parallelism factor</b> \u2014 " +
    "roughly " + par + " tokens decided per round versus 1 token per step for old-style decoding. " +
    "This view is a <b>MODELED</b> clean-room simulation of that decoding SCHEDULE, not a real " +
    "trained diffusion model \u2014 and it is NEVER claimed to be Mercury or LLaDA themselves.";
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
  _set("dl-length",   t || (S.length != null ? String(S.length) : "\u2014"));
  _set("dl-steps",    t || (S.steps  != null ? String(S.steps)  : "\u2014"));
  _set("dl-parallel", t || (S.parallelism != null ? fx(S.parallelism, 3) + "x" : "\u2014"));
  _set("dl-ar",       t || (S.parallelism != null ? fx(S.parallelism, 2) + "x faster (tokens/round vs 1.0 tok/step)" : "\u2014"));
  _set("dl-tpr",      t || (S.tokensPerRound ? S.tokensPerRound.join(",") : "\u2014"));
  _set("dl-conf",     t || (S.confidence && S.confidence.length ? fx(S.confidence[S.confidence.length - 1], 3) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("dl-label",    t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  if (_playTimer) { try { clearInterval(_playTimer); } catch (_) {} _playTimer = null; }
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
  _group = _overlay = _show = null;
  _cells = []; _floor = null; _roundMarker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _playRound = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.length = S.steps = S.parallelism = null;
  S.tokensPerRound = S.cumulative = S.confidence = S.finalSeq = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP, EP_FALLBACK], mount, unmount };
