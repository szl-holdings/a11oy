// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/confattest.js — CONFIDENTIAL-COMPUTE ATTESTATION + ACTION-GATE organ for
// the holographic governance ring. Renders the two governance legs as one scene:
//
//   (a) a confidential-compute ENCLAVE (box) emitting a SIMULATED attestation quote,
//       chained by an edge into a RECEIPT glyph — glows proof-teal when the enclave
//       quote attests OK, grey when the SIMULATED measurement mismatches;
//   (b) an ACTION GATE (torus) downstream of the enclave: the agent ACTION (small
//       node) must pass the gate to reach the VERDICT glyph. The gate governs the
//       ACTION EFFECT boundary, NEVER the reasoning. ALLOW → teal, HOLD → amber-grey.
//
// Distinct from attestinfer/pcai/cryptopipeline (inference / lifecycle transcript):
// here the ACTION boundary is governed. Honesty label "MODELED" is read VERBATIM from
// the JSON and shown as-is; it is NEVER upgraded. The enclave quote is SIMULATED (no
// real TEE/enclave). The gate verdict is ADVISORY (deny-by-default; Λ advisory) — a
// HOLD is safe, an ALLOW is NOT a proof of safety. No PROVEN/VERIFIED/1.0 state.
//
// Surface export shape (mirrors cryptopipeline.js / kvcache.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from same-origin live endpoints, szl_confattest.py):
//   quote:  label, quote{simulated,attested,quote_digest,mrtd}, lambda{value,advisory_pass},
//           receipt{digest_sha256,signature}, spine{dsse,ledger,signed_on_read}
//   gate:   governs, action{effect_class,reversible}, policy{preconditions[],policy_pass},
//           lambda{value,advisory_pass}, verdict("ALLOW"|"HOLD"), reason
//
// PRIMARY SOURCES (cited verbatim on-surface; ids verified — 0 runtime CDN):
//   Governing Actions, Not Agents arXiv:2606.26298 · Parallax arXiv:2604.12986 ·
//   EnclaveX arXiv:2606.31408 · OpenPCC arXiv:2606.11145 · OPAQUE 3.0 (no arXiv id).
//
// HONESTY LABEL: MODELED — SIMULATED enclave attestation quote (NO real TEE/enclave);
//   deterministic + replayable. Action gate is deny-by-default + Λ-ADVISORY (Conjecture 1).
//   Read verbatim; never upgraded. Trust ceiling 0.97, never 100%.
// COLOURS: lattice-blue 0x5b8dee (enclave / spine), proof-teal 0x3af4c8 (attested / ALLOW),
//   amber 0xe8c074 (HOLD / advisory), greys (mismatch / degraded). Purple BANNED. No green/1.0.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ stays
//   Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "confattest";
const TITLE = "Confidential-Compute Attestation + Action Gate (live)";

// same-origin, relative — a11oy-NATIVE self-hosted primary (no CDN, no cross-origin).
const EP_QUOTE = "/api/a11oy/v1/confattest/quote?seed=42";
const EP_GATE  = "/api/a11oy/v1/confattest/gate?seed=42&action=agent.tool.call&effect=write";

// data-viz hues — purple BANNED, no green
const C_ENCLAVE = 0x5b8dee;  // lattice-blue (enclave body / spine)
const C_OK      = 0x3af4c8;  // proof-teal (attested / ALLOW)
const C_HOLD    = 0xe8c074;  // amber (HOLD / advisory)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badgeQ = null, _badgeG = null;

let _enclave = null, _receipt = null, _gate = null, _actionNode = null, _verdict = null;
let _edges = [];

const S = {
  // (a) quote
  qLabel:     null,
  attested:   null,   // bool
  quoteDigest:null,
  mrtd:       null,
  qLambda:    null,   // number
  receiptSig: null,
  dsse:       null,
  ledger:     null,
  signedOnRead: null,
  qState:     "init",
  // (b) gate
  governs:    null,
  effect:     null,
  reversible: null,
  policyPass: null,   // bool
  gLambda:    null,   // number
  verdict:    null,   // "ALLOW" | "HOLD"
  reason:     null,
  gState:     "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 5, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 1.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildScene();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badgeQ = ctx.live.createBadge();
  _badgeG = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP_QUOTE, 5000, _onQuote, { badge: _badgeQ, onState: (m) => { S.qState = m.state; _paint(); } }));
  _polls.push(ctx.live.poll(EP_GATE, 5000, _onGate, { badge: _badgeG, onState: (m) => { S.gState = m.state; _paint(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

// enclave(0) → receipt(1) → gate(2) → verdict(3), laid along X; action node feeds the gate.
function _buildScene() {
  const THREE = _THREE;

  // (a) confidential-compute enclave — a shielded box
  _enclave = new THREE.Mesh(
    new THREE.BoxGeometry(1.1, 1.1, 1.1),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.4, wireframe: false }),
  );
  _enclave.position.set(0, 0.9, 0);
  _group.add(_enclave);

  // receipt glyph (content-addressed digest of the quote)
  _receipt = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.42, 0),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.4 }),
  );
  _receipt.position.set(2.6, 0.9, 0);
  _group.add(_receipt);

  // (b) action gate — a torus the action must pass through
  _gate = new THREE.Mesh(
    new THREE.TorusGeometry(0.7, 0.14, 16, 40),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.5 }),
  );
  _gate.position.set(5.4, 0.9, 0);
  _gate.rotation.y = Math.PI / 2;
  _group.add(_gate);

  // the agent ACTION node (approaches the gate)
  _actionNode = new THREE.Mesh(
    new THREE.SphereGeometry(0.22, 20, 20),
    new THREE.MeshStandardMaterial({ color: C_ENCLAVE, emissive: C_ENCLAVE, emissiveIntensity: 0.4, transparent: true, opacity: 0.85 }),
  );
  _actionNode.position.set(4.3, 0.9, 0);
  _group.add(_actionNode);

  // verdict glyph (ALLOW/HOLD) beyond the gate
  _verdict = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.5, 1),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.5 }),
  );
  _verdict.position.set(7.6, 0.9, 0);
  _group.add(_verdict);

  // linking edges: enclave→receipt, receipt→gate, gate→verdict
  _edges.push(_mkLine(_enclave.position, _receipt.position, C_ENCLAVE, 0.4));
  _edges.push(_mkLine(_receipt.position, _gate.position, C_ENCLAVE, 0.4));
  _edges.push(_mkLine(_gate.position, _verdict.position, C_ENCLAVE, 0.4));
  _edges.forEach((e) => _group.add(e));
}

function _mkLine(a, b, color, opacity) {
  const THREE = _THREE;
  const geo = new THREE.BufferGeometry().setFromPoints([a.clone(), b.clone()]);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  return new THREE.Line(geo, mat);
}

// =============================================================================
// live data handlers
// =============================================================================
function _onQuote(j) {
  S.qLabel      = (j.label || "MODELED").toUpperCase();
  const q = j.quote || {};
  S.attested    = typeof q.attested === "boolean" ? q.attested : null;
  S.quoteDigest = typeof q.quote_digest === "string" ? q.quote_digest : null;
  S.mrtd        = typeof q.mrtd === "string" ? q.mrtd : null;
  const lam = j.lambda || {};
  S.qLambda     = typeof lam.value === "number" ? lam.value : null;
  const rc = j.receipt || {};
  S.receiptSig  = typeof rc.signature === "string" ? rc.signature : null;
  const sp = j.spine || {};
  S.dsse         = typeof sp.dsse === "string" ? sp.dsse : null;
  S.ledger       = typeof sp.ledger === "string" ? sp.ledger : null;
  S.signedOnRead = typeof sp.signed_on_read === "boolean" ? sp.signed_on_read : null;
  _updateScene(); _paint();
}

function _onGate(j) {
  S.governs    = typeof j.governs === "string" ? j.governs : null;
  const ac = j.action || {};
  S.effect     = typeof ac.effect_class === "string" ? ac.effect_class : null;
  S.reversible = typeof ac.reversible === "boolean" ? ac.reversible : null;
  const pol = j.policy || {};
  S.policyPass = typeof pol.policy_pass === "boolean" ? pol.policy_pass : null;
  const lam = j.lambda || {};
  S.gLambda    = typeof lam.value === "number" ? lam.value : null;
  S.verdict    = typeof j.verdict === "string" ? j.verdict : null;
  S.reason     = typeof j.reason === "string" ? j.reason : null;
  _updateScene(); _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const qLive = S.qState === "live";
  const gLive = S.gState === "live";

  // (a) enclave + receipt reflect attestation
  const attOk = qLive && S.attested === true;
  _setMat(_enclave, attOk ? C_ENCLAVE : (qLive ? C_HOLD : C_DIM), attOk ? C_OK : (qLive ? C_HOLD : C_DIM), attOk ? 0.5 : 0.25, attOk ? 0.95 : 0.4);
  _setMat(_receipt, attOk ? C_OK : (qLive ? C_HOLD : C_DIM), attOk ? C_OK : (qLive ? C_HOLD : C_DIM), attOk ? 0.55 : 0.25, attOk ? 0.9 : 0.4);

  // (b) gate + verdict reflect the advisory verdict
  const allow = gLive && S.verdict === "ALLOW";
  const hold  = gLive && S.verdict === "HOLD";
  const gcol = allow ? C_OK : (hold ? C_HOLD : C_DIM);
  _setMat(_gate, gcol, gcol, allow ? 0.5 : 0.3, gLive ? 0.85 : 0.5);
  _setMat(_verdict, gcol, gcol, allow ? 0.55 : 0.3, gLive ? 0.85 : 0.5);

  // edges glow when both legs are healthy
  const spine = attOk;
  for (const e of _edges) {
    e.material.color.setHex(spine ? C_ENCLAVE : (qLive ? C_HOLD : C_DIM));
    e.material.opacity = spine ? 0.45 : 0.2;
  }
}

function _setMat(mesh, color, emissive, ei, opacity) {
  if (!mesh) return;
  mesh.material.color.setHex(color);
  mesh.material.emissive.setHex(emissive);
  mesh.material.emissiveIntensity = ei;
  mesh.material.opacity = opacity;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.09;
  if (_verdict) { _verdict.rotation.y += 0.02; _verdict.rotation.x += 0.007; }
  if (_gate) _gate.rotation.z += 0.01;
  if (_actionNode) {
    // the action node oscillates toward the gate: passes through on ALLOW, bounces on HOLD
    const allow = S.verdict === "ALLOW";
    const base = allow ? 6.0 : 4.3;
    _actionNode.position.x = base + Math.sin(t * 0.002) * (allow ? 1.4 : 0.5);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badgeQ,
    chips: [{ label: "MODELED", text: "SIMULATED enclave quote", name: "ca" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'Two governance legs in one scene. <b>(a)</b> A confidential-compute <b>enclave</b> emits a ' +
      '<b>SIMULATED</b> attestation quote (Intel-TDX MRTD + NVIDIA-CC EAT shape) chained into a ' +
      'content-addressed <b>receipt</b> — there is <b>NO real TEE/enclave</b>, values are SHA-derived ' +
      'and replayable. <b>(b)</b> An <b>action gate</b> that <b>governs the ACTION effect, NOT the ' +
      'reasoning</b> (clean-room of "Governing Actions, Not Agents"): deny-by-default over ' +
      'independently-attested preconditions, with Λ as an <b>advisory</b> axis (Conjecture 1). A ' +
      '<b>HOLD</b> is safe; an <b>ALLOW</b> is <b>not a proof of safety</b>. Label <b>MODELED</b>, ' +
      'read verbatim. Receipt UNSIGNED-LOCAL (signing is on-write, never on this GET). 0 runtime CDN.',
    citations:
      "Governing Actions, Not Agents arXiv:2606.26298 · Parallax arXiv:2604.12986 · " +
      "EnclaveX arXiv:2606.31408 · OpenPCC arXiv:2606.11145 · OPAQUE 3.0 (no arXiv id). " +
      "MODELED/SIMULATED · not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["ca-att"]     = _show.addField("enclave attested? (SIMULATED)");
  _el["ca-mrtd"]    = _show.addField("enclave MRTD (sha384)");
  _el["ca-qlam"]    = _show.addField("Λ advisory — quote (Conjecture 1)");
  _el["ca-receipt"] = _show.addField("quote receipt signature");
  _el["ca-governs"] = _show.addField("gate governs");
  _el["ca-action"]  = _show.addField("action effect · reversible");
  _el["ca-policy"]  = _show.addField("policy (deny-by-default)");
  _el["ca-glam"]    = _show.addField("Λ advisory — gate (Conjecture 1)");
  _el["ca-verdict"] = _show.addField("verdict (advisory, never proof)");
  _el["ca-spine"]   = _show.addField("DSSE/ledger spine (read-only)");
  _el["ca-label"]   = _show.addField("honesty label");

  _paint();
}

function _plainHtml() {
  const att = S.attested == null ? "loading…" : (S.attested ? "yes" : "no (mismatch)");
  const v = S.verdict || "loading…";
  return (
    "<b>What this means:</b> A confidential-compute <b>enclave</b> is a locked box that a program " +
    "runs inside; it can produce an <b>attestation quote</b> — a signed statement of what code it " +
    "loaded. Here that quote is <b>SIMULATED</b> (we never touch a real enclave), and it attests: <b>" +
    att + "</b>. We then <b>govern the agent's ACTION, not its thinking</b>: before the action can " +
    "cause a side effect, a gate checks independently-attested preconditions (deny-by-default). The " +
    "current verdict is <b>" + v + "</b>. A <b>HOLD</b> means “don’t act yet” (safe); " +
    "an <b>ALLOW</b> is advisory — it is <b>not a proof</b> the action is safe. Λ is an advisory " +
    "trust reading (Conjecture 1), never a guarantee.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paint() {
  const tq = _tok(S.qState);
  const tg = _tok(S.gState);
  _set("ca-att",     tq || (S.attested == null ? "—" : (S.attested ? "yes (SIMULATED)" : "no (SIMULATED mismatch)")));
  _set("ca-mrtd",    tq || (S.mrtd ? S.mrtd.slice(0, 24) + "…" : "—"));
  _set("ca-qlam",    tq || (S.qLambda == null ? "—" : String(S.qLambda) + " (advisory)"));
  _set("ca-receipt", tq || (S.receiptSig || "—"));
  _set("ca-governs", tg || (S.governs || "—"));
  _set("ca-action",  tg || ((S.effect || "—") + " · reversible=" + (S.reversible == null ? "—" : String(S.reversible))));
  _set("ca-policy",  tg || (S.policyPass == null ? "—" : (S.policyPass ? "pass" : "DENY (deny-by-default)")));
  _set("ca-glam",    tg || (S.gLambda == null ? "—" : String(S.gLambda) + " (advisory)"));
  _set("ca-verdict", tg || (S.verdict ? (S.verdict + " — advisory, not a safety proof") : "—"));
  _set("ca-spine",   tq || ("dsse=" + (S.dsse || "—") + " · ledger=" + (S.ledger || "—") + " · signed_on_read=" + (S.signedOnRead === false ? "no" : String(S.signedOnRead))));
  // honesty label verbatim — never upgraded
  _set("ca-label",   tq || (S.qLabel || "MODELED"));
  if (_show) { _show.setChip("ca", S.qLabel || "MODELED", { text: "SIMULATED enclave quote" }); _show.refreshPlain(); }
}

// =============================================================================
// unmount
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
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _enclave = _receipt = _gate = _actionNode = _verdict = null;
  _edges = []; _el = {}; _badgeQ = _badgeG = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.qLabel = S.attested = S.quoteDigest = S.mrtd = S.qLambda = S.receiptSig = null;
  S.dsse = S.ledger = S.signedOnRead = null;
  S.governs = S.effect = S.reversible = S.policyPass = S.gLambda = S.verdict = S.reason = null;
  S.qState = S.gState = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP_QUOTE, EP_GATE], mount, unmount };
