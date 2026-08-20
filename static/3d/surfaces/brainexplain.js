// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainexplain.js — BRAIN EXPLAIN. A transparent, human-readable account of
// WHY the brain retrieved what it did for a query. It reads the MODELED explanation
// trace from the backend (GET /brain/explain?q=) — which query terms matched which
// seed nodes, why each supporting node ranked where it did (personalized PageRank vs
// baseline salience), which communities were traversed, and each supporting node's OWN
// honesty label VERBATIM — and renders the supporting nodes as a lattice of rank bars.
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * the trace is MODELED — a derived account over a REAL retrieval subgraph; it
//     DESCRIBES the retrieval and never invents a rationale.
//   * each supporting node's basis is the honest reason it was included
//     (direct-term-match / substring-match / vector-similarity / graph-traversal /
//     unattributed) — an unattributed node is shown as such, not rationalized.
//   * verdict EXPLAINABLE / PARTIALLY-EXPLAINABLE / OPAQUE; an OPAQUE retrieval is
//     never shown as EXPLAINABLE. With no query-matched seed it is honestly OPAQUE.
//   * Λ = Conjecture 1 → GREY, never green. locked-proven = exactly 8.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brainexplain";
const TITLE = "Brain Explain — why the brain retrieved this";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_INFO    = "/api/a11oy/v1/brain/explain/info";
const EP_EXPLAIN = "/api/a11oy/v1/brain/explain";
const EP_RECEIPT = "/api/a11oy/v1/brain/explain/receipt";

// palette (doctrine v11) — NO purple
const C_OK     = 0x3af4c8;  // proof-teal — a direct query-term match
const C_MID    = 0x5b8dee;  // lattice-blue — graph traversal / neutral
const C_WARN   = 0x8a6bff;  // violet-blue — a MODELED similarity proxy (attention)
const C_CONJ   = 0x5a6570;  // GREY — unattributed / conjecture floor — never green
const C_BASE   = 0x1b3a44;  // dim base grid

const MAX_BARS = 24;
const DEFAULT_Q = "brain graph";

// basis → bar colour (the honest reason a node is in the grounding set)
const BASIS_DIRECT      = "direct-term-match";
const BASIS_SUBSTRING   = "substring-match";
const BASIS_VECTOR      = "vector-similarity";
const BASIS_TRAVERSAL   = "graph-traversal";
const BASIS_UNATTRIB    = "unattributed";

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;

// scene objects
let _boxGeo = null;
let _meshes = [];   // per supporting-node rank bar meshes

const S = {
  label: "MODELED", state: "idle",
  query: DEFAULT_Q,
  verdict: "OPAQUE", verdictReason: null,
  seedMatches: [],           // [{id, matched_terms, node_label, ...}]
  supporting: [],            // supporting_nodes (each with basis/ppr/why/node_label)
  communities: [],           // communities_traversed
  summary: null,             // counts rollup
  receipt: null,             // unsigned SHA-256 digest (POST only)
  note: null,
};

// -------------------------------------------------------------------------- //
// mount
// -------------------------------------------------------------------------- //
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  _boxGeo = new _THREE.BoxGeometry(1, 1, 1);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  if (_show) {
    _show.attachSceneLabels({
      objects: () => _meshes,
      text: (o) => (o.userData && o.userData.node && o.userData.node.id) || "",
      weight: (o) => (o.userData && o.userData.node && o.userData.node.ppr) || 0,
      topN: 8, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  _fetchExplain(S.query);

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j, fallback) {
  const lbl = (j && j.label != null) ? j.label : (fallback || "MODELED");
  return String(lbl).toUpperCase();
}

function _setBadge(state) {
  S.state = state;
  if (_badge && _badge.set) { try { _badge.set(state); } catch (_) {} }
}

// -------------------------------------------------------------------------- //
// data — GET the explanation trace for a query. PURE READ; mints nothing.
// -------------------------------------------------------------------------- //
function _fetchExplain(q) {
  S.query = q;
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  const url = EP_EXPLAIN + "?q=" + encodeURIComponent(q || "") + "&k=12";
  fetch(url, { headers: { accept: "application/json" },
               signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => { _inFlight = null; _onExplain(j); })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      _inFlight = null;
      S.state = "error"; _setBadge("error"); _paintOverlay();
    });
}

// POST the query for a receipt (receipt-on-write) — same trace + unsigned SHA-256.
function _mintReceipt() {
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const body = JSON.stringify({ q: S.query, k: 12 });
  fetch(EP_RECEIPT, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body,
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => _onReceipt(j))
    .catch(() => { S.state = "error"; _setBadge("error"); _paintOverlay(); });
}

function _ingest(j) {
  S.label = _readLabel(j, "MODELED");
  S.query = (j && j.query != null) ? String(j.query) : S.query;
  S.verdict = String((j && j.verdict) || "OPAQUE").toUpperCase();
  S.verdictReason = (j && j.verdict_reason) || null;
  S.seedMatches = (j && j.seed_matches) || [];
  S.supporting = (j && j.supporting_nodes) || [];
  S.communities = (j && j.communities_traversed) || [];
  S.summary = (j && j.summary) || null;
  S.note = (j && (j.verdict_reason || j.error)) || null;
  _rebuild();
}

function _onExplain(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  S.receipt = null;
  _ingest(j);
  S.state = "live"; _setBadge("live");
  _paintOverlay();
}

function _onReceipt(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  _ingest(j);
  S.receipt = j.receipt || null;
  S.state = "live"; _setBadge("live");
  _paintOverlay();
}

// -------------------------------------------------------------------------- //
// build — one bar per supporting node, height ∝ its personalized-PageRank rank.
// -------------------------------------------------------------------------- //
function _barColor(basis) {
  if (basis === BASIS_DIRECT || basis === BASIS_SUBSTRING) return C_OK;
  if (basis === BASIS_VECTOR) return C_WARN;       // MODELED proxy → attention hue
  if (basis === BASIS_UNATTRIB) return C_CONJ;     // GREY — honestly unattributed
  return C_MID;                                    // graph-traversal / neutral
}

function _rebuild() {
  if (!_group) return;
  _clearScene();
  const nodes = (S.supporting || []).slice(0, MAX_BARS);
  if (!nodes.length) return;

  // normalise ppr to [0,1] for bar height (descriptive — not a re-rank).
  let maxPpr = 0;
  nodes.forEach((n) => { const p = Number(n.ppr) || 0; if (p > maxPpr) maxPpr = p; });
  const denom = maxPpr > 0 ? maxPpr : 1;

  const n = nodes.length;
  const spread = 12.0;
  nodes.forEach((node, i) => {
    const norm = Math.max(0, Math.min(1, (Number(node.ppr) || 0) / denom));
    const h = 0.4 + 8.5 * norm;
    const color = _barColor(node.basis);
    const mat = new _THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.22,
      metalness: 0.12, roughness: 0.5, transparent: true, opacity: 0.95,
    });
    const mesh = new _THREE.Mesh(_boxGeo, mat);
    mesh.scale.set(0.7, h, 0.7);
    const x = (n === 1) ? 0 : (-spread / 2 + spread * (i / (n - 1)));
    mesh.position.set(x, h / 2 - 3.0, 0);
    mesh.userData = { node, baseGlow: 0.22 };
    _meshes.push(mesh);
    _group.add(mesh);
  });
}

function _clearScene() {
  _meshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _meshes = [];
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + soft breathing glow
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = Math.sin(t * 0.08) * 0.4;
  const pulse = 0.5 + 0.5 * Math.sin(t * 1.5);
  _meshes.forEach((m) => {
    if (!m.material) return;
    const base = m.userData.baseGlow || 0.22;
    m.material.emissiveIntensity = base * (0.8 + 0.3 * pulse);
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper)
// -------------------------------------------------------------------------- //
const _el = {};

function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", startExpanded: true,
    chips: [{ label: "MODELED", text: "trace", name: "src" }],
    legend: ["MODELED", "EXPLAINABLE", "PARTIALLY-EXPLAINABLE", "OPAQUE"],
    description:
      "<b>See WHY the brain retrieved what it did.</b> Type a query and the server reuses the " +
      "SAME honest retrieval the brain already runs, then turns it into a deterministic, " +
      "plain-language account: which query <b>terms matched</b> which seed nodes, why each " +
      "supporting node <b>ranked</b> where it did (personalized PageRank vs its baseline " +
      "salience), which <b>communities</b> the grounding traversed, and each node's OWN honesty " +
      "<b>label</b> read verbatim. Each supporting node is a bar; its <b>basis</b> (direct term " +
      "match / similarity proxy / graph traversal / unattributed) sets its colour. The trace is " +
      "<b>MODELED</b> — it DESCRIBES the retrieval, never inventing a rationale. Verdict: " +
      "EXPLAINABLE / PARTIALLY-EXPLAINABLE / <b>OPAQUE</b> (when retrieval returns too little to " +
      "explain — no rationale is fabricated).",
    citations:
      "Trace is MODELED over the LIVE retrieval from /api/a11oy/v1/brain/explain (pure read — no " +
      "signing on GET) — the same honest ranked retrieval as /brain/ask. A receipt is minted only " +
      "on POST /api/a11oy/v1/brain/explain/receipt (unsigned SHA-256 content digest, " +
      "receipt-on-write). Λ = Conjecture 1 (grey, never proven green); nothing here touches the " +
      "locked-8.",
    plain: { html: _plainHtml },
  });

  // query row: input + explain + receipt buttons
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap";
  const input = document.createElement("input");
  input.type = "text";
  input.value = S.query;
  input.placeholder = "query…";
  input.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:6px 9px;border-radius:8px;" +
    "border:1px solid #1c2836;background:#0a1117;color:#c9d6df;flex:1;min-width:120px";
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") _fetchExplain(input.value); });
  _el.input = input;
  const expBtn = document.createElement("button");
  expBtn.type = "button";
  expBtn.textContent = "explain";
  expBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  expBtn.addEventListener("click", () => _fetchExplain(input.value));
  const rcptBtn = document.createElement("button");
  rcptBtn.type = "button";
  rcptBtn.textContent = "receipt";
  rcptBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #1c2836;background:#0a1117;color:#c9d6df";
  rcptBtn.addEventListener("click", () => _mintReceipt());
  wrap.appendChild(input); wrap.appendChild(expBtn); wrap.appendChild(rcptBtn);
  _show.appendBody(wrap);

  // KPI rows
  _el.verdict   = _show.addField("Verdict");
  _el.seeds     = _show.addField("Seed matches");
  _el.support   = _show.addField("Supporting nodes");
  _el.direct    = _show.addField("Direct-match nodes");
  _el.unattrib  = _show.addField("Unattributed nodes");
  _el.comms     = _show.addField("Communities traversed");
  _el.receipt   = _show.addField("Receipt (SHA-256)");

  // per-node rationale list
  _el.nodes = document.createElement("div");
  _el.nodes.style.cssText =
    "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf;margin-top:2px";
  _show.appendBody(_el.nodes);

  // honest note (verbatim from the endpoint)
  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "MODELED", { text: "trace" });

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const loading = S.state === "loading";
  const sm = S.summary || {};

  set("verdict", loading ? "loading…" : (S.verdict || "OPAQUE"));
  set("seeds", loading ? "…" : _fmt(sm.seed_count != null ? sm.seed_count : (S.seedMatches || []).length));
  set("support", loading ? "…" : _fmt(sm.supporting_count != null ? sm.supporting_count : (S.supporting || []).length));
  set("direct", loading ? "…" : _fmt(sm.direct_match_count));
  set("unattrib", loading ? "…" : _fmt(sm.unattributed_count));
  set("comms", loading ? "…" : _fmt(sm.community_count != null ? sm.community_count : (S.communities || []).length));
  set("receipt", S.receipt ? String(S.receipt.content_sha256 || "").slice(0, 16) + "…"
                           : "— (POST to mint)");

  // per-node rationale (rank · basis · verbatim label)
  if (_el.nodes) {
    _el.nodes.textContent = "";
    (S.supporting || []).slice(0, 12).forEach((n) => {
      const line = document.createElement("div");
      line.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
      const terms = (n.matched_terms && n.matched_terms.length)
        ? " [" + n.matched_terms.join(", ") + "]" : "";
      line.textContent = "#" + _fmt(n.rank) + " · " + (n.id || "?") + " · " +
        (n.basis || "?") + terms + " · " + (n.node_label || "UNLABELLED");
      _el.nodes.appendChild(line);
    });
  }

  if (_el.note) {
    let note = S.note || "";
    if (S.state === "error") note = "explain error — the brain-explain API did not respond.";
    _el.note.textContent = note;
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "This shows the brain's <b>reasoning receipt</b> for a search. When the brain retrieves " +
    "knowledge for a query, this surface explains WHY: which of your search <b>words</b> literally " +
    "matched which pieces of knowledge, why each supporting piece was ranked where it was (a " +
    "measure called personalized PageRank vs how important the node is on its own), which " +
    "<b>clusters</b> of the graph were walked, and what honesty <b>label</b> each piece carries — " +
    "shown exactly as stored, never upgraded. That account is <b>MODELED</b>: it DESCRIBES the real " +
    "retrieval and never makes up a reason. If the search matched too little to explain, it honestly " +
    "says <b>OPAQUE</b> instead of inventing one. Label <b>" + (S.label || "MODELED") + "</b>."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  try { if (_inFlight && _inFlight.abort) _inFlight.abort(); } catch (_) {}
  _inFlight = null;
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearScene(); } catch (_) {}
  try { if (_boxGeo) _boxGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _boxGeo = null;
  _group = _show = _badge = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = "MODELED"; S.state = "idle";
  S.query = DEFAULT_Q;
  S.verdict = "OPAQUE"; S.verdictReason = null;
  S.seedMatches = []; S.supporting = []; S.communities = [];
  S.summary = null; S.note = null; S.receipt = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_INFO, EP_EXPLAIN, EP_RECEIPT], mount, unmount };
