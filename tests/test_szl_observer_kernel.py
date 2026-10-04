#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial contracts for the independent, read-only observer kernel."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from szl_observer_kernel import DOMAIN_PROFILES, EvidenceInput, adjudication_bounds, review_series


NOW = datetime(2026, 10, 1, 20, tzinfo=timezone.utc)


def evidence(reading, index, *, domain="cyber", kind="OBSERVATION", **changes):
    item = {"record_id": "event-" + str(index), "domain": domain, "metric": "review-count",
            "unit": "count", "scope": "test-region", "value": reading, "kind": kind,
            "event_at": (NOW - timedelta(seconds=60 - index)).isoformat()}
    item.update(changes)
    payload = json.dumps(item, separators=(",", ":"), allow_nan=False).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return EvidenceInput(payload, "urn:sha256:" + digest, "sha256:" + digest, NOW, kind)


def series(*, domain="cyber", kind="OBSERVATION"):
    return [evidence(value, index, domain=domain, kind=kind)
            for index, value in enumerate((8, 9, 10, 11, 12, 30))]


def review(records, **changes):
    arguments = {"domain": "cyber", "metric": "review-count", "unit": "count",
                 "scope": "test-region", "now": NOW}
    arguments.update(changes)
    return review_series(records, **arguments)


@pytest.mark.parametrize("domain", DOMAIN_PROFILES)
def test_all_seven_domains_share_evidence_contract_without_authority(domain):
    result = review(series(domain=domain), domain=domain)
    assert result["status"] == "RANKED"
    assert result["score"] == pytest.approx(20 / 1.4826)
    assert result["priority"] == "REVIEW_REQUIRED"
    assert result["label"] == "SNAPSHOT"
    assert result["probability"] is None
    assert result["source_authenticity"] == "NOT_VERIFIED"
    assert result["scientific_validation"] == "NOT_EVALUATED"
    assert result["external_writes"] == "DISABLED"
    assert len(result["evidence"]) == 6


def test_simulation_cannot_be_promoted_or_mixed():
    assert review(series(kind="SIMULATION"))["label"] == "SAMPLE"
    rows = series(); rows[-1] = evidence(30, 5, kind="SIMULATION")
    assert review(rows)["reason"] == "MIXED_SIMULATION_AND_OBSERVATION"


def test_identical_simulation_bytes_cannot_be_rewrapped_as_observations():
    rows = series(kind="SIMULATION")
    promoted = [replace(row, kind="OBSERVATION") for row in rows]
    defaulted = [EvidenceInput(row.payload, row.evidence_uri, row.evidence_digest, row.retrieved_at)
                 for row in rows]
    assert review(promoted)["reason"] == "DATA_KIND_BINDING_CONFLICT"
    assert review(defaulted)["reason"] == "DATA_KIND_BINDING_CONFLICT"


def test_even_integer_baseline_retains_exact_precision_above_float_integer_range():
    base = 2**53
    rows = [evidence(base + delta, index) for index, delta in enumerate((0, 1, 2, 3, 4, 5, 10))]
    result = review(rows)
    assert result["status"] == "RANKED"
    assert result["score"] == pytest.approx(5 / 1.4826)
    assert result["priority"] == "REVIEW_REQUIRED"
    assert result["baseline_median_exact"] == {"numerator": str(2 * base + 5), "denominator": "2"}
    assert result["baseline_mad_exact"] == {"numerator": "3", "denominator": "2"}
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("changes", [
    {"evidence_uri": "https://example.org/unpinned"}, {"evidence_digest": ""},
    {"evidence_uri": ""}, {"evidence_digest": "sha256:" + "A" * 64},
    {"payload": b"modified"}, {"payload": b"x" * 4097},
    {"retrieved_at": NOW + timedelta(seconds=1)},
    {"retrieved_at": NOW.replace(tzinfo=None)}, {"kind": "MEASURED"}, {"kind": []},
])
def test_binding_limits_and_clocks_fail_closed(changes):
    rows = series(); rows[-1] = replace(rows[-1], **changes)
    result = review(rows)
    assert result["status"] == "HOLD"
    assert result["score"] is None
    assert result["decision"] == "REVIEW_ONLY"


@pytest.mark.parametrize("changes", [
    {"value": True}, {"value": "30"}, {"value": None}, {"value": 10**101},
    {"scope": "another-region"}, {"unit": "seconds"}, {"metric": "another-metric"},
    {"domain": "seismic"}, {"record_id": ""}, {"extra": "not-in-schema"},
    {"event_at": "invalid"}, {"event_at": NOW.replace(tzinfo=None).isoformat()},
    {"event_at": (NOW + timedelta(seconds=1)).isoformat()},
])
def test_exact_payload_semantics_are_bound_and_invalid_values_abstain(changes):
    rows = series(); rows[-1] = evidence(30, 5, **changes)
    assert review(rows)["status"] == "HOLD"


@pytest.mark.parametrize("payload", [b'{"value":NaN}', b'{"value":Infinity}',
                                       b'{"value":1,"value":2}', b'[]', b'\xff'])
def test_malicious_json_rejected_even_with_matching_digest(payload):
    digest = hashlib.sha256(payload).hexdigest()
    rows = series()
    rows[-1] = EvidenceInput(payload, "urn:sha256:" + digest, "sha256:" + digest, NOW)
    assert review(rows)["status"] == "HOLD"


def test_retrieval_does_not_freshen_old_source_and_history_is_not_silently_dropped():
    rows = series()
    rows[0] = evidence(8, 0, event_at=(NOW - timedelta(seconds=901)).isoformat())
    assert review(rows)["reason"] == "STALE_SOURCE"
    assert review(series(), now=NOW + timedelta(seconds=901))["reason"] == "STALE_SOURCE"


def test_duplicate_ids_or_clocks_are_not_extra_baseline_evidence():
    rows = series(); rows[-1] = evidence(30, 5, record_id="event-0")
    assert review(rows)["reason"] == "DUPLICATE_RECORD_OR_CLOCK"
    rows = series(); rows[-1] = evidence(30, 5, event_at=(NOW - timedelta(seconds=60)).isoformat())
    assert review(rows)["reason"] == "DUPLICATE_RECORD_OR_CLOCK"


def test_latest_is_selected_by_event_time_and_baseline_excludes_it():
    rows = series()
    assert review(list(reversed(rows))) == review(rows)
    assert review(rows)["baseline_median"] == 10
    assert review(rows)["history_count"] == 5


def test_constant_baseline_is_not_perfect_confidence():
    rows = [evidence(10, index) for index in range(6)]
    assert review(rows)["reason"] == "CONSTANT_BASELINE"


def test_nonzero_deviation_cannot_underflow_to_an_exact_zero_score():
    rows = [evidence(value, index) for index, value in enumerate((-1e100, -1e100, 0, 1e100, 1e100, 5e-324))]
    assert review(rows)["reason"] == "NUMERIC_LIMIT"


@pytest.mark.parametrize("changes", [{"domain": "unknown"}, {"domain": []}, {"metric": ""},
                                    {"scope": "unsafe scope"}, {"max_age_seconds": True},
                                    {"max_age_seconds": 0}, {"max_age_seconds": 86401},
                                    {"now": NOW.replace(tzinfo=None)}])
def test_policy_and_clock_cannot_be_downgraded(changes):
    assert review(series(), **changes)["status"] == "HOLD"


def test_input_is_bounded_and_pure():
    rows = series()
    before = tuple(rows)
    assert review(rows[:5])["status"] == "HOLD"
    assert review(rows * 43)["status"] == "HOLD"
    assert review(iter(rows))["status"] == "HOLD"
    review(rows)
    assert tuple(rows) == before


def test_unresolved_evidence_stays_visible():
    result = adjudication_bounds(139, 25, 36)
    assert result["bounds"] == [139 / 200, 175 / 200]
    assert result["unresolved"] == 36
    assert "NOT_CONFIDENCE_INTERVAL" in result["kind"]


@pytest.mark.parametrize("counts", [(0, 0, 0), (-1, 1, 1), (True, 1, 1),
                                   (1.0, 1, 1), (1000001, 0, 0)])
def test_invalid_or_empty_reviews_never_become_zero_risk(counts):
    assert adjudication_bounds(*counts)["status"] == "HOLD"
