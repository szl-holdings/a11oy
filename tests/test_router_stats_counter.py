# SPDX-License-Identifier: Apache-2.0
"""Exactness and trust-boundary tests for live router decision counters."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

import szl_llm_registry as registry
import szl_model_harness as harness


@pytest.fixture
def isolated_counter(monkeypatch):
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    monkeypatch.setattr(registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z")


def _receipt(tier: int = 2, model_id: str = "gpt_5_4") -> dict:
    return {
        "schema": "szl.llm_route.lambda_receipt/v1",
        "tier_selected": tier,
        "model_id": model_id,
        "ts": "2026-08-26T12:00:01Z",
    }


def test_trusted_receipt_writes_increment_exact_route_and_total(isolated_counter) -> None:
    registry._forum_append(_receipt(), routing_decision=True)
    registry._forum_append(_receipt(), routing_decision=True)
    registry._forum_append(_receipt(5, "szl-sovereign-local"), routing_decision=True)

    snapshot = registry.router_stats_snapshot()

    assert snapshot["state"] == "LIVE"
    assert snapshot["counter_state"] == "OBSERVED"
    assert snapshot["counter_scope"] == "process_lifetime"
    assert snapshot["counter_started_at"] == "2026-08-26T12:00:00Z"
    assert snapshot["routing_decisions_total"] == 3
    assert snapshot["routes"] == [
        {"tier": 2, "model_id": "gpt_5_4", "routing_decisions": 2},
        {"tier": 5, "model_id": "szl-sovereign-local", "routing_decisions": 1},
    ]
    assert "MEASURED" not in str(snapshot)


def test_plain_forum_ingest_cannot_inflate_router_counter(isolated_counter) -> None:
    # /llm/forum/ingest uses the default flag. Even a body shaped like a routing
    # receipt is untrusted data and must not become operational telemetry.
    registry._forum_append(_receipt())

    snapshot = registry.router_stats_snapshot()

    assert len(registry._FORUM_LOG) == 1
    assert snapshot["routing_decisions_total"] == 0
    assert snapshot["routes"] == []


@pytest.mark.parametrize(
    "receipt",
    [
        {"tier_selected": True, "model_id": "gpt_5_4"},
        {"tier_selected": -1, "model_id": "gpt_5_4"},
        {"tier_selected": "2", "model_id": "gpt_5_4"},
        {"tier_selected": "2.0", "model_id": "gpt_5_4"},
        {"tier_selected": 2, "model_id": ""},
        {"tier_selected": 2, "model_id": 54},
    ],
)
def test_invalid_trusted_receipt_fails_before_any_mutation(
    isolated_counter, receipt: dict
) -> None:
    with pytest.raises(ValueError):
        registry._forum_append(receipt, routing_decision=True)

    assert registry._FORUM_LOG == []
    assert registry.router_stats_snapshot()["routing_decisions_total"] == 0


def test_concurrent_writers_do_not_lose_decisions(isolated_counter) -> None:
    writes_per_thread = 100
    threads = [
        threading.Thread(
            target=lambda: [
                registry._forum_append(_receipt(), routing_decision=True)
                for _ in range(writes_per_thread)
            ]
        )
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    snapshot = registry.router_stats_snapshot()
    assert snapshot["routing_decisions_total"] == 8 * writes_per_thread
    assert snapshot["routes"] == [
        {
            "tier": 2,
            "model_id": "gpt_5_4",
            "routing_decisions": 8 * writes_per_thread,
        }
    ]
    # The forum ring may truncate, but the independent process counter may not.
    assert len(registry._FORUM_LOG) == registry._FORUM_MAX


def test_sovereign_harness_override_is_counted_under_sovereign_tier(
    isolated_counter, monkeypatch
) -> None:
    fake_sovereign = SimpleNamespace(
        SOVEREIGN_BACKEND_ID="sovereign_local",
        is_sovereign=lambda model_id: model_id == "sovereign",
        run_on_sovereign=lambda prompt, requested_model_id: {
            "state": "UNAVAILABLE",
            "note": "test node is offline",
        },
        receipt_block=lambda result: {
            "backend_id": "sovereign_local",
            "state": result["state"],
        },
    )
    monkeypatch.setattr(harness, "_SOV_OK", True)
    monkeypatch.setattr(harness, "_sov", fake_sovereign)
    monkeypatch.setattr(
        harness,
        "_sign_receipt",
        lambda receipt: {"signed": False, "honesty": "test signer unavailable"},
    )

    result = harness.apply(
        "szl-honest-operator",
        model_id="sovereign",
        prompt="attribute the sovereign override",
        forum=True,
    )

    assert result["ok"] is True
    assert result["receipt"]["model_id"] == "sovereign_local"
    assert result["receipt"]["tier_selected"] == 5
    assert result["model_selected"]["tier"] == 5
    assert registry.router_stats_snapshot()["routes"] == [
        {
            "tier": 5,
            "model_id": "sovereign_local",
            "routing_decisions": 1,
        }
    ]
