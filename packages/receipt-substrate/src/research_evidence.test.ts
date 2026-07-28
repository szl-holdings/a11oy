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

test("content-selecting code parameters retain distinct redacted identities", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const openai = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: "https://research.example/paper?code=alpha",
    }],
  });
  const perplexity = normalizePerplexitySearchResult({
    ...base.perplexity,
    results: [{
      url: "https://research.example/paper?code=beta",
    }],
  });
  const comparison = compareResearchEvidence({
    query_sha256: fixtures.query_sha256,
    policy_sha256: fixtures.policy_sha256,
    providers: [openai, perplexity],
  });

  assert.equal(comparison.source_url_overlap_count, 0);
  assert.equal(comparison.label, "DIVERGENT");
  assert.equal(JSON.stringify(comparison).includes("alpha"), false);
  assert.equal(JSON.stringify(comparison).includes("beta"), false);
  assert.match(new URL(openai.sources[0]?.url ?? "").searchParams.get("code") ?? "", /^sha256:/);
});

test("query and snippet selectors retain distinct digested identities without leaking content", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const openai = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: "https://research.example/paper?q=private-query-alpha&snippet=private-snippet-alpha",
    }],
  });
  const perplexity = normalizePerplexitySearchResult({
    ...base.perplexity,
    results: [{
      url: "https://research.example/paper?q=private-query-beta&snippet=private-snippet-beta",
    }],
  });
  const comparison = compareResearchEvidence({
    query_sha256: fixtures.query_sha256,
    policy_sha256: fixtures.policy_sha256,
    providers: [openai, perplexity],
  });
  const receipt = emitTwoWitnessResearchReceipt(comparison, {
    actor_id: "did:example:selector-redaction",
    timestamp: new Date("2026-07-28T12:00:00.000Z"),
  });
  const serialized = JSON.stringify(receipt.envelope);
  const openaiUrl = new URL(openai.sources[0]?.url ?? "");
  const perplexityUrl = new URL(perplexity.sources[0]?.url ?? "");

  for (const forbidden of [
    "private-query-alpha",
    "private-query-beta",
    "private-snippet-alpha",
    "private-snippet-beta",
  ]) {
    assert.equal(serialized.includes(forbidden), false);
  }
  for (const key of ["q", "snippet"]) {
    assert.match(openaiUrl.searchParams.get(key) ?? "", /^sha256:[a-f0-9]{64}$/);
    assert.match(perplexityUrl.searchParams.get(key) ?? "", /^sha256:[a-f0-9]{64}$/);
    assert.notEqual(openaiUrl.searchParams.get(key), perplexityUrl.searchParams.get(key));
  }
  assert.equal(comparison.source_url_overlap_count, 0);
  assert.equal(comparison.label, "DIVERGENT");
});

test("source dates require an explicit timezone and normalize deterministically", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const zoned = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: "https://research.example/zoned",
      published_at: "2026-07-28T08:00:00-04:00",
      last_updated_at: "2026-07-28T12:00:00Z",
    }],
  });
  const zoneLess = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: "https://research.example/zone-less",
      published_at: "2026-07-28T12:00:00",
      last_updated_at: "2026-07-28",
    }],
  });

  assert.equal(zoned.sources[0]?.published_at, "2026-07-28T12:00:00.000Z");
  assert.equal(zoned.sources[0]?.last_updated_at, "2026-07-28T12:00:00.000Z");
  assert.equal(zoneLess.sources[0]?.published_at, undefined);
  assert.equal(zoneLess.sources[0]?.last_updated_at, undefined);

  const leapDay = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: "https://research.example/leap-day",
      published_at: "2024-02-29T23:59:59+00:00",
    }],
  });
  assert.equal(leapDay.sources[0]?.published_at, "2024-02-29T23:59:59.000Z");
});

test("source dates reject impossible calendar values and offsets", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const invalidValues = [
    "2026-02-29T12:00:00Z",
    "2026-02-30T00:00:00Z",
    "2026-04-31T12:00:00Z",
    "2026-13-01T00:00:00Z",
    "2026-07-28T24:00:00Z",
    "2026-07-28T24:01:00Z",
    "2026-07-28T12:00:00-00:00",
    "2026-07-28T12:00:00+24:00",
    "2026-07-28T12:00:00+04:60",
  ];

  for (const published_at of invalidValues) {
    const normalized = normalizeOpenAIWebSearchResult({
      ...base.openai,
      sources: [{
        url: "https://research.example/invalid-time",
        published_at,
      }],
    });
    assert.equal(normalized.sources[0]?.published_at, undefined, published_at);
  }
});

test("vendor-prefixed presigned credentials never enter normalized evidence", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const openai = normalizeOpenAIWebSearchResult({
    ...base.openai,
    sources: [{
      url: [
        "https://research.example/paper?topic=governance",
        "X-Amz-Credential=must-not-escape",
        "X-Amz-Signature=must-not-escape",
      ].join("&"),
    }],
  });
  const serialized = JSON.stringify(openai);

  assert.equal(serialized.includes("must-not-escape"), false);
  assert.equal(openai.sources[0]?.url, "https://research.example/paper?topic=governance");
});

test("comparison rejects undeclared provider, usage, and source fields", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const openai = normalizeOpenAIWebSearchResult(base.openai);
  const perplexity = normalizePerplexitySearchResult(base.perplexity);
  const unsafeOpenAI = {
    ...openai,
    api_key: "must-not-escape",
    usage: {
      ...(openai.usage ?? {}),
      response_body: "raw usage must not be receipted",
    },
    sources: openai.sources.map((source) => ({
      ...source,
      snippet: "raw snippet must not be receipted",
    })),
  } as NormalizedResearchProviderEvidence;
  const comparison = compareResearchEvidence({
    query_sha256: fixtures.query_sha256,
    policy_sha256: fixtures.policy_sha256,
    providers: [unsafeOpenAI, perplexity],
  });
  const serialized = JSON.stringify(comparison);

  assert.equal(serialized.includes("must-not-escape"), false);
  assert.equal(serialized.includes("raw usage must not be receipted"), false);
  assert.equal(serialized.includes("raw snippet must not be receipted"), false);
  assert.equal(serialized.includes("\"api_key\""), false);
  assert.equal(serialized.includes("\"response_body\""), false);
  assert.equal(serialized.includes("\"snippet\""), false);
  assert.equal(comparison.integrity_valid, false);
  assert.ok(
    comparison.integrity_errors.includes("openai: unexpected provider field api_key"),
  );
  assert.ok(
    comparison.integrity_errors.includes("openai: unexpected usage field response_body"),
  );
  assert.ok(
    comparison.integrity_errors.includes("openai: source 0 unexpected field snippet"),
  );
  assert.throws(
    () => emitTwoWitnessResearchReceipt(comparison, {
      actor_id: "did:example:projection-test",
    }),
    /comparison verification failed/,
  );
});

test("direct comparison rebuilds credential-bearing allowed fields before receipt emission", () => {
  const base = fixtures.cases.find((candidate) => candidate.name === "matching");
  assert.ok(base);
  const openai = normalizeOpenAIWebSearchResult(base.openai);
  const perplexity = normalizePerplexitySearchResult(base.perplexity);
  const unsafeOpenAI = {
    ...openai,
    response_id: { api_key: "response-id-secret-must-not-escape" },
    model: { snippet: "model-secret-must-not-escape" },
    sources: openai.sources.map((source, index) => (
      index === 0
        ? {
          ...source,
          url: `${source.url}?X-Amz-Credential=source-secret-must-not-escape`,
        }
        : source
    )),
  } as unknown as NormalizedResearchProviderEvidence;
  const comparison = compareResearchEvidence({
    query_sha256: fixtures.query_sha256,
    policy_sha256: fixtures.policy_sha256,
    providers: [unsafeOpenAI, perplexity],
  });
  const receipt = emitTwoWitnessResearchReceipt(comparison, {
    actor_id: "did:example:allowed-field-negative",
  });
  const serialized = JSON.stringify(receipt.envelope);
  const payload = receipt.envelope.payload as Record<string, unknown>;

  for (const forbidden of [
    "response-id-secret-must-not-escape",
    "model-secret-must-not-escape",
    "source-secret-must-not-escape",
  ]) {
    assert.equal(serialized.includes(forbidden), false);
  }
  assert.equal(comparison.providers[0]?.response_id, undefined);
  assert.equal(comparison.providers[0]?.model, undefined);
  assert.equal(
    comparison.providers[0]?.sources[0]?.url,
    "https://example.com/research/report",
  );
  assert.equal(comparison.integrity_valid, true);
  assert.equal(payload.evidence_class, "MODELED");
  assert.equal(payload.signature_state, "UNSIGNED_LOCAL");
  assert.equal(payload.external_attestation_state, "EXTERNAL_ATTESTATION_FALSE");
  assert.equal(payload.external_attestation, false);
  assert.equal(payload.action_authorization_state, "ACTION_AUTHORIZED_FALSE");
  assert.equal(payload.action_authorized, false);
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
