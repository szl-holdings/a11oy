// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
//
// surfaces/counter-uas.js — Counter-UAS surface STUB (Dev0 foundation; Dev4 fills this).
//
// Leader/technique to model: Anduril Lattice + CesiumJS
// Primary live endpoint (doctrine: WIRE TO LIVE DATA, never fabricate): /counter-uas/evaluate
//
// CONTRACT — every surface module is an ES module default-exporting:
//   { id, title, endpoints[], mount(ctx), unmount() }
// ctx (provided by the /holographic shell via szl3d):
//   ctx.stage      Stage from szl3d_boot.boot() — scene, camera, renderer, THREE,
//                  start, stop, onFrame, setBloom, backend, ...
//   ctx.container  the surface's DOM panel (for overlays/badges/HUD)
//   ctx.live       the szl3d_live module  (ctx.live.poll(endpoint, ms, onData, {badge}))
//   ctx.label      the szl3d_label module (ctx.label.chip / .billboard / .legend)
//   ctx.THREE      the three module
// mount() attaches scene objects + starts polling. unmount() stops polls and removes
// DOM it added (the shell disposes the stage).
//
// This STUB renders an honest "awaiting Dev4" placeholder + a LIVE badge wired to the
// real endpoint, proving the toolkit primitives work end-to-end before the real viz lands.

const ID = "counter-uas";
const TITLE = "Counter-UAS";
const ENDPOINT = "/counter-uas/evaluate";
const ACCENT = 0xff6b6b;

let _stage = null, _handle = null, _overlay = null, _obj = null;

function mount(ctx) {
  _stage = ctx.stage;
  const THREE = ctx.THREE;

  const geo = new THREE.IcosahedronGeometry(2.4, 1);
  const mat = new THREE.MeshStandardMaterial({
    color: ACCENT, emissive: ACCENT, emissiveIntensity: 0.35,
    metalness: 0.4, roughness: 0.35, wireframe: true,
  });
  _obj = new THREE.Mesh(geo, mat);
  _stage.scene.add(_obj);
  _stage.onFrame(() => { if (_obj) { _obj.rotation.y += 0.004; _obj.rotation.x += 0.0015; } });

  try {
    const bb = ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: TITLE, scale: 0.7, position: [0, 3.4, 0] });
    _stage.scene.add(bb);
  } catch (_) {}

  _overlay = document.createElement("div");
  _overlay.className = "szl3d-surface-overlay";
  Object.assign(_overlay.style, { position: "absolute", left: "14px", top: "14px", zIndex: "5",
    display: "flex", flexDirection: "column", gap: "8px", maxWidth: "min(92%,420px)" });
  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px";
  h.textContent = TITLE + "  ·  awaiting Dev4";
  const badge = ctx.live.createBadge();
  const legend = ctx.label.legend();
  legend.style.opacity = "0.85";
  _overlay.appendChild(h); _overlay.appendChild(badge.el); _overlay.appendChild(legend);
  (ctx.container || document.body).appendChild(_overlay);

  _handle = ctx.live.poll(ENDPOINT, 5000, (json, meta) => {
    // Dev4: replace with the real viz update. Honesty label is in meta.label.
    if (meta.label && _obj) { /* map live values to geometry here */ }
  }, { badge });

  return { id: ID, started: true };
}

function unmount() {
  try { if (_handle) _handle.stop(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try { if (_obj && _stage) _stage.scene.remove(_obj); } catch (_) {}
  _handle = null; _overlay = null; _obj = null; _stage = null;
}

export default { id: ID, title: TITLE, endpoints: [ENDPOINT], mount, unmount };
