// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import test from "node:test";

import { evaluateEndpointLabels } from "./probe_runner.mjs";

const SPEC = {
  degradedRules: {
    allowStatuses: [200],
    allowLabels: ["live", "cached"],
    liesIf: [
      "sample",
      "modeled",
      "degraded",
      "unavailable",
      "unknown",
      "mock",
      "fabricated",
      "placeholder",
    ],
  },
};

test("KEV gate separates canonical evidence kind from enrichment provenance", () => {
  const prior = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "live KEV IDs/dates/vendors + derived-sample enrichment",
  });
  assert.equal(prior.ok, false);

  const canonical = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "live",
    enrichment_provenance: "live KEV IDs/dates/vendors + derived-sample enrichment",
  });
  assert.equal(canonical.ok, true);
});

test("KEV gate unavailable evidence remains disallowed", () => {
  const verdict = evaluateEndpointLabels(200, SPEC, {
    mode: "unavailable",
    data_kind: "unavailable",
    enrichment_provenance: "no live or bundled KEV evidence available",
  });

  assert.equal(verdict.ok, false);
  assert.deepEqual(
    verdict.disallowed.map(({ path, normalized }) => ({ path, normalized })),
    [
      { path: "mode", normalized: "unavailable" },
      { path: "data_kind", normalized: "unavailable" },
    ],
  );
});
