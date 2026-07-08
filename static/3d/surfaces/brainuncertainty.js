// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainuncertainty.js — BRAIN UNCERTAINTY · calibrated, honest uncertainty on a
// brain retrieval. Complements a grounding-confidence surface: this is about UNCERTAINTY /
// CALIBRATION (dispersion, entropy, stability), NOT point grounding confidence.
//
// THREE component PILLARS (score dispersion, retrieval entropy, rank stability), each height
// by its uncertainty in [0,1], stand under a VERDICT plate that reads CONFIDENT / UNCERTAIN /
// HIGHLY-UNCERTAIN. A single spine gauges the combined uncertainty. HONEST BY CONSTRUCTION:
// every value is read from the same-origin feed, which is derived live from the honest brain
// retrieval (szl_brain_api) — never a hand-authored number.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/uncertainty?q=&k= (PURE READ, mints nothing):
//   ok, label (MODELED), query, k, results_retrieved, uncertainty, verdict, abstain_recommended,
//   components{ score_dispersion{uncertainty}, retrieval_entropy{uncertainty},
//              rank_stability{uncertainty} }, doctrine{ lambda, locked_proven, trust_ceiling }.
//
// HONESTY LABEL: MODELED — a deterministic, explainable measure over the retrieval's OWN shape.
//   CALIBRATION HONESTY, NOT A PROBABILITY GUARANTEE: it is NOT P(answer correct). The verdict
//   is NEVER CONFIDENT when dispersion or entropy is high. Λ = Conjecture 1, never a theorem.
//   Trust ceiling 0.97, never 100%. No green "verified / 1.0" state.
// COLOURS (approved hues ONLY): proof-teal 0x3af4c8 (CONFIDENT), lattice-blue 0x5b8dee
//   (UNCERTAIN / frame), violet-blue 0x8a6bff (HIGHLY-UNCERTAIN / abstain), greys (grid/idle).
//   No green, no red, no amber.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: reads only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22};
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "brainuncertainty";
const TITLE = "Brain Uncertainty · calibrated honest uncertainty on a brain retrieval (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ uncertainty endpoint.
// A representative demo query drives the live gauge; the number shown is whatever the honest
// retrieval yields for it (never a curated result).
const DEMO_Q = "estate thesis";
const DEMO_K = 10;
const EP = `/api/a11oy/v1/brain/uncertainty?q=${encodeURIComponent(DEMO_Q)}&k=${DEMO_K}`;

// verdict hues — approved palette only, no green/red/amber
const C_CONFIDENT = 0x3af4c8;  // proof-teal   — CONFIDENT
const C_UNCERTAIN = 0x5b8dee;  // lattice-blue — UNCERTAIN / frame
const C_HIGH      = 0x8a6bff;  // violet-blue  — HIGHLY-UNCERTAIN / abstain
const C_NEUTRAL   = 0x42505d;  // grey         — idle / no data
const C_GRID      = 0x1b3a44;  // floor colour

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "CONFIDENT")        return C_CONFIDENT;
  if (s === "HIGHLY-UNCERTAIN") return C_HIGH;
  if (s === "UNCERTAIN")        return C_UNCERTAIN;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _plate = null;            // THREE.Mesh — the verdict plate
let _spine = null;            // THREE.Mesh — combined-uncertainty gauge
let _pillars = [];            // Array<{ mesh, name, u }>

// live state (all read from JSON; nothing invented)
const S = {
  label:   null,   // MODELED (verbatim)
  query:   null,
  k:       null,
  n:       null,   // results_retrieved
  u:       null,   // combined uncertainty [0,1]
  verdict: null,   // CONFIDENT | UNCERTAIN | HIGHLY-UNCERTAIN
  abstain: null,
  disp:    null,   // component uncertainties
  ent:     null,
  stab:    null,
  trustCeil: null,
  lambda:  null,
  locked:  null,
  state:   "init",
};

// Fixed pillar layout — one per honest component (always the same 3, never padded).
const PILLARS = [
  { name: "score_dispersion",  label: "dispersion" },
  { name: "retrieval_entropy", label: "entropy" },
  { name: "rank_stability",    label: "stability" },
];

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.2, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlate();
  _buildSpine();
  _buildPillars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintScene(); },
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

function _buildPlate() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(6.6, 1.15, 0.6);
  _plate = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.32,
    transparent: true, opacity: 0.9,
  }));
  _plate.position.set(0, 6.4, 0);
  _group.add(_plate);

  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-6, 5.6, 0), new THREE.Vector3(6, 5.6, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_UNCERTAIN, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// A central spine whose lit height gauges the COMBINED uncertainty (0 floor .. 1 full).
function _buildSpine() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(0.5, 5.0, 0.5);
  _spine = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_UNCERTAIN, emissive: C_UNCERTAIN, emissiveIntensity: 0.3,
    transparent: true, opacity: 0.55,
  }));
  _spine.position.set(0, 2.5, -2.2);
  _group.add(_spine);
}

// Three pillars, one per honest component; height by that component's uncertainty [0,1].
function _buildPillars() {
  const THREE = _THREE;
  const n = PILLARS.length;
  const totalW = 8.4;
  const step = totalW / n;
  const startX = -totalW / 2 + step / 2;
  const geo = new THREE.BoxGeometry(1.5, 1.0, 1.1);

  for (let i = 0; i < n; i++) {
    const x = startX + step * i;
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: C_UNCERTAIN, emissive: C_UNCERTAIN, emissiveIntensity: 0.26,
      transparent: true, opacity: 0.9,
    }));
    mesh.scale.y = 0.4;
    mesh.position.set(x, 0.2, 0);
    _group.add(mesh);
    _pillars.push({ mesh, name: PILLARS[i].name, u: 0 });
  }
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.query   = j && j.query != null ? String(j.query) : null;
  S.k       = j && typeof j.k === "number" ? j.k : null;
  S.n       = j && typeof j.results_retrieved === "number" ? j.results_retrieved : null;
  S.u       = j && typeof j.uncertainty === "number" ? j.uncertainty : null;
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.abstain = j && typeof j.abstain_recommended === "boolean" ? j.abstain_recommended : null;

  const c = (j && j.components) || {};
  const cu = (name) => (c[name] && typeof c[name].uncertainty === "number") ? c[name].uncertainty : null;
  S.disp = cu("score_dispersion");
  S.ent  = cu("retrieval_entropy");
  S.stab = cu("rank_stability");

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _paintScene();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.07;
  const live = S.state === "live";
  if (_plate) {
    _plate.material.emissiveIntensity = 0.32 + (live ? 0.22 : 0.06) * (0.5 + 0.5 * Math.sin(t * 0.003));
  }
  for (let i = 0; i < _pillars.length; i++) {
    const p = _pillars[i];
    p.mesh.material.emissiveIntensity = (live ? 0.28 : 0.1) + (live ? 0.18 : 0.0) * (0.5 + 0.5 * Math.sin(t * 0.002 + i));
    p.mesh.material.opacity = live ? 0.92 : 0.4;
  }
}

// =============================================================================
function _paintScene() {
  const live = S.state === "live";
  const col = _verdictColor(live ? S.verdict : null);
  if (_plate) { _plate.material.color.setHex(col); _plate.material.emissive.setHex(col); }

  if (_spine) {
    const u = (live && typeof S.u === "number") ? S.u : 0;
    const h = 0.3 + u * 4.7;                  // gauge height by combined uncertainty
    _spine.scale.y = h / 5.0;
    _spine.position.y = h / 2;
    _spine.material.color.setHex(col);
    _spine.material.emissive.setHex(col);
  }

  const vals = { score_dispersion: S.disp, retrieval_entropy: S.ent, rank_stability: S.stab };
  for (const p of _pillars) {
    const u = (live && typeof vals[p.name] === "number") ? vals[p.name] : 0;
    p.u = u;
    const h = 0.4 + u * 4.4;                  // height by component uncertainty
    p.mesh.scale.y = h;
    p.mesh.position.y = h / 2;
    // a component >= 0.5 (the "never CONFIDENT" cap) glows in the high-uncertainty hue.
    const pcol = !live ? C_NEUTRAL : (u >= 0.5 ? C_HIGH : C_CONFIDENT);
    p.mesh.material.color.setHex(pcol);
    p.mesh.material.emissive.setHex(pcol);
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "calibration", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Calibrated, <b>honest uncertainty</b> on a brain retrieval. It reads the same honest ranked ' +
    'retrieval the brain already serves and derives three explainable measures — <b>score ' +
    'dispersion</b> (how flat the top scores are), <b>retrieval entropy</b> (how smeared the ' +
    'result mass is across graph communities), and <b>rank stability</b> (how fragile the top-k ' +
    'ordering is) — into one uncertainty in [0,1] with a verdict: <b>CONFIDENT / UNCERTAIN / ' +
    'HIGHLY-UNCERTAIN</b> (which recommends you <b>abstain</b>). <b>Never CONFIDENT</b> when ' +
    'dispersion or entropy is high. This is <b>calibration honesty, not a probability ' +
    'guarantee</b> — Λ = Conjecture 1, advisory. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bu-verdict", "verdict"));
  grid.appendChild(kpiRow("bu-unc",     "uncertainty [0,1]"));
  grid.appendChild(kpiRow("bu-abstain", "recommend abstain"));
  grid.appendChild(kpiRow("bu-query",   "query"));
  grid.appendChild(kpiRow("bu-n",       "results retrieved"));
  grid.appendChild(kpiRow("bu-disp",    "· score dispersion"));
  grid.appendChild(kpiRow("bu-ent",     "· retrieval entropy"));
  grid.appendChild(kpiRow("bu-stab",    "· rank stability"));
  grid.appendChild(kpiRow("bu-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bu-trust",   "trust ceiling"));
  grid.appendChild(kpiRow("bu-lambda",  "Λ"));
  card.appendChild(grid);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> CONFIDENT &nbsp; ' +
    '<span style="color:#5b8dee">■</span> UNCERTAIN &nbsp; ' +
    '<span style="color:#8a6bff">■</span> HIGHLY-UNCERTAIN (abstain). ' +
    'MODELED · calibration honesty, not a probability · never CONFIDENT if dispersion/entropy high.';
  card.appendChild(leg);
  host.appendChild(card);

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
  pd.id = "bu-plain";
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
    "<b>What this means:</b> an honest read on <b>how sure the brain is</b> about what it just " +
    "retrieved — before it answers. If one result clearly stands out, sits in a single coherent " +
    "topic cluster, and holds its rank, the retrieval is <b>CONFIDENT</b>. If the results are all " +
    "about equally weighted, scattered across many topics, or teetering on ties, it is " +
    "<b>UNCERTAIN</b> or <b>HIGHLY-UNCERTAIN</b> — and it openly recommends the system <b>abstain</b> " +
    "rather than bluff. It can <b>never</b> read CONFIDENT while the results are flat or scattered. " +
    "This is a measure of the retrieval's own shape — <b>not</b> a promise the answer is right.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _n(v) { return v == null ? "—" : String(v); }
function _f(v) { return typeof v === "number" ? v.toFixed(3) : "—"; }

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "calibration" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bu-verdict", vrd);
  _set("bu-unc",     t || _f(S.u));
  _set("bu-abstain", t || (S.abstain == null ? "—" : (S.abstain ? "YES — abstain" : "no")));
  _set("bu-query",   t || (S.query != null ? (S.query || "(empty)") : "—"));
  _set("bu-n",       t || _n(S.n));
  _set("bu-disp",    t || _f(S.disp));
  _set("bu-ent",     t || _f(S.ent));
  _set("bu-stab",    t || _f(S.stab));
  _set("bu-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bu-trust",   t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bu-lambda",  t || (S.lambda || "—"));
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
  _plate = _spine = null; _pillars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.query = S.verdict = null;
  S.k = S.n = S.u = S.abstain = S.disp = S.ent = S.stab = null;
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
