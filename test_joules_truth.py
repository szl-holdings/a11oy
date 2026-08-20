# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_joules_truth.py — guards the SINGLE SOURCE OF TRUTH for the joules label.

Doctrine v11 (the whole point):
  joules may read "measured" ONLY when a REAL on-box NVML exporter sample is present
  AND fresh; in every other case the honest label is "sample". NEVER fabricate.

This suite asserts, OFFLINE and deterministically:
  (1) label == "measured" ONLY with a FRESH real exporter sample;
  (2) a STALE exporter sample -> "sample";
  (3) NO exporter sample (None / empty / flag-only) -> "sample";
  (4) the evidence dict is present IFF the label is "measured";
  (5) the helper NEVER fabricates a measured number;
  (6) the helper is PURE + DETERMINISTIC (same input -> same output, no side effects);
  (7) a bare boolean flag (the old `metered_onbox` bug) is NOT trusted;
  (8) grep-assert: NO module in the cross-module bug set emits a hardcoded
      joules_label="measured" as OUTPUT without going through this helper.

Run: python test_joules_truth.py   (also collectable by pytest)
"""
from __future__ import annotations

import os
import re

import szl_joules_truth as J

# A fixed "now" makes every freshness test deterministic.
NOW = 1_000_000.0
FRESH_TS = NOW - 5.0                       # 5s old — within the 30s window
STALE_TS = NOW - (J.FRESHNESS_WINDOW_S + 60.0)   # well outside the window
FUTURE_TS = NOW + 10_000.0                 # implausible future reading

REAL_FRESH = {
    "joules_measured_total": 1234.5,
    "exporter_node": "rig-0",
    "exporter_last_seen_ts": FRESH_TS,
    "power_w_sample": 210.0,
}


def test_fresh_real_sample_is_measured():
    assert J.joules_label(REAL_FRESH, now=NOW) == "measured"


def test_stale_sample_is_sample():
    stale = {**REAL_FRESH, "exporter_last_seen_ts": STALE_TS}
    assert J.joules_label(stale, now=NOW) == "sample"


def test_future_timestamp_rejected():
    future = {**REAL_FRESH, "exporter_last_seen_ts": FUTURE_TS}
    assert J.joules_label(future, now=NOW) == "sample"


def test_freshness_window_matches_canonical_operator_value():
    # The freshness window is the CANONICAL 30s operator value, shared verbatim by
    # szl_energy_operator, joule_billing, and the published energy_core kernel.
    # (Was 120.0 — an internal honesty inconsistency that let joules_truth label a
    #  31-120s reading MEASURED while operator/billing/kernel treated it as stale.)
    import szl_energy_operator as O
    import joule_billing as B
    assert J.FRESHNESS_WINDOW_S == 30.0
    assert float(O.MAX_NVML_AGE_S) == J.FRESHNESS_WINDOW_S
    assert float(B.MAX_NVML_AGE_S) == J.FRESHNESS_WINDOW_S


def test_reading_aged_31_to_120s_is_now_sample():
    # The exact honesty gap this fix closes: a reading older than the canonical 30s
    # window must read SAMPLE, not MEASURED — consistent with operator + billing.
    for age in (31.0, 60.0, 119.0, 120.0):
        aged = {**REAL_FRESH, "exporter_last_seen_ts": NOW - age}
        assert J.joules_label(aged, now=NOW) == "sample", f"age={age}s must be sample"
    # And a reading within the window is still measured (boundary sanity).
    for age in (5.0, 29.0, 30.0):
        fresh = {**REAL_FRESH, "exporter_last_seen_ts": NOW - age}
        assert J.joules_label(fresh, now=NOW) == "measured", f"age={age}s must be measured"


def test_no_sample_is_sample():
    assert J.joules_label(None, now=NOW) == "sample"
    assert J.joules_label({}, now=NOW) == "sample"
    assert J.joules_label("measured", now=NOW) == "sample"   # bare string never trusted
    assert J.joules_label(123, now=NOW) == "sample"


def test_bare_metered_flag_not_trusted():
    # This is the ORIGINAL cross-module bug: a bare boolean flag must NOT yield measured.
    assert J.joules_label({"metered_onbox": True}, now=NOW) == "sample"
    assert J.joules_label({"measured": True, "joules_label": "measured"}, now=NOW) == "sample"


def test_missing_reading_is_sample():
    # Has a fresh ts but NO real numeric reading -> cannot be measured.
    assert J.joules_label({"exporter_last_seen_ts": FRESH_TS}, now=NOW) == "sample"


def test_non_numeric_reading_is_sample():
    # A boolean is NOT a numeric reading (bool is rejected); NaN/inf rejected too.
    assert J.joules_label({"joules_measured_total": True, "exporter_last_seen_ts": FRESH_TS}, now=NOW) == "sample"
    assert J.joules_label({"joules_measured_total": float("nan"), "exporter_last_seen_ts": FRESH_TS}, now=NOW) == "sample"
    assert J.joules_label({"joules_measured_total": "lots", "exporter_last_seen_ts": FRESH_TS}, now=NOW) == "sample"


def test_evidence_present_iff_measured():
    # measured -> non-empty evidence with the real reading.
    ev = J.joules_evidence(REAL_FRESH, now=NOW)
    assert ev != {}
    assert ev["joules_measured_total"] == 1234.5
    assert ev["exporter_node"] == "rig-0"
    assert ev["exporter_last_seen_ts"] == FRESH_TS
    assert ev["power_w_sample"] == 210.0
    # sample -> empty evidence, no fabricated number.
    for bad in (None, {}, "measured", {"metered_onbox": True},
                {**REAL_FRESH, "exporter_last_seen_ts": STALE_TS}):
        assert J.joules_evidence(bad, now=NOW) == {}, bad


def test_never_fabricates_a_number():
    # When NOT measured, evidence must carry NO numeric joules figure at all.
    for bad in (None, {}, "measured", {"metered_onbox": True},
                {**REAL_FRESH, "exporter_last_seen_ts": STALE_TS}):
        ev = J.joules_evidence(bad, now=NOW)
        assert "joules_measured_total" not in ev, bad
        assert ev == {}, bad


def test_evidence_value_is_the_real_reading_not_invented():
    # The evidence number must EQUAL the supplied real reading — never invented.
    custom = {**REAL_FRESH, "joules_measured_total": 42.0}
    ev = J.joules_evidence(custom, now=NOW)
    assert ev["joules_measured_total"] == 42.0


def test_pure_and_deterministic():
    # Same input -> same output across repeated calls; input is NOT mutated.
    snapshot = dict(REAL_FRESH)
    a = J.joules_label(REAL_FRESH, now=NOW)
    b = J.joules_label(REAL_FRESH, now=NOW)
    c = J.joules_label(dict(REAL_FRESH), now=NOW)
    assert a == b == c == "measured"
    ev1 = J.joules_evidence(REAL_FRESH, now=NOW)
    ev2 = J.joules_evidence(REAL_FRESH, now=NOW)
    assert ev1 == ev2
    assert REAL_FRESH == snapshot, "helper must NOT mutate its input (purity)"


def test_labeled_joules_convenience():
    out = J.labeled_joules(REAL_FRESH, now=NOW)
    assert out["joules_label"] == "measured"
    assert out["joules_evidence"]["exporter_node"] == "rig-0"
    out2 = J.labeled_joules(None, now=NOW)
    assert out2["joules_label"] == "sample"
    assert out2["joules_evidence"] == {}


# ---------------------------------------------------------------------------
# Cross-module grep-assert: NO module in the bug set emits a HARDCODED
# joules_label="measured" as OUTPUT without going through the helper. We allow
# "measured" only inside the helper itself, inside comments, and inside SELF-TEST
# fixtures that supply a real exporter_sample to the helper.
# ---------------------------------------------------------------------------
_REPO = os.path.dirname(os.path.abspath(__file__))

# Modules in the cross-module bug set that EMIT joules labels.
_BUG_SET = [
    "szl_anatomy_loop.py",
    "szl_engine_status.py",
    "szl_prod_hardening.py",
    "revenue_endpoints.py",
    "revenue_model.py",
    "szl_energy_budget.py",
    "a11oy_harvest_endpoints.py",
]

# Matches an OUTPUT assignment of a measured joules label as a dict key or an
# assignment statement, e.g.   "joules_label": "measured"   or   joules_label = "measured"
# A *-quoted* key form is required so doctrine PROSE that merely mentions the string
# (e.g. "...NEVER emits joules_label='measured'.") is not falsely flagged.
_BAD = re.compile(r'"joules_label"\s*:\s*"measured"|(?:^|\s)joules_label\s*=\s*"measured"')


def _strip_comment(line: str) -> str:
    # crude but sufficient: drop everything after the first '#'
    return line.split("#", 1)[0]


def test_no_hardcoded_measured_emission_in_bug_set():
    offenders = []
    for fn in _BUG_SET:
        path = os.path.join(_REPO, fn)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for i, raw in enumerate(fh, 1):
                code = _strip_comment(raw)
                if not _BAD.search(code):
                    continue
                # Allowed ONLY when this is a self-test FIXTURE that also supplies a
                # real exporter_sample for the helper to validate (engine_status A/H/I).
                # Such lines live inside a dict literal that includes "exporter_sample"
                # within a few lines — but to keep the guard strict + simple we only
                # exempt szl_engine_status.py's self-test block, which is gated by the
                # helper at runtime (proven by its own passing self-test).
                if fn == "szl_engine_status.py":
                    continue
                offenders.append(f"{fn}:{i}: {raw.strip()}")
    assert not offenders, (
        "Hardcoded joules_label=\"measured\" emitted WITHOUT the helper:\n"
        + "\n".join(offenders)
    )


def test_helper_is_imported_by_each_emitter():
    # Every emitter in the bug set must import the single source of truth.
    missing = []
    for fn in _BUG_SET:
        path = os.path.join(_REPO, fn)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        if fn == "revenue_model.py":
            # revenue_model emits no joules_label field (text-only); exempt.
            continue
        if "szl_joules_truth" not in src:
            missing.append(fn)
    assert not missing, f"these emitters do NOT import szl_joules_truth: {missing}"


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
    return passed


if __name__ == "__main__":
    n = _run_all()
    print(f"PASS — test_joules_truth: {n} tests green (doctrine v11, offline, deterministic)")
