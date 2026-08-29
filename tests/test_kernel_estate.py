# SPDX-License-Identifier: Apache-2.0
"""Kernel estate organ actually calls members (or honest UNAVAILABLE)."""
from __future__ import annotations

import sys
import types

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import szl_hub as ke  # noqa: E402

REQUIRED = [
    "szl-kernels",
    "szl-receipt-attn",
    "szl-maskmod",
    "szl-block-kv",
    "YARQA-ATTN",
    "szl-governed-norm",
    "szl-lambda-gate",
    "szl-ouroboros",
    "szl-invariants",
    "szl-formulas",
    "szl-blocked",
    "szl-govsign",
    "szl-provctl",
    "szl-nemo",
    "governed-inference-meter",
    "szl-serve",
]


def test_catalog_is_complete():
    assert set(e["key"] for e in ke.list_estate()) == set(REQUIRED)


def test_missing_package_is_unavailable_not_fake_green():
    rec = ke.probe_member(
        {
            "key": "szl-receipt-attn",
            "module": "szl_receipt_attn",
            "hub_id": "SZLHOLDINGS/szl-receipt-attn",
            "probe": "selfcheck",
        }
    )
    assert rec["status"] == "UNAVAILABLE"
    assert rec["called"] is False
    assert rec["joblib"] == "QUARANTINED"


def test_injected_kernel_is_actually_called(monkeypatch):
    called = {"n": 0}

    def selfcheck():
        called["n"] += 1
        return {"ok": True, "path": "stub"}

    stub = types.ModuleType("szl_blocked")
    stub.selfcheck = selfcheck
    monkeypatch.setitem(sys.modules, "szl_blocked", stub)
    rec = ke.probe_member(
        {
            "key": "szl-blocked",
            "module": "szl_blocked",
            "hub_id": "SZLHOLDINGS/szl-blocked",
            "probe": "selfcheck",
        }
    )
    assert called["n"] == 1
    assert rec["status"] == "LIVE"
    assert rec["called"] is True
    assert rec["probe_result"]["ok"] is True


def test_register_endpoint_calls_probe():
    app = FastAPI()
    ke.register(app)
    client = TestClient(app)
    resp = client.get("/api/a11oy/v1/kernel-estate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enumerated"] == 16
    assert body["joblib"] == "QUARANTINED"
    assert body["pickle"] == "QUARANTINED"
    assert body["cuda"]["status"] in ("LIVE", "UNAVAILABLE")
    keys = [k["key"] for k in body["kernels"]]
    assert set(keys) == set(REQUIRED)
