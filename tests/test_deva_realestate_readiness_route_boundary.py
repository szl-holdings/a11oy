# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import a11oy_deva_feeds as deva


def _assert_timestamp(value: object) -> None:
    assert value is not None
    if isinstance(value, (int, float)):
        assert float(value) > 0
        return
    assert isinstance(value, str) and value.strip()
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_cold_failure_is_canonical_unavailable_with_observation_clock() -> None:
    raw = {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "error": "ReadTimeout: bounded Treasury source timeout",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] is None
    assert result["freshness"]["status"] == "UNAVAILABLE"
    _assert_timestamp(result["freshness"]["fetched_at"])
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_last_good_failure_stays_cached_with_original_source_clock() -> None:
    observed_at = "2026-09-13T02:40:00+00:00"
    raw = {
        "value": {"items": [{"rate": 4.0}]},
        "freshness": {
            "status": "stale",
            "age_s": 45.0,
            "fetched_at": observed_at,
            "error": "ReadTimeout: refresh failed",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] == raw["value"]
    assert result["freshness"]["status"] == "cached"
    assert result["freshness"]["fetched_at"] == observed_at
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_all_readiness_evaluated_realestate_sources_cross_public_boundary() -> None:
    source = Path("a11oy_deva_feeds.py").read_text(encoding="utf-8")

    # HPD/DOB already cross this boundary. Rates and SEC evidence must do the
    # same so cold source failures cannot leak raw lowercase `unavailable`
    # without an observation timestamp into the readiness contract.
    required = (
        '"hpd": _readiness_public_source(hpd)',
        '"dob": _readiness_public_source(dob)',
        '"rates": _readiness_public_source(rates)',
        '"sec_fts": _readiness_public_source(sec)',
    )
    for expression in required:
        assert expression in source, expression

    # Pulse and deal both expose Treasury rates and therefore require two route
    # boundary applications rather than one accidental occurrence.
    assert source.count('"rates": _readiness_public_source(rates)') >= 2
