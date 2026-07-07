// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/interpretability.js — MECHANISTIC-INTERPRETABILITY / SPARSE-AUTOENCODER
// organ for the holographic frontier ring.
//
// Renders a 3D lattice of dictionary-feature nodes driven by a live JumpReLU sparse
// autoencoder snapshot from /api/a11oy/v1/interpretability/features. The top-K FIRED
// features light up; node brightness = SAE activation, node scale = causal-ablation KL
// (how much the output distribution shifts when that feature is ablated). Honesty label
// "MODELED" is read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors neuromorphic.js / frontier.js exactly):
//   export default { id, title, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   l0_sparsity         — fraction of dictionary features active (interpretability ↑ as ↓)
//   active_features     — count of features that fired (L0)
//   reconstruction_cos  — MODELED SAE reconstruction fidelity (cosine)
//   top_features[]      — {feature, activation, causal_ablation_kl, interpretation_confidence}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   SAEs find interpretable features: Cunningham et al. arXiv:2309.08600
//     https://arxiv.org/abs/2309.08600
//   JumpReLU SAEs: Rajamanoharan et al. arXiv:2407.14435
//     https://arxiv.org/abs/2407.14435
//   Anthropic circuit tracing: https://transformer-circuits.pub/2025/january-update/index.html
//   Sparse feature circuits (causal): Marks et al. arXiv:2406.02395
//     https://arxiv.org/abs/2406.02395
//
// HONESTY LABELS: MODELED (simulation of the METHOD; no proprietary weights, no measured
//   logits). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (fired feature nodes), violet-blue 0x8a6bff (top causal
//   feature flash — data-viz only). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

const ID    = "interpretability";
const TITLE = "Interpretability · Sparse-Autoencoder Features (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted SAE surface (same-origin, no CORS):
//   GET /api/a11oy/v1/interpretability/features (szl_a11oy_interpretability.py, MODELED).
// FALLBACK stays the dedicated killinchu Space (isolated compute, reached cross-origin —
// killinchu returns access-control-allow-origin: https://a-11-oy.com) so a rebuild/fault
// on EITHER path never darkens the organ (fault isolation preserved). If the primary
// reports missing/error we transparently swap to the Space fallback (see mount()).
const EP          = "/api/a11oy/v1/interpretability/features?seed=42&top_k=8&d_model=512&n_features=4096";
const EP_FALLBACK = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/interpretability/features?seed=42&top_k=8&d_model=512&n_features=4096";

// data-viz hues — purple BANNED
const C_NODE   = 0x5b8dee;  // lattice-blue (fired feature)
const C_TOP    = 0x8a6bff;  // violet-blue (highest causal feature flash — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / unfired dictionary node)
const C_ACCENT = 0x3af4c8;  // proof-teal accent for the reconstruction ring
const C_GRID   = 0x1b3a44;  // floor / link colour

// dictionary lattice geometry: a ring of feature nodes (the fired dictionary features)
const N_SLOTS = 16;   // visual dictionary slots on the ring (matches endpoint feature bank)
const RADIUS  = 4.2;  // world-unit ring radius

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _slots = [];        // Array<THREE.Mesh> — one per dictionary slot on the ring
let _links = null;      // THREE.LineSegments — slot→hub links
let _hub = null;        // THREE.Mesh — central reconstruction hub
let _ring = null;       // THREE.Mesh — reconstruction-fidelity ring

// per-slot flash timers
const _flash = new Float32Array(N_SLOTS);

// live state
const S = {
  label:        null,
  l0:           null,   // l0_sparsity
  active:       null,   // active_features
  recon:        null,   // reconstruction_cos
  top:          null,   // Array<{feature,activation,causal_ablation_kl,interpretation_confidence}>
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 7, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRing();
  _buildHub();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  // Guarded primary -> fallback: poll the a11oy-native endpoint; if it goes
  // missing/error, swap ONCE to the isolated killinchu Space (fault isolation).
  let _swapped = false;
  const _startPoll = (ep) => ctx.live.poll(ep, 5000, _onFeatures, {
    badge: _badge,
    onState: (m) => {
      S.state = m.state;
      if (!_swapped && (m.state === "missing" || m.state === "error")) {
        _swapped = true;
        try { _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = []; } catch (_) {}
        _polls.push(_startPoll(EP_FALLBACK));
      }
      _paintOverlay();
    },
  });
  _polls.push(_startPoll(EP));

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

function _buildRing() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.24, 14, 10);
  _slots = [];
  const linkPts = [];
  const hubY = 2.2;
  for (let i = 0; i < N_SLOTS; i++) {
    const ang = (i / N_SLOTS) * Math.PI * 2;
    const x = Math.cos(ang) * RADIUS;
    const z = Math.sin(ang) * RADIUS;
    const mat = new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15,
      metalness: 0.25, roughness: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(x, hubY, z);
    _group.add(mesh);
    _slots.push(mesh);
    // link each slot to the central hub
    linkPts.push(new THREE.Vector3(x, hubY, z), new THREE.Vector3(0, hubY, 0));
  }
  const lg = new THREE.BufferGeometry().setFromPoints(linkPts);
  _links = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.22 }));
  _group.add(_links);
}

function _buildHub() {
  const THREE = _THREE;
  // Central hub = the residual-stream activation being decomposed.
  _hub = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.6, 1),
    new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.55 }),
  );
  _hub.position.set(0, 2.2, 0);
  _group.add(_hub);

  // Reconstruction-fidelity ring around the hub (radius scales with reconstruction_cos).
  _ring = new THREE.Mesh(
    new THREE.TorusGeometry(1.2, 0.03, 10, 64),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.5 }),
  );
  _ring.position.set(0, 2.2, 0);
  _ring.rotation.x = Math.PI / 2;
  _group.add(_ring);
}

// =============================================================================
// live data handler
// =============================================================================
function _onFeatures(j) {
  // read honesty label VERBATIM — never upgrade
  S.label  = (j.label || "MODELED").toUpperCase();
  S.l0     = typeof j.l0_sparsity        === "number" ? j.l0_sparsity        : null;
  S.active = typeof j.active_features     === "number" ? j.active_features     : null;
  S.recon  = typeof j.reconstruction_cos === "number" ? j.reconstruction_cos  : null;
  S.top    = Array.isArray(j.top_features) ? j.top_features : null;

  _updateRing();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives slot colour/brightness from top features
// =============================================================================
function _updateRing() {
  const live = S.state === "live";
  const top  = S.top || [];
  // maximum causal KL among top features (for scaling node size)
  const maxKL = top.reduce((m, f) => Math.max(m, (f && f.causal_ablation_kl) || 0), 0.0001);

  _slots.forEach((mesh, i) => {
    const f = top[i];  // first N_SLOTS top features light up; the rest stay dim
    if (live && f) {
      const act = typeof f.activation === "number" ? f.activation : 0;
      const kl  = typeof f.causal_ablation_kl === "number" ? f.causal_ablation_kl : 0;
      const norm = kl / maxKL;                 // 0..1 relative causal effect
      const col = norm > 0.75 ? C_TOP : C_NODE;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.15 + 0.85 * act;
      mesh.scale.setScalar(0.7 + 0.9 * norm);  // bigger = more causally important
      _flash[i] = Math.min(30 + norm * 60, 90);
    } else {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.1;
      mesh.scale.setScalar(0.55);
    }
  });

  if (_hub) {
    const hcol = live ? C_NODE : C_DIM;
    _hub.material.color.setHex(hcol);
    _hub.material.emissive.setHex(hcol);
    _hub.material.emissiveIntensity = live ? 0.35 : 0.15;
    _hub.material.opacity = live ? 0.7 : 0.35;
  }

  if (_ring) {
    const cos = S.recon != null ? S.recon : 0.9;
    const rcol = live ? C_ACCENT : C_DIM;
    _ring.material.color.setHex(rcol);
    _ring.material.emissive.setHex(rcol);
    _ring.material.emissiveIntensity = live ? 0.2 + 0.6 * cos : 0.12;
    _ring.material.opacity = live ? 0.55 : 0.2;
    _ring.scale.setScalar(live ? (0.6 + cos) : 0.8);  // fuller ring = better reconstruction
  }

  if (_links) {
    _links.material.opacity = live ? 0.3 : 0.14;
    _links.material.color.setHex(live ? C_GRID : C_DIM);
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00012) * 0.2;
  if (_hub) { _hub.rotation.y += 0.006; _hub.rotation.x += 0.003; }
  if (_ring) { _ring.rotation.z += 0.004; }

  const live = S.state === "live";
  _slots.forEach((mesh, i) => {
    if (_flash[i] > 0) {
      _flash[i] -= 1;
      const f = _flash[i] / 90;
      const col = live ? C_TOP : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.15 + 0.9 * f);
    }
  });
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
    maxWidth: "min(94%,440px)",
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
    'A <b>JumpReLU sparse autoencoder</b> decomposes a model\u2019s internal activation into a ' +
    'few human-readable <b>features</b>; each fired feature is a node on the ring, and we ' +
    '<b>causally ablate</b> it to measure the output shift (KL). Honesty label <b>MODELED</b> ' +
    '(a simulation of the method \u2014 no proprietary weights, no measured logits). 0 runtime CDN.';
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
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "interpretability";
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

  grid.appendChild(kpiRow("ip-l0",     "L0 sparsity (active / dict)"));
  grid.appendChild(kpiRow("ip-active", "active features"));
  grid.appendChild(kpiRow("ip-recon",  "reconstruction cos \u2014 MODELED"));
  grid.appendChild(kpiRow("ip-topf",   "top feature (by causal KL)"));
  grid.appendChild(kpiRow("ip-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Cunningham et al. arXiv:2309.08600 \u00b7 Rajamanoharan et al. arXiv:2407.14435 (JumpReLU) \u00b7 Marks et al. arXiv:2406.02395 (sparse feature circuits) \u00b7 Anthropic transformer-circuits.pub. MODELED \u00b7 not claimed-as.";
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
  pd.id = "ip-plain";
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
  const act = S.active != null ? String(S.active) : "loading\u2026";
  const l0  = S.l0 != null ? (S.l0 * 100).toFixed(3) + "% of the dictionary" : "loading\u2026";
  const top = (S.top && S.top[0] && S.top[0].feature) ? S.top[0].feature : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of treating the model as a black box, a sparse " +
    "autoencoder breaks one internal activation into a handful of named, human-readable " +
    "<b>features</b> \u2014 here <b>" + act + "</b> fired (only <b>" + l0 + "</b>). " +
    "The most causally important one right now is <b>" + top + "</b>: turning it off shifts " +
    "the model\u2019s output the most. " +
    "Plain: this is how you audit <i>why</i> an AI produced an answer and prove which internal " +
    "concept drove it \u2014 but this view is a <b>MODELED</b> simulation of the technique, not a " +
    "readout from a live production model.";
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
  _set("ip-l0",     t || fx(S.l0, 6));
  _set("ip-active", t || (S.active != null ? String(S.active) : "\u2014"));
  _set("ip-recon",  t || fx(S.recon, 4));
  const top0 = (S.top && S.top[0]) ? S.top[0] : null;
  _set("ip-topf",   t || (top0 ? (top0.feature + "  (KL " + fx(top0.causal_ablation_kl, 3) + ")") : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("ip-label",  t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
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
  _slots = []; _links = null; _hub = null; _ring = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.l0 = S.active = S.recon = S.top = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP, EP_FALLBACK], mount, unmount };
