"""a11oy-vertical alias regression tests (Task #801, 2026-06).

The internal organ codenames are folded into a11oy as verticals:

  * amaru  -> a11oy Memory    (/api/a11oy/v1/memory/*)
  * sentra -> a11oy Sentinel  (/api/a11oy/v1/sentinel/*)
  * rosie  -> a11oy Operator  (/api/a11oy/v1/operator/*)

``serve.py`` registers a11oy-branded addresses (marker
``a11oy-vertical-aliases-task801``) that respond IDENTICALLY to the codename
routes (`/api/{amaru,sentra,rosie}/v1/*`) by reusing the SAME handler functions.
Both live side-by-side: the codename routes stay up for backward-compat until
consumers migrate. These routes live inside a defensive ``try/except`` block, so
a future edit that breaks the block (or drops a route) would silently regress the
whole vertical surface to 404 with no test catching it.

This module boots the real app in-process via Starlette TestClient (no mocks) and
guards:
  1. every a11oy-vertical route is live (200, not 404),
  2. the codename routes are STILL live (backward-compat not broken), and
  3. each vertical route's response is IDENTICAL to its codename route — byte for
     byte for the deterministic surfaces, and field-for-field (modulo per-call
     timestamps / receipt hashes) for the compute surfaces.
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


# --- 1. Every a11oy-vertical route is live (200, not 404) ------------------

@pytest.mark.parametrize("method,path,payload", [
    ("GET",  "/api/a11oy/v1/sentinel/gates", None),
    ("GET",  "/api/a11oy/v1/sentinel/threats/full", None),
    ("GET",  "/api/a11oy/v1/sentinel/verdict/feed", None),
    ("POST", "/api/a11oy/v1/sentinel/verdict", {"agent": "t", "action": {"value": "noop"}, "request_id": "t801"}),
    ("POST", "/api/a11oy/v1/sentinel/elite/compliance", {"framework": "NIST"}),
    ("GET",  "/api/a11oy/v1/sentinel/forecast/run", None),
    ("GET",  "/api/a11oy/v1/memory/llm/tiers", None),
    ("POST", "/api/a11oy/v1/memory/readiness/assess", {"subject": "demo", "records": {}}),
    ("POST", "/api/a11oy/v1/operator/ask", {"question": "which services are live?"}),
    ("POST", "/api/a11oy/v1/operator/act", {"action": "acknowledge", "target": "demo"}),
    ("GET",  "/api/a11oy/v1/operator/recommend", None),
    ("GET",  "/api/a11oy/v1/operator/mesh/3d", None),
])
def test_vertical_route_is_live(client, method, path, payload):
    r = client.post(path, json=payload) if method == "POST" else client.get(path)
    assert r.status_code == 200, f"{method} {path} regressed to {r.status_code}"


# --- 2. The codename routes are STILL live (backward-compat preserved) -----

@pytest.mark.parametrize("method,path,payload", [
    ("GET",  "/api/sentra/v1/gates", None),
    ("GET",  "/api/amaru/v1/llm/tiers", None),
    ("POST", "/api/rosie/v1/jarvis/ask", {"question": "which services are live?"}),
    ("GET",  "/api/rosie/v1/mesh/3d", None),
])
def test_codename_route_still_live(client, method, path, payload):
    r = client.post(path, json=payload) if method == "POST" else client.get(path)
    assert r.status_code == 200, f"codename {method} {path} broke (now {r.status_code})"


# --- 3a. Deterministic GET surfaces respond BYTE-IDENTICAL to the codename --

@pytest.mark.parametrize("codename,vertical", [
    ("/api/sentra/v1/gates",        "/api/a11oy/v1/sentinel/gates"),
    ("/api/sentra/v1/threats/full", "/api/a11oy/v1/sentinel/threats/full"),
    ("/api/sentra/v1/forecast/run", "/api/a11oy/v1/sentinel/forecast/run"),
    ("/api/amaru/v1/llm/tiers",     "/api/a11oy/v1/memory/llm/tiers"),
    ("/api/rosie/v1/mesh/3d",       "/api/a11oy/v1/operator/mesh/3d"),
])
def test_deterministic_get_is_identical(client, codename, vertical):
    rc = client.get(codename)
    rv = client.get(vertical)
    assert rc.status_code == rv.status_code == 200
    assert rc.json() == rv.json(), f"{vertical} diverged from {codename}"


# --- 3a-bis. The recommend pair is governed on BOTH sides (Task #751 governed
#     the a11oy twin; Task #1016 governed the rosie codename), so each carries a
#     per-call ``fetchedAt`` timestamp. They must be identical modulo that
#     volatile envelope field — compare with _strip_volatile.
def test_recommend_pair_identical_modulo_envelope(client):
    rc = client.get("/api/rosie/v1/jarvis/recommend")
    rv = client.get("/api/a11oy/v1/operator/recommend")
    assert rc.status_code == rv.status_code == 200
    bc, bv = rc.json(), rv.json()
    # Both surfaces must now carry the governed envelope.
    assert bc.get("status") == bv.get("status") == "REAL"
    assert isinstance(bc.get("fetchedAt"), str) and isinstance(bv.get("fetchedAt"), str)
    assert _strip_volatile(bc) == _strip_volatile(bv), \
        "rosie/recommend diverged from a11oy operator/recommend (modulo envelope timestamp)"


# --- 3b. Deterministic POST surfaces respond BYTE-IDENTICAL to the codename --

@pytest.mark.parametrize("codename,vertical,payload", [
    ("/api/sentra/v1/elite/compliance", "/api/a11oy/v1/sentinel/elite/compliance", {"framework": "STIG"}),
    ("/api/amaru/v1/readiness/assess",  "/api/a11oy/v1/memory/readiness/assess",
     {"subject": "demo", "records": {"medical_clearance": True}}),
])
def test_deterministic_post_is_identical(client, codename, vertical, payload):
    rc = client.post(codename, json=payload)
    rv = client.post(vertical, json=payload)
    assert rc.status_code == rv.status_code == 200
    assert rc.json() == rv.json(), f"{vertical} diverged from {codename}"


# --- 3c. Compute surfaces share the same logic / decision (modulo per-call
#         timestamps + receipt hashes that legitimately differ every call) ---

def _strip_volatile(d):
    """Drop fields that legitimately differ per call so the rest can be compared."""
    if isinstance(d, dict):
        return {k: _strip_volatile(v) for k, v in d.items()
                if k not in ("receipt_hash", "receipt", "ts_utc", "timestamp",
                             "entry", "entry_hash", "audit_depth", "actionId",
                             "id", "fetchedAt", "llm")}
    if isinstance(d, list):
        return [_strip_volatile(x) for x in d]
    return d


def test_sentinel_verdict_matches_codename_logic(client):
    payload = {"agent": "t801", "action": {"value": "DROP TABLE users"}, "request_id": "fixed-801"}
    rc = client.post("/api/sentra/v1/verdict", json=payload)
    rv = client.post("/api/a11oy/v1/sentinel/verdict", json=payload)
    assert rc.status_code == rv.status_code == 200
    bc, bv = rc.json(), rv.json()
    assert bc["decision"] == bv["decision"] == "deny"
    assert _strip_volatile(bc) == _strip_volatile(bv)


def test_operator_ask_matches_codename_logic(client):
    payload = {"question": "what is the lambda verdict?"}
    rc = client.post("/api/rosie/v1/jarvis/ask", json=payload)
    rv = client.post("/api/a11oy/v1/operator/ask", json=payload)
    assert rc.status_code == rv.status_code == 200
    bc, bv = rc.json(), rv.json()
    assert bc["topic"] == bv["topic"]
    assert bc["answer"] == bv["answer"]
    assert bc["citations"] == bv["citations"]
