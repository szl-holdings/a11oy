import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  TWO_WITNESS_LIVE_ADAPTERS_ENABLED,
  compareResearchEvidence,
  emitTwoWitnessResearchReceipt,
  normalizeOpenAIWebSearchResult,
  normalizePerplexitySearchResult,
  verifyReceipt,
  type NormalizedResearchProviderEvidence,
  type OpenAIWebSearchResultInput,
  type PerplexitySearchResultInput,
  type ResearchEvidenceLabel,
} from "./index.ts";

interface FixtureCase {
  readonly name: string;
  readonly expected_label: ResearchEvidenceLabel;
  readonly expected_integrity_valid: boolean;
  readonly tamper_source_list?: boolean;
  readonly openai: OpenAIWebSearchResultInput;
  readonly perplexity: PerplexitySearchResultInput;
}

interface FixtureDocument {
  readonly query_sha256: string;
  readonly policy_sha256: string;
  readonly cases: readonly FixtureCase[];
}

const fixtureUrl = new URL("../fixtures/two_witness_research_v0.json", import.meta.url);
const fixtures = JSON.parse(readFileSync(fixtureUrl, "utf8")) as FixtureDocument;

function normalizedProviders(fixture: FixtureCase): readonly NormalizedResearchProviderEvidence[] {
  const openai = normalizeOpenAIWebSearchResult(fixture.openai);
  const perplexity = normalizePerplexitySearchResult(fixture.perplexity);
  if (!fixture.tamper_source_list) return [openai, perplexity];

  return [
    {
      ...openai,
      sources: openai.sources.map((source, index) => (
        index === 0 ? { ...source, url: "https://tamper.example/changed" } : source
      )),
    },
    perplexity,
  ];
}

for (const fixture of fixtures.cases) {
  test(`two-witness fixture: ${fixture.name}`, () => {
    const comparison = compareResearchEvidence({
      query_sha256: fixtures.query_sha256,
      policy_sha256: fixtures.policy_sha256,
      providers: normalizedProviders(fixture),
    });

    assert.equal(comparison.label, fixture.expected_label);
    assert.equal(comparison.integrity_valid, fixture.expected_integrity_valid);
    assert.equal(comparison.action_authorized, false);
    assert.notEqual(comparison.label, "TRUE");

    const receipt = emitTwoWitnessResearchReceipt(comparison, {
      actor_id: "did:example:offline-test",
      invocation_id: `fixture-${fixture.name}`,
      timestamp: new Date("2026-07-28T12:00:00.000Z"),
    });
    assert.deepEqual(verifyReceipt(receipt), { valid: true, errors: [] });

    const serialized = JSON.stringify(receipt.envelope);
    assert.equal(serialized.includes("raw query must not be receipted"), false);
    assert.equal(serialized.includes("raw snippet must not be receipted"), false);
    assert.equal(serialized.includes("must-not-escape"), false);
    assert.equal(serialized.includes("\"snippet\""), false);
    assert.equal(serialized.includes("\"api_key\""), false);
  });
}

test("provider normalizers produce stable source hashes and strip sensitive URL parameters", () => {
  const fixture = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(fixture);
  const [openai, perplexity] = normalizedProviders(fixture);

  assert.equal(openai.sources[0]?.url, "https://example.com/research/report");
  assert.equal(perplexity.sources[0]?.url, "https://example.com/research/report");
  assert.equal(openai.source_list_sha256, perplexity.source_list_sha256);
  assert.match(openai.sources[0]?.title_sha256 ?? "", /^[a-f0-9]{64}$/);
});

test("live adapters remain disabled and the public label vocabulary excludes a truth claim", () => {
  const labels: readonly ResearchEvidenceLabel[] = [
    "CORROBORATED",
    "DIVERGENT",
    "SINGLE_PROVIDER",
    "INSUFFICIENT",
    "UNAVAILABLE",
  ];
  assert.equal(TWO_WITNESS_LIVE_ADAPTERS_ENABLED, false);
  assert.equal(labels.includes("TRUE" as ResearchEvidenceLabel), false);
});

test("receipt emission rejects a caller-modified comparison", () => {
  const fixture = fixtures.cases.find((candidate) => candidate.name === "disjoint");
  assert.ok(fixture);
  const comparison = compareResearchEvidence({
    query_sha256: fixtures.query_sha256,
    policy_sha256: fixtures.policy_sha256,
    providers: normalizedProviders(fixture),
  });

  assert.throws(
    () => emitTwoWitnessResearchReceipt(
      { ...comparison, label: "CORROBORATED" },
      { actor_id: "did:example:offline-test" },
    ),
    /comparison verification failed/,
  );
});
