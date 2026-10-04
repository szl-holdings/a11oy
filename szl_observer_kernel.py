#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only, evidence-bound signal review (services/provenance).

This pure kernel does not fetch, sign, store, forecast, train, or execute actions.
Content binding is not source authenticity or scientific validation. Median/MAD
is descriptive ranking, not a calibrated probability or a locked SZL formula.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import re
from statistics import median
from types import MappingProxyType


DOMAIN_PROFILES = MappingProxyType({
    "cyber": ("Detection and recovery evidence", "No autonomous containment"),
    "finance": ("Data vintage and scenario review", "No trading or credit decision"),
    "data-governance": ("Lineage and data-quality review", "No consent or compliance certification"),
    "enterprise": ("Service and incident evidence", "No deployment or restart"),
    "real-estate": ("Dated asset and exposure evidence", "No structural safety assessment"),
    "law": ("Dated source and jurisdiction review", "No legal determination"),
    "seismic": ("Catalogue and detection review", "No earthquake prediction or safety alert"),
})
_KEYS = frozenset({"record_id", "domain", "metric", "unit", "scope", "value", "event_at", "kind"})
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_DIGEST = re.compile(r"sha256:([0-9a-f]{64})\Z")
MAX_RECORDS = 256
MAX_PAYLOAD_BYTES = 4096


@dataclass(frozen=True)
class EvidenceInput:
    """Exact imported bytes plus a content-addressed reference; never a credential."""

    payload: bytes
    evidence_uri: str
    evidence_digest: str
    retrieved_at: datetime
    kind: str = "OBSERVATION"


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware clock required")
    return value.astimezone(timezone.utc)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON constant")


def _held(reason):
    return {
        "status": "HOLD", "reason": reason, "score": None,
        "label": "UNAVAILABLE", "decision": "REVIEW_ONLY",
        "source_authenticity": "NOT_VERIFIED", "scientific_validation": "NOT_EVALUATED",
        "external_writes": "DISABLED", "probability": None,
    }


def review_series(records, *, domain, metric, unit, scope, now, max_age_seconds=900):
    """Rank a single scoped numeric series, failing closed on any invalid input.

    Integration must supply its own UTC wall clock, not an imported document's
    generated_at value. Every baseline and current sample must be fresh and
    evidence-bound. Simulations cannot silently become observation baselines.
    """
    if not isinstance(domain, str) or domain not in DOMAIN_PROFILES or not all(
        isinstance(v, str) and _TOKEN.fullmatch(v) for v in (metric, unit, scope)
    ):
        return _held("INVALID_SCOPE")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        return _held("INVALID_FRESHNESS_POLICY")
    try:
        clock = _utc(now)
    except (ValueError, OverflowError):
        return _held("INVALID_CLOCK")
    if not isinstance(records, (list, tuple)) or not 6 <= len(records) <= MAX_RECORDS:
        return _held("INSUFFICIENT_OR_UNBOUNDED_SERIES")
    parsed = []
    ids = set()
    times = set()
    kinds = set()
    for record in records:
        if not isinstance(record, EvidenceInput):
            return _held("INVALID_RECORD")
        if not isinstance(record.payload, bytes) or not 1 <= len(record.payload) <= MAX_PAYLOAD_BYTES:
            return _held("UNBOUNDED_PAYLOAD")
        match = _DIGEST.fullmatch(record.evidence_digest) if isinstance(record.evidence_digest, str) else None
        if not match or record.evidence_uri != "urn:sha256:" + match.group(1):
            return _held("MISSING_OR_INVALID_BINDING")
        if hashlib.sha256(record.payload).hexdigest() != match.group(1):
            return _held("DIGEST_MISMATCH")
        if not isinstance(record.kind, str) or record.kind not in {"OBSERVATION", "SIMULATION"}:
            return _held("INVALID_DATA_KIND")
        kinds.add(record.kind)
        try:
            item = json.loads(record.payload.decode("utf-8"), object_pairs_hook=_object,
                              parse_constant=_reject_constant)
            if not isinstance(item, dict) or set(item) != _KEYS:
                return _held("INVALID_SCHEMA")
            if item["kind"] != record.kind:
                return _held("DATA_KIND_BINDING_CONFLICT")
            if not isinstance(item["record_id"], str) or not _TOKEN.fullmatch(item["record_id"]):
                return _held("INVALID_RECORD_ID")
            if (item["domain"], item["metric"], item["unit"], item["scope"]) != (domain, metric, unit, scope):
                return _held("INCOMPATIBLE_SERIES")
            if type(item["value"]) not in {int, float} or not math.isfinite(item["value"]) or abs(item["value"]) > 1e100:
                return _held("INVALID_NUMERIC_VALUE")
            if not isinstance(item["event_at"], str):
                return _held("INVALID_CLOCK")
            event_at = _utc(datetime.fromisoformat(item["event_at"].replace("Z", "+00:00")))
            retrieved = _utc(record.retrieved_at)
        except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
            return _held("INVALID_SCHEMA_OR_CLOCK")
        if event_at > retrieved or retrieved > clock:
            return _held("FUTURE_OR_INVERTED_CLOCK")
        if (clock - event_at).total_seconds() > max_age_seconds:
            return _held("STALE_SOURCE")
        if item["record_id"] in ids or event_at in times:
            return _held("DUPLICATE_RECORD_OR_CLOCK")
        ids.add(item["record_id"])
        times.add(event_at)
        parsed.append((event_at, item, record))
    if len(kinds) != 1:
        return _held("MIXED_SIMULATION_AND_OBSERVATION")
    parsed.sort(key=lambda row: row[0])
    history = [Fraction(row[1]["value"]) for row in parsed[:-1]]
    current = parsed[-1][1]["value"]
    center = median(history)
    mad = median(abs(value - center) for value in history)
    if mad == 0:
        return _held("CONSTANT_BASELINE")
    deviation = abs(Fraction(current) - center)
    try:
        score = float(deviation / mad) / 1.4826
        displayed_center, displayed_mad = float(center), float(mad)
    except (OverflowError, ZeroDivisionError):
        return _held("NUMERIC_LIMIT")
    if displayed_mad == 0 or (deviation != 0 and score == 0):
        return _held("NUMERIC_LIMIT")
    if not math.isfinite(score):
        return _held("NUMERIC_LIMIT")
    return {
        "status": "RANKED", "reason": "DESCRIPTIVE_RANK_ONLY", "score": score,
        "label": "SAMPLE" if kinds == {"SIMULATION"} else "SNAPSHOT",
        "decision": "REVIEW_ONLY", "priority": "REVIEW_REQUIRED" if score >= 3 else "NO_RANK_ALERT",
        "domain": domain, "metric": metric, "unit": unit, "scope": scope,
        "baseline_median": displayed_center, "baseline_mad": displayed_mad,
        "baseline_median_exact": {"numerator": str(center.numerator), "denominator": str(center.denominator)},
        "baseline_mad_exact": {"numerator": str(mad.numerator), "denominator": str(mad.denominator)},
        "history_count": len(history),
        "current_value": current, "event_at": parsed[-1][0].isoformat(),
        "evaluated_at": clock.isoformat(),
        "evidence": [{"evidence_uri": row[2].evidence_uri,
                      "evidence_digest": row[2].evidence_digest} for row in parsed],
        "source_authenticity": "NOT_VERIFIED", "scientific_validation": "NOT_EVALUATED",
        "external_writes": "DISABLED", "probability": None,
    }


def adjudication_bounds(confirmed, rejected, unresolved):
    """Unweighted adjudication bracket, not a confidence interval or truth rate.

    For a stratified/weighted sample use a separately validated design-weighted
    estimator; this count-based primitive must not silently stand in for one.
    """
    counts = (confirmed, rejected, unresolved)
    if any(type(value) is not int or not 0 <= value <= 1000000 for value in counts):
        return {"status": "HOLD", "reason": "INVALID_COUNTS", "bounds": None}
    total = sum(counts)
    if total == 0:
        return {"status": "HOLD", "reason": "NO_REVIEWS", "bounds": None}
    return {"status": "DESCRIPTIVE", "bounds": [confirmed / total, (confirmed + unresolved) / total],
            "total": total, "unresolved": unresolved, "kind": "ADJUDICATION_BRACKET_NOT_CONFIDENCE_INTERVAL"}
