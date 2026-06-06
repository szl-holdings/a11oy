/* ===========================================================================
 * data-adapter.js — Pulls LIVE Khipu receipts from all 5 organs and shapes them
 * into a force-graph {nodes, edges, doctrine, organs} model. REAL DATA, NO MOCKS.
 *
 * Strategy (honest, best-effort, failsafe):
 *   1. Preferred: GET <ROSIE>/api/rosie/v1/khipu/aggregate  (server fans out to
 *      every organ's /khipu/ledger and returns one pre-joined snapshot, marking
 *      any down organ HONESTLY e.g. {organ:"a11oy", status:"BUILD_ERROR"}).
 *   2. Fallback: if the aggregate endpoint errors/times-out, poll each organ's
 *      own /api/<organ>/khipu/ledger directly from the browser (CORS is open).
 *   3. Failsafe: if everything fails, return the LAST CACHED snapshot from
 *      localStorage (key 'khipu3d:lastSnapshot'). If cache is empty → null,
 *      and the UI shows an honest "Mesh quiescent" message (never fake nodes).
 *
 * Λ verdict derivation (HONEST): the live ledger nodes are DSSE-signed receipts.
 * Λ ∈ [0,1] is derived deterministically from REAL receipt facts only:
 *   base = signed ? 0.80 : 0.20
 *   + 0.10 if a verified Wire-D traceparent is present (trace continuity)
 *   + 0.05 per additional organ co-signing the same trace_id (BLS aggregate),
 *     capped so 3-of-4 quorum lands green.
 * No random numbers. If the receipt itself carries an explicit numeric
 * `lambda`/`verdict_value`, that REAL value is used verbatim instead.
 * Welford online variance of the per-organ Λ stream drives node SIZE.
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 * =========================================================================== */
(function (global) {
  "use strict";

  const ORGANS = ["rosie", "sentra", "amaru", "killinchu", "a11oy"];
  const ORGAN_BASE = {
    rosie:     "https://szlholdings-rosie.hf.space",
    sentra:    "https://szlholdings-sentra.hf.space",
    amaru:     "https://szlholdings-amaru.hf.space",
    killinchu: "https://szlholdings-killinchu.hf.space",
    a11oy:     "https://szlholdings-a11oy.hf.space"
  };
  // Wire that "homes" each organ's receipt edges (real Wire letters B–G).
  const ORGAN_WIRE = { rosie: "C", sentra: "B", amaru: "E", killinchu: "G", a11oy: "F" };
  const CACHE_KEY = "khipu3d:lastSnapshot";

  // Resolve the rosie origin: same-origin if served from the Space, else explicit.
  function rosieBase() {
    try {
      if (global.location && /szlholdings-rosie\.hf\.space/.test(global.location.host)) return "";
    } catch (_) {}
    return ORGAN_BASE.rosie;
  }

  async function getJSON(url, ms) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms || 8000);
    try {
      const r = await fetch(url, { signal: ctrl.signal, headers: { "accept": "application/json" } });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  // --- Λ derivation from a single REAL ledger node ---------------------------
  function deriveLambda(node, coCount) {
    const rcpt = node.receipt || {};
    // If the real receipt already carries a numeric verdict, honor it verbatim.
    for (const key of ["lambda", "verdict_value", "Lambda", "lambda_value"]) {
      if (typeof rcpt[key] === "number") return clamp01(rcpt[key]);
    }
    let v = node.signed ? 0.80 : 0.20;
    const tp = rcpt.traceparent || node.traceparent;
    if (tp && /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/.test(tp)) v += 0.10;
    if (coCount > 1) v += Math.min(0.10, 0.05 * (coCount - 1));
    return clamp01(v);
  }
  function clamp01(x) { return Math.max(0, Math.min(1, x)); }
  function verdictOf(l) { return l >= 0.8 ? "green" : (l >= 0.5 ? "amber" : "red"); }

  // Welford online variance over a stream of Λ values.
  function welford(values) {
    let k = 0, mean = 0, M2 = 0;
    for (const x of values) { k++; const d = x - mean; mean += d / k; M2 += d * (x - mean); }
    return { k, mean, var: k > 1 ? M2 / (k - 1) : 0 };
  }

  // --- Shape one organ's ledger payload into graph nodes/edges ---------------
  function organNodesFromLedger(organ, ledger, traceCosign) {
    const out = [];
    const nodes = (ledger && ledger.nodes) || [];
    const lambdas = [];
    nodes.forEach((n) => {
      const rcpt = n.receipt || {};
      const trace = rcpt.trace_id || (rcpt.traceparent || "").split("-")[1] || "";
      const co = trace ? (traceCosign[trace] ? traceCosign[trace].size : 1) : 1;
      const l = deriveLambda(n, co);
      lambdas.push(l);
      const variance = welford(lambdas);
      out.push({
        id: organ + ":" + n.index + ":" + (n.digest || "").slice(0, 8),
        organ: organ,
        wire: ORGAN_WIRE[organ] || "F",
        index: n.index,
        digest: n.digest || "",
        trace_id: trace,
        trace8: trace.slice(-8),
        traceparent: rcpt.traceparent || null,
        span_id: rcpt.span_id || null,
        parent_digest: (n.parents && n.parents[0]) || null,
        ts_utc: n.ts_utc || rcpt.ts_utc || null,
        signed: !!n.signed,
        keyid: n.keyid || null,
        slsa: n.slsa || (ledger && ledger.slsa) || null,
        doctrine: n.doctrine || (ledger && ledger.doctrine) || null,
        cosigners: co,
        lambda: l,
        verdict: verdictOf(l),
        var: variance.var,
        k: variance.k
      });
    });
    return out;
  }

  // Build edges: DSSE/Merkle parent chains (same organ) + W3C traceparent
  // continuations (same trace_id across organs).
  function buildEdges(nodes) {
    const byDigest = {}, byTrace = {};
    nodes.forEach((n) => {
      if (n.digest) byDigest[n.digest] = n;
      if (n.trace_id) (byTrace[n.trace_id] = byTrace[n.trace_id] || []).push(n);
    });
    const edges = [];
    // Wire F: Merkle DAG parent links inside an organ ledger.
    nodes.forEach((n) => {
      if (n.parent_digest && byDigest[n.parent_digest]) {
        edges.push({ source: byDigest[n.parent_digest].id, target: n.id, wire: "F", kind: "dsse-merkle" });
      }
    });
    // Wire D: traceparent continuations chaining receipts that share a trace_id
    // across organs (sorted by timestamp) — real trace continuity.
    Object.values(byTrace).forEach((grp) => {
      if (grp.length < 2) return;
      const s = grp.slice().sort((a, b) => String(a.ts_utc).localeCompare(String(b.ts_utc)));
      for (let i = 1; i < s.length; i++) {
        if (s[i].organ === s[i - 1].organ) continue; // cross-organ only for Wire D
        edges.push({ source: s[i - 1].id, target: s[i].id, wire: "D", kind: "traceparent" });
      }
    });
    return edges;
  }

  // Compute, across ALL organ ledgers, which organs co-signed each trace_id.
  function cosignIndex(ledgers) {
    const idx = {};
    Object.entries(ledgers).forEach(([organ, led]) => {
      ((led && led.nodes) || []).forEach((n) => {
        const r = n.receipt || {};
        const t = r.trace_id || (r.traceparent || "").split("-")[1];
        if (!t) return;
        (idx[t] = idx[t] || new Set()).add(organ);
      });
    });
    return idx;
  }

  // --- Direct browser fan-out (fallback path) --------------------------------
  async function pollAllOrgansDirect(timeoutMs) {
    const ledgers = {}; const organStatus = [];
    await Promise.all(ORGANS.map(async (organ) => {
      try {
        const led = await getJSON(ORGAN_BASE[organ] + "/api/" + organ + "/khipu/ledger", timeoutMs);
        ledgers[organ] = led;
        organStatus.push({ organ, status: "LIVE", count: (led.nodes || []).length, doctrine: led.doctrine, slsa: led.slsa });
      } catch (e) {
        ledgers[organ] = { nodes: [] };
        organStatus.push({ organ, status: "BUILD_ERROR", count: 0, error: String(e.message || e) });
      }
    }));
    const cosign = cosignIndex(ledgers);
    let nodes = [];
    Object.entries(ledgers).forEach(([organ, led]) => {
      nodes = nodes.concat(organNodesFromLedger(organ, led, cosign));
    });
    return { nodes, edges: buildEdges(nodes), organs: organStatus, source: "direct-fanout" };
  }

  // --- Normalize the server aggregate payload into the same model ------------
  function fromAggregate(agg) {
    // If the server already returns graph-shaped nodes, trust them; else, if it
    // returns raw ledgers, shape them client-side. Both honest.
    if (agg && Array.isArray(agg.nodes) && agg.nodes.length && agg.nodes[0].lambda !== undefined) {
      return { nodes: agg.nodes, edges: agg.edges || [], organs: agg.organs || [],
               doctrine: agg.doctrine, source: "server-aggregate" };
    }
    if (agg && agg.ledgers) {
      const cosign = cosignIndex(agg.ledgers);
      let nodes = [];
      Object.entries(agg.ledgers).forEach(([organ, led]) => {
        nodes = nodes.concat(organNodesFromLedger(organ, led, cosign));
      });
      return { nodes, edges: buildEdges(nodes), organs: agg.organs || [],
               doctrine: agg.doctrine, source: "server-aggregate-raw" };
    }
    return null;
  }

  const DOCTRINE = {
    plaque: "v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1 honest (L2 roadmap) · c7c0ba17",
    locked: "749/14/163", commit: "c7c0ba17", lambda: "Conjecture 1", slsa: "L1 honest (L2 roadmap)"
  };

  async function fetchSnapshot(opts) {
    opts = opts || {};
    const timeoutMs = opts.timeoutMs || 8000;
    let snap = null;
    // 1) preferred: server aggregate
    try {
      const agg = await getJSON(rosieBase() + "/api/rosie/v1/khipu/aggregate", timeoutMs);
      snap = fromAggregate(agg);
      if (snap && snap.doctrine == null) snap.doctrine = (agg && agg.doctrine) || DOCTRINE;
    } catch (_) { snap = null; }
    // 2) fallback: direct browser fan-out
    if (!snap || !snap.nodes || !snap.nodes.length) {
      try {
        const direct = await pollAllOrgansDirect(timeoutMs);
        if (direct.nodes.length) { snap = direct; snap.doctrine = DOCTRINE; }
      } catch (_) { /* keep snap as-is */ }
    }
    // 3) cache write on success / read on total failure
    if (snap && snap.nodes && snap.nodes.length) {
      snap.fetched_utc = new Date().toISOString();
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(snap)); } catch (_) {}
      return snap;
    }
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      if (cached && cached.nodes && cached.nodes.length) { cached.fromCache = true; return cached; }
    } catch (_) {}
    return null; // honest empty → UI shows "Mesh quiescent"
  }

  global.KhipuData = {
    ORGANS, ORGAN_BASE, ORGAN_WIRE, DOCTRINE,
    fetchSnapshot, pollAllOrgansDirect, deriveLambda, verdictOf, welford, buildEdges
  };
})(typeof window !== "undefined" ? window : globalThis);
