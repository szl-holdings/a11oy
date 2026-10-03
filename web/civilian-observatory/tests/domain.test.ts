import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@noble/hashes/utils.js";
import { analyzeInputSchema, planInputSchema, type FeedSnapshot, type SourceRecord } from "../shared/schema";
import { makeDryRun, rankAdvisories, sourceWithAge } from "../shared/domain";

// These are software-test fixtures, never operational/model benchmark data.
const source = (name: string): SourceRecord => ({
  name, source_url: "https://example.org/software-test-fixture",
  fetched_at: new Date().toISOString(), source_date: "2026-10-01",
  sha256: "0".repeat(64), status: "OBSERVED", error: null,
});
const feeds = (): FeedSnapshot => ({
  schema_version: "1.0", generated_at: new Date().toISOString(),
  kev: { source: source("CISA test fixture"), catalog_version: "FIXTURE",
    entries: [{ cveID: "CVE-2024-0001", dateAdded: "2026-10-01", vendorProject: "TEST",
      product: "FIXTURE", vulnerabilityName: "Not an incident", shortDescription: "UNIT TEST",
      requiredAction: "TEST ONLY", knownRansomwareCampaignUse: "Unknown" }] },
  epss: { source: source("EPSS test fixture"), requested: ["CVE-2024-0001", "CVE-2024-0002"],
    entries: [{ cve: "CVE-2024-0001", epss: 0, percentile: 0, date: "2026-10-01" },
      { cve: "CVE-2024-0002", epss: .99, percentile: .99, date: "2026-10-01" }] },
});
test("portable browser digest matches Node for exact Unicode payload bytes", () => {
  const payload = '{"type":"UNIT_TEST","text":"λ; café"}';
  assert.equal(bytesToHex(sha256(new TextEncoder().encode(payload))), createHash("sha256").update(payload, "utf8").digest("hex"));
});
test("KEV record precedes a non-KEV record even with a lower EPSS estimate", () => {
  assert.equal(rankAdvisories(["CVE-2024-0002", "CVE-2024-0001"], feeds()).rows[0].cve, "CVE-2024-0001");
});
test("missing data stays null, while a real zero remains zero", () => {
  const result = rankAdvisories(["CVE-2024-0001", "CVE-2024-0999"], feeds());
  assert.equal(result.rows[0].epss?.epss, 0);
  assert.equal(result.rows[1].epss, null);
  assert.equal(result.rows[1].priority, "INSUFFICIENT_DATA");
});
test("a KEV outage is unknown, not not-listed, even if stale entries were accidentally supplied", () => {
  const f = feeds(); f.kev.source.status = "UNAVAILABLE";
  assert.equal(rankAdvisories(["CVE-2024-0001"], f).rows[0].kev_status, "UNKNOWN");
});
test("an EPSS outage never exposes a previous entry as a current estimate", () => {
  const f = feeds(); f.epss.source.status = "UNAVAILABLE";
  assert.equal(rankAdvisories(["CVE-2024-0001"], f).rows[0].epss, null);
});
test("duplicate IDs collapse and tied records are deterministically ordered", () => {
  const r = rankAdvisories(["CVE-2024-0999", "CVE-2024-0998", "CVE-2024-0999"], feeds());
  assert.deepEqual(r.input, ["CVE-2024-0998", "CVE-2024-0999"]);
  assert.deepEqual(r.rows.map(x => x.cve), r.input);
});
test("exposure, trained-model execution, and asset matching are never inferred", () => {
  const result = rankAdvisories(["CVE-2024-0001"], feeds());
  assert.equal(result.asset_inventory_connected, false);
  assert.equal(result.model_executed, false);
  assert.equal(result.rows[0].exposure, "UNKNOWN");
});
test("analysis input rejects URLs, commands, additional keys, and oversized batches", () => {
  for (const value of [
    { cves: ["https://example.org"] }, { cves: ["CVE-2024-0001"], command: "run" },
    { cves: [] }, { cves: Array(51).fill("CVE-2024-0001") }, { cves: ["CVE-2024-1"] },
  ]) assert.equal(analyzeInputSchema.safeParse(value).success, false);
});
test("source freshness preserves past unavailability and detects stale/future clocks", () => {
  const f = source("FIXTURE"); f.fetched_at = "2020-01-01T00:00:00Z";
  assert.equal(sourceWithAge(f, 24).status, "STALE");
  f.fetched_at = "2099-01-01T00:00:00Z";
  assert.equal(sourceWithAge(f, 24).status, "STALE");
  f.status = "UNAVAILABLE";
  assert.equal(sourceWithAge(f, 24).status, "UNAVAILABLE");
});
test("dry-run schema rejects live mode, commands, and extra target fields", () => {
  for (const value of [
    { scenario: "cyber", simulatedApproval: true, mode: "execute" },
    { scenario: "cyber", simulatedApproval: true, mode: "dry-run", target: "example.org" },
    { scenario: "cyber", simulatedApproval: true, mode: "dry-run", command: "run" },
  ]) assert.equal(planInputSchema.safeParse(value).success, false);
});
test("all scenarios and approval states have zero external actions", () => {
  for (const scenario of ["cyber", "weather", "research"] as const) for (const approval of [false, true]) {
    const plan = makeDryRun(scenario, approval);
    assert.equal(plan.executed, false); assert.equal(plan.external_calls, 0);
    assert.equal(plan.steps.at(-1)?.state, "NO_ADAPTER");
    assert.equal(plan.steps[1].state, approval ? "SIMULATED_APPROVAL" : "REVIEW_REQUIRED");
  }
});
