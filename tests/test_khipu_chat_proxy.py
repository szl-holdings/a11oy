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
from szl_be_hardening import DOCTRINE_LOCK


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
    health_error = None
    chat_error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        _FakeAsyncClient.calls.append(("GET", url, None, None))
        if _FakeAsyncClient.health_error is not None:
            raise _FakeAsyncClient.health_error
        return _FakeResp(200, dict(_FakeAsyncClient.health))

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.calls.append(("POST", url, json, headers))
        if _FakeAsyncClient.chat_error is not None:
            raise _FakeAsyncClient.chat_error
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
    _FakeAsyncClient.health_error = None
    _FakeAsyncClient.chat_error = None

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
    assert body["pin"]["energy_attested_runs"] == "UNAVAILABLE"
    assert "not a trainer" in body["pin"]["forge_lab_role"]
    assert body["honesty"]["lab_v1"] == "https://szlholdings-szl-model-inference-lab.hf.space/v1"
    assert body["honesty"]["energy_attested_runs"] == "UNAVAILABLE"
    assert "not a trainer" in body["honesty"]["forge_lab"]
    assert body["honesty"]["ask_and_act"] == "not a live control plane"
    assert body["doctrine"]["source"] == "szl_be_hardening.DOCTRINE_LOCK"
    assert body["doctrine"]["state"] == "LOCKED"
    assert body["doctrine"]["locked_formula_count"] == DOCTRINE_LOCK["locked_formula_count"]
    assert body["doctrine"]["locked_formula_ids"] == DOCTRINE_LOCK["locked_formula_ids"]
    assert body["doctrine"]["lambda"] == DOCTRINE_LOCK["lambda"]
    assert body["measured_probe"]["label"] == "UNAVAILABLE"
    assert "measured_probe_2026_08_28" not in body
    assert "elapsed_ms" not in body["measured_probe"]
    assert "wall_s" not in body["measured_probe"]
    assert "signatures" not in body
    assert body["honesty"]["tokens_per_second"] == "not reported"
    assert "tok/s" not in r.text
    methods = [c[0] for c in _FakeAsyncClient.calls]
    assert "POST" not in methods


@pytest.mark.parametrize("ids,count", [
    ([{}], 1),
    ([[]], 1),
    (["F1"], True),
    (["F1", "F1"], 2),
    (["invalid"], 1),
    (["F1"], 2),
    (["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"], 9),
    (["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F23"], 8),
])
def test_malformed_doctrine_is_unavailable(proxy_client, monkeypatch, ids, count):
    client, chat = proxy_client
    monkeypatch.setattr(chat, "DOCTRINE_LOCK", {
        **DOCTRINE_LOCK,
        "locked_formula_ids": ids,
        "locked_formula_count": count,
    })

    response = client.get("/api/a11oy/v1/khipu/status")

    assert response.status_code == 200
    doctrine = response.json()["doctrine"]
    assert doctrine["state"] == "UNAVAILABLE"
    assert doctrine["version"] == "UNAVAILABLE"
    assert doctrine["locked_formula_count"] is None
    assert doctrine["locked_formula_ids"] == []


def test_status_failed_when_lab_not_ready(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.health = {"status": "LOADING"}
    r = client.get("/api/a11oy/v1/khipu/status")
    assert r.status_code == 200
    assert r.json()["lab_status"] == "FAILED"


def test_status_transport_failure_is_unavailable(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.health_error = OSError("network unavailable")

    r = client.get("/api/a11oy/v1/khipu/status")

    assert r.status_code == 200
    body = r.json()
    assert body["lab_status"] == "UNAVAILABLE"
    assert body["healthz"] is None
    assert "OSError" in body["error"]


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
    assert body["elapsed_ms_source"] == "PROXY_WALL"
    assert body["elapsed_ms_label"] == "MEASURED"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"
    assert "does not receive a receipt payload" in body["receipt_evidence_reason"]
    assert body["signature_evidence_label"] == "UNAVAILABLE"
    assert body["record_hash_evidence_label"] == "UNAVAILABLE"
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
    assert body["receipt_evidence_label"] == "UNAVAILABLE"
    assert body["signature_evidence_label"] == "UNAVAILABLE"
    assert body["record_hash_evidence_label"] == "UNAVAILABLE"
    assert body["text"] is None


def test_chat_incomplete_receipt_cannot_claim_measured_evidence(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat = {
        "choices": [{"message": {"content": "completion without a valid receipt"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "elapsed_ms": 12,
        "signature": "UNSIGNED",
        "record_sha256": "not-a-sha256",
    }

    r = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["elapsed_ms_label"] == "MEASURED"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"


def test_valid_looking_hash_and_signature_strings_do_not_prove_a_receipt(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat = {
        "choices": [{"message": {"content": "completion with reported receipt fields"}}],
        "signature": "SIGNED",
        "record_sha256": "a" * 64,
    }

    r = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})

    assert r.status_code == 200
    body = r.json()
    assert body["signature"] == "SIGNED"
    assert body["record_sha256"] == "a" * 64
    assert body["elapsed_ms_label"] == "MEASURED"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"
    assert body["signature_evidence_label"] == "UNAVAILABLE"
    assert body["record_hash_evidence_label"] == "UNAVAILABLE"


def test_generic_openai_id_is_not_receipt_hash_evidence(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat = {
        "id": "a" * 64,
        "choices": [{"message": {"content": "completion with only a generic response id"}}],
        "elapsed_ms": 12,
        "signature": "UNSIGNED",
    }

    r = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})

    assert r.status_code == 200
    body = r.json()
    assert body["record_sha256"] == "UNKNOWN"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"


def test_untrusted_negative_elapsed_never_surfaces_as_measured(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat = {
        "choices": [{"message": {"content": "completion with invalid upstream elapsed"}}],
        "elapsed_ms": -1,
        "signature": "UNSIGNED",
        "record_sha256": KHIPU_MEASURED_PROBE_2026_08_28["record_sha256"],
    }

    r = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})

    assert r.status_code == 200
    body = r.json()
    assert body["elapsed_ms"] >= 0
    assert body["elapsed_ms"] == body["wall_ms"]
    assert body["elapsed_ms"] != -1
    assert body["elapsed_ms_source"] == "PROXY_WALL"
    assert body["elapsed_ms_label"] == "MEASURED"


def test_chat_transport_failure_is_unavailable(proxy_client):
    client, _chat = proxy_client
    _FakeAsyncClient.chat_error = OSError("connection refused")

    response = client.post("/api/a11oy/v1/khipu/chat", json={"prompt": "hi"})

    assert response.status_code == 502
    body = response.json()
    assert body["ok"] is False
    assert body["lab_status"] == "UNAVAILABLE"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"
    assert body["signature_evidence_label"] == "UNAVAILABLE"
    assert body["record_hash_evidence_label"] == "UNAVAILABLE"
    assert "OSError" in body["error"]


def test_chat_requires_prompt(proxy_client):
    client, _chat = proxy_client
    r = client.post("/api/a11oy/v1/khipu/chat", json={})
    assert r.status_code == 422


def test_status_head_registered(proxy_client):
    client, _chat = proxy_client
    r = client.head("/api/a11oy/v1/khipu/status")
    assert r.status_code == 200
