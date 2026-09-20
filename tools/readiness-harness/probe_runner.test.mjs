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
    verdicts: [{ timestamp: "2026-06-05T23:32-40Z", decision: "deny" }],
    fetchedAt: "2026-07-26T01:05:07Z",
  };

  assert.equal(findTimestamp(body)?.toISOString(), "2026-07-26T01:05:07.000Z");
});
