# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem; 163 sorries).
# Authored by Stephen Lutar. DCO: Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent
"""Hermetic contracts for the second-brain citation-handle bridge
(packages/inference/src/retrieval/second_brain_bridge.py) and its ONE gated
seam in serve.py's a11oy.code request path.

Hermetic: the live Space is NEVER contacted — the bridge's own
``urllib.request.urlopen`` (and serve.py's ``_ac_hf_chat``) are monkeypatched,
mirroring the style of tests/test_brain_semantic_embedder.py.

The upstream API is a LEXICAL-OVERLAP ranker over the PUBLIC in-repo
projection (content_access=HANDLES_ONLY): it returns citation HANDLES
(nodeId + short note + sha256), NOT document text, NOT semantic retrieval,
NOT the private brain graph. These tests pin that honesty: LIVE only on a
well-formed ``szl.second-brain.retrieve/v1`` payload, UNAVAILABLE (never a
fake handle) on any failure, and byte-identical default behaviour in serve.py
when SZL_SECOND_BRAIN_RAG is unset.
"""
from __future__ import annotations

import io
import json

import pytest

from packages.inference.src.retrieval import second_brain_bridge as bridge
from packages.inference.src.retrieval.second_brain_bridge import (
    RESPONSE_SCHEMA,
    SECOND_BRAIN_RETRIEVE_URL,
    RetrievalResult,
    format_citation_context,
    retrieve_handles,
)

# The exact, verbatim schema the LIVE Space returns (handles only — no text).
_LIVE_PAYLOAD = {
    "schema": "szl.second-brain.retrieve/v1",
    "query": "sovereign inference",
    "k": 2,
    "handles": [
        {
            "nodeId": "n-001",
            "nodeKind": "SOFTWARE",
            "label": "DECLARED",
            "note": "Sovereign inference runs on own metal, receipts on write.",
            "source": "docs/architecture.md",
            "sha256": "a" * 64,
        },
        {
            "nodeId": "n-002",
            "nodeKind": "SOFTWARE",
            "label": "DECLARED",
            "note": "The governed envelope carries an honest status label.",
            "source": "serve.py",
            "sha256": "b" * 64,
        },
    ],
    "scores": [0.42, 0.17],
    "corpus_n": 575,
    "ready": True,
    "kind": "SOFTWARE",
    "content_access": "HANDLES_ONLY",
    "index_is_model_weights": False,
    "raw_graph_nodes_admitted_to_gradients": 0,
    "honesty": (
        "Lexical rank over the PUBLIC in-repo projection (575 chunks). "
        "Score is overlap, never correctness. Content stays in the controller. "
        "Not LIVE retrieval. Private 9464-node graph is not held/exposed."
    ),
}


class _Response:
    """Minimal urllib-style response double (context manager + .read())."""

    def __init__(self, payload, status=200):
        self._payload = (
            payload if isinstance(payload, (bytes, bytearray))
            else json.dumps(payload).encode("utf-8")
        )
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


# ── retrieve_handles — LIVE path ────────────────────────────────────────────

def test_retrieve_handles_live_passes_verbatim(monkeypatch):
    """HTTP 200 + the exact well-formed schema -> LIVE with verbatim handles."""
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return _Response(dict(_LIVE_PAYLOAD))

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("sovereign inference", top_k=2)

    assert res.status == "LIVE"
    assert res.schema == RESPONSE_SCHEMA
    assert res.query == "sovereign inference"
    assert res.k == 2
    assert res.handles == _LIVE_PAYLOAD["handles"]            # verbatim
    assert res.scores == [0.42, 0.17]                          # verbatim
    assert res.honesty == _LIVE_PAYLOAD["honesty"]             # verbatim
    assert res.corpus_n == 575
    assert res.ready is True
    assert res.kind == "SOFTWARE"
    assert res.content_access == "HANDLES_ONLY"
    assert res.error is None
    # The bridge posts the real endpoint with the real request shape.
    assert seen["url"] == SECOND_BRAIN_RETRIEVE_URL
    assert seen["method"] == "POST"
    assert seen["body"] == {"query": "sovereign inference", "top_k": 2}


def test_format_citation_context_is_honest_and_verbatim():
    """The citation block leads with the honest label + the API's OWN honesty."""
    res = RetrievalResult(
        status="LIVE", schema=RESPONSE_SCHEMA, query="q", k=2,
        handles=list(_LIVE_PAYLOAD["handles"]),
        scores=list(_LIVE_PAYLOAD["scores"]),
        honesty=_LIVE_PAYLOAD["honesty"], corpus_n=575, ready=True,
        kind="SOFTWARE", content_access="HANDLES_ONLY")
    ctx = format_citation_context(res)
    assert ctx  # non-empty for a LIVE result with handles
    assert "575-chunk lexical index" in ctx
    assert "not semantic retrieval" in ctx
    assert "not the full brain graph" in ctx
    assert _LIVE_PAYLOAD["honesty"] in ctx            # upstream honesty verbatim
    assert "n-001" in ctx and "n-002" in ctx
    assert "a" * 64 in ctx                            # sha256 pointers verbatim
    assert "Sovereign inference runs on own metal" in ctx
    # An UNAVAILABLE or empty LIVE result must render nothing to prepend.
    assert format_citation_context(RetrievalResult(status="UNAVAILABLE")) == ""
    assert format_citation_context(
        RetrievalResult(status="LIVE", handles=[])) == ""


# ── retrieve_handles — UNAVAILABLE paths (fail-closed, never raise) ─────────

def test_retrieve_handles_timeout_is_unavailable(monkeypatch):
    """A timeout -> UNAVAILABLE, empty handles, named error, never raises."""

    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert res.scores == []
    assert res.error is not None and "TimeoutError" in res.error


def test_retrieve_handles_malformed_json_is_unavailable(monkeypatch):
    """Malformed JSON -> UNAVAILABLE, empty handles — never treated as success."""

    def fake_urlopen(request, timeout):
        return _Response(b"{not valid json")

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert "malformed JSON" in (res.error or "")


def test_retrieve_handles_missing_handles_key_is_unavailable(monkeypatch):
    """A 200 payload WITHOUT the 'handles' key is a failure, not an empty win."""

    def fake_urlopen(request, timeout):
        return _Response({"schema": RESPONSE_SCHEMA, "scores": []})

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert "handles" in (res.error or "")


def test_retrieve_handles_http_error_is_unavailable(monkeypatch):
    """A non-2xx from the Space -> UNAVAILABLE, never a fabricated handle."""
    import urllib.error

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 503, "Service Unavailable", {}, io.BytesIO(b""))

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert "HTTP 503" in (res.error or "")


def test_retrieve_handles_empty_query_posts_nothing(monkeypatch):
    """An empty query is UNAVAILABLE and never touches the network."""
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return _Response(dict(_LIVE_PAYLOAD))

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    res = retrieve_handles("   ")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert calls == []


# ── serve.py integration — regression: flag OFF is byte-identical ───────────

def test_serve_path_byte_identical_when_flag_unset(monkeypatch):
    """SZL_SECOND_BRAIN_RAG unset: the bridge is never consulted and the
    generative path's messages/generation meta are byte-identical to before.

    ``_ac_hf_chat`` is stubbed to capture what the path would send; with the
    flag OFF the captured messages MUST be the untouched pair and the
    generation meta MUST NOT contain any second_brain_rag key.
    """
    import serve

    for name in ("SZL_SECOND_BRAIN_RAG", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN",
                 "A11OY_GPU_TOKEN", "LOCAL_LLM_TOKEN", "VLLM_API_KEY",
                 "HF_ROUTER_TOKEN", "HF_API_TOKEN", "HUGGINGFACE_TOKEN",
                 "HUGGINGFACEHUB_API_TOKEN", "Token"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_TOKEN", "x")  # reach the generative branch only

    captured = {}

    def fake_chat(messages, max_tokens=640, want_model=None):
        captured["messages"] = json.loads(json.dumps(messages))  # freeze
        return {"ok": True, "text": "def f(): pass", "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
                "display": "Qwen2.5-Coder 32B", "license": "Apache-2.0",
                "attempts": 1, "rate_limited": False, "error": None}

    def explode_retrieve(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("second-brain bridge consulted while flag is OFF")

    monkeypatch.setattr(serve, "_ac_hf_chat", fake_chat)
    monkeypatch.setattr(serve, "_ac_sb_retrieve", explode_retrieve)

    text, mode, gen_meta = serve._ac_complete(
        "how do I reverse a linked list?",
        {"tier": "T3", "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct", "role": "primary"},
        "code")

    assert mode == "generative"
    assert text == "def f(): pass"
    # The outbound messages are the untouched system+user pair — nothing prepended.
    assert captured["messages"] == [
        {"role": "system", "content": (
            "You are a11oy Code, a governed open-weight coding assistant. Answer the "
            "user's coding question directly and correctly. Be concise and include "
            "runnable code when relevant.")},
        {"role": "user", "content": "how do I reverse a linked list?"},
    ]
    # The envelope's generation meta must not claim retrieval was used.
    assert "second_brain_rag" not in gen_meta
    assert gen_meta["configured"] is True


# ── serve.py integration — flag ON: LIVE prepends, UNAVAILABLE stays honest ──

def _capture_chat(serve, monkeypatch, captured):
    def fake_chat(messages, max_tokens=640, want_model=None):
        captured["messages"] = list(messages)
        return {"ok": True, "text": "answer", "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
                "display": "Qwen2.5-Coder 32B", "license": "Apache-2.0",
                "attempts": 1, "rate_limited": False, "error": None}
    monkeypatch.setattr(serve, "_ac_hf_chat", fake_chat)


def test_serve_path_live_prepends_citation_handles(monkeypatch):
    """Flag ON + bridge LIVE: one citation system message is prepended and the
    response meta reports status=LIVE with the API fields verbatim."""
    import serve

    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    monkeypatch.setenv("HF_TOKEN", "x")
    res = RetrievalResult(
        status="LIVE", schema=RESPONSE_SCHEMA, query="q", k=2,
        handles=list(_LIVE_PAYLOAD["handles"]),
        scores=list(_LIVE_PAYLOAD["scores"]),
        honesty=_LIVE_PAYLOAD["honesty"], corpus_n=575, ready=True,
        kind="SOFTWARE", content_access="HANDLES_ONLY")
    monkeypatch.setattr(serve, "_ac_sb_retrieve", lambda query: res)
    captured = {}
    _capture_chat(serve, monkeypatch, captured)

    _text, mode, gen_meta = serve._ac_complete(
        "sovereign inference", {"tier": "T3", "model_id": "m", "role": "r"}, "code")

    assert mode == "generative"
    # Exactly ONE extra system message, prepended ahead of the original pair.
    assert len(captured["messages"]) == 3
    first = captured["messages"][0]
    assert first["role"] == "system"
    assert "citation handles" in first["content"]
    assert "not semantic retrieval" in first["content"]
    assert _LIVE_PAYLOAD["honesty"] in first["content"]
    assert captured["messages"][1]["role"] == "system"
    assert captured["messages"][2]["role"] == "user"
    # The envelope claims retrieval honestly — verbatim fields, used=True.
    sb = gen_meta["second_brain_rag"]
    assert sb["status"] == "LIVE"
    assert sb["used"] is True
    assert sb["handles"] == _LIVE_PAYLOAD["handles"]
    assert sb["scores"] == [0.42, 0.17]
    assert sb["honesty"] == _LIVE_PAYLOAD["honesty"]
    assert sb["corpus_n"] == 575
    assert "not semantic retrieval" in sb["label"]


def test_serve_path_unavailable_does_not_claim_retrieval(monkeypatch):
    """Flag ON + bridge UNAVAILABLE: the messages go out UNCHANGED and the
    meta reports status=UNAVAILABLE, used=False — never a fake citation."""
    import serve

    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    monkeypatch.setenv("HF_TOKEN", "x")
    res = RetrievalResult(status="UNAVAILABLE", query="q",
                          error="TimeoutError: timed out")
    monkeypatch.setattr(serve, "_ac_sb_retrieve", lambda query: res)
    captured = {}
    _capture_chat(serve, monkeypatch, captured)

    _text, mode, gen_meta = serve._ac_complete(
        "sovereign inference", {"tier": "T3", "model_id": "m", "role": "r"}, "code")

    assert mode == "generative"
    # Nothing prepended: the original system+user pair goes out as-is.
    assert len(captured["messages"]) == 2
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][1]["role"] == "user"
    sb = gen_meta["second_brain_rag"]
    assert sb["status"] == "UNAVAILABLE"
    assert sb["used"] is False
    # No handles key at all: an UNAVAILABLE result fabricates no citation handles.
    assert "handles" not in sb
    assert "TimeoutError" in (sb["error"] or "")


def test_serve_path_flag_on_but_bridge_module_missing_is_honest(monkeypatch):
    """Flag ON + bridge unimportable in this image: honest UNAVAILABLE, no crash."""
    import serve

    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    monkeypatch.setenv("HF_TOKEN", "x")
    monkeypatch.setattr(serve, "_ac_sb_retrieve", None)
    captured = {}
    _capture_chat(serve, monkeypatch, captured)

    _text, mode, gen_meta = serve._ac_complete(
        "sovereign inference", {"tier": "T3", "model_id": "m", "role": "r"}, "code")

    assert mode == "generative"
    assert len(captured["messages"]) == 2  # unchanged
    sb = gen_meta["second_brain_rag"]
    assert sb["status"] == "UNAVAILABLE"
    assert sb["used"] is False
