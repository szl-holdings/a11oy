# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Dedicated public inventory credentials; no fallback after rejection."""
import asyncio
import json

import httpx
import pytest

from routers import series_a_control_plane as control


@pytest.mark.parametrize("dedicated", [None, "synthetic-public-read-token"])
def test_public_inventory_ignores_generic_runtime_token(monkeypatch, dedicated):
    monkeypatch.setenv("GITHUB_TOKEN", "expired-generic-token-do-not-forward")
    if dedicated:
        monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", dedicated)
    else:
        monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)
    requests = []
    real_client = httpx.AsyncClient
    def response(request):
        requests.append(request)
        assert "expired-generic-token" not in str(request.headers)
        assert request.headers.get("authorization") == (f"Bearer {dedicated}" if dedicated else None)
        if request.url.path == "/search/issues":
            return httpx.Response(200, json={"total_count": 4})
        return httpx.Response(200, json=[{"name": "vertical-services", "private": False,
                                         "visibility": "public", "default_branch": "main"}])
    monkeypatch.setattr(control.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    collector = control.Collector()
    result = asyncio.run(collector.github())
    assert result.state == "OBSERVED"
    assert result.value["repository_count"] == 1
    assert collector.github_authentication_mode == ("DEDICATED_PUBLIC_READ_TOKEN" if dedicated else "PUBLIC_ANONYMOUS")
    assert result.detail == {"authenticated": bool(dedicated)}
    assert dedicated is None or dedicated not in json.dumps(result.as_dict())
    assert len(requests) == 2


def test_rejected_dedicated_credential_remains_unavailable_without_anonymous_retry(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "irrelevant-generic-token")
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", "rejected-dedicated-token")
    calls = []
    real_client = httpx.AsyncClient
    def response(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer rejected-dedicated-token"
        return httpx.Response(401, json={"message": "Bad credentials"})
    monkeypatch.setattr(control.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    result = asyncio.run(control.Collector().github())
    assert result.state == "UNAVAILABLE"
    assert len(calls) == 1
    assert "rejected-dedicated-token" not in json.dumps(result.as_dict())
