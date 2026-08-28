# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""Hermetic tests for the same-origin Khipu CPU-lab proxy.

Never contacts the live lab. Dummy Bearer not-a-secret only. GET does not
sign. No tokens/s marketing number.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO = Path(__file__).parent.parent.resolve()
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.inference.src.voters.khipu_gguf import KHIPU_MEASURED_PROBE_2026_08_28


class _FakeResp:
    def __init__(self, status_code, payload, content_type="application/json"):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": content_type}

    def json(self):
        return self._payload


class _FakeAsyncClient:
    calls = []
    health = {"status": "READY"}
    chat = None
    chat_status = 200

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        _FakeAsyncClient.calls.append(("GET", url, None, None))
        return _FakeResp(200, dict(_FakeAsyncClient.health))

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.calls.append(("POST", url, json, headers))
        payload = _FakeAsyncClient.chat
        if payload is None:
            payload = {
                "choices": [{"message": {"content": "Khipu is a signed receipt DAG."}}],
                "usage": {"prompt_tokens": 51, "completion_tokens": 21, "total_tokens": 72},
                "elapsed_ms": 2053,
                "signature": "UNSIGNED",
                "record_sha256": KHIPU_MEASURED_PROBE_2026_08_28["record_sha256"],
            }
        return _FakeResp(_FakeAsyncClient.chat_status, payload)


@pytest.fixture
def proxy_client(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("starlette.testclient")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    monkeypatch.setenv("A11OY_KHIPU_LAB_BASE", "http://lab.test")
    monkeypatch.setenv("HF_TOKEN", "this-must-never-be-sent")
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.health = {"status": "READY"}
    _FakeAsyncClient.chat = None
    _FakeAsyncClient.chat_status = 200

    import a11oy_khipu_chat as chat

    app = FastAPI()
    chat.register(app)
    with patch("a11oy_khipu_chat.httpx.AsyncClient", _FakeAsyncClient):
        yield TestClient(app), chat


def test_status_ready_no_sign(proxy_client):
    client, _chat = proxy_client
    r = client.get("/api/a11oy/v1/khipu/status")
    assert r.status_code == 200
    body = r.json()
    assert body["lab_status"] == "READY"
    assert body["pin"]["gguf_sha256"] == "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
    assert body["pin"]["gpu_inference_endpoint"] == "ROADMAP"
    assert body["pin"]["lab_v1"].endswith("/v1")
    assert body["pin"]["locked_lab_v1"] == "https://szlholdings-szl-model-inference-lab.hf.space/v1"
    assert body["pin"]["energy_attested_runs"] == "8/8 SIMULATED"
    assert "not a trainer" in body["pin"]["forge_lab_role"]
    assert body["honesty"]["lab_v1"] == "https://szlholdings-szl-model-inference-lab.hf.space/v1"
    assert body["honesty"]["energy_attested_runs"] == "8/8 SIMULATED"
    assert "not a trainer" in body["honesty"]["forge_lab"]
    assert body["honesty"]["ask_and_act"] == "not a live control plane"
    assert body["doctrine"]["locked_formulas"] == 8
    assert body["doctrine"]["lambda"] == "Conjecture 1"
    assert "signatures" not in body
    assert body["honesty"]["tokens_per_second"] == "not reported"
    assert "tok/s" not in r.text
    methods = [c[0] for c in _FakeAsyncClient.calls]
    assert "POST" not in methods


def test_status_failed_when_lab_not_ready(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.health = {"status": "LOADING"}
    r = client.get("/api/a11oy/v1/khipu/status")
    assert r.status_code == 200
    assert r.json()["lab_status"] == "FAILED"


def test_chat_clamps_and_passes_unsigned(proxy_client):
    client, _chat = proxy_client
    r = client.post(
        "/api/a11oy/v1/khipu/chat",
        json={"prompt": "What is Khipu?", "max_tokens": 999, "temperature": 0.9, "stream": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["lab_status"] == "READY"
    assert body["signature"] == "UNSIGNED"
    assert body["record_sha256"] == KHIPU_MEASURED_PROBE_2026_08_28["record_sha256"]
    assert body["elapsed_ms_label"] == "MEASURED"
    assert body["usage_label"] == "REPORTED"
    assert "tokens_per_second" not in body
    assert body["honesty"]["lambda"] == "Conjecture 1"
    posted = [c for c in _FakeAsyncClient.calls if c[0] == "POST"]
    assert posted
    _method, url, payload, headers = posted[0]
    assert url == "http://lab.test/v1/chat/completions"
    assert payload["max_tokens"] == 32
    assert payload["temperature"] == 0.0
    assert payload["stream"] is False
    assert headers["Authorization"] == "Bearer not-a-secret"
    assert "this-must-never-be-sent" not in str(headers)


def test_chat_lab_http_error_is_failed(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat_status = 503
    _FakeAsyncClient.chat = {"error": "lab down"}
    r = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["lab_status"] == "FAILED"
    assert body["signature"] == "UNKNOWN"
    assert body["record_sha256"] == "UNKNOWN"
    assert body["text"] is None


def test_chat_requires_prompt(proxy_client):
    client, _chat = proxy_client
    r = client.post("/api/a11oy/v1/khipu/chat", json={})
    assert r.status_code == 422


def test_status_head_registered(proxy_client):
    client, _chat = proxy_client
    r = client.head("/api/a11oy/v1/khipu/status")
    assert r.status_code == 200
