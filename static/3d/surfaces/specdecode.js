// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/specdecode.js — SELF-SPECULATIVE MULTI-TOKEN DECODING organ for the
// holographic frontier ring (Medusa/EAGLE-style draft-then-verify). Renders the
// draft model proposing `draft_len` candidate tokens per step as a 3D token-tree
// / pipeline, then colors each proposed token ACCEPTED (proof-teal) or REJECTED
// (grey) per the live snapshot from /api/killinchu/v1/specdecode/simulate. A HUD
// shows acceptance_rate + speedup_factor. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors testtime.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   draft_len, trials, acceptance_rate, mean_accept_len, mean_tokens_per_step,
//   speedup_factor, per_step_accept_lengths[], lossless
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Speculative Decoding (accept/reject arithmetic simulated here):
//     Leviathan, Kalman & Matias 2023, arXiv:2211.17192
//     https://arxiv.org/abs/2211.17192
//   Medusa (multiple decoding heads, tree verification — reference only):
//     Cai et al. 2024, github.com/FasterDecoding/Medusa
//     https://github.com/FasterDecoding/Medusa
//   EAGLE (feature-level extrapolation drafting — reference only):
//     Li et al. 2024, arXiv:2401.15077
//     https://arxiv.org/abs/2401.15077
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the accept/reject
//   arithmetic; NOT Medusa/EAGLE; NEVER-CLAIMED-AS a production drafter). Read
//   verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (draft tokens / pipeline), proof-teal 0x3af4c8
//   (accepted tokens / HUD accent), greys (rejected tokens / degraded state).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "specdecode";
const TITLE = "Self-Speculative Decoding · Draft-then-Verify (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the spec-decode organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/specdecode/simulate?seed=42&draft_len=6&trials=256";

// data-viz hues — purple BANNED
const C_DRAFT   = 0x5b8dee;  // lattice-blue (draft-proposed token / pipeline spine)
const C_ACCEPT  = 0x3af4c8;  // proof-teal (accepted token / HUD accent)
const C_REJECT  = 0x5a6570;  // grey (rejected token)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// token-tree pipeline layout geometry
const STEP_LEN    = 2.1;   // world-units between steps along X (pipeline axis)
const TOKEN_GAP   = 0.85;  // world-units between tokens within a step (Y, draft depth)
const MAX_STEPS   = 10;    // number of recent steps rendered along the pipeline
const MAX_TOKENS  = 12;    // cap on draft_len rendered per step (perf)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _spine      = null;               // THREE.Line — pipeline spine (draft -> verify axis)
let _tokenMesh  = [];                 // Array<Array<THREE.Mesh>> — [step][tokenIdx]
let _stepLinks  = [];                 // Array<THREE.Line> — link from spine to each step's tokens
let _marker     = null;               // THREE.Mesh — HUD "current step" pulsing marker

// live state
const S = {
  label:        null,
  draftLen:     null,   // draft_len
  trials:       null,   // trials
  acceptRate:   null,   // acceptance_rate
  meanAccept:   null,   // mean_accept_len
  meanTokens:   null,   // mean_tokens_per_step
  speedup:      null,   // speedup_factor
  stepLengths:  null,   // per_step_accept_lengths[]
  lossless:     null,   // lossless (bool)
  state:        "init",
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
  _buildPipeline();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSpecdecode, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed grid of token meshes: MAX_STEPS steps x MAX_TOKENS tokens
// per step. We toggle visibility / color / position in-place as live data
// arrives (no per-poll geometry churn).
function _buildPipeline() {
  const THREE = _THREE;

  // pipeline spine: a straight line along X marking the draft->verify axis
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(STEP_LEN * (MAX_STEPS - 1) + 1, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_DRAFT, transparent: true, opacity: 0.45 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const tokenGeo = new THREE.OctahedronGeometry(0.20, 0);
  for (let s = 0; s < MAX_STEPS; s++) {
    const stepTokens = [];
    const x = s * STEP_LEN;
    for (let t = 0; t < MAX_TOKENS; t++) {
      const y = 0.4 + t * TOKEN_GAP;
      const mesh = new THREE.Mesh(
        tokenGeo,
        new THREE.MeshStandardMaterial({ color: C_DRAFT, emissive: C_DRAFT, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
      );
      mesh.position.set(x, y, 0);
      mesh.visible = false;
      _group.add(mesh);
      stepTokens.push(mesh);
    }
    _tokenMesh.push(stepTokens);

    // vertical link line from spine up to the step's token column
    const linkGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, 0, 0), new THREE.Vector3(x, 0.4 + (MAX_TOKENS - 1) * TOKEN_GAP, 0),
    ]);
    const linkMat = new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.25 });
    const link = new THREE.Line(linkGeo, linkMat);
    link.visible = false;
    _group.add(link);
    _stepLinks.push(link);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.26, 1),
    new THREE.MeshStandardMaterial({ color: C_ACCEPT, emissive: C_ACCEPT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -0.6, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSpecdecode(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.draftLen    = typeof j.draft_len              === "number" ? j.draft_len              : null;
  S.trials      = typeof j.trials                 === "number" ? j.trials                 : null;
  S.acceptRate  = typeof j.acceptance_rate        === "number" ? j.acceptance_rate        : null;
  S.meanAccept  = typeof j.mean_accept_len        === "number" ? j.mean_accept_len        : null;
  S.meanTokens  = typeof j.mean_tokens_per_step   === "number" ? j.mean_tokens_per_step   : null;
  S.speedup     = typeof j.speedup_factor         === "number" ? j.speedup_factor         : null;
  S.stepLengths = Array.isArray(j.per_step_accept_lengths) ? j.per_step_accept_lengths : null;
  S.lossless    = typeof j.lossless               === "boolean" ? j.lossless              : null;

  _updatePipeline();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the token-tree / pipeline from live data
// =============================================================================
function _updatePipeline() {
  const live = S.state === "live";
  const draftLen = live && S.draftLen ? Math.min(S.draftLen, MAX_TOKENS) : 0;
  const steps = live && S.stepLengths && S.stepLengths.length
    ? S.stepLengths.slice(0, MAX_STEPS)
    : [];

  for (let s = 0; s < MAX_STEPS; s++) {
    const acceptedLen = s < steps.length ? steps[s] : -1;
    const showStep = live && s < steps.length && draftLen > 0;
    _stepLinks[s].visible = showStep;

    for (let t = 0; t < MAX_TOKENS; t++) {
      const mesh = _tokenMesh[s][t];
      if (!showStep || t >= draftLen) {
        mesh.visible = false;
        continue;
      }
      mesh.visible = true;
      const accepted = t < acceptedLen;
      const color = accepted ? C_ACCEPT : C_REJECT;
      mesh.material.color.setHex(color);
      mesh.material.emissive.setHex(color);
      mesh.material.emissiveIntensity = accepted ? 0.55 : 0.12;
      mesh.material.opacity = accepted ? 0.95 : 0.35;
      // rejected tokens (and everything after the first rejection) sit slightly
      // recessed in Z to visually read as "pruned" from the accepted path.
      mesh.position.z = accepted ? 0 : -0.35;
    }
  }

  // spine + marker degrade to grey when not live
  _spine.material.color.setHex(live ? C_DRAFT : C_DIM);
  _spine.material.opacity = live ? 0.45 : 0.15;

  if (_marker) {
    if (live && S.speedup != null) {
      _marker.material.color.setHex(C_ACCEPT);
      _marker.material.emissive.setHex(C_ACCEPT);
      _marker.material.opacity = 0.85;
      // marker rides along X proportional to speedup_factor (visual "throughput" cue)
      const x = Math.min(STEP_LEN * (MAX_STEPS - 1), (S.speedup || 1) * STEP_LEN * 0.9);
      _marker.position.set(x, -0.6, 0);
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
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "draft-then-verify", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A small <b>draft</b> model proposes several tokens per step; the <b>target</b> model ' +
    'verifies them all in one parallel pass, accepting via rejection sampling ' +
    '(accept if p<sub>draft</sub> \u2264 p<sub>target</sub>, else w.p. p<sub>target</sub>/p<sub>draft</sub>). ' +
    'Output distribution is <b>lossless</b> \u2014 identical to plain autoregressive decoding, just faster. ' +
    'Honesty label <b>MODELED</b> (deterministic accept/reject simulation; NOT Medusa/EAGLE). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "self-speculative decoding";
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

  grid.appendChild(kpiRow("sd-draftlen", "draft_len (\u03b3 proposed/step)"));
  grid.appendChild(kpiRow("sd-trials",   "trials simulated"));
  grid.appendChild(kpiRow("sd-accrate",  "acceptance_rate \u2014 MODELED"));
  grid.appendChild(kpiRow("sd-meanacc",  "mean accepted tokens/step"));
  grid.appendChild(kpiRow("sd-speedup",  "speedup_factor \u2014 MODELED"));
  grid.appendChild(kpiRow("sd-lossless", "lossless?"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Leviathan et al. arXiv:2211.17192 (speculative decoding) \u00b7 Medusa github.com/FasterDecoding/Medusa \u00b7 EAGLE arXiv:2401.15077. MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "sd-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const g       = S.draftLen   != null ? String(S.draftLen) : "loading\u2026";
  const accPct  = S.acceptRate != null ? (S.acceptRate * 100).toFixed(1) + "%" : "loading\u2026";
  const speedup = S.speedup    != null ? S.speedup.toFixed(2) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of generating one word at a time, a small, cheap " +
    "\u201cdraft\u201d model quickly guesses <b>" + g + " words ahead</b>. The big \u201ctarget\u201d " +
    "model then checks all of those guesses <i>at once</i> and keeps every guess it agrees with " +
    "(here, about <b>" + accPct + "</b> of guesses survive). Because checking a whole batch of " +
    "guesses costs about the same as generating one word normally, this yields roughly a <b>" +
    speedup + " speedup</b> in tokens produced per expensive model pass \u2014 with " +
    "<i>zero change</i> to what the model actually outputs (mathematically lossless, per " +
    "Leviathan et al. 2023). Plain: same answer, produced faster. This view is a <b>MODELED</b> " +
    "closed-form simulation of the accept/reject math, not a run of Medusa or EAGLE.";
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
  _set("sd-draftlen", t || (S.draftLen != null ? String(S.draftLen) : "\u2014"));
  _set("sd-trials",   t || (S.trials   != null ? String(S.trials)   : "\u2014"));
  _set("sd-accrate",  t || pct(S.acceptRate, 2));
  _set("sd-meanacc",  t || fx(S.meanAccept, 3));
  _set("sd-speedup",  t || (S.speedup != null ? S.speedup.toFixed(3) + "\u00d7" : "\u2014"));
  _set("sd-lossless", t || (S.lossless === true ? "yes (rejection-sampling identity)" : S.lossless === false ? "no" : "\u2014"));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "draft-then-verify" });
  if (_plain) _applyPlain();
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
  _floor = null; _spine = null; _tokenMesh = []; _stepLinks = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.draftLen = S.trials = S.acceptRate = null;
  S.meanAccept = S.meanTokens = S.speedup = S.stepLengths = S.lossless = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
