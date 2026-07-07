// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/agentmem.js — AGENTMEM: Λ-GOVERNED AGENT MEMORY (SZL synthesis) for
// the holographic frontier ring. Renders a persistent agent-memory store as a
// disc of memory nodes; a query recalls the top-k, which flow toward a central
// Λ-GATE. Each recall gets a Λ advisory (Conjecture 1 — gray, NEVER green):
// admitted recalls glow proof-teal, Λ-gated-out or inconsistent recalls stay
// grey. The gate core scales with the capped trust (<=0.97). A compact HUD shows
// the recall/consistency stats and the signed-receipt-per-recall DESIGN (nothing
// minted on a read). Live snapshot: /api/a11oy/v1/frontier/agentmem.
//
// This is an SZL CROSS-AXIS SYNTHESIS no published system ships together:
//   agent memory (MemGPT / A-MEM / Mem0 / DSPy) + Λ-gating (SZL restraint
//   advisory, Λ = Conjecture 1) + the signed receipt chain (receipt-per-recall).
//
// Surface export shape (mirrors titans.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   MemGPT: Towards LLMs as Operating Systems — Packer et al. 2023,
//     arXiv:2310.08560   https://arxiv.org/abs/2310.08560
//   A-MEM: Agentic Memory for LLM Agents — Xu et al. 2025,
//     arXiv:2502.12110   https://arxiv.org/abs/2502.12110
//   Mem0: Production-Ready AI Agents w/ Scalable Long-Term Memory — Chhikara
//     et al. 2025, arXiv:2504.19413   https://arxiv.org/abs/2504.19413
//   DSPy: Compiling Declarative LM Calls into Self-Improving Pipelines —
//     Khattab et al. 2023, arXiv:2310.03714   https://arxiv.org/abs/2310.03714
//
// HONESTY LABELS: MODELED (deterministic recall / consistency simulation; read
//   VERBATIM from JSON, never upgraded). The SZL SYNTHESIS is CONJECTURE: Λ as a
//   per-recall trust gate is Λ = Conjecture 1 (gray, never green), and the
//   signed-receipt-per-recall chain is design-only (RECEIPT-ON-WRITE — nothing is
//   minted or signed on this GET). Trust is capped at 0.97, never 1.0.
// COLOURS: lattice-blue 0x5b8dee (memory nodes / recall links), violet-blue
//   0x8a6bff (Λ-gate ring), proof-teal 0x3af4c8 (admitted recall / accent),
//   greys (gated-out / inconsistent / degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

const ID    = "agentmem";
const TITLE = "AgentMem · Λ-Governed Agent Memory (live)";

// Served SAME-ORIGIN by szl_agentmem.py — a deterministic governed-recall model.
const EP = "/api/a11oy/v1/frontier/agentmem?seed=42&n_memories=256&query_k=16&horizon=128";

// data-viz hues — purple BANNED
const C_MEM     = 0x5b8dee;  // lattice-blue (memory node / recall link)
const C_GATE    = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_ADMIT   = 0x3af4c8;  // proof-teal (admitted recall / accent)
const C_GATED   = 0x5a6570;  // grey (Λ-gated-out / inconsistent)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// layout geometry
const DISC_R    = 6.0;   // radius of the memory-store disc
const MAX_MEM   = 256;   // cap on memory nodes rendered (perf)
const MAX_RECALL = 24;   // cap on recall links rendered
const GATE_Y    = 0.6;   // height of the central Λ-gate core

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _collapsed = false;

// geometry handles
let _floor   = null;
let _memMesh = [];    // Array<THREE.Mesh> — memory nodes on the disc
let _gateRing = null; // THREE.LineLoop — Λ-gate ring
let _core     = null; // THREE.Mesh — central gate core (scales with trust)
let _links   = [];    // Array<THREE.Line> — recall links to the gate

// live state
const S = {
  label:        null,
  nMemories:    null,
  queryK:       null,
  horizon:      null,
  recalled:     null,   // recalled[]
  checked:      null,
  consistent:   null,
  conflicts:    null,
  consistencyRate: null,
  meanLambda:   null,
  admits:       null,
  gatedOut:     null,
  trust:        null,
  trustCap:     null,
  receiptSigned: null,
  receiptDigest: null,
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildMemoryDisc();
  _buildGate();
  _buildLinks();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onData, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Memory store: a disc of nodes laid out on a deterministic spiral so recalled
// (high-relevance) items cluster toward the centre near the Λ-gate.
function _buildMemoryDisc() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.12, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_MEM; i++) {
    const t = i / MAX_MEM;
    const r = DISC_R * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_MEM, emissive: C_MEM, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.15, Math.sin(a) * r);
    mesh.visible = false;
    _group.add(mesh);
    _memMesh.push(mesh);
  }
}

// Central Λ-gate: a ring (advisory boundary) + a core that scales with trust.
function _buildGate() {
  const THREE = _THREE;
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * 1.7, GATE_Y, Math.sin(a) * 1.7));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const m = new THREE.LineBasicMaterial({ color: C_GATE, transparent: true, opacity: 0.45 });
    _gateRing = new THREE.LineLoop(g, m);
    _group.add(_gateRing);
  }
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.7, 1),
    new THREE.MeshStandardMaterial({ color: C_GATE, emissive: C_GATE, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, GATE_Y, 0);
  _group.add(_core);
}

// Recall links: pre-allocated lines from a memory node to the gate core.
function _buildLinks() {
  const THREE = _THREE;
  for (let i = 0; i < MAX_RECALL; i++) {
    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0.15, 0), new THREE.Vector3(0, GATE_Y, 0),
    ]);
    const m = new THREE.LineBasicMaterial({ color: C_MEM, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(g, m);
    line.visible = false;
    _group.add(line);
    _links.push(line);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.nMemories = typeof p.n_memories === "number" ? p.n_memories : null;
  S.queryK    = typeof p.query_k    === "number" ? p.query_k    : null;
  S.horizon   = typeof p.horizon    === "number" ? p.horizon    : null;
  S.recalled  = Array.isArray(p.recalled) ? p.recalled : null;

  const c = (p && typeof p.consistency === "object") ? p.consistency : {};
  S.checked         = typeof c.checked === "number" ? c.checked : null;
  S.consistent      = typeof c.consistent === "number" ? c.consistent : null;
  S.conflicts       = typeof c.conflicts === "number" ? c.conflicts : null;
  S.consistencyRate = typeof c.consistency_rate === "number" ? c.consistency_rate : null;

  const g = (p && typeof p.lambda_gate === "object") ? p.lambda_gate : {};
  S.meanLambda = typeof g.mean_lambda_advisory === "number" ? g.mean_lambda_advisory : null;
  S.admits     = typeof g.admits === "number" ? g.admits : null;
  S.gatedOut   = typeof g.gated_out === "number" ? g.gated_out : null;
  S.trust      = typeof g.trust === "number" ? g.trust : null;
  S.trustCap   = typeof g.trust_cap === "number" ? g.trust_cap : null;

  const rd = (p && typeof p.receipt_design === "object") ? p.receipt_design : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // gate ring degrades to grey when not live
  if (_gateRing) {
    _gateRing.material.color.setHex(live ? C_GATE : C_DIM);
    _gateRing.material.opacity = live ? 0.45 : 0.12;
  }

  // memory nodes: light up the store; recalled nodes get pulled brighter.
  const nMem = live && S.nMemories ? Math.min(S.nMemories, MAX_MEM) : 0;
  const recalledIds = new Set();
  const admittedIds = new Set();
  if (live && S.recalled) {
    for (const r of S.recalled) {
      if (typeof r.id === "number") {
        recalledIds.add(r.id % MAX_MEM);
        if (r.admitted) admittedIds.add(r.id % MAX_MEM);
      }
    }
  }
  for (let i = 0; i < MAX_MEM; i++) {
    const mesh = _memMesh[i];
    if (i >= nMem) { mesh.visible = false; continue; }
    mesh.visible = true;
    const recalled = recalledIds.has(i);
    const admitted = admittedIds.has(i);
    const color = admitted ? C_ADMIT : (recalled ? (live ? C_GATE : C_GATED) : (live ? C_MEM : C_DIM));
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = admitted ? 0.6 : (recalled ? 0.4 : 0.12);
    mesh.material.opacity = recalled ? 0.95 : (live ? 0.35 : 0.15);
    mesh.scale.setScalar(admitted ? 1.5 : (recalled ? 1.2 : 0.8));
  }

  // recall links: draw from each recalled node to the gate; admitted proof-teal,
  // Λ-gated-out grey (the advisory verdict is shown, never hidden).
  const rec = live && S.recalled ? S.recalled.slice(0, MAX_RECALL) : [];
  for (let i = 0; i < MAX_RECALL; i++) {
    const line = _links[i];
    const r = i < rec.length ? rec[i] : null;
    if (!live || !r || typeof r.id !== "number") { line.visible = false; continue; }
    const src = _memMesh[r.id % MAX_MEM];
    if (!src) { line.visible = false; continue; }
    line.visible = true;
    const pos = line.geometry.attributes.position;
    pos.setXYZ(0, src.position.x, src.position.y, src.position.z);
    pos.setXYZ(1, 0, GATE_Y, 0);
    pos.needsUpdate = true;
    const color = r.admitted ? C_ADMIT : C_GATED;
    line.material.color.setHex(color);
    line.material.opacity = r.admitted ? 0.55 : 0.22;
  }

  // gate core: colour + size reflect the CAPPED trust (never green / never 1.0).
  if (_core) {
    if (live && S.trust != null) {
      _core.material.color.setHex(C_ADMIT);
      _core.material.emissive.setHex(C_ADMIT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.6 + S.trust * 1.0);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.6);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.12;
  if (_gateRing) _gateRing.rotation.y += 0.0016;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.008;
    const pulse = 1.0 + 0.1 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.trust != null) ? (0.6 + S.trust * 1.0) : 0.6;
    _core.scale.setScalar(base * pulse);
  }
}

// =============================================================================
// overlay — COMPACT: title + badge + small legend + collapsible panel
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "7px",
    maxWidth: "min(92vw,340px)", maxHeight: "calc(100dvh - 28px)", overflowY: "auto",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.3px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const brow = document.createElement("div");
  brow.style.cssText = "display:flex;gap:7px;align-items:center;flex-wrap:wrap";
  if (_badge && _badge.el) brow.appendChild(_badge.el);
  // honesty label pill (verbatim, never upgraded)
  const pill = document.createElement("span");
  pill.id = "am-pill";
  pill.style.cssText = "font:600 10px ui-monospace,monospace;padding:2px 7px;border-radius:10px;border:1px solid #8a6bff;color:#c9bdff;background:#14102a";
  pill.textContent = "MODELED · Λ=CONJECTURE 1";
  brow.appendChild(pill);
  _overlay.appendChild(brow);

  // small legend (3 chips)
  const lg = document.createElement("div");
  lg.style.cssText = "display:flex;gap:9px;flex-wrap:wrap;font-size:10px;color:#9fb1bf";
  lg.innerHTML =
    '<span style="color:#3af4c8">● admitted</span>' +
    '<span style="color:#8a6bff">● recalled</span>' +
    '<span style="color:#5a6570">● Λ-gated/stale</span>';
  _overlay.appendChild(lg);

  // collapse toggle
  const tog = document.createElement("button");
  tog.textContent = "▾ details";
  tog.style.cssText = "font:11px ui-monospace,monospace;padding:4px 10px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  tog.addEventListener("click", () => {
    _collapsed = !_collapsed;
    card.style.display = _collapsed ? "none" : "flex";
    tog.textContent = _collapsed ? "▸ details" : "▾ details";
  });
  _overlay.appendChild(tog);

  const card = document.createElement("div");
  card.id = "am-card";
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:5px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:3px";

  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("am-store",   "memory store / top-k"));
  grid.appendChild(kpiRow("am-cons",    "consistency_rate"));
  grid.appendChild(kpiRow("am-conf",    "conflicts (stale/contradict)"));
  grid.appendChild(kpiRow("am-lambda",  "mean Λ advisory (gray)"));
  grid.appendChild(kpiRow("am-gate",    "Λ-gate admits / gated-out"));
  grid.appendChild(kpiRow("am-trust",   "trust (capped ≤0.97)"));
  grid.appendChild(kpiRow("am-receipt", "recall receipt"));
  grid.appendChild(kpiRow("am-label",   "honesty label"));
  card.appendChild(grid);

  const note = document.createElement("div");
  note.style.cssText = "font-size:10px;color:#c9d6df;line-height:1.5;border-top:1px solid #1d2a36;padding-top:5px";
  note.innerHTML =
    "SZL synthesis: agent memory + <b>Λ trust gate</b> (Λ = Conjecture 1, gray) + " +
    "<b>signed receipt per recall</b> (receipt-on-write — nothing minted on this read).";
  card.appendChild(note);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9px;color:#6b7a86;line-height:1.5";
  fn.textContent = "MemGPT arXiv:2310.08560 · A-MEM 2502.12110 · Mem0 2504.19413 · DSPy 2310.03714. MODELED/CONJECTURE · not claimed-as.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  (ctx.container || document.body).appendChild(_overlay);
  _paintOverlay();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "—"; }
function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("am-store", t || (S.nMemories != null ? S.nMemories + " / " + (S.queryK != null ? S.queryK : "—") : "—"));
  _set("am-cons",  t || pct(S.consistencyRate, 1));
  _set("am-conf",  t || (S.conflicts != null ? String(S.conflicts) : "—"));
  _set("am-lambda", t || fx(S.meanLambda, 3));
  _set("am-gate",  t || (S.admits != null || S.gatedOut != null ? (S.admits != null ? S.admits : "—") + " / " + (S.gatedOut != null ? S.gatedOut : "—") : "—"));
  _set("am-trust", t || (S.trust != null ? fx(S.trust, 3) + (S.trustCap != null ? " (≤" + S.trustCap + ")" : "") : "—"));
  _set("am-receipt", t || (S.receiptSigned === false
        ? "unsigned preview" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptDigest ? S.receiptDigest.slice(0, 10) + "…" : "—")));
  _set("am-label", t || (S.label || "MODELED"));
}

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
  _floor = null; _memMesh = []; _gateRing = null; _core = null; _links = [];
  _el = {}; _badge = null; _collapsed = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nMemories = S.queryK = S.horizon = S.recalled = null;
  S.checked = S.consistent = S.conflicts = S.consistencyRate = null;
  S.meanLambda = S.admits = S.gatedOut = S.trust = S.trustCap = null;
  S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
