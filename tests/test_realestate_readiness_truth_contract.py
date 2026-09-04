# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import a11oy_deva_feeds as deva
import a11oy_vertical_feeds as vertical


def _assert_timestamp(value: object) -> None:
    assert value is not None
    if isinstance(value, (int, float)):
        assert float(value) > 0
        return
    assert isinstance(value, str) and value.strip()
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_vertical_no_value_failure_is_canonical_unavailable() -> None:
    raw = {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "fetched_at": 1788559200.0,
            "error": "TimeoutError: bounded upstream timeout",
        },
    }
    result = vertical._readiness_public_source(raw)
    assert result["value"] is None
    assert result["freshness"]["status"] == "UNAVAILABLE"
    assert result["freshness"]["fetched_at"] == 1788559200.0
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_deva_cold_failure_adds_observation_clock_without_inventing_data() -> None:
    raw = {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "error": "ReadTimeout: upstream did not answer",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] is None
    assert result["freshness"]["status"] == "UNAVAILABLE"
    _assert_timestamp(result["freshness"]["fetched_at"])
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_deva_last_good_failure_is_cached_with_original_clock() -> None:
    observed_at = "2026-09-04T21:00:00+00:00"
    raw = {
        "value": {"items": [{"id": "observed"}]},
        "freshness": {
            "status": "stale",
            "age_s": 42.0,
            "fetched_at": observed_at,
            "error": "ReadTimeout: refresh failed",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] == raw["value"]
    assert result["freshness"]["status"] == "cached"
    assert result["freshness"]["fetched_at"] == observed_at
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_all_three_realestate_readiness_routes_apply_the_public_wrapper() -> None:
    vertical_source = Path("a11oy_vertical_feeds.py").read_text(encoding="utf-8")
    deva_source = Path("a11oy_deva_feeds.py").read_text(encoding="utf-8")
    assert '"hpd_litigations": _readiness_public_source(hpd)' in vertical_source
    assert '"dob_violations": _readiness_public_source(dob)' in vertical_source
    assert deva_source.count('"hpd": _readiness_public_source(hpd)') == 2
    assert '"dob": _readiness_public_source(dob)' in deva_source
