// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  evaluateEndpointLabels,
  evaluateFreshness,
  findEvidenceLabels,
  findTimestamp,
  validateRouterStatsSemantic,
  validateSchema,
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

test("router-stats schema requires truthful live process-lifetime counters", () => {
  // Base object tracks the current doctrine-v11 contract: full protected
  // catalog coverage, fresh observation, and the exact honesty const from the
  // checked-in matrix. A hand-rolled minimal object goes stale silently (see
  // the pre-#1620 honesty drift) and must not be reintroduced here.
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
