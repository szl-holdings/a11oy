# SPDX-License-Identifier: Apache-2.0
"""Kernel probe honesty: REACHABLE / UNAVAILABLE only. Never LIVE or PASS."""
from __future__ import annotations

import szl_immune as immune


def setup_function() -> None:
    immune._KERNEL_CACHE["at"] = 0.0
    immune._KERNEL_CACHE["payload"] = None
    immune._FIELD_CACHE["at"] = 0.0
    immune._FIELD_CACHE["payload"] = None
    immune._NEXUS_CACHE["at"] = 0.0
    immune._NEXUS_CACHE["payload"] = None
    immune._LORENZ_CACHE["at"] = 0.0
    immune._LORENZ_CACHE["payload"] = None


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


def test_field_reachable_is_not_live_or_pass() -> None:
    def probe(url: str):
        assert url.endswith("/api/field")
        return 200, {
            "doctrine": "v11 LOCKED",
            "lambda_status": "Conjecture 1",
            "actuation": "SIMULATED",
            "rule": "hunt isolate deceive — never strike people",
            "cells": [{"id": "exile", "name": "RANGE.CLOUD.EXILE", "verb": "EXILE", "take": "off-estate"}],
            "hunts": [{"id": "G0034", "name": "Sandworm RANGE twin", "cluster": "G0034"}],
        }, None

    out = immune._field(now=1.0, probe=probe)
    assert out["reachability"] == "REACHABLE"
    assert out["actuation"] == "SIMULATED"
    assert out["cell_count"] == 1
    assert out["hunts"] == [{"id": "G0034", "name": "Sandworm RANGE twin", "cluster": "G0034"}]
    assert out["status"] == "REAL"
    assert out["reachability"] != "LIVE"
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]
    assert out["honesty"]["not_a_second_cop"] is True
    assert out["space"] == "SZLHOLDINGS/immune-lattice"


def test_field_failed_probe_does_not_invent_cells() -> None:
    def probe(_url: str):
        return None, None, "TimeoutError"

    out = immune._field(now=1.0, probe=probe)
    assert out["reachability"] == "UNAVAILABLE"
    assert out["ok"] is False
    assert out["cells"] is None
    assert out["cell_count"] is None
    assert out["status"] == "DEGRADED"
    assert out["error"] == "TimeoutError"


def test_nexus_reachable_is_not_live_or_pass() -> None:
    def probe(url: str):
        assert url.endswith("/api/immune/nexus/status")
        return 200, {
            "schema": "szl.immune-nexus-status/v1",
            "state": "EXECUTABLE",
            "programs": ["lorenz", "harmonic", "vanderpol", "duffing", "lotka", "nemo"],
            "truth": {
                "execution": "MEASURED_SOFTWARE_SIMULATION",
                "energy": "UNAVAILABLE",
                "uniqueness": "Conjecture 1 OPEN",
            },
            "ui": "/nexus.html",
        }, None

    out = immune._nexus(now=1.0, probe=probe)
    assert out["reachability"] == "REACHABLE"
    assert out["state"] == "EXECUTABLE"
    assert out["energy"] == "UNAVAILABLE"
    assert out["program_count"] == 6
    assert out["reachability"] != "LIVE"
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]


def test_nexus_failed_probe_is_unavailable() -> None:
    def probe(_url: str):
        return 404, None, "HTTP 404"

    out = immune._nexus(now=1.0, probe=probe)
    assert out["reachability"] == "UNAVAILABLE"
    assert out["ok"] is False
    assert out["state"] is None


def test_lorenz_seal_is_not_live_or_pass() -> None:
    def post(url: str, body: dict):
        assert url.endswith("/api/immune/nexus/run")
        assert body["program"] == "lorenz"
        assert body["mode"] == "OP"
        assert body["steps"] == 320
        return 201, {
            "requestId": body["requestId"],
            "governed": {
                "pass": True,
                "receipt": {
                    "payload": {
                        "agent": {
                            "nexus": {
                                "inputHash": "c5fcc5029392a5e4f7cd65a655d5379cd65d8f915b2ee96a1db5d44e35ea2358",
                                "outputHash": "4071a2f2faca744907747cb2cc82a9d841e125fa287240505f9f9a8454a399ac",
                                "invariantsHold": True,
                                "energy": "UNAVAILABLE",
                                "uniqueness": "Conjecture 1 OPEN",
                            }
                        }
                    }
                },
            },
            "result": {
                "execution": {
                    "stepsExecuted": 320,
                    "truth": "MEASURED_SOFTWARE_SIMULATION",
                    "energy": "UNAVAILABLE",
                    "uniqueness": "Conjecture 1 OPEN",
                },
                "coefficients": {"label": "σ 10 · ρ 27.9 · β 2.67"},
                "finalState": {"x": -7.707920173353, "y": -10.567955419679, "z": 21.305498529338},
            },
        }, None

    out = immune._nexus_lorenz(now=1.0, post=post)
    assert out["reachability"] == "REACHABLE"
    assert out["sealed"] is True
    assert out["inputHash"].startswith("c5fcc502")
    assert out["outputHash"].startswith("4071a2f2")
    assert out["energy"] == "UNAVAILABLE"
    assert out["reachability"] != "LIVE"
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]
    assert out["reference"]["outputHash"].startswith("4071a2f2")


def test_lorenz_failed_seal_is_unavailable_and_keeps_reference() -> None:
    def post(_url: str, _body: dict):
        return 409, {"error": "NEXUS_GOVERNANCE_REJECTED"}, "HTTP 409"

    out = immune._nexus_lorenz(now=1.0, post=post)
    assert out["reachability"] == "UNAVAILABLE"
    assert out["ok"] is False
    assert out["sealed"] is False
    assert out["inputHash"] is None
    assert out["reference"]["program"] == "lorenz"
    assert out["honesty"]["reference_is_not_this_run"] is True
