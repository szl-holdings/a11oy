# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11.
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""pytest suite for szl_research_infra — Verified Research Infrastructure.

Process-verification ONLY: these tests assert the WORKFLOW guarantees (prereg
freezes the spec; the trial chain is tamper-EVIDENT; verify reports chain_intact
correctly; demo data is labelled SIMULATED; no private key leaks into output).
They make NO empirical claim about psi/consciousness. They run fully offline
(no network, no model keys, no signing secret).
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_research_infra as ri


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    ri.register(app, ns="a11oy")
    return TestClient(app)


SPEC = {
    "statistical_test": "one-sample two-tailed z-test vs 0",
    "stopping_rule": "FIXED N — no optional stopping",
    "N": 10,
    "alpha": 0.05,
    "directionality": "two-tailed",
}


# --- core module-level guarantees -----------------------------------------

def test_selftest_passes():
    """The bundled no-server self-test passes end-to-end."""
    out = ri._selftest()
    assert out["ok"] is True
    for k in ("prereg_freezes_spec", "changed_spec_rejected", "tamper_detected",
              "reorder_detected", "demo_simulated_labelled", "no_key_in_output"):
        assert out[k] is True, (k, out)


def test_prereg_freezes_spec_changed_analysis_rejected():
    """Re-submitting the SAME experiment_id with a CHANGED analysis_spec is rejected:
    the spec is FROZEN at first registration (the tamper-evidence guarantee)."""
    reg = ri.ResearchRegistry()
    r0 = reg.prereg("e1", "directed attention shifts an interference measure",
                    "z-score of the shift", SPEC, "Researcher A")
    assert r0["ok"] and r0["frozen"] and r0["newly_registered"]
    h0 = r0["prereg_receipt"]["content_hash"]

    # same spec -> idempotent, same hash
    r_same = reg.prereg("e1", "directed attention shifts an interference measure",
                        "z-score of the shift", SPEC, "Researcher A")
    assert r_same["ok"] and r_same["idempotent"]
    assert r_same["prereg_receipt"]["content_hash"] == h0

    # changed analysis (optional stopping) -> REJECTED
    changed = dict(SPEC); changed["stopping_rule"] = "optional stopping (peek-and-stop)"
    r_chg = reg.prereg("e1", "directed attention shifts an interference measure",
                       "z-score of the shift", changed, "Researcher A")
    assert r_chg["ok"] is False and r_chg["rejected"] is True
    assert "FROZEN" in r_chg["reason"]


def test_trial_chain_breaks_on_tamper():
    """Editing a recorded trial value breaks the hash chain -> verify catches it."""
    reg = ri.ResearchRegistry()
    reg.prereg("e2", "h", "z", SPEC, "B")
    for i in range(4):
        reg.trial("e2", trial_index=i, value=float(i), simulated=True)
    assert reg.verify("e2")["chain_intact"] is True

    reg._chains["e2"]._chain[1]["value"] = 12345.0  # tamper
    v = reg.verify("e2")
    assert v["chain_intact"] is False
    assert v["ok"] is False
    assert v["chain_verify"]["first_break"]["index"] == 1


def test_verify_reports_chain_intact_correctly():
    """A clean, untampered chain reports chain_intact True, analysis_locked True, ok True."""
    reg = ri.ResearchRegistry()
    reg.prereg("e3", "h", "z", SPEC, "C")
    for i in range(6):
        reg.trial("e3", trial_index=i, value=float(i) * 0.5, simulated=True)
    v = reg.verify("e3")
    assert v["chain_intact"] is True
    assert v["analysis_locked"] is True
    assert v["ok"] is True
    assert v["trial_count"] == 6


def test_trial_without_prereg_is_rejected():
    """A trial cannot be appended before the analysis is pre-registered."""
    reg = ri.ResearchRegistry()
    r = reg.trial("never-registered", trial_index=0, value=1.0)
    assert r["ok"] is False
    assert "BEFORE" in r["reason"]


# --- demo fixture guarantees ----------------------------------------------

def test_demo_data_labelled_simulated():
    """Every demo trial is labelled SIMULATED/DEMO and the hypothesis is marked SIMULATED."""
    dv = ri._REGISTRY.verify(ri.DEMO_EXPERIMENT_ID)
    assert dv["chain_intact"] is True
    assert dv["trial_count"] == int(ri.DEMO_ANALYSIS_SPEC["N"])
    entries = ri._REGISTRY._chains[ri.DEMO_EXPERIMENT_ID].entries()
    assert entries, "demo chain must be seeded"
    assert all("SIMULATED" in e.get("data_label", "") for e in entries)
    assert "SIMULATED" in dv["prereg_receipt"]["hypothesis"]


def test_demo_analysis_spec_is_fixed_n_no_optional_stopping():
    """The demo prereg uses fixed N + two-tailed + explicit no-optional-stopping —
    the pre-registration discipline the literature prescribes (NOT an outcome claim)."""
    spec = ri.DEMO_ANALYSIS_SPEC
    assert spec["directionality"] == "two-tailed"
    assert "FIXED N" in spec["stopping_rule"]
    assert any("optional stopping" in g for g in spec["p_hacking_guards"])


# --- honesty / no-key guarantees ------------------------------------------

def test_no_private_key_in_any_output():
    """No private-key material ever appears in prereg/trial/verify output."""
    reg = ri.ResearchRegistry()
    r0 = reg.prereg("e4", "h", "z", SPEC, "D")
    reg.trial("e4", 0, 0.0, simulated=True)
    v = reg.verify("e4")
    blob = json.dumps({"prereg": r0, "verify": v}, default=str)
    assert "PRIVATE KEY" not in blob
    assert "BEGIN EC PRIVATE KEY" not in blob


def test_honest_note_process_verification_only():
    """verify carries the honest note: process-verification only, tamper-EVIDENT not
    tamper-proof, zero empirical psi claim, Λ stays Conjecture 1."""
    dv = ri._REGISTRY.verify(ri.DEMO_EXPERIMENT_ID)
    note = dv["honest_note"]
    assert "Process-verification ONLY" in note
    assert "tamper-EVIDENT" in note and "tamper-proof" in note
    assert "ZERO empirical claim" in note
    assert "Conjecture 1" in note
    assert "locked-8" in note


def test_prereg_receipt_signing_flag_honest():
    """Offline (no signing secret) the receipt is honestly UNSIGNED — never a fabricated
    signature. With a real key present it would be signed=True."""
    reg = ri.ResearchRegistry()
    r0 = reg.prereg("e5", "h", "z", SPEC, "E")
    receipt = r0["prereg_receipt"]
    assert "signed" in receipt
    dsse = receipt["dsse"]
    if not receipt["signed"]:
        # honest unsigned envelope: no fabricated signature
        assert dsse.get("signatures") == []
        assert "UNSIGNED" in dsse.get("honesty", "")


# --- HTTP surface (end-to-end through FastAPI) ----------------------------

def test_http_prereg_trial_verify_roundtrip(client: TestClient):
    """POST prereg -> POST trial -> GET verify round-trips through the registered routes."""
    eid = "http-exp-1"
    r = client.post("/api/a11oy/v1/research/prereg", json={
        "experiment_id": eid,
        "hypothesis": "directed attention shifts an interference measure",
        "primary_outcome": "z-score of the shift",
        "analysis_spec": SPEC,
        "researcher": "HTTP Researcher",
    })
    assert r.status_code == 200, r.text
    assert r.json()["prereg_receipt"]["content_hash"]

    rt = client.post("/api/a11oy/v1/research/trial", json={
        "experiment_id": eid, "trial_index": 0, "value": 0.42, "simulated": True})
    assert rt.status_code == 200, rt.text
    assert rt.json()["chain_head"]

    rv = client.get(f"/api/a11oy/v1/research/verify/{eid}")
    assert rv.status_code == 200, rv.text
    body = rv.json()
    assert body["chain_intact"] is True
    assert body["analysis_locked"] is True
    assert body["trial_count"] == 1
    assert "Process-verification ONLY" in body["honest_note"]


def test_http_changed_spec_returns_409(client: TestClient):
    """Re-registering an experiment_id with a changed analysis returns HTTP 409 (frozen)."""
    eid = "http-exp-2"
    base = {
        "experiment_id": eid, "hypothesis": "h", "primary_outcome": "z",
        "analysis_spec": SPEC, "researcher": "R",
    }
    assert client.post("/api/a11oy/v1/research/prereg", json=base).status_code == 200
    changed = dict(base); changed["analysis_spec"] = {**SPEC, "N": 9999}
    r = client.post("/api/a11oy/v1/research/prereg", json=changed)
    assert r.status_code == 409
    assert r.json()["rejected"] is True


def test_http_demo_verify(client: TestClient):
    """The bundled demo experiment verifies as an intact, SIMULATED chain over HTTP."""
    rv = client.get(f"/api/a11oy/v1/research/verify/{ri.DEMO_EXPERIMENT_ID}")
    assert rv.status_code == 200
    body = rv.json()
    assert body["chain_intact"] is True
    assert body["trial_count"] == int(ri.DEMO_ANALYSIS_SPEC["N"])
    assert "SIMULATED" in body["prereg_receipt"]["hypothesis"]


def test_http_trial_missing_fields_400(client: TestClient):
    r = client.post("/api/a11oy/v1/research/trial", json={"experiment_id": "x"})
    assert r.status_code == 400
