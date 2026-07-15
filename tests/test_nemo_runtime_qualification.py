# SPDX-License-Identifier: Apache-2.0
"""Offline qualification tests for the SZL-Nemo Ollama runtime contract.

These tests never contact Ollama. They pin the two evidence boundaries that
matter for promotion: the exact upstream manifest must match, and an execution
failure must never be converted into synthetic model output.
"""

from __future__ import annotations

import a11oy_nemo_core as nemo


EXPECTED_UPSTREAM = nemo.NEMO_EXPECTED_REGISTRY_MANIFEST_SHA256
SERVED_DIGEST = "d" * 64


def _tags(*, upstream_digest=EXPECTED_UPSTREAM, include_served=True):
    models = [{
        "name": nemo.NEMO_UPSTREAM_OLLAMA_MODEL,
        "digest": upstream_digest,
    }]
    if include_served:
        models.append({
            "name": nemo.NEMO_SERVED_MODEL,
            "digest": SERVED_DIGEST,
        })
    return {"models": models}


def test_runtime_ready_requires_exact_upstream_and_derived_tag(monkeypatch):
    calls = []

    def fake_ollama(path, payload=None, timeout_s=8.0):
        calls.append((path, payload, timeout_s))
        return _tags()

    monkeypatch.setattr(nemo, "_ollama_json", fake_ollama)
    status = nemo.nemo_runtime_status()

    assert calls == [("/api/tags", None, 8.0)]
    assert status["state"] == "READY"
    assert status["upstream_manifest_match"] is True
    assert status["upstream_registry_manifest_sha256"] == EXPECTED_UPSTREAM
    assert status["served_model_digest"] == SERVED_DIGEST
    assert status["szl_fine_tuned"] is False
    assert status["training_state"] == "NOT_FINE_TUNED"


def test_runtime_refuses_wrong_upstream_manifest(monkeypatch):
    monkeypatch.setattr(
        nemo, "_ollama_json",
        lambda *_args, **_kwargs: _tags(upstream_digest="f" * 64),
    )
    status = nemo.nemo_runtime_status()

    assert status["state"] == "UNAVAILABLE"
    assert status["upstream_manifest_match"] is False
    assert status["served_model_digest"] == SERVED_DIGEST


def test_runtime_refuses_missing_derived_recipe_tag(monkeypatch):
    monkeypatch.setattr(
        nemo, "_ollama_json",
        lambda *_args, **_kwargs: _tags(include_served=False),
    )
    status = nemo.nemo_runtime_status()

    assert status["state"] == "UNAVAILABLE"
    assert status["upstream_manifest_match"] is True
    assert status["served_model_digest"] is None


def test_runtime_transport_failure_is_honest_unavailable(monkeypatch):
    def down(*_args, **_kwargs):
        raise ConnectionError("offline fixture")

    monkeypatch.setattr(nemo, "_ollama_json", down)
    status = nemo.nemo_runtime_status()

    assert status["state"] == "UNAVAILABLE"
    assert status["error_type"] == "ConnectionError"
    assert status["served_model_digest"] is None
    assert status["upstream_manifest_match"] is False
    assert "no model output is fabricated" in status["honesty"].lower()


def test_infer_execute_true_returns_measured_generation_without_promotion(monkeypatch):
    runtime = {
        "schema": "szl.nemo.runtime-status/v1",
        "state": "READY",
        "served_model": "szl-nemo:latest",
        "served_model_digest": SERVED_DIGEST,
        "upstream_registry_manifest_sha256": EXPECTED_UPSTREAM,
        "szl_fine_tuned": False,
        "training_state": "NOT_FINE_TUNED",
    }
    measured = {
        "state": "ANSWERED_UNVERIFIED",
        "answer": "fixture answer",
        "answer_sha256": "a" * 64,
        "observed_model": "szl-nemo:latest",
        "quality_state": "UNVERIFIED_MODEL_OUTPUT",
        "training_state": "NOT_FINE_TUNED",
    }
    observed = {}

    monkeypatch.setattr(nemo, "nemo_runtime_status", lambda: dict(runtime))

    def fake_generate(query, supplied_runtime):
        observed["query"] = query
        observed["runtime"] = supplied_runtime
        return dict(measured)

    monkeypatch.setattr(nemo, "_live_nemo_generate", fake_generate)
    result = nemo.infer("identify yourself", top_k=1, execute=True)

    assert observed == {"query": "identify yourself", "runtime": runtime}
    assert result["execution_requested"] is True
    assert result["execution_state"] == "ANSWERED_UNVERIFIED"
    assert result["generation"] == measured
    assert result["generation"]["quality_state"] == "UNVERIFIED_MODEL_OUTPUT"
    assert result["generation"]["training_state"] == "NOT_FINE_TUNED"
    assert result["receipt"]["signed"] is False


def test_live_generate_disables_hidden_thinking_channel(monkeypatch):
    runtime = {
        "state": "READY",
        "served_model": "szl-nemo:latest",
        "served_model_digest": SERVED_DIGEST,
        "upstream_registry_manifest_sha256": EXPECTED_UPSTREAM,
    }
    calls = []

    def fake_ollama(path, payload=None, timeout_s=8.0):
        calls.append((path, payload, timeout_s))
        return {
            "model": runtime["served_model"],
            "response": "measured answer",
            "eval_count": 3,
            "eval_duration": 1,
            "load_duration": 2,
        }

    monkeypatch.setattr(nemo, "_ollama_json", fake_ollama)
    generation = nemo._live_nemo_generate("identify yourself", runtime)

    assert calls[0][0] == "/api/generate"
    assert calls[0][1]["think"] is False
    assert calls[0][1]["stream"] is False
    assert calls[0][2] == 180.0
    assert generation["answer"] == "measured answer"
    assert generation["observed_model"] == runtime["served_model"]
    assert generation["quality_state"] == "UNVERIFIED_MODEL_OUTPUT"


def test_infer_execute_true_fails_closed_when_runtime_unavailable(monkeypatch):
    runtime = {
        "schema": "szl.nemo.runtime-status/v1",
        "state": "UNAVAILABLE",
        "served_model": "szl-nemo:latest",
        "served_model_digest": None,
        "upstream_manifest_match": False,
        "szl_fine_tuned": False,
        "training_state": "NOT_FINE_TUNED",
    }
    transport_called = False

    monkeypatch.setattr(nemo, "nemo_runtime_status", lambda: dict(runtime))

    def forbidden_transport(*_args, **_kwargs):
        nonlocal transport_called
        transport_called = True
        raise AssertionError("transport must not run when identity is unavailable")

    monkeypatch.setattr(nemo, "_ollama_json", forbidden_transport)
    result = nemo.infer("do not fabricate", top_k=1, execute=True)

    assert transport_called is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["generation"] is None
    assert result["runtime_error_type"] == "RuntimeError"
    assert "no fallback or demo answer was fabricated" in result["skeleton_note"].lower()
