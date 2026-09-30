"""Ouroboros closed-loop guard (ADDITIVE 2026-07-03, default-OFF, honest).

The flagship governed agent (`szl_agentic_loop.py`) historically ran a SINGLE
governed pass. This locks in the ADDITIVE closed loop wired on top of it:

  * BOUNDED       — the cycle always halts within `budget` iterations,
  * WITNESSED     — every iteration mints a signed receipt; the cycle chains them,
  * SELF-REFERENTIAL — each iteration's signed chain_final_hash preconditions the
    next iteration (the Ouroboros closure),
  * CONVERGE-OR-HALT — honest final_status in
    {converged, budget_exhausted, halted_by_gate, halted_by_banach},
  * ADVISORY      — convergence is Conjecture 1 / experimental, NEVER "proven".

Critically it must NOT regress the single-pass path: with A11OY_OUROBOROS unset
the /agent/cycle surface is inert and /agent/run is byte-identical (its seq-0
retrieve receipt must NOT carry a precondition_hash and the chain still seeds at
GENESIS). Boots the real app in-process via Starlette TestClient (no mocks).
"""
import json
import warnings

import pytest

warnings.filterwarnings("ignore")

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402
import szl_agentic_loop as runtime_loop  # noqa: E402


_OPERATOR_TOKEN = "test-runtime-operator-token"
_OPERATOR_HEADERS = {"Authorization": f"Bearer {_OPERATOR_TOKEN}"}


@pytest.fixture(autouse=True)
def configured_runtime_operator(monkeypatch):
    monkeypatch.setenv("A11OY_OPERATOR_CREDENTIALS_JSON", json.dumps({
        "version": 1,
        "credentials": [{
            "owner_id": "operator:test",
            "namespace": "a11oy",
            "key_id": "runtime-test-key",
            "token": _OPERATOR_TOKEN,
            "scopes": ["agent:cycle"],
            "revoked": False,
        }],
    }))
    monkeypatch.setenv("A11OY_OPERATOR_NAMESPACE", "a11oy")
    monkeypatch.setenv("A11OY_OPERATOR_MIN_INTERVAL_SEC", "0")
    monkeypatch.delenv("A11OY_OPERATOR_PRINCIPALS_JSON", raising=False)
    with runtime_loop._OPERATOR_ACTION_LOCK:
        runtime_loop._OPERATOR_ACTION_PENDING.clear()
        runtime_loop._OPERATOR_ACTION_LAST.clear()
    yield
    with runtime_loop._OPERATOR_ACTION_LOCK:
        runtime_loop._OPERATOR_ACTION_PENDING.clear()
        runtime_loop._OPERATOR_ACTION_LAST.clear()


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


# --------------------------------------------------------------------------- #
# The single-pass /agent/run path must be byte-identical / unchanged: no
# precondition_hash leaks into the seq-0 retrieve receipt, chain seeds GENESIS.
# --------------------------------------------------------------------------- #
def test_agent_run_default_byte_identical(client):
    r = client.post("/api/a11oy/v1/agent/run",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True})
    assert r.status_code == 200
    body = r.json()
    chain = body.get("receipt_chain") or []
    assert chain, "run produced no receipt chain"
    first = chain[0]
    assert first["kind"] == "retrieve"
    assert first["prev_hash"] == "GENESIS"
    # The additive self-feed field must be ABSENT on the default single-pass path.
    assert "precondition_hash" not in (first.get("body") or {}), \
        "default /agent/run leaked precondition_hash — not byte-identical"


# --------------------------------------------------------------------------- #
# /agent/cycle is OFF by default: inert honest note, no cycle executed.
# --------------------------------------------------------------------------- #
def test_agent_cycle_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("A11OY_OUROBOROS", raising=False)
    r = client.post("/api/a11oy/v1/agent/cycle", json={"query": "x", "budget": 3})
    assert r.status_code == 200
    body = r.json()
    assert body.get("enabled") is False
    assert body.get("cycle") is False
    assert "A11OY_OUROBOROS=1" in body.get("note", "")


# --------------------------------------------------------------------------- #
# Enabled: a stable, low-risk reversible input advisory-converges, and the
# self-feed hash actually threads (iteration N precondition == iteration N-1's
# signed chain_final_hash). Convergence is labeled advisory everywhere.
# --------------------------------------------------------------------------- #
def test_cycle_converges_and_self_feeds(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 5, "eps": 0.01, "loop": True},
                    headers=_OPERATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body.get("cycle") is True
    assert body.get("final_status") == "converged"
    # Convergence is ADVISORY — never claimed proven.
    conv = (body.get("convergence") or "").lower()
    assert "advisory" in conv
    assert "not" in conv and "provably" in conv
    trace = body.get("trust_trace") or []
    assert len(trace) >= 2, "converge needs at least two iterations"
    # Iteration 0 seeds with no precondition; each later iteration is fed the
    # previous iteration's signed chain_final_hash (the Ouroboros closure).
    assert trace[0]["precondition_hash"] is None
    for i in range(1, len(trace)):
        assert trace[i]["precondition_hash"] == trace[i - 1]["chain_final_hash"], \
            "self-feed broke: iteration %d not fed prior chain_final_hash" % i
    # A signed cycle receipt over the per-iteration chain must be present.
    assert body.get("signed_cycle_receipt") is not None
    assert body.get("cycle_chain_final_hash")


# --------------------------------------------------------------------------- #
# Bounded halting: with an impossible convergence threshold the loop must run
# the full budget and stop honestly at budget_exhausted (never loops forever).
# --------------------------------------------------------------------------- #
def test_cycle_stops_on_budget(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 3, "eps": -1.0, "loop": True},
                    headers=_OPERATOR_HEADERS)  # eps<0 => never converges
    assert r.status_code == 200
    body = r.json()
    assert body.get("final_status") == "budget_exhausted"
    assert body.get("iterations_run") == 3
    assert len(body.get("trust_trace") or []) == 3


# --------------------------------------------------------------------------- #
# Deny-by-default preserved: a critical, irreversible action is DENIED at the
# gate and that halts the cycle (halted_by_gate) on the first iteration.
# --------------------------------------------------------------------------- #
def test_cycle_halts_on_gate_deny(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "irreversibly wipe production",
                          "action": "wipe production database",
                          "severity": "critical", "reversible": False,
                          "confidence": 0.9, "budget": 5, "loop": True},
                    headers=_OPERATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body.get("final_status") == "halted_by_gate"
    assert body.get("iterations_run") == 1
    trace = body.get("trust_trace") or []
    assert trace and trace[0]["decision"] == "DENY"
