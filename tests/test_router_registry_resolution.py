# SPDX-License-Identifier: Apache-2.0
"""Regressions for one canonical router-counter registry per process."""
from __future__ import annotations

import sys
from types import ModuleType

from fastapi.testclient import TestClient

import serve
import szl_llm_registry as vendored_registry
import szl_model_harness as harness


client = TestClient(serve.app)


def _optional_package(registry: ModuleType) -> ModuleType:
    package = ModuleType("szl_substrate")
    package.szl_llm_registry = registry
    return package


def _counter_capable_registry() -> ModuleType:
    registry = ModuleType("szl_substrate.szl_llm_registry")
    counts: dict[tuple[int, str], int] = {}
    registry.MODEL_REGISTRY = [{"tier": 2, "model_id": "optional-model"}]
    registry.register = lambda app: {"endpoints": []}

    def forum_append(receipt, *, routing_decision=False):
        if routing_decision:
            key = (receipt["tier_selected"], receipt["model_id"])
            counts[key] = counts.get(key, 0) + 1

    def snapshot():
        routes = [
            {"tier": tier, "model_id": model_id, "routing_decisions": count}
            for (tier, model_id), count in sorted(counts.items())
        ]
        return {
            "state": "LIVE",
            "counter_state": "OBSERVED",
            "counter_scope": "process_lifetime",
            "counter_started_at": "2026-08-26T12:00:00Z",
            "observed_at": "2026-08-26T12:00:01Z",
            "routing_decisions_total": sum(item["routing_decisions"] for item in routes),
            "routes": routes,
        }

    registry._forum_append = forum_append
    registry.router_stats_snapshot = snapshot
    return registry


def test_optional_substrate_writer_and_stats_reader_share_one_module(monkeypatch):
    optional_registry = _counter_capable_registry()
    package = _optional_package(optional_registry)
    monkeypatch.setitem(sys.modules, "szl_substrate", package)
    monkeypatch.setitem(
        sys.modules, "szl_substrate.szl_llm_registry", optional_registry
    )
    monkeypatch.delattr(serve, "_llm_reg", raising=False)
    monkeypatch.setattr(harness, "_REGISTRY_MODULE", None)
    monkeypatch.setattr(serve, "_llm_reg_info", {"endpoints": []})

    resolved = serve._resolve_llm_registry_module()
    harness._bind_registry(resolved)
    result = harness._forum_ingest({"tier_selected": 2, "model_id": "optional-model"})

    assert result["ingested"] is True
    assert resolved is optional_registry
    assert harness._reg() is optional_registry
    stats = client.get("/v1/router/stats").json()
    assert stats["state"] == "LIVE"
    assert stats["servedThisWindow"] == 1
    assert stats["routes"][0]["routing_decisions"] == 1


def test_stale_optional_substrate_falls_back_to_vendored_counter(monkeypatch):
    stale_registry = ModuleType("szl_substrate.szl_llm_registry")
    stale_registry.MODEL_REGISTRY = [{"tier": 2, "model_id": "stale-model"}]
    stale_registry.register = lambda app: {"endpoints": []}
    stale_registry._forum_append = lambda receipt, **kwargs: None
    package = _optional_package(stale_registry)
    monkeypatch.setitem(sys.modules, "szl_substrate", package)
    monkeypatch.setitem(sys.modules, "szl_substrate.szl_llm_registry", stale_registry)
    monkeypatch.delattr(serve, "_llm_reg", raising=False)
    monkeypatch.setattr(harness, "_REGISTRY_MODULE", None)
    monkeypatch.setattr(serve, "_llm_reg_info", {"endpoints": []})
    monkeypatch.setattr(vendored_registry, "_FORUM_LOG", [])
    monkeypatch.setattr(vendored_registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(
        vendored_registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z"
    )

    resolved = serve._resolve_llm_registry_module()
    harness._bind_registry(resolved)
    result = harness._forum_ingest({"tier_selected": 2, "model_id": "gpt_5_4"})

    assert result["ingested"] is True
    assert resolved is vendored_registry
    assert harness._reg() is vendored_registry
    stats = client.get("/v1/router/stats").json()
    assert stats["state"] == "LIVE"
    assert stats["servedThisWindow"] == 1


def test_partial_optional_writer_without_decision_keyword_falls_back(monkeypatch):
    partial_registry = _counter_capable_registry()
    partial_registry._forum_append = lambda receipt: None
    package = _optional_package(partial_registry)
    monkeypatch.setitem(sys.modules, "szl_substrate", package)
    monkeypatch.setitem(sys.modules, "szl_substrate.szl_llm_registry", partial_registry)
    monkeypatch.delattr(serve, "_llm_reg", raising=False)
    monkeypatch.setattr(harness, "_REGISTRY_MODULE", None)

    resolved = serve._resolve_llm_registry_module()

    assert callable(partial_registry.router_stats_snapshot)
    assert resolved is vendored_registry


def test_pre_server_trusted_write_keeps_registry_when_optional_appears(monkeypatch):
    optional_registry = _counter_capable_registry()
    package = _optional_package(optional_registry)
    monkeypatch.setitem(sys.modules, "szl_substrate", package)
    monkeypatch.setitem(
        sys.modules, "szl_substrate.szl_llm_registry", optional_registry
    )
    monkeypatch.setattr(harness, "_REGISTRY_MODULE", None)
    monkeypatch.delattr(serve, "_llm_reg", raising=False)
    monkeypatch.setattr(serve, "_llm_reg_info", {"endpoints": []})
    monkeypatch.setattr(vendored_registry, "_FORUM_LOG", [])
    monkeypatch.setattr(vendored_registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(
        vendored_registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z"
    )

    result = harness._forum_ingest({"tier_selected": 2, "model_id": "gpt_5_4"})
    resolved = serve._resolve_llm_registry_module()
    bound_registry = harness._bind_registry(resolved)

    assert result["ingested"] is True
    assert resolved is vendored_registry
    assert bound_registry is vendored_registry
    assert harness._reg() is vendored_registry
    stats = client.get("/v1/router/stats").json()
    assert stats["state"] == "LIVE"
    assert stats["servedThisWindow"] == 1
