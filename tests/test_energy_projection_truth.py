"""Fail-closed current-window and field-level provenance regression tests."""

import time

import szl_energy_projection as projection


def _unqualified_operator(**updates):
    raw = {
        "running": True,
        "joules_measured_total": 78_369.586,
        "joules_measured_label": "MEASURED",
        "window_seconds": 3600.0,
        "tokens_total": 120_000,
        "jobs_done": 40,
        "grid_price_eur_mwh": 62.08,
    }
    raw.update(updates)
    return raw


def test_hardcoded_sample_and_arbitrary_hour_never_projected():
    data = projection._extract_window(None, None)
    assert data["joules_measured"] is None
    assert data["historical_reference"]["label"] == "SAMPLE"
    assert data["historical_reference"]["rate_denominator_s"] is None
    result = projection.build_projection(_measured=data)
    assert result["ok"] is False
    assert result["measured_inputs"]["label"] == "UNAVAILABLE"
    assert result["measured_inputs"]["measured_rates_per_hour"]["joules_per_hr"]["value"] is None
    assert result["projection_1day_single_node"]["compute_done"]["joules"]["value"] is None
    assert result["projection_1day_single_node"]["earnings"]["compute_resale_usd"]["value"] is None
    assert result["scale_projection"]["lines"] == []


def test_operator_claim_and_lifetime_ledger_cannot_make_aligned_window():
    ledger = {"totals": {"joules_total": 900_000.0,
                         "tokens_total": 50_000, "jobs_total": 200}}
    unqualified = projection._extract_window(_unqualified_operator(), ledger)
    absent = projection._extract_window(None, ledger)
    for source in (unqualified, absent):
        assert source["qualified_window"] is False
        assert source["joules_measured"] is None
        assert source["tokens_measured"] is None
        assert source["jobs_measured"] is None


def test_attribution_fields_without_verified_window_still_fail_closed():
    op = _unqualified_operator(attribution_verified=True,
                               attribution_method="exclusive-process-counter",
                               attribution_version=1)
    assert projection._extract_window(op, None)["qualified_window"] is False
    end = time.time()
    op.update(measurement_window_verified=True,
              measurement_window_id="window-1",
              measurement_window_start_ts=end - 3600.0,
              measurement_window_end_ts=end)
    qualified = projection._extract_window(op, None)
    assert qualified["qualified_window"] is True
    assert qualified["joules_measured"] == 78_369.586


def test_qualified_energy_does_not_upgrade_unverified_grid_or_counts():
    end = time.time()
    op = _unqualified_operator(
        attribution_verified=True,
        attribution_method="exclusive-process-counter",
        attribution_version=1,
        measurement_window_verified=True,
        measurement_window_id="window-1",
        measurement_window_start_ts=end - 3600.0,
        measurement_window_end_ts=end,
    )
    measured = projection._extract_window(op, None)
    result = projection.build_projection(_measured=measured)
    assert result["ok"] is True
    inputs = result["measured_inputs"]
    assert inputs["label"] == "UNKNOWN"  # mixed provenance, not all MEASURED
    assert inputs["joules_measured"]["label"] == "MEASURED"
    assert inputs["tokens_measured"]["label"] == "REPORTED"
    assert inputs["jobs_measured"]["label"] == "REPORTED"
    assert inputs["grid_price_eur_mwh"]["label"] == "SAMPLE"
    assert result["projection_1day_single_node"]["earnings"]["grid_arbitrage_credit_usd"]["label"] == "ESTIMATE"


def test_missing_live_grid_uses_sample_price_without_measured_label():
    end = time.time()
    op = _unqualified_operator(
        grid_price_eur_mwh=None,
        attribution_verified=True,
        attribution_method="exclusive-process-counter",
        attribution_version=1,
        measurement_window_verified=True,
        measurement_window_id="window-2",
        measurement_window_start_ts=end - 3600.0,
        measurement_window_end_ts=end,
    )
    result = projection.build_projection(_measured=projection._extract_window(op, None))
    assert result["measured_inputs"]["grid_price_eur_mwh"]["value"] == projection._GROUND_TRUTH_GRID_EUR_MWH
    assert result["measured_inputs"]["grid_price_eur_mwh"]["label"] == "SAMPLE"


def test_stale_or_misaligned_window_never_becomes_current_rate():
    end = time.time() - 60.0
    op = _unqualified_operator(
        attribution_verified=True,
        attribution_method="exclusive-process-counter",
        attribution_version=1,
        measurement_window_verified=True,
        measurement_window_id="window-stale",
        measurement_window_start_ts=end - 3600.0,
        measurement_window_end_ts=end,
    )
    assert projection._extract_window(op, None)["qualified_window"] is False
    op["measurement_window_end_ts"] = time.time()
    assert projection._extract_window(op, None)["qualified_window"] is False
