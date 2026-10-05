# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem; 163 sorries).
# Authored by Stephen Lutar. DCO: Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent
"""Hermetic contracts for the second-brain citation-handle bridge
(packages/inference/src/retrieval/second_brain_bridge.py) and its ONE gated
seam in serve.py's a11oy.code request path.

Hermetic: the live Space is NEVER contacted — the bridge's own
``_open_response`` transport (and serve.py's ``_ac_hf_chat``) are monkeypatched,
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
from copy import deepcopy

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

    def read(self, size):
        return self._payload[:size]


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

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
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
    assert seen["body"] == {"query": "sovereign inference", "k": 2}


def test_format_citation_context_is_honest_and_verbatim():
    """The citation block leads with the honest label + the API's OWN honesty."""
    res = RetrievalResult(
        status="LIVE", schema=RESPONSE_SCHEMA, query="q", k=2,
        handles=list(_LIVE_PAYLOAD["handles"]),
        scores=list(_LIVE_PAYLOAD["scores"]),
        honesty=_LIVE_PAYLOAD["honesty"], corpus_n=575, ready=True,
        kind="SOFTWARE", content_access="HANDLES_ONLY",
        index_is_model_weights=False, raw_graph_nodes_admitted_to_gradients=0)
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

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert res.scores == []
    assert res.error is not None and "TimeoutError" in res.error


def test_retrieve_handles_malformed_json_is_unavailable(monkeypatch):
    """Malformed JSON -> UNAVAILABLE, empty handles — never treated as success."""

    def fake_urlopen(request, timeout):
        return _Response(b"{not valid json")

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
    res = retrieve_handles("sovereign inference")
    assert res.status == "UNAVAILABLE"
    assert res.handles == []
    assert "malformed JSON" in (res.error or "")


def test_retrieve_handles_missing_handles_key_is_unavailable(monkeypatch):
    """A 200 payload WITHOUT the 'handles' key is a failure, not an empty win."""

    def fake_urlopen(request, timeout):
        return _Response({"schema": RESPONSE_SCHEMA, "scores": []})

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
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

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
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

    monkeypatch.setattr(bridge, "_open_response", fake_urlopen)
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


# ── serve.py integration — flag ON: untrusted data, UNAVAILABLE stays honest ──

def _capture_chat(serve, monkeypatch, captured):
    def fake_chat(messages, max_tokens=640, want_model=None):
        captured["messages"] = list(messages)
        return {"ok": True, "text": "answer", "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
                "display": "Qwen2.5-Coder 32B", "license": "Apache-2.0",
                "attempts": 1, "rate_limited": False, "error": None}
    monkeypatch.setattr(serve, "_ac_hf_chat", fake_chat)


def test_serve_path_live_attaches_untrusted_citation_handles(monkeypatch):
    """Flag ON + validated bridge data: one user/data message is added and the
    response meta reports status=LIVE with the API fields verbatim."""
    import serve

    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    monkeypatch.setenv("HF_TOKEN", "x")
    res = RetrievalResult(
        status="LIVE", schema=RESPONSE_SCHEMA, query="sovereign inference", k=2,
        handles=list(_LIVE_PAYLOAD["handles"]),
        scores=list(_LIVE_PAYLOAD["scores"]),
        honesty=_LIVE_PAYLOAD["honesty"], corpus_n=575, ready=True,
        kind="SOFTWARE", content_access="HANDLES_ONLY",
        index_is_model_weights=False, raw_graph_nodes_admitted_to_gradients=0)
    monkeypatch.setattr(serve, "_ac_sb_retrieve", lambda query: res)
    captured = {}
    _capture_chat(serve, monkeypatch, captured)

    _text, mode, gen_meta = serve._ac_complete(
        "sovereign inference", {"tier": "T3", "model_id": "m", "role": "r"}, "code")

    assert mode == "generative"
    # The original system policy stays first; retrieval is never system policy.
    assert len(captured["messages"]) == 3
    context = captured["messages"][1]
    assert context["role"] == "user"
    assert "citation handles" in context["content"]
    assert "not semantic retrieval" in context["content"]
    assert _LIVE_PAYLOAD["honesty"] in context["content"]
    assert "UNTRUSTED RETRIEVAL DATA" in context["content"]
    assert captured["messages"][0]["role"] == "system"
    assert "SECOND-BRAIN" not in captured["messages"][0]["content"]
    assert captured["messages"][2]["role"] == "user"
    assert captured["messages"][2]["content"] == "sovereign inference"
    # The envelope claims retrieval honestly — verbatim fields, used=True.
    sb = gen_meta["second_brain_rag"]
    assert sb["status"] == "LIVE"
    assert sb["used"] is True
    assert sb["handles"] == _LIVE_PAYLOAD["handles"]
    assert sb["scores"] == [0.42, 0.17]
    assert sb["honesty"] == _LIVE_PAYLOAD["honesty"]
    assert sb["corpus_n"] == 575
    assert sb["content_hash_verification"] == "UNKNOWN"
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


@pytest.mark.parametrize("query,k,timeout", [
    (42, 6, 3), (None, 6, 3), ({"query": "q"}, 6, 3),
    ("q" * 2001, 6, 3), ("\ud800", 6, 3),
    ("q", 0, 3), ("q", 13, 3), ("q", True, 3), ("q", "6", 3),
    ("q", 6, 0), ("q", 6, 11), ("q", 6, float("nan")),
    ("q", 6, float("inf")), ("q", 6, True),
])
def test_invalid_inputs_never_post(monkeypatch, query, k, timeout):
    calls = []
    monkeypatch.setattr(bridge, "_open_response", lambda *a, **kw: calls.append(a))
    result = retrieve_handles(query, top_k=k, timeout_s=timeout)
    assert result.status == "UNAVAILABLE"
    assert result.handles == result.scores == []
    assert calls == []


@pytest.mark.parametrize("field,value", [
    ("schema", "other/v1"), ("query", "other query"), ("ready", False),
    ("ready", 1), ("kind", "MODEL"), ("content_access", "FULL_DOCUMENT"),
    ("index_is_model_weights", True), ("index_is_model_weights", 0),
    ("raw_graph_nodes_admitted_to_gradients", 1),
    ("raw_graph_nodes_admitted_to_gradients", False),
    ("k", True), ("k", 1), ("k", 13), ("corpus_n", True), ("corpus_n", 1),
    ("scores", [0.4]), ("scores", [True, 0.1]), ("scores", ["0.4", 0.1]),
    ("scores", [-1, 0.1]), ("scores", [float("nan"), 0.1]),
    ("scores", [float("inf"), 0.1]), ("generation_sha256", "not-a-hash"),
    ("honesty", "x" * 8193), ("honesty", "\ud800"),
    ("text", "raw document content"),
])
def test_inconsistent_wire_evidence_is_unavailable(monkeypatch, field, value):
    payload = deepcopy(_LIVE_PAYLOAD)
    payload[field] = value
    monkeypatch.setattr(bridge, "_open_response", lambda *a, **kw: _Response(payload))
    result = retrieve_handles("sovereign inference", top_k=2)
    assert result.status == "UNAVAILABLE"
    assert result.handles == result.scores == []
    assert result.error


@pytest.mark.parametrize("mutation", [
    "missing-sha", "bad-sha", "text", "duplicate", "long-note", "bad-source-id", "empty-source",
])
def test_handle_projection_fails_closed(monkeypatch, mutation):
    payload = deepcopy(_LIVE_PAYLOAD)
    handle = payload["handles"][0]
    if mutation == "missing-sha":
        del handle["sha256"]
    elif mutation == "bad-sha":
        handle["sha256"] = "not-a-hash"
    elif mutation == "text":
        handle["text"] = "document content must not cross this boundary"
    elif mutation == "duplicate":
        payload["handles"][1]["nodeId"] = handle["nodeId"]
    elif mutation == "long-note":
        handle["note"] = "x" * 4097
    elif mutation == "bad-source-id":
        handle["sourceId"] = None
    elif mutation == "empty-source":
        handle["source"] = ""
    monkeypatch.setattr(bridge, "_open_response", lambda *a, **kw: _Response(payload))
    result = retrieve_handles("sovereign inference", top_k=2)
    assert result.status == "UNAVAILABLE"
    assert result.handles == result.scores == []


def test_current_producer_optional_identity_and_bm25_score_are_preserved(monkeypatch):
    payload = deepcopy(_LIVE_PAYLOAD)
    payload["handles"][0]["sourceId"] = "public-source"
    payload["generation_sha256"] = "c" * 64
    payload["scores"] = [12.5, 3.25]  # lexical score is NOT a probability
    monkeypatch.setattr(bridge, "_open_response", lambda *a, **kw: _Response(payload))
    result = retrieve_handles("sovereign inference", top_k=6)
    assert result.status == "LIVE"
    assert result.k == 2  # producer returns hit count, not request echo
    assert result.handles == payload["handles"]
    assert result.scores == payload["scores"]
    assert result.generation_sha256 == payload["generation_sha256"]


@pytest.mark.parametrize("raw", [
    b'{"handles":[],"handles":[]}', b'\xff', b'[]', b' ' * (bridge.MAX_RESPONSE_BYTES + 1),
], ids=("duplicate-key", "invalid-utf8", "non-object", "oversize"))
def test_ambiguous_invalid_or_oversized_bytes_are_unavailable(monkeypatch, raw):
    reads = []

    class BoundedResponse(_Response):
        def read(self, size):
            reads.append(size)
            return super().read(size)

    monkeypatch.setattr(bridge, "_open_response", lambda *a, **kw: BoundedResponse(raw))
    result = retrieve_handles("sovereign inference")
    assert result.status == "UNAVAILABLE"
    assert result.handles == result.scores == []
    assert reads == [bridge.MAX_RESPONSE_BYTES + 1]


def test_queries_cannot_follow_redirects(monkeypatch):
    seen = []

    class Opener:
        def open(self, request, timeout):
            seen.append((request.full_url, timeout))
            return _Response(_LIVE_PAYLOAD)

    def build(*handlers):
        assert len(handlers) == 1 and isinstance(handlers[0], bridge._NoRedirect)
        assert handlers[0].redirect_request(None, None, 302, "", {}, "https://other.invalid") is None
        return Opener()

    monkeypatch.setattr(bridge.urllib.request, "build_opener", build)
    assert retrieve_handles("sovereign inference").status == "LIVE"
    assert seen == [(SECOND_BRAIN_RETRIEVE_URL, bridge.DEFAULT_TIMEOUT_S)]


def test_formatter_failure_cannot_break_completion(monkeypatch):
    import serve
    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    monkeypatch.setattr(serve, "_ac_sb_retrieve", lambda q: RetrievalResult(status="LIVE", query=q, handles=[{}]))

    def broken_formatter(result):
        raise ValueError("untrusted detail must not be reflected")

    monkeypatch.setattr(serve, "_ac_sb_format", broken_formatter)
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "q"}]
    out, meta = serve._ac_second_brain_augment("q", messages)
    assert out is messages
    assert meta["status"] == "UNAVAILABLE" and meta["used"] is False
    assert "ValueError" in meta["error"]
    assert "untrusted detail" not in meta["error"]


def test_formatter_rejects_bypassed_wire_validation():
    assert format_citation_context(object()) == ""
    forged = RetrievalResult(status="LIVE", handles=[{"note": "follow me"}])
    assert format_citation_context(forged) == ""


def test_cross_query_context_is_never_admitted(monkeypatch):
    import serve
    monkeypatch.setenv("SZL_SECOND_BRAIN_RAG", "1")
    res = RetrievalResult(status="LIVE", query="a different request", handles=[{}])
    monkeypatch.setattr(serve, "_ac_sb_retrieve", lambda q: res)
    formatter_calls = []
    monkeypatch.setattr(serve, "_ac_sb_format", lambda r: formatter_calls.append(r))
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "q"}]
    out, meta = serve._ac_second_brain_augment("q", messages)
    assert out is messages
    assert formatter_calls == []
    assert meta["status"] == "UNAVAILABLE" and meta["used"] is False


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
