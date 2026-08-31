// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainanswer.js — BRAIN ANSWER · the governed honest-answer synthesizer. The capstone
// over the brain-honesty surfaces: ONE endpoint that answers a question with a full honesty
// dossier, or abstains honestly. This surface renders that as a CORE orb carrying the governed
// verdict (ANSWERED-GOVERNED / ANSWERED-WITH-CAVEATS / ABSTAINED / INSUFFICIENT-SIGNAL) ringed by
// one PILLAR per dossier FACET — grounding, provenance chain, uncertainty, contradiction flags,
// constitution compliance — each coloured by the facet's OWN verbatim state. Pure knowledge-graph
// reasoning honesty; it advances NO detection / fusion / effector / targeting / cueing capability.
//
// An UNAVAILABLE facet reads grey — never dressed up as a pass. An adverse facet reads violet and
// stands tall so it cannot hide. The core is NEVER teal ("ANSWERED-GOVERNED") while the feed
// reports an abstention, a caveat, or an unavailable facet: the verdict shown is the verdict the
// endpoint returned, read VERBATIM, never upgraded in the renderer.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/answer (PURE READ, mints nothing):
//   ok, label (MODELED), governed_verdict, governed_verdict_reason, caveats[],
//   answer{ evidence_nodes, modeled_confidence, carries_caveats } | null,
//   honesty_dossier{ grounding, provenance, uncertainty, contradiction, constitution }
//     each { available, label, verdict },
//   summary{ facets_total, facets_available, min_facets_required, agent_state,
//            constitution_state, contradiction_state, caveat_count, answer_present },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// HONESTY LABEL: MODELED — a governed synthesis over MODELED retrieval and MODELED sibling
//   verdicts, never a MEASURED answer. Facet labels/verdicts are rendered verbatim; nothing is
//   upgraded. No green "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (ANSWERED-GOVERNED / healthy
//   facet), lattice-blue 0x5b8dee (ANSWERED-WITH-CAVEATS / frame), violet-blue 0x8a6bff
//   (ABSTAINED / adverse facet), grey 0x42505d (INSUFFICIENT-SIGNAL / UNAVAILABLE / init).
//   No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainanswer";
const TITLE = "Brain Answer · governed honest-answer synthesizer (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ synthesis endpoint.
const EP = "/api/a11oy/v1/brain/answer";

// verdict / facet hues — approved palette only, no green
const C_OK      = 0x3af4c8;  // proof-teal   — ANSWERED-GOVERNED / healthy facet
const C_MID     = 0x5b8dee;  // lattice-blue — ANSWERED-WITH-CAVEATS / frame
const C_ADVERSE = 0x8a6bff;  // violet-blue  — ABSTAINED / adverse facet
const C_NEUTRAL = 0x42505d;  // grey         — INSUFFICIENT-SIGNAL / UNAVAILABLE / init
const C_GRID    = 0x1b3a44;  // floor colour

// the five dossier facets, in the order the endpoint documents them
const FACETS = ["grounding", "provenance", "uncertainty", "contradiction", "constitution"];

// adverse / weak verdict tokens, matched VERBATIM against the facet's own verdict string
const ADVERSE_TOKENS = ["IN-VIOLATION", "CONFLICT-FLAGGED", "UNTRACEABLE", "UNKNOWN-ORIGIN"];
const WEAK_TOKENS = ["WEAK", "INSUFFICIENT", "UNCERTAIN", "PARTIAL", "STALE", "SPARSE",
                     "GAP", "SINGLE-SOURCE", "POSSIBLE-CONFLICT"];

// overall governed verdict -> core colour
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "ANSWERED-GOVERNED")     return C_OK;
  if (s === "ANSWERED-WITH-CAVEATS") return C_MID;
  if (s === "ABSTAINED")             return C_ADVERSE;
  if (s === "INSUFFICIENT-SIGNAL")   return C_NEUTRAL;
  return C_NEUTRAL;                  // init / unknown
}

// per-facet state, read VERBATIM: OK | WEAK | ADVERSE | UNAVAILABLE
function _facetState(f) {
  if (!f || f.available !== true) return "UNAVAILABLE";
  const v = String(f.verdict || "").toUpperCase();
  if (!v) return "UNAVAILABLE";
  for (let i = 0; i < ADVERSE_TOKENS.length; i++) {
    if (v.indexOf(ADVERSE_TOKENS[i]) >= 0) return "ADVERSE";
  }
  for (let i = 0; i < WEAK_TOKENS.length; i++) {
    if (v.indexOf(WEAK_TOKENS[i]) >= 0) return "WEAK";
  }
  if (String(f.label || "").toUpperCase() === "UNAVAILABLE") return "UNAVAILABLE";
  return "OK";
}

function _stateColor(s) {
  if (s === "OK")      return C_OK;
  if (s === "WEAK")    return C_MID;
  if (s === "ADVERSE") return C_ADVERSE;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the governed-verdict core orb
let _pillars = [];            // Array<{ mesh, key, state }>

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,  // top honesty label VERBATIM (MODELED)
  verdict:    null,  // ANSWERED-GOVERNED | ANSWERED-WITH-CAVEATS | ABSTAINED | INSUFFICIENT-SIGNAL
  reason:     null,
  caveats:    [],
  answerPresent: null,
  evidence:   null,
  confidence: null,  // MODELED, capped at 0.97, never MEASURED, never 1.0
  facetsTotal:     null,
  facetsAvailable: null,
  minFacets:  null,
  agentState: null,
  constState: null,
  contraState: null,
  facets:     [],    // [{ key, state, verdict, label }]
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
  _stage.camera.position.set(0, 5.2, 18);
  try {
    if (_stage.controls && _stage.controls.target) {
      _stage.controls.target.set(0, 2.4, 0); _stage.controls.update();
    }
  } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 9000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintCore(); },
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

function _buildCore() {
  const THREE = _THREE;
  const g = new THREE.OctahedronGeometry(1.6, 1);
  _core = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.34,
    transparent: true, opacity: 0.9, flatShading: true,
  }));
  _core.position.set(0, 4.8, 0);
  _group.add(_core);

  // dossier rail beneath the core
  const pts = [];
  const R = 5.8;
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * R, 0.02, Math.sin(a) * R));
  }
  const rg = new THREE.BufferGeometry().setFromPoints(pts);
  const ring = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_MID, transparent: true, opacity: 0.4,
  }));
  _group.add(ring);
}

// One PILLAR per dossier facet, in a ring; colour by the VERBATIM facet state, height by how
// loudly it must be seen (an adverse facet stands tallest so it cannot hide; an UNAVAILABLE
// facet is a short grey stub — honest, never a fabricated pass).
function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();

  const facets = Array.isArray(S.facets) ? S.facets : [];
  const n = facets.length;
  if (!n) return;
  const R = 5.0;
  const geo = new THREE.BoxGeometry(0.85, 1.0, 0.85);

  for (let i = 0; i < n; i++) {
    const f = facets[i];
    const color = _stateColor(f.state);
    const h = f.state === "ADVERSE" ? 4.8 : (f.state === "OK" ? 3.4
              : (f.state === "WEAK" ? 2.4 : 1.1));
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: f.state === "UNAVAILABLE" ? 0.42 : 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, z);
    _group.add(mesh);

    _pillars.push({ mesh, key: f.key, state: f.state });
  }
}

function _disposePillars() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) {
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach((m) => m.dispose && m.dispose());
      }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _pillars.forEach((p) => rm(p.mesh));
  _pillars = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade, never fabricate an answer
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.governed_verdict ? String(j.governed_verdict).toUpperCase() : null;
  S.reason  = j && j.governed_verdict_reason ? String(j.governed_verdict_reason) : null;
  S.caveats = Array.isArray(j && j.caveats) ? j.caveats.map((c) => String(c)) : [];

  const ans = (j && j.answer) || null;
  S.answerPresent = ans ? true : false;
  S.evidence   = ans && typeof ans.evidence_nodes === "number" ? ans.evidence_nodes : null;
  S.confidence = ans && typeof ans.modeled_confidence === "number" ? ans.modeled_confidence : null;

  const sm = (j && j.summary) || {};
  S.facetsTotal     = typeof sm.facets_total === "number" ? sm.facets_total : null;
  S.facetsAvailable = typeof sm.facets_available === "number" ? sm.facets_available : null;
  S.minFacets   = typeof sm.min_facets_required === "number" ? sm.min_facets_required : null;
  S.agentState  = sm.agent_state ? String(sm.agent_state) : null;
  S.constState  = sm.constitution_state ? String(sm.constitution_state) : null;
  S.contraState = sm.contradiction_state ? String(sm.contradiction_state) : null;

  const dos = (j && j.honesty_dossier) || {};
  S.facets = FACETS.map((key) => {
    const f = dos[key] || null;
    return {
      key,
      state: _facetState(f),
      verdict: f && f.verdict ? String(f.verdict).toUpperCase() : null,
      label: f && f.label ? String(f.label).toUpperCase() : "UNAVAILABLE",
    };
  });

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildPillars();
  _paintCore();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.08;

  const live = S.state === "live";
  if (_core) {
    _core.rotation.y += 0.0038; _core.rotation.x += 0.0014;
    const pulse = 0.34 + (live ? 0.24 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _core.material.emissiveIntensity = pulse;
  }
  if (_pillars.length) {
    const sweep = (t * 0.0002) % 1;
    const front = Math.floor(sweep * _pillars.length);
    for (let i = 0; i < _pillars.length; i++) {
      const p = _pillars[i];
      const near = i === front;
      // an ADVERSE facet always glows hot (a violation must never hide); others follow the sweep
      const adverse = p.state === "ADVERSE";
      const base = adverse ? 0.62 : (p.state === "OK" && live ? 0.26 : 0.12);
      p.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.85) : base;
    }
  }
}

// =============================================================================
function _paintCore() {
  if (!_core) return;
  const col = (S.state === "live") ? _verdictColor(S.verdict) : C_NEUTRAL;
  _core.material.color.setHex(col);
  _core.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "synthesis", name: "lbl" },
            { label: "—", text: "governed verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'One endpoint over the whole brain-honesty family: ask a question, get a <b>single ' +
    'governed answer object</b> — or an honest abstention. The <b>answer</b> comes only from ' +
    'the honesty-gated traversal (<b>brainagent</b>); a confident answer the traversal could ' +
    'not ground is never produced. Around it sits the <b>honesty dossier</b>: grounding, ' +
    'provenance chain, uncertainty, contradiction flags and per-query constitutional ' +
    'compliance, each read <b>verbatim</b> under its own honest label, with a missing sibling ' +
    'reading <b>UNAVAILABLE</b> rather than fabricated. The governed verdict only ever ' +
    '<b>downgrades</b>: it can never read ANSWERED-GOVERNED while the constitution is ' +
    'IN-VIOLATION, while the traversal abstained, or while a contradiction is ' +
    'CONFLICT-FLAGGED. Strictly knowledge-graph reasoning honesty. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;" +
                       "padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf";
    l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;" +
                      "max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("ba-verdict",  "governed verdict"));
  grid.appendChild(kpiRow("ba-answer",   "answer present"));
  grid.appendChild(kpiRow("ba-evidence", "grounded evidence nodes"));
  grid.appendChild(kpiRow("ba-conf",     "modeled confidence"));
  grid.appendChild(kpiRow("ba-facets",   "facets (available/total)"));
  grid.appendChild(kpiRow("ba-agent",    "traversal state"));
  grid.appendChild(kpiRow("ba-const",    "constitution state"));
  grid.appendChild(kpiRow("ba-contra",   "contradiction state"));
  grid.appendChild(kpiRow("ba-caveats",  "caveats"));
  grid.appendChild(kpiRow("ba-locked",   "locked proofs"));
  grid.appendChild(kpiRow("ba-ceil",     "trust ceiling"));
  grid.appendChild(kpiRow("ba-lambda",   "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> ANSWERED-GOVERNED / healthy facet &nbsp; ' +
    '<span style="color:#5b8dee">■</span> ANSWERED-WITH-CAVEATS / weak facet &nbsp; ' +
    '<span style="color:#8a6bff">■</span> ABSTAINED / adverse facet &nbsp; ' +
    '<span style="color:#8494a1">■</span> INSUFFICIENT-SIGNAL / UNAVAILABLE. ' +
    'MODELED · facet verdicts read verbatim · no answer is fabricated on abstention.';
  card.appendChild(leg);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;" +
                     "border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;" +
                     "width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ba-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;" +
                     "border-radius:7px;padding:7px 9px;display:none";
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
    "<b>What this means:</b> this is the one place you ask the brain a question and get an " +
    "answer <i>with its homework attached</i>. The answer itself is only ever what the brain " +
    "could actually trace through its own knowledge graph — if it could not trace it, you get " +
    "a plain <b>“I am not answering that”</b> instead of a confident guess. Alongside the " +
    "answer you always get the receipts: how well grounded it was, where it came from, how " +
    "uncertain it is, whether anything in the knowledge base disagrees, and whether the " +
    "answer obeys the brain’s own written rules. If a checker is not wired in this build it " +
    "says <b>UNAVAILABLE</b> — it never pretends that check passed. And the verdict can only " +
    "get <i>more</i> cautious, never less: a broken rule, an abstention, or an unresolved " +
    "disagreement always forces an abstention, no matter how good the rest looks. No " +
    "“verified / 1.0” state; confidence is capped at 0.97, never 100%.";
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

function _paintOverlay() {
  const t = _tok(S.state);
  const headline = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "synthesis" });
    _show.setChip("vrd", headline, { text: "governed verdict" });
  }
  _set("ba-verdict",  t || (S.verdict || "—"));
  _set("ba-answer",   t || (S.answerPresent == null ? "—"
                            : (S.answerPresent ? "yes" : "no (honest abstention)")));
  _set("ba-evidence", t || _n(S.evidence));
  _set("ba-conf",     t || (S.confidence != null ? String(S.confidence) : "—"));
  _set("ba-facets",   t || (S.facetsAvailable != null && S.facetsTotal != null
    ? S.facetsAvailable + " / " + S.facetsTotal : _n(S.facetsTotal)));
  _set("ba-agent",    t || _n(S.agentState));
  _set("ba-const",    t || _n(S.constState));
  _set("ba-contra",   t || _n(S.contraState));
  _set("ba-caveats",  t || (S.caveats && S.caveats.length ? String(S.caveats.length) : "none"));
  _set("ba-locked",   t || (S.locked != null ? String(S.locked) : "—"));
  _set("ba-ceil",     t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("ba-lambda",   t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposePillars();
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
  _core = null; _pillars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.reason = null; S.caveats = [];
  S.answerPresent = S.evidence = S.confidence = null;
  S.facetsTotal = S.facetsAvailable = S.minFacets = null;
  S.agentState = S.constState = S.contraState = null;
  S.facets = [];
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
