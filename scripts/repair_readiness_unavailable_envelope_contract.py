#!/usr/bin/env python3
"""Repair the readiness schema/runtime contradiction for canonical UNAVAILABLE envelopes.

The runtime deliberately returns ``value: null`` when an external source has never
been observed. The readiness harness already admits the canonical ``UNAVAILABLE``
label, but its schema validator still demanded ``value.items``. This script makes
that conditional shape explicit without inventing empty records or weakening any
HTTP, citation, freshness, or label gate.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "readiness-harness" / "probe_runner.mjs"
TESTS = ROOT / "tests" / "test_readiness_deep_vertical_contract.py"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    helper_anchor = '''function valueAtPath(obj, path) {
  let cursor = obj;
  for (const key of String(path).split(".")) {
    if (
      cursor === null || typeof cursor !== "object"
      || !Object.prototype.hasOwnProperty.call(cursor, key)
    ) {
      return { found: false, value: undefined };
    }
    cursor = cursor[key];
  }
  return { found: true, value: cursor };
}

function requiredFreshnessTimestampPaths(spec) {'''

    helper_replacement = '''function valueAtPath(obj, path) {
  let cursor = obj;
  for (const key of String(path).split(".")) {
    if (
      cursor === null || typeof cursor !== "object"
      || !Object.prototype.hasOwnProperty.call(cursor, key)
    ) {
      return { found: false, value: undefined };
    }
    cursor = cursor[key];
  }
  return { found: true, value: cursor };
}

// Source wrappers use value=null when an upstream has never produced evidence.
// That state is schema-valid only when it is the exact canonical UNAVAILABLE
// envelope: a measured failure clock plus a non-empty error. It never converts
// absence into an empty result set and it remains subject to the endpoint's
// independent label, citation, freshness, and HTTP-status gates.
function isCanonicalUnavailableItemsEnvelope(body, path) {
  const suffix = ".value.items";
  const text = String(path);
  if (!text.endsWith(suffix)) return false;
  const prefix = text.slice(0, -suffix.length);
  const candidate = prefix
    ? valueAtPath(body, prefix)
    : { found: true, value: body };
  if (
    !candidate.found
    || candidate.value === null
    || typeof candidate.value !== "object"
    || Array.isArray(candidate.value)
  ) return false;
  const source = candidate.value;
  const freshness = source.freshness;
  return (
    Object.prototype.hasOwnProperty.call(source, "value")
    && source.value === null
    && freshness !== null
    && typeof freshness === "object"
    && !Array.isArray(freshness)
    && freshness.status === "UNAVAILABLE"
    && toDate(freshness.fetched_at) !== null
    && typeof freshness.error === "string"
    && freshness.error.trim().length > 0
  );
}

function requiredFreshnessTimestampPaths(spec) {'''

    validation_anchor = '''      if (sc.requiredPaths && !sc.requiredPaths.every((path) => {
        let cursor = body;
        for (const key of path.split(".")) {
          if (!cursor || typeof cursor !== "object" || !(key in cursor)) return false;
          cursor = cursor[key];
        }
        return true;
      })) return false;
      if (sc.requiredPathTypes && !Object.entries(sc.requiredPathTypes).every(([path, type]) => {
        let cursor = body;
        for (const key of path.split(".")) {
          if (!cursor || typeof cursor !== "object" || !(key in cursor)) return false;
          cursor = cursor[key];
        }
        if (type === "array") return Array.isArray(cursor);'''

    validation_replacement = '''      if (sc.requiredPaths && !sc.requiredPaths.every((path) => {
        const candidate = valueAtPath(body, path);
        return candidate.found || isCanonicalUnavailableItemsEnvelope(body, path);
      })) return false;
      if (sc.requiredPathTypes && !Object.entries(sc.requiredPathTypes).every(([path, type]) => {
        const candidate = valueAtPath(body, path);
        if (!candidate.found) {
          return type === "array"
            && isCanonicalUnavailableItemsEnvelope(body, path);
        }
        const cursor = candidate.value;
        if (type === "array") return Array.isArray(cursor);'''

    test_anchor = '''def test_required_http_200_stale_unavailable_and_modeled_labels_fail() -> None:
'''

    test_insert = r'''def test_canonical_unavailable_source_envelopes_are_typed_not_fabricated() -> None:
    result = _node_eval(
        """
const observed = {
  value: { items: [{ url: "https://www.courtlistener.com/opinion/1/" }] },
  freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" },
};
const unavailable = {
  value: null,
  freshness: {
    status: "UNAVAILABLE",
    fetched_at: "2026-08-11T12:00:00Z",
    error: "upstream timeout",
  },
};

const matter = {
  surface: "matter",
  term: "insurance",
  opinions: structuredClone(unavailable),
  sources_cited: [{ url: "https://www.courtlistener.com/help/api/rest/" }],
  doctrine: {},
};
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, true);

delete matter.opinions.freshness.error;
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.freshness.error = "upstream timeout";

matter.opinions.value = { items: [] };
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.value = null;

matter.opinions.freshness.status = "unavailable";
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.freshness.status = "UNAVAILABLE";

matter.opinions.freshness.fetched_at = "not-a-timestamp";
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.freshness.fetched_at = "2026-08-11T12:00:00Z";

const legal = {
  vertical: "legal",
  federal_register: structuredClone(observed),
  court_filings: structuredClone(unavailable),
  sources_cited: [{ url: "https://www.federalregister.gov/" }],
  doctrine: {},
};
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, true);

legal.federal_register = structuredClone(unavailable);
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, true);

legal.court_filings.freshness.status = "live";
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, false);
legal.court_filings.freshness.status = "UNAVAILABLE";

legal.court_filings.value = { items: [] };
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, false);
legal.court_filings = structuredClone(observed);
delete legal.court_filings.value.items;
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, false);
"""
    )
    assert result.returncode == 0, result.stderr


def test_required_http_200_stale_unavailable_and_modeled_labels_fail() -> None:
'''

    replace_exact(PROBE, helper_anchor, helper_replacement)
    replace_exact(PROBE, validation_anchor, validation_replacement)
    replace_exact(TESTS, test_anchor, test_insert)

    commands = [
        ["python", "tools/readiness-harness/gen_tabs_matrix.py", "--check"],
        [
            "python", "-m", "pytest", "-q",
            "tests/test_readiness_deep_vertical_contract.py",
            "tests/test_legal_readiness_unavailable_contract.py",
        ],
        ["node", "tools/readiness-harness/probe_runner.test.mjs"],
        ["git", "diff", "--check"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
