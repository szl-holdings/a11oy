// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// szl3d_label.js — SHARED doctrine honesty-label renderer (Dev0 foundation).
//
// Doctrine v11 requires EVERY value on screen to carry its honesty label, read straight
// from the API JSON ({label}/{joules_label}/{data_label}). This module renders that label
// as either a color-coded DOM overlay chip OR a 3D billboard sprite in a three.js scene.
//
//   MEASURED        -> green   (real NVML/exporter measurement)
//   MODELED         -> amber   (closed-form / deterministic model, not measured)
//   SAMPLE          -> blue    (illustrative sample signal, not production)
//   STRUCTURAL-ONLY -> gray    (structure present, value unproven/unsigned)
//
// Unknown labels render in a neutral slate so we never silently drop an honesty signal.
// 0 runtime CDN. The 3D billboard path imports three through the page importmap.

export const LABELS = Object.freeze({
  MEASURED:          { key: "MEASURED",          color: "#2fd07a", hex: 0x2fd07a, text: "#04130b", note: "real measurement (NVML/exporter)" },
  // A REAL counter/power delta where the meter counts the WHOLE GPU and exclusivity is
  // NOT asserted: an honest upper bound that may include co-tenant energy. Rendered as
  // its own verbatim state (teal, not green) so it is NEVER upgraded to a clean MEASURED.
  MEASURED_SHARED_BOUNDED: { key: "MEASURED_SHARED_BOUNDED", color: "#39d3c4", hex: 0x39d3c4, text: "#03130f", note: "real GPU-wide delta, exclusivity not asserted — upper bound" },
  MODELED:           { key: "MODELED",           color: "#e8c074", hex: 0xe8c074, text: "#1a1304", note: "closed-form / deterministic model" },
  SAMPLE:            { key: "SAMPLE",            color: "#6fb1ff", hex: 0x6fb1ff, text: "#03101f", note: "illustrative sample signal" },
  "STRUCTURAL-ONLY": { key: "STRUCTURAL-ONLY",   color: "#8a97a3", hex: 0x8a97a3, text: "#0a0e12", note: "structure only — value unproven" },
});
const NEUTRAL = { key: "UNKNOWN", color: "#9fb1bf", hex: 0x9fb1bf, text: "#06090d", note: "label passed through verbatim" };

// Canonicalize any raw label token to one of the 4 doctrine states (or neutral).
export function normalize(raw) {
  if (!raw) return null;
  const t = String(raw).trim().toUpperCase();
  // Check the shared-bounded state BEFORE the generic MEASURED branch so the co-tenant
  // upper-bound caveat is preserved verbatim and never collapsed to a clean MEASURED.
  if (t.indexOf("SHARED") >= 0 && t.indexOf("MEASURED") >= 0) return "MEASURED_SHARED_BOUNDED";
  if (t.indexOf("MEASURED") >= 0) return "MEASURED";
  if (t.indexOf("MODELED") >= 0 || t.indexOf("MODELLED") >= 0) return "MODELED";
  if (t.indexOf("SAMPLE") >= 0) return "SAMPLE";
  if (t.indexOf("STRUCTURAL") >= 0) return "STRUCTURAL-ONLY";
  return t;
}

export function spec(raw) {
  const k = normalize(raw);
  if (k && LABELS[k]) return LABELS[k];
  return Object.assign({}, NEUTRAL, { key: k || NEUTRAL.key });
}

// ---------------------------------------------------------------------------
// DOM chip. chip(label, opts) -> HTMLElement
//   label : raw or canonical honesty token (e.g. "measured", "MODELED", "STRUCTURAL-ONLY")
//   opts.text : optional extra text appended after the label (e.g. a value)
//   opts.title: tooltip (defaults to the doctrine note)
//   opts.unstyled: skip inline styling (caller provides CSS via [data-label])
// ---------------------------------------------------------------------------
export function chip(label, opts = {}) {
  const s = spec(label);
  const el = document.createElement("span");
  el.className = "szl3d-label-chip";
  el.setAttribute("data-label", s.key);
  el.textContent = opts.text ? (s.key + " · " + opts.text) : s.key;
  el.title = opts.title || s.note;
  if (!opts.unstyled) {
    Object.assign(el.style, {
      display: "inline-block",
      font: "10.5px ui-monospace,SFMono-Regular,Menlo,monospace",
      fontWeight: "600", letterSpacing: ".4px",
      padding: "2px 8px", borderRadius: "5px",
      color: s.text, background: s.color,
      border: "1px solid rgba(255,255,255,.12)",
    });
  }
  return el;
}

// Update an existing chip in place (cheap, for live polling).
export function updateChip(el, label, opts = {}) {
  if (!el) return el;
  const s = spec(label);
  el.setAttribute("data-label", s.key);
  el.textContent = opts.text ? (s.key + " · " + opts.text) : s.key;
  el.title = opts.title || s.note;
  if (!opts.unstyled) { el.style.color = s.text; el.style.background = s.color; }
  return el;
}

// ---------------------------------------------------------------------------
// 3D billboard sprite. billboard(THREE, label, opts) -> THREE.Sprite
//   Draws the chip to a canvas texture and returns a camera-facing Sprite, so the
//   honesty label floats next to its 3D value. Pass the page's THREE module in.
//   opts.scale : world units of sprite height (default 0.6)
//   opts.text  : optional extra text after the label
// ---------------------------------------------------------------------------
export function billboard(THREE, label, opts = {}) {
  if (!THREE || !THREE.Sprite) throw new Error("szl3d.billboard: pass the three module as first arg");
  const s = spec(label);
  const str = opts.text ? (s.key + " · " + opts.text) : s.key;
  const pad = 18, fs = 40;
  const cnv = document.createElement("canvas");
  const ctx = cnv.getContext("2d");
  ctx.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  const w = Math.ceil(ctx.measureText(str).width) + pad * 2;
  const h = fs + pad * 2;
  cnv.width = w; cnv.height = h;
  // rounded background
  const r = 10;
  ctx.fillStyle = s.color;
  ctx.beginPath();
  ctx.moveTo(r, 0); ctx.arcTo(w, 0, w, h, r); ctx.arcTo(w, h, 0, h, r);
  ctx.arcTo(0, h, 0, 0, r); ctx.arcTo(0, 0, w, 0, r); ctx.closePath(); ctx.fill();
  ctx.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  ctx.fillStyle = s.text; ctx.textBaseline = "middle";
  ctx.fillText(str, pad, h / 2 + 2);

  const tex = new THREE.CanvasTexture(cnv);
  tex.anisotropy = 4;
  if ("colorSpace" in tex && THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: opts.depthTest !== false });
  const sprite = new THREE.Sprite(mat);
  const scaleH = opts.scale || 0.6;
  sprite.scale.set(scaleH * (w / h), scaleH, 1);
  sprite.userData.szlLabel = s.key;
  if (opts.position && sprite.position.set) sprite.position.set(opts.position[0], opts.position[1], opts.position[2]);
  return sprite;
}

// Legend element listing all 4 doctrine states (handy on every surface).
export function legend(opts = {}) {
  const el = document.createElement("div");
  el.className = "szl3d-label-legend";
  if (!opts.unstyled) Object.assign(el.style, { display: "flex", gap: "6px", flexWrap: "wrap" });
  ["MEASURED", "MODELED", "SAMPLE", "STRUCTURAL-ONLY"].forEach((k) => el.appendChild(chip(k, opts)));
  return el;
}

export default { LABELS, normalize, spec, chip, updateChip, billboard, legend };
