// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainlocal.js — BRAIN LOCAL. An honest liveness+capability probe of the
// LOCAL OpenAI-compatible inference endpoint the brain can be wired to (Ollama on
// 127.0.0.1:11434, a llama.cpp llama-server, or either behind a cloudflared tunnel,
// reached via the SZL_LOCAL_LLM_URL env var). It reads GET /brain/local and renders
// one pillar per configured node plus a bead per model the endpoint NAMED ITSELF.
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * env unset  -> UNAVAILABLE. Nothing is drawn as live and NO model is named.
//   * node answered THIS request -> LIVE, label MEASURED, models echoed verbatim.
//   * node answered but named no model -> DEGRADED (grey), never drawn as healthy.
//   * timeout / refused / error -> UNAVAILABLE (grey). Never a fabricated model.
//   * A11OY_JPT_MODELS declarations are MODELED and shown separately — a declared
//     tag is never counted as served.
//   * Λ = Conjecture 1 → GREY, never green. locked-proven = exactly 8.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brainlocal";
const TITLE = "Brain Local — local inference endpoint liveness";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_PROBE    = "/api/a11oy/v1/brain/local";
const EP_INFO     = "/api/a11oy/v1/brain/local/info";
const EP_MANIFEST = "/api/a11oy/v1/brain/brainlocal/manifest";

// palette (doctrine v11) — NO purple
const C_LIVE   = 0x3af4c8;  // proof-teal — a node that answered THIS request
const C_MODEL  = 0x5b8dee;  // lattice-blue — a model the endpoint named itself
const C_DECL   = 0x8a6bff;  // violet-blue — an operator declaration (MODELED)
const C_GREY   = 0x5a6570;  // GREY — DEGRADED / UNAVAILABLE — never green
const C_BASE   = 0x2a3138;  // dim GREY base plinth

const MAX_PILLARS = 8;
const MAX_BEADS   = 12;

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;

// scene objects
let _boxGeo = null, _beadGeo = null;
let _meshes = [];

const S = {
  label: "UNAVAILABLE", state: "idle",
  verdict: "UNAVAILABLE", verdictReason: null,
  nodes: [], served: [], declared: [], declaredNotServed: [],
  configured: false, liveNodes: 0, nodeCount: 0,
  note: null,
};

// -------------------------------------------------------------------------- //
// mount
// -------------------------------------------------------------------------- //
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  _boxGeo = new _THREE.BoxGeometry(1, 1, 1);
  _beadGeo = new _THREE.SphereGeometry(0.28, 14, 12);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  if (_show) {
    _show.attachSceneLabels({
      objects: () => _meshes,
      text: (o) => (o.userData && o.userData.name) || "",
      weight: (o) => (o.userData && o.userData.weight) || 0,
      topN: 8, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  _fetchProbe();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j, fallback) {
  const lbl = (j && j.label != null) ? j.label : (fallback || "UNAVAILABLE");
  return String(lbl).toUpperCase();
}

function _setBadge(state) {
  S.state = state;
  if (_badge && _badge.set) { try { _badge.set(state); } catch (_) {} }
}

// -------------------------------------------------------------------------- //
// data — GET the bounded live probe; mints nothing.
// -------------------------------------------------------------------------- //
function _fetchProbe() {
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  fetch(EP_PROBE, { headers: { accept: "application/json" },
                    signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok || r.status === 200 ? r.json() : r.json()))
    .then((j) => { _inFlight = null; _onProbe(j); })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      _inFlight = null;
      S.state = "error"; _setBadge("error"); _paintOverlay();
    });
}

function _onProbe(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  S.label = _readLabel(j, "UNAVAILABLE");
  S.verdict = String(j.verdict || j.status || "UNAVAILABLE").toUpperCase();
  S.verdictReason = j.verdict_reason || null;
  S.nodes = Array.isArray(j.nodes) ? j.nodes.slice(0, MAX_PILLARS) : [];
  S.served = Array.isArray(j.served_models) ? j.served_models.slice(0, MAX_BEADS) : [];
  S.declared = Array.isArray(j.declared_models) ? j.declared_models : [];
  S.declaredNotServed = Array.isArray(j.declared_not_served) ? j.declared_not_served : [];
  S.configured = !!(j.config && j.config.configured);
  S.liveNodes = j.live_node_count || 0;
  S.nodeCount = j.node_count || S.nodes.length;
  S.note = j.note || null;
  S.state = "live"; _setBadge(S.verdict === "LIVE" ? "live" : "idle");
  _rebuild(); _paintOverlay();
}

// -------------------------------------------------------------------------- //
// build: one pillar per configured node, one bead per NAMED model
// -------------------------------------------------------------------------- //
function _nodeColor(node) {
  const status = String((node && node.status) || "UNAVAILABLE").toUpperCase();
  if (status === "LIVE") return C_LIVE;
  return C_GREY;   // DEGRADED and UNAVAILABLE are both grey — never drawn healthy
}

function _rebuild() {
  if (!_group) return;
  _clearScene();

  // base grid marker — always present so an UNAVAILABLE read still renders a frame
  const baseMat = new _THREE.MeshStandardMaterial({
    color: C_BASE, emissive: C_BASE, emissiveIntensity: 0.1,
    metalness: 0.1, roughness: 0.8, transparent: true, opacity: 0.5,
  });
  const plinth = new _THREE.Mesh(_boxGeo, baseMat);
  plinth.scale.set(13.0, 0.12, 3.0);
  plinth.position.set(0, -3.1, 0);
  plinth.userData = { name: "", weight: 0 };
  _meshes.push(plinth);
  _group.add(plinth);

  const nodes = S.nodes || [];
  const n = nodes.length;
  const spread = 10.0;

  nodes.forEach((node, i) => {
    const served = (node.served_models || []).slice(0, MAX_BEADS);
    const color = _nodeColor(node);
    const h = 1.0 + 1.1 * Math.min(6, served.length);   // height = models NAMED
    const mat = new _THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.22,
      metalness: 0.12, roughness: 0.5, transparent: true, opacity: 0.95,
    });
    const mesh = new _THREE.Mesh(_boxGeo, mat);
    mesh.scale.set(0.8, h, 0.8);
    const x = (n === 1) ? 0 : (-spread / 2 + spread * (i / (n - 1)));
    mesh.position.set(x, h / 2 - 3.0, 0);
    mesh.userData = {
      name: String(node.endpoint || "node") + " · " + String(node.status || ""),
      weight: served.length, baseGlow: 0.22,
    };
    _meshes.push(mesh);
    _group.add(mesh);

    // one bead per model the endpoint NAMED ITSELF — never a placeholder bead
    served.forEach((name, k) => {
      const bmat = new _THREE.MeshStandardMaterial({
        color: C_MODEL, emissive: C_MODEL, emissiveIntensity: 0.3,
        metalness: 0.2, roughness: 0.4,
      });
      const bead = new _THREE.Mesh(_beadGeo, bmat);
      bead.position.set(x, h - 3.0 + 0.55 + k * 0.62, 1.05);
      bead.userData = { name, weight: 1, baseGlow: 0.3 };
      _meshes.push(bead);
      _group.add(bead);
    });
  });

  // declared-but-not-served tags float BEHIND in violet-blue: MODELED, not evidence
  (S.declaredNotServed || []).slice(0, MAX_BEADS).forEach((name, k) => {
    const dmat = new _THREE.MeshStandardMaterial({
      color: C_DECL, emissive: C_DECL, emissiveIntensity: 0.18,
      metalness: 0.1, roughness: 0.6, transparent: true, opacity: 0.6,
    });
    const bead = new _THREE.Mesh(_beadGeo, dmat);
    bead.position.set(-spread / 2 + k * 0.8, -2.4, -2.2);
    bead.userData = { name: name + " (declared, not served)", weight: 0, baseGlow: 0.18 };
    _meshes.push(bead);
    _group.add(bead);
  });
}

function _clearScene() {
  _meshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _meshes = [];
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + soft breathing glow
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = Math.sin(t * 0.08) * 0.4;
  const pulse = 0.5 + 0.5 * Math.sin(t * 1.5);
  _meshes.forEach((m) => {
    if (!m.material) return;
    const base = m.userData.baseGlow || 0.15;
    m.material.emissiveIntensity = base * (0.8 + 0.3 * pulse);
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper)
// -------------------------------------------------------------------------- //
const _el = {};

function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", startExpanded: true,
    chips: [{ label: "UNAVAILABLE", text: "probe", name: "src" }],
    legend: ["MEASURED", "MODELED", "DEGRADED", "UNAVAILABLE"],
    description:
      "<b>Is a local model actually reachable right now?</b> The server reads " +
      "<code>SZL_LOCAL_LLM_URL</code> (plus <code>A11OY_JPT_GPU_URLS</code>) and, on this " +
      "request, does one short bounded GET of the endpoint's own model listing " +
      "(<code>/v1/models</code>, then <code>/api/tags</code>). If a node answers, the " +
      "verdict is <b>LIVE</b> with label <b>MEASURED</b> and the model names are echoed " +
      "<b>verbatim from the endpoint</b>. If nothing is configured, or the node times out " +
      "or refuses, the verdict is honestly <b>UNAVAILABLE</b> — no model is named and " +
      "nothing is shown as wired. A node that answers but lists no model is " +
      "<b>DEGRADED</b>, drawn grey, never as healthy. Tags from " +
      "<code>A11OY_JPT_MODELS</code> are operator declarations (<b>MODELED</b>) and are " +
      "kept out of the served list.",
    citations:
      "Probe is LIVE from /api/a11oy/v1/brain/local (pure read — no signing on GET, no " +
      "inference, nothing stored); the self-describing manifest is at " +
      EP_INFO + " and the wall-readable honesty manifest at " + EP_MANIFEST + ". " +
      "Λ = Conjecture 1 (grey, never proven green); nothing here touches the locked-8.",
    plain: { html: _plainHtml },
  });

  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;gap:6px;align-items:center";
  const refBtn = document.createElement("button");
  refBtn.type = "button";
  refBtn.textContent = "re-probe";
  refBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  refBtn.addEventListener("click", () => _fetchProbe());
  wrap.appendChild(refBtn);
  _show.appendBody(wrap);

  _el.verdict  = _show.addField("Verdict");
  _el.label    = _show.addField("Label");
  _el.conf     = _show.addField("Endpoint configured");
  _el.nodes    = _show.addField("Nodes live / configured");
  _el.served   = _show.addField("Models served (verbatim)");
  _el.declared = _show.addField("Declared (MODELED)");

  _el.list = document.createElement("div");
  _el.list.style.cssText =
    "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf";
  _show.appendBody(_el.list);

  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "UNAVAILABLE", { text: "probe" });

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const loading = S.state === "loading";

  set("verdict", loading ? "probing…" : S.verdict);
  set("label", loading ? "…" : (S.label || "UNAVAILABLE"));
  set("conf", loading ? "…" : (S.configured ? "yes" : "no — nothing to probe"));
  set("nodes", loading ? "…" : (_fmt(S.liveNodes) + " / " + _fmt(S.nodeCount)));
  set("served", loading ? "…"
      : (S.served.length ? String(S.served.length) : "0 — none named"));
  set("declared", loading ? "…"
      : (S.declared.length ? String(S.declared.length) +
         (S.declaredNotServed.length ? " (" + S.declaredNotServed.length + " not served)" : "")
       : "0"));

  if (_el.list) {
    _el.list.textContent = "";
    (S.served || []).forEach((name) => {
      const line = document.createElement("div");
      line.style.cssText =
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#a9c4dd";
      line.textContent = "· " + name + " — MEASURED (named by the endpoint)";
      _el.list.appendChild(line);
    });
    (S.declaredNotServed || []).forEach((name) => {
      const line = document.createElement("div");
      line.style.cssText =
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#8a94a0";
      line.textContent = "· " + name + " — declared, NOT served (MODELED)";
      _el.list.appendChild(line);
    });
  }

  if (_el.note) {
    let note = S.note || "";
    if (S.state === "error") note = "probe error — the brain-local API did not respond.";
    else if (S.verdictReason) note = S.verdictReason + (note ? "  " + note : "");
    _el.note.textContent = note;
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "This checks one thing: can we reach a model running on our OWN hardware right now? " +
    "The server looks for an address in its environment and, if it finds one, asks that " +
    "address to list its models. If the answer comes back, we show <b>LIVE</b> and print " +
    "the model names exactly as the machine reported them — that reading is " +
    "<b>MEASURED</b>. If there is no address, or the machine is asleep or unreachable, we " +
    "say <b>UNAVAILABLE</b> and name no model at all, rather than pretend a model is " +
    "hooked up. Nothing is generated and nothing is saved here. Label <b>" +
    (S.label || "UNAVAILABLE") + "</b>."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  try { if (_inFlight && _inFlight.abort) _inFlight.abort(); } catch (_) {}
  _inFlight = null;
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearScene(); } catch (_) {}
  try { if (_boxGeo) _boxGeo.dispose(); } catch (_) {}
  try { if (_beadGeo) _beadGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _boxGeo = _beadGeo = null;
  _group = _show = _badge = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = "UNAVAILABLE"; S.state = "idle";
  S.verdict = "UNAVAILABLE"; S.verdictReason = null;
  S.nodes = []; S.served = []; S.declared = []; S.declaredNotServed = [];
  S.configured = false; S.liveNodes = 0; S.nodeCount = 0; S.note = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_PROBE, EP_INFO, EP_MANIFEST], mount, unmount };
