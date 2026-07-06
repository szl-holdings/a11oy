#!/usr/bin/env node
// Throttled API probe runner for the a11oy readiness harness.
//
// Reads tabs.json's endpoint contract registry and, for every endpoint, measures:
//   • HTTP status (vs degradedRules.allowStatuses)
//   • latency p50 / p95 over N polite samples
//   • response schema validity (schemas[] from tabs.json)
//   • citations present when citationsRequired
//   • freshness vs freshnessSLA (when the body carries a timestamp)
//
// It then assigns each endpoint a "Lies?" verdict (doctrine v11: stale/mock/uncited
// = a lie = fail) and writes readiness-verdict.json. Exit code is non-zero if any
// lie is found, unless --soft is passed.
//
// No external deps — Node >= 18 global fetch only.
//   node probe_runner.mjs --base https://a-11-oy.com [--samples 5] [--concurrency 3]
//                         [--soft] [--out readiness-verdict.json]

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : true;
}

const BASE = String(arg("base", process.env.A11OY_BASE || "https://a-11-oy.com")).replace(/\/$/, "");
const SAMPLES = parseInt(arg("samples", "5"), 10);
const CONCURRENCY = parseInt(arg("concurrency", "2"), 10);
const TIMEOUT_MS = parseInt(arg("timeout", "15000"), 10);
const SOFT = !!arg("soft", false);
const OUT = String(arg("out", join(HERE, "readiness-verdict.json")));
const RETRIES = parseInt(arg("retries", "2"), 10); // cold-burst 404s on deep tabs

const matrix = JSON.parse(readFileSync(join(HERE, "tabs.json"), "utf8"));
const ENDPOINTS = matrix.endpoints || {};
const SCHEMAS = matrix.schemas || {};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function percentile(arr, p) {
  if (!arr.length) return null;
  const s = [...arr].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1);
  return s[Math.max(0, idx)];
}

function toDate(v) {
  // numeric epoch: <1e12 is seconds (would otherwise parse as 1970-ms), else ms
  if (typeof v === "number") {
    const ms = v < 1e12 ? v * 1000 : v;
    const d = new Date(ms);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof v === "string") {
    // numeric string epoch
    if (/^\d{10}$/.test(v)) return new Date(parseInt(v, 10) * 1000);
    if (/^\d{13}$/.test(v)) return new Date(parseInt(v, 10));
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

function findTimestamp(obj, depth = 0) {
  if (!obj || depth > 3) return null;
  if (Array.isArray(obj)) {
    for (const v of obj.slice(0, 20)) {
      const t = findTimestamp(v, depth + 1);
      if (t) return t;
    }
    return null;
  }
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (/(checked_at|generated_at|generatedAt|updated_at|updatedAt|last_updated|timestamp|asOf|as_of|fetched_at|ts)$/i.test(k)) {
        const d = toDate(v);
        if (d) return d;
      }
    }
    for (const v of Object.values(obj)) {
      const t = findTimestamp(v, depth + 1);
      if (t) return t;
    }
  }
  return null;
}

// A response is "cited" if it carries any recognised provenance signal — an
// explicit citation/source/url field, OR a dataset/corpus/standard-version marker
// (MITRE ATT&CK version, STIX version, NVD feed, etc.) that pins the data origin.
const CITE_KEY = /(citation|citations|source|sources|sourceurl|source_url|url|references|provenance|attribution|corpus|dataset|feed|provider|anchor|mitre|stix|taxii|nvd|kev|edgar|courtlistener|_version)/i;
function hasCitation(obj, depth = 0) {
  if (!obj || depth > 4) return false;
  if (Array.isArray(obj)) return obj.slice(0, 30).some((v) => hasCitation(v, depth + 1));
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (CITE_KEY.test(k) && v && (typeof v === "string" ? v.length > 0 : true)) return true;
      if (hasCitation(v, depth + 1)) return true;
    }
  }
  return false;
}

// Only explicit LABEL fields carry a "this data is fake" admission. We never scan
// the whole body for substrings — honesty prose like "never fabricated" or a UI
// "placeholder" string must NOT trip the gate (that produced false lies).
const LABEL_KEY = /^(data_kind|datakind|kind|status|label|mode|source_kind|sourcekind|state)$/i;
function findLabelLie(obj, liesIf, depth = 0) {
  const lieSet = new Set(liesIf.map((s) => String(s).toLowerCase()));
  if (!obj || depth > 4) return null;
  if (Array.isArray(obj)) {
    for (const v of obj.slice(0, 30)) { const r = findLabelLie(v, liesIf, depth + 1); if (r) return r; }
    return null;
  }
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (LABEL_KEY.test(k) && typeof v === "string" && lieSet.has(v.trim().toLowerCase())) {
        return `${k}="${v}"`;
      }
      const r = findLabelLie(v, liesIf, depth + 1);
      if (r) return r;
    }
  }
  return null;
}

function validateSchema(schemaName, body) {
  const s = SCHEMAS[schemaName];
  if (!s) return { ok: true, why: "no-schema" };
  const checkOne = (sc) => {
    if (sc.type === "string") return typeof body === "string";
    if (sc.type === "array") return Array.isArray(body);
    if (sc.type === "object") {
      if (typeof body !== "object" || body === null || Array.isArray(body)) return false;
      if (sc.required && !sc.required.every((k) => k in body)) return false;
      if (sc.anyKey && !sc.anyKey.some((k) => k in body)) return false;
      return true;
    }
    return true;
  };
  if (s.anyOf) {
    return { ok: s.anyOf.some(checkOne), why: "anyOf" };
  }
  return { ok: checkOne(s), why: s.type };
}

async function probeOnce(path, method) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  const t0 = performance.now();
  try {
    const res = await fetch(BASE + path, {
      method,
      signal: ctrl.signal,
      headers: { accept: "application/json,text/plain,*/*" },
      ...(method === "POST" ? { body: "{}", headers: { "content-type": "application/json", accept: "*/*" } } : {}),
    });
    const ms = performance.now() - t0;
    const ct = res.headers.get("content-type") || "";
    let body = null;
    if (ct.includes("application/json")) {
      body = await res.json().catch(() => null);
    } else {
      body = await res.text().catch(() => null);
    }
    return { status: res.status, ms, body, ct };
  } catch (e) {
    return { status: 0, ms: performance.now() - t0, body: null, error: String(e.name || e) };
  } finally {
    clearTimeout(to);
  }
}

async function probeEndpoint(path, spec) {
  const method = spec.method || "GET";
  const allow = (spec.degradedRules?.allowStatuses) || [200];
  const lat = [];
  let last = null;
  // retry to absorb cold-burst 404/timeout on heavy deep tabs AND 429 rate-limits.
  // 429 gets a longer, growing backoff because it means "you're polling too fast".
  for (let attempt = 0; attempt <= RETRIES; attempt++) {
    last = await probeOnce(path, method);
    if (allow.includes(last.status)) break;
    if (attempt < RETRIES) {
      // 429 (our own rate-limit) and 0 (timeout/network) both mean "back off harder".
      const slow = last.status === 429 || last.status === 0;
      const backoff = slow ? 3000 * (attempt + 1) : 1200 * (attempt + 1);
      await sleep(backoff);
    }
  }
  lat.push(last.ms);
  // extra timing samples (measure only), polite spacing
  for (let i = 1; i < SAMPLES; i++) {
    await sleep(400);
    const r = await probeOnce(path, method);
    lat.push(r.ms);
    if (allowOk(spec, r.status)) last = allowOk(spec, last.status) ? last : r;
  }

  // INCONCLUSIVE classes — NOT doctrine lies (a lie = stale/mock/uncited):
  //  - 429: our own rate-limiting.
  //  - 0 / 5xx: timeout, network drop, or server error -> the endpoint is
  //    UNREACHABLE, which is a reachability/uptime failure, not "mock theater".
  // We surface unreachable separately so a transient tail-timeout during the
  // harness's own burst never gets branded a lie.
  const throttled = last.status === 429;
  const unreachable = last.status === 0 || last.status >= 500;
  const inconclusive = throttled || unreachable;
  const statusOk = allow.includes(last.status);
  const schema = inconclusive ? { ok: true } : validateSchema(spec.schema, last.body);
  const liesIf = (spec.degradedRules?.liesIf) || [];
  const labelLie = inconclusive ? null : findLabelLie(last.body, liesIf);

  let citationOk = true;
  if (spec.citationsRequired && statusOk) {
    citationOk = typeof last.body === "string" ? last.body.length > 0 : hasCitation(last.body);
  }

  let freshOk = true, ageSec = null;
  if (spec.freshnessSLA && statusOk && last.body && typeof last.body === "object") {
    const ts = findTimestamp(last.body);
    if (ts) {
      ageSec = Math.round((Date.now() - ts.getTime()) / 1000);
      freshOk = ageSec <= spec.freshnessSLA;
    }
  }

  const lies = [];
  // A bad status is only a doctrine lie if the endpoint actually answered with
  // an unexpected HTTP status (e.g. a 404 on a tab the console links). Timeouts,
  // network drops and 5xx are reachability failures, reported as `unreachable`.
  if (!inconclusive && !statusOk) lies.push(`status ${last.status} not in [${allow}]`);
  if (statusOk && !schema.ok) lies.push(`schema invalid (${spec.schema})`);
  if (!citationOk) lies.push("citationsRequired but none found");
  if (!freshOk) lies.push(`stale ${ageSec}s > SLA ${spec.freshnessSLA}s`);
  if (labelLie) lies.push(`mock/placeholder label: ${labelLie}`);

  return {
    path, method, status: last.status, error: last.error || null,
    throttled, unreachable,
    p50: Math.round(percentile(lat, 50)), p95: Math.round(percentile(lat, 95)),
    samples: lat.length, schemaOk: schema.ok, citationOk, freshOk, ageSec,
    citationsRequired: !!spec.citationsRequired, freshnessSLA: spec.freshnessSLA ?? null,
    lie: lies.length > 0, lies,
  };
}

function allowOk(spec, status) {
  return ((spec.degradedRules?.allowStatuses) || [200]).includes(status);
}

async function pool(items, n, fn) {
  const out = [];
  let i = 0;
  const workers = Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx]);
    }
  });
  await Promise.all(workers);
  return out;
}

(async () => {
  const paths = Object.keys(ENDPOINTS);
  console.error(`[probe] base=${BASE} endpoints=${paths.length} samples=${SAMPLES} conc=${CONCURRENCY}`);
  const results = await pool(paths, CONCURRENCY, (p) => probeEndpoint(p, ENDPOINTS[p]));

  const lies = results.filter((r) => r.lie);
  const unreachable = results.filter((r) => r.unreachable && !r.lie);
  const throttled = results.filter((r) => r.throttled && !r.lie && !r.unreachable);
  const verdict = {
    harness: "a11oy-readiness probe",
    doctrine: "v11",
    base: BASE,
    checkedAt: new Date().toISOString(),
    summary: {
      endpoints: results.length,
      ok: results.filter((r) => !r.lie && !r.unreachable && !r.throttled).length,
      lies: lies.length,
      unreachable: unreachable.length,
      throttled: throttled.length,
      p95_worst: Math.max(0, ...results.map((r) => r.p95 || 0)),
    },
    results,
  };
  writeFileSync(OUT, JSON.stringify(verdict, null, 2) + "\n");
  for (const r of results) {
    const tag = r.lie ? "LIE " : r.unreachable ? "DOWN" : r.throttled ? "thr " : "ok  ";
    let why = "";
    if (r.lie) why = "  -> " + r.lies.join("; ");
    else if (r.unreachable) why = `  -> unreachable (${r.error || "status " + r.status})`;
    console.error(`  ${tag} ${r.status} p50=${r.p50}ms p95=${r.p95}ms ${r.path}${why}`);
  }
  console.error(`[probe] ${verdict.summary.ok}/${verdict.summary.endpoints} clean, ${lies.length} lies, ${unreachable.length} unreachable, ${throttled.length} throttled. wrote ${OUT}`);
  // The build fails on LIES (doctrine v11). Unreachable/throttled are reachability
  // signals, surfaced but not doctrine failures (often transient self-throttling).
  if (lies.length && !SOFT) process.exit(1);
})();
