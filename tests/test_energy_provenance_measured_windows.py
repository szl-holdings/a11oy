#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Hash-bound bounded-window entries on the energy provenance chain.

A v2 entry binds its measurement label, scope and window joules into its receipt
hash, so a label cannot be promoted after append. v1 entries keep their exact
historical encoding. Operator jobs reach the chain only through the completed-job
stream, under public node names, and a read never appends.
"""
import hashlib
import json
import math
import os
import tempfile
import time

import pytest

import szl_energy_operator as OP
import szl_energy_provenance as ep

WINDOW = "BOUNDED_METER_WINDOW"


def _v1_hash(entry):
    payload = {k: entry[k] for k in ep._HASHED_FIELDS}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _measured(chain, seq=7, window=12.5):
    return chain.append(output=f"job-{seq}", source="energy-operator", source_seq=seq,
                        node="Sovereign GPU 2 (always-on anchor)",
                        window_joules_measured=window, measurement_scope=WINDOW)


def test_v1_entries_keep_their_historical_encoding():
    chain = ep.EnergyProvenanceChain()
    entry = chain.append(output=b"hello world", energy_source="grid", joules_est=1.5)

    assert "schema" not in entry
    assert entry["receipt_hash"] == _v1_hash(entry)
    assert chain.verify()["ok"] is True
    assert chain.measured_window_entries() == 0


def test_v2_entry_binds_its_measurement():
    chain = ep.EnergyProvenanceChain()
    entry = _measured(chain)

    assert entry["schema"] == ep.ENTRY_SCHEMA_V2
    assert entry["measurement_label"] == "MEASURED"
    assert entry["measurement_scope"] == WINDOW
    assert entry["window_joules_measured"] == 12.5
    assert entry["source"] == "energy-operator"
    assert entry["source_seq"] == 7
    assert entry["node"] == "Sovereign GPU 2 (always-on anchor)"
    assert entry["receipt_hash"] != _v1_hash(entry)
    assert chain.verify()["ok"] is True
    assert chain.measured_window_entries() == 1
    summary = chain.summary()
    assert summary["measured_window_entries"] == 1
    assert summary["window_joules_measured_total"] == 12.5
    assert summary["window_joules_label"] == "MEASURED"
    assert summary["window_joules_scope"] == WINDOW
    assert summary["entry_schemas"] == {"v1": 0, "v2": 1}
    assert "SAMPLE/ESTIMATE" in summary["total_joules_est_label"]


@pytest.mark.parametrize("window,scope", [
    (None, WINDOW), (0.0, WINDOW), (-1.0, WINDOW), (float("nan"), WINDOW),
    (float("inf"), WINDOW), (True, WINDOW), ("12.5", WINDOW), (12.5, None),
    (12.5, "HOST_TOTAL"),
])
def test_unverified_windows_are_recorded_as_sample(window, scope):
    chain = ep.EnergyProvenanceChain()
    entry = chain.append(output="job", source="energy-operator", source_seq=1,
                         node="Sovereign GPU 1", window_joules_measured=window,
                         measurement_scope=scope)

    assert entry["schema"] == ep.ENTRY_SCHEMA_V2
    assert entry["measurement_label"] == "SAMPLE"
    assert entry["measurement_scope"] is None
    assert entry["window_joules_measured"] is None
    assert chain.verify()["ok"] is True
    assert chain.measured_window_entries() == 0
    json.dumps(chain.summary(), allow_nan=False)


@pytest.mark.parametrize("field,value", [
    ("measurement_label", "SAMPLE"), ("window_joules_measured", 99.0),
    ("measurement_scope", None), ("node", "Sovereign GPU 1"),
    ("source", "elsewhere"), ("source_seq", 8),
])
def test_editing_any_bound_field_breaks_verification(field, value):
    chain = ep.EnergyProvenanceChain()
    entry = _measured(chain)
    entry[field] = value

    report = chain.verify()
    assert report["ok"] is False
    assert report["first_break"]["index"] == 0


def test_schema_cannot_be_stripped_or_injected():
    stripped = ep.EnergyProvenanceChain()
    del _measured(stripped)["schema"]
    assert stripped.verify()["ok"] is False

    injected = ep.EnergyProvenanceChain()
    entry = injected.append(output="job", energy_source="grid", joules_est=0.0)
    entry.update({"schema": ep.ENTRY_SCHEMA_V2, "measurement_label": "MEASURED",
                  "measurement_scope": WINDOW, "window_joules_measured": 12.5,
                  "source": "energy-operator", "source_seq": 1, "node": "x"})
    assert injected.verify()["ok"] is False
    assert injected.measured_window_entries() == 0

    unknown = ep.EnergyProvenanceChain()
    unknown.append(output="job", energy_source="grid", joules_est=0.0)["schema"] = "v9"
    assert unknown.verify()["ok"] is False


def test_missing_bound_field_fails_closed_without_raising():
    chain = ep.EnergyProvenanceChain()
    del _measured(chain)["node"]
    report = chain.verify()
    assert report["ok"] is False
    assert "tampered" in report["first_break"]["reason"]


def test_retention_keeps_a_verifiable_anchored_suffix():
    chain = ep.EnergyProvenanceChain(max_entries=3)
    appended = [_measured(chain, seq=i) for i in range(5)]

    assert len(chain) == 3
    retained = chain.entries()
    assert [e["source_seq"] for e in retained] == [2, 3, 4]
    report = chain.verify()
    assert report["ok"] is True
    assert report["retention_anchor"] == {
        "dropped_entries": 2, "anchor_prev_hash": appended[2]["prev_hash"]}
    assert chain.summary()["retention"]["dropped_entries"] == 2
    retained[1]["window_joules_measured"] = 1.0
    assert chain.verify()["ok"] is False


@pytest.mark.parametrize("raw,expected", [
    ("", 10000), ("abc", 10000), ("0", 10000), ("-4", 10000), ("250", 250),
    ("5000000", 1000000),
])
def test_retention_bound_configuration(monkeypatch, raw, expected):
    monkeypatch.setenv(ep.MAX_ENTRIES_ENV, raw)
    assert ep._max_entries_from_env() == expected


def _job(**overrides):
    job = {"node": "omen-betterwithage", "model": "llama3.1:8b", "kind": "generate",
           "tokens": 7, "wall_s": 0.5, "ts": "2026-11-19T00:00:00Z", "seq": 11,
           "joules_measured": None, "joules_label": "SAMPLE",
           "window_joules_measured": 12.5, "joules_scope": WINDOW,
           "window_evidence": {"gpu_windows": [{"gpu_uuid": "GPU-private-uuid"}]},
           "governance": {"receipt_id": "private-receipt"}}
    job.update(overrides)
    return job


def test_operator_job_enters_under_its_public_name_only():
    chain = ep.EnergyProvenanceChain()
    entry = ep.append_operator_job(_job(), chain=chain)

    assert entry["measurement_label"] == "MEASURED"
    assert entry["node"] == "Sovereign GPU 2 (always-on anchor)"
    assert entry["source"] == "energy-operator" and entry["source_seq"] == 11
    blob = json.dumps(chain.summary())
    for private in ("omen-betterwithage", "GPU-private-uuid", "private-receipt", "100."):
        assert private not in blob, private


@pytest.mark.parametrize("overrides", [
    {"window_joules_measured": None, "joules_scope": None},
    {"joules_scope": "HOST_TOTAL"},
    {"window_joules_measured": float("nan")},
])
def test_operator_job_without_a_verified_window_is_sample(overrides):
    chain = ep.EnergyProvenanceChain()
    entry = ep.append_operator_job(_job(**overrides), chain=chain)

    assert entry["measurement_label"] == "SAMPLE"
    assert chain.measured_window_entries() == 0
    json.dumps(chain.summary(), allow_nan=False)


@pytest.mark.parametrize("job", [
    None, "job", {}, _job(node="local-stub"), _job(node="rtx-betterwithage-stub"),
    _job(seq=None), _job(seq=True), _job(seq=-1),
])
def test_stub_or_malformed_jobs_are_not_recorded(job):
    chain = ep.EnergyProvenanceChain()
    assert ep.append_operator_job(job, chain=chain) is None
    assert len(chain) == 0


def _counter_sample(ts, joules):
    return OP._exporter_sample_for_node({"engines": [{"engine": "betterwithage", "gpus": [{
        "gpu_uuid": "GPU-fixture", "counter_epoch": "fixture-segment", "sample_ts": ts,
        "joules_method": "NVML_COUNTER_DELTA", "live": True, "joules": joules}]}]},
        "betterwithage")


def test_operator_stream_is_wired_once_and_appends_completed_jobs():
    chain = ep.EnergyProvenanceChain()
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(nodes=[], state_path=os.path.join(d, "l.json"))
        first = ep.wire_operator_to_provenance(op, chain=chain)
        again = ep.wire_operator_to_provenance(op, chain=chain)
        assert first == {"subscribed": True, "already_wired": False}
        assert again == {"subscribed": False, "already_wired": True}

        t = time.time() - 2
        op._commit("rtx-betterwithage", "llama3.1:8b", "generate", 42, 0.5,
                   _counter_sample(t + 1, 112.5), 12.5,
                   exporter_before_sample=_counter_sample(t, 100.0),
                   job_start_ts=t + 0.25, job_end_ts=t + 0.75)
        op._commit("rtx-betterwithage", "bge-large", "embed", 4, 0.2, None, None)
        op._commit("local-stub", "stub-llama", "generate", 3, 0.1, None, None)

    entries = chain.entries()
    assert [e["measurement_label"] for e in entries] == ["MEASURED", "SAMPLE"]
    assert entries[0]["window_joules_measured"] == 12.5
    assert entries[0]["node"] == "Sovereign GPU 1"
    assert chain.verify()["ok"] is True
    assert chain.measured_window_entries() == 1


def test_public_read_never_appends():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    ep.register(app, ns="a11oy")
    client = TestClient(app)
    before = len(ep._CHAIN)
    for _ in range(3):
        response = client.get("/api/a11oy/v1/energy/provenance")
        assert response.status_code == 200
    assert len(ep._CHAIN) == before


def test_selftest_still_passes():
    result = ep._selftest()
    assert result["ok"] is True
    assert all(value is True for key, value in result.items()
               if key not in ("ok", "math_source"))
    assert math.isfinite(ep.EnergyProvenanceChain().summary()["total_joules_est"])
