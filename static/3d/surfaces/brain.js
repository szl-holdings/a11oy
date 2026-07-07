// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brain.js — FORMULA-GRAPH BRAIN (SZL ORIGINAL). Renders the estate's
// OWN proven-formula library as a self-organizing LIVING GRAPH: each formula is
// a NODE, each real proof/semantic dependency is an EDGE, and a MODELED
// spreading-activation ("firing") pulse propagates outward from the locked-8
// proven core across K rounds. This is the "make it our own" fusion — it reuses
// three field-leader mechanisms purely as visualization primitives:
//   * DLA (arXiv:2606.10650)      — importance-aware activation ROUTING (edge weights)
//   * OPERA (arXiv:2606.25757)    — intrinsic firing REWARD = proven-mass reached
//   * Context-Ready (arXiv:2606.27538) — K-UNROLL as K spreading rounds
//
// THE GRAPH IS REAL: every node traces to a named Lean declaration in a cited
// lutar-lean file (kernel c7c0ba17) or a real DOI/arXiv. The FIRING DYNAMIC is
// MODELED (a deterministic toy on the real topology), read VERBATIM from
// /api/killinchu/v1/fgbrain/{graph,fire}. The honesty label "MODELED" is shown
// as-is and never upgraded.
//
// HARD INVARIANTS (Doctrine v11):
//   * locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}.
//   * Λ unconditional uniqueness = Conjecture 1 -> GRAY node, NEVER green/proven.
//   * Khipu BFT (Conj-2/3) -> GRAY, never green.
//   * COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//     greys. Purple BANNED as UI/background.
//   * 0 runtime CDN (three.js via ctx.THREE). Degrades gracefully on 404.
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

const ID    = "brain";
const TITLE = "Formula-Graph Brain";

const EP_GRAPH  = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/graph";
const EP_FIRE   = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/fire?seed=42&K=10";
// wave-16: self-repair probe (lesion F1, a known articulation point, and heal)
const EP_REPAIR = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/repair?down=F1&steps=12";
// wave-17: multi-timescale plasticity probe (Hebb/BCM/STDP/EWC per-tier learning rates)
const EP_PLAST  = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/plasticity?seed=42&rounds=30";
// wave-18: write-back memory loop (HEART/BLOOD hash-chain + A-MEM reconsolidation)
const EP_MEM    = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/memory?seed=42&sessions=5";
// wave-19: homeostatic self-regulation (MAPE-K + HRRL drive-reduction, meta-stats only)
const EP_VITALS = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/vitals?seed=42&rounds=12";
// wave-20: evolutionary self-improvement (MAP-Elites/DGM archive; kernel gate disposes)
const EP_EVOLVE = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/fgbrain/evolve?seed=42&generations=15";

// tier -> colour. proof-teal for the proven core, lattice-blue for verified/experimental,
// violet-blue for borrowed fusions, GREY for conjectures (never green).
const C_LOCKED = 0x3af4c8;  // proof-teal  (locked-proven core)
const C_SEMANT = 0x5b8dee;  // lattice-blue (semantic-verified)
const C_EXPER  = 0x5b8dee;  // lattice-blue (experimental, dimmer)
const C_BORROW = 0x8a6bff;  // violet-blue (borrowed field-leader fusions)
const C_CONJ   = 0x5a6570;  // GREY (conjectures — never green)
const C_EDGE   = 0x1b3a44;  // dim link
const C_DIM    = 0x42505d;  // grey (degraded / no live data)
const C_FIRE   = 0x3af4c8;  // firing pulse (proof-teal)

const TIER_COLOR = {
  locked: C_LOCKED, semantic: C_SEMANT, experimental: C_EXPER,
  borrowed: C_BORROW, conjecture: C_CONJ,
};
const TIER_RADIUS = { locked: 0.34, semantic: 0.24, experimental: 0.2, borrowed: 0.2, conjecture: 0.18 };

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _nodeMeshes = {};   // id -> mesh
let _edgeLines = [];    // line segments
let _pos = {};          // id -> THREE.Vector3
let _t0 = 0;

const S = {
  label: null, nodes: [], edges: [], tierCounts: null,
  lockedCount: null, rewardPerK: null, rewardFinal: null,
  nodesFired: null, conjGreen: null, state: "init",
  lesion: null, bodyHealth: null, lam2Before: null, lam2After: null, connectedAfter: null,
  lockedFrozen: null, plastScore: null, ewcCore: null,
  beats: null, chainOk: null, reconsGain: null,
  driveFinal: null, viability: null, inBand: null, setpointCount: null,
  lockedUntouched: null, failClosed: null,
  archiveCells: null, archiveCellsPossible: null, modeledPromotions: null,
  gateImmutable: null, claimPinningOk: null, rollbackRestored: null,
};

// deterministic layout: concentric shells by tier (locked core -> outward),
// angle from a hash of the id (stable, no RNG needed on the client).
const SHELL = { locked: 0.0, semantic: 2.2, experimental: 3.6, borrowed: 4.8, conjecture: 6.0 };
function _hash(str) { let h = 2166136261 >>> 0; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h; }

function _layout(nodes) {
  _pos = {};
  const byTier = {};
  nodes.forEach((n) => { (byTier[n.tier] = byTier[n.tier] || []).push(n); });
  Object.keys(byTier).forEach((tier) => {
    const arr = byTier[tier];
    const r = SHELL[tier] != null ? SHELL[tier] : 5.0;
    arr.forEach((n, i) => {
      const base = (_hash(n.id) % 360) * Math.PI / 180;
      const ang = base + (i / Math.max(1, arr.length)) * 2 * Math.PI * 0.15;
      const tilt = ((_hash(n.id + "y") % 200) / 200 - 0.5) * (tier === "locked" ? 1.1 : 2.2);
      _pos[n.id] = new _THREE.Vector3(Math.cos(ang) * r, tilt, Math.sin(ang) * r);
    });
  });
}

function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());

  _buildOverlay(ctx);
  _badge = ctx.live.createBadge();

  // Pull the real graph once, then poll the firing snapshot.
  _polls.push(ctx.live.poll(EP_GRAPH, 0, _onGraph, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));
  _polls.push(ctx.live.poll(EP_FIRE, 5000, _onFire, { onState: (m) => { S.state = m.state; _paintOverlay(); } }));
  _polls.push(ctx.live.poll(EP_REPAIR, 0, _onRepair, {}));
  _polls.push(ctx.live.poll(EP_PLAST, 0, _onPlast, {}));
  _polls.push(ctx.live.poll(EP_MEM, 0, _onMem, {}));
  _polls.push(ctx.live.poll(EP_VITALS, 0, _onVitals, {}));
  _polls.push(ctx.live.poll(EP_EVOLVE, 0, _onEvolve, {}));

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j) {
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label : "MODELED";
  return String(lbl).toUpperCase();
}

function _onGraph(j) {
  if (!j || !_group) { S.state = "error"; _paintOverlay(); return; }
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.nodes = Array.isArray(p.nodes) ? p.nodes : [];
  S.edges = Array.isArray(p.edges) ? p.edges : [];
  S.lockedCount = p.locked_count != null ? p.locked_count : null;
  _rebuildGraph();
  _paintOverlay();
}

function _onFire(j) {
  if (!j) return;
  const p = j.payload || j;
  S.label = _readLabel(j);
  S.tierCounts = p.tier_counts || null;
  S.rewardPerK = Array.isArray(p.firing_reward_per_k) ? p.firing_reward_per_k : null;
  S.rewardFinal = p.firing_reward_final != null ? p.firing_reward_final : null;
  S.nodesFired = p.nodes_fired != null ? p.nodes_fired : null;
  S.conjGreen = p.conjecture_rendered_green != null ? p.conjecture_rendered_green : null;
  if (p.locked_count != null) S.lockedCount = p.locked_count;
  _paintOverlay();
}

function _clearGraph() {
  Object.values(_nodeMeshes).forEach((m) => {
    if (m.geometry && m.geometry.dispose) m.geometry.dispose();
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _edgeLines.forEach((l) => {
    if (l.geometry && l.geometry.dispose) l.geometry.dispose();
    if (l.material && l.material.dispose) l.material.dispose();
    _group.remove(l);
  });
  _nodeMeshes = {}; _edgeLines = [];
}

function _rebuildGraph() {
  if (!_group || !S.nodes.length) return;
  _clearGraph();
  _layout(S.nodes);

  // edges first (behind nodes)
  S.edges.forEach((e) => {
    const a = _pos[e.src], b = _pos[e.dst];
    if (!a || !b) return;
    const g = new _THREE.BufferGeometry().setFromPoints([a, b]);
    const m = new _THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.5 });
    const line = new _THREE.Line(g, m);
    _edgeLines.push(line); _group.add(line);
  });

  // nodes
  S.nodes.forEach((n) => {
    const isConj = n.tier === "conjecture";
    const col = TIER_COLOR[n.tier] != null ? TIER_COLOR[n.tier] : C_DIM;
    const rad = TIER_RADIUS[n.tier] != null ? TIER_RADIUS[n.tier] : 0.2;
    const geo = new _THREE.SphereGeometry(rad, 18, 18);
    // conjecture nodes are flat/emissive-free grey so they can NEVER read as "fired green"
    const mat = new _THREE.MeshStandardMaterial({
      color: col,
      emissive: isConj ? 0x000000 : col,
      emissiveIntensity: isConj ? 0.0 : 0.28,
      metalness: 0.1, roughness: isConj ? 0.95 : 0.5,
      transparent: true, opacity: isConj ? 0.55 : 0.95,
    });
    const mesh = new _THREE.Mesh(geo, mat);
    mesh.position.copy(_pos[n.id]);
    mesh.userData = { id: n.id, tier: n.tier, isConj };
    _nodeMeshes[n.id] = mesh; _group.add(mesh);
  });
}

function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = t * 0.12;

  // MODELED firing pulse: a wave that expands from the locked core outward each
  // K, brightening proven nodes; conjecture nodes NEVER brighten (stay grey).
  const K = S.rewardPerK ? S.rewardPerK.length : 10;
  const phase = (t * 0.6) % (K + 2);
  Object.values(_nodeMeshes).forEach((m) => {
    if (!m.material) return;
    if (m.userData.isConj) { m.material.emissiveIntensity = 0.0; return; }  // gray-only invariant
    const shell = SHELL[m.userData.tier] != null ? SHELL[m.userData.tier] : 5.0;
    const reach = Math.max(0, 1 - Math.abs(phase - shell) * 0.8);
    const base = m.userData.tier === "locked" ? 0.35 : 0.2;
    m.material.emissiveIntensity = base + 0.6 * reach;
  });
}

function _onRepair(j) {
  if (!j) return;
  const p = j.payload || j;
  S.lesion = p.lesion != null ? p.lesion : null;
  S.bodyHealth = p.body_health_excl_lesion != null ? p.body_health_excl_lesion : null;
  S.lam2Before = p.fiedler_lambda2_before != null ? p.fiedler_lambda2_before : null;
  S.lam2After = p.fiedler_lambda2_after != null ? p.fiedler_lambda2_after : null;
  S.connectedAfter = p.still_connected_after_lesion != null ? p.still_connected_after_lesion : null;
  _paintOverlay();
}

function _onPlast(j) {
  if (!j) return;
  const p = j.payload || j;
  S.lockedFrozen = p.locked_edges_unchanged != null ? p.locked_edges_unchanged : null;
  S.plastScore = p.plasticity_score != null ? p.plasticity_score : null;
  S.ewcCore = p.ewc_core_protection_penalty != null ? p.ewc_core_protection_penalty : null;
  _paintOverlay();
}

function _onMem(j) {
  if (!j) return;
  const p = j.payload || j;
  S.beats = p.beats_written != null ? p.beats_written : null;
  S.chainOk = p.chain_intact != null ? p.chain_intact : null;
  S.reconsGain = p.reconsolidation_gain != null ? p.reconsolidation_gain : null;
  _paintOverlay();
}

function _onVitals(j) {
  if (!j) return;
  const p = j.payload || j;
  S.driveFinal = p.drive_final != null ? p.drive_final : null;
  S.viability = p.viability_horizon != null ? p.viability_horizon : null;
  S.inBand = p.in_band_count != null ? p.in_band_count : null;
  S.setpointCount = p.setpoint_count != null ? p.setpoint_count : null;
  S.lockedUntouched = p.locked_untouched != null ? p.locked_untouched : null;
  S.failClosed = p.fail_closed != null ? p.fail_closed : null;
  if (p.locked_count != null) S.lockedCount = p.locked_count;
  _paintOverlay();
}

function _onEvolve(j) {
  if (!j) return;
  const p = j.payload || j;
  S.archiveCells = p.archive_cells_filled != null ? p.archive_cells_filled : null;
  S.archiveCellsPossible = p.archive_cells_possible != null ? p.archive_cells_possible : null;
  S.modeledPromotions = p.modeled_promotions != null ? p.modeled_promotions : null;
  S.gateImmutable = p.gate_immutable != null ? p.gate_immutable : null;
  S.claimPinningOk = p.claim_pinning_ok != null ? p.claim_pinning_ok : null;
  S.rollbackRestored = p.rollback_restored != null ? p.rollback_restored : null;
  if (p.locked_count != null) S.lockedCount = p.locked_count;
  _paintOverlay();
}

// =============================================================================
// overlay HUD
// =============================================================================
function _buildOverlay(ctx) {
  _overlay = document.createElement("div");
  _overlay.style.cssText =
    "position:absolute;top:12px;left:12px;max-width:360px;font:12px/1.5 ui-monospace,Menlo,monospace;" +
    "color:#cfe3ea;background:rgba(15,32,39,0.82);border:1px solid #1b3a44;border-radius:10px;padding:12px 14px;" +
    "pointer-events:auto;backdrop-filter:blur(3px);z-index:20;";
  _overlay.innerHTML =
    '<div style="font-weight:700;letter-spacing:.03em;color:#eaf6f9;font-size:13px">Formula-Graph Brain ' +
      '<span id="brain-label" style="float:right;font-size:10px;padding:1px 7px;border-radius:8px;background:#123;color:#3af4c8;border:1px solid #1b3a44">MODELED</span></div>' +
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">Our 180+ formulas as a living graph — the proven-8 core fires outward.</div>' +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    _row("Nodes / Edges", "brain-ne") +
    _row("Locked-proven", "brain-locked") +
    _row("Firing reward (final)", "brain-reward") +
    _row("Proven nodes fired", "brain-fired") +
    _row("Conjectures shown green", "brain-conjgreen") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Self-repair (lesion &rarr; heal)</div>' +
    _row("Lesioned node", "brain-lesion") +
    _row("Body health (healed)", "brain-bodyhealth") +
    _row("Connectivity \u03bb2 aft.", "brain-lam2") +
    _row("Still one mind?", "brain-connected") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Plasticity (multi-timescale)</div>' +
    _row("Locked canon frozen", "brain-frozen") +
    _row("Plasticity score", "brain-plast") +
    _row("EWC core protection", "brain-ewc") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Memory (write-back loop)</div>' +
    _row("Receipt beats written", "brain-beats") +
    _row("Hash chain intact", "brain-chain") +
    _row("Reconsolidation gain", "brain-recons") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Homeostasis (self-regulation)</div>' +
    _row("Drive (final)", "brain-drive") +
    _row("In-band set-points", "brain-inband") +
    _row("Viability horizon", "brain-viab") +
    _row("Locked untouched", "brain-untouched") +
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">' +
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:2px">Evolution (proposes; kernel disposes)</div>' +
    _row("Archive cells filled", "brain-archive") +
    _row("Promotions (MODELED)", "brain-promos") +
    _row("Kernel gate immutable", "brain-gate") +
    _row("Drift rollback restored", "brain-rollback") +
    '<div id="brain-tiers" style="margin-top:6px;font-size:10.5px;color:#8fb3bd"></div>' +
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">' +
      _leg(C_LOCKED, "proven-8") + _leg(C_SEMANT, "verified") + _leg(C_BORROW, "borrowed") + _leg(C_CONJ, "conjecture (gray)") +
    '</div>' +
    '<div style="margin-top:8px"><button id="brain-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;' +
      'border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button></div>' +
    '<div id="brain-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>';
  (ctx.container || document.body).appendChild(_overlay);
  const btn = _overlay.querySelector("#brain-plain");
  if (btn) btn.addEventListener("click", () => { _plain = !_plain; _applyPlain(); });
}
function _row(k, id) {
  return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px">' +
    '<span style="color:#8fb3bd">' + k + '</span><span id="' + id + '" style="color:#eaf6f9;font-variant-numeric:tabular-nums">—</span></div>';
}
function _leg(hex, txt) {
  const c = "#" + hex.toString(16).padStart(6, "0");
  return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + c + ';margin-right:4px;vertical-align:middle"></span>' + txt + '</span>';
}
function _set(id, v) { const e = _overlay && _overlay.querySelector("#" + id); if (e) e.textContent = v; }

function _paintOverlay() {
  if (!_overlay) return;
  const deg = (S.state === "error" || S.state === "degraded");
  const d = deg ? "—" : null;
  _set("brain-label", S.label || "MODELED");
  _set("brain-ne", d || ((S.nodes.length || "—") + " / " + (S.edges.length || "—")));
  _set("brain-locked", d || (S.lockedCount != null ? String(S.lockedCount) + " (exactly 8)" : "—"));
  _set("brain-reward", d || (S.rewardFinal != null ? (S.rewardFinal * 100).toFixed(1) + "% mass" : "—"));
  _set("brain-fired", d || (S.nodesFired != null ? String(S.nodesFired) : "—"));
  _set("brain-conjgreen", d || (S.conjGreen != null ? (S.conjGreen + " (must be 0)") : "—"));
  _set("brain-lesion", d || (S.lesion != null ? String(S.lesion) : "\u2014"));
  _set("brain-bodyhealth", d || (S.bodyHealth != null ? (S.bodyHealth * 100).toFixed(1) + "%" : "\u2014"));
  _set("brain-lam2", d || (S.lam2After != null ? (S.lam2Before != null ? S.lam2Before.toFixed(3) + " \u2192 " : "") + S.lam2After.toFixed(3) : "\u2014"));
  _set("brain-connected", d || (S.connectedAfter != null ? (S.connectedAfter ? "yes" : "no \u2014 cut-vertex") : "\u2014"));
  _set("brain-frozen", d || (S.lockedFrozen != null ? (S.lockedFrozen ? "yes (never drifts)" : "NO \u2014 alert") : "\u2014"));
  _set("brain-plast", d || (S.plastScore != null ? S.plastScore.toFixed(3) : "\u2014"));
  _set("brain-ewc", d || (S.ewcCore != null ? S.ewcCore.toFixed(5) : "\u2014"));
  _set("brain-beats", d || (S.beats != null ? String(S.beats) : "\u2014"));
  _set("brain-chain", d || (S.chainOk != null ? (S.chainOk ? "yes (tamper-evident)" : "NO \u2014 alert") : "\u2014"));
  _set("brain-recons", d || (S.reconsGain != null ? (S.reconsGain >= 0 ? "+" : "") + S.reconsGain + " nodes" : "\u2014"));
  _set("brain-drive", d || (S.driveFinal != null ? S.driveFinal.toFixed(4) + (S.failClosed ? " (fail-closed)" : "") : "\u2014"));
  _set("brain-inband", d || (S.inBand != null && S.setpointCount != null ? S.inBand + " / " + S.setpointCount : "\u2014"));
  _set("brain-viab", d || (S.viability != null ? S.viability + " cycles" : "\u2014"));
  _set("brain-untouched", d || (S.lockedUntouched != null ? (S.lockedUntouched ? "yes (meta-stats only)" : "NO \u2014 alert") : "\u2014"));
  _set("brain-archive", d || (S.archiveCells != null ? (S.archiveCells + (S.archiveCellsPossible != null ? " / " + S.archiveCellsPossible : "")) : "\u2014"));
  _set("brain-promos", d || (S.modeledPromotions != null ? (S.modeledPromotions + " (MODELED, not locked-8)") : "\u2014"));
  _set("brain-gate", d || (S.gateImmutable != null ? (S.gateImmutable ? "yes" : "NO \u2014 alert") : "\u2014"));
  _set("brain-rollback", d || (S.rollbackRestored != null ? (S.rollbackRestored ? "yes" : "NO \u2014 alert") : "\u2014"));
  if (S.tierCounts) {
    const t = S.tierCounts;
    _set("brain-tiers", "tiers: locked " + (t.locked || 0) + " · semantic " + (t.semantic || 0) +
      " · experimental " + (t.experimental || 0) + " · borrowed " + (t.borrowed || 0) + " · conjecture " + (t.conjecture || 0));
  }
  if (_plain) _applyPlain();
}

function _applyPlain() {
  const box = _overlay && _overlay.querySelector("#brain-plainbox");
  if (!box) return;
  box.style.display = _plain ? "block" : "none";
  if (_plain) {
    box.innerHTML =
      "Each ball is one of our math formulas. The bright teal balls in the middle are the " +
      "<b>8 that are actually machine-proven</b>. Lines are real proof dependencies. A pulse " +
      "spreads out from the proven core across " + (S.rewardPerK ? S.rewardPerK.length : 10) + " rounds — that's the " +
      "\u201Cfiring.\u201D The grey balls are <b>conjectures we have NOT proven</b> (like \u039B\u2019s " +
      "uniqueness) — they stay grey and never light up green, on purpose. The routing/reward/spread " +
      "borrow ideas from three 2026 papers (DLA, OPERA, Context-Ready) but train nothing. Label is " +
      "<b>" + (S.label || "MODELED") + "</b> — a faithful drawing of our real proof structure, not a computation.";
  }
}

// =============================================================================
// unmount
// =============================================================================
function unmount() {
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
  _nodeMeshes = {}; _edgeLines = []; _pos = {};
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = null; S.nodes = []; S.edges = []; S.tierCounts = null;
  S.lockedCount = S.rewardPerK = S.rewardFinal = S.nodesFired = S.conjGreen = null;
  S.lesion = S.bodyHealth = S.lam2Before = S.lam2After = S.connectedAfter = null;
  S.lockedFrozen = S.plastScore = S.ewcCore = null;
  S.beats = S.chainOk = S.reconsGain = null;
  S.driveFinal = S.viability = S.inBand = S.setpointCount = null;
  S.lockedUntouched = S.failClosed = null;
  S.archiveCells = S.archiveCellsPossible = S.modeledPromotions = null;
  S.gateImmutable = S.claimPinningOk = S.rollbackRestored = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP_GRAPH, EP_FIRE, EP_REPAIR, EP_PLAST, EP_MEM, EP_VITALS, EP_EVOLVE], mount, unmount };
