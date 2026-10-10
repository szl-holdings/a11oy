#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure, bounded audit of a caller-supplied annual research panel.

Contract: records (at most 5,000) and an ISO YYYY-MM-DD as_of are required.
Each record has entity, integer period (1..9999), value (finite number or null)
and state (observed/suppressed/missing/invalid). Optional record metadata is
available_at, exclusion_reason, group and source_url. Optional panel controls
are expected_entities (at most 1,000 unique names), paired start_year/end_year,
source_url and specifications (at most 100 supplied robustness estimates).
Year ranges span at most 100 years; the expected grid has at most 10,000 cells.

All duplicate entity-period rows are excluded. Their presence blocks structural
acceptance; other exclusions remain visible without invalidating the audit.
Kept records require an observed numeric value, an in-scope unique key, no
reported exclusion and a supplied release date on or before as_of. Dates and
source URLs are unverified metadata: no date is inferred or source fetched.
Coverage counts unique observed numeric cells before release/exclusion filters;
missing cells include suppressed/invalid/null/ambiguous/absent cells. Raw record
counts, distinct grid cells and point-in-time eligible counts stay separate.

Output contains only JSON-compatible data. Percentages use raw record or stated
grid denominators and are null for zero denominators. Supplied robustness
estimates are REPORTED, never fitted or treated as evidence of causality.
No networking, filesystem writes, dynamic evaluation, signing or trading.
"""

from collections import Counter
from datetime import date
import math
import re
from urllib.parse import urlsplit


SCHEMA = "szl.finance.research-audit/v1"
MAX_RECORDS = 5000
MAX_ENTITIES = 1000
MAX_YEARS = 100
MAX_COVERAGE_CELLS = 10000
MAX_CELL_DETAILS = 1000
MAX_SPECIFICATIONS = 100
SMALL_CLUSTER_THRESHOLD = 30
STATES = ("observed", "suppressed", "missing", "invalid")
PAYLOAD_FIELDS = {"records", "as_of", "expected_entities", "start_year", "end_year",
                  "source_url", "specifications"}
RECORD_FIELDS = {"entity", "period", "value", "state", "available_at",
                 "exclusion_reason", "group", "source_url"}
SPEC_FIELDS = {"label", "estimate", "standard_error", "n", "clusters"}


def _fail(code, location):
    raise ValueError("RESEARCH_" + code + ": " + location)


def _text(value, location, limit=120):
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        _fail("INVALID_TEXT", location)
    return value


def _year(value, location):
    if type(value) is not int or not 1 <= value <= 9999:
        _fail("INVALID_YEAR", location)
    return value


def _date(value, location):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        _fail("INVALID_DATE", location)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail("INVALID_DATE", location)


def _number(value, location):
    if type(value) not in (int, float):
        _fail("INVALID_NUMBER", location)
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        _fail("INVALID_NUMBER", location)
    return value


def _url(value, location):
    _text(value, location, 2048)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ("http", "https") and parsed.hostname
                 and parsed.username is None and parsed.password is None
                 and not any(char.isspace() for char in value))
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        _fail("INVALID_SOURCE_URL", location)
    return value


def _percent(numerator, denominator):
    return round(100 * numerator / denominator, 6) if denominator else None


def _records(raw):
    if not isinstance(raw, list) or len(raw) > MAX_RECORDS:
        _fail("RECORD_LIMIT", "records must be a list of at most 5000 records")
    checked = []
    for index, row in enumerate(raw):
        location = "records[" + str(index) + "]"
        if (not isinstance(row, dict) or set(row) - RECORD_FIELDS
                or not {"entity", "period", "value", "state"} <= set(row)):
            _fail("INVALID_RECORD", location)
        entity = _text(row["entity"], location + ".entity")
        period = _year(row["period"], location + ".period")
        if not isinstance(row["state"], str) or row["state"] not in STATES:
            _fail("INVALID_STATE", location + ".state")
        if row["value"] is not None:
            _number(row["value"], location + ".value")
        for field in ("group", "exclusion_reason"):
            if field in row:
                _text(row[field], location + "." + field, 240 if field == "exclusion_reason" else 120)
        if "available_at" in row:
            _date(row["available_at"], location + ".available_at")
        if "source_url" in row:
            _url(row["source_url"], location + ".source_url")
        checked.append({**row, "entity": entity, "period": period})
    return checked


def _robustness(raw):
    if not isinstance(raw, list) or len(raw) > MAX_SPECIFICATIONS:
        _fail("SPECIFICATION_LIMIT", "specifications must be a list of at most 100 items")
    specifications, flags, labels = [], [], set()
    for index, spec in enumerate(raw):
        location = "specifications[" + str(index) + "]"
        if (not isinstance(spec, dict) or set(spec) - SPEC_FIELDS
                or not {"label", "estimate"} <= set(spec)):
            _fail("INVALID_SPECIFICATION", location)
        label = _text(spec["label"], location + ".label")
        if label in labels:
            _fail("DUPLICATE_SPECIFICATION", location + ".label")
        labels.add(label)
        _number(spec["estimate"], location + ".estimate")
        if "standard_error" in spec:
            if _number(spec["standard_error"], location + ".standard_error") < 0:
                _fail("INVALID_STANDARD_ERROR", location + ".standard_error")
        for field in ("n", "clusters"):
            if field in spec and (type(spec[field]) is not int or not 1 <= spec[field] <= 10**9):
                _fail("INVALID_COUNT", location + "." + field)
        if "n" in spec and "clusters" in spec and spec["clusters"] > spec["n"]:
            _fail("INVALID_COUNT", location + ".clusters exceeds n")
        specifications.append(dict(spec))
        if "clusters" in spec and spec["clusters"] < SMALL_CLUSTER_THRESHOLD:
            flags.append({"code": "SMALL_CLUSTER_COUNT", "label": label,
                          "clusters": spec["clusters"]})
    sign_change = (any(spec["estimate"] < 0 for spec in specifications)
                   and any(spec["estimate"] > 0 for spec in specifications))
    if sign_change:
        flags.insert(0, {"code": "ESTIMATE_SIGN_CHANGE"})
    return {"truth_label": "REPORTED", "computed": False, "externally_verified": False,
            "specifications": specifications, "sign_change": sign_change,
            "small_cluster_threshold": SMALL_CLUSTER_THRESHOLD, "flags": flags,
            "small_cluster_threshold_kind": "HEURISTIC_NOT_VALIDITY_TEST",
            "scope": "Supplied estimates only; no regression, significance or causal inference computed."}


def _attrition(key, rows, audits, values):
    total, kept = Counter(), Counter()
    for row, audit in zip(rows, audits):
        value = row.get(key)
        total[value] += 1
        if audit["eligible"]:
            kept[value] += 1
    return [{key: value, "total_records": total[value], "kept_records": kept[value],
             "excluded_records": total[value] - kept[value],
             "excluded_percent": _percent(total[value] - kept[value], total[value])}
            for value in values]


def audit_research(payload):
    """Audit annual panel records without mutating inputs or consulting a clock."""
    if (not isinstance(payload, dict) or set(payload) - PAYLOAD_FIELDS
            or not {"records", "as_of"} <= set(payload)):
        _fail("INVALID_PAYLOAD", "expected records, as_of and supported optional controls")
    cutoff = _date(payload["as_of"], "as_of")
    rows = _records(payload["records"])
    source_url = _url(payload["source_url"], "source_url") if "source_url" in payload else None
    robustness = _robustness(payload.get("specifications", []))
    submitted_entities = {row["entity"] for row in rows}
    if "expected_entities" in payload:
        raw_entities = payload["expected_entities"]
        if not isinstance(raw_entities, list) or len(raw_entities) > MAX_ENTITIES:
            _fail("ENTITY_LIMIT", "expected_entities must be a list of at most 1000 names")
        checked_entities = [_text(value, "expected_entities") for value in raw_entities]
        entities = set(checked_entities)
        if len(entities) != len(checked_entities):
            _fail("DUPLICATE_ENTITY", "expected_entities")
    else:
        entities = submitted_entities
    if len(entities) > MAX_ENTITIES:
        _fail("ENTITY_LIMIT", "expected grid exceeds 1000 entities")
    if ("start_year" in payload) != ("end_year" in payload):
        _fail("INVALID_YEAR_RANGE", "start_year and end_year must be supplied together")
    if "start_year" in payload:
        start = _year(payload["start_year"], "start_year")
        end = _year(payload["end_year"], "end_year")
        if start > end:
            _fail("INVALID_YEAR_RANGE", "start_year must not exceed end_year")
    else:
        years = [row["period"] for row in rows]
        start, end = (min(years), max(years)) if years else (None, None)
    year_count = end - start + 1 if start is not None else 0
    if year_count > MAX_YEARS or year_count * len(entities) > MAX_COVERAGE_CELLS:
        _fail("COVERAGE_LIMIT", "grid exceeds 100 years or 10000 entity-year cells")

    keys = Counter((row["entity"], row["period"]) for row in rows)
    duplicate_keys = {key for key, count in keys.items() if count > 1}
    state_counts = Counter(row["state"] for row in rows)
    primary_reasons, all_reasons = Counter(), Counter()
    audits, issue_counts = [], Counter()
    for index, row in enumerate(rows):
        reasons = []
        key = row["entity"], row["period"]
        if key in duplicate_keys:
            reasons.append("DUPLICATE_ENTITY_PERIOD")
        if row["entity"] not in entities:
            reasons.append("OUTSIDE_EXPECTED_ENTITIES")
        if start is not None and not start <= row["period"] <= end:
            reasons.append("OUTSIDE_YEAR_RANGE")
        if "exclusion_reason" in row:
            reasons.append("REPORTED_EXCLUSION")
        if row["state"] == "observed" and row["value"] is None:
            reasons.append("OBSERVED_NULL")
        elif row["state"] != "observed":
            reasons.append({"suppressed": "SUPPRESSED_VALUE", "missing": "MISSING_VALUE",
                            "invalid": "INVALID_VALUE"}[row["state"]])
        if row["state"] == "missing" and row["value"] is not None:
            issue_counts["MISSING_STATE_WITH_VALUE"] += 1
        if "available_at" not in row:
            reasons.append("RELEASE_DATE_UNKNOWN")
        elif _date(row["available_at"], "available_at") > cutoff:
            reasons.append("RELEASE_AFTER_AS_OF")
        if reasons:
            primary_reasons[reasons[0]] += 1
            all_reasons.update(reasons)
        audit = {"index": index, "entity": row["entity"], "period": row["period"],
                 "state": row["state"], "eligible": not reasons, "exclusion_reasons": reasons}
        if "exclusion_reason" in row:
            audit["reported_exclusion_reason"] = row["exclusion_reason"]
        audits.append(audit)

    unique_rows = {(row["entity"], row["period"]): (row, audit)
                   for row, audit in zip(rows, audits) if keys[row["entity"], row["period"]] == 1}
    grid, recorded, observed, eligible = [], 0, 0, 0
    for entity in sorted(entities):
        for period in range(start or 1, (end or 0) + 1):
            key = entity, period
            is_recorded = key in keys
            recorded += is_recorded
            if key in duplicate_keys:
                state, is_observed, is_eligible = "duplicate", False, False
            elif key in unique_rows:
                row, audit = unique_rows[key]
                is_observed = row["state"] == "observed" and row["value"] is not None
                state = "observed_null" if row["state"] == "observed" and not is_observed else row["state"]
                is_eligible = audit["eligible"]
            else:
                state, is_observed, is_eligible = "absent", False, False
            observed += is_observed
            eligible += is_eligible
            if len(grid) < MAX_CELL_DETAILS:
                grid.append({"entity": entity, "period": period, "state": state, "eligible": is_eligible})
    expected = year_count * len(entities)
    kept = sum(audit["eligible"] for audit in audits)
    total = len(rows)
    issues = []
    if duplicate_keys:
        issues.append({"code": "DUPLICATE_ENTITY_PERIOD", "severity": "BLOCKING",
                       "count": len(duplicate_keys), "unit": "distinct_entity_periods"})
    for code, count in sorted({**issue_counts, **{key: value for key, value in all_reasons.items()
                                                if key != "DUPLICATE_ENTITY_PERIOD"}}.items()):
        issues.append({"code": code, "severity": "WARNING", "count": count, "unit": "records"})
    return {
        "schema": SCHEMA, "truth_label": "MODELED", "audit_accepted": not duplicate_keys,
        "status": "BLOCKED" if duplicate_keys else "AUDITED", "as_of": payload["as_of"],
        "acceptance_scope": "Structural audit only; acceptance does not establish statistical validity.",
        "inputs": {"origin": "caller_supplied", "truth_label": "SAMPLE",
                   "externally_verified": False, "source_url": source_url,
                   "release_dates_verified": False},
        "summary": {
            "total_records": total, "kept_records": kept, "excluded_records": total - kept,
            "kept_percent": _percent(kept, total), "excluded_percent": _percent(total - kept, total),
            "unique_entity_periods": len(keys), "duplicate_cells": len(duplicate_keys),
            "observed_records": state_counts["observed"], "suppressed_records": state_counts["suppressed"],
            "missing_records": state_counts["missing"], "invalid_records": state_counts["invalid"],
            "null_records": sum(row["value"] is None for row in rows),
            "observed_zero_records": sum(row["state"] == "observed" and row["value"] == 0 for row in rows),
            "kept_zero_records": sum(audit["eligible"] and row["value"] == 0 for row, audit in zip(rows, audits)),
            "unknown_release_records": all_reasons["RELEASE_DATE_UNKNOWN"],
            "after_cutoff_records": all_reasons["RELEASE_AFTER_AS_OF"],
        },
        "exclusion_reasons": [{"reason": reason, "count": count}
                              for reason, count in sorted(primary_reasons.items())],
        "exclusion_reason_scope": "Mutually exclusive first reason per excluded record; all reasons remain in record_audit.",
        "attrition": {
            "entities": _attrition("entity", rows, audits, sorted(submitted_entities | entities)),
            "groups": _attrition("group", rows, audits,
                                 sorted({row.get("group") for row in rows}, key=lambda value: (value is not None, value or ""))),
        },
        "coverage": {
            "expected_cells": expected, "recorded_cells": recorded, "observed_cells": observed,
            "missing_cells": expected - observed, "absent_cells": expected - recorded,
            "eligible_cells": eligible, "coverage_percent": _percent(observed, expected),
            "entities": sorted(entities), "start_year": start, "end_year": end, "cells": grid,
            "cells_truncated": expected > MAX_CELL_DETAILS,
            "scope": "Unique observed numeric cells before release-date and reported-exclusion filters; duplicates are unobserved.",
            "grid_origin": "caller_supplied" if "expected_entities" in payload and "start_year" in payload else "partly_or_fully_inferred",
        },
        "robustness": robustness, "record_audit": audits, "issues": issues,
    }
