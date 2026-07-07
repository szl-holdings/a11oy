// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/cryptopipeline.js — CRYPTO-PIPELINE end-to-end AI-lifecycle verifiable
// transcript organ for the holographic frontier ring. Renders the four lifecycle
// stages — data-sourcing → training → inference → unlearning — as a hash-linked
// chain of commitment nodes: each stage node glows proof-teal when its recomputed
// link checks out, and the linking edges + a transcript-root glyph above show the
// composed end-to-end transcript. A tampered stage flips grey/broken to make the
// honesty legible: the hash chain DETECTS mutation.
//
// Distinct from zkinfer/attestinfer (inference-only). Here the whole PIPELINE is
// committed and linked. Honesty label "MODELED" is read VERBATIM from the JSON and
// displayed as-is; it is NEVER upgraded. The commit/link/root hashing is REAL and
// recomputable; the per-stage zk PROOF objects are SIMULATED (no SNARK). No
// PROVEN/VERIFIED/1.0 state anywhere.
//
// Surface export shape (mirrors kvcache.js / zkinfer.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from same-origin live endpoint, szl_crypto_pipeline.py):
//   label, lifecycle[], stages[]{stage,title,commit,link,tampered,proof{label,...}},
//   transcript_root, chain_consistent, verify{per_link[],root_ok}, tamper{...},
//   spine{dsse,ledger,signed_on_read}, receipt{digest_sha256,signature}
//
// PRIMARY SOURCES (cited verbatim on-surface; IDs only — 0 runtime CDN):
//   End-to-End AI-Pipeline Verifiability arXiv:2503.22573 · zkLLM arXiv:2404.16109 ·
//   Artemis commit-and-prove zkML arXiv:2409.12055 · SafetyNets arXiv:1706.10268.
//
// HONESTY LABEL: MODELED — real SHA-256 commitment/link/root chaining; per-stage zk
//   proofs SIMULATED (hash-commit chain, NOT a real SNARK/zk proof). Read verbatim;
//   never upgraded here. Trust ceiling 0.97, never 100%.
// COLOURS: lattice-blue 0x5b8dee (chain spine / stage body), proof-teal 0x3af4c8
//   (consistent link / transcript root), greys (broken/tampered/degraded). Purple
//   BANNED. No green/1.0 verified state.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ stays
//   Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "cryptopipeline";
const TITLE = "Crypto-Pipeline · End-to-End AI Lifecycle Verifiable Transcript (live)";

// same-origin, relative — a11oy-NATIVE self-hosted primary (no CDN, no cross-origin).
const EP = "/api/a11oy/v1/cryptopipeline/transcript?seed=42";

// data-viz hues — purple BANNED, no green
const C_STAGE   = 0x5b8dee;  // lattice-blue (stage commitment node / chain spine)
const C_OK      = 0x3af4c8;  // proof-teal (consistent link / transcript root)
const C_BROKEN  = 0x5a6570;  // grey (tampered / broken link)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

const STAGE_GAP = 3.2;       // world-units between stage nodes along X
const ROW_Y     = 0.6;       // resting height of a stage node
const ROOT_Y    = 4.2;       // height of the transcript-root glyph

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _floor = null, _root = null;
let _nodeMesh = [];   // Array<THREE.Mesh> — one per lifecycle stage
let _edgeLine = [];   // Array<THREE.Line> — chain link edges + root spokes

const S = {
  label:           null,
  lifecycle:       null,   // string[]
  stages:          null,   // object[]
  transcriptRoot:  null,   // string (hex)
  chainConsistent: null,   // bool
  tamperStage:     null,   // string
  tamperOk:        null,   // bool (chain_consistent_after_tamper)
  dsse:            null,   // spine.dsse
  ledger:          null,   // spine.ledger
  signedOnRead:    null,   // spine.signed_on_read
  receiptSig:      null,   // receipt.signature
  state:           "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(5, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(4.8, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildChain();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onData, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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
  _floor = grid;
}

// Four stage nodes in a row, chained left→right, each also spoked up to a
// transcript-root glyph. Built once; colours/positions toggle in-place on poll.
function _buildChain() {
  const THREE = _THREE;
  const N = 4; // data-sourcing, training, inference, unlearning

  // transcript-root glyph (the composed end-to-end commitment)
  _root = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.5, 1),
    new THREE.MeshStandardMaterial({ color: C_OK, emissive: C_OK, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.5 }),
  );
  _root.position.set(STAGE_GAP * (N - 1) / 2, ROOT_Y, 0);
  _group.add(_root);

  const nodeGeo = new THREE.BoxGeometry(0.7, 0.7, 0.7);
  for (let i = 0; i < N; i++) {
    const x = i * STAGE_GAP;
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.35 }),
    );
    mesh.position.set(x, ROW_Y, 0);
    _group.add(mesh);
    _nodeMesh.push(mesh);

    // spoke up to the transcript root
    const spoke = _mkLine(new THREE.Vector3(x, ROW_Y, 0), _root.position.clone(), C_GRID, 0.2);
    _group.add(spoke); _edgeLine.push(spoke);

    // chain link edge to previous stage
    if (i > 0) {
      const edge = _mkLine(new THREE.Vector3((i - 1) * STAGE_GAP, ROW_Y, 0),
                           new THREE.Vector3(x, ROW_Y, 0), C_STAGE, 0.5);
      _group.add(edge); _edgeLine.push(edge);
    }
  }
}

function _mkLine(a, b, color, opacity) {
  const THREE = _THREE;
  const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  return new THREE.Line(geo, mat);
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  S.label           = (j.label || "MODELED").toUpperCase();
  S.lifecycle       = Array.isArray(j.lifecycle) ? j.lifecycle : null;
  S.stages          = Array.isArray(j.stages) ? j.stages : null;
  S.transcriptRoot  = typeof j.transcript_root === "string" ? j.transcript_root : null;
  S.chainConsistent = typeof j.chain_consistent === "boolean" ? j.chain_consistent : null;
  const tam = j.tamper || {};
  S.tamperStage = typeof tam.tampered_stage === "string" ? tam.tampered_stage : null;
  S.tamperOk    = typeof tam.chain_consistent_after_tamper === "boolean" ? tam.chain_consistent_after_tamper : null;
  const sp = j.spine || {};
  S.dsse         = typeof sp.dsse === "string" ? sp.dsse : null;
  S.ledger       = typeof sp.ledger === "string" ? sp.ledger : null;
  S.signedOnRead = typeof sp.signed_on_read === "boolean" ? sp.signed_on_read : null;
  const rc = j.receipt || {};
  S.receiptSig = typeof rc.signature === "string" ? rc.signature : null;

  _updateChain();
  _paintOverlay();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateChain() {
  const live = S.state === "live" && S.stages && S.stages.length;
  const perLink = live ? S.stages : [];

  for (let i = 0; i < _nodeMesh.length; i++) {
    const mesh = _nodeMesh[i];
    if (!live || i >= perLink.length) {
      mesh.material.color.setHex(C_DIM); mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.15; mesh.material.opacity = 0.3;
      continue;
    }
    const st = perLink[i];
    const broken = !!st.tampered;
    const color = broken ? C_BROKEN : C_STAGE;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(broken ? C_BROKEN : C_OK);
    mesh.material.emissiveIntensity = broken ? 0.15 : 0.55;
    mesh.material.opacity = broken ? 0.4 : 0.95;
  }

  // chain link edges + root spokes reflect whole-chain consistency
  const ok = live && S.chainConsistent === true;
  for (const ln of _edgeLine) {
    ln.material.color.setHex(ok ? C_STAGE : (live ? C_BROKEN : C_DIM));
    ln.material.opacity = ok ? 0.5 : (live ? 0.3 : 0.15);
  }
  if (_root) {
    const rc = ok ? C_OK : (live ? C_BROKEN : C_DIM);
    _root.material.color.setHex(rc);
    _root.material.emissive.setHex(rc);
    _root.material.opacity = ok ? 0.6 : 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.1;
  if (_root) {
    _root.rotation.y += 0.02; _root.rotation.x += 0.008;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.004);
    _root.scale.setScalar(pulse);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MODELED", text: "hash-commit chain", name: "cp" }],
    legend: ["MODELED", "SIMULATED"],
    description:
      'The full AI lifecycle — <b>data-sourcing → training → inference → unlearning</b> ' +
      '— as a hash-linked chain of commitments composing into ONE end-to-end verifiable ' +
      'transcript. Each stage takes a real SHA-256 commitment over its content and links it to ' +
      'the previous stage; a transcript root binds them all. The <b>commit/link/root hashing is ' +
      'REAL and recomputable</b>; the per-stage zk proofs are <b>SIMULATED</b> (hash-commit chain, ' +
      'NOT a real SNARK). A tampered stage is shown breaking the chain. Honesty label ' +
      '<b>MODELED</b>, read verbatim. 0 runtime CDN.',
    citations:
      "End-to-End Pipeline Verifiability arXiv:2503.22573 · zkLLM arXiv:2404.16109 · " +
      "Artemis arXiv:2409.12055 · SafetyNets arXiv:1706.10268. MODELED/SIMULATED · not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["cp-lifecycle"] = _show.addField("lifecycle stages");
  _el["cp-root"]      = _show.addField("transcript_root (sha256)");
  _el["cp-consistent"]= _show.addField("chain_consistent (hash chain) — MODELED");
  _el["cp-proof"]     = _show.addField("per-stage zk proof");
  _el["cp-tamper"]    = _show.addField("tamper demo (mutated stage → chain)");
  _el["cp-dsse"]      = _show.addField("DSSE spine (advisory, read-only)");
  _el["cp-ledger"]    = _show.addField("durable-ledger spine (advisory)");
  _el["cp-sign"]      = _show.addField("signed on this GET?");
  _el["cp-receipt"]   = _show.addField("local receipt signature");
  _el["cp-label"]     = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const root = S.transcriptRoot ? S.transcriptRoot.slice(0, 12) + "…" : "loading…";
  const cons = S.chainConsistent == null ? "loading…" : (S.chainConsistent ? "yes" : "no (tampered)");
  return (
    "<b>What this means:</b> An AI system passes through four life stages — collecting data, " +
    "training on it, answering questions (inference), and later forgetting a record (unlearning). " +
    "At each stage we take a tamper-evident fingerprint (a hash) of what happened and chain it to the " +
    "one before, ending in a single <b>transcript root</b> (" + root + ") that stands for the whole " +
    "history. Anyone can re-derive the chain and check it matches — here it is <b>" + cons + "</b>. " +
    "If any stage were altered, the chain would visibly break. This is a <b>MODELED</b> hash-commit " +
    "chain: the linking is real, but the zero-knowledge proofs are <b>SIMULATED</b> — we do NOT " +
    "generate or check a real SNARK, and never claim one.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("cp-lifecycle", t || (S.lifecycle ? S.lifecycle.join(" → ") : "—"));
  _set("cp-root",      t || (S.transcriptRoot ? S.transcriptRoot.slice(0, 24) + "…" : "—"));
  _set("cp-consistent",t || (S.chainConsistent == null ? "—" : (S.chainConsistent ? "true" : "false (tampered)")));
  _set("cp-proof",     t || "SIMULATED (no SNARK generated)");
  _set("cp-tamper",    t || (S.tamperStage ? (S.tamperStage + " → consistent=" + (S.tamperOk === false ? "false (chain breaks)" : String(S.tamperOk))) : "—"));
  _set("cp-dsse",      t || (S.dsse || "—"));
  _set("cp-ledger",    t || (S.ledger || "—"));
  _set("cp-sign",      t || (S.signedOnRead === false ? "no (receipt-on-write only)" : String(S.signedOnRead)));
  _set("cp-receipt",   t || (S.receiptSig || "—"));
  // honesty label verbatim — never upgraded
  _set("cp-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("cp", S.label || "MODELED", { text: "hash-commit chain" }); _show.refreshPlain(); }
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
  _floor = null; _root = null; _nodeMesh = []; _edgeLine = [];
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.lifecycle = S.stages = S.transcriptRoot = S.chainConsistent = null;
  S.tamperStage = S.tamperOk = S.dsse = S.ledger = S.signedOnRead = S.receiptSig = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
