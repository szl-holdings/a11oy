"""HTTP-level tests for the R0513 OVERWATCH endpoint.

These complement the pure-function tests in test_overwatch.py by exercising
the FastAPI surface and asserting the doctrine guarantee that the call is
read-only — the receipt chain length must be unchanged across requests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from amaru.app import app, _chain


def test_overwatch_snapshot_endpoint_returns_panel():
    client = TestClient(app)
    resp = client.get("/overwatch/snapshot")
    assert resp.status_code == 200
    body = resp.json()
    assert body["panel_version"] == "r0513.v1"
    assert body["thesis_kernel_hash"] == "01f6c9b6"
    assert body["read_only"] is True
    assert len(body["invariants"]) == 6
    ids = [i["id"] for i in body["invariants"]]
    assert ids == ["I1", "I2", "I3", "I4", "I5", "I6"]
    # I4 is permanently reserved by doctrine.
    i4 = next(i for i in body["invariants"] if i["id"] == "I4")
    assert i4["status"] == "reserved"


def test_overwatch_snapshot_does_not_mutate_receipt_chain():
    client = TestClient(app)
    before = _chain.length()
    for _ in range(3):
        resp = client.get("/overwatch/snapshot")
        assert resp.status_code == 200
    after = _chain.length()
    assert before == after, (
        f"R0513 must be read-only: chain length changed {before} → {after}"
    )


def test_overwatch_summary_counts_sum_to_six():
    client = TestClient(app)
    body = client.get("/overwatch/snapshot").json()
    assert sum(body["summary"].values()) == 6
