// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/pddisagg.js — PREFILL/DECODE DISAGGREGATION MAP for the holographic frontier
// ring. An HONEST, STRUCTURAL-ONLY diagram + latency-model of splitting the PREFILL stage
// (compute-bound, prompt ingestion, TTFT) from the DECODE stage (memory-bandwidth-bound,
// token generation, TPOT) across the a11oy mesh nodes (omen / betterwithage). Two node
// pillars are drawn (prefill node → decode node) with a KV-cache handoff arc between them;
// paired bars contrast the COLOCATED single-pool baseline against the DISAGGREGATED split.
// a11oy does NOT yet disaggregate — nothing here routes a real request; every latency
// figure is a closed-form arithmetic MODEL, so the label is STRUCTURAL-ONLY / ROADMAP.
// Live snapshot (same-origin, szl_pddisagg.py):
//   /api/a11oy/v1/frontier/pddisagg
//
// FRONTIER CONTEXT (cited; NOT claimed as SZL's own):
//   NVIDIA Dynamo v1.2.0 — disaggregated serving / PD disaggregation, github.com/ai-dynamo/dynamo.
//   PD-disaggregation survey — arXiv:2603.13358.
//   DeepSeek/DistServe — Zhong et al. 2024, arXiv:2401.09670.
//   Splitwise — Patel et al. 2024, arXiv:2311.18677.
//
// HONESTY LABEL: STRUCTURAL-ONLY (roadmap latency model; a11oy does not disaggregate today,
//   never MEASURED). Read from the JSON; never upgraded.
// COLOURS: grey base grid, lattice-blue 0x5b8dee (prefill / colocated bar), proof-teal
//   0x3af4c8 (decode / disaggregated bar), violet-blue 0x8a6bff (KV handoff arc / HUD accent).
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "pddisagg";
const TITLE = "Prefill/Decode Disaggregation Map (STRUCTURAL-ONLY)";

// Served SAME-ORIGIN by szl_pddisagg.py — a closed-form structural latency model.
const EP = "/api/a11oy/v1/frontier/pddisagg?prompt_tokens=1024&gen_tokens=256";

// data-viz hues — purple BANNED
const C_PREFILL = 0x5b8dee;  // lattice-blue (prefill node / colocated baseline bar)
const C_DECODE  = 0x3af4c8;  // proof-teal (decode node / disaggregated bar)
const C_KV      = 0x8a6bff;  // violet-blue (KV-cache handoff arc / accent)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / axis colour

// layout geometry (world units)
const NODE_X   = 5.0;    // node pillar |x| offset (prefill left, decode right)
const BAR_X    = 5.5;    // latency bar |x| offset
const BAR_W    = 1.2;    // latency bar width
const BAR_CAP  = 8.0;    // world height for the tallest latency bar

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor = null;
let _prefillNode = null;   // THREE.Mesh — prefill node pillar (omen)
let _decodeNode = null;    // THREE.Mesh — decode node pillar (betterwithage)
let _kvArc = null;         // THREE.Line — KV-cache handoff arc prefill→decode
let _coBar = null;         // THREE.Mesh — colocated total-latency bar
let _diBar = null;         // THREE.Mesh — disaggregated total-latency bar

// live state
const S = {
  label: null,
  promptTokens: null, genTokens: null,
  prefillNode: null, decodeNode: null,
  coTtft: null, coTpot: null, coTotal: null,
  diTtft: null, diTpot: null, diTotal: null, kvTransfer: null,
  speedup: null,
  receiptSigned: null, receiptDigest: null,
  state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 7, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 3, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildNodes();
  _buildKvArc();
  _buildBars();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paint(); },
  }));
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

function _buildNodes() {
  const THREE = _THREE;
  const geo = new THREE.CylinderGeometry(0.9, 0.9, 2.0, 24);

  _prefillNode = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.85 }));
  _prefillNode.position.set(-NODE_X, 1.0, 0);
  _group.add(_prefillNode);

  _decodeNode = new THREE.Mesh(geo.clone(), new THREE.MeshStandardMaterial({
    color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.25, transparent: true, opacity: 0.85 }));
  _decodeNode.position.set(NODE_X, 1.0, 0);
  _group.add(_decodeNode);
}

// KV-cache handoff arc: prefill node → decode node (the disaggregation tax).
function _buildKvArc() {
  const THREE = _THREE;
  const pts = [];
  for (let i = 0; i <= 32; i++) {
    const t = i / 32;
    const x = -NODE_X + t * (2 * NODE_X);
    const y = 2.4 + Math.sin(Math.PI * t) * 2.6;   // arched handoff
    pts.push(new THREE.Vector3(x, y, 0));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  _kvArc = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.4 }));
  _group.add(_kvArc);
}

function _buildBars() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(BAR_W, 1, BAR_W);

  _coBar = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: C_PREFILL, emissive: C_PREFILL, emissiveIntensity: 0.22, transparent: true, opacity: 0.8 }));
  _coBar.position.set(-BAR_X, 0, -6);
  _coBar.visible = false;
  _group.add(_coBar);

  _diBar = new THREE.Mesh(geo.clone(), new THREE.MeshStandardMaterial({
    color: C_DECODE, emissive: C_DECODE, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _diBar.position.set(-BAR_X + 1.6, 0, -6);
  _diBar.visible = false;
  _group.add(_diBar);
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const raw = (j && j.label) || (p && p.label) || "STRUCTURAL-ONLY";
  // honesty label read from JSON; runtime default STRUCTURAL-ONLY, never upgraded.
  S.label = (raw || "STRUCTURAL-ONLY");
  S.label = String(S.label).toUpperCase();

  S.promptTokens = typeof p.prompt_tokens === "number" ? p.prompt_tokens : null;
  S.genTokens    = typeof p.gen_tokens === "number" ? p.gen_tokens : null;

  const st = (p && typeof p.stages === "object") ? p.stages : {};
  S.prefillNode = (st.prefill && st.prefill.node) || null;
  S.decodeNode  = (st.decode && st.decode.node) || null;

  const co = (p && typeof p.colocated === "object") ? p.colocated : {};
  S.coTtft  = typeof co.ttft_ms === "number" ? co.ttft_ms : null;
  S.coTpot  = typeof co.tpot_ms === "number" ? co.tpot_ms : null;
  S.coTotal = typeof co.total_ms === "number" ? co.total_ms : null;

  const di = (p && typeof p.disaggregated === "object") ? p.disaggregated : {};
  S.diTtft     = typeof di.ttft_ms === "number" ? di.ttft_ms : null;
  S.diTpot     = typeof di.tpot_ms === "number" ? di.tpot_ms : null;
  S.diTotal    = typeof di.total_ms === "number" ? di.total_ms : null;
  S.kvTransfer = typeof di.kv_transfer_ms === "number" ? di.kv_transfer_ms : null;

  S.speedup = typeof p.speedup === "number" ? p.speedup : null;

  const rd = (p && typeof p.receipt_design === "object") ? p.receipt_design : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // node pillars: light up prefill (blue) and decode (teal) when live.
  if (_prefillNode) {
    const c = live ? C_PREFILL : C_DIM;
    _prefillNode.material.color.setHex(c); _prefillNode.material.emissive.setHex(c);
    _prefillNode.material.opacity = live ? 0.95 : 0.85;
  }
  if (_decodeNode) {
    const c = live ? C_DECODE : C_DIM;
    _decodeNode.material.color.setHex(c); _decodeNode.material.emissive.setHex(c);
    _decodeNode.material.opacity = live ? 0.95 : 0.85;
  }

  // KV handoff arc glows violet when live (the disaggregation tax path).
  if (_kvArc) {
    const c = live ? C_KV : C_DIM;
    _kvArc.material.color.setHex(c);
    _kvArc.material.opacity = live ? 0.85 : 0.4;
  }

  // latency bars scaled to a shared cap (colocated is the taller/slower baseline).
  const maxV = Math.max(1, S.coTotal || 1, S.diTotal || 1);
  const norm = (v) => Math.max(0.05, (v / maxV) * BAR_CAP);
  if (_coBar) {
    if (live && S.coTotal != null) {
      const h = norm(S.coTotal); _coBar.scale.y = h; _coBar.position.y = h / 2;
      _coBar.material.color.setHex(C_PREFILL); _coBar.material.emissive.setHex(C_PREFILL);
      _coBar.visible = true;
    } else { _coBar.visible = false; }
  }
  if (_diBar) {
    if (live && S.diTotal != null) {
      const h = norm(S.diTotal); _diBar.scale.y = h; _diBar.position.y = h / 2;
      _diBar.material.color.setHex(C_DECODE); _diBar.material.emissive.setHex(C_DECODE);
      _diBar.visible = true;
    } else { _diBar.visible = false; }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.10;
  if (_kvArc && _kvArc.visible && S.state === "live") {
    const pulse = 0.6 + 0.4 * Math.abs(Math.sin(t * 0.0018));
    _kvArc.material.opacity = pulse;
  }
}

// =============================================================================
// showcase overlay (shared helper)
// =============================================================================
function _buildShowcase(ctx) {
  _show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "STRUCTURAL-ONLY", text: "prefill ↔ decode split", name: "pd" },
    ],
    legend: ["STRUCTURAL-ONLY", "ROADMAP"],
    description:
      "<b>Prefill/Decode Disaggregation Map.</b> A closed-form latency model of splitting the " +
      "<b style=\"color:#5b8dee\">prefill</b> stage (compute-bound, prompt ingestion / TTFT) from " +
      "the <b style=\"color:#3af4c8\">decode</b> stage (memory-bandwidth-bound, token generation / " +
      "TPOT) across the a11oy mesh nodes (omen / betterwithage). The " +
      "<b style=\"color:#8a6bff\">violet</b> arc is the cross-node KV-cache handoff — the tax paid " +
      "to disaggregate. Paired bars contrast the COLOCATED single-pool baseline against the " +
      "DISAGGREGATED split. a11oy does NOT disaggregate today — every figure is " +
      "<b>STRUCTURAL-ONLY / ROADMAP</b>, never a MEASURED serving result.",
    citations:
      "NVIDIA Dynamo v1.2.0 (github.com/ai-dynamo/dynamo) · PD-disaggregation survey " +
      "arXiv:2603.13358 · DistServe arXiv:2401.09670 · Splitwise arXiv:2311.18677. " +
      "STRUCTURAL-ONLY · ROADMAP — a11oy claims none of these systems as its own and does not " +
      "route a real disaggregated request. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "Serving a big model has two very different phases: <b>reading your prompt</b> (fast, " +
        "compute-heavy) and <b>writing the answer</b> one token at a time (slow, memory-heavy). " +
        "Running both on the same GPU makes them fight for resources. <b>Disaggregation</b> puts " +
        "each phase on its own machine so neither slows the other down — at the cost of shipping " +
        "the prompt's cached state between them. This map <b>estimates</b> what that split would " +
        "cost across a11oy's two nodes. These are <b>modeled estimates</b>, not measurements — " +
        "a11oy does not actually split requests this way yet, and nothing is signed just by " +
        "viewing this page.",
    },
  });

  _f.tokens  = _show.addField("prompt / gen tokens", "tokens");
  _f.map     = _show.addField("prefill → decode node", "map");
  _f.co      = _show.addField("colocated total (ms)", "co");
  _f.di      = _show.addField("disaggregated total (ms)", "di");
  _f.kv      = _show.addField("KV-cache handoff (ms)", "kv");
  _f.speedup = _show.addField("modeled speedup", "speedup");
  _f.receipt = _show.addField("map receipt", "receipt");
  _f.label   = _show.addField("honesty label", "label");
  _paint();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(k, v) { if (_f[k]) _f[k].textContent = v; }

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("pd", S.label || "STRUCTURAL-ONLY", { text: "prefill ↔ decode split" });

  _set("tokens", t || ((S.promptTokens != null ? S.promptTokens : "—") + " / " + (S.genTokens != null ? S.genTokens : "—")));
  _set("map",    t || ((S.prefillNode || "—") + " → " + (S.decodeNode || "—")));
  _set("co",     t || fx(S.coTotal, 2));
  _set("di",     t || fx(S.diTotal, 2));
  _set("kv",     t || fx(S.kvTransfer, 2));
  _set("speedup", t || (S.speedup != null ? fx(S.speedup, 4) + "×" : "—"));
  _set("receipt", t || (S.receiptSigned === false
        ? "unsigned preview" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptDigest ? S.receiptDigest.slice(0, 10) + "…" : "—")));
  _set("label", t || (S.label || "STRUCTURAL-ONLY"));
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
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
  _floor = _prefillNode = _decodeNode = _kvArc = _coBar = _diBar = null;
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.promptTokens = S.genTokens = S.prefillNode = S.decodeNode = null;
  S.coTtft = S.coTpot = S.coTotal = S.diTtft = S.diTpot = S.diTotal = S.kvTransfer = null;
  S.speedup = S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
