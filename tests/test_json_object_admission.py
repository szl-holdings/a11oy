"""JSON object admission for the parsed request handlers.

Non-objects are rejected. Valid objects still reach the handler. Operator
refusal stays ahead of parsing on the code completion route. The policy
string shorthand and GET handlers keep their existing parsers.
"""

import pytest

starlette_testclient = pytest.importorskip("starlette.testclient")
httpx = pytest.importorskip("httpx")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402

_OPERATOR = "test-operator-secret-not-real"
_JSON = {"content-type": "application/json"}
_NON_OBJECTS = (
    ("null", b"null"),
    ("array", b"[]"),
    ("string", b'"x"'),
    ("number", b"1"),
    ("boolean", b"true"),
)
_OPEN_ROUTES = (
    "/api/a11oy/v1/companion/ponder",
    "/api/a11oy/v1/companion/synthesize",
    "/api/a11oy/v1/companion/brain-jack",
    "/api/a11oy/v1/code/chat-deep",
    "/api/a11oy/v1/policy/decide",
    "/api/a11oy/v1/policy/compliance",
    "/api/a11oy/v1/reason/readiness",
    "/api/a11oy/v1/operator/ask",
)
_GATED_ROUTES = (
    "/api/a11oy/v1/companion/evolve",
    "/api/a11oy/v1/mcp/call",
    "/api/a11oy/v1/companion/act",
    "/api/a11oy/v2/operator/command",
)


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


def _post(client, path, payload, headers=None):
    merged = dict(_JSON)
    if headers:
        merged.update(headers)
    return client.post(path, content=payload, headers=merged)


def _auth(monkeypatch):
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", _OPERATOR)
    return {"Authorization": f"Bearer {_OPERATOR}"}


@pytest.mark.parametrize("path", _OPEN_ROUTES)
@pytest.mark.parametrize("label,payload", _NON_OBJECTS)
def test_open_routes_reject_non_objects(client, path, label, payload):
    response = _post(client, path, payload)
    assert response.status_code == 400, label
    assert response.json()["error"] == "JSON body must be an object"


@pytest.mark.parametrize("path", _GATED_ROUTES)
@pytest.mark.parametrize("label,payload", _NON_OBJECTS)
def test_gated_routes_refuse_before_admission(client, monkeypatch, path, label, payload):
    monkeypatch.delenv("A11OY_CODE_ADMIN_KEY", raising=False)
    anonymous = _post(client, path, payload)
    assert anonymous.status_code == 401, label
    assert anonymous.json()["status"] == "BLOCKED"
    authorized = _post(client, path, payload, _auth(monkeypatch))
    assert authorized.status_code == 400, label
    assert authorized.json()["error"] == "JSON body must be an object"


def test_valid_objects_reach_existing_handlers(client):
    chat = client.post("/api/a11oy/v1/code/chat-deep", json={"tier": "T3", "query": "local check"})
    assert chat.status_code == 200
    assert chat.json()["routed_to"] == "a11oy-local-router"
    assert chat.json()["deep_tier_consulted"] is False

    decide = client.post(
        "/api/a11oy/v1/policy/decide",
        json={"agent": "test", "action": {"value": "noop"}, "request_id": "object-admission"},
    )
    assert decide.status_code == 200
    assert isinstance(decide.json(), dict)

    compliance = client.post("/api/a11oy/v1/policy/compliance", json={"framework": "NIST"})
    assert compliance.status_code == 200
    assert isinstance(compliance.json(), dict)

    ask = client.post("/api/a11oy/v1/operator/ask", json={"question": "which services are live?"})
    assert ask.status_code == 200
    assert isinstance(ask.json(), dict)


def test_completion_authorizes_before_parsing(client, monkeypatch):
    monkeypatch.delenv("A11OY_CODE_ADMIN_KEY", raising=False)
    for payload in (b"null", b"[", b'"x"', b"1", b"true", b'{"query":"ping"}'):
        response = _post(client, "/api/a11oy/v1/code/complete", payload)
        assert response.status_code == 401
        assert response.json()["status"] == "BLOCKED"

    headers = _auth(monkeypatch)
    for payload in (b"null", b"[]", b'"x"', b"1", b"false"):
        response = _post(client, "/api/a11oy/v1/code/complete", payload, headers)
        assert response.status_code == 400
        assert response.json()["error"] == "JSON body must be an object"
    malformed = _post(client, "/api/a11oy/v1/code/complete", b"[", headers)
    assert malformed.status_code == 400
    assert malformed.json()["error"] == "invalid JSON body"
    admitted = _post(client, "/api/a11oy/v1/code/complete", b"{}", headers)
    assert admitted.status_code == 400
    assert admitted.json()["error"] == "missing 'query'"
    typed = client.post(
        "/api/a11oy/v1/code/complete",
        json={"query": 1},
        headers=headers,
    )
    assert typed.status_code == 400
    assert typed.json()["error"] == "query must be a string"


def test_policy_shorthand_and_reason_and_get_stay(client, monkeypatch):
    class _Offline:
        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(serve, "_http_client", _Offline())
    shorthand = _post(client, "/api/a11oy/v1/policy/evaluate", b'"medium"')
    assert shorthand.status_code == 503
    assert shorthand.json()["error"] == "backend unavailable"

    array = _post(client, "/api/a11oy/v1/policy/evaluate", b"[]")
    assert array.status_code == 400
    assert array.json()["error"].startswith("body must be {action:")

    reason = _post(client, "/api/a11oy/v1/reason", b"[]")
    assert reason.status_code == 400
    assert reason.json()["error"].startswith("expected")

    gate = client.get("/api/a11oy/v1/yuyay/gate", params={"proposal": "local"})
    assert gate.status_code == 200
    assert isinstance(gate.json(), dict)

    health = client.get("/api/a11oy/v1/code/health")
    assert health.status_code == 200
    assert isinstance(health.json(), dict)
