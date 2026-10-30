# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Shared brain counts describe only a manifest observed in the same Space."""
import json
from types import SimpleNamespace

import pytest

import szl_brain as brain


@pytest.fixture(autouse=True)
def isolated_inventory(monkeypatch):
    monkeypatch.setattr(brain, "_MCP_INVENTORY_OBSERVATION", None)


@pytest.mark.parametrize("space", ["a11oy", "killinchu"])
def test_no_observation_is_unknown_not_an_empty_inventory(space):
    canonical = brain.brain_payload(space)["canonical"]
    assert canonical["mcp_tools"] is None
    assert canonical["mcp_inventory"]["source"] is None
    assert canonical["mcp_inventory"]["reason"] == "MCP_MANIFEST_NOT_OBSERVED"


@pytest.mark.parametrize("space,other", [("a11oy", "killinchu"), ("killinchu", "a11oy")])
def test_observed_empty_inventory_has_its_own_source_and_never_crosses_spaces(space, other):
    brain.observe_mcp_inventory({"tools": [], "count": 12}, space=space)
    observed = brain.brain_payload(space)["canonical"]
    assert observed["mcp_tools"] == 0
    assert observed["mcp_inventory"]["source"] == f"/api/{space}/v1/mcp/tools"
    assert observed["mcp_inventory"]["label"] == "CACHED"
    assert observed["mcp_inventory"]["scope"] == "ADVERTISED_MANIFEST_ONLY"
    assert observed["mcp_inventory"]["capability_readiness_asserted"] is False
    unobserved = brain.brain_payload(other)["canonical"]
    assert unobserved["mcp_tools"] is None
    assert unobserved["mcp_inventory"]["source"] is None
    assert brain.CANONICAL["mcp_tools"] is None


@pytest.mark.parametrize("clock", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_bad_observation_clock_never_yields_a_count_or_nonfinite_json(monkeypatch, clock):
    monkeypatch.setattr(brain, "time", SimpleNamespace(monotonic=lambda: 100.0))
    brain.observe_mcp_inventory({"tools": [{"name": "synthetic"}]}, space="killinchu")
    monkeypatch.setattr(brain, "time", SimpleNamespace(monotonic=lambda: clock))
    inventory = brain.mcp_inventory_snapshot("killinchu")
    assert inventory["count"] is None
    assert inventory["reason"] == "MCP_MANIFEST_CLOCK_UNAVAILABLE"
    json.dumps(inventory, allow_nan=False)


def test_failed_wall_clock_does_not_interrupt_manifest_observation(monkeypatch):
    def fail(*args):
        raise OSError("synthetic wall-clock failure")

    monkeypatch.setattr(brain, "datetime", SimpleNamespace(now=fail))
    brain.observe_mcp_inventory({"tools": [{"name": "synthetic"}]}, space="killinchu")
    assert brain.mcp_inventory_snapshot("killinchu")["count"] is None


def test_malformed_manifest_is_unknown_with_explicit_reason():
    brain.observe_mcp_inventory({"tools": [{"name": None}]}, space="a11oy")
    inventory = brain.mcp_inventory_snapshot("a11oy")
    assert inventory["count"] is None
    assert inventory["label"] == "UNAVAILABLE"
    assert inventory["reason"] == "MCP_MANIFEST_INVALID"
    assert inventory["source"] == "/api/a11oy/v1/mcp/tools"
