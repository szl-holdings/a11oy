# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Governed code-as-action kernel (GCAK) — end-to-end behavioral guard (2026-06-16).

Two demo-defining moments are asserted here, with NO mocks and NO network:

  ALLOWED PATH — a benign NumPy cell composes a variable, a SECOND cell REUSES
  that variable (proving the kernel is PERSISTENT across cells, the property that
  the single-shot _sandbox_exec does NOT have), and each executed cell mints a
  receipt that the host's in-image ECDSA key signs.

  DENIED PATH — a malicious cell (socket exfil; then key/env/file theft) is
  HARD-DENIED at the gate BEFORE any execution. The cell never runs (executed is
  False, no stdout), and an honest signed DENY-receipt is still minted. This is
  the governance working — a truthful BLOCKED, not a fabricated success.

These run the real orchestration module directly (run_cell) so the gate, the
persistent kernel, and the receipt minting are all exercised together.
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

import a11oy_code_as_action as gcak  # noqa: E402


def _make_run(goal="test"):
    return gcak._STORE.create(goal)


# ---------------------------------------------------------------------------
# ALLOWED PATH — persistence across cells + signed receipt.
# ---------------------------------------------------------------------------
def test_benign_cell_runs_and_persists_variable_to_next_cell():
    """A var bound in cell 1 must still be bound in cell 2 — the persistent-kernel
    novelty. Single-shot _sandbox_exec cannot do this."""
    run_id = _make_run("persistence")
    c1 = gcak.run_cell(run_id, "a = np.arange(10)\nprint(int(a.sum()))")
    assert c1["allowed"] is True
    assert c1["executed"] is True
    assert c1["exec_ok"] is True
    assert c1["stdout"].strip() == "45"
    assert "a" in c1["new_or_changed"]

    # Cell 2 REUSES `a` — only possible if the kernel namespace persisted.
    c2 = gcak.run_cell(run_id, "b = a[a > 5]\nprint(b.tolist())")
    assert c2["allowed"] is True
    assert c2["executed"] is True
    assert c2["exec_ok"] is True
    assert c2["stdout"].strip() == "[6, 7, 8, 9]"


def test_benign_cell_mints_signed_receipt():
    """An allowed cell mints a receipt the host's in-image key signs (DSSE)."""
    # Use the REAL host signer so we test the actual signing path, not a stub.
    import serve

    run_id = _make_run("sign")
    cell = gcak.run_cell(run_id, "x = int(np.arange(5).sum())\nprint(x)",
                         sign_fn=serve._a11oy_sign_receipt)
    receipt = cell["receipt"]
    assert receipt["receipt_type"] == "a11oy.code_as_action.cell"
    assert receipt["allowed"] is True
    assert receipt["executed"] is True
    # Signed by the in-image ECDSA-P256 key (verifiable vs /cosign.pub).
    assert cell["dsse"]["signed"] is True
    # Energy is honestly labelled — SAMPLE on this CPU node, never a fake MEASURED.
    assert receipt["energy"]["joules_label"] in ("MEASURED", "SAMPLE")


# ---------------------------------------------------------------------------
# DENIED PATH — hard gate blocks BEFORE exec; honest deny-receipt.
# ---------------------------------------------------------------------------
def test_malicious_socket_cell_is_denied_before_execution():
    """A network-exfil cell is hard-denied at the gate and NEVER runs."""
    run_id = _make_run("exfil")
    cell = gcak.run_cell(
        run_id, "import socket\ns = socket.create_connection(('8.8.8.8', 53))")
    assert cell["allowed"] is False
    assert cell["verdict"] == "DENY"
    assert cell["executed"] is False
    assert cell["stdout"] == ""           # nothing ran
    assert cell["exec_ok"] is False
    findings = cell["security"]["findings"]
    assert any("socket" in f for f in findings)


def test_malicious_secret_theft_cell_is_denied_before_execution():
    """Reading a key/env/file is hard-denied — the sandbox can never reach a
    secret, by static gate, before any code executes."""
    run_id = _make_run("theft")
    cell = gcak.run_cell(
        run_id,
        "import os\nopen('/etc/passwd').read()\nos.environ['HF_TOKEN']")
    assert cell["allowed"] is False
    assert cell["executed"] is False
    assert cell["stdout"] == ""
    findings = cell["security"]["findings"]
    # The gate flags the secret-bearing tokens AND the dangerous imports/calls.
    assert any("HF_TOKEN" in f or "environ" in f for f in findings)
    assert any("os" in f for f in findings)


def test_denied_cell_still_mints_an_honest_signed_deny_receipt():
    """Even a blocked cell produces a signed receipt — an auditable record that
    governance fired. The receipt must say it did NOT execute."""
    import serve

    run_id = _make_run("deny-receipt")
    cell = gcak.run_cell(run_id, "import socket",
                         sign_fn=serve._a11oy_sign_receipt)
    receipt = cell["receipt"]
    assert receipt["allowed"] is False
    assert receipt["executed"] is False
    assert "DENIED before exec" in receipt["honest_label"]
    # Honestly signed deny-receipt (governance is auditable, not silent).
    assert cell["dsse"]["signed"] is True
    # No energy was spent on something that never ran.
    assert receipt["exec"]["ok"] is False


def test_denied_cell_does_not_pollute_the_persistent_namespace():
    """A blocked cell must not leave state behind: after a DENY, a later benign
    cell sees a clean namespace (the denied var name is absent)."""
    run_id = _make_run("clean")
    denied = gcak.run_cell(run_id, "import os\nstolen = os.environ.get('HF_TOKEN')")
    assert denied["executed"] is False

    # A subsequent benign cell can still run; `stolen` must NOT be defined.
    probe = gcak.run_cell(run_id, "print('stolen' in dir())")
    assert probe["executed"] is True
    assert probe["stdout"].strip() == "False"
