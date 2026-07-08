// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/gnqs.js — GNQS: Governed-Norm Quantization Stability (SZL synthesis) for
// the holographic frontier ring. Transformer LAYERS sit on an outer arc; each modeled
// layer's activation outlier is bounded by the SZL governed norm (szl-governed-norm)
// and flows inward toward a central Λ-GATE (the szl-lambda-gate; Λ = Conjecture 1 —
// gray, NEVER green) that decides which layers are QUANTIZATION-SAFE. Admitted layers
// glow proof-teal, Λ-gated / unstable layers stay grey. The gate core scales with the
// CAPPED trust (≤0.97). A compact HUD shows the quantization / stability / gate stats
// and the signed-quantization-receipt-per-write DESIGN (nothing minted on a read).
// Live snapshot:
//   /api/a11oy/v1/frontier/gnqs
//
// This is an SZL CROSS-AXIS SYNTHESIS no published system ships together:
//   post-training quantization (LLM.int8() / GPTQ / AWQ / SmoothQuant / BitNet) +
//   governed normalization bounding massive activations (RMSNorm / massive-activations
//   work) + the SZL Λ trust gate over which layers may be quantized + a signed
//   quantization-receipt-per-write chain.
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   LLM.int8() — Dettmers et al. 2022, arXiv:2208.07339
//   GPTQ — Frantar et al. 2022, arXiv:2210.17323
//   AWQ — Lin et al. 2023, arXiv:2306.00978
//   SmoothQuant — Xiao et al. 2022, arXiv:2211.10438
//   BitNet b1.58 — Ma et al. 2024, arXiv:2402.17764
//   RMSNorm — Zhang & Sennrich 2019, arXiv:1910.07467
//   Massive Activations — Sun et al. 2024, arXiv:2402.17762
//
// HONESTY LABELS: MODELED (deterministic per-layer activation profile + governed-norm
//   clamping + quantization-error model; read VERBATIM from JSON, never upgraded).
//   The SZL SYNTHESIS is CONJECTURE: Λ as a per-layer quantization-safe gate is
//   Λ = Conjecture 1 (gray, never green), and the signed-quantization-receipt-per-write
//   chain is design-only (RECEIPT-ON-WRITE — nothing minted or signed on this GET).
//   Trust capped at 0.97.
// COLOURS: lattice-blue 0x5b8dee (layers / links), violet-blue 0x8a6bff (Λ-gate ring),
//   proof-teal 0x3af4c8 (admitted layer / accent), greys (gated-out / unstable /
//   degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "gnqs";
const TITLE = "GNQS · Governed-Norm Quantization Stability (live)";

// Served SAME-ORIGIN by szl_gnqs.py — a deterministic governed-quantization model.
const EP = "/api/a11oy/v1/frontier/gnqs?seed=42&n_layers=48&bits=4&governed=1";

// data-viz hues — purple BANNED
const C_LAYER = 0x5b8dee;  // lattice-blue (layer node / link)
const C_GATE  = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_ADMIT = 0x3af4c8;  // proof-teal (quantization-safe layer / accent)
const C_GATED = 0x5a6570;  // grey (Λ-gated-out / unstable)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const OUT_R    = 7.0;    // radius of the outer layer arc
const MAX_LYR  = 96;     // cap on layer meshes rendered (matches backend _LAYER_CAP)
const GATE_Y   = 0.7;    // height of the central Λ-gate core

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor    = null;
let _gateRing = null; // THREE.LineLoop — Λ-gate ring
let _core     = null; // THREE.Mesh — central gate core (scales with trust)
let _lyrMesh  = [];   // Array<THREE.Mesh> — layer particles
let _lyrLine  = [];   // Array<THREE.Line> — layer -> gate links

// live state
const S = {
  label: null,
  nLayers: null, bits: null, governed: null,
  layers: null,            // layers[] (per-layer)
  admits: null, gatedOut: null,
  meanErr: null, meanRed: null, stabilityRate: null,
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
  _buildLayers();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  _show.attachSceneLabels({
    objects: () => _lyrMesh.filter((m) => m.visible && m.userData && m.userData.weight > 0),
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

// Layer particles: pre-allocated spheres on a deterministic spiral between the outer
// arc and the gate (layer depth = radius), each with a link line toward the gate core.
function _buildLayers() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.13, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_LYR; i++) {
    const t = (i + 1) / MAX_LYR;
    const r = 2.6 + (OUT_R - 3.4) * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_LAYER, emissive: C_LAYER, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.5 + 0.6 * Math.sin(t * 6.283), Math.sin(a) * r);
    mesh.visible = false;
    mesh.userData = { label: "", weight: 0 };
    _group.add(mesh);
    _lyrMesh.push(mesh);

    const lg = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), new THREE.Vector3(0, GATE_Y, 0)]);
    const lm = new THREE.LineBasicMaterial({ color: C_LAYER, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(lg, lm);
    line.visible = false;
    _group.add(line);
    _lyrLine.push(line);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.nLayers  = typeof p.n_layers === "number" ? p.n_layers : null;
  S.bits     = typeof p.bits     === "number" ? p.bits     : null;
  S.governed = typeof p.governed === "boolean" ? p.governed : null;
  S.layers   = Array.isArray(p.layers) ? p.layers : null;

  const q = (p && typeof p.quant === "object") ? p.quant : {};
  S.admits        = typeof q.admitted === "number" ? q.admitted : null;
  S.gatedOut      = typeof q.gated_out === "number" ? q.gated_out : null;
  S.meanErr       = typeof q.mean_quant_error === "number" ? q.mean_quant_error : null;
  S.meanRed       = typeof q.mean_error_reduction === "number" ? q.mean_error_reduction : null;
  S.stabilityRate = typeof q.stability_rate === "number" ? q.stability_rate : null;

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

  // layers: colour by verdict — quantization-safe proof-teal, gated/unstable grey.
  // size ~ error reduction (how much governed-norm helped); a massive-outlier layer
  // is labelled for the top-N ranking.
  const lyr = live && S.layers ? S.layers.slice(0, MAX_LYR) : [];
  for (let i = 0; i < MAX_LYR; i++) {
    const mesh = _lyrMesh[i];
    const line = _lyrLine[i];
    const l = i < lyr.length ? lyr[i] : null;
    if (!l) { mesh.visible = false; line.visible = false; mesh.userData.label = ""; mesh.userData.weight = 0; continue; }
    mesh.visible = true; line.visible = true;
    const admitted = !!l.admitted;
    const red = typeof l.error_reduction === "number" ? l.error_reduction : 0.3;
    const massive = !!l.massive;
    mesh.userData.label = "L" + (l.id != null ? l.id : i) + (massive ? " ·massive" : "");
    mesh.userData.weight = massive ? (1 + red) : 0;
    const col = admitted ? C_ADMIT : C_GATED;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = admitted ? 0.6 : 0.12;
    mesh.material.opacity = admitted ? 0.95 : 0.4;
    mesh.scale.setScalar(0.7 + red * 1.1);
    line.material.color.setHex(col);
    line.material.opacity = admitted ? 0.5 : 0.15;
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
      { label: "MODELED", text: "quant + stability", name: "qn" },
      { label: "STRUCTURAL-ONLY", text: "Λ=Conjecture 1 · receipt design", name: "syn" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>GNQS.</b> Each transformer <b>layer</b> (spiral) has MODELED activation outliers; " +
      "the SZL <b>governed norm</b> (szl-governed-norm) bounds them, cutting the modeled " +
      "<b>quantization error</b> at the chosen bit width. A central <b>Λ-gate</b> (the " +
      "szl-lambda-gate; Λ = Conjecture 1 — gray, NEVER green) then picks which layers are " +
      "quantization-safe: teal = admitted, grey = held back; the core scales with the capped " +
      "trust (≤0.97). Nothing here runs a real quantizer or normalization on real weights — " +
      "the error is <b>MODELED, not MEASURED</b>.",
    citations:
      "LLM.int8() arXiv:2208.07339 · GPTQ 2210.17323 · AWQ 2306.00978 · SmoothQuant 2211.10438 · " +
      "BitNet b1.58 2402.17764 · RMSNorm 1910.07467 · Massive Activations 2402.17762. " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "To run big models cheaply we <b>quantize</b> them — store numbers with fewer bits. " +
        "The trouble is a few giant 'outlier' values that wreck the low-bit maths. A special " +
        "<b>governed normalization</b> step tames those outliers so each layer survives " +
        "quantization better. A <b>trust gate</b> in the middle then decides which layers are " +
        "safe to shrink: teal = safe, grey = held back. The gate is a restraint idea we call " +
        "Λ — an honest <b>conjecture</b>, drawn grey, trust never 100%. These are modeled " +
        "estimates, not measurements, and nothing is signed just by viewing.",
    },
  });

  _f.workload = _show.addField("layers / bits", "workload");
  _f.err      = _show.addField("mean quant error (gov)", "err");
  _f.red      = _show.addField("mean error reduction", "red");
  _f.stab     = _show.addField("stability rate", "stab");
  _f.gov      = _show.addField("governed norm", "gov");
  _f.lambda   = _show.addField("mean Λ advisory (gray)", "lambda");
  _f.gate     = _show.addField("Λ-gate admits / gated-out", "gate");
  _f.trust    = _show.addField("trust (capped ≤0.97)", "trust");
  _f.receipt  = _show.addField("quantization receipt", "receipt");
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
  if (_show.setChip) _show.setChip("qn", S.label || "MODELED", { text: "quant + stability" });

  _set("workload", t || (S.nLayers != null || S.bits != null
        ? (S.nLayers != null ? S.nLayers : "—") + " / " + (S.bits != null ? S.bits + "-bit" : "—") : "—"));
  _set("err",  t || fx(S.meanErr, 4));
  _set("red",  t || pct(S.meanRed, 1));
  _set("stab", t || pct(S.stabilityRate, 1));
  _set("gov",  t || (S.governed == null ? "—" : (S.governed ? "on" : "off")));
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
  _floor = null; _gateRing = null; _core = null; _lyrMesh = []; _lyrLine = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nLayers = S.bits = S.governed = S.layers = null;
  S.admits = S.gatedOut = S.meanErr = S.meanRed = S.stabilityRate = null;
  S.meanLambda = S.lambdaMax = S.admitThresh = S.trust = S.trustCap = null;
  S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
