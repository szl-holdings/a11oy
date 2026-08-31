// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/agentops.js — AGENT OPS: the BOUNDED operate loop, in 3D. The companion
// to governedagent.js (which COMPOSES the siloed primitives into ONE composite
// receipt): this surface visualizes the OPERATE primitive — a minimal, HARD-bounded
// Ouroboros recursion that GROUNDS every step on the real brain graph and JUDGES it
// with a deterministic doctrine gate that never generates (writer≠judge).
//
// THE RING (Ouroboros — never unbounded): four stage nodes on a closed ring
//   GROUND → ACT → SELF-EVAL → GATE → (retry back to GROUND)
// The recursion BOUND is shown explicitly (step-cap × (1+retry-cap) = max actions).
// After a run, each planned step drops a satellite whose colour reads its honest
// status: teal = ACCEPTED, grey = EXHAUSTED, dim-blue = GATED (doctrine deny).
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * grounding is REAL (brain PPR via /agent/status → /agent/operate); a generated
//     action is LIVE only if a sovereign model answered, else verbatim UNAVAILABLE.
//   * the loop NEVER shows a fabricated ACCEPTED — with no model the honest final
//     status is EXHAUSTED, and that is exactly what is drawn.
//   * Λ = Conjecture 1 → GREY, never green. locked-8 untouched. trust ≤ 0.97.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "agentops";
const TITLE = "Agent Ops — bounded operate loop";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_STATUS  = "/api/a11oy/v1/agent/status";
const EP_OPERATE = "/api/a11oy/v1/agent/operate";

// palette (doctrine v11) — NO purple
const C_GROUND = 0x5b8dee;  // lattice-blue — GROUND (brain retrieval)
const C_ACT    = 0x8a6bff;  // violet-blue — ACT (writer / sovereign model)
const C_EVAL   = 0x5b8dee;  // lattice-blue — SELF-EVAL (heuristic)
const C_GATE   = 0x3af4c8;  // proof-teal — GATE (deterministic judge)
const C_RING   = 0x1b3a44;  // dim link — the Ouroboros ring
const C_RETRY  = 0x3a5a8c;  // dim lattice — the retry return arc
const C_ACCEPT = 0x3af4c8;  // proof-teal — ACCEPTED step
const C_GATED  = 0x5b8dee;  // lattice-blue — GATED step (doctrine deny)
const C_EXH    = 0x5a6570;  // GREY — EXHAUSTED (e.g. model UNAVAILABLE)

const STAGES = [
  { key: "ground", name: "GROUND",    color: C_GROUND },
  { key: "act",    name: "ACT",       color: C_ACT },
  { key: "eval",   name: "SELF-EVAL", color: C_EVAL },
  { key: "gate",   name: "GATE",      color: C_GATE },
];

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;

// scene objects
let _stageGeo = null, _satGeo = null;
let _stageMeshes = [];    // the 4 ring stage nodes (labelable)
let _satMeshes = [];      // per-step satellites (labelable)
let _ring = null, _ringGeo = null, _ringMat = null;
let _retryArc = null, _retryGeo = null, _retryMat = null;
let _stagePos = [];       // Vector3 per stage

// overlay DOM
let _input = null, _runBtn = null, _traceEl = null, _onKey = null;
const _el = {};

const S = {
  label: "MODELED", state: "idle",
  // config (from /status)
  stepCap: null, retryCap: null, maxActions: null,
  brainAvailable: null, gateAvailable: null, sovereignReady: null,
  // last run (from /status or a fresh /operate)
  goal: "", finalStatus: null, plannedSteps: null, actionsUsed: null,
  modelReachable: null, runId: null, runDigest: null, steps: null,
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
  _stageGeo = new _THREE.SphereGeometry(1, 20, 16);
  _satGeo = new _THREE.SphereGeometry(1, 12, 10);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  _buildRing();

  if (_show) {
    _show.attachSceneLabels({
      objects: () => _stageMeshes.concat(_satMeshes),
      text: (o) => (o.userData && o.userData.label) || "",
      weight: (o) => (o.userData && o.userData.weight) || 0,
      topN: 8, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  // one-shot config + last-run probe (GET — pure read, no signing).
  _fetchStatus();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j, fallback) {
  const lbl = (j && j.label != null) ? j.label : (fallback || "MODELED");
  return String(lbl).toUpperCase();
}

function _setBadge(state) {
  S.state = state;
  if (_badge && _badge.set) { try { _badge.set(state); } catch (_) {} }
}

// -------------------------------------------------------------------------- //
// data
// -------------------------------------------------------------------------- //
function _fetchStatus() {
  fetch(EP_STATUS, { headers: { accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => {
      const bl = j.bounded_loop || {};
      S.stepCap = bl.step_cap; S.retryCap = bl.retry_cap; S.maxActions = bl.max_actions;
      const g = j.grounding || {};
      S.brainAvailable = !!g.brain_available;
      S.gateAvailable = !!j.gate_available;
      S.sovereignReady = !!j.sovereign_writer_ready;
      const lr = j.last_run;
      if (lr) {
        S.goal = lr.goal || "";
        S.finalStatus = lr.final_status || null;
        S.plannedSteps = lr.planned_steps;
        S.actionsUsed = lr.actions_used;
        S.modelReachable = !!lr.model_reachable;
        S.runId = lr.run_id || null;
        S.runDigest = lr.run_digest || null;
      }
      S.state = "live";
      _setBadge("live");
      _rebuildSatellites();
      _paintOverlay();
    })
    .catch(() => { S.state = "idle"; _setBadge("idle"); _paintOverlay(); });
}

function _operate(goal) {
  goal = (goal || "").trim();
  if (!goal) return;
  S.goal = goal;
  if (_input && _input.value !== goal) _input.value = goal;
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  const url = EP_OPERATE + "?goal=" + encodeURIComponent(goal);
  fetch(url, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ goal: goal }),
    signal: ctrl ? ctrl.signal : undefined,
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => { _inFlight = null; _onOperate(j); })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      _inFlight = null;
      S.state = "error"; _setBadge("error"); _paintOverlay();
    });
}

function _onOperate(j) {
  if (!j || !j.ok) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  S.label = _readLabel(j, "MODELED");
  const b = j.bounded || {};
  S.stepCap = b.step_cap; S.retryCap = b.retry_cap; S.maxActions = b.max_actions;
  S.actionsUsed = b.actions_used; S.plannedSteps = b.planned_steps;
  S.finalStatus = j.final_status || null;
  S.modelReachable = !!j.model_reachable;
  S.runId = j.run_id || null;
  S.runDigest = j.run_digest || null;
  S.steps = Array.isArray(j.steps) ? j.steps : [];
  S.note = j.honesty || null;
  S.state = "live";
  _setBadge("live");
  _rebuildSatellites();
  _paintOverlay();
}

// -------------------------------------------------------------------------- //
// build: the Ouroboros ring (4 stages + retry return arc)
// -------------------------------------------------------------------------- //
function _buildRing() {
  _stagePos = [];
  const R = 6.0;
  STAGES.forEach((st, i) => {
    const theta = -Math.PI / 2 + i * (2 * Math.PI / STAGES.length);
    const p = new _THREE.Vector3(R * Math.cos(theta), R * Math.sin(theta), 0);
    _stagePos.push(p);
    const mat = new _THREE.MeshStandardMaterial({
      color: st.color, emissive: st.color, emissiveIntensity: 0.35,
      metalness: 0.15, roughness: 0.4, transparent: true, opacity: 0.95,
    });
    const mesh = new _THREE.Mesh(_stageGeo, mat);
    mesh.scale.setScalar(0.9);
    mesh.position.copy(p);
    mesh.userData = { label: st.name, weight: 1, stage: st.key, baseGlow: 0.35 };
    _stageMeshes.push(mesh);
    _group.add(mesh);
  });

  // the closed ring polyline (Ouroboros)
  const pts = [];
  const segs = 96;
  for (let i = 0; i <= segs; i++) {
    const theta = -Math.PI / 2 + (i / segs) * 2 * Math.PI;
    pts.push(R * Math.cos(theta), R * Math.sin(theta), 0);
  }
  _ringGeo = new _THREE.BufferGeometry();
  _ringGeo.setAttribute("position", new _THREE.Float32BufferAttribute(pts, 3));
  _ringMat = new _THREE.LineBasicMaterial({ color: C_RING, transparent: true, opacity: 0.55 });
  _ring = new _THREE.Line(_ringGeo, _ringMat);
  _group.add(_ring);

  // the retry return arc: GATE → GROUND (an inner chord marking bounded re-entry)
  const gate = _stagePos[3], ground = _stagePos[0];
  const mid = gate.clone().add(ground).multiplyScalar(0.5).multiplyScalar(0.35);
  const arc = [];
  const asegs = 32;
  for (let i = 0; i <= asegs; i++) {
    const t = i / asegs;
    // quadratic bezier gate→mid→ground
    const x = (1 - t) * (1 - t) * gate.x + 2 * (1 - t) * t * mid.x + t * t * ground.x;
    const y = (1 - t) * (1 - t) * gate.y + 2 * (1 - t) * t * mid.y + t * t * ground.y;
    arc.push(x, y, 0.4);
  }
  _retryGeo = new _THREE.BufferGeometry();
  _retryGeo.setAttribute("position", new _THREE.Float32BufferAttribute(arc, 3));
  _retryMat = new _THREE.LineDashedMaterial({
    color: C_RETRY, transparent: true, opacity: 0.6, dashSize: 0.4, gapSize: 0.3,
  });
  _retryArc = new _THREE.Line(_retryGeo, _retryMat);
  if (_retryArc.computeLineDistances) _retryArc.computeLineDistances();
  _group.add(_retryArc);
}

function _statusColor(st) {
  if (st === "ACCEPTED") return C_ACCEPT;
  if (st === "GATED") return C_GATED;
  return C_EXH;   // EXHAUSTED (or unknown) → honest grey
}

// per-step satellites orbit just outside the ring; colour = honest step status.
function _rebuildSatellites() {
  _clearSatellites();
  const steps = S.steps;
  const n = (steps && steps.length) ? steps.length
          : (S.plannedSteps || 0);
  if (!n) return;
  const R = 8.4;
  for (let i = 0; i < n; i++) {
    const theta = -Math.PI / 2 + (i / Math.max(1, n)) * 2 * Math.PI;
    const st = steps && steps[i] ? steps[i].status : null;
    const col = _statusColor(st);
    const mat = new _THREE.MeshStandardMaterial({
      color: col, emissive: col, emissiveIntensity: st ? 0.5 : 0.12,
      metalness: 0.1, roughness: 0.5, transparent: true, opacity: st ? 0.95 : 0.5,
    });
    const mesh = new _THREE.Mesh(_satGeo, mat);
    mesh.scale.setScalar(0.42);
    mesh.position.set(R * Math.cos(theta), R * Math.sin(theta), 0.2);
    const na = steps && steps[i] ? steps[i].n_attempts : null;
    mesh.userData = {
      label: "step " + (i + 1) + (st ? " · " + st : "") + (na ? " (" + na + "×)" : ""),
      weight: 0.5, baseGlow: mat.emissiveIntensity,
    };
    _satMeshes.push(mesh);
    _group.add(mesh);
  }
}

function _clearSatellites() {
  _satMeshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _satMeshes = [];
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + a pulse travelling GROUND→ACT→EVAL→GATE
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.z = Math.sin(t * 0.06) * 0.12;
  const active = Math.floor(t * 0.9) % STAGES.length;   // the travelling pulse
  _stageMeshes.forEach((m, i) => {
    if (!m.material) return;
    const base = m.userData.baseGlow || 0.35;
    m.material.emissiveIntensity = (i === active) ? base + 0.55 : base;
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper) + the goal box
// -------------------------------------------------------------------------- //
function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", startExpanded: true,
    chips: [{ label: "MODELED", text: "plan", name: "src" }],
    legend: ["LIVE", "MODELED", "STRUCTURAL-ONLY", "UNAVAILABLE"],
    description:
      "<b>The bounded operate loop.</b> Give it a goal and it runs a HARD-bounded " +
      "Ouroboros recursion: <b>GROUND</b> (real brain PageRank retrieval) → <b>ACT</b> " +
      "(a sovereign model proposes an action over that grounding) → <b>SELF-EVAL</b> " +
      "(a deterministic structural self-critique) → <b>GATE</b> (a file-backed doctrine " +
      "judge — Colang flows + codename scan — that never generates, so <b>writer≠judge</b>). " +
      "Each step retries within the bound; the loop can never exceed " +
      "<b>step-cap × (1+retry-cap)</b> actions. With no sovereign model the action is " +
      "honestly <b>UNAVAILABLE</b> and the final status is <b>EXHAUSTED</b> — never a " +
      "fabricated ACCEPTED. Satellites read each step's status: teal = ACCEPTED, " +
      "blue = GATED (doctrine deny), grey = EXHAUSTED.",
    citations:
      "Config + last run are LIVE from /api/a11oy/v1/agent/status (pure read — no signing " +
      "on GET). A run POSTs /api/a11oy/v1/agent/operate?goal= and returns per-step SHA-256 " +
      "hash-chained receipts (receipt-on-write). Grounding is REAL brain PPR regardless of " +
      "model. Λ = Conjecture 1 (grey, never proven green). locked-8 untouched; trust ≤ 0.97.",
    plain: { html: _plainHtml },
  });

  // --- the goal box (custom DOM into the collapsible body) ----------------- //
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;flex-direction:column;gap:7px";
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:6px";
  _input = document.createElement("input");
  _input.type = "text";
  _input.placeholder = "goal… (e.g. explain the estate thesis)";
  _input.setAttribute("aria-label", "Goal for the operate loop");
  _input.style.cssText =
    "flex:1 1 auto;min-width:0;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;" +
    "padding:7px 9px;border-radius:8px;border:1px solid #1c2836;background:#0a1117;" +
    "color:#e7eef6;outline:none";
  _runBtn = document.createElement("button");
  _runBtn.type = "button";
  _runBtn.textContent = "operate";
  _runBtn.style.cssText =
    "flex:0 0 auto;font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  _onKey = (e) => { if (e.key === "Enter") { e.preventDefault(); _operate(_input.value); } };
  _input.addEventListener("keydown", _onKey);
  _runBtn.addEventListener("click", () => _operate(_input.value));
  row.appendChild(_input); row.appendChild(_runBtn);
  wrap.appendChild(row);
  _show.appendBody(wrap);

  // KPI rows
  _el.bound     = _show.addField("Recursion bound");
  _el.actions   = _show.addField("Actions used");
  _el.final     = _show.addField("Final status");
  _el.model     = _show.addField("Writer (model)");
  _el.brain     = _show.addField("Grounding (brain)");
  _el.gate      = _show.addField("Judge (gate)");
  _el.digest    = _show.addField("Run digest");

  // per-step trace list
  _traceEl = document.createElement("div");
  _traceEl.style.cssText = "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf";
  _show.appendBody(_traceEl);

  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "MODELED", { text: "plan" });

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const bound = (S.stepCap != null && S.retryCap != null && S.maxActions != null)
    ? (S.stepCap + " steps × (1+" + S.retryCap + " retries) = " + S.maxActions + " max")
    : "—";
  set("bound", bound);
  set("actions", S.state === "loading" ? "operating…"
      : (S.actionsUsed != null && S.maxActions != null)
        ? (_fmt(S.actionsUsed) + " / " + _fmt(S.maxActions))
        : "—");
  set("final", S.state === "loading" ? "operating…" : (S.finalStatus || "—"));
  set("model", S.sovereignReady == null ? "—"
      : (S.modelReachable ? "LIVE"
         : (S.sovereignReady ? "ready (idle)" : "UNAVAILABLE (no local model)")));
  set("brain", S.brainAvailable == null ? "—" : (S.brainAvailable ? "LIVE (PPR)" : "UNAVAILABLE"));
  set("gate", S.gateAvailable == null ? "—"
      : (S.gateAvailable ? "STRUCTURAL (Colang+codename)" : "UNAVAILABLE (fail-closed)"));
  set("digest", S.runDigest ? (String(S.runDigest).slice(0, 16) + "…") : "—");
  if (_el.note) _el.note.textContent = S.note || "";

  // per-step trace
  if (_traceEl) {
    _traceEl.textContent = "";
    const steps = S.steps || [];
    steps.slice(0, 8).forEach((s, i) => {
      const line = document.createElement("div");
      line.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
      const st = s.status || "?";
      const na = s.n_attempts != null ? (" · " + s.n_attempts + "×") : "";
      const dot = (st === "ACCEPTED") ? "●" : (st === "GATED") ? "◐" : "○";
      line.textContent = dot + " step " + (i + 1) + ": " + st + na;
      line.title = (s.plan_line || "") + " — receipt " + String(s.receipt || "").slice(0, 12);
      _traceEl.appendChild(line);
    });
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "Give the agent a <b>goal</b> and watch it work in a tight, safe loop that can " +
    "<b>never run away</b>: it looks things up in our estate's brain, proposes a step, " +
    "checks its own work, then hands the step to a separate <b>rule-checker</b> that can " +
    "only say allow or deny (it can't be argued with). It repeats — but only up to a fixed " +
    "number of tries, shown here as the <b>recursion bound</b>. If we don't have a private " +
    "AI model running, the loop honestly reports <b>UNAVAILABLE / EXHAUSTED</b> instead of " +
    "pretending it succeeded. Every step leaves a tamper-evident fingerprint. " +
    "Label <b>" + (S.label || "MODELED") + "</b>."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  try { if (_inFlight && _inFlight.abort) _inFlight.abort(); } catch (_) {}
  _inFlight = null;
  try { if (_input && _onKey) _input.removeEventListener("keydown", _onKey); } catch (_) {}
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearSatellites(); } catch (_) {}
  _stageMeshes.forEach((m) => { if (m.material && m.material.dispose) m.material.dispose(); });
  _stageMeshes = [];
  try { if (_ring) _group.remove(_ring); } catch (_) {}
  try { if (_retryArc) _group.remove(_retryArc); } catch (_) {}
  if (_ringGeo) _ringGeo.dispose(); if (_ringMat) _ringMat.dispose();
  if (_retryGeo) _retryGeo.dispose(); if (_retryMat) _retryMat.dispose();
  _ring = _ringGeo = _ringMat = _retryArc = _retryGeo = _retryMat = null;
  try { if (_stageGeo) _stageGeo.dispose(); } catch (_) {}
  try { if (_satGeo) _satGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _stageGeo = _satGeo = null;
  _group = _show = _badge = null;
  _input = _runBtn = _traceEl = _onKey = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _stagePos = []; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = "MODELED"; S.state = "idle";
  S.stepCap = S.retryCap = S.maxActions = null;
  S.brainAvailable = S.gateAvailable = S.sovereignReady = null;
  S.goal = ""; S.finalStatus = null; S.plannedSteps = null; S.actionsUsed = null;
  S.modelReachable = null; S.runId = null; S.runDigest = null; S.steps = null; S.note = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_STATUS, EP_OPERATE], mount, unmount };
