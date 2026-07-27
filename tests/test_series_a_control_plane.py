from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import series_a_control_plane as control


def app(tmp_path: Path) -> FastAPI:
    os.environ["A11OY_SERIES_A_STARTUP_REFRESH"] = "0"
    value = FastAPI()
    control.register(value, db_path=str(tmp_path / "series-a.sqlite3"))
    return value


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
                "evidence": [{"evidence_id": "e1", "label": "UNKNOWN"}],
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
    passport = service.evaluate_passport(
        {
            "principal_id": "tester",
            "action": {
                "type": "probe.public_surface",
                "target": "https://a-11-oy.com/healthz",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": [{"evidence_id": "e1", "label": "MEASURED"}],
        }
    )
    digest = passport["passport_digest"]
    assert service.store.load_passport(digest)["attempts"] == 0
    service.store.consume_attempt(digest)
    assert service.store.load_passport(digest)["attempts"] == 1
    try:
        service.store.consume_attempt(digest)
    except RuntimeError:
        pass
    else:
        raise AssertionError("second attempt was accepted")


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
    value = app(tmp_path).state.szl_series_a_service.evaluate_passport(
        {
            "action": {
                "type": "estate.refresh",
                "target": "szl://estate/current",
                "impact": "MODERATE",
                "irreversible": False,
            },
            "evidence": [{"evidence_id": "e1", "label": "MEASURED"}],
        }
    )
    assert value["passport"]["private_reasoning_collected"] is False
    assert "secret_value" not in control._canonical({"secret_name": "HF_TOKEN"}).decode()
