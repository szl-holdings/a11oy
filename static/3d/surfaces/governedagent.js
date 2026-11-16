// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/governedagent.js — GOVERNED AGENT LOOP holographic surface (Wave J · Dev 5).
//
// Technique modeled (NOT claimed-as): the agent-framework closed loop
//   plan → act → self-eval → gate → retry, folded into OUR governed ecosystem.
//   Studied leaders (citable, non-leaked):
//     · LangGraph — stateful graph, conditional retry edges, interrupt() HITL
//       https://langchain-ai.github.io/langgraph/
//     · OpenAI Agents SDK — guardrails + approval interruptions + resumable state
//       https://openai.github.io/openai-agents-js/guides/human-in-the-loop/
//     · CrewAI — task guardrail callbacks + bounded retry  https://docs.crewai.com/
//     · AutoGen — reflection loops + human_input_mode gate
//       https://microsoft.github.io/autogen/
//     · Anthropic MCP — host composes servers; sensitive actions host-gated
//       https://modelcontextprotocol.io/
//   This implementation folds each step's plan+act+eval+gate
//   into a composite record. The backend may emit a signed envelope;
//   this view does not verify its signature or prove execution.
//   This surface COMPOSES three existing siloed pieces — the /code run-loop (act),
//   the model-harness (behavior profile), and the eval-arena (self-eval) — plus the
//   durable HumanApprovalGate, into ONE governed autonomous loop.
//
// EVERY value on screen traces to a REAL a11oy endpoint (doctrine v11 — never fabricate):
//   * GET  /api/a11oy/v1/agentloop/health   — composition liveness + signer mode
//   * POST /api/a11oy/v1/agentloop/run       — the governed loop → ONE composite receipt
//
// The scene: a horizontal PIPELINE of stage nodes (plan · act · self-eval · gate ·
// receipt), a run BEAM that flows left→right when a run fires, per-STEP satellites
// that light by eval accuracy / gate verdict, and a floating composite-RECEIPT panel
// showing the live signed hash-chain. Honesty labels read straight from the JSON.
// Degrades gracefully; no crash, no fake data. 0 runtime CDN (three via importmap).

const ID = "governedagent";
const TITLE = "Governed Agent Loop · request → outcome → evidence";
const EP_HEALTH = "/api/a11oy/v1/agentloop/health";
const EP_RUN = "/api/a11oy/v1/agentloop/run";

// palette (matches the estate)
const C_STAGE = 0x6fb1ff;   // pipeline stage node — blue
const C_ACT = 0xe8c074;     // act (engine) — gold
const C_EVAL = 0x39d3c4;    // self-eval — teal
const C_GATE = 0xff9b6b;    // gate — amber
const C_OK = 0x2fd07a;      // pass — green
const C_DIM = 0x4a5a68;

const STAGES = [
  { key: "plan", label: "plan", sub: "MODELED", color: C_STAGE },
  { key: "act", label: "act", sub: "engine P1-P6 · Λ-gate · sandbox", color: C_ACT },
  { key: "eval", label: "self-eval", sub: "eval-arena · Λ axes", color: C_EVAL },
  { key: "gate", label: "gate", sub: "HumanApprovalGate", color: C_GATE },
  { key: "receipt", label: "receipt", sub: "ONE composite DSSE", color: C_OK },
];

let _stage = null, _THREE = null, _ctx = null;
let _group = null, _overlay = null, _frameReg = false;
let _stageNodes = [];       // { mesh, label, key }
let _beam = null, _billboard = null, _badge = null, _poll = null;
let _stepSats = [];         // per-step satellites
let _runController = null, _lifecycle = 0;

const S = {
  state: "init", degraded: false, label: null,
  composes: null, signerMode: null,
  task: "Explain the deny-by-default policy for a governed action.",
  mode: "chat", model: "", profile: "", suite: "core_honest_v1",
  outcomeUncertain: false,
  running: false, lastResult: null, lastReceipt: null, runState: "idle",
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _lifecycle += 1;
  window.addEventListener("pagehide", _leavePage);
  window.addEventListener("pageshow", _resumePage);
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);
  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 6, 20);
  try { _stage.setBloom(true); } catch (_) {}

  _buildPipeline();
  _buildBeam();
  try {
    _billboard = ctx.label.billboard(THREE, "MODELED", { text: "plan modeled · execution evidence required", scale: 0.6, position: [0, 6.4, 0] });
    _group.add(_billboard);
  } catch (_) {}

  _buildOverlay();
  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  _startHealthPoll(ctx);

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildPipeline() {
  const THREE = _THREE;
  _stageNodes = [];
  const n = STAGES.length;
  const span = 14;
  STAGES.forEach((st, i) => {
    const x = -span / 2 + (span / Math.max(n - 1, 1)) * i;
    const mesh = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.9, 1),
      new THREE.MeshStandardMaterial({ color: st.color, emissive: st.color, emissiveIntensity: 0.4, metalness: 0.4, roughness: 0.45, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(x, 1.4, 0);
    _group.add(mesh);
    // connector rail to previous node
    if (i > 0) {
      const prev = _stageNodes[i - 1].mesh.position;
      const rail = new THREE.Mesh(
        new THREE.CylinderGeometry(0.04, 0.04, prev.distanceTo(mesh.position), 8),
        new THREE.MeshBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.5 }),
      );
      const mid = prev.clone().add(mesh.position).multiplyScalar(0.5);
      rail.position.copy(mid);
      rail.lookAt(mesh.position); rail.rotateX(Math.PI / 2);
      _group.add(rail);
    }
    let label = null;
    try {
      label = _ctx.label.billboard(_THREE, st.label, { text: st.sub, scale: 0.4, position: [x, 2.7, 0] });
      _group.add(label);
    } catch (_) {}
    _stageNodes.push({ mesh, label, key: st.key });
  });
}

function _buildBeam() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.35, 16, 16);
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.0 });
  _beam = new THREE.Mesh(geo, mat);
  _beam.visible = false;
  _group.add(_beam);
}

function _renderStepSats(steps) {
  const THREE = _THREE;
  _stepSats.forEach((s) => { try { _group.remove(s.mesh); } catch (_) {} try { if (s.label) _group.remove(s.label); } catch (_) {} });
  _stepSats = [];
  if (!Array.isArray(steps)) return;
  steps.forEach((st, i) => {
    const fin = st.final || {};
    const ev = fin.eval || {};
    const acc = typeof ev.accuracy === "number" ? ev.accuracy : null;
    const denied = fin.engine && fin.engine.decision === "DENY";
    const col = denied ? C_GATE : (acc !== null && acc >= 0.5 ? C_OK : C_ACT);
    const mesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.55, 0),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.55, metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.92 }),
    );
    const ang = (i / Math.max(steps.length, 1)) * Math.PI * 2;
    mesh.position.set(Math.cos(ang) * 3.4, -2.6, Math.sin(ang) * 3.4 - 1.5);
    _group.add(mesh);
    let label = null;
    try {
      const lab = "step " + (st.n != null ? st.n : i + 1);
      const sub = (acc !== null ? "acc " + acc : "acc —") + (st.retries ? " · retry " + st.retries : "");
      label = _ctx.label.billboard(_THREE, lab, { text: sub, scale: 0.36, position: [mesh.position.x, mesh.position.y + 1.0, mesh.position.z] });
      _group.add(label);
    } catch (_) {}
    _stepSats.push({ mesh, label });
  });
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onHealth(json, meta) {
  S.degraded = !!meta.degraded;
  S.label = meta.label || S.label;
  if (!json) { _paintOverlay(); return; }
  S.composes = json.composes || null;
  S.signerMode = json.signature_mode || null;
  if (Array.isArray(json.eval_suites) && json.eval_suites.length && !S.suite) {
    // leave suite blank (per-step heuristic) but expose the roster in the selector
    S._suites = json.eval_suites;
  }
  _paintOverlay();
  if (_billboard && _ctx && S.composes) {
    try {
      const avail = Object.values(S.composes).filter(Boolean).length;
      const tot = Object.keys(S.composes).length;
      _group.remove(_billboard);
      _billboard = _ctx.label.billboard(_THREE, "COMPOSES", {
        text: `${avail}/${tot} modules available; execution unverified`, scale: 0.56, position: [0, 6.4, 0],
      });
      _group.add(_billboard);
    } catch (_) {}
  }
}

function _completionState(value) {
  const completion = value && value.completion;
  if (!completion || typeof completion !== "object" || Array.isArray(completion)) {
    return "UNKNOWN - completion evidence absent";
  }
  if (completion.evidence_basis !== "UPSTREAM_REPORTED_UNVERIFIED"
      || completion.receipt_verification_asserted !== false || completion.model_qualified !== false) {
    return "UNKNOWN - completion evidence does not match the current server contract";
  }
  if (completion.state === "OBSERVED_COMPLETE" && completion.complete === true && value.ok === true) {
    return "OBSERVED_COMPLETE - upstream reported, unverified; model unqualified";
  }
  if (["BLOCKED", "INCOMPLETE", "UNKNOWN"].includes(completion.state) && completion.complete === false && value.ok === false) {
    return completion.state + " - upstream reported, unverified; no completion established";
  }
  return "UNKNOWN - inconsistent completion evidence";
}

function _startHealthPoll(ctx) {
  const lifecycle = _lifecycle;
  _poll = ctx.live.poll(EP_HEALTH, 9000, (value, meta) => {
    if (lifecycle === _lifecycle) _onHealth(value, meta);
  }, {
    badge: _badge,
    onState: (meta) => {
      if (lifecycle !== _lifecycle) return;
      S.state = meta.state; S.label = meta.label || S.label;
      if (meta.state !== "live") _paintOverlay();
    },
  });
}

function _resumePage() {
  if (_ctx && !_poll) _startHealthPoll(_ctx);
}

function _clearCredentials() {
  if (_el.operatorToken) _el.operatorToken.value = "";
}

function _leavePage() {
  _clearCredentials();
  if (_el.tenant) _el.tenant.value = "";
  _lifecycle += 1;
  if (_poll) { try { _poll.stop(); } catch (_) {} _poll = null; }
  S.composes = null; S.signerMode = null; S.state = "init"; S.label = null;
  if (_runController) {
    S.outcomeUncertain = true;
    S.runState = "UNKNOWN - request interrupted; execution may have occurred";
    _runController.abort();
    _runController = null;
  }
  S.running = false;
  _paintOverlay();
}

function _requestInputsChanged() {
  if (S.running) return;
  S.lastResult = null; S.lastReceipt = null;
  S.runState = S.outcomeUncertain
    ? "UNKNOWN - previous execution may have occurred; a new request still needs acknowledgement"
    : "INPUT_CHANGED - no result established for these inputs";
  _renderStepSats([]); _paintOverlay(); _paintReceipt();
}

async function _fireRun() {
  if (S.running) return;
  let token = String((_el.operatorToken && _el.operatorToken.value) || "").trim();
  const tenant = String((_el.tenant && _el.tenant.value) || "").trim();
  const task = String((_el.task && _el.task.value) || "").trim();
  const model = String((_el.modelSel && _el.modelSel.value) || "").trim();
  const mode = String((_el.modeSel && _el.modeSel.value) || "");
  const suite = String((_el.suiteSel && _el.suiteSel.value) || "").trim();
  const reject = (message) => { _clearCredentials(); S.runState = message; _paintOverlay(); };
  if (!token || token.length > 4096 || /[^\x21-\x7e]/.test(token)) {
    reject("BLOCKED - enter an operator credential for this one request"); return;
  }
  if (!tenant || tenant.length > 256 || /[^\x21-\x7e]/.test(tenant)) {
    reject("BLOCKED - enter the configured tenant; it is checked by the server"); return;
  }
  if (!task || task.length > 32000 || !model || model.length > 240
      || !["chat", "code", "research"].includes(mode) || !suite || suite.length > 160) {
    reject("BLOCKED - supply a task, explicit model and evaluation suite"); return;
  }
  if (S.outcomeUncertain && !window.confirm(
    "The previous request may have executed. This starts new work and may incur additional cost. Send a new request?")) {
    _clearCredentials(); return;
  }
  const body = { task, mode, model_id: model, eval_suite: suite, max_retries: 0,
    sandbox: false, consult_brain: false, allocate_energy: false };
  if (_el.profile && _el.profile.value.trim()) body.harness_profile_id = _el.profile.value.trim();
  const serialized = JSON.stringify(body);
  if (new TextEncoder().encode(serialized).length > 65536) {
    reject("BLOCKED - request exceeds the 64 KiB client boundary"); return;
  }
  const lifecycle = _lifecycle;
  const controller = new AbortController();
  _runController = controller;
  S.running = true; S.outcomeUncertain = false;
  S.lastResult = null; S.lastReceipt = null;
  S.runState = "RUNNING - one browser request; server authorization and policy still apply";
  _clearCredentials(); _paintOverlay(); _paintReceipt(); _animateBeam();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(EP_RUN, {
      method: "POST", redirect: "error", credentials: "same-origin", cache: "no-store",
      headers: { "content-type": "application/json", accept: "application/json",
        authorization: "Bearer " + token, "x-a11oy-tenant": tenant },
      body: serialized, signal: controller.signal,
    });
    token = "";
    if (lifecycle !== _lifecycle) return;
    if (!(response.headers.get("content-type") || "").toLowerCase().includes("application/json")) {
      throw new Error("NON_JSON_RESPONSE");
    }
    const raw = await response.text();
    if (lifecycle !== _lifecycle) return;
    if (raw.length > 1048576) throw new Error("RESPONSE_TOO_LARGE");
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("INVALID_RESPONSE");
    S.lastResult = value;
    S.lastReceipt = value.composite_receipt && value.composite_receipt.body || null;
    if (response.status === 401) S.runState = "BLOCKED - operator credential refused or unavailable";
    else if (response.status === 403) S.runState = "BLOCKED - tenant or policy admission refused";
    else if (!response.ok) {
      S.outcomeUncertain = response.status >= 500;
      S.runState = S.outcomeUncertain
        ? "UNKNOWN - server unavailable; execution may have occurred; no automatic retry"
        : "BLOCKED - request refused (HTTP " + response.status + ")";
    } else {
      S.runState = _completionState(value);
      S.outcomeUncertain = S.runState.startsWith("UNKNOWN");
    }
    _renderStepSats(Array.isArray(value.steps) ? value.steps : []);
    _paintOverlay(); _paintReceipt();
  } catch (_) {
    if (lifecycle !== _lifecycle) return;
    S.outcomeUncertain = true;
    S.runState = "UNKNOWN - response unavailable or invalid; execution may have occurred; no automatic retry";
  } finally {
    token = ""; clearTimeout(timer);
    if (lifecycle === _lifecycle) {
      _runController = null; S.running = false; _clearCredentials(); _paintOverlay();
    }
  }
}

function _animateBeam() {
  if (!_beam || !_stageNodes.length) return;
  _beam.visible = true;
  _beam.material.opacity = 0.9;
  _beam.userData.t = 0;
}

// =========================================================================================
// per-frame animation
// =========================================================================================
function _onFrame() {
  _stageNodes.forEach((n, i) => { n.mesh.rotation.y += 0.006 + i * 0.001; });
  _stepSats.forEach((s, i) => { s.mesh.rotation.y += 0.01 + i * 0.002; });
  if (_beam && _beam.visible && _stageNodes.length) {
    _beam.userData.t = (_beam.userData.t || 0) + 0.012;
    const t = _beam.userData.t;
    const seg = Math.min(_stageNodes.length - 1, Math.floor(t * (_stageNodes.length - 1)));
    const frac = (t * (_stageNodes.length - 1)) - seg;
    const a = _stageNodes[seg].mesh.position;
    const b = _stageNodes[Math.min(seg + 1, _stageNodes.length - 1)].mesh.position;
    _beam.position.lerpVectors(a, b, frac);
    if (t >= 1) { _beam.visible = false; _beam.material.opacity = 0; }
  }
}

// =========================================================================================
// DOM overlay (HUD)
// =========================================================================================
let _el = {};
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxHeight: "calc(100% - 28px)", overflowY: "auto", boxSizing: "border-box",
    maxWidth: "min(94%,480px)", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.5";
  sub.textContent = "The governed loop combines task planning, model output, evaluation and policy gates. A composite receipt may be returned; verification is reported separately. Plan MODELED. Lambda remains Conjecture 1 and cannot authorize work.";
  _overlay.appendChild(sub);

  _badge = ctx.live.createBadge();
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#6fb1ff"; return s; };
  badgeRow.appendChild(tag("agentloop")); badgeRow.appendChild(_badge.el);
  _overlay.appendChild(badgeRow);

  // composition status row
  _el.composes = document.createElement("div");
  _el.composes.style.cssText = "font:10px ui-monospace,monospace;color:#9fb1bf;line-height:1.6";
  _overlay.appendChild(_el.composes);

  // run controls
  const ctl = document.createElement("div");
  ctl.style.cssText = "display:flex;flex-direction:column;gap:6px;background:#0a1117;border:1px solid #1d2a36;border-radius:8px;padding:8px";
  const cl = document.createElement("div");
  cl.style.cssText = "font:600 11px ui-sans-serif;color:#e8c074"; cl.textContent = "run the governed loop (plan→act→eval→gate→receipt)";
  ctl.appendChild(cl);

  _el.task = document.createElement("input");
  _el.task.type = "text"; _el.task.value = S.task;
  _el.task.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-sans-serif";
  _el.task.setAttribute("aria-label", "Governed task");
  ctl.appendChild(_el.task);

  const credentialField = (label, type, maximum, placeholder) => {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    wrapper.style.cssText = "display:grid;gap:4px;min-width:0";
    const input = document.createElement("input");
    input.type = type; input.maxLength = maximum; input.autocomplete = "off";
    input.spellcheck = false; input.placeholder = placeholder;
    input.style.cssText = _el.task.style.cssText + ";width:100%;min-width:0;box-sizing:border-box";
    wrapper.appendChild(input); ctl.appendChild(wrapper);
    return input;
  };
  _el.operatorToken = credentialField("Operator credential (one request)", "password", 4096, "Existing operator credential");
  _el.tenant = credentialField("Configured tenant", "text", 256, "Existing tenant ID");
  const boundary = document.createElement("p");
  boundary.textContent = "Uses the existing operator and tenant gates. No sandbox execution or second-approver credential is enabled here. One browser request, zero orchestration retries; provider-internal retries and total cost are not established.";
  ctl.appendChild(boundary);

  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:6px;flex-wrap:wrap";
  const mkSel = (opts, val) => {
    const s = document.createElement("select");
    s.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-monospace,monospace";
    opts.forEach((o) => { const op = document.createElement("option"); op.value = o; op.textContent = o; s.appendChild(op); });
    if (val) s.value = val;
    return s;
  };
  _el.modeSel = mkSel(["chat", "code", "research"], S.mode);
  _el.modeSel.setAttribute("aria-label", "Task mode; sandbox execution is disabled here");
  _el.modelSel = document.createElement("input");
  _el.modelSel.type = "text"; _el.modelSel.maxLength = 240;
  _el.modelSel.placeholder = "Explicit configured model ID";
  _el.modelSel.setAttribute("aria-label", "Explicit configured model ID");
  _el.modelSel.style.cssText = _el.task.style.cssText;
  _el.suiteSel = mkSel(["", "core_honest_v1", "redteam_v1", "honesty_v1"], S.suite);
  _el.suiteSel.setAttribute("aria-label", "Evaluation suite");
  row.appendChild(_el.modeSel); row.appendChild(_el.modelSel); row.appendChild(_el.suiteSel);
  ctl.appendChild(row);

  _el.profile = document.createElement("input");
  _el.profile.type = "text"; _el.profile.placeholder = "harness_profile_id (optional)";
  _el.profile.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-monospace,monospace";
  ctl.appendChild(_el.profile);

  _el.runBtn = document.createElement("button");
  _el.runBtn.style.cssText = "background:#12202b;color:#eef3f6;border:1px solid #39d3c4;border-radius:7px;padding:7px 10px;cursor:pointer;font:600 11px ui-monospace,monospace";
  _el.runBtn.textContent = "Send one governed request";
  _el.runBtn.addEventListener("click", _fireRun);
  ctl.appendChild(_el.runBtn);
  for (const control of [_el.task, _el.operatorToken, _el.tenant, _el.modelSel, _el.modeSel, _el.suiteSel, _el.profile]) {
    control.addEventListener("input", _requestInputsChanged);
    control.addEventListener("change", _requestInputsChanged);
  }

  _el.runState = document.createElement("div");
  _el.runState.style.cssText = "font:10.5px ui-monospace,monospace;color:#9fb1bf";
  _el.runState.textContent = "run state: idle";
  ctl.appendChild(_el.runState);
  _overlay.appendChild(ctl);

  // composite receipt panel
  const det = document.createElement("details");
  det.open = true;
  const sum = document.createElement("summary");
  sum.style.cssText = "cursor:pointer;color:#39d3c4;font:11px ui-monospace,monospace";
  sum.textContent = "composite receipt · verification not established";
  _el.receipt = document.createElement("div");
  _el.receipt.style.cssText = "white-space:pre-wrap;font:10px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;max-height:230px;overflow:auto;margin-top:6px";
  _el.receipt.textContent = "— no run receipt observed —";
  det.appendChild(sum); det.appendChild(_el.receipt);
  _overlay.appendChild(det);

  // honesty legend
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);

  // sources (text only — NOT fetch-shaped, doctrine 0-CDN safe)
  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Read the completion state and its evidence basis together. An observed result is upstream-reported and unverified. Receipt verification, model qualification and real-world effects need separate evidence. Lambda is advisory; the locked-eight set is unchanged.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

function _paintOverlay() {
  for (const name of ["task", "operatorToken", "tenant", "modelSel", "modeSel", "suiteSel", "profile", "runBtn"]) {
    if (_el[name]) _el[name].disabled = S.running;
  }
  if (_el.composes) {
    if (!S.composes) { _el.composes.textContent = "composition: awaiting live health (" + S.state + ")"; }
    else {
      const c = S.composes;
      const mk = (k, on) => (on ? "✓ " : "✗ ") + k;
      _el.composes.textContent = "composition: " + [
        mk("act(engine)", c.act_engine_available),
        mk("plan", c.plan_source_available),
        mk("eval-arena", c.self_eval_available),
        mk("harness", c.behavior_profile_available),
        mk("gate", c.human_gate_available),
      ].join("  ") + (S.signerMode ? "  ·  " + S.signerMode : "");
    }
  }
  if (_el.runState) {
    let extra = "";
    if (S.lastResult && S.lastResult.aggregate) {
      const a = S.lastResult.aggregate;
      extra = "  ·  steps " + a.n_steps + "  ·  mean acc " + (a.mean_eval_accuracy != null ? a.mean_eval_accuracy : "—") +
        "  ·  Λ " + (a.mean_eval_lambda != null ? a.mean_eval_lambda : "—") +
        (a.any_gate_hold ? "  ·  GATE HELD" : "") + (a.any_step_denied ? "  ·  DENY" : "");
    }
    _el.runState.textContent = "run state: " + S.runState + extra;
  }
}

function _paintReceipt() {
  if (!_el.receipt) return;
  if (!S.lastReceipt) { _el.receipt.textContent = "— no run receipt observed —"; return; }
  const r = S.lastReceipt;
  const res = S.lastResult || {};
  const sig = (res.composite_receipt && res.composite_receipt.signing) || {};
  const agg = r.aggregate || {};
  const lines = [
    "completion       : " + ((res.completion && res.completion.state) || "UNKNOWN"),
    "evidence_basis   : " + ((res.completion && res.completion.evidence_basis) || "UNAVAILABLE"),
    "verification     : not established by this browser",
    "qualification    : not established by this response",
    "schema           : " + (r.schema || "?"),
    "run_id           : " + (r.run_id || "?"),
    "task             : " + (r.task || ""),
    "mode             : " + (r.mode || "?") + "   model: " + (r.model_id || "?"),
    "harness_profile  : " + (r.harness_profile_id || "(none)"),
    "n_steps          : " + (r.n_steps),
    "mean_eval_acc    : " + (agg.mean_eval_accuracy != null ? agg.mean_eval_accuracy : "—"),
    "mean_eval_Λ      : " + (agg.mean_eval_lambda != null ? agg.mean_eval_lambda : "—") + "  (" + (agg.lambda_status || "CONJECTURE") + ")",
    "any_gate_hold    : " + agg.any_gate_hold + "   any_step_denied: " + agg.any_step_denied,
    "run_chain_digest : " + (r.run_chain_digest || "?"),
    "signature        : " + (sig.alg || "?") + " / " + (sig.envelope || "?") + " · mode=" + (sig.mode || "?"),
    "  pae_sha256     : " + (sig.pae_sha256 || "?"),
    "  honesty        : " + (sig.note || "?"),
    "locked8_touched  : " + r.locked8_touched,
    "conjecture       : " + (r.honest_note || ""),
    "",
    "── step chain (hash-chained) ──",
  ];
  (r.step_chain || []).forEach((s) => {
    lines.push("  step " + s.n + " · " + (s.decision || "?") + " · acc " + (s.eval_accuracy != null ? s.eval_accuracy : "—") +
      " · Λ " + (s.eval_lambda != null ? s.eval_lambda : "—") + (s.harness_profile ? " · prof " + s.harness_profile : "") +
      "\n         digest " + (s.digest || "").slice(0, 24) + "…");
  });
  _el.receipt.textContent = lines.join("\n");
}

// =========================================================================================
// unmount
// =========================================================================================
function unmount() {
  _leavePage();
  window.removeEventListener("pagehide", _leavePage);
  window.removeEventListener("pageshow", _resumePage);
  try { if (_poll) _poll.stop(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach((m) => { if (m.map && m.map.dispose) m.map.dispose(); if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _poll = null; _overlay = _group = _beam = _billboard = null;
  _stageNodes = []; _stepSats = []; _badge = null; _el = {};
  S.composes = null; S.lastResult = null; S.lastReceipt = null; S.running = false;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_HEALTH, EP_RUN], mount, unmount };
