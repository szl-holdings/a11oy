#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""KHIPU-OS route boundary: GET verify recomputes and mints nothing."""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_khipu_os_routes as m  # noqa: E402

BASE = "/api/a11oy/v1/khipu-os"


@pytest.fixture
def dag(monkeypatch):
    d = m.KhipuOSDag()
    for i in range(4):
        d.add_receipt("test", "seed", {"i": i})
    # Injected before register() so get_dag() never starts the runner thread.
    monkeypatch.setattr(m, "_DAG", d)
    monkeypatch.setattr(m, "_load_ec_signer", lambda _path: (None, None))
    return d


@pytest.fixture
def client(dag):
    app = FastAPI()
    m.register(app)
    return TestClient(app)


def _state(client):
    s = client.get(BASE + "/stats").json()
    return s["hot_count"], s["merkle_root"], s["tamper_events"]


def test_get_verify_mints_no_receipt(client, dag):
    before = _state(client)
    seq = dag._seq
    for _ in range(2):
        r = client.get(BASE + "/verify")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["sampled"] == 5
        assert body["receipt"] is None
        assert body["recorded"] is False
    assert _state(client) == before
    assert dag._seq == seq
    assert not [r for r in dag.hot.values() if r.action == "self_verify"]


def test_get_verify_reports_hash_mismatch_without_mutating(client, dag):
    victim = next(r for r in dag.hot.values() if r.action == "seed")
    victim.payload["i"] = 999
    before = _state(client)
    body = client.get(BASE + "/verify", params={"sample": 1000}).json()
    assert body["ok"] is False
    assert body["bad"] == [{"id": victim.rid, "kind": "hash_mismatch"}]
    assert body["receipt"] is None
    assert _state(client) == before
    assert dag.tamper_events == []


def test_get_verify_reports_forged_signature(client, dag):
    victim = next(r for r in dag.hot.values() if r.action == "seed")
    victim.signature = "0" * 64
    body = client.get(BASE + "/verify", params={"sample": 1000}).json()
    assert body["ok"] is False
    assert body["bad"] == [{"id": victim.rid, "kind": "signature_invalid"}]
    assert dag.tamper_events == []


def test_recording_verify_keeps_write_path(dag):
    victim = next(r for r in dag.hot.values() if r.action == "seed")
    victim.payload["i"] = 999
    hot = len(dag.hot)
    out = dag.verify(1000, record=True)
    assert out["ok"] is False
    assert out["recorded"] is True
    assert len(dag.hot) == hot + 1
    rec = dag.hot[out["receipt"]]
    assert rec.action == "self_verify"
    assert rec.signature
    assert len(dag.tamper_events) == 1
    assert dag.tamper_events[0]["tripwire"] == "T22"


def test_verify_records_by_default(dag):
    hot = len(dag.hot)
    out = dag.verify()
    assert out["recorded"] is True
    assert dag.hot[out["receipt"]].action == "self_verify"
    assert len(dag.hot) == hot + 1


def test_checkpoint_without_ec_key_is_labelled_placeholder(client):
    r = client.post(BASE + "/checkpoint")
    assert r.status_code == 200
    env = r.json()["envelope"]
    assert env["sig_kind"].startswith("PLACEHOLDER")
    assert env["signatures"][0]["keyid"] == "PLACEHOLDER:Yachay"


def test_tick_still_mints_audit_receipt(dag):
    hot = len(dag.hot)
    out = dag.tick()
    assert out["verify_ok"] is True
    assert len(dag.hot) > hot
    assert [r for r in dag.hot.values() if r.action == "self_verify"]
