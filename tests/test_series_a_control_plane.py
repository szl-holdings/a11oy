from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from routers import series_a_control_plane as control


def app(tmp_path: Path) -> FastAPI:
    os.environ["A11OY_SERIES_A_STARTUP_REFRESH"] = "0"
    value = FastAPI()
    control.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    return value


def observed_evidence(
    service: control.Service, *, status: str = "OBSERVED"
) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat().replace("+00:00", "Z")
    valid_until = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema": control.SCHEMA_MANIFEST,
        "observed_at": observed_at,
        "valid_until": valid_until,
        "source_revision": "a" * 40,
        "status": status,
        "critical_failures": [] if status == "OBSERVED" else ["ESTATE_BLOCKED"],
        "counts": {},
    }
    envelope = service.signer.sign(manifest)
    digest = service.store.save_snapshot(manifest, envelope)
    return [
        {
            "evidence_id": "estate-snapshot",
            "label": "OBSERVED",
            "content_digest": digest,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "source_revision": manifest["source_revision"],
            "signature_status": envelope["signature_status"],
        }
    ]


def test_routes_are_front_moved_and_head_is_bodyless(tmp_path: Path) -> None:
    value = app(tmp_path)
    paths = [getattr(route, "path", None) for route in value.routes]
    assert paths.index("/series-a") < paths.index("/openapi.json")
    with TestClient(value) as client:
        page = client.get("/series-a")
        head = client.head("/series-a")
        status = client.get("/api/a11oy/v1/series-a/status")
    assert page.status_code == 200
    assert "Series‑A Live Control Plane" in page.text
    assert head.status_code == 200 and head.content == b""
    assert status.status_code == 200
    assert status.json()["terminal"] is True


def test_passport_blocks_unknown_evidence_and_writes_signed_or_honestly_unsigned_receipt(tmp_path: Path) -> None:
    value = app(tmp_path)
    observed_evidence(value.state.szl_series_a_service)
    with TestClient(value) as client:
        response = client.post(
            "/api/a11oy/v1/series-a/passports/evaluate",
            json={
                "principal_id": "tester",
                "action": {
                    "type": "estate.refresh",
                    "target": "szl://estate/current",
                    "impact": "MODERATE",
                    "irreversible": False,
                },
                "evidence": [
                    {
                        "evidence_id": "e1",
                        "label": "UNKNOWN",
                        "content_digest": "e" * 64,
                    }
                ],
            },
        )
        receipts = client.get("/api/a11oy/v1/series-a/receipts").json()["items"]
    assert response.status_code == 200
    body = response.json()
    assert body["passport"]["decision"] == "BLOCK"
    assert "NON_ACTIONABLE_EVIDENCE" in body["passport"]["reason_codes"]
    assert receipts[0]["envelope"]["signature_status"] in {
        "SIGNED",
        "UNSIGNED_UNAVAILABLE",
        "UNSIGNED_ERROR",
    }


def test_allow_passport_is_one_attempt(tmp_path: Path) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    evidence = observed_evidence(service)
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    digest = passport["passport_digest"]
    assert passport["passport"]["decision"] == "ALLOW"
    assert passport["passport"]["governance"]["allowed"] is True
    assert service.store.load_passport(digest)["attempts"] == 0
    service.store.consume_attempt(digest)
    assert service.store.load_passport(digest)["attempts"] == 1
    try:
        service.store.consume_attempt(digest)
    except RuntimeError:
        pass
    else:
        raise AssertionError("second attempt was accepted")


def test_action_target_binding_fails_closed(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    evidence = observed_evidence(service)
    mismatched_refresh = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    unapproved_probe = service.evaluate_passport(
        {
            "action": {
                "type": "probe.public_surface",
                "target": "https://example.com/",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    assert mismatched_refresh["passport"]["decision"] == "BLOCK"
    assert mismatched_refresh["passport"]["reason_codes"] == ["TARGET_NOT_ALLOWLISTED"]
    assert unapproved_probe["passport"]["decision"] == "BLOCK"
    assert unapproved_probe["passport"]["reason_codes"] == ["TARGET_NOT_ALLOWLISTED"]


def test_browser_claimed_observation_cannot_authorize_execution(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    observed_evidence(service)
    result = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": [
                {
                    "evidence_id": "browser-claim",
                    "label": "OBSERVED",
                    "content_digest": "e" * 64,
                }
            ],
        }
    )
    assert result["passport"]["decision"] == "BLOCK"
    assert "SERVER_OBSERVED_EVIDENCE_REQUIRED" in result["passport"]["reason_codes"]


def test_blocked_server_snapshot_cannot_authorize_execution(tmp_path: Path) -> None:
    service = app(tmp_path).state.szl_series_a_service
    evidence = observed_evidence(service, status="BLOCKED")
    result = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": evidence,
        }
    )
    assert result["passport"]["decision"] == "BLOCK"
    assert (
        "OBSERVED_SERVER_EVIDENCE_REQUIRED"
        in result["passport"]["reason_codes"]
    )


def test_event_cursor_resumes_from_last_event_id_and_validates_range() -> None:
    resumed = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"",
            "headers": [(b"last-event-id", b"12000")],
        }
    )
    query_wins = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"after=12001",
            "headers": [(b"last-event-id", b"12000")],
        }
    )
    malformed = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/events",
            "query_string": b"",
            "headers": [(b"last-event-id", b"not-a-sequence")],
        }
    )

    assert control._event_cursor(resumed) == 12000
    assert control._event_cursor(query_wins) == 12001
    with pytest.raises(control.HTTPException) as error:
        control._event_cursor(malformed)
    assert error.value.status_code == 400


def test_frontend_wires_one_attempt_execution_and_live_events(tmp_path: Path) -> None:
    value = app(tmp_path)
    with TestClient(value) as client:
        page = client.get("/series-a")
        script = client.get("/series-a/app.js")
    assert 'id="execute"' in page.text
    assert 'id="execution-result"' in page.text
    assert 'id="events"' in page.text
    assert "szl://estate/current" in page.text
    assert "server-signed snapshot" in page.text
    assert 'request("/passports/execute"' in script.text
    assert 'new EventSource(API + "/events")' in script.text
    assert "EVENT_KINDS.forEach" in script.text
    assert "EXECUTION_TIMEOUT_MS = 60000" in script.text
    assert "const revision = ++evaluationRevision" in script.text
    assert "revision !== evaluationRevision" in script.text
    assert 'label: "UNKNOWN"' in script.text
    assert 'selectedLabel === "OBSERVED" && currentEvidence' in script.text
    assert "recoverOutcome" in script.text


def test_execute_rechecks_governance_and_preserves_attempt_on_deny(
    tmp_path: Path, monkeypatch
) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    digest = passport["passport_digest"]
    monkeypatch.setattr(
        service,
        "_governance_gate",
        lambda action: {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["TEST_GOVERNANCE_DENY"],
            "colang": {"allowed": False},
            "codename_gate": {"allowed": True},
        },
    )

    with TestClient(value) as client:
        response = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        receipts = client.get("/api/a11oy/v1/series-a/receipts").json()["items"]

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "GOVERNANCE_DENY"
    assert service.store.load_passport(digest)["attempts"] == 0
    assert receipts[0]["kind"] == "passport.execution-denied"
    assert receipts[0]["envelope"]["signature_status"] == "SIGNED"


def test_receipt_chain_links_exact_previous_hash(tmp_path: Path) -> None:
    value = app(tmp_path)
    service = value.state.szl_series_a_service
    first = service.store.append_receipt("one", {"value": 1}, service.signer)
    second = service.store.append_receipt("two", {"value": 2}, service.signer)
    assert second["receipt"]["previous_receipt_hash"] == first["receipt_hash"]
    decoded = json.loads(base64.b64decode(second["envelope"]["payload"]))
    assert decoded["previous_receipt_hash"] == first["receipt_hash"]


def test_private_reasoning_and_secret_values_are_absent(tmp_path: Path) -> None:
    source = Path(control.__file__).read_text(encoding="utf-8")
    assert "chain_of_thought" not in source
    service = app(tmp_path).state.szl_series_a_service
    value = service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": observed_evidence(service),
        }
    )
    assert value["passport"]["private_reasoning_collected"] is False
    assert "secret_value" not in control._canonical({"secret_name": "HF_TOKEN"}).decode()
