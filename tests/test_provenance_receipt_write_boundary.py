#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local request-boundary proof, not deployment or cryptographic readiness."""
import asyncio
import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import szl_khipu
import szl_operator_auth as auth
import szl_provenance_receipt as provenance

OPERATOR = "provenance-boundary-test-only-not-a-real-key"
PREFIXES = ("/api/a11oy/v1/provenance", "/v1/provenance",
            "/api/killinchu/v1/provenance")


@pytest.fixture
def isolated(monkeypatch):
    dag = szl_khipu.KhipuDAG("provenance", ns="a11oy")
    monkeypatch.setattr(szl_khipu, "get_dag", lambda *_args, **_kwargs: dag)
    monkeypatch.setattr(provenance, "_COMPOSITE_INDEX", {})
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, OPERATOR)
    monkeypatch.delenv(auth.SECOND_APPROVER_KEY_ENV, raising=False)
    app = FastAPI()
    provenance.register(app)
    provenance.register(app, ns="killinchu")
    with TestClient(app) as client:
        yield app, client, dag


def _snapshot(dag):
    return dag.depth(), dag.head(), copy.deepcopy(provenance._COMPOSITE_INDEX)


def _unreachable(*_args, **_kwargs):
    pytest.fail("read or refused request reached composition/body consumption")


def _stub_external_composers(monkeypatch):
    for name in ("_compose_immune", "_compose_pac_bayes", "_compose_energy",
                 "_compose_model", "_compose_lean"):
        monkeypatch.setattr(provenance, name, lambda *_args, **_kwargs: {
            "ok": False, "label": "UNAVAILABLE", "reason": "external source not run",
        })


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("method", ("GET", "HEAD"))
def test_empty_safe_reads_never_compose_or_mint(isolated, monkeypatch, prefix, method):
    _app, client, dag = isolated
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    response = client.request(method, prefix + "/receipt")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    if method == "GET":
        assert response.json()["status"] == "UNAVAILABLE"
        assert response.json()["digest"] is None
    else:
        assert response.content == b""
    assert _snapshot(dag) == before


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("method", ("GET", "HEAD"))
def test_recorded_reads_and_missing_digests_do_not_mint(isolated, monkeypatch, prefix, method):
    _app, client, dag = isolated
    _stub_external_composers(monkeypatch)
    first = provenance.build_composite({"action": "local test one"})
    latest = provenance.build_composite({"action": "local test two"})
    # Concurrent publication may finish indexing the earlier sequence last.
    provenance._COMPOSITE_INDEX.pop(first["digest"])
    provenance._COMPOSITE_INDEX[first["digest"]] = first
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    monkeypatch.setattr(dag, "emit", _unreachable)
    for suffix, expected in (("", 200), ("/" + first["digest"], 200),
                             ("/" + "f" * 64, 404)):
        response = client.request(method, prefix + "/receipt" + suffix)
        assert response.status_code == expected
        if expected == 200:
            digest = latest["digest"] if not suffix else first["digest"]
            assert response.headers["x-szl-provenance-digest"] == digest
            if method == "GET":
                assert "envelope" not in response.json()
                assert "DSSE_PLACEHOLDER" in response.json()["honesty"]["receipt_signature"]
        assert _snapshot(dag) == before


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("authorization", (None, "Bearer wrong-test-only",
                                          "Basic " + OPERATOR, "Bearer "))
def test_refusal_precedes_body_and_composition(isolated, monkeypatch, prefix, authorization):
    app, _client, dag = isolated
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    route = next(route for route in app.routes if route.path == prefix + "/receipt")
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    request = Request({"type": "http", "method": "POST", "path": prefix + "/receipt",
                       "headers": headers}, receive=_unreachable)
    response = asyncio.run(route.endpoint(request))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert _snapshot(dag) == before


@pytest.mark.parametrize("prefix", PREFIXES)
def test_body_cannot_assert_operator_authority(isolated, monkeypatch, prefix):
    _app, client, dag = isolated
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    response = client.post(prefix + "/receipt", json={
        "operator": True, "Authorization": "Bearer " + OPERATOR,
        "two_person_attested": True,
    })
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert _snapshot(dag) == before


@pytest.mark.parametrize("failure", ("unconfigured", "resolver_error"))
def test_missing_configuration_or_resolver_error_denies(isolated, monkeypatch, failure):
    app, _client, dag = isolated
    before = _snapshot(dag)
    if failure == "unconfigured":
        monkeypatch.delenv(auth.OPERATOR_KEY_ENV)
    else:
        def broken_resolver(_request):
            raise RuntimeError("local resolver fixture")
        monkeypatch.setattr(auth, "principal", broken_resolver)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    route = next(route for route in app.routes if route.path == PREFIXES[0] + "/receipt")
    request = Request({"type": "http", "method": "POST", "path": route.path,
                       "headers": [(b"authorization", ("Bearer " + OPERATOR).encode())]},
                      receive=_unreachable)
    assert asyncio.run(route.endpoint(request)).status_code == 401
    assert _snapshot(dag) == before


@pytest.mark.parametrize("prefix", PREFIXES)
def test_admitted_post_records_one_integrity_only_composite(isolated, monkeypatch, prefix):
    _app, client, dag = isolated
    _stub_external_composers(monkeypatch)
    response = client.post(prefix + "/receipt", headers={
        "Authorization": "Bearer " + OPERATOR,
    }, json={"action": "local boundary test", "request_id": "fixture"})
    assert response.status_code == 200
    envelope = response.json()
    assert dag.depth() == 1
    assert dag.verify_chain()["ok"] is True
    assert set(provenance._COMPOSITE_INDEX) == {envelope["digest"]}
    assert envelope["digest"] == dag.head()
    assert envelope["khipu"]["signature"] == "DSSE_PLACEHOLDER"
    assert "DSSE_PLACEHOLDER" in envelope["honesty"]["receipt_signature"]


def test_standalone_peer_is_gated_without_middleware(isolated, monkeypatch):
    _app, _client, dag = isolated
    app = FastAPI()
    provenance.register(app, ns="killinchu")
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    with TestClient(app) as client:
        assert client.post(PREFIXES[2] + "/receipt", json={}).status_code == 401
        assert client.post("/v1/provenance/receipt", json={}).status_code == 401
        assert client.post(PREFIXES[2] + "/receipt-extra", json={}).status_code == 404
    assert dag.depth() == 0


@pytest.mark.parametrize("prefix", PREFIXES)
def test_public_discovery_cannot_disclose_private_envelopes(isolated, monkeypatch, prefix):
    _app, client, dag = isolated
    _stub_external_composers(monkeypatch)
    action = {"private_note": "SYNTHETIC_PRIVATE_OPERATOR_NOTE"}
    envelope = provenance.build_composite({"action": action})
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    for suffix in ("", "/" + envelope["digest"]):
        public = client.get(prefix + "/receipt" + suffix)
        assert public.status_code == 200
        assert "envelope" not in public.json()
        assert action["private_note"] not in public.text
        private = client.get(prefix + "/receipt" + suffix, headers={
            "Authorization": "Bearer " + OPERATOR,
        })
        assert private.json()["envelope"]["action"] == action
        assert _snapshot(dag) == before


def test_read_identity_failure_is_metadata_only(isolated, monkeypatch):
    _app, client, dag = isolated
    _stub_external_composers(monkeypatch)
    envelope = provenance.build_composite({"action": "SYNTHETIC_PRIVATE_ACTION"})
    before = _snapshot(dag)
    def broken_resolver(_request):
        raise RuntimeError("local identity fixture")
    monkeypatch.setattr(provenance, "principal", broken_resolver)
    response = client.get(PREFIXES[0] + "/receipt/" + envelope["digest"], headers={
        "Authorization": "Bearer " + OPERATOR,
    })
    assert response.status_code == 200
    assert "envelope" not in response.json()
    assert "SYNTHETIC_PRIVATE_ACTION" not in response.text
    assert _snapshot(dag) == before


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("body,status", (
    ("{", 400), ("null", 422), ("[]", 422), ("{}", 422),
    ('{"action":null}', 422), ('{"action":{}}', 422),
    ('{"action":[]}', 422), ('{"action":""}', 422),
    ('{"action":"  "}', 422), ('{"action":true}', 422),
    ('{"action":1}', 422), ('{"action":{"value":NaN}}', 400),
    ('{"action":{"value":Infinity}}', 400),
    ('{"action":{"value":-Infinity}}', 400),
    ('{"action":{"value":1e999}}', 400),
    ('{"action":"\\ud800"}', 400),
    ('{"action":"valid","unused":NaN}', 400),
))
def test_invalid_admitted_body_is_rejected_before_composition(
        isolated, monkeypatch, prefix, body, status):
    _app, client, dag = isolated
    before = _snapshot(dag)
    monkeypatch.setattr(provenance, "build_composite", _unreachable)
    monkeypatch.setattr(dag, "emit", _unreachable)
    response = client.post(prefix + "/receipt", headers={
        "Authorization": "Bearer " + OPERATOR, "Content-Type": "application/json",
    }, content=body)
    assert response.status_code == status
    assert response.json()["status"] == "BLOCKED"
    assert _snapshot(dag) == before
