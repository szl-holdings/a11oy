# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for IMMUNE Field fallback source attribution."""
from __future__ import annotations

import szl_immune as immune


def _clear_cache() -> None:
    immune._FIELD_CACHE.clear()


def test_primary_field_response_stays_channel_b() -> None:
    _clear_cache()

    def probe(url: str):
        assert url.endswith("/api/field")
        return 200, {
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "actuation": "SIMULATED",
            "rule": "observe only",
            "cells": [],
            "hunts": [],
        }, None

    result = immune._field(now=10_000.0, probe=probe)
    assert result["channel"] == "B"
    assert result["space"] == "SZLHOLDINGS/immune-lattice"
    assert result["contract"] == "/api/field"
    assert result["fallback_from"] is None
    _clear_cache()


def test_fallback_reports_channel_a_and_preserves_primary_failure() -> None:
    _clear_cache()
    calls: list[str] = []

    def probe(url: str):
        calls.append(url)
        if url.endswith("/api/field"):
            return 503, None, "field overlay unavailable"
        assert url.endswith("/api/immune/state")
        return 200, {
            "estate": [
                {"id": "cell-1", "title": "Observed cell", "role": "sensor"}
            ],
            "ledger": {"count": 7},
            "readiness": "OBSERVED",
            "mesh": "DEGRADED",
        }, None

    result = immune._field(now=20_000.0, probe=probe)
    assert len(calls) == 2
    assert result["ok"] is True
    assert result["channel"] == "A"
    assert result["space"] == "SZLHOLDINGS/immune"
    assert result["contract"] == "/api/immune/state"
    assert result["url"].endswith("/api/immune/state")
    assert result["cell_count"] == 1
    assert result["ledger"] == {"count": 7}
    assert result["fallback_from"] == {
        "channel": "B",
        "space": "SZLHOLDINGS/immune-lattice",
        "contract": "/api/field",
        "url": calls[0],
        "upstream_http": 503,
        "error": "field overlay unavailable",
    }
    _clear_cache()
