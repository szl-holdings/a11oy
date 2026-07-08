// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/execverify.js — EXECUTION-VERIFIED SYNTHESIS LOOP for the holographic frontier
// ring. An HONEST, STRUCTURAL-ONLY visualizer of a CLOSED loop that ties a11oy's existing
// honest-eval (evalarena), the Brain (corpus), and agentops (bounded operate loop) into one
// governed pipeline: eval → execution-verified trajectory → corpus candidate → signed
// receipt. Five stage rings are drawn around the loop; a funnel of trajectory motes shows
// how eval-passes narrow to execution-verified candidates through the Λ-advisory gate.
// a11oy does NOT train a model from the loop in-request — the synthesis is DESCRIBED and
// RECEIPTED, not executed end-to-end, so the label is STRUCTURAL-ONLY.
// Live snapshot (same-origin, szl_execverify.py):
//   /api/a11oy/v1/frontier/execverify
//
// FRONTIER CONTEXT (cited; NOT claimed as SZL's own):
//   Together AI ICML-2026 — one harness both evaluates agents AND generates
//     execution-verified training data: together.ai/blog/icml-2026.
//   Execution-guided synthesis — Chen et al. 2018, arXiv:1807.03100.
//   STaR: Self-Taught Reasoner — Zelikman et al. 2022, arXiv:2203.14465.
//
// HONESTY LABEL: STRUCTURAL-ONLY (the closed loop wiring the organs is a synthesis design;
//   eval scores / verification verdicts are MODELED, never MEASURED). Read from JSON.
// COLOURS: grey base grid, lattice-blue 0x5b8dee (loop ring / eval), proof-teal 0x3af4c8
//   (execution-verified candidate motes), violet-blue 0x8a6bff (Λ-gate accent / HUD). Purple
//   BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Λ stays Conjecture 1 (advisory, gray, NEVER green); trust capped ≤0.97, never 1.0.
// Nothing here is in the locked-8 (adds 0).

import { createShowcase } from "./_showcase.js";

const ID    = "execverify";
const TITLE = "Execution-Verified Synthesis Loop (STRUCTURAL-ONLY)";

// Served SAME-ORIGIN by szl_execverify.py — a deterministic seeded loop model.
const EP = "/api/a11oy/v1/frontier/execverify?seed=42&n_trajectories=48&pass_rate=0.6&verify=true";

// data-viz hues — purple BANNED
const C_LOOP = 0x5b8dee;  // lattice-blue (loop ring / eval stage / gated-out motes)
const C_CAND = 0x3af4c8;  // proof-teal (execution-verified corpus-candidate motes)
const C_GATE = 0x8a6bff;  // violet-blue (Λ-advisory gate ring / accent)
const C_DIM  = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID = 0x1b3a44;  // floor / axis colour

const LOOP_R  = 5.0;    // radius of the stage loop
const MOTE_N  = 48;     // max trajectory motes rendered
const FUNNEL_Y = 6.0;   // top of the trajectory funnel

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor = null;
let _loopRing = null;      // THREE.Line — the five-stage loop ring
let _gateRing = null;      // THREE.Line — Λ-advisory gate ring
let _stageNodes = [];      // Array<THREE.Mesh> — five stage markers
let _motes = [];           // Array<THREE.Mesh> — trajectory motes (candidate vs gated)

// live state
const S = {
  label: null,
  nTraj: null, evalPassed: null, execVerified: null,
  candidates: null, gatedOut: null,
  verificationRate: null, candidateYield: null,
  meanLambda: null, trust: null, trustCap: null,
  trajectories: null,
  receiptSigned: null, receiptDigest: null,
  state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLoop();
  _buildGate();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paint(); },
  }));
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Five stage markers (eval → execute → verify → candidate → receipt) on a ring.
function _buildLoop() {
  const THREE = _THREE;
  const pts = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * LOOP_R, 0.02, Math.sin(a) * LOOP_R));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  _loopRing = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.4 }));
  _group.add(_loopRing);

  const sgeo = new THREE.OctahedronGeometry(0.32, 0);
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2 - Math.PI / 2;
    const m = new THREE.Mesh(sgeo.clone(), new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.3, transparent: true, opacity: 0.85 }));
    m.position.set(Math.cos(a) * LOOP_R, 0.4, Math.sin(a) * LOOP_R);
    _group.add(m);
    _stageNodes.push(m);
  }
}

// Λ-advisory gate ring (violet, gray-status — never green): the admit boundary.
function _buildGate() {
  const THREE = _THREE;
  const pts = [];
  for (let i = 0; i <= 48; i++) {
    const a = (i / 48) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * 1.6, 2.4, Math.sin(a) * 1.6));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  _gateRing = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.4 }));
  _group.add(_gateRing);
}

function _clearMotes() {
  for (const m of _motes) { try { _group.remove(m); if (m.geometry) m.geometry.dispose(); if (m.material) m.material.dispose(); } catch (_) {} }
  _motes = [];
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const raw = (j && j.label) || (p && p.label) || "STRUCTURAL-ONLY";
  // honesty label read from JSON; runtime default STRUCTURAL-ONLY, never upgraded.
  S.label = (raw || "STRUCTURAL-ONLY");
  S.label = String(S.label).toUpperCase();

  const loop = (p && typeof p.loop === "object") ? p.loop : {};
  S.nTraj            = typeof loop.trajectories === "number" ? loop.trajectories : null;
  S.evalPassed       = typeof loop.eval_passed === "number" ? loop.eval_passed : null;
  S.execVerified     = typeof loop.execution_verified === "number" ? loop.execution_verified : null;
  S.candidates       = typeof loop.corpus_candidates === "number" ? loop.corpus_candidates : null;
  S.gatedOut         = typeof loop.gated_out === "number" ? loop.gated_out : null;
  S.verificationRate = typeof loop.verification_rate === "number" ? loop.verification_rate : null;
  S.candidateYield   = typeof loop.candidate_yield === "number" ? loop.candidate_yield : null;

  const gate = (p && typeof p.lambda_gate === "object") ? p.lambda_gate : {};
  S.meanLambda = typeof gate.mean_lambda_advisory === "number" ? gate.mean_lambda_advisory : null;
  S.trust      = typeof gate.trust === "number" ? gate.trust : null;
  S.trustCap   = typeof gate.trust_cap === "number" ? gate.trust_cap : null;

  S.trajectories = Array.isArray(p.trajectories) ? p.trajectories : null;

  const rd = (p && typeof p.receipt === "object") ? p.receipt : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const THREE = _THREE;
  const live = S.state === "live";

  if (_loopRing) {
    const c = live ? C_LOOP : C_DIM;
    _loopRing.material.color.setHex(c);
    _loopRing.material.opacity = live ? 0.85 : 0.4;
  }
  for (const m of _stageNodes) {
    const c = live ? C_LOOP : C_DIM;
    m.material.color.setHex(c); m.material.emissive.setHex(c);
    m.material.opacity = live ? 0.95 : 0.85;
  }
  if (_gateRing) {
    const c = live ? C_GATE : C_DIM;   // Λ gate: violet advisory, NEVER green.
    _gateRing.material.color.setHex(c);
    _gateRing.material.opacity = live ? 0.85 : 0.4;
  }

  // trajectory funnel: teal motes = execution-verified candidates that pass the Λ gate,
  // blue motes = gated-out trajectories. Positions are cosmetic; verdicts are from data.
  _clearMotes();
  if (live && S.trajectories && S.trajectories.length) {
    const geo = new THREE.SphereGeometry(0.12, 10, 10);
    const list = S.trajectories.slice(0, MOTE_N);
    const n = list.length;
    list.forEach((tr, i) => {
      const cand = !!tr.is_candidate;
      const a = (i / Math.max(1, n)) * Math.PI * 2;
      // candidates funnel toward the center/gate; gated-out drift to the outer ring.
      const r = cand ? 1.6 : LOOP_R * (0.8 + 0.2 * ((i % 5) / 5));
      const y = cand ? 2.4 : 0.6 + FUNNEL_Y * (i % 7) / 7;
      const c = cand ? C_CAND : C_LOOP;
      const m = new THREE.Mesh(geo.clone(), new THREE.MeshStandardMaterial({
        color: c, emissive: c, emissiveIntensity: cand ? 0.5 : 0.25,
        transparent: true, opacity: cand ? 0.95 : 0.55 }));
      m.position.set(Math.cos(a) * r, y, Math.sin(a) * r);
      _group.add(m);
      _motes.push(m);
    });
    geo.dispose();
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = t * 0.00008;
  if (_gateRing && S.state === "live") {
    const pulse = 1.0 + 0.06 * Math.sin(t * 0.003);
    _gateRing.scale.setScalar(pulse);
  }
}

// =============================================================================
// showcase overlay (shared helper)
// =============================================================================
function _buildShowcase(ctx) {
  _show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "STRUCTURAL-ONLY", text: "eval → verified → corpus", name: "ev" },
    ],
    legend: ["STRUCTURAL-ONLY", "MODELED"],
    description:
      "<b>Execution-Verified Synthesis Loop.</b> A closed honest loop that ties a11oy's own " +
      "organs — <b>evalarena</b> (honest eval), <b>agentops</b> (bounded operate loop, writer≠judge), " +
      "and the <b>Brain</b> corpus — into one governed pipeline: eval → " +
      "<b style=\"color:#3af4c8\">execution-verified</b> trajectory → corpus candidate → " +
      "SHA-256 receipt. Trajectory motes funnel from eval-passes down through the " +
      "<b style=\"color:#8a6bff\">Λ-advisory gate</b> (Conjecture 1, gray — never green): only " +
      "<b style=\"color:#3af4c8\">teal</b> execution-verified trajectories become corpus candidates. " +
      "a11oy does NOT train a model from the loop in-request — the synthesis is DESCRIBED and " +
      "RECEIPTED, so every number is <b>STRUCTURAL-ONLY / MODELED</b>, never MEASURED.",
    citations:
      "Together AI ICML-2026 (together.ai/blog/icml-2026) — one harness: honest eval + " +
      "execution-verified training data · execution-guided synthesis arXiv:1807.03100 · " +
      "STaR arXiv:2203.14465. STRUCTURAL-ONLY — a11oy claims none of these as its own and does " +
      "not run an end-to-end training loop in-request. Λ = Conjecture 1; trust capped 0.97. " +
      "Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "The same test harness that <b>grades</b> an agent can also <b>collect the runs that " +
        "actually worked</b> and feed them back as training data — closing the loop between " +
        "measuring an agent and improving it. This surface shows that loop over a11oy's own " +
        "parts: a run is scored, then <b>actually executed to check it really works</b> (not just " +
        "looks right), and only the verified ones become learning material — each stamped with a " +
        "tamper-evident receipt. These are <b>modeled estimates</b> of the loop, not a real " +
        "training run: a11oy does not train a model here, and nothing is signed just by viewing " +
        "this page.",
    },
  });

  _f.traj    = _show.addField("trajectories / eval-passed", "traj");
  _f.verify  = _show.addField("execution-verified", "verify");
  _f.cand    = _show.addField("corpus candidates / gated-out", "cand");
  _f.yield   = _show.addField("candidate yield · verify rate", "yield");
  _f.lambda  = _show.addField("Λ advisory (Conjecture 1)", "lambda");
  _f.trust   = _show.addField("trust (cap 0.97)", "trust");
  _f.receipt = _show.addField("candidate receipt", "receipt");
  _f.label   = _show.addField("honesty label", "label");
  _paint();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(k, v) { if (_f[k]) _f[k].textContent = v; }

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("ev", S.label || "STRUCTURAL-ONLY", { text: "eval → verified → corpus" });

  _set("traj",   t || ((S.nTraj != null ? S.nTraj : "—") + " / " + (S.evalPassed != null ? S.evalPassed : "—")));
  _set("verify", t || (S.execVerified != null ? String(S.execVerified) : "—"));
  _set("cand",   t || ((S.candidates != null ? S.candidates : "—") + " / " + (S.gatedOut != null ? S.gatedOut : "—")));
  _set("yield",  t || ((S.candidateYield != null ? fx(S.candidateYield, 4) : "—")
        + " · " + (S.verificationRate != null ? fx(S.verificationRate, 4) : "—")));
  _set("lambda", t || (S.meanLambda != null ? fx(S.meanLambda, 4) + " (gray, advisory)" : "—"));
  _set("trust",  t || (S.trust != null ? fx(S.trust, 4) + (S.trustCap != null ? " ≤ " + S.trustCap : "") : "—"));
  _set("receipt", t || (S.receiptSigned === false
        ? "unsigned preview" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptDigest ? S.receiptDigest.slice(0, 10) + "…" : "—")));
  _set("label", t || (S.label || "STRUCTURAL-ONLY"));
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  _clearMotes();
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
  _floor = _loopRing = _gateRing = null; _stageNodes = []; _motes = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nTraj = S.evalPassed = S.execVerified = S.candidates = S.gatedOut = null;
  S.verificationRate = S.candidateYield = S.meanLambda = S.trust = S.trustCap = null;
  S.trajectories = S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
