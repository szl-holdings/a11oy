# SPDX-License-Identifier: Apache-2.0
"""Kernel probe honesty: REACHABLE / UNAVAILABLE only. Never LIVE or PASS."""
from __future__ import annotations

import szl_immune as immune


def setup_function() -> None:
    immune._KERNEL_CACHE["at"] = 0.0
    immune._KERNEL_CACHE["payload"] = None


def test_reachable_write_ready_is_not_live_or_pass() -> None:
    def probe(_url: str):
        return 200, {
            "status": "READY",
            "write_ready": True,
            "authority": {"evidenceState": "VERIFIED", "keyId": "d51d70b2"},
            "receiptCount": 6,
            "blockers": [],
        }, None

    out = immune._kernel(now=1.0, probe=probe)
    assert out["reachability"] == "REACHABLE"
    assert out["write_ready"] is True
    assert out["key_id"] == "d51d70b2"
    assert out["ledger"] == 6
    assert out["status"] == "REAL"
    assert out["reachability"] != "LIVE"
    assert out.get("mode") is None
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]
    assert out["honesty"]["first_paint"] == "CONNECTING"
    assert out["channel_a"]["space"] == "SZLHOLDINGS/immune"
    assert out["channel_b"]["space"] == "SZLHOLDINGS/immune-lattice"


def test_failed_probe_is_unavailable_not_connecting() -> None:
    def probe(_url: str):
        return None, None, "TimeoutError"

    out = immune._kernel(now=1.0, probe=probe)
    assert out["reachability"] == "UNAVAILABLE"
    assert out["ok"] is False
    assert out["write_ready"] is None
    assert out["status"] == "DEGRADED"
    assert out["error"] == "TimeoutError"


def test_cache_does_not_reprobe_within_ttl() -> None:
    hits = {"n": 0}

    def probe(_url: str):
        hits["n"] += 1
        return 200, {"status": "READY", "write_ready": False}, None

    a = immune._kernel(now=10.0, probe=probe)
    b = immune._kernel(now=12.0, probe=probe)
    assert hits["n"] == 1
    assert a["cached"] is False
    assert b["cached"] is True
    assert b["reachability"] == "REACHABLE"
    assert b["write_ready"] is False
