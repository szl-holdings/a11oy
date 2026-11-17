#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline route tests. All action/signing/storage dependencies are isolated fakes.

No provider credential, project signer, live service or real receipt is loaded.
The deliberately invalid fixture signature proves only the NOT_PERFORMED label.
"""

import asyncio
import builtins
import copy
import hashlib
import importlib.util
import json
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
READS = {
    "heart": "/yuyay-13/vote", "blood": "/khipu/chain", "immune": "/immune/observation",
    "skeleton": "/lambda/convergence", "nervous": "/spans/recent",
    "wires": "/orchestrate/routing", "body": "/body/composed",
}
PAGES = ("yuyay-13", "khipu-chain-3d", "immune-3d", "lambda-spine-3d",
         "nervous-3d", "wires-3d", "body-3d")
PRIVATE_DEPENDENCIES = {"szl_dsse", "szl_khipu", "szl_formulas", "a11oy_v4_formulas"}


def _trap(*args, **kwargs):
    raise AssertionError("read attempted an effect or runtime dependency")


def _load_source(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    original_import = builtins.__import__

    def isolated_import(name, *args, **kwargs):
        if name.split(".")[0] in PRIVATE_DEPENDENCIES:
            raise AssertionError("project signing/action dependency import forbidden")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", isolated_import):
        spec.loader.exec_module(module)
    return module


def load_anatomy_module():
    """Reusable safe loader for the browser contract's real registered-GET cases."""
    return _load_source("szl_anatomy_3d.py", "anatomy_observation_fixture")


class Clock:
    def __init__(self):
        self.wall = time.time()
        self.mono = 100.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


class Dag:
    def __init__(self, ns, organ, clock):
        self.ns, self.organ, self.clock = ns, organ, clock
        self._chain = []
        self._lock = threading.Lock()

    def emit(self, action, payload):
        with self._lock:
            body = {"organ": self.organ, "ns": self.ns, "seq": len(self._chain),
                    "action": action, "payload_digest": hashlib.sha3_256(
                        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                    "ts": self.clock.time(),
                    "prev": self._chain[-1]["digest"] if self._chain else "0" * 64}
            digest = hashlib.sha3_256(json.dumps(body, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()
            row = {**body, "digest": digest, "chain_verified": True,
                   "signature": "FIXTURE_INVALID_SIGNATURE"}
            self._chain.append(row)
            return copy.deepcopy(row)


class Khipu:
    def __init__(self, clock):
        self.clock = clock
        self._REGISTRY = {}
        self._REG_LOCK = threading.Lock()
        self.write_lookups = []

    def get_dag(self, organ, ns):
        self.write_lookups.append((ns, organ))
        with self._REG_LOCK:
            return self._REGISTRY.setdefault(f"{ns}/{organ}", Dag(ns, organ, self.clock))


class Signer:
    public_key_fingerprint = signing_available = _load_private_key = staticmethod(_trap)

    def __init__(self):
        self.calls = []

    def sign_khipu_receipt(self, body, neuro=None):
        self.calls.append(copy.deepcopy(body))
        return {"receipt": copy.deepcopy(body),
                "dsse": {"signed": True,
                         "signatures": [{"keyid": "fixture-key-id", "sig": "FIXTURE_NOT_A_SIGNATURE"}]}}


def default_projection_responses():
    """Real registered GET outputs with empty, isolated process dependencies."""
    module = load_anatomy_module()
    module._KHIPU = Khipu(Clock())
    module._write_dependency = _trap
    observer = types.SimpleNamespace(recent_traces=lambda **kwargs: [])
    with patch.dict(sys.modules, {"szl_observability": observer}):
        app = FastAPI()
        module.register(app)
        with TestClient(app) as client:
            return {kind: client.get("/api/a11oy/v4" + path).json() for kind, path in READS.items()}


@pytest.fixture
def isolated(monkeypatch):
    module = load_anatomy_module()
    clock, signer = Clock(), Signer()
    khipu = Khipu(clock)
    evaluations = []

    def evaluate(slug, inputs, config):
        evaluations.append((slug, copy.deepcopy(inputs)))
        return {"verdict": "ALLOW"}

    v4 = types.SimpleNamespace(_BY_SLUG={}, evaluate=evaluate)
    module.time = clock
    module._DSSE, module._KHIPU, module._V4 = signer, khipu, v4
    module._SF = types.SimpleNamespace(axis_floors=lambda: [0.95, 0.95] + [0.90] * 11)
    dependencies = {"szl_dsse": signer, "szl_khipu": khipu,
                    "a11oy_v4_formulas": v4, "szl_formulas": module._SF}
    monkeypatch.setattr(module, "_write_dependency", lambda name, override: override or dependencies[name])
    monkeypatch.setitem(sys.modules, "szl_observability", types.SimpleNamespace(recent_traces=lambda **kwargs: []))
    auth = _load_source("szl_operator_auth.py", "anatomy_operator_fixture")
    # Replace the credential reader before any principal/refusal evaluation.
    auth.secret_matches = lambda presented, env_name: presented == "fixture-operator"
    auth.blocked_body = lambda action, needs_second_approver=False: {"ok": False, "status": "BLOCKED"}
    monkeypatch.setitem(sys.modules, "szl_operator_auth", auth)
    app = FastAPI()
    module.register(app)
    module.register(app, ns="tenant_two")
    return types.SimpleNamespace(module=module, clock=clock, signer=signer, khipu=khipu,
                                 evaluations=evaluations, auth=auth, app=app, client=TestClient(app))


def _authorized(client, path, body=None):
    return client.post(path, json={} if body is None else body,
                       headers={"Authorization": "Bearer fixture-operator"})


def _assert_read_boundary(body):
    assert body["schema"] == "szl.anatomy.observation/v1"
    assert body["mode"] == "READ_ONLY"
    assert body["storage_writes"] == 0 and body["receipt_minted_on_get"] is False
    assert body["execution_authorized"] is False and body["execution_performed"] is False
    assert body["signature_verified"] is False and body["signature_verification"] == "NOT_PERFORMED"
    assert body["source_revision"] is None and body["runtime_boot_id"] is None
    assert body["joules_measured"] is None and body["energy_label"] == "UNAVAILABLE"


@pytest.mark.parametrize("kind", READS)
def test_repeated_registered_get_and_head_are_inert(isolated, monkeypatch, kind):
    env = isolated
    monkeypatch.setattr(env.module, "_write_dependency", _trap)
    monkeypatch.setattr(env.khipu, "get_dag", _trap)
    before = copy.deepcopy(env.module._CACHE)
    for _ in range(2):
        response = env.client.get("/api/a11oy/v4" + READS[kind])
        assert response.status_code == 200
        _assert_read_boundary(response.json())
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["state"] == ("MODELED" if kind == "immune" else "UNAVAILABLE")
        head = env.client.head("/api/a11oy/v4" + READS[kind])
        assert head.status_code == 200 and head.content == b""
    assert env.module._CACHE == before
    assert env.khipu._REGISTRY == {} and not env.signer.calls and not env.evaluations


@pytest.mark.parametrize("page", PAGES)
def test_page_generation_does_not_resolve_runtime_dependencies(isolated, monkeypatch, page):
    monkeypatch.setattr(isolated.module, "_write_dependency", _trap)
    response = isolated.client.get("/" + page)
    assert response.status_code == 200
    assert 'method:"POST"' not in response.text and "https://SZLHOLDINGS-sentra" not in response.text
    assert "CapsuleGeometry" not in response.text
    assert response.text.index("/assets/szl/szl-design-system.css") < response.text.index("<style>")
    assert "Historical snapshot: 749/14/163" in response.text
    assert "exactly 8 locked formulas" in response.text and "Conjecture 1" in response.text
    assert not isolated.signer.calls and not isolated.khipu._REGISTRY


def test_registration_and_v6_redirect_are_inert(isolated, monkeypatch):
    monkeypatch.setattr(isolated.module, "_write_dependency", _trap)
    result = isolated.module.register(FastAPI(), ns="isolated_ns")
    assert result["signature_verification"] == "NOT_PERFORMED"
    assert "cosign_fingerprint" not in result and "signing_available" not in result
    response = isolated.client.get("/body-3d-v6", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/holographic#brainreranker"


@pytest.mark.parametrize("namespace", ["a11oy", "tenant_two"])
@pytest.mark.parametrize("suffix", ["/yuyay-13/vote", "/orchestrate/routing"])
def test_handler_denies_before_body_read(isolated, namespace, suffix):
    path = f"/api/{namespace}/v4{suffix}"
    endpoint = next(route.endpoint for route in isolated.app.routes
                    if getattr(route, "path", None) == path and "POST" in route.methods)

    class RequestTrap:
        headers = {}

        async def stream(self):
            raise AssertionError("denied request body was read")
            yield b""

    response = asyncio.run(endpoint(RequestTrap()))
    assert response.status_code == 401
    assert not isolated.signer.calls and not isolated.khipu.write_lookups and not isolated.evaluations


@pytest.mark.parametrize("namespace", ["a11oy", "tenant_two", "valid-ns_3"])
@pytest.mark.parametrize("suffix", ["/yuyay-13/vote", "/orchestrate/routing"])
def test_shared_middleware_admits_no_anonymous_receive(isolated, namespace, suffix):
    path = f"/api/{namespace}/v4{suffix}"
    assert isolated.auth.protected_action("POST", path)[1] == "sign"
    sent = []

    async def forbidden(*args):
        raise AssertionError("middleware reached body or handler")

    async def send(message):
        sent.append(message)

    gate = isolated.auth.OperatorGateMiddleware(forbidden)
    asyncio.run(gate({"type": "http", "method": "POST", "path": path, "headers": []}, forbidden, send))
    assert sent[0]["status"] == 401


def test_resolver_failure_denies_before_actions(isolated, monkeypatch):
    monkeypatch.setattr(isolated.auth, "principal", _trap)
    response = _authorized(isolated.client, "/api/a11oy/v4/yuyay-13/vote")
    assert response.status_code == 401
    assert not isolated.signer.calls and not isolated.evaluations


@pytest.mark.parametrize("kind,raw", [
    ("heart", b'{"scores":{"sound":NaN}}'), ("heart", b'{"scores":{"sound":Infinity}}'),
    ("heart", b'{"scores":{"sound":1e999}}'), ("heart", b'{"scores":{"sound":true}}'),
    ("heart", b'{"scores":{"sound":-1}}'), ("heart", b'{"scores":{"unknown":0.5}}'),
    ("heart", b'{"scores":{},"scores":{}}'), ("heart", b'{"extra":"private"}'),
    ("heart", b'[]'), ("heart", b'{invalid'),
    ("wires", b'{"energy_budget":1e999}'), ("wires", b'{"energy_budget":false}'),
    ("wires", b'{"routes":null}'), ("wires", b'{"routes":[]}'),
    ("wires", b'{"routes":[{"tier":"x","energy":-1}]}'),
    ("wires", b'{"routes":[{"tier":"x","energy":1,"admissible":"yes"}]}'),
    ("wires", b'{"routes":[{"tier":"<img>","energy":1}]}'),
    ("wires", b'{"routes":[{"tier":"x","energy":1,"private":"value"}]}'),
])
def test_invalid_inputs_have_no_effects(isolated, kind, raw):
    response = isolated.client.post("/api/a11oy/v4" + READS[kind], content=raw,
                                    headers={"Authorization": "Bearer fixture-operator",
                                             "Content-Type": "application/json"})
    assert response.status_code == 400
    assert not isolated.signer.calls and not isolated.khipu.write_lookups and not isolated.evaluations


def test_input_size_huge_integer_and_route_count_are_bounded(isolated):
    path = "/api/a11oy/v4/orchestrate/routing"
    for body in ({"energy_budget": 10 ** 400},
                 {"routes": [{"tier": f"r{i}", "energy": 1} for i in range(17)]}):
        assert _authorized(isolated.client, path, body).status_code == 400
    response = isolated.client.post(path, content=b" " * 16385,
                                    headers={"Authorization": "Bearer fixture-operator"})
    assert response.status_code == 400
    assert not isolated.signer.calls and not isolated.khipu.write_lookups


@pytest.mark.parametrize("kind,organ", [("heart", "yuyay"), ("wires", "kallpa")])
def test_authorized_write_reaches_its_namespaced_read_chain(isolated, monkeypatch, kind, organ):
    ns = "tenant_two"
    response = _authorized(isolated.client, f"/api/{ns}/v4" + READS[kind])
    assert response.status_code == 200 and response.json()["evidence_class"] == "SAMPLE"
    assert response.json()["execution_authorized"] is False
    assert all(namespace == ns for namespace, _ in isolated.khipu.write_lookups)
    calls = len(isolated.signer.calls), len(isolated.evaluations)
    monkeypatch.setattr(isolated.module, "_write_dependency", _trap)
    monkeypatch.setattr(isolated.khipu, "get_dag", _trap)
    current = isolated.client.get(f"/api/{ns}/v4" + READS[kind]).json()
    _assert_read_boundary(current)
    assert current["state"] == "OBSERVED" and current["evidence_class"] == "SAMPLE"
    assert current["receipt_signature_status"] == "UNVERIFIED" and current["signature_count"] == 1
    assert "FIXTURE_NOT_A_SIGNATURE" not in json.dumps(current)
    assert "receipt" not in current and "dsse" not in current
    chain = isolated.client.get(f"/api/{ns}/v4/khipu/chain?organ={organ}").json()
    _assert_read_boundary(chain)
    assert chain["state"] == "OBSERVED" and chain["data"]["organ"] == organ
    assert chain["data"]["pendants"][0]["ns"] == ns
    assert chain["chain_integrity"]["scope"] == "RETAINED_SUFFIX"
    assert chain["chain_verified"] is True and chain["signature_verified"] is False
    assert isolated.client.get("/api/a11oy/v4/khipu/chain?organ=" + organ).json()["state"] == "UNAVAILABLE"
    assert (len(isolated.signer.calls), len(isolated.evaluations)) == calls


def test_cache_is_deep_copied_and_input_identifiers_are_minimized(isolated):
    result = isolated.module.orchestrate_routing({"routes": [{"tier": "private-route-name", "energy": 0.2}]})
    isolated.module._remember_observation("a11oy", "wires", result)
    result["routes"][0]["energy"] = 500
    first = isolated.module.routing_observation()
    assert first["data"]["routes"][0]["energy"] == 0.2
    assert first["data"]["routes"][0]["tier"] == "sample-route-1"
    assert "private-route-name" not in json.dumps(first)
    first["data"]["routes"][0]["energy"] = 700
    assert isolated.module.routing_observation()["data"]["routes"][0]["energy"] == 0.2


def test_cache_expires_from_write_without_read_refresh(isolated):
    _authorized(isolated.client, "/api/a11oy/v4/yuyay-13/vote")
    before = copy.deepcopy(isolated.module._CACHE)
    isolated.clock.advance(59)
    assert isolated.module.yuyay_observation()["state"] == "OBSERVED"
    isolated.clock.advance(2)
    for _ in range(3):
        body = isolated.module.yuyay_observation()
        assert body["state"] == "STALE" and body["data"] is None
        assert body["signature_count"] == 0 and body["chain_verified"] is False
    assert isolated.module._CACHE == before
    assert isolated.module.lambda_convergence()["data"] is None


def test_cache_has_namespace_operation_and_byte_bounds(isolated):
    heart = isolated.module.yuyay_13_vote({})
    wires = isolated.module.orchestrate_routing({})
    for index in range(10):
        isolated.module._remember_observation(f"ns_{index}", "heart", heart)
        isolated.module._remember_observation(f"ns_{index}", "wires", wires)
    assert len(isolated.module._CACHE) == 8
    assert all(set(slots) == {"heart", "wires"} for slots in isolated.module._CACHE.values())
    assert isolated.module.yuyay_observation("ns_0")["state"] == "UNAVAILABLE"
    assert isolated.module.yuyay_observation("ns_9")["state"] == "OBSERVED"
    invalid = copy.deepcopy(heart)
    invalid["axes"][0]["axis"] = "x" * 20000
    before = copy.deepcopy(isolated.module._CACHE)
    with pytest.raises(ValueError):
        isolated.module._remember_observation("ns_9", "heart", invalid)
    assert isolated.module._CACHE == before
    for namespace in ("", "a11oy/other", "../a11oy", "a" * 65):
        with pytest.raises(ValueError):
            isolated.module.register(FastAPI(), ns=namespace)


@pytest.mark.parametrize("fault", ["missing", "empty", "malformed", "future", "expired", "broken"])
def test_chain_absence_failure_or_age_never_implies_verification(isolated, monkeypatch, fault):
    dag = isolated.khipu.get_dag("yuyay", "a11oy")
    if fault != "empty":
        dag.emit("sample", {})
    if fault == "missing":
        isolated.khipu._REGISTRY.clear()
    elif fault == "malformed":
        del dag._chain[0]["digest"]
    elif fault == "future":
        dag._chain[0]["ts"] += 30
    elif fault == "expired":
        isolated.clock.advance(61)
    elif fault == "broken":
        dag._chain[0]["digest"] = "a" * 64
    monkeypatch.setattr(isolated.khipu, "get_dag", _trap)
    result = isolated.module.khipu_chain()
    assert result["chain_verified"] is False and result["signature_verified"] is False
    if fault == "broken":
        assert result["chain_integrity"]["state"] == "INVALID"
    else:
        assert result["state"] in {"UNAVAILABLE", "STALE"} and result["data"] is None


def test_retained_suffix_never_claims_unseen_prefix(isolated, monkeypatch):
    dag = isolated.khipu.get_dag("yuyay", "a11oy")
    for _ in range(65):
        dag.emit("sample", {})
    before = copy.deepcopy(dag._chain)
    monkeypatch.setattr(isolated.khipu, "get_dag", _trap)
    result = isolated.module.khipu_chain()
    assert len(result["data"]["pendants"]) == 60 and result["data"]["truncated"] is True
    assert result["chain_integrity"] == {"state": "VERIFIED", "scope": "RETAINED_SUFFIX",
                                        "checked_records": 60, "prefix_verified": False}
    assert result["chain_verified"] is False and dag._chain == before


@pytest.mark.parametrize("query", ["since=nan", "since=inf", "since=-1", "organ=../yuyay", "organ=other"])
def test_invalid_chain_windows_fail_closed(isolated, query):
    response = isolated.client.get("/api/a11oy/v4/khipu/chain?" + query)
    assert response.status_code == 400
    assert response.json()["chain_verified"] is False
    assert not isolated.khipu.write_lookups


def _trace(env, **updates):
    row = {"trace_id": "private-inbound-request-id", "name": "private customer query <img>",
           "started_at": env.module._utc_at(env.clock.wall - 1), "duration_ms": 20.5,
           "span_count": 2, "status": "OK", "attributes": {"secret": "fixture private value"}}
    row.update(updates)
    return row


def test_process_traces_expose_only_minimized_summary(isolated, monkeypatch):
    row = _trace(isolated)
    observed = types.SimpleNamespace(recent_traces=lambda **kwargs: [row])
    monkeypatch.setitem(sys.modules, "szl_observability", observed)
    result = isolated.module.spans_recent("tenant_two")
    _assert_read_boundary(result)
    assert result["state"] == "OBSERVED" and result["data_scope"] == "PROCESS_WIDE_NOT_NAMESPACE_BOUND"
    projected = result["data"]["traces"][0]
    assert projected["name"] == "Process trace summary" and len(projected["trace_ref"]) == 64
    raw = json.dumps(result)
    assert "private" not in raw and "<img>" not in raw and "trace_id" not in raw and "attributes" not in raw
    assert result["data"]["span_count"] is None and result["data"]["correlation_only"] is True


@pytest.mark.parametrize("fault", ["future", "expired", "timezone", "nonfinite", "status", "empty", "exception"])
def test_trace_errors_and_age_do_not_relabel_unknown_as_observed(isolated, monkeypatch, fault):
    row = _trace(isolated)
    if fault == "future":
        row["started_at"] = isolated.module._utc_at(isolated.clock.wall + 1)
    elif fault == "expired":
        row["started_at"] = isolated.module._utc_at(isolated.clock.wall - 61)
    elif fault == "timezone":
        row["started_at"] = "2026-11-16T22:00:00"
    elif fault == "nonfinite":
        row["duration_ms"] = float("nan")
    elif fault == "status":
        row["status"] = "private free-text value"
    reader = _trap if fault == "exception" else lambda **kwargs: [] if fault == "empty" else [row]
    monkeypatch.setitem(sys.modules, "szl_observability", types.SimpleNamespace(recent_traces=reader))
    result = isolated.module.spans_recent()
    assert result["state"] in {"UNAVAILABLE", "STALE"} and result["data"] is None
    assert result["signature_verified"] is False


def test_fallback_receipt_cannot_fabricate_chain_or_signature(isolated, monkeypatch):
    monkeypatch.setattr(isolated.module, "_write_dependency", lambda *args: None)
    receipt = isolated.module._khipu_emit("sample", {})
    assert receipt["chain_verified"] is False and receipt["signature"] is None and receipt["digest"] is None
    signed = isolated.module._sign({"sample": True})
    assert signed["dsse"]["signatures"] == [] and signed["signature_status"] == "UNSIGNED"


def test_default_exporter_matches_all_registered_projection_kinds():
    responses = default_projection_responses()
    assert set(responses) == set(READS)
    for kind, payload in responses.items():
        _assert_read_boundary(payload)
        assert payload["kind"] == kind
        assert payload["state"] == ("MODELED" if kind == "immune" else "UNAVAILABLE")
