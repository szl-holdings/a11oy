# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""Hermetic tests for the khipu-gguf sovereign voter.

Never contacts the live CPU lab. Dummy Bearer not-a-secret only — HF_TOKEN
is never read or sent. No tokens/s marketing number.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).parent.parent.resolve()
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.inference.src.voters.khipu_gguf import (
    KHIPU_GGUF_FILE,
    KHIPU_GGUF_SHA256,
    KHIPU_LAB_DUMMY_BEARER,
    KHIPU_MAX_TOKENS,
    KHIPU_MEASURED_PROBE_2026_08_28,
    KHIPU_MODEL_REPO,
    KHIPU_MODEL_REV,
    KHIPU_TEMPERATURE,
    KhipuGGUFVoter,
    SOVEREIGN_VOTER_ID,
    clamp_max_tokens,
    extract_lab_receipt,
    khipu_lab_base,
    khipu_pin,
)


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("POST", "http://lab.test/v1/chat/completions")
            raise httpx.HTTPStatusError(
                "lab error",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )


class _FakeAsyncClient:
    last_post = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.last_post = {"url": url, "json": json, "headers": headers}
        return _FakeResp(
            200,
            {
                "choices": [{"message": {"content": "Khipu is a signed receipt DAG."}}],
                "usage": {"prompt_tokens": 51, "completion_tokens": 21, "total_tokens": 72},
                "elapsed_ms": 2053,
                "signature": "UNSIGNED",
                "record_sha256": KHIPU_MEASURED_PROBE_2026_08_28["record_sha256"],
            },
        )


def test_pin_matches_measured_2026_08_28():
    pin = khipu_pin()
    assert pin["model_repo"] == "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
    assert pin["model_rev"] == "67d60ec577730747055491640cfb91fc4a4b5d25"
    assert pin["gguf_file"] == "SZL-Khipu-1.5B-Q4_K_M.gguf"
    assert pin["gguf_sha256"] == "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
    assert pin["max_tokens"] == 32
    assert pin["temperature"] == 0.0
    assert pin["stream"] is False
    assert pin["gpu_inference_endpoint"] == "ROADMAP"
    assert pin["forge_lab"] == "SNAPSHOT"
    assert pin["killinchu_detector"] == "SIMULATED"
    assert pin["lambda"] == "Conjecture 1"
    assert "tokens" not in pin
    assert KHIPU_MODEL_REPO == pin["model_repo"]
    assert KHIPU_MODEL_REV == pin["model_rev"]
    assert KHIPU_GGUF_FILE == pin["gguf_file"]
    assert KHIPU_GGUF_SHA256 == pin["gguf_sha256"]


def test_measured_probe_is_history_not_live_rate():
    probe = KHIPU_MEASURED_PROBE_2026_08_28
    assert probe["label"] == "MEASURED"
    assert probe["when"] == "2026-08-28 ~12:32pm ET"
    assert probe["wall_s"] == 2.498
    assert probe["elapsed_ms"] == 2053
    assert probe["signature"] == "UNSIGNED"
    assert "tokens_per_second" not in probe
    assert "tok/s" not in str(probe)


def test_clamp_max_tokens():
    assert clamp_max_tokens(999) == KHIPU_MAX_TOKENS
    assert clamp_max_tokens(0) == 1
    assert clamp_max_tokens("nope") == KHIPU_MAX_TOKENS
    assert clamp_max_tokens(8) == 8


def test_lab_base_override(monkeypatch):
    monkeypatch.setenv("A11OY_KHIPU_LAB_BASE", "http://127.0.0.1:9/")
    assert khipu_lab_base() == "http://127.0.0.1:9"


def test_extract_lab_receipt_unsigned():
    extracted = extract_lab_receipt(
        {
            "choices": [{"message": {"content": "ok"}}],
            "signature": "UNSIGNED",
            "record_sha256": "abc",
            "usage": {"total_tokens": 3},
            "elapsed_ms": 10,
        }
    )
    assert extracted["text"] == "ok"
    assert extracted["signature"] == "UNSIGNED"
    assert extracted["record_sha256"] == "abc"
    assert extracted["elapsed_ms"] == 10


def test_extract_lab_receipt_missing_fields_are_unknown():
    extracted = extract_lab_receipt({"choices": [{"message": {"content": "x"}}]})
    assert extracted["signature"] == "UNKNOWN"
    assert extracted["record_sha256"] == "UNKNOWN"


def test_dummy_bearer_is_not_a_secret_literal():
    assert KHIPU_LAB_DUMMY_BEARER == "not-a-secret"
    assert SOVEREIGN_VOTER_ID == "khipu-gguf"


def test_vote_clamps_and_uses_dummy_bearer_not_hf_token(monkeypatch):
    monkeypatch.setenv("A11OY_KHIPU_LAB_BASE", "http://lab.test")
    monkeypatch.setenv("HF_TOKEN", "this-must-never-be-sent")
    _FakeAsyncClient.last_post = None
    with patch("packages.inference.src.voters.khipu_gguf.httpx.AsyncClient", _FakeAsyncClient):
        result = asyncio.run(KhipuGGUFVoter().vote(prompt="hello", max_tokens=999, temperature=0.9))

    assert result["status"] == "ok"
    assert result["text"] == "Khipu is a signed receipt DAG."
    posted = _FakeAsyncClient.last_post
    assert posted is not None
    assert posted["url"] == "http://lab.test/v1/chat/completions"
    assert posted["json"]["max_tokens"] == 32
    assert posted["json"]["temperature"] == KHIPU_TEMPERATURE
    assert posted["json"]["stream"] is False
    assert posted["headers"]["Authorization"] == "Bearer not-a-secret"
    assert "this-must-never-be-sent" not in str(posted["headers"])
    assert "HF_TOKEN" not in str(posted["headers"])
    assert "tokens_per_second" not in result
    assert "tok/s" not in str(result)


def test_vote_lab_error_is_error_not_stub(monkeypatch):
    class _FailClient(_FakeAsyncClient):
        async def post(self, url, json=None, headers=None):
            return _FakeResp(503, {"error": "lab down"})

    monkeypatch.setenv("A11OY_KHIPU_LAB_BASE", "http://lab.test")
    with patch("packages.inference.src.voters.khipu_gguf.httpx.AsyncClient", _FailClient):
        result = asyncio.run(KhipuGGUFVoter().vote(prompt="hello"))

    assert result["status"] == "error"
    assert result["text"] is None
    assert "STUB" not in (result.get("reason") or "")
