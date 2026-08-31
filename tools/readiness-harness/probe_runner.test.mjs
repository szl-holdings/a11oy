// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import test from "node:test";

import {
  evaluateEndpointLabels,
  evaluateFreshness,
  findEvidenceLabels,
  findTimestamp,
  validateSchema,
} from "./probe_runner.mjs";

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

test("router-stats schema requires live receipt-backed counter observations", () => {
  const observed = {
    state: "LIVE",
    mode: "live",
    data_kind: "live",
    catalog_state: "LIVE",
    throughput_state: "OBSERVED",
    routes: [],
    servedThisWindow: 0,
    routingDecisionsSinceStart: 0,
    tiers: ["T0"],
    counter_scope: "process_lifetime",
    counter_started_at: "2026-08-31T04:38:46.077434Z",
    observed_at: "2026-08-31T04:42:04.914661Z",
    source: "szl_llm_registry.router_stats_snapshot",
    catalog_source: "szl_llm_registry.MODEL_REGISTRY",
    doctrine: "v11",
    honesty: "Exact trusted routing-decision counts since counter_started_at.",
  };
  assert.equal(validateSchema("router_stats", observed).ok, true);
  assert.equal(validateSchema("router_stats", { ...observed, state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, throughput_state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, source: "szl_brain.TIERS" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, counter_scope: "rolling_window" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routes: "not-an-array" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: 0.5 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routingDecisionsSinceStart: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, counter_started_at: "not-a-time" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, observed_at: "not-a-time" }).ok, false);
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
