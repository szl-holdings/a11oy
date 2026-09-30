# SPDX-License-Identifier: Apache-2.0
"""BLS-specific missing-value contracts; generic numeric validation stays strict.

Authority: https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm
The official API represents missing CPI values as a dash with an explanatory
footnote. Do not infer, interpolate or replace that absent observation with zero.
"""
import importlib
import pytest

sources = importlib.import_module("verticals.puriq-markets.runtime.sources")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")


def response(value):
    return {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{
        "seriesID": "CUUR0000SA0", "data": [{"year": "2025", "period": "M10",
        "periodName": "October", "value": value, "footnotes": [{"code": "X",
        "text": "Data unavailable due to the 2025 lapse in appropriations."}]}]}]}}


def test_bls_documented_dash_preserves_period_and_footnote_without_fabrication():
    item = sources.normalize("bls-series", response("-"),
        {"series_id": "CUUR0000SA0"}, 1789430400)["items"][0]
    assert item["value"] is None and item["missing_value_marker"] == "-"
    assert item["year"] == "2025" and item["period"] == "M10"
    assert item["footnotes"][0]["code"] == "X"
    assert "lapse in appropriations" in item["footnotes"][0]["text"]


@pytest.mark.parametrize("value", ["0", "-1.5", "315.123"])
def test_bls_zero_negative_and_numeric_values_are_not_missing(value):
    item = sources.normalize("bls-series", response(value),
        {"series_id": "CUUR0000SA0"}, 1789430400)["items"][0]
    assert item["value"] == value and item["missing_value_marker"] is None


@pytest.mark.parametrize("value", ["--", "-(X)", "unknown", "NaN", "Infinity"])
def test_bls_undocumented_invalid_values_still_fail_closed(value):
    with pytest.raises(transport.FinanceError, match="INVALID_SOURCE_NUMBER"):
        sources.normalize("bls-series", response(value), {"series_id": "CUUR0000SA0"}, 1789430400)


def test_generic_financial_numbers_do_not_treat_dash_as_valid_or_missing():
    with pytest.raises(transport.FinanceError, match="INVALID_SOURCE_NUMBER"):
        sources.number("-")
