"""Legacy rosie-shaped operator endpoint regression tests (Task #1016, 2026-06-15).

The a11oy operator capability endpoints emit the full governed envelope
(``status`` in {REAL, DEMO, DEGRADED} + a ``citations`` list + a ``fetchedAt``
timestamp) after Task #516 / #751. Their legacy "rosie-shaped" twins serve the
SAME in-process data but historically returned the bare payload, leaving the two
surfaces inconsistent. Task #1016 wraps each rosie handler in the idempotent
``gov_envelope`` (additive — preserves all underlying data) so the rosie surface
stays in lockstep with its a11oy twin:

  * GET  /api/rosie/v1/jarvis/recommend   (mirror of /api/a11oy/v1/operator/recommend)
  * GET  /api/rosie/v1/ledger             (mirror of /api/a11oy/v1/operator/ledger)
  * GET  /api/rosie/v2/command-log        (mirror of /api/a11oy/v2/operator/command-log)
  * POST /api/rosie/v1/jarvis/ask         (mirror of /api/a11oy/v1/operator/ask)
  * POST /api/rosie/v1/jarvis/act         (mirror of /api/a11oy/v1/operator/act)

These routes are registered inside the SAME defensive ``try/except`` block as the
a11oy twins, so a future edit that breaks the block (or strips an envelope) would
silently regress the surface. This module locks the contract in by booting the
real app in-process via Starlette TestClient (no mocks). It guards against:
  1. routes regressing to 404 (each must be 200),
  2. the governed envelope being stripped, and
  3. the envelope replacing (rather than wrapping) the underlying payload.
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


def _assert_envelope(body):
    """Every governed response must carry the full envelope, unstripped."""
    assert isinstance(body, dict), f"expected a JSON object, got {type(body).__name__}"
    assert body.get("status") in ("REAL", "DEMO", "DEGRADED"), \
        f"missing/invalid governed status: {body.get('status')!r}"
    assert isinstance(body.get("citations"), list), \
        f"citations must be a list, got {type(body.get('citations')).__name__}"
    assert isinstance(body.get("fetchedAt"), str) and body["fetchedAt"], \
        "fetchedAt must be a non-empty timestamp string"


# --- GET rosie surfaces: must be 200 (not 404) and carry the envelope ------

@pytest.mark.parametrize("path", [
    "/api/rosie/v1/jarvis/recommend",
    "/api/rosie/v1/ledger",
    "/api/rosie/v2/command-log",
])
def test_rosie_get_surface_200_and_governed(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"GET {path} regressed to {r.status_code}"
    _assert_envelope(r.json())


# --- POST rosie surfaces: must be 200 (not 404) and carry the envelope -----

@pytest.mark.parametrize("path,payload", [
    ("/api/rosie/v1/jarvis/ask", {"question": "which services are live?"}),
    ("/api/rosie/v1/jarvis/act", {"action": "acknowledge", "target": "demo", "note": "regression test"}),
])
def test_rosie_post_surface_200_and_governed(client, path, payload):
    r = client.post(path, json=payload)
    assert r.status_code == 200, f"POST {path} regressed to {r.status_code}"
    _assert_envelope(r.json())


# --- the envelope must WRAP, never replace, the underlying payload ---------

def test_rosie_recommend_keeps_payload_under_envelope(client):
    r = client.get("/api/rosie/v1/jarvis/recommend")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert isinstance(body.get("recommendations"), list), \
        "rosie/recommend dropped its recommendations list"


def test_rosie_ledger_and_cmdlog_keep_records_under_envelope(client):
    rl = client.get("/api/rosie/v1/ledger")
    assert rl.status_code == 200
    bl = rl.json()
    _assert_envelope(bl)
    assert isinstance(bl.get("receipts"), list), "rosie/ledger dropped its receipts list"

    rc = client.get("/api/rosie/v2/command-log")
    assert rc.status_code == 200
    bc = rc.json()
    _assert_envelope(bc)
    assert isinstance(bc.get("receipts"), list), "rosie/command-log dropped its receipts list"


# --- the rosie twin must match its governed a11oy twin (same data, both wrapped) ---

def test_rosie_ledger_matches_a11oy_twin(client):
    rosie = client.get("/api/rosie/v1/ledger").json()
    a11oy = client.get("/api/a11oy/v1/operator/ledger").json()
    _assert_envelope(rosie)
    _assert_envelope(a11oy)
    assert rosie.get("receipts") == a11oy.get("receipts"), \
        "rosie/ledger and a11oy operator/ledger must serve identical records"


def test_rosie_cmdlog_matches_a11oy_twin(client):
    rosie = client.get("/api/rosie/v2/command-log").json()
    a11oy = client.get("/api/a11oy/v2/operator/command-log").json()
    _assert_envelope(rosie)
    _assert_envelope(a11oy)
    assert rosie.get("receipts") == a11oy.get("receipts"), \
        "rosie/command-log and a11oy operator/command-log must serve identical records"
