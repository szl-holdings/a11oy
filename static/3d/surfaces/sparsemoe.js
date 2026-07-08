// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/sparsemoe.js — EXTREME-SPARSITY MoE ANALYZER for the holographic frontier
// ring. An HONEST, STRUCTURAL-ONLY visualizer of the activation-ratio ↔ inference-cost
// tradeoff for Mixture-of-Experts configs. A relative-cost CURVE sweeps the activation
// ratio (X) against relative cost-per-token (Y); the user's config point and cited
// frontier reference points (GLM-5.2 etc.) are plotted on it, and two VRAM bars contrast
// the FULL frozen-weight footprint (all experts resident) with the per-token ACTIVE
// slice. Everything is a closed-form arithmetic MODEL — nothing loads or runs a 744B
// model, so the label is STRUCTURAL-ONLY, never MEASURED.
// Live snapshot (same-origin, szl_sparsemoe.py):
//   /api/a11oy/v1/frontier/sparsemoe
//
// FRONTIER CONTEXT (cited; NOT claimed as SZL's own):
//   GLM-5.2 ≈744B total / ≈40B active (≈5.4%), MIT — llmcheck.net state-of-open-source
//     (July 2026) + Anthony Maio "Checkpoint" survey.
//   DeepSeekMoE — Dai et al. 2024, arXiv:2401.06066.
//   Mixtral of Experts — Jiang et al. 2024, arXiv:2401.04088.
//
// HONESTY LABEL: STRUCTURAL-ONLY (closed-form estimator of a MoE config; no model run,
//   never MEASURED). Read from the JSON; never upgraded.
// COLOURS: grey base grid, lattice-blue 0x5b8dee (cost curve / frozen bar), proof-teal
//   0x3af4c8 (user config point / active slice), violet-blue 0x8a6bff (reference points /
//   HUD accent). Purple BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "sparsemoe";
const TITLE = "Extreme-Sparsity MoE Analyzer (STRUCTURAL-ONLY)";

// Served SAME-ORIGIN by szl_sparsemoe.py — a closed-form structural estimator.
const EP = "/api/a11oy/v1/frontier/sparsemoe?total=744&active=40&quant=fp8";

// data-viz hues — purple BANNED
const C_CURVE = 0x5b8dee;  // lattice-blue (relative-cost curve / frozen bar)
const C_USER  = 0x3af4c8;  // proof-teal (user config point / active slice)
const C_REF   = 0x8a6bff;  // violet-blue (cited reference points / accent)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / axis colour

// layout geometry (a plotting frame in world units)
const PLOT_W = 12.0;   // world width mapped to activation ratio 0..1
const PLOT_H = 8.0;    // world height mapped to relative cost 0..1
const PLOT_X = -6.0;   // left edge
const BAR_W  = 1.1;    // VRAM bar width

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor = null;
let _curve = null;         // THREE.Line — relative-cost curve
let _userPt = null;        // THREE.Mesh — user config point
let _refPts = [];          // Array<THREE.Mesh> — cited reference points
let _frozenBar = null;     // THREE.Mesh — full frozen-weight VRAM bar
let _activeBar = null;     // THREE.Mesh — active-slice VRAM bar

// live state
const S = {
  label: null,
  totalB: null, activeB: null, quant: null, bytesPerParam: null,
  activationRatio: null, activationPct: null,
  frozenVram: null, activeVram: null, relativeCost: null,
  curve: null, refs: null,
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
  _stage.camera.position.set(0, 7, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 3, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlotFrame();
  _buildCurve();
  _buildBars();

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

// A simple plot frame: X axis = activation ratio (0..1), Y axis = relative cost (0..1).
function _buildPlotFrame() {
  const THREE = _THREE;
  const pts = [
    new THREE.Vector3(PLOT_X, 0, 0), new THREE.Vector3(PLOT_X + PLOT_W, 0, 0),          // X axis
    new THREE.Vector3(PLOT_X, 0, 0), new THREE.Vector3(PLOT_X, PLOT_H, 0),              // Y axis
  ];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const line = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.5 }));
  _group.add(line);
}

function _buildCurve() {
  const THREE = _THREE;
  // start as a flat placeholder line; rebuilt from payload.curve on live data.
  const geo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(PLOT_X, 0, 0), new THREE.Vector3(PLOT_X + PLOT_W, 0, 0),
  ]);
  _curve = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.4 }));
  _group.add(_curve);

  _userPt = new THREE.Mesh(
    new THREE.SphereGeometry(0.28, 16, 16),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.3, transparent: true, opacity: 0.85 }),
  );
  _userPt.visible = false;
  _group.add(_userPt);
}

function _buildBars() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(BAR_W, 1, BAR_W);
  _frozenBar = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: C_CURVE, emissive: C_CURVE, emissiveIntensity: 0.22, transparent: true, opacity: 0.8 }));
  _frozenBar.position.set(PLOT_X + PLOT_W + 2.2, 0, 0);
  _frozenBar.visible = false;
  _group.add(_frozenBar);

  _activeBar = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: C_USER, emissive: C_USER, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _activeBar.position.set(PLOT_X + PLOT_W + 3.7, 0, 0);
  _activeBar.visible = false;
  _group.add(_activeBar);
}

function _clearRefs() {
  for (const m of _refPts) { try { _group.remove(m); if (m.geometry) m.geometry.dispose(); if (m.material) m.material.dispose(); } catch (_) {} }
  _refPts = [];
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

  S.totalB          = typeof p.total_params_b === "number" ? p.total_params_b : null;
  S.activeB         = typeof p.active_params_b === "number" ? p.active_params_b : null;
  S.quant           = typeof p.quant === "string" ? p.quant : null;
  S.bytesPerParam   = typeof p.bytes_per_param === "number" ? p.bytes_per_param : null;
  S.activationRatio = typeof p.activation_ratio === "number" ? p.activation_ratio : null;
  S.activationPct   = typeof p.activation_pct === "number" ? p.activation_pct : null;
  S.frozenVram      = typeof p.frozen_weight_vram_gb === "number" ? p.frozen_weight_vram_gb : null;
  S.activeVram      = typeof p.active_slice_vram_gb === "number" ? p.active_slice_vram_gb : null;
  S.relativeCost    = typeof p.relative_cost_per_token === "number" ? p.relative_cost_per_token : null;
  S.curve           = Array.isArray(p.curve) ? p.curve : null;
  S.refs            = Array.isArray(p.reference_configs) ? p.reference_configs : null;

  const rd = (p && typeof p.receipt_design === "object") ? p.receipt_design : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paint();
}

function _plotXY(ratio, cost) {
  const THREE = _THREE;
  const x = PLOT_X + Math.max(0, Math.min(1, ratio)) * PLOT_W;
  const y = Math.max(0, Math.min(1, cost)) * PLOT_H;
  return new THREE.Vector3(x, y, 0);
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const THREE = _THREE;
  const live = S.state === "live";

  // cost curve from payload.curve (activation_ratio -> relative_cost_per_token)
  if (_curve) {
    if (live && S.curve && S.curve.length) {
      const pts = S.curve.map((c) => _plotXY(
        typeof c.activation_ratio === "number" ? c.activation_ratio : 0,
        typeof c.relative_cost_per_token === "number" ? c.relative_cost_per_token : 0));
      _curve.geometry.dispose();
      _curve.geometry = new THREE.BufferGeometry().setFromPoints(pts);
      _curve.material.color.setHex(C_CURVE);
      _curve.material.opacity = 0.9;
    } else {
      _curve.material.color.setHex(C_DIM);
      _curve.material.opacity = 0.35;
    }
  }

  // user config point
  if (_userPt) {
    if (live && S.activationRatio != null && S.relativeCost != null) {
      _userPt.position.copy(_plotXY(S.activationRatio, S.relativeCost));
      _userPt.material.color.setHex(C_USER);
      _userPt.material.emissive.setHex(C_USER);
      _userPt.material.opacity = 0.95;
      _userPt.visible = true;
    } else {
      _userPt.visible = false;
    }
  }

  // cited reference points
  _clearRefs();
  if (live && S.refs) {
    for (const r of S.refs) {
      const ratio = typeof r.activation_ratio === "number" ? r.activation_ratio
        : (r.active_b && r.total_b ? r.active_b / r.total_b : 0);
      const m = new THREE.Mesh(
        new THREE.OctahedronGeometry(0.22, 0),
        new THREE.MeshStandardMaterial({ color: C_REF, emissive: C_REF, emissiveIntensity: 0.4, transparent: true, opacity: 0.85 }),
      );
      m.position.copy(_plotXY(ratio, ratio)); // reference cost ≈ its own activation ratio vs same-total baseline
      _group.add(m);
      _refPts.push(m);
    }
  }

  // VRAM bars: frozen (full) vs active (per-token slice), scaled to a shared log-ish cap.
  const maxV = Math.max(1, S.frozenVram || 1);
  const norm = (v) => Math.max(0.05, (v / maxV) * PLOT_H);
  if (_frozenBar) {
    if (live && S.frozenVram != null) {
      const h = norm(S.frozenVram); _frozenBar.scale.y = h; _frozenBar.position.y = h / 2;
      _frozenBar.material.color.setHex(C_CURVE); _frozenBar.material.emissive.setHex(C_CURVE);
      _frozenBar.visible = true;
    } else { _frozenBar.visible = false; }
  }
  if (_activeBar) {
    if (live && S.activeVram != null) {
      const h = norm(S.activeVram); _activeBar.scale.y = h; _activeBar.position.y = h / 2;
      _activeBar.material.color.setHex(C_USER); _activeBar.material.emissive.setHex(C_USER);
      _activeBar.visible = true;
    } else { _activeBar.visible = false; }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.10;
  if (_userPt && _userPt.visible) {
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _userPt.scale.setScalar(pulse);
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
      { label: "STRUCTURAL-ONLY", text: "activation ratio ↔ cost", name: "sm" },
    ],
    legend: ["STRUCTURAL-ONLY", "MODELED"],
    description:
      "<b>Extreme-Sparsity MoE Analyzer.</b> A closed-form estimator of the " +
      "<b>activation-ratio</b> (active ÷ total params) versus <b>inference-cost</b> tradeoff " +
      "for Mixture-of-Experts configs. The <b style=\"color:#5b8dee\">blue</b> curve sweeps " +
      "activation ratio against relative cost-per-token; the <b style=\"color:#3af4c8\">teal</b> " +
      "point is your config, and <b style=\"color:#8a6bff\">violet</b> markers are cited " +
      "frontier points (GLM-5.2 etc.). The two bars contrast the FULL frozen-weight VRAM " +
      "(all experts resident) with the per-token ACTIVE slice. Nothing loads or runs a model " +
      "— every number is <b>STRUCTURAL-ONLY</b>, never MEASURED.",
    citations:
      "GLM-5.2 ~744B/~40B MIT — llmcheck.net state-of-open-source (July 2026) · Anthony Maio " +
      "Checkpoint · DeepSeekMoE arXiv:2401.06066 · Mixtral arXiv:2401.04088. STRUCTURAL-ONLY · " +
      "not claimed-as; a11oy does not run a 744B model. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "A <b>Mixture-of-Experts</b> model has a huge total parameter count but only " +
        "<b>activates a small slice</b> of it per token — that is what makes today's biggest " +
        "open models (e.g. a cited ~744B-total / ~40B-active config) affordable to run. This " +
        "tool lets you plug in (total, active, quant) and see the <b>activation ratio</b>, a " +
        "rough <b>VRAM footprint</b> (all experts still have to sit in memory, even if only a " +
        "few run per token), and how much <b>cheaper</b> the sparse forward is than a dense " +
        "model of the same size. These are <b>modeled estimates</b>, not measurements — nothing " +
        "actually runs a model here, and nothing is signed just by viewing this page.",
    },
  });

  _f.config  = _show.addField("total / active (B)", "config");
  _f.quant   = _show.addField("quant · bytes/param", "quant");
  _f.ratio   = _show.addField("activation ratio", "ratio");
  _f.frozen  = _show.addField("frozen-weight VRAM (GB)", "frozen");
  _f.active  = _show.addField("active-slice VRAM (GB)", "active");
  _f.cost    = _show.addField("relative cost / token", "cost");
  _f.receipt = _show.addField("analysis receipt", "receipt");
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
  if (_show.setChip) _show.setChip("sm", S.label || "STRUCTURAL-ONLY", { text: "activation ratio ↔ cost" });

  _set("config", t || ((S.totalB != null ? S.totalB : "—") + " / " + (S.activeB != null ? S.activeB : "—")));
  _set("quant",  t || ((S.quant || "—") + (S.bytesPerParam != null ? " · " + S.bytesPerParam + " B" : "")));
  _set("ratio",  t || (S.activationRatio != null
        ? fx(S.activationRatio, 4) + (S.activationPct != null ? " (" + fx(S.activationPct, 2) + "%)" : "") : "—"));
  _set("frozen", t || fx(S.frozenVram, 2));
  _set("active", t || fx(S.activeVram, 2));
  _set("cost",   t || fx(S.relativeCost, 4));
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
  _clearRefs();
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
  _floor = _curve = _userPt = _frozenBar = _activeBar = null; _refPts = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.totalB = S.activeB = S.quant = S.bytesPerParam = null;
  S.activationRatio = S.activationPct = S.frozenVram = S.activeVram = S.relativeCost = null;
  S.curve = S.refs = S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
