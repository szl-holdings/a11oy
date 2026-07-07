// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/attestinfer.js — ATTESTED INFERENCE (Wave-H Team 3 deepening of Wave-A cc-attest)
//
// DEEPENS the Wave-A cc-attest measured-boot chain into a full "attested inference" flow that
// binds a device-attestation quote to a governed inference RECEIPT end-to-end, verifiable-by-
// design. Renders three linked stages driven by a single deterministic snapshot from
//   /api/a11oy/v1/attest/infer?seed=42&model=szl-modeled-lm :
//     (1) measured-boot TOWER — device_identity -> stage digests -> final_digest (mrtd),
//         glowing proof-teal when golden_match, grey on mismatch (same tower idiom as ccattest.js).
//     (2) Λ-GATE ring above the tower — colour = pass (proof-teal) / block (grey); the attestation
//         axis is hard-coupled to the boot match, so a mismatch collapses Λ to 0 (A4 zero-absorption).
//     (3) INFERENCE node — lit only when the Λ-gate RELEASED the inference (CoCo KBS style:
//         no secret/inference release without a good attestation). A HUD shows the attestation
//         quote digest, Λ value/floor/pass, DSSE signed flag, and the honesty label (verbatim).
//
// Surface export shape (mirrors ccattest.js / neuromorphic.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// HONESTY LABEL: MODELED (deterministic sha256/384 simulation of the attested path keyed on
//   (seed, model); NO real TEE, NO real GPU, NO NRAS/KDS network, NO real inference engine).
//   The DSSE envelope is REAL ECDSA-P256 in-Space and honestly UNSIGNED-LOCAL locally.
//   Label read VERBATIM from JSON; never upgraded. Λ = Conjecture 1 (advisory, gray, never green).
//   Nothing here is in the locked-8. Trust never 100% — the attestation is MODELED, not real trust.
//
// CONFIDENTIAL-COMPUTE LEADERS CITED (clean-room PATTERN; NOT claimed as SZL's own):
//   NVIDIA H100/H200 Confidential Computing + NRAS remote attestation
//     https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/
//   AMD SEV-SNP attestation (REPORT_DATA binds the inference; VCEK/KDS cert chain)
//     https://www.amd.com/content/dam/amd/en/documents/developer/lss-snp-attestation.pdf
//   Intel TDX (MRTD/RTMR TD Quote); in-toto/SLSA provenance (slsa.dev); Sigstore/Rekor
//     (cosign verify-blob); Confidential Containers (CoCo) attestation-agent + KBS.
//
// COLOURS: lattice-blue 0x5b8dee (tower/pending), proof-teal 0x3af4c8 (golden-match / Λ-pass /
//   released), violet-blue 0x8a6bff (device-identity marker, data-viz only), greys for
//   pending/blocked/degraded. Purple BANNED as UI/background. 0 RUNTIME CDN (vendored three.js).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown verbatim.

const ID    = "attestinfer";
const TITLE = "Attested Inference · TEE quote → Λ-gate → signed receipt (live)";

// Same-origin endpoint (this surface plugs into the a11oy registry, unlike Wave-A cc-attest
// which lived on the isolated killinchu Space).
const EP = "/api/a11oy/v1/attest/infer?seed=42&model=szl-modeled-lm";

// data-viz hues — purple BANNED
const C_BLOCK   = 0x5b8dee;  // lattice-blue (tower block body / pending)
const C_IDENT   = 0x8a6bff;  // violet-blue (device-identity marker — data-viz only)
const C_DIM     = 0x42505d;  // grey (pending / blocked / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal (golden-match / Λ-pass / released)
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
let _lambdaRing = null;      // Λ-gate ring above the tower
let _inferNode = null;       // inference node (lit only when released)
let _linkLine = null;        // gate -> inference link

// live state
const S = {
  label: null, seed: null, stages: null,
  deviceId: null, chain: null, finalDigest: null, goldenMatch: null,
  quoteDigest: null,
  lamValue: null, lamFloor: null, lamPass: null,
  released: null, outputDigest: null,
  dsseSigned: null, dsseLabel: null,
  honestNote: null, state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 8, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildIdentMarker();
  _buildTower();
  _buildLambdaRing();
  _buildInferNode();

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

// Λ-gate ring sits above the tower; its colour reflects pass/block.
function _buildLambdaRing() {
  const THREE = _THREE;
  const topY = 0.9 + MAX_BLOCKS * (BLOCK_H + BLOCK_GAP) + 0.9;
  _lambdaRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.5, 0.14, 16, 48),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.6 }),
  );
  _lambdaRing.position.set(0, topY, 0);
  _lambdaRing.rotation.x = Math.PI / 2;
  _group.add(_lambdaRing);
}

// Inference node above the Λ-ring; lit proof-teal only when the gate RELEASED the inference.
function _buildInferNode() {
  const THREE = _THREE;
  const topY = 0.9 + MAX_BLOCKS * (BLOCK_H + BLOCK_GAP) + 2.6;
  _inferNode = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.7, 1),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.5, wireframe: true }),
  );
  _inferNode.position.set(0, topY, 0);
  _group.add(_inferNode);
  const linkGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, topY - 1.1, 0), new THREE.Vector3(0, topY - 0.7, 0),
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
  S.stages      = typeof j.stages === "number" ? j.stages : null;
  S.deviceId    = typeof j.device_identity === "string" ? j.device_identity : null;
  S.chain       = Array.isArray(j.measurement_chain) ? j.measurement_chain : null;
  S.finalDigest = typeof j.final_digest === "string" ? j.final_digest : null;
  S.goldenMatch = typeof j.golden_match === "boolean" ? j.golden_match : null;

  const q = j.attestation_quote || {};
  S.quoteDigest = typeof q.quote_digest === "string" ? q.quote_digest : null;

  const lam = j.lambda || {};
  S.lamValue = typeof lam.value === "number" ? lam.value : null;
  S.lamFloor = typeof lam.floor === "number" ? lam.floor : null;
  S.lamPass  = typeof lam.pass === "boolean" ? lam.pass : null;

  const inf = j.inference || {};
  S.released    = typeof inf.released === "boolean" ? inf.released : null;
  S.outputDigest= typeof inf.output_digest === "string" ? inf.output_digest : null;

  const dsse = j.dsse || {};
  S.dsseSigned = typeof dsse.signed === "boolean" ? dsse.signed : null;
  S.dsseLabel  = dsse.local_label || (dsse.signed ? "REAL-SIGNED" : "UNSIGNED-LOCAL");

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

  // Λ-gate ring
  if (_lambdaRing) {
    const c = (live && gatePass) ? C_ACCENT : C_DIM;
    _lambdaRing.material.color.setHex(c);
    _lambdaRing.material.emissive.setHex(c);
    _lambdaRing.material.emissiveIntensity = (live && gatePass) ? 0.55 : 0.2;
    _lambdaRing.material.opacity = live ? 0.85 : 0.5;
  }

  // inference node — lit only when released
  if (_inferNode) {
    const on = live && released;
    _inferNode.material.color.setHex(on ? C_ACCENT : C_DIM);
    _inferNode.material.emissive.setHex(on ? C_ACCENT : C_DIM);
    _inferNode.material.emissiveIntensity = on ? 0.6 : 0.2;
    _inferNode.material.opacity = on ? 0.92 : 0.45;
    _inferNode.material.wireframe = !on;
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
  if (_lambdaRing && S.lamPass === true) { _lambdaRing.rotation.z += 0.01; const p = 1.0 + 0.06 * Math.sin(t * 0.003); _lambdaRing.scale.setScalar(p); }
  if (_inferNode && S.released === true) { _inferNode.rotation.y += 0.02; _inferNode.rotation.x += 0.012; }
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
    maxWidth: "min(94%,460px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    "A deepening of Wave-A cc-attest into a full <b>attested-inference</b> flow: a device " +
    "<b>measured-boot chain</b> \u2192 an attestation <b>quote</b> that binds this inference " +
    "(SEV-SNP <b>REPORT_DATA</b> style) \u2192 a <b>\u039b-gate</b> \u2192 gated inference \u2192 a " +
    "signed <b>receipt</b> embedding the quote digest + \u039b axes + SLSA provenance. " +
    "Honesty <b>MODELED</b> \u2014 no real TEE/GPU/NRAS/network; DSSE is REAL ECDSA-P256 in-Space, " +
    "UNSIGNED-LOCAL locally. 0 runtime CDN.";
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
  nm.textContent = "attest/infer";
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
  grid.appendChild(kpiRow("ai-seed",   "seed"));
  grid.appendChild(kpiRow("ai-ident",  "device identity (sha384, trunc)"));
  grid.appendChild(kpiRow("ai-golden", "measured-boot golden_match \u2014 MODELED"));
  grid.appendChild(kpiRow("ai-quote",  "attestation quote digest (trunc)"));
  grid.appendChild(kpiRow("ai-lambda", "\u039b value / floor \u2014 Conjecture 1"));
  grid.appendChild(kpiRow("ai-gate",   "\u039b-gate"));
  grid.appendChild(kpiRow("ai-infer",  "inference released"));
  grid.appendChild(kpiRow("ai-dsse",   "DSSE receipt"));
  grid.appendChild(kpiRow("ai-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.innerHTML =
    "Leaders (clean-room pattern, not claimed-as): NVIDIA H100/H200 CC + NRAS " +
    "(developer.nvidia.com/blog/confidential-computing-on-h100-gpus\u2026); AMD SEV-SNP REPORT_DATA/VCEK/KDS " +
    "(amd.com \u2026 lss-snp-attestation.pdf); Intel TDX MRTD; in-toto/SLSA (slsa.dev); Sigstore/Rekor " +
    "cosign (docs.sigstore.dev); Confidential Containers (CoCo) KBS. MODELED \u00b7 \u039b = Conjecture 1.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => { _plain = !_plain; pl.style.background = _plain ? "#0f2a20" : "#08140f"; _applyPlain(); });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ai-plain";
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
    "<b>What this means:</b> Real confidential-compute hardware (NVIDIA H100 CC, AMD SEV-SNP, " +
    "Intel TDX) boots through a measured sequence and produces a signed <b>attestation quote</b>. " +
    "A relying party (NVIDIA NRAS, AMD KDS, a Confidential-Containers key broker) checks that " +
    "quote before it will trust the machine with secrets or release a model. This view is a " +
    "labeled <b>toy stand-in</b>: it hashes a synthetic device ID and boot stages, binds this " +
    "run into the quote, then runs a <b>\u039b trust gate</b> that only releases a (fake) inference " +
    "when the attestation is good. Right now the measured boot <b>" + boot + "</b> and the " +
    "inference is <b>" + rel + "</b>. There is <b>no real GPU, no real key, and no network call</b> " +
    "\u2014 it shows how attested inference WORKS, not a working verifier. The receipt is signed for " +
    "real (ECDSA-P256) only inside the deployed Space; locally it is honestly UNSIGNED.";
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
  _set("ai-seed",   t || (S.seed != null ? String(S.seed) : "\u2014"));
  _set("ai-ident",  t || _trunc(S.deviceId, 18));
  _set("ai-golden", t || (S.goldenMatch === true ? "MATCH" : (S.goldenMatch === false ? "MISMATCH" : "\u2014")));
  _set("ai-quote",  t || _trunc(S.quoteDigest, 18));
  _set("ai-lambda", t || (S.lamValue != null ? (S.lamValue.toFixed(4) + " / " + (S.lamFloor != null ? S.lamFloor.toFixed(2) : "0.90")) : "\u2014"));
  _set("ai-gate",   t || (S.lamPass === true ? "PASS (release)" : (S.lamPass === false ? "BLOCK (withhold)" : "\u2014")));
  _set("ai-infer",  t || (S.released === true ? "RELEASED" : (S.released === false ? "WITHHELD" : "\u2014")));
  _set("ai-dsse",   t || (S.dsseSigned == null ? "\u2014" : (S.dsseSigned ? "REAL-SIGNED (ECDSA-P256)" : "UNSIGNED-LOCAL")));
  _set("ai-label",  t || (S.label || "MODELED"));
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
  _blocks = []; _identMarker = null; _lambdaRing = null; _inferNode = null; _linkLine = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seed = S.stages = S.deviceId = S.chain = S.finalDigest = S.goldenMatch = null;
  S.quoteDigest = S.lamValue = S.lamFloor = S.lamPass = null;
  S.released = S.outputDigest = S.dsseSigned = S.dsseLabel = S.honestNote = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
