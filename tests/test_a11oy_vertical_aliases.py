"""Canonical a11oy vertical and capability-route regression tests.

Doctrine v11 removed the retired public organ codenames. Owner directive
``owner-2026-09-04-sentra-assurance-command`` later restored two exact Sentra
assurance read contracts without restoring a general legacy prefix. The
supported capability API remains under ``/api/a11oy``. These tests boot the real
application in-process (no mocks) and prove all parts of that contract:

* supported routes execute successfully; and
* the two owner-authorized Sentra routes use the live Immune data; and
* all other retired names remain absent and fail closed.
"""

import warnings

import pytest

warnings.filterwarnings("ignore")

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


FRIENDLY_ROUTES = [
    ("GET", "/api/a11oy/v1/sentinel/gates", None),
    ("GET", "/api/a11oy/v1/sentinel/threats/full", None),
    ("GET", "/api/a11oy/v1/sentinel/verdict/feed", None),
    ("POST", "/api/a11oy/v1/sentinel/verdict", {"agent": "test", "action": {"value": "noop"}, "request_id": "canonical"}),
    ("POST", "/api/a11oy/v1/sentinel/elite/compliance", {"framework": "NIST"}),
    ("GET", "/api/a11oy/v1/sentinel/forecast/run", None),
    ("GET", "/api/a11oy/v1/memory/llm/tiers", None),
    ("POST", "/api/a11oy/v1/memory/readiness/assess", {"subject": "test", "records": {}}),
    ("POST", "/api/a11oy/v1/operator/ask", {"question": "which services are live?"}),
    ("POST", "/api/a11oy/v1/operator/act", {"action": "acknowledge", "target": "test"}),
    ("GET", "/api/a11oy/v1/operator/recommend", None),
    ("GET", "/api/a11oy/v1/operator/mesh/3d", None),
]


@pytest.mark.parametrize("method,path,payload", FRIENDLY_ROUTES)
def test_friendly_vertical_route_is_live(client, method, path, payload):
    response = client.post(path, json=payload) if method == "POST" else client.get(path)
    assert response.status_code == 200, f"{method} {path} regressed to {response.status_code}"
    assert isinstance(response.json(), dict)


GOVERNED_CAPABILITY_ROUTES = [
    ("GET", "/api/a11oy/v1/policy/gates", None),
    ("GET", "/api/a11oy/v1/policy/threats", None),
    ("GET", "/api/a11oy/v1/forecast/run", None),
    ("GET", "/api/a11oy/v1/reason/tiers", None),
    ("POST", "/api/a11oy/v1/policy/decide", {"agent": "test", "action": {"value": "noop"}, "request_id": "governed"}),
    ("POST", "/api/a11oy/v1/policy/compliance", {"framework": "STIG"}),
    ("POST", "/api/a11oy/v1/reason/readiness", {"subject": "test", "records": {}}),
    ("GET", "/api/a11oy/v1/operator/recommend", None),
    ("GET", "/api/a11oy/v1/operator/ledger", None),
    ("GET", "/api/a11oy/v2/operator/command-log", None),
    ("GET", "/api/a11oy/v1/capabilities/mesh", None),
]


@pytest.mark.parametrize("method,path,payload", GOVERNED_CAPABILITY_ROUTES)
def test_neutral_capability_route_is_governed(client, method, path, payload):
    response = client.post(path, json=payload) if method == "POST" else client.get(path)
    assert response.status_code == 200, f"{method} {path} regressed to {response.status_code}"
    body = response.json()
    assert body.get("status") == "REAL"
    assert isinstance(body.get("citations"), list)
    assert isinstance(body.get("fetchedAt"), str) and body["fetchedAt"]


SENTRA_ASSURANCE_ROUTES = (
    "/api/sentra/v1/gates",
    "/api/sentra/v1/audit-log",
)
RETIRED_PREFIXES = ("/api/amaru", "/api/rosie")
RETIRED_PROBES = [
    ("GET", "/api/amaru/v1/llm/tiers", None),
    ("POST", "/api/rosie/v1/jarvis/ask", {"question": "test"}),
    ("GET", "/api/rosie/v1/mesh/3d", None),
]


def test_sentra_assurance_routes_are_exact_and_precede_spa_catch_all(client):
    paths = [getattr(route, "path", "") for route in serve.app.routes]
    sentra_paths = sorted(path for path in paths if path.startswith("/api/sentra"))
    assert sentra_paths == sorted(SENTRA_ASSURANCE_ROUTES)
    catch_all = paths.index("/{full_path:path}")
    assert all(paths.index(path) < catch_all for path in SENTRA_ASSURANCE_ROUTES)

    gates = client.get(SENTRA_ASSURANCE_ROUTES[0])
    assert gates.status_code == 200
    assert gates.json()["total"] == 8
    assert len(gates.json()["gates"]) == 8

    audit = client.get(SENTRA_ASSURANCE_ROUTES[1], params={"limit": 2})
    assert audit.status_code == 200
    body = audit.json()
    assert body["status"] == "REAL"
    assert body["source"] == "/api/a11oy/v1/immune/feed"
    assert body["limit"] == 2
    assert len(body["entries"]) <= 2


@pytest.mark.parametrize("payload", [{}, {"action": None}, {"action": {}}, {"action": "  "}])
def test_canonical_immune_verdict_receipts_default_deny_missing_action(client, payload):
    response = client.post("/api/a11oy/v1/immune/verdict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "deny"
    assert body["fail_closed"] is True
    assert body["signals"] == ["contract:action-required"]
    assert body["khipu_receipt"]["digest"]


def test_retired_names_are_absent_from_explicit_routes():
    paths = {getattr(route, "path", "") for route in serve.app.routes}
    leaked = sorted(path for path in paths if path.startswith(RETIRED_PREFIXES) or "/jarvis" in path)
    assert leaked == [], f"retired public routes reappeared: {leaked}"


@pytest.mark.parametrize("method,path,payload", RETIRED_PROBES)
def test_retired_routes_fail_closed(client, method, path, payload):
    response = client.post(path, json=payload) if method == "POST" else client.get(path)
    assert response.status_code in (404, 405), f"retired route unexpectedly served: {method} {path}"
