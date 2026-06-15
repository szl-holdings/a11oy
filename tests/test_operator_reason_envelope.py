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

Task #751 extended this to the sibling operator capability endpoints registered
in the SAME defensive block (operator/recommend, operator/ledger, v2
operator/command-log, policy/decide). Task #1015 closes the remaining gap by
guarding the rest of the policy & reasoning capability surface in that same block:

  * GET  /api/a11oy/v1/policy/gates
  * GET  /api/a11oy/v1/policy/threats
  * GET  /api/a11oy/v1/policy/decisions/feed
  * POST /api/a11oy/v1/policy/compliance
  * GET  /api/a11oy/v1/forecast/run
  * GET  /api/a11oy/v1/reason/tiers
  * GET  /api/a11oy/v1/capabilities/mesh

These previously returned their bare payload, so Task #1015 also wrapped each one
with the idempotent ``gov_envelope`` in ``serve.py`` (preserving the underlying
payload) so they answer with the governed envelope like the rest of the surface.

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
    # --- Task #751: sibling operator capability GETs registered in the same
    #     defensive block — also guard them against 404 + envelope-stripping.
    ("/api/a11oy/v1/operator/recommend", None),
    ("/api/a11oy/v1/operator/ledger", None),
    ("/api/a11oy/v2/operator/command-log", None),
    # --- Task #1015: the remaining policy & reasoning capability GETs registered
    #     in the SAME defensive block — guard them against 404 + envelope-stripping.
    ("/api/a11oy/v1/policy/gates", None),
    ("/api/a11oy/v1/policy/threats", None),
    ("/api/a11oy/v1/policy/decisions/feed", None),
    ("/api/a11oy/v1/forecast/run", None),
    ("/api/a11oy/v1/reason/tiers", None),
    ("/api/a11oy/v1/capabilities/mesh", None),
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
    # --- Task #751: governed policy verdict surface (same defensive block).
    ("/api/a11oy/v1/policy/decide", {"agent": "regression-test", "action": {"value": "noop"}, "request_id": "task751"}),
    # --- Task #1015: governed compliance posture surface (same defensive block).
    ("/api/a11oy/v1/policy/compliance", {"framework": "NIST"}),
])
def test_post_surface_200_and_governed(client, path, payload):
    r = client.post(path, json=payload)
    assert r.status_code == 200, f"POST {path} regressed to {r.status_code}"
    _assert_envelope(r.json())


# --- Task #751: the policy verdict must keep its decision payload under the
#     envelope (the envelope must wrap, never replace, the governed verdict).
def test_policy_decide_carries_verdict_under_envelope(client):
    r = client.post("/api/a11oy/v1/policy/decide",
                    json={"agent": "regression-test", "action": {"value": "noop"}, "request_id": "task751"})
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert body.get("decision") in ("allow", "deny"), \
        f"policy/decide dropped its verdict: {body.get('decision')!r}"
    assert isinstance(body.get("receipt_hash"), str) and body["receipt_hash"], \
        "policy/decide must keep its receipt_hash under the envelope"


# --- Task #751: the operator ledger / command-log must keep their records
#     under the envelope (wrap, never replace, the governed payload).
def test_ledger_and_cmdlog_keep_records_under_envelope(client):
    rl = client.get("/api/a11oy/v1/operator/ledger")
    assert rl.status_code == 200
    bl = rl.json()
    _assert_envelope(bl)
    assert isinstance(bl.get("receipts"), list), "operator/ledger dropped its receipts list"

    rc = client.get("/api/a11oy/v2/operator/command-log")
    assert rc.status_code == 200
    bc = rc.json()
    _assert_envelope(bc)
    assert isinstance(bc.get("receipts"), list), "operator/command-log dropped its receipts list"


# --- Task #1015: the policy & reasoning capability endpoints must keep their
#     underlying payload UNDER the envelope (the envelope must wrap, never
#     replace, the governed payload).
def test_policy_reason_caps_keep_payload_under_envelope(client):
    rg = client.get("/api/a11oy/v1/policy/gates")
    assert rg.status_code == 200
    bg = rg.json()
    _assert_envelope(bg)
    assert "gates" in bg, "policy/gates dropped its gates payload"

    rt = client.get("/api/a11oy/v1/policy/threats")
    assert rt.status_code == 200
    _assert_envelope(rt.json())

    rf = client.get("/api/a11oy/v1/policy/decisions/feed")
    assert rf.status_code == 200
    bf = rf.json()
    _assert_envelope(bf)
    assert isinstance(bf.get("verdicts"), list), "policy/decisions/feed dropped its verdicts list"

    rc = client.post("/api/a11oy/v1/policy/compliance", json={"framework": "NIST"})
    assert rc.status_code == 200
    _assert_envelope(rc.json())

    rr = client.get("/api/a11oy/v1/forecast/run")
    assert rr.status_code == 200
    br = rr.json()
    _assert_envelope(br)
    assert "prediction" in br, "forecast/run dropped its prediction payload"

    rti = client.get("/api/a11oy/v1/reason/tiers")
    assert rti.status_code == 200
    _assert_envelope(rti.json())

    rm = client.get("/api/a11oy/v1/capabilities/mesh")
    assert rm.status_code == 200
    _assert_envelope(rm.json())


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
