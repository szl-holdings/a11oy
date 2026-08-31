"""QA input-hardening regression tests (QA squad, 2026-06-04).

Covers a class of robustness bugs found while stress/edge-testing the live
a11oy Space: several POST handlers called ``await request.json()`` (or assumed a
dict body) without guarding empty / malformed / wrong-type input. An unguarded
parse becomes an opaque HTTP 500 with a trace_id — a poor demo/judge experience
and a minor error-shape leak. Every public POST surface must instead answer with
a clean 400 (or a graceful fallback) and never a 500 on bad input.

Boots the real app in-process via Starlette TestClient (no mocks).
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


# --- /api/a11oy/v1/mcp/call -------------------------------------------------

def test_mcp_call_valid_tool_ok(client):
    r = client.post("/api/a11oy/v1/mcp/call", json={"name": "lambda_score"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_mcp_call_unknown_tool_404(client):
    r = client.post("/api/a11oy/v1/mcp/call", json={"name": "bogus"})
    assert r.status_code == 404


def test_mcp_call_empty_body_is_400_not_500(client):
    r = client.post("/api/a11oy/v1/mcp/call", content=b"")
    assert r.status_code == 400


def test_mcp_call_malformed_json_is_400_not_500(client):
    r = client.post("/api/a11oy/v1/mcp/call", content=b"{not json")
    assert r.status_code == 400


def test_mcp_call_array_body_is_400_not_500(client):
    r = client.post("/api/a11oy/v1/mcp/call", json=[1, 2, 3])
    assert r.status_code == 400


# --- /api/a11oy/v1/policy/evaluate ------------------------------------------

def test_policy_evaluate_array_body_is_400_not_500(client):
    r = client.post("/api/a11oy/v1/policy/evaluate", json=[1, 2, 3])
    assert r.status_code == 400


def test_policy_evaluate_empty_body_is_400(client):
    r = client.post("/api/a11oy/v1/policy/evaluate", content=b"")
    assert r.status_code == 400


def test_policy_evaluate_malformed_is_400(client):
    r = client.post("/api/a11oy/v1/policy/evaluate", content=b"{bad")
    assert r.status_code == 400


# --- /api/a11oy/v1/reason (already guarded — lock it in) ---------------------

def test_reason_empty_body_is_400(client):
    r = client.post("/api/a11oy/v1/reason", content=b"")
    assert r.status_code == 400


# --- Wire I rosie-companion handlers (registered conditionally) -------------

@pytest.mark.parametrize("path", [
    "/api/a11oy/v1/rosie-companion/ponder",
    "/api/a11oy/v1/rosie-companion/synthesize",
    "/api/a11oy/v1/rosie-companion/evolve",
    "/api/a11oy/v1/rosie-companion/brain-jack",
    "/api/a11oy/v1/code/chat-with-rosie",
])
def test_rosie_companion_bad_input_never_500(client, path):
    """Empty + malformed bodies must not produce a 500. If the Wire I router is
    not registered on this build the route 404s, which is also acceptable (the
    point is: no 500 on bad input)."""
    for payload in (b"", b"{not json"):
        r = client.post(path, content=payload)
        assert r.status_code != 500, f"{path} returned 500 on bad input"


# --- substrate sanity: bad formula id is a clean 404, not a 500 -------------

def test_unknown_formula_is_404(client):
    r = client.get("/api/a11oy/v1/puriq/formulas/F999")
    assert r.status_code == 404
