// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainqueryaudit.js — BRAIN QUERY AUDIT. A governed, append-only,
// hash-linked ledger of brain queries and the honest verdict each returned, rendered
// as a vertical chain of link-plates. Each plate is one audit entry; a bright rung
// between plates is drawn only where the hash-link VERIFIES. It reads the current
// ledger from the backend (GET /brain/audit) and can append a demo entry
// (POST /brain/audit/record) that mints an UNSIGNED SHA-256 receipt chained to the
// prior entry.
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * the surface's own view is MODELED (a derived audit view, not a measurement).
//   * chain integrity is RECOMPUTED by the server on every read: CHAIN-INTACT vs
//     CHAIN-BROKEN is reported verbatim; a broken chain is NEVER shown as intact.
//   * each receipt is an UNSIGNED-CONTENT-DIGEST (plain SHA-256) — NOT a signature,
//     NOT a proof beyond the content digest. RECEIPT-ON-WRITE: GET mints nothing.
//   * the ledger is EPHEMERAL (in-memory) and labelled so; never durable storage.
//   * Λ = Conjecture 1 → GREY, never green. locked-proven = exactly 8.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brainqueryaudit";
const TITLE = "Brain Query Audit — append-only hash-linked ledger";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_INFO   = "/api/a11oy/v1/brain/audit/info";
const EP_AUDIT  = "/api/a11oy/v1/brain/audit";
const EP_RECORD = "/api/a11oy/v1/brain/audit/record";

// palette (doctrine v11) — NO purple
const C_OK     = 0x3af4c8;  // proof-teal — an entry plate on an INTACT chain
const C_MID    = 0x5b8dee;  // lattice-blue — neutral plate / verified rung
const C_WARN   = 0x8a6bff;  // violet-blue — attention (a broken link)
const C_CONJ   = 0x5a6570;  // GREY — broken/degraded floor — never green
const C_BASE   = 0x1b3a44;  // dim base grid

const MAX_PLATES = 24;

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;

// scene objects
let _plateGeo = null, _rungGeo = null;
let _meshes = [];   // entry plate + rung meshes

const S = {
  label: "MODELED", state: "idle",
  verdict: "CHAIN-INTACT", verdictReason: null,
  entryCount: 0,
  ledger: [],                // [{seq, query, returned_verdict, grounding_label, receipt, prev_receipt}]
  firstBroken: null,         // index of first broken link, or null
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
  _plateGeo = new _THREE.BoxGeometry(1, 1, 1);
  _rungGeo = new _THREE.CylinderGeometry(0.06, 0.06, 1, 10);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  if (_show) {
    _show.attachSceneLabels({
      objects: () => _meshes.filter((m) => m.userData && m.userData.entry),
      text: (o) => "#" + ((o.userData && o.userData.entry && o.userData.entry.seq) ?? "?"),
      weight: (o) => (o.userData && o.userData.entry ? 1 : 0),
      topN: 8, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  _fetchAudit();

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
// data — GET current ledger + recomputed integrity verdict. Mints nothing.
// -------------------------------------------------------------------------- //
function _fetchAudit() {
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  fetch(EP_AUDIT, { headers: { accept: "application/json" },
                    signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => { _inFlight = null; _onAudit(j); })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      _inFlight = null;
      S.state = "error"; _setBadge("error"); _paintOverlay();
    });
}

// POST one demo entry → server appends + mints an UNSIGNED SHA-256 receipt.
function _appendDemo() {
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const body = JSON.stringify({
    query: "audit demo — what grounds this claim @ " + new Date().toISOString(),
    returned_verdict: "GROUNDED",
    grounding_label: "MODELED",
  });
  fetch(EP_RECORD, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body,
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then(() => _fetchAudit())   // re-read the ledger so the chain is server-verified
    .catch(() => { S.state = "error"; _setBadge("error"); _paintOverlay(); });
}

function _onAudit(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  S.label = _readLabel(j, "MODELED");
  S.verdict = String(j.verdict || "CHAIN-INTACT").toUpperCase();
  S.verdictReason = j.verdict_reason || null;
  S.entryCount = (typeof j.entry_count === "number") ? j.entry_count : 0;
  S.ledger = Array.isArray(j.ledger) ? j.ledger.slice(0, MAX_PLATES) : [];
  S.firstBroken = (j.integrity && j.integrity.first_broken_index != null)
    ? j.integrity.first_broken_index : null;
  S.note = (j.persistence && j.persistence.note) || null;
  S.state = "live"; _setBadge("live");
  _rebuild(); _paintOverlay();
}

// A plate is proof-teal on an INTACT chain, GREY below/at a broken link.
function _plateColor(i) {
  if (S.verdict === "CHAIN-BROKEN") {
    if (S.firstBroken != null && i === S.firstBroken) return C_WARN; // the break itself
    if (S.firstBroken != null && i > S.firstBroken) return C_CONJ;   // downstream doubt
  }
  return C_OK;
}

// -------------------------------------------------------------------------- //
// build — a vertical chain: one plate per entry, a rung between verified links.
// -------------------------------------------------------------------------- //
function _rebuild() {
  if (!_group) return;
  _clearScene();
  const entries = S.ledger || [];
  const n = entries.length;
  if (!n) return;
  const gap = 1.6;
  const y0 = -((n - 1) * gap) / 2;

  entries.forEach((e, i) => {
    const col = _plateColor(i);
    const mat = new _THREE.MeshStandardMaterial({
      color: col, emissive: col, emissiveIntensity: 0.22,
      metalness: 0.12, roughness: 0.5, transparent: true, opacity: 0.95,
    });
    const mesh = new _THREE.Mesh(_plateGeo, mat);
    mesh.scale.set(4.2, 0.55, 0.6);
    const y = y0 + i * gap;
    mesh.position.set(0, y, 0);
    mesh.userData = { entry: e, baseGlow: 0.22 };
    _meshes.push(mesh);
    _group.add(mesh);

    // rung to the prior plate — bright lattice-blue where the hash-link holds,
    // grey where it is the broken link. This is a VERBATIM read of server integrity.
    if (i > 0) {
      const broken = (S.verdict === "CHAIN-BROKEN" && S.firstBroken === i);
      const rc = broken ? C_CONJ : C_MID;
      const rmat = new _THREE.MeshStandardMaterial({
        color: rc, emissive: rc, emissiveIntensity: broken ? 0.12 : 0.35,
        metalness: 0.1, roughness: 0.45, transparent: true, opacity: 0.9,
      });
      const rung = new _THREE.Mesh(_rungGeo, rmat);
      rung.scale.set(1, gap - 0.55, 1);
      rung.position.set(0, y - gap / 2, 0);
      rung.userData = { link: true, baseGlow: broken ? 0.12 : 0.35 };
      _meshes.push(rung);
      _group.add(rung);
    }
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
    const base = m.userData.baseGlow || 0.22;
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
    chips: [{ label: "MODELED", text: "audit view", name: "src" }],
    legend: ["MODELED", "CHAIN-INTACT", "CHAIN-BROKEN", "UNSIGNED-CONTENT-DIGEST"],
    description:
      "<b>An append-only, hash-linked log of brain queries and the honest verdict each " +
      "returned.</b> Every entry records the <b>query</b>, when it was asked, the " +
      "<b>verdict</b> it got, and the grounding <b>label</b> (all verbatim). Appending an " +
      "entry mints an <b>UNSIGNED SHA-256</b> receipt that chains to the prior entry's " +
      "receipt (tamper-evident — a mini transparency log). On every read the server " +
      "<b>recomputes</b> the whole chain and reports <b>CHAIN-INTACT</b> or " +
      "<b>CHAIN-BROKEN</b> — a broken chain is never shown as intact. The view itself is " +
      "<b>MODELED</b> (a derived audit view, not a measurement).",
    citations:
      "Ledger is LIVE from /api/a11oy/v1/brain/audit (pure read — no signing on GET) over the " +
      "same process as the other brain-honesty surfaces. Appends go via POST " +
      "/api/a11oy/v1/brain/audit/record, which mints an unsigned SHA-256 content digest " +
      "(receipt-on-write). The ledger is ephemeral (in-memory) and labelled so. Λ = " +
      "Conjecture 1 (grey, never proven green); nothing here touches the locked-8.",
    plain: { html: _plainHtml },
  });

  // buttons: append a demo entry (POST) + refresh (GET)
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;gap:6px;align-items:center";
  const recBtn = document.createElement("button");
  recBtn.type = "button";
  recBtn.textContent = "append demo entry";
  recBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  recBtn.addEventListener("click", () => _appendDemo());
  const refBtn = document.createElement("button");
  refBtn.type = "button";
  refBtn.textContent = "refresh ledger";
  refBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #1c2836;background:#0a1117;color:#c9d6df";
  refBtn.addEventListener("click", () => _fetchAudit());
  wrap.appendChild(recBtn); wrap.appendChild(refBtn);
  _show.appendBody(wrap);

  // KPI rows
  _el.verdict = _show.addField("Chain verdict");
  _el.count   = _show.addField("Entries");
  _el.broken  = _show.addField("First broken link");
  _el.receipt = _show.addField("Receipt mode");

  // recent-entry list (verbatim query + verdict + label)
  _el.entries = document.createElement("div");
  _el.entries.style.cssText =
    "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf";
  _show.appendBody(_el.entries);

  // honest note (verbatim from the endpoint)
  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "MODELED", { text: "audit view" });

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const loading = S.state === "loading";

  set("verdict", loading ? "loading…" : S.verdict);
  set("count", loading ? "…" : _fmt(S.entryCount));
  set("broken", loading ? "…"
      : (S.firstBroken == null ? "none (intact)" : ("#" + S.firstBroken)));
  set("receipt", "UNSIGNED-CONTENT-DIGEST · sha256 · signed:false");

  // recent entries (verbatim, newest last)
  if (_el.entries) {
    _el.entries.textContent = "";
    (S.ledger || []).forEach((e) => {
      const line = document.createElement("div");
      line.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
      const q = (e.query != null && String(e.query).length) ? String(e.query) : "(empty)";
      const v = e.returned_verdict || "—";
      const l = e.grounding_label || "—";
      const rc = e.receipt ? String(e.receipt).slice(0, 10) : "—";
      line.textContent = "#" + e.seq + " · " + v + " · " + l + " · " + rc + "… · " + q;
      _el.entries.appendChild(line);
    });
  }

  if (_el.note) {
    let note = S.note || "";
    if (S.state === "error") note = "audit error — the brain-audit API did not respond.";
    else if (S.verdictReason) note = S.verdictReason + (note ? "  " + note : "");
    _el.note.textContent = note;
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "This is a tamper-evident <b>logbook</b> for questions asked of our estate's " +
    "<b>brain</b>. Every time a question is logged, we save the question, the answer's " +
    "honesty <b>verdict</b>, and a fingerprint (a SHA-256 <b>receipt</b>) that is linked " +
    "to the previous entry — like each page of a ledger referencing the page before it. " +
    "If anyone edits an old entry, the fingerprints stop matching and the server says " +
    "<b>CHAIN-BROKEN</b> instead of pretending everything is fine. Those receipts are " +
    "<b>unsigned</b> fingerprints, not signatures or proof of anything beyond the content. " +
    "The logbook lives in memory only, so it resets when the service restarts — we say so " +
    "rather than pretending it is permanent. View label <b>" + (S.label || "MODELED") + "</b>."
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
  try { if (_plateGeo) _plateGeo.dispose(); } catch (_) {}
  try { if (_rungGeo) _rungGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _plateGeo = _rungGeo = null;
  _group = _show = _badge = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = "MODELED"; S.state = "idle";
  S.verdict = "CHAIN-INTACT"; S.verdictReason = null;
  S.entryCount = 0; S.ledger = []; S.firstBroken = null; S.note = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_INFO, EP_AUDIT, EP_RECORD], mount, unmount };
