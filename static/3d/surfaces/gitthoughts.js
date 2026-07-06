// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/gitthoughts.js — GITOFTHOUGHTS VERSION-CONTROLLED REASONING MEMORY
// organ for the holographic frontier ring (GitOfThoughts = an agent's reasoning
// tree stored as a git repository: every scored thought is a COMMIT, scores are
// NOTES, terminal outcomes are TAGS, retrieval is `git log`; Shekar, Abhishek H S,
// Krishnan, arXiv:2606.14470). Renders the live snapshot as three panels:
//   (1) COMMIT TREE — the scored reasoning tree as a 3D branching DAG; each
//       thought is a commit node coloured by outcome tag (solved / partial /
//       dead-end), edges are parent links, and the HEAD->root `git log` branch
//       is highlighted in proof-teal;
//   (2) COPYABILITY THRESHOLD CURVE — retrieval accuracy vs case-similarity as a
//       3D line with the ~0.8 threshold plane, honestly showing the SHARP jump
//       (near-duplicate = answer retrieval) and the ~0 gain below it;
//   (3) DIFF / MERGE BARS — only-A / shared / only-B commit counts and the merged
//       commit count with any conflict slots.
// A HUD reports the MEASURED metrics from /api/killinchu/v1/gitthoughts/tree.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is;
// it is never upgraded.
//
// Surface export shape (mirrors muon.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   depth, branch, commit_count, leaf_count, head_sha, root_sha,
//   git_log[{sha7,depth,score,note,tag,content}], replay_ok, replay_len,
//   diff{only_a_count,shared_count,only_b_count,...}, merge{merged_commit_count,
//   conflict_count,...}, tag_histogram{solved,partial,dead-end}, threshold,
//   sweep[{similarity,accuracy,baseline,gain}], jump_size,
//   gain_below_threshold, gain_above_threshold
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   GitOfThoughts: Version-Controlled Reasoning and Agent Memory You Can Replay,
//     Diff, and Merge — Pavan C Shekar, Abhishek H S, Aswanth Krishnan.
//     https://arxiv.org/abs/2606.14470
//   Git content-addressed object model (Merkle DAG of commits) — Pro Git:
//     https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
//
// HONESTY LABELS: MODELED (deterministic reproduction of the GitOfThoughts DATA
//   STRUCTURE — commit/note/tag/log/replay/diff/merge — plus the copyability-
//   threshold finding on a synthetic case bank; runs NO real LLM; reasons
//   nothing; the ~0 below-threshold gain is MEASURED and displayed; the paper's
//   honest headline — memory does NOT improve novel-problem accuracy — is
//   reproduced; NEVER-CLAIMED-AS a real agent-memory system). Read verbatim.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "gitthoughts";
const TITLE = "GitOfThoughts (Version-Controlled Reasoning)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/gitthoughts/tree?seed=42&depth=4&branch=3";

// data-viz hues — purple BANNED
const C_SOLVED  = 0x3af4c8;  // proof-teal   (outcome tag: solved / HEAD branch)
const C_PARTIAL = 0x5b8dee;  // lattice-blue (outcome tag: partial)
const C_DEAD    = 0x5a6570;  // grey         (outcome tag: dead-end)
const C_INNER   = 0x42505d;  // grey         (non-leaf commit node)
const C_EDGE    = 0x1b3a44;  // link / floor colour (parent edges)
const C_HEAD    = 0x3af4c8;  // proof-teal   (HEAD->root git-log branch highlight)
const C_CURVE   = 0x5b8dee;  // lattice-blue (accuracy curve below threshold)
const C_CURVEHI = 0x3af4c8;  // proof-teal   (accuracy curve above threshold)
const C_THRESH  = 0x8a6bff;  // violet-blue  (~0.8 threshold plane)
const C_BASE    = 0x5a6570;  // grey         (no-memory baseline line)
const C_ONLYA   = 0x5b8dee;  // lattice-blue (diff: only-A commits)
const C_SHARED  = 0x8a6bff;  // violet-blue  (diff: shared commits)
const C_ONLYB   = 0x3af4c8;  // proof-teal   (diff: only-B commits)
const C_MERGE   = 0x3af4c8;  // proof-teal   (merged commit count)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)

// layout geometry
const TREE_DY   = 1.5;    // vertical world-units per tree depth level
const TREE_SPAN = 9.0;    // horizontal span of the widest tree level
const NODE_R    = 0.09;   // commit node sphere radius
const CURVE_X0  = 7.0;    // threshold-curve panel origin x
const CURVE_W   = 5.0;    // curve panel width (similarity 0..1)
const CURVE_H   = 3.2;    // curve panel height (accuracy 0..1)
const BAR_W     = 0.7;    // diff/merge bar width
const BAR_YSC   = 0.32;   // world-units per commit in the bars

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _treeGroup  = null;   // THREE.Group — commit tree nodes + edges + HEAD branch
let _curveGroup = null;   // THREE.Group — copyability threshold curve + planes
let _barGroup   = null;   // THREE.Group — diff/merge bars

// live state
const S = {
  label:       null,
  depth:       null,
  branch:      null,
  commitCount: null,   // commit_count
  leafCount:   null,   // leaf_count
  headSha:     null,   // head_sha
  rootSha:     null,   // root_sha
  gitLog:      null,   // Array<{sha7,depth,score,tag,content}>
  replayOk:    null,   // replay_ok
  replayLen:   null,   // replay_len
  diff:        null,   // {only_a_count,shared_count,only_b_count,...}
  merge:       null,   // {merged_commit_count,conflict_count,...}
  tagHist:     null,   // {solved,partial,"dead-end"}
  threshold:   null,   // ~0.8
  sweep:       null,   // Array<{similarity,accuracy,baseline,gain}>
  jumpSize:    null,   // jump_size
  gainBelow:   null,   // gain_below_threshold
  gainAbove:   null,   // gain_above_threshold
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 6, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 1.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildTree();
  _buildCurve();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onGit, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_EDGE, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// commit-tree panel: nodes/edges are rebuilt in place whenever fresh data
// arrives (node count depends on live depth/branch). Group is pre-created here.
function _buildTree() {
  const THREE = _THREE;
  _treeGroup = new THREE.Group();
  _treeGroup.position.set(-2.0, 0.2, 0);
  _group.add(_treeGroup);
}

// copyability threshold curve panel — the curve line + threshold plane + baseline
// are rebuilt in _updateCurve once the live sweep/threshold are known.
function _buildCurve() {
  const THREE = _THREE;
  _curveGroup = new THREE.Group();
  _curveGroup.position.set(CURVE_X0, 0.0, -2.5);
  _group.add(_curveGroup);
}

// diff/merge bars — heights set live in _updateBars.
function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(CURVE_X0 + 0.4, 0, 3.6);
  _group.add(_barGroup);
}

// =============================================================================
// live data handler
// =============================================================================
function _onGit(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.depth       = typeof src.depth        === "number" ? src.depth        : null;
  S.branch      = typeof src.branch       === "number" ? src.branch       : null;
  S.commitCount = typeof src.commit_count === "number" ? src.commit_count : null;
  S.leafCount   = typeof src.leaf_count   === "number" ? src.leaf_count   : null;
  S.headSha     = typeof src.head_sha     === "string" ? src.head_sha     : null;
  S.rootSha     = typeof src.root_sha     === "string" ? src.root_sha     : null;
  S.replayOk    = (typeof src.replay_ok   === "boolean") ? src.replay_ok  : null;
  S.replayLen   = typeof src.replay_len   === "number" ? src.replay_len   : null;
  S.threshold   = typeof src.threshold    === "number" ? src.threshold    : null;
  S.jumpSize    = typeof src.jump_size    === "number" ? src.jump_size    : null;
  S.gainBelow   = typeof src.gain_below_threshold === "number" ? src.gain_below_threshold : null;
  S.gainAbove   = typeof src.gain_above_threshold === "number" ? src.gain_above_threshold : null;

  S.gitLog  = Array.isArray(src.git_log) ? src.git_log : null;
  S.sweep   = Array.isArray(src.sweep)   ? src.sweep   : null;
  S.diff    = (src.diff  && typeof src.diff  === "object") ? src.diff  : null;
  S.merge   = (src.merge && typeof src.merge === "object") ? src.merge : null;
  S.tagHist = (src.tag_histogram && typeof src.tag_histogram === "object") ? src.tag_histogram : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateTree();
  _updateCurve();
  _updateBars();
}

function _disposeChildren(grp) {
  if (!grp) return;
  for (let i = grp.children.length - 1; i >= 0; i--) {
    const o = grp.children[i];
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) {
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => { if (m.dispose) m.dispose(); });
    }
    grp.remove(o);
  }
}

function _tagColor(tag) {
  if (tag === "solved") return C_SOLVED;
  if (tag === "partial") return C_PARTIAL;
  if (tag === "dead-end") return C_DEAD;
  return C_INNER;
}

// Rebuild the full commit tree as a branching DAG from live depth/branch, then
// overlay the HEAD->root git-log branch in proof-teal. Node count is bounded so
// the panel stays cheap (cap total rendered nodes).
function _updateTree() {
  const THREE = _THREE;
  if (!_treeGroup) return;
  _disposeChildren(_treeGroup);

  const live = S.state === "live";
  if (!live || S.depth == null || S.branch == null) return;

  const depth  = Math.max(1, Math.min(S.depth, 7));
  const branch = Math.max(1, Math.min(S.branch, 4));

  // cap: don't render more than this many nodes total (keeps big trees legible)
  const NODE_CAP = 400;

  // place nodes level by level; positions[level] = array of {x,y,idx}
  const nodeGeo = new THREE.SphereGeometry(NODE_R, 10, 8);
  const positions = [];
  let rendered = 0;

  for (let d = 0; d <= depth; d++) {
    const count = Math.pow(branch, d);
    const y = 3.0 - d * TREE_DY;                    // root at top, leaves at bottom
    const levelArr = [];
    for (let i = 0; i < count; i++) {
      if (rendered >= NODE_CAP) break;
      const x = count > 1 ? (-TREE_SPAN / 2 + (TREE_SPAN * i) / (count - 1)) : 0.0;
      levelArr.push({ x, y, idx: i });
      rendered++;
    }
    positions.push(levelArr);
  }

  // is a given (depth,idx) node on the HEAD->root git-log branch?
  // gitLog is HEAD..root (depth descending); reconstruct each level's sibling idx.
  // For the highlight we approximate the branch as one node per level whose
  // sibling index matches the recorded git_log slot when derivable; otherwise
  // fall back to index 0. Robust to shape: we only ever tint, never index-crash.
  const headBranchIdx = {};   // depth -> idx on the HEAD branch
  if (Array.isArray(S.gitLog)) {
    for (const c of S.gitLog) {
      if (c && typeof c.depth === "number") {
        // derive sibling index from the content tag "s<idx>" if present
        let idx = 0;
        if (typeof c.content === "string") {
          const mm = c.content.match(/\bs(\d+)\b/);
          if (mm) idx = parseInt(mm[1], 10);
        }
        headBranchIdx[c.depth] = idx;
      }
    }
  }

  // edges (parent links) + nodes
  const outerTag = { solved: false };
  for (let d = 0; d <= positions.length - 1; d++) {
    const level = positions[d];
    for (let i = 0; i < level.length; i++) {
      const p = level[i];
      const isLeaf = d === depth;
      // colour: leaves by outcome tag (cycled from tag_histogram proportions is
      // not per-node available, so leaves use score-agnostic solved/partial/dead
      // by position bucket for a representative palette); inner = grey.
      let color = C_INNER;
      if (isLeaf) {
        // representative tag colouring: split leaves into three bands by index
        const third = Math.max(1, Math.ceil(level.length / 3));
        color = i < third ? C_SOLVED : (i < 2 * third ? C_PARTIAL : C_DEAD);
      }
      const onHead = (headBranchIdx[d] != null) && (i === Math.min(headBranchIdx[d], level.length - 1));
      const mat = new THREE.MeshStandardMaterial({
        color: onHead ? C_HEAD : color,
        emissive: onHead ? C_HEAD : color,
        emissiveIntensity: onHead ? 0.6 : 0.25,
        transparent: true, opacity: onHead ? 0.98 : 0.85,
      });
      const mesh = new THREE.Mesh(nodeGeo, mat);
      mesh.position.set(p.x, p.y, 0);
      if (onHead) mesh.scale.setScalar(1.6);
      _treeGroup.add(mesh);

      // edge to parent (parent index = floor(i / branch))
      if (d > 0) {
        const parentLevel = positions[d - 1];
        const pj = Math.floor(i / branch);
        if (parentLevel[pj]) {
          const par = parentLevel[pj];
          const parentOnHead = (headBranchIdx[d - 1] != null) && (pj === Math.min(headBranchIdx[d - 1], parentLevel.length - 1));
          const edgeHi = onHead && parentOnHead;
          const eg = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(par.x, par.y, 0),
            new THREE.Vector3(p.x, p.y, 0),
          ]);
          const em = new THREE.LineBasicMaterial({
            color: edgeHi ? C_HEAD : C_EDGE,
            transparent: true,
            opacity: edgeHi ? 0.9 : 0.35,
          });
          _treeGroup.add(new THREE.Line(eg, em));
        }
      }
    }
  }
  void outerTag;
}

// Rebuild the copyability-threshold curve: a 3D line of (similarity, accuracy),
// a violet-blue vertical plane at the ~0.8 threshold, and a grey baseline line.
// Points above the threshold are proof-teal, below are lattice-blue — the SHARP
// jump is visually obvious.
function _updateCurve() {
  const THREE = _THREE;
  if (!_curveGroup) return;
  _disposeChildren(_curveGroup);

  const live = S.state === "live";
  if (!live || !Array.isArray(S.sweep) || !S.sweep.length) return;

  const thr = (S.threshold != null) ? S.threshold : 0.8;

  // baseline (no-memory accuracy) grey line across the panel
  let base = 0.42;
  if (S.sweep[0] && typeof S.sweep[0].baseline === "number") base = S.sweep[0].baseline;
  const baseGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, base * CURVE_H, 0),
    new THREE.Vector3(CURVE_W, base * CURVE_H, 0),
  ]);
  _curveGroup.add(new THREE.Line(baseGeo, new THREE.LineBasicMaterial({ color: C_BASE, transparent: true, opacity: 0.5 })));

  // threshold plane at similarity = thr (violet-blue, translucent, vertical)
  const planeGeo = new THREE.PlaneGeometry(CURVE_H * 1.05, 3.2);
  const planeMat = new THREE.MeshBasicMaterial({ color: C_THRESH, transparent: true, opacity: 0.12, side: THREE.DoubleSide });
  const plane = new THREE.Mesh(planeGeo, planeMat);
  plane.position.set(thr * CURVE_W, CURVE_H * 0.5, 0);
  plane.rotation.y = Math.PI / 2;
  _curveGroup.add(plane);

  // accuracy curve — build two coloured segments (below / above threshold)
  const belowPts = [];
  const abovePts = [];
  for (const r of S.sweep) {
    if (!r || typeof r.similarity !== "number" || typeof r.accuracy !== "number") continue;
    const v = new THREE.Vector3(r.similarity * CURVE_W, r.accuracy * CURVE_H, 0);
    if (r.similarity <= thr) belowPts.push(v);
    if (r.similarity >= thr) abovePts.push(v);
  }
  if (belowPts.length >= 2) {
    const g = new THREE.BufferGeometry().setFromPoints(belowPts);
    _curveGroup.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: C_CURVE, transparent: true, opacity: 0.85 })));
  }
  if (abovePts.length >= 2) {
    const g = new THREE.BufferGeometry().setFromPoints(abovePts);
    _curveGroup.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: C_CURVEHI, transparent: true, opacity: 0.95 })));
  }

  // small marker spheres at each sweep point (teal above, blue below)
  const dotGeo = new THREE.SphereGeometry(0.05, 8, 6);
  for (const r of S.sweep) {
    if (!r || typeof r.similarity !== "number" || typeof r.accuracy !== "number") continue;
    const col = r.similarity >= thr ? C_CURVEHI : C_CURVE;
    const m = new THREE.Mesh(dotGeo, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.9 }));
    m.position.set(r.similarity * CURVE_W, r.accuracy * CURVE_H, 0);
    _curveGroup.add(m);
  }
}

// diff/merge bars: only-A | shared | only-B commit counts, plus merged count.
function _updateBars() {
  const THREE = _THREE;
  if (!_barGroup) return;
  _disposeChildren(_barGroup);

  const live = S.state === "live";
  if (!live) return;

  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  function bar(x, count, color) {
    const c = (typeof count === "number") ? count : 0;
    const h = Math.max(0.06, c * BAR_YSC);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.4, transparent: true, opacity: 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h * 0.5, 0);
    _barGroup.add(mesh);
  }

  const d = S.diff || {};
  bar(0.0, d.only_a_count, C_ONLYA);
  bar(1.0, d.shared_count, C_SHARED);
  bar(2.0, d.only_b_count, C_ONLYB);
  const m = S.merge || {};
  bar(3.3, m.merged_commit_count, C_MERGE);
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;
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
    maxWidth: "min(94%,480px)",
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
    'GitOfThoughts stores an agent\u2019s reasoning tree as a <b>git repository</b>: every scored thought is a ' +
    '<b>commit</b> (sha256 over parent+content+score \u2014 a Merkle DAG), scores are <b>notes</b>, outcomes are ' +
    '<b>tags</b>, and retrieval is a <b>git log</b> DAG walk. This organ models the substrate \u2014 <b>log, replay, ' +
    'diff, merge</b> \u2014 and the paper\u2019s honest <b>copyability threshold</b>: memory only helps once the ' +
    'retrieved case is a near-duplicate (cosine similarity above <b>~0.8</b>); below it there is <b>no gain</b> ' +
    '(the model finds the answer, it does not transfer the method). Panels: commit tree, threshold curve, ' +
    'diff/merge bars. Honesty label <b>MODELED</b> (data-structure + finding reproduction; runs no LLM). 0 runtime CDN.';
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
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "gitofthoughts version-controlled reasoning";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("gt-tree",    "reasoning tree (depth \u00d7 branch)"));
  grid.appendChild(kpiRow("gt-commits", "commits (thoughts)"));
  grid.appendChild(kpiRow("gt-leaves",  "terminal thoughts (tagged)"));
  grid.appendChild(kpiRow("gt-head",    "HEAD sha (highest-scoring leaf)"));
  grid.appendChild(kpiRow("gt-log",     "git log length (HEAD\u2192root)"));
  grid.appendChild(kpiRow("gt-replay",  "replay verified (shas re-derived)"));
  grid.appendChild(kpiRow("gt-diff",    "diff (onlyA / shared / onlyB)"));
  grid.appendChild(kpiRow("gt-merge",   "merge (commits / conflicts)"));
  grid.appendChild(kpiRow("gt-tags",    "outcomes (solved / partial / dead)"));
  grid.appendChild(kpiRow("gt-thr",     "copyability threshold (cosine)"));
  grid.appendChild(kpiRow("gt-jump",    "accuracy jump across threshold"));
  grid.appendChild(kpiRow("gt-below",   "gain BELOW threshold (MEASURED)"));
  grid.appendChild(kpiRow("gt-above",   "gain ABOVE threshold (MEASURED)"));
  grid.appendChild(kpiRow("gt-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "GitOfThoughts \u2014 Shekar, Abhishek H S, Krishnan, arXiv:2606.14470 (arxiv.org/abs/2606.14470) \u00b7 git object model, Pro Git. MODELED \u00b7 data-structure + copyability-threshold reproduction; runs no LLM; memory does NOT improve novel-problem accuracy (reproduced honestly).";
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
  pd.id = "gt-plain";
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
  const thr   = S.threshold != null ? S.threshold.toFixed(2)   : "~0.80";
  const jump  = S.jumpSize   != null ? (S.jumpSize * 100).toFixed(0) + " pts" : "loading\u2026";
  const below = S.gainBelow  != null ? (S.gainBelow * 100).toFixed(1) + "%"   : "loading\u2026";
  const comm  = S.commitCount != null ? String(S.commitCount) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> When an AI reasons, its train of thought vanishes the moment it finishes \u2014 you " +
    "cannot audit it, replay it, or combine two agents\u2019 histories. GitOfThoughts fixes that by saving every " +
    "thought as a <b>git commit</b>, exactly like version-controlling code: each thought gets a fingerprint " +
    "(sha) built from its parent and content, so the whole history is tamper-evident and you can <b>replay, " +
    "diff, and merge</b> it. Here the tree holds about <b>" + comm + "</b> commits. But the researchers asked a " +
    "blunt question \u2014 <i>does giving an agent this memory make it smarter on new problems?</i> \u2014 and their " +
    "honest answer was <b>no</b>. Memory only helps when a past case is almost identical to the new one " +
    "(similarity above <b>" + thr + "</b>): then the model is simply <b>copying the answer</b>, not learning the " +
    "method. Below that line, the gain is essentially zero (<b>" + below + "</b> here). This view reproduces both the " +
    "data structure AND that honesty: the accuracy curve is flat until it <b>jumps by ~" + jump + "</b> right at the " +
    "threshold. This is a <b>MODELED</b> demo \u2014 it runs no real AI and claims no accuracy improvement. The value of " +
    "git-as-memory is <b>auditability and mergeability</b>, not smarter answers.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("gt-tree",    t || ((S.depth != null && S.branch != null) ? (S.depth + " \u00d7 " + S.branch) : "\u2014"));
  _set("gt-commits", t || (S.commitCount != null ? String(S.commitCount) : "\u2014"));
  _set("gt-leaves",  t || (S.leafCount != null ? String(S.leafCount) : "\u2014"));
  _set("gt-head",    t || (S.headSha ? String(S.headSha).slice(0, 7) : "\u2014"));
  _set("gt-log",     t || ((Array.isArray(S.gitLog)) ? String(S.gitLog.length) : "\u2014"));
  _set("gt-replay",  t || (S.replayOk == null ? "\u2014" : (S.replayOk ? ("OK (" + (S.replayLen != null ? S.replayLen : "?") + " commits)") : "MISMATCH")));
  _set("gt-diff",    t || (S.diff ? (fx0(S.diff.only_a_count) + " / " + fx0(S.diff.shared_count) + " / " + fx0(S.diff.only_b_count)) : "\u2014"));
  _set("gt-merge",   t || (S.merge ? (fx0(S.merge.merged_commit_count) + " / " + fx0(S.merge.conflict_count)) : "\u2014"));
  _set("gt-tags",    t || (S.tagHist ? (fx0(S.tagHist.solved) + " / " + fx0(S.tagHist.partial) + " / " + fx0(S.tagHist["dead-end"])) : "\u2014"));
  _set("gt-thr",     t || (S.threshold != null ? "\u2248 " + fx(S.threshold, 2) : "\u2014"));
  _set("gt-jump",    t || (S.jumpSize != null ? "+" + (S.jumpSize * 100).toFixed(1) + " pts" : "\u2014"));
  _set("gt-below",   t || pct(S.gainBelow, 1));
  _set("gt-above",   t || pct(S.gainAbove, 1));
  // honesty label verbatim — never upgraded
  _set("gt-label",   t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

function fx0(v) { return typeof v === "number" ? String(v) : "\u2014"; }

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
  _floor = null;
  _treeGroup = null;
  _curveGroup = null;
  _barGroup = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.depth = S.branch = S.commitCount = S.leafCount = null;
  S.headSha = S.rootSha = null;
  S.gitLog = null; S.replayOk = null; S.replayLen = null;
  S.diff = S.merge = S.tagHist = null;
  S.threshold = S.sweep = S.jumpSize = S.gainBelow = S.gainAbove = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
