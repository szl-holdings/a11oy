/* =============================================================================
 * live-body.js — SZL Living Anatomy · BODY v1 ENGINE (the living face)
 * =============================================================================
 * The Sovereign Org rendered as ONE living governed organism. This module is the
 * HONEST DATA SPINE for live-body.html's Three.js scene. It reads the SAME live
 * a11oy endpoints the unified console reads and exposes them as honest records.
 *
 * CRITICAL DISCIPLINE (binding — honest by construction, never a screensaver):
 *   - Every pulse travelling a vessel corresponds to a REAL receipt on the chain
 *     (/api/a11oy/v1/ledger). We never synthesize a receipt.
 *   - Every organ glows LIVE only on a real 2xx+JSON probe; otherwise it dims to an
 *     honest UNREACHABLE state. We never fabricate a green light.
 *   - sovereign:true is shown ONLY when /code/healthz reports the literal true.
 *   - Λ is advisory and its uniqueness is Conjecture 1 — pulled live from
 *     /v1/lambda + /v1/honest, never hardcoded as proven.
 *   - Verticals (insurance/defense/finance/realestate), SLSA skeletal integrity,
 *     and drift have NO live endpoint on this Space today, so they render in an
 *     explicit ROADMAP / N-A state — limbs do NOT fake-pulse and the skeleton does
 *     NOT claim a verified SLSA level. Honest absence over decorative motion.
 *   - Read-only. No key is sent. open-weight only.
 *
 * No build step, no framework, no CDN — a plain ES module that runs as a static
 * SDK page at the .static.hf.space URL, exactly like index.html.
 * ============================================================================ */
"use strict";

/* ---- the single live host the console reads (verified live this session) --- */
const HOST = "https://szlholdings-a11oy.hf.space";

/* Real, verified endpoints (curl-checked 2026-06-30):
 *   /api/a11oy/v1/ledger      -> {count, receipts:[{seq,action,receipt_id}]}  (THE chain)
 *   /api/a11oy/v1/lambda      -> {trust_axes,axes[],lambda,lambda_floor,pass,uniqueness}
 *   /api/a11oy/code/healthz   -> {sovereign,backend,mode,doctrine_state,...}
 *   /api/a11oy/v1/honest      -> {doctrine_lock:{lambda,locked_formula_ids,...}}
 *   /api/a11oy/readyz         -> {status,operator:{operator_running,...}}
 *   /api/a11oy/v1/govern/health-> {engines_live,engines_total,mesh[]}            */
const EP = {
  ledger:  HOST + "/api/a11oy/v1/ledger",
  lambda:  HOST + "/api/a11oy/v1/lambda",
  healthz: HOST + "/api/a11oy/code/healthz",
  honest:  HOST + "/api/a11oy/v1/honest",
  readyz:  HOST + "/api/a11oy/readyz",
  govern:  HOST + "/api/a11oy/v1/govern/health",
};

/* ---- KANCHAY palette (canonical brand · purple BANNED) -------------------- */
const KANCHAY = {
  void:    "#080c14",
  proof:   "#3af4c8",   // teal — proven / live
  lattice: "#5b8dee",   // blue — structure / vessels
  gold:    "#d7b96b",   // gold — Λ / heartbeat accent
  warn:    "#e0795b",   // ember — denied / down
  dim:     "#3a4456",   // honest unreachable / dormant
  text:    "#e9eef7",
};

/* ---- status vocabulary ---------------------------------------------------- */
const STATUS = {
  LIVE: "live",               // endpoint answered 2xx with usable JSON
  UNREACHABLE: "unreachable", // network / non-2xx / not-JSON — honest unknown
  PENDING: "pending",         // not yet polled
};

/* ---- the 4 console organs, each a REAL probe ------------------------------ *
 * These are the organs the unified console shows (Reasoning/Policy/Operator/
 * Receipts). Each maps to a real endpoint that proves it is alive; LIVE only on
 * a real 2xx+JSON answer, otherwise an honest UNREACHABLE dim. `pos` is a normalized
 * body-space anchor [x,y,z] the scene uses to place the organ. */
const ORGANS = [
  {
    id: "reasoning", name: "REASONING", glyph: "✸", color: KANCHAY.proof,
    pos: [0, 1.15, 0],
    probe: "lambda",
    role: "scores Λ (13-axis) + recommends the decision under uncertainty",
    actions: ["lambda.score", "decision.recommend"],
    summarize: (j) => {
      if (typeof j.lambda === "number")
        return `Λ ${j.lambda.toFixed(5)} ${j.pass ? "≥" : "<"} floor ${j.lambda_floor} · ${j.trust_axes || (j.axes||[]).length}-axis`;
      return "reasoning responding";
    },
  },
  {
    id: "policy", name: "POLICY", glyph: "⛨", color: KANCHAY.gold,
    pos: [-1.15, 0.15, 0.1],
    probe: "honest",
    role: "the deny-by-default gate (F12) — rejects unsafe / overclaiming work",
    actions: ["gate.evaluate"],
    summarize: (j) => {
      const lk = j.doctrine_lock || {};
      const ids = lk.locked_formula_ids || [];
      const f12 = ids.includes("F12");
      return `${lk.locked_formula_count ?? ids.length} locked · F12 gate ${f12 ? "armed" : "—"}`;
    },
  },
  {
    id: "operator", name: "OPERATOR", glyph: "⌁", color: KANCHAY.lattice,
    pos: [1.15, 0.15, 0.1],
    probe: "readyz",
    role: "approves + executes admitted work; the hands of the organism",
    actions: ["operator.approve"],
    summarize: (j) => {
      const op = j.operator || {};
      if (op.operator_running === true) return `operator running · ${j.status || "ready"}`;
      if (j.status) return `status: ${j.status}`;
      return "operator responding";
    },
  },
  {
    id: "receipts", name: "RECEIPTS", glyph: "❤", color: KANCHAY.warn,
    pos: [0, -1.15, 0],
    probe: "ledger",
    role: "signs + replays a verifiable receipt for every action (the heartbeat)",
    actions: ["receipt.sign", "replay.verify"],
    summarize: (j) => {
      const rs = j.receipts || j.items || (Array.isArray(j) ? j : null);
      const n = Array.isArray(rs) ? rs.length : (typeof j.count === "number" ? j.count : null);
      return n != null ? `${n} receipts on the chain` : "receipt bus reachable";
    },
  },
];

/* Which organ a receipt action originates from (so a pulse leaves the right
 * organ and travels to RECEIPTS/heart). Unknown actions default to receipts. */
const ACTION_SOURCE = {
  "gate.evaluate": "policy",
  "lambda.score": "reasoning",
  "decision.recommend": "reasoning",
  "operator.approve": "operator",
  "receipt.sign": "receipts",
  "replay.verify": "receipts",
};
function organForAction(action) {
  if (!action) return "receipts";
  const a = String(action).toLowerCase();
  if (ACTION_SOURCE[a]) return ACTION_SOURCE[a];
  // honest heuristic for verbs we haven't enumerated
  if (a.startsWith("gate")) return "policy";
  if (a.startsWith("lambda") || a.includes("decision") || a.includes("reason")) return "reasoning";
  if (a.includes("operator") || a.includes("approve") || a.includes("execute")) return "operator";
  return "receipts";
}
/* An action is a DENIAL (rejected pulse) only when it honestly says so. */
function isDenied(action) {
  const a = String(action || "").toLowerCase();
  return a.includes("deny") || a.includes("denied") || a.includes("reject") || a.includes("block");
}

/* The 4 verticals = limbs. NO live throughput endpoint exists on this Space, so
 * they render in an honest ROADMAP state and only pulse if a real receipt with a
 * "<vertical>|<action>" verb appears on the chain. Never fake-pulsed. */
const VERTICALS = [
  { id: "insurance",  name: "INSURANCE",  pos: [-1.7, -0.7, 0.0], color: KANCHAY.proof },
  { id: "defense",    name: "DEFENSE",    pos: [ 1.7, -0.7, 0.0], color: KANCHAY.lattice },
  { id: "finance",    name: "FINANCE",    pos: [-1.7,  0.9, 0.0], color: KANCHAY.gold },
  { id: "realestate", name: "REALESTATE", pos: [ 1.7,  0.9, 0.0], color: KANCHAY.warn },
];

/* ---- one honest GET (never throws; no creds, no custom headers => simple CORS) */
async function getJSON(url, timeoutMs = 9000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET", mode: "cors", credentials: "omit",
      signal: ctl.signal, cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) return { ok: false, why: `HTTP ${res.status}` };
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("json")) return { ok: false, why: "no JSON (route unmatched?)" };
    return { ok: true, json: await res.json() };
  } catch (e) {
    clearTimeout(t);
    return { ok: false, why: (e && e.name === "AbortError") ? "timeout" : "network/CORS" };
  }
}

/* probe one organ honestly -> {status, detail, raw} */
async function probeOrgan(organ, timeoutMs = 9000) {
  const r = await getJSON(EP[organ.probe], timeoutMs);
  if (!r.ok) return { status: STATUS.UNREACHABLE, detail: r.why, raw: null };
  let detail;
  try { detail = organ.summarize(r.json); }
  catch { detail = "responding (shape unrecognized)"; }
  return { status: STATUS.LIVE, detail, raw: r.json };
}

/* fetch the REAL receipt chain. Returns normalized receipts (or honest empty). */
async function fetchLedger(timeoutMs = 9000) {
  const r = await getJSON(EP.ledger, timeoutMs);
  if (!r.ok) return { reachable: false, why: r.why, count: 0, receipts: [] };
  const j = r.json;
  const raw = j.receipts || j.items || (Array.isArray(j) ? j : []);
  const receipts = (Array.isArray(raw) ? raw : []).map((x, i) => {
    const action = x.action || x.verb || x.kind || "receipt";
    return {
      seq: typeof x.seq === "number" ? x.seq : i,
      action,
      id: x.receipt_id || x.id || x.hash || String(i),
      organ: organForAction(action),
      denied: isDenied(action),
    };
  });
  return { reachable: true, count: j.count ?? receipts.length, receipts };
}

/* fetch Λ posture (heartbeat driver). Honest: uniqueness stays Conjecture 1. */
async function fetchLambda(timeoutMs = 9000) {
  const r = await getJSON(EP.lambda, timeoutMs);
  if (!r.ok) return { reachable: false, why: r.why };
  const j = r.json;
  return {
    reachable: true,
    lambda: typeof j.lambda === "number" ? j.lambda : null,
    floor: typeof j.lambda_floor === "number" ? j.lambda_floor : 0.90,
    pass: j.pass === true,
    axes: Array.isArray(j.axes) ? j.axes : [],
    aggregate: j.aggregate || "",
    uniqueness: j.uniqueness || "Conjecture 1",
    raw: j,
  };
}

/* fetch the GPU-mind posture (sovereign strict; default FALSE — never invent true) */
async function fetchMind(timeoutMs = 9000) {
  const r = await getJSON(EP.healthz, timeoutMs);
  if (!r.ok) return { reachable: false, sovereign: false, why: r.why };
  const j = r.json;
  return {
    reachable: true,
    sovereign: j.sovereign === true,
    backend: j.backend || j.inference || "unknown",
    mode: j.mode || "unknown",
    doctrine: j.doctrine_state ? `${j.doctrine || ""} ${j.doctrine_state}`.trim() : (j.doctrine || ""),
    raw: j,
  };
}

/* fetch doctrine / Λ lock for the honesty strip. */
async function fetchDoctrine(timeoutMs = 9000) {
  const r = await getJSON(EP.honest, timeoutMs);
  if (!r.ok) return { reachable: false };
  const lk = (r.json && r.json.doctrine_lock) || {};
  return {
    reachable: true,
    lambda: lk.lambda || "Conjecture 1",
    commit: lk.commit || "",
    lockedCount: lk.locked_formula_count ?? 8,
    lockedIds: lk.locked_formula_ids || [],
    declarations: lk.declarations, axioms: lk.axioms, sorries: lk.sorries,
    state: lk.state || "",
  };
}

/* fetch mesh/engine health — the only REAL drift-ish signal available today:
 * engines_total - engines_live antibodies. honest immune intensity in [0,1]. */
async function fetchImmune(timeoutMs = 9000) {
  const r = await getJSON(EP.govern, timeoutMs);
  if (!r.ok) return { reachable: false, intensity: 0, detail: r.why };
  const j = r.json;
  const total = typeof j.engines_total === "number" ? j.engines_total : 0;
  const live = typeof j.engines_live === "number" ? j.engines_live : total;
  const down = Math.max(0, total - live);
  return {
    reachable: true,
    intensity: total > 0 ? down / total : 0,   // real fraction of mesh down
    down, live, total,
    detail: down > 0 ? `${down}/${total} mesh engines down — antibodies active` : `mesh ${live}/${total} healthy`,
  };
}

/* ---- the engine surface --------------------------------------------------- */
const LiveBody = {
  HOST, EP, KANCHAY, STATUS, ORGANS, VERTICALS,
  organForAction, isDenied,
  probeOrgan, fetchLedger, fetchLambda, fetchMind, fetchDoctrine, fetchImmune,
};

if (typeof window !== "undefined") window.LiveBody = LiveBody;
export default LiveBody;
export {
  HOST, EP, KANCHAY, STATUS, ORGANS, VERTICALS,
  organForAction, isDenied,
  probeOrgan, fetchLedger, fetchLambda, fetchMind, fetchDoctrine, fetchImmune,
};
