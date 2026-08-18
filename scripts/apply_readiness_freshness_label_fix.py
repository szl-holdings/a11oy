#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

RUNNER = Path("tools/readiness-harness/probe_runner.mjs")
TESTS = Path("tools/readiness-harness/probe_runner.test.mjs")

OLD_CLASSIFIER = '''        const explicit = EXPLICIT_EVIDENCE_KEY.test(key);
        const freshnessScoped = (insideFreshness || keyIsFreshness)
          && FRESHNESS_LABEL_KEY.test(key);
        const rootScoped = depth === 0 && ROOT_LABEL_KEY.test(key)
          && candidates.has(normalized);
        if (explicit || freshnessScoped || rootScoped) {
'''

NEW_CLASSIFIER = '''        const explicit = EXPLICIT_EVIDENCE_KEY.test(key);
        const nestedFreshnessScoped = insideFreshness
          && FRESHNESS_LABEL_KEY.test(key);
        const scalarFreshness = keyIsFreshness && candidates.has(normalized);
        const rootScoped = depth === 0 && ROOT_LABEL_KEY.test(key)
          && candidates.has(normalized);
        if (explicit || nestedFreshnessScoped || scalarFreshness || rootScoped) {
'''

OLD_IMPORT = 'import { findTimestamp, validateSchema } from "./probe_runner.mjs";\n'
NEW_IMPORT = 'import { findEvidenceLabels, findTimestamp, validateSchema } from "./probe_runner.mjs";\n'

TEST_MARKER = 'test("schema freshness metadata is not treated as runtime evidence", () => {'
TEST_BLOCK = r'''

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
  assert.deepEqual(findEvidenceLabels({ freshness: "object" }), []);
  assert.deepEqual(findEvidenceLabels({ freshness: "string" }), []);
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
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        if text.count(new) != 1:
            raise RuntimeError(f"{label}: successor duplicated")
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one original anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    runner = RUNNER.read_text(encoding="utf-8")
    runner = replace_once(runner, OLD_CLASSIFIER, NEW_CLASSIFIER, "evidence classifier")
    RUNNER.write_text(runner, encoding="utf-8")

    tests = TESTS.read_text(encoding="utf-8")
    tests = replace_once(tests, OLD_IMPORT, NEW_IMPORT, "test import")
    if TEST_MARKER not in tests:
        tests = tests.rstrip() + TEST_BLOCK + "\n"
    elif tests.count(TEST_MARKER) != 1:
        raise RuntimeError("freshness regression tests duplicated")
    TESTS.write_text(tests, encoding="utf-8")

    final_runner = RUNNER.read_text(encoding="utf-8")
    final_tests = TESTS.read_text(encoding="utf-8")
    if OLD_CLASSIFIER in final_runner or NEW_CLASSIFIER not in final_runner:
        raise RuntimeError("evidence classifier repair not materialized")
    if NEW_IMPORT not in final_tests or TEST_MARKER not in final_tests:
        raise RuntimeError("freshness regression tests not materialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
