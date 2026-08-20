// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/s3search.js — VERIFIER-GUIDED STRATIFIED SEARCH OVER DENOISING
// TRAJECTORIES (S³) organ for the holographic frontier ring. Renders a FRONTIER
// of candidate denoising trajectories that BRANCH into children each step and are
// PRUNED back to W survivors by a reference-free verifier + stratified resample —
// the S³ mechanism of spending test-time compute DURING denoising rather than only
// at the final output. A HUD compares final grammar-satisfaction quality + frontier
// diversity for {no-search, final-best-of-K, S³} at MATCHED toy compute. Honesty
// label "MODELED" is read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// Surface export shape (mirrors testtime.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   frontier_width, branch_factor, num_denoise_steps, verifier_weight, diversity_strata,
//   target, flop_proxy_budget, no_search{}, final_best_of_k{}, s3{}, s3_trajectory[],
//   quality_gap_s3_vs_bok
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   S³ (Stratified Scaling Search over denoising trajectories — the mechanism toy-modeled here):
//     Bilal, Mohsin, Umer, Aali, Khanzada, Rafique, He, Fox & Hougen 2026, arXiv:2604.06260
//     https://arxiv.org/abs/2604.06260
//
// HONESTY LABELS: MODELED (toy analytic sim of the mid-denoising stratified-search
//   MECHANISM; seeded toy denoiser + closed-form grammar-satisfaction verifier, not a
//   learned one; state-update counter, not real FLOPs; does NOT reproduce S³'s LLaDA-8B
//   benchmarks). Narrowest new-axis claim at the dllm+testtime+specdecode junction.
//   Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (frontier trajectories / spine), violet-blue 0x8a6bff
//   (branched children — data-viz only), proof-teal 0x3af4c8 (surviving/best trajectory /
//   HUD accent), greys (pruned trajectories / degraded state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "s3search";
const TITLE = "S³ · Verifier-Guided Stratified Search over Denoising Trajectories (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin). This keeps the
// s3search organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/s3search/search?seed=42&frontier_width=6&branch_factor=3&num_denoise_steps=8";

// data-viz hues — purple BANNED
const C_FRONTIER = 0x5b8dee;  // lattice-blue (frontier trajectory / spine)
const C_BRANCH   = 0x8a6bff;  // violet-blue (branched children — data-viz only)
const C_SURVIVE  = 0x3af4c8;  // proof-teal (surviving / best trajectory / HUD accent)
const C_PRUNE    = 0x5a6570;  // grey (pruned trajectory)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// frontier-branching layout geometry
const STEP_LEN   = 2.0;   // world-units between denoise steps along X
const LANE_GAP   = 0.95;  // world-units between frontier lanes (Y)
const MAX_STEPS  = 10;    // number of denoise steps rendered along the pipeline
const MAX_LANES  = 8;     // cap on frontier_width rendered (perf)
const MAX_CHILD  = 4;     // cap on branch_factor children rendered per node (perf)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor    = null;
let _spine    = null;                 // THREE.Line — denoise-step axis
let _nodeMesh = [];                   // Array<Array<THREE.Mesh>> — [step][lane] frontier survivors
let _childMesh = [];                  // Array<Array<THREE.Mesh>> — [step][childIdx] branched children
let _stepLinks = [];                  // Array<THREE.Line> — vertical link per step
let _marker   = null;                 // THREE.Mesh — HUD "current best" pulsing marker

// live state
const S = {
  label:      null,
  width:      null,   // frontier_width
  branch:     null,   // branch_factor
  steps:      null,   // num_denoise_steps
  vweight:    null,   // verifier_weight
  strata:     null,   // diversity_strata
  target:     null,   // target string
  budget:     null,   // flop_proxy_budget
  noSearch:   null,   // {quality, diversity, flops}
  finalBoK:   null,   // {quality, diversity, flops, k}
  s3:         null,   // {quality, diversity, flops}
  traj:       null,   // s3_trajectory[]
  gap:        null,   // quality_gap_s3_vs_bok
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 8, 19);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(8, 3, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildFrontier();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSearch, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed grid of node + child meshes. We toggle visibility /
// color / position in-place as live data arrives (no per-poll geometry churn).
function _buildFrontier() {
  const THREE = _THREE;

  // denoise-step spine along X
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(STEP_LEN * (MAX_STEPS - 1) + 1, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_FRONTIER, transparent: true, opacity: 0.45 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const nodeGeo  = new THREE.OctahedronGeometry(0.22, 0);
  const childGeo = new THREE.TetrahedronGeometry(0.14, 0);

  for (let s = 0; s < MAX_STEPS; s++) {
    const x = s * STEP_LEN;

    // surviving frontier nodes (lanes) for this step
    const laneNodes = [];
    for (let l = 0; l < MAX_LANES; l++) {
      const y = 0.5 + l * LANE_GAP;
      const mesh = new THREE.Mesh(
        nodeGeo,
        new THREE.MeshStandardMaterial({ color: C_FRONTIER, emissive: C_FRONTIER, emissiveIntensity: 0.3, transparent: true, opacity: 0.0 }),
      );
      mesh.position.set(x, y, 0);
      mesh.visible = false;
      _group.add(mesh);
      laneNodes.push(mesh);
    }
    _nodeMesh.push(laneNodes);

    // branched children (spread slightly in +Z) that get pruned each step
    const kids = [];
    for (let c = 0; c < MAX_LANES * MAX_CHILD; c++) {
      const mesh = new THREE.Mesh(
        childGeo,
        new THREE.MeshStandardMaterial({ color: C_BRANCH, emissive: C_BRANCH, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
      );
      mesh.visible = false;
      _group.add(mesh);
      kids.push(mesh);
    }
    _childMesh.push(kids);

    // vertical link line marking the step
    const linkGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, 0, 0), new THREE.Vector3(x, 0.5 + (MAX_LANES - 1) * LANE_GAP, 0),
    ]);
    const linkMat = new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.22 });
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
    new THREE.MeshStandardMaterial({ color: C_SURVIVE, emissive: C_SURVIVE, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -0.7, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSearch(j) {
  // read honesty label VERBATIM — never upgrade. Accept top-level 'label' OR
  // nested 'payload.label'.
  const rawLabel = (j && typeof j.label === "string") ? j.label
                 : (j && j.payload && typeof j.payload.label === "string") ? j.payload.label
                 : "MODELED";
  S.label    = String(rawLabel).toUpperCase();
  S.width    = typeof j.frontier_width    === "number" ? j.frontier_width    : null;
  S.branch   = typeof j.branch_factor     === "number" ? j.branch_factor     : null;
  S.steps    = typeof j.num_denoise_steps === "number" ? j.num_denoise_steps : null;
  S.vweight  = typeof j.verifier_weight   === "number" ? j.verifier_weight   : null;
  S.strata   = typeof j.diversity_strata  === "number" ? j.diversity_strata  : null;
  S.target   = typeof j.target            === "string" ? j.target            : null;
  S.budget   = typeof j.flop_proxy_budget === "number" ? j.flop_proxy_budget : null;
  S.noSearch = (j.no_search && typeof j.no_search === "object") ? j.no_search : null;
  S.finalBoK = (j.final_best_of_k && typeof j.final_best_of_k === "object") ? j.final_best_of_k : null;
  S.s3       = (j.s3 && typeof j.s3 === "object") ? j.s3 : null;
  S.traj     = Array.isArray(j.s3_trajectory) ? j.s3_trajectory : null;
  S.gap      = typeof j.quality_gap_s3_vs_bok === "number" ? j.quality_gap_s3_vs_bok : null;

  _updateFrontier();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the frontier branch/prune from live data
// =============================================================================
function _updateFrontier() {
  const live = S.state === "live";
  const traj = live && S.traj && S.traj.length ? S.traj.slice(0, MAX_STEPS) : [];
  const width = live && S.width ? Math.min(S.width, MAX_LANES) : 0;
  const branch = live && S.branch ? Math.min(S.branch, MAX_CHILD) : 0;

  for (let s = 0; s < MAX_STEPS; s++) {
    const row = s < traj.length ? traj[s] : null;
    const showStep = live && !!row && width > 0;
    _stepLinks[s].visible = showStep;

    // survivor nodes: brightness scales with the step's best/mean quality;
    // top survivor reads proof-teal, others lattice-blue.
    const survivors = row ? Math.min(row.survivors || width, MAX_LANES) : 0;
    const bestQ = row && typeof row.best_quality === "number" ? row.best_quality : 0;
    for (let l = 0; l < MAX_LANES; l++) {
      const mesh = _nodeMesh[s][l];
      if (!showStep || l >= survivors) { mesh.visible = false; continue; }
      mesh.visible = true;
      const isTop = (l === 0);
      const color = isTop ? C_SURVIVE : C_FRONTIER;
      mesh.material.color.setHex(color);
      mesh.material.emissive.setHex(color);
      mesh.material.emissiveIntensity = isTop ? 0.55 : 0.28;
      mesh.material.opacity = 0.55 + 0.4 * Math.max(0, Math.min(1, bestQ));
      mesh.position.z = 0;
    }

    // branched children: shown recessed in +Z as "expanded then pruned".
    const kids = _childMesh[s];
    const x = s * STEP_LEN;
    let ci = 0;
    for (let l = 0; l < MAX_LANES; l++) {
      for (let c = 0; c < MAX_CHILD; c++) {
        const mesh = kids[ci++];
        const showChild = showStep && l < survivors && c < branch;
        if (!showChild) { mesh.visible = false; continue; }
        mesh.visible = true;
        // most children are pruned (grey), one per lane "survives" (violet-blue)
        const kept = (c === 0);
        const color = kept ? C_BRANCH : C_PRUNE;
        mesh.material.color.setHex(color);
        mesh.material.emissive.setHex(color);
        mesh.material.emissiveIntensity = kept ? 0.35 : 0.1;
        mesh.material.opacity = kept ? 0.6 : 0.28;
        const y = 0.5 + l * LANE_GAP + (c + 1) * 0.28;
        mesh.position.set(x + 0.55, y, 0.8 + c * 0.25);
      }
    }
  }

  // spine + marker degrade to grey when not live
  _spine.material.color.setHex(live ? C_FRONTIER : C_DIM);
  _spine.material.opacity = live ? 0.45 : 0.15;

  if (_marker) {
    if (live && S.s3 && typeof S.s3.quality === "number") {
      _marker.material.color.setHex(C_SURVIVE);
      _marker.material.emissive.setHex(C_SURVIVE);
      _marker.material.opacity = 0.85;
      // marker rides along X proportional to how far denoising progressed
      const prog = traj.length / Math.max(1, MAX_STEPS);
      _marker.position.set(STEP_LEN * (MAX_STEPS - 1) * prog, -0.7, 0);
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
    chips: [{ label: "MODELED", text: "stratified search", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Spend test-time compute <b>during denoising</b>, not just at the final output. ' +
    'A <b>frontier</b> of W trajectories is expanded into B children each step, scored by a ' +
    '<b>reference-free verifier</b>, then <b>stratified-resampled</b> to W survivors ' +
    '(reward-tilt + diversity). At matched compute this beats final <b>best-of-K</b>. ' +
    'Honesty label <b>MODELED</b> (toy denoiser + closed-form grammar verifier; not S³). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "s3search";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:60%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("s3-params",  "W \u00d7 B \u00d7 steps"));
  grid.appendChild(kpiRow("s3-budget",  "matched compute (FLOP-proxy)"));
  grid.appendChild(kpiRow("s3-ns",      "no-search quality \u2014 MODELED"));
  grid.appendChild(kpiRow("s3-bok",     "final best-of-K quality \u2014 MODELED"));
  grid.appendChild(kpiRow("s3-s3",      "S\u00b3 quality \u2014 MODELED"));
  grid.appendChild(kpiRow("s3-div",     "S\u00b3 frontier diversity"));
  grid.appendChild(kpiRow("s3-gap",     "S\u00b3 minus best-of-K (matched)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Bilal et al. 2026, arXiv:2604.06260 (S\u00b3: Stratified Scaling Search for Test-Time in Diffusion Language Models). MODELED \u00b7 not claimed-as.";
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
  pd.id = "s3-plain";
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
  const bokQ = S.finalBoK && typeof S.finalBoK.quality === "number" ? (S.finalBoK.quality * 100).toFixed(1) + "%" : "loading\u2026";
  const s3Q  = S.s3 && typeof S.s3.quality === "number" ? (S.s3.quality * 100).toFixed(1) + "%" : "loading\u2026";
  const gap  = S.gap != null ? (S.gap * 100).toFixed(1) + " pts" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> A diffusion model builds an answer by gradually cleaning up noise " +
    "over many steps. The usual way to spend extra compute is to run the whole thing many times " +
    "and keep the best result at the end (\u201cbest-of-K\u201d). S\u00b3 instead spends that same compute " +
    "<i>along the way</i>: at each cleanup step it tries several variations, keeps a cheap " +
    "\u201cquality checker\u201d\u2019s favourites while deliberately keeping some variety, and throws the rest away. " +
    "Pruning bad paths early means the same budget reaches a better answer \u2014 here " +
    "<b>" + s3Q + "</b> for S\u00b3 versus <b>" + bokQ + "</b> for final best-of-K at the same compute " +
    "(a <b>" + gap + "</b> gain). " +
    "This view is a <b>MODELED</b> toy analytic sim of the mid-denoising stratified-search mechanism, " +
    "not S\u00b3 itself: the \u201cdiffusion LM\u201d is a seeded toy denoiser over a few symbols, the " +
    "\u201creference-free verifier\u201d is a closed-form grammar-satisfaction proxy (not a learned verifier), " +
    "and \u201ccompute\u201d is a state-update counter (not real FLOPs). It shows branch-and-prune can beat " +
    "final best-of-K at a matched toy budget on a constructed constraint; it does <b>not</b> reproduce " +
    "S\u00b3\u2019s LLaDA-8B benchmarks on MATH-500 / GSM8K / ARC-Challenge / TruthfulQA (Bilal et al. 2026, " +
    "arXiv:2604.06260). <b>Distinctness flag:</b> this is the narrowest new-axis claim in Wave 11 \u2014 " +
    "a specific search primitive at the dllm+testtime+specdecode junction.";
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
function _q(o) { return o && typeof o.quality === "number" ? o.quality : null; }

function _paintOverlay() {
  const t = _tok(S.state);
  const params = (S.width != null && S.branch != null && S.steps != null)
    ? (S.width + " \u00d7 " + S.branch + " \u00d7 " + S.steps) : "\u2014";
  _set("s3-params", t || params);
  _set("s3-budget", t || (S.budget != null ? String(S.budget) : "\u2014"));
  _set("s3-ns",     t || pct(_q(S.noSearch), 2));
  _set("s3-bok",    t || pct(_q(S.finalBoK), 2));
  _set("s3-s3",     t || pct(_q(S.s3), 2));
  _set("s3-div",    t || pct(S.s3 && typeof S.s3.diversity === "number" ? S.s3.diversity : null, 2));
  _set("s3-gap",    t || (S.gap != null ? (S.gap >= 0 ? "+" : "") + (S.gap * 100).toFixed(2) + " pts" : "\u2014"));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "stratified search" });
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
  _floor = null; _spine = null; _nodeMesh = []; _childMesh = []; _stepLinks = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.width = S.branch = S.steps = S.vweight = S.strata = null;
  S.target = S.budget = S.noSearch = S.finalBoK = S.s3 = S.traj = S.gap = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
