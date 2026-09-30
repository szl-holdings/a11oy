#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline HTTP contract for reading the synthetic receipt ledger."""

import copy
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


LEDGER_ROUTES = ("/api/a11oy/v1/wow/ledger", "/v1/wow/ledger")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def wow_ledger(monkeypatch):
    # Import only this module, without reading or generating any signing key.
    signer = types.ModuleType("a11oy_signing_key")
    signer.load_signing_key = lambda: (None, "", "unavailable", "disabled in test")
    monkeypatch.setitem(sys.modules, "a11oy_signing_key", signer)
    spec = importlib.util.spec_from_file_location(
        "wow_ledger_read_contract", ROOT / "a11oy_dev1_endpoints.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._PRIV is None

    # Core-only fixtures bypass registration's mixed demo seed. Explicit
    # advancement also selects a core record, without other application code.
    module.time = types.SimpleNamespace(time=lambda: 0)
    module._LEDGER_ACTIONS = {"core": module._LEDGER_ACTIONS["core"]}
    for _ in range(2):
        module._ledger_append(
            "core", "gate.evaluate", "Synthetic core policy example", "ALLOW",
            "F1", 0.90, simulated=True,
        )
    app = FastAPI()
    module.register(app)
    with TestClient(app) as client:
        yield module, client


def ledger_state(module):
    return copy.deepcopy(list(module._LEDGER)), dict(module._LEDGER_SEQ)


def forbid_read_writes(monkeypatch, module):
    def forbidden(*args, **kwargs):
        raise AssertionError("A ledger read attempted to append or sign a receipt")

    monkeypatch.setattr(module, "_ledger_append", forbidden)
    monkeypatch.setattr(module, "_sign", forbidden)


@pytest.mark.parametrize("route", LEDGER_ROUTES)
def test_default_get_does_not_advance_ledger(wow_ledger, monkeypatch, route):
    module, client = wow_ledger
    before = ledger_state(module)
    forbid_read_writes(monkeypatch, module)

    for _ in range(3):
        response = client.get(route)
        assert response.status_code == 200
        payload = response.json()
        assert payload["chain_depth"] == before[1]["n"]
        assert payload["final_hash"] == before[0][-1]["hash"]
        assert payload["receipts"] == list(reversed(before[0]))
        assert payload["window_verified"] is True
        assert ledger_state(module) == before


@pytest.mark.parametrize("route", LEDGER_ROUTES)
@pytest.mark.parametrize("limit", (1, 400))
def test_explicit_peek_preserves_full_ledger(wow_ledger, monkeypatch, route, limit):
    module, client = wow_ledger
    before = ledger_state(module)
    forbid_read_writes(monkeypatch, module)

    response = client.get(route, params={"advance": 0, "limit": limit})
    assert response.status_code == 200
    payload = response.json()
    assert payload["receipts"] == list(reversed(before[0][-limit:]))
    assert payload["chain_depth"] == before[1]["n"]
    assert payload["final_hash"] == before[0][-1]["hash"]
    assert ledger_state(module) == before


@pytest.mark.parametrize("route", LEDGER_ROUTES)
def test_explicit_advance_adds_only_a_simulated_record(wow_ledger, monkeypatch, route):
    module, client = wow_ledger
    before = ledger_state(module)

    response = client.get(route, params={"advance": 1})
    assert response.status_code == 200
    payload = response.json()
    newest = payload["receipts"][0]
    assert payload["chain_depth"] == before[1]["n"] + 1
    assert newest["seq"] == before[1]["n"]
    assert newest["prev_hash"] == before[0][-1]["hash"]
    assert newest["simulated"] is True
    assert newest["vertical"] == "core"
    assert payload["final_hash"] == newest["hash"]
    assert payload["window_verified"] is True

    advanced = ledger_state(module)
    assert advanced[0][:-1] == before[0]
    forbid_read_writes(monkeypatch, module)
    assert client.get(route).status_code == 200
    assert ledger_state(module) == advanced


@pytest.mark.parametrize("route", LEDGER_ROUTES)
def test_empty_ledger_get_does_not_seed_records(wow_ledger, monkeypatch, route):
    module, client = wow_ledger
    module._LEDGER.clear()
    module._LEDGER_SEQ["n"] = 0
    before = ledger_state(module)
    forbid_read_writes(monkeypatch, module)

    response = client.get(route)
    assert response.status_code == 200
    payload = response.json()
    assert payload["chain_depth"] == 0
    assert payload["final_hash"] == "GENESIS"
    assert payload["receipts"] == []
    assert ledger_state(module) == before
