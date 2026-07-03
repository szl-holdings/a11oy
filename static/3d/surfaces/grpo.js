// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/grpo.js — GRPO REWARD DYNAMICS organ for the holographic frontier
// ring (Group Relative Policy Optimization, critic-free RL post-training).
// Renders each training step's sampled reward GROUP as points scattering
// around a group-mean plane; each point's height above/below the plane is
// its group-normalized advantage (proof-teal above the mean, grey below),
// a KL-tether line ties the group to a reference-policy anchor, and a HUD
// tracks mean_reward + kl_divergence + final_policy_score climbing over the
// run, from the live snapshot at /api/killinchu/v1/grpo/reward-dynamics.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed
// as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   group_size, steps, kl_beta, clip_eps, mean_reward, mean_advantage,
//   kl_divergence, clip_fraction, final_policy_score, reward_trajectory[],
//   kl_trajectory[], policy_score_trajectory[], advantage_trajectory[],
//   clip_fraction_trajectory[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   GRPO (group-relative advantage + PPO-clip + KL-penalty arithmetic
//   simulated here):
//     Shao et al. 2024, "DeepSeekMath", arXiv:2402.03300
//     https://arxiv.org/abs/2402.03300
//   DeepSeek-R1 (large-scale RL post-training using GRPO — reference only):
//     DeepSeek-AI 2025, arXiv:2501.12948
//     https://arxiv.org/abs/2501.12948
//
// HONESTY LABELS: MODELED (deterministic simulation of GRPO group-advantage +
//   PPO-clip + KL arithmetic; NOT a trained policy; NEVER-CLAIMED-AS
//   DeepSeek-R1/DeepSeekMath training). Read verbatim from JSON; never
//   upgraded here.
// COLOURS: lattice-blue 0x5b8dee (group-mean plane / spine), proof-teal
//   0x3af4c8 (above-mean / positive-advantage samples, HUD accent), greys
//   (below-mean / degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "grpo";
const TITLE = "GRPO Reward Dynamics · Group-Relative Advantage (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the GRPO organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/grpo/reward-dynamics?seed=42&group_size=8&steps=200&kl_beta=0.04";

// data-viz hues — purple BANNED
const C_PLANE   = 0x5b8dee;  // lattice-blue (group-mean plane / spine)
const C_ABOVE   = 0x3af4c8;  // proof-teal (above-mean / positive-advantage sample, HUD accent)
const C_BELOW   = 0x5a6570;  // grey (below-mean / negative-advantage sample)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour
const C_KL      = 0x8a6bff;  // NOTE: reserved slot unused — see doctrine note below

// Doctrine v11 colour scope: purple (any hue) is BANNED — the KL-tether line
// below intentionally uses lattice-blue (dimmed), never the 0x8a6bff constant
// above. The constant is retained ONLY as a documented "never use" marker so
// future edits do not accidentally reach for a purple hue for the tether.
const C_TETHER  = 0x5b8dee;  // KL-tether line — lattice-blue, dimmed via opacity

// group/step scatter layout geometry
const STEP_LEN    = 1.9;   // world-units between steps along X (training-step axis)
const GROUP_SPAN  = 3.2;   // world-units spread of a group across Z (per-sample jitter)
const MAX_STEPS   = 14;    // number of recent steps rendered along the axis
const MAX_SAMPLES = 16;    // cap on group_size rendered per step (perf)
const ADV_SCALE   = 1.6;   // world-units of height per unit of |advantage|

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _plane      = null;               // THREE.Mesh — translucent group-mean plane
let _spine      = null;               // THREE.Line — training-step axis
let _sampleMesh = [];                 // Array<Array<THREE.Mesh>> — [step][sampleIdx]
let _tethers    = [];                 // Array<THREE.Line> — KL-tether per step
let _marker     = null;               // THREE.Mesh — HUD "policy_score" pulsing marker

// live state
const S = {
  label:        null,
  groupSize:    null,   // group_size
  steps:        null,   // steps
  klBeta:       null,   // kl_beta
  clipEps:      null,   // clip_eps
  meanReward:   null,   // mean_reward
  meanAdv:      null,   // mean_advantage
  klDiv:        null,   // kl_divergence
  clipFrac:     null,   // clip_fraction
  policyScore:  null,   // final_policy_score
  rewardTraj:   null,   // reward_trajectory[]
  klTraj:       null,   // kl_trajectory[]
  scoreTraj:    null,   // policy_score_trajectory[]
  advTraj:      null,   // advantage_trajectory[]
  clipTraj:     null,   // clip_fraction_trajectory[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 7, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(6, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlaneAndSpine();
  _buildScatterGrid();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onGrpo, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Group-mean plane: a thin, translucent strip along the training-step axis at
// y=0 representing "the group mean" for each step — advantage is literally
// the height of each sample above/below this plane.
function _buildPlaneAndSpine() {
  const THREE = _THREE;

  const planeGeo = new THREE.PlaneGeometry(STEP_LEN * (MAX_STEPS - 1) + 1.4, GROUP_SPAN + 0.6);
  const planeMat = new THREE.MeshBasicMaterial({
    color: C_PLANE, transparent: true, opacity: 0.08, side: THREE.DoubleSide,
  });
  _plane = new THREE.Mesh(planeGeo, planeMat);
  _plane.rotation.x = -Math.PI / 2;
  _plane.position.set((STEP_LEN * (MAX_STEPS - 1)) / 2, 0, 0);
  _group.add(_plane);

  const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(STEP_LEN * (MAX_STEPS - 1) + 1, 0, 0)];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: C_PLANE, transparent: true, opacity: 0.5 });
  _spine = new THREE.Line(geo, mat);
  _group.add(_spine);
}

// Pre-allocate a fixed grid of sample meshes: MAX_STEPS steps x MAX_SAMPLES
// samples per step, plus one KL-tether line per step. We toggle
// visibility/color/position in-place as live data arrives (no per-poll
// geometry churn).
function _buildScatterGrid() {
  const THREE = _THREE;

  const sampleGeo = new THREE.SphereGeometry(0.16, 12, 10);
  for (let s = 0; s < MAX_STEPS; s++) {
    const stepSamples = [];
    const x = s * STEP_LEN;
    for (let t = 0; t < MAX_SAMPLES; t++) {
      // deterministic-looking jitter across Z for visual spread (purely
      // layout, not data — actual height/color comes from live advantage)
      const z = (((t * 2654435761) % 1000) / 1000 - 0.5) * GROUP_SPAN;
      const mesh = new THREE.Mesh(
        sampleGeo,
        new THREE.MeshStandardMaterial({ color: C_ABOVE, emissive: C_ABOVE, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
      );
      mesh.position.set(x, 0, z);
      mesh.visible = false;
      _group.add(mesh);
      stepSamples.push(mesh);
    }
    _sampleMesh.push(stepSamples);

    // KL-tether: vertical line from the plane up to a small anchor point,
    // whose height encodes that step's KL-divergence-vs-reference estimate.
    const tetherGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, 0, GROUP_SPAN / 2 + 0.4), new THREE.Vector3(x, 0.01, GROUP_SPAN / 2 + 0.4),
    ]);
    const tetherMat = new THREE.LineBasicMaterial({ color: C_TETHER, transparent: true, opacity: 0.55 });
    const tether = new THREE.Line(tetherGeo, tetherMat);
    tether.visible = false;
    _group.add(tether);
    _tethers.push(tether);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.26, 1),
    new THREE.MeshStandardMaterial({ color: C_ABOVE, emissive: C_ABOVE, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -0.6, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onGrpo(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.groupSize   = typeof j.group_size          === "number" ? j.group_size          : null;
  S.steps       = typeof j.steps               === "number" ? j.steps               : null;
  S.klBeta      = typeof j.kl_beta             === "number" ? j.kl_beta             : null;
  S.clipEps     = typeof j.clip_eps            === "number" ? j.clip_eps            : null;
  S.meanReward  = typeof j.mean_reward         === "number" ? j.mean_reward         : null;
  S.meanAdv     = typeof j.mean_advantage      === "number" ? j.mean_advantage      : null;
  S.klDiv       = typeof j.kl_divergence       === "number" ? j.kl_divergence       : null;
  S.clipFrac    = typeof j.clip_fraction       === "number" ? j.clip_fraction       : null;
  S.policyScore = typeof j.final_policy_score  === "number" ? j.final_policy_score  : null;
  S.rewardTraj  = Array.isArray(j.reward_trajectory)       ? j.reward_trajectory       : null;
  S.klTraj      = Array.isArray(j.kl_trajectory)           ? j.kl_trajectory           : null;
  S.scoreTraj   = Array.isArray(j.policy_score_trajectory) ? j.policy_score_trajectory : null;
  S.advTraj     = Array.isArray(j.advantage_trajectory)    ? j.advantage_trajectory    : null;
  S.clipTraj    = Array.isArray(j.clip_fraction_trajectory)? j.clip_fraction_trajectory: null;

  _updateScatter();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the group scatter / KL-tethers from live data
// =============================================================================
function _updateScatter() {
  const live = S.state === "live";
  const groupSize = live && S.groupSize ? Math.min(S.groupSize, MAX_SAMPLES) : 0;

  // Use the tail of each trajectory (most recent MAX_STEPS points) so the
  // pipeline always shows the latest training window.
  const rewardTail = live && S.rewardTraj && S.rewardTraj.length ? S.rewardTraj.slice(-MAX_STEPS) : [];
  const advTail     = live && S.advTraj    && S.advTraj.length    ? S.advTraj.slice(-MAX_STEPS)    : [];
  const klTail      = live && S.klTraj     && S.klTraj.length     ? S.klTraj.slice(-MAX_STEPS)     : [];
  const nSteps = rewardTail.length;

  for (let s = 0; s < MAX_STEPS; s++) {
    const showStep = live && s < nSteps && groupSize > 0;
    const meanAdvAtStep = showStep ? advTail[s] : 0;
    const klAtStep = showStep ? klTail[s] : 0;

    _tethers[s].visible = showStep;
    if (showStep) {
      const tetherHeight = Math.min(2.4, 0.3 + klAtStep * 6.0);
      const pos = _tethers[s].geometry.attributes.position;
      pos.setXYZ(1, s * STEP_LEN, tetherHeight, GROUP_SPAN / 2 + 0.4);
      pos.needsUpdate = true;
      _tethers[s].material.color.setHex(C_TETHER);
      _tethers[s].material.opacity = 0.55;
    }

    for (let t = 0; t < MAX_SAMPLES; t++) {
      const mesh = _sampleMesh[s][t];
      if (!showStep || t >= groupSize) {
        mesh.visible = false;
        continue;
      }
      mesh.visible = true;
      // per-sample advantage sign alternates deterministically around the
      // step's mean |advantage| so the cloud visibly straddles the plane —
      // exact per-sample values are not re-transmitted by the endpoint
      // (only the step aggregate is), so this renders the aggregate
      // magnitude as a symmetric scatter, which is an honest visual proxy.
      const sign = (t % 2 === 0) ? 1 : -1;
      const jitter = 0.65 + 0.35 * (((t * 2246822519) % 1000) / 1000);
      const height = sign * meanAdvAtStep * ADV_SCALE * jitter;
      mesh.position.y = height;

      const above = height >= 0;
      const color = above ? C_ABOVE : C_BELOW;
      mesh.material.color.setHex(color);
      mesh.material.emissive.setHex(color);
      mesh.material.emissiveIntensity = above ? 0.5 : 0.15;
      mesh.material.opacity = above ? 0.92 : 0.45;
    }
  }

  // plane + spine + marker degrade to grey when not live
  _plane.material.color.setHex(live ? C_PLANE : C_DIM);
  _plane.material.opacity = live ? 0.08 : 0.03;
  _spine.material.color.setHex(live ? C_PLANE : C_DIM);
  _spine.material.opacity = live ? 0.5 : 0.15;

  if (_marker) {
    if (live && S.policyScore != null) {
      _marker.material.color.setHex(C_ABOVE);
      _marker.material.emissive.setHex(C_ABOVE);
      _marker.material.opacity = 0.85;
      // marker rides along X proportional to final_policy_score (visual
      // "convergence" cue — climbs toward the end of the pipeline as the
      // policy score approaches 1.0)
      const x = Math.min(STEP_LEN * (MAX_STEPS - 1), (S.policyScore || 0) * STEP_LEN * (MAX_STEPS - 1));
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
    'GRPO samples a <b>group</b> of completions per step and normalizes each reward against ' +
    'the group\'s own mean/std \u2014 <b>no critic network</b> needed. The policy is updated via a ' +
    'PPO-clip surrogate (\u03b5=0.2) on that group-relative advantage, plus a KL penalty vs a fixed ' +
    'reference policy. Honesty label <b>MODELED</b> (deterministic group-advantage + PPO-clip + KL ' +
    'arithmetic; NOT a trained policy). 0 runtime CDN.';
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
  nm.textContent = "GRPO reward dynamics";
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

  grid.appendChild(kpiRow("gr-groupsize", "group_size (G samples/step)"));
  grid.appendChild(kpiRow("gr-steps",     "steps simulated"));
  grid.appendChild(kpiRow("gr-klbeta",    "kl_beta (KL-penalty coeff.)"));
  grid.appendChild(kpiRow("gr-clipeps",   "clip_eps (PPO-clip \u03b5)"));
  grid.appendChild(kpiRow("gr-reward",    "mean_reward \u2014 MODELED"));
  grid.appendChild(kpiRow("gr-adv",       "mean_advantage \u2014 MODELED"));
  grid.appendChild(kpiRow("gr-kl",        "kl_divergence (k3) \u2014 MODELED"));
  grid.appendChild(kpiRow("gr-clipfrac",  "clip_fraction \u2014 MODELED"));
  grid.appendChild(kpiRow("gr-score",     "final_policy_score \u2014 MODELED"));
  grid.appendChild(kpiRow("gr-label",     "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Shao et al. (DeepSeekMath GRPO) arXiv:2402.03300 \u00b7 DeepSeek-R1 arXiv:2501.12948. MODELED \u00b7 not claimed-as.";
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
  pd.id = "gr-plain";
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
  const g       = S.groupSize   != null ? String(S.groupSize) : "loading\u2026";
  const reward  = S.meanReward  != null ? (S.meanReward * 100).toFixed(1) + "%" : "loading\u2026";
  const score   = S.policyScore != null ? (S.policyScore * 100).toFixed(1) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of training a second, separate \u201ccritic\u201d network to judge how " +
    "good an answer is (as classic PPO does), GRPO just generates <b>" + g + " candidate answers</b> to the " +
    "same question and compares them <i>to each other</i> \u2014 the group's own average becomes the yardstick. " +
    "Answers better than the group average get reinforced; worse ones get discouraged. A safety clip keeps " +
    "any single update from swinging too far, and a KL \u201cleash\u201d keeps the model from drifting too far " +
    "from where it started. Over simulated training, the average reward per group reaches about <b>" + reward + "</b> " +
    "and a convergence proxy (<b>policy_score</b>) climbs to about <b>" + score + "</b>. This view is a <b>MODELED</b> " +
    "closed-form simulation of the group-advantage/PPO-clip/KL arithmetic from the DeepSeekMath paper, not a run of " +
    "DeepSeek-R1 or DeepSeekMath training.";
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
  _set("gr-groupsize", t || (S.groupSize != null ? String(S.groupSize) : "\u2014"));
  _set("gr-steps",     t || (S.steps     != null ? String(S.steps)     : "\u2014"));
  _set("gr-klbeta",    t || fx(S.klBeta, 4));
  _set("gr-clipeps",   t || fx(S.clipEps, 2));
  _set("gr-reward",    t || fx(S.meanReward, 4));
  _set("gr-adv",       t || fx(S.meanAdv, 4));
  _set("gr-kl",        t || fx(S.klDiv, 6));
  _set("gr-clipfrac",  t || pct(S.clipFrac, 2));
  _set("gr-score",     t || pct(S.policyScore, 2));
  // honesty label verbatim — never upgraded
  _set("gr-label", t || (S.label || "MODELED"));
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
  _floor = null; _plane = null; _spine = null; _sampleMesh = []; _tethers = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.groupSize = S.steps = S.klBeta = S.clipEps = null;
  S.meanReward = S.meanAdv = S.klDiv = S.clipFrac = S.policyScore = null;
  S.rewardTraj = S.klTraj = S.scoreTraj = S.advTraj = S.clipTraj = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
