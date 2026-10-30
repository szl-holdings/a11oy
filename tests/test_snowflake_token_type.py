# SPDX-License-Identifier: Apache-2.0
"""Snowflake SQL API token type is operator-selected, never guessed."""
from __future__ import annotations

import szl_connectors.warehouse.warehouse_connectors as wc


def _capture(monkeypatch):
    calls = []

    def fake_http_json(url, headers=None, method="GET", data=None, timeout=None):
        calls.append({"url": url, "headers": dict(headers or {})})
        return 200, {"data": []}

    monkeypatch.setattr(wc, "http_json", fake_http_json)
    monkeypatch.setenv("SZL_SNOWFLAKE_ACCOUNT", "orgname-acct")
    monkeypatch.setenv("SZL_SNOWFLAKE_ACCESS_TOKEN", "test-token-not-a-secret")
    return calls


def test_default_token_type_stays_oauth(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.delenv("SZL_SNOWFLAKE_TOKEN_TYPE", raising=False)

    wc.SnowflakeConnector().read()

    assert calls[0]["headers"]["X-Snowflake-Authorization-Token-Type"] == "OAUTH"


def test_programmatic_access_token_type_is_sent(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setenv("SZL_SNOWFLAKE_TOKEN_TYPE", "PROGRAMMATIC_ACCESS_TOKEN")

    wc.SnowflakeConnector().read()

    assert calls[0]["url"] == "https://orgname-acct.snowflakecomputing.com/api/v2/statements"
    assert calls[0]["headers"]["X-Snowflake-Authorization-Token-Type"] == "PROGRAMMATIC_ACCESS_TOKEN"


def test_unknown_token_type_refuses_without_calling_snowflake(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setenv("SZL_SNOWFLAKE_TOKEN_TYPE", "BASIC")

    rec = wc.SnowflakeConnector().read()

    assert calls == []
    assert rec.state == wc.State.ERROR
    assert rec.live is False
    assert "SZL_SNOWFLAKE_TOKEN_TYPE" in rec.note
