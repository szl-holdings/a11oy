#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Independent panel fixtures for deterministic research-audit boundaries."""

from copy import deepcopy
import importlib
import json

import pytest


research = importlib.import_module("verticals.puriq-markets.runtime.research")


def row(entity="A", period=2020, value=1, state="observed", **metadata):
    return {"entity": entity, "period": period, "value": value, "state": state,
            "available_at": "2021-03-01", **metadata}


def audit(records, **controls):
    return research.audit_research({"records": records, "as_of": "2021-03-01", **controls})


def test_suppressed_placeholder_never_becomes_observed_zero():
    result = audit([row(value=0), row("B", value=0, state="suppressed"),
                    row("C", value=None, state="missing"), row("D", value=None, state="invalid"),
                    row("E", value=None)])
    counts = result["summary"]
    assert (counts["total_records"], counts["kept_records"], counts["excluded_records"]) == (5, 1, 4)
    assert counts["observed_zero_records"] == counts["kept_zero_records"] == 1
    assert counts["suppressed_records"] == counts["missing_records"] == counts["invalid_records"] == 1
    assert counts["null_records"] == 3
    assert result["record_audit"][1]["exclusion_reasons"] == ["SUPPRESSED_VALUE"]
    assert result["record_audit"][4]["exclusion_reasons"] == ["OBSERVED_NULL"]
    assert result["coverage"]["observed_cells"] == 1
    assert result["coverage"]["missing_cells"] == 4
    assert result["coverage"]["absent_cells"] == 0


def test_release_cutoff_is_inclusive_and_unknown_dates_are_never_imputed():
    unknown = row("D")
    del unknown["available_at"]
    result = audit([row(), row("B", available_at="2021-03-02"),
                    row("C", available_at="2021-02-28"), unknown])
    assert result["summary"]["kept_records"] == 2
    assert result["summary"]["after_cutoff_records"] == 1
    assert result["summary"]["unknown_release_records"] == 1
    assert result["record_audit"][3]["exclusion_reasons"] == ["RELEASE_DATE_UNKNOWN"]
    assert result["coverage"]["observed_cells"] == 4
    assert result["coverage"]["eligible_cells"] == 2
    assert result["inputs"]["release_dates_verified"] is False


def test_all_duplicate_rows_are_excluded_without_an_arbitrary_winner():
    result = audit([row(value=12), row(value=99), row("B", value=3)])
    assert result["audit_accepted"] is False and result["status"] == "BLOCKED"
    assert result["summary"]["kept_records"] == 1
    assert result["summary"]["excluded_records"] == 2
    assert result["summary"]["unique_entity_periods"] == 2
    assert result["summary"]["duplicate_cells"] == 1
    assert result["coverage"]["recorded_cells"] == 2
    assert result["coverage"]["observed_cells"] == 1
    assert result["coverage"]["cells"][0]["state"] == "duplicate"
    assert result["issues"][0] == {"code": "DUPLICATE_ENTITY_PERIOD", "severity": "BLOCKING",
                                    "count": 1, "unit": "distinct_entity_periods"}


def test_same_entity_in_other_year_is_a_distinct_cell():
    result = audit([row(), row(period=2019)])
    assert result["audit_accepted"] is True and result["status"] == "AUDITED"
    assert result["summary"]["kept_records"] == 2
    assert result["coverage"]["expected_cells"] == 2


def test_attrition_uses_raw_record_denominators_and_declared_empty_entities():
    result = audit([row(group="small"), row(period=2019, group="small", state="suppressed", value=None),
                    row("B", group="large", exclusion_reason="No index")],
                   expected_entities=["A", "B", "C"])
    entities = {entry["entity"]: entry for entry in result["attrition"]["entities"]}
    groups = {entry["group"]: entry for entry in result["attrition"]["groups"]}
    assert entities["A"]["excluded_percent"] == 50
    assert entities["B"]["excluded_percent"] == 100
    assert entities["C"]["total_records"] == 0
    assert entities["C"]["excluded_percent"] is None
    assert groups["small"]["excluded_percent"] == 50
    assert groups["large"]["excluded_percent"] == 100
    assert result["record_audit"][2]["reported_exclusion_reason"] == "No index"
    assert sum(item["count"] for item in result["exclusion_reasons"]) == 2


def test_grid_scope_distinguishes_absence_from_suppression_and_unknown_release():
    unknown = row("B", period=2020)
    del unknown["available_at"]
    result = audit([row(), row("A", 2019, value=None, state="suppressed"), unknown,
                    row("OUTSIDE"), row("A", 2018)],
                   expected_entities=["A", "B"], start_year=2019, end_year=2020)
    coverage = result["coverage"]
    assert coverage["expected_cells"] == 4
    assert coverage["recorded_cells"] == 3
    assert coverage["observed_cells"] == 2
    assert coverage["missing_cells"] == 2
    assert coverage["absent_cells"] == 1
    assert coverage["eligible_cells"] == 1
    assert coverage["coverage_percent"] == 50
    assert coverage["grid_origin"] == "caller_supplied"
    assert "OUTSIDE_EXPECTED_ENTITIES" in result["record_audit"][3]["exclusion_reasons"]
    assert "OUTSIDE_YEAR_RANGE" in result["record_audit"][4]["exclusion_reasons"]


def test_empty_panel_and_empty_scope_do_not_invent_percentage_denominators():
    result = audit([])
    assert result["summary"]["kept_percent"] is None
    assert result["summary"]["excluded_percent"] is None
    assert result["coverage"]["coverage_percent"] is None
    assert result["coverage"]["cells"] == []
    assert audit([], expected_entities=["A"], start_year=2020, end_year=2021)["coverage"]["absent_cells"] == 2
    empty_scope = audit([row()], expected_entities=[])
    assert empty_scope["coverage"]["expected_cells"] == 0
    assert empty_scope["summary"]["kept_records"] == 0


def test_robustness_reports_supplied_values_and_flags_sign_and_small_clusters():
    specs = [{"label": "Base", "estimate": -.127, "standard_error": .04, "n": 96, "clusters": 4},
             {"label": "Trend", "estimate": .19, "clusters": 30},
             {"label": "Zero", "estimate": 0}]
    result = audit([row(value=-5)], specifications=specs)["robustness"]
    assert result["specifications"] == specs
    assert result["truth_label"] == "REPORTED" and result["computed"] is False
    assert result["externally_verified"] is False and result["sign_change"] is True
    assert result["flags"] == [{"code": "ESTIMATE_SIGN_CHANGE"},
                               {"code": "SMALL_CLUSTER_COUNT", "label": "Base", "clusters": 4}]
    assert audit([], specifications=[{"label": "negative", "estimate": -1},
                                     {"label": "zero", "estimate": 0}])["robustness"]["sign_change"] is False


def test_multiple_exclusions_remain_visible_without_double_counting():
    missing_release = row(state="suppressed", exclusion_reason="Source coverage", value=0)
    del missing_release["available_at"]
    result = audit([missing_release])
    assert result["exclusion_reasons"] == [{"reason": "REPORTED_EXCLUSION", "count": 1}]
    assert result["record_audit"][0]["exclusion_reasons"] == [
        "REPORTED_EXCLUSION", "SUPPRESSED_VALUE", "RELEASE_DATE_UNKNOWN"]
    assert result["summary"]["excluded_records"] == 1


def test_missing_state_with_numeric_value_remains_excluded_and_flagged():
    result = audit([row(value=5, state="missing")])
    assert result["summary"]["kept_records"] == 0
    assert any(item["code"] == "MISSING_STATE_WITH_VALUE" for item in result["issues"])


def test_result_is_repeatable_json_and_does_not_mutate_input():
    payload = {"records": [row(source_url="https://example.org/data")], "as_of": "2021-03-01",
               "source_url": "http://example.org/method", "specifications": [{"label": "A", "estimate": 1}]}
    before = deepcopy(payload)
    first = research.audit_research(payload)
    assert first == research.audit_research(payload)
    assert payload == before
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    assert first["truth_label"] == "MODELED" and first["inputs"]["truth_label"] == "SAMPLE"
    assert first["inputs"]["externally_verified"] is False
    first["robustness"]["specifications"][0]["estimate"] = 100
    assert payload == before


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf"), -float("inf"), 10**1000, [], {}])
def test_non_finite_non_numeric_and_boolean_values_are_rejected(value):
    with pytest.raises(ValueError, match="^RESEARCH_INVALID_NUMBER:"):
        audit([row(value=value)])


@pytest.mark.parametrize("change,code", [
    ({"entity": ""}, "INVALID_TEXT"), ({"entity": " A "}, "INVALID_TEXT"),
    ({"entity": "A\nB"}, "INVALID_TEXT"), ({"entity": "A" * 121}, "INVALID_TEXT"),
    ({"period": True}, "INVALID_YEAR"), ({"period": 2020.0}, "INVALID_YEAR"),
    ({"period": 10000}, "INVALID_YEAR"), ({"state": "unknown"}, "INVALID_STATE"),
    ({"state": []}, "INVALID_STATE"), ({"available_at": None}, "INVALID_DATE"),
    ({"available_at": "2021-02-29"}, "INVALID_DATE"),
    ({"available_at": "2021-03-01T00:00:00Z"}, "INVALID_DATE"),
    ({"source_url": "javascript:alert(1)"}, "INVALID_SOURCE_URL"),
    ({"source_url": "https://user:password@example.org"}, "INVALID_SOURCE_URL"),
    ({"source_url": "https://example.org:bad"}, "INVALID_SOURCE_URL"),
    ({"source_url": "https://example.org/a b"}, "INVALID_SOURCE_URL"),
    ({"unknown": 1}, "INVALID_RECORD"), ({"group": None}, "INVALID_TEXT"),
])
def test_malformed_records_raise_coded_value_errors(change, code):
    with pytest.raises(ValueError, match="^RESEARCH_" + code + ":"):
        audit([{**row(), **change}])


@pytest.mark.parametrize("controls,code", [
    ({"start_year": 2020}, "INVALID_YEAR_RANGE"),
    ({"start_year": 2021, "end_year": 2020}, "INVALID_YEAR_RANGE"),
    ({"start_year": 1900, "end_year": 2000}, "COVERAGE_LIMIT"),
    ({"expected_entities": ["A", "A"]}, "DUPLICATE_ENTITY"),
    ({"expected_entities": "A"}, "ENTITY_LIMIT"),
    ({"expected_entities": ["A"] * 1001}, "ENTITY_LIMIT"),
    ({"specifications": [{"label": "A", "estimate": 1, "standard_error": -1}]}, "INVALID_STANDARD_ERROR"),
    ({"specifications": [{"label": "A", "estimate": 1, "n": True}]}, "INVALID_COUNT"),
    ({"specifications": [{"label": "A", "estimate": 1, "clusters": 0}]}, "INVALID_COUNT"),
    ({"specifications": [{"label": "A", "estimate": 1, "n": 2, "clusters": 3}]}, "INVALID_COUNT"),
    ({"specifications": [{"label": "A", "estimate": 1}] * 2}, "DUPLICATE_SPECIFICATION"),
    ({"specifications": [{"label": "A", "estimate": 1}] * 101}, "SPECIFICATION_LIMIT"),
    ({"specifications": [{"label": "A"}]}, "INVALID_SPECIFICATION"),
    ({"unknown": 1}, "INVALID_PAYLOAD"),
])
def test_invalid_controls_and_specifications_are_bounded(controls, code):
    with pytest.raises(ValueError, match="^RESEARCH_" + code + ":"):
        audit([row()], **controls)


@pytest.mark.parametrize("payload", [None, [], {}, {"records": []}, {"as_of": "2021-03-01"}])
def test_required_contract_is_validated(payload):
    with pytest.raises(ValueError, match="^RESEARCH_INVALID_PAYLOAD:"):
        research.audit_research(payload)


def test_record_and_coverage_limits_and_truncated_detail_are_explicit():
    with pytest.raises(ValueError, match="^RESEARCH_RECORD_LIMIT:"):
        audit([row()] * 5001)
    with pytest.raises(ValueError, match="^RESEARCH_COVERAGE_LIMIT:"):
        audit([], expected_entities=[str(i) for i in range(101)], start_year=1900, end_year=1999)
    with pytest.raises(ValueError, match="^RESEARCH_COVERAGE_LIMIT:"):
        audit([row(period=1800), row(period=2020)])
    with pytest.raises(ValueError, match="^RESEARCH_ENTITY_LIMIT:"):
        audit([row(str(i)) for i in range(1001)])
    at_limit = audit([row(str(entity), year) for entity in range(50) for year in range(1900, 2000)])
    assert at_limit["summary"]["total_records"] == at_limit["summary"]["kept_records"] == 5000
    assert at_limit["coverage"]["expected_cells"] == 5000
    assert at_limit["coverage"]["cells_truncated"] is True
    assert len(at_limit["coverage"]["cells"]) == 1000


def test_absent_group_is_not_conflated_with_a_named_group():
    result = audit([row(), row("B", group="UNGROUPED")])
    assert [group["group"] for group in result["attrition"]["groups"]] == [None, "UNGROUPED"]


def test_extreme_finite_numbers_and_year_bounds_remain_json_safe():
    result = audit([row(value=1e308), row("B", value=-1e308)], specifications=[
        {"label": "positive", "estimate": 1e308, "standard_error": 1e308},
        {"label": "negative", "estimate": -1e308},
    ])
    assert result["summary"]["kept_records"] == 2
    assert result["robustness"]["sign_change"] is True
    json.dumps(result, allow_nan=False)
    assert audit([row(period=1)])["coverage"]["expected_cells"] == 1
    assert audit([row(period=9999)])["coverage"]["expected_cells"] == 1
    largest_grid = audit([], expected_entities=[str(i) for i in range(100)],
                         start_year=9900, end_year=9999)["coverage"]
    assert largest_grid["expected_cells"] == largest_grid["absent_cells"] == 10000
    assert len(largest_grid["cells"]) == 1000 and largest_grid["cells_truncated"] is True
