#!/usr/bin/env node
// Throttled API probe runner for the a11oy readiness harness.
//
// Reads tabs.json's endpoint contract registry and, for every endpoint, measures:
//   • HTTP status (vs degradedRules.allowStatuses)
//   • latency p50 / p95 over N polite samples
//   • response schema validity (schemas[] from tabs.json)
//   • citations present when citationsRequired
//   • freshness vs freshnessSLA (a missing or future-skewed clock fails closed)
//
// It then assigns each endpoint a "Lies?" verdict (doctrine v11: stale/mock/uncited
// = a lie = fail) and writes readiness-verdict.json. Exit code is non-zero if any
// lie, required endpoint outage, or required throttling is found, unless explicit report-only mode is
// selected (--report-only; legacy --soft is retained as an alias).
//
// No external deps — Node >= 18 global fetch only.
//   node probe_runner.mjs --base https://a-11-oy.com [--samples 5] [--concurrency 3]
//                         [--report-only] [--out readiness-verdict.json]

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : true;
}

function boundedIntegerArg(name, def, { min, max }) {
  const raw = arg(name, String(def));
  if (raw === true || typeof raw === "boolean") {
    throw new Error(`--${name} requires an integer value`);
  }
  const text = String(raw).trim();
  if (!/^-?\d+$/.test(text)) {
    throw new Error(`--${name} must be an integer between ${min} and ${max}`);
  }
  const value = Number(text);
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new Error(`--${name} must be an integer between ${min} and ${max}`);
  }
  return value;
}

const BASE = String(arg("base", process.env.A11OY_BASE || "https://a-11-oy.com")).replace(/\/$/, "");
const SAMPLES = boundedIntegerArg("samples", 5, { min: 1, max: 20 });
const CONCURRENCY = boundedIntegerArg("concurrency", 2, { min: 1, max: 32 });
const TIMEOUT_MS = boundedIntegerArg("timeout", 15000, { min: 1, max: 120000 });
const REPORT_ONLY = !!arg("report-only", false) || !!arg("soft", false);
const OUT = String(arg("out", join(HERE, "readiness-verdict.json")));
const RETRIES = boundedIntegerArg("retries", 2, { min: 0, max: 10 }); // cold-burst 404s on deep tabs
const SAFE_METHODS = new Set(["GET", "HEAD"]);
const STATE_CHANGE_AUTHORIZED =
  arg("allow-state-changing", false) === true &&
  process.env.A11OY_READINESS_MUTATION_AUTHORIZED === "1";

const matrix = JSON.parse(readFileSync(join(HERE, "tabs.json"), "utf8"));
const ENDPOINTS = matrix.endpoints || {};
const SCHEMAS = matrix.schemas || {};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SHA40 = /^[0-9a-f]{40}$/;

async function fetchBuildRevision() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}/api/build-info`, {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`/api/build-info returned HTTP ${response.status}`);
    }
    const payload = await response.json();
    const revision = payload?.build?.revision || payload?.revision;
    if (typeof revision !== "string" || !SHA40.test(revision)) {
      throw new Error("/api/build-info lacks an exact source revision");
    }
    return revision;
  } finally {
    clearTimeout(timeout);
  }
}

async function observeBuildRevision(fetcher = fetchBuildRevision, soft = REPORT_ONLY) {
  try {
    return { status: "OBSERVED", revision: await fetcher(), error: null };
  } catch (error) {
    if (!soft) throw error;
    const message = error instanceof Error ? error.message : String(error);
    return { status: "UNAVAILABLE", revision: null, error: message };
  }
}

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

const OBSERVATION_TIMESTAMP_KEY =
  /(checked_at|checkedAt|probed_at|probedAt|fetched_at|fetchedAt|generated_at|generatedAt|updated_at|updatedAt|last_updated|observed_at|observedAt)$/i;
const EVENT_TIMESTAMP_KEY = /(timestamp|asOf|as_of|ts)$/i;

function findTimestampsByKey(obj, keyPattern, depth = 0, found = []) {
  if (!obj || depth > 3) return found;
  if (Array.isArray(obj)) {
    for (const v of obj.slice(0, 20)) {
      findTimestampsByKey(v, keyPattern, depth + 1, found);
    }
    return found;
  }
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (keyPattern.test(k)) {
        const d = toDate(v);
        if (d) found.push(d);
      }
    }
    for (const v of Object.values(obj)) {
      findTimestampsByKey(v, keyPattern, depth + 1, found);
    }
  }
  return found;
}

function findTimestamps(obj) {
  // Freshness SLAs grade when the response/source was actually observed. Event
  // timestamps (for example an old but valid policy decision or a closed-market
  // candle) are only a fallback when no observation timestamp exists anywhere.
  const observed = findTimestampsByKey(obj, OBSERVATION_TIMESTAMP_KEY);
  return observed.length ? observed : findTimestampsByKey(obj, EVENT_TIMESTAMP_KEY);
}

function findTimestamp(obj) {
  return findTimestamps(obj)[0] || null;
}

const MAX_FUTURE_SKEW_SEC = 300;

function valueAtPath(obj, path) {
  let cursor = obj;
  for (const key of String(path).split(".")) {
    if (
      cursor === null || typeof cursor !== "object"
      || !Object.prototype.hasOwnProperty.call(cursor, key)
    ) {
      return { found: false, value: undefined };
    }
    cursor = cursor[key];
  }
  return { found: true, value: cursor };
}

// Source wrappers use value=null when an upstream has never produced evidence.
// That state is schema-valid only when it is the exact canonical UNAVAILABLE
// envelope: a measured failure clock plus a non-empty error. It never converts
// absence into an empty result set and it remains subject to the endpoint's
// independent label, citation, freshness, and HTTP-status gates.
function isCanonicalUnavailableSource(source) {
  if (
    source === null
    || typeof source !== "object"
    || Array.isArray(source)
  ) return false;
  const freshness = source.freshness;
  return (
    Object.prototype.hasOwnProperty.call(source, "value")
    && source.value === null
    && freshness !== null
    && typeof freshness === "object"
    && !Array.isArray(freshness)
    && freshness.status === "UNAVAILABLE"
    && toDate(freshness.fetched_at) !== null
    && typeof freshness.error === "string"
    && freshness.error.trim().length > 0
  );
}

function unavailableEnvelopePrefix(path) {
  const text = String(path);
  if (text === "value.items") return "";
  const suffix = ".value.items";
  return text.endsWith(suffix)
    ? text.slice(0, -suffix.length)
    : null;
}

function sourceEnvelopeAt(body, path) {
  const prefix = unavailableEnvelopePrefix(path);
  if (prefix === null) return { found: false, value: undefined };
  return prefix
    ? valueAtPath(body, prefix)
    : { found: true, value: body };
}

function isCanonicalUnavailableItemsEnvelope(body, path) {
  const candidate = sourceEnvelopeAt(body, path);
  return candidate.found && isCanonicalUnavailableSource(candidate.value);
}

function validateUnavailableItemEnvelopes(schema, body) {
  const prefixes = new Set();
  for (const [path, type] of Object.entries(schema?.requiredPathTypes || {})) {
    const prefix = type === "array" ? unavailableEnvelopePrefix(path) : null;
    if (prefix !== null) prefixes.add(prefix);
  }

  for (const prefix of prefixes) {
    const candidate = prefix
      ? valueAtPath(body, prefix)
      : { found: true, value: body };
    if (
      !candidate.found
      || candidate.value === null
      || typeof candidate.value !== "object"
      || Array.isArray(candidate.value)
    ) return false;

    const source = candidate.value;
    const status = source?.freshness?.status;
    if (status === "UNAVAILABLE") {
      if (!isCanonicalUnavailableSource(source)) return false;
    } else if (source.value === null) {
      // A null source without the exact typed UNAVAILABLE envelope is neither
      // observed evidence nor an admissible failure witness.
      return false;
    }
  }
  return true;
}

function requiredFreshnessTimestampPaths(spec) {
  const schema = SCHEMAS[spec?.schema];
  if (!schema || schema.type !== "object" || !schema.requiredPathTypes) return [];
  return Object.entries(schema.requiredPathTypes)
    .filter(([, type]) => type === "timestamp")
    .map(([path]) => path);
}

function collectFreshnessTimestamps(spec, body, isArenaHistory) {
  if (isArenaHistory) {
    const timestamp = toDate(body?.latest_run_at);
    return {
      timestamps: timestamp ? [timestamp] : [],
      missingPaths: timestamp ? [] : ["latest_run_at"],
    };
  }

  // Aggregate schemas declare every response-affecting child clock. Grade those
  // exact clocks so a convenient root timestamp cannot mask a missing sibling.
  const requiredPaths = requiredFreshnessTimestampPaths(spec);
  if (requiredPaths.length) {
    const timestamps = [];
    const missingPaths = [];
    for (const path of requiredPaths) {
      const candidate = valueAtPath(body, path);
      const timestamp = candidate.found ? toDate(candidate.value) : null;
      if (timestamp) timestamps.push(timestamp);
      else missingPaths.push(path);
    }
    return { timestamps, missingPaths };
  }

  return {
    timestamps: findTimestamps(body),
    missingPaths: [],
  };
}

function evaluateFreshness(path, spec, body, nowMs = Date.now()) {
  const sla = Number(spec?.freshnessSLA);
  if (!Number.isFinite(sla) || sla <= 0) {
    return {
      checked: false, freshOk: true, ageSec: null,
      freshnessMissing: false, freshnessReason: null,
      isArenaHistory: false,
    };
  }

  const isArenaHistory = path === "/api/a11oy/v1/eval-arena/history";
  const searchable = body !== null && typeof body === "object";
  // Eval history is a proof-of-run surface: the response observation time is
  // not evidence that a run occurred. Require its explicit latest-run clock.
  const evidence = searchable
    ? collectFreshnessTimestamps(spec, body, isArenaHistory)
    : { timestamps: [], missingPaths: [] };
  const { timestamps, missingPaths } = evidence;
  if (missingPaths.length || timestamps.length === 0) {
    return {
      checked: true, freshOk: false, ageSec: null,
      freshnessMissing: true,
      freshnessReason: missingPaths.length
        ? `freshness timestamp missing: ${missingPaths.join(", ")}`
        : null,
      isArenaHistory,
    };
  }

  const rawAgesSec = timestamps.map(
    (candidate) => (Number(nowMs) - candidate.getTime()) / 1000,
  );
  // The aggregate is only as fresh as its oldest required source. Future skew
  // is independently checked across every source so a fresh sibling cannot
  // conceal either a stale or future-dated one.
  const ageSec = Math.max(0, Math.round(Math.max(...rawAgesSec)));
  const hasFutureSkew = rawAgesSec.some((age) => age < -MAX_FUTURE_SKEW_SEC);
  if (hasFutureSkew) {
    return {
      checked: true, freshOk: false, ageSec,
      freshnessMissing: false,
      freshnessReason: isArenaHistory
        ? "latest eval run timestamp exceeds allowed future clock skew"
        : "freshness timestamp exceeds allowed future clock skew",
      isArenaHistory,
    };
  }

  if (isArenaHistory) {
    const declaredFreshness = String(body?.freshness?.status || "").toLowerCase();
    if (declaredFreshness !== "live") {
      return {
        checked: true, freshOk: false, ageSec,
        freshnessMissing: false,
        freshnessReason: `eval history declares freshness ${declaredFreshness || "unavailable"}`,
        isArenaHistory,
      };
    }
  }

  return {
    checked: true, freshOk: ageSec <= sla, ageSec,
    freshnessMissing: false, freshnessReason: null, isArenaHistory,
  };
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

// Evidence labels are intentionally path-scoped. We inspect explicit data-kind
// fields anywhere and status/state/label fields only at the response root or
// inside a `freshness` object. Domain statuses such as a court-case status, CVE
// status, or incident status are not endpoint-availability evidence.
const KNOWN_EVIDENCE_LABELS = new Set([
  "live", "cached", "stale", "unavailable", "modeled", "measured",
  "snapshot", "sample", "degraded", "reference", "unofficial-fallback",
  "empty", "available", "observed", "unknown", "mock", "fabricated",
  "placeholder",
]);
const EXPLICIT_EVIDENCE_KEY = /^(data_kind|datakind|source_kind|sourcekind|evidence_state|evidencestate)$/i;
const OBSERVATION_EVIDENCE_KEY = /^(throughput_state|counter_state)$/i;
const FRESHNESS_LABEL_KEY = /^(freshness|status|state|label|mode|data_kind|datakind|source_kind|sourcekind)$/i;
const ROOT_LABEL_KEY = /^(status|state|label|mode|freshness)$/i;

function findEvidenceLabels(obj, candidateLabels = []) {
  const candidates = new Set([
    ...KNOWN_EVIDENCE_LABELS,
    ...candidateLabels.map((value) => String(value).trim().toLowerCase()),
  ]);
  const found = [];

  function walk(value, path = "", depth = 0, insideFreshness = false) {
    if (value === null || value === undefined || depth > 5) return;
    if (Array.isArray(value)) {
      value.slice(0, 30).forEach((item, index) => {
        walk(item, `${path}[${index}]`, depth + 1, insideFreshness);
      });
      return;
    }
    if (typeof value !== "object") return;

    for (const [key, child] of Object.entries(value)) {
      const childPath = path ? `${path}.${key}` : key;
      const keyIsFreshness = key.toLowerCase() === "freshness";
      if (typeof child === "string") {
        const normalized = child.trim().toLowerCase();
        const explicit = EXPLICIT_EVIDENCE_KEY.test(key) || OBSERVATION_EVIDENCE_KEY.test(key);
        const nestedFreshnessScoped = insideFreshness
          && FRESHNESS_LABEL_KEY.test(key);
        const scalarFreshness = keyIsFreshness && candidates.has(normalized);
        const rootScoped = depth === 0 && ROOT_LABEL_KEY.test(key)
          && candidates.has(normalized);
        if (explicit || nestedFreshnessScoped || scalarFreshness || rootScoped) {
          found.push({ path: childPath, value: child, normalized });
        }
      }
      walk(child, childPath, depth + 1, insideFreshness || keyIsFreshness);
    }
  }

  walk(obj);
  return found;
}

function findEvidenceContradictions(spec, body) {
  if (
    spec?.schema !== "kevgate"
    || body === null
    || typeof body !== "object"
    || Array.isArray(body)
  ) {
    return [];
  }

  const items = Array.isArray(body.items) ? body.items : [];
  const contradictions = [];
  items.slice(0, 30).forEach((item, index) => {
    if (item === null || typeof item !== "object" || Array.isArray(item)) return;
    const dataKind = String(item.data_kind || "").trim().toLowerCase();
    if (dataKind !== "live" && dataKind !== "cached") return;
    const cvssSource = String(item.cvss_src || "").trim().toLowerCase();
    const cacheState = String(item.cvss_cache_state || "").trim().toLowerCase();
    if (cvssSource !== "nvd" || cacheState !== "fresh") {
      contradictions.push({
        path: `items[${index}].cvss_evidence`,
        value: `${cvssSource || "missing"}/${cacheState || "missing"}`,
        normalized: "inconsistent",
      });
    }
  });
  return contradictions;
}

function evaluateEndpointLabels(httpStatus, spec, body) {
  const allowStatuses = (spec.degradedRules?.allowStatuses) || [200];
  if (!allowStatuses.includes(httpStatus)) {
    return { checked: false, ok: true, labels: [], disallowed: [], lie: null };
  }
  const allowLabels = (spec.degradedRules?.allowLabels) || ["live", "cached"];
  const liesIf = (spec.degradedRules?.liesIf) || [];
  const allowed = new Set(allowLabels.map((value) => String(value).trim().toLowerCase()));
  const lieSet = new Set(liesIf.map((value) => String(value).trim().toLowerCase()));
  const labels = findEvidenceLabels(body, [...allowLabels, ...liesIf]);
  // OBSERVED is a valid supplemental counter label, but never a substitute for
  // the root LIVE/CACHED availability label. Inspecting these fields makes a
  // MODELED or unknown counter fail without broadening allowLabels.
  const supplementalObserved = (entry) => (
    entry.normalized === "observed"
    && /(^|\.)(throughput_state|counter_state)$/i.test(entry.path)
  );
  const disallowed = [
    ...labels.filter(
      (entry) => !allowed.has(entry.normalized) && !supplementalObserved(entry),
    ),
    ...findEvidenceContradictions(spec, body),
  ];
  const lie = labels.find((entry) => lieSet.has(entry.normalized)) || null;
  return {
    checked: true,
    ok: disallowed.length === 0 && lie === null,
    labels,
    disallowed,
    lie,
  };
}

const STRICT_UTC_TIMESTAMP =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;

function parseStrictUtcTimestamp(value) {
  if (typeof value !== "string") return null;
  const match = STRICT_UTC_TIMESTAMP.exec(value);
  if (!match) return null;
  const [, year, month, day, hour, minute, second, fraction = ""] = match;
  const milliseconds = Number((fraction + "000").slice(0, 3));
  const date = new Date(Date.UTC(
    Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute),
    Number(second), milliseconds,
  ));
  if (
    Number.isNaN(date.getTime())
    || date.getUTCFullYear() !== Number(year)
    || date.getUTCMonth() !== Number(month) - 1
    || date.getUTCDate() !== Number(day)
    || date.getUTCHours() !== Number(hour)
    || date.getUTCMinutes() !== Number(minute)
    || date.getUTCSeconds() !== Number(second)
  ) return null;
  return date;
}

function validateRouterStatsSemantic(body, contract, nowMs = Date.now()) {
  const fail = (why) => ({ ok: false, why });
  if (contract?.kind !== "router_stats_v1") {
    return fail("router semantic contract is missing or unknown");
  }
  const expected = contract.catalog;
  if (!Array.isArray(expected) || expected.length === 0) {
    return fail("protected router catalog is empty");
  }
  if (!Array.isArray(body?.routes) || body.routes.length !== expected.length) {
    return fail("runtime routes do not exactly cover the protected catalog");
  }
  if (body.honesty !== contract.honesty) {
    return fail("router honesty statement is not bound to the protected contract");
  }

  const organForTier = new Map([
    [0, "Reasoning"], [1, "Reasoning"], [2, "a11oy"], [3, "Operator"],
    [4, "Policy / Safety"], [5, "Knowledge"], [6, "a11oy"],
  ]);
  let routeTotal = 0;
  for (let index = 0; index < expected.length; index += 1) {
    const identity = expected[index];
    const route = body.routes[index];
    if (
      route === null || typeof route !== "object" || Array.isArray(route)
      || route.tier !== identity.tier || route.model !== identity.model
    ) return fail(`route ${index} does not match protected catalog identity`);
    const tierMatch = /^T(\d+)$/.exec(route.tier);
    if (!tierMatch) return fail(`route ${index} has an invalid tier identity`);
    const tier = Number(tierMatch[1]);
    const expectedOrgan = organForTier.get(tier) ?? "a11oy";
    const expectedLicense = tier >= 2 ? "AMBER" : "GREEN";
    if (
      route.catalog_member !== true
      || route.organ !== expectedOrgan
      || route.license !== expectedLicense
      || route.throughput_unit !== "routing_decisions_since_process_start"
      || !Number.isSafeInteger(route.throughput) || route.throughput < 0
      || !Number.isSafeInteger(route.routing_decisions)
      || route.routing_decisions < 0
      || route.routing_decisions !== route.throughput
    ) return fail(`route ${index} violates router counter semantics`);
    routeTotal += route.routing_decisions;
    if (!Number.isSafeInteger(routeTotal)) {
      return fail("router counter total exceeds the safe integer range");
    }
  }

  if (
    body.servedThisWindow !== routeTotal
    || body.routingDecisionsSinceStart !== routeTotal
  ) return fail("root router total does not equal the route sum");
  const expectedTiers = [...new Set(expected.map((route) => route.tier))].sort();
  if (
    !Array.isArray(body.tiers)
    || body.tiers.length !== expectedTiers.length
    || body.tiers.some((tier, index) => tier !== expectedTiers[index])
  ) return fail("root tier identity does not match the protected catalog");

  const startedAt = parseStrictUtcTimestamp(body.counter_started_at);
  const observedAt = parseStrictUtcTimestamp(body.observed_at);
  if (!startedAt || !observedAt) {
    return fail("router timestamps must be valid canonical UTC timestamps");
  }
  if (startedAt.getTime() > observedAt.getTime()) {
    return fail("counter_started_at is later than observed_at");
  }
  const maxFutureSkewSeconds = Number(contract.maxFutureSkewSeconds);
  const maxObservationAgeSeconds = Number(contract.observationMaxAgeSeconds);
  if (
    !Number.isFinite(maxFutureSkewSeconds) || maxFutureSkewSeconds < 0
    || !Number.isFinite(maxObservationAgeSeconds) || maxObservationAgeSeconds <= 0
  ) return fail("router observation bounds are invalid");
  const observationAgeSeconds = (Number(nowMs) - observedAt.getTime()) / 1000;
  if (observationAgeSeconds < -maxFutureSkewSeconds) {
    return fail("router observation exceeds the allowed future clock skew");
  }
  if (observationAgeSeconds > maxObservationAgeSeconds) {
    return fail("router observation is stale");
  }
  return { ok: true, why: "router_stats_v1" };
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
      if (sc.properties && !Object.entries(sc.properties).every(([key, rule]) =>
        !Object.prototype.hasOwnProperty.call(rule, "const") || body[key] === rule.const
      )) return false;
      if (sc.requiredPaths && !sc.requiredPaths.every((path) => {
        const candidate = valueAtPath(body, path);
        return candidate.found || isCanonicalUnavailableItemsEnvelope(body, path);
      })) return false;
      if (sc.requiredPathTypes && !Object.entries(sc.requiredPathTypes).every(([path, type]) => {
        const candidate = valueAtPath(body, path);
        if (!candidate.found) {
          return type === "array"
            && isCanonicalUnavailableItemsEnvelope(body, path);
        }
        const cursor = candidate.value;
        if (type === "array") return Array.isArray(cursor);
        if (type === "nonempty_array") return Array.isArray(cursor) && cursor.length > 0;
        if (type === "object") {
          return typeof cursor === "object" && cursor !== null && !Array.isArray(cursor);
        }
        if (type === "string") return typeof cursor === "string";
        if (type === "number") return typeof cursor === "number" && Number.isFinite(cursor);
        if (type === "nonnegative_integer") {
          return Number.isSafeInteger(cursor) && cursor >= 0;
        }
        if (type === "boolean") return typeof cursor === "boolean";
        if (type === "timestamp") return toDate(cursor) !== null;
        if (type === "process_epoch_timestamp") {
          return parseStrictUtcTimestamp(cursor) !== null;
        }
        return false;
      })) return false;
      if (!validateUnavailableItemEnvelopes(sc, body)) return false;
      if (sc.anyKey && !sc.anyKey.some((k) => k in body)) return false;
      return true;
    }
    return true;
  };
  if (s.anyOf) {
    return { ok: s.anyOf.some(checkOne), why: "anyOf" };
  }
  if (!checkOne(s)) return { ok: false, why: s.type };
  if (s.semanticContract?.kind === "router_stats_v1") {
    return validateRouterStatsSemantic(body, s.semanticContract);
  }
  return { ok: true, why: s.type };
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
  const method = String(spec.method || "GET").toUpperCase();
  const allow = (spec.degradedRules?.allowStatuses) || [200];
  if (!SAFE_METHODS.has(method) && !STATE_CHANGE_AUTHORIZED) {
    return {
      path, method, status: null, error: null, skipped: true,
      required: spec.required !== false,
      skipReason: "state-changing contract skipped; require --allow-state-changing and A11OY_READINESS_MUTATION_AUTHORIZED=1",
      throttled: false, unreachable: false, p50: null, p95: null, samples: 0,
      schemaOk: null, citationOk: null, labelPolicyOk: null,
      evidenceLabels: [], freshOk: null, ageSec: null,
      citationsRequired: !!spec.citationsRequired,
      freshnessSLA: spec.freshnessSLA ?? null,
      lie: false, lies: [],
    };
  }
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
  const labelPolicy = inconclusive
    ? { checked: false, ok: true, labels: [], disallowed: [], lie: null }
    : evaluateEndpointLabels(last.status, spec, last.body);

  let citationOk = true;
  if (spec.citationsRequired && statusOk) {
    citationOk = typeof last.body === "string" ? last.body.length > 0 : hasCitation(last.body);
  }

  const freshness = statusOk
    ? evaluateFreshness(path, spec, last.body)
    : {
        freshOk: true, ageSec: null, freshnessMissing: false,
        freshnessReason: null, isArenaHistory: false,
      };
  const {
    freshOk, ageSec, freshnessMissing, freshnessReason, isArenaHistory,
  } = freshness;

  const lies = [];
  // A bad status is only a doctrine lie if the endpoint actually answered with
  // an unexpected HTTP status (e.g. a 404 on a tab the console links). Timeouts,
  // network drops and 5xx are reachability failures, reported as `unreachable`.
  if (!inconclusive && !statusOk) lies.push(`status ${last.status} not in [${allow}]`);
  if (statusOk && !schema.ok) lies.push(`schema invalid (${spec.schema})`);
  if (!citationOk) lies.push("citationsRequired but none found");
  if (freshnessMissing) {
    if (isArenaHistory) lies.push("latest eval run timestamp missing");
    else lies.push(freshnessReason || "freshness timestamp missing");
  }
  else if (freshnessReason) lies.push(freshnessReason);
  else if (!freshOk) lies.push(`stale ${ageSec}s > SLA ${spec.freshnessSLA}s`);
  if (labelPolicy.lie) {
    lies.push(`mock/placeholder label: ${labelPolicy.lie.path}="${labelPolicy.lie.value}"`);
  }
  const disallowedLabels = labelPolicy.disallowed.filter(
    (entry) => entry !== labelPolicy.lie,
  );
  if (disallowedLabels.length) {
    lies.push("evidence label not allowed: " + disallowedLabels.slice(0, 5)
      .map((entry) => `${entry.path}="${entry.value}"`).join(", "));
  }

  return {
    path, method, status: last.status, error: last.error || null,
    required: spec.required !== false,
    throttled, unreachable,
    p50: Math.round(percentile(lat, 50)), p95: Math.round(percentile(lat, 95)),
    samples: lat.length, schemaOk: schema.ok, citationOk,
    labelPolicyOk: labelPolicy.ok,
    evidenceLabels: labelPolicy.labels.map((entry) => ({
      path: entry.path, value: entry.value,
    })),
    freshOk, ageSec,
    citationsRequired: !!spec.citationsRequired, freshnessSLA: spec.freshnessSLA ?? null,
    lie: lies.length > 0, lies,
  };
}

function allowOk(spec, status) {
  return ((spec.degradedRules?.allowStatuses) || [200]).includes(status);
}

async function pool(items, n, fn) {
  if (!Number.isSafeInteger(n) || n < 1) {
    throw new Error("probe pool concurrency must be a positive integer");
  }
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

function summarizeReleaseGate(results, expectedCount) {
  const complete = Number.isSafeInteger(expectedCount) && expectedCount > 0
    && Array.isArray(results) && results.length === expectedCount;
  const lies = Array.isArray(results) ? results.filter((r) => r?.lie).length : 0;
  const requiredUnreachable = Array.isArray(results)
    ? results.filter((r) => !r?.skipped && r?.required !== false && r?.unreachable).length
    : 0;
  const requiredThrottled = Array.isArray(results)
    ? results.filter((r) => !r?.skipped && r?.required !== false && r?.throttled).length
    : 0;
  return {
    complete,
    lies,
    requiredUnreachable,
    requiredThrottled,
    blocked: !complete || lies > 0 || requiredUnreachable > 0 || requiredThrottled > 0,
  };
}

function releaseExitCode(releaseGate, reportOnly = false) {
  return releaseGate?.blocked && !reportOnly ? 1 : 0;
}

async function main() {
  const paths = Object.keys(ENDPOINTS);
  if (paths.length === 0) {
    throw new Error("readiness matrix contains zero endpoint contracts");
  }
  console.error(`[probe] base=${BASE} endpoints=${paths.length} samples=${SAMPLES} conc=${CONCURRENCY}`);
  const sourceBefore = await observeBuildRevision();
  const results = await pool(paths, CONCURRENCY, (p) => probeEndpoint(p, ENDPOINTS[p]));
  const releaseGate = summarizeReleaseGate(results, paths.length);
  if (!releaseGate.complete) {
    throw new Error(`probe completed ${results.length}/${paths.length} endpoint contracts`);
  }
  const sourceAfter = await observeBuildRevision();
  let sourceRevisionStatus =
    sourceBefore.status === "OBSERVED" && sourceAfter.status === "OBSERVED"
      ? "OBSERVED"
      : "UNAVAILABLE";
  let sourceRevisionError = sourceBefore.error || sourceAfter.error || null;
  if (
    sourceRevisionStatus === "OBSERVED" &&
    sourceBefore.revision !== sourceAfter.revision
  ) {
    const message = `deployment revision changed during probe: ${sourceBefore.revision} -> ${sourceAfter.revision}`;
    if (!REPORT_ONLY) throw new Error(message);
    sourceRevisionStatus = "DIVERGENT";
    sourceRevisionError = message;
  }
  const sourceRevision =
    sourceRevisionStatus === "OBSERVED" ? sourceAfter.revision : null;

  const lies = results.filter((r) => r.lie);
  const unreachable = results.filter((r) => r.unreachable && !r.lie);
  const throttled = results.filter((r) => r.throttled && !r.lie && !r.unreachable);
  const verdict = {
    schema: "szl.readiness-verdict/v1",
    harness: "a11oy-readiness probe",
    doctrine: "v11",
    base: BASE,
    checkedAt: new Date().toISOString(),
    sourceRevision,
    sourceRevisionStatus,
    sourceRevisionError,
    sourceRevisionBefore: sourceBefore.revision,
    sourceRevisionBeforeStatus: sourceBefore.status,
    sourceRevisionAfter: sourceAfter.revision,
    sourceRevisionAfterStatus: sourceAfter.status,
    summary: {
      endpoints: results.length,
      ok: results.filter((r) => !r.skipped && !r.lie && !r.unreachable && !r.throttled).length,
      skippedStateChanging: results.filter((r) => r.skipped).length,
      lies: lies.length,
      unreachable: unreachable.length,
      throttled: throttled.length,
      p95_worst: Math.max(0, ...results.map((r) => r.p95 || 0)),
    },
    results,
  };
  writeFileSync(OUT, JSON.stringify(verdict, null, 2) + "\n");
  for (const r of results) {
    const tag = r.skipped ? "skip" : r.lie ? "LIE " : r.unreachable ? "DOWN" : r.throttled ? "thr " : "ok  ";
    let why = "";
    if (r.skipped) why = "  -> " + r.skipReason;
    else if (r.lie) why = "  -> " + r.lies.join("; ");
    else if (r.unreachable) why = `  -> unreachable (${r.error || "status " + r.status})`;
    console.error(`  ${tag} ${r.status ?? "-"} p50=${r.p50 ?? "-"}ms p95=${r.p95 ?? "-"}ms ${r.path}${why}`);
  }
  console.error(`[probe] ${verdict.summary.ok}/${verdict.summary.endpoints} clean, ${verdict.summary.skippedStateChanging} state-changing skipped, ${lies.length} lies, ${unreachable.length} unreachable, ${throttled.length} throttled. wrote ${OUT}`);
  // Release mode fails on doctrine lies, required endpoint outages, and required
  // throttling: HTTP 429 is honest evidence of an inconclusive probe, not a pass.
  // --report-only (and its legacy --soft alias) exists only to preserve the full
  // evidence artifact for a later fail-closed publisher; it never makes the
  // verdict publishable.
  const exitCode = releaseExitCode(releaseGate, REPORT_ONLY);
  if (exitCode) process.exitCode = exitCode;
}

if (fileURLToPath(import.meta.url) === resolve(process.argv[1] || "")) {
  main();
}

export {
  boundedIntegerArg,
  evaluateEndpointLabels,
  evaluateFreshness,
  findEvidenceLabels,
  findTimestamp,
  observeBuildRevision,
  pool,
  releaseExitCode,
  summarizeReleaseGate,
  validateRouterStatsSemantic,
  validateSchema,
};
