// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/supplychain.js — MODEL-ARTIFACT PROVENANCE (SLSA · in-toto · Rekor · C2PA).
//
// The model supply chain rendered as a governed, honestly-labeled pipeline: a weight
// artifact travels weights → build → attestation → deploy, each stage emitting a named
// provenance artifact (in-toto Statement, SLSA provenance predicate, DSSE envelope + Rekor
// inclusion proof, C2PA manifest). SLSA maturity is shown VERBATIM — L1 honest / L2
// attested / L3 roadmap — and NEVER upgraded past what is earned.
//
// DATA: live snapshot from the same-origin endpoint /api/a11oy/v1/frontier/supplychain:
//   label (MODELED, VERBATIM), slsa_ladder{levels[], highest_earned}, supply_chain{stages[]},
//   evidence_types{}, micro_artifact{ label, verify_ok, dsse{signed}, merkle_root },
//   doctrine{ trust_ceiling, lambda }, sources{}.
//
// VISUALIZES:
//   1. a four-STAGE PIPELINE — stacked nodes weights→build→attestation→deploy along z, each
//      tinted by its honest SLSA level (L1 honest = proof-teal earned, L2 attested = lattice-
//      blue modeled, L3 roadmap = grey, NOT earned). A proof-teal provenance packet travels
//      the pipeline carrying the evidence forward.
//   2. a SLSA LADDER — three rungs; only the L1 rung glows earned (proof-teal); L2 is modeled
//      (lattice-blue), L3 is greyed roadmap. No rung ever shows a green "verified/1.0" state.
//   3. a TRANSPARENCY-LOG node — a small Merkle glyph at the attestation stage; it pulses
//      proof-teal ONCE when the real in-toto/DSSE micro-artifact roundtrip returns MEASURED;
//      dim grey + "STUB" on HONEST-STUB. The DSSE signature node stays GREYED (UNSIGNED-LOCAL
//      — no key in the sandbox), never lit as signed.
//
// PRIMARY SOURCES (cited verbatim on-surface; 0 runtime CDN, no URL fetch):
//   SLSA v1.0 (slsa.dev) · in-toto USENIX Security 2019 · Sigstore/Rekor ACM CCS 2022
//   (DOI 10.1145/3548606.3560596) · C2PA spec · DSSE (secure-systems-lab).
//
// HONESTY LABEL: MODELED — structural/parameterized provenance surface, explicitly NOT
//   VERIFIED; no live L3 builder, no real Rekor, no real cosign signature on this read path.
//   The ONE narrowly MEASURED tile is the toy in-toto→DSSE→Merkle roundtrip (plumbing only;
//   signature is the honest placeholder; not model-scale). Read VERBATIM from JSON; never
//   upgraded here. SLSA never upgraded. Trust ceiling 0.97, NEVER 100%.
// COLOURS: lattice-blue 0x5b8dee (pipeline body / L2 modeled), violet-blue 0x8a6bff (data-viz
//   marker), proof-teal 0x3af4c8 (L1 earned / provenance packet / MEASURED pulse), greys
//   (pending / L3 roadmap / greyed signature / STUB). PURPLE BANNED. No green/1.0 state.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "supplychain";
const TITLE = "Model-Artifact Provenance · SLSA / in-toto / Rekor / C2PA (live)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/frontier/supplychain";

// data-viz hues — purple BANNED, no green
const C_BODY    = 0x5b8dee;  // lattice-blue (pipeline body / L2 modeled)
const C_PACKET  = 0x3af4c8;  // proof-teal (provenance packet / L1 earned / MEASURED pulse)
const C_MARKER  = 0x8a6bff;  // violet-blue (data-viz marker)
const C_DIM     = 0x42505d;  // grey (pending / L3 roadmap / greyed signature / STUB)
const C_GRID    = 0x1b3a44;  // floor / link colour

const N_STAGES  = 4;         // weights, build, attestation, deploy
const STAGE_GAP = 2.6;       // world-units between stages along z

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _nodes = [];        // Array<{ mesh, ring }> — stage nodes weights→deploy
let _links = [];        // Array<THREE.Line> — stage-to-stage links
let _packet = null;     // THREE.Mesh — traveling provenance packet
let _rungs = [];        // Array<THREE.Mesh> — SLSA ladder rungs L1/L2/L3
let _logGlyph = null;   // THREE.Mesh — transparency-log Merkle glyph (attestation stage)
let _sigNode = null;    // THREE.Mesh — DSSE signature node (greyed = unsigned)
let _floor = null;
let _pulseT = -1;       // >=0 while a MEASURED roundtrip pulse is animating

// live state (all read from JSON; nothing invented)
const S = {
  label:        null,   // top honesty label VERBATIM (MODELED)
  notVerified:  null,
  stages:       null,   // [{stage, slsa, label}]
  highestEarned:null,   // "L1"
  ladder:       null,   // [{level, claim, earned}]
  microLabel:   null,   // MEASURED | HONEST-STUB
  verifyOk:     null,
  dsseSigned:   null,   // expected false (UNSIGNED-LOCAL)
  merkleRoot:   null,
  subjectSha:   null,
  trustCeil:    null,
  lambda:       null,
  slsaL1:       null, slsaL2: null, slsaL3: null,  // verbatim level labels
  state:        "init",
};

// SLSA level -> colour: L1 earned = proof-teal, L2 modeled = lattice-blue, L3 roadmap = grey.
function _slsaColor(slsa) {
  if (typeof slsa !== "string") return C_DIM;
  if (slsa.indexOf("L1") >= 0) return C_PACKET;
  if (slsa.indexOf("L2") >= 0) return C_BODY;
  return C_DIM; // L3 roadmap / unknown -> grey
}

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(8, 6, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPipeline();
  _buildLadder();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 6000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _updateScene(); _paintOverlay(); },
  }));

  _buildOverlay();
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

// Four-stage pipeline weights→build→attestation→deploy along z; a provenance packet travels
// it; the attestation stage hosts a Merkle transparency-log glyph + a greyed signature node.
function _buildPipeline() {
  const THREE = _THREE;
  const nodeGeo = new THREE.IcosahedronGeometry(0.7, 1);
  const ringGeo = new THREE.TorusGeometry(1.0, 0.05, 8, 28);
  const z0 = -((N_STAGES - 1) * STAGE_GAP) / 2;

  for (let i = 0; i < N_STAGES; i++) {
    const z = z0 + i * STAGE_GAP;
    const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.18,
      transparent: true, opacity: 0.55, wireframe: true,
    }));
    mesh.position.set(-3.5, 1.6, z);
    _group.add(mesh);
    const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
      color: C_DIM, transparent: true, opacity: 0.0,
    }));
    ring.position.copy(mesh.position); ring.rotation.x = Math.PI / 2;
    _group.add(ring);
    _nodes.push({ mesh, ring });

    if (i > 0) {
      const link = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-3.5, 1.6, z0 + (i - 1) * STAGE_GAP),
          new THREE.Vector3(-3.5, 1.6, z),
        ]),
        new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.5 }));
      _group.add(link);
      _links.push(link);
    }
  }

  // provenance packet — small proof-teal octahedron traveling weights->deploy.
  _packet = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.26, 0),
    new THREE.MeshStandardMaterial({ color: C_PACKET, emissive: C_PACKET, emissiveIntensity: 0.6, transparent: true, opacity: 0.95 }),
  );
  _packet.position.set(-3.5, 1.6, z0);
  _group.add(_packet);

  // transparency-log Merkle glyph at the attestation stage (index 2).
  const attestZ = z0 + 2 * STAGE_GAP;
  _logGlyph = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.42, 0),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.5, wireframe: true }),
  );
  _logGlyph.position.set(-3.5, 3.1, attestZ);
  _group.add(_logGlyph);

  // DSSE signature node — stays GREYED (UNSIGNED-LOCAL, no key in sandbox); never lit signed.
  _sigNode = new THREE.Mesh(
    new THREE.SphereGeometry(0.3, 16, 12),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.08, transparent: true, opacity: 0.35 }),
  );
  _sigNode.position.set(-2.4, 3.1, attestZ);
  _group.add(_sigNode);
}

// SLSA ladder: three rungs. L1 earned (proof-teal), L2 modeled (lattice-blue), L3 grey roadmap.
function _buildLadder() {
  const THREE = _THREE;
  const rungGeo = new THREE.BoxGeometry(2.4, 0.28, 0.28);
  for (let i = 0; i < 3; i++) {
    const rung = new THREE.Mesh(rungGeo, new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15,
      transparent: true, opacity: 0.5,
    }));
    rung.position.set(5.5, 0.9 + i * 1.3, 0);
    _group.add(rung);
    _rungs.push(rung);
  }
  // rails
  for (const x of [4.4, 6.6]) {
    const rail = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, 0.6, 0), new THREE.Vector3(x, 0.9 + 2 * 1.3 + 0.4, 0),
      ]),
      new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.6 }));
    _group.add(rail);
    _links.push(rail);
  }
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label       = (j.label || "MODELED").toUpperCase();
  S.notVerified = j.not_verified === true;

  const sc = j.supply_chain || {};
  S.stages = Array.isArray(sc.stages) ? sc.stages : null;

  const ld = j.slsa_ladder || {};
  S.highestEarned = typeof ld.highest_earned === "string" ? ld.highest_earned : null;
  S.ladder = Array.isArray(ld.levels) ? ld.levels : null;

  const dl = (j.doctrine || {}).slsa_levels || {};
  S.slsaL1 = dl.L1 || null; S.slsaL2 = dl.L2 || null; S.slsaL3 = dl.L3 || null;

  const ma = j.micro_artifact || {};
  S.microLabel = typeof ma.label === "string" ? ma.label.toUpperCase() : null;
  S.verifyOk   = typeof ma.verify_ok === "boolean" ? ma.verify_ok : null;
  S.dsseSigned = ma.dsse && typeof ma.dsse.signed === "boolean" ? ma.dsse.signed : null;
  S.merkleRoot = ma.transparency_log && typeof ma.transparency_log.merkle_root === "string"
    ? ma.transparency_log.merkle_root : null;
  S.subjectSha = ma.subject && typeof ma.subject.sha256 === "string" ? ma.subject.sha256 : null;

  const d = j.doctrine || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;

  _updateScene();
  // fire a roundtrip pulse only when the real micro-artifact actually reconciled.
  if (S.microLabel === "MEASURED" && S.verifyOk === true) _pulseT = 0;
  _paintOverlay();
}

// =============================================================================
// scene updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // stage nodes tinted by honest SLSA level
  for (let i = 0; i < N_STAGES; i++) {
    const n = _nodes[i];
    if (!n) continue;
    const st = (live && S.stages && S.stages[i]) ? S.stages[i] : null;
    const c = (live && st) ? _slsaColor(st.slsa) : C_DIM;
    n.mesh.material.color.setHex(c);
    n.mesh.material.emissive.setHex(c);
    n.mesh.material.emissiveIntensity = (live && st) ? 0.45 : 0.15;
    n.mesh.material.opacity = live ? 0.9 : 0.5;
    n.mesh.material.wireframe = !(live && st);
    const earned = live && st && typeof st.slsa === "string" && st.slsa.indexOf("L1") >= 0;
    n.ring.visible = !!earned;
    if (earned) { n.ring.material.color.setHex(C_PACKET); n.ring.material.opacity = 0.85; }
  }
  _links.forEach((l) => { l.material.opacity = live ? 0.6 : 0.35; });

  // SLSA ladder rungs: L1 earned proof-teal, L2 modeled lattice-blue, L3 grey roadmap.
  const rungColors = [C_PACKET, C_BODY, C_DIM];
  for (let i = 0; i < _rungs.length; i++) {
    const r = _rungs[i];
    const lvl = S.ladder && S.ladder[i] ? S.ladder[i] : null;
    const c = live ? rungColors[i] : C_DIM;
    r.material.color.setHex(c);
    r.material.emissive.setHex(c);
    // only L1 (earned true) gets full glow; L2/L3 are dimmer (modeled / roadmap).
    const earned = lvl && lvl.earned === true;
    r.material.emissiveIntensity = live ? (earned ? 0.55 : (i === 1 ? 0.3 : 0.12)) : 0.12;
    r.material.opacity = live ? (earned ? 0.92 : 0.6) : 0.45;
  }

  // transparency-log glyph + greyed signature node
  if (_logGlyph) {
    const measured = live && S.microLabel === "MEASURED" && S.verifyOk === true;
    const c = measured ? C_PACKET : C_DIM;
    _logGlyph.material.color.setHex(c);
    _logGlyph.material.emissive.setHex(c);
    _logGlyph.material.emissiveIntensity = measured ? 0.5 : 0.18;
    _logGlyph.material.opacity = live ? 0.85 : 0.4;
    _logGlyph.material.wireframe = !measured;
  }
  if (_sigNode) {
    // signature is honest UNSIGNED-LOCAL — stays grey; only faintly lit when live for presence.
    _sigNode.material.color.setHex(C_DIM);
    _sigNode.material.emissive.setHex(C_DIM);
    _sigNode.material.emissiveIntensity = 0.08;
    _sigNode.material.opacity = live ? 0.4 : 0.25;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.10;
  if (_logGlyph) { _logGlyph.rotation.y += 0.02; _logGlyph.rotation.x += 0.008; }

  // provenance packet travels weights -> deploy along the pipeline, looping.
  if (_packet && _nodes.length) {
    const z0 = _nodes[0].mesh.position.z;
    const z1 = _nodes[_nodes.length - 1].mesh.position.z;
    const phase = (t * 0.00025) % 1;
    _packet.position.z = z0 + (z1 - z0) * phase;
    _packet.rotation.y += 0.05;
    const live = S.state === "live";
    _packet.material.color.setHex(live ? C_PACKET : C_DIM);
    _packet.material.emissive.setHex(live ? C_PACKET : C_DIM);
    _packet.material.opacity = live ? 0.95 : 0.35;
    // light the stage node the packet is currently passing through
    for (let i = 0; i < _nodes.length; i++) {
      const near = Math.abs(_nodes[i].mesh.position.z - _packet.position.z) < STAGE_GAP * 0.5;
      if (near && _nodes[i].ring.visible) {
        const p = 1.0 + 0.1 * Math.sin(t * 0.004);
        _nodes[i].ring.scale.setScalar(p);
      }
    }
  }

  // live roundtrip pulse: a single proof-teal (MEASURED) surge on the transparency-log glyph
  // when the real in-toto/DSSE micro-artifact reconciled. NEVER a green/1.0 state.
  if (_pulseT >= 0 && _logGlyph) {
    _pulseT += 0.02;
    _logGlyph.material.emissive.setHex(C_PACKET);
    _logGlyph.material.emissiveIntensity = 0.3 + 0.5 * Math.max(0, Math.sin(_pulseT * Math.PI));
    if (_pulseT >= 1) { _pulseT = -1; _logGlyph.material.emissiveIntensity = 0.5; }
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [
      { label: "MODELED", text: "provenance", name: "lbl" },
      { label: "SLSA L1 honest", text: "earned", name: "slsa" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY", "MEASURED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The <b>model supply chain</b> as a governed pipeline: <b>weights → build → ' +
    'attestation → deploy</b>, each emitting a named provenance artifact — an <b>in-toto ' +
    'Statement</b>, a <b>SLSA provenance</b> predicate, a <b>DSSE</b> envelope + <b>Rekor</b> ' +
    'transparency inclusion, and a <b>C2PA</b> manifest. SLSA maturity is shown VERBATIM — ' +
    '<b>L1 honest / L2 attested / L3 roadmap</b> — and never upgraded past what is earned. ' +
    'Honesty label <b>MODELED</b> — explicitly <b>NOT VERIFIED</b>; no live L3 builder, no ' +
    'real Rekor, no real signature on this read path. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "supplychain";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

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
  grid.appendChild(kpiRow("sc-slsa",   "highest SLSA earned (honest)"));
  grid.appendChild(kpiRow("sc-l2",     "SLSA L2"));
  grid.appendChild(kpiRow("sc-l3",     "SLSA L3"));
  grid.appendChild(kpiRow("sc-subject","in-toto subject digest (trunc)"));
  grid.appendChild(kpiRow("sc-dsse",   "DSSE signature"));
  grid.appendChild(kpiRow("sc-micro",  "in-toto→DSSE→Merkle roundtrip"));
  grid.appendChild(kpiRow("sc-root",   "transparency-log root (trunc)"));
  grid.appendChild(kpiRow("sc-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("sc-lambda", "Λ"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent =
    "Sources: SLSA v1.0 (slsa.dev) · in-toto USENIX Security 2019 · Sigstore/Rekor " +
    "ACM CCS 2022 (DOI 10.1145/3548606.3560596) · C2PA spec · DSSE (secure-systems-lab). " +
    "MODELED · not verified · SLSA never upgraded.";
  card.appendChild(fn);
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
  pd.id = "sc-plain";
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
  const micro = S.microLabel === "MEASURED" && S.verifyOk === true
    ? "really ran and re-verified just now"
    : (S.microLabel === "HONEST-STUB" ? "is an honest stub (did not run)" : "loading…");
  pd.innerHTML =
    "<b>What this means:</b> When you ship a model, you want proof of <b>where its weights " +
    "came from and how they were built</b> — the same idea as a tamper-evident label on " +
    "food. Industry uses <b>SLSA</b> (a maturity ladder), <b>in-toto</b> (a signed statement " +
    "of what produced what), <b>DSSE</b> (the envelope a signature goes in), <b>Rekor</b> (a " +
    "public tamper-evident log), and <b>C2PA</b> (content credentials). This tab shows the " +
    "four stages a model artifact travels and, honestly, <b>how far up the SLSA ladder we " +
    "actually are</b>: <b>L1 is earned</b> (provenance exists), <b>L2 is modeled/attested</b> " +
    "(signed provenance — but the signature here is a clearly-labeled placeholder, because " +
    "there is no signing key in this sandbox), and <b>L3 is a roadmap</b> (a hardened builder " +
    "we have <b>not</b> built). The one genuinely-run piece is a tiny <b>in-toto→DSSE→" +
    "Merkle-log</b> roundtrip computed on the server (it " + micro + "); it proves the " +
    "<b>plumbing</b> is real, not that it scales to real weights. Nothing is faked and no " +
    "level is claimed that was not earned.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _trunc(s, n) { return typeof s === "string" ? (s.length > n ? s.slice(0, n) + "…" : s) : "—"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "provenance" });
    _show.setChip("slsa", S.slsaL1 || "SLSA L1 honest", { text: "earned" });
  }
  _set("sc-slsa",    t || (S.highestEarned ? (S.highestEarned + " — " + (S.slsaL1 || "honest")) : "—"));
  _set("sc-l2",      t || (S.slsaL2 || "—"));
  _set("sc-l3",      t || (S.slsaL3 || "—"));
  _set("sc-subject", t || _trunc(S.subjectSha, 18));
  _set("sc-dsse",    t || (S.dsseSigned === false ? "UNSIGNED-LOCAL (placeholder)" : (S.dsseSigned === true ? "SIGNED" : "—")));
  _set("sc-micro",   t || (S.microLabel ? (S.microLabel + (S.verifyOk === true ? " · verify_ok" : "")) : "—"));
  _set("sc-root",    t || _trunc(S.merkleRoot, 18));
  _set("sc-trust",   t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("sc-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — dispose everything; must not affect other organs
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
  _nodes = []; _links = []; _packet = null; _rungs = []; _logGlyph = null; _sigNode = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _pulseT = -1;
  _stage = _THREE = _ctx = null;
  S.label = S.notVerified = S.stages = S.highestEarned = S.ladder = null;
  S.microLabel = S.verifyOk = S.dsseSigned = S.merkleRoot = S.subjectSha = null;
  S.trustCeil = S.lambda = S.slsaL1 = S.slsaL2 = S.slsaL3 = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
