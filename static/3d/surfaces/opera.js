// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/opera.js — OPERA (PERPLEXITY-REWARD REFLECTIVE ALIGNMENT) organ for
// the holographic frontier ring (Wenxuan Jiang et al., arXiv:2606.25757).
// Renders the intrinsic perplexity-reward MECHANISM vs a noisy LLM-judge as
// three live panels:
//   (1) PERPLEXITY CURVES — per-trace running-perplexity lines; the drops at
//       reflective steps are where the OPERA intrinsic reward is accrued;
//   (2) REWARD-CORRELATION BARS — Pearson correlation of the OPERA reward vs
//       the noisy-judge reward with the ground-truth logical-consistency label
//       (OPERA correlates; judge does not);
//   (3) REWARD-STABILITY BARS — variance of the OPERA reward vs the judge
//       reward (the judge is the taller/unstable bar; higher = worse).
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/opera/reward. Honesty label "MODELED" is read VERBATIM from
// the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors keyless.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   traces, steps, reflective_steps[...], opera_reward, opera_reward_variance,
//   judge_reward, judge_reward_variance, correlation_opera, correlation_judge,
//   consistency_rate, ppl_curves_head[[...]]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real):
//   OPERA: Aligning Open-Ended Reasoning via Objective Perplexity-based
//     Reinforcement Learning — Wenxuan Jiang et al. arXiv:2606.25757
//     https://arxiv.org/abs/2606.25757
//
// HONESTY LABELS: MODELED (deterministic reproduction of the intrinsic
//   perplexity-reward MECHANISM on toy synthetic reasoning traces; NOT a trained
//   model; trains nothing; no real RL rollout; the reward correlations and
//   variances are MEASURED; NEVER-CLAIMED-AS OPERA's Qwen3-8B SOTA or 20k
//   dataset). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "opera";
const TITLE = "OPERA Perplexity-Reward Alignment";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/opera/reward?seed=42&traces=8&steps=12";

// data-viz hues — purple BANNED
const C_OPERA  = 0x3af4c8;  // proof-teal   (OPERA intrinsic reward / correlation)
const C_JUDGE  = 0x5b8dee;  // lattice-blue (noisy-judge reward / correlation)
const C_CURVE  = 0x8a6bff;  // violet-blue  (perplexity curves)
const C_REFL   = 0x3af4c8;  // proof-teal   (reflective-step markers)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ZERO   = 0x5a6570;  // grey (near-zero)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const CURVE_SPAN = 5.0;    // world width of a perplexity curve
const CURVE_MAXN = 6;      // max curves rendered (matches head trim)
const CURVE_MAXP = 64;     // max points per curve
const BAR_W      = 0.8;    // reward-bar width

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _curveGroup = null;
let _curves     = [];     // Array<THREE.Line>
let _reflGroup  = null;
let _reflMarks  = [];     // Array<THREE.Mesh> — reflective-step markers
let _barGroup   = null;
let _barCorrOpera = null; // correlation(OPERA, label)
let _barCorrJudge = null; // correlation(judge, label)
let _barVarOpera  = null; // variance(OPERA reward)
let _barVarJudge  = null; // variance(judge reward)

// live state
const S = {
  label:       null,
  traces:      null,
  steps:       null,
  reflective:  null,   // reflective_steps
  operaReward: null,   // opera_reward
  operaVar:    null,   // opera_reward_variance
  judgeReward: null,   // judge_reward
  judgeVar:    null,   // judge_reward_variance
  corrOpera:   null,   // correlation_opera
  corrJudge:   null,   // correlation_judge
  consRate:    null,   // consistency_rate
  pplCurves:   null,   // Array<Array<number>>
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(1.5, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCurves();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onOpera, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

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

// Pre-allocate CURVE_MAXN perplexity lines (each CURVE_MAXP points) and a pool
// of reflective-step marker cubes; positions/visibility updated in place.
function _buildCurves() {
  const THREE = _THREE;
  _curveGroup = new THREE.Group();
  _curveGroup.position.set(-2.6, 0.05, 2.4);
  _group.add(_curveGroup);

  for (let i = 0; i < CURVE_MAXN; i++) {
    const positions = new Float32Array(CURVE_MAXP * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setDrawRange(0, 0);
    const line = new THREE.Line(
      geo,
      new THREE.LineBasicMaterial({ color: C_CURVE, transparent: true, opacity: 0.0 }),
    );
    line.visible = false;
    _curveGroup.add(line);
    _curves.push(line);
  }

  _reflGroup = new THREE.Group();
  _curveGroup.add(_reflGroup);
  const markGeo = new THREE.SphereGeometry(0.055, 8, 8);
  // pool: up to CURVE_MAXN curves * 6 reflective markers
  for (let i = 0; i < CURVE_MAXN * 6; i++) {
    const m = new THREE.Mesh(
      markGeo,
      new THREE.MeshStandardMaterial({ color: C_REFL, emissive: C_REFL, emissiveIntensity: 0.5, transparent: true, opacity: 0.0 }),
    );
    m.visible = false;
    _reflGroup.add(m);
    _reflMarks.push(m);
  }
}

function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(4.4, 0, 0.0);
  _group.add(_barGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  function mkBar(x, color) {
    const b = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
    );
    b.position.set(x, 0.5, 0);
    _barGroup.add(b);
    return b;
  }

  // correlation pair (front row) and variance pair (back row)
  _barCorrOpera = mkBar(0.0, C_OPERA);
  _barCorrJudge = mkBar(1.2, C_JUDGE);
  _barVarOpera  = mkBar(0.0, C_OPERA); _barVarOpera.position.z = 1.6;
  _barVarJudge  = mkBar(1.2, C_JUDGE); _barVarJudge.position.z = 1.6;
}

// =============================================================================
// live data handler
// =============================================================================
function _onOpera(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.traces      = typeof src.traces                === "number" ? src.traces                : null;
  S.steps       = typeof src.steps                 === "number" ? src.steps                 : null;
  S.reflective  = Array.isArray(src.reflective_steps) ? src.reflective_steps               : null;
  S.operaReward = typeof src.opera_reward          === "number" ? src.opera_reward          : null;
  S.operaVar    = typeof src.opera_reward_variance === "number" ? src.opera_reward_variance : null;
  S.judgeReward = typeof src.judge_reward          === "number" ? src.judge_reward          : null;
  S.judgeVar    = typeof src.judge_reward_variance === "number" ? src.judge_reward_variance : null;
  S.corrOpera   = typeof src.correlation_opera     === "number" ? src.correlation_opera     : null;
  S.corrJudge   = typeof src.correlation_judge     === "number" ? src.correlation_judge     : null;
  S.consRate    = typeof src.consistency_rate      === "number" ? src.consistency_rate      : null;

  S.pplCurves   = Array.isArray(src.ppl_curves_head) ? src.ppl_curves_head : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateCurves();
  _updateBars();
}

// Draw each perplexity curve as a polyline (x = step, y = -log(ppl) scaled so
// LOWER perplexity is HIGHER on screen -> visible drops), and place reflective
// markers at the reflective-step positions.
function _updateCurves() {
  const live = S.state === "live";
  const curves = (live && S.pplCurves) ? S.pplCurves : [];
  const reflect = (live && Array.isArray(S.reflective)) ? S.reflective : [];

  // global perplexity range for normalization across visible curves
  let pmin = Infinity, pmax = -Infinity;
  for (let i = 0; i < curves.length; i++) {
    for (let t = 0; t < curves[i].length; t++) {
      const v = curves[i][t];
      if (v < pmin) pmin = v;
      if (v > pmax) pmax = v;
    }
  }
  if (!isFinite(pmin) || !isFinite(pmax) || pmax <= pmin) { pmin = 0.0; pmax = 1.0; }
  const span = (pmax - pmin) || 1.0;

  let markIdx = 0;
  for (let i = 0; i < CURVE_MAXN; i++) {
    const line = _curves[i];
    const curve = curves[i];
    if (!live || !curve || curve.length < 2) { line.visible = false; continue; }

    const n = Math.min(curve.length, CURVE_MAXP);
    const pos = line.geometry.attributes.position.array;
    const dx = CURVE_SPAN / (n - 1);
    const z = i * 0.55;
    for (let t = 0; t < n; t++) {
      // height: lower perplexity -> higher; so a DROP rises on screen
      const h = 0.15 + 2.4 * (1.0 - (curve[t] - pmin) / span);
      pos[t * 3 + 0] = t * dx;
      pos[t * 3 + 1] = h;
      pos[t * 3 + 2] = z;
    }
    line.geometry.attributes.position.needsUpdate = true;
    line.geometry.setDrawRange(0, n);
    line.geometry.computeBoundingSphere();
    line.visible = true;
    line.material.color.setHex(C_CURVE);
    line.material.opacity = 0.85;

    // reflective-step markers on this curve
    for (let k = 0; k < reflect.length; k++) {
      const t = reflect[k];
      if (t < 0 || t >= n) continue;
      const mk = _reflMarks[markIdx++];
      if (!mk) break;
      const h = 0.15 + 2.4 * (1.0 - (curve[t] - pmin) / span);
      mk.position.set(t * dx, h, z);
      mk.visible = true;
      mk.material.color.setHex(C_REFL);
      mk.material.emissive.setHex(C_REFL);
      mk.material.opacity = 0.95;
    }
  }
  // hide unused markers
  for (let i = markIdx; i < _reflMarks.length; i++) _reflMarks[i].visible = false;
}

// correlation bars: height ∝ correlation (in [-1,1] mapped to positive height so
// OPERA's high correlation towers over the judge). variance bars: height ∝
// variance (judge is the taller = more unstable).
function _updateBars() {
  const live = S.state === "live";

  function setCorrBar(mesh, corr, color) {
    if (!mesh) return;
    if (!live || corr == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.05; mesh.position.y = 0.025;
      return;
    }
    const h = Math.max(0.06, ((corr + 1.0) / 2.0) * 3.0);
    mesh.scale.y = h; mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.42;
    mesh.material.opacity = 0.92;
  }

  setCorrBar(_barCorrOpera, S.corrOpera, C_OPERA);
  setCorrBar(_barCorrJudge, S.corrJudge, C_JUDGE);

  // variance bars — normalized to the larger of the two so the taller (judge)
  // is clearly the unstable one.
  const vmax = Math.max(
    (S.operaVar != null ? S.operaVar : 0),
    (S.judgeVar != null ? S.judgeVar : 0),
    1e-9,
  );
  function setVarBar(mesh, v, color) {
    if (!mesh) return;
    if (!live || v == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.05; mesh.position.y = 0.025;
      return;
    }
    const h = Math.max(0.06, (v / vmax) * 3.0);
    mesh.scale.y = h; mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.42;
    mesh.material.opacity = 0.92;
  }
  setVarBar(_barVarOpera, S.operaVar, C_OPERA);
  setVarBar(_barVarJudge, S.judgeVar, C_JUDGE);
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
    'OPERA replaces an unreliable <b>LLM-as-a-judge</b> reward (prone to stylistic bias and positional ' +
    'inconsistency) with an <b>intrinsic reward from perplexity dynamics</b>: the uncertainty reduction ' +
    '(perplexity <b>drop</b>) at <b>critical reflective states</b> of a reasoning trace. Panels: per-trace ' +
    'perplexity curves (drops at reflective steps = where reward accrues), reward\u2013correlation bars ' +
    '(OPERA vs noisy judge against the ground-truth logical-consistency label), and reward-stability bars ' +
    '(variance; the judge is the taller/unstable one). Honesty label <b>MODELED</b> (deterministic mechanism ' +
    'reproduction on toy traces; trains nothing). 0 runtime CDN.';
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
  nm.textContent = "opera \u00b7 intrinsic perplexity reward";
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

  grid.appendChild(kpiRow("op-dims",     "traces \u00d7 steps"));
  grid.appendChild(kpiRow("op-refl",     "reflective steps"));
  grid.appendChild(kpiRow("op-oreward",  "OPERA reward \u2014 mean (MEASURED)"));
  grid.appendChild(kpiRow("op-jreward",  "judge reward \u2014 mean (MEASURED)"));
  grid.appendChild(kpiRow("op-corropera","corr(OPERA, consistency)"));
  grid.appendChild(kpiRow("op-corrjudge","corr(judge, consistency)"));
  grid.appendChild(kpiRow("op-ovar",     "OPERA reward variance"));
  grid.appendChild(kpiRow("op-jvar",     "judge reward variance (higher=unstable)"));
  grid.appendChild(kpiRow("op-cons",     "consistency rate (ground truth)"));
  grid.appendChild(kpiRow("op-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "OPERA \u2014 Wenxuan Jiang et al., \u201cAligning Open-Ended Reasoning via Objective Perplexity-based Reinforcement Learning\u201d arXiv:2606.25757 (arxiv.org/abs/2606.25757). MODELED \u00b7 intrinsic perplexity-reward mechanism demo on toy traces, not a trained model or real RL rollout.";
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
  pd.id = "op-plain";
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
  const co = S.corrOpera != null ? S.corrOpera.toFixed(2) : "loading\u2026";
  const cj = S.corrJudge != null ? S.corrJudge.toFixed(2) : "loading\u2026";
  const jv = S.judgeVar  != null ? S.judgeVar.toFixed(2)  : "loading\u2026";
  const ov = S.operaVar  != null ? S.operaVar.toFixed(2)  : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> To train a model on open-ended tasks (like creative writing) you need a " +
    "<b>reward</b> \u2014 a score for how good an answer is. A common trick is to ask another AI to be the " +
    "\u201cjudge,\u201d but judges are swayed by <b>style and ordering</b>, so their scores are noisy and " +
    "unreliable. OPERA uses a signal from <b>inside the model</b> instead: as a good reasoning trace works " +
    "toward a sound conclusion, the model becomes <b>more certain</b> \u2014 its \u201cperplexity\u201d drops " +
    "at the moments it reflects. OPERA rewards exactly those confidence gains. Here, on toy traces with a " +
    "known right/wrong label, OPERA\u2019s reward lines up with true logical consistency (correlation \u2248 <b>" +
    co + "</b>) while the noisy judge does not (\u2248 <b>" + cj + "</b>), and the judge\u2019s reward is far " +
    "more erratic (variance <b>" + jv + "</b> vs OPERA\u2019s <b>" + ov + "</b>). This view is a <b>MODELED</b> " +
    "deterministic reproduction of that reward MECHANISM on tiny synthetic traces \u2014 it <b>trains no " +
    "model</b> and runs no reinforcement learning. The paper\u2019s headline that OPERA on <b>Qwen3-8B</b> " +
    "reaches SOTA and rivals Gemini2.5 / MiniMax-M2.5 is a <b>claim about real training runs</b> " +
    "the estate does not independently verify.";
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
  _set("op-dims",      t || ((S.traces != null && S.steps != null) ? (S.traces + " \u00d7 " + S.steps) : "\u2014"));
  _set("op-refl",      t || (Array.isArray(S.reflective) ? ("[" + S.reflective.join(", ") + "]") : "\u2014"));
  _set("op-oreward",   t || fx(S.operaReward, 4));
  _set("op-jreward",   t || fx(S.judgeReward, 4));
  _set("op-corropera", t || fx(S.corrOpera, 4));
  _set("op-corrjudge", t || fx(S.corrJudge, 4));
  _set("op-ovar",      t || fx(S.operaVar, 4));
  _set("op-jvar",      t || fx(S.judgeVar, 4));
  _set("op-cons",      t || (S.consRate != null ? (100.0 * S.consRate).toFixed(1) + "%" : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("op-label",     t || (S.label || "MODELED"));
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
  _curveGroup = null; _curves = [];
  _reflGroup = null; _reflMarks = [];
  _barGroup = null;
  _barCorrOpera = _barCorrJudge = _barVarOpera = _barVarJudge = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.traces = S.steps = S.reflective = null;
  S.operaReward = S.operaVar = S.judgeReward = S.judgeVar = null;
  S.corrOpera = S.corrJudge = S.consRate = null;
  S.pplCurves = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
