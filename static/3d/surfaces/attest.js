// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/attest.js — CHAIN OF TITLE · L6 ATTESTATION. The allodial claim, drawn as the thing a
// third party can actually check. One PILLAR per chain-of-title policy rule (predicate type ·
// doctrine v11 · kernel verified · honesty invariants · provenance coverage 1.0 · subject binds a
// non-empty kernel commit), a CORE orb carrying the tri-state verdict PASSED / FAILED / UNKNOWN,
// two SUBJECT anchors on the floor (the locked-8 kernel gitCommit, always bound; the sovereign
// weights sha256, drawn grey and hollow when no weights artifact is readable — an absent subject
// is SHOWN, never invented), and a TRANSPARENCY beam standing for the Rekor strand.
//
// Pure honesty / provenance / observability. It advances NO detection, fusion, effector, targeting
// or cueing capability, and it proves nothing new about the locked-8 — it ATTESTS the pin.
//
// DATA: live snapshot from GET /api/a11oy/v1/attest/manifest (PURE READ; the ledger write is
// opt-in on SZL_LAKE_DIR and never happens on this path):
//   ok, label, verdict, verdict_scope, statement_digest_sha256,
//   statement{ _type, predicateType, subject[]{name,digest}, predicate{ doctrine,
//     provenance{ corpus_sha, kernel_verified, kernel_pin, provenance_coverage },
//     energy_measured[], honesty_invariants{...}, seal{ formula, tier }, lambda{...} } },
//   envelope{ signed, payloadType, signatures[] },
//   rekor{ status (RECORDED|UNREACHABLE|NOT_ATTEMPTED), log_index, inclusion_proof, label },
//   verification{ policy{ checks{...}, failed[] }, signature{ status }, transparency{...} }.
//
// HONESTY LABEL: MODELED. It becomes MEASURED only for the transparency strand, and only when a
//   REAL Rekor inclusion proof came back in the same request — the surface reads the server's
//   label VERBATIM and never upgrades it. UNKNOWN is drawn as UNKNOWN: an unreachable
//   transparency log is never coloured as a pass. A FAILED rule is drawn tallest so it cannot
//   hide. Λ = Conjecture 1 (never a theorem, never green). Trust ceiling 0.97, never 100%. The
//   SEAL formula is shown with its tier PROPOSED attached, and no score is asserted.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (PASSED / rule holds / RECORDED),
//   lattice-blue 0x5b8dee (frame / UNKNOWN), violet-blue 0x8a6bff (FAILED / rule broken),
//   grey 0x42505d (absent subject / NOT_ATTEMPTED / init).
// 0 RUNTIME CDN. Vendored three.js via the page importmap (ctx.THREE).
// CITED PRIOR ART (SZL claims none of it as its own): in-toto Attestation Framework; SLSA v1.1
//   Build L0-L3 + Verification Summary Attestation; Sigstore/cosign keyless + Rekor; DSSE;
//   sigstore/model-transparency; EU Cloud Sovereignty Framework SEAL + HHI (the SEAL formula).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17; introduces
//   no theorem; makes no consciousness claim. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "attest";
const TITLE = "Chain of Title · L6 attestation · the allodial claim, third-party verifiable (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ attestation endpoint.
const EP = "/api/a11oy/v1/attest/manifest";

const C_OK      = 0x3af4c8;  // proof-teal   — PASSED / rule holds / RECORDED
const C_MID     = 0x5b8dee;  // lattice-blue — UNKNOWN / frame
const C_BAD     = 0x8a6bff;  // violet-blue  — FAILED / rule broken
const C_NEUTRAL = 0x42505d;  // grey         — absent subject / NOT_ATTEMPTED / init
const C_GRID    = 0x1b3a44;

// The six policy rules, in the order ops/szl_chain_of_title.rego declares them.
const RULES = [
  ["predicate_type_matches",      "predicate type"],
  ["doctrine_is_v11",             "doctrine v11"],
  ["kernel_verified",             "kernel verified"],
  ["honesty_invariants_all_true", "honesty invariants"],
  ["provenance_coverage_is_one",  "provenance 1.0"],
  ["subject_binds_kernel_commit", "subject binds kernel"],
];

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "PASSED")  return C_OK;
  if (s === "FAILED")  return C_BAD;
  if (s === "UNKNOWN") return C_MID;
  return C_NEUTRAL;
}
function _ruleColor(held) {
  if (held === true)  return C_OK;
  if (held === false) return C_BAD;
  return C_NEUTRAL;                       // not evaluated this request
}
function _rekorColor(status) {
  const s = String(status || "").toUpperCase();
  if (s === "RECORDED")    return C_OK;
  if (s === "UNREACHABLE") return C_MID;   // UNKNOWN, never a pass
  return C_NEUTRAL;                        // NOT_ATTEMPTED / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // verdict core orb
let _pillars = [];            // [{ mesh, key, held }]
let _anchors = [];            // [{ mesh, name, bound }]
let _beam = null;             // transparency (Rekor) beam
let _spin = 0;

// live state — every field read from JSON; nothing invented
const S = {
  label:       null,   // server label VERBATIM (MODELED, or MEASURED for a real inclusion proof)
  verdict:     null,   // PASSED | FAILED | UNKNOWN
  scope:       null,   // what the verdict actually covers
  stmtDigest:  null,
  predType:    null,
  doctrine:    null,
  corpusSha:   null,
  kernelPin:   null,
  kernelOk:    null,
  coverage:    null,
  invariants:  null,   // { name: bool }
  energyCount: null,   // length of energy_measured[] — 0 is the honest offline state
  sealFormula: null,
  sealTier:    null,
  lambdaStat:  null,
  lambdaThm:   null,
  trustCeil:   null,
  signed:      null,
  sigStatus:   null,
  subjects:    [],     // [{ name, bound, digest }]
  rekorStatus: null,
  rekorIndex:  null,
  rekorLabel:  null,
  rekorNote:   null,
  checks:      {},     // rule -> bool
  failed:      [],
  state:       "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 5.4, 19.0);
  try {
    if (_stage.controls && _stage.controls.target) {
      _stage.controls.target.set(0, 2.6, 0); _stage.controls.update();
    }
  } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCore();
  _buildBeam();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 12000, _onData, {
    badge: _badge,
    onState: (m) => { S.state = m.state; _paintOverlay(); _paintCore(); },
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
  _core = new THREE.Mesh(
    new THREE.OctahedronGeometry(1.7, 1),
    new THREE.MeshStandardMaterial({
      color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.34,
      transparent: true, opacity: 0.9, flatShading: true,
    }));
  _core.position.set(0, 5.0, 0);
  _group.add(_core);

  // the "deed" ring the rules stand on
  const pts = [];
  const R = 6.2;
  for (let i = 0; i <= 80; i++) {
    const a = (i / 80) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * R, 0.02, Math.sin(a) * R));
  }
  const ring = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: C_MID, transparent: true, opacity: 0.4 }));
  _group.add(ring);
}

// The TRANSPARENCY beam — the Rekor strand. Teal and solid only for a real inclusion proof;
// lattice-blue and translucent for UNREACHABLE (UNKNOWN); grey for NOT_ATTEMPTED. There is no
// state in which an unanchored attestation is drawn as anchored.
function _buildBeam() {
  const THREE = _THREE;
  _beam = new THREE.Mesh(
    new THREE.CylinderGeometry(0.16, 0.16, 9.0, 12, 1, true),
    new THREE.MeshStandardMaterial({
      color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.2,
      transparent: true, opacity: 0.22, side: THREE.DoubleSide,
    }));
  _beam.position.set(0, 9.6, 0);
  _group.add(_beam);
}

// One PILLAR per policy rule. A BROKEN rule stands tallest and reads violet so it cannot hide; an
// un-evaluated rule is a short grey stub, never a quiet pass. Rebuilt on every snapshot.
function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();

  const R = 5.4;
  const geo = new THREE.BoxGeometry(0.95, 1.0, 0.95);
  for (let i = 0; i < RULES.length; i++) {
    const key = RULES[i][0];
    const held = (key in S.checks) ? !!S.checks[key] : null;
    const color = _ruleColor(held);
    const h = held === false ? 4.9 : (held === true ? 3.4 : 1.2);
    const a = (i / RULES.length) * Math.PI * 2 - Math.PI / 2;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: held === null ? 0.4 : 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(Math.cos(a) * R, h / 2, Math.sin(a) * R);
    _group.add(mesh);
    _pillars.push({ mesh, key, held });
  }
}

// SUBJECT anchors — the two things the deed can bind. The kernel anchor is solid (its gitCommit is
// always bound). The weights anchor is drawn HOLLOW and grey when no weights artifact is readable:
// the missing subject is displayed as missing rather than filled in.
function _buildAnchors() {
  const THREE = _THREE;
  _disposeAnchors();

  const want = ["locked8_kernel", "sovereign_weights"];
  for (let i = 0; i < want.length; i++) {
    const name = want[i];
    const found = S.subjects.find((s) => s.name === name);
    const bound = !!(found && found.bound);
    const color = bound ? C_OK : C_NEUTRAL;
    const mesh = new THREE.Mesh(
      new THREE.TorusGeometry(1.05, bound ? 0.2 : 0.07, 10, 40),
      new THREE.MeshStandardMaterial({
        color, emissive: color, emissiveIntensity: bound ? 0.3 : 0.1,
        transparent: true, opacity: bound ? 0.9 : 0.35, wireframe: !bound,
      }));
    mesh.rotation.x = Math.PI / 2;
    mesh.position.set(i === 0 ? -3.1 : 3.1, 0.35, 8.4);
    _group.add(mesh);
    _anchors.push({ mesh, name, bound });
  }
}

function _rm(o) {
  if (!o) return;
  try {
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) {
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => m.dispose && m.dispose());
    }
    if (_group) _group.remove(o);
  } catch (_) {}
}
function _disposePillars() { _pillars.forEach((p) => _rm(p.mesh)); _pillars = []; }
function _disposeAnchors() { _anchors.forEach((a) => _rm(a.mesh)); _anchors = []; }

// =============================================================================
// live data — read VERBATIM, never upgrade a label, never fabricate a pass
// =============================================================================
function _onData(j) {
  const st = (j && j.statement) || {};
  const pr = (st && st.predicate) || {};
  const pv = (pr && pr.provenance) || {};
  const ver = (j && j.verification) || {};
  const pol = (ver && ver.policy) || {};
  const env = (j && j.envelope) || {};
  const rk = (j && j.rekor) || {};

  // The server's own label, verbatim. MODELED unless it reported MEASURED for a real proof.
  S.label   = j && j.label ? String(j.label).toUpperCase() : "MODELED";
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.scope   = j && j.verdict_scope ? String(j.verdict_scope) : null;
  S.stmtDigest = j && j.statement_digest_sha256 ? String(j.statement_digest_sha256) : null;

  S.predType = st.predicateType ? String(st.predicateType) : null;
  S.doctrine = pr.doctrine ? String(pr.doctrine) : null;
  S.corpusSha = typeof pv.corpus_sha === "string" ? pv.corpus_sha : null;
  S.kernelPin = pv.kernel_pin ? String(pv.kernel_pin) : null;
  S.kernelOk  = typeof pv.kernel_verified === "boolean" ? pv.kernel_verified : null;
  S.coverage  = typeof pv.provenance_coverage === "number" ? pv.provenance_coverage : null;

  S.invariants = (pr.honesty_invariants && typeof pr.honesty_invariants === "object")
    ? pr.honesty_invariants : null;
  // 0 is the HONEST offline state (no meter answered) — it is displayed as 0, not hidden.
  S.energyCount = Array.isArray(pr.energy_measured) ? pr.energy_measured.length : null;

  const seal = (pr && pr.seal) || {};
  S.sealFormula = seal.formula ? String(seal.formula) : null;
  S.sealTier    = seal.tier ? String(seal.tier).toUpperCase() : null;

  const lam = (pr && pr.lambda) || {};
  S.lambdaStat = lam.status ? String(lam.status) : null;
  S.lambdaThm  = typeof lam.is_theorem === "boolean" ? lam.is_theorem : null;
  S.trustCeil  = typeof lam.trust_ceiling === "number" ? lam.trust_ceiling : null;

  S.signed    = typeof env.signed === "boolean" ? env.signed : null;
  S.sigStatus = (ver.signature && ver.signature.status)
    ? String(ver.signature.status).toUpperCase() : null;

  const subs = Array.isArray(st.subject) ? st.subject : [];
  S.subjects = subs.map((s) => {
    const d = (s && s.digest) || {};
    const val = d.gitCommit || d.sha256 || null;
    return {
      name: s && s.name ? String(s.name) : "?",
      digest: val ? String(val) : null,
      bound: !!(val && String(val).trim()),
    };
  });

  S.rekorStatus = rk.status ? String(rk.status).toUpperCase() : null;
  S.rekorIndex  = (rk.log_index === null || rk.log_index === undefined) ? null : rk.log_index;
  S.rekorLabel  = rk.label ? String(rk.label).toUpperCase() : null;
  S.rekorNote   = rk.note ? String(rk.note) : null;

  S.checks = (pol.checks && typeof pol.checks === "object") ? pol.checks : {};
  S.failed = Array.isArray(pol.failed) ? pol.failed : [];

  _buildPillars();
  _buildAnchors();
  _paintCore();
  _paintBeam();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.07;

  const live = S.state === "live";
  if (_core) {
    _core.rotation.y += 0.004; _core.rotation.x += 0.0013;
    _core.material.emissiveIntensity =
      0.34 + (live ? 0.24 : 0.07) * (0.5 + 0.5 * Math.sin(t * 0.003));
  }
  if (_beam) {
    // The beam only pulses for a REAL inclusion proof; UNKNOWN sits still and dim.
    const recorded = S.rekorStatus === "RECORDED";
    _beam.material.emissiveIntensity =
      recorded && live ? 0.42 + 0.28 * (0.5 + 0.5 * Math.sin(t * 0.004)) : 0.16;
  }
  _anchors.forEach((a) => { a.mesh.rotation.z += a.bound ? 0.006 : 0.0015; });
  if (_pillars.length) {
    _spin = (t * 0.0002) % 1;
    const lead = Math.floor(_spin * _pillars.length);
    for (let i = 0; i < _pillars.length; i++) {
      const p = _pillars[i];
      const base = p.held === false ? 0.62 : (p.held === true && live ? 0.26 : 0.11);
      p.mesh.material.emissiveIntensity = (i === lead && live) ? Math.max(base, 0.85) : base;
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

function _paintBeam() {
  if (!_beam) return;
  const col = (S.state === "live") ? _rekorColor(S.rekorStatus) : C_NEUTRAL;
  _beam.material.color.setHex(col);
  _beam.material.emissive.setHex(col);
  _beam.material.opacity = S.rekorStatus === "RECORDED" ? 0.5 : 0.2;
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "chain of title", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The allodial claim is only worth what a <b>third party can check</b>. This surface reads the ' +
    'estate\'s <b>in-toto v1 Statement</b>: its <b>subject</b> binds the locked-8 kernel ' +
    '<b>gitCommit c7c0ba17</b> (and a sovereign-weights sha256 only when a real weights artifact ' +
    'is readable that request — the hollow grey ring is an <i>absent</i> subject, shown rather ' +
    'than invented); its <b>predicate</b> carries doctrine v11, the provenance strand ' +
    '(corpus_sha, training config read verbatim from the committed trainer, kernel_verified ' +
    're-checked against the digest-verified formula registry), <b>energy_measured[]</b> — empty ' +
    'when no joule meter answered — and the <b>honesty_invariants</b> themselves, bound INTO the ' +
    'signed predicate so the doctrine becomes checkable rather than asserted. It is DSSE-signed ' +
    'with the estate cosign key and structured for cosign keyless + <b>Rekor</b>. The verdict is ' +
    'tri-state: <b>PASSED</b>, <b>FAILED</b>, or <b>UNKNOWN</b> when a required transparency-log ' +
    'inclusion proof cannot be obtained. A tampered Statement is FAILED — <b>FAILED beats ' +
    'UNKNOWN</b>, so nothing hides behind an offline log. Strictly provenance/observability; adds ' +
    'nothing to the locked-8. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("at-verdict",  "verdict"));
  grid.appendChild(kpiRow("at-scope",    "verdict covers"));
  grid.appendChild(kpiRow("at-rules",    "policy rules held"));
  grid.appendChild(kpiRow("at-failed",   "failed rules"));
  grid.appendChild(kpiRow("at-predtype", "predicate type"));
  grid.appendChild(kpiRow("at-doctrine", "doctrine"));
  grid.appendChild(kpiRow("at-kernel",   "kernel verified @ pin"));
  grid.appendChild(kpiRow("at-subjects", "subjects bound"));
  grid.appendChild(kpiRow("at-corpus",   "corpus sha256"));
  grid.appendChild(kpiRow("at-coverage", "provenance coverage"));
  grid.appendChild(kpiRow("at-energy",   "energy_measured readings"));
  grid.appendChild(kpiRow("at-sig",      "DSSE signature"));
  grid.appendChild(kpiRow("at-rekor",    "Rekor transparency"));
  grid.appendChild(kpiRow("at-digest",   "statement sha256"));
  grid.appendChild(kpiRow("at-seal",     "SEAL formula (tier)"));
  grid.appendChild(kpiRow("at-lambda",   "Λ"));
  grid.appendChild(kpiRow("at-ceil",     "trust ceiling"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> PASSED / rule holds / RECORDED &nbsp; ' +
    '<span style="color:#5b8dee">■</span> UNKNOWN (log unreachable) &nbsp; ' +
    '<span style="color:#8a6bff">■</span> FAILED / rule broken &nbsp; ' +
    '<span style="color:#8494a1">■</span> absent subject / NOT_ATTEMPTED. ' +
    'MODELED — MEASURED only for a real Rekor inclusion proof returned that request. ' +
    'Prior art cited, none claimed as SZL\'s: in-toto · SLSA v1.1 (Build L0-L3 + VSA) · ' +
    'Sigstore/Rekor keyless · DSSE · sigstore/model-transparency · EU CSF SEAL + HHI. ' +
    'Λ = Conjecture 1, never a theorem.';
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
  pd.id = "at-plain";
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
    "<b>What this means:</b> think of a property <b>deed</b>. Saying “we own this outright” is a " +
    "claim; a deed is something a stranger can take to a registry and check. This surface is the " +
    "deed for the software: a signed document that names exactly <i>what</i> is being claimed " +
    "(the pinned proof kernel, and the model weights when a real weights file is there to point " +
    "at), <i>where it came from</i> (which corpus, which training settings, read out of the " +
    "actual training script rather than typed in by hand), and <i>which honesty rules the estate " +
    "binds itself to</i> — those rules sit inside the signed document, so breaking one breaks the " +
    "signature's claim. Then it tries to file that deed in a public append-only log (Rekor), the " +
    "way you would record a deed at a county office. " +
    "<b>The important part is what happens when something is missing.</b> No weights file, so no " +
    "weights line on the deed — you see a hollow grey ring, not a made-up number. No power meter " +
    "answering, so the energy list reads <b>0 readings</b>, not an estimate dressed up as a " +
    "measurement. The public log unreachable, so the verdict reads <b>UNKNOWN</b> — not " +
    "“passed”. And if the document itself has been altered, the verdict is <b>FAILED</b>, which " +
    "always wins over UNKNOWN, so a tamper can never hide behind an offline log. " +
    "Right now it reads: <b>" + (S.verdict || "—") + "</b> — " + (S.scope || "no live snapshot") +
    ". Λ stays <b>Conjecture 1</b> — a conjecture, never a theorem; confidence never reaches 100%.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _short(h, n) {
  if (!h) return "—";
  const s = String(h);
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "chain of title" });
    _show.setChip("vrd", t || (S.verdict || "—"), { text: "verdict" });
  }
  const keys = RULES.map((r) => r[0]);
  const held = keys.filter((k) => S.checks[k] === true).length;
  const evaluated = keys.filter((k) => k in S.checks).length;

  _set("at-verdict",  t || (S.verdict || "—"));
  _set("at-scope",    t || (S.scope || "—"));
  _set("at-rules",    t || (evaluated ? held + " / " + evaluated : "—"));
  _set("at-failed",   t || (S.failed && S.failed.length ? S.failed.join(", ") : "none"));
  _set("at-predtype", t || (S.predType || "—"));
  _set("at-doctrine", t || (S.doctrine || "—"));
  _set("at-kernel",   t || (S.kernelOk === null ? "—"
    : (S.kernelOk ? "verified" : "NOT VERIFIED") + " @ " + (S.kernelPin || "—")));
  _set("at-subjects", t || (S.subjects.length
    ? S.subjects.map((s) => s.name + (s.bound ? " ✓" : " (absent)")).join(", ")
    : "—"));
  // An absent corpus digest reads ABSENT, never a placeholder hash.
  _set("at-corpus",   t || (S.corpusSha ? _short(S.corpusSha, 18) : "ABSENT (honest null)"));
  _set("at-coverage", t || (S.coverage === null ? "—" : String(S.coverage)));
  _set("at-energy",   t || (S.energyCount === null ? "—"
    : S.energyCount + (S.energyCount === 0 ? " (no meter answered)" : " MEASURED")));
  _set("at-sig",      t || (S.sigStatus || (S.signed === false ? "UNSIGNED-NO-KEY" : "—")));
  _set("at-rekor",    t || (S.rekorStatus
    ? S.rekorStatus + (S.rekorIndex !== null ? " · index " + S.rekorIndex : "")
    : "—"));
  _set("at-digest",   t || _short(S.stmtDigest, 18));
  _set("at-seal",     t || (S.sealFormula
    ? S.sealFormula + " (" + (S.sealTier || "PROPOSED") + ")" : "—"));
  _set("at-lambda",   t || (S.lambdaStat
    ? S.lambdaStat + (S.lambdaThm === false ? " (not a theorem)" : "") : "—"));
  _set("at-ceil",     t || (S.trustCeil === null ? "—" : String(S.trustCeil)));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposePillars();
    _disposeAnchors();
    _rm(_beam); _beam = null;
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
  _core = null; _pillars = []; _anchors = []; _beam = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.scope = S.stmtDigest = null;
  S.predType = S.doctrine = S.corpusSha = S.kernelPin = null;
  S.kernelOk = S.coverage = S.invariants = S.energyCount = null;
  S.sealFormula = S.sealTier = S.lambdaStat = S.lambdaThm = S.trustCeil = null;
  S.signed = S.sigStatus = null;
  S.subjects = [];
  S.rekorStatus = S.rekorIndex = S.rekorLabel = S.rekorNote = null;
  S.checks = {}; S.failed = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
