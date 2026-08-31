// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { evaluateEndpointLabels } from "./probe_runner.mjs";

const MATRIX = JSON.parse(readFileSync(new URL("./tabs.json", import.meta.url)));
const SPEC = MATRIX.endpoints["/api/a11oy/v1/sec/kevgate"];

test("KEV gate keeps sample-derived item evidence fail-closed", () => {
  const prior = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "live KEV IDs/dates/vendors + derived-sample enrichment",
  });
  assert.equal(prior.ok, false);

  const canonical = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "sample",
    enrichment_provenance: "live KEV IDs/dates/vendors + derived-sample enrichment",
    items: [{
      data_kind: "sample",
      cvss_src: "derived",
      cvss_cache_state: "stale",
      evidence_detail: "cvss=derived-sample; stale-nvd-cache-ignored",
    }],
  });
  assert.equal(canonical.ok, false);
  assert.deepEqual(
    canonical.disallowed.map(({ path, normalized }) => ({ path, normalized })),
    [
      { path: "data_kind", normalized: "sample" },
      { path: "items[0].data_kind", normalized: "sample" },
    ],
  );

  const fullySourced = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "cached",
    enrichment_provenance: "live KEV with cached EPSS and CVSS evidence",
    items: [{
      data_kind: "cached",
      cvss_src: "nvd",
      cvss_cache_state: "fresh",
      evidence_detail: "cvss=nvd-cache",
    }],
  });
  assert.equal(fullySourced.ok, true);
});

test("KEV gate rejects cached labels backed by derived or stale CVSS", () => {
  const contradictory = evaluateEndpointLabels(200, SPEC, {
    mode: "live",
    data_kind: "cached",
    enrichment_provenance: "live KEV with contradictory enrichment labels",
    items: [{
      data_kind: "cached",
      cvss_src: "derived",
      cvss_cache_state: "stale",
      evidence_detail: "cvss=derived-sample; stale-nvd-cache-ignored",
    }],
  });

  assert.equal(contradictory.ok, false);
  assert.deepEqual(
    contradictory.disallowed.map(({ path, normalized }) => ({ path, normalized })),
    [{ path: "items[0].cvss_evidence", normalized: "inconsistent" }],
  );
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
