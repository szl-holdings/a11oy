// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/governance.js — AI GOVERNANCE / Assurance holographic surface (Dev5).
//
// Leader/technique modeled (we are MODELED ON, never claim to BE):
//   GUAC v1.0 (OpenSSF) — Graph for Understanding Artifact Composition
//   Sigstore / Rekor    — append-only hash-chained Merkle transparency log
//   SCITT (IETF)         — Transparent Statement -> Ledger Entry -> Merkle proof
//   Technique: 3D force-directed dependency knowledge graph + 3D Merkle hash-chain
//   tree + compliance crosswalk heatmap.
//
// DOCTRINE v11 (LOCKED): WIRE TO LIVE DATA, never fabricate. Every value on screen
// traces to a real a11oy endpoint and carries its honesty label read straight off the
// JSON.
//
// LIVE WIRING (2026-06-15): the original 5 assurance/forge routes (artifact /
// credential / compliance / attest / forge-ledger) are a PENDING backend (Forge mesh)
// and 404, so the tab read OFFLINE. This surface is now driven by the a11oy Restraint
// GOVERNANCE gate, which IS live (HTTP 200):
//   GET  /api/a11oy/v1/restraint/info       -> trust posture: doctrine lock, 6-rung
//                                              ladder spec, Λ floor, signed-receipts flag,
//                                              visible_codenames=0.
//   POST /api/a11oy/v1/restraint/evaluate    -> a LIVE governance gate decision over a
//                                              sample task: which ladder rung holds
//                                              (ALLOW/DESCEND), advisory Λ score, a signed
//                                              DSSE receipt, and a MODELED energy tie-in.
//   GET  /api/a11oy/v1/honest                -> git_sha + doctrine_lock for the build badge.
// The ladder/Λ/receipt verdict drives the Merkle/ledger/kill-switch/attestation/callout
// demos with REAL values; each value carries the honesty label (HEURISTIC/MODELED) read
// straight off the JSON. The legacy assurance routes are still polled (optional) and light
// up automatically if the Forge mesh ever returns 200, but the tab no longer depends on them.
//
// SURFACE CONTRACT (same as its 8 siblings): each live endpoint above is polled via
// ctx.live.poll (bound to _live = ctx.live in mount()); values are never hardcoded and
// carry the honest STRUCTURAL-ONLY placeholder label until the live poll confirms them.
//
// TEACHING POINT (doctrine): a SIGNATURE is NOT proof of safety — CVE-2026-45321
// (Mini Shai-Hulud): 84 @tanstack/* npm versions shipped VALID SLSA L3 / Sigstore
// provenance; provenance flagged ZERO; behaviour caught all 84. Λ = Conjecture 1
// (advisory governance, NOT proven trust / NOT proven safe).
//
// 0 runtime CDN: three via the page importmap (ctx.THREE); the SBOM force-graph reuses
// the repo-vendored 3d-force-graph UMD global at /vendor/3d-force-graph.min.js.
//
// CONTRACT: default-export { id, title, endpoints[], mount(ctx), unmount() }.

const ID = "governance";
const TITLE = "AI Governance · Assurance";

// LIVE governance routes (HTTP 200) — the trust posture + gate decision the tab renders.
const EP = {
  info:     "/api/a11oy/v1/restraint/info",       // trust posture: doctrine lock + ladder spec + Λ floor
  gate:     "/api/a11oy/v1/restraint/evaluate",   // LIVE gate decision (POST sample task) -> rung/Λ/receipt
  honest:   "/api/a11oy/v1/honest",               // git_sha + doctrine_lock for the build badge
};
// Optional PENDING-backend routes (Forge mesh). Polled but NOT required: 404 -> honest
// NO-LIVE-DATA badge; light up automatically if the mesh ever returns 200.
const EP_PENDING = {
  artifact:   "/api/a11oy/v1/assurance/artifact",   // artifact_behaviour_monitor.py
  credential: "/api/a11oy/v1/assurance/credential",  // content_credentials.py (C2PA)
};
// A representative governance task the live gate evaluates (demos 13/14: the ladder gate
// in action). Deterministic input -> deterministic rung/Λ/receipt, so the viz is stable.
const GATE_TASK = { task: "add a cache for these API responses", intensity: "full" };
const ENDPOINTS = [...Object.values(EP), ...Object.values(EP_PENDING)];

// Palette (matches the holographic shell tokens).
const C = {
  accent: 0x8a6bff, teal: 0x39d3c4, gold: 0xe8c074, red: 0xff6b6b,
  green: 0x2fd07a, gray: 0x8a97a3, blue: 0x6fb1ff, cream: 0xeef3f6,
};
// Honest framework-status colors (IMPLEMENTED/PARTIAL/ROADMAP) for the heatmap.
const STATUS_COLOR = { IMPLEMENTED: 0x2fd07a, PARTIAL: 0xe8c074, ROADMAP: 0x8a97a3 };

let _stage = null, _THREE = null, _label = null, _live = null;
let _root = null;                 // THREE.Group holding everything we add to the scene
let _handles = [];                // poll handles to stop on unmount
let _overlay = null, _graphPanel = null, _graph = null, _hud = {};
let _frameCb = null, _fgScript = null;
let _plain = false, _plainEl = null;  // "what this means" plain-language toggle
const _state = {};                // last meta per endpoint (for HUD)

// ---------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------
function el(tag, css, txt) {
  const e = document.createElement(tag);
  if (css) e.style.cssText = css;
  if (txt != null) e.textContent = txt;
  return e;
}
function disposeObj(o) {
  o.traverse?.((c) => {
    if (c.geometry) c.geometry.dispose?.();
    if (c.material) {
      const m = c.material;
      (Array.isArray(m) ? m : [m]).forEach((mm) => { mm.map?.dispose?.(); mm.dispose?.(); });
    }
  });
}

// ---------------------------------------------------------------------------
// mount
// ---------------------------------------------------------------------------
function mount(ctx) {
  _stage = ctx.stage; _THREE = ctx.THREE; _label = ctx.label; _live = ctx.live;
  const THREE = _THREE;
  _root = new THREE.Group();
  _stage.scene.add(_root);

  _buildOverlay(ctx);

  // --- the 7 in-scene scene demos (positioned around the estate) -----------
  const merkle = buildMerkleTree(THREE);          // Demo: Rekor-style 3D Merkle hash-chain tree
  merkle.position.set(-7.5, 0, 0);
  _root.add(merkle);

  const helix = buildAttestationHelix(THREE);     // Demo: attestation timeline helix
  helix.position.set(7.5, -1, 0);
  _root.add(helix);

  const heatmap = buildComplianceHeatmap(THREE);  // Demo: NIST/ISO/EU compliance heatmap (60/60/0)
  heatmap.position.set(0, 4.2, -3);
  _root.add(heatmap);

  const ledger = buildLedgerChain(THREE);          // Demo: Forge ledger hash-chain replay
  ledger.position.set(0, -4.4, 0);
  _root.add(ledger);

  const axes = buildAttestationAxes(THREE);        // Demo: 3-axis attestation (build/model/runtime)
  axes.position.set(7.0, 4.0, -1);
  _root.add(axes);

  const pq = buildPqNode(THREE);                   // Demo: PQ hybrid Ed25519+ML-DSA node
  pq.position.set(-7.5, 4.0, -1);
  _root.add(pq);

  const killSwitch = buildKillSwitch(THREE);       // Demo: kill-switch indicator
  killSwitch.position.set(0, 0, 6);
  _root.add(killSwitch);

  const callout = buildSigSafetyCallout(THREE);    // Demo: signature ≠ safety teaching callout
  callout.position.set(0, -8.2, 2);
  _root.add(callout);

  // doctrine billboards. The Merkle/ledger clusters render the LIVE ladder decision
  // (HEURISTIC rung detectors, off /restraint/evaluate); the crosswalk pillars render the
  // LIVE doctrine posture invariants (off /restraint/info). Labelled honestly per JSON.
  _root.add(_label.billboard(THREE, "HEURISTIC", { text: "Ladder gate (Merkle)", scale: 0.5, position: [-7.5, 4.4, 0] }));
  _root.add(_label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Attest helix", scale: 0.5, position: [7.5, 3.0, 0] }));
  _root.add(_label.billboard(THREE, "MEASURED", { text: "Doctrine posture", scale: 0.5, position: [0, 7.0, -3] }));

  this_registerFrame(THREE, { merkle, helix, heatmap, ledger, axes, pq, killSwitch, callout });

  // --- SBOM dependency force-graph (GUAC-style), reuses vendored ForceGraph3D
  _initForceGraph();

  // --- wire all 5 gap routes; each renders NO-LIVE-DATA honestly on 404 -----
  startPolls(ctx);

  return { id: ID, started: true };
}

// per-frame animation registered once with the stage.
function this_registerFrame(THREE, parts) {
  let t = 0;
  _frameCb = () => {
    t += 0.016;
    if (_root) _root.rotation.y = Math.sin(t * 0.08) * 0.06;
    parts.helix.rotation.y += 0.006;
    parts.merkle.rotation.y += 0.003;
    parts.ledger.rotation.y -= 0.004;
    // kill-switch pulse (armed=red glow throb; safe=steady green) — value set by poll
    const ks = parts.killSwitch.userData;
    if (ks.core) {
      const armed = !!ks.armed;
      const pulse = armed ? (0.5 + 0.5 * Math.sin(t * 6)) : 0.85;
      ks.core.material.emissiveIntensity = (armed ? 0.6 : 0.3) + pulse * (armed ? 0.8 : 0.1);
    }
    // PQ node: two interlocked rings (Ed25519 + ML-DSA) counter-rotate
    if (parts.pq.userData.ed) parts.pq.userData.ed.rotation.z += 0.01;
    if (parts.pq.userData.ml) parts.pq.userData.ml.rotation.x -= 0.012;
    // helix beads orbit on flowing
    (parts.helix.userData.beads || []).forEach((b, i) => {
      b.material.emissiveIntensity = 0.4 + 0.4 * Math.sin(t * 2 + i * 0.7);
    });
  };
  _stage.onFrame(_frameCb);
}

// ===========================================================================
// DEMOS — 3D scene objects (built to the engine shapes; live values overlaid)
// ===========================================================================

// Demo 1: Rekor/SCITT-style 3D Merkle hash-chain tree (TubeGeometry branches).
// forge ledger uses a LINEAR khipu chain (prev_hash/entry_hash, no merkle); the
// Rekor inclusion proof is a binary Merkle tree — we render the canonical Merkle
// structure and color leaves by signature freshness once /forge/ledger is live.
function buildMerkleTree(THREE) {
  const g = new THREE.Group(); g.userData.kind = "merkle";
  const leafMat = () => new THREE.MeshStandardMaterial({
    color: C.gray, emissive: C.gray, emissiveIntensity: 0.25, metalness: 0.4, roughness: 0.4,
  });
  const levels = 4;                      // 1 + 2 + 4 + 8 = 15 nodes
  const nodes = [];
  let y = 3.2;
  const spread = 4.6;
  const branchMat = new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 0.2, transparent: true, opacity: 0.55 });
  const placed = [];
  for (let lvl = 0; lvl < levels; lvl++) {
    const count = Math.pow(2, lvl);
    const row = [];
    const w = spread * (lvl / (levels - 1));
    for (let i = 0; i < count; i++) {
      const x = count === 1 ? 0 : (-w + (2 * w) * (i / (count - 1)));
      const isLeaf = lvl === levels - 1;
      const geo = new THREE.OctahedronGeometry(isLeaf ? 0.28 : 0.36, 0);
      const node = new THREE.Mesh(geo, leafMat());
      node.position.set(x, y - lvl * 1.7, 0);
      node.userData.leaf = isLeaf;
      g.add(node); row.push(node); nodes.push(node);
    }
    placed.push(row);
  }
  // connect parents -> children with tube branches
  for (let lvl = 0; lvl < levels - 1; lvl++) {
    placed[lvl].forEach((parent, pi) => {
      [2 * pi, 2 * pi + 1].forEach((ci) => {
        const child = placed[lvl + 1][ci];
        if (!child) return;
        const curve = new THREE.LineCurve3(parent.position.clone(), child.position.clone());
        const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 1, 0.03, 6, false), branchMat);
        g.add(tube);
      });
    });
  }
  g.userData.leaves = placed[levels - 1];
  g.userData.root = placed[0][0];
  g.userData.allNodes = nodes;
  return g;
}

// Demo 2: attestation timeline helix — SCITT-style. Each ring = a pipeline stage;
// beads = attestations (SLSA provenance, SBOM, test result) that lock into the ledger.
function buildAttestationHelix(THREE) {
  const g = new THREE.Group(); g.userData.kind = "helix";
  const turns = 3, perTurn = 12, n = turns * perTurn, R = 1.7, H = 6;
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / perTurn) * Math.PI * 2;
    const yy = -H / 2 + H * (i / n);
    pts.push(new THREE.Vector3(Math.cos(a) * R, yy, Math.sin(a) * R));
  }
  const curve = new THREE.CatmullRomCurve3(pts);
  const tube = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 200, 0.045, 8, false),
    new THREE.MeshStandardMaterial({ color: C.teal, emissive: C.teal, emissiveIntensity: 0.3, transparent: true, opacity: 0.7 }),
  );
  g.add(tube);
  const beads = [];
  const stageColors = [C.gold, C.teal, C.accent, C.blue];
  for (let i = 0; i < n; i += 3) {
    const p = curve.getPointAt(i / n);
    const bead = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 12, 12),
      new THREE.MeshStandardMaterial({ color: stageColors[(i / 3) % stageColors.length], emissive: stageColors[(i / 3) % stageColors.length], emissiveIntensity: 0.5 }),
    );
    bead.position.copy(p); g.add(bead); beads.push(bead);
  }
  g.userData.beads = beads;
  return g;
}

// Demo 3: NIST / ISO / EU compliance crosswalk heatmap (HONEST 60/60/0).
// Rows = controls (compliance.json), cols = the 3 frameworks. Cell color =
// IMPLEMENTED/PARTIAL/ROADMAP; bar height = framework pct_implemented. We seed
// it with the STRUCTURAL frame from compliance.json and replace with live cells
// when /assurance/compliance is 200.
function buildComplianceHeatmap(THREE) {
  const g = new THREE.Group(); g.userData.kind = "heatmap";
  const frameworks = ["NIST", "ISO", "EU"];
  const rows = 10, cols = 3, cw = 1.05, ch = 0.5;
  const cells = [];
  // STRUCTURAL seed mirroring compliance.json (NIST/ISO: 6 impl,3 part,1 road; EU: 0,9,1)
  const seed = {
    NIST: ["IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "PARTIAL", "PARTIAL", "PARTIAL", "ROADMAP"],
    ISO:  ["IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "PARTIAL", "PARTIAL", "PARTIAL", "ROADMAP"],
    EU:   ["PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "ROADMAP"],
  };
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const status = seed[frameworks[c]][r];
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(cw * 0.9, 0.12, ch * 0.9),
        new THREE.MeshStandardMaterial({ color: STATUS_COLOR[status], emissive: STATUS_COLOR[status], emissiveIntensity: 0.3, metalness: 0.2, roughness: 0.6 }),
      );
      mesh.position.set((c - 1) * cw, 0, (r - rows / 2) * ch);
      mesh.userData = { framework: frameworks[c], row: r };
      g.add(mesh); cells.push(mesh);
    }
  }
  // posture pillars — each maps to a load-bearing doctrine INVARIANT, set live from
  // /restraint/info (full height + green when the invariant holds, off the real JSON).
  // Seeded short/gray (STRUCTURAL-ONLY) until the live poll confirms; never pre-claimed.
  const INV_LABEL = { NIST: "0 runtime-CDN", ISO: "signed receipts", EU: "0 codenames" };
  const pillars = {};
  frameworks.forEach((f, c) => {
    const h = 0.05;
    const col = C.gray;
    const pil = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, h, 0.5),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.35, transparent: true, opacity: 0.85 }),
    );
    pil.position.set((c - 1) * cw, h / 2 + 0.2, (rows / 2) * ch + 0.9);
    g.add(pil); pillars[f] = pil;
    const bb = _label.billboard(THREE, "STRUCTURAL-ONLY", { text: INV_LABEL[f], scale: 0.32, position: [(c - 1) * cw, 1.4, (rows / 2) * ch + 0.9] });
    g.add(bb);
  });
  g.userData.cells = cells; g.userData.pillars = pillars; g.userData.frameworks = frameworks;
  return g;
}

// Demo 4: Forge ledger hash-chain replay — linear khipu chain (prev_hash/entry_hash).
// Genesis = 64 zeros; ring color (safe-auto/gated/forbidden) + decision (ALLOW/DENY/
// BLOCKED). Populated from /forge/ledger entries[]; kill_switch drives the indicator.
function buildLedgerChain(THREE) {
  const g = new THREE.Group(); g.userData.kind = "ledger";
  const n = 8, gap = 1.25;
  const blocks = [];
  for (let i = 0; i < n; i++) {
    const blk = new THREE.Mesh(
      new THREE.BoxGeometry(0.7, 0.7, 0.7),
      new THREE.MeshStandardMaterial({ color: C.gray, emissive: C.gray, emissiveIntensity: 0.25, metalness: 0.5, roughness: 0.4 }),
    );
    blk.position.set((i - (n - 1) / 2) * gap, 0, 0);
    g.add(blk); blocks.push(blk);
    if (i > 0) {
      const link = new THREE.Mesh(
        new THREE.CylinderGeometry(0.025, 0.025, gap - 0.7, 6),
        new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 0.3 }),
      );
      link.rotation.z = Math.PI / 2;
      link.position.set((i - (n - 1) / 2) * gap - gap / 2, 0, 0);
      g.add(link);
    }
  }
  // genesis marker (64 zeros)
  blocks[0].material.color.setHex(C.blue); blocks[0].material.emissive.setHex(C.blue);
  g.userData.blocks = blocks;
  return g;
}

// Demo 5: 3-axis attestation (build / model / runtime) — runtime_attestation.py.
// Three orthogonal axes; a bar grows along each present axis. trust_level rises
// NONE -> BUILD-ONLY -> BUILD+MODEL -> ALL-THREE-AXES. More axes = more STRUCTURE,
// NOT more safety (lambda_note).
function buildAttestationAxes(THREE) {
  const g = new THREE.Group(); g.userData.kind = "axes";
  const defs = [
    { name: "build", dir: [1, 0, 0], color: C.green },
    { name: "model", dir: [0, 1, 0], color: C.gold },
    { name: "runtime", dir: [0, 0, 1], color: C.teal },
  ];
  const bars = {};
  defs.forEach((d) => {
    const len = 1.6;
    const bar = new THREE.Mesh(
      new THREE.CylinderGeometry(0.06, 0.06, len, 8),
      new THREE.MeshStandardMaterial({ color: d.color, emissive: d.color, emissiveIntensity: 0.35, transparent: true, opacity: 0.45 }),
    );
    // orient cylinder (default +Y) along dir
    const v = new THREE.Vector3(...d.dir);
    bar.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v);
    bar.position.copy(v.clone().multiplyScalar(len / 2));
    g.add(bar); bars[d.name] = bar;
  });
  const hub = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 16, 16),
    new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 0.4 }),
  );
  g.add(hub);
  g.userData.bars = bars;
  return g;
}

// Demo 6: PQ hybrid-signature node — pq_signing.py (Ed25519 + ML-DSA, FIPS-204
// ML-DSA-65). Two interlocked rings; hybrid policy = BOTH must verify. ML-DSA is
// a STRUCTURAL STUB in-sandbox (real:false) until the real PQ signer lands -> gray.
function buildPqNode(THREE) {
  const g = new THREE.Group(); g.userData.kind = "pq";
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.45, 0),
    new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 0.4, metalness: 0.5, roughness: 0.3 }),
  );
  g.add(core);
  const ed = new THREE.Mesh(
    new THREE.TorusGeometry(0.95, 0.05, 8, 40),
    new THREE.MeshStandardMaterial({ color: C.green, emissive: C.green, emissiveIntensity: 0.45 }),  // Ed25519 = real
  );
  g.add(ed);
  const ml = new THREE.Mesh(
    new THREE.TorusGeometry(0.95, 0.05, 8, 40),
    new THREE.MeshStandardMaterial({ color: C.gray, emissive: C.gray, emissiveIntensity: 0.3 }),       // ML-DSA = STUB until real
  );
  ml.rotation.x = Math.PI / 2;
  g.add(ml);
  g.userData.core = core; g.userData.ed = ed; g.userData.ml = ml;
  return g;
}

// Demo 7: kill-switch indicator — forge_governance.py kill_switch bool. Armed
// (true) -> gated actions forced to DENY, throbbing red; safe (false) -> steady green.
function buildKillSwitch(THREE) {
  const g = new THREE.Group(); g.userData.kind = "killswitch";
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.7, 0.08, 10, 48),
    new THREE.MeshStandardMaterial({ color: C.gray, emissive: C.gray, emissiveIntensity: 0.3 }),
  );
  g.add(ring);
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 24, 24),
    new THREE.MeshStandardMaterial({ color: C.green, emissive: C.green, emissiveIntensity: 0.4, metalness: 0.3, roughness: 0.4 }),
  );
  g.add(core);
  g.userData.core = core; g.userData.ring = ring; g.userData.armed = false;
  return g;
}

// Demo 8: signature ≠ safety teaching callout (CVE-2026-45321). A green "valid
// signature" badge sitting ON a red behavioural-anomaly body — the whole point:
// a valid signature does NOT make the artifact safe.
function buildSigSafetyCallout(THREE) {
  const g = new THREE.Group(); g.userData.kind = "callout";
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(1.4, 1.0, 1.0),
    new THREE.MeshStandardMaterial({ color: C.red, emissive: C.red, emissiveIntensity: 0.35, transparent: true, opacity: 0.7 }),
  );
  g.add(body);
  // a green "signature valid" seal stuck on the malicious body
  const seal = new THREE.Mesh(
    new THREE.CylinderGeometry(0.32, 0.32, 0.1, 24),
    new THREE.MeshStandardMaterial({ color: C.green, emissive: C.green, emissiveIntensity: 0.5 }),
  );
  seal.rotation.x = Math.PI / 2; seal.position.set(0, 0, 0.55);
  g.add(seal);
  g.add(_label.billboard(THREE, "STRUCTURAL-ONLY", { text: "signature ≠ safety · CVE-2026-45321", scale: 0.4, position: [0, 1.0, 0] }));
  return g;
}

// ===========================================================================
// SBOM dependency knowledge graph (GUAC-style) — reuses vendored ForceGraph3D.
// Demo 9. Renders into its own DOM panel (the UMD lib owns a three.js canvas).
// Seeded STRUCTURAL; replaced with real nodes/edges when /assurance/artifact 200s.
// ===========================================================================
function _seedSbom() {
  // STRUCTURAL placeholder graph (clearly labelled). Real SBOM arrives via the
  // artifact route's dependency closure + behavioural verdict per node.
  const root = { id: "szl/agentic-pinn-solver", group: "root", status: "ROADMAP", val: 8 };
  const nodes = [root];
  const links = [];
  const deps = ["numpy", "fastapi", "starlette", "cryptography", "uvicorn", "pydantic", "ed25519", "rekor-client"];
  deps.forEach((d, i) => {
    const node = { id: d, group: "dep", status: "ROADMAP", val: 3 };
    nodes.push(node);
    links.push({ source: root.id, target: d, rel: "depends-on" });
    if (i % 3 === 0) {
      const sub = { id: d + "·sub", group: "transitive", status: "ROADMAP", val: 2 };
      nodes.push(sub);
      links.push({ source: d, target: sub.id, rel: "depends-on" });
    }
  });
  return { nodes, links };
}

function _initForceGraph() {
  if (!_graphPanel) return;
  const ForceGraph3D = (typeof window !== "undefined") && window.ForceGraph3D;
  if (!ForceGraph3D) {
    // vendored lib not yet on the page — inject it same-origin (0 CDN), then build.
    if (!_fgScript) {
      _fgScript = el("script");
      _fgScript.src = "/vendor/3d-force-graph.min.js";
      _fgScript.onload = () => { try { _buildForceGraph(); } catch (_) {} };
      _fgScript.onerror = () => { if (_hud.sbom) _hud.sbom.textContent = "SBOM graph: vendored lib unavailable"; };
      document.head.appendChild(_fgScript);
    }
    return;
  }
  _buildForceGraph();
}

function _buildForceGraph() {
  const ForceGraph3D = window.ForceGraph3D;
  if (!ForceGraph3D || !_graphPanel || _graph) return;
  const data = _seedSbom();
  _graph = ForceGraph3D()(_graphPanel)
    .backgroundColor("rgba(5,7,13,0)")
    .graphData(data)
    .nodeLabel((n) => `${n.id} · ${n.status}`)
    .nodeColor((n) => "#" + (STATUS_COLOR[n.status] || C.gray).toString(16).padStart(6, "0"))
    .nodeVal((n) => n.val || 3)
    .nodeOpacity(0.92)
    .linkColor(() => "rgba(138,107,255,0.4)")
    .linkDirectionalParticles(1)
    .linkDirectionalParticleSpeed(0.006)
    .width(_graphPanel.clientWidth || 360)
    .height(_graphPanel.clientHeight || 240)
    .showNavInfo(false);
}

// update the SBOM graph from a live /assurance/artifact verdict (real shape).
function _updateSbomFromArtifact(json) {
  if (!_graph) return;
  // The artifact route returns a behavioural verdict (assess_live_certificate /
  // assess_artifact). When a full dependency closure is present we render it; else
  // we color the single certified artifact node by its verdict.
  const verdict = json.behavioural_verdict || json.verdict;
  const vColor = verdict === "ALLOW" ? "PARTIAL" : (verdict === "DENY" ? null : "ROADMAP");
  const data = _graph.graphData();
  if (data && data.nodes && data.nodes.length) {
    data.nodes.forEach((n) => {
      if (n.group === "root") {
        // DENY -> red; ALLOW -> amber (PARTIAL, never green: signature ≠ safety);
        n.status = vColor || "DENY";
        n._deny = verdict === "DENY";
      }
    });
    _graph.nodeColor((n) => n._deny ? "#ff6b6b" : ("#" + (STATUS_COLOR[n.status] || C.gray).toString(16).padStart(6, "0")));
    _graph.refresh && _graph.refresh();
  }
}

// ===========================================================================
// OVERLAY HUD — badges per route + legend + teaching callout + SBOM panel
// ===========================================================================
function _buildOverlay(ctx) {
  _overlay = el("div", "position:absolute;left:14px;top:14px;z-index:5;display:flex;flex-direction:column;gap:9px;max-width:min(94%,440px);pointer-events:none");

  const head = el("div", "font:600 14px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px", TITLE);
  _overlay.appendChild(head);

  const sub = el("div", "font:10.5px ui-monospace,Menlo,monospace;color:#9fb1bf;line-height:1.5",
    "modeled on GUAC v1.0 · Sigstore/Rekor · SCITT — knowledge graph + Merkle hash-chain + crosswalk");
  _overlay.appendChild(sub);

  // per-route live badges: LIVE routes first (drive the tab), then the PENDING ones.
  const badgeWrap = el("div", "display:flex;flex-direction:column;gap:5px;pointer-events:auto");
  _hud.badges = {};
  const ROUTE_LABEL = {
    info: "restraint posture (info)", gate: "governance gate (evaluate)",
    honest: "build provenance (honest)",
    artifact: "artifact monitor (pending mesh)", credential: "C2PA credential (pending mesh)",
  };
  const ALL_BADGE_ROUTES = { ...EP, ...EP_PENDING };
  Object.keys(ALL_BADGE_ROUTES).forEach((k) => {
    const row = el("div", "display:flex;align-items:center;gap:8px");
    const tag = el("span", "font:10px ui-monospace,monospace;color:#7d8a96;min-width:182px", ROUTE_LABEL[k]);
    const badge = _live.createBadge();
    _hud.badges[k] = badge;
    row.appendChild(tag); row.appendChild(badge.el);
    badgeWrap.appendChild(row);
  });
  _overlay.appendChild(badgeWrap);

  // LIVE governance posture + gate readout (filled from /restraint/info + /evaluate)
  _hud.posture = el("div", "font:10px ui-monospace,Menlo,monospace;color:#7d8a96;line-height:1.5;pointer-events:auto", "posture: awaiting /restraint/info…");
  _overlay.appendChild(_hud.posture);

  _hud.gate = el("div",
    "pointer-events:auto;margin-top:1px;padding:7px 9px;border:1px solid #2a2440;border-radius:8px;" +
    "background:rgba(138,107,255,.07);color:#cdbdf2;font:10px ui-monospace,Menlo,monospace;line-height:1.55");
  _hud.gate.textContent = "governance gate: awaiting /restraint/evaluate…";
  _overlay.appendChild(_hud.gate);

  _hud.honest = el("div", "font:10px ui-monospace,Menlo,monospace;color:#7d8a96;line-height:1.5;pointer-events:auto", "build: awaiting /honest…");
  _overlay.appendChild(_hud.honest);

  // honesty legend (doctrine chips)
  const legend = _label.legend(); legend.style.opacity = "0.9"; legend.style.pointerEvents = "auto";
  _overlay.appendChild(legend);

  // teaching callout (doctrine): signature ≠ safety
  const teach = el("div",
    "pointer-events:auto;margin-top:2px;padding:8px 10px;border:1px solid #3a2330;border-radius:8px;" +
    "background:rgba(255,107,107,.08);color:#ffb4b4;font:10.5px ui-monospace,Menlo,monospace;line-height:1.55");
  teach.innerHTML =
    "<b style='color:#ff8f8f'>A signature is NOT proof of safety.</b><br>" +
    "CVE-2026-45321 (Mini Shai-Hulud): 84 @tanstack/* npm versions shipped <i>valid</i> " +
    "SLSA L3 / Sigstore provenance. Provenance flagged 0; behaviour caught all 84. " +
    "<span style='color:#9fb1bf'>Λ = Conjecture 1 — advisory governance, NOT proven trust.</span>";
  _overlay.appendChild(teach);

  // status / scope line (filled live)
  _hud.status = el("div", "font:10px ui-monospace,monospace;color:#7d8a96;line-height:1.5;pointer-events:auto");
  _hud.status.textContent = "wiring live governance gate (restraint info + evaluate + honest)…";
  _overlay.appendChild(_hud.status);

  // "what this means" plain-language toggle (matches the research surfaces).
  const pl = el("button", "pointer-events:auto;font:11px ui-monospace,monospace;padding:5px 11px;" +
    "border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content;margin-top:2px");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  _overlay.appendChild(pl);
  _plainEl = el("div", "pointer-events:auto;font-size:10.5px;color:#c9d6df;line-height:1.55;" +
    "border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none;margin-top:2px");
  _overlay.appendChild(_plainEl);

  // SBOM graph panel (bottom-right), hosts the GUAC-style force-directed graph
  _graphPanel = el("div",
    "position:absolute;right:14px;bottom:42px;width:min(40vw,380px);height:min(34vh,260px);z-index:5;" +
    "border:1px solid #1b2734;border-radius:10px;background:rgba(7,13,21,.55);overflow:hidden;pointer-events:auto");
  const gh = el("div", "position:absolute;left:8px;top:6px;z-index:2;font:10px ui-monospace,monospace;color:#9fb1bf", "SBOM dependency graph · GUAC-style");
  _hud.sbom = el("div", "position:absolute;left:8px;bottom:6px;z-index:2;font:9.5px ui-monospace,monospace;color:#7d8a96", "STRUCTURAL-ONLY · awaiting /assurance/artifact");
  _graphPanel.appendChild(gh); _graphPanel.appendChild(_hud.sbom);

  const host = ctx.container || document.body;
  host.appendChild(_overlay);
  host.appendChild(_graphPanel);
}

function _applyPlain() {
  const pd = _plainEl;
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  pd.innerHTML =
    "<b>What this means:</b> This surface shows the app’s own <b>governance gate</b> in action. " +
    "Before an AI action runs, it is checked against a doctrine ‘restraint ladder’ that decides " +
    "whether to <b>allow</b> the action or <b>descend</b> to a safer, more restricted rung. Here we " +
    "run a real sample task through that live gate and show which rung held, an advisory <b>Λ</b> " +
    "score, and a cryptographically <b>signed receipt</b> of the decision. The key honesty point, " +
    "shown in red: a valid <b>signature is not proof of safety</b> — a real supply-chain attack " +
    "(CVE-2026-45321) shipped 84 packages with perfectly valid provenance, and only " +
    "behaviour-analysis caught them. So Λ is labelled a <b>conjecture</b> and advisory governance, " +
    "never ‘proven safe’. The dependency graph and compliance grid below trace to live endpoints, " +
    "or show <b>NO-LIVE-DATA</b> when a backend is still pending — never a fabricated pass.";
}

// ===========================================================================
// LIVE POLLS — wire each gap route; render honest state; light up on 200.
// ===========================================================================
function startPolls(ctx) {
  // 1) restraint posture (LIVE) -> doctrine lock, 6-rung ladder spec, Λ floor, codenames=0.
  //    _live is ctx.live (aliased in mount()); the surface contract idiom is ctx.live.poll.
  _handles.push(_live.poll(EP.info, 15000, (json, meta) => {
    _state.info = meta;
    _applyPosture(json);
  }, { badge: _hud.badges.info }));

  // 2) governance gate (LIVE, POST) -> a real ladder decision over GATE_TASK: which rung
  //    holds, advisory Λ, signed DSSE receipt, MODELED energy tie-in. Drives the
  //    Merkle/ledger/kill-switch/attestation/callout demos with real values.
  _handles.push(_live.poll(EP.gate, 12000, (json, meta) => {
    _state.gate = meta;
    _applyGate(json);
  }, {
    badge: _hud.badges.gate,
    fetchInit: {
      method: "POST",
      headers: { "content-type": "application/json", "accept": "application/json" },
      body: JSON.stringify(GATE_TASK),
    },
  }));

  // 3) build provenance (LIVE) -> git_sha + doctrine_lock badge.
  _handles.push(_live.poll(EP.honest, 20000, (json, meta) => {
    _state.honest = meta;
    _applyHonest(json);
  }, { badge: _hud.badges.honest }));

  // 4/5) PENDING-backend assurance routes (Forge mesh). Optional: 404 -> honest
  //    NO-LIVE-DATA badge; light up the SBOM/callout automatically if they ever 200.
  _handles.push(_live.poll(EP_PENDING.artifact, 9000, (json, meta) => {
    _state.artifact = meta;
    _updateSbomFromArtifact(json);
    const v = json.behavioural_verdict || json.verdict;
    if (v && _hud.sbom) {
      const safe = json.signature_alone_is_safety; // doctrine invariant: always false
      _hud.sbom.textContent = `verdict ${v} · sig==safety:${safe === undefined ? "?" : safe} · ${json.fired_monitors ? json.fired_monitors.length : 0} fired`;
    }
  }, { badge: _hud.badges.artifact }));

  _handles.push(_live.poll(EP_PENDING.credential, 11000, (json, meta) => {
    _state.credential = meta;
    const hint = json.trust_hint || (json.active_manifest && json.active_manifest.labels && json.active_manifest.labels.trust);
    const callout = _root && _root.children.find((c) => c.userData && c.userData.kind === "callout");
    if (callout) {
      const seal = callout.children.find((c) => c.geometry && c.geometry.type === "CylinderGeometry");
      if (seal) {
        const col = hint === "TAMPERED" ? C.red : (hint === "C2PA_TRUST_LIST" ? C.green : C.gold);
        seal.material.color.setHex(col); seal.material.emissive.setHex(col);
      }
    }
  }, { badge: _hud.badges.credential }));

  // roll a compact status line as states change
  _refreshStatus();
  const si = setInterval(_refreshStatus, 2000);
  _handles.push({ stop: () => clearInterval(si) });
}

// --- LIVE posture: /restraint/info -> doctrine lock + ladder spec + Λ floor ----------
function _applyPosture(json) {
  const doc = json.doctrine || {};
  // resize the compliance pillars to the REAL doctrine posture rather than a seed:
  // visible_codenames is an enforced-0 invariant; signed_receipts a boolean; runtime_cdn 0.
  // We map the three "framework" pillars to the three load-bearing doctrine invariants so
  // the heatmap reads a real, labelled posture (MEASURED off the live JSON).
  const heatmap = _root && _root.children.find((c) => c.userData && c.userData.kind === "heatmap");
  if (heatmap && heatmap.userData.pillars) {
    const inv = [
      { key: "NIST", ok: doc.runtime_cdn === 0, txt: "0 CDN" },
      { key: "ISO", ok: doc.signed_receipts === true, txt: "signed" },
      { key: "EU", ok: (doc.visible_codenames === 0), txt: "0 codename" },
    ];
    inv.forEach(({ key, ok }) => {
      const pil = heatmap.userData.pillars[key];
      if (!pil) return;
      const h = ok ? 3.5 : 0.05;
      pil.scale.y = h / pil.geometry.parameters.height;
      pil.position.y = h / 2 + 0.2;
      const col = ok ? C.green : C.gray;
      pil.material.color.setHex(col); pil.material.emissive.setHex(col);
    });
  }
  if (_hud.posture) {
    const ladderN = Array.isArray(json.ladder) ? json.ladder.length : "?";
    _hud.posture.textContent =
      `posture: doctrine ${doc.version || "?"} · LOCKED ${doc.locked ?? "?"} · ${ladderN}-rung ladder · ` +
      `Λ ${doc.lambda ? "floor<1.0" : "?"} · signed-receipts ${doc.signed_receipts ? "ON" : "off"} · ` +
      `runtime-CDN ${doc.runtime_cdn ?? "?"} · visible-codenames ${doc.visible_codenames ?? "?"}`;
    _hud.posture.style.color = "#39d3c4";
  }
}

// --- LIVE gate: /restraint/evaluate -> rung decision + Λ + DSSE receipt + energy -------
function _applyGate(json) {
  const trail = Array.isArray(json.ladder_trail) ? json.ladder_trail : [];
  const stopped = typeof json.stopped_at_rung === "number" ? json.stopped_at_rung : null;
  const lambdaScore = json.lambda_score && typeof json.lambda_score.lambda === "number"
    ? json.lambda_score.lambda : null;
  const label = json.label || _live.readHonestyLabel(json) || null;

  // Merkle tree: color leaves by which rung held (the held rung = green, descended = amber,
  // not-yet-reached = gray). Honest structural map of the ladder decision.
  const merkle = _root && _root.children.find((c) => c.userData && c.userData.kind === "merkle");
  if (merkle && Array.isArray(merkle.userData.leaves)) {
    merkle.userData.leaves.forEach((leaf, i) => {
      let col = C.gray;
      const t = trail[i];
      if (t) col = t.held ? C.green : C.gold;
      leaf.material.color.setHex(col); leaf.material.emissive.setHex(col);
    });
    if (merkle.userData.root) {
      merkle.userData.root.material.color.setHex(C.blue);
      merkle.userData.root.material.emissive.setHex(C.blue);
    }
  }

  // Ledger chain: each block = a ladder rung in the trail; held rung = green (ALLOW here),
  // descended rungs = amber. Genesis stays blue. Real per-rung decision, not a seed.
  const ledger = _root && _root.children.find((c) => c.userData && c.userData.kind === "ledger");
  if (ledger && Array.isArray(ledger.userData.blocks)) {
    ledger.userData.blocks.forEach((blk, i) => {
      if (i === 0) return; // genesis blue
      const t = trail[i - 1];
      let col = C.gray;
      if (t) col = t.held ? C.green : C.gold;
      blk.material.color.setHex(col); blk.material.emissive.setHex(col);
    });
  }

  // Kill-switch: a governance gate decision is advisory (Λ kept < 1.0). Armed (red) iff the
  // advisory Λ breaches the floor; safe (green) when Λ < 1.0. Real value off the JSON.
  const killSwitch = _root && _root.children.find((c) => c.userData && c.userData.kind === "killswitch");
  if (killSwitch && lambdaScore != null) {
    const armed = lambdaScore >= 1.0;
    killSwitch.userData.armed = armed;
    const col = armed ? C.red : C.green;
    killSwitch.userData.core.material.color.setHex(col);
    killSwitch.userData.core.material.emissive.setHex(col);
  }

  // Attestation axes: a SIGNED DSSE receipt present -> the build axis is attested; the gate
  // ran in-runtime -> runtime axis present. model axis stays dim (no model attestation here).
  const hasReceipt = !!(json.signed_receipt && json.signed_receipt.signatures);
  const axes = _root && _root.children.find((c) => c.userData && c.userData.kind === "axes");
  if (axes && axes.userData.bars) {
    const present = { build: hasReceipt, model: false, runtime: true };
    Object.entries(present).forEach(([name, on]) => {
      const bar = axes.userData.bars[name];
      if (!bar) return;
      bar.material.opacity = on ? 0.95 : 0.3;
      bar.material.emissiveIntensity = on ? 0.55 : 0.2;
    });
  }

  // sig≠safety callout seal: a valid signed receipt is NOT proof of safety (doctrine). Keep
  // the seal AMBER even when the receipt verifies — a green seal would over-claim safety.
  const callout = _root && _root.children.find((c) => c.userData && c.userData.kind === "callout");
  if (callout) {
    const seal = callout.children.find((c) => c.geometry && c.geometry.type === "CylinderGeometry");
    if (seal) {
      const col = hasReceipt ? C.gold : C.gray; // signed -> amber (advisory), never green
      seal.material.color.setHex(col); seal.material.emissive.setHex(col);
    }
  }

  // HUD gate line — real rung + Λ + energy (MODELED), each labelled off the JSON.
  if (_hud.gate) {
    const energy = json.energy_tiein || {};
    const saved = json.lines_saved_estimate || {};
    _hud.gate.innerHTML =
      `<b style="color:#c9b8ff">gate</b> rung ${stopped ?? "?"}/${json.rung_name ? json.rung_name : "?"} ` +
      `→ <span style="color:#9fe6c7">${json.answer ? String(json.answer).slice(0, 40) : "—"}</span><br>` +
      `Λ ${lambdaScore != null ? lambdaScore.toFixed(3) : "?"} (advisory, &lt;1.0) · ` +
      `label <span style="color:#e8c074">${label || "?"}</span> · ` +
      `receipt ${hasReceipt ? "DSSE-signed" : "—"}<br>` +
      `energy ${energy.joules_saved_modeled != null ? energy.joules_saved_modeled + "J" : "—"} / ` +
      `${energy.tokens_saved_modeled != null ? energy.tokens_saved_modeled + " tok" : "—"} ` +
      `<span style="color:#7d8a96">[${energy.label || "MODELED"}]</span> · ` +
      `${saved.lines_saved_modeled != null ? saved.lines_saved_modeled + " LOC saved" : ""}`;
  }
}

// --- LIVE build provenance: /honest -> git_sha + doctrine_lock badge -------------------
function _applyHonest(json) {
  if (!_hud.honest) return;
  const sha = json.git_sha || (json.honest_labels && json.honest_labels.git_sha) || "?";
  const lock = json.doctrine_lock || (json.honest_labels && json.honest_labels.doctrine_lock) || "?";
  _hud.honest.textContent = `build ${String(sha).slice(0, 8)} · doctrine ${lock}`;
  _hud.honest.style.color = "#9fb1bf";
}

function _refreshStatus() {
  if (!_hud.status) return;
  // The tab is LIVE when the governance-gate routes (info/gate/honest) are live; the two
  // PENDING assurance routes are reported separately and honestly when still 404.
  const liveCore = Object.keys(EP).filter((k) => _state[k] && _state[k].state === "live");
  const pendingMissing = Object.keys(EP_PENDING).filter((k) => _state[k] && (_state[k].state === "missing" || _state[k].state === "error"));
  if (liveCore.length === 0) {
    _hud.status.textContent = "connecting to live governance gate (restraint info + evaluate + honest)…";
    _hud.status.style.color = "#7d8a96";
  } else {
    const pend = pendingMissing.length
      ? ` · ${pendingMissing.length} assurance route(s) NO-LIVE-DATA (Forge mesh pending)`
      : "";
    _hud.status.textContent = `LIVE governance gate: ${liveCore.join(", ")}${pend}`;
    _hud.status.style.color = "#39d3c4";
  }
}

// ---------------------------------------------------------------------------
// unmount
// ---------------------------------------------------------------------------
function unmount() {
  _handles.forEach((h) => { try { h.stop && h.stop(); } catch (_) {} });
  _handles = [];
  try { if (_frameCb && _stage && _stage.offFrame) _stage.offFrame(_frameCb); } catch (_) {}
  _frameCb = null;
  try { if (_graph && _graph._destructor) _graph._destructor(); } catch (_) {}
  _graph = null;
  try { if (_root && _stage) { disposeObj(_root); _stage.scene.remove(_root); } } catch (_) {}
  _root = null;
  [_overlay, _graphPanel].forEach((n) => { try { if (n && n.parentNode) n.parentNode.removeChild(n); } catch (_) {} });
  _overlay = null; _graphPanel = null; _hud = {}; _plain = false; _plainEl = null;
  _stage = null; _THREE = null; _label = null; _live = null;
  for (const k in _state) delete _state[k];
}

export default { id: ID, title: TITLE, endpoints: ENDPOINTS, mount, unmount };
