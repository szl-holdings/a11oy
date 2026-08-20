/* =============================================================================
 * covenant-cockpit.js — SZL Living Anatomy · COVENANT COCKPIT v1 (data spine)
 * =============================================================================
 * The holographic trust surface of PCGI (Proof-Carrying Governed Intelligence).
 * This module is the HONEST DATA SPINE for covenant-cockpit.html's Three.js
 * scene. It reads REAL szl-receipt in-toto receipts and turns each governed
 * decision into a provenance graph:
 *
 *     decision ──governs──▶  Λ-gate (policy_id)
 *              ──backs────▶  Lean proof (lean_theorem @ kernel_commit)
 *              ──burned───▶  energy (measured joules OR honest UNAVAILABLE)
 *              ──cosigned─▶  BFT witness(es)
 *
 * CRITICAL DISCIPLINE (binding — honest by construction):
 *   - Nodes come ONLY from real receipt JSON. No receipts → an HONEST empty
 *     state ("no receipts yet"). We NEVER fabricate a node.
 *   - The verify badge is a GENUINE WebCrypto ECDSA-P256-SHA256 check over the
 *     szl-receipt DSSE PAE, against the bundled cosign public key. An unsigned
 *     receipt reads UNAVAILABLE (unsigned-honest), never a fake "verified".
 *   - Energy is verbatim measured joules OR the string UNAVAILABLE — a joule is
 *     never fabricated.
 *   - Λ is advisory; its uniqueness is Conjecture 1 — surfaced from the receipt,
 *     never dressed up as a theorem. The Lean proof node backs the KERNEL
 *     invariant, not "the AI is correct".
 *   - Read-only, same-origin. Loads ./receipts.json if present, else the bundled
 *     ./receipts.sample.json, else the honest empty state.
 *
 * No build step, no framework, no CDN — a plain ES module that runs as a static
 * SDK page at the .static.hf.space URL, exactly like index.html / live-body.html.
 * The pure functions (normalizeBundle / buildGraph / verifyEnvelope) take no DOM
 * and are unit-tested headless in qa_cockpit.mjs.
 * ============================================================================ */
"use strict";

/* ---- KANCHAY palette (canonical brand · purple BANNED) -------------------- */
const KANCHAY = {
  void:    "#080c14",
  proof:   "#3af4c8",   // teal  — Lean proof / verified
  lattice: "#5b8dee",   // blue  — decision node / edges
  gold:    "#d7b96b",   // gold  — Λ-gate / policy
  warn:    "#e0795b",   // ember — energy burned / failed verify
  audit:   "#9ef0c0",   // mint  — BFT witness
  dim:     "#3a4456",   // honest unavailable / dormant
  text:    "#e9eef7",
};

/* ---- node kinds → color + geometry hint ---------------------------------- */
const NODE_KIND = {
  decision: { color: KANCHAY.lattice, glyph: "◆", label: "decision" },
  gate:     { color: KANCHAY.gold,    glyph: "⛨", label: "Λ-gate" },
  proof:    { color: KANCHAY.proof,   glyph: "⊢", label: "Lean proof" },
  energy:   { color: KANCHAY.warn,    glyph: "⚡", label: "energy" },
  witness:  { color: KANCHAY.audit,   glyph: "✍", label: "BFT witness" },
};

/* ---- verify status vocabulary -------------------------------------------- */
const VERIFY = {
  VERIFIED:    "verified",     // signed + WebCrypto DSSE signature valid
  UNAVAILABLE: "unavailable",  // unsigned-honest, or no pubkey, or not run
  FAILED:      "failed",       // signed but signature invalid (tamper)
  PENDING:     "pending",
};

/* ---- candidate data sources (same-origin, read-only) --------------------- */
const SOURCES = ["./receipts.json", "./receipts.sample.json"];

/* ---- one honest GET (never throws) --------------------------------------- */
async function getJSON(url, timeoutMs = 9000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET", mode: "same-origin", credentials: "omit",
      signal: ctl.signal, cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) return { ok: false, why: `HTTP ${res.status}` };
    return { ok: true, json: await res.json() };
  } catch (e) {
    clearTimeout(t);
    return { ok: false, why: (e && e.name === "AbortError") ? "timeout" : "not found" };
  }
}

/* ---- base64 → bytes (browser + node safe) -------------------------------- */
function b64ToBytes(b64) {
  if (typeof atob === "function") {
    const bin = atob(String(b64).replace(/-/g, "+").replace(/_/g, "/"));
    const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return u;
  }
  return new Uint8Array(Buffer.from(String(b64), "base64"));   // node fallback
}

/* ---- normalize a loaded bundle into honest receipt records --------------- *
 * Accepts the bundled shape {cosign_pub, receipts:[{id,envelope,statement}]}
 * OR a bare array of envelopes/records. Returns decoded, doctrine-clean records.
 * Pure: no DOM, no network. */
function normalizeBundle(raw) {
  let list = [];
  let cosignPub = null;
  if (Array.isArray(raw)) {
    list = raw;
  } else if (raw && typeof raw === "object") {
    cosignPub = raw.cosign_pub || raw.cosignPub || null;
    list = raw.receipts || raw.items || [];
  }
  const receipts = [];
  for (const entry of (Array.isArray(list) ? list : [])) {
    // an entry may be {envelope, statement, id} OR a bare envelope
    const env = entry && entry.envelope ? entry.envelope
      : (entry && entry.payload ? entry : null);
    if (!env || !env.payload) continue;   // not a receipt shape → skip (no fake node)
    let body = null;
    try { body = JSON.parse(new TextDecoder().decode(b64ToBytes(env.payload))); }
    catch { body = null; }
    if (!body || typeof body !== "object") continue;   // undecodable → honest skip
    receipts.push({
      id: entry.id || body.subject || env.digest || `receipt-${receipts.length}`,
      envelope: env,
      statement: entry.statement || null,
      body,
      digest: env.digest || null,
      signed: env.signed === true,
    });
  }
  return { receipts, cosignPub };
}

/* ---- build the provenance graph from real receipts (PURE) ---------------- *
 * Returns {nodes, edges, stats}. Empty input → empty graph (honest). */
function buildGraph(receipts) {
  const nodes = [];
  const edges = [];
  const byId = new Map();
  const list = Array.isArray(receipts) ? receipts : [];

  function ensure(id, kind, label, meta) {
    let n = byId.get(id);
    if (n) { n.degree++; return n; }
    n = { id, kind, label, meta: meta || {}, degree: 1, pos: [0, 0, 0] };
    byId.set(id, n); nodes.push(n);
    return n;
  }

  list.forEach((r, i) => {
    const b = r.body || {};
    const dId = `d:${r.id}`;
    const decision = ensure(dId, "decision", r.id, {
      receiptIndex: i, receiptId: r.id, verdict: b.verdict, producer: b.producer,
    });
    // Λ-gate that governed it
    if (b.policy_id) {
      const g = ensure(`g:${b.policy_id}`, "gate", b.policy_id, { policy_id: b.policy_id });
      edges.push({ from: dId, to: g.id, kind: "governs" });
    }
    // Lean proof backing the KERNEL invariant (not "the AI is correct")
    if (b.lean_theorem) {
      const p = ensure(`p:${b.lean_theorem}`, "proof", b.lean_theorem, {
        lean_theorem: b.lean_theorem, kernel_commit: b.kernel_commit || null,
      });
      edges.push({ from: dId, to: p.id, kind: "backs" });
    }
    // energy burned (measured joules OR honest UNAVAILABLE)
    const energy = b.energy;
    const measured = energy && typeof energy === "object" && typeof energy.joules === "number";
    const e = ensure(`e:${r.id}`, "energy", measured ? `${energy.joules} J` : "UNAVAILABLE", {
      measured: !!measured,
      joules: measured ? energy.joules : null,
      receiptId: r.id,
    });
    edges.push({ from: dId, to: e.id, kind: "burned" });
    // BFT witnesses that co-signed
    for (const w of (Array.isArray(b.bft_witnesses) ? b.bft_witnesses : [])) {
      const wn = ensure(`w:${w}`, "witness", String(w), { witness: String(w) });
      edges.push({ from: dId, to: wn.id, kind: "cosigned" });
    }
  });

  layout(nodes);

  const stats = {
    receipts: list.length,
    decisions: nodes.filter((n) => n.kind === "decision").length,
    gates: nodes.filter((n) => n.kind === "gate").length,
    proofs: nodes.filter((n) => n.kind === "proof").length,
    witnesses: nodes.filter((n) => n.kind === "witness").length,
    energyMeasured: nodes.filter((n) => n.kind === "energy" && n.meta.measured).length,
    energyUnavailable: nodes.filter((n) => n.kind === "energy" && !n.meta.measured).length,
    edges: edges.length,
  };
  return { nodes, edges, stats };
}

/* deterministic 3D orbital layout by node kind (mutates node.pos) ----------- */
function layout(nodes) {
  const byKind = {};
  for (const n of nodes) (byKind[n.kind] = byKind[n.kind] || []).push(n);
  // ring placer: even angular spread, per-kind phase, on a shell
  const ring = (arr, radius, y, phase, zJitter) => {
    const n = arr.length;
    arr.forEach((node, i) => {
      const a = (n <= 1 ? phase : (i / n) * Math.PI * 2 + phase);
      node.pos = [
        Math.cos(a) * radius,
        y + (zJitter ? Math.sin(i * 1.7) * zJitter : 0),
        Math.sin(a) * radius,
      ];
      node._angle = a;
    });
  };
  ring(byKind.decision || [], 1.5, 0.0, Math.PI / 2, 0.12);   // inner ring
  ring(byKind.gate || [], 1.1, 1.5, 0.0, 0.0);                // top dome
  ring(byKind.proof || [], 1.1, -1.5, Math.PI, 0.0);          // bottom dome
  ring(byKind.witness || [], 3.1, 0.0, Math.PI / 5, 0.5);     // outer equatorial
  // energy sits radially just outside its own decision
  const decs = byKind.decision || [];
  const decAngle = new Map(decs.map((d) => [d.meta.receiptId, d._angle]));
  for (const e of (byKind.energy || [])) {
    const a = decAngle.has(e.meta.receiptId) ? decAngle.get(e.meta.receiptId)
      : Math.random() * Math.PI * 2;
    e.pos = [Math.cos(a) * 2.3, -0.1, Math.sin(a) * 2.3];
  }
}

/* ---- WebCrypto DSSE ECDSA-P256-SHA256 verify (szl-receipt binary-LE PAE) -- *
 * Matches szl_receipt._canonical.pae EXACTLY: little-endian 64-bit lengths,
 * NOT the ascii-decimal DSSE variant. Returns a VERIFY.* status. */
function _cat() {
  const arrs = [].slice.call(arguments);
  let n = 0; for (const a of arrs) n += a.length;
  const o = new Uint8Array(n); let p = 0;
  for (const a of arrs) { o.set(a, p); p += a.length; }
  return o;
}
function _le64(n) {
  const b = new Uint8Array(8); let v = BigInt(n);
  for (let i = 0; i < 8; i++) { b[i] = Number(v & 0xffn); v >>= 8n; }
  return b;
}
function _paeBinary(payloadType, payloadBytes) {
  const enc = new TextEncoder();
  const t = enc.encode(payloadType || "");
  return _cat(enc.encode("DSSEv1 "), _le64(t.length), t,
    enc.encode(" "), _le64(payloadBytes.length), payloadBytes);
}
function _derToRaw(der) {
  let i = 0;
  if (der[i++] !== 0x30) throw new Error("bad DER (no SEQUENCE)");
  let sl = der[i++]; if (sl & 0x80) { let n = sl & 0x7f; while (n--) i++; }
  const rdInt = () => {
    if (der[i++] !== 0x02) throw new Error("bad DER (no INTEGER)");
    const len = der[i++]; let v = der.slice(i, i + len); i += len;
    while (v.length > 1 && v[0] === 0) v = v.slice(1);
    return v;
  };
  const r = rdInt(), s = rdInt();
  const out = new Uint8Array(64); out.set(r, 32 - r.length); out.set(s, 64 - s.length);
  return out;
}
function _subtle() {
  if (typeof crypto !== "undefined" && crypto.subtle) return crypto.subtle;
  if (typeof globalThis !== "undefined" && globalThis.crypto && globalThis.crypto.subtle)
    return globalThis.crypto.subtle;
  return null;
}
async function importCosign(pem) {
  const s = _subtle(); if (!s) throw new Error("WebCrypto unavailable");
  const b64 = String(pem).replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  return s.importKey("spki", b64ToBytes(b64), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
}
async function verifyEnvelope(envelope, key) {
  if (!envelope || envelope.signed !== true || !envelope.signature)
    return { status: VERIFY.UNAVAILABLE, detail: "unsigned-honest (no signature)" };
  if (!key) return { status: VERIFY.UNAVAILABLE, detail: "no cosign public key bundled" };
  const s = _subtle(); if (!s) return { status: VERIFY.UNAVAILABLE, detail: "WebCrypto unavailable" };
  try {
    const payload = b64ToBytes(envelope.payload);
    const pae = _paeBinary(envelope.payloadType, payload);
    const rawSig = _derToRaw(b64ToBytes(envelope.signature));
    const ok = await s.verify({ name: "ECDSA", hash: "SHA-256" }, key, rawSig, pae);
    return ok
      ? { status: VERIFY.VERIFIED, detail: "ECDSA-P256-SHA256 over DSSE PAE — unaltered from signer" }
      : { status: VERIFY.FAILED, detail: "signature mismatch — do NOT trust this receipt" };
  } catch (e) {
    return { status: VERIFY.UNAVAILABLE, detail: `verify error: ${e && e.message ? e.message : e}` };
  }
}

/* ---- top-level loader (browser): first present source wins ---------------- */
async function loadReceipts() {
  for (const url of SOURCES) {
    const r = await getJSON(url);
    if (!r.ok) continue;
    const { receipts, cosignPub } = normalizeBundle(r.json);
    if (receipts.length === 0) continue;         // present but empty → try next
    return { source: url, receipts, cosignPub, empty: false };
  }
  return { source: null, receipts: [], cosignPub: null, empty: true,
    why: "no receipts.json or receipts.sample.json with valid receipts" };
}

/* ---- the engine surface -------------------------------------------------- */
const CovenantCockpit = {
  KANCHAY, NODE_KIND, VERIFY, SOURCES,
  getJSON, b64ToBytes, normalizeBundle, buildGraph, layout,
  importCosign, verifyEnvelope, loadReceipts,
};

if (typeof window !== "undefined") window.CovenantCockpit = CovenantCockpit;
export default CovenantCockpit;
export {
  KANCHAY, NODE_KIND, VERIFY, SOURCES,
  getJSON, b64ToBytes, normalizeBundle, buildGraph, layout,
  importCosign, verifyEnvelope, loadReceipts,
};
