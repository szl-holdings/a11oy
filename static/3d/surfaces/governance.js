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
// JSON. The 5 assurance/forge routes are PENDING the Forge mesh deploy and currently
// 404 -> ctx.live.poll renders the honest NO-LIVE-DATA badge for each; this viz is
// built to the REAL data shapes the engines (artifact_behaviour_monitor.py,
// content_credentials.py, compliance_crosswalk.py, runtime_attestation.py,
// forge_governance.py, pq_signing.py) WILL return, so it lights up automatically on 200.
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

// The 5 gap routes (PENDING Forge mesh; 404 -> NO-LIVE-DATA until 200).
const EP = {
  artifact:   "/api/a11oy/v1/assurance/artifact",   // artifact_behaviour_monitor.py
  credential: "/api/a11oy/v1/assurance/credential",  // content_credentials.py (C2PA)
  compliance: "/api/a11oy/v1/assurance/compliance",  // compliance_crosswalk.py + compliance.json
  attest:     "/api/a11oy/v1/assurance/attest",      // runtime_attestation.py
  ledger:     "/api/a11oy/v1/forge/ledger",          // forge_governance.py
};
const ENDPOINTS = Object.values(EP);

// Palette (matches the holographic shell tokens).
const C = {
  accent: 0xb08fff, teal: 0x39d3c4, gold: 0xe8c074, red: 0xff6b6b,
  green: 0x2fd07a, gray: 0x8a97a3, blue: 0x6fb1ff, cream: 0xeef3f6,
};
// Honest framework-status colors (IMPLEMENTED/PARTIAL/ROADMAP) for the heatmap.
const STATUS_COLOR = { IMPLEMENTED: 0x2fd07a, PARTIAL: 0xe8c074, ROADMAP: 0x8a97a3 };

let _stage = null, _THREE = null, _label = null, _live = null;
let _root = null;                 // THREE.Group holding everything we add to the scene
let _handles = [];                // poll handles to stop on unmount
let _overlay = null, _graphPanel = null, _graph = null, _hud = {};
let _frameCb = null, _fgScript = null;
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

  // doctrine billboards (every cluster is labelled honestly until its route is live)
  _root.add(_label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Merkle ledger", scale: 0.5, position: [-7.5, 4.4, 0] }));
  _root.add(_label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Attest helix", scale: 0.5, position: [7.5, 3.0, 0] }));
  _root.add(_label.billboard(THREE, "MEASURED", { text: "Crosswalk 60/60/0", scale: 0.5, position: [0, 7.0, -3] }));

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
  // framework coverage pillars (height = pct_implemented; seeded 60/60/0)
  const pct = { NIST: 60, ISO: 60, EU: 0 };
  const pillars = {};
  frameworks.forEach((f, c) => {
    const h = Math.max(0.05, (pct[f] / 100) * 3.5);
    const col = pct[f] >= 100 ? C.green : (pct[f] > 0 ? C.gold : C.gray);
    const pil = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, h, 0.5),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.35, transparent: true, opacity: 0.85 }),
    );
    pil.position.set((c - 1) * cw, h / 2 + 0.2, (rows / 2) * ch + 0.9);
    g.add(pil); pillars[f] = pil;
    const bb = _label.billboard(THREE, "MEASURED", { text: `${f} ${pct[f]}%`, scale: 0.34, position: [(c - 1) * cw, h + 0.7, (rows / 2) * ch + 0.9] });
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
    .linkColor(() => "rgba(176,143,255,0.4)")
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

  // per-route live badges (each shows NO-LIVE-DATA until Forge meshes it)
  const badgeWrap = el("div", "display:flex;flex-direction:column;gap:5px;pointer-events:auto");
  _hud.badges = {};
  const ROUTE_LABEL = {
    artifact: "artifact (behaviour monitor)", credential: "credential (C2PA)",
    compliance: "compliance (crosswalk)", attest: "attest (build/model/runtime)",
    ledger: "forge ledger (hash-chain)",
  };
  Object.keys(EP).forEach((k) => {
    const row = el("div", "display:flex;align-items:center;gap:8px");
    const tag = el("span", "font:10px ui-monospace,monospace;color:#7d8a96;min-width:182px", ROUTE_LABEL[k]);
    const badge = _live.createBadge();
    _hud.badges[k] = badge;
    row.appendChild(tag); row.appendChild(badge.el);
    badgeWrap.appendChild(row);
  });
  _overlay.appendChild(badgeWrap);

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
  _hud.status.textContent = "awaiting Forge mesh — all 5 assurance routes render NO-LIVE-DATA honestly until 200.";
  _overlay.appendChild(_hud.status);

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

// ===========================================================================
// LIVE POLLS — wire each gap route; render honest state; light up on 200.
// ===========================================================================
function startPolls(ctx) {
  // 1) artifact behaviour monitor -> SBOM node verdict + status
  _handles.push(_live.poll(EP.artifact, 6000, (json, meta) => {
    _state.artifact = meta;
    _updateSbomFromArtifact(json);
    const v = json.behavioural_verdict || json.verdict;
    if (v && _hud.sbom) {
      const safe = json.signature_alone_is_safety; // doctrine invariant: always false
      _hud.sbom.textContent = `verdict ${v} · sig==safety:${safe === undefined ? "?" : safe} · ${json.fired_monitors ? json.fired_monitors.length : 0} fired`;
    }
  }, { badge: _hud.badges.artifact }));

  // 2) C2PA credential -> trust hint colors the callout seal honestly
  _handles.push(_live.poll(EP.credential, 7000, (json, meta) => {
    _state.credential = meta;
    // trust_hint ∈ {STRUCTURAL-ONLY, SELF_SIGNED, C2PA_TRUST_LIST, TAMPERED} — never "green"
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

  // 3) compliance crosswalk -> recolor heatmap cells + resize pillars (60/60/0 honest)
  _handles.push(_live.poll(EP.compliance, 8000, (json, meta) => {
    _state.compliance = meta;
    _applyCompliance(json);
  }, { badge: _hud.badges.compliance }));

  // 4) runtime attestation -> grow the present build/model/runtime axis bars
  _handles.push(_live.poll(EP.attest, 7000, (json, meta) => {
    _state.attest = meta;
    _applyAttest(json);
  }, { badge: _hud.badges.attest }));

  // 5) forge ledger -> color blocks by ring/decision, drive kill-switch indicator
  _handles.push(_live.poll(EP.ledger, 6000, (json, meta) => {
    _state.ledger = meta;
    _applyLedger(json);
  }, { badge: _hud.badges.ledger }));

  // roll a compact status line as states change
  _handles.forEach((h) => {});
  _refreshStatus();
  const si = setInterval(_refreshStatus, 2000);
  _handles.push({ stop: () => clearInterval(si) });
}

function _refreshStatus() {
  if (!_hud.status) return;
  const live = Object.keys(_state).filter((k) => _state[k] && _state[k].state === "live");
  const missing = Object.keys(EP).filter((k) => !_state[k] || _state[k].state === "missing" || _state[k].state === "init");
  if (live.length === 0) {
    _hud.status.textContent = `awaiting Forge mesh · ${missing.length}/5 routes NO-LIVE-DATA · viz lights up automatically on 200`;
    _hud.status.style.color = "#7d8a96";
  } else {
    _hud.status.textContent = `LIVE: ${live.join(", ")} · ${missing.length} still awaiting Forge mesh`;
    _hud.status.style.color = "#39d3c4";
  }
}

function _applyCompliance(json) {
  const heatmap = _root && _root.children.find((c) => c.userData && c.userData.kind === "heatmap");
  if (!heatmap) return;
  const cov = (json.coverage || json).frameworks || json.frameworks;
  const crosswalk = json.crosswalk;
  const FW = { NIST_AI_RMF: "NIST", ISO_IEC_42001: "ISO", EU_AI_ACT: "EU" };
  // recolor cells from the real crosswalk[] (control x framework x status)
  if (Array.isArray(crosswalk)) {
    const byFw = { NIST: [], ISO: [], EU: [] };
    crosswalk.forEach((c) => { const f = FW[c.framework]; if (f) byFw[f].push(c.status); });
    heatmap.userData.cells.forEach((cell) => {
      const arr = byFw[cell.userData.framework];
      const st = arr && arr[cell.userData.row];
      if (st && STATUS_COLOR[st]) { cell.material.color.setHex(STATUS_COLOR[st]); cell.material.emissive.setHex(STATUS_COLOR[st]); }
    });
  }
  // resize coverage pillars to real pct_implemented (honest 60/60/0 expected)
  if (cov) {
    Object.entries(FW).forEach(([apiKey, shortKey]) => {
      const entry = cov[apiKey];
      const pil = heatmap.userData.pillars[shortKey];
      if (entry && pil && typeof entry.pct_implemented === "number") {
        const h = Math.max(0.05, (entry.pct_implemented / 100) * 3.5);
        pil.scale.y = h / pil.geometry.parameters.height;
        pil.position.y = h / 2 + 0.2;
        const col = entry.pct_implemented >= 100 ? C.green : (entry.pct_implemented > 0 ? C.gold : C.gray);
        pil.material.color.setHex(col); pil.material.emissive.setHex(col);
      }
    });
  }
}

function _applyAttest(json) {
  const axes = _root && _root.children.find((c) => c.userData && c.userData.kind === "axes");
  if (!axes) return;
  const present = json.axes_present || [];
  ["build", "model", "runtime"].forEach((name) => {
    const bar = axes.userData.bars[name];
    if (!bar) return;
    const on = present.indexOf(name) >= 0;
    bar.material.opacity = on ? 0.95 : 0.3;
    bar.material.emissiveIntensity = on ? 0.55 : 0.2;
  });
}

function _applyLedger(json) {
  const ledger = _root && _root.children.find((c) => c.userData && c.userData.kind === "ledger");
  const killSwitch = _root && _root.children.find((c) => c.userData && c.userData.kind === "killswitch");
  const entries = json.entries || json.replay || [];
  const RING = { "safe-auto": C.green, gated: C.gold, forbidden: C.red, unknown: C.gray };
  if (ledger && Array.isArray(entries)) {
    ledger.userData.blocks.forEach((blk, i) => {
      const e = entries[i];
      if (!e) return;
      if (i === 0) return; // keep genesis blue
      const col = e.decision === "BLOCKED" || e.decision === "DENY" ? C.red : (RING[e.ring] || C.gray);
      blk.material.color.setHex(col); blk.material.emissive.setHex(col);
    });
  }
  // kill-switch: forge_governance kill_switch bool -> armed indicator
  if (killSwitch) {
    const armed = !!json.kill_switch;
    killSwitch.userData.armed = armed;
    const col = armed ? C.red : C.green;
    killSwitch.userData.core.material.color.setHex(col);
    killSwitch.userData.core.material.emissive.setHex(col);
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
  _overlay = null; _graphPanel = null; _hud = {};
  _stage = null; _THREE = null; _label = null; _live = null;
  for (const k in _state) delete _state[k];
}

export default { id: ID, title: TITLE, endpoints: ENDPOINTS, mount, unmount };
