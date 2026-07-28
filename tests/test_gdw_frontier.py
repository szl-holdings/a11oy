"""Operational guards for GDW auth, state, receipts, proofs, and concurrency."""

from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import gdw_frontier


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("GDW_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("GDW_DB_PATH", str(tmp_path / "gdw.sqlite3"))
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    app = FastAPI()
    gdw_frontier.register(app)
    return app


def payload(session_id="session-1", dry_run=False, risk=0.35):
    return {
        "session_id": session_id,
        "request": "governed transition",
        "allowed_experts": ["planner", "retriever", "auditor"],
        "risk_budget": risk,
        "mode_hint": "auto",
        "dry_run": dry_run,
    }


def headers(request_id):
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_auth_state_receipt_and_proof_flow(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        denied = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers={"X-Request-Id": "missing-auth"},
        )
        assert denied.status_code == 401

        first = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("flow-1"),
        )
        assert first.status_code == 200
        body = first.json()
        assert body["decision"] == "ACCEPT"
        assert body["step"] == 1
        assert len(body["state_hash"]) == 64
        assert len(body["receipt_hash"]) == 64
        assert body["proof"]["status"] == "INPUT_EXPORTED"

        second = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("flow-2"),
        )
        assert second.json()["step"] == 2

        dry = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(dry_run=True),
            headers=headers("flow-dry"),
        ).json()
        assert dry["step"] == 2
        assert dry["state_hash"] == second.json()["state_hash"]
        assert dry["receipt_hash"] is None

        replay = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("flow-2"),
        ).json()
        assert replay["replayed"] is True
        assert replay["receipt_hash"] == second.json()["receipt_hash"]

        conflict = client.post(
            "/api/a11oy/v1/gdw/step",
            json={**payload(), "request": "different content"},
            headers=headers("flow-2"),
        )
        assert conflict.status_code == 409

        integrity = client.get(
            "/api/a11oy/v1/gdw/integrity",
            headers={"Authorization": "Bearer test-token"},
        ).json()
        assert integrity["ok"] is True
        assert integrity["orphan_receipts"] == 0


def test_reject_and_quarantine_preserve_state(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        accepted = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("policy-accept"),
        ).json()
        rejected = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(risk=0.95),
            headers=headers("policy-reject"),
        ).json()
        quarantined_payload = payload(risk=0.2)
        quarantined_payload["allowed_experts"] = ["unknown"]
        quarantined = client.post(
            "/api/a11oy/v1/gdw/step",
            json=quarantined_payload,
            headers=headers("policy-quarantine"),
        ).json()
    assert rejected["decision"] == "REJECT"
    assert quarantined["decision"] == "QUARANTINE"
    assert rejected["state_hash"] == accepted["state_hash"]
    assert quarantined["state_hash"] == accepted["state_hash"]
    assert rejected["receipt_hash"] is None
    assert quarantined["receipt_hash"] is None


def test_same_session_concurrency_is_monotonic(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)

    def send(index):
        with TestClient(app) as client:
            response = client.post(
                "/api/a11oy/v1/gdw/step",
                json=payload(session_id="shared-session"),
                headers=headers(f"concurrent-{index}"),
            )
            assert response.status_code == 200
            return response.json()

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(send, range(24)))
    assert sorted(row["step"] for row in rows) == list(range(1, 25))
    assert all(row["receipt_hash"] for row in rows)

    with TestClient(app) as client:
        state = client.get(
            "/api/a11oy/v1/gdw/sessions/shared-session",
            headers={"Authorization": "Bearer test-token"},
        ).json()
        integrity = client.get(
            "/api/a11oy/v1/gdw/integrity",
            headers={"Authorization": "Bearer test-token"},
        ).json()
    assert state["step"] == 24
    assert integrity["ok"] is True


def test_metrics_and_bench_meta(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("metrics-1"),
        )
        metrics = client.get(
            "/api/a11oy/v1/gdw/metrics",
            headers={"Authorization": "Bearer test-token"},
        )
        meta = client.get(
            "/api/a11oy/v1/gdw/bench/meta",
            headers={"Authorization": "Bearer test-token"},
        )
    assert metrics.status_code == 200
    assert "gdw_requests_total" in metrics.text
    assert meta.json()["benchmark_status"] == "UNMEASURED"


def test_proof_outbox_is_durable_and_drainable(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", "outbox")
    with TestClient(app) as client:
        result = client.post(
            "/api/a11oy/v1/gdw/step",
            json=payload(),
            headers=headers("outbox-1"),
        ).json()
        integrity = client.get(
            "/api/a11oy/v1/gdw/integrity",
            headers={"Authorization": "Bearer test-token"},
        ).json()
    assert result["proof"]["status"] == "OUTBOX_PERSISTED"
    assert integrity["pending_proofs"] == 1

    from gdw_proofs import export_proof_payload
    from gdw_workspace import GDWWorkspace

    workspace = GDWWorkspace()
    pending = workspace.pending_proofs()
    artifact = export_proof_payload(pending[0]["payload"])
    workspace.mark_proof_exported(
        pending[0]["proposal_id"],
        artifact,
        "2026-07-28T00:00:00+00:00",
    )
    assert workspace.integrity()["pending_proofs"] == 0
