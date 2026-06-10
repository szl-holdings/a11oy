"""Operator & reason endpoint regression tests (Task #516 / #601, 2026-06-09).

Task #516 added the self-contained governed operator + reason capability surface
to a11oy (marker ``a11oy-operator-reason-envelope-task516`` in ``serve.py``):

  * GET  /api/a11oy/v1/operator/ask        (descriptor + grounded answer via ?question=)
  * POST /api/a11oy/v1/operator/ask        (grounded operator Q&A)
  * POST /api/a11oy/v1/operator/act        (HITL hash-chained action ring)
  * GET  /api/a11oy/v1/reason              (governed reasoning gate descriptor)
  * POST /api/a11oy/v1/reason              (severity-aware governed reasoning gate)
  * GET  /api/a11oy/v1/reason/readiness    (per-capability readiness probe)
  * POST /api/a11oy/v1/reason/readiness    (5-criterion deployment-readiness gate)
  * POST /api/a11oy/v2/operator/command    (9-stage governed operator loop, HITL gate)

These routes are registered inside a defensive ``try/except`` block, so a future
edit that breaks the block (or renames/strips a route) would silently regress the
whole surface to 404 — with no test, that goes unnoticed. Every one of these
endpoints must also answer with the governed envelope (``status`` in
{REAL, DEMO, DEGRADED} + a ``citations`` list + a ``fetchedAt`` timestamp); a
stripped envelope is a contract break for downstream consoles/agents.

This module locks all of that in by booting the real app in-process via Starlette
TestClient (no mocks). It guards against:
  1. routes regressing to 404 (each must be 200),
  2. the governed envelope being stripped, and
  3. the v2 governed operator loop's human-approval gate being bypassed
     (approved:false must be HELD_FOR_APPROVAL; approved:true executes for real).
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


# --- GET surfaces: must be 200 (not 404) and carry the envelope ------------

@pytest.mark.parametrize("path,params", [
    ("/api/a11oy/v1/operator/ask", None),                       # bare descriptor
    ("/api/a11oy/v1/operator/ask", {"question": "which services are live?"}),
    ("/api/a11oy/v1/reason", None),
    ("/api/a11oy/v1/reason/readiness", None),
])
def test_get_surface_200_and_governed(client, path, params):
    r = client.get(path, params=params) if params else client.get(path)
    assert r.status_code == 200, f"GET {path} regressed to {r.status_code}"
    _assert_envelope(r.json())


# --- POST surfaces: must be 200 (not 404) and carry the envelope -----------

@pytest.mark.parametrize("path,payload", [
    ("/api/a11oy/v1/operator/ask", {"question": "what is the current status?"}),
    ("/api/a11oy/v1/operator/act", {"action": "acknowledge", "target": "demo", "note": "regression test"}),
    ("/api/a11oy/v1/reason", {"action": {"severity": "medium"}}),
    ("/api/a11oy/v1/reason/readiness", {"subject": "demo-deploy"}),
    ("/api/a11oy/v2/operator/command", {"command": "acknowledge alert", "target": "demo", "approved": False}),
])
def test_post_surface_200_and_governed(client, path, payload):
    r = client.post(path, json=payload)
    assert r.status_code == 200, f"POST {path} regressed to {r.status_code}"
    _assert_envelope(r.json())


# --- v2 governed operator loop: human-approval gate must hold --------------

def test_v2_command_unapproved_is_held(client):
    """Without explicit approval the loop must WITHHOLD execution."""
    r = client.post("/api/a11oy/v2/operator/command",
                    json={"command": "restart receipts server", "target": "szl-receipts", "approved": False})
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert body.get("outcome") == "HELD_FOR_APPROVAL"
    assert body.get("ok") is False
    # The Execute stage must NOT run for real when execution is withheld.
    exec_stage = next((s for s in body.get("stages", []) if s.get("stage") == "Execute"), None)
    assert exec_stage is not None and exec_stage.get("status") == "DEGRADED"


def test_v2_command_approved_executes(client):
    """With approval + an allowed policy the loop executes a real, enumerated action."""
    r = client.post("/api/a11oy/v2/operator/command",
                    json={"command": "acknowledge alert", "target": "demo", "approved": True})
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert body.get("outcome") == "APPROVED"
    assert body.get("ok") is True
    exec_stage = next((s for s in body.get("stages", []) if s.get("stage") == "Execute"), None)
    assert exec_stage is not None and exec_stage.get("status") == "REAL"


def test_v2_command_empty_is_rejected(client):
    """An empty command must be cleanly rejected (not a 500, not silently run)."""
    r = client.post("/api/a11oy/v2/operator/command", json={"approved": True})
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert body.get("outcome") == "REJECTED_EMPTY_COMMAND"
    assert body.get("ok") is False
