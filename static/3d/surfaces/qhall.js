// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/qhall.js — QUANTUM-INSPIRED TENSOR-NETWORK HALLUCINATION-UNCERTAINTY
// organ for the holographic frontier ring.
//
// Renders a 3D constellation of candidate LLM generations, encoded as low-bond-dimension
// matrix-product-state (MPS) vectors and grouped into semantic-equivalence clusters, driven
// by a live snapshot from /api/killinchu/v1/qhall/quantify. Each generation is a node; nodes
// in the same semantic cluster share a colour and orbit a common cluster centroid. A HUD
// tracks the semantic entropy (aleatoric-uncertainty score) and whether it crosses the
// oversight threshold — the "entropy maximization for human-review flagging" behaviour.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// IMPORTANT — QUANTUM-INSPIRED, NOT A REAL QUANTUM COMPUTER:
//   "Quantum tensor network" here is the mathematical INSPIRATION (low-rank MPS math from
//   quantum many-body physics), simulated ENTIRELY on a classical CPU. There is NO quantum
//   hardware, NO quantum circuit, and NO real LLM behind this organ — the candidate answers
//   and their sequence log-probabilities are synthetic toy data. This is stated plainly in
//   the "what this means" copy and echoed in the endpoint's own JSON payload.
//
// Surface export shape (mirrors interpretability.js / qec.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   n_generations         — candidate generations for the fixed prompt
//   bond_dim              — MPS bond dimension χ (low-rank truncation)
//   n_clusters            — semantic-equivalence classes found
//   cluster_sizes         — member counts per class
//   semantic_entropy      — aleatoric-uncertainty score (nats)
//   normalized_entropy    — semantic_entropy / ln(n)  (0..1)
//   threshold             — oversight threshold (nats)
//   flag_for_review       — bool (entropy-maximization human-review flag)
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Vipulanandan, Premaratne & Sarkar (2026) "Semantic Uncertainty Quantification of
//     Hallucinations in LLMs: A Quantum Tensor Network Based Method". arXiv:2601.20026
//     (ICLR 2026; 116 experiments, 8 model families).
//     https://arxiv.org/abs/2601.20026
//
// HONESTY LABELS: MODELED (simulation of the METHOD on synthetic toy data; quantum-INSPIRED
//   classical MPS stand-in, NO real quantum hardware, NO real LLM). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee (consistent / dominant cluster nodes), violet-blue 0x8a6bff
//   (scattered / contradictory cluster nodes — data-viz only), proof-teal 0x3af4c8 (entropy
//   HUD accent), greys for dim/idle. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// This organ adds NOTHING to SZL's own locked-8 / Λ-Conjecture-1.

import { createShowcase } from "./_showcase.js";

const ID    = "qhall";
const TITLE = "Quantum-Inspired Tensor-Network Hallucination Uncertainty (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the qhall organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/qhall/quantify?seed=42&n_generations=8&bond_dim=4&threshold=0.9";

// data-viz hues — purple BANNED
const C_NODE   = 0x5b8dee;  // lattice-blue (consistent / dominant-cluster generation)
const C_SCAT   = 0x8a6bff;  // violet-blue (scattered / minority-cluster generation — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / idle node)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (entropy HUD ring)
const C_GRID   = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _nodes = [];        // Array<THREE.Mesh> — one per candidate generation
let _links = null;      // THREE.LineSegments — intra-cluster links
let _ring = null;       // THREE.Mesh — entropy HUD ring above the constellation
const _lastN = { n: 0 };// last-built node count, so we only rebuild on change

// max constellation we'll ever build (matches endpoint answer-bank cap)
const _MAX_NODES = 8;
const _pulse = new Float32Array(_MAX_NODES);

// live state
const S = {
  label:      null,
  n:          null,   // n_generations
  bondDim:    null,   // bond_dim
  nClusters:  null,   // n_clusters
  sizes:      null,   // cluster_sizes[]
  entropy:    null,   // semantic_entropy
  normEnt:    null,   // normalized_entropy
  threshold:  null,   // threshold
  flag:       null,   // flag_for_review
  clusterOf:  [],     // per-node cluster index (from generations[])
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildConstellation(8);   // default 8-node constellation; rebuilt on live data if n differs
  _buildEntropyRing();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onQuantify, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Build (or rebuild) an n-node constellation of candidate generations, laid out on a
// ring. Cluster membership (colour + intra-cluster links) is applied later from live data.
function _buildConstellation(n) {
  const THREE = _THREE;
  n = Math.max(2, Math.min(n | 0, _MAX_NODES));
  if (_lastN.n === n && _nodes.length) return; // already built at this size
  _lastN.n = n;

  _disposeConstellation();

  const radius = 5.2;
  const y = 1.4;

  const geo = new THREE.SphereGeometry(0.42, 16, 12);
  const mat0 = new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.25, roughness: 0.55 });

  _nodes = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * radius;
    const z = Math.sin(a) * radius;
    const mesh = new THREE.Mesh(geo, mat0.clone());
    mesh.position.set(x, y, z);
    mesh.userData.home = new THREE.Vector3(x, y, z);
    _group.add(mesh);
    _nodes.push(mesh);
  }
}

function _disposeConstellation() {
  if (_nodes[0] && _nodes[0].geometry) _nodes[0].geometry.dispose(); // shared geometry
  _nodes.forEach((m) => {
    _group.remove(m);
    if (m.material && m.material.dispose) m.material.dispose();
  });
  if (_links) {
    _group.remove(_links);
    if (_links.geometry) _links.geometry.dispose();
    if (_links.material) _links.material.dispose();
    _links = null;
  }
  _nodes = [];
}

function _buildEntropyRing() {
  const THREE = _THREE;
  _ring = new THREE.Mesh(
    new THREE.TorusGeometry(2.0, 0.035, 10, 64),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.5 }),
  );
  _ring.position.set(0, 5.6, 0);
  _ring.rotation.x = Math.PI / 2;
  _group.add(_ring);
}

// =============================================================================
// live data handler
// =============================================================================
function _onQuantify(j) {
  // Read honesty label VERBATIM — never upgrade. Handle top-level 'label' OR a nested
  // 'payload.label' so we match this module's own shape (top-level) AND any wrapper.
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (p && p.label != null) ? p.label : (j && j.label != null ? j.label : "MODELED");
  S.label = String(rawLabel).toUpperCase();

  S.n          = typeof p.n_generations      === "number" ? p.n_generations      : null;
  S.bondDim    = typeof p.bond_dim           === "number" ? p.bond_dim           : null;
  S.nClusters  = typeof p.n_clusters         === "number" ? p.n_clusters         : null;
  S.sizes      = Array.isArray(p.cluster_sizes) ? p.cluster_sizes                : null;
  S.entropy    = typeof p.semantic_entropy   === "number" ? p.semantic_entropy   : null;
  S.normEnt    = typeof p.normalized_entropy === "number" ? p.normalized_entropy : null;
  S.threshold  = typeof p.threshold          === "number" ? p.threshold          : null;
  S.flag       = typeof p.flag_for_review    === "boolean" ? p.flag_for_review   : null;

  // per-node cluster assignment from generations[]
  S.clusterOf = [];
  if (Array.isArray(p.generations)) {
    p.generations.forEach((g) => {
      S.clusterOf.push(typeof g.cluster === "number" ? g.cluster : 0);
    });
  }

  if (S.n) _buildConstellation(S.n);
  _updateConstellation();
  _paintOverlay();
}

// =============================================================================
// geometry updater — colours nodes by cluster, links intra-cluster members
// =============================================================================
function _updateConstellation() {
  const THREE = _THREE;
  const live = S.state === "live";

  // dominant cluster (largest) is drawn lattice-blue (consistent); minority clusters are
  // violet-blue (scattered / contradictory — data-viz only).
  let dominant = 0;
  if (Array.isArray(S.sizes) && S.sizes.length) {
    let best = -1;
    S.sizes.forEach((sz, ci) => { if (sz > best) { best = sz; dominant = ci; } });
  }

  _nodes.forEach((mesh, i) => {
    if (live && S.clusterOf.length) {
      const ci = i < S.clusterOf.length ? S.clusterOf[i] : 0;
      const col = ci === dominant ? C_NODE : C_SCAT;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.35;
      _pulse[i] = 60;
    } else {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.12;
    }
  });

  // intra-cluster links: connect every pair of nodes sharing a cluster.
  if (_links) {
    _group.remove(_links);
    if (_links.geometry) _links.geometry.dispose();
    if (_links.material) _links.material.dispose();
    _links = null;
  }
  if (live && S.clusterOf.length) {
    const pts = [];
    for (let a = 0; a < _nodes.length; a++) {
      for (let b = a + 1; b < _nodes.length; b++) {
        if (S.clusterOf[a] != null && S.clusterOf[a] === S.clusterOf[b]) {
          pts.push(_nodes[a].position.clone(), _nodes[b].position.clone());
        }
      }
    }
    if (pts.length) {
      const lg = new THREE.BufferGeometry().setFromPoints(pts);
      _links = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: C_NODE, transparent: true, opacity: 0.3 }));
      _group.add(_links);
    }
  }

  if (_ring) {
    // ring brightness/scale scales with normalized entropy: HIGH entropy (scattered,
    // flagged for review) burns brighter; LOW entropy (consistent) stays calm.
    const norm = S.normEnt != null ? Math.max(0, Math.min(1, S.normEnt)) : 0;
    const flagged = S.flag === true;
    const rcol = live ? (flagged ? C_SCAT : C_ACCENT) : C_DIM;
    _ring.material.color.setHex(rcol);
    _ring.material.emissive.setHex(rcol);
    _ring.material.emissiveIntensity = live ? 0.2 + 0.7 * norm : 0.12;
    _ring.material.opacity = live ? 0.55 : 0.2;
    _ring.scale.setScalar(live ? (0.7 + 0.6 * norm) : 0.8);
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.15;
  if (_ring) { _ring.rotation.z += 0.004; }

  const live = S.state === "live";
  _nodes.forEach((mesh, i) => {
    if (_pulse[i] > 0) {
      _pulse[i] -= 1;
      const f = _pulse[i] / 60;
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.2 + 0.8 * f);
    }
    // gentle bob so consistent vs scattered clusters read as "living" data
    if (mesh.userData.home) {
      mesh.position.y = mesh.userData.home.y + (live ? Math.sin(t * 0.0012 + i) * 0.12 : 0);
    }
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "tensor-network uncertainty", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Several candidate answers for one prompt are encoded as low-rank ' +
    '<b>matrix-product-state (MPS) tensor vectors</b>, clustered into ' +
    '<b>semantic-equivalence classes</b>, and scored by the <b>entropy</b> of the ' +
    'cluster distribution. Low entropy \u2192 the answers agree (confident); high ' +
    'entropy \u2192 they contradict each other and the prompt is <b>flagged for human ' +
    'review</b>. Honesty label <b>MODELED</b> \u2014 <b>quantum-INSPIRED</b> (a classical ' +
    'tensor-network stand-in), <b>not</b> a real quantum computer and not a real LLM. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "qhall \u00b7 semantic-uncertainty";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:58%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("qh-n",      "candidate generations"));
  grid.appendChild(kpiRow("qh-bond",   "MPS bond dimension \u03c7"));
  grid.appendChild(kpiRow("qh-clus",   "semantic clusters"));
  grid.appendChild(kpiRow("qh-sizes",  "cluster sizes"));
  grid.appendChild(kpiRow("qh-ent",    "semantic entropy (nats) \u2014 MODELED"));
  grid.appendChild(kpiRow("qh-norm",   "normalized entropy (0\u20131)"));
  grid.appendChild(kpiRow("qh-thr",    "oversight threshold (nats)"));
  grid.appendChild(kpiRow("qh-flag",   "flag for human review"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Vipulanandan, Premaratne & Sarkar arXiv:2601.20026 (ICLR 2026) \u00b7 quantum-INSPIRED classical MPS stand-in, no real quantum hardware, no real LLM. MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "qhall-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const n    = S.n != null ? String(S.n) : "loading\u2026";
  const cl   = S.nClusters != null ? String(S.nClusters) : "loading\u2026";
  const ent  = S.entropy != null ? S.entropy.toFixed(3) : "loading\u2026";
  const verdict = S.flag == null
    ? "loading\u2026"
    : (S.flag ? "FLAGGED for a human to double-check" : "confident \u2014 no review needed");
  pd.innerHTML =
    "<b>What this means:</b> We ask the model the same question and collect <b>" + n + "</b> " +
    "candidate answers. Each answer is turned into a compact math fingerprint (a " +
    "<b>tensor-network / MPS vector</b>) and answers that mean the same thing are grouped " +
    "together \u2014 here into <b>" + cl + "</b> distinct meaning-groups. If almost all answers " +
    "land in one group, the model is confident; if they scatter across many contradictory " +
    "groups, that's a warning sign of a possible <b>hallucination</b>. We measure that scatter " +
    "with <b>entropy = " + ent + "</b>: right now this prompt is <b>" + verdict + "</b>. " +
    "<br><br><b>Important honesty note:</b> this organ is <b>quantum-INSPIRED</b>, not a real " +
    "quantum computer. The tensor-network math borrows ideas from quantum physics, but it runs " +
    "entirely on an ordinary classical processor \u2014 there is <b>no quantum hardware</b> and " +
    "<b>no quantum circuit</b> involved. It is also <b>not</b> a real language model: the answers " +
    "and their probabilities are <b>synthetic toy data</b> for demonstration. Everything shown is " +
    "a <b>MODELED</b> simulation of the method (Vipulanandan et al., ICLR 2026), not a live readout.";
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
  _set("qh-n",     t || (S.n != null ? String(S.n) : "\u2014"));
  _set("qh-bond",  t || (S.bondDim != null ? String(S.bondDim) : "\u2014"));
  _set("qh-clus",  t || (S.nClusters != null ? String(S.nClusters) : "\u2014"));
  _set("qh-sizes", t || (Array.isArray(S.sizes) ? "[" + S.sizes.join(", ") + "]" : "\u2014"));
  _set("qh-ent",   t || fx(S.entropy, 3));
  _set("qh-norm",  t || fx(S.normEnt, 3));
  _set("qh-thr",   t || fx(S.threshold, 3));
  _set("qh-flag",  t || (S.flag == null ? "\u2014" : (S.flag ? "FLAG \u2014 send to human review" : "clear \u2014 high confidence")));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "tensor-network uncertainty" });
  if (_plain) _applyPlain();
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
  _nodes = []; _links = null; _ring = null;
  _lastN.n = 0;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.n = S.bondDim = S.nClusters = S.sizes = null;
  S.entropy = S.normEnt = S.threshold = S.flag = null;
  S.clusterOf = [];
  S.state = "init";
  _pulse.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
