"""SGH structured-graph control guard (ADDITIVE 2026-07-03, default-OFF, honest).

Locks in the OPTIONAL SGH node state machine that WRAPS the governed Ouroboros
cycle (inspiration: arXiv:2604.11378, own-code reimplementation). Asserts:

  * DEFAULT OFF  — with A11OY_SGH unset the /agent/cycle response is
    byte-identical to the core cycle (no 'sgh' key); /agent/run untouched.
  * ENABLED      — an explicit immutable plan DAG + node-state trace appears,
    the machine reaches HALT, and escalation is STRICTLY BOUNDED.
  * BOUNDED      — recovery is NEVER unbounded: attempts <= max_recover, and a
    never-converging cycle escalates then HALTs.
  * ADVISORY     — the SGH layer is labelled advisory/experimental and NEVER
    claims "provably terminating/sound"; it cites the paper as inspiration.

The module-level unit tests need no app; the wiring tests boot the real app
in-process via Starlette TestClient (no mocks).
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

import szl_sgh_scheduler as S


# --------------------------------------------------------------------------- #
# Module unit tests — no app required.
# --------------------------------------------------------------------------- #
def test_plan_is_immutable_and_versioned():
    p1 = S.build_plan()
    p2 = S.build_plan()
    assert p1["immutable"] is True
    assert p1["plan_version"].startswith("sgh-plan-")
    # Same tasks => same deterministic plan version.
    assert p1["plan_version"] == p2["plan_version"]
    # Different tasks => a DIFFERENT immutable plan (new version, not mutation).
    p3 = S.build_plan(tasks=("a", "b", "c"))
    assert p3["plan_version"] != p1["plan_version"]
    assert len(p3["nodes"]) == 3 and len(p3["edges"]) == 2


def test_satisfied_cycle_halts_without_recovery():
    core = {"final_status": "converged", "cycle_chain_final_hash": "h0"}
    r = S.wrap_governed_cycle(core, lambda: core, max_recover=3)
    assert r["sgh_final_state"] == "HALT"
    assert r["sgh_halt_reason"] == "converged"
    assert r["recover_attempts"] == 0
    assert r["escalated"] is False
    # PLAN, EXECUTE, VERIFY, HALT
    states = [t["to_state"] for t in r["node_state_trace"]]
    assert states == ["PLAN", "EXECUTE", "VERIFY", "HALT"]


def test_gate_deny_is_terminal_not_retried():
    # A deny-by-default halt is terminal: SGH must NOT retry a safety denial.
    core = {"final_status": "halted_by_gate", "cycle_chain_final_hash": "hg"}
    calls = {"n": 0}

    def reexec():
        calls["n"] += 1
        return core

    r = S.wrap_governed_cycle(core, reexec, max_recover=3)
    assert r["sgh_halt_reason"] == "halted_by_gate"
    assert r["recover_attempts"] == 0
    assert calls["n"] == 0, "gate-deny must not trigger any recovery re-execution"


def test_recovery_is_strictly_bounded_then_escalates():
    core = {"final_status": "budget_exhausted", "cycle_chain_final_hash": "hb"}
    calls = {"n": 0}

    def reexec():
        calls["n"] += 1
        return core  # never converges

    r = S.wrap_governed_cycle(core, reexec, max_recover=2)
    assert r["sgh_final_state"] == "HALT"
    assert r["escalated"] is True
    assert r["recover_attempts"] == 2, "must stop at max_recover, never unbounded"
    assert calls["n"] == 2, "exactly max_recover re-executions, no more"
    assert r["sgh_halt_reason"].startswith("escalated_after_2_recover_attempts")
    assert r["bounded"] is True


def test_recover_ceiling_caps_max_recover():
    core = {"final_status": "budget_exhausted", "cycle_chain_final_hash": "x"}
    r = S.wrap_governed_cycle(core, lambda: core, max_recover=10_000)
    assert r["max_recover"] == S.MAX_RECOVER_CEILING
    assert r["recover_attempts"] <= S.MAX_RECOVER_CEILING


def test_plan_version_constant_across_recovery():
    core = {"final_status": "budget_exhausted", "cycle_chain_final_hash": "x"}
    r = S.wrap_governed_cycle(core, lambda: core, max_recover=3)
    versions = {t["plan_version"] for t in r["node_state_trace"]}
    assert len(versions) == 1, "plan must NOT mutate mid-run (single plan_version)"


def test_node_trace_is_hash_chained():
    core = {"final_status": "converged", "cycle_chain_final_hash": "h"}
    r = S.wrap_governed_cycle(core, lambda: core, max_recover=1)
    trace = r["node_state_trace"]
    assert trace[0]["prev_hash"] == "SGH-GENESIS"
    for i in range(1, len(trace)):
        assert trace[i]["prev_hash"] == trace[i - 1]["hash"], "SGH chain broke"
    assert r["sgh_chain_final_hash"] == trace[-1]["hash"]


def test_reexecute_error_is_honest_escalation_not_crash():
    core = {"final_status": "budget_exhausted", "cycle_chain_final_hash": "x"}

    def boom():
        raise RuntimeError("simulated re-exec failure")

    r = S.wrap_governed_cycle(core, boom, max_recover=2)
    assert r["sgh_final_state"] == "HALT"
    assert r["escalated"] is True
    assert "escalated_on_reexecute_error" in r["sgh_halt_reason"]


def test_advisory_labels_and_paper_citation():
    core = {"final_status": "converged", "cycle_chain_final_hash": "h"}
    r = S.wrap_governed_cycle(core, lambda: core)
    assert "advisory" in r["label"].lower()
    assert "experimental" in r["label"].lower()
    term = r["termination"].lower()
    assert "not a formal" in term and "future" in term
    assert "2604.11378" in r["inspiration"]
    # Must NOT overclaim.
    assert "provably terminating" not in term
    assert "provably sound" not in term


# --------------------------------------------------------------------------- #
# Wiring tests — boot the real app.
# --------------------------------------------------------------------------- #
starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


def test_cycle_default_off_no_sgh_key(client, monkeypatch):
    # Ouroboros ON but SGH unset: the cycle runs normally, NO 'sgh' key added.
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    monkeypatch.delenv("A11OY_SGH", raising=False)
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 5, "eps": 0.01})
    assert r.status_code == 200
    body = r.json()
    assert body.get("cycle") is True
    assert "sgh" not in body, "default path must be byte-identical (no sgh key)"


def test_cycle_sgh_enabled_exposes_plan_dag_and_halts(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    monkeypatch.setenv("A11OY_SGH", "1")
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 5, "eps": 0.01})
    assert r.status_code == 200
    body = r.json()
    # Core cycle fields are still present (wrapping, not replacing).
    assert body.get("cycle") is True
    assert body.get("final_status") == "converged"
    sgh = body.get("sgh")
    assert isinstance(sgh, dict), "SGH layer must be exposed when enabled"
    assert sgh["sgh_final_state"] == "HALT"
    assert sgh["plan_dag"]["immutable"] is True
    assert sgh["plan_version"].startswith("sgh-plan-")
    assert sgh["node_state_trace"], "must expose the explicit node-state trace"
    assert sgh["bounded"] is True
    # Advisory, cites the paper, no overclaim.
    assert "advisory" in sgh["label"].lower()
    assert "2604.11378" in sgh["inspiration"]
    assert "provably terminating" not in sgh["termination"].lower()


def test_cycle_sgh_bounded_escalation_on_never_converge(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    monkeypatch.setenv("A11OY_SGH", "1")
    # eps<0 => the inner cycle never converges => SGH must escalate then HALT.
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 3, "eps": -1.0})
    assert r.status_code == 200
    sgh = r.json().get("sgh")
    assert sgh is not None
    assert sgh["sgh_final_state"] == "HALT"
    assert sgh["escalated"] is True
    assert sgh["recover_attempts"] <= sgh["max_recover"]


def test_agent_run_untouched_when_sgh_enabled(client, monkeypatch):
    # /agent/run is the single-pass path — SGH must not touch it at all.
    monkeypatch.setenv("A11OY_SGH", "1")
    r = client.post("/api/a11oy/v1/agent/run",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True})
    assert r.status_code == 200
    body = r.json()
    assert "sgh" not in body
    chain = body.get("receipt_chain") or []
    assert chain and chain[0]["prev_hash"] == "GENESIS"
