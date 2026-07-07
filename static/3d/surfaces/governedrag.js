// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/governedrag.js — GOVERNED RAG · retrieval-with-receipts holographic surface (Wave J · Dev 4).
//
// The differentiator, rendered live: EVERY retrieved answer ships a SIGNED receipt
//   proving WHICH source passages grounded WHICH claims. RAG systems retrieve and
//   generate; almost none emit a machine-checkable, signed per-claim attribution
//   gated on a faithfulness score. That governance layer is what SZL adds on top
//   of the retrieval SOTA.
//
// Leaders studied + composed (citable, non-leaked): dense retrieval DPR
//   (arxiv 2004.04906), hybrid BM25+dense with reciprocal-rank fusion, ColBERT
//   late-interaction (arxiv 2004.12832), cross-encoder rerankers (Cohere Rerank),
//   GraphRAG (Microsoft), Anthropic contextual retrieval, citation-grounded
//   generation / ALCE (arxiv 2305.14627), and RAGAS reference-free eval
//   (arxiv 2309.15217). SZL's governed version folds them into ONE deterministic,
//   honest pipeline with a Λ-gate + signed per-claim receipt.
//
// EVERY value on screen traces to a REAL a11oy endpoint (doctrine v11 — never fabricate):
//   * GET  /api/a11oy/v1/rag/corpus   — the embedded demo corpus (id/text/source) + sha256
//   * POST /api/a11oy/v1/rag/query    — Λ-gated grounded answer → per-claim citations →
//                                       signed receipt → /llm/forum (the demo)
//
// The scene: a ring of CORPUS-PASSAGE nodes around a central QUERY core; when a
// query fires, grounding BEAMS light from the passages that grounded each claim to
// the core (color = grounded/ungrounded), and a floating RECEIPT panel shows the
// live signed per-claim citation map + RAGAS faithfulness + advisory Λ. Honesty
// labels are read straight from the JSON. Degrades gracefully; no crash, no fake data.
//
// 0 runtime CDN: three resolves through the page importmap to /static/3d/vendor/.

const ID = "governedrag";
const TITLE = "Governed RAG · Retrieval-with-Receipts";
const EP_CORPUS = "/api/a11oy/v1/rag/corpus";
const EP_QUERY = "/api/a11oy/v1/rag/query";

// palette (matches the estate)
const C_PASSAGE = 0x39d3c4;   // corpus passage — teal
const C_GROUND = 0x2fd07a;    // grounded citation beam — green
const C_UNGROUND = 0x8a6a3a;  // ungrounded — dim gold
const C_CORE = 0xe8c074;      // query core — gold
const C_BEAM = 0x6fb1ff;      // retrieval beam — blue

let _stage = null, _THREE = null, _ctx = null;
let _group = null, _overlay = null, _frameReg = false;
let _passageNodes = [];      // { mesh, label, id }
let _core = null, _beams = [], _billboard = null;
let _poll = null, _badge = null;

const S = {
  corpus: [],
  label: null, state: "init", degraded: false,
  selectedModel: "",           // optional; blank = extractive/MODELED (honest w/o key)
  lastReceipt: null, lastAnswer: null, lastClaims: [], lastRagas: null,
  queryState: "idle",
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);
  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 6, 18);
  try { _stage.setBloom(true); } catch (_) {}

  _buildCore();
  try {
    _billboard = ctx.label.billboard(THREE, "MODELED", { text: "retrieval-with-receipts · per-claim citations", scale: 0.6, position: [0, 6.4, 0] });
    _group.add(_billboard);
  } catch (_) {}

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  _poll = ctx.live.poll(EP_CORPUS, 12000, _onCorpus, {
    badge: _badge,
    onState: (m) => { S.state = m.state; S.label = m.label || S.label; if (m.state !== "live") _paintOverlay(); },
  });

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.3, 1),
    new THREE.MeshStandardMaterial({ color: C_CORE, emissive: C_CORE, emissiveIntensity: 0.55, metalness: 0.4, roughness: 0.4, transparent: true, opacity: 0.92 }),
  );
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.7, 1),
    new THREE.MeshBasicMaterial({ color: C_CORE, wireframe: true, transparent: true, opacity: 0.28 }),
  );
  _core.add(core, shell);
  _core.core = core;
  _group.add(_core);
  try {
    _core.lbl = _ctx.label.billboard(_THREE, "QUERY", { text: "grounded answer core", scale: 0.5, position: [0, -2.1, 0] });
    _core.add(_core.lbl);
  } catch (_) {}
}

function _renderCorpusRing() {
  const THREE = _THREE;
  _passageNodes.forEach((n) => { try { _group.remove(n.mesh); } catch (_) {} try { if (n.label) _group.remove(n.label); } catch (_) {} });
  _passageNodes = [];

  const ps = S.corpus;
  const R = 6.6;
  ps.forEach((p, i) => {
    const ang = (i / Math.max(ps.length, 1)) * Math.PI * 2;
    const x = Math.cos(ang) * R, z = Math.sin(ang) * R;
    const mesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.62, 0),
      new THREE.MeshStandardMaterial({ color: C_PASSAGE, emissive: C_PASSAGE, emissiveIntensity: 0.5, metalness: 0.35, roughness: 0.45, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(x, 1.2 + (i % 2) * 0.4, z);
    mesh.userData = { id: p.id };
    _group.add(mesh);
    let label = null;
    try {
      label = _ctx.label.billboard(_THREE, p.id, { text: (p.source || "").slice(0, 28), scale: 0.4, position: [x, 2.3 + (i % 2) * 0.4, z] });
      _group.add(label);
    } catch (_) {}
    _passageNodes.push({ mesh, label, id: p.id });
  });
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onCorpus(json, meta) {
  S.degraded = !!meta.degraded;
  S.label = meta.label || S.label;
  if (!json || !Array.isArray(json.corpus)) { _paintOverlay(); return; }
  S.corpus = json.corpus;
  _renderCorpusRing();
  _paintOverlay();
  if (_billboard && _ctx) {
    try {
      _group.remove(_billboard);
      _billboard = _ctx.label.billboard(_THREE, "MODELED", {
        text: `corpus: ${json.corpus_size} passages · sha ${(json.corpus_sha256 || "").slice(0, 10)}…`, scale: 0.56, position: [0, 6.4, 0],
      });
      _group.add(_billboard);
    } catch (_) {}
  }
}

// POST query → grounded answer + per-claim citations + signed receipt (the demo)
async function _fireQuery() {
  const q = (_el.query && _el.query.value || "").trim();
  if (!q) { S.queryState = "empty query"; _paintOverlay(); return; }
  S.queryState = "querying";
  _paintOverlay();
  try {
    const bodyObj = { query: q, top_k: 4 };
    if (S.selectedModel) bodyObj.model_id = S.selectedModel;
    const res = await fetch(EP_QUERY, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(bodyObj),
    });
    if (!res.ok) { S.queryState = "error(" + res.status + ")"; _paintOverlay(); return; }
    const json = await res.json();
    S.lastReceipt = json.rag_receipt || null;
    S.lastAnswer = json.grounded_answer || null;
    S.lastClaims = Array.isArray(json.claims) ? json.claims : [];
    S.lastRagas = json.ragas || null;
    S.queryState = json.rag_state || "done";
    _fireGroundingBeams();
    _paintOverlay();
    _paintReceipt();
  } catch (e) {
    S.queryState = "error";
    _paintOverlay();
  }
}

// light beams from the passages that grounded each claim into the query core
function _fireGroundingBeams() {
  _beams.forEach((b) => { try { _group.remove(b); } catch (_) {} });
  _beams = [];
  const THREE = _THREE;
  const grounded = new Set();
  S.lastClaims.forEach((c) => (c.citations || []).forEach((cit) => grounded.add(cit.passage_id)));
  _passageNodes.forEach((n) => {
    const isGround = grounded.has(n.id);
    const from = n.mesh.position.clone();
    const to = new THREE.Vector3(0, 1.2, 0);
    const mid = from.clone().add(to).multiplyScalar(0.5);
    const len = from.distanceTo(to);
    const geo = new THREE.CylinderGeometry(0.03, 0.09, 1, 10, 1, true);
    const mat = new THREE.MeshBasicMaterial({ color: isGround ? C_GROUND : C_BEAM, transparent: true, opacity: isGround ? 0.0 : 0.0, side: THREE.DoubleSide, depthWrite: false });
    const beam = new THREE.Mesh(geo, mat);
    beam.position.copy(mid);
    beam.scale.set(1, len, 1);
    beam.lookAt(to);
    beam.rotateX(Math.PI / 2);
    beam.userData = { t: 0, ground: isGround };
    beam.visible = true;
    _group.add(beam);
    _beams.push(beam);
    // brighten grounded passage nodes
    try { n.mesh.material.emissiveIntensity = isGround ? 0.95 : 0.35; } catch (_) {}
  });
}

// =========================================================================================
// per-frame animation
// =========================================================================================
function _onFrame() {
  if (_core && _core.core) {
    _core.rotation.y += 0.004;
    const s = 1 + 0.05 * Math.sin(performance.now() * 0.003);
    _core.core.scale.setScalar(s);
  }
  _passageNodes.forEach((n, i) => { n.mesh.rotation.y += 0.008 + i * 0.0008; });
  _beams.forEach((beam) => {
    beam.userData.t = (beam.userData.t || 0) + 0.03;
    const t = beam.userData.t;
    const peak = beam.userData.ground ? 0.9 : 0.35;
    beam.material.opacity = Math.max(0, peak * (1 - Math.abs(Math.sin(t))));
  });
}

// =========================================================================================
// DOM overlay (HUD)
// =========================================================================================
let _el = {};
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,470px)", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.5";
  sub.innerHTML = 'Deterministic <b>hybrid retrieval</b> (dense + BM25 → RRF → ' +
    'ColBERT-style rerank) → <b>per-claim citations</b> → RAGAS faithfulness → ' +
    'Λ-gate → a <span style="color:#2fd07a">SIGNED receipt</span> proving which ' +
    'sources grounded which claims. Λ is <b>advisory</b> (Conjecture 1), never "green".';
  _overlay.appendChild(sub);

  _badge = ctx.live.createBadge();
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#6fb1ff"; return s; };
  badgeRow.appendChild(tag("corpus")); badgeRow.appendChild(_badge.el);
  _overlay.appendChild(badgeRow);

  // query demo controls
  const ctl = document.createElement("div");
  ctl.style.cssText = "display:flex;flex-direction:column;gap:6px;background:#0a1117;border:1px solid #1d2a36;border-radius:8px;padding:8px";
  const cl = document.createElement("div");
  cl.style.cssText = "font:600 11px ui-sans-serif;color:#e8c074"; cl.textContent = "governed RAG query (grounded answer + receipt)";
  ctl.appendChild(cl);

  _el.query = document.createElement("input");
  _el.query.type = "text"; _el.query.value = "What is RAGAS and how does it measure faithfulness?";
  _el.query.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:6px;font:11px ui-sans-serif";
  ctl.appendChild(_el.query);

  _el.modelSel = document.createElement("select");
  _el.modelSel.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-monospace,monospace";
  [["", "(extractive · honest, no model key)"], ["claude_opus_4_8", "claude_opus_4_8 (abstractive MODELED)"], ["gpt_5_5", "gpt_5_5 (abstractive MODELED)"]].forEach(([v, t]) => {
    const o = document.createElement("option"); o.value = v; o.textContent = t; _el.modelSel.appendChild(o);
  });
  _el.modelSel.value = S.selectedModel;
  _el.modelSel.addEventListener("change", () => { S.selectedModel = _el.modelSel.value; });
  ctl.appendChild(_el.modelSel);

  _el.queryBtn = document.createElement("button");
  _el.queryBtn.textContent = "▶ query (retrieve + ground + Λ-gate + sign + forum)";
  _el.queryBtn.style.cssText = "background:#12202b;color:#eef3f6;border:1px solid #39d3c4;border-radius:7px;padding:7px 10px;cursor:pointer;font:600 11px ui-monospace,monospace";
  _el.queryBtn.addEventListener("click", _fireQuery);
  ctl.appendChild(_el.queryBtn);

  _el.queryState = document.createElement("div");
  _el.queryState.style.cssText = "font:10.5px ui-monospace,monospace;color:#9fb1bf";
  _el.queryState.textContent = "state: idle";
  ctl.appendChild(_el.queryState);
  _overlay.appendChild(ctl);

  // grounded answer + per-claim citation panel
  _el.answer = document.createElement("div");
  _el.answer.style.cssText = "font:11px ui-sans-serif;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;line-height:1.5";
  _el.answer.textContent = "— run a query to see the grounded answer + per-claim citations —";
  _overlay.appendChild(_el.answer);

  // signed receipt panel
  const det = document.createElement("details");
  det.open = true;
  const sum = document.createElement("summary");
  sum.style.cssText = "cursor:pointer;color:#39d3c4;font:11px ui-monospace,monospace";
  sum.textContent = "signed RAG receipt (szl.rag_query.receipt/v1)";
  _el.receipt = document.createElement("div");
  _el.receipt.style.cssText = "white-space:pre-wrap;font:10px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;max-height:230px;overflow:auto;margin-top:6px";
  _el.receipt.textContent = "— run a query to see the live signed receipt —";
  det.appendChild(sum); det.appendChild(_el.receipt);
  _overlay.appendChild(det);

  // honesty legend
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);

  // sources (text only — NOT fetch-shaped, doctrine 0-CDN safe)
  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Leaders studied + composed: DPR (arXiv:2004.04906) · BM25/RRF hybrid · ColBERT " +
    "(arXiv:2004.12832) · Cohere Rerank cross-encoder · GraphRAG (Microsoft) · Anthropic contextual " +
    "retrieval · citation-grounded generation ALCE (arXiv:2305.14627) · RAGAS reference-free eval " +
    "(arXiv:2309.15217). SZL's governed version adds the layer none ship: a Λ-gated (Conjecture 1, " +
    "never green) SIGNED per-claim receipt proving which sources grounded which claims. Retrieval + " +
    "grounding + scoring + signing are REAL + deterministic; abstractive rewrite is MODELED (honest " +
    "extractive answer with no model key). NOT in the locked-8; trust < 100%.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

function _paintOverlay() {
  if (_el.queryState) _el.queryState.textContent = "state: " + S.queryState +
    (S.lastRagas ? "  ·  faithfulness=" + S.lastRagas.faithfulness + " ctx-precision=" + S.lastRagas.context_precision : "");
  if (_el.answer) {
    if (!S.lastAnswer) {
      _el.answer.textContent = S.corpus.length ? "— run a query to see the grounded answer + per-claim citations —" :
        (S.state === "live" ? "corpus empty" : "awaiting live corpus (" + S.state + ")");
    } else {
      _el.answer.innerHTML = "";
      const a = document.createElement("div");
      a.style.cssText = "color:#eef3f6;margin-bottom:6px";
      a.innerHTML = "<b style='color:#e8c074'>grounded answer:</b> " + _esc(S.lastAnswer);
      _el.answer.appendChild(a);
      S.lastClaims.forEach((c) => {
        const row = document.createElement("div");
        row.style.cssText = "border-top:1px solid #12202b;padding-top:5px;margin-top:5px;font-size:10.5px";
        const cited = (c.citations || []).map((x) => x.passage_id + "(" + x.support + ")").join(", ") || "none";
        const col = c.grounded ? "#2fd07a" : "#ff9b6b";
        row.innerHTML = "<span style='color:" + col + "'>" + (c.grounded ? "✓ grounded" : "✗ ungrounded") +
          "</span> — " + _esc(c.claim) + "<br><span style='color:#5b6c78'>grounded by: " + _esc(cited) + "</span>";
        _el.answer.appendChild(row);
      });
    }
  }
}

function _paintReceipt() {
  if (!_el.receipt) return;
  if (!S.lastReceipt) { _el.receipt.textContent = "— run a query to see the live signed receipt —"; return; }
  const r = S.lastReceipt;
  const sig = r.signature || {};
  const gr = r.grounding || {};
  const ra = r.ragas || {};
  const lines = [
    "schema        : " + (r.schema || "?"),
    "query         : " + (r.query || ""),
    "corpus        : " + (r.corpus && r.corpus.origin) + " · size=" + (r.corpus && r.corpus.size),
    "corpus sha256 : " + (r.corpus && r.corpus.sha256),
    "retrieval     : " + (r.retrieval && r.retrieval.method),
    "retrieved ids : " + (r.retrieval && (r.retrieval.retrieved_ids || []).join(", ")),
    "── per-claim citation map (the differentiator) ──",
  ];
  (gr.per_claim_citations || []).forEach((c, i) => {
    lines.push("  [" + (i + 1) + "] " + (c.grounded ? "grounded" : "UNGROUNDED") +
      " by [" + (c.grounded_by || []).join(",") + "]  support=" + c.best_support);
    lines.push("      \"" + (c.claim || "").slice(0, 70) + "\"");
  });
  lines.push("grounded/total: " + gr.grounded_claim_count + "/" + gr.total_claim_count);
  lines.push("RAGAS         : faithfulness=" + ra.faithfulness + " ctx-precision=" + ra.context_precision +
    " avg-support=" + ra.avg_grounding_support);
  lines.push("Λ (lambda)    : " + r.lambda + "  (floor " + r.lambda_floor + ")");
  lines.push("gate_pass     : " + r.gate_pass + "   [Λ ADVISORY · Conjecture 1 · never 'green']");
  lines.push("rag_state     : " + r.rag_state + "   honesty_label=" + r.honesty_label);
  lines.push("model_id      : " + (r.model_id || "(none · extractive)") + "  api_key_wired=" + r.api_key_wired);
  lines.push("signature     : " + sig.alg + " / " + sig.envelope + " · signed=" + sig.signed);
  lines.push("  value       : " + (sig.value || "?"));
  lines.push("  honesty     : " + (sig.honesty || ""));
  lines.push("conjecture    : " + r.conjecture_note);
  _el.receipt.textContent = lines.join("\n");
}

function _esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// =========================================================================================
// unmount
// =========================================================================================
function unmount() {
  try { if (_poll) _poll.stop(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach((m) => { if (m.map && m.map.dispose) m.map.dispose(); if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _poll = null; _overlay = _group = _core = _billboard = null;
  _passageNodes = []; _beams = []; _badge = null; _el = {};
  S.corpus = []; S.lastReceipt = null; S.lastAnswer = null; S.lastClaims = []; S.lastRagas = null;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_CORPUS, EP_QUERY], mount, unmount };
