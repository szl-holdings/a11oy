"""Wave P · Dev 4 — DEEPEN the governed agent-loop end-to-end (Brain-powered).

Proves that POST /api/a11oy/v1/agentloop/run is a real MULTI-STEP governed run that
CHAINS, into ONE composite signed receipt:

  brain-context (corpus="brain")  →  profile  →  steps (act + Λ-gate)  →  eval  →  energy

against a real multi-step task. The Brain feed (szl_agentloop_brain) codes against the
unmerged Brain PRs' read paths — szl_brain_corpus.brain_pulse (#814) for the vault and
szl_brain_energy.brain_energy_summary (#811, /brain/energy) for power — with a GUARDED
on-main fallback (szl_brain_api / szl_energy_budget). So in THIS runtime the labels are
honestly MODELED/SAMPLE, never a fabricated node or joule, and the endpoint is 200.

Run: python3 test_deepen_agentloop_dev4.py   (also import-safe under pytest).
Additive; touches no locked-8 numbers; Λ = Conjecture 1 (advisory, never green).
"""
import os

os.environ.pop("SZL_LOCAL_LLM_URL", None)  # honest-degradation path, no local Tower

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_model_harness as H
import szl_eval_arena as E
import szl_agent_loop_governed as A

NS = "a11oy"
TASK = "write a python function that returns the first 5 primes and explain how it works"


def _build_client() -> TestClient:
    app = FastAPI()
    H.register(app, NS)
    E.register(app, NS)
    A.register(app, NS)
    return TestClient(app)


def test_agentloop_health_advertises_brain_powered():
    c = _build_client()
    r = c.get(f"/api/{NS}/v1/agentloop/health")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["composes"]["brain_feed_available"] is True, j["composes"]
    bp = j["brain_powered"]
    assert bp["available"] is True
    assert bp["corpus_id"] == "brain"
    assert bp["energy_endpoint"] == f"/api/{NS}/v1/brain/energy"
    return j


def test_agentloop_composite_chains_brain_profile_steps_eval_energy():
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/agentloop/run", json={
        "task": TASK,
        "mode": "code",
        "harness_profile_id": "szl-honest-operator",
        "consult_brain": True,
        "allocate_energy": True,
        "max_retries": 1,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True

    # multi-step governed run.
    assert len(j["steps"]) >= 2, "a real code task must decompose into multiple steps"

    body = j["composite_receipt"]["body"]

    # (a) BRAIN-CONTEXT pulled from the vault (corpus="brain"), advisory, recorded.
    assert body["brain_consulted"] is True
    bc = body["brain_context"]
    assert isinstance(bc, dict) and bc["corpus_id"] == "brain"
    assert "label" in bc and "available" in bc
    # honesty: either real passages OR an honest UNAVAILABLE — never fabricated.
    assert "MEASURED" not in str(bc.get("label"))

    # (b) PROFILE applied per step (harness attach recorded on the step).
    step0 = j["steps"][0]["final"]
    assert "harness_profile" in step0  # None or a real profile summary — never faked

    # (c) Λ-GATED STEPS — advisory, CONJECTURE, never "green"/proven.
    assert body["aggregate"]["lambda_status"] == "CONJECTURE"
    assert "advisory" in body["aggregate"]["lambda_posture"]

    # (d) SELF-EVAL via the eval-arena recorded per step.
    assert "eval" in step0 and "suite_id" in step0["eval"]

    # (e) ENERGY allocated from the Brain's harnessed power (/brain/energy), advisory.
    assert body["energy_allocated"] is True
    ea = body["energy_allocation"]
    assert isinstance(ea, dict) and "loop_allocation_joules_label" in ea
    # never a fabricated live-meter reading in this runtime (fallback is SAMPLE).
    assert "MEASURED" not in str(ea.get("label"))

    # (f) ONE composite receipt genuinely CHAINS all five, in order.
    assert body["chain_order"][0] == "brain-context"
    assert body["chain_order"][-1] == "energy"
    assert "steps(profile+act+eval)" in body["chain_order"]
    assert body["brain_digest"] and body["energy_digest"]
    assert body["run_chain_digest"], "one whole-run hash-chain digest over all five"

    # doctrine: nothing to the locked-8; composite signed (or honest UNSIGNED-LOCAL).
    assert body["locked8_touched"] is False
    assert body["locked8"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    sig = j["composite_receipt"]["signing"]
    assert sig["mode"] in ("REAL", "UNSIGNED-LOCAL")

    # composes advertises the Brain read paths it used.
    comp = body["composes"]
    assert "szl_brain_corpus" in comp["brain_context"]
    assert "/brain/energy" in comp["brain_energy"]

    # forum ingest of the ONE composite receipt.
    assert j["forum_ingest"].get("ingested") in (True, False)  # honest either way
    return j


def test_agentloop_brain_off_is_backwards_compatible():
    """consult_brain/allocate_energy=False → no brain/energy chained (old behavior)."""
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/agentloop/run", json={
        "task": "State the doctrine in one line.",
        "consult_brain": False,
        "allocate_energy": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()["composite_receipt"]["body"]
    assert body["brain_consulted"] is False and body["energy_allocated"] is False
    assert body["brain_context"] is None and body["energy_allocation"] is None
    assert body["chain_order"] == ["steps(profile+act+eval)"]
    assert body["locked8_touched"] is False
    return body


if __name__ == "__main__":
    h = test_agentloop_health_advertises_brain_powered()
    print("health: brain_feed_available=%s brain_context_available=%s brain_energy_available=%s"
          % (h["composes"]["brain_feed_available"],
             h["composes"]["brain_context_available"],
             h["composes"]["brain_energy_available"]))
    j = test_agentloop_composite_chains_brain_profile_steps_eval_energy()
    body = j["composite_receipt"]["body"]
    print("\n=== END-TO-END COMPOSITE RECEIPT (Wave P Dev 4) ===")
    print("run_id          :", j["run_id"])
    print("task            :", j["task"][:70])
    print("n_steps         :", body["n_steps"])
    print("chain_order     :", body["chain_order"])
    print("brain_context   :", (body["brain_context"] or {}).get("label"))
    print("  read_path     :", (body["brain_context"] or {}).get("read_path"))
    print("  n_passages    :", (body["brain_context"] or {}).get("n_passages"))
    print("energy_alloc    :", (body["energy_allocation"] or {}).get("label"))
    print("  read_path     :", (body["energy_allocation"] or {}).get("read_path"))
    print("  joules        :", (body["energy_allocation"] or {}).get("loop_allocation_joules"),
          (body["energy_allocation"] or {}).get("loop_allocation_joules_label"))
    print("brain_digest    :", body["brain_digest"])
    print("energy_digest   :", body["energy_digest"])
    print("run_chain_digest:", body["run_chain_digest"])
    print("lambda_status   :", body["aggregate"]["lambda_status"], "(", body["aggregate"]["lambda_posture"], ")")
    print("locked8_touched :", body["locked8_touched"])
    print("signing         :", j["composite_receipt"]["signing"]["mode"])
    print("forum_ingest    :", j["forum_ingest"])
    b = test_agentloop_brain_off_is_backwards_compatible()
    print("\nbrain-off compat: chain_order=%s brain_context=%s energy=%s"
          % (b["chain_order"], b["brain_context"], b["energy_allocation"]))
    print("\nALL DEV-4 WAVE-P END-TO-END TESTS PASSED.")
