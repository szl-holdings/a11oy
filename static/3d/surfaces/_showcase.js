// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/_showcase.js — SHARED showcase-overlay helper for every holographic surface.
//
// THE PROBLEM THIS SOLVES: sprawling descriptive text + KPI walls were rendered as a big
// always-open panel that covered the canvas ("text taking over the view"), and on phones it
// pushed the 3D subject below the fold. This helper is the ONE reusable fix so every surface
// (Groups A/B/C/D) shows the SAME compact, collapsible, mobile-friendly chrome:
//
//   * default view = 3D scene + a compact title bar + the honesty-badge pill row + a tiny
//     legend. The full descriptive text + KPI readouts live behind an (i) toggle.
//   * desktop → small corner card (top-left). mobile (<=640px) → bottom sheet; collapsed it
//     is just the title bar + pills, so the 3D subject owns the screen above the fold.
//   * honesty labels stay VERBATIM (rendered as small pills via szl3d_label.chip), never
//     hidden, never upgraded.
//   * optional in-scene node labels via createSceneLabels(): hover/tap tooltip + top-N
//     persistent labels only, billboarded (always camera-facing), size-capped, fade with
//     distance — so we never render every label at once (the other half of the text bug).
//
// 0 runtime CDN. Pure DOM + the page's THREE (passed in via ctx). Palette per doctrine v11:
//   lattice-blue #5b8dee · violet-blue #8a6bff · proof-teal #3af4c8 · gold #d7b96b · greys.
//   Void bg #080c14. PURPLE BANNED. Dispose is the caller's job for scene geom; this helper
//   cleans up every DOM node + listener it creates on destroy().
//
// USAGE (see DESIGN_HELPER.md for the full API):
//   import { createShowcase } from "./_showcase.js";
//   const show = createShowcase(ctx, {
//     id: "episodic", title: "Episodic Memory · Temporal KG (live)",
//     badge,                                  // a szl3d_live badge (kept in the pill row)
//     chips: [{ label: "MODELED", text: "graph" }],
//     legend: ["MODELED", "SAMPLE"],          // or true for all 4 doctrine states
//     description: "<b>…</b> full text moved off the canvas …",
//     plain: { html: "<b>What this means:</b> …" },  // optional investor/consumer blurb
//   });
//   const vN = show.addField("episodes in graph"); // KPI row -> value <span>
//   show.setChip(0, "MODELED", { text: "graph" });  // live update a pill
//   … on unmount: show.destroy();

const CSS_ID = "szl-showcase-css";
const PALETTE = Object.freeze({
  void: "#080c14", panel: "rgba(10,17,26,.82)", line: "#1c2836",
  lattice: "#5b8dee", violet: "#8a6bff", proof: "#3af4c8", gold: "#d7b96b",
  cream: "#e7eef6", para: "#9fb1bf", dim: "#6b7a86",
});

// One-time stylesheet inject. Media queries + collapse states can't live in inline styles,
// so the shared classes go here; every surface that imports the helper reuses them.
function _ensureCSS() {
  if (typeof document === "undefined" || document.getElementById(CSS_ID)) return;
  const s = document.createElement("style");
  s.id = CSS_ID;
  s.textContent = `
.szl-show{position:absolute;left:12px;top:12px;z-index:7;
  width:min(90vw,340px);max-height:calc(100% - 24px);
  display:flex;flex-direction:column;
  color:${PALETTE.cream};font:12px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,Arial;
  background:${PALETTE.panel};border:1px solid ${PALETTE.line};border-radius:12px;
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  box-shadow:0 8px 28px rgba(0,0,0,.42);overflow:hidden}
.szl-show__bar{display:flex;align-items:center;gap:9px;padding:9px 11px;flex:0 0 auto}
.szl-show__dot{width:9px;height:9px;border-radius:50%;background:${PALETTE.lattice};
  box-shadow:0 0 8px ${PALETTE.lattice};flex:0 0 auto}
.szl-show__title{font-weight:600;font-size:13px;letter-spacing:.3px;flex:1 1 auto;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.szl-show__toggle{flex:0 0 auto;cursor:pointer;width:27px;height:27px;border-radius:8px;
  border:1px solid ${PALETTE.line};background:#0e1722;color:#9fb6cc;
  font:600 14px ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1;
  display:flex;align-items:center;justify-content:center;transition:.12s}
.szl-show__toggle:hover{border-color:${PALETTE.proof};color:${PALETTE.cream}}
.szl-show__pills{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:0 11px 10px;flex:0 0 auto}
.szl-show__body{padding:0 11px 12px;display:flex;flex-direction:column;gap:10px;
  overflow:auto;-webkit-overflow-scrolling:touch;min-height:0}
.szl-show--collapsed .szl-show__body{display:none}
.szl-show__desc{color:${PALETTE.para};font-size:11px;line-height:1.55}
.szl-show__desc b{color:${PALETTE.cream}}
.szl-show__legend{display:flex;gap:5px;flex-wrap:wrap}
.szl-show__card{background:#0a1117;border:1px solid ${PALETTE.line};border-radius:9px;
  padding:9px 10px;display:flex;flex-direction:column;gap:5px}
.szl-show__row{display:flex;justify-content:space-between;gap:12px;font-size:11px;align-items:baseline}
.szl-show__row .k{color:${PALETTE.para}}
.szl-show__row .v{font-variant-numeric:tabular-nums;color:${PALETTE.cream};text-align:right;
  max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.szl-show__foot{font-size:9.5px;color:${PALETTE.dim};line-height:1.5}
.szl-show__plainbtn{font:11px ui-monospace,Menlo,monospace;padding:5px 11px;border-radius:7px;
  border:1px solid ${PALETTE.proof};background:#08140f;color:${PALETTE.proof};cursor:pointer;width:fit-content}
.szl-show__plain{font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;
  border-radius:7px;padding:7px 9px;display:none}
.szl-show__plain b{color:${PALETTE.cream}}
.szl-show__plain--on{display:block}
/* In-scene hover/tap labels: crisp DOM text projected to the node, always camera-facing. */
.szl-lbl-layer{position:absolute;inset:0;z-index:6;pointer-events:none;overflow:hidden}
.szl-lbl{position:absolute;transform:translate(-50%,-140%);
  font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.2px;
  padding:2px 7px;border-radius:6px;white-space:nowrap;
  background:rgba(8,12,20,.86);border:1px solid ${PALETTE.line};color:${PALETTE.cream};
  box-shadow:0 2px 8px rgba(0,0,0,.4);will-change:transform,opacity}
.szl-lbl--hover{border-color:${PALETTE.proof};color:${PALETTE.proof}}
@media (max-width:640px){
  .szl-show{left:0;right:0;bottom:0;top:auto;width:auto;max-height:62vh;
    border-radius:14px 14px 0 0;border-bottom:none;box-shadow:0 -8px 28px rgba(0,0,0,.5)}
  .szl-show__body{max-height:46vh}
  .szl-show__bar{padding:10px 12px}
  .szl-show__title{font-size:13px}
}
`;
  (document.head || document.documentElement).appendChild(s);
}

function _asNode(x) {
  if (x == null) return null;
  if (typeof x === "string") { const d = document.createElement("div"); d.innerHTML = x; return d; }
  return x; // assume DOM node
}

// ---------------------------------------------------------------------------
// createShowcase(ctx, opts) -> controller
// ---------------------------------------------------------------------------
export function createShowcase(ctx, opts = {}) {
  _ensureCSS();
  const container = (ctx && ctx.container) || document.body;
  const labelMod = ctx && ctx.label;

  const root = document.createElement("div");
  root.className = "szl-show";
  root.setAttribute("data-surface", opts.id || "");
  // Start collapsed by default so the scene is the star; a surface may pass startExpanded.
  let expanded = !!opts.startExpanded;
  if (!expanded) root.classList.add("szl-show--collapsed");

  // --- title bar (always visible): accent dot + title + (i)/× toggle ---------
  const bar = document.createElement("div");
  bar.className = "szl-show__bar";
  const dot = document.createElement("span");
  dot.className = "szl-show__dot";
  if (opts.accent) { dot.style.background = opts.accent; dot.style.boxShadow = "0 0 8px " + opts.accent; }
  const title = document.createElement("div");
  title.className = "szl-show__title";
  title.textContent = opts.title || opts.id || "surface";
  title.title = opts.title || "";
  const toggle = document.createElement("button");
  toggle.className = "szl-show__toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Toggle surface details");
  bar.appendChild(dot); bar.appendChild(title); bar.appendChild(toggle);
  root.appendChild(bar);

  // --- pill row (always visible): live badge + honesty chips + tiny legend ---
  const pills = document.createElement("div");
  pills.className = "szl-show__pills";
  root.appendChild(pills);

  let badge = opts.badge || null;
  if (badge && badge.el) pills.appendChild(badge.el);

  // honesty chips (verbatim) — track them so callers can live-update by index/name
  const chipEls = [];
  const chipNames = [];
  function _addChip(spec) {
    if (!labelMod || !labelMod.chip) return null;
    const el = labelMod.chip(spec.label, { text: spec.text, title: spec.title });
    if (spec.name) chipNames.push(spec.name); else chipNames.push(null);
    chipEls.push(el);
    pills.appendChild(el);
    return el;
  }
  (opts.chips || []).forEach(_addChip);

  // minimal legend — subset (array of tokens) or all 4 doctrine states (true)
  if (opts.legend && labelMod && labelMod.chip) {
    const leg = document.createElement("div");
    leg.className = "szl-show__legend";
    const tokens = Array.isArray(opts.legend)
      ? opts.legend
      : ["MEASURED", "MODELED", "SAMPLE", "STRUCTURAL-ONLY"];
    tokens.forEach((t) => { const c = labelMod.chip(t); c.style.opacity = ".9"; leg.appendChild(c); });
    pills.appendChild(leg);
  }

  // --- collapsible body: description + KPI card + citations + plain-language --
  const body = document.createElement("div");
  body.className = "szl-show__body";
  root.appendChild(body);

  const descNode = _asNode(opts.description);
  if (descNode) { descNode.classList.add("szl-show__desc"); body.appendChild(descNode); }

  // default KPI card (surfaces add rows via addField); created lazily
  let card = null;
  const fields = {};
  function _ensureCard() {
    if (card) return card;
    card = document.createElement("div");
    card.className = "szl-show__card";
    body.appendChild(card);
    return card;
  }
  function addField(label, key) {
    _ensureCard();
    const row = document.createElement("div");
    row.className = "szl-show__row";
    const k = document.createElement("span"); k.className = "k"; k.textContent = label;
    const v = document.createElement("span"); v.className = "v"; v.textContent = "—";
    row.appendChild(k); row.appendChild(v);
    card.appendChild(row);
    if (key) fields[key] = v;
    return v;
  }

  const citeNode = _asNode(opts.citations);
  if (citeNode) { citeNode.classList.add("szl-show__foot"); body.appendChild(citeNode); }

  // optional plain-language ("what this means") toggle inside the body
  let plainBtn = null, plainBox = null, plainOn = false, plainHtmlFn = null;
  if (opts.plain) {
    plainBtn = document.createElement("button");
    plainBtn.type = "button";
    plainBtn.className = "szl-show__plainbtn";
    plainBtn.textContent = opts.plain.label || "◑ what this means";
    plainBox = document.createElement("div");
    plainBox.className = "szl-show__plain";
    plainHtmlFn = (typeof opts.plain === "function") ? opts.plain
      : (typeof opts.plain.html === "function") ? opts.plain.html
      : () => (opts.plain.html || (typeof opts.plain === "string" ? opts.plain : ""));
    plainBtn.addEventListener("click", () => {
      plainOn = !plainOn;
      plainBox.classList.toggle("szl-show__plain--on", plainOn);
      plainBtn.style.background = plainOn ? "#0f2a20" : "#08140f";
      if (plainOn) plainBox.innerHTML = plainHtmlFn() || "";
    });
    body.appendChild(plainBtn);
    body.appendChild(plainBox);
  }

  // --- collapse behaviour ----------------------------------------------------
  function _syncToggle() { toggle.textContent = expanded ? "×" : "ⓘ"; }
  function setExpanded(on) {
    expanded = !!on;
    root.classList.toggle("szl-show--collapsed", !expanded);
    _syncToggle();
    if (expanded && plainOn && plainBox) plainBox.innerHTML = plainHtmlFn ? (plainHtmlFn() || "") : plainBox.innerHTML;
  }
  toggle.addEventListener("click", () => setExpanded(!expanded));
  _syncToggle();

  container.appendChild(root);

  // --- scene-label sub-helper bound to this container ------------------------
  let _labels = null;
  function attachSceneLabels(labelOpts) {
    _labels = createSceneLabels(ctx, labelOpts);
    return _labels;
  }

  function setBadge(b) {
    if (badge && badge.el && badge.el.parentNode) badge.el.parentNode.removeChild(badge.el);
    badge = b;
    if (badge && badge.el) pills.insertBefore(badge.el, pills.firstChild);
  }

  function setChip(ref, label, o = {}) {
    let el = null;
    if (typeof ref === "number") el = chipEls[ref];
    else { const i = chipNames.indexOf(ref); if (i >= 0) el = chipEls[i]; }
    if (el && labelMod && labelMod.updateChip) labelMod.updateChip(el, label, o);
    return el;
  }

  function refreshPlain() {
    if (plainOn && plainBox && plainHtmlFn) plainBox.innerHTML = plainHtmlFn() || "";
  }

  function destroy() {
    try { if (_labels) _labels.destroy(); } catch (_) {}
    _labels = null;
    try { if (root.parentNode) root.parentNode.removeChild(root); } catch (_) {}
  }

  return {
    el: root, bar, pills, body,
    title, toggle,
    addField, field: (k) => fields[k], fields,
    addChip: _addChip, setChip,
    setExpanded, isExpanded: () => expanded,
    setBadge, refreshPlain,
    attachSceneLabels,
    // escape hatch: append custom DOM into the collapsible body
    appendBody: (n) => { const x = _asNode(n); if (x) body.appendChild(x); return x; },
    card: _ensureCard,
    destroy,
  };
}

// ---------------------------------------------------------------------------
// createSceneLabels(ctx, opts) -> controller
//
// In-scene node labels done right: a DOM label layer over the canvas that projects each
// world position to screen every frame (so labels are always camera-facing = "billboarded"),
// fades with camera distance, and shows text ONLY for the top-N most-connected nodes plus a
// single hover/tap tooltip. This is the reusable cure for "every label at once".
//
// opts:
//   objects   : () => THREE.Object3D[]   labelable meshes (called live; may change per poll)
//   text      : (obj) => string          label text for an object (required for any label)
//   weight    : (obj) => number          ranking for top-N (default 0 → insertion order)
//   topN      : number                   how many persistent labels (default 0 = hover-only)
//   hover     : boolean                  enable hover/tap tooltip (default true)
//   fadeNear  : number                   camera distance at full opacity (default 8)
//   fadeFar   : number                   camera distance at min opacity  (default 60)
//   minOpacity: number                   floor opacity for far labels (default 0.15)
//   container : DOM                      overlay host (default ctx.container)
// ---------------------------------------------------------------------------
export function createSceneLabels(ctx, opts = {}) {
  _ensureCSS();
  const THREE = ctx.THREE;
  const stage = ctx.stage;
  const container = opts.container || ctx.container || document.body;
  const canvas = stage && stage.renderer && stage.renderer.domElement;
  const camera = stage && stage.camera;
  if (!THREE || !stage || !camera) {
    return { update() {}, destroy() {}, setObjects() {} };
  }

  const getObjects = typeof opts.objects === "function" ? opts.objects : () => [];
  const getText = typeof opts.text === "function" ? opts.text : (o) => (o && o.userData && o.userData.label) || "";
  const getWeight = typeof opts.weight === "function" ? opts.weight : () => 0;
  const topN = Math.max(0, opts.topN || 0);
  const hoverOn = opts.hover !== false;
  const fadeNear = opts.fadeNear != null ? opts.fadeNear : 8;
  const fadeFar = opts.fadeFar != null ? opts.fadeFar : 60;
  const minOpacity = opts.minOpacity != null ? opts.minOpacity : 0.15;

  const layer = document.createElement("div");
  layer.className = "szl-lbl-layer";
  container.appendChild(layer);

  // pool of persistent DOM labels for the top-N
  const pool = [];
  for (let i = 0; i < topN; i++) {
    const el = document.createElement("div");
    el.className = "szl-lbl";
    el.style.display = "none";
    layer.appendChild(el);
    pool.push(el);
  }
  // single hover label
  const hoverEl = document.createElement("div");
  hoverEl.className = "szl-lbl szl-lbl--hover";
  hoverEl.style.display = "none";
  layer.appendChild(hoverEl);

  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const proj = new THREE.Vector3();
  let hovered = null, hoverText = "";

  function _rect() { return (canvas && canvas.getBoundingClientRect) ? canvas.getBoundingClientRect() : container.getBoundingClientRect(); }

  function _pick(clientX, clientY) {
    const r = _rect();
    ndc.x = ((clientX - r.left) / Math.max(1, r.width)) * 2 - 1;
    ndc.y = -((clientY - r.top) / Math.max(1, r.height)) * 2 + 1;
    ray.setFromCamera(ndc, camera);
    const objs = getObjects();
    const hits = ray.intersectObjects(objs, true);
    if (!hits.length) return null;
    // walk up to the object that is actually in the labelable set
    let o = hits[0].object;
    const set = new Set(objs);
    while (o && !set.has(o)) o = o.parent;
    return o || hits[0].object;
  }

  function _onMove(e) {
    if (!hoverOn) return;
    const p = ("touches" in e && e.touches[0]) || e;
    const o = _pick(p.clientX, p.clientY);
    hovered = o;
    hoverText = o ? (getText(o) || "") : "";
    if (!o || !hoverText) hoverEl.style.display = "none";
  }
  function _onLeave() { hovered = null; hoverEl.style.display = "none"; }

  if (hoverOn && canvas) {
    canvas.addEventListener("pointermove", _onMove, { passive: true });
    canvas.addEventListener("pointerdown", _onMove, { passive: true });
    canvas.addEventListener("pointerleave", _onLeave, { passive: true });
  }

  function _place(el, obj, text, isHover) {
    if (!obj) { el.style.display = "none"; return; }
    obj.getWorldPosition(proj);
    const dist = camera.position.distanceTo(proj);
    proj.project(camera);
    if (proj.z > 1) { el.style.display = "none"; return; } // behind camera
    const r = _rect();
    const x = (proj.x * 0.5 + 0.5) * r.width;
    const y = (-proj.y * 0.5 + 0.5) * r.height;
    // fade with distance, size-capped (font stays fixed → size cap)
    let op = 1;
    if (dist > fadeNear) op = Math.max(minOpacity, 1 - (dist - fadeNear) / Math.max(1, fadeFar - fadeNear));
    el.textContent = text;
    el.style.left = x + "px";
    el.style.top = y + "px";
    el.style.opacity = String(isHover ? Math.max(op, 0.9) : op);
    el.style.display = "block";
  }

  function update() {
    const objs = getObjects();
    // persistent top-N by weight
    if (topN) {
      const ranked = objs
        .map((o) => ({ o, w: getWeight(o) }))
        .sort((a, b) => b.w - a.w)
        .slice(0, topN);
      for (let i = 0; i < pool.length; i++) {
        const item = ranked[i];
        if (item && item.o) _place(pool[i], item.o, getText(item.o) || "", false);
        else pool[i].style.display = "none";
      }
    }
    // hover/tap label
    if (hoverOn && hovered && hoverText) _place(hoverEl, hovered, hoverText, true);
    else hoverEl.style.display = "none";
  }

  // drive updates off the stage frame loop
  let _reg = true;
  stage.onFrame(function _lblFrame() { if (_reg) update(); });

  function destroy() {
    _reg = false;
    if (hoverOn && canvas) {
      canvas.removeEventListener("pointermove", _onMove);
      canvas.removeEventListener("pointerdown", _onMove);
      canvas.removeEventListener("pointerleave", _onLeave);
    }
    try { if (layer.parentNode) layer.parentNode.removeChild(layer); } catch (_) {}
  }

  return { update, destroy, setObjects() {} };
}

export default { createShowcase, createSceneLabels, PALETTE };
