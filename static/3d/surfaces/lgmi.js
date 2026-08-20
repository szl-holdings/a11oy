// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/lgmi.js — LGMI: Λ-Governed Mechanistic Interpretability (SZL synthesis)
// for the holographic frontier ring. Sparse FEATURES sit on an outer arc; each
// modeled CIRCUIT composes features and flows inward toward a central Λ-GATE
// (the szl-lambda-gate aggregator; Λ = Conjecture 1 — gray, NEVER green). Admitted
// (trusted) circuits glow proof-teal, Λ-gated / low-faithfulness circuits stay grey.
// The gate core scales with the CAPPED trust (≤0.97). A compact HUD shows the
// attribution / faithfulness / gate stats and the signed-attribution-receipt-per-
// write DESIGN (nothing minted on a read). Live snapshot:
//   /api/a11oy/v1/frontier/lgmi
//
// This is an SZL CROSS-AXIS SYNTHESIS no published system ships together:
//   mechanistic interpretability (sparse autoencoders / attribution patching /
//   automated circuit discovery) + the SZL Λ trust gate over which circuits a claim
//   may rely on + a signed attribution-receipt-per-write chain.
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Towards Monosemanticity — Bricken et al. 2023 (Transformer Circuits)
//   Sparse Autoencoders Find Interpretable Features — Cunningham et al. 2023, arXiv:2309.08600
//   JumpReLU Sparse Autoencoders — Rajamanoharan et al. 2024, arXiv:2407.14435
//   ACDC (automated circuit discovery) — Conmy et al. 2023, arXiv:2304.14997
//   IOI circuit — Wang et al. 2022, arXiv:2211.00593
//   Attribution Patching / AtP* — Kramár et al. 2024, arXiv:2403.00745
//
// HONESTY LABELS: MODELED (deterministic sparse-feature population + circuit
//   attribution + faithfulness checks; read VERBATIM from JSON, never upgraded).
//   The SZL SYNTHESIS is CONJECTURE: Λ as a per-circuit trust gate is Λ = Conjecture
//   1 (gray, never green), and the signed-attribution-receipt-per-write chain is
//   design-only (RECEIPT-ON-WRITE — nothing minted or signed on this GET). Trust
//   capped at 0.97.
// COLOURS: lattice-blue 0x5b8dee (features / links), violet-blue 0x8a6bff (Λ-gate
//   ring), proof-teal 0x3af4c8 (admitted circuit / accent), greys (gated-out /
//   low-faithfulness / degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "lgmi";
const TITLE = "LGMI · Λ-Governed Mechanistic Interpretability (live)";

// Served SAME-ORIGIN by szl_lgmi.py — a deterministic governed-interpretability model.
const EP = "/api/a11oy/v1/frontier/lgmi?seed=42&n_features=64&n_circuits=48&sparsity=0.08";

// data-viz hues — purple BANNED
const C_FEAT  = 0x5b8dee;  // lattice-blue (feature node / circuit link)
const C_GATE  = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_ADMIT = 0x3af4c8;  // proof-teal (admitted circuit / accent)
const C_GATED = 0x5a6570;  // grey (Λ-gated-out / low-faithfulness)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const FEAT_R    = 7.0;   // radius of the outer feature arc
const MAX_CIRC  = 96;    // cap on circuit meshes rendered (matches backend _CIRCUIT_CAP)
const MAX_FEAT  = 12;    // cap on feature emitters shown on the arc
const GATE_Y    = 0.7;   // height of the central Λ-gate core

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor    = null;
let _featMesh = [];   // Array<THREE.Mesh> — feature emitters on the outer arc
let _gateRing = null; // THREE.LineLoop — Λ-gate ring
let _core     = null; // THREE.Mesh — central gate core (scales with trust)
let _circMesh = [];   // Array<THREE.Mesh> — circuit particles
let _circLine = [];   // Array<THREE.Line> — circuit -> gate links

// live state
const S = {
  label: null,
  nFeatures: null, nCircuits: null, sparsity: null,
  features: null,          // features[] {id, activation_freq, monosemanticity, dead}
  circuits: null,          // circuits[] (per-circuit)
  admits: null, gatedOut: null,
  meanAttr: null, meanFaith: null, consistencyRate: null, deadRate: null,
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
  _buildFeatures();
  _buildGate();
  _buildCircuits();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  _show.attachSceneLabels({
    objects: () => _featMesh.filter((m) => m.visible),
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.userData ? o.userData.weight : 0),
    topN: MAX_FEAT,
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

// Feature emitters: up to MAX_FEAT sparse latents on the outer arc, each a
// lattice-blue node; a more monosemantic feature is drawn larger + weighted higher.
function _buildFeatures() {
  const THREE = _THREE;
  const geo = new THREE.OctahedronGeometry(0.34, 0);
  for (let i = 0; i < MAX_FEAT; i++) {
    const a = Math.PI * (0.12 + 0.76 * (i / Math.max(1, MAX_FEAT - 1)));
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_FEAT, emissive: C_FEAT, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * FEAT_R, 1.1, Math.sin(a) * FEAT_R);
    mesh.visible = false;
    mesh.userData = { label: "", weight: 0 };
    _group.add(mesh);
    _featMesh.push(mesh);
  }
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

// Circuit particles: pre-allocated spheres on a deterministic spiral between the
// feature arc and the gate, each with a link line toward the gate core.
function _buildCircuits() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.13, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_CIRC; i++) {
    const t = (i + 1) / MAX_CIRC;
    const r = 2.6 + (FEAT_R - 3.4) * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_FEAT, emissive: C_FEAT, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.5 + 0.6 * Math.sin(t * 6.283), Math.sin(a) * r);
    mesh.visible = false;
    _group.add(mesh);
    _circMesh.push(mesh);

    const lg = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), new THREE.Vector3(0, GATE_Y, 0)]);
    const lm = new THREE.LineBasicMaterial({ color: C_FEAT, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(lg, lm);
    line.visible = false;
    _group.add(line);
    _circLine.push(line);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.nFeatures = typeof p.n_features === "number" ? p.n_features : null;
  S.nCircuits = typeof p.n_circuits === "number" ? p.n_circuits : null;
  S.sparsity  = typeof p.sparsity   === "number" ? p.sparsity   : null;
  S.features  = Array.isArray(p.features) ? p.features : null;
  S.circuits  = Array.isArray(p.circuits) ? p.circuits : null;

  const at = (p && typeof p.attribution === "object") ? p.attribution : {};
  S.admits          = typeof at.admitted === "number" ? at.admitted : null;
  S.gatedOut        = typeof at.gated_out === "number" ? at.gated_out : null;
  S.meanAttr        = typeof at.mean_attribution === "number" ? at.mean_attribution : null;
  S.meanFaith       = typeof at.mean_faithfulness === "number" ? at.mean_faithfulness : null;
  S.consistencyRate = typeof at.consistency_rate === "number" ? at.consistency_rate : null;
  S.deadRate        = typeof at.dead_feature_rate === "number" ? at.dead_feature_rate : null;

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

  // feature emitters: size ~ monosemanticity (dead latents drop out / dim).
  const feats = live && S.features ? S.features.slice(0, MAX_FEAT) : [];
  for (let i = 0; i < MAX_FEAT; i++) {
    const mesh = _featMesh[i];
    const s = i < feats.length ? feats[i] : null;
    if (!s) { mesh.visible = false; mesh.userData.label = ""; mesh.userData.weight = 0; continue; }
    mesh.visible = true;
    const mono = typeof s.monosemanticity === "number" ? s.monosemanticity : 0.5;
    const dead = !!s.dead;
    mesh.userData.label = "f" + (s.id != null ? s.id : i) + (dead ? " ·dead" : " m" + mono.toFixed(2));
    mesh.userData.weight = dead ? 0 : mono;
    const col = dead ? C_DIM : (live ? C_FEAT : C_DIM);
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = dead ? 0.08 : (live ? 0.3 : 0.1);
    mesh.material.opacity = dead ? 0.25 : (live ? 0.9 : 0.3);
    mesh.scale.setScalar(0.6 + (dead ? 0.0 : mono * 0.9));
  }

  // circuits: colour by verdict — admitted proof-teal, Λ-gated/low-faithfulness grey.
  const circ = live && S.circuits ? S.circuits.slice(0, MAX_CIRC) : [];
  for (let i = 0; i < MAX_CIRC; i++) {
    const mesh = _circMesh[i];
    const line = _circLine[i];
    const t = i < circ.length ? circ[i] : null;
    if (!t) { mesh.visible = false; line.visible = false; continue; }
    mesh.visible = true; line.visible = true;
    const admitted = !!t.admitted;
    const attr = typeof t.attribution === "number" ? t.attribution : 0.5;
    const col = admitted ? C_ADMIT : C_GATED;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = admitted ? 0.6 : 0.12;
    mesh.material.opacity = admitted ? 0.95 : 0.4;
    mesh.scale.setScalar(0.7 + attr * 1.0);
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
      { label: "MODELED", text: "features + circuits", name: "mi" },
      { label: "STRUCTURAL-ONLY", text: "Λ=Conjecture 1 · receipt design", name: "syn" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>LGMI.</b> Sparse <b>features</b> (outer arc) compose MODELED <b>circuits</b> that " +
      "carry an <b>attribution</b> effect, then pass a central <b>Λ-gate</b> (the " +
      "szl-lambda-gate aggregator; Λ = Conjecture 1 — gray, NEVER green). Admitted circuits " +
      "glow proof-teal, Λ-gated / low-faithfulness circuits stay grey; the core scales with " +
      "the capped trust (≤0.97). Mechanistic interpretability finds features & circuits; the " +
      "SZL twist governs WHICH circuits a claim may rely on — nothing here trains a real SAE " +
      "or runs attribution patching.",
    citations:
      "Towards Monosemanticity (Transformer Circuits 2023) · Sparse Autoencoders arXiv:2309.08600 · " +
      "JumpReLU 2407.14435 · ACDC 2304.14997 · IOI 2211.00593 · Attribution Patching / AtP* 2403.00745. " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "Researchers can find the tiny internal 'parts' of a language model that do specific " +
        "jobs — the dots on the outer ring are those parts, and the dots flowing inward are " +
        "small circuits built from them. A <b>trust gate</b> in the middle decides which " +
        "circuits are reliable enough to base an explanation on: teal = trusted, grey = held " +
        "back. The gate is a restraint idea we call Λ — an honest <b>conjecture</b>, so it's " +
        "drawn grey and its trust never hits 100%. Nothing is signed or saved just by looking " +
        "at this page.",
    },
  });

  _f.workload = _show.addField("features / circuits", "workload");
  _f.attr     = _show.addField("mean attribution", "attr");
  _f.faith    = _show.addField("mean faithfulness", "faith");
  _f.cons     = _show.addField("consistency rate", "cons");
  _f.dead     = _show.addField("dead-feature rate", "dead");
  _f.lambda   = _show.addField("mean Λ advisory (gray)", "lambda");
  _f.gate     = _show.addField("Λ-gate admits / gated-out", "gate");
  _f.trust    = _show.addField("trust (capped ≤0.97)", "trust");
  _f.receipt  = _show.addField("attribution receipt", "receipt");
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
  if (_show.setChip) _show.setChip("mi", S.label || "MODELED", { text: "features + circuits" });

  _set("workload", t || (S.nFeatures != null || S.nCircuits != null
        ? (S.nFeatures != null ? S.nFeatures : "—") + " / " + (S.nCircuits != null ? S.nCircuits : "—") : "—"));
  _set("attr",  t || fx(S.meanAttr, 3));
  _set("faith", t || pct(S.meanFaith, 1));
  _set("cons",  t || pct(S.consistencyRate, 1));
  _set("dead",  t || pct(S.deadRate, 1));
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
  _floor = null; _featMesh = []; _gateRing = null; _core = null; _circMesh = []; _circLine = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nFeatures = S.nCircuits = S.sparsity = S.features = S.circuits = null;
  S.admits = S.gatedOut = S.meanAttr = S.meanFaith = S.consistencyRate = S.deadRate = null;
  S.meanLambda = S.lambdaMax = S.admitThresh = S.trust = S.trustCap = null;
  S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
