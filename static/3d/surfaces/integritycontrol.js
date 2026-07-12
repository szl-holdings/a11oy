// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
//
// Integrity Control Plane -- a compact, read-only view of two local contracts:
//   GET /api/a11oy/v1/waqay/security-loop/manifest
//   GET /api/a11oy/v1/claim-integrity/info
//
// This surface does not invoke an action route. A successful fetch means only that the
// contract manifest was read. It does NOT mean that a deployer, rollback mechanism, model,
// signer, repository writer, or any other effector is live. The view reports the API fields
// verbatim and treats any boundary mismatch as a violation rather than rounding it up.

import { createShowcase } from "./_showcase.js";

const ID = "integritycontrol";
const TITLE = "Integrity Control Plane · proposal boundaries";
const SECURITY_EP = "/api/a11oy/v1/waqay/security-loop/manifest";
const CLAIM_EP = "/api/a11oy/v1/claim-integrity/info";

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
      "contracts. It reads two same-origin GET endpoints and checks their control boundaries " +
      "without invoking a deploy, rollback, write, model, signer, or repository action. " +
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
}

export default {
  id: ID,
  title: TITLE,
  endpoints: [SECURITY_EP, CLAIM_EP],
  mount,
  unmount,
};
