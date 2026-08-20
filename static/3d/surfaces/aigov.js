// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/aigov.js — AIGOV: AI-Governance Conformance for the holographic frontier
// ring. Three framework pillars (EU AI Act / NIST AI RMF 1.0 / ISO/IEC 42001) stand
// on a floor; each cited CONTROL is a node orbiting its pillar, coloured by its
// MODELED evidence status — proof-teal = SATISFIED (advisory), lattice-blue =
// PARTIAL, grey = GAP (gaps are always shown, never hidden). A central Λ-READINESS
// core scales with the ADVISORY readiness score (Λ = Conjecture 1 — gray, NEVER
// green; capped ≤0.97, never 1.0). A compact HUD shows per-framework coverage, the
// advisory readiness, and the honest verdict. Live snapshot:
//   /api/a11oy/v1/frontier/aigov
//
// This is an SZL GOVERNANCE SYNTHESIS: it cross-walks a11oy model/inference evidence
// (signed receipts, DSSE/in-toto supply chain, doctrine gate + Λ restraint, energy
// ledger, honest-label discipline) onto the REAL regulated-AI control catalogs.
//
// FRAMEWORKS CITED (clean-room; NOT claimed as SZL's own):
//   EU AI Act — Regulation (EU) 2024/1689 (Annex IV; Arts. 9/10/12/13/14/15/72)
//   NIST AI RMF 1.0 — NIST AI 100-1 (GOVERN / MAP / MEASURE / MANAGE)
//   ISO/IEC 42001:2023 — AI management system (Annex A controls)
//   COMPL-AI — Guldimann et al. 2024, arXiv:2410.07959 (technical interpretation)
//
// HONESTY LABELS: MODELED (real cited control catalog + a genuine design crosswalk;
//   the per-control evidence strengths, coverage rates and readiness are a
//   deterministic SELF-ASSESSMENT MODEL — computed, read VERBATIM from JSON, never
//   upgraded). The readiness is ADVISORY CONJECTURE: Λ = Conjecture 1 (gray, never
//   green). It is NOT a compliance guarantee, NOT an attestation, NOT an ATO — the
//   honest verdict is SELF-ASSESSED / ADVISORY (third-party conformity assessment
//   REQUIRED). Nothing is signed on this read. Readiness capped ≤0.97, never 1.0.
// COLOURS: lattice-blue 0x5b8dee (pillars / PARTIAL), violet-blue 0x8a6bff
//   (Λ-readiness ring), proof-teal 0x3af4c8 (SATISFIED-advisory / accent), greys
//   (GAP / degraded / no-live-data). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Readiness never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "aigov";
const TITLE = "AI Governance Conformance · Λ-Advisory Readiness (live)";

// Served SAME-ORIGIN by szl_aigov.py — a deterministic governed-conformance model.
const EP = "/api/a11oy/v1/frontier/aigov?seed=42";

// data-viz hues — purple BANNED
const C_PILLAR = 0x5b8dee;  // lattice-blue (framework pillar / PARTIAL control)
const C_RING   = 0x8a6bff;  // violet-blue (Λ-readiness ring)
const C_SAT    = 0x3af4c8;  // proof-teal (SATISFIED-advisory / accent)
const C_GAP    = 0x5a6570;  // grey (GAP)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor colour

// layout geometry
const N_PILLAR   = 3;     // EU AI Act / NIST AI RMF 1.0 / ISO/IEC 42001
const PILLAR_R   = 6.4;   // radius the three pillars sit on
const MAX_CTRL   = 32;    // cap on control nodes rendered
const CORE_Y     = 1.4;   // height of the central Λ-readiness core

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor    = null;
let _pillars  = [];   // Array<THREE.Mesh> — the framework pillars (labelled top-N)
let _ring     = null; // THREE.LineLoop — Λ-readiness ring
let _core     = null; // THREE.Mesh — central readiness core (scales with score)
let _ctrlMesh = [];   // Array<THREE.Mesh> — per-control orbiting nodes

// live state
const S = {
  label: null,
  frameworks: null,        // per-framework roll-up
  controls: null,          // control rows
  ctrlTotal: null, satTotal: null, partialTotal: null, gapTotal: null,
  coverage: null,
  readiness: null, readinessCap: null, green: null,
  verdict: null, isGuarantee: null, isAto: null,
  lambdaMax: null,
  mappingSigned: null, mappingDigest: null,
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
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPillars();
  _buildRing();
  _buildControls();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  // top-N framework-pillar labels (billboarded) + hover tooltip via the helper.
  _show.attachSceneLabels({
    objects: () => _pillars.filter((m) => m.visible),
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.userData ? o.userData.weight : 0),
    topN: N_PILLAR,
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
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Three framework pillars on an arc; each a lattice-blue column, labelled with its
// framework name + advisory readiness once live.
function _buildPillars() {
  const THREE = _THREE;
  const geo = new THREE.CylinderGeometry(0.4, 0.5, 3.2, 6);
  for (let i = 0; i < N_PILLAR; i++) {
    const a = Math.PI * (0.5 + (i - (N_PILLAR - 1) / 2) * 0.5);
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_PILLAR, emissive: C_PILLAR, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * PILLAR_R, 1.6, Math.sin(a) * PILLAR_R);
    mesh.visible = false;
    mesh.userData = { label: "", weight: 0, idx: i, home: mesh.position.clone() };
    _group.add(mesh);
    _pillars.push(mesh);
  }
}

// Central Λ-readiness core: an advisory ring + a core that scales with the CAPPED
// advisory readiness score (never green, never 1.0).
function _buildRing() {
  const THREE = _THREE;
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * 2.1, CORE_Y, Math.sin(a) * 2.1));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const m = new THREE.LineBasicMaterial({ color: C_RING, transparent: true, opacity: 0.45 });
    _ring = new THREE.LineLoop(g, m);
    _group.add(_ring);
  }
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.8, 1),
    new THREE.MeshStandardMaterial({ color: C_RING, emissive: C_RING, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, CORE_Y, 0);
  _group.add(_core);
}

// Control nodes: pre-allocated spheres arranged on a deterministic spiral between
// the pillars and the core; coloured by MODELED evidence status once live.
function _buildControls() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.15, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_CTRL; i++) {
    const t = (i + 1) / MAX_CTRL;
    const r = 2.8 + (PILLAR_R - 3.4) * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_PILLAR, emissive: C_PILLAR, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.6 + 1.4 * t, Math.sin(a) * r);
    mesh.visible = false;
    _group.add(mesh);
    _ctrlMesh.push(mesh);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.frameworks = Array.isArray(p.frameworks) ? p.frameworks : null;
  S.controls   = Array.isArray(p.controls) ? p.controls : null;

  const sm = (p && typeof p.summary === "object") ? p.summary : {};
  S.ctrlTotal    = typeof sm.controls_total === "number" ? sm.controls_total : null;
  S.satTotal     = typeof sm.satisfied_advisory === "number" ? sm.satisfied_advisory : null;
  S.partialTotal = typeof sm.partial === "number" ? sm.partial : null;
  S.gapTotal     = typeof sm.gaps === "number" ? sm.gaps : null;
  S.coverage     = typeof sm.coverage_rate === "number" ? sm.coverage_rate : null;

  const rd = (p && typeof p.readiness === "object") ? p.readiness : {};
  S.readiness    = typeof rd.score_advisory === "number" ? rd.score_advisory : null;
  S.readinessCap = typeof rd.score_cap === "number" ? rd.score_cap : null;
  S.green        = typeof rd.green === "boolean" ? rd.green : null;
  S.verdict      = typeof rd.verdict === "string" ? rd.verdict : null;
  S.isGuarantee  = typeof rd.is_compliance_guarantee === "boolean" ? rd.is_compliance_guarantee : null;
  S.isAto        = typeof rd.authorization_to_operate === "boolean" ? rd.authorization_to_operate : null;
  S.lambdaMax    = (rd.lambda_bounds && typeof rd.lambda_bounds.max === "number") ? rd.lambda_bounds.max : null;

  const mp = (p && typeof p.mapping_preview === "object") ? p.mapping_preview : {};
  S.mappingSigned = typeof mp.signed === "boolean" ? mp.signed : null;
  S.mappingDigest = typeof mp.mapping_preview_digest === "string" ? mp.mapping_preview_digest : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // readiness ring degrades to grey when not live
  if (_ring) {
    _ring.material.color.setHex(live ? C_RING : C_DIM);
    _ring.material.opacity = live ? 0.45 : 0.12;
  }

  // framework pillars: light up + label with the framework name and its advisory
  // readiness; weight (for the top-N ranking) tracks the readiness.
  const fws = live && S.frameworks ? S.frameworks : [];
  for (let i = 0; i < N_PILLAR; i++) {
    const mesh = _pillars[i];
    const fw = i < fws.length ? fws[i] : null;
    if (!fw) { mesh.visible = false; mesh.userData.label = ""; mesh.userData.weight = 0; continue; }
    mesh.visible = true;
    const rdy = typeof fw.readiness_advisory === "number" ? fw.readiness_advisory : 0;
    const cov = typeof fw.coverage_rate === "number" ? fw.coverage_rate : 0;
    mesh.userData.label = (fw.framework || ("fw" + i)) + " · " + (rdy * 100).toFixed(0) + "%";
    mesh.userData.weight = rdy;
    // colour a pillar by its coverage: some SATISFIED -> teal tint, else lattice-blue.
    const col = cov > 0 ? C_SAT : C_PILLAR;
    mesh.material.color.setHex(live ? col : C_DIM);
    mesh.material.emissive.setHex(live ? col : C_DIM);
    mesh.material.emissiveIntensity = live ? 0.28 : 0.1;
    mesh.material.opacity = live ? 0.9 : 0.3;
    mesh.scale.y = 0.5 + rdy * 1.2;
  }

  // control nodes: colour by MODELED status — SATISFIED(advisory) proof-teal,
  // PARTIAL lattice-blue, GAP grey. Gaps are always shown, never hidden.
  const ctrls = live && S.controls ? S.controls.slice(0, MAX_CTRL) : [];
  for (let i = 0; i < MAX_CTRL; i++) {
    const mesh = _ctrlMesh[i];
    const c = i < ctrls.length ? ctrls[i] : null;
    if (!c) { mesh.visible = false; continue; }
    mesh.visible = true;
    const status = String(c.status || "");
    const strength = typeof c.evidence_strength === "number" ? c.evidence_strength : 0.4;
    let col = C_GAP;
    if (status.indexOf("SATISFIED") === 0) col = C_SAT;
    else if (status === "PARTIAL") col = C_PILLAR;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = col === C_SAT ? 0.6 : (col === C_PILLAR ? 0.3 : 0.12);
    mesh.material.opacity = col === C_GAP ? 0.4 : 0.95;
    mesh.scale.setScalar(0.6 + strength * 1.0);
  }

  // readiness core: colour + size reflect the CAPPED advisory readiness (never
  // green / never 1.0). Teal accent, but the score itself is drawn as advisory.
  if (_core) {
    if (live && S.readiness != null) {
      _core.material.color.setHex(C_SAT);
      _core.material.emissive.setHex(C_SAT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.6 + S.readiness * 1.0);
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
  if (_ring) _ring.rotation.y += 0.0015;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.008;
    const pulse = 1.0 + 0.1 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.readiness != null) ? (0.6 + S.readiness * 1.0) : 0.6;
    _core.scale.setScalar(base * pulse);
  }
}

// =============================================================================
// showcase overlay (shared helper) — compact chrome + collapsible KPIs
// =============================================================================
function _buildShowcase(ctx) {
  _show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "MODELED", text: "conformance crosswalk", name: "cf" },
      { label: "STRUCTURAL-ONLY", text: "Λ readiness · advisory", name: "adv" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>AI Governance Conformance.</b> Three framework pillars — <b>EU AI Act</b> " +
      "(Reg. (EU) 2024/1689, Annex IV), <b>NIST AI RMF 1.0</b> and <b>ISO/IEC 42001</b> — " +
      "each carry cited CONTROLS cross-walked to a11oy evidence (signed receipts, " +
      "DSSE/in-toto supply chain, doctrine gate + Λ restraint, energy ledger, honest " +
      "labels). Each control node is coloured by its MODELED evidence status: proof-teal " +
      "SATISFIED (advisory), lattice-blue PARTIAL, grey GAP (gaps are shown, never " +
      "hidden). The central core scales with the <b>Λ-advisory readiness</b> " +
      "(Λ = Conjecture 1 — gray, NEVER green; capped ≤0.97). This is a SELF-ASSESSMENT " +
      "MODEL — <b>NOT a compliance guarantee, NOT an attestation, NOT an ATO</b>; a " +
      "third-party conformity assessment is REQUIRED.",
    citations:
      "EU AI Act — Reg. (EU) 2024/1689 · NIST AI RMF 1.0 (NIST AI 100-1) · " +
      "ISO/IEC 42001:2023 · COMPL-AI arXiv:2410.07959. " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "Companies that build AI have to answer to rulebooks — the EU AI Act, the US " +
        "NIST framework, and the ISO 42001 standard. This surface lines up what a11oy " +
        "can already show as evidence against each rule, and marks each one teal " +
        "(covered), blue (partly covered) or grey (a real gap we haven't closed). The " +
        "middle score is a <b>readiness estimate</b> — an honest self-check, drawn grey " +
        "as a <b>conjecture</b>, and it never reaches 100%. It is <b>not</b> a pass, a " +
        "certificate, or permission to deploy: a real outside auditor still has to sign " +
        "off. Nothing is signed or saved just by looking at this page.",
    },
  });

  _f.frameworks = _show.addField("frameworks mapped", "frameworks");
  _f.controls   = _show.addField("controls (cited)", "controls");
  _f.coverage   = _show.addField("coverage (satisfied-advisory)", "coverage");
  _f.gaps       = _show.addField("partial / gaps (honest)", "gaps");
  _f.eu         = _show.addField("EU AI Act readiness", "eu");
  _f.nist       = _show.addField("NIST AI RMF 1.0 readiness", "nist");
  _f.iso        = _show.addField("ISO/IEC 42001 readiness", "iso");
  _f.readiness  = _show.addField("Λ readiness (advisory ≤0.97)", "readiness");
  _f.verdict    = _show.addField("verdict", "verdict");
  _f.mapping    = _show.addField("mapping preview", "mapping");
  _f.label      = _show.addField("honesty label", "label");
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

function _fwReadiness(name) {
  if (!Array.isArray(S.frameworks)) return null;
  const f = S.frameworks.find((x) => x && x.framework === name);
  return f && typeof f.readiness_advisory === "number" ? f.readiness_advisory : null;
}

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("cf", S.label || "MODELED", { text: "conformance crosswalk" });

  _set("frameworks", t || (S.frameworks != null ? String(S.frameworks.length) : "—"));
  _set("controls", t || (S.ctrlTotal != null ? String(S.ctrlTotal) : "—"));
  _set("coverage", t || (S.satTotal != null && S.ctrlTotal != null
        ? S.satTotal + "/" + S.ctrlTotal + (S.coverage != null ? " (" + pct(S.coverage, 0) + ")" : "") : "—"));
  _set("gaps", t || (S.partialTotal != null || S.gapTotal != null
        ? (S.partialTotal != null ? S.partialTotal : "—") + " / " + (S.gapTotal != null ? S.gapTotal : "—") : "—"));
  _set("eu",   t || pct(_fwReadiness("EU AI Act"), 1));
  _set("nist", t || pct(_fwReadiness("NIST AI RMF 1.0"), 1));
  _set("iso",  t || pct(_fwReadiness("ISO/IEC 42001"), 1));
  _set("readiness", t || (S.readiness != null
        ? fx(S.readiness, 3) + (S.readinessCap != null ? " (≤" + S.readinessCap + ")" : "")
          + (S.green === false ? " · not-green" : "") : "—"));
  _set("verdict", t || (S.verdict || "—"));
  _set("mapping", t || (S.mappingSigned === false
        ? "unsigned preview" + (S.mappingDigest ? " " + S.mappingDigest.slice(0, 10) + "…" : "")
        : (S.mappingDigest ? S.mappingDigest.slice(0, 10) + "…" : "—")));
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
  _floor = null; _pillars = []; _ring = null; _core = null; _ctrlMesh = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.frameworks = S.controls = null;
  S.ctrlTotal = S.satTotal = S.partialTotal = S.gapTotal = S.coverage = null;
  S.readiness = S.readinessCap = S.green = S.verdict = S.isGuarantee = S.isAto = null;
  S.lambdaMax = S.mappingSigned = S.mappingDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
