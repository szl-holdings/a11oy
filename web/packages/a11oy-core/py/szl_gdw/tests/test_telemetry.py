#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

from szl_gdw.telemetry import OperationalTelemetry


def test_snapshot_is_read_only_and_honestly_labeled():
    telemetry = OperationalTelemetry()
    telemetry.record_session_created()
    telemetry.record_step("ACCEPT", replayed=False)
    telemetry.record_step("ACCEPT", replayed=True)
    telemetry.record_error("validation")

    first = telemetry.snapshot({"counts": {"sessions": 1}})
    second = telemetry.snapshot({"counts": {"sessions": 1}})

    assert first == second
    assert first["status"] == "MODELED"
    assert first["counters"]["step_requests"] == 2
    assert first["counters"]["step_replays"] == 1
    assert first["decisions"] == {"ACCEPT": 2}
    assert first["hardware_observation"] == "UNAVAILABLE"
    assert first["energy_observation"] == "UNAVAILABLE"
    assert first["performance_claim"] == "UNAVAILABLE"


def test_unknown_categories_fail_closed_to_bounded_buckets():
    telemetry = OperationalTelemetry()
    telemetry.record_step("invented", replayed=False)
    telemetry.record_error("secret internal exception text")

    result = telemetry.snapshot()

    assert result["decisions"] == {"UNAVAILABLE": 1}
    assert result["errors"] == {"unavailable": 1}
