// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
//
// Integrity Control Plane -- two read-only contracts plus one bounded computational read:
//   GET /api/a11oy/v1/waqay/security-loop/manifest
//   GET /api/a11oy/v1/claim-integrity/info
//   POST /api/a11oy/v1/claim-integrity/atomize
//
// Atomization is a deterministic punctuation/newline split. It is not semantic evaluation,
// persistence, signing, approval, or execution. Every returned candidate stays atomic=false
// and human-review-required. A successful request does NOT mean that a deployer, rollback
// mechanism, model, signer, repository writer, or any other effector is live.

import { createShowcase } from "./_showcase.js";

const ID = "integritycontrol";
const TITLE = "Integrity Control Plane · proposal boundaries";
const SECURITY_EP = "/api/a11oy/v1/waqay/security-loop/manifest";
const CLAIM_EP = "/api/a11oy/v1/claim-integrity/info";
const ATOMIZE_EP = "/api/a11oy/v1/claim-integrity/atomize";

const C_TEAL = 0x3af4c8;
const C_BLUE = 0x5b8dee;
const C_AMBER = 0xe8c074;
const C_RED = 0xff5964;
const C_DIM = 0x42505d;
const C_GRID = 0x1b3a44;

let _ctx = null;
let _stage = null;
let _THREE = null;
let _group = null;
let _show = null;
let _polls = [];
let _frameRegistered = false;
let _core = null;
let _ring = null;
let _nodes = [];
let _links = [];
let _boundaryPill = null;
let _compileController = null;
let _compileSerial = 0;
let _proseInput = null;
let _compileButton = null;
let _compileStatus = null;
let _candidateList = null;

const S = {
  security: null,
  claim: null,
  fetch: { security: "init", claim: "init" },
  mode: null,
  effectors: null,
  signing: null,
  verdict: "AWAITING-CONTRACTS",
};

function _isObject(v) { return !!v && typeof v === "object" && !Array.isArray(v); }
function _upper(v) { return v == null ? null : String(v).trim().toUpperCase(); }
function _number(v) { return typeof v === "number" && Number.isFinite(v) ? v : null; }

// Pure boundary reducer. No fallback values are invented: a field is known only after the
// corresponding endpoint supplies it. Exported so contract tests can pin the reducer.
export function deriveIntegrityBoundary(security, claim) {
  const sec = _isObject(security) ? security : null;
  const clm = _isObject(claim) ? claim : null;
  const complete = !!sec && !!clm;

  const securityMode = sec ? _upper(sec.mode) : null;
  const claimMode = clm ? _upper(clm.decision_state) : null;
  const securityEffectors = sec ? _number(sec.effectors) : null;
  const claimEffectors = clm ? _number(clm.effectors_enabled) : null;
  const externalMutations = sec ? _upper(sec.external_mutations) : null;

  const secReceipt = sec && _isObject(sec.receipt) ? sec.receipt : null;
  const signatureDefault = secReceipt ? _upper(secReceipt.signature_default) : null;
  const claimMissing = clm && Array.isArray(clm.not_implemented_here)
    ? clm.not_implemented_here.map(_upper) : [];
  const signingAbsent = !!signatureDefault && signatureDefault.includes("UNSIGNED") &&
    claimMissing.includes("SIGNING");

  const proposalOnly = complete && securityMode === "PROPOSAL_ONLY" &&
    claimMode === "PROPOSAL_ONLY";
  const zeroEffectors = complete && securityEffectors === 0 && claimEffectors === 0;
  const mutationsDisabled = complete && externalMutations === "DISABLED";

  let verdict = "AWAITING-CONTRACTS";
  if (complete) {
    verdict = proposalOnly && zeroEffectors && mutationsDisabled
      ? "BOUNDARIES-INTACT"
      : "BOUNDARY-VIOLATION";
  }

  return {
    complete,
    securityMode,
    claimMode,
    securityEffectors,
    claimEffectors,
    externalMutations,
    signing: signingAbsent ? "UNSIGNED" : (complete ? "UNKNOWN" : null),
    proposalOnly,
    zeroEffectors,
    mutationsDisabled,
    verdict,
  };
}

function _derive() {
  const d = deriveIntegrityBoundary(S.security, S.claim);
  S.mode = d.proposalOnly ? "PROPOSAL_ONLY" :
    (d.complete ? `${d.securityMode || "UNKNOWN"} / ${d.claimMode || "UNKNOWN"}` : null);
  S.effectors = d.zeroEffectors ? 0 :
    (d.complete ? `${d.securityEffectors ?? "?"} / ${d.claimEffectors ?? "?"}` : null);
  S.signing = d.signing;
  S.verdict = d.verdict;
  _paint();
}

function _setCompileStatus(message, tone = "neutral") {
  if (!_compileStatus) return;
  _compileStatus.textContent = message;
  _compileStatus.dataset.claimCompileState = tone;
  _compileStatus.style.color = tone === "error" ? "#ff8b94" :
    (tone === "ready" ? "#3af4c8" : (tone === "loading" ? "#e8c074" : "#9fb1bf"));
}

function _clearCandidates() {
  if (!_candidateList) return;
  while (_candidateList.firstChild) _candidateList.removeChild(_candidateList.firstChild);
}

function _renderCandidates(payload) {
  _clearCandidates();
  const atoms = payload && Array.isArray(payload.atoms) ? payload.atoms : [];
  const contractIntact = payload && payload.semantic_atomization_computed === false &&
    String(payload.decision_state || "").toUpperCase() === "PROPOSAL_ONLY" &&
    payload.effectors_enabled === 0 &&
    payload.method === "VISIBLE-PUNCTUATION-AND-NEWLINE-SPLIT" &&
    Number.isInteger(payload.candidate_count) && payload.candidate_count >= 0 &&
    payload.candidate_count <= 32 && payload.candidate_count === atoms.length;

  if (!contractIntact) {
    _setCompileStatus("CONTRACT MISMATCH: response was not proposal-only with zero effectors.", "error");
    return;
  }

  if (!atoms.length) {
    _setCompileStatus("0 structural candidates. No semantic claim was established.", "ready");
    return;
  }

  let rendered = 0;
  atoms.forEach((atom, index) => {
    const reviewRequired = atom && atom.human_review_required === true;
    const structuralOnly = atom && atom.atomic === false &&
      String(atom.atomization_state || "").toUpperCase() === "STRUCTURAL-SPLIT-ONLY";
    if (!reviewRequired || !structuralOnly || typeof atom.statement !== "string") return;

    const row = document.createElement("article");
    row.dataset.claimCandidate = String(index + 1);
    row.dataset.reviewRequired = "true";
    Object.assign(row.style, {
      border: "1px solid #263746", borderRadius: "8px", padding: "8px 9px",
      background: "#09121a", display: "grid", gap: "5px",
    });

    const heading = document.createElement("div");
    heading.textContent = `Candidate ${String(index + 1).padStart(2, "0")} · REVIEW REQUIRED`;
    Object.assign(heading.style, {
      color: "#e8c074", font: "600 10px ui-monospace,Menlo,monospace",
      letterSpacing: ".35px",
    });

    const statement = document.createElement("div");
    statement.textContent = atom.statement;
    Object.assign(statement.style, {
      color: "#e7eef6", fontSize: "11px", lineHeight: "1.5",
      overflowWrap: "anywhere", whiteSpace: "pre-wrap",
    });

    const boundary = document.createElement("div");
    boundary.textContent = "STRUCTURAL-SPLIT-ONLY · atomic=false · no evidence attached";
    Object.assign(boundary.style, {
      color: "#778b9b", font: "9px ui-monospace,Menlo,monospace",
    });

    row.appendChild(heading);
    row.appendChild(statement);
    row.appendChild(boundary);
    _candidateList.appendChild(row);
    rendered += 1;
  });

  if (rendered !== atoms.length) {
    _clearCandidates();
    _setCompileStatus("CONTRACT MISMATCH: one or more candidates were not structural and review-required.", "error");
    return;
  }
  _setCompileStatus(`${rendered} structural candidate${rendered === 1 ? "" : "s"}. Human review required.`, "ready");
}

function _compileProse() {
  const prose = _proseInput ? _proseInput.value.trim() : "";
  if (!prose) {
    _clearCandidates();
    _setCompileStatus("Enter prose before compiling structural candidates.", "error");
    if (_proseInput) _proseInput.focus();
    return;
  }

  if (_compileController && _compileController.abort) {
    try { _compileController.abort(); } catch (_) {}
  }
  const ctrl = (typeof window !== "undefined" && "AbortController" in window)
    ? new AbortController() : null;
  _compileController = ctrl;
  const serial = ++_compileSerial;
  _clearCandidates();
  _setCompileStatus("Compiling visible punctuation and newline splits…", "loading");
  if (_compileButton) {
    _compileButton.disabled = true;
    _compileButton.textContent = "Compiling…";
  }

  fetch(ATOMIZE_EP, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ text: prose }),
    signal: ctrl ? ctrl.signal : undefined,
  })
    .then(async (response) => {
      let payload = null;
      try { payload = await response.json(); } catch (_) {}
      if (!response.ok) {
        const error = new Error(`http ${response.status}`);
        error.status = response.status;
        error.payload = payload;
        throw error;
      }
      return payload;
    })
    .then((payload) => {
      if (serial !== _compileSerial) return;
      _compileController = null;
      _renderCandidates(payload);
    })
    .catch((error) => {
      if (error && error.name === "AbortError") return;
      if (serial !== _compileSerial) return;
      _compileController = null;
      _clearCandidates();
      if (error && error.status === 413) {
        _setCompileStatus("413 · INPUT TOO LARGE: reduce the prose and retry.", "error");
      } else if (error && error.status === 422) {
        _setCompileStatus("422 · INVALID INPUT: the atomization contract refused this request.", "error");
      } else if (error && error.status === 503) {
        _setCompileStatus("503 · UNAVAILABLE: the Claim Compiler is not ready.", "error");
      } else {
        _setCompileStatus("UNAVAILABLE: no structural candidates were returned.", "error");
      }
    })
    .finally(() => {
      if (serial !== _compileSerial || !_compileButton) return;
      _compileButton.disabled = false;
      _compileButton.textContent = "Compile candidates";
    });
}

export function mount(ctx) {
  _ctx = ctx;
  _stage = ctx.stage;
  _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 5.5, 16);
  try {
    if (_stage.controls && _stage.controls.target) {
      _stage.controls.target.set(0, 1.5, 0);
      _stage.controls.update();
    }
  } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildScene();
  _buildOverlay();
  if (!_frameRegistered) { _stage.onFrame(_onFrame); _frameRegistered = true; }

  _polls.push(ctx.live.poll(SECURITY_EP, 10000, (j) => {
    S.security = j;
    _derive();
  }, {
    onState: (m) => {
      S.fetch.security = m.state;
      if (m.state !== "live" && m.state !== "degraded") S.security = null;
      _derive();
    },
  }));
  _polls.push(ctx.live.poll(CLAIM_EP, 10000, (j) => {
    S.claim = j;
    _derive();
  }, {
    onState: (m) => {
      S.fetch.claim = m.state;
      if (m.state !== "live" && m.state !== "degraded") S.claim = null;
      _derive();
    },
  }));

  _paint();
  return { id: ID, started: true };
}

function _buildScene() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(32, 32, C_GRID, 0x0f2027);
  grid.material.opacity = 0.15;
  grid.material.transparent = true;
  _group.add(grid);

  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.15, 1),
    new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2,
      transparent: true, opacity: 0.78, wireframe: true,
    }),
  );
  _core.position.y = 1.6;
  _group.add(_core);

  _ring = new THREE.Mesh(
    new THREE.TorusGeometry(4.25, 0.035, 8, 96),
    new THREE.MeshBasicMaterial({ color: C_BLUE, transparent: true, opacity: 0.38 }),
  );
  _ring.rotation.x = Math.PI / 2;
  _ring.position.y = 1.6;
  _group.add(_ring);

  // Six points mirror the manifest's proposal-state topology. They are structural nodes,
  // never active deployers. No per-node text is rendered, keeping the scene uncluttered.
  const count = 6;
  for (let i = 0; i < count; i += 1) {
    const a = (i / count) * Math.PI * 2;
    const node = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.28, 0),
      new THREE.MeshStandardMaterial({
        color: C_BLUE, emissive: C_BLUE, emissiveIntensity: 0.2,
        transparent: true, opacity: 0.8,
      }),
    );
    node.position.set(Math.cos(a) * 4.25, 1.6, Math.sin(a) * 4.25);
    _group.add(node);
    _nodes.push(node);

    const linkGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 1.6, 0), node.position.clone(),
    ]);
    const link = new THREE.Line(linkGeo, new THREE.LineBasicMaterial({
      color: C_GRID, transparent: true, opacity: 0.28,
    }));
    _group.add(link);
    _links.push(link);
  }
}

function _buildOverlay() {
  _show = createShowcase(_ctx, {
    id: ID,
    title: TITLE,
    accent: "#3af4c8",
    startExpanded: true,
    chips: [
      {
        label: "STRUCTURAL-ONLY",
        text: "read-only manifests",
        name: "honesty",
        title: "Contract structure read from two same-origin endpoints; not an operational effector.",
      },
    ],
    description:
      "A compact view of the <b>Waqay Security Loop</b> and <b>Claim Integrity</b> " +
      "contracts. It preserves two same-origin GET polls and offers one bounded atomization " +
      "request without invoking evaluation, deploy, rollback, persistence, model, signer, or repository action. " +
      "<b>LIVE</b> here can only mean a manifest fetch succeeded; it never means effectors are live.",
    citations:
      "SZL-native clean-room control plane · read-only contract manifests · " +
      "no copied third-party interface, branding, or implementation.",
    plain: {
      label: "◑ boundary meaning",
      html: () =>
        "<b>What this means:</b> The system exposes the rules that a future security workflow " +
        "would have to obey. Today it may produce proposals only. The reported effector count " +
        "must be zero, external mutations must be disabled, and signatures remain unsigned " +
        "unless a real signer and independent verification are added. A manifest is a contract, " +
        "not proof that production automation exists.",
    },
  });

  _boundaryPill = document.createElement("span");
  _boundaryPill.setAttribute("data-integrity-boundary", "awaiting");
  Object.assign(_boundaryPill.style, {
    display: "inline-block", font: "600 10.5px ui-monospace,monospace",
    letterSpacing: ".35px", padding: "2px 8px", borderRadius: "5px",
    color: "#111820", background: "#e8c074", border: "1px solid rgba(255,255,255,.12)",
  });
  _show.pills.appendChild(_boundaryPill);

  _show.addField("control state", "mode");
  _show.addField("effectors (security / claim)", "effectors");
  _show.addField("external mutations", "mutations");
  _show.addField("signature boundary", "signing");
  _show.addField("contract endpoints", "feeds");
  _show.addField("allowed output", "output");

  const compiler = document.createElement("section");
  compiler.dataset.claimCompiler = "structural-only";
  Object.assign(compiler.style, {
    display: "grid", gap: "8px", border: "1px solid #1c3841", borderRadius: "9px",
    padding: "9px", background: "rgba(5,17,22,.88)", minWidth: "0",
  });

  const compilerTitle = document.createElement("div");
  compilerTitle.textContent = "Claim Compiler · structural proposal";
  Object.assign(compilerTitle.style, {
    color: "#3af4c8", font: "600 11px ui-monospace,Menlo,monospace",
  });

  const compilerBoundary = document.createElement("div");
  compilerBoundary.textContent =
    "Splits visible punctuation/newlines only. No semantic evaluation, persistence, signing, approval, or effectors.";
  Object.assign(compilerBoundary.style, {
    color: "#9fb1bf", fontSize: "10px", lineHeight: "1.45",
  });

  const label = document.createElement("label");
  label.htmlFor = `${ID}-prose`;
  label.textContent = "Prose to atomize";
  Object.assign(label.style, { color: "#c9d6df", fontSize: "10px" });

  _proseInput = document.createElement("textarea");
  _proseInput.id = `${ID}-prose`;
  _proseInput.rows = 5;
  _proseInput.placeholder = "Paste a bounded technical paragraph. No data is stored by this surface.";
  _proseInput.setAttribute("aria-describedby", `${ID}-compile-status`);
  _proseInput.spellcheck = true;
  Object.assign(_proseInput.style, {
    boxSizing: "border-box", width: "100%", minHeight: "96px", resize: "vertical",
    border: "1px solid #2b4050", borderRadius: "8px", padding: "9px",
    background: "#071019", color: "#e7eef6", outline: "none",
    font: "11px/1.5 ui-monospace,Menlo,monospace",
  });

  _compileButton = document.createElement("button");
  _compileButton.type = "button";
  _compileButton.textContent = "Compile candidates";
  _compileButton.dataset.claimCompileAction = "atomize";
  Object.assign(_compileButton.style, {
    minHeight: "40px", width: "100%", border: "1px solid #3af4c8",
    borderRadius: "8px", background: "#0a241f", color: "#3af4c8",
    cursor: "pointer", font: "600 11px ui-monospace,Menlo,monospace",
  });
  _compileButton.addEventListener("click", _compileProse);

  _proseInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      _compileProse();
    }
  });

  _compileStatus = document.createElement("div");
  _compileStatus.id = `${ID}-compile-status`;
  _compileStatus.setAttribute("role", "status");
  _compileStatus.setAttribute("aria-live", "polite");
  Object.assign(_compileStatus.style, {
    color: "#9fb1bf", font: "10px/1.45 ui-monospace,Menlo,monospace",
    overflowWrap: "anywhere",
  });
  _setCompileStatus("Not evaluated. Submit prose to request structural candidates.");

  _candidateList = document.createElement("div");
  _candidateList.dataset.claimCandidateList = "review-required";
  Object.assign(_candidateList.style, {
    display: "grid", gap: "7px", maxHeight: "210px", overflowY: "auto",
    WebkitOverflowScrolling: "touch",
  });

  compiler.appendChild(compilerTitle);
  compiler.appendChild(compilerBoundary);
  compiler.appendChild(label);
  compiler.appendChild(_proseInput);
  compiler.appendChild(_compileButton);
  compiler.appendChild(_compileStatus);
  compiler.appendChild(_candidateList);
  _show.appendBody(compiler);

  // Give the operator workflow enough room on laptops while remaining bounded on phones.
  _show.el.style.width = "min(94vw, 460px)";
}

function _field(key, value, color) {
  if (!_show) return;
  const el = _show.field(key);
  if (!el) return;
  el.textContent = value;
  if (color) el.style.color = color;
}

function _paint() {
  if (!_show) return;
  const d = deriveIntegrityBoundary(S.security, S.claim);
  const fetched = [S.fetch.security, S.fetch.claim].filter((v) => v === "live").length;

  let color = "#e8c074";
  let bg = "#e8c074";
  let text = "AWAITING CONTRACTS";
  if (d.verdict === "BOUNDARIES-INTACT") {
    color = "#3af4c8";
    bg = "#3af4c8";
    text = "READ-ONLY BOUNDARIES INTACT";
  } else if (d.verdict === "BOUNDARY-VIOLATION") {
    color = "#ff5964";
    bg = "#ff5964";
    text = "BOUNDARY VIOLATION";
  }

  if (_boundaryPill) {
    _boundaryPill.dataset.integrityBoundary = d.verdict.toLowerCase();
    _boundaryPill.textContent = text;
    _boundaryPill.style.background = bg;
  }
  if (_core && _core.material) {
    const hex = d.verdict === "BOUNDARIES-INTACT" ? C_TEAL :
      (d.verdict === "BOUNDARY-VIOLATION" ? C_RED : C_AMBER);
    _core.material.color.setHex(hex);
    _core.material.emissive.setHex(hex);
  }
  _nodes.forEach((node) => {
    const hex = d.verdict === "BOUNDARY-VIOLATION" ? C_RED :
      (d.verdict === "BOUNDARIES-INTACT" ? C_TEAL : C_DIM);
    node.material.color.setHex(hex);
    node.material.emissive.setHex(hex);
  });

  _field("mode", d.complete ? (d.proposalOnly ? "PROPOSAL_ONLY" :
    `${d.securityMode || "UNKNOWN"} / ${d.claimMode || "UNKNOWN"}`) : "NO-LIVE-DATA", color);
  _field("effectors", d.complete ?
    `${d.securityEffectors ?? "?"} / ${d.claimEffectors ?? "?"}` : "NO-LIVE-DATA",
    d.zeroEffectors ? "#3af4c8" : color);
  _field("mutations", d.complete ? (d.externalMutations || "UNKNOWN") : "NO-LIVE-DATA",
    d.mutationsDisabled ? "#3af4c8" : color);
  _field("signing", d.signing || "NO-LIVE-DATA", d.signing === "UNSIGNED" ? "#e8c074" : color);
  _field("feeds", `${fetched}/2 fetched`, fetched === 2 ? "#3af4c8" : "#e8c074");
  _field("output", d.proposalOnly ? "proposal only · no action" : "NO ACTION", "#9fb1bf");
}

function _onFrame() {
  const t = performance.now();
  if (_ring) _ring.rotation.z = t * 0.00008;
  if (_core) {
    _core.rotation.x = t * 0.00017;
    _core.rotation.y = t * 0.00023;
    _core.material.emissiveIntensity = 0.22 + 0.08 * (0.5 + 0.5 * Math.sin(t * 0.002));
  }
  _nodes.forEach((node, i) => {
    node.rotation.x = t * 0.00028 + i;
    node.rotation.y = t * 0.00019 + i;
  });
}

export function unmount() {
  _compileSerial += 1;
  if (_compileController && _compileController.abort) {
    try { _compileController.abort(); } catch (_) {}
  }
  _compileController = null;
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} });
  _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach((m) => { if (m && m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}

  _ctx = _stage = _THREE = _group = _show = _core = _ring = _boundaryPill = null;
  _nodes = [];
  _links = [];
  _frameRegistered = false;
  S.security = S.claim = null;
  S.fetch.security = S.fetch.claim = "init";
  S.mode = S.effectors = S.signing = null;
  S.verdict = "AWAITING-CONTRACTS";
  _proseInput = _compileButton = _compileStatus = _candidateList = null;
}

export default {
  id: ID,
  title: TITLE,
  endpoints: [SECURITY_EP, CLAIM_EP, ATOMIZE_EP],
  mount,
  unmount,
};
