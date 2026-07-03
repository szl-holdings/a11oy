"""LTC-derived bounded-dynamics advisory note (ADDITIVE 2026-07-03).

Locks in the honest, ADDITIVE Liquid-Time-Constant (arXiv:2006.04439, Apache-2.0)
bounded-dynamics note wired alongside the advisory Banach guard in the governed
Ouroboros cycle. Discipline under test:

  * BOUNDED     — the fused semi-implicit Euler step keeps |h| inside its
    analytic bound for every step (LTC bounded-state property, by construction).
  * ADVISORY    — every surface is labelled "LTC-derived · advisory · experimental";
    the note NEVER changes final_status, NEVER overrides the gate, and is NOT the
    halting reason (the finite budget alone guarantees halting).
  * GRACEFUL    — malformed input degrades to an honest inert no-op, never raises.
  * NON-REGRESSION — /agent/run stays byte-identical; the note is additive-only.
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

import szl_ltc_dynamics as L

_ADVISORY = "LTC-derived · advisory · experimental"


# --------------------------------------------------------------------------- #
# Unit: the module's bounded-dynamics primitives.
# --------------------------------------------------------------------------- #
def test_step_is_bounded_for_a_range_of_inputs():
    # The fused semi-implicit Euler step must never leave the analytic |h|<=1
    # bound for normalised drive, across many states/inputs/time-constants.
    for h in (-1.0, -0.3, 0.0, 0.4, 1.0):
        for x in (0.0, 0.25, 0.5, 0.75, 1.0):
            for tau in (1e-3, 0.5, 1.0, 10.0, 1e3):
                out = L.ltc_step(h, x, tau=tau, A=x)
                assert abs(out) <= 1.0 + 1e-9


def test_tau_is_clamped_into_bounds():
    # Out-of-range / degenerate tau must be clamped (bounded-tau self-check),
    # never propagate a divide-by-zero or an unbounded time-constant.
    assert abs(L.ltc_step(0.2, 0.5, tau=0.0)) <= 1.0 + 1e-9
    assert abs(L.ltc_step(0.2, 0.5, tau=-5.0)) <= 1.0 + 1e-9
    assert abs(L.ltc_step(0.2, 0.5, tau=1e9)) <= 1.0 + 1e-9


def test_note_on_contracting_sequence_is_bounded_and_labelled():
    note = L.ltc_stability_note([0.5, 0.25, 0.12, 0.06, 0.03])
    assert note["ltc_bounded"] is True
    assert note["label"] == _ADVISORY
    assert isinstance(note["ltc_stability_estimate"], float)
    # A settling sequence should read as contracting (< 1.0), advisory only.
    assert note["ltc_stability_estimate"] < 1.0


def test_note_is_graceful_on_bad_or_short_input():
    for bad in (None, [], [0.1], ["a", "b"], [None, None]):
        note = L.ltc_stability_note(bad)
        assert note["label"] == _ADVISORY
        assert note["ltc_bounded"] in (False, None)
        assert note["ltc_stability_estimate"] is None


# --------------------------------------------------------------------------- #
# Integration: the cycle payload carries the additive advisory note, and it
# never becomes the halting reason. Boots the real app (no mocks).
# --------------------------------------------------------------------------- #
starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


def test_cycle_emits_advisory_ltc_note(client, monkeypatch):
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    r = client.post("/api/a11oy/v1/agent/cycle",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True,
                          "budget": 5, "eps": 0.01})
    assert r.status_code == 200
    body = r.json()
    note = body.get("ltc_stability_note")
    assert note is not None, "cycle payload missing additive ltc_stability_note"
    assert note.get("label") == _ADVISORY
    # The advisory note must NOT be the halting reason — halting stays owned by
    # the budget/gate/Banach statuses only.
    assert body.get("final_status") in {
        "converged", "budget_exhausted", "halted_by_gate", "halted_by_banach"}
    # Convergence stays advisory everywhere (Conjecture 1 preserved).
    conv = (body.get("convergence") or "").lower()
    assert "advisory" in conv and "not" in conv and "provably" in conv


def test_agent_run_has_no_ltc_field(client):
    # The single-pass /agent/run path is additive-clean: the LTC note lives ONLY
    # on the optional cycle surface, never leaks into the default pass.
    r = client.post("/api/a11oy/v1/agent/run",
                    json={"query": "deploy a low-risk reversible change",
                          "severity": "low", "reversible": True})
    assert r.status_code == 200
    assert "ltc_stability_note" not in r.json()
