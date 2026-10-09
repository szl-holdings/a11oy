// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  awaitReadiness,
  evaluateEndpointLabels,
  evaluateFreshness,
  findEvidenceLabels,
  findTimestamp,
  probeEndpoint,
  releaseExitCode,
  retainAwaitFailure,
  summarizeReleaseGate,
  validateRouterStatsSemantic,
  validateSchema,
  withSourceRevisionBracket,
} from "./probe_runner.mjs";

const readinessMatrix = JSON.parse(readFileSync(
  new URL("./tabs.json", import.meta.url),
  "utf8",
));
const routerSemanticContract =
  readinessMatrix.schemas.router_stats.semanticContract;

function liveRouterStats(nowMs = Date.now()) {
  const organForTier = new Map([
    [0, "Reasoning"], [1, "Reasoning"], [2, "a11oy"], [3, "Operator"],
    [4, "Policy / Safety"], [5, "Knowledge"], [6, "a11oy"],
  ]);
  const routes = routerSemanticContract.catalog.map((identity, index) => {
    const tier = Number(identity.tier.slice(1));
    const decisions = index === 2 ? 3 : 0;
    return {
      organ: organForTier.get(tier) ?? "a11oy",
      tier: identity.tier,
      model: identity.model,
      throughput: decisions,
      routing_decisions: decisions,
      throughput_unit: "routing_decisions_since_process_start",
      license: tier >= 2 ? "AMBER" : "GREEN",
      catalog_member: true,
    };
  });
  return {
    state: "LIVE",
    mode: "live",
    data_kind: "live",
    catalog_state: "LIVE",
    throughput_state: "OBSERVED",
    counter_state: "OBSERVED",
    routes,
    servedThisWindow: 3,
    routingDecisionsSinceStart: 3,
    tiers: [...new Set(routes.map((route) => route.tier))].sort(),
    counter_scope: "process_lifetime",
    counter_started_at: "2026-01-01T00:00:00Z",
    observed_at: new Date(nowMs - 1_000).toISOString(),
    source: "szl_llm_registry.router_stats_snapshot",
    catalog_source: "szl_llm_registry.MODEL_REGISTRY",
    doctrine: "v11",
    honesty: routerSemanticContract.honesty,
  };
}

test("freshness prefers response observation time over an idle policy event", () => {
  const body = {
    verdicts: [{ timestamp: "2026-06-05T23:32:40Z", decision: "deny" }],
    fetchedAt: "2026-07-26T01:05:07Z",
  };

  assert.equal(findTimestamp(body)?.toISOString(), "2026-07-26T01:05:07.000Z");
});

test("freshness recognizes explicit snake- and camel-case observation clocks", () => {
  for (const key of ["observed_at", "observedAt"]) {
    const body = {
      timestamp: "2026-06-05T23:32:40Z",
      [key]: "2026-07-26T01:05:07Z",
    };

    assert.equal(findTimestamp(body)?.toISOString(), "2026-07-26T01:05:07.000Z");
    assert.equal(evaluateFreshness(
      "/api/a11oy/provenance",
      { freshnessSLA: 60 },
      body,
      Date.parse("2026-07-26T01:06:00Z"),
    ).freshOk, true);
  }
});

test("freshness ignores counters whose names merely end in ts", () => {
  const observedAt = "2026-10-09T01:08:18.985Z";
  const body = {
    historical_billable_receipts: 0,
    historical_reported_charged_cents: 0,
    ts: observedAt,
  };

  assert.equal(findTimestamp(body)?.toISOString(), observedAt);
  assert.equal(evaluateFreshness(
    "/api/a11oy/v1/energy/harvest",
    { freshnessSLA: 3600 },
    body,
    Date.parse("2026-10-09T01:09:00Z"),
  ).freshOk, true);
});

test("freshness prefers nested source fetch time over a market event timestamp", () => {
  const body = {
    equities: {
      SPY: {
        value: { ts: 1784923200 },
        freshness: { fetched_at: 1785027907.8332539 },
      },
    },
  };

  assert.equal(findTimestamp(body)?.getTime(), 1785027907833);
});

const SOURCE_A = "a".repeat(40);
const SOURCE_B = "b".repeat(40);

function readinessSnapshot(
  fetchedAt,
  { source = SOURCE_A, applicationReady = true, stale = false } = {},
) {
  return {
    sections: [],
    summary: { application_ready: applicationReady },
    checked_at: fetchedAt,
    snapshot_fetched_at: fetchedAt,
    snapshot_source_revision: source,
    stale,
  };
}

test("readiness retains the canonical 300-second freshness boundary", () => {
  const path = "/api/a11oy/v1/readiness";
  const spec = readinessMatrix.endpoints[path];
  const result = evaluateFreshness(
    path,
    spec,
    readinessSnapshot("2026-10-07T16:42:44Z"),
    Date.parse("2026-10-07T16:50:50Z"),
  );

  assert.equal(spec.freshnessSLA, 300);
  assert.equal(result.ageSec, 486);
  assert.equal(result.freshOk, false);
});

test("passive readiness waiting never calls refresh and requires the witnessed source", async () => {
  const path = "/api/a11oy/v1/readiness";
  const calls = [];
  let reads = 0;
  let now = Date.parse("2026-10-07T16:50:50Z");
  const awaited = await awaitReadiness({
    request: async (requestedPath) => {
      calls.push(requestedPath);
      reads += 1;
      const fetchedAt = reads === 1
        ? "2026-10-07T16:42:44Z"
        : "2026-10-07T16:50:50Z";
      return { status: 200, body: readinessSnapshot(fetchedAt) };
    },
    clock: () => now,
    sleepFn: async (ms) => { now += ms; },
    timeoutMs: 5000,
    pollMs: 1000,
    expectedSourceRevision: SOURCE_A,
  });

  assert.equal(awaited.snapshotSourceRevision, SOURCE_A);
  assert.deepEqual(calls, [path, path]);
  assert.equal(calls.some((requestedPath) => requestedPath.endsWith("/refresh")), false);
});

test("waiting and the final probe reject foreign, unready, or stale snapshots", async () => {
  const path = "/api/a11oy/v1/readiness";
  const spec = readinessMatrix.endpoints[path];
  const cases = [
    [readinessSnapshot("2026-10-07T16:50:50Z", { source: SOURCE_B }), /source revision/],
    [readinessSnapshot("2026-10-07T16:50:50Z", { applicationReady: false }), /not ready/],
    [readinessSnapshot("2026-10-07T16:50:50Z", { stale: true }), /stale=false/],
  ];

  for (const [body, expected] of cases) {
    let now = Date.parse("2026-10-07T16:50:50Z");
    await assert.rejects(
      awaitReadiness({
        request: async () => ({ status: 200, body }),
        clock: () => now,
        sleepFn: async (ms) => { now += ms; },
        timeoutMs: 1000,
        pollMs: 1000,
        expectedSourceRevision: SOURCE_A,
      }),
      expected,
    );
    const result = await probeEndpoint(path, spec, {
      expectedSourceRevision: SOURCE_A,
      request: async () => ({ status: 200, ms: 1, body, ct: "application/json" }),
      sleepFn: async () => {},
    });
    assert.equal(result.lie, true);
    assert.match(result.lies.join("; "), expected);
    assert.equal(summarizeReleaseGate([result], 1).blocked, true);
  }
});

test("source observations bracket waiting and the full probe across an A-to-B transition", async () => {
  const events = [];
  const revisions = [SOURCE_A, SOURCE_B];
  const bracket = await withSourceRevisionBracket(async (sourceBefore) => {
    events.push(`wait:${sourceBefore.revision}`);
    await awaitReadiness({
      request: async (path) => {
        events.push(`readiness:${path}`);
        return {
          status: 200,
          body: readinessSnapshot("2026-10-07T16:50:50Z"),
        };
      },
      clock: () => Date.parse("2026-10-07T16:50:50Z"),
      expectedSourceRevision: sourceBefore.revision,
    });
    events.push("full-probe");
    return "complete";
  }, {
    observeSource: async () => {
      const revision = revisions.shift();
      events.push(`source:${revision}`);
      return { status: "OBSERVED", revision, error: null };
    },
    soft: true,
  });

  assert.deepEqual(events, [
    `source:${SOURCE_A}`,
    `wait:${SOURCE_A}`,
    "readiness:/api/a11oy/v1/readiness",
    "full-probe",
    `source:${SOURCE_B}`,
  ]);
  assert.equal(bracket.sourceRevisionStatus, "DIVERGENT");
  assert.equal(bracket.sourceRevision, null);
});

test("a report-only readiness wait failure remains a blocking result", () => {
  const results = [{
    path: "/api/a11oy/v1/readiness",
    lie: false,
    lies: [],
    freshOk: true,
    runtimeState: "RUNNING",
  }];

  retainAwaitFailure(results, new Error("readiness wait did not converge"));

  assert.equal(results[0].lie, true);
  assert.equal(results[0].freshOk, false);
  assert.equal(results[0].runtimeState, "ERROR");
  assert.equal(summarizeReleaseGate(results, 1).blocked, true);
});

test("an unavailable source witness blocks as unreachable without becoming a lie", async () => {
  const path = "/api/a11oy/v1/readiness";
  const body = readinessSnapshot(new Date().toISOString());
  const result = await probeEndpoint(path, readinessMatrix.endpoints[path], {
    expectedSourceRevision: null,
    request: async () => ({ status: 200, ms: 1, body, ct: "application/json" }),
    sleepFn: async () => {},
  });
  const error = new Error("cannot await readiness without an observed deployment revision");
  error.awaitFailureClass = "unreachable";
  retainAwaitFailure([result], error);
  const gate = summarizeReleaseGate([result], 1);

  assert.equal(result.sourceRevisionOk, null);
  assert.equal(result.lie, false);
  assert.equal(result.unreachable, true);
  assert.equal(gate.lies, 0);
  assert.equal(gate.requiredUnreachable, 1);
  assert.equal(gate.blocked, true);
});

test("ownership readiness requires all four REIT source clocks", () => {
  const path = "/api/a11oy/v1/deva/re/ownership";
  const spec = readinessMatrix.endpoints[path];
  const observedAt = "2026-10-07T19:00:00Z";
  const observed = {
    value: { filings: [] },
    freshness: { status: "live", fetched_at: observedAt },
  };
  const body = {
    tab: "ownership",
    sec_fts: {
      value: { items: [] },
      freshness: { status: "live", fetched_at: observedAt },
    },
    reits: Object.fromEntries(
      ["Vornado", "Boston Properties", "SL Green", "Realty Income"]
        .map((name) => [name, structuredClone(observed)]),
    ),
    doctrine: {},
  };
  const nowMs = Date.parse("2026-10-07T19:00:30Z");
  assert.equal(spec.unavailableBlocksReadiness, true);
  assert.equal(validateSchema(spec.schema, body).ok, true);
  assert.equal(evaluateFreshness(path, spec, body, nowMs).freshOk, true);

  delete body.reits.Vornado.freshness.fetched_at;
  assert.equal(validateSchema(spec.schema, body).ok, false);
  body.reits.Vornado = structuredClone(observed);

  body.reits["SL Green"] = {
    value: null,
    freshness: {
      status: "UNAVAILABLE",
      fetched_at: observedAt,
      error: "ReadTimeout: SEC source did not answer",
    },
  };
  assert.equal(validateSchema(spec.schema, body).ok, false);
  assert.equal(evaluateEndpointLabels(200, spec, body).ok, true);
  const freshness = evaluateFreshness(path, spec, body, nowMs);
  assert.equal(freshness.freshOk, false);
  assert.match(freshness.freshnessReason, /required source unavailable: reits\.SL Green/);
});

test("tab-matrix schema validates available and truthful unavailable wrappers", () => {
  assert.equal(validateSchema("tab_matrix", {
    matrix_available: true,
    probe_verdict_available: false,
    matrix: { tabs: [], endpoints: {} },
  }).ok, true);

  assert.equal(validateSchema("tab_matrix", {
    matrix_available: false,
    probe_verdict_available: false,
    note: "tabs.json not bundled with this deploy",
  }).ok, true);

  assert.equal(validateSchema("tab_matrix", {
    matrix_available: true,
    probe_verdict_available: false,
    matrix: { tabs: [] },
  }).ok, false);

  assert.equal(validateSchema("tab_matrix", {
    matrix_available: true,
    probe_verdict_available: false,
    matrix: { tabs: null, endpoints: {} },
  }).ok, false);

  assert.equal(validateSchema("tab_matrix", {
    matrix_available: true,
    probe_verdict_available: false,
    matrix: { tabs: [], endpoints: "broken" },
  }).ok, false);

  assert.equal(validateSchema("tab_matrix", {
    matrix_available: false,
    probe_verdict_available: false,
  }).ok, false);
});

test("router-stats schema requires truthful live process-lifetime counters", () => {
  const observed = liveRouterStats();
  assert.equal(validateSchema("router_stats", observed).ok, true);
  assert.equal(validateSchema("router_stats", { ...observed, state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, data_kind: "modeled" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, throughput_state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, counter_scope: "window" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, source: "szl_brain.TIERS" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routes: [] }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: 0.5 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: 2 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routingDecisionsSinceStart: -1 }).ok, false);
});

test("router counter evidence is inspected without weakening root labels", () => {
  const spec = {
    degradedRules: {
      allowStatuses: [200],
      allowLabels: ["live", "cached"],
      liesIf: ["mock", "fabricated", "placeholder"],
    },
  };
  assert.equal(evaluateEndpointLabels(200, spec, {
    state: "LIVE",
    mode: "live",
    data_kind: "live",
    throughput_state: "OBSERVED",
  }).ok, true);
  assert.equal(evaluateEndpointLabels(200, spec, {
    state: "LIVE",
    mode: "live",
    data_kind: "live",
    throughput_state: "MODELED",
  }).ok, false);
  assert.equal(evaluateEndpointLabels(200, spec, {
    state: "OBSERVED",
    throughput_state: "OBSERVED",
  }).ok, false);
});

test("schema freshness metadata is not treated as runtime evidence", () => {
  const labels = findEvidenceLabels({
    requiredPathTypes: {
      freshness: "object",
      checked_at: "timestamp",
    },
  });
  assert.deepEqual(labels, []);
});

test("scalar freshness captures canonical negative evidence labels only", () => {
  for (const value of ["modeled", "degraded", "sample", "unknown"]) {
    assert.deepEqual(findEvidenceLabels({ freshness: value }), [{
      path: "freshness",
      value,
      normalized: value,
    }]);
  }
  for (const metadataType of ["object", "string", "OBJECT", "STRING"]) {
    assert.deepEqual(findEvidenceLabels({ freshness: metadataType }), []);
  }
});

test("real freshness objects retain unknown and negative statuses", () => {
  const labels = findEvidenceLabels({
    freshness: {
      status: "vendor-pending",
      mode: "modeled",
      state: "degraded",
      label: "sample",
    },
  });
  assert.deepEqual(labels.map(({ path, normalized }) => ({ path, normalized })), [
    { path: "freshness.status", normalized: "vendor-pending" },
    { path: "freshness.mode", normalized: "modeled" },
    { path: "freshness.state", normalized: "degraded" },
    { path: "freshness.label", normalized: "sample" },
  ]);
});

test("explicit evidence-kind fields remain fail-closed for unknown values", () => {
  assert.deepEqual(findEvidenceLabels({ payload: { data_kind: "vendor-pending" } }), [{
    path: "payload.data_kind",
    value: "vendor-pending",
    normalized: "vendor-pending",
  }]);
});

test("feed pulse freshness grades its current heartbeat clock", () => {
  const spec = readinessMatrix.endpoints["/api/a11oy/v1/feeds/pulse"];
  const nowMs = Date.parse("2026-09-01T05:30:00Z");
  const body = {
    probed_at: "2026-09-01T05:29:50Z",
    items: [{
      feed: "celestrak",
      mode: "cached",
      fetched_at: "2026-08-31T00:00:00Z",
      source_url: "https://celestrak.org/",
    }],
  };

  const currentHeartbeat = evaluateFreshness(
    "/api/a11oy/v1/feeds/pulse",
    spec,
    body,
    nowMs,
  );
  assert.equal(currentHeartbeat.freshOk, true);
  assert.equal(currentHeartbeat.ageSec, 10);

  const missingHeartbeat = evaluateFreshness(
    "/api/a11oy/v1/feeds/pulse",
    spec,
    { items: body.items },
    nowMs,
  );
  assert.equal(missingHeartbeat.freshOk, false);
  assert.equal(missingHeartbeat.freshnessMissing, true);
  assert.match(missingHeartbeat.freshnessReason, /probed_at/);
});

test("canonical unavailable freshness.status is not a doctrine lie", () => {
  const spec = {
    degradedRules: {
      allowStatuses: [200],
      allowLabels: ["live", "cached"],
      liesIf: ["mock", "fabricated", "placeholder"],
    },
  };
  const fetchedAt = "2026-09-19T23:37:19Z";
  const canonical = {
    hpd: {
      value: null,
      freshness: {
        status: "UNAVAILABLE",
        fetched_at: fetchedAt,
        error: "HTTPStatusError 503",
      },
    },
    rates: {
      value: [{ pair: "EURUSD" }],
      freshness: {
        status: "live",
        fetched_at: fetchedAt,
        error: "",
      },
    },
  };
  assert.equal(evaluateEndpointLabels(200, spec, canonical).ok, true);

  const missingError = {
    hpd: {
      value: null,
      freshness: {
        status: "UNAVAILABLE",
        fetched_at: fetchedAt,
      },
    },
  };
  assert.equal(evaluateEndpointLabels(200, spec, missingError).ok, false);

  const valueNotNull = {
    hpd: {
      value: [],
      freshness: {
        status: "UNAVAILABLE",
        fetched_at: fetchedAt,
        error: "HTTPStatusError 503",
      },
    },
  };
  assert.equal(evaluateEndpointLabels(200, spec, valueNotNull).ok, false);

  const rootUnavailable = {
    freshness: {
      status: "UNAVAILABLE",
    },
  };
  assert.equal(evaluateEndpointLabels(200, spec, rootUnavailable).ok, false);
});

const unavailableContracts = [
  ["/api/a11oy/v1/vert/realestate/feed", "hpd_litigations", {
    vertical: "realestate", sources_cited: [{ url: "https://data.cityofnewyork.us/" }],
    doctrine: {},
  }, ["dob_violations", "rates"]],
  ["/api/a11oy/v1/deva/re/pulse", "hpd", { tab: "pulse", doctrine: {} }, ["dob", "rates"]],
  ["/api/a11oy/v1/deva/re/distress?limit=1", "hpd", { tab: "distress", doctrine: {} }, []],
];

function sourceResponse(sourcePath, base, siblings, fetchedAt) {
  const body = structuredClone(base);
  body[sourcePath] = {
    value: null,
    freshness: {
      status: "UNAVAILABLE", fetched_at: fetchedAt, error: "bounded upstream timeout",
    },
  };
  for (const name of siblings) {
    body[name] = {
      value: { items: [{ id: "observed-fixture" }] },
      freshness: { status: "live", fetched_at: fetchedAt },
    };
  }
  return body;
}

test("required canonical source absence is honest DEGRADED and blocks release", () => {
  for (const [path, sourcePath, base, siblings] of unavailableContracts) {
    const spec = readinessMatrix.endpoints[path];
    const body = sourceResponse(sourcePath, base, siblings, "2026-09-12T09:00:00Z");
    assert.equal(validateSchema(spec.schema, body).ok, true);
    const labels = evaluateEndpointLabels(200, spec, body);
    assert.equal(labels.ok, true);
    assert.equal(labels.lie, null);
    assert.deepEqual(labels.unavailableSources, [sourcePath]);
    const gate = summarizeReleaseGate([{
      path, required: true, lie: false, degraded: labels.unavailableSources.length > 0,
    }], 1);
    assert.equal(gate.lies, 0);
    assert.equal(gate.requiredDegraded, 1);
    assert.equal(releaseExitCode(gate), 1);
    assert.equal(evaluateFreshness(path, spec, body,
      Date.parse("2026-09-12T09:01:00Z")).freshOk, true);
    assert.equal(evaluateFreshness(path, spec, body,
      Date.parse("2026-09-12T11:00:00Z")).freshOk, false);
    body[sourcePath] = {
      value: { items: [] },
      freshness: { status: "live", fetched_at: "2026-09-12T09:00:00Z" },
    };
    assert.equal(validateSchema(spec.schema, body).ok, true);
    assert.deepEqual(evaluateEndpointLabels(200, spec, body).unavailableSources, []);
  }
});

test("HTTP probe retains required source absence in the release result", async () => {
  const [path, sourcePath, base, siblings] = unavailableContracts[2];
  const body = sourceResponse(sourcePath, base, siblings, new Date().toISOString());
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const result = await probeEndpoint(path, readinessMatrix.endpoints[path]);
    assert.equal(result.lie, false);
    assert.equal(result.schemaOk, true);
    assert.equal(result.freshOk, true);
    assert.equal(result.degraded, true);
    assert.equal(result.runtimeState, "DEGRADED");
    assert.deepEqual(result.unavailableSources, [sourcePath]);
    assert.equal(releaseExitCode(summarizeReleaseGate([result], 1)), 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Python feed unavailable envelope is honest only with null evidence and a failure clock", () => {
  const spec = { degradedRules: { allowStatuses: [200], allowLabels: ["live", "cached"] } };
  const fx = {
    value: null,
    freshness: {
      status: "unavailable",
      fetched_at: 1790910000.25,
      error: "HTTPStatusError: upstream 503",
    },
  };
  const body = { fx };
  assert.equal(evaluateEndpointLabels(200, spec, body).ok, true);
  assert.equal(evaluateEndpointLabels(200, spec, { fx: { ...fx, value: {} } }).ok, false);
  assert.equal(evaluateEndpointLabels(200, spec, { fx: { ...fx, freshness: { ...fx.freshness, error: "" } } }).ok, false);
  assert.equal(evaluateEndpointLabels(200, spec, { fx: { ...fx, freshness: { ...fx.freshness, fetched_at: "bad" } } }).ok, false);
  assert.equal(evaluateEndpointLabels(200, spec, { fx: { ...fx, freshness: { ...fx.freshness, status: "stale" } } }).ok, false);
});

test("SYNTHETIC HTTP probe blocks a fresh cited but unbuilt RAG index", async () => {
  const path = "/api/a11oy/v1/rag/status";
  const body = {
    status: "DEGRADED",
    data_kind: "unavailable",
    index: { built: false, chunks: 0 },
    index_built: false,
    corpus: {},
    fetchedAt: new Date().toISOString(),
    citations: [{ source: "SYNTHETIC unbuilt RAG status fixture; no deployed API contacted" }],
  };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const result = await probeEndpoint(path, readinessMatrix.endpoints[path]);
    assert.equal(result.lie, false);
    assert.equal(result.schemaOk, true);
    assert.equal(result.citationOk, true);
    assert.equal(result.freshOk, true);
    assert.equal(result.labelPolicyOk, true);
    assert.equal(result.degraded, true);
    assert.equal(result.runtimeState, "DEGRADED");
    assert.deepEqual(result.unavailableSources, ["$"]);
    const gate = summarizeReleaseGate([result], 1);
    assert.equal(gate.requiredDegraded, 1);
    assert.equal(gate.blocked, true);
    assert.equal(releaseExitCode(gate), 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("admitted negative root scalar labels retain endpoint-level absence", () => {
  const spec = readinessMatrix.endpoints["/api/a11oy/v1/rag/status"];
  for (const key of [
    "status", "state", "label", "mode", "freshness",
    "data_kind", "datakind", "source_kind", "sourcekind",
    "evidence_state", "evidencestate",
  ]) {
    for (const value of ["degraded", "UNAVAILABLE", " DeGrAdEd "]) {
      const result = evaluateEndpointLabels(200, spec, { [key]: value });
      assert.equal(result.ok, true, `${key}=${value}`);
      assert.equal(result.lie, null, `${key}=${value}`);
      assert.deepEqual(result.unavailableSources, ["$"], `${key}=${value}`);
    }
  }
});

test("default and unknown root labels remain rejected without a new allowlist", () => {
  for (const spec of [
    {},
    { degradedRules: { allowStatuses: [200], allowLabels: ["live", "cached"] } },
  ]) {
    for (const value of ["degraded", "unavailable", "unknown", "vendor-pending"]) {
      const result = evaluateEndpointLabels(200, spec, { data_kind: value });
      assert.equal(result.ok, false, value);
      assert.deepEqual(result.unavailableSources, [], value);
    }
  }
  const ragSpec = readinessMatrix.endpoints["/api/a11oy/v1/rag/status"];
  for (const value of ["unknown", "vendor-pending"]) {
    assert.equal(evaluateEndpointLabels(200, ragSpec, { data_kind: value }).ok, false);
  }
});

test("nested optional and domain negatives do not speak for root availability", () => {
  const spec = readinessMatrix.endpoints["/api/a11oy/v1/rag/status"];
  const body = {
    status: "LIVE",
    data_kind: "live",
    incidents: [{ status: "UNAVAILABLE", state: "degraded", label: "unavailable" }],
    optional: {
      data_kind: "unavailable",
      mode: "degraded",
      freshness: { status: "DEGRADED" },
      source: {
        value: null,
        freshness: {
          status: "UNAVAILABLE",
          fetched_at: new Date().toISOString(),
          error: "SYNTHETIC optional-source absence",
        },
      },
    },
  };
  const result = evaluateEndpointLabels(200, spec, body);
  assert.equal(result.ok, true);
  assert.deepEqual(result.unavailableSources, []);
  assert.deepEqual(evaluateEndpointLabels(200, spec, [{ status: "DEGRADED" }])
    .unavailableSources, []);
});

test("SYNTHETIC HTTP probe keeps built live RAG operational evidence unchanged", async () => {
  const path = "/api/a11oy/v1/rag/status";
  const body = {
    status: "REAL", data_kind: "live",
    index: { built: true, chunks: 1 }, index_built: true, corpus: {},
    fetchedAt: new Date().toISOString(),
    citations: [{ source: "SYNTHETIC built RAG status fixture; no deployed API contacted" }],
  };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const result = await probeEndpoint(path, readinessMatrix.endpoints[path]);
    assert.equal(result.lie, false);
    assert.equal(result.schemaOk, true);
    assert.equal(result.citationOk, true);
    assert.equal(result.freshOk, true);
    assert.equal(result.labelPolicyOk, true);
    assert.equal(result.degraded, false);
    assert.equal(result.runtimeState, "RUNNING");
    assert.deepEqual(result.unavailableSources, []);
    assert.equal(releaseExitCode(summarizeReleaseGate([result], 1)), 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("SYNTHETIC HTTP root-negative evidence does not mask independent failures", async () => {
  const path = "/api/a11oy/v1/rag/status";
  const base = {
    status: "DEGRADED", data_kind: "unavailable",
    index: { built: false, chunks: 0 }, index_built: false, corpus: {},
    fetchedAt: new Date().toISOString(),
    citations: [{ source: "SYNTHETIC negative-evidence fixture; no deployed API contacted" }],
  };
  const noCitation = { ...base };
  delete noCitation.citations;
  delete noCitation.corpus;
  const stale = { ...base, fetchedAt: "2000-01-01T00:00:00Z" };
  const noClock = { ...base };
  delete noClock.fetchedAt;
  const originalFetch = globalThis.fetch;
  try {
    for (const [body, spec, failedGate, expectedReason] of [
      [noCitation, readinessMatrix.endpoints[path], "citationOk", /citationsRequired/],
      [stale, readinessMatrix.endpoints[path], "freshOk", /stale/],
      [noClock, readinessMatrix.endpoints[path], "freshOk", /freshness timestamp missing/],
      [base, { ...readinessMatrix.endpoints[path], schema: "text" },
        "schemaOk", /schema invalid/],
    ]) {
      globalThis.fetch = async () => new Response(JSON.stringify(body), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
      const result = await probeEndpoint(path, spec);
      assert.equal(result[failedGate], false, failedGate);
      assert.equal(result.lie, true);
      assert.equal(result.degraded, true);
      assert.equal(result.runtimeState, "ERROR");
      assert.deepEqual(result.unavailableSources, ["$"]);
      assert.ok(result.lies.some((reason) => expectedReason.test(reason)));
      assert.equal(releaseExitCode(summarizeReleaseGate([result], 1)), 1);
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});
