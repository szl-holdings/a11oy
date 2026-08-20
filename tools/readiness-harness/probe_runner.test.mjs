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

test("freshness recognizes the canonical observed_at response clock", () => {
  const body = {
    verdicts: [{ timestamp: "2026-06-05T23:32:40Z", decision: "deny" }],
    observed_at: "2026-08-20T09:55:00Z",
  };

  assert.equal(findTimestamp(body)?.toISOString(), "2026-08-20T09:55:00.000Z");
});

test("a bundled catalog uses its real release clock and remains stale", () => {
  const body = {
    data_kind: "cached",
    dateReleased: "2025-09-30T12:35:25.4401Z",
  };
  const verdict = evaluateFreshness(
    "/api/a11oy/v1/sec/kev",
    { freshnessSLA: 86400 },
    body,
    Date.parse("2026-08-20T11:09:06.017Z"),
  );

  assert.equal(findTimestamp(body)?.toISOString(), "2025-09-30T12:35:25.440Z");
  assert.equal(verdict.freshnessMissing, false);
  assert.equal(verdict.freshOk, false);
  assert.ok(verdict.ageSec > 86400);
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

const kevLabelSpec = {
  modeRequiresDataKind: true,
  degradedRules: {
    allowStatuses: [200],
    allowLabels: ["live", "cached"],
    liesIf: ["mock", "fabricated", "placeholder"],
  },
};

test("a live mode cannot hide weaker or negative KEV evidence", () => {
  for (const dataKind of [
    "cached", "sample", "snapshot", "none", "unavailable", "vendor-pending",
  ]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
      mode: "live",
      data_kind: dataKind,
      items: [],
    });

    assert.equal(verdict.ok, false, dataKind);
  }

  const allowedButContradictory = evaluateEndpointLabels(200, kevLabelSpec, {
    mode: "live",
    data_kind: "cached",
  });
  assert.deepEqual(allowedButContradictory.disallowed, []);
  assert.match(allowedButContradictory.pairConflict.reason, /contradictory/);
});

test("cached mode with live data_kind fails despite individually allowed labels", () => {
  const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
    mode: "cached",
    data_kind: "live",
  });

  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.disallowed, []);
  assert.deepEqual(
    {
      mode: verdict.pairConflict.mode.normalized,
      dataKind: verdict.pairConflict.dataKind.normalized,
    },
    { mode: "cached", dataKind: "live" },
  );
});

test("compatible canonical live and cached pairs remain allowed", () => {
  for (const evidence of [
    { mode: "live", data_kind: "live" },
    { mode: "cached", data_kind: "cached" },
  ]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, evidence);
    assert.equal(verdict.ok, true, JSON.stringify(evidence));
    assert.equal(verdict.pairConflict, null, JSON.stringify(evidence));
  }
});

test("an unknown mode paired with a positive data_kind is fail-closed", () => {
  const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
    mode: "vendor-pending",
    data_kind: "live",
  });

  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.disallowed, []);
  assert.match(verdict.pairConflict.reason, /not a compatible known/);
});

test("a root mode without data_kind is fail-closed", () => {
  for (const mode of ["live", "cached", "vendor-pending", true]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, { mode });

    assert.equal(verdict.ok, false, String(mode));
    assert.equal(verdict.pairConflict.mode.value, mode);
    assert.equal(verdict.pairConflict.dataKind.path, "data_kind");
    assert.match(verdict.pairConflict.reason, /requires a root data_kind/);
  }
});

test("mode/data_kind pairing is scoped to endpoints that declare the contract", () => {
  const verdict = evaluateEndpointLabels(200, {
    degradedRules: kevLabelSpec.degradedRules,
  }, {
    mode: "production",
  });

  assert.equal(verdict.ok, true);
  assert.equal(verdict.pairConflict, null);
});

test("a data_kind-only KEV payload remains allowed", () => {
  const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
    data_kind: "cached",
  });

  assert.equal(verdict.ok, true);
  assert.equal(verdict.pairConflict, null);
});

test("non-string data_kind-only evidence is fail-closed", () => {
  for (const dataKind of [true, 1, null, {}, []]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
      data_kind: dataKind,
    });

    assert.equal(verdict.ok, false, JSON.stringify(dataKind));
    assert.equal(verdict.pairConflict.dataKind.value, dataKind);
    assert.match(verdict.pairConflict.reason, /must be a string/);
  }
});

test("nested non-string explicit evidence is fail-closed", () => {
  for (const evidence of [
    { items: [{ data_kind: true }] },
    { payload: { source_kind: ["live"] } },
    { rows: [{ evidence_state: null }] },
  ]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, evidence);
    assert.equal(verdict.ok, false, JSON.stringify(evidence));
    assert.ok(verdict.pairConflict, JSON.stringify(evidence));
    assert.match(verdict.pairConflict.reason, /must be a string/);
  }
});

test("root arrays cannot hide malformed explicit evidence", () => {
  for (const [evidence, path] of [
    [[{ data_kind: true }], "[0].data_kind"],
    [[{ payload: { source_kind: ["live"] } }], "[0].payload.source_kind"],
    [[[{ evidence_state: null }]], "[0][0].evidence_state"],
  ]) {
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, evidence);
    assert.equal(verdict.ok, false, JSON.stringify(evidence));
    assert.equal(verdict.pairConflict.dataKind.path, path);
    assert.match(verdict.pairConflict.reason, /must be a string/);
  }

  const valid = evaluateEndpointLabels(200, kevLabelSpec, [{
    data_kind: "live",
  }]);
  assert.equal(valid.ok, true);
  assert.equal(valid.pairConflict, null);
});

test("root arrays enforce complete compatible evidence pairs on every item", () => {
  const cases = [
    {
      body: [{ mode: "live", data_kind: "cached" }],
      modePath: "[0].mode",
      reason: /contradictory/,
    },
    {
      body: [{ mode: "vendor-pending", data_kind: "live" }],
      modePath: "[0].mode",
      reason: /not a compatible known/,
    },
    {
      body: [{ mode: "live" }],
      modePath: "[0].mode",
      reason: /requires a root data_kind/,
    },
    {
      body: [
        { mode: "live", data_kind: "live" },
        { mode: "cached", data_kind: "live" },
      ],
      modePath: "[1].mode",
      reason: /contradictory/,
    },
    {
      body: [[{ mode: "live", data_kind: "cached" }]],
      modePath: "[0][0].mode",
      reason: /contradictory/,
    },
  ];

  for (const { body, modePath, reason } of cases) {
    assert.equal(validateSchema("generic_list", body).ok, true, JSON.stringify(body));
    const verdict = evaluateEndpointLabels(200, kevLabelSpec, body);
    assert.equal(verdict.ok, false, JSON.stringify(body));
    assert.equal(verdict.pairConflict.mode.path, modePath);
    assert.match(verdict.pairConflict.reason, reason);
  }
});

test("explicit evidence remains fail-closed beyond five nesting levels", () => {
  const nestedEvidence = (dataKind, levels = 8) => {
    let value = { data_kind: dataKind };
    for (let level = 0; level < levels; level += 1) {
      value = { payload: value };
    }
    return value;
  };
  const evidencePath = `${"payload.".repeat(8)}data_kind`;

  const malformed = evaluateEndpointLabels(200, kevLabelSpec, nestedEvidence(true));
  assert.equal(malformed.ok, false);
  assert.equal(malformed.pairConflict.dataKind.path, evidencePath);
  assert.match(malformed.pairConflict.reason, /must be a string/);

  const fabricated = evaluateEndpointLabels(
    200,
    kevLabelSpec,
    nestedEvidence("fabricated"),
  );
  assert.equal(fabricated.ok, false);
  assert.deepEqual(fabricated.labels.map(({ path }) => path), [evidencePath]);
  assert.equal(fabricated.lie.path, evidencePath);

  const allowed = evaluateEndpointLabels(200, kevLabelSpec, nestedEvidence("live"));
  assert.equal(allowed.ok, true);
  assert.deepEqual(allowed.labels.map(({ path }) => path), [evidencePath]);
});

test("non-string mode/data_kind pairs cannot bypass the evidence contract", () => {
  const verdict = evaluateEndpointLabels(200, kevLabelSpec, {
    mode: true,
    data_kind: "live",
  });
  assert.equal(verdict.ok, false);
  assert.match(verdict.pairConflict.reason, /must be string/);
});

test("KEVGate schema requires complete governed decisions for every row", () => {
  const valid = {
    mode: "live",
    data_kind: "live",
    count: 2,
    governed_decision_rows: 2,
    governance_complete: true,
    items: [
      { decision: "allow", gates_fired: [], lambda_value: 1.0 },
      { decision: "deny", gates_fired: ["gate-03"], lambda_value: 0.0 },
    ],
  };
  assert.equal(validateSchema("kevgate", valid).ok, true);

  for (const body of [
    { ...valid, governance_complete: false },
    { ...valid, governed_decision_rows: 1 },
    { ...valid, count: 1 },
    { ...valid, items: [] },
    { ...valid, items: [{ decision: null, gates_fired: [], lambda_value: 1.0 }] },
    { ...valid, items: [{ decision: "allow", gates_fired: null, lambda_value: 1.0 }] },
    { ...valid, items: [{ decision: "allow", gates_fired: [], lambda_value: true }] },
  ]) {
    assert.equal(validateSchema("kevgate", body).ok, false, JSON.stringify(body));
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
