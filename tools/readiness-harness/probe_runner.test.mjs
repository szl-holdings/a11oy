// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import test from "node:test";

import {
  evaluateEndpointLabels,
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

test("freshness recognizes the canonical observed_at response clock", () => {
  const body = {
    verdicts: [{ timestamp: "2026-06-05T23:32:40Z", decision: "deny" }],
    observed_at: "2026-08-20T09:55:00Z",
  };

  assert.equal(findTimestamp(body)?.toISOString(), "2026-08-20T09:55:00.000Z");
});

test("mixed KEVGate provenance remains release-red", () => {
  const descriptor = "live KEV IDs/dates/vendors + LIVE EPSS 24/24; CVSS/severity = derived-sample (deterministic from CVE ID)";
  const verdict = evaluateEndpointLabels(200, {
    degradedRules: {
      allowStatuses: [200],
      allowLabels: ["live", "cached"],
      liesIf: ["mock", "fabricated", "placeholder"],
    },
  }, {
    mode: "live",
    data_kind: descriptor,
    gates_mapped: [{ gate: "security", decision: "deny" }],
  });

  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.disallowed.map(({ path }) => path), ["data_kind"]);
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
