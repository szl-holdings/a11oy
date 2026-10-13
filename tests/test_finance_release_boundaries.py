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
contract = importlib.import_module("verticals.puriq-markets.runtime.contract")
REVISION = "1" * 40
# What the canonical runtime actually sends; derived from its contract module.
CANONICAL_HEADERS = {"content-type": "application/json",
                     contract.HEADER.lower(): contract.header_value()}
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
    state = {"body": observation(), "status": 503, "headers": dict(CANONICAL_HEADERS), "raw": None, "calls": []}
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


def test_stale_503_keeps_data_and_failure_only_when_self_consistent(projection):
    http, state = projection
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503 and result.json() == state["body"]
    assert result.headers["x-content-type-options"] == "nosniff"
    # A top-level revision that disagrees with the observation's own provenance
    # is internal inconsistency, not a different-but-compatible runtime.
    state["body"]["source_revision"] = "2" * 40
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503
    assert result.json()["error"] == "CANONICAL_PROVENANCE_MISMATCH"
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
    assert http.get("/api/finance/overview").json()["error"] == "CANONICAL_REVISION_INCONSISTENT"


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
    assert result.json()["error"] == "CANONICAL_REVISION_UNREPORTED"
    assert "data" not in result.json()


def test_unavailable_observation_uses_canonical_identity_convention():
    c = transport.FinanceClient(fetch=lambda p: b"broken", environ={"SZL_GIT_SHA": REVISION}, clock=lambda: NOW)
    result = c.observe("coinbase-ticker")
    assert result["state"] == "UNAVAILABLE" and result["source_revision"] == REVISION


# Versioned contract instead of exact-revision coupling between the Spaces.
# The projection is built from REVISION; the canonical runtime runs OTHER.
OTHER = "2" * 40


def other_runtime_observation():
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ={"SZL_GIT_SHA": OTHER}, clock=lambda: NOW, monotonic=lambda: NOW)
    return c.observe("coinbase-ticker")


def test_compatible_contract_from_a_different_runtime_revision_is_served(projection):
    http, state = projection
    state.update(status=200, body=other_runtime_observation())
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 200 and result.json() == state["body"]
    # The answering runtime's revision is forwarded as evidence, unchanged.
    assert result.json()["source_revision"] == OTHER
    assert state["namespace"]["CFG"]["source_revision"] == REVISION


def test_compatible_overview_from_a_different_runtime_revision_is_served(projection):
    http, state = projection
    c = transport.FinanceClient(environ={"SZL_GIT_SHA": OTHER}, clock=lambda: NOW)
    children = {source: c._unavailable(source, NOW, "UPSTREAM_HTTP_503")
        for source in ("polymarket-markets", "kalshi-markets", "treasury-rates", "coinbase-ticker")}
    state.update(status=200, body={"schema": "szl.finance.overview/v1", "source_revision": OTHER,
        "execution_enabled": False, "ok": False, "state": "DEGRADED", "data": children,
        "sources_requested": 4, "sources_available": 0, "event_equivalence": "NOT_ESTABLISHED"})
    result = http.get("/api/finance/overview")
    assert result.status_code == 200 and result.json() == state["body"]


@pytest.mark.parametrize("declared,error,served", [
    ("szl.finance.read-api/2", "CANONICAL_CONTRACT_INCOMPATIBLE", [2]),
    ("szl.finance.read-api/3,szl.finance.read-api/2", "CANONICAL_CONTRACT_INCOMPATIBLE", [2, 3]),
    (None, "CANONICAL_CONTRACT_UNDECLARED", None),
    ("szl.finance.read-api/one", "CANONICAL_CONTRACT_INVALID", None),
    ("other.contract/1", "CANONICAL_CONTRACT_INVALID", None),
    ("szl.finance.read-api/1;" + "x" * 300, "CANONICAL_CONTRACT_INVALID", None),
])
def test_incompatible_contract_fails_closed_with_reason(projection, declared, error, served):
    http, state = projection
    state.update(status=200, body=other_runtime_observation(), headers={"content-type": "application/json"})
    if declared is not None:
        state["headers"]["x-szl-finance-contract"] = declared
    result = http.get("/api/finance/observations/coinbase-ticker")
    body = result.json()
    assert result.status_code == 503 and body["error"] == error
    assert body["state"] == "UNAVAILABLE" and "data" not in body and "source_revision" not in body
    assert body["contract"] == {"name": "szl.finance.read-api", "supported_versions": [1], "served_versions": served}


def test_one_supported_version_among_several_served_is_compatible(projection):
    http, state = projection
    state.update(status=200, body=other_runtime_observation())
    state["headers"]["x-szl-finance-contract"] = "szl.finance.read-api/1, szl.finance.read-api/2"
    assert http.get("/api/finance/observations/coinbase-ticker").status_code == 200


def test_unreported_runtime_revision_is_refused_not_trusted(projection):
    http, state = projection
    c = transport.FinanceClient(fetch=lambda p: b'{"price":"100","bid":"99","ask":"101"}',
        environ={}, clock=lambda: NOW, monotonic=lambda: NOW)
    state.update(status=200, body=c.observe("coinbase-ticker"))
    assert state["body"]["source_revision"] == "UNBOUND"
    result = http.get("/api/finance/observations/coinbase-ticker")
    assert result.status_code == 503 and result.json()["error"] == "CANONICAL_REVISION_UNREPORTED"


def readyz(http, state):
    import hashlib
    digest = hashlib.sha256("<main>SYNTHETIC TEST</main>".encode()).hexdigest()
    state["namespace"]["CFG"].setdefault("landing_sha256", digest)
    state["namespace"]["CFG"].setdefault("panels_sha256", digest)
    state["namespace"]["_finance_readiness_cache"].clear()
    return http.get("/readyz")


def test_readyz_is_ready_for_a_compatible_runtime_at_another_revision(projection):
    http, state = projection
    state.update(status=200, body=contract.descriptor(OTHER))
    result = readyz(http, state)
    body = result.json()
    assert result.status_code == 200 and body["ready"] is True and body["state"] == "MEASURED"
    assert body["schema"] == "szl.vertical-shell-readiness/v1"
    # Same vocabulary as every other vertical shell: checks.upstream + upstream{...}.
    assert body["checks"] == {"landing_sha256": True, "panels_sha256": True, "upstream": True}
    upstream = body["upstream"]
    assert upstream["accepted"] is True and upstream["status"] == "COMPATIBLE" and upstream["reason"] is None
    assert upstream["served_versions"] == [1] and upstream["components_match"] is True
    assert upstream["observed_source_revision"] == OTHER
    assert upstream["revision_role"] == "EVIDENCE_NOT_COMPATIBILITY_KEY"
    assert upstream["route"] == "/api/a11oy/v1/finance/contract"
    assert state["calls"][-1][0].endswith("/api/a11oy/v1/finance/contract")


def test_readyz_is_not_ready_for_an_incompatible_contract(projection):
    http, state = projection
    future = contract.descriptor(OTHER)
    future["versions"] = [2]
    state.update(status=200, body=future)
    state["headers"]["x-szl-finance-contract"] = "szl.finance.read-api/2"
    result = readyz(http, state)
    body = result.json()
    assert result.status_code == 503 and body["ready"] is False and body["state"] == "INCOMPATIBLE"
    assert body["checks"]["upstream"] is False
    assert body["upstream"]["reason"] == "CANONICAL_CONTRACT_INCOMPATIBLE"
    assert body["upstream"]["served_versions"] == [2]
    assert body["upstream"]["observed_source_revision"] is None


@pytest.mark.parametrize("declared,reason,expected", [
    (None, "CANONICAL_CONTRACT_UNDECLARED", "CONTRACT_UNDECLARED"),
    ("garbage", "CANONICAL_CONTRACT_INVALID", "CONTRACT_INVALID"),
])
def test_readyz_separates_a_broken_declaration_from_a_version_mismatch(projection, declared, reason, expected):
    http, state = projection
    state.update(status=200, body=contract.descriptor(OTHER), headers={"content-type": "application/json"})
    if declared is not None:
        state["headers"]["x-szl-finance-contract"] = declared
    body = readyz(http, state).json()
    assert body["state"] == expected and body["upstream"]["reason"] == reason
    assert body["ready"] is False and body["checks"]["upstream"] is False


def test_readyz_rejects_a_contract_body_that_disagrees_with_its_header(projection):
    http, state = projection
    lying = contract.descriptor(OTHER)
    lying["versions"] = [1, 2]
    state.update(status=200, body=lying)
    result = readyz(http, state)
    assert result.status_code == 503 and result.json()["state"] == "CONTRACT_INVALID"
    assert result.json()["upstream"]["reason"] == "CANONICAL_CONTRACT_INVALID"


@pytest.mark.parametrize("component", ["analytics", "signed_price"])
def test_readyz_is_not_ready_when_a11oy_serves_other_pinned_components(projection, component):
    # A compatible contract version does not cover the exact component pins the
    # analytics and signed-price routes enforce; readiness must not stay green.
    http, state = projection
    changed = contract.descriptor(OTHER)
    changed["components"][component] = {**changed["components"][component], "revision": "f" * 40}
    state.update(status=200, body=changed)
    result = readyz(http, state)
    body = result.json()
    assert result.status_code == 503 and body["ready"] is False and body["state"] == "COMPONENT_MISMATCH"
    assert body["checks"]["upstream"] is False and body["upstream"]["components_match"] is False
    assert body["upstream"]["reason"] == "CANONICAL_COMPONENT_MISMATCH"


def test_contract_without_component_bindings_is_invalid(projection):
    http, state = projection
    bare = {k: v for k, v in contract.descriptor(OTHER).items() if k != "components"}
    state.update(status=200, body=bare)
    assert readyz(http, state).json()["upstream"]["reason"] == "CANONICAL_CONTRACT_INVALID"


@pytest.mark.parametrize("failure", ["transport", "sleeping-space-html"])
def test_upstream_down_fails_data_and_readiness(projection, failure):
    http, state = projection
    if failure == "transport":
        import httpx
        class Down:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def stream(self, method, target, headers):
                raise httpx.ConnectError("synthetic outage")
        state["namespace"]["httpx"] = SimpleNamespace(Client=Down)
        expected = "CANONICAL_SOURCE_TRANSPORT_UNAVAILABLE"
    else:
        state.update(status=503, headers={"content-type": "text/html"}, raw=b"<html>building</html>")
        expected = "CANONICAL_SOURCE_UNAVAILABLE"
    data = http.get("/api/finance/observations/coinbase-ticker")
    assert data.status_code == 503 and data.json()["error"] == expected
    result = readyz(http, state)
    body = result.json()
    assert result.status_code == 503 and body["ready"] is False and body["state"] == "UPSTREAM_UNAVAILABLE"
    assert body["checks"] == {"landing_sha256": True, "panels_sha256": True, "upstream": False}
    assert body["upstream"]["reason"] == expected and body["upstream"]["accepted"] is False


def test_readiness_probe_is_bounded_by_a_short_cache(projection):
    http, state = projection
    state.update(status=200, body=contract.descriptor(OTHER))
    assert readyz(http, state).status_code == 200
    calls = len(state["calls"])
    assert http.get("/readyz").status_code == 200
    assert len(state["calls"]) == calls
    state["namespace"]["_FINANCE_READINESS_TTL"] = 0
    state.update(status=503, headers={"content-type": "text/html"}, raw=b"<html>down</html>")
    assert http.get("/readyz").status_code == 503
    assert len(state["calls"]) == calls + 1


def test_readiness_ttl_starts_when_the_upstream_read_completes(projection):
    # A probe slower than the TTL must still be cached once it completes.
    import time
    http, state = projection
    namespace = state["namespace"]
    clock = {"now": 1000.0}
    namespace["_finance_time"] = SimpleNamespace(monotonic=lambda: clock["now"],
        strftime=time.strftime, gmtime=time.gmtime)
    real = namespace["_finance_get"]
    def slow(kind, *args, **kwargs):
        clock["now"] += 11.0
        return real(kind, *args, **kwargs)
    namespace["_finance_get"] = slow
    state.update(status=200, body=contract.descriptor(OTHER))
    namespace["_finance_readiness_cache"].clear()
    namespace["_finance_upstream_readiness"]()
    calls = len(state["calls"])
    clock["now"] += 5.0
    assert namespace["_finance_upstream_readiness"]()["accepted"] is True
    assert len(state["calls"]) == calls


def test_concurrent_cold_readiness_probes_share_one_upstream_read(projection):
    import threading
    http, state = projection
    namespace = state["namespace"]
    release, entered = threading.Event(), threading.Event()
    real = namespace["_finance_get"]
    def gated(kind, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return real(kind, *args, **kwargs)
    namespace["_finance_get"] = gated
    state.update(status=200, body=contract.descriptor(OTHER))
    namespace["_finance_readiness_cache"].clear()
    results = []
    workers = [threading.Thread(target=lambda: results.append(namespace["_finance_upstream_readiness"]()))
               for _ in range(8)]
    for worker in workers:
        worker.start()
    assert entered.wait(5)
    release.set()
    for worker in workers:
        worker.join(5)
    assert len(results) == 8 and all(result is results[0] for result in results)
    assert len(state["calls"]) == 1


def test_an_older_slow_probe_cannot_overwrite_a_newer_result(projection):
    # Probes are serialized, so completion order equals start order and the
    # cache always holds the most recently started observation.
    import threading
    http, state = projection
    namespace = state["namespace"]
    order = []
    real = namespace["_finance_get"]
    first_inside, release_first = threading.Event(), threading.Event()
    def observed(kind, *args, **kwargs):
        if not order:
            order.append("first")
            first_inside.set()
            assert release_first.wait(5)
            return real(kind, *args, **kwargs)
        order.append("second")
        state.update(status=503, headers={"content-type": "text/html"}, raw=b"<html>down</html>")
        return real(kind, *args, **kwargs)
    namespace["_finance_get"] = observed
    namespace["_FINANCE_READINESS_TTL"] = 0
    state.update(status=200, body=contract.descriptor(OTHER))
    namespace["_finance_readiness_cache"].clear()
    first = threading.Thread(target=namespace["_finance_upstream_readiness"])
    first.start()
    assert first_inside.wait(5)
    later = []
    second = threading.Thread(target=lambda: later.append(namespace["_finance_upstream_readiness"]()))
    second.start()
    release_first.set()
    first.join(5)
    second.join(5)
    assert order == ["first", "second"]
    assert later[0]["status"] == "UPSTREAM_UNAVAILABLE"
    assert namespace["_finance_readiness_cache"]["value"] is later[0]


def test_local_integrity_failure_still_reports_invalid(projection):
    http, state = projection
    state.update(status=200, body=contract.descriptor(OTHER))
    state["namespace"]["CFG"]["landing_sha256"] = "0" * 64
    body = readyz(http, state).json()
    assert body["checks"]["landing_sha256"] is False
    assert body["ready"] is False and body["state"] == "INVALID"
    assert body["checks"]["upstream"] is True


def coinbase_client(revision):
    import itertools
    ticks = itertools.count(0, 10)  # past every provider cooldown between reads
    return transport.FinanceClient(environ={"SZL_SOURCE_REVISION": revision}, monotonic=lambda: next(ticks),
        fetch=lambda plan: json.dumps([[plan.parameters["start"] + i * 86400, 50, 200, 100,
                                       100 + i * .1 + i % 5, 1] for i in range(260)][::-1]).encode())


def reenvelope(body, revision):
    """What a client could forge: a self-consistent envelope at another revision."""
    body = deepcopy(body)
    body["source_revision"] = revision
    receipt = body["receipt"]
    receipt["source_revision"] = revision
    receipt.pop("receipt_sha256")
    receipt["payload_sha256"] = transport.digest({k: v for k, v in body.items() if k != "receipt"})
    receipt["receipt_sha256"] = transport.digest(receipt)
    return body


@pytest.mark.parametrize("operation,symbol,query", [
    ("signals", "BTC-USD", []),
    ("quote", "BTC-USD", [("benchmark", "ETH-USD")]),
])
def test_analytics_cannot_mix_runtime_revisions_in_one_answer(operation, symbol, query):
    analytics = importlib.import_module("verticals.puriq-markets.runtime.analytics")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("mixed_revision_contract", root / "scripts/hf_finance_read_proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)
    check = proxy.validation_namespace(REVISION)["_finance_check_analytics"]
    kind = f"analytics/v2/{operation}/{symbol}"
    benchmark = dict(query).get("benchmark")
    honest = analytics.compute(coinbase_client(OTHER), operation, symbol, "coinbase", benchmark)
    check(honest, kind, query, "GET")
    nested = [key for key in ("asset", "benchmark") if honest["inputs"].get(key)]
    assert nested == (["asset", "benchmark"] if benchmark else ["asset"])
    # The whole envelope re-stamped by another runtime: nested data disagrees.
    with pytest.raises(ValueError, match="CANONICAL_REVISION_INCONSISTENT"):
        check(reenvelope(honest, "3" * 40), kind, query, "GET")
    for key in nested:
        # One nested observation alone comes from another runtime.
        partial = deepcopy(honest)
        partial["inputs"][key]["observation"] = analytics.compute(
            coinbase_client("3" * 40), operation, symbol, "coinbase", benchmark)["inputs"][key]["observation"]
        with pytest.raises(ValueError, match="CANONICAL_REVISION_INCONSISTENT"):
            check(reenvelope(partial, OTHER), kind, query, "GET")


def test_projection_supports_the_contract_this_repository_serves():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("contract_pair", root / "scripts/hf_finance_read_proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)
    assert proxy.CONTRACT["name"] == contract.NAME
    assert proxy.CONTRACT["header"] == contract.HEADER.lower()
    supported = set(proxy.CONTRACT["supported_versions"]) & set(contract.VERSIONS)
    assert supported, "same-commit A11oy and Finance must share a contract version"
    # Every response schema the projection validates is covered by that version.
    emitted = proxy._bound_source()
    validated = {s for s in contract.RESPONSE_SCHEMAS[max(supported)] if f'"{s}"' in emitted}
    assert validated == set(contract.RESPONSE_SCHEMAS[max(supported)])
    assert "CANONICAL_REVISION_MISMATCH" not in emitted
    assert 'CFG.get("source_revision"' not in emitted.split("def finance_version", 1)[0]