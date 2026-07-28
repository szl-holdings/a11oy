"""Fail-closed regression coverage for the conflicted GDW surface."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import gdw_frontier
import szl_receipt_substrate


HOLD_DETAIL = {
    "schema": "szl.gdw.hold/v1",
    "status": "UNAVAILABLE",
    "label": "UNAVAILABLE",
    "reason": "GDW_CONSOLIDATION_REQUIRED",
    "write_ready": False,
    "external_effects": "DISABLED",
}


def make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "gdw.sqlite3"
    proof_dir = tmp_path / "proofs"
    monkeypatch.setenv("GDW_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("GDW_DB_PATH", str(db_path))
    monkeypatch.setenv("GDW_PROOF_DIR", str(proof_dir))
    app = FastAPI()
    registration = gdw_frontier.register(app)
    return app, db_path, proof_dir, registration


def payload():
    return {
        "session_id": "session-1",
        "request": "governed transition",
        "allowed_experts": ["planner", "retriever", "auditor"],
        "risk_budget": 0.35,
        "mode_hint": "auto",
        "dry_run": False,
    }


def auth_headers():
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": "containment-test",
    }


def assert_hold(response):
    assert response.status_code == 503
    assert response.json() == HOLD_DETAIL


def test_health_truthfully_reports_unavailable(tmp_path, monkeypatch):
    app, db_path, proof_dir, registration = make_app(tmp_path, monkeypatch)
    assert registration["state"] == "UNAVAILABLE"
    assert registration["reason"] == "GDW_CONSOLIDATION_REQUIRED"

    with TestClient(app) as client:
        for path in ("/api/a11oy/v1/gdw/healthz", "/v1/gdw/healthz"):
            response = client.get(path)
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "UNAVAILABLE"
            assert body["label"] == "UNAVAILABLE"
            assert body["reason"] == "GDW_CONSOLIDATION_REQUIRED"
            assert body["write_ready"] is False
            assert body["external_effects"] == "DISABLED"
            assert body["persistence"] == "DISABLED_PENDING_CONSOLIDATION"
            assert body["benchmark_claim"] == "UNMEASURED"

    assert not db_path.exists()
    assert not proof_dir.exists()


def test_all_operational_routes_fail_closed_without_artifacts(tmp_path, monkeypatch):
    app, db_path, proof_dir, _registration = make_app(tmp_path, monkeypatch)
    receipt_count_before = len(szl_receipt_substrate._LEDGER)

    with TestClient(app) as client:
        canonical_gets = (
            "/api/a11oy/v1/gdw/bench/meta",
            "/api/a11oy/v1/gdw/metrics",
            "/api/a11oy/v1/gdw/integrity",
            "/api/a11oy/v1/gdw/sessions/session-1",
        )
        alias_gets = (
            "/v1/gdw/bench/meta",
            "/v1/gdw/metrics",
            "/v1/gdw/integrity",
            "/v1/gdw/sessions/session-1",
        )
        for path in canonical_gets + alias_gets:
            assert_hold(client.get(path, headers=auth_headers()))

        assert_hold(
            client.post(
                "/api/a11oy/v1/gdw/step",
                json=payload(),
                headers=auth_headers(),
            )
        )
        assert_hold(
            client.post(
                "/v1/gdw/step",
                json=payload(),
                headers=auth_headers(),
            )
        )

    assert not db_path.exists()
    assert not proof_dir.exists()
    assert len(szl_receipt_substrate._LEDGER) == receipt_count_before


def test_hold_precedes_authentication(tmp_path, monkeypatch):
    app, db_path, proof_dir, _registration = make_app(tmp_path, monkeypatch)
    receipt_count_before = len(szl_receipt_substrate._LEDGER)

    with TestClient(app) as client:
        assert_hold(client.get("/api/a11oy/v1/gdw/integrity"))
        assert_hold(
            client.post(
                "/api/a11oy/v1/gdw/step",
                json=payload(),
                headers={"X-Request-Id": "no-auth"},
            )
        )
        assert_hold(client.post("/api/a11oy/v1/gdw/step"))
        assert_hold(
            client.post(
                "/api/a11oy/v1/gdw/step",
                content=b"{not-json",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "not-a-bearer-token",
                    "X-Request-Id": "spaces are not canonical",
                },
            )
        )

    assert not db_path.exists()
    assert not proof_dir.exists()
    assert len(szl_receipt_substrate._LEDGER) == receipt_count_before
