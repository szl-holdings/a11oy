# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
import serve

ROOT = Path(__file__).resolve().parents[1]


def _matrix():
    path = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
    spec = importlib.util.spec_from_file_location("readiness_matrix_alignment", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def _timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _matches(rule, payload):
    if rule.get("type") != "object" or not isinstance(payload, dict):
        return False
    if any(key not in payload for key in rule.get("required", [])):
        return False
    for key, item in rule.get("properties", {}).items():
        if "const" in item and payload.get(key) != item["const"]:
            return False
    for key, kind in rule.get("requiredPathTypes", {}).items():
        value = payload.get(key)
        if kind == "array" and not isinstance(value, list):
            return False
        if kind == "nonempty_array" and not (isinstance(value, list) and value):
            return False
        if kind == "string" and not isinstance(value, str):
            return False
        if kind == "nonnegative_integer" and not (
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
        ):
            return False
        if kind == "timestamp" and not _timestamp(value):
            return False
    return True


def _schema_matches(schema, payload):
    return any(_matches(rule, payload) for rule in schema["anyOf"])


def test_finance_contract_admits_only_explicitly_labeled_stale_observations():
    contract = _matrix()["endpoints"]["/api/a11oy/v1/vert/finance/feed"]
    allowed = set(contract["degradedRules"]["allowLabels"])
    assert "stale" in allowed
    assert not {"mock", "fabricated", "placeholder"} & allowed
    assert "observation clock" in contract["note"]
    assert "never upgraded to live" in contract["note"]


def test_live_router_payload_matches_observed_counter_schema():
    matrix = _matrix()
    contract = matrix["endpoints"]["/api/a11oy/v1/router/stats"]
    response = TestClient(serve.app).get("/api/a11oy/v1/router/stats")
    assert response.status_code == 200
    payload = response.json()
    assert _schema_matches(matrix["schemas"]["router_stats"], payload)
    assert payload["throughput_state"] == "OBSERVED"
    assert payload["source"] == "szl_llm_registry.router_stats_snapshot"
    assert "modeled" not in contract["degradedRules"]["allowLabels"]


def test_unavailable_router_payload_matches_fail_closed_schema(monkeypatch):
    matrix = _matrix()
    monkeypatch.setattr(serve, "_llm_reg_info", None)
    response = TestClient(serve.app).get("/api/a11oy/v1/router/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "UNAVAILABLE"
    assert payload["servedThisWindow"] is None
    assert payload["routes"] == []
    assert _schema_matches(matrix["schemas"]["router_stats"], payload)
