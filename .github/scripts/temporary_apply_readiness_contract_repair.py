#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

GENERATOR = Path("tools/readiness-harness/gen_tabs_matrix.py")
TEST = Path("tests/test_readiness_runtime_contract_alignment.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} predecessor count must be 1, observed {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = GENERATOR.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '        allow_labels=("live", "cached", "reference", "unofficial-fallback"),\n'
        '        note="Live Yahoo/macro finance feed; cold-burst 404 tolerated, re-probe."),',
        '        allow_labels=("live", "cached", "stale", "reference", "unofficial-fallback"),\n'
        '        note=(\n'
        '            "Live Yahoo/macro finance feed. Official-equity observations may "\n'
        '            "honestly declare freshness.status=stale outside an active market "\n'
        '            "session; the observation clock must still satisfy the one-hour SLA. "\n'
        '            "The stale label is never upgraded to live."\n'
        '        )),',
        "finance endpoint contract",
    )

    old_router = '''    # router/stats: the current endpoint is a deterministic modeled display of
    #   the real tier catalog. It is not production traffic, QPS, tokens,
    #   completed inference, or an observed routing-decision counter.
    "/api/a11oy/v1/router/stats": ep(
        schema="router_stats",
        sla=None,
        allow_labels=("live", "cached", "modeled"),
        note=(
            "Deterministic MODELED tier-display signals from szl_brain.TIERS; "
            "not production traffic, QPS, tokens, or completed inference."
        ),
    ),
'''
    new_router = '''    # router/stats: exact process-lifetime routing-decision counters. The
    # counters increment only on trusted routing-receipt writes and reset on
    # process rebuild. They are not QPS, tokens, inference completions, or
    # traffic outside this process. Zero is a valid observed count.
    "/api/a11oy/v1/router/stats": ep(
        schema="router_stats",
        sla=None,
        allow_labels=("live", "cached", "degraded", "unavailable"),
        note=(
            "LIVE/OBSERVED process-lifetime routing-decision counts from "
            "szl_llm_registry.router_stats_snapshot. Legacy throughput and "
            "servedThisWindow fields carry that count, never QPS or tokens. "
            "Registry failure is honestly UNAVAILABLE; catalog drift is DEGRADED."
        ),
    ),
'''
    text = replace_once(text, old_router, new_router, "router endpoint contract")

    router_schema = '''    "router_stats": {
        "anyOf": [
            {
                "type": "object",
                "required": [
                    "state", "mode", "data_kind", "catalog_state",
                    "throughput_state", "routes", "servedThisWindow",
                    "routingDecisionsSinceStart", "tiers", "counter_scope",
                    "counter_started_at", "observed_at", "source", "doctrine",
                    "honesty",
                ],
                "requiredPathTypes": {
                    "routes": "nonempty_array",
                    "servedThisWindow": "nonnegative_integer",
                    "routingDecisionsSinceStart": "nonnegative_integer",
                    "tiers": "nonempty_array",
                    "counter_scope": "string",
                    "counter_started_at": "timestamp",
                    "observed_at": "timestamp",
                    "honesty": "string",
                },
                "properties": {
                    "state": {"const": "LIVE"},
                    "mode": {"const": "live"},
                    "data_kind": {"const": "live"},
                    "catalog_state": {"const": "LIVE"},
                    "throughput_state": {"const": "OBSERVED"},
                    "source": {"const": "szl_llm_registry.router_stats_snapshot"},
                    "doctrine": {"const": "v11"},
                },
            },
            {
                "type": "object",
                "required": [
                    "state", "mode", "data_kind", "catalog_state",
                    "throughput_state", "routes", "servedThisWindow",
                    "routingDecisionsSinceStart", "tiers", "counter_scope",
                    "counter_started_at", "observed_at", "source", "doctrine",
                    "honesty",
                ],
                "requiredPathTypes": {
                    "routes": "nonempty_array",
                    "servedThisWindow": "nonnegative_integer",
                    "routingDecisionsSinceStart": "nonnegative_integer",
                    "tiers": "nonempty_array",
                    "counter_scope": "string",
                    "counter_started_at": "timestamp",
                    "observed_at": "timestamp",
                    "honesty": "string",
                },
                "properties": {
                    "state": {"const": "DEGRADED"},
                    "mode": {"const": "degraded"},
                    "data_kind": {"const": "live"},
                    "catalog_state": {"const": "DRIFT"},
                    "throughput_state": {"const": "OBSERVED"},
                    "source": {"const": "szl_llm_registry.router_stats_snapshot"},
                    "doctrine": {"const": "v11"},
                },
            },
            {
                "type": "object",
                "required": [
                    "state", "mode", "data_kind", "catalog_state",
                    "throughput_state", "routes", "servedThisWindow",
                    "routingDecisionsSinceStart", "tiers", "counter_scope",
                    "counter_started_at", "observed_at", "source", "doctrine",
                    "honesty",
                ],
                "requiredPathTypes": {
                    "routes": "array",
                    "tiers": "array",
                    "counter_scope": "string",
                    "observed_at": "timestamp",
                    "honesty": "string",
                },
                "properties": {
                    "state": {"const": "UNAVAILABLE"},
                    "mode": {"const": "unavailable"},
                    "data_kind": {"const": "unavailable"},
                    "catalog_state": {"const": "UNAVAILABLE"},
                    "throughput_state": {"const": "UNAVAILABLE"},
                    "source": {"const": "unavailable"},
                    "doctrine": {"const": "v11"},
                },
            },
        ],
    },
'''
    pattern = re.compile(
        r'^    "router_stats": \{.*?^    \},\n(?=    "feeds_pulse":)',
        re.MULTILINE | re.DOTALL,
    )
    text, count = pattern.subn(router_schema, text, count=1)
    if count != 1:
        raise SystemExit(f"router schema predecessor count must be 1, observed {count}")
    GENERATOR.write_text(text, encoding="utf-8", newline="\n")

    TEST.write_text(
        '''# SPDX-License-Identifier: Apache-2.0
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
''',
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
