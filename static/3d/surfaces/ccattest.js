// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ccattest.js — CONFIDENTIAL-COMPUTE ATTESTATION CHAIN (TEE / NVIDIA H100 CC)
// organ for the holographic frontier ring. DISTINCT from the L6 chain-of-title receipt
// organ (governance/provenance/sovereign-compute doctrine) — this is a hardware-
// attestation hash-chain simulation, not a build/agent-action provenance receipt.
//
// Renders a vertical lattice-blue tower of stacked hash-blocks driven by a live
// deterministic snapshot from /api/killinchu/v1/cc-attest/verify:
//   device_identity (sha384) -> measurement_chain[] (bootloader -> firmware -> driver ->
//   microcode -> gpu-vbios) -> final_digest -> golden_match (bool).
// Each block in the tower is one measurement-log stage; blocks whose chained digest
// matches the fixed golden reference glow proof-teal, non-matching/pending blocks are
// grey. A HUD shows golden_match + a truncated final_digest. Honesty label "MODELED" is
// read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors testtime.js / neuromorphic.js / interpretability.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   label, seed, stages, device_identity, measurement_chain[{stage,digest}],
//   final_digest, golden_match, honest_note
//
// CONCEPT CITED (clean-room; NOT claimed as SZL's own; NO real GPU/TEE/network used):
//   NVIDIA, "Confidential Computing on H100 GPUs for Secure and Trustworthy AI" (2023):
//   https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/
//
// HONESTY LABEL: MODELED (deterministic sha256/sha384 hash-chain simulation of the TEE +
//   H100 CC attestation concept; NOT a real TDX/SEV-SNP/NRAS verifier; NEVER-CLAIMED-AS
//   actual hardware attestation). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (pending/tower body), proof-teal 0x3af4c8 (golden-match
//   glow ring), violet-blue 0x8a6bff (device-identity marker, data-viz only), greys for
//   pending/unverified/degraded. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100% — the
// attestation is MODELED, not real trust.

const ID    = "ccattest";
const TITLE = "Confidential-Compute Attestation Chain · TEE / H100 CC (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/cc-attest/verify?seed=42&stages=5";

// data-viz hues — purple BANNED
const C_BLOCK   = 0x5b8dee;  // lattice-blue (tower block body)
const C_IDENT   = 0x8a6bff;  // violet-blue (device-identity marker — data-viz only)
const C_DIM     = 0x42505d;  // grey (pending / unverified / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal (golden-match glow ring / HUD accent)
const C_GRID    = 0x1b3a44;  // floor / link colour

// tower layout geometry
const BLOCK_H     = 1.1;    // world-units, height of one hash-block
const BLOCK_W     = 2.2;    // world-units, block footprint (X/Z)
const BLOCK_GAP   = 0.22;   // world-units, gap between stacked blocks
const MAX_BLOCKS  = 5;      // bootloader..gpu-vbios

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _blocks   = [];   // Array<{ mesh: THREE.Mesh, ring: THREE.Mesh }> — stacked hash-blocks
let _identMarker = null;  // THREE.Mesh — device-identity marker (base of tower)
let _floor    = null;

// live state
const S = {
  label:      null,
  seed:       null,
  stagesReq:  null,
  deviceId:   null,   // device_identity hex
  chain:      null,   // measurement_chain[]
  finalDigest:null,
  goldenMatch:null,   // bool
  honestNote: null,
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(3, 7, 14);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 3, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildIdentMarker();
  _buildTower();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onAttest, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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
  _floor = grid;
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

// Pre-allocate MAX_BLOCKS stacked hash-block meshes + glow rings; visibility and
// colour are updated in-place as live data arrives (no per-poll geometry churn).
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
    mesh.position.set(0, y, 0);
    mesh.visible = false;
    _group.add(mesh);

    const ringMat = new THREE.MeshBasicMaterial({ color: C_ACCENT, transparent: true, opacity: 0.0 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.set(0, y, 0);
    ring.rotation.x = Math.PI / 2;
    ring.visible = false;
    _group.add(ring);

    _blocks.push({ mesh, ring, y });
  }

  // vertical spine (edge lines) connecting block centers, grey, data-viz only
  const spinePts = [];
  for (let i = 0; i < MAX_BLOCKS; i++) spinePts.push(new THREE.Vector3(0, _blocks[i].y, 0));
  const spineGeo = new THREE.BufferGeometry().setFromPoints(spinePts);
  const spine = new THREE.Line(spineGeo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.5 }));
  _group.add(spine);
}

// =============================================================================
// live data handler
// =============================================================================
function _onAttest(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.seed        = typeof j.seed === "number" ? j.seed : null;
  S.stagesReq   = typeof j.stages === "number" ? j.stages : null;
  S.deviceId    = typeof j.device_identity === "string" ? j.device_identity : null;
  S.chain       = Array.isArray(j.measurement_chain) ? j.measurement_chain : null;
  S.finalDigest = typeof j.final_digest === "string" ? j.final_digest : null;
  S.goldenMatch = typeof j.golden_match === "boolean" ? j.golden_match : null;
  S.honestNote  = typeof j.honest_note === "string" ? j.honest_note : null;

  _updateTower();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the stacked hash-block tower from live data
// =============================================================================
function _updateTower() {
  const live = S.state === "live";

  if (live && S.chain && S.chain.length) {
    const n = Math.min(MAX_BLOCKS, S.chain.length);
    for (let i = 0; i < MAX_BLOCKS; i++) {
      const b = _blocks[i];
      if (i < n) {
        b.mesh.visible = true;
        // Golden-match applies to the CHAIN AS A WHOLE (final_digest comparison);
        // if golden_match is true, light every realized block proof-teal to show
        // the whole verified chain; otherwise blocks stay lattice-blue (present,
        // computed) but the top block + ring signal the mismatch in grey/teal below.
        const isFinal = i === n - 1;
        const verified = S.goldenMatch === true;
        b.mesh.material.color.setHex(verified ? C_ACCENT : C_BLOCK);
        b.mesh.material.emissive.setHex(verified ? C_ACCENT : C_BLOCK);
        b.mesh.material.emissiveIntensity = verified ? 0.55 : 0.25;
        b.mesh.material.opacity = 0.88;

        b.ring.visible = isFinal;
        if (isFinal) {
          b.ring.material.color.setHex(verified ? C_ACCENT : C_DIM);
          b.ring.material.opacity = verified ? 0.9 : 0.35;
        }
      } else {
        b.mesh.visible = false;
        b.ring.visible = false;
      }
    }
  } else {
    _blocks.forEach((b) => {
      b.mesh.visible = false;
      b.ring.visible = false;
    });
  }

  if (_identMarker) {
    if (live && S.deviceId) {
      _identMarker.material.color.setHex(C_IDENT);
      _identMarker.material.emissive.setHex(C_IDENT);
      _identMarker.material.opacity = 0.85;
    } else {
      _identMarker.material.color.setHex(C_DIM);
      _identMarker.material.emissive.setHex(C_DIM);
      _identMarker.material.opacity = 0.3;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  if (_identMarker) {
    _identMarker.rotation.y += 0.015;
    _identMarker.rotation.x += 0.008;
  }
  // pulse the top (final-digest) glow ring, if visible and golden_match
  for (const b of _blocks) {
    if (b.ring.visible && S.goldenMatch === true) {
      const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
      b.ring.scale.setScalar(pulse);
    }
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
    maxWidth: "min(94%,440px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A deterministic <b>sha256/sha384 hash-chain</b> stand-in for a TEE + ' +
    '<b>NVIDIA H100 Confidential Computing</b>-style measured-boot attestation: ' +
    'device identity \\u2192 ordered stage digests \\u2192 final digest checked ' +
    'against a fixed golden reference. Honesty label <b>MODELED</b> \\u2014 NOT a real ' +
    'TDX/SEV-SNP/NRAS verifier, no real key material, no live GPU, no network. 0 runtime CDN.';
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
  nm.textContent = "cc-attest";
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
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("cc-seed",   "seed"));
  grid.appendChild(kpiRow("cc-stages", "stages (measurement log depth)"));
  grid.appendChild(kpiRow("cc-ident",  "device identity (sha384, truncated)"));
  grid.appendChild(kpiRow("cc-final",  "final digest (truncated)"));
  grid.appendChild(kpiRow("cc-golden", "golden_match \\u2014 MODELED"));
  grid.appendChild(kpiRow("cc-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "NVIDIA, \"Confidential Computing on H100 GPUs for Secure and Trustworthy AI\" (2023), developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai. MODELED \\u00b7 not claimed-as.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "cc-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  (ctx.container || document.body).appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const match = S.goldenMatch === true ? "MATCHES" : (S.goldenMatch === false ? "does NOT match" : "loading\u2026");
  pd.innerHTML =
    "<b>What this means:</b> Real NVIDIA H100 Confidential-Computing hardware boots " +
    "through a measured sequence \\u2014 bootloader, firmware, driver, microcode, GPU " +
    "VBIOS \\u2014 and produces a signed attestation report a relying party checks " +
    "against NVIDIA's remote attestation service before trusting the GPU with secrets. " +
    "This view is a <b>toy stand-in</b>: it hashes together a synthetic device ID and a " +
    "chain of stage names with plain SHA-256/SHA-384, then compares the result to a " +
    "single fixed \\u201cgolden\\u201d value. Right now the computed chain <b>" + match +
    "</b> that golden value. There is <b>no real GPU, no real key, and no network call</b> " +
    "involved \\u2014 it exists to show how attestation-chain verification WORKS, not to " +
    "perform one. Plain: this is a labeled toy model of a real security concept, not a " +
    "working hardware verifier.";
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
  _set("cc-seed",   t || (S.seed != null ? String(S.seed) : "\u2014"));
  _set("cc-stages", t || (S.stagesReq != null ? String(S.stagesReq) : "\u2014"));
  _set("cc-ident",  t || _trunc(S.deviceId, 20));
  _set("cc-final",  t || _trunc(S.finalDigest, 20));
  _set("cc-golden", t || (S.goldenMatch === true ? "MATCH" : (S.goldenMatch === false ? "MISMATCH" : "\u2014")));
  // honesty label verbatim — never upgraded
  _set("cc-label",  t || (S.label || "MODELED"));
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
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _overlay = null;
  _blocks = []; _identMarker = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seed = S.stagesReq = S.deviceId = S.chain = null;
  S.finalDigest = S.goldenMatch = S.honestNote = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
