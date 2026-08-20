# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_energy_projection.py — guards the honest 1-day + scale projection engine.

Doctrine v11 (the whole point — this is the module most at risk of dishonest numbers):
  - A projection is exactly measured_rate × time (re-derivable, EXACT).
  - Every projected DOLLAR is labeled MODELED or ESTIMATE — NEVER MEASURED. A grep of
    the projected blocks FAILS the build if a projected revenue carries MEASURED.
  - The FLOPs formula string (tokens × model_params × 2) is present and re-derivable.
  - The scale lines (1/3/10/100/1000) DERIVE from the single-node measured rate
    (n-node line == n × single-node line).

Run: python test_energy_projection.py   (also collectable by pytest)
"""
from __future__ import annotations

import json

import szl_energy_projection as P

# A fixed, injected MEASURED window makes every projection deterministic + exact.
# 1-hour window → daily extrapolation is exactly ×24.
MEASURED = {
    "measured_source": "test:injected",
    "joules_measured": 78_369.586,
    "window_seconds": 3600.0,
    "tokens_measured": 120_000.0,
    "jobs_measured": 40.0,
    "power_w_sample": 9.74,
    "grid_price_eur_mwh": -2.90,
    "node": "betterwithage",
    "all_measured": True,
}


def _proj():
    return P.build_projection(window="running", _measured=MEASURED)


def test_projection_is_exactly_rate_times_time():
    """projection == measured_rate × time (EXACT, re-derivable)."""
    p = _proj()
    cd = p["projection_1day_single_node"]["compute_done"]
    # joules/day = joules × (86400 / window_s) = joules × 24 for a 1h window
    assert abs(cd["joules"]["value"] - 78_369.586 * 24.0) < 1e-6
    assert abs(cd["tokens"]["value"] - 120_000.0 * 24.0) < 1e-6
    assert abs(cd["jobs"]["value"] - 40.0 * 24.0) < 1e-6


def test_projection_scales_with_window_length():
    """A 2h window must yield exactly half the daily factor of a 1h window."""
    m2 = dict(MEASURED, window_seconds=7200.0)  # 2h → daily = ×12
    p2 = P.build_projection(_measured=m2)
    j = p2["projection_1day_single_node"]["compute_done"]["joules"]["value"]
    assert abs(j - 78_369.586 * 12.0) < 1e-6


def test_flops_formula_present_and_rederivable():
    """FLOPs formula string present; value == tokens/day × params × 2."""
    p = _proj()
    flops = p["projection_1day_single_node"]["compute_done"]["flops"]
    assert flops["formula"] == "FLOPs = tokens × model_params × 2"
    assert flops["formula"] == P.FLOP_FORMULA
    assert "2" in flops["formula"] and "model_params" in flops["formula"]
    tokens_day = 120_000.0 * 24.0
    expected = tokens_day * P.DEFAULT_MODEL_PARAMS * 2.0
    assert abs(flops["value"] - expected) < 1.0
    # citation to the standard inference FLOP estimate is present
    assert "2N" in flops["citation"] or "2 FLOPs" in flops["citation"]


def test_top_level_flop_estimate_block_present():
    p = _proj()
    fe = p["flop_estimate"]
    assert fe["formula"] == P.FLOP_FORMULA
    assert fe["flops_per_param_per_token"] == 2.0
    assert fe["model_params"] == P.DEFAULT_MODEL_PARAMS


def test_every_projected_dollar_labeled_modeled_or_estimate():
    """Projected dollars must be MODELED or ESTIMATE — never MEASURED."""
    p = _proj()
    earn = p["projection_1day_single_node"]["earnings"]
    assert earn["compute_resale_usd"]["label"] == P.ESTIMATE
    assert earn["grid_arbitrage_credit_usd"]["label"] == P.MODELED
    assert earn["total_usd"]["label"] == P.MODELED
    for line in p["scale_projection"]["lines"]:
        assert line["compute_resale_usd_yr"]["label"] == P.ESTIMATE
        assert line["grid_arbitrage_usd_yr"]["label"] == P.MODELED
        assert line["total_usd_yr"]["label"] == P.MODELED


def test_grep_no_measured_label_in_any_projected_block():
    """Build FAILS if a projected revenue/value is labeled MEASURED.

    The measured_inputs block legitimately carries MEASURED (those are observations).
    But NOTHING inside the projected blocks may claim MEASURED.
    """
    p = _proj()
    for path in ("projection_1day_single_node", "scale_projection"):
        blob = json.dumps(p[path])
        assert P.MEASURED not in blob, (
            f"DOCTRINE VIOLATION: '{P.MEASURED}' found in projected block '{path}'"
        )


def test_resale_uses_estimate_input_45c():
    """The big resale line uses the 45¢/kWh ESTIMATE input, clearly labeled."""
    p = _proj()
    resale = p["projection_1day_single_node"]["earnings"]["compute_resale_usd"]
    assert "45" in resale["estimate_input"]
    assert resale["label"] == P.ESTIMATE
    # value == kWh/day × 0.45
    kwh_day = (78_369.586 * 24.0) / P.JOULES_PER_KWH
    assert abs(resale["value"] - kwh_day * 0.45) < 1e-6


def test_scale_lines_derive_from_single_node_rate():
    """n-node line must equal exactly n × the single-node line (derived, not restated)."""
    p = _proj()
    lines = {l["nodes"]: l for l in p["scale_projection"]["lines"]}
    assert set(lines) == {1, 3, 10, 100, 1000}
    r1 = lines[1]["compute_resale_usd_yr"]["value"]
    for n in (3, 10, 100, 1000):
        rn = lines[n]["compute_resale_usd_yr"]["value"]
        # each value is independently rounded to 6 decimals, so allow the rounding
        # slack (≈5e-7 per value) scaled by n; the relation is exact pre-rounding.
        tol = (n + 1) * 1e-6
        assert abs(rn - n * r1) < tol, (
            f"{n}-node resale {rn} != {n}× single-node {r1}"
        )
    # kwh_yr also scales linearly (allow rounding slack, exact pre-rounding)
    k1 = lines[1]["kwh_yr"]["value"]
    assert abs(lines[10]["kwh_yr"]["value"] - 10 * k1) < 11e-6


def test_three_node_case_present():
    """Founder is wiring rig #3 — the 3-node line must be explicitly projected."""
    p = _proj()
    nodes = [l["nodes"] for l in p["scale_projection"]["lines"]]
    assert 3 in nodes


def test_grid_arbitrage_is_tiny_vs_resale():
    """Grid arbitrage is the pennies line; resale is the headline (orders larger)."""
    p = _proj()
    earn = p["projection_1day_single_node"]["earnings"]
    arb = abs(earn["grid_arbitrage_credit_usd"]["value"])
    resale = abs(earn["compute_resale_usd"]["value"])
    assert resale > arb  # resale dominates


def test_measured_inputs_carry_measured_label():
    """The live inputs ARE measured and must say so (provenance honesty)."""
    p = _proj()
    mi = p["measured_inputs"]
    assert mi["label"] == P.MEASURED
    assert mi["joules_measured"]["label"] == P.MEASURED
    assert mi["window_seconds"]["label"] == P.MEASURED
    assert mi["measured_source"] == "test:injected"


def test_negative_grid_price_yields_positive_arb_credit():
    """A negative grid price means the grid paid us → arbitrage credit is positive."""
    p = _proj()  # MEASURED has grid -2.90
    arb = p["projection_1day_single_node"]["earnings"]["grid_arbitrage_credit_usd"]["value"]
    assert arb > 0


def test_handler_degrades_without_500():
    """handle_projection returns a dict (live or fallback), never raises."""
    out = P.handle_projection(window="running")
    assert isinstance(out, dict)
    assert "endpoint" in out


def test_fallback_marks_source_when_no_siblings():
    """With no operator/ledger modules importable, fallback ground-truth is labeled."""
    # _extract_window with both None → documented fallback, clearly sourced.
    m = P._extract_window(None, None)
    assert "fallback" in m["measured_source"]
    assert m["joules_measured"] == P._GROUND_TRUTH_JOULES
    # tokens unknown in fallback — must be None, NOT fabricated
    assert m["tokens_measured"] is None


def test_honesty_block_invariants():
    p = _proj()
    h = p["honesty"]
    assert h["sovereign"] is False
    assert h["free_energy"] is False
    assert h["projected_revenue_label"] == P.MODELED
    assert h["resale_input_label"] == P.ESTIMATE


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
        passed += 1
    print(f"\nok:true  {passed}/{len(fns)} projection tests passed")
    sys.exit(0)
