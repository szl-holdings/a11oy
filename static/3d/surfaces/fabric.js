// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
//
// surfaces/fabric.js — COMPUTE FABRIC surface (Dev2).
//
// Leader/technique modeled (NOT claimed-as): NVIDIA Omniverse DC digital twin +
// MIT-LL TX-Digital Twin (per-node instanced cards, color-graded health) +
// 3d-force-graph (vasturiano) — a 3D force-directed node mesh of the live compute pool.
//
// Primary live endpoint (doctrine v11: WIRE TO LIVE DATA, never fabricate):
//   /api/a11oy/v1/compute-pool-hardened   (the hardened sub-second, breaker-guarded
//   prober that returns the REAL TCP-probed pool JSON — honest per-node reachability
//   with probe_elapsed_s, not the optimistic cached counts the plain /compute-pool
//   path can report)
//   counts{nodes_total, nodes_reachable, gpu_nodes_reachable, sovereign_gpu_live}
//   nodes[]{name,kind,endpoint,reachable,sovereign,capabilities,models[]}
//
// Every value on screen traces to that JSON. If a node lacks a field (e.g. the
// hardened prober omits capabilities/models), we render the honest absence — we
// never invent a model name or a reachability. If the endpoint 404s / errors /
// {degraded:true}, the badge shows the honest state and the last good mesh is kept
// (or, with no data ever, an honest NO-LIVE-DATA placeholder). 0 runtime CDN.
//
// Honesty posture rendered on the viz:
//   * reachable  -> REAL TCP probe result (teal glow ON) vs unreachable (dim, red ring)
//   * sovereign  -> a PROPERTY of owned hardware (gold), passed through, NEVER inferred
//   * the node-detail label chip is STRUCTURAL-ONLY: the topology mesh is structure,
//     not a measured bandwidth — we do NOT claim measured NVLink bytes/sec. The reach
//     counts ARE measured (live probe), labeled accordingly in the HUD.

const ID = "fabric";
const TITLE = "Compute Fabric";
const ENDPOINT = "/api/a11oy/v1/compute-pool-hardened";

// Doctrine palette (matches the shell CSS vars).
const C = {
  sovereign: 0xe8c074, // gold — owned sovereign hardware
  hosted: 0x6fb1ff,    // blue — third-party hosted inference
  gpu: 0x39d3c4,       // teal — GPU-class node
  unreachable: 0xff6b6b,
  edge: 0x2a5a6b,
  edgeHot: 0x39d3c4,
  hub: 0x12202b,
  text: "#eef3f6",
  para: "#9fb1bf",
};

let _ctx = null, _stage = null, _THREE = null;
let _handle = null, _overlay = null, _panel = null, _detailChip = null;
let _root = null;          // group holding the whole mesh (rotates slowly)
let _nodeMeshes = [];      // [{ data, group, core, ring, glow, orbit[], labelSprite, basePos }]
let _edges = [];           // [{ line, a, b, hot }]
let _hubMesh = null, _healthRing = null, _healthFill = null;
let _raf = null, _frameCb = null;
let _lastJson = null, _lastMeta = null;
let _t = 0;
let _hud = {};             // references to live HUD value spans
let _selected = null;
let _ray = null, _pointer = null, _onClick = null, _onMove = null;
let _domEl = null;

// ----------------------------------------------------------------------------
// Deterministic layout: place nodes on a force-relaxed sphere shell around a
// central fabric hub. We seed positions deterministically from the node name
// (no randomness => stable across polls) and run a light repulsion relax so the
// graph reads like a 3d-force-graph layout without a per-frame CPU sim.
// ----------------------------------------------------------------------------
function _hash(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}
function _seedPos(name, i, n) {
  // Fibonacci-sphere seed perturbed by name hash -> deterministic, well-spread.
  const h = _hash(name);
  const golden = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - (i / Math.max(1, n - 1)) * 2;
  const r = Math.sqrt(Math.max(0, 1 - y * y));
  const theta = golden * i + (h % 360) * Math.PI / 180;
  const R = 6.4;
  return [Math.cos(theta) * r * R, y * R * 0.78, Math.sin(theta) * r * R];
}
function _relax(positions, iters) {
  // tiny O(n^2) repulsion so close seeds spread; n is ~6, cost is trivial.
  for (let it = 0; it < iters; it++) {
    for (let a = 0; a < positions.length; a++) {
      for (let b = a + 1; b < positions.length; b++) {
        const dx = positions[a][0] - positions[b][0];
        const dy = positions[a][1] - positions[b][1];
        const dz = positions[a][2] - positions[b][2];
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 0.0001) d2 = 0.0001;
        const f = 1.6 / d2;
        const d = Math.sqrt(d2);
        const ux = dx / d, uy = dy / d, uz = dz / d;
        positions[a][0] += ux * f; positions[a][1] += uy * f; positions[a][2] += uz * f;
        positions[b][0] -= ux * f; positions[b][1] -= uy * f; positions[b][2] -= uz * f;
      }
    }
  }
  return positions;
}

function _isGpu(kind) { return /gpu/i.test(String(kind || "")); }
function _nodeColor(node) {
  if (!node.reachable) return C.unreachable;
  if (node.sovereign) return C.sovereign;
  if (_isGpu(node.kind)) return C.gpu;
  return C.hosted;
}

// ----------------------------------------------------------------------------
// HUD overlay (left): title, LIVE badge, fabric-health ring readout, counts,
// honesty legend. Right panel: node-detail (click a node).
// ----------------------------------------------------------------------------
function _styleOverlay(el) {
  Object.assign(el.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "5",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(92%,360px)", pointerEvents: "none",
  });
}
function _row(label, valId) {
  const r = document.createElement("div");
  r.style.cssText = "display:flex;justify-content:space-between;gap:14px;" +
    "font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:" + C.para + ";pointerEvents:none";
  const k = document.createElement("span"); k.textContent = label;
  const v = document.createElement("span"); v.id = valId;
  v.style.cssText = "color:" + C.text + ";font-weight:600;letter-spacing:.3px";
  v.textContent = "—";
  r.appendChild(k); r.appendChild(v);
  _hud[valId] = v;
  return r;
}

function _buildOverlay() {
  const ov = document.createElement("div");
  ov.className = "szl3d-fabric-overlay";
  _styleOverlay(ov);

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:" + C.text + ";letter-spacing:.4px";
  h.textContent = "◇ " + TITLE + " · live node mesh";
  ov.appendChild(h);

  const badge = _ctx.live.createBadge();
  badge.el.style.pointerEvents = "auto";
  ov.appendChild(badge.el);

  const card = document.createElement("div");
  card.style.cssText = "background:#0b121b;border:1px solid #1b2734;border-radius:9px;" +
    "padding:9px 11px;display:flex;flexDirection:column;gap:5px;pointerEvents:none";
  card.appendChild(_row("fabric health", "v_health"));
  card.appendChild(_row("nodes reachable", "v_reach"));
  card.appendChild(_row("GPU nodes live", "v_gpu"));
  card.appendChild(_row("sovereign GPU live", "v_sov"));
  card.appendChild(_row("chaski 2nd-lung", "v_chaski"));
  card.appendChild(_row("reach probe", "v_label"));
  ov.appendChild(card);

  const note = document.createElement("div");
  note.style.cssText = "font:9.5px ui-monospace,monospace;color:#6c7a86;line-height:1.5;pointerEvents:none";
  note.textContent = "reachable = REAL TCP probe this sweep · sovereign = owned-hardware " +
    "property, never inferred · topology is STRUCTURAL-ONLY (no measured NVLink bytes).";
  ov.appendChild(note);

  const legend = _ctx.label.legend();
  legend.style.opacity = "0.85";
  legend.style.pointerEvents = "none";
  ov.appendChild(legend);

  return { ov, badge };
}

function _buildPanel() {
  const p = document.createElement("div");
  p.className = "szl3d-fabric-panel";
  Object.assign(p.style, {
    position: "absolute", right: "14px", top: "14px", zIndex: "5",
    width: "min(46%,300px)", background: "#0b121b", border: "1px solid #1b2734",
    borderRadius: "9px", padding: "11px 13px", display: "none",
    font: "11px ui-monospace,SFMono-Regular,Menlo,monospace", color: C.para,
    pointerEvents: "auto",
  });
  return p;
}

function _renderPanel(node) {
  if (!_panel) return;
  if (!node) { _panel.style.display = "none"; return; }
  _panel.style.display = "block";
  _panel.innerHTML = "";

  const title = document.createElement("div");
  title.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:" + C.text +
    ";display:flex;align-items:center;gap:8px;margin-bottom:7px";
  const dot = document.createElement("span");
  const hex = "#" + _nodeColor(node).toString(16).padStart(6, "0");
  dot.style.cssText = "width:10px;height:10px;border-radius:50%;background:" + hex +
    ";box-shadow:0 0 8px " + hex;
  const nm = document.createElement("span"); nm.textContent = node.name || "(unnamed)";
  title.appendChild(dot); title.appendChild(nm);
  _panel.appendChild(title);

  const close = document.createElement("button");
  close.textContent = "×";
  close.style.cssText = "position:absolute;right:8px;top:6px;background:none;border:none;" +
    "color:" + C.para + ";font-size:16px;cursor:pointer;line-height:1";
  close.onclick = () => { _select(null); };
  _panel.appendChild(close);

  const meta = [
    ["kind", node.kind || "—"],
    ["endpoint", node.endpoint || "—"],
    ["reachable", node.reachable ? "YES (live TCP probe)" : "NO (timeout/refusal)"],
    ["sovereign", node.sovereign ? "YES (owned hardware)" : "no (hosted/third-party)"],
  ];
  meta.forEach(([k, v]) => {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:12px;margin:3px 0";
    const a = document.createElement("span"); a.textContent = k; a.style.color = C.para;
    const b = document.createElement("span"); b.textContent = v;
    b.style.cssText = "color:" + C.text + ";text-align:right;max-width:62%;word-break:break-all";
    r.appendChild(a); r.appendChild(b); _panel.appendChild(r);
  });

  // capabilities (honest: only what JSON carries)
  const caps = Array.isArray(node.capabilities) ? node.capabilities : [];
  const capWrap = document.createElement("div");
  capWrap.style.cssText = "margin-top:8px";
  const capH = document.createElement("div");
  capH.textContent = "capabilities (" + caps.length + ")";
  capH.style.cssText = "color:" + C.para + ";margin-bottom:4px";
  capWrap.appendChild(capH);
  if (caps.length) {
    const tagRow = document.createElement("div");
    tagRow.style.cssText = "display:flex;flex-wrap:wrap;gap:4px";
    caps.forEach((c) => {
      const t = document.createElement("span");
      t.textContent = String(c);
      t.style.cssText = "font-size:9.5px;padding:2px 6px;border-radius:5px;" +
        "background:#12202b;border:1px solid #1b2734;color:" + C.text;
      tagRow.appendChild(t);
    });
    capWrap.appendChild(tagRow);
  } else {
    const none = document.createElement("div");
    none.textContent = "— none in feed —";
    none.style.cssText = "color:#6c7a86;font-style:italic";
    capWrap.appendChild(none);
  }
  _panel.appendChild(capWrap);

  // models (honest: only what JSON carries)
  const models = Array.isArray(node.models) ? node.models : [];
  const mWrap = document.createElement("div");
  mWrap.style.cssText = "margin-top:8px";
  const mH = document.createElement("div");
  mH.textContent = "models (" + models.length + ")";
  mH.style.cssText = "color:" + C.para + ";margin-bottom:4px";
  mWrap.appendChild(mH);
  if (models.length) {
    models.slice(0, 12).forEach((mdl) => {
      const li = document.createElement("div");
      li.textContent = "• " + (typeof mdl === "string" ? mdl : (mdl && mdl.id) || JSON.stringify(mdl));
      li.style.cssText = "color:" + C.text + ";margin:2px 0;word-break:break-all";
      mWrap.appendChild(li);
    });
    if (models.length > 12) {
      const more = document.createElement("div");
      more.textContent = "… +" + (models.length - 12) + " more";
      more.style.color = "#6c7a86";
      mWrap.appendChild(more);
    }
  } else {
    const none = document.createElement("div");
    none.textContent = "— none in feed (model list not exposed by this node) —";
    none.style.cssText = "color:#6c7a86;font-style:italic";
    mWrap.appendChild(none);
  }
  _panel.appendChild(mWrap);

  if (node.detail) {
    const d = document.createElement("div");
    d.textContent = node.detail;
    d.style.cssText = "margin-top:8px;color:#6c7a86;line-height:1.5";
    _panel.appendChild(d);
  }

  const chipWrap = document.createElement("div");
  chipWrap.style.cssText = "margin-top:9px";
  chipWrap.appendChild(_ctx.label.chip("STRUCTURAL-ONLY", { text: "topology" }));
  _panel.appendChild(chipWrap);
}

// ----------------------------------------------------------------------------
// 3D mesh construction
// ----------------------------------------------------------------------------
function _clearMesh() {
  if (_root && _stage) _stage.scene.remove(_root);
  _root = null; _nodeMeshes = []; _edges = [];
  _hubMesh = null; _healthRing = null; _healthFill = null;
}

function _makeGlowSprite(THREE, hex) {
  const cnv = document.createElement("canvas");
  cnv.width = cnv.height = 128;
  const g = cnv.getContext("2d");
  const col = "#" + hex.toString(16).padStart(6, "0");
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  grad.addColorStop(0, col);
  grad.addColorStop(0.25, col);
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.globalAlpha = 0.9; g.fillStyle = grad; g.beginPath();
  g.arc(64, 64, 64, 0, Math.PI * 2); g.fill();
  const tex = new THREE.CanvasTexture(cnv);
  if ("colorSpace" in tex && THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  return new THREE.Sprite(mat);
}

function _nameSprite(THREE, text, hex) {
  const fs = 40, pad = 14;
  const cnv = document.createElement("canvas");
  const g = cnv.getContext("2d");
  g.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  const w = Math.ceil(g.measureText(text).width) + pad * 2;
  const h = fs + pad * 2;
  cnv.width = w; cnv.height = h;
  g.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  g.fillStyle = "rgba(8,16,26,0.72)";
  g.fillRect(0, 0, w, h);
  g.fillStyle = "#" + hex.toString(16).padStart(6, "0");
  g.textBaseline = "middle"; g.fillText(text, pad, h / 2 + 2);
  const tex = new THREE.CanvasTexture(cnv);
  if ("colorSpace" in tex && THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sp = new THREE.Sprite(mat);
  const sh = 0.5;
  sp.scale.set(sh * (w / h), sh, 1);
  return sp;
}

function _buildMesh(json) {
  const THREE = _THREE;
  _clearMesh();
  _root = new THREE.Group();
  _stage.scene.add(_root);

  const nodes = Array.isArray(json.nodes) ? json.nodes : [];
  const n = nodes.length;

  // central fabric hub
  const hubGeo = new THREE.IcosahedronGeometry(1.05, 1);
  const hubMat = new THREE.MeshStandardMaterial({
    color: C.hub, emissive: C.gpu, emissiveIntensity: 0.25,
    metalness: 0.6, roughness: 0.3, wireframe: true, transparent: true, opacity: 0.55,
  });
  _hubMesh = new THREE.Mesh(hubGeo, hubMat);
  _root.add(_hubMesh);

  // fabric-health ring (6/6) around the hub — torus whose arc-fill we color by
  // reachable/total. Built as two tori: a dim full ring + a bright reachable arc.
  const ringBase = new THREE.Mesh(
    new THREE.TorusGeometry(2.0, 0.045, 8, 96),
    new THREE.MeshBasicMaterial({ color: 0x223240, transparent: true, opacity: 0.8 })
  );
  ringBase.rotation.x = Math.PI / 2;
  _root.add(ringBase);
  _healthRing = ringBase;

  // positions (deterministic + light relax)
  const positions = nodes.map((nd, i) => _seedPos(nd.name || ("node" + i), i, n));
  _relax(positions, 18);

  // edges hub<->node (the fabric mesh spokes) — bandwidth-style tubes
  nodes.forEach((nd, i) => {
    const p = positions[i];
    const reachable = !!nd.reachable;
    const hex = reachable ? C.edgeHot : C.edge;
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(p[0], p[1], p[2])];
    const curve = new THREE.CatmullRomCurve3([
      pts[0],
      new THREE.Vector3(p[0] * 0.4, p[1] * 0.4 + 0.6, p[2] * 0.4),
      pts[1],
    ]);
    const tubeGeo = new THREE.TubeGeometry(curve, 20, reachable ? 0.05 : 0.025, 6, false);
    const tubeMat = new THREE.MeshBasicMaterial({
      color: hex, transparent: true, opacity: reachable ? 0.55 : 0.2,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const line = new THREE.Mesh(tubeGeo, tubeMat);
    _root.add(line);
    _edges.push({ line, hot: reachable, idx: i });
  });

  // node cards (instanced look via per-node box) + glow + reachability ring + model orbit
  nodes.forEach((nd, i) => {
    const p = positions[i];
    const color = _nodeColor(nd);
    const grp = new THREE.Group();
    grp.position.set(p[0], p[1], p[2]);

    // GPU nodes get a chunkier "card"; hosted get a slimmer chip.
    const gpu = _isGpu(nd.kind);
    const size = gpu ? 0.62 : 0.46;
    const coreGeo = gpu
      ? new THREE.BoxGeometry(size, size * 0.7, size * 0.18)
      : new THREE.OctahedronGeometry(size * 0.62, 0);
    const coreMat = new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: nd.reachable ? 0.7 : 0.15,
      metalness: 0.5, roughness: 0.35,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.userData.fabricNodeIdx = i;
    grp.add(core);

    // reachability glow (additive sprite) — only bright when reachable
    const glow = _makeGlowSprite(THREE, color);
    glow.scale.set(2.0, 2.0, 1);
    glow.material.opacity = nd.reachable ? 0.85 : 0.18;
    grp.add(glow);

    // unreachable nodes get a red warning ring
    let ring = null;
    if (!nd.reachable) {
      ring = new THREE.Mesh(
        new THREE.TorusGeometry(size * 0.95, 0.03, 6, 32),
        new THREE.MeshBasicMaterial({ color: C.unreachable, transparent: true, opacity: 0.8 })
      );
      grp.add(ring);
    }

    // per-node model-list orbit: one small bead per model, ringing the node.
    const models = Array.isArray(nd.models) ? nd.models : [];
    const orbit = [];
    const orbitGrp = new THREE.Group();
    const mCount = Math.min(models.length, 16);
    for (let k = 0; k < mCount; k++) {
      const a = (k / Math.max(1, mCount)) * Math.PI * 2;
      const rr = size + 0.45;
      const bead = new THREE.Mesh(
        new THREE.SphereGeometry(0.06, 8, 8),
        new THREE.MeshBasicMaterial({ color: 0xeef3f6, transparent: true, opacity: 0.85 })
      );
      bead.position.set(Math.cos(a) * rr, 0, Math.sin(a) * rr);
      orbitGrp.add(bead); orbit.push(bead);
    }
    grp.add(orbitGrp);

    // capability-count tag + name
    const nameTag = _nameSprite(THREE, nd.name || ("node" + i), color);
    nameTag.position.set(0, size + 0.55, 0);
    grp.add(nameTag);

    _root.add(grp);
    _nodeMeshes.push({
      data: nd, group: grp, core, glow, ring, orbit, orbitGrp, nameTag,
      basePos: [p[0], p[1], p[2]], gpu, color, phase: (_hash(nd.name || "x") % 100) / 100,
    });
  });

  // chaski 2nd-lung indicator: if a node named chaski is present + reachable, draw
  // a soft "breathing" secondary ring (the founder-tailnet GPU = the 2nd lung).
  const chaski = _nodeMeshes.find((m) => /chaski/i.test(m.data.name || ""));
  if (chaski) {
    const lung = new THREE.Mesh(
      new THREE.TorusGeometry(0.95, 0.02, 6, 40),
      new THREE.MeshBasicMaterial({
        color: chaski.data.reachable ? C.gpu : 0x55606a,
        transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false,
      })
    );
    lung.rotation.x = Math.PI / 2;
    chaski.group.add(lung);
    chaski.lung = lung;
  }
}

// ----------------------------------------------------------------------------
// HUD update from live JSON
// ----------------------------------------------------------------------------
function _deriveSovereignGpuLive(json) {
  // Prefer the JSON's own count; else derive honestly from nodes[].
  const c = json.counts || {};
  if (typeof c.sovereign_gpu_live === "number") return c.sovereign_gpu_live;
  const nodes = Array.isArray(json.nodes) ? json.nodes : [];
  return nodes.filter((nd) => nd.sovereign && _isGpu(nd.kind) && nd.reachable).length;
}

function _updateHud(json, meta) {
  const c = (json && json.counts) || {};
  const nodes = Array.isArray(json && json.nodes) ? json.nodes : [];
  const total = typeof c.nodes_total === "number" ? c.nodes_total : nodes.length;
  const reach = typeof c.nodes_reachable === "number"
    ? c.nodes_reachable : nodes.filter((n) => n.reachable).length;
  const gpu = typeof c.gpu_nodes_reachable === "number"
    ? c.gpu_nodes_reachable : nodes.filter((n) => n.reachable && _isGpu(n.kind)).length;
  const sovGpu = _deriveSovereignGpuLive(json);

  if (_hud.v_health) _hud.v_health.textContent = reach + "/" + total + " online";
  if (_hud.v_reach) _hud.v_reach.textContent = String(reach);
  if (_hud.v_gpu) _hud.v_gpu.textContent = String(gpu);
  if (_hud.v_sov) {
    _hud.v_sov.textContent = String(sovGpu);
    _hud.v_sov.style.color = sovGpu > 0 ? "#e8c074" : C.para;
  }
  const chaski = nodes.find((n) => /chaski/i.test(n.name || ""));
  if (_hud.v_chaski) {
    _hud.v_chaski.textContent = chaski
      ? (chaski.reachable ? "BREATHING" : "down") : "absent";
    _hud.v_chaski.style.color = chaski && chaski.reachable ? "#39d3c4" : C.para;
  }
  if (_hud.v_label) {
    // reach counts come from a live TCP probe — that IS measured.
    _hud.v_label.textContent = "MEASURED (live TCP)";
    _hud.v_label.style.color = "#2fd07a";
  }

  // update health ring fill: scale arc opacity by reachable fraction
  if (_healthRing) {
    const frac = total > 0 ? reach / total : 0;
    _healthRing.material.color.setHex(frac >= 1 ? C.gpu : (frac > 0 ? C.sovereign : C.unreachable));
    _healthRing.material.opacity = 0.35 + 0.5 * frac;
  }
}

// ----------------------------------------------------------------------------
// Degraded / missing handling
// ----------------------------------------------------------------------------
function _showDegraded(meta) {
  // keep last good mesh if we have one; just annotate the HUD honestly
  if (_hud.v_health) {
    if (meta.state === "missing") _hud.v_health.textContent = "NO-LIVE-DATA";
    else if (meta.state === "error") _hud.v_health.textContent = "OFFLINE";
    else if (meta.state === "degraded") _hud.v_health.textContent = "DEGRADED";
  }
  if (!_lastJson && !_nodeMeshes.length) {
    // never had data — render an honest placeholder hub so the tab isn't empty.
    if (!_root) {
      const THREE = _THREE;
      _root = new THREE.Group(); _stage.scene.add(_root);
      const m = new THREE.Mesh(
        new THREE.IcosahedronGeometry(2.2, 1),
        new THREE.MeshStandardMaterial({ color: C.hosted, emissive: C.hosted, emissiveIntensity: 0.2, wireframe: true })
      );
      _root.add(m); _hubMesh = m;
      try {
        const bb = _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "compute-pool · awaiting live data", scale: 0.6, position: [0, 3, 0] });
        _root.add(bb);
      } catch (_) {}
    }
  }
}

// ----------------------------------------------------------------------------
// Raycast click -> select node -> detail panel
// ----------------------------------------------------------------------------
function _select(idx) {
  _selected = idx;
  _nodeMeshes.forEach((m, i) => {
    const on = i === idx;
    if (m.core && m.core.material) {
      m.core.material.emissiveIntensity = on ? 1.4 : (m.data.reachable ? 0.7 : 0.15);
    }
  });
  _renderPanel(idx == null ? null : _nodeMeshes[idx] && _nodeMeshes[idx].data);
}

function _setupPicking() {
  const THREE = _THREE;
  _ray = new THREE.Raycaster();
  _pointer = new THREE.Vector2();
  _domEl = _stage.renderer && _stage.renderer.domElement;
  if (!_domEl) return;

  let downX = 0, downY = 0;
  _onMove = (e) => { /* reserved for hover; kept light */ };
  const _onDown = (e) => { downX = e.clientX; downY = e.clientY; };
  _onClick = (e) => {
    // ignore drags (orbit controls)
    if (Math.abs(e.clientX - downX) > 4 || Math.abs(e.clientY - downY) > 4) return;
    const rect = _domEl.getBoundingClientRect();
    _pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    _pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    _ray.setFromCamera(_pointer, _stage.camera);
    const cores = _nodeMeshes.map((m) => m.core).filter(Boolean);
    const hits = _ray.intersectObjects(cores, false);
    if (hits.length) {
      const idx = hits[0].object.userData.fabricNodeIdx;
      _select(idx === _selected ? null : idx);
    } else {
      _select(null);
    }
  };
  _domEl.addEventListener("mousedown", _onDown);
  _domEl.addEventListener("click", _onClick);
  _domEl._szlFabricDown = _onDown; // for cleanup
}

// ----------------------------------------------------------------------------
// Per-frame animation: slow rotate, GPU-live pulse, model-orbit spin,
// bandwidth-tube shimmer, chaski lung breathing, hub spin.
// ----------------------------------------------------------------------------
function _frame() {
  _t += 0.016;
  if (_root) _root.rotation.y += 0.0018;
  if (_hubMesh) { _hubMesh.rotation.y -= 0.004; _hubMesh.rotation.x += 0.0012; }

  _nodeMeshes.forEach((m) => {
    // GPU-live pulse: reachable GPU nodes breathe in emissive + glow.
    if (m.gpu && m.data.reachable && m.core && m.core.material) {
      const pulse = 0.7 + 0.5 * (0.5 + 0.5 * Math.sin(_t * 2.2 + m.phase * 6.28));
      if (_selected == null || _nodeMeshes[_selected] !== m) m.core.material.emissiveIntensity = pulse;
      if (m.glow) m.glow.material.opacity = 0.6 + 0.35 * (0.5 + 0.5 * Math.sin(_t * 2.2 + m.phase * 6.28));
    }
    // model orbit spin
    if (m.orbitGrp) m.orbitGrp.rotation.y += m.gpu ? 0.012 : 0.006;
    // unreachable ring slow pulse
    if (m.ring) m.ring.material.opacity = 0.4 + 0.4 * (0.5 + 0.5 * Math.sin(_t * 3));
    // chaski lung breathing
    if (m.lung) {
      const b = 0.85 + 0.25 * (0.5 + 0.5 * Math.sin(_t * 1.3));
      m.lung.scale.set(b, b, b);
      m.lung.material.opacity = 0.4 + 0.4 * (0.5 + 0.5 * Math.sin(_t * 1.3));
    }
  });

  // bandwidth-tube shimmer: animate opacity of reachable spokes
  _edges.forEach((e, i) => {
    if (e.hot && e.line && e.line.material) {
      e.line.material.opacity = 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(_t * 3 + i));
    }
  });
}

// ----------------------------------------------------------------------------
// mount / unmount
// ----------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _t = 0; _selected = null; _lastJson = null; _hud = {};

  const built = _buildOverlay();
  _overlay = built.ov;
  (ctx.container || document.body).appendChild(_overlay);

  _panel = _buildPanel();
  (ctx.container || document.body).appendChild(_panel);

  // enable bloom for the holographic node glow (safe no-op on WebGPU per toolkit).
  try { if (_stage.setBloom) _stage.setBloom(true); } catch (_) {}

  _frameCb = _frame;
  _stage.onFrame(_frameCb);

  _setupPicking();

  _handle = ctx.live.poll(ENDPOINT, 5000, (json, meta) => {
    _lastMeta = meta;
    if (meta.state === "live" || meta.state === "degraded") {
      _lastJson = json;
      _buildMesh(json);          // rebuild from the latest real probe
      _setupPicking();           // re-bind cores (mesh was rebuilt)
      _updateHud(json, meta);
      if (meta.state === "degraded") _showDegraded(meta);
      // re-render panel if a node is selected and still present
      if (_selected != null && _nodeMeshes[_selected]) _renderPanel(_nodeMeshes[_selected].data);
      else _select(null);
    } else {
      _showDegraded(meta);
    }
  }, { badge: built.badge, onState: (meta) => { if (meta.state !== "live" && meta.state !== "degraded") _showDegraded(meta); } });

  return { id: ID, started: true };
}

function unmount() {
  try { if (_handle) _handle.stop(); } catch (_) {}
  try {
    if (_domEl) {
      if (_onClick) _domEl.removeEventListener("click", _onClick);
      if (_domEl._szlFabricDown) _domEl.removeEventListener("mousedown", _domEl._szlFabricDown);
      _domEl._szlFabricDown = null;
    }
  } catch (_) {}
  try { _clearMesh(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try { if (_panel && _panel.parentNode) _panel.parentNode.removeChild(_panel); } catch (_) {}
  _handle = null; _overlay = null; _panel = null; _detailChip = null;
  _nodeMeshes = []; _edges = []; _root = null; _hubMesh = null;
  _healthRing = null; _healthFill = null; _frameCb = null; _ray = null;
  _pointer = null; _onClick = null; _onMove = null; _domEl = null;
  _ctx = null; _stage = null; _THREE = null; _lastJson = null; _selected = null;
}

export default { id: ID, title: TITLE, endpoints: [ENDPOINT], mount, unmount };
