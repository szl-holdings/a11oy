// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/pcai.js — PROOF-CARRYING ATTESTED INFERENCE (Wave-N Dev 2)
//
// The Wave-N deepening of attested inference into ONE off-the-shelf-checkable proof-carrying
// bundle. Driven by a single deterministic snapshot from
//   /api/a11oy/v1/pcai/run?seed=42&model=szl-modeled-lm
// it renders the four legs that a SINGLE in-toto/SLSA v1 DSSE bundle binds together:
//   (1) measured-boot TOWER  — device_identity → stage digests → final_digest (mrtd), reusing the
//       cc-attest chain; proof-teal when golden_match, grey on a simulated tamper.
//   (2) TEE QUOTE ring        — the NVIDIA-NRAS-style attestation quote (nonce + overall-result)
//       that binds this inference; colour = overall_att_result.
//   (3) Λ-GATE ring           — colour = pass (proof-teal) / block (grey); the attestation axis is
//       hard-coupled to the boot match, so a mismatch collapses Λ to 0 (A4 zero-absorption).
//   (4) BUNDLE node           — the ONE in-toto/SLSA statement + DSSE envelope + Sigstore bundle,
//       lit proof-teal only when the Λ-gate RELEASED the inference. A HUD shows the subject
//       digest, quote digest, Λ value/floor/pass, DSSE signed flag, and the exact off-the-shelf
//       `cosign verify-blob` / `slsa-verifier verify-artifact` commands (verbatim from JSON).
//
// Surface export shape (mirrors attestinfer.js / ccattest.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// HONESTY LABEL: MODELED (deterministic sha256/384 simulation keyed on (seed, model); NO real
//   TEE, NO real GPU, NO NRAS/KDS/DCAP network, NO real inference engine, NO Rekor log entry).
//   The DSSE envelope is REAL ECDSA-P256 in-Space (cosign verify-blob-checkable) and honestly
//   UNSIGNED-LOCAL locally. Label read VERBATIM from JSON; never upgraded. Λ = Conjecture 1
//   (advisory, gray, never green). Nothing here is in the locked-8.
//
// LEADERS CITED (clean-room PATTERN; NOT claimed as SZL's own):
//   in-toto / SLSA v1 provenance (Statement _type, subject.digest, buildDefinition, runDetails)
//     https://slsa.dev/spec/v1.0/provenance
//   Sigstore cosign + Rekor transparency log (cosign verify-blob --key cosign.pub; bundle format)
//     https://docs.sigstore.dev/cosign/verifying/verify/ · https://docs.sigstore.dev/about/bundle/
//   NVIDIA NRAS TEE attestation — signed EAT token, nonce, RIM/OCSP, submod measurement digest
//     https://docs.nvidia.com/attestation/technical-docs-nras/latest/nras_introduction.html
//   slsa-verifier verify-artifact (--provenance-path / --source-uri)
//     https://github.com/slsa-framework/slsa-verifier
//
// COLOURS: lattice-blue 0x5b8dee (tower/pending), proof-teal 0x3af4c8 (golden-match / Λ-pass /
//   released / signed), violet-blue 0x8a6bff (device-identity marker, data-viz only), greys for
//   pending/blocked/degraded. Purple BANNED as UI/background. 0 RUNTIME CDN (vendored three.js).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown verbatim.

const ID    = "pcai";
const TITLE = "Proof-Carrying Attested Inference · one cosign/slsa-verifier-checkable bundle (live)";

const EP = "/api/a11oy/v1/pcai/run?seed=42&model=szl-modeled-lm";

// data-viz hues — purple BANNED
const C_BLOCK   = 0x5b8dee;  // lattice-blue (tower block body / pending)
const C_IDENT   = 0x8a6bff;  // violet-blue (device-identity marker — data-viz only)
const C_DIM     = 0x42505d;  // grey (pending / blocked / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal (golden-match / Λ-pass / released / signed)
const C_GRID    = 0x1b3a44;  // floor / link colour

const BLOCK_H     = 1.0;
const BLOCK_W     = 2.0;
const BLOCK_GAP   = 0.22;
const MAX_BLOCKS  = 5;       // bootloader..gpu-vbios

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _blocks = [];            // stacked measured-boot hash-blocks
let _identMarker = null;     // device-identity marker (base)
let _quoteRing = null;       // TEE-quote ring
let _lambdaRing = null;      // Λ-gate ring
let _bundleNode = null;      // proof-carrying bundle node (lit only when released)
let _linkLine = null;        // gate -> bundle link

// live state
const S = {
  label: null, seed: null,
  deviceId: null, chain: null, finalDigest: null, goldenMatch: null,
  quoteDigest: null, nonce: null, overallResult: null,
  lamValue: null, lamFloor: null, lamPass: null,
  released: null, subjectDigest: null,
  dsseSigned: null, dsseLabel: null,
  cosignCmd: null, slsaCmd: null, bundleMedia: null, tlogStatus: null,
  honestNote: null, state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 4.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildIdentMarker();
  _buildTower();
  _buildQuoteRing();
  _buildLambdaRing();
  _buildBundleNode();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSnap, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateScene(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(30, 30, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildIdentMarker() {
  const THREE = _THREE;
  _identMarker = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.4, 0),
    new THREE.MeshStandardMaterial({ color: C_IDENT, emissive: C_IDENT, emissiveIntensity: 0.35, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _identMarker.position.set(0, 0.35, 0);
  _group.add(_identMarker);
}

function _buildTower() {
  const THREE = _THREE;
  const boxGeo = new THREE.BoxGeometry(BLOCK_W, BLOCK_H, BLOCK_W);
  const ringGeo = new THREE.TorusGeometry(BLOCK_W * 0.62, 0.05, 8, 24);
  for (let i = 0; i < MAX_BLOCKS; i++) {
    const y = 0.9 + i * (BLOCK_H + BLOCK_GAP);
    const mat = new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15,
      transparent: true, opacity: 0.5, wireframe: false,
    });
    const mesh = new THREE.Mesh(boxGeo, mat);
    mesh.position.set(0, y, 0); mesh.visible = false;
    _group.add(mesh);
    const ringMat = new THREE.MeshBasicMaterial({ color: C_ACCENT, transparent: true, opacity: 0.0 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.set(0, y, 0); ring.rotation.x = Math.PI / 2; ring.visible = false;
    _group.add(ring);
    _blocks.push({ mesh, ring, y });
  }
  const spinePts = [];
  for (let i = 0; i < MAX_BLOCKS; i++) spinePts.push(new THREE.Vector3(0, _blocks[i].y, 0));
  const spine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(spinePts),
    new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.5 }));
  _group.add(spine);
}

// TEE-quote ring sits just above the tower top; colour reflects overall_att_result.
function _buildQuoteRing() {
  const THREE = _THREE;
  const topY = 0.9 + MAX_BLOCKS * (BLOCK_H + BLOCK_GAP) + 0.55;
  _quoteRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.15, 0.09, 12, 40),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.55 }),
  );
  _quoteRing.position.set(0, topY, 0);
  _quoteRing.rotation.x = Math.PI / 2;
  _group.add(_quoteRing);
}

// Λ-gate ring above the quote ring; its colour reflects pass/block.
function _buildLambdaRing() {
  const THREE = _THREE;
  const topY = 0.9 + MAX_BLOCKS * (BLOCK_H + BLOCK_GAP) + 1.55;
  _lambdaRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.5, 0.14, 16, 48),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.6 }),
  );
  _lambdaRing.position.set(0, topY, 0);
  _lambdaRing.rotation.x = Math.PI / 2;
  _group.add(_lambdaRing);
}

// Bundle node above the Λ-ring; lit proof-teal only when the gate RELEASED the inference.
function _buildBundleNode() {
  const THREE = _THREE;
  const topY = 0.9 + MAX_BLOCKS * (BLOCK_H + BLOCK_GAP) + 3.3;
  _bundleNode = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.8, 1),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.5, wireframe: true }),
  );
  _bundleNode.position.set(0, topY, 0);
  _group.add(_bundleNode);
  const linkGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, topY - 1.4, 0), new THREE.Vector3(0, topY - 0.8, 0),
  ]);
  _linkLine = new THREE.Line(linkGeo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.5 }));
  _group.add(_linkLine);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSnap(j) {
  S.label       = (j.label || "MODELED").toUpperCase();  // verbatim, never upgraded
  S.seed        = typeof j.seed === "number" ? j.seed : null;
  S.deviceId    = typeof j.device_identity === "string" ? j.device_identity : null;
  S.chain       = Array.isArray(j.measurement_chain) ? j.measurement_chain : null;
  S.finalDigest = typeof j.final_digest === "string" ? j.final_digest : null;
  S.goldenMatch = typeof j.golden_match === "boolean" ? j.golden_match : null;

  const q = j.tee_quote || {};
  S.quoteDigest   = typeof q.quote_digest === "string" ? q.quote_digest : null;
  S.nonce         = typeof q.nonce === "string" ? q.nonce : null;
  S.overallResult = typeof q.overall_att_result === "boolean" ? q.overall_att_result : null;

  const lam = j.lambda || {};
  S.lamValue = typeof lam.value === "number" ? lam.value : null;
  S.lamFloor = typeof lam.floor === "number" ? lam.floor : null;
  S.lamPass  = typeof lam.pass === "boolean" ? lam.pass : null;

  const inf = j.inference || {};
  S.released = typeof inf.released === "boolean" ? inf.released : null;

  const art = j.artifact || {};
  S.subjectDigest = typeof art.subject_digest_sha384 === "string" ? art.subject_digest_sha384 : null;

  const dsse = j.dsse || {};
  S.dsseSigned = typeof dsse.signed === "boolean" ? dsse.signed : null;
  S.dsseLabel  = dsse.local_label || (dsse.signed ? "REAL-SIGNED" : "UNSIGNED-LOCAL");

  const vc = j.verify_commands || {};
  S.cosignCmd = typeof vc.cosign_verify_blob === "string" ? vc.cosign_verify_blob : null;
  S.slsaCmd   = typeof vc.slsa_verifier_verify_artifact === "string" ? vc.slsa_verifier_verify_artifact : null;

  const b = j.bundle || {};
  S.bundleMedia = typeof b.mediaType === "string" ? b.mediaType : null;
  const vm = b.verificationMaterial || {};
  S.tlogStatus  = typeof vm.tlog_status === "string" ? vm.tlog_status : null;

  S.honestNote = typeof j.honest_note === "string" ? j.honest_note : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// scene updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const bootOk = S.goldenMatch === true;
  const quoteOk = S.overallResult === true;
  const gatePass = S.lamPass === true;
  const released = S.released === true;

  // tower blocks
  if (live && S.chain && S.chain.length) {
    const n = Math.min(MAX_BLOCKS, S.chain.length);
    for (let i = 0; i < MAX_BLOCKS; i++) {
      const b = _blocks[i];
      if (i < n) {
        b.mesh.visible = true;
        b.mesh.material.color.setHex(bootOk ? C_ACCENT : C_BLOCK);
        b.mesh.material.emissive.setHex(bootOk ? C_ACCENT : C_BLOCK);
        b.mesh.material.emissiveIntensity = bootOk ? 0.5 : 0.25;
        b.mesh.material.opacity = 0.88;
        const isFinal = i === n - 1;
        b.ring.visible = isFinal;
        if (isFinal) { b.ring.material.color.setHex(bootOk ? C_ACCENT : C_DIM); b.ring.material.opacity = bootOk ? 0.9 : 0.35; }
      } else { b.mesh.visible = false; b.ring.visible = false; }
    }
  } else {
    _blocks.forEach((b) => { b.mesh.visible = false; b.ring.visible = false; });
  }

  // device-identity marker
  if (_identMarker) {
    const on = live && S.deviceId;
    _identMarker.material.color.setHex(on ? C_IDENT : C_DIM);
    _identMarker.material.emissive.setHex(on ? C_IDENT : C_DIM);
    _identMarker.material.opacity = on ? 0.85 : 0.3;
  }

  // TEE-quote ring
  if (_quoteRing) {
    const c = (live && quoteOk) ? C_ACCENT : (live && S.quoteDigest ? C_BLOCK : C_DIM);
    _quoteRing.material.color.setHex(c);
    _quoteRing.material.emissive.setHex(c);
    _quoteRing.material.emissiveIntensity = (live && quoteOk) ? 0.5 : 0.2;
    _quoteRing.material.opacity = live ? 0.8 : 0.55;
  }

  // Λ-gate ring
  if (_lambdaRing) {
    const c = (live && gatePass) ? C_ACCENT : C_DIM;
    _lambdaRing.material.color.setHex(c);
    _lambdaRing.material.emissive.setHex(c);
    _lambdaRing.material.emissiveIntensity = (live && gatePass) ? 0.55 : 0.2;
    _lambdaRing.material.opacity = live ? 0.85 : 0.5;
  }

  // bundle node — lit only when released
  if (_bundleNode) {
    const on = live && released;
    _bundleNode.material.color.setHex(on ? C_ACCENT : C_DIM);
    _bundleNode.material.emissive.setHex(on ? C_ACCENT : C_DIM);
    _bundleNode.material.emissiveIntensity = on ? 0.6 : 0.2;
    _bundleNode.material.opacity = on ? 0.92 : 0.45;
    _bundleNode.material.wireframe = !on;
  }
  if (_linkLine) _linkLine.material.opacity = (live && released) ? 0.85 : 0.4;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  if (_identMarker) { _identMarker.rotation.y += 0.015; _identMarker.rotation.x += 0.008; }
  if (_quoteRing && S.overallResult === true) { _quoteRing.rotation.z -= 0.008; }
  if (_lambdaRing && S.lamPass === true) { _lambdaRing.rotation.z += 0.01; const p = 1.0 + 0.06 * Math.sin(t * 0.003); _lambdaRing.scale.setScalar(p); }
  if (_bundleNode && S.released === true) { _bundleNode.rotation.y += 0.02; _bundleNode.rotation.x += 0.012; }
  for (const b of _blocks) {
    if (b.ring.visible && S.goldenMatch === true) { const p = 1.0 + 0.12 * Math.sin(t * 0.0035); b.ring.scale.setScalar(p); }
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,480px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    "ONE proof-carrying <b>bundle</b> binds all four legs: (a) the inference <b>receipt</b>, " +
    "(b) a <b>TEE attestation quote digest</b> (reused cc-attest chain), (c) an in-toto / SLSA v1 " +
    "<b>provenance predicate</b>, and (d) the <b>\u039b axes</b> \u2014 emitted as a DSSE envelope + " +
    "Sigstore-style bundle + intoto.jsonl that a standard <b>cosign verify-blob</b> / " +
    "<b>slsa-verifier</b> COULD check. Honesty <b>MODELED</b> \u2014 no real TEE/GPU/NRAS/network/Rekor; " +
    "DSSE is REAL ECDSA-P256 in-Space, UNSIGNED-LOCAL locally. 0 runtime CDN.";
  _overlay.appendChild(sub);

  const brow = document.createElement("div");
  brow.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  if (_badge && _badge.el) brow.appendChild(_badge.el);
  _overlay.appendChild(brow);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "pcai/run";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id; v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:60%;overflow-wrap:anywhere";
    v.textContent = "\u2014"; _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("pc-seed",   "seed"));
  grid.appendChild(kpiRow("pc-ident",  "device identity (sha384, trunc)"));
  grid.appendChild(kpiRow("pc-golden", "measured-boot golden_match \u2014 MODELED"));
  grid.appendChild(kpiRow("pc-quote",  "(b) TEE quote digest (trunc)"));
  grid.appendChild(kpiRow("pc-nras",   "NRAS-style overall_att_result"));
  grid.appendChild(kpiRow("pc-lambda", "(d) \u039b value / floor \u2014 Conjecture 1"));
  grid.appendChild(kpiRow("pc-gate",   "\u039b-gate"));
  grid.appendChild(kpiRow("pc-infer",  "inference released"));
  grid.appendChild(kpiRow("pc-subject","(c) SLSA subject digest (trunc)"));
  grid.appendChild(kpiRow("pc-bundle", "bundle mediaType"));
  grid.appendChild(kpiRow("pc-dsse",   "DSSE envelope"));
  grid.appendChild(kpiRow("pc-tlog",   "Rekor transparency log"));
  grid.appendChild(kpiRow("pc-label",  "honesty label"));
  card.appendChild(grid);
  _overlay.appendChild(card);

  // verify-command block (documented in code + shown verbatim here)
  const vcard = document.createElement("div");
  vcard.style.cssText = "background:#08120c;border:1px solid #12402f;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";
  const vh = document.createElement("div");
  vh.style.cssText = "font:600 11px ui-monospace,monospace;color:#3af4c8;letter-spacing:.3px";
  vh.textContent = "\u2713 verify this bundle yourself (off-the-shelf tools)";
  vcard.appendChild(vh);
  const vpre = document.createElement("pre");
  vpre.id = "pc-verify";
  vpre.style.cssText = "margin:0;font:10px ui-monospace,monospace;color:#c9d6df;white-space:pre-wrap;word-break:break-word;line-height:1.5";
  vpre.textContent = "\u2026";
  _el["verify"] = vpre;
  vcard.appendChild(vpre);
  _overlay.appendChild(vcard);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.innerHTML =
    "Leaders (clean-room pattern, not claimed-as): in-toto / SLSA v1 provenance (slsa.dev/spec/v1.0/provenance); " +
    "Sigstore cosign + Rekor (docs.sigstore.dev/cosign/verifying, /about/bundle, /logging); " +
    "NVIDIA NRAS TEE attestation \u2014 signed EAT, nonce, RIM/OCSP " +
    "(docs.nvidia.com/attestation \u2026 nras_introduction); slsa-verifier (github.com/slsa-framework/slsa-verifier). " +
    "MODELED \u00b7 \u039b = Conjecture 1 \u00b7 nothing to locked-8.";
  _overlay.appendChild(fn);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => { _plain = !_plain; pl.style.background = _plain ? "#0f2a20" : "#08140f"; _applyPlain(); });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "pc-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  (ctx.container || document.body).appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"]; if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const boot = S.goldenMatch === true ? "PASSES" : (S.goldenMatch === false ? "FAILS" : "loading\u2026");
  const rel  = S.released === true ? "RELEASED" : (S.released === false ? "WITHHELD" : "loading\u2026");
  pd.innerHTML =
    "<b>What this means:</b> Real confidential-compute hardware (NVIDIA H100 CC + NRAS, AMD SEV-SNP, " +
    "Intel TDX) boots through a measured sequence and produces a signed <b>attestation quote</b>; a " +
    "supply-chain system (in-toto / SLSA) separately proves <b>where an artifact was built</b>. PCAI " +
    "fuses them: it wraps the inference result, the attestation quote, the SLSA provenance, and a " +
    "\u039b trust score into <b>one signed bundle</b> \u2014 so an investor or auditor can run the standard " +
    "<b>cosign verify-blob</b> and <b>slsa-verifier</b> commands (shown above) and check it themselves, " +
    "without trusting us. This view is a labeled <b>toy stand-in</b>: it hashes a synthetic device ID " +
    "and boot stages, binds this run into the quote, then runs a \u039b gate that only releases a (fake) " +
    "inference when the attestation is good. Right now the measured boot <b>" + boot + "</b> and the " +
    "inference is <b>" + rel + "</b>. There is <b>no real GPU, no real network call, and no Rekor log " +
    "entry</b> \u2014 it shows how proof-carrying attested inference WORKS. The bundle is signed for real " +
    "(ECDSA-P256) only inside the deployed Space; locally it is honestly UNSIGNED.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}
function _trunc(s, n) { return typeof s === "string" ? (s.length > n ? s.slice(0, n) + "\u2026" : s) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("pc-seed",   t || (S.seed != null ? String(S.seed) : "\u2014"));
  _set("pc-ident",  t || _trunc(S.deviceId, 18));
  _set("pc-golden", t || (S.goldenMatch === true ? "MATCH" : (S.goldenMatch === false ? "MISMATCH" : "\u2014")));
  _set("pc-quote",  t || _trunc(S.quoteDigest, 18));
  _set("pc-nras",   t || (S.overallResult === true ? "true" : (S.overallResult === false ? "false" : "\u2014")));
  _set("pc-lambda", t || (S.lamValue != null ? (S.lamValue.toFixed(4) + " / " + (S.lamFloor != null ? S.lamFloor.toFixed(2) : "0.90")) : "\u2014"));
  _set("pc-gate",   t || (S.lamPass === true ? "PASS (release)" : (S.lamPass === false ? "BLOCK (withhold)" : "\u2014")));
  _set("pc-infer",  t || (S.released === true ? "RELEASED" : (S.released === false ? "WITHHELD" : "\u2014")));
  _set("pc-subject",t || _trunc(S.subjectDigest, 18));
  _set("pc-bundle", t || (S.bundleMedia ? _trunc(S.bundleMedia, 40) : "\u2014"));
  _set("pc-dsse",   t || (S.dsseSigned == null ? "\u2014" : (S.dsseSigned ? "REAL-SIGNED (ECDSA-P256)" : "UNSIGNED-LOCAL")));
  _set("pc-tlog",   t || (S.tlogStatus ? (S.tlogStatus.indexOf("UNAVAILABLE") === 0 ? "UNAVAILABLE-LOCAL" : _trunc(S.tlogStatus, 28)) : "\u2014"));
  _set("pc-label",  t || (S.label || "MODELED"));

  // verify commands verbatim from JSON
  if (_el["verify"]) {
    if (t) { _el["verify"].textContent = t; }
    else if (S.cosignCmd || S.slsaCmd) {
      _el["verify"].textContent =
        "$ " + (S.cosignCmd || "cosign verify-blob \u2026") + "\n" +
        "$ " + (S.slsaCmd   || "slsa-verifier verify-artifact \u2026") + "\n" +
        "# local: UNSIGNED (no cosign secret) \u00b7 in-Space: PASS byte-for-byte";
    } else { _el["verify"].textContent = "\u2026"; }
  }
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => { if (m.dispose) m.dispose(); }); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _overlay = null;
  _blocks = []; _identMarker = null; _quoteRing = null; _lambdaRing = null; _bundleNode = null; _linkLine = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seed = S.deviceId = S.chain = S.finalDigest = S.goldenMatch = null;
  S.quoteDigest = S.nonce = S.overallResult = null;
  S.lamValue = S.lamFloor = S.lamPass = null;
  S.released = S.subjectDigest = null;
  S.dsseSigned = S.dsseLabel = S.cosignCmd = S.slsaCmd = S.bundleMedia = S.tlogStatus = S.honestNote = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
