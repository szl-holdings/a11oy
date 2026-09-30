# SPDX-License-Identifier: Apache-2.0
"""Adversarial release contracts, exercising actual generated Space code.

All market inputs are synthetic fixtures. No network, broker or provider writes.
"""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
REVISION = "1" * 40
NOW = 1789430400


def observation():
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: NOW, monotonic=lambda: NOW)
    body = c.observe("coinbase-ticker")
    body.update(ok=False, state="STALE", error="UPSTREAM_HTTP_503",
                served_at=transport.stamp(NOW + 40), retrieval_age_seconds=40)
    return body


@pytest.fixture
def projection(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    def load(name, relative):
        spec = importlib.util.spec_from_file_location(name, root / relative)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    proxy = load("release_projection", "scripts/hf_finance_read_proxy.py")
    base = load("release_base", "scripts/_hf_publish_vertical_flagships_v4_impl_base.py")
    cfg = {"slug": "finance", "title": "PURIQ", "upstream": "unused",
           "hf_repository": "SZLHOLDINGS/finance", "source_revision": REVISION}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "index.html").write_text("<main>SYNTHETIC TEST</main>")
    (tmp_path / "panels.html").write_text("<main>SYNTHETIC TEST</main>")
    monkeypatch.chdir(tmp_path)
    namespace = {"__name__": "release_generated_app"}
    exec(compile(proxy.augment(base.APP), "release_generated_app", "exec"), namespace)
    state = {"body": observation(), "status": 503, "headers": {"content-type": "application/json"}, "raw": None, "calls": []}
    class Response:
        @property
        def status_code(self): return state["status"]
        @property
        def headers(self): return state["headers"]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self):
            yield state["raw"] if state["raw"] is not None else json.dumps(state["body"]).encode()
    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 5, "follow_redirects": False, "trust_env": False}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, target, headers):
            assert method == "GET"
            assert headers["Accept-Encoding"] == "identity"
            state["calls"].append((target, headers))
            return Response()
    namespace["httpx"] = SimpleNamespace(Client=Client)
    state["namespace"] = namespace
    return TestClient(namespace["app"]), state


def test_stale_503_keeps_data_and_failure_only_when_exact_source_matches(projection):
    http, state = projection
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503 and result.json() == state["body"]
    assert result.headers["x-content-type-options"] == "nosniff"
    state["body"]["source_revision"] = "2" * 40
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503
    assert result.json()["error"] == "CANONICAL_REVISION_MISMATCH"
    assert "data" not in result.json()


@pytest.mark.parametrize("key,value,error", [
    ("source", "kalshi-book", "CANONICAL_SOURCE_IDENTITY_MISMATCH"),
    ("execution_enabled", True, "CANONICAL_SCHEMA_INVALID"),
    ("schema", "other", "CANONICAL_SCHEMA_INVALID"),
    ("ok", True, "CANONICAL_SCHEMA_INVALID"),
    ("state", "SNAPSHOT", "CANONICAL_SCHEMA_INVALID"),
])
def test_non200_status_does_not_bypass_semantic_checks(projection, key, value, error):
    http, state = projection
    state["body"][key] = value
    assert http.get("/api/finance/observations/coinbase-ticker").json()["error"] == error


def test_unavailable_source_is_revision_bound_and_survives_projection(projection):
    c = transport.FinanceClient(fetch=lambda p: b"broken", environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: NOW)
    body = c.observe("coinbase-ticker")
    assert body["source_revision"] == REVISION and body["state"] == "UNAVAILABLE"
    http, state = projection
    state["body"] = body
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503 and result.json() == body


@pytest.mark.parametrize("raw", [b'{"ok":true,"ok":false}', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":1e99999}', b'[]', b'\xff'])
def test_ambiguous_and_nonfinite_json_is_never_forwarded(projection, raw):
    http, state = projection
    state["raw"] = raw
    assert http.get("/api/finance/observations/coinbase-ticker").json()["error"] == "CANONICAL_SCHEMA_INVALID"


@pytest.mark.parametrize("headers,error", [
    ({"content-type": "text/not-json"}, "CANONICAL_SOURCE_UNAVAILABLE"),
    ({"content-type": "application/json", "content-encoding": "gzip"}, "CANONICAL_ENCODING_DENIED"),
    ({"content-type": "application/json", "content-length": "4000001"}, "CANONICAL_RESPONSE_TOO_LARGE"),
    ({"content-type": "application/json", "content-length": "-1"}, "CANONICAL_RESPONSE_TOO_LARGE"),
])
def test_projection_transport_boundaries(projection, headers, error):
    http, state = projection
    state["headers"] = headers
    assert http.get("/api/finance/observations/coinbase-ticker").json()["error"] == error


def test_actual_chunk_length_is_bounded_without_content_length(projection):
    http, state = projection
    state["raw"] = b" " * 4_000_001
    assert http.get("/api/finance/observations/coinbase-ticker").json()["error"] == "CANONICAL_RESPONSE_TOO_LARGE"


def test_projection_read_deadline_without_sleep(projection):
    http, state = projection
    ticks = iter([100.0, 113.0])
    state["namespace"]["_finance_time"] = SimpleNamespace(monotonic=lambda: next(ticks))
    assert http.get("/api/finance/observations/coinbase-ticker").json()["error"] == "CANONICAL_RESPONSE_DEADLINE"


@pytest.mark.parametrize("status", [403, 404, 422])
def test_request_errors_do_not_leak_arbitrary_upstream_body(projection, status):
    http, state = projection
    state.update(status=status, body={"error": "provider secret fixture", "data": {"private": "fixture"}})
    body = http.get("/api/finance/observations/coinbase-ticker").json()
    assert body["error"] == "CANONICAL_REQUEST_DENIED"
    assert "data" not in body and "fixture" not in json.dumps(body)


def test_overview_nested_stale_data_cannot_mix_runtime_revisions(projection):
    http, state = projection
    c = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: NOW)
    children = {source: c._unavailable(source, NOW, "UPSTREAM_HTTP_503")
        for source in ("polymarket-markets", "kalshi-markets", "treasury-rates")}
    children["coinbase-ticker"] = observation()
    state.update(status=200, body={"schema": "szl.finance.overview/v1", "source_revision": REVISION,
        "execution_enabled": False, "ok": False, "state": "DEGRADED", "data": children,
        "sources_requested": 4, "sources_available": 0, "event_equivalence": "NOT_ESTABLISHED"})
    body = http.get("/api/finance/overview").json()
    assert body["data"]["coinbase-ticker"]["state"] == "STALE"
    state["body"]["data"]["coinbase-ticker"]["source_revision"] = "2" * 40
    assert http.get("/api/finance/overview").json()["error"] == "CANONICAL_REVISION_MISMATCH"


def test_busy_provider_returns_bounded_failure_and_does_not_fetch(monkeypatch):
    monkeypatch.setattr(transport, "PROVIDER_WAIT_SECONDS", 0.001)
    c = transport.FinanceClient(fetch=lambda p: pytest.fail("busy provider fetched"), environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: NOW)
    lock = c._provider_locks["coinbase"]
    lock.acquire()
    try:
        body = c.observe("coinbase-ticker")
        assert body["error"] == "PROVIDER_BUSY" and body["source_revision"] == REVISION
        assert body["state"] == "UNAVAILABLE" and body["ok"] is False
    finally:
        lock.release()


def test_busy_provider_preserves_fresh_cache_then_marks_expired_cache_stale(monkeypatch):
    monkeypatch.setattr(transport, "PROVIDER_WAIT_SECONDS", 0.001)
    ticks = [float(NOW)]
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: ticks[0], monotonic=lambda: ticks[0])
    original = c.observe("coinbase-ticker")
    proof = deepcopy(original["provenance"])
    lock = c._provider_locks["coinbase"]
    lock.acquire()
    try:
        cached = c.observe("coinbase-ticker")
        assert cached["state"] == "CACHED" and cached["ok"] is True
        ticks[0] += 100
        stale = c.observe("coinbase-ticker")
        assert stale["state"] == "STALE" and stale["ok"] is False
        assert stale["error"] == "PROVIDER_BUSY" and stale["provenance"] == proof
    finally:
        lock.release()


def test_provider_lock_released_after_unexpected_internal_exception():
    def broken(p): raise RuntimeError("synthetic internal bug")
    c = transport.FinanceClient(fetch=broken, environ={"SZL_SOURCE_REVISION": REVISION}, clock=lambda: NOW)
    with pytest.raises(RuntimeError, match="synthetic internal bug"):
        c.observe("coinbase-ticker")
    assert not c._provider_locks["coinbase"].locked()


@pytest.mark.parametrize("alias", ["SZL_GIT_SHA", "SZL_SOURCE_REVISION", "A11OY_GIT_SHA"])
def test_each_supported_runtime_identity_convention_is_source_bound(alias):
    env = {alias: REVISION}
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ=env, clock=lambda: NOW, monotonic=lambda: NOW)
    assert c.registry()["source_revision"] == REVISION
    body = c.observe("coinbase-ticker")
    assert body["source_revision"] == REVISION
    assert body["provenance"]["runtime_reported_source_revision"] == REVISION


def test_actual_docker_identity_convention_flows_through_generated_projection(projection):
    docker = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "ARG SZL_GIT_SHA=unknown" in docker
    assert "ENV SZL_GIT_SHA=${SZL_GIT_SHA}" in docker
    env = {"SZL_GIT_SHA": REVISION, "A11OY_GIT_SHA": ""}
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ=env, clock=lambda: NOW, monotonic=lambda: NOW)
    http, state = projection
    state.update(status=200, body=c.observe("coinbase-ticker"))
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 200 and result.json() == state["body"]


@pytest.mark.parametrize("conflicting_alias", ["SZL_SOURCE_REVISION", "A11OY_GIT_SHA"])
def test_conflicting_runtime_alias_never_selects_a_convenient_identity(conflicting_alias):
    env = {"SZL_GIT_SHA": REVISION, conflicting_alias: "2" * 40}
    assert transport.source_revision(env) == "UNBOUND"


@pytest.mark.parametrize("invalid", ["0" * 40, "unknown", "main", "A" * 40, "1" * 39,
    "1" * 41, None, False, 123])
def test_invalid_alias_is_not_ignored_when_canonical_identity_is_valid(invalid):
    assert transport.source_revision({"SZL_GIT_SHA": REVISION, "A11OY_GIT_SHA": invalid}) == "UNBOUND"


@pytest.mark.parametrize("env", [{}, {"SZL_GIT_SHA": "unknown"}, {"SZL_GIT_SHA": "0" * 40},
    {"SZL_GIT_SHA": " ", "A11OY_GIT_SHA": ""}, {"GITHUB_SHA": REVISION}])
def test_unbound_or_unrelated_workflow_identity_cannot_qualify_the_runtime(env):
    assert transport.source_revision(env) == "UNBOUND"


def test_agreeing_aliases_resolve_without_rewriting_the_identity():
    assert transport.source_revision({"SZL_GIT_SHA": REVISION,
        "SZL_SOURCE_REVISION": " " + REVISION + " ", "A11OY_GIT_SHA": REVISION}) == REVISION


def test_conflicting_identity_is_refused_by_actual_generated_projection(projection):
    env = {"SZL_GIT_SHA": REVISION, "A11OY_GIT_SHA": "2" * 40}
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ=env, clock=lambda: NOW, monotonic=lambda: NOW)
    http, state = projection
    state.update(status=200, body=c.observe("coinbase-ticker"))
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503
    assert result.json()["error"] == "CANONICAL_REVISION_MISMATCH"
    assert "data" not in result.json()


def test_unavailable_observation_uses_canonical_identity_convention():
    c = transport.FinanceClient(fetch=lambda p: b"broken", environ={"SZL_GIT_SHA": REVISION}, clock=lambda: NOW)
    result = c.observe("coinbase-ticker")
    assert result["state"] == "UNAVAILABLE" and result["source_revision"] == REVISION
