// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/kvcache.js — KV-CACHE H2O EVICTION organ for the holographic frontier
// ring (Heavy-Hitter Oracle runtime cache eviction, Zhang et al. 2023-style).
// Renders a simulated decoding stream of `seq_len` tokens as a 3D token row:
// kept heavy-hitters glow proof-teal, the recent sliding window glows
// lattice-blue, and evicted tokens fade to grey and drop out of the row. A HUD
// shows memory_ratio + mass_retained per policy (H2O / sliding-window / full-
// cache oracle) from the live snapshot at
// /api/killinchu/v1/kvcache/h2o-evict. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   seq_len, capacity, window, memory_ratio, h2o_mass_retained,
//   sliding_mass_retained, full_mass_retained, h2o_vs_sliding_gain,
//   evicted_count, per_token[] {i, mass, h2o_kept, sliding_kept}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   H2O — Heavy-Hitter Oracle KV-cache eviction (policy simulated here):
//     Zhang et al. 2023, arXiv:2306.14048
//     https://arxiv.org/abs/2306.14048
//   StreamingLLM (recency-window / attention-sink baseline — reference only):
//     Xiao et al. 2023, arXiv:2309.17453
//     https://arxiv.org/abs/2309.17453
//
// HONESTY LABELS: MODELED (deterministic simulation of the H2O heavy-hitter
//   eviction policy on a synthetic attention-mass trace; NOT a real KV cache
//   or trained model; NEVER-CLAIMED-AS a production inference engine). Read
//   verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (recent sliding window), proof-teal 0x3af4c8
//   (kept heavy hitters / HUD accent), greys (evicted tokens / degraded state).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "kvcache";
const TITLE = "KV-Cache H2O Eviction · Heavy-Hitter Oracle (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the KV-cache eviction organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/kvcache/h2o-evict?seed=42&seq_len=512&capacity=128&window=32";

// data-viz hues — purple BANNED
const C_WINDOW   = 0x5b8dee;  // lattice-blue (recent sliding-window tokens)
const C_HEAVY    = 0x3af4c8;  // proof-teal (kept heavy hitters / HUD accent)
const C_EVICTED  = 0x5a6570;  // grey (evicted token)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// token-row layout geometry
const TOKEN_GAP  = 0.42;   // world-units between tokens along X (decoding axis)
const MAX_TOKENS = 160;    // cap on tokens rendered in the row (perf)
const ROW_Y      = 0.4;    // resting height of a kept token
const EVICT_Y    = -1.6;   // dropped height of an evicted token

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor      = null;
let _spine      = null;               // THREE.Line — decoding-stream spine
let _tokenMesh  = [];                 // Array<THREE.Mesh> — one per rendered token slot
let _marker     = null;               // THREE.Mesh — HUD pulsing marker (memory_ratio cue)

// live state
const S = {
  label:               null,
  seqLen:              null,   // seq_len
  capacity:            null,   // capacity
  window:              null,   // window
  memoryRatio:         null,   // memory_ratio
  h2oMassRetained:     null,   // h2o_mass_retained
  slidingMassRetained: null,   // sliding_mass_retained
  fullMassRetained:    null,   // full_mass_retained
  h2oVsSlidingGain:    null,   // h2o_vs_sliding_gain
  evictedCount:        null,   // evicted_count
  perToken:            null,   // per_token[]
  state:               "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 7, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(6, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildTokenRow();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onKvcache, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed row of token meshes: MAX_TOKENS slots. We toggle
// visibility / color / position in-place as live data arrives (no per-poll
// geometry churn).
function _buildTokenRow() {
  const THREE = _THREE;

  // decoding-stream spine: a straight line along X marking the token order
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(TOKEN_GAP * (MAX_TOKENS - 1) + 1, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_WINDOW, transparent: true, opacity: 0.4 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const tokenGeo = new THREE.OctahedronGeometry(0.16, 0);
  for (let t = 0; t < MAX_TOKENS; t++) {
    const x = t * TOKEN_GAP;
    const mesh = new THREE.Mesh(
      tokenGeo,
      new THREE.MeshStandardMaterial({ color: C_EVICTED, emissive: C_EVICTED, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(x, ROW_Y, 0);
    mesh.visible = false;
    _group.add(mesh);
    _tokenMesh.push(mesh);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.26, 1),
    new THREE.MeshStandardMaterial({ color: C_HEAVY, emissive: C_HEAVY, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -0.9, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onKvcache(j) {
  // read honesty label VERBATIM — never upgrade
  S.label               = (j.label || "MODELED").toUpperCase();
  S.seqLen              = typeof j.seq_len               === "number" ? j.seq_len               : null;
  S.capacity            = typeof j.capacity              === "number" ? j.capacity              : null;
  S.window              = typeof j.window                === "number" ? j.window                : null;
  S.memoryRatio         = typeof j.memory_ratio          === "number" ? j.memory_ratio          : null;
  S.h2oMassRetained     = typeof j.h2o_mass_retained     === "number" ? j.h2o_mass_retained     : null;
  S.slidingMassRetained = typeof j.sliding_mass_retained === "number" ? j.sliding_mass_retained : null;
  S.fullMassRetained    = typeof j.full_mass_retained    === "number" ? j.full_mass_retained    : null;
  S.h2oVsSlidingGain    = typeof j.h2o_vs_sliding_gain   === "number" ? j.h2o_vs_sliding_gain   : null;
  S.evictedCount        = typeof j.evicted_count         === "number" ? j.evicted_count         : null;
  S.perToken            = Array.isArray(j.per_token) ? j.per_token : null;

  _updateTokenRow();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the token row from live data
// =============================================================================
function _updateTokenRow() {
  const live = S.state === "live";
  const toks = live && S.perToken && S.perToken.length ? S.perToken.slice(0, MAX_TOKENS) : [];

  for (let t = 0; t < MAX_TOKENS; t++) {
    const mesh = _tokenMesh[t];
    if (!live || t >= toks.length) {
      mesh.visible = false;
      continue;
    }
    mesh.visible = true;
    const rec = toks[t];
    const kept = !!rec.h2o_kept;
    const inWindow = kept && !!rec.sliding_kept; // recent tokens are kept by BOTH policies
    let color;
    if (!kept) {
      color = C_EVICTED;                          // evicted under H2O -> grey, dropped
    } else if (inWindow) {
      color = C_WINDOW;                            // recent-window heavy hitter -> lattice-blue
    } else {
      color = C_HEAVY;                             // pure heavy hitter (older) -> proof-teal
    }
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = kept ? (inWindow ? 0.45 : 0.6) : 0.12;
    mesh.material.opacity = kept ? 0.95 : 0.30;
    // evicted tokens visually drop out of the row (H2O eviction cue); mass
    // scales the resting height slightly for kept heavy hitters (taller = heavier).
    const massScale = typeof rec.mass === "number" ? Math.min(1.0, rec.mass * 2.0) : 0.0;
    mesh.position.y = kept ? ROW_Y + massScale * 0.5 : EVICT_Y;
    mesh.position.z = kept ? 0 : -0.4;
  }

  // spine degrades to grey when not live
  _spine.material.color.setHex(live ? C_WINDOW : C_DIM);
  _spine.material.opacity = live ? 0.4 : 0.15;

  if (_marker) {
    if (live && S.memoryRatio != null) {
      _marker.material.color.setHex(C_HEAVY);
      _marker.material.emissive.setHex(C_HEAVY);
      _marker.material.opacity = 0.85;
      // marker rides along X proportional to memory_ratio (visual "budget" cue)
      const x = Math.min(TOKEN_GAP * (MAX_TOKENS - 1), (S.memoryRatio || 0) * TOKEN_GAP * (MAX_TOKENS - 1));
      _marker.position.set(x, -0.9, 0);
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
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
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
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MODELED", text: "h2o eviction", name: "kv" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'A decoding stream accumulates a KV cache entry per token. <b>H2O</b> (Heavy-Hitter Oracle) ' +
      'keeps a bounded cache by retaining the top cumulative-attention-mass \u201cheavy hitters\u201d ' +
      'plus a sliding recent <b>window</b>, instead of evicting purely by recency. HUD compares ' +
      'H2O against a sliding-window-only baseline and the full-cache (no eviction) oracle. ' +
      'Honesty label <b>MODELED</b> (deterministic simulation on a synthetic attention trace; NOT a ' +
      'real KV cache or trained model). 0 runtime CDN.',
    citations:
      "H2O \u2014 Zhang et al. arXiv:2306.14048 \u00b7 StreamingLLM \u2014 Xiao et al. arXiv:2309.17453. MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["kv-seqlen"]   = _show.addField("seq_len (decoded tokens)");
  _el["kv-capacity"] = _show.addField("capacity (KV-cache slots)");
  _el["kv-window"]   = _show.addField("window (recent tokens reserved)");
  _el["kv-memratio"] = _show.addField("memory_ratio (capacity/seq_len)");
  _el["kv-h2o"]      = _show.addField("H2O mass_retained \u2014 MODELED");
  _el["kv-sliding"]  = _show.addField("sliding-window mass_retained");
  _el["kv-full"]     = _show.addField("full-cache mass_retained (oracle)");
  _el["kv-gain"]     = _show.addField("H2O vs sliding gain");
  _el["kv-evicted"]  = _show.addField("evicted_count");
  _el["kv-label"]    = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const mem     = S.memoryRatio         != null ? (S.memoryRatio * 100).toFixed(1) + "%" : "loading\u2026";
  const h2oPct  = S.h2oMassRetained     != null ? (S.h2oMassRetained * 100).toFixed(1) + "%" : "loading\u2026";
  const slidPct = S.slidingMassRetained != null ? (S.slidingMassRetained * 100).toFixed(1) + "%" : "loading\u2026";
  return (
    "<b>What this means:</b> A language model keeps a running \u201cnotebook\u201d (the KV cache) of " +
    "every word it has generated so it can pay attention back to earlier words. That notebook grows " +
    "forever unless something is thrown away. Here the notebook is capped at just <b>" + mem + "</b> " +
    "of its full size. Throwing away only the OLDEST pages (sliding-window) keeps just <b>" + slidPct +
    "</b> of the important information. The <b>H2O</b> approach instead keeps whichever pages turned " +
    "out to matter most so far (the \u201cheavy hitters\u201d), plus the most recent few \u2014 and keeps " +
    "<b>" + h2oPct + "</b> of the important information at the SAME notebook size. This view is a " +
    "<b>MODELED</b> deterministic simulation of that keep/discard rule on a synthetic attention trace, " +
    "not a run of a real trained model or KV cache.");
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
  _set("kv-seqlen",   t || (S.seqLen   != null ? String(S.seqLen)   : "\u2014"));
  _set("kv-capacity", t || (S.capacity != null ? String(S.capacity) : "\u2014"));
  _set("kv-window",   t || (S.window   != null ? String(S.window)   : "\u2014"));
  _set("kv-memratio", t || pct(S.memoryRatio, 2));
  _set("kv-h2o",      t || pct(S.h2oMassRetained, 2));
  _set("kv-sliding",  t || pct(S.slidingMassRetained, 2));
  _set("kv-full",     t || pct(S.fullMassRetained, 2));
  _set("kv-gain",     t || (S.h2oVsSlidingGain != null ? "+" + pct(S.h2oVsSlidingGain, 2) : "\u2014"));
  _set("kv-evicted",  t || (S.evictedCount != null ? String(S.evictedCount) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("kv-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("kv", S.label || "MODELED", { text: "h2o eviction" }); _show.refreshPlain(); }
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
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
  _group = _show = null;
  _floor = null; _spine = null; _tokenMesh = []; _marker = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.capacity = S.window = S.memoryRatio = null;
  S.h2oMassRetained = S.slidingMassRetained = S.fullMassRetained = null;
  S.h2oVsSlidingGain = S.evictedCount = S.perToken = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
