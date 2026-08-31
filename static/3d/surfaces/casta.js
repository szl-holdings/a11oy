// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/casta.js — CASTA: Clean-room Anomaly + Streaming Test-time Adaptation
// (SZL synthesis) for the holographic frontier ring. A drifting STREAM of windows
// spirals inward; the clean-room SDA detector (khipu-sda-core) scores each for
// anomalies, and a central Λ-GATE (the szl-lambda-gate; Λ = Conjecture 1 — gray,
// NEVER green) decides which streaming test-time ADAPTATION updates are safe to apply
// — REFUSING to adapt to flagged anomalies. Applied (admitted) windows glow
// proof-teal, Λ-gated / anomalous windows stay grey. The gate core scales with the
// CAPPED trust (≤0.97). A compact HUD shows the detection / adaptation / gate stats
// and the signed-adaptation-receipt-per-write DESIGN (nothing minted on a read).
// Live snapshot:
//   /api/a11oy/v1/frontier/casta
//
// This is an SZL CROSS-AXIS SYNTHESIS no published system ships together:
//   streaming test-time adaptation (Tent / CoTTA / EATA / MEMO) + streaming anomaly
//   detection (Robust Random Cut Forest / Isolation Forest) as a GUARD + the SZL Λ
//   trust gate that refuses to adapt to anomalies + a signed adaptation-receipt-per-
//   write chain.
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Tent — Wang et al. 2021, arXiv:2006.10726
//   CoTTA — Wang et al. 2022, arXiv:2203.13591
//   EATA — Niu et al. 2022, arXiv:2204.02610
//   MEMO — Zhang et al. 2021, arXiv:2110.09506
//   Robust Random Cut Forest — Guha et al. 2016, PMLR v48
//   Isolation Forest — Liu et al. 2008, IEEE ICDM
//
// HONESTY LABELS: MODELED (deterministic drifting stream + injected anomalies +
//   clean-room anomaly scores + adaptation-gain model; read VERBATIM from JSON, never
//   upgraded). The SZL SYNTHESIS is CONJECTURE: Λ as a per-window adaptation-safe gate
//   is Λ = Conjecture 1 (gray, never green), and the signed-adaptation-receipt-per-
//   write chain is design-only (RECEIPT-ON-WRITE — nothing minted or signed on this
//   GET). Trust capped at 0.97.
// COLOURS: lattice-blue 0x5b8dee (windows / links), violet-blue 0x8a6bff (Λ-gate ring),
//   proof-teal 0x3af4c8 (applied adaptation / accent), greys (gated-out / anomalous /
//   degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "casta";
const TITLE = "CASTA · Clean-room Anomaly × Streaming Test-time Adaptation (live)";

// Served SAME-ORIGIN by szl_casta.py — a deterministic governed-adaptation model.
const EP = "/api/a11oy/v1/frontier/casta?seed=42&n_steps=48&drift=0.015&contamination=0.12&adapt=1";

// data-viz hues — purple BANNED
const C_WIN   = 0x5b8dee;  // lattice-blue (stream window / link)
const C_GATE  = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_ADMIT = 0x3af4c8;  // proof-teal (applied adaptation / accent)
const C_GATED = 0x5a6570;  // grey (Λ-gated-out / anomalous)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const OUT_R    = 7.0;    // radius of the outer stream arc
const MAX_WIN  = 96;     // cap on window meshes rendered (matches backend _WINDOW_CAP)
const GATE_Y   = 0.7;    // height of the central Λ-gate core

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor    = null;
let _gateRing = null; // THREE.LineLoop — Λ-gate ring
let _core     = null; // THREE.Mesh — central gate core (scales with trust)
let _winMesh  = [];   // Array<THREE.Mesh> — stream-window particles
let _winLine  = [];   // Array<THREE.Line> — window -> gate links

// live state
const S = {
  label: null,
  nSteps: null, drift: null, contamination: null, adapt: null,
  windows: null,           // windows[] (per-window)
  admits: null, gatedOut: null,
  detected: null, trueAnom: null, detectionRate: null, fpRate: null,
  meanGain: null, stabilityRate: null,
  meanLambda: null, lambdaMax: null, admitThresh: null,
  trust: null, trustCap: null,
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
  _stage.camera.position.set(0, 10, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildGate();
  _buildWindows();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  _show.attachSceneLabels({
    objects: () => _winMesh.filter((m) => m.visible && m.userData && m.userData.weight > 0),
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.userData ? o.userData.weight : 0),
    topN: 10,
    hover: true,
  });

  _polls.push(ctx.live.poll(EP, 5000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paint(); },
  }));
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(48, 48, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Central Λ-gate: an advisory ring + a core that scales with the CAPPED trust.
function _buildGate() {
  const THREE = _THREE;
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * 1.9, GATE_Y, Math.sin(a) * 1.9));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const m = new THREE.LineBasicMaterial({ color: C_GATE, transparent: true, opacity: 0.45 });
    _gateRing = new THREE.LineLoop(g, m);
    _group.add(_gateRing);
  }
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.75, 1),
    new THREE.MeshStandardMaterial({ color: C_GATE, emissive: C_GATE, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, GATE_Y, 0);
  _group.add(_core);
}

// Stream-window particles: pre-allocated spheres on a deterministic spiral (a time
// axis inward), each with a link line toward the gate core.
function _buildWindows() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.13, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_WIN; i++) {
    const t = (i + 1) / MAX_WIN;
    const r = 2.6 + (OUT_R - 3.4) * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_WIN, emissive: C_WIN, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.5 + 0.6 * Math.sin(t * 6.283), Math.sin(a) * r);
    mesh.visible = false;
    mesh.userData = { label: "", weight: 0 };
    _group.add(mesh);
    _winMesh.push(mesh);

    const lg = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), new THREE.Vector3(0, GATE_Y, 0)]);
    const lm = new THREE.LineBasicMaterial({ color: C_WIN, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(lg, lm);
    line.visible = false;
    _group.add(line);
    _winLine.push(line);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.nSteps        = typeof p.n_steps === "number" ? p.n_steps : null;
  S.drift         = typeof p.drift   === "number" ? p.drift   : null;
  S.contamination = typeof p.contamination === "number" ? p.contamination : null;
  S.adapt         = typeof p.adapt   === "boolean" ? p.adapt  : null;
  S.windows       = Array.isArray(p.windows) ? p.windows : null;

  const st = (p && typeof p.stream === "object") ? p.stream : {};
  S.admits        = typeof st.admitted === "number" ? st.admitted : null;
  S.gatedOut      = typeof st.gated_out === "number" ? st.gated_out : null;
  S.detected      = typeof st.detected_anomalies === "number" ? st.detected_anomalies : null;
  S.trueAnom      = typeof st.true_anomalies === "number" ? st.true_anomalies : null;
  S.detectionRate = typeof st.detection_rate === "number" ? st.detection_rate : null;
  S.fpRate        = typeof st.false_positive_rate === "number" ? st.false_positive_rate : null;
  S.meanGain      = typeof st.mean_adaptation_gain === "number" ? st.mean_adaptation_gain : null;
  S.stabilityRate = typeof st.stability_rate === "number" ? st.stability_rate : null;

  const g = (p && typeof p.lambda_gate === "object") ? p.lambda_gate : {};
  S.meanLambda  = typeof g.mean_lambda_advisory === "number" ? g.mean_lambda_advisory : null;
  S.admitThresh = typeof g.admit_threshold === "number" ? g.admit_threshold : null;
  S.lambdaMax   = (g.bounds && typeof g.bounds.max === "number") ? g.bounds.max : null;
  S.trust       = typeof g.trust === "number" ? g.trust : null;
  S.trustCap    = typeof g.trust_cap === "number" ? g.trust_cap : null;

  const rd = (p && typeof p.receipt_design === "object") ? p.receipt_design : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  if (_gateRing) {
    _gateRing.material.color.setHex(live ? C_GATE : C_DIM);
    _gateRing.material.opacity = live ? 0.45 : 0.12;
  }

  // windows: colour by verdict — applied adaptation proof-teal, gated/anomalous grey.
  // size ~ adaptation gain; a true-anomaly window is labelled for the top-N ranking.
  const win = live && S.windows ? S.windows.slice(0, MAX_WIN) : [];
  for (let i = 0; i < MAX_WIN; i++) {
    const mesh = _winMesh[i];
    const line = _winLine[i];
    const w = i < win.length ? win[i] : null;
    if (!w) { mesh.visible = false; line.visible = false; mesh.userData.label = ""; mesh.userData.weight = 0; continue; }
    mesh.visible = true; line.visible = true;
    const applied = !!w.applied;
    const anom = !!w.is_anomaly;
    const gain = typeof w.adaptation_gain === "number" ? w.adaptation_gain : 0.3;
    const score = typeof w.anomaly_score === "number" ? w.anomaly_score : 0;
    mesh.userData.label = "w" + (w.id != null ? w.id : i) + (anom ? " ·anomaly" : "");
    mesh.userData.weight = anom ? (1 + score) : 0;
    const col = applied ? C_ADMIT : C_GATED;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = applied ? 0.6 : 0.12;
    mesh.material.opacity = applied ? 0.95 : 0.4;
    mesh.scale.setScalar(0.7 + (applied ? gain : score) * 1.0);
    line.material.color.setHex(col);
    line.material.opacity = applied ? 0.5 : 0.15;
  }

  if (_core) {
    if (live && S.trust != null) {
      _core.material.color.setHex(C_ADMIT);
      _core.material.emissive.setHex(C_ADMIT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.6 + S.trust * 1.0);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.6);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.12;
  if (_gateRing) _gateRing.rotation.y += 0.0015;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.008;
    const pulse = 1.0 + 0.1 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.trust != null) ? (0.6 + S.trust * 1.0) : 0.6;
    _core.scale.setScalar(base * pulse);
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
      { label: "MODELED", text: "anomaly + adaptation", name: "ca" },
      { label: "STRUCTURAL-ONLY", text: "Λ=Conjecture 1 · receipt design", name: "syn" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>CASTA.</b> A drifting <b>stream</b> of windows (spiral) is scored by the clean-room " +
      "SDA detector (khipu-sda-core) for <b>anomalies</b>; a central <b>Λ-gate</b> (the " +
      "szl-lambda-gate; Λ = Conjecture 1 — gray, NEVER green) decides which streaming " +
      "test-time <b>adaptation</b> updates are safe to apply, REFUSING to adapt to flagged " +
      "anomalies. Applied windows glow proof-teal, Λ-gated / anomalous windows stay grey; the " +
      "core scales with the capped trust (≤0.97). Nothing here runs a real adaptation loop or " +
      "anomaly forest — detection & gains are <b>MODELED</b>.",
    citations:
      "Tent arXiv:2006.10726 · CoTTA 2203.13591 · EATA 2204.02610 · MEMO 2110.09506 · " +
      "Robust Random Cut Forest (PMLR v48 2016) · Isolation Forest (IEEE ICDM 2008). " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "When live data slowly changes, a model can <b>adapt</b> on the fly — but adapting to a " +
        "bad or poisoned batch can break it. CASTA watches the stream for <b>anomalies</b> " +
        "(the flagged grey dots) and a <b>trust gate</b> in the middle only lets safe updates " +
        "through: teal = adapted, grey = refused. The gate is a restraint idea we call Λ — an " +
        "honest <b>conjecture</b>, drawn grey, trust never 100%. These are modeled estimates, " +
        "not measurements, and nothing is signed just by viewing this page.",
    },
  });

  _f.workload = _show.addField("windows / drift", "workload");
  _f.detect   = _show.addField("detection rate", "detect");
  _f.fp       = _show.addField("false-positive rate", "fp");
  _f.gain     = _show.addField("mean adaptation gain", "gain");
  _f.stab     = _show.addField("stability rate", "stab");
  _f.lambda   = _show.addField("mean Λ advisory (gray)", "lambda");
  _f.gate     = _show.addField("Λ-gate applied / held", "gate");
  _f.trust    = _show.addField("trust (capped ≤0.97)", "trust");
  _f.receipt  = _show.addField("adaptation receipt", "receipt");
  _f.label    = _show.addField("honesty label", "label");
  _paint();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "—"; }
function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(k, v) { if (_f[k]) _f[k].textContent = v; }

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("ca", S.label || "MODELED", { text: "anomaly + adaptation" });

  _set("workload", t || (S.nSteps != null || S.drift != null
        ? (S.nSteps != null ? S.nSteps : "—") + " / " + (S.drift != null ? S.drift : "—") : "—"));
  _set("detect", t || (S.detectionRate != null
        ? pct(S.detectionRate, 1) + (S.trueAnom != null ? " (" + (S.detected != null ? S.detected : "—") + "/" + S.trueAnom + ")" : "") : "—"));
  _set("fp",   t || pct(S.fpRate, 1));
  _set("gain", t || fx(S.meanGain, 3));
  _set("stab", t || pct(S.stabilityRate, 1));
  _set("lambda", t || (S.meanLambda != null
        ? fx(S.meanLambda, 3) + (S.lambdaMax != null ? " (max " + S.lambdaMax + ")" : "") : "—"));
  _set("gate",  t || (S.admits != null || S.gatedOut != null
        ? (S.admits != null ? S.admits : "—") + " / " + (S.gatedOut != null ? S.gatedOut : "—") : "—"));
  _set("trust", t || (S.trust != null ? fx(S.trust, 3) + (S.trustCap != null ? " (≤" + S.trustCap + ")" : "") : "—"));
  _set("receipt", t || (S.receiptSigned === false
        ? "unsigned preview" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptDigest ? S.receiptDigest.slice(0, 10) + "…" : "—")));
  _set("label", t || (S.label || "MODELED"));
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
  _floor = null; _gateRing = null; _core = null; _winMesh = []; _winLine = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nSteps = S.drift = S.contamination = S.adapt = S.windows = null;
  S.admits = S.gatedOut = S.detected = S.trueAnom = S.detectionRate = S.fpRate = null;
  S.meanGain = S.stabilityRate = null;
  S.meanLambda = S.lambdaMax = S.admitThresh = S.trust = S.trustCap = null;
  S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
