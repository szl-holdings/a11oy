"""QA input-hardening regression tests (QA squad, 2026-06-04).

While stress/edge-testing the live amaru Space, two POST handlers returned an
opaque HTTP 500 (internal_error + trace_id) on empty / malformed / wrong-type
JSON bodies:

  POST /api/amaru/v1/mcp/call  -> 500 on empty / malformed / array
                                  (unguarded await request.json())
  POST /api/amaru/v1/reason    -> 500 on a JSON array body
                                  (.get() on a list after a guarded parse)

Every public POST surface must answer with a clean 4xx (or graceful fallback)
and never a 500 on bad input. Boots the real app in-process (no mocks).
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


@pytest.mark.parametrize("payload", [b"", b"{not json", b"[1,2,3]"])
def test_mcp_call_bad_input_is_400_not_500(client, payload):
    r = client.post("/api/amaru/v1/mcp/call", content=payload)
    assert r.status_code != 500
    assert r.status_code == 400


def test_mcp_call_valid_tool_ok(client):
    r = client.post("/api/amaru/v1/mcp/call", json={"name": "ask", "arguments": {"query": "x"}})
    assert r.status_code == 200


def test_mcp_call_unknown_tool_404(client):
    r = client.post("/api/amaru/v1/mcp/call", json={"name": "bogus"})
    assert r.status_code == 404


@pytest.mark.parametrize("payload", [b"", b"{not json", b"[1,2,3]"])
def test_reason_bad_input_never_500(client, payload):
    r = client.post("/api/amaru/v1/reason", content=payload)
    assert r.status_code != 500
    # 400 (question required / invalid body) or 503 (reason modules unavailable
    # in a bare test env) are both acceptable — the point is: never a 500.
    assert r.status_code in (400, 503)


# --- substrate sanity: REAL signing path stays graceful under odd input -----

def test_khipu_sign_handles_injection_string(client):
    r = client.post("/api/amaru/khipu/sign",
                    json={"receipt": {"decision": "<script>alert(1)</script> DROP TABLE x"}})
    assert r.status_code == 200
    # injection string must be carried as opaque payload, never reflected raw
    assert "<script>" not in r.text


def test_khipu_ledger_reads(client):
    r = client.get("/api/amaru/khipu/ledger")
    assert r.status_code == 200
    assert "count" in r.json()
