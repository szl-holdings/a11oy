// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainground.js — BRAINGROUND · grounding-confidence + honest abstention over brain
// retrieval.
//
// FOUR PILLARS, one per grounding-confidence component (seed coverage · subgraph cohesion ·
// salience mass · community consistency), each height-scaled by its live value ∈ [0,1]. A
// KEYSTONE ORB above them carries the honest verdict — GROUNDED / WEAK-GROUNDING /
// INSUFFICIENT-GROUNDING — read VERBATIM from the same-origin feed. When the grounding is weak
// the orb dims to grey and the surface states the brain SHOULD ABSTAIN — the point is that the
// brain can honestly say "I don't have enough grounding" rather than answer anyway.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/ground?q=&k= (PURE READ, mints nothing):
//   ok, label (MODELED), query, grounding_confidence, verdict, should_abstain, verdict_reason,
//   components{ seed_coverage{value}, subgraph_cohesion{value}, salience_mass{value},
//               community_consistency{value} }, weights, thresholds, grounding_stats{node_count,…}.
//
// HONESTY LABEL: MODELED — grounding_confidence is a deterministic graph statistic over the
//   brain's REAL grounding_subgraph, NEVER a MEASURED semantic truth. The brain's own honest
//   labels are reused VERBATIM and never upgraded. High confidence is never shown when the
//   components are weak. No green "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved hues only): proof-teal 0x3af4c8 (GROUNDED / pillars), violet-blue 0x8a6bff
//   (WEAK-GROUNDING), lattice-blue 0x5b8dee (frame), greys (INSUFFICIENT / abstain, floor). No
//   other hue.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: read-only over knowledge-graph retrieval — adds NOTHING to the locked-8
//   {F1,F4,F7,F11,F12,F18,F19,F22}; Λ stays Conjecture 1; introduces no theorem. Degrades grey
//   on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "brainground";
const TITLE = "Brainground · grounding-confidence + honest abstention (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ ground endpoint with a
// representative demo query (values come live from the endpoint; nothing is hand-authored).
const DEMO_Q = "brain graph knowledge";
const EP = "/api/a11oy/v1/brain/ground?q=" + encodeURIComponent(DEMO_Q) + "&k=12";

// approved hues only — no amber, no crimson, no green
const C_GROUNDED = 0x3af4c8;  // proof-teal   — GROUNDED / pillars
const C_WEAK     = 0x8a6bff;  // violet-blue  — WEAK-GROUNDING
const C_ABSTAIN  = 0x6b7a86;  // grey         — INSUFFICIENT-GROUNDING / abstain
const C_FRAME    = 0x5b8dee;  // lattice-blue — frame
const C_GRID     = 0x1b3a44;  // floor colour

// the four components, in display order, with human labels
const COMPONENTS = [
  ["seed_coverage",         "seed coverage"],
  ["subgraph_cohesion",     "subgraph cohesion"],
  ["salience_mass",         "salience mass"],
  ["community_consistency", "community consistency"],
];

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "GROUNDED")       return C_GROUNDED;
  if (s === "WEAK-GROUNDING") return C_WEAK;
  return C_ABSTAIN;           // INSUFFICIENT-GROUNDING / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _keystone = null;         // THREE.Mesh — the verdict orb
let _pillars = [];            // Array<{ mesh, key, value }>

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,   // top honesty label VERBATIM (MODELED)
  query:      null,
  confidence: null,
  verdict:    null,
  abstain:    null,
  reason:     null,
  comp:       {},     // { seed_coverage: v, ... } each ∈ [0,1]
  nodeCount:  null,
  linkCount:  null,
  trustCeil:  null,
  lambda:     null,
  locked:     null,
  state:      "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.2, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPillars();
  _buildKeystone();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 9000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintKeystone(); _paintPillars(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildPillars() {
  const THREE = _THREE;
  const n = COMPONENTS.length;
  const totalW = 10.0;
  const step = totalW / n;
  const startX = -totalW / 2 + step / 2;
  const geo = new THREE.BoxGeometry(1.5, 1.0, 1.5);

  for (let i = 0; i < n; i++) {
    const [key] = COMPONENTS[i];
    const x = startX + step * i;
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: C_GROUNDED, emissive: C_GROUNDED, emissiveIntensity: 0.22,
      transparent: true, opacity: 0.9,
    }));
    mesh.scale.y = 0.05;
    mesh.position.set(x, 0.025, 0);
    _group.add(mesh);

    // lattice base ring for each pillar (frame hue)
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.15, 0.03, 8, 40),
      new THREE.MeshBasicMaterial({ color: C_FRAME, transparent: true, opacity: 0.35 }));
    ring.rotation.x = Math.PI / 2;
    ring.position.set(x, 0.02, 0);
    _group.add(ring);

    _pillars.push({ mesh, ring, key, value: 0 });
  }
}

function _buildKeystone() {
  const THREE = _THREE;
  _keystone = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.15, 1),
    new THREE.MeshStandardMaterial({
      color: C_ABSTAIN, emissive: C_ABSTAIN, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.92, flatShading: true,
    }));
  _keystone.position.set(0, 6.4, 0);
  _group.add(_keystone);

  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-5.4, 5.2, 0), new THREE.Vector3(5.4, 5.2, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_FRAME, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label      = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.query      = j && j.query ? String(j.query) : null;
  S.confidence = j && typeof j.grounding_confidence === "number" ? j.grounding_confidence : null;
  S.verdict    = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.abstain    = j && typeof j.should_abstain === "boolean" ? j.should_abstain : null;
  S.reason     = j && j.verdict_reason ? String(j.verdict_reason) : null;

  const c = (j && j.components) || {};
  S.comp = {};
  COMPONENTS.forEach(([key]) => {
    const v = c[key] && typeof c[key].value === "number" ? c[key].value : null;
    S.comp[key] = v;
  });

  const gs = (j && j.grounding_stats) || {};
  S.nodeCount = typeof gs.node_count === "number" ? gs.node_count : null;
  S.linkCount = typeof gs.link_count === "number" ? gs.link_count : null;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _paintPillars();
  _paintKeystone();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.08;

  const live = S.state === "live";
  if (_keystone) {
    const pulse = 0.3 + (live ? 0.25 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _keystone.material.emissiveIntensity = pulse;
    _keystone.rotation.y += 0.004;
    _keystone.rotation.x = Math.sin(t * 0.0007) * 0.15;
  }
  _pillars.forEach((p, i) => {
    const base = live ? 0.26 : 0.1;
    const wob = live ? 0.14 * (0.5 + 0.5 * Math.sin(t * 0.002 + i)) : 0;
    p.mesh.material.emissiveIntensity = base + wob;
    p.mesh.material.opacity = live ? 0.9 : 0.4;
  });
}

// =============================================================================
function _paintPillars() {
  const live = S.state === "live";
  const col = _verdictColor(live ? S.verdict : null);
  _pillars.forEach((p) => {
    const v = live && typeof S.comp[p.key] === "number" ? S.comp[p.key] : 0;
    p.value = v;
    const h = 0.1 + v * 4.6;           // height by component value ∈ [0,1]
    p.mesh.scale.y = h;
    p.mesh.position.y = h / 2;
    // pillars share the verdict hue (teal grounded / violet weak / grey abstain)
    p.mesh.material.color.setHex(col);
    p.mesh.material.emissive.setHex(col);
  });
}

function _paintKeystone() {
  if (!_keystone) return;
  const col = _verdictColor(S.state === "live" ? S.verdict : null);
  _keystone.material.color.setHex(col);
  _keystone.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "grounding", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    "A grounding-confidence lens over the brain's retrieval. For a query it scores the brain's " +
    "<b>real</b> grounding subgraph across four explainable parts — <b>seed coverage</b>, " +
    "<b>subgraph cohesion</b>, <b>salience mass</b>, <b>community consistency</b> — and combines " +
    "them into one confidence ∈ [0,1]. When the grounding is weak it returns " +
    "<b>INSUFFICIENT-GROUNDING</b> and states the brain <b>should abstain</b> rather than answer. " +
    "grounding_confidence is <b>MODELED</b> (a deterministic graph statistic), never a measured " +
    "semantic truth; high confidence is never shown when the parts are weak. 0 runtime CDN.";
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("bg-verdict",  "verdict"));
  grid.appendChild(kpiRow("bg-conf",     "grounding confidence"));
  grid.appendChild(kpiRow("bg-abstain",  "should abstain"));
  grid.appendChild(kpiRow("bg-seed",     "seed coverage"));
  grid.appendChild(kpiRow("bg-cohesion", "subgraph cohesion"));
  grid.appendChild(kpiRow("bg-salience", "salience mass"));
  grid.appendChild(kpiRow("bg-comm",     "community consistency"));
  grid.appendChild(kpiRow("bg-nodes",    "grounding nodes"));
  grid.appendChild(kpiRow("bg-locked",   "locked proofs"));
  grid.appendChild(kpiRow("bg-trust",    "trust ceiling"));
  grid.appendChild(kpiRow("bg-lambda",   "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> GROUNDED &nbsp; ' +
    '<span style="color:#8a6bff">■</span> WEAK-GROUNDING &nbsp; ' +
    '<span style="color:#6b7a86">■</span> INSUFFICIENT-GROUNDING (abstain). ' +
    'MODELED · confidence is a graph statistic, never measured semantic truth · never upgraded.';
  card.appendChild(leg);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "bg-plain";
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
  pd.innerHTML =
    "<b>What this means:</b> before the brain answers a question, this checks whether it actually " +
    "has enough supporting knowledge to answer honestly. It looks at how much of the question the " +
    "brain found, how tightly the supporting facts connect, how concentrated the strongest facts " +
    "are, and whether they cluster in one topic. If the support is thin it says " +
    "<b>INSUFFICIENT-GROUNDING</b> — the brain should say “I don't have enough grounding” instead " +
    "of guessing. The score is an honest graph measurement, not a claim of truth, and confidence " +
    "is capped at 0.97, never 100%. No “verified / 1.0” state.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _pct(v) { return v == null ? "—" : (Math.round(v * 1000) / 10) + "%"; }
function _n(v) { return v == null ? "—" : String(v); }

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "grounding" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bg-verdict",  vrd);
  _set("bg-conf",     t || _pct(S.confidence));
  _set("bg-abstain",  t || (S.abstain == null ? "—" : (S.abstain ? "YES — abstain" : "no")));
  _set("bg-seed",     t || _pct(S.comp["seed_coverage"]));
  _set("bg-cohesion", t || _pct(S.comp["subgraph_cohesion"]));
  _set("bg-salience", t || _pct(S.comp["salience_mass"]));
  _set("bg-comm",     t || _pct(S.comp["community_consistency"]));
  _set("bg-nodes",    t || _n(S.nodeCount));
  _set("bg-locked",   t || (S.locked != null ? String(S.locked) : "—"));
  _set("bg-trust",    t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bg-lambda",   t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

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
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _keystone = null; _pillars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.query = S.confidence = S.verdict = S.abstain = S.reason = null;
  S.comp = {}; S.nodeCount = S.linkCount = null;
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
