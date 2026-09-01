#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the bounded readiness-contract repair for honest unavailable sources.

The patch does not convert unavailable external evidence into a live result. It
teaches the release harness to distinguish an explicit, timestamped, errored
UNAVAILABLE observation from fabricated or uncited live data. It also aligns the
readiness snapshot gate with the endpoint's own stale flag and warming cadence.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
PROBE = ROOT / "tools" / "readiness-harness" / "probe_runner.mjs"
PROBE_TEST = ROOT / "tools" / "readiness-harness" / "probe_runner.test.mjs"
DEEP_TEST = ROOT / "tests" / "test_readiness_deep_vertical_contract.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"expected one regex anchor in {path}, found {count}: {pattern[:80]}")
    path.write_text(updated, encoding="utf-8")


def patch_generator() -> None:
    replace_once(
        GEN,
        '''def ep(method="GET", schema=None, sla=None, citations=False,
       allow_statuses=(200,), allow_labels=("live", "cached"),
       lies_if=("mock", "fabricated", "placeholder"), note=""):
    return {
        "method": method,
        "schema": schema,
        "freshnessSLA": sla,
        "citationsRequired": citations,
        "degradedRules": {
            "allowStatuses": list(allow_statuses),
            "allowLabels": list(allow_labels),
            "liesIf": list(lies_if),
        },
        "note": note,
    }
''',
        '''def ep(method="GET", schema=None, sla=None, citations=False,
       allow_statuses=(200,), allow_labels=("live", "cached"),
       lies_if=("mock", "fabricated", "placeholder"),
       citation_waive_paths=(), note=""):
    contract = {
        "method": method,
        "schema": schema,
        "freshnessSLA": sla,
        "citationsRequired": citations,
        "degradedRules": {
            "allowStatuses": list(allow_statuses),
            "allowLabels": list(allow_labels),
            "liesIf": list(lies_if),
        },
        "note": note,
    }
    if citation_waive_paths:
        contract["citationWaiveWhenUnavailablePaths"] = list(citation_waive_paths)
    return contract
''',
    )

    replace_once(
        GEN,
        '''    "/api/a11oy/v1/devb/legal/matter?limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        note="Bounded CourtListener matter probe; returned opinions carry authority URLs."),''',
        '''    "/api/a11oy/v1/devb/legal/matter?limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        allow_labels=("live", "cached", "unavailable"),
        citation_waive_paths=("opinions.freshness.status",),
        note="Bounded CourtListener matter probe; returned opinions carry authority URLs. A timestamped, errored UNAVAILABLE observation is honest degraded evidence, not an uncited live claim."),''',
    )
    replace_once(
        GEN,
        '''    "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        note="Bounded CourtListener authority probe for the defense-builder alias."),''',
        '''    "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        allow_labels=("live", "cached", "unavailable"),
        citation_waive_paths=("opinions.freshness.status",),
        note="Bounded CourtListener authority probe for the defense-builder alias; explicit timestamped UNAVAILABLE remains fail-honest."),''',
    )
    replace_once(
        GEN,
        '''    "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        note="Bounded CourtListener authority probe for the insurance-review alias."),''',
        '''    "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1": ep(
        schema="devb_legal_matter", sla=HOUR, citations=True,
        allow_labels=("live", "cached", "unavailable"),
        citation_waive_paths=("opinions.freshness.status",),
        note="Bounded CourtListener authority probe for the insurance-review alias; explicit timestamped UNAVAILABLE remains fail-honest."),''',
    )
    replace_once(
        GEN,
        '''    "/api/a11oy/v1/devb/legal/exposure?limit=1": ep(
        schema="devb_legal_exposure", sla=HOUR, citations=True,
        note="SEC/CourtListener exposure graph; case nodes retain CourtListener URLs."),''',
        '''    "/api/a11oy/v1/devb/legal/exposure?limit=1": ep(
        schema="devb_legal_exposure", sla=HOUR, citations=True,
        allow_labels=("live", "cached", "unavailable"),
        citation_waive_paths=("freshness.litigation.status",),
        note="SEC/CourtListener exposure graph; case nodes retain CourtListener URLs. A timestamped unavailable litigation source waives only the missing CourtListener citation, never a live/cached claim."),''',
    )
    replace_once(
        GEN,
        '''    # ── readiness (self) ──
    "/api/a11oy/v1/readiness": ep(schema="readiness", sla=5 * MIN),''',
        '''    # ── readiness (self) ──
    "/api/a11oy/v1/readiness": ep(
        schema="readiness", sla=10 * MIN,
        note="Background readiness snapshot. The schema requires stale=false and grades only its explicit checked_at assembly clock; nested source clocks retain their own live/cached/unreachable labels."),''',
    )

    regex_once(
        GEN,
        r'    "devb_legal_matter": \{.*?\n    "devb_legal_regulatory": \{',
        '''    "devb_legal_matter": {
        "anyOf": [
            {
                "type": "object",
                "required": ["surface", "term", "opinions", "doctrine"],
                "properties": {"surface": {"const": "matter"}},
                "requiredPaths": [
                    "opinions.value.items", "opinions.freshness.status",
                    "opinions.freshness.fetched_at",
                ],
                "requiredPathTypes": {
                    "term": "string", "opinions.value.items": "array",
                    "opinions.freshness.status": "string",
                    "opinions.freshness.fetched_at": "timestamp",
                    "doctrine": "object",
                },
                "requiredPathEnums": {
                    "opinions.freshness.status": ["live", "cached"],
                },
            },
            {
                "type": "object",
                "required": ["surface", "term", "opinions", "doctrine"],
                "properties": {"surface": {"const": "matter"}},
                "requiredPaths": [
                    "opinions.value", "opinions.freshness.status",
                    "opinions.freshness.fetched_at", "opinions.freshness.error",
                ],
                "requiredPathTypes": {
                    "term": "string", "opinions.freshness.status": "string",
                    "opinions.freshness.fetched_at": "timestamp",
                    "opinions.freshness.error": "string", "doctrine": "object",
                },
                "requiredPathValues": {
                    "opinions.value": None,
                    "opinions.freshness.status": "unavailable",
                },
            },
        ],
    },
    "devb_legal_regulatory": {''',
    )

    regex_once(
        GEN,
        r'    "devb_legal_exposure": \{.*?\n    "feeds_pulse": \{',
        '''    "devb_legal_exposure": {
        "anyOf": [
            {
                "type": "object",
                "required": ["nodes", "links", "freshness", "note", "doctrine"],
                "requiredPaths": [
                    "freshness.status", "freshness.litigation.status",
                    "freshness.litigation.fetched_at",
                ],
                "requiredPathTypes": {
                    "nodes": "array", "links": "array", "freshness": "object",
                    "freshness.status": "string", "freshness.litigation": "object",
                    "freshness.litigation.status": "string",
                    "freshness.litigation.fetched_at": "timestamp",
                    "note": "string", "doctrine": "object",
                },
                "requiredPathEnums": {
                    "freshness.litigation.status": ["live", "cached"],
                },
            },
            {
                "type": "object",
                "required": ["nodes", "links", "freshness", "note", "doctrine"],
                "requiredPaths": [
                    "freshness.status", "freshness.litigation.status",
                    "freshness.litigation.fetched_at",
                    "freshness.litigation.error",
                ],
                "requiredPathTypes": {
                    "nodes": "array", "links": "array", "freshness": "object",
                    "freshness.status": "string", "freshness.litigation": "object",
                    "freshness.litigation.status": "string",
                    "freshness.litigation.fetched_at": "timestamp",
                    "freshness.litigation.error": "string",
                    "note": "string", "doctrine": "object",
                },
                "requiredPathValues": {
                    "freshness.litigation.status": "unavailable",
                },
            },
        ],
    },
    "feeds_pulse": {''',
    )

    replace_once(
        GEN,
        '    "readiness": {"type": "object", "required": ["sections"]},',
        '''    "readiness": {
        "type": "object",
        "required": ["sections", "checked_at", "stale"],
        "properties": {"stale": {"const": False}},
        "requiredPathTypes": {
            "sections": "array",
            "checked_at": "timestamp",
        },
    },''',
    )


def patch_probe() -> None:
    replace_once(
        PROBE,
        '''function hasCitation(obj, depth = 0) {
  if (!obj || depth > 4) return false;
  if (Array.isArray(obj)) return obj.slice(0, 30).some((v) => hasCitation(v, depth + 1));
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (CITE_KEY.test(k) && v && (typeof v === "string" ? v.length > 0 : true)) return true;
      if (hasCitation(v, depth + 1)) return true;
    }
  }
  return false;
}
''',
        '''function hasCitation(obj, depth = 0) {
  if (!obj || depth > 4) return false;
  if (Array.isArray(obj)) return obj.slice(0, 30).some((v) => hasCitation(v, depth + 1));
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (CITE_KEY.test(k) && v && (typeof v === "string" ? v.length > 0 : true)) return true;
      if (hasCitation(v, depth + 1)) return true;
    }
  }
  return false;
}

function citationWaivedByUnavailable(spec, body) {
  const paths = spec?.citationWaiveWhenUnavailablePaths;
  if (!Array.isArray(paths) || paths.length === 0) return false;
  return paths.every((path) => {
    const candidate = valueAtPath(body, path);
    return candidate.found
      && String(candidate.value || "").trim().toLowerCase() === "unavailable";
  });
}
''',
    )

    replace_once(
        PROBE,
        '''      if (sc.requiredPathTypes && !Object.entries(sc.requiredPathTypes).every(([path, type]) => {
        let cursor = body;
        for (const key of path.split(".")) {
          if (!cursor || typeof cursor !== "object" || !(key in cursor)) return false;
          cursor = cursor[key];
        }
        if (type === "array") return Array.isArray(cursor);
        if (type === "nonempty_array") return Array.isArray(cursor) && cursor.length > 0;
        if (type === "object") {
          return typeof cursor === "object" && cursor !== null && !Array.isArray(cursor);
        }
        if (type === "string") return typeof cursor === "string";
        if (type === "number") return typeof cursor === "number" && Number.isFinite(cursor);
        if (type === "nonnegative_integer") {
          return Number.isSafeInteger(cursor) && cursor >= 0;
        }
        if (type === "boolean") return typeof cursor === "boolean";
        if (type === "timestamp") return toDate(cursor) !== null;
        if (type === "process_epoch_timestamp") {
          return parseStrictUtcTimestamp(cursor) !== null;
        }
        return false;
      })) return false;
      if (sc.anyKey && !sc.anyKey.some((k) => k in body)) return false;''',
        '''      if (sc.requiredPathTypes && !Object.entries(sc.requiredPathTypes).every(([path, type]) => {
        let cursor = body;
        for (const key of path.split(".")) {
          if (!cursor || typeof cursor !== "object" || !(key in cursor)) return false;
          cursor = cursor[key];
        }
        if (type === "array") return Array.isArray(cursor);
        if (type === "nonempty_array") return Array.isArray(cursor) && cursor.length > 0;
        if (type === "object") {
          return typeof cursor === "object" && cursor !== null && !Array.isArray(cursor);
        }
        if (type === "string") return typeof cursor === "string";
        if (type === "number") return typeof cursor === "number" && Number.isFinite(cursor);
        if (type === "nonnegative_integer") {
          return Number.isSafeInteger(cursor) && cursor >= 0;
        }
        if (type === "boolean") return typeof cursor === "boolean";
        if (type === "timestamp") return toDate(cursor) !== null;
        if (type === "process_epoch_timestamp") {
          return parseStrictUtcTimestamp(cursor) !== null;
        }
        return false;
      })) return false;
      if (sc.requiredPathValues && !Object.entries(sc.requiredPathValues).every(([path, expected]) => {
        const candidate = valueAtPath(body, path);
        return candidate.found && Object.is(candidate.value, expected);
      })) return false;
      if (sc.requiredPathEnums && !Object.entries(sc.requiredPathEnums).every(([path, allowed]) => {
        const candidate = valueAtPath(body, path);
        return candidate.found && Array.isArray(allowed) && allowed.includes(candidate.value);
      })) return false;
      if (sc.anyKey && !sc.anyKey.some((k) => k in body)) return false;''',
    )

    replace_once(
        PROBE,
        '''  let citationOk = true;
  if (spec.citationsRequired && statusOk) {
    citationOk = typeof last.body === "string" ? last.body.length > 0 : hasCitation(last.body);
  }
''',
        '''  const citationWaived = spec.citationsRequired && statusOk
    ? citationWaivedByUnavailable(spec, last.body)
    : false;
  let citationOk = true;
  if (spec.citationsRequired && statusOk && !citationWaived) {
    citationOk = typeof last.body === "string" ? last.body.length > 0 : hasCitation(last.body);
  }
''',
    )

    replace_once(
        PROBE,
        '''    samples: lat.length, schemaOk: schema.ok, citationOk,
    labelPolicyOk: labelPolicy.ok,''',
        '''    samples: lat.length, schemaOk: schema.ok, citationOk, citationWaived,
    labelPolicyOk: labelPolicy.ok,''',
    )

    replace_once(
        PROBE,
        '''export {
  boundedIntegerArg,
  evaluateEndpointLabels,''',
        '''export {
  boundedIntegerArg,
  citationWaivedByUnavailable,
  evaluateEndpointLabels,''',
    )


def patch_probe_tests() -> None:
    replace_once(
        PROBE_TEST,
        '''import {
  evaluateEndpointLabels,''',
        '''import {
  citationWaivedByUnavailable,
  evaluateEndpointLabels,''',
    )
    text = PROBE_TEST.read_text(encoding="utf-8")
    marker = 'test("unavailable legal evidence is explicit, typed, and narrowly citation-waived"'
    if marker in text:
        raise RuntimeError("probe regression already installed")
    block = r'''

test("unavailable legal evidence is explicit, typed, and narrowly citation-waived", () => {
  const matterSpec = readinessMatrix.endpoints[
    "/api/a11oy/v1/devb/legal/matter?limit=1"
  ];
  const unavailableMatter = {
    surface: "matter",
    term: "securities",
    opinions: {
      value: null,
      freshness: {
        status: "unavailable",
        fetched_at: "2026-09-01T11:55:00Z",
        error: "ConnectTimeout: CourtListener did not answer",
      },
    },
    doctrine: {},
  };
  assert.equal(validateSchema("devb_legal_matter", unavailableMatter).ok, true);
  assert.equal(citationWaivedByUnavailable(matterSpec, unavailableMatter), true);
  assert.equal(evaluateEndpointLabels(200, matterSpec, unavailableMatter).ok, true);

  const missingError = structuredClone(unavailableMatter);
  delete missingError.opinions.freshness.error;
  assert.equal(validateSchema("devb_legal_matter", missingError).ok, false);

  const fakeLive = structuredClone(unavailableMatter);
  fakeLive.opinions.freshness.status = "live";
  assert.equal(validateSchema("devb_legal_matter", fakeLive).ok, false);
  assert.equal(citationWaivedByUnavailable(matterSpec, fakeLive), false);

  const liveMatter = {
    surface: "matter",
    term: "securities",
    opinions: {
      value: { items: [{ url: "https://www.courtlistener.com/opinion/1/" }] },
      freshness: { status: "live", fetched_at: "2026-09-01T11:55:00Z" },
    },
    doctrine: {},
  };
  assert.equal(validateSchema("devb_legal_matter", liveMatter).ok, true);
  assert.equal(citationWaivedByUnavailable(matterSpec, liveMatter), false);

  const exposureSpec = readinessMatrix.endpoints[
    "/api/a11oy/v1/devb/legal/exposure?limit=1"
  ];
  const unavailableExposure = {
    nodes: [],
    links: [],
    freshness: {
      status: "unavailable",
      litigation: {
        status: "unavailable",
        fetched_at: "2026-09-01T11:55:00Z",
        error: "ConnectTimeout: CourtListener did not answer",
      },
    },
    note: "No case relationship is asserted without CourtListener evidence.",
    doctrine: {},
  };
  assert.equal(validateSchema("devb_legal_exposure", unavailableExposure).ok, true);
  assert.equal(citationWaivedByUnavailable(exposureSpec, unavailableExposure), true);
});

test("readiness snapshot contract follows its explicit stale flag and assembly clock", () => {
  const spec = readinessMatrix.endpoints["/api/a11oy/v1/readiness"];
  const nowMs = Date.parse("2026-09-01T12:00:00Z");
  const current = {
    sections: [],
    checked_at: "2026-09-01T11:52:10Z",
    stale: false,
  };
  assert.equal(validateSchema("readiness", current).ok, true);
  assert.equal(evaluateFreshness(
    "/api/a11oy/v1/readiness", spec, current, nowMs,
  ).freshOk, true);

  const declaredStale = { ...current, stale: true };
  assert.equal(validateSchema("readiness", declaredStale).ok, false);

  const tooOld = { ...current, checked_at: "2026-09-01T11:49:59Z" };
  const staleClock = evaluateFreshness(
    "/api/a11oy/v1/readiness", spec, tooOld, nowMs,
  );
  assert.equal(staleClock.freshOk, false);
  assert.equal(staleClock.ageSec, 601);
});
'''
    PROBE_TEST.write_text(text.rstrip() + block + "\n", encoding="utf-8")


def patch_python_tests() -> None:
    replace_once(
        DEEP_TEST,
        '''        schema = schemas[schema_name]
        assert schema["type"] == "object"
        assert schema.get("required")
        assert schema.get("requiredPathTypes")
''',
        '''        schema = schemas[schema_name]
        variants = schema.get("anyOf") or [schema]
        assert variants
        for variant in variants:
            assert variant["type"] == "object"
            assert variant.get("required")
            assert variant.get("requiredPathTypes")
''',
    )


def main() -> int:
    patch_generator()
    patch_probe()
    patch_probe_tests()
    patch_python_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
