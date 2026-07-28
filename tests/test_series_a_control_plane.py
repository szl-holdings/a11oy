from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import series_a_control_plane as control


def app(tmp_path: Path) -> FastAPI:
    os.environ["A11OY_SERIES_A_STARTUP_REFRESH"] = "0"
    value = FastAPI()
    control.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    return value


def observed_evidence(service: control.Service) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat().replace("+00:00", "Z")
    valid_until = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema": control.SCHEMA_MANIFEST,
        "observed_at": observed_at,
        "valid_until": valid_until,
        "source_revision": "a" * 40,
        "status": "OBSERVED",
        "critical_failures": [],
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


def test_frontend_wires_one_attempt_execution_and_live_events(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    value = app(tmp_path)
    revision = control._git_revision()
    with TestClient(value) as client:
        page = client.get("/series-a")
        script = client.get(f"/series-a/app.js?v={revision}")
        style = client.get(f"/series-a/styles.css?v={revision}")
        unversioned_script = client.get("/series-a/app.js")
    assert 'id="execute"' in page.text
    assert 'id="execution-result"' in page.text
    assert 'id="events"' in page.text
    assert "szl://estate/current" in page.text
    assert "server-signed snapshot" in page.text
    assert f'/series-a/app.js?v={revision}' in page.text
    assert f'/series-a/styles.css?v={revision}' in page.text
    assert "__SOURCE_REVISION__" not in page.text
    assert script.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert style.headers["cache-control"] == "public,max-age=31536000,immutable"
    assert unversioned_script.headers["cache-control"] == "no-store"
    assert 'request("/passports/execute"' in script.text
    assert 'new EventSource(API + "/events")' in script.text
    assert "EVENT_KINDS.forEach" in script.text
    assert "EXECUTION_TIMEOUT_MS = 135000" in script.text
    assert "const revision = ++evaluationRevision" in script.text
    assert "revision !== evaluationRevision" in script.text
    assert 'label: "UNKNOWN"' in script.text
    assert 'selectedLabel === "OBSERVED" && currentEvidence' in script.text
    assert "recoverOutcome" in script.text
    assert "/passports/outcomes/${encodeURIComponent(passportDigest)}" in script.text
    assert "PENDING_RECONCILIATION" in script.text


def test_unknown_source_revision_never_makes_assets_immutable(
    tmp_path: Path, monkeypatch
) -> None:
    for key in ("SZL_GIT_SHA", "A11OY_GIT_SHA", "GITHUB_SHA"):
        monkeypatch.delenv(key, raising=False)
    value = app(tmp_path)
    with TestClient(value) as client:
        page = client.get("/series-a")
        script = client.get("/series-a/app.js?v=UNKNOWN")
    assert "/series-a/app.js?v=UNKNOWN" in page.text
    assert script.headers["cache-control"] == "no-store"


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


def test_successful_execution_is_recoverable_by_passport_digest(
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

    async def probe(target: str) -> dict[str, object]:
        return {
            "status": "SUCCEEDED",
            "target": target,
            "http_status": 200,
            "latency_ms": 1,
        }

    monkeypatch.setattr(service, "_probe", probe)

    with TestClient(value) as client:
        missing = client.get(
            "/api/a11oy/v1/series-a/passports/outcomes/" + ("f" * 64)
        )
        executed = client.post(
            "/api/a11oy/v1/series-a/passports/execute",
            json={"passport_digest": digest},
        )
        recovered = client.get(
            f"/api/a11oy/v1/series-a/passports/outcomes/{digest}"
        )

    assert missing.status_code == 404
    assert executed.status_code == 200
    assert recovered.status_code == 200
    assert recovered.json()["outcome"] == executed.json()["outcome"]
    assert (
        recovered.json()["outcome_receipt"]["receipt_hash"]
        == executed.json()["outcome_receipt"]["receipt_hash"]
    )
    assert recovered.headers["cache-control"] == "no-store"
    assert recovered.json()["outcome"]["status"] == "SUCCEEDED"
    assert recovered.json()["outcome_receipt"]["kind"] == "passport.outcome"


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
