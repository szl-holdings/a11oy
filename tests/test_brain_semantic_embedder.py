# SPDX-License-Identifier: Apache-2.0
"""Operational contracts for the local Brain semantic embedder."""

import io
import json

import pytest

import szl_brain_api as brain_api


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def test_ollama_current_api_batches_inputs(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, json.loads(request.data), timeout))
        return _Response({"embeddings": [[3.0, 4.0], [0.0, 2.0]]})

    monkeypatch.setattr(brain_api.urllib.request, "urlopen", fake_urlopen)
    rows = brain_api._ollama_embed(
        ["first evidence", "second evidence"], "http://127.0.0.1:11434")

    assert rows == [[3.0, 4.0], [0.0, 2.0]]
    assert len(calls) == 1
    assert calls[0][0].endswith("/api/embed")
    assert calls[0][1]["input"] == ["first evidence", "second evidence"]


def test_ollama_partial_batch_fails_closed(monkeypatch):
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/embed"):
            return _Response({"embeddings": [[1.0, 0.0]]})
        raise OSError("legacy endpoint unavailable")

    monkeypatch.setattr(brain_api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="both batch and legacy APIs"):
        brain_api._ollama_embed(
            ["first evidence", "second evidence"], "http://127.0.0.1:11434")


def test_embedder_uses_bounded_batches_and_normalizes(monkeypatch):
    calls = []

    def fake_embed(texts, url, model, timeout):
        calls.append(list(texts))
        return [[3.0, 4.0] for _ in texts]

    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("SZL_BRAIN_EMBED_BATCH", "2")
    monkeypatch.setattr(brain_api, "_ollama_embed", fake_embed)

    embedder = brain_api._Embedder()
    rows = embedder.embed(["a", "b", "c", "d", "e"])

    # One constructor probe, followed by three bounded corpus batches.
    assert calls == [["a11oy"], ["a", "b"], ["c", "d"], ["e"]]
    assert rows == [[0.6, 0.8]] * 5
    assert embedder.source == "ollama:nomic-embed-text"


def test_embedder_refuses_to_mix_vector_spaces_when_runtime_fails(monkeypatch):
    calls = 0

    def fake_embed(texts, url, model, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return [[1.0, 0.0]]
        raise RuntimeError("runtime stopped")

    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(brain_api, "_ollama_embed", fake_embed)
    embedder = brain_api._Embedder()

    with pytest.raises(
            brain_api.SemanticEmbeddingUnavailableError,
            match="semantic scoring refused"):
        embedder.embed(["evidence"])

    assert embedder.source == "ollama:nomic-embed-text"
    assert embedder._use_ollama is True
    assert embedder.last_error == "ollama runtime failed: RuntimeError"


def test_content_hash_binds_exact_embedding_inputs():
    before = {
        "nodes": [{"id": "node:1", "kind": "paper", "title": "old evidence"}],
        "links": [],
    }
    after = {
        "nodes": [{"id": "node:1", "kind": "paper", "title": "new contradiction"}],
        "links": [],
    }

    assert brain_api._content_hash(before) != brain_api._content_hash(after)
