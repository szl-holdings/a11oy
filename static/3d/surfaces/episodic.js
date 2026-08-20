// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/episodic.js — GOVERNED EPISODIC-MEMORY / TEMPORAL KNOWLEDGE-GRAPH organ for
// the holographic frontier ring, clean-room-inspired by (NOT a reproduction of)
// MemMachine's episodic/graph memory idea (github.com/MemMachine/MemMachine, Apache-2.0).
//
// Renders a small graph of "episodes" (event/fact nodes) positioned along a TIME axis,
// sized by MODELED salience, linked by temporal-succession (chronological chain) and
// semantic-relatedness (cosine of a MODELED embedding) edges. On each poll, the top-k
// RECALL result for the query episode lights up (recency*salience*relatedness score).
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is; it is
// never upgraded. Every episode also carries a real content hash + an explicitly
// labeled HONEST-STUB receipt (never presented as a real Sigstore/DSSE signature).
//
// Surface export shape (mirrors interpretability.js / worldmodel.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   graph.episodes[]      — {id, text, t, salience, content_hash, honesty_receipt}
//   graph.edges[]         — {src, dst, type: temporal-succession|semantic-relatedness, weight}
//   recall.top_k[]        — {id, score, components:{recency,salience,relatedness}, rank}
//   scoring_formula       — exact deterministic recall formula (shown in overlay)
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   MemMachine — episodic/graph memory (Apache-2.0):
//     https://github.com/MemMachine/MemMachine
//   Tulving (1972) "Episodic and Semantic Memory" — classic episodic/semantic distinction:
//     https://alicekim.ca/EpisodicSemantic.pdf
//   Zep / Graphiti — temporal knowledge-graph memory (related open approach):
//     https://github.com/getzep/graphiti
//
// HONESTY LABELS: MODELED (deterministic simulation of the episodic-graph PATTERN;
//   PUBLIC/synthetic episode content only; embeddings are a MODELED construction, not a
//   real trained embedding model). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (episode nodes / temporal edges), violet-blue 0x8a6bff
//   (recalled top-k flash + semantic-relatedness edges — data-viz only), proof-teal
//   0x3af4c8 (query marker / receipt accent), greys for degraded/no-data. Purple BANNED
//   as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

import { createShowcase } from "./_showcase.js";

const ID    = "episodic";
const TITLE = "Episodic Memory · Temporal Knowledge-Graph (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the episodic-memory organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/episodic/recall?seed=42&k=3&query=what%20did%20I%20ask%20about%20earlier%3F&n_episodes=12";

// data-viz hues — purple BANNED
const C_NODE   = 0x5b8dee;  // lattice-blue (episode node / temporal-succession edge)
const C_TOP    = 0x8a6bff;  // violet-blue (recalled top-k flash + relatedness edges — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / non-recalled node)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (query marker / receipt ring)
const C_GRID   = 0x1b3a44;  // floor / link colour

const N_SLOTS = 16;   // visual episode slots (matches endpoint n_episodes cap)
const SPAN_X  = 16;   // world-unit span of the time axis

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _nodes = [];        // Array<THREE.Mesh> — one per episode
let _tempoLinks = null; // THREE.LineSegments — temporal-succession chain
let _semLinks = null;   // THREE.LineSegments — semantic-relatedness edges
let _queryMarker = null; // THREE.Mesh — the query episode ("now")

// per-node flash timers (recall highlight)
const _flash = new Float32Array(N_SLOTS);

// live state
const S = {
  label:      null,
  episodes:   null,   // Array<{id,text,t,salience,content_hash,honesty_receipt}>
  edges:      null,   // Array<{src,dst,type,weight}>
  topK:       null,   // Array<{id,score,components,rank}>
  query:      null,   // query text
  formula:    null,   // scoring_formula string
  receiptType: null,  // "HONEST-STUB" (verbatim)
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildNodes();
  _buildQueryMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onRecall, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

function _buildNodes() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.22, 14, 10);
  _nodes = [];
  for (let i = 0; i < N_SLOTS; i++) {
    const mat = new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15,
      metalness: 0.25, roughness: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    // placeholder position; laid out along time axis once live data arrives
    mesh.position.set((i / N_SLOTS) * SPAN_X - SPAN_X / 2, 1.4, 0);
    _group.add(mesh);
    _nodes.push(mesh);
  }
}

function _buildQueryMarker() {
  const THREE = _THREE;
  // Query episode = "now" — a pulsing teal marker at the far end of the time axis.
  _queryMarker = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.42, 0),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.6 }),
  );
  _queryMarker.position.set(SPAN_X / 2 + 1.4, 1.4, 0);
  _group.add(_queryMarker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onRecall(j) {
  // read honesty label VERBATIM — never upgrade
  S.label    = (j.label || "MODELED").toUpperCase();
  const g    = j.graph || {};
  S.episodes = Array.isArray(g.episodes) ? g.episodes : null;
  S.edges    = Array.isArray(g.edges) ? g.edges : null;
  const rec  = j.recall || {};
  S.topK     = Array.isArray(rec.top_k) ? rec.top_k : null;
  S.query    = (rec.query_episode && rec.query_episode.text) || j.query || null;
  S.formula  = j.scoring_formula || null;
  const firstReceipt = S.episodes && S.episodes[0] && S.episodes[0].honesty_receipt;
  S.receiptType = (firstReceipt && firstReceipt.type) || null;

  _layoutGraph();
  _paintOverlay();
}

// =============================================================================
// geometry updater — lays out nodes on the time axis, draws edges, highlights top-k
// =============================================================================
function _layoutGraph() {
  const THREE = _THREE;
  const live = S.state === "live";
  const episodes = S.episodes || [];
  const edges = S.edges || [];
  const topK = S.topK || [];
  const topIds = new Set(topK.map((r) => r.id));

  if (!episodes.length) {
    _nodes.forEach((mesh) => {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.1;
      mesh.scale.setScalar(0.5);
    });
    if (_tempoLinks) { _tempoLinks.material.opacity = 0.1; }
    if (_semLinks) { _semLinks.material.opacity = 0.06; }
    return;
  }

  const tMin = Math.min(...episodes.map((e) => e.t));
  const tMax = Math.max(...episodes.map((e) => e.t));
  const tSpan = Math.max(tMax - tMin, 1e-6);
  const idToPos = {};

  episodes.forEach((e, i) => {
    const mesh = _nodes[i % _nodes.length];
    const nx = ((e.t - tMin) / tSpan) * SPAN_X - SPAN_X / 2;
    mesh.position.set(nx, 1.4, 0);
    idToPos[e.id] = mesh.position.clone();

    const sal = typeof e.salience === "number" ? e.salience : 0.5;
    const recalled = topIds.has(e.id);
    const col = live ? (recalled ? C_TOP : C_NODE) : C_DIM;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = live ? (recalled ? 0.85 : 0.25) : 0.1;
    // node SIZE = salience (per spec)
    mesh.scale.setScalar(live ? (0.55 + 1.1 * sal) : 0.5);
    if (live && recalled) _flash[i % _flash.length] = 90;
  });

  // rebuild edge geometry (temporal-succession + semantic-relatedness)
  const tempoPts = [];
  const semPts = [];
  edges.forEach((ed) => {
    const a = idToPos[ed.src], b = idToPos[ed.dst];
    if (!a || !b) return;
    if (ed.type === "temporal-succession") { tempoPts.push(a, b); }
    else { semPts.push(a, b); }
  });

  if (_tempoLinks) { _group.remove(_tempoLinks); _tempoLinks.geometry.dispose(); _tempoLinks.material.dispose(); _tempoLinks = null; }
  if (_semLinks) { _group.remove(_semLinks); _semLinks.geometry.dispose(); _semLinks.material.dispose(); _semLinks = null; }

  if (tempoPts.length) {
    const g = new THREE.BufferGeometry().setFromPoints(tempoPts);
    _tempoLinks = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: live ? C_NODE : C_DIM, transparent: true, opacity: live ? 0.5 : 0.12 }));
    _group.add(_tempoLinks);
  }
  if (semPts.length) {
    const g = new THREE.BufferGeometry().setFromPoints(semPts);
    _semLinks = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: live ? C_TOP : C_DIM, transparent: true, opacity: live ? 0.32 : 0.08 }));
    _group.add(_semLinks);
  }

  if (_queryMarker) {
    const qcol = live ? C_ACCENT : C_DIM;
    _queryMarker.material.color.setHex(qcol);
    _queryMarker.material.emissive.setHex(qcol);
    _queryMarker.material.emissiveIntensity = live ? 0.5 : 0.15;
    _queryMarker.material.opacity = live ? 0.7 : 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.15;
  if (_queryMarker) { _queryMarker.rotation.y += 0.01; _queryMarker.rotation.x += 0.004; }

  const live = S.state === "live";
  _nodes.forEach((mesh, i) => {
    if (_flash[i] > 0) {
      _flash[i] -= 1;
      const f = _flash[i] / 90;
      const col = live ? C_TOP : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.2 + 0.9 * f);
    }
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "episodic graph", name: "ep" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'A small graph of <b>episodes</b> (event/fact nodes) laid out on a time axis, sized by ' +
      '<b>salience</b>, linked by temporal-succession and semantic-relatedness edges. A ' +
      '<b>RECALL</b> query lights up the top-k episodes by recency\u00d7salience\u00d7relatedness. ' +
      'Honesty label <b>MODELED</b> (synthetic/public episodes; clean-room-inspired by ' +
      'MemMachine\u2019s episodic/graph memory idea \u2014 not a reproduction). 0 runtime CDN.',
    citations:
      "MemMachine github.com/MemMachine/MemMachine (Apache-2.0) \u00b7 Tulving (1972) episodic/semantic memory \u00b7 Zep/Graphiti github.com/getzep/graphiti. MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["ep-n"]       = _show.addField("episodes in graph");
  _el["ep-query"]   = _show.addField("recall query");
  _el["ep-top1"]    = _show.addField("top recall (id, score)");
  _el["ep-receipt"] = _show.addField("receipt type");
  _el["ep-label"]   = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const n = S.episodes ? String(S.episodes.length) : "loading\u2026";
  const top0 = (S.topK && S.topK[0]) ? S.topK[0] : null;
  const topTxt = top0 ? (top0.id + " (score " + fx(top0.score, 3) + ")") : "loading\u2026";
  const rtype = S.receiptType || "loading\u2026";
  return (
    "<b>What this means:</b> Most AI systems today either forget everything between " +
    "sessions or dump raw transcripts into a vector store. This organ demonstrates a " +
    "<b>third option</b>: memories as a small, auditable <b>graph</b> of discrete " +
    "\u201cepisodes\u201d (here, <b>" + n + "</b> of them) connected by time and meaning. " +
    "Asking a question triggers a <b>recall</b> that ranks episodes by how recent, how " +
    "important (salience), and how related they are \u2014 right now the top match is " +
    "<b>" + topTxt + "</b>. Every episode carries a real content fingerprint plus a " +
    "clearly labeled <b>" + rtype + "</b> receipt \u2014 an honest placeholder for real " +
    "cryptographic signing, never faked as one. " +
    "Plain: this is what \u201cthe AI remembers what happened, and can prove what it " +
    "remembers,\u201d looks like \u2014 but this view is a <b>MODELED</b> demonstration with " +
    "synthetic/public data, not a production memory store.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("ep-n",       t || (S.episodes != null ? String(S.episodes.length) : "\u2014"));
  _set("ep-query",   t || (S.query || "\u2014"));
  const top0 = (S.topK && S.topK[0]) ? S.topK[0] : null;
  _set("ep-top1",    t || (top0 ? (top0.id + "  (score " + fx(top0.score, 4) + ")") : "\u2014"));
  _set("ep-receipt", t || (S.receiptType || "\u2014"));
  // honesty label verbatim — never upgraded
  _set("ep-label",   t || (S.label || "MODELED"));
  if (_show) { _show.setChip("ep", S.label || "MODELED", { text: "episodic graph" }); _show.refreshPlain(); }
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
  _nodes = []; _tempoLinks = null; _semLinks = null; _queryMarker = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.episodes = S.edges = S.topK = S.query = S.formula = S.receiptType = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
