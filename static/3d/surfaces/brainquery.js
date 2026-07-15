// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainquery.js — ASK THE BRAIN (WAVE 1). The companion to brain.js:
// brain.js *renders* the whole estate knowledge graph; this surface makes it
// QUERYABLE. Type a question → the server retrieves a grounding subgraph
// (HippoRAG-style Personalized PageRank over the honest graph, merged with
// GraphRAG community context) and it lights up here in 3D:
//   * node SIZE  = salience (PageRank over the full graph)
//   * node GLOW  = match score (how strongly the query hit that node)
//   * seeds (direct query hits) ring brightest; PPR-reached nodes fill the halo.
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * the grounding subgraph is REAL (retrieved from /brain/ask); it is shown
//     whether or not a sovereign model was reachable.
//   * generated prose is shown ONLY when the endpoint returns one; otherwise the
//     answer pill reads its verbatim UNAVAILABLE — NEVER a fabricated answer.
//   * embeddings tier is shown verbatim (hash-fallback similarity is MODELED,
//     never MEASURED).
//   * query latency is MEASURED only when supplied by the server's monotonic
//     clock; browser animation time is never presented as request latency.
//   * canonical node count is dedupe lineage, not evidence/model admission;
//     training eligibility remains BLOCKED/UNAVAILABLE when the estate is
//     entirely quarantined.
//   * exact-query provenance is fetched by pure GET; this surface never mints
//     or POSTs a receipt.
//   * Λ = Conjecture 1 → GREY node, never green. locked-proven = exactly 8.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brainquery";
const TITLE = "Brain Query — ask the graph";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_ASK   = "/api/a11oy/v1/brain/ask";
const EP_INDEX = "/api/a11oy/v1/brain/index";
const EP_RERANKER = "/api/a11oy/v1/brain/reranker/inventory?limit=1";
const EP_PROVENANCE = "/api/a11oy/v1/brain/provenance";

// palette (doctrine v11) — NO purple
const C_INPUT   = 0x5b8dee;  // lattice-blue — repos + surfaces (input)
const C_TOPIC   = 0x8a6bff;  // violet-blue — topic clusters
const C_FORMULA = 0x8a6bff;  // violet-blue — formulas
const C_LOCKED  = 0x3af4c8;  // proof-teal — locked-proven core
const C_ESTATE  = 0x3af4c8;  // proof-teal — estate root (output)
const C_ENDPT   = 0x5b8dee;  // lattice-blue — live endpoints
const C_FIELD   = 0x3a5a8c;  // lattice-blue (dim) — harvested field leaders
const C_CONJ    = 0x5a6570;  // GREY — conjectures (Λ) — never green
const C_EDGE    = 0x1b3a44;  // dim link

const MAX_NODES = 240;   // grounding subgraphs are small; cap defensively
const MAX_EDGES = 900;

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;
let _provenanceFlight = null, _querySerial = 0;

// scene objects
let _sphereGeo = null;
let _meshes = [];                       // individual node meshes (labelable)
let _edges = null, _edgeGeo = null, _edgeMat = null;
let _pos = {};                          // id -> Vector3

// query DOM
let _input = null, _askBtn = null, _answerEl = null, _resultsEl = null;
let _onKey = null;

const S = {
  label: "MODELED", state: "idle",
  query: "", answer: null, answerLabel: "UNAVAILABLE", answerModel: null,
  nodes: null, links: null, seedScore: null,
  retrieval: null, note: null,
  // index tiers (from /brain/index) — honest capability pills
  vectorBackend: null, embedSource: null, embedTier: null, communityAlgo: null,
  rawNodes: null, rawLinks: null, distinctArtifacts: null, personNodes: null,
  canonicalNodes: null, quarantinedNodes: null, trainingEligible: null,
  rerankerState: "UNAVAILABLE", rerankerNote: null,
  queryLatency: null,
  provenanceVerdict: "UNAVAILABLE", provenanceFraction: null,
  provenanceQuery: null, provenanceState: "UNAVAILABLE",
};

// -------------------------------------------------------------------------- //
// deterministic layout: golden-angle disc; radius grows for LESS-salient nodes
// so the most salient sit at the centre. Stable (hash-seeded), no RNG.
// -------------------------------------------------------------------------- //
function _hash(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h;
}

function _salience(n) { return (n.ppr != null ? n.ppr : (n.salience || 0)); }

function _layout(nodes) {
  _pos = {};
  // most salient first → smallest radius (centre); tie-break by id for stability
  const ranked = nodes.slice().sort((a, b) => (_salience(b) - _salience(a)) || (a.id < b.id ? -1 : 1));
  const N = ranked.length || 1;
  const R = 9.0;
  ranked.forEach((n, i) => {
    const r = R * Math.sqrt((i + 0.5) / N);
    const theta = i * 2.399963229728653; // golden angle
    const jz = ((_hash(n.id) % 200) / 200 - 0.5) * 2.4; // depth jitter
    _pos[n.id] = new _THREE.Vector3(r * Math.cos(theta), r * Math.sin(theta), jz);
  });
}

function _isConj(n) { return (n.conjecture != null) || n.formula_id === "F23"; }

function _nodeColor(n) {
  if (_isConj(n)) return C_CONJ;
  if (n.kind === "formula") return n.locked ? C_LOCKED : C_FORMULA;
  if (n.kind === "estate") return C_ESTATE;
  if (n.kind === "endpoint") return C_ENDPT;
  if (n.kind === "topic") return C_TOPIC;
  if (n.layer === 0) return C_INPUT;
  if (n.layer === -1) return C_FIELD;
  return C_INPUT;
}

// size grows with salience; salience is normalised per-result so the biggest
// retrieved node reads clearly regardless of absolute PageRank magnitude.
let _maxSal = 1e-9;
function _nodeRadius(n) {
  const s = _salience(n) / _maxSal;                 // 0..1
  let r = 0.22 + 0.85 * Math.sqrt(Math.max(0, s));
  if (n.kind === "estate") r = Math.max(r, 0.7);
  return Math.min(r, 1.3);
}

// glow (emissiveIntensity) tracks the query MATCH score (seeds glow brightest);
// non-seed PPR-reached nodes get a dim honest floor.
function _glow(n) {
  const sc = (S.seedScore && S.seedScore[n.id] != null) ? S.seedScore[n.id] : 0;
  return 0.14 + 0.9 * Math.min(1, sc);
}

// -------------------------------------------------------------------------- //
// mount
// -------------------------------------------------------------------------- //
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  // Browser time drives animation only. It is never emitted or labeled as
  // query latency; the latency field accepts the server's monotonic receipt.
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  _sphereGeo = new _THREE.SphereGeometry(1, 12, 10);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  // one-shot index probe → honest capability pills (vector/embedding/community).
  _fetchIndex();
  _fetchRerankerInventory();

  // top-N + hover/tap labels bound to the node meshes.
  if (_show) {
    _show.attachSceneLabels({
      objects: () => _meshes,
      text: (o) => (o.userData && o.userData.node && (o.userData.node.title || o.userData.node.id)) || "",
      weight: (o) => (o.userData && o.userData.node && _salience(o.userData.node)) || 0,
      topN: 10, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  // seed a friendly default query so the surface isn't empty on first open.
  _ask("what proves the estate thesis");

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
// data
// -------------------------------------------------------------------------- //
function _fetchIndex() {
  fetch(EP_INDEX, { headers: { accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      S.vectorBackend = j.vector_backend || null;
      S.embedSource   = j.embed_source || null;
      S.embedTier     = _readLabel(j, "MODELED"); // whole payload is MODELED
      if (j.embed_tier) S.embedTier = String(j.embed_tier).toUpperCase();
      S.communityAlgo = j.community_algo || null;
      const rawValue = j.raw_node_count != null ? j.raw_node_count : j.node_count;
      S.rawNodes = rawValue != null && Number.isFinite(Number(rawValue)) ? Number(rawValue) : null;
      S.rawLinks = j.link_count != null && Number.isFinite(Number(j.link_count))
        ? Number(j.link_count) : null;
      S.distinctArtifacts = j.distinct_artifacts != null && Number.isFinite(Number(j.distinct_artifacts))
        ? Number(j.distinct_artifacts) : null;
      S.personNodes = j.person_node_count != null && Number.isFinite(Number(j.person_node_count))
        ? Number(j.person_node_count) : null;
      _paintOverlay();
    })
    .catch(() => { /* index pills stay "—"; the ask path still works */ });
}

function _fetchRerankerInventory() {
  fetch(EP_RERANKER, { headers: { accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      const inv = (j && j.inventory) || {};
      const raw = inv.raw_node_count != null ? Number(inv.raw_node_count) : NaN;
      const canonical = inv.canonical_node_count != null ? Number(inv.canonical_node_count) : NaN;
      const quarantined = inv.quarantined_node_count != null ? Number(inv.quarantined_node_count) : NaN;
      if (S.rawNodes == null && Number.isFinite(raw)) S.rawNodes = raw;
      S.canonicalNodes = Number.isFinite(canonical) ? canonical : null;
      S.quarantinedNodes = Number.isFinite(quarantined) ? quarantined : null;
      // Canonical means dedupe lineage only. It is never promoted into model
      // admission. When every raw node is quarantined, eligibility is exactly 0.
      S.trainingEligible = Number.isFinite(raw) && raw > 0 && quarantined === raw ? 0 : null;
      S.rerankerState = S.trainingEligible === 0 ? "BLOCKED" : "UNAVAILABLE";
      S.rerankerNote = S.trainingEligible === 0
        ? "all raw nodes quarantined; canonical count is dedupe lineage, not admission"
        : "inventory does not establish training eligibility";
      _paintOverlay();
    })
    .catch(() => {
      S.canonicalNodes = S.quarantinedNodes = S.trainingEligible = null;
      S.rerankerState = "UNAVAILABLE";
      S.rerankerNote = "reranker inventory endpoint unavailable";
      _paintOverlay();
    });
}

function _fetchProvenance(q, serial) {
  if (_provenanceFlight && _provenanceFlight.abort) {
    try { _provenanceFlight.abort(); } catch (_) {}
  }
  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  _provenanceFlight = ctrl;
  S.provenanceState = "loading";
  S.provenanceQuery = q;
  S.provenanceVerdict = "UNAVAILABLE";
  S.provenanceFraction = null;
  _paintOverlay();
  const url = EP_PROVENANCE + "?q=" + encodeURIComponent(q) + "&k=12";
  // Pure GET: this surface never calls the provenance receipt POST.
  fetch(url, { method: "GET", headers: { accept: "application/json" },
    signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      if (serial !== _querySerial || String(j.query || "") !== q) return;
      const coverage = (j && j.coverage) || {};
      const fraction = coverage.fraction_traceable_to_source != null
        ? Number(coverage.fraction_traceable_to_source) : NaN;
      S.provenanceVerdict = String(j.verdict || "UNAVAILABLE").toUpperCase();
      S.provenanceFraction = Number.isFinite(fraction) ? fraction : null;
      S.provenanceState = _readLabel(j, "UNAVAILABLE");
      S.provenanceQuery = String(j.query || "");
      _paintOverlay();
    })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      if (serial !== _querySerial) return;
      S.provenanceVerdict = "UNAVAILABLE";
      S.provenanceFraction = null;
      S.provenanceState = "UNAVAILABLE";
      _paintOverlay();
    });
}

function _ask(q) {
  q = (q || "").trim();
  if (!q) return;
  S.query = q;
  const serial = ++_querySerial;
  S.queryLatency = null;
  S.answer = null;
  S.answerLabel = "UNAVAILABLE";
  S.answerModel = null;
  S.nodes = S.links = S.seedScore = null;
  S.retrieval = S.note = null;
  if (_group) _clearScene();
  if (_provenanceFlight && _provenanceFlight.abort) {
    try { _provenanceFlight.abort(); } catch (_) {}
  }
  _provenanceFlight = null;
  S.provenanceState = "loading";
  S.provenanceQuery = q;
  S.provenanceVerdict = "UNAVAILABLE";
  S.provenanceFraction = null;
  if (_input && _input.value !== q) _input.value = q;
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  const url = EP_ASK + "?q=" + encodeURIComponent(q);
  fetch(url, { headers: { accept: "application/json" }, signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      if (serial !== _querySerial) return;
      _inFlight = null;
      _onAsk(j);
      _fetchProvenance(q, serial);
    })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      if (serial !== _querySerial) return;
      _inFlight = null;
      S.state = "error";
      S.label = "UNAVAILABLE";
      S.provenanceState = "UNAVAILABLE";
      _setBadge("error");
      _paintOverlay();
    });
}

function _onAsk(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  S.label = _readLabel(j, "MODELED");
  const g = j.grounding_subgraph || {};
  S.nodes = Array.isArray(g.nodes) ? g.nodes.slice(0, MAX_NODES) : [];
  const keep = new Set(S.nodes.map((n) => n.id));
  S.links = (Array.isArray(g.links) ? g.links : [])
    .filter((l) => keep.has(l.source) && keep.has(l.target)).slice(0, MAX_EDGES);

  // seed match scores drive node glow.
  S.seedScore = {};
  (j.seeds || []).forEach((s) => { S.seedScore[s.id] = s.score || 0; });

  // honest answer handling — NEVER fabricate. Verbatim label from the endpoint.
  S.answer = (j.answer != null && String(j.answer).trim()) ? String(j.answer) : null;
  S.answerLabel = String(j.answer_label || "UNAVAILABLE").toUpperCase();
  S.answerModel = j.answer_model || null;
  S.retrieval = j.retrieval || null;
  S.note = j.note || null;
  const latency = j.query_latency || null;
  S.queryLatency = latency && String(latency.label || "").toUpperCase() === "MEASURED"
    && Number.isFinite(Number(latency.value_ms)) ? latency : null;

  S.state = "live";
  _setBadge("live");
  _rebuild();
  _paintOverlay();
}

// -------------------------------------------------------------------------- //
// build
// -------------------------------------------------------------------------- //
function _rebuild() {
  if (!_group || !S.nodes) return;
  _clearScene();
  if (!S.nodes.length) return;
  _maxSal = Math.max(1e-9, ...S.nodes.map(_salience));
  _layout(S.nodes);
  S.nodes.forEach(_addMesh);
  _buildEdges();
}

function _addMesh(n) {
  const col = _nodeColor(n);
  const conj = _isConj(n);
  const mat = new _THREE.MeshStandardMaterial({
    color: col,
    emissive: conj ? 0x000000 : col,
    emissiveIntensity: conj ? 0.0 : _glow(n),
    metalness: 0.1, roughness: conj ? 0.95 : 0.45,
    transparent: true, opacity: conj ? 0.62 : 0.96,
  });
  const mesh = new _THREE.Mesh(_sphereGeo, mat);
  mesh.scale.setScalar(_nodeRadius(n));
  mesh.position.copy(_pos[n.id]);
  mesh.userData = { node: n, baseGlow: mat.emissiveIntensity, isConj: conj };
  _meshes.push(mesh);
  _group.add(mesh);
}

function _buildEdges() {
  const pts = [];
  for (let i = 0; i < S.links.length; i++) {
    const l = S.links[i];
    const a = _pos[l.source], b = _pos[l.target];
    if (!a || !b) continue;
    pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
  }
  if (!pts.length) return;
  _edgeGeo = new _THREE.BufferGeometry();
  _edgeGeo.setAttribute("position", new _THREE.Float32BufferAttribute(pts, 3));
  _edgeMat = new _THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.3 });
  _edges = new _THREE.LineSegments(_edgeGeo, _edgeMat);
  _group.add(_edges);
}

function _clearScene() {
  _meshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _meshes = [];
  if (_edges) _group.remove(_edges);
  if (_edgeGeo) _edgeGeo.dispose();
  if (_edgeMat) _edgeMat.dispose();
  _edges = _edgeGeo = _edgeMat = null;
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + seed "breathing" glow (conjectures stay flat)
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = Math.sin(t * 0.09) * 0.45 + t * 0.02;
  const pulse = 0.5 + 0.5 * Math.sin(t * 1.7);
  _meshes.forEach((m) => {
    if (!m.material || m.userData.isConj) return;
    const base = m.userData.baseGlow || 0.14;
    m.material.emissiveIntensity = base * (0.75 + 0.35 * pulse);
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper) + the query box
// -------------------------------------------------------------------------- //
const _el = {};

function _buildOverlay(ctx) {
  const compactViewport = typeof window !== "undefined" && (
    (window.matchMedia && window.matchMedia("(max-width: 640px)").matches) ||
    Number(window.innerWidth || 0) <= 640
  );
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", startExpanded: !compactViewport,
    chips: [{ label: "MODELED", text: "retrieval", name: "src" }],
    legend: ["MEASURED", "MODELED", "UNAVAILABLE"],
    description:
      "<b>Ask the estate's brain.</b> Your question is answered by RETRIEVAL over the real " +
      "knowledge graph: the server seeds Personalized PageRank (HippoRAG-style) from the nodes " +
      "your query hits, walks the graph to a grounding subgraph, and merges in the relevant " +
      "community context (GraphRAG-style). That subgraph lights up here — node <b>size = salience</b> " +
      "(PageRank), node <b>glow = match</b> to your query. Generated prose appears only if a " +
      "sovereign model is reachable; otherwise the answer is honestly <b>UNAVAILABLE</b> — the " +
      "subgraph is real regardless. Nothing is fabricated.",
    citations:
      "Retrieval is LIVE from /api/a11oy/v1/brain/ask (pure read — no signing on GET) over the " +
      "same honest graph as /brain/graph. Vectors/embeddings/community tiers shown verbatim below. " +
      "Λ = Conjecture 1 (grey, never proven green).",
    plain: { html: _plainHtml },
  });

  // --- the query box (custom DOM into the collapsible body) ---------------- //
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;flex-direction:column;gap:7px";
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:6px";
  _input = document.createElement("input");
  _input.type = "text";
  _input.placeholder = "ask the brain… (e.g. what proves the thesis?)";
  _input.setAttribute("aria-label", "Ask the brain");
  _input.style.cssText =
    "flex:1 1 auto;min-width:0;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;" +
    "padding:7px 9px;border-radius:8px;border:1px solid #1c2836;background:#0a1117;" +
    "color:#e7eef6;outline:none";
  _askBtn = document.createElement("button");
  _askBtn.type = "button";
  _askBtn.textContent = "ask";
  _askBtn.style.cssText =
    "flex:0 0 auto;font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  _onKey = (e) => { if (e.key === "Enter") { e.preventDefault(); _ask(_input.value); } };
  _input.addEventListener("keydown", _onKey);
  _askBtn.addEventListener("click", () => _ask(_input.value));
  row.appendChild(_input); row.appendChild(_askBtn);
  wrap.appendChild(row);

  // honest answer box (prose OR verbatim UNAVAILABLE pill)
  _answerEl = document.createElement("div");
  _answerEl.style.cssText =
    "font-size:11px;color:#c9d6df;line-height:1.5;border:1px dashed #26333f;border-radius:8px;" +
    "padding:8px 10px;min-height:18px";
  wrap.appendChild(_answerEl);
  _show.appendBody(wrap);

  // KPI rows
  _el.answerLbl = _show.addField("Generated answer");
  _el.rawNodes  = _show.addField("Raw graph nodes");
  _el.distinct  = _show.addField("Distinct artifacts");
  _el.people    = _show.addField("Person nodes");
  _el.canonical = _show.addField("Canonical dedupe lineage");
  _el.grounded  = _show.addField("Retrieved for this query");
  _el.edges     = _show.addField("Grounding edges");
  _el.latency   = _show.addField("Server query latency");
  _el.eligibility = _show.addField("Training eligibility");
  _el.provenance = _show.addField("Typed-query provenance");
  _el.vectors   = _show.addField("Vector backend");
  _el.embed     = _show.addField("Embeddings");
  _el.community = _show.addField("Communities via");

  // top retrieved nodes (cited ids) list
  _resultsEl = document.createElement("div");
  _resultsEl.style.cssText = "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf";
  _show.appendBody(_resultsEl);

  // honest note (verbatim from the endpoint)
  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _safeSourceHref(n) {
  const candidates = [n && n.url, n && n.source];
  for (let i = 0; i < candidates.length; i++) {
    const raw = typeof candidates[i] === "string" ? candidates[i].trim() : "";
    if (!raw) continue;
    // One initial slash denotes a same-origin path. Protocol-relative URLs are
    // external and deliberately rejected here.
    if (/^\/(?![\/\\])/.test(raw)) {
      try {
        const local = new URL(raw, window.location.origin);
        if (local.origin === window.location.origin &&
            (local.protocol === "http:" || local.protocol === "https:")) return local.href;
      } catch (_) { /* malformed same-origin path remains plain text */ }
    }
    try {
      const parsed = new URL(raw);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") return parsed.href;
    } catch (_) { /* malformed/non-URL source labels remain plain text */ }
  }
  return null;
}

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "MODELED", { text: "retrieval" });

  // honest answer: prose if present, else the verbatim UNAVAILABLE label.
  if (_answerEl) {
    if (S.state === "loading") {
      _answerEl.textContent = "retrieving grounding subgraph…";
      _answerEl.style.color = "#9fb1bf";
    } else if (S.state === "error") {
      _answerEl.textContent = "retrieval error — the brain API did not respond.";
      _answerEl.style.color = "#d78a8a";
    } else if (S.answer) {
      _answerEl.textContent = S.answer;
      _answerEl.style.color = "#c9d6df";
    } else {
      _answerEl.textContent = "";
      const unavailable = document.createElement("b");
      unavailable.style.color = "#e7eef6";
      unavailable.textContent = S.answerLabel || "UNAVAILABLE";
      _answerEl.appendChild(unavailable);
      _answerEl.appendChild(document.createTextNode(
        " — no sovereign model was reachable, so no answer text is generated. " +
        "The grounding subgraph shown is real; a fabricated answer is never produced."
      ));
      _answerEl.style.color = "#9fb1bf";
    }
  }

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const gN = S.nodes ? S.nodes.length : null;
  const gE = S.links ? S.links.length : null;
  set("rawNodes", S.rawNodes == null ? "UNAVAILABLE" :
    (_fmt(S.rawNodes) + (S.rawLinks == null ? "" : " nodes / " + _fmt(S.rawLinks) + " links")));
  set("distinct", S.distinctArtifacts == null ? "UNAVAILABLE" : _fmt(S.distinctArtifacts));
  set("people", S.personNodes == null ? "UNAVAILABLE" : _fmt(S.personNodes));
  set("canonical", S.canonicalNodes == null ? "UNAVAILABLE" :
    (_fmt(S.canonicalNodes) + " (dedupe only; not admission)"));
  set("latency", S.state === "loading" ? "loading..." : (S.queryLatency
    ? ("MEASURED · " + Number(S.queryLatency.value_ms).toLocaleString("en-US") +
       " ms · server monotonic") : "UNAVAILABLE"));
  set("eligibility", S.trainingEligible === 0
    ? ("BLOCKED / UNAVAILABLE · 0 training-eligible · all " + _fmt(S.quarantinedNodes) + " raw nodes quarantined")
    : (S.rerankerState + " · training eligibility not established"));
  const provenancePct = S.provenanceFraction == null ? null
    : Math.round(Math.max(0, Math.min(1, S.provenanceFraction)) * 1000) / 10;
  set("provenance", S.provenanceState === "loading" ? "loading exact query..."
    : (S.provenanceVerdict + (provenancePct == null ? "" : " · " + provenancePct + "% traceable") +
       " · read-only GET"));
  if (_el.provenance) {
    _el.provenance.title = S.provenanceQuery
      ? ('Exact query: "' + S.provenanceQuery + '". GET mints nothing.')
      : "Exact-query provenance is unavailable.";
  }
  set("answerLbl", S.answer ? (S.answerLabel + (S.answerModel ? " · " + S.answerModel : ""))
                            : (S.answerLabel || "UNAVAILABLE"));
  set("grounded", S.state === "loading" ? "loading…" : _fmt(gN));
  set("edges", S.state === "loading" ? "loading…" : _fmt(gE));
  set("vectors", S.vectorBackend || "—");
  set("embed", S.embedSource ? (S.embedSource + " [" + (S.embedTier || "MODELED") + "]") : "—");
  set("community", S.communityAlgo || "—");
  if (_el.note) _el.note.textContent = S.note || "";

  // cited-node list (top grounding nodes by salience)
  if (_resultsEl) {
    _resultsEl.textContent = "";
    const top = (S.nodes || []).slice()
      .sort((a, b) => (_salience(b) - _salience(a)) || (a.id < b.id ? -1 : 1))
      .slice(0, 8);
    top.forEach((n) => {
      const line = document.createElement("div");
      line.style.cssText = "display:flex;align-items:baseline;gap:5px;min-width:0;overflow:hidden";
      const safeHit = (S.seedScore && S.seedScore[n.id] != null) ? " hit" : "";
      const id = document.createElement("code");
      id.style.cssText = "flex:0 0 auto;color:#6f8ca4;font-size:9px";
      id.textContent = String(n.id || "UNAVAILABLE");
      const href = _safeSourceHref(n);
      const title = document.createElement(href ? "a" : "span");
      title.style.cssText = "min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#b7c7d3";
      title.textContent = String(n.title || n.id || "UNAVAILABLE");
      if (href) {
        title.href = href;
        title.target = "_blank";
        title.rel = "noopener noreferrer";
        title.style.textDecoration = "underline";
        title.style.textDecorationColor = "#38556c";
      }
      const meta = document.createElement("span");
      meta.style.cssText = "flex:0 0 auto;color:#738493";
      meta.textContent = "[" + (n.kind || "?") + "]" + safeHit;
      line.appendChild(id);
      line.appendChild(title);
      line.appendChild(meta);
      line.title = String(n.id || "");
      _resultsEl.appendChild(line);
    });
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "Type a question and our estate's <b>brain</b> answers by looking things up in its own " +
    "knowledge graph — the same real network of repos, formulas, papers and people you can see " +
    "in the Brain surface. It finds the nodes your question touches, follows the connections " +
    "outward to gather the most relevant ones, and lights them up: <b>bigger = more important</b> " +
    "in the graph, <b>brighter = closer match</b> to what you asked. If we have a private AI model " +
    "running, it writes a short answer that only cites those nodes; if not, it honestly says " +
    "<b>UNAVAILABLE</b> instead of making something up — but you still get the real, grounded " +
    "subgraph. Label <b>" + (S.label || "MODELED") + "</b>."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  try { if (_inFlight && _inFlight.abort) _inFlight.abort(); } catch (_) {}
  try { if (_provenanceFlight && _provenanceFlight.abort) _provenanceFlight.abort(); } catch (_) {}
  _inFlight = _provenanceFlight = null;
  _querySerial += 1;
  try { if (_input && _onKey) _input.removeEventListener("keydown", _onKey); } catch (_) {}
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearScene(); } catch (_) {}
  try { if (_sphereGeo) _sphereGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _sphereGeo = null;
  _group = _show = _badge = null;
  _input = _askBtn = _answerEl = _resultsEl = _onKey = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _pos = {}; _frameReg = false; _maxSal = 1e-9;
  _stage = _THREE = _ctx = null;
  S.label = "MODELED"; S.state = "idle";
  S.query = ""; S.answer = null; S.answerLabel = "UNAVAILABLE"; S.answerModel = null;
  S.nodes = S.links = S.seedScore = null;
  S.retrieval = S.note = null;
  S.vectorBackend = S.embedSource = S.embedTier = S.communityAlgo = null;
  S.rawNodes = S.rawLinks = S.distinctArtifacts = S.personNodes = null;
  S.canonicalNodes = S.quarantinedNodes = S.trainingEligible = null;
  S.rerankerState = "UNAVAILABLE"; S.rerankerNote = null;
  S.queryLatency = null;
  S.provenanceVerdict = S.provenanceState = "UNAVAILABLE";
  S.provenanceFraction = S.provenanceQuery = null;
}

export default {
  id: ID, title: TITLE,
  endpoints: [EP_ASK, EP_INDEX, EP_RERANKER, EP_PROVENANCE],
  mount, unmount,
};
