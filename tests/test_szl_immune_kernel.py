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


def _verified_lorenz_payload(request_id: str, *, signed_request_id: str | None = None) -> dict:
    bound_request_id = request_id if signed_request_id is None else signed_request_id
    return {
        "requestId": bound_request_id,
        "program": "lorenz",
        "mode": "OP",
        "steps": 320,
        "agent": {"nexus": {
            "requestId": bound_request_id,
            "program": "lorenz",
            "mode": "OP",
            "steps": 320,
            "inputHash": "c5fcc5029392a5e4f7cd65a655d5379cd65d8f915b2ee96a1db5d44e35ea2358",
            "outputHash": "4071a2f2faca744907747cb2cc82a9d841e125fa287240505f9f9a8454a399ac",
            "invariantsHold": True,
            "energy": "UNAVAILABLE",
            "uniqueness": "Conjecture 1 OPEN",
            "truth": "MEASURED_SOFTWARE_SIMULATION",
            "coefficients": {"label": "sigma 10 / rho 27.9 / beta 2.67"},
            "final": {"x": -7.707920173353, "y": -10.567955419679, "z": 21.305498529338},
        }},
    }


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
    seen: dict = {}

    def post(url: str, body: dict):
        assert url.endswith("/api/immune/nexus/run")
        assert body["program"] == "lorenz"
        assert body["mode"] == "OP"
        assert body["steps"] == 320
        seen["request_id"] = body["requestId"]
        return 201, {
            "requestId": body["requestId"],
            "governed": {
                "pass": True,
                "receipt": {"payloadType": "application/vnd.in-toto+json"},
            },
        }, None

    def verify(_receipt: dict):
        return {
            "verified": True,
            "keyid_expected": "test-lorenz-key",
            "payload_decoded": _verified_lorenz_payload(seen["request_id"]),
        }

    out = immune._nexus_lorenz(now=1.0, post=post, verify=verify)
    assert out["reachability"] == "REACHABLE"
    assert out["sealed"] is True
    assert out["inputHash"].startswith("c5fcc502")
    assert out["outputHash"].startswith("4071a2f2")
    assert out["energy"] == "UNAVAILABLE"
    assert out["reachability"] != "LIVE"
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]
    assert out["receipt_verification"] == {
        "verified": True,
        "keyid": "test-lorenz-key",
        "request_binding": True,
    }
    assert out["reference_only"]["outputHash"].startswith("4071a2f2")


def test_lorenz_failed_seal_is_unavailable_and_keeps_reference() -> None:
    def post(_url: str, _body: dict):
        return 409, {"error": "NEXUS_GOVERNANCE_REJECTED"}, "HTTP 409"

    out = immune._nexus_lorenz(
        now=1.0,
        post=post,
        verify=lambda _receipt: {"verified": False, "reason": "signature mismatch"},
    )
    assert out["reachability"] == "UNAVAILABLE"
    assert out["ok"] is False
    assert out["sealed"] is False
    assert out["inputHash"] is None
    assert out["reference_only"]["program"] == "lorenz"
    assert out["honesty"]["reference_is_not_this_run"] is True


def test_lorenz_rejects_verified_receipt_bound_to_another_request() -> None:
    seen: dict = {}

    def post(_url: str, body: dict):
        seen["request_id"] = body["requestId"]
        return 201, {
            "requestId": body["requestId"],
            "governed": {
                "pass": True,
                "receipt": {"payloadType": "application/vnd.in-toto+json"},
            },
        }, None

    def verify(_receipt: dict):
        return {
            "verified": True,
            "keyid_expected": "test-lorenz-key",
            "payload_decoded": _verified_lorenz_payload(
                seen["request_id"], signed_request_id="lorenz-op-substituted"
            ),
        }

    out = immune._nexus_lorenz(post=post, verify=verify)
    assert out["ok"] is False
    assert out["sealed"] is False
    assert out["inputHash"] is None
    assert out["receipt_verification"]["verified"] is True
    assert out["receipt_verification"]["request_binding"] is False
    assert "not bound" in out["error"]


def test_lorenz_action_results_are_never_cached() -> None:
    hits = {"n": 0}

    def post(_url: str, body: dict):
        hits["n"] += 1
        return 409, {"requestId": body["requestId"], "error": "rejected"}, "HTTP 409"

    def verify(_receipt: dict):
        return {"verified": False, "reason": "receipt unavailable"}

    first = immune._nexus_lorenz(now=10.0, post=post, verify=verify)
    second = immune._nexus_lorenz(now=11.0, post=post, verify=verify)
    assert hits["n"] == 2
    assert first["cached"] is False
    assert second["cached"] is False


def test_field_state_fallback_binds_ledger_not_pass() -> None:
    seen = []

    def probe(url: str):
        seen.append(url)
        if url.endswith("/api/field"):
            return 404, {"error": "not found"}, "HTTP 404"
        assert url.endswith("/api/immune/state")
        return 200, {
            "authority": {"mode": "PASS", "evidenceState": "VERIFIED", "authorityReceiptCount": 17},
            "readiness": {"status": "READY", "write_ready": True, "ready": True},
            "ledger": {
                "count": 2,
                "lastHash": "5ddcc2a3ba3091c2215164f2526bf98475657586dcd28564b810cef36a6c6bed",
                "verify": {"ok": True},
            },
            "estate": [
                {"id": "immune", "title": "IMMUNE", "role": "defense kernel", "stage": "WRITE-READY"},
                {"id": "a11oy", "title": "a11oy", "role": "command center", "stage": "LIVE"},
            ],
            "mesh": {"required": 3, "of": 4, "reached": True, "liveCount": 4},
        }, None

    out = immune._field(now=1.0, probe=probe)
    assert any(u.endswith("/api/field") for u in seen)
    assert any(u.endswith("/api/immune/state") for u in seen)
    assert out["reachability"] == "REACHABLE"
    assert out["contract"] == "/api/immune/state"
    assert out["ledger"]["count"] == 2
    assert out["cell_count"] == 2
    assert out["cells"][1]["verb"] == "OBSERVED"
    assert out["actuation"] == "SIMULATED"
    assert out["status"] == "REAL"
    assert out["reachability"] != "LIVE"
    assert out.get("mode") is None
    assert "PASS" not in str(out["cells"])
    assert out["honesty"]["never_fabricate"] == ["LIVE", "PASS"]


def test_kernel_ledger_dict_count_is_forwarded() -> None:
    def probe(_url: str):
        return 200, {
            "status": "READY",
            "write_ready": True,
            "authority": {"evidence_state": "VERIFIED", "key_id": "c841507add86f06c", "receipt_count": 4},
            "ledger": {"ok": True, "count": 7, "first_bad_seq": None},
            "blockers": [],
        }, None

    out = immune._kernel(now=1.0, probe=probe)
    assert out["reachability"] == "REACHABLE"
    assert out["ledger"] == 7
    assert out["key_id"] == "c841507add86f06c"
    assert out["write_ready"] is True
    assert out["reachability"] != "LIVE"
