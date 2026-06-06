"""Integration tests for rosie.console.a11oy_client.

Boots a real stdlib http.server on an ephemeral port that mimics a11oy's
`serve` route contract and exercises every A11oyClient method over real TCP.
No mocked transport: each request crosses a socket and the real JSON response
is parsed back. This proves rosie's instilled a11oy wire actually issues the
correct method/path/body and parses a11oy's real response shapes.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import pytest

from src.console.a11oy_client import A11oyClient, A11oyError, client_from_env

# The a11oy_server fixture is provided by test/conftest.py (a real stdlib
# http.server mimicking the a11oy serve contract).


class TestA11oyClient:
    def test_health_and_ready(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        assert c.health()["status"] == "ok"
        assert c.health()["sha"] == "abc123"
        assert c.ready()["status"] == "ready"

    def test_ledger_carries_limit(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        page = c.ledger(limit=7)
        assert page["count"] == 1
        assert page["receipts"][0]["limit"] == 7

    def test_receipt_by_hash(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        out = c.receipt("m-1")
        assert out["receipt"]["receipt_id"] == "m-1"

    def test_verify_valid_and_invalid(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        ok = c.verify([{"receipt_id": "r-1"}])
        assert ok.valid is True
        assert ok.broken_at is None
        bad = c.verify([])
        assert bad.valid is False
        assert bad.broken_at == 0

    def test_policy_allow_and_deny(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        allow = c.evaluate_policy(action_id="a", severity="low", confidence=0.9)
        assert allow.allowed is True
        assert allow.gate == "thresholdPolicySeverity"
        deny = c.evaluate_policy(action_id="b", severity="critical")
        assert deny.allowed is False
        assert deny.decision == "deny"

    def test_unreachable_raises_a11oy_error(self):
        c = A11oyClient("http://127.0.0.1:1", timeout=0.5)
        with pytest.raises(A11oyError):
            c.health()

    def test_non_2xx_raises_with_status(self, a11oy_server):
        c = A11oyClient(a11oy_server)
        with pytest.raises(A11oyError) as exc:
            c._request("GET", "/does-not-exist")  # unmatched path -> real 404
        assert exc.value.status == 404

    def test_client_from_env(self):
        assert client_from_env({}) is None
        c = client_from_env({"ROSIE_A11OY_URL": "http://a11oy:8080"})
        assert c is not None and c.base_url == "http://a11oy:8080"
